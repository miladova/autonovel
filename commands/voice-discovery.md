---
name: autonovel:voice-discovery
description: Fill the book-specific fingerprint in Part 2 of the book's voice.md.
argument-hint: "--book <short-name> [--force | --upgrade]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - books/{book}/seed.txt
  - books/{book}/outline.md
  - books/{book}/design.md
  - books/{book}/voice.md
writes:
  - books/{book}/voice.md
context_mode: book
---

<purpose>
Populate Part 2 of `books/{book}/voice.md` — the book-specific fingerprint.
Part 1 is series-wide and usually handwritten; leave it alone. Part 2 is
the per-book register that every chapter's prose will match: sentence
rhythm, sensory palette, POV distance, what the narrator notices and what
they refuse to name.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. If missing, stop and
   surface a one-line usage reminder.

   Two re-run flags (mutually exclusive):
   - `--force` regenerates Parts 1, 2, and 4 from scratch, overwriting
     whatever was there. Use only when the prior voice.md is junk and
     you want a clean re-derive.
   - `--upgrade` is the safe upgrade path for an existing book whose
     voice.md predates Parts 3 and 4. It **preserves Parts 1 and 2
     verbatim**, appends the Part 3 placeholder if it's missing, and
     drafts Part 4 from `shared/characters.md` (when the cast is ≥3).
     This is what to run after `autonovel install` brings in a new
     autonovel version that adds voice.md sections — no
     hand-editing required.

2. Use `file_read` on `project.yaml`. Resolve the book entry and its POV.
   Capture `genre` and `period` — the voice has to sit inside the period's
   register.

3. Use `file_read` on `shared/world.md` and `shared/characters.md`. The
   POV's class, era, and profession all constrain vocabulary.

4. Use `file_read` on `books/{book}/seed.txt` and
   `books/{book}/outline.md`. A seed about grief reads differently from a
   seed about appetite; the outline's pacing shapes cadence.

4a. Use `file_read` on `books/{book}/design.md` if it exists
    (`/autonovel:design` writes it). Its `## Voice` section is the brief:
    the register, rhythm, viewpoint plan, density of description,
    interiority and bans were decided there from the author's stated
    preferences, and Part 2 elaborates them — never contradicts them. Its
    `## Cast` entries (want, contradiction, signature) are the source for
    Part 4's fingerprints, and its `## Places` signatures feed the palette.

5. Use `file_read` on `books/{book}/voice.md`. Keep Part 1 (series voice)
   verbatim.

   Part 2 handling depends on the flags:
   - `--upgrade`: **always preserve Part 2 verbatim**, even when it's
     populated. Skip steps 6 (Part 2 drafting) entirely; jump to
     step 6a (Part 4) and step 7 (write).
   - `--force`: regenerate Part 2.
   - Neither flag: if Part 2 has substantive content (more than the
     template placeholder), stop with a one-line message: "Part 2 is
     populated; re-run with `--upgrade` to add Parts 3 and 4 without
     touching it, or `--force` to regenerate everything."

6. Draft Part 2. Keep it concrete and usable by a drafting model. The
   mechanics of prose (how sentences and paragraphs join, how scenes
   are built, how dialogue is shaped) are `shared/craft/PROSE.md`'s and
   are not restated here; Part 2 records the REGISTER. Include:
   - who the reader is, in one sentence, and the two or three published
     writers whose register is the model (the drafter imitates a named
     model far better than it follows a rule),
   - the reading-grade band, on one line in exactly this form so the
     mechanical scanners have a baseline: `FK grade band: 5–8` (modern
     commercial fiction sits around 5–8, literary and period registers
     higher; see `shared/craft/CRAFT.md` §6 "Registers, operationally"),
   - whether narration contracts (a spoken modern register does:
     *didn't*, *couldn't*; a formal or period register may not), and
     the grammar the narrator refuses (for a plain register: *whether*
     for *if*, *perhaps*, fronted objects, participial ellipsis, a
     character explaining to a listener what the listener can see),
   - POV distance (close, middle, telescope), tense,
   - 6–12 word "palette" — sensory motifs the narrator returns to,
   - at least three further "do not" rules specific to this POV
     (anachronisms to avoid, emotional registers the narrator refuses,
     punctuation habits to resist),
   - a sample paragraph in-voice as a reference, 150 to 300 words, with
     at least one exchange of dialogue in it, that passes
     `autonovel mechanical register` against the declared band.

