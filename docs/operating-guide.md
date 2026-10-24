# Operating guide

Day-to-day operation of autonovel: where human input matters and why,
how long each stage takes, concrete workflows for common tasks
(first-pass draft, minor revision, factual fix, major restructure,
adding a plot point), and the boring-but-essential mechanics
(updating tools, recovering from a crash, starting a new book or
series).

This is the doc to read **after** you've finished the install
walkthrough in [`README.md`](../README.md) and **before** you start
your second novel.

---

## 0. How the editing commands relate

The single most-asked question after a first-pass draft. **Read
this section first if you're confused about which of `draft`,
`draft-pass`, `revise`, `revision-pass`, `brief`, `evaluate`,
`review`, `structure-review`, or `reader-panel` to run when.** Everything else in this
doc assumes you've internalised this layout.

### The four roles

Every editing command falls into one of four roles:

| Role | What it does | Scope | Modifies prose? |
|---|---|---|---|
| **Atomic** | Operate on ONE chapter at a time. | 1 chapter | Some yes, some no |
| **Sweep** | Loop the atomic commands across MANY chapters in one shot. | N chapters | Yes (delegates to atomic) |
| **Whole-book reviewer** | Read the whole book and write a REPORT. Never modifies prose. | Whole book | **No** |
| **Mechanical helper** | Deterministic regex / scanner / file-mover. Feeds evidence into other commands. | Varies | Sometimes |

### The commands by role

| Command | Role | One-line summary |
|---|---|---|
| `/autonovel:draft N` | Atomic | Write chapter N from outline + voice + canon. |
| `/autonovel:evaluate --chapter N` | Atomic | Score chapter N. Writes `eval_logs/chNN_eval.json`. |
| `/autonovel:brief N` | Atomic | Synthesise a per-chapter revision plan from whatever evidence is on disk (eval, cuts, panel, review). Writes `briefs/chNN.md`. **Does NOT rewrite prose** — just plans. |
| `/autonovel:revise N` | Atomic | Rewrite chapter N **per the brief at `briefs/chNN.md`**. Refuses if the brief is missing. |
| `/autonovel:adversarial-edit N` | Atomic helper | Find 10–20 cut/rewrite candidates in chapter N. Writes `edit_logs/chNN_cuts.json`. |
| `/autonovel:apply-cuts N` | Atomic helper | Deterministically remove flagged passages (no LLM). |
| `/autonovel:check-anachronism N` | Atomic helper | Period-vocabulary + LLM semantic anachronism scan. Writes `edit_logs/chNN_anachronism.md`. |
| `/autonovel:draft-pass` | Sweep | "Write the rest of the book." Per chapter: draft (with its cold first reader) → anachronism → evaluate → if low, brief + revise + re-eval → promote-canon. With `--deep`: also runs reader-panel + review at end. |
| `/autonovel:revision-pass` | Sweep | "Improve these chapters." Per chapter: anachronism → brief → revise → evaluate → promote-canon. |
| `/autonovel:reader-panel` | Whole-book reviewer | Four-persona panel (Editor / Genre Reader / Writer / First Reader). Writes `edit_logs/reader_panel.json`. **Does NOT modify chapters.** |
| `/autonovel:review` | Whole-book reviewer | Opus dual-persona deep review (literary critic + professor of fiction). Writes `edit_logs/review.md` + `review.json`. Its stop-revising verdict is gated on `structure-review`. **Does NOT modify chapters.** |
| `/autonovel:structure-review` | Whole-book reviewer | The book-level structure judge: is it one story building to a climax, or a string of episodes? Through-line, chapter N → N+1 causal chain, stakes ladder per act, removability per chapter, climax build, a 1–5 structure score separate from prose, and 3–7 structural brief candidates. Writes `edit_logs/structure_review.json` + `.md`. **Does NOT modify chapters.** See [§2g](#2g-when-to-stop-revising-the-book-level-gate). |
| `/autonovel:design` | Foundation (heavy) | The book-level decisions before the outline, worked back from the climax: the question and when it is posed, the one action and span, one rival with a dated plan, the skills the climax spends (each planted inside its own contest, tested, paid), rehearsals, the cast web, sequences, clocks, places, voice → `books/<book>/design.md`. Tested against `shared/craft/DESIGN.md`, read cold by a second reader, checked by `design-validate`. `--from-book <drafted-book>` re-designs a drafted book as a new isolated one (keeps facts and art, never its prose). **Does NOT write chapters or the outline.** |
| `/autonovel:cast` | Foundation (heavy) | The character dossiers → `books/<book>/cast.md`: for each principal want, fear, the contradiction shown in an act, what they put first when forced to choose, secret, private life, how they see a room, their history with each other person, the choices that test them chapter by chapter, what each chapter shows of them, a private monologue (for the writer only) and a return tag; a short entry with a return tag for every ensemble player. Real people built from the research record. Tested against `shared/craft/CHARACTER.md` C1–C12 and read cold. `draft`, `revise`, `gen-outline` and `evaluate` read it. **Does NOT write chapters.** |
| `/autonovel:first-read` | Chapter reader (heavy) | A cold first reader who knows nothing about the subject and sees only the book so far: every word or name it didn't know, every sentence it had to read twice, where it got lost or crowded, anyone it had forgotten when they came back, places it couldn't picture, who felt like a real person and who like a type, where it skimmed, and whether it would turn the page → `edit_logs/first_read_chNN.md`. `draft` runs it on every new chapter and fixes what it finds. **Does NOT modify chapters.** |
| `/autonovel:developmental-edit` | Whole-book editor | A developmental editor's full read: one reader, every chapter in order, cold, with notes per chapter and counted evidence, then a ranked letter on the story (`edit_logs/editor_letter.md`) and where it disagrees with the scoring reviewers. `--stage` queues its in-chapter fixes in `briefs/conversation.md`. **Does NOT modify chapters.** |
| `/autonovel:chapter-summary` | Mechanical helper | One-line-per-chapter overview table — Date / POV / Score / Words / Cast / Plot (with location prefix). Pure mechanical, no LLM. The right tool for "which chapters happen in <date range>?" or "where does <character> appear?" before a revision pass. **Does NOT modify chapters.** |
| `/autonovel:motifs` | Mechanical helper | Per-chapter motif density tracker. Reads `books/{book}/motifs.md` (one bullet per motif: `- slug: keyword1, keyword2`). Flags motifs that drop to zero in the back half of a book they were established in earlier — catches "set up an image, never paid it off". Pure mechanical. **Does NOT modify chapters.** |
| `/autonovel:talk` | Conversational layer | Ask the book questions or queue edits in natural language. Three modes: **Q+A** (cites chapter+line, no edit), **Suggest-and-stage** (queues an edit in `briefs/conversation.md`), **Mechanical+suggest** (runs `entity-track` first, then queues a structured cut-list). Queued turns get folded into the brief by the next `/autonovel:revise <N>`. |
| `/autonovel:dashboard` | Mechanical helper | Per-book at-a-glance dashboard — re-renders the latest eval logs + mechanical augmentations (cast size, scene count, dialogue density, motif density), each chapter's lowest dimension beside its score, the book's ten lowest scores, cold-reader items, score and tension sparklines, per-book aggregates, and tension-drop alarms; `--dimensions` for every dimension of every chapter. Re-runs without firing an LLM evaluate pass. **Does NOT modify chapters.** |
| `/autonovel:story-map` | Reading surface | One HTML page to *see* the book's shape without re-reading it — synopsis in reading order under the outline's act headers, plot threads × chapters (plant / turn / payoff) with the score / tension curve directly under the grid, characters on stage per chapter with their state changes, story-time axis with gaps labelled, places. Writes `edit_logs/story_map.html` (+ `.json`) and, on first run or `--refresh-threads`, the hand-editable thread ledger `threads.md` (LLM, from the outline + summaries — never the prose). Data, not verdicts. **Does NOT modify chapters.** |
| `/autonovel:summaries` | Mechanical helper | Filter the chapter-summary index by a small DSL — `pov == "Lucia"`, `cast contains Niccolò`, `story_time >= "1521-11"`, `chapter in 5..12`, `score < 7.0 and word_count > 3000`. Pure mechanical, no LLM, free, scriptable. The right tool when you know exactly which chapters you want; `/autonovel:talk` is the LLM-mediated path for fuzzy questions. **Does NOT modify chapters.** |
| `/autonovel:dialogue` | Mechanical helper | Per-chapter dialogue-mechanics linter — adverb-heavy speech tags, said-bookisms, repeated speech-verb stutters. Fast pre-flight before a heavy-tier evaluate run. **Does NOT modify chapters.** |
| `/autonovel:period-register` | Mechanical helper | Per-book roll-up of every period-bans hit across every chapter, with worst-offenders ranking. **Does NOT modify chapters.** |
| `/autonovel:syntax-drift` | Mechanical helper | Per-chapter Flesch-Kincaid grade vs the voice file's declared `FK grade band: L–H` (then seed.txt; the voice file's own prose only as a weak last resort). Catches modern syntax in period-correct vocabulary and the reverse. Pure math; review list, not a gate. For the fuller register picture (narration and dialogue separately, contraction ratio, utterance length, lines that explain to the listener) `autonovel mechanical register <book>` is the scanner `/autonovel:evaluate` scores as `register`. **Does NOT modify chapters.** |
| `/autonovel:pov-bleed` | Mechanical helper | Heuristic POV-bleed scan — flag interiority verbs / nouns attached to non-POV characters. Suggestion list, not a gate (false positives are common). **Does NOT modify chapters.** |
| `/autonovel:import-book` | Setup | Import an externally-written manuscript. Splits a directory of `*.md` files or a single combined manuscript into autonovel-shape `ch_NN.md` files; flips `project.yaml :: books[].mode` to `edit-imported` so `/autonovel:draft` refuses to overwrite. The rest of the pipeline (evaluate / brief / revise / panel / review / typeset) treats imported chapters identically to drafted ones. |
| `/autonovel:series-arc` | Mechanical helper | Cross-book scoreboard for series with ≥2 books — per-book completion, cross-book cast, story-time discipline, unresolved threads, composite arc score. Pure mechanical, no LLM call. **Does NOT modify chapters.** |
| `/autonovel:show-dont-tell` | Mechanical helper | Per-chapter pre-flight scanner for tell-candidate lines (emotion-state, interiority verbs, perception filters, narrator labels). Wider net than the existing slop regex; surfaces line-level review targets. **Does NOT modify chapters.** |
| `/autonovel:diff` | Mechanical helper | What changed between two versions of the book (a tag, your `last-read` bookmark, a checkpoint, the working tree) as one HTML page: word-level edits inside their paragraphs, next/prev stepping, Changes / Whole chapter / Clean text views, a big-changes filter, word deltas per chapter, and a link to the story map (synopsis, threads, characters, timeline, places), which it rebuilds beside it. The check after a `revise` / `revision-pass` that the brief's asks actually landed — and those commands hand a chapter you have already read back as this page themselves. Zero-LLM unless `--annotate` (a plain *what* note, a *why* and a big flag per change). **Does NOT modify chapters.** |

