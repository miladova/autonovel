---
name: autonovel:diff
description: Show what changed between two versions of a book — word-level edits in context, chapter by chapter, with next/prev stepping, Changes / Whole chapter / Clean text views and a big-changes filter — as one HTML page you open in a browser. Zero-LLM unless --annotate (a plain what-changed note, a why and a big flag per change).
argument-hint: "[--book <short-name>] [--from <tag|commit|last-read|last-tag|checkpoint:<timestamp>|checkpoint:latest>] [--to <tag|commit|worktree>] [--chapters N-M|N,M] [--mark-read] [--annotate]"
model_tier: light
allowed-tools:
  - bash
  - file_read
  - file_write
reads:
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/canon.md
  - shared/canon.md
  - books/{book}/edit_logs/last_read.json
  - .autonovel/checkpoints/*
  - books/{book}/briefs/ch*.md
  - books/{book}/briefs/conversation.md
  - books/{book}/edit_logs/review.md
writes:
  - books/{book}/edit_logs/diff_*.html
  - books/{book}/edit_logs/diff_*.json
  - books/{book}/edit_logs/diff_*.why.json
  - books/{book}/edit_logs/last_read.json
  - books/{book}/edit_logs/story_map.html
  - books/{book}/edit_logs/story_map.json
context_mode: book
---

<purpose>
"What actually changed in the book since I last read it?" — answered
without re-reading the book, or even the chapter. `git diff` on
markdown is line-based: a one-word trim lights up a whole paragraph,
and there is no reading surface. This command writes one
self-contained HTML page (no network, opens in any browser, works on
a phone, light and dark, fit to publish as a claude.ai artifact) that
shows every change **word by word inside its paragraph**, with a
sidebar listing every change per chapter, and `j`/`k` (or `n`/`p`, or
the ◀ ▶ buttons) stepping from change to change with a
"change N of M" counter and a brief highlight on the change it lands
on. A header table gives per-chapter and whole-book word-count deltas.
Chapter summaries and the book's `voice.md` / `outline.md` /
`canon.md` (plus `shared/canon.md`) are diffed in a "Summaries and
foundation" section after the chapters.

One page, three views of the same text (the choice is remembered):
**Changes** (the default: unchanged paragraphs folded to one line),
**Whole chapter** (every paragraph, the changes marked) and **Clean
text** (the new version to read straight through: no strike-throughs,
no highlights, no notes, cut paragraphs gone). A **Big changes only**
filter in the Changes view hides wording trims. A paragraph rewritten
past inline marking shows as its new text with a closed "show the
earlier draft" fold, not as interleaved fragments; a paragraph pushed
down past newly written ones still shows as an edit of itself;
markdown *italics* and **bold** render as such.

The same run rebuilds the book's **story map**
(`books/{book}/edit_logs/story_map.html` with its data file
`books/{book}/edit_logs/story_map.json`, as `/autonovel:story-map`
writes them: synopsis in reading order, plot threads, characters,
timeline and places) beside the diff page and links the two: a
**Story map** button in the diff toolbar, "this chapter in the story
map" on every chapter heading, and "N changes" on every changed
chapter of the story map's synopsis. So the author reads where the
story goes and what changed in one place. `--no-story-map` skips it.

Versions it can compare:

- **Git refs** — a tag (`draft_1`), a commit, `HEAD~5`.
- **`last-tag`** (default `--from`) — the most recent tag; when
  `--to` is itself tagged, the tag before it.
- **`last-read`** — the bookmark `--mark-read` records in
  `books/{book}/edit_logs/last_read.json`: "everything since I last
  looked". No bookmark yet → last tag → the first commit that touched
  the chapters.
- **Checkpoints** — `checkpoint:latest` or `checkpoint:<timestamp>`
  (a unique prefix is enough): the book as it stood just before that
  command ran, rebuilt from `.autonovel/checkpoints/` snapshots. Works
  without git.
- **`worktree`** (default `--to`) — the files on disk now, including
  uncommitted edits.

The diff is pure mechanical (`autonovel mechanical diff-chapters`,
difflib at paragraph then word level). The only LLM work is the
optional `--annotate` pass, which gives each change three things: a
plain **what** note at its head ("Sibylla introduced: thirty-nine,
twenty years younger than Jakob, married twenty-one years"), so the
author can skim the notes and open only the changes they care about;
a quieter **why** under it, traced to the brief, the `/autonovel:talk`
turn, or the review item that asked for it — so a discussed edit can
be checked against what landed, and a change nobody asked for stands
out; and a **big** flag that drives the big-changes filter and the list
of big changes, as links, at the head of each chapter. Without
annotations the filter falls back to size (40+ words added and
removed, or a paragraph moved).

`/autonovel:revise` and `/autonovel:draft` run the same helper when
they rewrite a chapter the author has already read, so revised chapters
go back to the author as this page.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via `_begin`.
   `--from` defaults to `last-tag`, `--to` to `worktree`.
   `--chapters` takes `5`, `3-7` or `2,5,9-11`; with `--chapters` the
   foundation files are skipped (chapter summaries are kept).
   `--mark-read` and `--annotate` are flags.

2. **Mechanical diff.** Use `bash` to run, from the series root:

   ```
   autonovel mechanical diff-chapters --book {book} --from <FROM> --to <TO> [--chapters <SPEC>]
   ```

   Add `--mark-read` here only when `--mark-read` was passed and
   `--annotate` was not. The helper writes
   `books/{book}/edit_logs/diff_<from>_<to>.html` (with `--chapters`,
   `diff_<from>_<to>_ch05-07.html`, so a page for some chapters never
   overwrites another) plus the JSON data next to it (the same name
   ending `.json`) and prints one JSON object:
   `html`, `json`, `open` (a path to paste into a browser — on WSL the
   `\\wsl.localhost\…` form), `why_path`, `from` / `to` (each with a
   `pinned` value naming that exact version), `hunks`, `big_hunks`,
   `chapters_changed`, `words_added`, `words_removed`, `net_words`,
   `chapters` (one row per changed chapter), `bookmark` (when
   `--mark-read` wrote `books/{book}/edit_logs/last_read.json`) and
   `story_map` (`html`, `open`, `warnings`, or `error` when the map
   could not be built — the diff page is still written, without the
   link).
   Exit code 2 means a version did not resolve (unknown tag, no git
   repository, no such checkpoint): show the helper's stderr message
   and stop.

   Without `--annotate`, skip to step 4.

3. **`--annotate` only — a what note, a why and a big flag per change.**
   a. Print the compact change list for the *same* two versions (use
      the `pinned` values from step 2 so `last-read` / `last-tag`
      cannot move under you):

      ```
      autonovel mechanical diff-chapters --book {book} --from <from.pinned> --to <to.pinned> [--chapters <SPEC>] --format hunks
      ```

      Each change appears as `- <hunk id> (fp <fingerprint>) ¶N +a −r`
      (`(rewritten)` when a paragraph was rewritten whole) followed by
      `~ old → new`, `− deleted` or `+ inserted` lines.
   b. Work chapter by chapter. For chapter N, `file_read`
      `books/{book}/briefs/chNN.md` if it exists (the brief's
      "Specific cuts" / "Specific rewrites" / "Structural findings"
      sections); once per run, `file_read`
      `books/{book}/briefs/conversation.md` (turn headers look like
      `## <date> — turn 47 — suggest`) and the latest
      `books/{book}/edit_logs/review.md` (items look like
      `### Item 4 — …`). Read only what you need; these files are long.
   c. For each hunk, write three things:
      - **`what`** — ONE line saying what the change is, for an author
        who is not a writer or a historian. Name what happens, who
        arrives, what fact changed: `Sibylla introduced: thirty-nine,
        twenty years younger than Jakob, married twenty-one years`,
        `New scene: the first morning out of the Germans' house — Tucher
        shows Jakob the Rialto bankers`, `Barbara's father is alive (the
        research corrected this; before, he was dead)`, `Wording
        tightened`. Introduce each person and term the first time
        (`Höchstetter, Jakob's neighbour and rival`), no jargon
        (`POV`, `beat`, `register`, `exposition` never appear), and
        quote a new line of dialogue rather than describing it.
      - **`why`** — ONE line (≤ 25 words) naming the source and what it
        asked for: `brief ch14 — rename the alias so it no longer
        collides with ch 18's Kessler`, `talk turn 47 — cut the second
        gloss of the ducat`, `review item 4 — date contradicted ch 9`.
        When nothing in those files asks for the change, say so plainly
        (`not traced to a brief, talk turn or review item`) — never
        invent a reason.
      - **`big`** — `true` for a change the author would want to read:
        a new or cut scene, a new or changed line for a character, a
        changed fact, date or plot turn; `false` for wording trims and
        tidying, however many words they touch.
      Optionally add a one-line summary per changed chapter under the
      chapter key (`ch14`).
   d. `file_write` the annotations to the `why_path` from step 2
      (`books/{book}/edit_logs/diff_<from>_<to>.why.json`) as one JSON
      object: `{"ch14-002": {"what": "…", "why": "…", "big": true, "fp":
      "cb4fcf26ae"}, "ch14": "…"}` (hunk ids and fingerprints copied from
      the list; the fingerprint lets the helper drop an annotation if
      the text has changed since). An older sidecar holding only `why`
      strings still loads.
   e. Re-run the helper so the page carries the annotations, writing
      over the same file:

      ```
      autonovel mechanical diff-chapters --book {book} --from <from.pinned> --to <to.pinned> [--chapters <SPEC>] --out <html from step 2> --why <why_path> [--mark-read]
      ```

      (`--mark-read` here when it was requested.) Its output reports
      `why_applied`, `why_stale` and `big_hunks`. The page now shows the
      what note at the head of each change with the why under it, the
      notes in the sidebar, and each chapter's big changes listed as
      links under its heading.

4. **Report.** Print the HTML path as the deliverable — the `open`
   value first (paste it into a browser's address bar), then the `html`
   path — followed by this 5-line summary table built from the
   helper's JSON:

   ```
   | | |
   |---|---|
   | From → To | <from.description> → <to.description> |
   | Changes | <hunks> (<chapter_hunks> in prose, <foundation_hunks> in summaries/foundation); <big_hunks> big |
   | Chapters changed | <chapters_changed> of <chapters_compared>: <list of chapter numbers, "added"/"removed" marked> |
   | Words | +<words_added> −<words_removed> (net <net_words>) |
   | Bookmark | moved to <bookmark.sha short or ref> / unchanged |
   | Story map | <story_map.open>, linked from the diff page (or the error) |
   ```

   If `story_map.warnings` mentions missing summaries, add one line:
   the synopsis has gaps until `/autonovel:summarize-chapter --stale
   --book {book}` runs.

   Then one line: "In the page: `j`/`k` step between changes; Changes /
   Whole chapter / Clean text switch the view (`e` toggles Whole
   chapter); Big changes only hides wording trims." If `from.note` is
   set (e.g. "no last-read bookmark yet; last tag is draft_1"), print
   it. If there are no changes, say so in one line and skip the table.

5. Do not edit chapters or any other book file. This command only
   writes the diff page, its JSON and why sidecars, the story map
   beside it, and (with `--mark-read`) the bookmark.
</workflow>

<acceptance>
- Without `--annotate`, no LLM reasoning is needed: the output is the
  helper's paths plus the summary table.
- The HTML file exists at the printed path and is self-contained
  (inline CSS and JS, no external requests).
- A one-word edit shows as one inline change inside its paragraph,
  not as the whole paragraph deleted and re-inserted.
- The page offers Changes, Whole chapter and Clean text views and a
  Big changes only filter; "Next" steps through the changes the view
  shows, one at a time, with the counter following.
- `--mark-read` leaves `books/{book}/edit_logs/last_read.json`
  pointing at the `--to` version; the next `--from last-read` diff
  starts there.
- With `--annotate`, every hunk id in the change list has an entry in
  the why sidecar with a plain `what` note (people and terms
  introduced, no jargon), a `why` naming its source or stating that
  none was found, and a `big` flag; the re-rendered page shows the note
  at the head of each change, the why under it, and each chapter's big
  changes listed under its heading.
</acceptance>
