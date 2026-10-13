---
name: autonovel:research
description: Research a real-world topic with live web search and write sourced notes; or `--query` to ask cross-source questions over existing notes without firing web search.
argument-hint: "\"<topic>\" | --from-seed [--book <name>] | --query \"<question>\""
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - web_search
  - web_fetch
reads:
  - project.yaml
  - shared/research/sources.yaml
  - shared/sources.bib
  - shared/world.md
  - shared/research/notes/{topic}.md
  - books/{book}/seed.txt
writes:
  - shared/research/notes/{topic}.md
  - shared/sources.bib
  - books/{book}/pending_canon.md
context_mode: series
---

<purpose>
Investigate `<topic>` against live web sources and produce a research
notes file the drafting and canon layers can trust. The output is a
markdown document at `shared/research/notes/<slug>.md` with an explicit
`## Sources` block (citations in BibTeX shortname form), a
`## Candidate Canon Entries` block, and uncertainty hedges where the web
record is thin. This command is the research-layer equivalent of a
writer walking into a special-collections library: it must cite, and it
must flag when it is guessing.

Design rules:
- The URLs in `shared/research/sources.yaml` marked `weight: primary`
  are mandatory stops. The command MUST call `web_fetch` on every
  primary URL before drafting notes. Secondary URLs are optional but
  strongly preferred.
- Additional sources come from `web_search` queries scoped to the
  topic. Prefer authoritative domains (`.edu`, `.gov`, `.org`,
  university presses, Britannica, national library archives) over
  general-web results.
- Every factual claim in the notes needs a citation. Citations use the
  BibTeX shortname format: `[shortname]`. New shortnames are appended
  to `shared/sources.bib`.
- Anything not recoverable from sources is marked `Speculative`,
  `Uncertain`, or `Needs verification` — never silently asserted.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Two modes:

   **(a) Explicit topic.** A free-form quoted string, e.g.
   `"Venetian apothecaries 1520"`. Anything not quoted is still
   accepted as a single topic. Run the workflow once for that topic.

   **(b) From-seed.** `--from-seed [--book <name>]` reads the active
   book's `seed.txt` plus `project.yaml :: period` to auto-derive 2–4
   research topics, then runs the per-topic workflow (steps 2-10
   below) for each. Use this at the start of foundation for any
   project with a period set — it gives `gen-world` and `gen-canon`
   primary-source notes to draw from instead of the LLM's general
   knowledge. If `--book` is missing, use the inferred book from
   `_begin`'s output.

   To derive topics in mode (b):

   - Pull the period (`period.start`, `period.end`, `period.region`)
     and genre from `project.yaml`.
   - Read `books/{book}/seed.txt`. Extract every named real person,
     place, institution, event, or historically-specific noun (e.g.
     "Jakob Fugger", "Fondaco dei Tedeschi", "the Council of Ten",
     "the mint fire of 1521"). Skip clearly fictional names.
   - Always include one *period overview* topic, slugged as
     `<region>-<start>-<end>` (e.g. `italy-1450-1550`), that asks
     for a one-page summary of the period's politics, economy, and
     daily life in the region.
   - Always include one *period vocabulary* topic, slugged as
     `<region>-<start>-<end>-vocabulary`, that asks for ten
     period-correct nouns and ten anachronisms to avoid.
   - Cap total topics at 4 to keep cost predictable. If the seed
     yields more than 2 named people/places, pick the 2 most central
     to the plot per the seed's pitch.

   **(c) Query-existing-notes.** `--query "<question>"` reads every
   `shared/research/notes/*.md` (no web search, no `web_fetch`),
   answers the question with inline `[shortname]` citations, and
   writes nothing. Distinct from `/autonovel:talk` (queries prose)
   and modes (a)/(b) (live research). Cheap; the right tool for
   "how did Fugger and Maximilian I interact?" or "which notes
   mention the Council of Ten?" Use the
   `autonovel mechanical research-index` CLI for the structural
   "what's even in there" view first; use `--query` for synthesis.

   When mode (c) fires:
     1. Use `bash` to invoke `autonovel mechanical research-index
        <series_root>` so the user sees the available notes inline
        in the response (this lets them spot when a relevant note
        is missing and could be researched live).
     2. Use `file_read` on every `shared/research/notes/*.md` (or a
        subset narrowed by keyword overlap with the question — your
        judgement). Read the actual prose, not just titles.
     3. Answer the question in 2-5 paragraphs. Every claim must
        carry a `[shortname]` citation pulled directly from the
        source notes. When a question has no support in the notes,
        say so explicitly and recommend
        `/autonovel:research "<sub-topic>"` to fill the gap.
     4. End with a `## Sources read` list — slug names, not URLs —
        so the user can drill into specific notes if the answer
        is interesting.

   Missing topic and no `--from-seed`/`--query` → stop with a
   one-line reminder:
   `usage: /autonovel:research "<topic>"  OR  /autonovel:research --from-seed [--book <name>]  OR  /autonovel:research --query "<question>"`.

2. Slugify the topic (lowercase, non-alphanumerics → `-`, collapse
   repeats, trim). Example: `"Venetian apothecaries 1520"` →
   `venetian-apothecaries-1520`. That slug is `<slug>` for the rest
   of the workflow. The notes file is
   `shared/research/notes/<slug>.md` (what `{topic}.md` resolves to
   at runtime).

3. Use `file_read` on `project.yaml` to pull `period.start`,
   `period.end`, `period.region`, and `genre`. These pin the research
   window — when a web result predates or postdates the series
   period, flag it.

