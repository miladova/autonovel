---
name: autonovel:structure-review
description: Book-level structural review — through-line, chapter-to-chapter causal chain, act escalation ladder, removability test, climax build — scored 1–5 separately from prose, with structural brief candidates brief/revise can act on.
argument-hint: "--book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - project.yaml
  - shared/craft/CRAFT.md
  - books/{book}/seed.txt
  - books/{book}/outline.md
  - books/{book}/chapters/*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/threads.md
  - books/{book}/edit_logs/structure_review.json
  - books/{book}/edit_logs/review.json
  - books/{book}/edit_logs/reader_panel.json
  - shared/craft/genres/*.md
  - shared/genres/*.md
writes:
  - books/{book}/edit_logs/structure_review.json
  - books/{book}/edit_logs/structure_review.md
context_mode: book
---

<purpose>
Answer one question about a finished (or nearly finished) draft: **is this
one story building to a climax, or a string of episodes?** The other
whole-book reviewers do not ask it. `/autonovel:review` writes an editorial
letter that is mostly about prose; `/autonovel:reader-panel` asks ten
local questions; `/autonovel:evaluate --full` used to see only the first
and last 500 characters of each chapter. A book can hold 7+ chapter
scores, a 4★ review and a panel that would buy it through many revision
passes while its author reads it as a string of short anecdotes rather
than one story building to a climax. This command exists to catch and
name that failure.

It reads the whole manuscript, the outline and every chapter summary, and
writes:

- `books/{book}/edit_logs/structure_review.json` — machine-readable:
  the through-line, a causal-chain table (chapter N → N+1: *happens
  because of* / *happens after* / *unrelated*), an escalation ladder per
  act, a removability verdict per chapter, the climax build, the named
  failure modes found, a 1–5 **structure score** that is separate from
  prose, and 3–7 **structural brief candidates** that `/autonovel:brief
  --from auto` turns into `kind: structural` briefs.
- `books/{book}/edit_logs/structure_review.md` — the same, as a report a
  person reads.

`/autonovel:review` will not declare "stop revising" until this file is
newer than every chapter, scores ≥ 4 and flags no chapter removable.
Prose is not scored here. A book of beautiful chapters can score 2.
</purpose>

<ground-rules>
These rules bind every judgement below. Re-read them before scoring.

1. **Strong prose is not evidence of structure.** Vivid scenes, a good
   line, a paid-off image, a high chapter score: none of them is a
   reason to call a link causal, a stake higher, or a chapter
   necessary. Do not praise prose anywhere in this review except where
   a structural fact is hidden in it.
2. **Every "because" is argued with a concrete plot fact.** Name the
   event in the earlier chapter (who did what) and the action in the
   later chapter it forces. Apply the test: *if that event had gone the
   other way, would this chapter happen as written?* If you cannot name
   the event, the link is "happens after".
3. **These are not causes:** a recurring character, place or object; a
   motif or image (a recurring object, document or ritual); a callback
   line; a narrator promise or flash-forward ("years later she would…"); a dated
   clock that is merely carried; a theme. They are continuity. They
   belong under foreshadowing, never in the causal chain.
4. **History is not causation.** A death, an election, a war, a fair or
   a plague that arrives on its historical date is "happens after"
   unless the protagonist's earlier action in the book changes how it
   lands for him. The record is the weather; the novel has to supply
   the spine.
5. **Default to "happens after".** A link is "because" only when rule 2
   is met. A chapter is "removable" unless a later chapter's action
   fails without it.
6. **Do not hedge a structural defect.** Never write "cost of
   ambition", "individually fine", "largely successful", "thematically
   coherent", "by design", "the episodic shape is the point", or any
   phrase that turns a defect into a qualified compliment. State the
   defect, the chapters, and the fix. If the seed explicitly declares
   an episodic form (linked stories, a picaresque, a chronicle), say so
   in the verdict — and still score it on this rubric.
7. **Read before you trust.** The chapter summaries are an index
   written by the drafter; their "Threads closed" and "Promise" lines
   are bookkeeping, and a summary can be stale (the dossier flags it).
   Judge from the prose.
8. **Do not read the other reviewers first.** `review.json`,
   `reader_panel.json` and any previous `structure_review.json` are
   read only at step 12, after your tables and score are written, and
   they may not raise the score.
</ground-rules>

<failure-modes>
Name every one that applies in `failure_modes` (ids in backticks). The
first is the failure this command was built to catch.

- `anecdote-chain` — **the failure this command exists to catch.** Every chapter is a
  self-contained wager: its first scene names what the POV can lose
  *this chapter*, its last scene settles it, and the next chapter opens
  on a new counterparty, often after a time jump. Continuity is carried
  by recurring cast, objects, dated clocks, callbacks and narrator
  promise lines, not by consequence. Each chapter is good, so chapter
  evals hold at 7+, the dual-persona review gives 4★ pass after pass,
  the panel says it would buy it — and the author reads it as a string
  of short anecdotes, not a continuing story building to a climax.
  Signs: summaries whose "Threads closed" line settles the
  chapter's own stake; most links "happens after"; several chapters
  removable; act stakes that grow in size but reset in kind. Caps the
  score at 2.
- `motif-spine` — a recurring image or device (an object, a document,
  a ritual, a refrain) is offered as the spine. A motif ties
  chapters together in the reader's memory; it makes nothing happen.
  (Typical review line: "The book reads as one line; the spine is the
  <recurring image>.")
- `promise-line-architecture` — planted details and narrator
  flash-forwards paid later are counted as structure ("the
  architecture of promise and payment across fifty years is the book's
  real achievement"). A paid promise line is a callback, not a cause.
- `chronicle-spine` — the order and the triggers of the chapters are the
  historical record's; the protagonist's earlier choices do not change
  how the recorded events land.
- `late-through-line` — the question the ending answers is first posed
  after the first quarter of the book.
- `reset-ladder` — stakes grow in size (sums, ranks, borrowers) but reset
  in kind each act: a new counterparty, a new bet, the previous bet
  closed. The reader's question restarts each act instead of tightening.
- `finishing-not-converging` — the last ~20% closes threads one at a time
  (a roll-call of callbacks) instead of forcing them into one decision
  whose outcome depends on all of them.
- `missing-antagonist` — no opposing force persists across acts; each act
  brings its own obstacle, which leaves with the act.
</failure-modes>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. Missing is a usage
   error — print `usage: /autonovel:structure-review --book <short-name>`
   and stop.

1a. When the book has a genre guide (the book's genre guide: the file
`_begin`'s `genre:` line names (`autonovel genre show --book {book}`
prints it when no preamble ran; it is `shared/craft/genres/<genre>.md`,
or the series' own `shared/genres/<genre>.md`)), read its `## Subgenres`
   entries for the book's subgenres: their "must deliver" lists are the
   genre's obligatory scenes, which the climax build and the act ladder
   are checked against. History is still not causation (rule 4).

2. Use `file_read` on `project.yaml`: the book's title, `genre`, and
   `period` (a set `period.start`, or a genre naming historical fiction,
   turns on the historical-fiction check at step 9). Use `file_read` on
   `shared/craft/CRAFT.md` §1 "Causation, not sequence" and §8 "Plot
   Structure" — the craft basis of every test below (Forster's "of
   grief", Parker and Stone's "therefore / but", never "and then").
   If the section is missing, run `autonovel refresh-templates` with
   `bash` and read it again; if that fails, proceed — this command
   restates every rule it applies.

3. Use `bash` to run the data-assembly helper once:

   ```
   autonovel mechanical structure-dossier books/{book}
   ```

   It prints one JSON object: the outline's acts, chapter entries and
   any `## Spine` / `## Stakes ladder` / `## Causal spine` sections;
   per chapter the title, POV, story_time, word count, start/end position
   as a percentage of the book, the months since the previous chapter,
   the full continuity summary, the latest chapter score; the
   `climax_window_chapters` (chapters starting at or after 80% of the
   words); `story_time_gaps_of_a_year_or_more`; the optional thread
   ledger `books/{book}/threads.md`; and `warnings`. It judges nothing.
   If `chapter_count` < 3, stop: "structure review needs at least three
   drafted chapters". Note every warning; stale or missing summaries
   mean you must lean on the prose for those chapters.

4. Use `file_read` on `books/{book}/seed.txt`. Record the question the
   seed promises (`seed_intent`), the spine it claims, and any declared
   form. Use `file_read` on `books/{book}/outline.md` for the author's
   act design. When the outline has a `## Causal spine`, it is the plan
   the draft was held to: compare it with what the prose delivers, and
   treat an outline line marked `after` as a known weak link. When
   `books/{book}/threads.md` exists (the story-map thread ledger),
   read it as an index of plants and payoffs — best-effort; this
   review never depends on it.

5. **Read the manuscript.** Use `file_read` on every
   `books/{book}/chapters/ch_NN.md` in order (not the `.summary.md`
   files; those came with the dossier). For each chapter keep a short
   working note:
   - **stake** — what the POV can lose *in this chapter*, concretely;
   - **trigger** — what starts the chapter's action: an event in an
     earlier chapter (which, and what), or something from outside the
     book's prior action (history, a new arrival, a time jump);
   - **hand-forward** — which later chapter acts on this chapter's
     result, and how;
   - **settled here?** — is the chapter's own stake opened and closed
     inside the chapter?
   - one short quote that proves the trigger and one that proves the
     hand-forward.

   Context budget: when the runtime cannot hold the whole manuscript
   at once (well under ~400k tokens of context), use `task` to fan out
   one subagent per act. Give each subagent the dossier's summaries for
   the WHOLE book plus its act's chapter files, and have it return only
   the per-chapter notes above with their quotes. Every structural
   judgement below stays in this conversation. Never judge a chapter
   from its summary alone.

6. **Through-line.** State the one question the book asks and answers,
   as a question about the protagonist (yes/no or which-way), ending in
   `?`. It is the question the climax's decision answers — not a theme
   ("money and the soul") and not the seed's pitch restated. Record
   `posed_in` (the first chapter in which a reader could ask it; `null`
   if none does), `posed_at_pct` (that chapter's `start_pct` from the
   dossier), `answered_in`, `ending_answers` (`yes` = the climax's
   decision answers it; `partly` = answered thematically, or a
   different question is answered; `no`), the `answer` in one sentence,
   and `seed_intent`. If the book's real question differs from the
   seed's, say so in `verdict`.

   A question counts as **posed** only when the protagonist's want and
   the force opposing it are both on the page — an opening image or a
   theme that later turns out relevant does not pose anything. A
   question whose answer is simply accumulation ("will he get rich?",
   "will she rise?") answered by more money or rank each act is a
   chronicle's direction, not a through-line: the answer must be in
   doubt at the midpoint and settled by the climax's decision; if it is
   settled by accumulation, `ending_answers` is `partly`.

7. **Causal chain.** For every consecutive pair (1→2, 2→3, … n−1→n),
   one row: `{from, to, link, cause_chapters, evidence}`.
   - `because` — chapter N+1's central action (its stake or its turn)
     exists because of an event in an earlier chapter, usually N:
     someone acts on what happened there, a decision made there forces
     this one, a consequence lands. `cause_chapters` names the earlier
     chapter(s) (braided or multi-POV books may cite N−2 or N−5).
     `evidence` = "In ch N, <who did what>; in ch N+1, <the action it
     forces>."
   - `after` — N+1 follows in time, but its trigger is outside the
     book's prior action (rules 3–4): a recorded event on its date, a
     new arrival or offer, a time jump that resets the board, or only a
     carried clock, object, character, callback or promise line.
     `evidence` names the actual trigger.
   - `unrelated` — no link beyond the protagonist's presence.
   Fill `causal_summary` with the counts and `because_ratio`.

8. **Escalation ladder.** Use the outline's act headings when the
   dossier found them; otherwise divide the book at its major turns
   into 3–5 acts. One row per act: `{act, title, chapters: [first,
   last], stake, same_question, vs_previous, evidence}`.
   - `stake` — what the protagonist can lose in this act, concretely
     (a person, a position, a freedom, a self), not the size of a sum.
   - `same_question` — does this act's stake belong to the
     through-line question?
   - `vs_previous` — `first` for act one; then `higher` (strictly more
     to lose and still the same bet, or a deeper kind: a life over
     money, a self over property), `level`, `lower`, or `reset` (the
     previous act's stake was settled and a new, unrelated bet opens).
     A larger number is not a higher stake when nothing already at risk
     is still at risk.

9. **Historical-fiction check** (when step 2 found period fiction). The
   record is episodic by nature: deals, deaths, elections, wars. List
   the recorded events the book stages and, for each, whether the novel
   makes it land *because of* something the protagonist did earlier in
   the book, or whether it simply arrives. A book whose acts and
   triggers follow the record is `chronicle-spine` however vivid each
   event is. The fix is never to change the record; it is to invent
   what the protagonist risks, who opposes him across the years, and
   which earlier choice of his the recorded event punishes or rewards.

10. **Removability test.** For every chapter: imagine it deleted, and
    allow one sentence in a neighbouring chapter to carry any fact a
    later chapter needs (a name, a sum, a date). Which later chapter's
    action now fails or stops making sense? Record `{chapter, verdict,
    breaks, what_breaks}`:
    - `load-bearing` — a later chapter's decision is caused by what
      happens in this chapter's scenes; `breaks` lists those chapters
      and `what_breaks` names the action that fails.
    - `weak` — a later chapter needs only one fact or object from it.
    - `removable` — nothing later fails. Losing texture, a character
      introduction (a sentence can introduce), a callback's antecedent
      (callbacks can be replanted), a thematic note, or "a great
      scene" does not make a chapter necessary. **A removable chapter
      is an anecdote; flag it.** `breaks` is empty.
    The last chapter is judged by the through-line: `what_breaks` says
    what the ending answers. Copy every removable chapter into
    `removable_chapters`.

11. **Climax build.** Take the dossier's `climax_window_chapters` (the
    last ~20%). List every thread still open at the window's start
    (from the prose, the summaries' open threads, the outline's thread
    ledger, `threads.md`), and for each the `ending`: `converged`
    (forced into the climax decision — that decision's outcome depends
    on it), `finished` (closed in its own scene), or `dropped`.
    `verdict`: `converges` (two or more threads meet in one decision
    and the rest support it), `mixed`, or `finishes` (threads close one
    by one).

12. **Score, then reconcile.** Name the `failure_modes` that apply,
    set `episodic_risk` (`low` / `medium` / `high`), write `verdict` in
    plain words (two to four sentences: what the book is structurally,
    where it stops being one story, what would make it one), and set
    `structure_score` with the anchors and caps below. Before scoring,
    answer for yourself: *if I deleted the prose and kept only my causal
    table, would it read as one story?* The chapter scores in the
    dossier are prose scores; a book of 7.5 chapters can score 2 here,
    and that is the point of this review.

    **Only now** use `file_read` on `books/{book}/edit_logs/review.json`,
    `books/{book}/edit_logs/reader_panel.json` and any previous
    `books/{book}/edit_logs/structure_review.json` (each best-effort;
    skip silently when absent). Record in `reviewer_disagreements` every
    place a prior reviewer claimed a spine, escalation, an earned ending
    or a necessary chapter that your tables contradict (`{source,
    claim, finding}`), and in `delta_vs_previous` how the score and
    removable list moved since the last structure review. They may
    change a fact in a table you got wrong; they may not raise the
    score.

13. **Structural brief candidates** — 3 to 7 (0–7 only at score 5).
    Each `{id: "S1"…, kind, title, chapters, edits: [{chapter,
    instruction}], command, expected_effect, fixes, priority}`:
    - `instruction` is a scene instruction for one chapter: what
      happens on the page, where, who is present, what changes by the
      end — the shape `/autonovel:revise` can execute inside that
      chapter.
    - `expected_effect` names what it fixes: links turned from `after`
      to `because` ("9→10, 12→13"), rungs raised, a chapter that stops
      being removable, a question posed earlier, threads converged.
    - `kind` is one of: `add-consequence-scene` (in N+1, a scene where
      N's result forces the POV's next choice — the standard cure for an
      `after` link), `retarget-stake` (rewrite a chapter's stake so it
      is the through-line's bet raised, not a new bet — the cure for a
      reset ladder), `pose-question-earlier`, `thread-the-antagonist`
      (one opposing force that persists across acts), `move-reveal`,
      `plant-earlier`, `converge-climax`, `merge`, `cut`, `reorder`,
      `split`, `other`.
    - Cross-chapter kinds carry the exact command the author runs; revise
      never executes them: `merge` → `/autonovel:merge-chapters
      --chapters N,M --book {book}` (adjacent chapters only); `cut` →
      `/autonovel:remove-chapter N --book {book}`; `reorder` →
      `/autonovel:reorder --from A --to B --book {book}`; `split` →
      `/autonovel:split-chapter --chapter N --book {book}`. A cut or
      merge also carries an `edits` entry for the chapter that absorbs
      the one fact a later chapter needs. Other kinds set `command`
      to `null` (or an `/autonovel:add-subplot` / `/autonovel:foreshadow`
      call when that is the right tool).
    - Prefer in-chapter fixes; propose at most two cross-chapter
      commands. Lead with the candidate that turns the most `after`
      links into `because`. Every removable chapter is addressed by a
      candidate (cut it, merge it, or give it a consequence a later
      chapter needs).
    - Historical fiction: never alter a recorded date or outcome.
      Change what the protagonist does about the record, what he
      risks, and who opposes him.

14. **Write and validate the JSON.** Start from the skeleton:

    ```
    autonovel mechanical structure-validate --template --chapters <n>
    ```

    fill every field, set `schema: "autonovel.structure_review/1"`,
    `book`, `timestamp` (UTC ISO-8601), `chapter_count`, `scope`, and
    use `file_write` to save `books/{book}/edit_logs/structure_review.json`.
    Then run:

    ```
    autonovel mechanical structure-validate books/{book}
    ```

    It checks the shape, the coverage (one link per pair, one verdict
    per chapter) and the rubric caps below as arithmetic over your own
    tables. Fix every error and re-run until it exits 0. When it says
    the score exceeds a cap, lower the score — change a table only if
    the table itself was wrong, never to fit a score you prefer.

15. **Write the report.** Use `file_write` to save
    `books/{book}/edit_logs/structure_review.md` (at least 600 words) with
    these sections: `# Structure review — <title>`; a first line
    `**Structure: N/5** (prose is not scored here) · episodic risk ·
    book-level gate PASS/BLOCK`; `## Verdict`; `## Through-line`;
    `## Causal chain` (a table: N→N+1 | link | evidence); `## Escalation
    ladder` (a table); `## Removability` (a table, then the anecdotes —
    the removable chapters — by name); `## Climax build`; `## Failure
    modes`; `## Structural brief candidates` (numbered, each with its
    chapters, per-chapter instructions, command, expected effect);
    `## What the other reviewers said`; `## How to act on this`.

16. Print a one-screen summary: the score, the verdict, the gate
    (from the validator's `gate`), the removable chapters, the
    top three candidates, and the command sequence from step 17.

17. **Postamble next step.** Pass the sequence to `autonovel _end` with
    `--next-standard-step` (same shape as `/autonovel:revision-pass`
    step 6), filled from this run:

    ```
    1. <only when a candidate has a command> Cross-chapter moves first
       (they renumber chapters; run them yourself, in this order):
         <each candidate command>
       then /autonovel:impact-of --book {book} --source merge-chapters
       (or remove-chapter / reorder) and re-run
       /autonovel:structure-review --book {book} so the candidates match
       the new numbering.
    2. In-chapter structural fixes:
         /autonovel:revision-pass --chapters structural --book {book}
       (brief --from auto turns each candidate into a `kind: structural`
       brief; revise restructures inside each chapter.)
    3. Re-check the structure: /autonovel:structure-review --book {book}
    4. Then /autonovel:review --book {book}: its stop-revising verdict
       is gated on this file (score ≥ 4, no removable chapter).
    ```

    When the gate already passes, write instead the next step of the
    whole-book order: `/autonovel:developmental-edit --book {book}` when
    there is no editor's letter or a chapter changed since it;
    `/autonovel:revision-pass --chapters <the letter's open chapters>`
    when the letter has open recommendations; otherwise
    `/autonovel:reader-panel`, then `/autonovel:review` for the
    prose-level verdict. (`autonovel next` prints the same step.)

   After the last chapter the whole-book work has one order (`/autonovel:next`
   and every `_end` footer walk it): the editor's letter
   (`/autonovel:developmental-edit`) → the structure review → a
   revision pass on the letter's open recommendations and the structure
   candidates → the re-read (structure review again, then the editor's
   second letter) → the reader panel and the dual-persona review once the
   structure gate passes and the letter has nothing open → typeset.
</workflow>

<scoring>
Structure score anchors (1–5; prose is not part of it):

  5  One story. The through-line is posed by ~15% and answered by the
     climax's decision; ≥ 80% of links are "because"; every act raises
     the same stake; no chapter is removable; the climax converges.
  4  One story with soft spots. Posed by 25%; ≥ 65% "because"; at most
     one act plateaus; no removable chapter (weak ones allowed); the
     climax converges or is mixed.
  3  A story with an episodic stretch. Posed late (25–50%) or answered
     only partly; 50–65% "because"; one or two removable chapters; or
     one act resets.
  2  A string of episodes with a frame. Under 50% "because", or a
     quarter of the chapters removable, or the question posed after
     the midpoint, or most act transitions reset. Strong prose and paid
     promise lines do not lift a 2.
  1  A chronicle. Chapters could be reordered or dropped without loss;
     no question runs through the book.

Caps (the validator enforces these over your own tables):

  - any removable chapter → ≤ 3; removable chapters ≥ 25% of the book → ≤ 2
  - because-ratio < 0.80 → ≤ 4; < 0.65 → ≤ 3; < 0.50 → ≤ 2
  - ending answers the through-line only `partly` → ≤ 3; `no` → ≤ 2
  - question posed after 25% → ≤ 3; after 50%, or never → ≤ 2
  - climax `finishes` → ≤ 3
  - any act transition `level` / `lower` / `reset` → ≤ 3; half or more → ≤ 2
  - episodic_risk `medium` → ≤ 3; `high` → ≤ 2
  - `anecdote-chain` named → ≤ 2
</scoring>

<acceptance>
- `books/{book}/edit_logs/structure_review.json` exists and
  `autonovel mechanical structure-validate books/{book}` exits 0.
- The causal chain has one row per consecutive chapter pair; every
  `because` row's evidence names a plot event in an earlier chapter and
  the action it forces (never a motif, callback, clock or promise line).
- The removability table has one verdict per chapter, and
  `removable_chapters` lists exactly the removable ones.
- `candidates` holds 3–7 entries (0–7 only at score 5); every merge /
  cut / reorder / split candidate carries its exact `/autonovel:*`
  command.
- `books/{book}/edit_logs/structure_review.md` exists, is at least 600
  words, and contains every section listed in step 15.
- No hedge phrase from ground rule 6 qualifies a structural defect.
</acceptance>
