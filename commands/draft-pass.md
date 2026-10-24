---
name: autonovel:draft-pass
description: Draft a range of chapters end-to-end with per-chapter eval + revise-on-low-score + canon promotion. Single-button "write the rest of the book."
argument-hint: "--chapters <range> [--book <name>] [--retry-below <score>] [--no-revise-low] [--no-anachronism] [--no-promote] [--skip-eval] [--floor <score>] [--deep] [--no-structure]"
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
  - shared/events.md
  - shared/period_bans.txt
  - shared/research/notes/*.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/design.md
  - books/{book}/cast.md
  - shared/craft/*.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.md
writes:
  - books/{book}/canon.md
  - books/{book}/edit_logs/first_read_ch{chapter}.md
  - books/{book}/edit_logs/first_read_ch{chapter}_2.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/eval_logs/ch{chapter:02d}_eval.json
  - books/{book}/edit_logs/ch{chapter:02d}_anachronism.md
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/pending_canon.md
  - shared/canon.md
  - books/{book}/edit_logs/structure_review.json
  - books/{book}/edit_logs/structure_review.md
  - books/{book}/edit_logs/reader_panel.json
  - books/{book}/edit_logs/review.json
  - books/{book}/edit_logs/review.md
context_mode: book
---

<purpose>
The "let it write the rest of the book" command. Drafts a range of
chapters end-to-end, fixes low-scoring chapters with brief+revise,
runs anachronism checks, and promotes pending canon at the end so
the final state is coherent — the book's `canon.md` reflects everything
the sweep discovered, every chapter is at or above threshold (or
explicitly flagged as below), and continuity summaries are fresh.

Per chapter, in ascending chapter-number order, sequentially:

  1. `draft N`              — full /autonovel:draft workflow,
                              cold first reader included
                              (writes ch_NN.md, ch_NN.summary.md,
                              the reader's report
                              `first_read_ch{chapter}.md`,
                              appends pending_canon)
  2. `check-anachronism N`  — period-vocabulary + LLM semantic check
                              (skip via --no-anachronism)
  3. `evaluate N`           — score the new draft (skip via --skip-eval)
  4. **If score < threshold, or its lowest dimension is under the
     dimension floor, or the second cold reader's serious items are
     not all fixed** AND --no-revise-low NOT set:
     a. `brief N --from auto`   — synthesize revision brief
     b. `revise N`              — rewrite per the brief; regenerates
                                  the chapter summary
     c. `evaluate N` again      — re-score
     d. keep whichever version scored higher; the other is in the
        checkpoint and recoverable via autonovel rollback
  5. **`promote-canon`** (skip via --no-promote)  — fold the new
                              pending_canon entries from this chapter
                              into the book's canon.md (research-cited
                              facts → shared/canon.md) *before* moving on
                              to chapter N+1. Critical: chapter N+1's
                              draft must see the canonical facts
                              chapter N just established, otherwise
                              N+1 invents conflicting versions of the
                              same fact (e.g. chapter N establishes
                              Tommaso's age in 1521; chapter N+1
                              gives a different age). Research-tagged
                              entries still win contradictions per
                              the standard promote-canon discipline.

After every chapter in the range completes:

  6. **Final promote-canon sweep** (skip via --no-promote) — catch
     anything still pending (typically from the last chapter's
     revise loop). Idempotent: if the per-chapter promotes already
     consumed everything, this is a no-op.

Sequential only — drafts cannot run in parallel because chapter N+1's
draft reads chapter N's prose and summary. Same per-chapter
*drafting* quality as `/autonovel:draft N` repeated; the wrap is
about adding the immediate-fix-on-low-score loop and the canon
propagation that makes the *whole-book* result coherent.

When NOT to use this:

- Early in a series (chapters 1-3) when you're calibrating voice.
  Use per-chapter `/autonovel:draft` so you can fix voice before
  drift compounds.
- When you need a heavy revision pass: that's
  `/autonovel:revision-pass`, which adds adversarial-edit +
  reader-panel + multi-cycle iteration. draft-pass is a one-pass
  command; revision-pass is the multi-pass deepener.

When TO use this:

- Foundation is solid. Voice is set. You want a coherent
  first-draft-plus-immediate-fix of every remaining chapter and
  you'd rather review the whole book at once afterwards than each
  chapter in isolation.
- After a major change (added a character, restructured a chapter)
  and you want to redraft a range with the new context.
</purpose>

<workflow>
**Read-failure policy across the sweep.** Each per-chapter
sub-agent inherits `/autonovel:draft`'s and `/autonovel:revise`'s
"do not retry on read failure" policy: a missing prior summary,
a missing prior chapter, an unreadable eval log → note the gap
in the per-chapter eval log row and proceed. The sweep does NOT
abort the whole run on a single chapter's input gap; the only
hard-stop is a missing chapter file when `revise` is supposed to
rewrite it. This catches the 2026-04-25 retry-loop bug class
that stalled long sweeps around chapter 8-10.

1. Parse `$ARGUMENTS`. Required: `--chapters <range>`.
   Range can be `N-M` (inclusive), `N,M,K` (comma-separated), or
   `all` (every chapter named in the outline that lacks a chapter
   file). Optional flags:
     - `--book` (defaults via `_begin`)
     - `--retry-below <score>` (default project.yaml::defaults
       .chapter_threshold; below this, the revise loop fires)
     - `--floor <score>` (default project.yaml::defaults
       .dimension_floor, else the threshold; any one dimension below
       this fires the revise loop even when the mean passes)
     - `--no-revise-low` (skip step 4; just redraft once on low
       score)
     - `--no-anachronism` (skip step 2)
     - `--no-promote` (skip step 5)
     - `--skip-eval` (skip steps 3 and 4 entirely; pure drafting)
     - `--no-structure` (don't run the structure review at the end
       of a sweep that drafts the outline's last chapter; see step 5)
     - `--deep` (after promote-canon, also run the whole-book
       reviewers: the book-level structure review, the reader-panel
       and the Opus dual-persona review; produces reports at
       `books/{book}/edit_logs/structure_review.json` + `.md`,
       `books/{book}/edit_logs/reader_panel.json` and
       `books/{book}/edit_logs/review.md` + `review.json`. Does NOT
       auto-revise from those reports — the user reviews them and
       decides whether to run a follow-up `/autonovel:revision-pass
       --chapters <list>` (or `--chapters structural`). ~15-35 extra
       minutes of compute on a 70k-word book.)
   Missing `--chapters` → stop with usage hint.

2. Use `file_read` on `project.yaml`. Keep `_begin`'s `genre:` line
   (the book's genre, subgenres and guide) for the subagent prompt in
   step 3. Resolve the book entry, `pov`,
   `defaults.chapter_target_words`, `defaults.chapter_threshold`,
   `defaults.dimension_floor` (the threshold when unset).
   Read `books/{book}/outline.md` to identify chapter numbers
   defined; resolve `all` to outlined chapters that lack a chapter
   file.

   Check the outline for its spine sections — `## Spine`, `## Stakes
   ladder`, `## Causal spine` (written by `/autonovel:gen-outline`).
   They are what every chapter in this sweep is held to (step 3, the
   SPINE CHECK). When they are absent (an outline written before they
   were required), do not stop: draft from the beats, set the flag
   `no-spine` for the subagents, and put "outline has no causal spine
   — run /autonovel:gen-outline --book {book} --add-spine before the
   next sweep" at the top of the summary at step 6.

2a. **Start sweep-progress tracking.** Use `bash` to invoke:

    ```
    autonovel _sweep-start --command autonovel:draft-pass --book {book} --chapters {N1,N2,...}
    ```

    This writes `.autonovel/sweep-progress.json` with the full
    target chapter list. After every successful per-chapter run
    (step 3.b below) you'll mark the chapter done; the file gets
    cleared at step 7. If the sweep is interrupted (power loss,
    /clear, budget exhaustion), `/autonovel:resume` reads the file
    and offers a precise "continue from chapter N" with the
    remaining chapter list.

3. **For each chapter N in the resolved range, in ascending order,
   spawn a `task` subagent.**

   Per-chapter execution runs in a *fresh* subagent conversation,
   not in this parent conversation. The parent only sees the
   subagent's one-line return value. This is what makes long
   sweeps feasible: in the old in-line model, each chapter inflated
   the parent conversation with chapter-of-prose-plus-tool-output
   and a 19-chapter sweep would exhaust context around chapter
   8-10. With Task subagents, parent context grows by ~16 short
   strings across the run.

   Drafts MUST be sequential (N+1 reads N's prose and summary), so
   spawn one Task at a time and wait for the result before the next.

   For each chapter N:

   a. Use the `task` tool to spawn a subagent. Description:
      `Draft chapter N of book {book} (autonovel pipeline)`. Allowed
      tools: Read, Write, Bash, `task` (the draft's cold first reader
      is a fresh subagent), WebSearch (for research-note fallbacks).
      Model: standard tier (sonnet 4.6 for draft; heavier sub-steps
      run their own).

      Prompt for the subagent (substitute {book}, N, threshold,
      and the active flags into this template; keep structure
      verbatim so subagents behave consistently):

      ```
      You are running ONE chapter (chapter N) of an autonovel
      draft-pass for book {book}. The PARENT command holds
      .autonovel/in-progress.lock — do NOT call `autonovel _begin`
      or `autonovel _end` inside this task.

      Threshold for the revise loop: {threshold}.
      Dimension floor: {floor}.
      Genre: {genre line from _begin, e.g. "Historical fiction
      (Biographical novel, Historical thriller (political)) — guide:
      shared/craft/genres/historical.md (extra evaluate dimensions:
      history)", or "none"}.
      Skip flags in effect: {flags}.

      Run these steps in order, each one inline (do not invoke
      slash-commands):

      1. DRAFT — the full /autonovel:draft workflow. Read the
         command file first, in full (the canonical workflow at
         ~/.claude/commands/autonovel/draft.md), and follow every
         step from 1a to the end, skipping only its preamble and
         postamble. Its reads are the inputs: project.yaml,
         shared/world.md, shared/characters.md, shared/canon.md,
         books/{book}/canon.md (this book's own canon),
         shared/events.md, books/{book}/voice.md,
         books/{book}/outline.md (chapter N's beats, AND — unless
         `no-spine` is in flags — the `## Spine` question, chapter
         N's act row in `## Stakes ladder`, and the `## Causal spine`
         lines `- N because M:` and `- N+1 because N:`),
         books/{book}/design.md and books/{book}/cast.md when they
         exist, the shared/craft/*.md docs it names,
         books/{book}/chapters/ch_*.summary.md (rolling continuity),
         the genre guide named above (draft step 3e: its promise,
         the book's subgenres, `## Drafting` and `## The first
         reader`; evaluate scores its extra dimensions),
         and `autonovel _tail-chapter --book {book} --chapter {N-1}
         --words 1000` for the prior tail (best-effort, no retry).
         Do not skip the steps added since this template was first
         written: 3a (hold the chapter to the spine: open on the
         earlier event the causal line names, make the stake its
         act's rung on the through-line question, end with the
         hand-off fact the next chapter acts on), 3b (the design),
         3c (the reader's map), 3d (people with depth, from
         cast.md), and step 10's first reader: spawn one fresh cold
         reader with `task` per shared/craft/FIRST-READER.md, save
         its report at books/{book}/edit_logs/first_read_ch{N:02d}.md,
         fix what it finds, and a second fresh reader only if the
         first found serious items (its report at
         books/{book}/edit_logs/first_read_ch{N:02d}_2.md).
         Write books/{book}/chapters/ch_{N:02d}.md with YAML
         frontmatter + the 150-250 word
         books/{book}/chapters/ch_{N:02d}.summary.md, then run
         `autonovel _stamp-summary --book {book} --chapter {N}`
         (draft step 13). Append
         candidate canon facts to
         books/{book}/pending_canon.md.

      2. ANACHRONISM (skip if --no-anachronism is in flags):
         run `autonovel mechanical period-bans
         books/{book}/chapters/ch_{N:02d}.md
         shared/period_bans.txt` plus a brief LLM semantic
         pass. Combined report at
         books/{book}/edit_logs/ch{N:02d}_anachronism.md. Capture
         the total hit count.

      3. EVALUATE (skip if --skip-eval):
         reproduce the /autonovel:evaluate --chapter N body —
         judge the chapter on the standard chapter dimensions,
         run `autonovel mechanical slop`,
         `autonovel mechanical cliches`,
         `autonovel mechanical sensory` for mechanical penalties.
         Write books/{book}/eval_logs/ch{N:02d}_eval.json, with
         `weakest_dimension`, `weakest_score` and the `first_reader`
         block (evaluate step 6). Capture overall_score as score_v1,
         and weakest_dimension / weakest_score as low_v1.

      3b. SPINE CHECK (skip if `no-spine` is in flags): reread the
         chapter's first scene and last scene against the outline's
         two causal-spine lines. spine_ok = yes only when (i) the
         first scene acts on the event `- N because M:` names, on the
         page, and (ii) the chapter ends with the fact `- N+1 because
         N:` needs, still open. A chapter that opens and settles its
         own stake while neither line holds is the anecdote failure
         (`/autonovel:structure-review`'s `anecdote-chain`) however
         well it scores. spine_ok = no sends the chapter to the revise
         loop even when score_v1 ≥ threshold.

      4. REVISE LOOP (skip if --skip-eval or --no-revise-low, or if
         score_v1 ≥ threshold AND weakest_score ≥ floor AND
         first_reader.all_fixed is not false AND spine_ok is yes or
         skipped). A chapter whose mean passes but whose lowest
         dimension is under the floor is revised for that dimension:
         the brief leads with it.
         a. Brief from eval+anachronism: write
            books/{book}/briefs/ch{N:02d}.md with named-passage
            prescriptions. When spine_ok is no, the brief is
            `kind: structural` (frontmatter; see /autonovel:brief
            step 5) and its `## Structural brief` names the missing
            link — which earlier event the opening must act on, which
            hand-off the ending must leave — as scene instructions.
         b. Revise: rewrite books/{book}/chapters/ch_{N:02d}.md
            per the brief, following the /autonovel:revise workflow
            (~/.claude/commands/autonovel/revise.md: it holds the
            cast to draft step 3d and answers the first reader's
            report). Regenerate
            books/{book}/chapters/ch_{N:02d}.summary.md and stamp
            it (`autonovel _stamp-summary --book {book} --chapter {N}`).
         c. Re-evaluate. score_v2.
         d. Keep whichever version scored higher (on a tie of
            the mean, the one with the higher weakest_score); the
            other version is in the preamble checkpoint and
            recoverable via autonovel rollback. Restore the kept
            version's summary with it.
         e. Last, run `autonovel mechanical summary-check
            books/{book} --chapters {N}`. If chapter N is not
            `fresh` (its prose changed after the summary, or the
            kept version's summary was lost), rewrite the summary
            from the chapter as it now stands and stamp it. Chapter
            N+1's drafter reads this summary as its memory of
            chapter N.

      5. PROMOTE CANON (skip if --no-promote):
         **invoke the safe in-sweep helper via Bash:**

           autonovel _promote-canon --book {book} --no-lock --format json

         The --no-lock flag is load-bearing — the parent
         draft-pass holds the in-progress lock, so the helper
         must skip the lock check. Without --no-lock it would
         refuse to run and per-chapter canon promotion would
         silently fail (author bug-report 2026-04-26). DO NOT
         invoke /autonovel:promote-canon as a slash-command —
         that routes through the slash-command's preamble and
         hits the same lock collision.

         The helper does the full de-dup / contradiction /
         research-tagged-supersedure / conflict-block pipeline
         atomically (same logic the slash-command runs; see
         commands/promote-canon.md). Parse the JSON output;
         books[0].promoted is the P count for the status line
         below.

      Return EXACTLY this single line as your final message
      (nothing else):

      [ch N] draft Xw · anach Y · eval s1 (low D d) · spine K [→ revise → eval s2 (low D d)] · final s · canon +P

      Where: X = final word count, Y = anachronism hit count or
      "—" if skipped, s1 = score_v1, D d = the weakest dimension
      and its score (⚠ after it when under the floor), K = ✓ or ✗
      from the SPINE
      CHECK ("—" if skipped), s2 = score_v2 (only if
      revise ran; otherwise "—"), s = the kept score, P = count
      of canon entries promoted (or "—" if --no-promote).
      ```

   b. Capture the subagent's return string. Append to the running
      progress list (you will print these in the summary at step
      6). Print the line immediately so the user has live progress.

      Then use `bash` to mark the chapter complete in the sweep-
      progress file:

      ```
      autonovel _sweep-mark-done --chapter N --summary "<the one-line return>"
      ```

      This is best-effort — if the helper errors (e.g. the file
      was deleted), don't retry; continue to the next chapter.

   c. Move to chapter N+1. The subagent terminates; its working
      memory (the chapter prose, the eval JSON, the brief, etc.)
      is discarded — only the one-line summary persists in your
      parent context.

   **Critical: do NOT call `autonovel _begin` or `autonovel _end`
   yourself, and do not let the subagent call them either. The
   parent command holds the series lock for the entire sweep.**

4. **Final promote-canon sweep** (skip if `--no-promote`). After
   the loop completes, run promote-canon one last time to catch
   anything pending that didn't get promoted in the per-chapter
   step (typically: revise-loop additions in the very last
   chapter, or any other book's pending file if this series has
   multiple books). This is idempotent — if the per-chapter
   promotes already consumed everything, the call is a no-op
   summary line.

5. **Whole-book review.** When this sweep drafted the outline's last
   chapter, run 5a (the structure review) even without `--deep`, unless
   `--no-structure`: the editor's letter that comes next compares itself
   with it, and no later step should find the book unreviewed. With
   `--deep`, run all three:

   a. Reproduce `/autonovel:structure-review --book {book}`'s workflow
      inline, first: the book-level structural pass (through-line,
      causal chain, escalation ladder, removability, climax build);
      writes `books/{book}/edit_logs/structure_review.json` and
      `structure_review.md` (the candidates `brief --from auto` turns
      into structural briefs). It runs first because review's
      stop-revising verdict is gated on it.
   b. Reproduce `/autonovel:reader-panel --book {book}`'s workflow
      inline. Four-persona pass over the full manuscript; writes
      `books/{book}/edit_logs/reader_panel.json`.
   c. Reproduce `/autonovel:review --book {book}`'s workflow
      inline. Opus dual-persona (literary critic + professor of
      fiction) pass; writes `books/{book}/edit_logs/review.md` and
      `review.json` (the parsed items `brief --from review` reads).

   Both produce REPORTS, not chapter changes. The summary table in
   step (6) names which chapters each report flags so the user can
   pick what to act on. The natural next step is
   `/autonovel:revision-pass --chapters <list>` against the flagged
   chapters, or `/autonovel:revise <N>` per chapter for the deepest
   issues. We do NOT auto-revise from these reports because (a)
   they often disagree with each other, and (b) a structural
   recommendation (e.g. "cut chapter 12") needs human judgement.

6. **Print a summary table** in the postamble footer:

   ```
   chapter | draft (words) | anach | eval v1 | eval v2 | final | lowest       | revised?
   --------|---------------|-------|---------|---------|-------|--------------|----------
        4  | 3100          | 0     | 7.4     | —       | 7.4   | prose 7.2    | no
        5  | 2950          | 2     | 5.9     | 6.7     | 6.7   | pull 6.3 ⚠   | yes
        6  | 3200          | 1     | 7.6     | 7.7     | 7.7   | place 7.1    | yes (place 6.8)
   ```

   The lowest column is the kept version's weakest dimension, ⚠ under
   the floor; a chapter revised for a dimension shows the v1 low in
   brackets.

   Plus a one-paragraph headline ("Drafted 3 chapters; 1 revised
   on low score; 4 candidate canon entries promoted; 0 conflicts.").

   With `--deep`: append a second block showing the structure
   review's score, verdict and removable chapters, then reader-panel
   and review highlights — top 3 panel concerns, top 3 review items —
   plus the chapter list each one flags. This is the user's
   shopping list for the next revision-pass.

   List every chapter whose SPINE CHECK ended ✗ after the revise loop
   as "chapters that still do not follow from the one before" — a
   structural signal no score in the table shows.

6a. **Clear sweep-progress tracking.** Use `bash` to invoke
    `autonovel _sweep-clear`. The sweep is over;
    `.autonovel/sweep-progress.json` is no longer needed. (If
    `/autonovel:resume` finds the file from this point on, that
    means a *new* sweep started and was interrupted.)

7. **Postamble: write a multi-line `next_standard_step` reflecting
   what the sweep just produced.** A multi-chapter draft sweep
   (especially with `--deep`) leaves multiple concurrent
   next-actions; the default single-line `next_standard_step` is
   wrong because `/autonovel:next` would otherwise pick one and
   miss the rest. Same shape as `revision-pass.md` step 6 — a
   numbered list of the cases that apply, with state filled in
   from *this run*:

   ```
   1. Verify per-chapter scores: <N> chapter(s) ended below
      threshold, or with a dimension under the floor, despite the
      inline retry-revise: <list, each with its lowest, e.g.
      "7 (place 6.9)">.
      Run /autonovel:revision-pass --chapters <list> --book {book}
      to deepen them.
      <OR "All chapters ≥ threshold." when N=0>

   2. Resolve canon conflicts: <K> entry/entries in
      books/{book}/pending_canon.md as conflicts.
      Open it and follow the HOW TO RESOLVE block at the top.
      <OR "No conflicts; pending_canon.md is clean." when K=0>

   3. <only when --deep ran:> Structure review: <score>/5, removable
      <list or "none">; reader-panel + review flagged:
      <chapter list from those reports>.
      Act on them: /autonovel:revision-pass --chapters structural
      (structure candidates) and/or --chapters <list> (panel/review)
      <OR "Structure gate passes; reader-panel + review flagged
       nothing." when empty>

   4. <only when this sweep drafted the outline's last chapter
      and --deep did NOT run:> The structure review ran (step 5):
      <score>/5, gate <PASS|BLOCK>. Next, the editor's whole-book
      read:
        /autonovel:developmental-edit --book {book}
      then a revision pass on its letter, the re-read, and the
      reader panel and dual-persona review once the structure gate
      passes (`/autonovel:next` walks the order).
      <for a sweep that did not reach the last chapter: "Draft the
      remaining chapters: /autonovel:draft-pass --chapters <rest>">

   5. Backup the substantive change:
        cd ~/<series-root>
        git add . && git commit -m "Draft pass: chapters <range>" && git push
      <OR omit when no git remote is set up>

   6. After acting on (1)/(3), decide whether to run another
      revision-pass on any newly-flagged chapters, or move on
      to /autonovel:title, /autonovel:introduction,
      /autonovel:typeset, /autonovel:package.
   ```

   Substitute the actual values: count + list of below-threshold
   chapters, count of pending-canon conflicts (read
   `books/{book}/pending_canon.md` to count `## Conflict N`
   blocks), the chapter range that was swept, the panel+review
   flagged lists when `--deep` ran. Pass the whole multi-line
   block to the postamble via `autonovel _end
   --next-standard-step "<rendered text>"`:

   ```
   autonovel _end --command autonovel:draft-pass \
       --args "<the original $ARGUMENTS>" \
       --status ok \
       --wrote <every-path-actually-modified> \
       --next-standard-step "$(cat <<'EOF'
   1. Verify per-chapter scores: ...
   2. Resolve canon conflicts: ...
   3. (--deep only) Structure review + reader-panel + review flagged: ...
   4. (no --deep) Run whole-book reviewers (structure-review first): ...
   5. Backup: git add . && git commit && git push
   6. After acting on (1)/(3), ...
   EOF
   )"
   ```

   Without `--next-standard-step`, the auto-computed
   `_next_step_for(series, book)` wins — usually "draft N+1" —
   and the closer is dropped on the floor. `/autonovel:next` then
   misroutes the user.
</workflow>

<files-touched>
This sweep delegates to the same set of files each underlying command
touches. For the contract record:

Reads:
- `project.yaml`
- `shared/world.md`, `shared/characters.md`, `shared/canon.md`,
  `shared/events.md`, `shared/period_bans.txt`
- `books/{book}/canon.md` (this book's own canon)
- `shared/research/notes/*.md` (when the outline names them)
- `books/{book}/voice.md`, `books/{book}/outline.md`
- `books/{book}/chapters/ch_{chapter}.md` (during retry / revise)
- `books/{book}/chapters/ch_*.summary.md` (rolling continuity)
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json` (read by brief --from auto)
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.md` (read between eval and brief)

Writes (per chapter in range, plus the end-of-sweep promote):
- `books/{book}/chapters/ch_{chapter}.md`
- `books/{book}/chapters/ch_{chapter}.summary.md`
- `books/{book}/eval_logs/ch{chapter:02d}_eval.json`
- `books/{book}/edit_logs/first_read_ch{chapter}.md` and, when the first
  reader found serious items, `first_read_ch{chapter}_2.md`
- `books/{book}/edit_logs/ch{chapter:02d}_anachronism.md`
- `books/{book}/briefs/ch{chapter:02d}.md` (only if revise loop fires)
- `books/{book}/pending_canon.md`
- `books/{book}/canon.md` (per-chapter + end-of-sweep promote, only if not --no-promote)
- `shared/canon.md` (same promote; research-cited entries only)
- `books/{book}/edit_logs/structure_review.json` + `structure_review.md`,
  `reader_panel.json`, `review.json` + `review.md` (only with `--deep`)
</files-touched>

<acceptance>
- For every chapter N in the resolved range,
  `books/{book}/chapters/ch_{N:02d}.md` exists, parses YAML
  frontmatter, is at least 2000 words.
- For every chapter N,
  `books/{book}/chapters/ch_{N:02d}.summary.md` exists and is
  100-400 words.
- Unless `--skip-eval` was passed, every chapter has a fresh
  `books/{book}/eval_logs/ch{N:02d}_eval.json`.
- Unless `--no-anachronism`, every chapter has a fresh
  `books/{book}/edit_logs/ch{N:02d}_anachronism.md`.
- Unless `--no-revise-low` or `--skip-eval`, every chapter that
  scored below threshold on its first eval has a corresponding
  `books/{book}/briefs/ch{N:02d}.md` from the revise loop, and the
  final chapter file is whichever version (draft or revise) scored
  higher.
- Unless `--no-promote`, the sweep ends with at most a few entries
  remaining in `books/{book}/pending_canon.md` (only the conflicts).
- A summary table is printed in the postamble footer.
</acceptance>
