# Editorial practice: pipeline audit

The study text this audit measures against — how professional editors,
agents and critics read, diagnose and fix a novel (§0–§20, sources §21) —
ships to every series as `shared/craft/EDITING.md`
([`src/autonovel/templates/series/shared/craft/EDITING.md`](../src/autonovel/templates/series/shared/craft/EDITING.md);
repo-root symlink `EDITING.md`). `/autonovel:developmental-edit` reads it
every run. The § numbers below refer to it. This file keeps Part VII, the
audit of this repo's pipeline against it, which does not belong in a
series. Research done 2026-10-17; the working notes with every URL and
its verification status were kept in that session's scratchpad.

# Part VII — Audit of the autonovel pipeline (repo only)

## §21 Scope and method

On 2026-10-17 each checklist item was looked for in the following files:

- `commands/`: `structure-review.md`, `review.md`, `reader-panel.md`,
  `evaluate.md`, `brief.md`, `revise.md`, `gen-outline.md`, `draft.md`,
  `draft-pass.md`, `voice-discovery.md`, `gen-characters.md`,
  `run-pipeline.md`, `story-map.md`, `appendix.md`;
- the seed template, `src/autonovel/templates/book/seed.txt`;
- the craft documents in `src/autonovel/templates/series/shared/craft/`
  (`CRAFT.md`, `PROSE.md`, `ANTI-PATTERNS.md`).

`commands/developmental-edit.md` and the `prolepsis` scanner were
uncommitted work in progress on that date. They are counted, marked
*(wip)*. Line numbers refer to the files as read that day.

**Status:**
- **covered**: a command asks the question and acts on the answer;
- **partly**: it is asked in part, only at chapter level, only after
  drafting, or only as an impression;
- **missing**: nowhere.

**Carry** says whether the pipeline's shape can hold the item at all:
- **yes**: an existing command can do it with a rubric change;
- **outline**: only if the outline or a design document records it,
  because drafters never see the whole book;
- **new stage**: it needs a stage the pipeline lacks (design before the
  outline, or re-outline and redraft after review);
- **author**: it needs the author's decision.

## §22 Coverage

