#!/usr/bin/env python3
"""Build The Gilded Door manuscript into a formatted PDF (ReportLab Platypus)."""
import json
import os
import re
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak,
    KeepTogether, Flowable,
)
from reportlab.pdfgen import canvas as pdfcanvas


class ChapterMarker(Flowable):
    """Zero-height flowable that records the running head for its page."""
    def __init__(self, head):
        super().__init__()
        self.head = head
        self.width = 0
        self.height = 0

    def draw(self):
        self.canv.page_heads[self.canv.getPageNumber()] = self.head


class NumberedCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []
        self.page_heads = {}

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_furniture(total)
            super().showPage()
        super().save()

    def _draw_furniture(self, total):
        page = self.getPageNumber()
        if page <= 2:
            return
        self.saveState()
        head = self.page_heads.get(page, _BOOK_TITLE)
        self.setFont("Serif-Italic", 8.6)
        self.setFillColor(RULE)
        self.drawCentredString(PAGE_W / 2, PAGE_H - 0.5 * inch, head.upper())
        self.setStrokeColor(RULE)
        self.setLineWidth(0.4)
        self.line(MARGIN, PAGE_H - 0.58 * inch, PAGE_W - MARGIN, PAGE_H - 0.58 * inch)
        self.setFont("Serif", 9)
        self.drawCentredString(PAGE_W / 2, 0.48 * inch, str(page - 2))
        self.restoreState()


_BOOK_TITLE = "The Gilded Door"

BOOK_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BOOK_DIR, "fonts")
INK = HexColor("#1f1a17")
RULE = HexColor("#8a7a63")

pdfmetrics.registerFont(TTFont("Serif", f"{FONT_DIR}/DejaVuSerif.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Bold", f"{FONT_DIR}/DejaVuSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Italic", f"{FONT_DIR}/DejaVuSerif-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Serif-BoldItalic", f"{FONT_DIR}/DejaVuSerif-BoldItalic.ttf"))
pdfmetrics.registerFontFamily(
    "Serif", normal="Serif", bold="Serif-Bold",
    italic="Serif-Italic", boldItalic="Serif-BoldItalic",
)

PAGE_W, PAGE_H = (5.5 * inch, 8.5 * inch)
MARGIN = 0.78 * inch

styles = {
    "body": ParagraphStyle(
        "body", fontName="Serif", fontSize=10.6, leading=15.6,
        alignment=TA_JUSTIFY, textColor=INK, spaceAfter=0,
        firstLineIndent=15, allowWidows=0, allowOrphans=0,
    ),
    "bodyfirst": ParagraphStyle(
        "bodyfirst", parent=None, fontName="Serif", fontSize=10.6,
        leading=15.6, alignment=TA_JUSTIFY, textColor=INK,
        firstLineIndent=0, spaceAfter=0,
    ),
    "chapternum": ParagraphStyle(
        "chapternum", fontName="Serif", fontSize=12, leading=16,
        alignment=TA_CENTER, textColor=RULE, spaceBefore=24, spaceAfter=6,
        tracking=2,
    ),
    "chaptertitle": ParagraphStyle(
        "chaptertitle", fontName="Serif-Bold", fontSize=19, leading=24,
        alignment=TA_CENTER, textColor=INK, spaceAfter=26,
    ),
    "part": ParagraphStyle(
        "part", fontName="Serif", fontSize=15, leading=22,
        alignment=TA_CENTER, textColor=RULE, tracking=3,
    ),
    "parttitle": ParagraphStyle(
        "parttitle", fontName="Serif-Bold", fontSize=22, leading=28,
        alignment=TA_CENTER, textColor=INK,
    ),
    "scene": ParagraphStyle(
        "scene", fontName="Serif", fontSize=12, leading=18,
        alignment=TA_CENTER, textColor=RULE, spaceBefore=10, spaceAfter=10,
        firstLineIndent=0,
    ),
    "title": ParagraphStyle(
        "title", fontName="Serif-Bold", fontSize=30, leading=38,
        alignment=TA_CENTER, textColor=INK,
    ),
    "author": ParagraphStyle(
        "author", fontName="Serif-Italic", fontSize=16, leading=22,
        alignment=TA_CENTER, textColor=RULE,
    ),
    "tochead": ParagraphStyle(
        "tochead", fontName="Serif-Bold", fontSize=17, leading=22,
        alignment=TA_CENTER, textColor=INK, spaceAfter=18,
    ),
    "tocpart": ParagraphStyle(
        "tocpart", fontName="Serif-Bold", fontSize=10.5, leading=16,
        alignment=TA_CENTER, textColor=RULE, spaceBefore=10, spaceAfter=4,
        tracking=1.5,
    ),
    "tocchap": ParagraphStyle(
        "tocchap", fontName="Serif", fontSize=10.4, leading=15,
        alignment=TA_JUSTIFY, textColor=INK, firstLineIndent=0,
    ),
}


