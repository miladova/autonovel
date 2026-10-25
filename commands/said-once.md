---
name: autonovel:said-once
description: Read the whole book for what it says more than once — a fact, a rule, a count, an explanation, who someone is or an earlier scene, told again in any words — and write the ledger of where each point is told and what every other mention gets, which draft, brief, revise and evaluate check each chapter against. --stage queues each chapter's cuts for revision-pass.
argument-hint: "--book <short-name> [--stage]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - shared/craft/PROSE.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
  - books/{book}/voice.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/edit_logs/said_once_ledger.md
writes:
  - books/{book}/edit_logs/said_once_ledger.md
  - books/{book}/briefs/conversation.md
context_mode: book
---

<purpose>
A chapter evaluation reads one chapter. It can see a point made twice
inside that chapter, but not that the same point was explained eight
chapters earlier in other words, and `autonovel mechanical repeats`
finds repeated *wording*, not a point told again in new words (measured
on one book: it found about four in five places repeated in nearly the
same words and under half of the places where a point was told again in
new words). On that book the author, two-thirds into chapter 1, found it
"long and a bit slow" with "repetition", and a whole-book read found the
same in nearly every chapter: a story-so-far paragraph opening every
chapter of one strand, the vote count recited in seven chapters, an
earlier scene retold five times. Only a reader who has read the whole
book, in order, can catch those.

This command is that reader. It reads every chapter in order, keeps a
ledger of each point the book tells (where it is first told, and every
later telling, with a verdict), and writes
`books/{book}/edit_logs/said_once_ledger.md`. `/autonovel:draft`,
`/autonovel:brief`, `/autonovel:revise` and `/autonovel:evaluate` read
the ledger, so a chapter is held to the whole book's tellings, not only
its own (`shared/craft/PROSE.md` §7 rule 9, "Say it once"). With
`--stage` it also queues each chapter's cuts in
`books/{book}/briefs/conversation.md`, so `/autonovel:revision-pass`
carries them out. It never changes a chapter.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`: `--book <short-name>` (defaults via `_begin`);
   `--stage` is a flag.

2. Use `file_read` on `shared/craft/PROSE.md` §7 (rule 9 is the rule this
   command applies), `books/{book}/voice.md` (Part 3 may carry the book's
   own say-once rule) and the book's genre guide: the file `_begin`'s
   `genre:` line names (`autonovel genre show --book {book}` prints it
   when no preamble ran; it is `shared/craft/genres/<genre>.md`, or the
   series' own `shared/genres/<genre>.md`), its `## The promise` and
   `## Cutting`. In historical fiction the period is the payload: a gloss
   or a period fact stays in the book, told once; only its second
   telling is a repeat. When `books/{book}/edit_logs/said_once_ledger.md`
   exists, read it: this run replaces it, and an earlier decision on
   where a point is told stands unless the chapters have changed it.

3. Use `bash` to run `autonovel mechanical repeats books/{book} --format
   json`. Its `echoes` (the same wording at two or more places, ranked by
   how rare the words are; `quoted` marks wording inside a letter or note
   each time, `recurring` a short phrase in four or more chapters), each
   chapter's `told_before` (sentences close to one in an earlier chapter)
   and `phrases` are candidates to confirm in the read. They are not the
   ledger: the read is.

