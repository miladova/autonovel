"""Tier-1 tests for `autonovel _begin` / `_end` lifecycle."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from autonovel import command_log, last_action, lock
from autonovel.housekeeping import lifecycle
from autonovel.housekeeping.scaffold import new_book
from autonovel.paths import SeriesLayout


@pytest.fixture
def demo_series(series_root: Path) -> SeriesLayout:
    series = SeriesLayout(root=series_root)
    new_book(series, book_name="one", pov="Ana")
    return series


def test_begin_creates_lock_and_checkpoint(demo_series: SeriesLayout) -> None:
    result = lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    assert demo_series.lock_file.exists()
    assert result.checkpoint is not None
    # Two writes are declared by commands/draft.md; both should resolve under books/one.
    resolved_strs = {str(p.relative_to(demo_series.root)) for p in result.resolved_writes}
    assert "books/one/chapters/ch_05.md" in resolved_strs
    assert "books/one/pending_canon.md" in resolved_strs

    # Checkpoint snapshotted pending_canon.md (which exists) as .bak and the
    # ch_05.md as .absent.
    cp_dir = result.checkpoint.directory
    assert (cp_dir / "books/one/pending_canon.md.bak").exists()
    assert (cp_dir / "books/one/chapters/ch_05.md.absent").exists()


def test_end_releases_lock_and_writes_last_action(demo_series: SeriesLayout) -> None:
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft",
        "5 --book one",
        status="ok",
        wrote=["books/one/chapters/ch_05.md"],
        series=demo_series,
    )
    assert not demo_series.lock_file.exists()
    la = last_action.read(demo_series.last_action_file)
    assert la is not None
    assert la.command == "autonovel:draft"
    assert la.book == "one"
    assert la.next_standard_step  # non-empty
    assert "/autonovel:draft" in result.footer  # footer contains the command line
    assert "**Next:**" in result.footer

    log_entries = command_log.read_all(demo_series.command_log_file)
    assert any(e.command == "autonovel:draft" and e.status == "ok" for e in log_entries)


def test_end_footer_includes_postamble_hint(demo_series: SeriesLayout) -> None:
    """Every successful command postamble appends a one-line "💡"
    hint after the Next: line. On a fresh series no situational
    signal applies, so the hint falls back to the general pool."""
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft",
        "5 --book one",
        status="ok",
        wrote=["books/one/chapters/ch_05.md"],
        series=demo_series,
    )
    assert "💡" in result.footer


def test_end_next_standard_step_override_replaces_auto_computed(
    demo_series: SeriesLayout,
) -> None:
    """Bug 1 fix from 2026-04-30: revision-pass / draft-pass write
    a multi-line action plan as next_standard_step. Without the
    override flag, the auto-computed `_next_step_for(series, book)`
    wins (typically "draft N+1") and the sweep's careful closer is
    dropped. The override must reach last_action.json verbatim."""
    custom_plan = (
        "1. Verify deltas: <details>\n"
        "2. Re-run reader-panel + review:\n"
        "     /autonovel:reader-panel --book one\n"
        "     /autonovel:review --book one\n"
        "3. Backup: git add . && git commit && git push"
    )
    lifecycle.begin("autonovel:revision-pass", "--chapters 1-5 --book one",
                     series=demo_series)
    result = lifecycle.end(
        "autonovel:revision-pass", "--chapters 1-5 --book one",
        status="ok", wrote=[],
        series=demo_series,
        next_standard_step_override=custom_plan,
    )
    la = last_action.read(demo_series.last_action_file)
    assert la is not None
    assert la.next_standard_step == custom_plan
    assert "reader-panel" in (la.next_standard_step or "")
    # Footer surfaces the multi-line block too.
    assert "reader-panel" in result.footer


def test_end_no_override_falls_back_to_auto_computed(
    demo_series: SeriesLayout,
) -> None:
    """Default path unchanged: when override is None,
    `_next_step_for(series, book)` wins."""
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft", "5 --book one",
        status="ok", wrote=["books/one/chapters/ch_05.md"],
        series=demo_series,
    )
    la = last_action.read(demo_series.last_action_file)
    assert la is not None
    assert la.next_standard_step is not None
    # Auto-computed → should be a slash-command, single-line.
    assert "/autonovel:" in la.next_standard_step


def test_end_footer_no_hint_on_error(demo_series: SeriesLayout) -> None:
    """On status=error the postamble must not emit a hint —
    suggesting a follow-up while the command itself failed is
    misleading."""
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft",
        "5 --book one",
        status="error",
        wrote=[],
        series=demo_series,
    )
    assert "💡" not in result.footer


def test_end_error_marks_interrupted_and_skips_last_action(demo_series: SeriesLayout) -> None:
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    lifecycle.end(
        "autonovel:draft",
        "5 --book one",
        status="error",
        wrote=[],
        series=demo_series,
    )
    info = lock.read(demo_series.lock_file)
    assert info is not None and info.status == "interrupted"
    assert last_action.read(demo_series.last_action_file) is None
    log_entries = command_log.read_all(demo_series.command_log_file)
    assert any(e.status == "error" for e in log_entries)


def test_begin_refuses_when_live_lock(demo_series: SeriesLayout) -> None:
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    with pytest.raises(Exception):
        # A second begin should fail because the lock is held by our own live PID.
        lifecycle.begin("autonovel:next", "--book one", series=demo_series)


def test_begin_unknown_command_raises(demo_series: SeriesLayout) -> None:
    with pytest.raises(lifecycle.BeginError):
        lifecycle.begin("autonovel:nope", "", series=demo_series)


def test_argument_parsing_produces_book_and_chapter() -> None:
    from autonovel.adapters.base import discover_commands
    from autonovel.adapters.installer import _commands_source_dir

    draft = next(c for c in discover_commands(_commands_source_dir()) if c.name == "autonovel:draft")
    ctx = lifecycle._parse_arguments(draft, "7 --book inquisitor")
    assert ctx["book"] == "inquisitor"
    assert ctx["chapter"] == "07"
    assert ctx["prev"] == "06"


# ---------------------------------------------------------------------------
# next-step phase inference (PR-9 fixup) — STATE.md decisions log.
#
# Bug being prevented: book.status in project.yaml is set to "seed" at
# scaffold time and is not advanced by every command. The earlier
# implementation read book.status directly, so a series that had run
# gen-world/characters/canon/voice-discovery/gen-outline still got
# /autonovel:gen-world recommended as "next". The fixed implementation
# infers phase from filesystem artefacts.


def _populate_foundation(demo_series: SeriesLayout, book_root: Path) -> None:
    """Write enough content to every foundation artefact that
    `_is_populated` accepts them. Used by next-step tests that want to
    exercise post-foundation behaviour without running the actual LLM
    foundation commands."""
    long = "Real content. " * 30  # > 120 chars, no template markers
    (demo_series.shared / "world.md").write_text(f"# World\n\n{long}\n", encoding="utf-8")
    (demo_series.shared / "characters.md").write_text(f"# Characters\n\n{long}\n", encoding="utf-8")
    (demo_series.shared / "canon.md").write_text(f"# Canon\n\n{long}\n", encoding="utf-8")
    (book_root / "voice.md").write_text(f"# Voice\n\n{long}\n", encoding="utf-8")
    (book_root / "outline.md").write_text(f"# Outline\n\n{long}\n", encoding="utf-8")


def test_next_step_after_gen_outline_is_not_gen_world(demo_series: SeriesLayout) -> None:
    """After every foundation artefact is populated, the next-step
    recommendation must move past the seed-phase suggestion of
    /autonovel:gen-world."""
    book_root = demo_series.books / "one"
    _populate_foundation(demo_series, book_root)
    lifecycle.begin("autonovel:gen-outline", "--book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:gen-outline",
        "--book one",
        status="ok",
        wrote=["books/one/outline.md"],
        series=demo_series,
    )
    assert result.last_action is not None
    assert result.last_action.next_standard_step is not None
    assert "gen-world" not in result.last_action.next_standard_step, (
        f"next-step regressed to gen-world after gen-outline; got "
        f"{result.last_action.next_standard_step!r}"
    )
    assert "**Next:**" in result.footer


def test_next_step_after_drafting_advances_chapter(demo_series: SeriesLayout) -> None:
    """When chapters/ has a drafted file and foundation is populated,
    next-step must be a drafting-phase recommendation."""
    book_root = demo_series.books / "one"
    _populate_foundation(demo_series, book_root)
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_01.md").write_text(
        "---\nbook: one\nchapter: 1\npov: Ana\nstory_time: 2020-01-01\n"
        "events: []\nstatus: draft\n---\n\nProse goes here.\n",
        encoding="utf-8",
    )
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft",
        "1 --book one",
        status="ok",
        wrote=["books/one/chapters/ch_01.md"],
        series=demo_series,
    )
    next_cmd = result.last_action.next_standard_step
    assert next_cmd is not None
    assert "gen-world" not in next_cmd
    assert "gen-characters" not in next_cmd
    assert "gen-canon" not in next_cmd


def test_next_step_chains_foundation_in_order(demo_series: SeriesLayout) -> None:
    """A user running /autonovel:next after each foundation command
    should walk through the canonical sequence world → characters →
    voice → canon → outline. We assert the first missing link is
    surfaced rather than a generic foundation-evaluate suggestion."""
    book_root = demo_series.books / "one"
    long = "Real content. " * 30

    # Nothing populated → expect gen-world.
    lifecycle.begin("autonovel:gen-world", "", series=demo_series)
    r = lifecycle.end("autonovel:gen-world", "", status="ok", wrote=[],
                      series=demo_series)
    # gen-world has no --book, so book is None and next_step is skipped.
    # We assert chaining via /autonovel:draft (book-aware) instead.

    # Populate world; expect characters next.
    (demo_series.shared / "world.md").write_text(f"# World\n\n{long}\n", encoding="utf-8")
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    r = lifecycle.end("autonovel:draft", "1 --book one", status="ok", wrote=[],
                      series=demo_series)
    assert "gen-characters" in r.last_action.next_standard_step

    # Populate characters; expect voice-discovery.
    (demo_series.shared / "characters.md").write_text(f"# Characters\n\n{long}\n", encoding="utf-8")
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    r = lifecycle.end("autonovel:draft", "1 --book one", status="ok", wrote=[],
                      series=demo_series)
    assert "voice-discovery" in r.last_action.next_standard_step

    # Populate voice; expect gen-canon.
    (book_root / "voice.md").write_text(f"# Voice\n\n{long}\n", encoding="utf-8")
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    r = lifecycle.end("autonovel:draft", "1 --book one", status="ok", wrote=[],
                      series=demo_series)
    assert "gen-canon" in r.last_action.next_standard_step

    # Populate canon; expect gen-outline.
    (demo_series.shared / "canon.md").write_text(f"# Canon\n\n{long}\n", encoding="utf-8")
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    r = lifecycle.end("autonovel:draft", "1 --book one", status="ok", wrote=[],
                      series=demo_series)
    assert "gen-outline" in r.last_action.next_standard_step

    # Populate outline; foundation gap is closed; expect a non-foundation
    # next step (evaluate or draft).
    (book_root / "outline.md").write_text(f"# Outline\n\n{long}\n", encoding="utf-8")
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    r = lifecycle.end("autonovel:draft", "1 --book one", status="ok", wrote=[],
                      series=demo_series)
    nxt = r.last_action.next_standard_step
    assert "gen-world" not in nxt
    assert "gen-characters" not in nxt
    assert "voice-discovery" not in nxt
    assert "gen-canon" not in nxt
    assert "gen-outline" not in nxt


# ---------------------------------------------------------------------------
# --book inference (post-PR-9 author testing): defaulting to the last book
# the user worked on, or to the only book in a single-book project.

def test_begin_infers_book_from_last_action(demo_series: SeriesLayout) -> None:
    """If --book is missing from $ARGUMENTS, infer it from
    last-action.json (the most recent book the user worked on)."""
    new_book(demo_series, book_name="two", pov="Beatrice")
    # Last action sets the active book to "two".
    last_action.write(
        demo_series.last_action_file,
        command="autonovel:draft",
        args=["1", "--book", "two"],
        wrote=[],
        book="two",
        next_standard_step=None,
        next_rationale=None,
        sidequests=[],
    )
    # Begin a draft with NO --book in $ARGUMENTS.
    result = lifecycle.begin("autonovel:draft", "5", series=demo_series)
    assert result.resolved_book == "two"
    assert result.book_inferred is True
    # Writes resolved against the inferred book.
    paths = {str(p.relative_to(demo_series.root)) for p in result.resolved_writes}
    assert "books/two/chapters/ch_05.md" in paths


def test_begin_infers_book_from_single_book_project(demo_series: SeriesLayout) -> None:
    """If the series has exactly one book and no last-action, infer
    that book."""
    # demo_series has one book ("one") and no last-action yet.
    result = lifecycle.begin("autonovel:draft", "3", series=demo_series)
    assert result.resolved_book == "one"
    assert result.book_inferred is True


def test_begin_does_not_override_explicit_book(demo_series: SeriesLayout) -> None:
    """An explicit --book in $ARGUMENTS wins over inference."""
    new_book(demo_series, book_name="two", pov="Beatrice")
    last_action.write(
        demo_series.last_action_file,
        command="autonovel:draft",
        args=["1", "--book", "two"],
        wrote=[],
        book="two",
        next_standard_step=None,
        next_rationale=None,
        sidequests=[],
    )
    result = lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    assert result.resolved_book == "one"
    assert result.book_inferred is False


def test_begin_leaves_book_unresolved_when_ambiguous(demo_series: SeriesLayout) -> None:
    """Multiple books, no last-action, no --book — leave book
    unresolved so the LLM surfaces the usage error to the user."""
    new_book(demo_series, book_name="two")
    new_book(demo_series, book_name="three")
    result = lifecycle.begin("autonovel:draft", "5", series=demo_series)
    assert result.resolved_book is None
    assert result.book_inferred is False


# ---------------------------------------------------------------------------
# Pending-canon gate (post-PR-9 author-testing): when chapters have been
# drafted and pending_canon.md has new candidates, the right next step is
# /autonovel:promote-canon, NOT another draft. Otherwise chapter N+1 misses
# the new facts that chapter N just discovered.

def test_pending_canon_blocks_advance_after_draft(demo_series: SeriesLayout) -> None:
    book_root = demo_series.books / "one"
    _populate_foundation(demo_series, book_root)
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_01.md").write_text(
        "---\nbook: one\nchapter: 1\npov: Ana\nstory_time: 2020-01-01\n"
        "events: []\nstatus: draft\n---\n\nProse goes here.\n",
        encoding="utf-8",
    )
    # Pending canon has new entries (not the template stub).
    (book_root / "pending_canon.md").write_text(
        "# Pending canon\n\n- [Tommaso's birthday] 1487-05-12\n"
        "- [Mint fire date] 1521-11-04\n- [Brother's name] Niccolò\n",
        encoding="utf-8",
    )
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft", "1 --book one", status="ok",
        wrote=["books/one/chapters/ch_01.md"], series=demo_series,
    )
    next_cmd = result.last_action.next_standard_step
    assert next_cmd is not None
    assert "promote-canon" in next_cmd, (
        f"expected promote-canon recommendation; got {next_cmd!r}"
    )


def test_pending_canon_skipped_during_foundation(demo_series: SeriesLayout) -> None:
    """No chapters drafted yet → no canon candidates can exist; the
    pending-canon gate must not fire even if pending_canon.md happens
    to have content (e.g. user pre-loaded it)."""
    book_root = demo_series.books / "one"
    _populate_foundation(demo_series, book_root)
    (book_root / "pending_canon.md").write_text(
        "- [Tommaso's birthday] 1487-05-12\n", encoding="utf-8"
    )
    lifecycle.begin("autonovel:gen-outline", "--book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:gen-outline", "--book one", status="ok",
        wrote=["books/one/outline.md"], series=demo_series,
    )
    # Should advance to evaluate or draft, NOT to promote-canon (no
    # chapters drafted yet → no candidates to promote).
    assert "promote-canon" not in result.last_action.next_standard_step


def test_pending_canon_skipped_after_promotion(demo_series: SeriesLayout) -> None:
    """If /autonovel:promote-canon was just run and pending_canon.md
    is older than that run, don't re-suggest promote-canon."""
    import time
    book_root = demo_series.books / "one"
    _populate_foundation(demo_series, book_root)
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_01.md").write_text(
        "---\nbook: one\nchapter: 1\npov: Ana\nstory_time: 2020-01-01\n"
        "events: []\nstatus: draft\n---\n\nProse goes here.\n",
        encoding="utf-8",
    )
    pending = book_root / "pending_canon.md"
    pending.write_text(
        "- [Tommaso's birthday] 1487-05-12\n", encoding="utf-8"
    )
    # Simulate that promote-canon just ran successfully (logged in
    # command-log.jsonl), and modify pending_canon.md to be older.
    time.sleep(0.05)
    lifecycle.begin("autonovel:promote-canon", "--book one", series=demo_series)
    lifecycle.end(
        "autonovel:promote-canon", "--book one", status="ok",
        wrote=["shared/canon.md"], series=demo_series,
    )
    # Now make pending_canon.md older than the promote-canon log entry.
    import os
    older = pending.stat().st_mtime - 60
    os.utime(pending, (older, older))

    # After draft, the gate should NOT re-suggest promote-canon.
    lifecycle.begin("autonovel:draft", "2 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft", "2 --book one", status="ok",
        wrote=[], series=demo_series,
    )
    assert "promote-canon" not in result.last_action.next_standard_step


