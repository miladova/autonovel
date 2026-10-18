---
name: autonovel:story-map
description: One HTML page that shows the book's shape — synopsis in reading order, plot-thread grid with the score/tension curve under it, characters, timeline and places — built from the summaries and outline you already have.
argument-hint: "[--book <short-name>] [--refresh-threads]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/characters.md
  - shared/events.md
  - books/{book}/outline.md
  - books/{book}/threads.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/eval_logs/*.json
writes:
  - books/{book}/threads.md
  - books/{book}/edit_logs/story_map.html
  - books/{book}/edit_logs/story_map.json
context_mode: book
---

<purpose>
The reading surface for "how does the plot develop?". An author who
can't hold a 24-chapter book in their head — "it feels like a bunch of
short anecdotes, not a continuing story building to a climax" — needs
to *see* the book's shape without re-reading it.
`/autonovel:chapter-summary`, `/autonovel:summaries` and
`/autonovel:dashboard` answer that as terminal tables; this command
writes one self-contained HTML page (no internet needed, light/dark,
works on a phone) the author opens in a browser:

- **Synopsis** — every chapter summary stitched in reading order with
  the outline's act headers; a "one line per chapter" switch shows only
  each chapter's end state, the whole book in a couple of minutes.
- **Threads** — plot threads as rows, chapters as columns: which
  chapters plant, turn, pay off or merely touch each thread; click a
  cell to read that touch. Directly under the grid, on the same chapter
  axis, the score / tension / irreversible-change curves from the eval
  logs — so "is it one story, and does it build?" is one glance.
- **Characters** — who is on stage where, and each principal's
  chapters in order with the per-chapter state change.
- **Timeline & places** — story time on a proportional axis with gaps
  over a year labelled; places visited vs only named.

The page is data, not a verdict: it shows which chapters touch each
thread and how long a thread goes untouched; whether that is a problem
is the author's call.

Built from what already exists — chapter frontmatter, every
`ch_NN.summary.md`, `outline.md`, `shared/characters.md`,
`shared/events.md`, the eval logs — plus one LLM-written file, the
thread ledger `books/{book}/threads.md`, which this command writes the
first time (or on `--refresh-threads`) from the outline and the
summaries, never from the chapter prose. The ledger is plain markdown;
edit it by hand and re-run.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via `_begin`.
   `--refresh-threads` is optional.

2. **Decide whether to write the ledger.** Write
   `books/{book}/threads.md` (step 3) only when `--refresh-threads` was
   passed OR the file does not exist. When it exists and
   `--refresh-threads` was not passed, do not touch it — the author may
   have edited it by hand — and go to step 4.

3. **Write the thread ledger** (`file_read` + `file_write`).

   a. Read `books/{book}/outline.md`, then every
      `books/{book}/chapters/ch_NN.summary.md` in chapter order, then
      `shared/characters.md` (for exact names). Read the existing
      `books/{book}/threads.md` too when refreshing. **Do not read the
      chapter prose** (`ch_NN.md`); the summaries are the contract and
      keep this cheap. If a chapter has no summary, leave it out and say
      so in step 5.

   b. Use the `bash` tool to print the file header:

      ```
      autonovel mechanical story-map --threads-template --book {book}
      ```

      Start the file with that output verbatim (it documents the
      grammar for whoever edits the file next).

   c. Then write sections in exactly this grammar — the Python helper
      parses exactly this and reports anything else as a warning:

      ```
      ## Thread: <name>
      - question: <the question the thread poses the reader>
      - ch <N> <role>: <one-line state of the thread after chapter N>

      ## Character: <name>
      - aliases: <name>, <name>
      - arc: <one-line arc summary>
      - ch <N>: <one-line state change in chapter N>

      ## Places
      - <place>
      - <place>: <alias>, <alias>
      ```

      `<role>` is one of `plant`, `turn`, `payoff`, `touch` (omitted =
      `touch`). `<N>` is a chapter number (`ch 5`; `ch 05`, `ch5`,
      `ch_05` also parse). One item per line; a chapter may appear more
      than once in a section; other `##` sections are ignored.

   d. **Threads.** 5–12 of them, the main through-line first. A thread
      is a question the book makes the reader want answered (will he
      repay the 300 by Michaelmas? who is reading the letters?), drawn
      from the outline's act notes and beats and the summaries'
      `Threads opened` / `Threads closed` lines. Mark a chapter only
      when it changes the thread's state: `plant` where it is first
      raised, `turn` where it is complicated, reversed or raised in
      stakes, `payoff` where its question is answered, `touch` for a
      small advance. One `payoff` per thread at most; a thread still
      open at the end has none. Each note is one line, at most ~20
      words, saying what is true of the thread after that chapter, in
      plain words taken from the summary. **Do not invent connections
      the summaries do not show, and do not write judgements** ("stalls",
      "weak", "should") — an empty column or a long gap is exactly the
      information the author is asking for. Keep thread names stable
      across refreshes (reuse the existing file's names and order where
      the thread still applies) so the grid rows do not jump around.

   e. **Characters.** The POV characters plus up to ~6 others on stage
      in the most chapters. Use the `shared/characters.md` heading as
      `<name>`; `aliases:` lists how the summaries' `Cast on stage`
      lines name them (e.g. `Jakob`). Add `- ch <N>:` lines only where
      the character's situation changes — what they want, what they
      gain or lose — one line each, from the summaries' `POV state` and
      `Plot`.

   f. **Places.** The canonical place names the summaries' `Location`
      lines use (cities, regions, sites the story returns to), with
      aliases for alternative spellings. Skip rooms and one-off
      interiors.

4. **Build the page.** Use the `bash` tool:

   ```
   autonovel mechanical story-map --book {book}
   ```

   The helper reads chapter frontmatter (`books/{book}/chapters/ch_*.md`
   — frontmatter only), every summary, `outline.md`, `threads.md`,
   `shared/characters.md`, `shared/events.md`, `project.yaml` (display
   title) and `books/{book}/eval_logs/*.json` (via the dashboard), then
   writes `books/{book}/edit_logs/story_map.html` and its data file
   `books/{book}/edit_logs/story_map.json`, and prints one JSON object:
   `html`, `url`, `json`, `chapters`, `threads`, `characters`,
   `places`, `thread_source`, `synopsis_minutes`, `warnings`,
   `grid_text`. Thread source order: `threads.md` → a `## Threads`
   ledger in `outline.md` → the outline's `events:` ids.

   When a `/autonovel:diff` page (`diff_*.html` with its `.json`) is in
   the same folder, the newest one is linked from the map's header and
   each changed chapter in the synopsis gets an "N changes" link into
   it (`diff_page` in the JSON). `/autonovel:diff` rebuilds this map
   itself on every run, so the two pages always link each other.

5. **Report** to the user, in this order:
   - The page: `Open: <html>` and the `<url>` on the next line. This is
     the deliverable; never suggest a shell command to view it.
   - The `grid_text` value verbatim in a fenced code block (threads as
     rows, chapters as columns) so the shape shows in the terminal too.
   - One line of counts: chapters, threads (and `thread_source`),
     characters, places, synopsis minutes.
   - `warnings`, verbatim, up to 10 (ledger lines that did not parse,
     chapters without summaries, stale summaries, threads touching a
     chapter that has no file yet), with the remainder counted.
   - When `thread_source` is not `threads.md`, one line: run
     `/autonovel:story-map --refresh-threads --book {book}` to write the
     ledger.
   Do not editorialise about the book's structure; the page shows it.

6. Postamble: pass `--wrote` for `books/{book}/threads.md` (only when
   step 3 wrote it), `books/{book}/edit_logs/story_map.html` and
   `books/{book}/edit_logs/story_map.json`.
</workflow>

<acceptance>
- `books/{book}/edit_logs/story_map.html` exists, is one self-contained
  file (inline CSS/JS, no external fetches) and has the Synopsis,
  Threads, Characters and Timeline & places tabs.
- `books/{book}/edit_logs/story_map.json` exists beside it.
- `books/{book}/threads.md` is written only on first run or with
  `--refresh-threads`; it starts with the `--threads-template` header
  and every thread/character line follows the grammar (the helper's
  `warnings` list no `threads.md:` lines).
- No chapter prose (`ch_NN.md` body) is read by the LLM step.
- The reply gives the HTML path and URL, the text grid, and the
  helper's warnings; it never asks the user to run a shell command.
</acceptance>
