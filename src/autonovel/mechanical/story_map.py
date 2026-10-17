"""Story map — one self-contained HTML page that shows a book's shape.

Background (author, 2026-10-17, on the 24-chapter *kingmaker*): "I don't
feel I have a good sense of how the plot develops — it feels a little
like a bunch of short anecdotes and not a continuing story building to a
climax." `/autonovel:chapter-summary`, `/autonovel:summaries` and
`/autonovel:dashboard` are table-shaped CLI output; this module is the
*reading* surface over the same data, built from material that already
exists on disk — never from a fresh read of the prose:

  - chapter frontmatter (`title`, `pov`, `story_time`, `events`) and each
    `ch_NN.summary.md` (Plot, POV state, Cast on stage, Location,
    Threads opened / closed) via `chapter_summary`;
  - `outline.md` (act headers, per-chapter `events:` ids, an optional
    `## Threads` ledger in the foreshadow / add-subplot shapes);
  - `books/<book>/threads.md` — the story-map thread ledger (grammar
    below), written by `/autonovel:story-map --refresh-threads` and
    hand-editable;
  - `shared/characters.md` (principals, in the author's order) and
    `shared/events.md` (event titles + per-chapter `rendered_in` notes);
  - the eval logs, through `dashboard.build_dashboard` (score / tension /
    irreversible change per chapter).

Tabs: **Synopsis** (the summaries stitched in reading order, act headers
from the outline), **Threads** (threads × chapters grid with the
escalation curve directly underneath on the same chapter axis),
**Characters** (presence grid + each principal's chapters in order with
the per-chapter state change), **Timeline & places** (story_time on a
proportional axis, gaps > 1 year labelled; places visited vs named-only).

Nothing here is a verdict. Where a reader might want "this thread
stalls", the page shows the data (which chapters touch it, the longest
run of chapters without a touch) and leaves the judgement to the author.

threads.md grammar (parsed exactly; other lines are reported as
warnings, never fatal):

    ## Thread: <name>
    - question: <the question the thread poses the reader>
    - ch <N> <role>: <one-line state of the thread after chapter N>
          role = plant | turn | payoff | touch   (omitted = touch)

    ## Character: <name>
    - aliases: <name>, <name>
    - arc: <one-line arc summary>
    - ch <N>: <one-line state change in chapter N>

    ## Places
    - <place>
    - <place>: <alias>, <alias>

`ch 5`, `ch 05`, `ch5`, `ch_05` and `ch. 5` all mean chapter 5; the
`: <note>` part of a `ch` line may be left off. HTML comments and any
other `##` section are ignored, so other tools may add their own
sections to the same file.

Thread source, in order of preference: `threads.md` → an explicit
`## Threads` ledger in `outline.md` → outline / frontmatter `events:`
ids (titles and touch notes from `shared/events.md`). Pure mechanical;
no LLM.
"""

from __future__ import annotations

import html
import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .chapter_summary import (
    _index_latest_per_chapter_eval,
    _parse_cast,
    _parse_frontmatter,
    parse_summary_sections,
    summarize_chapters,
)
from .chapter_titles import inspect_titles
from .dashboard import build_dashboard
from .pov_bleed import parse_cast_ordered
from ..paths import iter_chapter_files


ROLES = ("plant", "turn", "payoff", "touch")
# When one chapter carries several touches of the same thread, the cell
# shows the strongest: a payoff outranks a plant outranks a turn.
_ROLE_RANK = {"payoff": 3, "plant": 2, "turn": 1, "touch": 0}
_ROLE_GLYPH = {"plant": "P", "turn": "T", "payoff": "✓", "touch": "•"}
_ROLE_TEXT_GLYPH = {"plant": "P", "turn": "T", "payoff": "X", "touch": "o"}

READING_WPM = 230          # synopsis reading-time estimate
GAP_FLAG_YEARS = 1.0       # story-time gaps above this are labelled
SUMMARY_CAST_MIN = 3       # an unlisted cast name needs this many chapters

THREADS_LEDGER_HEADER = """# Threads — {book}

<!--
Story-map thread ledger. Read by `autonovel mechanical story-map` (the
/autonovel:story-map page). Written by `/autonovel:story-map
--refresh-threads` from the outline and the chapter summaries. Safe to
edit by hand: a plain `/autonovel:story-map` never rewrites this file;
only --refresh-threads does (the previous version is checkpointed).

Grammar (one item per line; other lines are reported, never fatal):

  ## Thread: <name>                 one section per plot thread
  - question: <the question the thread poses the reader>
  - ch <N> <role>: <one-line state of the thread after chapter N>
        role = plant | turn | payoff | touch   (omitted = touch)

  ## Character: <name>              one section per principal
  - aliases: <name>, <name>         how the summaries' Cast lines name them
  - arc: <one-line arc summary>
  - ch <N>: <one-line state change: what they want / what they lose>

  ## Places                         optional: canonical place names
  - <place>
  - <place>: <alias>, <alias>

`ch 5`, `ch 05`, `ch5` and `ch_05` all mean chapter 5; the `: <note>`
part of a `ch` line may be left off. A chapter may appear more than
once in a section. Other `##` sections are ignored.
-->
"""


# ---------------------------------------------------------------- model


@dataclass
class Touch:
    chapter: int
    role: str = "touch"
    note: str = ""

    def to_dict(self) -> dict:
        return {"chapter": self.chapter, "role": self.role, "note": self.note}


@dataclass
class Thread:
    name: str
    question: str = ""
    consequence: str = ""
    touches: list[Touch] = field(default_factory=list)

    @property
    def chapters(self) -> list[int]:
        return sorted({t.chapter for t in self.touches})

    def cell_role(self, chapter: int) -> str | None:
        roles = [t.role for t in self.touches if t.chapter == chapter]
        if not roles:
            return None
        return max(roles, key=lambda r: _ROLE_RANK.get(r, 0))

    def notes_for(self, chapter: int) -> list[Touch]:
        return [t for t in self.touches if t.chapter == chapter]

    def longest_gap(self) -> tuple[int, int, int] | None:
        """(chapters without a touch, last touch before, next touch) for
        the longest silent run between the first and last touch. Data,
        not a verdict — a thread may rightly sleep through an act."""
        chs = self.chapters
        best: tuple[int, int, int] | None = None
        for a, b in zip(chs, chs[1:]):
            silent = b - a - 1
            if silent > 0 and (best is None or silent > best[0]):
                best = (silent, a, b)
        return best

    def to_dict(self) -> dict:
        gap = self.longest_gap()
        return {
            "name": self.name,
            "question": self.question,
            "consequence": self.consequence,
            "chapters": self.chapters,
            "touches": [t.to_dict() for t in self.touches],
            "longest_gap": ({"chapters": gap[0], "after": gap[1], "before": gap[2]}
                            if gap else None),
        }


@dataclass
class CharacterArc:
    """One `## Character:` section of threads.md."""
    name: str
    aliases: list[str] = field(default_factory=list)
    arc: str = ""
    states: dict[int, list[str]] = field(default_factory=dict)


@dataclass
class Ledger:
    threads: list[Thread] = field(default_factory=list)
    characters: list[CharacterArc] = field(default_factory=list)
    places: list[tuple[str, list[str]]] = field(default_factory=list)
    has_places: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class Act:
    index: int
    title: str
    intro: str = ""
    chapters: list[int] = field(default_factory=list)

    @property
    def short(self) -> str:
        m = re.match(r"^((?:act|part)\s+[\w-]+)", self.title, re.IGNORECASE)
        return m.group(1).title() if m else f"Act {self.index + 1}"

    def to_dict(self) -> dict:
        return {"index": self.index, "title": self.title, "short": self.short,
                "intro": self.intro, "chapters": list(self.chapters)}


@dataclass
class OutlineInfo:
    acts: list[Act] = field(default_factory=list)
    chapter_titles: dict[int, str] = field(default_factory=dict)
    chapter_story_time: dict[int, str] = field(default_factory=dict)
    chapter_events: dict[int, list[str]] = field(default_factory=dict)
    chapter_act: dict[int, int] = field(default_factory=dict)
    ledger_threads: list[Thread] = field(default_factory=list)


@dataclass
class CastEntry:
    raw: str
    name: str


@dataclass
class MapChapter:
    chapter: int
    title: str = ""
    story_time: str = ""
    pov: str = ""
    score: float | None = None
    word_count: int | None = None
    plot: str = ""
    plot_line: str = ""
    pov_state: str = ""
    location: str = ""
    cast: list[CastEntry] = field(default_factory=list)
    threads_opened: str = ""
    threads_closed: str = ""
    has_summary: bool = False
    summary_stale: bool = False
    act: int | None = None
    start: str | None = None
    end: str | None = None
    t0: float | None = None
    t1: float | None = None
    gap_before: float | None = None      # years since the previous chapter ended
    backwards: bool = False              # starts before the previous chapter did
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter, "title": self.title,
            "story_time": self.story_time, "pov": self.pov,
            "score": self.score, "word_count": self.word_count,
            "plot": self.plot, "pov_state": self.pov_state,
            "location": self.location,
            "cast": [c.raw for c in self.cast],
            "threads_opened": self.threads_opened,
            "threads_closed": self.threads_closed,
            "has_summary": self.has_summary,
            "summary_stale": self.summary_stale,
            "act": self.act, "start": self.start, "end": self.end,
            "gap_before_years": (round(self.gap_before, 2)
                                 if self.gap_before is not None else None),
            "backwards": self.backwards,
        }


@dataclass
class Appearance:
    chapter: int
    as_pov: bool = False
    cast_entry: str = ""
    line: str = ""
    state: str = ""
    state_source: str = ""

    def to_dict(self) -> dict:
        return {"chapter": self.chapter, "as_pov": self.as_pov,
                "cast_entry": self.cast_entry, "line": self.line,
                "state": self.state, "state_source": self.state_source}


@dataclass
class Principal:
    name: str
    source: str
    aliases: list[str] = field(default_factory=list)
    arc: str = ""
    appearances: list[Appearance] = field(default_factory=list)
    # matching keys (lower-case), filled while building
    _keys: set[str] = field(default_factory=set, repr=False)
    _tokens: set[str] = field(default_factory=set, repr=False)
    _token_aliases: set[str] = field(default_factory=set, repr=False)
    _ledger: CharacterArc | None = field(default=None, repr=False)

    @property
    def slug(self) -> str:
        return re.sub(r"[^\w]+", "-", self.name.lower(), flags=re.UNICODE).strip("-")

    def to_dict(self) -> dict:
        return {"name": self.name, "source": self.source,
                "aliases": list(self.aliases), "arc": self.arc,
                "chapters": [a.chapter for a in self.appearances],
                "appearances": [a.to_dict() for a in self.appearances]}


