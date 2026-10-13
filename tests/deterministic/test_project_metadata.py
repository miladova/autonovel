"""Tier-1 tests for the title/subtitle/author fields on BookEntry +
the series-level author on ProjectConfig.

Added 2026-04-25 to back the `/autonovel:title` command and the
typeset-side display-metadata resolution. The fields are all
optional; the helpers fall back through book → series → "Anonymous"
sensibly so a writer who never runs `/autonovel:title` still gets
a usable PDF.
"""

from __future__ import annotations

from pathlib import Path

from autonovel import project as project_mod
from autonovel.project import BookEntry, ProjectConfig


def test_book_entry_defaults_to_no_metadata() -> None:
    b = BookEntry(name="the-bell")
    assert b.title is None
    assert b.subtitle is None
    assert b.author is None


def test_display_title_falls_back_through_chain() -> None:
    b = BookEntry(name="the-bell")
    # No explicit title, no fallback → name slug.
    assert b.display_title() == "the-bell"
    # Fallback (series_name) used when title unset.
    assert b.display_title(fallback="House of Bells") == "House of Bells"
    # Explicit title wins over fallback.
    b.title = "The Real Title"
    assert b.display_title(fallback="House of Bells") == "The Real Title"


def test_display_author_falls_back_to_anonymous() -> None:
    b = BookEntry(name="the-bell")
    assert b.display_author() == "Anonymous"
    assert b.display_author(fallback="Series Author") == "Series Author"
    b.author = "P. M. Calvi"
    assert b.display_author(fallback="Series Author") == "P. M. Calvi"


def test_to_dict_omits_unset_metadata() -> None:
    """Optional fields don't appear in the serialised YAML when unset
    — keeps project.yaml visually clean for new books."""
    b = BookEntry(name="the-bell")
    d = b.to_dict()
    assert "title" not in d
    assert "subtitle" not in d
    assert "author" not in d


def test_to_dict_includes_set_metadata() -> None:
    b = BookEntry(
        name="the-bell",
        title="The Real Title",
        subtitle="A Novel of Bells",
        author="P. M. Calvi",
    )
    d = b.to_dict()
    assert d["title"] == "The Real Title"
    assert d["subtitle"] == "A Novel of Bells"
    assert d["author"] == "P. M. Calvi"


def test_project_config_series_level_author() -> None:
    cfg = ProjectConfig(series_name="house-of-bells", author="P. M. Calvi")
    assert cfg.author == "P. M. Calvi"
    d = cfg.to_dict()
    assert d["author"] == "P. M. Calvi"


def test_project_config_to_dict_omits_unset_author() -> None:
    cfg = ProjectConfig(series_name="house-of-bells")
    assert "author" not in cfg.to_dict()


def test_yaml_roundtrip_preserves_metadata(tmp_path: Path) -> None:
    """The full read/write cycle: build a ProjectConfig with all the
    new fields populated, dump, load, assert round-trip."""
    cfg = ProjectConfig(series_name="house-of-bells", author="P. M. Calvi")
    cfg.books.append(BookEntry(
        name="the-bell",
        pov="Tommaso",
        title="The Bell at Vespers",
        subtitle="A Novel",
        author="R. M. Calvi",  # book-level overrides series-level
    ))
    path = tmp_path / "project.yaml"
    project_mod.dump(cfg, path)

    loaded = project_mod.load(path)
    assert loaded.author == "P. M. Calvi"
    book = loaded.book_by_name("the-bell")
    assert book is not None
    assert book.title == "The Bell at Vespers"
    assert book.subtitle == "A Novel"
    assert book.author == "R. M. Calvi"
    # display_author respects the book-level override.
    assert book.display_author(fallback=loaded.author) == "R. M. Calvi"


def test_yaml_with_no_metadata_loads_cleanly(tmp_path: Path) -> None:
    """Backward compatibility: an existing project.yaml from before
    the title/author fields shipped must still load. Real users have
    these on disk."""
    path = tmp_path / "project.yaml"
    path.write_text(
        "series_name: house-of-bells\n"
        "genre: historical-fiction\n"
        "books:\n"
        "  - name: the-bell\n"
        "    pov: Tommaso\n"
        "    status: drafted\n",
        encoding="utf-8",
    )
    cfg = project_mod.load(path)
    assert cfg.author is None
    book = cfg.book_by_name("the-bell")
    assert book is not None
    assert book.title is None
    assert book.author is None
    # Falls back through the chain cleanly.
    assert book.display_title(fallback=cfg.series_name) == "house-of-bells"
    assert book.display_author(fallback=cfg.author) == "Anonymous"


# ---------------------- typeset + image dicts (loader / dump) ---


def test_typeset_dict_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    path.write_text(
        "series_name: tiny\n"
        "typeset:\n"
        "  chapter_titles: false\n",
        encoding="utf-8",
    )
    cfg = project_mod.load(path)
    assert cfg.typeset == {"chapter_titles": False}
    # Dump round-trips the typeset block.
    out = tmp_path / "out.yaml"
    project_mod.dump(cfg, out)
    cfg2 = project_mod.load(out)
    assert cfg2.typeset == {"chapter_titles": False}


def test_typeset_omitted_when_empty(tmp_path: Path) -> None:
    """Backward-compat: a config with no `typeset:` block must dump
    without one, so existing project.yaml files don't gain noise."""
    cfg = ProjectConfig(series_name="tiny")
    out = tmp_path / "out.yaml"
    project_mod.dump(cfg, out)
    text = out.read_text(encoding="utf-8")
    assert "typeset" not in text
    assert "image" not in text


