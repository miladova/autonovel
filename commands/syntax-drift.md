---
name: autonovel:syntax-drift
description: Per-chapter Flesch-Kincaid grade vs voice/seed baseline. Catches modern syntax in period-correct vocabulary.
argument-hint: "[--book <short-name>] [--threshold <float>] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - books/{book}/voice.md
  - books/{book}/seed.txt
  - books/{book}/chapters/ch_*.md
writes: []
context_mode: book
---

<purpose>
Catches the bug class where period-correct vocabulary masks
modern syntax. The literal `period-bans` scanner flags
*words*; this command flags *sentence shape*. Pure mechanics —
the Flesch-Kincaid grade formula is well-defined math:

```
FK_grade = 0.39 × (words / sentences)
         + 11.8 × (syllables / words)
         - 15.59
```

Higher FK grade = harder reading = longer sentences with more
syllables-per-word. Period fiction often runs 9-12; modern
commercial fiction runs 5-8. The *delta* between a chapter and
the book's voice baseline matters more than the absolute number.

Baseline source (in priority order):
1. A band declared in `books/{book}/voice.md` on one line,
   `FK grade band: 5–8`. Its midpoint is the baseline and its
   half-width the tolerance; `--threshold` is ignored. This is
   the authoritative read on intended register (modern commercial
   fiction sits around grade 5–8; literary and period registers
   higher).
2. `books/{book}/seed.txt` — the user's pitch, written in the
   target voice.
3. The voice file's own prose. Weak: a voice file is a rules
   document, not a sample of the register, and the output says so
   when this fallback is used. Declare a band instead.
4. Median of chapter grades (when none of the above yields a
   usable baseline AND there are ≥3 chapters).

Chapters outside the tolerance (default `--threshold` 1.0 grade
level when no band is declared) get flagged. For the fuller
register picture — narration and dialogue graded separately,
contraction ratio, utterance length, lines that explain to the
listener — use `autonovel mechanical register` (`/autonovel:evaluate`
runs it and scores the `register` dimension). The LLM judge does the
actual scoring; this command surfaces the candidates.

**Review list, not a quality gate.** Real explanations for a
drifting chapter include intentional register shift (action
sequence, dialogue-heavy chapter, modernism homage) as well as
modern-syntax leakage. The user (or LLM judge) decides which.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. `--threshold <float>` (default 1.0).
   `--format markdown|json`.

2. Use the `Bash` tool to call the housekeeping helper. The
   helper reads `books/{book}/voice.md` (preferred baseline),
   `books/{book}/seed.txt` (fallback), and every `ch_NN.md`
   under `books/{book}/chapters/`:

   ```
   autonovel mechanical syntax-drift books/{book} --threshold {T} --format <format>
   ```

3. Print the helper's stdout verbatim. Do not editorialise.

4. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- The output begins with `# Period syntax drift — <book>` and
  names the resolved baseline + source.
- A per-chapter table lists FK grade, delta-vs-baseline, and a
  flag when the absolute delta exceeds `--threshold`.
- When the baseline cannot be resolved (no voice.md / seed.txt
  AND fewer than 3 chapters), the output explains why and
  exits 0 cleanly.
- When `--format json`, every chapter and flag from the
  markdown is recoverable from the JSON payload.
</acceptance>
