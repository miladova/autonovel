---
name: autonovel:foreshadow
description: Plant a detail in chapter N and pay it off in chapter M; updates the outline thread ledger.
argument-hint: "--plant <N> --payoff <M> --thread \"<one-sentence>\" --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
writes:
  - books/{book}/outline.md
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
context_mode: book
---

<purpose>
Sidequest: a lighter-weight version of `/autonovel:add-subplot`.
Plant a single image, object, or line in chapter `N`; pay it off —
as a callback, not a new storyline — in chapter `M`. No new
characters, no new plot beat. Two chapters touched; one checkpoint.

Use this when you want the foreshadowing discipline without the
subplot machinery: the goal is texture and return, not arc.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--plant <N>`, `--payoff <M>`,
   `--thread "<desc>"`, `--book <short-name>`. Reject `M <= N`.
   The `<desc>` is used as the thread label and as the brief's
   heading.

2. Use `file_read` on `project.yaml`, `shared/characters.md`,
   `shared/canon.md`, `books/{book}/canon.md`, `books/{book}/voice.md`,
   `books/{book}/outline.md`, and both target chapters
   (`books/{book}/chapters/ch_{plant}.md` and
   `books/{book}/chapters/ch_{payoff}.md`).

3. Append a ledger line to `books/{book}/outline.md` under a
   `## Threads` section (create if absent):

       - Plant ch_{plant:02d} / Payoff ch_{payoff:02d}: <thread>

4. For each of the two chapters, draft a tight brief and rewrite:

   - Brief format: H1 `# Chapter <N> — foreshadow: <thread>`; H2
     sections `## What lands here`, `## Specific rewrite`, and
     `## Target length` (current ± 100 words).
   - Plant chapter: the rewrite must add the image/line/object
     without pointing at it. The reader should not yet know it
     matters. Prefer one sentence of concrete detail over a
     paragraph of foreshadowing.
   - Payoff chapter: the rewrite must echo the plant — same
     image, same object, same line, possibly inverted — in a
     moment of decision or realization. Do not explain the
     callback.

   Use `file_write` for each brief under
   `books/{book}/briefs/ch{chapter:02d}.md`, then overwrite
   `books/{book}/chapters/ch_{chapter}.md` with the revised
   chapter. Preserve YAML; set `status: revised`; recompute
   `word_count`.

5. **Regenerate the chapter summary** to reflect the rewritten
   prose. Use `file_write` to overwrite
   `books/{book}/chapters/ch_{chapter}.summary.md` following the
   canonical 7-section template defined in `commands/draft.md`
   step 12 (Location, Plot, POV state, Cast on stage, Threads
   opened, Threads closed, Story time). 150–250 words total. The
   per-chapter summary is the rolling-context surface every
   downstream drafter / reviser reads — skipping this regeneration
   leaves the summary stale and continuity drifts (the next
   chapter's drafter sees the OLD cast / threads / POV state).
   The lifecycle's verify-writes guard catches the unpaired-chapter
   case and prints a 🔴 banner if you skip; don't skip.
</workflow>

<acceptance>
- `books/{book}/outline.md` gains a ledger line under `## Threads`
  naming both chapters.
- Both chapters parse YAML frontmatter and carry `status: revised`.
- Neither rewrite changes the chapter's word count by more than
  ±10%.
- Two briefs exist under `books/{book}/briefs/`, each naming the
  thread in its H1.
</acceptance>
