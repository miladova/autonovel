"""Tier-1 tests for `autonovel.mechanical.series_arc`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel import project as project_mod
from autonovel.housekeeping import scaffold
from autonovel.mechanical.series_arc import (
    _is_zero_threads,
    build_report,
    render_markdown,
)


def _seed_book(series_root: Path, name: str, *,
                chapters: dict[int, dict] | None = None,
                pov: str = "Tommaso") -> None:
    """Add a book with the given chapter shapes. `chapters` is
    `{n: {"prose": ..., "summary": "**Plot:** ...", "score": 7.5}}`."""
    if (series_root / "books" / name).exists():
        cfg = project_mod.load(series_root / "project.yaml")
    else:
        layout = scaffold.SeriesLayout(root=series_root)
        scaffold.new_book(layout, book_name=name, pov=pov)
    book_root = series_root / "books" / name
    chapters_dir = book_root / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    eval_dir = book_root / "eval_logs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    for n, spec in (chapters or {}).items():
        (chapters_dir / f"ch_{n:02d}.md").write_text(
            f"---\nbook: {name}\nchapter: {n}\npov: {pov}\n"
            f"story_time: {spec.get('story_time', f'2020-01-{n:02d}')}\n"
            f"events: []\nstatus: drafted\nword_count: 100\n---\n\n"
            + spec.get("prose", f"Prose {n}.\n"),
            encoding="utf-8",
        )
        if "summary" in spec:
            (chapters_dir / f"ch_{n:02d}.summary.md").write_text(
                spec["summary"], encoding="utf-8")
        if "score" in spec:
            (eval_dir / f"ch{n:02d}_eval.json").write_text(
                json.dumps({"overall_score": spec["score"]}),
                encoding="utf-8",
            )


@pytest.fixture
def series(tmp_path: Path):
    res = scaffold.new_series(tmp_path / "s", series_name="s")
    return res.series.root


# ---------------------------------------------------------- _is_zero_threads


def test_is_zero_threads() -> None:
    assert _is_zero_threads("none")
    assert _is_zero_threads("None.")
    assert _is_zero_threads("zero")
    assert _is_zero_threads("—")
    assert _is_zero_threads("")
    assert not _is_zero_threads("the bell motif")


# ---------------------------------------------------------- build_report


def test_build_report_single_book(series: Path) -> None:
    _seed_book(series, "b", chapters={
        1: {"summary": "**Plot:** A.\n**Cast on stage:** Tommaso\n", "score": 7.5},
        2: {"summary": "**Plot:** B.\n**Cast on stage:** Tommaso\n", "score": 7.0},
    })
    report = build_report(series)
    assert report.book_count == 1
    assert report.books[0].chapter_count == 2
    assert report.books[0].above_threshold == 2
    assert report.books[0].summary_coverage == 1.0
    assert report.books[0].eval_coverage == 1.0


def test_build_report_no_books_returns_empty(series: Path) -> None:
    # No books added.
    report = build_report(series)
    assert report.book_count == 0
    assert report.arc_score == 0.0


def test_build_report_cross_book_cast(series: Path) -> None:
    cast_a = "**Cast on stage:** Tommaso; Lucia\n"
    cast_b = "**Cast on stage:** Tommaso; Niccolò\n"
    _seed_book(series, "a", chapters={1: {"summary": cast_a}})
    _seed_book(series, "b", chapters={1: {"summary": cast_b}})
    report = build_report(series)
    assert "Tommaso" in report.cross_book_cast
    assert set(report.cross_book_cast["Tommaso"]) == {"a", "b"}
    # Lucia appears only in book a → not cross-book.
    assert "Lucia" not in report.cross_book_cast


def test_build_report_unresolved_threads(series: Path) -> None:
    open_summary = (
        "**Plot:** opens.\n"
        "**Cast on stage:** Tommaso\n"
        "**Threads opened:** the missing letter; the cracked seal\n"
        "**Threads closed:** none\n"
    )
    close_summary = (
        "**Plot:** closes.\n"
        "**Cast on stage:** Tommaso\n"
        "**Threads opened:** none\n"
        "**Threads closed:** the missing letter\n"
    )
    _seed_book(series, "a", chapters={
        1: {"summary": open_summary},
        2: {"summary": close_summary},
    })
    report = build_report(series)
    threads = [t.thread for t in report.unresolved_threads]
    assert "the cracked seal" in threads
    # The missing letter was closed → not unresolved.
    assert "the missing letter" not in threads


def test_build_report_backwards_story_time_jumps(series: Path) -> None:
    _seed_book(series, "a", chapters={
        1: {"story_time": "2020-01-01"},
        2: {"story_time": "2020-02-01"},
        3: {"story_time": "2019-12-01"},  # backwards
    })
    report = build_report(series)
    assert len(report.backwards_story_time_jumps) == 1
    j = report.backwards_story_time_jumps[0]
    assert j.book == "a" and j.chapter == 3


def test_overlapping_books_do_not_count_boundary_reset_as_backwards(series: Path) -> None:
    """Two books whose project.yaml ranges overlap (a rewrite, a parallel
    POV) legitimately reset the clock at the book boundary. Jumps
    INSIDE either book are still reported."""
    _seed_book(series, "a", chapters={
        1: {"story_time": "1473-09-01"},
        2: {"story_time": "1525-12-01"},
    })
    _seed_book(series, "b", chapters={
        1: {"story_time": "1473-09-01"},   # boundary reset — exempt
        2: {"story_time": "1480-01-01"},
        3: {"story_time": "1475-01-01"},   # real in-book backwards jump
    })
    cfg = project_mod.load(series / "project.yaml")
    for b in cfg.books:
        b.story_time_range = [1471, 1525]
    project_mod.dump(cfg, series / "project.yaml")

    report = build_report(series)
    assert report.overlapping_books == ["a ~ b"]
    assert [(j.book, j.chapter) for j in report.backwards_story_time_jumps] == [("b", 3)]
    md = render_markdown(report)
    assert "Overlapping story-time ranges" in md
    assert report.to_dict()["overlapping_books"] == ["a ~ b"]


def test_non_overlapping_books_still_report_boundary_jump(series: Path) -> None:
    _seed_book(series, "a", chapters={1: {"story_time": "1500-01-01"}})
    _seed_book(series, "b", chapters={1: {"story_time": "1490-01-01"}})
    cfg = project_mod.load(series / "project.yaml")
    cfg.books[0].story_time_range = [1500, 1510]
    cfg.books[1].story_time_range = [1490, 1495]
    project_mod.dump(cfg, series / "project.yaml")
    report = build_report(series)
    assert report.overlapping_books == []
    assert [(j.book, j.chapter) for j in report.backwards_story_time_jumps] == [("b", 1)]


def test_build_report_above_threshold_count(series: Path) -> None:
    _seed_book(series, "a", chapters={
        1: {"score": 7.5},
        2: {"score": 6.0},
        3: {"score": 8.0},
    })
    report = build_report(series, threshold=7.0)
    assert report.books[0].above_threshold == 2


def test_build_report_summary_coverage(series: Path) -> None:
    _seed_book(series, "a", chapters={
        1: {"summary": "**Plot:** ok.\n"},
        2: {},  # no summary file
    })
    report = build_report(series)
    assert report.books[0].summary_coverage == 0.5


def test_build_report_arc_score_range(series: Path) -> None:
    _seed_book(series, "a", chapters={
        1: {"summary": "**Plot:** A.\n**Cast on stage:** Tommaso\n", "score": 7.5},
    })
    report = build_report(series)
    # Score is 0..10.
    assert 0.0 <= report.arc_score <= 10.0


def test_build_report_arc_score_zero_when_empty(series: Path) -> None:
    report = build_report(series)
    assert report.arc_score == 0.0


def test_build_report_unresolved_thread_penalty_lowers_arc_score(
    series: Path,
) -> None:
    """A series with all threads closed scores higher than one with
    several unresolved."""
    closed_summary = (
        "**Plot:** ok.\n"
        "**Cast on stage:** Tommaso\n"
        "**Threads opened:** thread one\n"
        "**Threads closed:** thread one\n"
    )
    _seed_book(series, "good", chapters={
        1: {"summary": closed_summary, "score": 8.0},
    })
    closed_score = build_report(series).arc_score

    # Reset by rebuilding into a fresh series.
    series2 = series.parent / "s2"
    series2.mkdir()
    scaffold.new_series.__wrapped__ if False else None
    res2 = scaffold.new_series(series2 / "x", series_name="x")
    _seed_book(res2.series.root, "bad", chapters={
        1: {"summary": (
                "**Plot:** ok.\n**Cast on stage:** Tommaso\n"
                "**Threads opened:** thread one; thread two; thread three\n"
                "**Threads closed:** none\n"
            ), "score": 8.0},
    })
    bad_score = build_report(res2.series.root).arc_score
    assert bad_score < closed_score


# ---------------------------------------------------------- render


def test_render_markdown_includes_composite_score(series: Path) -> None:
    _seed_book(series, "a", chapters={
        1: {"summary": "**Plot:** A.\n**Cast on stage:** Tommaso\n", "score": 7.5},
    })
    out = render_markdown(build_report(series))
    assert "Series arc score" in out
    assert "Composite arc score" in out
    assert "## Books" in out


def test_render_markdown_one_book_note(series: Path) -> None:
    _seed_book(series, "solo", chapters={1: {"score": 7.5}})
    out = render_markdown(build_report(series))
    assert "≥2 books" in out


def test_render_markdown_cross_book_section(series: Path) -> None:
    _seed_book(series, "a", chapters={
        1: {"summary": "**Cast on stage:** Tommaso; Lucia\n"}})
    _seed_book(series, "b", chapters={
        1: {"summary": "**Cast on stage:** Tommaso\n"}})
    out = render_markdown(build_report(series))
    assert "Cross-book cast" in out
    assert "Tommaso" in out


# ---------------------------------------------------------- CLI


def test_cli_series_arc_markdown(series: Path) -> None:
    _seed_book(series, "a", chapters={1: {"score": 7.5}})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "series-arc",
         str(series)],
        capture_output=True, text=True, check=True,
    )
    assert "Series arc score" in proc.stdout


def test_cli_series_arc_json(series: Path) -> None:
    _seed_book(series, "a", chapters={1: {"score": 7.5}})
    _seed_book(series, "b", chapters={1: {"score": 7.0}})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "series-arc",
         str(series), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["book_count"] == 2
    assert "arc_score" in payload
    assert len(payload["books"]) == 2
