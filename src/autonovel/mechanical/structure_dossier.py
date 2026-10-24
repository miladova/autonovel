"""Book-level structure dossier: data assembly for `/autonovel:structure-review`.

Packs everything the book-level structural reviewer needs to see *besides*
the prose into one JSON object:

  - the outline: its act headings (any `## ` heading that is followed by
    chapter entries), every `## Chapter N` entry (title, POV, story_time,
    beats), and the optional parseable spine sections `gen-outline` now
    writes: `## Spine` (the through-line question, want, opposing force),
    `## Stakes ladder` (one row per act) and `## Causal spine` (one
    `- N because M: <fact>` line per chapter);
  - every drafted chapter: frontmatter title / POV / story_time, word
    count, its position in the book as a start/end percentage of the
    total words, the gap in months since the previous chapter's
    story_time, the full text of its continuity summary, the latest
    per-chapter eval score;
  - the "last ~20%" window (chapters starting at or after 80% of the
    words), which the climax-build test reads;
  - presence / freshness of the whole-book reviewer artifacts, and the
    optional LLM-authored `books/<book>/threads.md` thread ledger
    (best-effort; never required).

**No judgement lives here.** Nothing in this module decides whether a
link is causal, whether a stake is higher, or whether a chapter could be
cut. The author rule for this repo is that scanners are data assembly or
candidate generators, never quality gates; the LLM reviewer does the
judging. Parsing is tolerant: a missing or older-shaped file degrades to
an empty field plus a warning, never an exception.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..summaries import state as summary_state
from .frontmatter import strip_yaml_frontmatter

# Reserved `## ` headings in an outline that are spine sections, not acts.
SPINE_SECTION = "spine"
STAKES_SECTION = "stakes ladder"
CAUSAL_SECTION = "causal spine"
_RESERVED_SECTIONS = {SPINE_SECTION, STAKES_SECTION, CAUSAL_SECTION,
                      "threads", "thread ledger"}

_H2_RE = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_CHAPTER_HEADING_RE = re.compile(
    r"^chapter\s+(\d+)\b\s*(?:[—–:\-]+\s*(.*))?$", re.IGNORECASE)
_POV_RE = re.compile(r"\(\s*POV\s*:\s*([^)]+)\)", re.IGNORECASE)
_KV_BULLET_RE = re.compile(r"^\s*[-*]\s+([A-Za-z][A-Za-z _/'-]*?)\s*:\s*(.*)$")
_BEAT_RE = re.compile(r"^\s{2,}[-*]\s+(.*)$")
_CAUSAL_LINE_RE = re.compile(
    r"^\s*[-*]\s*(?:ch(?:apter)?\.?\s*)?(?P<n>\d+)\s+"
    r"(?P<link>because|after)\s+(?:of\s+)?"
    r"(?P<causes>(?:ch(?:apter)?\.?\s*)?\d+(?:\s*(?:,|&|and)\s*(?:ch(?:apter)?\.?\s*)?\d+)*)"
    r"\s*(?:[:—–]|-\s)\s*(?P<text>.+)$",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"(?<!\d)(\d{3,4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?")
_RANGE_RE = re.compile(r"(\d+)\s*(?:-|–|—|to)\s*(\d+)")

CLIMAX_WINDOW_START_PCT = 80.0


# ------------------------------------------------------------------ outline


@dataclass
class OutlineChapter:
    chapter: int
    title: str = ""
    pov: str | None = None
    story_time: str | None = None
    beats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"chapter": self.chapter, "title": self.title, "pov": self.pov,
                "story_time": self.story_time, "beats": list(self.beats)}


@dataclass
class OutlineInfo:
    present: bool = False
    acts: list[dict] = field(default_factory=list)
    chapters: list[OutlineChapter] = field(default_factory=list)
    preamble: str = ""
    spine: dict = field(default_factory=lambda: {"present": False})
    stakes_ladder: dict = field(default_factory=lambda: {"present": False})
    causal_spine: dict = field(default_factory=lambda: {"present": False})
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "present": self.present,
            "preamble": self.preamble,
            "acts": self.acts,
            "chapters": [c.to_dict() for c in self.chapters],
            "spine": self.spine,
            "stakes_ladder": self.stakes_ladder,
            "causal_spine": self.causal_spine,
            "warnings": list(self.warnings),
        }


def _split_h2_sections(text: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Return (lines before the first H2, [(heading, body lines), ...])."""
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for raw in text.splitlines():
        m = _H2_RE.match(raw)
        if m:
            current = (m.group(1).strip(), [])
            sections.append(current)
            continue
        if current is None:
            preamble.append(raw)
        else:
            current[1].append(raw)
    return preamble, sections


