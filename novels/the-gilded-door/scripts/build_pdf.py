#!/usr/bin/env python3
"""Typeset THE GILDED DOOR from chapters/*.md to a print-quality PDF.

Book block 5.5 x 8.5 in. EB Garamond (OFL). Mirrored margins, running heads,
two-line drop caps, hyphenated justification, scene ornaments, two-pass TOC.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
CHAPTERS = ROOT / "chapters"
OUT = ROOT / "out"

TITLE = "THE GILDED DOOR"
SUBTITLE = "A Novel of Rome"
AUTHOR = "ANONYMOUS"
YEAR = "MMXXVI"

PAGE_W, PAGE_H = 5.5 * inch, 8.5 * inch
INNER, OUTER = 0.85 * inch, 0.70 * inch
TOP, BOTTOM = 0.78 * inch, 0.90 * inch
FRAME_W = PAGE_W - INNER - OUTER
FRAME_H = PAGE_H - TOP - BOTTOM

INK = HexColor("#191411")
OXBLOOD = HexColor("#4A1418")
GOLD = HexColor("#9A7834")
PALE_GOLD = HexColor("#C6A45C")
CREAM = HexColor("#F3E7CF")
GREY = HexColor("#6C635C")
LIGHT_GREY = HexColor("#9A9088")

PARTS = {
    1: ("PART ONE", "THE GILDED DOOR"),
    2: ("PART TWO", "THE BOOK OF DEBTS"),
    3: ("PART THREE", "THE WOUND"),
    4: ("PART FOUR", "THE CAUSA"),
}


# --------------------------------------------------------------------------
# fonts
# --------------------------------------------------------------------------
def register_fonts() -> None:
    files = {
        "EBG": "EBGaramond-Regular.ttf",
        "EBG-Italic": "EBGaramond-Italic.ttf",
        "EBG-SemiBold": "EBGaramond-SemiBold.ttf",
        "EBG-Bold": "EBGaramond-Bold.ttf",
        "EBG-SemiBoldItalic": "EBGaramond-SemiBoldItalic.ttf",
    }
    for name, fn in files.items():
        pdfmetrics.registerFont(TTFont(name, str(FONTS / fn)))
    pdfmetrics.registerFontFamily(
        "EBG",
        normal="EBG",
        bold="EBG-SemiBold",
        italic="EBG-Italic",
        boldItalic="EBG-SemiBoldItalic",
    )


S = {}


def styles() -> None:
    base = dict(
        fontName="EBG",
        fontSize=11,
        leading=15.2,
        textColor=INK,
        hyphenationLang="en_GB",
        embeddedHyphenation=1,
        uriWasteReduce=0.3,
        allowWidows=0,
        allowOrphans=0,
        splitLongWords=1,
    )
    S["body"] = ParagraphStyle(
        "body", **base, alignment=TA_JUSTIFY, firstLineIndent=15, spaceBefore=0, spaceAfter=0
    )
    S["body_noindent"] = ParagraphStyle("body_noindent", parent=S["body"], firstLineIndent=0)
    S["letter"] = ParagraphStyle(
        "letter",
        parent=S["body"],
        fontSize=10.2,
        leading=14.6,
        alignment=TA_JUSTIFY,
        leftIndent=20,
        rightIndent=14,
        firstLineIndent=10,
        textColor=HexColor("#2A2320"),
        spaceBefore=0,
        spaceAfter=0,
    )
    S["toc_title"] = ParagraphStyle(
        "toc_title", parent=S["body"], alignment=TA_LEFT, fontSize=9.4, leading=12, firstLineIndent=0
    )
    S["toc_num"] = ParagraphStyle(
        "toc_num",
        parent=S["body"],
        alignment=TA_LEFT,
        fontSize=8.2,
        leading=12,
        firstLineIndent=0,
        textColor=GREY,
    )
    S["toc_page"] = ParagraphStyle(
        "toc_page",
        parent=S["body"],
        alignment=TA_RIGHT,
        fontSize=8.6,
        leading=12,
        firstLineIndent=0,
        textColor=GREY,
    )
    S["toc_part"] = ParagraphStyle(
        "toc_part",
        parent=S["body"],
        alignment=TA_LEFT,
        fontSize=8.2,
        leading=12,
        firstLineIndent=0,
        textColor=OXBLOOD,
    )
    S["back"] = ParagraphStyle(
        "back", parent=S["body"], fontSize=10.2, leading=14.4, firstLineIndent=14, spaceAfter=1
    )
    S["back_h"] = ParagraphStyle(
        "back_h",
        parent=S["body"],
        fontSize=13,
        leading=16,
        alignment=TA_CENTER,
        firstLineIndent=0,
        textColor=OXBLOOD,
        spaceAfter=4,
    )


# --------------------------------------------------------------------------
# small flowables
# --------------------------------------------------------------------------
def tracked(canv, x, y, text, font, size, tracking, color=None):
    # Character spacing is a graphics-state property and survives the text
    # object, so bracket the run or it leaks into every later string on the page.
    canv.saveState()
    t = canv.beginText(x, y)
    t.setFont(font, size)
    t.setCharSpace(tracking)
    if color is not None:
        t.setFillColor(color)
    t.textOut(text)
    canv.drawText(t)
    canv.restoreState()


def roman(n: int) -> str:
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


class Callback(Flowable):
    """Zero-height marker that runs a callback when drawn."""

    def __init__(self, fn, height=0.0):
        Flowable.__init__(self)
        self.fn = fn
        self.width = 0
        self.height = height

    def wrap(self, aw, ah):
        return (0.0, self.height)

    def draw(self):
        self.fn(self.canv)


class Spaced(Flowable):
    """A centred line with letter-spacing, drawn on the canvas."""

    def __init__(self, text, font="EBG-SemiBold", size=9.2, tracking=2.6,
                 color=OXBLOOD, align="center", height=None, leading=None):
        Flowable.__init__(self)
        self.text, self.font, self.size = text, font, size
        self.tracking, self.color, self.align = tracking, color, align
        self.leading = leading or size * 1.35
        self.height = height if height is not None else self.leading

    def wrap(self, aw, ah):
        self.width = aw
        return (aw, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        size = self.size
        tracking = self.tracking
        w = pdfmetrics.stringWidth(self.text, self.font, size) + tracking * len(self.text)
        if w > self.width and self.width > 0:
            scale = (self.width - 4) / w
            size *= scale
            tracking *= scale
            w = pdfmetrics.stringWidth(self.text, self.font, size) + tracking * len(self.text)
        if self.align == "center":
            x = (self.width - w) / 2.0
        elif self.align == "right":
            x = self.width - w
        else:
            x = 0
        tracked(c, x, (self.height - size) / 2.0 + size * 0.18, self.text,
                self.font, size, tracking, self.color)
        c.restoreState()


class Rule(Flowable):
    """A short hairline with a diamond at its centre."""

    def __init__(self, width=64, color=GOLD, diamond=True, pad=6):
        Flowable.__init__(self)
        self.rule_w = width
        self.color = color
        self.diamond = diamond
        self.height = pad * 2 + 4
        self.width = width

    def wrap(self, aw, ah):
        self.width = aw
        return (aw, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(self.color)
        c.setLineWidth(0.5)
        cx = self.width / 2.0
        y = self.height / 2.0
        gap = 5.5
        c.line(cx - self.rule_w / 2.0, y, cx - gap, y)
        c.line(cx + gap, y, cx + self.rule_w / 2.0, y)
        if self.diamond:
            c.setFillColor(self.color)
            p = c.beginPath()
            p.moveTo(cx, y + 2.2)
            p.lineTo(cx + 2.2, y)
            p.lineTo(cx, y - 2.2)
            p.lineTo(cx - 2.2, y)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
        c.restoreState()


class SceneBreak(Flowable):
    """Fleuron scene separator."""

    def __init__(self, gap_before=9, gap_after=9):
        Flowable.__init__(self)
        self.gap_before = gap_before
        self.gap_after = gap_after
        self.height = gap_before + gap_after + 11

    def wrap(self, aw, ah):
        self.width = aw
        return (aw, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(LIGHT_GREY)
        c.setFont("EBG", 10)
        glyph = "\u2766"
        w = pdfmetrics.stringWidth(glyph, "EBG", 10)
        c.drawString((self.width - w) / 2.0, self.gap_after, glyph)
        c.restoreState()


class DropCap(Flowable):
    """Drop-capped first paragraph.

    Splits the opening plain-text paragraph into N short lines beside a large
    initial, then the caller places the remainder as a normal paragraph.
    """

    def __init__(self, text, style, lines=2, cap_size=None, gap=5.0):
        Flowable.__init__(self)
        self.text = text
        self.style = style
        self.n_lines = lines
        self.gap = gap
        self.leading = style.leading
        self.size = style.fontSize
        self.cap_size = cap_size or (lines * self.leading / 0.66)
        self.cap_char = text[0] if text else ""
        self.rest = text[1:]
        self.fragments = []
        self.remainder = ""
        self.used_lines = 0
        self.width = 0

    def _space_w(self):
        return pdfmetrics.stringWidth(" ", self.style.fontName, self.size)

    def wrap(self, aw, ah):
        self.width = aw
        cap_w = pdfmetrics.stringWidth(self.cap_char, self.style.fontName, self.cap_size)
        line_w = aw - cap_w - self.gap
        words = self.rest.split()
        space = self._space_w()
        self.fragments = []
        cur, cur_w = [], 0.0
        while words and len(self.fragments) < self.n_lines:
            w = words[0]
            ww = pdfmetrics.stringWidth(w, self.style.fontName, self.size)
            add = ww if not cur else cur_w + space + ww
            if add <= line_w or len(cur) < 2:
                cur.append(w)
                cur_w = add
                words.pop(0)
            else:
                self.fragments.append(cur)
                cur, cur_w = [], 0.0
        if cur:
            self.fragments.append(cur)
        self.used_lines = max(1, len(self.fragments))
        self.remainder = " ".join(words)
        self.height = self.used_lines * self.leading
        return (aw, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(self.style.textColor)
        # initial
        cap_w = pdfmetrics.stringWidth(self.cap_char, self.style.fontName, self.cap_size)
        base = 0.22 * self.size
        cap_baseline = self.height - self.used_lines * self.leading + base
        c.setFont(self.style.fontName, self.cap_size)
        c.drawString(0, cap_baseline, self.cap_char)
        # short lines
        c.setFont(self.style.fontName, self.size)
        space = self._space_w()
        for i, frag in enumerate(self.fragments):
            y = self.height - (i + 1) * self.leading + base
            widths = [pdfmetrics.stringWidth(w, self.style.fontName, self.size) for w in frag]
            total = sum(widths) + space * (len(frag) - 1)
            target = self.width - cap_w - self.gap
            extra = (target - total) / (len(frag) - 1) if len(frag) > 1 else 0.0
            if extra < 0 or extra > space * 1.8:
                extra = 0.0
            x = cap_w + self.gap
            for w, ww in zip(frag, widths):
                c.drawString(x, y, w)
                x += ww + space + extra
        c.restoreState()


# --------------------------------------------------------------------------
# document
# --------------------------------------------------------------------------
class BookDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        BaseDocTemplate.__init__(self, filename, pagesize=(PAGE_W, PAGE_H), **kw)
        left_frame = Frame(OUTER, BOTTOM, FRAME_W, FRAME_H, id="l",
                           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        right_frame = Frame(INNER, BOTTOM, FRAME_W, FRAME_H, id="r",
                            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover",
                            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[cover_frame], onPage=self.cover, onPageEnd=self.decorate),
            PageTemplate(id="verso", frames=[left_frame], onPage=self.begin_page, onPageEnd=self.decorate),
            PageTemplate(id="recto", frames=[right_frame], onPage=self.begin_page, onPageEnd=self.decorate),
        ])
        self.current_chapter = ""
        self.chapter_started = False
        self.plain_page = False
        self.body_started = False
        self.body_first_page = 0
        self.chapter_pages = {}
        self.part_pages = {}
        self.outline = []

    # ---- page state -----------------------------------------------------
    def begin_page(self, canv, doc):
        self.chapter_started = False
        self.plain_page = False

    def decorate(self, canv, doc):
        page = canv.getPageNumber()
        if page == 1:
            return
        if not self.body_started:
            return
        folio = page - self.body_first_page + 1
        canv.saveState()
        if not self.plain_page:
            if not self.chapter_started:
                label = (TITLE if folio % 2 == 0 else self.current_chapter.upper())
                w = pdfmetrics.stringWidth(label, "EBG-SemiBold", 7.3) + 1.55 * len(label)
                x = (PAGE_W - w) / 2.0
                tracked(canv, x, PAGE_H - 42, label, "EBG-SemiBold", 7.3, 1.55, GREY)
            canv.setFont("EBG", 8.6)
            canv.setFillColor(GREY)
            num = str(folio)
            canv.drawCentredString(PAGE_W / 2.0, 36, num)
        canv.restoreState()

    def cover(self, canv, doc):
        canv.saveState()
        canv.setFillColor(HexColor("#3B1116"))
        canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        # double rule
        canv.setStrokeColor(PALE_GOLD)
        canv.setLineWidth(0.9)
        canv.rect(30, 30, PAGE_W - 60, PAGE_H - 60, fill=0, stroke=1)
        canv.setLineWidth(0.35)
        canv.rect(37, 37, PAGE_W - 74, PAGE_H - 74, fill=0, stroke=1)
        # top mark
        cx = PAGE_W / 2.0
        canv.setFillColor(PALE_GOLD)
        p = canv.beginPath()
        p.moveTo(cx, PAGE_H - 84)
        p.lineTo(cx + 4.2, PAGE_H - 88.2)
        p.lineTo(cx, PAGE_H - 92.4)
        p.lineTo(cx - 4.2, PAGE_H - 88.2)
        p.close()
        canv.drawPath(p, fill=1, stroke=0)
        # title
        for text, y in (("THE", 392), ("GILDED", 340), ("DOOR", 288)):
            w = pdfmetrics.stringWidth(text, "EBG-SemiBold", 35) + 3.2 * len(text)
            tracked(canv, (PAGE_W - w) / 2.0, y, text, "EBG-SemiBold", 35, 3.2, CREAM)
        # rule + subtitle
        canv.setStrokeColor(PALE_GOLD)
        canv.setLineWidth(0.5)
        canv.line(cx - 52, 256, cx - 7, 256)
        canv.line(cx + 7, 256, cx + 52, 256)
        p = canv.beginPath()
        p.moveTo(cx, 259.2)
        p.lineTo(cx + 3.2, 256)
        p.lineTo(cx, 252.8)
        p.lineTo(cx - 3.2, 256)
        p.close()
        canv.setFillColor(PALE_GOLD)
        canv.drawPath(p, fill=1, stroke=0)
        sub = SUBTITLE.upper()
        w = pdfmetrics.stringWidth(sub, "EBG-SemiBold", 9.4) + 3.4 * len(sub)
        tracked(canv, (PAGE_W - w) / 2.0, 222, sub, "EBG-SemiBold", 9.4, 3.4, PALE_GOLD)
        # city / date
        canv.setFillColor(HexColor("#C9B79A"))
        canv.setFont("EBG-Italic", 10.2)
        canv.drawCentredString(cx, 128, "Rome, AD 112\u2013113")
        # author
        w = pdfmetrics.stringWidth(AUTHOR, "EBG-SemiBold", 11) + 4.2 * len(AUTHOR)
        tracked(canv, (PAGE_W - w) / 2.0, 74, AUTHOR, "EBG-SemiBold", 11, 4.2, CREAM)
        canv.restoreState()


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------
def smart(t: str) -> str:
    """Convert straight quotes, dashes and ellipses to typographic forms."""
    out = []
    prev = ""
    i = 0
    n = len(t)
    while i < n:
        ch = t[i]
        if ch == '"':
            opening = prev == "" or prev.isspace() or prev in "([{\u2014\u2013-\u2018\u201c"
            out.append("\u201c" if opening else "\u201d")
            prev = ch
            i += 1
            continue
        if ch == "'":
            opening = prev == "" or prev.isspace() or prev in "([{\u2014\u2013-"
            nxt = t[i + 1] if i + 1 < n else ""
            if opening and (nxt.isalpha() or nxt in "\u201c"):
                out.append("\u2018")
            else:
                out.append("\u2019")
            prev = ch
            i += 1
            continue
        if t.startswith("---", i):
            out.append("\u2014")
            prev = "-"
            i += 3
            continue
        if t.startswith("--", i):
            out.append("\u2013")
            prev = "-"
            i += 2
            continue
        if t.startswith("...", i):
            out.append("\u2026")
            prev = "."
            i += 3
            continue
        out.append(ch)
        prev = ch
        i += 1
    return "".join(out)


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(t: str) -> str:
    t = esc(smart(t))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t, flags=re.S)
    t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t, flags=re.S)
    return t


def parse_front(raw: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        raise ValueError("missing frontmatter")
    front = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            front[k.strip()] = v.strip().strip('"').strip("'")
    return front, m.group(2).strip()


def chapter_defs():
    chs = []
    for p in sorted(CHAPTERS.glob("ch_*.md")):
        front, body = parse_front(p.read_text(encoding="utf-8"))
        chs.append({
            "num": int(front.get("chapter", 0)),
            "title": front.get("title", ""),
            "dateline": front.get("dateline", ""),
            "part": int(front.get("part", 1)),
            "pov": front.get("pov", ""),
            "body": body,
            "path": p,
        })
    chs.sort(key=lambda c: c["num"])
    return chs


# Chapters whose last page would otherwise carry only a line or two: their
# leading is tightened by a fraction of a point so the ending pulls back a leaf.
TIGHT = {6: 0.18}


def body_flowables(ch, doc):
    out = []
    delta = TIGHT.get(ch["num"], 0.0)
    body_st = S["body"]
    body_ni = S["body_noindent"]
    letter_st = S["letter"]
    if delta:
        tag = "t%d" % ch["num"]
        body_st = S["body"].clone(tag + "b", leading=S["body"].leading - delta)
        body_ni = S["body_noindent"].clone(tag + "n", leading=S["body_noindent"].leading - delta)
        letter_st = S["letter"].clone(tag + "l", leading=S["letter"].leading - delta)
    blocks = re.split(r"\n\s*\n", ch["body"])
    first = True
    after_break = False
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if re.fullmatch(r"\*\s*\*\s*\*", b):
            out.append(SceneBreak())
            after_break = True
            continue
        if b.startswith(">"):
            text = " ".join(line.lstrip("> ").strip() for line in b.splitlines())
            out.append(Paragraph(inline(text), letter_st))
            out.append(Spacer(1, 7))
            after_break = True
            continue
        text = " ".join(line.strip() for line in b.splitlines())
        if first and "*" not in text and len(text) > 200:
            dc = DropCap(text, body_ni, lines=2)
            out.append(dc)
            # remainder needs the fragments computed; wrap at known width
            dc.wrap(FRAME_W, 1000)
            if dc.remainder:
                out.append(Paragraph(inline(dc.remainder), body_ni))
            first = False
            after_break = False
            continue
        style = body_st if not (first or after_break) else body_ni
        out.append(Paragraph(inline(text), style))
        first = False
        after_break = False
    return out


def front_matter(toc_rows):
    out = []
    out.append(NextPageTemplate(["verso", "recto"]))
    out.append(PageBreak())                      # 1 cover -> 2
    out.append(PageBreak())                      # 2 blank -> 3
    out.append(Spacer(1, 150))
    out.append(Spaced(TITLE, size=13, tracking=4.6, color=INK))
    out.append(PageBreak())                      # 3 half-title -> 4
    out.append(PageBreak())                      # 4 blank -> 5
    out.append(Spacer(1, 108))
    out.append(Spaced("THE GILDED", size=22, tracking=4.0, color=OXBLOOD, leading=30))
    out.append(Spaced("DOOR", size=22, tracking=4.0, color=OXBLOOD, leading=30))
    out.append(Spacer(1, 12))
    out.append(Spaced(SUBTITLE.upper(), size=8.8, tracking=3.9, color=GREY))
    out.append(Spacer(1, 26))
    out.append(Rule(width=54))
    out.append(Spacer(1, 110))
    out.append(Spaced(AUTHOR, size=11.5, tracking=4.4, color=INK))
    out.append(Spacer(1, 6))
    out.append(Spaced(YEAR, size=8.2, tracking=2.4, color=GREY))
    out.append(PageBreak())                      # 5 title -> 6
    # copyright (verso of title page)
    out.append(Spacer(1, 268))
    def _credits(block, style_name):
        t = Table([[Paragraph(inline(block), S["back"].clone(style_name, fontSize=7.6,
                                                             leading=10.8,
                                                             alignment=TA_CENTER,
                                                             firstLineIndent=0,
                                                             textColor=GREY))]],
                  colWidths=[FRAME_W - 52])
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        t.hAlign = "CENTER"
        return t
    out.append(_credits(
        "This is a work of fiction. The historical persons, places and events "
        "portrayed here are used imaginatively. All other characters are "
        "inventions, and any resemblance to the living or the dead is accidental.",
        "cr1"))
    out.append(Spacer(1, 10))
    out.append(_credits(
        "**Mature content.** This novel contains depictions of slavery, sexual "
        "coercion, physical violence and torture. It is intended for adult readers.",
        "cr2"))
    out.append(Spacer(1, 16))
    out.append(_credits("First edition, " + YEAR + " · Set in EB Garamond · 5.5 × 8.5 inches",
                        "cr3"))
    out.append(PageBreak())                      # 6 -> 7
    # epigraph
    out.append(Spacer(1, 190))
    out.append(Paragraph(
        "<i>“Quid Romae faciam? mentiri nescio.”</i>",
        S["body"].clone("ep1", fontSize=11.5, leading=16, alignment=TA_CENTER,
                        firstLineIndent=0, textColor=INK)))
    out.append(Spacer(1, 8))
    out.append(Paragraph(
        "“What should I do at Rome? I do not know how to lie.”",
        S["body"].clone("ep2", fontSize=9.4, leading=13, alignment=TA_CENTER,
                        firstLineIndent=0, textColor=GREY)))
    out.append(Spacer(1, 10))
    out.append(Spaced("JUVENAL · SATIRES III", size=7.6, tracking=2.4, color=GOLD))
    out.append(PageBreak())                      # 7 -> 8
    out.append(PageBreak())                      # 8 blank -> 9
    # contents
    out.append(Spacer(1, 28))
    out.append(Spaced("CONTENTS", size=10.5, tracking=4.4, color=OXBLOOD))
    out.append(Spacer(1, 20))
    out.append(Rule(width=44))
    out.append(Spacer(1, 14))
    def _table(rows):
        t = Table(rows, colWidths=[34, FRAME_W - 34 - 24, 24])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 3.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return t

    rows = []
    for kind, a, b, c in toc_rows:
        if kind == "break":
            if rows:
                out.append(_table(rows))
                rows = []
            out.append(PageBreak())
            out.append(Spacer(1, 58))
            continue
        if kind == "part":
            rows.append([Paragraph("", S["toc_part"]),
                         Paragraph(esc(a), S["toc_part"]),
                         Paragraph(esc(b), S["toc_page"])])
        else:
            rows.append([Paragraph(esc(a), S["toc_num"]),
                         Paragraph(inline(b), S["toc_title"]),
                         Paragraph(esc(c), S["toc_page"])])
    if rows:
        out.append(_table(rows))
    return out


def part_page(num):
    label, title = PARTS[num]
    return [
        PageBreak(),
        Callback(lambda c, n=num: None),
        Spacer(1, 128),
        Spaced(label, size=8.6, tracking=4.4, color=GOLD),
        Spacer(1, 14),
        Spaced(title, size=19, tracking=1.8, color=OXBLOOD, leading=26),
        Spacer(1, 20),
        Rule(width=60),
    ]


def back_matter():
    out = [PageBreak(), Spacer(1, 40)]
    out.append(Spaced("A NOTE ON THE HISTORY", size=10.2, tracking=3.6, color=OXBLOOD))
    out.append(Spacer(1, 18))
    out.append(Rule(width=44))
    out.append(Spacer(1, 16))
    paras = [
        "The Rome of this novel is the Rome of the years 112 and 113, in the fifteenth and sixteenth years of the emperor Trajan. The great forum beside the Forum of Augustus was then new; the column that carried the story of the Dacian wars was dedicated in the spring of 113 and the emperor left for the east in the autumn of that year, and did not come back. Trajan was consul for the sixth time, with Titus Sextius Africanus, and the city was between two wars.",
        "A few of the people in this book existed. Trajan did; so did his wife Pompeia Plotina, his sister Marciana, his niece Matidia, the jurist Neratius Priscus and the prefect Acilius Attianus. Their public careers are a matter of record. What they said in private, and what they did in the rooms this novel invents, is not.",
        "The rest are invented, but the conditions they live in are not. A senator needed a census of a million sesterces. An equestrian needed four hundred thousand. A freedman could be richer than either and still be barred from the Senate, from certain marriages, and from the easy assumption of respect. A woman could own property, run a business, lend money and go to law, and still require a man to stand for her in a question of status. A slave was a thing in law: a thing that could be sold, pledged, inherited, and, where a court wanted evidence, tortured.",
        "A child born to a free mother was free, even if the mother had been a slave when the child was conceived; the law leaned, where it could, toward liberty. That single rule is the hinge on which this story turns, and it is the one piece of legal machinery here that I have not invented.",
        "The other machinery is as close to the record as I could make it. A question of status was heard before the urban praetor, with a free man — the adsertor — asserting the claim on the person's behalf, and the archaic form of manumission by the rod survived into the second century for exactly this purpose: freedom declared in public, before witnesses, by a touch of wood. Restitutio natalium was an imperial rescript, granted by the emperor's own hand and outside the ordinary petitions office, and it did what the novel says it did: it made a freed person freeborn in law, from birth, and it erased the record of the servitude that had come before. It was a favour, and it could carry conditions.",
        "Relegation to an island was not a sentence of death. It was the emperor's answer to a case that the courts would have handled more harshly and more publicly, and it allowed a great family to survive a crime it could not deny. Men came back from it, and wrote about it, and were believed.",
        "The Latin and the money are left as the Romans left them. A sesterce was a small brass coin, four of them made a denarius, and a legionary's year was twelve hundred of them before deductions. A modius of wheat cost a few sesterces in a good year and a great deal more in a bad one. Where a character says a sum, the sum is meant to be felt, not converted. The glossary at the back explains the words a reader is likely to trip over, and the offices a reader is likely to confuse.",
    ]
    for p in paras:
        out.append(Paragraph(inline(p), S["back"]))
        out.append(Spacer(1, 6))

    out.append(PageBreak())
    out.append(Spacer(1, 40))
    out.append(Spaced("GLOSSARY", size=10.2, tracking=3.6, color=OXBLOOD))
    out.append(Spacer(1, 18))
    out.append(Rule(width=44))
    out.append(Spacer(1, 16))
    terms = [
        ("aedile", "A magistrate responsible for streets, markets, water and public order. The aediles could close a disorderly house and fine its keeper."),
        ("adsertor libertatis", "The free man who formally asserted, in court, that a person claimed as a slave was in fact free. If he lost, he paid a penalty."),
        ("annona", "The grain supply of Rome, and the office that managed it. A bad year meant bread riots; a good year meant votes."),
        ("basilica", "A long roofed hall used for courts and business, usually along a forum."),
        ("causa liberalis", "A freedom suit: a formal hearing to decide whether a person was free or a slave."),
        ("census", "The property qualification for a class. A senator needed a million sesterces; an equestrian, four hundred thousand."),
        ("centurion", "A career soldier commanding a century of about eighty men. The backbone of the army and, often, of a province's administration."),
        ("client", "A man attached to a patron by favours, obligations and the morning call. The relationship ran both ways, and neither way was free."),
        ("cognitio", "A hearing conducted by a magistrate or the emperor himself, rather than by a jury court."),
        ("consular", "A man who had been consul. The rank opened the great provinces and the emperor's council, and closed nothing."),
        ("decemviri", "The board of ten young senators who, among other duties, sat with the praetor in questions of status and inheritance."),
        ("delator", "An informer who brought prosecutions in the hope of a share of the condemned man's property. Necessary to the treasury; loathed by everyone."),
        ("denarius", "A silver coin worth four sesterces, and roughly a day's wage for a skilled workman."),
        ("equestrian", "The second order of Rome, below the Senate. Knights commanded cohorts, ran the great offices, and lent the state its money."),
        ("ergastulum", "The slave prison or workhouse on a country estate. The word was meant to frighten, and did."),
        ("familia", "The household, including slaves, freedmen and dependants. Not a family in the modern sense; a unit of authority."),
        ("freedman", "A slave who had been formally manumitted. Free, and not free: barred from office, marked by the name, and often richer than his betters."),
        ("fiscus", "The emperor's treasury, as distinct from the public treasury of Rome."),
        ("hypocaust", "The under-floor heating of a bath or a rich man's dining room."),
        ("imperium", "The power of command held by consuls, praetors and governors. A man with imperium could order a beating, a levy or a war."),
        ("infamia", "Legal disgrace. It followed certain trades and certain convictions, and it shut courts, marriages and doors."),
        ("ius annuli", "The right of a freedman to wear the gold ring of an equestrian. A small hoop of metal, and a whole rank of difference."),
        ("lanista", "A trainer and dealer in gladiators. A useful man to know, and not a respectable one."),
        ("lararium", "The household shrine, where the family's gods stood in miniature."),
        ("legatus", "A senator serving as the emperor's deputy, usually in command of a legion or a province."),
        ("leno", "A brothel-keeper or pimp. Legally tolerated, socially despised, and taxed."),
        ("libertus", "A freedman, in relation to the master who freed him."),
        ("lictors", "The attendants who carried the fasces before a magistrate. The number of rods told you how much to bow."),
        ("litter", "A covered sedan chair carried by slaves. A public statement about the length of a man's purse."),
        ("ludi", "The games: chariot racing, theatre, gladiators, beast hunts. The Roman calendar's chief entertainment and its chief politics."),
        ("manumission", "The formal freeing of a slave, by will, by the rod before a magistrate, or by census. Informal freedom left a man neither slave nor citizen."),
        ("mosaic", "A floor or wall picture made of small stone or glass cubes. Expensive, durable, and a way of telling guests exactly who you were."),
        ("nomen", "The middle name of a Roman citizen, marking the clan. A freedman took the name of the man who freed him, and never stopped hearing it."),
        ("patron", "A man who protected clients and freedmen and expected service in return. The word covered everything from friendship to ownership."),
        ("peculium", "The savings a slave was allowed to keep and manage. Often the only road to buying one's own freedom."),
        ("peristyle", "A garden or court surrounded by a colonnade."),
        ("plagium", "The crime of knowingly holding a free person as a slave, or of buying and selling one. Punished severely, and committed often."),
        ("praetor", "A senior magistrate with legal jurisdiction. The urban praetor heard cases between citizens; his edict was law for a year."),
        ("proconsul", "A consul's power extended to a province after his year in office. The great provinces were governed by men chosen by lot or by favour."),
        ("relegatio", " A sentence of banishment to a named place, without loss of citizenship or property. The milder cousin of exile, and often the emperor's way of ending a scandal quietly."),
        ("restitutio natalium", "An imperial grant restoring to a freedman the standing of the freeborn. A favour, not a right; it could not be demanded, only bought."),
        ("sesterce", "The common brass coin. Four to the denarius; a month's rent in the Subura for a small room."),
        ("stola", "The long dress of a respectable married woman. Not cloth so much as a claim."),
        ("tablinum", "The room off the atrium where a household kept its records and received its visitors."),
        ("toga", "The citizen's gown. Heavy, awkward, expensive to keep white, and indispensable in public."),
        ("tribune", "An officer of a cohort or a legion, or a plebeian official. In the vigiles, a tribune commanded a cohort of the fire-watch."),
        ("vigiles", "The fire-watch of Rome: seven cohorts of freedmen, with buckets, hooks, pumps and a licence to break down doors."),
        ("vindicta", "The rod used in the formal manumission of a slave before a magistrate. A touch of wood, and a change of life."),
    ]
    rows = []
    for term, defn in terms:
        rows.append([
            Paragraph("<b>" + esc(term) + "</b>", S["back"].clone("g1", firstLineIndent=0,
                                                                  fontSize=9.4, leading=12.2)),
            Paragraph(inline(defn), S["back"].clone("g2", firstLineIndent=0, fontSize=9.4,
                                                    leading=12.2)),
        ])
    t = Table(rows, colWidths=[92, FRAME_W - 92])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    out.append(t)

    out.append(PageBreak())
    out.append(Spacer(1, 40))
    out.append(Spaced("COLOPHON", size=10.2, tracking=3.6, color=OXBLOOD))
    out.append(Spacer(1, 18))
    out.append(Rule(width=44))
    out.append(Spacer(1, 16))
    for p in [
        "Set in EB Garamond, a digital revival of the types cut by Claude Garamont in the sixteenth century, itself drawn from the hand of a fifteenth-century Venetian. The face is licensed under the SIL Open Font License and is used here without modification beyond subsetting.",
        "Composed and typeset with the *autonovel* pipeline: chapters held as plain text, the page built from a single specification of measure, leading and ornament, and the whole assembled twice, once to learn where each chapter falls and once to print it.",
        "The book was written in the order it is meant to be read.",
    ]:
        out.append(Paragraph(inline(p), S["back"].clone("col", fontSize=9.6, leading=13.2,
                                                        alignment=TA_JUSTIFY)))
        out.append(Spacer(1, 7))
    return out


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def build(chapters, pages, part_pages, out_path, pad=False):
    doc = BookDoc(str(out_path), title="The Gilded Door", author="Anonymous",
                  subject="A Novel of Rome", creator="autonovel")
    story = []
    # TOC rows
    toc_rows = []
    by_part = {}
    for ch in chapters:
        by_part.setdefault(ch["part"], []).append(ch)
    for pnum in sorted(by_part):
        label, ptitle = PARTS[pnum]
        pg = part_pages.get(pnum)
        if pnum == 3:
            toc_rows.append(("break", "", "", ""))
        # part pages are unnumbered plates: no folio in the contents
        toc_rows.append(("part", ptitle, "", ""))
        for ch in by_part[pnum]:
            pg = pages.get(ch["num"])
            toc_rows.append(("chapter", roman(ch["num"]), ch["title"],
                             str(pg) if pg else "00"))
    story += front_matter(toc_rows)
    if pad:
        story.append(PageBreak())

    first_body = [True]

    def mark_chapter(ch):
        def fn(canv):
            if first_body[0]:
                doc.body_started = True
                doc.body_first_page = canv.getPageNumber()
                first_body[0] = False
            doc.current_chapter = ch["title"]
            doc.chapter_started = True
            doc.plain_page = False
            doc.chapter_pages[ch["num"]] = canv.getPageNumber() - doc.body_first_page + 1
            key = "ch%d" % ch["num"]
            canv.bookmarkPage(key)
            canv.addOutlineEntry("%s. %s" % (roman(ch["num"]), ch["title"]), key, level=1)
        return fn

    def mark_part(pnum):
        def fn(canv):
            doc.plain_page = True
            doc.chapter_started = True
            doc.part_pages[pnum] = canv.getPageNumber() - doc.body_first_page + 1
            key = "part%d" % pnum
            canv.bookmarkPage(key)
            canv.addOutlineEntry(PARTS[pnum][1].title(), key, level=0)
        return fn

    current_part = None
    for ch in chapters:
        if ch["part"] != current_part:
            current_part = ch["part"]
            story.append(PageBreak())
            story.append(Callback(mark_part(current_part)))
            story.append(Spacer(1, 128))
            story.append(Spaced(PARTS[current_part][0], size=8.6, tracking=4.4, color=GOLD))
            story.append(Spacer(1, 14))
            story.append(Spaced(PARTS[current_part][1], size=19, tracking=1.8,
                                color=OXBLOOD, leading=26))
            story.append(Spacer(1, 20))
            story.append(Rule(width=60))
        story.append(PageBreak())
        story.append(Callback(mark_chapter(ch)))
        story.append(Spacer(1, 24))
        story.append(Spaced("CHAPTER " + roman(ch["num"]), size=8.8, tracking=3.2, color=GOLD))
        story.append(Spacer(1, 8))
        story.append(Spaced(ch["title"].upper(), size=15.2, tracking=1.15, color=OXBLOOD,
                            leading=20))
        story.append(Spacer(1, 8))
        if ch["dateline"]:
            story.append(Spaced(ch["dateline"], font="EBG-Italic", size=9.2, tracking=0.5,
                                color=GREY, leading=13))
        story.append(Spacer(1, 12))
        story.append(Rule(width=46))
        story.append(Spacer(1, 14))
        story += body_flowables(ch, doc)

    def mark_back(canv):
        doc.current_chapter = TITLE.upper()
        doc.chapter_started = True
        doc.plain_page = False
    bm = back_matter()
    story.append(bm[0])          # the PageBreak that opens the back matter
    story.append(Callback(mark_back))
    story += bm[1:]
    doc.build(story)
    return doc.chapter_pages, doc.part_pages, doc.body_first_page


def main():
    register_fonts()
    styles()
    chapters = chapter_defs()
    if not chapters:
        sys.exit("no chapters found")
    OUT.mkdir(parents=True, exist_ok=True)
    pages, part_pages = {}, {}
    pad = False
    for i in range(5):
        tmp = OUT / ("_pass%d.pdf" % (i + 1))
        new_pages, new_parts, _bfp = build(chapters, pages, part_pages, tmp, pad)
        if new_pages == pages and new_parts == part_pages:
            break
        pages, part_pages = new_pages, new_parts
    # chapter one must open on a recto: body page 1 at an odd physical page
    probe = OUT / "_probe.pdf"
    _, _, bfp = build(chapters, pages, part_pages, probe, pad)
    if bfp % 2 == 0:
        pad = not pad
        pages, part_pages = {}, {}
        for i in range(3):
            tmp = OUT / ("_pad%d.pdf" % i)
            pages, part_pages, _ = build(chapters, pages, part_pages, tmp, pad)
    final = OUT / "the-gilded-door.pdf"
    build(chapters, pages, part_pages, final, pad)
    print("wrote", final)
    print("chapters:", len(chapters),
          "words:", sum(len(c["body"].split()) for c in chapters))
    print("chapter pages:", pages)


if __name__ == "__main__":
    main()
