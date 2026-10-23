---
name: autonovel:design
description: Design the book before it is outlined — the climax, the question it answers, the one action, the opponent's dated plan, the plants the climax spends, the rehearsals, the cast web, sequences, places and voice — into books/{book}/design.md, tested against DESIGN.md Part II and read cold by a second reader. --from-book re-designs a drafted book as a new, isolated book that keeps its facts and art.
argument-hint: "--book <short-name> [--from-book <from_book>] [--notes \"<the author's direction, in their words>\"] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - project.yaml
  - shared/craft/DESIGN.md
  - shared/craft/EDITING.md
  - shared/craft/CRAFT.md
  - shared/world.md
  - shared/characters.md
  - shared/events.md
  - shared/canon.md
  - shared/research/notes/*.md
  - books/{book}/seed.txt
  - books/{book}/design.md
  - books/{book}/briefs/conversation.md
  - books/{from_book}/seed.txt
  - books/{from_book}/edit_logs/editor_letter*.md
  - books/{from_book}/edit_logs/structure_review.md
  - books/{from_book}/edit_logs/review.md
  - books/{from_book}/chapters/ch_*.summary.md
  - books/{from_book}/briefs/conversation.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
writes:
  - books/{book}/design.md
  - books/{book}/seed.txt
  - books/{book}/typeset/plates.yaml
  - project.yaml
context_mode: book
---

<purpose>
Make the decisions that decide whether a book reads as one story, before
anything is outlined or drafted, and write them down where the outline,
the drafter and the reviewers can be held to them:
`books/{book}/design.md`.

Drafters execute the outline and the outline executes the design. When
nobody designs, the outline becomes a list of good scenes in date order
and the book drafts into a string of well-written episodes, which no
amount of in-chapter revision repairs. One book in this pipeline was
revised four times after an editor's diagnosis and still read as
episodes; the fault was a design nobody had written down. This command
is where it gets written down. The author is not expected to be a writer
or an editor: they say what the book should be, and this command turns
that into a design a professional would sign off.

It works from the climax backward (`shared/craft/DESIGN.md`): first the
scene in which the protagonist, by his own act and at his own cost,
answers the book's question; then the question, the one action and
span, the rival who wants the same prize, what the protagonist must know
and be able to do to win (each skill planted inside a contest of its
own, tested, then spent), the smaller rehearsals of the climax, the cast
as a web of different answers, the sequences that hand their results
on, the clocks, the places and the voice. It tests the design against
DESIGN.md Part II (D1–D14), has a second reader read it cold, and
validates its shape mechanically.

`--from-book <from_book>` (a drafted book) is the re-design loop. When a
developmental edit finds design-level faults (no single action, no
lasting opponent, the question posed late, a span told by calendar,
wins by luck), the remedy is a new design and a redraft, not chapter
briefs. With `--from-book`, the command creates `{book}` as a new,
isolated book in the series if it does not exist (`context: isolated`,
so drafters never read the old prose), copies the old book's art,
reads the old book's editor's letters, structure review, review and
chapter summaries (never its chapters), and writes a keep-ledger (what
worked and has a place in the new design) and a fault-ledger (each
diagnosed fault and the design decision that prevents it). Facts carry
forward through the shared research, canon and cast; the shape does
not.

`--notes "<text>"` is the author's direction in their own words. It
wins over the seed and over any earlier direction.
</purpose>

<workflow>
1. **Parse `$ARGUMENTS`.** `--book <short-name>` is required.
   `--from-book <name>` names a drafted book to re-design from.
   `--notes "<text>"` carries the author's direction verbatim. If
   `books/{book}/design.md` exists with more than a placeholder and
   `--force` is absent, stop and say so in one line (offer `--force`).

2. **Study first.** Use `file_read` on `shared/craft/DESIGN.md` in
   full. Then read, in `shared/craft/EDITING.md`, the card (§0) and the
   questions the design card cites: P1–P3, S1, S3, S8, S9, C1–C6,
   A1–A3, V1–V3, R1, E1–E2 and, for a historical book, Part III, for a
   thriller, Part IV. Read `shared/craft/CRAFT.md` §4 (foreshadowing).
   Read the book's genre guide: the file `_begin`'s `genre:` line names
   (`autonovel genre show --book {book}` prints it when no preamble ran;
   it is `shared/craft/genres/<genre>.md`, or the series' own
   `shared/genres/<genre>.md`): `## The promise`, the `## Subgenres`
   entry for each of
   the book's subgenres, and `## Design`. The subgenres' "must deliver"
   lists join the `## Genre contract`; when `## Design` asks for a
   ledger (historical fiction's `## What the reader comes to learn`),
   write it, each item with its chapter and how it is delivered, spread
   so no chapter carries none and the last act still teaches.
   The design is built to pass those questions; you will cite them in
   the tests.

3. **A new book from a drafted one** (`--from-book`). Use `bash` from
   the series root:
   a. If `books/{book}/` does not exist, create it as an isolated book
      with the drafted book's POV and story-time range (read them from
      the `{from_book}` entry in `project.yaml`):

      ```
      autonovel new-book {book} --isolated --pov "<pov>" --story-time-range <first>-<last>
      ```

      Then copy the `title:` and `author:` of the `{from_book}` entry
      onto the new entry in `project.yaml` (edit only those two keys;
      leave every other line as it is).
   b. Copy the art if the new book has none: `books/{from_book}/art/`
      to `books/{book}/art/`, and `books/{from_book}/typeset/plates/`
      with `books/{from_book}/typeset/plates.yaml` to
      `books/{book}/typeset/`. The plates' `chapter:` numbers belong
      to the old book; leave them, and say in the report that the
      outline step reassigns them.
   c. Read the drafted book's record of what failed and what worked:
      every `books/{from_book}/edit_logs/editor_letter*.md` (newest
      first), `books/{from_book}/edit_logs/structure_review.md`,
      `books/{from_book}/edit_logs/review.md`, every
      `books/{from_book}/chapters/ch_*.summary.md`, its
      `books/{from_book}/seed.txt` and the author's turns in
      `books/{from_book}/briefs/conversation.md`. **Never read the
      drafted book's chapter files**: the new book must not inherit
      their shape or sentences.

4. **Read the facts.** `project.yaml`; `books/{book}/seed.txt` (unless
   it is the template placeholder); `books/{book}/briefs/conversation.md`
   if present; `shared/world.md`, `shared/characters.md`,
   `shared/events.md`, `shared/canon.md`; and the research notes under
   `shared/research/notes/`. Design is where the facts are chosen, so
   read every note whose subject the climax, the opponent, the cast or
   a candidate sequence touches; skim the headings of the rest.
   Historical books: real dates and outcomes are fixed; invent only in
   the gaps, and mark invented people `(invented)`.

5. **The author's intent.** List every explicit direction the author
   has given: `--notes` first and verbatim, then the seed, then the
   author's turns in `briefs/conversation.md` (the drafted book's,
   with `--from-book`), newest winning on conflict. Each becomes a
   bullet under `## Author's intent` saying how the design honours it,
   or stating a departure and the reason, for the author to accept or
   overrule. Where an old seed rule produced a diagnosed fault (a
   pacing rule that made every chapter its own contest, a style rule
   the author now rejects), name the rule and drop it.

6. **Decide, in the card's order** (DESIGN.md §0: climax → question →
   one action and span → opponent → protagonist and skills → plants →
   rehearsals → cast → sequences → clocks and stakes → places →
   voice), and write `books/{book}/design.md` with `file_write` in
   this grammar (`autonovel mechanical design-validate` parses it;
   prose under any bullet is free):

   ```
   # Design — <Title>

   ## Author's intent
   - "<direction, quoted>" (source): honoured by <…> | departure: <reason>

   ## Pitch
   <one paragraph, under 100 words: who wants what, against whom, by when, at what cost>

   ## Dramatic question
   - question: <one question a reader waits on, ending in ?>
   - posed_in: <chapter, in the first quarter>
   - posed_by: <the character who asks it on the page, and how>
   - answered_in: <the climax chapter>
   - in doubt: <for each act, what keeps the answer open>

   ## Climax
   - chapter: <N>
   - scene: <place, date, who is in the room and what each wants>
   - action: <what the protagonist does that no one else could>
   - spends: <P-ids — at least three, from at least two acts>
   - cost: <what he gives up or risks>
   - threads: <the rival, the intimate, the mentor's lesson, the secret — how they meet here>

   ## Shape
   - pattern: <DESIGN.md §3 pattern(s), e.g. education-and-campaign + many locks>
   - span: <first year–last year>, and why this span
   - chapters: <N>
   - target_words: <N>
   - redesign_of: <from-book>        (only with --from-book)
   - proportion: <which chapters each phase gets, and why>

   ## Controlling idea
   <value + cause, one or two sentences>

   ## Protagonist
   - name / want / need / misbelief / wound / contradiction / signature
   - attacks: <act by act, the event that attacks the misbelief>
   - skills: <the skills and knowledge the climax spends — each a plant>

   ## Opponent
   - name: <one rival who wants the same prize>
   - wants: <the same prize, and why>
   - plan:
     - <date>: <his move — most are offstage; say how each reaches the page>
   - appears_in: <chapters — at least one in every act>
   - wins_in: <chapter(s) where he wins on the page, before the climax>
   - attacks: <the protagonist weakness he exploits>

   ## Plants
   - P1 <name>: <the skill or fact> | plant: ch N (<the contest it is learned inside>) | test: ch N | payoff: ch N

   ## Rehearsals
   - R1 <name> (ch A–B): <the smaller version of the climax> | teaches: P1, P2 | outcome: <succeeds | fails> — <what it costs>

   ## Gatekeepers        (optional — for a climax with several locks)
   | Lock | Wants | The rival's offer | Key | Plant | Opens in |

   ## Cast
   ### <Name> — <function in the web>
   - want / fear / secret / contradiction / signature
   - entrance: ch N, <the action they are first seen in>
   - arc: <how the plot changes them>
   - answers: <their answer to the book's question>

   ## Sequences
   - S1 (ch A–B) <title>: <the sequence's own question> | hands on: <the result that forces S2>

   ## Clocks
   - <deadline>: set ch N, runs out ch N

   ## Stakes ladder
   | Act | Chapters | Stake | Higher than the last act because |

   ## Reader questions
   - end of act I (ch N): <what the reader wants to know next — never "what happens next year">

   ## Places
   ### <Place> (ch …)
   - orientation: <a plain picture of the place in its own time: how big, who ruled it, what it lived on, what made it unlike anywhere else or unlike today>
   - use: <what the place does in its scenes>
   - signature: <two or three recurring sense details>
   - arrival: <the moment of pressure it is first seen in>
   - only here: <set-piece moments only this place allows>
   - set_piece: ch N — <the moment the place is shown whole through the viewpoint's eyes: who walks it, guided by whom, wanting what>

   ## Terms
   - <institution, office, coin, trade or foreign word>: ch N — <one-line plain gloss>

   ## Voice
   - register / rhythm / viewpoint / description / interiority / dialogue / bans

   ## Genre contract
   - <convention or obligatory scene>: ch N

   ## What the reader comes to learn      (when the genre guide's ## Design asks for it)
   - events: <real event played on the page>: ch N — <as a scene, through whom>
   - people: <real person>: ch N — <first met as a person, doing what>
   - daily life: <work, money, travel, faith, food, law… in use>: ch N — <whose need>
   - places: <place, name then>: ch N set piece — still standing: <today's name> | gone

   ## Keep ledger         (with --from-book)
   - <what worked in the drafted book>: kept as <…> in ch N | dropped: <why>

   ## Fault ledger        (with --from-book)
   - <diagnosed fault, with the letter it came from>: prevented by <design decision>

   ## Design tests
   - D1 pass|fail|n/a: <evidence>
   … through D14
   ```

   Rules while deciding:
   - **Climax first** (DESIGN.md §2). The protagonist decides it, by
     his own act, spending plants; other people's votes or verdicts
     can be its occasion, never its cause.
   - **The question** is posed on the page by a character in the first
     quarter; if the reader may know the outcome, make it a *how* and
     *at what cost* with open parts (§4).
   - **Earned outcomes** (§15): no major win turns on a wager, odds or
     luck; each turns on knowledge the reader saw acquired. Risk stays
     real.
   - **Plants inside contests** (§8): every chapter that plants a skill
     has its own stake in that scene; the plant is never a lecture or
     a forecast.
   - **Proportion** (§10): the climax campaign gets dense time and
     room; an education gets no more than it needs to make each plant
     land.
   - **Cast** (§7): historical figures get documented signatures from
     the research notes (portraits, letters, sayings); every principal
     gets a want in every scene they enter.
   - **Places** (§12): from the research notes, accurate to the year,
     chosen for what they do in the scene, each with its orientation.
   - **Terms** (§13a): every word a reader today may not know that the
     story turns on, with the chapter that explains it.
   - **Plain words to the author** (§13a): the report and every page
     written for the author say what the design means in ordinary
     words — "what wins each elector's vote", "what he learned and
     where he uses it" — never the design's own terms (locks, keys,
     plants, spends, beats).
   - **Voice** (§13): from the author's stated preferences first.
   - **Chapters**: honour the seed's length; otherwise
     `project.yaml defaults.chapter_target_words` and a book of
     roughly 90,000–110,000 words.
   - **Keep ledger**: an old scene or person is kept only if the new
     design has a place for it, and is redrafted in the new voice,
     never pasted.

7. **Self-test, D1–D13.** Write `## Design tests` honestly, one line
   per test with the evidence. A test that fails changes the design,
   not the verdict; revise and re-test until D1–D13 pass or are
   `n/a` with a reason.

8. **A cold reader (D14).** Use `task` to spawn one heavy-tier reader
   that has not seen your reasoning, the author's notes or the seed.
   Give it only `books/{book}/design.md` and DESIGN.md Part II, and
   ask it to answer, briefly and bluntly: (1) the book in one sentence;
   (2) what the reader will be waiting to find out, and from which
   chapter; (3) who is against the protagonist and what he wants;
   (4) which sequence could be skipped, and what would fail without
   it; (5) which win looks like luck; (6) which principal is thinnest;
   (7) where a reader would stop reading. Change the design for every
   answer that exposes a fault. Record the reader's answers, and what
   you changed, in the `D14` line. D14 passes only when the reader's
   one-sentence book matches the pitch and question and no sequence is
   skippable. **If the first read changed the design materially** (the
   climax, the opponent, the shape, a cut sequence), spawn a second,
   fresh cold reader on the revised design, with the same questions and
   two more — is the climax's temptation real at that hour, and does
   the design contradict itself anywhere — and change the design again
   for what it finds. On the first book designed this way the second
   read found a temptation that could not tempt and a rule the design
   had already broken, both missed by the first. Record both reads in
   D14.

9. **Validate.** Use `bash`:

   ```
   autonovel mechanical design-validate books/{book} --format markdown
   ```

   Fix every error and re-run until it reports OK. Address each warning
   or justify it in the relevant test line.

10. **The seed** (new books). If `books/{book}/seed.txt` is missing or
    the template placeholder, write it with `file_write`: the author's
    `--notes` verbatim at the top under "Author's direction (<date>)",
    then the factual frame (period, real people, dated events, what is
    fixed and what may be invented, length), and one line saying the
    design lives in `books/{book}/design.md`. Copy facts from the
    drafted book's seed, never its superseded rules. Leave an existing
    author-written seed untouched.

11. **Report** to the author, briefly, in plain words:
    - the pitch, and the question (posed in chapter N, by whom);
    - the climax in two lines, and which plants it spends;
    - the opponent and his plan in two lines;
    - the cast, one line each (name — function — what they want);
    - the sequences, one line each;
    - with `--from-book`: what changed from the drafted book (the fault
      ledger in a few lines) and what was kept;
    - every departure from the author's direction, as a question for
      them;
    - the cold reader's one-sentence book.
    Then **Next:**
    1. Read the design: `books/{book}/design.md`
    2. `/autonovel:gen-outline --book {book}` (bound to the design)
    3. `/autonovel:voice-discovery --book {book}`
    4. `/autonovel:draft 1 --book {book}`
</workflow>

<acceptance>
- `books/{book}/design.md` exists and
  `autonovel mechanical design-validate books/{book}` exits 0.
- Every explicit author direction appears under `## Author's intent`,
  honoured or with a stated departure.
- D14 records a cold reader's answers.
- With `--from-book`: the book exists in `project.yaml` with
  `context: isolated`; `## Keep ledger` and `## Fault ledger` are
  filled; the drafted book's chapter files were not read.
- No chapter, outline or canon file is written.
</acceptance>
