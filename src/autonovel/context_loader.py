"""Build the context file list for a (book, chapter) draft.

The drafter (`/autonovel:draft`) reads many files, but multi-book series
need one extra rule: other books' chapters are only legal context when
their `story_time` is less than or equal to the chapter being drafted.
Anything later in story time is a spoiler and must not leak into the
draft, even if the sibling chapter is already on disk.

This helper resolves that rule. It returns:

    - `shared`:    shared/* files that are always read
    - `book`:      the book's own outline, voice, prior chapter
    - `sibling`:   chapters from other books readable at this story_time
    - `events`:    event ids the outline names for this chapter
    - `excluded`:  sibling-book chapters deliberately withheld as spoilers

It is both a library (used by tests) and a CLI entry point
(`python -m autonovel.context_loader --book X --chapter N`) so a runtime
command can shell out and get a JSON manifest.

Budget rule (§19 risk: "story-time loader blowup"): this helper returns
paths only. Token budgeting (truncate-oldest-first, summarize-rest) is
the drafter's responsibility — all we do here is tell it which files it
is allowed to look at.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Iterable

import yaml

from . import project as project_mod
from .paths import SeriesLayout, load_series
from .validators.events import parse as parse_events


_OUTLINE_HEADING_RE = re.compile(r"^##\s+Chapter\s+(?P<n>\d+)\b", re.MULTILINE)
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<body>.*?\n)---\s*(?:\n|\Z)",
    flags=re.DOTALL,
)


class ContextError(ValueError):
    pass


@dataclass
class ContextBundle:
    book: str
    chapter: int
    story_time: str
    shared: list[str]
    book_files: list[str]
    sibling_chapters: list[str]
    events: list[str]
    excluded_spoilers: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_context(
    series: SeriesLayout,
    *,
    book: str,
    chapter: int,
) -> ContextBundle:
    cfg = project_mod.load(series.project_file)
    entry = cfg.book_by_name(book)
    if entry is None:
        raise ContextError(f"book {book!r} not in project.yaml")

    book_root = series.book(book).root
    outline_path = series.book(book).outline_file
    if not outline_path.is_file():
        raise ContextError(f"missing outline: {outline_path}")

    story_time, event_ids, notes = _read_outline_chapter(outline_path, chapter)

    shared = _existing(
        series.root,
        [
            "project.yaml",
            "shared/world.md",
            "shared/characters.md",
            "shared/canon.md",
            "shared/events.md",
            "shared/period_bans.txt",
        ],
    )
    notes_paths = _glob(series.root, "shared/research/notes/*.md")
    shared.extend(notes_paths)

    book_files = _existing(
        series.root,
        [
            f"books/{book}/voice.md",
            f"books/{book}/outline.md",
            f"books/{book}/seed.txt",
            f"books/{book}/canon.md",
            f"books/{book}/pending_canon.md",
        ],
    )

    prev_rel = _prev_chapter_path(book, chapter)
    if (series.root / prev_rel).is_file():
        book_files.append(prev_rel)

    if entry.is_isolated:
        # `context: isolated` (project.yaml books[]): this book never
        # reads sibling-book prose — the case for a rewrite of a story
        # another book already tells, where the old chapters would
        # otherwise all clear the story-time gate and anchor the new
        # draft on exactly the prose being replaced.
        sibling_chapters = []
        excluded = _all_sibling_chapters(series, self_book=book)
        notes = list(notes) + [
            f"context: isolated — {len(excluded)} sibling-book chapter(s) "
            "withheld by project.yaml; only shared/ lore is read"
        ]
    else:
        sibling_chapters, excluded = _sibling_chapters(
            series=series,
            self_book=book,
            self_chapter=chapter,
            self_story_time=story_time,
            event_ids=event_ids,
        )

    return ContextBundle(
        book=book,
        chapter=chapter,
        story_time=story_time,
        shared=sorted(shared),
        book_files=sorted(book_files),
        sibling_chapters=sorted(sibling_chapters),
        events=event_ids,
        excluded_spoilers=sorted(excluded),
        notes=notes,
    )


def _read_outline_chapter(outline_path: Path, chapter: int) -> tuple[str, list[str], list[str]]:
    """Return (story_time, events, notes) for the chapter block of interest."""
    text = outline_path.read_text(encoding="utf-8")
    headings = list(_OUTLINE_HEADING_RE.finditer(text))
    if not headings:
        raise ContextError(f"{outline_path}: no `## Chapter N` headings")

    target_idx = None
    for idx, m in enumerate(headings):
        if int(m.group("n")) == chapter:
            target_idx = idx
            break
    if target_idx is None:
        raise ContextError(
            f"{outline_path}: outline has no `## Chapter {chapter}` entry"
        )

    start = headings[target_idx].end()
    end = headings[target_idx + 1].start() if target_idx + 1 < len(headings) else len(text)
    block = text[start:end]

    story_time = ""
    events: list[str] = []
    notes: list[str] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if line.startswith("- story_time:"):
            story_time = line.split(":", 1)[1].strip()
        elif line.startswith("- events:"):
            events = _parse_list(line.split(":", 1)[1])
        elif line.startswith("- notes:"):
            notes = _parse_list(line.split(":", 1)[1])
    if not story_time:
        raise ContextError(
            f"{outline_path}: chapter {chapter} has no `story_time` field"
        )
    return story_time, events, notes


def _parse_list(value: str) -> list[str]:
    s = value.strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = yaml.safe_load(s)
        except yaml.YAMLError:
            parsed = None
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    return [p.strip() for p in s.strip("[]").split(",") if p.strip()]


def _existing(root: Path, rel_paths: Iterable[str]) -> list[str]:
    return [p for p in rel_paths if (root / p).is_file()]


def _glob(root: Path, pattern: str) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())


def _prev_chapter_path(book: str, chapter: int) -> str:
    return f"books/{book}/chapters/ch_{chapter - 1:02d}.md"


def _sibling_chapters(
    *,
    series: SeriesLayout,
    self_book: str,
    self_chapter: int,
    self_story_time: str,
    event_ids: list[str],
) -> tuple[list[str], list[str]]:
    """Return (readable, excluded) sibling chapters ordered by story_time.

    Two rules layered together (§8 events + §19 spoiler control):
      * `story_time` of the sibling <= self story_time (any book that
        happens "later" in fictional time is a spoiler).
      * Chapters that `rendered_in` *this* chapter's events in another
        book are surfaced as explicit pointers, but the drafter is still
        expected to obey the `book_constraints` line from events.md.
    """
    cfg = project_mod.load(series.project_file)
    self_bound = _as_date_bound(self_story_time, upper=True)

    readable: list[str] = []
    excluded: list[str] = []

    for book in cfg.books:
        if book.name == self_book:
            continue
        chapters_dir = series.book(book.name).chapters
        if not chapters_dir.is_dir():
            continue
        from .paths import iter_chapter_files
        for ch_path in iter_chapter_files(chapters_dir):
            sibling_time = _chapter_story_time(ch_path)
            rel = str(ch_path.relative_to(series.root))
            if sibling_time is None:
                excluded.append(rel)
                continue
            sibling_upper = _as_date_bound(sibling_time, upper=False)
            if sibling_upper is None:
                excluded.append(rel)
                continue
            if sibling_upper <= self_bound:
                readable.append(rel)
            else:
                excluded.append(rel)

    events_file = series.root / "shared" / "events.md"
    if events_file.is_file() and event_ids:
        events, _problems = parse_events(events_file)
        excluded_set = set(excluded)
        readable_set = set(readable)
        for ev in events:
            if ev.id not in event_ids:
                continue
            for rendered in ev.rendered_in:
                if rendered.book == self_book:
                    continue
                rel = f"books/{rendered.book}/chapters/ch_{rendered.chapter:02d}.md"
                if not (series.root / rel).is_file():
                    continue
                # Spoiler rule dominates event rendering: if the sibling
                # chapter happens later in story_time than the chapter
                # being drafted, it stays in `excluded`. Only surface
                # chapters that also cleared the story_time gate.
                if rel in excluded_set or rel in readable_set:
                    continue
                readable.append(rel)
                readable_set.add(rel)

    return readable, excluded


def _all_sibling_chapters(series: SeriesLayout, *, self_book: str) -> list[str]:
    """Every chapter file in every OTHER book (relative paths). Used to
    report what `context: isolated` withheld."""
    from .paths import iter_chapter_files
    cfg = project_mod.load(series.project_file)
    out: list[str] = []
    for book in cfg.books:
        if book.name == self_book:
            continue
        for ch_path in iter_chapter_files(series.book(book.name).chapters):
            out.append(str(ch_path.relative_to(series.root)))
    return out


def _chapter_story_time(ch_path: Path) -> str | None:
    """Extract `story_time` from a chapter's YAML frontmatter."""
    try:
        text = ch_path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group("body"))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("story_time")
    if value is None:
        return None
    return str(value)