| ID | Status | Where (or absence) | Carry |
|---|---|---|---|
| Process: cold read | partly | (wip) `developmental-edit.md` 74–77 reads cold. `structure-review.md` step 4 (175–183) reads seed and outline *before* the prose (step 5). `reader-panel.md` 50–61 and `evaluate.md` 453–461 give judges the outline beats first. | yes |
| Process: one reader reads it all | partly | (wip) `developmental-edit.md` 67–73. `structure-review.md` 200–206 allows fan-out per act. `reader-panel.md` 58–61 falls back to 500-character openings and closings plus summaries. | yes |
| Process: scene map from the page | partly | `structure-dossier`, the summaries and `story-map` exist, but they are written by the drafter, at chapter grain, with no value or polarity column. | yes |
| Process: the letter | partly | (wip) `developmental-edit.md` 194–225 has the professional form. `review.md` 67–84 is one combined prompt, prose-weighted. | yes |
| Process: self-preference (§5) | missing | Every judge is the drafter's model family, and the four "personas" are one model (`reader-panel.md` 63–77). There is no cross-family judge and no calibration against published books, except `evaluate` 9+ needing "a specific published work it competes with" (802–803). | yes |
| P1 one sentence | partly | Seed §1 asks for a pitch (template 17–28); nothing tests it. `reader-panel` `book_in_one_sentence` (91–93) asks only after drafting. | new stage |
| P2 dramatic question | covered at outline, partly after | `gen-outline` spine `question:`/`posed_in:` (80–91). `evaluate --phase foundation` `causal_spine` (110–128). `structure-review` through-line (208–227), which rejects accumulation questions (223–227). Nothing asks whether a historically known answer is in doubt. | outline |
| P3 one action vs a life | partly | `structure-review` `chronicle-spine` (127–129) and step 9 (261–269); `gen-outline` historical paragraph (141–146). Nothing asks before outlining whether the seed's span should be one action. | new stage, author |
| P4 controlling idea | missing | Theme appears only as "not a beat" or "not a cause" (`gen-outline` 27, 115; `structure-review` 74). `theme_coherence` has weight 4/100 (`evaluate` 491). | outline |
| P5 genre promise | missing | Genre is read from `project.yaml` only. The panel's Genre Reader (68–70) is an impression. CRAFT.md §1 Sanderson's promises (67–86) are unchecked. | outline |
| S1 causation | covered | CRAFT.md §1 (99–148). `gen-outline` causal spine (125–139). `draft` 3a (79–100). `draft-pass` spine check (257–266). `structure-review` causal chain (229–244). `evaluate --full` `causal_chain`. | yes, but only what the outline carries |
| S2 removability | covered | `structure-review` step 10 (271–287); `evaluate --full` `removability`; the panel's `chapter_to_cut` (99–103). | yes |
| S3 escalation | covered at act level | Ladder: `gen-outline` 93–105; `structure-review` 246–259, with `reset-ladder` (132–134). No per-scene intensity ("power of 10") and no point-of-no-return check. | yes |
| S4 one desire line | partly | Spine `want:` (`gen-outline` 87). Reset is caught only through the ladder. | outline |
| S5 midpoint | partly | `gen-outline` beats ask for "a midpoint reversal" (118); CRAFT.md tables (20–51, 195–214). Nothing checks the drafted midpoint, or whether it pairs plot with inner revelation. | yes |
| S6 momentum | partly | `evaluate --full` tension-drop alarm (752–766); panel `momentum_loss` and `pulled_vs_informed` (104–107). The tension number is the model's own impression. | yes |
| S7 proportion; main events as scenes | partly | Chapter level: PROSE.md §5 rule 9 (298–304); ANTI-PATTERNS §12; `brief` structural findings (175–189). No book-level words-to-importance check. | yes |
| S8 span and time | partly | The dossier lists gaps of a year or more (`structure-review` 168–169). Nothing judges whether the span fits, and no command offers to compress it. | new stage, author |
| S9 order of telling | missing | `reorder` is mechanics. No command considers starting late, a frame, or non-chronological order. | author |
| SC1 value turn | partly | PROSE.md §5 rule 5, McKee's two charges (281–283). `evaluate` `beat_coverage` checks the goal, conflict, disaster and consequence beats (605–659), but names no value and tracks no polarity across the book. | yes |
| SC2 crisis | missing | No dilemma or best-bad-choice test anywhere. | yes |
| SC3 scene–sequel chain | partly | Described in PROSE.md §5 (209–213); not checked. | yes |
| SC4 the gap | partly | PROSE.md §5 rule 4 (No / Yes-but). | yes |
| SC5 micro-tension | missing | Maass is not cited. | yes |
| SC6 turn on the page | covered at chapter level | PROSE.md §5 rule 9; `brief` 175–189. | yes |
| C1 want and agency | partly | Seed POV want (31–43); `gen-characters` want/refuse (45–48); spine `want:`. Nothing checks acting against reacting; CRAFT.md sliders (154–170) are unchecked. (wip) `developmental-edit` notes record it (158–160). | yes |
| C2 misbelief attacked by plot | missing in practice | CRAFT.md §2 teaches Ghost/Wound/Lie/Want/Need (171–214), but no command records or checks a Lie (no command mentions misbelief, lie, wound or ghost). `gen-characters` gives only a "private contradiction" (47) and forbids arcs in its file (58–59). `arc_completion` has weight 7/100 (483). | outline |
| C3 climax choice, want vs need | missing | `structure-review` convergence counts plot threads, not the inner choice. | outline |
| C4 vivid protagonist | partly | Panel `thinnest_character` only. | yes |
| C5 personal and public stakes | partly | Ladder "stake"; no personal/public distinction. | outline |
| C6 web of characters; merges | missing | voice-discovery Part 4 covers speech only (94–121). | outline |
| A1 antagonism at full strength | partly | `structure-review` `missing-antagonist` (138–139) flags absence only; nothing tests strength or levels. | outline |
| A2 same prize, persisting | partly | `gen-outline` `opposing_force:` "persists" (88–90); the `thread-the-antagonist` candidate (334). (wip) `developmental-edit` opposition notes and appearance counts (156–157, 179–180). No antagonist entry is required in `characters.md`. | outline |
| A3 the opponent's plan | missing | — | outline |
| V1 whose story; viewpoint | missing at book level | `voice-discovery` records POV distance (85); `pov-bleed` is line-level. Nothing asks the Lukács question for a world-historical protagonist. | author |
| V2 reader knowledge vs character | missing | No suspense/surprise design anywhere. | outline |
| V3 no hindsight | **decided 2026-10-18** | PROSE.md §7.3 *licensed* one narrator "promise line" a chapter. Decided for Stone and Mantel: §7.3 now rules out narrator forecasts by default (one exception: a declared retrospective narrator, a handful a book, only to sharpen the central question); `autonovel mechanical prolepsis` counts the candidates. | yes (done) |
| V4 backstory placement | partly | CRAFT.md info-dump rule (286–291); PROSE.md §7. No whole-book check. | yes |
| T1 embodied theme | missing | — | yes |
| T2 worth doing | missing | `review.md`'s critic stage is free-form (67–70); no aim test (Updike rule 1). | yes |
| G1 obligatory scenes | missing | — | outline |
| G2 form fits premise | missing | — | author |
| R1 question at each chapter end | partly | PROSE.md §5 rule 7 (286–289) and §8, per chapter. (wip) `developmental-edit` "What I want to know now" (151–152). `story-map` `threads.md` records a `question:` per thread (96–122), but only after drafting. | outline |
| R2 suspense/curiosity/surprise | missing | `threads.md` records plant and payoff, not which interest is working or whether lines resolve. | outline |
| R3 wanted, improbable outcome | missing | — | outline |
| R4 shape of fortune | partly | Tension curve and dashboard; no rise/fall shape test. | yes |
| R5 ending recasts the beginning | partly | CRAFT.md Save the Cat mirror image (49–51); unchecked. | yes |
| O1 starts at the point of change | partly | `hook_strength` covers chapter 1's first 250 words (680–688); a chapter-1 call-to-action cap (441–444). No "where does the story start" test across the opening chapters. | yes |
| O2 first-page question | partly | `hook_strength`. | yes |
| E1 climax by the protagonist's choice | partly | `structure-review`: answered "by the climax's decision" (210–216); "History is not causation" (76–80). No rescue or deus-ex-machina test. | yes |
| E2 convergence | covered | `structure-review` step 11 (289–297); `evaluate --full` `climax_convergence`. | yes |
| E3 reversal with recognition | missing | — | outline |
| E4 false ending | missing | — | outline |
| E5 ending trusts the reader | partly | PROSE.md §8; CRAFT.md §7. | yes |
| H1 the invented therefore | covered | `structure-review` step 9; `gen-outline` 141–146; CRAFT.md 142–146. | outline |
| H2 invention in the gaps | partly | PROSE.md §7 (Harris, Mantel). | yes |
| H3 known-outcome suspense | missing | — | outline |
| H4 span and campaigns | missing | — | new stage, author |
| H5 research in service | partly | PROSE.md §7; `brief` enrichment "a brush, not a chisel" (112–122). | yes |
| H6 not a monument | missing | — | author |
| H7 living forward | decided 2026-10-18 | As V3. | yes (done) |
| H8 author's note | covered | `appendix` "Notes on what's invented" (37, 200). | yes |
| TH1–TH7 thriller contract | missing (TH2 partly) | `clocks_paid` tracks chapter clocks (`evaluate` 130–146, 505–515). There is no book clock, no villain's MacGuffin, no hero-at-the-mercy scene, no false ending. | outline |

