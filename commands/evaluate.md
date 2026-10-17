---
name: autonovel:evaluate
description: Score the foundation, a chapter, the whole book, or a head-to-head chapter pair.
argument-hint: "--phase foundation --book <name> | --phase series | --chapter <N> --book <name> | --full --book <name> | --compare <N>,<M> --book <name> [--vs-book <other>]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - books/*/canon.md
  - books/{book}/canon.md
  - shared/events.md
  - shared/period_bans.txt
  - shared/craft/*.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/*/outline.md
  - books/*/voice.md
  - books/*/chapters/ch_*.summary.md
  - books/{book}/edit_logs/structure_review.json
writes:
  - books/{book}/eval_logs/*.json
  - .autonovel/eval_logs/*.json
context_mode: book
---

<purpose>
Judge model scores, subtracts a deterministic AI-slop penalty, and writes
an eval log the rest of the pipeline consumes. This command is the
successor to the old `evaluate.py` — the mechanical half lives in
`src/autonovel/mechanical/` and is invoked via `bash`; the LLM-judgement
half is this command's body. Five modes:

  --phase foundation   score the planning layer for one book
  --phase series       score arc *quality* across ≥2 books (no --book)
  --chapter <N>        score a single chapter
  --full               score the whole book holistically
  --compare <N>,<M>    pick a winner between two chapters (successor to
                       the deleted `compare_chapters.py`); add
                       `--vs-book <other>` to read M from another book
                       (rewrite vs original)

Eval logs are JSON and land under `books/{book}/eval_logs/<timestamp>_<mode>.json`,
or `.autonovel/eval_logs/<timestamp>_series.json` for `--phase series`.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Exactly one of `--phase`, `--chapter`, `--full`, or
   `--compare` must be present. `--book <short-name>` is required for
   every mode EXCEPT `--phase series` (which is whole-series). Anything
   else is a usage error — print a one-line reminder and stop.

2. Use `file_read` on `project.yaml` to resolve the book entry, its `pov`,
   and `defaults.chapter_target_words` / `defaults.chapter_threshold`. The
   defaults drive two calibration rules that follow.

3. Load the shared layer with `file_read`: `shared/world.md`,
   `shared/characters.md`, `shared/canon.md`, `shared/events.md`. Load
   `shared/period_bans.txt` if it exists; treat missing as empty.

4. Load the per-book layer with `file_read`: `books/{book}/voice.md`
   (Parts 1, 2, AND 3), `books/{book}/outline.md`, and the book's own
   `books/{book}/canon.md` (book-scoped facts; `canon_compliance` is
   judged against shared canon + THIS book's canon, never a sibling
   book's).

4a. **Parse Part 3 (Custom rubric) from voice.md.** Look for a
    heading exactly matching `## Part 3 — Custom rubric` (em-dash)
    or `## Custom rubric`. Treat each top-level bullet under that
    heading as one rubric criterion. Strip the HTML comment
    placeholder (the `<!-- … -->` block from the template) — only
    real bullets count. Empty or comment-only sections mean "no
    custom rubric for this book"; proceed normally without flagging
    a missing surface (this is the expected state for many books).

4b. **Parse Part 4 (Per-character voice fingerprints) from
    voice.md.** Look for `## Part 4 — Per-character voice
    fingerprints`. Treat every `### Name (...)` block under that
    heading as one character fingerprint. Strip the HTML comment
    placeholder; only real `###` blocks count. Empty or comment-
    only Part 4 means "use Part 2 alone for character_voice
    scoring"; proceed normally. When Part 4 has fingerprints, the
    `character_voice` dimension scored in step 6 changes from
    "do characters sound distinct?" (Part 2 only) to "does each
    character honour their Part 4 block?" — verify per-line that
    Tommaso's dialogue obeys Tommaso's Speech / Verbal tics /
    Refuses, etc. Quote the strongest violation in
    `weakest_moment` for the dimension.

5. Mode `--phase foundation`: evaluate the planning layer only. Use a
   literary-critic system prompt calibrated to the SCORING CALIBRATION
   block below. Score the dimensions: `magic_system` (or
   `world_rule_consistency` for non-fantasy genres — use whichever the
   `project.yaml :: genre` dictates), `world_history`,
   `geography_and_culture`, `lore_interconnection`, `iceberg_depth`,
   `character_depth`, `character_distinctiveness`, `character_secrets`,
   `outline_completeness`, `foreshadowing_balance`, `clocks_paid`,
   `causal_spine`, `internal_consistency`, `voice_clarity`,
   `canon_coverage`, `canon_outline_consistency`. For each dimension
   emit `{score, gap, fix, note}`.

   **`causal_spine` — does the outline commit to one story?** Read the
   outline's `## Spine`, `## Stakes ladder` and `## Causal spine`
   sections (`/autonovel:gen-outline` writes them). Check: the spine
   `question:` is one question about the protagonist that the last act
   answers, posed in the first quarter; every act row on the ladder is
   strictly higher than the one before *on the same bet* (a bigger sum
   with a new counterparty is a reset); every `- N because M:` line
   names an event in chapter M that forces chapter N (not an object,
   motif, callback or carried date); `after` lines are few and none
   sits at an act boundary; the chapter beats agree with the lines
   (chapter N's first beat acts on M's event). Score 9-10 when all
   hold; 7-8 with one or two `after` links; 5-6 when the ladder resets
   in kind once or the question is posed late; below 5 when most
   chapters open and settle their own stake (the outline of an
   anecdote chain). When the three sections are absent, judge from the
   beats alone, cap the score at 5, and make the `fix` "run
   `/autonovel:gen-outline --book {book} --add-spine`". Catching an
   episodic outline here costs minutes; catching it in a drafted book
   costs a structural revision pass.

   **`clocks_paid` — every clock in the outline has a paying beat.**
   Walk the outline's beats and list every deadline, ultimatum or
   promise with a date that a beat sets ("three days to…", "come
   home by Candlemas or…", "the loan falls due at Easter"). For each,
   find the later beat where it runs out, is met or is bought off,
   and check that the paying beat is a scene the POV acts in, not a
   line of summary in the next chapter's opening ("Georg wrote; he
   has till Michaelmas"). Emit `clocks: [{set_in, clock, paid_in,
   paid_as: scene|summary|unpaid}]` under the dimension. Score 9-10
   when every clock is paid as a scene, 7-8 with one paid in summary,
   5-6 with one unpaid or two in summary, below 5 when a chapter
   ends on a clock the next chapter opens after. The `fix` names the
   chapter where the paying scene belongs (CRAFT.md §4 rule 3, PROSE
   §5.8). Reader panels name this failure as "the missing scene";
   catching it in the outline is cheaper than catching it in prose. Weighting: lore 40%, character 30%, structure
   20% (`causal_spine` is half of it), craft 10%. Include `overall_score`, `lore_score`,
   `weakest_dimension`, `top_3_improvements`.

   **`canon_outline_consistency` — cross-check canon.md against
   outline.md.** Read both files. Find every fact that appears in
   BOTH (a date, a character name, a location, an event). When
   the canon and outline disagree on the value (e.g. canon says
   `[Anselmo arrived] 1473` but outline ch 4 says "Anselmo
   arrives in 1471"), score this dimension low and emit a
   `canon_outline_conflicts` array with one entry per conflict:
   `{fact, canon_value, outline_value, recommendation}`. The
   recommendation says which side is authoritative for this
   project — usually canon (since `/autonovel:promote-canon` is
   the process by which facts harden), so the outline is the
   side that should change. When canon and outline agree on
   every fact mentioned in both, score the dimension 9-10 and
   emit `canon_outline_conflicts: []`. This catches the bug
   class where an outline plant in chapter 4 contradicts a
   canon entry that hardened from a different chapter's
   research, leaving downstream chapters drafted against a
   silently-wrong date or name.

5b. Mode `--phase series`: score arc *quality* across the whole
    series. Requires `project.yaml :: books` length ≥ 2; refuse
    cleanly with a one-line message otherwise. This mode pairs
    with `/autonovel:series-arc` (the structural scoreboard) —
    that command surfaces *what* is missing; this mode scores
    *whether the missing thing is load-bearing*. Reads:
    - `project.yaml` for the books list.
    - `shared/world.md`, `shared/characters.md`, `shared/canon.md`,
      `shared/events.md`.
    - For each book: `books/{name}/outline.md`, `books/{name}/canon.md`,
      `books/{name}/voice.md` Part 1+2, every
      `books/{name}/chapters/ch_*.summary.md` (the continuity
      summaries — load these instead of the prose so the
      context budget fits ≥2 books).
    - The most recent `--full` eval log per book (when one
      exists), purely for the `weakest_chapter` and
      `top_suggestion` fields.
    - First, run `autonovel mechanical series-arc <series_root>
      --format json` via the `Bash` tool. Treat its
      `cross_book_cast`, `backwards_story_time_jumps`,
      `unresolved_threads`, and `arc_score` as *evidence* —
      the LLM judges *quality*, the helper provides
      *structure*.

    Score the dimensions:
    - `series_question`: does the series open a load-bearing
      question and resolve it by the final book? 9-10 = a
      named promise opens in book 1 and pays off; 5-6 = the
      books cohere thematically but no single question drives
      across them; 1-3 = each book is a standalone with no
      arc carry.
    - `early_setup_late_payoff`: of the threads
      `series-arc` flagged as unresolved, how many are real
      payoff debts vs benign loose ends? Flag the worst
      offenders by name. Score the ratio of paid-off setups
      to total setups.
    - `cross_book_character_growth`: for each character in
      the cross-book cast, do their state changes feel
      earned across books? Surface the character whose arc
      is weakest as `weakest_arc_character`.
    - `world_evolution_consistency`: does the world deepen
      across books without contradicting itself? Backwards
      story-time jumps from `series-arc` are evidence here.
    - `tonal_continuity`: do voice and register match the
      series's frame across books, or does book N feel like
      a different series?

    Emit per-dimension `{score, weakest_moment, fix, note}` plus
    a top-level `series_score`, `weakest_dimension`,
    `weakest_book`, `top_3_arc_revisions`, and a
    `unresolved_thread_payoff_plan` array — one entry per
    `series-arc` unresolved thread the LLM rates as
    load-bearing, with a one-sentence "where this should pay
    off" note that brief / revise can act on.

    Write the eval log to
    `.autonovel/eval_logs/<timestamp>_series.json` (NOT under
    any single book — this is a series-level artefact).

6. Mode `--chapter <N>`: use `file_read` on
   `books/{book}/chapters/ch_{chapter}.md`. If the file is missing or
   empty, emit `{"error": "...", "overall_score": 0.0}` and stop. Also
   load the outline entry for this chapter and the last ~1500 words of
   `books/{book}/chapters/ch_{prev}.md` (where `{prev}` = chapter - 1,
   zero-padded). Score the dimensions: `voice_adherence`, `beat_coverage`,
   `character_voice`, `plants_seeded`, `prose_quality`, `continuity`,
   `canon_compliance`, `lore_integration`, `engagement`,
   `irreversible_change`, `show_dont_tell_ratio`, `concreteness`,
   `register`. Each emits
   `{score, weakest_moment, fix, note}`. Include
   `three_weakest_sentences`, `three_strongest_sentences`,
   `ai_patterns_detected`, `overall_score`, `weakest_dimension`,
   `top_3_revisions`, `new_canon_entries`.

   **Judge `voice_adherence` and `prose_quality` against the register
   voice.md Part 2 asks for, not against a general idea of good
   prose.** A plain contemporary register is not marked down for being
   plain, explanatory or direct, and a literary register is not marked
   down for density. The reverse failure is the one to catch: a book
   that asked for plain English and got compression, riddle openers,
   metonymy, period cadence or epigram closers (`shared/craft/CRAFT.md`
   §6 "register tells"). Judge the mechanics of the prose (how
   sentences and paragraphs connect, how scenes are built, how
   dialogue is shaped) against `shared/craft/PROSE.md`, which is
   register-neutral; read it with `file_read` before scoring, and if
   `shared/craft/` is missing run `autonovel refresh-templates` with
   `bash` first. Where voice.md Part 1 overrides `shared/craft/CRAFT.md`
   or `shared/craft/ANTI-PATTERNS.md`, score to the voice file. Quote the register
   failures under `three_weakest_sentences` so the brief can act on
   them.

   **`register` (copy-editor pass; the LLM-judge upgrade to the
   register scanner).** Run the mechanical scanner first via the
   `Bash` tool:

   ```
   autonovel mechanical register books/{book} --chapter {N} --format json
   ```

   It reports, for narration and dialogue separately, the
   Flesch-Kincaid grade, mean narration sentence length, the
   contraction ratio and every uncontracted negative, formal
   connectives and tags (*whether, perhaps, upon, put in that,
   remarked*), fronted-object openers, elliptical participles,
   utterance count and mean length, utterances over 40 words, and
   "explaining to the listener" candidates (*that's the…, over
   there, at the end there, as you know, you know about*). Read
   `books/{book}/voice.md` for the book's declared register: the
   `FK grade band: L–H` line if present, the models it names, and
   what its narrator refuses. Then judge **as a copy editor at a
   commercial imprint, not as a literary critic**, in two passes:

     - **Narration.** For each candidate and for any sentence the
       scanner missed, ask: would a narrator in this book's
       declared register write this sentence today? Formal grammar
       under modern vocabulary (uncontracted negatives on every
       page, *whether*, *perhaps*, fronted objects, participial
       ellipsis) is the costume failure CRAFT.md §6 names; period
       nouns are not.
     - **Dialogue.** For each utterance over 40 words and each
       listener-explaining candidate, and for any other line that
       reads as speech for the reader's benefit, ask: would this
       person say this to that listener, now, standing where they
       are? A character naming the place they both can see, the
       time they both know, or the thing in the listener's hand is
       exposition in a mouth (Turkey City's "As you know, Bob";
       PROSE.md §6.4). A speech carrying four thoughts is a lecture;
       spoken turns carry one or two.

   Emit `register_edits`: an array of `{line_no, kind:
   "narration"|"dialogue", quote, why, rewrite}` with the exact
   quote and a rewrite in the book's register (for dialogue, cut
   the exposition from the mouth and say in one phrase where it
   goes: narration, a character who doesn't know it, or nowhere).
   Score `register` 0–10: 10 when the chapter's narration FK grade
   sits inside the declared band, the contraction ratio is above
   0.9 (or the book declares otherwise), no utterance lectures and
   no line explains to its listener; subtract roughly a point per
   two confirmed edits, floor 3. `weakest_moment` = the worst
   edit's quote; `fix` = its rewrite. Record the scanner's numbers
   (`fk_narration`, `fk_dialogue`, `contraction_ratio`,
   `uncontracted_negatives`, `mean_utterance_words`,
   `long_utterances`) under the dimension so the brief and the
   dashboard can show them. When the book declares no band and no
   register, score to PROSE.md §1, §4 and §6 alone and say so in
   the note. `register_edits` is consumed verbatim by
   `/autonovel:brief` (its `## Register edits` section), so every
   entry must be actionable by a line edit.

   **`show_dont_tell_ratio` (the LLM-judge upgrade to the
   pre-flight scanner).** Run the mechanical scanner first via
   the `Bash` tool:

   ```
   autonovel mechanical show-dont-tell books/{book} --format json
   ```

   Filter the JSON's `chapters` array for the chapter under
   evaluation. Each `candidates` entry is one suspect line
   (kind ∈ {emotion-state, interiority, perception-filter,
   narrator-label}, with a snippet). For every candidate,
   classify the line as one of:

     - **direct**: the narrator names the emotion / mental
       state without rendering it through body, action, or
       perception. *"She felt sad."* / *"He knew his brother
       had betrayed him."* (bare proposition, no anchor).
     - **indirect**: the line *appears* to tell but is anchored
       by sensory or behavioural evidence on either side, OR
       names the state through a body-line (autonomic
       response, micro-action). *"Her shoulders dropped. She
       was tired."* (the body line earns the label.)
     - **hybrid**: legitimate direct telling that's load-
       bearing — interior summary, time compression, a POV
       confession, register-mark in close-third. *"He had
       known the way home since he was six."* The narrator's
       voice is supposed to do this work.

   Compute:
   - `direct_count`, `indirect_count`, `hybrid_count` —
     totals across all candidates the scanner flagged for this
     chapter.
   - `show_dont_tell_ratio = (indirect + hybrid) / total` to
     two decimals (or `1.0` when total == 0). Higher is
     better — a chapter that anchors or earns every flagged
     line is doing show-don't-tell well.
   - `tell_score`: 0–10. Map `show_dont_tell_ratio` linearly
     to the 0–10 band, but penalise raw `direct_count` >
     `chapter_word_count / 500` (more than ~1 direct-tell per
     500 words is "telling-heavy" regardless of ratio).
   - `worst_offenders`: array of up to 5 entries naming the
     `direct`-classified lines with highest weight (longest
     bare-proposition direct tells; emotion-state lines beat
     interiority lines beat narrator-labels). Each entry:
     `{line_no, kind, snippet, why}` — `why` is one short
     sentence on what to embody instead.

   Record the dimension as `{score: tell_score, ratio,
   direct_count, indirect_count, hybrid_count, worst_offenders}`.
   `weakest_moment` for this dimension is the worst_offenders[0]
   snippet; `fix` is its `why`.

   When the scanner returned no candidates (rare; small chapter
   or no tell patterns at all), score `tell_score = 9.0` and
   note `"no tell candidates flagged"` rather than emitting a
   misleading 10/10.

   **`concreteness` (the LLM-judge upgrade to the vagueness
   scanner).** Run the mechanical scanner first via the `Bash`
   tool:

   ```
   autonovel mechanical vagueness books/{book} --format json
   ```

   Filter the JSON's `chapters` array for the chapter under
   evaluation. Each `candidates` entry is one vague line (kind ∈
   {filler-noun, empty-intensifier, empty-evaluative, hedge},
   with a snippet). The scanner over-flags on purpose — judge
   each candidate as one of:

     - **vague**: an abstract stand-in that dodges a concrete,
       specific image — *"it was a beautiful thing"*, *"he felt
       something"*, *"the place was very nice"*. The prose tells
       you a judgement instead of showing the specific that earns
       it. (Same failure as the cryptic teaser VO line "I bought
       speed".)
     - **earned**: legitimate — vague word in dialogue/voice, a
       deliberate withholding, an abstraction the close-third POV
       would actually use, or a word doing real grammatical work
       (*"a couple of days"*).

   Score `concreteness` 0–10: high when nearly every flagged line
   is earned and the prose renders specific, sensory, nameable
   detail; low when abstract filler and empty evaluatives stand
   in for images. Penalise empty-evaluative density most (a
   "beautiful"/"interesting" that names a reaction the reader
   should have had). `weakest_moment` = the most vague line; `fix`
   = the concrete specific it should become (name the thing, the
   number, the sensory detail). When the scanner returned no
   candidates, score 9.0 and note `"no vague candidates flagged"`.

   **`irreversible_change` (Stability Trap antidote).** This is
   the named ceiling failure from the Bells production: AI
   defaults to safe, round-edged chapter endings — the board
   resets between chapters, tension can't compound, the book
   plateaus around pacing 7. The score classifies the chapter's
   ending and trajectory:

     9-10: At least one specific, named, irreversible change
           (death, public revelation, broken oath, signed
           contract, opened door that can't be closed). The
           character or world cannot return to the chapter's
           opening state.
     7-8:  Irreversible change happened, but it's softened
           (deferred consequence, off-page, not the chapter's
           main beat). Still moves the story forward.
     5-6:  Reversible change: something happened that *could*
           be undone, walked back, or revealed as misunderstanding
           in a later chapter. The chapter "advances" but commits
           to nothing.
     3-4:  Status-quo restored: the board ends the chapter where
           it started. The events of the chapter could be cut
           without affecting later chapters.
     1-2:  Pure setup or pure stasis: nothing of consequence
           happened. The chapter exists to fill space.

   Required: `weakest_moment` quotes the chapter's final scene
   when the score is below 7, naming what reverted; `fix`
   prescribes ONE specific irreversible commitment the rewrite
   should make (a line, a death, a refusal, a destroyed object —
   not vague "raise stakes"). Below 6 is added to
   `top_3_revisions` automatically.

   For chapter 1 specifically, additionally check whether the
   ending makes the protagonist incapable of refusing the call
   to action — chapter 1 endings that leave the door open for the
   protagonist to walk away score capped at 7.

7. Mode `--full`: score the book as a book. The aggregate is weighted
   toward structure so that it cannot be carried by chapter prose: a
   book of strong chapters that do not cause each other is a weak novel,
   and before this weighting the per-chapter tier was all the
   pipeline measured (on *kingmaker* every chapter held 7+ while the
   author read the book as "a bunch of short anecdotes").

   **Inputs.** Use `bash` to run `autonovel mechanical
   structure-dossier books/{book}` once: the outline's acts and spine
   sections, every chapter's full continuity summary
   (`books/{book}/chapters/ch_NN.summary.md`), word count, position
   in the book, story_time and gap from the previous chapter, the
   latest chapter score and the climax window. Glob
   `books/{book}/chapters/*.md` in order and take each chapter's
   opening and closing 500 chars and outline beats as before; read a
   chapter in full wherever a structure dimension below turns on it.
   When `books/{book}/edit_logs/structure_review.json` exists, run
   `autonovel mechanical structure-validate books/{book}`: if it is
   valid and its gate is not `stale`, use its tables (causal chain,
   escalation, removability, climax) as the evidence for the
   structure block and do not score any structure dimension more than
   one point above what those tables imply; record its
   `structure_score` as `structure_review_score`. Otherwise judge the
   structure block yourself from the summaries and prose, and set
   `top_suggestion` to "run /autonovel:structure-review --book {book}"
   unless something more urgent applies.

   **Dimensions and weights** (each `{score, weakest_moment, fix,
   note}`, 0–10; record the weights as `dimension_weights`):

   | Group (weight) | Dimension | Weight | What it measures |
   |---|---|---|---|
   | Structure (50%) | `causal_chain` | 15 | Share of chapter N → N+1 links where N+1 happens *because of* an earlier chapter (an event, not a motif, callback, carried clock or promise line). Score ≈ 10 × because-share; −1 if an act boundary is only "happens after". |
   | | `through_line` | 10 | One question about the protagonist, posed in the first quarter, answered by the climax's decision. 9-10 posed ≤15% and answered by a decision; 7-8 posed ≤25%; 5-6 posed late or answered only thematically; 3-4 several questions, none dominant; 1-2 none. |
   | | `escalation` | 10 | Per act, the stake is strictly higher than the previous act's *on the same bet*. 9-10 every act raises it; 7-8 one plateau; 5-6 grows in size but resets in kind (new counterparty, new bet); 3-4 flat; 1-2 falls. |
   | | `removability` | 10 | For each chapter, does a later chapter's action fail if it is cut? 10 minus 2 per removable chapter minus 0.5 per weak one, floor 1. List them as `removable_chapters`. |
   | | `climax_convergence` | 5 | Do the last ~20% force the open threads into one decision (9-10: three or more; 7-8: two) or close them one by one (5-6), or drop some (≤4)? |
   | Arc & payoff (20%) | `arc_completion` | 7 | The protagonist ends truly different, at a cost. |
   | | `irreversible_change_arc` | 5 | The chapter-pair state test below. |
   | | `foreshadowing_resolution` | 4 | Plants paid, payoffs planted. |
   | | `clocks_paid` | 4 | The clock ledger below. |
   | Reader pull (15%) | `pacing_curve` | 8 | Tension rises into the climax; no three-chapter decline. |
   | | `overall_engagement` | 7 | Would a reader keep turning pages, and because of what. |
   | Prose & consistency (15%) | `voice_consistency` | 4 | |
   | | `show_dont_tell_arc` | 4 | The whole-book show-vs-tell pass below. |
   | | `theme_coherence` | 4 | |
   | | `world_consistency` | 3 | |

   **Aggregate.** `structure_subscore` = the weighted mean of the five
   structure dimensions. `weighted_mean` = the weighted mean of all
   fifteen. `raw_novel_score = min(weighted_mean, structure_subscore +
   1.0)` — the cap is the point: no amount of prose lifts a book more
   than one point above its structure. `novel_score` is
   `raw_novel_score` minus the slop penalty (step 9). Include
   `structure_subscore`, `weighted_mean`, `structure_cap_applied`
   (true when the cap bound), `weakest_dimension`, `weakest_chapter`,
   `top_suggestion`. Strong prose is not evidence of structure: never
   raise a structure dimension because the chapters read well.

   **`clocks_paid` (whole-book clock ledger).** From the chapter
   closings and openings, list every deadline, ultimatum or dated
   promise a chapter ends on or sets, and for each the chapter and
   manner of its payment: `scene` (the POV acts in the scene where it
   runs out), `summary` (reported after the fact, "Georg wrote; I've
   got till Michaelmas"), `carried` (named again with the date still
   standing) or `unpaid`. Emit `clocks: [{set_in, clock, paid_in,
   paid_as}]` and `unpaid_or_summary_clocks` as a list of chapter
   numbers for the brief / revise loop. Score as the foundation
   dimension of the same name. This is the one structural fault a
   per-chapter eval cannot see and a reader panel always does.

   **`show_dont_tell_arc` (whole-book show-vs-tell)**: run the
   mechanical scanner once (`autonovel mechanical show-dont-tell
   books/{book} --format json`), classify every candidate across
   the book the same way `--chapter` mode does (direct /
   indirect / hybrid), and aggregate to a per-chapter
   `show_dont_tell_ratio_per_chapter[N]` array plus a book-level
   ratio. Surface the chapters whose ratio drops below 0.6 as
   `tell_heavy_chapters` so the brief / revise loop has a target
   list. Score 0–10 the same way `--chapter` does, scaled for
   the book.

   **`irreversible_change_arc` (whole-book Stability Trap check).**
   Walk every chapter pair (N → N+1) and ask: "Could chapter N+1
   have started from chapter N's *opening* state instead of its
   *closing* state?" Every "yes" is a chapter that didn't change
   the world. Score the book on the ratio:

     9-10: Every chapter's closing state is load-bearing for the
           next chapter (or the climax). No chapter could be cut
           without breaking later chapters' premises.
     7-8:  ≤2 chapters could be cut without breaking later
           chapters; book commits to its consequences.
     5-6:  3-5 chapters are essentially reversible / cuttable; the
           middle sags because the board keeps resetting.
     3-4:  Half the book leaves the world unchanged; suspect a
           series of "filler" chapters in the middle act.
     1-2:  Only the climax commits to anything; the rest is stalling.

   Required when the score is below 8: a `cuttable_chapters` list
   naming each chapter that fails the "could chapter N+1 have
   started from N's opening state?" test, with one line of
   evidence per chapter. This is the load-bearing surface for
   the user's revision plan.

8. Mode `--compare <N>,<M>`: use `file_read` on
   `books/{book}/chapters/ch_{chapter}.md` for each of N and M (truncate
   to ~3000 words each if longer). With `--vs-book <other>`, chapter M
   is read from `books/<other>/chapters/ch_M.md` instead — the
   cross-book head-to-head (old chapter N of a finished book against
   new chapter N of its rewrite is the natural progress metric for a
   second version). Pick the better one — no ties allowed. Emit
   `{winner, winner_chapter, winner_book, margin, decisive_moment,
   winner_strength, loser_weakness, best_sentence_a, best_sentence_b}`
   (`winner_book` equals `--book` unless `--vs-book` won). Judge both
   against the SAME rubric but each against its OWN book's voice.md —
   a rewrite in a plainer register is not penalised for not sounding
   like the original.

9. Mechanical slop penalty. For `--chapter` and `--full`, before writing
   the log, use `bash` to run
   `autonovel mechanical slop <chapter-path>` for each chapter
   under evaluation and parse its JSON. Record the per-chapter
   `slop_penalty` under `result["slop"]` (for single-chapter) or
   `result["slop_per_chapter"][N]` (for full). Subtract `slop_penalty`
   from the judge's score to produce `overall_score` (or `novel_score`),
   keeping the unadjusted value as `raw_judge_score` /
   `raw_novel_score`. Do NOT run the slop scanner for `--phase` or
   `--compare`.

10. Period bans. If `shared/period_bans.txt` exists and is non-empty,
    also run `bash: autonovel mechanical period-bans
    <chapter-path> shared/period_bans.txt` for each chapter under
    evaluation. Record the `hits` list under `result["period_ban_hits"]`.
    A single period-ban violation caps `canon_compliance` at 6; three or
    more caps it at 4.

10a. Bigram cliché scan. For `--chapter` and `--full`, run
    `bash: autonovel mechanical cliches <chapter-path>` for each
    chapter and parse its JSON. Record under
    `result["cliches"]` (for single-chapter) or
    `result["cliches_per_chapter"][N]` (for full). The scanner's
    `density_per_1000_words` field adds to the slop penalty:
    every full unit of density above 2.0 subtracts 0.1 from
    `overall_score`, capped at 0.5 total. (Empirically, well-edited
    prose runs <2 cliché-bigram hits per 1000 words; >5 reads
    AI-tinged.)

10b. Sensory-channel balance. For `--chapter` and `--full`, run
    `bash: autonovel mechanical sensory <chapter-path>` for each
    chapter and parse its JSON. Record under
    `result["sensory"]` / `result["sensory_per_chapter"][N]`. If a
    chapter has a `dominant_channel` (one channel >70% of all
    sensory hits), call it out in the `weakest_moment` field for
    that chapter — visual dominance is the most common AI tell;
    it reads as a film-script camera move rather than a scene with
    a body in it. Do not subtract from the score automatically; the
    judge weighs it as one signal among many.

10e. **Per-scene beat coverage.** For `--chapter` and `--full`,
    run `bash: autonovel mechanical scenes <chapter-path>` for each
    chapter and parse its JSON. The output gives a stable per-scene
    index (`scene_count`, then a `scenes` list with `index`,
    `word_count`, `opening_line`, `closing_line` for each).

    For each scene in each chapter, score the **four story beats**
    on a 0/1 binary (present / absent):

      - **goal** — does someone in the scene want something
        specific (not just emotional valence)?
      - **conflict** — is there resistance to that want (another
        character, the world, the POV's own contradiction)?
      - **disaster_or_decision** — does the scene turn (the want
        is denied / a bad result, OR the POV makes a choice they
        can't unmake)?
      - **consequence** — does the scene's end change something
        going forward (knowledge, relationship, position, stakes)?

    Aggregate per chapter into `beat_coverage` block:

    ```json
    "beat_coverage": {
      "score": 7.5,
      "scenes": [
        {"index": 1, "beats_hit": ["goal", "conflict", "consequence"],
         "beats_missed": ["disaster_or_decision"]},
        {"index": 2, "beats_hit": ["goal", "conflict",
         "disaster_or_decision", "consequence"], "beats_missed": []}
      ],
      "weakest_scenes": [
        {"index": 1, "missed_count": 1,
         "fix": "scene 1 ends without anyone changing — give Tommaso a "
                "decision he can't take back before the break"}
      ]
    }
    ```

    Scoring: every beat is worth 2.5 points; per-chapter score is
    the average across scenes. **A scene missing 2 or more beats
    goes into `weakest_scenes`** with a one-sentence prescription
    naming the missing beat and what to add. brief.md walks
    `weakest_scenes` and names them by index — that's the load-
    bearing surface that turns "tighten chapter 8" into "scene 8.2
    needs a decision before the break". Single-scene chapters
    (no `***` breaks) are scored as one scene; the prescription
    might be "split into two scenes around the midpoint
    decision".

    For `--full` mode, record `beat_coverage_per_chapter[N]` and
    surface a top-line `book_beat_coverage_score` averaging the
    per-chapter scores. Chapters whose score is below 6 go into
    a `weak_beat_coverage_chapters` list at the top level —
    these are the chapters whose middles drift, which is the
    "drifting middle" Bells failure mode.

10d. **Custom-rubric scoring.** When step 4a parsed at least one
    bullet criterion, score each one in addition to the standard
    rubric. For each criterion:
      - Apply the rule to the chapter (or, in `--full` mode, to
        every chapter and aggregate).
      - Score 0–10 (10 = chapter fully respects the rule; 0 = the
        rule is grossly violated). Use the same calibration as the
        standard rubric.
      - Surface a one-sentence finding: what the chapter did vs.
        what the rule asked for. Quote a passage when violated.
    Record under `result["custom_rubric"]` as a list of
    `{criterion, score, finding}` objects (single-chapter mode) or
    `result["custom_rubric_per_chapter"][N]` (full mode). Any
    criterion with a score below 6 is also added to the
    `top_3_revisions` list so brief picks it up. Do NOT subtract
    from `overall_score` automatically — the judge weighs custom
    rubric findings as one signal among many; the visible flag in
    the eval log + the brief is the load-bearing surface.

10c. First-page hook (for `--chapter 1` only). Read the first
    250 words of the chapter and score them on a separate
    `hook_strength` dimension (0–10) covering: specific image in
    line 1, stakes implied by line 3, voice signature visible
    early, no info-dump preamble. Record the score under
    `result["hook_strength"]` alongside the regular dimensions.
    Don't subtract from the overall score; it surfaces as its own
    line in the summary table so the user can see whether chapter
    1 is doing the work it needs to.

11. Use `file_write` to save the eval log to
    `books/{book}/eval_logs/<timestamp>_<mode>.json` where `<timestamp>`
    is `YYYYMMDD_HHMMSS` and `<mode>` is one of `foundation`,
    `ch{chapter:02d}`, `full`, `compare_{N}_vs_{M}`.

12. Print a one-screen summary to stdout. **Render the per-dimension
    scores as a real markdown table** so the user gets a visually
    aligned grid, not a wall of `dimension: 6.5` text. The exact
    shape varies by mode but the table format is mandatory:

    For `--chapter` mode:

    ```markdown
    | Dimension | Score | Weakest moment / Note |
    |---|---|---|
    | voice_adherence | 7.2 | "She felt the chill" — telling not showing |
    | beat_coverage | 6.5 | midpoint reversal landed flat |
    | character_voice | 7.8 | — |
    | prose_quality | 6.9 | three "she did not" patterns in 2400w |
    | register | 6.0 | FK narr 5.8 in band; 11 utterances >40w; "That's the bell, at the end there" explains to the listener |
    | engagement | 7.0 | — |
    | internal_consistency | 8.0 | — |

    **Overall:** 7.1 (raw 7.4 − slop 0.3)
    **Weakest:** beat_coverage (6.5)
    **Top fixes:** … (one bullet each)
    ```

    For `--phase foundation` and `--full` use the same table shape
    with the dimensions appropriate to the mode (lore /
    character / structure / craft for foundation; for full, the
    fifteen dimensions in their four groups with a Weight column,
    structure group first, then a line
    `**Novel:** N (structure X.X; weighted mean Y.Y; cap applied:
    yes/no; − slop Z)`).

    Render every dimension on its own row. Missing values get an
    em-dash, never a blank cell. Do not skip the table because the
    text list "felt enough"; per author testing 2026-04-25 the
    table is what makes the score block scannable.

    **For `--full` mode, also emit a pacing-curve table** showing
    the shape of the book chapter-by-chapter. This is the
    reader-interest signal — flat curves bore, curves with a
    consistent rise into the climax engage. The shape:

    ```markdown
    | Ch | Words | Score | Tension | Dialogue % | Scenes | Beats hit |
    |---|---|---|---|---|---|---|
    |  1 | 3100  | 7.4 | 6.5 | 22% | 2 | 4/4 |
    |  2 | 2950  | 6.8 | 7.0 | 35% | 3 | 3/4 |
    |  3 | 3200  | 7.1 | 7.5 | 18% | 2 | 4/4 |
    | …  | …     | …   | …   | …   | … | …   |
    ```

    Pull `Words` from each chapter's frontmatter or recompute,
    `Score` from the latest eval log, `Tension` from the per-chapter
    judge pass (1-10 scale; how taut the chapter feels), `Dialogue %`
    by counting lines between paragraph breaks that begin with `"`,
    `Scenes` by `***` or scene-break markers, `Beats hit` against
    the outline entry's beats list.

    **Tension-drop alarm for `--full`.** After the table, scan the
    Tension column for any window of three or more consecutive
    chapters where each chapter's tension is lower than the
    previous one's. Surface each such window:

    ```
    ⚠️  Tension drop detected: chapters 7→8→9 trend down (7.5 → 6.8 → 6.0).
        Recommend /autonovel:revision-pass --chapters 7-9 with
        focus on stakes-escalation.
    ```

    These warnings are reader-interest signals — a 3-chapter
    decline is the kind of mid-book sag readers DNF on. Even when
    individual chapter scores are above threshold, the *trend*
    matters.

    **First-page hook line for `--chapter 1` mode.** When the
    invoked chapter is chapter 1, also surface the
    `hook_strength` score from step 10c on its own line under
    the dimension table:

    ```
    **First-page hook (first 250 words):** 7.0
    ```

    Below 6.0 is a real concern — chapter 1's opening is what
    decides whether a reader continues. Suggest
    `/autonovel:revise 1 --from auto` and call out the hook
    weakness in the brief.

    **Custom-rubric findings table** (when step 10d ran with at
    least one criterion). Render under the dimension table as its
    own block:

    ```markdown
    **Custom rubric (book-specific):**

    | Criterion (first 60 chars) | Score | Finding |
    |---|---|---|
    | At most 2 financial transactions per chapter | 5.0 | 4 ledger entries on p.3; arithmetic crowds out scene |
    | Ending must commit to one irreversible thing | 7.0 | — |
    ```

    Use the criterion's leading text (truncated to 60 chars +
    ellipsis) as the row label. Render `—` when there's no finding
    to report. This is the load-bearing surface for per-book
    rules; do not collapse it into a single line.
</workflow>

<scoring-calibration>
  9-10: Could not improve with a month of editorial work. Name a specific
        published work it competes with, or do not give 9+.
  7-8:  Strong. Skilled author could draft from this with minimal invention.
  5-6:  Functional but thin. Writer would have to invent on the fly.
  3-4:  Sketchy. More questions than answers.
  1-2:  Placeholder.
  0:    Empty or missing.

  Median chapter score is 6. An 8 is exceptional. A 9 is rare. A 10 does
  not exist for a first draft. Err toward lower scores. For EVERY
  dimension, identify the biggest gap and a concrete improvement.
</scoring-calibration>

<acceptance>
- A JSON eval log is written under `books/{book}/eval_logs/`.
- The log contains a numeric top-line score
  (`overall_score` / `novel_score` / `winner`).
- For chapter and full modes the log contains a `slop` block with
  numeric `slop_penalty`, and `overall_score` equals
  `raw_judge_score - slop_penalty` rounded to 2dp.
- For full mode the log contains the fifteen dimensions of step 7,
  `dimension_weights`, `structure_subscore`, `weighted_mean` and
  `structure_cap_applied`, and `raw_novel_score` is at most
  `structure_subscore + 1.0`.
- For foundation mode the log contains `causal_spine`.
- For compare mode the log contains a non-null `winner_chapter` equal
  to one of the two compared chapter numbers.
</acceptance>
