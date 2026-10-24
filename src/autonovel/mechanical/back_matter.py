"""Build a `back_matter.tex` for typeset's PDF path.

Reads optional `appendix.md` from the book's root, converts paragraphs
via the existing md_to_latex pipeline, wraps each in a starred
chapter heading (`\\chapter*{}` so it's unnumbered and excluded from
the chapter numbering), and concatenates the result. The output is
`\\input{}`-able from novel.tex, in the `\\backmatter` zone (after
the last chapter).

The `\\backmatter` LaTeX command must precede this content (already
the case in novel.tex). When the appendix doesn't exist, returns
("", []) and the typeset workflow simply doesn't write
`back_matter.tex` — novel.tex's `\\IfFileExists` then silently skips
inclusion.

Why a separate module from front_matter.py: front and back matter
sit in different LaTeX zones (`\\frontmatter` vs `\\backmatter`),
need different `\\input{}` lines in novel.tex, and grow at different
rates (back matter typically grows over multi-book series with
appendix sections accumulating). Keeping them in parallel files
matches the LaTeX layout and keeps the contract obvious.

Markdown shape supported (intentionally narrow — same as
front_matter.py):

  - paragraphs separated by blank lines
  - `*italic*`
  - smart-quote / em-dash / en-dash conversion
  - `---` scene breaks (rare but allowed)
  - `## Sub-heading` is allowed in appendix (unlike preface) since
    the appendix often has labelled sections (Timeline of events,
    Bios, Notes on sources, etc.). These render as `\\section*{}`
    in the LaTeX output.

Headings inside the appendix file:
  - `# Title` at the top is dropped — we emit our own canonical
    `\\chapter*{Appendix}` heading.
  - `## Section` lines are promoted to `\\section*{}` (unnumbered;
    not in the TOC by default, but appendix is itself a TOC entry
    so navigation still works).
"""

from __future__ import annotations

import re
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .latex import latex_escape, md_to_latex


_SUBHEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
# `### Sub-sub-heading` — the appendix Sources section commonly has
# `## Sources` then `### Primary` / `### Secondary` underneath.
# Without this rule those `###` lines render literally in the PDF
# / ePub (user 2026-04-30 reported markdown remnants in Sources).
_SUBSUBHEADING_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^[-*]\s+(.*\S)\s*$")


def _lists_to_itemize(body: str) -> str:
    """Turn markdown bullet lists into `itemize` blocks. Without this a
    list's lines ran together into one paragraph in the PDF: the cast
    list and the timeline of kingmaker2's appendix came out as a single
    run of text (2026-10-24). An indented line continues the item above
    it; a blank line or any other line ends the list."""
    out: list[str] = []
    in_list = False
    for line in body.splitlines():
        m = _LIST_ITEM_RE.match(line)
        if m:
            if not in_list:
                out.append("\\begin{itemize}\\setlength{\\itemsep}{0.15em}")
                in_list = True
            out.append(f"\\item {m.group(1)}")
        elif in_list and line.startswith((" ", "\t")) and line.strip():
            out[-1] += " " + line.strip()
        else:
            if in_list:
                out.append("\\end{itemize}")
                in_list = False
            out.append(line)
    if in_list:
        out.append("\\end{itemize}")
    return "\n".join(out)


def build_back_matter_tex(
    book_root: Path,
    *,
    output: Path | None = None,
) -> tuple[str, list[str]]:
    """Concatenate appendix into one back-matter LaTeX block.
    Returns the generated TeX and a list of section titles included
    (`["Appendix"]` typically; future expansion can add more).

    The appendix file is optional; when absent the helper returns
    ("", []) and writing is skipped.
    """
    sections: list[tuple[str, Path]] = []
    appendix = book_root / "appendix.md"
    if appendix.is_file():
        sections.append(("Appendix", appendix))

    if not sections:
        return "", []

    pieces: list[str] = []
    titles: list[str] = []
    for title, path in sections:
        body = strip_yaml_frontmatter(path.read_text(encoding="utf-8")).strip()
        # Drop the `# Title` line if present (we emit our own).
        body_lines = body.splitlines()
        if body_lines and body_lines[0].strip().startswith("# "):
            body_lines = body_lines[1:]
            while body_lines and body_lines[0].strip() == "":
                body_lines.pop(0)
        body = "\n".join(body_lines)

        # Promote `### Sub-sub-heading` BEFORE `## Sub-heading`
        # (otherwise the `##` rule would partial-match the leading
        # two hashes of a `###` line and leave `# Title` behind).
        body = _SUBSUBHEADING_RE.sub(
            lambda m: f"\\subsection*{{{latex_escape(m.group(1))}}}",
            body,
        )
        body = _SUBHEADING_RE.sub(
            lambda m: f"\\section*{{{latex_escape(m.group(1))}}}",
            body,
        )

        body = _lists_to_itemize(body)
        latex_body = md_to_latex(body)
        # `\markboth{}{<title>}` resets the running header on the
        # recto to "Appendix" — without it, the header inherits the
        # last numbered \chaptermark value ("Chapter 24") and the
        # appendix pages still read as the last chapter. User
        # 2026-04-30 hit this exact bug.
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