4. Use `file_read` on `shared/research/sources.yaml`. Collect every
   entry whose `weight` is `primary` into `primary_urls`; collect
   `secondary` into `secondary_urls`. If the file is missing or
   empty, proceed with an empty list.

5. Use `file_read` on `shared/world.md` and any existing
   `shared/research/notes/{topic}.md`. The world bible pins what has
   already been canonized; a pre-existing notes file is the prior
   run we are extending, not overwriting.

6. Call `web_fetch` on every URL in `primary_urls`. Record the
   rendered page's key facts verbatim with the source URL attached.
   If a primary URL fails to fetch (404, network error), keep the
   attempt and add a `Needs verification` note in the draft — do
   not silently skip it.

7. Call `web_search` at least twice with queries derived from the
   topic and the series period. Examples for a 1520 Venetian topic:
   `"Venetian apothecaries 1520 Rialto"`,
   `"speziale guild Venice sixteenth century"`. Record at least
   four additional candidate sources from the search results, then
   `web_fetch` the two or three most authoritative.

8. Synthesize. Draft notes under the following section skeleton.
   Concrete over abstract. Every H2 section names its sources with
   bracketed shortnames that also exist in `shared/sources.bib`.

   ```
   # Research — <topic>

   Updated <UTC-date>. Period: <start>-<end> <region>.

   ## Summary
   (Two to four paragraphs. The facts a chapter writer can lean on
   without second-guessing. Every claim carries [shortname].)

   ## Material detail
   (Physical specifics — tools, ingredients, clothing, buildings,
   smells, money, scale. This is what rescues a chapter from
   generic period flavour.)

   ## People and institutions
   (Named offices, guilds, families. Dates where known.)

   ## Uncertainties
   - Speculative: ...
   - Uncertain: ...
   - Needs verification: ...

   ## Candidate Canon Entries
   - <fact> [shortname]
   - <fact> [shortname]

   ## Sources
   - [shortname1] Short attribution line + URL + weight
     (primary/secondary/search).
   - [shortname2] ...
   ```

   Minimum bars for the smoke test to pass:
   - At least two distinct `[shortname]` citations appear in the
     body.
   - At least one URL listed under `## Sources` matches a primary
     URL from `shared/research/sources.yaml`.
   - The `## Candidate Canon Entries` section has at least one entry,
     with a shortname.
   - At least one of the words `Speculative`, `Uncertain`, or
     `Needs verification` appears.

9. Use `file_write` to save the notes to
   `shared/research/notes/{topic}.md` (with `{topic}` replaced by
   the slug). Overwrite any prior version.

10. Use `file_write` to append new shortname entries to
    `shared/sources.bib`. Every shortname cited in step 8 must be
    resolvable from `shared/sources.bib` — append if missing, leave
    alone if already there. Skip this step if every citation was
    already in the bib.

11. **Auto-pipe research candidates into the canon-promotion queue.**

    > **Hard rule: do NOT write to `shared/canon.md` (or any
    > `books/<book>/canon.md`) from this command. Ever. The only
    > command that writes canon is `/autonovel:promote-canon`
    > (research-cited entries land in `shared/canon.md`).** Research
    > candidates go into
    > the per-book queue file, where they wait for the next
    > promote-canon run. This rule exists because canon.md is the
    > single point of truth across all books in the series, and an
    > out-of-band write here loses provenance, race-protection, and
    > conflict detection.

    Concretely: for every line in this notes file's
    `## Candidate Canon Entries` section, **append it to
    `books/{book}/pending_canon.md`** (using `file_write` in append
    mode — read the existing content, add new lines after it, write
    back). Add a `[research:<slug>]` tag at the end of every
    appended line. Required exact format:

    ```
    - <fact> [shortname] [research:<slug>]
    ```

    The `[research:<slug>]` tag is what
    `/autonovel:promote-canon` keys on to resolve conflicts in
    research's favour (cited > guessed) while preserving the
    citation in the canonical entry. Without the tag, the entry
    looks like a chapter-derived candidate and loses the
    research-wins-on-conflict behaviour. Do not omit it.

    User flow this step enables:
    1. `/autonovel:research --from-seed`  — research notes written;
       candidates queued in `pending_canon.md`.
    2. `/autonovel:promote-canon`         — queued candidates
       merged into canon, contradictions decided in research's
       favour, supersedures recorded with citations.

    Skip this step in mode (a) — explicit-topic mode is for
    on-demand research where the user is reading the notes
    themselves; auto-piping there would surprise them. Mode (b)
    `--from-seed` is the auto-piping mode by design.

    If `--book` is unknown (mode-b run series-wide without a
    specific book), append to *every* book's
    `pending_canon.md` listed in `project.yaml`. Each book's
    `/autonovel:promote-canon` run then picks them up at its
    leisure.
</workflow>

<acceptance>
- `shared/research/notes/<slug>.md` exists and begins with a
  `# Research — <topic>` heading.
- The file contains a `## Sources` section with ≥ 2 distinct
  `[shortname]` citations.
- At least one `url:` from the `primary` entries of
  `shared/research/sources.yaml` is present as a substring of the
  notes file.
- At least one of `Speculative`, `Uncertain`, or
  `Needs verification` appears in the file.
- A `## Candidate Canon Entries` section exists.
- Every `[shortname]` cited in the notes resolves to an entry in
  `shared/sources.bib`.
</acceptance>
