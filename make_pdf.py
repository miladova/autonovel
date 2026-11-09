#!/usr/bin/env python3
"""Convert novella.md to a formatted PDF using reportlab."""

import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    PageBreak, NextPageTemplate, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas as pdfcanvas

# ---------------------------------------------------------------- colors
INK      = HexColor("#1a1a1a")
GOLD     = HexColor("#8a6d3b")      # house of Black-ish gold / warm tone
DARKGOLD = HexColor("#4a3720")
PAPER    = HexColor("#fafaf5")
LINE     = HexColor("#d4c7b4")

# ---------------------------------------------------------------- styles
def st(name, **kw):
    base = dict(
        fontName="Times-Roman", fontSize=11, leading=15,
        textColor=INK, alignment=TA_JUSTIFY, spaceAfter=8,
    )
    base.update(kw)
    return ParagraphStyle(name, **base)

S_TITLE    = st("title",  fontName="Times-Bold",  fontSize=26, leading=32,
                alignment=TA_CENTER, textColor=DARKGOLD, spaceAfter=16)
S_SUBTITLE = st("subtitle", fontName="Times-Italic", fontSize=14, leading=18,
                alignment=TA_CENTER, textColor=GOLD, spaceAfter=6)
S_AUTHOR   = st("author",   fontName="Times-Roman",  fontSize=12, leading=16,
                alignment=TA_CENTER, textColor=INK, spaceAfter=4)
S_NOTE     = st("note",     fontName="Times-Italic", fontSize=9,  leading=12,
                alignment=TA_CENTER, textColor=HexColor("#666666"), spaceBefore=10)
S_CHAPTER  = st("chapter",  fontName="Times-Bold",  fontSize=18, leading=22,
                alignment=TA_CENTER, textColor=DARKGOLD, spaceBefore=20, spaceAfter=10)
S_SCENE    = st("scene",    fontName="Times-Italic", fontSize=12, leading=16,
                alignment=TA_CENTER, textColor=GOLD, spaceBefore=14, spaceAfter=14)
S_BODY     = st("body")
S_BODY_FIRST = st("bodyFirst", spaceBefore=0)
S_EPILOGUE = st("epilogue", fontName="Times-Italic", fontSize=11, leading=15,
                alignment=TA_JUSTIFY, textColor=HexColor("#333333"))
S_AUTHOR_NOTE = st("authorNote", fontSize=9.5, leading=13, textColor=HexColor("#444444"))