**Counts.** Of the 58 question-level items above (P, S, SC, C, A, V, T,
G, R, O, E, H; thriller counted as one), 6 are covered, 27 partly, 23
missing and 2 in conflict (both decided 2026-10-18: see V3/H7).
- **Covered:** S1, S2, E2, H1, H8, and SC6 at chapter level.
- **Missing:** most of character, antagonism, genre, reader experience
  and the historical items.

The pipeline's book-level strength is plot causation. It was added
on 2026-10-16/17 and is well built. Almost everything else a
developmental editor asks about the *people* and the *reader* is absent.

## §23 Can the architecture carry it?

1. **The book's shape is decided once, early, by the mid-tier model,
   from a seed nobody tested.**
   - `gen-outline` is `model_tier: standard` (line 5).
   - The seed template asks for a pitch, a want, a fear and obstacles,
     but never for a dramatic question, an antagonist's plan, a
     misbelief, a span decision or a genre contract.
   - The foundation gate is `foundation_score > 7.5 AND lore_score >
     7.0` (`run-pipeline.md` 29–33), with lore weighted 40% and
     structure 20% (`evaluate.md` 144–146). The worldbuilding is gated;
     the premise is not.
   
   Literature: Coyne's Foolscap comes before the draft, and an unfilled
   field means "you didn't make the choice necessary". Cron works out
   want and misbelief before plotting. Kushner and Sorkin chose their
   points of friction before writing.
