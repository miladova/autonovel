# autonovel rewrite state

**Last updated:** 2026-04-24 by PR 9

## Completed
- [x] PR 1: layout + housekeeping
- [x] PR 2: first command + Claude adapter
- [x] PR 3: foundation commands
- [x] PR 4: evaluation + revision commands
- [x] PR 5: research + period guardrails
- [x] PR 6: orchestrator + multi-book wiring
- [x] PR 7: art, covers, audiobook, typeset, landing
- [x] PR 8: Codex + Gemini adapters
- [x] PR 9: docs + full genre fixtures + publish prep

## In progress
- none — PR 9 landed. Tier 1+2 456/456 green. `npm publish` itself
  is parked behind a human gate. Post-PR-9 author testing on
  Chromebook + WSL on Claude Max $200 surfaced 12 onboarding /
  reliability issues; 11 are fixed (commits 9207a55, 405930b,
  d5ceebb, 56d7734, 3851ac0, 79ebb99, 34098d0, plus this entry's
  lesson-recording commit), 1 is open. Full narrative in
  `docs/lessons-from-author-testing.md`; remaining open items in
  `FUTURE-TODOS.md`.

## Blockers
- none

## Decisions log (append-only)
- 2026-04-24: Use `/autonovel:` namespace (REWRITE-PLAN.md §4; avoids `/gpd:`).
- 2026-04-24: Model tiers abstract over provider; adapters pick specific models (§17).
- 2026-04-24 (PR 1): series/book scaffolder, `.autonovel/` lifecycle primitives,
  next-step decision table, chapter frontmatter validator, `autonovel` CLI.
- 2026-04-24 (PR 2): generic commands live under `commands/` at repo root and
  ship inside the wheel via `autonovel/commands/`. Adapter translates
  generic tool names (`file_read`, `file_write`, `task`, `web_search`,
  `web_fetch`, `bash`) to runtime-specific names. Claude Code adapter writes
  to `~/.claude/commands/autonovel/<stem>.md` by default; `--path` overrides.
- 2026-04-24 (PR 2): preamble/postamble injected by the adapter invokes two
  hidden housekeeping subcommands — `autonovel _begin` and `autonovel _end` —
  so command authors never reimplement lock / checkpoint / last-action / log.
  This is the one-place-to-change contract for the whole pipeline.
- 2026-04-24 (PR 2): `/autonovel:next` and `/autonovel:resume` shipped with
  the first command so the state-file formats (last-action.json,
  in-progress.lock) get exercised by real commands from day one.
- 2026-04-24 (PR 2): `draft_chapter.py` deleted (§18). `run_pipeline.py` and
  `run_drafts.py` still reference it by subprocess, which is accepted — both
  delete in PR 6.
- 2026-04-24 (PR 2 polish): smoke test gate relaxed to `claude`-on-PATH
  only; word-count window widened to [1800, 5000]; retry-once policy live
  via `tests/conftest.py` + `pytest-rerunfailures`. Pattern for PR 3+:
  future smoke tests just add `@pytest.mark.smoke` to inherit the retry.
