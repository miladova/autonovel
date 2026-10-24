"""Tier-1 tests for `autonovel mechanical newcomers` (new names per
chapter — candidates for the reader's map).

Bug class: the author found a chapter that "suddenly introduces several
new characters and locations" and terms never explained. The helper
lists what each chapter introduces and how much lands in its opening.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.mechanical import newcomers
from autonovel.mechanical.__main__ import main as mech_main


def _chapters(tmp: Path, bodies: list[str]) -> Path:
    book = tmp / "b"
    (book / "chapters").mkdir(parents=True)
    for i, body in enumerate(bodies, 1):
        (book / "chapters" / f"ch_{i:02d}.md").write_text(
            f"---\nchapter: {i}\n---\n\n{body}\n", encoding="utf-8")
    return book


def test_names_are_new_only_once_and_keep_their_final_s(tmp_path: Path) -> None:
    book = _chapters(tmp_path, [
        "The rider came through the Einlass to see Jakob in Augsburg. Far away, Charles waited.",
        "Later Jakob rode to Venice, and the Einlass was shut. He met Negro at the gate.",
    ])
    rep = newcomers.scan_book(book)
    ch1 = {n["word"] for n in rep["chapters"][0]["newcomers"]}
    ch2 = {n["word"] for n in rep["chapters"][1]["newcomers"]}
    assert {"Einlass", "Jakob", "Augsburg", "Charles"} <= ch1
    assert ch2 == {"Venice", "Negro"}


def test_sentence_starts_contractions_and_dialogue_openers_are_not_names(tmp_path: Path) -> None:
    book = _chapters(tmp_path, [
        'Snow fell. "Poor man," she said. "I\'ll go." You\'ll see Konrad soon. '
        "Nobody spoke to Konrad."
    ])
    words = {n["word"] for n in newcomers.scan_book(book)["chapters"][0]["newcomers"]}
    assert words == {"Konrad"}


def test_opening_count_and_cli(tmp_path: Path, capsys) -> None:
    filler = " ".join(["word"] * 600)
    book = _chapters(tmp_path, [f"He met Anna and Bruno in Cleves. {filler} Then Dora came."])
    assert mech_main(["newcomers", str(book), "--first-words", "500"]) == 0
    data = json.loads(capsys.readouterr().out)
    ch = data["chapters"][0]
    assert ch["in_opening"] == ["Anna", "Bruno", "Cleves"]
    assert "Dora" in [n["word"] for n in ch["newcomers"]]
    assert mech_main(["newcomers", str(book), "--format", "markdown"]) == 0
    assert "in the opening: Anna, Bruno, Cleves" in capsys.readouterr().out
    assert mech_main(["newcomers", str(tmp_path / "nope")]) == 2


def test_returning_names_after_a_gap(tmp_path: Path) -> None:
    """A name returns when last seen three or more chapters away (the
    default gap of 4), the absence after which draft step 3c re-anchors
    a person. In a book that alternates between two times, a name from
    one strand seen two chapters back is not returning."""
    book = _chapters(tmp_path, [
        "Jakob wrote to Albrecht at Mainz and to Joachim.",
        "In Venice Jakob met Negro.",
        "Then Jakob read what Albrecht wanted, and Negro was far away.",
        "In Venice Negro wrote again.",
        "Jakob rode to Mainz, and Joachim was waiting.",
    ])
    rep = newcomers.scan_book(book)
    assert rep["chapters"][2]["returning"] == []   # Albrecht last seen two chapters back
    ch5 = {r["word"]: r["last_seen_chapter"] for r in rep["chapters"][4]["returning"]}
    assert ch5 == {"Joachim": 1, "Mainz": 1}   # three chapters away
    narrow = newcomers.scan_book(book, gap=2)
    ch3 = {r["word"]: r["last_seen_chapter"] for r in narrow["chapters"][2]["returning"]}
    assert ch3 == {"Albrecht": 1}
    md = newcomers.render_markdown(rep)
    assert "returning after a gap of 4+ chapters: Joachim (last seen ch 1)" in md or "Joachim (last seen ch 1)" in md
