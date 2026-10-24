---
name: autonovel:shorten
description: Compress one chapter to a target word count (no shorter than 1800 words).
argument-hint: "--chapter <N> --book <short-name> --target-words <W>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
writes:
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
context_mode: book
---

<purpose>
Sidequest: compress a single chapter to a target word count. Writes a
compression brief, then rewrites the chapter from it — all in one
checkpoint, so `autonovel rollback` undoes the whole operation.

Bells learning: any chapter below ~1800 words becomes the new weakest
chapter; this command refuses to brief below 1800 words, no matter
what the user asks for. The sweet spot for compressed chapters is
2200-3000w.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--chapter <N> --book <short-name>
   --target-words <W>`. All three are required. If `W` is less than
   1800, stop with: "target_words must be >= 1800 (see Bells
   compression floor)".

2. Use `file_read` on `project.yaml` and `books/{book}/voice.md` for
   voice guardrails (these must not drift during compression).

3. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md`. Count
   the current words. If the chapter is already at or under the
   target, stop with: "chapter already at target (W words)".

4. Draft a compression brief. Identify the passages that dilute
   tension: over-explaining, narrator summary where a scene was
   already dramatized, restated beats. Keep what earns its place;
   cut what restates. Allocate the cut across the chapter evenly —
   do not trim only the ending, which is where the chapter's
   irreversible change must land.

5. Use `file_write` to save the brief to
   `books/{book}/briefs/ch{chapter:02d}.md` with an H1 header
   `# Chapter {chapter} — compression to {target} words` and the
   standard brief sections (What works / What drags / Specific cuts /
   Voice guardrails / Target length).

6. Rewrite the chapter from that brief. Preserve the YAML frontmatter
   (update `status` to `revised`, recompute `word_count`). Use
   `file_write` to overwrite `books/{book}/chapters/ch_{chapter}.md`.

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
- `books/{book}/chapters/ch_{chapter}.md` exists and parses YAML
  frontmatter.
- The rewritten chapter's word count is within ±10% of
  `target-words`, and not below 1800.
- `books/{book}/briefs/ch{chapter:02d}.md` exists and names the
  target word count.
</acceptance>