@dataclass
class Place:
    name: str
    aliases: list[str] = field(default_factory=list)
    visited: list[int] = field(default_factory=list)
    named_only: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "aliases": list(self.aliases),
                "visited": list(self.visited), "named_only": list(self.named_only)}


@dataclass
class StoryMap:
    book: str
    title: str
    chapters: list[MapChapter]
    acts: list[Act]
    threads: list[Thread]
    thread_source: str
    principals: list[Principal]
    absent_principals: list[str]
    places: list[Place]
    place_source: str
    series: dict[str, list[float | None]]
    series_sources: dict[str, str]
    warnings: list[str]
    sources: dict[str, str]
    generated_at: str
    book_root: Path

    # ------------------------------------------------------- derived
    @property
    def total_words(self) -> int:
        return sum(c.word_count or 0 for c in self.chapters)

    @property
    def synopsis_words(self) -> int:
        return sum(len(c.plot.split()) for c in self.chapters)

    @property
    def synopsis_minutes(self) -> int:
        return _minutes(self.synopsis_words)

    @property
    def skim_words(self) -> int:
        """Words in the skim view: each chapter's end-of-chapter POV state
        (or its first plot sentence when the summary has no POV state)."""
        return sum(len((c.pov_state or c.plot_line).split()) for c in self.chapters)

    @property
    def span(self) -> tuple[str, str, float] | None:
        dated = [c for c in self.chapters if c.t0 is not None and c.t1 is not None]
        if not dated:
            return None
        first = min(dated, key=lambda c: c.t0)
        last = max(dated, key=lambda c: c.t1)
        return (first.start or "", last.end or "", last.t1 - first.t0)

    @property
    def columns(self) -> list[int]:
        cols = {c.chapter for c in self.chapters}
        for t in self.threads:
            cols.update(t.chapters)
        return sorted(cols)

    def to_dict(self) -> dict:
        span = self.span
        return {
            "book": self.book, "title": self.title,
            "generated_at": self.generated_at,
            "chapter_count": len(self.chapters),
            "word_count": self.total_words,
            "synopsis_words": self.synopsis_words,
            "synopsis_minutes": self.synopsis_minutes,
            "skim_words": self.skim_words,
            "story_time_span": ({"start": span[0], "end": span[1],
                                 "years": round(span[2], 1)} if span else None),
            "acts": [a.to_dict() for a in self.acts],
            "chapters": [c.to_dict() for c in self.chapters],
            "thread_source": self.thread_source,
            "threads": [t.to_dict() for t in self.threads],
            "characters": [p.to_dict() for p in self.principals],
            "absent_characters": list(self.absent_principals),
            "place_source": self.place_source,
            "places": [p.to_dict() for p in self.places],
            "escalation": {"chapters": [c.chapter for c in self.chapters],
                           "series": {k: list(v) for k, v in self.series.items()},
                           "sources": dict(self.series_sources)},
            "warnings": list(self.warnings),
            "sources": dict(self.sources),
        }


def _minutes(words: int) -> int:
    return max(1, math.ceil(words / READING_WPM)) if words else 0


# --------------------------------------------------------- threads.md

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_LEDGER_H2_RE = re.compile(r"^##(?!#)\s*(.+?)\s*$")
_LEDGER_THREAD_RE = re.compile(r"^thread\s*:\s*(.+)$", re.IGNORECASE)
_LEDGER_CHAR_RE = re.compile(r"^character\s*:\s*(.+)$", re.IGNORECASE)
_LEDGER_PLACES_RE = re.compile(r"^places$", re.IGNORECASE)
_TOUCH_RE = re.compile(
    r"^[-*]\s+ch(?:apter)?[\s._]*(\d+)"
    r"(?:\s+(plant|turn|payoff|touch))?\s*(?::\s*(.*?))?\s*$",
    re.IGNORECASE,
)
_KEY_RE = re.compile(r"^[-*]\s+(question|arc|aliases)\s*:\s*(.*?)\s*$", re.IGNORECASE)
_BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$")