4. **The read.** Read the chapters in order, `books/{book}/chapters/ch_NN.md`,
   in full, as a reader would, keeping a running ledger as you go:
   - each time the book tells a point a reader needs (a fact, a rule, a
     sum or count, an explanation or gloss, who a person is and what they
     want, what happened in an earlier scene, the situation so far), add
     it with its chapter, line and a short quote;
   - each time it tells a point already in the ledger, in any words, add
     the mention (chapter, line, short quote) and judge it: **keep,
     deliberate** (a payoff line, a letter read again, a refrain the book
     sets up, a person's line that turns an old fact to a new purpose);
     **a clause** (a reminder after a long absence, three or more
     chapters away, as `/autonovel:draft` step 3c allows, a few words not
     a sentence); or **cut** (the reader has it);
   - note every paragraph near a chapter's start that restates the story
     so far, and every count or list recited again when only one line of
     it changed.
   Never judge a chapter from its summary.

   **Context budget.** When the chapters fit in this conversation (up to
   about 250,000 tokens), read them yourself. Otherwise use `task` to read
   the book act by act, **one act at a time, in order**: give the first
   reader the first act's chapters and this step's instructions, and each
   next reader the ledger so far and its act. A later act's reader must
   know what the earlier acts told, so the readers never run in
   parallel. Each returns its additions to the ledger with quotes; every
   decision in step 5 stays in this conversation.

5. **Where each point is told.** For each point told more than once,
   choose the one telling that stays: the first, unless a later one sits
   where the point matters more (the scene where it is at stake); give
   every other telling its verdict from step 4. A point the book needs
   that is only ever told in a repeat keeps one telling. Nothing the
   genre's reader came for leaves the book.

6. Use `file_write` on `books/{book}/edit_logs/said_once_ledger.md`, in
   this shape:

   ```
   # Said once: where each recurring point is told

   Written <date> by /autonovel:said-once from a read of chapters 1–N
   in order (<how: one reader, or act by act>). The rule:
   shared/craft/PROSE.md §7 rule 9. Nothing the genre's reader came for
   is cut: every fact stays in the book, told once.

   ## Points

   1. **<the point, in a few words>.** **Told:** ch X (L<line>, “<quote>”).
      **Elsewhere:** ch Y L<line>: cut; ch Z L<line>: a clause; ch W
      L<line>: keep, deliberate (<why>).

   ## Openings

   - ch N L<line>: restates the story so far — cut; the one fact it
     needs goes in as a clause at L<line>.

   ## By chapter

   ### Chapter N
   - L<line> (point K): cut | a clause | keep, deliberate — “<quote>”

   ## Gestures and phrases

   - “<phrase>” (ch A, B, C): vary or cut the repeats.
   ```

   Order the points by how often they are told again, most first. Under
   `## By chapter`, list only the chapters with a mention to cut or
   shorten; a chapter with none gets no heading.

7. **`--stage` only.** For each chapter under `## By chapter` with a cut
   or a clause, use `file_write` to append one turn to
   `books/{book}/briefs/conversation.md` (create it if missing), in the
   shape `/autonovel:talk` writes: a `## <date> — turn <next> — suggest`
   header; `**Question / suggestion:** say each thing once
   (/autonovel:said-once)`; `**Mode:** suggest`; `**Target:** chapter N`;
   `**Answer / suggestion:**` the standing rules (keep the telling the
   ledger keeps, improve it if needed, and never add a second
   explanation; nothing the genre's reader came for is cut; keep every
   scene, its order, every fact, date and sum, and every character beat;
   change nothing else; run the scanner afterwards), then the chapter's
   entries from `## By chapter` with their quotes; `**Status:** queued`.
   Never queue a turn for a chapter with nothing to change.

8. Report, in plain sentences: how many points the book tells more than
   once and the five told most; which chapters open on the story so
   far; the chapters with the most repeats; the ledger's path; and the
   next step: with `--stage`, `/autonovel:revision-pass --chapters
   <the staged chapters> --book {book}`; without it, `/autonovel:said-once
   --book {book} --stage` to queue the cuts, or `/autonovel:talk` to
   discuss them. Do not modify any chapter.
</workflow>

<acceptance>
- `books/{book}/edit_logs/said_once_ledger.md` exists with `## Points`
  and `## By chapter`; every point names where it is told, and every
  by-chapter entry carries a line number, a verdict and a quote.
- Every chapter was read in full, in order (by this conversation or by
  act readers run one after another), never judged from its summary.
- With `--stage`, one queued turn per chapter that has a cut or a
  clause, none for a chapter without; without `--stage`,
  `books/{book}/briefs/conversation.md` is unchanged.
- No chapter file changed.
</acceptance>
