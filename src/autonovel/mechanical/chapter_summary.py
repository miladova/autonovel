"""Per-chapter overview table — what's in each chapter at a glance.

Pulls already-structured data from three places:

  1. Each `ch_NN.md` chapter file's YAML frontmatter — `chapter`,
     `pov`, `story_time`, `events`, `status`, `word_count`.
  2. Each `ch_NN.summary.md` continuity-handoff file's structured
     sections — **Plot**, **Cast on stage**, **Story time**.
  3. The latest eval log (`eval_logs/<timestamp>_chNN.json` or
     `eval_logs/<timestamp>_full.json`'s per-chapter rows) for
     `overall_score`.

Returns one record per drafted chapter with a normalised set of
fields the `/autonovel:chapter-summary` command renders as a
markdown table. Pure-Python; no LLM.

Bug story (2026-04-26): the user asked "how do I find which
chapters are mainly set in Venice when Jakob was learning?" and
correctly noted that grepping chapter prose isn't the right tool.
The structured fields above give a scannable per-chapter view that
makes that filter trivial — read down the Plot column, ignore
chapters whose `story_time` falls outside the relevant range.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter


@dataclass
class ChapterRow:
    chapter: int
    story_time: str | None = None
    pov: str | None = None
    word_count: int | None = None
    location: str | None = None    # short phrase from summary's Location section
    plot: str | None = None        # one-sentence pull from Plot
    cast: list[str] = field(default_factory=list)   # names from Cast on stage
    score: float | None = None     # latest overall_score
    status: str | None = None      # canonical: drafted | revised | imported
    revision_count: int = 0        # how many times the chapter has been re-evaluated
    pov_state: str | None = None       # what POV knows / wants / fears at close
    threads_opened: str | None = None  # mysteries / promises future chapters owe
    threads_closed: str | None = None  # earlier setups this chapter resolved
    summary_stale: bool = False    # True when ch_NN.md mtime > ch_NN.summary.md
    low_dim: str | None = None     # the latest eval's lowest-scoring dimension
    low_score: float | None = None
    reader_open: int | None = None  # serious first-reader items not confirmed fixed

    @property
    def display_status(self) -> str:
        """Canonical, human-readable status for tables and TUIs.
        Combines `status` with `revision_count` so the user sees
        'revised ×6' instead of an ambiguous 'revised'.

        Strict enumeration of returned values:
          - 'drafted'   — initial draft, never re-evaluated
          - 'revised ×N' — evaluated N times after initial draft
                          (N is the post-draft eval count, ≥1)
          - 'imported'  — externally-imported manuscript
          - <raw>       — anything else (legacy values like
                          'revised-v6' from before the canonical
                          enumeration; fallback so we don't lose
                          information)
        """
        raw = (self.status or "").strip().lower()
        if raw == "drafted":
            if self.revision_count > 0:
                return f"revised ×{self.revision_count}"
            return "drafted"
        if raw == "revised":
            if self.revision_count >= 1:
                return f"revised ×{self.revision_count}"
            return "revised"
        if raw == "imported":
            return "imported"
        # Legacy / unrecognised — pass through verbatim so we don't
        # lose information (e.g. old `revised-v6` shape).
        return self.status or ""

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "story_time": self.story_time,
            "pov": self.pov,
            "word_count": self.word_count,
            "location": self.location,
            "plot": self.plot,
            "cast": list(self.cast),
            "score": self.score,
            "status": self.status,
            "revision_count": self.revision_count,
            "display_status": self.display_status,
            "pov_state": self.pov_state,
            "threads_opened": self.threads_opened,
            "threads_closed": self.threads_closed,
            "summary_stale": self.summary_stale,
            "low_dim": self.low_dim,
            "low_score": self.low_score,
            "reader_open": self.reader_open,
        }


def summarize_chapters(book_root: Path) -> list[ChapterRow]:
    """Return one ChapterRow per drafted `ch_NN.md` under
    `book_root/chapters/`, ordered by chapter number. Chapters
    without a summary file or eval log produce a row with the
    available fields populated and the rest left None.
    """
    from ..paths import iter_chapter_files
    chapters_dir = book_root / "chapters"
    chapter_files = iter_chapter_files(chapters_dir)
    eval_dir = book_root / "eval_logs"
    eval_index = _index_latest_per_chapter_eval(eval_dir)
    eval_counts = _count_evals_per_chapter(eval_dir)
    details = chapter_score_details(eval_dir)

    rows: list[ChapterRow] = []
    for ch_path in chapter_files:
        num_str = ch_path.stem.split("_")[-1]
        try:
            num = int(num_str)
        except ValueError:
            continue

        row = ChapterRow(chapter=num)
        text = ch_path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        row.story_time = fm.get("story_time")
        row.pov = fm.get("pov")
        row.status = fm.get("status")
        wc = fm.get("word_count")
        if wc is not None:
            try:
                row.word_count = int(wc)
            except (TypeError, ValueError):
                pass

        # Fall back to a real word count if frontmatter didn't carry one
        # (rare; chapters drafted before word_count became standard).
        # Strip the leading `# Title` heading so the fallback matches
        # the frontmatter convention (body words only, not the heading).
        if row.word_count is None:
            body = strip_yaml_frontmatter(text).lstrip()
            if body.startswith("#"):
                # Drop the heading line plus any blank lines after it.
                lines = body.splitlines()
                lines = lines[1:]
                while lines and lines[0].strip() == "":
                    lines.pop(0)
                body = "\n".join(lines)
            row.word_count = len(body.split())

        summary_path = chapters_dir / f"{ch_path.stem}.summary.md"
        if summary_path.is_file():
            sm = _parse_summary(summary_path.read_text(encoding="utf-8"))
            row.plot = sm.get("plot")
            row.cast = sm.get("cast") or []
            row.location = sm.get("location")
            row.pov_state = sm.get("pov_state")
            row.threads_opened = sm.get("threads_opened")
            row.threads_closed = sm.get("threads_closed")
            # The summary's Story time tends to be more specific than
            # the frontmatter's (which can be a range); prefer it
            # when present.
            if sm.get("story_time"):
                row.story_time = sm["story_time"]
            # Continuity check: a chapter modified since its
            # `.summary.md` was written has drifted from its summary.
            # The next chapter's drafter reads summaries for prior-
            # chapter context, so a stale summary breaks continuity.
            try:
                if ch_path.stat().st_mtime > summary_path.stat().st_mtime:
                    row.summary_stale = True
            except OSError:  # pragma: no cover
                pass

        row.score = eval_index.get(num)
        detail = details.get(num)
        if detail is not None:
            row.low_dim, row.low_score = detail.low_dim, detail.low_score
            row.reader_open = detail.reader_open
        # revision_count = post-draft eval count - 1 (the first eval
        # is the post-draft eval; subsequent ones are post-revise).
        # Imported chapters skip the count (they don't go through the
        # autonovel draft→revise cycle).
        eval_count = eval_counts.get(num, 0)
        if (row.status or "").lower() != "imported":
            row.revision_count = max(0, eval_count - 1)
        rows.append(row)
    return rows


# ----------------------------------------------------- frontmatter parsing


_FRONTMATTER_FIELDS = ("chapter", "pov", "story_time", "events",
                       "status", "word_count", "book")


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML frontmatter as a flat string→string dict.

    We don't pull in PyYAML for this — the chapter frontmatter is a
    flat shallow mapping with simple scalar values, and parsing it
    line-by-line keeps the helper dependency-light. Fields not in
    `_FRONTMATTER_FIELDS` are ignored.
    """
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict[str, str] = {}
    for i in range(1, len(lines)):
        line = lines[i]
        if line.strip() == "---":
            break
        # Field on its own line: `key: value` (value may be quoted).
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if key not in _FRONTMATTER_FIELDS:
            continue
        # Strip surrounding quotes on the value (single or double).
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        out[key] = value
    return out


