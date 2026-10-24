"""Tier-1 tests for `src/autonovel/promote_canon.py` and the
`autonovel _promote-canon` CLI subcommand.

Locks the engine that ships 2026-04-26 to fix the lock-collision
bug class: per-chapter promote-canon inside a sweep was failing
because sub-agents invoked the slash-command, hit the parent's
in-progress lock, and silently left pending entries unmerged. The
new helper does the file ops directly and supports --no-lock so
sweep sub-agents can call it without lock contention.

Coverage:
  - parsing pending entries (bullet shapes, research tags,
    shortnames, provenance, no-new-facts marker)
  - classification (duplicate, contradiction, survivor) including
    the year-mismatch + negation-flip heuristics
  - research-tagged supersedure (research entry beats existing
    canon, prior line recorded under `## Superseded`)
  - conflict-block format parity with promote-canon.md step 8
    (HTML instruction block at top, `## Conflict N` numbering,
    file path identification, source attribution)
  - mutual exclusion: file with conflicts never also has
    `no new facts`
  - canon-line shape per promote-canon.md step 5
  - dry-run leaves files untouched
  - --no-lock bypasses the lock check; without it, a held lock
    refuses the run
  - CLI round-trip with both human and json formats
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from autonovel import promote_canon as pc
from autonovel.housekeeping.scaffold import new_book, new_series
from autonovel.paths import SeriesLayout


def _make_series(tmp_path: Path) -> SeriesLayout:
    res = new_series(tmp_path / "demo", series_name="demo")
    new_book(res.series, book_name="one", pov="Tom")
    return res.series


def _seed_pending(series: SeriesLayout, book: str, lines: list[str]) -> Path:
    pending = series.books / book / "pending_canon.md"
    pending.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return pending


def _seed_canon(series: SeriesLayout, lines: list[str]) -> Path:
    path = series.shared / "canon.md"
    path.write_text("# Canon\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------- parsing


def test_parse_simple_bullet() -> None:
    entries = pc._parse_pending("- Tommaso lives in Venice.\n")
    assert len(entries) == 1
    assert entries[0].fact_text == "Tommaso lives in Venice"
    assert entries[0].research_slug is None
    assert entries[0].shortnames == []


def test_parse_research_tag_and_shortname() -> None:
    entries = pc._parse_pending(
        "- Fugger arrived in Venice 1478 [fugger-bib] [research:venice-1479-1500]\n"
    )
    assert len(entries) == 1
    e = entries[0]
    assert e.research_slug == "venice-1479-1500"
    assert e.shortnames == ["fugger-bib"]
    assert "1478" in e.fact_text


def test_parse_provenance() -> None:
    entries = pc._parse_pending(
        "- Tommaso speaks Latin (from one ch_03)\n"
    )
    assert entries[0].provenance == "one ch_03"


def test_parse_skips_a_no_new_facts_note_in_a_bullet() -> None:
    """A revision worker wrote its marker as a bullet with a comment, and
    the parser promoted it into canon as a fact (kingmaker2, 2026-10-24)."""
    text = ("- ch 6 (revise 2026-10-24, R11 turn 39): no new facts "
            "(two frames removed; no fact changed)\n"
            "- [Real fact] No new facts were ever kept in this ledger (invented)\n")
    entries = pc._parse_pending(text)
    assert len(entries) == 1
    assert "No new facts were ever kept" in entries[0].raw_line


def test_parse_skips_no_new_facts() -> None:
    entries = pc._parse_pending("no new facts\n")
    assert entries == []


def test_parse_skips_html_comment_block() -> None:
    """Conflict files have an HTML-comment instruction block at the
    top — bullets *inside* that block are documentation, not real
    pending entries."""
    text = (
        "# Conflicts — resolve before next promote-canon\n"
        "\n"
        "<!--\n"
        "  - This is documentation.\n"
        "  - Don't parse me.\n"
        "-->\n"
        "\n"
        "- Real pending entry.\n"
    )
    entries = pc._parse_pending(text)
    assert len(entries) == 1
    assert entries[0].fact_text == "Real pending entry"


def test_parse_dedupes_within_one_file() -> None:
    text = "- Same fact stated.\n- Same fact stated.\n- Different fact.\n"
    entries = pc._parse_pending(text)
    assert len(entries) == 2


# ---------------------------------------------------- classification


def test_classify_duplicate_against_canon() -> None:
    e = pc.PendingEntry(
        raw_line="- Tommaso lives in Venice with his uncle.",
        fact_text="Tommaso lives in Venice with his uncle",
        research_slug=None, shortnames=[], provenance=None,
    )
    canon = "- Tommaso lives in Venice with his uncle (from one ch_01)\n"
    result = pc._classify(e, canon_text=canon, world_text="", characters_text="")
    assert result["kind"] == "duplicate"


def test_classify_year_mismatch_is_contradiction() -> None:
    e = pc.PendingEntry(
        raw_line="- Fugger arrived in Venice 1478.",
        fact_text="Fugger arrived in Venice 1478",
        research_slug=None, shortnames=[], provenance=None,
    )
    canon = "- Fugger arrived in Venice 1473 (from one ch_03)\n"
    result = pc._classify(e, canon_text=canon, world_text="", characters_text="")
    assert result["kind"] == "contradiction"
    assert "1478" in result["rationale"] or "date" in result["rationale"]


def test_classify_unrelated_fact_is_survivor() -> None:
    e = pc.PendingEntry(
        raw_line="- Niccolò is a glassblower.",
        fact_text="Niccolò is a glassblower",
        research_slug=None, shortnames=[], provenance=None,
    )
    canon = "- Tommaso speaks Latin (from one ch_01)\n"
    result = pc._classify(e, canon_text=canon, world_text="", characters_text="")
    assert result["kind"] == "survivor"


def test_classify_finds_contradiction_in_world_md_not_just_canon() -> None:
    """Contradictions can be against shared/world.md or
    shared/characters.md too. The reported file path tells the user
    which file to edit. The 3-digit-year case (`421 CE`) exercises
    the heuristic's coverage of early-medieval dates."""
    e = pc.PendingEntry(
        raw_line="- Venice was founded in 421 CE.",
        fact_text="Venice was founded in 421 CE",
        research_slug=None, shortnames=[], provenance=None,
    )
    world = "- Venice was founded in 697 CE during the early Byzantine period.\n"
    result = pc._classify(e, canon_text="", world_text=world, characters_text="")
    assert result["kind"] == "contradiction"
    assert result["existing_file"] == "shared/world.md"


