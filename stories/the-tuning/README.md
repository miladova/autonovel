# The Tuning

A short story. Warsaw, May 1943.

> Marianna Frontczak, forty-two, is taken through the gate of a
> requisitioned villa to tune a piano. The officer billeted there turns out
> to be the man she has not seen in nineteen years.

5,176 words. Delivered as a typeset PDF (`the-tuning.pdf`, 19 pages, 6 × 9 in).

## Files

| File | What it is |
|---|---|
| `the-tuning.md` | The manuscript. Plain Markdown: `#` title, blank-line paragraphs, `* * *` for scene breaks, `*emphasis*` for italics. |
| `the-tuning.pdf` | The formatted booklet: title page, colophon, running heads, drop cap, scene ornaments, notes. |
| `build_pdf.py` | Typesetter. Reads the Markdown, writes the PDF with ReportLab. |
| `fetch_fonts.py` | Pulls Crimson Text (SIL OFL) from `google/fonts` through the GitHub API. |
| `fonts/` | Vendored Crimson Text faces plus `OFL.txt`. |

## Rebuild

```bash
python build_pdf.py            # -> the-tuning.pdf
python build_pdf.py -o out.pdf # elsewhere
```

Requires `reportlab` and `pyphen` (`pip install reportlab pyphen`). Pyphen is
optional: without it the pages simply set looser, since justified text then
has no hyphenation.

## Typography

Crimson Text at 11.4/16.1 on a 4.4 in measure, justified. Symmetric 0.8 in
margins (a screen deliverable, not a bound book, so no gutter). Running heads
alternate *The Tuning* / *Warsaw, 1943*; the folio starts at 1 on the first
story page. A dropped initial opens the story, and the three scene breaks take
a three-dot ornament. The German and Polish are glossed at the back.

Two things worth knowing if you edit the builder:

- **No thin spaces.** Crimson Text has no U+2009, so `stringWidth` returns
  zero advance for it. Letterspacing built from thin spaces collapses —
  "THE TUNING" sets as "THETUNING", or over itself. `draw_tracked` measures
  and draws character by character instead.
- **No inline display initials.** An inline `<font size="30">` makes ReportLab
  advance the first line by more than the style's leading while still
  reporting the old paragraph height, so the next paragraph rides up into the
  text. The initial is drawn as a glyph in a fitted table instead, with its
  baseline pinned to the third line (`Versal.RISE`).

## On the prose

The manuscript scores 0.0 on the pipeline's own slop penalty
(`autonovel mechanical slop the-tuning.md`): no banned-word hits, no fiction
AI tells, no telling violations, 0.19 em dashes per thousand words, sentence
length CV 0.97.
