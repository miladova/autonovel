#!/usr/bin/env python3
"""Typeset manuscript/BOOK.md to a print-ready A5 PDF.

Pure reportlab; no LaTeX or pandoc needed. Output:
manuscript/The-Water-Between.pdf
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer)

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "BOOK.md"
OUT = ROOT / "The-Water-Between.pdf"

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
INK = HexColor("#1a1a1a")
FAINT = HexColor("#8a8a8a")

PDF_W, PDF_H = A5
MARGIN_IN = 20 * mm
MARGIN_OUT = 17 * mm
MARGIN_TOP = 20 * mm
MARGIN_BOT = 22 * mm


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "DejaVuSerif.ttf")))
    pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "DejaVuSerif-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Body-Italic", str(FONT_DIR / "DejaVuSerif.ttf")))
    # DejaVu ships no serif italic; synthesise the slant with the italic family below.
    pdfmetrics.registerFontFamily(
        "Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-Bold"
    )


LIGATURES = {
    "\u2014": "\u2014",   # em dash
    "\u2013": "\u2013",
}


def esc(text: str) -> str:
    """Escape for reportlab paragraphs, keeping markdown emphasis."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text


def inline(text: str) -> str:
    """Convert the little inline markdown the manuscript uses to RML tags."""
    text = esc(text)
    # bold first, then italic (no nesting in the source beyond these)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    return text


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


# ---------------------------------------------------------------- page furniture