def _blank_comments(text: str) -> str:
    """Remove HTML comments but keep their newlines so warnings still
    cite the right line numbers."""
    return _COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def parse_threads_ledger(text: str, *, filename: str = "threads.md") -> Ledger:
    """Parse the story-map ledger grammar (module docstring) exactly.
    Unrecognised lines inside a Thread / Character / Places section are
    collected in `Ledger.warnings` as `threads.md:<line>: …`."""
    ledger = Ledger()
    section: str | None = None          # "thread" | "character" | "places" | "other"
    cur_thread: Thread | None = None
    cur_char: CharacterArc | None = None
    for lineno, raw in enumerate(_blank_comments(text).splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# ") or line == "#":
            continue
        h2 = _LEDGER_H2_RE.match(line)
        if h2:
            head = h2.group(1)
            cur_thread = cur_char = None
            if m := _LEDGER_THREAD_RE.match(head):
                section = "thread"
                name = m.group(1).strip()
                cur_thread = next((t for t in ledger.threads if t.name == name), None)
                if cur_thread is None:
                    cur_thread = Thread(name=name)
                    ledger.threads.append(cur_thread)
            elif m := _LEDGER_CHAR_RE.match(head):
                section = "character"
                name = m.group(1).strip()
                cur_char = next((c for c in ledger.characters if c.name == name), None)
                if cur_char is None:
                    cur_char = CharacterArc(name=name)
                    ledger.characters.append(cur_char)
            elif _LEDGER_PLACES_RE.match(head):
                section = "places"
                ledger.has_places = True
            else:
                section = "other"
            continue
        if section in (None, "other"):
            continue

        def warn(why: str) -> None:
            ledger.warnings.append(f"{filename}:{lineno}: {why}: {line[:90]}")

        if section == "places":
            m = _BULLET_RE.match(line)
            if not m:
                warn("expected `- <place>` or `- <place>: <alias>, <alias>`")
                continue
            body = m.group(1)
            name, _, rest = body.partition(":")
            aliases = [a.strip() for a in rest.split(",") if a.strip()]
            if name.strip():
                ledger.places.append((name.strip(), aliases))
            continue

        m = _TOUCH_RE.match(line)
        if m:
            ch = int(m.group(1))
            role = (m.group(2) or "touch").lower()
            note = (m.group(3) or "").strip()
            if section == "thread" and cur_thread is not None:
                cur_thread.touches.append(Touch(chapter=ch, role=role, note=note))
            elif section == "character" and cur_char is not None:
                cur_char.states.setdefault(ch, []).append(note)
            continue
        m = _KEY_RE.match(line)
        if m:
            key, value = m.group(1).lower(), m.group(2).strip()
            if section == "thread" and cur_thread is not None and key == "question":
                cur_thread.question = value
                continue
            if section == "character" and cur_char is not None and key == "arc":
                cur_char.arc = value
                continue
            if section == "character" and cur_char is not None and key == "aliases":
                cur_char.aliases.extend(a.strip() for a in value.split(",") if a.strip())
                continue
            warn(f"`{key}:` does not belong in a {section} section")
            continue
        if section == "thread":
            warn("expected `- question: …` or `- ch <N> [plant|turn|payoff|touch]: …`")
        else:
            warn("expected `- aliases: …`, `- arc: …` or `- ch <N>: …`")
    for t in ledger.threads:
        t.touches.sort(key=lambda x: x.chapter)
    return ledger


# --------------------------------------------------------- outline.md

_H2_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
_H3_RE = re.compile(r"^###(?!#)\s+(.+?)\s*$")
_OUTLINE_CH_RE = re.compile(r"^chapter\s+(\d+)\b\s*[—–:.\-]*\s*(.*)$", re.IGNORECASE)
_ACT_RE = re.compile(r"^(act|part)\b", re.IGNORECASE)
_THREADS_SECTION_RE = re.compile(r"^(threads?|thread ledger|foreshadowing)\b", re.IGNORECASE)
_OUTLINE_FIELD_RE = re.compile(r"^[-*]\s+(story_time|events)\s*:\s*(.*?)\s*$")
_FORESHADOW_RE = re.compile(
    r"^[-*]\s+plant\s+ch[\s._]*(\d+)\s*/\s*payoff\s+ch[\s._]*(\d+)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
_LEGACY_ROLE_RE = re.compile(
    r"^[-*]\s+(plant|turn|payoff|touch)\s*:\s*ch(?:apter)?[\s._]*(\d+)\s*(?:[—–:\-]+\s*)?(.*?)\s*$",
    re.IGNORECASE,
)
_LEGACY_KEY_RE = re.compile(r"^[-*]\s+(description|question|consequence)\s*:\s*(.*?)\s*$",
                            re.IGNORECASE)


def _parse_id_list(value: str) -> list[str]:
    value = value.strip().strip("[]")
    return [v.strip().strip("'\"") for v in value.split(",") if v.strip().strip("'\"")]


def parse_outline(text: str) -> OutlineInfo:
    """Act headers (`## ACT …` / `## Part …`), per-chapter sections
    (`## Chapter N — title` with `- story_time:` / `- events:`), and an
    optional `## Threads` ledger (foreshadow / add-subplot shapes, or the
    threads.md touch lines under `### Thread: <name>`)."""
    info = OutlineInfo()
    mode: str | None = None              # "act" | "chapter" | "threads" | None
    cur_act: Act | None = None
    cur_ch: int | None = None
    intro_buf: list[str] = []
    ledger_lines: list[str] = []

    def close_act_intro() -> None:
        nonlocal intro_buf
        if cur_act is not None and intro_buf and not cur_act.intro:
            paras = "\n".join(intro_buf).strip()
            cur_act.intro = re.sub(r"\n{3,}", "\n\n", paras)
        intro_buf = []

    for raw in _blank_comments(text).splitlines():
        line = raw.rstrip()
        h2 = _H2_RE.match(line.strip())
        if h2 is None and mode != "threads":
            # `### Chapter N` nested under a `## Act …` header counts too.
            h3 = _H3_RE.match(line.strip())
            if h3 and _OUTLINE_CH_RE.match(h3.group(1).strip()):
                h2 = h3
        if h2:
            if mode == "act":
                close_act_intro()
            head = h2.group(1).strip()
            if m := _OUTLINE_CH_RE.match(head):
                cur_ch = int(m.group(1))
                mode = "chapter"
                if m.group(2).strip():
                    info.chapter_titles[cur_ch] = m.group(2).strip()
                if cur_act is not None:
                    info.chapter_act[cur_ch] = cur_act.index
                    if cur_ch not in cur_act.chapters:
                        cur_act.chapters.append(cur_ch)
            elif _ACT_RE.match(head):
                cur_act = Act(index=len(info.acts), title=head)
                info.acts.append(cur_act)
                mode = "act"
                cur_ch = None
            elif _THREADS_SECTION_RE.match(head):
                mode = "threads"
                cur_ch = None
            else:
                mode = None
                cur_ch = None
            continue
        if mode == "act":
            if line.strip() == "---":
                continue
            intro_buf.append(line.strip())
        elif mode == "chapter" and cur_ch is not None:
            m = _OUTLINE_FIELD_RE.match(line.strip())
            if m:
                if m.group(1) == "story_time":
                    info.chapter_story_time[cur_ch] = m.group(2).strip().strip("'\"")
                else:
                    info.chapter_events[cur_ch] = _parse_id_list(m.group(2))
        elif mode == "threads":
            ledger_lines.append(line)
    if mode == "act":
        close_act_intro()
    info.ledger_threads = _parse_outline_ledger(ledger_lines)
    return info


def _parse_outline_ledger(lines: list[str]) -> list[Thread]:
    threads: list[Thread] = []
    cur: Thread | None = None

    def get(name: str) -> Thread:
        for t in threads:
            if t.name == name:
                return t
        t = Thread(name=name)
        threads.append(t)
        return t

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if h3 := _H3_RE.match(line):
            name = re.sub(r"^thread\s*:\s*", "", h3.group(1), flags=re.IGNORECASE).strip()
            cur = get(name) if name else None
            continue
        if m := _FORESHADOW_RE.match(line):
            t = get(m.group(3).strip())
            t.touches.append(Touch(int(m.group(1)), "plant", ""))
            t.touches.append(Touch(int(m.group(2)), "payoff", ""))
            continue
        if cur is None:
            continue
        if m := _LEGACY_ROLE_RE.match(line):
            cur.touches.append(Touch(int(m.group(2)), m.group(1).lower(), m.group(3).strip()))
        elif m := _TOUCH_RE.match(line):
            cur.touches.append(Touch(int(m.group(1)), (m.group(2) or "touch").lower(),
                                     (m.group(3) or "").strip()))
        elif m := _LEGACY_KEY_RE.match(line):
            key = m.group(1).lower()
            if key in ("description", "question"):
                cur.question = m.group(2).strip()
            else:
                cur.consequence = m.group(2).strip()
    for t in threads:
        t.touches.sort(key=lambda x: x.chapter)
    return [t for t in threads if t.touches]


# --------------------------------------------------------- events.md

_EVENT_H2_RE = re.compile(r"^##\s+([A-Za-z]+-[\w-]+)\s*:\s*(.+?)\s*$")
_RENDERED_RE = re.compile(r"^\s*-?\s*([\w.-]+)/ch[_ ]?(\d+)\s*:\s*(.+?)\s*$")


def parse_events_md(text: str) -> dict[str, dict]:
    """`{event_id: {"title": str, "rendered": {(book, chapter): note}}}`
    from `shared/events.md` (`## E-001: <title>` blocks with
    `rendered_in:` lines `<book>/ch_NN: <note>`)."""
    out: dict[str, dict] = {}
    cur: dict | None = None
    for raw in _blank_comments(text).splitlines():
        if m := _EVENT_H2_RE.match(raw.strip()):
            cur = {"title": m.group(2).strip(), "rendered": {}}
            out[m.group(1)] = cur
            continue
        if raw.startswith("## "):
            cur = None
            continue
        if cur is not None and (m := _RENDERED_RE.match(raw)):
            cur["rendered"][(m.group(1), int(m.group(2)))] = m.group(3).strip()
    return out


# --------------------------------------------------------- story time

_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"), 1)}
_ISO_RE = re.compile(r"(?<![\d-])(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?(?![\d])")
_MONTH_NAME_RE = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", re.IGNORECASE)


def _story_time_head(s: str) -> str:
    """The date part of a story_time string — before the first sentence
    break, without parentheticals (summaries often append clock notes)."""
    s = re.sub(r"\([^)]*\)", "", s or "")
    return re.split(r"\.\s+|\.$", s.strip(), maxsplit=1)[0].strip()


def parse_story_time(s: str) -> tuple[str, str, float, float] | None:
    """`(start, end, t0, t1)` for a story_time such as `1477-09`,
    `1474-06 to 1474-08`, `1477-09-01 to 1477-11-17`, `1474-12-01 to
    January 1475`. Years are fractional (`t0` is the start of the first
    date's period, `t1` the end of the last date's). None if no date."""
    head = _story_time_head(s)
    points: list[tuple[int, tuple[int, int | None, int | None], str]] = []
    for m in _ISO_RE.finditer(head):
        y = int(m.group(1))
        mo = int(m.group(2)) if m.group(2) else None
        d = int(m.group(3)) if m.group(3) else None
        if mo is not None and not 1 <= mo <= 12:
            continue
        if d is not None and not 1 <= d <= 31:
            d = None
        points.append((m.start(), (y, mo, d), m.group(0)))
    for m in _MONTH_NAME_RE.finditer(head):
        y, mo = int(m.group(2)), _MONTHS[m.group(1).lower()]
        # Drop the bare-year ISO match this month-name date contains.
        points = [p for p in points if not (p[2] == m.group(2)
                                            and m.start() <= p[0] <= m.end())]
        points.append((m.start(), (y, mo, None), f"{y:04d}-{mo:02d}"))
    if not points:
        return None
    points.sort(key=lambda p: p[0])
    first, last = points[0][1], points[-1][1]
    t0, t1 = _frac(first, end=False), _frac(last, end=True)
    if t1 < t0:  # "to" range written backwards, or a single odd value
        t1 = _frac(first, end=True)
    return (_iso(first), _iso(last), t0, t1)


def _frac(p: tuple[int, int | None, int | None], *, end: bool) -> float:
    y, mo, d = p
    if mo is None:
        return y + (1.0 if end else 0.0)
    if d is None:
        return y + (mo - 1 + (1 if end else 0)) / 12.0
    return y + (mo - 1) / 12.0 + (d - 1 + (1 if end else 0)) / 365.25


def _iso(p: tuple[int, int | None, int | None]) -> str:
    y, mo, d = p
    if mo is None:
        return f"{y:04d}"
    if d is None:
        return f"{y:04d}-{mo:02d}"
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _fmt_years(y: float) -> str:
    y = abs(y)
    if y < 1.0:
        months = max(1, round(y * 12))
        return f"{months} month{'s' if months != 1 else ''}"
    return f"{y:.1f} years" if y < 10 else f"{y:.0f} years"


# --------------------------------------------------------- cast + places


def _clean_name(entry: str) -> str:
    names = _parse_cast(entry)
    name = names[0] if names else entry
    name = re.sub(r"\s*\([^)]*\)?", "", name)
    return name.strip(" .;:*_").strip()


def _split_cast(text: str) -> list[CastEntry]:
    out: list[CastEntry] = []
    for chunk in (text or "").split(";"):
        raw = chunk.strip().rstrip(".").strip()
        if not raw:
            continue
        name = _clean_name(raw)
        if name:
            out.append(CastEntry(raw=raw, name=name))
    return out


def _name_variants(name: str) -> list[str]:
    main = re.sub(r"\s*\([^)]*\)", "", name).strip()
    paren = re.findall(r"\(([^)]*)\)", name)
    return [v for v in [main, *[p.strip() for p in paren]] if v]


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[\s/]+", name)
            if len(t) >= 3 and t[0].isupper()]


def _location_heads(text: str) -> list[str]:
    """Primary place of each segment of a summary `Location:` line —
    `Venice / Fondaco (…)` → `Venice`, `Augsburg: counting-room` →
    `Augsburg`; segments split on ` + `, `;` and sentence breaks. Long
    descriptive phrases (> 3 words) and someone's room (`Jakob's …`) are
    skipped. A `## Places` section in threads.md replaces this list."""
    t = re.sub(r"\([^)]*\)", "", text or "")
    heads: list[str] = []
    for seg in re.split(r"\s+\+\s+|;\s*|\.\s+(?=[A-Z])", t):
        seg = seg.strip().rstrip(".").strip()
        head = re.split(r"\s+/\s+|:|,", seg, maxsplit=1)[0].strip()
        head = re.sub(r"^(?:the)\s+", "", head, flags=re.IGNORECASE)
        if not head or not head[0].isupper():
            continue
        if len(head.split()) > 3 or re.match(r"^\S+'s\b", head):
            continue
        heads.append(head)
    return heads


def _mentions(text: str, names: list[str]) -> bool:
    for n in names:
        if n and re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text or "", re.IGNORECASE):
            return True
    return False


# --------------------------------------------------------- build


def _series_root_for(book_root: Path) -> Path:
    return book_root.parent.parent


def _book_title(series_root: Path, book: str) -> str:
    try:
        from .. import project as project_mod
        cfg = project_mod.load(series_root / "project.yaml")
        for b in cfg.books:
            if b.name == book:
                return b.display_title(fallback=book)
    except Exception:  # noqa: BLE001 — a missing/odd project.yaml is not fatal here
        pass
    return book


