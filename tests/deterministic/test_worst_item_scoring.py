"""The worst item, not only the mean (2026-10-23).

A chapter's overall score hid a 6.9 for sense of place inside a 7.8
(kingmaker2 ch 7). Every surface now shows the lowest dimension beside
the mean, the dashboard ranks the book's lowest scores, and a dimension
under `defaults.dimension_floor` sends a chapter back to revise.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.housekeeping import next_actions
from autonovel.housekeeping.next_step import PipelineState, next_step
from autonovel.mechanical.chapter_summary import (
    chapter_score_details, format_low, render_markdown_table, score_detail, summarize_chapters,
)
from autonovel.mechanical.dashboard import build_dashboard, render_dimensions, render_markdown
from autonovel.mechanical.summary_query import filter_rows as query
from autonovel.paths import SeriesLayout


def _eval(dims: dict[str, float], overall: float, **extra) -> dict:
    data = {
        "overall_score": overall,
        "dimensions": {k: {"score": v, "weakest_moment": f"{k} moment", "fix": f"{k} fix"}
                       for k, v in dims.items()},
    }
    data.update(extra)
    return data


def _book(tmp_path: Path, evals: dict[int, dict]) -> Path:
    book = tmp_path / "books" / "b"
    (book / "chapters").mkdir(parents=True)
    (book / "eval_logs").mkdir()
    for n, data in evals.items():
        (book / "chapters" / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\nword_count: 3000\n---\n\n" + "Words. " * 50, encoding="utf-8")
        (book / "eval_logs" / f"ch{n:02d}_eval.json").write_text(json.dumps(data), encoding="utf-8")
    return book


def test_score_detail_lowest_dimension_and_reader() -> None:
    d = score_detail(7, _eval({"sense_of_place": 6.9, "prose_quality": 7.4, "engagement": 7.2},
                              7.8, first_reader={"serious_items_first": ["a", "b"],
                                                 "serious_items_second": None}))
    assert (d.low_dim, d.low_score) == ("sense_of_place", 6.9)
    assert d.low_moment == "sense_of_place moment"
    assert d.reader_first == 2 and d.reader_second is None and d.reader_open == 2
    assert format_low(d.low_dim, d.low_score, floor=7.0) == "place 6.9 ⚠"
    assert format_low(None, None) == "—"


def test_score_detail_tie_prefers_the_judges_weakest() -> None:
    d = score_detail(3, _eval({"engagement": 7.0, "prose_quality": 7.0}, 7.3,
                              weakest_dimension="prose_quality"))
    assert d.low_dim == "prose_quality"


def test_score_detail_all_fixed_clears_open_items() -> None:
    d = score_detail(19, _eval({"engagement": 7.5}, 7.6,
                               first_reader={"serious_items_first": 5,
                                             "serious_items_second": ["x"], "all_fixed": True}))
    assert d.reader_open == 0


def test_reader_open_counts_the_evaluators_open_items() -> None:
    """A revised chapter can keep two of a report's twenty-seven items:
    the evaluator's `open_items` is the count, not the report's length."""
    from autonovel.mechanical.chapter_summary import score_detail
    d = score_detail(3, {"overall_score": 7.6, "dimensions": {"engagement": 7.5},
                         "first_reader": {"serious_items_first": 29,
                                          "serious_items_second": 27,
                                          "open_items": ["the committee", "the purse"],
                                          "all_fixed": False}})
    assert d.reader_second == 27 and d.reader_open == 2
    d = score_detail(3, {"overall_score": 7.6, "dimensions": {"engagement": 7.5},
                         "first_reader": {"serious_items_second": 27, "open_items": [],
                                          "all_fixed": True}})
    assert d.reader_open == 0


def test_latest_log_wins(tmp_path: Path) -> None:
    book = _book(tmp_path, {1: _eval({"engagement": 6.0}, 6.5)})
    (book / "eval_logs" / "20990101_000000_ch01_eval.json").write_text(
        json.dumps(_eval({"engagement": 8.0, "prose_quality": 7.5}, 7.9)), encoding="utf-8")
    d = chapter_score_details(book / "eval_logs")[1]
    assert (d.low_dim, d.low_score) == ("prose_quality", 7.5)


def test_chapter_summary_table_shows_lowest(tmp_path: Path) -> None:
    book = _book(tmp_path, {1: _eval({"sense_of_place": 6.9, "engagement": 8.0}, 7.8)})
    rows = summarize_chapters(book)
    assert rows[0].low_dim == "sense_of_place"
    assert "place 6.9" in render_markdown_table(rows)


def test_dashboard_lowest_column_worst_list_and_dimensions(tmp_path: Path) -> None:
    book = _book(tmp_path, {
        1: _eval({"sense_of_place": 6.9, "engagement": 8.0, "history": 7.1}, 7.8),
        2: _eval({"sense_of_place": 8.0, "engagement": 7.3}, 7.6,
                 first_reader={"serious_items_first": ["a"], "serious_items_second": ["b"]}),
    })
    report = build_dashboard(book, threshold=7.0, floor=7.0, worst_n=3)
    assert [(w.chapter, w.dimension) for w in report.worst] == [
        (1, "sense_of_place"), (1, "history"), (2, "engagement")]
    assert report.worst[0].moment == "sense_of_place moment"
    assert report.aggregate.lowest == (1, "sense_of_place", 6.9)
    assert report.aggregate.below_floor == 1
    md = render_markdown(report, threshold=7.0)
    assert "| Lowest |" in md and "place 6.9 ⚠" in md
    assert "## Needs attention first" in md
    assert "ch 2 (1 left)" in md
    dims = render_dimensions(report)
    assert "## Story" in dims and "## People and place" in dims
    assert "## Genre and book-specific" in dims and "history" in dims
    assert "**6.9 ⚠**" in dims
    assert "| 2 | 1 | 1 | 1 left |" in dims
    data = report.to_dict()
    assert data["rows"][0]["low_dim"] == "sense_of_place"
    assert data["worst"][0]["score"] == 6.9


def test_dashboard_floor_defaults_to_threshold(tmp_path: Path) -> None:
    book = _book(tmp_path, {1: _eval({"engagement": 7.2}, 7.5)})
    assert build_dashboard(book, threshold=7.5).aggregate.below_floor == 1
    assert build_dashboard(book, threshold=7.5, floor=7.0).aggregate.below_floor == 0


def test_dimensions_view_without_evals(tmp_path: Path) -> None:
    book = _book(tmp_path, {})
    assert "No per-chapter eval logs" in render_dimensions(build_dashboard(book))


def test_next_step_revises_a_passing_mean_with_a_failing_dimension() -> None:
    s = PipelineState(book="a", phase="drafting", last_chapter_number=7,
                      last_chapter_score=7.8, chapters_total=19,
                      last_chapter_low=("sense_of_place", 6.9))
    ns = next_step(s)
    assert ns.command == "/autonovel:revise 7 --book a"
    assert "sense_of_place 6.9" in ns.rationale and "7.0 floor" in ns.rationale


def test_next_step_floor_is_configurable() -> None:
    s = PipelineState(book="a", phase="drafting", last_chapter_number=7,
                      last_chapter_score=7.8, chapters_total=19,
                      last_chapter_low=("sense_of_place", 6.9), dimension_floor=6.5)
    ns = next_step(s)
    assert ns.command == "/autonovel:draft 8 --book a"
    assert "lowest: sense_of_place 6.9" in ns.rationale


def test_next_actions_flag_floor_and_unchecked_reader(review_phase_book) -> None:
    series, book = review_phase_book
    eval_dir = series / "books" / book / "eval_logs"
    (eval_dir / "20990101_000000_ch03_eval.json").write_text(json.dumps(_eval(
        {"sense_of_place": 6.4, "engagement": 8.0}, 7.6,
        first_reader={"serious_items_first": ["a", "b", "c"]})), encoding="utf-8")
    actions = next_actions.enumerate_actions(SeriesLayout(root=series), book=book)
    floor = [a for a in actions if a.title.startswith("Dimension under")]
    assert floor and floor[0].priority == "MEDIUM"
    assert "ch 3 place 6.4" in floor[0].title
    assert floor[0].command == f"/autonovel:revision-pass --chapters 3 --book {book}"
    reread = [a for a in actions if a.title.startswith("Cold-reader items never re-read")]
    assert reread and "ch 3 (3)" in reread[0].title


def test_summary_query_low_score(tmp_path: Path) -> None:
    book = _book(tmp_path, {1: _eval({"sense_of_place": 6.9}, 7.8),
                            2: _eval({"engagement": 7.6}, 7.7)})
    rows = summarize_chapters(book)
    assert [r.chapter for r in query(rows, "low_score < 7.0")] == [1]
    assert [r.chapter for r in query(rows, 'low_dim == "engagement"')] == [2]
