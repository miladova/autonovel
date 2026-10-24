---
name: autonovel:rename-character
description: Globally rename a character across every chapter, summary, outline, cast and design file, queued brief and shared file with word-boundary safety.
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
  - books/{book}/cast.md
  - books/{book}/design.md
  - books/{book}/seed.txt
  - books/{book}/threads.md
  - books/{book}/briefs/*.md
writes:
  - books/*/canon.md
  - shared/characters.md
  - shared/canon.md
  - shared/events.md
  - shared/world.md
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/pending_canon.md
  - books/{book}/chapters/*.md
  - books/{book}/cast.md
  - books/{book}/design.md
  - books/{book}/seed.txt
  - books/{book}/threads.md
  - books/{book}/briefs/*.md
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
   - every book's `books/<book>/canon.md` (book-scoped canon), or,
     when `--book` is passed, only that book's: another book's canon
     belongs with that book's chapters, which this sweep leaves alone.
   - per book (loop over all books in `project.yaml`, or just
     `--book` if passed):
     - `books/{book}/outline.md`
     - `books/{book}/voice.md`
     - `books/{book}/pending_canon.md`
     - every `books/{book}/chapters/*.md` (chapters and their
       summaries)
     - `books/{book}/cast.md` and `books/{book}/design.md`, when they
       exist: draft and revise read the cast dossiers and the design,
       so a name left there comes back in the next rewrite
     - `books/{book}/seed.txt` and `books/{book}/threads.md`, when
       they exist
     - every `books/{book}/briefs/*.md`, including
       `briefs/conversation.md`: a queued brief or staged turn that
       still uses the old name would hand it to the next revise
   Leave the research notes (`shared/research/`) and the edit logs
   (`books/{book}/edit_logs/`) alone: the notes are the record of the
   sources, and the logs are a history of what was said at the time.
   Step 7 lists any mention of the old name left in them.

3a. Use `bash` to run `autonovel mechanical summary-check books/{book}`
   for each book in the sweep and note which chapters' summaries are
   `fresh`. The rename rewrites a chapter and its summary alike, so
   those stay true after it; step 5a records that.

4. Ambiguity scan. For every target, count word-boundary matches of
   `<old-name>` (case-insensitive), and list every longer word that
   contains it (e.g. `Anatolia` when renaming `Ana`), with file and
   line. The word-boundary replacement never touches a longer word,
   so decide for each one whether it is a different word or a form of
   this character's name:
   - A different word (a place such as `Negroponte` when renaming
     `Negro`, an ordinary word such as `banana`) is left as it is.
     Name it in the step 7 report and go on.
   - A form of the name that word boundaries would miss (a plural
     `Anas`, a compound `Ana-Maria`, a name run into another word)
     stops the rename before any file is touched:

         rename refuses: `<old>` also appears as `<word>` in
         <file:line>, which the word-boundary replace would miss.
         Resolve by hand, then re-run.

5. Use `bash` to run the replacement. One invocation per file, so a
   failure mid-sweep leaves the earlier files already rewritten
   (the checkpoint from the preamble captures them all):

       sed -E -i "s/\b<old>\b/<new>/g; s/\b<old-lower>\b/<new-lower>/g; s/\b<old-upper>\b/<new-upper>/g" <file>

   For each file under `books/{book}/briefs/`, keep its modification
   time (`touch -r` from the checkpoint copy, or `stat` before and
   `touch -d` after): an old brief written before briefs carried a
   fingerprint is judged pending by its time, and a rename doesn't
   make it new.

   The three substitutions preserve the three common casings
   (Title, lower, UPPER). Do not attempt to match every possible
   casing — that is a source of bugs; instead rely on the
   ambiguity scan above to catch mixed-case surprises.

5a. For every chapter the rename changed whose summary step 3a found
   `fresh`, use `bash` to run `autonovel _stamp-summary --book {book}
   --chapter N` (the summary received the same rename, so it still
   matches). Leave a summary that was already out of date unstamped:
   the next command that reads it refreshes it.

6. Use `file_write` to append an audit entry to
   `shared/canon.md` under a `## Renamed <UTC-date>` heading:

       - Renamed `<old>` -> `<new>` across <N> files.

7. Print a per-file report (files touched, replacement counts), the
   longer words step 4 left untouched, and every file outside the
   targets that still names `<old-name>` as a whole word (research
   notes, edit logs; `grep -rlw` over `shared/research/` and
   `books/{book}/edit_logs/`), so the author knows the old name
   survives there on purpose.
</workflow>

<acceptance>
- Every file that contained `<old-name>` as a whole word now
  contains `<new-name>` in the same position.
- No file contains `<old-name>` as a whole word after the sweep
  (substring overlap intentionally preserved).
- `shared/canon.md` gains a `## Renamed <date>` audit line.
- If the ambiguity scan refused, no file was modified (the sweep
  either happens fully or is refused).
- `books/{book}/cast.md`, `books/{book}/design.md` and every queued
  brief no longer name `<old-name>`.
</acceptance>
