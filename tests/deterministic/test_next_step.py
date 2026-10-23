"""Next-step decision table (REWRITE-PLAN.md §21.5)."""

from __future__ import annotations

from autonovel.housekeeping.next_step import PipelineState, next_step


def test_seed_routes_to_gen_world() -> None:
    s = PipelineState(book="a", phase="seed")
    ns = next_step(s)
    assert ns.command == "/autonovel:gen-world"


def test_foundation_below_threshold_re_evaluates() -> None:
    s = PipelineState(book="a", phase="foundation", foundation_score=5.0)
    ns = next_step(s)
    assert "evaluate" in ns.command and "foundation" in ns.command


def test_foundation_above_threshold_starts_drafting() -> None:
    s = PipelineState(book="a", phase="foundation", foundation_score=7.6)
    ns = next_step(s)
    assert ns.command == "/autonovel:draft 1 --book a"


def test_drafting_good_chapter_advances() -> None:
    # Default chapter_threshold went 6.0 → 7.0 on 2026-04-25; previous
    # test used 6.8 which now sits below threshold. Bump to 7.5 so
    # this test stays a clean "above threshold → advance" assertion.
    s = PipelineState(
        book="a",
        phase="drafting",
        last_chapter_number=3,
        last_chapter_score=7.5,
        chapters_total=20,
    )
    assert next_step(s).command == "/autonovel:draft 4 --book a"


def test_drafting_bad_chapter_revises() -> None:
    s = PipelineState(
        book="a",
        phase="drafting",
        last_chapter_number=3,
        last_chapter_score=5.0,
    )
    assert next_step(s).command == "/autonovel:revise 3 --book a"


def test_last_chapter_drafted_asks_for_the_editors_read() -> None:
    s = PipelineState(
        book="a",
        phase="drafting",
        last_chapter_number=20,
        last_chapter_score=7.0,
        chapters_total=20,
    )
    assert next_step(s).command == "/autonovel:developmental-edit --book a"


def test_last_chapter_drafted_with_letter_acts_on_it() -> None:
    s = PipelineState(
        book="a",
        phase="drafting",
        last_chapter_number=20,
        last_chapter_score=7.0,
        chapters_total=20,
        editor_letter_done=True,
    )
    assert next_step(s).command == "/autonovel:revision-pass --chapters all --book a"


def test_last_chapter_below_threshold_still_revises() -> None:
    s = PipelineState(
        book="a",
        phase="drafting",
        last_chapter_number=20,
        last_chapter_score=6.0,
        chapters_total=20,
    )
    assert next_step(s).command == "/autonovel:revise 20 --book a"


def test_revision_plateau_moves_to_review() -> None:
    s = PipelineState(
        book="a",
        phase="revision",
        adversarial_done=True,
        reader_panel_done=True,
        revision_cycles_run=3,
        score_deltas=[0.2, 0.1],
    )
    assert next_step(s).command == "/autonovel:review --book a"


def test_revision_still_improving_keeps_iterating() -> None:
    s = PipelineState(
        book="a",
        phase="revision",
        adversarial_done=True,
        reader_panel_done=True,
        revision_cycles_run=3,
        score_deltas=[0.6, 0.5],
    )
    assert next_step(s).command == "/autonovel:brief --auto --book a"


def test_max_revision_cycles_forces_review() -> None:
    s = PipelineState(
        book="a",
        phase="revision",
        adversarial_done=True,
        reader_panel_done=True,
        revision_cycles_run=6,
        score_deltas=[1.0, 0.9],  # still improving, but hit cap
    )
    assert next_step(s).command == "/autonovel:review --book a"


def test_export_phase_goes_to_package() -> None:
    s = PipelineState(book="a", phase="export")
    assert next_step(s).command == "/autonovel:package --book a"


def test_done_with_pending_canon_prompts_promotion() -> None:
    s = PipelineState(book="a", phase="done", has_pending_canon=True)
    assert next_step(s).command.startswith("autonovel promote-canon")
