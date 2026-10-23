"""Tier-1 deterministic tests for `autonovel.mechanical.cuts`.

Covers the string-removal paths that `/autonovel:apply-cuts` depends on:
exact match, whitespace-normalised match, ambiguity rejection, short-quote
rejection, and the file-level apply_cuts orchestrator.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from autonovel.mechanical import apply_cuts, collapse_blank_lines, find_and_remove


def test_exact_single_match_removes_quote() -> None:
    text = "Alpha beta gamma. Delta echo foxtrot."
    new, ok, reason = find_and_remove(text, "Delta echo foxtrot.")
    assert ok
    assert reason == ""
    assert "Delta echo foxtrot." not in new
    assert "Alpha beta gamma." in new


def test_ambiguous_exact_match_refuses() -> None:
    text = "I said yes. I said yes. I said yes."
    new, ok, reason = find_and_remove(text, "I said yes.")
    assert not ok
    assert "ambiguous" in reason
    assert new == text


def test_whitespace_normalised_match_succeeds() -> None:
    text = "The cat\nsat   on\tthe mat and purred contentedly in the sun."
    new, ok, reason = find_and_remove(text, "The cat sat on the mat and purred contentedly")
    assert ok, reason
    assert "purred contentedly" not in new


def test_short_quote_is_rejected() -> None:
    text = "Hello world. How are you."
    new, ok, reason = find_and_remove(text, "Hi")
    assert not ok
    assert "not found" in reason or "too short" in reason


def test_collapse_blank_lines() -> None:
    assert collapse_blank_lines("a\n\n\n\nb") == "a\n\nb"
    assert collapse_blank_lines("a\n\nb") == "a\n\nb"


def test_apply_cuts_applies_matching_quotes_and_writes(tmp_path) -> None:
    chapter = tmp_path / "ch_05.md"
    chapter.write_text(
        "The tower fell. He wept for a long time afterwards in the rubble.\n\n"
        "Morning came, cold and grey over the shattered bricks of his home.",
        encoding="utf-8",
    )
    cuts = [
        {
            "quote": "He wept for a long time afterwards in the rubble.",
            "type": "OVER-EXPLAIN",
            "reason": "redundant telling",
            "action": "CUT",
        }
    ]
    stats = apply_cuts(chapter, cuts, overall_fat_percentage=20)
    assert stats.applied == 1
    assert stats.failed == 0
    assert "He wept for a long time afterwards" not in chapter.read_text(encoding="utf-8")


def test_apply_cuts_respects_type_filter(tmp_path) -> None:
    chapter = tmp_path / "ch.md"
    chapter.write_text("A quick brown fox jumps over a lazy dog. Here is another long line.", encoding="utf-8")
    cuts = [
        {"quote": "A quick brown fox jumps over a lazy dog.", "type": "FAT", "action": "CUT"},
        {"quote": "Here is another long line.", "type": "OVER-EXPLAIN", "action": "CUT"},
    ]
    stats = apply_cuts(chapter, cuts, types={"OVER-EXPLAIN"}, overall_fat_percentage=20)
    assert stats.applied == 1
    assert stats.skipped == 1
    assert "quick brown fox" in chapter.read_text(encoding="utf-8")


def test_apply_cuts_dry_run_does_not_write(tmp_path) -> None:
    chapter = tmp_path / "ch.md"
    original = "Alpha beta gamma. Delta echo foxtrot golf hotel."
    chapter.write_text(original, encoding="utf-8")
    cuts = [{"quote": "Delta echo foxtrot golf hotel.", "type": "FAT", "action": "CUT"}]
    stats = apply_cuts(chapter, cuts, overall_fat_percentage=20, dry_run=True)
    assert stats.applied == 1
    assert chapter.read_text(encoding="utf-8") == original


def test_apply_cuts_skips_under_min_fat(tmp_path) -> None:
    chapter = tmp_path / "ch.md"
    chapter.write_text("Intact prose that should stay untouched.", encoding="utf-8")
    cuts = [{"quote": "Intact prose that should stay untouched.", "type": "FAT", "action": "CUT"}]
    stats = apply_cuts(chapter, cuts, overall_fat_percentage=5, min_fat=10)
    assert stats.applied == 0
    assert chapter.read_text(encoding="utf-8") == "Intact prose that should stay untouched."


def test_cli_apply_cuts_round_trip(tmp_path) -> None:
    chapter = tmp_path / "ch.md"
    cuts_file = tmp_path / "ch_cuts.json"
    chapter.write_text("Alpha beta gamma delta. This sentence is slated for removal today.", encoding="utf-8")
    cuts_file.write_text(
        json.dumps(
            {
                "cuts": [
                    {
                        "quote": "This sentence is slated for removal today.",
                        "type": "OVER-EXPLAIN",
                        "action": "CUT",
                    }
                ],
                "overall_fat_percentage": 25,
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autonovel.mechanical",
            "apply-cuts",
            str(chapter),
            str(cuts_file),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["applied"] == 1
    assert "slated for removal" not in chapter.read_text(encoding="utf-8")


def test_misplaced_and_move_are_never_applied(tmp_path) -> None:
    """Period content delivered badly is moved or dramatised by the revise,
    never removed (genre guide `## Cutting`), whatever --types says."""
    ch = tmp_path / "ch.md"
    body = ("The Fondaco was a warehouse the German merchants had to live in by law. "
            "He went home and slept until the bells woke him at dawn.")
    ch.write_text(body, encoding="utf-8")
    cuts = [
        {"quote": "The Fondaco was a warehouse the German merchants had to live in by law.",
         "type": "MISPLACED", "action": "MOVE", "reason": "give it to the factor at the gate"},
        {"quote": "He went home and slept until the bells woke him at dawn.",
         "type": "OVER-EXPLAIN", "action": "MOVE", "reason": "x"},
    ]
    stats = apply_cuts(ch, cuts, types={"MISPLACED", "OVER-EXPLAIN"})
    assert stats.applied == 0 and len(stats.held) == 2
    assert ch.read_text(encoding="utf-8") == body


def test_rewrite_replaces_instead_of_removing(tmp_path) -> None:
    ch = tmp_path / "ch.md"
    ch.write_text("She felt very sad about the whole thing and the loss of it all.\n\nNext.",
                  encoding="utf-8")
    cuts = [{"quote": "She felt very sad about the whole thing and the loss of it all.",
             "type": "TELL", "action": "REWRITE", "rewrite": "She put the cup down unfinished."}]
    stats = apply_cuts(ch, cuts)
    assert stats.applied == 1 and stats.rewritten == 1
    assert ch.read_text(encoding="utf-8").startswith("She put the cup down unfinished.")
    assert stats.words_removed == 14 - 6
