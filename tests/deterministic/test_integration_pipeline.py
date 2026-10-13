"""Multi-stage pipeline integration tests (Tier-1, no LLM).

Background: each command has unit tests in isolation, but real bugs
hit the *seams* between commands — draft writes a chapter, eval
writes a score, next-step decides; promote-canon empties the
pending file, next-step decides; etc. FUTURE-TODOS #5.2 prescribes
a deterministic test suite that walks these seams by simulating
exactly the on-disk state each command would have produced (no
real LLM call) and asserting the next-step recommendation between
each step.

These tests intentionally bypass `lifecycle.begin/end` postambles
so they exercise the inference path the postamble itself uses
(`_next_step_for`) without recursion. The promote-canon step calls
the real helper at `autonovel.promote_canon.promote`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from autonovel import last_action as last_action_mod
from autonovel import project as project_mod
from autonovel import promote_canon as promote_canon_mod
from autonovel.housekeeping import lifecycle, next_actions, scaffold
from autonovel.paths import SeriesLayout


# -------------------------------------------------- helpers


def _bootstrap(tmp_path: Path) -> tuple[SeriesLayout, str]:
    """A series + one book + a populated foundation. Returns the
    layout + book name. Foundation is fully filled (so the
    foundation-gap path is silent) and chapters/ is empty (drafting
    has not started)."""
    res = scaffold.new_series(tmp_path / "series", series_name="series")
    scaffold.new_book(res.series, book_name="b", pov="Ana")
    layout = SeriesLayout(root=res.series.root)
    long = "Real content. " * 30
    (layout.shared / "world.md").write_text(f"# World\n\n{long}\n", encoding="utf-8")
    (layout.shared / "characters.md").write_text(f"# Characters\n\n{long}\n", encoding="utf-8")
    (layout.shared / "canon.md").write_text(f"# Canon\n\n{long}\n", encoding="utf-8")
    book_root = layout.books / "b"
    (book_root / "voice.md").write_text(f"# Voice\n\n{long}\n", encoding="utf-8")
    (book_root / "outline.md").write_text(f"# Outline\n\n{long}\n", encoding="utf-8")
    # Book-scoped canon half (seeded from the outline by `gen-canon --book`).
    (book_root / "canon.md").write_text(f"# Book canon\n\n{long}\n", encoding="utf-8")
    return layout, "b"


def _draft(book_root: Path, n: int) -> None:
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / f"ch_{n:02d}.md").write_text(
        f"---\nbook: b\nchapter: {n}\npov: Ana\nstory_time: 2020-01-{n:02d}\n"
        f"events: []\nstatus: drafted\nword_count: 3000\n---\n\n"
        + (f"Prose for chapter {n}. " * 100),
        encoding="utf-8",
    )


def _evaluate_timestamped(book_root: Path, n: int, score: float, *, when: str) -> None:
    """Mirrors what evaluate.md writes: `<ts>_chNN.json`."""
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(exist_ok=True)
    (eval_dir / f"{when}_ch{n:02d}.json").write_text(
        json.dumps({"overall_score": score}), encoding="utf-8",
    )


def _evaluate_plain(book_root: Path, n: int, score: float) -> None:
    """Mirrors what draft-pass.md writes: `chNN_eval.json`."""
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(exist_ok=True)
    (eval_dir / f"ch{n:02d}_eval.json").write_text(
        json.dumps({"overall_score": score}), encoding="utf-8",
    )


# -------------------------------------------------- foundation-to-drafting seam


def test_foundation_complete_then_first_draft_lands_on_evaluate(tmp_path: Path) -> None:
    """Seam: foundation done → user runs /autonovel:draft 1 (writes
    ch_01.md) → next-step says evaluate chapter 1. Evaluate writes
    a score → next-step decides advance vs revise.

    Note: with foundation populated but no chapters and no
    foundation eval, next_step recommends `evaluate --phase
    foundation` (not draft 1) — the user is expected to score the
    foundation first. Once they draft, phase rolls forward to
    drafting and the evaluate-chapter / advance / revise branch
    takes over."""
    layout, book = _bootstrap(tmp_path)
    book_root = layout.books / book

    # Simulate the user running /autonovel:draft 1 (skipping the
    # foundation evaluate — production lets you do this; the eval
    # gate is advisory).
    _draft(book_root, 1)
    ns = lifecycle._next_step_for(layout, book)
    # Without a score, next_step routes to evaluate (the
    # 2026-04-25 fix: never advance past a chapter we haven't
    # scored).
    assert "evaluate" in ns.command and "1" in ns.command

    # Eval lands above threshold (timestamped form — exercises the
    # 2026-04-28 lifecycle fix) → advance.
    _evaluate_timestamped(book_root, 1, 7.5, when="20260415_120000")
    ns = lifecycle._next_step_for(layout, book)
    assert "draft 2" in ns.command


def test_low_score_routes_to_revise_then_re_eval_then_advance(
    tmp_path: Path,
) -> None:
    """Seam: low eval → revise → re-eval (higher score) → advance."""
    layout, book = _bootstrap(tmp_path)
    book_root = layout.books / book
    _draft(book_root, 1)

    _evaluate_timestamped(book_root, 1, 5.5, when="20260415_120000")
    ns = lifecycle._next_step_for(layout, book)
    assert "revise" in ns.command and "1" in ns.command

    # User runs /autonovel:revise 1 → ch_01.md is rewritten in place
    # (we just touch it). Then a fresh eval lands above threshold.
    time.sleep(0.01)
    _evaluate_timestamped(book_root, 1, 7.4, when="20260416_120000")
    ns = lifecycle._next_step_for(layout, book)
    assert "draft 2" in ns.command


# -------------------------------------------------- pending-canon seam


def test_draft_to_promote_canon_to_advance(tmp_path: Path) -> None:
    """Seam: chapter 1 drafted + scored → user-research adds a
    pending canon entry → next-step is promote-canon (gate fires).
    Run promote_canon → pending file is rewritten with no entries
    → next-step advances to draft 2."""
    layout, book = _bootstrap(tmp_path)
    book_root = layout.books / book
    _draft(book_root, 1)
    _evaluate_timestamped(book_root, 1, 7.5, when="20260415_120000")

    # Pending canon picks up a single survivor entry.
    (book_root / "pending_canon.md").write_text(
        "# Pending\n\n- [Tommaso birthday] 1487-05-12 (from b ch_01)\n",
        encoding="utf-8",
    )
    ns = lifecycle._next_step_for(layout, book)
    assert "promote-canon" in ns.command, ns.command

    # User runs /autonovel:promote-canon → helper rewrites pending
    # file (survivor moved into canon.md, pending becomes a no-op
    # marker).
    promote_canon_mod.promote(layout, book=book)

    # Pending gate must no longer fire.
    ns = lifecycle._next_step_for(layout, book)
    assert "promote-canon" not in ns.command
    assert "draft 2" in ns.command


# -------------------------------------------------- next_actions across seams


def test_next_actions_priority_shifts_through_pipeline(tmp_path: Path) -> None:
    """As state evolves, the situational action list shifts. Walk
    three seams and assert which actions are present at each."""
    layout, book = _bootstrap(tmp_path)
    book_root = layout.books / book

    # Stage 1: foundation done, no chapters. No HIGH/MEDIUM/LOW
    # situational actions other than git-backup (no repo) and
    # missing title.
    actions = next_actions.enumerate_actions(layout, book=book)
    titles = [a.title.lower() for a in actions]
    assert any("back up" in t or "remote" in t for t in titles)
    assert any("display" in t for t in titles)
    assert not any("regressed" in t for t in titles)
    assert not any("conflict" in t for t in titles)

    # Stage 2: 4 chapters drafted with paired summaries; no review;
    # one chapter with a regression history. Expect HIGH regression.
    for n in range(1, 5):
        _draft(book_root, n)
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(exist_ok=True)
    (eval_dir / "20260101_120000_ch02_eval.json").write_text(
        json.dumps({"overall_score": 7.5}), encoding="utf-8")
    (eval_dir / "20260102_120000_ch02_eval.json").write_text(
        json.dumps({"overall_score": 6.5}), encoding="utf-8")
    actions = next_actions.enumerate_actions(layout, book=book)
    high = [a for a in actions if a.priority == "HIGH"]
    assert any("regressed" in a.title.lower() for a in high)

    # Stage 3: drop a typeset PDF older than the chapters. LOW
    # action: "Rebuild PDF + ePub".
    typeset = book_root / "typeset"
    typeset.mkdir(exist_ok=True)
    pdf = typeset / "b_latest.pdf"
    pdf.write_bytes(b"%PDF\n%%EOF\n")
    older = time.time() - 1000
    os.utime(pdf, (older, older))
    actions = next_actions.enumerate_actions(layout, book=book)
    low = [a for a in actions if a.priority == "LOW"]
    assert any("rebuild pdf" in a.title.lower() for a in low)


# -------------------------------------------------- last_action.json + canonical surface


def test_last_action_canonical_surfaces_at_bottom(tmp_path: Path) -> None:
    """After a real lifecycle.end writes last-action.json with a
    next_standard_step, /autonovel:next's canonical-pipeline section
    must surface that exact step at the bottom of the action list."""
    layout, book = _bootstrap(tmp_path)
    layout.autonovel.mkdir(exist_ok=True)
    last_action_mod.write(
        layout.last_action_file,
        command="autonovel:draft",
        args=["1", "--book", book],
        wrote=[f"books/{book}/chapters/ch_01.md"],
        book=book,
        next_standard_step="/autonovel:evaluate --chapter 1 --book b",
        next_rationale="evaluate the new chapter before advancing",
    )
    canon = next_actions.canonical_pipeline_action(layout, book=book)
    assert canon is not None
    assert canon.command == "/autonovel:evaluate --chapter 1 --book b"
    out = next_actions.render_human([], canonical=canon)
    assert "Canonical pipeline next step" in out
    assert "/autonovel:evaluate --chapter 1 --book b" in out


# -------------------------------------------------- foundation chain


def test_foundation_chain_walks_world_to_outline(tmp_path: Path) -> None:
    """Empty foundation → next-step says gen-world. Populate world →
    says gen-characters. Etc. This exercises the same chain
    test_lifecycle.py covers, but via _next_step_for directly so it
    runs without a postamble write."""
    res = scaffold.new_series(tmp_path / "s", series_name="s")
    scaffold.new_book(res.series, book_name="b", pov="Ana")
    layout = SeriesLayout(root=res.series.root)
    book_root = layout.books / "b"
    long = "Real content. " * 30

    # gen-world
    ns = lifecycle._next_step_for(layout, "b")
    assert "gen-world" in ns.command

    # gen-characters
    (layout.shared / "world.md").write_text(f"# World\n\n{long}\n", encoding="utf-8")
    ns = lifecycle._next_step_for(layout, "b")
    assert "gen-characters" in ns.command

    # voice-discovery
    (layout.shared / "characters.md").write_text(
        f"# Characters\n\n{long}\n", encoding="utf-8")
    ns = lifecycle._next_step_for(layout, "b")
    assert "voice-discovery" in ns.command

    # gen-canon
    (book_root / "voice.md").write_text(f"# Voice\n\n{long}\n", encoding="utf-8")
    ns = lifecycle._next_step_for(layout, "b")
    assert "gen-canon" in ns.command

    # gen-outline
    (layout.shared / "canon.md").write_text(f"# Canon\n\n{long}\n", encoding="utf-8")
    ns = lifecycle._next_step_for(layout, "b")
    assert "gen-outline" in ns.command

    # Foundation closed. Without a foundation eval score, next_step's
    # foundation branch advises evaluating foundation before drafting.
    # That's the canonical advisory path; the chain-walk test confirms
    # the recommendation is no longer a foundation *gap* (one of the
    # gen-* commands).
    (book_root / "outline.md").write_text(f"# Outline\n\n{long}\n", encoding="utf-8")
    # The book-scoped canon half is seeded FROM the outline, so it is the
    # one remaining gap once the outline exists.
    ns = lifecycle._next_step_for(layout, "b")
    assert "gen-canon --book b" in ns.command
    (book_root / "canon.md").write_text(f"# Book canon\n\n{long}\n", encoding="utf-8")
    ns = lifecycle._next_step_for(layout, "b")
    for forbidden in ("gen-world", "gen-characters", "voice-discovery",
                       "gen-canon", "gen-outline"):
        assert forbidden not in ns.command


# -------------------------------------------------- naming-convention round-trip


def test_eval_score_indexer_handles_three_naming_conventions(
    tmp_path: Path,
) -> None:
    """The bug FUTURE-TODOS #5.1 surfaced (and #5.2 prevents from
    regressing): `_last_eval_score` must find the latest eval per
    chapter regardless of which command wrote it."""
    layout, book = _bootstrap(tmp_path)
    book_root = layout.books / book
    _draft(book_root, 1)
    _draft(book_root, 2)
    _draft(book_root, 3)

    _evaluate_plain(book_root, 1, 7.5)               # draft-pass shape
    _evaluate_timestamped(book_root, 2, 7.0, when="20260415_120000")  # evaluate.md shape
    eval_dir = book_root / "eval_logs"
    (eval_dir / "20260415_130000_ch03_eval.json").write_text(  # third historical shape
        json.dumps({"overall_score": 6.5}), encoding="utf-8",
    )

    assert lifecycle._last_eval_score(book_root, 1) == 7.5
    assert lifecycle._last_eval_score(book_root, 2) == 7.0
    assert lifecycle._last_eval_score(book_root, 3) == 6.5
