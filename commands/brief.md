---
name: autonovel:brief
description: Generate a revision brief for one chapter from cuts, eval, panel and review feedback, and (optionally) targeted research notes.
argument-hint: "<chapter-number> --book <short-name> [--from cuts|eval|panel|review|structure|auto] [--enrich-with <research-notes-path>]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/edit_logs/ch{chapter:02d}_cuts.json
  - books/{book}/edit_logs/reader_panel.json
  - books/{book}/edit_logs/review.json
  - books/{book}/edit_logs/structure_review.json
  - books/{book}/eval_logs/*.json
  - books/{book}/edit_logs/first_read_ch{chapter}.md
  - books/{book}/edit_logs/first_read_ch{chapter}_2.md
  - shared/research/notes/*.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
writes:
  - books/{book}/briefs/ch{chapter:02d}.md
context_mode: book
---

<purpose>
Produce `books/{book}/briefs/ch{chapter:02d}.md` — the targeted revision
instructions the next `/autonovel:revise` run will follow literally.
Default source is `auto`: detect the weakest chapter and assemble a
brief from whatever artifacts are newest (eval log, cuts file, reader
panel, review, structure review). Successor to `gen_brief.py`.

A good brief names specific passages to change, not vague moods.

There are two kinds of brief, marked in a frontmatter block at the top
of the file:

- `kind: prose` — line, paragraph and scene fixes inside the chapter as
  it stands (the default; a brief with no frontmatter, written before
  this marker existed, is a prose brief).
- `kind: structural` — the chapter's job in the book changes: a
  consequence scene that makes this chapter happen *because of* an
  earlier one, a stake retargeted onto the book's through-line, a
  reveal moved, a plant for the climax, a scene cut because the
  chapter is being merged. Written when
  `books/{book}/edit_logs/structure_review.json` (from
  `/autonovel:structure-review`) has a structural brief candidate that
  names this chapter. `/autonovel:revise` is allowed to restructure the
  chapter for it; cross-chapter moves (merge, cut, reorder, split) are
  listed with the exact command for the author to run and are never
  executed by revise.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `<chapter-number> --book <short-name>`.
   `--from` is one of `cuts`, `eval`, `panel`, `review`, `structure`,
   or `auto` (default `auto`). `--enrich-with <path>` (optional) names a research notes
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
     `/autonovel:adversarial-edit` first if missing). Candidates of type
     `MISPLACED`, or with action `MOVE`, are not cuts: they go under
     `## Move, don't cut`.
   - `eval`: read the most recent
     `books/{book}/eval_logs/ch{chapter:02d}_*.json` file: every
     dimension's score, `weakest_moment` and `fix`, and its
     `first_reader` block. Read `defaults.dimension_floor` from
     `project.yaml` (the chapter threshold when unset). When the
     `first_reader` block lists items not fixed (its `open_items`;
     an older eval without them: every item of the last report
     unless `all_fixed`), read the report it
     came from, `books/{book}/edit_logs/first_read_ch{chapter}_2.md`
     when it exists, else `first_read_ch{chapter}.md`.
   - `panel`: read `books/{book}/edit_logs/reader_panel.json` and
     isolate the entries that name this chapter number (the ten
     answers per reader, the `disagreements` list and the
     `custom_rubric` violations).
   - `review`: read `books/{book}/edit_logs/review.json` (written by
     `/autonovel:review`) and isolate the `items` whose `full_text`
     names this chapter number. Each item carries `severity`,
     `type`, `qualified` and a concrete fix; unqualified `major`
     items lead the brief.
   - `structure`: read `books/{book}/edit_logs/structure_review.json`
     (written by `/autonovel:structure-review`; run it first if
     missing). First use `bash` to run `autonovel mechanical
     structure-validate books/{book}` and read its JSON: when the
     errors include a `chapter_count` mismatch, the chapters were
     renumbered since the review (a merge, cut or reorder ran) — do
     not use its candidates; say "re-run /autonovel:structure-review"
     in the brief and fall back to the other sources. When the gate
     only reports `stale`, use the candidates and note in the brief
     that they predate the latest prose. Isolate every entry in
     `candidates` whose `chapters` list contains this chapter, and for
     each its `edits` entry for this chapter, its `kind`, `command`,
     `expected_effect` and `fixes`. Also note this chapter's row in
     `causal_chain` (both the link into it and the link out of it), its
     `removability` verdict, and its act's `escalation` row — the
     brief explains *why* the chapter is being restructured in those
     terms.
   - `auto`: read whichever of the above exist, preferring the most
     recent. If two or more exist, merge signals (structural
     candidates first — a change to the chapter's job outranks every
     line edit — then cuts, weighted highest of the rest because
     they're the most concrete, then review items, then eval, then
     panel). The structure review, the panel and the review are the
     only sources that see across chapters; when any of them names
     this chapter, the brief carries it even if the chapter's own eval
     score is high.

   - **Always, whatever `--from` says:** use `bash` to run `autonovel
     mechanical repeats books/{book} --chapter {chapter} --format json`
     (wording the chapter repeats, inside itself or from earlier
     chapters; phrases it leans on; sentence pairs making one point),
     and take the eval log's `repetition` dimension (its `repeats` list)
     and any **Told again** items in the first-reader report when they
     exist. They feed `## Said already`.

4a. **The genre's payload.** Use `file_read` on the book's genre guide:
the file `_begin`'s `genre:` line names (`autonovel genre show --book
{book}` prints it when no preamble ran; it is
`shared/craft/genres/<genre>.md`, or the series' own
`shared/genres/<genre>.md`): `## The
    promise`, `## Drafting` and `## Cutting`. Nothing the promise names
    goes under `## Specific cuts` (for historical fiction: real events
    and people, daily life, how people saw the world, places and their
    names); a source that asks to cut it becomes a `## Move, don't cut`
    item. When the eval log scores a genre dimension (historical
    fiction's `history`) under the floor, it leads `## Weakest first`,
    with the items the design's `## What the reader comes to learn`
    ledger assigns to this chapter.

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

5. Draft the revision brief. It opens with a frontmatter block naming
   its kind:

   ```
   ---
   kind: structural          # or: prose
   structural_candidates: [S2, S5]   # structural only: candidate ids
   source: books/{book}/edit_logs/structure_review.json   # structural only
   ---
   ```

   The kind is `structural` exactly when step 4 found at least one
   structural candidate for this chapter; otherwise `prose` (and the
   last two keys are omitted). Required sections, as Markdown H2s:
   - `## Structural brief` *(structural only; first section after the
     frontmatter)* — the chapter's new job in one sentence, then one
     block per candidate, most important first:
       - **Candidate** `S<n>` (`<kind>`) — its title, and the
         `expected_effect` verbatim (which links become *because*,
         which chapter stops being removable, which rung rises).
       - **Why this chapter**: the causal link into it and out of it
         from `causal_chain`, its removability verdict, and its act's
         stake from `escalation`, in one or two sentences.
       - **What changes on the page**: the candidate's `instruction`
         for this chapter verbatim, then sharpened into scene terms
         — where in the chapter (which scene, by its opening line),
         who is present, what the POV decides, what is different by
         the chapter's end, and which fact the next chapter must be
         able to act on.
       - **Within-chapter moves allowed**: add, cut, merge or reorder
         scenes *inside this chapter*; move a reveal into or out of
         it; change its ending. Name each move the candidate needs.
       - **What must not change**: facts later chapters consume
         (names, dates, sums, objects, who knows what) unless the
         candidate says otherwise, the POV, and the period record.
   - `## Cross-chapter operations — run these yourself` *(structural
     only, when any candidate touching this chapter has a non-null
     `command`)* — one line per command, verbatim (e.g.
     `/autonovel:merge-chapters --chapters 15,16 --book {book}`), with
     one sentence on what it does to this chapter. These change the
     chapter list; `/autonovel:revise` never runs them. Say whether to
     run them before or after this brief's revise (a merge or cut
     runs first; then re-run `/autonovel:structure-review` because the
     numbering changes).
   - `## Chapter {chapter} — revision target` (one-line goal; when a
     dimension is under the floor, the goal names it)
   - `## Weakest first` *(whenever an eval log exists)* — the worst
     items, not the mean. Every dimension under the floor, lowest
     first; when none is, the single lowest. For each: the dimension
     and score, the judge's `weakest_moment` quoted, and its `fix`
     sharpened into an instruction on the page (which passage, what
     changes). Then every serious cold-reader item the `first_reader`
     block lists as not fixed, quoted from the report, each with the
     fix (`shared/craft/FIRST-READER.md` "What the writer does with
     it"). This section leads the prose sections: the revise is judged
     on whether the weakest dimension rose, not whether the mean did.
   - `## What works` (two or three sentences from the source material)
   - `## What drags` (concrete, quote-level, ordered by impact)
   - `## Specific cuts` (quoted passages to remove, carried over from
     the cuts JSON if present; never the genre's payload, step 4a)
   - `## Said already` *(whenever the repetition sources of step 4 find
     anything you confirm by reading the chapter)* — one entry per point
     the chapter says more than once (`shared/craft/PROSE.md` §7 rule 9):
     the point in a few words; every place it is said, by line, quoted;
     the one that **stays** (the first, or the one in the scene where it
     matters, whichever is stronger; for something an earlier chapter
     already told, the earlier chapter's); and what happens to each of
     the others (cut, folded into the one that stays, or cut to a clause
     after a long absence). A paragraph near the chapter's start that
     restates the story so far gets its own entry: cut it, and name the
     one fact in it the chapter needs and the line where it goes as a
     clause. A deliberate echo the reader is meant to hear (a payoff
     line, a letter read again) is listed as "keep, deliberate". These
     are not cuts of the genre's payload: the fact or gloss stays in the
     book, once, so step 4a does not move them to `## Move, don't cut`.
   - `## Move, don't cut` *(when any source flags payload content that
     is badly placed or delivered: `MISPLACED` / `MOVE` cuts, a first
     reader's "skimmed: it stopped the story", a review's "lecture")* —
     for each, the passage quoted, where it goes (the scene where it is
     at stake, the person who would notice or say it) or how it becomes
     a scene or a clause. The revise keeps it.
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
     final target applies). For a structural brief, first set the
     final target to the current length plus any scene the brief adds
     (typically 800–1500 words) or minus any scene it cuts, never
     below ~1800 words, then apply the 0.77 correction; state the
     final target and the allowed range (±25% for a structural brief,
     ±15% for a prose one).

6. Use `file_write` to save to
   `books/{book}/briefs/ch{chapter:02d}.md`. Overwrite any prior brief
   for this chapter — briefs are disposable working documents, not
   canonical artifacts. Then use `bash` to run
   `autonovel _stamp-brief --book {book} --chapter {chapter}`: it records
   the fingerprint of the chapter the brief was written against, so
   `/autonovel:next` knows the brief is waiting until the chapter is
   revised, and done once it is.

7. Print the brief's kind, the target length and the count of specific
   cuts / rewrites collected. For a structural brief also print the
   candidate ids and, verbatim, every cross-chapter command the author
   has to run.
</workflow>

<acceptance>
- `books/{book}/briefs/ch{chapter:02d}.md` exists, opens with a
  frontmatter block carrying `kind: prose` or `kind: structural`, and
  contains every required H2 section from step 5.
- The kind is `structural` exactly when a structure-review candidate
  names this chapter; a structural brief has a `## Structural brief`
  section with each candidate's per-chapter instruction, and lists
  every candidate `command` under `## Cross-chapter operations — run
  these yourself`.
- The brief quotes at least one passage from the chapter (no brief can
  be voice-only hand-waving; specificity is the point).
- `## Target length` names a word-count number, not a vague target.
</acceptance>
