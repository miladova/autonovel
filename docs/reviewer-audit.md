# Reviewer audit: book-level judgement (2026-10-17)

The question, from the author after 24 chapters of *kingmaker*
(series `medieval-king-maker`): *"I don't feel I have a good sense of how
the plot develops — it feels a little like a bunch of short anecdotes and
not a continuing story building to a climax."* Line and paragraph prose
"is starting to seem reasonable"; the worry is the whole-book tier, and
"we rely on [the reviewers] for quality writing — perhaps we need a
better/different/improved full book reviewer?"

This document audits every command that judges or enforces book-level
quality, shows what the kingmaker reviewers actually said, and records
what shipped in response. Evidence was read from
`books/kingmaker/edit_logs/review.md` + `review.json`,
`reader_panel.json`, `eval_logs/` (113 logs), `outline.md`, `seed.txt`,
the 24 `ch_NN.summary.md` files and `briefs/ch16.md`, all read-only.

## Verdict

1. No book-level reviewer asked a causal question. `review` asked for an
   editorial letter, `reader-panel` asked ten local questions, and
   `evaluate --full` read only the first and last 500 characters of each
   chapter (and never ran on kingmaker: 0 of 113 eval logs are `_full`).
2. The chapter-tier rubrics actively rewarded closed episodes: a stake
   in the first 500 words settled by the end, an irreversible change per
   chapter, every dated clock paid as its own scene. A chapter that
   opens and settles its own wager scores best on all of them.
3. The reviewers read bookkeeping as architecture. They saw the
   episodic stretch, then hedged it ("Individually each scene is fine,
   and the strain is a cost of ambition"), praised a recurring ledger
   image as "the spine", and counted paid narrator promise lines as
   "the architecture of promise and payment". The stop rule then
   counted those hedges toward stopping.
4. Nothing downstream could act on a structural finding: `brief` and
   `revise` are per-chapter by construction, and the outline committed
   to a sequence of wagers, not to a stakes ladder or a causal spine.
5. Answer: a **different** full-book reviewer — a new
   `/autonovel:structure-review` with its own inputs, rubric, sycophancy
   guards and machine-readable output — plus improvements to `review`
   (stop rule gated on it), `reader-panel`, `evaluate --full`, `brief`,
   `revise`, `revision-pass`, `gen-outline`, `draft` and `draft-pass`.

## What the kingmaker reviewers said

| Reviewer | Saw the episodic shape? | How it was framed | Effect |
|---|---|---|---|
| `review` critic | Partly: "Then the book does something brave: it keeps going." "Covering fifty-two years in twenty-four chapters means time-jumps and a cast that has to keep arriving and departing. Some figures … do their business and simply stop." | "There are costs." Then ★★★★. | No item. |
| `review` professor | Asserted the opposite: "The book reads as one line. The spine is the two-page ledger Jakob learns in Ch 2 … That spine runs from the slate in Ch 1 to the unruled margin beside 'Bubenhausen, short' in Ch 24." | A motif named as the spine. (The seed had said: "Drop: the ledger-as-metaphor framing".) | "This is a finished novel with a real spine … The work left is protection, not repair." |
| `review` item 11 | Yes, locally: "Ch 16 covers 1512–1515 in three business scenes." | "Individually each scene is fine, and the strain is a cost of ambition in a fifty-two-year book." Typed `compression`, `minor`, `qualified: true`. | Counted toward "most items are qualified hedges → stop". |
| `review` items overall | — | 0 of 11 items typed `structural`; items 1–9 are continuity, promise lines, tics and glosses. | `stop_revising: false` only because of two mechanical majors. |
| panel, editor | No. | "The condition is a copy-edit for repetition, not structure. The architecture of promise and payment across fifty years is the book's real achievement." | Would buy. |
| panel, genre reader | Saw a list and called it a ladder: "Up to then every act had raised the stakes: Scutari, then the pepper short, then Tyrol, then the copper corner, then India." | Five separate bets read as escalation; the fix asked for was local ("rebuild Ch 15-16 into a single chapter"). | Would buy. |
| panel, writer | Yes, locally: "Ch 16 then covers three years in three loosely joined episodes … that's the place where I could see the outline." | One sag, not a shape. | "Yes, without conditions." |
| panel, all four `earned_ending` | No. | Answered as a plant→payoff ledger: "Leipheim was planted on the Fondaco roof in Ch 3 ('Fugger money would pay the soldiers who did it') and is paid …" — a narrator flash-forward, not a cause. | "Yes, it's earned." ×4 |

The shape was designed in. `seed.txt`: "The book's spine is that wager,
raised four times — Tyrol 1488, Hungary 1495, the Venice copper corner
1498–1502, Frankfurt 1519" and "Every chapter is a wager. In the first 500
words the reader knows what Jakob (or Konrad) can lose in this chapter; by
the end it is won, lost, or raised." `outline.md` line 3: "Every chapter is
a wager: the first beat names what the POV can lose, the last beat settles
or raises it." Act One: "The spine under the six wagers … each chapter
ends with the number changed and one *first* banked." Act Three is titled
"four bets". `voice.md` Part 3 then enforced "Stake in 500 words" on every
chapter through `evaluate` and the panel.

What the data alone shows (`autonovel mechanical structure-dossier
books/kingmaker`, no judgement): 14 of the 23 chapter transitions cross a
year or more of story time (56 months between ch 9 and ch 10); the only
tight run is ch 18–21, the 1519 election. The seed's own dramatic
question — "The man who owns the news has to decide whether to publish
it" — needs the receipts, and the receipts begin in ch 19–20 ("Receipts",
74–79% of the book) and become a question in ch 22 (88%). This audit's
reading of the summaries (to be confirmed by the acceptance run below):
a latent causal spine exists — the Habsburg debt that passes from
Sigismund (ch 7–9) to Maximilian (ch 9–19) to Charles (ch 19–23) — but
chapters 1–6 (Venice), 10 and 12–13 (copper, India) and 15 hang off it as
closed wagers, the rivals rotate act by act, and the "spine" every
reviewer named was the ledger motif.

