---
name: autonovel:developmental-edit
description: A developmental editor's full read of a drafted book — one reader, every chapter in order, running notes, counted evidence — then a ranked editor's letter on the story (not the prose), compared against the pipeline's own reviewers. --stage queues the in-chapter fixes for revision-pass.
argument-hint: "--book <short-name> [--focus \"<the author's concern, in their words>\"] [--stage]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/craft/EDITING.md
  - shared/craft/CRAFT.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/seed.txt
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/briefs/conversation.md
  - books/{book}/edit_logs/editor_letter.md
  - books/{book}/edit_logs/structure_review.md
  - books/{book}/edit_logs/review.md
  - books/{book}/edit_logs/reader_panel.json
writes:
  - books/{book}/edit_logs/editor_read_notes.md
  - books/{book}/edit_logs/editor_letter.md
  - books/{book}/edit_logs/editor_letter_*.md
  - books/{book}/edit_logs/editor_read_notes_*.md
  - books/{book}/briefs/conversation.md
context_mode: book
---

<purpose>
Do what a developmental editor does with a finished draft: read the whole
book once, in order, as a reader; keep notes as you go; count the things
the diagnosis rests on; then write the author a letter that says what the
book is, what must survive revision, what is wrong with the *story* and
why, and what to do about it in order of effect for the cost.

This command exists because the pipeline's instruments missed what a
reader saw. A book's dual-persona review can hold at 4★ for many passes
and its reader panel say every persona would buy it, while the author
finds the book a string of episodes rather than one story. The author is
not a writer or an editor and should not have to be: the editor's judgement is this
command's job. It is not a score and not a gate. Its output is a letter a
person acts on.

It differs from the other whole-book readers on purpose:

- `/autonovel:review` writes an editorial letter that is mostly about
  prose; `/autonovel:reader-panel` gives four personas' reactions;
  `/autonovel:structure-review` scores plot causation against a rubric.
  This command reads the book *before* it reads any of them, forms its
  own diagnosis, and only then compares, recording where it agrees and
  where an instrument is blind.
- It judges the reader's experience (where the book holds, where it lets
  go, what the reader knows and wants at each point), the relationships
  and arcs that carry causation as much as plot does, the narration's
  handling of time, the protagonist's engine and errors, the opposition,
  the theme, and the ending.
- It is accountable: it names which pipeline rules, staged edits or its
  own earlier advice produced the problems it finds.
</purpose>

<ground-rules>
Re-read these before writing the letter.

1. **One reader reads the whole book.** You read every chapter yourself,
   in full, in order. Do not fan out to subagents, do not read in
   parallel, and do not substitute summaries for prose. A whole-book
   judgement made from fragments is the failure this command replaces.
   If the runtime cannot hold the book, the notes file is your memory:
   write it after every chapter and re-read the notes, never the
   summaries.
2. **Read cold, compare later.** Do not open the seed, outline, chapter
   summaries, eval logs, the review, the panel or the structure review
   until the reader's pass is written. Their verdicts anchor; the
   author needs an independent read.
3. **Strong prose is not a working story.** A vivid scene, a good line,
   a paid-off image or a high chapter score is not evidence that the
   book builds. Say what works, specifically, so revision protects it;
   then judge the story on its own terms.
4. **Count, don't assert.** Every claim about the whole book rests on a
   count or a list of chapters: how many joints cross a year, how many
   chapters flash forward, how often the protagonist is wrong, where
   each principal first appears, which chapters each opposing force is
   in. Use the helpers in step 7 for the counts they can make and read
   the prose to verify every candidate they return.
5. **Character causation counts as much as plot causation.** A chapter
   that changes a relationship a later chapter's choice depends on is
   load-bearing, even if no later plot event needs it.
6. **Diagnose the reader's experience, not the plan.** The outline's
   intention is not evidence of the effect. If the plan says "one wager
   raised four times" and the reader feels four separate wagers, the
   reader is right.
