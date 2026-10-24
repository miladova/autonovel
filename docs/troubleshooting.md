# Troubleshooting

Common errors and what to do about them. If your error isn't listed,
open an issue with the exact error text and the output of
`autonovel doctor`.

---

## `API Error: Extra usage is required for 1M context`

**Full error text seen on Claude Code:**

```
API Error: Extra usage is required for 1M context - run /extra-usage
to enable or /model to switch to standard context
```

**What it means.** Claude Code's currently-selected session model is
a 1M-context variant (e.g. `claude-opus-4-7[1m]`), and Anthropic's
1M-context billing tier is not enabled on your account.

**Recommended fix — enable 1M.** autonovel benefits from 1M context;
`/autonovel:reader-panel`, `/autonovel:review` and
`/autonovel:structure-review` all read entire manuscripts, and
multi-book review can blow through 200k. Inside
Claude Code:

```
/extra-usage
```

This is the path the error message itself points you at, and on a
Claude Max $200/month plan it is the right default.

**Workaround — drop `[1m]`.** If `/extra-usage` doesn't unlock 1M for
your account (verified to happen on Claude Max $200/month during PR-9
author testing — the `/extra-usage` toggle didn't lift the gate), the
mechanical workaround is to run `/model` and pick a model without the
`[1m]` suffix:

- Opus 4.7 (no [1M]) — best quality.
- Sonnet 4.6 (no [1M]) — what every `/autonovel:*` standard-tier
  command targets.
- Haiku 4.5 (no [1M]) — fastest / cheapest, fine for
  `/autonovel:apply-cuts` and other light-tier commands.

Then re-run the command that failed. Foundation, drafting, and
per-chapter eval all fit comfortably in 200k; you only feel the loss
in whole-book review and multi-book series work.

**Resolved (model-pin flip).** The per-command frontmatter `model:`
pin was the culprit: on Claude Max with a `[1m]` session model, the
non-`[1m]` per-command pin silently won and downshifted the session.
Fix: **`autonovel install` no longer pins a `model:` by default** — the
session model wins, so 1M-by-default users aren't downshifted at all.
Per-tier pinning is now an explicit `--pin-model` opt-in. A finer-grained
per-tier toggle via `project.yaml` remains a possible future option (see
`FUTURE-TODOS.md`).

**Why does Max not unlock /extra-usage automatically?** Don't know.
That's between you and Anthropic billing. The two paths above both
work regardless.

---

## `claude: command not found` after `pipx install`

You installed `pipx` but never opened a fresh terminal after
`pipx ensurepath`. Close the current terminal window, open a new
one, and try `autonovel --version` again.

If that doesn't fix it, check whether pipx put the install root on
your PATH:

```bash
pipx ensurepath --force
echo "$PATH" | tr : '\n' | grep -i pipx
```

Expected output includes a line ending in `.local/bin` or similar.

---

## `error: No project.yaml found walking upward from <path>`

You launched `claude` (or a housekeeping subcommand) from a directory
that isn't an autonovel series. `cd` into the directory created by
`autonovel new-series` (the one containing `project.yaml`) and try
again. The README's "Be in the series root" callout under §4
diagnoses this with `pwd` and `ls project.yaml`.

---

## `error: another command is already in flight` from `autonovel _begin`

A previous command exited without releasing
`.autonovel/in-progress.lock`. There are three recovery paths
depending on how stuck you are.

**Recommended (Claude Code):**

```
/autonovel:resume
```

It will detect the stale lock, show you what command was running,
and offer to redo / keep partial / inspect.

**Wait for the watchdog (since 2026-04-28):** locks older than
30 minutes are automatically taken over by the next command's
`_begin`. So if you ran a command, it errored without `_end`,
and you wait half an hour, the next command runs cleanly with
a one-line "took over expired lock from <prior command>" note.
This catches the bug class where an LLM skips the postamble in
the same Claude Code session.

**Manual clear (runtime crashed, no resume available):**

```bash
cat .autonovel/in-progress.lock        # see what was running
rm .autonovel/in-progress.lock         # only after confirming no `claude` is running
```

---

## A `/autonovel:*` command runs but writes nothing

Most often: you launched `claude` from inside a book directory
(`books/<book>/`) instead of the series root. The commands resolve
paths like `shared/world.md` relative to the runtime's cwd, so a
book-directory launch makes those paths look one folder too deep
and the commands silently fall through.

Quit Claude Code, `cd` to the series root (where `project.yaml`
lives), launch `claude` again, retry.

---

## My session model is `[1m]` and per-command pinning silently downshifts me

When you select a `[1m]`-context model in Claude Code (e.g.
`claude-opus-4-7[1m]`), a per-command frontmatter `model:`
`claude-opus-4-7` (no `[1m]`) appears to win — silently
downshifting your session out of 1M context.

**This is now the default behaviour's job to prevent.** As of the
model-pin flip, `autonovel install` **omits the `model:` field by
default**, so the runtime's session model always wins and you never
lose 1M context. You don't need to do anything — a plain
`autonovel install` is already safe.

If you *want* per-command tier intent back (cheap Haiku for light
commands, expensive Opus for heavy ones), opt in explicitly:

```bash
autonovel install --pin-model
```

…but note that on a `[1m]` session this re-introduces the downshift.
(`autonovel install --no-model-pin` is still accepted as a deprecated
no-op, since omitting the pin is now the default.)

The lessons-from-author-testing doc §8 has the longer narrative
on why the interaction is non-obvious. FUTURE-TODOS tracks a more
granular future option where pinning is per-tier via project.yaml.

---

## A `/autonovel:*` command's postamble shows a `🔴 VERIFY-WRITES` banner

The postamble caught a self-report mismatch. The LLM passed
`--wrote <path>` to `autonovel _end` for one or more files, but
the on-disk state doesn't match the claim. As of 2026-04-30 the
warning leads the postamble (rather than trailing it) so it can't
get buried under a long sweep closer.

- `claimed created but file does not exist` — the LLM said it
  created a file but never invoked the `Write` tool. Re-run the
  command; if it fails twice, look at the command body for a
  step that should be writing the file.
- `claimed modified but bytes match the checkpoint` — the LLM
  said it edited a file but the bytes are identical to the
  begin-time backup. **For chapter files specifically, this is
  almost always the silent-revise-failure bug class** — the
  per-chapter task subagent in a `revision-pass` / `draft-pass`
  sweep reported success without invoking Write/Edit. The fix is
  to re-run the sweep targeting just those chapters; the banner
  now lists them by path. For non-chapter paths, the command may
  have legitimately decided no edits were needed (e.g.
  `pending_canon.md` only grows when new facts surface) — review
  before re-running.
- `chapter file(s) were modified WITHOUT regenerating their .summary.md` —
  a chapter was claimed in `--wrote` and its summary doesn't match
  it (stale or missing). Since the summary gate (below) holds any
  command that changed a chapter's prose, this now only fires for a
  summary from before fingerprints that is older than its chapter.
  The banner spells out the `summarize-chapter --force` invocation.

**`🔴 SUMMARY GATE: _end did not close this command`** (exit 3). The
command changed a chapter's text and left its continuity summary
describing the old text. Every summary carries a fingerprint of the
chapter it was written from (`summary_of:` in its frontmatter, written
by `autonovel _stamp-summary`); `_end` compares the chapters the run
changed (against `_begin`'s checkpoint; frontmatter-only edits don't
count) with their summaries and keeps the lock until each matches. The
command's model rewrites each listed summary from the chapter, stamps
it, and runs `_end` again; the postamble tells it to. If you hit it
by hand, do the same, or run `_end --status error` to abandon the run.
Frontmatter (`word_count`, `status`, `title`) never trips it, which is
what used to make every revised chapter look stale.

The banner is informational — the command exited `ok` and the
lock has been released. Decide whether to re-run based on the
command's contract: if the command is *required* to produce a
specific file (e.g. `/autonovel:gen-world` writes
`shared/world.md`), re-run when it shows up missing. The
chapter-file specific call-out is the load-bearing case for
sweep commands — the situational `/autonovel:next` will also
flag those chapters via the brief→revise signal, since the
brief is fresh while the chapter file is unchanged.

The same warnings get logged to
`.autonovel/command-log.jsonl`'s `note` field so an audit trail
outlives the postamble print.

---

## PDF shows the first sentence of each chapter as a page header / alternating heading

Two distinct bugs combined to produce this — both fixed 2026-04-28
but the typeset half is invisible to in-flight series unless you
refresh the templates explicitly.

What you should see in a clean PDF: each chapter opens with
"chapter <Roman>" as the heading, no further chapter text in the
running header. Verso (left) page header is the book title, recto
(right) is "Chapter <Roman>". The first sentence of the chapter
is plain prose with a drop cap on the first letter, NOT a large
italic block at the chapter title page.

If yours doesn't look like that:

```bash
# 1. Pull the latest autonovel and reinstall.
( cd ~/autonovel && git pull && pipx reinstall . ) && autonovel install

# 2. Refresh the typeset template in your series.
cd ~/<your-series-root>
autonovel refresh-templates              # default refreshes typeset/ only
                                          # add `--dry-run` to preview

# 3. Rebuild the PDF.
/autonovel:typeset --book <your-book>
```

The two underlying causes (for the curious / for future
debugging):

1. `mechanical/latex.py::build_chapters_tex` was using the first
   prose line as the chapter title argument when chapters had no
   `# Heading` after the YAML frontmatter (the production shape).
   The fix emits an empty `\chapter{}` so `\titleformat` prints
   "chapter <Roman>" alone.

2. The shared `<series-root>/typeset/novel.tex` template is
   copied at `autonovel new-series` time and never updated by
   `autonovel install`. The 2026-04-25 fix that switched the
   running header from `\textit{\leftmark}` (which renders the
   chapter title arg from #1) to `\fancyhead[RO]{Chapter
   \thechapter}` only takes effect after `autonovel
   refresh-templates`.

If `refresh-templates` reports your `novel.tex` under "local-only
(preserved)" instead of "updated", you've hand-edited the file —
diff your version against the package template at
`<autonovel-repo>/src/autonovel/templates/series/typeset/novel.tex`
and re-apply your customisations on top of the new shape.

---

## `tectonic: command not found` (or `pandoc`, `potrace`, `ffmpeg`)

You're trying to run an export command (`/autonovel:typeset`,
`/autonovel:audiobook-assemble`, etc.) without the matching external
CLI tool installed. `autonovel doctor` reports these as warnings;
install just the one(s) you need:

```bash
# Linux / WSL / Chromebook:
sudo apt install -y tectonic pandoc potrace ffmpeg librsvg2-bin fontconfig

# macOS:
brew install tectonic pandoc potrace ffmpeg librsvg fontconfig
```

You only need these for the matching export commands — drafting and
revision don't.

---

## My typeset PDF / ePub is missing parts (cover overlay, preface, glossary, appendix, page numbers, chapter titles)

A 2026-04-30 user session surfaced a cluster of typeset gaps. As of
that date the fixes are landed; for an existing series, run:

```bash
autonovel refresh-templates --only typeset
```

to pick up the updated `novel.tex`, then re-run typeset. The
specific symptoms each fix addresses:

| Symptom | Fix landed |
|---|---|
| **PDF missing title overlay on front cover image** (you see the bare painting; no book title) | `novel.tex` now prefers `cover_titled.png` over the bare `cover.png`. The auto-prepare-art step in typeset auto-runs `/autonovel:cover-composite` if `cover_titled.png` is missing. |
| **PDF missing preface / introduction / glossary / appendix** | `novel.tex` reads `front_matter.tex` + `back_matter.tex` via `\IfFileExists` guards. They're auto-built by the typeset workflow. **If still missing, check that the source files exist** (`books/<book>/preface.md`, `introduction.md`, `glossary.md`, `appendix.md`). Generate any missing one with `/autonovel:introduction --from both` / `/autonovel:glossary --from auto` / `/autonovel:appendix --from auto`. |
| **PDF page number missing on full-page image pages** | `mechanical/latex.py` now emits `\thispagestyle{plain}` (footer page number visible) for `before-chapter` / `after-chapter` plates instead of `{empty}` (suppressed). |
| **First plate (chapter-start placement) too small** | Default width bumped from 0.6× to 0.8× textwidth — matches the published-book convention while leaving margin. Per-plate overrides via plates.yaml are still respected. |
| **ePub missing glossary / appendix** | typeset.md body's pandoc invocation now includes `<glossary-arg>` and `<appendix-arg>` in the input order: front-matter → preface → introduction → glossary → chapters → appendix → back-cover → colophon. |
| **TOC reads "Chapter I, II, III…" instead of chapter names** | Run `/autonovel:extract-chapter-titles --book <name>` to backfill 2-6 word evocative titles into chapter frontmatter. typeset reads the `title:` field and renders "Chapter VII — The Apothecary's Mortar". `/autonovel:next` surfaces this as a LOW polish signal. **Or — if you actually want numbers-only chapters** (some genres prefer this), set `typeset.chapter_titles: false` in `project.yaml` and re-typeset. The toggle is honoured by both PDF and ePub paths. |
| **ePub missing cover image / chapter ornaments / imported plates** | Three image surfaces are now wired into the ePub: (1) **front cover** via pandoc's `--epub-cover-image=cover_titled.png` flag — confirm that file exists; (2) **per-chapter ornaments** at `art/ornament_chNN.png` (auto-generated by `/autonovel:art-ornaments-all`) appear at chapter opening; (3) **user-imported plates** registered in `typeset/plates.yaml` (via `/autonovel:art-import`) appear at their declared placement (before-chapter / chapter-start / after-chapter) with caption + attribution. The `build_epub_md` helper reads the manifest the same way the PDF path does, so a plate that appears in the PDF also appears in the ePub. Re-run `autonovel refresh-templates --only typeset` then re-run `/autonovel:typeset` to pick up the manifest-reading change. |
| **PDF cover page font too large / translucent overlay swallows the image** | Title size shrunk from 9% → 6% of cover width; top translucent band tightened from 4-38% → 6-20% of cover height. Re-run `/autonovel:cover-composite` to regenerate `cover_titled.png` with the new proportions. |
| **PDF appendix running header reads "Chapter 24" instead of "Appendix"** | `\chapter*{}` doesn't update the running-header mark, so `\rightmark` inherited the last `\chaptermark` value. Fixed via explicit `\markboth{}{<title>}` after each `\chapter*` in front_matter.py / back_matter.py, plus `novel.tex` running header now reads `\rightmark`. Run `autonovel refresh-templates --only typeset` then re-typeset. |
| **Timeline emoji markers (📖, 🏛) render as boxes or get dropped in the PDF / ePub** | EB Garamond and TeX Gyre Pagella don't include emoji glyphs. Original fix used italic parentheticals (`*(in story)*` etc.) but the user reported the three categories looked identical on the page (round 3 of 2026-04-30). Final fix: typeset-safe Unicode geometric shapes from the U+25xx block (in every standard serif font) PAIRED with distinct font weights — `**◆ in story**` (filled diamond, bold), `*◇ referenced*` (open diamond, italic), `○ context` (open circle, plain). Three different shapes plus three different weights makes the category unmistakable even on a quick page-flip. Re-run `/autonovel:appendix --sections timeline --from auto --force` to regenerate. |
| **`**bold**` markers show literally in the PDF / ePub** (timeline dates, Sources entries) | `md_to_latex` only handled `*italic*` — `**bold**` survived as literal text. Fixed: `**X**` now becomes `\textbf{X}` in the LaTeX output and `<strong>X</strong>` (via pandoc) in the ePub. Regenerate the appendix or re-run typeset. |
| **`###` sub-sub-headings show literally in the appendix Sources section** | back_matter.py only promoted `## Heading` → `\section*{}`. Now `### Sub-heading` → `\subsection*{}`. Re-run `/autonovel:appendix` to regenerate (or just re-run typeset; the back-matter builder runs every typeset). |
| **Blank pages after each before-chapter image plate** ("I'd expect images on the left of an open book and the chapter to start on the right page") | Plate render used `\cleardoublepage` on both sides — forced plate to recto, then forced next page to recto, leaving an extra blank verso. Now uses `\cleartoverso` (custom macro forcing to next even/verso page) before the plate, then `\clearpage` after — plate on verso, chapter on facing recto, no blank pages. Run `autonovel refresh-templates --only typeset` to pick up the macro definition. |
| **Words split across pages, headings stranded at page-bottom** | Added widow + orphan + broken-hyphenation penalties to `novel.tex` (all set to 10000 — TeX's "infinitely bad"). Plus `\raggedbottom` to allow a slight bottom-rag rather than rubber-stretching, and `\needspace` for heading-on-last-line protection. Pick up via `autonovel refresh-templates --only typeset`. |
| **ePub shows `**@TITLE@**` and `*@AUTHOR@*` placeholders on page 3** | The ePub `epub_front_matter.md` template wasn't being rendered with per-book values before being passed to pandoc — pandoc just inlined the literal placeholders. Fixed: typeset.md ePub workflow step 5.0 now invokes `autonovel mechanical render-novel-tex` against each ePub template, writing the substituted file to `books/<book>/typeset/`. Update autonovel and re-run typeset. |
| **No way to add a back-cover image** | `novel.tex` now reads `books/<book>/art/back_cover.png` if it exists, rendering it as a full-bleed page after the colophon (parallel to the front-cover block). Drop a PNG at that path and re-typeset. (For the printed wraparound — front + spine + back on one canvas — `/autonovel:cover-print --pages <N>` is still the right tool.) |
| **TOC doesn't show chapter names even after `/autonovel:extract-chapter-titles`** | TWO real root causes were found 2026-04-30 (round 4): (1) **PDF: the `novel.tex` template had no `\tableofcontents` directive at all** — so the PDF had no TOC, just chapter-running-headers. Fixed by adding `\tableofcontents` to the frontmatter zone; pick up via `autonovel refresh-templates --only typeset`. (2) **ePub: `epub.py::_extract_chapter_title` only read `# Heading` lines, never YAML frontmatter `title:`** — chapters drafted with title-in-frontmatter (the canonical shape after extract-chapter-titles) had no prose heading, so the heading defaulted to "Chapter N" and pandoc's ePub TOC read as numbers. Fixed: extractor now reads frontmatter first, falls back to heading. Both fixes ship in autonovel 2026-04-30 round 4; pull the new code + refresh templates + re-typeset. After fixes, run `autonovel mechanical chapter-titles books/<book>` to confirm every chapter reports ✅ frontmatter or 📝 # Heading; both render correctly. ❌ missing chapters produce blank TOC entries — re-run `/autonovel:extract-chapter-titles --book <name>` for those. |
| **"Back cover square" — what's the back cover concept?** | PDF: typeset doesn't include a back cover (printed-book back covers come from `/autonovel:cover-print --pages <N>` which builds the wraparound). ePub: `typeset/epub_back_cover.md` is the back-of-book section that pandoc weaves in (currently a one-line "Back Cover" placeholder; edit the file to write real back-cover prose). |

For an existing book that hit any of these in a typeset run before
2026-04-30, the recovery sequence is:

```bash
# In your series root:
autonovel refresh-templates --only typeset      # pick up new novel.tex + plate sizing

# In Claude Code (only if these are missing):
/autonovel:cover-composite --book <name>        # produces cover_titled.png if not there
/autonovel:extract-chapter-titles --book <name> # backfill chapter titles for the TOC
/autonovel:glossary --book <name> --from auto   # if you want a glossary
/autonovel:appendix --book <name> --from auto   # if you want an appendix
/autonovel:typeset --book <name>                # regenerates with all the fixes
```

---

## tectonic typeset spits out long font-lookup output and fails / produces wrong-looking PDF

Symptom: tectonic prints many lines like `(Font: searching for ...)` /
`Cannot find OpenType font ...` / `*** stepping through fonts by
name` and either fails or produces a PDF with the wrong typeface.

Root cause: the typeset template's `\setmainfont{EB Garamond}` is
asking fontconfig for EB Garamond; it isn't installed (or
fontconfig itself isn't), so fontspec walks its name-fallback
chain trying related variants, prints the noisy lookup, and either
gives up or substitutes a generic serif. As of 2026-04-30 the
template has a graceful fallback chain — `EB Garamond` → system
`Garamond` → `TeX Gyre Pagella` (always present in tectonic's
bundled set) — so a missing font no longer breaks typeset, but
the PDF is rendered in the wrong typeface.

**Diagnose:**

```bash
fc-match "EB Garamond"          # should report an EBGaramond*.otf
                                 # path. If it reports something
                                 # else (DejaVu, Liberation, Times
                                 # New Roman) → font is missing.
fc-list | grep -i garamond      # what fontconfig actually has
```

**Fix:**

```bash
# Linux / WSL / Chromebook:
sudo apt-get install -y fonts-ebgaramond fontconfig
fc-cache -fv

# macOS:
brew install --cask font-eb-garamond
# OR manual: download from https://fonts.google.com/specimen/EB+Garamond
# and double-click each .ttf to install.

# Either way — easiest:
autonovel install-export-tools --exports pdf --apply
```

`autonovel doctor` (as of 2026-04-30) checks this proactively: it
runs `fc-match "EB Garamond"` and warns when the result is a
fallback rather than the requested font. Run `autonovel doctor`
before typeset and you'll see the warning *before* the noisy
build output.

**For existing series scaffolded before 2026-04-30:** the
`novel.tex` template has been updated with a graceful font
fallback chain (`EB Garamond` → system `Garamond` → `TeX Gyre
Pagella`), so a missing font no longer breaks typeset. To pick
up the new template:

```bash
autonovel refresh-templates --only typeset
```

Re-runs the package-shipped templates over your live series's
`typeset/` directory. Preserves any local edits to other files.

---

## Fal.ai / ElevenLabs API errors during export

These are paid third-party services. autonovel doesn't ship API keys
— you provide them in `.env` at the series root:

```bash
FAL_KEY=fal-...
ELEVENLABS_API_KEY=...
```

`autonovel doctor` warns when these are missing.

---

## Smoke tests skip with `claude CLI not on $PATH`

Tier-3 smoke tests need a real runtime. Either install Claude Code
(or Codex CLI / Gemini CLI) and add it to `$PATH`, or accept the
skip — Tier 1+2 (deterministic + contract) are the gates that run
on every commit and don't need a runtime.

```bash
which claude        # should print a path; if blank, install Claude Code
```
