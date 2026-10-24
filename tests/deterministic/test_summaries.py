"""Tier-1 tests for continuity-summary freshness (`autonovel.summaries`).

A chapter's `ch_NN.summary.md` is the next drafter's memory of that
chapter. It is fresh when the fingerprint `_stamp-summary` recorded
matches the chapter's prose as it now stands; `_begin` lists the ones
that aren't for any command that reads summaries, and `_end` refuses to
close a command that changed a chapter and left its summary behind.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from autonovel import lock, summaries
from autonovel.adapters.base import parse_command
from autonovel.adapters.claude_code import ClaudeCodeAdapter
from autonovel.adapters.installer import _commands_source_dir
from autonovel.housekeeping import lifecycle
from autonovel.housekeeping.scaffold import new_book
from autonovel.paths import SeriesLayout

SUMMARY = "**Plot:** " + "Ana crosses the river and pays the toll. " * 5 + "\n"


@pytest.fixture
def demo_series(series_root: Path) -> SeriesLayout:
    series = SeriesLayout(root=series_root)
    new_book(series, book_name="one", pov="Ana")
    return series


def _chapter(series: SeriesLayout, n: int, prose: str, *, summary: str | None = SUMMARY,
             stamp: bool = True) -> Path:
    chapters = series.books / "one" / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    path = chapters / f"ch_{n:02d}.md"
    path.write_text(f"---\nchapter: {n}\nword_count: 3\n---\n# Title {n}\n\n{prose}\n",
                    encoding="utf-8")
    if summary is not None:
        (chapters / f"ch_{n:02d}.summary.md").write_text(summary, encoding="utf-8")
        if stamp:
            summaries.stamp(path)
    return path


# ------------------------------------------------------------ fingerprint


def test_body_hash_ignores_frontmatter_title_and_trailing_space() -> None:
    a = "---\nchapter: 1\nword_count: 10\n---\n# One\n\nShe rode west.\n"
    b = "---\nchapter: 1\nword_count: 12\nstatus: revised\n---\n# A New Title\n\nShe rode west.   \n\n"
    assert summaries.body_hash(a) == summaries.body_hash(b)


def test_body_hash_changes_with_the_prose() -> None:
    a = "---\nchapter: 1\n---\n\nShe rode west.\n"
    b = "---\nchapter: 1\n---\n\nShe rode east.\n"
    assert summaries.body_hash(a) != summaries.body_hash(b)


def test_stamp_adds_frontmatter_and_keeps_the_summary(demo_series: SeriesLayout) -> None:
    ch = _chapter(demo_series, 1, "She rode west.", stamp=False)
    fp = summaries.stamp(ch)
    text = ch.with_name("ch_01.summary.md").read_text(encoding="utf-8")
    assert text.startswith(f"---\nsummary_of: {fp}\n---\n")
    assert "Ana crosses the river" in text
    # Re-stamping replaces the line, never duplicates it.
    ch.write_text(ch.read_text(encoding="utf-8").replace("west", "east"), encoding="utf-8")
    fp2 = summaries.stamp(ch)
    text = ch.with_name("ch_01.summary.md").read_text(encoding="utf-8")
    assert fp2 != fp and text.count("summary_of:") == 1


def test_stamp_refuses_a_missing_or_stub_summary(demo_series: SeriesLayout) -> None:
    ch = _chapter(demo_series, 1, "She rode west.", summary=None)
    with pytest.raises(summaries.StampError):
        summaries.stamp(ch)
    ch.with_name("ch_01.summary.md").write_text("**Plot:** TBD\n", encoding="utf-8")
    with pytest.raises(summaries.StampError):
        summaries.stamp(ch)


# ------------------------------------------------------------ states


def test_states(demo_series: SeriesLayout) -> None:
    fresh = _chapter(demo_series, 1, "One.")
    stale = _chapter(demo_series, 2, "Two.")
    stale.write_text(stale.read_text(encoding="utf-8").replace("Two.", "Two, changed."),
                     encoding="utf-8")
    _chapter(demo_series, 3, "Three.", summary=None)
    legacy = _chapter(demo_series, 4, "Four.", stamp=False)
    old = time.time() - 1000
    os.utime(legacy, (old, old))
    got = {s.chapter: s.status for s in summaries.book_states(demo_series.books / "one")}
    assert got == {1: "fresh", 2: "stale", 3: "missing", 4: "unverified"}
    # A summary from before fingerprints that is older than its chapter is stale.
    os.utime(legacy.with_name("ch_04.summary.md"), (old - 10, old - 10))
    assert summaries.state(legacy).status == "stale"
    assert fresh.exists()


def test_frontmatter_only_edit_keeps_a_stamped_summary_fresh(demo_series: SeriesLayout) -> None:
    """The false alarm after every revision: revise writes the summary,
    then the chapter's word_count / status, so the chapter is newer."""
    ch = _chapter(demo_series, 1, "She rode west.")
    old = time.time() - 1000
    os.utime(ch.with_name("ch_01.summary.md"), (old, old))
    ch.write_text(ch.read_text(encoding="utf-8").replace("word_count: 3", "word_count: 4\nstatus: revised"),
                  encoding="utf-8")
    assert summaries.state(ch).status == "fresh"


