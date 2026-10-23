# Future todos

Items that are out of PR-9 scope but worth recording so a future
session can pick them up. Companion to `ROADMAP.md` (PR sequence),
`STATE.md` (decisions log), and `docs/lessons-from-author-testing.md`
(narrative explanation of *why* certain defensive shapes exist).

The list is rough on purpose — each entry is a one-line reminder, not
a spec. Promote to `ROADMAP.md` (or a fresh PR plan) when one is ready
to start.

## Near-term — pull into the next PR

- **Historical fiction is not defined as a genre: what the reader comes
  for is missing, so the feedback loop pushes to cut it (opened
  2026-10-23, author).** The author: "some of the interest of historical
  fiction is learning a bit of history, so some real events and people,
  also what life was like during the past, how people worked, lived, saw
  the world. I also delight in seeing places today (Venice) that still
  [have] buildings (St Mark's for example) and names and places that were
  there in the 1500s." On kingmaker2 the cold first readers reported
  history paragraphs as "skimmed" ("the Frankfurt guidebook paragraph",
  "a lecture"), the judge listed glosses among the three weakest
  sentences and marked prose down for them, and the editor's summary
  echoed it as "fewer explanation paragraphs". What exists is scattered:
  DESIGN §12 ("the answer is not less of the place but the place
  walked"), §13a terms, §14's thriller list with one line "the period
  made concrete", FIRST-READER's one sentence on skimming. Nothing
  defines the genre's promise as a whole, and the reader and judge who
  drive revision don't hold it. Proposed:
  1. A craft section (DESIGN §14 or a new `HISTORICAL-FICTION.md`)
     defining the promise: real events and people, met on the page; daily
     life (work, money, travel, food, faith, medicine, law, how news
     moved); how people saw the world; places, especially those still
     standing, under their names of the time; the past's difference. How
     it is delivered well (through a person, at pressure, a clause at
     first use, set pieces), and the rule: a skimmed history passage is
     moved or dramatized, never just cut.
  2. `design` writes a `## What the reader comes to learn` ledger (events,
     people, daily life, surviving places) with the chapter that delivers
     each, checked like plants; the genre contract gains it.
  3. FIRST-READER for a historical book: a reader of historical fiction
     who knows nothing about this period and reads partly to learn it; the
     report adds "What did you learn about the period that you enjoyed?"
     and splits Skimmed into "stopped the story here" from "didn't want
     this at all".
  4. `evaluate` gains a `history` dimension (the period delivered: real
     people and events on the page, daily life, places, accuracy), and the
     prose judge stops counting a gloss as weak prose for being a gloss.
  5. `adversarial-edit` / `apply-cuts`: OVER-EXPLAIN never cuts period
     content; such candidates become "move or dramatize".
  6. `appendix --sections places`: "Places you can still see", the
     buildings and streets in the book that stand today.
  Doc-sync: commands, docs, README, templates/series/CLAUDE.md, help.

- **Structural layer: scene ledger and cross-chapter checks (opened
  2026-10-14).** The kingmaker panel + review found faults no per-chapter
  eval sees: a clock paid offstage, a pivot told in pluperfect, the same
  announced-want opener in every scene, confrontations in indirect speech.
  Shipped the same night: `brief --from review` + `## Structural findings`;
  `evaluate` `clocks_paid` (foundation + full); PROSE §5.8/§5.9/§6.5 and
  CRAFT §4 rule 3; consumers follow `review.md`. **Still open:** (1) a
  per-chapter *scene ledger* surface (Story Grid / Bickham style: one row
  per scene — goal, opposition, outcome, value shift, on-page vs reported,
  clock set / paid) emitted by `evaluate --chapter` under `beat_coverage`
  and compared with the outline beat, so "the pivot is a report" is a
  scored row, not a panel discovery; (2) an opener-device repetition check
  across chapters (same sentence shape opening consecutive scenes or
  chapters: "What X wanted was…", "X was Y when Z") — a candidate list for
  the judge, not a word list; (3) `evaluate --chapter` should read the
  previous chapter's *closing* (not just its summary) so an open clock is
  visible to the per-chapter judge; (4) `reader-panel` and `review` don't
  read `shared/craft/` and so judge against their own idea of craft;
  (5) `revision-pass` should print which panel/review items each brief
  consumed so the user can see the editorial letter being worked through;
  (6) the review parser keys items to chapters by "Ch N" text — fine for
  now, brittle if a reviewer writes "chapter five".
  (7) **False stale-summary hints after every sweep (seen 3× on
  2026-10-15).** The per-chapter worker writes `ch_NN.summary.md`, then the
  evaluate step rewrites the chapter's frontmatter (`word_count`, `status`),
  so the chapter's mtime ends up newer than its summary and `next` /
  the postamble hint say "regenerate stale chapter summaries" for every
  chapter just revised. Either have revise/draft write the summary as the
  very last step (after evaluate), or make the staleness check compare the
  chapter's *body* hash recorded in the summary frontmatter instead of
  mtimes. Workaround used: `touch` the summaries after the sweep.

- **Craft docs reach the writer; sourced PROSE.md (shipped 2026-10-14).**
  Root cause of "we are making up how to write prose on the fly": CRAFT.md /
  ANTI-SLOP.md / ANTI-PATTERNS.md lived only at the repo root, commands named
  them with no path, nothing installed them, the series CLAUDE.md never
  mentioned them — a series session drafted from `voice.md` alone. Now the
  four docs are a series template subtree (`shared/craft/`; repo-root files
  are symlinks), `new-series` copies them, `refresh-templates` default
  includes them, `doctor` warns when missing/stale, draft/revise/evaluate read
  them by series path and self-heal. `PROSE.md` is new: register-neutral
  mechanics with every rule traced (Williams known-new; Le Guin; Gardner /
  Darwin psychic distance; Swain / Bickham / McKee scene chain; Stein /
  Browne & King / Leonard dialogue; Darwin / Harris information) plus a
  folklore list (§9) and a judge checklist (§10). Later the same day:
  `autonovel mechanical register` (narration/dialogue split, FK each,
  contraction ratio, formal connectives, utterance length,
  listener-explaining candidates), the `register` copy-editor dimension in
  `evaluate` with `register_edits` → brief `## Register edits` → revise line
  edits, draft/revise self-check, `FK grade band:` in voice.md as the
  syntax-drift baseline. **Still open:** (1) other commands that touch prose
  (reader-panel, review, adversarial-edit, lengthen, shorten,
  deepen-character, revoice) still don't read `shared/craft/` or run the
  register scanner; (2) `voice-discovery --upgrade` should strip a voice
  file's home-made mechanics rules that PROSE.md now covers and leave
  register + calibration, and add the `FK grade band` line to existing
  books; (3) paragraph-shape markers (unjoined openers, connective share,
  dialogue-paragraph share and runs) are still a scratch script; fold them
  into the register scanner or a sibling; (4) the eight
  `tests/fixtures/tiny-series-*` have no `shared/craft/` (commands self-heal,
  but smoke runs will each do a refresh); (5) the register-specific
  CRAFT.md §5–6 could shrink now that PROSE.md holds the mechanics; (6) the
  dashboard has no row for the `register` dimension or the scanner's
  numbers; (7) a numeric target in a voice file gets gamed by the writer
  (dialogue ≥30% of words produced exposition in mouths): voice templates
  should prefer bands and "look at" thresholds over floors, and the
  evaluate rubric should say so; (8) the register scanner's
  listener-explaining phrase list catches only the blatant form ("at the
  end there"); the copy-editor judge found 6–7 per chapter where the
  scanner found 0–2, so the scanner is a reminder, not the detector — fine,
  but say so in its header; (9) moving speeches into narration predictably
  pushes narration sentences over a book's length ceiling (11 in ch 1): add
  a `--max-sentence N` report of narration sentences over N to the register
  scanner so revise can catch its own side-effect.

- **Book-scoped canon + isolated context — rewrite support (shipped
  2026-10-12).** Pre-work for a second version of the Fugger novel in the
  same series. (1) **Canon is book-scoped**: `books/<book>/canon.md` (new
  template file + `BookLayout.canon_file`) holds the facts a book's prose
  fixed; `shared/canon.md` keeps series-wide facts. `promote_canon.py`
  routes chapter-derived → book, research-cited → shared (`--scope`
  override), classifies against shared + the book's OWN canon only, and
  writes `## Superseded` blocks into whichever file held the old line.
  `context_loader`, draft/revise/evaluate/+15 command bodies, impact-of,
  entity-track, doctor, TUI read both. (2) `autonovel canon-partition` +
  `/autonovel:canon-partition` migrate an old series (provenance-tagged
  bullets move mechanically; the LLM classifies untagged leftovers via
  `--move-key` / `--move-section`). (3) `project.yaml books[].context:
  isolated` (`new-book --isolated`) — the loader withholds every sibling
  chapter; `draft.md` step 9 honours it. (4) `evaluate --compare N,M
  --vs-book <other>` cross-book head-to-head; `series-arc` exempts the
  clock reset between books with overlapping `story_time_range`s. (5)
  Hygiene: `status` infers phase from disk (a drafted book no longer
  shows `seed`); `.autonovel/session-notes/.gitkeep` + `_begin`
  self-heal (doctor PROBLEM on cloned series). `/autonovel:help rewrite`.
  Tier 1+2 1875 → 1908. **Still open:** `gen-canon` routing is
  LLM-judged (no mechanical check that a book-canon bullet isn't plain
  history); a `--vs-book` eval log has no dashboard surface yet; the
  repo's default model pins are still the 4.x family.

- **Teaser VO synthesis + book concreteness review (shipped 2026-06-09).**
  Two follow-ups from the Phase-13 short. (1) **Free VO/TTS** — new
  `teaser/vo.py` + `teaser-vo` CLI synthesizes the voiceover spine: `stub`
  (offline silent $0) / **`edge`** (free Microsoft Edge TTS, **no key** — the
  easy default) / `elevenlabs` (paid, reuses the audiobook account); wired
  into `teaser-assemble --narration` (laid over the cut as the primary voice;
  a music bed ducks under it via sidechain). (2) **"Concrete, not cryptic"
  carried to the BOOK pipeline** — new `vagueness` mechanical scanner (a
  candidate generator like show-dont-tell: filler nouns, empty intensifiers/
  evaluatives, hedges) + `/autonovel:vagueness` + a **`concreteness` lens in
  `/autonovel:evaluate`** (classifies each vague candidate vague-vs-earned)
  + ANTI-SLOP.md "vagueness is slop" section. Tier 1+2: 1852 → 1875.
  **Still open:** the VO *quality*/timing (my Fugger lines ran ~119s vs a
  58s cut — narration must be budgeted to the cut); judging the *rendered*
  cut (vision) not the script; making the assembly cut-critique adversarial.

- **Phase 13 — the AI-video SHORT (shipped 2026-06-08).** Even with Phases
  11+12 a full Fugger run was STILL incoherent — the *shape* was wrong, not
  the script. AI video has no continuity between clips, so a 180s/30-shot
  montage can't cohere. Research → 45–60s, 6–12 shots, carried by one
  first-person **voiceover spine** (Goodfellas/Shawshank; fiction). Added a
  **`mode` knob** (`short` default | `trailer`) on ONE pipeline: `Teaser.mode`,
  `Spine.narrator`, per-shot `Shot.voiceover`; mode-aware planner (short =
  ≤12 longer shots + `voiceover_target`, warn >90s) and critique (short drops
  the `thin-dialogue` gate, adds advisory `no-narrator`/`thin-narration`/
  `too-many-shots`; the viewer-blind read counts the VO + judges spine
  cohesion). Defaults moved to 60s. teaser-craft §12; all command bodies
  thread `--mode`. Tier 1+2: 1842 → 1852. **Open follow-ups (the user
  deprioritized render quality, but these remain):** (1) **VO-audio
  synthesis** — actually generate/lay the narration track over the cut (TTS),
  like the music bed; right now the VO lines + cohesion judgement land but the
  audio isn't synthesized. (2) **Judge the rendered cut, not the script** —
  a vision pass over the assembled animatic; make the assembly cut-critique
  adversarial (it rubber-stamped the bad cut "KEEP"). (3) identity-lock /
  reference-chaining for cross-clip face consistency (render quality).

- **Phase 12 — teaser LEGIBILITY + honest grading (shipped 2026-06-08).** A
  full Fugger run on Phase 11 *still* produced a terrible teaser that
  self-scored 7–9: 9 of 23 shots were OBJECTS (a ledger, a riderless horse,
  seven wax seals), named figures had no identification, 12 text cards
  papered over it — and the quality judge graded the *script's intent* (which
  it could see) not a stranger's *experience*. Fixes: (1) **viewer-blind
  legibility gate** — `quality.json` schema /2 gains a per-shot `legibility`
  read (`clear/who/what/why`, judged from the perceivable layer ONLY — action
  + spoken line + card, names/spine/beat-notes hidden) + `viewer_takeaway` +
  `would_watch`; `passes()` now needs every scene legible + would_watch, so a
  boring/illegible teaser can't self-pass. (2) **drama over mechanism +
  identify** — `Shot.identify` lower-third (always burned by `teaser-assemble`),
  advisory `instrument-only-shot`/`unidentified-figure`, `cast-sprawl` counts
  only real people. (3) **cut the card crutch** — `thin-text-cards` removed
  from the gate, advisory `too-many-cards` added; meaning rides spoken
  dialogue + more characters. (4) **genre care** — read `project.yaml ::
  genre` and build in that idiom (historical *fiction*, not documentary, not
  generic montage). teaser-craft §11 + all command bodies updated. Tier 1+2:
  1831 → 1841. **Open follow-up:** the planning pipeline is free — regenerate
  the Fugger teaser script by hand against these rules and confirm it's
  legible before any (paid) re-render. Deeper: have the gate judge the
  *rendered clips* (vision), not just the script, and make the assembly cut
  critique adversarial too (it also marked the bad cut "KEEP").

- ~~**★ TOP PRIORITY — Teaser CONTENT QUALITY: "it's boring, nothing
  happens."**~~ **Phase 11 — ALL 8 items shipped 2026-06-08.** Added
  `teaser/quality.py` — an eight-dimension interestingness rubric
  (hook_grip, question_sharpness, stakes_escalation, character,
  dialogue_quality, surprise_turn, coherence, button) scored 1-10 by the LLM
  judge in `teaser-critique` → `teaser/quality.json`, with a **HARD quality
  gate** (overall ≥ 7 AND no dimension < 5) computed in one place
  (`teaser-quality` CLI) and enforced as a **second render gate** in
  `teaser-render` (real backends only; `stub`/`--shot`/`--skip-narrative-gate`
  exempt; `--dry-run` reports it). Spine gained `turn` (midpoint reversal),
  shots gained `character_beat` (want/cost); advisory `no-turn`/
  `no-character-arc` flags. Pacing model reworked for long runtimes
  (`movements` + length-scaled `dialogue_target` + gentler avg-shot curve).
  New `/autonovel:teaser-brief` distils treatment → `teaser/brief.md` before
  beats. `teaser-beats`/`shot-prompts` author the turn + character beats +
  scaled dialogue; `teaser-revise` lifts the weak quality dimensions + runs
  the adversarial de-boring pass (`--deboring`) and re-scores; `teaser`
  orchestrator + `/autonovel:next` are quality-gate aware. Few-shot worked
  beat-sheets + the rubric in teaser-craft §11. Maps the 8-point plan: 1
  quality gate, 2 micro-arc/turn, 3 dialogue, 4 character, 5 use-the-180s, 6
  brief, 7 few-shot, 8 de-boring. Tier 1+2: 1805 → 1831. Original plan
  follows for context.

- **★ (shipped — see above) Teaser CONTENT QUALITY: "it's boring, nothing
  happens."** Raised 2026-06-08 after a full Fugger run on the new pipeline.
  Even at 180s the teaser is *flat*: no felt plot, almost no dialogue, no
  character development, no surprise — "just a sequence of clips, that are
  also boring." **Diagnosis:** Phase 6 enforces story *structure* (a spine
  block exists, ≥N dialogue lines exist, cards exist, 4-act roles, monotonic
  `stakes_level`) — a **floor, not quality**. A teaser passes every
  mechanical gate and is still dull because nothing checks whether the
  dramatic question is *sharp*, the dialogue carries *subtext/voice*, the
  beats *actually escalate in felt stakes*, there's a *turn/reversal*, the
  hook *grips*, or the button *teases*. **Presence ≠ interesting.** The leap
  from "has a story shape" to "is a good story":
  1. **Quality rubric + a HARD quality gate (not presence).** Add an LLM
     "interestingness" judge to `teaser-critique` scoring 1–10 each on: hook
     grip (would you keep watching?), dramatic-question sharpness, stakes
     escalation (specific + felt + rising), character (do we learn who
     someone IS / wants?), dialogue quality (subtext, voice, a quotable
     line), surprise/turn (a reversal?), coherence (does it add up?), button
     (withholds + teases?). **Block the render gate on a minimum** (e.g.
     overall ≥7 AND no dimension <5), persist the scored rubric, and make
     `teaser-revise` lift the low dimensions. This makes "boring" a
     measurable, blocking failure instead of a pass.
  2. **Beat selection = a micro-arc with a TURN, not a montage.** Strengthen
     `teaser-beats`: a 180s piece is a compressed story (setup → inciting
     image → escalation with a **midpoint reversal** → crisis → button).
     Require a named turn/reversal beat; require each escalation beat to name
     the NEW thing now at stake (not "more tension"); pull the spine from the
     treatment's central conflict, not a generic question.
  3. **Dialogue that carries the story.** Select the manuscript's *best*
     lines (quotable, character-revealing, subtext-loaded), not the first
     few; budget more for 180s (≈6–10), placed at hook / turn / button; have
     the LLM pick the strongest and sharpen to trailer cadence. Thin/generic
     dialogue is the #1 felt failure.
  4. **Character in the teaser.** ≥1 beat showing the protagonist's *want*
     and ≥1 showing *cost/change* — a flicker of development, not just a
     recurring face. Add craft rule + critique check.
  5. **Use the 180s.** 35×4s clips = a montage. Fewer, longer, meaningful
     beats grouped into 3–4 movements with their own build; let key moments
     breathe. Rework the pacing model for longer runtimes.
  6. **A `treatment → teaser-brief` distillation step** (mirrors the book's
     brief): distill the sprawling treatment into the single most filmable
     through-line + the 3 must-have dramatic moments + the killer lines,
     BEFORE beats — so beats are chosen from a sharp brief, not the whole
     story.
  7. **Few-shot worked examples.** Put 1–2 *great* 3-min teaser beat-sheets
     in `teaser-craft.md` as targets to imitate — few-shot lifts LLM output
     quality more than rules alone.
  8. **Adversarial "de-boring" revise pass.** A mode that hunts the 3
     flattest beats and the flattest line and replaces them with the most
     dramatic moments / sharpest quotes from the story.
  **Biggest levers:** #1 (quality gate so boring = blocked), #7 (few-shot
  exemplars), #3 (real dialogue selection). Likely "Phase 11: teaser
  storytelling quality." NOTE: also re-verify the runtime install is current
  — a stale critic that "sees no problem" masks all of this (the user hit
  exactly that).