def build_story_map(book_root: Path, *, series_root: Path | None = None) -> StoryMap:
    """Read everything the story map needs and return the model. Pure
    I/O; tolerant of every missing input (no summaries, no eval logs, no
    outline, no characters.md, no threads)."""
    book_root = Path(book_root)
    series_root = Path(series_root) if series_root else _series_root_for(book_root)
    book = book_root.name
    warnings: list[str] = []
    sources: dict[str, str] = {}

    rows = {r.chapter: r for r in summarize_chapters(book_root)}
    titles = {r.chapter: r.title for r in inspect_titles(book_root).rows if r.title}

    outline_path = book_root / "outline.md"
    outline = (parse_outline(outline_path.read_text(encoding="utf-8"))
               if outline_path.is_file() else OutlineInfo())
    sources["acts"] = (f"outline.md ({len(outline.acts)} act headers)"
                       if outline.acts else "none (no `## Act …` / `## Part …` headers in outline.md)")

    # ---- chapters
    chapters: list[MapChapter] = []
    chapters_dir = book_root / "chapters"
    for ch_path in iter_chapter_files(chapters_dir):
        try:
            n = int(ch_path.stem.split("_")[-1])
        except ValueError:
            continue
        row = rows.get(n)
        fm = _parse_frontmatter(ch_path.read_text(encoding="utf-8"))
        mc = MapChapter(chapter=n, path=str(ch_path))
        mc.title = titles.get(n) or outline.chapter_titles.get(n, "")
        mc.pov = fm.get("pov", "") or ""
        summary_path = chapters_dir / f"{ch_path.stem}.summary.md"
        sections: dict[str, str] = {}
        if summary_path.is_file():
            mc.has_summary = True
            sections = parse_summary_sections(summary_path.read_text(encoding="utf-8"))
        mc.plot = sections.get("plot", "")
        mc.pov_state = sections.get("pov state", "")
        mc.location = sections.get("location", "")
        mc.threads_opened = sections.get("threads opened", "")
        mc.threads_closed = sections.get("threads closed", "")
        mc.cast = _split_cast(sections.get("cast on stage", ""))
        if row is not None:
            mc.score = row.score
            mc.word_count = row.word_count
            mc.plot_line = row.plot or ""
            mc.summary_stale = row.summary_stale
        fm_time = fm.get("story_time", "") or ""
        mc.story_time = fm_time or _story_time_head(sections.get("story time", "")) \
            or outline.chapter_story_time.get(n, "")
        parsed = (parse_story_time(fm_time) if fm_time else None) \
            or parse_story_time(sections.get("story time", "")) \
            or parse_story_time(outline.chapter_story_time.get(n, ""))
        if parsed:
            mc.start, mc.end, mc.t0, mc.t1 = parsed
        mc.act = outline.chapter_act.get(n)
        if not mc.has_summary:
            warnings.append(f"ch {n}: no summary on disk — run "
                            f"/autonovel:summarize-chapter {n} --book {book}")
        elif mc.summary_stale:
            warnings.append(f"ch {n}: chapter is newer than its summary — run "
                            f"/autonovel:summarize-chapter --stale --book {book}")
        chapters.append(mc)
    chapters.sort(key=lambda c: c.chapter)

    prev: MapChapter | None = None
    for c in chapters:
        if c.t0 is None:
            continue
        if prev is not None:
            c.gap_before = c.t0 - prev.t1
            c.backwards = c.t0 < prev.t0
        prev = c

    acts = [a for a in outline.acts]
    for a in acts:
        a.chapters = [n for n in a.chapters if any(c.chapter == n for c in chapters)] \
            or a.chapters

    # ---- ledger + threads
    ledger_path = book_root / "threads.md"
    ledger = (parse_threads_ledger(ledger_path.read_text(encoding="utf-8"))
              if ledger_path.is_file() else Ledger())
    warnings.extend(ledger.warnings)
    events_path = series_root / "shared" / "events.md"
    events = (parse_events_md(events_path.read_text(encoding="utf-8"))
              if events_path.is_file() else {})

    if ledger.threads:
        threads, thread_source = ledger.threads, "threads.md"
    elif outline.ledger_threads:
        threads, thread_source = outline.ledger_threads, "outline.md ## Threads"
    else:
        threads = _threads_from_events(book, chapters, outline, events, chapters_dir)
        thread_source = "outline events" if threads else "none"
    drafted = {c.chapter for c in chapters}
    if drafted:
        for t in threads:
            missing = sorted({x.chapter for x in t.touches} - drafted)
            if missing:
                warnings.append(f"thread “{t.name}” touches ch "
                                f"{', '.join(map(str, missing))}, which has no chapter file yet")
    sources["threads"] = {
        "threads.md": f"books/{book}/threads.md",
        "outline.md ## Threads": f"books/{book}/outline.md — `## Threads` ledger",
        "outline events": "outline.md / chapter frontmatter `events:` ids "
                          "(titles + notes from shared/events.md)",
        "none": "none — no threads.md, no outline `## Threads` ledger, no events: ids",
    }[thread_source]

    # ---- characters
    principals, absent = _build_principals(chapters, ledger, series_root)
    sources["characters"] = ("threads.md `## Character:` sections, "
                             "shared/characters.md, summary Cast lines")

    # ---- places
    places, place_source = _build_places(chapters, ledger)

    # ---- escalation (reuse the dashboard's series)
    series, series_sources = _escalation_series(book_root, chapters)

    return StoryMap(
        book=book,
        title=_book_title(series_root, book),
        chapters=chapters,
        acts=acts,
        threads=threads,
        thread_source=thread_source,
        principals=principals,
        absent_principals=absent,
        places=places,
        place_source=place_source,
        series=series,
        series_sources=series_sources,
        warnings=warnings,
        sources=sources,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        book_root=book_root,
    )


def _threads_from_events(book: str, chapters: list[MapChapter], outline: OutlineInfo,
                         events: dict[str, dict], chapters_dir: Path) -> list[Thread]:
    per_ch: dict[int, list[str]] = {n: list(ids) for n, ids in outline.chapter_events.items()}
    for c in chapters:
        fm = _parse_frontmatter(Path(c.path).read_text(encoding="utf-8"))
        for eid in _parse_id_list(fm.get("events", "") or ""):
            if eid not in per_ch.setdefault(c.chapter, []):
                per_ch[c.chapter].append(eid)
    by_id: dict[str, Thread] = {}
    for n in sorted(per_ch):
        for eid in per_ch[n]:
            ev = events.get(eid, {})
            name = f"{eid} · {ev['title']}" if ev.get("title") else eid
            t = by_id.setdefault(eid, Thread(name=name))
            note = ev.get("rendered", {}).get((book, n), "")
            t.touches.append(Touch(chapter=n, role="touch", note=note))
    return list(by_id.values())


def _build_principals(chapters: list[MapChapter], ledger: Ledger,
                      series_root: Path) -> tuple[list[Principal], list[str]]:
    listed: list[Principal] = []
    for name in parse_cast_ordered(series_root / "shared" / "characters.md"):
        # `**Role:** …` / `**Want:** …` field labels inside an entry are
        # not names.
        if name.endswith(":"):
            continue
        listed.append(Principal(name=name, source="characters.md"))
    # Token aliases: a name token unique to one listed principal.
    token_count: dict[str, int] = {}
    for p in listed:
        toks = {t.lower() for v in _name_variants(p.name) for t in _tokens(v)}
        p._tokens = toks
        p._keys = {v.lower() for v in _name_variants(p.name)}
        for t in toks:
            token_count[t] = token_count.get(t, 0) + 1
    for p in listed:
        p._token_aliases = {t for t in p._tokens if token_count.get(t) == 1}

    def match(name: str, pool: list[Principal]) -> Principal | None:
        key = name.lower().strip()
        if not key:
            return None
        hits = [p for p in pool if key in p._keys]
        if len(hits) == 1:
            return hits[0]
        if hits:
            return None
        toks = {t.lower() for t in _tokens(name)}
        if len(name.split()) > 1 and toks:
            hits = [p for p in pool if toks <= p._tokens]
            return hits[0] if len(hits) == 1 else None
        hits = [p for p in pool if key in p._token_aliases]
        return hits[0] if len(hits) == 1 else None

    principals: list[Principal] = []
    for arc in ledger.characters:
        target = match(arc.name, listed)
        if target is None:
            target = Principal(name=arc.name, source="threads.md")
            target._keys = {v.lower() for v in _name_variants(arc.name)}
            target._tokens = {t.lower() for v in _name_variants(arc.name) for t in _tokens(v)}
        else:
            listed.remove(target)
            target.source = "threads.md + characters.md"
        target._ledger = arc
        target.arc = arc.arc
        target.aliases = list(arc.aliases)
        target._keys |= {a.lower() for a in arc.aliases}
        if target not in principals:
            principals.append(target)
    pool = principals + listed
    # Recompute token aliases over the merged pool so threads.md-only
    # principals ("Hans Prantl") also answer to a unique token ("Prantl").
    token_count = {}
    for p in pool:
        for t in p._tokens:
            token_count[t] = token_count.get(t, 0) + 1
    for p in pool:
        p._token_aliases = {t for t in p._tokens if token_count.get(t) == 1}

    unmatched: dict[str, tuple[str, set[int]]] = {}
    for c in chapters:
        pov_p = match(c.pov, pool) if c.pov else None
        seen: set[int] = set()
        for entry in c.cast:
            p = match(entry.name, pool)
            if p is None:
                if entry.name[:1].isupper():
                    k = entry.name.lower()
                    disp, chs = unmatched.get(k, (entry.name, set()))
                    chs.add(c.chapter)
                    unmatched[k] = (disp, chs)
                continue
            if id(p) in seen:
                continue
            seen.add(id(p))
            p.appearances.append(Appearance(
                chapter=c.chapter,
                as_pov=(p is pov_p) or "pov" in entry.raw.lower(),
                cast_entry=entry.raw,
            ))
        if pov_p is not None and id(pov_p) not in seen:
            seen.add(id(pov_p))
            pov_p.appearances.append(Appearance(chapter=c.chapter, as_pov=True,
                                                cast_entry=f"{c.pov} (POV)"))
        elif pov_p is None and c.pov[:1].isupper() \
                and not any("pov" in e.raw.lower() for e in c.cast):
            # An unlisted POV character counts like an unlisted cast name
            # (unless the cast line already marks someone as the POV).
            k = c.pov.lower()
            disp, chs = unmatched.get(k, (c.pov, set()))
            chs.add(c.chapter)
            unmatched[k] = (disp, chs)

    for k, (disp, chs) in sorted(unmatched.items(), key=lambda kv: (-len(kv[1][1]), kv[0])):
        if len(chs) < SUMMARY_CAST_MIN:
            continue
        p = Principal(name=disp, source="summary cast / chapter POV")
        for c in chapters:
            if c.chapter not in chs:
                continue
            entry = next((e for e in c.cast if e.name.lower() == k), None)
            is_pov = c.pov.lower() == k
            p.appearances.append(Appearance(
                chapter=c.chapter,
                as_pov=is_pov or bool(entry and "pov" in entry.raw.lower()),
                cast_entry=entry.raw if entry else (f"{disp} (POV)" if is_pov else disp)))
        p._keys = {k}
        pool.append(p)

    by_ch = {c.chapter: c for c in chapters}
    # Whose end-of-chapter "POV state" is it? The principal the frontmatter
    # `pov` names; failing that, the one principal flagged POV in the cast.
    pov_owner: dict[int, Principal] = {}
    for c in chapters:
        owner = match(c.pov, pool) if c.pov else None
        if owner is None:
            flagged = [p for p in pool
                       if any(a.chapter == c.chapter and a.as_pov for a in p.appearances)]
            owner = flagged[0] if len(flagged) == 1 else None
        if owner is not None:
            pov_owner[c.chapter] = owner
    for p in pool:
        arc = p._ledger
        if arc is not None:
            have = {a.chapter for a in p.appearances}
            for ch in arc.states:
                if ch not in have:
                    p.appearances.append(Appearance(chapter=ch))
        p.appearances.sort(key=lambda a: a.chapter)
        for a in p.appearances:
            c = by_ch.get(a.chapter)
            if c is not None:
                a.line = c.plot_line or c.plot[:180]
            if arc is not None and arc.states.get(a.chapter):
                a.state = " / ".join(arc.states[a.chapter])
                a.state_source = "threads.md"
            elif c is not None and c.pov_state and pov_owner.get(a.chapter) is p:
                a.state = c.pov_state
                a.state_source = "summary POV state"

    shown = [p for p in pool if p.appearances or p._ledger is not None]
    absent = [p.name for p in pool if not p.appearances and p._ledger is None]
    return shown, absent


