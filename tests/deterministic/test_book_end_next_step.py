"""The step after a book's last outlined chapter (kingmaker2, 2026-10-22).

A 19-chapter book finished drafting and `_end` offered `/autonovel:draft
20`: nothing told the next-step logic how many chapters the outline
declares, and `state.json` still read `phase: seed`, `chapters_total: 0`.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.housekeeping import lifecycle
from autonovel.paths import SeriesLayout, outline_chapter_numbers


def _outline_with(book_root: Path, n: int) -> None:
    blocks = "\n\n".join(f"## Chapter {i} — Title {i}\n\n- story_time: 2020-01-{i:02d}\n- beats: x"
                         for i in range(1, n + 1))
    (book_root / "outline.md").write_text(f"# Outline\n\n{blocks}\n", encoding="utf-8")


def test_outline_chapter_numbers_reads_h2_and_h3(tmp_path: Path) -> None:
    p = tmp_path / "outline.md"
    p.write_text("# O\n\n## Act I\n\n### Chapter 1 — A\n\n## Chapter 2\n\n## Chapter 3 — C\n",
                 encoding="utf-8")
    assert outline_chapter_numbers(p) == [1, 2, 3]
    assert outline_chapter_numbers(tmp_path / "missing.md") == []


def test_last_outlined_chapter_leads_to_developmental_edit(
    review_phase_book: tuple[Path, str],
) -> None:
    series, book = review_phase_book
    book_root = series / "books" / book
    _outline_with(book_root, 10)  # the fixture drafts and scores ch 1-10
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    assert ns.command == f"/autonovel:developmental-edit --book {book}"
    assert "draft 11" not in ns.command

    (book_root / "edit_logs").mkdir(exist_ok=True)
    (book_root / "edit_logs" / "editor_letter.md").write_text("# Editor's letter\n", encoding="utf-8")
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    # The letter is written; the structure review is next (whole_book.py).
    assert ns.command == f"/autonovel:structure-review --book {book}"


def test_mid_book_still_advances(review_phase_book: tuple[Path, str]) -> None:
    series, book = review_phase_book
    _outline_with(series / "books" / book, 12)
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    assert ns.command == f"/autonovel:draft 11 --book {book}"


def test_end_syncs_book_state(review_phase_book: tuple[Path, str]) -> None:
    series, book = review_phase_book
    book_root = series / "books" / book
    _outline_with(book_root, 10)
    state_path = book_root / "state.json"
    assert json.loads(state_path.read_text())["phase"] == "seed"
    lifecycle._sync_book_state(SeriesLayout(root=series), book)
    state = json.loads(state_path.read_text())
    assert state["chapters_drafted"] == 10
    assert state["chapters_total"] == 10
    assert state["phase"] == "revision"

    # Phase never moves backwards.
    state["phase"] = "review"
    state_path.write_text(json.dumps(state))
    lifecycle._sync_book_state(SeriesLayout(root=series), book)
    assert json.loads(state_path.read_text())["phase"] == "review"