def _clean_text(lines: list[str], limit: int = 2000) -> str:
    kept = [ln.strip() for ln in lines if ln.strip() and ln.strip() != "---"]
    out = " ".join(kept)
    return out if len(out) <= limit else out[: limit - 1].rstrip() + "…"


def _parse_chapter_entry(num: int, heading_rest: str, body: list[str]) -> OutlineChapter:
    title = (heading_rest or "").strip()
    pov = None
    m = _POV_RE.search(title)
    if m:
        pov = m.group(1).strip()
        title = _POV_RE.sub("", title).strip()
    entry = OutlineChapter(chapter=num, title=title, pov=pov)
    in_beats = False
    for raw in body:
        if not raw.strip():
            continue
        kv = _KV_BULLET_RE.match(raw)
        is_top_level = kv is not None and not raw.startswith("  ")
        if is_top_level:
            key = kv.group(1).strip().lower()
            in_beats = key == "beats"
            if key == "story_time":
                entry.story_time = kv.group(2).strip() or None
            elif key == "pov" and kv.group(2).strip():
                entry.pov = kv.group(2).strip()
            continue
        beat = _BEAT_RE.match(raw)
        if in_beats and beat:
            entry.beats.append(beat.group(1).strip())
        elif in_beats and entry.beats and raw.startswith("    "):
            # Continuation line of a wrapped beat.
            entry.beats[-1] = f"{entry.beats[-1]} {raw.strip()}"
    return entry


def _parse_kv_section(body: list[str]) -> dict:
    fields: dict[str, str] = {}
    for raw in body:
        kv = _KV_BULLET_RE.match(raw)
        if kv and not raw.startswith("  "):
            key = re.sub(r"[\s/-]+", "_", kv.group(1).strip().lower())
            fields[key] = kv.group(2).strip()
    return {"present": True, "fields": fields, "text": _clean_text(body, 4000)}


def _chapters_from_cell(cell: str) -> list[int]:
    nums: list[int] = []
    for part in re.split(r"[,;]", cell):
        part = part.strip()
        if not part:
            continue
        rng = _RANGE_RE.search(part)
        if rng:
            lo, hi = int(rng.group(1)), int(rng.group(2))
            if lo <= hi and hi - lo < 500:
                nums.extend(range(lo, hi + 1))
            continue
        single = re.search(r"\d+", part)
        if single:
            nums.append(int(single.group(0)))
    return sorted(set(nums))


def _parse_stakes_section(body: list[str]) -> dict:
    """Markdown table (preferred) or one bullet per act."""
    rows: list[dict] = []
    table = [ln for ln in body if ln.strip().startswith("|")]
    if len(table) >= 2:
        header = [c.strip().lower() for c in table[0].strip().strip("|").split("|")]
        for ln in table[1:]:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c or "--") for c in cells):
                continue  # separator row
            row = {header[i] if i < len(header) else f"col{i}": cells[i]
                   for i in range(len(cells))}
            chap_key = next((k for k in row if k.startswith("chapter")), None)
            row["chapters_list"] = _chapters_from_cell(row.get(chap_key, "")) if chap_key else []
            rows.append(row)
    else:
        for ln in body:
            if re.match(r"^\s*[-*]\s+", ln) and not ln.startswith("  "):
                text = re.sub(r"^\s*[-*]\s+", "", ln).strip()
                paren = re.search(r"\(([^)]*\d[^)]*)\)", text)
                rows.append({"text": text,
                             "chapters_list": _chapters_from_cell(paren.group(1)) if paren else []})
    return {"present": True, "rows": rows, "text": _clean_text(body, 4000)}


