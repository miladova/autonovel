"""The whole-book reviewers in one order after the last chapter (2026-10-23).

The author asked whether the structure review was routine: it wasn't. A
19-chapter book reached its revision pass with no structure review, no
reader panel and no dual-persona review, and the step chain shipped that
morning (letter → revision-pass) would have offered the revision pass
again forever. `whole_book.next_whole_book_step` walks one order.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from autonovel.housekeeping import lifecycle
from autonovel.housekeeping.next_step import PipelineState, next_step
from autonovel.housekeeping.whole_book import (
    WholeBookState, gather, ledger_open_chapters, next_whole_book_step,
)
from autonovel.paths import SeriesLayout

LETTER = """# Editor's letter — X

Body.

## Recommendations ledger

| id | recommendation | chapters | kind | status |
|---|---|---|---|---|
| R1 | Re-enter strands | 3, 5, 7 | in-chapter | staged |
| R2 | Thin names | 14–16 | in-chapter | proposed |
| R3 | Done thing | 9 | in-chapter | done |
| R4 | Back matter | back matter | cross-chapter | proposed |
| R5 | Sibylla | 14-18 | author-decision | decided: leave (a) |
"""


def test_ledger_open_chapters() -> None:
    assert ledger_open_chapters(LETTER) == [3, 5, 7, 14, 15, 16]
    assert ledger_open_chapters("# no ledger\n") == []


def _step(**kw) -> str:
    return next_whole_book_step("b", WholeBookState(**kw)).command


def test_the_order() -> None:
    assert _step() == "/autonovel:developmental-edit --book b"
    assert _step(letter="fresh", letter_open_chapters=[3]) == "/autonovel:structure-review --book b"
    assert _step(letter="fresh", letter_open_chapters=[3], structure="stale") == \
        "/autonovel:structure-review --book b"
    assert _step(letter="fresh", letter_open_chapters=[5, 3], structure="passes") == \
        "/autonovel:revision-pass --chapters 3,5 --book b"
    # A blocking gate's candidates join the letter's chapters in one pass.
    assert _step(letter="fresh", letter_open_chapters=[5], structure="blocks",
                 structure_chapters=[2, 5]) == "/autonovel:revision-pass --chapters 2,5 --book b"
    assert _step(letter="fresh", structure="blocks", structure_reasons=["score 3/5"]) == \
        "/autonovel:revision-pass --chapters structural --book b"
    # After the revision: the gate again (stale), then the second letter.
    assert _step(letter="stale", letter_open_chapters=[3], structure="stale") == \
        "/autonovel:structure-review --book b"
    assert _step(letter="stale", letter_open_chapters=[3], structure="passes") == \
        "/autonovel:developmental-edit --book b"
    # Nothing open and the gate passes: panel, review, typeset.
    assert _step(letter="fresh", structure="passes") == "/autonovel:reader-panel --book b"
    assert _step(letter="fresh", structure="passes", panel="fresh") == "/autonovel:review --book b"
    assert _step(letter="fresh", structure="passes", panel="fresh", review="fresh") == \
        "/autonovel:typeset --book b"


def test_next_step_uses_the_order_after_the_last_chapter() -> None:
    s = PipelineState(book="b", phase="drafting", last_chapter_number=19,
                      last_chapter_score=7.6, chapters_total=19,
                      whole_book=WholeBookState(letter="fresh", letter_open_chapters=[2],
                                                structure="passes"))
    assert next_step(s).command == "/autonovel:revision-pass --chapters 2 --book b"
    s.last_chapter_number = 12
    assert next_step(s).command == "/autonovel:draft 13 --book b"


def _age(path: Path, seconds: int) -> None:
    t = time.time() - seconds
    os.utime(path, (t, t))


def test_gather_reads_the_files(review_phase_book) -> None:
    series, book = review_phase_book
    root = series / "books" / book
    logs = root / "edit_logs"
    logs.mkdir(exist_ok=True)
    for p in (root / "chapters").glob("ch_*.md"):
        _age(p, 3600)
    (logs / "editor_letter.md").write_text(LETTER, encoding="utf-8")
    s = gather(root)
    assert s.letter == "fresh" and s.letter_open_chapters == [3, 5, 7, 14, 15, 16]
    assert s.structure == "missing"
    assert s.panel == "fresh" and s.review in ("fresh", "missing")
    # A chapter rewritten after the letter makes it, and the panel, stale.
    (root / "chapters" / "ch_03.md").write_text(
        (root / "chapters" / "ch_03.md").read_text() + "\nMore.\n", encoding="utf-8")
    s = gather(root)
    assert s.letter == "stale" and s.panel == "stale"
    (logs / "structure_review.json").write_text("{not json", encoding="utf-8")
    assert gather(root).structure == "invalid"


def test_footer_walks_it_on_a_real_layout(review_phase_book) -> None:
    series, book = review_phase_book
    root = series / "books" / book
    blocks = "\n\n".join(f"## Chapter {i} — T\n\n- beats: x" for i in range(1, 11))
    (root / "outline.md").write_text(f"# Outline\n\n{blocks}\n", encoding="utf-8")
    (root / "edit_logs").mkdir(exist_ok=True)
    (root / "edit_logs" / "editor_letter.md").write_text(LETTER, encoding="utf-8")
    ns = lifecycle._next_step_for(SeriesLayout(root=series), book)
    assert ns.command == f"/autonovel:structure-review --book {book}"


def test_commands_name_the_order() -> None:
    root = Path(__file__).resolve().parents[2]
    flat = lambda p: " ".join((root / p).read_text(encoding="utf-8").split())  # noqa: E731
    rp = flat("commands/revision-pass.md")
    assert rp.index("/autonovel:structure-review --book {book} /autonovel:developmental-edit") > 0
    dp = flat("commands/draft-pass.md")
    assert "--no-structure" in dp and "run 5a (the structure review) even without `--deep`" in dp
    de = flat("commands/developmental-edit.md")
    assert "6. Re-read: /autonovel:structure-review --book {book} then /autonovel:developmental-edit" in de
    sr = flat("commands/structure-review.md")
    assert "the whole-book order" in sr
    assert "whole-book order" in flat("commands/help.md")
