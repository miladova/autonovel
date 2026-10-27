#!/usr/bin/env python3
"""Typeset THE GILDED MYRTLE from manuscript markdown into a 5.5 x 8.5in PDF.

Design target is src/autonovel/templates/series/typeset/novel.tex:
trade-paperback trim, mirrored margins, EB Garamond, 1.12 line stretch,
1.5em first-line indent, justified body with a forgiving measure,
widow/orphan control, ragged bottom, small-caps running heads
(title verso / chapter recto), centered folios, part-title pages that
start recto with no running head.

Usage:  /tmp/venv/bin/python typeset.py [output.pdf]
"""

import os
import re
import sys

from reportlab.lib.colors import black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, PageBreak,
                                PageTemplate, Paragraph, Spacer)

HERE = os.path.dirname(os.path.abspath(__file__))
MS = os.path.join(HERE, "..", "manuscript")
FONTS = os.path.join(HERE, "fonts")

TITLE = "THE GILDED MYRTLE"
SUBTITLE = "A NOVEL OF ROME"

PAGE_W, PAGE_H = 5.5 * inch, 8.5 * inch
M_TOP = 0.75 * inch
M_BOT = 0.85 * inch
M_IN = 0.85 * inch
M_OUT = 0.65 * inch
TEXT_W = PAGE_W - M_IN - M_OUT
TEXT_H = PAGE_H - M_TOP - M_BOT

BODY_SIZE = 11.0
VERSAL_SIZE = 18.5
LEADING = BODY_SIZE * 1.12 * 1.235  # ~ novel.tex's \setstretch{1.12}
INDENT = 1.5 * BODY_SIZE

PARTS = [
    ("part_01.md", 1, 4),
    ("part_02.md", 5, 10),
    ("part_03.md", 11, 16),
    ("part_04.md", 17, 25),
]

NUMERALS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
            7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten", 11: "Eleven",
            12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen",
            16: "Sixteen", 17: "Seventeen", 18: "Eighteen", 19: "Nineteen",
            20: "Twenty", 21: "Twenty-One", 22: "Twenty-Two",
            23: "Twenty-Three", 24: "Twenty-Four", 25: "Twenty-Five"}


# ---------------------------------------------------------------- fonts


def register_fonts():
    variants = {
        "EBG": "400Regular",
        "EBG-Bold": "700Bold",
        "EBG-Italic": "400Regular_Italic",
        "EBG-BoldItalic": "700Bold_Italic",
        "EBG-Semi": "600SemiBold",
    }
    for name, folder in variants.items():
        path = os.path.join(FONTS, folder, "EBGaramond_%s.ttf" % folder)
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(
        "EBG",
        normal="EBG",
        bold="EBG-Bold",
        italic="EBG-Italic",
        boldItalic="EBG-BoldItalic",
    )


VERSAL_GAP = 0.0  # set once the fonts are registered


# ---------------------------------------------------------------- styles


def styles():
    global VERSAL_GAP
    VERSAL_GAP = (pdfmetrics.getAscent("EBG", VERSAL_SIZE)
                  - pdfmetrics.getAscent("EBG", BODY_SIZE))
    s = {}
    s["body"] = ParagraphStyle(
        "body",
        fontName="EBG",
        fontSize=BODY_SIZE,
        leading=LEADING,
        alignment=TA_JUSTIFY,
        firstLineIndent=INDENT,
        spaceBefore=0,
        spaceAfter=0,
        allowWidows=0,
        allowOrphans=0,
        hyphenationLang="en_US",
        embeddedHyphenation=1,
        splitLongWords=1,
        uriWasteReduce=0.3,
        textColor=black,
    )
    s["body0"] = ParagraphStyle("body0", parent=s["body"], firstLineIndent=0)
    s["chapnum"] = ParagraphStyle(
        "chapnum",
        fontName="EBG",
        fontSize=8.6,
        leading=11,
        alignment=TA_CENTER,
        charSpace=2.4,
    )
    s["chaptitle"] = ParagraphStyle(
        "chaptitle",
        fontName="EBG-Italic",
        fontSize=16,
        leading=19,
        alignment=TA_CENTER,
    )
    s["partnum"] = ParagraphStyle(
        "partnum",
        fontName="EBG",
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        charSpace=4.0,
    )
    s["parttitle"] = ParagraphStyle(
        "parttitle",
        fontName="EBG",
        fontSize=19,
        leading=24,
        alignment=TA_CENTER,
        charSpace=3.0,
    )
    s["halftitle"] = ParagraphStyle(
        "halftitle",
        fontName="EBG",
        fontSize=15,
        leading=20,
        alignment=TA_CENTER,
        charSpace=2.6,
    )
    s["bigtitle"] = ParagraphStyle(
        "bigtitle",
        fontName="EBG",
        fontSize=31,
        leading=37,
        alignment=TA_CENTER,
        charSpace=2.0,
    )
    s["subtitle"] = ParagraphStyle(
        "subtitle",
        fontName="EBG-Italic",
        fontSize=13.5,
        leading=18,
        alignment=TA_CENTER,
        charSpace=1.0,
    )
    s["colophon"] = ParagraphStyle(
        "colophon",
        fontName="EBG",
        fontSize=8.6,
        leading=13.2,
        alignment=TA_CENTER,
    )
    return s