# ---------------------------------------------------------------------------
# Postamble compliance watchdog: a previous run that never closed its
# lock should be silently overridden when its PID is dead, but with a
# warning surfaced via BeginResult.abandoned_lock so the user knows.

def test_begin_takes_over_stale_lock_and_reports_it(demo_series: SeriesLayout) -> None:
    """A lock written under a non-existent PID is treated as abandoned;
    next begin succeeds and surfaces the prior info."""
    import json as _json
    from autonovel.lock import LockInfo
    # Write a lock with a PID that almost certainly doesn't exist.
    fake = LockInfo(
        pid=999999,
        runtime="claude",
        command="autonovel:draft",
        args=["3", "--book", "one"],
        started_at="2026-04-25T12:00:00+00:00",
        status="running",
    )
    demo_series.lock_file.parent.mkdir(parents=True, exist_ok=True)
    demo_series.lock_file.write_text(
        _json.dumps(fake.to_dict(), indent=2), encoding="utf-8"
    )

    result = lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    assert result.abandoned_lock is not None
    assert result.abandoned_lock.pid == 999999
    assert result.abandoned_lock.command == "autonovel:draft"
    # The new lock is held by the current process.
    assert demo_series.lock_file.exists()
    info = lock.read(demo_series.lock_file)
    assert info is not None and info.pid == os.getpid()