def _parse_causal_section(body: list[str]) -> dict:
    links: list[dict] = []
    unparsed: list[str] = []
    for ln in body:
        if not re.match(r"^\s*[-*]\s+", ln) or ln.startswith("    "):
            continue
        m = _CAUSAL_LINE_RE.match(ln)
        if not m:
            unparsed.append(ln.strip())
            continue
        causes = sorted({int(x) for x in re.findall(r"\d+", m.group("causes"))})
        links.append({"chapter": int(m.group("n")), "link": m.group("link").lower(),
                      "cause_chapters": causes, "text": m.group("text").strip()})
    return {"present": True, "links": links, "unparsed_lines": unparsed}


def parse_outline(text: str) -> OutlineInfo:
    info = OutlineInfo(present=bool(text.strip()))
    if not info.present:
        info.warnings.append("outline.md is missing or empty.")
        return info
    preamble, sections = _split_h2_sections(text)
    info.preamble = _clean_text([ln for ln in preamble if not ln.startswith("# ")], 3000)

    pending_act: dict | None = None
    for heading, body in sections:
        ch = _CHAPTER_HEADING_RE.match(heading)
        if ch:
            entry = _parse_chapter_entry(int(ch.group(1)), ch.group(2) or "", body)
            info.chapters.append(entry)
            if pending_act is not None:
                pending_act["chapters"].append(entry.chapter)
            continue
        key = heading.strip().lower()
        if key == SPINE_SECTION:
            info.spine = _parse_kv_section(body)
            pending_act = None
        elif key == STAKES_SECTION:
            info.stakes_ladder = _parse_stakes_section(body)
            pending_act = None
        elif key == CAUSAL_SECTION:
            info.causal_spine = _parse_causal_section(body)
            pending_act = None
        elif key in _RESERVED_SECTIONS:
            pending_act = None
        else:
            # A candidate act heading; it becomes an act only if chapter
            # entries follow it before the next non-chapter heading.
            pending_act = {"heading": heading, "chapters": [],
                           "intro": _clean_text(body, 2000)}
            info.acts.append(pending_act)
    info.acts = [a for a in info.acts if a["chapters"]]

    outline_nums = [c.chapter for c in info.chapters]
    if not info.spine.get("present"):
        info.warnings.append(
            "outline.md has no `## Spine` section (the through-line question). "
            "Outlines written before gen-outline required one lack it; the "
            "reviewer will infer it. Retrofit with `/autonovel:gen-outline "
            "--book <book> --add-spine`.")
    if not info.stakes_ladder.get("present"):
        info.warnings.append(
            "outline.md has no `## Stakes ladder` section (one row per act).")
    if not info.causal_spine.get("present"):
        info.warnings.append(
            "outline.md has no `## Causal spine` section (`- N because M: <fact>`).")
    else:
        covered = {lk["chapter"] for lk in info.causal_spine.get("links", [])}
        missing = [n for n in outline_nums if n > min(outline_nums or [1]) and n not in covered]
        info.causal_spine["missing_chapters"] = missing
        info.causal_spine["planned_after_links"] = [
            lk["chapter"] for lk in info.causal_spine.get("links", []) if lk["link"] == "after"]
        if missing:
            info.warnings.append(
                "`## Causal spine` has no line for chapter(s) "
                + ", ".join(str(n) for n in missing) + ".")
        if info.causal_spine.get("unparsed_lines"):
            info.warnings.append(
                f"`## Causal spine` has {len(info.causal_spine['unparsed_lines'])} "
                "line(s) not in the `- N because M: <fact>` shape.")
    return info


# ----------------------------------------------------------------- chapters


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    try:
        import yaml
        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 — degrade to a line parse
        out: dict = {}
        for ln in block.splitlines():
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", ln)
            if m:
                out[m.group(1)] = m.group(2).strip().strip("'\"")
        return out


def _body_word_count(text: str) -> int:
    body = strip_yaml_frontmatter(text).lstrip()
    lines = body.splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return len("\n".join(lines).split())


def _month_range(story_time: str | None) -> tuple[int, int] | None:
    """(first, last) as months since year 0 for the first and last
    date-like tokens of a story_time ("1479-01 to 1485-11"), else None.
    Purely positional arithmetic; non-calendar story times return None."""
    if not story_time:
        return None
    months: list[int] = []
    for m in _DATE_RE.finditer(str(story_time)):
        year = int(m.group(1))
        month = int(m.group(2)) if m.group(2) else 1
        if not 1 <= month <= 12:
            month = 1
        months.append(year * 12 + (month - 1))
    if not months:
        return None
    return months[0], months[-1]


