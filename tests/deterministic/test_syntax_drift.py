"""Tier-1 tests for the period syntax-drift scanner.

The Flesch-Kincaid formula is well-defined math, so these tests
pin behaviour rather than fixture-prose taste:

  - syllable counting hits the documented edge cases
    (`the`, `little`, silent-e),
  - FK grade rises monotonically with longer sentences /
    longer words,
  - drift detection respects the threshold and the absolute-delta
    semantics,
  - baseline resolution prefers voice.md > seed.txt > median,
  - missing baselines fail closed (no flags) instead of crashing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical.period_register import (
    SyntaxDriftHit,
    _syllables_in_word,
    build_syntax_drift_report,
    flesch_kincaid_grade,
    render_syntax_drift_markdown,
)


# ---------------------------------------------------------- syllables


def test_syllables_simple_words() -> None:
    assert _syllables_in_word("cat") == 1
    assert _syllables_in_word("apple") == 2
    assert _syllables_in_word("banana") == 3


def test_syllables_silent_e_subtracts() -> None:
    assert _syllables_in_word("make") == 1
    assert _syllables_in_word("late") == 1


def test_syllables_le_suffix_adds_back() -> None:
    assert _syllables_in_word("table") == 2
    assert _syllables_in_word("little") == 2


def test_syllables_floor_one() -> None:
    """Even an all-consonant or one-letter word never reports 0."""
    assert _syllables_in_word("the") == 1
    assert _syllables_in_word("rhythm") >= 1


# ---------------------------------------------------------- FK grade


def test_fk_grade_returns_none_for_short_input() -> None:
    assert flesch_kincaid_grade("Hi.") is None
    assert flesch_kincaid_grade("") is None


def test_fk_grade_rises_with_longer_sentences() -> None:
    short = (
        "He walked. She ran. They stopped. He sat. She stood. "
        "They looked. He smiled. She nodded."
    )
    long = (
        "He walked across the courtyard with his friend, "
        "considering whether the messenger had been entirely "
        "honest. He concluded that some particular details "
        "remained unanswered after the magistrate's hearing."
    )
    short_g = flesch_kincaid_grade(short)
    long_g = flesch_kincaid_grade(long)
    assert short_g is not None and long_g is not None
    assert long_g > short_g


def test_fk_grade_strips_frontmatter() -> None:
    """A chapter file with frontmatter shouldn't include the YAML
    in its FK calculation."""
    body = "He walked across the courtyard with his friend. " * 5
    plain = body
    fronted = "---\nchapter: 1\nstatus: drafted\n---\n\n" + body
    plain_g = flesch_kincaid_grade(plain)
    fronted_g = flesch_kincaid_grade(fronted)
    assert plain_g == fronted_g


# ---------------------------------------------------------- build_syntax_drift_report


def _seed_book(tmp_path: Path, *, voice: str | None = None,
                seed: str | None = None,
                chapters: dict[int, str] | None = None) -> Path:
    book = tmp_path / "b"
    book.mkdir(parents=True)
    if voice is not None:
        (book / "voice.md").write_text(voice, encoding="utf-8")
    if seed is not None:
        (book / "seed.txt").write_text(seed, encoding="utf-8")
    chapters_dir = book / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    for n, prose in (chapters or {}).items():
        (chapters_dir / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\n---\n\n{prose}\n", encoding="utf-8")
    return book


_LITERARY = (
    "He considered the magistrate's silence carefully, weighing the "
    "consequences of speaking before the apothecary returned with the "
    "sealed letter that had arrived from Augsburg the previous Thursday "
    "afternoon, and he wondered, not for the first time, whether the "
    "messenger had been entirely truthful with him."
) * 4

_TERSE = (
    "He walked. She ran. They stopped. He sat. She stood. "
    "They looked. He smiled. She nodded. He left. She stayed."
) * 5


def test_baseline_prefers_seed_over_voice_prose(tmp_path: Path) -> None:
    """2026-10-14: the voice file is a rules document, not a sample of
    the register, so its own prose is the LAST baseline, after a
    declared `FK grade band` and after seed.txt."""
    book = _seed_book(tmp_path, voice=_LITERARY, seed=_TERSE,
                       chapters={1: _LITERARY})
    report = build_syntax_drift_report(book)
    assert report.baseline_source == "seed.txt"


def test_baseline_uses_voice_prose_only_as_last_resort(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=_LITERARY, seed=None,
                       chapters={1: _LITERARY})
    report = build_syntax_drift_report(book)
    assert report.baseline_source == "voice.md"


def test_baseline_declared_band_wins(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=_LITERARY + "\nFK grade band: 5–8\n",
                       seed=_TERSE, chapters={1: _TERSE})
    report = build_syntax_drift_report(book)
    assert report.baseline_source == "voice.md:band"
    assert report.baseline == 6.5 and report.threshold == 1.5


def test_baseline_falls_back_to_seed(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=None, seed=_LITERARY,
                       chapters={1: _LITERARY})
    report = build_syntax_drift_report(book)
    assert report.baseline_source == "seed.txt"


def test_baseline_falls_back_to_median(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=None, seed=None,
                       chapters={1: _LITERARY, 2: _LITERARY,
                                  3: _TERSE})
    report = build_syntax_drift_report(book)
    assert report.baseline_source == "median-of-chapters"
    assert report.baseline is not None


def test_no_baseline_when_too_few_chapters(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=None, seed=None,
                       chapters={1: _TERSE})
    report = build_syntax_drift_report(book)
    assert report.baseline is None
    assert report.drift_hits == []


def test_drift_flagged_when_above_threshold(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=_LITERARY,
                       chapters={1: _LITERARY, 2: _TERSE})
    report = build_syntax_drift_report(book, threshold=1.0)
    flagged = {h.chapter for h in report.drift_hits}
    # ch1 matches voice; ch2 is much flatter, should flag.
    assert 2 in flagged
    assert 1 not in flagged


def test_drift_threshold_respected(tmp_path: Path) -> None:
    """Doubling the threshold must reduce or hold the flagged set."""
    book = _seed_book(tmp_path, voice=_LITERARY,
                       chapters={1: _LITERARY, 2: _TERSE})
    tight = build_syntax_drift_report(book, threshold=0.5)
    loose = build_syntax_drift_report(book, threshold=5.0)
    assert len(loose.drift_hits) <= len(tight.drift_hits)


def test_drift_chapter_grades_in_order(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=_LITERARY,
                       chapters={3: _LITERARY, 1: _LITERARY, 2: _TERSE})
    report = build_syntax_drift_report(book)
    chapter_nums = [n for n, _ in report.chapter_grades]
    assert chapter_nums == [1, 2, 3]


# ---------------------------------------------------------- render


def test_render_no_baseline_message(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, chapters={1: _TERSE})
    out = render_syntax_drift_markdown(build_syntax_drift_report(book),
                                          book="b")
    assert "Cannot compute baseline" in out


def test_render_includes_table_and_flags(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=_LITERARY,
                       chapters={1: _LITERARY, 2: _TERSE})
    out = render_syntax_drift_markdown(build_syntax_drift_report(book),
                                          book="b")
    assert "Period syntax drift — b" in out
    assert "FK grade" in out
    assert "⚠️" in out


# ---------------------------------------------------------- CLI


def test_cli_syntax_drift_markdown(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=_LITERARY,
                       chapters={1: _LITERARY})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "syntax-drift",
         str(book)],
        capture_output=True, text=True, check=True,
    )
    assert "Period syntax drift" in proc.stdout


def test_cli_syntax_drift_json(tmp_path: Path) -> None:
    book = _seed_book(tmp_path, voice=_LITERARY,
                       chapters={1: _LITERARY, 2: _TERSE})
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "syntax-drift",
         str(book), "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["baseline"] is not None
    assert payload["baseline_source"] == "voice.md"  # no seed, no band: last resort
    assert len(payload["chapter_grades"]) == 2