# ---------------------------------------------------------------- inline markup
def inline(text):
    """Convert basic markdown inline markup to reportlab <b>/<i> tags."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text

# ---------------------------------------------------------------- parse markdown
with open("novella.md", "r", encoding="utf-8") as f:
    raw = f.read()

# Split into blocks by blank lines
raw_blocks = re.split(r"\n\s*\n", raw.strip())
blocks = []
for rb in raw_blocks:
    rb = rb.strip()
    if rb:
        blocks.append(rb)

# ---------------------------------------------------------------- page furniture
def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(0.9 * inch, 0.7 * inch, A4[0] - 0.9 * inch, 0.7 * inch)
    canvas.setFont("Times-Italic", 8.5)
    canvas.setFillColor(HexColor("#666666"))
    canvas.drawCentredString(A4[0] / 2.0, 0.5 * inch,
                             "Star and Moon  ·  Cassiopeia Black & Remus Lupin")
    canvas.drawRightString(A4[0] - 0.9 * inch, 0.35 * inch,
                           f"Page {doc.page}")
    canvas.restoreState()

def title_footer(canvas, doc):
    canvas.saveState()
    canvas.restoreState()

# ---------------------------------------------------------------- build story
story = []

# --- Title page ---
story.append(Spacer(1, 2.2 * inch))
story.append(Paragraph("Star and Moon", S_TITLE))
story.append(Paragraph("A Novella in Two Timelines", S_SUBTITLE))
story.append(Spacer(1, 0.25 * inch))
story.append(HRFlowable(width="55%", thickness=1, color=LINE,
                        hAlign="CENTER", spaceBefore=4, spaceAfter=16))
story.append(Paragraph("Set in the Harry Potter universe", S_SUBTITLE))
story.append(Spacer(1, 0.55 * inch))
story.append(Paragraph("Cassiopeia Black &times; Remus Lupin", S_AUTHOR))
story.append(Spacer(1, 0.15 * inch))
story.append(Paragraph("Marauders Era (1975&ndash;1981) &nbsp;&middot;&nbsp; "
                       "OG Timeline (1995&ndash;1998)", S_AUTHOR))
story.append(Spacer(1, 1.1 * inch))
story.append(HRFlowable(width="55%", thickness=1, color=LINE,
                        hAlign="CENTER", spaceBefore=4, spaceAfter=16))
story.append(Paragraph("The house of Black does not weep.<br/>The house of Black endures.", S_NOTE))
story.append(NextPageTemplate("body"))
story.append(PageBreak())

# --- Body content ---
first_body = True
for block in blocks:
    # Skip the author note block at the very end (we'll handle it separately)
    if block.startswith("**Author's Note:**"):
        continue

    # Horizontal rule separator
    if block.strip() == "---":
        story.append(HRFlowable(width="30%", thickness=0.8, color=LINE,
                                hAlign="CENTER", spaceBefore=6, spaceAfter=6))
        continue

    # Chapter heading: lines starting with ##
    if block.startswith("## "):
        title = inline(block[3:].strip())
        if " — " in title:
            chapter_part, subtitle = title.split(" — ", 1)
            story.append(Paragraph(chapter_part.strip(), S_CHAPTER))
            story.append(Paragraph(inline(subtitle.strip()), S_SCENE))
        else:
            story.append(Paragraph(title.strip(), S_CHAPTER))
        story.append(Spacer(1, 8))
        continue

    # Prologue / Epilogue headings
    if block.startswith("# Prologue"):
        story.append(Paragraph("Prologue", S_CHAPTER))
        story.append(Paragraph("Stardust and Ash", S_SCENE))
        story.append(Spacer(1, 8))
        continue
    if block.startswith("# Epilogue"):
        story.append(Paragraph("Epilogue", S_CHAPTER))
        story.append(Paragraph("The Stars Remain", S_SCENE))
        story.append(Spacer(1, 8))
        continue

    # Top-level # title (skip main title already on cover)
    if block.startswith("# ") and not block.startswith("# Prologue") and not block.startswith("# Epilogue"):
        continue

    # Author note section
    if block.startswith("**Author's Note:**"):
        story.append(PageBreak())
        story.append(Paragraph("Author's Note", S_CHAPTER))
        story.append(Spacer(1, 10))
        body_text = block.replace("**Author's Note:**", "", 1).strip()
        story.append(Paragraph(inline(body_text), S_AUTHOR_NOTE))
        continue

    # Regular body paragraph
    p_text = inline(block)
    style = S_BODY_FIRST if first_body else S_BODY
    first_body = False
    story.append(Paragraph(p_text, style))

# ---------------------------------------------------------------- document
doc = BaseDocTemplate(
    "Star_and_Moon_Novella.pdf",
    pagesize=A4,
    leftMargin=0.9 * inch, rightMargin=0.9 * inch,
    topMargin=0.85 * inch, bottomMargin=0.95 * inch,
    title="Star and Moon",
    author="Cassiopeia Black & Remus Lupin (fanfiction)",
    subject="Harry Potter novella — two timelines",
)

frame_title = Frame(0.9 * inch, 0.95 * inch, A4[0] - 1.8 * inch,
                    A4[1] - 1.8 * inch, id="title")
frame_body  = Frame(0.9 * inch, 0.95 * inch, A4[0] - 1.8 * inch,
                    A4[1] - 1.8 * inch, id="body")

doc.addPageTemplates([
    PageTemplate(id="title", frames=[frame_title], onPage=title_footer),
    PageTemplate(id="body",  frames=[frame_body],  onPage=footer),
])

doc.build(story)
print("PDF built: Star_and_Moon_Novella.pdf")
