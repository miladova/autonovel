"""Tier-2 contract: "say each thing once" reaches every producer and
consumer.

Bug class: the kingmaker2 author found version 3's chapter 1 "long and a
bit slow" — the same fact explained four times, one rule stated five
times — and a sweep found the same in nearly every chapter. Every check
had passed it: evaluate asked whether a *term* was explained twice, the
cold reader had no category for being told again, revise fixed a lost
reader by adding a second explanation beside the first, and the brief
had nowhere to put a repeat. These assertions keep each surface wired.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CRAFT = ROOT / "src" / "autonovel" / "templates" / "series" / "shared" / "craft"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_prose_md_states_the_rule_with_its_source() -> None:
    prose = _flat((CRAFT / "PROSE.md").read_text(encoding="utf-8"))
    assert "**Say it once.**" in prose
    assert "Once Is Usually Enough" in prose
    assert "never adds a second statement beside the first" in prose
    assert "§7.9 Said more than once" in prose       # the judge's checklist


def test_evaluate_scores_repetition_from_the_scanner() -> None:
    ev = _read("commands/evaluate.md")
    assert "`sense_of_place`, `repetition`" in _flat(ev)
    assert "autonovel mechanical repeats books/{book} --chapter {N}" in ev
    assert '"story-so-far"' in ev and "keep_line" in ev
    assert "caps the score at 6" in _flat(ev)
    assert "repeated_across_book" in ev               # --full mode
    assert "Forgot who or Told again" in _flat(ev)    # a serious cold-reader item


def test_first_reader_reports_told_again_in_eleven_sections() -> None:
    brief = _flat((CRAFT / "FIRST-READER.md").read_text(encoding="utf-8"))
    assert "6. **Told again**" in brief
    assert "11. **What worked**" in brief
    assert "first five sections" not in brief        # position-free wording
    fr = _flat(_read("commands/first-read.md"))
    assert "eleven sections" in fr and "ten sections" not in fr
    assert "forgot N · told again N · couldn't picture N" in fr
    assert "eleven sections" in _flat(_read("commands/draft.md"))


def test_brief_has_said_already_fed_by_the_scanner() -> None:
    brief = _flat(_read("commands/brief.md"))
    assert "## Said already" in brief
    assert "autonovel mechanical repeats books/{book} --chapter {chapter}" in brief
    assert "not cuts of the genre's payload" in brief


def test_draft_and_revise_say_once_and_replace_not_add() -> None:
    draft = _flat(_read("commands/draft.md"))
    assert "**Say each thing once**" in draft
    assert "**Said-once self-check**" in draft
    assert "autonovel mechanical repeats books/{book} --chapter {chapter}" in draft
    revise = _flat(_read("commands/revise.md"))
    assert "**Replace, don't add.**" in revise
    assert "## Said already" in revise
    assert "autonovel mechanical repeats books/{book} --chapter {chapter}" in revise


def test_editors_and_cutters_use_the_scanner() -> None:
    adv = _read("commands/adversarial-edit.md")
    assert "  - bash\n" in adv.split("---")[1]          # allowed-tools
    assert "autonovel mechanical repeats" in adv
    assert "story so far" in _flat(adv)
    dev = _read("commands/developmental-edit.md")
    assert "autonovel mechanical repeats books/{book}" in dev


def test_historical_guide_cuts_a_second_telling_not_the_first() -> None:
    guide = _flat((CRAFT / "genres" / "historical.md").read_text(encoding="utf-8"))
    assert "Nor is a second telling" in guide
    assert "**`repetition`** marks down a period fact" in guide


def test_score_tables_label_and_group_the_dimension() -> None:
    from autonovel.mechanical.chapter_summary import dimension_label
    from autonovel.mechanical.dashboard import DIMENSION_GROUPS
    assert dimension_label("repetition") == "repeats"
    assert "repetition" in dict(DIMENSION_GROUPS)["Writing"]
