# Teaser craft — how to make a 1–3 minute AI-video teaser

> **Who this is for:** anyone using autonovel's movie-teaser mode —
> especially if you've **never made a video before.** It's the film-craft
> companion to [`CRAFT.md`](../CRAFT.md) (prose craft) and
> [`ANTI-SLOP.md`](../ANTI-SLOP.md). The teaser commands read this file
> the way the writing commands read CRAFT.md — it's *prompt material*,
> not just documentation. The build spec lives in
> [`prd-movie-teaser-mode.md`](prd-movie-teaser-mode.md).

A teaser sells a **tone and a question**, not the plot. Done right, a
90-second teaser made of cheap AI clips can feel like a real film. This
guide is the opinionated craft autonovel applies — every default here is
overridable, and `/autonovel:teaser-coach` will explain any of it in the
context of *your* story.

---

## 0. The story spine — do this *before* picking a single shot

The most common failure mode of an AI teaser is that it goes nowhere: a
set of pretty clips of the same characters standing where and when they
are, no question, no stakes, nobody saying anything that tells you what the
story *is*. The fix is upstream of the visuals — fix the **spine** first,
then every beat serves it. `teaser-beats` writes the spine into `beats.md`;
`shot-prompts` copies it into `teaser.json`; `teaser-critique` checks the
beats actually answer it. The six spine fields (Phase 6 best practices):

- **Dramatic question (bp 1)** — the ONE question the teaser poses and
  **never answers.** "Can a clerk outlast the bank that owns his country?"
  Every beat must advance or complicate it; a beat that doesn't touch the
  question is cut. This is the throughline that makes the cut *go
  somewhere*.
- **Logline (bp 6)** — the one-sentence premise the **text cards** carry.
- **Want + opposing force (bp 4)** — what the protagonist wants and the
  concrete force in the way. Conflict is the intrigue; without a stated
  opposition the teaser has nothing to escalate.
- **Turn / reversal (Phase 11)** — the ONE midpoint reversal that flips the
  story: the moment the viewer's read of the situation turns over (the ally
  is the enemy; the rescue is a trap; the victory costs everything). A teaser
  *without* a turn is a flat montage; this single beat is what makes it a
  micro-story. Name the real reversal from the story, stage it visibly at
  roughly the midpoint, and let it hold.