# ------------------------------------------------------------ _begin


def test_begin_lists_summaries_to_refresh_for_a_command_that_reads_them(
    demo_series: SeriesLayout,
) -> None:
    _chapter(demo_series, 1, "One.")
    two = _chapter(demo_series, 2, "Two.")
    two.write_text(two.read_text(encoding="utf-8") + "More.\n", encoding="utf-8")
    _chapter(demo_series, 3, "Three.", summary=None)
    result = lifecycle.begin("autonovel:draft", "4 --book one", series=demo_series)
    assert [s.chapter for s in result.summaries_to_refresh] == [2, 3]
    # The refreshed summaries join the checkpoint, so rollback covers them.
    resolved = {str(p.relative_to(demo_series.root)) for p in result.resolved_writes}
    assert "books/one/chapters/ch_02.summary.md" in resolved


def test_begin_leaves_out_the_chapter_the_command_rewrites(demo_series: SeriesLayout) -> None:
    three = _chapter(demo_series, 3, "Three.")
    three.write_text(three.read_text(encoding="utf-8") + "More.\n", encoding="utf-8")
    result = lifecycle.begin("autonovel:draft", "3 --book one", series=demo_series)
    assert result.summaries_to_refresh == []


def test_begin_does_not_refresh_for_a_display_command(demo_series: SeriesLayout) -> None:
    two = _chapter(demo_series, 2, "Two.")
    two.write_text(two.read_text(encoding="utf-8") + "More.\n", encoding="utf-8")
    result = lifecycle.begin("autonovel:chapter-summary", "--book one", series=demo_series)
    assert not result.summaries_to_refresh


# ------------------------------------------------------------ _end gate


def test_end_gate_ignores_a_frontmatter_only_change(demo_series: SeriesLayout) -> None:
    ch = _chapter(demo_series, 5, "Prose.")
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    ch.write_text(ch.read_text(encoding="utf-8").replace("word_count: 3", "word_count: 9"),
                  encoding="utf-8")
    result = lifecycle.end("autonovel:draft", "5 --book one", status="ok",
                           wrote=["books/one/chapters/ch_05.md"], series=demo_series)
    assert not result.summary_gate
    assert lock.read(demo_series.lock_file) is None


def test_end_gate_holds_a_new_chapter_without_a_summary(demo_series: SeriesLayout) -> None:
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    _chapter(demo_series, 5, "Fresh prose.", summary=None)
    result = lifecycle.end("autonovel:draft", "5 --book one", status="ok",
                           wrote=["books/one/chapters/ch_05.md"], series=demo_series)
    assert [s.chapter for s in result.summary_gate] == [5]
    assert lock.read(demo_series.lock_file) is not None


def test_end_gate_lets_an_import_close_without_summaries(demo_series: SeriesLayout) -> None:
    """import-book writes no summaries; the next command that reads
    them writes them."""
    lifecycle.begin("autonovel:import-book", "--book one --from x", series=demo_series)
    _chapter(demo_series, 1, "Imported prose.", summary=None)
    result = lifecycle.end("autonovel:import-book", "--book one --from x", status="ok",
                           wrote=[], series=demo_series)
    assert not result.summary_gate


def test_end_gate_ignores_a_checkpoint_from_an_earlier_run(demo_series: SeriesLayout) -> None:
    """Only the closing run's own checkpoint counts: a chapter changed
    since an earlier run of the same command doesn't hold this one."""
    ch = _chapter(demo_series, 5, "Prose.")
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    lifecycle.end("autonovel:draft", "5 --book one", status="ok", wrote=[], series=demo_series)
    ch.write_text(ch.read_text(encoding="utf-8") + "Hand edit.\n", encoding="utf-8")
    # A later run of a different command that writes no chapters.
    lifecycle.begin("autonovel:next", "--book one", series=demo_series)
    result = lifecycle.end("autonovel:next", "--book one", status="ok", wrote=[],
                           series=demo_series)
    assert not result.summary_gate


# ------------------------------------------------------------ commands and adapters


def _cmd(stem: str):
    return parse_command(_commands_source_dir() / f"{stem}.md")


def test_refresh_mode_follows_reads_unless_the_command_reports() -> None:
    assert _cmd("draft").refreshes_summaries
    assert _cmd("evaluate").refreshes_summaries
    assert not _cmd("revise").refreshes_summaries  # reads no summary
    for stem in ("summarize-chapter", "chapter-summary", "summaries", "dashboard",
                 "next", "story-map", "diff", "series-arc"):
        assert _cmd(stem).reads_summaries
        assert not _cmd(stem).refreshes_summaries, stem