@dataclass
class ChapterEntry:
    chapter: int
    title: str | None = None
    pov: str | None = None
    story_time: str | None = None
    word_count: int = 0
    start_pct: float = 0.0
    end_pct: float = 0.0
    gap_months_from_previous: int | None = None
    summary_present: bool = False
    summary_stale: bool = False
    summary: str = ""
    latest_score: float | None = None
    outline_title: str | None = None

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter, "title": self.title, "pov": self.pov,
            "story_time": self.story_time, "word_count": self.word_count,
            "start_pct": self.start_pct, "end_pct": self.end_pct,
            "gap_months_from_previous": self.gap_months_from_previous,
            "summary_present": self.summary_present,
            "summary_stale": self.summary_stale,
            "summary": self.summary,
            "latest_score": self.latest_score,
            "outline_title": self.outline_title,
        }


def _artifact(path: Path, chapter_mtime: float | None) -> dict:
    if not path.is_file():
        return {"present": False, "path": str(path)}
    mtime = path.stat().st_mtime
    return {"present": True, "path": str(path), "mtime": mtime,
            "stale": chapter_mtime is not None and chapter_mtime > mtime}


def build_dossier(book_root: Path) -> dict:
    """Assemble the dossier for one book. Pure read; never writes."""
    from ..paths import iter_chapter_files
    from .chapter_summary import _index_latest_per_chapter_eval

    book_root = Path(book_root)
    chapters_dir = book_root / "chapters"
    outline_path = book_root / "outline.md"
    outline = parse_outline(
        outline_path.read_text(encoding="utf-8") if outline_path.is_file() else "")
    outline_titles = {c.chapter: c.title for c in outline.chapters}
    scores = _index_latest_per_chapter_eval(book_root / "eval_logs")

    entries: list[ChapterEntry] = []
    newest_chapter_mtime: float | None = None
    for path in iter_chapter_files(chapters_dir):
        try:
            num = int(path.stem.split("_")[-1])
        except ValueError:
            continue
        text = path.read_text(encoding="utf-8")
        fm = _frontmatter(text)
        wc = fm.get("word_count")
        try:
            words = int(wc) if wc is not None else _body_word_count(text)
        except (TypeError, ValueError):
            words = _body_word_count(text)
        entry = ChapterEntry(
            chapter=num,
            title=(str(fm["title"]) if fm.get("title") else None),
            pov=(str(fm["pov"]) if fm.get("pov") else None),
            story_time=(str(fm["story_time"]) if fm.get("story_time") else None),
            word_count=words,
            latest_score=scores.get(num),
            outline_title=outline_titles.get(num),
        )
        mtime = path.stat().st_mtime
        newest_chapter_mtime = mtime if newest_chapter_mtime is None else max(newest_chapter_mtime, mtime)
        summary_path = chapters_dir / f"{path.stem}.summary.md"
        if summary_path.is_file():
            entry.summary_present = True
            entry.summary = strip_yaml_frontmatter(
                summary_path.read_text(encoding="utf-8")).strip()
            entry.summary_stale = summary_state(path).status == "stale"
        entries.append(entry)
    entries.sort(key=lambda e: e.chapter)

    total = sum(e.word_count for e in entries)
    running = 0
    prev_end: int | None = None
    for e in entries:
        e.start_pct = round(100.0 * running / total, 1) if total else 0.0
        running += e.word_count
        e.end_pct = round(100.0 * running / total, 1) if total else 0.0
        # Gap = this chapter's first date minus the previous chapter's
        # last date: the time jump the reader crosses between them.
        span = _month_range(e.story_time)
        if span is not None and prev_end is not None:
            e.gap_months_from_previous = span[0] - prev_end
        if span is not None:
            prev_end = span[1]

    climax_window = [e.chapter for e in entries if e.start_pct >= CLIMAX_WINDOW_START_PCT]
    if entries and not climax_window:
        climax_window = [entries[-1].chapter]

    warnings = list(outline.warnings)
    missing_summaries = [e.chapter for e in entries if not e.summary_present]
    stale_summaries = [e.chapter for e in entries if e.summary_stale]
    if missing_summaries:
        warnings.append("no continuity summary for chapter(s) "
                        + ", ".join(map(str, missing_summaries))
                        + " — run /autonovel:summarize-chapter --all.")
    if stale_summaries:
        warnings.append("summary no longer matches its chapter for chapter(s) "
                        + ", ".join(map(str, stale_summaries))
                        + " — the chapter's text changed after the summary was written;"
                        " trust the prose over these summaries.")
    drafted = {e.chapter for e in entries}
    outlined = {c.chapter for c in outline.chapters}
    if outlined and drafted and outlined != drafted:
        only_outline = sorted(outlined - drafted)
        only_drafted = sorted(drafted - outlined)
        if only_outline:
            warnings.append("outlined but not drafted: chapter(s) "
                            + ", ".join(map(str, only_outline)) + ".")
        if only_drafted:
            warnings.append("drafted but not in the outline: chapter(s) "
                            + ", ".join(map(str, only_drafted)) + ".")

    big_gaps = [{"from": entries[i - 1].chapter, "to": e.chapter,
                 "months": e.gap_months_from_previous}
                for i, e in enumerate(entries)
                if i and e.gap_months_from_previous is not None
                and e.gap_months_from_previous >= 12]

    edit_logs = book_root / "edit_logs"
    review_md = edit_logs / "review.md"
    if not review_md.is_file() and (edit_logs / "opus_review.md").is_file():
        review_md = edit_logs / "opus_review.md"
    artifacts = {
        "structure_review": _artifact(edit_logs / "structure_review.json", newest_chapter_mtime),
        "review": _artifact(review_md, newest_chapter_mtime),
        "reader_panel": _artifact(edit_logs / "reader_panel.json", newest_chapter_mtime),
        "seed": _artifact(book_root / "seed.txt", None),
    }
    previous = _previous_structure_review(edit_logs / "structure_review.json")
    if previous is not None:
        artifacts["structure_review"].update(previous)

    threads_path = book_root / "threads.md"
    threads = {"present": threads_path.is_file(), "path": str(threads_path)}
    if threads["present"]:
        t = threads_path.read_text(encoding="utf-8")
        threads["text"] = t if len(t) <= 20000 else t[:19999] + "…"
        threads["truncated"] = len(t) > 20000

    return {
        "book": book_root.name,
        "book_root": str(book_root),
        "chapter_count": len(entries),
        "total_words": total,
        "climax_window_start_pct": CLIMAX_WINDOW_START_PCT,
        "climax_window_chapters": climax_window,
        "story_time_gaps_of_a_year_or_more": big_gaps,
        "outline": outline.to_dict(),
        "chapters": [e.to_dict() for e in entries],
        "threads": threads,
        "artifacts": artifacts,
        "warnings": warnings,
        "note": ("Data only. Chapter scores are prose scores; they are not "
                 "evidence of structure."),
    }