def _research_entry(text: str) -> pc.PendingEntry:
    return pc.PendingEntry(
        raw_line=f"- {text} [src] [research:note]",
        fact_text=text,
        research_slug="note", shortnames=["src"], provenance=None,
    )


def test_classify_different_keys_sharing_series_nouns_is_survivor() -> None:
    """Regression (2026-10-13): two keyed facts about DIFFERENT events
    that share the series' own proper nouns and disagree on the year
    are not a contradiction. The old heuristic retired
    `[Fugger Venice loss, 1477]` because `[Battle of Calliano] ...
    1487` also said "Venetian force"."""
    e = _research_entry(
        "[Battle of Calliano] On 10 August 1487 Archduke Sigismund's Tyrolean "
        "force defeated the Venetian army at Calliano; the Venetian commander "
        "drowned in the Adige"
    )
    book_canon = (
        "- [Fugger Venice loss, 1477] In October 1477 Jakob and Tucher's position "
        "collapses when the Ottoman raid breaks a Venetian force at the Isonzo; "
        "the Fugger account loses 300 ducats.\n"
        "- [Konrad Mair] Konrad Mair is an invented Fugger rider, born 1468.\n"
    )
    result = pc._classify(
        e, canon_text="", world_text="", characters_text="", book_canon_text=book_canon
    )
    assert result["kind"] == "survivor"