# --------------------------------------------------- summary.md parsing


_SECTION_RE = re.compile(r"^\s*\*\*([A-Z][A-Za-z ]+):\*\*\s*(.*)$")


def parse_summary_sections(text: str) -> dict[str, str]:
    """Return every `**Field:** value` section of a summary.md as a
    `{lowercased field name: full text}` mapping — no truncation, no
    first-sentence pull. Continuation lines are joined with spaces.

    `_parse_summary` (the table-shaped view) and the story map's
    synopsis (which needs the whole Plot paragraph) both read
    summaries through this one parser.
    """
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_buf: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_buf
        if current_key:
            sections[current_key] = " ".join(current_buf).strip()
        current_key = None
        current_buf = []

    for raw in text.splitlines():
        m = _SECTION_RE.match(raw)
        if m:
            flush()
            key = m.group(1).strip().lower()
            current_key = key
            first_value = m.group(2).strip()
            if first_value:
                current_buf.append(first_value)
        elif current_key:
            stripped = raw.strip()
            if stripped:
                current_buf.append(stripped)
    flush()
    return sections


def _parse_summary(text: str) -> dict:
    """Pull `**Plot:**`, `**Cast on stage:**`, `**Story time:**` from
    a summary.md. Returns a dict with `plot` (one-sentence string),
    `cast` (list of names), `story_time` (string).

    The summary template (commands/draft.md step 12, summarize-
    chapter.md step) writes each field as `**Field:** value` — the
    regex above matches that shape and is generous about
    whitespace.
    """
    sections = parse_summary_sections(text)

    out: dict = {}
    if "plot" in sections:
        out["plot"] = _first_sentence(sections["plot"])
    if "cast on stage" in sections:
        out["cast"] = _parse_cast(sections["cast on stage"])
    if "story time" in sections:
        out["story_time"] = sections["story time"]
    if "location" in sections:
        # Location is meant to be a short phrase; if the summary
        # accidentally wrote a longer paragraph, take the first
        # sentence so the table column doesn't blow.
        out["location"] = _first_sentence(sections["location"])
    if "pov state" in sections:
        # Multi-sentence allowed (knows / wants / fears) but cap at
        # a reasonable display length.
        out["pov_state"] = _trim(sections["pov state"], 280)
    if "threads opened" in sections:
        out["threads_opened"] = _trim(sections["threads opened"], 280)
    if "threads closed" in sections:
        out["threads_closed"] = _trim(sections["threads closed"], 280)
    return out


