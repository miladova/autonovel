---
name: autonovel:import-book
description: Import an externally-written manuscript into a book's chapters/. Splits a directory or single-file source into autonovel-shape ch_NN.md files.
argument-hint: "--book <short-name> --from <path> [--split-on <regex>] [--start <N>] [--pov <name>] [--keep-mode] [--overwrite] [--reverse-engineer] [--dry-run]"
model_tier: light
allowed-tools:
  - bash
  - file_read
reads:
  - project.yaml
writes:
  - books/{book}/chapters/ch_*.md
  - project.yaml
context_mode: book
---

<purpose>
Open up the use case where the user has an external manuscript
(their own, an estate's, a public-domain text being modernised)
and wants to use autonovel's evaluate / revise / panel / review /
typeset surfaces against it without re-drafting from scratch.

What this command does:
- Splits the source into chapters (a directory of `*.md` files
  becomes one chapter per file, sorted by filename; a single-file
  manuscript splits on `^# ` headings, falling back to `^## `,
  falling back to "treat the whole file as one chapter").
- Strips any pre-existing YAML frontmatter from the source.
- Writes each chapter as `books/{book}/chapters/ch_NN.md` with
  autonovel-shape frontmatter — `pov`, `story_time` are
  `inferred` placeholders by default, `status: imported`.
- Marks the book as `mode: edit-imported` in `project.yaml` so
  `/autonovel:draft` refuses to overwrite the import without
  `--force`. The rest of the pipeline works identically: you
  can evaluate / brief / revise / panel / review / typeset
  imported chapters as if you had drafted them.

What this command does NOT do (yet):
- Reverse-engineer a foundation (voice / characters / outline)
  from the imported prose. After import, run the standard
  foundation commands (`/autonovel:gen-characters`,
  `/autonovel:voice-discovery`, `/autonovel:gen-canon`,
  `/autonovel:gen-outline`) against the imported prose; OR
  supply your own foundation files under `shared/` and
  `books/{book}/voice.md` and pass `--keep-mode` to skip the
  mode flip.
- Convert non-markdown formats (`.docx`, `.epub`, `.txt`).
  Pre-convert with pandoc (already a documented optional
  dependency) before pointing this command at the result.
- Backfill `pov` / `story_time` / cast on the imported
  frontmatter. Run `/autonovel:summarize-chapter --all` after
  import for the LLM-side fill pass.

Pure mechanical. No LLM call. Light tier — runs in milliseconds.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` is required (the
   book must already exist in `project.yaml`; run
   `autonovel new-book <name>` first if not). `--from <path>`
   is required.

2. Optional flags:
   - `--split-on <regex>` — multiline regex with a named `title`
     group, e.g. `^Chapter (?P<title>.+)$`. Overrides the
     default heading split.
   - `--start <N>` — chapter number to start writing at.
     Default: append after the highest existing `ch_NN.md`.
   - `--pov <name>` — write this POV into every imported
     chapter's frontmatter (default: `inferred`).
   - `--keep-mode` — leave `project.yaml :: books[].mode`
     untouched. Default: flip to `edit-imported`.
   - `--overwrite` — replace existing `ch_NN.md` files at the
     target paths. Default: skip with a warning.
   - `--reverse-engineer` — after the import, scan the imported
     prose for high-frequency capitalised tokens (candidate
     character names) and either write a stub
     `shared/characters.md` (when missing) or append a
     "Candidate cast (auto-detected)" block (when present). Pure
     mechanical — voice and outline reverse-engineering belong in
     the LLM follow-ups (`voice-discovery` / `summarize-chapter`
     / `gen-outline`), printed as a numbered next-step list.
   - `--dry-run` — print what would be written; touch nothing.

3. Use the `Bash` tool to call the housekeeping CLI (this is
   the safe path — the helper handles error paths and
   project.yaml mutation atomically):

   ```
   autonovel import-book {book} --from {path} \
     [--split-on '<regex>'] [--start N] [--pov <name>] \
     [--keep-mode] [--overwrite] [--reverse-engineer] [--dry-run]
   ```

   The CLI validates the book exists, runs the splitter, writes
   the per-chapter files, and updates `project.yaml :: books[].mode`
   unless `--keep-mode` was passed.

4. Print the helper's stdout verbatim — it lists the written
   paths and any skipped-because-already-exist warnings.

5. After a non-dry-run import, suggest the next step based on
   what's missing:
   - When the book has no `voice.md` (Part 1+2 unpopulated):
     suggest `/autonovel:voice-discovery --book {book}`.
   - When `shared/characters.md` is missing or stub: suggest
     `/autonovel:gen-characters`.
   - When `shared/canon.md` is empty: suggest
     `/autonovel:gen-canon` to seed canon FROM the imported
     prose (series-wide facts → `shared/canon.md`; the manuscript's
     own plot facts → `books/{book}/canon.md`).
   - Then a chapter-summary backfill pass:
     `/autonovel:summarize-chapter --all --book {book}` to fill
     the per-chapter summaries that revise / brief / panel
     read.
   - Then the rest of the pipeline: evaluate, brief, revise,
     review, typeset — all unchanged from the standard flow.
</workflow>

<acceptance>
- The book named in `--book` exists in `project.yaml` before
  this command starts (else the helper exits non-zero with a
  one-line message naming `autonovel new-book`).
- For each detected chapter, exactly one
  `books/{book}/chapters/ch_{NN:02d}.md` is written, with
  autonovel-shape YAML frontmatter (`book`, `chapter`,
  `status: imported`, `word_count`, `imported_from: <source>`,
  plus `pov` / `story_time` / `events`).
- `project.yaml :: books[<book>].mode` is `edit-imported`
  after the run unless `--keep-mode` was passed.
- Existing chapter files are preserved unless `--overwrite`
  is set; the helper lists skipped paths.
- `--dry-run` writes no files and modifies no `project.yaml`.
</acceptance>
