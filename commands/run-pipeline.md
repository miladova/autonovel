---
name: autonovel:run-pipeline
description: Drive the full pipeline across one or more books (foundation→drafting→revision→export).
argument-hint: "--books <name[,name...]> [--phase <phase>] [--max-cycles <N>]"
model_tier: light
allowed-tools:
  - file_read
  - bash
reads:
  - project.yaml
  - shared/events.md
  - books/{book}/outline.md
  - books/{book}/state.json
  - books/{book}/chapters/*.md
  - .autonovel/last-action.json
writes: []
context_mode: series
---

<purpose>
Replace the pre-rewrite `run_pipeline.py`. This command is the series-
level driver: it inspects each book's state, decides what the next
standard step is, and routes to the right slash command. It never
writes prose or lore itself — every content mutation goes through a
sibling `/autonovel:*` command that owns its own lock + checkpoint +
footer.

Loop structure for each book in `--books`:
  1. foundation until `foundation_score > 7.5 AND lore_score > 7.0`
     (commands, in order: `gen-world`, `gen-characters`,
     `voice-discovery`, `gen-canon` (shared half), `gen-outline`,
     `gen-canon --book {book}` (book half, seeded from the outline),
     `evaluate --phase foundation`).
  2. drafting every chapter in `outline.md` order that does not yet
     exist, scoring with `evaluate --chapter N`; on score `< 6.0`
     retry once and otherwise continue (forward progress wins).
  3. revision in cycles: `adversarial-edit` → `apply-cuts` →
     `structure-review` → `reader-panel` → briefs (`brief --from auto`
     turns structure-review candidates into `kind: structural`
     briefs) → `revise`; stop when score delta `< 0.3` across two
     consecutive cycles AND the book-level structure gate passes
     (`autonovel mechanical structure-validate books/<book>`), or
     after 6 cycles. Cross-chapter moves the structure review asks
     for (merge / cut / reorder / split) are surfaced to the user,
     never run by the loop.
  4. export via PR-7 commands if available; otherwise surface the
     missing command and stop.

Multi-book wiring: before drafting a chapter, this command shells out
to `python -m autonovel.context_loader --book <b> --chapter <N>` so
the `/autonovel:draft` invocation knows which sibling-book chapters
are readable at that story_time (no spoilers from chapters whose
`story_time` is later). Events come from `shared/events.md`, which
should be valid per `autonovel mechanical` — run
`/autonovel:promote-canon` first if `pending_canon.md` has entries.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Accept `--books a,b,c` (comma-separated; if
   omitted, default to every book in `project.yaml`), `--phase
   foundation|drafting|revision|export|all` (default `all`), and
   `--max-cycles N` (default 6, revision-only).

2. Use `file_read` on `project.yaml` to resolve the book list and
   whichever defaults are relevant (`chapter_target_words`,
   `foundation_threshold`, `chapter_threshold`). If a requested book
   is not listed, stop with a usage error — do not create books
   implicitly.

3. Use `file_read` on `shared/events.md` and call `python -m
   autonovel.mechanical slop shared/events.md` is *not* valid (that
   target is prose). Instead, surface any malformed event the
   validator would flag and stop — the downstream context loader
   trusts this file. (A smoke test enforces this.)

4. For each book in order:

   a. Use `file_read` on `books/{book}/state.json` to learn the current
      phase. Use `file_read` on `books/{book}/outline.md` and
      `books/{book}/chapters/*.md` to cross-check.

   b. If the requested phase includes `foundation` and the state says
      `phase < drafting`: route through the five foundation commands
      until `foundation_score > 7.5 AND lore_score > 7.0` or after
      20 iterations, whichever comes first. **Second and later books
      in a series skip the series-scoped steps** — `gen-world`,
      `gen-characters` and the shared half of `gen-canon` are only run
      when `shared/world.md` / `shared/characters.md` /
      `shared/canon.md` are still template stubs; a populated shared
      layer was drafted against by the earlier book and must not be
      regenerated under it. For such a book run only `voice-discovery`,
      `gen-outline`, then `gen-canon --book {book}` (book-scoped half,
      seeded from the outline).
      Print the next
      slash-command invocation and stop — routing preserves lock and
      checkpoint guarantees of the target command. Do not shell out
      to `claude -p` from within `bash`; the user (or the outer
      runtime turn) runs the next command.

   c. If the requested phase includes `drafting`: for each chapter
      number in outline order that does not yet have a chapter file,
      run `python -m autonovel.context_loader --book {book} --chapter
      N` via `bash`, parse the JSON for `sibling_chapters` and
      `excluded_spoilers`, and print the `/autonovel:draft N --book
      {book}` invocation with a note listing the sibling files the
      drafter is allowed to read. On score `< 6.0` after
      `/autonovel:evaluate --chapter N --book {book}`, retry once.

   d. If the requested phase includes `revision`: score each chapter
      from the previous cycle, compute a mean score, and stop when
      the delta is `< 0.3` across two consecutive cycles and the
      structure gate passes (`gate.passes` from `autonovel mechanical
      structure-validate books/{book}`), or after `--max-cycles`
      (default 6). Route through `/autonovel:adversarial-edit`,
      `/autonovel:apply-cuts`, `/autonovel:structure-review`,
      `/autonovel:reader-panel`, `/autonovel:brief`, and
      `/autonovel:revise` in that order. A chapter-score plateau with
      the structure gate blocked is not a stop: it means the prose is
      done and the book's shape is not — print the structure
      review's cross-chapter commands for the user and keep cycling
      on its structural candidates.

   e. If the requested phase includes `export`: surface the PR-7
      commands once they ship. For now, print a single line
      explaining that export commands land in PR 7 and point at the
      legacy typeset templates under `typeset/`.

5. After each book's step, read `.autonovel/last-action.json` (if
   present) and print a one-line summary: which book, which phase,
   which next command to run. This is the contract — the orchestrator
   *suggests*, it never invokes.

6. Emit a final "standard next step" line. If every requested book is
   at `export-done`, say so; otherwise name the first book + phase
   that still has work.
</workflow>

<acceptance>
- No files are modified by this command directly; the contract is
  advisory only. (A read-only snapshot of the series tree before and
  after `/autonovel:run-pipeline` must be byte-identical apart from
  `.autonovel/` bookkeeping.)
- The output names the current phase of every requested book and the
  single next slash command to run.
- When `shared/events.md` is malformed per the `E-NNN` + field
  schema (§8), this command surfaces the problem list and stops
  rather than suggesting a draft.
- Multi-book runs never suggest a draft for book `X` chapter `N`
  without first surfacing the `excluded_spoilers` list from the
  context loader — the drafter must see which sibling chapters are
  off-limits.
</acceptance>