2. **Drafters never see the book.** Each chapter is drafted from the
   outline, the prior summaries and the last 1,000 words (`draft.md`
   134–166), in a fresh subagent (`draft-pass.md` 177–198). Anything
   long-range has to be in the outline, or it will not be written:
   - the antagonist's plan and his appearances;
   - the misbelief beats;
   - the reader-question ledger;
   - the obligatory scenes;
   - the known-outcome obstacles.
   
   Today the outline carries only the plot spine.
3. **Revision is chapter-local.** `revise` must "never touch another
   chapter" (165–171). Cross-chapter moves are merges, cuts and
   reorders the author runs. There is no path from a whole-book
   diagnosis to a new outline and a redraft, which is the professional
   remedy:
   - Hohoff's reconception of Lee's book;
   - Gottlieb's "rewrite it from beginning to end";
   - Matt Bell's "Retype everything. Yes, everything."
   
   A persistent antagonist or an inner arc cannot be added by 24
   in-chapter patches. `docs/reviewer-audit.md` root cause 6 shows a
   structural patch making the book worse. The only redraft path is a
   `context: isolated` rewrite book, which nothing routes the author to.
4. **The judges are the writer's model family, and three of the four
   whole-book judges read the plan first.** Self-preference (Panickssery
   et al.), the lack of correlation with experts (Chakrabarty et al.) and
   the absence of turning points in model stories (Tian et al.) all point
   the same way: the pipeline's scores flatter the pipeline's prose.
   - `structure-review` defends itself well: it counts, quotes evidence,
     caps the score and reads the other reviewers last.
   - It still reads the outline before the manuscript.
   - (wip) `developmental-edit` fixes the order but not the family bias.
5. **The index is written by the drafter.** Every whole-book instrument
   leans on the drafter's own summaries. `structure-review` says so
   (ground rule 7, 91–94); the others do not.
6. **Rules that pull the other way.**
   - Chapter-local closure rewards self-contained chapters
     (`reviewer-audit.md` root cause 2).
   - PROSE.md §7.3 still licenses narrator forecasts, against V3 and H7.
   
   Both need an explicit decision, not just a new rule beside them.

## §24 Ranked gaps, by expected effect on the finished book

Book-level gaps first. Each names the professional practice it lacks.

> **Update 2026-10-18.** Gaps 1–6 are now addressed by
> `/autonovel:design` (`books/{book}/design.md`, built from the study
> text `shared/craft/DESIGN.md`): the climax and question designed first,
> the protagonist's misbelief attacked per act, one rival with a dated
> plan on stage every act, reader questions per act boundary and the
> known-outcome problem (§4 there), the genre's obligatory scenes, and
> the re-design loop (`--from-book`, routed to by
> `/autonovel:developmental-edit` when its diagnosis is design-level).
> `gen-outline` (now heavy) and `draft` are bound to it, `evaluate
> --phase foundation` scores it, and `autonovel mechanical
> design-validate` checks its shape. Gap 7 is partly addressed (a cold
> reader of the design, D14). Gaps 8–9 stand.

1. **No premise-and-design stage before the outline** (P1–P5, H4, V1,
   S8). The practice it lacks: Coyne's Foolscap, Bransford and Reid's
   pitch tests, Stone's "Not every life will fit", Kushner's four months.
   A fifty-year life goes in, and a fifty-year chronicle comes out,
   unless something stops it before the outline.
2. **No protagonist misbelief, designed and attacked** (C2, C3). The
   practice: Cron's misbelief and third rail; Weiland's Lie mapped to
   the beats; Truby's weakness and need. CRAFT.md teaches it and no
   command uses it. Without it, external events have nothing to do to
   the protagonist, and chapters become episodes of the same man
   winning.
