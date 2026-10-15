---
name: autonovel:next
description: Show state-aware next actions — pending conflicts, regressions, fresh briefs, panel/review staleness, backup status, plus the canonical pipeline next step.
argument-hint: "[--book <short-name>]"
model_tier: light
allowed-tools:
  - bash
reads:
  - project.yaml
  - .autonovel/last-action.json
  - books/{book}/pending_canon.md
  - books/{book}/eval_logs/*.json
  - books/{book}/briefs/ch*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/edit_logs/reader_panel.json
  - books/{book}/edit_logs/review.md
  - books/{book}/typeset/*.pdf
  - books/{book}/preface.md
  - books/{book}/introduction.md
  - books/{book}/chapters/ch_*.md
writes: []
context_mode: none
---

<purpose>
Read-only "where am I" with situational awareness. Inspects current
filesystem state — pending canon conflicts, chapter regressions,
stale reader-panel / Opus review reports, git backup status,
missing title/author/front-matter, stale typeset — and emits a
prioritised action list. The canonical pipeline next step (from
last-action.json) appears at the bottom; situational actions take
precedence over it.

This is the right command after a sweep, after a `/clear`, or
whenever you're unsure. Pure mechanical (no LLM); cheap to call
repeatedly.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Optional `--book <short-name>` restricts
   the scan to one book.

2. Use `bash` to invoke the helper:

   ```
   autonovel _next-actions [--book {book}] --format human
   ```

   The helper inspects:
     - `books/{book}/pending_canon.md` for `## Conflict N` blocks
     - `books/{book}/eval_logs/*.json` for chapter regressions
       (latest score below prior best by ≥0.3)
     - `books/{book}/briefs/ch*.md` mtimes vs the corresponding
       `books/{book}/chapters/ch_*.md` mtimes — a brief newer than
       its chapter is the signal that the brief was written but
       revise hasn't run yet (HIGH)
     - `books/{book}/chapters/ch_NN.summary.md` mtimes vs the
       corresponding `ch_NN.md` mtimes — a summary older than its
       chapter means the rolling-context surface every downstream
       drafter / reviser reads has drifted from the prose (HIGH —
       continuity is data-integrity, not polish; surfaces a
       `/autonovel:summarize-chapter --force` recommendation per
       chapter, or `--all` for multi-chapter sweeps)
     - `books/{book}/edit_logs/reader_panel.json` and
       `review.md` (legacy name `opus_review.md`) mtimes vs
       `books/{book}/chapters/ch_*.md` mtimes (staleness)
     - `books/{book}/typeset/*_latest.pdf` mtime vs
       `books/{book}/chapters/ch_*.md` mtimes (typeset staleness)
     - `project.yaml` for missing `books[].title` / `.author`
     - `books/{book}/preface.md` and `introduction.md` presence
     - `git status` + remote for backup state
     - `.autonovel/last-action.json` for the canonical pipeline
       next step. Past-end-of-book guard: when the canonical line
       says draft chapter `N` and `N` exceeds the count of existing
       chapters by more than 1, it gets demoted to "book appears
       complete — try evaluate --full / typeset" (INFO).

   It returns a prioritised markdown action list (HIGH for data-
   integrity issues like conflicts, regressions, and fresh briefs;
   MEDIUM for review staleness and backup; LOW for polish; then
   the canonical pipeline next step at the bottom).

3. Print the helper's stdout verbatim. Do not editorialise.

4. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files written.
- Output is the helper's markdown verbatim (or `_No actions
  queued. Series is clean._` when nothing applies).
- When `.autonovel/last-action.json` exists, its
  `next_standard_step` appears in the canonical pipeline section
  at the bottom.
</acceptance>
