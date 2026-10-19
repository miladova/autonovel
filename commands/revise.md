---
name: autonovel:revise
description: Rewrite one chapter from a brief, preserving voice and continuity.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - shared/craft/*.md
  - books/{book}/voice.md
  - books/{book}/cast.md
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/briefs/conversation.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{prev}.md
  - books/{book}/edit_logs/last_read.json
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/pending_canon.md
  - books/{book}/briefs/conversation.md
  - books/{book}/edit_logs/diff_*.html
  - books/{book}/edit_logs/diff_*.json
  - books/{book}/edit_logs/story_map.html
  - books/{book}/edit_logs/story_map.json
context_mode: book
---

<purpose>
Rewrite chapter `{chapter}` of book `{book}` by following
`books/{book}/briefs/ch{chapter:02d}.md` literally. Preserve voice,
world, and character continuity; obey the brief's cut list, rewrite
list, and target length. Successor to `gen_revision.py`. Bells
learning: the writer overshoots briefs by ~30%; the brief itself
already bakes in the ~0.77 correction, so write to the brief's stated
target, not a mental "safe" overshoot.
</purpose>

<workflow>
**Read-failure policy.** When `file_read` errors on any input
EXCEPT the chapter file at step 6, do NOT retry — note the gap
and proceed. The chapter file at step 6 is load-bearing (we're
rewriting it); failure to read it is a hard stop. Catches the
2026-04-25 retry-loop bug class where a single missing summary
file blocked a full revision-pass.

1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   Missing args are a usage error — stop with a one-line reminder.

2. Use `file_read` on `project.yaml` to resolve the book entry and the
   defaults block.

3. Use `file_read` on `books/{book}/briefs/ch{chapter:02d}.md`. If the
   brief is missing, stop and surface:
   "run `/autonovel:brief {chapter} --book {book}` first".

   Read the brief's frontmatter `kind`. `kind: structural` (written by
   `/autonovel:brief` from a `/autonovel:structure-review` candidate)
   changes what this rewrite may do — see step 7a. No frontmatter, or
   `kind: prose`, is a prose brief: rewrite the chapter as it stands.

3a. **Fold queued conversation suggestions into the brief.**
    Use `file_read` on `books/{book}/briefs/conversation.md` if it
    exists. Find every turn block where `Target: chapter {chapter}`
    AND `Status: queued`. Treat each such block's
    `Answer / suggestion:` body as additional brief content,
    appended to the main brief in your working memory. The
    conversation log entries are first-class brief input — they
    came from the author hand-curating edits via
    `/autonovel:talk`. If the file is missing or no queued entries
    target this chapter, proceed normally.

4. Use `file_read` on the canon: `shared/world.md`,
   `shared/characters.md`, `shared/canon.md`, and this book's own
   `books/{book}/canon.md`. These are guardrails, not
   raw material — the chapter must not contradict them.

5. Use `file_read` on `books/{book}/voice.md` (Parts 1, 2, 3, AND 4).
   The voice fingerprint is the most important input after the
   brief.

   Part 3 is the custom rubric — book-specific writing rules the
   rewrite must honour. The brief's `## Custom-rubric findings`
   section names which rules were flagged in the prior eval; the
   rewrite must fix those *and* not introduce fresh violations of
   any other Part 3 rule.

   Part 4 is per-character voice fingerprints. When present, apply
   each character's block at every line of their dialogue AND (for
   the POV character) at every interiority sentence. The revise
   pass is the right place to *intensify* per-character voice — a
   first draft often has every character converging on the
   narrator's register; the rewrite should make each character
   recognisable from a single line of dialogue. If a character's
   line in the prior draft could plausibly belong to any other
   speaker in the book, that's the line to rewrite first.

5a. When `books/{book}/cast.md` exists, use `file_read` on it and on
   `shared/craft/CHARACTER.md`. The rewrite holds the people on stage to
   `/autonovel:draft` step 3d: each who matters has a want of their own
   in the scene, the dossier's contradiction shows in an act, a
   `pressure choices` entry for this chapter is staged, and its `on the
   page` line for this chapter is delivered. A brief item quoting a first
   reader's "Who felt real" or "Couldn't picture" is answered from the
   dossier and from the places notes (draft step 3c's set piece), not by
   adding adjectives.

6. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md` (the
   current draft — the raw material the rewrite carves from). This
   read IS load-bearing; if it fails, stop with a one-line message
   ("cannot read current chapter; check books/{book}/chapters/").

   Then, **best-effort (do not retry on failure)**, use the `Bash`
   tool to run exactly once:

   ```
   autonovel _tail-chapter --book {book} --chapter {prev} --words 2000
   ```

   The helper reads `books/{book}/chapters/ch_{prev}.md`, strips
   YAML frontmatter, and prints the last 2000 words of the previous
   chapter as continuity flavour, in one deterministic shot (no
   `file_read` line-range gymnastics). If the helper exits non-zero
   or returns no output: **do not retry** — note the gap in the
   eval log and proceed without the prior-chapter quote. The brief
   is the load-bearing input here; the quote is a flavour assist.

7. Draft the rewrite. Follow the brief exactly. Use `file_read` on
   the craft reference documents in the series first:
   `shared/craft/PROSE.md` (sentence, paragraph, scene and dialogue
   mechanics), `shared/craft/CRAFT.md`, `shared/craft/ANTI-SLOP.md`
   and `shared/craft/ANTI-PATTERNS.md`; if `shared/craft/` is missing,
   run `autonovel refresh-templates` with `bash` first. Where
   `books/{book}/voice.md` Parts 1–3 explicitly override one of them,
   the voice file wins (same precedence rule as `/autonovel:draft`
   step 10). Otherwise honor the anti-pattern rules:
   - No triadic sensory lists (X. Y. Z.)
   - No "He did not [verb]" more than once
   - No "He thought about [X]" constructions
   - No "the way [X] did [Y]" more than twice
   - No "not X, but Y" formula in narration
   - No over-explaining after showing
   - At most two section breaks
   - At least one moment that genuinely surprises
   - 70%+ in-scene (dialogue and action, not summary)
   - Dialogue sounds like speech, not written prose
   When the brief has a `## Register edits` section, apply every
   entry as a line edit where it stands before doing anything else,
   and keep the information it removes from a mouth where the entry
   says it goes. After the rewrite, run
   `autonovel mechanical register books/{book} --chapter {chapter}`
   with `bash` and read the candidates against the voice file's
   declared register (its `FK grade band`, its refusals): fix any
   uncontracted negative in narration that is not an emphasis, any
   utterance over 40 words that is a lecture, and any line that
   explains to its listener what the listener can see. This is the
   same check `/autonovel:evaluate` scores as `register`; catching
   it here saves an eval-brief-revise cycle.
   Preserve the chapter's YAML frontmatter (`book`, `chapter`, `pov`,
   `story_time`, `events`) verbatim; update `status` to `revised` and
   recompute `word_count`.

7a. **Structural brief (`kind: structural`).** The brief's `## Structural
    brief` section changes the chapter's job in the book, and the
    rewrite is allowed to restructure the chapter to do it:
    - Add, cut, merge or reorder scenes **inside this chapter**; move a
      reveal into or out of it; write the consequence scene that makes
      this chapter happen because of an earlier one; retarget the
      chapter's stake onto the book's through-line; change the ending
      so the next chapter has a fact to act on. Do each move the brief
      names, and no other structural move.
    - Keep every fact later chapters consume (names, dates, sums,
      objects, who knows what) unless the brief says to change it, and
      keep the POV, the `story_time` window and the period record.
    - **Never touch another chapter.** The brief's `## Cross-chapter
      operations — run these yourself` lines (`/autonovel:merge-chapters`,
      `/autonovel:remove-chapter`, `/autonovel:reorder`,
      `/autonovel:split-chapter`, …) are for the author; do not execute
      them and do not imitate them by rewriting a neighbour. Print each
      one verbatim at the end of the run under "Cross-chapter
      operations the structure review asked for — run these yourself".
    - Length follows the brief's `## Target length` and its stated
      range (±25% for a structural brief).
    - The structural change outranks line edits: when a `## Register
      edits` or `## Specific cuts` item sits in a scene the structural
      brief removes or rewrites, drop that item.
    - The regenerated summary (step 9) must make the new link visible:
      its **Plot** names the earlier event this chapter now acts on and
      the result the next chapter needs.

8. Use `file_write` to overwrite
   `books/{book}/chapters/ch_{chapter}.md` with the full revised
   chapter. Do not truncate. Do not summarize.

8b. **Re-evaluate the chapter title.** Read the chapter's current
    frontmatter `title:` field. If the rewrite changed the
    chapter's central beat — step 6 added or removed a major
    plot moment, the cast shifted significantly, or the chapter
    now ends on a different decision — regenerate the title using
    the same 2-6 word evocative-phrase shape as `commands/draft.md`
    step 11 (Concrete object/phrase from the chapter's central
    beat; not a plot summary; avoid cliché and generic
    abstractions). Update the frontmatter `title:` field as part
    of the chapter rewrite (preserve everything else verbatim).
    When the rewrite was a polish pass that didn't change the
    central beat, leave the title alone. typeset surfaces the
    title in TOC + chapter opening + running header, so a stale
    title misleads the reader.

9. **Regenerate the chapter summary.** Use `file_write` to overwrite
   `books/{book}/chapters/ch_{chapter}.summary.md` with a fresh
   150–250 word continuity summary. **The shape and section list
   are exactly those defined in `/autonovel:draft` step 12** — see
   that file for the canonical seven labelled sections (Location,
   Plot, POV state, Cast on stage, Threads opened, Threads closed,
   Story time). Do NOT inline a different list here; defer to
   draft.md's spec so the two stay in sync. The summary must
   reflect the *revised* chapter, not the draft it replaced.

   Specifically: if the chapter's setting changed in the rewrite
   (a scene moved from Venice to Padua, say), update the **Location**
   field accordingly. Cast on stage entries are similarly
   refreshed for the new prose. The whole point of regenerating
   the summary post-revise is that downstream readers (the next
   chapter's drafter, `/autonovel:chapter-summary`'s table) see
   the current state, not the pre-revision one.

10. Use `file_write` to append any new candidate canon facts to
    `books/{book}/pending_canon.md` (or add a single `no new facts`
    line if the rewrite established nothing new). Never edit
    `shared/canon.md` directly — that is what `/autonovel:promote-canon`
    is for.

11. **Mark folded conversation entries as applied.** If step 3a
    found queued turns targeting this chapter, use `file_write` to
    rewrite `books/{book}/briefs/conversation.md` with each of
    those turn blocks' `Status:` line changed from `queued` to
    `applied`. Other turns and other fields must be preserved
    byte-for-byte — only the matching `Status: queued` lines flip
    to `Status: applied`. If no entries were folded, do not touch
    the file.

12. **Hand the chapter back as a diff.** An author who has already
    read this chapter must not have to read it whole again to find
    what the rewrite did. Use `bash` to run, from the series root:

    ```
    autonovel mechanical diff-chapters --book {book} --from last-read --chapters {chapter} --if-read
    ```

    It compares the chapter as the author last read it — the version
    `books/{book}/edit_logs/last_read.json` records, which
    `/autonovel:diff --mark-read` writes — with the rewrite on disk,
    and writes the page `books/{book}/edit_logs/diff_*.html` (named for
    the chapter, with its data file `diff_*.json`, and the story map
    `books/{book}/edit_logs/story_map.html` / `story_map.json` rebuilt
    beside it). When there is no bookmark, or the chapter did not exist
    in the version last read, it writes nothing and prints
    `"skipped": "<reason>"`: say nothing about it. Otherwise end the
    final report with:

    ```
    What changed in chapter {chapter} since you last read it: <open>
      (<html>) — <hunks> changes, <big_hunks> big, +<words_added> −<words_removed> words.
      The page opens on the changes; Whole chapter and Clean text show the same text whole.
    ```

    (`open` and `html` come from the helper's JSON.) For a plain note
    and a big/small flag on every change, the author can run
    `/autonovel:diff --book {book} --from last-read --chapters {chapter} --annotate`.
    Do not pass `--mark-read`: the author marks the version read after
    reading it. Inside `/autonovel:revision-pass` skip this step — the
    sweep hands the whole range back at the end. Best-effort: if the
    helper fails, say so in one line and finish.
</workflow>

<acceptance>
- `books/{book}/chapters/ch_{chapter}.md` exists, parses YAML
  frontmatter, and carries `status: revised` plus a fresh `word_count`.
- The rewrite differs from the prior draft (not a byte-for-byte copy).
- Chapter length is within ±15% of the brief's stated target (±25% for
  a `kind: structural` brief, or the range the brief states).
- A structural rewrite changed only this chapter's file (and its
  summary / pending canon); every cross-chapter command in the brief
  was printed for the author, none was executed.
- `books/{book}/chapters/ch_{chapter}.summary.md` exists and reflects
  the revised chapter (mtime is newer than the chapter file's prior
  draft).
- `books/{book}/pending_canon.md` grows by at least one line (either a
  candidate fact or the explicit `no new facts` marker).
- Any `briefs/conversation.md` entries with
  `Target: chapter {chapter}` + `Status: queued` are flipped to
  `Status: applied` exactly once. Untouched turns are byte-identical.
- When the author had read the chapter (`last_read.json` exists and
  the chapter was in that version), the final report names the diff
  page from step 12; the bookmark itself is unchanged.
</acceptance>