def _as_date_bound(story_time: str, *, upper: bool) -> date | None:
    """Convert a story_time (date or `a..b` range) into a comparable date.

    For the *self* side we want the upper bound of the range; for the
    *sibling* side we want the lower bound, so "a book that begins later
    than I end" is excluded even if the range overlaps. That is the
    conservative spoiler rule.

    Returns None when the value is malformed, in which case the caller
    treats it as not-readable.
    """
    s = story_time.strip()
    if not s:
        return None
    parts = s.split("..")
    if len(parts) == 1:
        return _parse_iso(parts[0])
    if len(parts) == 2:
        start, end = parts
        return _parse_iso(end) if upper else _parse_iso(start)
    return None


def _parse_iso(s: str) -> date | None:
    s = s.strip()
    if not _ISO_DATE_RE.match(s):
        return None
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m autonovel.context_loader")
    p.add_argument("--book", required=True)
    p.add_argument("--chapter", required=True, type=int)
    p.add_argument(
        "--series-root",
        type=Path,
        default=None,
        help="Series root (default: walk up from CWD until project.yaml is found).",
    )
    args = p.parse_args(argv)

    series = SeriesLayout(root=args.series_root) if args.series_root else load_series()
    try:
        bundle = build_context(series, book=args.book, chapter=args.chapter)
    except ContextError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    json.dump(bundle.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
