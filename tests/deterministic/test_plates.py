"""Tier-1 tests for `autonovel.housekeeping.plates` and the LaTeX
plates-manifest weave in `autonovel.mechanical.latex`."""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel.housekeeping import plates
from autonovel.housekeeping.scaffold import new_book, new_series
from autonovel.mechanical.latex import build_chapters_tex


@pytest.fixture
def book_root(tmp_path: Path) -> Path:
    res = new_series(tmp_path / "demo", series_name="demo")
    new_book(res.series, book_name="one")
    return res.series.root / "books" / "one"


def _src_image(tmp_path: Path, name: str = "art.png") -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # plausible PNG header
    return p


def test_import_plate_writes_manifest_and_copies_file(tmp_path: Path, book_root: Path) -> None:
    src = _src_image(tmp_path, "venice-1500-map.png")
    result = plates.import_image(
        book_root, src, chapter=1,
        kind="plate", placement="before-chapter",
        caption="Map of Venice, 1500.",
        attribution="Public domain.",
    )
    assert result.kind == "plate"
    assert result.plate is not None
    assert result.plate.slug == "venice-1500-map"
    installed = book_root / "typeset" / "plates" / "venice-1500-map.png"
    assert installed.exists()
    assert installed.read_bytes() == src.read_bytes()
    manifest = book_root / "typeset" / "plates.yaml"
    assert manifest.exists()
    plates_list = plates.read_manifest(manifest)
    assert len(plates_list) == 1
    assert plates_list[0].caption == "Map of Venice, 1500."
    assert plates_list[0].attribution == "Public domain."


def test_import_ornament_replaces_chapter_ornament(tmp_path: Path, book_root: Path) -> None:
    src = _src_image(tmp_path, "woodcut.png")
    result = plates.import_image(
        book_root, src, chapter=3, kind="ornament",
    )
    assert result.kind == "ornament"
    assert result.plate is None
    installed = book_root / "art" / "ornaments" / "ch_03.png"
    assert installed.exists()
    assert installed.read_bytes() == src.read_bytes()
    # No plates manifest written for ornament mode.
    assert not (book_root / "typeset" / "plates.yaml").exists()


def test_re_import_same_slug_refuses_without_force(tmp_path: Path, book_root: Path) -> None:
    src = _src_image(tmp_path, "x.png")
    plates.import_image(book_root, src, chapter=1, slug="map")
    with pytest.raises(plates.ImportError):
        plates.import_image(book_root, src, chapter=1, slug="map")
    # With force=True, allowed.
    result = plates.import_image(book_root, src, chapter=1, slug="map", force=True)
    assert result.overwrote is True


def test_unsupported_extension_rejected(tmp_path: Path, book_root: Path) -> None:
    bogus = tmp_path / "x.gif"
    bogus.write_bytes(b"GIF89a")
    with pytest.raises(plates.ImportError):
        plates.import_image(book_root, bogus, chapter=1)


def test_missing_source_rejected(tmp_path: Path, book_root: Path) -> None:
    with pytest.raises(plates.ImportError):
        plates.import_image(book_root, tmp_path / "no-such.png", chapter=1)


def test_manifest_round_trip(tmp_path: Path, book_root: Path) -> None:
    """Importing two plates produces a sorted, deduplicated manifest."""
    src1 = _src_image(tmp_path, "a.png")
    src2 = _src_image(tmp_path, "b.png")
    plates.import_image(book_root, src2, chapter=5, slug="durer")
    plates.import_image(book_root, src1, chapter=1, slug="venice-1500")
    manifest = book_root / "typeset" / "plates.yaml"
    plates_list = plates.read_manifest(manifest)
    # Sorted by chapter ascending.
    assert [p.chapter for p in plates_list] == [1, 5]
    assert [p.slug for p in plates_list] == ["venice-1500", "durer"]


def test_slugify() -> None:
    assert plates.slugify("Venice, c. 1500") == "venice-c-1500"
    assert plates.slugify("Dürer Portrait!!!") == "d-rer-portrait"
    assert plates.slugify("") == "untitled"


