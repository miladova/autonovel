---
name: autonovel:summarize-chapter
description: Write or refresh a chapter's 150-250 word continuity summary and stamp it with the chapter's fingerprint — one chapter, every chapter, or only those whose summary no longer matches.
argument-hint: "<chapter-number> | --all | --stale [--book <short-name>] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
  - task
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
writes:
  - books/{book}/chapters/ch_{chapter}.summary.md
context_mode: book
summaries: report
---

<purpose>
Produce a 150-250 word continuity summary at
`books/{book}/chapters/ch_{chapter}.summary.md` for an already-drafted
chapter, and stamp it with the fingerprint of the chapter it summarises
(`autonovel _stamp-summary`). `/autonovel:draft` and `/autonovel:revise`
write and stamp summaries themselves, and every command that reads
summaries refreshes the out-of-date ones before it reads them; this
command backfills chapters drafted before summaries existed, and
refreshes a summary on demand after a chapter was edited by hand.

Future drafts read every prior summary as continuity context. Without
summaries, chapter N+5 only has chapter N+4's last 1000 words to lean
on — which is fine for two-chapter continuity but not five.

The summary is NOT a chapter summary for the reader. It is a
continuity handoff to the next drafter: what happened, who was on
stage, what threads opened, what threads closed, where in story time.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Three modes:

   - **`<chapter-number>`** — write or refresh the summary for one
     chapter.
   - **`--stale`** — every chapter whose summary no longer matches the
     chapter as it now stands, or has none. Use `bash` to run
     `autonovel mechanical summary-check books/{book}` and take its
     `needs_refresh` list: `stale` (the chapter's text changed after
     the summary was written), `unverified` (written before summaries
     carried a fingerprint) and `missing`. The right shape after a
     chapter was edited by hand.
   - **`--all`** — every drafted chapter under
     `books/{book}/chapters/ch_*.md`, whatever its state. Implies
     `--force`.

   `--book` defaults via `_begin`. `--force` (in single-chapter
   mode) overwrites an existing summary that is still `fresh`
   (default: refuse, naming the file). Missing chapter number AND
   no `--all`/`--stale` → stop with usage hint.

   For `--all` / `--stale` with more than one target, spawn one `task`
   subagent per chapter, up to three at a time, each running steps 2–7
   for its chapter, so the chapters don't fill this conversation. Print
   a one-line per-chapter progress marker as each returns. At the end,
   run `autonovel mechanical summary-check books/{book}` again and emit
   a single line: `Refreshed N of M chapter(s); all summaries match
   their chapters` (or name any that still don't).

2. Use `file_read` on `project.yaml` to resolve the book entry,
   `pov`, and `defaults.chapter_target_words`.

3. In single-chapter mode without `--force`, use `bash` to run
   `autonovel mechanical summary-check books/{book} --chapters
   {chapter}`. If the chapter's summary is `fresh`, stop with a
   one-line message naming the file: it already matches the chapter.

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
   no `# Heading`, no frontmatter of your own — just the seven
   labelled sections. Then use `bash` to run
   `autonovel _stamp-summary --book {book} --chapter {chapter}`; it
   adds a two-line frontmatter (`summary_of:` and the chapter's
   fingerprint) that marks the summary as matching the chapter as it
   now stands.
</workflow>

<acceptance>
- `books/{book}/chapters/ch_{chapter}.summary.md` exists and is
  between 100 and 400 words.
- The summary names the chapter's POV character, contains the
  chapter's `story_time`, and lists at least one thread (opened or
  closed) — these are the load-bearing fields future drafts read.
- `autonovel mechanical summary-check books/{book}` reports the
  chapter's summary `fresh`.
</acceptance>
