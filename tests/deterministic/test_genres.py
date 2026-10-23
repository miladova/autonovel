"""Genres and subgenres as a first-class choice (2026-10-23).

The pipeline's cold readers and judge pushed to cut a historical novel's
history because nothing said what its reader comes for. A registry of
genres and subgenres, a sourced guide per genre in fixed sections, and
every writing, reading and judging command reading its sections fix that.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from autonovel import cli, genres, project
from autonovel.housekeeping import scaffold
from autonovel.mechanical import design as design_mod

CRAFT = Path(__file__).resolve().parents[2] / "src/autonovel/templates/series/shared/craft"
GUIDE = CRAFT / "genres" / "historical.md"
COMMANDS = Path(__file__).resolve().parents[2] / "commands"


def _series(tmp_path: Path, genre: str = "historical-fiction", subgenres=None) -> Path:
    res = scaffold.new_series(tmp_path / "s", series_name="s", genre=genre,
                              subgenres=subgenres or [])
    scaffold.new_book(res.series, book_name="b", pov="Ana")
    return res.series.root


# ------------------------------------------------------------- registry

def test_aliases_resolve_to_registry_ids() -> None:
    assert genres.find("historical fiction").id == "historical"
    assert genres.find("Historical-Fiction").id == "historical"
    assert genres.find("sci-fi").id == "science-fiction"
    assert genres.find("nonsense") is None
    g = genres.find("historical")
    assert g.subgenre("historical thriller").id == "political-thriller"
    assert g.subgenre("Fictional biography").id == "biographical"
    assert genres.find("sf").subgenre("first alien encounter").id == "first-contact"


def test_every_genre_and_subgenre_has_a_promise() -> None:
    ids = set()
    for g in genres.GENRES:
        assert g.promise.strip(), g.id
        assert g.id not in ids
        ids.add(g.id)
        for s in g.subgenres:
            assert s.promise.strip(), (g.id, s.id)


def test_resolve_book_overrides_and_other(tmp_path: Path) -> None:
    root = _series(tmp_path, subgenres=["traditional"])
    cfg = project.load(root / "project.yaml")
    r = genres.resolve(cfg, "b", series_root=root)
    assert [s.id for s in r.subgenres] == ["traditional"]
    assert r.guide_path == "shared/craft/genres/historical.md"
    assert r.dimensions == ["history"]
    entry = cfg.book_by_name("b")
    entry.subgenres = ["biographical", "historical thriller", "other: banking", "steampunk"]
    r = genres.resolve(cfg, "b", series_root=root)
    assert [s.id for s in r.subgenres] == ["biographical", "political-thriller"]
    assert r.other_subgenres == ["banking", "steampunk"]
    assert any("steampunk" in w for w in r.warnings)
    assert not any("banking" in w for w in r.warnings)
    assert "Biographical novel" in r.label()


def test_unknown_genre_and_missing_guide_warn(tmp_path: Path) -> None:
    root = _series(tmp_path, genre="space-opera-noir")
    r = genres.resolve(project.load(root / "project.yaml"), None, series_root=root)
    assert r.genre is None and r.guide_path is None
    assert any("not in the registry" in w for w in r.warnings)
    root2 = _series(tmp_path / "2", genre="sf")
    r2 = genres.resolve(project.load(root2 / "project.yaml"), None, series_root=root2)
    assert r2.genre.id == "science-fiction" and r2.guide_path is None
    assert any("--add science-fiction" in w for w in r2.warnings)


def test_series_guide_wins_over_package_guide(tmp_path: Path) -> None:
    root = _series(tmp_path)
    own = root / "shared" / "genres"
    own.mkdir(parents=True)
    (own / "historical.md").write_text("# mine\n\n### The `period` dimension (chapter mode)\n",
                                       encoding="utf-8")
    r = genres.resolve(project.load(root / "project.yaml"), "b", series_root=root)
    assert r.guide_path == "shared/genres/historical.md"
    assert r.dimensions == ["period"]


def test_project_round_trip_keeps_subgenres(tmp_path: Path) -> None:
    root = _series(tmp_path, subgenres=["biographical", "historical-thriller"])
    cfg = project.load(root / "project.yaml")
    assert cfg.genre == "historical"
    assert cfg.subgenres == ["biographical", "political-thriller"]
    text = (root / "project.yaml").read_text()
    assert text.index("genre:") < text.index("subgenres:") < text.index("period:")
    cfg.book_by_name("b").subgenres = ["mystery"]
    project.dump(cfg, root / "project.yaml")
    assert project.load(root / "project.yaml").book_by_name("b").subgenres == ["mystery"]


def test_subgenres_must_be_strings(tmp_path: Path) -> None:
    p = tmp_path / "project.yaml"
    p.write_text("series_name: x\ngenre: historical\nsubgenres: [1, 2]\n", encoding="utf-8")
    with pytest.raises(project.ProjectValidationError):
        project.load(p)


# ------------------------------------------------------------- CLI

def test_cli_genre_set_and_show(tmp_path: Path, capsys, monkeypatch) -> None:
    root = _series(tmp_path)
    monkeypatch.chdir(root)
    assert cli.main(["genre", "set", "--book", "b", "--subgenres",
                     "biographical, historical thriller"]) == 0
    capsys.readouterr()
    assert cli.main(["genre", "show", "--book", "b", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["genre"] == "historical"
    assert [s["id"] for s in data["subgenres"]] == ["biographical", "political-thriller"]
    assert data["guide"] == "shared/craft/genres/historical.md"
    assert data["dimensions"] == ["history"]
    cfg = project.load(root / "project.yaml")
    assert cfg.book_by_name("b").subgenres == ["biographical", "political-thriller"]
    assert cfg.subgenres == []
    assert cli.main(["genre", "list"]) == 0
    assert "political-thriller" in capsys.readouterr().out


def test_begin_prints_the_genre_line(tmp_path: Path, capsys) -> None:
    root = _series(tmp_path, subgenres=["biographical"])
    cli._print_genre_line(scaffold.SeriesLayout(root=root), "b")
    out = capsys.readouterr().out
    assert out.startswith("genre: Historical fiction (Biographical novel)")
    assert "guide: shared/craft/genres/historical.md" in out
    assert "extra evaluate dimensions: history" in out


# ------------------------------------------------------------- the guide

def test_guide_has_every_section_in_order() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    heads = re.findall(r"^## (.+)$", text, re.MULTILINE)
    wanted = [name for name, _ in genres.GUIDE_SECTIONS]
    assert [h for h in heads if h in wanted] == wanted


def test_guide_covers_every_registry_subgenre() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    ids = re.findall(r"^### `([a-z-]+)`", text, re.MULTILINE)
    assert set(ids) == {s.id for s in genres.find("historical").subgenres}


def test_guide_sources_carry_urls_and_rules_hold() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    sources = text.split("## Sources", 1)[1]
    flat = " ".join(text.split())
    assert len(re.findall(r"<https?://", sources)) >= 20
    assert genres.guide_ledger_heading(GUIDE) == "What the reader comes to learn"
    # The rule the guide exists for.
    assert "never fixed by cutting the history" in flat
    assert "`MISPLACED`" in flat


def test_guides_readme_lists_sections() -> None:
    text = (CRAFT / "genres" / "README.md").read_text(encoding="utf-8")
    for name, _ in genres.GUIDE_SECTIONS:
        assert f"| {name} |" in text


def test_first_reader_brief_defers_to_the_genre() -> None:
    text = " ".join((CRAFT / "FIRST-READER.md").read_text(encoding="utf-8").split())
    assert "## The first reader" in text and "never simply cut" in text


# ------------------------------------------------------------- the commands

# Which guide sections each command must name.
READERS = {
    "draft": ["## Drafting", "## The first reader"],
    "revise": ["## Drafting"],
    "brief": ["## Cutting", "## Drafting", "Move, don't cut"],
    "first-read": ["## The first reader"],
    "evaluate": ["## Judging"],
    "adversarial-edit": ["## Cutting", "MISPLACED"],
    "reader-panel": ["## The first reader"],
    "review": ["## Judging", "## Editing"],
    "developmental-edit": ["## Editing"],
    "design": ["## Design", "What the reader comes to learn"],
    "gen-outline": ["What the reader comes to learn"],
    "cast": ["## Subgenres"],
    "structure-review": ["## Subgenres"],
    "research": ["## Research", "Places then and now"],
    "gen-world": ["## Research"],
    "appendix": ["## Back matter", "Places you can still see"],
    "draft-pass": ["genre guide"],
    "revision-pass": ["genre guide"],
    "genre": ["autonovel genre show", "shared/genres/"],
}


@pytest.mark.parametrize("stem", sorted(READERS))
def test_command_reads_its_guide_sections(stem: str) -> None:
    text = (COMMANDS / f"{stem}.md").read_text(encoding="utf-8")
    front = text.split("\n---", 2)[0]
    assert "shared/craft/genres/" in front, f"{stem}: guide not declared in reads"
    text = " ".join(text.split())
    for needle in READERS[stem]:
        assert needle in text, f"{stem}: does not mention {needle!r}"


def test_design_validate_warns_without_the_ledger(tmp_path: Path) -> None:
    root = _series(tmp_path)
    book = root / "books" / "b"
    (book / "design.md").write_text("# Design\n\n## Shape\n- chapters: 3\n", encoding="utf-8")
    rep = design_mod.check(book)
    assert any("What the reader comes to learn" in w for w in rep.warnings)
    (book / "design.md").write_text(
        "# Design\n\n## Shape\n- chapters: 3\n\n## What the reader comes to learn\n"
        "- events: the vote: ch 3 — a scene\n", encoding="utf-8")
    rep = design_mod.check(book)
    assert not any("What the reader comes to learn" in w for w in rep.warnings)


def test_next_actions_ask_for_the_subgenre_and_the_guide(tmp_path: Path) -> None:
    from autonovel.housekeeping import next_actions
    root = _series(tmp_path)
    layout = scaffold.SeriesLayout(root=root)
    titles = [a.title for a in next_actions.enumerate_actions(layout, book="b")]
    assert any(t.startswith("Name b's subgenre") for t in titles)
    (root / "shared" / "craft" / "genres" / "historical.md").unlink()
    acts = next_actions.enumerate_actions(layout, book="b")
    assert any(a.command == "autonovel refresh-templates" for a in acts)
    cfg = project.load(root / "project.yaml")
    cfg.genre, cfg.subgenres = "sci-fi", ["hard-sf"]
    project.dump(cfg, root / "project.yaml")
    acts = next_actions.enumerate_actions(layout, book="b")
    assert any(a.command == "/autonovel:genre --add science-fiction" for a in acts)
