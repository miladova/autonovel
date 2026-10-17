---
name: autonovel:gen-outline
description: Generate the outline for one book from its seed, world, and characters.
argument-hint: "--book <short-name> [--force] [--add-spine]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/events.md
  - books/{book}/seed.txt
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_*.summary.md
writes:
  - books/{book}/outline.md
context_mode: book
---

<purpose>
Produce `books/{book}/outline.md`: a chapter-by-chapter plan (Layer-2) for
one book. Each chapter entry names its story_time, any series events it
renders (`E-###` ids from `shared/events.md`), and its beats — the
concrete moves, not the abstract theme. Drafting reads this file for every
chapter, so specificity now saves revision later.

The outline also commits to the book's **spine** in three parseable
sections that `/autonovel:draft`, `/autonovel:draft-pass`,
`/autonovel:evaluate` and `/autonovel:structure-review` read:

- `## Spine` — the one question the book asks and answers, the
  protagonist's want, the opposing force that persists across acts.
- `## Stakes ladder` — one row per act: what can be lost, and why it is
  strictly more than the act before.
- `## Causal spine` — one line per chapter: `- N because M: <the event
  in chapter M that forces chapter N>`.

A sequence of good scenes is not an outline. An outline that makes
every chapter "a wager: the first beat names what the POV can lose, the
last beat settles or raises it" drafts into a string of well-written
anecdotes. A chapter-local stake is fine only
when its result is the next chapter's problem.

`--add-spine` retrofits the three sections onto an existing outline
without touching its chapter entries — the path for books outlined
before these sections were required.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. If missing, stop and
   surface a one-line usage reminder. `--force` permits overwriting a
   populated outline. `--add-spine` switches to retrofit mode (step 9).

2. Use `file_read` on `project.yaml`. Resolve the book entry. Capture
   `pov`, `story_time_range`, and `defaults.chapter_target_words` — the
   outline's chapter count should roughly match
   `seed.txt target length ÷ chapter_target_words`, honoring any chapter
   count already implied by the seed.

3. Use `file_read` on `books/{book}/seed.txt`. This is the authorial
   intent. If the seed states a chapter count or length, honor it.

4. Use `file_read` on `shared/world.md`, `shared/characters.md`, and
   `shared/events.md`. Any chapter whose story_time overlaps a registered
   event's `canonical` window must either render that event (list the
   `E-###` id) or step deliberately around it.

5. Use `file_read` on `books/{book}/voice.md`. Part 1 (series voice)
   constrains the kinds of scenes that belong in this book.

6. Use `file_read` on `books/{book}/outline.md`. If it contains more than
   the template placeholder and neither `--force` nor `--add-spine` was
   supplied, stop.

7. Draft the spine first, then the chapters that serve it.

   a. **`## Spine`** — key: value bullets:
      - `question:` the one question about the protagonist the book
        asks and the climax answers (yes/no or which-way), ending in
        `?`. Not a theme.
      - `posed_in:` the chapter that first poses it — in the first
        quarter of the book.
      - `answered_in:` the chapter whose decision answers it.
      - `want:` what the protagonist wants across the whole book.
      - `opposing_force:` who or what opposes that want in every act
        (one person or institution that persists, not a new obstacle
        per act).
      - `cost:` what answering the question costs.

   b. **`## Stakes ladder`** — a table, one row per act:

      ```
      | Act | Chapters | Stake | Higher than the last act because |
      |---|---|---|---|
      | I | 1-6 | <what can be lost> | (opening stake) |
      | II | 7-12 | <…> | <why strictly more, and still the same bet> |
      ```

      Each act raises the same bet: more to lose on the through-line
      question, or a deeper kind of loss (a life over money, a self over
      property). A bigger number with a new counterparty is a reset, not
      a raise.

   c. **The chapters**, grouped under one `## Act <I, II, …> — <name>`
      heading per act (the same acts as the ladder), each heading
      followed by one line saying what the act's stake is and what in
      the previous act forces it. For each chapter:
      - `## Chapter N — <title>`
      - `- story_time: <ISO date or date range within the book's story_time_range>`
      - `- events: [E-001, ...]` (may be empty)
      - `- beats:` followed by 3–6 concrete beat lines. A beat names what
        changes in the scene; a theme is not a beat. The first beat
        names what the previous chapter's result forces now; the last
        beat leaves the fact the next chapter acts on.
      Structure across chapters: stable rising action, a midpoint
      reversal, a costly climax in which the open threads meet in one
      decision. Never end on a round-edged resolution — the "Stability
      Trap" is an AI tell where the ending neutralises every posed
      threat. Push toward irreversible change, real cost, and one
      unanswered mystery the next chapter can pull on.

   d. **`## Causal spine`** — one line per chapter from 2 to the last:

      ```
      - 2 because 1: <the event in chapter 1 that forces chapter 2>
      - 7 because 4, 6: <…>
      - 13 after 12: <why this link is only sequence — a known weak link>
      ```

      `because` lines name an event in an earlier chapter (who did
      what), not a recurring object, a motif, a callback or a carried
      date. Write `after` only when a chapter genuinely opens on
      something outside the book's prior action; every `after` line is
      a weak link the drafter and the structure review will see — keep
      them few, and none at an act boundary. If you cannot write a
      `because` line for a chapter, change the chapter, not the line.

   **Historical fiction** (project.yaml `period` set): the record is
   episodic — deals, deaths, elections, wars arrive on their dates. The
   outline must impose the spine the history lacks: the opposing force
   that persists between recorded events, and for each recorded event
   the earlier choice of the protagonist that it punishes or rewards.
   Never change a recorded date or outcome to get a `because`.

8. Use `file_write` to replace `books/{book}/outline.md`. Start with
   `# Outline`, then any preamble line, then `## Spine`, `## Stakes
   ladder`, the act headings and chapter entries, and `## Causal spine`
   last. No frontmatter.

9. **`--add-spine` (retrofit).** Read the existing outline and every
   `books/{book}/chapters/ch_NN.summary.md` that exists. Write the
   three sections from what the outline (and the drafted chapters)
   actually do — honestly: a link that is only sequence is written
   `after`, a question first posed late gets that late `posed_in`, an
   act whose stake resets says so in its "higher because" cell. Insert
   `## Spine` and `## Stakes ladder` after the preamble and append
   `## Causal spine` at the end. Leave every `## Chapter N` entry and
   act heading byte-for-byte unchanged, and replace an existing spine
   section rather than adding a second. Print the `after` links and
   reset rungs you found — they are the outline-level shape of what
   `/autonovel:structure-review` will flag in the prose.
</workflow>

<acceptance>
- `books/{book}/outline.md` exists and begins with `# Outline`.
- At least three `## Chapter N` headings, each with `story_time`,
  `events`, and `beats` sub-items.
- Every `story_time` falls within the book's `story_time_range` from
  `project.yaml`.
- Every `E-###` id referenced in `events:` exists in
  `shared/events.md`.
- The outline has a `## Spine` section whose `question:` ends in `?`, a
  `## Stakes ladder` with one row per act, and a `## Causal spine` with
  one `- N because|after M: …` line for every chapter after the first
  (`autonovel mechanical structure-dossier books/{book}` reports no
  outline spine warnings).
- With `--add-spine`, every chapter entry is unchanged.
</acceptance>
