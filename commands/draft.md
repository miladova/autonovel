---
name: autonovel:draft
description: Draft one chapter of a book as full prose.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - task
  - bash
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - shared/events.md
  - shared/research/notes/*.md
  - shared/craft/*.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/design.md
  - books/{book}/cast.md
  - books/{book}/glossary.md
  - books/{book}/chapters/ch_{prev}.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/edit_logs/last_read.json
writes:
  - books/{book}/edit_logs/first_read_ch{chapter}.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/pending_canon.md
  - books/{book}/edit_logs/diff_*.html
  - books/{book}/edit_logs/diff_*.json
  - books/{book}/edit_logs/story_map.html
  - books/{book}/edit_logs/story_map.json
context_mode: book
---

<purpose>
Write chapter `{chapter}` of book `{book}` as full prose, obeying the series
voice, world, characters, outline beats, and canon. Respect story-time:
chapters from other books with `story_time` less than or equal to this
chapter's `story_time` are readable context; chapters later in story-time are
off-limits.
</purpose>

<workflow>
**Read-failure policy.** When `file_read` errors (file not found,
permission denied, encoding error) on any input that's NOT the
load-bearing chapter file, do NOT retry. Note the gap in your
working memory + the postamble's eval-log write, and proceed
without that input. The author hit retry-loops 2026-04-25 on
non-existent prior chapters and on summary files that hadn't
been backfilled yet; the right response is "this prose-context
input is missing, draft anyway with what's available". The single
exception is reads that load the chapter we're writing-against
(`/autonovel:revise` step 6); those are the *only* truly
required reads — surface the error and stop, don't retry.

1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`. If the
   chapter number or `--book` is missing, stop and print a one-line usage
   reminder. Do not touch disk. Accept an optional `--force` flag (used
   below in step 1a).

1a. **Edit-imported guard.** Use `file_read` on `project.yaml`.
    If `books[<book>].mode == "edit-imported"` and `--force` is
    not in `$ARGUMENTS`, stop with this message:

    ```
    refusing to draft chapter <N> — book is in `edit-imported`
    mode (the prose was supplied via /autonovel:import-book).
    Pass --force to add a new chapter anyway, or use
    /autonovel:revise <N> --book <book> if you meant to edit
    the existing chapter.
    ```

    The user's manuscript is the load-bearing input in
    edit-imported mode; running draft would clobber it.

2. Use `file_read` on `project.yaml` again (or reuse from step 1a).
   Resolve the book entry, its `pov`, and the defaults block
   (`chapter_target_words`, `chapter_threshold`).

3. Use `file_read` on `books/{book}/outline.md`. Locate the entry for chapter
   `{chapter}`. Capture its beats, its `story_time`, and any events it
   references. If the chapter is not in the outline, stop and surface the gap.

3a. **Hold the chapter to the book's spine.** From the same outline,
    read the `## Spine` section (the through-line `question:`, `want:`,
    `opposing_force:`), this chapter's act row in `## Stakes ladder`,
    and two lines of `## Causal spine`: `- {chapter} because M: …` (what
    this chapter must open on — the earlier event that forces it) and
    `- {chapter+1} because {chapter}: …` (the fact this chapter must
    leave for the next one to act on). These are binding, like the
    beats:
    - the chapter's first scene acts on the named earlier event —
      someone does something *because of it*, on the page — rather than
      opening on a fresh problem;
    - the chapter's stake is its act's rung on the ladder, on the
      through-line question — not a new, self-contained bet that the
      chapter opens and settles;
    - the chapter ends with the hand-off fact in place, unresolved
      enough that the next chapter has to deal with it.
    A `- {chapter} after M:` line is a known weak link: draft it, and
    still give the chapter one consequence of an earlier chapter if the
    beats allow. When the outline has none of these sections (outlined
    before they were required), draft from the beats alone and add one
    line to the postamble: "outline has no causal spine — run
    `/autonovel:gen-outline --book {book} --add-spine`". Do not stop.

3b. **Hold the chapter to the design** (when `books/{book}/design.md`
    exists; `/autonovel:design` writes it). Read from it:
    - the `## Cast` entry of every principal in this chapter's beats:
      give each a want in every scene they enter, play their
      `signature:` (the gesture, object or habit of speech), let their
      `contradiction:` show at least once, and keep their `secret:`
      hidden unless the beats expose it;
    - the `## Places` entry for the chapter's setting: use the place for
      what its `use:` says, bring in its `signature:` sense details, and
      when the chapter arrives somewhere or stages a set piece, describe
      the place fully and concretely through the viewpoint's attention
      (what this person, wanting this, would notice), accurate to the
      year — description thins only in the chase;
    - the `## Plants` rows for the ids on this chapter's `plants:`,
      `tests:` and `payoffs:` lines. A **plant** is acquired inside the
      chapter's own contest, while something else is at stake: never
      explained to the reader, never flagged as important, never
      forecast. A **test** uses it once at small stakes or shows it in a
      new light. A **payoff** spends it where it decides the outcome,
      so a reader recognises it without being reminded in a paragraph;
    - `## Voice` (with `voice.md`, which wins on line-level detail) and
      `## Opponent` (if he is on stage, he wants something in the scene
      and the reader sees his plan working).
    A win the protagonist earns turns on knowledge the reader saw him
    acquire, never on a wager or the odds (`shared/craft/DESIGN.md` §15).

3c. **The reader's map** (every book). A reader who stops because they
    are lost is gone; a reader who has to look a word up is half gone.
    - **Explain at first use.** Every institution, office, title, coin,
      trade word or foreign word a reader today may not know is
      explained in plain words the first time it appears in the book —
      in the same sentence or the next, through the scene where it can
      be (a character's question, a thing seen being used), as briefly
      as the scene allows: *the seven electors, the princes who by an
      old law chose the man who would be Emperor*; *fustian, the cheap,
      hard-wearing cotton-and-linen cloth the family had made its money
      on*; *the Marangona, the great bell of St Mark's that opened and
      closed the working day*. Read the earlier chapters' summaries and
      `books/{book}/glossary.md` (if present) to know what the reader
      has already been told; once explained, a word is used freely.
      When `design.md` has a `## Terms` section, explain each term in
      the chapter it names.
    - **One new person at a time.** Each new character arrives with
      name, who they are to the viewpoint character, and one concrete
      detail. Name only the people the scene needs; no more than three
      new named people or places on a chapter's first page.
    - **The first page orients.** Where we are, when, and what is at
      stake for the viewpoint character today, in plain statements
      before any flourish. In a book that moves between times or
      places, the chapter's `dateline` (step 12) does half of this and
      the first paragraph does the rest.
    - **What a place was like then: the set piece.** A major place's
      first appearance in the book gets a set piece, not a paragraph.
      Give the plain picture of it in its own time — how big, who ruled
      it, what it lived on, what made it unlike anywhere else or unlike
      today (`design.md` `## Places` `orientation:`) — and then walk it
      through the viewpoint character's eyes: what this person, wanting
      what they want today, sees, hears, smells, pays for, is frightened
      or dazzled by. Mix the two, a sentence of fact and then the street,
      so the picture never stops the story for a lecture. A guide is the
      natural device: a newcomer shown round by someone who lives there
      and has reasons of their own. Use the research: the places notes
      in `shared/research/notes/` carry walks, only-here details and set
      pieces gathered for exactly this, and a set piece that uses none of
      them is a wasted arrival. Budget roughly 600–1,200 words for a
      major place's first set piece, spread across the chapter's scenes
      if need be; a minor place gets a few lines. When the design names
      a place's `set_piece:`, stage it there. When the place returns,
      give its signature in a line and what has changed.
    - **Re-anchor whoever returns.** A person, place or term the reader
      last met more than a chapter ago — and anyone from the other
      strand, in a book that alternates — is re-anchored in a clause the
      first time they come back: who they are and what they want, through
      action where the scene allows (*Albrecht, the young Archbishop of
      Mainz who spent faster than anyone Jakob knew, wanted cash in his
      hand*). In an ensemble — a council, seven princes — re-anchor each
      member every time the group comes on stage, until the book has
      shown each of them often enough to stand alone. `books/{book}/cast.md`
      `return tag:` lines give the facts; vary the wording.
    - **Plain over clever.** When `voice.md` asks for plain English,
      no figure of speech the reader has to decode ("rode as if the
      saddle owed him money"), no compressed witty construction whose
      referent is ambiguous ("vain, gifted and young, and he knew all
      three"), no idiom of recognition ("knew him by the way he sat the
      horse"): say the thing.

3d. **People with depth** (every book). Use `file_read` on
    `shared/craft/CHARACTER.md` and, when it exists, on
    `books/{book}/cast.md` (the dossiers `/autonovel:cast` writes). A
    character who appears with a trait and a habit and nothing else is a
    type — "a cluster of traits stuck on a name" — and a reader feels it
    within a page. For everyone on stage who matters in this chapter
    (CHARACTER.md §4):
    - **A want of their own in the scene**, apart from the viewpoint
      character's, showing in what they ask for, hide, refuse or reach
      for; secondaries bring business of their own into the room.
    - **Choice, not label**: no narrator's verdict ("the vainest man
      in town"); a choice that costs. When the dossier's choice ladder
      names this chapter, stage that choice.
    - **The contradiction acted** in what the person does, and **stress
      behaviour, not a tic**: a habit recurs only when it shows something
      new; under pressure they do their particular thing, and it costs.
    - **The viewpoint's hinterland**: at least three of a feeling he won't
      admit, a memory, a desire apart from the scheme, an opinion of
      someone, a fear, a misreading — one pulling against his own plan —
      and the body (age, fatigue, cold, hunger). Not only calculation.
    - **Under- rather than over-articulate**: in charged talk people say
      less than they mean; the history between the two (who owes whom,
      an old grievance or affection) shapes what is said, and each pair
      has its own register.
    - **Who knows what**, in scenes of secrets and deals: let the reader
      track what each person believes the others know, to about four
      layers and no deeper.
    - **Real people from the record**: their recorded words, acts and
      contradictions (the research notes and cast.md cite them), in the
      mind of their own time; invent only in the record's silences, never
      against it, and never shrink them to their reputation.
    - **Witness, don't judge**: no verdict from the narrator on a person
      or on the values of their time.
    Use the dossier's `on the page` line for this chapter: show the thing
    about each person that no earlier chapter has.

4. Use `file_read` on `shared/world.md`, `shared/characters.md`,
   `shared/canon.md`, `books/{book}/canon.md` (this book's OWN canon —
   facts its earlier chapters established; a sibling book's canon.md is
   never read), and `shared/events.md`. For every event the outline
   references, use only the `canonical` field and this book's
   `rendered_in` row from `shared/events.md` — ignore other books' POV rows.

5. Use `file_read` on any `shared/research/notes/*.md` that the outline entry
   for this chapter names explicitly. Do not load the full research tree.

6. Use `file_read` on `books/{book}/voice.md`. Parts 1 (series voice),
   2 (book fingerprint), 3 (custom rubric, when present), AND 4
   (per-character voice fingerprints, when present) are all in
   scope.

   Part 3 lists book-specific writing rules that must be honoured
   at draft time — drafting against the rules is cheaper than
   revising back to them. Treat each Part 3 bullet as a hard
   constraint on the chapter's prose.

   Part 4 lists per-character voice fingerprints. When present,
   apply each character's block at every line of their dialogue
   AND (for the POV character) at every interiority sentence.
   This is the antidote to the "all characters sound the same"
   AI tell — without per-character voicing, every speaker tends
   to converge on the narrator's register. Verify before writing
   each dialogue exchange: which character is speaking, what's
   in their Part 4 block, does the line you're about to write
   honour Speech / Verbal tics / Refuses? If Part 4 is empty or
   absent (solo-cast book, or the cast threshold wasn't met),
   fall back to Part 2 alone.

7. **Best-effort prior-chapter quote (do not retry on failure).** Use
   the `Bash` tool to run, exactly once:

   ```
   autonovel _tail-chapter --book {book} --chapter {prev} --words 1000
   ```

   The helper reads `books/{book}/chapters/ch_{prev}.md`, strips any
   YAML frontmatter, and prints the last 1000 words to stdout — no
   `file_read` line-range gymnastics. If the prior chapter doesn't
   exist, the helper exits zero with no output; that's normal for
   chapter 1. Capture the
   stdout as your continuity flavour. **Do not retry** on any failure
   (non-zero exit, empty output, error message): note the gap as a
   one-line observation you'll repeat in the postamble's eval-log
   write, and proceed to step 8. Step 8 (per-chapter summaries) is
   the *load-bearing* continuity surface; this last-1000-words
   quote is a flavour assist the chapter can be drafted without.
   We use the helper specifically to prevent the loop autonovel
   hit on author testing 2026-04-25, where `Read` with an off-by-one
   `offset/limit` triggered retry attempts on a prior chapter
   shorter than the requested line range.

8. **Read every prior summary** for narrative continuity. Use `file_read`
   on `books/{book}/chapters/ch_*.summary.md` for chapters 1 through
   `{prev}` (any that exist). Each file is ~150-250 words and contains
   the chapter's plot, character moves, threads opened, threads
   resolved. **These summaries are the load-bearing continuity
   context** that prevents chapter N from forgetting what chapter 1
   set up — much more important than the step-7 quote. If a summary
   is missing for a drafted chapter — likely a chapter drafted before
   this step shipped — note the gap but do not regenerate it inline;
   the user can backfill via `/autonovel:summarize-chapter`.

9. Sibling-book context. First check this book's entry in `project.yaml`:
   if it carries `context: isolated`, **skip this step entirely** — load no
   chapter from any other book (the book is a rewrite / second version of a
   story another book already tells, and the old prose must not anchor the
   new draft; shared/ lore above is still in force). Otherwise use `task` to
   fan out loading of sibling-book chapters whose `story_time` is less than
   or equal to this chapter's `story_time` (`python -m
   autonovel.context_loader --book {book} --chapter {chapter}` lists exactly
   which files are legal). Budget the loader — truncate oldest first,
   summarize rather than quote beyond ~8000 tokens.

10. Draft the chapter. Target length: when `books/{book}/design.md`
   exists, its `## Shape` `target_words` divided by `chapters`, rounded
   to the nearest hundred (the design chose the book's length and
   chapter count together); otherwise
   `project.yaml :: defaults.chapter_target_words`. Before writing, use
   `file_read` on the craft reference documents in the series:
   `shared/craft/PROSE.md` (sentence, paragraph, scene and dialogue
   mechanics, with sources), `shared/craft/CRAFT.md` (structure,
   character, show/tell, the stability trap), `shared/craft/ANTI-SLOP.md`
   and `shared/craft/ANTI-PATTERNS.md` (banned phrases and tics). If
   `shared/craft/` is missing, run `autonovel refresh-templates` with
   `bash` first; it copies the package's current versions into the
   series. Obey all four. Do not use any word that appears in
   `shared/period_bans.txt`.

   **Register self-check before the summary.** When the draft is
   written, run `autonovel mechanical register books/{book}
   --chapter {chapter}` with `bash`. It measures narration and
   dialogue separately: Flesch-Kincaid grade, contraction ratio,
   uncontracted negatives, formal connectives, utterances over 40
   words, and lines that explain to the listener what the listener
   can see. Read the candidates against `books/{book}/voice.md`
   (its `FK grade band: L–H` line and its refusals) and fix them in
   the draft now: a narration that never contracts a negative, a
   character delivering a 100-word lecture, or a line like "That's
   the bell, at the end there" is the register failure a reader
   hears first, and the judge scores it as `register`. Period nouns
   are fine; formal grammar under modern vocabulary is not.

   **Reader's-map self-check** (step 3c). Run `autonovel mechanical
   newcomers books/{book} --chapter {chapter} --format markdown`: it
   lists the names and terms that appear for the first time in the book
   in this chapter, which land in the opening, and which return after an
   absence. For each, check that
   a new person arrives with who they are, that an unfamiliar term or
   foreign word is explained in plain words where it first appears, and
   that the opening doesn't introduce more than about three new names;
   and, under "returning", that each person or place back after an
   absence is re-anchored (step 3c); fix the draft where it doesn't.

   **First reader** (always, before the summary). Use `file_read` on
   `shared/craft/FIRST-READER.md` and spawn, with `task`, one fresh
   heavy-tier reader exactly as that brief says: it is given only this
   chapter and the earlier chapters (the last three in full and the
   rest as summaries when the book is long) — never the outline,
   design, research, voice file or your notes — and it reports in the
   brief's ten sections, quoting the text. Save its report at
   `books/{book}/edit_logs/first_read_ch{chapter}.md`. Then fix every
   item under Lost, Didn't know, Read twice, Too many at once and Forgot
   who; give each place under Couldn't picture its picture (step 3c's
   set piece); deepen each person under Who felt real who read as a
   type (step 3d); and treat a Skimmed-or-bored stall or a "no" to the
   page turn as a scene to rework before anything else. When the report
   had serious items, spawn a second fresh reader on the fixed chapter
   and fix what it finds. Your own checks can't see what you already
   know; this reader can. The author must never be the first person to
   find an unexplained word or a sentence that has to be read twice.

   **Precedence.** The `shared/craft/` documents are series-wide
   defaults. Where `books/{book}/voice.md` Parts 1–3 explicitly
   override one of them (a plain-register thriller that says "telling
   is allowed" or "CRAFT.md §6 does not apply", for instance), the
   voice file wins. PROSE.md is register-neutral and is not expected
   to need overriding; CRAFT.md §5–6 describe a register and a book's
   voice file is where the author's register is recorded.

11. **Write a 2-6 word evocative chapter title.** Concrete object
    or phrase from the chapter's central beat — what the chapter is
    *about*, not a plot summary. Examples: "The Apothecary's
    Mortar", "What Tommaso Knew", "Carnival Hours", "Salt and
    Saltpeter". Avoid cliché ("The Beginning", "A New Hope"),
    avoid POV-character names alone (the running header already
    shows POV via `\chaptermark`), avoid generic abstractions
    ("Confrontation", "Decision").

    The title goes into the chapter's YAML frontmatter `title:`
    field; typeset surfaces it in the TOC, the chapter opening
    page, and the running header. project.yaml ::
    typeset.chapter_titles = false (default true) opts out of
    this and reverts to numbered-only chapters.

12. Use `file_write` to write `books/{book}/chapters/ch_{chapter}.md`. Start
    with a YAML frontmatter block per `docs/chapter-frontmatter.md`:
    `book`, `chapter`, `pov`, `title` (the 2-6 word title from
    step 11), `dateline` (place and date as a reader sees them under
    the chapter title — "Augsburg, January 1519", "Venice, autumn
    1473"; copy the outline entry's `dateline:` when it has one, and
    always set it when the book's chapters move between times or
    places), `story_time` (ISO date or range), `events`,
    `status: drafted`, and `word_count`.

13. **Write the chapter summary.** Use `file_write` to save a
    150–250 word summary at
    `books/{book}/chapters/ch_{chapter}.summary.md`. Cover seven
    things, each as a one or two sentence section:
      - **Plot:** what happened in this chapter (action, decisions,
        outcomes — not theme), opening with the earlier event this
        chapter acts on and ending with the result the next chapter
        has to deal with.
      - **Location:** the dominant setting in compact form, e.g.
        `Venice / Rialto`, `Augsburg / Fugger counting-house`,
        `Padua road`. One short phrase. When the chapter spans
        multiple locations, name the primary one (where the most
        on-page time happens) optionally with `+ <other>` after.
        This is what `/autonovel:chapter-summary` displays in the
        Plot column for at-a-glance "which chapters are set in X?"
        filtering — keep it succinct.
      - **POV state:** what the POV character knows, wants, fears at
        the close that they didn't at the open.
      - **Cast on stage:** every named character who appeared,
        with their role in this chapter (e.g. "Tommaso — POV;
        Niccolò — first appearance, declined to speak").
      - **Threads opened:** new mysteries, conflicts, promises this
        chapter introduced that future chapters need to pay off.
      - **Threads closed:** earlier setups this chapter resolved
        (cite the earlier chapter when known).
      - **Story time:** the ISO date or date range covered.
    Future drafts read this file as continuity context (step 8). It
    is NOT a chapter summary for the reader — it is a continuity
    handoff to the next drafter.

14. Use `file_write` to append any new candidate canon facts to
    `books/{book}/pending_canon.md` (promote-canon routes them into this
    book's `canon.md`; only research-cited facts reach `shared/canon.md`).
    If none are new, append a single line
    noting that no new facts were discovered in this chapter. Never edit
    `shared/canon.md` directly — that is what `autonovel promote-canon` is for.

15. **A redraft goes back to the author as a diff.** Only when step 12
    wrote over a chapter file that was already there (a redraft — a new
    chapter is read whole): use `bash` to run, from the series root,

    ```
    autonovel mechanical diff-chapters --book {book} --from last-read --chapters {chapter} --if-read
    ```

    exactly as `/autonovel:revise` step 12 does. It compares the
    chapter as the author last read it (the version
    `books/{book}/edit_logs/last_read.json` records) with the redraft,
    writes the page `books/{book}/edit_logs/diff_*.html` with its
    `diff_*.json` and the story map `story_map.html` / `story_map.json`
    rebuilt beside it, and prints `"skipped": "<reason>"` (write nothing
    about it) when the author has no bookmark or had not read this
    chapter. Otherwise end the report with "What changed in chapter
    {chapter} since you last read it: <open> (<html>) — <hunks> changes,
    <big_hunks> big". Never pass `--mark-read`. Best-effort: on a helper
    failure, say so in one line and finish.
</workflow>

<acceptance>
- `books/{book}/chapters/ch_{chapter}.md` exists and is at least 2000 words.
- Its YAML frontmatter parses and contains `book`, `chapter`, `pov`,
  `story_time`, `events`, and `status: drafted`.
- `books/{book}/chapters/ch_{chapter}.summary.md` exists and is between
  100 and 400 words.
- `books/{book}/pending_canon.md` has at least one new line appended (either
  a candidate fact or an explicit no-new-facts marker).
- No case-insensitive word-boundary match of any word from
  `shared/period_bans.txt` appears anywhere in the chapter body.
- A redraft of a chapter the author had read ends with the diff page
  from step 15.
</acceptance>
