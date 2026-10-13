---
name: autonovel:shot-prompts
description: Turn a teaser beat-sheet into provider-ready, heavily-described shot prompts (the core deliverable). Fills the structured shot schema, runs a free pre-generation critique, and writes teaser.json + per-shot markdown.
argument-hint: "--book <short-name> [--mode short|trailer] [--provider generic|veo|sora|runway|kling|luma|pollinations] [--length <seconds>] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/teaser/beats.md
  - shared/world.md
  - shared/characters.md
  - books/{book}/voice.md
  - books/{book}/art/visual_style.json
  - books/{book}/treatment.md
  - books/{book}/chapters/*.md
  - books/{book}/teaser/teaser.json
writes:
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/shots/shot_*.md
context_mode: book
---

<purpose>
The core deliverable of teaser mode: turn each beat in
`books/{book}/teaser/beats.md` into one or more **richly-described shot
prompts** a video model will obey. Output is two things:

  - **`books/{book}/teaser/teaser.json`** — the machine-readable teaser:
    the **`spine`** (dramatic question, logline, want, opposing force,
    emotional arc, score direction — copied from `beats.md` so it flows to
    render + critique), then the ordered list of shots in the structured
    schema (PRD §8): framing, subject + verbatim appearance, one action,
    setting, lighting, palette, camera move, lens, style, mood, separate
    negative prompt, separate **dialogue** (loaded lines mined from the
    manuscript), **text cards** (carrying the premise), consistency anchors.
  - **`books/{book}/teaser/shots/shot_<id>.md`** — hand-editable,
    copy-paste-ready prompt files, rendered deterministically from the
    schema in canonical Veo/Sora order.

A **free, pre-generation critique** runs before you spend anything: the
mechanical linter plus an LLM critic pass that rewrites weak prompts —
catching most failures for $0 (PRD §24.2). No image/video tool is
called; you take these prompts to your generator (or, later,
`/autonovel:teaser-render`).

Craft rules are in `docs/teaser-craft.md` — read it; the discipline
below (one action per shot, verbatim appearance, palette lock, content-word
negatives) comes from there.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/beats.md` and
`shared/characters.md` are load-bearing — stop if the beat-sheet is
missing (run `/autonovel:teaser-beats` first). Treat `voice.md`,
`art/visual_style.json`, `treatment.md`, and `chapters/*.md` as
best-effort enrichment; note gaps and proceed. Do not retry failed reads
of best-effort inputs.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   **`--mode short|trailer`** (default `short` — Phase 13), `--provider
   <name>` (default `generic`), `--length <seconds>` (default:
   `project.yaml :: teaser.length_s` if set, else `60` for short / `90` for
   trailer), `--force`. Write the chosen `mode` into `teaser.json`. In
   **short** mode you are building a 45–60s, ≤12-shot micro-story carried by
   a first-person **voiceover spine** (see step 5c + `docs/teaser-craft.md`
   §12); in **trailer** mode, the older longer montage shape.

2. **Refusal-on-overwrite, then archive.** If
   `books/{book}/teaser/teaser.json` exists and `--force` was not passed,
   stop with a message pointing the user to `--force` or hand-editing. When
   `--force` **was** passed, preserve the prior script first — `bash`:
   `autonovel mechanical teaser-archive-script books/{book}/teaser/teaser.json`
   (copies it to `teaser/script-takes/teaser_<UTC>.json`; no-op if absent).
   Reference originals in `teaser/refs/` are untouched, so a full re-run
   keeps every prior script and reuses the approved portraits/plates.

3. **Budget.** `bash`:
   `autonovel mechanical teaser-plan --length <seconds> --provider <name> --mode <mode> --format human`
   — note the shot target and the provider's clip cap + native-audio flag
   (only emit `audio`/`dialogue` when the provider supports audio). In
   **short** mode honour the **shot cap (≤12)** and the **voiceover_target**
   (most shots carry a VO line); FEW longer shots, not a montage.

4. **Load the spine + foundation for description:**
   - `books/{book}/teaser/beats.md` `## Spine` block — the dramatic
     question, logline, want, opposing force, **turn** (the midpoint
     reversal), emotional arc, score direction, **genre**. Copy all of it
     verbatim into the teaser's `spine` object (below). **If `beats.md` has NO `## Spine` block (an
     older beat-sheet generated before the story-spine pass), do NOT leave
     the spine empty — AUTHOR it now yourself** from `treatment.md` /
     `outline.md` / `shared/canon.md` (the same way `teaser-beats` would),
     so a re-run of `shot-prompts` alone still yields a complete spine and a
     READY render gate. (Best practice: also re-run `/autonovel:teaser-beats
     --force` to write the spine back into `beats.md`, or just use the
     `/autonovel:teaser` orchestrator which does both.) It is load-bearing:
     render + critique read it, and the **narrative gate** in
     `teaser-render` refuses a real render
     when the spine/payload is thin (bp 12).
   - `shared/characters.md` — each character's **appearance**. Write ONE
     appearance string per character and reuse it **verbatim** in every
     shot (consistency; teaser-craft §6). Assign each a reference image
     path `refs/<name>.png` (the plan; generated later).
   - `shared/world.md` — settings/locations.
   - `project.yaml :: genre` / `period` / `region` — wardrobe, props, era
     look, AND the teaser's **idiom**. Read the genre carefully and build in
     *that* genre's convention (e.g. historical **fiction** = a cinematic
     character-and-stakes drama trailer; a thriller = withheld menace; a
     biography/history = fact-forward). Never fall back to a generic moody
     montage — that genre-blind default is what makes a teaser feel like
     nothing (Phase 12).
   - `books/{book}/art/visual_style.json` — palette anchors (3-5),
     grade, lens look. Hold the palette identical across shots.
   - `books/{book}/voice.md` Part 4 — per-character beat density / how a
     character carries a moment.
   - `books/{book}/treatment.md` + `books/{book}/chapters/*.md` — the
     concrete image for each beat (best-effort).

5. **Externalize interiority** (teaser-craft §3). For beats drawn from
   prose, run `bash`: `autonovel mechanical show-dont-tell <chapter-file>`
   to surface interiority lines, and convert any interior state into
   **visible behaviour** in the shot's `action` (film shows; it cannot
   narrate thought). Best-effort.

5b. **Mine the dialogue + write the text cards** (Phase 6 — the fix for
   "not enough dialogue to know anything"). A teaser must let the viewer
   *hear* the story and read its premise:
   - **Dialogue (bp 5, Phase 11).** Read `books/{book}/treatment.md` +
     `books/{book}/chapters/*.md` and pull the **`dialogue_target` highest-
     voltage lines** the plan printed (≈1 per 20 s — so ~8-10 for a 180 s
     teaser, not 3) — the ones that reveal a stake, a relationship, or the
     genre in one breath (a threat, a vow, a cost named aloud), each with
     **subtext and a distinct voice** (thin/on-the-nose dialogue is the #1
     felt failure). Adapt each to a short trailer line and assign it to the
     shot it belongs to as `audio.dialogue: [{speaker, line}]`. These are
     *loaded* lines, not ambient chatter; spread them across the arc (one
     near the hook, the sharpest at the turn and just before the
     title/button). **Provider gate:** only emit
     spoken `dialogue` when the provider has native audio (check
     `teaser-plan`); if it does not, carry those lines as **text cards**
     instead (below) so the meaning still lands.
   - **Text cards — sparing (Phase 12, revised).** Real shorts don't
     slideshow cards; they let **characters talk.** So carry the story in
     spoken dialogue first, and use `text_card`s only where a card genuinely
     beats a line: the **title** beat (carries the logline) and at most ONE
     button line. Do NOT put a card on every other shot — a card stack is the
     crutch that papers over illegible visuals. Prefer more characters
     speaking + a sparing narrator VO line over more cards.

5c. **The voiceover spine (Phase 13 — short mode; THE coherence device).**
   Independently-generated AI clips do NOT stitch into a story; **one
   first-person voiceover does** (think *Goodfellas*/*Shawshank* — and that's
   fiction, not documentary). So in **short** mode:
   - Set `spine.narrator` — WHO speaks and from when (e.g. *"Jakob Fugger in
     old age, looking back at the ledger that made him"*). First person, past
     tense, one consistent voice.
   - Write a **`voiceover` line on most shots** (`voiceover_target` from the
     plan) so the narration runs as ONE continuous thread across the cut —
     each line picks up where the last left off and advances the single
     story. Read the VO lines back in order with the pictures ignored: they
     must, alone, tell a coherent micro-story (setup → escalation → the turn →
     payoff/cost). This is what the viewer actually follows.
   - Keep in-scene `audio.dialogue` to ≤2–3 of the very sharpest lines (AI
     lip-sync is unreliable; the VO is added in post and always lands). The
     VO carries meaning the images can't; the few spoken lines are accents.
   - **Concrete, NOT cryptic (the #1 VO failure).** Every VO line must be
     self-explaining to a modern stranger on first hearing — plain
     cause-and-effect, concrete nouns, the *actual thing* that happened.
     Trailer-poetry that "has a ring" but a fuzzy meaning is a defect: a
     viewer hearing *"I bought speed"* / *"the page no one read"* / *"money
     moves faster than men"* does not know what it means. Write *"I paid for
     couriers faster than any king's; I heard the news first and traded on it
     before my rivals knew"* instead. Test each line: would someone who knows
     nothing of this history understand exactly what happened and why it
     mattered? If it only sounds good, rewrite it.
   - **Connected, NOT a list (the #2 VO failure, right behind cryptic).** The
     lines play back as ONE continuous monologue, so each must hand off to the
     next — by cause (*so / because / that's why*), by time (*then / until /
     by the time*), or a returning noun — and the rhythm must **vary** (a long
     winding line, then a short hard one), never N flat declaratives of the
     same shape (*"Seventh son of a wool merchant. I learned the books. I lent
     to kings."* is a list, not a spine). Read the VO lines aloud in order, in
     one breath: one voice building to a point, not a stack of captions. Litmus
     test: if two adjacent lines could swap order unnoticed, they aren't
     connected yet — give one a connective that depends on the other.
   - The VO is NOT narration-of-history (documentary) — it is the
     protagonist living his own story in his own voice (genre-appropriate for
     historical fiction).
   (In **trailer** mode skip the VO spine and lean on mined dialogue + cards
   as before.)

6. **Author the shots.** Build the full `books/{book}/teaser/teaser.json`
   as `{title, length_s, mode, provider, spine:{dramatic_question, logline,
   want, opposing_force, turn, emotional_arc, score_direction, genre,
   narrator}, shots:[… each with a `voiceover` line in short mode …]}` — the
   `spine` copied from `beats.md` (step 4); set `mode` to the chosen mode. For each
   beat, write 1+ shots that obey teaser-craft §4: one subject + one
   action + one camera move; present tense; only what's in frame; concrete
   cinematography vocabulary (teaser-craft §5); `duration_s` ≤ the provider
   clip cap; a content-word `negative_prompt` (e.g. `blurry, distorted
   hands, extra limbs, watermark, flicker, morphing` — never "no …"); the
   beat's `role`; the human `beat_note`; and the mined `audio.dialogue` /
   `text_card` from step 5b. **Diegetic text is the subject in many shots —
   protect it (teaser-craft §4):** if a shot's subject is written material
   (a ledger of accounts, a letter, a map, a signboard), do **NOT** put
   `text`/`letters`/`words`/`numbers` in its `negative_prompt` — that blanks
   the very thing the shot is about; describe the writing instead ("columns
   of ink figures, a tally that won't balance"). Reserve "no text" for shots
   where stray UI/watermark text would be a *defect*. (`teaser-render`
   auto-suppresses only the overlay *title* on `role: title` shots; the title
   is burned in at assembly.) Enforce the craft gates:
   - **4-act order (bp 2):** exactly one `role: hook` as the first shot
     (and it signals the **genre**, bp 9), one `role: title` ~2/3 in, one
     `role: button` as the last shot, escalation shots between.
   - **Stakes ladder (bp 3):** give every `role: escalation` shot a
     `stakes_level` integer that **strictly rises** in shot order (1, 2,
     3, …) — the cut must escalate, not idle.
   - **The turn (Phase 11):** stage `spine.turn` as a visible reversal in an
     `escalation` shot at roughly the midpoint — show the flip, don't narrate
     it. (The reversal text stays in `spine.turn`; the shot makes it
     visible.)
   - **Character beats (Phase 11):** tag ≥1 shot `character_beat: "want"`
     (the protagonist visibly pursuing what they want) and ≥1
     `character_beat: "cost"` (the price/change it exacts), and write those
     shots to *show* it — a choice, a loss — not just a recurring face.
   - **Drama over mechanism (Phase 12 — the #1 legibility fix):** every
     hook/escalation shot must put a **person making a visible choice** on
     screen, not an OBJECT. A ledger, a wax seal, a contract, a riderless
     horse, a map, a stack of dispatches mean nothing to a stranger — they
     read as "a horse," not "the courier was intercepted." Show the *man
     deciding to buy the emperor*, not the wax being pressed. If a beat is
     inherently about an instrument, frame a named person *using* it and let
     a line carry the meaning. Do NOT emit object-only subjects.
   - **Identify the players (Phase 12):** the first appearance of each key
     real figure gets an `identify` ("Name — epithet" — e.g. `"Jakob Fugger
     — the richest man in Europe"`, `"Albrecht of Brandenburg — an archbishop
     who bought his office"`), which the assembler burns as a subtle
     lower-third. A teaser of unnamed strangers in period dress is illegible;
     this is how a viewer knows who matters.
   - **Restraint (bp 10):** do NOT emit a shot that is merely "the
     character standing where/when they are" — every shot turns the
     question or implies a larger world. Cut filler.
   - **One hero face (bp 11):** ≤3 distinct `subject.name`s; the rest are
     silhouettes/crowd (no name, no consistency lock).
   Pace the cut to the **emotional arc** — the hook holds, escalation cuts
   tighten, the button breathes.

7. **Validate (hard gate).** `bash`:
   `autonovel mechanical teaser-validate books/{book}/teaser/teaser.json --provider <name>`
   If it reports problems, fix the JSON and re-run until valid.

8. **Critique (free, pre-generation — PRD §24.2).**
   a. `bash`: `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider <name>`
      — read the advisory flags. **Story-spine flags are must-fix**
      (`no-dramatic-question`, `no-logline`, `no-stakes`,
      `no-emotional-arc`, `thin-dialogue`): clear them by filling the spine /
      mining more lines, not by ignoring them. Heed the Phase-12 legibility
      advisories too (`instrument-only-shot`, `unidentified-figure`,
      `too-many-cards`). Plus the prompt flags (appearance-drift, thin-prompt,
      no-palette, no-reference, multi-action, audio-unsupported,
      missing hook/button, length-mismatch).
   b. **LLM critic pass:** for each shot, judge the prompt against
      teaser-craft §4 (legibility), the consistency rules, and whether it
      serves the beat + (for X-Prize) stakes / character / visual
      ambition. Rewrite weak prompts in the JSON. Then **re-run validate**
      (step 7) and confirm the mechanical flags you can fix are gone.

9. **Render the per-shot files.** `bash`:
   `autonovel mechanical teaser-render-prompt books/{book}/teaser/teaser.json --provider <name> --out-dir books/{book}/teaser/shots`
   — this writes `books/{book}/teaser/shots/shot_<id>.md` for every shot
   in the provider's **render dialect** (prose for veo/sora/generic/
   pollinations; terse comma-keywords for runway; concise + a Luma camera
   enum for luma) and deterministic canonical order. You don't pick the
   dialect — it follows `--provider`.

9a. **Reference-image plan (consistency anchors).** `bash`:
    `autonovel mechanical teaser-refs-plan books/{book}/teaser/teaser.json --art-references-dir shared/art_references`
    — lists the canonical reference image each recurring subject needs,
    which shots use it, and which already exist (in `books/{book}/teaser/refs/`
    or as a shared `shared/art_references/` plate). Reuse a shared plate
    when one is suggested; otherwise note the missing refs in the summary
    so the user can generate them (`/autonovel:art-curate`, or later
    `/autonovel:teaser-render`). This kills the "which refs do I still
    need?" `ls` workflow.

10. Print a one-screen summary: shot count, total seconds vs target,
    remaining advisory flags, missing reference images, estimated clip
    count incl. ~3× takes, and the next step:

    ```
    🎬 Wrote books/{book}/teaser/teaser.json + N shot files in
         books/{book}/teaser/shots/. {valid}; {k} advisory flags left.

    Next: generate the clips from these prompts in your video tool
    (free dev pass: Pollinations — see docs/teaser-craft.md / PRD §22),
    or wait for /autonovel:teaser-render (Phase 3.5).
    Re-run with --force to regenerate.
    ```
</workflow>

<acceptance>
- `books/{book}/teaser/teaser.json` exists and passes
  `autonovel mechanical teaser-validate` for the chosen provider (no shot
  exceeds the provider clip cap; every shot has a named subject, a
  verbatim appearance, and one action; negative/dialogue are separate
  fields).
- `books/{book}/teaser/shots/shot_<id>.md` exists for every shot, each
  with a `## Shot <id>`, a `**Prompt**` block in canonical order, and the
  separate negative/dialogue/reference sections.
- Each character uses ONE appearance string across all shots
  (`teaser-critique` reports no `appearance-drift`).
- `teaser.json` ALWAYS carries a `spine` object with a non-empty dramatic
  question, logline, want, opposing force, **turn**, genre, and emotional
  arc — copied from `beats.md` when it has a `## Spine` block, else
  **authored here** from treatment/outline/canon (a spineless older
  `beats.md` must NOT yield a spineless teaser). `teaser-critique` reports no
  `no-dramatic-question` / `no-logline` / `no-stakes` / `no-emotional-arc` /
  `no-genre` / `no-turn`.
- ≥1 shot is tagged `character_beat: "want"` and ≥1 `character_beat: "cost"`,
  and an `escalation` shot near the midpoint stages the `spine.turn` reversal
  (`teaser-critique` reports no `no-character-arc`).
- Every hook/escalation shot centers a **person** (not an object); each key
  figure's first appearance carries an `identify` lower-third
  (`teaser-critique` reports no `instrument-only-shot` / `unidentified-figure`).
  Text cards are sparing (title + at most one button line) — meaning rides
  spoken dialogue, not a card stack (no `too-many-cards`).
- In **short** mode: `mode:"short"`, ≤12 shots, a non-empty `spine.narrator`,
  and a first-person `voiceover` line on most shots that reads as ONE
  continuous story (`teaser-critique` reports no `no-narrator` /
  `thin-narration` / `too-many-shots`).
- The teaser carries the **length-scaled spoken dialogue lines** (audio
  providers; carried as a sparing VO/cards otherwise) — no `thin-dialogue`
  flag remains — and keeps text cards minimal (title + at most one button
  line; no `too-many-cards`).
- The teaser has exactly one `hook` and at least one `button`, and the
  button does not reveal the resolution.
- No image/video provider is called; the command is free.
- Refusal on overwrite without `--force`; with `--force`, the prior
  `teaser.json` is archived to `teaser/script-takes/` before regenerating.
</acceptance>
