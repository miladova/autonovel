#!/usr/bin/env python3
"""Typeset the manuscript in novel/chapters/ as a print-ready PDF."""
import html
import re
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent
CHAPTERS = ROOT / "chapters"
OUT = ROOT / "output" / "Historical_Novel.pdf"

TITLE = "Every Favour a Debt"
SUBTITLE = "A Novel"

PAGE_W, PAGE_H = 6 * inch, 9 * inch
MARGIN_OUTER = 0.75 * inch
MARGIN_INNER = 0.85 * inch
MARGIN_TOP = 0.85 * inch
MARGIN_BOTTOM = 0.85 * inch

INK = HexColor("#1a1712")
RULE = HexColor("#8a7a5a")

NUMERALS = [
    "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen", "Twenty", "Twenty-One",
    "Twenty-Two", "Twenty-Three", "Twenty-Four", "Twenty-Five",
]


def styles():
    s = {}
    s["title"] = ParagraphStyle(
        "TitlePage", fontName="Times-Bold", fontSize=30, leading=36,
        alignment=TA_CENTER, textColor=INK, spaceAfter=14)
    s["subtitle"] = ParagraphStyle(
        "Subtitle", fontName="Times-Italic", fontSize=14, leading=18,
        alignment=TA_CENTER, textColor=INK)
    s["front_small"] = ParagraphStyle(
        "FrontSmall", fontName="Times-Roman", fontSize=8.5, leading=13,
        alignment=TA_LEFT, textColor=INK, spaceAfter=8)
    s["contents_head"] = ParagraphStyle(
        "ContentsHead", fontName="Times-Bold", fontSize=16, leading=20,
        alignment=TA_CENTER, textColor=INK, spaceAfter=18)
    s["chapter_number"] = ParagraphStyle(
        "ChapterNumber", fontName="Times-Roman", fontSize=10, leading=14,
        alignment=TA_CENTER, textColor=RULE, spaceBefore=36, spaceAfter=10)
    s["chapter_title"] = ParagraphStyle(
        "ChapterTitle", fontName="Times-Bold", fontSize=18, leading=22,
        alignment=TA_CENTER, textColor=INK, spaceAfter=6)
    s["body_first"] = ParagraphStyle(
        "BodyFirst", fontName="Times-Roman", fontSize=10.5, leading=15.5,
        alignment=TA_JUSTIFY, textColor=INK, spaceAfter=0, firstLineIndent=0)
    s["body"] = ParagraphStyle(
        "Body", fontName="Times-Roman", fontSize=10.5, leading=15.5,
        alignment=TA_JUSTIFY, textColor=INK, spaceAfter=0, firstLineIndent=14)
    s["scene"] = ParagraphStyle(
        "SceneBreak", fontName="Times-Roman", fontSize=10.5, leading=15.5,
        alignment=TA_CENTER, textColor=RULE, spaceBefore=10, spaceAfter=10)
    s["end"] = ParagraphStyle(
        "EndMark", fontName="Times-Italic", fontSize=11, leading=15,
        alignment=TA_CENTER, textColor=INK, spaceBefore=24)
    s["toc1"] = ParagraphStyle(
        "TOC1", fontName="Times-Roman", fontSize=10, leading=16,
        leftIndent=12, firstLineIndent=0, textColor=INK)
    return s


class NovelDoc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            if style == "ChapterTitle":
                text = flowable.getPlainText()
                key = f"ch-{abs(hash(text)) % 10**8}-{self.seq.nextf('chapter')}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, 0, False)
                self.notify("TOCEntry", (0, text, self.page, key))


def decorate(canvas, doc):
    canvas.saveState()
    page = doc.page
    # No running matter on title/copyright pages.
    if page >= 3:
        canvas.setFont("Times-Roman", 7.5)
        canvas.setFillColor(HexColor("#6b5f4a"))
        header = TITLE.upper()
        canvas.drawCentredString(PAGE_W / 2, PAGE_H - 0.55 * inch, header)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN_OUTER, PAGE_H - 0.62 * inch,
                    PAGE_W - MARGIN_OUTER, PAGE_H - 0.62 * inch)
        canvas.setFont("Times-Roman", 9)
        canvas.setFillColor(INK)
        canvas.drawCentredString(PAGE_W / 2, 0.5 * inch, str(page))
    canvas.restoreState()


def body_markup(text: str) -> str:
    text = html.escape(text.strip())
    # *italic* spans (used sparingly in the manuscript)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


def main():
    st = styles()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = NovelDoc(
        str(OUT), pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN_INNER, rightMargin=MARGIN_OUTER,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=TITLE, author="", subject="A novel",
        creator="typeset in-house", keywords="novel, historical fiction",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=decorate)])

    story = []

    # ---- Title page ----
    story.append(Spacer(1, 1.6 * inch))
    story.append(Paragraph(TITLE, st["title"]))
    story.append(Paragraph("· &nbsp; · &nbsp; ·", st["scene"]))
    story.append(Paragraph(SUBTITLE, st["subtitle"]))
    story.append(PageBreak())

    # ---- Copyright / notice page ----
    story.append(Spacer(1, 0.4 * inch))
    for line in [
        f"<b>{TITLE}</b>",
        "",
        "A work of fiction. Names, characters, places and incidents are "
        "products of the imagination or are used fictitiously. Any resemblance "
        "to actual persons, living or dead, is entirely coincidental.",
        "",
        "For adult readers.",
        "",
        "First edition.",
        "",
        "Typeset on a 6 × 9 inch page. Printed page numbers appear at the "
        "foot of each page from the contents onward.",
    ]:
        story.append(Paragraph(line if line else "&nbsp;", st["front_small"]))
    story.append(PageBreak())

    # ---- Contents ----
    story.append(Paragraph("Contents", st["contents_head"]))
    toc = TableOfContents()
    toc.levelStyles = [st["toc1"]]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(PageBreak())

    # ---- Chapters ----
    files = sorted(CHAPTERS.glob("ch*.txt"))
    total_words = 0
    for i, path in enumerate(files):
        raw = path.read_text(encoding="utf-8").strip()
        lines = raw.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        total_words += len(body.split())
        numeral = NUMERALS[i] if i < len(NUMERALS) else str(i + 1)

        story.append(Paragraph(f"Chapter {numeral}", st["chapter_number"]))
        story.append(Paragraph(html.escape(title), st["chapter_title"]))
        story.append(Paragraph("· &nbsp; · &nbsp; ·", st["scene"]))
        story.append(Spacer(1, 6))

        first = True
        for block in re.split(r"\n\s*\n", body):
            block = block.strip()
            if not block:
                continue
            if block == "§":
                story.append(Paragraph("⁂", st["scene"]))
                first = True
                continue
            # Collapse hard line wraps inside a paragraph.
            para = " ".join(line.strip() for line in block.splitlines())
            style = st["body_first"] if first else st["body"]
            story.append(Paragraph(body_markup(para), style))
            first = False

        if i != len(files) - 1:
            story.append(PageBreak())

    story.append(Spacer(1, 18))
    story.append(Paragraph("· &nbsp; · &nbsp; ·", st["scene"]))
    story.append(Paragraph("The End", st["end"]))

    doc.multiBuild(story)
    print(f"Wrote {OUT}  chapters={len(files)}  body_words={total_words}")


if __name__ == "__main__":
    main()