# ---------------------------------------------------------------- flowables


class Rule(Flowable):
    """Centred hairline with a small diamond at its middle."""

    def __init__(self, width=1.35 * inch, gap=5, thick=0.5):
        Flowable.__init__(self)
        self.width = width
        self.gap = gap
        self.thick = thick
        self.height = 12

    def wrap(self, aw, ah):
        return (aw, self.height)

    def draw(self):
        c = self.canv
        w = self.width
        x0 = (self.width_frame - w) / 2.0
        y = self.height / 2.0
        c.setLineWidth(self.thick)
        c.setStrokeColor(black)
        c.setFillColor(black)
        c.line(x0, y, x0 + w / 2 - self.gap - 3, y)
        c.line(x0 + w / 2 + self.gap + 3, y, x0 + w, y)
        d = 2.6
        c.saveState()
        c.translate(x0 + w / 2, y)
        c.rotate(45)
        c.rect(-d / 2, -d / 2, d, d, stroke=0, fill=1)
        c.restoreState()

    def drawOn(self, canv, x, y, _sW=0):
        self.width_frame = _sW or TEXT_W
        Flowable.drawOn(self, canv, x, y, _sW)


class Tracked(Flowable):
    """A line of centred, letter-spaced type (fake small caps)."""

    def __init__(self, text, font="EBG", size=8.6, spacing=0.0, leading=None):
        Flowable.__init__(self)
        self.text = text
        self.font = font
        self.size = size
        self.spacing = spacing
        self.height = leading if leading else size * 1.35

    def wrap(self, aw, ah):
        return (aw, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        t = c.beginText()
        t.setFont(self.font, self.size)
        t.setCharSpace(self.spacing)
        w = pdfmetrics.stringWidth(self.text, self.font, self.size)
        w += self.spacing * max(len(self.text) - 1, 0)
        t.setTextOrigin(self.width_frame / 2.0 - w / 2.0, (self.height - self.size) / 2.0 + self.size * 0.18)
        t.textOut(self.text)
        c.drawText(t)
        c.restoreState()

    def drawOn(self, canv, x, y, _sW=0):
        self.width_frame = _sW or TEXT_W
        Flowable.drawOn(self, canv, x, y, _sW)


class TocRow(Flowable):
    """One contents line: label left, folio right, with a hairline leader."""

    def __init__(self, label, folio, indent=0.0, size=9.6, leading=15.5,
                 font="EBG", spacing=0.0, gap_above=0.0):
        Flowable.__init__(self)
        self.label = label
        self.folio = str(folio) if folio else ""
        self.indent = indent
        self.size = size
        self.height = leading + gap_above
        self.font = font
        self.spacing = spacing
        self.lead_top = gap_above

    def wrap(self, aw, ah):
        return (aw, self.height)

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(black)
        base = self.height - self.lead_top - self.size * 0.82
        font = self.font
        size = self.size
        if self.spacing:
            t = c.beginText()
            t.setFont(font, size)
            t.setCharSpace(self.spacing)
            t.setTextOrigin(self.indent, base)
            t.textOut(self.label)
            c.drawText(t)
            lw = (pdfmetrics.stringWidth(self.label, font, size)
                  + self.spacing * max(len(self.label) - 1, 0))
        else:
            c.setFont(font, size)
            c.drawString(self.indent, base, self.label)
            lw = pdfmetrics.stringWidth(self.label, font, size)
        if self.folio:
            fw = pdfmetrics.stringWidth(self.folio, "EBG", size)
            c.setFont("EBG", size)
            c.drawString(self.width_frame - fw, base, self.folio)
            x0 = self.indent + lw + 7
            x1 = self.width_frame - fw - 7
            if x1 > x0:
                c.setLineWidth(0.35)
                c.setStrokeColorRGB(0.45, 0.45, 0.45)
                c.setDash(0.6, 2.6)
                c.line(x0, base + 1.8, x1, base + 1.8)
                c.setDash()
        c.restoreState()

    def drawOn(self, canv, x, y, _sW=0):
        self.width_frame = TEXT_W
        Flowable.drawOn(self, canv, x, y, _sW)


class Marker(Flowable):
    """Zero-height bookmark: records its page and makes a PDF outline entry."""

    def __init__(self, sink, key, title=None, level=0):
        Flowable.__init__(self)
        self.sink = sink
        self.key = key
        self.title = title
        self.level = level

    def wrap(self, aw, ah):
        return (0, 0)

    def draw(self):
        n = self.canv.getPageNumber()
        self.sink[self.key] = n
        if self.title:
            self.canv.bookmarkPage(self.key)
            self.canv.addOutlineEntry(self.title, self.key, level=self.level,
                                      closed=self.level == 0)


class Blank(Flowable):
    def wrap(self, aw, ah):
        return (0, 0)

    def draw(self):
        pass


# ---------------------------------------------------------------- text helpers

QUOTE_RE = re.compile(r'"')


def smart(text):
    """Curly quotes and apostrophes for a book setting."""
    out = []
    for ch in text:
        if ch == '"':
            prev = out[-1] if out else ""
            if prev == "" or prev in " \t\n([—–":
                out.append("\u201c")
            else:
                out.append("\u201d")
        elif ch == "'":
            out.append("\u2019")
        else:
            out.append(ch)
    s = "".join(out)
    return s.replace("...", "\u2026")


def inline(md):
    """Convert a little markdown to reportlab intra-paragraph markup."""
    s = md.strip()
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", s)
    s = smart(s)
    return s


def read_md(name):
    with open(os.path.join(MS, name), encoding="utf-8") as fh:
        raw = fh.read()
    title = pov = None
    body = []
    for block in re.split(r"\n\s*\n", raw):
        b = block.strip()
        if not b:
            continue
        if b.startswith("## "):
            pov = b[3:].strip()
            continue
        if b.startswith("# "):
            title = b[2:].strip()
            continue
        body.append(b)
    return title, pov, body


def chapter_paras(body, st):
    """Paragraphs for a chapter, with a raised versal on the first.

    reportlab lays a paragraph out on its leading alone, so the overshoot of
    the enlarged first letter is not counted and the following paragraph would
    ride up into the last line. A hair of space after the opening paragraph
    puts the box back the right height.
    """
    out = []
    for i, block in enumerate(body):
        txt = inline(block)
        if i == 0:
            out.append(Paragraph(raised_initial(txt), st["body0"]))
            out.append(Spacer(1, VERSAL_GAP))
        else:
            out.append(Paragraph(txt, st["body"]))
    return out


def raised_initial(markup):
    """Enlarge the very first letter -- a versal, not a drop cap."""
    m = re.match(r"(<[a-zA-Z/][^>]*>)*([A-Za-z\u00c0-\u024f])", markup)
    if not m:
        return markup
    i = m.end() - 1
    return (markup[:i] + '<font size="%s">' % VERSAL_SIZE + markup[i]
            + "</font>" + markup[i + 1:])


def draw_tracked(canv, x_center, y, text, font, size, spacing):
    t = canv.beginText()
    t.setFont(font, size)
    t.setCharSpace(spacing)
    w = pdfmetrics.stringWidth(text, font, size) + spacing * max(len(text) - 1, 0)
    t.setTextOrigin(x_center - w / 2.0, y)
    t.textOut(text)
    canv.drawText(t)


# ---------------------------------------------------------------- document


class Book(BaseDocTemplate):
    """Trade-paperback doc: mirrored margins, running heads, centred folios."""

    FRONT_PAGES = 6  # half title, blank, title, colophon, contents, blank

    def __init__(self, filename, plain=(), bare=(), running=None, **kw):
        BaseDocTemplate.__init__(
            self,
            filename,
            pagesize=(PAGE_W, PAGE_H),
            leftMargin=M_IN,
            rightMargin=M_OUT,
            topMargin=M_TOP,
            bottomMargin=M_BOT,
            title="The Gilded Myrtle",
            subject="A Novel of Rome",
            creator="autonovel typeset",
            author="",
            **kw
        )
        self.plain_pages = set(plain)   # folio, no running head
        self.bare_pages = set(bare)     # nothing at all
        self.chapter_running = running or {}
        recto = Frame(M_IN, M_BOT, TEXT_W, TEXT_H, id="recto",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        verso = Frame(M_OUT, M_BOT, TEXT_W, TEXT_H, id="verso",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.frames_pair = {1: recto, 0: verso}
        self.addPageTemplates([
            PageTemplate(id="page", frames=[recto], onPage=self.decorate,
                         pagesize=(PAGE_W, PAGE_H + 0))
        ])

    def handle_pageBegin(self):
        # BaseDocTemplate.handle_pageBegin() increments self.page, so the
        # page being begun is self.page + 1: odd = recto (inner margin left).
        odd = (self.page + 1) % 2 == 1
        self.pageTemplate.frames = [self.frames_pair[1 if odd else 0]]
        BaseDocTemplate.handle_pageBegin(self)

    def decorate(self, canv, doc):
        n = canv.getPageNumber()
        if n <= self.FRONT_PAGES or n in self.bare_pages:
            return
        canv.saveState()
        canv.setFillColor(black)
        if n not in self.plain_pages:
            head = self.chapter_running.get(n) if n % 2 == 1 else TITLE
            if head:
                draw_tracked(canv, PAGE_W / 2.0, PAGE_H - M_TOP + 22,
                             head.upper(), "EBG", 7.8, 1.6)
        canv.setFont("EBG", 9.4)
        canv.drawCentredString(PAGE_W / 2.0, M_BOT - 27,
                               str(n - self.FRONT_PAGES))
        canv.restoreState()


# ---------------------------------------------------------------- build


CHAPTER_TITLES = None  # filled by layout(), keyed ch number -> POV name


def contents(st, pages):
    """Contents page. `pages` maps chapter number -> printed folio."""
    f = [Spacer(1, 0.55 * inch),
         Tracked("CONTENTS", "EBG", 10.5, 4.6, 15),
         Spacer(1, 18)]
    for md_name, first, last in PARTS:
        ptitle, psub, _ = read_md(md_name)
        num = ptitle.lstrip("#").strip().split()[-1]
        f.append(TocRow("PART " + num.upper() + "  \u00b7  " + psub.upper(),
                        pages.get("part" + str(first), ""), size=8.6,
                        leading=16, font="EBG", spacing=1.6, gap_above=4))
        for ch in range(first, last + 1):
            f.append(TocRow("%s  \u00b7  %s" % (NUMERALS[ch], CHAPTER_TITLES[ch]),
                            pages.get(ch, ""), indent=0.16 * inch,
                            size=10.0, leading=13.0, font="EBG-Italic"))
    f.append(PageBreak())
    return f


def front_matter(st, pages=None):
    f = [Spacer(1, 2.55 * inch),
         Tracked("THE GILDED MYRTLE", "EBG", 14.5, 3.0, 20),
         PageBreak(), Blank(), PageBreak(),
         Spacer(1, 1.42 * inch),
         Tracked("THE GILDED", "EBG", 29, 2.4, 37),
         Tracked("MYRTLE", "EBG", 29, 4.6, 37),
         Spacer(1, 18), Rule(), Spacer(1, 18),
         Paragraph(SUBTITLE, st["subtitle"]),
         PageBreak(),
         Spacer(1, 4.5 * inch),
         Paragraph("This is a work of fiction.", st["colophon"]),
         Spacer(1, 12),
         Paragraph("Set in EB Garamond.", st["colophon"]),
         Spacer(1, 12),
         Paragraph("Rome, in the twelfth year of Trajan.", st["colophon"]),
         PageBreak()]
    if pages is not None:
        f += contents(st, pages)
        f += [Blank(), PageBreak()]
    return f


def part_page(md_name, st, sink, key):
    title, sub, _ = read_md(md_name)
    num = title.lstrip("#").strip()
    return [Marker(sink, key, num.title(), 0),
            Spacer(1, 2.3 * inch),
            Tracked(num.upper(), "EBG", 10.5, 5.2, 15),
            Spacer(1, 21),
            Rule(width=1.1 * inch),
            Spacer(1, 23),
            Tracked(sub.upper(), "EBG", 17.5, 3.4, 24),
            PageBreak()]


def chapter(md_name, st, sink, key):
    title, pov, body = read_md(md_name)
    label = title.replace("Chapter", "").strip().upper()
    f = [Marker(sink, key, "Chapter " + label.title(), 1),
         Spacer(1, 1.30 * inch),
         Tracked("CHAPTER " + label, "EBG", 8.8, 2.8, 13),
         Spacer(1, 9),
         Paragraph(pov, st["chaptitle"]),
         Spacer(1, 13),
         Rule(width=1.0 * inch),
         Spacer(1, 27)]
    f += chapter_paras(body, st)
    f.append(PageBreak())
    return f, "Chapter " + title.replace("Chapter", "").strip()


def layout(out_path, blanks=frozenset(), plain=frozenset(), bare=frozenset(),
           running=None, pages=None, offset=None):
    global CHAPTER_TITLES
    register_fonts()
    st = styles()
    sink = {}
    heads = {}
    if CHAPTER_TITLES is None:
        CHAPTER_TITLES = {ch: read_md("ch_%02d.md" % ch)[1] for ch in range(1, 26)}
    doc = Book(out_path, plain=plain, bare=bare, running=running)
    if offset is not None:
        doc.FRONT_PAGES = offset
    story = front_matter(st, pages)
    for idx, (pf, first, last) in enumerate(PARTS):
        if idx in blanks:
            story += [PageBreak()]  # leaves the previous page empty
        story += part_page(pf, st, sink, "part%d" % idx)
        for ch in range(first, last + 1):
            fl, head = chapter("ch_%02d.md" % ch, st, sink, "ch%d" % ch)
            heads["ch%d" % ch] = head
            story += fl
    doc.build(story[:-1])
    return sink, heads


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                          os.path.join(HERE, "..", "the-gilded-myrtle.pdf"))
    tmp = out + ".tmp"

    # Pass 1: no contents page, learn where the parts and chapters fall.
    sink, heads = layout(tmp)
    raw = [sink["part%d" % i] for i in range(len(PARTS))]
    blanks, delta = set(), 0
    for i, p in enumerate(raw):
        if i and (p + delta) % 2 == 0:
            blanks.add(i)
            delta += 1
    sink, heads = layout(tmp, frozenset(blanks))
    part_pages = [sink["part%d" % i] for i in range(len(PARTS))]
    offset = part_pages[0] - 1

    # The contents page (plus its blank verso) is an even number of pages, so
    # inserting it does not move any part title off its recto.
    toc_pages = 2
    pages = {}
    for i, p in enumerate(part_pages):
        pages["part%d" % (i + 1)] = p - offset
    for k, p in sink.items():
        if k.startswith("ch"):
            pages[int(k[2:])] = p - offset

    # Pass 2: with contents; numbers in the contents come from pass 1.
    sink2, heads = layout(tmp, frozenset(blanks), pages=pages, offset=offset + toc_pages)
    part2 = [sink2["part%d" % i] for i in range(len(PARTS))]
    assert all(p % 2 == 1 for p in part2[1:]), part2
    assert part2[0] == part_pages[0] + toc_pages, (part2[0], part_pages[0])
    ch_pages = sorted((p, k) for k, p in sink2.items() if k.startswith("ch"))
    running = {}
    for i, (p, k) in enumerate(ch_pages):
        nxt = ch_pages[i + 1][0] if i + 1 < len(ch_pages) else p + 60
        for pg in range(p, nxt):
            running[pg] = heads[k]

    # Pass 3: final, with running heads, folios and bare part/blank pages.
    bare = set(part2) | {p - 1 for p in part2}
    final = layout(out, frozenset(blanks), frozenset(p for p, _ in ch_pages),
                   frozenset(bare), running, pages=pages, offset=offset + toc_pages)
    for k, p in final[0].items():
        if k.startswith("ch") and pages.get(int(k[2:])) != p - (offset + toc_pages):
            raise SystemExit("contents page numbers drifted at %s" % k)

    if os.path.exists(tmp):
        os.remove(tmp)
    import pymupdf
    n = pymupdf.open(out).page_count
    print("wrote %s (%d pages, text pp. 1-%d, blanks before parts %s)"
          % (out, n, n - offset - toc_pages, sorted(i + 1 for i in blanks)))


if __name__ == "__main__":
    main()
