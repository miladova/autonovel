"""Series-arc score — cross-book continuity scoring.

When `project.yaml` declares ≥2 books, the dashboard needs a
view that crosses book boundaries:

- **Story-time monotonicity.** A series whose chapters have ISO
  `story_time` values should generally read forward in time.
  Backwards jumps are legitimate (flashback chapters, prequels)
  but the *count* of backwards jumps and their *magnitude* are
  signal — five backwards jumps in three books is a structure
  problem.

- **Recurring cast.** How many named characters appear in ≥2
  books? Surface the cross-book cast (high-leverage characters
  whose continuity matters most) so revise can prioritise them.

- **Thread payoff.** Chapters whose summary `Threads opened:`
  field names a thread that never matches a later chapter's
  `Threads closed:` field. Per-book threads are a craft
  question; *cross-book* unresolved threads are usually a
  spent-arc-budget problem.

- **Per-book completion.** Fraction of each book's chapters
  that have a summary file, an eval log, and a score above
  the chapter threshold. Multi-book series often have one
  book stalling — surfacing this guides where revise/brief
  effort should land next.

Pure mechanical. No LLM. The LLM-side scoring of arc *quality*
(does the series payoff feel earned?) is a future LLM-judge
upgrade in the same shape as `/autonovel:review`. This module
provides the structural scoreboard; humans + LLMs read it.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from .chapter_summary import (
    ChapterRow,
    _parse_summary,
    summarize_chapters,
)
from ..paths import iter_chapter_files


@dataclass
class BookSummary:
    name: str
    chapter_count: int
    summary_coverage: float  # 0.0-1.0 — fraction of chapters with a summary
    eval_coverage: float     # 0.0-1.0 — fraction with at least one eval
    above_threshold: int     # chapters whose latest score >= threshold
    earliest_story_time: str | None
    latest_story_time: str | None
    threads_opened: list[tuple[int, str]] = field(default_factory=list)
    threads_closed: list[tuple[int, str]] = field(default_factory=list)
    cast_appearances: dict[str, int] = field(default_factory=dict)


@dataclass
class StoryTimeJump:
    """One backwards jump in chapter `story_time` order."""
    book: str
    chapter: int
    prev_story_time: str
    this_story_time: str


@dataclass
class UnresolvedThread:
    book: str
    chapter: int
    thread: str


@dataclass
class SeriesArcReport:
    book_count: int
    threshold: float
    books: list[BookSummary]
    cross_book_cast: dict[str, list[str]]  # character → list of book names
    backwards_story_time_jumps: list[StoryTimeJump]
    unresolved_threads: list[UnresolvedThread]
    arc_score: float                       # 0.0-10.0 composite
    # Pairs of books whose project.yaml `story_time_range`s overlap
    # (e.g. a rewrite of the same story). A story-time reset at the
    # boundary between two such books is expected, not a structure
    # problem, so it is not counted as a backwards jump.
    overlapping_books: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "book_count": self.book_count,
            "threshold": self.threshold,
            "arc_score": self.arc_score,
            "books": [
                {
                    "name": b.name,
                    "chapter_count": b.chapter_count,
                    "summary_coverage": b.summary_coverage,
                    "eval_coverage": b.eval_coverage,
                    "above_threshold": b.above_threshold,
                    "earliest_story_time": b.earliest_story_time,
                    "latest_story_time": b.latest_story_time,
                    "threads_opened_count": len(b.threads_opened),
                    "threads_closed_count": len(b.threads_closed),
                    "cast_appearances": dict(b.cast_appearances),
                }
                for b in self.books
            ],
            "cross_book_cast": {k: list(v)
                                  for k, v in self.cross_book_cast.items()},
            "overlapping_books": list(self.overlapping_books),
            "backwards_story_time_jumps": [
                {"book": j.book, "chapter": j.chapter,
                 "prev": j.prev_story_time, "this": j.this_story_time}
                for j in self.backwards_story_time_jumps
            ],
            "unresolved_threads": [
                {"book": t.book, "chapter": t.chapter, "thread": t.thread}
                for t in self.unresolved_threads
            ],
        }


# ---------------------------------------------------------- public entry


def build_report(series_root: Path, *, threshold: float = 7.0) -> SeriesArcReport:
    """Inspect every book under `series_root/books/` and return a
    SeriesArcReport. Pure I/O — no LLM, no subprocess."""
    from .. import project as project_mod
    cfg = project_mod.load(series_root / "project.yaml")
    books_dir = series_root / "books"
    book_summaries: list[BookSummary] = []
    for entry in cfg.books:
        book_root = books_dir / entry.name
        if not book_root.is_dir():
            continue
        book_summaries.append(_summarise_book(book_root, threshold=threshold))

    cross_book_cast = _cross_book_cast(book_summaries)
    overlapping = _overlapping_books(cfg)
    backwards = _backwards_story_time_jumps(
        book_summaries, books_dir, overlapping=overlapping)
    unresolved = _unresolved_threads(book_summaries)
    arc_score = _composite_score(book_summaries, threshold,
                                  backwards, unresolved)
    return SeriesArcReport(
        book_count=len(book_summaries),
        threshold=threshold,
        books=book_summaries,
        cross_book_cast=cross_book_cast,
        backwards_story_time_jumps=backwards,
        unresolved_threads=unresolved,
        arc_score=arc_score,
        overlapping_books=sorted(f"{a} ~ {b}" for a, b in overlapping),
    )


# ---------------------------------------------------------- per-book


def _summarise_book(book_root: Path, *, threshold: float) -> BookSummary:
    rows = summarize_chapters(book_root)
    chapter_count = len(rows)
    chapters_dir = book_root / "chapters"
    have_summary = 0
    have_eval = 0
    above_threshold = 0
    threads_opened: list[tuple[int, str]] = []
    threads_closed: list[tuple[int, str]] = []
    cast_appearances: dict[str, int] = {}
    earliest: str | None = None
    latest: str | None = None

    for row in rows:
        # Summary coverage: does the .summary.md exist on disk?
        summary_path = chapters_dir / f"ch_{row.chapter:02d}.summary.md"
        if summary_path.is_file():
            have_summary += 1
            sm = _parse_summary(summary_path.read_text(encoding="utf-8"))
            opened = sm.get("threads_opened") if hasattr(sm, "get") else None
            # _parse_summary's flat dict only carries plot/cast/story_time/
            # location; threads aren't surfaced. Re-parse the file for
            # them.
            for thread in _extract_threads(summary_path,
                                              key="threads opened"):
                threads_opened.append((row.chapter, thread))
            for thread in _extract_threads(summary_path,
                                              key="threads closed"):
                threads_closed.append((row.chapter, thread))
        if row.score is not None:
            have_eval += 1
            if row.score >= threshold:
                above_threshold += 1
        if row.cast:
            for name in row.cast:
                cast_appearances[name] = cast_appearances.get(name, 0) + 1
        st = row.story_time
        if st:
            if earliest is None or st < earliest:
                earliest = st
            if latest is None or st > latest:
                latest = st

    return BookSummary(
        name=book_root.name,
        chapter_count=chapter_count,
        summary_coverage=(have_summary / chapter_count) if chapter_count else 0.0,
        eval_coverage=(have_eval / chapter_count) if chapter_count else 0.0,
        above_threshold=above_threshold,
        earliest_story_time=earliest,
        latest_story_time=latest,
        threads_opened=threads_opened,
        threads_closed=threads_closed,
        cast_appearances=cast_appearances,
    )


_THREAD_BLOCK_RE = re.compile(
    r"^\s*\*\*Threads (opened|closed):\*\*\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_threads(path: Path, *, key: str) -> list[str]:
    """Pull thread strings out of a summary file. The convention is
    one short noun-phrase per thread, separated by `;` or `,` on a
    single line. Returns trimmed strings."""
    text = path.read_text(encoding="utf-8")
    threads: list[str] = []
    target = key.lower().replace("threads ", "")  # "opened" | "closed"
    for m in _THREAD_BLOCK_RE.finditer(text):
        if m.group(1).lower() != target:
            continue
        chunk = m.group(2)
        if not chunk:
            continue
        # Split on `;` if present, else `,`. The summary template
        # puts threads as a single sentence; we split conservatively
        # so light formatting differences don't shred a thread name.
        sep = ";" if ";" in chunk else (
            "," if "," in chunk else None
        )
        if sep is None:
            cleaned = chunk.strip().rstrip(".").strip()
            if cleaned and not _is_zero_threads(cleaned):
                threads.append(cleaned)
        else:
            for part in chunk.split(sep):
                cleaned = part.strip().rstrip(".").strip()
                if cleaned and not _is_zero_threads(cleaned):
                    threads.append(cleaned)
    return threads


def _is_zero_threads(s: str) -> bool:
    """Filter out 'none', 'zero', '—' style placeholders."""
    norm = s.lower().strip(".—-* ")
    return norm in {"none", "zero", "n/a", "na", ""}


# ---------------------------------------------------------- cross-book


def _cross_book_cast(books: list[BookSummary]) -> dict[str, list[str]]:
    """Return cast members appearing in ≥2 books, mapped to the
    list of books they appear in."""
    by_char: dict[str, list[str]] = {}
    for b in books:
        for name in b.cast_appearances:
            by_char.setdefault(name, []).append(b.name)
    return {n: bs for n, bs in by_char.items() if len(bs) >= 2}


def _overlapping_books(cfg) -> list[tuple[str, str]]:
    """Pairs (earlier, later) of books in declaration order whose
    `story_time_range`s intersect. Books without a range never overlap."""
    out: list[tuple[str, str]] = []
    ranged = [(b.name, b.story_time_range) for b in cfg.books
              if b.story_time_range and len(b.story_time_range) == 2]
    for i, (a_name, a_rng) in enumerate(ranged):
        for b_name, b_rng in ranged[i + 1:]:
            if a_rng[0] <= b_rng[1] and b_rng[0] <= a_rng[1]:
                out.append((a_name, b_name))
    return out


def _backwards_story_time_jumps(
    books: list[BookSummary], books_dir: Path,
    *, overlapping: list[tuple[str, str]] | None = None,
) -> list[StoryTimeJump]:
    """Walk every chapter in series order (book order; chapter order
    within each book) and find any ISO `story_time` value that's
    less than the previous chapter's. Lex compare works for ISO
    dates.

    The first chapter of a book whose `story_time_range` overlaps the
    previous book's is exempt: two books covering the same years (a
    rewrite, a parallel POV) legitimately reset the clock at the
    boundary."""
    overlap_set = {frozenset(pair) for pair in (overlapping or [])}
    out: list[StoryTimeJump] = []
    last_st: str | None = None
    prev_book: str | None = None
    for b in books:
        book_root = books_dir / b.name
        rows = summarize_chapters(book_root)
        boundary_exempt = (
            prev_book is not None
            and frozenset((prev_book, b.name)) in overlap_set
        )
        for idx, row in enumerate(sorted(rows, key=lambda r: r.chapter)):
            if idx == 0 and boundary_exempt:
                st0 = row.story_time
                if st0 is not None:
                    last_st = st0
                prev_book = b.name
                continue
            st = row.story_time
            if st is None:
                continue
            if last_st is not None and st < last_st:
                out.append(StoryTimeJump(
                    book=b.name, chapter=row.chapter,
                    prev_story_time=last_st, this_story_time=st,
                ))
            last_st = st
        prev_book = b.name
    return out


def _unresolved_threads(books: list[BookSummary]) -> list[UnresolvedThread]:
    """A thread is unresolved when it appears in `Threads opened:`
    in book/chapter A and there's no matching string in any book/
    chapter's `Threads closed:` later in series order.

    \"Matching\" is substring (case-insensitive) — the close
    summary doesn't have to repeat the open phrasing verbatim.
    Empty / placeholder threads (`none`, `zero`, …) are pre-
    filtered upstream by `_is_zero_threads`.
    """
    closed_norm: list[str] = []
    for b in books:
        for _, t in b.threads_closed:
            closed_norm.append(t.lower())

    unresolved: list[UnresolvedThread] = []
    for b in books:
        for chapter, t in b.threads_opened:
            t_norm = t.lower()
            # Exact substring match either direction (the close note
            # may be a shorter restatement, or a longer expansion).
            matched = any(t_norm in c or c in t_norm
                           for c in closed_norm)
            if not matched:
                unresolved.append(UnresolvedThread(
                    book=b.name, chapter=chapter, thread=t,
                ))
    return unresolved


# ---------------------------------------------------------- composite score


def _composite_score(
    books: list[BookSummary], threshold: float,
    backwards: list[StoryTimeJump],
    unresolved: list[UnresolvedThread],
) -> float:
    """0–10 composite score blending four signals:

      - mean per-book completion (summary + eval coverage)
      - mean fraction-above-threshold
      - story-time discipline penalty (backwards jumps cost 0.5
        each, capped at 3.0)
      - unresolved-thread penalty (1.0 per thread / total opened,
        capped at 2.0)
    """
    if not books:
        return 0.0
    coverage = statistics.fmean(
        [(b.summary_coverage + b.eval_coverage) / 2 for b in books]
    )
    above_frac_per_book: list[float] = []
    for b in books:
        if b.chapter_count == 0:
            continue
        above_frac_per_book.append(b.above_threshold / b.chapter_count)
    above_mean = (statistics.fmean(above_frac_per_book)
                   if above_frac_per_book else 0.0)
    base = (coverage * 4.0) + (above_mean * 6.0)  # 0..10

    base -= min(3.0, 0.5 * len(backwards))
    total_opened = sum(len(b.threads_opened) for b in books)
    if total_opened > 0:
        unresolved_frac = len(unresolved) / total_opened
        base -= min(2.0, 2.0 * unresolved_frac)
    return max(0.0, min(10.0, round(base, 2)))


# ---------------------------------------------------------- render


def render_markdown(report: SeriesArcReport) -> str:
    parts: list[str] = []
    parts.append("# Series arc score")
    parts.append("")
    parts.append(
        f"**Composite arc score: {report.arc_score:.1f} / 10** "
        f"(threshold: {report.threshold:.1f}, books: {report.book_count})"
    )
    if report.book_count < 2:
        parts.append("")
        parts.append(
            "_Series-arc scoring is meant for ≥2 books. With only "
            "one book, the score reduces to per-book completion._"
        )
    parts.append("")
    parts.append("## Books")
    parts.append("")
    parts.append("| Book | Chapters | Summary % | Eval % | ≥thr | Story time |")
    parts.append("|---|---|---|---|---|---|")
    for b in report.books:
        story_range = "—"
        if b.earliest_story_time and b.latest_story_time:
            if b.earliest_story_time == b.latest_story_time:
                story_range = b.earliest_story_time
            else:
                story_range = f"{b.earliest_story_time} → {b.latest_story_time}"
        parts.append(
            f"| {b.name} | {b.chapter_count} | "
            f"{int(b.summary_coverage * 100)}% | "
            f"{int(b.eval_coverage * 100)}% | "
            f"{b.above_threshold}/{b.chapter_count} | "
            f"{story_range} |"
        )

    if report.cross_book_cast:
        parts.append("")
        parts.append("## Cross-book cast")
        parts.append("")
        ranked = sorted(report.cross_book_cast.items(),
                         key=lambda kv: -len(kv[1]))
        for name, books in ranked[:20]:
            parts.append(f"- `{name}` — appears in {', '.join(books)}")

    if report.overlapping_books:
        parts.append("")
        parts.append(
            "_Overlapping story-time ranges (the clock reset at these book "
            "boundaries is expected, not a backwards jump): "
            + "; ".join(f"`{p}`" for p in report.overlapping_books) + "_"
        )

    if report.backwards_story_time_jumps:
        parts.append("")
        parts.append("## Backwards story-time jumps")
        parts.append("")
        parts.append(
            "_Backwards = a chapter whose `story_time` is earlier than "
            "the prior chapter's. Legitimate for flashbacks; check "
            "each one is intentional._"
        )
        parts.append("")
        for j in report.backwards_story_time_jumps:
            parts.append(
                f"- {j.book} ch{j.chapter}: "
                f"{j.prev_story_time} → {j.this_story_time}"
            )

    if report.unresolved_threads:
        parts.append("")
        parts.append("## Unresolved threads")
        parts.append("")
        parts.append(
            "_Threads opened in one chapter with no matching close in "
            "any later chapter. Substring-matched both directions; "
            "false positives possible if the close phrased it very "
            "differently._"
        )
        parts.append("")
        for t in report.unresolved_threads[:30]:
            parts.append(f"- {t.book} ch{t.chapter}: {t.thread}")
        if len(report.unresolved_threads) > 30:
            parts.append(f"  …and {len(report.unresolved_threads) - 30} more.")

    return "\n".join(parts) + "\n"