## Root causes

1. **No causal question anywhere.** Not one rubric line asked whether
   chapter N+1 happens *because of* chapter N, whether act stakes rise
   on the same bet, what single question the book answers, or which
   chapter could be cut.
2. **Chapter-local success trains episodes.** "Stake in 500 words",
   `irreversible_change` per chapter, PROSE.md §5 rule 4 ("The scene
   ends with the question answered against the character") and the
   clock rule ("a clock set on the page is paid on the page") each
   reward a chapter that opens and settles its own bet. None asks that
   the result become the next chapter's problem.
3. **Ledgers mistaken for structure.** The summary format (Threads
   opened / closed, Clocks, Promise), `clocks_paid` and the narrator's
   promise lines produce a dense web of plants and payoffs. The
   reviewers read that web as architecture. A paid callback is
   continuity, not cause.
4. **A stop rule that rewards hedging.** `review.md`: stop when "most
   flagged items are qualified hedges ('individually fine', 'largely
   successful', 'cost of ambition')". The one structural observation
   was phrased in exactly those words and counted toward stopping.
5. **A blind and unused whole-book scorer.** `evaluate --full` built its
   picture from "opening 500 chars, closing 500 chars, word count" per
   chapter, had no weights, and its only dependency test
   (`irreversible_change_arc`: "Could chapter N+1 have started from
   chapter N's *opening* state…?") measures state change, which every
   kingmaker chapter passes — Jakob is richer or poorer at every chapter
   end.
6. **Structural fixes made it worse.** The `## Structural findings`
   section of `brief` prescribes intra-chapter scenes: "a clock set
   here and paid offstage in the next chapter, a pivot told in
   pluperfect…". On kingmaker, `briefs/ch16.md` used it to add a new
   opening negotiation that pays ch 15's "by spring" clock — and the
   panel's editor then named ch 16's first half "clock-paying
   bookkeeping", the book's worst sag.
7. **The earlier "spine" fix was a narration device.** On 2026-10-15
   the author already reported "six wagers with no felt spine" for
   kingmaker ch 1–9 (STATE.md decisions log). The response admitted
   the narrator's *promise line* (PROSE.md §7.3: "one a chapter at
   most, tied to the book's spine") and the §10 checklist's only spine
   test became "flag a chapter with no promise line and no named step".
   That made each chapter *point at* the future without making the
   next chapter *follow from* it; the reviewers then read the ~20 paid
   promise lines as "the architecture of promise and payment". PROSE.md
   §7.3 and §10 now say a promise line is a callback, not a cause, and
   point at the book-level test.
8. **The teaser tier was stricter than the book tier.** `teaser-beats`
   / `shot-prompts` require a story spine (dramatic question, want vs
   opposing force, the turn, a stakes ladder) and `teaser-critique`
   blocks a render on a "list, not a spine". The book pipeline had no
   equivalent.

## Per-command audit

The five questions: **Q1** does it measure causal chain, escalation,
through-line, climax build, removability? **Q2** can "every chapter is
good" pass as "the book is good"? **Q3** can it produce or act on a
structural brief? **Q4** does the outline commit to a stakes ladder and a
causal spine that drafting is held to? **Q5** where is the stop-revising
decision, and is it prose-weighted?

### `evaluate --full` (and `--phase foundation`)

- **Before.** Q1: partly — `arc_completion`, `pacing_curve`,
  `theme_coherence`, `foreshadowing_resolution`, `world_consistency`,
  `voice_consistency`, `overall_engagement`, `irreversible_change_arc`,
  `show_dont_tell_arc`, `clocks_paid`; no causal chain, through-line,
  escalation or removability dimension; `cuttable_chapters` only
  "Required when the score is below 8". Inputs: "opening 500 chars,
  closing 500 chars". Q2: yes — `novel_score` was an unweighted judge
  score, and seven of ten dimensions are chapter aggregates. Foundation:
  "structure 20%" was `outline_completeness`, `foreshadowing_balance`,
  `clocks_paid` — no spine check.
- **After.** Fifteen dimensions in four weighted groups, structure 50%
  (`causal_chain` 15, `through_line` 10, `escalation` 10,
  `removability` 10, `climax_convergence` 5); inputs from the
  structure dossier (full summaries, positions, gaps) and, when fresh,
  the structure review's tables. **`raw_novel_score = min(weighted_mean,
  structure_subscore + 1.0)`** — prose cannot lift the book more than
  one point above its structure. Foundation gains `causal_spine`
  (scores the outline's spine sections; capped at 5 when absent). Full
  table in `commands/evaluate.md` step 7 and `docs/commands.md`.

### `review`

- **Before.** Q1: no — the prompt is "Review it first as a literary
  critic … then as a professor of fiction … Be fair but honest; you
  don't have to find defects." Q2: yes. Q5: the stop rule lived here and
  was prose-weighted, with hedges counting toward stopping.
- **After.** The stop verdict needs **both** the book-level gate
  (`autonovel mechanical structure-validate books/{book}` →
  `gate.passes`: a fresh, valid `structure_review.json` scoring ≥ 4 with
  no removable chapter; missing or stale → "run
  /autonovel:structure-review first") **and** the Bells prose rule.
  Items about order, causation, act stakes, a removable chapter or an
  episodic stretch are typed `structural`, are never `qualified`, and a
  major/moderate one blocks. The professor is told a motif is not a
  spine and must name the spine as a chain of causes per act. The
  review stays an editorial letter; it is no longer the structure judge.

### `reader-panel`

- **Before.** Q1: no — `momentum_loss`, `earned_ending`,
  `cut_candidate`, `missing_scene`, `thinnest_character`, `best_scene`,
  `worst_scene`, `would_recommend`, `haunts_you`, `next_book`. Step 3:
  "do not send the full prose to every persona — the arc summary
  [opening/closing 500 chars] is enough". Q2: yes — four "would buy".
- **After.** Four book-level questions per persona:
  `book_in_one_sentence` (what it is about and the question it
  answers), `felt_like_episodes`, `chapter_to_cut` (a whole chapter,
  or "none" with the chapter each is needed for), `pulled_vs_informed`;
  a `book_level` block (`one_sentence_agreement`, `episode_votes`,
  `cut_votes`, `informed_not_pulled`); the arc summary now carries each
  chapter's summary Plot/Threads lines; `earned_ending` is told a paid
  callback is not an earned ending.

### `brief`

- **Before.** Q3: no structural brief type. `## Structural findings`
  appeared "only when the panel or the review names this chapter" and
  prescribed intra-chapter scenes (see root cause 6).
- **After.** `--from structure` and `--from auto` read
  `structure_review.json`; a candidate naming the chapter makes the
  brief `kind: structural` (frontmatter marker, `structural_candidates`,
  `source`), with `## Structural brief` (the chapter's new job, the
  links in and out, the act's rung, the instruction as scene terms,
  allowed within-chapter moves, what must not change) and `##
  Cross-chapter operations — run these yourself` listing the exact
  `/autonovel:merge-chapters` / `remove-chapter` / `reorder` /
  `split-chapter` command. Structural candidates outrank every line
  edit; length range ±25%.

### `revise` and `revision-pass`

- **Before.** Q3: "Follow the brief exactly"; ±15% length; no notion of
  a change to the chapter's job.
- **After.** `revise` step 7a: a `kind: structural` brief permits
  adding, cutting, merging or reordering scenes inside the chapter,
  moving a reveal, retargeting the stake, changing the ending — and
  forbids touching any other chapter; cross-chapter commands are
  printed for the author, never executed. `revision-pass --chapters
  structural` resolves to every chapter a candidate names (refuses when
  chapters were renumbered since the review), tags structural briefs in
  its per-chapter line, collects the cross-chapter commands, and puts
  `/autonovel:structure-review` first in its re-review closer.

### `gen-outline`, `draft`, `draft-pass`

- **Before.** Q4: no. `gen-outline` asked for "stable rising action, a
  midpoint reversal, a costly climax" and per-chapter beats — a
  sequence of scenes. `draft` held each chapter to its beats only;
  `draft-pass` gated on chapter score only.
- **After.** `gen-outline` writes three parseable sections — `## Spine`
  (`question:`, `posed_in:`, `want:`, `opposing_force:`…), `## Stakes
  ladder` (one row per act, "higher than the last act because"), `##
  Causal spine` (`- N because M: <event>`; `after` marks a known weak
  link) — groups chapters under act headings, and `--add-spine`
  retrofits an existing outline without touching its chapter entries.
  `draft` step 3a holds each chapter to its causal lines (open on the
  earlier event, stake = the act's rung, end on the hand-off fact);
  `draft-pass` adds a SPINE CHECK that sends a chapter to a
  `kind: structural` revise even when it scores above threshold, and
  `--deep` runs the structure review first. Old outlines keep working:
  absent sections produce a warning and a pointer to `--add-spine`.

### `next`, `run-pipeline`, the TUI

`/autonovel:next` (MEDIUM): run the structure review on a drafted book
that has none; re-run it when stale or invalid; act on it
(`/autonovel:revision-pass --chapters structural`, plus its
cross-chapter commands) while the gate blocks. `run-pipeline` stops a
revision loop only when the score plateau **and** the structure gate
agree. The TUI's Reviews tab shows `structure_review.json` and its score.

## The historical-fiction trap

The record is episodic by nature: deals, deaths, elections, wars arrive
on their dates. A historical novel that follows the record is a
chronicle however vivid each event is. The new tools check that the
novel imposes a spine the history lacks: `structure-review` ground rule
4 ("History is not causation"), its step 9 (for each staged recorded
event: does it land *because of* something the protagonist did earlier,
or does it simply arrive?), the `chronicle-spine` failure mode, and the
`gen-outline` instruction to invent the opposing force that persists
between recorded events and the earlier choice each event punishes or
rewards — never by changing a recorded date or outcome.

## Why a new command, not `review --structure`

- **Different job, different guard.** The review is an editorial letter;
  its value is in line and scene items. Asking the same call to judge
  structure lets the critic's warmth anchor the professor (kingmaker's
  critic called it "one of the most satisfying historical thrillers I
  have read in years" one stage before the professor found "a real
  spine"). The structure reviewer reads no other reviewer until its
  tables and score are written, and may not raise its score afterwards.
- **Different inputs and discipline.** Seed + outline + every summary +
  the dossier + the full prose; default "happens after" until a
  concrete plot fact proves "because"; one row per chapter pair and per
  chapter, so nothing can be skipped.
- **Machine-readable output.** Tables and 3–7 candidates that
  `brief` consumes, a gate that `review`, `next` and `run-pipeline`
  consume, and its own staleness.
- **Mechanical guard against a sycophantic score.** `structure-validate`
  checks the shape and applies the rubric caps as arithmetic over the
  reviewer's *own* tables (e.g. any removable chapter caps the score at
  3; a because-ratio under 0.5 caps it at 2; the named `anecdote-chain`
  caps it at 2). A 4/5 beside a table that says most links are "happens
  after" is rejected as invalid. Python never judges a link; it only
  holds the judge to its own evidence.

## The structural brief type

```
---
kind: structural
structural_candidates: [S2, S5]
source: books/<book>/edit_logs/structure_review.json
---
## Structural brief
## Cross-chapter operations — run these yourself
## Chapter N — revision target
…
```

Candidate kinds: `add-consequence-scene` (turn an "after" link into a
"because"), `retarget-stake` (the cure for a reset ladder),
`pose-question-earlier`, `thread-the-antagonist`, `move-reveal`,
`plant-earlier`, `converge-climax`, and the cross-chapter `merge`,
`cut`, `reorder`, `split` (each with its exact command, run by the
author). Every candidate carries per-chapter scene instructions and the
links, rungs or removable chapters it fixes.

## The stop-revising decision, before and after

| | Before | After |
|---|---|---|
| Where | `review.md` only | `review.md` (verdict), `structure-validate` (gate), `next` and `run-pipeline` (consumers) |
| Book-level input | none | `structure_review.json`: fresh, valid, score ≥ 4, no removable chapter |
| Hedged items | counted toward stopping | still count for prose items; never for `structural` items |
| Missing evidence | n/a | "run /autonovel:structure-review first" |

## Acceptance test (for the integrator)

On kingmaker, read-only except for the two new edit logs:

```text
autonovel refresh-templates            # picks up CRAFT.md §1 "Causation, not sequence"
/autonovel:structure-review --book kingmaker
autonovel mechanical structure-validate books/kingmaker --format markdown
```

Expected: a valid file; the book's 4★ prose does not lift its structure
score; the author's symptom is named (`anecdote-chain` and/or
`reset-ladder`, `late-through-line`, `motif-spine`); removable chapters
and 3–7 candidates with per-chapter instructions; gate BLOCK. If it
passes kingmaker at 4–5, the prompt has failed its purpose.

## Leftovers (consciously not done)

- **Not run on a real book.** Running the LLM commands is the
  integrator's acceptance step above; the cap thresholds (0.50 / 0.65 /
  0.80 because-ratio, 25% removable) are first calibrations and should
  be revisited after kingmaker and one more book.
- **`next_step.py` decision table unchanged.** The pure state machine
  still routes revision → panel → brief → review; the structure gate
  lives in `/autonovel:next`'s situational actions, `review`'s stop
  verdict and `run-pipeline`. Adding a `structure_review_done` field to
  `PipelineState` is a follow-up if the canonical footer should name it.
- **Story-map integration.** `structure-review` reads
  `books/<book>/threads.md` when the story-map ledger exists, but the
  story-map view does not yet render `structure_review.json`'s causal
  chain or ladder.
- **Series level.** `evaluate --phase series` and `series-arc` were not
  given the causal-chain treatment across books.
