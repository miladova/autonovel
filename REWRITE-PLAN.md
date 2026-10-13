# autonovel rewrite plan

**Status:** plan of record as of 2026-04-24. Written at the end of the planning session; intended to be the handoff artifact that every subsequent implementation session starts from.

**Scope:** full rewrite of `autonovel` from a set of Python scripts that call the Anthropic API directly into a GPD-style package of markdown commands installed into the user's AI CLI runtime (Claude Code, OpenAI Codex, Gemini CLI).

**Reference implementations:**
- `psi-oss/get-physics-done` — architecture we are copying.
- `mattprusak/autoresearch-genealogy` — minimal-markdown pattern for prompts.

---

## 1. Why the rewrite

The current repo calls `api.anthropic.com` directly from ~18 Python scripts. This:

- Forces one specific provider.
- Duplicates ~20 lines of HTTP wiring in every script.
- Prevents the CLI runtime from doing what it is already good at: auth, file I/O, web search, iteration, parallel sub-agents.
- Leaves the "framework" scripts contaminated with Bells-story-specific prompts.

The GPD pattern replaces all of this with markdown command files that the runtime executes. The runtime owns the model, auth, and tool calls. Python stays only for housekeeping.

---

## 2. Target architecture in one paragraph

Autonovel ships as an npm package. `npx autonovel install` detects which AI CLIs are installed on the user's machine and drops a set of `/autonovel:*` command files into each one at the runtime's expected path. The user then opens their project folder inside any of those CLIs and invokes commands like `/autonovel:draft 5 --book inquisitor`. The runtime handles the model call, reads the files the command tells it to read, does web search if the command needs it, and writes output files. A small local `autonovel` Python command stays on the user's PATH for housekeeping (new series, new book, promote canon entries, show status). No Python code calls any LLM.

---

## 3. Repo structure after the rewrite

```
autonovel/                              # this repo, the source of truth
  package.json                          # for npx autonovel install
  pyproject.toml                        # for the housekeeping CLI
  README.md                             # install + one-worked-example
  CLAUDE.md, AGENTS.md, GEMINI.md       # symlinks to a single conventions file
  docs/
    commands.md                         # every /autonovel:* command
    series-layout.md                    # shared/ vs books/ + project.yaml
    writing-a-historical-series.md      # 1450-1550 Europe walkthrough
    multi-book.md                       # 3-book coordination rules
    testing.md                          # how to run and extend the tests
    pipeline-history.md                 # archived PIPELINE.md from Bells run
  CRAFT.md, ANTI-SLOP.md, ANTI-PATTERNS.md
                                         # unchanged; referenced by commands
  commands/                             # the single source of truth
    draft.md
    gen-world.md
    gen-characters.md
    gen-outline.md
    voice-discovery.md
    gen-canon.md
    evaluate.md
    adversarial-edit.md
    apply-cuts.md
    reader-panel.md
    review.md
    brief.md
    revise.md
    research.md
    promote-canon.md
    check-anachronism.md
    run-pipeline.md
    new-series.md
    new-book.md
  src/autonovel/                        # housekeeping Python
    __init__.py
    cli.py                              # entry for `autonovel` command
    housekeeping/                       # new-book, promote-canon, status
    adapters/                           # runtime install adapters
      base.py
      claude_code.py
      codex.py
      gemini.py
      detect.py                         # which runtimes are present
    validators/                         # Tier-1 and Tier-2 tests
      frontmatter.py
      chapter_frontmatter.py
      events_ledger.py
      command_contract.py
    mechanical/                         # regex-only helpers ported from evaluate.py
      slop_scanner.py
      anachronism_scanner.py
  tests/
    deterministic/                      # Tier 1
    contracts/                          # Tier 2
    smoke/                              # Tier 3 (opt-in, costs money)
    regression/                         # Tier 4 (opt-in, costs money)
    fixtures/
      tiny-series-historical/           # 1520 Venice, 3 chapters
      tiny-series-scifi/                # near-future, 3 chapters
      tiny-series-literary/             # contemporary, 3 chapters
      bells-reference/                  # frozen outputs for regression

# A user's own series repo looks like this (not this repo):
my-renaissance-series/
  project.yaml                          # series config (period, genre, LLM tier)
  shared/
    world.md, characters.md, canon.md
    events.md                           # cross-book event ledger
    timeline.md
    MYSTERY.md
    sources.bib                         # BibTeX, real-world citations
    research/
      seed/*.md                         # user-authored, forced into context
      sources.yaml                      # URLs the agent must consult
      notes/*.md                        # agent-generated research
    period_bans.txt                     # anachronism blocklist
  books/
    inquisitor/
      seed.txt, voice.md, outline.md
      chapters/ch_*.md                  # each with YAML frontmatter
      pending_canon.md                  # candidate facts, awaits promotion
      state.json, results.tsv
      briefs/, edit_logs/, eval_logs/, typeset/
    apothecary/
    merchant/
```

---

## 4. Command catalogue

All commands live in `commands/` as markdown with YAML frontmatter. The installer translates to each runtime's native format.

**See also §21.8** for the sidequest commands (shorten, lengthen, split, merge, add-character, add-subplot, rename, reorder, remove, deepen, revoice, foreshadow, add-source, next, resume, sidequest). Those are listed separately because they exist to let the writer step off the standard path without losing state.

