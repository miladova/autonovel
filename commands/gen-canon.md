---
name: autonovel:gen-canon
description: Seed canon — series-wide facts into shared/canon.md (world, characters, research) and each book's outline-committed facts into books/<book>/canon.md.
argument-hint: "[--book <short-name>] [--force]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/events.md
  - shared/research/notes/*.md
  - books/*/outline.md
  - shared/canon.md
  - books/*/canon.md
writes:
  - books/*/canon.md
  - shared/canon.md
context_mode: series
---

<purpose>
Seed canon with hard facts. Two files, two scopes:

- `shared/canon.md` — facts **every book in the series** must respect:
  real history, world rules, the cast's fixed biography (birth / death
  dates, family relations), geography, institutions. Derived from
  world + characters + events + research notes.
- `books/{book}/canon.md` — facts **one book's outline** commits to
  (its chapter dates, its invented plot objects, its submerged
  backstory). They bind that book only; a sibling book — or a
  *rewrite* of the same story — may decide them differently.

Canon is append-only going forward; `/autonovel:promote-canon` grows
both files from drafted chapters. This command sets the initial state.

Order: the shared half can run as soon as world / characters /
research exist; the book half is extracted FROM `books/{book}/outline.md`,
so run `--book <short-name>` after `/autonovel:gen-outline` (on a
first book that means running this command twice; `/autonovel:next`
asks for each half at the right moment).
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--force` permits overwriting an already-populated
   canon file. `--book <short-name>` restricts the book-scoped half to
   one book (the series-wide half is only (re)written when
   `shared/canon.md` is still the template stub or `--force` is given —
   adding a second book to a finished series must NOT rewrite the
   shared facts the first book was drafted against). Any other
   argument is a usage error — stop with a one-line reminder.

2. Use `file_read` on `project.yaml`, `shared/world.md`,
   `shared/characters.md`, `shared/events.md`, and every
   `books/*/outline.md` that exists.

2a. **Read research notes when present.** Use `bash` with
    `ls shared/research/notes/*.md 2>/dev/null` to enumerate any
    research notes. For each file, `file_read` it and treat its
    **Cited facts** + **Sources** sections as the *primary*
    source of truth for dates / names / events that conflict
    with the LLM's general knowledge. Period projects with
    `project.yaml :: period.start` set should have research
    notes by this point; if the directory is empty for a
    period project, surface a one-line nudge: "no research
    notes — gen-canon may invent dates that conflict with later
    research" — but proceed when the user has consciously
    chosen to skip research.

    Carry the citation token (`[research:<slug>]`) through every
    canon bullet whose fact came from a research note. The
    promote-canon helper already honours that tag for tagged-
    survives-untagged conflict resolution; preserving it here
    means a future `/autonovel:research` rerun that updates a
    note can supersede the canon entry cleanly.

3. Use `file_read` on `shared/canon.md` and each target
   `books/{book}/canon.md`. A file that contains more than the
   template placeholder comment is left alone unless `--force` was
   supplied; if nothing is writable, stop and say so.

4. Extract canonical facts. A canon entry is a single verifiable claim a
   future chapter must not contradict. Good entries:
   - dated events with named participants,
   - anatomical / physical consequences (scars, disabilities, deaths),
   - family relations, ranks, affiliations,
   - geographical constants (which side of the river, which gate faces
     north).
   Avoid thematic statements, opinions, or anything that could reasonably
   be rewritten later.

5. **Route each fact by scope.** A fact goes to `shared/canon.md`
   when it would hold in ANY book set in this world (it comes from
   world / characters / events / research, or it is verifiable
   history). A fact goes to `books/{book}/canon.md` when it exists
   only because THIS book's outline chose it (a chapter's committed
   date, an invented object, a secret the plot turns on, a favour
   never repaid). When in doubt, book-scoped — promoting a fact to
   series-wide later is one line; un-binding a sibling book from a
   plot invention is a revision pass.

6. Use `file_write` to write `shared/canon.md` (start with `# Canon`)
   and each `books/{book}/canon.md` (start with `# Book canon`).
   Entries as bullet list, one fact per bullet, each with a leading
   `[shortname]` key. Reference events by their `E-###` id in square
   brackets when applicable. No frontmatter.
</workflow>

<acceptance>
- `shared/canon.md` exists, begins with `# Canon`, and contains at least
  three bullet entries (lines beginning with `- `).
- Every `books/{book}/canon.md` written begins with `# Book canon`; no
  bullet in it is plain verifiable history (those belong in shared).
- No bullet is a thematic statement (no lines of the form
  "The story is about X" or "The theme is Y").
- Every `E-###` id referenced in bullets exists in `shared/events.md`.
</acceptance>
