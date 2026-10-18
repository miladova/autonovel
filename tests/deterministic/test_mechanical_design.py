"""Tier-1 tests for `autonovel mechanical design-validate` (the design
stage's shape check, DESIGN.md Part II).

Bug class: a book revised four times after an editor's diagnosis still
read as a string of episodes because its design — no single question
posed early, no opponent across acts, wins by wager, a climax others
decide — was never written down, so nothing could check it. These tests
pin the structural promises a design.md must make and the outline
binding (`--outline`).
"""

from __future__ import annotations

import json
from pathlib import Path

from autonovel.mechanical import design
from autonovel.mechanical.__main__ import main as mech_main

GOOD = """# Design — demo

## Author's intent
- "the climax is the election": honoured — ch 10–12.

## Pitch
A clerk learns to read men and buys a crown.

## Dramatic question
- question: Can he buy the crown before the rival does?
- posed_in: 2
- posed_by: the mentor, at the doge's election
- answered_in: 11

## Climax
- chapter: 11
- scene: the chapel, the vote
- action: he pays the last elector with the receipts he kept
- spends: P1, P2, P3
- cost: his name on every bill
- threads: rival, mentor's lesson

## Shape
- pattern: education-and-campaign + many locks
- span: 1473–1519
- chapters: 12
- target_words: 100000

## Controlling idea
Things outweigh promises.

## Protagonist
- name: Jakob
- want: the crown for his candidate
- need: to be owed by no one
- misbelief: everything has a price

## Opponent
- name: Ambrosius Rival
- wants: the same crown, for France
- plan:
  - 1480: apprentices beside him
  - 1518: buys the pledges
- appears_in: 2, 6, 9, 11
- wins_in: 7

## Plants
- P1 speed: news first | plant: ch 1 (the fog) | test: ch 5 | payoff: ch 11
- P2 the book: double entry | plant: ch 3 (the audit) | test: ch 6 | payoff: ch 11
- P3 the cipher: a nomenclator | plant: ch 4 (the letter) | test: ch 8 | payoff: ch 11
- P4 the jewel: things not promises | plant: ch 5 (the pawn) | payoff: ch 12

## Rehearsals
- R1 the doge (ch 2–3): watches a bought election | teaches: P1 | outcome: succeeds — he sees how
- R2 the Diet (ch 8–9): the pledges | teaches: P2, P3 | outcome: fails — the promises die with the Emperor

## Cast
### Jakob — protagonist
- want: the crown
- fear: being owed
- secret: the receipts
- entrance: ch 1, counting knives in the fog
### Mentor — mentor
- want: a son
- fear: the Ten
- secret: he reads the Germans' letters
- entrance: ch 1, at the weighing

## Sequences
- S1 (ch 1–2) Venice: will the boy last? | hands on: he is noticed
- S2 (ch 3–4) the books: can he keep them? | hands on: he keeps a secret book
- S3 (ch 5–6) the mines: | hands on: metal
- S4 (ch 7–8) the rival wins: | hands on: the pledges
- S5 (ch 9–10) the race: | hands on: the money moves
- S6 (ch 11–12) the vote and after

## Clocks
- the election day

## Stakes ladder
| Act | Chapters | Stake | Higher because |
|---|---|---|---|
| I | 1-4 | a place | — |
| II | 5-8 | the firm | more |
| III | 9-12 | the Empire | most |

## Reader questions
- end of I: will the rival get there first?

## Places
### Venice
- use: the city that reads letters
- signature: bells, fog
- arrival: ch 1

## Voice
- register: modern

## Genre contract
- clock: ch 9

## Design tests
- D1 pass: fits a page
- D2 pass: spends P1–P3
- D3 pass: ch 2
- D4 pass: every sequence hands on
- D5 pass: rival in every act
- D6 pass: all planted
- D7 pass: R2 fails
- D8 pass: cast complete
- D9 pass: span earned
- D10 pass: questions
- D11 pass: places work
- D12 pass: no luck
- D13 pass: intent honoured
- D14 pass: cold reader retold it
"""


def _book(tmp: Path, text: str = GOOD, outline: str | None = None) -> Path:
    b = tmp / "demo"
    b.mkdir()
    (b / "design.md").write_text(text, encoding="utf-8")
    if outline is not None:
        (b / "outline.md").write_text(outline, encoding="utf-8")
    return b


def test_good_design_passes(tmp_path: Path) -> None:
    rep = design.check(_book(tmp_path))
    assert rep.ok, rep.errors
    s = rep.summary
    assert s["chapters"] == 12 and s["climax"] == 11 and s["posed_in"] == 2
    assert s["climax_spends"] == ["P1", "P2", "P3"]
    assert [p["id"] for p in s["plants"]] == ["P1", "P2", "P3", "P4"]
    assert s["acts"] == ["I", "II", "III"]
    assert s["cast"] == ["Jakob", "Mentor"]