- 2026-04-24 (auth policy, project-wide): **subscription auth is primary.**
  The smoke test subprocess strips `ANTHROPIC_API_KEY` from the env before
  invoking `claude -p` (because Claude Code prefers API-key billing when
  both modes are present, which would defeat the "free against my
  subscription" goal). Escape hatch: `AUTONOVEL_SMOKE_USE_API_KEY=1` on
  the developer's env preserves the key. New runtime commands don't need
  to do anything — they run inside the user's Claude Code session, which
  is subscription-auth automatically. Legacy Python scripts
  (`evaluate.py`, `review.py`, …) still call `api.anthropic.com` directly
  with `ANTHROPIC_API_KEY` — that's the pre-rewrite path, tracked for
  deletion in §18 across PRs 4-7.
- 2026-04-24 (PR 3): five foundation commands shipped — `gen-world`,
  `gen-characters`, `gen-outline`, `voice-discovery`, `gen-canon`. Each
  uses the PR 2 preamble/postamble contract unmodified; no new adapter
  work required. Model tiers: `gen-world`, `gen-characters`,
  `voice-discovery` → heavy (Opus-class creative drafting); `gen-outline`,
  `gen-canon` → standard (structured extraction from already-written
  Layer-4/3 material).
- 2026-04-24 (PR 3): `/autonovel:sidequest` dispatcher shipped as a
  read-only menu that points at real commands rather than invoking them
  (§21.7). Routing via a separate slash-command invocation preserves the
  target's own lock/checkpoint guarantees; menu grows per §21.10 as later
  PRs land revision/research sidequests.
- 2026-04-24 (PR 3): nine Python generators deleted per §18 — `seed.py`,
  `gen_world.py`, `gen_characters.py`, `gen_outline.py`,
  `gen_outline_part2.py`, `voice_fingerprint.py`, `gen_canon.py`,
  `build_outline.py`, `build_arc_summary.py`. `run_pipeline.py` still
  shells out to the first six by name; those references are accepted as
  dangling and delete with `run_pipeline.py` itself in PR 6.
- 2026-04-24 (PR 4): mechanical regex logic extracted into
  `src/autonovel/mechanical/` (`slop.py`, `cuts.py`). Commands shell out
  via `python -m autonovel.mechanical <slop|period-bans|apply-cuts>` so
  the deterministic half is out of the prompt and Tier-1 testable. The
  scoring surface (TIER1/2/3 word lists, fiction-AI-tells,
  telling-patterns, em-dash density, sentence-length CV, structural
  tics, and the penalty weighting) is copied verbatim from
  pre-rewrite `evaluate.py` — do not tune the weights without
  re-freezing `tests/fixtures/bells-reference/scores.json`.
- 2026-04-24 (PR 4): eight evaluation/revision commands shipped —
  `evaluate`, `adversarial-edit`, `apply-cuts`, `reader-panel`,
  `review`, `brief`, `revise`, plus `compare` folded into
  `/autonovel:evaluate --compare`. Model tiers: `apply-cuts` → light
  (no LLM, shells out); `brief` → standard; all others (drafting-class
  judgement) → heavy.
- 2026-04-24 (PR 4): five sidequest commands shipped (§21.10) — `shorten`,
  `lengthen`, `split-chapter`, `merge-chapters`, `revoice`. Each lands
  changes as a single checkpoint so `autonovel rollback` undoes the
  full operation. Chapter renumber logic in `split-chapter` and
  `merge-chapters` runs via `bash` with `mv`/`git mv` in collision-safe
  order, never as an LLM rename loop (CLAUDE.md gotcha: "Chapter
  renumbering after merges/deletes must be done by script, never
  hand-edited"). The sidequest menu grew from 11 to 23 entries.
- 2026-04-24 (PR 4): path-placeholder convention unified on
  `ch{chapter}.md` / `ch_{chapter}.md` / `ch{chapter}_cuts.json` in both
  frontmatter and body. The zero-padding is applied at runtime by the
  runtime — commands describe the padding in words rather than using
  `{chapter:02d}`, because the contract test (`_path_stem in body`)
  needs a substring match.
- 2026-04-24 (PR 4): eight Python generators deleted per §18 —
  `evaluate.py`, `adversarial_edit.py`, `apply_cuts.py`,
  `reader_panel.py`, `review.py`, `gen_brief.py`, `gen_revision.py`,
  `compare_chapters.py`. `run_pipeline.py` and `run_drafts.py` still
  reference them by subprocess; those references are accepted as
  dangling and delete with their callers in PR 6 (same policy as PR 3).
- 2026-04-24 (PR 5): nine commands shipped — `research`,
  `check-anachronism`, `promote-canon`, plus the six §21.10 PR-5
  sidequests `add-character`, `deepen-character`, `rename-character`,
  `add-subplot`, `foreshadow`, `add-source`. Model tiers: `research`,
  `deepen-character`, `add-subplot`, `foreshadow` → heavy (drafting-
  class rewrites); `check-anachronism`, `promote-canon`,
  `add-character`, `rename-character`, `add-source` → standard
  (structured edits / mechanical sweeps with light LLM judgment).
- 2026-04-24 (PR 5): `/autonovel:research` uses the generic
  `web_search` + `web_fetch` tools (translated by the adapter to
  `WebSearch` / `WebFetch` for Claude Code). Primary URLs in
  `shared/research/sources.yaml` are mandatory stops; citations use
  BibTeX shortnames resolved against `shared/sources.bib`. The
  Venetian-apothecary smoke test in `tests/smoke/test_historical_research.py`
  asserts file shape (sources section, ≥2 distinct citations, primary
  URL hit, period-detail keyword floor, uncertainty hedge, candidate
  canon entries) — not factual content, per §12.4 flakiness policy.
- 2026-04-24 (PR 5): `/autonovel:check-anachronism` is the two-pass
  guardrail — deterministic half reuses `python -m autonovel.mechanical
  period-bans`; semantic half is LLM overlay for concepts / mental
  frames / metaphors the word list cannot catch. Writes a JSON report
  under `edit_logs/`, never touches the chapter.
- 2026-04-24 (PR 5): `/autonovel:promote-canon` is the single entry
  point to `shared/canon.md`. `.autonovel/in-progress.lock` (from the
  preamble) gives §19 cross-book race mitigation; contradictions are
  never merged optimistically — they park under a `# Conflicts` header
  in `books/{book}/pending_canon.md` for manual resolution.
- 2026-04-24 (PR 5): `shared/period_bans.txt` template seeded for
  1400-1600 Europe (~90 entries spanning modern register, 19-20th
  century technology metaphors, modern institutional concepts,
  forensics, and managerial idioms). The existing fixture's smaller
  list is preserved to keep the PR-4 revision smoke tests green —
  expanding the fixture would require re-checking every seed paragraph
  against the new bans.
- 2026-04-24 (PR 5): `/autonovel:rename-character` script-based, not
  LLM-rename (CLAUDE.md: "Chapter renumbering ... must be done by
  script, never hand-edited" — same discipline applies to global
  rename). Word-boundary `sed`, three casings (Title/lower/UPPER);
  refuses when any target overlaps a longer word (e.g. `Ana` vs
  `Anatolia`) to prevent silent mangling.
- 2026-04-24 (PR 5): sidequest dispatcher grew from 23 to 32 entries,
  adding the PR-5 research + cast/thread section.
- 2026-04-24 (PR 6): `src/autonovel/context_loader.py` is the
  multi-book context resolver. Given `(book, chapter)` it returns a
  typed `ContextBundle` with `shared`, `book_files`,
  `sibling_chapters`, `events`, and `excluded_spoilers`. Spoiler rule:
  a sibling chapter is readable only if its `story_time` upper bound
  is ≤ the target chapter's `story_time` lower bound. Event rendering
  (a chapter appearing under `rendered_in` for one of this chapter's
  events) surfaces *additional* sibling chapters, but spoiler gating
  still dominates — a chapter that fails the story_time check stays
  excluded even if it renders the same event. Also exposed as a CLI
  (`python -m autonovel.context_loader --book X --chapter N
  --series-root …`) so `/autonovel:run-pipeline` can shell out for
  a JSON manifest before routing to `/autonovel:draft`.
- 2026-04-24 (PR 6): `src/autonovel/validators/events.py` parses
  `shared/events.md` into typed `Event` records (§8: id, title,
  date, location, present, canonical, rendered_in, book_constraints).
  The parser is forgiving (it returns every event it could
  identify) and emits a problems list rather than raising — the
  validator's job is to surface issues in a single report, not to
  fail-fast on the first bad line. `check_cross_consistency(events,
  project_books)` flags `rendered_in` rows that name books missing
  from `project.yaml`.
- 2026-04-24 (PR 6): three commands shipped — `run-pipeline`,
  `reorder`, `remove-chapter`. `/autonovel:run-pipeline` is an
  advisory orchestrator (model_tier: light, context_mode: series);
  every content mutation still goes through a sibling `/autonovel:*`
  command that owns its own lock + checkpoint + footer. Snapshot
  before/after `/autonovel:run-pipeline` must be byte-identical
  apart from `.autonovel/` bookkeeping — that is the contract. The
  reorder + remove-chapter sidequests follow the §21.8 discipline:
  chapter renumber runs via `bash` + `mv` in collision-safe order,
  never an LLM rename loop. Sidequest dispatcher grew from 32 to 35
  entries.
- 2026-04-24 (PR 6): deleted `run_pipeline.py` and `run_drafts.py`
  per §18. Dangling references from PR 3 and PR 4 (gen_world,
  gen_characters, evaluate, adversarial_edit, apply_cuts, reader_panel,
  review, gen_brief, gen_revision, compare_chapters) were to these
  two orchestrators and now resolve. Legacy doc references in
  README.md, WORKFLOW.md, PIPELINE.md, and CLAUDE.md are left
  untouched on purpose — REWRITE-PLAN §18 parks PIPELINE.md for PR 8
  and the README/CLAUDE rewrite for PR 9; editing them in PR 6 would
  sprawl the diff.
- 2026-04-24 (PR 7): fifteen export commands shipped —
  `art-style`, `art-directions`, `art-curate`, `art-pick`,
  `art-ornaments-all`, `art-vectorize`, `cover-composite`,
  `cover-print`, `audiobook-script`, `audiobook-voices`,
  `audiobook-generate`, `audiobook-assemble`, `typeset`, `landing`,
  `package`. Model tiers: creative briefs (`art-style`,
  `art-directions`) → heavy; structured / judgement prose
  (`art-curate`, `art-ornaments-all`, `audiobook-script`,
  `audiobook-generate`, `landing`) → standard; mechanical / PIL-only
  (`art-pick`, `art-vectorize`, `cover-composite`, `cover-print`,
  `audiobook-voices`, `audiobook-assemble`, `typeset`, `package`) →
  light. Sidequest dispatcher grew from 35 to 50 entries.
- 2026-04-24 (PR 7): four new `python -m autonovel.mechanical`
  subcommands exported — `spine-width` (cover canvas + spine calc
  from pages + paper stock + trim + bleed), `audio-validate` (shape
  + speaker-coverage check on parsed chapter scripts), `audio-chunk`
  (pack script segments into ElevenLabs-budget chunks with fallback
  voice resolution), `audio-marks` (cumulative chapter timestamps;
  optional `ffmetadata` output for m4b embedding), and `build-tex`
  (chapters_content.tex builder ported verbatim from
  `typeset/build_tex.py`). Each is pure-Python, writes JSON on
  stdout, and is Tier-1 tested (61 new tests across
  `test_mechanical_spine.py`, `_audio.py`, `_latex.py`).
- 2026-04-24 (PR 7): PIL-heavy cover rendering factored into
  `src/autonovel/export/cover.py` — `composite_cover` (e-book text
  overlay), `print_cover` (KDP/Lulu/IngramSpark wraparound with
  spine from `mechanical.spine.cover_spec`), and `thumbnail_matrix`
  (Amazon full-size, 800×1200 web, 400×600 social, 800×800 square).
  Commands shell out via `python3 -c "from autonovel.export.cover
  import ..."` rather than inlining the ~200-line PIL script into
  command bodies. The landing HTML renderer lives alongside at
  `src/autonovel/export/landing.py` with `@KEY@` substitution so the
  template survives being inside CSS and JSON-LD blocks.
- 2026-04-24 (PR 7): typeset templates genericised. The pre-rewrite
  `typeset/novel.tex` (Bells-specific) now uses `@TITLE@`,
  `@AUTHOR@`, `@SERIES_NAME@`, `@YEAR@` placeholders; `epub_*`
  templates likewise. Moved from repo root to
  `src/autonovel/templates/series/typeset/` so every new series gets
  a local copy at scaffold time. `landing/index.html` gave up its
  Bells content and moved to
  `src/autonovel/templates/series/landing/template.html`. The
  `new-series` scaffolder picks them up via the existing `_copy_tree`
  path — no new code.
- 2026-04-24 (PR 7): deleted `gen_art.py`, `gen_art_directions.py`,
  `gen_cover_composite.py`, `gen_cover_print.py`,
  `gen_audiobook_script.py`, `gen_audiobook.py`,
  `typeset/build_tex.py`, and `landing/index.html` per §18. The
  `typeset/` and `landing/` directories at repo root are now empty
  and have been removed; their content lives under
  `src/autonovel/templates/series/`. Legacy doc references in
  README.md, WORKFLOW.md, PIPELINE.md, CLAUDE.md that still mention
  the deleted scripts are left untouched on purpose — REWRITE-PLAN
  §18 parks the README/CLAUDE rewrite for PR 9.
- 2026-04-24 (PR 7): `audiobook_voices.json` at repo root kept as
  the example voice map (the same file the Bells production used).
  It's not read by any new command — `/autonovel:audiobook-voices`
  writes per-book voices at `books/{book}/audiobook/voices.yaml`.
  The root file can be deleted in PR 9 along with the README rewrite;
  leaving it in place for now so tooling users have a reference
  shape to compare against.
- 2026-04-24 (PR 7): Tier-3 smoke coverage is intentionally
  **one test**, not fifteen. `tests/smoke/test_typeset_smoke.py`
  exercises `/autonovel:typeset --book tiny-inquisitor --pdf-only`
  and asserts `chapters_content.tex` exists with drop caps + every
  chapter title, the copied `novel.tex` has placeholders
  substituted, and (only if `tectonic` is installed) the produced
  `novel.pdf` is ≥ 4 KB. Art / cover / audiobook commands need paid
  APIs (fal.ai, ElevenLabs) and are left as manual-invoke only; PR 9
  will document the manual path.
- 2026-04-24 (PR 8): two new adapters shipped — `CodexAdapter` and
  `GeminiAdapter`. `installer.load_adapter` now dispatches on
  `claude` / `codex` / `gemini`; `detect._candidates()` surfaces all
  three for the auto-install path. Tier 1 added 24 golden-file tests
  (`tests/deterministic/test_adapter_codex.py`,
  `test_adapter_gemini.py`); Tier 2 contract tests parametrise over
  every command unchanged. Total Tier 1+2: **440 passing**.
- 2026-04-24 (PR 8): REWRITE-PLAN §11 went stale between writing and
  implementation. Codex CLI 0.125 retired the `~/.codex/prompts/`
  slash-command convention and now uses skills
  (`~/.codex/skills/<name>/SKILL.md` with YAML frontmatter, same
  shape as Claude skills). The adapter installs to
  `~/.codex/skills/autonovel/<stem>/SKILL.md` so a single install
  marker (`autonovel/`) cleanly covers uninstall. Skill name is
  prefixed `autonovel-<stem>` to avoid collisions with user-installed
  skills sharing a stem. Per-skill model pinning is not yet supported
  by Codex — the intended tier and a suggested model name go into
  the SKILL.md `metadata` block as documentation.
- 2026-04-24 (PR 8): Gemini adapter targets
  `~/.gemini/commands/autonovel/<stem>.toml` per §11. Prompt body
  uses TOML literal triple-quoted strings (`'''…'''`) rather than
  basic strings, because command bodies contain LaTeX backslashes
  (e.g. art-vectorize) that would otherwise need escaping. The
  adapter raises if a body ever contains `'''` so the literal-string
  delimiter stays unambiguous; nothing in the current 48 commands
  trips it. `description` and `arg_hint` go through a single-line
  basic-string escaper (`\\` and `"` only).
- 2026-04-24 (PR 8): tool-name translation in body is intentionally
  scoped to backticked tokens only (`` `task` `` → `` `spawn` `` for
  Codex, `` `task` `` → `` `run_agent` `` for Gemini, etc.). Word-
  boundary substitution would mangle prose like "is a creative task"
  or "bash your seed.txt"; the fixture commands contain both
  patterns so this matters. Generic names that already match the
  target runtime's verb (`file_read` for Codex) are kept as identity.
- 2026-04-24 (PR 8): Tier-3 spot-check smoke tests added —
  `tests/smoke/test_codex_smoke.py` and `tests/smoke/test_gemini_smoke.py`.
  Each runs a `gen-canon`-shaped invocation against the
  `tiny-series-historical` fixture. Both auto-skip when the runtime
  binary is absent. The Codex test redirects `CODEX_HOME` into the
  test's `tmp_path` and copies the user's real `auth.json` over so
  subscription auth survives without polluting the global install.
  Gemini test installs project-local under `<series>/.gemini/commands/`.
- 2026-04-24 (PR 8): `PIPELINE.md` moved to `docs/pipeline-history.md`
  per §18. Stale references in README.md / WORKFLOW.md / CLAUDE.md
  are left untouched on purpose — REWRITE-PLAN §18 parks the
  README/CLAUDE rewrite for PR 9 to keep diffs small.
- 2026-04-24 (PR 7): external-tool dependency check folded into
  `autonovel doctor`. New `EXPORT_TOOLS` table maps each command's
  external CLI dependency (tectonic, pandoc, potrace, ffmpeg,
  rsvg-convert, fontconfig) to the slash-command that needs it and
  the OS install hint. Surfaces as WARNINGS (never PROBLEMS) so a
  user who only drafts and revises is never told their setup is
  broken because they don't have tectonic. Three new tests in
  `tests/deterministic/test_doctor.py` lock the contract: every
  reported line includes purpose + install hint, missing tools are
  warnings not problems, and the `export_tools=False` flag silences
  the whole pass for callers that don't care. Python image/audio
  deps (Pillow, pydub) move to a new `[export]` extras-require
  group; `.env.example` documents both keys (FAL_KEY,
  ELEVENLABS_API_KEY) and the OS install hints (apt + brew).
- 2026-04-24 (PR 9): seven new genre fixtures shipped under
  `tests/fixtures/tiny-series-{scifi,literary,mystery,thriller,romance,fantasy,horror}/`
  with paired smoke tests at `tests/smoke/test_<genre>_smoke.py`.
  Each test asserts a §12 genre-characteristic property
  (sci-fi: ≥3 hard-limit bullets in world.md and no `[citation needed]`
  placeholders; literary: ≥5 distinct voice-discovery trials;
  mystery: ≥3 red herrings + clue-per-act ledger;
  thriller: stakes-escalation per chapter + ≥1 page-turn hook;
  romance: four-beat coverage + HEA/HFN named;
  fantasy: every magic-system bullet has a cost/limit clause;
  horror: dread keyword + sensory-specifics per chapter).
  All seven auto-skip cleanly when `claude` is not on `$PATH`.
- 2026-04-24 (PR 9): `autonovel test-fixture new|list|run` shipped.
  Scaffolds a fixture series + paired smoke-test stub by walking up
  from cwd to the repo root (a directory carrying both
  `tests/fixtures/` and `tests/smoke/`). 11 new Tier-1 tests in
  `tests/deterministic/test_test_fixture.py` cover the layout,
  rejection of bad names, idempotency-failure on existing fixtures,
  list/has-smoke-test marking, and missing-smoke detection. Total
  Tier 1+2: **451 passing** (440 → 451).
- 2026-04-24 (PR 9): npm shape scaffolded — `package.json` declares
  the `autonovel` bin, `bin/autonovel.js` is a thin Node shim that
  forwards to `python -m autonovel.cli`. The shim picks `python3`
  then `python` from `$PATH`, tries `import autonovel`, and falls
  back to running against the bundled `src/` via `PYTHONPATH` for
  `npx autonovel ...` against an unprovisioned Python (otherwise
  prints a `pipx install autonovel` hint). Actual `npm publish` is
  deferred to a human gate (FUTURE-TODOS.md "Real `npm publish`
  flow").
- 2026-04-24 (PR 9): docs landed under `docs/` —
  `commands.md` (every `/autonovel:*` per tier+context-mode),
  `multi-book.md` (story-time gating, events ledger, promote-canon),
  `testing.md` (four tiers, auth policy, flakiness),
  `adding-a-genre-fixture.md` (§12a walkthrough),
  `writing-a-historical-series.md` (12-step end-to-end). README
  rewritten for the rewrite (npm + npx + pipx install paths;
  install requirements; doc index; subscription-auth guidance).
  CLAUDE.md rewritten as the agent-side conventions file; AGENTS.md
  and GEMINI.md symlink to it.
- 2026-04-29 (series-arc LLM-judge upgrade; FUTURE-TODOS
  Series-arc-LLM-judge entry): new `--phase series` mode in
  `commands/evaluate.md` scores arc *quality* across ≥2 books.
  Pairs with the structural `/autonovel:series-arc` scoreboard
  — helper provides evidence (cross-book cast, backwards
  story-time jumps, unresolved threads, arc_score), LLM scores
  quality across five dimensions: `series_question`,
  `early_setup_late_payoff`, `cross_book_character_growth`,
  `world_evolution_consistency`, `tonal_continuity`. Top-level
  outputs include `series_score`, `weakest_book`,
  `top_3_arc_revisions`, and the load-bearing
  `unresolved_thread_payoff_plan` array brief / revise act on.
  Eval log lands at `.autonovel/eval_logs/<ts>_series.json`
  (series-level, not per-book). evaluate.md frontmatter reads
  expanded to include `books/*/outline.md`,
  `books/*/voice.md`, `books/*/chapters/ch_*.summary.md`;
  writes adds `.autonovel/eval_logs/*.json`. 8 Tier-1
  regression locks pin contract surfaces. Tier 1+2: 1115 →
  1123.
- 2026-04-29 (period syntax-drift scanner; FUTURE-TODOS
  Period-register-extension entry): Flesch-Kincaid grade per
  chapter vs voice / seed / median-of-chapters baseline.
  Chapters whose absolute grade-delta exceeds `--threshold`
  (default 1.0) are flagged. Pure math — no curated register
  dictionaries, no vocabulary lists — so this scanner doesn't
  drift with the codebase's word lists. New helpers in
  `mechanical/period_register.py` (`flesch_kincaid_grade`,
  `_syllables_in_word`, `build_syntax_drift_report`,
  `render_syntax_drift_markdown`), CLI subcommand `autonovel
  mechanical syntax-drift`, slash-command
  `/autonovel:syntax-drift`. Review list, not a gate; LLM
  judge in `voice_adherence` scores. 18 Tier-1 tests + 5
  contract pickups. Tier 1+2: 1092 → 1115.
- 2026-04-29 (dialogue-mechanics extensions; FUTURE-TODOS
  Dialogue-extensions entry): three new detectors in
  `mechanical/dialogue.py` — action-beat-as-tag clusters (3+
  in 10-line window), softening qualifiers in short retorts
  (under-80-char dialogue with `maybe`/`kind of`/`a little`/
  etc.), un-tagged-dialogue clusters (≥3 consecutive un-tagged
  paragraphs). The originally-planned cast-count gate for the
  un-tagged check was reverted per
  `feedback_avoid_brittle_python.md`: the cap-token-count
  proxy broke on Unicode names + sentence-initial capitalised
  dialogue. Reported as review-list, not a gate. Curated word
  lists kept short (~25 action-beat verbs, ~13 softening
  qualifiers). Slash-command body disclaimer updated to name
  the candidate-generator scope. 11 new Tier-1 tests. Tier 1+2:
  1081 → 1092.
- 2026-04-29 (show-don't-tell LLM-judge upgrade; FUTURE-TODOS
  Show-don't-tell follow-up): `commands/evaluate.md`
  `--chapter` mode gains `show_dont_tell_ratio` dimension;
  `--full` mode gains `show_dont_tell_arc`. Body invokes the
  existing mechanical pre-flight scanner via `bash`,
  classifies each candidate as direct (bare proposition,
  unanchored), indirect (sensory/behavioural anchor), or
  hybrid (legitimate direct telling — interior summary,
  register-mark in close-third). Per-chapter
  `(indirect + hybrid) / total` ratio mapped to 0-10 with a
  raw-direct-count penalty. `worst_offenders` array surfaces
  top-5 direct lines with embodiment suggestions for revise.
  `--full` adds `tell_heavy_chapters` list (ratio < 0.6) for
  sweep targeting. Zero-candidates chapters score 9.0 (not
  10.0) to flag the suspicious case. 7 Tier-1 regression
  locks. Tier 1+2: 1074 → 1081.
- 2026-04-28 (token + cost tracking; FUTURE-TODOS Token+Cost
  entry): `command_log.LogEntry` gains optional fields book /
  model / tier / input_tokens / output_tokens /
  cache_read_tokens / cache_creation_tokens / cost_usd. Empty
  fields omitted from rendered JSON so historical entries stay
  readable. `autonovel _end` accepts `--tier` /
  `--input-tokens` / `--output-tokens` / `--cache-read-tokens`
  / `--cache-creation-tokens` / `--cost-usd` flags; postamble
  template (Claude adapter) instructs the runtime to forward
  whatever the session's usage report exposes.
  `lifecycle.end()` accepts a `usage: dict | None` and threads
  it through to `command_log.append`. New `autonovel cost` CLI
  subcommand + `src/autonovel/cost.py` helper roll up
  per-book / per-tier / per-command totals (markdown + JSON).
  Mechanical-only commands count as $0 runs and are surfaced
  separately from heavy/standard/light. 18 Tier-1 tests + 0
  contract pickups (no new slash-command — CLI-only). Tier
  1+2: 1056 → 1074.
- 2026-04-28 (research at the front of the foundation — final
  step; FUTURE-TODOS Research entry): the third sub-item closes
  out the multi-step shipment. `commands/gen-world.md` step 3a
  and `commands/gen-canon.md` step 2a now read every populated
  `shared/research/notes/*.md` as primary source of truth, cite
  slug provenance in the world bible's Sources section, surface
  a one-line nudge to run `/autonovel:research --from-seed`
  when a period project has no research notes, and (gen-canon)
  preserve the `[research:<slug>]` citation tag through to
  canon bullets so promote-canon's tagged-survives-untagged
  conflict resolution stays correct (research entries beat
  draft-derived contradictions). New `tests/deterministic/
  test_research_at_front.py` adds 7 regression locks covering
  reads-declarations, body mentions, recovery-path nudges, and
  tag preservation. Tier 1+2: 1049 → 1056.
- 2026-04-28 (show-don't-tell pre-flight scanner; FUTURE-TODOS
  show-dont-tell entry): new helper
  `src/autonovel/mechanical/show_dont_tell.py` + slash-command
  `/autonovel:show-dont-tell` cast a wider net than the existing
  slop regex. Four pattern families: emotion-state
  (`<X> was/felt/seemed <emotion>` against ~50-word curated
  emotion list), interiority verbs (`knew`/`realised`/`thought`
  /`believed`/`wondered`/`hoped`/`feared`/`wished`/…),
  perception filters (`<Y> looked/sounded <adverb>` against
  curated filter-adverb list), narrator labels (`It was
  <emotion>`, `There was <emotion>`). Per-chapter table + per-
  line hits with snippets + density-per-1000 column. CLI
  subcommand `autonovel mechanical show-dont-tell`. The LLM-
  judge ratio scoring upgrade (direct/indirect/hybrid
  classification) is queued separately as a follow-up. 18
  Tier-1 tests + 5 contract pickups. Tier 1+2: 1026 → 1049.
- 2026-04-28 (series-arc score; FUTURE-TODOS series-arc entry):
  new helper `src/autonovel/mechanical/series_arc.py` + slash-
  command `/autonovel:series-arc` cross-book scoreboard for
  series with ≥2 books. Per-book completion (summary / eval /
  above-threshold + earliest/latest story_time), cross-book
  cast (characters in ≥2 books), backwards story-time jumps
  (chapters where story_time regresses — legitimate for
  flashbacks), unresolved threads (Threads opened with no
  Threads closed substring match later), composite arc score
  0-10 blending coverage + above-threshold fraction +
  story-time discipline penalty + unresolved-thread penalty.
  CLI subcommand `autonovel mechanical series-arc
  <series_root>`. LLM-judge upgrade for arc *quality* still
  queued. 16 Tier-1 tests + 5 contract pickups. Tier 1+2:
  1005 → 1026.
- 2026-04-28 (edit-imported manuscript mode Phase 1; FUTURE-TODOS
  edit-imported entry): new `autonovel import-book <name> --from
  <path>` CLI subcommand and `/autonovel:import-book` slash-
  command. Splits a directory of `*.md` files (one chapter per
  file) OR a single combined manuscript (split on `^# `, fallback
  `^## `, fallback whole file). `--split-on '<regex>'` overrides.
  Strips pre-existing frontmatter, writes autonovel-shape
  `ch_NN.md` with `status: imported` + `imported_from:` for
  audit, flips `project.yaml :: books[].mode` to
  `edit-imported`. New `BookEntry.mode` field (default `draft`,
  omitted from YAML to keep existing files clean).
  `commands/draft.md` step 1a refuses to overwrite an
  edit-imported book without `--force`. Helper at
  `src/autonovel/import_book.py`. Phase 2 (foundation reverse-
  engineering from prose) still queued. 26 Tier-1 tests +
  contract pickups. Tier 1+2: 974 → 1005.
- 2026-04-28 (quality scanners — dialogue + period-register +
  pov-bleed): three pure-mechanical pre-flight scanners. All
  read-only, light-tier, run in milliseconds.
  (1) `mechanical/dialogue.py` flags adverb-heavy speech tags
  (`said quietly`), said-bookisms (`exclaimed`, `murmured`,
  `whispered`, …), and stutters (same non-said verb 3+ times in
  a 10-line window). Per-chapter counts + per-line snippets.
  Slash-command `/autonovel:dialogue`. 16 Tier-1 tests.
  (2) `mechanical/period_register.py` rolls the existing
  `slop.period_ban_hits` scanner across every chapter, emits
  per-chapter table + worst-offenders ranking. Slash-command
  `/autonovel:period-register`. 16 Tier-1 tests covering bans
  loading (comments / blanks), word-boundary matching,
  frontmatter strip, summary aggregation, render shapes, CLI.
  (3) `mechanical/pov_bleed.py` flags lines where a cast member
  who is NOT the chapter's POV is named with an interiority
  verb (`thought`, `felt`, `knew`, `realised`, `wondered`, …)
  or possessive interiority (`Niccolò's mind`, `Lucia's
  heart`). Reads `shared/characters.md` for cast (bullet or
  heading form). Output is a review list, not a gate. Slash-
  command `/autonovel:pov-bleed`. 19 Tier-1 tests.
  Doc sync in same commit per the keep-docs-in-sync rule:
  docs/commands.md (3 new rows), docs/operating-guide.md §0
  (3 new mechanical-helper rows), README.md (drafting/revision
  bucket gains the three pre-flight scanners), series-template
  CLAUDE.md "When in doubt" (3 new affordances). Tier 1+2:
  912 → 974.
- 2026-04-28 (reliability batch — drafter graceful-read +
  canon-vs-outline + `_begin` cwd banner + `--no-model-pin`):
  four small reliability fixes from the FUTURE-TODOS reliability
  group.
  (1) Drafter commands (draft / revise / draft-pass /
  revision-pass) gain explicit "Read-failure policy" preambles
  at the top of `<workflow>` — no retry on non-load-bearing
  reads, hard-stop only on revise's chapter-file read. Catches
  the 2026-04-25 retry-loop bug class.
  (2) `commands/evaluate.md` `--phase foundation` mode adds a
  new `canon_outline_consistency` dimension that emits a
  `canon_outline_conflicts` array naming every fact where canon
  and outline disagree.
  (3) `_cmd_begin` prints a `_begin: running from series root
  \`<name>\`` banner (or `(cwd: <relative>)` when launched from
  below the root) so wrong-cwd launches are visible up front.
  Two new Tier-1 tests.
  (4) New `autonovel install --no-model-pin` flag re-renders
  every command without the `model:` frontmatter field — recovery
  path for [1m]-session-model users whose per-command pin
  silently downshifts. ClaudeCodeAdapter.render gains
  `pin_model: bool = True`. Installer signature-inspects the
  adapter so Codex/Gemini stay no-op until they opt in. Three
  new Tier-1 tests. docs/troubleshooting.md gains both the
  "[1m] downshifting" entry and a tweak to the lock-flight
  recovery section. Tier 1+2: 907 → 912.
- 2026-04-28 (property-based tests via hypothesis; FUTURE-TODOS
  Property-Based-Tests entry): new
  `tests/deterministic/test_property_based.py` uses `hypothesis`
  (added under `[test]` extras in pyproject.toml) to generate
  random book layouts (chapter count 0-12, random POV/status/
  prose/score, summary/eval/motif/entity/pending-canon presence)
  and assert invariants across them: `iter_chapter_files` count
  equals chapter-count exactly (no `.summary.md` collisions),
  `_infer_phase` returns a known phase, `_next_step_for` always
  returns non-empty command + rationale with no unsubstituted
  placeholders, `enumerate_actions` priorities valid, summary /
  dashboard / entity-track / motif builders never crash on
  arbitrary layouts. Decision table tested independently of
  disk via PipelineState strategy. 10 properties × 25 examples
  = ~250 random layouts per run. docs/testing.md Tier-1 row
  updated. Tier 1+2: 897 → 907.
- 2026-04-28 (verify-writes auditor; FUTURE-TODOS Verify-Writes
  entry): postamble's `--wrote` flags are LLM self-reports — LLM
  can claim a write without invoking Write/Edit. New
  `checkpoints.verify_writes(cp, series_root, claimed)` returns
  a `WriteVerificationReport` with one item per claim and
  statuses created / modified / deleted / unchanged / missing /
  outside-checkpoint. `lifecycle.end` invokes it after lock
  release, surfaces `unchanged` and `missing` as warnings in
  the postamble footer (`⚠️ verify-writes:`) and records a
  one-line summary on the command-log entry's `note` field for
  audit. Paths with unresolved `{book}` placeholders or paths
  outside the checkpoint are classified `outside-checkpoint`
  (informational, not warnings). Doc sync in
  docs/troubleshooting.md. 13 new Tier-1 tests covering each
  status path + lifecycle integration + command-log audit
  trail. Tier 1+2: 884 → 897.
- 2026-04-28 (postamble compliance watchdog; FUTURE-TODOS
  Postamble Watchdog entry): `lock.acquire_with_takeover` gains
  `expire_after_seconds` parameter (default 30 min via
  `DEFAULT_LOCK_EXPIRE_SECONDS`). Any lock older than threshold
  is silently taken over at the next `_begin`, with the
  abandoned LockInfo surfaced via the existing
  `BeginResult.abandoned_lock` channel. Independent of PID
  liveness — catches the same-Claude-Code-session case where
  the LLM skipped `_end` (PID is still alive but the lock is
  stale anyway). Lock age comes from `started_at` ISO timestamp
  in the lock JSON, with mtime fallback when corrupted. New
  `is_expired(lock_path, max_age_seconds)` predicate.
  `expire_after_seconds=None` or `0` reverts to pre-2026-04-28
  PID-only behaviour. Doc sync in docs/troubleshooting.md
  "another command is already in flight" entry. 7 new Tier-1
  tests including end-to-end through `lifecycle.begin`. Tier
  1+2: 877 → 884.
- 2026-04-28 (structured summary queries; FUTURE-TODOS Summary
  Queries entry): new light-tier command `/autonovel:summaries
  [--book <name>] [--where '<expr>'] [--format markdown|json]`
  over a small mechanical query DSL. Supports `==/!=/<=/>=/</>`
  numeric/lexical compare on `pov`, `score`, `story_time`,
  `word_count`, `cast`, `plot`, `location`, `chapter`, `status`,
  plus `<field> contains <literal>`, `<field> in <num>..<num>`,
  and `and` / `or` / `not` / parenthesisation. Hand-written
  tokeniser + recursive-descent parser (no `eval()` — safer +
  user-friendly error messages naming the offending token).
  Helper at `src/autonovel/mechanical/summary_query.py` + CLI
  subcommand `autonovel mechanical summary-query <book_root>`.
  Distinct from `/autonovel:talk` by being free, scriptable,
  stable. 32 Tier-1 tests + 5 contract pickups. Tier 1+2:
  840 → 877.
- 2026-04-28 (per-book pacing/tension dashboard; FUTURE-TODOS
  Dashboard entry): new light-tier command `/autonovel:dashboard
  [--book <name>] [--threshold <float>] [--format markdown|json]`
  re-renders the latest `<ts>_full.json` eval log without firing
  another LLM evaluate. Augments with mechanical dimensions
  (cast size from summary, scene count from `***`/`---` markers,
  dialogue density from paragraph-opening `"`, motif density
  from motifs.md when present), ASCII sparklines (▁ to █) for
  score + tension, per-book aggregates (mean / median / range /
  stdev, longest sub-threshold streak), tension-drop alarms
  (≥3 consecutive declines) re-run from existing data. Helper
  at `src/autonovel/mechanical/dashboard.py` + CLI subcommand
  `autonovel mechanical dashboard <book_root>`. Output footer
  names per-column provenance. 32 Tier-1 tests + 4 contract
  auto-pickups. Tier 1+2: 803 → 840.
- 2026-04-28 (talk-with-the-book mode + named-entity tracker;
  FUTURE-TODOS Talk-mode entry): new heavy-tier command
  `/autonovel:talk --book <name> "<question or suggestion>"
  [--target <chapter>]`. Three modes classified from the user's
  prompt — **Q+A** (cites chapter+line, no edit pending),
  **Suggest-and-stage** (queues a structured turn in
  `books/{book}/briefs/conversation.md` for the next revise),
  **Mechanical+suggest** (calls `autonovel mechanical
  entity-track` first, then queues a cut-list grounded in the
  scan). The conversation log is append-only — each invocation
  reads the existing log + processes one new turn + appends a
  six-field block (`Question / suggestion`, `Mode`, `Target`,
  `Answer / suggestion`, `Status`). `commands/revise.md` step 3a
  reads the log and folds every queued turn with
  `Target: chapter <N>` into the brief; step 11 flips them to
  `Status: applied`. `commands/revision-pass.md` declares the
  same files in reads/writes so sweeps inherit the contract.
  New helper `src/autonovel/mechanical/entity_track.py` (the
  named-entity generalisation of `motifs.py`): per-book
  `entities.md` config first, fallback to `[shortname]` heads
  in `shared/canon.md`. CLI subcommand `autonovel mechanical
  entity-track <book_root>` and 13 Tier-1 tests covering the
  parse/scan/build/CLI paths. Tier 1+2: 785 → 803.
- 2026-04-28 (PDF page-header regression — two-bug fix; FUTURE-TODOS
  PDF entry): **Bug A**: `mechanical/latex.py::build_chapters_tex`
  read `lines[0]` of the post-frontmatter body as the chapter title;
  real chapter files (per `commands/draft.md`) have no `# Heading`
  line so `lines[0]` was the first sentence of prose, which became
  `\chapter{<sentence>}` and rendered as a large italic block at
  every chapter title page. Fix: new `_extract_chapter_title()`
  honours an optional `title:` frontmatter field, falls back to a
  real `# Heading` if present, otherwise emits empty `\chapter{}`
  so `\titleformat` prints `chapter <Roman>` alone. **Bug B**:
  even with the latex fix, in-flight series carry a stale
  `<series-root>/typeset/novel.tex` from before the 2026-04-25
  running-header fix (`autonovel install` doesn't refresh typeset
  templates). New `autonovel refresh-templates [--only typeset]
  [--dry-run]` housekeeping subcommand re-copies package templates
  over the live series, preserves local-only files, reports
  updated / unchanged / preserved-extra. Default is `typeset/`
  only. Operating-guide §3b updated. 11 new Tier-1 tests (2
  latex regression + 9 refresh-templates); Tier 1+2: 774 → 785.
- 2026-04-28 (per-chapter art prompts as first-class artifacts;
  FUTURE-TODOS #3): new light-tier command `/autonovel:art-prompts
  --book <name> [--chapters <range>] [--surface
  ornament|plate|scene-break] [--style lineart|full|symbolic]
  [--force]` writes one markdown prompt file per chapter at
  `books/{book}/art/prompts/ch{NN:02d}_{surface}.md` (sections:
  Motif, Rationale, Prompt, Universal constraints, Style, Source
  inputs). Built from outline + summary + visual_style.json +
  world cues — outline + summary name the turning point, which
  is a richer motif source than the first 400 words of prose.
  No image provider call. `commands/art-ornaments-all.md`
  updated: declares the prompts dir under `reads:`, prefers the
  authored `## Prompt` body verbatim when present, falls back to
  inline derivation when missing. Hand-edit target for the
  prompts; also the right input for a different generator
  (Midjourney, ComfyUI, a commissioned artist). 5 contract test
  auto-pickups for the new command; Tier 1+2: 769 → 774.
- 2026-04-28 (per-chapter motif tracker; FUTURE-TODOS #22): new
  mechanical helper `src/autonovel/mechanical/motifs.py` reads
  per-book `motifs.md` (bullet shape `- slug: kw1, kw2, kw3`),
  strips YAML frontmatter from each chapter before counting,
  matches keywords on word boundaries case-insensitively, emits
  a per-chapter markdown table (zero-hit cells `·`). Back-half
  drop warnings fire only when the motif was used at least once
  in the front half — silent for declared-but-never-used motifs
  (avoids noise). Books under 4 chapters skip warning logic.
  CLI subcommand `autonovel mechanical motifs <book_root>` and
  slash-command `/autonovel:motifs` (light tier, pure mechanical).
  17 new Tier-1 tests + 5 contract auto-pickups for the new
  command. Tier 1+2: 747 → 769.
- 2026-04-28 (pipx-isolated install Tier-3 test; FUTURE-TODOS #5.3):
  new file `tests/smoke/test_pipx_install.py` builds a wheel via
  `pipx install <repo>` against an isolated `PIPX_HOME` /
  `PIPX_BIN_DIR`, falling back to `python -m pipx` when the binary
  isn't on `$PATH`. Exercises the CLI surfaces that historically
  break under wheel packaging — `--help`, `_next-actions --help`,
  `mechanical slop --help`, `_promote-canon --help`, plus an
  end-to-end `new-series` + `doctor` round-trip (the strongest
  check for `templates/` packaging). Marked `smoke +
  pipx_install` so it can be excluded with
  `-m "smoke and not pipx_install"`. Adds a `pipx_install`
  marker registration to `pyproject.toml`.
- 2026-04-28 (multi-stage pipeline integration tests; FUTURE-TODOS
  #5.2): new file
  `tests/deterministic/test_integration_pipeline.py` walks the
  seams that unit-tested-in-isolation commands miss — foundation
  chain → first-draft → evaluate → advance/revise; low-score →
  revise → re-eval → advance; pending-canon gate (real
  `promote_canon.promote` round-trip releases the gate); situational
  `next_actions.enumerate_actions` shifts across pipeline stages;
  canonical pipeline action surfaces at the bottom of the
  `/autonovel:next` output; eval-score indexer resolves all three
  production naming conventions in a single test. 7 new Tier-1
  tests; Tier 1+2: 740 → 747.
- 2026-04-28 (realistic late-stage fixtures + lifecycle bug fix;
  FUTURE-TODOS #5.1): two new conftest fixtures —
  `mid_revision_book` (8 chapters, ch02+ch03 below threshold with
  briefs written, deliberately stale panel report) and
  `review_phase_book` (10 chapters above threshold, panel +
  review newer than every chapter). New test file
  `tests/deterministic/test_state_machine_realistic.py` runs
  `iter_chapter_files`, `_infer_phase`, `_next_step_for`, and
  `next_actions.enumerate_actions` against each shape (parametrised
  where invariants apply across all three). The realistic-fixture
  pass found a real bug in `lifecycle._last_eval_score`: glob
  `ch{NN}*.json` only matched plain `chNN_eval.json`, missing the
  timestamped `<ts>_chNN.json` form `evaluate.md` writes — so
  after `/autonovel:evaluate --chapter N` the next-step inference
  saw no score and looped on evaluate. Helper now delegates to
  `mechanical.chapter_summary._index_latest_per_chapter_eval` which
  already handles all three production naming conventions. 17 new
  Tier-1 tests. Tier 1+2: 723 → 740.
- 2026-04-28 (`/autonovel:next` made dynamic; FUTURE-TODOS #2):
  state-aware action enumerator at
  `src/autonovel/housekeeping/next_actions.py`. Inspects live
  filesystem for HIGH (pending-canon conflicts, chapter
  regressions ≥0.3 below prior best across timestamped /
  non-timestamped eval-log naming), MEDIUM (reader-panel +
  Opus-review staleness vs chapter mtimes; git backup state —
  no repo / no remote / uncommitted / unpushed), LOW (typeset
  `<book>_latest.pdf` staleness, missing book title or author,
  missing preface/introduction once ≥3 chapters drafted).
  Hidden subcommand `autonovel _next-actions [--book <name>]
  [--format human|json]` invokes it; `commands/next.md`
  rewrites the body to call the helper and print verbatim.
  Last-action.json's `next_standard_step` still surfaces — but
  as the lowest-priority "canonical pipeline next step" line at
  the bottom, so situational state always wins. 27 new Tier-1
  tests (`tests/deterministic/test_next_actions.py`) cover each
  per-book check, three git-backup states, canonical-action
  lookup with book filtering, the human render's priority
  grouping, and CLI round-trips. Tier 1+2: 696 → 723.
- 2026-04-26 (live-novel session, second wave): a long author-test
  day on the live novel surfaced concrete gaps; everything below
  shipped on master between 2026-04-25 PM and 2026-04-26 PM.
  Tier 1+2: 451 → 674.
  - **Quality dimensions for the brief→revise loop.** Four named
    ceiling fixes from CLAUDE.md's "production gotchas" list ship
    as a stack: (1) per-book Custom rubric in voice.md Part 3,
    read by evaluate / reader-panel / brief / draft / revise so
    book-specific scoring rules don't have to live in repo-shared
    command files; (2) per-character voice fingerprints in
    voice.md Part 4, auto-drafted by voice-discovery when the
    cast is ≥3, applied at every dialogue line and POV interiority;
    (3) `irreversible_change` evaluate dimension (per chapter) +
    `irreversible_change_arc` (whole book, with `cuttable_chapters`
    list), with brief.md's new `## Stability check` section
    forbidden from vague "raise stakes" prescriptions; (4) per-
    scene `beat_coverage` (goal / conflict / disaster-or-decision
    / consequence) backed by a new `autonovel mechanical scenes`
    helper, with brief.md's new `## Weak scenes` section naming
    the scene by index + opening line.
  - **voice.md upgrade path.** voice-discovery gains a `--upgrade`
    flag: preserves Parts 1+2 verbatim while appending Part 3
    placeholder and drafting Part 4. Safe rollout for existing
    books without re-running foundation.
  - **Late research → light integration.** Both /autonovel:brief
    and /autonovel:revision-pass gain `--enrich-with <research-
    notes-path>`. The brief reads the research notes,
    identifies which scenes the research is relevant to, adds an
    `## Enrichment from research` block with 1–2 specific period
    details per relevant scene and explicit "do NOT change plot,
    dialogue, voice, structure" guards. Chapters where the
    research doesn't fit get briefs without the block — the
    research is a brush, not a chisel.
  - **Per-chapter promote-canon in revision-pass.** Mirrors the
    aea1511 fix from draft-pass: each chapter's revise discoveries
    land in shared/canon.md before the next chapter's revise
    reads canon. Without it, an early-chapter revise that
    clarified a fact would re-introduce the inconsistency in
    chapter N+1.
  - **promote-canon postamble + conflict-block clarity.** Two
    user-confusion fixes shipped together. Conflict blocks
    written back to `pending_canon.md` now carry a mandatory
    HTML-comment instruction block at the top with three
    labelled resolution paths (accept / reject / both wrong),
    and each `## Conflict N` block names the file path the
    contradicting line lives in. Postamble names the next
    command explicitly per case (supersedure → revision-pass on
    the affected chapter; conflicts → open the pending file's
    instruction block; plain success → /autonovel:next).
    revision-pass is the default recommendation even for a
    single chapter — `revision-pass --chapters NN` does the
    whole loop in one command.
  - **Typeset bug-cluster fix.** Three bugs reported against
    the live PDF/ePub build: (1) ePub contaminated with summary
    file content (`ch_*.md` glob matched both prose and
    `ch_NN.summary.md`) — fixed by new `build_epub_md` helper
    enumerating via `iter_chapter_files()`; (2) PDF leaked YAML
    frontmatter into chapter prose because `latex.py` parsed
    `lines[0]` as the title — fixed by shared
    `strip_yaml_frontmatter()` helper; (3) running header
    cascaded into italicised chapter-prose-looking content —
    fixed by switching recto to `\textsc{Chapter \thechapter}`
    (Roman numeral, no chapter-title state). Plus replaced
    fragile `sed -i 's/@TITLE@/.../'` with Python helper
    `render_novel_tex` (sed silently breaks on titles
    containing `/`, `&`, `\`).
  - **Dated typeset filenames.** PDF/ePub now write
    `<book>_<YYYYMMDD>_<HHMM>.{pdf,epub}` per build (kept) plus
    `<book>_latest.{pdf,epub}` overwritten on each successful
    build. Failed tectonic runs leave the partial novel.pdf in
    place but do NOT update the timestamped or latest names.
  - **Title + author management.** New `/autonovel:title`
    command (light) with three modes: propose (5 title + 3
    author candidates from outline/seed), pick (commits a
    proposal), set (explicit values). `BookEntry` schema gains
    optional `title` / `subtitle` / `author` fields; series-
    level `author` field also added (book inherits from series).
    Display-resolution helpers `BookEntry.display_title()` /
    `display_author()` codify the fallback chain. Backwards-
    compatible: existing project.yaml files load cleanly.
  - **Front matter (preface + introduction).** New
    `/autonovel:introduction` command (heavy) with `--from
    user|auto|both`. Scaffolds `books/<book>/preface.md`
    (hand-authored — the AI explicitly does NOT fill the
    bracketed placeholders) and/or AI-generates
    `books/<book>/introduction.md` (~600–1200 words, essay-form,
    grounded in the book's themes; never reveals plot past the
    inciting incident). Both auto-included in typeset's PDF
    front matter (via new `build_front_matter_tex` helper +
    `\IfFileExists{front_matter.tex}` guard in novel.tex) and
    ePub front matter (pandoc invocation gains optional preface +
    introduction args).
  - **`/autonovel:chapter-summary` command.** Pure-mechanical
    one-line-per-chapter overview table: Ch | Date | POV | Sco |
    Words | Cast | Plot (with `**Location** —` prefix when the
    summary carries the new Location field). Pulls structured
    fields from chapter frontmatter, summary.md, and the latest
    eval log. The right tool for "which chapters happen in
    <date range>?" or "where does <character> appear?" — scan
    the relevant column instead of grepping prose.
  - **Chapter summary template gains `**Location:**`** as the
    first field, paired with Plot. Updated in draft.md step 12
    and summarize-chapter.md step 6. revise.md step 9 was the
    one path that drifted (had a stale inline list); commit
    3ba469a fixed it by replacing the inline list with a real
    DRY reference to draft step 12.
  - **Score-delta surfacing in revision-pass.** Per-chapter line
    now ends with `eval: <prev> → <new> (Δ ±X.X) | canon: +<P>`
    so writers see whether a revise actually moved the chapter
    or regressed it. End-of-sweep summary table column is
    `prev → new (Δ)`; headline assessment is required to call
    out regressions explicitly.
  - **Statusline: context-% from `data["context_window"]`.**
    Reads the nested object Claude Code sends (where the value
    is **remaining** %, converted to used at the read site).
    Five new schema paths covered (remaining_pct +
    percentage_remaining + percent_remaining + remaining_percentage
    + the legacy `usage.context_pct`). Plus an opt-in debug
    dump under `AUTONOVEL_STATUSLINE_DEBUG=1` writing
    `~/.autonovel-statusline-debug.log` for diagnosing future
    schema drift.
  - **Comprehensive series .gitignore + GitHub backup
    walkthrough** (operating-guide §3e.1). Excludes `.autonovel/
    checkpoints/`, audiobook MP3s, timestamped typeset builds;
    KEEPS `<book>_latest.{pdf,epub}` so a fresh `git clone` of
    a backup carries usable artefacts. Doc walkthrough explicitly
    notes that the autonovel codebase being on GitHub does NOT
    back up the user's book — the two are separate dirs.
  - **`requires-python` lowered 3.12 → 3.11.** Conservative pick
    at PR-1 time; audit confirmed no 3.12-only features in
    runtime source. Matches Debian 12 / WSL Ubuntu 22.04+ system
    Python. README install step gains a `pipx install '.[export]'
    --python python3.13` callout for users whose default `python3`
    is older.
  - **Operating-guide §0 "How the editing commands relate".**
    Single-most-asked confusion after a first-pass draft. Four-
    role table (atomic / sweep / whole-book reviewer /
    mechanical helper), per-command table, ASCII call-graph,
    explicit Q&A for the "I ran draft-pass --all then review
    then reader-panel — did I need to run brief?" case (no, but
    you're not done — your next move is revision-pass --chapters
    <flagged>). README's command list also gained the new
    commands (`chapter-summary`, `title`, `introduction`).
- 2026-04-25 (PR 9 author-testing follow-ups): twelve onboarding /
  reliability issues surfaced during a real first-run on Chromebook
  + WSL on Claude Max $200/month. Eleven fixed across commits
  `9207a55` (README rewrite), `405930b` (seed.txt template +
  time/effort guidance), `d5ceebb` (series-root callout),
  `56d7734` (series CLAUDE.md + AGENTS/GEMINI symlinks),
  `3851ac0` and `79ebb99` (1M-context docs and reframed to
  recommend `/extra-usage`), `79ebb99` again (next-step phase
  inferred from filesystem; postamble strengthened to **Mandatory**),
  `34098d0` (foundation chained in canonical order via
  `_foundation_gap`; populated-marker list extended to cover
  Seeded by / Filled by / Leave empty until then), and the present
  commit (lessons doc + cross-links). Open: per-command `model:`
  override on `[1m]` session models — see FUTURE-TODOS.md and the
  open question in `docs/lessons-from-author-testing.md` §8.
  Tier 1+2: 451 → 456.
- 2026-04-24 (PR 9 fixup): `audiobook_voices.json` had a second job
  beyond being a deletion target — it was the **shape reference** a
  user comparing against `voices.yaml` would consult. Restored as
  `src/autonovel/templates/book/audiobook/voices.yaml.example` so
  `autonovel new-book` ships an example next to where
  `/autonovel:audiobook-voices` writes the live file. The Bells voice
  metadata (`description`, `why` audit fields) is preserved verbatim;
  only the format changed JSON → YAML. `commands/audiobook-voices.md`
  now declares the example file under `reads:` and the body explains
  the shape contract for round-tripping.
- 2026-04-24 (PR 9): legacy root files deleted —
  `WORKFLOW.md` (replaced by `docs/writing-a-historical-series.md`),
  `audiobook_voices.json` (functional replacement: per-book
  `books/{book}/audiobook/voices.yaml` written by
  `/autonovel:audiobook-voices`; reference shape: see fixup entry
  above for `voices.yaml.example`),
  `main.py`, repo-root `world.md` / `characters.md` / `outline.md` /
  `canon.md` / `voice.md` / `MYSTERY.md` / `state.json` /
  `results.tsv` / `chapters/.gitkeep` (all pre-rewrite per-novel
  templates, now under `src/autonovel/templates/`). `program.md`
  moved to `docs/program-history.md` (parallel to PR-8's
  `docs/pipeline-history.md`); the one inline reference in
  `commands/gen-outline.md` was replaced by an inline 4-line
  Stability-Trap explanation. `.env.example` cleaned of legacy-Python
  language.
- 2026-04-24 (PR 9): forward-looking todos consolidated into
  `FUTURE-TODOS.md` (output writing quality, reader interest,
  maintenance, portability, testing). ROADMAP.md no longer doubles as
  a future-todos sink — that role moves to FUTURE-TODOS.md so a
  freshly cleared session has one obvious place to look.
- 2026-04-24 (PR 4): Tier-4 Bells regression harness scaffolded at
  `tests/fixtures/bells-reference/` (empty chapters dir + empty
  scores.json + populate-instructions README) and
  `tests/smoke/test_bells_regression.py` (marked `@pytest.mark.smoke
  @pytest.mark.regression`). Skips cleanly until the fixture is
  populated from the `autonovel/bells` branch. Two guards: (a) a
  deterministic `slop_penalty` drift check tolerant to ±0.1, and (b) an
  LLM-judged `overall_score` drift check tolerant to ±0.5 per §12.4.
  The LLM half carries an inline TODO (Bells → series bridge) so the
  harness stays explicitly skipped rather than silently passing.
- 2026-04-30 (519f3d7): `autonovel tui` Front matter tab renamed
  to "Front + back matter" and restructured to surface every
  front- and back-matter file the typeset pipeline weaves in
  (preface / introduction / glossary / appendix) with present-or-
  absent indicators and word counts. Stale-summary `⚠` legend
  added to the Chapters tab footer (chapter `.md` newer than its
  `.summary.md` — continuity-critical because downstream drafters
  read the summary, not the chapter, for rolling context). TOC-
  shows-chapter-names follow-up filed in FUTURE-TODOS (later
  shipped 7940cd0 + 67bd55a).
- 2026-04-30 (67bd55a): four user-facing landings in one commit —
  (1) `/autonovel:help` light-tier slash-command with topic mode
  (`art / foundation / drafting / revising / typeset / research /
  front-matter / sweeps / tui / cli / next-steps`); (2) chapter-
  name TOC support — `/autonovel:draft` step 11 generates a 2-6
  word evocative title at draft time written to YAML
  `title:`, new `/autonovel:extract-chapter-titles` LLM-backfill
  for legacy chapters, new mechanical `chapter-titles` inspector;
  (3) mixed-source appendix timeline (`📖`/`🏛️ referenced`/`🏛️
  context` rows from chapter summaries + research notes); (4)
  `autonovel doctor --install-missing` flag for one-command
  setup via the install-export-tools handoff. Doc-sync gaps in
  this commit caught by fbfe283 one commit later.
- 2026-04-30 (fbfe283): doc-sync catch-up for 67bd55a — README,
  series-template CLAUDE.md, and `docs/commands.md` mechanical
  section all gained the `/autonovel:help` and chapter-name TOC
  entries that should have shipped with the feature commit.
  Reinforced `feedback_keep_docs_in_sync.md` with the explicit
  five-surface checklist (operating-guide / commands.md / help.md
  / tui / series CLAUDE.md) so the same gap doesn't recur.
- 2026-04-30 (d1d1b8d): typeset font robustness — three layers of
  defence against the missing-font failure mode (tectonic
  walking fontspec's noisy "stepping through fonts by name"
  fallback chain mid-build). Layer 1: `templates/series/typeset/
  novel.tex` wraps `\setmainfont{EB Garamond}` in
  `\IfFontExistsTF` with a three-tier fallback (EB Garamond →
  system Garamond → TeX Gyre Pagella always present) that emits
  a clean `*** WARNING:` line naming the install command. Layer
  2: `housekeeping/doctor.py::check_typeset_fonts` runs
  `fc-match` against every name `novel.tex` references and warns
  before typeset rather than after. Layer 3: `install_export_
  tools.py` learned to install fonts with the `verify` step
  using `fc-match`.
- 2026-04-30 (b73eeb7): typeset cluster-fix from one real session
  — (1) PDF cover prefers `cover_titled.png` over bare
  `cover.png` (so the title overlay actually appears); (2)
  full-page plate pages get `\thispagestyle{plain}` (footer page
  number visible) instead of `{empty}`; (3) chapter-start plate
  default width bumped 0.6× → 0.8× textwidth to match
  published-book conventions; (4) `commands/typeset.md` ePub
  pandoc invocation now wires in glossary + appendix. Plus the
  start of the `docs/troubleshooting.md` typeset-symptom table
  that subsequent fix-batches kept extending (this commit set
  the "describe each fix as a row with symptom + fix landed"
  pattern).
- 2026-04-30 (f8acafb): typeset round 2 — five more bugs from a
  follow-up real-session run. (1) Cover proportions retuned
  (title 9% → 6% of cover width; top translucent band 4-38% →
  6-20% of cover height) so the painting isn't visually
  swallowed. (2) Appendix running header reads "Appendix"
  instead of inheriting the last `\chaptermark` (explicit
  `\markboth` after each `\chapter*` in front_matter.py /
  back_matter.py; novel.tex header reads `\rightmark`). (3)
  Timeline markers switched from emoji (📖/🏛️) to italic
  parentheticals because EB Garamond and TeX Gyre Pagella don't
  ship emoji glyphs (later superseded by 3d36d92). (4) ePub
  ornament wiring — `art/ornament_chNN.png` now appears at
  chapter opening in the ePub.
- 2026-04-30 (a7af370): ePub plate support — `mechanical/epub.
  py::build_epub_md` now reads `plates.yaml` (the same manifest
  the PDF path uses) and embeds user-imported plates at the
  declared `placement` (before-chapter / chapter-start / after-
  chapter) with caption + attribution. Bug story: a user with 3
  imported plates (via `/autonovel:art-import`) saw them in the
  PDF but not the ePub because the previous fix only covered
  auto-generated `ornament_chNN.png`, not the plates manifest.
- 2026-04-30 (5877563): typeset round 3 — eight quality fixes.
  Highlights: `md_to_latex` now handles `**bold**` (was leaving
  literal `**` in the output); `### sub-sub-headings` in the
  appendix promote to `\subsection*` (was rendering as literal
  `###`); plate verso/recto via custom `\cleartoverso` macro so
  before-chapter plates land on verso with the chapter on the
  facing recto (no blank verso); widow / orphan / broken-
  hyphenation penalties set to 10000 in novel.tex; ePub
  `@TITLE@` / `@AUTHOR@` placeholders now substituted via
  `mechanical render-novel-tex` per ePub template before pandoc
  sees them; back-cover image surface added — drop a PNG at
  `books/<book>/art/back_cover.png` and `novel.tex` renders it
  full-bleed after the colophon (parallel to the front-cover
  block).
- 2026-04-30 (3d36d92): timeline markers retuned again — the
  italic parentheticals from f8acafb made the three categories
  visually identical on a quick page-flip. Final fix: typeset-
  safe Unicode geometric shapes (U+25xx, present in every
  standard serif font) PAIRED with distinct font weights —
  `**◆ in story**` (filled diamond, bold), `*◇ referenced*`
  (open diamond, italic), `○ context` (open circle, plain).
  Three different shapes plus three different weights makes the
  category unmistakable.
- 2026-04-30 (7940cd0): TOC chapter names — REAL root cause.
  Two distinct bugs both fixed: (1) `templates/series/typeset/
  novel.tex` had no `\tableofcontents` directive at all — so
  the PDF had no TOC, just chapter-running-headers (added
  `\tableofcontents` to the frontmatter zone; pick up via
  `autonovel refresh-templates --only typeset`); (2)
  `mechanical/epub.py::_extract_chapter_title` only read prose
  `# Heading` lines, never YAML frontmatter `title:` —
  chapters drafted with title-in-frontmatter (the canonical
  shape after `/autonovel:extract-chapter-titles`) had no
  prose heading, so pandoc's ePub TOC defaulted to
  "Chapter N" instead of the title. Lock-in: extractor now
  reads frontmatter first, falls back to heading. The
  preceding 67bd55a / 519f3d7 fixed peripheral chapter-title
  rendering bugs but never the actual TOC; this commit hit
  the right place after the user explicitly asked to find the
  real root cause.
- 2026-05-01 (this batch): four follow-ups landed in one
  session — see "Tests last known green" entry below for the
  per-item summary. Plus: doc-sync remediation across the
  preceding 10 commits (3 commits' worth of gaps closed:
  519f3d7 TUI rename mention in `commands/help.md` /
  `docs/commands.md`; 5877563 `back_cover.png` surface in
  TUI Front+back tab + `docs/operating-guide.md`; d1d1b8d
  doctor font check in `docs/commands.md` / `commands/help.md`
  / `docs/operating-guide.md`). `feedback_keep_docs_in_sync.md`
  bumped to MEMORY.md position #1 with explicit "PRECONDITION
  FOR GREEN" framing — reinforced 4× by user.
- 2026-06-05 (movie-teaser planning, pre-implementation): new
  adjacent feature scoped — movie-script mode + AI-video teaser
  generator (script → beat-sheet → descriptive shot prompts →
  consistency anchors → optional assembly), targeting the Future
  Vision X-Prize (3-min trailer + ≤12pp treatment + 2pp brief;
  deadline 2026-08-15; AI explicitly allowed). Artifacts:
  `docs/prd-movie-teaser-mode.md` (v0.3, research-grounded:
  provider landscape, prompt schema, cinematography vocab,
  cross-shot consistency, free agent-driven tier (Pollinations-
  first), three-layer self-critique testing) and
  `docs/impl-plan-movie-teaser.md` (additive-only, regression-
  gated phasing). **Safety baseline: tag `pre-movies` @ `e252f71`
  pushed; Tier 1+2 = 1503 passed / 1 skipped verified.** Prime
  directive from user: do NOT break the existing book-writing
  pipeline — all teaser code lands in a new `src/autonovel/teaser/`
  package, the only existing-file edit is purely-additive optional
  `teaser`/`video` dicts on `ProjectConfig` (mirrors `typeset`/
  `image`), every commit holds the ≥1503 regression gate, and
  `git reset --hard pre-movies` is the rollback. No implementation
  started yet — planning only.
- 2026-06-05 (movie-teaser Phase 0 + treatment command): first
  implementation increment, additive-only. New `src/autonovel/teaser/`
  package (marker only this phase). Additive optional `teaser`/`video`
  dicts on `ProjectConfig` (mirror `typeset`/`image`: omitted-when-
  empty, round-trip + pre-movie back-compat tests). `[video]`/
  `[scripts]` extras stubs (empty — Phase 0 + treatment need no extra
  deps). Docs split: `docs/teaser-craft.md` is now the canonical
  user-facing creative guide (PRD §§18–20 marked build-spec, pointer
  added). New guard `tests/deterministic/test_install_immutability.py`
  pins that command render is independent of siblings + every command
  (incl. new ones) installs with the begin/end lifecycle. New
  `commands/treatment.md` (heavy) — film treatment + 2-page brief from
  the foundation, `--audience xprize` default (optimistic future, real
  problem, stakes + arc, visual ambition); writes
  `books/{book}/treatment.md` + `brief.md`; reveals the ending (unlike
  a teaser). Doc-sync: docs/commands.md (new Movie/teaser section),
  README, series-template CLAUDE.md, commands/help.md (movie topic),
  FUTURE-TODOS (progress). Only existing-file edit was the additive
  `project.py` fields. Regression gate held: **Tier 1+2 1503 → 1515
  passed, 1 skipped, 0 failed.**
- 2026-06-05 (movie-teaser Phase 1: teaser-beats + shot-prompts):
  additive. New `src/autonovel/teaser/{shots,beats,render_prompt,
  providers,critique}.py` (shot schema + teaser.json I/O + hard
  validation incl. provider clip-cap; beat/shot budget planner;
  canonical-order prompt render; provider capability table as data;
  mechanical pre-generation critique). New mechanical CLI branches
  `teaser-plan` / `teaser-validate` / `teaser-critique` /
  `teaser-render-prompt` (additive subparsers; existing untouched).
  New commands `/autonovel:teaser-beats` (standard) + `/autonovel:
  shot-prompts` (heavy, authors schema → validate hard-gate +
  mechanical critique + LLM rewrite pass → render per-shot markdown;
  all free). LLM/quality stays in command bodies; Python is
  structure-only. Doc-sync across commands.md / README / series
  CLAUDE.md / help.md / teaser-craft.md / FUTURE-TODOS. No existing-
  module behaviour changed. Regression gate: **Tier 1+2 1515 → 1546
  passed, 1 skipped, 0 failed.** Deferred: `/autonovel:teaser`
  orchestrator + standalone teaser-critique command.
- 2026-06-05 (movie-teaser Phase 1 *final*: teaser orchestrator +
  teaser-critique): additive. New commands `/autonovel:teaser`
  (standard — chains teaser-beats → shot-prompts, each in a fresh
  `task` subagent for context hygiene; `--with-treatment` runs
  treatment first when absent; overwrite-guarded; free) and
  `/autonovel:teaser-critique` (standard — standalone re-runnable
  free pre-generation critique = mechanical linter + LLM critic pass;
  **read-only** on teaser.json; writes advisory `teaser/critique.md`).
  Robustness: `teaser.shots.load` now raises a clear ValueError on a
  non-object top-level JSON (was an opaque AttributeError when probing
  the validator). LLM/quality stays in command bodies. Validated the
  upstream `shot-prompts` end-to-end on the Fugger book (35 shots,
  144s, clean critique). Doc-sync across commands.md / help.md /
  README / series CLAUDE.md / teaser-craft.md / impl-plan /
  FUTURE-TODOS. No existing-module behaviour changed. Regression gate:
  **Tier 1+2 1546 → 1562 passed, 1 skipped, 0 failed.**
- 2026-06-05 (movie-teaser Phase 2: render dialects + reference-image
  consistency): additive. `render_prompt.py` gained per-provider render
  **dialects** keyed off `providers.dialect` — `render_terse` (Runway:
  comma-keywords), `render_enum` (Luma: concise + camera-motion enum via
  `luma_camera()` mapping, unknown moves pass through verbatim), and the
  `render_visual()` dispatcher (prose for veo/sora/generic/pollinations/
  kling). `render_markdown` now renders via the dialect and prints the
  dialect name; `render_prose` unchanged (no regression). New
  `src/autonovel/teaser/refs.py` — per-subject **reference-image plan**
  (which canonical ref each recurring subject needs, which shots use it,
  which already exist in `teaser/refs/` or a `shared/art_references/`
  plate, appearance-drift count). New mechanical CLI `teaser-refs-plan`
  (additive subparser). `shot-prompts.md` wired to run it + note missing
  refs. All format-translation + filesystem facts; no LLM, no
  word-list quality gate. Doc-sync: commands.md (dialect note +
  refs-plan row), teaser-craft.md (§5 dialects, §6 refs-plan),
  module docstring, impl-plan, FUTURE-TODOS. No existing-module
  behaviour changed. Regression gate: **Tier 1+2 1562 → 1570 passed,
  1 skipped, 0 failed.**
- 2026-06-05 (movie-teaser Phase 3.5: thin free render adapter + clip
  critique): additive. New `src/autonovel/teaser/render.py` — stateless
  Pollinations render adapter: deterministic per-(shot,take) URL +
  seed (`crc32`, explicit `shot.seed` honoured), aspect→size (480p dev
  default; watermarks/low-res OK), `build_request`/`plan`/`render` with
  an injectable httpx client seam (mirrors export/wikimedia; tests never
  hit the network). Failures isolate per-clip; one bad download never
  aborts the batch. New mechanical CLI `resolve-video-provider` (twin of
  resolve-image-provider: CLI → `project.yaml::video.provider` →
  pollinations) and `teaser-render` (`--dry-run` builds the URL plan for
  $0; `--kind image|video`; `--takes`; `--shot`; `--height`). New command
  `/autonovel:teaser-render` (standard) — resolve provider → dry-run plan
  → download clips → **vision clip critique** (KEEP/REGENERATE/
  UPGRADE-TO-PAID) → advisory `teaser/clips/render-report.md`. BRIGHT
  LINES held (PRD §23.2): clips on disk only, **no state file**, **no
  auto-assembly**, paid providers only ever *recommended* (never
  auto-called). HTTP (not LLM) in Python is consistent with the existing
  wikimedia-fetch download. Doc-sync: commands.md (movie row + 2
  mechanical rows), help.md, README, series CLAUDE.md, teaser-craft.md
  §10, module docstring, impl-plan, FUTURE-TODOS. No existing-module
  behaviour changed. Regression gate: **Tier 1+2 1570 → 1584 passed,
  1 skipped, 0 failed.**
- 2026-06-05 (movie-teaser Phase 3: ffmpeg cut-list assembly + viewer-
  panel cut critique): additive. New `src/autonovel/teaser/assemble.py` —
  `CutList`/`CutEntry` schema + I/O, `build_cut_list(teaser, clips_dir)`
  (default cut from teaser + clips on disk; skips + reports shots with no
  clip), and `ffmpeg_command()`/`ffmpeg_command_str()` — a PURE planner
  that builds the ffmpeg argv (image slideshow `-loop 1 -t dur` or video
  `trim`+concat; optional audio bed + `-shortest`) but **never runs
  ffmpeg** (mirrors mechanical/audio.py). New mechanical CLI
  `teaser-cut-list` + `teaser-ffmpeg-cmd`. New command
  `/autonovel:teaser-assemble` (standard) — ffmpeg-presence check → build/
  reuse cut_list.json → plan cmd → run ffmpeg via `bash` (the audiobook-
  assemble division of labour) → viewer-panel cut critique (hook/
  escalation/title/button) → `teaser/assembly-report.md`. v1 thin: hard
  cuts only, no burned-in text (cards listed for the editor), missing
  clip skipped not fatal. Doc-sync: commands.md (movie row + 2 mechanical
  rows + header now "full pipeline shipped"), help.md, README (dropped
  "in progress"), series CLAUDE.md, teaser-craft.md §10, module
  docstring, impl-plan, FUTURE-TODOS. **Movie-teaser pipeline now
  end-to-end: treatment → teaser → teaser-critique → teaser-render →
  teaser-assemble.** No existing-module behaviour changed. Regression
  gate: **Tier 1+2 1584 → 1600 passed, 1 skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 4: real free render backends +
  model-pin flip): additive. THREE strands, all behind the existing
  thin-adapter line. (1) **Model-pin default flip** — `pin_model` now
  defaults to **False** in `claude_code.render` / `installer.install` /
  `cli.py`; `autonovel install` omits the `model:` frontmatter so the
  session model wins (kills the `[1m]` billing-gate downshift).
  `--pin-model` is the explicit opt-in; `--no-model-pin` kept as a
  deprecated no-op. Only the Claude adapter is affected (Codex/Gemini
  emit `suggested_model`, untouched). (2) **Multi-provider video
  backends** — new `src/autonovel/teaser/backends.py`: a `Net` HTTP
  wrapper (httpx client seam) + `RateLimiter` (paces ≥
  `providers.min_interval_s`, 429/503 bounded exp-backoff honouring
  `Retry-After`) + key resolution (`--token` → env → `.env` via
  python-dotenv) + per-provider create→poll→download adapters: **`grok`**
  (xAI Grok Imagine — DEFAULT video provider; native dialogue+music, 5
  free/day + $25, no card), `kie`, `veo` (Gemini API path), `magichour`,
  `fal`, manual `flow`, and an offline **`stub`** (Pillow placeholder
  keyframes — no network/key/quota, to validate the pipeline for $0).
  Pollinations demoted to **images-only** with a free-token path +
  **early-402** detection (one actionable message, not N identical
  failures). `render.py` dispatches by provider; `RenderRequest` gains
  `provider`/`duration_s`. `resolve-video-provider` default flips
  pollinations→**grok** (image default stays pollinations). `teaser-render`
  gains `--kind auto`, `--token`, `--delay`, `--max-retries`; dry-run JSON
  now reports `needs_key`/`key_present`/`manual`. (3) **`providers.py`**
  capability table extended (kinds/needs_key/min_interval_s/free_note) +
  rows for stub/grok/kie/magichour/fal/flow. New tests:
  `test_teaser_phase4.py` (22) — key resolution, rate-limiter,
  Net 402/auth/429, each backend via scripted client, stub offline,
  missing-key/manual/402 fail-fast, CLI dry-run key status; offline
  stub→cut-list→ffmpeg smoke verified by hand. Doc-sync: NEW
  `docs/teaser-render-providers.md` (backend matrix + key setup +
  Flow/Veo-$300 notes), `commands/teaser-render.md` (rewritten:
  stub-first, key gates, manual flow), commands.md (movie row + 2
  mechanical rows + install row + header), help.md (movie + install),
  README, series CLAUDE.md, teaser-craft.md §10, teaser.md, teaser-
  assemble.md, troubleshooting.md (two model-pin sections rewritten),
  FUTURE-TODOS (3 items closed; character-refs + Veo-Vertex + audio-mix
  added). Adapter tests re-pointed for the new pin default. `.env`
  (gitignored) seeded with the user's `XAI_API_KEY`. No existing-module
  behaviour changed; install-immutability holds (only Claude `model:`
  line removed by default, by design). Regression gate: **Tier 1+2 1600
  → 1621 passed, 1 skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 5.1: character-reference manifest +
  approval gate): additive. New `src/autonovel/teaser/refmanifest.py` —
  `CharacterRef` (subject, source wikimedia|local|generate, source_ref,
  locked appearance, constraints, morph, status pending→approved→locked,
  ref_path) + `RefManifest` (yaml load/dump w/ header, slug-insensitive
  `get`) + `scaffold_from_teaser` (starter manifest from `refs.plan_refs`)
  + `build_status` (merges auto plan with manifest → per-subject
  `next_action`: declare-source/fetch-source/generate/approve/ready) +
  `RefStatus.unapproved_subjects()` (the approval gate). New mechanical
  CLI `teaser-refs` (`--init` scaffolds `books/{book}/teaser/refs.yaml`;
  else prints status; json/human). New command `/autonovel:teaser-refs`
  (standard) — scaffold → declare source (PD art via wikimedia-search/
  -fetch, local via art-import, or generate) → approve/lock; advisory
  approval gate wired into `teaser-render` step 5 (real renders only;
  `stub` exempt). Reuses `refs.py`/`wikimedia-*`/`art-import` (no new
  generation path). New tests: `test_teaser_phase5.py` (8). Doc-sync:
  commands.md (slash row + mechanical row + pipeline summary), help.md
  (movie section), series CLAUDE.md (step 3b), teaser-render.md
  (approval-gate step), FUTURE-TODOS (dir-nesting TODO added). Mechanical
  only; picking/approving/fetching are command-body LLM/interactive
  steps. No existing-module behaviour changed. Regression gate: **Tier
  1+2 1621 → 1635 passed, 1 skipped, 0 failed.** NEXT (Phase 5.2): feed
  the locked reference image into the backends as the image-to-video /
  image-conditioning input (grok/veo/kie `image` field) so approved refs
  actually anchor real renders; optional morph-from-source step.

- 2026-06-06 (movie-teaser Phase 5.2: reference-conditioned keyframes):
  additive. Approved character references now actually anchor the render
  so identity holds across separately-generated shots. New **`gemini`**
  image backend (`backends._gemini_image`, Nano Banana 2/Pro) — synchronous
  reference-conditioned photoreal stills, each `refs.yaml` portrait
  attached as an `inline_data` part; `_load_ref` (local path / http URL →
  base64) shared with `fal` (FLUX.1 Kontext for `--kind image`).
  `RenderRequest` gained `model` + `reference_images`; `build_request`
  gained `reference_images` + `style_override` (and pollinations
  flux-kontext for an http ref); `plan` gained `shot_refs`/`max_refs`/
  `style_override` (drops missing local refs, caps at max_refs, characters
  before locations). `teaser-render` gained `--refs` / `--refs-manifest` /
  `--film-style`; `_load_teaser_refs_map` reads `refs.yaml` via
  `refmanifest`, **enforces the approval gate** (only approved/locked
  subjects' refs flow), prefers `refs/<slug>_ref.png` over `ref_path`, and
  resolves shots from the manifest `shots:` (fallback: auto plan).
  `refmanifest.CharacterRef` gained `kind` (character|location|prop) +
  `shots` (scaffold records them). providers.py: new `gemini` row,
  `fal` now image+video. New tests: `test_teaser_phase52.py` (12). Doc-sync:
  teaser-render.md (gemini + --refs/--film-style + reference workflow),
  teaser-refs.md (portrait convention + render-with-refs next step),
  teaser-render-providers.md (gemini row + reference-conditioning section),
  commands.md (slash + mechanical rows). No existing-module behaviour
  changed; pollinations/grok/veo/etc text paths unaffected when `--refs`
  absent. Regression gate: **Tier 1+2 1635 → 1647 passed, 1 skipped, 0
  failed.**

- 2026-06-06 (movie-teaser Phase 5.3: image-to-video start frames):
  additive. A composed keyframe (image) now seeds the video backends so
  the identity-locked still becomes motion. `RenderRequest` gained
  `init_image`; `build_request`/`plan` carry it; `plan(from_keyframes=True,
  keyframe_dir=…)` auto-detects each shot's `shot_<id>.{png,jpg,jpeg,webp}`
  (default dir = out_dir) for `--kind video` and sets it as the start
  frame (image kind never seeds one). backends: `_init_image` helper +
  `grok` (`image` data-URI), `veo` (`instances[].image.bytesBase64Encoded`
  + mimeType), `kie` (`input.image_url` data-URI) attach it when present;
  no init ⇒ unchanged text-to-video. `teaser-render` gained
  `--from-keyframes` / `--keyframe-dir`. New tests:
  `test_teaser_phase53.py` (8). Doc-sync: teaser-render.md (i2v workflow),
  teaser-render-providers.md (keyframe→motion section), commands.md
  (rows), STATE, impl-plan. No existing-module behaviour changed.
  Regression gate: **Tier 1+2 1647 → 1655 passed, 1 skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 5.4: audio-bed mixing in assembly):
  additive. Fixed two assembly audio bugs: clip audio was always dropped
  (`concat a=0`) and a bed *replaced* rather than ducked. `CutList` gained
  `audio_mode` (auto|none|bed-only|clip-only|mix|duck) + `clip_audio`
  (bool|None → infer from kind) + `has_clip_audio()`/`resolve_audio_mode()`.
  `ffmpeg_command` now: keeps native clip dialogue/music (`concat a=1` →
  `[aclip]` for video w/ audio); **duck** mode ducks the bed under the
  dialogue via `sidechaincompress` (asplit the dialogue → key the
  compressor → amix); mix/clip-only/bed-only/none as named. `auto`:
  image→bed-only/none, video+bed→duck, video no-bed→clip-only, silent
  video→bed-only/none. Bed mapped as a raw input stream (`2:a`, no
  brackets — caught by the Phase-3 test). `build_cut_list` +
  `teaser-cut-list` gained `--audio-mode`/`--clip-audio`/`--no-clip-audio`;
  teaser-assemble command body documents duck-by-default. New tests:
  `test_teaser_phase54.py` (10). Doc-sync: teaser-assemble.md,
  commands.md (2 rows), STATE, impl-plan. Also: user's `GEMINI_API_KEY`
  added to gitignored `.env` (resolves for gemini/veo). No existing-module
  behaviour changed (image slideshow + bed path preserved). Regression
  gate: **Tier 1+2 1655 → 1665 passed, 1 skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 5.5+5.6: audio→prompt + voice lock/age):
  additive. **Gap found:** `render_visual` (the backend prompt) omitted the
  shot `audio` block entirely — only the human `.md` showed it — so
  grok/veo never received the dialogue/SFX. **5.5:** new
  `render_prompt.render_audio_for_prompt(shot, voices)` (compact dialogue +
  per-speaker voice tag + sfx + ambience); `build_request` appends it to the
  prompt **for `--kind video` only**; `plan` threads `shot_voices`.
  **5.6 (voice lock + age):** `refmanifest.CharacterRef` gained `voice`,
  `birth_year`, `voice_ages[]` ({name,descriptor,from_year,to_year}) +
  `resolve_voice(year)`/`age_variant_name(year)` (auto-age from a shot's
  story-time; per-line `voice` override wins). `Shot` gained optional
  `story_year`. `teaser-render --voices` + `_load_teaser_voices_map`
  (reads refs.yaml, **approval-gated**, resolves each speaker's voice by
  the shot's `story_year`). Voices live in refs.yaml (one manifest/gate for
  face + voice). Design confirmed with user: auto-age from story-time,
  storage in refs.yaml. New tests: `test_teaser_phase56.py` (11). Doc-sync:
  teaser-render.md, teaser-refs.md, teaser-render-providers.md (audio/voice
  table + section), commands.md (2 rows), FUTURE-TODOS (scene-transitions +
  music-generation TODOs added), STATE, impl-plan. No existing-module
  behaviour changed (audio only appended for video shots that declare it).
  Regression gate: **Tier 1+2 1665 → 1676 passed, 1 skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 5.7: scene transitions): additive.
  `CutEntry` gained `transition` (cut|fade|dissolve) + `fade_out` +
  `transition_dur`; `ffmpeg_command` emits **concat-compatible** per-clip
  fades (`fade=t=in/out`, clamped to half the clip) — `dissolve` degrades
  to a fade-in for now (true cross-dissolve = xfade overlap, noted 5.7b).
  `build_cut_list(transitions=True)` auto-defaults: open→fade-in,
  close→fade-out, title-role→fade; everything else a hard cut. New
  `suggest_transitions(teaser)` + `teaser-transitions` CLI flag candidate
  points from **structured signals only** (|Δstory_year|≥gap, setting/
  location change, fast→slow duration shift, beat→title/button, open/close)
  — advisory candidate generator; the artistic placement is the LLM's call
  in the teaser-assemble command body (feedback_avoid_brittle_python).
  `teaser-cut-list`/`teaser-assemble` gained `--no-transitions`. New tests:
  `test_teaser_phase57.py` (11). Doc-sync: teaser-assemble.md (transitions
  step + defaults), commands.md (3 rows incl. new teaser-transitions),
  FUTURE-TODOS (TODO closed, 5.7b cross-dissolve noted), STATE, impl-plan.
  No existing-module behaviour changed (a default CutEntry is still a hard
  cut; build_cut_list defaults only touch open/close/title). Regression
  gate: **Tier 1+2 1676 → 1687 passed, 1 skipped, 0 failed.**

- 2026-06-06 (Veo durationSeconds bugfix): `backends._veo` sent
  `parameters.durationSeconds` as a **string**, which Veo's API rejects
  with HTTP 400 (confirmed live: the same key + prompt succeeds when it's
  a number). Changed to an `int`. Regression guard added
  (`test_teaser_phase53.py::test_veo_duration_is_a_number_not_string`).
  (Field note from live testing: grok's video API returned 403 on the
  user's XAI key — that tier likely needs a separate Grok-Imagine
  subscription; environment/billing, not a code bug.) Tier 1+2 1687 →
  1688.

- 2026-06-06 (movie-teaser Phase 5.8: versioned takes): additive. New
  `src/autonovel/teaser/takes.py` — `archive_take` copies each render into
  `clips/takes/shot_<id>_take<N>.<ext>` (monotonic `next_take_number`,
  never overwrites) while `shot_<id>.<ext>` stays the latest pointer;
  `list_takes` + `promote_take` (promote an earlier take back to latest);
  `parse_clip_name`. `teaser-render` archives each ok clip by default
  (`--no-archive` opts out; JSON gains `archived`). New CLIs `teaser-takes`
  (list) + `teaser-take-pick --shot --take` (promote). `teaser-ffmpeg-cmd
  --versioned` timestamps the mp4 (reuses typeset `output_filename`/
  `latest_filename`) + returns a `latest` the command body copies to;
  teaser-assemble body uses it. New tests: `test_teaser_phase58.py` (8).
  Doc-sync: teaser-render.md, teaser-assemble.md, commands.md (render +
  assemble rows + 3 mechanical rows), FUTURE-TODOS (closed), STATE,
  impl-plan. No existing-module behaviour changed (render still writes the
  same latest file; archiving is an added copy). Regression gate: **Tier
  1+2 1688 → 1696 passed, 1 skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 5.9: music score policy + audio seam-
  fades; + Veo fixed-duration fix): additive. **Music** — real trailers
  ride one continuous score, not per-clip music. New `--score
  native|bed|none` (`render_audio_for_prompt(..., score)` → for bed/none
  appends "No musical score; diegetic sound only" to the video prompt so
  the model's per-clip music doesn't fight a single teaser-wide bed);
  threaded through build_request/plan + teaser-render. **Audio seam-fades**
  — `CutList.audio_seam_fade` + `ffmpeg_command` applies per-clip
  `afade` in/out on each clip's audio (concat-compatible) so native
  per-clip music doesn't pop at cuts; `teaser-cut-list`/`teaser-assemble
  --audio-seam-fade`. (True overlapping cross-fade still deferred = 5.7b.)
  **Veo duration fix** — Veo only accepts a fixed set of lengths (4/6/8s);
  `_clip_seconds(..., allowed=(4,6,8))` snaps to nearest (ties→shorter),
  still numeric (the earlier string→400 fix). New tests:
  `test_teaser_phase59.py` (10). Doc-sync: teaser-render.md,
  teaser-assemble.md, teaser-render-providers.md (music/score section +
  provider duration quirks), commands.md (render/cut-list/assemble rows),
  STATE, impl-plan. No existing-module behaviour changed (default `score`
  = native = no prompt change; seam-fade off by default). Regression gate:
  **Tier 1+2 1696 → 1706 passed, 1 skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 6: teaser storytelling — ALL 12 best
  practices + script versioning): additive. The first real render read as a
  set of disconnected clips — no throughline, no stakes, almost no
  dialogue. Fix is upstream of the visuals: a **story spine** + enforced
  trailer craft. New `shots.Spine` (dramatic_question, logline, want,
  opposing_force, emotional_arc, score_direction, genre) on `Teaser` +
  per-shot `stakes_level`, serialized under `teaser.json :: spine` /
  `stakes_level` and **omitted when empty/None** so pre-Phase-6 teasers
  round-trip byte-identical. Best-practice map: bp1 dramatic question, bp2
  4-act order (hook-first/title-~⅔/button-last), bp3 rising stakes ladder,
  bp4 want+opposing force, bp5 dialogue mining (3–6 loaded lines), bp6
  premise text cards, bp7 withhold-the-answer button, bp8 emotional arc +
  score direction, bp9 genre-signalling hook, bp10 restraint (cut filler),
  bp11 one hero face (≤3 named), bp12 **render gate**. `teaser-beats`
  authors the spine + 4-act ladder; `shot-prompts` copies the spine, mines
  dialogue, writes cards, sets `stakes_level`, enforces order/restraint/
  cast; `critique.py` gained story-spine flags (`no-dramatic-question`/
  `no-logline`/`no-stakes`/`no-emotional-arc`/`no-genre`/`thin-dialogue`/
  `thin-text-cards`), 4-act flags (`hook-not-first`/`multiple-hooks`/
  `no-title`/`button-not-last`/`title-after-button`), stakes-ladder flags
  (`no-stakes-ladder`/`stakes-not-rising`), `cast-sprawl`, plus
  `STORY_GATE_CODES`/`story_gate_failures`/`story_ready`. **bp 12 gate:**
  `teaser-render` refuses a real generation (exit 3) while any story-spine
  flag is present — `stub` + single-`--shot` exempt, `--skip-narrative-gate`
  overrides, `--dry-run` reports `narrative_gate_blocks`. **Script
  versioning** (re-run without losing old scripts): `takes.archive_script` +
  `teaser-archive-script` CLI timestamp-copy `beats.md`/`teaser.json` to
  `teaser/script-takes/` before a `--force` regenerate; the `refs/`
  portraits + location plates are reused untouched. New
  `Teaser.dialogue_line_count()` / `text_card_count()`. New tests:
  `test_teaser_phase6.py` (26). Doc-sync: teaser-beats/shot-prompts/
  teaser-critique/teaser-render/teaser command bodies, teaser-craft.md
  (new §0), prd (spine+shot schema + gate), commands.md (rows + flags +
  archive-script row), series-template CLAUDE.md, README, FUTURE-TODOS,
  STATE, impl-plan. No existing-module behaviour changed (empty spine
  omitted; no new required fields; gate exempts stub). `autonovel install`
  re-run. Regression gate: **Tier 1+2 1706 → 1732 passed, 1 skipped,
  0 failed.**

- 2026-06-06 (movie-teaser Phase 7: character/location references —
  generalize the Fugger spike): additive. (1) **Locations as first-class
  refs** — `refs.plan_refs(include_locations=)` surfaces distinct settings
  as `kind="location"` entries; `refmanifest.scaffold_from_teaser` /
  `build_status` thread it; `teaser-refs --init --with-locations` +
  `teaser-refs-plan --with-locations` (and `RefEntry.kind`). The existing
  refs-map already orders characters-then-locations + applies the approval
  gate, so declared+approved location plates attach to every shot in that
  setting — the period-correct-place fix (wooden Rialto, not the 1591
  bridge). (3) **Prompt/appearance sync** — `CharacterRef.appearance_ages`
  (parallel to `voice_ages`) + `resolve_appearance(year)`;
  `_load_teaser_appearances_map` resolves each shot's appearance by
  `story_year`; `render.build_request(appearance_override=)` /
  `plan(shot_appearances=)` swap the prompt's appearance text so it matches
  the age-correct plate (boy→youth→man→elder). (5) **Refs reach the VIDEO
  backends** — `backends._init_image` falls back to the shot's primary
  reference plate as the image-to-video start frame (grok/veo/kie) when no
  `--from-keyframes` keyframe exists, so locked identity reaches motion.
  All additive: `include_locations`/age-ladder/override default off/empty;
  no existing behaviour changed (phase2/5 ref tests green unchanged). New
  tests: `test_teaser_phase7.py` (12). Remaining (logged): auto-derive age
  windows from chapter dates, lineage-morph variant plates, auto
  default-source suggestions per entity type. Doc-sync: teaser-refs.md,
  teaser-render.md, teaser-craft.md (§6), teaser-render-providers.md,
  commands.md (ref rows), FUTURE-TODOS, STATE, impl-plan. `autonovel
  install` re-run. Regression gate: **Tier 1+2 1732 → 1744 passed, 1
  skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 8: mixed assembly + burn-in title cards):
  additive. (1) **Mixed assembly** — `teaser-cut-list --kind mixed` /
  `teaser-assemble --kind mixed`: `build_cut_list` picks `shot_<id>.mp4`
  (video, native audio, trimmed to duration_s) else `shot_<id>.png` (still,
  held) per shot; `CutEntry.media` + `media_kind()`; `ffmpeg_command`
  normalizes every segment to one WxH + stereo AAC and synthesizes per-still
  silence (`anullsrc` lavfi inputs) so the concat `a=1` has an audio pad for
  each segment, with the bed ducking/mixing over the concatenated track.
  `has_clip_audio()` now true for mixed cuts with ≥1 video segment.
  (2) **Burn-in title cards** — `--burn-titles` (+ `--font`): opt-in ffmpeg
  `drawtext` per `text_card` (title-role centered/large, stingers
  lower-third), alpha-faded over each segment; `CutEntry.card_kind`,
  `CutList.burn_titles`/`font_file`, `_burn_chain` + `_dt_escape` (escape
  `\\`/`:`/`%`, apostrophe → typographic to dodge the nested-quote
  minefield). Timing is segment-local (every segment trimmed/held to
  duration_s). Additive: image/video paths unchanged (phase3/5.4/5.9 tests
  green); mixed/burn off by default. New tests: `test_teaser_phase8.py`
  (9). Doc-sync: teaser-assemble.md, commands.md (assemble + cut-list
  rows), FUTURE-TODOS, STATE, impl-plan. `autonovel install` re-run.
  Regression gate: **Tier 1+2 1744 → 1753 passed, 1 skipped, 0 failed.**

- 2026-06-06 (movie-teaser Phase 9: music-generation backend): additive.
  New `teaser/music.py` — generate one cohesive trailer bed from a prompt
  (default = the teaser spine's `score_direction`, the Phase-6 tie-in):
  `generate_bed(provider=stub|musicgen|elevenlabs)`; `stub` writes a valid
  stereo silent WAV offline (stdlib `wave`) so the generate→assemble chain
  works for $0, `musicgen` (HF Inference `facebook/musicgen-*`, free
  `HF_TOKEN`) + `elevenlabs` (`ELEVENLABS_API_KEY`) POST via the injectable
  client seam; reuses backends' `.env` key resolution + typed `RenderError`.
  `teaser-music <teaser.json>` CLI writes a versioned
  `teaser/music/<title>_bed_<UTC>.<ext>` + `_latest`, `--dry-run` reports
  key status; fed to `teaser-assemble --audio`. Added the per-shot
  `audio.music` prompt line in `render_audio_for_prompt` — emitted ONLY on
  `--score native` (one-off cues; the single bed carries music on bed/none).
  Additive: stub needs no key; no existing behaviour changed. New tests:
  `test_teaser_phase9.py` (9). Doc-sync: teaser-assemble.md (music section),
  teaser-render-providers.md, teaser-craft.md (§0), commands.md, FUTURE-TODOS,
  STATE, impl-plan. `autonovel install` re-run. Regression gate: **Tier 1+2
  1753 → 1762 passed, 1 skipped, 0 failed.**

- 2026-06-06 (Phase 10: directory-nesting clarity): additive, non-teaser.
  The `<series>/books/<book>/` layout is correct; the confusion is
  series-name == book-name → `…/<name>/books/<name>/`. New
  `paths.looks_doubled` + `paths.nesting_note`; `doctor.run` WARNS on a
  name collision (per book) and flags a literal `books/books/` level as a
  PROBLEM; `new-book` prints the note on collision; series-template CLAUDE.md
  documents the layout prominently. Audited paths.py / new-series / new-book
  / teaser out_dir defaults — nothing writes a second `books/` level. No
  existing behaviour changed (warnings only). New tests:
  `test_directory_nesting.py` (5). Doc-sync: series-template CLAUDE.md,
  commands.md (doctor row), FUTURE-TODOS, STATE. Regression gate: **Tier 1+2
  1762 → 1767 passed, 1 skipped, 0 failed.**

- 2026-06-07 (run-feedback fixes: refs data-loss + teaser next-step +
  gate clarity): additive bug-fixes from a real Fugger run. (1) **Data-loss
  bug:** `teaser-refs --init --force` rebuilt every subject as `pending`,
  dropping hand-locked plates. `scaffold_from_teaser(preserve=…)` now does a
  non-destructive merge — an already-declared subject is kept verbatim
  (status/source/appearance/constraints/voice/voice_ages/appearance_ages/
  ref_path), only `shots` refreshes, new subjects added pending, and orphan
  locked subjects retained; the CLI loads the existing manifest on `--force`
  and reports `Preserved N approved/locked`. (2) **Flow clarity:** teaser/
  movie commands no longer show "draft chapter N+1" as the next step —
  `lifecycle._teaser_next_step` maps each teaser command to the teaser-flow
  next (treatment→teaser→critique→render→assemble), used by `_end` before
  the chapter pipeline. (3) **Gate message:** the narrative-gate refusal now
  names the regenerate fix (`shot-prompts --force`) and calls out a
  totally-absent `spine` block (teaser.json predating the story pass). New
  tests: `test_teaser_flow_fixes.py` (6). No existing behaviour changed
  (preserve defaults None; non-teaser next-step unchanged). Doc-sync:
  teaser-refs.md, commands.md, STATE. Regression gate: **Tier 1+2 1767 →
  1773 passed, 1 skipped, 0 failed.**

- 2026-06-07 (run-feedback round 2: teaser revise-loop + richer stub cards):
  additive. (1) **The missing "revise" half of the teaser loop** —
  `/autonovel:teaser-revise` (new heavy command) reads `teaser/critique.md`
  + the mechanical flags and **applies them to `teaser.json` IN PLACE**
  (fills the spine, strengthens dialogue/cards, repairs 4-act order + stakes
  ladder, rewrites only flagged shots), preserving everything else,
  archiving the prior script, re-validating + re-critiquing up to
  `--max-rounds`. This mirrors the book's evaluate→revise; `shot-prompts
  --force` stays the blind regenerate-from-scratch. Wired into the
  next-step chain (`teaser-critique` → revise when BLOCKED → re-critique).
  (2) **`teaser-critique` output now leads with the render-gate verdict** +
  the exact next command (READY→render, BLOCKED→teaser-revise) so the user
  never has to guess how to act on the critique. (3) **Richer stub cards** —
  `RenderRequest.card` (role/location/dialogue/plot/text_card, filled by
  `build_request`) drawn by `make_stub` as a wrapped, labelled scene card,
  so the free offline first-pass review shows what each beat *is*, not just a
  colour + prompt slice. New tests: `test_teaser_revise.py` (6). No
  existing behaviour changed (card defaults
  empty; revise is new). Doc-sync: new commands/teaser-revise.md,
  teaser-critique.md (verdict), teaser-craft.md (§10 loop), commands.md
  (row + pipeline line), STATE. `autonovel install` re-run. Regression gate:
  **Tier 1+2 1773 → 1785 passed, 1 skipped, 0 failed** (+6 contract pickups for the new command, +6 deterministic).

- 2026-06-07 (teaser orchestrator runs the critique→revise loop): additive,
  command-body + next-step. `/autonovel:teaser` gained **Stage 3** — after
  beats + shot-prompts it spawns a subagent running `/autonovel:teaser-revise
  --max-rounds {revise_rounds}` (default 2; `--no-revise` skips), which loops
  critique→apply-in-place→re-critique until the render gate is READY, and the
  combined summary now reports the **gate verdict** (READY/BLOCKED) + the
  right next step (refs/render vs another revise). New flags `--revise-rounds`
  / `--no-revise`; frontmatter reads/writes gained `teaser/critique.md`; the
  orchestrator's postamble next-step flipped from teaser-critique to
  teaser-render (it now produces a READY teaser itself). 1 new test. No
  existing behaviour changed (loop additive; `--no-revise` reproduces the old
  two-stage flow). Doc-sync: teaser.md, commands.md (row), STATE. `autonovel
  install` re-run. Regression gate: **Tier 1+2 1786 passed, 1 skipped.**

- 2026-06-07 (render-side: text-free titles + sent negatives + spend-gated
  auto-regenerate): additive. Root-cause for the "model hallucinated a wrong
  title" run: the authored `negative_prompt` was **never sent** to any
  backend. Fixed — `RenderRequest.negative_prompt` + `build_request` folds it
  into the prompt as a trailing `Negative prompt:` line (all backends now
  honour it); a `role: title` / text-card shot auto-gets `_NO_TEXT_TERMS`
  (text/letters/typography/title card/…) so it renders TEXT-FREE (title
  burned in at assembly). Render-side critique→regenerate loop (the analogue
  of the script revise loop, but SPEND-GATED): `teaser-render` command body
  auto-re-renders REGENERATE clips for free on `stub`, and on a paid backend
  only with `--auto-regenerate` (bounded by `--max-regen`, default 3);
  UPGRADE-TO-PAID is never auto-acted. New tests: `test_teaser_negative.py`
  (6). No existing behaviour changed (no negative + non-title ⇒ prompt
  unchanged). Doc-sync: teaser-render.md, teaser-craft.md (§9), commands.md
  (row), STATE. `autonovel install` re-run. Regression gate: **Tier 1+2
  1792 passed, 1 skipped, 0 failed.**

- 2026-06-07 (diegetic-text fix + render --revise + /next teaser-awareness):
  additive, three threads. (1) **Diegetic text protected** (user caught that
  a ledgers/accounts teaser would be blanked): the title no-text augmentation
  is **narrowed to `role: title` only** and to *overlay-title* terms
  (`title text`/`movie title`/`caption`/`watermark`/`logo`, NOT broad
  `text`/`letters`/`words`) so content shots of ledgers/letters keep their
  writing; shot-prompts + teaser-craft §4 + the teaser-critique checklist now
  tell authors NOT to negative-prompt `text` on a shot whose subject IS
  written material. (Supersedes the broad `_NO_TEXT_TERMS` from the prior
  entry → `_NO_TITLE_TEXT_TERMS`.) (2) **`teaser-render --revise`** — the
  render-side mirror of teaser-revise: the vision critique persists a
  machine-readable `clips/render-report.json` alongside the .md; `--revise`
  reads it and re-renders ONLY the REGENERATE shots (review-between-runs,
  spend-gated, UPGRADE-TO-PAID never auto-acted). (3) **`/autonovel:next` is
  teaser-aware** — new `next_actions._teaser_actions` surfaces the teaser
  flow's next step (beats→shot-prompts, BLOCKED gate→teaser-revise,
  READY→teaser-render, clips→teaser-assemble; silent when no teaser or the
  cut is assembled), so `next` no longer ignores teaser work. New tests:
  `test_teaser_negative.py` (7), `test_teaser_next_actions.py` (7). No
  existing behaviour changed. Doc-sync: teaser-render.md, shot-prompts.md,
  teaser-critique.md, teaser-craft.md (§4/§9), commands.md (render + next
  rows), STATE. `autonovel install` re-run. Regression gate: **Tier 1+2
  1800 passed, 1 skipped, 0 failed.**

- 2026-06-07 (shot-prompts authors the spine when beats.md lacks one):
  command-body fix. Root cause of "I ran shot-prompts but the spine was
  still missing / teaser stayed boring": `shot-prompts` only *copied* the
  spine from `beats.md`'s `## Spine` block — so an OLD beats.md (pre-Phase-6,
  no spine) silently yielded a spineless teaser.json and a BLOCKED gate.
  Fixed: step 4 now instructs shot-prompts to **author the spine itself**
  from treatment/outline/canon when beats.md has no `## Spine` block, so a
  re-run of shot-prompts alone produces a complete spine + READY gate.
  Acceptance updated ("ALWAYS carries a spine"). Doc-only/command-body; no
  Python change. `autonovel install` re-run. Gate unchanged: **1800 passed,
  1 skipped.**

- 2026-06-07 (fresh-run reset, keep refs): additive. New
  `takes.reset_teaser` + `teaser-reset` CLI + `/autonovel:teaser --fresh`:
  archive every teaser artifact (beats/teaser.json/shots/clips/critique/
  cut_list/music/reports) to `teaser/reset-archive/<UTC>/` EXCEPT the
  approved `refs/` + `refs.yaml`, then rebuild from the top (treatment via
  `--with-treatment`/separate, beats→shots→critique→revise→READY).
  Non-destructive (moves, never deletes); a second reset doesn't nest the
  prior archive. `--fresh` implies `--force`. Lets a clean run keep only the
  expensive hand-approved references. ALSO (paired with the prior commit):
  `shot-prompts` now authors the spine when `beats.md` lacks a `## Spine`
  block — so the "ran shot-prompts but the teaser stayed boring against an
  old beat-sheet" failure can't recur. New tests: `test_teaser_reset.py`
  (5). Doc-sync: teaser.md, commands.md (orchestrator + new mechanical row),
  shot-prompts.md, STATE. `autonovel install` re-run. Regression gate:
  **Tier 1+2 1805 passed, 1 skipped, 0 failed.**
- 2026-06-08 (movie-teaser Phase 11 — storytelling QUALITY, the "it's
  boring" fix): structure was a floor, not quality — a teaser passed every
  Phase-6 gate and was still flat. Added a **second render gate** that makes
  "boring" a measurable, blocking failure. New `teaser/quality.py`: an
  eight-dimension interestingness rubric (hook_grip, question_sharpness,
  stakes_escalation, character, dialogue_quality, surprise_turn, coherence,
  button) **scored 1-10 by the LLM judge** in `teaser-critique` →
  `teaser/quality.json`; Python only validates the structure and computes
  the gate (overall ≥ 7 AND no dimension < 5) in one place (`teaser-quality`
  CLI), shared with the render gate (per `feedback_avoid_brittle_python`:
  taste stays with the LLM). `teaser-render` refuses a real generation when
  the scorecard is missing/below-bar (real backends only; `stub`/`--shot`/
  `--skip-narrative-gate` exempt; `--dry-run` reports `quality_gate_blocks`/
  `quality_overall`). Data model (additive, omitted-when-empty): spine
  `turn` (midpoint reversal) + per-shot `character_beat` (want/cost);
  advisory `no-turn`/`no-character-arc`. Pacing reworked for long runtimes
  (`movements` + length-scaled `dialogue_target` + gentler avg-shot curve).
  New `/autonovel:teaser-brief` distils treatment → `teaser/brief.md` before
  beats; `teaser-beats`/`shot-prompts` author the turn + character beats +
  scaled dialogue; `teaser-revise` lifts the weak dimensions + runs the
  adversarial de-boring pass (`--deboring`) and re-scores; the `teaser`
  orchestrator + `/autonovel:next` + lifecycle next-step are quality-gate
  aware. Few-shot worked beat-sheets + the rubric in teaser-craft §11.
  Doc-sync: all command bodies, teaser-craft.md, commands.md, help.md,
  README.md, templates/series/CLAUDE.md, prd + impl-plan, FUTURE-TODOS,
  STATE; `autonovel install` re-run. Maps the FUTURE-TODOS 8-point plan
  (1 quality gate · 2 micro-arc/turn · 3 dialogue · 4 character · 5
  use-the-180s · 6 brief · 7 few-shot · 8 de-boring). Regression gate:
  **Tier 1+2 1831 passed, 1 skipped, 0 failed.**

- 2026-06-08 (movie-teaser Phase 12 — legibility + honest grading): a full
  Fugger run on Phase 11 STILL shipped a terrible teaser that self-scored
  7–9. Root cause from the real artifacts: 9 of 23 shots were OBJECTS (a
  ledger, a riderless horse, seven wax seals), named figures had no
  identification, 12 text cards papered over it — and `quality.json` graded
  the *script's intent* (which the model could see) not a stranger's
  *experience*. The self-score was circular. Fix: an **external, viewer-blind**
  half to the gate — `quality.json` schema /2 carries a per-shot `legibility`
  read (`clear/who/what/why`) the LLM judges from ONLY the perceivable layer
  (visible action + spoken line + on-screen card, names/spine/beat-notes
  hidden), plus `viewer_takeaway` + `would_watch`; `QualityScore.passes()` now
  requires the dims AND every scene legible AND would_watch, so an illegible
  "tour of objects" can no longer self-pass; the render gate enforces it.
  Supporting craft: `Shot.identify` (a figure's first-appearance lower-third,
  burned by `teaser-assemble` always, ~2.5 s), advisory `instrument-only-shot`
  / `unidentified-figure` candidate-generators (NOT gates — per
  feedback_avoid_brittle_python the LLM legibility read is the real judge),
  `cast-sprawl` now counts only real people (objects can't be rationalised as
  cast), `thin-text-cards` REMOVED from the story gate + advisory
  `too-many-cards` added (cards were a crutch; meaning rides spoken dialogue +
  more characters speaking, per user), and reading `project.yaml :: genre` to
  build in the book's actual idiom (historical *fiction*, not documentary, not
  generic montage — the user corrected a documentary over-swing). Doc-sync:
  teaser-craft §11, all teaser command bodies, commands.md, help.md, README,
  templates/series/CLAUDE.md, prd + impl-plan, FUTURE-TODOS, STATE;
  `autonovel install` re-run. Regression gate: **Tier 1+2 1841 passed, 1
  skipped, 0 failed.**

- 2026-06-08 (movie-teaser Phase 13 — the AI-video SHORT): even with Phases
  11+12, a full Fugger run was STILL incoherent (no plot/character/cohesion).
  Diagnosis: the *shape* fought the medium. AI video has continuity inside a
  clip and NONE between clips (a character drifts by shot four), so a 180s,
  30-shot montage is 30 unrelated images — nothing to cohere. Research (No
  Film School, 2026 AI-short workflows, character-consistency writeups):
  narrative shorts live at 45–60s / 6–12 shots, carried by ONE first-person
  voiceover spine (Goodfellas/Shawshank — fiction, not documentary). User
  picked: one pipeline + a `mode` knob (default short), 60s default. Added
  `Teaser.mode` (short|trailer, omitted when default), `Spine.narrator`,
  per-shot `Shot.voiceover`; `beats.plan(mode)` → short = 6–12 shots (hard
  cap 12) + longer avg + `voiceover_target` + warn >90s, trailer = the old
  montage budget; mode-aware `critique` (short does NOT gate on thin-dialogue
  since the VO carries it — adds advisory no-narrator/thin-narration/
  too-many-shots; trailer keeps thin-dialogue); the viewer-blind legibility
  read now counts the `voiceover` as perceivable and reads the VO spine
  end-to-end for cohesion. Defaults moved 90→60. All command bodies thread
  `--mode`; teaser-craft §12. Render/identity-drift deliberately OUT of scope
  (user: video quality is the lesser problem). Doc-sync: all teaser command
  bodies, teaser-craft, commands.md, help.md, README, templates/series,
  prd + impl-plan, FUTURE-TODOS, STATE; `autonovel install` re-run.
  Regression gate: **Tier 1+2 1852 passed, 1 skipped, 0 failed.**

- 2026-06-09 (edge-tts dependency + first real VO audio): added `edge-tts>=6`
  to the `[video]` optional extra in pyproject.toml (lazy-imported by
  teaser/vo.py; base install unaffected). Installed it and generated the first
  REAL narration MP3 for the Fugger short via `teaser-vo --provider edge`
  (free, no key, en-GB-RyanNeural, 54.9s — fits the 60s cut). Confirmed the
  pre-existing voice system is the ElevenLabs audiobook pipeline (paid); edge
  is the free path. (The Fugger short was also rebuilt fresh to 60s with a
  concrete VO budgeted to the cut.)
- 2026-06-09 (free teaser VO + book concreteness review): two follow-ups the
  user asked for after the Phase-13 short. (1) **Free VO/TTS** — new
  `teaser/vo.py` (mirrors music.py) + `teaser-vo` CLI synthesizes the
  voiceover spine from the shots' `voiceover` lines: `stub` (offline silent
  $0) / `edge` (free Microsoft Edge TTS, **no API key** — the easy default,
  injectable synth seam for tests) / `elevenlabs` (paid, reuses the audiobook
  account; injectable httpx client). Wired into assembly: `CutList.
  narration_track` + `teaser-cut-list --narration` + `teaser-assemble
  --narration`; the narration is laid over the cut as the PRIMARY voice and a
  music bed ducks UNDER it (sidechain). The audiobook pipeline's ElevenLabs
  is paid; edge is the free path the user wanted. (2) **Concreteness review
  on the BOOK pipeline** — new `mechanical/vagueness.py` candidate-generator
  scanner (filler nouns / empty intensifiers / empty evaluatives / hedges;
  advisory, NOT a gate, per feedback_avoid_brittle_python) + `/autonovel:
  vagueness` command + a **`concreteness` dimension in `/autonovel:evaluate`**
  (LLM classifies each candidate vague-vs-earned and names the concrete
  specific) + ANTI-SLOP.md "vagueness is slop" section. Additive — no book
  tool changed behaviour. New tests: test_teaser_vo.py (11), test_vagueness.py
  (6). Doc-sync: commands.md, help.md, ANTI-SLOP.md, evaluate/teaser-assemble
  bodies, FUTURE-TODOS, STATE; `autonovel install` re-run. Tier 1+2: 1852 →
  1875. Open: VO timing must be budgeted to the cut (the Fugger VO ran ~119s
  vs a 58s cut).
- 2026-06-09 (teaser VO craft — "concrete, not cryptic"): hand-running the
  Phase-13 short on the Fugger book surfaced a writing flaw the user caught —
  VO lines like "I bought speed" / "the page no one read" / "money moves
  faster than men" have a ring but a fuzzy meaning a modern viewer can't
  decode. Encoded the rule (prompt material, not Python — it's a taste/clarity
  judgement for the LLM, per feedback_avoid_brittle_python): every VO line
  must be self-explaining to a modern stranger on first hearing — plain
  cause-and-effect, concrete nouns, the actual thing that happened. Added to
  teaser-craft §12, shot-prompts (VO authoring), teaser-critique (the
  viewer-blind read marks cryptic VO as NOT clear), teaser-revise (cryptic-VO
  fix). No test/green-count change. `autonovel install` re-run.

- 2026-10-12 (book-scoped canon + isolated context — rewrite support):
  pre-work for a second version of the Fugger novel in the SAME series
  (same POV, same years, new outline / voice / pacing). Audit found two
  structural gaps: (a) `shared/canon.md` had grown to ~45k words / ~450
  bullets, most promoted from book-1 prose or outline (a locked coffer, a
  favour never repaid) and read as SERIES canon by every draft; (b) the
  story-time spoiler gate made every old chapter legal sibling context for a
  same-range book, with no opt-out. Decisions: **canon is book-scoped** —
  new `books/<book>/canon.md` (template + `BookLayout.canon_file`) holds
  facts a book's prose fixed; `shared/canon.md` keeps series-wide facts
  (history, world, research-cited). `promote_canon.py` routes
  chapter-derived → book, `[research:*]` → shared (`--scope auto|book|series`
  override), classifies against shared + the book's OWN canon only (a
  rewrite may diverge from the original freely), and writes `## Superseded`
  blocks into the file that held the old line. Readers updated together
  (producers AND consumers): context_loader, draft / revise / evaluate /
  compare-models / add-subplot / foreshadow / deepen-character / talk /
  treatment / glossary / appendix / impact-of / rename-character /
  draft-pass / revision-pass / research / import-book / help / gen-canon
  (outline-committed facts → book half; shared half not rewritten once
  populated) / run-pipeline (2nd book skips gen-world / gen-characters),
  impact.py, entity_track, doctor (warn on missing book canon), TUI.
  Migration: `autonovel canon-partition` (housekeeping/canon_partition.py)
  moves `(from <book> ch_NN)`-tagged bullets mechanically and reports
  untagged leftovers; `/autonovel:canon-partition` (new command, standard
  tier) LLM-classifies them and feeds `--move-key` / `--move-section` back —
  the LLM never hand-edits canon. **Isolated context**: `project.yaml
  books[].context: series|isolated` (`new-book --isolated`, validated);
  the loader withholds every sibling chapter and notes it; `draft.md` step 9
  honours it. **Rewrite tooling**: `evaluate --compare N,M --vs-book
  <other>` (cross-book head-to-head, `winner_book`); `series-arc` lists
  `overlapping_books` and exempts the clock reset at a boundary between
  books with overlapping `story_time_range`s. **Hygiene from the live
  series audit**: `status` phase = max(state.json, project.yaml, on-disk
  inference) so a 24-chapter book no longer shows `seed`;
  `.autonovel/session-notes/.gitkeep` at scaffold + `_begin` self-heal
  (empty dir untracked by git → doctor PROBLEM after clone). Docs:
  multi-book.md (book canon, isolated, new "A rewrite" section),
  series-layout, commands.md, templates/series/CLAUDE.md, REWRITE-PLAN §6/§7,
  README, operating-guide, writing-a-historical-series, help topic
  `rewrite`, FUTURE-TODOS. Tags `prior_to_new_booksupport` on both the
  codebase and the series repo mark the state before this work. Applied to
  the live series: 380 bullets moved (360 by tag, 11 by section, 9 by key);
  shared/canon.md 45,538 → 3,675 words. Regression gate: **Tier 1+2 1908
  passed, 1 skipped, 0 failed** (+33: promote_canon 8, canon_partition 10,
  context_loader 1, series_arc 2, scaffold 2, project 1, status 3,
  lifecycle 1, new command contract pickups).
- 2026-10-13 (foundation order: book canon AFTER the outline): while
  creating the Fugger rewrite as book `kingmaker` in the live series, the
  documented recipe (voice-discovery → `gen-canon --book` → gen-outline)
  turned out to be wrong in practice: `gen-canon`'s book half is extracted
  FROM `books/<book>/outline.md`, so run before the outline it seeds
  nothing, and `/autonovel:next` never asked for it afterwards (its gap
  chain only checked `shared/canon.md`). Decision: the canonical chain is
  world → characters → voice → **shared** canon → outline → **book**
  canon (`gen-canon --book`) → evaluate. `lifecycle._foundation_gap` gains
  the sixth step, guarded so it only fires while the book has no chapters
  (a book drafted or imported before book-scoped canon existed must not be
  told to re-seed; promote-canon owns the file once drafting starts).
  Docs synced: help (foundation list + `rewrite` topic, which now also
  points at `add-character --book` for the rewrite's new people),
  multi-book, operating-guide (3 places), README, writing-a-historical-
  series, run-pipeline, gen-canon purpose. Tests: lifecycle chain test +
  integration seam test extended; late-stage fixtures unchanged thanks to
  the chapter guard. **Tier 1+2 1908 passed, 1 skipped** (count unchanged;
  two existing tests extended). Live-series note: book `kingmaker`
  (isolated, 24-chapter outline, two POVs) was created with the lifecycle
  log intact by wrapping each foundation write in `_begin`/`_end`; two
  book-1 inventions (`Matthäus Schwarz age`, the 6–1 `Frankfurt election`
  tally) were moved out of shared canon with `canon-partition --move-key`.
- 2026-10-13 (promote-canon "same fact" test): the first live promotion of
  29 research-cited facts for `kingmaker` dry-ran as **28 supersedures**:
  `_looks_contradictory` called any two lines sharing two 4+-letter
  tokens with disjoint years a contradiction, and research-tagged entries
  win contradictions, so `[Battle of Calliano] … 1487 … Venetian force`
  would have retired `[Fugger Venice loss, 1477]`, and `[1498 copper
  syndicate]` would have retired the *Höchstetter* paragraph in
  characters.md on the strength of the word "house". The same misfire had
  already written a bogus `## Superseded 2026-04-29` block into the live
  series' shared canon (marking `[Jakob Fugger birth]` superseded by 1519
  election facts); that block is now replaced by an audit note in the
  series. Decision: "same fact" is judged (1) by matching `[Key]` headline
  (then ANY number/year/negation difference is a contradiction), (2) for
  differing keys only on overwhelming overlap (≥4 shared informative
  tokens, Jaccard ≥ 0.5), (3) for unkeyed prose on Jaccard ≥ 0.3 with
  series-ubiquitous tokens discounted — learned from the corpus
  (`_common_tokens`: on ≥5 lines and ≥15% of them), not a hardcoded
  stop-list. Wrapped prose is compared as whole paragraphs (`_units`), not
  70-character physical lines. Dry-run after the fix: 29 promoted, 0
  supersedures, 0 conflicts. Four regression tests added; promote-canon.md
  step 4 describes the rule. **Tier 1+2 1912 passed, 1 skipped.**
- 2026-10-13 (foundation score never read): after the kingmaker
  foundation eval logged 7.82 (threshold 7.5) the `_end` footer still
  said "foundation below threshold; re-evaluate". `lifecycle.compute_next`
  loaded `last_chapter_score` from eval logs for drafted books but never
  loaded `foundation_score`, so `next_step`'s foundation branch could not
  recommend `draft 1` — the same bug class fixed for chapters on
  2026-04-28. Decision: `_last_foundation_score` reads the newest
  `<ts>_foundation.json` (`overall_score`) when the book has no chapters
  and the phase is foundation. New lifecycle test
  `test_foundation_eval_score_unlocks_draft_one`. **Tier 1+2 1913
  passed, 1 skipped.**

- 2026-10-13 (register precedence: voice.md over CRAFT.md): the first six
  kingmaker chapters came out in a compressed literary-historical
  register (riddle openers "The slate … had a city on it", metonymy "a
  clean hand", epigram closers) despite a voice file asking for plain
  contemporary English, and the judge scored them 7.3–7.9. Root cause:
  CRAFT.md §6 presented one genre's aesthetic (Le Guin, "style IS the
  fantasy", "a register appropriate to the world", surprise / subtext /
  restraint) as universal craft, §3 and §5 and ANTI-PATTERNS §1/§4 pushed
  the same way, and nothing said the book's voice file outranks them.
  Decision: CRAFT.md gets a scope-and-precedence header, §3/§5/§6/§7/§8
  rewritten register-neutral (register is the book's choice; clarity is
  a universal; a "register tells" list names the model's literary
  defaults), ANTI-PATTERNS §1/§4 softened, and `draft.md` step 10 /
  `revise.md` step 7 state that voice.md Parts 1–3 win on conflict. The
  book voice template's Part 1 comment now tells authors to list
  overrides. Live series: kingmaker voice.md carries explicit overrides,
  a register test, a not-this/this pair from the actual draft, and a
  Part 3 "Register test" criterion; chapter 2 revised as the proof.

- **2026-10-14 — Craft docs reach the writer; sourced PROSE.md.** The
  author, after a third prose complaint in two days ("too much short
  conversation", then "disconnected statements"): "it feels like I/we
  are making up how to write prose on the fly … review online
  literature guidance for writing fiction perhaps?" Root cause, found
  while wiring the fix: CRAFT.md / ANTI-SLOP.md / ANTI-PATTERNS.md lived
  only at the repo root; `draft.md` said "Obey ANTI-PATTERNS.md" with no
  path; nothing installed them anywhere a series session could read;
  the series CLAUDE.md template never mentioned them (and the live
  Fugger series had no CLAUDE.md at all). Every chapter had been drafted
  from `voice.md` alone, and the voice file had accreted one invented
  rule per complaint. Decision: (1) the craft docs become a series
  template subtree `templates/series/shared/craft/` (source of truth;
  repo-root files are symlinks), copied by `new-series`, refreshed by
  `refresh-templates` (default scope now `typeset` + `shared/craft`),
  checked by `doctor` (missing / stale warnings); `draft`, `revise`,
  `evaluate` read them at `shared/craft/<name>` and run the refresh
  themselves if the folder is missing. (2) New `PROSE.md`, built from
  two web-research passes over the craft literature: known-new contract
  (Williams, Gopen & Swan, Pinker), paragraphs (Le Guin, Prose, Harnby),
  rhythm as variance (Provost, Le Guin, Follett), psychic distance and
  free indirect (Gardner, Darwin, Wood), scene as cause-and-effect
  chain (Swain, Bickham, Ingermanson, McKee's turn test, Follett's
  turn every 4–6 pages, Child, Bell, Vonnegut), dialogue (Browne &
  King, Stein's four questions, Leonard, Turkey City, George),
  information (Darwin, Harris, Palahniuk), endings; a §9 folklore list
  (genre sentence lengths, dialogue percentages, chapter lengths, "the
  epigram closer") so pipeline heuristics are labelled as such; a §10
  judge checklist. (3) The book voice template's Part 1 tells authors
  to record register, not re-derive mechanics. Live series: kingmaker
  voice.md Part 2 reduced to reader / register / tuning fork /
  "Calibration for this book" (numbers labelled as this book's
  choices) with mechanics delegated to PROSE.md by section; a fourth
  "Not this" failure (statements with no joins, paragraphs split to
  game a dialogue count) recorded with its chained rewrite. Tests:
  `test_craft_docs.py` (template ships all four; root symlinks resolve;
  new-series copies; doctor missing / stale / quiet; refresh restores;
  prose commands name the series path) and the refresh default test
  rewritten. Open items in FUTURE-TODOS near-term.

- **2026-10-14 (later) — Register is measured, not guessed.** After the
  craft docs reached the writer the author still heard "1500s style"
  and asked why the harness had not found it: "you should be finding
  these via the autonovel harness already — why didn't it find it? fix
  the underlying issues." Quoted line: Tucher telling Jakob "That's San
  Giacomo's bell, at the end there, and you've got a quarter of an hour
  before it rings." Diagnosis: (a) the judge is the writer's own model
  prompted as a literary critic; no persona asks "would this person say
  this to that listener?"; (b) the pipeline steered by invented counts
  (dialogue ≥30% of words) and the writer gamed them by moving
  narration into mouths; (c) the only register instrument,
  `syntax-drift`, baselined against the voice file's OWN prose (a rules
  document) and was wired into nothing; (d) word-list scanners cannot
  see grammar. Measured: narration contraction ratio 0.0 in five of six
  chapters (27 uncontracted negatives, 0 contracted in ch 4); FK grade
  4.2–4.9 overall, 5.2–5.8 narration; 11 utterances over 40 words in
  ch 1, mean utterance 22 words. Decision: new `autonovel mechanical
  register` (narration vs dialogue split; FK each; contraction ratio and
  every uncontracted negative; formal connectives/tags; fronted openers;
  elliptical participles; utterance count/mean/long; listener-explaining
  candidates) as a candidate generator; `syntax-drift` baselines on a
  declared `FK grade band: L–H` line in voice.md (seed.txt next, voice
  prose last with a warning); `evaluate --chapter` gains a `register`
  dimension judged AS A COPY EDITOR in the book's declared register,
  emitting `register_edits` (quote → rewrite) that `brief` copies into
  `## Register edits` and `revise` applies as line edits; `draft` and
  `revise` run the scanner on their output before writing the summary;
  `voice-discovery` writes the band, the model authors, the contraction
  policy and a 150–300-word sample that passes the scanner; the book
  voice template documents the band line. Tests: `test_register.py`
  (9), syntax-drift baseline order rewritten (band > seed > voice prose
  > median). CRAFT.md §6 gains the "formal grammar under modern
  vocabulary" register tell; the operational register spec (sourced
  markers and bands) follows from the research pass in progress.

- 2026-10-14 (the editorial letter reaches the rewrite): the first
  reader-panel + review on kingmaker ch 1–6 after the register pass
  found no register faults and a unanimous set of structural ones (a
  chapter-ending clock paid offstage in the next chapter's opening, the
  act's pivot told in pluperfect and labelled, scene openers on the
  same announced want, confrontations in indirect speech, a motiveless
  antagonist). Per-chapter evals scored 8.6–8.8 because every fault
  sits between chapters or between a rule and its literal reading
  (voice.md asked for the want "named" → "What Jakob wanted was…";
  PROSE §6.5 "summarise information exchanges" → confrontations
  summarised). Pipeline gaps found while tracing it: `brief` read the
  panel but not `review.json`, so the professor's numbered items never
  reached `revise`; `next`, the TUI, `draft-pass` and the operating
  guide watched `edit_logs/opus_review.md` while `review` writes
  `review.md` + `review.json`; nothing checked that a clock set in one
  chapter is paid on the page. Decisions: `brief` gains `--from review`,
  merges review items in `auto`, and emits `## Structural findings`
  (scene instructions, outranking line edits, allowed to grow the
  target length); every consumer follows the producer to `review.md`
  with a legacy fallback to `opus_review.md` in `next_actions` and the
  TUI; `evaluate` gains `clocks_paid` in `--phase foundation` (outline
  beats) and `--full` (chapter closings/openings) with a per-clock
  ledger and `unpaid_or_summary_clocks`; PROSE.md §5 gains rules 8
  (clocks paid as scenes) and 9 (the chapter's turn is a scene, not a
  pluperfect report), §5.1 names the announced-want shape, §6.5 names
  the reverse failure (confrontation as indirect speech), §10 gains
  four checklist lines; CRAFT.md §4 gains rule 3 (clocks). The
  structural layer is the trade's developmental edit: outline = beat
  sheet, panel + review = editorial letter, brief = revision letter,
  revise = the rewrite; the missing piece was the letter reaching the
  rewrite.
- 2026-10-15 (promise lines and glossing): the author's own read of
  kingmaker ch 1–9 found no foreshadowing ("a story of a young merchant
  boy in Venice"), unglossed names (SCUTARI chalked on a slate), unrelated
  coins, an event arriving unseeded, and six wagers with no felt spine.
  PROSE §7 rule 3 had banned all forward-pointing on Emma Darwin's
  authority; that conflated a character's clairvoyance (still banned)
  with the narrator's promise line, which commercial fiction uses
  (Follett; Sanderson's promises; Vonnegut rule 8). Decision: §7.3
  distinguishes the two and admits a declared promise line once a
  chapter; new §7.4 glosses every proper noun where it first appears;
  §10 gains spine and glossing checks. The book-level rules (spine,
  Venice on the page, money glossed, letters in italics) live in the
  kingmaker voice file, not here.
- 2026-10-17 (`/autonovel:diff`: what changed, word by word, in one
  page): the author could only check discussed edits with line-based
  `git diff` (a one-word trim lights a whole paragraph; no reading
  surface). New `autonovel mechanical diff-chapters`
  (`mechanical/bookdiff.py`): difflib paragraph alignment, then
  monotonic pairing of similar paragraphs (1:1, split 1:2, merge 2:1;
  ratio 0.4, calibrated on kingmaker where unrelated paragraphs top out
  at 0.33), then word-level diff with semantic cleanup; moved paragraphs
  tagged. Versions: git ref/tag, `last-tag` (default from), `last-read`
  bookmark (`edit_logs/last_read.json`, written by `--mark-read`),
  `checkpoint:<ts>|latest`, `worktree` (default to). Output is one
  self-contained HTML page (j/k jumping, "change N of M", folded
  context, word deltas, a foundation section) plus a JSON sidecar;
  `--annotate` adds a fingerprint-checked one-line "why" per change
  traced to brief / talk turn / review item. Zero-LLM without
  `--annotate`. Series `.gitignore` drops the regenerable pages.
- 2026-10-17 (book-level structure tier, "review the reviewers"): the
  author's read of kingmaker ("a bunch of short anecdotes, not a
  continuing story building to a climax") contradicted every reviewer:
  chapter evals 7+, review 4★ for ten passes, panel "all four would buy
  it". Audit in `docs/reviewer-audit.md`: no rubric asked a causal
  question; chapter-tier rules reward self-contained wagers; plant/payoff
  and promise-line ledgers were read as architecture; review's stop rule
  counted the hedged structural item toward stopping; `evaluate --full`
  was blind and never run. Decision: a new heavy command,
  `/autonovel:structure-review`, not a review mode (own inputs, "happens
  after" by default, reads other reviewers only after scoring,
  machine-readable output). Mechanical support is data and consistency
  only: `structure-dossier`, and `structure-validate` (shape, scoring
  caps over the reviewer's own tables, the gate). review's
  stop_revising requires the gate (fresh, valid, score ≥ 4, no removable
  chapter); structural items are never qualified. reader-panel adds four
  book-level questions. `evaluate --full`: 15 weighted dimensions,
  structure 50%, novel score ≤ structure subscore + 1.0; foundation
  adds `causal_spine`. brief writes `kind: structural` briefs; revise
  restructures inside one chapter and prints cross-chapter commands;
  `revision-pass --chapters structural`. gen-outline writes Spine /
  Stakes ladder / Causal spine (`--add-spine`); draft holds to it;
  draft-pass spine check and `--deep`. Integration rule: prompt
  material (command bodies, shared/craft) never names a specific book
  or quotes its verdict, since that primes every later run on that book
  toward the expected answer; the history lives here and in the audit.
- 2026-10-17 (story map: see the book's shape without re-reading it):
  the author on kingmaker could not see how the plot develops.
  `/autonovel:story-map` + `autonovel mechanical story-map` write one
  self-contained `edit_logs/story_map.html` (+ `.json`) from material
  already on disk: synopsis in reading order under the outline's act
  headers (with a one-line-per-chapter skim), a threads × chapters grid
  (plant / turn / payoff / touch) with score / tension /
  irreversible-change curves on the same axis directly underneath,
  characters' presence and state changes, a story-time axis with
  >1-year gaps labelled, places visited vs named-only. Threads come from
  a new hand-editable `books/<book>/threads.md` ledger (exact grammar;
  the LLM writes it from outline + summaries on first run or
  `--refresh-threads`, never from prose), else an outline `## Threads`
  ledger, else `events:` ids. Data, not verdicts. Reuse over
  duplication: `parse_summary_sections()`,
  `_index_latest_per_chapter_eval(key=…)`, `parse_cast_ordered()`,
  `dashboard.build_dashboard`. Kingmaker's outline has no thread ledger;
  its synopsis reads in 18 min full, 2 min skim.
- 2026-10-18 (the editor's read as a skill; "learn to be the writer,
  editor and critic"): the author, who is not a writer, said it should not
  be him supplying review methods, and that the top priority is for the AI
  itself to learn to write, edit and criticise. A full cold read of
  kingmaker by the integrator (not delegated) and a ranked developmental
  letter found what four stars hid: narrator flash-forwards in 19 of 24
  chapters (the 2026-10-15 promise-line rule, the integrator's own
  mistake: prolepsis is not foreshadowing), year-plus resets at 14 of 23
  joints, an unattacked misbelief, a single win-by-noticing engine, no
  lasting opponent. Decisions: (1) `/autonovel:developmental-edit`
  encodes that read — one reader, cold, fixed per-chapter notes, a
  measurement pass, a one-page test, an intent pass, a ranked letter, and
  comparison with the instruments only afterwards; `--stage` queues
  in-chapter fixes in `briefs/conversation.md`. (2) The sourced study
  text (Parts 0–VI, ~22k words: passes, the letter, P/S/SC/C/A/V/T/G/R/O/E
  questions, historical fiction, the thriller, case studies, where AI
  editors fail) ships as `shared/craft/EDITING.md` (fifth craft doc);
  its pipeline audit stays in `docs/editorial-practice.md`. (3) PROSE.md
  §7.3: the story is lived forward; no narrator forecasts by default
  (Stone, Mantel), replacing one-promise-line-a-chapter. (4)
  `autonovel mechanical prolepsis` counts candidate forecasts (candidate
  generator, not a gate). `/autonovel:next` suggests the read on a
  drafted book (MEDIUM) and a re-read after chapters change (LOW).

### 2026-10-18 — `/autonovel:diff` rebuilds and links the story map

The author opened the diff page expecting the storyline, characters and
places there ("I thought they were going there?"). The story map was a
separate page nothing linked, and had never been built for kingmaker:
built in parallel, the cross-link stayed a FUTURE-TODO. Now
`diff-chapters` rebuilds `story_map.html` beside every diff page and the
two link each other (toolbar button + per-chapter links in the diff;
"N changes" on changed chapters in the map; a standalone story-map run
links the newest diff in its folder). A story-map failure is reported in
the JSON and never fails the diff. Lesson: a tool built for the author
is not shipped until it is reachable from the page the author already
opens.

### 2026-10-18 — `/autonovel:design`: the book is designed before it is outlined

After four in-chapter revision rounds on kingmaker moved causal links
15→23 of 23 and removed every flash-forward, four cold reads still found
17 of 24 chapters opening and settling their own contest: the fault was
the design (a life told contest by contest under a seed rule that every
chapter is a wager). The author then said what the book should be (the
skills young Jakob learns as plants for a climax in which he buys the
election, tension and skulduggery, a modern fuller voice, rich places,
characters alive, smart moves on early knowledge rather than bets) and
asked for the design stage first, then a redo.

Shipped: `shared/craft/DESIGN.md` (sixth craft doc; the author's half of
EDITING.md: climax first, one action through a long span — education
and campaign, many locks, rehearsal ladder, long project with recurring
rival, intercut, late start — suspense with a known outcome, the
competent protagonist and fair play, the rival with a dated plan, the
cast web and what makes characters come alive, plants inside contests,
rehearsals, sequences, place, voice, earned outcomes, tests D1–D14, and
re-designing a drafted book); `commands/design.md` (heavy; climax-first
decisions into a parseable design.md; self-tests; a cold second reader
for D14; `design-validate`; `--from-book` creates an isolated new book,
copies art, reads letters and summaries never chapters, writes keep and
fault ledgers and the new seed; `--notes` = the author's words, which
win); `mechanical/design.py` + `design-validate` (structural promises;
`--outline` checks the outline lists every plant/test/payoff on its
chapter); `gen-outline` heavy and bound (sequence/plants/tests/payoffs
bullets per chapter, plates reassigned on a re-design); `draft` step 3b
(cast signatures and wants, places through the POV's attention, plants
never announced, wins by knowledge); `evaluate --phase foundation`
gains `design` (structure 35%); the foundation gap order
(canon → design → outline, only for undrafted books); `/autonovel:next`
design actions; `developmental-edit` routes design-level diagnoses to a
re-design. Decision: the validator checks shape only; whether the design
is good is the designer's and the cold reader's call (no brittle
quality gate).

## Tests last known green
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-18 (design) —
  **2128 passing, 1 skipped**. +19: `test_mechanical_design.py` (10),
  three `/autonovel:next` design tests, 6 per-command tests for
  `/autonovel:design`; the two foundation-chain tests now walk
  canon → design → outline.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-18 (later) —
  **2109 passing, 1 skipped**. +4: `_resolve_writes` glob test and
  `test_diff_story_map_links.py` (3).
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-18 —
  **2105 passing, 1 skipped**. +20 over the 2085 mark:
  `test_mechanical_prolepsis.py` (10), four `/autonovel:next`
  developmental-edit tests, and 6 per-command tests for
  `/autonovel:developmental-edit` (EDITING.md picked up by the craft-doc
  tests through `scaffold.CRAFT_DOCS`).
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-17 (later) —
  **2085 passing, 1 skipped**. +39 over the 2046 mark:
  `test_mechanical_story_map.py` (33) and 6 per-command tests for
  `/autonovel:story-map`.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-17 —
  **2046 passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +112 over the 1934 mark: `test_mechanical_bookdiff.py` (46) and 6
  per-command tests for `/autonovel:diff`; `test_mechanical_structure.py`
  (35), `test_structure_review_contract.py` (19) and 6 per-command tests
  for `/autonovel:structure-review`.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-14 (night) —
  **1934 passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +1 over the 1933 mark: `test_review_staleness_legacy_name` (a series
  carrying only the pre-2026-10 `opus_review.md` is still checked for
  staleness).
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-14 (later) —
  **1933 passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +12 over the 1921 mark: `test_register.py` (10: narration/dialogue
  split, formal vs spoken flagging, contraction ratio, dialogue
  negatives excluded, long-utterance threshold, curly quotes, build +
  CLI, declared-band parsing, band beats voice prose) and two
  syntax-drift baseline-order tests (seed before voice prose; declared
  band wins), one renamed.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-14 — **1921
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +8 over the 1913 mark: `test_craft_docs.py` (template ships all four
  craft docs; repo-root symlinks resolve to the template; new-series
  copies `shared/craft/`; doctor warns on missing and on stale, quiet
  when current; refresh restores after deletion; draft / revise /
  evaluate name the series path and the self-heal) and the refresh
  default-scope test rewritten for `typeset` + `shared/craft`.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-13 — **1913
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +5 over the 1908 mark: four promote-canon "same fact" regression tests
  (different keys sharing series nouns → survivor; same key different
  day → contradiction; wrapped prose compared as a paragraph; common
  tokens learned from the corpus) and one lifecycle test (a passing
  `<ts>_foundation.json` unlocks `draft 1`).
- Tier 1 + Tier 2 (deterministic + contracts): 2026-10-13 — **1908
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  Unchanged count from 2026-10-12 (two existing lifecycle / integration
  tests extended for the sixth foundation step, `gen-canon --book` after
  the outline). The 2026-10-12 mark was +33 over 1875: book-scoped canon
  (`promote_canon.py` routing + `housekeeping/canon_partition.py` +
  `canon-partition` CLI), `context: isolated`, series-arc overlap
  exemption, status phase inference, session-notes self-heal,
  `/autonovel:canon-partition` contract pickups.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-09 — **1875
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +23 since the 1852 mark: free teaser VO (`teaser/vo.py` + `teaser-vo` CLI +
  assembly `--narration` mixing → test_teaser_vo.py 11) + book concreteness
  review (`mechanical/vagueness.py` + `/autonovel:vagueness` + evaluate
  `concreteness` lens → test_vagueness.py 6) + 2 new commands' contract
  pickups.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-08 — **1852
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +10 since the 1842 mark: movie-teaser **Phase 13 — the AI-video SHORT**.
  `mode` knob (short|trailer, default short) on one pipeline; `Teaser.mode`,
  `Spine.narrator`, `Shot.voiceover`; mode-aware planner (short = ≤12 longer
  shots + voiceover_target, warn >90s) + critique (short drops thin-dialogue
  gate, adds no-narrator/thin-narration/too-many-shots; VO counts toward
  legibility) → new test_teaser_phase13.py (16) + 2 updated. Prior mark
  1842 = cast-sprawl age-ladder collapse.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-08 — **1842
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +1 since the 1841 mark: cast-sprawl now collapses a hero's age-ladder
  (boy/man/elder = ONE face) + ignores object "subjects" — found while
  hand-running the Phase-12 pipeline on the real Fugger book as a proof.
  Prior mark 1841 = movie-teaser **Phase 12 — legibility + honest
  grading**. `quality.json` schema /2 (viewer-blind legibility read +
  viewer_takeaway + would_watch; `passes()` now requires every scene legible),
  `Shot.identify` lower-third (burned by teaser-assemble), advisory
  `instrument-only-shot`/`unidentified-figure`/`too-many-cards`,
  `thin-text-cards` removed from the gate, cast-sprawl counts only people →
  phase-11 file extended + assembly identify tests; 2 next-actions pickups
  updated. Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-08 — **1831
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +26 since the 1805 mark: movie-teaser **Phase 11 — storytelling QUALITY**
  (the "it's boring" fix). New `teaser/quality.py` (8-dimension
  interestingness rubric + HARD quality gate: overall ≥ 7, no dim < 5),
  `teaser-quality` CLI, quality gate as a second render gate in
  `teaser-render`, spine `turn` + per-shot `character_beat`, advisory
  `no-turn`/`no-character-arc`, length-aware pacing (movements +
  dialogue_target), new `/autonovel:teaser-brief`, quality-aware
  `/autonovel:next` → 17 phase-11 tests + 4 next-actions pickups + 1
  teaser-brief contract pickup (and 2 next-actions tests updated for the
  new gate). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-07 — **1805
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +5 since the 1800 mark: fresh-run teaser reset (takes.reset_teaser +
  teaser-reset CLI + --fresh) → 5 tests. Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-07 — **1800
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +8 since the 1792 mark: diegetic-text narrowing + render --revise +
  /next teaser-awareness (next_actions._teaser_actions) → +1 negative, +7
  next-actions tests. Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-07 — **1792
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +6 since the 1786 mark: render-side text-free titles + sent negatives +
  auto-regenerate (6 tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-07 — **1786
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +1 since the 1785 mark: teaser orchestrator next-step → render (Stage 3
  critique→revise loop). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-07 — **1785
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +12 since the 1773 mark: teaser revise-loop (new teaser-revise command +
  4 contract pickups, critique verdict) + richer stub scene cards → 6
  deterministic + 6 contract. Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-07 — **1773
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +6 since the 1767 mark: run-feedback fixes (refs --init --force preserve
  + teaser-flow next-step + gate message → 6 tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1767
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +5 since the 1762 mark: Phase 10 directory-nesting clarity (looks_doubled
  + doctor checks → 5 tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1762
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +9 since the 1753 mark: movie-teaser Phase 9 (music-generation backend:
  stub silent-WAV + musicgen/elevenlabs + audio.music line → 9 tests).
  Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1753
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +9 since the 1744 mark: movie-teaser Phase 8 (mixed assembly + burn-in
  title cards → 9 tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1744
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +12 since the 1732 mark: movie-teaser Phase 7 (locations as refs +
  appearance age ladder + refs to video backends → 12 tests). Prior
  marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1732
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +26 since the 1706 mark: movie-teaser Phase 6 (all 12 best practices:
  story spine + 4-act order + stakes ladder + genre + dialogue mining +
  text cards + restraint/cast + render gate + script versioning → 26
  tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1706
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +10 since the 1696 mark: movie-teaser Phase 5.9 (score policy + audio
  seam-fades + Veo fixed-duration snap → 10 tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1696
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +8 since the 1688 mark: movie-teaser Phase 5.8 (versioned takes:
  takes.py + teaser-takes/teaser-take-pick + --versioned mp4 → 8 tests).
  Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1688
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +1 since the 1687 mark: Veo durationSeconds-as-int regression guard.
  Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1687
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +11 since the 1676 mark: movie-teaser Phase 5.7 (scene transitions:
  fade emission + auto-defaults + suggester → 11 phase-5.7 tests).
  Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1676
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +11 since the 1665 mark: movie-teaser Phase 5.5+5.6 (audio-to-prompt
  wiring + voice lock/age → 11 phase-5.6 tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1665
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +10 since the 1655 mark: movie-teaser Phase 5.4 (audio-bed ducking +
  native-clip-audio preservation → 10 phase-5.4 tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1655
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +8 since the 1647 mark: movie-teaser Phase 5.3 (image-to-video start
  frames: init_image on request/plan/backends → 8 phase-5.3 tests).
  Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1647
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +12 since the 1635 mark: movie-teaser Phase 5.2 (gemini reference-
  conditioned image backend + refs threading + approval-gated refs map →
  12 phase-5.2 tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1635
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +14 since the 1621 mark: movie-teaser Phase 5.1 (refmanifest.py +
  teaser-refs CLI + /autonovel:teaser-refs → 8 phase-5 tests + auto
  contract/placeholder tests for the new command). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-06 — **1621
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +21 since the 1600 mark: movie-teaser Phase 4 (backends.py multi-
  provider render + stub + model-pin flip → 22 new phase-4 tests, minus
  net adapter-test re-points). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-05 — **1600
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +16 since the 1584 mark: movie-teaser Phase 3 (assemble.py cut-list +
  ffmpeg planner + teaser-cut-list/teaser-ffmpeg-cmd CLIs + teaser-
  assemble command → 10 explicit + 6 auto contract tests). Prior marks
  below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-05 — **1584
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +14 since the 1570 mark: movie-teaser Phase 3.5 (render.py adapter +
  resolve-video-provider + teaser-render CLI + teaser-render command →
  8 explicit + 6 auto contract tests). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-05 — **1570
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +8 since the 1562 mark: movie-teaser Phase 2 (render dialects +
  refs.py reference-image plan + teaser-refs-plan CLI). Prior marks
  below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-05 — **1562
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +16 since the 1546 mark: movie-teaser Phase 1 final (teaser +
  teaser-critique commands → 12 auto contract tests + 4 explicit
  tests for the load() guard and the two command bodies). Prior marks
  below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-05 — **1546
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +31 since the 1515 mark: movie-teaser Phase 1 (teaser shots/beats/
  render/critique modules + 4 mechanical CLI helpers + teaser-beats /
  shot-prompts commands). Prior marks below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-06-05 — **1515
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  +12 since 2026-05-01: movie-teaser Phase 0 + `/autonovel:treatment`
  (project.py teaser/video round-trip + back-compat, install-
  immutability guards, treatment command contract pickups). Prior
  baseline below.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-05-01 — **1503
  passing, 1 skipped** (`pytest tests/deterministic tests/contracts`).
  Four shipped follow-ups in one batch:
  1. `/autonovel:impact-of` source extension — `rename-character`
     reads command-log for the most recent `--old`/`--new`, word-
     boundary-greps every chapter for stragglers (catches what the
     slash-command's sed missed in possessives / unicode look-alikes
     / HTML entities); `merge-chapters / reorder / remove-chapter`
     grep prose for chapter-number cross-references (`Chapter VII`,
     `chapter 7`, `ch. 12`) so a renumber doesn't leave silently-
     wrong navigational pointers (+15).
  2. `project.yaml :: typeset.chapter_titles = false` enforcement —
     `build_chapters_tex` and `build_epub_md` accept a
     `chapter_titles: bool` kwarg; CLI gains `--no-chapter-titles`
     (explicit override) and `--project-yaml <path>` (read the
     toggle from `typeset.chapter_titles`); `commands/typeset.md`
     passes `--project-yaml project.yaml` on both build paths so
     numbers-only mode now actually flows through to TOC + chapter
     pages (was documented in draft.md but not enforced) (+11).
  3. `autonovel install --dry-run` — preview the per-runtime install
     plan without touching disk; sigil flips from `+` to `~` and
     trailer line names "no files written" (+4).
  4. `project.yaml :: image.provider` wired as default —
     `ProjectConfig` gains `typeset` and `image` dicts (round-trip
     in YAML, omitted when empty); new `autonovel mechanical
     resolve-image-provider [--project-yaml ...] [--cli-provider
     ...]` helper applies the precedence rule (CLI override →
     project.yaml → `pollinations` default) in one place;
     `commands/art-curate.md` and `commands/art-ornaments-all.md`
     now invoke it instead of re-implementing precedence (+8).
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-30 — **1334
  passing, 1 skipped** (pydub absent locally;
  `pytest tests/deterministic tests/contracts`). TUI fixes (cursor
  preservation across refresh; clearer score-sparkline labels;
  `p` pause binding; copy/paste guidance in Help tab); `[export]`
  extras smoke (+2, 1 skip when pydub absent); JSON-schema
  validation of every commands/*.md frontmatter via jsonschema
  added to `[test]` extra (+72 parametrized tests, +2 sanity);
  `/autonovel:impact-of` source extension to `gen-canon` (canon-
  driven, same logic as promote-canon) and `voice-discovery /
  add-character / gen-characters / gen-world / add-source`
  (mtime-driven, lists chapters older than the foundation file)
  (+10); GitHub Actions workflows for Tier 1+2 (test.yml, every
  push/PR matrix 3.11/3.12/3.13) and smoke-weekly.yml (cron +
  workflow_dispatch, supports OAuth or API-key auth, exits 0 with
  diagnostic when no secret configured) (+7).
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-29 (late PM) —
  **1243 passing** (`pytest tests/deterministic tests/contracts`).
  Three additional commits on the workflow-guidance + tooling
  batch: `autonovel install-export-tools` interactive installer
  (+16); `/autonovel:impact-of` LLM follow-up — `--with-llm`
  classifier (HIGH/MEDIUM/LOW/FALSE_POSITIVE) and `--source
  research` mode (+4 regression locks); `autonovel tui`
  read-only terminal browser via textual `[tui]` extra, with
  Help / Chapters / Research / Foundation / Front matter /
  Reviews / Commands tabs and live next-step rationale + reads/
  writes per suggested command (+16). Doc sync follow-up
  brought docs/commands.md rows for `/autonovel:next` + `/autonovel:
  impact-of` up to date and added a CLI subcommands section.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-29 (PM) —
  **1207 passing**. Workflow-guidance batch (six commits):
  brief-newer-than-chapter signal + past-end guard in
  `/autonovel:next` (+7); postamble "💡 Maybe try:" hints (+6);
  `/autonovel:impact-of` (kills the ls/grep workflow after
  promote-canon, +21+5 contract pickups); research-notes index
  + `/autonovel:research --query` mode (+13); sweep-progress
  checkpoint for `/autonovel:resume` continuation (+18); edit-
  imported Phase 2 foundation reverse-engineering (+14 + 1
  contract pickup). Single-session delta: 1123 → 1207 (+84).
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-29 (AM) — **1123
  passing** (`pytest tests/deterministic tests/contracts`).
  FUTURE-TODOS #1 added 22; #2 added 27; #5.1 added 17 (and fixed
  a real lifecycle._last_eval_score glob bug along the way); #5.2
  added 7; #22 (per-chapter motif tracker) added 17 + 5 contract
  pickups; #3 (`/autonovel:art-prompts`) added 5 contract pickups
  for the new slash-command. PDF page-header regression fix added
  2 latex regression tests + 9 `autonovel refresh-templates`
  tests. Talk-mode added 13 entity-track tests + 5 contract
  pickups for `/autonovel:talk`.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-26 — **674
  passing** (`pytest tests/deterministic tests/contracts`). The
  2026-04-25 PM and 2026-04-26 waves added 223 tests across the
  scene splitter (14), shared frontmatter helper (6), ePub
  combiner (12), front-matter builder (12), typeset helpers (16),
  per-book metadata (9), chapter-summary helper (16 + 5 contract),
  statusline debug-capture + context-% paths (5), plus the
  Tier-2 contract auto-pickups for the new commands
  (`title`, `introduction`, `chapter-summary`).
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — **451
  passing** (`pytest tests/deterministic tests/contracts`). PR 9
  added 11 new Tier-1 tests in
  `tests/deterministic/test_test_fixture.py` covering the
  `autonovel test-fixture new|list|run` housekeeping shape: layout
  parity with `autonovel new-series`, smoke-test stub generation
  (markers + function name + fixture-name interpolation), name
  validation, idempotency-on-existing rejection, repo-root walk-up,
  and `list_fixtures` marking ✓ vs · for fixtures with/without a
  paired smoke test. The seven new fixture directories did not
  trigger any new contract tests; the existing contract suite is
  command-shape only.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — 440
  passing (`pytest tests/deterministic tests/contracts`). PR 8
  added 24 new Tier-1 tests (12 in `test_adapter_codex.py`,
  12 in `test_adapter_gemini.py`) covering render, frontmatter
  shape, backticked tool-name translation, custom model maps,
  install round-trip, install-twice idempotency, and a
  `tomllib.loads` round-trip on every emitted Gemini `.toml`.
  Earlier PR-7 line:
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — 416
  passing (`pytest tests/deterministic tests/contracts`). PR 7
  added 61 new Tier-1 tests and ~75 contract-test parametrisations
  (15 new commands × 5 parametrised checks per command):
  - `test_mechanical_spine.py` (14): spine-width by paper stock,
    cover-canvas arithmetic, pixel conversions, override precedence,
    CLI emits JSON.
  - `test_mechanical_audio.py` (24): `validate_script` shape rules,
    `chunk_segments` packing + tag-drop + fallback voice, overage
    split on sentence boundary, chapter marks cumulative + no
    trailing pause + ffmetadata format.
  - `test_mechanical_latex.py` (23): escape of the five LaTeX
    specials, scene-break / italic / dash / smart-quote conversion,
    drop-cap wrapping, multi-chapter build, ornament PDF-preferred-
    over-PNG wiring, CLI round-trip.
- Tier 1 + Tier 2 (deterministic + contracts): 2026-04-24 — 280 passing
  (`pytest tests/deterministic tests/contracts`). PR 6 added 17 new
  Tier-1 tests: 8 for the events validator
  (`tests/deterministic/test_events_validator.py` — good ledger parse,
  duplicate id detection, missing required fields, bad ISO date,
  malformed `rendered_in` row, cross-consistency against project
  books, empty document, Path accepted) and 9 for the context loader
  (`tests/deterministic/test_context_loader.py` — shared+book path
  inclusion, sibling spoiler gating, event-rendering surfacing with
  spoiler dominance, unknown book/chapter errors, missing story_time
  error, CLI success + error paths). PR 6's three new commands
  (`run-pipeline`, `reorder`, `remove-chapter`) are auto-picked up by
  the contract test. `context_loader.py` lives at
  `src/autonovel/` top level (not under `validators/`) because it
  composes shared files, book files, outline parsing, and events —
  it is a context builder, not a pure validator.
- Tier 3 (smoke): 2026-04-24 — Claude Code under subscription auth.
  - `tests/smoke/test_foundation_smoke.py` — 6/6 green (4m41s from PR 3).
  - `tests/smoke/test_revision_smoke.py` — **6/6 green (10m32s)** on
    the first clean PR-4 run. Tests:
    `evaluate_chapter`, `adversarial_edit_produces_cuts`,
    `apply_cuts_reduces_word_count`, `brief_writes_structured_brief`,
    `revise_rewrites_chapter`, `shorten_compresses_chapter`.
  Two real bugs were caught by the first run and fixed before green:
    1. `ch{chapter:02d}` placeholder had been flattened to `ch{chapter}`
       during PR 4 to satisfy a contract test. That broke the
       zero-pad-to-two-digits convention the smoke tests assert
       (`ch01_cuts.json` etc.); reverting to `ch{chapter:02d}` both in
       frontmatter and body text keeps contract and smoke tests green
       simultaneously.
    2. `/autonovel:apply-cuts` step 4 was written as a multi-line
       bash command; bash parses newlines as statement separators,
       so the model's shell invocation ran the first fragment with
       no args and tried to execute path literals. Rewritten as a
       single-line call with an explicit "do not add --dry-run" note.
  One test-harness bug was also caught and fixed:
    3. The seeded chapter body repeated a paragraph 16 times, so the
       cut-quote appeared 16 times. The mechanical module correctly
       refuses ambiguous matches. Seed now has a unique marker
       paragraph; a collection-time assertion
       (`assert _SEED_BODY.count(SEED_UNIQUE_CUT_QUOTE) == 1`)
       fails fast if future seed edits break that invariant.
- Tier 3 (PR-5 live-research smoke): 2026-04-24 — **1/1 green (2m21s)**
  on the first clean PR-5 run. `tests/smoke/test_historical_research.py`
  ran under subscription auth against live web (WebSearch + WebFetch).
  Assertions that passed: sources section present, ≥2 distinct
  `[shortname]` citations, ≥1 primary URL from `sources.yaml` echoed in
  the notes, ≥2 period-specific keywords from the generous detail list,
  uncertainty hedge present, candidate-canon section present. §12.4
  flakiness policy says this test is allowed to flake; retry-once
  policy in `tests/conftest.py` covers ordinary drift but did not
  trigger this run.
- Tier 3 (PR-6 multi-book smoke): 2026-04-24 — **1/1 green (8m16s)**
  on the first clean PR-6 run under subscription auth.
  `tests/smoke/test_multi_book_smoke.py` seeds a second book
  (`tiny-apothecary`) alongside the fixture's `tiny-inquisitor`, adds
  a legal-earlier sibling chapter (1521-12-01) and an illegal-future
  sibling (1521-12-08) carrying a distinctive "SPOILER_MARKER"
  phrase, then runs `/autonovel:draft 1 --book tiny-inquisitor`
  (story_time 1521-12-04). Assertions: draft is valid, drafted
  chapter does NOT contain the SPOILER_MARKER phrase (exclusion
  honoured), and the chapter never names Tommaso or Lucia as the
  arsonist (E-001 canonical consistency). The sanity layer shells
  out to `python -m autonovel.context_loader` first and fail-fasts
  if the loader itself returns the wrong gating. Runs on subscription
  auth under `@pytest.mark.smoke`. The real drafter did honour the
  exclusion — "Giraldo's burns smelled of saltpeter" did not leak
  from `tiny-apothecary/ch_02` (1521-12-08) into
  `tiny-inquisitor/ch_01` (1521-12-04).
- Tier 3 (PR-8 codex spot-check): 2026-04-24 — **1/1 green (52.11s)**
  on the first clean PR-8 run. `tests/smoke/test_codex_smoke.py` ran
  under subscription auth via Codex CLI 0.125 against the
  `tiny-series-historical` fixture. The test redirects
  `CODEX_HOME=<tmp>/.codex`, copies the user's real
  `~/.codex/auth.json` into the redirected home so subscription auth
  survives, installs the autonovel skills under
  `<tmp>/.codex/skills/autonovel/<stem>/SKILL.md`, then asks
  `codex exec --full-auto -C <fixture>` to invoke the
  `autonovel-gen-canon` skill end-to-end. Codex discovered the
  skill, ran the autonovel preamble (`autonovel _begin`), wrote
  `shared/canon.md` (≥3 bullets, ≥80 words), and ran the postamble
  (`autonovel _end --status ok`). End-to-end on the first attempt;
  no adapter changes required.
- Tier 3 (PR-8 gemini spot-check): not run — `gemini` CLI is not on
  PATH on this box. `tests/smoke/test_gemini_smoke.py` skips
  cleanly. The adapter ships with full Tier-1 coverage including a
  `tomllib.loads` round-trip on every emitted `.toml`; Tier-3
  validation is parked for whenever a Gemini-CLI box is available
  (PR 9 release polish is a natural pairing).
- Tier 3 (PR-7 typeset smoke): 2026-04-24 — **1/1 green (72.65s)**
  on the first clean PR-7 run under subscription auth. `tectonic`
  was not installed on the test box, so the optional PDF assertion
  was skipped per the conditional in
  `tests/smoke/test_typeset_smoke.py`; the
  `chapters_content.tex` build (mechanical.latex inside a real
  Claude Code session) and the `@TITLE@` / `@AUTHOR@` substitution
  in the per-book `novel.tex` were both exercised end-to-end.
  Re-run with `tectonic` on PATH to extend coverage to the
  produced PDF: `pytest tests/smoke -q -m smoke -k typeset`.
- Tier 4 (Bells regression): 2026-04-24 — harness added and passing in
  "skip" mode. Activates once a human populates
  `tests/fixtures/bells-reference/` from the `autonovel/bells` branch.

## Running the smoke test manually

```bash
# One-time: log in once on your subscription (Claude Max / Team / Pro).
claude login

# Run all smoke tests. Uses your subscription auth — "free" against your plan.
pytest tests/smoke -q -m smoke

# Run just one (cheap iteration).
pytest tests/smoke -q -m smoke -k evaluate_chapter

# Run Tier-4 (Bells regression) only — skipped until fixture populated.
pytest tests/smoke -q -m "smoke and regression"

# Optional: exercise the API-key path instead (pay-per-token).
AUTONOVEL_SMOKE_USE_API_KEY=1 ANTHROPIC_API_KEY=sk-ant-... \
  pytest tests/smoke -q -m smoke
```

Each smoke test copies `tests/fixtures/tiny-series-historical/` to a
temp dir, installs the commands into `.claude/commands/` under that
copy, seeds whatever inputs the command needs (a drafted chapter, a
pre-written cuts file, a minimal brief), and invokes
`claude -p "/autonovel:<command> ..."`. Acceptance keys live in the
`<acceptance>` block of each command file.

## Open questions
- Tier-4 harness needs Bells chapters copied from the `autonovel/bells`
  branch before the LLM-judged drift check does useful work. Until
  then the harness passes trivially. Populating it is a standalone
  one-off, scoped to whenever a human next wants to gate the rewrite
  on Bells-parity.

## Resume pointer
**The Fugger rewrite exists as book `kingmaker` (2026-10-13); foundation
order fixed in the pipeline.** In the live series (`~/books/medieval-king-
maker`) the second book is scaffolded `--isolated` with seed.txt (modern
spy-and-money thriller, every chapter a wager), voice.md (close-third past-
tense procedural register, Part 3 rubric that enforces stake / dialogue /
out-of-the-room / no-aphorism, Part 4 fingerprints), a 24-chapter outline
in four acts, book canon, and 10 new cast entries — nothing drafted yet.
The codebase change: `/autonovel:next` now asks for `gen-canon --book` AFTER
the outline (the book half is seeded from it) and only while the book has no
chapters; docs list the six-step foundation. **Next real-world step (needs
the user):** `/autonovel:evaluate --phase foundation --book kingmaker`, then
`/autonovel:title --book kingmaker`, then `/autonovel:draft 1 --book
kingmaker`; compare with `evaluate --compare N,N --book kingmaker --vs-book
medieval-king-maker`. Open: the series' `llm:` pins are still the 4.x family;
`shared/world.md` mentions the "Fugger Zeitungen", which are anachronistic for
Jakob's lifetime (book canon forbids the word in `kingmaker`; a shared-world
correction would need the user's say-so since book 1 was drafted against it).
Prior:
**Book-scoped canon + isolated context (rewrite support) SHIPPED 2026-10-12.**
The live series' canon is partitioned (shared ≈ history only; book-1
inventions in `books/medieval-king-maker/canon.md`). Recipe:
`/autonovel:help rewrite` and docs/multi-book.md "A rewrite". The April
full-book eval was judged at light tier (haiku) and is a soft baseline only.
Prior:
**Phase 13 (the AI-video SHORT) SHIPPED 2026-06-08.** After Phases 11+12 the
teaser was still incoherent because the *shape* was wrong: 180s/30 clips can't
cohere as AI video. Phase 13 makes the default a **45–60s, ≤12-shot,
first-person-voiceover-spine short** (one pipeline + `mode: short|trailer`
knob). Tier 1+2 1842 → 1852. **Next real-world step (needs the user):**
re-run `/autonovel:teaser --book medieval-king-maker --fresh` (now defaults to
short mode, 60s) — free, stops before render — and read the new `teaser.json`:
≤12 shots, a `spine.narrator`, a `voiceover` line on most shots that reads as
ONE story. **Open follow-ups (FUTURE-TODOS near-term, all still pending):**
(1) **VO-audio synthesis** — actually lay the narration track over the cut
(TTS), like the music bed; today the VO lines + cohesion judgement land but
the audio isn't generated. (2) **judge the rendered cut, not the script** — a
vision pass over the assembled animatic + make the assembly cut-critique
adversarial (it rubber-stamped the bad cut "KEEP"). (3) identity-lock /
reference-chaining (render quality, user-deprioritized). Also: the doubled
series path `books/medieval-king-maker/books/medieval-king-maker` (Phase-10
nesting) is still unfixed in that series. Prior:
**Phase 12 (teaser LEGIBILITY + honest grading) shipped 2026-06-08.** The
Phase-11 quality gate was self-certifying — it graded the *script* (which the
model could see) not a stranger's *experience*, so a full Fugger run shipped
a teaser that self-scored 7–9 and was still terrible (9/23 object shots, no
figure IDs, 12 cards). Phase 12 adds the **viewer-blind legibility gate**
(`quality.json` /2: per-shot who/what/why judged from on-screen info only;
blocks illegible "tours of objects"), `Shot.identify` lower-thirds, drama-over-
mechanism + genre-care authoring, and drops the text-card crutch. Tier 1+2
1831 → 1841. **Next real-world step (needs the user):** the planning pipeline
is FREE — regenerate the Fugger teaser SCRIPT (`/autonovel:teaser --book
medieval-king-maker --fresh`) and read `teaser/quality.json`'s legibility
read + `teaser.json` to confirm it now centers identified people, not objects,
BEFORE any paid re-render. **Deeper open work** (FUTURE-TODOS near-term): make
the gate judge the *rendered clips* (vision), not just the script, and make
the assembly cut-critique adversarial (it also marked the bad cut "KEEP"). Also
note the doubled series path `books/medieval-king-maker/books/medieval-king-maker`
(the Phase-10 nesting issue, still unfixed in that series). Prior:
**Phase 11 (teaser storytelling QUALITY) shipped 2026-06-08** — all 8 items
of the "it's boring" plan landed: the interestingness rubric + HARD quality
gate (`teaser/quality.py` + `quality.json` + second render gate), spine
`turn`, per-shot `character_beat`, length-aware pacing (movements +
dialogue_target), `/autonovel:teaser-brief` distillation, the de-boring
revise pass, and few-shot exemplars in teaser-craft §11. Tier 1+2 1805 →
1831. **Next real-world step (needs the user):** run the full pipeline on
the Fugger book against the now-current install (`/autonovel:teaser --book
medieval-king-maker --fresh --length 180`) and judge whether the output is
actually *interesting* — the quality gate should now block a flat teaser and
the de-boring revise should lift it. **Do NOT run a non-dry render on a keyed
provider during dev** (`.env` resolves real keys; use `--provider stub` /
`--dry-run`). Then: the longer-term TODO to bring the same research→encode→
ENFORCE rigor to the novel *prose* pipeline (FUTURE-TODOS near-term).

See `ROADMAP.md` at project root — forward-looking todos and the PR-7
resume pointer live there. STATE.md keeps the append-only decisions
log and the "Tests last known green" line. Keeping them separate means
a `/clear` leaves the roadmap intact without the decisions-log
noise.