def _trim(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _first_sentence(text: str) -> str:
    """Return text up through the first sentence-ending punctuation
    (`.`, `?`, `!`). The terminator must be preceded by a letter so
    that a Plot field starting with an ISO date (`1492-08-12. The
    protagonist…`) doesn't truncate to just the date — the `.` after
    `12` is not a sentence boundary even though it's followed by
    whitespace. If no boundary found, return the whole text. Caps at
    180 chars so a rambling sentence doesn't blow the column."""
    if not text:
        return ""
    # `(?<=[A-Za-z])` requires a letter immediately before the
    # punctuation, ruling out date-internal periods and trailing
    # numerals.
    m = re.search(r"(?<=[A-Za-z])[.!?](?=\s|$)", text)
    if m:
        result = text[: m.end()].strip()
    else:
        result = text.strip()
    if len(result) > 180:
        result = result[:179].rstrip() + "…"
    return result


def _parse_cast(text: str) -> list[str]:
    """The Cast on stage line in a summary looks like:
       'Tommaso — POV; Niccolò — first appearance, declined to speak; Marco — antagonist'
    Pull just the names (everything before the first '—' or ',' in
    each ';'-separated entry)."""
    names: list[str] = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Split off any role descriptor after `—`, `-`, or `,`.
        for sep in (" — ", " – ", " - ", ","):
            if sep in chunk:
                chunk = chunk.split(sep, 1)[0]
                break
        chunk = chunk.strip()
        if chunk and chunk not in names:
            names.append(chunk)
    return names


# ----------------------------------------------------- eval log indexing


_EVAL_FILENAME_RE = re.compile(
    r"^(?P<ts>\d{8}_\d{6})_ch(?P<chapter>\d+)_eval\.json$"
)
_EVAL_CH_FILENAME_RE = re.compile(
    r"^(?P<ts>\d{8}_\d{6})_ch(?P<chapter>\d+)\.json$"
)


def _count_evals_per_chapter(eval_dir: Path) -> dict[int, int]:
    """Return {chapter_number: count of distinct eval logs}. Used as
    a proxy for revision count — each /autonovel:revise run produces
    a fresh eval log, so post-draft eval count = revise count + 1
    (the initial post-draft eval). Returns 0 for chapters with no
    log (also covered by `dict.get(num, 0)`).

    Honest signal vs LLM-self-reported `status: revised-v6`:
    counting actual eval files on disk can't be hallucinated.
    """
    if not eval_dir.is_dir():
        return {}
    counts: dict[int, int] = {}
    for path in eval_dir.iterdir():
        if not path.is_file() or path.suffix != ".json":
            continue
        m = _EVAL_FILENAME_RE.match(path.name) or _EVAL_CH_FILENAME_RE.match(path.name)
        chapter: int | None = None
        if m:
            try:
                chapter = int(m.group("chapter"))
            except ValueError:
                continue
        else:
            plain = re.match(r"^ch(\d+)_eval\.json$", path.name)
            if not plain:
                continue
            try:
                chapter = int(plain.group(1))
            except ValueError:
                continue
        counts[chapter] = counts.get(chapter, 0) + 1
    return counts


def _eval_number(data: dict, key: str) -> float | None:
    """Pull a numeric value out of one eval log. `key` may be dotted
    (`dimensions.irreversible_change`); a dimension stored as
    `{"score": 8.6, ...}` yields its `score`. None when absent or
    non-numeric."""
    value: object = data
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    if isinstance(value, dict):
        value = value.get("score")
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _index_latest_per_chapter_eval(eval_dir: Path, *,
                                   key: str = "overall_score") -> dict[int, float]:
    """Return {chapter_number: latest value of `key`} by scanning
    `eval_logs/` (default `overall_score`; `key` may be dotted, e.g.
    `dimensions.irreversible_change`, or a top-level field such as
    `tension`). Tolerates a few historical naming conventions
    (`<ts>_ch01.json`, `<ts>_ch01_eval.json`, plain `chNN_eval.json`).
    Picks the latest log carrying the field: by the filename's timestamp,
    or by mtime when the name has none (the two compare as times, so a
    later `evaluate` log beats an older plain draft-pass log). Skips
    files it can't parse.
    """
    by_chapter: dict[int, tuple[float, float]] = {}
    for chapter, when, data in _iter_chapter_eval_logs(eval_dir):
        score_f = _eval_number(data, key)
        if score_f is None:
            continue
        prior = by_chapter.get(chapter)
        if prior is None or when > prior[0]:
            by_chapter[chapter] = (when, score_f)
    return {ch: score for ch, (_when, score) in by_chapter.items()}


# ----------------------------------------------------- worst item, not only the mean

# A chapter's mean hides its weakest dimension: a 6.9 for sense of place
# disappears inside a 7.8 (kingmaker2 ch 7, 2026-10-23: "the worst scored
# items should be the ones that get the attention"). These helpers read
# the whole latest eval log per chapter so every surface can show the
# lowest dimension beside the mean, and the open cold-reader items.

# Short labels for tables. A dimension not listed here (a genre
# dimension such as `history`, or a custom one) shows its own name.
DIMENSION_LABELS: dict[str, str] = {
    "beat_coverage": "beats",
    "irreversible_change": "change",
    "engagement": "pull",
    "plants_seeded": "plants",
    "continuity": "continuity",
    "canon_compliance": "canon",
    "character_depth": "depth",
    "character_voice": "voices",
    "sense_of_place": "place",
    "lore_integration": "lore",
    "voice_adherence": "voice",
    "prose_quality": "prose",
    "register": "register",
    "show_dont_tell_ratio": "show",
    "concreteness": "concrete",
}


def dimension_label(name: str) -> str:
    return DIMENSION_LABELS.get(name, name.replace("_", " "))


@dataclass
class ScoreDetail:
    """One chapter's latest eval, reduced to what a reader of the scores
    needs: the mean, every dimension, the lowest one and why, and the
    cold first reader's serious items that nobody has confirmed fixed."""
    chapter: int
    overall: float | None = None
    dimensions: dict[str, float] = field(default_factory=dict)
    low_dim: str | None = None
    low_score: float | None = None
    low_moment: str | None = None   # the judge's weakest_moment for low_dim
    low_fix: str | None = None
    moments: dict[str, str] = field(default_factory=dict)  # dimension → the judge's weakest_moment
    reader_first: int | None = None   # serious items, first cold reader
    reader_second: int | None = None  # serious items, second reader (None: none ran)
    reader_all_fixed: bool | None = None
    reader_open: int | None = None

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter, "overall": self.overall,
            "dimensions": dict(self.dimensions),
            "low_dim": self.low_dim, "low_score": self.low_score,
            "low_moment": self.low_moment, "low_fix": self.low_fix,
            "reader_first": self.reader_first, "reader_second": self.reader_second,
            "reader_all_fixed": self.reader_all_fixed, "reader_open": self.reader_open,
        }