7. **Recommend story-level moves.** A question posed earlier, an
   opponent who lasts and wins sometimes, an error the protagonist must
   pay for, a choice played on the page, a cut or a merge. Never
   recommend a linking sentence or a catch-up paragraph at a joint as the
   fix for a joint: a joint is fixed by what happens in the scenes (a
   person doing something because of the last chapter), not by a
   paragraph that says why. Never recommend a change that breaks the
   book's own spine or theme to improve a metric. A frame is a
   recommendation only if it carries its own suspense (`EDITING.md` S9);
   a frame that announces how the life ends is hindsight by structure.
8. **The record and the author's intent are constraints.** In historical
   fiction the dates and deaths stand; the novel supplies the
   "therefore". Recommendations that change the record say so and why.
9. **Find what the author has not raised.** At least three of the
   problems in the letter must be ones the author never named. If the
   author found a problem first, say so and say why the pipeline missed
   it.
10. **Own the pipeline's mistakes.** If a rule in the seed or voice file,
    a staged edit in `briefs/conversation.md`, or an earlier letter of
    yours produced a problem, name it in the letter. The author needs to
    know which advice to stop following.
11. **Discount your own judgement.** You are the same model family that
    drafted the book, and model judges favour their own text and do not
    track expert readers (`EDITING.md` §5). Trust a count, a list or a
    quoted passage over an impression; assume the book lacks turning
    points, a real setback and tension until you have found them on the
    page; and before the letter, argue the strongest case that the book
    does not work and answer it with the text.
12. **Judge the book against its own aim.** State what the author was
    trying to do (the seed, read in step 8, and the book itself) and do
    not fault it for not attempting something else (Updike's first rule;
    James's donnée). Where the aim itself is the problem (a whole life
    when the story is one campaign of it), say so as a choice for the
    author, not a defect of execution.
13. **Write for a non-specialist.** Plain words; name the craft
    principle and where it comes from (the study text in
    `shared/craft/EDITING.md` gives sources) in one sentence, then say
    what it means on this book's pages. No hedging: "individually fine",
    "a cost of ambition", "largely successful" never qualify a defect.
