---
name: autonovel:apply-cuts
description: Deterministically remove quotes flagged by adversarial-edit.
argument-hint: "<chapter-number> --book <short-name> [--types OVER-EXPLAIN REDUNDANT] [--min-fat N] [--dry-run]"
model_tier: light
allowed-tools:
  - file_read
  - bash
reads:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/edit_logs/ch{chapter:02d}_cuts.json
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
context_mode: book
---

<purpose>
Apply the cuts produced by `/autonovel:adversarial-edit`. This is NOT an
LLM operation — string removal is deterministic via
`autonovel mechanical apply-cuts`. The command's job is to
parse arguments, invoke the CLI, and summarise results. The Bells
production learned that OVER-EXPLAIN (~32%) and REDUNDANT (~26%)
dominate cuts; default to those two types unless the user says otherwise.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   Optional: `--types TYPE [TYPE...]` (default: `OVER-EXPLAIN REDUNDANT`),
   `--min-fat N` (default 0), `--dry-run`. Missing required args are a
   usage error — print a one-line reminder and stop.

2. Use `file_read` on
   `books/{book}/edit_logs/ch{chapter:02d}_cuts.json` to confirm it
   exists. If missing, surface: "no cuts file — run
   `/autonovel:adversarial-edit {chapter} --book {book}` first".

3. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md` only to
   confirm the target exists. Do not modify it from within the command
   body; the `bash` step does that.

4. Use `bash` to invoke the apply-cuts subprocess. Call it as a
   **single-line** command (bash parses newlines as statement
   separators, so a multi-line invocation will silently run the first
   fragment and then try to execute the path arguments as programs).
   The exact shape is:

   ```
   autonovel mechanical apply-cuts books/{book}/chapters/ch_{chapter}.md books/{book}/edit_logs/ch{chapter:02d}_cuts.json --types <TYPE1> [<TYPE2> ...] [--min-fat N] [--dry-run]
   ```

   Substitute the user's types list; omit `--min-fat` and `--dry-run`
   if the user didn't pass them. Do NOT add `--dry-run` on your own —
   the user expects a real run unless they explicitly asked for a dry
   run. The subprocess writes the chapter file back in place unless
   `--dry-run`. Parse its JSON output on stdout.

   A `REWRITE` with a replacement is applied as a replacement. A
   `MISPLACED` cut or a `MOVE` action is never applied, whatever
   `--types` says: the helper lists it under `held`. It is content the
   book's genre guide protects (in historical fiction, the period),
   badly placed; `/autonovel:brief` carries it as a move.

5. Print a one-screen summary: words removed, cuts applied (and how many
   were rewrites), held for the brief (`held`, quoted), cuts skipped
   (with reasons), and any cuts that failed to match (these are the
   ones the adversarial-editor's quote was imprecise about — flag them
   so the user can hand-apply or re-run the edit).

6. **The chapter summary is now stale** —
   `books/{book}/chapters/ch_{chapter}.summary.md` references the
   pre-cuts prose. apply-cuts is light-tier and doesn't run the
   LLM, so we don't regenerate the summary inline (that would bump
   the tier). Print a closing line directing the user to refresh
   continuity:

   ```
   ⚠️  ch_NN.summary.md is now older than ch_NN.md. Run
       /autonovel:summarize-chapter NN --book {book} --force
   to regenerate (or accept the /autonovel:next nag, which will
   surface this until you do).
   ```

   The lifecycle's verify-writes guard will also fire its 🔴 banner
   in the postamble (chapter modified without paired summary write),
   so this step is belt-and-suspenders — the user can't miss it.
</workflow>

<acceptance>
- For `--dry-run`, the chapter file is unchanged on disk.
- For a real run, the chapter's word count decreases by approximately
  the reported `words_removed`.
- The command exits non-zero only if `apply-cuts` reported `failed > 0`
  (a match failure the user should see).
- No cut is applied whose quote is shorter than 25 characters after
  whitespace normalisation — the mechanical module refuses those.
</acceptance>