- ~~**Teaser CREATIVE/NARRATIVE quality — the teaser doesn't tell a
  story.**~~ **Phase 6 — ALL 12 best practices + script versioning shipped
  2026-06-06.** The teaser data model gained a `spine` (dramatic question,
  logline, want, opposing force, emotional arc, score direction, genre —
  omitted when empty so old teasers round-trip unchanged) and a per-shot
  `stakes_level`. `teaser-beats` authors the spine + a 4-act, rising-ladder
  beat order; `shot-prompts` copies the spine in, mines 3–6 loaded dialogue
  lines, authors 2–4 premise text cards, sets `stakes_level`, and enforces
  4-act order / restraint / one-hero. `teaser-critique` (mechanical + LLM)
  gained the story-spine flags (`no-dramatic-question`/`no-logline`/
  `no-stakes`/`no-emotional-arc`/`no-genre`/`thin-dialogue`/
  `thin-text-cards`), 4-act flags (`hook-not-first`/`multiple-hooks`/
  `no-title`/`button-not-last`/`title-after-button`), stakes-ladder flags
  (`no-stakes-ladder`/`stakes-not-rising`), and `cast-sprawl`, and judges
  the story first. **bp 12 render gate:** `teaser-render` *refuses* a real
  generation (exit 3) while any story-spine flag is present (`stub` +
  single-`--shot` exempt; `--skip-narrative-gate` overrides) — quota can't
  be burned on a meaningless teaser. **Script versioning:**
  `teaser-archive-script` + the `--force` path version `beats.md`/
  `teaser.json` into `teaser/script-takes/` so a full re-run never loses a
  prior script while reusing the `refs/` originals. 26 tests. Tier 1+2:
  1706 → 1732. Maps: bp1 question, bp2 4-act order, bp3 stakes ladder, bp4
  want/force, bp5 dialogue mining, bp6 text cards, bp7 withhold, bp8
  emotional arc + score, bp9 genre, bp10 restraint, bp11 one hero face,
  bp12 render gate. Original entry follows for context.

  Surfaced 2026-06-06 from the first real Fugger render. Diagnosis: *"it
  didn't go anywhere and didn't seem to mean anything; there wasn't enough
  dialogue to know anything about the story, or any intrigue — it wasn't a
  teaser, it was a set of short clips with the same characters set
  when/where they are."* The render *mechanics* now work; the **generative
  craft** is the gap. The craft is already documented in
  `docs/teaser-craft.md` (§7/§8) but `teaser-beats`/`shot-prompts` don't
  *enforce* it — they select visually-distinct snapshots, not a rising arc,
  and emit almost no dialogue. Encode + enforce these best practices
  (researched 2026-06-06; sources in the session log — StudioBinder, Derek
  Lieu, FriesenPress, Reedsy, MasterClass):
  1. **One dramatic question / throughline.** `teaser-beats` must first
     pick the *single* question the teaser poses and never answers, then
     every beat must advance or complicate it. Reject a beat-sheet that is
     a "tour" of scenes with no causal spine. (This is the root fix for
     "didn't go anywhere.")
  2. **Enforce the 4-act trailer shape with labelled, timecoded roles.**
     Each beat carries a role: `cold-hook` (0–10s) → `premise` (10–30s) →
     `escalation` (30–60s, accelerating) → `title` (~⅔) → `button` (final
     5–10s). `teaser-beats` output is structured by role, not a flat list;
     `teaser-critique` checks every role is present.
  3. **Causal stakes ladder.** Beat N's stakes must exceed beat N-1's
     (cost / danger / irreversibility rising). Add a stakes-ladder check —
     a teaser is escalation, not a montage of equals.
  4. **A stated want + an antagonistic force.** Surface what the
     protagonist wants and what stands in the way; no conflict → no
     intrigue. Pull these from the treatment/canon, not invented.
  5. **Dialogue as narrative payload, not ambience.** Budget **3–6 short,
     loaded lines** that reveal stakes/relationship/genre — *adapted from
     the manuscript's best "trailer-worthy" lines*, not generic chatter.
     This is the direct fix for "not enough dialogue to know anything."
     `shot-prompts` should mine the chapters for the highest-voltage lines.
  6. **Curated text cards carry the logline cheaply.** 2–4 cards delivering
     the premise/question ("In a city built on debt…" → "one ledger could
     burn it down"), dodging AI lipsync — already a craft default, make it
     a required output with model-written card copy.
  7. **Withhold the answer; end on a button.** Never resolve. End on the
     unanswered question or a stinger *after* the title that deepens it.
  8. **Tonal/emotional spine.** One emotional arc; cuts accelerate into a
     title drop; hold the final image. Pick a trailerised score shape
     (ties into the `--score`/music work).
  9. **Genre signal in the first 10s.** The hook must telegraph genre +
     tone so the viewer knows what *kind* of story this is.
  10. **Restraint — scope without context.** Striking fragments that imply
      a larger world; cut anything that is merely "characters standing
      where/when they are." Do more with less.
  11. **One hero face, clear want.** Anchor on a single protagonist's
      stakes so the viewer cares (craft §7 already says this; enforce it
      in beat selection — demote multi-protagonist sprawl).
  12. **Narrative self-critique BEFORE render (new gate).** `teaser-critique`
      today is a mechanical/shot-prompt linter. Add a **viewer-panel
      narrative pass on the beat-sheet** that scores: does it pose a
      question? escalate? state a stake? does dialogue reveal character?
      does the button withhold? — with a hard gate so a flat "set of
      clips" can't reach the (costly) render step. This is the single
      highest-leverage change.
  **Where it lands:** `commands/teaser-beats.md` (1–4, 6, 10, 11),
  `commands/shot-prompts.md` (5 dialogue mining, 7 button, 9 hook),
  `commands/teaser-critique.md` (12 narrative gate + role/ladder checks),
  `docs/teaser-craft.md` (fold the researched best-practices in as prompt
  material). Keep additive + regression-gated. Likely a "Phase 6: teaser
  storytelling" plan. Pairs with the music/score work (8).

- **Longer-term: apply the same best-practice *encoding* rigor to the
  novel prose/script generation.** Raised 2026-06-06 alongside the teaser
  craft gap: *"add a longer-term todo to improve the script writing in a
  similar fashion."* The teaser fix above is a template — research the
  external craft, distil concrete best practices, then **encode AND
  enforce** them in the generating commands (not just document them).
  Apply the same treatment to the book pipeline: audit `draft`/`revise`/
  `brief`/`evaluate` against current best practice for scene construction
  (goal→conflict→disaster / reaction→dilemma→decision scene-sequel
  structure), dramatic-question-per-chapter, stakes escalation across the
  arc, dialogue subtext, withholding/reveal cadence, and POV discipline —
  beyond the existing rubric in `CRAFT.md`/`voice.md` Part 3. The pattern:
  (a) web-research the craft, (b) add concrete checks to the LLM judge in
  `evaluate`/`reader-panel` (not brittle Python — see
  feedback_avoid_brittle_python), (c) feed the findings forward through
  `brief`→`revise`. The teaser work proves the shape; generalise it.

- ~~**Version every render/mp4 as a distinct take (never overwrite).**~~
  **Shipped 2026-06-06 (Phase 5.8).** New `teaser/takes.py`: each render is
  archived to `clips/takes/shot_<id>_take<N>.<ext>` (monotonic, never
  overwritten) while `shot_<id>.<ext>` stays the "latest" pointer;
  `teaser-takes` lists them, `teaser-take-pick --shot --take` promotes an
  earlier one back to latest. `teaser-ffmpeg-cmd --versioned` timestamps
  the assembled mp4 (`<title>_teaser_<UTC>.mp4`) + a `_latest` pointer the
  command body copies to. `--no-archive` opts out. Reuses the
  `typeset-filename` timestamp/latest pattern.

- ~~**Scene transitions between teaser scenes.**~~ **Shipped 2026-06-06
  (Phase 5.7).** `CutEntry` gained `transition` (cut|fade|dissolve) +
  `fade_out` + `transition_dur`; `ffmpeg_command` emits concat-compatible
  fade-in/out; `build_cut_list` auto-defaults open→fade-in, close→fade-out,
  title→fade; `suggest_transitions` (+ `teaser-transitions` CLI) flags
  candidates from structured signals (story_year jumps, location changes,
  pace shifts) — advisory, the LLM places them. **Remaining (5.7b):** a
  true **cross-dissolve** needs the `xfade` overlap rework (overlapping
  clips with cumulative offsets + audio acrossfade); `dissolve` currently
  degrades to a fade-in.

- ~~**Music GENERATION (not just a bed).**~~ **Phase 9 shipped 2026-06-06.**
  New `teaser/music.py` + `teaser-music` CLI generates one cohesive bed from
  a prompt (default = the spine's `score_direction`, tying into Phase 6):
  `stub` (offline silent WAV via stdlib `wave` — $0 chain test), `musicgen`
  (HF Inference, free `HF_TOKEN`), `elevenlabs` (`ELEVENLABS_API_KEY`),
  reusing the backends key-resolution + injectable-client seam + typed
  `RenderError`. Versioned output `teaser/music/<title>_bed_<UTC>.<ext>` +
  `_latest`. Also added the per-shot `audio.music` prompt line (emitted only
  on the `--score native` path — one-off cues; the bed carries the music on
  the `bed`/`none` paths). 9 tests (test_teaser_phase9). Tier 1+2 1753 →
  1762. Wired into teaser-assemble's music section + providers doc.
  **Remaining:** auto-duration the bed to the cut length; more providers.

- ~~**Series/book directory nesting is confusing (clean up soon).**~~
  **Phase 10 shipped 2026-06-06.** The layout is structurally correct
  (`<series>/books/<book>/`); the confusion is series-name == book-name
  rendering as `…/<name>/books/<name>/`. `paths.looks_doubled` +
  `nesting_note` describe it; `autonovel doctor` now WARNS on a name
  collision and flags a *real* `books/books/` level as a PROBLEM;
  `autonovel new-book` prints the note when the new book matches the series
  name; the series-template CLAUDE.md documents the layout prominently
  (repeated name = correct, not a bug). Audited paths.py / new-series /
  new-book / teaser out_dir defaults — none write a second `books/` level.
  5 tests (test_directory_nesting). Tier 1+2 1762 → 1767. **Remaining
  (optional):** a `new-series --with-book` that picks a distinct default
  book name. Original entry follows for context.

- **Series/book directory nesting is confusing (clean up soon).**
  Reported 2026-06-06. On the Fugger book the clips land at
  `~/books/medieval-king-maker/books/medieval-king-maker/teaser/clips/`
  — the series root and the book share the name `medieval-king-maker`,
  so the autonovel layout (`<series>/books/<book>/…`) reads as a doubled
  path. It is structurally correct (a series *contains* `books/<name>/`)
  but looks broken when series-name == book-name, and the absolute path
  is needlessly deep. **Action:** investigate — (a) when a series has a
  single book whose name == series name, consider flattening or a
  clearer default book name in `new-series`; (b) document the
  `<series>/books/<book>/` layout prominently so it's not mistaken for a
  bug; (c) sanity-check that no command writes a *second* `books/` level
  by mistake. Audit `paths.py` + `new-series` scaffolding + the teaser
  `out_dir` defaults.

- ~~**Flip the install default to NO model pin.**~~ **Shipped
  2026-06-06.** `pin_model` now defaults to **False** across
  `claude_code.render`, `installer.install`, and `cli.py`; `autonovel
  install` omits the `model:` field so the session model wins (no more
  `[1m]` downshift). `--pin-model` is the explicit opt-in for per-tier
  pinning; `--no-model-pin` kept as a deprecated no-op. Tests
  (`test_adapter.py`) + `docs/troubleshooting.md` re-pointed.

- ~~**Pollinations free image endpoint returns `402 Payment Required`;
  add a free video backend.**~~ **Shipped 2026-06-06 (Phase 4 render
  backends).** Pollinations is now images-only with a free-token path
  (`POLLINATIONS_TOKEN` → `Authorization: Bearer`) and **early-402
  detection** (one actionable message, not 35 identical failures). Real
  free *video* now comes from new backends: **`grok`** (default — native
  dialogue+music, 5 free/day + $25, no card), `kie`, `veo`, `magichour`,
  `fal`, and manual `flow`, plus an offline **`stub`** backend to
  validate the pipeline for $0. See `docs/teaser-render-providers.md`.

- ~~**Render adapter has no rate-limiting / backoff / 429 handling.**~~
  **Shipped 2026-06-06.** `teaser/backends.py::RateLimiter` paces calls
  ≥ the provider's `min_interval_s` (`providers.py`), retries 429/503
  with bounded exponential backoff honouring `Retry-After`, and exposes
  `--delay` / `--max-retries` on `teaser-render`.

- **Character-reference development + approval workflow for teaser
  keyframes.** Requested 2026-06-06 (Fugger book). Today
  `teaser/refs.py` + `teaser-refs-plan` plan ONE canonical reference
  image per recurring subject and check `teaser/refs/` +
  `shared/art_references/`; `art-import` imports a user image and
  `wikimedia-{search,fetch}` pull public-domain art. What's missing is a
  deliberate, per-book **character-reference pipeline with an approval
  gate**: (a) seed a subject's reference from a real source — e.g.
  Dürer's *Portrait of Jakob Fugger* (PD via Wikimedia) for the
  protagonist, or the Matthäus Schwarz *Klaidungsbüchlein* costume
  sketches for his assistant — then image-to-image/morph it into the
  shot's framing; (b) a per-book `entities`/`character_refs` manifest of
  allowed sources + constraints (period dress, age, likeness limits);
  (c) an **approve step** (pick/lock a reference before any shot spends a
  real generation), reusing the `art-directions → art-pick` shape; (d)
  feed the locked refs as the consistency anchor to the video backends
  (grok/veo image-to-video). Keep it additive; the `stub` backend lets
  the whole flow be rehearsed for free. Likely a "Phase 5: character
  references" plan.

- **Reference-conditioned rendering — GENERALIZE the manual Fugger spike
  into the normal `autonovel:teaser` flow.** **Phase 7 shipped 2026-06-06
  (most of it).** Done: (1) **locations as first-class refs** —
  `teaser-refs --with-locations` scaffolds/tracks a `kind: location` plate
  per distinct setting (refs.py `plan_refs(include_locations=)`,
  refmanifest scaffold/status), with period-correct source guidance (the
  Rialto anachronism fix); (3) **prompt/appearance sync** — `appearance_ages`
  ladder on `CharacterRef` + `resolve_appearance(year)` +
  `_load_teaser_appearances_map` + `build_request(appearance_override=)`, so
  each shot's prompt text matches the age-correct plate by `story_year`;
  (5) **refs reach the VIDEO backends** — `_init_image` falls back to the
  shot's primary reference plate as the image-to-video start frame for
  grok/veo/kie, and declared location plates attach via the existing
  refs-map (characters first, place second). 12 tests (test_teaser_phase7).
  Tier 1+2: 1732 → 1744. **Remaining:** (2) auto-DERIVE the age windows
  from chapter dates / treatment ages (today you hand-author
  `appearance_ages`/`voice_ages`), (2b) the actual **lineage-morph** that
  makes the variant plates one face aging (interactive image-gen), and
  (4) **auto default-source suggestions** per entity type (real person →
  period portrait; real place → period painting with anachronism guards;
  invented/prop → generate) presented as approve-able defaults. Original
  entry follows for context.

- **Reference-conditioned rendering — GENERALIZE the manual Fugger spike
  into the normal `autonovel:teaser` flow.** Requested 2026-06-06 (Fugger
  book): *"this should be a general approach for videos, not just a manual
  forcing"* and *"the prompts probably need updating too to pull the right
  images/ages."* **Now built (Fugger spike, opt-in, works end-to-end):**
  `gemini` registered as a reference-conditioned **image** backend (Nano
  Banana 2 `gemini-3.1-flash-image-preview`, default; 2.5 / 3-pro
  selectable); `RenderRequest.reference_images` is multi-image; the
  gemini/fal backends attach N references; `teaser-render --refs` maps
  **shot → ordered reference list** (characters first, then locations/
  props, capped) by inverting each refs.yaml entity's `shots`; refs.yaml
  entities gained `kind` (character|location|prop) + `shots` + an approval
  gate; `--film-style` swaps the book's engraving style for a photoreal
  film look without mutating teaser.json. Proven: faces hold across scenes;
  Carpaccio's *wooden* Rialto plate fixes the 1591-stone-bridge anachronism;
  shot 01b carries boy-portrait + Venice plate (true multi-ref); a Jakob
  **age ladder** (boy 14 → youth 18 → man ~40 → elder ~62, lineage-morphed
  so it's one face aging) is tagged per shot. **All of that is currently
  HAND-FORCED** (manually editing refs.yaml, hand-running a lineage script,
  hand-writing each variant's `shots:`). To make it the *normal* automated
  flow:
  1. **Auto-extract entities** in `teaser-refs --init`: scaffold not just
     character subjects but **locations** (distinct `setting`s) and
     recurring **props** as first-class entities, each listing its shots.
  2. **Character age-ladder, auto.** A recurring character spans years; the
     command should derive **age variants** from story-time (chapter dates /
     treatment ages) and tag each shot to the right life-stage, then
     **lineage-morph** the variants from one source so it is one face aging.
     Today this is manual `Subject (boy)/(youth)/(man)/(elder)` entities.
  3. **Prompt/appearance SYNC (the gap the user flagged).** The per-shot
     appearance TEXT must match the chosen variant — today the reference
     IMAGE pulls the right age (a youth renders ~17) but the shot's prompt
     still says "boy of fourteen" / "in his fifties" (baked once at
     `shot-prompts` time), which contradicts the image and can drag a shot
     older. The render should pull the variant's appearance string ALONGSIDE
     its image (an `appearance_override` parallel to `style_override`), or
     `shot-prompts` should regenerate age-correct appearance per shot.
  4. **Auto default-source suggestions** by entity type: real person →
     period portrait (Dürer/Hans-Maler); real place → period painting WITH
     anachronism guards (e.g. Carpaccio's wooden Rialto, NOT the 1591 stone
     bridge a naïve search returns); invented/prop → `generate`. Present
     these as defaults the user approves (the `art-directions → art-pick`
     shape) rather than hand-declaring each `source_ref`.
  5. **Carry refs to the VIDEO backends, not just gemini images.** Same
     shot→refs map should feed grok/veo/kie image-to-video / character-ref
     inputs (providers advertise `3-reference-images` / `characters+
     input_reference` but the POST bodies don't attach images yet).
  See project memory `teaser-reference-image-design` +
  `gemini-image-key-location`. Likely folds into the "Phase 5: character
  references" plan above.

- ~~**teaser-assemble: mixed static/dynamic + burn-in title cards.**~~
  **Phase 8 shipped 2026-06-06.** (1) **Mixed assembly** — `--kind mixed`:
  `build_cut_list` resolves each shot to `shot_<id>.mp4` (video, native
  audio) else `shot_<id>.png` (still, held); `CutEntry.media` +
  `media_kind()`; `ffmpeg_command` normalizes both to one WxH + stereo AAC,
  synthesizing per-still silence (`anullsrc`) so the concat `a=1` has an
  audio pad for every segment; the bed still ducks/mixes over the result.
  (2) **Burn-in title cards** — `--burn-titles` (+ `--font`): opt-in ffmpeg
  `drawtext` per `text_card` (title-role centered/large, stingers
  lower-third), alpha-faded over each segment; `CutEntry.card_kind`,
  `CutList.burn_titles`/`font_file`, `_burn_chain` + `_dt_escape` (colon/
  percent escaped, apostrophe → typographic to dodge quote hell). Timing is
  segment-local since every segment is trimmed/held to `duration_s`. Veo
  4/6/8 snap already shipped (5.9). 9 tests (test_teaser_phase8). Tier 1+2
  1744 → 1753. Wired on teaser-cut-list / teaser-assemble. **Remaining:**
  true cross-dissolve (xfade overlap, 5.7b). Original entry follows.

- **teaser-assemble: mixed static/dynamic + burn-in title cards.**
  Requested 2026-06-06 (Fugger book). Two gaps the Fugger movie hit, both
  hand-scripted in a one-off ffmpeg script (not in the pipeline):
  (1) **Mixed assembly** — a real teaser is mostly static keyframes with a
  few *dynamic* video shots (image-to-video) woven in. `teaser-assemble`
  should stitch a cut where each shot is its `video/shot_<id>.mp4` if present
  (with native audio) else its `clips/shot_<id>.png` held for `duration_s`
  (silent track), all normalized to one WxH + stereo AAC so a concat works.
  Today it only does all-image OR all-video.
  (2) **Burn-in text cards** — `cut_list.json` already stores each shot's
  `text_card` (and the title), but assemble only lists them as "add in an
  editor" notes. Add an opt-in pass (`--burn-titles`) that draws them with
  ffmpeg `drawtext`: the title centered/large, stingers lower-third, each
  faded in/out over its shot's *actual* segment duration, in a configurable
  serif (the Fugger run used EB Garamond). Timecodes must come from the
  real (mixed) segment durations, not `duration_s`, since dynamic clips run
  longer. Keep "no model-rendered type" (the model garbles lettering — burn
  it in post/assemble instead). Also: **Veo durations must snap to {4,6,8}s**
  (Veo-3-fast rejects 5/7 with a misleading "between 4 and 8" 400) — the
  render path should round `duration_s` to the nearest allowed value per
  provider.

- **Music: a `music` audio field + a cohesive trailer bed.** Requested
  2026-06-06 (Fugger book). `render_audio_for_prompt` emits dialogue + SFX +
  ambience but **no music** — so the Veo/grok prompt never asks for a score
  (the Fugger run had to fold "underscored by a driving string ostinato"
  into the `ambience` string as a workaround). Add an `audio.music` field
  emitted as its own prompt line. BUT per-clip model music does NOT connect
  across shots (3 adjacent courier-war clips = 3 unrelated cues) — the right
  answer for a trailer is **one continuous bed** laid in `teaser-assemble`
  (the `--mix duck` ducking option already exists; it needs a music source —
  a user-supplied track or a generated one) under the whole cut, with the
  per-clip dialogue/SFX on top. Document: prefer the assembly bed; per-shot
  `music` cues are for one-off dramatic beats only.

- **Non-destructive render — keep previous takes, never overwrite.**
  Requested 2026-06-06 (Fugger book). Today `teaser-render` writes
  `clips/shot_<id>.png` and a re-run **overwrites** it; a curated/QA'd frame
  is lost the moment you re-render (the user had to hand-copy the clips dir
  to a `takes/` backup before re-rendering). `--takes <n>` already suffixes
  `_take2`/`_take3`, but same-take re-runs clobber. **Action:** make renders
  versioned by default — each render lands a new take (timestamp or
  incrementing index) and a per-shot **selected/current** pointer chooses
  which take the cut-list/assemble uses (mirror the `art-directions →
  art-pick` shape: `teaser-render` accumulates takes, a `teaser-pick`
  selects). Never destroy a prior take; `teaser-assemble` reads the
  selected take. Bonus: a vision-critique auto-pick of the best take.
  Pairs with the reference-conditioned-render generalization entry above.
  **Applies to ALL written media, not just `clips/*.png`:** the video path
  `video/shot_<id>.mp4` has the identical constant-name clobber (confirmed
  2026-06-06 — re-rendering a shot overwrites its prior video take), and so
  does the **assembled output** (`teaser-assemble` / the cut should write a
  timestamped, never-overwritten copy under `teaser/cuts/` plus a stable
  "latest" name, so earlier cuts survive — the Fugger run lost intermediate
  MIXED cuts to a constant filename until a manual `cuts/` versioning copy
  was bolted on). Version takes for png keyframes, mp4 clips, AND assembled
  cuts uniformly.

- **Veo on the $300 GCP credit via Vertex (ADC).** The shipped `veo`
  backend drives the Gemini **API-key** path. The $300 new-account
  welcome credit applies only on the **Vertex** path (gcloud ADC,
  `{region}-aiplatform.googleapis.com`, `publishers/google/models/...`).
  Add a Vertex variant (ADC token, region config) so eligible users get
  ~50 min of free with-audio Veo. Documented in
  `docs/teaser-render-providers.md`; not yet wired.

- **Native-audio vs audio-bed in teaser-assemble.** `grok`/`veo` clips
  carry native dialogue+music; `magichour`/`stub` are silent. The
  assemble step preserves clip audio by default and only mixes a bed when
  `--audio` is passed — but if a user passes `--audio` *and* the clips
  already have dialogue, the bed should duck/mix rather than replace.
  Add a mix-vs-replace policy (and per-provider default) once real
  renders are flowing.

- ~~**Edit-and-revise mode for an externally-written manuscript —
  Phase 1 (import + mode flip).**~~ **Shipped 2026-04-28.** New
  `autonovel import-book <name> --from <path>` CLI subcommand and
  `/autonovel:import-book` slash-command. Splits a directory of
  `*.md` files (one chapter per file) OR a single combined
  manuscript (split on `^# `, fallback `^## `, fallback whole
  file) — `--split-on '<regex>'` overrides with a custom pattern.
  Strips pre-existing YAML frontmatter from each section, writes
  autonovel-shape `ch_NN.md` with `status: imported` and
  `imported_from: <source>` for audit, and flips
  `project.yaml :: books[].mode` to `edit-imported`. New
  `BookEntry.mode` field (default `draft`, omitted from YAML to
  keep existing files clean). `commands/draft.md` step 1a refuses
  to overwrite an edit-imported book without `--force`. New
  helper at `src/autonovel/import_book.py`. 26 Tier-1 tests
  covering directory + single-file splits, frontmatter stripping,
  custom regex split, fallback titles, writer skip-existing,
  dry-run, append-after-existing chapter numbering, BookEntry
  YAML round-trip, CLI happy path / dry-run / unknown-book. Tier
  1+2: 974 → 1005. Phase 2 (reverse-engineered foundation) is
  still queued: see follow-up entry below.

- ~~**Edit-and-revise mode — Phase 2 (foundation reverse-engineering).**~~
  **Shipped 2026-04-29 PM** as commit `a636c70` (mechanical v1).
  `autonovel import-book ... --reverse-engineer` extracts
  candidate character names from imported prose (capitalised
  single-word tokens above a frequency threshold; structural-
  English reject list of ~70 sentence-starters / month / weekday
  / honorific tokens) and writes a stub `shared/characters.md`
  when missing OR appends a "Candidate cast (auto-detected)"
  block when present (idempotent — re-runs detect the sentinel
  heading). Numbered next-steps printed: voice-discovery,
  summarize-chapter, gen-outline, evaluate. New helper
  `src/autonovel/import_foundation.py`. 14 new Tier-1 tests.
  Tier 1+2: 1193 → 1207. Doc sync: commands/import-book.md,
  docs/commands.md, series-template CLAUDE.md.
  Open follow-ups (deliberately deferred per
  feedback_avoid_brittle_python.md): voice.md Part 2 derivation
  from prose register (mechanical heuristics drift; voice-discovery
  is the right LLM-side tool), outline.md derivation from
  per-chapter summaries (needs LLM via summarize-chapter first).
  Original entry follows for context:

- **Edit-and-revise mode — Phase 2 (foundation reverse-engineering).** The
  pipeline today assumes autonovel drafted the book itself. New use
  case 2026-04-28: a user has a finished or partial manuscript
  (their own, an estate's, a public-domain text they're modernising)
  and wants to use the eval / revise / panel / review / typeset
  surfaces against it without re-drafting from scratch. Two
  sub-modes that share most of the import pipeline:

  1. **Book-only**: user drops a directory of chapter files (any
     of `.md`, `.txt`, `.docx` via pandoc, `.epub` via pandoc, a
     single combined manuscript, or a folder of one-file-per-
     chapter). The new `/autonovel:import --book <name> --from
     <path>` command:
      - splits the manuscript into chapters (heading detection,
        scene-break detection, or explicit `--split-on <regex>`),
      - writes `books/<name>/chapters/ch_NN.md` with autonovel-
        shape YAML frontmatter (chapter number + word count,
        `pov`/`status`/`story_time` left as `inferred` placeholders
        for the user to fill or for a follow-up
        `/autonovel:summarize-chapter` LLM pass to backfill),
      - reverse-engineers a stub foundation by sampling prose
        across chapters: a draft `voice.md` (Part 1 generic, Part
        2 derived from prose register), a stub `characters.md`
        with every named entity that appears more than N times,
        a stub `outline.md` listing chapter beats inferred from
        the chapter-summary helper running across the imported
        prose. None of these are authoritative — they exist so
        evaluate / revise have something to read against.

  2. **Book + foundation**: user supplies the manuscript AND a
     seed/voice/world/canon (e.g. they wrote the book against an
     existing series' conventions). Same import command with
     `--keep-foundation` skips the reverse-engineering and trusts
     the user's existing `shared/*` and `books/<name>/voice.md`.

  Cross-cutting:
  - `project.yaml :: books[].mode = edit-imported` so downstream
    commands know not to draft new chapters (forbid
    `/autonovel:draft N` in this mode by default; allow with
    `--force` for the case where the user wants to add a new
    chapter to an existing book).
  - The summary backfill step needs to be cheap; a sweep wrapper
    `/autonovel:summarize-chapter --all --book <name>` already
    exists or is one CLI flag away.
  - Tier-1 tests for the splitter (markdown headings, scene
    breaks, explicit `--split-on`), frontmatter-stub generation,
    and reverse-engineered foundation shape.
  - docs/operating-guide.md gets a §2g "Editing an externally-
    written book" walkthrough.

  Cost: ~6-10 hr (one new command, one helper file, frontmatter
  stub generator, reverse-engineering heuristics, Tier-1 tests,
  walkthrough). Opens up a meaningful adjacent use case without
  changing the rest of the pipeline.

- ~~**`/autonovel:next` — brief-newer-than-chapter signal + full
  audit of situational gaps.**~~ **Shipped 2026-04-29 PM** as
  commit `b7abadd`. Brief→revise HIGH situational signal in
  `housekeeping/next_actions.py::_brief_newer_than_chapter_actions`;
  past-end-of-book guard in `canonical_pipeline_action` that
  demotes draft commands targeting chapter N where N >
  existing_chapters + 1 to a "book appears complete" INFO
  pointing at evaluate --full / typeset. 7 new Tier-1 tests
  (single + multiple briefs, conversation.md non-trigger,
  past-end and next-sequential cases). Tier 1+2: 1123 → 1130.
  Doc sync: commands/next.md, docs/operating-guide.md, series-
  template CLAUDE.md.
  Original entry follows for context:

- **`/autonovel:next` — brief-newer-than-chapter signal + full
  audit of situational gaps.** Surfaced 2026-04-29 by author
  testing: ran `/autonovel:brief` for chapters 1, 2, 3, 5, 10 of
  an active book; `/autonovel:next` then said "draft chapter 25"
  (past end of book) instead of "revise chapters with fresh
  briefs." The canonical-pipeline default ("draft the next
  chapter") wins because no situational signal fires for the
  brief→revise pair. Concrete gaps:
   1. **brief newer than chapter → revise.** When
      `books/<book>/briefs/ch{NN}_brief.md` mtime > the
      corresponding `chapters/ch_{NN}.md` mtime, surface a HIGH
      situational action recommending `/autonovel:revise
      --chapter {NN}` (or `revision-pass --chapters {range}` for
      contiguous runs). Same shape as the existing regression /
      pending-canon checks in
      `housekeeping/next_actions.py::enumerate_actions`.
   2. **Audit every other situational case.** Walk each branch
      in `enumerate_actions` and confirm: (a) the trigger fires
      reliably on the realistic fixtures, (b) the recommended
      command's `argument-hint` matches what the action prints,
      (c) the priority is right (HIGH for data integrity,
      MEDIUM for staleness, LOW for polish). Property-based
      tests (`test_property_based.py`) verify shape but not
      semantic correctness of every branch.
   3. **Past-end-of-book guard on the canonical next step.**
      When the canonical pipeline says `draft <N>` and `N >
      planned_chapter_count + 1` (or > a configured ceiling),
      demote the line to INFO and surface a "book appears
      complete — try `/autonovel:evaluate --full` or
      `/autonovel:typeset`" suggestion instead.
  Add Tier-1 tests under
  `tests/deterministic/test_next_actions_situational.py`. Cost:
  ~3-4 hr (signal + audit + guard + tests).

- ~~**Situational-aware help hints in command output.**~~
  **Shipped 2026-04-29 PM** as commit `f1d12d7`. Every
  successful postamble now ends with a one-line `💡 Maybe try:`
  hint pulled from `next_actions.top_hint(series, just_ran=...)`
  — picks the highest-priority situational action with a runnable
  command that doesn't point back at the just-ran command, falls
  back to a 6-entry rotating "Did you know?" pool indexed by
  hash(just_ran) for deterministic-yet-varied general hints.
  Wrapped in try/except so a hint-path crash never fails the
  command. Suppressed on status=error. 6 new Tier-1 tests. Tier
  1+2: 1130 → 1136. Doc sync: docs/operating-guide.md.
  Original entry follows for context:

- **Situational-aware help hints in command output.** Surfaced
  2026-04-29 by author testing: "I'm generally lost on next
  steps, especially when the software is giving incorrect
  guidance." Today the postamble's `next_standard_step` is the
  only hint, and `/autonovel:next` is a separate call.
  Proposal: every command postamble appends a "💡 Maybe try:"
  line inferred from the same `next_actions` enumerator that
  powers `/autonovel:next`, with a max of 1-2 suggestions
  ranked by priority. Examples:
   - After `brief` → "💡 Maybe try: `/autonovel:revise
     --chapter <N>` (brief is fresher than the chapter)."
   - After `evaluate --chapter N` with score < threshold →
     "💡 Maybe try: `/autonovel:brief --chapter N` then
     `/autonovel:revise --chapter N`."
   - After `promote-canon` if conflicts remain → "💡 Maybe try:
     resolve `## Conflict` blocks in
     `shared/canon.md`, then re-run `/autonovel:promote-canon`."
  Prefer situational; fall back to a small randomised pool of
  general "did you know" hints (e.g. "💡 Did you know? `/autonovel:
  summaries --where 'score < 7'` filters chapters") only when
  no situational hint applies. Implementation: extend
  `next_actions.enumerate_actions` to expose a `top_hint(state,
  just_ran=<command>)` API; postamble in `_end` calls it and
  prints the line. Suppress when `--quiet` or when the command
  itself errored. Cost: ~3 hr (API + postamble wiring + Tier-1
  tests + the small general-hints pool).

- ~~**`/autonovel:impact-of <command>` — answer "what should I
  revise now?" without ls/grep.**~~ **Shipped 2026-04-29 PM** in
  two commits. Mechanical first pass (`347ed61`):
  `src/autonovel/mechanical/impact.py` parses `## Superseded`
  blocks in `shared/canon.md`, computes tokens unique to each
  prior_value, greps every chapter (frontmatter-stripped) for
  them, emits a per-chapter checklist of `/autonovel:revise
  --chapter N` calls with line-snippet evidence. CLI subcommand
  `autonovel mechanical impact-of` and slash-command
  `/autonovel:impact-of`. 21 new Tier-1 tests + 5 contract
  pickups. Tier 1+2: 1136 → 1162.
  LLM follow-up (`54ac17c`): slash-command extended with
  `--with-llm` (Haiku-tier classifier labels each match
  HIGH/MEDIUM/LOW/FALSE_POSITIVE so the action checklist only
  includes HIGH+MEDIUM) and `--source research` mode (LLM by
  default; reads notes newer than the last canon timestamp,
  scans each chapter against the notes' Candidate Canon
  Entries). 4 new Tier-1 regression locks. Tier 1+2: 1223 →
  1227.
  ~~Open follow-up: extending `--source` to `voice-discovery`,
  `gen-canon`, `add-character`, `rename-character`,
  `merge-chapters`, `reorder`, `remove-chapter`, `add-source`.~~
  **Shipped across two waves (most landed earlier; rename + renumber
  on 2026-05-01).** `voice-discovery / gen-canon / add-character /
  gen-characters / gen-world / add-source` shipped 2026-04-30 as
  canon-driven (gen-canon) + mtime-driven (the rest).
  `rename-character` shipped 2026-05-01 as a new "rename-verify"
  report kind: reads the most recent `autonovel:rename-character`
  entry from `.autonovel/command-log.jsonl`, parses `--old`/`--new`
  from its args, and word-boundary-greps every chapter for the OLD
  name (catches stragglers the slash-command's sed missed —
  possessives, hyphens, unicode look-alikes, HTML entities).
  `merge-chapters / reorder / remove-chapter` shipped 2026-05-01 as
  "renumber-refs": greps every chapter for prose chapter-number
  cross-references (`Chapter VII`, `chapter 7`, `ch. 12`) and emits
  a candidate review list — false positives expected (thematic
  mentions, references that were always to the right chapter).
  Both new report kinds use the command-log timestamp as context
  but degrade cleanly when no logged invocation exists. 15 new
  Tier-1 tests. Tier 1+2 contribution from this batch: +15.
  Original entry follows for context:

- **`/autonovel:impact-of <command>` — answer "what should I
  revise now?" without ls/grep.** Surfaced 2026-04-29: after
  `/autonovel:promote-canon` the author asked "what's the next
  step?" and the only correct answer required (a) reading
  `## Superseded` blocks in `shared/canon.md`, (b) `grep -ril`
  for each flipped fact across `books/<book>/chapters/`, (c)
  cross-referencing the chapter list, (d) running
  `/autonovel:evaluate --full`, and (e) building a targeted
  revise list. That is exactly the workflow autonovel exists to
  collapse — the user said "I should never have to use ls or
  grep." Same shape recurs after `research`, `add-source`,
  `voice-discovery`, `gen-canon`, `add-character`,
  `rename-character`, `merge-chapters`, `reorder`,
  `remove-chapter`. Each of those mutates a foundation file
  and downstream chapters may need to be revised; today the
  user has to do the impact analysis by hand.
  Proposed command: `/autonovel:impact-of <command>
  [--book <name>] [--since <git-ref>]` — a light-tier
  command that:
   1. Reads what changed (Superseded blocks for promote-canon;
      `git diff <ref>..HEAD shared/` for the others; new
      `shared/research/notes/<slug>.md` files for research).
   2. Walks `books/<book>/chapters/` and finds chapters that
      reference the changed surfaces — by literal grep for
      flipped names/dates and by per-chapter LLM scan for
      semantic dependencies (the cheap `chapter-summary` index
      already names cast + locations + facts).
   3. Emits a targeted action plan: a markdown checklist of
      `/autonovel:revise --chapter N (because <fact>
      changed)`, ranked by impact (number of references,
      severity of contradiction).
   4. Exposes the same plan via `autonovel _impact-of` for
      `/autonovel:next` to consume — so after `promote-canon`,
      `next` can lead with the targeted revise list instead of
      the canonical "draft chapter N+1" line.
  Generalises the brief→revise signal entry above. The
  situational-hints entry adds *one-line nudges*; this entry
  adds *the actionable list with rationale* the user actually
  needs. Cost: ~5-7 hr (analyzer per command type + LLM per-
  chapter scan + Tier-1 tests + slash-command + `_impact-of`
  CLI).
  Bigger principle: any time the help-flow forces the user
  into shell commands (`ls`, `grep`, `cat`) to figure out
  which of N chapters to act on, that's a missing autonovel
  surface — file an issue.

- ~~**Query/grep helper for `shared/research/notes/`.**~~
  **Shipped 2026-04-29 PM** as commit `54a0bd2`. Two
  complementary surfaces: `autonovel mechanical research-index
  <series>` emits a per-note metadata table (slug / title /
  updated / words / sources / body citations / candidate canon
  entries / uncertainties), with `--grep <pattern>` (full-body)
  and `--cites <URL-or-DOI>` (Sources block only) filters; and
  `/autonovel:research --query "<question>"` reads every note
  and answers with inline `[shortname]` citations — no web
  search, pure synthesis. 13 new Tier-1 tests. Tier 1+2: 1162 →
  1175. Doc sync: docs/commands.md research row, series-template
  CLAUDE.md.
  Original entry follows for context:

- **Query/grep helper for `shared/research/notes/`.** Surfaced
  2026-04-29: author has research notes for Jakob Fugger,
  Maximilian I, Charles V and wants a structured way to
  recall what's there + ask follow-up cross-character questions
  ("how did Fugger and Maximilian's relationship evolve?")
  without reading every file. Today the only paths are
  `Read shared/research/notes/<slug>.md` (one at a time) or
  `grep -r '<term>'`. Two complementary surfaces:
   1. **`autonovel mechanical research-index <series_root>`**
      (free, mechanical) — emits a markdown table: slug,
      title, source count, citation count, word count,
      last-updated. Optional `--grep '<pattern>'` filters by
      keyword across notes. Optional `--cites '<URL-or-DOI>'`
      shows which notes cite a given source.
   2. **`/autonovel:research --query "<question>"`** (LLM,
      cheap) — reads every file under `shared/research/notes/`,
      answers the question with inline citations to the source
      slugs, and writes nothing (read-only Q+A). Distinct from
      `/autonovel:talk` by querying *research* rather than
      *prose*. Distinct from `/autonovel:research "<topic>"`
      by NOT firing live web search — pure synthesis over
      what's already in `notes/`.
  The mechanical surface is the cheap "what's even in there"
  view; the LLM surface answers cross-character questions
  that need synthesis. Cost: ~4-5 hr for both.
  Open question: does adding new notes from a `--query`
  follow-up belong here too, or stay in
  `/autonovel:research "<topic>"` as today?



- ~~**PDF page-header still leaks chapter prose (regression of the
  2026-04-25 fix).**~~ **Shipped 2026-04-28.** Two distinct bugs,
  both fixed:
   1. `mechanical/latex.py::build_chapters_tex` was reading
      `lines[0]` of the post-frontmatter body as the chapter title.
      Real chapter files (per `commands/draft.md`) are YAML
      frontmatter + prose only — no `# Title` heading after the
      frontmatter. So `lines[0]` = first sentence of prose, which
      became `\chapter{<sentence>}` and rendered as a large italic
      block at every chapter title page. Fixed: new
      `_extract_chapter_title()` honours an optional
      `title:` frontmatter field, falls back to a real `# Heading`
      if present, otherwise emits empty `\chapter{}` so
      `\titleformat{\chapter}` prints `chapter <Roman>` alone.
      The empty-title case is the production shape and is now
      Tier-1 locked.
   2. Even with the new `mechanical/latex.py`, users with
      in-flight series carry a stale `<series-root>/typeset/novel.tex`
      from before the 2026-04-25 fix (`autonovel install` doesn't
      refresh typeset templates). New housekeeping subcommand
      `autonovel refresh-templates [--only typeset] [--dry-run]`
      re-copies package-shipped templates over the live series,
      preserves local-only files (custom macros etc.), and reports
      which files were updated vs unchanged vs preserved as
      local-only. Default is `typeset/` only — minimal blast
      radius. Operating-guide §3b includes the new section
      "Typeset templates need a separate refresh".
  Tier 1+2: 774 → 785.

- ~~**Talk-with-the-book mode.**~~ **Shipped 2026-04-28.** New
  heavy-tier command `/autonovel:talk --book <name>
  "<question-or-suggestion>" [--target <chapter>]`. Three modes
  it classifies from the prompt:
   - **Q+A** — *"explain why Jakob opened the book of accounts"*
     → answers with chapter+line citations.
   - **Suggest-and-stage** — *"add some details about the book of
     accounts being out of alignment"* → writes a structured
     turn to `books/{book}/briefs/conversation.md` with `Status:
     queued`.
   - **Mechanical+suggest** — *"how many cipher-diary entries
     are referred to later? Cut the orphans"* → first calls
     `autonovel mechanical entity-track`, surfaces the per-
     chapter table, performs the semantic added-vs-referred
     pairing, queues a structured cut-list.
  `commands/revise.md` reads `briefs/conversation.md`, folds
  every queued turn with `Target: chapter <N>` into the brief,
  flips them to `Status: applied` after the rewrite. The same
  conversation-fold contract is exposed in
  `commands/revision-pass.md` so sweeps pick up queued turns
  for every chapter in range automatically. New mechanical
  helper `src/autonovel/mechanical/entity_track.py` is the
  reusable named-entity tracker the Mechanical+suggest mode
  drives; it's a generalisation of `motifs.py` that resolves
  entities from `books/<book>/entities.md` first, falls back
  to `[shortname]` heads in `shared/canon.md`. Tier 1+2:
  785 → 803 (13 entity-track tests + 5 contract auto-pickups
  for `/autonovel:talk`).

- ~~**Per-book tension/pacing visualisation — beyond the existing
  `--full` table.**~~ **Shipped 2026-04-28.** New light-tier
  command `/autonovel:dashboard [--book <name>] [--threshold
  <float>] [--format markdown|json]` re-renders the latest
  `<ts>_full.json` eval log without firing another LLM evaluate.
  Augments with mechanical dimensions (cast size from summary,
  scene count from `***`/`---` markers, dialogue density from
  paragraph-opening `"`, motif density from `motifs.md` when
  present), ASCII sparklines (▁ to █) for the score and tension
  series, per-book aggregates (mean / median / range / stdev,
  longest sub-threshold streak), and the tension-drop alarm
  (≥3 consecutive declines) re-run from the existing data.
  Output ends with a `_sources_` provenance footer naming where
  each column came from. New helper
  `src/autonovel/mechanical/dashboard.py` + CLI subcommand
  `autonovel mechanical dashboard <book_root>`. 32 Tier-1 tests
  + 4 contract auto-pickups for the new command. Tier 1+2:
  803 → 840.

- ~~**Easy way to interact and query the chapter summaries.**~~
  **Shipped 2026-04-28.** New light-tier command
  `/autonovel:summaries [--book <name>] [--where '<expr>']
  [--format markdown|json]` filters the structured chapter-
  summary index via a small DSL. Supports comparison operators
  (`==`, `!=`, `<`, `<=`, `>`, `>=`) on `pov`, `score`,
  `story_time`, `word_count`, `cast`, `plot`, `location`,
  `chapter`, `status`, plus `<field> contains <literal>`,
  `<field> in <num>..<num>`, and `and` / `or` / `not` /
  parenthesisation. Numeric on numeric fields; lexicographic on
  the rest (works for ISO dates). New helper
  `src/autonovel/mechanical/summary_query.py` with a hand-
  written tokeniser + recursive-descent parser (deliberately
  not `eval()` — safer and more user-friendly errors). CLI
  subcommand `autonovel mechanical summary-query <book_root>`.
  Distinct from `/autonovel:talk` (LLM-mediated Q+A) by being
  free, scriptable, and stable — no LLM drift. 32 Tier-1 tests
  + 5 contract pickups. Tier 1+2: 840 → 877.



- ~~**`autonovel _promote-canon` Python helper for safe in-sweep
  canon promotion.**~~ **Shipped 2026-04-26.** Hidden CLI
  subcommand `autonovel _promote-canon --book <name>
  [--no-lock] [--dry-run] [--format json|human]` ships at
  `src/autonovel/promote_canon.py`. Engine implements the full
  pipeline: parse pending entries (handles bullet shape,
  `[shortname]` citations, `[research:slug]` tags, `(from ...)`
  provenance, skips `no new facts` and HTML-comment instruction
  blocks, dedupes within file); classify Duplicate (case-
  insensitive substring with 60% length floor) / Contradiction
  (year-mismatch with shared-token threshold 2; negation-flip
  with threshold 3 — conservative, won't drop facts on a
  heuristic) / Survivor; research-tagged entries beat
  contradictions and emit `## Superseded` blocks with citation;
  conflict-block format matches `commands/promote-canon.md`
  step 8 verbatim (mandatory HTML instruction block at top,
  `## Conflict N` numbered blocks naming the contradicting
  file path). The lock-collision bug class is structurally
  impossible: sub-agents invoke `autonovel _promote-canon
  --no-lock` via the `Bash` tool — no slash-command, no preamble,
  no lock check. `commands/promote-canon.md` body, `revision-pass.md`
  step 3f, and `draft-pass.md` step 5 all wired to call the
  helper as the single source of truth. 22 Tier-1 tests cover
  parsing, classification, supersedure, conflict-block format,
  mutual exclusion (file with conflicts never also has `no new
  facts`), dry-run, lock refusal without `--no-lock`, and CLI
  round-trips in human + json formats.

- ~~**Make `/autonovel:next` dynamic instead of static.**~~
  **Shipped 2026-04-28.** New helper module
  `src/autonovel/housekeeping/next_actions.py` enumerates
  filesystem state directly (no last-action.json replay) and
  returns a prioritised list of `NextAction` records: HIGH for
  data-integrity (pending-canon conflict blocks, chapter
  regressions ≥0.3 below prior best), MEDIUM for review
  staleness (reader-panel / Opus review reports older than any
  chapter file) and git backup (no repo / no remote /
  uncommitted / unpushed), LOW for polish (stale typeset PDF,
  missing book title or author, missing preface / introduction
  once ≥3 chapters drafted). Hidden subcommand `autonovel
  _next-actions [--book <name>] [--format human|json]` invokes
  the enumerator. The frozen `next_standard_step` from
  last-action.json is still surfaced — but as the lowest-
  priority "canonical pipeline next step" line at the bottom,
  so situational state always wins. `commands/next.md`
  rewritten to call the helper via the `bash` tool and print
  its output verbatim. 27 Tier-1 tests cover each per-book
  check, the three git-backup states, the canonical-action
  lookup with book filtering, the human render's priority
  grouping, and CLI round-trips in human + json. Stopgap
  postamble multi-line `next_standard_step` values from the
  sweep commands are still useful (they produce the canonical-
  pipeline line) but no longer the only source of truth.



- ~~**Per-chapter art prompts as first-class artifacts.**~~
  **Shipped 2026-04-28.** New light-tier command
  `/autonovel:art-prompts --book <name> [--chapters <range>]
  [--surface ornament|plate|scene-break] [--style lineart|full|
  symbolic] [--force]` reads outline + per-chapter summary +
  `art/visual_style.json` + `shared/world.md`, picks one
  symbolic motif per chapter via a light-tier model call, and
  writes a markdown prompt file at
  `books/{book}/art/prompts/ch{NN:02d}_{surface}.md` — six
  sections (Motif, Rationale, Prompt, Universal constraints,
  Style, Source inputs). `--force` required to overwrite an
  existing prompt file. No image provider is called.
  `commands/art-ornaments-all.md` updated to read the prompt
  file's `## Prompt` body verbatim when present, falling back to
  inline derivation otherwise. The prompt files are the right
  hand-edit target before generation, the right input for a
  non-default generator (Midjourney, ComfyUI, a commissioned
  artist), and richer than the first 400 words of prose because
  outline + summary name the chapter's turning point.

- ~~**Per-book rubric extensions via `voice.md`.**~~ **Shipped
  2026-04-25.** voice.md template now includes a `## Part 3 —
  Custom rubric` section. evaluate.md (step 4a + 10d), reader-panel
  (step 2 + 5), brief (step 5 — `## Custom-rubric findings`
  section), draft (step 6) and revise (step 5) all read it. eval
  logs gain `custom_rubric` / `custom_rubric_per_chapter` arrays;
  panel logs gain a `custom_rubric` block keyed per reader. Brief
  is required to surface flagged criteria so revise propagates
  fixes. voice-discovery preserves Part 3 verbatim. Carry-over: a
  rubric-snippet library at `src/autonovel/templates/rubrics/`
  (so common patterns like "financial discipline" or "stability-
  trap antidote" are paste-in templates) is still open as a
  follow-up.

- ~~**Long-sweep context exhaustion in draft-pass / revision-pass.**~~
  **Partly fixed 2026-04-25 evening.** draft-pass and revision-pass
  per-chapter sequences now run inside `task` subagents — each
  chapter's full workflow lives in a fresh subagent conversation
  and only a one-line summary returns to the parent. The parent's
  context grows by one short string per chapter instead of one
  full chapter's prose + tool output. Sweeps that previously
  stalled around chapter 8-10 should now run end-to-end.
  Still open: a sweep checkpoint file
  (`.autonovel/sweep-progress.json`) that `/autonovel:resume`
  reads to offer "continue from chapter N" recovery, so the user
  doesn't have to figure out `--chapters <remaining>` after an
  interruption.


- **Test-coverage gaps surfaced 2026-04-25.** The session's bug
  pattern revealed three structural test gaps that let
  late-stage / multi-stage / install-time bugs slip past Tier 1+2:

  1. ~~**Realistic late-stage fixtures.**~~ **Shipped 2026-04-28.**
     Two new conftest fixtures join `late_stage_book`:
     `mid_revision_book` (8 chapters, all evaluated, ch02+ch03
     below threshold with briefs written, panel report deliberately
     stale) and `review_phase_book` (10 chapters, all above
     threshold, panel + Opus review newer than every chapter — the
     shape right before typeset). New test file
     `tests/deterministic/test_state_machine_realistic.py`
     parametrises across all three fixtures and asserts shape
     invariants (chapter count, phase rolls forward, no foundation
     regression, situational action coverage). The realistic-fixture
     pass surfaced and fixed a real bug in
     `lifecycle._last_eval_score`: its glob `ch{NN}*.json` matched
     only the plain `chNN_eval.json` shape, missing the timestamped
     `<ts>_chNN.json` form `evaluate.md` writes — so after running
     `/autonovel:evaluate --chapter N` the next-step inference saw
     no score and looped recommending evaluate again. Helper now
     delegates to `mechanical.chapter_summary._index_latest_per_chapter_eval`
     which already handles all three naming conventions.
     Tier 1+2: 723 → 740.

  2. ~~**Multi-stage integration tests** (deterministic, no LLM).~~
     **Shipped 2026-04-28.** New file
     `tests/deterministic/test_integration_pipeline.py` walks the
     real seams: foundation chain (world → characters → voice →
     canon → outline → drafting); first-draft → evaluate → advance
     vs revise (with the timestamped eval shape that #5.1 fixed);
     low-score → revise → re-eval → advance; pending-canon gate
     (draft → pending entry appears → next-step says
     promote-canon → run real `promote_canon.promote` →
     pending file rewritten → gate releases → advance);
     situational `next_actions` shifts as state evolves; canonical
     pipeline action surfaced at the bottom; eval-score indexer
     resolves all three production naming conventions. 7 new
     Tier-1 tests; Tier 1+2: 740 → 747.

  3. ~~**pipx-isolated install test (Tier-3).**~~
     **Shipped 2026-04-28.** New file
     `tests/smoke/test_pipx_install.py` builds a wheel via
     `pipx install <repo>` against an isolated `PIPX_HOME` /
     `PIPX_BIN_DIR` (so the install never touches the user's real
     pipx state). Falls back to `python -m pipx` when `pipx` isn't
     on `$PATH`, skips cleanly when neither works. Then exercises
     the CLI surfaces that have historically broken under wheel
     packaging: `autonovel --help`, `_next-actions --help`,
     `mechanical slop --help`, `_promote-canon --help`, and an
     end-to-end `new-series` + `doctor` round-trip — the last is
     the strongest check for `templates/` packaging since
     `new-series` writes from `src/autonovel/templates/` and a
     missing force-include in pyproject would fail there. Marked
     `smoke + pipx_install` so it can be excluded independently
     (`-m "smoke and not pipx_install"`). Runs in ~6s on the
     dev box.

- **Bells Tier-4 fixture populate.** Still parked since PR 4. The
  harness is built; the chapters from `autonovel/bells` branch
  need copying in. Once populated, this is the canonical
  full-pipeline regression — gates LLM-prompt drift across an
  entire 19-chapter manuscript. Today's work would have benefited:
  a regression run on Bells chapters with summaries + evals + briefs
  would have caught at least the chapter-count and next-step bugs
  before they shipped.

- ~~**Property-based tests for invariants.**~~
  **Shipped 2026-04-28.** New file
  `tests/deterministic/test_property_based.py` uses
  `hypothesis` (added under `[test]` extras) to generate random
  book layouts (chapter count 0-12, random POV, status, prose,
  scores, summary/eval-log/motif/entity/pending-canon presence)
  and assert invariants:

  - `iter_chapter_files` count equals the chapter-count exactly
    (catches the `.summary.md` glob regression).
  - `_infer_phase` returns a known phase name for every layout.
  - `lifecycle._next_step_for` always returns a non-empty
    command + rationale, namespace `/autonovel:` or `autonovel`,
    no unsubstituted `{...}` placeholders.
  - `enumerate_actions` priorities are in {HIGH, MEDIUM, LOW,
    INFO} with non-empty title + rationale.
  - `summarize_chapters` row-count matches chapter file count.
  - `build_dashboard`, `build_entity_report`, `build_motif_report`
    do not crash on arbitrary layouts.
  - `next_step.next_step()` decision table returns valid
    command + rationale for every legal `PipelineState`.

  10 properties × 25 examples each = ~250 random layouts per
  CI run. Tier 1+2: 897 → 907.

- ~~**Read-only TUI for series state — terminal only, NOT a web
  server.**~~ **Shipped 2026-04-29 PM** as commit `597d308`. New
  CLI subcommand `autonovel tui [--book <name>]` launches a
  textual-based read-only browser with seven tabs: Help (live —
  for each suggested next command, shows rationale + reads/
  writes from frontmatter), Chapters (DataTable + side detail
  + score sparkline), Research (notes list + preview), Foundation
  (status of each shared/ + per-book file), Front matter
  (title/author/preface/introduction), Reviews (reader-panel +
  Opus review presence + mtimes), Commands (last 15 + situational
  next-actions + canonical step). Header bar: series name · book
  selector · lock state · sweep progress live · cost today +
  total. Polls FS every 5 s; press `r` to refresh; `b` to switch
  books; `0-6` to jump to tabs; `q` to quit. Read-only by
  contract — never acquires the lock; safe to run alongside an
  active sweep. New optional extra `[tui]` (`textual>=0.70`); the
  CLI prints a clear pip / pipx install hint when textual isn't
  importable. New helper `src/autonovel/tui.py`. 16 new Tier-1
  tests covering sparkline edge cases, slash-command extraction,
  command-index cache, state-load shape on minimal + late-stage
  fixtures, graceful CLI degradation. Tier 1+2: 1227 → 1243. Doc
  sync: docs/operating-guide.md, README.md, docs/commands.md
  (new CLI subcommands section).
  Original entry follows for context:

- **Read-only TUI for series state — terminal only, NOT a web
  server.** Author noted 2026-04-25 that NousResearch's earlier
  autonovel had a richer read-only console showing file artifacts
  and live progress; the rewrite ships only `autonovel status`
  (one-shot CLI), `autonovel statusline` (Claude Code status bar),
  `.autonovel/command-log.jsonl` (append-only JSON log), and
  `/autonovel:dashboard` (markdown table — shipped 2026-04-28).

  The next step is a long-running terminal UI via `textual` or
  `urwid` that streams the lock state, last-action, recent
  command-log entries, per-book phase + chapter scores, and the
  `pending_canon.md` queue.

  **Constraint clarified 2026-04-28: must be terminal-native
  (TUI), not a web server.** Author runs autonovel on
  WSL / Linux on Chromebook, where a localhost web server is
  awkward (no direct browser access from the WSL filesystem
  context; the user has to do port-forwarding gymnastics that
  defeat the "trivial to start" goal). Same constraint applies
  to `/autonovel:dashboard`'s output today — markdown table in
  the runtime's chat is the right surface, NOT a generated HTML
  file the user is supposed to open. Future enhancements to the
  dashboard (sparklines per dimension, expandable rows, filter
  controls) should keep the same shape: print to stdout, render
  in the terminal, no browser dependency.

  Roughly 1–2 days for a textual TUI. Hold for now — current
  tools cover the same data and the dashboard fills the
  highest-value visualisation gap. Pick this up when CLI
  output becomes the bottleneck.


- **Research-from-seed auto-merges into canon (no manual editing).**
  ~~Open~~ **Fixed 2026-04-25.** `/autonovel:research --from-seed`
  now appends every research-derived candidate to the active book's
  `pending_canon.md` with a `[research:<slug>]` tag.
  `/autonovel:promote-canon` honours that tag: research-tagged
  entries win contradictions against the prior canon, and the
  supersedure is recorded in a `## Superseded <UTC-date>` block in
  `shared/canon.md` with the citation. Net effect: a user runs
  research-from-seed, then promote-canon, and `shared/canon.md`
  reflects cited primary-source facts without hand edits — date
  corrections like "Fugger arrived 1478 not 1473" propagate
  automatically and visibly.


- ~~**Drafter must degrade gracefully when reading prior chapter
  files.**~~ **Shipped 2026-04-28.** Each drafter command body
  (`commands/draft.md`, `commands/revise.md`,
  `commands/draft-pass.md`, `commands/revision-pass.md`) gains an
  explicit **Read-failure policy** preamble at the top of its
  `<workflow>`: do NOT retry on `file_read` errors for non-load-
  bearing inputs (prior summaries, eval logs, prior-chapter
  quotes); note the gap and proceed. The single hard-stop is the
  chapter file at `revise` step 6 — that's the load-bearing input
  we're rewriting. Catches the 2026-04-25 retry-loop bug class
  that stalled long sweeps around chapter 8-10 when a single
  summary file was missing or had a different shape than expected.

  context fails.** ~~Open~~ **Fixed 2026-04-25.** `commands/draft.md`
  step 7 and `commands/revise.md` step 6 now mark the prior-chapter
  read as best-effort with explicit "do not retry on failure"
  wording, and call out per-chapter summaries (step 8) as the
  load-bearing continuity surface. Author can no longer stall on
  Read retries when ch_{prev} hits a Claude-Code-internal hiccup.
  Carry-over: a *time-based* watchdog on `_begin` (live PID + lock
  older than N minutes → mark abandoned) is still open as a more
  general defence — the no-retry wording fixes this specific case
  but not the broader "LLM is wedged but PID is alive" failure.

- **Cross-provider `/autonovel:compare-models`.** V1 (shipped
  2026-04-25) is single-provider — it compares two Claude models
  within the active runtime. The natural extension is Opus vs GPT
  vs Gemini head-to-head, since model providers ship updates every
  few months and the user shouldn't have to migrate to evaluate.
  Implementation hint: add a `--runtimes claude,codex,gemini`
  argument; the parent runtime spawns a draft per (runtime, model)
  pair via the adapter layer (likely a new `autonovel _spawn-draft`
  CLI subcommand that knows how to invoke each runtime's headless
  mode and copy the result back into `eval_logs/`). The judge stays
  on whichever runtime the parent is in. ~3-5 hours of work.

- ~~**Research belongs at the front of the foundation, not as a
  manual step.**~~ **Shipped 2026-04-28.** All three sub-items
  are now live:
    1. `/autonovel:research --from-seed` mode (shipped earlier)
       reads `seed.txt` + `project.yaml :: period` and writes
       sourced notes per topic.
    2. `_foundation_gap` recommends `/autonovel:research
       --from-seed` before gen-world when
       `project.yaml :: period.start` is set and
       `shared/research/notes/` is empty (lifecycle.py lines
       ~504-514). Three Tier-1 tests around the gap behaviour.
    3. **(2026-04-28)** `commands/gen-world.md` step 3a and
       `commands/gen-canon.md` step 2a now read every populated
       `shared/research/notes/*.md` as primary source of truth,
       cite slug provenance in the world bible's Sources
       section, surface a one-line nudge when a period project
       has no research notes, and (gen-canon) preserve the
       `[research:<slug>]` tag through to canon bullets so
       promote-canon's tagged-survives-untagged conflict
       resolution stays correct. 7 new Tier-1 regression locks
       in `tests/deterministic/test_research_at_front.py`. Tier
       1+2: 1049 → 1056.

## From live author testing (post-PR-9)

These surfaced during a real first-run on a Chromebook + WSL on Claude
Max $200/month. Full narrative + rationale in
`docs/lessons-from-author-testing.md`.

- ~~**Onboarding flow — clear "what to write and when" + sensible
  defaults for working title and author attribution.**~~
  **v1 shipped 2026-04-30** as `autonovel onboard <book>` plus
  doc updates in operating-guide §1 and README. Wizard walks
  through pitch / period / genre / working title / human author
  / attribution style with structured prompts; every prompt has
  a `(skip)` option that lands in a `## Onboarding TODO` block
  for `/autonovel:next` to surface. Writes a structured seed.txt
  + updates project.yaml :: books[<book>].title (with `(working)`
  suffix) and .author (rendered per attribution_style:
  seed-by-human / human-only / ai-only / co-author). 13 new
  Tier-1 tests cover full-run / all-skipped / partial-skip /
  attribution rendering / project.yaml preservation. New helper
  `src/autonovel/onboard.py`. Tier 1+2: 1393 → 1406.

  Open follow-ups (deferred from v1):
   1. Inline LLM working-title proposals during the wizard. v1
      defers to `/autonovel:title` (which is a runtime command,
      not a Python helper) for proposals — the wizard's
      "working title" prompt either takes the user's typed input
      or skips with guidance to run /autonovel:title once they're
      in Claude Code. A future v2 could call out to the runtime
      from the CLI to inline this.
   2. Structured author dict (`{human, ai_co_author,
      attribution_style}`) on `project.yaml :: books[].author`
      instead of the currently-rendered string. v1 stores the
      rendered string ("Seed by X; drafted with Autonovel") so
      typeset / cover.py / ePub builder don't need schema
      migration. v2 would migrate to the dict and add a
      `display_attribution()` helper that callers use, with
      legacy-string-author backward compat.

- **Onboarding flow — original entry follows for context.** Surfaced
  2026-04-30 by author testing. The current new-series + new-book
  flow drops the user into a series root with a stub `seed.txt`,
  empty `voice.md` Part 2, no title, no author, and no concrete
  guidance on *which file to fill in next or how much to write*.
  The result is a confused user pasting a half-formed pitch into
  seed.txt and then asking the runtime "what now?" — exactly the
  ls/grep failure mode but at the start instead of the middle.
  Three concrete improvements:

  1. **Onboarding wizard.** New CLI subcommand
     `autonovel onboard [--book <name>]` that walks through the
     foundation in order with prompts:
       - "Paste your one-paragraph pitch (period, protagonist,
         central conflict, tone). Examples: ..." → writes
         `seed.txt` with the formatted result.
       - Period? Region? Genre? → updates `project.yaml`.
       - Working title (we'll suggest 3 from the seed) → sets
         `books[<name>].title`.
       - Human author name → `books[<name>].author` (default-set
         per below).
       - "Run `/autonovel:gen-world` next" — the next-step is
         spelled out, with the tier (heavy) and approximate token
         cost noted.
     Each prompt has a `(skip — fill later)` option; the wizard
     writes a one-line `## Onboarding TODO` block to seed.txt
     listing what's still empty.

  2. **Suggested working titles from the seed.** When the user
     provides a seed, generate 3 working-title candidates via a
     light-tier LLM call and write them as commented options in
     seed.txt:
     ```
     # Working titles (LLM-suggested; pick one or write your own
     # via `/autonovel:title --book <name> --set "<title>"`):
     #   1. "<candidate-A>"
     #   2. "<candidate-B>"
     #   3. "<candidate-C>"
     ```
     Pre-populates `books[<name>].title = "<candidate-A> (working)"`
     so the title page never falls back to "Untitled" while the
     book is in flight. The `(working)` suffix flags it as a
     placeholder; `/autonovel:title --set` strips the suffix.

  3. **Author attribution defaults — credit the human, name the
     AI honestly.** Currently `books[<name>].author` defaults to
     empty and the typeset title page falls back to "Anonymous".
     Better: at onboard / new-book time, default to a structured
     `author` value:
     ```yaml
     author:
       human: "<name>"          # required; prompted at onboard
       ai_co_author: "Autonovel"  # optional; truthful credit
       attribution_style: "seed-by-human"   # default
     ```
     Where `attribution_style` controls the typeset rendering:
       - `seed-by-human` (default): "Seed by **<human>**;
         drafted with Autonovel."
       - `human-only`: "<human>" (when the human did substantive
         editing — they decide).
       - `ai-only`: "Autonovel" (acknowledging full AI authorship;
         honest for unedited drafts).
       - `custom`: free-form string the human supplies.
     The credit lands on the title page (typeset / cover) and in
     ePub metadata. Honest by default ("the AI did most of the
     work"), but the human gets named and acknowledged. Avoids
     both extremes (uncredited human; deceptively-credited AI).

  4. **Onboarding state reachable from `/autonovel:next`.** Add a
     HIGH situational signal "Foundation incomplete — run
     `autonovel onboard`" when seed.txt is empty / only has
     placeholder content / `books[<name>].title` is unset. So
     even a user who skipped onboarding finds their way back via
     the existing next-action flow.

  Cost: ~6-8 hr (CLI subcommand + prompt module + LLM
  title-suggestion via light tier + project.yaml schema bump for
  the structured author block + typeset.tex update for the new
  attribution_style render path + Tier-1 tests + operating-guide
  §1 onboarding walkthrough rewrite). The structured author
  block is a one-way schema change so PR sequence matters —
  ship the schema migration before the CLI to keep already-
  in-flight series upgradable.

- ~~**Per-command `model:` override on `[1m]` session models —
  recovery path.**~~ **Shipped 2026-04-28.** New CLI flag
  `autonovel install --no-model-pin` re-renders every command
  file with the `model:` frontmatter field omitted, so the
  runtime's session model wins on every invocation. Recovery
  path for users on a `[1m]` session model whose per-command pin
  silently downshifts them to the non-`[1m]` variant. Adapter
  signature gains `pin_model: bool = True` parameter; installer
  inspects the adapter signature and only forwards the flag to
  adapters that accept it (so Codex/Gemini stay no-op until they
  opt in). Doc sync in docs/troubleshooting.md "My session
  model is `[1m]`" section. The longer-term fix
  (`project.yaml :: llm.honor_session_model` to make pinning
  per-project opt-out) is still tracked but not blocking now
  that the recovery flag exists.

- **Per-command `model:` override — per-project opt-out.** The
  `--no-model-pin` install flag (shipped 2026-04-28 above) is the
  recovery path; the long-term fix is per-project opt-out via
  `project.yaml :: llm.honor_session_model = true` so users can
  pick the policy per-series rather than at install time. Lower
  priority now that the recovery path exists.
- ~~**Postamble compliance watchdog.**~~ **Shipped 2026-04-28.**
  `lock.acquire_with_takeover` gains an `expire_after_seconds`
  parameter (default 30 min via `DEFAULT_LOCK_EXPIRE_SECONDS`).
  Any lock older than the threshold is silently taken over at
  the next `_begin`, with the abandoned LockInfo surfaced via
  the existing `BeginResult.abandoned_lock` channel so the
  postamble can warn the user. Independent of PID liveness —
  catches the same-Claude-Code-session case where the LLM
  skipped `_end`. Lock age comes from the `started_at` ISO
  timestamp in the lock JSON, with mtime fallback when that
  field is corrupted. Pass `expire_after_seconds=None` or `0`
  to disable for callers that explicitly want the
  pre-2026-04-28 PID-only semantics. New `is_expired(lock_path,
  max_age_seconds)` predicate. 7 new Tier-1 tests including
  end-to-end through `lifecycle.begin`. Tier 1+2: 877 → 884.
- ~~**Verify `writes:` files were actually modified.**~~
  **Shipped 2026-04-28.** New
  `checkpoints.verify_writes(cp, series_root, claimed)` returns a
  `WriteVerificationReport` with one item per claim and statuses
  `created` / `modified` / `deleted` / `unchanged` / `missing` /
  `outside-checkpoint`. `lifecycle.end` invokes it after release,
  surfaces `unchanged` and `missing` as warnings in the
  postamble footer (`⚠️ verify-writes:`) and records a one-line
  summary on the command-log entry's `note` field for audit
  trail. Catches the bug class where the LLM passes `--wrote
  <path>` without invoking Write/Edit. Paths still containing
  `{book}` placeholders or paths outside the checkpoint are
  classified `outside-checkpoint` (informational, not warnings).
  Doc sync in docs/troubleshooting.md. 13 new Tier-1 tests
  covering each status path + lifecycle integration. Tier 1+2:
  884 → 897.
- ~~**Canon-vs-outline cross-consistency in `/autonovel:evaluate`.**~~
  **Shipped 2026-04-28.** `commands/evaluate.md` `--phase
  foundation` mode gains a new `canon_outline_consistency`
  dimension. The judge reads both `shared/canon.md` and
  `books/<book>/outline.md`, finds every fact mentioned in
  BOTH, and emits a `canon_outline_conflicts` array with one
  entry per disagreement (canon says ch4 is in 1473, outline
  ch4 says 1471 → flagged). Recommendation defaults to "canon
  wins; revise the outline" since `/autonovel:promote-canon`
  is the process by which facts harden. Catches the bug class
  where outline plants contradict canon entries that hardened
  from a different chapter's research, leaving downstream
  chapters drafted against silently-wrong dates or names.

- **Canon-vs-outline cross-consistency — Python-side helper.** Today
  When canon says X arrived in 1473 and the outline says 1471, the
  user shouldn't have to spot the contradiction manually. evaluate
  --phase foundation could date-compare references.
- ~~**`autonovel install --dry-run`** so users can preview what would
  be written into `~/.claude/commands/` before mutating it.~~
  **Shipped 2026-05-01.** `installer.install()` accepts a
  `dry_run: bool = False` kwarg; when true it renders every
  command (so render errors still surface) but creates no
  directories and writes no files. CLI exposes `--dry-run`; the
  per-runtime banner switches from "installed" to "would install"
  and per-file sigils from `+` to `~`. Trailer line names "no
  files written. Re-run without --dry-run to apply." 4 new Tier-1
  tests cover: nothing-on-disk after a fresh dry-run, plan ↔ real
  install file-list match, dry-run idempotent over an existing
  install dir.
- ~~**`autonovel _begin` should echo a "running from `<dir>`" banner.**~~
  **Shipped 2026-04-28.** `_cmd_begin` prints a one-line
  banner `_begin: running from series root \`<name>\`` (or
  `... (cwd: <relative-path>)` when the user launched the
  runtime from below the series root). Catches the
  wrong-cwd-launch failure mode before the command silently
  misroutes paths. Two new Tier-1 tests cover the at-root and
  below-root cases. Tier 1+2: 907 → 912.


## Output writing quality

These are things that would lift the prose ceiling beyond what the
current pipeline reliably produces (Bells topped out at pacing ≈ 7,
prose ≈ 8 / 10, with investigation-heavy plots).

- ~~**Per-character voice fingerprints.**~~ **Shipped 2026-04-25.**
  voice.md template now includes a `## Part 4 — Per-character voice
  fingerprints` section. voice-discovery (step 6a) auto-drafts it
  when shared/characters.md has ≥3 named principals — one ~5-bullet
  block per character (Speech / Verbal tics / Refuses / Body during
  dialogue / Interiority [POV only]); cap 6 characters. Step 7b
  preserves hand-edited Part 4 verbatim across re-runs (`--force`
  overrides). draft.md (step 6) and revise.md (step 5) both apply
  Part 4 at every dialogue line + every interiority sentence.
  evaluate.md (step 4b) shifts the `character_voice` dimension from
  "do characters sound distinct?" to "does each character honour
  their Part 4 block?" when Part 4 is populated, with the strongest
  violation quoted in `weakest_moment`. Solo-cast / single-speaker
  books fall back to Part 2 cleanly (the threshold rule skips Part
  4 generation; the placeholder comment stays).
- ~~**Dialogue mechanics linter.**~~ **Shipped 2026-04-28.** New
  mechanical helper `src/autonovel/mechanical/dialogue.py` flags
  adverb-heavy speech tags (`said quietly`, `murmured softly`),
  said-bookisms (`exclaimed`, `murmured`, `whispered`,
  `growled`, …), and repeated-speech-verb stutters (the same
  non-`said` verb 3+ times within a 10-line window). Per-chapter
  counts + per-line hits with snippets. New CLI subcommand
  `autonovel mechanical dialogue <book_root>` and slash-command
  `/autonovel:dialogue`. 16 Tier-1 tests covering each pattern,
  edge cases (frontmatter strip, plain-said unflagged, stutter
  window boundaries), render shapes, and CLI round-trip.

- ~~**Dialogue mechanics — extension follow-ups.**~~
  **Shipped 2026-04-29** with the brittle parts deliberately
  scoped down (see feedback_avoid_brittle_python.md). Three new
  detectors in `mechanical/dialogue.py`:
  - **action-beat-as-tag clusters** — 3+ action-beat tags
    (`she laughed, "..."`) within a 10-line window.
  - **softening qualifiers in short retorts** — `maybe / kind
    of / a little / I think / I guess` inside dialogue lines
    under 80 chars.
  - **unattributed-dialogue clusters** — ≥3 consecutive un-tagged
    dialogue paragraphs. Reported as a review list, not a gate;
    the cast-count gate that 2026-04-29 testing tried to add
    was reverted because it relied on a brittle proper-noun-
    counting proxy that broke on Unicode names. The LLM
    judge's `voice_adherence` dimension is the right place to
    score this.
  Word lists kept short and curated (`ACTION_BEAT_VERBS` ~25
  entries, `SOFTENING_QUALIFIERS` ~13). 11 new Tier-1 tests +
  command-body disclaimer update. Tier 1+2: 1081 → 1092.
- ~~**Scene-level beat coverage in `evaluate.py`.**~~ **Shipped
  2026-04-25.** New `autonovel mechanical scenes <chapter>` helper
  splits a chapter into scenes by `***` / `---` / `* * *` breaks
  (Tier-1 testable; 14 tests covering frontmatter strip, surrounding
  whitespace tolerance, phantom-empty-scene drops, opening/closing
  edge cases, CLI round-trip with and without `--full`). evaluate.md
  step 10e walks the per-scene index and scores each scene 0/1 on
  goal / conflict / disaster_or_decision / consequence; aggregates
  to per-chapter `beat_coverage` block with `weakest_scenes` list
  (any scene missing 2+ beats), each entry carrying a one-sentence
  prescription naming the missed beat and what to add. Single-scene
  chapters get the "split into two scenes around the midpoint
  decision" suggestion. `--full` mode aggregates to
  `book_beat_coverage_score` + `weak_beat_coverage_chapters` list,
  which catches the "drifting middle" Bells failure mode. brief.md
  walks `weakest_scenes` and turns "tighten chapter 8" into "scene
  8.2 needs a decision before the break" with the scene's
  `opening_line` quoted for surgical targeting.
- ~~**Cliché bigram/trigram scanner.**~~ **Shipped 2026-04-25** —
  `autonovel mechanical cliches <path>` returns a curated bigram
  scan; `evaluate.md` invokes it for `--chapter` and `--full`,
  feeding `density_per_1000_words` into the slop penalty (every
  full unit above 2.0 subtracts 0.1, capped at 0.5).
- ~~**Sensory-channel balance scanner.**~~ **Shipped 2026-04-25** —
  `autonovel mechanical sensory <path>` returns per-channel
  fractions (visual/auditory/olfactory/gustatory/tactile) and a
  `dominant_channel` flag when one channel >70%. `evaluate.md`
  surfaces dominance as a chapter `weakest_moment` callout.
- ~~**Period register lock.**~~ **Shipped 2026-04-28.** New
  helper `src/autonovel/mechanical/period_register.py` rolls
  the existing `slop.period_ban_hits` scanner across every
  chapter and emits a per-chapter hit table + a worst-offenders
  ranking by total occurrences. Useful before typeset to confirm
  the manuscript stays in period across the full run. CLI
  subcommand `autonovel mechanical period-register <book_root>`
  and slash-command `/autonovel:period-register`. 16 Tier-1
  tests covering bans loading (comments + blanks), word-boundary
  case-insensitive matching, frontmatter stripping, summary
  aggregation, render shapes (with/without `--summary-only`,
  no-bans message, no-chapters message), and CLI round-trip.

- ~~**Period register — extension follow-up.**~~
  **Shipped 2026-04-29.** Per-chapter Flesch-Kincaid grade
  computed against a voice/seed/median baseline; chapters
  whose absolute delta exceeds `--threshold` (default 1.0
  grade level) are flagged. Pure math — no curated word-lists,
  no register dictionaries — so this scanner doesn't drift
  with vocabulary. New helper functions in
  `src/autonovel/mechanical/period_register.py`
  (`flesch_kincaid_grade`, `_syllables_in_word`,
  `build_syntax_drift_report`, `render_syntax_drift_markdown`),
  CLI subcommand `autonovel mechanical syntax-drift
  <book_root>`, slash-command `/autonovel:syntax-drift`.
  Reported as a review list — real chapter drift can be
  intentional register shift (action sequences, dialogue-
  heavy, modernism homage); the LLM judge in
  `/autonovel:evaluate`'s `voice_adherence` dimension scores.
  18 Tier-1 tests + 5 contract pickups. Tier 1+2: 1092 →
  1115.
- ~~**POV bleed scanner.**~~ **Shipped 2026-04-28.** New helper
  `src/autonovel/mechanical/pov_bleed.py` flags lines where a
  cast member who is NOT the chapter's POV is named with an
  interiority verb (`thought`, `felt`, `knew`, `realised`,
  `wondered`, `remembered`, `hoped`, `feared`, `believed`, …)
  or possessive interiority (`Niccolò's mind`, `Lucia's heart`).
  Cast comes from `shared/characters.md` (parsed in `**Name**`
  bullet form OR `## Name` heading form); chapter POV from the
  YAML frontmatter `pov:` field. False-positive caveat is
  documented inline in the rendered report — non-POV characters
  CAN have their interiority legitimately reported by another
  character, so output is a review list not a gate. CLI
  subcommand `autonovel mechanical pov-bleed <book_root>` and
  slash-command `/autonovel:pov-bleed`. 19 Tier-1 tests covering
  cast parsing (both shapes + missing file), verb / possessive
  patterns, POV-self-exclusion, no-cast / no-cast-override
  paths, render shapes, and CLI round-trip.

- **POV bleed — knowledge-edge follow-up.** The 2026-04-28 scanner
  catches interiority (`Niccolò thought`, `Lucia's mind raced`).
  Knowledge edges (POV references a fact they couldn't have)
  needs cross-chapter tracking and is best done as an LLM-judge
  dimension, not a mechanical scanner — the cheap "the woman /
  the man" version was considered 2026-04-29 and rejected per
  `feedback_avoid_brittle_python.md`: the de-anonymising-drift
  detector would need a brittle proper-noun heuristic that
  drifts on Unicode names + sentence-initial caps. Right shape
  is a future LLM-judge dimension that consumes the existing
  pov-bleed scanner output and adds knowledge-edge reasoning;
  hold for now.
- ~~**Bell's "irreversible change" scorer.**~~ **Shipped 2026-04-25.**
  evaluate.md gains an `irreversible_change` dimension on
  `--chapter` mode and `irreversible_change_arc` on `--full` mode.
  Per-chapter calibration runs from 9-10 (specific named irreversible
  change at the chapter's main beat) down to 1-2 (pure setup or
  stasis); chapter 1 specifically caps at 7 if the ending leaves the
  protagonist able to refuse the call to action. Whole-book mode
  walks every (N→N+1) chapter pair asking "could chapter N+1 have
  started from N's *opening* state?" — every "yes" is a chapter that
  failed to commit, surfaced in `cuttable_chapters`. Below 6 on the
  per-chapter score is added to `top_3_revisions` automatically.
  brief.md adds a `## Stability check` section (only when the eval
  log's score is <7) that names the reversion and prescribes ONE
  specific irreversible commitment — never falls back to vague
  "raise stakes" because that's exactly what the Stability Trap
  produces. The named ceiling failure from CLAUDE.md ("AI defaults
  to safe, round-edged endings; pacing ≈ 7 plateau on
  investigation-heavy plots") now has a measurement and a
  prescription.
- ~~**Per-chapter motif tracker.**~~ **Shipped 2026-04-28.**
  New mechanical helper `src/autonovel/mechanical/motifs.py` reads
  `books/<book>/motifs.md` (one bullet per motif: `- slug:
  keyword1, keyword2, keyword3`), strips YAML frontmatter from each
  chapter before counting (so `events: [bell-toll]` doesn't inflate
  the bell density), and matches keywords on word boundaries
  case-insensitively. Emits a markdown table with one row per
  chapter and one column per motif (zero-hit cells render as `·`).
  Back-half drop warnings fire only when the motif was used at
  least once in the front half — silent when a declared motif was
  never used (avoids noise). Books under 4 chapters skip warning
  logic entirely. CLI subcommand `autonovel mechanical motifs
  <book_root> [--format markdown|json]`. New slash-command
  `/autonovel:motifs` wraps it. 17 Tier-1 tests + 5 contract
  pickups; Tier 1+2: 747 → 769.
- ~~**Show-don't-tell — pre-flight scanner.**~~ **Shipped 2026-04-28.**
  New helper `src/autonovel/mechanical/show_dont_tell.py` casts a
  wider net than the existing slop regex. Four pattern families:
  emotion-state (`<X> was/felt/seemed <emotion>` against a curated
  ~50-word emotion list), interiority verbs (`knew`, `realised`,
  `understood`, `recognised`, `decided`, `thought`, `believed`,
  `wondered`, `hoped`, `feared`, `wished`, …), perception filters
  (`<Y> looked/sounded <adverb>` against a curated filter-adverb
  list), narrator labels (`It was <emotion>`, `There was
  <emotion>`). Per-chapter table + per-line hits with snippets;
  density-per-1000-words column for normalisation. Slash-command
  `/autonovel:show-dont-tell`. The LLM-judge ratio scoring
  upgrade (direct/indirect/hybrid classification + per-chapter
  ratio) is queued separately. 18 Tier-1 tests + 5 contract
  pickups. Tier 1+2: 1026 → 1049.

- ~~**Show-don't-tell — LLM-judge ratio upgrade follow-up.**~~
  **Shipped 2026-04-29.** `commands/evaluate.md` `--chapter`
  mode gains the `show_dont_tell_ratio` dimension; `--full`
  mode gains `show_dont_tell_arc`. Both invoke the mechanical
  pre-flight scanner via `bash`, classify each candidate
  line as **direct** (bare proposition, no anchor),
  **indirect** (anchored by sensory / behavioural evidence),
  or **hybrid** (legitimate direct telling — interior
  summary, time compression, register-mark in close-third).
  Per-chapter ratio = `(indirect + hybrid) / total`; mapped
  linearly to 0-10 with a penalty when raw `direct_count`
  exceeds `chapter_word_count / 500`. `worst_offenders` array
  surfaces the top-5 direct-classified lines with one-line
  embodiment suggestions for brief / revise. `--full`
  aggregates a `tell_heavy_chapters` list (ratio < 0.6) so a
  sweep brief can target them. Zero-candidates chapters score
  9.0 (not 10.0) to flag the suspicious case where the
  scanner found nothing. 7 Tier-1 regression locks lock the
  contract surfaces in `evaluate.md`. Tier 1+2: 1074 → 1081.

## Reader interest / reading experience

- ~~**TOC + chapter-page rendering should show chapter names by
  default; numbers-only as an opt-in.**~~ **v1 shipped 2026-04-30
  PM.** Three sub-items all live:
  1. `commands/draft.md` step 11 generates a 2-6 word evocative
     title at draft time; written to frontmatter `title:` field.
     `commands/revise.md` step 8b regenerates the title when the
     central beat changes.
  2. `mechanical/chapter_titles.py` inspector + new CLI
     subcommand `autonovel mechanical chapter-titles` reports
     which chapters have a title (frontmatter / heading / missing).
     `/autonovel:extract-chapter-titles --book <name>` LLM-
     backfills the missing list. /autonovel:next surfaces the
     missing-titles count as a LOW polish signal.
  3. `mechanical/latex.py::_extract_chapter_title` already
     surfaces the title via `\chapter{<title>}`, so TOC + chapter
     opening + running header all read it for free. The
     numbers-only opt-out via `project.yaml :: typeset.chapter_titles
     = false` is documented in draft.md but not yet enforced —
     follow-up entry below.
  10 new Tier-1 tests for the inspector + render shapes. Tier
  1+2: 1409 → 1431.

  ~~Open follow-up: enforce `project.yaml :: typeset.chapter_titles
  = false` in `_extract_chapter_title`.~~ **Shipped 2026-05-01.**
  `ProjectConfig` gains a `typeset` dict (round-trips in YAML, omitted
  when empty); `build_chapters_tex` and `build_epub_md` accept a
  `chapter_titles: bool = True` kwarg; `autonovel mechanical build-tex`
  and `build-epub-md` gain `--no-chapter-titles` (explicit override)
  and `--project-yaml <path>` (read `typeset.chapter_titles` from
  `project.yaml`); `commands/typeset.md` passes `--project-yaml
  project.yaml` on both build paths. When false, chapters render as
  `\chapter{}` (PDF — `\titleformat` prints "chapter <Roman>" alone)
  and `# Chapter N` (ePub — pandoc TOC reads "Chapter 1, Chapter 2,
  …"). 11 new Tier-1 tests. Tier 1+2: 1492 → 1503.

- **TOC + chapter-page rendering — original entry follows for context.**
  current typeset emits `\chapter*{}` (empty) when a chapter
  file has no `title:` frontmatter field — relying on
  `\titleformat{\chapter}` to render `chapter <Roman>` alone.
  That makes the table of contents read `Chapter I`, `Chapter
  II`, `…` with no signal of what each chapter contains. For
  real-book convention, the TOC should show evocative chapter
  titles ("The Apothecary's Mortar"), with the numbers either
  alongside or as a metadata cue.

  Three sub-asks:

  1. **Generate chapter titles by default during draft.**
     `/autonovel:draft` step N adds a step: write a 2-6 word
     evocative title for the chapter to the frontmatter `title:`
     field. The LLM is good at this from prose. Same shape for
     `revise` (regenerate when the chapter's central beat
     changed). New `--no-title` flag for users who want
     numbers-only books explicitly.
  2. **Mechanical title-extractor for retroactive backfill.**
     `autonovel mechanical extract-chapter-titles <book>` reads
     each chapter's prose and proposes a 3-5-word title via
     LLM (light tier; can run as a sweep). Updates frontmatter
     in place.
  3. **Typeset surfaces the title in the TOC, the chapter
     opening page, and the running header.** Update
     `mechanical/latex.py::_extract_chapter_title` to use the
     frontmatter `title:` when present; emit `\chapter[<short>
     ]{<long>}` so TOC short-form matches the running-header
     and the chapter opening page reads "Chapter VII — The
     Apothecary's Mortar". Numbers-only mode (project.yaml ::
     typeset.chapter_titles = false) preserves the current
     empty-`\chapter*{}` shape.

  Cost: ~6-8 hr (draft.md + revise.md body changes; mechanical
  extract-chapter-titles helper + CLI; latex.py title rendering
  + typeset.tex template; project.yaml schema bump for the
  numbers-only switch; Tier-1 tests across the chain). Pairs
  with the existing chapter-summary helper (which already
  exposes the 7-section template's Plot field — that field is
  the primary input for a chapter-title suggestion).

- ~~**Automated mixed-source timeline for the appendix —
  fictional + real-world dates, distinctly marked.**~~
  **v1 shipped 2026-04-30 PM.** Mechanical pass shipped
  (`mechanical/timeline.py::extract_in_narrative_dates`); LLM
  merge documented in the slash-command body.
  - Mechanical: walks chapter summaries' `## Story time` +
    frontmatter `events:` for in-narrative dates (`📖` marker
    with chapter cite). New CLI subcommand `autonovel mechanical
    timeline-extract`. 11 new Tier-1 tests covering extraction,
    summary-overrides-frontmatter precedence, sorting, render
    shapes. Tier 1+2 contribution: +11.
  - LLM: `/autonovel:appendix --sections timeline` body extended
    to invoke the mechanical helper, then layer in `🏛️ referenced`
    rows (real events the prose mentions, cross-referenced
    against research notes) and `🏛️ context` rows (events the
    prose doesn't mention but the reader should know — opt-in
    via `--include-context`). `--story-only` cuts to narrative
    only.
  Pairs with the existing `/autonovel:summaries --where
  'story_time >= "1492-08"'` query DSL — same data, different
  surface.

- **Automated mixed-source timeline for the appendix — original
  entry follows for context.** Surfaced 2026-04-30. The current `/autonovel:appendix --sections
  timeline` (shipped same day) is LLM-only and pulls from
  research notes + canon. Richer shape: walk the manuscript
  itself for in-story dates and merge with researched
  real-world events, marking each row's source so the reader
  knows what's documented vs invented.

  Three sources of timeline rows:

  1. **Story-time, in-narrative.** Mechanical pass over
     `books/<book>/chapters/ch_*.summary.md`'s `## Story time`
     fields plus the `events:` frontmatter array on each
     chapter. These are the dates the book actually depicts.
     Render with a marker (e.g. `📖 ch N`) so the reader
     understands "this happened on the page".
  2. **Real, referenced in the book.** Real-world events the
     prose mentions (e.g. "the sack of Constantinople, forty
     years before") without depicting them. Detected by
     cross-referencing chapter prose against research-notes'
     candidate canon entries marked with year tokens. Render
     with a different marker (e.g. `🏛️ referenced ch N`).
  3. **Real, context-setting.** Events the reader should know
     to follow the book but the prose never mentions —
     researched + LLM-curated for relevance to the period and
     to the book's thematic concerns. Render with a third marker
     (e.g. `🏛️ context`). The scholarly-edition convention is
     to include these so the reader can place the story in its
     wider history.

  Output: an alphabetically-by-date timeline merging all three,
  with a legend explaining the markers. Filter switches:
  `--story-only` for just (1), `--include-context` to add (3)
  on top of (1)+(2), default (1)+(2). Replaces the current
  appendix-timeline LLM-only path with a mechanical-then-LLM
  hybrid: the mechanical pass covers (1) deterministically, the
  LLM does (2) cross-referencing and (3) curation.

  Implementation seam:
  - `mechanical/timeline.py` extracts story-time rows from
    chapter summaries + frontmatter events. Pure-Python; cheap.
  - `/autonovel:appendix --sections timeline` body extended to
    invoke the mechanical helper first, then ask the LLM to add
    rows (2) and (3) on top, marking each row's source.
  - Format spec in the appendix template (Markdown rows like
    `**1492-08-03** 📖 — Lucia first appears (ch 5).`).

  Cost: ~5-7 hr (helper + summary parsing for `## Story time` /
  `events:` extraction; LLM-side body changes; tests; doc sync).
  Pairs with the existing `/autonovel:summaries --where 'story_time
  >= "1492-08"'` query DSL — same data, different surface.

- ~~**Pacing curve graph in `/autonovel:evaluate --full`.**~~
  **Shipped 2026-04-25** — `--full` mode emits a markdown table
  with per-chapter words / score / tension / dialogue% / scenes /
  beats-hit so the user sees the shape of the book at a glance.
- ~~**Tension-drop alarms.**~~ **Shipped 2026-04-25** — `--full`
  scans the tension column for any window of three+ consecutive
  chapters trending down and surfaces a "⚠️  Tension drop
  detected: chapters X→Y→Z" callout with the recommended
  revision-pass invocation.
- ~~**First-page hook check.**~~ **Shipped 2026-04-25** —
  `/autonovel:evaluate --chapter 1` adds a separate
  `hook_strength` score over the first 250 words; surfaces it on
  its own line in the summary; flags below 6.0 as a real concern.
- ~~**Series-arc score.**~~ **Shipped 2026-04-28.** New helper
  `src/autonovel/mechanical/series_arc.py` and slash-command
  `/autonovel:series-arc` deliver a cross-book scoreboard:
  per-book completion (summary / eval / above-threshold counts
  + earliest/latest story_time), cross-book cast (characters
  appearing in ≥2 books, ranked by spread), backwards story-
  time jumps (chapter where `story_time` regresses from prior
  — legitimate for flashbacks but worth surfacing), unresolved
  threads (chapter `Threads opened:` with no later
  `Threads closed:` substring match), and a composite 0-10 arc
  score blending completion + above-threshold fraction +
  story-time discipline penalty + unresolved-thread penalty.
  CLI subcommand `autonovel mechanical series-arc <series_root>`
  + slash-command. 16 Tier-1 tests + 5 contract pickups. Tier
  1+2: 1005 → 1026.

- ~~**Series-arc — LLM-judge upgrade follow-up.**~~
  **Shipped 2026-04-29.** New `--phase series` mode in
  `commands/evaluate.md` scores arc *quality* across ≥2 books.
  Pairs with the structural scoreboard
  (`/autonovel:series-arc`): the helper provides evidence
  (cross-book cast, backwards story-time jumps, unresolved
  threads, structural arc score); the LLM judges quality
  (does the series open a load-bearing question and resolve
  it? do early-book setups pay off late? does each cross-book
  character earn their state changes? does world evolution
  stay consistent? does tone carry across books?). Five
  dimensions: `series_question`, `early_setup_late_payoff`,
  `cross_book_character_growth`, `world_evolution_consistency`,
  `tonal_continuity`. Top-level outputs include
  `series_score`, `weakest_book`, `top_3_arc_revisions`, and
  the load-bearing `unresolved_thread_payoff_plan` array
  (one entry per `series-arc` thread the LLM rates as a real
  payoff debt, with a one-sentence "where this should pay
  off" note that brief / revise can act on). Eval log lands
  at `.autonovel/eval_logs/<ts>_series.json` (series-level,
  not per-book). 8 Tier-1 regression locks pin the contract
  surface. Tier 1+2: 1115 → 1123.

## Adjacent output formats

- **Movie script + theater play output formats — both from a finished
  manuscript and from-scratch.** Surfaced 2026-05-01. autonovel today
  produces novels (PDF + ePub + audiobook). A natural adjacent direction
  is screenplay / stage-play output — same foundation (world / cast /
  outline / canon / voice fingerprints) drives a different leaf-shape.
  Two modes:

  1. **Adapt a finished autonovel book** — `/autonovel:adapt --book
     <name> --to screenplay|stage-play [--length feature|short|tv-pilot|
     one-act|three-act]`. Reads `books/<name>/chapters/`, the outline,
     and the per-character voice fingerprints (Part 4 of voice.md is
     load-bearing here — dialogue must already sound like the character),
     and emits a script under `books/<name>/scripts/<format>/`. Most of
     the heavy lifting is already done: the prose has scenes, beats,
     dialogue, POV. Adaptation is a structural rewrite (collapse
     interiority into action; promote subtext to externalised choices;
     enforce the format's act/scene structure) rather than fresh
     drafting. Reads `pacing` and `irreversible_change` dimensions
     from `eval_logs/` to identify the load-bearing scenes that must
     survive the cut.

  2. **Author from scratch in script mode** — `/autonovel:new-book <name>
     --mode screenplay|stage-play` flips the book's `mode` field
     analogously to `edit-imported` (already shipped). The drafter writes
     in script format from the start, the evaluator scores against
     screenplay/stage-play rubrics rather than novel rubrics
     (visual-storytelling, dialogue-as-action, scene-as-unit-of-change),
     and typeset emits standard industry format (Final Draft / Fountain
     for screenplays; Samuel French style for stage plays).

  Cross-cutting concerns:

  - **Script-format typesetting** is non-trivial and bigger than the
    novel typeset path. Industry shapes are strict:
      - **Screenplay**: 12-pt Courier, 1-inch margins, scene headings
        in CAPS, character names centered above dialogue, action lines
        flush left, parentheticals in parens. Page count maps roughly
        1 page = 1 minute of screen time. Standard exporter is the
        Fountain markup language → PDF via `screenplain` or similar
        Python lib; `.fdx` (Final Draft XML) is the format pros expect.
      - **Stage play**: similar but distinct conventions (character
        names in caps inline at dialogue start; stage directions in
        italics; act/scene breaks more pronounced). Fountain-derived
        formats exist; pandoc has experimental support.
    Suggests a new `[scripts]` extras with `screenplain` + `fountain-
    parser` + maybe `prosemark`; `autonovel doctor` learns to pre-flight
    these like it does tectonic / pandoc / fonts.

  - **Evaluator rubric per medium.** A novel's "interiority" dimension
    is a script's bug. New per-medium evaluator rubrics under
    `evaluate.md` — picked by the book's `mode` field. Scene-level
    beat coverage (already shipped via `scenes.py`) carries over
    cleanly; show-don't-tell is a non-negotiable in script form
    (everything is shown — there's no narrator).

  - **Voice fingerprints become casting briefs.** voice.md Part 4
    (per-character) is exactly what an actor / director reads to
    understand their character — the fingerprint shape is already
    right. Add a `--for-casting` flag to `/autonovel:voice-discovery`
    that reformats Part 4 into a casting-brief-shaped document.

  - **Audiobook → table read pipeline.** The audiobook script parser
    (`commands/audiobook-script.md`) already extracts speaker-attributed
    dialogue and emotion tags from prose. That's 70% of what a
    table-read script needs. Worth wiring `--for-table-read` as an
    alternative output mode to `audiobook-script`.

  - **Front-matter shapes differ.** Screenplays open with a title page,
    no preface. Stage plays open with a cast list, setting note, and
    sometimes a director's note. The existing front_matter.tex /
    back_matter.tex builders are PDF-novel-shaped and would need
    parallel script-mode templates.

  Cost: substantial. Plausibly a multi-PR effort spanning a new typeset
  path (~12 hr), new evaluator rubrics (~6 hr), the adapter command
  (~8 hr), the new-mode drafter changes (~10 hr), and the script-format
  exporters with format-conformance tests (~10 hr). Total: ~46 hr of
  focused work, plus review iterations against real screenwriting /
  playwriting conventions. Worth scoping as its own milestone rather
  than a near-term item.

  Open questions:

  - Should "from-scratch script mode" reuse the novel pipeline's
    foundation (world / characters / outline / canon) or fork into a
    script-specific scaffold? Probably reuse — the foundation is
    medium-agnostic, only the leaf prose form changes.
  - Does the audiobook flow get a "radio play" subset (script mode +
    audiobook synthesis = an actual radio drama with multi-voice
    casting)? Cheap addition once script mode exists.
  - Industry-standard `.fdx` (Final Draft XML) vs Fountain (.fountain)
    vs PDF-only — likely all three; `.fdx` for pros, `.fountain` for
    git-friendly source-control, PDF for portability.

- **🎬 MOVIE-SCRIPT MODE FOR AI VIDEO + 1–3 MINUTE TEASER GENERATOR
  (near-term, user-prioritised 2026-06-05).** A focused subset of the
  big "movie script + theater play" entry above, scoped tight enough
  to actually ship. The user's intent: produce a *movie* script (the
  combined entry covered movie + play, but the deliverable here is
  specifically the screenplay/movie path), and from it auto-generate a
  detailed, descriptive **1–3 minute teaser/preview** whose shots are
  emitted as richly-described prompts ready to feed an AI video tool
  (Sora 2 / Veo 3 / Runway Gen-4 / Kling, etc.). The script is the
  spec; the teaser is the first shippable visual artefact — much
  cheaper and more impressive than a full film, and it forces us to
  solve the load-bearing problems (descriptive prompting, shot
  decomposition, character/style consistency across clips) at a tiny
  scale before the ultra-long-term full-video pipeline below.

  Why teaser-first, not full-film-first: clips from every current
  provider are short (~4–10 s native), so even a 1–3 min teaser is
  already an assembled montage of 15–40 generated clips — the same
  assembly + consistency machinery the full pipeline needs, but at a
  cost and iteration speed a single author can actually run.

  Scope of THIS item (the teaser, not the whole movie):
   1. **Movie-script mode** — author/adapt a screenplay (reuse the
      adapt + from-scratch shapes from the combined entry above), OR
      derive a teaser straight from an existing autonovel book's
      outline + key scenes without a full screenplay first.
   2. **Teaser beat-sheet** — a light-tier command selects the 8–20
      teaser-worthy beats (hook → escalation → title card → button)
      from the script/outline, honouring trailer craft (withhold the
      ending; lead with the hook; rhythm to a music bed).
   3. **Descriptive shot-prompt generator** — the core deliverable.
      Each beat → one or more shots, each shot emitted as a
      provider-targeted, heavily-descriptive prompt using a structured
      field schema (shot size · subject + appearance · action ·
      setting · lighting · camera movement · lens/film-stock/look ·
      mood · audio cue · negative prompt). Provider profiles tune the
      phrasing/length per target (Runway = concise, Veo = rich
      cinematography, Sora = audio-aware, Kling = its own conventions).
      Pulls character appearance from `shared/characters.md` +
      voice.md Part 4, setting from `shared/world.md`, period from
      `project.yaml`. Output: hand-edit-friendly `.md` per shot plus a
      machine `teaser.json`.
   4. **Consistency anchors** — emit reference-image / first-frame /
      character-reference guidance per shot so the same character and
      location read consistently across the assembled clips (the known
      hard part; reuse the cross-book illustration-coherence reference
      library shared/art_references/).
   5. **Assembly spec (optional v1.5)** — a `cut_list.json` + ffmpeg
      concat with music bed + text cards to stitch user-generated
      clips into the finished teaser. v1 can stop at "hand the prompts
      + cut order to the user"; v1.5 automates the stitch.

  This sits between the combined movie/play entry (its parent — share
  the screenplay typeset + evaluator-rubric work) and the
  ultra-long-term full-video pipeline (its superset — the teaser is
  that pipeline run on a 2-minute spec). PRD: `docs/prd-movie-teaser-
  mode.md` (drafted 2026-06-05, informed by a web-research pass on
  current AI-video prompting; see the PRD's References section).
  Cost: PRD-scoped; the teaser-only v1 is far smaller than the full
  movie or video pipeline — plausibly ~20–30 hr for shot-prompt
  generation + provider profiles + beat-sheet, excluding the
  screenplay-typeset work it inherits from the parent entry.
  **Progress (2026-06-05):** implementation plan written
  (`docs/impl-plan-movie-teaser.md`); `pre-movies` safety tag created.
  **Phase 0 shipped** — `src/autonovel/teaser/` package; additive
  optional `teaser`/`video` dicts on `ProjectConfig`; `[video]`/
  `[scripts]` extras stubs; docs split (`docs/teaser-craft.md` is now
  the canonical creative guide); install-immutability guard tests.
  **`/autonovel:treatment` shipped** — film treatment + 2-page brief
  (X-Prize-shaped). Tier 1+2: 1503 → 1515.
  **Phase 1 shipped (2026-06-05)** — `src/autonovel/teaser/{shots,beats,
  render_prompt,providers,critique}.py`; mechanical CLI `teaser-plan` /
  `teaser-validate` / `teaser-critique` / `teaser-render-prompt`;
  `/autonovel:teaser-beats` (beat-sheet on the hook→escalation→title→
  button arc) and `/autonovel:shot-prompts` (structured shot schema →
  provider-ready prompts + teaser.json + per-shot markdown, with a free
  mechanical+LLM pre-generation critique incl. appearance-drift /
  clip-cap / one-action / palette / consistency checks). All free, no
  generation. Tier 1+2: 1515 → 1546. First validated end-to-end on the
  Fugger book (treatment + brief committed to medieval-king-maker, tag
  `first-movie-brief`); `shot-prompts` then validated on the same book
  (35 shots, 144s, clean critique).
  **Phase 1 final shipped (2026-06-05)** — `/autonovel:teaser` (the
  one-command orchestrator: chains teaser-beats → shot-prompts, each in
  a fresh `task` subagent for context hygiene; `--with-treatment`;
  overwrite-guarded; free) and `/autonovel:teaser-critique` (standalone
  re-runnable free critique = mechanical linter + LLM critic; read-only
  on teaser.json; writes `teaser/critique.md`). Plus a robustness guard
  (`shots.load` raises a clear error on malformed top-level JSON). Tier
  1+2: 1546 → 1562.
  **Phase 2 shipped (2026-06-05)** — per-provider render **dialects**
  (`render_prompt.render_visual`: prose for veo/sora/generic/pollinations,
  terse comma-keywords for Runway, concise + Luma camera-enum for Luma;
  follows `--provider` automatically) and reference-image **consistency
  anchors** (`teaser/refs.py` + `teaser-refs-plan` CLI: which canonical
  ref each subject needs, which shots use it, which exist in `teaser/refs/`
  or a `shared/art_references/` plate, which are missing — wired into
  shot-prompts so no manual `ls`). Tier 1+2: 1562 → 1570.
  **Phase 3.5 shipped (2026-06-05)** — thin free render adapter
  (`teaser/render.py`: stateless deterministic-seed Pollinations URLs,
  injectable httpx seam, per-clip failure isolation) + `teaser-render`
  and `resolve-video-provider` CLIs + `/autonovel:teaser-render` command
  (resolve → dry-run plan → download → vision KEEP/REGENERATE/
  UPGRADE-TO-PAID clip critique → advisory `clips/render-report.md`).
  Bright lines held: clips on disk only, no state file, no auto-assembly,
  paid providers only recommended. `--dry-run` plans for $0; watermarks/
  low-res fine for dev. Tier 1+2: 1570 → 1584.
  **Phase 3 shipped (2026-06-05)** — ffmpeg assembly: `teaser/assemble.py`
  (`CutList` schema + `build_cut_list` from teaser+clips + a PURE
  `ffmpeg_command` planner — image slideshow or video trim+concat, audio
  bed, never runs ffmpeg) + `teaser-cut-list`/`teaser-ffmpeg-cmd` CLIs +
  `/autonovel:teaser-assemble` (ffmpeg check → cut_list.json → run ffmpeg
  via bash → viewer-panel cut critique → assembly-report.md). v1: hard
  cuts, no burned-in text (cards go in an editor), missing clip skipped.
  Tier 1+2: 1584 → 1600. **✅ The movie-teaser pipeline is now
  end-to-end** (treatment → teaser → teaser-critique → teaser-render →
  teaser-assemble). Future polish: crossfades/transitions, burned-in
  title cards via an editor-export, native-audio (Veo/Sora) paths,
  `--kind video` on more providers.

- **🚀 ULTRA-LONG-TERM: Script → full video pipeline.** Surfaced
  2026-05-01. The natural endpoint of the screenplay output above:
  drive a full video-generation pipeline from a parsed Fountain /
  `.fdx` script. The script becomes the spec — every scene, every
  beat, every cut, every duration.

  Pipeline shape (each stage produces a versioned artefact under
  `books/<name>/video/`):

  1. **Script → shot list.** Parse the screenplay's scene headings
     (`INT. APOTHECARY'S SHOP — DAY`), action lines, and dialogue
     into a structured `shots.json`: per-shot framing (wide /
     medium / close), camera move (static / pan / dolly / handheld),
     duration estimate (rough proxy: 2-3s per action beat, 3-5s
     per spoken line), and the in-shot subjects (characters from
     `shared/characters.md`, props from canon, setting from world).
     New `/autonovel:shot-list --book <name>` light-tier command
     emits the JSON; reads voice.md Part 4 for character beat
     density. Hand-edit-friendly — the LLM gets the rough cut
     right ~80% of the time and the user fixes the rest.

  2. **Shot list → storyboard frames.** Each shot becomes 1-3
     storyboard frames (key + transition frames). Reuse the existing
     `/autonovel:art-curate` pipeline with a shot-specific prompt
     ("medium shot of Tommaso turning toward the door, apothecary
     shop interior, late afternoon light, period-correct 1521") and
     the cross-book illustration coherence reference library
     (shared/art_references/) to keep characters consistent across
     shots. Output: `books/<name>/video/storyboard/<scene>_<shot>_
     <frame>.png`. New `/autonovel:storyboard --book <name>
     [--scene <range>]` heavy-tier command (one LLM prompt per
     frame).

  3. **Storyboard → animated shots.** Each frame-pair becomes a
     short video clip via image-to-video / video-generation provider
     (Runway Gen-3, Sora, Kling, or local equivalents — same
     `[--provider runway|sora|kling|local-svd]` precedence shape as
     `image.provider`). Camera moves from the shot list become
     provider-specific motion prompts. Output: `books/<name>/video/
     clips/<scene>_<shot>.mp4`. New `[video]` extras pulling in
     whatever provider SDKs land. Real-money expensive at first;
     local SVD-style models will likely catch up within a few years.

  4. **Audio: narration + dialogue + score + SFX.** Reuses the
     existing audiobook pipeline for dialogue (per-character
     ElevenLabs voices already in `voices.yaml`); adds an `[ambient]`
     track per scene from a public-domain music library (drone /
     period / silent options) and an SFX track from the `shared/sfx/`
     library (entry above). New `/autonovel:video-audio --book
     <name> [--scene <range>]` orchestrates per-shot audio mixing
     against the shot list timing.

  5. **Edit list → final cut.** A `cut_list.json` (LLM-generated
     from the script's pacing — tight cuts in action sequences,
     long takes in dialogue scenes; tunable per shot) drives ffmpeg
     concatenation with cross-fades, hard cuts, dissolves per the
     specified style. Output: `books/<name>/video/<book>_v<N>.mp4`.
     Reuse the existing `mechanical/audio.py::format_chapter_marks_
     mp4chaps` shape for chapter-level navigation.

  6. **Style coherence at every layer.** This is the load-bearing
     constraint. Same problem as cross-book illustration coherence
     (entry above) but harder — characters must look the same not
     just across books but across thousands of shots within one
     scene, with motion. Likely needs a per-character LoRA-style
     fine-tune (or whatever the provider's character-locking
     primitive is by then), trained from the storyboard frame set
     once it's been picked. Foundation file: `shared/character_
     models/<name>.safetensors` (or the provider's equivalent
     handle) referenced by every video-generation call.

  Cross-cutting:
    - **Director's-mode evaluator rubric** — distinct from the
      screenplay rubric; scores shot variety, pacing variation,
      coverage (does every important moment get its own frame?),
      continuity (does the prop in shot 4 match shot 7?). Visual-
      LLM judge over the storyboard frames + shot list.
    - **Iteration loop is the real cost.** Re-rendering one shot
      after a script edit must NOT re-render the whole movie. State
      tracking via `.autonovel/video-state.json`: which scenes →
      which shots → which clips are current vs stale, mtime against
      the source script. Same shape as the existing chapter ↔
      summary stale-detection.
    - **Real-time preview.** A `autonovel video-preview` TUI /
      web mode plays back the current rough cut (storyboard +
      audio, no rendered video yet) so the director iterates on
      pacing before paying for the expensive video generation.
    - **Print-vs-screen typeset divergence.** The book's PDF
      typeset, screenplay typeset, and video-final cut are three
      different leaf outputs from the same foundation; the
      typeset-templates story we already have generalises cleanly.
    - **Industry-standard exchange.** EDL / XML / OTIO export so
      the rough cut can be opened in DaVinci Resolve / Premiere /
      Final Cut for human polish. We're not trying to replace the
      editor — we're making the rough cut so cheap the editor
      starts at version 4 instead of version 1.
    - **Audio ducking, music sync, lip sync** — the boring
      production-finish work that nobody does well right now. Real
      time to get there: years, not months. ML-driven lip sync
      (Wav2Lip-style; later real-time generative) is the closest-
      to-shippable piece.

  Cost: enormous — easily 200-300 hr for a v1 that produces a
  watchable rough cut from a script (shot-list extraction is
  ~25 hr; storyboard reuse of art-curate is ~15 hr; video-clip
  provider integration is ~30-40 hr per provider; audio mixing
  is ~25 hr; cut list + ffmpeg edit is ~30 hr; state tracking is
  ~20 hr; preview UI is ~30 hr; character coherence at video
  scale is the hard research problem and could swallow another
  100+ hr alone). The video-generation models themselves will
  determine whether v1 is "watchable" or "uncanny-valley
  unwatchable" — likely 2-3 years of provider quality improvement
  before the rough-cut output is usable for anything beyond a
  storyboard reel. Best treated as the long-horizon endpoint of
  the whole adjacent-formats arc, not a near-term plan.

  Open questions:
    - Should the "video" extras pull in heavy ML deps (diffusers,
      torch, ffmpeg-python, OpenTimelineIO, …) by default or
      stay strictly cloud-API for v1? Probably cloud-only initially;
      add `[video-local]` once local generative video catches up.
    - Where does live-action footage fit? An `--actors human` mode
      where the storyboard becomes a *shot-list document for a
      human director* (no video generation; the pipeline stops at
      stage 1) is a useful intermediate product — gets indie
      filmmakers a free pre-production package from their script.
    - Same script, multiple cuts (theatrical / streaming / TV
      pilot) — the cut_list.json is per-version; the underlying
      storyboard + clip library is shared. Director's-cut shape
      from the start.

- **Children's books with cross-book illustration coherence.** Surfaced
  2026-05-01. Children's books are an entirely different shape than the
  current adult-novel target — short prose (under 1000 words for picture
  books, 5-15k for early-readers, 20-50k for middle-grade), heavy
  illustration density (1-2 illustrations per spread for picture books;
  every 1-3 pages for early-readers), and the *artwork* is the
  load-bearing surface, not the prose.

  Two strands:

  1. **`/autonovel:new-book --mode picture-book|early-reader|middle-
     grade`** flips the book's mode analogously to other modes. Each
     mode has its own evaluator rubric (vocabulary band check via the
     existing syntax-drift Flesch-Kincaid scanner — easy reuse;
     repeated-phrase patterning for early readers; chapter-target word
     count brought way down), its own typeset shape (large-format
     trim sizes — 8.5"×8.5" picture book; 6"×9" middle-grade; spread
     layouts with image + facing-page text rather than running prose),
     and its own front matter (dedication, "For ages X-Y", reading-
     level badges).

  2. **Cross-book character/setting illustration coherence** — the hard
     part. A series of children's books needs the protagonist to look
     like the same kid across every book, the dog to be the same dog,
     the bedroom to be the same bedroom. Today's `art-curate` generates
     each variant independently with no character/setting memory. Three
     mechanisms:
       - **Reference-image library at `shared/art_references/`** —
         per-character, per-setting, per-key-prop reference PNGs that
         every illustration generation reads as `image-to-image` input
         (or via the equivalent `--reference-image` flag for paid
         providers; ControlNet for local SD; `--style-reference` for
         pollinations once it supports it). Auto-populated by promoting
         picked variants from `books/<name>/art/` after `art-pick`.
         Foundation file analogous to `shared/characters.md` but for
         visual identity.
       - **Visual-style continuity scoring** — extend `evaluate.md`
         with a `visual_continuity` dimension that compares each new
         illustration against the reference-image library via CLIP
         embeddings or a vision-LLM judge ("does this character look
         like the same character?"). Below-threshold matches get
         flagged for re-generation rather than silently shipping.
       - **`shared/art_style_lock.md`** — a structured lock file the
         illustrator (LLM or human) reads before each render: palette,
         line weight, character-specific identifiers (red hat, freckles,
         curly hair), setting consistency rules. Generated by
         `art-style` with a `--lock` flag; hand-edited like any other
         foundation file.

  Cross-cutting:
    - **Layout typesetting** — picture books need full-bleed
      illustrations and tight image+text page composition; the current
      novel.tex layout is wrong-shape. New `templates/picture-book/`
      shape with InDesign-IDML or Affinity Publisher PDF/X export
      paths, or a Pillow-based composer that handles spread layouts
      directly. The existing `art-import --as plate` shape is closer
      than the chapter-prose shape.
    - **Print-on-demand integration** — picture books typically print
      via specialty POD (Lulu hardcover, BookBaby color-print) rather
      than KDP. Different cover specs (hardcover dust-jacket
      dimensions, board-book page-stock weights). Worth a
      `cover-print --format hardcover-dust-jacket` mode.

  Cost: another multi-PR milestone — illustration coherence alone is
  ~20 hr (reference library + visual-continuity scorer +
  art_style_lock); picture-book typeset is ~15 hr; mode-specific
  evaluator rubrics ~8 hr; print-spec extensions ~10 hr. Total
  ~50-60 hr.

- **Interactive web-page books — narrated, quizzable, branching.**
  Surfaced 2026-05-01. An entirely different output medium — instead
  of a static PDF / ePub, render the book as an interactive web page
  (likely a single-page React or vanilla-JS app served as a static
  site) with:

  1. **Audio narration synced to text.** The existing audiobook script
     parser (`commands/audiobook-script.md`) already produces speaker-
     attributed + emotion-tagged JSON; the audiobook generator
     (`commands/audiobook-generate.md`) already renders MP3 via
     ElevenLabs. Add a `--for-web` mode that emits per-paragraph audio
     sprites + a JSON timing manifest so the web page can highlight
     the active word/sentence as it plays (the standard "karaoke
     subtitle" pattern). Cheap given the existing pipeline.

  2. **Speech-recognition quizzing.** After each chapter (or
     configurable interval), the page poses a comprehension question
     ("Who did Tommaso meet at the bell tower?"), captures the child's
     spoken answer via the browser's `SpeechRecognition` API, and
     scores it against an LLM-generated rubric. Three quiz strategies:
       - **Recall** — name a character / location / event from the
         chapter just read.
       - **Inference** — "Why did she hide the key?" — open-ended;
         scored on semantic match, not literal text.
       - **Prediction** — "What do you think happens next?" — scored
         on plausibility against the outline + canon (no wrong
         answers, but "knight rides in" gets a "good guess — keep
         reading!" while "they go to the moon" gets a "interesting!
         let's see…").
     Generation: new `/autonovel:quiz --book <name> [--chapters
     <range>]` light-tier command writes per-chapter quiz JSON to
     `books/<name>/web/quizzes/ch_NN.json`; the web frontend reads
     it. Speech recognition is browser-native (no cloud STT cost);
     scoring is cloud LLM (cheap, one call per spoken answer).

  3. **Clickable sound effects.** Inline SFX markers in the prose
     (e.g. `[sfx:bell-toll]`, `[sfx:door-creak]`) become clickable
     icons in the rendered web page that play the named effect.
     Authored manually or auto-detected during a `/autonovel:audiobook-
     script --emit-sfx` pass that scans for sound-bearing prose
     ("the bell tolled", "the door creaked open") and inserts the
     markers. SFX library: a curated public-domain set under
     `shared/sfx/` (bell-toll.mp3, door-creak.mp3, footsteps-stone.
     mp3, …) seeded by `autonovel install-sfx-library` (or use
     freesound.org's CC0 set via API).

  4. **Choose-your-own-adventure branching paths.** Optional —
     applies when the book has been authored with branch points (see
     the standalone CYOA mode below). The web page renders the book
     as a graph, lets the reader pick at each branch, and tracks
     which paths they've explored.

  Implementation surface:
    - **New `/autonovel:web-build --book <name>`** typeset-equivalent
      command that emits `books/<name>/web/` (HTML + JS + CSS + audio
      + image assets + a manifest.json mapping chapters to assets).
      Static site — drops onto Netlify / Vercel / GitHub Pages
      without a backend.
    - **New `[web]` extras** pulling in whatever JS bundling we choose
      (likely just esbuild + a small handwritten runtime — no React
      framework dependency, keeps output size and complexity down).
    - **TUI Reviews tab gains a "Web preview" link** that prints the
      `python -m http.server` command pointing at the built site.
    - **Accessibility pass** — speech recognition, audio narration,
      and quizzing are exactly what assistive-tech-friendly book
      design wants; lean into screen-reader compatibility, keyboard
      navigation, and high-contrast modes from day one.

  Cost: substantial — ~40-50 hr for v1 (web-build command + frontend
  runtime + audio sprite path + quiz generator + SFX wiring); CYOA
  branching adds another ~15 hr if shipped together.

- **Choose-your-own-adventure book type — standalone authoring mode.**
  Surfaced 2026-05-01. Distinct from the CYOA-branching feature of
  the interactive web books above — this is a *first-class CYOA mode*
  for authoring branching narratives the same way other modes
  (novel / picture-book / screenplay) are first-class.

  Authoring shape:

  - **`/autonovel:new-book --mode cyoa`** scaffolds a book whose
    `outline.md` is a directed graph (decision nodes + outcome nodes)
    rather than a linear chapter list. Outline format extended with
    `[branch:<id>]` markers and `→ ch_<NN>` outgoing edges per choice.
  - **Drafter writes "passages" not "chapters"** — each passage is a
    short scene (~300-1500 words) ending in a 2-4-choice decision
    point, identified by `passage_id` rather than chapter number.
    `books/<name>/passages/p_NNN.md` instead of `chapters/`.
  - **`/autonovel:cyoa-graph --book <name>`** mechanical helper renders
    the passage graph (Graphviz dot, or a Mermaid block for inline
    docs); flags dead ends (passages with no exits) and unreachable
    passages (no incoming edges). Same shape as the existing
    `/autonovel:graph` summaries surface but for CYOA topology.
  - **Evaluator rubric per passage** — different dimensions: choice-
     differentiation (do the choices feel meaningfully different?),
     consequence-fidelity (does the outcome reflect the choice?),
     dead-end-justification (is the dead end a satisfying ending or
     a feel-bad lose-state?), graph-balance (no choice should
     trivially dominate; player agency must be real).
  - **Foundation files unchanged** — `shared/world.md`, `characters.md`,
     `canon.md` carry over verbatim. Canon discipline becomes
     branch-aware: facts established in one branch may or may not be
     true in others (e.g. "the dragon was killed in branch A" is
     not canon for branch B). New `## Branch-scoped` block in
     `shared/canon.md` with passage_id provenance per fact.

  Output shapes — three:

  - **Print PDF** — classic Bantam/CYOA shape: every passage numbered,
    "If you choose X, turn to passage 47. If you choose Y, turn to
     passage 12." Reader physically flips. typeset emits a permuted
     passage order so consecutive passage numbers in the printed book
     don't reveal the graph structure.
  - **ePub with linked navigation** — same content, but each choice
     is a hyperlink. Inert without a page-turning device.
  - **Interactive web page** — the natural fit; reuses the
     `/autonovel:web-build` infra from the entry above (audio
     narration + clickable choices + path-tracking + "show me the
     graph" reveal at the end).

  Cross-cutting:
    - **Story-time gating** (the existing context-loader rule that
      drafters only see prior chapters) needs branch-aware extension:
      a passage being drafted only sees passages on its prior path,
      not other branches. Existing `context_loader.py` is shaped
      around chapter linearity; CYOA needs path-aware graph traversal.
    - **Audiobook synthesis** maps cleanly — each passage gets its
      own audio file + a JSON branch-table for the player to navigate.
    - **Quizzing** (from the interactive-web entry) doubles as a
      good fit — "what choice did you just make and why?"

  Cost: ~30-40 hr for the authoring side (mode + drafter + outline
  graph + evaluator rubric); ~15 hr for the print-PDF permuted-order
  exporter; web-build reuse adds ~5 hr on top. Pairs naturally with
  the interactive-web milestone above — best done together so the
  most engaging output (web with audio + quizzing + branching) ships
  as a single coherent slice.

  Open question: should CYOA share the `passages/` shape with
  parser-IF / Twine-style hypertext fiction, or stay novel-shaped?
  Twine's `.twee` source format is a plausible interchange shape;
  importing/exporting `.twee` would let authors round-trip with
  the existing CYOA toolchain (Twine, Inform 7).

## Free / no-API-key cover and ornament generation

- **Local Stable Diffusion provider — `--provider local-sd`.** The
  Pollinations.ai option (shipped 2026-04-30) is free + no key
  but is rate-limited and quality varies per request. A truly
  free alternative is local SD via the `diffusers` Python package
  (or A1111 / ComfyUI HTTP). New optional extra `[local-art]`
  pulls in `diffusers + transformers + torch`; bigger install
  (~5 GB model weights) but unlimited use thereafter. Should
  detect CUDA / MPS / CPU and fall back gracefully; CPU works but
  is slow. `autonovel install-export-tools --exports cover-local`
  walks the user through the model download. Cost: ~5-7 hr
  (provider implementation + install-tool flow + Tier-1 tests
  with mocked diffusers + doc). Hold for users who hit
  Pollinations rate limits or want offline-first operation.

- ~~**Wikimedia-Commons public-domain art provider — `--provider
  wikimedia`.**~~ **Shipped 2026-04-30.** New helper
  `src/autonovel/export/wikimedia.py` with three-step API:
  `search_images(query)` → `fetch_image_metadata(file_title)` →
  `download_and_crop(details, target_size, output)`. Two CLI
  subcommands `autonovel mechanical wikimedia-search` (returns
  candidates as JSON; `--detailed` includes full per-candidate
  metadata with one extra HTTP call each) and `wikimedia-fetch`
  (downloads + center-crops one image to the target aspect via
  Pillow LANCZOS resampling). Strict PD/CC0 default; pass
  `--allow-non-pd` for CC-BY content (caller responsible for
  attribution). The slash-command `/autonovel:art-curate
  --provider wikimedia` body documents the search → user-picks →
  fetch flow. 12 new Tier-1 tests with httpx.Client stubbed
  for offline runs. Tier 1+2: 1381 → 1393.

- **Pollinations.ai prompt-tuning loop.** The free
  Pollinations.ai endpoint lacks the prompt-engineering knobs
  (negative prompt, guidance scale, sampler) that paid providers
  expose. Quality depends entirely on the prompt. A future
  helper could iterate: generate 3 variants per direction, pick
  the highest CLIP-similarity to the prompt mechanically (or via
  a second LLM judge call), retry once with a tightened prompt
  if all 3 are below a threshold. Adds robustness on a free
  provider where bad rolls are common. Cost: ~4-5 hr.

## Maintenance

- **`state.json` never leaves `seed`, so `_end` offers to draft a chapter
  past the book's end (2026-10-22).** kingmaker2 finished draft-pass at
  ch 19 of a 19-chapter outline, and `_end` printed **Next:**
  `/autonovel:draft 20`. Its `state.json` still read `phase: seed`,
  `chapters_drafted: 0`, `chapters_total: 0`: `scaffold.py` writes
  `chapters_total: 0` and nothing (gen-outline, draft, draft-pass) updates
  it, so `next_step`'s "all chapters drafted" branch
  (`s.chapters_total and n >= s.chapters_total`) never fires. Fix: take
  `chapters_total` from the outline's `## Chapter N` headings when the
  state says 0 (gen-outline could also write it), and have draft-pass's
  close set `phase: revision`. The whole-book step after the last chapter
  is `/autonovel:developmental-edit`, not `adversarial-edit all`.

- ~~**Token + cost tracking.**~~ **Shipped 2026-04-28.**
  `command_log.LogEntry` gains optional fields: `book`, `model`,
  `tier`, `input_tokens`, `output_tokens`, `cache_read_tokens`,
  `cache_creation_tokens`, `cost_usd`. All optional — emitted
  to JSON only when populated so historical entries stay
  readable. `autonovel _end` accepts matching CLI flags
  (`--tier`, `--input-tokens`, `--output-tokens`,
  `--cache-read-tokens`, `--cache-creation-tokens`,
  `--cost-usd`); the postamble template instructs the runtime
  to forward whatever the session's usage report exposes.
  `lifecycle.end` now accepts a `usage` dict and threads it
  through to `command_log.append`. New `autonovel cost` CLI
  subcommand + `src/autonovel/cost.py` helper roll up
  per-book / per-tier / per-command totals with markdown +
  JSON output. Mechanical-only commands count as $0 runs and
  are surfaced separately from heavy / standard / light. 18
  Tier-1 tests covering log round-trip, partial telemetry
  (tokens but no cost), aggregation by book / tier / command,
  unknown-cost runs, error-runs, mechanical-runs, render
  shapes, lifecycle wiring, CLI happy paths. Tier 1+2: 1056 →
  1074.

- **Token + cost tracking — pricing table follow-up.** The 2026-04-28
  shipment surfaces whatever the runtime reports. Not yet
  done: an in-repo pricing table that maps (model, tier) →
  USD/1Mtok so a postamble can compute `--cost-usd` even
  when the runtime omits it. Hold for now — manual cost
  estimation is brittle and varies across plans
  (subscription vs API; with vs without prompt caching);
  better to display exactly what the runtime reports.

- **Token + cost tracking — `autonovel status` budget surface
  follow-up.** The 2026-04-28 shipment delivers `autonovel cost`
  (separate command). A natural extension is a one-line cost
  summary in `autonovel status` so the daily-checkpoint flow
  surfaces it without a second invocation. Cheap (~30 min):
  call `cost.build_report` from inside `_cmd_status` and add a
  one-liner like "spent $X.XX across N runs (M today)".
- **Bells Tier-4 fixture populate.** Copy the final Bells chapters
  from the `autonovel/bells` branch into
  `tests/fixtures/bells-reference/` and freeze `scores.json`.
  Standalone one-off; the harness is already in place.
- **Codex Tier-3 spot-check on a Codex-equipped box.** Has run on
  the dev machine; rerun in CI once a Codex CLI runner is available.
- **Gemini Tier-3 spot-check on a Gemini-equipped box.** Skipped on
  the PR-8 dev box because `gemini` was not on `$PATH`. Adapter has
  full Tier-1 coverage; just needs an end-to-end run.
- ~~**`autonovel doctor --fix` for missing external CLI tools.**~~
  **v1 shipped 2026-04-30 PM** as `autonovel doctor
  --install-missing` (semantically clearer than `--fix-tools`;
  parallel to `install-export-tools --apply`). Detects missing
  export tools via `doctor.missing_export_tools()`, builds an
  install plan via `install_export_tools.plan()` filtered to
  the missing-tools subset, hands off to `apply()` with per-
  tool confirmation (or `--yes` to skip prompts). Pairs the two
  flows: `doctor` reports issues, `doctor --install-missing`
  fixes the export-tool subset in one command. 2 new Tier-1
  tests cover the helper + present-tools-excluded path.

- **`autonovel doctor --fix` — original entry follows for context.** Today
  the doctor reports them; could shell out to brew/apt to install on
  approval. **Caveat from author testing 2026-04-25:** naïve `apt
  install` of `tectonic` on Chromebook/Debian frequently fails or
  installs a too-old version that autonovel can't use. A real
  `--fix` mode would need (a) per-OS install command tables, (b) a
  per-tool fallback chain when the package-manager version is broken
  (tectonic → apt → prebuilt static binary), and (c) post-install
  re-verification (run the binary, confirm version) rather than just
  checking `which`. Probably better as a separate `autonovel
  install-export-tools` subcommand than a `doctor` flag, since the
  scope is "set up an environment" not "diagnose a series".

- ~~**`autonovel install-export-tools` interactive helper.**~~
  **Shipped 2026-04-29 PM** as commit `1baae2c`. New CLI
  subcommand `autonovel install-export-tools [--exports
  pdf,epub,cover,audiobook,art] [--apply] [--yes]`. Detects OS
  (macos/debian/fedora/arch/other from /etc/os-release) and
  install method (pipx/pip/editable). Maps user-facing exports
  to per-tool install plans, deduping shared tools. Each tool
  has a per-OS install command list, optional notes (e.g.
  apt-tectonic too old → upstream prebuilt), and a `verify`
  command run after install to catch too-old binaries that
  `which` would falsely report as OK. Python pkg installs
  (Pillow / pydub) emit `pipx inject autonovel <pkg>` when
  pipx-installed, else `pip install <pkg>`. Default mode prints
  the plan; `--apply` runs with per-tool confirmation. New
  helper `src/autonovel/install_export_tools.py`. 16 new Tier-1
  tests. Tier 1+2: 1207 → 1223. Doc sync in operating-guide §3b.
  Original entry follows for context:

- **`autonovel install-export-tools` interactive helper.** Surfaced
  by 2026-04-25 author testing: writers hit real pain getting
  tectonic + Pillow + ffmpeg installed on Chromebook ("for a writer
  this stuff is too hard"). New subcommand asks the user which
  exports they want (PDF? cover? audiobook?), detects the OS,
  prints the exact commands they need (or runs them with
  confirmation), and handles the known special cases (tectonic
  fallback to prebuilt binary on Linux; `pipx inject` for `Pillow`
  / `pydub` when autonovel was installed without `[export]`
  extras; per-OS font install hints for cover rendering). Goal:
  zero shell debugging for the export path — the writer answers
  three questions and gets working tools. Cost: ~2-3 hrs.
- **Drift on `commands/*.md` frontmatter schema.** When `argument-hint`
  or `model_tier` semantics change, the contract test catches usage
  but not field shape. Add a JSON-schema file at
  `src/autonovel/validators/command_schema.json` and a Tier-1 check.

## Portability

- **Real `npm publish` flow.** `package.json` and `bin/autonovel.js`
  are scaffolded but the package has not been published; verify
  `npm install -g autonovel` and `npx autonovel install` actually
  work on a clean box. Probably needs `prepublishOnly` to bundle the
  Python source via a build step, or a postinstall pipx hook.
- ~~**`autonovel install --dry-run`.**~~ **Shipped 2026-05-01.**
  See the Maintenance section above for full notes.
- **Per-runtime tool-name regression test.** Tier-1 already
  golden-files each adapter; add a fuzzer that random-generates
  command bodies and asserts no double-translation happens.
- **Windows path handling.** Adapters use `pathlib`, but the install
  destinations (`~/.claude/commands/...`) and the bash preamble assume
  POSIX semantics. Smoke once on a Windows runner before claiming
  cross-platform support.
- ~~**`project.yaml :: image.provider`** is referenced in
  `commands/art-curate.md` but not yet read by any code.~~
  **Shipped 2026-05-01.** `ProjectConfig` gains an `image` dict
  (round-trips in YAML, omitted when empty). New mechanical helper
  `autonovel mechanical resolve-image-provider [--project-yaml ...]
  [--cli-provider ...]` applies the precedence rule (CLI override
  → `project.yaml :: image.provider` → `pollinations` default) in
  one place; both `commands/art-curate.md` step 1 and
  `commands/art-ornaments-all.md` step 1 invoke it instead of
  re-implementing precedence. Helper degrades cleanly on missing /
  malformed project.yaml. 8 new Tier-1 tests covering YAML round-
  trip + each precedence path + missing-file fallback.
- **uv vs pip.** Repo currently has `uv.lock`; CLAUDE.md says
  `pip install -e .[test,export]`. Pick one canonical path or
  document both.

## Testing

- **Per-runtime smoke matrix in CI.** Today CI is Tier 1+2 only. A
  weekly cron that runs Tier-3 against Claude Code on a
  subscription-auth runner would catch runtime-version drift early.
- **Genre-fixture matrix runner.** `pytest --genre-matrix` (referenced
  in REWRITE-PLAN §12a) is not yet implemented. Today users run one
  fixture at a time via `autonovel test-fixture run <name>`.
- **`pytest -m 'genre("mystery")'` parameter selection.** The
  `genre(name)` marker is registered in `pyproject.toml` but pytest's
  `-m` parser doesn't filter by argument by default. Either add a
  pytest plugin/hook that reads the genre name out of the marker, or
  update docs to recommend `-k <genre>` instead.
- **Adapter round-trip test for the Codex `auth.json` rewriting.**
  The PR-8 smoke test redirects `CODEX_HOME` and copies the user's
  real `auth.json` into the redirected home — fragile. Add a Tier-1
  unit test that exercises the env-redirection path against a
  fake `auth.json`.
- **Mechanical-module pyproject extras smoke.** The `[export]` extras
  pin Pillow + pydub but no test imports them — a dependency drift
  in those packages would only surface at export time. Add a
  smoke import-only test gated on `[export]` being installed.
- **Flakiness budget.** `tests/flakiness.jsonl` is append-only with
  no rotation. Add `autonovel test-fixture trim-flakiness --keep N`
  or a `pytest --strict-flakiness` mode that fails when a test has
  flipped > N times in the last K runs.

## Typeset toolchain gotchas found on the kingmaker build (2026-10-16)

1. **WOFF fonts break xdvipdfmx.** On Debian/Ubuntu `fonts-ebgaramond` installs
   TTF, OTF *and* WOFF copies; fontconfig may hand tectonic the WOFF italic
   (`Cannot proceed without the font: /usr/share/fonts/woff/ebgaramond/...`).
   Fix used: a user `~/.config/fontconfig/fonts.conf` rejecting
   `/usr/share/fonts/woff/*`. `autonovel doctor` should detect WOFF-only
   matches (`fc-match "EB Garamond:italic"` ending in `.woff`) and print this
   fix; `install-export-tools` could write the rule.
2. **EB Garamond 12 Bold lacks glyphs** (ü, curly apostrophe), so TOC lines
   for titles like "Jüterbog" or "Man's" lose characters. Fix used in the
   per-book novel.tex: `BoldFont={EB Garamond 12 Regular}` with
   `BoldFeatures={FakeBold=1.4}`. The template `typeset/novel.tex` should
   adopt this (or test glyph coverage) so every book gets it.
3. **ePub metadata template paths.** `typeset/epub_metadata.yaml` carries
   `css: ../../../typeset/epub_style.css` and `cover-image: ../art/cover_titled.png`
   relative to the book's typeset dir, but pandoc resolves them against the
   cwd (the series root), so the css line aborts the build and the cover line
   fails when a book has no art. The typeset command should drop both lines
   when rendering `metadata.yaml` (it passes `--css` and `--epub-cover-image`
   itself) and pass `--metadata title=… author=…` explicitly, since pandoc
   still warned about a missing `<title>` with the metadata file alone.
4. **No `autonovel mechanical build-epub-metadata` helper exists**; the
   command text says metadata.yaml is "assembled on the fly" but leaves it to
   the LLM. Add the helper.

## Audiobook: free local TTS provider + two bugs (found on the kingmaker audiobook, 2026-10-17)

1. **`audiobook-generate` only knows ElevenLabs.** A free local provider is now
   proven: Kokoro-82M (Apache-2.0) in a Python 3.12 env renders ~35x real time
   on an RTX 5060 Ti with Whisper WER ~2%; the single-narrator renderer and
   assembler used for kingmaker live in the series repo at
   `books/kingmaker/audiobook/tools/`. Add `provider: kokoro` to `voices.yaml`
   and the generate command (voice ids like `bm_george`; paragraph/scene
   pauses; chapter heading spoken), and make `audiobook-assemble` loudnorm to
   −19 LUFS and attach `art/cover_titled.png`. Qwen3-TTS 1.7B was 0.6x real
   time without flash-attn; chatterbox-tts does not import on Python 3.13.
2. **`autonovel mechanical audio-marks --format ffmetadata` returns JSON**
   (same output as `--format json`), so `audiobook-assemble --format m4b`
   would embed no chapters. Fix the formatter and add a Tier-1 test that the
   ffmetadata output starts with `;FFMETADATA1` and has one `[CHAPTER]` per row.
3. **`.gitignore` template** ignores `books/*/audiobook/*.mp3` but not
   `books/*/audiobook/chapters/*.mp3`, where `audiobook-generate` writes;
   add the recursive patterns (and `_work/`).
4. **Light-cast multi-voice edition with Kokoro (deferred 2026-10-17; revisit
   when the next Kokoro voice release lands).** The pipeline already has the
   design (`audiobook-voices` → `voices.yaml`, `audiobook-script` →
   speaker-attributed segments with the narrator keeping the tags); only the
   renderer needs per-segment voices and the ElevenLabs emotion tags
   (`[slowly]` etc.) must be stripped or Kokoro reads them aloud. Blocker is
   voice quality, not count: Kokoro's British set is 8 voices (4f/4m) plus
   blending, but only bf_emma, bm_george and bm_fable are clean; the other five
   are muddy, and mixing in American voices breaks the accent. Industry norm is
   single narrator (duet only in romance/YA; full cast a niche), and kingmaker's
   narrator is the book's main instrument, so when revisited do a *light cast*:
   narrator on all narration and tags, own voices only for ~5 principals
   (Jakob, Sibylla, Ulrich, Maximilian, +1), everyone else on the narrator.
   Dialogue is 25% of the book by words (~3 of 12 h). Trial first: render one
   dialogue-heavy chapter both ways and listen before committing the book.

## Reader-facing diff: follow-ups (core shipped 2026-10-17 as `/autonovel:diff`)

- **Renumber-aware chapter matching.** Chapters pair by file number, so a
  diff across `reorder` / `merge-chapters` / `split-chapter` /
  `remove-chapter` shows a renumbered chapter as rewritten. When the chapter
  set or numbering changed between the two versions, pair old and new
  chapters by content similarity first.
- **PDF mode** — changebars in the typeset build (HTML came first).
- **Surfacing.** A LOW `/autonovel:next` signal ("N chapters changed since
  your last read → `/autonovel:diff --from last-read`"), and let
  `/autonovel:talk` answer "what changed in ch 21 since draft_1?" from the
  diff JSON.
- ~~**Revised samples go back to the author as a diff, every time
  (2026-10-18).**~~ **Done 2026-10-18.** The author re-read the
  third-draft kingmaker2 ch 1–2 in full because the page showed only the
  clean text. Now `revise` (step 12), `draft` on a redraft (step 15) and
  `revision-pass` (once per sweep) run `diff-chapters --from last-read
  --if-read` and name the page; `--if-read` writes nothing unless the
  author's bookmark resolves and the chapter was in that version. Every
  feature of the page built by hand that day is in the helper's page: a
  plain **what** note per change (with the *why* under it) and a **big**
  flag from `--annotate`; **Changes / Whole chapter / Clean text** views,
  remembered; a **big changes only** filter (size fallback: 40+ words or
  a moved paragraph) with the big ones listed under each chapter heading;
  **rewritten paragraphs** as new text with a "show the earlier draft"
  fold (the same 50%/4 and 60%/10 rule); **italics** rendered at the token
  level; dark mode through `data-theme`-aware tokens; next/prev stepping
  by index with an IntersectionObserver resync, a measured toolbar offset
  and a brief highlight. Also: pairing inside a hunk now sums similarity
  ratios over the whole hunk (no diagonal band), so a paragraph pushed
  down past new ones pairs with itself and a neighbour sharing a few
  words is no longer glued on as a "split"; a `--chapters` page is named
  `diff_<from>_<to>_chNN-MM.html`.
- **The hand-back page could carry its notes (2026-10-18).** `revise` has
  the brief in context when it hands the chapter back, so it could write
  the `what` / `why` / `big` sidecar for its own page (the notes are the
  part the author skims) instead of leaving `--annotate` as a second run.
  Cost: a few hundred output tokens per revise; decide whether
  `revision-pass` subagents should each return their notes for the
  sweep's one page.
- **Diff page, small leftovers.** Under the big-changes filter the hunk
  head still reads "Change 10 of 56" while the toolbar counter reads "2 of
  27" (the head is the change's identity; consider showing both). When
  only some changes of a chapter are annotated, the chapter's big list
  mixes note-flagged and size-flagged changes under one heading.

## Story-map follow-ups (story-map shipped 2026-10-17)

- `/autonovel:dashboard` (and the TUI sparkline) read `tension` only from a
  `--full` eval log; kingmaker's per-chapter logs carry `tension` for ch 1–9
  but the dashboard shows none. story-map already falls back to the
  per-chapter field (`_index_latest_per_chapter_eval(key="tension")`); the
  dashboard could do the same.
- `/autonovel:dashboard` shows only `overall_score` per chapter. The author
  asked (2026-10-22, kingmaker2 ch 3–18) for "a table of the current scores
  across several metrics", and the answer took a script over
  `eval_logs/ch*_eval.json`: the 15 `dimensions.*.score` values, the
  first reader's serious-item counts (`first_reader.serious_items_first` /
  `_second`), and `weakest_dimension`. Add `--dimensions` (two tables,
  story and writing, plus a mean row and a count of each chapter's weakest
  dimension) so the author can get the table from autonovel. Older logs lack
  `first_reader` and `dimension_mean`; compute the mean, show `—` for the
  first reader.

## Book-level structure tier: leftovers (after `/autonovel:structure-review`, 2026-10-17)

The audit requested here shipped as `docs/reviewer-audit.md` plus
`/autonovel:structure-review`, the `kind: structural` brief, the
structure-weighted `evaluate --full`, the gated `review` stop rule, the
panel's book-level questions and `gen-outline`'s spine sections. Left:

1. **Calibrate on real books.** The rubric caps in
   `mechanical/structure_review.py` (because-ratio 0.50 / 0.65 / 0.80,
   removable ≥ 25%) are first guesses. Run the reviewer on kingmaker
   (expected: gate BLOCK, `anecdote-chain`) and on one book the author
   reads as a continuing story; adjust the thresholds and the scoring
   anchors in `commands/structure-review.md` together (the contract test
   `tests/contracts/test_structure_review_contract.py` pins them).
2. **Canonical footer.** `housekeeping/next_step.py` still routes the
   revision phase panel → brief → review; the structure gate is only in
   `/autonovel:next`'s situational actions, `review`'s verdict and
   `run-pipeline`. Add a `structure_review_done` / `structure_gate`
   field to `PipelineState` (filled by `lifecycle._next_step_for` from
   `structure-validate`) so the postamble's **Next:** line names
   `/autonovel:structure-review` before `/autonovel:review`.
3. **Story-map view of the structure review.** `/autonovel:story-map` is
   on master; render `structure_review.json`'s causal chain (because /
   after / unrelated per seam), the stakes ladder and the removable
   chapters next to the thread view, so "does it build" is one glance.
4. **Series level.** `evaluate --phase series` and `series-arc` have no
   cross-book causal chain or ladder; a series whose books are each
   self-contained is the same failure one level up.
5. **Calibration from the first real run (kingmaker, 2026-10-18: 2/5,
   gate BLOCK) against a full editor's read (`books/kingmaker/edit_logs/
   editor_letter.md` in the series).** The reviewer caught the shape the
   old reviewers missed, but:
   - It scores plot causation only. Chapters whose load is a relationship
     (kingmaker 13, 14, 18: the Trevisan reveal, Tucher's confession,
     Sibylla's grey) came out "weak"/"removable". Add character causation to
     the link and removability tests: a chapter is load-bearing if a later
     chapter's choice depends on the state of a relationship it changed.
   - Narrator prolepsis was one failure mode among five; on the editor's
     read it was the main cause of the "anecdotes" experience (19 of 24
     chapters). Add a measured `prolepsis_density` (chapters with a
     flash-forward past their own story time) to the dossier and make it a
     cap when high.
   - Some candidates would raise the because-ratio by breaking the book's
     declared spine (S2: Jakob tells Tucher the secret price). Candidates
     must be checked against the seed/voice spine and theme; a linking
     sentence at a joint is not a fix, a new chapter opening is.
   - It dismissed the book's own frame ("what is he worth?" → the inventory
     with no total) as `motif-spine`. A frame that poses a present-time
     question is a structural device; distinguish it from a recurring image.
   - Second calibration (after the stage-B revision, 2026-10-18): it
     counted a cause *stated in a chapter's opening recap paragraph* as
     "because" (its evidence for 9→10 was the catch-up sentence itself),
     so it rewards bridges; and it weights a two-year gap at a "because"
     joint as nothing. Rule to add: a "because" must be enacted by a
     person in the chapter's scenes; a recap that names the cause is
     continuity. It also has no line for the opposition's strength or a
     protagonist who always wins (the developmental-edit letter found
     both).
   - Prompt bugs the run reported: CRAFT.md section names wrong (§1/§8 are
     subsections); reads `review.json` but the dossier points at
     `review.md`; no rule for reviewer quotes of since-changed text; the
     `--template` lacks the historical-check, `reviewer_disagreements` and
     `delta_vs_previous` fields the workflow asks for; `priority`/`fixes`
     on candidates undefined; weak vs load-bearing boundary unclear;
     `posed_at_pct` uses chapter start with a strict `>25`; the 400k-token
     budget rule assumes the agent knows its window; the postamble
     telemetry paragraph has a garbled sentence.

## From the editorial-practice audit (2026-10-18): design before the outline

**Done 2026-10-18:** items 1 and 2 shipped as `/autonovel:design`
(`books/{book}/design.md`, study text `shared/craft/DESIGN.md`,
`autonovel mechanical design-validate [--outline]`), with `gen-outline`
(now heavy) and `draft` bound to it, a `design` dimension in `evaluate
--phase foundation`, the design step in the foundation order and
`/autonovel:next`, and the re-design loop as `--from-book` (routed to by
`developmental-edit` when its diagnosis is design-level). Left:

- **Calibrate on a real re-design.** The validator's thresholds (≥3
  plants spent by the climax, ≥2 rehearsals, 6–10 sequences, posed by
  25%) are first guesses; check them on the first book redrafted from a
  design, against its developmental-edit letter.
- **Revision bound to the design.** `revise` / `revision-pass` /
  `brief` do not read `design.md` yet; a brief that would break a plant
  or move the rival off stage should say so.
- **Story map shows the design.** `story_map.html` could draw the plant
  ledger (plant → test → payoff arcs) and the rival's appearances on the
  same chapter axis as the threads.
- **DESIGN.md sources.** Several claims are marked (unverified); verify
  them as EDITING.md's were.

- **Reader's-map scanners (from the author's first read of kingmaker2,
  2026-10-18: "I don't know what that style is"; "my first time hearing
  about electors"; "I didn't understand fustian"; "suddenly introduces
  several new characters and locations").** `draft` step 3c and the
  voice rubric now ask for plain words, first-use explanations, one new
  person at a time and an orienting first page; add candidate
  generators so the reviewer can see them: (1) DONE 2026-10-18 as
  `autonovel mechanical newcomers` (run by draft); (2) narration similes and idioms ("as if", "as
  though", "like a") as a review queue for books whose voice asks for
  plain English; (3) terms in design.md `## Terms` not yet explained by
  their chapter.

- **The author must never be the first reader (2026-10-18: "I am not a
  book editor or english major — I shouldn't be the one finding issues
  like this").** Shipped: `/autonovel:first-read` and the first-reader
  step in `draft` (FIRST-READER.md). Left: (1) `revise` and
  `revision-pass` should run the same reader on the revised chapter;
  (2) `voice-discovery` should offer the author two or three contrasting
  sample openings (plain / literary / pacy) to choose from instead of the
  designer choosing — "modern" was read as literary-modern when the
  author meant plain; (3) a cross-model first reader (a different model
  family) to cut self-preference; (4) the reader panel should run on the
  first chapters early, not only on the finished book.
  From the first real run (kingmaker2 ch 1–2, three readers each,
  ~670k tokens and ~65 minutes for two chapters): (5) the cold reader
  cannot catch fact slips it has no way to know (the design said "sixty"
  for a man who was fifty-nine that January), so draft needs a
  period-facts check: ages and weekdays computed from canon birth dates
  and the chapter's story_time, journey times checked against distances;
  (6) ~~orientation through the scene~~ shipped 2026-10-18 as draft
  step 3c's set piece and FIRST-READER's "Couldn't picture"; (7) cap the
  loop at two readers unless the second still finds someone lost, and log
  the cost.

- **Characters (2026-10-18, after `/autonovel:cast` shipped).** Left:
  (1) a front-matter cast list ("Principal characters", grouped, one line
  each, spoiler-free) built from `cast.md` return tags and typeset before
  the glossary — customary for historical novels with large casts;
  (2) `story-map` should read `cast.md` for its characters panel;
  (3) `structure-review` / `developmental-edit` should check each
  principal's pressure choices landed where `cast.md` scheduled them;
  (4) a `cast-validate` helper only if dossiers drift (field presence,
  return tags) — not a quality gate.

Smaller, from the same audit: cross-family judging for the whole-book
reviewers (self-preference, §5); a scene map with value/polarity; the
thriller contract checks (TH1–TH7); an aim test in `review.md`'s critic
stage (Updike rule 1); `structure-review` should read the prose before
the outline (ground rule order).

## developmental-edit: first-run fixes done, two left (2026-10-18)

Fixed after its first real run on kingmaker: the one-page test now runs
before the dossier (which carries the outline, summaries and scores); the
previous letter *and notes* are moved to mtime-stamped names unread;
ledger last, word cap excludes it; step references; no author quote in
the prompt or EDITING.md; `_resolve_writes` expands globs instead of
checkpointing a literal `…_*.md`. Left: (1) `autonovel _end` appends the
canonical "previous chapter met threshold; advance" rationale to
whole-book commands where it means nothing — `next_step` should not emit
a chapter-advance line for book-scope commands; (2) a `--stage` dry-run
test fixture, so the staging format is pinned by a test.


## CI: the Tier 1+2 workflow is disabled (2026-10-18)

The author disabled `.github/workflows/test.yml` on GitHub after months of
failure emails. It had failed on every push since 2026-06-06 only because
the workflow installs `.[test]` and not Pillow, which 18 teaser tests need
(locally `.[test,export]` is installed and the suite is green). Fix before
re-enabling: install `-e '.[test,export]'` in the workflow (or skip the
Pillow-dependent tests with `pytest.importorskip("PIL")`), then re-enable it
from the Actions tab.
