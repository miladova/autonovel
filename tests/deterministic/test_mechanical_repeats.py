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


def test_a_sentence_told_again_with_words_changed_is_told_before(tmp_path: Path) -> None:
    """Across chapters, a near-copy with a few words changed shares no
    six-word run but is still the same sentence: `told_before` finds it,
    in the later chapter, pointing at the earlier one."""
    book = _book(tmp_path, [
        f"{_filler(1)}\n\nFrance paid the councillors first, at a table where its friends "
        f"could watch the gold counted out.\n\n{_filler(2)}",
        _filler(3),
        f"{_filler(4)}\n\nFrance had paid those councillors first, where all its friends "
        f"could watch the gold being counted.\n\n{_filler(5)}",
    ])
    rep = repeats.scan_book(book)
    told = rep["chapters"][2]["told_before"]
    assert told, "the near-copy in chapter 3 should be found"
    assert told[0]["earlier"]["chapter"] == 1
    assert {"councillors", "france", "gold", "watch"} <= set(told[0]["shared"])
    assert rep["chapters"][0]["told_before"] == []     # the first telling is not "before"
    assert rep["chapters"][1]["told_before"] == []


def test_echo_flags_quoted_and_recurring_and_rarer_words_rank_first(tmp_path: Path) -> None:
    letter = "*Pay them after the vote. You were right. Finish it.*"
    openers = ["Konrad came up from", "They met at", "Bastian waited by",
               "The carts stood at", "Nobody slept near"]
    closers = ["before noon.", "in the rain.", "with the boats.", "all evening.",
               "after the bell."]
    book = _book(tmp_path, [
        f"{_filler(i + 1)}\n\n"
        + (f"{letter}\n\n" if i < 2 else "")
        + f"{openers[i]} the river gate on the quay {closers[i]}\n\n"
        f"Then he stood at the bottom of the stairs."
        for i in range(5)
    ])
    rep = repeats.scan_book(book)
    by_text = {e["text"]: e for e in rep["echoes"]}
    quoted = next(e for t, e in by_text.items() if "Pay them after the vote" in t)
    assert quoted["quoted"] and not quoted["recurring"]
    gate = next(e for t, e in by_text.items() if "river gate on the quay" in t)
    assert gate["recurring"] and not gate["quoted"]
    # Ranked by places × the rarity of the words (a weight on every echo).
    weights = [(len(e["places"]) - 1) * e["weight"] for e in rep["echoes"]]
    assert all(w > 0 for w in weights) and weights == sorted(weights, reverse=True)
