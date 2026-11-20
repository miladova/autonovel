#!/usr/bin/env python3
"""Typeset `the-tuning.md` as a 6x9 short-story booklet (PDF).

Design notes
------------
* Trim 6 x 9 in, symmetric 0.80 in margins, justified text with pyphen
  hyphenation for long words only (>5 letters, so "piano" is never broken
  as "Pi-ano").
* Crimson Text (SIL OFL, vendored in ./fonts) for every text role: an
  old-style serif that holds the Polish and German diacritics and reads
  well at 11.4 / 16.1.
* Opening drop cap, set as a fitted table rather than an inline 30 pt font.
  An inline size change makes ReportLab advance the first line by more than
  the style's leading while still reporting the old height, so the next
  paragraph rides up into the text. The table version keeps the metrics
  honest: the versal is drawn as a glyph, and the words beside it are found
  by wrapping, not by hand.
* Three-dot ornament for scene breaks; running heads; folio numbering from
  1 on the first story page, suppressed on it.
* Front matter: title page, colophon. Back matter: notes on the German and
  Polish so a reader can get the plain sense of a line without leaving the
  booklet.

Usage:  python build_pdf.py [-o out.pdf]
"""
from __future__ import annotations

import argparse
import pathlib
import re

from reportlab import rl_config
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

HERE = pathlib.Path(__file__).resolve().parent
FONTS = HERE / "fonts"
SOURCE = HERE / "the-tuning.md"
DEFAULT_OUT = HERE / "the-tuning.pdf"

PAGE_W, PAGE_H = 6 * inch, 9 * inch
M_TOP, M_BOTTOM, M_SIDE = 0.82 * inch, 0.86 * inch, 0.80 * inch
TEXT_W = PAGE_W - 2 * M_SIDE
TEXT_H = PAGE_H - M_TOP - M_BOTTOM

PAPER = (0.993, 0.988, 0.978)
INK = (0.09, 0.08, 0.075)
INK_SOFT = (0.42, 0.40, 0.37)
HAIRLINE = (0.79, 0.77, 0.73)

BODY_SIZE, BODY_LEAD = 11.4, 16.1
HYPH = "en_GB"


# --------------------------------------------------------------------------
# fonts
# --------------------------------------------------------------------------
def register_fonts() -> None:
    for name, file in {
        "Crimson": "CrimsonText-Regular.ttf",
        "Crimson-Italic": "CrimsonText-Italic.ttf",
        "Crimson-Bold": "CrimsonText-Bold.ttf",
        "Crimson-BoldItalic": "CrimsonText-BoldItalic.ttf",
        "Crimson-Semi": "CrimsonText-SemiBold.ttf",
    }.items():
        pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
    pdfmetrics.registerFontFamily(
        "Crimson",
        normal="Crimson",
        bold="Crimson-Bold",
        italic="Crimson-Italic",
        boldItalic="Crimson-BoldItalic",
    )


