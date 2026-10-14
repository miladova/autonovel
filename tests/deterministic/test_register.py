"""Tier-1 tests for the register scanner (`autonovel mechanical register`).

A candidate generator for the structural markers of prose register —
contraction ratio, Flesch-Kincaid grade of narration vs dialogue,
formal connectives, utterance length, explaining-to-the-listener
lines. Never a gate: the book's voice.md declares the band, the judge
decides. Born 2026-10-14 when a plain-register book read as "1500s
style" through three revision passes with 27 uncontracted negatives
and no "didn't" in one chapter, and nothing in the pipeline could see
it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from autonovel.mechanical import register as rg
from autonovel.mechanical.period_register import (
    build_syntax_drift_report,
    declared_fk_band,
)

FORMAL = (
    'Jakob did not ask whose. He could not finish the sum, and perhaps that '
    'was the point. That part Jakob had decided on the steps. He watched it '
    'hung, tagged and numbered, and wondered whether the clerk would notice.\n'
    '\n'
    '"That\'s San Giacomo\'s bell, at the end there, and you\'ve got a quarter '
    'of an hour before it rings, and when it rings every table closes and '
    'every broker goes home and the price you did not pay is the price you '
    'will pay tomorrow," Tucher said.\n'
)

SPOKEN = (
    "Jakob didn't ask whose. He couldn't finish the sum, and maybe that was "
    "the point. He'd decided that part on the steps. He watched the clerk "
    "hang it, tag it and number it.\n"
    '\n'
    '"Pepper\'s up," Tucher said. "Two ducats so far. Four by closing."\n'
)


def test_splits_narration_and_dialogue() -> None:
    rep = rg.scan_chapter(SPOKEN, chapter=1)
    assert rep.dialogue_words > 0 and rep.narration_words > 0
    assert rep.utterances == 2
    assert rep.words == rep.narration_words + rep.dialogue_words


def test_formal_prose_is_flagged_and_spoken_is_not() -> None:
    formal = rg.scan_chapter(FORMAL, chapter=1)
    spoken = rg.scan_chapter(SPOKEN, chapter=1)
    assert formal.uncontracted_negatives >= 2
    assert spoken.uncontracted_negatives == 0
    assert spoken.contractions >= 3
    kinds = {c.kind for c in formal.candidates}
    assert {"uncontracted-negative", "formal", "fronted", "elliptical",
            "long-utterance", "listener-explaining"} <= kinds
    assert not {c.kind for c in spoken.candidates} & {"formal", "fronted", "elliptical", "listener-explaining"}


def test_contraction_ratio() -> None:
    assert rg.scan_chapter(SPOKEN).contraction_ratio == 1.0
    f = rg.scan_chapter(FORMAL)
    assert f.contraction_ratio is not None and f.contraction_ratio < 0.5


def test_dialogue_only_counts_quoted_text_for_uncontracted() -> None:
    """'did not' inside dialogue is speech, not narration, and must not
    count against the narration ratio."""
    rep = rg.scan_chapter('"I did not do it," she said. He didn\'t believe her.\n')
    assert rep.uncontracted_negatives == 0
    assert rep.contractions == 1


def test_long_utterance_threshold() -> None:
    long_line = '"' + " ".join(["word"] * 45) + '"\n'
    assert any(c.kind == "long-utterance" for c in rg.scan_chapter(long_line).candidates)
    assert not any(c.kind == "long-utterance"
                   for c in rg.scan_chapter(long_line, long_utterance=50).candidates)


def test_curly_quotes_normalised() -> None:
    rep = rg.scan_chapter("“That’s the bell over there,” he said.\n")
    assert rep.utterances == 1
    assert any(c.kind == "listener-explaining" for c in rep.candidates)


def test_build_report_and_cli(tmp_path: Path) -> None:
    book = tmp_path / "b"
    (book / "chapters").mkdir(parents=True)
    (book / "chapters" / "ch_01.md").write_text("---\nchapter: 1\n---\n\n" + FORMAL, encoding="utf-8")
    (book / "chapters" / "ch_02.md").write_text("---\nchapter: 2\n---\n\n" + SPOKEN, encoding="utf-8")
    rep = rg.build_report(book)
    assert [c.chapter for c in rep.chapters] == [1, 2]
    only = rg.build_report(book, chapter=2)
    assert [c.chapter for c in only.chapters] == [2]
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "register", str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["chapters"][0]["uncontracted_negatives"] >= 2
    assert payload["chapters"][1]["contraction_ratio"] == 1.0
    md = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "register", str(book)],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "Register scan" in md and "listener-explaining" in md


# ---------------------------------------------------- syntax-drift band

def test_declared_fk_band_parses_dash_variants() -> None:
    assert declared_fk_band("FK grade band: 5–8") == (5.0, 8.0)
    assert declared_fk_band("fk grade band: 6-7.5") == (6.0, 7.5)
    assert declared_fk_band("FK grade band: 8 to 5") == (5.0, 8.0)
    assert declared_fk_band("no band here") is None


def test_syntax_drift_prefers_declared_band_over_voice_prose(tmp_path: Path) -> None:
    book = tmp_path / "b"
    (book / "chapters").mkdir(parents=True)
    # A voice file whose own prose is dense but which declares a plain band.
    (book / "voice.md").write_text(
        "Notwithstanding the considerable complexity of the aforementioned "
        "considerations, the narrator's register remains unpretentious. "
        "FK grade band: 5–8\n", encoding="utf-8")
    plain = "He walked in. She looked up. The room was cold. Nobody spoke for a while. " * 8
    (book / "chapters" / "ch_01.md").write_text("---\nchapter: 1\n---\n\n" + plain, encoding="utf-8")
    rep = build_syntax_drift_report(book)
    assert rep.baseline_source == "voice.md:band"
    assert rep.baseline == 6.5
    assert rep.threshold == 1.5  # half the band width


def test_syntax_drift_grades_narration_only(tmp_path: Path) -> None:
    """Dialogue reads lower than narration in every register; the drift
    report is about the narrator, so quoted speech is stripped."""
    narration = ("The magistrate considered the sealed correspondence carefully before "
                 "answering, weighing the consequences of every alternative. ") * 6
    chatter = '"No." "Yes." "Go." "Stay." "Now." "Why?" ' * 20
    book = tmp_path / "b"
    (book / "chapters").mkdir(parents=True)
    (book / "chapters" / "ch_01.md").write_text("---\nchapter: 1\n---\n\n" + narration, encoding="utf-8")
    (book / "chapters" / "ch_02.md").write_text("---\nchapter: 2\n---\n\n" + narration + chatter, encoding="utf-8")
    (book / "chapters" / "ch_03.md").write_text("---\nchapter: 3\n---\n\n" + narration, encoding="utf-8")
    rep = build_syntax_drift_report(book)
    grades = dict(rep.chapter_grades)
    assert grades[1] == grades[2] == grades[3]
