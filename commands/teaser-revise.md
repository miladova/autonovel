---
name: autonovel:teaser-revise
description: Apply the teaser critique's findings to teaser.json IN PLACE — fix the flagged shots, fill the story spine, strengthen dialogue/cards, repair the 4-act order and stakes ladder — WITHOUT regenerating from scratch. The "revise" half of the teaser loop (mirrors how the book pipeline acts on evaluate). Preserves everything that already works.
argument-hint: "--book <short-name> [--provider generic|veo|sora|runway|kling|luma|pollinations] [--max-rounds <n>] [--deboring]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/critique.md
  - books/{book}/teaser/quality.json
  - books/{book}/teaser/beats.md
  - books/{book}/teaser/brief.md
  - books/{book}/treatment.md
  - books/{book}/chapters/*.md
writes:
  - books/{book}/teaser/teaser.json
  - books/{book}/teaser/quality.json
  - books/{book}/teaser/shots/shot_*.md
context_mode: book
---

<purpose>
The teaser loop is **author → critique → revise**, exactly like the book
pipeline's draft → evaluate → revise. `/autonovel:shot-prompts` authors;
`/autonovel:teaser-critique` finds problems (read-only); **this command
acts on what the critique found and fixes the teaser in place** — so you
never hand-edit `teaser.json` and never lose good work.

The distinction that matters:

  - `/autonovel:shot-prompts --force` **regenerates from scratch** — a
    fresh author pass. Good for a clean restart, but it discards your
    current shots and may introduce *new* problems.
  - `/autonovel:teaser-revise` **edits the existing `teaser.json`** —
    it touches only what the critique flagged (a weak shot prompt, a
    missing spine field, thin dialogue, a missing card, a broken 4-act
    order or stakes ladder) and **leaves everything else exactly as it
    is**. This is the surgical fix loop.

It reads the critique's machine-readable flags *and* the prose suggestions
in `critique.md`, applies them, re-validates, and re-critiques until the
must-fix flags clear (or it reports what's left). No image/video tool is
called — it is free.

**Phase 11 — fix BORING, not just broken.** Clearing the structural flags
only gets the teaser to "has a story shape"; it can still be dull. This
command also reads the `quality.json` scorecard and **lifts the weakest
interestingness dimensions** until the quality gate passes (overall ≥ 7, no
dimension < 5). The most aggressive form is the **de-boring pass** (`bp`
item 8, on by default when the quality gate is BLOCKED, forceable with
`--deboring`): find the 3 flattest beats and the flattest dialogue line and
**replace them with the most dramatic moments and sharpest quotes** the
story has — a real reversal at the `turn`, a line with subtext, a beat that
shows the protagonist's want and its cost. Then it re-scores `quality.json`
so the gate reflects the improvement.
</purpose>

<workflow>
**Read-failure policy.** `books/{book}/teaser/teaser.json` is load-bearing
— stop if it is missing (run `/autonovel:shot-prompts` first). If
`books/{book}/teaser/critique.md` is missing, generate findings inline
(step 2) rather than failing. Treat `beats.md`, `treatment.md`, and
`chapters/*.md` as best-effort sources for filling gaps; note and proceed.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--provider <name>` (default: the `provider` in `teaser.json`),
   `--max-rounds <n>` (default 3 — how many revise→re-critique passes
   before stopping), `--deboring` (force the aggressive de-boring pass even
   when the quality gate already passes — push an already-fine teaser to
   *great*). Confirm the book exists in `project.yaml`.

2. **Get the current findings + quality score.** `bash`:
   `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider <name> --format json`
   Parse the `findings` (each `{shot_id, code, message}`). Then read the
   quality scorecard: `file_read` `books/{book}/teaser/quality.json` (and
   `bash`: `autonovel mechanical teaser-quality books/{book}/teaser/quality.json --format json`
   for the computed verdict + weakest dimensions). If `quality.json` is
   missing, treat the quality gate as BLOCKED — `/autonovel:teaser-critique`
   has not scored it yet; you will score it in step 6b. Also `file_read`
   `books/{book}/teaser/critique.md` when it exists for the LLM critic's
   per-shot prose suggestions and the `brief.md` distilled through-line when
   present. If there are **no findings, the quality gate PASSES, and
   `--deboring` was not passed**, report "already clean + interesting" and
   stop (nothing to do).

3. **Archive the current script** before editing it (so this revision is
   reversible): `bash`:
   `autonovel mechanical teaser-archive-script books/{book}/teaser/teaser.json`
   (copies it to `teaser/script-takes/teaser_<UTC>.json`).

4. **Apply each finding as a TARGETED edit** to `teaser.json` — `file_read`
   it, fix only what is flagged, `file_write` it back. **Preserve every
   shot/field the critique did not flag** (do not re-author the whole
   teaser, do not renumber shots, do not invent new ones unless a finding
   explicitly requires adding/cutting a beat). Map each flag to its fix:
   - `no-dramatic-question` / `no-logline` / `no-stakes` /
     `no-emotional-arc` / `no-genre` → fill the missing `spine` field,
     pulling it from `beats.md`'s `## Spine` block, else from
     `treatment.md` / canon. Do not overwrite a spine field that is
     already present and fine.
   - `thin-dialogue` → mine 1–3 more **loaded** lines from
     `treatment.md` / `chapters/*.md` (a threat, a vow, a cost named
     aloud) and add them to the most fitting shots' `audio.dialogue`;
     don't pad with filler.
   - `hook-not-first` / `multiple-hooks` / `no-title` / `button-not-last`
     / `title-after-button` → fix the `role`s / reorder so the 4-act
     shape holds (one `hook` first, one `title` ~2/3, one `button` last).
   - `no-stakes-ladder` / `stakes-not-rising` → set/repair each
     escalation shot's `stakes_level` so it strictly rises in order.
   - `cast-sprawl` → demote extra named faces to silhouettes/crowd
     (clear `subject.name`) so ≤3 named faces remain.
   - `appearance-drift` → reuse ONE appearance string for the subject
     across its shots.
   - `thin-prompt` / `no-palette` / `multi-action` / per-shot prose
     suggestions in `critique.md` → rewrite **only that shot's** prompt
     fields per teaser-craft §4/§5 (one action, palette anchors, concrete
     cinematography). Apply the critic's concrete suggestion when given.
   - `no-turn` → add the midpoint `turn`/reversal to `spine.turn` (pull the
     real story reversal from `brief.md` / `treatment.md`) AND make the beat
     visible: ensure a shot near the midpoint actually *shows* the flip.
   - `no-character-arc` → tag ≥1 shot `character_beat: "want"` and ≥1
     `character_beat: "cost"`, and make those shots *show* it (a choice, a
     loss) — not just a face.
   - `too-many-cards` → cut the card slideshow: convert most `text_card`s
     into spoken `audio.dialogue` (more characters talking) or a sparing VO
     line; keep cards only for the title and maybe one button line (Phase 12).
   - `instrument-only-shot` → the named culprit shots are OBJECT shots a
     stranger can't read (a ledger, a wax seal, a riderless horse). Rewrite
     each to **center a named person making a visible choice**, with a line
     that carries the meaning — or cut it. Show the man buying the emperor,
     not the wax (Phase 12).
   - `unidentified-figure` → give the figure's FIRST appearance an `identify`
     ("Name — epithet", e.g. "Albrecht of Brandenburg — an archbishop who
     bought his office") so a first-time viewer knows who they are (Phase 12).
   - `no-narrator` → set `spine.narrator` (who speaks the first-person VO,
     e.g. "Jakob in old age, looking back") — short mode (Phase 13).
   - `thin-narration` → write a first-person `voiceover` line on most shots
     so the narration runs as ONE continuous story across the cut (read them
     back in order — they must cohere alone). This is the short's spine.
   - **cryptic VO (a shot the legibility read marked unclear because its
     `voiceover` is evocative-but-fuzzy)** → rewrite the line concretely:
     plain cause-and-effect, concrete nouns, the actual thing that happened
     (*"I bought speed"* → *"I paid for couriers faster than any king's; I
     heard the news first and traded before my rivals knew"*). Concrete beats
     evocative.
   - **`disconnected-vo` (the spine reads as a list — every line clear but
     nothing hands off, "a bunch of short statements not connected")** → keep
     the lines concrete but **thread them into one monologue**: give each line a
     connective that depends on the one before (cause — *so / because / that's
     why*; time — *then / until / by the time*; or a returning noun), and
     **vary the rhythm** (a long winding line, then a short hard one) so they
     stop sounding like N declaratives in lockstep. Read the spine aloud in one
     breath; if two adjacent lines could swap order unnoticed, they're still a
     list — rewrite until each depends on its neighbour.
   - `too-many-shots` → a short is ≤12 longer shots, not a montage; merge or
     cut the weakest beats until ≤12 and lengthen the keepers (Phase 13).
   - `no-reference` → leave as-is here (references are developed in
     `/autonovel:teaser-refs`); note it in the summary.

4b. **Lift the weak quality dimensions, fix illegible scenes, + the de-boring
   pass (Phase 11/12 — fix BORING *and* CONFUSING).** Read
   `books/{book}/teaser/quality.json` — both the weak `scores` AND the
   `legibility` read. **Every shot the viewer-blind judge marked
   `clear: false` is a hard fix** (it blocks the render gate): a stranger
   could not tell who/what/why. Rewrite those shots to put an **identified
   person making a visible choice** on screen and let **spoken dialogue**
   (or a sparing VO) carry the idea — never rely on the viewer already
   knowing the history. Then lift the weak dimensions: This is what turns "structurally complete" into "interesting."
   Take the `quality.json` weakest dimensions (and the per-dimension `note`s
   the critic left) and act on each — pull the raw material from `brief.md`
   (the distilled through-line + must-have moments + killer lines),
   `treatment.md`, and `chapters/*.md`:
   - low `hook_grip` → replace the opener with the single most arresting
     image/line the story has; intrigue, don't establish.
   - low `question_sharpness` → sharpen `spine.dramatic_question` to
     something specific to THIS story; re-point beats that don't touch it.
   - low `stakes_escalation` → re-order/replace escalation beats so each
     names a NEW, higher cost; fix the `stakes_level` ladder.
   - low `character` → add the want + cost `character_beat`s (above).
   - low `dialogue_quality` → swap filler/on-the-nose lines for the
     sharpest, most loaded quotes in the manuscript; subtext over statement.
   - low `surprise_turn` → install a real reversal at `spine.turn` and stage
     it in a shot.
   - low `coherence` → cut shots that don't serve the question; make the
     through-line legible.
   - low `button` → rewrite the closing beat to withhold the resolution AND
     deepen the question (no tidy, round-edged close — the Stability Trap).
   **De-boring pass** (run when the quality gate is BLOCKED, or always with
   `--deboring`): hunt the **3 flattest beats** and the **flattest dialogue
   line** and *replace* them outright with the most dramatic moments and the
   sharpest quotes the story offers. Boring is a defect to be cut, not
   softened.

5. **Validate (hard gate).** `bash`:
   `autonovel mechanical teaser-validate books/{book}/teaser/teaser.json --provider <name>`
   Fix any structural errors and re-run until valid.

6. **Re-critique the structure and loop.** `bash`:
   `autonovel mechanical teaser-critique books/{book}/teaser/teaser.json --provider <name> --format json`
   If must-fix story-spine flags remain (`no-dramatic-question`,
   `no-logline`, `no-stakes`, `no-emotional-arc`, `no-genre`,
   `thin-dialogue`) and you have rounds left (`--max-rounds`), go back to
   step 4 for another targeted pass. Stop when the spine flags are clear or
   the round budget is spent (report any that remain and why).

6b. **Re-score the quality gate (scores AND the viewer-blind read).** Now
   that the teaser has changed, re-judge the eight interestingness dimensions
   AND re-run the **viewer-blind legibility read** (teaser-critique steps
   4b–4c): for each shot, from the perceivable layer only (action + spoken
   line + card, names/spine hidden), can a stranger tell who/what/why? Update
   `legibility`, `viewer_takeaway`, `would_watch`. Don't inflate — score what
   is actually on the page; a scene you just rewrote is only `clear` if the
   rewrite truly shows it. `file_write` the updated
   `books/{book}/teaser/quality.json`, then `bash`:
   `autonovel mechanical teaser-quality books/{book}/teaser/quality.json --format json`
   (exit 3 = still BLOCK). If the quality gate is still BLOCKED and you have
   rounds left, go back to step 4b and lift the weakest dimensions again.

7. **Re-render the per-shot files** so they match the revised JSON. `bash`:
   `autonovel mechanical teaser-render-prompt books/{book}/teaser/teaser.json --provider <name> --out-dir books/{book}/teaser/shots`

8. Print a one-screen summary — flags **before → after**, quality
   **before → after**, what changed (per shot / spine field), and the next step:

   ```
   🔧 Revised books/{book}/teaser/teaser.json — {before} flag(s) → {after};
        quality {old_overall}/10 → {new_overall}/10.
        Changed: {spine fields filled; turn added; dialogue/cards sharpened;
        de-boring swaps; character beats}.
        Render gate: {READY (story ✓ + quality {n}/10) | still BLOCKED —
        story: <codes>; quality: <weakest dims>}.

   {If READY:}  Next: /autonovel:teaser-render --book {book} --provider stub
                (validate free), then a real backend.
   {If BLOCKED:} Re-run /autonovel:teaser-revise --book {book} (more rounds),
                or /autonovel:shot-prompts --book {book} --force for a clean
                re-author if the beats themselves are the problem.
   ```
</workflow>

<acceptance>
- `books/{book}/teaser/teaser.json` is edited IN PLACE: every shot/field the
  critique did NOT flag is byte-for-byte preserved; only flagged items
  change. The prior version is archived to `teaser/script-takes/` first.
- After the run, `autonovel mechanical teaser-critique` reports strictly
  fewer findings than before (and the must-fix story-spine flags are cleared,
  unless reported as un-fixable with a reason).
- `teaser.json` passes `autonovel mechanical teaser-validate`; the per-shot
  files in `books/{book}/teaser/shots/` are regenerated to match.
- `books/{book}/teaser/quality.json` is re-scored after the edits and its
  `overall` does not drop; when the round budget allows, the quality gate
  ends PASS (overall ≥ 7, no dimension < 5) or the remaining weak dimensions
  are reported with why they could not be lifted.
- No image/video provider is called; the command is free.
- It never regenerates the whole teaser from scratch (that is
  `/autonovel:shot-prompts --force`) — it is the surgical, critique-driven
  revise loop.
</acceptance>
