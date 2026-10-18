"""Tier-1: chapter datelines and landscape plates in the PDF and ePub.

Bug class (author, 2026-10-18, on a book that alternates 1519 with
1473–1518): "Need clear date changes for constant chapter back and forth
by dates" — the place and date must sit under every chapter title. And a
wide city view (de' Barbari's Venice) printed as a strip across a
portrait page was "way too small to be of interest": `layout:
landscape` turns the plate's page sideways.
"""

from __future__ import annotations

from pathlib import Path

from autonovel.mechanical import epub, latex


def _book(tmp: Path, *, dateline: str | None, layout: str | None) -> Path:
    book = tmp / "b"
    ch = book / "chapters"
    ch.mkdir(parents=True)
    dl = f'dateline: "{dateline}"\n' if dateline else ""
    (ch / "ch_01.md").write_text(
        f"---\nbook: b\nchapter: 1\ntitle: The Gate\n{dl}story_time: 1473-09\n---\n\nHe came in.\n",
        encoding="utf-8")
    ts = book / "typeset"
    (ts / "plates").mkdir(parents=True)
    (ts / "plates" / "view.jpg").write_bytes(b"\xff\xd8\xff")
    lay = f"  layout: {layout}\n" if layout else ""
    (ts / "plates.yaml").write_text(
        "plates:\n- slug: view\n  file: plates/view.jpg\n  placement: before-chapter\n"
        f"  chapter: 1\n  caption: A view.\n{lay}", encoding="utf-8")
    return book


def test_frontmatter_value_reads_quoted_and_bare() -> None:
    text = '---\ntitle: X\ndateline: "Venice, autumn 1473"\nfoo: bar\n---\nBody\n'
    assert latex.frontmatter_value(text, "dateline") == "Venice, autumn 1473"
    assert latex.frontmatter_value(text, "foo") == "bar"
    assert latex.frontmatter_value(text, "missing") == ""
    assert latex.frontmatter_value("no frontmatter", "dateline") == ""


def test_latex_prints_dateline_under_the_title(tmp_path: Path) -> None:
    book = _book(tmp_path, dateline="Venice, autumn 1473", layout=None)
    tex, _ = latex.build_chapters_tex(book / "chapters",
                                      plates_manifest=book / "typeset" / "plates.yaml")
    title_at = tex.index("\\chapter{The Gate}")
    date_at = tex.index("Venice, autumn 1473")
    assert title_at < date_at < tex.index("He came in")
    assert "\\begin{landscape}" not in tex


def test_latex_landscape_plate_turns_the_page(tmp_path: Path) -> None:
    book = _book(tmp_path, dateline=None, layout="landscape")
    tex, _ = latex.build_chapters_tex(book / "chapters",
                                      plates_manifest=book / "typeset" / "plates.yaml")
    assert "\\begin{landscape}" in tex and "\\end{landscape}" in tex
    assert tex.index("\\end{landscape}") < tex.index("\\chapter{The Gate}")


def test_epub_dateline_and_wide_plate(tmp_path: Path) -> None:
    book = _book(tmp_path, dateline="Augsburg, January 1519", layout="landscape")
    md, _ = epub.build_epub_md(book / "chapters",
                               plates_manifest=book / "typeset" / "plates.yaml")
    assert '<p class="dateline">Augsburg, January 1519</p>' in md
    assert md.index("# Chapter 1: The Gate") < md.index('class="dateline"')
    assert "width: 100%; max-width: 1400px;" in md


def test_template_loads_pdflscape_and_styles_dateline() -> None:
    root = Path(__file__).resolve().parents[2] / "src/autonovel/templates/series/typeset"
    assert "\\usepackage{pdflscape}" in (root / "novel.tex").read_text(encoding="utf-8")
    assert "p.dateline" in (root / "epub_style.css").read_text(encoding="utf-8")
