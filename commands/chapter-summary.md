---
name: autonovel:chapter-summary
description: Print a one-line-per-chapter overview — date, POV, score and lowest dimension, cast, plot — for the active book.
argument-hint: "[--book <short-name>] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/eval_logs/*.json
writes: []
context_mode: book
---

<purpose>
Surface the per-chapter index a writer reaches for when they ask
"which chapters happen in Venice when Jakob was there?" or "which
chapters has Lucia in them?" or "which chapter dropped to a 6.5
again?". Pulls already-structured fields from chapter frontmatter
(`pov`, `story_time`, `word_count`), the per-chapter summary file
(`Plot`, `Cast on stage`, `Story time`), and the latest eval log
(`overall_score`, and the lowest-scoring dimension beside it, so a
dimension that fails is not hidden by the chapter's mean) and renders
one row per drafted chapter as a markdown table.

Pure mechanical. No LLM. Light tier — runs in seconds, costs
nothing, safe to call repeatedly.

Use cases:
- "Which chapters fall in 1521-12 to 1522-02?" → scan the Date
  column.
- "Where does Niccolò appear?" → scan the Cast column.
- "Which chapter scored lowest?" → scan the Score column; "what
  is weakest in each chapter?" → the Low column (`place 6.9`).
- "Plain overview before I start a revision pass" → just read
  the table top to bottom.

For deeper filtering ("set in Venice"), pipe the markdown table
into your terminal's text reader and visually scan the Plot
column — that's the right tool for substring filtering of
structured output.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. `--format markdown|json` (default `markdown`); use
   `json` when piping into another tool.

2. Use the `Bash` tool to call the housekeeping helper:

   ```
   autonovel mechanical chapter-summary books/{book} --format <format>
   ```

   The helper reads every `ch_NN.md` under
   `books/{book}/chapters/`, parses its frontmatter and the
   sibling `ch_NN.summary.md` (when present), looks up the
   latest `overall_score` and lowest dimension from
   `books/{book}/eval_logs/`, and
   emits the table (or JSON when `--format json`).

3. Print the helper's stdout verbatim. Do not editorialise.

4. After the table, add a one-line tip when the table contains
   ≥1 chapter without a summary file, since those rows show `—`
   in the Cast and Plot columns:

   ```
   Tip: chapter(s) <N,M> have no summary on disk. Run
        /autonovel:summarize-chapter <N> --book {book}
        to backfill (one per chapter; cheap).
   ```

   When every chapter has a summary, omit the tip.
</workflow>

<acceptance>
- The output is either a markdown table or a JSON object,
  depending on `--format`.
- The markdown table has one row per drafted `ch_NN.md` under
  `books/{book}/chapters/`, in chapter-number order.
- Chapters without a `ch_NN.summary.md` still appear in the
  table (with `—` in cast / plot columns) — never silently
  excluded.
- Chapters without an eval log still appear (with `—` in the
  Score and Low columns).
</acceptance>