| Command | Purpose | Reads | Writes |
|---|---|---|---|
| `/autonovel:new-series <name>` | Create a series folder with shared/ and project.yaml | — | directory tree |
| `/autonovel:new-book <name> [--series]` | Add a book to a series | project.yaml | books/<name>/ |
| `/autonovel:research <topic>` | Web-search + seeded research; writes cited notes | shared/research/seed/, shared/research/sources.yaml | shared/research/notes/<topic>.md |
| `/autonovel:gen-world` | Generate shared/world.md from seed + voice | seed.txt, voice.md, CRAFT.md, research notes | shared/world.md |
| `/autonovel:gen-characters` | Generate shared/characters.md | seed.txt, shared/world.md, CRAFT.md | shared/characters.md |
| `/autonovel:gen-outline --book <name>` | Outline for one book; respects shared world/chars | shared/* + books/<name>/seed.txt | books/<name>/outline.md |
| `/autonovel:voice-discovery --book <name>` | 5 trial passages, pick best, fill voice.md Part 2 | shared/world.md, seed.txt | books/<name>/voice.md |
| `/autonovel:gen-canon` | Cross-reference hard facts into shared/canon.md | shared/world.md, shared/characters.md, chapters | shared/canon.md |
| `/autonovel:draft <ch> --book <name>` | Draft one chapter | everything relevant | books/<name>/chapters/ch_<N>.md |
| `/autonovel:evaluate --chapter <N> --book <name>` | Score one chapter (LLM judge + mechanical) | one chapter | books/<name>/eval_logs/… |
| `/autonovel:evaluate --full --book <name>` | Score whole novel | all chapters | … |
| `/autonovel:evaluate --phase foundation --book <name>` | Score planning docs | shared/* + book voice | … |
| `/autonovel:adversarial-edit <ch> --book <name>` | "Cut 500 words" analysis | one chapter | books/<name>/edit_logs/ch<N>_cuts.json |
| `/autonovel:apply-cuts --types OVER-EXPLAIN,REDUNDANT --book <name>` | Batch cut applier | edit_logs + chapters | rewritten chapters |
| `/autonovel:reader-panel --book <name>` | 4-persona novel-level evaluation | all chapters | books/<name>/edit_logs/reader_panel.json |
| `/autonovel:review --book <name>` | Opus dual-persona full-manuscript review | all chapters | books/<name>/review.md |
| `/autonovel:brief --auto --book <name>` | Auto-generate revision brief from feedback | panel + eval + chapters | books/<name>/briefs/ch<N>.md |
| `/autonovel:revise <ch> --book <name>` | Rewrite a chapter from a brief | brief + chapter + context | rewritten chapter |
| `/autonovel:check-anachronism --book <name>` | Scan all chapters vs period_bans + judge pass | chapters + period_bans.txt + sources.bib | flags report |
| `/autonovel:promote-canon --book <name>` | Merge pending_canon.md into shared/canon.md (interactive) | pending_canon.md | shared/canon.md |
| `/autonovel:run-pipeline [--book <name>] [--books a,b,c]` | Full orchestrator | everything | everything |
| `/autonovel:art-style --book <name>` | Derive the visual style for this book from voice + world | shared/world.md, book voice.md | books/<name>/art/style.md |
| `/autonovel:art-directions --book <name> --n <count>` | Generate diverse art directions for curation | art/style.md | books/<name>/art/directions/ |
| `/autonovel:art-curate <target> --book <name> --n <count>` | Generate cover / ornament variants via fal.ai and present for picking | art/style.md, art/directions/ | books/<name>/art/<target>/variants/ |
| `/autonovel:art-pick <target> <variant> --book <name>` | Commit a variant as the chosen version | variants/ | books/<name>/art/<target>/chosen.* |
| `/autonovel:art-ornaments-all --book <name>` | One ornament per chapter, derived from chapter content | chapters/ + art/style.md | books/<name>/art/ornaments/ |
| `/autonovel:art-vectorize --book <name>` | PNG → SVG → PDF-ready vector assets | art/**/*.png | art/**/*.svg + .pdf |
| `/autonovel:cover-composite --book <name>` | Compose text overlay on chosen cover art | art/cover/chosen.*, typeset metadata | books/<name>/typeset/cover-composite.* |
| `/autonovel:cover-print --book <name> --size <trade|lulu|kdp>` | Full-wrap print-ready cover with spine/bleed | book metadata, art | books/<name>/typeset/cover-print.pdf |
| `/autonovel:audiobook-script --book <name>` | Parse chapters into speaker-attributed script | chapters/ + characters.md | books/<name>/audiobook/script.json |
| `/autonovel:audiobook-voices --book <name>` | Map each speaker to an ElevenLabs (or chosen provider) voice | script.json + voices catalogue | books/<name>/audiobook/voices.json |
| `/autonovel:audiobook-generate --book <name> [--test <ch>]` | Synthesize audio for all chapters (or one test chapter) | script + voices | books/<name>/audiobook/<ch>.mp3 |
| `/autonovel:audiobook-assemble --book <name>` | Concatenate per-chapter files into a full novel with chapter marks | per-chapter mp3s | books/<name>/audiobook/full.mp3 + chapters.cue |
| `/autonovel:typeset --book <name> [--format pdf|epub|both]` | Build LaTeX/tectonic PDF and/or ePub | chapters, typeset/* | books/<name>/typeset/novel.pdf, .epub |
| `/autonovel:landing --book <name>` | Generate a static landing page for the book | metadata, cover, sample chapter | books/<name>/landing/index.html |
| `/autonovel:package --book <name>` | One-shot: typeset + cover + audiobook + landing; produce a release bundle | everything above | books/<name>/release/ |

---

## 5. Command file format (the contract)

Every file in `commands/` has this shape. The installer validates it.

```markdown
---
name: autonovel:draft
description: Draft one chapter of a book.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: standard                # heavy | standard | light
allowed-tools:
  - file_read
  - file_write
  - task
reads:
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - shared/events.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{prev}.md    # previous chapter, last 1000 words
  - shared/research/notes/*.md
writes:
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/pending_canon.md         # appended, not overwritten
context_mode: book                        # none | book | series
---

<purpose>
Write chapter N of the named book as full prose, obeying the voice, world,
characters, outline beats, and canon. Respect story-time: chapters from other
books with story_time <= this chapter's story_time are readable context.
</purpose>

<workflow>
1. Parse arguments...
2. Read project.yaml to resolve the series and book paths...
3. Read the chapter's outline entry and its story_time...
4. Load sibling-book chapters with story_time <= current, as read-only...
5. Write the chapter following anti-pattern rules from ANTI-PATTERNS.md...
6. Append candidate canon facts to books/{book}/pending_canon.md...
</workflow>

<acceptance>
- File books/{book}/chapters/ch_{chapter}.md exists and is >= 2000 words.
- Frontmatter contains book, chapter, pov, story_time, events, status=drafted.
- At least one candidate fact added to pending_canon.md OR a note saying none.
- No words from shared/period_bans.txt appear (check after write).
</acceptance>
```

Fields:

- **`model_tier`** — `heavy` (Opus 4.7 + thinking), `standard` (Sonnet 4.6), `light` (Haiku). The adapter maps tier → specific model per runtime; the command author never names a model.
- **`reads` / `writes`** — the contract the Tier-2 tests validate. Paths may use `{book}`, `{chapter}`, `{prev}`, `{topic}` placeholders.
- **`context_mode`** — lets the runtime know how much of the surrounding filesystem to pull in by default.
- **`<acceptance>`** — machine-checkable post-conditions. The smoke test harness runs these.

---

## 6. `project.yaml` schema

One file per series. Replaces env vars.

```yaml
series_name: renaissance-europe
genre: historical-fiction
period:
  start: 1450
  end: 1550
  region: europe
llm:
  heavy: claude-opus-4-7
  standard: claude-sonnet-4-6
  light: claude-haiku-4-5-20251001
  thinking:
    heavy: true
    standard: false
books:
  - name: inquisitor
    pov: Tommaso
    story_time_range: [1519, 1523]
    status: drafting
  - name: apothecary
    pov: Lucia
    story_time_range: [1520, 1524]
    status: outlined
  - name: merchant
    pov: Gasparo
    story_time_range: [1518, 1524]
    status: seed
  - name: inquisitor-retold          # a rewrite of `inquisitor`
    pov: Tommaso
    story_time_range: [1519, 1523]
    status: seed
    context: isolated                 # never reads sibling-book chapters as context
defaults:
  chapter_target_words: 3200
  foundation_threshold: 7.5
  chapter_threshold: 6.0
```

---

## 7. Chapter frontmatter

```yaml
---
book: inquisitor
chapter: 5
pov: Tommaso
story_time: 1522-03-15           # ISO date; may be a range: 1522-03-15..1522-03-18
events: [E-047, E-048]
status: drafted                  # drafted | revised | locked
word_count: 3214
score: 7.8
---
```

The `story_time` field is the backbone of multi-book coordination: when drafting chapter X, the context loader shows every already-drafted chapter across all books with story_time less than or equal to X. A book with `context: isolated` in `project.yaml` (a rewrite of a story another book tells) opts out: no sibling chapter is ever shown, only `shared/` lore. Canon is book-scoped (2026-10-12): `shared/canon.md` holds series-wide facts, `books/<book>/canon.md` the facts one book's prose fixed; a book is never checked against a sibling's canon.

---

## 8. `shared/events.md` format

```markdown
## E-047: Fire at the Venetian mint
- date: 1522-03-15
- location: Zecca, Venice
- present: [Tommaso, Lucia, Master Giraldo, two apprentices]
- canonical: Master Giraldo set the fire to destroy the ledgers proving his fraud.
  Wind was from the south. The ledger room burned hottest. Two apprentices
  escaped via the south window.
- rendered_in:
    inquisitor/ch_12: Tommaso's POV, sees smoke from the Piazza.
    apothecary/ch_08: Lucia's POV, treats Giraldo's burns that night.
- book_constraints: Lucia must not know who lit it at the end of this scene.
```

Drafters reading this for their POV use only the `canonical` field and their POV row from `rendered_in`.

---

## 9. Installer: `npx autonovel install`

Clear, simple instructions for the README:

````markdown
## Install

Install the commands into whichever AI CLI you use.

Pick one of the two install paths. Both work; both are supported.

**Option A — global install (recommended if you'll use autonovel more than once):**

```bash
# Install once; the `autonovel` command is then on your PATH forever.
npm install -g autonovel
autonovel install

# The installer does three things:
#   a. Detects which AI CLIs are on your machine (Claude Code, Codex, Gemini CLI).
#   b. Writes the /autonovel:* commands into each one.
#   c. Leaves `autonovel` on your PATH for setup and housekeeping.
```

**Option B — no global install:**

```bash
# Run the installer without adding anything permanent to your system.
# Every later `autonovel` call is prefixed with `npx`.
npx autonovel install
```

After either path, the workflow is the same:

```bash
# Start a new series. (If you used Option B: `npx autonovel new-series ...`)
autonovel new-series renaissance-europe

# Add your first book.
autonovel new-book inquisitor --series renaissance-europe

# Open the series folder in whichever CLI you installed.
cd renaissance-europe
claude          # or:  codex          or:  gemini

# Inside the CLI, run the pipeline.
/autonovel:run-pipeline --book inquisitor
```

That is the whole quickstart. Everything else is one command.

### Installing into one runtime only

```bash
autonovel install --only claude       # or codex, or gemini
```

### Uninstalling

```bash
autonovel uninstall
npm uninstall -g autonovel            # only if you used Option A
```
````

Behind the scenes, the installer writes to:

- Claude Code: `~/.claude/commands/autonovel/*.md`
- Codex: `~/.codex/prompts/autonovel-*.md`
- Gemini CLI: `~/.gemini/commands/autonovel/*.toml`

Each file is generated from the one source-of-truth `commands/*.md` plus a per-runtime template.

---

## 10. Housekeeping CLI (`autonovel`)

Plain Python, no LLM calls. Lives on `$PATH` after install.

```
autonovel install [--only <runtime>]
autonovel uninstall
autonovel new-series <name> [--genre <genre>] [--period <start>-<end>]
autonovel new-book <name> --series <name> [--pov <character>]
autonovel promote-canon --book <name>          # interactive merge
autonovel status [--series <name>]             # progress dashboard
autonovel doctor                               # check runtimes, paths, perms
autonovel version
```

---

## 11. Runtime adapter matrix

| Feature | Claude Code | Codex | Gemini CLI |
|---|---|---|---|
| Command syntax | `/autonovel:draft` | `$autonovel-draft` | `/autonovel:draft` |
| Command file path | `.claude/commands/autonovel/draft.md` | `.codex/prompts/autonovel-draft.md` | `.gemini/commands/autonovel/draft.toml` |
| Tool name: read a file | `Read` | `file_read` | `read_file` |
| Tool name: web search | `WebSearch` | `web_search` | `google_web_search` |
| Sub-agent fan-out | `Task` | `spawn` | `run_agent` |
| Frontmatter style | YAML | YAML | TOML |
| Extended thinking | yes | (n/a; uses reasoning_effort) | yes |

The adapter for each runtime owns all of this mapping. Command authors write generic names (`file_read`, `web_search`, `task`) and the adapter translates. This is exactly how GPD's `tool_names.py` works.

---

## 12. Testing plan — four tiers

### Tier 1: deterministic (pytest, free, runs on every commit)

- **`frontmatter.py`**: parse every `commands/*.md`, assert required fields, legal tool names, valid model_tier, valid context_mode.
- **`chapter_frontmatter.py`**: given a chapter file, parse its YAML, assert book/chapter/pov/story_time/events/status present, ISO date parses, events resolve against `shared/events.md`.
- **`events_ledger.py`**: parse `shared/events.md`, check every `rendered_in` entry references a chapter file that exists and is tagged with matching event ID.
- **`command_contract.py`**: dependency graph over `reads:` / `writes:` across all commands; detect orphan outputs (nobody reads this) and unresolved inputs (nobody writes this).
- **`slop_scanner.py`** and **`anachronism_scanner.py`**: regex logic extracted from current `evaluate.py`; tested with known-good and known-bad strings.
- **Housekeeping tests**: `new-series`, `new-book`, `promote-canon` dry-run, chapter-renumber rename logic.
- **Adapter tests**: given a command file with known frontmatter, assert each adapter produces the correct output file at the correct path with the correct content. Golden-file comparison.

### Tier 2: command contracts (pytest, free, runs on every commit)

- Parse frontmatter `reads` and `writes` from every command.
- Parse the command body and verify every file listed under `reads:` is mentioned in the body (the command actually uses what it claims to read).
- Parse `writes:` and verify the body describes writing each file.
- Verify placeholders in paths (`{book}`, `{chapter}`) are defined in `argument-hint` or resolvable from context.
- Run `new-series` → `new-book` and confirm every file a downstream command lists under `reads:` exists as an empty template.

### Tier 3: smoke tests (pytest, costs money, opt-in)

Invokes the runtime in headless mode against a tiny fixture series. Claude Code first; Codex and Gemini on pre-release.

Per-genre fixture series under `tests/fixtures/`. Ship with eight fixtures covering the major commercial and literary genres; users can add more (see §12a):

- **`tiny-series-historical/`** — 1520 Venice, 3 chapters. Period guardrails, sources.bib, forced research URL. Used for the live-search smoke test.
- **`tiny-series-scifi/`** — near-future, 3 chapters. Technology-rule consistency.
- **`tiny-series-literary/`** — contemporary, 3 chapters. Voice-heavy; no world rules.
- **`tiny-series-mystery/`** — amateur detective, 3 chapters. Fair-play clue seeding; red-herring ledger.
- **`tiny-series-thriller/`** — pursuit plot, 3 chapters. Pacing/beat density checks; ticking-clock enforcement.
- **`tiny-series-romance/`** — dual-POV contemporary, 3 chapters. Beat-sheet (meet / conflict / dark-moment / resolution) coverage; HEA or HFN ending required.
- **`tiny-series-fantasy/`** — secondary-world, 3 chapters. Sanderson's laws hard-rule check; magic-cost enforcement.
- **`tiny-series-horror/`** — slow-burn, 3 chapters. Dread/escalation pacing; sensory-specificity check.

For each command, for each fixture where relevant, for Claude Code only:

1. Reset fixture to known state.
2. Invoke `claude -p "/autonovel:<cmd> <args>" --allowed-tools "..."` headless.
3. Check exit code.
4. Run the `<acceptance>` block from the command's frontmatter as assertions against the filesystem.

Example assertions for `/autonovel:draft 1 --book tiny-inquisitor`:
- File `books/tiny-inquisitor/chapters/ch_01.md` exists.
- Frontmatter parses; `pov` equals `Tommaso`; `story_time` is a valid ISO date in [1519, 1523].
- Word count between 2000 and 4500.
- No words from `shared/period_bans.txt` appear (case-insensitive word-boundary match).
- At least one line appended to `pending_canon.md`.

Cost estimate: ~$5 per full smoke sweep on Sonnet; ~$0.50 on Haiku. The fixture is sized so Haiku can complete it, but results are dim — default to Sonnet.

### 12a. User-extensible genre fixtures

End users can add their own genre fixtures without modifying autonovel itself. Extensibility is a first-class feature.

**Adding a new fixture:**

```bash
autonovel test-fixture new my-western
# Creates tests/fixtures/tiny-series-my-western/ with:
#   project.yaml            (genre=my-western, period/region stubs)
#   seed.txt                (user fills in)
#   shared/period_bans.txt  (empty; user fills in if period-sensitive)
#   shared/characters.md    (seed characters)
#   books/book-one/seed.txt
#   smoke/test_my_western.py  (template test, ready to customize)
#   README.md               (what this fixture is for, what it tests)
```

**Contract a fixture must satisfy:**

- `project.yaml` is valid per §6.
- `smoke/test_*.py` declares `@pytest.mark.smoke` and `@pytest.mark.genre("<name>")`.
- At least one assertion on a genre-characteristic behaviour (not just "a file was written").
- A `README.md` explaining what genre quirk this fixture exercises.

**Running fixture tests:**

```bash
pytest -m 'smoke and genre("mystery")'              # one genre
pytest -m 'smoke and not genre("horror")'           # all except one
pytest -m 'smoke' --genre-matrix                    # full matrix, parallel
```

`autonovel test-fixture list` and `autonovel test-fixture run <name>` are housekeeping CLI shortcuts.

The shipped eight fixtures live in `tests/fixtures/` in this repo. Users' custom fixtures go in their own series-repo under `tests/fixtures/` and run against their locally installed autonovel.

### Tier 4: evaluator regression (pytest, costs money, opt-in, manual)

- Frozen set: the final Bells chapters with their final `evaluate.py` scores captured in `tests/fixtures/bells-reference/scores.json`.
- For a PR that changes a command, run the command against matched inputs and compare score.
- Assert new score within 0.5 of frozen reference.
- This is the "did the rewrite make it worse" guardrail.

### Genre test — historical fiction live-search

This is the test you specifically asked for. Lives under `tests/smoke/test_historical_research.py`.

```python
@pytest.mark.smoke
@pytest.mark.historical
def test_research_venetian_apothecaries_1520(tmp_runtime_series):
    """
    /autonovel:research must do live web search and produce a sourced notes file
    for a real historical topic in the 1400-1600 European window.
    """
    series = tmp_runtime_series("tiny-series-historical")
    topic = "Venetian apothecaries 1520"

    result = run_command_in_runtime(
        runtime="claude",
        command=f"/autonovel:research \"{topic}\"",
        cwd=series.path,
        allowed_tools=["Read", "Write", "WebSearch", "WebFetch"],
    )
    assert result.exit_code == 0

    notes = series.path / "shared/research/notes/venetian-apothecaries-1520.md"
    assert notes.exists()

    text = notes.read_text()
    # Has a sources section with at least two distinct citations.
    assert "## Sources" in text
    assert len(extract_citations(text)) >= 2

    # Cites at least one forced URL from shared/research/sources.yaml.
    forced = load_yaml(series.path / "shared/research/sources.yaml")
    forced_urls = [s["url"] for s in forced if s.get("weight") == "primary"]
    assert any(u in text for u in forced_urls)

    # Contains at least one period-specific detail from a known list.
    known_details = ["theriac", "mithridate", "Zecca", "speziale", "Rialto",
                     "bezoar", "aqua vitae"]
    assert sum(1 for d in known_details if d.lower() in text.lower()) >= 2

    # Flags uncertainty where appropriate.
    assert "Speculative" in text or "Uncertain" in text or "Needs verification" in text

    # Produces candidate canon entries.
    assert "## Candidate Canon Entries" in text
```

Additional genre-specific smoke tests (one per fixture, minimum):

- **Sci-fi**: `/autonovel:gen-world` must not hallucinate current-year facts. Generated world.md contains no `[citation needed]` placeholders and the technology rules section has at least three explicit hard limits.
- **Literary contemporary**: `/autonovel:voice-discovery` produces 5 distinct trial passages (Levenshtein distance above a threshold between any two) and picks one with a written justification.
- **Mystery**: `/autonovel:gen-outline` produces an outline with at least three red herrings and at least one true clue per act, logged in a dedicated ledger section. Chapters that plant clues are tagged in the foreshadowing ledger.
- **Thriller**: every chapter's outline entry carries a stakes-escalation note; at least one chapter per act ends on an explicit page-turn hook (external threat or revelation).
- **Romance**: outline covers the four-beat structure (meet, conflict, dark-moment, resolution); final chapter outline explicitly names the HEA or HFN state.
- **Romance (flakiness-accepted flavor)**: `/autonovel:evaluate` on a drafted chapter returns a `romantic_tension` dimension score; we assert presence, not exact value.
- **Fantasy**: `/autonovel:gen-world` magic system section has costs/limits for every listed power; smoke test fails if any rule lacks a cost clause.
- **Horror**: `/autonovel:evaluate --chapter 1` returns a `dread_arc` commentary; assertion is presence-plus-nonempty, not score.

### Flakiness policy (resolved decision)

Live web search is inherently non-deterministic. **Smoke tests that depend on web search are permitted to be flaky.** Policy:

1. The test runner retries failed smoke tests **once** automatically.
2. A test that fails on both attempts is a red flag, not a hard CI failure — CI surfaces it as a warning and links to the log, but does not block merges of unrelated PRs.
3. Tests that run twice and flip (once fail, once pass) are tracked in `tests/flakiness.jsonl` so we can spot a test that has degraded to worthless.
4. For the historical live-search test specifically, the `known_details` keyword list is **intentionally generous** (≥2 hits out of 7+ listed) so ordinary web-search result drift does not fail it. The test exists to catch *gross* failure — e.g., the research command returns an empty file, or returns fabricated sources without citations, or ignores the forced URLs.
5. Determinism is a non-goal for live-search behaviour, because our production users will hit the same drift. If the test is reliable against drift, our users will be too.

---

## 13. PR sequence

Each PR starts in a fresh Claude Code session. Each reads this file + `STATE.md` at start, updates `STATE.md` at end.

### PR 1 — foundation: repo layout, project.yaml, housekeeping CLI
**Goal:** turn the single-book repo into a series-aware scaffold, no LLM calls added or removed yet.
**Scope:**
- Create `src/autonovel/` Python package, `pyproject.toml` setup, console_scripts entry for `autonovel`.
- Implement `autonovel new-series`, `new-book`, `status`, `doctor`, `version`.
- Move existing templates to `shared/` and `books/<name>/` layout.
- Add `project.yaml` template, chapter frontmatter schema doc.
- Write Tier-1 deterministic tests for housekeeping.
- **Delete** nothing yet.
**Acceptance:** `pytest tests/deterministic` passes. `autonovel new-series demo && autonovel new-book one --series demo` produces the target tree. Existing Python generators still run unchanged on the old layout via a compat shim.
**Human gate:** yes, reviews directory layout and project.yaml fields.

### PR 2 — first command + installer adapter (Claude Code only)
**Goal:** prove the end-to-end pattern works for one command on one runtime.
**Scope:**
- Write `commands/draft.md` with full frontmatter contract.
- Write `src/autonovel/adapters/base.py` and `claude_code.py`.
- Implement `autonovel install --only claude` and `autonovel uninstall`.
- Write Tier-1 adapter tests (golden-file).
- Write Tier-2 contract tests for `draft.md`.
- Write Tier-3 smoke test invoking `/autonovel:draft 1 --book tiny-inquisitor` against `tiny-series-historical`.
**Acceptance:** after `npx autonovel install --only claude`, opening Claude Code in a series folder and running `/autonovel:draft 1 --book inquisitor` produces a valid chapter file. Tier-1 and Tier-2 green in CI. Tier-3 green on manual invoke.
**Human gate:** yes, this is the architecture-defining PR.

### PR 3 — foundation commands
**Goal:** replace `gen_world.py`, `gen_characters.py`, `gen_outline.py`, `voice_fingerprint.py`, `gen_canon.py`, `seed.py`.
**Scope:** one markdown command per generator. De-Bells the prompts; read from `project.yaml`. Tier-1, Tier-2, Tier-3 tests for each. Delete the replaced Python files.
**Acceptance:** a brand-new series can reach "ready to draft" using only `/autonovel:*` commands. Tier-3 smoke green on Claude Code.
**Human gate:** optional; auto-merge on green is fine.

### PR 4 — evaluation and revision commands
**Goal:** replace `evaluate.py` (keep mechanical bits as a pure Python module in `src/autonovel/mechanical/`), `adversarial_edit.py`, `apply_cuts.py`, `reader_panel.py`, `review.py`, `gen_brief.py`, `gen_revision.py`, `compare_chapters.py`.
**Scope:** one markdown command per. Extract regex-only logic into a small pure-Python module the LLM commands can invoke via shell. Tier-4 regression tests against `bells-reference` for `/autonovel:evaluate`. Delete replaced Python.
**Acceptance:** a drafted book can complete one revision cycle using only commands. Tier-4 regression within 0.5 of reference.
**Human gate:** optional.

### PR 5 — research and period guardrails
**Goal:** add the features historical fiction needs.
**Scope:**
- `commands/research.md` with forced-URL + web-search protocol.
- `commands/check-anachronism.md`.
- `commands/promote-canon.md`.
- `shared/period_bans.txt` seeded for 1400-1600 Europe.
- `shared/sources.bib` template.
- Tier-3 historical live-search test (the one spec'd in section 12).
**Acceptance:** the Venetian-apothecary smoke test passes. User can drop a URL into `sources.yaml` and research consults it.
**Human gate:** optional.

### PR 6 — orchestrator and multi-book wiring
**Goal:** replace `run_pipeline.py`; add story-time context loader and `events.md`.
**Scope:**
- `commands/run-pipeline.md`.
- Context loader helper in `src/autonovel/context_loader.py` that returns the right files given a book/chapter pair (respecting story_time).
- `shared/events.md` schema + validator in `src/autonovel/validators/`.
- Tier-3 multi-book test: two books, interleaved story times, draft both and verify neither contradicts the other's canonical events.
**Acceptance:** `/autonovel:run-pipeline --books a,b,c` runs. Delete `run_pipeline.py`.
**Human gate:** optional.

### PR 7 — export: art, covers, audiobook, typeset, landing
**Goal:** port every export feature from the current Python tree into commands, and improve them.
**Scope:**
- `commands/art-*.md` (style, directions, curate, pick, ornaments-all, vectorize).
- `commands/cover-composite.md`, `commands/cover-print.md`.
- `commands/audiobook-*.md` (script, voices, generate, assemble).
- `commands/typeset.md` (PDF + ePub from one command; keeps `typeset/novel.tex`, `typeset/epub_*` as templates).
- `commands/landing.md`.
- `commands/package.md` — end-to-end release builder.
- **Improvements over current implementation:**
  - Art: per-chapter ornament prompting now references chapter content (current implementation uses one generic style); multi-provider support (fal.ai as default, adapter layer so users can drop in other image models).
  - Cover: output matrix (KDP, Lulu, Amazon thumbnail, social cards) from one command; spine-width auto-calculator that reads trim size + page count + paper stock.
  - Audiobook: multi-take per line with best-take selection via an LLM listener pass; chapter-level concat with proper chapter marks (m4b where possible); emotion/tone tags in the script JSON.
  - Landing: responsive default template; og:image and twitter:card metadata; structured-data markup; optional multi-book series navigation.
- Tier-1 tests for mechanical bits (spine-width calc, script parser, chapter-mark stitching).
- Tier-3 smoke tests for each command — these are expensive (image gen, TTS) so they run on manual invoke only, not CI.
- Third-party API keys (`FAL_KEY`, `ELEVENLABS_API_KEY`) remain optional and documented.
**Acceptance:** a drafted+revised book can produce PDF + ePub + cover + audiobook + landing page via `/autonovel:package --book <name>`. Every feature in the current Python implementation has a command equivalent or is explicitly explained as removed in the release notes.
**Human gate:** optional.

### PR 8 — Codex and Gemini adapters
**Goal:** make the other two runtimes work.
**Scope:** `adapters/codex.py` and `adapters/gemini.py`. Tool-name translation table. Per-runtime golden-file tests. Run one smoke test end-to-end on each runtime to validate.
**Acceptance:** `npm install -g autonovel && autonovel install` (no flag) installs to all detected runtimes. Smoke suite green on Claude Code; spot-check green on Codex and Gemini.
**Human gate:** optional.

### PR 9 — documentation, full genre fixture suite, publish
**Goal:** ship.
**Scope:**
- Complete all eight shipped genre fixtures under `tests/fixtures/` with their per-genre smoke tests (§12).
- `autonovel test-fixture new|list|run` housekeeping commands (§12a).
- `docs/commands.md`, `docs/series-layout.md`, `docs/multi-book.md`, `docs/testing.md`, `docs/adding-a-genre-fixture.md`.
- `docs/writing-a-historical-series.md` — end-to-end walkthrough on a trimmed version of the planned Renaissance series.
- Move `PIPELINE.md` to `docs/pipeline-history.md`.
- Rewrite `README.md` with both install paths (npm -g and npx) documented equally.
- Update `CLAUDE.md`; symlink `AGENTS.md` and `GEMINI.md`.
- Delete any remaining Python legacy.
- Tag `v0.1.0` and publish to npm (supporting both `npx autonovel` and `npm install -g autonovel`).
**Acceptance:** a new user can install and run a worked example in under 10 minutes using only the README. All eight genre fixtures run under `pytest -m smoke` when API keys are configured.
**Human gate:** yes, final review before publish.

---

## 14. `STATE.md` template (created at start of PR 1)

```markdown
# autonovel rewrite state

**Last updated:** YYYY-MM-DD by PR N

## Completed
- [x] PR 1: layout + housekeeping
- [ ] PR 2: first command + Claude adapter
...

## In progress
- PR N: <title>
  - Current step: <step>
  - Files touched this session: <list>
  - Next action: <what a fresh session should do first>

## Blockers
- none

## Decisions log (append-only)
- 2026-04-24: Use `/autonovel:` namespace (conflicts with `/gpd:` avoided).
- 2026-04-24: Model tiers abstract over provider; adapters pick specific models.
- ...

## Tests last known green
- Tier 1: YYYY-MM-DD
- Tier 2: YYYY-MM-DD
- Tier 3 (historical smoke): YYYY-MM-DD
- Tier 4 (Bells regression): YYYY-MM-DD

## Open questions
- <any unresolved architectural call>
```

---

## 15. Autonomous-run setup (optional)

If you want PRs 3-7 to run without human intervention:

1. Enable branch protection on `master` with "require CI green" on Tier-1+2.
2. In `.github/workflows/rewrite.yml`, have CI also run Tier-3 smoke on Claude Code for PR branches.
3. Configure GitHub's auto-merge for PRs labelled `rewrite:auto`.
4. Use `/loop <<autonomous-loop-dynamic>>` in Claude Code with a prompt that says:
   > Read REWRITE-PLAN.md and STATE.md. Execute the next uncompleted PR from the sequence. On completion, commit, push, open a PR with the `rewrite:auto` label (for PRs 3-7) or `rewrite:human-gate` (for PRs 1, 2, 8), update STATE.md, stop.
5. Each fresh session is a fresh context window. The only state that survives is the repo itself plus `STATE.md`.
6. You check in at the human-gate PRs (1, 2, 8) to approve architecture and shipping.

Total human time across the rewrite: ~30 minutes at the 3 gates, plus spot-checks of auto-merged PRs if you like.

---

## 16. Context discipline rules for every session

1. At session start, read `REWRITE-PLAN.md` (this file) and `STATE.md`. Nothing else until you know which PR you are doing.
2. Do not re-read files that are already covered by the PR spec's acceptance criteria — trust the spec.
3. When you need to understand existing code to replace it, delegate to an Explore sub-agent with a specific question. Do not read files directly into main context unless you are editing them.
4. Delete replaced Python files in the same PR that replaces them. Never leave "old_*.py" around.
5. If context pressure hits, stop, update `STATE.md` with exact resume instructions, commit, and end the session. A fresh session picks up from `STATE.md`.
6. Prefer writing to reading. When unsure what a file should say, write the new version from spec and let Tier-1/Tier-2 tests tell you if you got it wrong — cheaper than re-reading the old one.

---

## 17. Model selection per command (frontmatter `model_tier`)

| Tier | Model on Claude Code | Extended thinking | Where used |
|---|---|---|---|
| heavy | `claude-opus-4-7` | on | gen-world, gen-characters, voice-discovery, review, run-pipeline orchestration, research synthesis |
| standard | `claude-sonnet-4-6` | off | draft, revise, evaluate, adversarial-edit, reader-panel, brief, gen-outline, gen-canon |
| light | `claude-haiku-4-5-20251001` | off | apply-cuts (mechanical), check-anachronism (mostly regex + light judge), promote-canon (interactive) |

Codex and Gemini adapters map tiers to the provider's closest equivalent. `project.yaml` can override the mapping for users who want GPT-5 as judge and Claude as writer, etc.

---

## 18. What gets deleted and when

| File | Deleted in | Replaced by |
|---|---|---|
| `seed.py` | PR 3 | `commands/new-series.md` (optional seed generator built into new-series) |
| `gen_world.py` | PR 3 | `commands/gen-world.md` |
| `gen_characters.py` | PR 3 | `commands/gen-characters.md` |
| `gen_outline.py`, `gen_outline_part2.py` | PR 3 | `commands/gen-outline.md` |
| `voice_fingerprint.py` | PR 3 | `commands/voice-discovery.md` |
| `gen_canon.py` | PR 3 | `commands/gen-canon.md` |
| `draft_chapter.py` | PR 2 | `commands/draft.md` |
| `run_drafts.py` | PR 6 | folded into `/autonovel:run-pipeline` |
| `evaluate.py` | PR 4 | `commands/evaluate.md` + `src/autonovel/mechanical/` |
| `adversarial_edit.py` | PR 4 | `commands/adversarial-edit.md` |
| `apply_cuts.py` | PR 4 | `commands/apply-cuts.md` |
| `reader_panel.py` | PR 4 | `commands/reader-panel.md` |
| `review.py` | PR 4 | `commands/review.md` |
| `gen_brief.py` | PR 4 | `commands/brief.md` |
| `gen_revision.py` | PR 4 | `commands/revise.md` |
| `compare_chapters.py` | PR 4 | folded into `/autonovel:evaluate --compare` |
| `build_outline.py`, `build_arc_summary.py` | PR 3 | folded into `/autonovel:gen-outline --from-chapters` |
| `run_pipeline.py` | PR 6 | `commands/run-pipeline.md` |
| `gen_art.py`, `gen_art_directions.py` | PR 7 | `commands/art-*.md` |
| `gen_cover_composite.py`, `gen_cover_print.py` | PR 7 | `commands/cover-composite.md`, `commands/cover-print.md` |
| `gen_audiobook_script.py`, `gen_audiobook.py` | PR 7 | `commands/audiobook-*.md` |
| `typeset/build_tex.py` | PR 7 | folded into `commands/typeset.md`; `typeset/novel.tex` and `typeset/epub_*` stay as templates |
| `landing/index.html` | PR 7 | `commands/landing.md` uses it as one of multiple templates |
| `PIPELINE.md` | PR 8 | moved to `docs/pipeline-history.md` |

Art, cover, audiobook, typeset, and landing-page generation are **all in scope** for the rewrite. PR 7 ports every feature currently in the repo and improves each. No features are dropped.

---

## 19. Risks and open questions

### Known risks
- **Runtime headless mode may change.** `claude -p` output format and `codex exec` arg shape are moving targets. The installer should pin supported runtime versions and fail loudly on mismatch.
- **Cost of Tier-3 smoke on every PR** could balloon. Default: smoke only on PRs touching a command file, only the affected genre fixture, only Claude Code.
- **Cross-book drafting races.** Two terminals drafting book A ch 5 and book B ch 3 simultaneously could both append to `shared/canon.md`. Mitigation: they append only to their own `books/<name>/pending_canon.md`; `promote-canon` is single-threaded.
- **Story-time loader blowup.** A book with 20 other-book chapters in scope per draft is a huge context. Budget the loader; truncate oldest first; summarize the rest.

### Resolved decisions (2026-04-24)
1. **Install paths:** both `npm install -g autonovel` and `npx autonovel` are supported first-class. README documents both equally. (Option A recommended for recurring use.)
2. **Live-search determinism:** accept flakiness. The historical smoke test retries once and tolerates ordinary web-search drift. See §12 "Flakiness policy" for the full rule set.
3. **Shipped genre fixtures:** eight — historical, sci-fi, literary, mystery, thriller, romance, fantasy, horror. Users can add more via `autonovel test-fixture new <name>` (§12a).
4. **Art / cover / audiobook / typeset / landing:** fully in scope, PR 7. Every existing feature ports with an upgrade — multi-provider art, output-matrix covers, multi-take audio, responsive landing, one-shot `/autonovel:package` bundler.

### Remaining open questions
- None at the plan level; all outstanding calls are implementation details the individual PRs resolve.

---

## 20. Runbook for humans

### To start the rewrite

```bash
# in a fresh Claude Code session, in the autonovel repo
/autonovel:something-not-yet-existing  # you don't have commands yet

# instead:
claude
> Read REWRITE-PLAN.md and STATE.md. Execute PR 1. Do not start PR 2.
```

### To resume mid-rewrite after a context reset

```bash
claude
> Read REWRITE-PLAN.md and STATE.md. Continue from the "In progress" section of STATE.md.
```

### To run a PR autonomously

```bash
# once the loop skill is configured
/loop <<autonomous-loop-dynamic>>
# prompt: "Execute the next uncompleted PR from REWRITE-PLAN.md."
```

### To check progress from your normal shell

```bash
autonovel status                    # once PR 1 ships
# or just:
cat STATE.md
```

---

---

## 21. Writer UX, context management, and resilience

This section covers three related needs:
1. The human writer should always know the standard next step, and how to get off the standard path for common side tasks (add a character, shorten a chapter, start a minor subplot).
2. All state must survive a `/clear`, a CLI exit, a power loss, an out-of-budget interruption, or the user switching runtimes mid-project.
3. Every destructive change must be reversible.

### 21.1 The `.autonovel/` working directory

Every series folder gets a hidden `.autonovel/` subfolder, added by `autonovel new-series`. It is the single source of truth for "what has this pipeline done here."

```
.autonovel/
  state.json                     # series-level progress snapshot
  in-progress.lock               # present only while a command is running
  last-action.json               # what just completed + standard next step
  command-log.jsonl              # append-only log of every invocation
  checkpoints/
    2026-04-24T15-30-00/         # one directory per change-set
      _manifest.json             # which files changed, command, reason
      books/inquisitor/chapters/ch_05.md.bak
      shared/canon.md.bak
  session-notes/
    2026-04-24_session1.md       # free-form "handoff" notes a session writes
```

This folder is **checked in to git** alongside the rest of the series — it is part of the project's state, not runtime junk. Only `in-progress.lock` is git-ignored (it is per-machine).

### 21.2 The command lifecycle — lock, write, record

Every `/autonovel:*` command that writes to disk follows the same lifecycle. This is enforced by a shared preamble and postamble the installer injects into every command body:

**Preamble (at start of command body):**
1. Resolve `--book` and `--series` arguments against `project.yaml`.
2. Check `.autonovel/in-progress.lock`. If present and the recorded PID is still running, refuse with "another command is in flight." If present but stale, offer to take it over.
3. Write a fresh `.autonovel/in-progress.lock` with PID, runtime, command, args, start time.
4. For every path listed in the command's `writes:` frontmatter, copy the current file (if any) into `.autonovel/checkpoints/<timestamp>/`.
5. Write the checkpoint `_manifest.json`.

**Postamble (at end of command body, success path):**
1. Delete `.autonovel/in-progress.lock`.
2. Compute the standard next step using the rules in §21.5.
3. Overwrite `.autonovel/last-action.json` with completion summary + next step.
4. Append a line to `.autonovel/command-log.jsonl`.
5. Emit the user-facing footer described in §21.5.

**Postamble (failure path):** leave the lock in place; mark status=interrupted in the lock file. Do not touch last-action.json.

Commands that never write to disk (status, next, sidequest, doctor) skip checkpointing but still log to command-log.jsonl.

### 21.3 Resuming from `/clear`, power loss, budget exhaustion, or manual exit

All three scenarios look identical to autonovel: next time a command is invoked, something is wrong on disk.

- **After `/clear`**: runtime memory is empty, disk is intact, no lock. Nothing to recover. A fresh `/autonovel:next` reads `last-action.json` and re-announces the standard next step. This is the happy path.
- **After power loss / kill -9 / runtime crash**: the lock file is still present. `/autonovel:resume` (and every command's preamble) detects the stale lock and offers three choices:
  - **Redo**: roll back from the checkpoint and re-run the interrupted command from scratch. Safe, because checkpoints are the pre-state snapshot.
  - **Keep partial**: clear the lock but leave any partially written files in place. User inspects and continues manually.
  - **Inspect**: show what was mid-flight and what would change, exit without doing anything.
- **After budget / rate-limit hit mid-command**: same as power loss. Lock remains; partial files may exist. Resume logic takes over.
- **After user switches runtime** (started in Claude Code, wants to continue in Codex): disk state is runtime-agnostic. `autonovel status` works from any shell. Commands behave identically. No special handling needed.

This mechanism is implemented in one shared helper used by every command; no command author has to reimplement it.

### 21.4 Rollback and checkpoints

`autonovel rollback` (housekeeping CLI, not a runtime command — should work even if runtimes are offline) lists recent checkpoints:

```
$ autonovel rollback
Recent checkpoints:
  [1]  2026-04-24 15:30  /autonovel:draft 5 --book inquisitor
       → books/inquisitor/chapters/ch_05.md (new)
       → books/inquisitor/pending_canon.md (appended)
  [2]  2026-04-24 14:12  /autonovel:evaluate --chapter 4 --book inquisitor
       → books/inquisitor/eval_logs/ch_04_2026-04-24.json (new)
  [3]  2026-04-24 11:08  /autonovel:revise 3 --book inquisitor
       → books/inquisitor/chapters/ch_03.md (rewritten)

Roll back to which? [1-3, 0=cancel]: _
```

Rollback restores the exact pre-state and leaves a new checkpoint recording the rollback itself (so you can un-rollback). Checkpoints older than N (default 20) are pruned automatically; a `--keep-forever` flag on a command pins a specific checkpoint.

Rollback is **file-level, not git-level**. It does not touch git. If the user commits between a command and a rollback, the rollback still works on files but leaves the repo in a state the user chose.

### 21.5 The "standard next step" contract

Every command body that writes to disk must, in its postamble, decide and emit a standard next step. The logic sits in a small helper the installer injects:

```
next_step(book, last_command) =
    if last_command was foundation work and foundation_score >= threshold:
        /autonovel:draft 1 --book <name>
    if last_command was draft N and score >= threshold:
        /autonovel:evaluate --chapter N --book <name>
    if last_command was evaluate N and score >= threshold:
        /autonovel:draft N+1 --book <name>
    if last_command was evaluate N and score < threshold:
        /autonovel:revise N --book <name>
    if all chapters are drafted and no revision cycle has run:
        /autonovel:adversarial-edit all --book <name>
    if adversarial cycle just finished:
        /autonovel:reader-panel --book <name>
    if reader panel just finished:
        /autonovel:brief --auto --book <name>
    if stopping conditions from §13 PR 4 are met:
        /autonovel:review --book <name>
    ...
```

The helper's full decision table lives in `src/autonovel/housekeeping/next_step.py` so it is tested (Tier 1) and editable in one place.

**Footer template** that every command emits at end of its user-facing output:

```markdown
---
**Done:** /autonovel:draft 5 --book inquisitor
**Wrote:** books/inquisitor/chapters/ch_05.md (3,214 words, score pending)
**Next:** /autonovel:evaluate --chapter 5 --book inquisitor
  *(standard path: evaluate the draft you just wrote)*

Other options (see full list with `/autonovel:sidequest`):
- Shorten this chapter: `/autonovel:shorten --chapter 5 --target-words 2800 --book inquisitor`
- Lengthen this chapter: `/autonovel:lengthen --chapter 5 --target-words 3800 --book inquisitor`
- Revise against a brief: `/autonovel:revise 5 --book inquisitor`
- Roll back this draft: `autonovel rollback`
```

This footer is the primary UX for "standard path forward." It is also the primary documentation — users learn the system by reading footers, not by reading docs.

### 21.6 `/autonovel:next` and `/autonovel:resume`

Two small navigation commands, both reading purely from `.autonovel/`.

- **`/autonovel:next [--book <name>]`** — prints the last action, the standard next step, and the top three sidequest alternatives. Read-only. Useful after `/clear`, after a break, or when the user is unsure.
- **`/autonovel:resume [--book <name>]`** — detects in-flight commands, offers redo / keep-partial / inspect as described in §21.3. Takes no destructive action without explicit confirmation.

### 21.7 `/autonovel:sidequest` — the menu of non-standard work

Interactive command. Lists every "off the standard path" operation grouped by theme, with a one-sentence description each. Selecting one runs the real command with guided arguments.

```
/autonovel:sidequest

Character work:
  1. Add a new character               → /autonovel:add-character
  2. Rename a character everywhere     → /autonovel:rename-character
  3. Deepen an existing character      → /autonovel:deepen-character

Chapter work:
  4. Shorten a chapter                 → /autonovel:shorten
  5. Lengthen a chapter                → /autonovel:lengthen
  6. Split a chapter into two          → /autonovel:split-chapter
  7. Merge two chapters                → /autonovel:merge-chapters
  8. Rewrite a chapter in a new voice  → /autonovel:revoice

Story work:
  9. Add a minor subplot                → /autonovel:add-subplot
  10. Add / harvest a foreshadowing    → /autonovel:foreshadow
  11. Reorder chapters                  → /autonovel:reorder
  12. Remove a chapter entirely         → /autonovel:remove-chapter

Research / consistency:
  13. Research a topic                  → /autonovel:research
  14. Recheck anachronisms              → /autonovel:check-anachronism
  15. Add or update a source            → /autonovel:add-source

Maintenance:
  16. Roll back recent changes          → autonovel rollback
  17. Reconcile state                   → autonovel doctor
  18. Show status                       → autonovel status

Select [1-18, 0=exit]:
```

Each entry in this menu is a real command with its own frontmatter contract, tests, and footer. The menu itself is just a dispatcher.

### 21.8 The sidequest commands (new entries for §4 command catalogue)

| Command | Purpose | Effect | Checkpoint? |
|---|---|---|---|
| `/autonovel:add-character` | Add a character to the cast; update characters.md; optionally insert into specific chapters | `shared/characters.md` grows; one entry added | yes |
| `/autonovel:rename-character --old X --new Y` | Global find/replace respecting word boundaries; update canon.md | every chapter and shared file | yes |
| `/autonovel:deepen-character <name>` | Add an unguarded moment the POV catches, via targeted brief + revise | one or two chapters rewritten | yes |
| `/autonovel:shorten --chapter N --target-words W` | Compression brief + revise; honors §13-PR4 "do not go below 1800w" rule | one chapter | yes |
| `/autonovel:lengthen --chapter N --target-words W` | Expansion brief + revise; targets physical accumulation / dread / silence | one chapter | yes |
| `/autonovel:split-chapter --chapter N` | Propose split points; rewrite as two; renumber subsequent chapters | many chapters | yes |
| `/autonovel:merge-chapters --chapters N,M` | Merge two adjacent chapters; renumber | many chapters | yes |
| `/autonovel:revoice <chapter>` | Apply a voice shift to one chapter only (for a different POV, or a register change) | one chapter | yes |
| `/autonovel:add-subplot` | Add a minor storyline: plant in one chapter, harvest in another; honors foreshadowing ledger | two to three chapters | yes |
| `/autonovel:foreshadow --plant N --payoff M --thread "..."` | Targeted plant + payoff insertion; updates ledger | two chapters + outline | yes |
| `/autonovel:reorder --from A --to B` | Move chapter; renumber; fix all internal cross-references | many chapters | yes |
| `/autonovel:remove-chapter <N>` | Delete; renumber; patch continuity | many chapters + outline | yes |
| `/autonovel:add-source <url-or-doi>` | Add to sources.bib + sources.yaml; optionally re-run research on affected canon | shared/sources.bib | yes |
| `/autonovel:next` | Read-only "where am I" | nothing | no |
| `/autonovel:resume` | Read-only until user picks an option | nothing by default | no |
| `/autonovel:sidequest` | Interactive dispatcher | nothing | no |

Design constraint: every sidequest command writes its changes as a single checkpoint. If you regret it, one `autonovel rollback` undoes the entire operation.

### 21.9 `autonovel status` — the always-visible dashboard

Housekeeping CLI, works from any shell without a runtime:

```
$ autonovel status
Series: renaissance-europe (1450-1550 Europe, historical-fiction)

Books:
  inquisitor     drafting    14/20 chapters     avg score 7.4
                 last action: /autonovel:draft 14 (2h ago)
                 next step:   /autonovel:evaluate --chapter 14 --book inquisitor

  apothecary     outlined    0/18 chapters      —
                 last action: /autonovel:gen-outline (yesterday)
                 next step:   /autonovel:draft 1 --book apothecary

  merchant       seed        0/0 chapters       —
                 last action: /autonovel:new-book (3 days ago)
                 next step:   /autonovel:gen-outline --book merchant

Shared: 247 canon entries, 34 events, 12 research notes, 8 pending canon entries to promote

Recent activity:
  15:30  draft 14 --book inquisitor       OK
  14:12  evaluate --chapter 13 …          OK (score 7.6)
  11:08  revise 3 --book inquisitor       OK

Open issues:
  books/inquisitor/pending_canon.md has 8 entries — run /autonovel:promote-canon
  books/apothecary/outline.md references E-047 which books/inquisitor/ch_12 also renders
    — these must stay consistent
```

No runtime required. No LLM call. Just filesystem reads.

### 21.10 Impact on the PR sequence

These additions fold into the existing PR sequence, not as an extra PR:

- **PR 1** gains: `.autonovel/` directory layout, lock/checkpoint helpers, `autonovel status`, `autonovel rollback`, `autonovel doctor`. The next-step decision table (pure Python). Tier-1 tests for all of the above.
- **PR 2** gains: preamble/postamble injection in the adapter so every command file gets the lock + checkpoint + footer behaviour automatically. The first command (`/autonovel:draft`) exercises this end-to-end. `/autonovel:next` and `/autonovel:resume` are written in this PR because they are tiny and validate the state file formats.
- **PR 3** gains: `/autonovel:sidequest` as a dispatcher, populated with the sidequest entries whose underlying commands exist so far.
- **PR 4** gains: `/autonovel:shorten`, `/autonovel:lengthen`, `/autonovel:split-chapter`, `/autonovel:merge-chapters`, `/autonovel:revoice`. (Natural fit — these are revision operations.)
- **PR 5** gains: `/autonovel:add-character`, `/autonovel:deepen-character`, `/autonovel:add-subplot`, `/autonovel:foreshadow`, `/autonovel:rename-character`, `/autonovel:add-source`. (Natural fit — these are research- and structure-adjacent.)
- **PR 6** gains: `/autonovel:reorder`, `/autonovel:remove-chapter`. (Needs the multi-book / story-time machinery already in PR 6.)
- **PR 8** gains: the "standard next step" convention is the README's primary how-it-works explanation; doc work grows accordingly.

Net change: no extra PR. Each existing PR does a bit more. The biggest pickup is in PR 1 (infrastructure) and PR 4-5 (sidequest commands).

### 21.11 What the user experience looks like end-to-end

First session on a new series:

```
$ autonovel new-series renaissance-europe
Created renaissance-europe/
Next: cd renaissance-europe && autonovel new-book inquisitor

$ cd renaissance-europe
$ autonovel new-book inquisitor --pov Tommaso
Created books/inquisitor/
Edit books/inquisitor/seed.txt to describe what this book is about.
Next: open the folder in your runtime and run /autonovel:gen-world

$ claude .
> /autonovel:gen-world
[... Claude Code reads files, writes shared/world.md ...]
---
**Done:** /autonovel:gen-world
**Wrote:** shared/world.md (3,840 words)
**Next:** /autonovel:gen-characters
  *(standard path: characters depend on world)*

Other options:
- Research a topic first: /autonovel:research <topic>
- Regenerate with different emphasis: /autonovel:gen-world --regenerate
- Roll back: autonovel rollback
```

Six hours later the laptop dies. User comes back:

```
$ cd renaissance-europe
$ autonovel status
Series: renaissance-europe
Books: inquisitor (foundation in progress)
Last action: /autonovel:draft 3 --book inquisitor (INTERRUPTED 3h ago)
  A lock file is present. Run `autonovel resume` or /autonovel:resume inside a runtime.

$ autonovel resume
Previous command did not complete: /autonovel:draft 3 --book inquisitor
Partial output: books/inquisitor/chapters/ch_03.md (142 words — clearly incomplete)
Options:
  [1] Redo from scratch (recommended; checkpoint will be restored first)
  [2] Keep partial and continue manually
  [3] Inspect and decide later
Choice: _
```

Writer wants to add a new character mid-drafting:

```
> /autonovel:sidequest
[... menu ...]
Select: 1
Character name: Benedetta the copyist
Role in the story: passes documents between Tommaso and the archbishop
Introduced starting: chapter 8
POV: no
[... Claude Code updates shared/characters.md, adds candidate canon,
     suggests which chapters should reference her, all in one checkpoint ...]
---
**Done:** /autonovel:add-character Benedetta
**Wrote:** shared/characters.md (+ Benedetta entry), books/inquisitor/pending_canon.md (+3)
**Next:** /autonovel:revise 8 --book inquisitor --brief "introduce Benedetta per characters.md"
  *(standard path: weave the new character into her introduction chapter)*

Other options:
- Skip weaving for now: /autonovel:next (resume prior path)
- Roll back: autonovel rollback
```

This is the UX we are committing to.

### 21.12 Tests that protect the resilience features

New Tier-1 tests:

- **Lock lifecycle**: simulate preamble-start, kill, new invocation; assert stale-lock detection works.
- **Checkpoint round-trip**: write a file, checkpoint, modify, rollback, assert exact byte identity.
- **Next-step decision table**: parameterised tests over the full state-to-next-step mapping.
- **Command-log invariants**: after N simulated invocations, log has N entries, all have required fields, timestamps are monotonic.
- **Sidequest dispatcher**: every menu entry points to an existing command; every command in scope that isn't "standard" appears in the menu.

New Tier-3 smoke tests:

- **Resume from kill**: run `/autonovel:draft`, kill it, run `/autonovel:resume`, select redo, assert final state equals clean-draft final state.
- **Roll back a sidequest**: run `/autonovel:shorten`, compare word count, `autonovel rollback`, assert chapter restored exactly.
- **Footer presence**: after any command, assert `.autonovel/last-action.json` has `next_standard_step` populated.

---

*End of plan. `STATE.md` is created at the start of PR 1.*
