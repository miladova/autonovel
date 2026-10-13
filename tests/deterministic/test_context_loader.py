"""Tier-1 tests for `autonovel.context_loader`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel import project as project_mod
from autonovel.context_loader import (
    ContextError,
    build_context,
    main,
)
from autonovel.housekeeping import scaffold
from autonovel.paths import SeriesLayout


def _setup_two_book_series(tmp_path: Path) -> SeriesLayout:
    result = scaffold.new_series(
        tmp_path / "s", series_name="s", genre="historical-fiction"
    )
    series = result.series
    scaffold.new_book(series, book_name="inquisitor", pov="Tommaso")
    scaffold.new_book(series, book_name="apothecary", pov="Lucia")

    cfg = project_mod.load(series.project_file)
    for b in cfg.books:
        b.story_time_range = [1521, 1523]
    project_mod.dump(cfg, series.project_file)

    # inquisitor outline: two chapters at 1521-12-04 and 1521-12-06.
    (series.book("inquisitor").outline_file).write_text(
        """# Outline

## Chapter 1 — Ashes at the Zecca
- story_time: 1521-12-04
- events: [E-001]
- beats:
  - Tommaso investigates the morning after.

## Chapter 2 — The apothecary
- story_time: 1521-12-06
- events: []
- beats:
  - He crosses to Ponte San Giovanni.
""",
        encoding="utf-8",
    )
    (series.book("apothecary").outline_file).write_text(
        """# Outline

## Chapter 1 — Before the fire
- story_time: 1521-12-01
- events: []
- beats:
  - Lucia sorts saltpeter.

## Chapter 2 — Smoke in the night
- story_time: 1521-12-08
- events: [E-001]
- beats:
  - She treats the burn she will not name.
""",
        encoding="utf-8",
    )

    # events.md: E-001 renders in both books.
    (series.shared / "events.md").write_text(
        """# Events ledger

## E-001: Fire at the Venetian mint
- date: 1521-12-03
- location: Zecca, Venice
- present: [Master Giraldo, two apprentices]
- canonical: Master Giraldo set the fire.
- rendered_in:
    inquisitor/ch_01: Tommaso investigates the ashes.
    apothecary/ch_02: Lucia treats the burn, unnamed.
