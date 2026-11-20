# The Tuning

A short story. Warsaw, May 1943.

> Marianna Frontczak, forty-two, is taken through the gate of a
> requisitioned villa to tune a piano. The officer billeted there turns out
> to be the man she has not seen in nineteen years.

5,368 words. Delivered as a typeset PDF (`the-tuning.pdf`, 20 pages, 6 × 9 in),
with the German and Polish carried line by line in English underneath.

## Files

| File | What it is |
|---|---|
| `the-tuning.md` | The manuscript. Plain Markdown: `#` title, blank-line paragraphs, `* * *` for scene breaks, `*emphasis*` for italics. |
| `the-tuning.pdf` | The formatted booklet: title page, colophon, running heads, drop cap, scene ornaments, notes. |
| `build_pdf.py` | Typesetter. Reads the Markdown, writes the PDF with ReportLab. |
| `add_glosses.py` | Inserts the translations into the manuscript (idempotent; run once). |
| `fetch_fonts.py` | Pulls Crimson Text (SIL OFL) from `google/fonts` through the GitHub API. |
| `fonts/` | Vendored Crimson Text faces plus `OFL.txt`. |

## Rebuild

```bash
python build_pdf.py            # -> the-tuning.pdf
python build_pdf.py -o out.pdf # elsewhere
```

Requires `reportlab` and `pyphen` (`pip install reportlab pyphen`). Pyphen is
optional: without it the pages simply set looser, since justified text then
has no hyphenation at all.

## Reading the German

Readers should not have to turn to the back for a line of dialogue, so every
German and Polish run carries its plain English immediately beside it, in the
same small grey italic:

- **A speech** (or a speech with a said-tag) gets the translation on its own
  line, tucked under it: `"Bleiben Sie."` then *Stay*.
- **German inside narration** gets the English in brackets right where it
  falls: `the word Wagen (car)`, `"Ich habe dir geschrieben," she said. (I
  wrote to you.)` The gloss goes behind the said-tag, never between the
  quotation and its attribution.

In the Markdown that is `{{English}}` at the end of a paragraph for the first
case and `[[English]]` inline for the second; `add_glosses.py` writes both.
Short brackets are set unbreakable so a translation never splits across two
lines, while the long ones are allowed to break.

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
- **`rl_config.hyphenationMinWordLength` is a decoy.** ReportLab reads it at
  import, so setting it at build time changes nothing and two-letter
  fragments ("Pi-ano", "be-fore") survive. The minimums have to be baked into
  a Pyphen callable and handed to the style as `hyphenationLang`, which is
  where ReportLab looks first.
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
