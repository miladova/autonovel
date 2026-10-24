---
name: autonovel:revoice
description: Apply a voice shift to one chapter — different POV or register.
argument-hint: "<chapter-number> --book <short-name> [--pov <name>] [--register <label>]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
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
Sidequest: rewrite one chapter with a different voice — either a
different POV character or a different register (e.g. tightening the
formal register of a ceremonial chapter, loosening an action chapter's
prose rhythm). Plot, beats, and canon stay intact; only the voice
surface changes. One checkpoint.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`
   plus at least one of `--pov <name>` or `--register <label>`.
   `<register>` is free-form (e.g. `clipped`, `formal`,
   `stream-of-consciousness`, `period-ornate`). Neither flag present
   is a usage error — there is no default; the user has to name the
   shift.

2. Use `file_read` on `project.yaml`, `books/{book}/voice.md`,
   `shared/characters.md`, and `books/{book}/chapters/ch_{chapter}.md`.
   If `--pov` is given, confirm the named character exists in
   `shared/characters.md`; otherwise stop with the gap.

3. Draft a revoice brief:
   - If `--pov`: name the new POV, their age, their vocabulary wells
     (from `shared/characters.md`), and what they notice that the
     original POV did not. Preserve every plot event and beat.
   - If `--register`: name the shift concretely (sentence length
     envelope, vocabulary domain, rhythm target) and quote one or two
     passages from voice.md Part 2 that anchor it.

4. Use `file_write` to save the brief to
   `books/{book}/briefs/ch{chapter:02d}.md`.

5. Rewrite the chapter from the brief. Keep beats, canon facts, and
   plot moves identical. Update YAML frontmatter: `pov` if changed,
   `status: revised`, fresh `word_count`. Use `file_write` to
   overwrite `books/{book}/chapters/ch_{chapter}.md`.

6. **Regenerate the chapter summary** to reflect the rewritten
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
- `books/{book}/chapters/ch_{chapter}.md` parses YAML frontmatter.
- If `--pov <name>` was given, the frontmatter's `pov` equals `<name>`.
- `status` is `revised`; `word_count` is fresh.
- `books/{book}/briefs/ch{chapter:02d}.md` exists and names the
  revoice shift explicitly (POV change or register label).
</acceptance>