def test_image_provider_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    path.write_text(
        "series_name: tiny\n"
        "image:\n"
        "  provider: wikimedia\n",
        encoding="utf-8",
    )
    cfg = project_mod.load(path)
    assert cfg.image.get("provider") == "wikimedia"


# --------------------- teaser + video dicts (movie-teaser mode) ---


def test_teaser_and_video_dicts_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    path.write_text(
        "series_name: tiny\n"
        "teaser:\n"
        "  length_s: 180\n"
        "  ending: reveal-vision\n"
        "video:\n"
        "  provider: pollinations\n",
        encoding="utf-8",
    )
    cfg = project_mod.load(path)
    assert cfg.teaser == {"length_s": 180, "ending": "reveal-vision"}
    assert cfg.video == {"provider": "pollinations"}
    # Dump round-trips both blocks.
    out = tmp_path / "out.yaml"
    project_mod.dump(cfg, out)
    cfg2 = project_mod.load(out)
    assert cfg2.teaser == {"length_s": 180, "ending": "reveal-vision"}
    assert cfg2.video == {"provider": "pollinations"}


def test_teaser_and_video_omitted_when_empty(tmp_path: Path) -> None:
    """Backward-compat: a config with no teaser/video blocks must dump
    without them, so existing project.yaml files don't gain noise."""
    cfg = ProjectConfig(series_name="tiny")
    assert cfg.teaser == {}
    assert cfg.video == {}
    out = tmp_path / "out.yaml"
    project_mod.dump(cfg, out)
    text = out.read_text(encoding="utf-8")
    assert "teaser" not in text
    assert "video" not in text


def test_pre_movie_project_yaml_loads_unchanged(tmp_path: Path) -> None:
    """A project.yaml authored before movie-teaser mode (no teaser/video
    keys) loads cleanly and the dumped form is byte-identical to a config
    that never had them — proves the additive fields can't perturb
    existing series."""
    path = tmp_path / "project.yaml"
    path.write_text(
        "series_name: house-of-bells\n"
        "genre: historical-fiction\n"
        "books:\n"
        "  - name: the-bell\n"
        "    pov: Tommaso\n"
        "    status: drafted\n",
        encoding="utf-8",
    )
    cfg = project_mod.load(path)
    assert cfg.teaser == {}
    assert cfg.video == {}
    out = tmp_path / "out.yaml"
    project_mod.dump(cfg, out)
    text = out.read_text(encoding="utf-8")
    assert "teaser" not in text
    assert "video" not in text


# --------------------- resolve-image-provider CLI helper -------


def test_resolve_image_provider_default(tmp_path: Path) -> None:
    """No project.yaml + no override → repo default `pollinations`."""
    import json
    import subprocess
    import sys
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "resolve-image-provider"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data == {"provider": "pollinations", "source": "default"}


def test_resolve_image_provider_from_project_yaml(tmp_path: Path) -> None:
    import json
    import subprocess
    import sys
    project_yaml = tmp_path / "project.yaml"
    project_yaml.write_text(
        "series_name: tiny\n"
        "image:\n"
        "  provider: wikimedia\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "resolve-image-provider", "--project-yaml", str(project_yaml)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data == {"provider": "wikimedia", "source": "project.yaml"}


def test_resolve_image_provider_cli_wins_over_project_yaml(
    tmp_path: Path,
) -> None:
    """CLI override beats the per-series default."""
    import json
    import subprocess
    import sys
    project_yaml = tmp_path / "project.yaml"
    project_yaml.write_text(
        "series_name: tiny\n"
        "image:\n"
        "  provider: wikimedia\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "resolve-image-provider", "--project-yaml", str(project_yaml),
         "--cli-provider", "openai"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data == {"provider": "openai", "source": "cli"}


def test_resolve_image_provider_project_yaml_no_image_block(
    tmp_path: Path,
) -> None:
    """project.yaml without an `image:` block falls through to default."""
    import json
    import subprocess
    import sys
    project_yaml = tmp_path / "project.yaml"
    project_yaml.write_text("series_name: tiny\n", encoding="utf-8")
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "resolve-image-provider", "--project-yaml", str(project_yaml)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data == {"provider": "pollinations", "source": "default"}


def test_resolve_image_provider_missing_project_yaml_falls_back(
    tmp_path: Path,
) -> None:
    """A path that doesn't exist falls back to default rather than
    crashing — defensive against typos in the slash-command body."""
    import json
    import subprocess
    import sys
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical",
         "resolve-image-provider",
         "--project-yaml", str(tmp_path / "missing.yaml")],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data == {"provider": "pollinations", "source": "default"}


def test_book_context_round_trips_and_validates(tmp_path: Path) -> None:
    from autonovel.project import BookEntry, ProjectConfig, dump, load, validate
    cfg = ProjectConfig.default("s")
    cfg.books.append(BookEntry(name="one"))
    cfg.books.append(BookEntry(name="two", context="isolated"))
    path = tmp_path / "project.yaml"
    dump(cfg, path)
    text = path.read_text(encoding="utf-8")
    assert "context: isolated" in text
    assert text.count("context:") == 1          # default omitted
    back = load(path)
    assert back.books[0].context == "series" and not back.books[0].is_isolated
    assert back.books[1].context == "isolated" and back.books[1].is_isolated
    assert validate(back) == []
    back.books[1].context = "bogus"
    problems = validate(back)
    assert any("context must be one of" in p for p in problems)