6a. **Draft Part 4 — Per-character voice fingerprints** (when the
    cast warrants it). Read `shared/characters.md` and identify the
    book's main cast: named characters who appear as principals
    (POV characters from `project.yaml :: books[*].pov`, plus any
    other named characters with substantive paragraphs in
    characters.md — antagonists, primary supporting cast).
    Threshold: **draft Part 4 when the main cast count is ≥3.**
    Below that, single-character or two-character books are well
    served by Part 2 alone — skip Part 4 and leave the template
    placeholder comment in place.

    For each main-cast character, emit one block under `## Part 4
    — Per-character voice fingerprints`:

      ### {Name} ({POV} | speaking-only)
      - Speech: {sentence shape, register shifts under stress}
      - Verbal tics: {distinctive words / phrases / never-says}
      - Refuses: {topics, emotional registers, metaphor families
        they avoid}
      - Body during dialogue: {what their hands / face / posture do}
      - Interiority: {only for POV characters — how they think
        about emotion; direct vs indirect, what they refuse to name}

    Keep each block to those five items; the drafter has to apply
    many at once and verbose blocks dilute. The "all characters
    sound the same" AI tell is the one Part 4 exists to fight, so
    each character must be distinguishable on speech alone.
    Speaking-only characters (non-POV) skip the Interiority line.

    Cap the cast at 6 characters in Part 4. Walk-on characters
    (one-scene cameos, named villagers) get no fingerprint;
    they're voiced from Part 2.

7. Use `file_write` to replace `books/{book}/voice.md` with Part 1
   (preserved verbatim) + the new Part 2 under its existing heading
   + Part 3 (preserved verbatim if present — see step 7a) + Part 4
   (newly drafted from step 6a, OR preserved verbatim if the user
   has hand-edited it — see step 7b).

7a. **Preserve Part 3 (Custom rubric) verbatim.** If the existing
    voice.md contains a `## Part 3 — Custom rubric` section, keep
    its body byte-for-byte. Part 3 holds book-specific scoring
    criteria the user authored (or left as the placeholder); this
    command must never overwrite or "regenerate" it. The standard
    template's commented-out placeholder is preserved unchanged
    when no real content has been added. If voice.md has no Part
    3 section at all (older books from before the custom-rubric
    contract), append the template's Part 3 placeholder at the
    end so the surface exists for the user to fill in later.

7b. **Preserve Part 4 if hand-edited.** If the existing voice.md
    contains a `## Part 4 — Per-character voice fingerprints`
    section AND its body has any character block (a `### Name`
    heading), preserve it byte-for-byte — the user has tuned per-
    character voices and the auto-generation must not overwrite
    that work. `--force` overrides this preservation. If Part 4
    exists but contains only the template placeholder comment
    (no `###` headings), step 6a's freshly-drafted Part 4
    replaces it.
</workflow>

<acceptance>
- `books/{book}/voice.md` still contains a `## Part 1` section matching
  what was there before this run.
- `## Part 2 — Book-specific fingerprint` (or `## Part 2 — Book
  fingerprint`) now contains concrete guidance: sentence-length guidance,
  POV distance, at least one palette line, and at least one `do not` rule.
- Part 2 is not empty and not only the template placeholder comment.
- A `## Part 3 — Custom rubric` section exists in the file (either
  preserved verbatim from a prior version or appended from the
  template placeholder). Its body is unchanged from the input.
- A `## Part 4 — Per-character voice fingerprints` section exists.
  Its body is either (a) a freshly-drafted set of `### Name` blocks
  (when shared/characters.md had ≥3 named principals and Part 4
  was not previously hand-edited), (b) preserved verbatim from the
  prior voice.md if hand-edited, or (c) the template placeholder
  comment (when the cast count is below 3 — Part 4 isn't useful
  for solo-cast books).
</acceptance>
