---
name: autonovel:series-arc
description: Series-arc score across ≥2 books — completion, cross-book cast, story-time discipline, unresolved threads, composite arc score.
argument-hint: "[--threshold <float>] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - project.yaml
  - books/*/chapters/ch_*.md
  - books/*/chapters/ch_*.summary.md
  - books/*/eval_logs/*.json
writes: []
context_mode: none
---

<purpose>
When a series declares ≥2 books, the dashboard needs a view that
crosses book boundaries:

- **Story-time monotonicity**: chapter `story_time` values
  should generally read forward across books. Backwards jumps
  are legitimate for flashback chapters but the *count* and
  *magnitude* are signal — five backwards jumps in three books
  is usually a structure problem. Two books whose `project.yaml`
  `story_time_range`s overlap (a rewrite of the same story, a
  parallel POV) are expected to reset the clock at the book
  boundary; that reset is reported under `overlapping_books` and
  NOT counted as a backwards jump.
- **Recurring cast**: characters appearing in ≥2 books are the
  high-leverage continuity targets; revise should prioritise
  them.
- **Thread payoff**: chapters whose summary `Threads opened:`
  field names a thread that never matches a later chapter's
  `Threads closed:` field. Per-book threads are a craft
  question; cross-book unresolved threads are usually a
  spent-arc-budget problem.
- **Per-book completion**: fraction of each book's chapters
  with a summary, with an eval log, with a score above
  threshold. Multi-book series often have one book stalling
  — surfacing this guides where revise/brief effort lands
  next.

A composite **arc score** (0–10) blends per-book completion,
fraction-above-threshold, story-time discipline, and unresolved-
thread fraction.

Pure mechanical. No LLM. The LLM-side scoring of arc *quality*
(does the payoff feel earned?) is an LLM-judge upgrade in the
shape of `/autonovel:review`; this command provides the
structural scoreboard the LLM and the human read.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Optional `--threshold <float>` (default
   7.0; pass the project's `chapter_threshold` from
   `project.yaml :: defaults` when set per-series).
   `--format markdown|json` (default `markdown`).

2. Use the `Bash` tool to call the housekeeping helper. The
   helper reads every book's chapter prose under `chapters/`,
   sibling `*.summary.md` files for the cast/threads, and
   per-book `eval_logs/*.json` for the score column:

   ```
   autonovel mechanical series-arc . --threshold {T} --format <format>
   ```

3. Print the helper's stdout verbatim. Do not editorialise.

4. The output begins with the composite arc score on its own
   line; below that is a per-book completion table and any of
   four optional sections (cross-book cast, backwards story-
   time jumps, unresolved threads). When the series has only
   one book, the helper notes that scoring reduces to per-book
   completion.

5. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- Markdown output begins with `# Series arc score`, names the
  composite score, and includes a per-book completion table.
- When ≥2 books share a cast member, a `## Cross-book cast`
  block lists each shared character with the books they appear
  in.
- When any chapter's `story_time` regresses from the prior
  chapter's, a `## Backwards story-time jumps` block lists each
  jump (legitimate for intentional flashbacks; sanity check).
- When threads opened in one chapter have no later close, an
  `## Unresolved threads` block lists each one (substring match
  in either direction).
- When `--format json`, every count from the markdown output is
  recoverable from the JSON.
</acceptance>