### The crucial insight: `brief` is the synthesiser

`brief` is the bridge between **evidence on disk** (eval logs,
cuts, anachronism reports, reader-panel findings, review findings,
custom-rubric flags from `voice.md` Part 3) and **a plan the
rewrite can act on**. It reads everything available, picks the
load-bearing items, and writes one focused per-chapter `briefs/chNN.md`.

`revise` then reads `briefs/chNN.md` and rewrites the chapter to
match. **`revise` won't run without a brief** — that's deliberate;
it's the reason rewrites stay targeted instead of drifting.

You almost never call `brief` and `revise` directly. You call a
sweep that calls them for you.

### Who calls whom (the automation graph)

```
                ┌───────────────────────────────────────────────────┐
                │  draft-pass (sweep over N chapters, default sequential)
                │      ├─ per chapter:
                │      │    draft → anachronism → evaluate
                │      │    if score < threshold:
                │      │        brief + revise + re-eval (keep best)
                │      │    promote-canon (per chapter)
                │      └─ with --deep:
                │            reader-panel + review on whole book at END
                └───────────────────────────────────────────────────┘

                ┌───────────────────────────────────────────────────┐
                │  revision-pass (sweep over N chapters)
                │      └─ per chapter:
                │            anachronism → brief → revise → evaluate
                │            promote-canon (per chapter)
                └───────────────────────────────────────────────────┘

                ┌───────────────────────────────────────────────────┐
                │  structure-review (whole book → REPORT + structural
                │                    brief candidates, no rewrites)
                │  reader-panel  (whole book → REPORT, no rewrites)
                │  review        (whole book → REPORT, no rewrites;
                │                 stop verdict gated on structure-review)
                └───────────────────────────────────────────────────┘
                        │
                        │  reports land in edit_logs/
                        ▼
                 You then run revision-pass
                 (which calls brief → revise → evaluate per chapter,
                  with brief picking up the structure candidates +
                  panel + review evidence along with the existing
                  eval + cuts; `--chapters structural` targets exactly
                  the chapters the structure review named).
```

### "I ran draft-pass --all, then review, then reader-panel — did I need to run brief?"

**Short answer: no, but you're not done.**

`draft-pass` already ran `brief` + `revise` for any chapter whose
draft scored below threshold. Every chapter ended at a score above
threshold (or marked low, with a recorded brief) by the time the
sweep finished.

`review` and `reader-panel` then produced **reports**. They wrote
findings to `edit_logs/reader_panel.json` and
`edit_logs/review.md` (+ `review.json`). **They did not touch any chapter.**

To act on those reports — to actually rewrite the chapters they
flagged — your next move is:

```text
/autonovel:revision-pass --chapters <flagged>
```

Pass the chapter list the panel + review surfaced (the `--deep`
postamble names them). `revision-pass` walks each one and calls
`brief` (which now sees the new panel + review evidence on disk
and folds it in), then `revise` (which rewrites against the
brief), then `evaluate` (re-scores). One sweep — no manual
`brief` calls needed.

If you want surgical control over a single chapter (you read the
panel report and disagree with most of it but agree on chapter
12), use the per-chapter atomic flow:

```text
/autonovel:brief 12 --from auto      # write the brief; hand-edit briefs/ch12.md if needed
/autonovel:revise 12                 # rewrite per the brief
/autonovel:evaluate --chapter 12     # re-score
```

### The minimal end-to-end flow on a fresh book

```text
# Foundation (run /autonovel:next; do each step it suggests)
/autonovel:gen-world
/autonovel:gen-characters
/autonovel:voice-discovery --book <book>
/autonovel:gen-canon                       # series-wide facts → shared/canon.md
/autonovel:design --book <book>            # climax, question, rival, plants, sequences → design.md
/autonovel:cast --book <book>              # character dossiers → cast.md
/autonovel:gen-outline --book <book>
/autonovel:gen-canon --book <book>         # this book's outline facts → books/<book>/canon.md
/autonovel:evaluate --phase foundation --book <book>

# First-pass draft (one command, walks away)
/autonovel:draft-pass --chapters 1-19 --deep    # --deep adds structure-review + review + reader-panel at end

# Act on the deep-pass reports — structure first
#   (run any merge / cut / reorder it lists yourself, then re-run structure-review)
/autonovel:revision-pass --chapters structural
/autonovel:revision-pass --chapters <flagged-from-deep-pass>

# (Repeat until the structure gate passes and the reports are clean — §2g.)

# Set the title, write the front matter, typeset
/autonovel:title --book <book>           # propose / pick / set title + author
/autonovel:introduction --book <book> --from both   # preface (you write) + intro (AI drafts)
/autonovel:typeset --book <book>         # PDF + ePub
```

That's the whole story. `draft` and `revise` and `brief` and
`evaluate` exist for surgical work; `draft-pass` and
`revision-pass` exist because you almost always want the loop, not
the atoms.

---

## 1. Where human input matters, and how much

**Lost? Run `/autonovel:help`.** Zero-arg shows a category-
grouped overview of every command. `/autonovel:help <topic>`
walks one workflow with the exact command sequence —
`/autonovel:help art` is the right place to start if the 10
art-* / cover-* commands feel opaque. Topics: art, foundation,
drafting, revising, structure, typeset, research, front-matter,
sweeps, tui, cli, next-steps.

**Quick start: run the onboarding wizard.** Before reading the
rest of this section:

```bash
autonovel new-series my-novel
cd my-novel
autonovel new-book book-one
autonovel onboard book-one
```

`autonovel onboard` walks you through the load-bearing inputs in
prompt-driven order — pitch, period, genre, working title, human
author, attribution style. Every prompt has a `(skip)` option
that lands a `## Onboarding TODO` block in `seed.txt` for
`/autonovel:next` to surface later. Output: a structured
`seed.txt` and a populated `project.yaml :: books[<book>]` ready
for foundation. Then open Claude Code in the series root and run
`/autonovel:next` to walk through the rest. Skip the wizard and
hand-edit if you prefer; the file shapes are documented below.

---

The pipeline is autonomous in execution but you decide the shape.
Per stage, the minimum-viable input + the recommended-for-quality
input + how long each takes:

| Stage | Minimum input | Recommended input | Your time | Computer time |
|---|---|---|---|---|
| **Seed** (`books/<book>/seed.txt`) | 1 paragraph: pitch + POV + obstacle + change | 6-section guided template (pitch, POV, obstacles, change, period/place, notes) | 5 min minimum, **20–30 min recommended** | – |
| **Foundation review** (world, characters, canon, outline) | Read the produced files; rerun if a stage looks wrong | Skim each generated file; check canon dates and event ledger; rerun the offending stage | 10 min minimum, **30–60 min recommended** | 1–3 min per `gen-*` cycle |
| **Voice discovery** | Accept the AI's pick | Read all 5 trial passages; pick one; optionally rerun for fresh trials | 2 min minimum, **5–10 min recommended** | 2–4 min per run |
| **Per-chapter draft review** | Skim eval score; let pipeline advance if ≥ threshold | Read the chapter; if it surprised you (good or bad) note why | 1 min minimum, **3–5 min recommended** | 2–5 min per chapter draft (Sonnet) |
| **Reader-panel feedback** | Run it; read the headline | Read each persona's full report; mark which complaints you agree with before running revise | 5 min minimum, **15–30 min recommended** | 5–10 min for whole book |
| **Structure review** | Run it once the book is drafted; read the verdict and the removable chapters | Read the causal-chain table and the candidates; decide the merges / cuts it proposes yourself; re-run after each structural pass until the gate passes (§2g) | 10 min minimum, **20–40 min** per round | 10–20 min per pass on whole book |
| **Opus review** | Run it once near the end | Iterate review → revise loops until the items become hedged ("perhaps could do") **and** the structure gate passes | 5 min minimum, **15–60 min** per round | 5–15 min per pass on whole book |
| **Major decisions** (cut a chapter, add a character, change ending) | Decide; type the sidequest | Decide deliberately; consider impact on canon, outline, downstream chapters | 5–60 min depending on scope | 2–10 min for the sidequest itself |
| **Export** (PDF, ePub, audiobook, cover) | `/autonovel:package` and walk away | Inspect the typeset PDF for orphan/widow lines; tweak `typeset/novel.tex` | 5 min minimum, **30 min recommended** | 30–60 sec PDF; 5–60 min audiobook depending on length |

**Total for a 70k-word novel:** the computer does roughly 4–8 hours
of paid work spread across the run; you spend roughly 4–8 hours of
attention spread across days. Bells took ~a week of part-time
attention.

The single highest-leverage place to invest your time is **the
seed.** A vague seed → a vague book. A specific seed → the AI fills
in confidently, the eval is meaningful, and revisions stay
targeted.

---

## 2. Workflow patterns with concrete examples

For every example below, assume you're in your series root (the
folder containing `project.yaml`) and have launched `claude` /
`codex` / `gemini` from there.

### 2a. First-pass draft (mostly automated)

You've finished the foundation. The eval scored ≥ 7.5. You want
the whole book drafted unattended.

