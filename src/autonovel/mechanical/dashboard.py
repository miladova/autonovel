"""Per-book dashboard — re-renders the shape of the book without
firing an LLM evaluate run.

Background: `/autonovel:evaluate --full` already emits a markdown
table with per-chapter `words / score / tension / dialogue% /
scenes / beats-hit`. That data lives in the latest full-mode eval
log. Today the only way to see it is to re-run evaluate, which
costs heavy-tier LLM time. This dashboard reads the existing
artefacts (eval logs, chapter frontmatter, chapter summaries,
motifs config) and re-renders + augments without an LLM call.

Augmentations beyond the existing table:

- ASCII sparkline column (▁ to █) for the score and tension
  series so the *shape* is visible at a glance.
- Per-book aggregates: chapter-count, mean / median / range /
  stdev of score, longest sub-threshold streak.
- Mechanical dimensions that don't need an LLM:
  - `cast_size` per chapter (count from each summary's
    `Cast on stage` field).
  - `scene_count` per chapter (count of `***` or `---` scene
    breaks).
  - `dialogue_density` per chapter (proportion of paragraphs
    starting with `"`).
  - `motif_density` per chapter (sum of motif keyword hits when
    `motifs.md` exists).

Worst item, not only the mean (2026-10-23): each row also shows the
chapter's lowest-scoring dimension (`place 6.9`, ⚠ under the dimension
floor) and its cold first reader's serious items, and the report ranks
the ten lowest chapter-dimension scores in the book under "Needs
attention first". `render_dimensions` is the `--dimensions` view: every
dimension for every chapter, in groups.

Pure mechanical. No LLM call. Light tier, safe to call repeatedly.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from .chapter_summary import (
    ScoreDetail,
    _index_latest_per_chapter_eval,
    chapter_score_details,
    dimension_label,
    format_low,
    summarize_chapters,
)
from .frontmatter import strip_yaml_frontmatter
from .motifs import build_report as build_motif_report
from ..paths import iter_chapter_files


_SCENE_BREAK_RE = re.compile(r"^(\*\s*\*\s*\*|---|\*\s*\*\s*\*)\s*$", re.MULTILINE)
_FULL_EVAL_RE = re.compile(r"^\d{8}_\d{6}_full\.json$")


@dataclass
class ChapterMetrics:
    chapter: int
    word_count: int | None = None
    score: float | None = None
    tension: float | None = None
    dialogue_density: float | None = None  # 0.0-1.0
    scene_count: int | None = None
    beats_hit: str | None = None           # "4/4" — pulled verbatim from eval
    irreversible_change: float | None = None
    cast_size: int | None = None
    motif_density: int | None = None       # sum of all motif hits
    pov: str | None = None
    detail: ScoreDetail | None = None      # every dimension, the lowest, the reader

    @property
    def low_dim(self) -> str | None:
        return self.detail.low_dim if self.detail else None

    @property
    def low_score(self) -> float | None:
        return self.detail.low_score if self.detail else None

    @property
    def reader_status(self) -> str:
        """`✓` (serious items fixed and confirmed), `2 left` (the second
        reader still found items), `6 unchecked` (the first reader's items
        were never re-read), `—` (no reader recorded)."""
        d = self.detail
        if d is None or (d.reader_first is None and d.reader_second is None):
            return "—"
        if d.reader_all_fixed:
            return "✓"
        if d.reader_second is not None:
            return f"{d.reader_second} left" if d.reader_second else "✓"
        return f"{d.reader_first} unchecked" if d.reader_first else "✓"


@dataclass
class BookAggregate:
    chapter_count: int
    score_mean: float | None
    score_median: float | None
    score_min: float | None
    score_max: float | None
    score_stdev: float | None
    longest_sub_threshold_streak: int
    tension_mean: float | None
    tension_min: float | None
    tension_max: float | None
    threshold: float
    floor: float | None = None
    lowest: tuple[int, str, float] | None = None   # (chapter, dimension, score)
    below_floor: int = 0                           # chapter-dimension scores under the floor


@dataclass
class TensionDrop:
    """Three or more consecutive chapters of declining tension."""
    start: int
    end: int
    values: list[float]


@dataclass
class WorstItem:
    """One chapter-dimension score among the book's lowest."""
    chapter: int
    dimension: str
    score: float
    moment: str | None = None
    fix: str | None = None


