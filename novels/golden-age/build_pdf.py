#!/usr/bin/env python3
"""Build a Royal Octavo (6x9 in) print-grade PDF for Book One using Typst + EB Garamond."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import typst
import yaml

BOOK_DIR = Path(__file__).resolve().parent / "books" / "book-one"
FONTS_DIR = Path(__file__).resolve().parent / "typeset" / "fonts"

PARTS = {
    1: ("PART ONE", "The Blood of the Right-Hand Horse", "October, AD 156 – March, AD 157"),
    7: ("PART TWO", "Chalk and Flour", "May, AD 157 – October, AD 158"),
    13: ("PART THREE", "The Narrow Stripe and the Stola", "March, AD 159 – December, AD 159"),
    19: ("PART FOUR", "Dog-Star Over Subura", "March, AD 160 – October, AD 160"),
    25: ("PART FIVE", "Aequanimitas", "December, AD 160 – March, AD 161"),
}

ROMAN = [
    "", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX",
]


def parse_chapter(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?\n)---\s*\n", raw, flags=re.DOTALL)
    meta = yaml.safe_load(m.group(1)) if m else {}
    body = raw[m.end():].lstrip() if m else raw.lstrip()

    title = f"Chapter {meta.get('chapter', '')}"
    dateline = ""
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        heading = lines.pop(0)[2:].strip()
        heading = re.sub(r"^Chapter\s+[0-9IVXLCDM]+\s*[—–:\-]\s*", "", heading, flags=re.IGNORECASE)
        title = heading
        while lines and not lines[0].strip():
            lines.pop(0)
    if lines and lines[0].startswith("*") and lines[0].endswith("*") and len(lines[0]) < 120:
        dateline = lines.pop(0).strip("* ").strip()
        while lines and not lines[0].strip():
            lines.pop(0)

    prose = "\n".join(lines).strip()
    words = len(re.findall(r"\b\w+\b", prose))
    return {
        "num": int(meta.get("chapter", 0)),
        "pov": str(meta.get("pov", "")),
        "story_time": str(meta.get("story_time", "")),
        "title": title,
        "dateline": dateline,
        "prose": prose,
        "words": words,
    }


def escape_typst_inline(text: str) -> str:
    """Convert markdown inline bold/italics (including nested spans) and escape Typst syntax safely."""
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    text = text.replace("\\", "\\\\")
    for ch in ("#", "$", "@", "<", ">", "~", "^", "[", "]"):
        text = text.replace(ch, "\\" + ch)
    text = text.replace("---", "—").replace("--", "–")

    out: list[str] = []
    stack: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "*":
            j = i
            while j < n and text[j] == "*":
                j += 1
            run = j - i
            i = j
            while run > 0:
                if run >= 3:
                    if stack and stack[-1] == "*":
                        out.append("]")
                        stack.pop()
                        run -= 1
                    elif stack and stack[-1] == "**":
                        out.append("]")
                        stack.pop()
                        run -= 2
                    else:
                        out.append("#strong[#emph[")
                        stack.append("**")
                        stack.append("*")
                        run -= 3
                elif run == 2:
                    if "**" in stack:
                        while stack and stack[-1] != "**":
                            out.append("]")
                            stack.pop()
                        out.append("]")
                        stack.pop()
                    elif len(stack) >= 2 and stack[-1] == "*" and stack[-2] == "*":
                        out.append("]]")
                        stack.pop()
                        stack.pop()
                    else:
                        out.append("#strong[")
                        stack.append("**")
                    run = 0
                elif run == 1:
                    if stack and stack[-1] == "*":
                        out.append("]")
                        stack.pop()
                    else:
                        out.append("#emph[")
                        stack.append("*")
                    run = 0
        else:
            out.append(text[i])
            i += 1
    while stack:
        out.append("]")
        stack.pop()
    return "".join(out)


def render_paragraph_first(para: str) -> str:
    """Render opening paragraph of a chapter with classical small-caps lead-in."""
    para = " ".join(line.strip() for line in para.splitlines()).strip()
    words = para.split(" ")
    # Find clean split point near word 4 where markdown asterisks are balanced
    split_at = min(4, len(words))
    while split_at < len(words) and (" ".join(words[:split_at]).count("*") % 2 != 0):
        split_at += 1
    lead_raw = " ".join(words[:split_at]).replace("**", "").replace("*", "")
    rest_raw = " ".join(words[split_at:])
    lead_t = escape_typst_inline(lead_raw)
    rest_t = escape_typst_inline(rest_raw)
    if rest_t:
        return f"#par(first-line-indent: 0pt)[#smallcaps[{lead_t}] {rest_t}]"
    return f"#par(first-line-indent: 0pt)[#smallcaps[{lead_t}]]"


def render_chapter_typst(ch: dict) -> str:
    blocks = re.split(r"\n\s*\n", ch["prose"])
    out: list[str] = []
    num_rom = ROMAN[ch["num"]] if ch["num"] < len(ROMAN) else str(ch["num"])
    t_esc = escape_typst_inline(ch["title"])
    sub_line = ch["dateline"] or f"{ch['pov']}"
    sub_esc = escape_typst_inline(sub_line)

    out.append(f"""