def test_build_chapters_tex_weaves_plates(tmp_path: Path, book_root: Path) -> None:
    """The build-tex pipeline must emit \\includegraphics + caption +
    attribution at the placement declared in plates.yaml."""
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_01.md").write_text(
        "# The Arrival\n\nProse for chapter one.\n", encoding="utf-8",
    )
    src = _src_image(tmp_path, "venice.png")
    plates.import_image(
        book_root, src, chapter=1,
        placement="before-chapter",
        caption="Map of Venice, c. 1500.",
        attribution="Public domain.",
    )
    manifest = book_root / "typeset" / "plates.yaml"
    content, reports = build_chapters_tex(
        chapters, plates_manifest=manifest,
    )
    assert "venice.png" in content
    assert "Map of Venice, c. 1500." in content
    assert "Public domain." in content
    # `before-chapter` produces a dedicated full-page block with
    # `\cleartoverso` (force to even/verso page so chapter heading
    # falls on facing recto) and a single `\clearpage` after.
    # 2026-04-30 fix: previously used `\cleardoublepage` on both
    # sides, which produced extra blank pages.
    assert "\\cleartoverso" in content
    # The plate appears BEFORE the \chapter heading for chapter 1.
    plate_idx = content.find("venice.png")
    chapter_idx = content.find("\\chapter{")
    assert plate_idx < chapter_idx, "before-chapter plate must precede the chapter heading"


def test_before_chapter_plate_uses_plain_pagestyle(
    tmp_path: Path, book_root: Path,
) -> None:
    """Page numbers on plate pages — user 2026-04-30 reported the
    page numbers vanished on image pages. Fix uses `\\thispagestyle{plain}`
    not `{empty}` so the footer page number stays visible."""
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_01.md").write_text(
        "# The Arrival\n\nProse.\n", encoding="utf-8"
    )
    src = _src_image(tmp_path, "venice.png")
    plates.import_image(
        book_root, src, chapter=1,
        placement="before-chapter",
        caption="Map of Venice.",
    )
    manifest = book_root / "typeset" / "plates.yaml"
    content, _ = build_chapters_tex(chapters, plates_manifest=manifest)
    # plate block should use pagestyle{plain} (page numbers visible)
    # rather than {empty} (page numbers suppressed).
    plate_idx = content.find("venice.png")
    # Walk back to find the pagestyle directive in the plate block.
    surrounding = content[max(0, plate_idx - 600):plate_idx]
    assert "thispagestyle{plain}" in surrounding
    assert "thispagestyle{empty}" not in surrounding


def test_chapter_start_plate_renders_at_0_8_textwidth(
    tmp_path: Path, book_root: Path,
) -> None:
    """User 2026-04-30 reported chapter-1 plate too small. The
    chapter-start placement bumped from 0.6 to 0.8 textwidth —
    matches the published-book convention for in-flow opening
    plates while still leaving margin."""
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_01.md").write_text(
        "# The Arrival\n\nProse.\n", encoding="utf-8"
    )
    src = _src_image(tmp_path, "opening.png")
    plates.import_image(
        book_root, src, chapter=1,
        placement="chapter-start",
        caption="Opening flourish.",
    )
    manifest = book_root / "typeset" / "plates.yaml"
    content, _ = build_chapters_tex(chapters, plates_manifest=manifest)
    assert "width=0.8\\textwidth" in content
    # Old 0.6 should not appear for chapter-start placement.
    chapter_start_idx = content.find("opening.png")
    surrounding = content[max(0, chapter_start_idx - 100):chapter_start_idx]
    assert "0.6\\textwidth" not in surrounding


def test_build_chapters_tex_without_manifest(tmp_path: Path, book_root: Path) -> None:
    """No manifest → no plate weaving, no error."""
    chapters = book_root / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "ch_01.md").write_text("# T\n\nP\n", encoding="utf-8")
    content, _ = build_chapters_tex(chapters)
    assert "\\chapter" in content
    assert "\\includegraphics" not in content


def test_import_keeps_keys_added_by_hand(tmp_path: Path, book_root: Path) -> None:
    """kingmaker2, 2026-10-24: importing two maps rewrote the manifest and
    dropped `layout: landscape` from the Venice view and Augsburg plates."""
    import yaml
    first = _src_image(tmp_path, "venice-view.png")
    plates.import_image(book_root, first, chapter=2, kind="plate",
                        placement="before-chapter", caption="Venice.")
    manifest = book_root / "typeset" / "plates.yaml"
    data = yaml.safe_load(manifest.read_text())
    data["plates"][0]["layout"] = "landscape"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False))
    plates.import_image(book_root, _src_image(tmp_path, "map.png"), chapter=1,
                        kind="plate", placement="before-chapter")
    by_slug = {p.slug: p for p in plates.read_manifest(manifest)}
    assert by_slug["venice-view"].extra == {"layout": "landscape"}
    assert "layout: landscape" in manifest.read_text()
    # Re-importing the same slug keeps its hand-added keys too.
    plates.import_image(book_root, first, chapter=2, kind="plate",
                        placement="before-chapter", caption="Venice, 1500.", force=True)
    again = {p.slug: p for p in plates.read_manifest(manifest)}["venice-view"]
    assert again.extra == {"layout": "landscape"} and again.caption == "Venice, 1500."