def test_question_posed_late_is_an_error(tmp_path: Path) -> None:
    rep = design.check(_book(tmp_path, GOOD.replace("- posed_in: 2", "- posed_in: 7")))
    assert any("after the first quarter" in e for e in rep.errors)


def test_climax_must_spend_three_known_plants(tmp_path: Path) -> None:
    rep = design.check(_book(tmp_path, GOOD.replace("- spends: P1, P2, P3", "- spends: P1, P9")))
    assert any("spends 1 known plant" in e for e in rep.errors)
    assert any("P9" in e and "not in ## Plants" in e for e in rep.errors)


def test_plant_must_come_before_payoff(tmp_path: Path) -> None:
    bad = GOOD.replace("| plant: ch 4 (the letter) | test: ch 8 | payoff: ch 11",
                       "| plant: ch 11 (the letter) | payoff: ch 4")
    rep = design.check(_book(tmp_path, bad))
    assert any("P3: planted in ch 11 but pays in ch 4" in e for e in rep.errors)


def test_opponent_missing_from_an_act_and_late_win(tmp_path: Path) -> None:
    bad = GOOD.replace("- appears_in: 2, 6, 9, 11", "- appears_in: 2, 3").replace(
        "- wins_in: 7", "- wins_in: 11")
    rep = design.check(_book(tmp_path, bad))
    assert any("not on stage in act(s) II, III" in e for e in rep.errors)
    assert any("not before the climax" in e for e in rep.errors)


def test_rehearsals_need_a_failure(tmp_path: Path) -> None:
    rep = design.check(_book(tmp_path, GOOD.replace("outcome: fails —", "outcome: succeeds —")))
    assert any("none has an outcome that fails" in e for e in rep.errors)


def test_failed_or_missing_design_test_is_an_error(tmp_path: Path) -> None:
    bad = GOOD.replace("- D4 pass: every sequence hands on", "- D4 fail: S3 settles itself").replace(
        "- D14 pass: cold reader retold it\n", "")
    rep = design.check(_book(tmp_path, bad))
    assert any("D4 fails" in e for e in rep.errors)
    assert any("D14 not recorded" in e for e in rep.errors)


def test_sequence_gap_and_redesign_ledgers(tmp_path: Path) -> None:
    bad = GOOD.replace("- S5 (ch 9–10) the race: | hands on: the money moves\n", "").replace(
        "- target_words: 100000", "- target_words: 100000\n- redesign_of: old")
    rep = design.check(_book(tmp_path, bad))
    assert any("uncovered" in e and "9, 10" in e for e in rep.errors)
    assert any("## Keep ledger" in e for e in rep.errors)
    assert any("## Fault ledger" in e for e in rep.errors)


def test_outline_binding(tmp_path: Path) -> None:
    chapters = []
    for n in range(1, 13):
        lines = [f"## Chapter {n} — T", "- story_time: 1473", "- events: []"]
        if n == 1:
            lines.append("- plants: [P1]")
        if n == 11:
            lines.append("- payoffs: [P1, P2]")   # P3 missing
        if n in (2, 6, 9, 11):
            lines.append("- beats:\n  - Rival waits")
        chapters.append("\n".join(lines))
    outline = ("# Outline\n\n## Spine\n- question: Can he buy the crown before the rival does?\n\n"
               + "\n\n".join(chapters) + "\n")
    rep = design.check(_book(tmp_path, outline=outline), outline=True)
    errs = "\n".join(rep.errors)
    assert "outline ch 11: `- payoffs:` does not list P3" in errs
    assert "outline ch 3: `- plants:` does not list P2" in errs
    assert "outline ch 1: `- plants:` does not list P1" not in errs
    assert not any("Spine question differs" in w for w in rep.warnings)


def test_cli_exit_codes_and_markdown(tmp_path: Path, capsys) -> None:
    b = _book(tmp_path)
    assert mech_main(["design-validate", str(b)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert mech_main(["design-validate", str(b), "--format", "markdown"]) == 0
    assert capsys.readouterr().out.startswith("# design-validate")
    (b / "design.md").write_text(GOOD.replace("- posed_in: 2", "- posed_in: 9"), encoding="utf-8")
    assert mech_main(["design-validate", str(b)]) == 1
    capsys.readouterr()
    empty = tmp_path / "none"
    empty.mkdir()
    assert mech_main(["design-validate", str(empty)]) == 2