- book_constraints: Tommaso cannot know who lit it.
""",
        encoding="utf-8",
    )

    # Seed a sibling chapter file with valid frontmatter for each book.
    _write_chapter(
        series.book("inquisitor").chapters / "ch_01.md",
        book="inquisitor",
        chapter=1,
        pov="Tommaso",
        story_time="1521-12-04",
        events=["E-001"],
    )
    _write_chapter(
        series.book("apothecary").chapters / "ch_01.md",
        book="apothecary",
        chapter=1,
        pov="Lucia",
        story_time="1521-12-01",
        events=[],
    )
    _write_chapter(
        series.book("apothecary").chapters / "ch_02.md",
        book="apothecary",
        chapter=2,
        pov="Lucia",
        story_time="1521-12-08",
        events=["E-001"],
    )
    return series


def _write_chapter(
    path: Path,
    *,
    book: str,
    chapter: int,
    pov: str,
    story_time: str,
    events: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    events_list = "[" + ", ".join(events) + "]"
    body = (
        "---\n"
        f"book: {book}\n"
        f"chapter: {chapter}\n"
        f"pov: {pov}\n"
        f"story_time: {story_time}\n"
        f"events: {events_list}\n"
        "status: drafted\n"
        "---\n\nPlaceholder body.\n"
    )
    path.write_text(body, encoding="utf-8")


def test_build_context_lists_shared_and_book_files(tmp_path: Path) -> None:
    series = _setup_two_book_series(tmp_path)
    bundle = build_context(series, book="inquisitor", chapter=2)

    assert bundle.book == "inquisitor"
    assert bundle.chapter == 2
    assert bundle.story_time == "1521-12-06"
    assert bundle.events == []  # chapter 2 names no events
    assert "shared/world.md" in bundle.shared
    assert "shared/characters.md" in bundle.shared
    assert "shared/events.md" in bundle.shared
    assert "books/inquisitor/outline.md" in bundle.book_files
    assert "books/inquisitor/voice.md" in bundle.book_files
    # The book's own canon is per-book context (book-scoped canon).
    assert "books/inquisitor/canon.md" in bundle.book_files
    # Previous chapter is included when it exists.
    assert "books/inquisitor/chapters/ch_01.md" in bundle.book_files


def test_isolated_book_reads_no_sibling_chapters(tmp_path: Path) -> None:
    """`context: isolated` (a rewrite of a story another book tells)
    withholds every sibling chapter even when it clears the story-time
    gate; shared/ lore is still listed."""
    series = _setup_two_book_series(tmp_path)
    cfg = project_mod.load(series.project_file)
    cfg.book_by_name("inquisitor").context = "isolated"
    project_mod.dump(cfg, series.project_file)

    bundle = build_context(series, book="inquisitor", chapter=2)
    assert bundle.sibling_chapters == []
    # apothecary/ch_01 (1521-12-01) would normally be readable.
    assert "books/apothecary/chapters/ch_01.md" in bundle.excluded_spoilers
    assert "books/apothecary/chapters/ch_02.md" in bundle.excluded_spoilers
    assert any("isolated" in n for n in bundle.notes)
    assert "shared/world.md" in bundle.shared
    assert "books/inquisitor/outline.md" in bundle.book_files


def test_sibling_spoiler_gating(tmp_path: Path) -> None:
    """Chapters later in story_time than `self` must be excluded."""
    series = _setup_two_book_series(tmp_path)
    bundle = build_context(series, book="inquisitor", chapter=2)

    # apothecary/ch_01 is 1521-12-01 (before self 1521-12-06) → readable.
    assert "books/apothecary/chapters/ch_01.md" in bundle.sibling_chapters
    # apothecary/ch_02 is 1521-12-08 (after self) → excluded as spoiler.
    assert "books/apothecary/chapters/ch_02.md" in bundle.excluded_spoilers
    assert (
        "books/apothecary/chapters/ch_02.md" not in bundle.sibling_chapters
    ), "future-story-time chapter leaked into readable context"


def test_rendered_in_event_surfaces_sibling_chapter(tmp_path: Path) -> None:
    """A chapter that renders the same event (and sits at an earlier
    story_time) is always surfaced as sibling context so the drafter can
    obey `book_constraints`."""
    series = _setup_two_book_series(tmp_path)
    # Add a later apothecary chapter that happens *before* self and also
    # renders E-001 (earlier story_time, earlier chapter body).
    bundle = build_context(series, book="inquisitor", chapter=1)
    # Self story_time is 1521-12-04; apothecary/ch_01 is 1521-12-01.
    assert "books/apothecary/chapters/ch_01.md" in bundle.sibling_chapters
    # apothecary/ch_02 (1521-12-08) still excluded — spoiler dominates
    # event rendering.
    assert "books/apothecary/chapters/ch_02.md" not in bundle.sibling_chapters
    assert "books/apothecary/chapters/ch_02.md" in bundle.excluded_spoilers


def test_unknown_book_raises(tmp_path: Path) -> None:
    series = _setup_two_book_series(tmp_path)
    with pytest.raises(ContextError):
        build_context(series, book="nonexistent", chapter=1)


def test_unknown_chapter_raises(tmp_path: Path) -> None:
    series = _setup_two_book_series(tmp_path)
    with pytest.raises(ContextError):
        build_context(series, book="inquisitor", chapter=99)


def test_outline_chapter_missing_story_time_raises(tmp_path: Path) -> None:
    series = _setup_two_book_series(tmp_path)
    (series.book("inquisitor").outline_file).write_text(
        """# Outline

## Chapter 1 — No story_time here
- events: []
- beats:
  - Tommaso broods.
""",
        encoding="utf-8",
    )
    with pytest.raises(ContextError):
        build_context(series, book="inquisitor", chapter=1)


def test_cli_returns_json(tmp_path: Path) -> None:
    series = _setup_two_book_series(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autonovel.context_loader",
            "--book",
            "inquisitor",
            "--chapter",
            "2",
            "--series-root",
            str(series.root),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["book"] == "inquisitor"
    assert data["chapter"] == 2
    assert "shared/events.md" in data["shared"]
    assert "books/apothecary/chapters/ch_02.md" in data["excluded_spoilers"]


def test_cli_errors_when_chapter_missing(tmp_path: Path) -> None:
    series = _setup_two_book_series(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autonovel.context_loader",
            "--book",
            "inquisitor",
            "--chapter",
            "99",
            "--series-root",
            str(series.root),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Chapter 99" in result.stderr or "chapter 99" in result.stderr
