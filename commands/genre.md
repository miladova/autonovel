---
name: autonovel:genre
description: Show or set a book's genre and subgenres (each with what its reader comes for), or research and write a sourced guide for a genre that has none yet.
argument-hint: "[--book <short-name>] [--list] [--set <genre>] [--subgenres <a,b>] [--add <genre>]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
  - web_search
  - web_fetch
reads:
  - project.yaml
  - shared/craft/genres/README.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
  - shared/craft/EDITING.md
writes:
  - project.yaml
  - shared/genres/*.md
context_mode: series
---

<purpose>
A book's genre decides what its reader comes for, and so what every
writing, reading and judging command must protect. A reader of
historical fiction comes partly to learn the period: real events and
people, how people lived and saw the world, places that still stand. A
reader of hard science fiction comes for science followed to its
consequences. Before genres were first-class, the pipeline knew neither,
and its cold readers and judges pushed to cut what the reader came for.

Each genre in the registry (`autonovel genre list`) has subgenres with a
one-line promise. A genre with a written guide
(`shared/craft/genres/<genre>.md`, package-owned) tells each command what
to do: `shared/craft/genres/README.md` lists the sections and who reads
which. `_begin` names the book's genre and guide at the start of every
command.

Three modes:

- **show** (no flags, or `--list`): the book's genre, subgenres, their
  promises and the guide; `--list` prints the whole registry.
- **`--set <genre>` and/or `--subgenres <a,b>`**: write them to
  `project.yaml` (the series, or the book's entry with `--book`). A book
  can be two subgenres at once; a subgenre the registry lacks is given as
  `other: <words>`.
- **`--add <genre>`**: research the genre (or one subgenre) and write a
  sourced guide in the standard sections to `shared/genres/<genre>.md`,
  the series' own copy, which `refresh-templates` never overwrites. Use it
  when the registry says "no guide yet".
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book` defaults via `_begin` for show and set;
   without a book, set writes the series' `genre:` / `subgenres:`.

2. **Show** (no `--set`, `--subgenres` or `--add`). Use `bash` to run
   `autonovel genre show --book {book}` (or `autonovel genre list` with
   `--list`) and print its output verbatim. When it warns that the guide
   is missing, the fix is `autonovel refresh-templates`; when no guide is
   written for the genre, offer `/autonovel:genre --add <genre>`.

3. **Set.** Use `bash` to run
   `autonovel genre set [--genre <genre>] [--subgenres "<a,b>"] [--book {book}]`.
   It normalises aliases (historical-fiction → historical, historical
   thriller → political-thriller), keeps `other: <words>` as given, and
   prints the result. Print it, then one line on what changes: every
   later draft, revise, first reader, evaluate, cut list and editor's
   read follows the new genre's guide; chapters already drafted are not
   rewritten (`/autonovel:revision-pass` applies the guide to them).

4. **Add a guide** (`--add <genre>`, for a genre the registry marks "no
   guide yet", or one it lacks). Study first: use
   `file_read` on `shared/craft/genres/README.md` (the sections) and on
   `shared/craft/genres/historical.md` as the model of depth and
   sourcing; read `shared/craft/EDITING.md`'s part on the genre if it has
   one. Then research with `web_search` (at least eight searches) and
   `web_fetch` (the most authoritative pages, fetched, never quoted from
   a search snippet):
   - the genre's definition by its readers' society, librarians'
     readers' advisory (NoveList, Saricks) or a standard guide;
   - surveys or published evidence of why its readers read it and what
     spoils it for them;
   - its subgenres, from a recognised taxonomy, each with a promise and
     comparable books;
   - how its writers deliver what the reader comes for without stopping
     the story (for science fiction, the exposition of invented science;
     for fantasy, the world's rules), in their own words.
   Write `shared/genres/<genre>.md` with the README's sections in order,
   in the historical guide's voice: plain sentences, every claim tied to
   a named source with a URL in `## Sources`, verbatim quotes only from
   fetched pages, and anything unverified marked "unverified". The
   `## Judging` section defines at most one extra evaluate dimension
   under a heading ``### The `<name>` dimension (chapter mode)`` (the
   heading is how `autonovel genre show` finds it), with a 0–10
   rubric; `## Cutting` names what never counts as over-explaining;
   `## The first reader` says who this genre's reader is.
   Never name one of this series' books in the guide.

5. Print a one-screen summary: the genre and subgenres now set (or the
   guide written, its sections and source count), and the commands that
   will read it.
</workflow>

<acceptance>
- Show writes nothing.
- Set changes only `genre:` / `subgenres:` in `project.yaml` (series or
  the named book's entry), and `autonovel genre show` then reports them.
- Add writes `shared/genres/<genre>.md` with every section the README
  lists, in order, and a `## Sources` section whose entries carry URLs.
</acceptance>