def make_styles():
    body = ParagraphStyle(
        "body",
        fontName="Body",
        fontSize=9.6,
        leading=14.2,
        textColor=INK,
        alignment=TA_JUSTIFY,
        firstLineIndent=4.6 * mm,
        spaceBefore=0,
        spaceAfter=0,
        hyphenationLang="",
        embeddedHyphenation=0,
        allowWidows=1,
        allowOrphans=1,
    )
    body_first = ParagraphStyle("body_first", parent=body, firstLineIndent=0)
    body_noindent = ParagraphStyle("body_noindent", parent=body, firstLineIndent=0)
    style_d = ParagraphStyle(
        "display",
        fontName="Body",
        fontSize=17,
        leading=22,
        textColor=INK,
        alignment=TA_CENTER,
        spaceBefore=0,
        spaceAfter=6 * mm,
    )
    chap_head = ParagraphStyle(
        "chap",
        fontName="Body",
        fontSize=12.5,
        leading=16,
        textColor=INK,
        alignment=TA_CENTER,
        spaceBefore=0,
        spaceAfter=2 * mm,
    )
    dateline = ParagraphStyle(
        "dateline",
        fontName="Body",
        fontSize=8.4,
        leading=12,
        textColor=FAINT,
        alignment=TA_CENTER,
        spaceAfter=9 * mm,
    )
    title = ParagraphStyle(
        "title",
        fontName="Body-Bold" if False else "Body",
        fontSize=26,
        leading=31,
        textColor=INK,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    subtitle = ParagraphStyle(
        "subtitle",
        fontName="Body",
        fontSize=11,
        leading=16,
        textColor=INK,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    epigraph = ParagraphStyle(
        "epigraph",
        fontName="Body",
        fontSize=9.2,
        leading=14,
        textColor=INK,
        alignment=TA_CENTER,
        leftIndent=12 * mm,
        rightIndent=12 * mm,
        spaceAfter=3 * mm,
    )
    epigraph_src = ParagraphStyle(
        "epigraph_src", parent=epigraph, fontSize=8.2, textColor=FAINT
    )
    contents = ParagraphStyle(
        "contents",
        fontName="Body",
        fontSize=10.2,
        leading=17,
        textColor=INK,
        alignment=TA_LEFT,
        leftIndent=18 * mm,
        spaceAfter=0,
    )
    section = ParagraphStyle(
        "section",
        fontName="Body",
        fontSize=8.2,
        leading=13,
        textColor=FAINT,
        alignment=TA_CENTER,
        spaceBefore=8 * mm,
        spaceAfter=8 * mm,
    )
    return dict(
        body=body,
        body_first=body_first,
        body_noindent=body_noindent,
        display=style_d,
        chap_head=chap_head,
        dateline=dateline,
        title=title,
        subtitle=subtitle,
        epigraph=epigraph,
        epigraph_src=epigraph_src,
        contents=contents,
        section=section,
    )


def draw_frame(canv, doc, rect_style):
    """Running head + folio."""
    page = canv.getPageNumber()
    if page <= doc.front_matter_pages:
        return
    canv.saveState()
    canv.setFont("Body", 7.6)
    canv.setFillColor(FAINT)
    y = PDF_H - MARGIN_TOP + 8 * mm
    canv.drawCentredString(PDF_W / 2, y, "THE WATER BETWEEN")
    canv.setFont("Body", 8.4)
    canv.drawCentredString(PDF_W / 2, MARGIN_BOT - 9 * mm, str(page - doc.front_matter_pages))
    canv.restoreState()


def build_story(styles):
    raw = SRC.read_text(encoding="utf-8")
    lines = raw.split("\n")
    story = []
    front_pages_marker = {"n": 0}

    # ---------------- front matter
    story.append(Spacer(1, 34 * mm))
    story.append(Paragraph("THE WATER BETWEEN", styles["title"]))
    story.append(Paragraph("A Novella of the <i>Titanic</i>", styles["subtitle"]))
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph(
        "&ldquo;They that go down to the sea in ships, that do business in great waters; "
        "these see the works of the Lord, and his wonders in the deep.&rdquo;",
        styles["epigraph"]))
    story.append(Paragraph("PSALM 107", styles["epigraph_src"]))
    story.append(PageBreak())

    # contents (collected as we go; approximated by scanning headings)
    chapter_titles = [ln.lstrip("# ").strip() for ln in lines if ln.startswith("# ")]
    chapter_titles = [t for t in chapter_titles if t != "The Water Between"]
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("CONTENTS", styles["epigraph_src"]))
    story.append(Spacer(1, 8 * mm))
    for t in chapter_titles:
        story.append(Paragraph(inline(t), styles["contents"]))
    story.append(NextPageTemplate("running"))
    story.append(PageBreak())
    story.append(_Marker(front_pages_marker))

    # ---------------- body
    i = 0
    current_chapter = None
    first_para_of_scene = True
    chapter_head = None
    chapter_date = None
    in_front = True

    # We parse the markdown file directly so we can honour # headings and --- scene breaks.
    pending_chapter: list[tuple[str, str]] = []

    def flush_chapter():
        nonlocal first_para_of_scene, chapter_head, chapter_date
        if chapter_head is None:
            return
        blk = [Spacer(1, 6 * mm),
               Paragraph(inline(chapter_head), styles["chap_head"])]
        if chapter_date:
            blk.append(Paragraph(inline(chapter_date), styles["dateline"]))
        else:
            blk.append(Spacer(1, 9 * mm))
        story.extend(blk)
        for kind, text in pending_chapter:
            if kind == "p":
                st = styles["body_first"] if first_para_of_scene else styles["body"]
                story.append(Paragraph(inline(text), st))
            elif kind == "br":
                story.append(Paragraph("* * *", styles["section"]))
                first_para_of_scene = True
        pending_chapter.clear()

    # First pass: split into chapters by '# ' headings at top level
    body_lines = []
    started = False
    for ln in lines:
        if ln.startswith("# ") and ln.lstrip("# ").strip() != "The Water Between":
            started = True
        if started:
            body_lines.append(ln)

    chapter_blocks: list[tuple[str, list[str]]] = []
    for ln in body_lines:
        if ln.startswith("# "):
            chapter_blocks.append((ln.lstrip("# ").strip(), []))
        elif chapter_blocks:
            chapter_blocks[-1][1].append(ln)

    for idx, (title, body) in enumerate(chapter_blocks):
        paras: list[tuple[str, str]] = []
        buf: list[str] = []
        for ln in body:
            stripped = ln.strip()
            if not stripped:
                if buf:
                    paras.append(("p", " ".join(buf)))
                    buf = []
                continue
            if stripped == "---":
                if buf:
                    paras.append(("p", " ".join(buf)))
                    buf = []
                paras.append(("br", ""))
                continue
            buf.append(stripped)
        if buf:
            paras.append(("p", " ".join(buf)))

        # strip leading/trailing scene rules
        while paras and paras[0][0] == "br":
            paras.pop(0)
        while paras and paras[-1][0] == "br":
            paras.pop()

        # first paragraph may be a dateline-ish note? use frontmatter dateline instead
        date = chapter_dates.get(title, "")

        if idx > 0:
            story.append(PageBreak())
        chapter_head, chapter_date = title, date
        first_para_of_scene = True
        story.append(Spacer(1, 14 * mm))
        story.append(Paragraph(inline(title), styles["chap_head"]))
        if date:
            story.append(Paragraph(esc(date), styles["dateline"]))
        else:
            story.append(Spacer(1, 9 * mm))
        for kind, text in paras:
            if kind == "p":
                st = styles["body_first"] if first_para_of_scene else styles["body"]
                story.append(Paragraph(inline(text), st))
                first_para_of_scene = False
            else:
                story.append(Paragraph("* * *", styles["section"]))
                first_para_of_scene = True

    # ---------------- note on the book
    if note_text:
        story.append(PageBreak())
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("A NOTE ON THE BOOK", styles["chap_head"]))
        story.append(Spacer(1, 6 * mm))
        for p in note_text:
            story.append(Paragraph(inline(p), styles["body_noindent"]))
            story.append(Spacer(1, 3 * mm))

    return story, front_pages_marker