@dataclass
class DashboardReport:
    book: str
    rows: list[ChapterMetrics]
    aggregate: BookAggregate | None
    tension_drops: list[TensionDrop] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)  # which artefact each col came from
    worst: list[WorstItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "book": self.book,
            "rows": [
                {
                    "chapter": r.chapter,
                    "word_count": r.word_count,
                    "score": r.score,
                    "tension": r.tension,
                    "dialogue_density": r.dialogue_density,
                    "scene_count": r.scene_count,
                    "beats_hit": r.beats_hit,
                    "irreversible_change": r.irreversible_change,
                    "cast_size": r.cast_size,
                    "motif_density": r.motif_density,
                    "pov": r.pov,
                    "low_dim": r.low_dim,
                    "low_score": r.low_score,
                    "reader": r.reader_status,
                    "dimensions": dict(r.detail.dimensions) if r.detail else {},
                }
                for r in self.rows
            ],
            "aggregate": (
                {
                    "chapter_count": self.aggregate.chapter_count,
                    "score_mean": self.aggregate.score_mean,
                    "score_median": self.aggregate.score_median,
                    "score_min": self.aggregate.score_min,
                    "score_max": self.aggregate.score_max,
                    "score_stdev": self.aggregate.score_stdev,
                    "longest_sub_threshold_streak":
                        self.aggregate.longest_sub_threshold_streak,
                    "tension_mean": self.aggregate.tension_mean,
                    "tension_min": self.aggregate.tension_min,
                    "tension_max": self.aggregate.tension_max,
                    "threshold": self.aggregate.threshold,
                    "floor": self.aggregate.floor,
                    "lowest": (
                        {"chapter": self.aggregate.lowest[0],
                         "dimension": self.aggregate.lowest[1],
                         "score": self.aggregate.lowest[2]}
                        if self.aggregate.lowest else None),
                    "below_floor": self.aggregate.below_floor,
                } if self.aggregate else None
            ),
            "worst": [
                {"chapter": w.chapter, "dimension": w.dimension, "score": w.score,
                 "moment": w.moment, "fix": w.fix}
                for w in self.worst
            ],
            "tension_drops": [
                {"start": d.start, "end": d.end, "values": d.values}
                for d in self.tension_drops
            ],
            "sources": dict(self.sources),
        }


# ---------------------------------------------------------- public entry


