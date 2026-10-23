"""Decision table: given pipeline state, return the standard next command.

Implements REWRITE-PLAN.md §21.5. Pure function — no I/O. Testable in Tier 1.
"""

from __future__ import annotations

from dataclasses import dataclass


# Defaults from REWRITE-PLAN.md §6 `defaults` block.
DEFAULT_FOUNDATION_THRESHOLD = 7.5
DEFAULT_CHAPTER_THRESHOLD = 7.0


@dataclass
class PipelineState:
    """Snapshot of what's true about a book right now."""

    book: str
    phase: str  # seed | foundation | drafting | revision | review | export | done
    foundation_score: float = 0.0
    lore_score: float = 0.0
    chapters_drafted: int = 0
    chapters_total: int = 0  # chapters the outline declares
    editor_letter_done: bool = False  # edit_logs/editor_letter.md exists
    # The whole-book reviewers' state (`whole_book.gather`). When set, the
    # step after the last chapter walks their order; None keeps the
    # letter-only decision (callers that don't read the book's files).
    whole_book: object | None = None
    last_chapter_score: float | None = None
    last_chapter_number: int | None = None
    # The last chapter's lowest-scoring dimension, `(name, score)`. A mean
    # that passes can hide one dimension under the floor; that chapter
    # goes back to revise too.
    last_chapter_low: tuple[str, float] | None = None
    revision_cycles_run: int = 0
    score_deltas: list[float] | None = None  # deltas between consecutive revision cycles
    adversarial_done: bool = False
    reader_panel_done: bool = False
    review_done: bool = False
    has_pending_canon: bool = False

    foundation_threshold: float = DEFAULT_FOUNDATION_THRESHOLD
    chapter_threshold: float = DEFAULT_CHAPTER_THRESHOLD
    dimension_floor: float | None = None  # None: same as chapter_threshold
    plateau_delta: float = 0.3
    min_revision_cycles: int = 2
    max_revision_cycles: int = 6


@dataclass
class NextStep:
    command: str
    rationale: str


def next_step(state: PipelineState) -> NextStep:
    b = state.book
    s = state

    if s.phase == "seed":
        return NextStep(
            command=f"/autonovel:gen-world",
            rationale="foundation starts with the world",
        )

    if s.phase == "foundation":
        if s.foundation_score >= s.foundation_threshold:
            return NextStep(
                command=f"/autonovel:draft 1 --book {b}",
                rationale="foundation meets threshold; begin drafting",
            )
        return NextStep(
            command=f"/autonovel:evaluate --phase foundation --book {b}",
            rationale="foundation below threshold; re-evaluate after more work",
        )

    if s.phase == "drafting":
        # Prefer an explicit last_chapter_number; otherwise fall back to
        # chapters_drafted (the count of chapter files on disk). Either
        # tells us which chapter was most recently touched.
        n = s.last_chapter_number if s.last_chapter_number is not None else (
            s.chapters_drafted if s.chapters_drafted else None
        )
        if n is None:
            return NextStep(
                command=f"/autonovel:draft 1 --book {b}",
                rationale="no chapter drafted yet",
            )
        # Chapter exists but hasn't been evaluated → evaluate before
        # advancing. Without a score we can't decide between "draft
        # next" and "revise this one", so the eval is the next move.
        if s.last_chapter_score is None:
            return NextStep(
                command=f"/autonovel:evaluate --chapter {n} --book {b}",
                rationale=f"chapter {n} drafted; evaluate before advancing",
            )
        floor = s.dimension_floor if s.dimension_floor is not None else s.chapter_threshold
        low = s.last_chapter_low
        if (s.last_chapter_score >= s.chapter_threshold
                and low is not None and low[1] < floor):
            return NextStep(
                command=f"/autonovel:revise {n} --book {b}",
                rationale=(f"chapter {n} scores {s.last_chapter_score:.1f}, but its "
                           f"lowest dimension, {low[0]} {low[1]:.1f}, is under the "
                           f"{floor:.1f} floor; revise for it"),
            )
        if s.last_chapter_score >= s.chapter_threshold:
            if s.chapters_total and n >= s.chapters_total:
                # The book is drafted. Its whole-book steps have one
                # order (whole_book.py): the editor's letter, the
                # structure review, the revision, the re-read, then the
                # panel and the review.
                if s.whole_book is not None:
                    from .whole_book import next_whole_book_step
                    step = next_whole_book_step(b, s.whole_book)  # type: ignore[arg-type]
                    return NextStep(command=step.command, rationale=step.rationale)
                if not s.editor_letter_done:
                    return NextStep(
                        command=f"/autonovel:developmental-edit --book {b}",
                        rationale=(f"all {s.chapters_total} outlined chapters drafted; "
                                   f"get the editor's whole-book read before revising"),
                    )
                return NextStep(
                    command=f"/autonovel:revision-pass --chapters all --book {b}",
                    rationale=("the editor's letter is written; act on it "
                               "(edit_logs/editor_letter.md names the chapters)"),
                )
            return NextStep(
                command=f"/autonovel:draft {n + 1} --book {b}",
                rationale=("previous chapter met threshold; advance"
                           + (f" (its lowest: {low[0]} {low[1]:.1f})" if low else "")),
            )
        return NextStep(
            command=f"/autonovel:revise {n} --book {b}",
            rationale="previous chapter below threshold; revise",
        )

    if s.phase == "revision":
        if not s.adversarial_done:
            return NextStep(
                command=f"/autonovel:adversarial-edit all --book {b}",
                rationale="start revision with adversarial pass",
            )
        if not s.reader_panel_done:
            return NextStep(
                command=f"/autonovel:reader-panel --book {b}",
                rationale="adversarial pass done; gather reader feedback",
            )
        if s.revision_cycles_run < s.min_revision_cycles:
            return NextStep(
                command=f"/autonovel:brief --auto --book {b}",
                rationale="below min revision cycles; keep iterating",
            )
        if s.revision_cycles_run >= s.max_revision_cycles:
            return NextStep(
                command=f"/autonovel:review --book {b}",
                rationale="hit max revision cycles; move to Opus review",
            )
        if _plateau(s):
            return NextStep(
                command=f"/autonovel:review --book {b}",
                rationale="score plateau reached; move to Opus review",
            )
        return NextStep(
            command=f"/autonovel:brief --auto --book {b}",
            rationale="revision still improving; keep going",
        )

    if s.phase == "review":
        if not s.review_done:
            return NextStep(
                command=f"/autonovel:review --book {b}",
                rationale="run the Opus review pass",
            )
        return NextStep(
            command=f"/autonovel:typeset --book {b}",
            rationale="review complete; typeset the manuscript",
        )

    if s.phase == "export":
        return NextStep(
            command=f"/autonovel:package --book {b}",
            rationale="bundle the finished artifacts",
        )

    if s.phase == "done":
        if s.has_pending_canon:
            return NextStep(
                command=f"autonovel promote-canon --book {b}",
                rationale="book done; promote any pending canon entries",
            )
        return NextStep(
            command=f"autonovel status",
            rationale="book done; no next action for this book",
        )

    return NextStep(
        command=f"autonovel status",
        rationale=f"unknown phase `{s.phase}`; check series status",
    )


def _plateau(s: PipelineState) -> bool:
    if not s.score_deltas or len(s.score_deltas) < 2:
        return False
    last_two = s.score_deltas[-2:]
    return all(abs(d) < s.plateau_delta for d in last_two)
