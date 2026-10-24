"""Tier-1 tests for the state-aware next-actions enumerator.

Covers each per-book check (pending-canon conflicts, regressions,
panel/review/typeset staleness, missing title/author, missing front
matter), the series-wide git-backup states, the canonical pipeline
action lookup, the human render, and a CLI round-trip via
`autonovel _next-actions`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from autonovel import last_action as last_action_mod
from autonovel.housekeeping import next_actions
from autonovel.housekeeping.next_actions import NextAction
from autonovel.paths import SeriesLayout


# --------------------------------------------------------- per-book helpers


def _layout(series_root: Path) -> SeriesLayout:
    return SeriesLayout(root=series_root)


def _write_chapter(book_root: Path, n: int, content: str = "Prose. " * 100) -> Path:
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    path = chapters / f"ch_{n:02d}.md"
    path.write_text(
        f"---\nchapter: {n}\nstatus: drafted\nword_count: 1500\n---\n\n{content}",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------- pending canon conflicts


def test_pending_canon_conflict_actions_flags_blocks(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    pending = series / "books" / book / "pending_canon.md"
    pending.write_text(
        "# Conflicts — resolve before next promote-canon\n\n"
        "HOW TO RESOLVE A CONFLICT\n... blurb ...\n\n"
        "## Conflict 1\n- Pending: x\n- Existing: y\n\n"
        "## Conflict 2\n- Pending: a\n- Existing: b\n",
        encoding="utf-8",
    )
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    high = [a for a in actions if a.priority == "HIGH" and "conflict" in a.title.lower()]
    assert len(high) == 1
    assert "2" in high[0].title  # 2 conflicts


def test_pending_canon_with_no_conflict_header_emits_nothing(
    late_stage_book: tuple[Path, str]
) -> None:
    series, book = late_stage_book
    # late_stage_book wrote a pending_canon.md without a conflicts header.
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("conflict" in a.title.lower() for a in actions)


# --------------------------------------------------------- chapter regressions


def test_chapter_regression_actions_flags_drop_at_or_above_threshold(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    eval_dir = series / "books" / book / "eval_logs"
    # Chapter 7: prior best 7.5, latest 7.0 — delta 0.5 ≥ 0.3 → flagged.
    (eval_dir / "20260101_120000_ch07_eval.json").write_text(
        json.dumps({"overall_score": 7.5}), encoding="utf-8"
    )
    (eval_dir / "20260102_120000_ch07_eval.json").write_text(
        json.dumps({"overall_score": 7.0}), encoding="utf-8"
    )
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    regressions = [a for a in actions if "regressed" in a.title.lower()]
    assert len(regressions) == 1
    assert "7" in regressions[0].title
    assert "revision-pass" in (regressions[0].command or "")


def test_chapter_regression_ignores_small_drops(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    eval_dir = series / "books" / book / "eval_logs"
    # Drop 7.5 → 7.3 = 0.2 < 0.3 → ignored.
    (eval_dir / "20260101_120000_ch08_eval.json").write_text(
        json.dumps({"overall_score": 7.5}), encoding="utf-8"
    )
    (eval_dir / "20260102_120000_ch08_eval.json").write_text(
        json.dumps({"overall_score": 7.3}), encoding="utf-8"
    )
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("regressed" in a.title.lower() for a in actions)


def test_chapter_regression_handles_timestamped_naming(series_root: Path) -> None:
    """Timestamped `<ts>_chNN_eval.json` shape (the production
    naming) — flag a regression on chapter 9."""
    book = "the-book"
    book_root = series_root / "books" / book
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "20260101_120000_ch09_eval.json").write_text(
        json.dumps({"overall_score": 7.8}), encoding="utf-8"
    )
    (eval_dir / "20260201_120000_ch09_eval.json").write_text(
        json.dumps({"overall_score": 7.0}), encoding="utf-8"
    )
    # Wire the book into project.yaml so the per-book pass scans it.
    from autonovel import project as project_mod
    cfg = project_mod.load(_layout(series_root).project_file)
    cfg.books.append(project_mod.BookEntry(name=book, status="drafting"))
    project_mod.dump(cfg, _layout(series_root).project_file)
    actions = next_actions.enumerate_actions(_layout(series_root), book=book)
    regressions = [a for a in actions if "regressed" in a.title.lower()]
    assert any("9" in a.title for a in regressions)


# --------------------------------------------------------- brief newer than chapter


def test_brief_newer_than_chapter_flags_revise(
    late_stage_book: tuple[Path, str],
) -> None:
    """Brief at briefs/ch02.md exists in the fixture; force its mtime
    to be newer than the chapter and confirm we recommend revise."""
    series, book = late_stage_book
    book_root = series / "books" / book
    chapter = book_root / "chapters" / "ch_02.md"
    brief = book_root / "briefs" / "ch02.md"
    older = time.time() - 1000
    os.utime(chapter, (older, older))
    newer = time.time()
    os.utime(brief, (newer, newer))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    revise = [a for a in actions if "fresh brief" in a.title.lower()]
    assert len(revise) == 1
    assert revise[0].priority == "HIGH"
    assert revise[0].command is not None
    # Single chapter → revise --chapter 2.
    assert "revise --chapter 2" in revise[0].command


def test_brief_older_than_chapter_silent(
    late_stage_book: tuple[Path, str],
) -> None:
    """Brief older than its chapter (the chapter has been revised
    against it already) → no signal."""
    series, book = late_stage_book
    book_root = series / "books" / book
    chapter = book_root / "chapters" / "ch_02.md"
    brief = book_root / "briefs" / "ch02.md"
    older = time.time() - 1000
    os.utime(brief, (older, older))
    newer = time.time()
    os.utime(chapter, (newer, newer))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("fresh brief" in a.title.lower() for a in actions)


def test_multiple_fresh_briefs_recommend_revision_pass(
    late_stage_book: tuple[Path, str],
) -> None:
    """Three fresh briefs → revision-pass with comma-list of chapters."""
    series, book = late_stage_book
    book_root = series / "books" / book
    briefs_dir = book_root / "briefs"
    older = time.time() - 1000
    newer = time.time()
    for n in (1, 3, 5):
        chapter = book_root / "chapters" / f"ch_{n:02d}.md"
        os.utime(chapter, (older, older))
        brief = briefs_dir / f"ch{n:02d}.md"
        brief.write_text(f"# Brief for ch {n}\n\n- Tighten.\n", encoding="utf-8")
        os.utime(brief, (newer, newer))
    # Also touch the existing ch02 brief to be older so it doesn't fire.
    os.utime(briefs_dir / "ch02.md", (older - 1, older - 1))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    revise = [a for a in actions if "fresh brief" in a.title.lower()]
    assert len(revise) == 1
    assert "1,3,5" in revise[0].title
    assert "revision-pass" in (revise[0].command or "")


def test_brief_without_matching_chapter_silent(
    late_stage_book: tuple[Path, str],
) -> None:
    """Stray brief for a chapter that doesn't exist → silent (no
    chapter to compare mtimes against)."""
    series, book = late_stage_book
    book_root = series / "books" / book
    (book_root / "briefs" / "ch99.md").write_text("orphan brief", encoding="utf-8")
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    titles = " | ".join(a.title for a in actions)
    assert "ch 99" not in titles.lower() and "ch99" not in titles.lower()


def test_conversation_md_does_not_trigger_brief_signal(
    late_stage_book: tuple[Path, str],
) -> None:
    """briefs/conversation.md is the talk-queue, not a per-chapter
    brief. Must not match the regex."""
    series, book = late_stage_book
    book_root = series / "books" / book
    conversation = book_root / "briefs" / "conversation.md"
    conversation.write_text("Status: queued\nTarget: chapter 2\n",
                             encoding="utf-8")
    # Make sure conversation.md is newer than every chapter so it
    # would fire if the regex were broken.
    older = time.time() - 1000
    for ch_path in (book_root / "chapters").glob("ch_*.md"):
        os.utime(ch_path, (older, older))
    os.utime(conversation, (time.time(), time.time()))
    # Also reset the existing ch02 brief older so the legitimate signal
    # doesn't fire.
    os.utime(book_root / "briefs" / "ch02.md", (older - 1, older - 1))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("fresh brief" in a.title.lower() for a in actions)


# --------------------------------------------------------- summary stale


def test_summary_stale_flagged_high_when_chapter_newer(
    late_stage_book: tuple[Path, str],
) -> None:
    """The continuity signal: chapter file is newer than its
    .summary.md. /autonovel:next must surface it as HIGH —
    summaries are the rolling-context surface every drafter reads."""
    series, book = late_stage_book
    book_root = series / "books" / book
    summary = book_root / "chapters" / "ch_03.summary.md"
    chapter = book_root / "chapters" / "ch_03.md"
    older = time.time() - 1000
    newer = time.time()
    os.utime(summary, (older, older))
    os.utime(chapter, (newer, newer))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    stale = [a for a in actions if "stale" in a.title.lower()
             and "summar" in a.title.lower()]
    assert len(stale) == 1
    assert stale[0].priority == "HIGH"
    assert "3" in stale[0].title


def test_summary_stale_silent_when_summary_newer(
    late_stage_book: tuple[Path, str],
) -> None:
    """No drift → no signal."""
    series, book = late_stage_book
    book_root = series / "books" / book
    # Make every summary newer than its chapter so the signal is silent.
    newer = time.time()
    older = time.time() - 1000
    for n in (1, 2, 3, 4, 5):
        ch = book_root / "chapters" / f"ch_{n:02d}.md"
        sm = book_root / "chapters" / f"ch_{n:02d}.summary.md"
        os.utime(ch, (older, older))
        os.utime(sm, (newer, newer))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("stale" in a.title.lower() and "summar" in a.title.lower()
                    for a in actions)


def test_summary_stale_recommends_summarize_chapter_for_one(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    book_root = series / "books" / book
    # Single stale summary.
    older = time.time() - 1000
    newer = time.time()
    for n in (1, 2, 3, 4, 5):
        ch = book_root / "chapters" / f"ch_{n:02d}.md"
        sm = book_root / "chapters" / f"ch_{n:02d}.summary.md"
        os.utime(ch, (older, older))
        os.utime(sm, (newer, newer))
    chapter = book_root / "chapters" / "ch_03.md"
    os.utime(chapter, (newer + 100, newer + 100))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    stale = next(a for a in actions if "stale" in a.title.lower()
                  and "summar" in a.title.lower())
    assert "summarize-chapter 3" in (stale.command or "")
    assert "--force" in (stale.command or "")


def test_summary_stale_multi_chapter_uses_stale_sweep(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    book_root = series / "books" / book
    older = time.time() - 1000
    newer = time.time()
    # Mark ch 2, 3, 4 as stale.
    for n in (1, 5):
        ch = book_root / "chapters" / f"ch_{n:02d}.md"
        sm = book_root / "chapters" / f"ch_{n:02d}.summary.md"
        os.utime(ch, (older, older))
        os.utime(sm, (newer, newer))
    for n in (2, 3, 4):
        ch = book_root / "chapters" / f"ch_{n:02d}.md"
        sm = book_root / "chapters" / f"ch_{n:02d}.summary.md"
        os.utime(sm, (older, older))
        os.utime(ch, (newer + n, newer + n))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    stale = next(a for a in actions if "stale" in a.title.lower()
                  and "summar" in a.title.lower())
    assert "2,3,4" in stale.title
    # Multi-chapter case routes to the --stale sweep, not per-chapter.
    assert "--stale" in (stale.command or "")


def test_summary_stamped_survives_frontmatter_only_edit(
    late_stage_book: tuple[Path, str],
) -> None:
    """The false alarm this signal used to raise after every revision:
    the summary is written, then the chapter's frontmatter (word_count,
    status) is rewritten, so the chapter's mtime is newer. A stamped
    summary is judged by the chapter body, so it stays fresh."""
    from autonovel import summaries
    series, book = late_stage_book
    book_root = series / "books" / book
    chapter = book_root / "chapters" / "ch_03.md"
    summary = book_root / "chapters" / "ch_03.summary.md"
    summaries.stamp(chapter)
    older = time.time() - 1000
    os.utime(summary, (older, older))
    text = chapter.read_text(encoding="utf-8")
    assert text.startswith("---")
    chapter.write_text(text.replace("---\n", "---\nstatus: revised\n", 1), encoding="utf-8")
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("stale" in a.title.lower() and "3" in a.title for a in actions)


def test_summary_stamped_goes_stale_when_prose_changes(
    late_stage_book: tuple[Path, str],
) -> None:
    """A summary touched after the prose changed (the old `touch`
    workaround) used to read as fresh. The fingerprint catches it."""
    from autonovel import summaries
    series, book = late_stage_book
    book_root = series / "books" / book
    chapter = book_root / "chapters" / "ch_03.md"
    summary = book_root / "chapters" / "ch_03.summary.md"
    summaries.stamp(chapter)
    chapter.write_text(chapter.read_text(encoding="utf-8") + "\nA new paragraph.\n",
                       encoding="utf-8")
    newer = time.time() + 100
    os.utime(summary, (newer, newer))
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    stale = [a for a in actions if "stale" in a.title.lower() and "summar" in a.title.lower()]
    assert len(stale) == 1 and "3" in stale[0].title


# --------------------------------------------------------- panel / review staleness


def test_panel_staleness_actions_when_chapter_newer(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    edit_logs = series / "books" / book / "edit_logs"
    edit_logs.mkdir(exist_ok=True)
    panel = edit_logs / "reader_panel.json"
    panel.write_text(json.dumps({"flagged": []}), encoding="utf-8")
    # Reset panel mtime to a fixed time, then touch a chapter newer.
    older = time.time() - 1000
    os.utime(panel, (older, older))
    _write_chapter(series / "books" / book, 6)
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    panel_actions = [a for a in actions if "reader-panel" in a.title.lower()]
    assert len(panel_actions) == 1
    assert panel_actions[0].priority == "MEDIUM"


def test_panel_staleness_skipped_when_no_report(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("reader-panel" in a.title.lower() for a in actions)


def test_review_staleness_actions(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    edit_logs = series / "books" / book / "edit_logs"
    edit_logs.mkdir(exist_ok=True)
    review = edit_logs / "review.md"
    review.write_text("# Opus review\n\nFlagged.\n", encoding="utf-8")
    older = time.time() - 1000
    os.utime(review, (older, older))
    _write_chapter(series / "books" / book, 7)
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    review_actions = [a for a in actions if "opus review" in a.title.lower()]
    assert len(review_actions) == 1


def test_review_staleness_legacy_name(late_stage_book: tuple[Path, str]) -> None:
    """A series reviewed before 2026-10 carries `opus_review.md`; with no
    `review.md` beside it, staleness is still checked against the legacy
    file."""
    series, book = late_stage_book
    edit_logs = series / "books" / book / "edit_logs"
    (edit_logs / "review.md").unlink(missing_ok=True)
    legacy = edit_logs / "opus_review.md"
    legacy.write_text("# Opus review\n\nFlagged.\n", encoding="utf-8")
    older = time.time() - 1000
    os.utime(legacy, (older, older))
    _write_chapter(series / "books" / book, 7)
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    review_actions = [a for a in actions if "opus review" in a.title.lower()]
    assert len(review_actions) == 1


# --------------------------------------------------------- typeset staleness


def test_typeset_staleness_actions(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    typeset = series / "books" / book / "typeset"
    typeset.mkdir(exist_ok=True)
    pdf = typeset / f"{book}_latest.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    older = time.time() - 1000
    os.utime(pdf, (older, older))
    _write_chapter(series / "books" / book, 8)
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    typeset_actions = [a for a in actions if "rebuild pdf" in a.title.lower()]
    assert len(typeset_actions) == 1
    assert typeset_actions[0].priority == "LOW"


def test_typeset_skipped_when_no_pdf(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("rebuild pdf" in a.title.lower() for a in actions)


# --------------------------------------------------------- title/author + front matter


def test_missing_title_action(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    # Default scaffolded book has no title set.
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    title_actions = [a for a in actions if "display" in a.title.lower()]
    assert len(title_actions) == 1
    assert "title" in title_actions[0].rationale.lower()


def test_title_set_silences_action(late_stage_book: tuple[Path, str]) -> None:
    from autonovel import project as project_mod
    series, book = late_stage_book
    cfg = project_mod.load(_layout(series).project_file)
    entry = cfg.book_by_name(book)
    assert entry is not None
    entry.title = "The Real Title"
    cfg.author = "A. Author"
    project_mod.dump(cfg, _layout(series).project_file)
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("display" in a.title.lower() for a in actions)


def test_missing_front_matter_when_three_chapters_drafted(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    # late_stage_book has 5 chapters drafted, no preface or intro.
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    fm = [a for a in actions if "preface or introduction" in a.title.lower()]
    assert len(fm) == 1


def test_front_matter_action_silenced_when_preface_exists(
    late_stage_book: tuple[Path, str],
) -> None:
    series, book = late_stage_book
    (series / "books" / book / "preface.md").write_text("# Preface\n\nText.\n", encoding="utf-8")
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("preface or introduction" in a.title.lower() for a in actions)


def test_front_matter_skipped_below_three_chapters(series_root: Path) -> None:
    """Newly-scaffolded series with no chapters → no front-matter
    nag."""
    actions = next_actions.enumerate_actions(_layout(series_root))
    assert not any("preface or introduction" in a.title.lower() for a in actions)


# --------------------------------------------------------- glossary suggestion


def test_glossary_suggested_for_period_fiction_with_chapters(
    late_stage_book: tuple[Path, str],
) -> None:
    """Period fiction (project.yaml :: period.start set) with 3+
    chapters but no glossary.md → LOW signal recommending
    /autonovel:glossary. Late-stage fixture has 5 chapters."""
    series, book = late_stage_book
    # Set a period in project.yaml.
    from autonovel import project as project_mod
    cfg = project_mod.load(_layout(series).project_file)
    cfg.period = {"start": "1480", "end": "1550", "region": "Venice"}
    project_mod.dump(cfg, _layout(series).project_file)
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    glossary = [a for a in actions
                 if "glossary" in a.title.lower()]
    assert len(glossary) == 1
    assert glossary[0].priority == "LOW"
    assert "/autonovel:glossary" in (glossary[0].command or "")


def test_glossary_silent_for_contemporary_fiction(
    late_stage_book: tuple[Path, str],
) -> None:
    """No period set → not historical fiction → no glossary nag."""
    series, book = late_stage_book
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("glossary" in a.title.lower() for a in actions)


def test_glossary_silent_when_file_exists(
    late_stage_book: tuple[Path, str],
) -> None:
    """Existing glossary.md (even a stub) silences the signal —
    the user has explicitly opted in."""
    series, book = late_stage_book
    from autonovel import project as project_mod
    cfg = project_mod.load(_layout(series).project_file)
    cfg.period = {"start": "1480", "end": "1550", "region": "Venice"}
    project_mod.dump(cfg, _layout(series).project_file)
    (series / "books" / book / "glossary.md").write_text(
        "# Glossary\n\nstub\n", encoding="utf-8"
    )
    actions = next_actions.enumerate_actions(_layout(series), book=book)
    assert not any("glossary" in a.title.lower() for a in actions)


def test_glossary_silent_under_three_chapters(series_root: Path) -> None:
    """Books with <3 chapters drafted are too early to be worth
    glossary work — the prose may still be churning."""
    from autonovel import project as project_mod
    cfg = project_mod.load(_layout(series_root).project_file)
    cfg.period = {"start": "1480", "end": "1550", "region": "Venice"}
    cfg.books.append(project_mod.BookEntry(name="b", status="drafting"))
    project_mod.dump(cfg, _layout(series_root).project_file)
    actions = next_actions.enumerate_actions(_layout(series_root), book="b")
    assert not any("glossary" in a.title.lower() for a in actions)


# --------------------------------------------------------- git backup states


def test_git_backup_no_repo_state(series_root: Path) -> None:
    actions = next_actions.enumerate_actions(_layout(series_root))
    backup = [a for a in actions if "back up" in a.title.lower()]
    assert len(backup) == 1
    assert backup[0].priority == "MEDIUM"


def test_git_backup_no_remote_state(series_root: Path) -> None:
    subprocess.run(["git", "-C", str(series_root), "init", "-q"], check=True)
    actions = next_actions.enumerate_actions(_layout(series_root))
    backup = [a for a in actions if "remote" in a.title.lower() and "github" in a.title.lower()]
    assert len(backup) == 1


# --------------------------------------------------------- canonical pipeline action


def test_canonical_pipeline_action_present_when_last_action_set(
    series_root: Path,
) -> None:
    layout = _layout(series_root)
    layout.autonovel.mkdir(exist_ok=True)
    last_action_mod.write(
        layout.last_action_file,
        command="autonovel:draft",
        args=["1"],
        book="b",
        next_standard_step="/autonovel:evaluate --chapter 1 --book b",
        next_rationale="evaluate the new chapter",
    )
    canon = next_actions.canonical_pipeline_action(layout)
    assert canon is not None
    assert canon.priority == "INFO"
    assert "/autonovel:evaluate" in (canon.command or "")


def test_canonical_pipeline_action_none_when_no_last_action(
    series_root: Path,
) -> None:
    canon = next_actions.canonical_pipeline_action(_layout(series_root))
    assert canon is None


def test_canonical_pipeline_action_past_end_replaced(
    late_stage_book: tuple[Path, str],
) -> None:
    """Late-stage fixture has 5 chapters. Canonical action says draft
    25 → past end → replaced with 'book may be complete' INFO action
    pointing at evaluate --full."""
    series, book = late_stage_book
    layout = _layout(series)
    last_action_mod.write(
        layout.last_action_file,
        command="autonovel:brief",
        args=["--chapter", "5"],
        book=book,
        next_standard_step=f"/autonovel:draft 25 --book {book}",
        next_rationale="next chapter in the pipeline",
    )
    canon = next_actions.canonical_pipeline_action(layout, book=book)
    assert canon is not None
    assert "appears complete" in canon.title.lower()
    assert "/autonovel:evaluate --full" in (canon.command or "")
    assert canon.priority == "INFO"


def test_canonical_pipeline_action_next_sequential_passes_through(
    late_stage_book: tuple[Path, str],
) -> None:
    """Late-stage fixture has 5 chapters. draft 6 (= existing+1) is
    legitimate — the guard must not fire."""
    series, book = late_stage_book
    layout = _layout(series)
    last_action_mod.write(
        layout.last_action_file,
        command="autonovel:evaluate",
        args=["--chapter", "5"],
        book=book,
        next_standard_step=f"/autonovel:draft 6 --book {book}",
        next_rationale="next chapter",
    )
    canon = next_actions.canonical_pipeline_action(layout, book=book)
    assert canon is not None
    assert "appears complete" not in canon.title.lower()
    assert "/autonovel:draft 6" in (canon.command or "")


def test_canonical_pipeline_action_filtered_by_book(series_root: Path) -> None:
    layout = _layout(series_root)
    layout.autonovel.mkdir(exist_ok=True)
    last_action_mod.write(
        layout.last_action_file,
        command="autonovel:draft",
        args=[],
        book="other-book",
        next_standard_step="/autonovel:evaluate",
        next_rationale="...",
    )
    assert next_actions.canonical_pipeline_action(layout, book="this-book") is None
    assert next_actions.canonical_pipeline_action(layout, book="other-book") is not None


# --------------------------------------------------------- postamble hint


def test_top_hint_prefers_situational_over_general(
    late_stage_book: tuple[Path, str],
) -> None:
    """Fresh brief on ch02 → top_hint should suggest revise, not a
    'did you know'."""
    series, book = late_stage_book
    book_root = series / "books" / book
    older = time.time() - 1000
    os.utime(book_root / "chapters" / "ch_02.md", (older, older))
    os.utime(book_root / "briefs" / "ch02.md", (time.time(), time.time()))
    hint = next_actions.top_hint(_layout(series), just_ran="autonovel:brief", book=book)
    assert hint is not None
    assert "Maybe try" in hint
    assert "revise --chapter 2" in hint


def test_top_hint_skips_just_ran_command(series_root: Path) -> None:
    """If the only situational signal points at the same command we
    just ran, fall back to a general hint instead of suggesting the
    user run the command they just finished."""
    layout = _layout(series_root)
    # Only signal will be the git-backup MEDIUM (no command — it's a
    # multi-step). top_hint must skip it (a.command is None) and
    # produce a general hint.
    hint = next_actions.top_hint(layout, just_ran="autonovel:next")
    assert hint is not None
    assert "Did you know" in hint


def test_top_hint_general_hint_is_deterministic_per_command(
    series_root: Path,
) -> None:
    """Same just_ran value → same general hint each call. Different
    just_ran → potentially different hint (rotation)."""
    layout = _layout(series_root)
    a1 = next_actions.top_hint(layout, just_ran="autonovel:draft")
    a2 = next_actions.top_hint(layout, just_ran="autonovel:draft")
    assert a1 == a2  # determinism
    # Across many command names the pool rotates — at least one pair
    # should differ. Not a hard guarantee but very likely with 6 hints.
    distinct = {
        next_actions.top_hint(layout, just_ran=f"autonovel:cmd{i}")
        for i in range(20)
    }
    assert len(distinct) >= 2


def test_top_hint_skips_situational_targeting_just_ran_command(
    late_stage_book: tuple[Path, str],
) -> None:
    """When we just ran revise, the brief→revise signal would be the
    top action — but we should skip it (the user just did revise)
    and fall back to either the next-priority signal or general."""
    series, book = late_stage_book
    book_root = series / "books" / book
    older = time.time() - 1000
    os.utime(book_root / "chapters" / "ch_02.md", (older, older))
    os.utime(book_root / "briefs" / "ch02.md", (time.time(), time.time()))
    hint = next_actions.top_hint(_layout(series), just_ran="autonovel:revise", book=book)
    assert hint is not None
    # Must not suggest revise again.
    assert "revise --chapter 2" not in hint


# --------------------------------------------------------- render


def test_render_human_empty_returns_clean_message() -> None:
    out = next_actions.render_human([], canonical=None)
    assert "clean" in out.lower()


def test_render_human_groups_by_priority() -> None:
    actions = [
        NextAction(priority="LOW", title="low thing", command=None, rationale="lo"),
        NextAction(priority="HIGH", title="high thing", command="cmd", rationale="hi"),
    ]
    out = next_actions.render_human(actions, canonical=None)
    # HIGH section appears before LOW section in the rendered output.
    assert out.index("HIGH priority") < out.index("LOW priority")
    assert "high thing" in out
    assert "low thing" in out


def test_render_human_includes_canonical_block() -> None:
    canon = NextAction(
        priority="INFO", title="canonical", command="/autonovel:x", rationale="why"
    )
    out = next_actions.render_human([], canonical=canon)
    assert "Canonical pipeline next step" in out
    assert "/autonovel:x" in out


def test_enumerate_sorts_high_before_medium_before_low(series_root: Path) -> None:
    """Sanity: a synthetic series that triggers HIGH (conflicts) +
    MEDIUM (git backup absent) + LOW (missing title) emits them in
    priority order."""
    book = "demo-book"
    book_root = series_root / "books" / book
    book_root.mkdir(parents=True, exist_ok=True)
    # HIGH: pending_canon conflict block.
    (book_root / "pending_canon.md").write_text(
        "# Conflicts — resolve before next promote-canon\n\n## Conflict 1\n- Pending: x\n",
        encoding="utf-8",
    )
    # Wire the book into project.yaml so book_by_name finds it.
    from autonovel import project as project_mod
    cfg = project_mod.load(_layout(series_root).project_file)
    cfg.books.append(project_mod.BookEntry(name=book, status="drafting"))
    project_mod.dump(cfg, _layout(series_root).project_file)

    actions = next_actions.enumerate_actions(_layout(series_root))
    priorities = [a.priority for a in actions]
    # Confirm HIGH appears before any MEDIUM / LOW.
    high_idx = next((i for i, p in enumerate(priorities) if p == "HIGH"), None)
    medium_idx = next((i for i, p in enumerate(priorities) if p == "MEDIUM"), None)
    assert high_idx is not None
    if medium_idx is not None:
        assert high_idx < medium_idx


# --------------------------------------------------------- CLI round-trip


def test_cli_next_actions_human_format(late_stage_book: tuple[Path, str]) -> None:
    series, _ = late_stage_book
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_next-actions", "--format", "human"],
        cwd=series, capture_output=True, text=True, check=True,
    )
    # Late-stage fixture has no title set + no front matter + no git
    # repo, so we always have at least one MEDIUM (backup) and at
    # least one LOW (title) action.
    assert "priority" in proc.stdout.lower()


def test_cli_next_actions_json_format(late_stage_book: tuple[Path, str]) -> None:
    series, _ = late_stage_book
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_next-actions", "--format", "json"],
        cwd=series, capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert "actions" in payload
    assert isinstance(payload["actions"], list)
    assert "canonical" in payload


def test_cli_next_actions_book_filter(late_stage_book: tuple[Path, str]) -> None:
    series, book = late_stage_book
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_next-actions",
         "--book", book, "--format", "json"],
        cwd=series, capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    # Every per-book action is for `book`; series-wide ones have book=None.
    for a in payload["actions"]:
        assert a["book"] in (book, None)
