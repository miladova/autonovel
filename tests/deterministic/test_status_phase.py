"""Tier-1: `autonovel status` reports the most-advanced phase signal.

The per-book `state.json :: phase` is written once at scaffold time and
never advanced by the pipeline, so a 24-chapter book used to show
`seed`. The on-disk inference (chapters → drafting) is now the floor.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.housekeeping import status
from autonovel.housekeeping.scaffold import new_book, new_series


def test_status_infers_drafting_from_chapters_when_state_is_stale(tmp_path: Path) -> None:
    res = new_series(tmp_path / "s", series_name="s")
    series = res.series
    new_book(series, book_name="one", pov="Tom")
    book = series.book("one")
    assert json.loads(book.state_file.read_text(encoding="utf-8"))["phase"] == "seed"
    book.chapters.mkdir(exist_ok=True)
    (book.chapters / "ch_01.md").write_text(
        "---\nbook: one\nchapter: 1\npov: Tom\nstory_time: 1500-01-01\n"
        "events: []\nstatus: drafted\nword_count: 10\n---\n\nSome prose.\n",
        encoding="utf-8",
    )
    report = status.gather(series)
    assert report.books[0].status == "drafting"
    assert report.books[0].chapters_drafted == 1
    assert "drafting" in status.render(report)


def test_status_keeps_explicit_later_phase(tmp_path: Path) -> None:
    res = new_series(tmp_path / "s", series_name="s")
    series = res.series
    new_book(series, book_name="one", pov="Tom")
    book = series.book("one")
    data = json.loads(book.state_file.read_text(encoding="utf-8"))
    data["phase"] = "revision"
    book.state_file.write_text(json.dumps(data), encoding="utf-8")
    report = status.gather(series)
    assert report.books[0].status == "revision"


def test_status_fresh_book_is_seed(tmp_path: Path) -> None:
    res = new_series(tmp_path / "s", series_name="s")
    new_book(res.series, book_name="one", pov="Tom")
    report = status.gather(res.series)
    assert report.books[0].status == "seed"