> If you're unclear how `draft-pass` relates to `draft`, `revise`,
> `brief`, `revision-pass`, `review`, and `reader-panel`, **read
> [§0 first](#0-how-the-editing-commands-relate)** — that section
> is the conceptual map for everything below.

```text
/autonovel:next                        # confirms the next step
/autonovel:draft-pass --chapters 1-19  # walk away — does the full per-chapter loop
                                       # plus the end-of-sweep canon promote
```

For each chapter the sweep runs: **draft → anachronism check →
evaluate → if score < threshold (default 7.0), brief + revise +
re-eval (keeps best) → promote-canon** (so each chapter's
discoveries land in the book's `canon.md` — research-cited facts in
`shared/canon.md` — before the next chapter drafts and reads it). A final `promote-canon` sweep also runs
after the last chapter to catch anything still pending. Disable
either with `--no-promote`.

Add `--deep` and the sweep also runs `structure-review`,
`reader-panel` and `review` on the whole book at the end — produces
reports (does not auto-revise from them) and surfaces a
flagged-chapters list. (Every sweep, deep or not, also runs a
per-chapter spine check against the outline's `## Causal spine`.)

```text
/autonovel:draft-pass --chapters 1-19 --deep   # adds ~10–25 min for the deep passes
```

Realistic time budget on a 19-chapter / 70k-word book:
- Plain `draft-pass`: 2–3 hours unattended.
- `draft-pass --deep`: 2.5–3.5 hours unattended.

Postamble prints a summary table:

```
chapter | draft (words) | anach | eval v1 | eval v2 | final | revised?
--------|---------------|-------|---------|---------|-------|----------
     1  | 3100          | 0     | 7.4     | —       | 7.4   | no
     2  | 2950          | 2     | 6.8     | 7.3     | 7.3   | yes
   …
```

With `--deep`: append a "panel + review flagged chapters X, Y, Z"
block. Your move next is `/autonovel:revision-pass --chapters
X,Y,Z` against the flagged list, or done if nothing was flagged.
**Time you spent watching this happen: zero.** Time skimming the
summary: 5 min.

### 2b. Minor revision (a single chapter feels off)

Chapter 7 came back at 5.8 and reads as flat. You don't want to
revise the whole book — just chapter 7.

```text
/autonovel:adversarial-edit 7          # judge finds 10–20 cuts/rewrites
/autonovel:apply-cuts 7 --types OVER-EXPLAIN REDUNDANT
                                       # mechanical cuts (no LLM)
/autonovel:brief 7 --from auto         # synthesize revision brief
/autonovel:revise 7                    # rewrite per the brief
/autonovel:evaluate --chapter 7        # re-score
```

Time: ~10–15 min of compute, ~5 min reading the brief between
steps to see if you disagree with anything. If you do, edit
`books/<book>/briefs/ch07.md` before running `revise`.

### 2b.1. Late research, woven lightly into existing chapters

You finished a revision pass. Then you realised you wanted deeper
research on a specific topic — Venice politics + trade in the
1479-1500 window when Jakob Fugger was there, say. You don't want
to redraft anything; you want the chapters where Fugger appears
to carry richer period detail, but their plot, dialogue, scene
shapes, and voice should stay exactly as they are.

Three commands, in order:

```text
# 1. Targeted research (writes notes to shared/research/notes/<slug>.md)
/autonovel:research "Venice politics and trade 1479-1500"
```

The notes file lands at
`shared/research/notes/venice-politics-and-trade-1479-1500.md`
with `## Material detail`, `## People and institutions`, and a
`## Sources` block carrying `[shortname]` citations. Read it once;
make sure it actually says what you wanted.

```text
# 2. Identify chapters where the research is relevant.
#    Easiest path: grep your chapter files for the topic's main names.
ls books/<book>/chapters/ch_*.md | xargs grep -l Fugger
# →  books/<book>/chapters/ch_05.md
#    books/<book>/chapters/ch_08.md
#    books/<book>/chapters/ch_12.md
```

Or scan the outline if your chapter files don't quote the names
verbatim yet. Aim for the ≤6 chapters where the research naturally
belongs — forcing it elsewhere just produces tone shifts.

```text
# 3. Sweep those chapters with --enrich-with pointing at the notes.
/autonovel:revision-pass --chapters 5,8,12 \
    --enrich-with shared/research/notes/venice-politics-and-trade-1479-1500.md
```

For each chapter, `revision-pass` runs the standard loop
(anachronism → brief → revise → evaluate → promote-canon). The
`--enrich-with` flag passes through to each chapter's brief. The
brief considers whether the research is relevant to *this*
chapter; when it is, it adds an `## Enrichment from research`
block with **1-2 specific period details per relevant scene**
(named scene index, named detail, the `[shortname]` citation,
plus an explicit "do NOT change plot, dialogue, voice, scene
structure" guard). Chapters where the research doesn't fit (the
research is a brush, not a chisel) get briefs without the
enrichment block — they pass through with whatever revisions the
standard loop wanted.

Why this works:
- The brief is the bridge — it decides which scenes get
  enriched and which stay alone, based on the chapter's actual
  content, not blanket find-and-replace.
- The "do NOT change" guards in the enrichment block keep the
  rewrite light. Without them, `revise` would re-write the whole
  chapter, which is the opposite of what you want post-revision.
- The research notes also carry their own `## Candidate Canon
  Entries` section — concrete dated facts (e.g. "Fugger arrived
  in Venice 1478 [bib]") that the per-chapter `promote-canon`
  step folds into `shared/canon.md` (research-cited entries are
  series-wide) at the end of each chapter's loop. So the research's *facts* land in canon (and supersede
  any contradictory entries because of the `[research:slug]` tag)
  while the research's *texture* lands in prose.

Surgical alternative for a single chapter: same flag works on
`brief` directly:

```text
/autonovel:brief 8 --from auto \
    --enrich-with shared/research/notes/venice-politics-and-trade-1479-1500.md
/autonovel:revise 8
/autonovel:evaluate --chapter 8
```

When NOT to use this:
- For sweeping period research at the start of a project, use
  `/autonovel:research --from-seed` instead — it auto-derives
  topics from the seed and auto-pipes facts into pending_canon.
  `--enrich-with` is for *late* research on chapters that are
  already revised.
- For a wrong fact (canon says 1471, research says 1478), the
  fact lands in canon via promote-canon; you don't need
  `--enrich-with` for that. Use it when you want *texture* —
  named officials, building details, period vocabulary, the
  weight of a coin in the right currency — that the original
  draft generalised.

Time: ~2-3 min per affected chapter (the standard revision-pass
budget). The light-touch constraint keeps it predictable.

#### After the sweep — the closer

A multi-chapter revision pass (with or without `--enrich-with`)
substantively changes the manuscript and the canon. Don't stop at
"the sweep finished" — there's a short, named verify-then-review
sequence that catches the things a sweep can silently break:

1. **Read the score deltas in the postamble** *(2 min, attention)*.
   Per-chapter line ends in `eval: <prev> → <new> (Δ ±X.X) |
   canon: +<P>`. Two flags worth acting on:
   - **Negative Δ** on any chapter = the rewrite made it worse.
     Re-run *that one chapter* without the enrichment flag:
     `/autonovel:revision-pass --chapters <NN>`. The brief drops
     the enrichment block and reconsiders the rewrite from
     cuts/eval evidence alone.
   - **canon: +P where P > 0** = research-derived facts landed
     in `shared/canon.md`. End-of-sweep promote-canon also ran;
     anything *still* in `pending_canon.md` is a conflict that
     needs human resolution — see §2c below.

   To see the rewrites themselves rather than their scores, open the
   page the sweep's summary names (it hands back the chapters you had
   already read, against your last read), or run
   `/autonovel:diff --book <book> --from last-read --mark-read`
   (or `--from <tag>`). It writes one HTML page — path printed —
   with every word-level edit shown inside its paragraph and `j`/`k`
   stepping change to change, so you can confirm the brief's asks
   landed (and spot edits nobody asked for) without re-reading the
   chapters; "Big changes only" hides the wording trims, and "Clean
   text" is the new version to read straight through. `--annotate`
   gives each change a plain note on what it is, the brief / talk turn
   / review item behind it, and a big/small flag. `--mark-read` once
   you have read it, so the next hand-back starts there.

2. **Check `books/<book>/pending_canon.md`** *(2 min if any conflicts)*.
   If the file says `no new facts`, you're done with canon. If
   it has `# Conflicts — resolve before next promote-canon`,
   open it and follow the HTML-comment instruction block at the
   top (three labelled paths). Re-run `/autonovel:promote-canon`
   after editing.

   **After `/autonovel:promote-canon` runs cleanly**, if any facts
   were superseded (research-tagged entries that beat prior canon),
   the question "which chapters reference the now-wrong fact?"
   used to require manual `ls` + `grep`. It doesn't anymore:

   ```text
   /autonovel:impact-of --book <book>
   ```

   parses every `## Superseded <date>` block in `shared/canon.md`,
   greps each chapter for tokens unique to the prior value, and
   prints a per-chapter action checklist of `/autonovel:revise
   --chapter N` calls with line-snippet evidence. Mechanical
   candidate generator — some matches are false positives (a year
   that coincides with the flipped fact in unrelated context),
   so skim each snippet before revising. Cheap, no LLM.

3. **Re-run structure-review, reader-panel + review on the revised
   book** *(25-50 min compute, 30-45 min reading)*.
   You changed many chapters; any prior `structure_review.json`,
   `reader_panel.json` and `review.md` describe the pre-revision
   book and are now stale. Re-running gives you a fresh
   flagged-chapter list. Structure first — review's stop-revising
   verdict is gated on it (§2g):

   ```text
   /autonovel:structure-review --book <book>
   /autonovel:reader-panel --book <book>
   /autonovel:review --book <book>
   ```

   Both are whole-book reviewers (see §0) — they write reports,
   don't modify chapters. The chapters you just revised should
   now be stronger; chapters that *weren't* revised may look
   weaker by comparison, which is itself a useful signal pointing
   at next round's targets.

4. **Commit to your GitHub backup** *(1 min)*. A substantive
   revision is the right cadence for a snapshot:

   ```bash
   cd ~/<series-root>
   git add . && git commit -m "Research enrichment pass: chapters <list>" && git push
   ```

   Recipe + `.gitignore` template in §3e.1. Skip if your novel
   isn't yet backed up — set up the private repo first.

5. **(Optional) Typeset and read a few chapters in PDF form**
   *(1 min compute, 5-15 min reading)*.

   ```text
   /autonovel:typeset --book <book>
   ```

   Open `books/<book>/typeset/<book>_latest.pdf` and read 2–3
   of the chapters you just enriched end-to-end. Reading on the
   page catches texture problems the LLM judges miss — a name
   that came in too heavy, a period detail that breaks voice, a
   citation that reads as didactic. Cheap, safe, read-only
   against chapter prose.

6. **Decide: another revision pass on the panel/review flagged
   chapters?**

   ```text
   /autonovel:revision-pass --chapters <flagged-list>
   ```

   No `--enrich-with` this time *unless* you have new research.
   When the structure gate blocks, the next pass is
   `/autonovel:revision-pass --chapters structural --book <book>`
   (after running any merge / cut the structure review lists).
   If nothing was flagged and the structure gate passes, you're
   done with this round — move on to `/autonovel:title`,
   `/autonovel:introduction`, `/autonovel:typeset`,
   `/autonovel:package`.

The same closer applies to a non-`--enrich-with` revision-pass —
the verify → panel-review → backup → decide loop is what closes
*every* multi-chapter rewrite, not just enrichment ones. §2a's
first-pass recipe already names this implicitly ("Your move next
is `/autonovel:revision-pass --chapters X,Y,Z` against the flagged
list, or done if nothing was flagged"); this section names it
explicitly because §2b.1 readers come here from a different
mental model (they were doing a research integration, not a
quality pass) and shouldn't have to chase the closer through §2a.

### 2c. Minor factual error (a date is wrong, a name is misspelled)

Research found that Jakob Fugger arrived in Venice in 1478, but
your canon says 1471 and chapter 3 references the 1471 date. Two
fixes:

**For the canon (one source of truth across all books):**

```text
/autonovel:research --from-seed       # writes notes with citations
/autonovel:promote-canon              # research-tagged entries win conflicts
                                      # (the [research:slug] tag does this automatically)
```

`shared/canon.md` now has the corrected fact plus a
`## Superseded <UTC-date>` block recording what changed.

**For the affected chapters:**

```text
/autonovel:check-anachronism 3         # report into edit_logs/
                                       # — does the chapter actually reference the wrong date,
                                       #   or is the contradiction only in canon?
/autonovel:brief 3 --from auto         # if the chapter needs revision
/autonovel:revise 3                    # rewrites chapter 3 with the corrected date
```

For a misspelled character name across the whole book:

```text
/autonovel:rename-character --old Niccolo --new Niccolò
```

**Script-based**, not LLM rename. Word-boundary `sed` across every
chapter and summary, the outline, the cast and design files, every
queued brief and staged turn, and the shared files. A longer word
that merely contains the name (`Anatolia` when renaming `Ana`) is left
alone and listed; the rename refuses only when the name also appears
in a form word boundaries would miss, such as a plural (`Anas`).
Research notes and edit logs keep the old name, and the report lists
where.

#### What if `/autonovel:promote-canon` reports conflicts?

When the same `pending_canon.md` entry contradicts an existing
line in `shared/canon.md` (or `world.md` / `characters.md`),
`/autonovel:promote-canon` does NOT silently merge. It writes the
contradicting entries back to `books/<book>/pending_canon.md`
under a `# Conflicts — resolve before next promote-canon`
header, and each conflict gets its own `## Conflict N` block.

Open `books/<book>/pending_canon.md` and read the HTML-comment
block at the top — it contains step-by-step instructions for the
three resolution paths (accept the new fact / reject it / both
are wrong). Each `## Conflict N` block tells you exactly which
file the contradicting line lives in, so you know where to edit.

The short version:

- **Accept the new fact** (research-derived dates are usually
  this case): edit the file named in `Existing canon (in: ...)`,
  replace the old line with the new one, delete the `## Conflict
  N` block from `pending_canon.md`, re-run `/autonovel:promote-canon`.
- **Reject the new fact** (a chapter hallucinated something the
  canon already settles): delete the `## Conflict N` block; the
  candidate is dropped. Optionally `/autonovel:revise` the chapter
  named under `Source` so the wrong fact stops coming back.
- **Both wrong**: edit the canonical file to the correct value,
  delete the `## Conflict N` block.

Re-run `/autonovel:promote-canon` after editing. Resolved
conflicts disappear; unresolved ones come back flagged with the
same instructions. There is no `--force-merge` mode by design —
the human decision lives in this loop.

### 2d. Adding pictorial plates (maps, paintings, photographs)

Historical fiction (and some non-fiction) wants real images in the
typeset PDF — a period map, a portrait, a trade-route diagram.
`/autonovel:art-import` handles each:

```text
/autonovel:art-import --file ~/Downloads/de_barbari_venice_1500.png \
  --chapter 1 --placement before-chapter \
  --caption "Jacopo de' Barbari, View of Venice, 1500." \
  --attribution "Public domain, via Wikimedia Commons."

/autonovel:art-import --file ~/Downloads/durer_jakob_fugger.jpg \
  --chapter 5 --placement before-chapter \
  --caption "Albrecht Dürer, Portrait of Jakob Fugger the Rich, c. 1518." \
  --attribution "Bayerische Staatsgemäldesammlungen."

/autonovel:art-import --file ~/maps/hanseatic_routes.svg \
  --chapter 9 --placement before-chapter \
  --caption "Principal Venetian–Hanseatic trade routes, late 15th century."

/autonovel:typeset                     # rebuild the PDF with the plates woven in
```

Each invocation copies your image into
`books/<book>/typeset/plates/<slug>.<ext>` and registers it in
`books/<book>/typeset/plates.yaml` with the chapter, placement,
caption, and attribution. Three placements:

- `--placement before-chapter` (default) — **dedicated full-page**
  plate facing the chapter heading. Best for full maps, portraits,
  full paintings.
- `--placement chapter-start` — **inline centered** image just below
  the chapter title. Smaller; no page break. Best for atmospheric
  inserts (a sketch of bagged spices, a small woodcut).
- `--placement after-chapter` — full-page plate after the chapter
  body. Less common.

For a small monochrome insert that should *replace* the AI-generated
chapter ornament rather than add a new page:

```text
/autonovel:art-import --file ~/Downloads/austere_church_woodcut.png \
  --chapter 7 --as ornament
```

`--as ornament` mode drops the file at `books/<book>/art/ornaments/
ch_07.png` (overriding whatever ornament-pipeline produced).

`books/<book>/typeset/plates.yaml` is human-readable; you can edit
it directly to tweak captions, reorder, or remove plates. Re-running
`art-import` with the same `--slug` overwrites the prior entry only
if you pass `--force`.

### 2e. Major change (cut a chapter, change the ending)

Halfway through revision you decide chapter 12 should be cut — its
beats are folded into chapters 11 and 13. (The usual evidence is
`/autonovel:structure-review` flagging it `removable` — no later
chapter breaks without it — with a `cut` or `merge` candidate that
carries the exact command below and names the chapter that absorbs
its one needed fact.)

```text
/autonovel:remove-chapter 12          # deletes ch_12.md; renumbers 13→12, 14→13, etc.
                                      # — chapter renumbering is by script, not LLM rename
/autonovel:revision-pass --chapters 11,12   # the new 11 and 12 (formerly 11 and 13)
                                            # need fresh briefs + revises
/autonovel:evaluate --full            # confirm the whole book still scores
```

Or two adjacent chapters that should be one:

```text
/autonovel:merge-chapters --chapters 14,15
```

For a structural ending change — different kind of resolution, not
just a tweak — the cleanest path is:

1. Edit `books/<book>/outline.md` directly to change the final
   chapters' beats.
2. `/autonovel:revise <last-chapter>` — picks up the new beats.
3. `/autonovel:check-anachronism` and `/autonovel:reader-panel`
   to confirm continuity hasn't broken.
4. Address any chapters where the new ending changes what was set
   up — for instance, if the new ending requires a key foreshadowed
   detail in chapter 5, run `/autonovel:foreshadow --plant 5
   --payoff <last>`.

Time: 20–60 min of human thinking, 30–90 min of compute.

### 2f. Adding a plot point retroactively

You've drafted 10 chapters and realise you want to add a subplot —
a minor character secretly poisoning the well — that needs setup
in chapter 2 and payoff in chapter 9.

```text
/autonovel:add-subplot \
  --thread "Eduardo poisons the speziale's well over jealousy" \
  --plant 2 --payoff 9
```

This:
- Edits `books/<book>/outline.md` to add a plant beat in 2 and a
  payoff beat in 9.
- Writes a `## Threads` ledger entry tracking the plant→payoff.
- Does **not** rewrite chapters 2 or 9 — that's the next step.

Then:

```text
/autonovel:revise 2     # incorporate the plant
/autonovel:revise 9     # incorporate the payoff
/autonovel:revision-pass --chapters 3-8    # propagate ripples through middle chapters
```

For a single foreshadow detail (rather than a full subplot):

```text
/autonovel:foreshadow --plant 2 --payoff 9 \
  --thread "the Fugger ledger entry that Tommaso misreads"
```

Same shape, simpler thread.

For a brand-new character mid-book:

```text
/autonovel:add-character --name Eduardo --role apothecary's apprentice
```

…then either let downstream chapters pick him up via
`/autonovel:revise`, or use `/autonovel:deepen-character Eduardo`
to add an unguarded moment that makes him real.

### 2g. When to stop revising: the book-level gate

Every chapter can be good while the book is not. On *kingmaker* the
chapter evals held at 7+, `/autonovel:review` held at 4★ for ten
passes and the reader panel said all four personas would buy it —
and the author's own read was *"a bunch of short anecdotes and not a
continuing story building to a climax."* Each of those reviewers is
prose-weighted; none asked whether chapter N+1 happens *because of*
chapter N. (The full audit: [`reviewer-audit.md`](reviewer-audit.md).)

Before either half, get an editor's read:
`/autonovel:developmental-edit --book <book>` reads the whole book in
order, cold, and writes a ranked letter on the story. The two gates
below are instruments; the letter is the judgement, and it says where
the instruments are blind. Revise from the letter, then use the gates
to check.

So "stop revising" now has two halves, and both must hold:

1. **Book-level gate** — `/autonovel:structure-review --book <book>`
   has run since the last chapter changed, and it scores the
   structure ≥ 4/5 with **no chapter removable** (a chapter no later
   chapter needs is an anecdote).
2. **Prose level** — the Bells rule `/autonovel:review` applies: 4½★
   with no major unqualified items, or mostly qualified hedges, or
   fewer than three items. Structural items never count as hedges.

`/autonovel:review` computes both and writes the verdict to
`review.json`; when the structure review is missing or stale it says
"run /autonovel:structure-review first". `/autonovel:next` surfaces the
same gate, and `autonovel mechanical structure-validate books/<book>
--format markdown` prints it for free.

The loop when the gate blocks:

```text
/autonovel:developmental-edit --book <book>     # the editor's letter (read it first)
/autonovel:developmental-edit --book <book> --stage   # queue the in-chapter fixes you accept
/autonovel:structure-review --book <book>       # verdict + candidates
#   cross-chapter moves it lists are YOURS to run, before the sweep:
#   /autonovel:merge-chapters --chapters 15,16 --book <book>
#   /autonovel:remove-chapter 13 --book <book>
#   then /autonovel:impact-of --book <book> --source merge-chapters
#   and re-run /autonovel:structure-review (the numbering changed)
/autonovel:revision-pass --chapters structural --book <book>
#   brief --from auto writes `kind: structural` briefs; revise
#   restructures inside each chapter and never touches a neighbour
/autonovel:structure-review --book <book>       # re-check
/autonovel:review --book <book>                 # the prose-level half
```

A structural pass is measured by the next structure review, not by
the chapter-score deltas: a consequence scene can lower a chapter's
prose score while turning an "after" into a "because". Two rotations
of structural passes without the score rising means the outline is the
problem — go back to `/autonovel:gen-outline --book <book> --add-spine`,
read its `## Causal spine`, and decide the restructure yourself.

For **historical fiction** the check matters most: the record is
episodic by nature (deals, deaths, elections), so the novel has to
supply the spine — who opposes the protagonist between the recorded
events, and which earlier choice of his each event punishes or
rewards. The structure review flags a book whose chapters simply
follow the record as `chronicle-spine`.

---

## 3. Day-to-day mechanics

### 3a. Updating Claude Code itself

Claude Code self-updates when you invoke it; just relaunch.
Verify the version:

```bash
claude --version
```

If you ever need to manually upgrade (e.g. a release that fixes
something you're hitting), see Anthropic's
[Claude Code install guide](https://docs.claude.com/en/docs/claude-code) — the install method depends on
how you originally installed it (npm, native installer, etc.).

**Where Claude Code keeps state on your machine:**

| Path | What lives there |
|---|---|
| `~/.claude/settings.json` | Your global Claude Code config (model preference, theme, hooks) |
| `~/.claude/commands/autonovel/` | The `/autonovel:*` command files (written by `autonovel install`) |
| `~/.claude/projects/` | Per-project conversation history |
| `<your-series-root>/.claude/settings.json` | Project-local overrides (statusline + permissions, written by `autonovel statusline-setup`) |
| `<your-series-root>/.claude/commands/` | Project-local commands (only used by autonovel's smoke tests; you can ignore) |

If a Claude Code update changes its tool API or settings shape,
re-run `autonovel install` to refresh the command files into the
new shape.

### 3b. Updating autonovel

```bash
cd ~/autonovel              # the autonovel source clone
git pull                    # latest commits
pipx reinstall .            # rebuild the installed package from local source
cd ~/<your-series-root>
autonovel install           # re-render /autonovel:* commands into ~/.claude/commands/autonovel/
                            # — needed any time we ship new commands or change a body
```

Three-line variant when you remember the gist but not the order:

```bash
( cd ~/autonovel && git pull && pipx reinstall . )  &&  autonovel install
```

**Important:** `autonovel install` only overwrites command files in
your runtime's directory (e.g. `~/.claude/commands/autonovel/`). It
**does not touch your book content** — your `books/<book>/voice.md`,
`books/<book>/chapters/`, `shared/canon.md`, eval logs, briefs, and
everything else under your series root are completely safe across
upgrades. Re-installing the commands is how you *pick up* new
features (e.g. the per-book Custom rubric, per-character voice
fingerprints, irreversible-change scorer, scene-beat coverage that
shipped 2026-04-25); your novel never gets clobbered.

**Preview before installing.** If you want to see what the install
would write before letting it touch `~/.claude/commands/`:

```bash
autonovel install --dry-run    # prints would-be paths; touches no disk
```

Each runtime banner switches from "installed" to "would install" and
the per-file sigil flips from `+` to `~`. Useful for `npx autonovel
install --dry-run` on a fresh box, or just to confirm what changed
between two `pipx reinstall` runs.

**Typeset templates need a separate refresh.** `autonovel install`
does not touch `<series-root>/typeset/novel.tex` (or other typeset
template files), because those were copied into your series at
`autonovel new-series` time and you might have hand-edited them.
When a fix lands in the package's typeset templates — e.g. the
2026-04-25 PDF running-header fix and the 2026-04-28 chapter-title
fix that together stop the first sentence of each chapter being
used as an "alternating page header" — pull it into your series with:

```bash
autonovel refresh-templates              # default: typeset/ and shared/craft/
autonovel refresh-templates --dry-run    # preview; writes nothing
```

The command only touches files that exist in the package template;
your local-only files (custom macros, hand-tuned overrides) are
preserved and listed under `local-only (preserved)` in the report.
Pass `--only typeset --only shared` to also pull research seeds /
shared template updates.

**The craft reference documents refresh the same way.** Since
2026-10 every series carries `shared/craft/` (`CRAFT.md`, `PROSE.md`,
`ANTI-SLOP.md`, `ANTI-PATTERNS.md`), the documents the draft, revise
and evaluate commands read before touching prose. Before that they
lived only in the autonovel repository, where a series session could
not see them, and the writer worked from `voice.md` alone. A series
created earlier has no `shared/craft/`: `autonovel doctor` warns, and
`autonovel refresh-templates` (default scope) copies the current
versions in. Do not hand-edit them; a book's register and any
deliberate departures belong in `books/<book>/voice.md` Parts 1–3,
which outrank the craft documents on conflict.

### 3b.1. Upgrading an existing book to use new voice.md sections

When autonovel ships new voice.md surfaces (Parts 3 and 4 shipped
2026-04-25 — Custom rubric and Per-character voice fingerprints),
your existing book's `voice.md` won't have them yet. The safe
upgrade path:

```bash
# 1. Pull the new autonovel and reinstall commands (see §3b above).
( cd ~/autonovel && git pull && pipx reinstall . )  &&  autonovel install

# 2. Inside Claude Code, in your series root:
/autonovel:voice-discovery --book <book> --upgrade
```

`--upgrade` is the load-bearing flag here. It:

- **Preserves Parts 1 and 2 verbatim** — your hand-tuned voice
  fingerprint is never overwritten.
- **Appends the Part 3 placeholder** (Custom rubric) if it isn't
  already present. You then hand-edit Part 3 to add book-specific
  scoring rules — see the placeholder comment for examples.
- **Drafts Part 4** (Per-character voice fingerprints) from
  `shared/characters.md` if the cast count is ≥3.

Without `--upgrade`, voice-discovery refuses to re-run on a
populated voice.md (because it would otherwise regenerate Part 2
and lose your work). Use `--force` only when the prior voice.md is
junk and you genuinely want a clean re-derive.

### 3b.2. Generating a PDF and ePub

The fastest "I want to see the book typeset" sequence, after the
tools in §5a/§5b are installed:

```bash
# 1. Inside Claude Code, in your series root:
/autonovel:typeset --book <book>
```

That single command produces:

- `books/<book>/typeset/<book>.pdf` (via tectonic)
- `books/<book>/typeset/<book>.epub` (via pandoc, when pandoc is
  installed; silently skipped if not)

If you only want one or the other:

```text
/autonovel:typeset --book <book> --pdf-only
/autonovel:typeset --book <book> --epub-only
```

Pre-flight: run `autonovel doctor` (in the series root) first.
Missing `tectonic` or `pandoc` show as **WARNING** lines with the
fix command — install whatever you need, re-run `doctor` until the
warning for your target tool is gone, then run typeset.

Don't want to debug shell? Use the interactive helper:

```bash
autonovel install-export-tools                          # print all install steps
autonovel install-export-tools --exports pdf,epub       # narrow to one slice
autonovel install-export-tools --apply                  # run them, prompt-per-tool
autonovel install-export-tools --apply --yes            # run them all, no prompts
```

It detects your OS (Debian/Ubuntu/macOS), notices whether autonovel
itself was installed via pipx vs pip, and prints the exact commands
in order — including the known-fragile cases (e.g. apt-tectonic
often ships too old → fall back to the upstream prebuilt binary)
and the `pipx inject` vs `pip install` choice for `Pillow` / `pydub`.
Each tool has a `verify` command run after install so a too-old
binary on PATH gets caught instead of silently passing.

You can run typeset between revision passes purely as a "what does
the book look like right now?" check — it doesn't modify the
chapters, only writes typeset artifacts under
`books/<book>/typeset/`. Safe to interrupt and re-run.

**Numbers-only chapter pages.** By default typeset renders
"Chapter VII — The Apothecary's Mortar" in the TOC and chapter
opening pages, reading the per-chapter `title:` frontmatter that
`/autonovel:draft` step 11 generates. To switch to the older
"Chapter I, Chapter II, …" convention (numbers only), set:

```yaml
# project.yaml
typeset:
  chapter_titles: false
```

Both the PDF and ePub paths honour the toggle (the flag flows
through `autonovel mechanical build-tex --project-yaml project.yaml`
and `build-epub-md --project-yaml project.yaml`, which `/autonovel:
typeset` invokes for you). One-off override at the CLI:
`autonovel mechanical build-tex <chapters_dir> --no-chapter-titles`.

**Adding a back-cover image to the PDF.** Drop a PNG at
`books/<book>/art/back_cover.png` and re-run `/autonovel:typeset`.
The template renders it as a full-bleed page after the colophon
(parallel to the front-cover block). Its presence is also surfaced
in the `autonovel tui` Front + back matter tab so you can see at
a glance whether the file is in place. (For the printed wraparound
— front + spine + back on one canvas — `/autonovel:cover-print
--pages <N>` is the right tool; the back-cover PNG drop-in is
specifically for the standalone PDF.)

For cover art (`/autonovel:cover-print`), audiobook
(`/autonovel:audiobook-*`), and chapter ornaments
(`/autonovel:art-vectorize`), see §5c–§5d for the tool prerequisites
and the per-command help inside Claude Code.

### 3c. Restarting after a crash, power loss, or kernel reboot

Power off mid-draft → boot back up → continue. autonovel is
designed for this.

```bash
cd ~/<your-series-root>     # whichever folder has project.yaml
ls .autonovel/in-progress.lock 2>/dev/null && echo "lock exists"
```

Then in Claude Code, in the series root:

```text
/autonovel:resume
```

It detects the stale lock from the interrupted command, shows you
what was running, and offers three options:

- **Redo**: re-run the command from scratch (safe; the prior
  attempt's checkpoint is still there).
- **Keep partial**: take whatever the prior attempt actually wrote
  to disk and move on. Useful when a 3,200-word draft made it
  before the crash and you'd rather edit it than redraft.
- **Inspect**: print the prior command, its arguments, and which
  files were partially written, then let you decide.

If `/autonovel:resume` fails or you want to be sure, you can
manually `autonovel rollback` to a checkpoint before the crashed
command:

```bash
autonovel rollback --list           # show recent checkpoints
autonovel rollback --to 2026-04-25T18:32:00Z   # restore a specific one
```

Each `/autonovel:*` command takes a checkpoint at its preamble, so
rolling back to the most recent one undoes only the most recent
command.

### 3d. Starting a new book in the same series

Your series shares world, characters, canon, and the events ledger
across books. Adding a second book reuses all of that:

```bash
cd ~/<series-root>
autonovel new-book the-cartographer --pov Lucia --story-time-range 1492-1502
```

That creates `books/the-cartographer/` with empty seed, voice,
outline, etc. Edit the seed:

```bash
nano books/the-cartographer/seed.txt
```

Then in Claude Code (in the series root):

```text
/autonovel:next        # walks you through voice-discovery, gen-outline, then
                       # gen-canon --book <new> (the book half) for the new book
                       # (gen-world / gen-characters / shared gen-canon are already done from book one)
/autonovel:draft-pass --chapters 1-12 --book the-cartographer
```

Cross-book continuity is enforced automatically:

- Chapters in `the-cartographer` (1492–1502) cannot leak content
  from `the-inquisitor` chapters (1519–1523) into their drafts —
  story-time gating prevents it.
- Conversely, when you draft `the-inquisitor` chapter 5, the
  drafter has access to `the-cartographer` chapters whose
  story_time is ≤ chapter 5's story_time.
- Inter-book canonical events live in `shared/events.md` — see
  [`docs/multi-book.md`](multi-book.md) for the schema.

### 3e. Starting a new series

A series is the unit of co-evolving lore. A standalone novel is a
series with one book. Choose a series root somewhere outside the
autonovel source clone (a clean parent dir for novel projects):

```bash
mkdir -p ~/novels
cd ~/novels
autonovel new-series the-low-countries --genre historical-fiction
cd the-low-countries
autonovel new-book amsterdam --pov Wolfaert --story-time-range 1648-1652
nano books/amsterdam/seed.txt
autonovel statusline-setup    # wire the per-project statusline + tool permissions
claude                         # launch your runtime in the new series root
```

Then in Claude Code:

```text
/autonovel:next               # foundation gap detector picks up from seed
```

Walks you through `gen-world → gen-characters → voice-discovery →
gen-canon (shared) → design → gen-outline → gen-canon --book (this book's
outline facts) → evaluate-foundation → draft 1`. If
`project.yaml` has a `period` set, the chain prepends
`/autonovel:research --from-seed`.

### 3e.1. Backing up your novel to GitHub (private repo)

**Important:** your novel data — `~/<series-root>` — is NOT
backed up anywhere unless you explicitly set up a backup. The
autonovel codebase being on GitHub does not back up your book; the
two live in separate directory trees. A Chromebook crash, an
accidental `rm -rf`, or a corrupted Linux container loses your
book if the only copy is local.

The recommended backup is a private GitHub repo. Free for personal
use, version history of every revision, restorable to any new
machine in one `git clone`.

**One-time setup** (run from your series root):

```bash
cd ~/<series-root>            # the folder with project.yaml

# Quick sanity check — is this already a git repo backed up somewhere?
git remote -v 2>/dev/null
# If `origin  https://github.com/...` prints, you're already backed up.
# If nothing prints, continue below.

# Initialise a git repo at the series root (idempotent — safe to
# re-run on an already-initialised tree).
git init
git branch -M main

# Copy autonovel's recommended .gitignore template if your series
# doesn't have one yet (or has the older minimal version).
# The template excludes the bulk regenerables (checkpoints,
# typeset artefacts, audiobook MP3s, LaTeX intermediates) but
# commits everything that costs work to recreate (chapters,
# briefs, eval logs, voice, canon, cover art, project.yaml).
cp ~/code/autonovel/src/autonovel/templates/series/.gitignore .gitignore
# Or if you installed via pipx and don't have the source clone:
# pipx-install path:
# cp ~/.local/share/pipx/venvs/autonovel/lib/python*/site-packages/autonovel/templates/series/.gitignore .gitignore

# First snapshot.
git add .
git commit -m "Initial backup $(date +%Y-%m-%d)"

# Push to a NEW PRIVATE GitHub repo. You need the `gh` CLI for
# this one-shot creation (`sudo apt install gh` on Chromebook /
# Debian; `brew install gh` on macOS). One-time `gh auth login`
# first if you haven't.
gh repo create my-novel-backup --private --source=. --remote=origin --push
```

After this, your novel lives at `https://github.com/<you>/my-novel-backup`
as a private repo — only you can see it.

**Daily / per-session use** (after the one-time setup):

```bash
cd ~/<series-root>
git add .
git commit -m "End of session $(date +%Y-%m-%d)"
git push
```

Or wrap that in a shell function in `~/.bashrc` so you can just
type `novel-save`:

```bash
novel-save() {
  ( cd ~/<series-root> && git add . && git commit -m "Snapshot $(date +%Y-%m-%d_%H%M)" && git push )
}
```

**What gets committed (the things that cost real work):**

- `project.yaml`, `shared/world.md`, `shared/canon.md`,
  `shared/characters.md`, `shared/events.md`, `shared/research/`,
  `shared/sources.bib`
- `books/<book>/seed.txt`, `voice.md`, `outline.md`,
  `pending_canon.md`
- `books/<book>/chapters/ch_NN.md` (the prose) and
  `books/<book>/chapters/ch_NN.summary.md` (continuity handoffs)
- `books/<book>/briefs/`, `eval_logs/`, `edit_logs/` (the decision
  trail — losing these means re-running expensive evaluations)
- `books/<book>/preface.md`, `introduction.md` if you've made them
- `books/<book>/title_proposals.md` if you've used `/autonovel:title`
- `books/<book>/art/cover.png`, `ornament_chNN.png` (regenerating
  these costs fal.ai credit)
- `books/<book>/audiobook/voices.yaml` and the parsed scripts

**What's deliberately NOT committed:**

- `.autonovel/checkpoints/` (large; per-command snapshots, only
  useful within one session)
- `.autonovel/in-progress.lock` (PID-bound, useless on another
  machine)
- `books/<book>/typeset/<book>_<YYYYMMDD>_<HHMM>.pdf` and `.epub`
  (the per-build timestamped copies — excluded so the repo
  doesn't balloon with one new file per rebuild)
- `books/<book>/typeset/novel.tex`, `chapters_combined.md`,
  `front_matter.tex`, `chapters_content.tex`, `metadata.yaml`
  (intermediate build inputs, regenerated by `/autonovel:typeset`)
- BUT `books/<book>/typeset/<book>_latest.pdf` and
  `<book>_latest.epub` ARE committed — these are the convenience
  pointers `/autonovel:typeset` overwrites on every successful
  build, so a `git clone` of your backup gives you a usable PDF
  and ePub on a fresh machine without rebuilding. Delete the two
  `!` lines from `.gitignore` if you'd rather not commit any
  binary outputs at all.
- `books/<book>/audiobook/*.mp3`, `*.wav`, `*.m4b` (large; ~50–500 MB
  for a full novel; regenerable via `/autonovel:audiobook-generate`,
  though that DOES cost ElevenLabs credit on each rebuild — so if
  you've finished the audiobook and want to commit the audio, just
  remove that line from `.gitignore`)

If you only have an existing novel set up before this `.gitignore`
was improved, you can apply the new version retroactively — it's
just a copy. Re-running `git add .` after copying picks up any
files newly excluded (and skips them) and any files newly tracked.

### 3f. Daily checkpoint: where am I?

Anywhere in your series root:

```bash
autonovel status                    # CLI: phase, scores, last command, lock state
```

Or in Claude Code:

```text
/autonovel:next                     # state-aware action list
```

`/autonovel:next` inspects the live filesystem — pending canon
conflicts, chapter regressions, briefs not yet acted on (the chapter unchanged since the brief was written)
(the brief→revise pair is the most common situational signal),
**stale per-chapter summaries** (a `.summary.md` whose recorded
fingerprint no longer matches its chapter's text — the load-bearing
continuity surface every drafter reads, HIGH priority because next
chapter's drafter would see the wrong cast / threads / POV state;
commands refresh such summaries before reading them and can't
finish while one they changed is out of date, so this means a hand
edit), stale reader-panel
/ Opus review reports, missing front matter, missing book title,
GitHub backup state — and emits a prioritised action list. The canonical pipeline next step (from the prior
command's footer) appears at the bottom; situational actions take
precedence over it. Past-end-of-book guard: when the canonical
line points to a draft chapter beyond what exists by more than 1,
it gets demoted to a "book appears complete — try `/autonovel:evaluate
--full`" suggestion. Cheap to call repeatedly; pure mechanical,
no LLM.

You'll also see a one-line **💡 Maybe try:** hint in every
command's postamble footer (right after `**Next:**`). It's the
top situational signal pulled from the same enumerator
`/autonovel:next` uses, so most of the time you don't need to
call `/autonovel:next` at all — the hint already points at the
work the situational state demands. When no situational signal
applies, it falls back to a rotating "Did you know?" hint from
a small pool of less-known commands. Decorative, never blocking
— a crash in the hint path doesn't fail the command.

For a long-running view that updates as your book grows, run
`autonovel tui` in a *separate* terminal window from the series
root:

```bash
autonovel tui                  # default: first book in project.yaml
autonovel tui --book <name>    # start on a specific book
```

The TUI is read-only by contract — it never acquires the lock and
never writes any file. Polls the filesystem every 5 s; press `r`
to refresh on demand. Tabs:

- **Help (live)** — for each currently-suggested next command,
  shows *why* it's suggested (rationale from the situational
  enumerator), *what it does* (description from the command
  frontmatter), *what it reads* (every input artifact), and
  *what it writes* (every output artifact, or "read-only" when
  the command writes nothing). The right pane to consult before
  invoking a heavy-tier command in your runtime.
- **Chapters** — DataTable of every chapter (ch / words / pov /
  story_time / score / status) with a side-pane chapter detail
  view. Score sparkline at the bottom. Cursor a row to see its
  detail.
- **Research** — list of `shared/research/notes/*.md` with a
  preview pane.
- **Foundation** — status of `world.md`, `characters.md`,
  `canon.md`, `voice.md`, `outline.md`, `seed.txt`, plus the
  pending-canon state.
- **Front + back matter** — every surface typeset weaves into
  the PDF: title page (title + author), preface,
  introduction, glossary (front matter, before chapter 1),
  and appendix (back matter, after the last chapter). Each
  row shows ✅/❌ for presence, the word count when present,
  and the exact slash-command to create it when absent.
  Render order documented inline (Title → Preface →
  Introduction → Glossary → chapters → Appendix → colophon).
- **Reviews** — reader-panel + Opus review presence + last-run
  timestamps.
- **Commands** — last 15 logged commands + the situational
  next-actions list + canonical pipeline step.

Header bar: series name · book selector · lock state · sweep
progress (live) · cost today + total · `⏸ paused` indicator
when auto-refresh is suspended. Switch books with `b`. Quit with
`q`. Pause / resume auto-refresh with `p` — useful when you want
to read prose or copy text without the cursor jumping around.

**Cursor preservation:** highlighting chapter 14 and walking away
no longer resets you to chapter 1 on the next refresh — the row
cursor is restored across each 5 s tick (clamped to the new row
count if rows are added or removed).

**Scroll preservation:** the chapter-detail and research-note
preview panes hold their `VerticalScroll` position across refresh.
Reading line 200 of a long research note no longer snaps you back
to line 0 every 5 s.

**Sparklines (Chapters tab):** two side-by-side rows show the
shape of the book at a glance:

- **Score** — overall score from per-chapter `/autonovel:evaluate`
  on a 0–10 scale (10 best). Threshold is 7.0; any chapter below
  is a `revise` candidate. Range / mean / below-threshold count
  shown alongside.
- **Tension** — `tension` dimension from `/autonovel:evaluate
  --full` on a 0–10 scale (higher = more pull-through). Reads
  the latest `<ts>_full.json`; if you haven't run `--full` yet,
  the line says so explicitly. A `⚠️  Tension drops` line surfaces
  any range of ≥3 consecutive declining chapters — the same
  signal the dashboard's tension-drop alarm flags.
- `·` blocks in either row mark chapters with no eval data for
  that dimension yet.

**Copy / paste:** textual captures mouse events; bypass with
`shift+drag` (works in GNOME Terminal, iTerm2, Windows Terminal,
kitty, Alacritty). For best results, press `p` first to pause
auto-refresh so the view doesn't redraw under your selection.
The Help tab includes the same instructions inline so you don't
need to context-switch.

Optional dep: requires `textual>=0.70`. Install via `pip install
'autonovel[tui]'` or `pipx inject autonovel textual`.

Or, for the cost-and-token side of "where am I":

```bash
autonovel cost                      # CLI: token + cost rollup
autonovel cost --format json        # machine-readable for scripts
```

`autonovel cost` reads `.autonovel/command-log.jsonl` and rolls up
per-book / per-tier / per-command totals. Token counts and USD
costs are LLM-self-reported (whatever the runtime's session-usage
report exposes) — treat them as estimates, not invoices. Mechanical-
only commands (no LLM call) count as $0 runs and are surfaced
separately from heavy / standard / light tiers. The postamble
forwards usage automatically when the runtime reports it; the
fields are best-effort, so partial data degrades cleanly.

Or in your status bar (if you ran `autonovel statusline-setup`):

```
medieval-king-maker · drafting · ch03 · idle  │  sonnet-4-6 · 12% · $0.42
```

These are your three sources of truth. They never disagree.

---

## 4. Is there a web console / GUI?

**Today: no.** autonovel is CLI + the runtime's chat UI. Status
visibility lives in:

- `autonovel status` — full report (phase, scores, lock, log tail).
- `autonovel statusline` — one-line summary in the runtime's status
  bar (after `autonovel statusline-setup`). Updates only when Claude
  Code re-renders the bar, which it does on user input — not on a
  timer. During a long sweep the chapter count therefore *appears*
  frozen between prompts; the bar tags the active command name as
  `◍ <command>` while the lock is held so you can tell what's
  actually running. If the context-percentage half is missing on
  your Claude Code version (the JSON schema has changed across
  releases), enable a one-shot diagnostic dump: set
  `AUTONOVEL_STATUSLINE_DEBUG=1` in your shell, hit Enter once
  inside Claude Code, then read
  `~/.autonovel-statusline-debug.log` — it captures the raw stdin
  payload Claude Code is sending so a missing schema path can be
  added.
- `cat .autonovel/command-log.jsonl` — append-only log of every
  command that ran, with timestamps and write-paths.
- `git log --oneline` — every successful command's
  preamble/postamble takes a checkpoint, so the git history is the
  paper trail for the project.

For the *book* rather than the pipeline, `/autonovel:story-map
--book <name>` writes a self-contained HTML page
(`books/<name>/edit_logs/story_map.html`) you open in any browser:
the synopsis in reading order, the plot-thread grid with the
score / tension curve under it, characters, timeline and places.
It is a static file — re-run the command after revising to redraw
it.

If you remember NousResearch's earlier autonovel having a richer
read-only console (file artifact browser + live progress), that
piece did not port to this rewrite — autonovel here is the
markdown-commands-into-AI-CLI architecture; the runtime's chat is
the user surface. A read-only TUI / web dashboard for "what's the
state of every book in every series" is in
[`FUTURE-TODOS.md`](../FUTURE-TODOS.md) as a near-term item but
not yet implemented.

---

## 5. Installing PDF / ePub / audiobook tools

The autonovel package itself doesn't include the typesetting,
SVG-vectorisation, or audio-conversion tools — those are
language-agnostic OS-level binaries you install via your package
manager. Default installs (npm / pipx) bring nothing in this
section; you add only what you need.

`autonovel doctor` reports anything missing as a **warning** (not
an error). You can drift through drafting and revision without any
of these. Install only what you need, when you need it.

### 5a. PDF typesetting (`/autonovel:typeset`)

Required: **`tectonic`** (TeX engine that auto-fetches packages).
Optional: **`rsvg-convert`** (for vector ornaments at print quality).

```bash
# Linux / WSL Ubuntu / Chromebook Linux container:
sudo apt update
sudo apt install -y librsvg2-bin
# tectonic — try apt first; if doctor still flags it, see below.
sudo apt install -y tectonic

# macOS (with Homebrew):
brew install tectonic librsvg

# Verify:
tectonic --version          # should print the version
rsvg-convert --version
```

**Chromebook / Debian — when apt's `tectonic` doesn't work:**
Author testing 2026-04-25 hit the case where the Debian apt
`tectonic` package was either missing on the user's channel or
too old for autonovel's templates (the failure mode looks like
"needs a static-library compiled version"). If `tectonic` is
absent or `autonovel doctor` keeps complaining, grab the
prebuilt static binary from the official quick-install:

  <https://tectonic-typesetting.github.io/book/latest/installation/index.html>

The Linux instructions there drop one self-contained binary into
`~/.local/bin/`. No Rust toolchain or system libraries needed.
Re-run `tectonic --version` and `autonovel doctor` to confirm.

### 5b. ePub generation (`/autonovel:typeset --epub-only`)

Required: **`pandoc`** (universal document converter).

```bash
# Linux / WSL Ubuntu / Chromebook:
sudo apt install -y pandoc

# macOS:
brew install pandoc

# Verify:
pandoc --version
```

### 5c. Cover and ornament rendering (`/autonovel:cover-*`, `/autonovel:art-vectorize`)

**Three paths to a cover, ranked by cost:**

1. **Free, no key, instant — typographic-only** (NYRB Classics
   shape: title + author on a solid color):
   ```text
   /autonovel:cover-print --book <name> --pages <N> --typographic-only [--bg-color "#1a3b5c"]
   ```
   No image-API key needed; no Stable Diffusion install; no
   Pollinations rate-limits. Pillow + system fonts only. The
   right choice if you don't have or don't want to pay for an
   image API.
2. **Free, no key, AI-generated — Pollinations.ai**:
   ```text
   /autonovel:art-directions --book <name> --surface cover
   /autonovel:art-curate --book <name> --surface cover --provider pollinations
   /autonovel:art-pick --book <name> --surface cover --variant N
   /autonovel:cover-composite --book <name>
   /autonovel:cover-print --book <name> --pages <N>
   ```
   Pollinations.ai is an open HTTPS endpoint (no signup, no
   key). Quality is roughly SDXL-level; varies per request.
   Subject to rate limits (a handful of requests per minute);
   fine for one cover, slow for 24 chapter ornaments.
3. **Paid, key required — fal / replicate / openai**: same flow
   as (2) but `--provider fal` / `replicate` / `openai` and the
   corresponding `FAL_KEY` / `REPLICATE_API_TOKEN` /
   `OPENAI_API_KEY` env var. More consistent quality, no
   rate-limit anxiety, costs money.

**Provider precedence:** `--provider <X>` flag (per-call) wins
over `project.yaml :: image.provider` (per-series default), which
wins over the repo-wide default `pollinations`. Set
`image.provider: fal` (or whatever) in `project.yaml` to make
that provider the default for every art-* command without typing
`--provider` each time. The `autonovel mechanical
resolve-image-provider` helper applies this rule and is what the
slash-commands invoke; you can run it yourself to see what
provider any given series resolves to.

Required for any path: **`fontconfig`** (font lookup),
**`potrace`** (PNG → SVG, only if vectorising ornaments). Plus
the Python `Pillow` package (in the autonovel `[export]` extra).

```bash
# Linux / WSL / Chromebook:
sudo apt install -y fontconfig potrace

# macOS:
brew install fontconfig potrace

# Python image library (one-time, only if you ran the bare
# `pipx install .` rather than `pipx install '.[export]'`):
pipx inject autonovel Pillow
```

EB Garamond and Bebas Neue are the cover fonts the templates
reference. Install them too:

```bash
# Linux / WSL / Chromebook:
sudo apt install -y fonts-ebgaramond fonts-bebas-neue

# macOS (download manually from Google Fonts):
# Open https://fonts.google.com/specimen/EB+Garamond → Download
# Open https://fonts.google.com/specimen/Bebas+Neue → Download
# Double-click each .ttf to install.
```

**Pre-flight font check.** `autonovel doctor` runs `fc-match`
against every font the typeset template references (currently
just `EB Garamond` for chapter prose) and warns when one isn't
installed. The warning includes the exact install command for
your OS. This catches the case where `tectonic` would otherwise
walk fontspec's noisy "stepping through fonts by name" fallback
chain before failing mid-build — you see "install
`fonts-ebgaramond`" up front instead of debugging tectonic's
output. The typeset template ALSO has a runtime fallback
(EB Garamond → system Garamond → TeX Gyre Pagella) so a missing
font produces a still-readable PDF with a `*** WARNING:` line
naming the install command rather than a build failure. Either
way: run `autonovel doctor` after installing fonts to confirm
fontconfig sees them.

#### 5c.1. The 10 art commands, explained

There are 10 `/autonovel:art-*` and `/autonovel:cover-*` commands.
The names obscure what they do; here's the map.

**Surfaces** — every art command takes a `--surface` flag picking
which artwork it works on:

- `cover` — the front cover image
- `ornament` — small decorative images (chapter-opening flourishes,
  scene-break dividers)
- `map` — book's geography (one image per book)
- `scene-break` — the dingbat / divider between scenes within a chapter

**The full pipeline (cover example):**

```text
                                                            ┌────────────────┐
                                                            │ visual_style   │
                                                            │   .json        │
                                                            └───────┬────────┘
                                                                    │
                                ┌───────────────────────────────────┘
                                │
1.  /autonovel:art-style ───────┘  derive visual style from world + voice
                                   (one-time per book; sets palette / register)

2.  /autonovel:art-directions    generate N (default 5) radically different
        --surface cover          prompt directions for the surface
                                   (writes books/<book>/art/directions/cover.json)

3.  /autonovel:art-curate        run each direction through the image provider
        --surface cover           (pollinations | fal | replicate | openai)
        --provider pollinations  → books/<book>/art/variants/cover_01.png … _05.png

4.  /autonovel:art-pick          you pick one as the final
        --surface cover
        --variant 3              → books/<book>/art/cover.png (canonical)

5.  /autonovel:cover-composite   overlay title + author + subtitle text on
                                   the picked image
                                  → books/<book>/art/cover_titled.png

6.  /autonovel:cover-print       compose the print-ready wraparound (front +
        --pages 320               spine + back) + KDP/Lulu/Kindle thumbnails
                                  → books/<book>/art/cover_print.png +
                                    books/<book>/art/thumbnails/*.png
```

**Per-chapter ornaments** — same flow, two added steps:

```text
1-2. art-style + art-directions  (or skip 2 and use art-prompts instead)

2'. /autonovel:art-prompts       one prompt .md per chapter, derived from
        --surface ornament        the chapter's outline + summary so each
                                   ornament references chapter content
                                   (a bell for a bell-chapter, a key for a
                                   lock-chapter)

3'. /autonovel:art-ornaments-all run every chapter's prompt through the
        --provider pollinations   provider
                                  → books/<book>/art/ornament_ch{NN}.png

4'. /autonovel:art-vectorize     convert ornament PNGs → SVGs (potrace)
                                   for sharper print rendering — optional
                                   but typeset-quality.
```

**User-supplied art bypass** — when you have an existing image
(historical painting, photo, map you drew):

```text
/autonovel:art-import --file ~/Downloads/painting.jpg \
    --surface plate --slug fugger-portrait \
    --caption "..." --attribution "..."
```

Skips the direction → curate → pick flow entirely. typeset weaves
imported plates into the manuscript at the placement the user
configures (`before-chapter N`, `chapter-start N`, `after-chapter N`).

**Three free paths to a cover (no API key needed):**

1. **Typographic-only** — no AI art at all:
   ```text
   /autonovel:cover-print --book <name> --pages <N> --typographic-only --bg-color "#1a3b5c"
   ```
   Title + author over solid color via Pillow. NYRB Classics shape.
   Skips steps 1-5 entirely.
2. **Pollinations** — free AI art (rate-limited):
   ```text
   /autonovel:art-style --book <name>
   /autonovel:art-directions --book <name> --surface cover
   /autonovel:art-curate --book <name> --surface cover --provider pollinations
   /autonovel:art-pick --book <name> --surface cover --variant 2
   /autonovel:cover-composite --book <name>
   /autonovel:cover-print --book <name> --pages <N>
   ```
3. **Wikimedia Commons (public-domain art)** — perfect for
   historical fiction (FUTURE-TODOS — local SD and Wikimedia
   provider are queued).

**Paid paths (more consistent quality, costs money):** swap
`--provider pollinations` for `--provider fal` (needs `FAL_KEY`)
or `replicate` (needs `REPLICATE_API_TOKEN`) or `openai` (needs
`OPENAI_API_KEY`). Alternatively set `image.provider: <X>` in
`project.yaml` to make a paid provider the default for the whole
series — `--provider` then only needs to appear when you want a
one-off override.

**The 10-command summary** (one line each):

| Command | What it does |
|---|---|
| `/autonovel:art-style` | Derive visual style from world + voice (run once per book) |
| `/autonovel:art-directions` | Generate N radically different prompt directions for one surface |
| `/autonovel:art-curate` | Run the directions through the image provider, save PNG variants |
| `/autonovel:art-pick` | Select one variant as the final art for a surface |
| `/autonovel:art-prompts` | Per-chapter authored prompts (richer than --directions for ornaments) |
| `/autonovel:art-ornaments-all` | Generate every chapter's ornament from its prompt |
| `/autonovel:art-import` | Import a user-supplied image (painting, map, photo) — skips the AI flow |
| `/autonovel:art-vectorize` | Convert ornament PNGs → SVGs for sharper print rendering |
| `/autonovel:cover-composite` | Overlay title + author text on the picked cover art |
| `/autonovel:cover-print` | Compose the wraparound (front + spine + back) + thumbnails |

### 5d. Audiobook generation (`/autonovel:audiobook-*`)

Required: **`ffmpeg`** (audio assembly + m4b output). Plus the
Python `pydub` package and an ElevenLabs API key
(`ELEVENLABS_API_KEY` in `.env`).

```bash
# Linux / WSL / Chromebook:
sudo apt install -y ffmpeg

# macOS:
brew install ffmpeg

# Python audio library (one-time, only if you ran the bare
# `pipx install .` rather than `pipx install '.[export]'`):
pipx inject autonovel pydub

# ElevenLabs key — paste into <series-root>/.env
echo 'ELEVENLABS_API_KEY=sk_...' >> .env

# Verify:
ffmpeg -version
```

### 5e. All-at-once for the impatient

```bash
# Linux / WSL / Chromebook (one shot):
sudo apt update && sudo apt install -y pandoc potrace ffmpeg \
    librsvg2-bin fontconfig fonts-ebgaramond fonts-bebas-neue
sudo apt install -y tectonic   # may fail or be too old; if so, see §5a fallback
pipx inject autonovel Pillow pydub  # skip if you already used `pipx install '.[export]'`

# macOS (one shot):
brew install tectonic pandoc potrace ffmpeg librsvg fontconfig
pipx inject autonovel Pillow pydub  # skip if you already used `pipx install '.[export]'`
# (then download EB Garamond + Bebas Neue from Google Fonts manually)
```

After install, verify:

```bash
autonovel doctor
```

The export-tools section should now report no warnings for the
tools you just installed.

### 5f. None of this for "just write the book" mode

If you only want to draft and revise — no PDF, no cover, no
audiobook — you don't need any of section 5. autonovel is fully
usable on a fresh pipx install for the entire writing pipeline up
to and including `/autonovel:reader-panel` and
`/autonovel:review`. Export tools are a separate decision you make
when you're ready to publish.

---

## See also

- [`README.md`](../README.md) — install + quickstart.
- [`docs/commands.md`](commands.md) — every `/autonovel:*` command.
- [`docs/multi-book.md`](multi-book.md) — coordinating books in one series.
- [`docs/writing-a-historical-series.md`](writing-a-historical-series.md) — 12-step end-to-end on a Renaissance series.
- [`docs/troubleshooting.md`](troubleshooting.md) — common errors and fixes.
- [`docs/lessons-from-author-testing.md`](lessons-from-author-testing.md) — defensive code rationale: why certain decisions were made.
