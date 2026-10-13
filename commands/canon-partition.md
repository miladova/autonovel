---
name: autonovel:canon-partition
description: Move a finished book's chapter-derived facts out of the series-wide shared/canon.md into that book's own books/<book>/canon.md — mechanical first pass on provenance tags, then an LLM classification of the untagged leftovers (real history stays shared; plot inventions move). Run once before adding a sibling book or a rewrite.
argument-hint: "--to-book <short-name> [--move-section <heading>]... [--move-key <shortname>]... [--dry-run] [--no-llm]"
model_tier: standard
allowed-tools:
  - bash
  - file_read
reads:
  - project.yaml
  - shared/canon.md
  - books/*/canon.md
writes:
  - shared/canon.md
  - books/*/canon.md
context_mode: series
---

<purpose>
Before book-scoped canon (2026-10-12) every promoted fact landed in
`shared/canon.md`, so a finished book's prose-derived inventions (a
locked coffer, a favour never repaid, the day a courier left Lisbon)
sit next to real history as *series* canon. A second book — a
different POV, a later period, or a **rewrite of the same story** —
would be bound by the first book's plot choices, and every draft pays
the token cost of the whole file (the Fugger book's canon reached
~45,000 words).

This command splits the file:

- `shared/canon.md` keeps what is true in ANY book set in this world —
  verifiable history, world rules, fixed biography, geography,
  institutions, every research-cited entry, and every `## Superseded`
  audit block.
- `books/{book}/canon.md` receives what exists only because THAT
  book's outline or chapters chose it.

Two halves. The **mechanical** helper (`autonovel canon-partition`)
moves every bullet whose `(from <book> ch_NN)` provenance names a
book, and reports the untagged leftovers. The **LLM** half (this
command) classifies those leftovers one by one and feeds the
decisions back to the helper as `--move-key` / `--move-section`
flags — the LLM never edits the canon files by hand.

Idempotent: a second run moves nothing. `autonovel rollback` undoes
it (the preamble checkpoints both files).
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--to-book <short-name>` names the book the
   untagged leftovers belong to (required unless `--dry-run` with no
   moves). `--move-section` / `--move-key` (repeatable) are explicit
   moves the user already decided. `--dry-run` reports and writes
   nothing. `--no-llm` skips step 4 (tagged bullets only). Any other
   argument is a usage error — stop with a one-line reminder.

2. **Mechanical pass.** Use `bash` to run (the preamble holds the
   lock, so pass `--no-lock`):

   ```
   autonovel canon-partition --no-lock [--to-book <book>] \
       [--move-section "<heading>"]... [--move-key "<shortname>"]... \
       [--dry-run] --format json
   ```

   It reads `project.yaml` and `shared/canon.md`, moves tagged bullets
   into each named book's `books/<book>/canon.md` (creating the file
   with a `# Book canon` header, grouping bullets under their original
   section heading suffixed "(partitioned from shared/canon.md)",
   keeping indented continuation lines verbatim), rewrites
   `shared/canon.md` without them (dropping any section left empty),
   and returns `moved`, `stayed_shared`, `superseded_blocks_kept`, and
   a `leftovers` list of `{section, shortname, snippet}` for every
   untagged bullet still in shared.

3. Print the helper's markdown summary (re-run with `--format
   markdown` or render the JSON): words before → after, moved per
   book, kept, warnings for unmatched `--move-*` arguments.

4. **Classify the leftovers** (skip with `--no-llm` or when
   `leftovers` is empty). Use `file_read` on `shared/canon.md` once
   so each leftover is seen in full. For every entry decide:

   - **series-wide** — a stranger with a history book could verify it
     (a real person's birth or death, an institution's rules, a real
     event's date, geography, the meaning of a coin), OR it is a world
     rule every book must obey. **Stays.** Section headings like
     "Personal identities and dates", "Historical fixed points",
     "Institutions and geography" are strong hints.
   - **book-scoped** — it exists only because this book's outline or
     prose chose it: a chapter's committed date for a fictional scene,
     an invented object, a secret the plot turns on, a submerged
     backstory, a character's private calculation, anything that a
     differently-plotted retelling could legitimately change.
     **Moves.** Section headings like "The outline's committed dates",
     "Material facts fixed in the outline", "Submerged facts" are
     strong hints — when every bullet in a section is book-scoped,
     prefer one `--move-section` over N `--move-key`s.

   Be conservative in ONE direction: when a bullet mixes history with
   a fictional gloss ("Maximilian died 12 Jan 1519; Jakob heard it by
   courier on the 16th"), it is book-scoped — the historical half is
   almost certainly also present as its own shared bullet.

5. Print the classification as a two-column list (`stays` /
   `moves → <book>`) with a one-phrase reason each, then re-run the
   helper (not `--dry-run`) with the resulting `--move-section` /
   `--move-key` flags and `--to-book <book>`. Print the final summary
   and the new word counts. Nothing is edited by hand.

6. Suggest the next step: when the user is about to add a rewrite,
   `autonovel new-book <new> --pov "<pov>" --story-time-range <a>-<b>
   --isolated` (see `/autonovel:help rewrite`); otherwise
   `/autonovel:next`.
</workflow>

<acceptance>
- `shared/canon.md` no longer contains any bullet whose `(from <book>
  …)` provenance names a book in `project.yaml`; every `## Superseded`
  block and every `(from research note …)` bullet is still present.
- Each named `books/<book>/canon.md` begins with `# Book canon` and
  contains the moved bullets, verbatim, under headings suffixed
  "(partitioned from shared/canon.md)".
- The printed classification lists every leftover exactly once as
  `stays` or `moves`, with a reason.
- A second invocation reports `moved: {}`.
- With `--dry-run`, neither file changes.
</acceptance>
