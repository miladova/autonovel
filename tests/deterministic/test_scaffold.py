"""New-series and new-book scaffolding (PR 1 acceptance)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autonovel import project as project_mod
from autonovel.housekeeping import scaffold
from autonovel.paths import SeriesLayout


EXPECTED_SHARED_FILES = [
    "shared/world.md",
    "shared/characters.md",
    "shared/canon.md",
    "shared/events.md",
    "shared/timeline.md",
    "shared/MYSTERY.md",
    "shared/period_bans.txt",
    "shared/sources.bib",
    "shared/research/sources.yaml",
]

EXPECTED_SERIES_DIRS = [
    "shared",
    "shared/research",
    "shared/research/seed",
    "shared/research/notes",
    "books",
    ".autonovel",
    ".autonovel/checkpoints",
    ".autonovel/session-notes",
]


def test_new_series_creates_expected_tree(tmp_path: Path) -> None:
    result = scaffold.new_series(tmp_path / "renaissance-europe", series_name="renaissance-europe", genre="historical-fiction")
    root = result.series.root

    assert (root / "project.yaml").is_file()
    for d in EXPECTED_SERIES_DIRS:
        assert (root / d).is_dir(), f"missing {d}"
    for f in EXPECTED_SHARED_FILES:
        assert (root / f).is_file(), f"missing {f}"

    assert (root / ".gitignore").is_file()
    assert (root / ".autonovel/state.json").is_file()

    cfg = project_mod.load(root / "project.yaml")
    assert cfg.series_name == "renaissance-europe"
    assert cfg.genre == "historical"  # the alias is stored as its registry id
    assert cfg.books == []
    assert project_mod.validate(cfg) == []


def test_new_series_rejects_bad_name(tmp_path: Path) -> None:
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.new_series(tmp_path / "Bad Name", series_name="Bad Name")


def test_new_series_rejects_non_empty_target(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "junk").write_text("x", encoding="utf-8")
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.new_series(tmp_path / "demo", series_name="demo")


def test_new_book_creates_book_tree(series_root: Path) -> None:
    series = SeriesLayout(root=series_root)
    result = scaffold.new_book(series, book_name="one", pov="Ana", story_time_range=[2020, 2021])

    book = result.book_root
    assert book.is_dir()
    for rel in ("seed.txt", "voice.md", "outline.md", "canon.md", "pending_canon.md", "state.json", "results.tsv"):
        assert (book / rel).is_file(), f"missing books/one/{rel}"
    for rel in ("chapters", "briefs", "edit_logs", "eval_logs", "typeset"):
        assert (book / rel).is_dir(), f"missing books/one/{rel}/"

    cfg = project_mod.load(series.project_file)
    assert [b.name for b in cfg.books] == ["one"]
    assert cfg.books[0].pov == "Ana"
    assert cfg.books[0].story_time_range == [2020, 2021]
    assert cfg.books[0].context == "series"
    assert "context" not in yaml.safe_load(series.project_file.read_text(encoding="utf-8"))["books"][0]


def test_new_book_isolated_context(series_root: Path) -> None:
    series = SeriesLayout(root=series_root)
    scaffold.new_book(series, book_name="retold", context="isolated")
    cfg = project_mod.load(series.project_file)
    assert cfg.books[0].context == "isolated"
    assert cfg.books[0].is_isolated
    assert yaml.safe_load(series.project_file.read_text(encoding="utf-8"))["books"][0]["context"] == "isolated"
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.new_book(series, book_name="bad", context="whatever")


def test_new_series_keeps_session_notes_dir_in_git(series_root: Path) -> None:
    """An empty dir is not tracked by git, so a cloned series used to
    arrive without .autonovel/session-notes/ and fail `doctor`."""
    assert (series_root / ".autonovel" / "session-notes" / ".gitkeep").is_file()


def test_new_book_rejects_duplicate(series_root: Path) -> None:
    series = SeriesLayout(root=series_root)
    scaffold.new_book(series, book_name="one")
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.new_book(series, book_name="one")


def test_project_yaml_validates_schema(tmp_path: Path) -> None:
    bad = tmp_path / "project.yaml"
    bad.write_text("series_name: ''\nbooks:\n  - name: one\n  - name: one\n", encoding="utf-8")
    cfg = project_mod.load(bad)
    problems = project_mod.validate(cfg)
    assert any("series_name" in p for p in problems)
    assert any("one" in p for p in problems)


def test_two_books_coexist(series_root: Path) -> None:
    series = SeriesLayout(root=series_root)
    scaffold.new_book(series, book_name="one")
    scaffold.new_book(series, book_name="two", pov="B")
    cfg = project_mod.load(series.project_file)
    names = sorted(b.name for b in cfg.books)
    assert names == ["one", "two"]


def test_new_series_writes_agent_conventions(tmp_path: Path) -> None:
    """CLAUDE.md ships in the template; AGENTS.md / GEMINI.md are aliased
    so all three runtimes auto-load the same conventions file."""
    result = scaffold.new_series(tmp_path / "demo", series_name="demo")
    root = result.series.root

    claude = root / "CLAUDE.md"
    assert claude.is_file()
    primary = claude.read_text(encoding="utf-8")
    assert "autonovel series" in primary.lower()
    assert "Operating rules" in primary  # spot-check expected content

    for alias_name in ("AGENTS.md", "GEMINI.md"):
        alias = root / alias_name
        assert alias.exists(), f"{alias_name} missing from scaffolded series"
        # Symlink target points at CLAUDE.md (or the file is a plain copy
        # on a platform that refused the symlink). Either way the
        # contents must match — that is the contract.
        assert alias.read_text(encoding="utf-8") == primary, (
            f"{alias_name} content does not match CLAUDE.md"
        )


def test_seed_template_carries_guided_prompts(tmp_path: Path) -> None:
    """The seed.txt template should be a guided multi-section prompt,
    not a 1-line stub. Author-testing in PR 9 surfaced that a short
    stub leaves writers with no idea how much to fill in."""
    series_result = scaffold.new_series(tmp_path / "demo", series_name="demo")
    book_result = scaffold.new_book(series_result.series, book_name="one")
    seed = (book_result.book_root / "seed.txt").read_text(encoding="utf-8")

    # Expect the six guided sections.
    expected_headings = [
        "## 1. The pitch",
        "## 2. The POV character",
        "## 3. What stands in the way",
        "## 4. What changes by the end",
        "## 5. Period and place",
        "## 6. Anything else",
    ]
    for h in expected_headings:
        assert h in seed, f"seed.txt missing heading: {h}"
    # Each section should ship at least one example so an author sees depth.
    assert seed.lower().count("example") >= 4
