---
name: autonovel:draft
description: Draft one chapter of a book as full prose.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - task
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
  - books/{book}/chapters/ch_{prev}.md
  - books/{book}/chapters/ch_*.summary.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/pending_canon.md
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

10. Draft the chapter. Target length comes from
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
    step 11), `story_time` (ISO date or range), `events`,
    `status: drafted`, and `word_count`.

13. **Write the chapter summary.** Use `file_write` to save a
    150–250 word summary at
    `books/{book}/chapters/ch_{chapter}.summary.md`. Cover seven
    things, each as a one or two sentence section:
      - **Plot:** what happened in this chapter (action, decisions,
        outcomes — not theme).
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
</acceptance>
