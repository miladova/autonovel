#!/usr/bin/env python3
"""Typeset THE DIVIDED HARVEST as a 6x9 trade-paperback PDF.

Requires: reportlab.  Usage:  python3 tools/build_pdf.py
"""
import html
import pathlib
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

HERE = pathlib.Path(__file__).resolve().parent.parent
FONTS = HERE / "fonts"
OUT = pathlib.Path(__import__("os").environ.get("OUTPDF", str(HERE / "THE-DIVIDED-HARVEST.pdf")))

PAGE_W, PAGE_H = 6 * inch, 9 * inch
M_TOP, M_BOT = 0.85 * inch, 0.80 * inch
M_OUT, M_IN = 0.80 * inch, 0.95 * inch
TEXT_W = PAGE_W - M_OUT - M_IN
TEXT_H = PAGE_H - M_TOP - M_BOT

import os
CH_LAST_LEAD = float(os.environ.get("CH10_LEAD", "0"))

INK = colors.HexColor("#141210")
MUTED = colors.HexColor("#6a655e")
RULE = colors.HexColor("#a09a90")

for name, file in [("Crimson", "Crimson-Roman.ttf"),
                   ("Crimson-It", "Crimson-Italic.ttf"),
                   ("Crimson-Bd", "Crimson-Bold.ttf"),
                   ("Crimson-BdIt", "Crimson-BoldItalic.ttf"),
                   ("Crimson-Semi", "Crimson-Semibold.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
pdfmetrics.registerFontFamily("Crimson", normal="Crimson", bold="Crimson-Bd",
                              italic="Crimson-It", boldItalic="Crimson-BdIt")

BODY = ParagraphStyle("body", fontName="Crimson", fontSize=10.5, leading=float(os.environ.get("BODY_LEAD","15.3")),
                      alignment=TA_JUSTIFY, firstLineIndent=13, textColor=INK,
                      spaceBefore=0, spaceAfter=0, allowWidows=0, allowOrphans=0)
BODY_FIRST = ParagraphStyle("bodyfirst", parent=BODY, firstLineIndent=0)
QUOTE = ParagraphStyle("quote", parent=BODY, fontSize=9.6, leading=13.6,
                       firstLineIndent=0, leftIndent=16, rightIndent=6,
                       spaceBefore=7, spaceAfter=7, textColor=colors.HexColor("#22201d"))
QUOTE_FIRST = ParagraphStyle("quotefirst", parent=QUOTE, spaceBefore=2)
CH_NUM = ParagraphStyle("chnum", fontName="Crimson-Semi", fontSize=11, leading=14,
                        alignment=TA_CENTER, textColor=MUTED, spaceAfter=10)
CH_TITLE = ParagraphStyle("chtitle", fontName="Crimson-It", fontSize=23, leading=28,
                          alignment=TA_CENTER, textColor=INK, spaceAfter=4)
ORNAMENT = ParagraphStyle("orn", fontName="Crimson", fontSize=10, leading=float(os.environ.get("BODY_LEAD","15.3")),
                          alignment=TA_CENTER, textColor=MUTED,
                          spaceBefore=8, spaceAfter=8)
HEAD = ParagraphStyle("head", fontName="Crimson", fontSize=7.6, leading=10,
                      alignment=TA_CENTER, textColor=MUTED)
TITLE_BIG = ParagraphStyle("title", fontName="Crimson-Semi", fontSize=27, leading=32,
                           alignment=TA_CENTER, textColor=INK, spaceAfter=10)
SUBTITLE = ParagraphStyle("sub", fontName="Crimson-It", fontSize=12.5, leading=17,
                          alignment=TA_CENTER, textColor=colors.HexColor("#3a3733"))
HALF = ParagraphStyle("half", fontName="Crimson-Semi", fontSize=15, leading=19,
                      alignment=TA_CENTER, textColor=INK)
SMALL = ParagraphStyle("small", fontName="Crimson", fontSize=8.6, leading=12.4,
                       alignment=TA_LEFT, textColor=colors.HexColor("#3a3733"))
TOC_LINE = ParagraphStyle("toc", fontName="Crimson", fontSize=10, leading=17,
                          textColor=INK)
TOC_NUM = ParagraphStyle("tocnum", parent=TOC_LINE, alignment=2)
TOC_HEAD = ParagraphStyle("tochead", fontName="Crimson-Semi", fontSize=11, leading=16,
                          alignment=TA_CENTER, textColor=MUTED, spaceAfter=18)


def inline(text):
    """Markdown-ish inline markup -> reportlab mini-HTML."""
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", t)
    return t


def draw_tracked(c, cx, y, text, size, track, font="Crimson"):
    widths = [pdfmetrics.stringWidth(ch, font, size) for ch in text]
    total = sum(widths) + track * max(len(text) - 1, 0)
    x = cx - total / 2
    c.setFont(font, size)
    for ch, w in zip(text, widths):
        c.drawString(x, y, ch)
        x += w + track


class Rule(Flowable):
    def __init__(self, width=28, thickness=0.6, color=RULE, space=12):
        super().__init__()
        self.width_, self.thickness, self.color = width, thickness, color
        self.height = space

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness)
        c.line((PAGE_W - 2 * M_IN) / 2 - self.width_ / 2, self.height * 0.45,
               (PAGE_W - 2 * M_IN) / 2 + self.width_ / 2, self.height * 0.45)


class Tracked(Flowable):
    """A line of letterspaced text, centred in the frame."""

    def __init__(self, text, size=11, track=2.2, font="Crimson-Semi",
                 color=MUTED, before=0, after=0):
        super().__init__()
        self.text, self.size, self.track = text, size, track
        self.font, self.color = font, color
        self.before, self.after = before, after
        self.width = 0

    def wrap(self, aw, ah):
        self.width = aw
        widths = [pdfmetrics.stringWidth(c, self.font, self.size) for c in self.text]
        self.total = sum(widths) + self.track * max(len(self.text) - 1, 0)
        self.height = self.size * 1.25 + self.before + self.after
        return (aw, self.height)

    def draw(self):
        c = self.canv
        c.setFont(self.font, self.size)
        c.setFillColor(self.color)
        x = (self.width - self.total) / 2
        y = self.after + self.size * 0.25
        for ch in self.text:
            c.drawString(x, y, ch)
            x += pdfmetrics.stringWidth(ch, self.font, self.size) + self.track


class ChapterMarker(Paragraph):
    """Zero-height flowable carrying chapter metadata for pass 1."""

    def __init__(self, word, title):
        super().__init__("", BODY)
        self.chapter = (word, title)
        self.height = 0
        self.spaceBefore = 0
        self.spaceAfter = 0

    def wrap(self, aw, ah):
        return (0, 0)

    def draw(self):
        pass


def spaced(s, size=5.0):
    """Fake letterspacing: join characters with a small-font space."""
    sep = f'<font size="{size}"> </font>'
    return sep.join(list(s))


def parse(chapter_paths):
    chapters = []
    for path in chapter_paths:
        lines = path.read_text().split("\n")
        word = title = None
        blocks, buf = [], []

        def flush():
            if buf:
                blocks.append(("p", " ".join(buf).strip()))
                buf.clear()

        i = 0
        while i < len(lines):
            ln = lines[i].strip()
            if ln.startswith("# ") and word is None:
                word = ln[2:].strip()
            elif ln.startswith("## ") and title is None:
                title = ln[3:].strip()
            elif ln == "":
                flush()
            elif ln == "***":
                flush()
                blocks.append(("break", ""))
            elif ln.startswith(">"):
                flush()
                q = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    q.append(lines[i].strip().lstrip(">").strip())
                    i += 1
                blocks.append(("q", "\n".join([x for x in q])))
                continue
            else:
                buf.append(ln)
            i += 1
        flush()
        chapters.append({"word": word, "title": title, "blocks": blocks})
    return chapters


def quote_table(text):
    paras = [p for p in text.split("\n") if p.strip()]
    rows = [[Paragraph(inline(p), QUOTE_FIRST if n == 0 else QUOTE)]
            for n, p in enumerate(paras)]
    t = Table(rows, colWidths=[TEXT_W - 22])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build(chapters, chapter_pages=None, markers=None):
    """chapter_pages: title -> printed page (pass 2). markers: [(page, title)] from pass 1."""
    class BookDoc(BaseDocTemplate):
        """Alternates recto/verso so margins mirror."""

        def handle_pageBegin(self):
            self.pageTemplate = self.pageTemplates[0 if self.page % 2 == 0 else 1]
            BaseDocTemplate.handle_pageBegin(self)

    doc = BookDoc(str(OUT), pagesize=(PAGE_W, PAGE_H),
                          leftMargin=M_OUT, rightMargin=M_IN,
                          topMargin=M_TOP, bottomMargin=M_BOT,
                          title="The Divided Harvest",
                          author="Arena Agent",
                          subject="A novella of Warsaw, 1958")

    verso_frame = Frame(M_OUT, M_BOT, TEXT_W, TEXT_H, id="verso",
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    recto_frame = Frame(M_IN, M_BOT, TEXT_W, TEXT_H, id="recto",
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    state = {"chapter": None, "pages": {}, "openers": set(), "markers": []}
    opener_pages = {pg for pg, _ in (markers or [])}

    def chapter_for(page):
        title = None
        for pg, name in (markers or []):
            if pg <= page:
                title = name
        return title

    def decorate(canvas, d, template):
        page = d.page
        if page <= 4:
            return
        if page in opener_pages:
            return
        shown = page - 4
        canvas.saveState()
        canvas.setFont("Crimson", 8.6)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W / 2, 0.52 * inch, str(shown))
        ch = chapter_for(page) if markers else state["chapter"]
        if ch:
            left = template.id == "verso"
            label = ("THE DIVIDED HARVEST" if left else ch.upper())
            canvas.setFont("Crimson", 7.4)
            canvas.setFillColor(MUTED)
            draw_tracked(canvas, PAGE_W / 2, PAGE_H - 0.58 * inch, label, 7.4, 1.15)
        canvas.restoreState()

    doc.addPageTemplates([
        PageTemplate(id="recto", frames=[recto_frame],
                     onPage=lambda c, d: decorate(c, d, doc.pageTemplates[0])),
        PageTemplate(id="verso", frames=[verso_frame],
                     onPage=lambda c, d: decorate(c, d, doc.pageTemplates[1])),
    ])

    def after(flowable):
        if isinstance(flowable, ChapterMarker):
            state["pages"][flowable.chapter[1]] = doc.page
            state["chapter"] = flowable.chapter[1]
            state["openers"].add(doc.page)
            state["markers"].append((doc.page, flowable.chapter[1]))

    doc.afterFlowable = after

    story = []

    # --- front matter -----------------------------------------------------
    story += [Spacer(1, 2.1 * inch),
              Tracked("THE DIVIDED HARVEST", size=15, track=3.2, color=INK),
              Spacer(1, 0.5 * inch),
              Paragraph("A NOVELLA", ParagraphStyle("x", parent=HEAD, fontSize=8.6)),
              NextPageTemplate("recto"), PageBreak()]

    story += [Spacer(1, 1.45 * inch),
              Paragraph("The<br/>Divided<br/>Harvest", TITLE_BIG),
              Spacer(1, 0.30 * inch),
              Rule(46), Spacer(1, 0.18 * inch),
              Paragraph("A Novella of Warsaw, 1958", SUBTITLE),
              Spacer(1, 1.5 * inch),
              NextPageTemplate("verso"), PageBreak()]

    note = ("This is a work of fiction. The Poland of 1958 — Gomułka's \u201cPolish road to socialism,\u201d "
            "Cardinal Wyszyński two years out of internment, Warsaw rising from its ruins under the shadow "
            "of the Palace of Culture — is rendered as faithfully as the story allows. The Office for "
            "Religious Affairs, the Security Service's Department IV, the 1949 decree of the Holy Office "
            "on Catholics who joined the Communist Party, and the preparations for the Millennium of 1966 "
            "were real. The people are invented; the world they move through was not.")
    story += [Spacer(1, 1.2 * inch),
              Paragraph("THE DIVIDED HARVEST", ParagraphStyle("cp", parent=HEAD, fontSize=7.6, alignment=0)),
              Spacer(1, 6),
              Paragraph(note, SMALL),
              Spacer(1, 14),
              Paragraph("Set in Crimson. Ten chapters. Approximately 43,000 words.", SMALL),
              NextPageTemplate("recto"), PageBreak()]

    # --- contents ---------------------------------------------------------
    story += [Spacer(1, 1.0 * inch), Paragraph("CONTENTS", TOC_HEAD)]
    rows = []
    for n, ch in enumerate(chapters, 1):
        pg = str(chapter_pages.get(ch["title"], "")) if chapter_pages else ""
        rows.append([Paragraph(f"{n}.&nbsp;&nbsp;{ch['title']}", TOC_LINE),
                     Paragraph(pg, TOC_NUM)])
    toc_tbl = Table(rows, colWidths=[TEXT_W - 40, 40])
    toc_tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    story += [toc_tbl, NextPageTemplate("recto"), PageBreak()]

    # --- chapters ---------------------------------------------------------
    for n, ch in enumerate(chapters):
        if n:
            story.append(PageBreak())
        story += [ChapterMarker(ch["word"], ch["title"]),
                  Spacer(1, 0.85 * inch),
                  Tracked(ch["word"].upper(), size=11, track=3.0, after=10),
                  Paragraph(ch["title"], CH_TITLE),
                  Rule(30, space=26),
                  Spacer(1, 0.22 * inch)]
        first_para = True
        for kind_i, (kind, text) in enumerate(ch["blocks"]):
            if kind == "break":
                story.append(Paragraph("*&nbsp;&nbsp;*&nbsp;&nbsp;*", ORNAMENT))
                first_para = True
            elif kind == "q":
                story += [Spacer(1, 7), quote_table(text), Spacer(1, 5)]
                first_para = False
            else:
                st = BODY if not first_para else BODY_FIRST
                if n == len(chapters) - 1 and CH_LAST_LEAD:
                    st = ParagraphStyle("bodylast", parent=st, leading=CH_LAST_LEAD)
                para = Paragraph(inline(text), st)
                last_in_chapter = (kind_i == len(ch["blocks"]) - 1)
                if last_in_chapter:
                    story.append(KeepTogether([para]))
                else:
                    story.append(para)
                first_para = False

    story += [Spacer(1, 14), Rule(22, space=22)]

    # --- colophon ---------------------------------------------------------
    story += [PageBreak(), Spacer(1, 3.0 * inch),
              Paragraph("END", ParagraphStyle("e", parent=HEAD, fontSize=8)),
              Spacer(1, 28), Rule(24, space=22),
              Spacer(1, 10),
              Paragraph("Brzozówka is a village that does not exist.<br/>"
                        "Everything around it does.", ParagraphStyle(
                            "c", parent=SUBTITLE, fontSize=10.5))]

    doc.build(story)
    return state


def main():
    paths = sorted((HERE / "chapters").glob("*.md"))
    chapters = parse(paths)
    first = build(chapters)                     # pass 1: collect page numbers
    pages = {k: v - 4 for k, v in first["pages"].items()}
    build(chapters, chapter_pages=pages, markers=first["markers"])  # pass 2
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
