#!/usr/bin/env python
"""Typeset books/<book>/chapters/ch_NN.md into a single trade-paperback PDF.

Usage: python typeset/build_pdf.py <book-dir> <out.pdf>
Markdown subset: '# Title' (chapter title, first line after frontmatter),
'* * *' scene breaks, *italic*, blank-line paragraphs.
"""
import re
import sys
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer)
from reportlab.lib.fonts import addMapping

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"

for name, fn in [("Garamond", "EBGaramond-Regular.ttf"),
                 ("Garamond-Italic", "EBGaramond-Italic.ttf"),
                 ("Garamond-Bold", "EBGaramond-Bold.ttf"),
                 ("Garamond-BoldItalic", "EBGaramond-BoldItalic.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONTS / fn)))
addMapping("Garamond", 0, 0, "Garamond")
addMapping("Garamond", 0, 1, "Garamond-Italic")
addMapping("Garamond", 1, 0, "Garamond-Bold")
addMapping("Garamond", 1, 1, "Garamond-BoldItalic")

PAGE = (5.5 * inch, 8.5 * inch)
W, H = PAGE
M_IN, M_OUT, M_TOP, M_BOT = 0.72 * inch, 0.72 * inch, 0.75 * inch, 0.8 * inch

body = ParagraphStyle("body", fontName="Garamond", fontSize=11, leading=15.2,
                      alignment=TA_JUSTIFY, firstLineIndent=16, spaceAfter=0)
body_first = ParagraphStyle("body_first", parent=body, firstLineIndent=0)
chap_num = ParagraphStyle("chap_num", fontName="Garamond", fontSize=11,
                          leading=14, alignment=TA_CENTER, textColor="#444444",
                          spaceBefore=90, spaceAfter=6)
chap_title = ParagraphStyle("chap_title", fontName="Garamond-Italic",
                            fontSize=20, leading=24, alignment=TA_CENTER,
                            spaceAfter=8)
dateline = ParagraphStyle("dateline", fontName="Garamond", fontSize=9.5,
                          leading=12, alignment=TA_CENTER, textColor="#555555",
                          spaceAfter=36)
scene_break = ParagraphStyle("scene", fontName="Garamond", fontSize=11,
                             leading=14, alignment=TA_CENTER, spaceBefore=10,
                             spaceAfter=10)
title_main = ParagraphStyle("tm", fontName="Garamond", fontSize=30, leading=36,
                            alignment=TA_CENTER, spaceBefore=170)
title_sub = ParagraphStyle("ts", fontName="Garamond-Italic", fontSize=13,
                           leading=18, alignment=TA_CENTER, spaceBefore=14)
title_author = ParagraphStyle("ta", fontName="Garamond", fontSize=14,
                              leading=18, alignment=TA_CENTER, spaceBefore=120)
small_c = ParagraphStyle("sc", fontName="Garamond", fontSize=9, leading=12,
                         alignment=TA_CENTER, textColor="#555555")
toc_line = ParagraphStyle("toc", fontName="Garamond", fontSize=11, leading=17)


def inline(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    s = s.replace("--", "\u2014")
    s = re.sub(r'(^|[\s(\[\u2014>])"', "\\1\u201c", s)
    s = s.replace('"', "\u201d")
    s = re.sub(r"(^|[\s(\[\u2014>\u201c])'", "\\1\u2018", s)
    s = s.replace("'", "\u2019")
    return s


def parse_chapter(path: Path):
    text = path.read_text(encoding="utf-8")
    fm = {}
    if text.startswith("---"):
        _, front, text = text.split("---", 2)
        for line in front.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
    lines = text.strip().splitlines()
    title = ""
    if lines and lines[0].startswith("# "):
        title = lines.pop(0)[2:].strip()
    paras, buf = [], []
    for ln in lines + [""]:
        if ln.strip() == "":
            if buf:
                paras.append(" ".join(buf).strip())
                buf = []
        elif ln.strip() in ("* * *", "***", "---"):
            if buf:
                paras.append(" ".join(buf).strip())
                buf = []
            paras.append("\x00BREAK")
        else:
            buf.append(ln.strip())
    return fm, title, paras


def chapter_flow(num, fm, title, paras):
    out = [Paragraph(f"{num}", chap_num), Paragraph(inline(title), chap_title)]
    if fm.get("dateline"):
        out.append(Paragraph(inline(fm["dateline"]), dateline))
    else:
        out.append(Spacer(1, 30))
    first = True
    for p in paras:
        if p == "\x00BREAK":
            out.append(Paragraph("\u2042", scene_break))
            first = True
            continue
        out.append(Paragraph(inline(p), body_first if first else body))
        first = False
    return out


class Doc(BaseDocTemplate):
    def __init__(self, fn, meta, **kw):
        super().__init__(fn, pagesize=PAGE, **kw)
        self.meta = meta
        self.chapter_title = ""
        odd = Frame(M_IN, M_BOT, W - M_IN - M_OUT, H - M_TOP - M_BOT, id="odd",
                    leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="plain", frames=[odd], onPage=self._blank),
            PageTemplate(id="text", frames=[odd], onPage=self._running,
                         autoNextPageTemplate="text"),
        ])

    def _blank(self, canv, doc):
        pass

    def _running(self, canv, doc):
        canv.saveState()
        canv.setFont("Garamond", 8.5)
        canv.setFillColor("#555555")
        n = doc.page
        if n % 2 == 0:
            canv.drawString(M_OUT, H - 0.5 * inch, self.meta["title"].upper())
            canv.drawString(M_OUT, 0.5 * inch, str(n))
        else:
            canv.drawRightString(W - M_OUT, H - 0.5 * inch,
                                 self.chapter_title.upper())
            canv.drawRightString(W - M_OUT, 0.5 * inch, str(n))
        canv.restoreState()

    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name == "chap_title":
            self.chapter_title = re.sub("<[^>]+>", "", fl.text)
            self.notify("TOCEntry", (0, self.chapter_title, self.page))


def build(book_dir: Path, out: Path):
    chapters = sorted(book_dir.glob("chapters/ch_*.md"))
    meta = {"title": "The Freedman's Children",
            "series": "Rome at the Summit \u2014 Book One",
            "author": "autonovel"}
    story = []
    story.append(Paragraph(meta["title"].upper(), title_main))
    story.append(Paragraph(meta["series"], title_sub))
    story.append(Paragraph("A Novel", title_author))
    story.append(PageBreak())
    story.append(Spacer(1, 400))
    story.append(Paragraph("Mature content: adult themes, sex, violence, "
                           "strong language. Not for readers under 18.", small_c))
    story.append(Spacer(1, 8))
    story.append(Paragraph("This is a work of fiction. Historical persons appear "
                           "within the record; all else is invented.", small_c))
    story.append(NextPageTemplate("text"))
    story.append(PageBreak())
    for path in chapters:
        fm, title, paras = parse_chapter(path)
        num = int(fm.get("chapter", re.findall(r"\d+", path.stem)[0]))
        story.extend(chapter_flow(num, fm, title, paras))
        story.append(PageBreak())
    doc = Doc(str(out), meta, title=meta["title"], author=meta["author"])
    doc.build(story)
    print(f"wrote {out} ({len(chapters)} chapters)")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
