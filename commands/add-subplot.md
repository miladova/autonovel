---
name: autonovel:add-subplot
description: Add a minor storyline — plant it in one chapter, harvest it in another — and log the thread in the outline.
argument-hint: "--thread \"<one-sentence-description>\" --plant <N> --payoff <M> --book <short-name>"
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
  - books/{book}/chapters/*.md
writes:
  - books/{book}/outline.md
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/pending_canon.md
context_mode: book
---

<purpose>
Sidequest: seed a two-beat subplot — plant a detail in chapter `N`,
pay it off in chapter `M` (with `M > N`) — and record it in the
outline's foreshadowing / thread ledger so later commands do not
trample it. Two chapters rewritten as one checkpoint.

Design rule: a subplot earns its place by changing at least one
character's choice downstream. If the thread is just decoration, do
not add it — use `/autonovel:foreshadow` instead, which is explicit
about planting without a full subplot arc.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--thread "<desc>"`,
   `--plant <N>`, `--payoff <M>`, `--book <short-name>`.
   Reject `M <= N`: "payoff chapter must come after plant".

2. Use `file_read` on `project.yaml`, `shared/characters.md`,
   `shared/canon.md`, `books/{book}/canon.md`, `books/{book}/voice.md`,
   `books/{book}/outline.md`, and both
   `books/{book}/chapters/ch_{plant}.md` and
   `books/{book}/chapters/ch_{payoff}.md`. Also glob
   `books/{book}/chapters/*.md` so the thread does not accidentally
   echo or contradict material in chapters between plant and
   payoff.

3. Draft a thread entry for the outline. Format:

       ### Thread: <short label>
       - Description: <thread>
       - Plant: ch_{plant:02d} — <one-line where/how>
       - Payoff: ch_{payoff:02d} — <one-line where/how>
       - Consequence: <what changes because of this thread>

   Use `file_write` to append this under a `## Threads` section in
   `books/{book}/outline.md` (create the section if absent).

4. For EACH of the two chapters (plant first, then payoff), draft a
   brief and rewrite the chapter:

   a. Draft a brief specific to that chapter's role in the thread.
      Target length: current word count ± 200. Name the plant or
      payoff exactly. Use `file_write` to save to
      `books/{book}/briefs/ch{chapter:02d}.md`.
   b. Rewrite `books/{book}/chapters/ch_{chapter}.md` from the
      brief. Preserve the YAML frontmatter; set `status: revised`;
      recompute `word_count`. Use `file_write` to overwrite.

5. Append any new facts the thread established to
   `books/{book}/pending_canon.md` (e.g. a new possession, a
   location, a relationship). Single `no new facts` line if none.

6. **Regenerate the chapter summary** to reflect the rewritten
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
- `books/{book}/outline.md` contains a `## Threads` section with a
  `### Thread: …` entry naming both chapter numbers and a
  consequence.
- Both `books/{book}/chapters/ch_{plant}.md` and
  `books/{book}/chapters/ch_{payoff}.md` parse YAML frontmatter
  and carry `status: revised`.
- Each rewritten chapter differs from its prior draft.
- `books/{book}/briefs/` contains a brief for each of the two
  chapters.
</acceptance>