</ground-rules>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` (resolved by the preamble
   if omitted). `--focus "<text>"`: the author's concern, verbatim; the
   letter must answer it. `--stage`: after the letter, queue the
   in-chapter recommendations (step 13). Read `project.yaml` for the
   book's title, genre and period.

2. **Study before you read.** Use `file_read` on
   `shared/craft/EDITING.md` in full: how professional editors read a
   manuscript, the diagnostic questions by level, the failure patterns
   with their fixes, and the sections on historical fiction and the
   commercial thriller when the book is one. Then read
   `shared/craft/CRAFT.md` §1 (plot structure). If `EDITING.md` is
   missing, stop and tell the author to run
   `autonovel refresh-templates` (or `autonovel doctor` to see why).

3. **Archive the previous letter and notes.** Without reading them,
   use `bash` to move each of `books/{book}/edit_logs/editor_letter.md`
   and `books/{book}/edit_logs/editor_read_notes.md` that exists to a
   name stamped with its own mtime to the minute, e.g.
   `ts=$(date -r books/{book}/edit_logs/editor_letter.md +%Y-%m-%dT%H%M)`
   then `mv books/{book}/edit_logs/editor_letter.md
   books/{book}/edit_logs/editor_letter_$ts.md` (likewise
   `editor_read_notes_$ts.md`; add `-2` if the name is taken).
   `edit_logs/` keeps every past letter. Moving instead of copying means
   the new files are written fresh and nothing old is read before
   step 10 compares against it.

4. **Set up the notes.** Use `file_write` to start
   `books/{book}/edit_logs/editor_read_notes.md` with a header: the
   book, today's date, "reader's pass, read cold before the seed,
   outline, summaries and reviews", and the author's `--focus` text if
   given (recorded, not yet answered).

5. **The reader's pass.** Read `books/{book}/chapters/ch_*.md` in
   chapter order, every word (skip `*.summary.md`). After each chapter
   (two at most), append a block to the notes with these fields:
   - **What happens:** three to six lines.
   - **What I want to know now:** the open questions the chapter leaves
     a reader holding.
   - **What pulls me forward / where I'd put it down.**
   - **Caused by / sets up:** which earlier chapter's result this one
     answers (cite the chapter), and what it plants.
   - **Opposition:** who or what stands against the protagonist here,
     and whether it was here before and will be again.
   - **The protagonist:** what they want, what they are wrong about,
     whether they are wrong *here* and what it costs them, whether
     anything in them changed.
   - **The scene turns:** for each scene, the value at stake and its
     charge at the open and at the close (McKee, Coyne); flag a scene
     whose only change is "uninformed to informed".
   - **Time and narration:** the gap from the previous chapter; every
     place the narration steps outside the story's present (a
     flash-forward, a summary of years), and what it does to the scene.
   - **Craft notes:** only those that affect the story.
   Every four to six chapters, add a **Running diagnosis**: your current
   hypotheses about the book's shape. Revise them openly when later
   chapters change your mind; the notes should show the revisions.

6. **The one-page test.** Before any plan, dossier or summary, fill,
   from the book and your notes alone: the one-sentence pitch (who wants what, against whom,
   at what cost: `EDITING.md` P1); the dramatic question the reader is
   waiting on and where it is posed (P2); one action or a life (P3); the
   controlling idea as "[value] because [cause]" (P4); the genre and its
   obligatory scenes (P5, G1, and §18 for a thriller); the protagonist's
   Lie, Want and Need (C2); the opponent who competes for the same prize
   and his plan (A2, A3); the midpoint's revelation (S5); the climax's
   choice (E1). Write it under **One page** in the notes. A field you
   cannot fill from the pages is a decision the book has not made; it
   belongs in the letter.

7. **The measurement pass.** Only now, use `bash` to run, from the series
   root (the dossier carries the outline, the chapter summaries and the
   latest scores, which is why it comes after the one-page test):
   - `autonovel mechanical structure-dossier books/{book} --format json`
     (story-time gaps between chapters, each chapter's position in the
     book, word counts, the summaries with their cast lines, eval scores);
   - `autonovel mechanical prolepsis books/{book} --format markdown`
     (candidate narrator flash-forwards per chapter; read each in its
     paragraph and keep the real ones).
   From your notes and these, tabulate the facts your diagnoses rest on:
   chapter joints that cross a year or more; chapters with a
   flash-forward; chapters where the protagonist is wrong and pays;
   the chapter and percentage where each principal and each opposing
   force first appears, and the chapters they are on stage; where the
   book's central question is first posed and where it is answered;
   which chapters a later chapter's choice depends on (plot or
   relationship). Put the tables in the notes under **Measurements**.

8. **The intent pass.** Now read `books/{book}/seed.txt`,
   `books/{book}/outline.md`, `books/{book}/voice.md` and
   `books/{book}/briefs/conversation.md`. Compare intent with what the
   pages do. Find the rules and staged edits that produced each problem
   (a seed rule that every chapter must open and settle its own stake; a
   voice rule that demands a forward-pointing line per chapter; a staged
   edit that added a scene to pay a clock). Note them under
   **Causes in the pipeline**. Then compare the One page (step 6) with
   what the seed and outline intended.

9. **Write the letter.** Use `file_write` to save
   `books/{book}/edit_logs/editor_letter.md`, 1,800–3,500 words (not
   counting the ledger), with these sections, the ledger always last:
   - `# Editor's letter — <title>` and a first line saying when and how
     the read was done.
   - `## What the book is`: the premise and its real subject, one
     paragraph. If the book has a question it is really asking, state it.
   - `## What works, and must survive revision`: specific scenes, arcs
     and devices, with chapters, so no revision cuts them.
   - `## <the author's concern, or "The main problem">`: the problems,
     ranked by what they cost the reader. For each: the diagnosis in
     one sentence; the evidence (counts, chapters, a quoted line); the
     craft principle and its source in one sentence; what the reader
     experiences because of it. Answer `--focus` directly here. Name
     the One-page fields (step 6) the book leaves blank.
   - `## What caused it`: the pipeline rules, staged edits and earlier
     advice from step 8, plainly, including your own.
   - `## What I recommend, in order of effect for the cost`: numbered.
     Each: the story-level move; the chapters; what it fixes; its cost
     (chapters, rough words); its risk; a direction, concrete enough for
     an author who is not a writer to judge, while the book stays the
     author's (Gottlieb: the editor finds what the book needs, the
     writer provides it); which command carries it out
     (`/autonovel:revision-pass`, `/autonovel:merge-chapters`,
     `/autonovel:remove-chapter`, `/autonovel:reorder`,
     `/autonovel:add-subplot`, `/autonovel:foreshadow`,
     `/autonovel:gen-outline --add-spine`, or "author's decision" for a
     frame or a change of POV).
   - `## What not to do`: fixes that would raise a reviewer's number or
     satisfy a rule while damaging the book.
   - `## Suggested order of work`: cheapest decisive changes first, the
     big decisions after a re-read of that draft.
   - `## Recommendations ledger`: a table with one row per
     recommendation: `id | recommendation | chapters | kind | status`,
     where kind is `in-chapter`, `cross-chapter` or `author-decision`,
     and status is `proposed`.