def _build_places(chapters: list[MapChapter], ledger: Ledger) -> tuple[list[Place], str]:
    if ledger.has_places and ledger.places:
        places = [Place(name=n, aliases=list(a)) for n, a in ledger.places]
        source = "threads.md `## Places`"
    else:
        heads: list[str] = []
        for c in chapters:
            for h in _location_heads(c.location):
                if h.lower() not in (x.lower() for x in heads):
                    heads.append(h)
        heads = [h for h in heads
                 if not any(h.lower().startswith(g.lower() + " ") for g in heads if g != h)]
        places = [Place(name=h) for h in heads]
        source = ("summary `Location:` lines (add a `## Places` section to "
                  "threads.md to set the list)") if places else "none"
    for p in places:
        names = [p.name, *p.aliases]
        for c in chapters:
            if _mentions(c.location, names):
                p.visited.append(c.chapter)
            elif _mentions(c.plot, names):
                p.named_only.append(c.chapter)
    places = [p for p in places if p.visited or p.named_only]
    places.sort(key=lambda p: (min(p.visited + p.named_only), p.name))
    return places, source


def _escalation_series(book_root: Path, chapters: list[MapChapter]
                       ) -> tuple[dict[str, list[float | None]], dict[str, str]]:
    report = build_dashboard(book_root)
    by_ch = {r.chapter: r for r in report.rows}
    eval_dir = book_root / "eval_logs"
    per_ch_tension = _index_latest_per_chapter_eval(eval_dir, key="tension")
    per_ch_irc = _index_latest_per_chapter_eval(eval_dir, key="dimensions.irreversible_change")
    series: dict[str, list[float | None]] = {"score": [], "tension": [],
                                             "irreversible_change": []}
    used: dict[str, set[str]] = {k: set() for k in series}
    for c in chapters:
        r = by_ch.get(c.chapter)
        score = r.score if r else None
        series["score"].append(score)
        if score is not None:
            used["score"].add("latest per-chapter eval log")
        for key, fallback in (("tension", per_ch_tension),
                              ("irreversible_change", per_ch_irc)):
            v = getattr(r, key, None) if r else None
            if v is not None:
                used[key].add("latest --full eval log")
            elif c.chapter in fallback:
                v = fallback[c.chapter]
                used[key].add("latest per-chapter eval log")
            series[key].append(v)
    srcs = {k: ("; ".join(sorted(v)) if v else "none") for k, v in used.items()}
    return series, srcs


# --------------------------------------------------------- text grid


