#!/usr/bin/env python3
"""Compile By Second Intention chapters into a print-grade trade book PDF via Typst."""
from __future__ import annotations

import re
import sys
from pathlib import Path
import typst

PARTS = {
    1: ("PART ONE", "Per Secundam", "February – March 1943"),
    9: ("PART TWO", "Granulation", "April – June 1943"),
    17: ("PART THREE", "Foreign Bodies", "July – September 1943"),
    25: ("PART FOUR", "Open Wound", "September – November 1943"),
}

ROMAN = [
    "", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX",
]


def escape_typst_inline(s: str) -> str:
    """Convert Markdown inline italics/bold and escape Typst special characters."""
    # Protect markdown bold and italics first with placeholders
    tokens: list[str] = []

    def save_tok(val: str) -> str:
        idx = len(tokens)
        tokens.append(val)
        return f"\x00TOK{idx}\x00"

    # Bold **...**
    s = re.sub(
        r"\*\*(.+?)\*\*",
        lambda m: save_tok(f"#strong[{escape_raw(m.group(1))}]"),
        s,
    )
    # Italic *...*
    s = re.sub(
        r"\*([^*]+?)\*",
        lambda m: save_tok(f"#emph[{escape_raw(m.group(1))}]"),
        s,
    )
    s = escape_raw(s)
    for idx in range(len(tokens) - 1, -1, -1):
        s = s.replace(f"\x00TOK{idx}\x00", tokens[idx])
    return s


def escape_raw(s: str) -> str:
    s = s.replace("\\", "\\\\")
    for ch in ("#", "$", "@", "<", ">", "[", "]", "_", "*", "`", "~"):
        s = s.replace(ch, "\\" + ch)
    # Typographic dashes
    s = s.replace(" --- ", " — ")
    s = s.replace("---", "—")
    s = s.replace(" -- ", " – ")
    return s


def format_lead_paragraph(p: str) -> str:
    """Small-caps the first 3-4 words of a chapter's opening paragraph."""
    m = re.match(r'^([“"\']?\S+(?:\s+\S+){1,2})\s+(.*)$', p, flags=re.DOTALL)
    if not m:
        return f"#par(first-line-indent: 0pt)[{escape_typst_inline(p)}]"
    lead, rest = m.group(1), m.group(2)
    # Avoid splitting inside markdown italics
    if "*" in lead:
        return f"#par(first-line-indent: 0pt)[{escape_typst_inline(p)}]"
    return (
        f"#par(first-line-indent: 0pt)[#smallcaps[{escape_raw(lead)}] "
        f"{escape_typst_inline(rest)}]"
    )


def parse_chapter(path: Path, expected_num: int) -> tuple[int, str, str, list[str]]:
    raw = path.read_text(encoding="utf-8").strip()
    lines = raw.splitlines()
    title = f"Chapter {ROMAN[expected_num]}"
    dateline = ""
    start_idx = 0
    if lines and lines[0].startswith("# "):
        hdr = lines[0][2:].strip()
        # Allow "# Chapter I: Title" or "# Title"
        m = re.match(r"^(?:Chapter\s+[IVXLCDM\d]+\s*[:—-]\s*)?(.+)$", hdr, re.I)
        title = m.group(1).strip() if m else hdr
        start_idx = 1
        while start_idx < len(lines) and not lines[start_idx].strip():
            start_idx += 1
        if start_idx < len(lines) and re.match(r"^\*[^*]+\*$", lines[start_idx].strip()):
            dateline = lines[start_idx].strip().strip("*").strip()
            start_idx += 1

    body = "\n".join(lines[start_idx:]).strip()
    blocks = re.split(r"\n\s*\n", body)
    return expected_num, title, dateline, [b.strip() for b in blocks if b.strip()]