#pagebreak(weak: true)
#v(0.82in)
#place(hide[#heading(level: 2, outlined: true)[{num_rom}. #h(0.35em) {t_esc}]])
#metadata("{t_esc}") <ch-running-title>
#align(center)[
  #text(size: 9.5pt, tracking: 2.2pt)[#smallcaps[Chapter {num_rom}]]
  #v(0.14in)
  #text(size: 18pt, style: "italic")[{t_esc}]
  #v(0.08in)
  #text(size: 9.5pt, style: "italic", fill: rgb("#444444"))[{sub_esc}]
  #v(0.32in)
]
""")

    is_chapter_first_para = True
    need_no_indent = True
    for raw_b in blocks:
        b = raw_b.strip()
        if not b:
            continue
        if re.match(r"^(\*\s*\*\s*\*|---|___+|❦)$", b):
            out.append("""
#v(0.18in)
#block(breakable: false)[
  #align(center)[#text(size: 10pt, tracking: 6pt, fill: rgb("#555555"))[\\* \\* \\*]]
]
#v(0.18in)
""")
            need_no_indent = True
            continue

        if "EXPLICIT LIBER PRIMVS" in b:
            out.append("""
#v(0.45in)
#align(center)[
  #text(size: 10.5pt, tracking: 2.6pt)[#smallcaps[Explicit Liber Primus]]
]
""")
            continue

        if is_chapter_first_para:
            out.append(render_paragraph_first(b))
            is_chapter_first_para = False
            need_no_indent = False
        elif need_no_indent:
            joined = " ".join(line.strip() for line in b.splitlines())
            out.append(f"#par(first-line-indent: 0pt)[{escape_typst_inline(joined)}]")
            need_no_indent = False
        else:
            joined = " ".join(line.strip() for line in b.splitlines())
            out.append(escape_typst_inline(joined))
            out.append("")

    out.append("")
    return "\n".join(out)


BODY_PAGE_SETUP = r"""
#set page(
  numbering: "1",
  header: context {
    let pg = here().page()
    let ch_starts = query(selector(heading.where(level: 2))).filter(h => h.location().page() == pg)
    let pt_starts = query(selector(heading.where(level: 1))).filter(h => h.location().page() == pg)
    if ch_starts.len() == 0 and pt_starts.len() == 0 {
      let disp_num = counter(page).get().first()
      if calc.even(disp_num) {
        align(left)[#text(size: 8.5pt, tracking: 1.5pt, fill: rgb("#555555"))[#smallcaps[By Bronze and Balance]]]
      } else {
        let prev = query(selector(<ch-running-title>).before(here()))
        if prev.len() > 0 {
          align(right)[#text(size: 9pt, style: "italic", fill: rgb("#555555"))[#prev.last().value]]
        }
      }
    }
  },
  footer: context {
    let pg = here().page()
    let pt_starts = query(selector(heading.where(level: 1))).filter(h => h.location().page() == pg)
    if pt_starts.len() == 0 {
      align(center)[#text(size: 9.5pt, fill: rgb("#444444"))[#counter(page).display("1")]]
    }
  }
)
"""


def build(output_pdf: Path) -> tuple[int, int]:
    ch_files = sorted((BOOK_DIR / "chapters").glob("ch_*.md"))
    if not ch_files:
        raise SystemExit("No chapters found in books/book-one/chapters/")
    chapters = [parse_chapter(p) for p in ch_files]
    total_words = sum(c["words"] for c in chapters)

    typst_parts: list[str] = [r"""
#set document(
  title: "By Bronze and Balance",
  author: "M. A. Severn",
)

#set page(
  width: 6in,
  height: 9in,
  margin: (inside: 0.9in, outside: 0.72in, top: 0.82in, bottom: 0.88in),
  numbering: none,
)

#set text(
  font: "EB Garamond",
  size: 11.2pt,
  lang: "en",
  number-type: "old-style",
  ligatures: true,
)

#set par(
  justify: true,
  leading: 0.66em,
  first-line-indent: 1.45em,
  spacing: 0.66em,
)

#show heading.where(level: 1): it => {
  set text(font: "EB Garamond", size: 21pt, weight: "regular", style: "italic")
  it.body
}

