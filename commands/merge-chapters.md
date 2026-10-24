---
name: autonovel:merge-chapters
description: Merge two adjacent chapters; renumber subsequent chapters; update outline.
argument-hint: "--chapters <N>,<M> --book <short-name>"
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
Sidequest: merge adjacent chapters `N` and `M` (must be consecutive,
`M = N + 1`) into a single chapter kept at number `N`, and renumber
every chapter after `M` by -1. Updates the outline to match. Lands in
one checkpoint.

CLAUDE.md: renumber by bash script, never by hand. Do the rename
upward from the lowest number to avoid collisions.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--chapters <N>,<M> --book <short-name>`.
   Reject with a usage error if `M != N + 1`.

2. Use `file_read` on both chapter files. If either is missing, stop.
   Read `books/{book}/outline.md` to recover the beats of both
   chapters — the merged chapter must still hit them.

3. Use `file_read` on `books/{book}/voice.md` — the merged chapter
   has to read as one chapter, not two stapled together; voice
   continuity matters.

4. Draft the merged chapter: combine the two halves so transitions
   are seamless, trim any handshake that only existed to span the
   original break, keep both sets of beats. Preserve the YAML
   frontmatter from chapter `N` (update `word_count`, set
   `status: revised`, and append any `events:` from chapter `M` that
   were not already on chapter `N`).

5. Use `file_write` to overwrite `books/{book}/chapters/ch_{chapter}.md`
   with the merged chapter. Use `bash` to `rm` the chapter `M` file.

6. Use `bash` to rename every chapter originally > `M` down by one,
   working from the lowest number upward so no collision occurs:
   `mv ch_(M+1).md ch_M.md; mv ch_(M+2).md ch_(M+1).md; ...`.

7. Use `file_write` to update `books/{book}/outline.md`: combine the
   two entries into one under `## Chapter N`, and renumber every
   subsequent `## Chapter` heading by -1.

8. **Regenerate every changed chapter's summary.** Whichever
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
- Exactly one fewer chapter file exists under
  `books/{book}/chapters/` than before the command.
- `books/{book}/chapters/ch_{chapter}.md` parses YAML frontmatter
  and carries a `word_count` that is within a reasonable margin of
  the sum of the two original chapters.
- Every chapter originally > `M` is now at its old number minus one
  (filenames, frontmatter numbers, outline entries all agree).
- `books/{book}/outline.md` has exactly one fewer `## Chapter N`
  heading than before.
</acceptance>
