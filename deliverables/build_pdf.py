from __future__ import annotations

from pathlib import Path
import html
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parent
CHAPTERS = ROOT / "chapters"
PDF_PATH = ROOT / "novel.pdf"
BOOK_TITLE = "ASHES BENEATH THE SILK"
AUTHOR = "A. M. Vesper"

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
REGULAR = FONT_DIR / "DejaVuSerif.ttf"
ITALIC = FONT_DIR / "DejaVuSerif-Italic.ttf"
BOLD = FONT_DIR / "DejaVuSerif-Bold.ttf"
BOLDITALIC = FONT_DIR / "DejaVuSerif-BoldItalic.ttf"
if not ITALIC.exists():
    ITALIC = REGULAR
if not BOLDITALIC.exists():
    BOLDITALIC = BOLD

if REGULAR.exists():
    pdfmetrics.registerFont(TTFont("NovelSerif", str(REGULAR)))
    pdfmetrics.registerFont(TTFont("NovelSerif-Italic", str(ITALIC)))
    pdfmetrics.registerFont(TTFont("NovelSerif-Bold", str(BOLD)))
    pdfmetrics.registerFont(TTFont("NovelSerif-BoldItalic", str(BOLDITALIC)))
    BODY_FONT = "NovelSerif"
    ITALIC_FONT = "NovelSerif-Italic"
    BOLD_FONT = "NovelSerif-Bold"
else:
    BODY_FONT = "Times-Roman"
    ITALIC_FONT = "Times-Italic"
    BOLD_FONT = "Times-Bold"

PAGE_W, PAGE_H = 5.5 * inch, 8.5 * inch
LEFT = 0.82 * inch
RIGHT = 0.66 * inch
TOP = 0.76 * inch
BOTTOM = 0.74 * inch
FRAME_W = PAGE_W - LEFT - RIGHT
FRAME_H = PAGE_H - TOP - BOTTOM


def parse_chapter(path: Path) -> tuple[str, str, str, list[str]]:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    if text.startswith("---"):
        pieces = text.split("---", 2)
        if len(pieces) == 3:
            for line in pieces[1].strip().splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip().strip('"').strip("'")
            text = pieces[2]
    paragraphs = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("# "):
            continue
        if block == "---":
            paragraphs.append("◆   ◆   ◆")
            continue
        paragraphs.append(block)
    title = meta.get("title", path.stem.replace("_", " ").title())
    dateline = meta.get("dateline", "")
    location = meta.get("location", "")
    return title, dateline, location, paragraphs


def inline_markup(raw: str) -> str:
    s = html.escape(raw, quote=False)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
    s = s.replace("\n", "<br/>")
    return s


class NovelDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(LEFT, BOTTOM, FRAME_W, FRAME_H, id="novel-frame", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="novel", frames=[frame], onPage=draw_page)])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and getattr(flowable.style, "name", "") == "ChapterTitle":
            text = flowable.getPlainText()
            key = "chapter-" + re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=0, closed=False)
            self.notify("TOCEntry", (0, text, self.page))