- **Emotional arc (bp 8)** — the tonal journey ("quiet unease → mounting
  dread → defiant hope"). The cut should *move* along it: hook holds,
  escalation tightens, button breathes.
- **Score direction (bp 8)** — the single building musical cue the whole
  cut rides (real trailers ride *one* score, not per-shot music; see §7 and
  `teaser-render --score`). It doubles as the **music-bed prompt**:
  `teaser-music` scores the bed from this line (`--provider stub` for an
  offline $0 placeholder, `musicgen`/`elevenlabs` for real audio), and
  `teaser-assemble --audio` ducks it under the dialogue.
- **Genre/tone (bp 9)** — what *kind* of story this is. The **hook must
  telegraph the genre in the first ~10 s** — a viewer should know they're
  watching a historical thriller (or a gothic romance, …) before they know
  the plot.

The arc the spine rides — enforce the **4-act order** and a **rising
ladder**:

- **4-act order (bp 2).** Exactly one **hook** (first shot, signals the
  genre) → **escalation** (the middle) → **title** (~⅔ in) → **button**
  (last). `teaser-critique` flags `hook-not-first`, `multiple-hooks`,
  `no-title`, `button-not-last`, `title-after-button`.
- **Rising stakes ladder (bp 3).** Give each escalation shot a
  `stakes_level` that strictly increases in shot order — the cut must
  escalate, not idle. `teaser-critique` flags `no-stakes-ladder` (unranked)
  and `stakes-not-rising` (dips).
- **Withhold the answer (bp 7).** The button deepens the question and never
  shows the resolution — that's what the film/book is for.
- **Restraint — scope without context (bp 10).** Cut any shot that is
  merely "the character standing where/when they are." Keep only shots that
  turn the question or imply a larger world. Do more with less.
- **One hero face (bp 11).** Build the teaser on ONE protagonist's stakes;
  ≤3 named faces, the rest silhouettes/crowd (no consistency lock needed).
  `teaser-critique` flags `cast-sprawl` above three named faces.

Two more best practices that turn the spine into something a viewer can
read:

- **Dialogue as payload, not ambience (bp 5).** A teaser must let you
  *hear* the story. Mine **3-6 of the highest-voltage lines** from the
  manuscript — a threat, a vow, a cost named aloud — adapt them short, and
  spread them across the arc (the sharpest just before the title/button).
  Generic chatter teaches the viewer nothing; loaded lines reveal a stake,
  a relationship, or the genre in one breath. (Only spoken on
  native-audio providers; otherwise carry them as text cards.)
- **Stakes ladder, not a montage of equals.** Order the escalation beats
  so each one's cost / danger / irreversibility exceeds the one before. If
  beat 6 isn't scarier than beat 3, re-order or cut.

`teaser-critique` raises `no-dramatic-question`, `no-logline`, `no-stakes`,
`no-emotional-arc`, `no-genre`, and `thin-dialogue` when these are missing —
treat them as must-fix, not advisory. (Phase 12: a text-card requirement was
*removed* — cards are a crutch; legibility is enforced by the viewer-blind
quality gate in §11, not by counting cards.) **They are the
render gate (bp 12):** `/autonovel:teaser-render` *refuses* to spend a real
generation while any of them is present (the offline `stub` backend and
single-`--shot` runs are exempt; `--skip-narrative-gate` overrides). You
literally cannot burn quota on a teaser that has no story — fix it for free
first, or validate the chain offline with `--provider stub`.

**Structure is the floor, not the ceiling (Phase 11).** Everything above
proves a teaser *has a story shape*. It cannot tell a **boring** teaser from
a gripping one — presence ≠ interesting. So there is a **second** render
gate: the *interestingness* rubric (§11). `/autonovel:teaser-critique` scores
the teaser 1-10 on eight dimensions (hook grip, question sharpness, stakes
escalation, character, dialogue quality, surprise/turn, coherence, button)
and writes `teaser/quality.json`; `/autonovel:teaser-render` refuses a real
generation unless it clears **overall ≥ 7 AND no dimension < 5**.
`/autonovel:teaser-revise` lifts the weakest dimensions and runs a de-boring
pass. "Boring" is now a measurable, blocking failure — see §11.

---

## 1. The words: beat → scene → shot → clip

Four terms, used consistently:

- **Beat** — one story turning point ("she discovers the ledger is
  forged"). A teaser is built from ~8–20 beats.
- **Scene** — a continuous unit in one place + time. A scene may hold
  several beats.
- **Shot** — one camera setup: one framing, one move. *This is the unit
  a video model renders.* One scene → many shots.
- **Clip** — the actual generated 4–10-second video for one shot.
  Usually 2–4 takes per shot; keep the best.

The pipeline: **story → beats → scenes → shots → clips → cut.**

## 2. The dual-audience problem (the one big idea)

A scene description has to satisfy two readers who want opposite things:

| Reader | Wants | Hates |
|---|---|---|
| **You** (editing) | meaning, emotion, why the beat matters | a dry list of nouns |
| **The video model** | concrete visible nouns, one action, present tense, what's literally in frame | interiority, abstraction, metaphor, backstory |

So each shot is written **twice**: a one-line *beat note* you understand,
and a *shot prompt* the model obeys. Example:

- **Beat note:** *Tommaso realises the accounts don't balance — the
  moment the conspiracy becomes real to him.*
- **Shot prompt:** *Medium close-up, low-angle. TOMMASO (late 20s,
  ink-stained fingers, plain woollen doublet) snaps the ledger shut, jaw
  tightening, one slow exhale. Candlelit counting-house, ledgers stacked
  behind. Warm low-key light, amber/walnut palette. Slow push-in. 85mm,
  shallow depth of field. Shot on 35mm film. Tense.*

## 3. Externalise interiority (film shows; it can't narrate)

Novels live in thought ("she wondered if he'd betray her"). A camera can
only show **behaviour**. Convert every interior state into a visible
action:

- *anxious* → grips the table edge, jaw tight, one hard swallow
- *suspicious* → eyes flick to the door, hand drifts off the cup
- *triumphant* → the smallest smile, shoulders drop

(This is the same show-don't-tell discipline the writing pipeline uses —
run forward: interiority → action.)

## 4. Rules for a shot description the model will obey

- **One subject doing one thing; one camera move.** Multi-action clips
  fall apart.
- **Present tense, active, concrete.** "Rain hammers the cobbles," not
  "it had been raining."
- **Only what's in frame.** No backstory, no off-screen cause, no
  "because."
- **No un-filmable abstraction.** "Her world collapses" → pick the
  visible image that *means* that.
- **Name the subject identically every time** — reusing the exact
  appearance words keeps the character consistent across clips.
- **No legible *overlay* text** — title/subtitle/caption cards are burned in
  at the editor / `teaser-assemble --burn-titles`, not set by the model
  (models garble type). **But diegetic writing that IS the subject — a
  ledger of accounts, a letter, a map, a signboard — is legitimate scene
  content; keep it.** So for a shot whose subject is written material, do
  **not** put `text` / `letters` / `words` / `numbers` in its
  `negative_prompt` (that would blank the very thing the shot is about) —
  describe the writing ("columns of ink figures, a tally that doesn't
  balance") and only negative-prompt the failure modes (`blurry, distorted
  hands, watermark, modern typography`). The render only auto-suppresses
  overlay *title* type on `role: title` shots, never diegetic writing.
- **No real people or trademarked characters** (also a competition-rules
  issue).

## 5. Cinematography words that actually work

Use *these* terms — the models are trained on them:

- **Shot sizes:** extreme close-up · close-up · medium · wide /
  establishing · over-the-shoulder · POV · two-shot.
- **Angles:** eye-level · low-angle · high-angle · bird's-eye · dutch.
- **Camera moves:** static · pan · tilt · dolly in/out · truck · zoom
  in/out · crane · aerial/drone · handheld · orbit · push-in / pull-out
  · dolly-zoom (vertigo).
- **Lens/optical:** wide-angle · telephoto · shallow depth of field /
  bokeh · rack focus · lens flare · "85mm" / "35mm handheld".
- **Lighting:** golden hour · moonlight · firelight · neon · low-key ·
  high-key · Rembrandt · film-noir shadows · volumetric rays ·
  backlight/silhouette.
- **Look / film stock:** "shot on 35mm film" · anamorphic · "cinematic
  film look" · era looks ("1980s vaporwave", "1920s sepia + grain").
- **Palette:** name **3–5 colour anchors** ("amber, cream, walnut") and
  hold them across every shot — this is what makes the edit seamless.
- **Temporal:** slow-motion · time-lapse.

autonovel pulls the era look from your `project.yaml` period/region and
the palette/grade from `art/visual_style.json`, so you don't type these
by hand. It also renders the prompt in each provider's **dialect** — full
prose for Veo/Sora (and the generic/Pollinations default), terse
comma-separated keywords for Runway, a concise description plus a Luma
camera-motion enum for Luma — automatically from `--provider`. Same
facts, the shape each tool wants.

## 6. Keeping a character consistent across clips

The hardest part. The workflow that works:

1. Generate a **canonical reference image** of each character and key
   location first.
2. Feed that image as the **reference / first frame** of every clip with
   that subject.
3. **Reuse the exact appearance description** in every prompt.
4. Hold **lighting logic + the 3–5 colour palette** identical.
5. Chain **last frame of one clip → first frame of the next** for
   continuous action.

Honest caveat: identity still drifts sometimes. Reference images reduce
it; they don't perfect it. Lean on them and pick the best takes.

**Locations + age (Phase 7).** Lock **places** the same way you lock faces:
`teaser-refs --with-locations` scaffolds one reference plate per distinct
setting, so the same place recurs *and* renders period-correctly — declare
a period-accurate source (the wooden Rialto, not the 1591 stone bridge) to
dodge the anachronism a naïve search returns. For a character who **ages**
across the story, give them an `appearance_ages` ladder (boy 14 → youth 18
→ man 40 → elder 62, parallel to the `voice_ages` voice ladder); the render
picks the age-correct appearance text for each shot's `story_year` so the
prompt matches the life-stage plate. With `--refs`, approved character AND
location plates flow into the image *and* video backends (a shot with no
keyframe uses its primary plate as the image-to-video start frame).

`/autonovel:shot-prompts` assigns each recurring subject a canonical
reference path (`teaser/refs/<name>.png`) and runs
`autonovel mechanical teaser-refs-plan`, which tells you exactly which
reference images you still need to make, which shots use each, and
whether a `shared/art_references/` plate already covers one — so you're
never grepping the refs dir by hand.

## 7. Creative defaults — your first-timer questions, answered

Opinionated starting points (all overridable; `/autonovel:teaser-coach`
explains each against your story).

### How long is a shot? a scene? the teaser?

| | Default | Why |
|---|---|---|
| One **shot** | **2–4 s** | Clips are short; trailers cut fast. Over-generate, pick best. |
| The **hook** | one **4–6 s** shot | The opening image needs room to land. |
| **Escalation** cuts | down to **1–2 s** | Accelerating cuts = rising tension. |
| **Final image** | **3–5 s** hold | Let the last beat breathe. |
| **30 s** teaser | **~8–12 shots** | Good debug size. |
| **3:00** teaser (X-Prize) | **~35–60 shots** | The competition target. |

### How many characters?

**One hero face; at most 2–3 named faces total.** More faces = more
identity drift and less emotional clarity. A teaser sells *one* person's
stakes. Crowds, silhouettes, and backs-of-heads are free — they don't
need consistency locking.

### How do I hook people in the first 5 seconds?

Pick one — and **intrigue, don't explain** (no exposition up front):

- the **strongest single image** in your world;
- a **dramatic question** — a situation that demands "…what happens
  next?";
- a **provocative line** (text card or one spoken line) — *"They told us
  the war was over."*;
- **disorientation → orientation** — a strange close-up, then pull out
  to reveal the world.

### The ending — do I hint at it or keep it a surprise?

- **Default: tease the *question*, withhold the *answer*.** Show the
  stakes and the world; never show the resolution. End on the unanswered
  question, or a "button" (a final hook *after* the title card) that
  deepens the mystery.
- **For the X-Prize:** the brief asks you to "show a future worth
  building," so the **vision** is often the point — **reveal the vision,
  withhold the journey.** Show the hopeful destination; hint that
  humanity *earns* it through struggle; hide the road.
- **Never** spoil a twist or the final emotional beat — that's what the
  film is for.

### Other sensible defaults

| Knob | Default | Note |
|---|---|---|
| Aspect ratio | **16:9** | Festival/competition standard; `9:16` for social. |
| Audio | music bed + 1–2 dialogue stings + SFX | Music carries a teaser; dialogue is sparing. |
| Text cards | **2–4 short cards** | Carry narrative cheaply; dodge AI lipsync. |
| Title card | at **~⅔** point | Brand beat before the button. |

## 8. Teaser structure (the shape of the 60–180 s)

1. **Cold hook (0–10 s)** — one arresting image or line.
2. **Escalation montage (10–60 s)** — accelerating shots, rising stakes,
   intercut with text cards; pacing tightens.
3. **Title card** (mid or ~⅔ in).
4. **Button / stinger (final 5–10 s)** — a last shock or unanswered
   question after the title.

**Music and sound design carry a teaser.** Build to a drop on the title
card; let text cards do narrative work; ramp from longer opening shots to
quick escalation cuts, then hold the final image.

## 9. When the model misbehaves

Common failures: morphing/identity drift, flicker, extra/melting limbs,
garbled text, physics breaks, unwanted camera drift.

Fixes that reliably help: use reference/first-frame images; one action +
one camera move + a short clip; render text in the editor not the model;
higher resolution; change one thing at a time; and a **negative prompt**
written as content words — `blurry, distorted hands, extra limbs,
watermark, text, subtitles, flicker, morphing`. **Never** write "no
walls" / "don't show…" *inside the scene description* — the model reads the
content words, so inline negation backfires; the negative belongs in its
own labelled section, which `teaser-render` now appends automatically (it
was previously authored but dropped).

**Title plates never set type in the model.** A `role: title` shot renders
**without an overlay title**: `teaser-render` auto-injects a *narrow*
overlay-title negative (`title text, movie title, caption, watermark, …` —
NOT broad `text`/`letters`, so a vellum/ledger title plate keeps its ruling
and diegetic marks) and the title is **burned in at assembly**
(`teaser-assemble --burn-titles`). This is the fix for the classic "model
stamps a wrong/garbled title" failure, and it is title-only — content shots
of ledgers/letters keep their writing (see §4). The vision critique's
REGENERATE verdicts are re-rendered automatically on the free `stub`, and on
a paid backend only with `teaser-render --auto-regenerate` (inline, capped
by `--max-regen`) or `teaser-render --revise` (a separate re-run that reads
the persisted `clips/render-report.md` so you can review the suggestions
first) — so a re-render loop never quietly runs up a bill.

## 10. The commands

The craft above is applied by these commands:

1. `/autonovel:treatment --book <name>` — film treatment + 2-page brief
   (reveals the ending; X-Prize-shaped by default).
1b. `/autonovel:teaser-brief --book <name>` — **distil** the treatment into a
   one-page teaser brief: the single filmable through-line, the turn, the 3
   must-have moments, the killer lines. Run before beats so the beats are
   chosen from a sharp brief, not the whole story (the `/autonovel:teaser`
   orchestrator runs this for you). Writes `teaser/brief.md`.
2. `/autonovel:teaser --book <name> [--length 180] [--provider <p>]` —
   **the one-command pipeline.** Runs steps 2a→2b for you, each in a
   fresh subagent, and prints one summary. `--with-treatment` runs step 1
   first when no treatment exists. Or run the two sub-steps yourself if
   you want to hand-edit the beat-sheet between them:
   - 2a. `/autonovel:teaser-beats --book <name> [--length 180]` — selects
     the hook → escalation → title → button beats to a budget. Writes
     `teaser/beats.md` (edit it freely).
   - 2b. `/autonovel:shot-prompts --book <name> [--provider <p>]` — turns
     beats into provider-ready shot prompts, runs a free pre-generation
     critique, and writes `teaser/teaser.json` + `teaser/shots/shot_*.md`.
3. `/autonovel:teaser-critique --book <name>` — re-run the free critique
   (mechanical linter + LLM critic) on a hand-edited `teaser.json`; writes
   an advisory `teaser/critique.md`, **scores the interestingness rubric to
   `teaser/quality.json`** (§11), and prints the **render-gate verdict** —
   READY only when the story is complete AND quality ≥ 7 (no dimension < 5).
   Read-only on the teaser.
3b. `/autonovel:teaser-revise --book <name> [--deboring]` — **the fix loop.**
   Applies the critique's findings to `teaser.json` *in place* (fills the
   spine incl. the turn, strengthens dialogue/cards, repairs the 4-act order
   + stakes ladder, rewrites weak shots) AND **lifts the weak quality
   dimensions + runs the de-boring pass** (swap the flattest beats/lines for
   the most dramatic moments/sharpest quotes), re-scoring `quality.json` —
   all **without regenerating from scratch** so you never hand-edit and never
   lose good work. Re-critiques until both gates are READY.
   This is the teaser analogue of the book's *evaluate → revise*; use
   `shot-prompts --force` only when you want a clean re-author from the beats.
4. `/autonovel:teaser-render --book <name> [--provider <p>] [--kind auto|image|video] [--dry-run]`
   — render the prompts into actual clips. On a fresh teaser it first
   validates the chain **free and offline** via the `stub` backend (local
   placeholder keyframes — no network/key/quota), then renders real video
   on **`grok`** (free dialogue+music, no card) or another backend; a
   vision critique marks each clip **KEEP / REGENERATE / UPGRADE-TO-PAID**.
   Clips land in `teaser/clips/`; stateless, nothing assembled. `--dry-run`
   shows the plan + key status for $0. Backend/key map:
   `docs/teaser-render-providers.md`.
5. `/autonovel:teaser-assemble --book <name> [--audio <path>]` — stitch
   the clips into one teaser video with ffmpeg (via an editable
   `teaser/cut_list.json`), then a **viewer-panel cut critique** judges
   the whole cut (does the hook land, does it accelerate, does the button
   withhold?) → `teaser/assembly-report.md`. v1 is hard cuts; add the
   title/subtitle cards in an editor (models garble text — §4).

Steps 1–3 are free with no generation; step 4 validates the whole chain
for **$0/zero-quota** via the offline `stub` backend before spending a
real backend's limited free generations (`grok` = 5/day) — see
`docs/teaser-render-providers.md`; step 5 runs ffmpeg locally.

**Re-running the whole pipeline (Phase 6).** Passing `--force` to
`/autonovel:teaser` / `teaser-beats` / `shot-prompts` regenerates the
scripts, but first **archives the previous `beats.md` / `teaser.json` to
`teaser/script-takes/<name>_<UTC>.<ext>`** — so you never lose a script you
preferred (re-promote one by copying it back). The character/location
**reference originals in `teaser/refs/` are untouched**: a full re-run
changes the scripts while reusing the approved portraits and location
plates. Rendered clips are likewise versioned (`teaser-takes`, Phase 5.8).

## 11. Make it INTERESTING — the quality rubric + worked examples (Phase 11)

A teaser can pass every structural gate in §0 and still be dull: a tour of
pretty clips, no felt plot, almost no dialogue, no character, no surprise.
That is the failure this section exists to kill. **Structure is the floor;
this is the bar.**

### 11.1 The eight interestingness dimensions

`/autonovel:teaser-critique` scores each 1-10 and writes `teaser/quality.json`;
`/autonovel:teaser-render` blocks a real render unless **overall ≥ 7 AND no
dimension < 5**. Score honestly and harshly — a generous 7 spends real money
on a boring teaser.

| Dimension | The question (score 1-10) |
|---|---|
| `hook_grip` | Would a stranger keep watching past ~10 s? Does the opener *arrest*, not merely establish? |
| `question_sharpness` | Is the dramatic question sharp and specific to THIS story — not a generic "will they survive?" |
| `stakes_escalation` | Do the stakes rise beat to beat — specific, felt, irreversible — or a montage of equals? |
| `character` | Do we learn who someone IS — what they want, what it costs — or just see a face? |
| `dialogue_quality` | Subtext, voice, ≥1 quotable line — or filler / on-the-nose? |
| `surprise_turn` | Is there a real turn/reversal that re-frames the story — or a straight line? |
| `coherence` | Does it add up to ONE legible story a first-timer could follow? |
| `button` | Does the ending withhold the resolution AND deepen the question — no tidy close? |

The weakest dimensions are the **de-boring targets** for
`/autonovel:teaser-revise`: it lifts each low dimension and replaces the 3
flattest beats + the flattest line with the most dramatic moments and the
sharpest quotes the story has.

### 11.1b The viewer-blind legibility read — the un-gameable half

A self-score is gameable: the *same model* that wrote the teaser scores it,
and it can see its own intent (the spine, the names, the beat-notes) — so it
grades the *script it meant*, not the *experience a stranger gets*, and
passes itself with eloquent 8s while the rendered teaser is an illegible
tour of objects. (This is exactly what happened: a teaser of a ledger, a
riderless horse, and seven wax seals — no identified people — self-scored 7–9
and shipped.) So the gate has a second, **external** half. The judge re-watches
**as a first-time viewer who knows nothing about the book**: for each shot it
sees ONLY the perceivable layer — the visible action + the spoken line + any
on-screen text, with the names/spine/beat-notes **hidden** — and must answer
**who / what / why**. A scene is `clear` only if a stranger could. Then it
writes the **viewer takeaway** ("a stranger comes away believing: ___") and
**would_watch**. The render gate blocks on *any* illegible scene and on a
teaser a stranger wouldn't watch — not just a low score.

**Drama over mechanism (the #1 legibility fix).** Every hook/escalation
shot must put a **person making a visible choice** on screen, not an OBJECT.
A ledger, a wax seal, a contract, a riderless horse, a map, a stack of
dispatches mean nothing to a stranger — they read as "a horse," not "the
courier was intercepted." Show the *man deciding to buy the emperor*, not the
wax being pressed. If a beat is about an instrument, frame a named person
*using* it and let a line carry the meaning.

**Identify the players.** The first appearance of each real figure gets a
subtle lower-third — `identify: "Jakob Fugger — the richest man in Europe"`,
`"Albrecht of Brandenburg — an archbishop who bought his office"` — which
`teaser-assemble` burns at the bottom for ~2.5 s. A teaser of unnamed
strangers in period dress is illegible; this is how historical-drama trailers
tell you who matters. (`identify` is *not* a text card — it's a name label;
keep story cards sparing, per §7.)

**Build in the right genre, carefully.** Read the book's actual genre and
build in *that* idiom — historical **fiction** is a cinematic
character-and-stakes drama, not a documentary and not a generic moody
montage. A genre-blind default (atmosphere with no people, no stakes) is the
root cause of a teaser that feels like nothing.

### 11.2 Worked example A — historical thriller (180 s)

A *target to imitate*, not a template to copy. Note the spine has a **turn**,
the escalation is grouped into **movements** that each build, the **dialogue
is loaded** (subtext, not chatter), and there are explicit **want/cost**
character beats.

```
SPINE
  Dramatic question: Can one clerk prove the bank that owns his country
    forged its own ledgers — before it erases him with a stroke of ink?
  Logline: A guild bookkeeper discovers the empire's richest bank has
    falsified the accounts that fund a war, and becomes the only witness.
  Want: to make the forged ledger public and survive.
  Opposing force: the Fugger bank — limitless money, the Emperor's ear.
  Turn (midpoint): the magistrate he risked everything to reach is already
    the bank's man — the law itself is bought. (The viewer thought "expose
    it to the authorities"; now there ARE no clean authorities.)
  Emotional arc: quiet diligence → dawning dread → cornered defiance.
  Score: a single cello ostinato that tightens, then drops out on the button.
  Genre: historical conspiracy thriller.

HOOK (4-6 s) — a quill stops mid-figure; a bead of ink swells and falls onto
  a number that doesn't belong. CARD: "Every empire keeps two ledgers."
MOVEMENT 1 (escalation, rising) —
  • He recompiles the column by candlelight; the totals won't reconcile.
    [character_beat: want — he NEEDS the truth to balance] stakes_level 1
  • A bank courier watches him through the counting-house window. lvl 2
  • DIALOGUE (factor, low): "Numbers don't lie, Tomaso. Men do." lvl 3
THE TURN (~90 s, hold 4-5 s) — he lays the ledger before the magistrate, who
  slides it back unopened and signs the bank's writ. spine.turn made visible.
MOVEMENT 2 (escalation, higher) —
  • His name is struck from the guild rolls — pen through ink. [cost] lvl 4
  • DIALOGUE (Tomaso, breaking): "Then I'll print it where you can't reach."
    lvl 5
  • Presses roll in a cellar; ink like blood. lvl 6
TITLE (~2/3) — THE SECOND LEDGER
BUTTON (final 4 s) — a single printed sheet pinned to a cathedral door at
  dawn; a gloved hand reaches for it. Cut to black. CARD: "Some debts are
  paid in truth." (Withholds: does he live? does it land? — that's the film.)
```

Why it works: one sharp question; a real reversal (the law is bought) that
re-frames everything after it; dialogue that names a stake in one breath;
want *and* cost shown, not told; a button that deepens the question instead
of resolving it.

### 11.3 Worked example B — optimistic sci-fi (180 s, X-Prize shape)

```
SPINE
  Dramatic question: When the machine that could heal the dying coast needs
    a human to risk everything to start it, will anyone step forward?
  Logline: In a drowning delta, an engineer must trust an unfinished
    carbon-capture leviathan — and a stranger's hands — to save her city.
  Want: to prove the machine works before the next storm.
  Opposing force: a town that has stopped believing rescue is possible.
  Turn (midpoint): the machine doesn't fail — the PEOPLE do; it works only
    when the whole town crews it together. (Hope was never about the tech.)
  Emotional arc: weary resolve → collective doubt → earned, communal hope.
  Score: a lone piano that gathers instruments until it's a crowd.
  Genre: grounded optimistic sci-fi.

HOOK (5 s) — a child presses a palm to a fogged turbine; it hums awake.
  CARD: "They said the coast was already lost."
MOVEMENT 1 — the engineer alone, fighting dead systems [want] · a flooded
  street · DIALOGUE: "I don't need faith. I need forty pairs of hands."
THE TURN (~90 s) — she throws the master switch and NOTHING happens; then,
  one by one, neighbours take the manual cranks. The machine breathes.
MOVEMENT 2 — green floods the readouts · the storm wall holds · [cost: she
  gives up leaving on the last boat] · DIALOGUE: "We don't get saved. We
  save."
TITLE — THE TIDEMAKERS
BUTTON — dawn; the coast is still there; she hands the child the wrench.
  (Reveals the *vision* — a future worth building — withholds the *journey*.)
```

Same engine: a specific question, a genuine reversal (the limiting factor is
people, not tech), loaded lines, a paid cost, and a button that shows the
hopeful destination while hiding the road — exactly the X-Prize ask (§7).

## 12. The AI-video SHORT — the default shape (Phase 13)

A full Fugger run with all of §0–§11 in force was *still* incoherent: no
plot, no character, nothing held together. The problem wasn't the script —
it was the **shape**, and it was fighting the medium. AI video has continuity
*inside* a clip and **none between clips** (every generation is a blank slate;
a character introduced in shot one drifts by shot four). So a 180-second,
30-shot montage is 30 unrelated images — there is nothing to cohere. The fix
is a different artifact, and it's now the **default `mode: short`**:

- **45–60 seconds, not 180.** AI narrative shorts cohere at 15–60s; 90s is
  already a stretch. Pass `--length 60` (the default) and `--mode short`.
  `--mode trailer` keeps the older long montage shape for live/stock footage
  or an X-Prize-length cut.
- **6–12 shots, not 30+.** One beat ≈ one shot. The planner caps short mode
  at 12 and `teaser-critique` flags `too-many-shots`.
- **Fewer, LONGER shots.** AI only has continuity within a clip, so hold the
  key beats 5–8 s (the cap). Fewer long continuous shots beat a strobe of
  2-second cuts. (Modern ASL is 3–5 s; for AI video, lean longer.)
- **One first-person VOICEOVER spine — the single most important device.**
  A narrator (the protagonist, looking back — *Goodfellas*, *Shawshank*; this
  is fiction, not documentary) speaking over the cut is what ties disjoint
  clips into ONE story. `spine.narrator` names the voice; most shots carry a
  `voiceover` line; read in order they must tell a coherent micro-story on
  their own. In-scene lip-synced dialogue stays to ≤2–3 accents (lip-sync is
  unreliable; VO is added in post and always lands).
- **Concrete, not cryptic — every VO line must be self-explaining to a
  modern stranger on FIRST hearing.** This is the most common VO failure:
  trailer-poetry that has a ring but a fuzzy meaning. A 21st-century viewer
  hearing a 15th-century man say *"I bought speed"* or *"the page no one
  read"* or *"money moves faster than men"* does **not** know what that
  literally means. Say the actual thing in plain cause-and-effect with
  concrete nouns: not *"I bought speed"* → *"I paid for couriers faster than
  any king's; I heard the news first and traded on it before my rivals
  knew."* Not *"I took their crowns as surety"* → *"I lent against their
  silver mines; when they couldn't repay, the mines were mine."* Test each
  line: *would a viewer who knows nothing of this history understand exactly
  what happened and why it mattered?* If it only sounds good, rewrite it.
  Concrete beats evocative every time.
- **Connected, not a list — the spine is ONE monologue, not captions.** The
  second-most-common VO failure, right behind cryptic: every line is concrete
  and self-contained, but strung together they play as a bulleted list of
  facts — *"Seventh son of a wool merchant. I learned the account books. I
  lent to kings."* — three flat declaratives of the same shape, no thread.
  A short delivers the lines as **continuous narration**, so they must
  *connect*: each picks up the one before — by cause (*so*, *because*,
  *that's why*), by time (*then*, *until*, *by the time*), or by a returning
  noun — and the **rhythm must vary** (a long winding line, then a short hard
  one), never N declaratives in lockstep. Read the whole spine aloud in **one
  breath**: it should sound like one voice working toward a point, not a stack
  of headlines. Litmus test — *if two adjacent lines could swap order and no
  one would notice, they aren't connected yet.* (Render-side: the narration
  track joins the lines as one paragraph so the TTS voice carries intonation
  across them — but that only protects prose that already flows; it can't
  connect a list.)
- **One protagonist; minimize everyone else.** Drift compounds with each
  added face — keep ≤3, and let the VO carry relationships.
- **Judge the assembled CUT, cold** — not the script. The script can read
  beautifully and the film still be garbage; watch it as a stranger.

The 60-second story shape (open as late as possible, on the conflict):
setup 0–15 s → escalation 15–35 s → the turn + payoff 35–60 s. Establish
genre by 10 s; end on an irreversible cost, not a tidy resolution.

> *Why this section supersedes the montage instinct:* §8's "35–60 shots for
> 3 minutes" is the **trailer** shape, and it only works with real footage
> you can cut freely. For AI-generated video, default to the short.

---

*See [`prd-movie-teaser-mode.md`](prd-movie-teaser-mode.md) for the
provider landscape, the machine prompt schema, the free
agent-driven toolchain, and the self-critique testing loop.*
