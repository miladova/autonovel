---
name: autonovel:lengthen
description: Expand one chapter to a target word count via physical accumulation, not filler.
argument-hint: "--chapter <N> --book <short-name> --target-words <W>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
writes:
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
context_mode: book
---

<purpose>
Sidequest: expand a chapter to a target word count. Writes a brief and
rewrites in one checkpoint. The expansion must come from physical
accumulation (body, texture, proximate danger), dread, or silence — not
from adding exposition or interiority. The voice fingerprint is the
guardrail: if the added material reads like narrator summary, undo.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--chapter <N> --book <short-name>
   --target-words <W>`. All three are required. Stop with a one-line
   reminder if any are missing.

2. Use `file_read` on `project.yaml`, `books/{book}/voice.md`,
   `shared/world.md`, and `shared/characters.md`. The voice Part 2 and
   the world details are what let the expansion feel earned rather
   than invented.

3. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md`. Count
   current words. If already at or above the target, stop.

4. Draft an expansion brief. Expand via:
   - Physical accumulation (body sensations, proximate objects, weather)
   - Dread / silence (unspoken moments between lines of dialogue)
   - Concrete specificity where the current draft generalized
   Never expand via narrator interiority that tells the reader what
   the scene already shows, and never add a new plot beat.

5. Use `file_write` to save the brief to
   `books/{book}/briefs/ch{chapter:02d}.md` with the standard
   sections and target length.

6. Rewrite the chapter from that brief. Preserve the YAML frontmatter
   (set `status: revised`, recompute `word_count`). Use `file_write`
   to overwrite `books/{book}/chapters/ch_{chapter}.md`.

7. **Regenerate the chapter summary** to reflect the rewritten
   prose. Use `file_write` to overwrite
   `books/{book}/chapters/ch_{chapter}.summary.md` following the
   canonical 7-section template defined in `commands/draft.md`
   step 13 (Location, Plot, POV state, Cast on stage, Threads
   opened, Threads closed, Story time). 150–250 words total. The
   per-chapter summary is the rolling-context surface every
   downstream drafter / reviser reads — skipping this regeneration
   leaves the summary stale and continuity drifts (the next
   chapter's drafter sees the OLD cast / threads / POV state).
   Then use `bash` to run `autonovel _stamp-summary --book {book} --chapter {chapter}`,
   which records that the summary matches the chapter as it now stands.
   Write the summary after your last change to the chapter's prose: `_end`
   will not close the command while the summary describes older text (the
   summary gate).
</workflow>

<acceptance>
- `books/{book}/chapters/ch_{chapter}.md` parses its YAML frontmatter
  and carries `status: revised`.
- The rewritten chapter's word count is within ±10% of
  `target-words`.
- `books/{book}/briefs/ch{chapter:02d}.md` exists and names the
  target.
</acceptance>