# ---------------------------------------------------------------------------
# Research-from-seed at the front of the foundation: when project.yaml
# has a period set and no research notes exist, the foundation gap
# recommends /autonovel:research --from-seed BEFORE gen-world.

def test_foundation_gap_recommends_research_when_period_set(demo_series: SeriesLayout) -> None:
    import yaml as _yaml
    raw = _yaml.safe_load(demo_series.project_file.read_text(encoding="utf-8"))
    raw["period"] = {"start": 1450, "end": 1550, "region": "italy"}
    demo_series.project_file.write_text(_yaml.safe_dump(raw), encoding="utf-8")

    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft", "1 --book one", status="ok", wrote=[],
        series=demo_series,
    )
    assert "research --from-seed" in result.last_action.next_standard_step


def test_foundation_gap_skips_research_for_contemporary(demo_series: SeriesLayout) -> None:
    """With no period set, research is not part of the foundation
    chain — gen-world is the first recommendation."""
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft", "1 --book one", status="ok", wrote=[],
        series=demo_series,
    )
    assert "research" not in result.last_action.next_standard_step


def test_foundation_gap_skips_research_when_notes_exist(demo_series: SeriesLayout) -> None:
    import yaml as _yaml
    raw = _yaml.safe_load(demo_series.project_file.read_text(encoding="utf-8"))
    raw["period"] = {"start": 1450, "end": 1550, "region": "italy"}
    demo_series.project_file.write_text(_yaml.safe_dump(raw), encoding="utf-8")
    notes = demo_series.shared / "research" / "notes" / "italy-1450-1550.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text(
        "# Research — Italy 1450-1550\n\n"
        + ("Real research content. " * 20),
        encoding="utf-8",
    )
    lifecycle.begin("autonovel:draft", "1 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft", "1 --book one", status="ok", wrote=[],
        series=demo_series,
    )
    # Research populated → next gap is gen-world.
    assert "research" not in result.last_action.next_standard_step
    assert "gen-world" in result.last_action.next_standard_step


