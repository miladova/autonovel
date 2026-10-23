"""Tier-1 tests for the craft reference documents (`shared/craft/`).

Bug class caught (2026-10-14): CRAFT.md, ANTI-SLOP.md and
ANTI-PATTERNS.md lived only at the autonovel repo root. Commands said
"obey ANTI-PATTERNS.md" with no path, nothing installed the files
anywhere a series session could read them, and the series CLAUDE.md
never mentioned them — so the writer drafted every chapter from
`voice.md` alone. The fix ships them as a series template subtree
(`shared/craft/`), copied in by `new-series`, refreshed by
`refresh-templates`, and checked by `doctor`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from autonovel.housekeeping import doctor, scaffold

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def fresh_series(tmp_path: Path):
    return scaffold.new_series(tmp_path / "demo", series_name="demo").series


def test_every_craft_doc_ships_in_the_template() -> None:
    tmpl = scaffold.craft_template_dir()
    for name in scaffold.CRAFT_DOCS:
        p = tmpl / name
        assert p.is_file(), f"{name} missing from templates/series/shared/craft/"
        assert len(p.read_text(encoding="utf-8").split()) > 300, f"{name} is a stub"


def test_repo_root_docs_are_symlinks_to_the_template() -> None:
    """One source of truth: the repo-root CRAFT.md etc. must resolve to
    the template copies, so an edit in either place is the same edit."""
    tmpl = scaffold.craft_template_dir().resolve()
    for name in scaffold.CRAFT_DOCS:
        root_copy = REPO_ROOT / name
        assert root_copy.exists(), f"{name} missing at repo root"
        assert root_copy.resolve() == (tmpl / name).resolve(), (
            f"{name} at repo root is not the template file"
        )


def test_new_series_gets_shared_craft(fresh_series) -> None:
    for name in scaffold.CRAFT_DOCS:
        dst = fresh_series.shared / "craft" / name
        assert dst.is_file(), f"new-series did not copy shared/craft/{name}"
        src = scaffold.craft_template_dir() / name
        assert dst.read_bytes() == src.read_bytes()


def test_doctor_warns_when_craft_docs_missing(fresh_series) -> None:
    import shutil
    shutil.rmtree(fresh_series.shared / "craft")
    report = doctor.run(fresh_series.root, export_tools=False)
    hits = [w for w in report.warnings if "craft docs missing" in w]
    assert hits, report.warnings
    assert "refresh-templates" in hits[0]
    for name in scaffold.CRAFT_DOCS:
        assert name in hits[0]


def test_doctor_warns_when_a_craft_doc_is_stale(fresh_series) -> None:
    (fresh_series.shared / "craft" / "PROSE.md").write_text("old\n", encoding="utf-8")
    report = doctor.run(fresh_series.root, export_tools=False)
    hits = [w for w in report.warnings if "craft docs stale" in w]
    assert hits, report.warnings
    assert "PROSE.md" in hits[0]
    assert "CRAFT.md" not in hits[0].split("stale:")[1].split("differ")[0].replace("PROSE.md", "")


def test_doctor_quiet_when_craft_docs_current(fresh_series) -> None:
    report = doctor.run(fresh_series.root, export_tools=False)
    assert not [w for w in report.warnings if "craft docs" in w]


def test_refresh_restores_craft_docs_after_deletion(fresh_series) -> None:
    import shutil
    shutil.rmtree(fresh_series.shared / "craft")
    result = scaffold.refresh_templates(fresh_series)
    names = {p.name for p in result.updated}
    assert set(scaffold.CRAFT_DOCS) <= names
    assert (fresh_series.shared / "craft" / "PROSE.md").is_file()


def test_prose_commands_read_craft_docs_from_the_series() -> None:
    """The three prose commands must name the series-side path, not the
    bare repo filename a series session cannot resolve."""
    for stem in ("draft", "revise", "evaluate"):
        text = (REPO_ROOT / "commands" / f"{stem}.md").read_text(encoding="utf-8")
        assert "shared/craft/PROSE.md" in text, f"{stem}.md does not read shared/craft/PROSE.md"
        assert "refresh-templates" in text, f"{stem}.md lacks the self-heal instruction"
        # Every craft doc is named with its series path at least once, so
        # a later section citation ("CRAFT.md §6") resolves for the reader.
        for name in scaffold.CRAFT_DOCS:
            if re.search(rf"(?<![/\w]){re.escape(name)}", text):
                assert f"shared/craft/{name}" in text, (
                    f"{stem}.md mentions {name} but never gives its shared/craft/ path"
                )


def test_genre_guides_ship_and_doctor_checks_them(fresh_series) -> None:
    for name in scaffold.GENRE_GUIDES:
        assert (scaffold.craft_template_dir() / name).is_file(), name
        assert (fresh_series.shared / "craft" / name).is_file(), name
    (fresh_series.shared / "craft" / "genres" / "historical.md").write_text("old\n", encoding="utf-8")
    report = doctor.run(fresh_series.root, export_tools=False)
    hits = [w for w in report.warnings if "craft docs stale" in w]
    assert hits and "genres/historical.md" in hits[0]