def draw_page(canvas: Canvas, doc: NovelDocTemplate):
    page = canvas.getPageNumber()
    if page <= 3:
        return
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#62574d"))
    canvas.setFont(BODY_FONT, 7.2)
    y = PAGE_H - 0.43 * inch
    if page % 2 == 0:
        canvas.drawString(LEFT, y, BOOK_TITLE.title())
    else:
        canvas.drawRightString(PAGE_W - RIGHT, y, "A NOVEL")
    canvas.setStrokeColor(colors.HexColor("#c8beb2"))
    canvas.setLineWidth(0.35)
    canvas.line(LEFT, y - 0.10 * inch, PAGE_W - RIGHT, y - 0.10 * inch)
    canvas.setFont(BODY_FONT, 8)
    canvas.setFillColor(colors.HexColor("#403a35"))
    canvas.drawCentredString(PAGE_W / 2, 0.38 * inch, str(page))
    canvas.restoreState()


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="BodyNovel",
    fontName=BODY_FONT,
    fontSize=10.15,
    leading=14.3,
    alignment=TA_JUSTIFY,
    firstLineIndent=15,
    spaceAfter=6.2,
    textColor=colors.HexColor("#24211e"),
    splitLongWords=1,
))
styles.add(ParagraphStyle(
    name="Dialogue",
    parent=styles["BodyNovel"],
    firstLineIndent=0,
    leftIndent=10,
    rightIndent=6,
    fontName=BODY_FONT,
))
styles.add(ParagraphStyle(
    name="SceneBreak",
    parent=styles["BodyNovel"],
    alignment=TA_CENTER,
    firstLineIndent=0,
    fontSize=8.7,
    leading=15,
    textColor=colors.HexColor("#827466"),
    spaceBefore=6,
    spaceAfter=8,
))
styles.add(ParagraphStyle(
    name="ChapterTitle",
    fontName=ITALIC_FONT,
    fontSize=19,
    leading=24,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#2d2824"),
    spaceAfter=7,
    keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="ChapterNumber",
    fontName=BODY_FONT,
    fontSize=8.4,
    leading=12,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#76695d"),
    spaceAfter=4,
    keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="Dateline",
    fontName=ITALIC_FONT,
    fontSize=8.9,
    leading=12,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#76695d"),
    spaceAfter=3,
    keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="ContentsTitle",
    fontName=BOLD_FONT,
    fontSize=20,
    leading=26,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#2d2824"),
    spaceAfter=24,
))
styles.add(ParagraphStyle(
    name="ContentsEntry",
    fontName=BODY_FONT,
    fontSize=9.3,
    leading=14,
    leftIndent=5,
    rightIndent=5,
))
styles.add(ParagraphStyle(
    name="FrontMatter",
    fontName=BODY_FONT,
    fontSize=9.3,
    leading=13.4,
    alignment=TA_JUSTIFY,
    textColor=colors.HexColor("#38312c"),
))
styles.add(ParagraphStyle(
    name="TitleMain",
    fontName=BOLD_FONT,
    fontSize=27,
    leading=33,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#211d1a"),
    spaceAfter=13,
))
styles.add(ParagraphStyle(
    name="TitleSub",
    fontName=ITALIC_FONT,
    fontSize=11.5,
    leading=17,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#655a50"),
))
styles.add(ParagraphStyle(
    name="Colophon",
    fontName=BODY_FONT,
    fontSize=8,
    leading=12,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#71665b"),
))


def roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for value, symbol in vals:
        while n >= value:
            out += symbol
            n -= value
    return out