def inline(text):
    """Minimal markdown inline: _italic_ / *italic*, **bold**."""
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", text)
    return text


def page_decoration(canvas, doc):
    # Furniture is drawn by NumberedCanvas at save time, once every page's
    # running head is known.
    return


def part_page(story, name):
    story.append(Spacer(1, 2.5 * inch))
    story.append(Paragraph(name.split("—")[0].strip(), styles["part"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(name.split("—")[1].strip().upper() if "—" in name else "",
                           styles["parttitle"]))
    story.append(PageBreak())


def chapter_story(num, title, text, first_body=False):
    out = [
        ChapterMarker(f"{num.title()} · {_BOOK_TITLE}"),
        Spacer(1, 0.35 * inch),
        Paragraph(num.upper(), styles["chapternum"]),
        Paragraph(title, styles["chaptertitle"]),
    ]
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    body_open = True
    for p in paras:
        if re.fullmatch(r"[*•·\s⁂]+", p.strip()) or p.strip() in ("***", "---"):
            out.append(Paragraph("⁂", styles["scene"]))
            body_open = True
            continue
        if p.startswith("#"):  # skip embedded headings
            continue
        style = styles["bodyfirst"] if body_open else styles["body"]
        out.append(Paragraph(inline(p), style))
        body_open = False
    out.append(PageBreak())
    return out


def build():
    with open(os.path.join(BOOK_DIR, "book.json"), encoding="utf-8") as f:
        book = json.load(f)

    out_pdf = os.path.join(BOOK_DIR, "output", "TheGildedDoor.pdf")
    doc = BaseDocTemplate(
        out_pdf, pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.85 * inch, bottomMargin=0.75 * inch,
        title=book["title"], author=book["author"],
    )
    frame = Frame(MARGIN, 0.7 * inch, PAGE_W - 2 * MARGIN,
                  PAGE_H - 1.55 * inch, id="main")
    doc.addPageTemplates([PageTemplate(id="book", frames=frame,
                                       onPage=page_decoration)])
    global _BOOK_TITLE
    _BOOK_TITLE = book["title"]

    story = []
    # Half title
    story.append(Spacer(1, 2.6 * inch))
    story.append(Paragraph(book["title"].upper(), styles["title"]))
    story.append(PageBreak())
    # Title page
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph(book["title"], styles["title"]))
    story.append(Spacer(1, 0.45 * inch))
    story.append(Paragraph(book["author"], styles["author"]))
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph("R O M E &nbsp; · &nbsp; A . D . &nbsp; 1 1 2",
                           styles["part"]))
    story.append(PageBreak())
    # Contents
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph("CONTENTS", styles["tochead"]))
    for part in book["parts"]:
        story.append(Paragraph(part["name"], styles["tocpart"]))
        for ch in part["chapters"]:
            line = f"{ch['num'].title()} &nbsp;<i>{ch['title']}</i>"
            story.append(Paragraph(line, styles["tocchap"]))
    story.append(PageBreak())

    total_words = 0
    for part in book["parts"]:
        part_page(story, part["name"])
        for ch in part["chapters"]:
            path = os.path.join(BOOK_DIR, "manuscript", ch["file"])
            if not os.path.exists(path):
                placeholder = (
                    f"_Manuscript for {ch['num']} — {ch['title']} "
                    f"is being written._"
                )
                text = placeholder
            else:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                # strip a leading markdown H1 line if present
                text = re.sub(r"^\s*#.*\n", "", text, count=1)
            total_words += len(re.findall(r"\b[\w’'-]+\b", text))
            story.extend(chapter_story(ch["num"], ch["title"], text))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Built {out_pdf}")
    print(f"Approx manuscript word count: {total_words:,}")


if __name__ == "__main__":
    build()
