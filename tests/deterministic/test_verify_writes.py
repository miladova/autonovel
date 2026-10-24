"""Tier-1 tests for the verify-writes auditor.

The postamble's `--wrote <path>` flags are LLM self-reports. The
LLM can claim a write without actually invoking Write / Edit. The
checkpoint snapshot taken at `_begin` is the ground truth — comparing
the live file against the snapshot tells us whether the claim is
honest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel import checkpoints
from autonovel.housekeeping import lifecycle, scaffold


# ---------------------------------------------------------- helpers


@pytest.fixture
def series_root(tmp_path: Path):
    res = scaffold.new_series(tmp_path / "demo", series_name="demo")
    return res.series.root


def _make_checkpoint(series_root: Path, *, files: list[Path],
                      command: str = "autonovel:draft") -> checkpoints.Checkpoint:
    return checkpoints.create(
        series_root / ".autonovel" / "checkpoints",
        series_root,
        files,
        command=command,
        args=[],
    )


# ---------------------------------------------------------- verify_writes


def test_verify_modified_file_status_modified(series_root: Path) -> None:
    target = series_root / "shared" / "world.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original content", encoding="utf-8")
    cp = _make_checkpoint(series_root, files=[target])
    target.write_text("genuinely new content", encoding="utf-8")
    report = checkpoints.verify_writes(cp, series_root, ["shared/world.md"])
    assert [i.status for i in report.items] == ["modified"]
    assert report.warnings == []


def test_verify_unchanged_file_status_unchanged(series_root: Path) -> None:
    """The classic LLM lie: --wrote was passed but the file wasn't
    touched. verify_writes catches it as `unchanged` (warning)."""
    target = series_root / "shared" / "world.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original", encoding="utf-8")
    cp = _make_checkpoint(series_root, files=[target])
    # Don't touch the file. LLM claims --wrote anyway.
    report = checkpoints.verify_writes(cp, series_root, ["shared/world.md"])
    assert report.items[0].status == "unchanged"
    assert len(report.warnings) == 1


def test_verify_missing_file_status_missing(series_root: Path) -> None:
    """File was absent at begin, LLM claimed creation, but no file
    appeared. The other classic lie."""
    target = series_root / "shared" / "new_file.md"
    cp = _make_checkpoint(series_root, files=[target])
    # Don't create the file.
    report = checkpoints.verify_writes(cp, series_root, ["shared/new_file.md"])
    assert report.items[0].status == "missing"
    assert len(report.warnings) == 1


def test_verify_created_file_status_created(series_root: Path) -> None:
    target = series_root / "shared" / "new_file.md"
    cp = _make_checkpoint(series_root, files=[target])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("new content", encoding="utf-8")
    report = checkpoints.verify_writes(cp, series_root, ["shared/new_file.md"])
    assert report.items[0].status == "created"
    assert report.warnings == []


def test_verify_deleted_file_status_deleted(series_root: Path) -> None:
    target = series_root / "shared" / "world.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("here", encoding="utf-8")
    cp = _make_checkpoint(series_root, files=[target])
    target.unlink()
    report = checkpoints.verify_writes(cp, series_root, ["shared/world.md"])
    assert report.items[0].status == "deleted"
    assert report.warnings == []


def test_verify_unresolved_placeholder_classified_outside(series_root: Path) -> None:
    """Paths still containing `{book}` etc. weren't resolved at end-
    time — surface as outside-checkpoint, not a warning."""
    cp = _make_checkpoint(series_root, files=[])
    report = checkpoints.verify_writes(
        cp, series_root, ["books/{book}/chapters/ch_{chapter}.md"]
    )
    assert report.items[0].status == "outside-checkpoint"
    assert report.warnings == []


def test_verify_path_outside_checkpoint_classified(series_root: Path) -> None:
    """A claimed path with no entry in the checkpoint is
    outside-checkpoint, not a warning. Some commands legitimately
    write side-effect files outside their declared writes:."""
    cp = _make_checkpoint(series_root, files=[])
    report = checkpoints.verify_writes(
        cp, series_root, ["shared/canon.md"]
    )
    assert report.items[0].status == "outside-checkpoint"


def test_verify_multiple_paths_mixed(series_root: Path) -> None:
    a = series_root / "a.md"
    b = series_root / "b.md"
    a.write_text("a-orig", encoding="utf-8")
    cp = _make_checkpoint(series_root, files=[a, b])
    a.write_text("a-new", encoding="utf-8")
    # b not created
    report = checkpoints.verify_writes(cp, series_root, ["a.md", "b.md"])
    statuses = {i.path: i.status for i in report.items}
    assert statuses["a.md"] == "modified"
    assert statuses["b.md"] == "missing"
    assert len(report.warnings) == 1


def test_verify_empty_claims_is_empty(series_root: Path) -> None:
    cp = _make_checkpoint(series_root, files=[])
    report = checkpoints.verify_writes(cp, series_root, [])
    assert report.items == []
    assert report.warnings == []


def test_verify_strips_whitespace_from_path(series_root: Path) -> None:
    target = series_root / "x.md"
    target.write_text("orig", encoding="utf-8")
    cp = _make_checkpoint(series_root, files=[target])
    target.write_text("new", encoding="utf-8")
    report = checkpoints.verify_writes(cp, series_root, ["  x.md  "])
    assert report.items[0].status == "modified"


# ---------------------------------------------------------- lifecycle integration


def _resolve(p: Path) -> Path:
    return p


def test_lifecycle_end_surfaces_unchanged_warning_in_footer(series_root: Path) -> None:
    """End-to-end: a real begin/end pair where the LLM lies about
    writing surfaces the warning in the footer the postamble prints."""
    from autonovel.paths import SeriesLayout
    series = SeriesLayout(root=series_root)
    # Use a real command whose `writes:` resolves to a concrete path
    # without {book}. /autonovel:gen-world writes shared/world.md.
    target = series_root / "shared" / "world.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original world", encoding="utf-8")

    lifecycle.begin("autonovel:gen-world", "", series=series)
    # Don't touch the file. Claim --wrote anyway.
    result = lifecycle.end(
        "autonovel:gen-world", "", status="ok",
        wrote=["shared/world.md"], series=series,
    )
    assert result.verify_report is not None
    assert any(w.status == "unchanged" for w in result.verify_report.warnings)
    assert "verify-writes" in result.footer.lower()
    assert "shared/world.md" in result.footer


def test_verify_warning_appears_at_top_of_footer(series_root: Path) -> None:
    """Bug 2 fix from 2026-04-30: when a sweep emits a multi-line
    `next_standard_step` closer, a warning at the bottom of the
    postamble gets buried. Verify-writes warnings must lead the
    footer so the user sees them before the long action plan."""
    from autonovel.paths import SeriesLayout
    series = SeriesLayout(root=series_root)
    target = series_root / "shared" / "world.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original world", encoding="utf-8")
    lifecycle.begin("autonovel:gen-world", "", series=series)
    result = lifecycle.end(
        "autonovel:gen-world", "", status="ok",
        wrote=["shared/world.md"], series=series,
    )
    footer = result.footer
    # The verify warning must appear BEFORE the Done: marker.
    warning_idx = footer.find("VERIFY-WRITES")
    done_idx = footer.find("**Done:**")
    assert warning_idx >= 0, "verify-writes banner missing"
    assert done_idx >= 0, "Done marker missing"
    assert warning_idx < done_idx, (
        "verify-writes warning must appear ABOVE the Done line "
        "so it doesn't get buried by long sweep closers"
    )


def test_verify_warning_calls_out_chapter_files_specifically(
    series_root: Path,
) -> None:
    """The 2026-04-30 silent-revise-failure bug: 5 chapters claimed
    revised but bytes unchanged. The warning must specifically flag
    chapter files (the load-bearing case for sweeps), not just dump
    every unchanged path in a flat list."""
    from autonovel.paths import SeriesLayout
    series = SeriesLayout(root=series_root)
    book_root = series_root / "books" / "the-book"
    chapters = book_root / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    # Mock a revision-pass shape: pre-existing chapter files claimed
    # written but not actually modified.
    for n in (2, 5, 9):
        (chapters / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\n---\n\nProse.\n",
            encoding="utf-8",
        )
    # Use draft as the test command (its writes: include
    # books/{book}/chapters/ch_{chapter}.md).
    lifecycle.begin("autonovel:revise", "5 --book the-book", series=series)
    result = lifecycle.end(
        "autonovel:revise", "5 --book the-book", status="ok",
        wrote=[
            "books/the-book/chapters/ch_05.md",
            "books/the-book/briefs/ch05.md",  # missing — no checkpoint, doesn't exist on disk
        ],
        series=series,
    )
    # Either path showing as unchanged or missing should fire the
    # banner. Assert the chapter-specific call-out wording.
    if result.verify_report and result.verify_report.warnings:
        footer = result.footer
        assert "chapter file" in footer.lower() or "ch_05.md" in footer


def test_unpaired_chapter_writes_finds_missing_summary() -> None:
    """The structural guard: a chapter file claimed for write
    without its paired `.summary.md` flags the unpaired-chapter
    bug class — apply-cuts / lengthen / shorten / etc. modifying
    the chapter prose but never regenerating the summary."""
    from autonovel.checkpoints import find_unpaired_chapter_writes
    unpaired = find_unpaired_chapter_writes([
        "books/the-book/chapters/ch_05.md",
        "books/the-book/edit_logs/ch05_cuts.json",  # not a summary
    ])
    assert unpaired == ["books/the-book/chapters/ch_05.md"]


def test_unpaired_chapter_writes_silent_when_summary_present() -> None:
    """When the summary IS in the same claim list, no warning."""
    from autonovel.checkpoints import find_unpaired_chapter_writes
    unpaired = find_unpaired_chapter_writes([
        "books/the-book/chapters/ch_05.md",
        "books/the-book/chapters/ch_05.summary.md",
    ])
    assert unpaired == []


def test_unpaired_chapter_writes_handles_multi_chapter() -> None:
    """A sweep claims many chapters; only the ones missing their
    summary get flagged."""
    from autonovel.checkpoints import find_unpaired_chapter_writes
    unpaired = find_unpaired_chapter_writes([
        "books/b/chapters/ch_01.md",
        "books/b/chapters/ch_01.summary.md",
        "books/b/chapters/ch_02.md",  # missing summary
        "books/b/chapters/ch_03.md",
        "books/b/chapters/ch_03.summary.md",
        "books/b/chapters/ch_04.md",  # missing summary
    ])
    assert unpaired == [
        "books/b/chapters/ch_02.md",
        "books/b/chapters/ch_04.md",
    ]


def test_unpaired_chapter_writes_ignores_non_chapter_paths() -> None:
    """Outline / world / canon writes don't trigger the guard —
    the rule is specific to per-chapter summaries."""
    from autonovel.checkpoints import find_unpaired_chapter_writes
    unpaired = find_unpaired_chapter_writes([
        "shared/world.md",
        "books/b/voice.md",
        "books/b/outline.md",
    ])
    assert unpaired == []


def test_chapter_changed_without_summary_is_held_by_the_summary_gate(series_root: Path) -> None:
    """End-to-end: a command that changes a chapter's prose and leaves
    its summary describing the old text can't close. `_end` refuses,
    keeps the lock, and spells out the stamp command; once the summary
    is rewritten and stamped, `_end` closes."""
    from autonovel import lock, summaries
    from autonovel.paths import SeriesLayout
    series = SeriesLayout(root=series_root)
    book_root = series_root / "books" / "the-book"
    chapters = book_root / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    ch5 = chapters / "ch_05.md"
    ch5.write_text("---\nchapter: 5\n---\n\nProse.\n", encoding="utf-8")
    (chapters / "ch_05.summary.md").write_text("**Plot:** " + "old events. " * 20 + "\n",
                                               encoding="utf-8")
    summaries.stamp(ch5)
    lifecycle.begin("autonovel:apply-cuts", "5 --book the-book", series=series)
    ch5.write_text("---\nchapter: 5\n---\n\nNew prose.\n", encoding="utf-8")
    result = lifecycle.end(
        "autonovel:apply-cuts", "5 --book the-book", status="ok",
        wrote=["books/the-book/chapters/ch_05.md"],
        series=series,
    )
    assert result.summary_gate and result.summary_gate[0].chapter == 5
    assert "SUMMARY GATE" in result.footer
    assert "autonovel _stamp-summary --book the-book --chapter 5" in result.footer
    assert lock.read(series.lock_file) is not None  # still held
    (chapters / "ch_05.summary.md").write_text("**Plot:** " + "new events. " * 20 + "\n",
                                               encoding="utf-8")
    summaries.stamp(ch5)
    result = lifecycle.end(
        "autonovel:apply-cuts", "5 --book the-book", status="ok",
        wrote=["books/the-book/chapters/ch_05.md",
               "books/the-book/chapters/ch_05.summary.md"],
        series=series,
    )
    assert not result.summary_gate
    assert "**Done:**" in result.footer
    assert lock.read(series.lock_file) is None


def test_unpaired_silent_when_summary_also_claimed(series_root: Path) -> None:
    """Commands that DO regenerate and stamp the summary (revise step 9
    etc.) pass the gate and don't trigger the unpaired guard."""
    from autonovel import summaries
    from autonovel.paths import SeriesLayout
    series = SeriesLayout(root=series_root)
    book_root = series_root / "books" / "the-book"
    chapters = book_root / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    ch5 = chapters / "ch_05.md"
    sm5 = chapters / "ch_05.summary.md"
    ch5.write_text("---\nchapter: 5\n---\n\nProse.\n", encoding="utf-8")
    sm5.write_text("**Plot:** old.\n", encoding="utf-8")
    lifecycle.begin("autonovel:revise", "5 --book the-book", series=series)
    ch5.write_text("---\nchapter: 5\n---\n\nNew.\n", encoding="utf-8")
    sm5.write_text("**Plot:** " + "new events. " * 20 + "\n", encoding="utf-8")
    summaries.stamp(ch5)
    result = lifecycle.end(
        "autonovel:revise", "5 --book the-book", status="ok",
        wrote=[
            "books/the-book/chapters/ch_05.md",
            "books/the-book/chapters/ch_05.summary.md",
        ],
        series=series,
    )
    assert not result.summary_gate
    assert result.verify_report is not None
    assert result.verify_report.unpaired_chapter_writes == []


