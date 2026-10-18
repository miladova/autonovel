---
name: autonovel:cast
description: Build the book's character dossiers, books/{book}/cast.md, so the people on the page have depth — for each principal what they want and fear, the contradiction they act out, what they put first when forced to choose, their secret and private life, how they see a room, their history with each other person, the choices that test them chapter by chapter, a private monologue for the writer and a one-clause return tag; a short entry for each minor or ensemble player. Real people are built from the research record. Draft, revise, evaluate and the outline read it.
argument-hint: "--book <short-name> [--character <name>] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - project.yaml
  - shared/craft/CHARACTER.md
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - books/{book}/seed.txt
  - books/{book}/design.md
  - books/{book}/outline.md
  - books/{book}/voice.md
  - shared/research/notes/*.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/edit_logs/first_read_ch*.md
  - books/{book}/cast.md
writes:
  - books/{book}/cast.md
context_mode: book
---

<purpose>
A design names each character's want, fear, secret and contradiction in
a line. That is enough to plan a book and not enough to write a person:
the drafter reaches for the line it was given, and the page shows the
signature (the receipt, the straightened sleeve) without the life under
it, and readers find the characters simple. This command
does the work a novelist does before drafting — the dossier, the
relationships, the choices that will test each person, a private
monologue in their own voice — so the drafter has a person to render,
not a label to repeat.

`shared/craft/CHARACTER.md` is the method: what depth is, the dossier
fields, how depth gets onto the page, how to build real people from the
record, how to keep an ensemble distinct, and the tests C1–C12 this
command checks each principal against.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`: `--book` (required). `--character <name>` builds
   or rebuilds that one entry and leaves the rest of the file alone.
   Without it, an existing populated `books/{book}/cast.md` is rebuilt
   only with `--force` (the run's checkpoint keeps the old file); without
   `--force`, stop and say so.

2. Use `file_read` on `shared/craft/CHARACTER.md`, in full. If
   `shared/craft/` lacks it, run `autonovel refresh-templates` with
   `bash` first.

3. Use `file_read` on `project.yaml`, `books/{book}/seed.txt`,
   `books/{book}/design.md` (its `## Cast`, `## Opposition`, gatekeepers
   table and spine), `books/{book}/outline.md`, `books/{book}/voice.md`
   (Part 4's per-character fingerprints), `shared/characters.md`,
   `shared/canon.md` and `books/{book}/canon.md`. When there is no
   design, take the cast from `shared/characters.md` and the outline.

4. **Decide who gets what** (CHARACTER.md "Who gets a dossier"). A full
   dossier for every principal: the viewpoint characters, the intimate,
   the rival, the mentor, the influence character, every ally on stage in
   three or more chapters, and anyone whose choice the plot turns on. A
   short entry for every minor and ensemble player (a council, a court,
   seven electors). List both groups before writing.

5. **The record first, for real people.** Find the research notes that
   cover each real person (`bash`: `grep -l -i "<surname>"
   shared/research/notes/*.md`) and use `file_read` on them. The
   contradiction, fears, griefs, relationships and recorded words of a
   real principal come from the record, cited by note name in square
   brackets; mark anything you add `(invented)`, and invent only where
   the record is silent. Never reduce a real person to the trait they
   are famous for. When a real principal has no research on their inner
   life, write the entry from what exists, mark it thin, and print
   `/autonovel:research "<name>: inner life, contradictions,
   relationships, recorded words"` under **Next**.

6. **What the page already shows.** When chapters exist, use `file_read`
   on each one and on `books/{book}/edit_logs/first_read_ch*.md`. For
   each person, note what the drafted chapters actually put on the page,
   and every place a first reader said they read as a type ("Who felt
   real"). The dossier has to answer those: a want of their own in the
   scene they were flat in, the contradiction shown there, a choice.

7. **Write each full dossier** in the CHARACTER.md format: the fields in
   order, each specific to this person (no field may be true of half the
   cast), then the **pressure choices** by chapter — the moment in each
   act where they must choose between two things they value and what it
   costs — and the **on the page** list: for each chapter they appear
   in, the one thing that chapter shows of them that no earlier chapter
   has. Then the **private monologue**: 150–300 words, first person,
   present tense, as they would think it at their first appearance,
   unguarded, in their own words and with their blind spot showing. It
   is for the writer only and is never pasted into a chapter.

8. **The relationship map.** A table of the pairs that matter: their
   history, the balance between them (who owes whom what), what is never
   said, and how it changes, with chapters. Every principal pair gets a
   row; a relationship with no history and no change is a fault to fix.

9. **Short entries** for the minor and ensemble players: who they are,
   where, age, what they want, their price or their fear, one concrete
   detail of face or manner (from the record where real), and a
   **return tag** — one clause that re-anchors them when they come back
   ("Albrecht, the young Archbishop of Mainz who spent faster than anyone
   Jakob knew, and wanted cash in his hand"). Give every principal a
   return tag too. Where what they want changes, give the tag per act.

10. **Self-test** each principal against CHARACTER.md's tests C1–C12
    and write the verdicts under `## Tests`, one line each
    (`- <name> C<n> pass|fail: <reason>`). A fail is fixed in the
    dossier — usually by scheduling the act that shows it in a named
    chapter — before the file is written. Two principals who pass the
    same tests in the same way are the same person under two names:
    merge them or make them differ.

11. **Cold check.** Use `task` to spawn one fresh heavy-tier reader
    given only the draft `cast.md` and CHARACTER.md's "How characters
    come out flat" section. Ask it: who still reads as a type; which two
    people are the same person; whose want is only the protagonist's
    want; which contradiction is a label rather than an act; whose
    private life is empty; which return tags would not tell a reader who
    had forgotten the person who they are. Fix what it finds.

12. Use `file_write` to save `books/{book}/cast.md`: `# Cast`, then
    `## Principals` (the dossiers), `## Relationships` (the table),
    `## Ensemble and minor players` (the short entries), `## Tests`.
    With `--character`, replace only that person's entry (and their
    rows in the relationship table and tests).

13. Report, in plain words: each principal in one line (want ·
    contradiction · the choice that tests them, with its chapter); the
    people a first reader called a type and what their dossier now
    gives them; real people whose record is thin; and **Next**: when
    chapters are drafted, `/autonovel:revise <N> --book {book}` for the
    chapters whose people were flat (the brief should cite the cast.md
    "on the page" lines), or `/autonovel:draft <N> --book {book}` for
    the next chapter; before an outline exists,
    `/autonovel:gen-outline --book {book}`.
</workflow>

<acceptance>
- `books/{book}/cast.md` exists with `## Principals`, `## Relationships`,
  `## Ensemble and minor players` and `## Tests`.
- Every principal has every CHARACTER.md dossier field, pressure choices
  with chapters, an "on the page" list, a private monologue and a return
  tag; every ensemble player has a return tag.
- Every real principal's contradiction cites a research note or is
  marked `(invented)`.
- No chapter, outline or design file was changed.
</acceptance>
