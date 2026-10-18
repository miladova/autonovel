# CLAUDE.md

This file provides guidance to AI CLI agents (Claude Code, OpenAI
Codex, Gemini CLI) when working *on this repo* — the autonovel
codebase itself, not a series produced with it. `AGENTS.md` and
`GEMINI.md` symlink here so all three runtimes read the same conventions.

> If you opened a series folder in your runtime by mistake and you
> want to write a novel, this is the wrong file. The series-side
> conventions live in the series's own `CLAUDE.md` (added by
> `autonovel new-series`); your runtime's `/autonovel:*` commands are
> the entry point.

## What this repo is

`autonovel` ships an autonomous novel-writing pipeline as a set of
markdown commands installed into an AI CLI runtime, plus a small
Python housekeeping CLI. The runtime owns the model, auth, and tool
calls; Python does scaffolding, validation, and mechanical regex
scoring only.

Authoritative specs:

- [`REWRITE-PLAN.md`](REWRITE-PLAN.md) — architecture and PR sequence.
- [`STATE.md`](STATE.md) — append-only decisions log + current Tier-1+2
  green count.
- [`ROADMAP.md`](ROADMAP.md) — forward-looking todos.
- [`docs/`](docs/) — user-facing documentation (commands, multi-book,
  testing, fixture authoring, the historical-series walkthrough).
- [`docs/pipeline-history.md`](docs/pipeline-history.md) — archived
  pre-rewrite spec from the Bells production run.

Reference docs consumed by writer/judge prompts (do not edit lightly —
they are the *prompt material*, not project documentation):

- [`CRAFT.md`](CRAFT.md), [`PROSE.md`](PROSE.md),
  [`ANTI-SLOP.md`](ANTI-SLOP.md), [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md),
  [`EDITING.md`](EDITING.md), [`DESIGN.md`](DESIGN.md).
  The repo-root files are symlinks; the source of truth is
  `src/autonovel/templates/series/shared/craft/`, which
  `autonovel new-series` copies into every series as `shared/craft/`
  and `autonovel refresh-templates` keeps current. Commands read them
  at `shared/craft/<name>` inside the series (a series session cannot
  see this repo). `PROSE.md` is the register-neutral mechanics
  reference, each rule traced to its source in the craft literature.
  `EDITING.md` is the study text of how professionals read, diagnose and
  fix a whole novel, which `/autonovel:developmental-edit` reads every
  run; its audit of this pipeline against it is
  [`docs/editorial-practice.md`](docs/editorial-practice.md).
  `DESIGN.md` is the author's half: how a book is designed before it is
  outlined (climax first, plants and payoffs, the rival, rehearsals,
  the design tests D1–D14), which `/autonovel:design` reads every run.

## Layout

```
autonovel/
  package.json              # npm shim entry — bin/autonovel.js → python -m autonovel.cli
  pyproject.toml            # Python package — `pipx install autonovel`
  bin/autonovel.js          # node wrapper that forwards to the Python CLI
  commands/                 # /autonovel:* command source — one md per command
  src/autonovel/            # housekeeping Python (CLI, adapters, validators, mechanical, templates)
  docs/                     # user-facing docs
  tests/
    deterministic/          # Tier 1 — frontmatter, mechanical, adapters, CLI
    contracts/              # Tier 2 — every reads:/writes: backed by command body
    smoke/                  # Tier 3 — opt-in, real runtime invocation
    fixtures/
      tiny-series-historical/    # the original
      tiny-series-{scifi,literary,mystery,thriller,romance,fantasy,horror}/
      bells-reference/           # Tier-4 regression — populates from autonovel/bells branch
  CRAFT.md, PROSE.md, ANTI-SLOP.md, ANTI-PATTERNS.md, EDITING.md, DESIGN.md   # symlinks → templates/series/shared/craft/
  CLAUDE.md, AGENTS.md, GEMINI.md   # AGENTS/GEMINI are symlinks to CLAUDE.md
```

## Common commands

Python dependency management uses standard pip/pipx. From a clone:

```bash
pip install -e .[test,export]            # editable + test + export deps
pytest tests/deterministic tests/contracts -q   # Tier 1 + 2 — fast, free, every commit
pytest tests/smoke -q -m smoke           # Tier 3 — costs money / subscription auth
autonovel test-fixture run <genre>       # one fixture's smoke test
```

Running the housekeeping CLI:

```bash
python -m autonovel.cli <subcommand>
# or, from npm:
npx autonovel <subcommand>
# or, after `pipx install autonovel`:
autonovel <subcommand>
```

Three are idempotent across the rewrite:

- `autonovel install` writes `/autonovel:*` command files into every
  detected runtime's expected path.
- `autonovel doctor` warns on missing external tools (tectonic,
  pandoc, potrace, ffmpeg, rsvg-convert, fontconfig); does not error.
- `autonovel test-fixture new <name>` scaffolds a new genre fixture +
  paired smoke-test stub (see `docs/adding-a-genre-fixture.md`).

## Architecture (one paragraph)

