---
name: autonovel:rename-character
description: Globally rename a character across every chapter, outline, and shared file with word-boundary safety.
argument-hint: "--old <old-name> --new <new-name> [--book <short-name>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/canon.md
  - books/*/canon.md
  - shared/characters.md
  - shared/world.md
  - shared/events.md
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/pending_canon.md
  - books/{book}/chapters/*.md
writes:
  - books/*/canon.md
  - shared/characters.md
  - shared/canon.md
  - shared/events.md
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/pending_canon.md
  - books/{book}/chapters/*.md
context_mode: series
---

<purpose>
Sidequest: rename a character in every place their name appears.
Word-boundary replace (never substring — "Ana" in "banana" stays),
case-preserving for the common forms (`Ana` → `Maria`, `ana` →
`maria`, `ANA` → `MARIA`). Runs as one checkpoint so a botched
rename is one `autonovel rollback` away.

Gotcha (CLAUDE.md: "Chapter renumbering ... must be done by script,
never hand-edited"): the same discipline applies here. The rename is
scripted — the LLM identifies the targets and ambiguities, then uses
`bash` with `sed` (word-boundary regex) to perform the substitution
on every identified file. Files are only touched if at least one
replacement occurs.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--old <old-name>` and
   `--new <new-name>`. Optional: `--book <short-name>` to limit
   the sweep to one book (shared files still get rewritten).
   Missing args are a usage error.

2. Use `file_read` on `project.yaml`, `shared/characters.md`,
   `shared/canon.md`, every `books/*/canon.md`, `shared/world.md`, and
   `shared/events.md`.
   If `<old-name>` is not in `shared/characters.md`, stop — this
   command only renames established characters, so fat-finger typos
   cannot silently mangle the manuscript. Suggest
   `/autonovel:add-character --name <new>` instead.

3. Enumerate target files:
   - shared: `shared/characters.md`, `shared/canon.md`,
     `shared/events.md`, `shared/world.md`.
   - every book's `books/<book>/canon.md` (book-scoped canon).
   - per book (loop over all books in `project.yaml`, or just
     `--book` if passed):
     - `books/{book}/outline.md`
     - `books/{book}/voice.md`
     - `books/{book}/pending_canon.md`
     - every `books/{book}/chapters/*.md`

4. Ambiguity scan. For every target, count word-boundary matches of
   `<old-name>` (case-insensitive). If any file also contains a
   substring that overlaps (e.g. renaming `Ana` when `Anatolia`
   appears), surface the matching lines to the user and stop:

       rename refuses: `<old>` overlaps with `<word>` in <file:line>.
       Resolve by hand or pass `--force-overlap`.

   `--force-overlap` is NOT supported in this version; the message
   just flags the next manual step.

5. Use `bash` to run the replacement. One invocation per file, so a
   failure mid-sweep leaves the earlier files already rewritten
   (the checkpoint from the preamble captures them all):

       sed -E -i "s/\b<old>\b/<new>/g; s/\b<old-lower>\b/<new-lower>/g; s/\b<old-upper>\b/<new-upper>/g" <file>

   The three substitutions preserve the three common casings
   (Title, lower, UPPER). Do not attempt to match every possible
   casing — that is a source of bugs; instead rely on the
   ambiguity scan above to catch mixed-case surprises.

6. Use `file_write` to append an audit entry to
   `shared/canon.md` under a `## Renamed <UTC-date>` heading:

       - Renamed `<old>` -> `<new>` across <N> files.

7. Print a per-file report (files touched, replacement counts).
</workflow>

<acceptance>
- Every file that contained `<old-name>` as a whole word now
  contains `<new-name>` in the same position.
- No file contains `<old-name>` as a whole word after the sweep
  (substring overlap intentionally preserved).
- `shared/canon.md` gains a `## Renamed <date>` audit line.
- If the ambiguity scan fired, no file was modified (the sweep
  either happens fully or is refused).
</acceptance>