def test_classify_same_key_different_year_is_contradiction() -> None:
    e = _research_entry(
        "[Aachen coronation] Charles was crowned King of the Romans at Aachen "
        "on 23 October 1520"
    )
    canon = "- [Aachen coronation] Charles was crowned at Aachen on 26 October 1520\n"
    result = pc._classify(e, canon_text=canon, world_text="", characters_text="")
    assert result["kind"] == "contradiction"
    assert "1520" in result["rationale"] or "date" in result["rationale"]


def test_classify_wrapped_prose_is_compared_as_a_paragraph() -> None:
    """characters.md is hard-wrapped. A 70-character fragment must not
    be matched on its own: `Head of the Höchstetter house (born 1463),`
    shares "house" with half the corpus."""
    e = _research_entry(
        "[1498 copper syndicate] In 1498 the Augsburg houses of Fugger, "
        "Gossembrot and Herwart combined in the first German copper syndicate; "
        "Sigmund Gossembrot died in 1500"
    )
    characters = (
        "## Ambrosius Höchstetter\n\n"
        "Head of the Höchstetter house (born 1463), the third of Augsburg's\n"
        "great merchant-banking families. A speculator where Jakob is a\n"
        "lender; runs his own courier relay to the Tyrol and joins the\n"
        "Fuggers in a copper cartel in 1517.\n"
    )
    result = pc._classify(e, canon_text="", world_text="", characters_text=characters)
    assert result["kind"] == "survivor"
    # The paragraph is one unit, the heading is not a unit.
    assert pc._units(characters) == [
        "Head of the Höchstetter house (born 1463), the third of Augsburg's "
        "great merchant-banking families. A speculator where Jakob is a "
        "lender; runs his own courier relay to the Tyrol and joins the "
        "Fuggers in a copper cartel in 1517."
    ]


def test_common_tokens_learned_from_corpus_not_hardcoded() -> None:
    lines = "\n".join(f"- Fugger fact number {i} about the Fugger house in Augsburg." for i in range(10))
    common = pc._common_tokens([lines])
    assert {"fugger", "house", "augsburg", "fact", "number", "about"} <= common
    # A small corpus declares nothing common (floor of 5 lines).
    assert pc._common_tokens(["- Fugger one.\n- Fugger two.\n- Fugger three.\n"]) == frozenset()


# ---------------------------------------------------- end-to-end


def test_promote_simple_survivors(tmp_path: Path) -> None:
    """Chapter-derived facts land in the BOOK canon (books/one/canon.md),
    not shared/canon.md — book-scoped canon, 2026-10-12."""
    series = _make_series(tmp_path)
    _seed_pending(series, "one", [
        "- Tommaso speaks Latin.",
        "- Niccolò is a glassblower.",
    ])
    report = pc.promote(series, book="one")
    assert report.books[0].promoted == 2
    assert report.books[0].promoted_to_book == 2
    assert report.books[0].promoted_to_shared == 0
    assert report.books[0].conflicts == 0
    book_canon = (series.books / "one" / "canon.md").read_text(encoding="utf-8")
    assert book_canon.startswith("# Book canon")
    assert "## Promoted" in book_canon
    assert "Tommaso speaks Latin" in book_canon
    assert "Niccolò is a glassblower" in book_canon
    shared_text = (series.shared / "canon.md").read_text(encoding="utf-8")
    assert "Tommaso speaks Latin" not in shared_text
    pending_text = (series.books / "one" / "pending_canon.md").read_text(encoding="utf-8")
    assert pending_text.strip() == "no new facts"