def build_dashboard(book_root: Path, *, threshold: float = 7.0,
                    floor: float | None = None, worst_n: int = 10) -> DashboardReport:
    """Inspect every artefact under `book_root/` and return a
    DashboardReport. Pure I/O — no LLM, no subprocess.

    `threshold` defines the chapter-score gate (default 7.0 from
    `defaults.chapter_threshold`); used for the sub-threshold streak
    and is forwarded into the aggregate so the renderer can highlight
    chapters below the bar.

    `floor` is the dimension floor (`defaults.dimension_floor`; the
    threshold when unset): a dimension under it marks the chapter ⚠ even
    when the mean passes. `worst_n` sizes the "Needs attention first" list.
    """
    if floor is None:
        floor = threshold
    chapters_dir = book_root / "chapters"
    chapter_paths = iter_chapter_files(chapters_dir)
    summary_rows = {row.chapter: row for row in summarize_chapters(book_root)}
    details = chapter_score_details(book_root / "eval_logs")

    # Pull `tension`, `dialogue%`, `scene_count`, `beats_hit`,
    # `irreversible_change` from the latest --full eval log if any
    # exists. Per-chapter rows in --chapter eval logs DO NOT carry
    # tension; that's a --full-only column.
    full_rows = _read_latest_full_eval_rows(book_root / "eval_logs")
    full_index = {row.get("chapter"): row for row in full_rows
                  if isinstance(row.get("chapter"), int)}

    # A per-chapter eval may carry `tension` too (draft-pass writes it);
    # the --full log, when present, wins below.
    chapter_tension = _index_latest_per_chapter_eval(book_root / "eval_logs", key="tension")

    # Motif index — counts per chapter for the sum across all motifs.
    motif_index: dict[int, int] = {}
    if (book_root / "motifs.md").is_file():
        mr = build_motif_report(book_root)
        for r in mr.rows:
            motif_index[r.chapter] = sum(r.counts.values())

    sources: dict[str, str] = {
        "score": "per-chapter eval logs (latest)",
        "word_count": "chapter frontmatter; fallback to body word count",
        "cast_size": "chapter summary file (Cast on stage)",
        "scene_count": "*** / --- markers in chapter prose",
        "dialogue_density": "fraction of paragraphs starting with \"",
        "tension": "(missing — run /autonovel:evaluate --full)",
        "beats_hit": "(missing — run /autonovel:evaluate --full)",
        "irreversible_change": "(missing — run /autonovel:evaluate --full)",
        "motif_density": "books/{book}/motifs.md" if motif_index else "(no motifs.md)",
    }
    if chapter_tension:
        sources["tension"] = "per-chapter eval logs (latest)"
    if full_rows:
        sources["tension"] = "latest --full eval log"
        sources["beats_hit"] = "latest --full eval log"
        sources["irreversible_change"] = "latest --full eval log"

    rows: list[ChapterMetrics] = []
    for ch_path in chapter_paths:
        m = re.match(r"^ch_(\d+)\.md$", ch_path.name)
        if not m:
            continue
        n = int(m.group(1))
        prose = strip_yaml_frontmatter(ch_path.read_text(encoding="utf-8"))

        m_row = ChapterMetrics(chapter=n, detail=details.get(n))
        sm_row = summary_rows.get(n)
        if sm_row is not None:
            m_row.word_count = sm_row.word_count
            m_row.score = sm_row.score
            m_row.pov = sm_row.pov
            if sm_row.cast is not None:
                m_row.cast_size = len(sm_row.cast)
        m_row.scene_count = _count_scenes(prose)
        m_row.dialogue_density = _dialogue_density(prose)
        if n in motif_index:
            m_row.motif_density = motif_index[n]

        if n in chapter_tension:
            m_row.tension = chapter_tension[n]
        full_row = full_index.get(n)
        if full_row:
            tension = full_row.get("tension")
            if isinstance(tension, (int, float)):
                m_row.tension = float(tension)
            beats_hit = full_row.get("beats_hit")
            if beats_hit is not None:
                m_row.beats_hit = str(beats_hit)
            irc = full_row.get("irreversible_change")
            if isinstance(irc, (int, float)):
                m_row.irreversible_change = float(irc)
            # Prefer --full's score/word_count when both exist.
            if m_row.score is None:
                s = full_row.get("score") or full_row.get("overall_score")
                if isinstance(s, (int, float)):
                    m_row.score = float(s)
            if m_row.word_count is None:
                wc = full_row.get("word_count") or full_row.get("words")
                if isinstance(wc, (int, float)):
                    m_row.word_count = int(wc)

        rows.append(m_row)

    rows.sort(key=lambda r: r.chapter)
    aggregate = _aggregate(rows, threshold=threshold, floor=floor)
    tension_drops = _tension_drops(rows)
    if details:
        sources["lowest"] = "lowest dimension in each chapter's latest eval log"
        sources["reader"] = "first_reader block of each chapter's latest eval log"
    return DashboardReport(
        book=book_root.name,
        rows=rows,
        aggregate=aggregate,
        tension_drops=tension_drops,
        sources=sources,
        worst=_worst_items(rows, n=worst_n),
    )


def _worst_items(rows: list[ChapterMetrics], *, n: int) -> list[WorstItem]:
    """The `n` lowest chapter-dimension scores in the book, lowest first
    (ties in chapter order), each with the judge's weakest moment for
    that dimension (and its fix, for the chapter's lowest)."""
    items: list[WorstItem] = []
    for r in rows:
        if r.detail is None:
            continue
        for name, score in r.detail.dimensions.items():
            items.append(WorstItem(chapter=r.chapter, dimension=name, score=score))
    items.sort(key=lambda w: (w.score, w.chapter, w.dimension))
    items = items[:n]
    by_ch = {r.chapter: r.detail for r in rows}
    for w in items:
        d = by_ch.get(w.chapter)
        if d is not None:
            w.moment = d.moments.get(w.dimension)
            if d.low_dim == w.dimension:
                w.fix = d.low_fix
    return items


