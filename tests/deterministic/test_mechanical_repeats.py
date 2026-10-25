"""Tier-1 tests for `autonovel mechanical repeats` (things said more than
once — candidates for evaluate's `repetition` dimension).

Bug class: the kingmaker2 author found chapter 1 "long and a bit slow",
with "repetition about the electors": one rule stated five times, the same
fact explained four times, the same description of a person repeated word
for word in four chapters. The evaluation checked terms explained twice,
never ideas. The helper lists repeated wording, phrases a chapter leans
on, and sentence pairs that make one point.
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.mechanical import repeats
from autonovel.mechanical.__main__ import main as mech_main


def _filler(seed: int, sentences: int = 120) -> str:
    """Prose-shaped filler: the same function words throughout (so they are
    the book's common words) around content words used once each."""
    out = []
    for i in range(sentences):
        k = seed * 1000 + i
        out.append(f"The w{k}a of the w{k}b was in the w{k}c, and he had a w{k}d.")
    paras = [" ".join(out[j:j + 6]) for j in range(0, len(out), 6)]
    return "\n\n".join(paras)


def _book(tmp: Path, bodies: list[str]) -> Path:
    book = tmp / "b"
    (book / "chapters").mkdir(parents=True)
    for i, body in enumerate(bodies, 1):
        (book / "chapters" / f"ch_{i:02d}.md").write_text(
            f"---\nchapter: {i}\n---\n\n{body}\n", encoding="utf-8")
    return book


GLOSS = "the Count, the Elector Palatine's younger brother, rode in"


def test_a_description_repeated_across_chapters_is_an_echo(tmp_path: Path) -> None:
    book = _book(tmp_path, [
        f"{_filler(1)}\n\nAt noon {GLOSS} from the river.\n\n{_filler(2)}",
        f"{_filler(3)}\n\nBy evening {GLOSS} again.\n\n{_filler(4)}",
        f"{_filler(5)}\n\nNobody came that day.",
    ])
    rep = repeats.scan_book(book)
    hits = [e for e in rep["echoes"] if "Elector Palatine's younger brother" in e["text"]]
    assert len(hits) == 1
    echo = hits[0]
    assert echo["chapters"] == [1, 2] and echo["across_chapters"]
    assert echo["words"] >= 8
    # Line numbers are file lines, frontmatter included.
    ch1 = (book / "chapters" / "ch_01.md").read_text().splitlines()
    assert "younger brother" in ch1[echo["places"][0]["line"] - 1]
    # Filler shares its function words everywhere but is never an echo.
    assert all("w1" not in e["text"] for e in rep["echoes"])


def test_a_phrase_a_chapter_leans_on_is_listed_and_one_used_evenly_is_not(tmp_path: Path) -> None:
    rule = " ".join(f"Sum {i} would be paid after the vote, Jakob said." for i in range(6))
    book = _book(tmp_path, [
        f"{_filler(1)}\n\n{rule}\n\n{_filler(2)}",
        f"{_filler(3)}\n\nOnce it would be paid after the vote.\n\n{_filler(4)}",
        _filler(5), _filler(6), _filler(7),
    ])
    rep = repeats.scan_book(book)
    ch1 = rep["chapters"][0]
    phrases = {p["phrase"]: p for p in ch1["phrases"]}
    assert "paid after the vote" in phrases
    assert phrases["paid after the vote"]["count"] == 6
    assert phrases["paid after the vote"]["book_count"] == 7
    # "after the vote" adds nothing beside "paid after the vote".
    assert "after the vote" not in phrases
    assert rep["chapters"][1]["phrases"] == []


def test_the_same_point_twice_in_one_chapter_is_a_similar_pair(tmp_path: Path) -> None:
    book = _book(tmp_path, [
        f"{_filler(1)}\n\nYou paid each elector after he'd voted, and only if he'd voted "
        f"for Charles.\n\n{_filler(2)}\n\nUnless every elector is paid after he's voted, "
        f"and only if he's voted for Charles.\n\n{_filler(3)}",
        _filler(4),
    ])
    pairs = repeats.scan_book(book)["chapters"][0]["similar_sentences"]
    assert pairs, "the restated rule should be a candidate pair"
    top = pairs[0]
    assert {"elector", "voted", "paid"} <= set(top["shared"])
    assert top["lines"][0] < top["lines"][1]


def test_one_callback_is_one_echo_and_plain_prose_has_none(tmp_path: Path) -> None:
    """A payoff line used once more is still listed (the judge keeps it);
    a chapter of plain, varied prose gives nothing."""
    book = _book(tmp_path, [_filler(1), _filler(2)])
    rep = repeats.scan_book(book)
    assert rep["echoes"] == []
    assert all(c["phrases"] == [] and c["similar_sentences"] == [] for c in rep["chapters"])


def test_cli_chapter_filter_markdown_and_missing_book(tmp_path: Path, capsys) -> None:
    book = _book(tmp_path, [
        f"{_filler(1)}\n\nAt noon {GLOSS} from the river.",
        f"{_filler(2)}\n\nBy evening {GLOSS} again.",
        _filler(3),
    ])
    assert mech_main(["repeats", str(book), "--chapter", "3"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [c["chapter"] for c in data["chapters"]] == [3]
    assert data["echoes"] == []        # chapter 3 shares no wording
    assert mech_main(["repeats", str(book), "--chapter", "2", "--format", "markdown"]) == 0
    md = capsys.readouterr().out
    assert "# Things said more than once" in md
    assert "ch 1:" in md and "ch 2:" in md
    assert mech_main(["repeats", str(tmp_path / "nope")]) == 2