#show heading.where(level: 2): it => {
  set text(font: "EB Garamond", size: 17.5pt, weight: "regular", style: "italic")
  // Display only the chapter title on the chapter page itself (strip "I. " prefix used for TOC)
  it.body
}

#show outline.entry.where(level: 1): it => {
  v(0.14in, weak: true)
  strong(it)
}

// 1. Half-Title
#v(2.3in)
#align(center)[
  #text(size: 15pt, tracking: 2.5pt)[#smallcaps[By Bronze and Balance]]
  #v(0.18in)
  #text(size: 10pt, style: "italic", fill: rgb("#555555"))[The Ash and the Porphyry · Book One]
]

#pagebreak()

// 2. Series Verso
#v(2.6in)
#align(center)[
  #text(size: 9.5pt, tracking: 1.8pt)[#smallcaps[The Ash and the Porphyry]]
  #v(0.22in)
  #text(size: 10.5pt, style: "italic")[
    I. By Bronze and Balance (AD 156–161)\
    II. Two Suns in the West (AD 161–166)\
    III. The Auction of Trajan (AD 166–171)
  ]
]

#pagebreak()

// 3. Full Title Page
#v(1.45in)
#align(center)[
  #text(size: 10pt, tracking: 2.4pt, fill: rgb("#444444"))[#smallcaps[The Ash and the Porphyry · I]]
  #v(0.35in)
  #text(size: 27pt, tracking: 1.2pt)[#smallcaps[By Bronze and Balance]]
  #v(0.22in)
  #text(size: 12pt, style: "italic")[A Novel of Antonine Rome]
  #v(1.1in)
  #text(size: 13pt, tracking: 4pt)[— ✦ —]
  #v(1.1in)
  #text(size: 13pt, tracking: 2pt)[#smallcaps[M. A. Severn]]
  #v(1.65in)
  #text(size: 9pt, tracking: 1.8pt, fill: rgb("#555555"))[#smallcaps[Rome · Anno Domini CLVI–CLXI]]
]

#pagebreak()

// 4. Edition & Historical Note Verso
#v(4.1in)
#set par(first-line-indent: 0pt, spacing: 0.9em)
#text(size: 9pt, fill: rgb("#444444"))[
  #emph[By Bronze and Balance] opens on the Ides of October in the nineteenth year of the Emperor Titus Aelius Hadrianus Antoninus Augustus Pius (AD 156) and closes in the spring of AD 161.

  Sums of money are reckoned in Roman #emph[quadrantes], copper #emph[asses], brass #emph[sestertii] (four #emph[asses]), silver #emph[denarii] (four #emph[sestertii]), and gold #emph[aurei] (one hundred #emph[sestertii]). A day-laborer in the clay-yards earns three to four #emph[sestertii] a day; entry to the equestrian order requires a census of four hundred thousand; a seat in the Senate, one million.

  Set in EB Garamond on Royal Octavo pages.
]

#pagebreak()

// 5. Epigraph
#v(2.0in)
#pad(x: 0.55in)[
  #text(size: 10.5pt, style: "italic")[
    “Mancipatio is an imaginary sale, and is a right peculiar to Roman citizens. It is performed thus: in the presence of not fewer than five Roman citizens of full age as witnesses, and another of the same condition who holds a balance of bronze and is called the scale-holder, the taker holds the thing and says: #emph[I affirm that this man is mine by Quiritary right, and let him be bought to me with this bronze and this bronze balance]; and then he strikes the balance with the bronze...”
  ]
  #v(0.08in)
  #align(right)[#text(size: 9.5pt)[— #smallcaps[Gaius], #emph[Institutes], I.119]]
  #v(0.55in)
  #text(size: 10.5pt, style: "italic")[
    “Since there is no room in Rome for honest trades, nor any profit in sweat, let us leave our father’s country while grey hair is new...”
  ]
  #v(0.08in)
  #align(right)[#text(size: 9.5pt)[— #smallcaps[Juvenal], #emph[Satires], III]]
]

#pagebreak()

