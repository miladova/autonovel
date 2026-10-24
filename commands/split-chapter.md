---
name: autonovel:split-chapter
description: Split one chapter into two; renumber subsequent chapters; update outline.
argument-hint: "--chapter <N> --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/*.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/outline.md
context_mode: book
---

<purpose>
Sidequest: split chapter `{chapter}` into two chapters and renumber
every chapter after it by +1. Updates `books/{book}/outline.md` to
match. All changes land in a single checkpoint so `autonovel rollback`
undoes the entire operation.

CLAUDE.md gotcha: "Chapter renumbering after merges/deletes must be
done by script, never hand-edited." Use `bash` with `git mv` or
filesystem `mv` in a deterministic order to perform the renumber —
never ask the LLM to rename files one-by-one.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--chapter <N> --book <short-name>`.
   Missing is a usage error.

2. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md`.
   Identify the natural split point: a scene break, a POV shift, a
   time jump, or a shift in tension. If no natural break is visible,
   stop and surface: "no clean split point — consider
   /autonovel:lengthen or /autonovel:shorten instead".

3. Use `file_read` on `books/{book}/outline.md` to recover the
   chapter's beats. The two halves must each end on a beat that
   earns its own chapter break. Also use `file_read` on
   `books/{book}/voice.md` — each half has to sustain the book's
   voice on its own, without cross-reference.

4. Use `bash` to rename every chapter whose number is > `{chapter}`,
   working from the highest number downward so no collision occurs.
   Example: if splitting ch_05 and chapters go to ch_12:
   `mv ch_12.md ch_13.md; mv ch_11.md ch_12.md; ...; mv ch_06.md ch_07.md`.

5. Draft the two halves as two complete chapters. The first keeps the
   original number `{chapter}`; the second becomes `{chapter} + 1`.
   Preserve the original YAML frontmatter on both halves (update
   `chapter` number, `word_count`; `status: revised`). Use
   `file_write` for each half: `books/{book}/chapters/ch_{chapter}.md`
   and the new next-chapter file.

6. Use `file_write` to update `books/{book}/outline.md`: split the
   original entry into two `## Chapter N` entries and renumber every
   subsequent entry by +1.

7. **Regenerate every changed chapter's summary.** Whichever
   chapters were merged / split / renamed, their `.summary.md`
   files are now stale (the new chapter has a different
   plot/cast/threads shape). Use `file_write` to overwrite each
   affected `books/{book}/chapters/ch_NN.summary.md` following
   the canonical 7-section template (Location, Plot, POV state,
   Cast on stage, Threads opened, Threads closed, Story time;
   150–250 words total per chapter), then use `bash` to run
   `autonovel _stamp-summary --book {book} --chapter NN` for each.
   A chapter that was only renumbered keeps its summary: it moved
   with the chapter and its fingerprint still matches, so leave it.
   `_end` will not close the command while any chapter whose prose
   changed has a summary describing older text (the summary gate).
</workflow>

<acceptance>
- Exactly one additional chapter file exists under
  `books/{book}/chapters/` compared to before the command.
- `books/{book}/chapters/ch_{chapter}.md` and
  `books/{book}/chapters/ch_{chapter+1}.md` both parse YAML
  frontmatter and their `chapter` field matches their filename number.
- Every chapter originally numbered > `{chapter}` is now at `+1`
  (filenames, frontmatter numbers, and outline entries all agree).
- `books/{book}/outline.md` has exactly one more `## Chapter N`
  heading than before.
</acceptance>