10. **Compare with the instruments, now.** Read
   `books/{book}/edit_logs/structure_review.md`,
   `books/{book}/edit_logs/review.md` and
   `books/{book}/edit_logs/reader_panel.json` if they exist, and the
   archived previous letter from step 3. Insert
   `## Where this read disagrees with the instruments` before the
   ledger:
   for each instrument, what it caught that you also found, what it
   missed, what it got wrong and why (which part of its rubric is
   blind), and any of its proposed fixes that would damage the book.
   If there was a previous letter, add what has changed since it and
   whether the revision did what it recommended. Do not change your
   diagnosis to match an instrument; change it only if the instrument
   points you to a passage that proves you wrong, and say so.

11. **Check the letter against the ground rules.** Every whole-book
    claim has a count or a list; at least three problems the author has
    not raised; no hedge phrase qualifies a defect; no recommendation is
    a linking sentence; every recommendation names its chapters and its
    command; the spine and theme survive every recommendation. Fix what
    fails.

12. **Print a one-screen summary:** the top three problems, the top
    three recommendations, the path of the letter and the notes, and
    whether the instruments agreed.

13. **`--stage` only.** For every ledger row whose kind is `in-chapter`,
    append one turn per chapter to `books/{book}/briefs/conversation.md`
    in the file's existing format (`## <date> — turn N — suggest`,
    `**Question / suggestion:**` quoting the letter's recommendation,
    `**Mode:** suggest`, `**Target:** chapter N`,
    `**Answer / suggestion:**` with the concrete instruction for that
    chapter, `**Status:** queued`), and set that row's status in the
    ledger to `staged`. Never stage `cross-chapter` or
    `author-decision` rows: list them for the author with the command to
    run. Without `--stage`, print the command that would stage them.

14. **Postamble next step.** Pass `--next-standard-step` to
    `autonovel _end`, filled from this run:

    ```
    1. Read the letter: books/{book}/edit_logs/editor_letter.md
       (the notes behind it: editor_read_notes.md).
    2. Decide the author-decision items it lists (<ids>).
    3. Queue the in-chapter fixes, if you agree with them:
         /autonovel:developmental-edit --book {book} --stage
       <OR "Staged: <n> turns in briefs/conversation.md." when --stage ran>
    4. Revise:
         /autonovel:revision-pass --chapters <chapters> --book {book}
    5. Re-read: /autonovel:developmental-edit --book {book}
       then /autonovel:structure-review --book {book}
    ```
</workflow>

<acceptance>
- `books/{book}/edit_logs/editor_read_notes.md` has one block per
  chapter with every field from step 5, at least one Running diagnosis
  per quarter of the book, a Measurements section, a One page section
  and a Causes in the pipeline section.
- `books/{book}/edit_logs/editor_letter.md` exists, is 1,800–3,500
  words without the ledger, has every section in steps 9 and 10,
  answers `--focus` when given, and ends with the recommendations
  ledger.
- Every whole-book claim in the letter cites a count or chapters; at
  least three problems are ones the author has not raised.
- A previous letter and notes were moved to `editor_letter_<stamp>.md`
  and `editor_read_notes_<stamp>.md` before the new ones were written.
- With `--stage`, every `in-chapter` ledger row has a queued turn per
  target chapter in `briefs/conversation.md` and its status is
  `staged`; no other row is staged.
</acceptance>