A `commands/<stem>.md` file is the source of truth for one
`/autonovel:<stem>` command. The file's YAML frontmatter declares its
model tier, its required generic tools, and the files it reads /
writes. An *adapter* (`src/autonovel/adapters/{claude_code,codex,gemini}.py`)
translates that frontmatter into the runtime's native shape and writes
the rendered file into the runtime's expected install path. The runtime
then handles the model, the auth, and the tool calls. A small Python
housekeeping CLI (`autonovel`) owns scaffolding, install/uninstall,
status/doctor, and rollback. No Python code calls an LLM.

## Conventions

### Generic tool names

Commands use generic tool names in their `allowed-tools` frontmatter
and in the body. Adapters translate to runtime-specific names:

| Generic | Claude Code | Codex CLI | Gemini CLI |
|---|---|---|---|
| `file_read` | `Read` | (identity) | `read_file` |
| `file_write` | `Write` | `write_file` | `write_file` |
| `bash` | `Bash` | `shell` | `run_shell_command` |
| `task` | `Task` | `spawn` | `run_agent` |
| `web_search` | `WebSearch` | `web_search` | `google_web_search` |
| `web_fetch` | `WebFetch` | `web_fetch` | `web_fetch` |

Tool-name translation in the body is **scoped to backticked tokens
only** (`` `task` `` → `` `spawn` ``, etc.). Word-boundary
substitution would mangle prose like *"is a creative task"* or
*"bash your seed.txt"*. Test fixtures contain both patterns.

### Preamble / postamble

Every command body opens with a hidden preamble and closes with a
hidden postamble that invoke `autonovel _begin` and `autonovel _end`.
These two hidden subcommands own:

- `.autonovel/in-progress.lock` (PID-locked; cross-book race
  mitigation).
- `.autonovel/checkpoints/<timestamp>/` (rollback target).
- `.autonovel/last-action.json` (input to `/autonovel:resume`).
- `.autonovel/command-log.jsonl` (one line per command run).

Command authors **never reimplement** lock / checkpoint / log logic —
this is the one-place-to-change contract for the whole pipeline.
PR-2 decisions log in `STATE.md` is the canonical reference.

### Auth policy

Subscription auth is primary. The smoke-test conftest strips
`ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from the subprocess env
before invoking `claude -p`, because Claude Code prefers API-key
billing when both modes are present and that defeats the *"free
against my subscription"* goal. Escape hatch:
`AUTONOVEL_SMOKE_USE_API_KEY=1`. New runtime commands don't need to
do anything — they run inside the user's subscription session.

### Model tiers

Every command file declares `model_tier: heavy | standard | light`.
Each adapter maps to the runtime's closest equivalent model.
Defaults on Claude Code: Opus 4.7 (heavy), Sonnet 4.6 (standard),
Haiku 4.5 (light). `project.yaml` overrides per-series. See
`REWRITE-PLAN.md` §17 for the full mapping table.

### Chapter renumbering, character renames

Chapter renumbering after `merge-chapters` / `remove-chapter` /
`reorder` runs **by script** (collision-safe `mv` / `git mv`),
never as an LLM rename loop. Same discipline for
`/autonovel:rename-character` (word-boundary `sed` with overlap
refusal — refuses `Ana` if `Anatolia` exists).

### Two flake-tolerant policies

- Live web search smoke tests are permitted to flake and auto-retry
  once (`tests/conftest.py`). A test that flips fail→pass logs to
  `tests/flakiness.jsonl`. See `REWRITE-PLAN.md` §12.4.
- Genre keyword lists in smoke tests are *intentionally generous*
  (≥2 hits out of 7+) so ordinary search/LLM drift does not fail
  them. Tests exist to catch *gross* failure.

## Gotchas (learned in the Bells production)

- **Don't over-compress.** Any chapter below ~1800 words becomes the
  new weakest. Sweet spot for compressed chapters is 2200–3000w.
- **`/autonovel:revise` overshoots** by ~30% — brief 3200w, expect
  3800–4200w.
- **Pacing ≈ 7 is a likely ceiling** for investigation-heavy plots;
  fixing one stretch just exposes the next. Stop after two rotations
  of "weakest chapter."
- **OVER-EXPLAIN (~32%) and REDUNDANT (~26%)** dominate adversarial
  cuts — prioritise these filters in `/autonovel:apply-cuts`.
- **The Stability Trap.** AI defaults to safe, round-edged endings;
  revisions should actively push toward irreversible change, cost,
  and mystery.

## Working in this repo

1. Read `REWRITE-PLAN.md` + `STATE.md` first. The decisions log in
   STATE.md is the project's working memory across sessions.
2. Don't re-read files already covered by a PR spec's acceptance
   criteria — trust the spec.
3. Commands and tests share a contract: every `reads:` / `writes:`
   path declared in frontmatter must appear in the body. Tier-2
   contract tests catch violations on every commit.
4. New commands inherit lock / checkpoint / log behaviour by following
   the preamble / postamble contract — do not reimplement.
5. Each PR ends by appending a decisions entry to `STATE.md` and
   updating the Tier-1+2 green count.