# ---------------------------------------------------------- helpers


def _read_latest_full_eval_rows(eval_dir: Path) -> list[dict]:
    """Find the most recent `<ts>_full.json` in `eval_dir` and
    return its `rows` / `chapters` / `per_chapter` array. Tolerates
    a few historical key names since the evaluate.md spec doesn't
    pin one."""
    if not eval_dir.is_dir():
        return []
    candidates = [p for p in eval_dir.iterdir()
                  if p.is_file() and _FULL_EVAL_RE.match(p.name)]
    if not candidates:
        return []
    candidates.sort(key=lambda p: p.name)
    latest = candidates[-1]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(data, dict):
        return []
    for key in ("rows", "chapters", "per_chapter", "pacing_curve"):
        rows = data.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _count_scenes(prose: str) -> int:
    """Number of distinct scenes in a chapter — break-marker count + 1
    when there's any prose, capped at zero for an empty chapter."""
    if not prose.strip():
        return 0
    breaks = len(_SCENE_BREAK_RE.findall(prose))
    return breaks + 1


def _dialogue_density(prose: str) -> float | None:
    """Fraction of prose paragraphs that open with a double-quote.
    Returns None for empty chapters (avoids 0.0 noise)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", prose) if p.strip()]
    if not paragraphs:
        return None
    dialogue = sum(1 for p in paragraphs
                    if p.startswith('"') or p.startswith("“"))
    return round(dialogue / len(paragraphs), 3)


def _aggregate(rows: list[ChapterMetrics], *, threshold: float,
               floor: float | None = None) -> BookAggregate | None:
    if not rows:
        return None
    lowest: tuple[int, str, float] | None = None
    below = 0
    for r in rows:
        if r.detail is None:
            continue
        for name, v in r.detail.dimensions.items():
            if floor is not None and v < floor:
                below += 1
            if lowest is None or v < lowest[2]:
                lowest = (r.chapter, name, v)
    scores = [r.score for r in rows if r.score is not None]
    tensions = [r.tension for r in rows if r.tension is not None]

    streak = 0
    longest = 0
    for r in rows:
        if r.score is not None and r.score < threshold:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0

    return BookAggregate(
        chapter_count=len(rows),
        score_mean=round(statistics.fmean(scores), 2) if scores else None,
        score_median=round(statistics.median(scores), 2) if scores else None,
        score_min=min(scores) if scores else None,
        score_max=max(scores) if scores else None,
        score_stdev=(round(statistics.stdev(scores), 2)
                     if len(scores) >= 2 else None),
        longest_sub_threshold_streak=longest,
        tension_mean=(round(statistics.fmean(tensions), 2)
                      if tensions else None),
        tension_min=min(tensions) if tensions else None,
        tension_max=max(tensions) if tensions else None,
        threshold=threshold,
        floor=floor,
        lowest=lowest,
        below_floor=below,
    )


def _tension_drops(rows: list[ChapterMetrics]) -> list[TensionDrop]:
    """Find every monotonically-declining run of length ≥3."""
    drops: list[TensionDrop] = []
    run_start = None
    run_values: list[float] = []
    prev = None
    for r in rows:
        t = r.tension
        if t is None:
            if run_start is not None and len(run_values) >= 3:
                drops.append(TensionDrop(start=run_start, end=r.chapter - 1,
                                          values=list(run_values)))
            run_start = None
            run_values = []
            prev = None
            continue
        if prev is not None and t < prev:
            if run_start is None:
                run_start = r.chapter - 1
                run_values = [prev, t]
            else:
                run_values.append(t)
        else:
            if run_start is not None and len(run_values) >= 3:
                drops.append(TensionDrop(start=run_start, end=r.chapter - 1,
                                          values=list(run_values)))
            run_start = None
            run_values = []
        prev = t
    if run_start is not None and len(run_values) >= 3:
        drops.append(TensionDrop(start=run_start, end=rows[-1].chapter,
                                  values=list(run_values)))
    return drops


# ---------------------------------------------------------- sparkline


_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float | None], *,
                lo: float | None = None,
                hi: float | None = None) -> str:
    """ASCII sparkline of one numeric series. None values render as
    a gap (space). Uses block characters from `▁` to `█` mapped over
    the value range; if `lo` and `hi` aren't given, picks them from
    the data."""
    nums = [v for v in values if v is not None]
    if not nums:
        return " " * len(values)
    if lo is None:
        lo = min(nums)
    if hi is None:
        hi = max(nums)
    span = hi - lo if hi > lo else 1.0
    out = []
    last = len(_SPARK_BLOCKS) - 1
    for v in values:
        if v is None:
            out.append(" ")
            continue
        idx = int(round((v - lo) / span * last))
        idx = max(0, min(last, idx))
        out.append(_SPARK_BLOCKS[idx])
    return "".join(out)


# ---------------------------------------------------------- render


def render_markdown(report: DashboardReport, *, threshold: float = 7.0) -> str:
    """Markdown rendering: per-chapter table, sparkline lines,
    aggregate block, tension-drop alarms."""
    parts: list[str] = []
    parts.append(f"# Dashboard — {report.book}")
    parts.append("")
    if not report.rows:
        parts.append("_No chapters drafted yet._")
        return "\n".join(parts) + "\n"

    # Headers — only include columns that have at least one
    # populated value; otherwise the table is mostly em-dashes.
    cols: list[tuple[str, str]] = [("ch", "Ch"), ("words", "Words")]
    has_score = any(r.score is not None for r in report.rows)
    has_tension = any(r.tension is not None for r in report.rows)
    has_dialog = any(r.dialogue_density is not None for r in report.rows)
    has_scene = any(r.scene_count is not None for r in report.rows)
    has_beats = any(r.beats_hit for r in report.rows)
    has_irc = any(r.irreversible_change is not None for r in report.rows)
    has_cast = any(r.cast_size is not None for r in report.rows)
    has_motif = any(r.motif_density is not None for r in report.rows)
    has_low = any(r.low_dim is not None for r in report.rows)
    has_reader = any(r.reader_status != "—" for r in report.rows)
    floor = report.aggregate.floor if report.aggregate else None
    if has_score:
        cols.append(("score", "Score"))
    if has_low:
        cols.append(("low", "Lowest"))
    if has_reader:
        cols.append(("reader", "Reader"))
    if has_tension:
        cols.append(("tension", "Tension"))
    if has_dialog:
        cols.append(("dialog", "Dialog %"))
    if has_scene:
        cols.append(("scene", "Scenes"))
    if has_beats:
        cols.append(("beats", "Beats"))
    if has_irc:
        cols.append(("irc", "IrrChg"))
    if has_cast:
        cols.append(("cast", "Cast"))
    if has_motif:
        cols.append(("motif", "Motif Σ"))

    parts.append("| " + " | ".join(label for _, label in cols) + " |")
    parts.append("|" + "|".join("---" for _ in cols) + "|")
    for r in report.rows:
        cells: list[str] = []
        for key, _ in cols:
            cells.append(_fmt_cell(r, key, threshold=threshold, floor=floor))
        parts.append("| " + " | ".join(cells) + " |")

    if has_low or has_reader:
        parts.append("")
        legend = []
        if has_low and floor is not None:
            legend.append(f"Lowest is the chapter's weakest dimension; ⚠ = under the "
                          f"{floor:.1f} floor, which sends a chapter to revise even when "
                          f"its mean passes")
        if has_reader:
            legend.append("Reader = the cold first reader's serious items: ✓ fixed and "
                          "re-read, N left = the second reader still found N, N unchecked "
                          "= the first reader's N were fixed but never re-read")
        parts.append("_" + ". ".join(legend) + "._")

    # Sparklines.
    if has_score:
        spark = sparkline([r.score for r in report.rows], lo=0.0, hi=10.0)
        parts.append("")
        parts.append(f"score:   `{spark}`")
    if has_tension:
        spark = sparkline([r.tension for r in report.rows], lo=0.0, hi=10.0)
        parts.append(f"tension: `{spark}`")

    # Aggregate.
    a = report.aggregate
    if a is not None and (a.score_mean is not None or a.tension_mean is not None):
        parts.append("")
        parts.append("## Aggregate")
        parts.append("")
        if a.score_mean is not None:
            parts.append(
                f"- score:  mean {a.score_mean:.2f} · median {a.score_median:.2f}"
                f" · range {a.score_min:.1f}–{a.score_max:.1f}"
                + (f" · stdev {a.score_stdev:.2f}" if a.score_stdev is not None else "")
            )
            parts.append(
                f"- longest sub-{a.threshold:.1f} streak: "
                f"{a.longest_sub_threshold_streak} chapter(s)"
            )
        if a.lowest is not None:
            ch, dim, v = a.lowest
            parts.append(
                f"- lowest dimension in the book: {dimension_label(dim)} {v:.1f} "
                f"(ch {ch}); {a.below_floor} chapter-dimension score(s) under the "
                f"{a.floor:.1f} floor"
            )
        if a.tension_mean is not None:
            parts.append(
                f"- tension: mean {a.tension_mean:.2f}"
                f" · range {a.tension_min:.1f}–{a.tension_max:.1f}"
            )

    if report.worst:
        parts.append("")
        parts.append("## Needs attention first")
        parts.append("")
        parts.append("The lowest scores in the book, whatever the chapter's mean:")
        parts.append("")
        for i, w in enumerate(report.worst, 1):
            mark = " ⚠" if floor is not None and w.score < floor else ""
            line = f"{i}. ch {w.chapter} · {dimension_label(w.dimension)} {w.score:.1f}{mark}"
            if w.moment:
                line += f" — {_clip(w.moment, 140)}"
            parts.append(line)
        unchecked = [(r.chapter, r.reader_status) for r in report.rows
                     if r.reader_status not in ("—", "✓")]
        if unchecked:
            parts.append("")
            parts.append("Cold-reader items not confirmed fixed: "
                         + ", ".join(f"ch {c} ({st})" for c, st in unchecked)
                         + ". `/autonovel:first-read <N>` re-reads a chapter.")

    # Tension-drop alarms.
    if report.tension_drops:
        parts.append("")
        parts.append("## ⚠️ Tension drops (consecutive declines)")
        parts.append("")
        for d in report.tension_drops:
            arrow = " → ".join(f"{v:.1f}" for v in d.values)
            parts.append(
                f"- chapters {d.start}-{d.end}: {arrow}. Consider "
                f"`/autonovel:revision-pass --chapters {d.start}-{d.end}` "
                f"with focus on stakes-escalation."
            )

    # Source provenance footer.
    parts.append("")
    parts.append("_sources_:")
    for col, src in report.sources.items():
        parts.append(f"- {col}: {src}")

    return "\n".join(parts) + "\n"


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _fmt_cell(r: ChapterMetrics, key: str, *, threshold: float,
              floor: float | None = None) -> str:
    if key == "ch":
        return str(r.chapter)
    if key == "low":
        return format_low(r.low_dim, r.low_score, floor=floor)
    if key == "reader":
        return r.reader_status
    if key == "words":
        return str(r.word_count) if r.word_count is not None else "—"
    if key == "score":
        if r.score is None:
            return "—"
        marker = "" if r.score >= threshold else " ⚠"
        return f"{r.score:.1f}{marker}"
    if key == "tension":
        return f"{r.tension:.1f}" if r.tension is not None else "—"
    if key == "dialog":
        if r.dialogue_density is None:
            return "—"
        return f"{int(round(r.dialogue_density * 100))}%"
    if key == "scene":
        return str(r.scene_count) if r.scene_count is not None else "—"
    if key == "beats":
        return r.beats_hit or "—"
    if key == "irc":
        return f"{r.irreversible_change:.1f}" if r.irreversible_change is not None else "—"
    if key == "cast":
        return str(r.cast_size) if r.cast_size is not None else "—"
    if key == "motif":
        return str(r.motif_density) if r.motif_density is not None else "—"
    return "—"


# ---------------------------------------------------------- --dimensions

# The chapter rubric in three groups, so each table fits a terminal. A
# dimension not listed (a genre dimension such as `history`, or one a
# book adds) goes in a fourth group.
DIMENSION_GROUPS: list[tuple[str, list[str]]] = [
    ("Story", ["beat_coverage", "irreversible_change", "engagement",
               "plants_seeded", "continuity", "canon_compliance"]),
    ("People and place", ["character_depth", "character_voice",
                          "sense_of_place", "lore_integration"]),
    ("Writing", ["voice_adherence", "prose_quality", "register",
                 "show_dont_tell_ratio", "concreteness", "repetition"]),
]


def render_dimensions(report: DashboardReport) -> str:
    """Every dimension for every chapter: one table per group, a mean row
    and a lowest row under each, the chapter's own lowest in bold and ⚠
    under the floor; then how often each dimension was a chapter's
    weakest, and the cold readers' counts."""
    parts = [f"# Dimensions — {report.book}", ""]
    scored = [r for r in report.rows if r.detail and r.detail.dimensions]
    if not scored:
        parts.append("_No per-chapter eval logs with dimension scores yet._")
        return "\n".join(parts) + "\n"
    floor = report.aggregate.floor if report.aggregate else None
    seen = {n for r in scored for n in r.detail.dimensions}
    known = {n for _, names in DIMENSION_GROUPS for n in names}
    groups = [(t, [n for n in names if n in seen]) for t, names in DIMENSION_GROUPS]
    extra = sorted(seen - known)
    if extra:
        groups.append(("Genre and book-specific", extra))
    for title, names in groups:
        if not names:
            continue
        parts.append(f"## {title}")
        parts.append("")
        parts.append("| Ch | Score | " + " | ".join(dimension_label(n) for n in names) + " |")
        parts.append("|---|---|" + "|".join("---" for _ in names) + "|")
        for r in scored:
            d = r.detail
            cells = []
            for n in names:
                v = d.dimensions.get(n)
                if v is None:
                    cells.append("—")
                    continue
                cell = f"{v:.1f}" + (" ⚠" if floor is not None and v < floor else "")
                cells.append(f"**{cell}**" if n == d.low_dim else cell)
            overall = f"{d.overall:.1f}" if d.overall is not None else "—"
            parts.append(f"| {r.chapter} | {overall} | " + " | ".join(cells) + " |")
        means, lows = [], []
        for n in names:
            vals = [r.detail.dimensions[n] for r in scored if n in r.detail.dimensions]
            means.append(f"{statistics.fmean(vals):.2f}" if vals else "—")
            lows.append(f"{min(vals):.1f}" if vals else "—")
        parts.append("| mean | | " + " | ".join(means) + " |")
        parts.append("| lowest | | " + " | ".join(lows) + " |")
        parts.append("")
    counts: dict[str, int] = {}
    for r in scored:
        if r.low_dim:
            counts[r.low_dim] = counts.get(r.low_dim, 0) + 1
    if counts:
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        parts.append("**Weakest dimension, by number of chapters:** "
                     + ", ".join(f"{dimension_label(n)} {c}" for n, c in ranked))
        parts.append("")
    readers = [r for r in scored if r.detail.reader_first is not None
               or r.detail.reader_second is not None]
    if readers:
        parts.append("## Cold first readers (serious items)")
        parts.append("")
        parts.append("| Ch | 1st reader | 2nd reader | Status |")
        parts.append("|---|---|---|---|")
        for r in readers:
            d = r.detail
            first = "—" if d.reader_first is None else str(d.reader_first)
            second = "—" if d.reader_second is None else str(d.reader_second)
            parts.append(f"| {r.chapter} | {first} | {second} | {r.reader_status} |")
        parts.append("")
    floor_txt = f"the {floor:.1f} floor" if floor is not None else "the floor"
    parts.append(f"_Score is the chapter's overall score; **bold** is its lowest "
                 f"dimension; ⚠ is under {floor_txt}. Logs older than the cold "
                 f"first reader show — in its columns._")
    return "\n".join(parts) + "\n"