def test_claude_render_carries_the_refresh_step_only_where_it_applies() -> None:
    adapter = ClaudeCodeAdapter()
    draft = adapter.render(_cmd("draft"))
    assert "summaries to refresh:" in draft and "autonovel _stamp-summary" in draft
    assert "Task" in draft.split("\n---", 1)[0]  # allowed-tools
    assert "SUMMARY GATE" in draft
    status = adapter.render(_cmd("chapter-summary"))
    assert "summaries to refresh:" not in status


# ------------------------------------------------------------ CLI


def _run(series_root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ}
    return subprocess.run([sys.executable, "-m", "autonovel.cli", *args], cwd=series_root,
                          capture_output=True, text=True, env=env)


def test_cli_stamp_and_check(demo_series: SeriesLayout) -> None:
    ch = _chapter(demo_series, 1, "One.", stamp=False)
    ch.write_text(ch.read_text(encoding="utf-8") + "More.\n", encoding="utf-8")
    old = time.time() - 1000
    os.utime(ch.with_name("ch_01.summary.md"), (old, old))
    r = _run(demo_series.root, "mechanical", "summary-check", "books/one")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["needs_refresh"] == [1]
    r = _run(demo_series.root, "_stamp-summary", "--book", "one", "--chapter", "1")
    assert r.returncode == 0, r.stderr
    assert "stamped: chapter 1" in r.stdout
    r = _run(demo_series.root, "mechanical", "summary-check", "books/one", "--format", "markdown")
    assert "All 1 summaries match" in r.stdout


def test_cli_end_exits_3_on_the_gate(demo_series: SeriesLayout) -> None:
    ch = _chapter(demo_series, 5, "Prose.")
    r = _run(demo_series.root, "_begin", "--command", "autonovel:draft", "--args", "5 --book one")
    assert r.returncode == 0, r.stderr
    ch.write_text(ch.read_text(encoding="utf-8") + "New scene.\n", encoding="utf-8")
    r = _run(demo_series.root, "_end", "--command", "autonovel:draft", "--args", "5 --book one",
             "--status", "ok", "--wrote", "books/one/chapters/ch_05.md")
    assert r.returncode == 3
    assert "SUMMARY GATE" in r.stdout
    r = _run(demo_series.root, "_stamp-summary", "--book", "one", "--chapter", "5")
    assert r.returncode == 0
    r = _run(demo_series.root, "_end", "--command", "autonovel:draft", "--args", "5 --book one",
             "--status", "ok", "--wrote", "books/one/chapters/ch_05.md")
    assert r.returncode == 0 and "**Done:**" in r.stdout


# ------------------------------------------------------------ briefs


def _brief(series: SeriesLayout, n: int, text: str = "---\nkind: prose\n---\n\n# Brief\n\nCut the tag.\n") -> Path:
    briefs = series.books / "one" / "briefs"
    briefs.mkdir(parents=True, exist_ok=True)
    path = briefs / f"ch{n:02d}.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_brief_is_pending_until_the_chapter_is_rewritten(demo_series: SeriesLayout) -> None:
    ch = _chapter(demo_series, 5, "Prose.")
    b = _brief(demo_series, 5)
    summaries.stamp_brief(ch)
    assert "brief_for:" in b.read_text(encoding="utf-8")
    assert "kind: prose" in b.read_text(encoding="utf-8")
    assert summaries.brief_pending(ch) is True
    ch.write_text(ch.read_text(encoding="utf-8").replace("Prose.", "Revised prose."), encoding="utf-8")
    # A worker touching the brief after the rewrite doesn't make it pending again.
    later = time.time() + 100
    os.utime(b, (later, later))
    assert summaries.brief_pending(ch) is False


def test_legacy_brief_falls_back_to_mtime(demo_series: SeriesLayout) -> None:
    ch = _chapter(demo_series, 5, "Prose.")
    b = _brief(demo_series, 5)
    old = time.time() - 1000
    os.utime(ch, (old, old))
    assert summaries.brief_pending(ch) is True
    os.utime(b, (old - 10, old - 10))
    assert summaries.brief_pending(ch) is False


def test_next_does_not_offer_a_consumed_brief(demo_series: SeriesLayout) -> None:
    from autonovel.housekeeping import next_actions
    ch = _chapter(demo_series, 5, "Prose.")
    b = _brief(demo_series, 5)
    summaries.stamp_brief(ch)
    ch.write_text(ch.read_text(encoding="utf-8") + "A new line.\n", encoding="utf-8")
    summaries.stamp(ch)
    later = time.time() + 100
    os.utime(b, (later, later))
    acts = next_actions.enumerate_actions(demo_series, book="one")
    assert not any("fresh briefs" in a.title for a in acts)