# ---------------------------------------------------------------------------
# Chapter-counting must NOT count ch_NN.summary.md alongside ch_NN.md.
# Author hit this 2026-04-25 after the per-chapter-summary commit shipped:
# 3 chapters drafted + 3 summary files = 6 chapter-count, statusline and
# next-step both reported chapter 6.

def test_chapter_count_excludes_summary_files(demo_series: SeriesLayout) -> None:
    book_root = demo_series.books / "one"
    _populate_foundation(demo_series, book_root)
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    # Three drafted chapters with paired summaries (the 2026-04-25 case).
    for n in (1, 2, 3):
        (chapters / f"ch_{n:02d}.md").write_text(
            f"---\nbook: one\nchapter: {n}\npov: Ana\nstory_time: 2020-01-{n:02d}\n"
            f"events: []\nstatus: drafted\n---\n\nProse for chapter {n}.\n",
            encoding="utf-8",
        )
        (chapters / f"ch_{n:02d}.summary.md").write_text(
            f"Summary of chapter {n}: things happened.", encoding="utf-8",
        )
    lifecycle.begin("autonovel:draft", "3 --book one", series=demo_series)
    result = lifecycle.end(
        "autonovel:draft", "3 --book one", status="ok",
        wrote=["books/one/chapters/ch_03.md"], series=demo_series,
    )
    next_cmd = result.last_action.next_standard_step
    # The bug: with summary files counted, this would be `evaluate
    # --chapter 6` or `draft 7`. With the fix, it's chapter 3.
    assert "chapter 3" in next_cmd or "ch_03" in next_cmd or "--chapter 3" in next_cmd, (
        f"chapter count regressed (saw summary files as chapters?): "
        f"next_step recommended {next_cmd!r}"
    )


def test_begin_recreates_missing_session_notes_dir(demo_series: SeriesLayout) -> None:
    """A series cloned from backup arrives without the (empty, untracked)
    session-notes dir; the preamble self-heals it so `doctor` stays clean."""
    import shutil
    shutil.rmtree(demo_series.session_notes, ignore_errors=True)
    assert not demo_series.session_notes.exists()
    lifecycle.begin("autonovel:draft", "5 --book one", series=demo_series)
    assert demo_series.session_notes.is_dir()
    lifecycle.end("autonovel:draft", "5 --book one", status="ok", wrote=[], series=demo_series)
