---
name: autonovel:gen-world
description: Generate shared/world.md from project.yaml and the books' seeds.
argument-hint: ""
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/*/seed.txt
  - shared/world.md
  - shared/research/notes/*.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
writes:
  - shared/world.md
context_mode: series
---

<purpose>
Seed the series-wide world bible in `shared/world.md`. This is a Layer-4
artifact: what exists. Later commands depend on it — `gen-characters`,
`gen-outline`, every `draft`, every `evaluate`. Write it once and evolve it
sparingly through canon promotion rather than wholesale rewrites.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. This command takes no positional arguments; `--force`
   is optional and permits overwriting a populated `shared/world.md`. Any
   other argument is a usage error — stop and surface a one-line reminder.

2. Use `file_read` on `project.yaml`. The fields that matter for world
   construction: `series_name`, `genre`, `period.start`, `period.end`,
   `period.region`. If `genre` implies period guardrails (historical,
   alt-history, period-fantasy), those constrain every later layer.

3. Use `file_read` on every `books/*/seed.txt`. Each seed is one to three
   paragraphs about a book in the series. Read all of them — the world has
   to support every book, not just the first.

3a. **Read research notes when present.** Use `bash` with
   `ls shared/research/notes/*.md 2>/dev/null` to enumerate any
   research notes. For each file, `file_read` the whole thing and
   treat its **Cited facts** + **Sources** sections as
   *primary* over the LLM's general knowledge. Period
   projects (those with `project.yaml :: period.start` set)
   should have research notes; if the directory is empty for a
   period project, surface a one-line nudge in stdout: "no
   research notes — run `/autonovel:research --from-seed` first
   so the world is built on cited dates" — but proceed if the
   user is consciously skipping research. Cite the research-
   note slugs in the world bible's Sources section so the
   provenance trail is visible to gen-canon.

3b. When the series has a genre guide (the book's genre guide: the file
`_begin`'s `genre:` line names (`autonovel genre show --book {book}`
prints it when no preamble ran; it is `shared/craft/genres/<genre>.md`,
or the series' own `shared/genres/<genre>.md`)), read its `## The
   promise` and `## Research`: the world bible carries what this genre's
   reader comes for (for historical fiction: daily life, how people saw
   the world, and the places with their names then and what survives).

4. Use `file_read` on `shared/world.md`. If it contains more than the
   template placeholder comment and `--force` was not supplied, stop; this
   command does not overwrite handwritten world bibles without confirmation.

5. Draft the world bible. Concrete over abstract. Name specific places,
   institutions, material constraints (climate, economy, technology,
   prevailing belief). Do not plot; do not profile characters. Keep it to
   roughly 400-900 words unless the series demands more.

6. Use `file_write` to replace `shared/world.md` with the new bible. Start
   with `# World` as the first heading. No frontmatter; this is shared
   canon, not a chapter.
</workflow>

<acceptance>
- `shared/world.md` exists, begins with `# World`, and is at least 400
  words of substantive content (template placeholder comments do not count).
- `project.yaml` was read (model references `period` and `genre` in the
  drafted bible where relevant).
- No plot beats or chapter-by-chapter summaries appear in the bible — that
  is `outline.md`'s job.
</acceptance>