3. **No designed antagonist** (A1–A3, TH1, TH3–TH5). The practice:
   McKee's Principle of Antagonism; Truby's opponent who competes for
   the same goal; Follett's Hamleigh and Waleran; Story Grid's MacGuffin
   and "making it personal". The pipeline has one `opposing_force:` line
   and a failure flag for its absence.
4. **No re-outline-and-redraft loop** (§23.3). The practice: Hohoff's
   reconception, Gottlieb's full rewrite, Matt Bell's retype, Perkins's
   "reorganization". Book-level faults found after drafting are patched
   per chapter, and patches can worsen the book.
5. **No design of the reader's experience** (P2's "in doubt", R1–R3, V2,
   H3). The practice: Child's question and delay; Hitchcock's bomb;
   Brewer and Lichtenstein's three interests; Gerrig and Forsyth on
   known outcomes. A historical thriller lives or dies here.
   `threads.md` comes closest, but is written after drafting and the
   drafter never reads it.
6. **No genre contract** (P5, G1, thriller conventions). The practice:
   Coyne's conventions and obligatory scenes. The book is pitched as a
   thriller, and no instrument asks for a thriller's scenes.
7. **Uncalibrated self-judgement, plan read first** (§5, §23.4). The
   practice: the cold reader's read (Martin, Gottlieb), Updike's
   aim-then-evidence, and comparison with a successful model. The
   mitigations are to read cold, count, ask the author questions he can
   answer without craft vocabulary ("after chapter N, what did you want
   to know?"), judge with a different model family, and compare against
   named published books.
8. **No scene-level map across the book** (SC1, SC2, S6). The practice:
   Coyne's spreadsheet with value and polarity; the crisis as a
   best-bad choice. Without it, runs of the same charge and crises with
   no cost are invisible.
9. **Openings and endings only partly covered** (O1 across the opening
   chapters; E1 rescue or history; E3; E4; C3). The practice: Fitzgerald
   to Hemingway, Monteith, Aristotle's reversal with recognition, the
   false ending.
10. **No argument and no critic's aim test** (P4, T1, T2). The practice:
    McKee's controlling idea, Truby's moral argument, Updike's rules,
    Stone's "cement". `review.md`'s critic stage is an unstructured
    newspaper review.
11. **The hindsight conflict** (V3, H7). *Decided 2026-10-18:* PROSE.md
    §7.3 now follows Stone and Mantel (the story is lived forward; no
    narrator forecasts by default). The 2026-10-15 promise-line rule it
    replaces was the main cause of the kingmaker "anecdotes" read.
12. **Proportion and span are measured, never judged** (S7, S8).

**The first change.** Add a heavy-tier design stage between
`gen-characters` and `gen-outline`, and bind the outline to it. It could
be a new `/autonovel:design --book` command or a mandatory first step of
`gen-outline`. It writes `books/{book}/design.md`:

- the one-sentence pitch and dramatic question, with how the answer
  stays in doubt (P1, P2, H3);
- the single action and the span, with what is cut or folded in (P3,
  S8, H4);
- the controlling idea (P4);
- the genre with its conventions and obligatory scenes, each assigned an
  act (P5, G1);
- the viewpoint decision, including the world-historical-protagonist
  question (V1, H6);
- the protagonist's Lie, Want, Need and origin, and the beat where each
  act attacks the Lie (C2, C3);
- the antagonist: what he wants, why he needs the protagonist, his plan
  in steps with dates, and the act-by-act ledger of his appearances (A1–A3,
  TH1);
- a reader-question ledger: what the reader knows and wants to know at
  each act boundary (R1–R3, V2).

`evaluate --phase foundation` should then gate on this design instead of
on lore, and `gen-outline` should run on the heavy tier.

Why this first:
- Every hole the author has found so far traces to a decision the
  outline made by default.
- Drafters can only execute what the outline carries.
- The literature puts these decisions before the draft.
- Fixing a story at design costs minutes; fixing it in 108,000 words of
  prose costs a structural revision that the chapter-local architecture
  cannot fully perform.

The second change is the loop in gap 4. A `developmental-edit` letter
whose problems are design-level should route to a revised `design.md`
and outline, and to a redraft, rather than to in-chapter briefs.

---
