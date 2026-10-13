---
name: autonovel:impact-of
description: After a foundation mutation, list the chapters that reference the old fact and need revising — kills the ls / grep / cat workflow. Mechanical first pass; opt-in LLM classification of false positives.
argument-hint: "[--book <short-name>] [--source promote-canon|gen-canon|voice-discovery|add-character|gen-characters|gen-world|add-source|rename-character|merge-chapters|reorder|remove-chapter|research] [--with-llm] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
  - file_read
reads:
  - shared/canon.md
  - books/{book}/canon.md
  - shared/research/notes/*.md
  - books/{book}/chapters/ch_*.md
writes: []
context_mode: book
---

<purpose>
"What should I revise after `/autonovel:promote-canon`?" — and
its siblings: "after `/autonovel:research`?", "after
`/autonovel:gen-canon`?". The "now what?" moment that used to
require manual `ls` + `grep` across `shared/canon.md` Superseded
blocks and `books/<book>/chapters/`. autonovel exists to collapse
that investigation into one command.

Five mechanical detection shapes, plus an LLM augmentation:

  - **Canon-driven** (`--source promote-canon`, `--source gen-canon`).
    Parses `## Superseded` blocks in `shared/canon.md`, computes
    tokens unique to each prior_value, greps every chapter for
    them. Fast, free, no LLM. Same logic for both — gen-canon is
    the regenerate-from-foundation variant of promote-canon and
    writes the same Superseded blocks when it changes a fact.
  - **Mtime-driven** (`--source voice-discovery`, `add-character`,
    `gen-characters`, `gen-world`, `add-source`). Each maps to a
    foundation file (`books/<book>/voice.md`,
    `shared/characters.md`, `shared/world.md`,
    `shared/sources.bib`); the helper lists chapters whose mtime
    is older than the foundation's. The natural shape for
    foundation surfaces that change in ways grep can't see (a
    new voice fingerprint, a new character entry, a fact in the
    world bible).
  - **Rename-verify** (`--source rename-character`). Reads the
    most recent `autonovel:rename-character` entry from
    `.autonovel/command-log.jsonl`, extracts `--old`/`--new` from
    its args, and word-boundary-greps every chapter for the OLD
    name. The slash-command's sed should have caught everything;
    this catches what slipped through (possessives, hyphens,
    unicode look-alikes, HTML entities). Empty result = clean
    rename.
  - **Renumber-refs** (`--source merge-chapters`, `reorder`,
    `remove-chapter`). After a renumber, prose mentions of
    `Chapter VII`, `chapter 7`, `ch. 12`, etc. may now point at
    the wrong chapter. Greps every chapter for chapter-number
    cross-references and emits a candidate review list; reads
    the most recent invocation from the command-log for context.
    Review-list shape: false positives are common (thematic
    mentions, references that were always to the right chapter).
  - **LLM-augmented** (`--with-llm`, applies to canon-driven
    sources). After the mechanical pass, a Haiku-tier classifier
    reads each candidate chapter line in context and labels it
    `HIGH` (real direct fix needed), `MEDIUM` (implied — needs
    careful re-read), `LOW` (token coincidence), or
    `FALSE_POSITIVE`. The action checklist then only includes
    HIGH/MEDIUM matches; LOW/FALSE_POSITIVE matches drop to a
    separate "skipped — token coincidence" block. Cuts the
    false-positive review burden on noisy matches like 4-digit
    years.

Plus the standalone LLM-only mode for sources without a clean
mechanical signal:

  - **`--source research`.** Reads every
    `shared/research/notes/*.md` newer than the latest entry in
    `shared/canon.md`'s `## Promoted` / `## Superseded` blocks
    (i.e. notes added since the last promote-canon). For each
    note, the LLM extracts the load-bearing facts and per-chapter
    scans for contradictions. Default: LLM-augmented. Add
    `--no-llm` to fall back to a literal-grep over the notes'
    `[shortname]` citations and Candidate Canon Entries (the
    cheap baseline; only useful when you suspect a verbatim quote
    in a chapter).

Per the brittle-Python rule, the mechanical layer is a candidate
generator (review list, not a quality gate). The LLM layer is the
classifier — that's where the cross-chapter reasoning lives. Both
are read-only by contract.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. `--source` defaults to `promote-canon`; supported
   values: `promote-canon`, `research`. `--with-llm` enables the
   classifier (only meaningful for `promote-canon` mechanical
   pass); `--no-llm` disables it for `research` mode (which is
   LLM by default). `--format markdown|json` (default
   `markdown`).

2. **Mechanical pass.** Use `bash` to invoke:

   ```
   autonovel mechanical impact-of books/{book} --source <SOURCE> --format json
   ```

   Two helper shapes depending on `--source`:

   - **Canon-driven** (`promote-canon`, `gen-canon`): the helper
     parses `shared/canon.md` AND this book's `books/{book}/canon.md`
     for `## Superseded <UTC-date>`
     blocks, extracts (prior_value, new_value) pairs, computes
     tokens unique to prior, and greps every
     `books/{book}/chapters/ch_*.md` (frontmatter-stripped) for
     them. JSON output gives you the structured match list with
     `report_kind: canon-driven`.
   - **Mtime-driven** (`voice-discovery`, `add-character`,
     `gen-characters`, `gen-world`, `add-source`): the helper
     resolves the source command to its foundation file path,
     lists chapters whose mtime is older than the foundation
     file's, and emits a stale-chapters list. JSON has
     `report_kind: mtime-driven`. Action plan: each stale chapter
     gets a `/autonovel:revise --chapter N` checklist entry to
     reconcile against the updated foundation.
   - **Rename-verify** (`rename-character`): reads the most
     recent `autonovel:rename-character` entry from
     `.autonovel/command-log.jsonl`, word-boundary-greps every
     chapter for the OLD name, and reports stragglers with line
     snippets. JSON has `report_kind: rename-verify`. Empty
     matches list means the rename took cleanly.
   - **Renumber-refs** (`merge-chapters`, `reorder`,
     `remove-chapter`): greps every chapter for prose
     chapter-number cross-references (`Chapter VII`, `chapter 7`,
     `ch. 12`). JSON has `report_kind: renumber-refs`. Each
     chapter with at least one match gets a checklist entry to
     verify the references against the current chapter ordering.

   When `--source research` is set instead, skip step 2 and go
   to step 3 (research mode is LLM-only by default).

3. **LLM classification pass — `--with-llm` only.** For each
   match the mechanical pass returned (chapter, line_no,
   line_text, matched_tokens, supersedure context), classify the
   match into one of:
     - `HIGH` — chapter directly states the now-wrong fact
       (e.g. "Fugger arrived in 1473" with prior "1473"
       superseded to "1478"). The fix is a literal substitution.
     - `MEDIUM` — chapter implies a fact that the new value
       contradicts (e.g. "five years before the fire" with the
       fire's date flipped). The fix needs a careful rewrite,
       not a search-and-replace.
     - `LOW` — token coincidence (e.g. "1473" appears in a
       different context — the year a different building was
       built; the chapter is about something else). Skip.
     - `FALSE_POSITIVE` — clearly a non-issue (e.g. the
       matched name "1473" is part of a date range that doesn't
       semantically intersect with the flipped fact).

   Emit the classification + a one-sentence rationale per
   match. Use `file_read` on the chapter (with line context)
   only when needed — the line_text + supersedure context the
   mechanical pass emitted is usually enough.

   The action checklist at the bottom of the report includes
   only HIGH and MEDIUM chapters; LOW / FALSE_POSITIVE drop to a
   separate "skipped — token coincidence" block at the end so
   the user can audit if curious.

4. **Research mode — `--source research`.** Use `bash` to find
   notes newer than the most recent `## Promoted` / `##
   Superseded` block in `shared/canon.md`:

   ```
   autonovel mechanical research-index <series_root> --format json
   ```

   Then `file_read` each note newer than the canon's last
   timestamp. For each note's `## Candidate Canon Entries`
   block, the LLM extracts the load-bearing facts as
   `(shortname, claim)` pairs.

   Then for each chapter under `books/{book}/chapters/`, the
   LLM scans for any prose that contradicts a candidate-canon
   claim. Emit per-chapter findings with the contradicting
   chapter line + the candidate canon claim it contradicts +
   one-sentence "what should change."

   With `--no-llm`, fall back to literal grep over the notes'
   `[shortname]` citations using the same mechanical-helper
   pipeline as `--source promote-canon` (lower precision; only
   useful when you suspect a verbatim quote of an obsolete
   fact).

5. Print the report. Mechanical-only mode prints the helper's
   markdown verbatim. LLM-augmented modes print the same
   structure with the classification block layered on.

6. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files written.
- Mechanical-only mode (no `--with-llm`, source =
  `promote-canon`) returns identical output to direct CLI
  invocation `autonovel mechanical impact-of books/{book}` —
  the slash-command is a thin wrapper in this mode.
- LLM-augmented mode emits a classification per match
  (HIGH / MEDIUM / LOW / FALSE_POSITIVE) with a one-sentence
  rationale, and the action checklist contains only HIGH/MEDIUM
  chapters.
- Research mode reads `shared/research/notes/*.md` and emits
  per-chapter findings citing the candidate-canon claims that
  contradict chapter prose.
- Every chapter referenced in the action plan has at least one
  matched line snippet shown above it (so the user can judge
  the call before acting).
- When the source has nothing to act on (no Superseded blocks
  for `promote-canon`; no new research notes for `research`),
  the output explains why — no facts flipped, no new research
  since last canon promotion.
</acceptance>