def _iter_chapter_eval_logs(eval_dir: Path):
    """Yield `(chapter, when, data)` for every per-chapter eval log in the
    three naming shapes. `when` is seconds since the epoch: the filename's
    `YYYYMMDD_HHMMSS` stamp, or the file's mtime when it has none."""
    if not eval_dir.is_dir():
        return
    for path in eval_dir.iterdir():
        if not path.is_file() or path.suffix != ".json":
            continue
        m = _EVAL_FILENAME_RE.match(path.name) or _EVAL_CH_FILENAME_RE.match(path.name)
        if m:
            chapter = int(m.group("chapter"))
            try:
                when = datetime.strptime(m.group("ts"), "%Y%m%d_%H%M%S").timestamp()
            except ValueError:
                when = path.stat().st_mtime
        else:
            plain = re.match(r"^ch(\d+)_eval\.json$", path.name)
            if not plain:
                continue
            chapter, when = int(plain.group(1)), path.stat().st_mtime
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — skip malformed eval logs
            continue
        if isinstance(data, dict):
            yield chapter, when, data


def _count_items(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, list):
        return len(value)
    if isinstance(value, (int, float)):
        return int(value)
    return None


def score_detail(chapter: int, data: dict) -> ScoreDetail:
    """Reduce one eval log to a ScoreDetail."""
    d = ScoreDetail(chapter=chapter, overall=_eval_number(data, "overall_score"))
    dims = data.get("dimensions")
    if isinstance(dims, dict):
        for name, value in dims.items():
            v = _eval_number(dims, name)
            if v is not None:
                d.dimensions[name] = v
                if isinstance(value, dict) and value.get("weakest_moment"):
                    d.moments[name] = str(value["weakest_moment"])
    if d.dimensions:
        low = min(d.dimensions.values())
        tied = [n for n, v in d.dimensions.items() if v == low]
        judge = data.get("weakest_dimension")
        d.low_dim = judge if judge in tied else tied[0]
        d.low_score = low
        entry = dims.get(d.low_dim) if isinstance(dims, dict) else None
        if isinstance(entry, dict):
            d.low_moment = entry.get("weakest_moment") or None
            d.low_fix = entry.get("fix") or None
    fr = data.get("first_reader")
    if isinstance(fr, dict):
        d.reader_first = _count_items(fr.get("serious_items_first"))
        d.reader_second = _count_items(fr.get("serious_items_second"))
        fixed = fr.get("all_fixed")
        d.reader_all_fixed = fixed if isinstance(fixed, bool) else None
        last = d.reader_second if d.reader_second is not None else d.reader_first
        if last is not None:
            d.reader_open = 0 if d.reader_all_fixed else last
    return d


