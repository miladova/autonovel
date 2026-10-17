---
name: autonovel:summarize-chapter
description: Backfill a 150-250 word continuity summary for a chapter that was drafted before summaries were standard.
argument-hint: "<chapter-number> | --all | --stale [--book <short-name>] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
writes:
  - books/{book}/chapters/ch_{chapter}.summary.md
context_mode: book
---

<purpose>
Produce a 150-250 word continuity summary at
`books/{book}/chapters/ch_{chapter}.summary.md` for an already-drafted
chapter. `/autonovel:draft` and `/autonovel:revise` write summaries
themselves; this command exists to backfill chapters drafted on an
earlier autonovel version that didn't yet ship the summary step.

Future drafts read every prior summary as continuity context. Without
summaries, chapter N+5 only has chapter N+4's last 1000 words to lean
on — which is fine for two-chapter continuity but not five.

The summary is NOT a chapter summary for the reader. It is a
continuity handoff to the next drafter: what happened, who was on
stage, what threads opened, what threads closed, where in story time.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Three modes:

   - **`<chapter-number>`** — backfill or refresh the summary for
     one chapter (the original mode).
   - **`--all`** — sweep every chapter under
     `books/{book}/chapters/ch_*.md` that lacks a summary OR whose
     summary is older than the chapter file. Implies `--force` for
     stale ones; preserves up-to-date ones unless explicit
     `--force` is also passed.
   - **`--stale`** — same as `--all` but only refreshes summaries
     that are mtime-stale (chapter newer than summary), skipping
     chapters whose summary is current. The right shape after a
     long revise sweep that may have silently no-op'd revise step
     9 on some chapters.

   `--book` defaults via `_begin`. `--force` (in single-chapter
   mode) overwrites an existing summary (default: refuse if a
   non-trivial summary already exists). Missing chapter number AND
   no `--all`/`--stale` → stop with usage hint.

   For `--all` / `--stale`, run steps 2-7 once per target chapter,
   in ascending chapter order. Print a one-line per-chapter
   progress marker so the user can see the sweep advancing. Skip
   chapters whose summary is up-to-date (in `--stale` mode) or
   whose summary is non-trivial without `--force` (in `--all`
   mode). At the end, emit a single summary line: `Refreshed N of
   M chapter(s); skipped <list>` so the user can confirm coverage.

2. Use `file_read` on `project.yaml` to resolve the book entry,
   `pov`, and `defaults.chapter_target_words`.

3. Use `file_read` on
   `books/{book}/chapters/ch_{chapter}.summary.md` if it exists. If
   the file already contains a populated summary (>100 chars, not
   the template stub) and `--force` was not supplied, stop with a
   one-line message naming the existing file. Do not overwrite.

4. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md`. If
   the chapter does not exist, stop with a one-line message —
   summary backfill needs prose to summarize.

5. Use `file_read` on `books/{book}/voice.md` (Part 1 only — the
   summary should match series voice register, but does not need
   the per-book fingerprint) and on `books/{book}/outline.md` (just
   the entry for this chapter, for plant/payoff context).

6. Synthesize the summary. Seven sections, each one or two sentences:

   - **Location:** the dominant setting in compact form (e.g.
     `Venice / Rialto`, `Augsburg / Fugger counting-house`). One
     short phrase. Multi-location chapters: name the primary
     location with `+ <other>` after if helpful. The
     `/autonovel:chapter-summary` table prepends this to the Plot
     column for at-a-glance "which chapters are set in X?"
     filtering.
   - **Plot:** what happened (action, decisions, outcomes — not
     theme), opening with the earlier event this chapter acts on
     (or saying plainly that it opens on something new) and ending
     with the result the next chapter has to deal with — the shape
     `/autonovel:draft` step 13 defines.
   - **POV state:** what the POV character knows, wants, fears at
     the close that they didn't at the open.
   - **Cast on stage:** every named character who appeared, with
     their role this chapter.
   - **Threads opened:** new mysteries, conflicts, promises that
     future chapters need to pay off.
   - **Threads closed:** earlier setups this chapter resolved (cite
     the earlier chapter when known).
   - **Story time:** the ISO date or date range covered.

   Total length: 150-250 words. Match the chapter's tense and POV.

7. Use `file_write` to save the summary at
   `books/{book}/chapters/ch_{chapter}.summary.md`. Plain markdown,
   no frontmatter, no `# Heading` — just the seven labelled sections.
</workflow>

<acceptance>
- `books/{book}/chapters/ch_{chapter}.summary.md` exists and is
  between 100 and 400 words.
- The summary names the chapter's POV character, contains the
  chapter's `story_time`, and lists at least one thread (opened or
  closed) — these are the load-bearing fields future drafts read.
</acceptance>
