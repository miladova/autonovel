"""Tier-1 tests for `src/autonovel/mechanical/latex.py`.

Covers the three things `/autonovel:typeset` leans on:

  - `latex_escape` — the five special characters.
  - `md_to_latex` — scene-break translation, italic, quotes, dashes.
  - `build_chapters_tex` — multi-chapter build, drop caps, ornament
    wiring with PDF-preferred-over-PNG.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autonovel.mechanical.latex import (
    build_chapters_tex,
    find_ornament,
    latex_escape,
    make_drop_cap,
    md_to_latex,
)


class TestLatexEscape:
    @pytest.mark.parametrize(
        "raw,escaped",
        [
            ("a & b", r"a \& b"),
            ("50% off", r"50\% off"),
            ("$5", r"\$5"),
            ("#hashtag", r"\#hashtag"),
            ("snake_case", r"snake\_case"),
        ],
    )
    def test_special_characters(self, raw: str, escaped: str) -> None:
        assert latex_escape(raw) == escaped


class TestMdToLatex:
    def test_scene_break(self) -> None:
        out = md_to_latex("paragraph one\n\n---\n\nparagraph two")
        assert "\\scenebreak" in out

    def test_italic(self) -> None:
        assert "\\textit{word}" in md_to_latex("a *word* here")

    def test_em_dash(self) -> None:
        assert "---" in md_to_latex("word—word")

    def test_en_dash(self) -> None:
        assert "--" in md_to_latex("p. 10–12")

    def test_smart_quotes(self) -> None:
        out = md_to_latex("“hello,” she said")
        assert "``hello,''" in out

    def test_straight_quotes_folded(self) -> None:
        out = md_to_latex('"Go," he said')
        assert "``Go,''" in out

    def test_ellipsis(self) -> None:
        assert "\\ldots{}" in md_to_latex("and then…")

    def test_ampersand_escaped(self) -> None:
        assert r"\&" in md_to_latex("Smith & Co.")

    def test_bold(self) -> None:
        """User 2026-04-30 reported `**` markers showing literally
        in the appendix Sources + timeline date. Root cause: the
        regex only handled `*italic*`, not `**bold**`."""
        assert "\\textbf{1492-08-03}" in md_to_latex("**1492-08-03** event")

    def test_bold_does_not_consume_italic(self) -> None:
        """Bold and italic on the same line must coexist."""
        out = md_to_latex("**Plot:** *italics inside*")
        assert "\\textbf{Plot:}" in out
        assert "\\textit{italics inside}" in out

    def test_bold_with_special_char_inside(self) -> None:
        """Bold containing an ampersand still works — the bold
        regex runs BEFORE latex_escape, so the `&` inside the
        bold gets escaped to `\\&` correctly."""
        out = md_to_latex("**Smith & Co.** publisher")
        assert "\\textbf{Smith \\& Co.}" in out


class TestDropCap:
    def test_simple_paragraph(self) -> None:
        out = make_drop_cap("Cass woke up.")
        assert "\\lettrine" in out
        assert "{C}" in out

    def test_multi_word_first_word(self) -> None:
        out = make_drop_cap("Hello world, and more.")
        assert "{H}" in out
        assert "{ello}" in out

    def test_empty_body_noop(self) -> None:
        assert make_drop_cap("") == ""

    def test_preserves_rest_of_body(self) -> None:
        body = "First paragraph.\n\nSecond paragraph here."
        out = make_drop_cap(body)
        assert "Second paragraph here." in out


class TestBuildChaptersTex:
    def _seed_chapters(self, root: Path, count: int = 2) -> Path:
        ch_dir = root / "chapters"
        ch_dir.mkdir()
        for i in range(1, count + 1):
            (ch_dir / f"ch_{i:02d}.md").write_text(
                f"# Chapter {i}: Title {i}\n\nFirst paragraph of chapter {i}.\n\n"
                f"Second paragraph here.\n",
                encoding="utf-8",
            )
        return ch_dir

    def test_builds_two_chapters(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path, count=2)
        content, reports = build_chapters_tex(ch_dir)
        assert len(reports) == 2
        assert "\\chapter{Title 1}" in content
        assert "\\chapter{Title 2}" in content
        assert "\\clearpage" in content

    def test_drops_cap_on_each_chapter(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path, count=2)
        content, _ = build_chapters_tex(ch_dir)
        assert content.count("\\lettrine") == 2

    def test_writes_output_file(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path)
        output = tmp_path / "out" / "chapters_content.tex"
        content, _ = build_chapters_tex(ch_dir, output=output)
        assert output.read_text(encoding="utf-8") == content

    def test_empty_dir_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "chapters"
        empty.mkdir()
        with pytest.raises(FileNotFoundError):
            build_chapters_tex(empty)

    def test_ornament_pdf_preferred_over_png(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path, count=1)
        art = tmp_path / "art"
        (art / "pdf").mkdir(parents=True)
        (art / "pdf" / "ornament_ch01.pdf").write_bytes(b"%PDF-1.4")
        (art / "ornament_ch01.png").write_bytes(b"PNG")
        content, reports = build_chapters_tex(ch_dir, art_dir=art)
        assert reports[0].ornament is not None
        assert reports[0].ornament.suffix == ".pdf"
        assert "ornament_ch01.pdf" in content

    def test_ornament_png_used_when_pdf_absent(self, tmp_path: Path) -> None:
        ch_dir = self._seed_chapters(tmp_path, count=1)
        art = tmp_path / "art"
        art.mkdir()
        (art / "ornament_ch01.png").write_bytes(b"PNG")
        content, _ = build_chapters_tex(ch_dir, art_dir=art)
        assert "ornament_ch01.png" in content

    def test_find_ornament_returns_none_when_missing(self, tmp_path: Path) -> None:
        art = tmp_path / "art"
        art.mkdir()
        assert find_ornament(art, 5) is None

    def test_yaml_frontmatter_is_stripped(self, tmp_path: Path) -> None:
        """Regression for the 2026-04-25 PDF bug: when a chapter file
        opens with YAML frontmatter (book / chapter / pov / word_count
        / story_time / events / status — what every real autonovel
        chapter has), the previous build_chapters_tex treated lines[0]
        as the title (`---`) and rendered every frontmatter field as
        prose at the top of the chapter. Locking the fix: the
        frontmatter must NOT appear in the rendered LaTeX, AND the
        chapter title must come from the `# Title` heading, NOT
        from the frontmatter delimiter."""
        ch_dir = tmp_path / "chapters"
        ch_dir.mkdir()
        (ch_dir / "ch_01.md").write_text(
            "---\n"
            "book: tiny\n"
            "chapter: 1\n"
            "pov: Tommaso\n"
            "story_time: 1521-12-04\n"
            "events: []\n"
            "status: drafted\n"
            "word_count: 3245\n"
            "---\n"
            "# The Real Chapter Title\n"
            "\n"
            "First sentence of actual prose.\n",
            encoding="utf-8",
        )
        content, reports = build_chapters_tex(ch_dir)
        # Frontmatter must not leak as visible prose.
        assert "book: tiny" not in content
        assert "word_count" not in content
        assert "Tommaso" not in content
        assert "story\\_time" not in content  # underscore escapes
        assert "story_time" not in content    # raw too
        assert "events: []" not in content
        # Real title comes from the `# …` heading, not `---`.
        assert "\\chapter{The Real Chapter Title}" in content
        assert "\\chapter{---}" not in content
        # Real prose still renders.
        assert "First sentence of actual prose." in content
        assert reports[0].title == "The Real Chapter Title"

    def test_chapter_without_title_heading_emits_empty_chapter_arg(
        self, tmp_path: Path
    ) -> None:
        """Regression for the 2026-04-28 PDF bug: real chapter files
        produced by `/autonovel:draft` are YAML frontmatter + prose
        only, NO `# Title` heading. The previous implementation took
        `lines[0]` of the post-frontmatter body — i.e. the first
        sentence of prose — and rendered it as `\\chapter{<sentence>}`,
        producing a large italic block at every chapter's title page
        and (with stale novel.tex) feeding `\\markboth` so old
        templates surfaced it as alternating page headers via
        `\\textit{\\leftmark}`. Lock the fix: when there's no title,
        emit `\\chapter{}` and let `\\titleformat` print "chapter
        <Roman>" alone."""
        ch_dir = tmp_path / "chapters"
        ch_dir.mkdir()
        first_sentence = (
            "Tommaso looked up at the apothecary's broken sign and "
            "wondered when the rain would stop."
        )
        (ch_dir / "ch_01.md").write_text(
            "---\n"
            "book: tiny\n"
            "chapter: 1\n"
            "pov: Tommaso\n"
            "story_time: 1521-12-04\n"
            "events: []\n"
            "status: drafted\n"
            "word_count: 3245\n"
            "---\n\n"
            f"{first_sentence}\n\nMore prose here.\n",
            encoding="utf-8",
        )
        content, reports = build_chapters_tex(ch_dir)
        assert "\\chapter{}" in content, (
            "no-title chapter should render \\chapter{} so titleformat "
            "prints 'chapter <Roman>' alone; instead got: "
            + content[:400]
        )
        # The body of the first sentence (post-drop-cap) MUST appear
        # after the \chapter{} block — not inside its argument.
        body_tail = "ommaso} looked up at the apothecary's broken sign"
        assert body_tail in content
        idx_chapter = content.index("\\chapter")
        idx_close = content.index("}", idx_chapter)
        assert body_tail not in content[idx_chapter:idx_close + 1]
        # Crucially: NO chunk of the original first-sentence prose
        # ends up inside the chapter title argument.
        assert "looked up at the apothecary" not in content[
            idx_chapter:idx_close + 1
        ]
        assert reports[0].title == ""

    def test_title_field_in_frontmatter_wins_over_heading(
        self, tmp_path: Path
    ) -> None:
        """The 2026-04-28 fix added a `title:` slot in chapter
        frontmatter. When set, it wins over a `# Heading` first
        line and over the empty fallback."""
        ch_dir = tmp_path / "chapters"
        ch_dir.mkdir()
        (ch_dir / "ch_01.md").write_text(
            "---\n"
            "chapter: 1\n"
            "title: \"The Glassblower's Lament\"\n"
            "---\n\n"
            "# Some markdown heading the writer left behind\n\n"
            "Prose.\n",
            encoding="utf-8",
        )
        content, reports = build_chapters_tex(ch_dir)
        assert "\\chapter{The Glassblower's Lament}" in content
        assert reports[0].title == "The Glassblower's Lament"