def chapter_score_details(eval_dir: Path) -> dict[int, ScoreDetail]:
    """{chapter: ScoreDetail} from each chapter's latest eval log that
    carries an `overall_score` (same choice as the score columns)."""
    latest: dict[int, tuple[float, dict]] = {}
    for chapter, when, data in _iter_chapter_eval_logs(eval_dir):
        if _eval_number(data, "overall_score") is None:
            continue
        prior = latest.get(chapter)
        if prior is None or when > prior[0]:
            latest[chapter] = (when, data)
    return {ch: score_detail(ch, data) for ch, (_when, data) in latest.items()}


def format_low(low_dim: str | None, low_score: float | None, *,
               floor: float | None = None) -> str:
    """`place 6.9` (with ` ⚠` under the floor), or `—`."""
    if low_dim is None or low_score is None:
        return "—"
    mark = " ⚠" if floor is not None and low_score < floor else ""
    return f"{dimension_label(low_dim)} {low_score:.1f}{mark}"


# ----------------------------------------------------- table renderer


def render_markdown_table(rows: list[ChapterRow]) -> str:
    """Render the chapter summary as a markdown table the
    `/autonovel:chapter-summary` command prints to stdout.

    Columns: Ch | Date | POV | Sco | Low | Words | Cast | Plot. Low is
    the latest eval's lowest-scoring dimension (`place 6.9`), so a weak
    dimension is not hidden by the chapter's mean.

    The Plot column is **prefixed with the chapter's Location** when
    the summary carries one (e.g.
    `Venice / Rialto: Fire at the apothecary…`). Chapters whose
    summary predates the Location field show plot alone — graceful
    fallback so older books don't get blank Plot cells. The Sco
    column is intentionally compact (3-char header + 3-char cell)
    to leave width for Plot, which is where filtering happens.

    Cast and Plot are width-trimmed defensively so the table stays
    one-row-per-chapter even on long entries.
    """
    if not rows:
        return "_No chapters drafted yet._\n"

    header = "| Ch | Date       | POV       | Sco | Low          | Words | Cast                          | Plot |"
    sep    = "|----|------------|-----------|-----|--------------|-------|-------------------------------|------|"
    lines = [header, sep]
    for r in rows:
        ch = f"{r.chapter:>2}"
        date = (r.story_time or "—")[:10].ljust(10)
        pov = (r.pov or "—")[:9].ljust(9)
        score = f"{r.score:.1f}" if r.score is not None else "—"
        score_col = score.rjust(3)
        low_col = format_low(r.low_dim, r.low_score)[:12].ljust(12)
        words = f"{r.word_count}" if r.word_count is not None else "—"
        words_col = words.rjust(5)
        cast_str = ", ".join(r.cast) if r.cast else "—"
        if len(cast_str) > 29:
            cast_str = cast_str[:28] + "…"
        cast_col = cast_str.ljust(29)
        plot_text = (r.plot or "—").replace("|", "\\|")
        if r.location:
            location_text = r.location.replace("|", "\\|")
            plot_with_location = f"**{location_text}** — {plot_text}"
        else:
            plot_with_location = plot_text
        lines.append(f"| {ch} | {date} | {pov} | {score_col} | {low_col} | {words_col} | {cast_col} | {plot_with_location} |")
    return "\n".join(lines) + "\n"
