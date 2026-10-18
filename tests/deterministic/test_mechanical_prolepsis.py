"""Tier-1 tests for `autonovel mechanical prolepsis` (candidate narrator
flash-forwards, the counter behind /autonovel:developmental-edit).

Bug class: on kingmaker an editor's full read traced the "string of
anecdotes" feel to narrator flash-forwards in 19 of 24 chapters, which
no reviewer had counted (and which the editor himself first undercounted
by eye at 17). The helper is a candidate generator, so these tests pin
what it must find, what it must skip, and that it never gates anything.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.mechanical import prolepsis
from autonovel.mechanical.__main__ import main as mech_main


def _chapter(book: Path, n: int, story_time: str, body: str) -> None:
    ch = book / "chapters"
    ch.mkdir(parents=True, exist_ok=True)
    (ch / f"ch_{n:02d}.md").write_text(
        f"---\nbook: demo\nchapter: {n}\nstory_time: {story_time}\n---\n\n{body}\n",
        encoding="utf-8")


def test_year_past_story_time_with_would_is_a_candidate() -> None:
    hits = prolepsis.scan_text(
        "He burned the letter. In 1519 he would buy an Empire with sums anybody could read.",
        end_year=1473)
    assert len(hits) == 1
    assert hits[0].year == 1519
    assert "would" in hits[0].reason


def test_year_inside_story_time_is_not_a_candidate() -> None:
    assert prolepsis.scan_text(
        "In 1473 he would often count the knives before bed.", end_year=1475) == []


def test_relative_jump_is_a_candidate_without_a_year() -> None:
    hits = prolepsis.scan_text(
        "Thirty years later the water-stairs would be the busiest steps in Venice.",
        end_year=None)
    assert [h.reason for h in hits] == ["relative jump"]


def test_scene_jump_inside_the_chapter_span_is_skipped() -> None:
    # "six years later" inside a chapter whose story_time runs to 1485 is
    # the chapter moving forward, not the narrator flashing forward.
    assert prolepsis.scan_text(
        "In March 1485, six years later, Jakob sat on the bench outside the chamber.",
        end_year=1485) == []


def test_dialogue_is_ignored() -> None:
    body = ('“In 1525 they will all be dead,” he said. '
            '"Thirty years later nobody will remember," she answered.')
    assert prolepsis.scan_text(body, end_year=1474) == []


def test_contracted_would_counts() -> None:
    hits = prolepsis.scan_text("In October 1518 they’d have a guest from Wittenberg.",
                               end_year=1510)
    assert len(hits) == 1 and hits[0].year == 1518


def test_scan_book_reports_chapters_and_counts(tmp_path: Path) -> None:
    book = tmp_path / "demo"
    _chapter(book, 1, "1473-09", "He counted. In 1519 he would buy an Empire.")
    _chapter(book, 2, "1474-06 to 1474-09", "Scutari held. Nobody bid.")
    _chapter(book, 3, "1474-12 to 1475-01",
             "On 4 April 1525 the League's army would break a band at Leipheim.")
    rep = prolepsis.scan_book(book)
    assert rep["chapter_count"] == 3
    assert rep["chapters_with_candidates"] == [1, 3]
    assert rep["candidate_count"] == 2
    assert rep["chapters"][2]["story_time_end_year"] == 1475


def test_summary_files_are_not_scanned(tmp_path: Path) -> None:
    book = tmp_path / "demo"
    _chapter(book, 1, "1473-09", "Nothing ahead of its time here.")
    (book / "chapters" / "ch_01.summary.md").write_text(
        "Promise line: in 1519 he would buy an Empire.", encoding="utf-8")
    assert prolepsis.scan_book(book)["candidate_count"] == 0


def test_cli_json_and_markdown(tmp_path: Path, capsys) -> None:
    book = tmp_path / "demo"
    _chapter(book, 1, "1473-09", "In 1519 he would buy an Empire.")
    assert mech_main(["prolepsis", str(book)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["candidate_count"] == 1
    assert mech_main(["prolepsis", str(book), "--format", "markdown"]) == 0
    md = capsys.readouterr().out
    assert md.startswith("# Prolepsis candidates")
    assert "## Chapter 1" in md


def test_cli_missing_chapters_dir_exits_2(tmp_path: Path) -> None:
    assert mech_main(["prolepsis", str(tmp_path / "nope")]) == 2
