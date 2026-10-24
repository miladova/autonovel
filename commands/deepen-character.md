---
name: autonovel:deepen-character
description: Revise one or two chapters to add an unguarded moment that deepens a named character.
argument-hint: "<name> [--chapter <N>] [--book <short-name>]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/craft/CHARACTER.md
  - books/{book}/cast.md
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/*.md
writes:
  - books/{book}/briefs/ch{chapter:02d}.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_{chapter}.summary.md
  - books/{book}/pending_canon.md
context_mode: book
---

<purpose>
Sidequest: add an unguarded moment — a beat where a character is
caught off-guard by their own want / fear / secret — to one chapter.
The point is depth, not length; the revision can net-zero words if
it trades exposition for interior gesture.

Bells learning: interiority without consequence is a slop pattern. A
deepening moment MUST be observed by the POV, must change how another
character treats the deepened one (even slightly), or must close a
scene.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `<name>`. Optional: `--chapter
   <N>` to target a specific chapter; `--book <short-name>` to scope
   the search. If `--chapter` is omitted, auto-pick the chapter
   where this character has the most presence but the least
   interiority (in practice: the chapter with the most dialogue
   lines attributed to them but the fewest in-scene gestures).

2. Use `file_read` on `project.yaml`, `shared/characters.md`,
   `shared/canon.md`, `books/{book}/canon.md`, and `books/{book}/voice.md`, and, when
   present, `books/{book}/cast.md` (the character's dossier) and
   `shared/craft/CHARACTER.md` (how depth gets onto the page); take the
   unguarded moment from the dossier's fear, secret or contradiction.
   Confirm the character exists. If not, stop and suggest
   `/autonovel:add-character --name <name>`.

3. If `--chapter` was omitted, glob `books/{book}/chapters/*.md`
   and pick the target chapter per the heuristic in step 1. Print
   the chosen number to stdout so the user can intervene.

4. Use `file_read` on
   `books/{book}/chapters/ch_{chapter}.md` and
   `books/{book}/outline.md`.

5. Draft a brief targeted at the unguarded moment. Four sections:
   - **Unguarded beat**: what the moment is, in one sentence.
   - **Where it lands**: the exact paragraph or dialogue turn it
     attaches to (quote the current text, verbatim).
   - **Specific rewrites**: the new prose, in the chapter's voice.
   - **Target length**: usually the current word count ± 200.

   Use `file_write` to save the brief to
   `books/{book}/briefs/ch{chapter:02d}.md`.

6. Rewrite the chapter from the brief. Preserve YAML frontmatter,
   set `status: revised`, recompute `word_count`. Use `file_write`
   to overwrite `books/{book}/chapters/ch_{chapter}.md`. Never
   lengthen beyond ±10% unless the brief explicitly asks for it.

7. Append any new candidate canon facts to
   `books/{book}/pending_canon.md` (e.g. a newly named possession,
   a habit). Single `no new facts` line if nothing was established.

8. **Regenerate the chapter summary** to reflect the rewritten
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
- `books/{book}/chapters/ch_{chapter}.md` exists, parses YAML
  frontmatter, and carries `status: revised`.
- The rewritten chapter differs from the prior draft.
- Word count is within ±10% of the prior count unless the brief
  documented a different target.
- `books/{book}/briefs/ch{chapter:02d}.md` exists and names the
  character in its `# Chapter ... — deepening <name>` heading.
</acceptance>