def _previous_structure_review(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"parse_error": True}
    if not isinstance(data, dict):
        return {"parse_error": True}
    return {"structure_score": data.get("structure_score"),
            "removable_chapters": data.get("removable_chapters"),
            "timestamp": data.get("timestamp")}


def render_markdown(dossier: dict) -> str:
    """Compact human view: one row per chapter plus the warnings."""
    lines = [f"# Structure dossier — {dossier['book']}", "",
             f"{dossier['chapter_count']} chapters, {dossier['total_words']} words. "
             f"Climax window (start ≥ {dossier['climax_window_start_pct']:.0f}%): "
             + (", ".join(map(str, dossier["climax_window_chapters"])) or "—"), ""]
    acts = dossier["outline"].get("acts") or []
    if acts:
        lines.append("## Acts (from outline headings)")
        for a in acts:
            ch = a["chapters"]
            lines.append(f"- {a['heading']} — ch {ch[0]}–{ch[-1]}")
        lines.append("")
    lines += ["| Ch | Words | Start % | Gap (mo) | Story time | Title |",
              "|---|---|---|---|---|---|"]
    for c in dossier["chapters"]:
        gap = c["gap_months_from_previous"]
        lines.append(
            f"| {c['chapter']} | {c['word_count']} | {c['start_pct']:.1f} | "
            f"{'—' if gap is None else gap} | {c['story_time'] or '—'} | "
            f"{(c['title'] or c['outline_title'] or '—').replace('|', '/')} |")
    if dossier["warnings"]:
        lines += ["", "## Warnings"] + [f"- {w}" for w in dossier["warnings"]]
    return "\n".join(lines) + "\n"
