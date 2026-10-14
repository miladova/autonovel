"""Tier-1 tests for `autonovel refresh-templates`.

Catches the bug class: a user runs `autonovel new-series`, then
later a fix lands in the package's `templates/series/typeset/`,
and the user's series silently keeps the stale copy. The
2026-04-25 PDF running-header fix and the 2026-04-28 chapter-title
fix would both have been invisible to in-flight series without
this command.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.housekeeping import scaffold


@pytest.fixture
def fresh_series(tmp_path: Path):
    res = scaffold.new_series(tmp_path / "demo", series_name="demo")
    return res.series


def _stale_typeset(series_root: Path) -> Path:
    """Overwrite the typeset/novel.tex with stale content. Returns
    the path."""
    target = series_root / "typeset" / "novel.tex"
    target.write_text("% STALE TEMPLATE\n", encoding="utf-8")
    return target


def test_refresh_replaces_stale_typeset(fresh_series) -> None:
    target = _stale_typeset(fresh_series.root)
    result = scaffold.refresh_templates(fresh_series)
    assert target in result.updated
    fresh = target.read_text(encoding="utf-8")
    assert "STALE TEMPLATE" not in fresh
    assert "fancyhead" in fresh  # the fix lives here


def test_refresh_dry_run_writes_nothing(fresh_series) -> None:
    target = _stale_typeset(fresh_series.root)
    before = target.read_text(encoding="utf-8")
    result = scaffold.refresh_templates(fresh_series, dry_run=True)
    assert target in result.updated
    # File still has the stale content because dry_run skipped writes.
    assert target.read_text(encoding="utf-8") == before


def test_refresh_marks_already_current_as_unchanged(fresh_series) -> None:
    """Running refresh against an already-current series produces no
    updates."""
    result = scaffold.refresh_templates(fresh_series)
    assert result.updated == []
    assert any(
        p.name == "novel.tex" for p in result.unchanged
    ), "novel.tex should appear in unchanged set"


def test_refresh_preserves_local_only_files(fresh_series) -> None:
    """A user-added file under typeset/ that has no package counterpart
    must NOT be deleted by refresh — it shows up in `extra`."""
    custom = fresh_series.root / "typeset" / "my_custom_macros.tex"
    custom.write_text("% mine\n", encoding="utf-8")
    result = scaffold.refresh_templates(fresh_series)
    assert custom.is_file()
    assert custom in result.extra


def test_refresh_default_scope_is_typeset_and_craft(fresh_series) -> None:
    """Default scope is `typeset/` plus `shared/craft/` — other
    subtrees are listed as skipped so the user can opt them in
    explicitly, and `shared/` as a whole is NOT refreshed (world.md is
    user-owned) even though `shared/craft/` is."""
    stale_world = fresh_series.shared / "world.md"
    stale_world.write_text("# my world\n", encoding="utf-8")
    stale_craft = fresh_series.shared / "craft" / "CRAFT.md"
    stale_craft.write_text("# STALE CRAFT\n", encoding="utf-8")
    result = scaffold.refresh_templates(fresh_series)
    skipped_names = {p.name for p in result.skipped}
    assert "landing" in skipped_names
    assert "shared" not in skipped_names  # partially refreshed, not skipped
    assert stale_craft in result.updated
    assert "STALE CRAFT" not in stale_craft.read_text(encoding="utf-8")
    assert stale_world.read_text(encoding="utf-8") == "# my world\n"


def test_refresh_only_accepts_multiple_subtrees(fresh_series) -> None:
    # Pre-stale a file in `shared/` and one in `typeset/`.
    (fresh_series.shared / "world.md").write_text("# stale world\n",
                                                    encoding="utf-8")
    (fresh_series.root / "typeset" / "novel.tex").write_text(
        "% stale\n", encoding="utf-8")
    result = scaffold.refresh_templates(
        fresh_series, only=("typeset", "shared"))
    updated_names = {p.name for p in result.updated}
    assert "novel.tex" in updated_names
    assert "world.md" in updated_names


def test_refresh_emits_no_extras_for_clean_series(fresh_series) -> None:
    """A freshly scaffolded series has no local-only typeset files."""
    result = scaffold.refresh_templates(fresh_series)
    assert result.extra == []


def test_cli_refresh_templates_round_trip(fresh_series, tmp_path: Path) -> None:
    target = _stale_typeset(fresh_series.root)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "refresh-templates"],
        cwd=fresh_series.root, capture_output=True, text=True, check=True,
    )
    assert "updated" in proc.stdout.lower()
    fresh = target.read_text(encoding="utf-8")
    assert "STALE TEMPLATE" not in fresh


def test_cli_refresh_templates_dry_run_no_writes(fresh_series) -> None:
    target = _stale_typeset(fresh_series.root)
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "refresh-templates",
         "--dry-run"],
        cwd=fresh_series.root, capture_output=True, text=True, check=True,
    )
    assert "would update" in proc.stdout.lower()
    assert target.read_text(encoding="utf-8") == "% STALE TEMPLATE\n"
