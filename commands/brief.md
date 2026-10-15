---
name: autonovel:brief
description: Generate a revision brief for one chapter from cuts, eval, panel and review feedback, and (optionally) targeted research notes.
argument-hint: "<chapter-number> --book <short-name> [--from cuts|eval|panel|review|auto] [--enrich-with <research-notes-path>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/edit_logs/ch{chapter:02d}_cuts.json
  - books/{book}/edit_logs/reader_panel.json
  - books/{book}/edit_logs/review.json
  - books/{book}/eval_logs/*.json
  - shared/research/notes/*.md
writes:
  - books/{book}/briefs/ch{chapter:02d}.md
context_mode: book
---

<purpose>
Produce `books/{book}/briefs/ch{chapter:02d}.md` — the targeted revision
instructions the next `/autonovel:revise` run will follow literally.
Default source is `auto`: detect the weakest chapter and assemble a
brief from whatever artifacts are newest (eval log, cuts file, reader
panel). Successor to `gen_brief.py`.

A good brief names specific passages to change, not vague moods.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   `--from` is one of `cuts`, `eval`, `panel`, `review`, or `auto`
   (default `auto`). `--enrich-with <path>` (optional) names a research notes
   file (typically `shared/research/notes/<slug>.md` produced by
   `/autonovel:research`) whose detail the rewrite should weave in
   *lightly* — see step 5b. Missing required args are a usage error
   — print a one-line reminder and stop.

2. Use `file_read` on `project.yaml` and `books/{book}/voice.md` for
   voice guardrails the brief must preserve (body-first emotion, no
   telling after showing, no triadic sensory lists, 70%+ in-scene,
   etc. — pull these from the voice.md Part 2 body, don't invent them).

3. Use `file_read` on `books/{book}/chapters/ch_{chapter}.md`. If
   missing, surface the gap and stop.

4. Load source artifacts per `--from`:
   - `cuts`: read
     `books/{book}/edit_logs/ch{chapter:02d}_cuts.json` (run
     `/autonovel:adversarial-edit` first if missing).
   - `eval`: read the most recent
     `books/{book}/eval_logs/ch{chapter:02d}_*.json` file.
   - `panel`: read `books/{book}/edit_logs/reader_panel.json` and
     isolate the entries that name this chapter number (the ten
     answers per reader, the `disagreements` list and the
     `custom_rubric` violations).
   - `review`: read `books/{book}/edit_logs/review.json` (written by
     `/autonovel:review`) and isolate the `items` whose `full_text`
     names this chapter number. Each item carries `severity`,
     `type`, `qualified` and a concrete fix; unqualified `major`
     items lead the brief.
   - `auto`: read whichever of the above exist, preferring the most
     recent. If two or more exist, merge signals (cuts weighted highest
     because they're the most concrete, then review items, then eval,
     then panel). The panel and the review are the only sources that
     see across chapters; when either names this chapter, the brief
     carries it even if the chapter's own eval score is high.

5a. **Load enrichment research** (only when `--enrich-with <path>`
    was supplied). Use `file_read` on the named file. Treat the
    file's `## Material detail` and `## People and institutions`
    sections as the well to draw from. Identify which scenes in the
    chapter the research is *relevant to* — typically scenes where
    a person, place, institution, or material item from the
    research notes appears or could plausibly appear. Skip scenes
    where forcing in research detail would distort the chapter's
    existing focus. **The research is a brush, not a chisel:** the
    rewrite must add 1–2 period-specific details per relevant scene,
    not restructure or expand the chapter.

5. Draft the revision brief. Required sections, as Markdown H2s:
   - `## Chapter {chapter} — revision target` (one-line goal)
   - `## What works` (two or three sentences from the source material)
   - `## What drags` (concrete, quote-level, ordered by impact)
   - `## Specific cuts` (quoted passages to remove, carried over from
     the cuts JSON if present)
   - `## Specific rewrites` (before → after snippets where the source
     suggested them)
   - `## Structural findings` *(only when the panel or the review
     names this chapter)* — one bullet per finding, most severe
     first, each with the source (`review item N` or the reader's
     name), the finding in one sentence, and the prescription as a
     scene instruction: what happens on the page, where in the
     chapter, who is present, what changes by the end. These are
     the developmental-edit items the per-chapter eval cannot see:
     a clock set here and paid offstage in the next chapter, a
     pivot told in pluperfect or indirect speech instead of played
     as a scene, a character who acts without a motive, a win with
     no victim on the page, a scene whose stake is only cited.
     A structural finding outranks every line edit below it; when
     one asks for a new scene, the `## Target length` section
     allows for it instead of asking the revise to fit it into the
     old count.
   - `## Voice guardrails` (bulleted — preserve from voice.md Part 2)
   - `## Enrichment from research` *(only when `--enrich-with` was
     given AND step 5a found at least one scene where the research
     is relevant)*. For each relevant scene, write one bullet:
       - **Scene index** (from the existing eval log's
         `beat_coverage.scenes` if available, otherwise eyeball it)
         and the scene's opening line as identifier.
       - **The research detail to add**, named specifically (a
         person's official title, a building's location, a material
         object's price or scale, a named institution's process).
         Quote the citation `[shortname]` from the notes so the
         rewrite knows the provenance.
       - **What NOT to change**: plot, dialogue, voice, scene
         structure, scene length (±5%), POV positioning. Enrichment
         is texture; the existing scenes stay shaped as they are.
     Cap at 4 enrichment bullets per chapter — more than that and
     the rewrite stops being light. Omit the section entirely when
     `--enrich-with` was not given OR no scenes warranted it
     (don't force-fit research where it doesn't belong; chapters
     that simply don't touch the researched topic stay clean).
   - `## Weak scenes` *(only when the eval log's
     `beat_coverage.weakest_scenes` array has any entries)* — for
     each entry, write one bullet naming the scene by index, the
     missing beat(s) (goal / conflict / disaster_or_decision /
     consequence), and the prescription verbatim from the eval log
     (or a sharpened version). This is what turns "tighten chapter
     8" into "scene 8.2 needs a decision before the break" — the
     single most surgical brief surface. Quote the scene's
     `opening_line` so the rewrite knows exactly which scene to
     touch. Omit the section when no scenes are weak.
   - `## Stability check` *(only when the eval log's
     `irreversible_change` score is below 7)* — name the chapter's
     final scene, name what reverted (board reset to opening / change
     softened / no consequence committed), and prescribe ONE specific
     irreversible commitment the rewrite must add: a death, a public
     revelation, a signed contract, a destroyed object, a refused
     offer, an oath broken, a door closed. Use the eval log's
     `irreversible_change.fix` verbatim or sharpen it; never fall
     back to vague "raise stakes" — the Stability Trap (AI's default
     to safe, round-edged endings) is the named ceiling failure from
     the Bells production, and only specific irreversible commitments
     break it. Omit the section when the score is ≥7.
   - `## Register edits` *(only when the eval log carries a
     non-empty `register_edits` array)* — copy every entry as one
     bullet: `L{line_no} ({kind}): "{quote}" → "{rewrite}" — {why}`.
     These are line edits, not rewrites: the revise applies them
     where they stand and changes nothing around them. Lead with the
     dialogue entries, because exposition in a character's mouth
     ("That's San Giacomo's bell, at the end there") is the failure
     a reader hears first; for each, say where the information goes
     instead (narration, a character who doesn't know it, or
     nowhere). Add one line with the scanner's numbers from the
     `register` dimension (narration FK grade vs the voice file's
     band, contraction ratio, mean utterance length, count of
     utterances over 40 words) so the revise can re-measure. Omit
     the section when the array is empty or absent.
   - `## Custom-rubric findings` *(only when present)* — for every
     criterion in the eval log's `custom_rubric` array (or the panel
     log's `custom_rubric` block) that scored below 6 or was named
     by any reader, write one bullet: the rule, the violation
     finding, and the prescription (what the revise should do
     instead). These are the book-specific rules from voice.md Part
     3. They are NOT optional — a brief that ignores a flagged
     custom-rubric finding will produce a revise that still violates
     the rule. Omit the section entirely when no findings apply.
   - `## Target length` (in words — the Bells learning is that
     `gen_revision` overshoots ~30%, so brief for `target × 0.77` if a
     final target applies)

6. Use `file_write` to save to
   `books/{book}/briefs/ch{chapter:02d}.md`. Overwrite any prior brief
   for this chapter — briefs are disposable working documents, not
   canonical artifacts.

7. Print the target length and the count of specific cuts / rewrites
   collected.
</workflow>

<acceptance>
- `books/{book}/briefs/ch{chapter:02d}.md` exists and contains every
  required H2 section from step 5.
- The brief quotes at least one passage from the chapter (no brief can
  be voice-only hand-waving; specificity is the point).
- `## Target length` names a word-count number, not a vague target.
</acceptance>