def build() -> None:
    chapter_paths = sorted(CHAPTERS.glob("ch_*.md"))
    epilogue_path = CHAPTERS / "epilogue.md"
    entries = [(p, i) for i, p in enumerate(chapter_paths, start=1)]
    if epilogue_path.exists():
        entries.append((epilogue_path, None))

    doc = NovelDocTemplate(
        str(PDF_PATH),
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=LEFT,
        rightMargin=RIGHT,
        topMargin=TOP,
        bottomMargin=BOTTOM,
        title=BOOK_TITLE,
        author=AUTHOR,
        subject="Historical fiction",
        creator="Arena.ai Agent Mode",
    )

    story = []
    # Title leaf
    story.extend([
        Spacer(1, 1.05 * inch),
        Paragraph(BOOK_TITLE, styles["TitleMain"]),
        Spacer(1, 0.08 * inch),
        HRFlowable(width="34%", thickness=0.7, color=colors.HexColor("#887a6d"), hAlign="CENTER"),
        Spacer(1, 0.15 * inch),
        Paragraph("A historical novel", styles["TitleSub"]),
        Spacer(1, 1.05 * inch),
        Paragraph(AUTHOR, ParagraphStyle("TitleAuthor", parent=styles["TitleSub"], fontName=BOLD_FONT, fontSize=11.5, textColor=colors.HexColor("#302a25"))),
        Spacer(1, 1.25 * inch),
        Paragraph("Mature / 18+", ParagraphStyle("Rating", parent=styles["TitleSub"], fontSize=8.2, textColor=colors.HexColor("#8b7d70"))),
        PageBreak(),
        Spacer(1, 0.8 * inch),
        Paragraph("ASHES BENEATH THE SILK", styles["ContentsTitle"]),
        Paragraph("Contents", ParagraphStyle("ContentsLabel", parent=styles["TitleSub"], fontName=BOLD_FONT, fontSize=10, textColor=colors.HexColor("#75695e"))),
        Spacer(1, 0.22 * inch),
    ])
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle(name="TOCLevel0", fontName=BODY_FONT, fontSize=9.2, leading=15, leftIndent=4, firstLineIndent=0, rightIndent=4, textColor=colors.HexColor("#302a25"))]
    story.append(toc)
    story.append(PageBreak())

    # Copyright / historical fiction note on its own leaf.
    story.extend([
        Spacer(1, 1.15 * inch),
        Paragraph("ASHES BENEATH THE SILK", ParagraphStyle("CopyrightTitle", parent=styles["TitleSub"], fontName=BOLD_FONT, fontSize=12, textColor=colors.HexColor("#332d28"))),
        Spacer(1, 0.4 * inch),
        Paragraph("Copyright © 2026 A. M. Vesper", styles["Colophon"]),
        Spacer(1, 0.18 * inch),
        Paragraph("This is a work of historical fiction. The principal characters are invented; the novel places them against real places, dates, and conditions of the Second World War.", styles["FrontMatter"]),
        Spacer(1, 0.25 * inch),
        Paragraph("No part of this work may be reproduced or transmitted in any form without permission of the copyright holder, except for brief quotations in reviews.", styles["FrontMatter"]),
        Spacer(1, 1.0 * inch),
        Paragraph("For the names that were carried out of the fire.", ParagraphStyle("Dedication", parent=styles["TitleSub"], fontSize=10.5)),
        PageBreak(),
    ])

    for path, number in entries:
        title, dateline, location, paragraphs = parse_chapter(path)
        if number is None:
            number_label = "EPILOGUE"
        else:
            number_label = f"CHAPTER {roman(number)}"
        story.append(Spacer(1, 0.34 * inch))
        story.append(Paragraph(number_label, styles["ChapterNumber"]))
        story.append(Paragraph(title, styles["ChapterTitle"]))
        if dateline or location:
            line = dateline
            if location:
                line += ("  ·  " if line else "") + location
            story.append(Paragraph(inline_markup(line), styles["Dateline"]))
        story.append(Paragraph("◆   ◇   ◆", styles["SceneBreak"]))
        for idx, paragraph in enumerate(paragraphs):
            if paragraph == "◆   ◆   ◆":
                story.append(Paragraph("◆   ◆   ◆", styles["SceneBreak"]))
                continue
            style = styles["BodyNovel"]
            if paragraph.startswith("“") or paragraph.startswith('"'):
                style = styles["Dialogue"]
            story.append(Paragraph(inline_markup(paragraph), style))
        if path != entries[-1][0]:
            story.append(PageBreak())

    story.append(Spacer(1, 0.4 * inch))
    story.append(HRFlowable(width="25%", thickness=0.5, color=colors.HexColor("#887a6d"), hAlign="CENTER"))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph("THE END", ParagraphStyle("End", parent=styles["Colophon"], fontName=BOLD_FONT, fontSize=8.5)))

    doc.multiBuild(story)
    print(f"wrote {PDF_PATH} ({PDF_PATH.stat().st_size:,} bytes)")

if __name__ == "__main__":
    build()