class TestCli:
    def test_build_tex_cli_writes_output(self, tmp_path: Path) -> None:
        ch_dir = tmp_path / "chapters"
        ch_dir.mkdir()
        (ch_dir / "ch_01.md").write_text("# Ch 1: Title\n\nHello.\n", encoding="utf-8")
        out = tmp_path / "out.tex"
        result = subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "build-tex",
             str(ch_dir), "--output", str(out)],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert payload["chapters"] == 1
        assert out.exists()
        assert "\\chapter{Title}" in out.read_text(encoding="utf-8")


class TestChapterTitlesToggle:
    """`project.yaml :: typeset.chapter_titles = false` opt-out for the
    PDF path. When false, per-chapter `title:` extraction is skipped
    and every chapter renders as `\\chapter{}` so `\\titleformat`
    prints "chapter <Roman>" alone (numbers-only TOC + chapter pages).
    """

    def _seed_titled(self, root: Path) -> Path:
        ch_dir = root / "chapters"
        ch_dir.mkdir()
        (ch_dir / "ch_01.md").write_text(
            "---\n"
            "chapter: 1\n"
            "title: The Apothecary's Mortar\n"
            "---\n\n"
            "First sentence of prose.\n",
            encoding="utf-8",
        )
        return ch_dir

    def test_default_keeps_titles(self, tmp_path: Path) -> None:
        ch_dir = self._seed_titled(tmp_path)
        content, reports = build_chapters_tex(ch_dir)
        assert "\\chapter{The Apothecary's Mortar}" in content
        assert reports[0].title == "The Apothecary's Mortar"

    def test_chapter_titles_false_drops_title(self, tmp_path: Path) -> None:
        ch_dir = self._seed_titled(tmp_path)
        content, reports = build_chapters_tex(ch_dir, chapter_titles=False)
        assert "\\chapter{}" in content
        assert "The Apothecary's Mortar" not in content
        assert reports[0].title == ""

    def test_cli_no_chapter_titles_flag(self, tmp_path: Path) -> None:
        ch_dir = self._seed_titled(tmp_path)
        out = tmp_path / "out.tex"
        subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "build-tex",
             str(ch_dir), "--output", str(out), "--no-chapter-titles"],
            capture_output=True, text=True, check=True,
        )
        text = out.read_text(encoding="utf-8")
        assert "\\chapter{}" in text
        assert "The Apothecary's Mortar" not in text

    def test_cli_project_yaml_false(self, tmp_path: Path) -> None:
        ch_dir = self._seed_titled(tmp_path)
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(
            "series_name: tiny\n"
            "typeset:\n"
            "  chapter_titles: false\n",
            encoding="utf-8",
        )
        out = tmp_path / "out.tex"
        subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "build-tex",
             str(ch_dir), "--output", str(out),
             "--project-yaml", str(project_yaml)],
            capture_output=True, text=True, check=True,
        )
        text = out.read_text(encoding="utf-8")
        assert "\\chapter{}" in text
        assert "The Apothecary's Mortar" not in text

    def test_cli_project_yaml_true_keeps_titles(self, tmp_path: Path) -> None:
        ch_dir = self._seed_titled(tmp_path)
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(
            "series_name: tiny\n"
            "typeset:\n"
            "  chapter_titles: true\n",
            encoding="utf-8",
        )
        out = tmp_path / "out.tex"
        subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "build-tex",
             str(ch_dir), "--output", str(out),
             "--project-yaml", str(project_yaml)],
            capture_output=True, text=True, check=True,
        )
        text = out.read_text(encoding="utf-8")
        assert "\\chapter{The Apothecary's Mortar}" in text

    def test_cli_project_yaml_missing_typeset_keeps_titles(
        self, tmp_path: Path,
    ) -> None:
        """Backwards compat: project.yaml with no `typeset:` block
        must not change behaviour."""
        ch_dir = self._seed_titled(tmp_path)
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text("series_name: tiny\n", encoding="utf-8")
        out = tmp_path / "out.tex"
        subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "build-tex",
             str(ch_dir), "--output", str(out),
             "--project-yaml", str(project_yaml)],
            capture_output=True, text=True, check=True,
        )
        text = out.read_text(encoding="utf-8")
        assert "\\chapter{The Apothecary's Mortar}" in text

    def test_no_chapter_titles_overrides_project_yaml_true(
        self, tmp_path: Path,
    ) -> None:
        """Explicit `--no-chapter-titles` flag wins over
        project.yaml's `typeset.chapter_titles: true`."""
        ch_dir = self._seed_titled(tmp_path)
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(
            "series_name: tiny\n"
            "typeset:\n"
            "  chapter_titles: true\n",
            encoding="utf-8",
        )
        out = tmp_path / "out.tex"
        subprocess.run(
            [sys.executable, "-m", "autonovel.mechanical", "build-tex",
             str(ch_dir), "--output", str(out),
             "--project-yaml", str(project_yaml),
             "--no-chapter-titles"],
            capture_output=True, text=True, check=True,
        )
        text = out.read_text(encoding="utf-8")
        assert "\\chapter{}" in text


def test_drop_cap_with_a_one_letter_first_word() -> None:
    """kingmaker2, 2026-10-24: 'A little before five…' put the whole first
    paragraph in lettrine's small-caps box and the line ran off the page."""
    from autonovel.mechanical.latex import make_drop_cap
    out = make_drop_cap("A little before five in the morning, a rider came.\n\nNext.")
    assert out.startswith("\\lettrine[lines=2, lhang=0.1, nindent=0.2em]{A}{} little before five")
    out = make_drop_cap("On a hot night in July.\n")
    assert "{O}{n} a hot night" in out
