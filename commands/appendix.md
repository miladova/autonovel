---
name: autonovel:appendix
description: Generate or scaffold a back-matter appendix (the people in the book, real and invented; timeline of real events, real-character bios, places you can still see, sources, the historical note).
argument-hint: "--book <short-name> [--sections cast,timeline,bios,places,sources,notes] [--from auto|user|both] [--story-only|--include-context] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - shared/research/notes/*.md
  - shared/sources.bib
  - books/{book}/outline.md
  - books/{book}/design.md
  - books/{book}/cast.md
  - books/{book}/appendix.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
writes:
  - books/{book}/appendix.md
context_mode: book
---

<purpose>
Back-matter content typeset weaves in after the last chapter
(post-`\backmatter`, before the colophon). For historical fiction
the appendix typically holds:

  - **The people in the book** — a cast list, real and invented,
    grouped by household or side, one line each, with the chapter
    where each first appears. Customary in historical novels with
    large casts (*Wolf Hall*'s is grouped by place and time), and
    what lets the narration introduce each person once (draft step
    3c): the reader who forgets has somewhere to look.
  - **Timeline** — real-world dates the novel touches, in
    chronological order.
  - **Bios** — short paragraphs on the historical figures who
    appear as characters (Jakob Fugger, Maximilian I, Charles V,
    etc.). 100-200 words each; what's documented vs what the
    novel invented.
  - **Sources** — a list of the primary and secondary works the
    research drew from, in scholar shape (not BibTeX raw — readable).
  - **Notes** — author's notes on what's invented vs documented
    (the *Wolf Hall* end-paper convention).

The user picks which sections via `--sections`; default is
`timeline,bios` (the two most readers want). Each section becomes
a `## Sub-heading` inside `appendix.md`, which the back-matter
builder promotes to `\section*{}` in the LaTeX output and to a
heading in the ePub.

Three modes selected by `--from`, paralleling
`/autonovel:introduction` and `/autonovel:glossary`:

  - `--from auto` (default): AI-generates each requested section
    from research notes + canon + cast.
  - `--from user`: scaffold with HOW-TO-EDIT block + section
    placeholders.
  - `--from both`: AI-draft + leave a HUMAN-PASS comment listing
    items to refine.

`--force` permits overwriting an existing appendix.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--sections <comma-list>` (default `timeline,bios`, plus `places`
   and `notes` when the book's genre guide has a `## Back matter`
   section that asks for them; allowed values `cast / timeline / bios /
   places / sources / notes`). Read that section of the book's genre guide: the
   file `_begin`'s `genre:` line names (`autonovel genre show --book
   {book}` prints it when no preamble ran; it is
   `shared/craft/genres/<genre>.md`, or the series' own
   `shared/genres/<genre>.md`): it says what this
   genre's reader expects after the last chapter. `--from
   <auto|user|both>` (default `auto`), `--force`.

2. **Refusal-on-overwrite check.** If `books/{book}/appendix.md`
   exists with substantive content (>50 chars beyond template
   stub) and `--force` was not supplied, stop with: "books/{book}/
   appendix.md already exists; pass `--force` to overwrite or
   hand-edit the file directly".

3. **Load source material.** `file_read`:
   - `project.yaml` for the book's `period.start`, `period.end`,
     `period.region` — the timeline window.
   - `shared/canon.md` for hardened series-wide facts, plus this
     book's `books/{book}/canon.md` for facts its own chapters fixed.
   - `shared/research/notes/*.md` for primary-source citations.
   - `shared/characters.md` for the cast (use this to identify
     which entries need bios — every named historical figure who
     appears).
   - `shared/sources.bib` for the bibliography.
   - `books/{book}/outline.md` for the chapter span (the timeline
     should cover events the book references plus a margin).
   - The chapters themselves for which characters/events actually
     appear in the narrative.
   - For `cast`: `books/{book}/cast.md` (who is real and who invented,
     each person's household and relation to the protagonist) and every
     `books/{book}/chapters/ch_*.summary.md` (the `**Cast on stage:**`
     line of each; the preamble has brought every summary up to date,
     so each lists the chapter as it now stands).

4. **Section generation per `--sections` flag** (in this order
   regardless of how the user listed them — a stable rendering
   order is more reader-friendly than a custom one):

   **(a0) The people in the book.** A cast list for the reader who
   wants to check who someone is. Who goes in: every person on the page
   in two or more chapters, every principal in `cast.md`, and anyone a
   later chapter names as if the reader should remember them. A walk-on
   in one scene stays out. Group them by household or side, in the
   book's own terms (the protagonist's house, a city, a court, the other
   side, another time the book visits), groups in order of first
   appearance and people within a group the same way. One line each:

   ```
   - **<Name>** — <who they are, in a phrase, and what they are to the
     protagonist>. *(ch N)* <(invented)>
   ```

   `*(ch N)*` is the chapter where the person first appears on the
   page; take it from the summaries' cast lines and check it in the
   chapter. Mark `(invented)` everyone `cast.md` or
   `shared/characters.md` marks as invented; a real person's line may
   give their dates. Say nothing that happens after the person's first
   chapters: the list is read before and during the book, and a line
   that says who betrays whom spoils it. Never list a person the
   chapters don't contain.

   **(a) Timeline — three-source merge.** Walk three sources of
   timeline rows and merge them with distinct markers per source:

   Three visually distinct markers — typeset-safe Unicode
   geometric shapes paired with distinct font weights so the
   category is unmistakable at a glance:

     **◆ in story** (filled diamond, bold) — depicted in the novel.
     *◇ referenced* (open diamond, italic) — real event prose mentions.
     ○ context (open circle, plain) — real, period-only context.

   The three rendering categories:

   - **`◆ in story`** — Mechanical pass; pulled from chapter
     summaries' `## Story time` sections + each chapter's
     frontmatter `events:` array. The dates the book actually
     depicts. Run via `bash`:

     ```
     autonovel mechanical timeline-extract books/{book} --format json
     ```

     Returns rows with `source: "narrative"` and a `chapter`
     field pointing at the chapter. The slash-command's job is
     to enrich each row's `description` field with a one-clause
     summary from the chapter's `## Plot` section.

   - **`◇ referenced` Real, mentioned in the prose.** Walk every
     chapter's prose for real-world events the book mentions but
     doesn't depict (e.g. "the sack of Constantinople, forty
     years before"). Cross-reference each candidate against
     `shared/research/notes/*.md` and `shared/canon.md` —
     emit a row only when a research note corroborates the date.
     Skip if `--story-only` was passed.

   - **`○ context` Real, context-setting.** LLM-curated events
     the prose doesn't mention but the reader should know to
     follow the period (the *Wolf Hall* end-paper convention).
     Walk research notes for period-relevant entries the prose
     doesn't reference; pick events that thematically connect
     (the same political crisis, the same trade route, the same
     intellectual movement). Cap at ~10 such rows so the timeline
     stays focused. Default OFF; `--include-context` opts in.

   Default mode: `narrative` + `referenced`. `--story-only` cuts
   to narrative only. `--include-context` adds context rows.

   Render via the mechanical helper after merging:

   ```
   autonovel mechanical timeline-extract books/{book} --format markdown
   ```

   then layer the LLM-merged referenced + context rows in the
   same shape:

     - In-story (mechanical):  `**1492-08-03** **◆ in story** — <plot> *(ch 5)*`
     - Referenced:             `**1492-04-12** *◇ referenced* — <event> [shortname]`
     - Context:                `**1453-05-29** ○ context — <event> [shortname]`

   The leading **bold date** stays consistent across all three
   categories (so date-sorting reads cleanly). The marker shape
   AND font weight together identify the category. Cap total
   entries at ~40 for the focused-edition convention; longer is
   encyclopedia territory.

   **(b) Bios.** One paragraph per named historical figure who
   appears as a character. 100-200 words each. Required structure:

   ```
   **<Name>** (<birth year>–<death year>). <One paragraph: their
   actual historical role, what's documented, what the novel
   invents.> <One sentence on novel-vs-history if the novel
   reshapes them substantively, e.g. "The novel compresses his
   1517-1519 banking decisions into a single dramatised conference
   in chapter 12.">.
   ```

   Skip fictional characters (cross-reference shared/characters.md
   to identify which entries are flagged real-vs-invented; if
   ambiguous, only include figures the research notes corroborate).

   **(b2) Places you can still see.** For each place in the book that
   survives: its name then and its name now, what a visitor can still
   see (the building, the street, the room), and the chapters it
   appears in; then, briefly, the places that do not survive. Draw on
   the research notes' `## Places then and now` and the design's
   `## What the reader comes to learn` places. Only what the research
   corroborates; never invent a surviving building.

   **(c) Sources.** Group into "Primary" and "Secondary" sub-blocks.
   For each: `<author>, *<title>* (<year>). <one-line gloss of
   what the novel drew from it>.` Pull from
   `shared/research/notes/<*>.md`'s `## Sources` blocks; resolve
   shortnames against `shared/sources.bib` for full citations.

   **(d) Notes.** Hand-authored short essay (200-500 words):
   what's documented vs invented, compressed or moved, and why;
   deliberate anachronisms; thanks for source-material guidance. Draw
   the invention list from the design (`books/{book}/design.md`'s
   historical note or invention list, when present). Explain the
   choices; do not apologise for them (the guide's `## Back matter`). The AI in `--from auto` writes a
   stub; the human is expected to refine.

5. Format the output as `books/{book}/appendix.md`:

   ```markdown
   # Appendix

   ## The people in the book

   <groups and entries>

   ## Timeline

   <entries>

   ## Bios

   <entries>

   ## Places you can still see

   <entries>

   ## Sources

   <entries>

   ## Notes on what's invented

   <prose>
   ```

   Only sections actually requested via `--sections` appear. Each
   `## Sub-heading` becomes a `\section*{}` in the LaTeX output
   (per `back_matter.py`'s sub-heading-promotion rule).

6. **User mode** (`--from user`): write each requested section as
   a stub with HOW-TO-EDIT comments and 1-2 example entries.

7. **Both mode** (`--from both`): AI-generate as in 4-5, then
   prepend a `<!-- HUMAN PASS: -->` block listing ambiguities and
   refinements the AI couldn't make confidently (parallel to
   glossary's both-mode shape).

8. Print a one-screen summary: which sections were written, total
   word count, next-step hint:

   ```
   📄 Wrote books/{book}/appendix.md (sections: <list>; N words).

   To refine:
     1. Open books/{book}/appendix.md in your editor.
     2. Verify the Timeline dates against your research notes.
     3. Check the Bios for any novel-invented details that should
        be flagged "the novel imagines that…" rather than stated
        as fact.
     4. The Notes section is the right place to acknowledge
        deliberate anachronisms or compressions; expand it.
     5. Save. typeset will weave it into back matter automatically.

   When ready: /autonovel:typeset --book {book}
   ```
</workflow>

<acceptance>
- `books/{book}/appendix.md` exists and opens with `# Appendix`.
- Each section requested via `--sections` appears as a `## Sub-
  heading` in the file.
- Auto / both mode: at least 5 entries per requested data section
  (cast / timeline / bios / sources); the notes section is at least 150
  words.
- The cast section gives every listed person a first-appearance
  chapter that the chapter bears out, marks the invented ones, and
  spoils nothing past the person's first chapters.
- User mode: scaffold with HOW-TO-EDIT block + 1-2 example
  entries per section.
- Refusal on overwrite without `--force` is the default; the
  command never silently destroys hand-authored content.
- The next `/autonovel:typeset --book {book}` run picks up
  appendix.md via the back-matter builder and renders it as a
  `\chapter*{Appendix}` block after the last chapter, with each
  `## Sub-heading` as `\section*{}`.
</acceptance>
