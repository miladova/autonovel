"""Tier-1 tests for `autonovel.housekeeping.canon_partition` and the
`autonovel canon-partition` CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.housekeeping import canon_partition as cp
from autonovel.housekeeping.scaffold import new_book, new_series
from autonovel.paths import SeriesLayout


CANON = """# Canon

Hard facts true across all books in this series.

## Personal identities and dates

- [Jakob Fugger birth] Jakob Fugger was born in 1459 in Augsburg.
- [Maximilian I death] Maximilian I died on 12 January 1519.

## Submerged facts

Facts that shape behaviour but never appear on the page.

- [Tucher covered for Jakob] In 1476 Tucher absorbed a ledger discrepancy.
  - Jakob never repaid the favour directly.
- [Hans Fugger's land title] The title was legally unclear.

## Promoted 2026-04-25 (ch_03)

- [Pepper loss courier] Jakob calculated nineteen days. (from one ch_03)
- [Guinea pepper] The pepper was malagueta. [fugger-bib] (from research note venice-1473)
- [Untagged promoted] A fact with no provenance at all.

## Superseded 2026-04-29

- Prior canon line: `- [Jakob Venice arrival] September 1473 (from one ch_01)`
  - Superseded by: `[Jakob Venice arrival] October 1473 [bib] (from research note venice-1473)`
  - Rationale: date mismatch
"""


def _series(tmp_path: Path, *, books: tuple[str, ...] = ("one",)) -> SeriesLayout:
    res = new_series(tmp_path / "demo", series_name="demo")
    for b in books:
        new_book(res.series, book_name=b, pov="Tom")
    (res.series.shared / "canon.md").write_text(CANON, encoding="utf-8")
    return res.series


# ------------------------------------------------------------ parsing


def test_parse_canon_splits_sections_and_bullets_with_continuations() -> None:
    preamble, sections = cp.parse_canon(CANON)
    assert preamble[0] == "# Canon"
    titles = [s.title for s in sections]
    assert titles == [
        "Personal identities and dates", "Submerged facts",
        "Promoted 2026-04-25 (ch_03)", "Superseded 2026-04-29",
    ]
    submerged = sections[1]
    assert len(submerged.bullets) == 2
    assert submerged.bullets[0].shortname == "Tucher covered for Jakob"
    assert len(submerged.bullets[0].lines) == 2          # continuation kept
    promoted = sections[2]
    assert promoted.bullets[0].provenance == "one ch_03"
    assert promoted.bullets[0].provenance_book(["one"]) == "one"
    assert promoted.bullets[1].provenance_book(["one"]) is None   # research note stays
    assert promoted.bullets[2].provenance is None
    assert sections[3].is_superseded


def test_render_round_trips_bullets_verbatim() -> None:
    preamble, sections = cp.parse_canon(CANON)
    out = cp.render_sections(preamble, sections)
    for line in CANON.splitlines():
        if line.strip():
            assert line in out, line


# ------------------------------------------------------------ partition


def test_tagged_bullets_move_to_their_book(tmp_path: Path) -> None:
    series = _series(tmp_path)
    report = cp.partition(series)
    assert report.moved == {"one": 1}
    assert report.moved_by_tag == 1
    assert report.superseded_blocks_kept == 1
    shared = (series.shared / "canon.md").read_text(encoding="utf-8")
    book = (series.books / "one" / "canon.md").read_text(encoding="utf-8")
    assert "Pepper loss courier" not in shared
    assert "Pepper loss courier" in book
    assert book.startswith("# Book canon")
    assert "## Promoted 2026-04-25 (ch_03) (partitioned from shared/canon.md)" in book
    # Research-cited, untagged and Superseded all stay.
    assert "Guinea pepper" in shared
    assert "Untagged promoted" in shared
    assert "## Superseded 2026-04-29" in shared
    assert "Jakob Venice arrival" in shared
    # Leftovers are reported for classification.
    keys = {e.shortname for e in report.leftovers}
    assert "Tucher covered for Jakob" in keys
    assert "Jakob Fugger birth" in keys
    assert report.shared_words_after < report.shared_words_before


def test_move_section_and_key(tmp_path: Path) -> None:
    series = _series(tmp_path)
    report = cp.partition(
        series, to_book="one",
        move_sections=["Submerged facts"],
        move_keys=["Untagged promoted", "no-such-key"],
    )
    assert report.moved == {"one": 4}        # 1 tag + 2 section + 1 key
    assert report.moved_by_section == 2
    assert report.moved_by_key == 1
    assert report.unmatched_keys == ["no-such-key"]
    shared = (series.shared / "canon.md").read_text(encoding="utf-8")
    book = (series.books / "one" / "canon.md").read_text(encoding="utf-8")
    assert "## Submerged facts" not in shared          # emptied section dropped
    assert "never appear on the page" not in shared     # ...with its intro line
    assert "## Submerged facts (partitioned from shared/canon.md)" in book
    assert "  - Jakob never repaid the favour directly." in book
    assert "Untagged promoted" in book
    assert "Jakob Fugger birth" in shared              # history stays


def test_partition_is_idempotent(tmp_path: Path) -> None:
    series = _series(tmp_path)
    cp.partition(series)
    shared_1 = (series.shared / "canon.md").read_text(encoding="utf-8")
    book_1 = (series.books / "one" / "canon.md").read_text(encoding="utf-8")
    report = cp.partition(series)
    assert report.moved == {}
    assert (series.shared / "canon.md").read_text(encoding="utf-8") == shared_1
    assert (series.books / "one" / "canon.md").read_text(encoding="utf-8") == book_1


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    series = _series(tmp_path)
    before = (series.shared / "canon.md").read_text(encoding="utf-8")
    book_before = (series.books / "one" / "canon.md").read_text(encoding="utf-8")
    report = cp.partition(series, dry_run=True)
    assert report.moved == {"one": 1}
    assert (series.shared / "canon.md").read_text(encoding="utf-8") == before
    assert (series.books / "one" / "canon.md").read_text(encoding="utf-8") == book_before


def test_move_requires_to_book(tmp_path: Path) -> None:
    series = _series(tmp_path)
    with pytest.raises(cp.PartitionError):
        cp.partition(series, move_sections=["Submerged facts"])
    with pytest.raises(cp.PartitionError):
        cp.partition(series, to_book="nope", move_keys=["x"])


def test_provenance_of_unknown_book_stays(tmp_path: Path) -> None:
    series = _series(tmp_path)
    (series.shared / "canon.md").write_text(
        "# Canon\n\n## X\n\n- [a] fact (from elsewhere ch_01)\n", encoding="utf-8")
    report = cp.partition(series)
    assert report.moved == {}
    assert report.stayed_shared == 1


def test_render_markdown_lists_leftovers(tmp_path: Path) -> None:
    series = _series(tmp_path)
    report = cp.partition(series, dry_run=True)
    md = cp.render_markdown(report)
    assert "(dry-run)" in md
    assert "## Untagged bullets still in shared/canon.md" in md
    assert "`Tucher covered for Jakob`" in md


def test_cli_json(tmp_path: Path) -> None:
    series = _series(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "canon-partition",
         "--series", str(series.root), "--dry-run", "--format", "json"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(proc.stdout)
    assert data["dry_run"] is True
    assert data["moved"] == {"one": 1}
    assert any(e["shortname"] == "Tucher covered for Jakob" for e in data["leftovers"])