def test_scope_series_forces_shared(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    _seed_pending(series, "one", ["- Tommaso speaks Latin."])
    report = pc.promote(series, book="one", scope="series")
    assert report.books[0].promoted_to_shared == 1
    assert "Tommaso speaks Latin" in (series.shared / "canon.md").read_text(encoding="utf-8")
    assert not (series.books / "one" / "canon.md").read_text(encoding="utf-8").count("Tommaso")


def test_scope_book_forces_book_even_for_research(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    _seed_pending(series, "one", ["- Fugger arrived 1478 [fugger-bib] [research:venice]"])
    report = pc.promote(series, book="one", scope="book")
    assert report.books[0].promoted_to_book == 1
    assert "1478" in (series.books / "one" / "canon.md").read_text(encoding="utf-8")


def test_research_tagged_goes_to_shared_by_default(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    _seed_pending(series, "one", ["- Fugger arrived 1478 [fugger-bib] [research:venice]"])
    report = pc.promote(series, book="one")
    assert report.books[0].promoted_to_shared == 1
    assert report.books[0].promoted_to_book == 0
    assert "1478" in (series.shared / "canon.md").read_text(encoding="utf-8")


def test_duplicate_detected_against_own_book_canon(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    (series.books / "one" / "canon.md").write_text(
        "# Book canon\n\n- Tommaso speaks Latin (from one ch_02)\n", encoding="utf-8")
    _seed_pending(series, "one", ["- Tommaso speaks Latin."])
    report = pc.promote(series, book="one")
    assert report.books[0].duplicates == 1
    assert report.books[0].promoted == 0


def test_contradiction_against_own_book_canon_names_that_file(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    (series.books / "one" / "canon.md").write_text(
        "# Book canon\n\n- Fugger arrived in Venice 1473 (from one ch_03)\n", encoding="utf-8")
    _seed_pending(series, "one", ["- Fugger arrived in Venice 1478 (from one ch_05)"])
    report = pc.promote(series, book="one")
    assert report.books[0].conflicts == 1
    pending_text = (series.books / "one" / "pending_canon.md").read_text(encoding="utf-8")
    assert "**Existing canon (in: books/one/canon.md):**" in pending_text


def test_sibling_book_canon_is_not_a_constraint(tmp_path: Path) -> None:
    """A rewrite (book `two`) may contradict book `one`'s own canon
    freely — only shared/ and its OWN canon bind it."""
    series = _make_series(tmp_path)
    new_book(series, book_name="two", pov="Tom")
    (series.books / "one" / "canon.md").write_text(
        "# Book canon\n\n- Fugger arrived in Venice 1473 (from one ch_03)\n", encoding="utf-8")
    _seed_pending(series, "two", ["- Fugger arrived in Venice 1478 (from two ch_01)"])
    report = pc.promote(series, book="two")
    br = report.books[0]
    assert br.conflicts == 0
    assert br.promoted_to_book == 1
    assert "1478" in (series.books / "two" / "canon.md").read_text(encoding="utf-8")


def test_research_supersedes_line_in_book_canon_writes_block_there(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    (series.books / "one" / "canon.md").write_text(
        "# Book canon\n\n- Fugger arrived in Venice 1473 (from one ch_03)\n", encoding="utf-8")
    _seed_pending(series, "one", [
        "- Fugger arrived in Venice 1478 [fugger-bib] [research:venice-1479-1500]",
    ])
    report = pc.promote(series, book="one")
    assert report.books[0].supersedures == 1
    book_canon = (series.books / "one" / "canon.md").read_text(encoding="utf-8")
    assert "## Superseded" in book_canon            # audit trail where the old line lived
    shared_text = (series.shared / "canon.md").read_text(encoding="utf-8")
    assert "1478" in shared_text                     # the cited fact itself is series-wide
    assert "## Superseded" not in shared_text


def test_research_tagged_entry_supersedes_existing_canon(tmp_path: Path) -> None:
    """Research-derived entries beat existing canon on contradiction.
    The new entry promotes, the prior line gets a `## Superseded`
    block with the citation."""
    series = _make_series(tmp_path)
    _seed_canon(series, ["- Fugger arrived in Venice 1473 (from one ch_03)"])
    _seed_pending(series, "one", [
        "- Fugger arrived in Venice 1478 [fugger-bib] [research:venice-1479-1500]",
    ])
    report = pc.promote(series, book="one")
    br = report.books[0]
    assert br.promoted == 1
    assert br.supersedures == 1
    assert br.conflicts == 0
    canon_text = (series.shared / "canon.md").read_text(encoding="utf-8")
    assert "## Promoted" in canon_text
    assert "## Superseded" in canon_text
    assert "1478" in canon_text
    assert "Fugger arrived in Venice 1473" in canon_text  # prior preserved
    assert "venice-1479-1500" in canon_text  # research note attribution


def test_non_research_contradiction_lands_in_conflict_block(tmp_path: Path) -> None:
    """A pending entry that contradicts canon WITHOUT a research tag
    goes back to pending_canon.md as a structured conflict for the
    user to resolve."""
    series = _make_series(tmp_path)
    _seed_canon(series, ["- Fugger arrived in Venice 1473 (from one ch_03)"])
    _seed_pending(series, "one", [
        "- Fugger arrived in Venice 1478 (from one ch_05)",
    ])
    report = pc.promote(series, book="one")
    br = report.books[0]
    assert br.conflicts == 1
    assert br.promoted == 0
    pending_text = (series.books / "one" / "pending_canon.md").read_text(encoding="utf-8")
    assert "# Conflicts — resolve before next promote-canon" in pending_text
    # Mandatory HTML instruction block at the top.
    assert "<!--" in pending_text
    assert "HOW TO RESOLVE A CONFLICT" in pending_text
    assert "-->" in pending_text
    # Structured `## Conflict N` block per promote-canon.md step 8.
    assert "## Conflict 1" in pending_text
    assert "**New candidate:**" in pending_text
    assert "**Existing canon (in: shared/canon.md):**" in pending_text
    assert "**Why they conflict:**" in pending_text
    assert "**Source:**" in pending_text


def test_conflicts_and_no_new_facts_are_mutually_exclusive(tmp_path: Path) -> None:
    """A pending file with conflicts NEVER also says 'no new facts'.
    Uses a year-mismatch contradiction (which the heuristic
    catches reliably) plus an unrelated survivor."""
    series = _make_series(tmp_path)
    _seed_canon(series, [
        "- Fugger arrived in Venice 1473 (from one ch_03)",
    ])
    _seed_pending(series, "one", [
        "- Fugger arrived in Venice 1478 (from one ch_05)",  # year-mismatch contradiction
        "- Tommaso speaks Latin (from one ch_06)",           # survivor
    ])
    pc.promote(series, book="one")
    pending_text = (series.books / "one" / "pending_canon.md").read_text(encoding="utf-8")
    assert "no new facts" not in pending_text
    assert "## Conflict 1" in pending_text


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    canon_path = _seed_canon(series, [
        "- Fugger arrived in Venice 1473 (from one ch_03)",
    ])
    pending_path = _seed_pending(series, "one", [
        "- Tommaso speaks Latin.",                            # survivor
        "- Fugger arrived in Venice 1478 (from one ch_05)",   # year-mismatch contradiction
    ])
    canon_before = canon_path.read_text(encoding="utf-8")
    pending_before = pending_path.read_text(encoding="utf-8")
    report = pc.promote(series, book="one", dry_run=True)
    assert report.dry_run is True
    assert report.books[0].promoted == 1
    assert report.books[0].conflicts == 1
    # Files unchanged.
    assert canon_path.read_text(encoding="utf-8") == canon_before
    assert pending_path.read_text(encoding="utf-8") == pending_before


def test_canon_line_shape_for_research_tagged(tmp_path: Path) -> None:
    """Research-tagged survivors render as `(from research note <slug>)`,
    others as `(from <book> ch_<NN>)` per promote-canon.md step 5."""
    series = _make_series(tmp_path)
    _seed_pending(series, "one", [
        "- Foo fact [research:venice]",
        "- Bar fact (from one ch_02)",
    ])
    pc.promote(series, book="one")
    canon = (series.shared / "canon.md").read_text(encoding="utf-8")
    assert "Foo fact (from research note venice)" in canon
    book_canon = (series.books / "one" / "canon.md").read_text(encoding="utf-8")
    assert "Bar fact (from one ch_02)" in book_canon


def test_re_running_with_resolved_conflicts_clears_pending(tmp_path: Path) -> None:
    """After the user 'rejects' a conflict (deletes the `## Conflict
    N` block from pending_canon.md), re-running promote-canon picks
    up no candidates and sets the file to 'no new facts'."""
    series = _make_series(tmp_path)
    _seed_canon(series, ["- Tommaso lives in Venice (from one ch_01)"])
    _seed_pending(series, "one", ["- Tommaso lives in Padua (from one ch_05)"])
    pc.promote(series, book="one")
    # Simulate user rejecting: clear pending file.
    (series.books / "one" / "pending_canon.md").write_text(
        "no new facts\n", encoding="utf-8"
    )
    report = pc.promote(series, book="one")
    assert report.books[0].conflicts == 0
    assert report.books[0].promoted == 0


def test_promote_with_unknown_book_raises(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    with pytest.raises(ValueError, match="unknown book"):
        pc.promote(series, book="nonexistent")


# ---------------------------------------------------- CLI


def test_cli_human_format(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    _seed_pending(series, "one", ["- Tommaso speaks Latin."])
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_promote-canon", "--book", "one"],
        check=True, capture_output=True, text=True,
        cwd=series.root,
    )
    assert "promoted:    1" in proc.stdout
    assert "book: one" in proc.stdout


def test_cli_json_format(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    _seed_pending(series, "one", ["- Tommaso speaks Latin."])
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_promote-canon",
         "--book", "one", "--format", "json"],
        check=True, capture_output=True, text=True,
        cwd=series.root,
    )
    payload = json.loads(proc.stdout)
    assert payload["books"][0]["promoted"] == 1


def test_cli_refuses_when_lock_held_without_no_lock_flag(tmp_path: Path) -> None:
    """The lock-collision bug class — without --no-lock, the helper
    refuses to run when another command holds the in-progress lock.
    With --no-lock, it runs anyway (the caller is asserting safety)."""
    from autonovel import lock as lock_mod
    series = _make_series(tmp_path)
    _seed_pending(series, "one", ["- Tommaso speaks Latin."])
    # Acquire the lock as if a parent revision-pass were holding it.
    lock_mod.acquire(
        series.lock_file,
        runtime="claude",
        command="autonovel:revision-pass",
        args=["--chapters", "1-5"],
    )
    try:
        # Without --no-lock: refuse.
        proc = subprocess.run(
            [sys.executable, "-m", "autonovel.cli", "_promote-canon", "--book", "one"],
            capture_output=True, text=True,
            cwd=series.root,
        )
        assert proc.returncode != 0
        assert "another autonovel command is in progress" in proc.stderr
        # With --no-lock: succeed (this is what sweep sub-agents call).
        proc = subprocess.run(
            [sys.executable, "-m", "autonovel.cli", "_promote-canon",
             "--book", "one", "--no-lock"],
            check=True, capture_output=True, text=True,
            cwd=series.root,
        )
        assert "promoted:    1" in proc.stdout
    finally:
        lock_mod.release(series.lock_file)


def test_cli_dry_run(tmp_path: Path) -> None:
    series = _make_series(tmp_path)
    _seed_pending(series, "one", ["- Tommaso speaks Latin."])
    canon_path = series.shared / "canon.md"
    canon_before = canon_path.read_text(encoding="utf-8") if canon_path.exists() else ""
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "_promote-canon",
         "--book", "one", "--dry-run"],
        check=True, capture_output=True, text=True,
        cwd=series.root,
    )
    assert "(dry-run — no files written)" in proc.stdout
    canon_after = canon_path.read_text(encoding="utf-8") if canon_path.exists() else ""
    assert canon_after == canon_before
