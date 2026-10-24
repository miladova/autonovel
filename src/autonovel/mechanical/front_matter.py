"""Build a `front_matter.tex` for typeset's PDF path.

Reads optional `preface.md` (hand-authored) and `introduction.md`
(AI-generated, or hand-authored — the file is just a file) from the
book's root, converts paragraphs via the existing md_to_latex
pipeline, wraps each in a starred chapter heading (`\\chapter*{}` so
it's unnumbered and excluded from the chapter numbering), and
concatenates the result. The output is `\\input{}`-able from
novel.tex.

The `\\frontmatter` LaTeX command must precede this content (already
the case in novel.tex). When neither preface nor introduction
exists, returns ("", []) and the typeset workflow simply doesn't
write `front_matter.tex` — novel.tex's `\\IfFileExists` then
silently skips inclusion.

Markdown shape supported (intentionally narrow — the same shape
md_to_latex already handles):

  - paragraphs separated by blank lines
  - `*italic*`
  - smart-quote / em-dash / en-dash conversion
  - `---` scene breaks (rare in front matter; supported anyway)

Headings inside a preface/introduction file are NOT promoted to
`\\section{}` — front matter typically has one heading (the
chapter*) and uninterrupted prose under it. If a preface needs
sub-headings, hand-edit `front_matter.tex` after generation.
"""

from __future__ import annotations

from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .latex import latex_escape, md_to_latex
from .back_matter import _lists_to_itemize


def build_front_matter_tex(
    book_root: Path,
    *,
    output: Path | None = None,
) -> tuple[str, list[str]]:
    """Concatenate preface + introduction + glossary into one front-
    matter LaTeX block. Returns the generated TeX and a list of
    section titles included (`["Preface", "Introduction",
    "Glossary"]` etc.).

    All three source files are optional; when none exists the helper
    returns ("", []) and writing is skipped. Order is fixed:
    preface (author voice) first, introduction (essay) second,
    glossary (period-vocabulary reference) last so it sits right
    before chapter 1 — readers can flip back to it without paging
    through the introduction.
    """
    sections: list[tuple[str, Path]] = []
    preface = book_root / "preface.md"
    introduction = book_root / "introduction.md"
    glossary = book_root / "glossary.md"
    if preface.is_file():
        sections.append(("Preface", preface))
    if introduction.is_file():
        sections.append(("Introduction", introduction))
    if glossary.is_file():
        sections.append(("Glossary", glossary))

    if not sections:
        return "", []

    pieces: list[str] = []
    titles: list[str] = []
    for title, path in sections:
        body = strip_yaml_frontmatter(path.read_text(encoding="utf-8")).strip()
        # If the file opens with its own `# Title`, drop that line —
        # we emit our own canonical chapter* heading. (Same shape as
        # the ePub builder.)
        body_lines = body.splitlines()
        if body_lines and body_lines[0].strip().startswith("#"):
            body_lines = body_lines[1:]
            while body_lines and body_lines[0].strip() == "":
                body_lines.pop(0)
        body = "\n".join(body_lines)

        # A glossary is usually a list; keep its lines apart (back_matter).
        latex_body = md_to_latex(_lists_to_itemize(body))
        # `\markboth{}{<title>}` resets the running header on the
        # recto to the section's name (Preface / Introduction /
        # Glossary). Without this, the running header inherits the
        # last \chaptermark value, which for an early `\frontmatter`
        # section would inherit nothing useful, or for back-matter
        # would inherit the last numbered chapter ("Chapter 24") —
        # the user 2026-04-30 reported this exact bug for the
        # appendix.
        escaped_title = latex_escape(title)
        chapter_block = (
            f"\\chapter*{{{escaped_title}}}\n"
            f"\\addcontentsline{{toc}}{{chapter}}{{{escaped_title}}}\n"
            f"\\markboth{{}}{{{escaped_title}}}\n\n"
            f"{latex_body}\n"
        )
        pieces.append(chapter_block)
        titles.append(title)

    content = "\n\\clearpage\n\n".join(pieces)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    return content, titles
