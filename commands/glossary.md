---
name: autonovel:glossary
description: Generate or scaffold a period-vocabulary glossary for the typeset front matter. Critical for historical fiction.
argument-hint: "--book <short-name> [--from auto|user|both] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - shared/world.md
  - shared/canon.md
  - books/{book}/canon.md
  - shared/research/notes/*.md
  - books/{book}/glossary.md
  - books/{book}/chapters/ch_*.md
writes:
  - books/{book}/glossary.md
context_mode: book
---

<purpose>
Period-vocabulary reference that sits in the front matter, right
before chapter 1 (after preface and introduction). For historical
fiction the glossary is often load-bearing: a reader who doesn't
know what a *grosso* is, what a Doge does, or what the Council of
Ten represents can't track the political stakes. The convention
in published historical fiction (Mantel, Eco, Dunnett, Penman) is
a one-page vocabulary list the reader can flip back to.

Three modes selected by `--from`, paralleling
`/autonovel:introduction`:

  - `--from auto` (default for this command — the LLM is good at
    extracting period vocabulary from the prose + research notes):
    AI-generate `glossary.md` by walking every chapter for italic-
    formatted foreign terms, names, and titles; cross-referencing
    `shared/research/notes/`, `shared/canon.md`, `books/{book}/canon.md`,
    and `shared/world.md` for explanations; producing a single
    alphabetised list with one-line definitions in the writer's
    voice (short, declarative, no parenthetical lecturing).
  - `--from user`: scaffold a starter template with a HOW-TO-EDIT
    block + a few example entries; user fills in.
  - `--from both`: AI-generates the list, then leaves a HAND-EDIT
    section at the top with guidance on what to refine.

`--force` permits overwriting an existing glossary (the command
otherwise refuses to clobber author content).
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--from <auto|user|both>` (default `auto`), `--force`.

2. **Refusal-on-overwrite check.** If `books/{book}/glossary.md`
   exists with substantive content (>50 chars beyond template
   stub) and `--force` was not supplied, stop with: "books/{book}/
   glossary.md already exists; pass `--force` to overwrite or
   hand-edit the file directly".

3. **AI generation** (`--from auto` or `--from both`): walk every
   `books/{book}/chapters/ch_*.md` and look for:
     - Italicised foreign-language terms (`*grosso*`, `*Fondaco*`,
       `*podestà*`).
     - Capitalised institutional names that aren't characters
       (`Council of Ten`, `Quarantia`, `Arsenale`, `Magistrato alle
       Acque`).
     - Titles + offices that recur (`Doge`, `Provveditore`,
       `Capitano`).
     - Coins, weights, measures (`ducat`, `grosso`, `soldo`,
       `passo`, `staio`).
     - Period-specific roles (`condottiere`, `apothecary`,
       `bombardier`, `inquisitor`).
     - Place-names whose modern reader won't recognise them
       (`Cipango`, `Levant`, `Constantinople`, the *Stato da Mar*).

   For each candidate, cross-reference:
     - `shared/research/notes/*.md` for the scholarly definition
       with citations (preferred — the glossary entry should match
       what the research established).
     - `shared/canon.md` for the project's canonical fact (e.g.
       "[Council seats] Ten members, two-year terms.").
     - `shared/world.md` for the world-bible entry.
     - The chapter context for which sense is used.

   Cap the glossary at ~30 entries; this is a reader aid, not an
   encyclopedia. Drop entries the prose itself defines inline (a
   chapter that introduces *grosso* in dialogue with "the merchant
   counted out twenty grossi — small silver, each a fortieth of a
   ducat" doesn't need a glossary line).

   Format each entry as:

   ```markdown
   **<term>** — <one-line definition>. <Optional context: era,
   region, or pronunciation when non-obvious>.
   ```

   Sort alphabetically (case-insensitive). Italicise foreign-
   language headwords (`***grosso***`); plain bold for English
   headwords (`**Doge**`). One blank line between entries; no
   sub-headings, no per-letter section dividers (the list is
   short enough that A-Z scrolling is fine).

4. **User scaffold** (`--from user`): write `books/{book}/glossary.md`
   with a HOW-TO-EDIT comment block followed by 3-5 example
   entries the user replaces. Include in the comments: typical
   length (15-30 entries; longer is reference-book territory),
   what to include vs cut (drop terms the prose defines inline),
   the alphabetisation rule, and the formatting convention for
   foreign-language vs English headwords.

5. **Both mode** (`--from both`): AI-generate as in step 3, but
   prepend a `<!-- HUMAN PASS: -->` comment block listing 3-5
   suggested refinements the AI couldn't make confidently:
     - "Anatolia: confirm whether the chapter's usage refers to
       the geographic region or the Ottoman beylerbeylik."
     - "Quarantia: research-notes say 40 members; canon.md says
       40-member criminal court — reconcile."
   These are signals from the AI to the human about ambiguity.

6. Write to `books/{book}/glossary.md` with a `# Glossary` heading.
   Body is plain markdown alphabetised list; keep total file ≤800
   words.

7. Print a one-screen summary: which mode ran, how many entries
   were produced, and the next-step hint:

   ```
   📄 Wrote books/{book}/glossary.md (N entries; alphabetised).

   To refine:
     1. Open books/{book}/glossary.md in your editor.
     2. Cut entries the prose itself defines clearly inline.
     3. Add any term a sensitive reader would stumble on that the
        AI missed (run /autonovel:talk --book {book} "what period
        vocabulary do you use that a modern reader might not
        know?" for help).
     4. Save. typeset will weave it into front matter automatically.

   When ready: /autonovel:typeset --book {book}
   ```
</workflow>

<acceptance>
- `books/{book}/glossary.md` exists and opens with `# Glossary`.
- Auto / both mode: ≥10 alphabetised entries; each in `**term**
  — definition.` shape; total file is between 200 and 800 words.
- User mode: scaffold with HOW-TO-EDIT comment block + 3-5
  example entries.
- Refusal on overwrite without `--force` is the default; the
  command never silently destroys hand-authored content.
- The next `/autonovel:typeset --book {book}` run picks up
  glossary.md via the front-matter builder and renders it as a
  `\chapter*{Glossary}` block right before chapter 1.
</acceptance>