class _Marker(Spacer):
    """Zero-height spacer used to switch page templates."""

    def __init__(self, box):
        super().__init__(0, 0)
        self.box = box


# chapter datelines, keyed by heading (kept in sync with the chapter frontmatter)
chapter_dates = {
    "I. The Ocean Greyhound": "At sea, Friday 12 April 1912",
    "II. Dead Reckoning": "Southampton and at sea, 10\u201312 April 1912",
    "III. Saturday": "At sea, Saturday 13 April 1912",
    "IV. The Flat Calm": "At sea, Sunday 14 April 1912",
    "V. The Ship That Could Not Sink": "At sea, Sunday 14 April 1912",
    "VI. The Work": "At sea, the night of 14\u201315 April 1912",
    "VII. The Cries": "At sea, the morning of 15 April 1912",
    "VIII. The Count": "Carpathia, 15\u201316 April 1912",
    "IX. The Pier": "New York, 18 April \u2013 1 May 1912",
    "X. Calon L\u00e2n": "Barmouth, 4\u20136 June 1912",
}

note_text: list[str] = []


def load_note(raw: str) -> None:
    m = re.search(r"## A Note on the Book\s*(.+)\Z", raw, re.S)
    if not m:
        return
    for para in re.split(r"\n\s*\n", m.group(1).strip()):
        if para.strip():
            note_text.append(" ".join(para.split()))


class Book(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, pagesize=A5, **kw)
        self.front_matter_pages = 0
        frame_front = Frame(MARGIN_IN, MARGIN_BOT, PDF_W - MARGIN_IN - MARGIN_OUT,
                            PDF_H - MARGIN_TOP - MARGIN_BOT, id="front",
                            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        frame_body = Frame(MARGIN_OUT, MARGIN_BOT, PDF_W - 2 * MARGIN_OUT,
                           PDF_H - MARGIN_TOP - MARGIN_BOT, id="body",
                           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="front", frames=[frame_front], onPage=self._plain,
                         autoNextPageTemplate="front"),
            PageTemplate(id="running", frames=[frame_body], onPage=self._running,
                         autoNextPageTemplate="running"),
        ])

    def _plain(self, canv, doc):
        pass

    def _running(self, canv, doc):
        page = canv.getPageNumber()
        canv.saveState()
        canv.setFont("Body", 7.4)
        canv.setFillColor(FAINT)
        canv.drawCentredString(PDF_W / 2, PDF_H - MARGIN_TOP + 9 * mm, "THE WATER BETWEEN")
        canv.setFont("Body", 8.2)
        canv.drawCentredString(PDF_W / 2, MARGIN_BOT - 10 * mm, str(page - 2))
        canv.restoreState()

    def afterFlowable(self, flowable):
        pass


def main() -> None:
    register_fonts()
    raw = SRC.read_text(encoding="utf-8")
    load_note(raw)
    styles = make_styles()
    story, _ = build_story(styles)
    doc = Book(str(OUT), title="The Water Between",
               author="A. M.", subject="A Novella of the Titanic")
    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