# --------------------------------------------------------------------------
# text preparation
# --------------------------------------------------------------------------
def smart_quotes(s: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(s):
        prev = s[i - 1] if i else ""
        if ch == '"':
            opening = prev == "" or prev.isspace() or prev in "([{\u2014\u2013"
            out.append("\u201c" if opening else "\u201d")
        elif ch == "'":
            out.append("\u2019")           # the text has apostrophes only
        elif ch == "-" and prev.isalpha() and i + 1 < len(s) and s[i + 1].isalpha():
            out.append("\u2010")
        else:
            out.append(ch)
    return "".join(out)


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


GLOSS_SIZE = 8.9
GLOSS_HEX = "#%02x%02x%02x" % tuple(round(c * 255) for c in INK_SOFT)


def body_html(raw: str) -> str:
    """Escape, curl the quotes, italics from *emphasis*, and `[[English]]` into
    a bracketed translation in the same small grey italic the gloss lines use."""
    s = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", escape(smart_quotes(raw)))

    def bracket(m: re.Match) -> str:
        english = m.group(1)
        # A short translation is set unbreakable, so it hangs together and
        # moves as a unit rather than splitting after "(How" and finishing on
        # the next line. A long one has to be allowed to break.
        body = english.replace(" ", "\u00a0") if len(english) <= 34 else english
        return (f' (<i><font size="{GLOSS_SIZE}" color="{GLOSS_HEX}">'
                f"{body}</font></i>)")

    return re.sub(r"\[\[(.+?)\]\]", bracket, s)


def tracked_width(text: str, font: str, size: float, tracking: float,
                  word_gap: float) -> float:
    """Width of a hand-tracked line.

    Crimson Text has no thin space (U+2009), so stringWidth returns zero
    advance for it and both letterspacing and kerning-by-space silently
    collapse: "THE TUNING" sets as "THETUNING" or, worse, on top of itself.
    Measure and draw character by character instead.
    """
    w = 0.0
    for ch in text:
        w += word_gap if ch == " " else pdfmetrics.stringWidth(ch, font, size) + tracking
    return max(w - (tracking if text else 0), 0.0)


def draw_tracked(canv, x: float, y: float, text: str, font: str, size: float,
                 tracking: float, word_gap: float, color=INK) -> None:
    canv.setFillColorRGB(*color)
    canv.setFont(font, size)
    for ch in text:
        if ch == " ":
            x += word_gap
            continue
        canv.drawString(x, y, ch)
        x += pdfmetrics.stringWidth(ch, font, size) + tracking


# --------------------------------------------------------------------------
# flowables
# --------------------------------------------------------------------------
class Ornament(Flowable):
    """Three dots, centred: the scene break."""

    def __init__(self, space_before: float = 15.5, space_after: float = 15.5) -> None:
        super().__init__()
        self.sb, self.sa = space_before, space_after
        self.width = TEXT_W
        self.height = space_before + space_after + 3

    def draw(self) -> None:
        c = self.canv
        c.setFillColorRGB(*INK_SOFT)
        cx, y = TEXT_W / 2, self.sa + 1.2
        for dx in (-9, 0, 9):
            c.circle(cx + dx, y, 1.15, stroke=0, fill=1)


class Rule(Flowable):
    """Hairline rule, centred in its box."""

    def __init__(self, width: float, thickness: float = 0.5,
                 space_after: float = 0, color=INK_SOFT) -> None:
        super().__init__()
        self.wanted, self.t, self.sa, self.color = width, thickness, space_after, color
        self.width, self.height = width, thickness + space_after

    def wrap(self, aw, ah):
        self.width = aw
        return aw, self.t + self.sa

    def draw(self) -> None:
        c = self.canv
        c.setStrokeColorRGB(*self.color)
        c.setLineWidth(self.t)
        c.line((self.width - self.wanted) / 2, self.sa,
               (self.width + self.wanted) / 2, self.sa)


class TrackedLine(Flowable):
    """A centred display line with hand-set tracking.

    Not a Paragraph: ReportLab's paragraph parser collapses a run of
    whitespace, so a word gap built out of spaces and thin spaces collapses to
    one space and "THE TUNING" sets as "THETUNING". Drawing characters one at
    a time gives exact control of both letter and word gaps.
    """

    def __init__(self, text: str, font: str, size: float, tracking: float,
                 word_gap: float, color=INK) -> None:
        super().__init__()
        self.text, self.font, self.size = text, font, size
        self.tracking, self.word_gap, self.color = tracking, word_gap, color
        self.width = self._measure()
        self.height = size * 1.06

    def _measure(self) -> float:
        return tracked_width(self.text, self.font, self.size,
                             self.tracking, self.word_gap)

    def wrap(self, aw, ah):
        self._aw = aw
        return aw, self.height

    def draw(self) -> None:
        draw_tracked(self.canv, (self._aw - self.width) / 2, 0, self.text,
                     self.font, self.size, self.tracking, self.word_gap,
                     self.color)


class Bookmark(Flowable):
    """Zero-size flowable that writes a PDF outline entry at its position."""

    def __init__(self, title: str, key: str, level: int = 0) -> None:
        super().__init__()
        self.title, self.key, self.level = title, key, level
        self.width = self.height = 0

    def draw(self) -> None:
        self.canv.bookmarkPage(self.key)
        self.canv.addOutlineEntry(self.title, self.key, level=self.level, closed=False)


class Versal(Flowable):
    """The display initial, drawn as a glyph.

    Its baseline has to land on the baseline of the last line it stands
    beside, not on the bottom of the row: a paragraph's final baseline sits
    about a descent above the bottom of its box, so the glyph is drawn that
    far up (RISE). Measured against the rendered page; if the body leading or
    size changes, re-check it.
    """

    RISE = 4.7

    def __init__(self, letter: str, width: float, height: float,
                 font: str = "Crimson-Semi", size: float = 58) -> None:
        super().__init__()
        self.letter, self.width, self.height = letter, width, height
        self.font, self.size = font, size

    def draw(self) -> None:
        self.canv.setFillColorRGB(*INK)
        self.canv.setFont(self.font, self.size)
        self.canv.drawString(0, self.RISE, self.letter)


def _narrow_style() -> ParagraphStyle:
    return ParagraphStyle(
        "narrow", fontName="Crimson", fontSize=BODY_SIZE, leading=BODY_LEAD,
        textColor=INK, alignment=TA_JUSTIFY, firstLineIndent=0,
        hyphenationLang=HYPH, embeddedHyphenation=1,
    )


def dropcap(text: str, cap_lines: int = 3, size: float = 58) -> list[Flowable]:
    """Opening paragraph as a drop cap.

    The versal sits in a left cell; beside it, a narrow justified column holds
    as many words as will wrap to `cap_lines`; the remainder runs full measure
    underneath. The split is found by wrapping, so it cannot drift when the
    text is edited.
    """
    words = text.split()
    letter, rest = words[0][0], words[0][1:]
    words = ([rest] if rest else []) + words[1:]

    cap_gap = 6.0
    cap_w = pdfmetrics.stringWidth(letter, "Crimson-Semi", size) + cap_gap
    narrow_w = TEXT_W - cap_w
    narrow = _narrow_style()

    best = 1
    for i in range(1, len(words) + 1):
        probe = Paragraph(body_html(" ".join(words[:i])), narrow)
        probe.wrap(narrow_w, 10_000)
        if len(probe.blPara.lines) <= cap_lines:
            best = i
        else:
            break

    head = Paragraph(body_html(" ".join(words[:best])), narrow)
    table = Table(
        [[Versal(letter, cap_w, cap_lines * BODY_LEAD, size=size), head]],
        colWidths=[cap_w, narrow_w],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "BOTTOM"),
        ("VALIGN", (1, 0), (1, 0), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    out: list[Flowable] = [table]
    tail = " ".join(words[best:])
    if tail:
        out.append(Paragraph(body_html(tail), ParagraphStyle(
            "cont", parent=narrow, firstLineIndent=0)))
    return out


# --------------------------------------------------------------------------
# page furniture
# --------------------------------------------------------------------------
def paint_paper(canv) -> None:
    canv.saveState()
    canv.setFillColorRGB(*PAPER)
    canv.rect(-2, -2, PAGE_W + 4, PAGE_H + 4, stroke=0, fill=1)
    canv.restoreState()


def on_front(canv, doc) -> None:
    paint_paper(canv)


def on_body(canv, doc) -> None:
    paint_paper(canv)
    label = doc.page - 2                      # story pages are 1..n
    canv.saveState()
    if label >= 2:                            # no head on the opening page
        head = "THE TUNING" if doc.page % 2 == 0 else "WARSAW, 1943"
        tw = tracked_width(head, "Crimson-Italic", 8.3, 1.6, 6.0)
        draw_tracked(canv, (PAGE_W - tw) / 2, PAGE_H - M_TOP + 25, head,
                     "Crimson-Italic", 8.3, 1.6, 6.0, INK_SOFT)
        canv.setStrokeColorRGB(*HAIRLINE)
        canv.setLineWidth(0.4)
        canv.line(PAGE_W / 2 - 62, PAGE_H - M_TOP + 17,
                  PAGE_W / 2 + 62, PAGE_H - M_TOP + 17)
    if label >= 1:
        canv.setFillColorRGB(*INK_SOFT)
        canv.setFont("Crimson", 9.4)
        canv.drawCentredString(PAGE_W / 2, M_BOTTOM - 25, str(label))
    canv.restoreState()


# --------------------------------------------------------------------------
# styles
# --------------------------------------------------------------------------
def styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName="Crimson", fontSize=BODY_SIZE, leading=BODY_LEAD,
                textColor=INK, hyphenationLang=HYPH, embeddedHyphenation=1)
    return {
        "body": ParagraphStyle("body", alignment=TA_JUSTIFY, firstLineIndent=13,
                               allowWidows=0, allowOrphans=0, **base),
        "body_first": ParagraphStyle("body_first", alignment=TA_JUSTIFY,
                                     firstLineIndent=0, allowWidows=0,
                                     allowOrphans=0, **base),
        "title": ParagraphStyle("title", fontName="Crimson-Semi", fontSize=24,
                                leading=31, alignment=TA_CENTER, textColor=INK),
        "subtitle": ParagraphStyle("subtitle", fontName="Crimson-Italic",
                                   fontSize=11.5, leading=16,
                                   alignment=TA_CENTER, textColor=INK_SOFT),
        "dateline": ParagraphStyle("dateline", fontName="Crimson", fontSize=9.4,
                                   leading=14, alignment=TA_CENTER,
                                   textColor=INK_SOFT),
        "colo": ParagraphStyle("colo", fontName="Crimson", fontSize=9.3,
                               leading=14.6, alignment=TA_CENTER,
                               textColor=INK_SOFT, firstLineIndent=0),
        "colo_i": ParagraphStyle("colo_i", fontName="Crimson-Italic", fontSize=9.3,
                                 leading=14.6, alignment=TA_CENTER,
                                 textColor=INK_SOFT),
        "gloss": ParagraphStyle("gloss", fontName="Crimson-Italic", fontSize=8.9,
                               leading=12.3, textColor=INK_SOFT, alignment=TA_LEFT,
                               leftIndent=13, firstLineIndent=0, spaceBefore=2.6,
                               spaceAfter=0.6),
        "note_h": ParagraphStyle("note_h", fontName="Crimson-Semi", fontSize=12.5,
                                 leading=16, alignment=TA_LEFT, textColor=INK,
                                 spaceAfter=2),
        "note": ParagraphStyle("note", fontName="Crimson", fontSize=9.7,
                               leading=13.7, alignment=TA_LEFT, textColor=INK,
                               firstLineIndent=0, spaceAfter=5.5),
        "note_i": ParagraphStyle("note_i", fontName="Crimson-Italic", fontSize=9.4,
                                 leading=13.6, alignment=TA_LEFT,
                                 textColor=INK_SOFT, firstLineIndent=0,
                                 spaceBefore=10),
    }


# --------------------------------------------------------------------------
# manuscript
# --------------------------------------------------------------------------
GLOSS_RE = re.compile(r"^(?P<main>.*?)\s*\{\{(?P<gloss>.+?)\}\}\s*$", re.S)


def split_gloss(block: str) -> tuple[str, str | None]:
    """A block may carry its translation as `{{English}}`. The manuscript keeps
    one block per typeset paragraph; the builder hangs the translation under
    the line it belongs to."""
    m = GLOSS_RE.match(block)
    if not m:
        return block, None
    return m.group("main").strip(), m.group("gloss").strip()


def load_blocks() -> tuple[str, list[str]]:
    """Title plus a flat block list, `* * *` kept as the scene-break marker."""
    lines = SOURCE.read_text(encoding="utf-8").strip().split("\n")
    title, blocks, buf = "", [], []
    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if not line.strip():
            if buf:
                blocks.append(" ".join(buf))
                buf = []
            continue
        if line.strip() in {"* * *", "***", "---"}:
            if buf:
                blocks.append(" ".join(buf))
                buf = []
            blocks.append("* * *")
            continue
        buf.append(line.strip())
    if buf:
        blocks.append(" ".join(buf))
    return title, blocks


NOTES: list[str] = [
    "The German and the Polish are left as spoken. Beneath each line that "
    "needs it, in the smaller italic, is the plain English; where a German "
    "word falls inside a sentence of narration, the English follows it in "
    "brackets. Nothing is translated inside the quotation marks.",

    "<b>Ausweis</b> is a permit, as distinct from the <b>Kennkarte</b>, the "
    "identity card every Pole in the Generalgouvernement had to carry. The "
    "paper the Major writes is worth more than the piano: it keeps a household "
    "out of a street roundup, and it ties that household to his desk.",

    "The <i>du</i> the two of them use is the intimate form, and it is spoken "
    "in front of a housekeeper with a brother in the police. That is the risk "
    "she takes, and she takes it on purpose.",
]

HISTORICAL = (
    "The ghetto uprising began on 19 April 1943. The Great Synagogue on "
    "T\u0142omackie Street was blown up on 16 May, and the ash falling through "
    "this story is from that burning. Performance of Chopin by Poles was "
    "forbidden under the occupation. The curfew hour in Warsaw moved from "
    "month to month, which is why everyone in the city knew it to the minute."
)


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def build(out: pathlib.Path) -> None:
    rl_config.hyphenationLang = HYPH
    rl_config.embeddedHyphenation = 1
    rl_config.hyphenationMinWordLength = 6
    register_fonts()
    st = styles()
    title, blocks = load_blocks()

    doc = BaseDocTemplate(
        str(out),
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=M_SIDE, rightMargin=M_SIDE,
        topMargin=M_TOP, bottomMargin=M_BOTTOM,
        title=title,
        subject="A short story. Warsaw, May 1943.",
        author="",
        creator="autonovel stories/the-tuning/build_pdf.py",
    )

    frame = Frame(M_SIDE, M_BOTTOM, TEXT_W, TEXT_H,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                  id="text")
    doc.addPageTemplates([
        PageTemplate(id="front", frames=[frame], onPage=on_front),
        PageTemplate(id="body", frames=[frame], onPage=on_body),
    ])

    story: list[Flowable] = []

    # title page -----------------------------------------------------------
    story += [Spacer(1, 2.2 * inch)]
    story.append(Bookmark("Title page", "title"))
    story.append(TrackedLine("THE TUNING", "Crimson-Semi", 26, 3.6, 17))
    story.append(Spacer(1, 16))
    story.append(Rule(width=64, thickness=0.6))
    story.append(Spacer(1, 15))
    story.append(Paragraph("A Short Story", st["subtitle"]))
    story.append(Spacer(1, 1.95 * inch))
    story.append(TrackedLine("WARSAW \u00b7 MAY 1943", "Crimson", 9.4, 1.8, 8,
                             color=INK_SOFT))
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())

    # colophon (verso) -----------------------------------------------------
    story += [Spacer(1, 2.45 * inch)]
    story.append(TrackedLine("THE TUNING", "Crimson-Italic", 9.3, 2.2, 9,
                             color=INK_SOFT))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Warsaw, May 1943. The ash coming down over the city is from the "
        "ghetto, four streets north, in the fourth week of its destruction.",
        st["colo"]))
    story.append(Spacer(1, 13))
    story.append(Paragraph(
        "The German and Polish are given in plain English at the back.",
        st["colo"]))
    story.append(Spacer(1, 2.3 * inch))
    story.append(Rule(width=26, thickness=0.4))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Set in Crimson Text", st["colo"]))
    story.append(PageBreak())

    # body -----------------------------------------------------------------
    story.append(Bookmark("The Tuning", "story"))
    first = True
    after_break = True
    for block in blocks:
        if block == "* * *":
            story.append(Ornament())
            after_break = True
            continue
        if first:
            main, gloss = split_gloss(block)
            story.extend(dropcap(main, cap_lines=3))
            if gloss:
                story.append(Paragraph(body_html(gloss), st["gloss"]))
            first = False
            after_break = False
            continue
        main, gloss = split_gloss(block)
        para = Paragraph(body_html(main),
                         st["body_first"] if after_break else st["body"])
        if gloss:
            # never let a line and its translation land on facing pages
            story.append(KeepTogether([para, Paragraph(body_html(gloss),
                                                       st["gloss"])]))
        else:
            story.append(para)
        after_break = False

    # notes ----------------------------------------------------------------
    story.append(PageBreak())
    story.append(Bookmark("A note on the German and Polish", "notes"))
    story.append(Paragraph("A note on the German and Polish", st["note_h"]))
    story.append(Rule(width=TEXT_W, thickness=0.4, space_after=14))
    story.append(Spacer(1, 4))
    for entry in NOTES:
        story.append(Paragraph(entry, st["note"]))
    story.append(Paragraph(HISTORICAL, st["note_i"]))

    doc.build(story)


def main() -> None:
    ap = argparse.ArgumentParser(description="Typeset the-tuning.md as a PDF.")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    build(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
