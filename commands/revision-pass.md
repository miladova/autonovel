---
name: autonovel:revision-pass
description: Sweep check-anachronism + brief + revise + evaluate across a range of chapters in one invocation.
argument-hint: "--chapters <range|all|structural> [--book <name>] [--skip-anachronism] [--skip-eval] [--no-promote] [--enrich-with <research-notes-path>] [--parallel [N]]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - shared/craft/genres/*.md
  - shared/genres/*.md
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - shared/period_bans.txt
  - shared/research/notes/*.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.md
  - books/{book}/edit_logs/structure_review.json
  - books/{book}/edit_logs/review.json
  - books/{book}/edit_logs/reader_panel.json
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
  - books/{book}/briefs/conversation.md
  - books/{book}/edit_logs/last_read.json
writes:
  - books/{book}/edit_logs/diff_*.html
  - books/{book}/edit_logs/diff_*.json
  - books/{book}/edit_logs/story_map.html
  - books/{book}/edit_logs/story_map.json
  - books/{book}/canon.md
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.md
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/briefs/conversation.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
  - books/{book}/pending_canon.md
  - shared/canon.md
context_mode: book
---

<purpose>
Run the standard revision loop across multiple chapters in one
invocation. For each chapter in the requested range, sequentially
runs:

  1. `check-anachronism` (period-vocabulary + LLM semantic check)
  2. `brief --from auto` (synthesize revision brief from cuts/eval/panel/
     review, and — when `/autonovel:structure-review` has a structural
     brief candidate for the chapter — a `kind: structural` brief)
  3. `revise` (rewrite chapter against the brief; regenerates the
     summary; folds queued `briefs/conversation.md` entries
     targeting this chapter into the brief and flips them to
     `Status: applied`)
  4. `evaluate --chapter N` (score the revised version)

This is the "I have 3 drafted chapters, I want them all revised in
one go" command. Author preference 2026-04-25: minimise required
typing for the standard end-to-end flow while keeping the option to
skip individual stages.

`--chapters structural` is the structural sweep: it resolves to every
chapter named by a candidate in
`books/{book}/edit_logs/structure_review.json`, so each one gets a
`kind: structural` brief and a rewrite that may restructure the chapter
from the inside. Cross-chapter moves (merge, cut, reorder, split) are
never executed by the sweep; it collects their exact commands and
prints them for the author at the end.

Sequential by default within a book — later chapters' revisions read
earlier chapters' refreshed summaries. **Parallel via `--parallel
[N]`** (opt-in, default off): fan up to N chapters across `Task`
subagents simultaneously. Trade-off: parallel is ~Nx faster, but
each chapter's revise reads the *pre-sweep* version of its
neighbours' summaries (chapter 5's revise won't see chapter 4's
fresh post-revise summary in the same pass), so continuity drift
stays one revision-pass behind. A second
`/autonovel:revision-pass` picks up the propagation. Default
parallelism when `--parallel` is given without a number is **3**
(matches typical rate-limit headroom on standard accounts).

One single lock + checkpoint covers the whole sweep — sub-steps do
NOT run their own `autonovel _begin`/`_end`, so there's exactly
one preamble/postamble across the run. Rollback restores every
chapter the sweep touched in one shot.
</purpose>

<workflow>
**Read-failure policy across the sweep.** Per-chapter sub-agents
inherit `/autonovel:revise`'s read-failure policy: do NOT retry
on `file_read` errors for prior summaries, eval logs,
adversarial-edit reports, or panel JSON. Note the gap in the
per-chapter brief and proceed. The hard stop is a missing
chapter file at revise step 6 — that's the load-bearing input.
This prevents the 2026-04-25 retry-loop bug class from stalling
the whole sweep on a single missing input.

1. Parse `$ARGUMENTS`. Required: `--chapters <range>`. The range
   can be `N-M` (inclusive), `N,M,K` (comma-separated), `all`
   (every drafted chapter), or `structural` (every chapter a
   structure-review candidate names; resolved at step 2). `--book`
   defaults via `_begin`.
   `--skip-anachronism`, `--skip-eval`, and `--no-promote` are
   independent flags that drop those stages from the per-chapter
   sequence. `--enrich-with <research-notes-path>` (optional)
   propagates to each chapter's `brief` step — the brief considers
   whether the named research file is relevant to that chapter
   and, when it is, adds an `## Enrichment from research` block
   with light-touch period detail (no plot/dialogue/structure
   change). Use this when targeted research finished AFTER the
   first revision pass and you want to weave its detail into the
   chapters where it naturally belongs without redrafting them.
   Missing `--chapters` → stop with a one-line usage hint.

2. Use `file_read` on `project.yaml` to resolve the book entry,
   `pov`, and `defaults.chapter_target_words`. Use the `Bash` tool
   to run `ls books/{book}/chapters/ch_*.md` and pull the existing
   chapter numbers; resolve `all` to the full list and validate that
   every requested chapter exists.

   Resolve `structural`: use `bash` to run `autonovel mechanical
   structure-validate books/{book}` and read its JSON. Exit code 2 (no
   `structure_review.json`) → stop with "run /autonovel:structure-review
   --book {book} first". An error reporting a `chapter_count` mismatch
   means chapters were merged, cut or reordered since the review → stop
   with "chapters were renumbered since the structure review; re-run
   /autonovel:structure-review --book {book}". A gate that is only
   `stale` → warn once and continue. Otherwise use `file_read` on
   `books/{book}/edit_logs/structure_review.json` and take the union of
   every candidate's `edits[].chapter`, ascending. Remember each
   candidate's non-null `command` for step 4. With any explicit range,
   chapters a candidate names still get a structural brief at (b).

2a. **Start sweep-progress tracking.** Use `bash` to invoke:

    ```
    autonovel _sweep-start --command autonovel:revision-pass --book {book} --chapters {N1,N2,...}
    ```

    Same shape as draft-pass: writes
    `.autonovel/sweep-progress.json` so `/autonovel:resume` can
    offer "continue from chapter N" if the sweep is interrupted.
    Cleared at step 5a after the final promote-canon. After every
    successful chapter you'll mark it done with
    `autonovel _sweep-mark-done --chapter N --summary "<line>"`.

3. **Spawn one `task` subagent per chapter.** Per-chapter execution
   runs in a fresh subagent conversation, not in this parent
   conversation. Same context-saving discipline as draft-pass:
   the parent only sees one short summary string per chapter, so
   long sweeps don't exhaust the parent's context window.

   Two execution modes:

   - **Default (no `--parallel`):** spawn one Task at a time, in
     ascending chapter-number order. Each chapter's full sequence
     completes before the next is spawned. Maximum continuity
     fidelity (each chapter's revise reads its predecessors'
     refreshed summaries).
   - **`--parallel [N]`:** spawn up to N Task subagents
     simultaneously (default N=3). Faster but each parallel Task
     reads the *pre-sweep* version of its neighbours' summaries,
     so the rolling-summary context is one revision-pass stale
     within the run. Re-run revision-pass once more to propagate.

   For each chapter N, the subagent's prompt template (substitute
   {book}, N, the active flags, and `_begin`'s `genre:` line, which
   names the book's genre, subgenres and guide; the subagent runs no
   preamble of its own and needs it for steps b–d):

   **0. Capture the pre-revision score** (always; cheap):
      Use `file_read` on `books/{book}/eval_logs/ch{N:02d}_eval.json`
      and remember its top-level `overall_score` field as
      `prev_score`. If the file is missing or unparseable, set
      `prev_score = None` (this happens when the chapter was just
      drafted in the same session and never evaluated, or on the
      very first revision pass before any eval ran). The score
      delta we report at step (e) is computed against this value
      so the user sees how the revise actually moved the chapter,
      not just where it landed.

   a. **check-anachronism** *(skippable via --skip-anachronism)*:
      Use `Bash` to run
      `autonovel mechanical period-bans
      books/{book}/chapters/ch_{N:02d}.md shared/period_bans.txt`
      for the deterministic half. Then load
      `books/{book}/chapters/ch_{N:02d}.md`,
      `shared/world.md`, `shared/canon.md`, `books/{book}/canon.md`
      and run an LLM semantic
      pass for concept/metaphor anachronism (the same logic
      `/autonovel:check-anachronism` carries out). Combine the
      regex hits and the LLM hits into a report at
      `books/{book}/edit_logs/ch{N:02d}_anachronism.md`. Do NOT
      modify the chapter.

   b. **brief --from auto**: Reproduce the body of
      `/autonovel:brief` — read the latest `eval_logs/ch{N:02d}*.json`,
      `edit_logs/ch{N:02d}_cuts.json` (if any), the new
      anachronism report from (a), `edit_logs/review.json` and
      `edit_logs/reader_panel.json` (if any), and
      `edit_logs/structure_review.json` (if any) — then synthesize a
      revision brief at `books/{book}/briefs/ch{N:02d}.md`. The brief
      enumerates specific named passages to change, target word
      count, and prescriptions per anti-pattern. When a
      structure-review candidate names chapter N, the brief is
      `kind: structural` (frontmatter) with the `## Structural brief`
      and `## Cross-chapter operations — run these yourself` sections
      `/autonovel:brief` step 5 defines; otherwise `kind: prose`. The
      brief follows the genre guide (brief step 4a): the genre's
      payload (for historical fiction, the period) is never a
      `## Specific cuts` item; badly placed payload is a `## Move,
      don't cut` item.

      **When this sweep was invoked with `--enrich-with <path>`,
      pass that flag through to the per-chapter brief.** Each
      chapter's brief considers whether the research file is
      relevant to that chapter (a chapter where the researched
      topic — person, institution, period detail — naturally
      appears); when it is, the brief adds an `## Enrichment from
      research` block with 1–2 specific period details per relevant
      scene, no structural changes. Chapters whose subject doesn't
      touch the research stay clean; the brief omits the
      enrichment block.

   c. **revise**: Reproduce the body of `/autonovel:revise` — read
      the brief, the current chapter, the prior chapter's last
      ~2000 words via `autonovel _tail-chapter --book {book}
      --chapter {N-1} --words 2000` (best-effort, no retry),
      voice, the genre guide's `## Drafting` (revise step 5b), and
      rewrite the chapter. Overwrite
      `books/{book}/chapters/ch_{N:02d}.md`. **Regenerate the
      summary** at `books/{book}/chapters/ch_{N:02d}.summary.md`
      so chapter N+1's revise reads the updated version, then use
      `bash` to run `autonovel _stamp-summary --book {book} --chapter
      {N}` (revise step 9). If a later step changes the prose again,
      rewrite the summary where it no longer holds and stamp it again. A
      `kind: structural` brief lets the rewrite restructure chapter N
      from the inside (`/autonovel:revise` step 7a); it never edits
      another chapter and never runs a cross-chapter command — return
      those commands verbatim to the parent instead. Skip revise's
      step 12 (the hand-back diff): the parent hands the whole range
      back once, at step 4.

   d. **evaluate** *(skippable via --skip-eval)*: Reproduce the
      body of `/autonovel:evaluate --chapter N` — score the revised
      chapter against the standard chapter dimensions and the genre
      guide's extra dimensions (historical fiction: `history`), write
      `books/{book}/eval_logs/ch{N:02d}_eval.json` (with
      `weakest_dimension`, `weakest_score` and the `first_reader`
      block, evaluate step 6). Read the new `overall_score` from the
      file you just wrote and remember it as `new_score`, and the
      weakest dimension and score as `new_low`. The eval file is what the next sweep
      iteration's brief will pull from.

   e. **Compute the delta**: `delta = new_score - prev_score`
      (only if both are non-None; otherwise leave as "—"). This
      is display-only — no file written.

   f. **promote-canon** *(skippable via --no-promote)*: invoke
      the safe in-sweep helper via `Bash`:

      ```
      autonovel _promote-canon --book {book} --no-lock --format json
      ```

      The `--no-lock` flag is **load-bearing** — the parent
      revision-pass holds `.autonovel/in-progress.lock`, so the
      helper must skip the lock check. Without `--no-lock` the
      helper would refuse to run with "another autonovel command
      is in progress" and per-chapter canon promotion would
      silently fail (author bug-report 2026-04-26).

      DO NOT invoke `/autonovel:promote-canon` as a slash-command
      from inside this sub-agent — that would route through the
      slash-command's preamble (`autonovel _begin`) and hit the
      same lock collision. Always use the bare CLI with `--no-lock`.

      Parse the JSON output. The `books[0].promoted` field is the
      `<P>` count for the per-chapter status line below. The
      helper does the full de-dup / contradiction-detection /
      research-tagged-supersedure / conflict-block-emission
      pipeline atomically — same logic the slash-command's body
      runs (see `commands/promote-canon.md`) — so per-chapter
      inline promotion lets each revision's discoveries land in
      the book's `books/{book}/canon.md` (research-cited facts in
      `shared/canon.md`) before the next chapter's revise reads
      canon.

      Mirrors the per-chapter promote-canon that draft-pass
      adopted in `aea1511`. Without it, revisions that discover
      new canon facts (a clarified date, a character revelation,
      a corrected name) leave them in pending_canon.md until the
      *end* of the sweep, and chapter N+1's revise reads the
      pre-revision `shared/canon.md` — re-introducing the very
      inconsistency the chapter-N revise just fixed.

   **Critical: do NOT call `autonovel _begin` or `autonovel _end`
   for any sub-step.** This command holds the series lock for the
   entire range — its own preamble already ran. Sub-steps that
   tried to acquire the lock would deadlock.

   After each chapter finishes, print one line:

   ```
   [ch N] anachronism: <count> hits | brief: <words>w [structural S2,S5] | revise: <words>w (delta <±N>w) | eval: <prev_score> → <new_score> (Δ <±X.X>) low <prev_low> → <new_low> | canon: +<P>
   ```

   (`[structural …]` appears only for a `kind: structural` brief and
   lists its candidate ids.)

   When `prev_score` is None (no prior eval on disk), render the
   eval segment as `eval: — → <new_score>` and omit the Δ. When
   `--skip-eval` was passed, omit the eval segment entirely. When
   `--no-promote` was passed, omit the `canon:` segment; otherwise
   `<P>` is the count of pending_canon entries promoted into
   shared/canon.md by this chapter's promote-canon step (`0` is a
   valid value when the chapter discovered no new facts).

   so the user has live progress and can see whether the revise
   actually improved the chapter or made it worse — a negative Δ
   is a real signal worth surfacing immediately, not buried in the
   end-of-sweep table. If a sub-step errors, log the failure and
   continue to the next chapter — do not abort the whole sweep on
   one chapter's hiccup.

   After each chapter, use `bash` to run `autonovel mechanical
   summary-check books/{book} --chapters N`. If chapter N is not
   `fresh`, its summary describes older text: bring it up to date the
   way the preamble's summary step does (one `task` subagent rewrites it
   from the chapter and stamps it) before the next chapter starts, and
   say so in the chapter's line. `_end` will not close the sweep while
   any chapter it changed has a summary that doesn't match.

   After each chapter's per-chapter line, use `bash` to mark the
   chapter complete in the sweep-progress file:

   ```
   autonovel _sweep-mark-done --chapter N --summary "<the line above>"
   ```

   Best-effort: don't retry on error.

4. After the loop completes, print a summary table that includes
   the score movement so the user sees at a glance which chapters
   the revise lifted, which it left flat, and which it regressed:

   ```
   chapter | anachronism | revise (words) | prev → new (Δ)    | lowest, prev → new
   --------|-------------|----------------|-------------------|----------------------------
        1  | 2 hits      | 2900 (-150)    | 7.5 → 7.9 (+0.4)  | place 6.9 ⚠ → place 7.6
        2  | 0 hits      | 3200 (+50)     | 6.5 → 6.8 (+0.3)  | pull 6.0 ⚠ → pull 6.6 ⚠
        3  | 1 hit       | 2750 (-300)    | 7.4 → 7.1 (-0.3)  | prose 7.2 → depth 6.8 ⚠
   ```

   The lowest column is the chapter's weakest dimension before and
   after (⚠ under `defaults.dimension_floor`, the threshold when
   unset): a revise that lifts the mean and leaves the worst
   dimension under the floor has not done its job.

   Render `—` in the prev cell when no prior eval existed
   (typically chapter just drafted and never evaluated, or the
   very first revision pass). Render `—` in the Δ cell whenever
   either side is `—`.

   Append a one-paragraph headline assessment that names every
   chapter still with a dimension under the floor, and calls out any
   *regressions* explicitly ("3/3 chapters above threshold;
   chapter 3 regressed -0.3 — review before next pass; recommend
   `/autonovel:reader-panel` next"). A negative delta on any
   chapter is a real concern and should not be buried in the
   table.

   **Hand the revised chapters back as one diff.** Use `bash` to run,
   with the chapter numbers actually swept as the range (`3-7`,
   `2,5,9`; never the words `all` or `structural`):

   ```
   autonovel mechanical diff-chapters --book {book} --from last-read --chapters <range> --if-read
   ```

   It compares each chapter as the author last read it (the version
   `books/{book}/edit_logs/last_read.json` records) with the revision,
   writes one page `books/{book}/edit_logs/diff_*.html` (with its
   `diff_*.json`, and `story_map.html` / `story_map.json` rebuilt beside
   it), and prints `"skipped": "<reason>"` — say nothing about it — when
   the author has no bookmark or had read none of these chapters.
   Otherwise add one line after the table: "What changed since you last
   read: <open> (<html>) — <hunks> changes, <big_hunks> big." Do not pass
   `--mark-read`. Best-effort: on a helper failure, say so in one line.

   When any chapter had a structural brief, add a block "Cross-chapter
   operations the structure review asked for — run these yourself"
   listing every candidate `command` collected at step 2 and returned
   by the per-chapter subagents, de-duplicated, verbatim, in candidate
   priority order. A chapter-score Δ is not the measure of a
   structural pass (a consequence scene can lower a chapter's prose
   score); the measure is the next `/autonovel:structure-review`.

5. **Final promote-canon sweep** *(skip if `--no-promote`)*. After
   the loop completes, run `/autonovel:promote-canon` one last time
   to catch any pending_canon entries that the per-chapter step
   couldn't promote (typically: revise additions in the very last
   chapter that landed after that chapter's promote-canon ran, or
   any other book's pending file in a multi-book series). Idempotent
   — if every per-chapter promote already consumed everything, this
   call is a no-op summary line.

5a. **Clear sweep-progress tracking.** Use `bash` to invoke
    `autonovel _sweep-clear`. The sweep is over;
    `.autonovel/sweep-progress.json` is no longer needed.

6. **Postamble: write a multi-line `next_standard_step` reflecting
   what the sweep just produced.** The default
   single-line `next_standard_step` is wrong for a multi-chapter
   rewrite — `/autonovel:next` would otherwise just say "run
   reader-panel" and skip the verify-then-review-then-backup
   closer that ANY multi-chapter sweep needs. Operating-guide
   §2b.1 "After the sweep — the closer" is the canonical
   prose; the postamble should write a compact version of the
   same six steps as a numbered list, with state filled in from
   *what just happened in this run*:

   ```
   1. Verify deltas: <N> chapter(s) regressed (Δ<0): <list>.
      Re-run those without --enrich-with:
        /autonovel:revision-pass --chapters <list> --book {book}
      <OR "No regressions; all chapters held or improved." when N=0>

   2. Resolve canon conflicts: <K> entry/entries still in
      books/{book}/pending_canon.md as conflicts.
      Open it and follow the HOW TO RESOLVE block at the top.
      <OR "No conflicts; pending_canon.md is clean." when K=0>

   3. The re-read (<N> chapters changed, so every whole-book
      report is stale), in order:
        /autonovel:structure-review --book {book}
        /autonovel:developmental-edit --book {book}
      The structure review first, so the editor's second letter can
      compare against it and say whether this pass did what the
      first letter asked. The reader panel and the dual-persona
      review come after, once the structure gate passes and the
      letter has nothing left open (`/autonovel:next` walks the
      order).
      <when structural briefs ran: list the cross-chapter commands
       collected in step 4, to run before the structure review>


   4. Backup the substantive change:
        cd ~/<series-root>
        git add . && git commit -m "Revision pass: chapters <range>" && git push
      <OR omit when no git remote is set up>

   5. Optional: typeset to read in PDF form:
        /autonovel:typeset --book {book}

   6. After (3), decide whether to run another revision-pass on
      the panel/review flagged-chapter list, or move on to
      /autonovel:title, /autonovel:introduction, /autonovel:typeset,
      /autonovel:package.
   ```

   Substitute the actual values: count of regressions and the
   list, count of pending-canon conflicts (read
   `books/{book}/pending_canon.md` after the final promote-canon
   to count `## Conflict N` blocks), the chapter range that was
   swept. Pass the whole multi-line block to the postamble via
   the `--next-standard-step` flag on `autonovel _end`:

   ```
   autonovel _end --command autonovel:revision-pass \
       --args "<the original $ARGUMENTS>" \
       --status ok \
       --wrote <every-path-actually-modified> \
       --next-standard-step "$(cat <<'EOF'
   1. Verify deltas: ...
   2. Resolve canon conflicts: ...
   3. Re-run whole-book reviewers: ...
      /autonovel:structure-review --book {book}
      /autonovel:reader-panel --book {book}
      /autonovel:review --book {book}
   4. Backup: git add . && git commit && git push
   5. ...
   EOF
   )"
   ```

   The `--next-standard-step` flag stores the multi-line block in
   `last-action.json :: next_standard_step` so
   `/autonovel:next` prints it verbatim. **Without this flag**,
   the postamble falls back to the auto-computed
   `_next_step_for(series, book)` result — typically "draft N+1"
   — and the carefully-crafted closer is dropped on the floor.
   The 2026-04-30 silent-revise-failure session ran into this
   exact case.

   Note: this multi-line shape is the right shape for any
   multi-chapter sweep. Single-chapter atomic commands (draft,
   revise, evaluate) keep their concise single-line
   `next_standard_step` because their state space is small.
</workflow>

<files-touched>
This sweep delegates to the same set of files each underlying command
touches. For the contract record (and so a `--dry-run`-style audit
can enumerate them):

Reads:
- `project.yaml`
- `shared/world.md`, `shared/characters.md`, `shared/canon.md`
- `books/{book}/canon.md` (this book's own canon)
- `shared/period_bans.txt`
- `books/{book}/voice.md`, `books/{book}/outline.md`
- `books/{book}/chapters/ch_{chapter}.md` (per chapter in range)
- `books/{book}/chapters/ch_*.summary.md` (rolling continuity)
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.md` (read between stages)
- `books/{book}/edit_logs/structure_review.json` (`--chapters structural`, and structural briefs)
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json` (read by brief --from auto)

Writes (per chapter in range):
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.md`
- `books/{book}/briefs/ch{chapter:02d}.md`
- `books/{book}/chapters/ch_{chapter}.md`
- `books/{book}/chapters/ch_{chapter}.summary.md`
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json`
- `books/{book}/pending_canon.md` (revise may append candidate facts)
</files-touched>

<acceptance>
- For every chapter N in the resolved range, the corresponding
  `books/{book}/chapters/ch_{N:02d}.md`,
  `books/{book}/chapters/ch_{N:02d}.summary.md`,
  `books/{book}/briefs/ch{N:02d}.md`, and
  `books/{book}/eval_logs/ch{N:02d}_eval.json` exist and have
  modification times newer than the start of the sweep.
- If `--skip-anachronism` was passed, no
  `books/{book}/edit_logs/ch{N:02d}_anachronism.md` was created
  by this run.
- The summary table is printed in the postamble footer; the user
  can read per-chapter results without opening the eval logs.
</acceptance>
