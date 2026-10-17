---
name: autonovel:diff
description: Show what changed between two versions of a book — word-level edits in context, chapter by chapter, with next/prev jumping — as one HTML page you open in a browser. Zero-LLM unless --annotate.
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
context_mode: book
---

<purpose>
"What actually changed in the book since I last read it?" — answered
without re-reading the book, or even the chapter. `git diff` on
markdown is line-based: a one-word trim lights up a whole paragraph,
and there is no reading surface. This command writes one
self-contained HTML page (no network, opens in any browser, works on
a phone) that shows every change **word by word inside its
paragraph**, with the unchanged paragraphs folded to one line, a
sidebar listing every change per chapter, and `j`/`k` (or `n`/`p`, or
the ◀ ▶ buttons) jumping from change to change with a
"change N of M" counter. A header table gives per-chapter and
whole-book word-count deltas. Chapter summaries and the book's
`voice.md` / `outline.md` / `canon.md` (plus `shared/canon.md`) are
diffed in a "Summaries and foundation" section after the chapters.

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
optional `--annotate` pass: one line of *why* per change, traced to
the brief, the `/autonovel:talk` turn, or the review item that asked
for it — so a discussed edit can be checked against what landed, and
a change nobody asked for stands out.
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
   `books/{book}/edit_logs/diff_<from>_<to>.html` plus the JSON data
   next to it (`diff_<from>_<to>.json`) and prints one JSON object:
   `html`, `json`, `open` (a path to paste into a browser — on WSL the
   `\\wsl.localhost\…` form), `why_path`, `from` / `to` (each with a
   `pinned` value naming that exact version), `hunks`,
   `chapters_changed`, `words_added`, `words_removed`, `net_words`,
   `chapters` (one row per changed chapter) and `bookmark` (when
   `--mark-read` wrote `books/{book}/edit_logs/last_read.json`).
   Exit code 2 means a version did not resolve (unknown tag, no git
   repository, no such checkpoint): show the helper's stderr message
   and stop.

   Without `--annotate`, skip to step 4.

3. **`--annotate` only — one-line why per change.**
   a. Print the compact change list for the *same* two versions (use
      the `pinned` values from step 2 so `last-read` / `last-tag`
      cannot move under you):

      ```
      autonovel mechanical diff-chapters --book {book} --from <from.pinned> --to <to.pinned> [--chapters <SPEC>] --format hunks
      ```

      Each change appears as `- <hunk id> (fp <fingerprint>) ¶N +a −r`
      followed by `~ old → new`, `− deleted` or `+ inserted` lines.
   b. Work chapter by chapter. For chapter N, `file_read`
      `books/{book}/briefs/chNN.md` if it exists (the brief's
      "Specific cuts" / "Specific rewrites" / "Structural findings"
      sections); once per run, `file_read`
      `books/{book}/briefs/conversation.md` (turn headers look like
      `## <date> — turn 47 — suggest`) and the latest
      `books/{book}/edit_logs/review.md` (items look like
      `### Item 4 — …`). Read only what you need; these files are long.
   c. For each hunk, write ONE line (≤ 25 words) naming the source and
      what it asked for: `brief ch14 — rename the alias so it no longer
      collides with ch 18's Kessler`, `talk turn 47 — cut the second
      gloss of the ducat`, `review item 4 — date contradicted ch 9`.
      When nothing in those files asks for the change, say so plainly
      (`not traced to a brief, talk turn or review item`) — never
      invent a reason. Optionally add a one-line summary per changed
      chapter under the chapter key (`ch14`).
   d. `file_write` the annotations to the `why_path` from step 2
      (`books/{book}/edit_logs/diff_<from>_<to>.why.json`) as one JSON
      object: `{"ch14-002": {"why": "…", "fp": "cb4fcf26ae"}, "ch14": "…"}`
      (hunk ids and fingerprints copied from the list; the fingerprint
      lets the helper drop an annotation if the text has changed since).
   e. Re-run the helper so the page carries the annotations, writing
      over the same file:

      ```
      autonovel mechanical diff-chapters --book {book} --from <from.pinned> --to <to.pinned> [--chapters <SPEC>] --out <html from step 2> --why <why_path> [--mark-read]
      ```

      (`--mark-read` here when it was requested.) Its output reports
      `why_applied` and `why_stale`.

4. **Report.** Print the HTML path as the deliverable — the `open`
   value first (paste it into a browser's address bar), then the `html`
   path — followed by this 5-line summary table built from the
   helper's JSON:

   ```
   | | |
   |---|---|
   | From → To | <from.description> → <to.description> |
   | Changes | <hunks> (<chapter_hunks> in prose, <foundation_hunks> in summaries/foundation) |
   | Chapters changed | <chapters_changed> of <chapters_compared>: <list of chapter numbers, "added"/"removed" marked> |
   | Words | +<words_added> −<words_removed> (net <net_words>) |
   | Bookmark | moved to <bookmark.sha short or ref> / unchanged |
   ```

   Then one line: "In the page: `j`/`k` jump between changes, `e`
   shows all context." If `from.note` is set (e.g. "no last-read
   bookmark yet; last tag is draft_1"), print it. If there are no
   changes, say so in one line and skip the table.

5. Do not edit chapters or any other book file. This command only
   writes the diff page, its JSON and why sidecars, and (with
   `--mark-read`) the bookmark.
</workflow>

<acceptance>
- Without `--annotate`, no LLM reasoning is needed: the output is the
  helper's paths plus the summary table.
- The HTML file exists at the printed path and is self-contained
  (inline CSS and JS, no external requests).
- A one-word edit shows as one inline change inside its paragraph,
  not as the whole paragraph deleted and re-inserted.
- `--mark-read` leaves `books/{book}/edit_logs/last_read.json`
  pointing at the `--to` version; the next `--from last-read` diff
  starts there.
- With `--annotate`, every hunk id in the change list has an entry in
  the why sidecar, each naming its source or stating that none was
  found, and the re-rendered page shows them under each change.
</acceptance>