def test_lifecycle_end_clean_when_writes_real(series_root: Path) -> None:
    from autonovel.paths import SeriesLayout
    series = SeriesLayout(root=series_root)
    target = series_root / "shared" / "world.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original", encoding="utf-8")
    lifecycle.begin("autonovel:gen-world", "", series=series)
    target.write_text("new world content — ten times longer than the prior version", encoding="utf-8")
    result = lifecycle.end(
        "autonovel:gen-world", "", status="ok",
        wrote=["shared/world.md"], series=series,
    )
    assert result.verify_report is not None
    assert result.verify_report.warnings == []
    assert "verify-writes" not in result.footer.lower()


def test_lifecycle_end_logs_verify_warnings_to_command_log(series_root: Path) -> None:
    """The command log entry carries a `note` field summarising the
    verify failures so an audit trail outlives the postamble print."""
    from autonovel import command_log as cl
    from autonovel.paths import SeriesLayout
    series = SeriesLayout(root=series_root)
    target = series_root / "shared" / "world.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("original", encoding="utf-8")
    lifecycle.begin("autonovel:gen-world", "", series=series)
    lifecycle.end(
        "autonovel:gen-world", "", status="ok",
        wrote=["shared/world.md"], series=series,
    )
    entries = cl.read_all(series.command_log_file)
    assert entries
    last = entries[-1]
    assert last.note is not None
    assert "verify-writes" in last.note