def render_grid_text(sm: StoryMap, *, label_width: int = 28) -> str:
    """Compact terminal view of the thread grid: threads as rows,
    chapters as one-character columns."""
    cols = sm.columns
    if not sm.threads:
        return ("(no plot threads yet — run /autonovel:story-map --refresh-threads "
                f"--book {sm.book} to write books/{sm.book}/threads.md)\n")
    lines = [f"Threads × chapters ({sm.thread_source}) — "
             "P plant · T turn · X payoff · o touch · . none"]
    pad = " " * (label_width + 1)
    if cols and max(cols) >= 10:
        lines.append(pad + "".join(str(c // 10) if c >= 10 else " " for c in cols))
    lines.append(pad + "".join(str(c % 10) for c in cols))
    for t in sm.threads:
        label = t.name if len(t.name) <= label_width else t.name[: label_width - 1] + "…"
        cells = "".join(_ROLE_TEXT_GLYPH.get(t.cell_role(c) or "", ".") for c in cols)
        lines.append(f"{label:<{label_width}} {cells}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------- HTML

_CW = 28          # px per chapter column (grid + escalation charts share it)
_CHART_H = 76


def _e(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _inline_md(text: str) -> str:
    """Escape, then render the little markdown summaries use."""
    s = _e(text)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def _paras(text: str) -> str:
    return "".join(f"<p>{_inline_md(p.strip())}</p>"
                   for p in re.split(r"\n\s*\n", text or "") if p.strip())


def _rel_link(target: str, out_dir: Path | None) -> str:
    if not target:
        return ""
    p = Path(target)
    if out_dir is not None:
        try:
            return Path(os.path.relpath(p.resolve(), out_dir.resolve())).as_posix()
        except ValueError:
            pass
    return p.resolve().as_uri()


def _chart_svg(values: list[float | None], label: str, cols: list[int]) -> str:
    """One escalation row: a line chart whose point i sits at the centre
    of grid column i, so it lines up with the thread cells above it."""
    n = len(values)
    w = max(1, n) * _CW
    nums = [v for v in values if v is not None]
    if not nums:
        return ""
    lo = max(0.0, math.floor(min(nums)) - 1.0)
    hi = 10.0 if max(nums) <= 10 else math.ceil(max(nums))
    if hi - lo < 1:
        hi = lo + 1
    pad = 8

    def y(v: float) -> float:
        return pad + (hi - v) / (hi - lo) * (_CHART_H - 2 * pad)

    parts = [f'<svg class="chart" width="{w}" height="{_CHART_H}" viewBox="0 0 {w} {_CHART_H}" '
             f'role="img" aria-label="{_e(label)} by chapter">']
    for g in range(int(math.ceil(lo)), int(hi) + 1):
        parts.append(f'<line class="gl" x1="0" x2="{w}" y1="{y(g):.1f}" y2="{y(g):.1f}"/>')
    seg: list[str] = []
    paths: list[str] = []
    for i, v in enumerate(values):
        if v is None:
            if len(seg) > 1:
                paths.append(" ".join(seg))
            seg = []
            continue
        seg.append(f"{'M' if not seg else 'L'}{(i + .5) * _CW:.1f},{y(v):.1f}")
    if len(seg) > 1:
        paths.append(" ".join(seg))
    for d in paths:
        parts.append(f'<path class="ln" d="{d}"/>')
    for i, v in enumerate(values):
        if v is None:
            continue
        parts.append(f'<circle class="pt" cx="{(i + .5) * _CW:.1f}" cy="{y(v):.1f}" r="3.2">'
                     f'<title>{_e(label)} · ch {cols[i]}: {v:g}</title></circle>')
    parts.append("</svg>")
    return "".join(parts)


def _thread_meta(t: Thread) -> str:
    """Counts only: how many chapters touch the thread, its first and
    last chapter, and the longest run of chapters with no touch."""
    chs = t.chapters
    meta = f"{len(chs)} chapter{'s' if len(chs) != 1 else ''}"
    if len(chs) == 1:
        meta += f" · ch {chs[0]}"
    elif chs:
        meta += f" · ch {chs[0]}–{chs[-1]}"
    gap = t.longest_gap()
    if gap:
        meta += f" · longest gap {gap[0]} (ch {gap[1]}→{gap[2]})"
    return meta


def _grid_head(sm: StoryMap, cols: list[int], first_label: str) -> str:
    by_ch = {c.chapter: c for c in sm.chapters}
    out = [f'<colgroup><col class="lab-col">' + f'<col class="c-col">' * len(cols) + "</colgroup>",
           "<thead>"]
    if sm.acts:
        out.append('<tr class="actrow"><th class="lab"></th>')
        run_act, run_len = None, 0
        cells: list[str] = []
        for c in cols:
            a = by_ch[c].act if c in by_ch else None
            if a == run_act:
                run_len += 1
                continue
            if run_len:
                cells.append(_act_cell(sm, run_act, run_len))
            run_act, run_len = a, 1
        if run_len:
            cells.append(_act_cell(sm, run_act, run_len))
        out.append("".join(cells) + "</tr>")
    out.append(f'<tr><th class="lab">{_e(first_label)}</th>')
    for c in cols:
        mc = by_ch.get(c)
        tip = f"ch {c}" + (f" — {mc.title}" if mc and mc.title else "") + \
              (f" · {mc.story_time}" if mc and mc.story_time else "")
        cls = "chh" if mc else "chh undrafted"
        out.append(f'<th class="{cls}" scope="col"><a href="#ch-{c}" title="{_e(tip)}">{c}</a></th>')
    out.append("</tr></thead>")
    return "".join(out)


def _act_cell(sm: StoryMap, act: int | None, span: int) -> str:
    if act is None or act >= len(sm.acts):
        return f'<td class="act none" colspan="{span}"></td>'
    a = sm.acts[act]
    return (f'<td class="act a{act % 2}" colspan="{span}" title="{_e(a.title)}">'
            f'<span>{_e(a.short)}</span></td>')


def _escalation_rows(sm: StoryMap, cols: list[int]) -> str:
    idx = {c.chapter: i for i, c in enumerate(sm.chapters)}
    labels = {"score": "Score", "tension": "Tension",
              "irreversible_change": "Irreversible change"}
    rows = []
    for key, label in labels.items():
        vals_by_ch = sm.series.get(key, [])
        vals = [vals_by_ch[idx[c]] if c in idx and idx[c] < len(vals_by_ch) else None
                for c in cols]
        nums = [v for v in vals if v is not None]
        if not nums:
            continue
        svg = _chart_svg(vals, label, cols)
        rng = f"{min(nums):g}–{max(nums):g}"
        rows.append(f'<tr class="esc"><th class="lab">{_e(label)}'
                    f'<span class="meta">{_e(rng)} · {_e(sm.series_sources.get(key, ""))}</span></th>'
                    f'<td class="chart-cell" colspan="{len(cols)}">{svg}</td></tr>')
    return "".join(rows)


_CSS = """
:root{--bg:#f8f6f1;--fg:#1f1d1a;--muted:#6e675d;--line:#e2ddd2;--card:#fffdf9;
--accent:#8a3b12;--plant:#2f6db5;--turn:#b07a10;--payoff:#2e7d3e;--touch:#8b8478;
--present:#c9c2b5;--a0:#efe9dd;--a1:#e4ecef;--chart:#8a3b12;--warn:#9a5b00;
--cw:28px;--labw:15rem}
@media (prefers-color-scheme:dark){:root{--bg:#151412;--fg:#ebe6dd;--muted:#a39b8e;
--line:#34302a;--card:#1d1b18;--accent:#e08a5a;--plant:#6aa7ec;--turn:#e0b04a;
--payoff:#6cc27e;--touch:#8f887c;--present:#4a453d;--a0:#25221d;--a1:#1e2629;
--chart:#e08a5a;--warn:#e0a64a}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 Georgia,"Iowan Old Style","Palatino Linotype",serif}
a{color:var(--accent)}
.wrap{max-width:72rem;margin:0 auto;padding:0 16px}
header.top{background:var(--card)}
.tabbar{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line)}
.eyebrow{margin:.8rem 0 0;font:600 .75rem/1.2 system-ui,sans-serif;letter-spacing:.08em;
text-transform:uppercase;color:var(--muted)}
h1{margin:.15rem 0 .2rem;font-size:1.7rem;line-height:1.2}
.facts{margin:0 0 .5rem;color:var(--muted);font:.85rem/1.4 system-ui,sans-serif}
nav.tabs{display:flex;gap:.25rem;overflow-x:auto;max-width:72rem;margin:0 auto;padding:0 16px}
nav.tabs a{font:600 .9rem/1 system-ui,sans-serif;padding:.65rem .8rem;text-decoration:none;
color:var(--muted);border-bottom:3px solid transparent;white-space:nowrap}
nav.tabs a.on{color:var(--fg);border-bottom-color:var(--accent)}
main{padding:1rem 0 3rem}
.js .panel{display:none}.js .panel.on{display:block}
.panel>h2:first-child{margin-top:.5rem}
h2{font-size:1.35rem;margin:2rem 0 .6rem}
h3{font-size:1.08rem;margin:1.4rem 0 .2rem}
.note{color:var(--muted);font:.85rem/1.45 system-ui,sans-serif}
.warn{color:var(--warn)}
.synopsis{max-width:42rem}
.synopsis .act-h{border-top:2px solid var(--line);padding-top:1rem}
.synopsis details{font-size:.92rem;color:var(--muted);margin:.2rem 0 1rem}
.synopsis summary{cursor:pointer;font:.8rem/1.4 system-ui,sans-serif}
.chap h3 .num{color:var(--muted);font-weight:normal;margin-right:.35rem}
.meta{display:block;color:var(--muted);font:.78rem/1.4 system-ui,sans-serif}
.chap .meta{margin-bottom:.35rem}
.chap p{margin:.2rem 0 .5rem}
.chap .state{font-style:italic;color:var(--muted)}
.chap,.panel,.who,.act-h{scroll-margin-top:3.6rem}
.modes{display:none;gap:.4rem;margin:.2rem 0 1rem}.js .modes{display:flex;flex-wrap:wrap}
.modes button{font:600 .8rem/1 system-ui,sans-serif;padding:.45rem .7rem;border-radius:999px;
border:1px solid var(--line);background:var(--card);color:var(--muted);cursor:pointer}
.modes button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.skimline{display:none}
.synopsis.skim .plot,.synopsis.skim details{display:none}
.synopsis.skim .skimline{display:block}
.synopsis.skim .chap h3{margin-top:.8rem}
.gridwrap{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--card);
margin:.6rem 0}
table.grid{border-collapse:collapse;table-layout:fixed;font:13px/1.2 system-ui,sans-serif}
.grid col.lab-col{width:var(--labw)}.grid col.c-col{width:var(--cw)}
.grid th,.grid td{padding:0;border-bottom:1px solid var(--line)}
.grid th.lab{position:sticky;left:0;z-index:2;background:var(--card);text-align:left;
padding:.3rem .5rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;
border-right:1px solid var(--line);white-space:normal}
.grid th.lab .meta{font-weight:normal}
.grid th.chh{height:1.8rem;text-align:center;font-weight:600}
.grid th.chh a{text-decoration:none;display:block}
.grid th.undrafted a{color:var(--muted);font-weight:normal}
.grid td.act{font-size:11px;color:var(--muted);text-align:center;white-space:nowrap;
overflow:hidden;height:1.3rem}
.grid td.act.a0{background:var(--a0)}.grid td.act.a1{background:var(--a1)}
.grid td.c{text-align:center;height:1.9rem;cursor:default;border-left:1px solid var(--line)}
.grid td.c.f{cursor:pointer;color:#fff;font-weight:700}
.grid td.c.plant{background:var(--plant)}.grid td.c.turn{background:var(--turn)}
.grid td.c.payoff{background:var(--payoff)}.grid td.c.touch{color:var(--fg);background:var(--present)}
.grid td.c.present{background:var(--present);color:var(--fg)}
.grid td.c.pov{background:var(--accent);color:#fff}
.grid td.c.sel{outline:3px solid var(--fg);outline-offset:-3px}
.grid tr.esc th.lab{font-weight:600}
.grid td.chart-cell{padding:0;vertical-align:middle}
svg.chart{display:block}
svg .gl{stroke:var(--line);stroke-width:1}
svg .ln{fill:none;stroke:var(--chart);stroke-width:2}
svg .pt{fill:var(--chart)}
.legend{display:flex;flex-wrap:wrap;gap:.4rem .9rem;font:.8rem/1.4 system-ui,sans-serif;color:var(--muted);margin:.4rem 0}
.legend b{display:inline-block;width:1.2rem;text-align:center;color:#fff;border-radius:3px;margin-right:.25rem}
.lg-plant{background:var(--plant)}.lg-turn{background:var(--turn)}
.lg-payoff{background:var(--payoff)}.lg-touch{background:var(--present);color:var(--fg)!important}
.lg-pov{background:var(--accent)}
.detail{min-height:2.6rem;padding:.6rem .8rem;border-left:4px solid var(--accent);
background:var(--card);font:.9rem/1.45 system-ui,sans-serif;margin:.4rem 0 1rem}
.tlist{padding-left:1.1rem}.tlist li{margin:.15rem 0}
.role{font:600 .72rem/1 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.04em;
padding:.12rem .3rem;border-radius:3px;color:#fff;margin-right:.3rem}
.role.plant{background:var(--plant)}.role.turn{background:var(--turn)}
.role.payoff{background:var(--payoff)}.role.touch{background:var(--touch)}
table.data{border-collapse:collapse;width:100%;font:.85rem/1.4 system-ui,sans-serif;margin:.5rem 0 1rem}
table.data th,table.data td{border-bottom:1px solid var(--line);padding:.35rem .4rem;text-align:left;vertical-align:top}
table.data th{color:var(--muted);font-weight:600}
.tablewrap{overflow-x:auto}
.who{border-top:1px solid var(--line);padding:.3rem 0}
.who summary{cursor:pointer;font-weight:600;padding:.3rem 0}
.who summary .meta{display:inline;margin-left:.4rem}
.apps{list-style:none;padding:0;margin:.3rem 0 .8rem}
.apps li{padding:.35rem 0;border-bottom:1px dashed var(--line)}
.apps .st{display:block}.apps .ln2{display:block;color:var(--muted);font-size:.9rem}
.tag{font:600 .7rem/1 system-ui,sans-serif;background:var(--accent);color:#fff;border-radius:3px;padding:.1rem .3rem;margin-left:.3rem}
.timewrap{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--card);margin:.6rem 0}
svg.time text{font:11px system-ui,sans-serif;fill:var(--fg)}
svg.time .tick{stroke:var(--line)}
svg.time .axis{stroke:var(--muted)}
svg.time .bar{fill:var(--accent);opacity:.85}
svg.time .gap{stroke:var(--warn);stroke-width:2;fill:none}
svg.time .gapt{fill:var(--warn);font-weight:600}
.gapflag{color:var(--warn);font-weight:600}
footer{border-top:1px solid var(--line);padding:1rem 0 2rem}
@media (max-width:640px){:root{--labw:8.5rem}h1{font-size:1.35rem}body{font-size:15.5px}
.grid th.lab .meta{display:none}}
"""

_JS = r"""
(function(){
document.documentElement.classList.add('js');
var tabs=[].slice.call(document.querySelectorAll('nav.tabs a'));
var panels=[].slice.call(document.querySelectorAll('.panel'));
function show(id,scrollTo){
  var panel=document.getElementById(id);
  if(!panel)return;
  if(!panel.classList.contains('panel')){panel=panel.closest('.panel');}
  if(!panel)return;
  panels.forEach(function(p){p.classList.toggle('on',p===panel);});
  tabs.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#'+panel.id);});
  var el=document.getElementById(id);
  if(scrollTo&&el&&el!==panel){el.scrollIntoView({block:'start'});}
  else if(scrollTo){window.scrollTo(0,0);}
}
function route(){var h=(location.hash||'#synopsis').slice(1);show(h,true);}
window.addEventListener('hashchange',route);
window.addEventListener('load',route);
route();
document.addEventListener('click',function(ev){
  var mb=ev.target.closest('.modes button');
  if(mb){
    var syn=document.getElementById('synopsis');
    syn.classList.toggle('skim',mb.getAttribute('data-mode')==='skim');
    [].slice.call(document.querySelectorAll('.modes button')).forEach(function(b){b.classList.toggle('on',b===mb);});
    return;
  }
  var td=ev.target.closest('td.c.f');
  if(!td)return;
  var box=document.getElementById(td.getAttribute('data-box'));
  if(!box)return;
  [].slice.call(document.querySelectorAll('td.c.sel')).forEach(function(x){x.classList.remove('sel');});
  td.classList.add('sel');
  var ch=td.getAttribute('data-ch');
  box.innerHTML='';
  var h=document.createElement('strong');h.textContent=td.getAttribute('data-row');
  box.appendChild(h);
  box.appendChild(document.createTextNode(' · '));
  var a=document.createElement('a');a.href='#ch-'+ch;
  a.textContent='ch '+ch+(td.getAttribute('data-title')?' — '+td.getAttribute('data-title'):'');
  box.appendChild(a);
  var p=document.createElement('div');p.textContent=td.getAttribute('data-note')||'(no note)';
  box.appendChild(p);
});
})();
"""


def render_html(sm: StoryMap, *, out_dir: Path | None = None) -> str:
    cols = sm.columns
    by_ch = {c.chapter: c for c in sm.chapters}
    span = sm.span
    facts = [f"{len(sm.chapters)} chapter{'s' if len(sm.chapters) != 1 else ''}",
             f"{sm.total_words:,} words"]
    if span:
        facts.append(f"story time {span[0]} → {span[1]} ({_fmt_years(span[2])})")
    if sm.synopsis_minutes:
        facts.append(f"synopsis ≈ {sm.synopsis_minutes} min read")
    facts.append(f"threads: {sm.thread_source}")

    out: list[str] = []
    out.append("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
               "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
               f"<title>Story map — {_e(sm.title)}</title><style>{_CSS}</style></head><body>")
    out.append('<header class="top"><div class="wrap">'
               f'<p class="eyebrow">Story map · {_e(sm.book)}</p><h1>{_e(sm.title)}</h1>'
               f'<p class="facts">{" · ".join(_e(f) for f in facts)}</p></div></header>'
               '<div class="tabbar"><nav class="tabs" aria-label="Story map sections">'
               '<a href="#synopsis">Synopsis</a><a href="#threads">Threads</a>'
               '<a href="#characters">Characters</a><a href="#timeline">Timeline &amp; places</a>'
               '</nav></div><main class="wrap">')

    # ---------------- synopsis
    out.append('<section id="synopsis" class="panel synopsis"><h2>Synopsis</h2>')
    if not sm.chapters:
        out.append('<p class="note">No chapters drafted yet.</p>')
    out.append(f'<p class="note">The chapter summaries in reading order '
               f'({sm.synopsis_words:,} words). Act headers come from outline.md.</p>')
    if sm.chapters:
        out.append('<div class="modes" role="group" aria-label="Synopsis length">'
                   f'<button type="button" class="on" data-mode="full">Full plot '
                   f'(≈ {sm.synopsis_minutes} min)</button>'
                   f'<button type="button" data-mode="skim">One line per chapter '
                   f'(≈ {_minutes(sm.skim_words)} min)</button></div>')
    last_act: int | None = -1
    for c in sm.chapters:
        if c.act != last_act and c.act is not None and c.act < len(sm.acts):
            a = sm.acts[c.act]
            out.append(f'<h2 class="act-h" id="act-{a.index + 1}">{_e(a.title)}</h2>')
            if a.intro:
                out.append(f'<details><summary>The outline’s note for this act</summary>'
                           f'{_paras(a.intro)}</details>')
        last_act = c.act
        meta = [x for x in (
            c.story_time,
            f"POV {c.pov}" if c.pov else "",
            f"score {c.score:.1f}" if c.score is not None else "",
            f"{c.word_count:,} words" if c.word_count else "",
        ) if x]
        link = _rel_link(c.path, out_dir)
        out.append(f'<article class="chap" id="ch-{c.chapter}"><h3><span class="num">{c.chapter}</span>'
                   f'{_e(c.title or f"Chapter {c.chapter}")}</h3>'
                   f'<span class="meta">{" · ".join(_e(m) for m in meta)}'
                   + (f' · <a href="{_e(link)}">chapter file</a>' if link else "")
                   + "</span>")
        if c.plot:
            out.append(f'<p class="plot">{_inline_md(c.plot)}</p>')
        else:
            out.append(f'<p class="note warn">No summary on disk. Run '
                       f'<code>/autonovel:summarize-chapter {c.chapter} --book {_e(sm.book)}</code>.</p>')
        if c.pov_state:
            out.append(f'<p class="state">At the close: {_inline_md(c.pov_state)}</p>')
        elif c.plot_line:
            out.append(f'<p class="skimline">{_inline_md(c.plot_line)}</p>')
        out.append("</article>")
    out.append("</section>")

    # ---------------- threads + escalation
    out.append('<section id="threads" class="panel"><h2>Threads</h2>')
    out.append(f'<p class="note">Rows are plot threads, columns are chapters. A filled cell '
               f'means the chapter touches the thread; click one to read that touch. '
               f'Source: {_e(sm.sources.get("threads", ""))}.</p>')
    out.append('<div class="legend"><span><b class="lg-plant">P</b>plant</span>'
               '<span><b class="lg-turn">T</b>turn</span><span><b class="lg-payoff">✓</b>payoff</span>'
               '<span><b class="lg-touch">•</b>touch</span></div>')
    if sm.thread_source in ("none", "outline events"):
        what = ("No thread ledger yet." if sm.thread_source == "none" else
                "These rows are the outline’s event ids, not plot threads — there is no "
                "thread ledger yet.")
        out.append(f'<p class="note warn">{what} Run '
                   f'<code>/autonovel:story-map --refresh-threads --book {_e(sm.book)}</code> '
                   f'to have one written to <code>books/{_e(sm.book)}/threads.md</code> from the '
                   f'outline and the chapter summaries. The escalation curve is under the grid; the '
                   f'summaries’ own “threads opened / closed” notes are at the bottom of this tab.</p>')
    if cols:
        out.append('<div class="gridwrap"><table class="grid">')
        out.append(_grid_head(sm, cols, "Thread"))
        out.append("<tbody>")
        for t in sm.threads:
            out.append(f'<tr><th class="lab" title="{_e(t.question)}">{_e(t.name)}'
                       f'<span class="meta">{_e(_thread_meta(t))}</span></th>')
            for c in cols:
                role = t.cell_role(c)
                if role is None:
                    out.append('<td class="c"></td>')
                    continue
                notes = " / ".join(f"{x.role}: {x.note}" if x.note else x.role
                                   for x in t.notes_for(c))
                title = by_ch[c].title if c in by_ch else ""
                out.append(f'<td class="c f {role}" data-box="thread-detail" data-row="{_e(t.name)}" '
                           f'data-ch="{c}" data-title="{_e(title)}" data-note="{_e(notes)}" '
                           f'title="{_e(f"ch {c} · {notes}")}">{_ROLE_GLYPH[role]}</td>')
            out.append("</tr>")
        out.append("</tbody><tbody>")
        out.append(_escalation_rows(sm, cols))
        out.append("</tbody></table></div>")
        out.append('<div id="thread-detail" class="detail" aria-live="polite">'
                   'Click a filled cell to read that touch.</div>')
        if not any(v is not None for vals in sm.series.values() for v in vals):
            out.append('<p class="note">No eval scores yet — run <code>/autonovel:evaluate</code> '
                       'to put the score and tension curves under the grid.</p>')
        else:
            out.append(f'<p class="note">Under the grid, on the same chapter axis: score, tension '
                       f'and irreversible change per chapter from the eval logs (rows with no data '
                       f'are omitted). Scale: lowest value rounded down to 10.</p>')

    if sm.threads:
        out.append("<h2>The threads</h2>")
        for t in sm.threads:
            out.append(f'<h3>{_e(t.name)}<span class="meta">{_e(_thread_meta(t))}</span></h3>')
            if t.question:
                out.append(f'<p class="note">{_inline_md(t.question)}</p>')
            if t.consequence:
                out.append(f'<p class="note">Consequence: {_inline_md(t.consequence)}</p>')
            out.append('<ul class="tlist">')
            for x in t.touches:
                title = by_ch[x.chapter].title if x.chapter in by_ch else ""
                out.append(f'<li><span class="role {x.role}">{x.role}</span>'
                           f'<a href="#ch-{x.chapter}">ch {x.chapter}</a>'
                           + (f" {_e(title)}" if title else "")
                           + (f" — {_inline_md(x.note)}" if x.note else "") + "</li>")
            out.append("</ul>")
    if any(c.threads_opened or c.threads_closed for c in sm.chapters):
        out.append("<h2>What each summary says it opened and closed</h2>"
                   '<p class="note">Verbatim from each chapter summary’s “Threads opened” / '
                   '“Threads closed” lines.</p><div class="tablewrap"><table class="data">'
                   "<tr><th>Ch</th><th>Opened</th><th>Closed</th></tr>")
        for c in sm.chapters:
            out.append(f'<tr><td><a href="#ch-{c.chapter}">{c.chapter}</a></td>'
                       f"<td>{_inline_md(c.threads_opened)}</td><td>{_inline_md(c.threads_closed)}</td></tr>")
        out.append("</table></div>")
    out.append("</section>")

    # ---------------- characters
    out.append('<section id="characters" class="panel"><h2>Characters</h2>')
    if not sm.principals:
        out.append('<p class="note">No characters found — neither shared/characters.md nor the '
                   'summaries’ “Cast on stage” lines name anyone yet.</p>')
    else:
        out.append(f'<p class="note">Who is on stage in which chapter (from the summaries’ '
                   f'“Cast on stage” lines and the chapter POV). Principals come from '
                   f'{_e(sm.sources.get("characters", ""))}; names in the cast lines that '
                   f'characters.md does not list appear when they are on stage in '
                   f'{SUMMARY_CAST_MIN}+ chapters.</p>')
        out.append('<div class="legend"><span><b class="lg-pov">P</b>POV</span>'
                   '<span><b class="lg-touch">•</b>on stage</span></div>')
        out.append('<div class="gridwrap"><table class="grid">')
        out.append(_grid_head(sm, cols, "Character"))
        out.append("<tbody>")
        for p in sm.principals:
            apps = {a.chapter: a for a in p.appearances}
            n_pov = sum(1 for a in p.appearances if a.as_pov)
            meta = f"{len(apps)} ch" + (f" · POV {n_pov}" if n_pov else "")
            out.append(f'<tr><th class="lab"><a href="#who-{_e(p.slug)}">{_e(p.name)}</a>'
                       f'<span class="meta">{_e(meta)}</span></th>')
            for c in cols:
                a = apps.get(c)
                if a is None:
                    out.append('<td class="c"></td>')
                    continue
                note = "; ".join(x for x in (a.cast_entry, a.state) if x)
                title = by_ch[c].title if c in by_ch else ""
                cls = "pov" if a.as_pov else "present"
                out.append(f'<td class="c f {cls}" data-box="char-detail" data-row="{_e(p.name)}" '
                           f'data-ch="{c}" data-title="{_e(title)}" data-note="{_e(note)}" '
                           f'title="{_e(f"ch {c} · {note}")}">{"P" if a.as_pov else "•"}</td>')
            out.append("</tr>")
        out.append("</tbody></table></div>")
        out.append('<div id="char-detail" class="detail" aria-live="polite">'
                   'Click a filled cell for that chapter’s cast line and state change.</div>')
        for i, p in enumerate(sm.principals):
            n_pov = sum(1 for a in p.appearances if a.as_pov)
            meta = f"{len(p.appearances)} chapters" + (f" · POV in {n_pov}" if n_pov else "") \
                + f" · {p.source}"
            out.append(f'<details class="who" id="who-{_e(p.slug)}"{" open" if i < 2 else ""}>'
                       f'<summary>{_e(p.name)}<span class="meta">{_e(meta)}</span></summary>')
            if p.aliases:
                out.append(f'<p class="note">Also: {_e(", ".join(p.aliases))}</p>')
            if p.arc:
                out.append(f"<p>{_inline_md(p.arc)}</p>")
            out.append('<ol class="apps">')
            for a in p.appearances:
                c = by_ch.get(a.chapter)
                title = c.title if c else ""
                out.append(f'<li><a href="#ch-{a.chapter}">ch {a.chapter}</a> {_e(title)}'
                           + ('<span class="tag">POV</span>' if a.as_pov else ""))
                if a.state:
                    src = " (POV state)" if a.state_source == "summary POV state" else ""
                    out.append(f'<span class="st">{_inline_md(a.state)}'
                               f'<span class="note">{_e(src)}</span></span>')
                if a.line:
                    out.append(f'<span class="ln2">{_inline_md(a.line)}</span>')
                out.append("</li>")
            out.append("</ol></details>")
        if sm.absent_principals:
            out.append(f'<p class="note">Listed in shared/characters.md but not on stage in any '
                       f'summary’s cast: {_e(", ".join(sm.absent_principals))}.</p>')
    out.append("</section>")

    # ---------------- timeline + places
    out.append('<section id="timeline" class="panel"><h2>Timeline</h2>')
    out.append(_timeline_svg(sm))
    out.append('<div class="tablewrap"><table class="data"><tr><th>Ch</th><th>Title</th>'
               "<th>Story time</th><th>Gap since previous chapter</th></tr>")
    for c in sm.chapters:
        if c.gap_before is None:
            gap = "—"
        elif c.backwards:
            gap = f'<span class="gapflag">starts before the previous chapter</span>'
        elif c.gap_before > GAP_FLAG_YEARS:
            gap = f'<span class="gapflag">{_e(_fmt_years(c.gap_before))}</span>'
        elif c.gap_before <= 0:
            gap = "continuous / overlapping"
        else:
            gap = _e(_fmt_years(c.gap_before))
        out.append(f'<tr><td><a href="#ch-{c.chapter}">{c.chapter}</a></td><td>{_e(c.title)}</td>'
                   f"<td>{_e(c.story_time or '—')}</td><td>{gap}</td></tr>")
    out.append("</table></div>")
    out.append(f'<p class="note">Gaps over {GAP_FLAG_YEARS:g} year are highlighted. Dates come '
               f'from chapter frontmatter <code>story_time</code> (falling back to the summary’s '
               f'Story time, then the outline).</p>')

    out.append("<h2>Places</h2>")
    if not sm.places:
        out.append('<p class="note">No places found. Summaries carry a “Location:” line; '
                   'or add a <code>## Places</code> section to threads.md.</p>')
    else:
        out.append(f'<p class="note">Visited = named in the chapter summary’s Location line. '
                   f'Named only = mentioned in the Plot but not the Location. '
                   f'Place list: {_e(sm.place_source)}.</p>')
        out.append('<div class="tablewrap"><table class="data"><tr><th>Place</th>'
                   "<th>Visited (chapters)</th><th>Named only</th></tr>")
        for p in sm.places:
            vis = ", ".join(f'<a href="#ch-{n}">{n}</a>' for n in p.visited) or "—"
            nam = ", ".join(f'<a href="#ch-{n}">{n}</a>' for n in p.named_only) or "—"
            out.append(f"<tr><td>{_e(p.name)}</td><td>{vis}</td><td>{nam}</td></tr>")
        out.append("</table></div>")
    out.append("</section>")

    # ---------------- footer
    out.append("</main><footer><div class=\"wrap note\">")
    if sm.warnings:
        out.append("<p><strong>Notes</strong></p><ul>")
        for w in sm.warnings[:40]:
            out.append(f"<li>{_e(w)}</li>")
        if len(sm.warnings) > 40:
            out.append(f"<li>…and {len(sm.warnings) - 40} more (see story_map.json).</li>")
        out.append("</ul>")
    out.append(f"<p>Generated {_e(sm.generated_at)} by <code>autonovel mechanical story-map</code> "
               f"from files on disk (summaries, outline, threads.md, characters.md, eval logs). "
               f"It shows what those files say; it does not judge the book. Re-run "
               f"<code>/autonovel:story-map --book {_e(sm.book)}</code> after revising.</p>")
    out.append(f"</div></footer><script>{_JS}</script></body></html>")
    return "".join(out)


def _timeline_svg(sm: StoryMap) -> str:
    dated = [c for c in sm.chapters if c.t0 is not None and c.t1 is not None]
    if not dated:
        return ('<p class="note">No chapter has a parseable story_time (ISO dates such as '
                '<code>1477-09</code> or <code>1477-09-01 to 1477-11-17</code>).</p>')
    raw_lo = min(c.t0 for c in dated)
    raw_hi = max(c.t1 for c in dated)
    monthly = raw_hi - raw_lo < 2.0
    if monthly:
        t_lo = math.floor(raw_lo * 12) / 12
        t_hi = math.ceil(raw_hi * 12) / 12
    else:
        t_lo, t_hi = math.floor(raw_lo), math.ceil(raw_hi)
    if t_hi <= t_lo:
        t_hi = t_lo + (1 / 12 if monthly else 1)
    width = 1100
    left, right = 24, 24
    usable = width - left - right

    def x(t: float) -> float:
        return left + (t - t_lo) / (t_hi - t_lo) * usable

    # Greedy lanes so neighbouring chapter labels do not overprint.
    lanes: list[float] = []
    placed: list[tuple[MapChapter, int, float, float]] = []
    for c in sorted(dated, key=lambda c: (c.t0, c.chapter)):
        x0, x1 = x(c.t0), max(x(c.t1), x(c.t0) + 3)
        need_end = max(x1, x0 + 20)
        lane = next((i for i, end in enumerate(lanes) if end + 3 <= x0), None)
        if lane is None:
            lanes.append(need_end)
            lane = len(lanes) - 1
        else:
            lanes[lane] = need_end
        placed.append((c, lane, x0, x1))

    # Gap brackets (> GAP_FLAG_YEARS), labels stacked in rows so close
    # gaps (several chapters in a few years) do not overprint.
    gaps: list[tuple[float, float, str, int]] = []
    label_rows: list[float] = []          # right edge of the last label in each row
    prev: MapChapter | None = None
    for c in sm.chapters:
        if c.t0 is None:
            continue
        if prev is not None and c.gap_before is not None and c.gap_before > GAP_FLAG_YEARS \
                and not c.backwards:
            gx0, gx1 = x(prev.t1), x(c.t0)
            text = _fmt_years(c.gap_before)
            half = len(text) * 3.4
            mid = (gx0 + gx1) / 2
            row = next((i for i, end in enumerate(label_rows) if end + 4 <= mid - half), None)
            if row is None:
                label_rows.append(mid + half)
                row = len(label_rows) - 1
            else:
                label_rows[row] = mid + half
            gaps.append((gx0, gx1, text, row))
        prev = c

    lane_h = 22
    top = 34 + 14 * max(0, len(label_rows) - 1)
    height = top + max(1, len(lanes)) * lane_h + 30
    parts = [f'<div class="timewrap"><svg class="time" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" role="img" aria-label="Story time by chapter">']
    axis_y = height - 22
    parts.append(f'<line class="axis" x1="{left}" x2="{width - right}" y1="{axis_y}" y2="{axis_y}"/>')
    ticks: list[tuple[float, str]] = []
    if monthly:
        m_lo, m_hi = round(t_lo * 12), round(t_hi * 12)
        step = next(s for s in (1, 2, 3, 6, 12) if (m_hi - m_lo) / s <= 14)
        for mm in range(m_lo + (-m_lo) % step, m_hi + 1, step):
            ticks.append((mm / 12, f"{mm // 12:04d}-{mm % 12 + 1:02d}"))
    else:
        span = t_hi - t_lo
        step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 250, 500, 1000)
                    if span / s <= 14)
        for yv in range(int(math.ceil(t_lo / step) * step), int(t_hi) + 1, step):
            ticks.append((float(yv), str(yv)))
    for tv, label in ticks:
        parts.append(f'<line class="tick" x1="{x(tv):.1f}" x2="{x(tv):.1f}" y1="{top - 6}" y2="{axis_y + 4}"/>'
                     f'<text x="{x(tv):.1f}" y="{axis_y + 16}" text-anchor="middle">{label}</text>')
    for c, lane, x0, x1 in placed:
        yb = top + lane * lane_h
        parts.append(f'<a href="#ch-{c.chapter}"><rect class="bar" x="{x0:.1f}" y="{yb}" '
                     f'width="{x1 - x0:.1f}" height="8" rx="2">'
                     f'<title>ch {c.chapter} {_e(c.title)} · {_e(c.story_time)}</title></rect>'
                     f'<text x="{x0:.1f}" y="{yb + 19}">{c.chapter}</text></a>')
    for gx0, gx1, text, row in gaps:
        ly = top - 18 - row * 14
        parts.append(f'<path class="gap" d="M{gx0:.1f},{top - 10} L{gx0:.1f},{top - 14} '
                     f'L{gx1:.1f},{top - 14} L{gx1:.1f},{top - 10}"/>'
                     f'<text class="gapt" x="{(gx0 + gx1) / 2:.1f}" y="{ly}" '
                     f'text-anchor="middle">{_e(text)}</text>')
    parts.append("</svg></div>")
    return "".join(parts)


# --------------------------------------------------------- write


def default_output_path(book_root: Path) -> Path:
    return Path(book_root) / "edit_logs" / "story_map.html"


def write_story_map(sm: StoryMap, *, out: Path | None = None,
                    fmt: str = "html") -> dict:
    """Write story_map.html (+ story_map.json sidecar) — or only the JSON
    when `fmt == "json"` — and return the summary dict the CLI prints."""
    target = Path(out) if out else default_output_path(sm.book_root)
    if target.suffix.lower() not in (".html", ".htm", ".json"):
        target = target / "story_map.html"
    html_path = target.with_suffix(".html")
    json_path = target.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(sm.to_dict(), indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    wrote_html = None
    if fmt == "html":
        html_path.write_text(render_html(sm, out_dir=html_path.parent), encoding="utf-8")
        wrote_html = html_path
    return {
        "html": str(wrote_html.resolve()) if wrote_html else None,
        "url": wrote_html.resolve().as_uri() if wrote_html else None,
        "json": str(json_path.resolve()),
        "chapters": len(sm.chapters),
        "threads": len(sm.threads),
        "characters": len(sm.principals),
        "places": len(sm.places),
        "thread_source": sm.thread_source,
        "synopsis_words": sm.synopsis_words,
        "synopsis_minutes": sm.synopsis_minutes,
        "warnings": list(sm.warnings),
        "grid_text": render_grid_text(sm),
    }
