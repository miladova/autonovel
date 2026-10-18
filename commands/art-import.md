---
name: autonovel:art-import
description: Import a user-supplied image (map, painting, photo) as a typeset plate or chapter ornament.
argument-hint: "--file <path> --chapter <N> [--book <name>] [--as plate|ornament] [--placement before-chapter|chapter-start|after-chapter] [--slug <key>] [--caption \"<line>\"] [--attribution \"<credit>\"] [--force]"
model_tier: light
allowed-tools:
  - bash
  - file_read
reads:
  - books/{book}/typeset/plates.yaml
writes:
  - books/{book}/typeset/plates.yaml
  - books/{book}/typeset/plates/<slug>.<ext>
  - books/{book}/art/ornaments/ch_{chapter}.<ext>
context_mode: book
---

<purpose>
Bring a user-supplied image into the typeset output. Two modes:

  - **plate** (default) — full-page or near-full-page illustration
    with caption and attribution, placed before, at the start of,
    or after a chapter. Right for maps, paintings, portraits,
    photographs of period objects. The typeset path renders these
    on dedicated pages for `before-chapter` / `after-chapter` and
    inline (centered, half-width) for `chapter-start`.

  - **ornament** — replaces the AI-generated chapter ornament with
    your own image at the chapter heading. Right for woodcuts and
    period engravings matching the existing chapter-ornament
    aesthetic. Smaller than a plate.

The command is light-tier — no LLM, just file copy + manifest
write. It calls `autonovel art-import` (the housekeeping CLI),
which is on `$PATH` after pipx install.

Use cases this was built for (historical fiction, 2026-04-25):

  /autonovel:art-import --file ~/Downloads/de_barbari_venice_1500.png \
    --chapter 1 --placement before-chapter \
    --caption "Jacopo de' Barbari, View of Venice, 1500." \
    --attribution "Public domain, via Wikimedia Commons."

  /autonovel:art-import --file ~/Downloads/durer_jakob_fugger.jpg \
    --chapter 5 --placement before-chapter \
    --caption "Albrecht Dürer, Portrait of Jakob Fugger the Rich, c. 1518." \
    --attribution "Bayerische Staatsgemäldesammlungen, public domain."

  /autonovel:art-import --file ~/Downloads/hanseatic-routes.svg \
    --chapter 9 --placement before-chapter \
    --caption "Principal Venetian–Hanseatic trade routes, late 15th century."

Manifest (`books/{book}/typeset/plates.yaml`) is human-readable and
hand-editable — re-running art-import with the same `--slug`
overwrites the prior entry; deleting an entry by hand also works.
A full-page plate (`before-chapter` / `after-chapter`) may carry
`layout: landscape`: the PDF turns that page sideways so a wide
picture — a city view, a map — fills the page's long side instead of
shrinking to a strip, and the ePub shows it at full width. Add the
line by hand under the plate's entry.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--file <path>` (the source image
   on disk), `--chapter <N>` (1-indexed). `--book` defaults via
   `_begin`. `--as` is `plate` (default) or `ornament`.
   `--placement` is one of `before-chapter` (default for plate),
   `chapter-start`, `after-chapter`. `--slug` overrides the
   auto-derived slug (default: filename stem). `--caption` and
   `--attribution` are italic and small-print under the plate
   respectively. `--force` permits overwriting an existing entry
   with the same slug or chapter ornament. Missing `--file` or
   `--chapter` → stop with usage hint.

2. Use the `Bash` tool to invoke (single-shot):

   ```
   autonovel art-import --file <path> --chapter <N> \
     [--book <name>] [--as <kind>] [--placement <p>] \
     [--slug <s>] [--caption "<c>"] [--attribution "<a>"] [--force]
   ```

   Pass through every flag the user supplied. The CLI:
     - validates the source file exists and has an accepted
       extension (PNG, JPG, JPEG, PDF, SVG, TIFF, TIF),
     - copies it to `books/{book}/typeset/plates/<slug>.<ext>`
       (plate mode) or `books/{book}/art/ornaments/ch_NN.<ext>`
       (ornament mode),
     - for plate mode, appends/updates the `plates.yaml` manifest
       at `books/{book}/typeset/plates.yaml`,
     - prints a summary of what was installed.

3. Reproduce the CLI's stdout verbatim in your reply so the user
   sees the installed path, the slug, the placement, and the
   "rebuild the PDF" hint. The CLI handles all error surfacing —
   unsupported extension, missing file, slug conflict — with a
   `error: <message>` line; pass those through unchanged.

4. The user's next step (already printed by the CLI) is to
   `/autonovel:typeset --book {book}` to actually weave the new
   plate into the PDF. The typeset path's
   `autonovel mechanical build-tex` reads the plates manifest
   and inserts each plate at its declared placement. Until typeset
   is run, the manifest carries the plate but the PDF doesn't.
</workflow>

<acceptance>
- After a successful plate import:
  - `books/{book}/typeset/plates/<slug>.<ext>` exists and is a
    byte-identical copy of the source file.
  - `books/{book}/typeset/plates.yaml` contains an entry with the
    correct `slug`, `chapter`, `placement`, `caption`, and
    `attribution`.
- After a successful ornament import:
  - `books/{book}/art/ornaments/ch_{chapter}.<ext>` exists and is
    a byte-identical copy of the source file.
- `books/{book}/chapters/ch_*.md` is unchanged. Importing art is a
  typeset-side operation; chapter prose stays prose.
- The `Next:` footer line names `/autonovel:typeset --book {book}`
  as the command that rebuilds the PDF with the new art.
</acceptance>