def build_typst_source(chap_dir: Path) -> str:
    files = sorted(chap_dir.glob("ch_*.md"))
    if not files:
        raise SystemExit("No chapters found to compile.")

    chapters = []
    for idx, f in enumerate(files, start=1):
        chapters.append(parse_chapter(f, idx))

    out: list[str] = []
    out.append(r"""
#set document(title: "By Second Intention — Book One")
#set page(
  width: 6in,
  height: 9in,
  margin: (inside: 0.92in, outside: 0.78in, top: 0.88in, bottom: 0.88in),
  numbering: none,
)
#set text(
  font: "Libertinus Serif",
  size: 10.5pt,
  lang: "en",
  region: "GB",
  hyphenate: true,
)
#set par(
  leading: 0.68em,
  justify: true,
  first-line-indent: 1.4em,
  spacing: 0.68em,
)

// Half-title
#page(header: none, footer: none)[
  #v(2.6in)
  #align(center)[
    #text(size: 15pt, tracking: 2.5pt)[#smallcaps[By Second Intention]]
  ]
]

#page(header: none, footer: none)[]

// Full Title Page
#page(header: none, footer: none)[
  #v(1.5in)
  #align(center)[
    #text(size: 9.5pt, tracking: 2.2pt, fill: luma(90))[#smallcaps[Book One]]
    #v(0.35in)
    #line(length: 2.2in, stroke: 0.5pt + luma(120))
    #v(0.32in)
    #text(size: 26pt, tracking: 1.8pt, weight: "regular")[BY SECOND\ INTENTION]
    #v(0.28in)
    #text(size: 12pt, style: "italic", fill: luma(70))[A Novel]
    #v(0.32in)
    #line(length: 2.2in, stroke: 0.5pt + luma(120))
    #v(2.4in)
    #text(size: 9pt, tracking: 1.6pt, fill: luma(90))[#smallcaps[Warsaw · Berlin]]
  ]
]

// Edition / Colophon Front Note
#page(header: none, footer: none)[
  #v(5.1in)
  #set par(first-line-indent: 0pt, leading: 0.72em)
  #text(size: 8.5pt, fill: luma(85))[
    This is a work of historical fiction. While certain institutions, streets, and public events of Berlin (1928–1933) and occupied Warsaw (1943) belong to the historical record, the principal characters and their private actions are inventions of the narrative.

    #v(0.18in)
    Typeset in Libertinus Serif on a Royal Octavo (6 × 9 in.) trim.
  ]
]

// Epigraph
#page(header: none, footer: none)[
  #v(2.35in)
  #pad(left: 0.65in, right: 0.65in)[
    #set par(first-line-indent: 0pt, leading: 0.8em)
    #text(size: 10pt, style: "italic")[
      Sanatio per primam intentionem fit cum vulneris labia, nullo extraneo interposito corpore, mutuo conglutinantur. Sanatio vero per secundam intentionem, cum propter contusionem, sordes aut mortuam carnem vulnus apertum servandum est, donec ex imo nova caro cum cicatrice granulet.
    ]
    #v(0.16in)
    #text(size: 9.5pt)[
      Healing by first intention occurs when the lips of a wound, with no foreign body between them, cleave cleanly together. Healing by second intention occurs when, by reason of bruising, filth, or dead flesh, the wound must be kept open until new flesh granulates upward from the bottom in scar.
    ]
    #v(0.18in)
    #align(right)[
      #text(size: 8.8pt, fill: luma(80))[— #smallcaps[Surgical Compendium, Charité-Krankenhaus, 1928]]
    ]
  ]
]

#page(header: none, footer: none)[]
""")

    # Table of Contents (flows cleanly across front-matter pages with no header/footer)
    out.append(r"""
#pagebreak()
#v(0.4in)
#align(center)[
  #text(size: 12pt, tracking: 2.2pt)[#smallcaps[Contents]]
  #v(0.22in)
]
#block[
  #set par(first-line-indent: 0pt, leading: 0.52em, spacing: 0.36em)
""")
    for num, title, dateline, _ in chapters:
        if num in PARTS:
            p_num, p_title, p_dates = PARTS[num]
            out.append(
                f'  #v(0.1in)\n  #text(size: 8.6pt, tracking: 1.4pt, weight: "bold")[#smallcaps[{escape_raw(p_num + " — " + p_title)}]] '
                f'#text(size: 8.2pt, style: "italic", fill: luma(95))[({escape_raw(p_dates)})]\n  #v(0.02in)'
            )
        out.append(
            f'  #grid(columns: (2.6em, 1fr), gutter: 0.4em, '
            f'[#text(size: 8.8pt, fill: luma(80))[{ROMAN[num]}.]], '
            f'[#text(size: 9.1pt)[{escape_raw(title)}]])'
        )
    out.append("]\n#pagebreak(to: \"odd\")\n")

    # Main Book Body Setup with Running Headers & Folios
    out.append(r"""
#counter(page).update(1)
#let current-chapter = state("chap", "")

#set page(
  header: context {
    let pg = counter(page).get().first()
    let ch = current-chapter.get()
    if ch != "" {
      if calc.even(pg) {
        align(center)[#text(size: 8pt, tracking: 1.6pt, fill: luma(95))[#smallcaps[By Second Intention]]]
      } else {
        align(center)[#text(size: 8pt, tracking: 1.4pt, fill: luma(95))[#smallcaps[#ch]]]
      }
    }
  },
  footer: context {
    let pg = counter(page).get().first()
    align(center)[#text(size: 8.8pt, fill: luma(85))[#pg]]
  },
)
""")

    for num, title, dateline, blocks in chapters:
        if num in PARTS:
            p_num, p_title, p_dates = PARTS[num]
            out.append(f"""
#pagebreak(weak: true, to: "odd")
#current-chapter.update("")
#page(header: none, footer: none)[
  #v(2.3in)
  #align(center)[
    #text(size: 9.5pt, tracking: 2.5pt, fill: luma(85))[#smallcaps[{escape_raw(p_num)}]]
    #v(0.24in)
    #line(length: 1.6in, stroke: 0.45pt + luma(130))
    #v(0.24in)
    #text(size: 20pt, tracking: 1.2pt)[{escape_raw(p_title)}]
    #v(0.18in)
    #text(size: 10pt, style: "italic", fill: luma(85))[{escape_raw(p_dates)}]
  ]
]
#page(header: none, footer: none)[]
""")

        out.append(f"""
#pagebreak(weak: true)
#current-chapter.update("")
#v(0.85in)
#align(center)[
  #text(size: 9pt, tracking: 2.4pt, fill: luma(90))[#smallcaps[Chapter {ROMAN[num]}]]
  #v(0.14in)
  #text(size: 16pt, weight: "regular")[{escape_raw(title)}]
""")
        if dateline:
            out.append(
                f'  #v(0.08in)\n  #text(size: 9.2pt, style: "italic", fill: luma(85))[{escape_raw(dateline)}]\n'
            )
        out.append("]\n#v(0.36in)\n")
        out.append(f'#current-chapter.update("{escape_raw(title)}")\n')

        first_after_break = True
        is_chapter_lead = True
        for b in blocks:
            if re.match(r"^\*\s*\*\s*\*$", b) or b in ("***", "---"):
                out.append(
                    '\n#v(0.22in)\n#align(center)[#text(size: 10pt, tracking: 6pt, fill: luma(90))[\\* \\* \\*]]\n#v(0.22in)\n'
                )
                first_after_break = True
                continue

            # Collapse internal single newlines inside a paragraph
            para = " ".join(ln.strip() for ln in b.splitlines())
            if is_chapter_lead:
                out.append(format_lead_paragraph(para) + "\n\n")
                is_chapter_lead = False
                first_after_break = False
            elif first_after_break:
                out.append(f"#par(first-line-indent: 0pt)[{escape_typst_inline(para)}]\n\n")
                first_after_break = False
            else:
                out.append(escape_typst_inline(para) + "\n\n")

    out.append("""
#v(0.6in)
#align(center)[
  #line(length: 1.4in, stroke: 0.45pt + luma(120))
  #v(0.16in)
  #text(size: 9.2pt, tracking: 2pt, fill: luma(80))[#smallcaps[End of Book One]]
]
""")
    return "\n".join(out)


def main() -> None:
    novel_dir = Path(__file__).resolve().parent
    chap_dir = novel_dir / "chapters"
    typ_path = novel_dir / "internal_notes" / "manuscript.typ"
    pdf_path = novel_dir.parent / "By_Second_Intention.pdf"

    src = build_typst_source(chap_dir)
    typ_path.write_text(src, encoding="utf-8")
    pdf_bytes = typst.compile(str(typ_path))
    pdf_path.write_bytes(pdf_bytes)

    import pypdf
    reader = pypdf.PdfReader(str(pdf_path))
    print(f"Compiled {pdf_path} -> {len(reader.pages)} pages ({len(pdf_bytes) // 1024:,} KB)")


if __name__ == "__main__":
    main()