// 6. Persons at the Opening of the Chronicle (Spoiler-Free)
#v(0.35in)
#align(center)[
  #text(size: 13pt, tracking: 2pt)[#smallcaps[Persons at the Opening of the Chronicle]]
  #v(0.06in)
  #text(size: 9.5pt, style: "italic", fill: rgb("#555555"))[October, AD 156]
]
#v(0.22in)
#text(size: 9.6pt)[
  #smallcaps[At the Tiber Clay-Yards (#emph[Figlinae Subortanae])]\
  #strong[Lucius Cassius Corvus], aged fifteen, freeborn Roman citizen (#emph[ingenuus]) of the Crustumina tribe, son of a dead Sabine land-surveyor.\
  #strong[Lucida], aged fifteen, a Junian Latin (#emph[Latina Iuniana]), daughter of a deceased Tyrian freedwoman dyer.\
  #strong[Gaius Ummidius Scaeva], a former Praetorian soldier; chief bailiff and rent-enforcer.

  #v(0.13in)
  #smallcaps[In the Subura, Argiletum, and Trans-Tiberim]\
  #strong[Berenice] (called #emph[Beroe]), a Syrian cosmetic-chemist and midwife above the Argiletum fulleries.\
  #strong[Habinnas Barba], a Cappadocian freedman and master-baker (#emph[pistor]).\
  #strong[Sura], a mute Gallic stable and oven girl.

  #v(0.13in)
  #smallcaps[On the Caelian Hill, the Courts, and the Markets]\
  #strong[Publius Vedius Pollio], an equestrian financier, landlord, and syndicate contractor.\
  #strong[Quintus Servilius Priscus], a patrician consular senator.\
  #strong[Phileros], chief Greek archive-freedman (#emph[tabularius]) in the household of Priscus.\
  #strong[Aulus Volusenus Niger], nephew to Priscus; a young patrician student of advocacy.\
  #strong[Tullia Crispina], a wealthy equestrian widow with shipping interests at Ostia.\
  #strong[Marcus Cornelius Fronto], consular senator from Cirta and Rome's foremost master of Latin rhetoric.\
  #strong[Quintus Junius Rusticus], Stoic philosopher and senator.

  #v(0.13in)
  #smallcaps[The Imperial House]\
  #strong[Titus Aelius Hadrianus Antoninus Augustus Pius], Emperor of Rome, aged seventy.\
  #strong[Marcus Aurelius Caesar], his nephew, son-in-law, and working colleague, aged thirty-five.\
  #strong[Annia Galeria Faustina] (#emph[Faustina the Younger]), daughter of Antoninus and wife to Marcus Caesar.\
  #strong[Lucius Ceionius Commodus], younger adoptive son of Antoninus Pius, aged twenty-five.\
  #strong[Ceionia Fabia], elder sister to Lucius Commodus.
]

#pagebreak()

// 7. Contents
#v(0.35in)
#align(center)[
  #text(size: 13pt, tracking: 2pt)[#smallcaps[Contents]]
]
#v(0.2in)
#text(size: 9.8pt)[
  #outline(title: none, indent: 1.1em, depth: 2)
]

// Switch to numbered body pages
#pagebreak(to: "odd")
#counter(page).update(1)
#set par(first-line-indent: 1.45em, spacing: 0.66em)
""" + BODY_PAGE_SETUP]

    for ch in chapters:
        if ch["num"] in PARTS:
            p_num, p_title, p_dates = PARTS[ch["num"]]
            typst_parts.append(f"""
#pagebreak(to: "odd", weak: true)
#set page(header: none, footer: none)
#v(2.35in)
#align(center)[
  #text(size: 10pt, tracking: 2.8pt, fill: rgb("#444444"))[#smallcaps[{p_num}]]
  #v(0.25in)
  #heading(level: 1, outlined: true)[{escape_typst_inline(p_title)}]
  #v(0.18in)
  #text(size: 10pt, tracking: 1.2pt, fill: rgb("#555555"))[{escape_typst_inline(p_dates)}]
]
#pagebreak(to: "odd")
{BODY_PAGE_SETUP}
""")
        typst_parts.append(render_chapter_typst(ch))

    # Classical Colophon on closing page
    typst_parts.append(r"""
#pagebreak(to: "odd", weak: true)
#set page(header: none, footer: none)
#v(2.8in)
#align(center)[
  #text(size: 11pt, tracking: 3pt)[— ✦ —]
  #v(0.28in)
  #text(size: 10pt, style: "italic", fill: rgb("#444444"))[
    Here ends #strong[By Bronze and Balance],\
    the first volume of #emph[The Ash and the Porphyry].
  ]
  #v(0.22in)
  #text(size: 9.5pt, style: "italic", fill: rgb("#555555"))[
    The chronicle continues in Book Two:\
    #smallcaps[Two Suns in the West] (AD 161–166).
  ]
]
""")

    src_typ = BOOK_DIR / "typeset" / "manuscript.typ"
    src_typ.parent.mkdir(parents=True, exist_ok=True)
    src_typ.write_text("\n".join(typst_parts), encoding="utf-8")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf_bytes = typst.compile(str(src_typ), font_paths=[str(FONTS_DIR)])
    output_pdf.write_bytes(pdf_bytes)
    pages = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))
    return total_words, pages


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (BOOK_DIR / "typeset" / "By-Bronze-and-Balance.pdf")
    words, pages = build(out)
    print(f"Built {out} — {words:,} words across {pages} pages.")
