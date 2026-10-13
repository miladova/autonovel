# Series conventions

You (the AI) are running inside an **autonovel series**. This file is
auto-loaded by Claude Code (and read on demand by Codex / Gemini) so
you have shared context regardless of which command the user invokes.

A "series" here is the unit of co-evolving lore. A standalone novel
is a series with one book — same layout, same rules.

> **Layout note:** a series *contains* its books under `books/<book>/`. So
> a standalone novel's files live at `<series>/books/<book>/…` — and when
> the book shares the series name, that path reads as
> `my-novel/books/my-novel/…`. The repeated name is **correct, not a
> doubled-path bug** (`autonovel doctor` confirms it; use a distinct book
> short-name in `new-book` if you'd rather avoid the repetition). A literal
> `books/books/` level *would* be a bug — doctor flags that as a PROBLEM.

## Layout

```
project.yaml             # series config: genre, period, llm tier mapping
shared/
  world.md               # universe-level rules
  characters.md          # cast registry (every named character)
  canon.md               # series-wide hard facts (history, world rules) — append-only via /autonovel:promote-canon
  events.md              # inter-book event ledger (story_time + rendered_in)
  timeline.md
  period_bans.txt        # forbidden vocabulary (period fiction)
  sources.bib            # research bibliography
  research/
    sources.yaml         # forced URLs that /autonovel:research must consult
    notes/               # per-topic research notes (one .md per topic)
    seed/                # source PDFs / images the user dropped in
books/<book>/
  seed.txt               # the user's pitch — authoritative input
  voice.md               # Part 1: generic guardrails. Part 2: book-specific fingerprint
  outline.md             # generated; structure across chapters
  canon.md               # book-scoped canon — facts THIS book's chapters fixed; binds this book only
  pending_canon.md       # candidate canon — promote-canon routes into canon.md (or shared/ if research-cited)
  chapters/ch_NN.md      # the prose
  briefs/                # generated revision briefs
  edit_logs/             # adversarial-edit + check-anachronism reports
  eval_logs/             # /autonovel:evaluate scoreboards
  audiobook/             # voices.yaml + voices.yaml.example + scripts + audio
  typeset/               # PDF/ePub build artefacts
.autonovel/
  state.json             # series-wide phase + scores
  in-progress.lock       # PID lock; do not edit
  checkpoints/           # rollback targets, written by every command's preamble
  command-log.jsonl      # one line per command run
```

## Operating rules

1. **Use the `/autonovel:*` commands.** Do not edit chapter prose,
   outlines, voice files, or canon directly except when explicitly
   acting *as* one of those commands. Each command owns a lock,
   checkpoint, and log entry; freelance edits skip all three.

2. **Canon files are append-only via `/autonovel:promote-canon`.**
   Drafting and revision append observations to
   `books/<book>/pending_canon.md`. Promotion routes chapter-derived
   facts into the book's own `books/<book>/canon.md` and research-cited
   facts into `shared/canon.md`; it is single-threaded across the
   series and parks contradictions under a `# Conflicts` header for
   human resolution. Never optimistically merge. A book's canon binds
   that book only — a sibling book or a rewrite (`context: isolated`
   in `project.yaml`) is never checked against it.

3. **Chapter renumbering** after `/autonovel:merge-chapters`,
   `/autonovel:remove-chapter`, or `/autonovel:reorder` runs by
   shell script (collision-safe `mv` / `git mv`). Never rename
   chapters in an LLM rename loop. Same discipline applies to
   `/autonovel:rename-character`.

4. **Story-time gating** is a spoiler control. When drafting a
   chapter, only sibling chapters with `story_time` upper-bound ≤
   the target chapter's `story_time` lower-bound are legal context.
   The context loader at `python -m autonovel.context_loader`
   enforces this; trust it over your own reasoning.

5. **The Stability Trap.** AI defaults to safe, round-edged endings.
   Push toward irreversible change, real cost, and one mystery the
   next chapter can pull on.

## Where per-book guidance lives

If the user wants you to behave differently for one book in the
series (e.g. "Book Two is first-person; never head-hop"), that
guidance belongs in `books/<book>/voice.md` Part 1 — every drafting
and revision command reads it automatically. Don't add a per-book
`CLAUDE.md`; it would not auto-load.

## Production gotchas (learned in the Bells production)

These are real — they're not style preferences. The Bells team hit
each of these and the workaround is in the codebase:

- **Don't compress chapters below ~1800 words.** They become the
  new weakest. Sweet spot for compressed chapters is 2200–3000w.
- **`/autonovel:revise` overshoots target word count by ~30%.**
  Brief 3200w, expect 3800–4200w.
- **Pacing ≈ 7 is a likely ceiling** for investigation-heavy plots.
  Stop after two rotations of "weakest chapter".
- **OVER-EXPLAIN (~32%) and REDUNDANT (~26%)** dominate adversarial
  cuts. Prioritise these in `/autonovel:apply-cuts`.

## When in doubt

- Run `/autonovel:help` for the discoverability overview.
  `/autonovel:help <topic>` walks one workflow with the exact
  command sequence — `/autonovel:help art`, `/autonovel:help
  typeset`, `/autonovel:help foundation`, `/autonovel:help
  drafting`, `/autonovel:help revising`, `/autonovel:help
  research`, `/autonovel:help front-matter`, `/autonovel:help
  sweeps`, `/autonovel:help tui`, `/autonovel:help cli`,
  `/autonovel:help next-steps`. The right place to start when a
  set of commands feels opaque (the 10 art-* / cover-* commands
  in particular).
- Run `/autonovel:next` to see the prioritised state-aware action
  list (pending conflicts, regressions, briefs newer than their
  chapters — the brief→revise pair, stale review reports, backup
  status, plus the canonical pipeline next step). Past-end-of-book
  guard: when the canonical line points to a draft chapter beyond
  what exists by more than 1, it gets demoted to "book appears
  complete — try evaluate --full / typeset". You'll also see a
  one-line "💡 Maybe try:" hint in every command's postamble
  drawn from the same enumerator, so most of the time you don't
  need to call `/autonovel:next` separately.
- Run `/autonovel:resume` if a previous command left an
  `.autonovel/in-progress.lock` behind. Also detects an
  interrupted sweep (`draft-pass` or `revision-pass`) via
  `.autonovel/sweep-progress.json` and prints a precise "continue
  from chapter N" with the remaining chapter list.
- Run `/autonovel:impact-of --book <name>` after any foundation
  mutation to get a per-chapter action checklist of revises.
  `--source promote-canon` (default) parses `## Superseded`
  blocks; `--source rename-character` greps stragglers of the
  OLD name from the most recent rename in `command-log.jsonl`;
  `--source merge-chapters|reorder|remove-chapter` greps prose
  for now-stale chapter-number cross-references; mtime sources
  (`voice-discovery / add-character / gen-characters / gen-world
  / add-source`) flag chapters older than the foundation file.
  No more `ls` + `grep` to figure out what to revise next.
- Run `/autonovel:sidequest` for the menu of non-standard operations
  (rename character, split chapter, deepen character, etc.).
- Run `/autonovel:talk --book <name> "<question>"` to ask the book
  questions or queue edits. Three modes (Q+A / Suggest-and-stage
  / Mechanical+suggest); queued edits get folded into the brief
  by the next `/autonovel:revise <chapter>` automatically.
- Run `/autonovel:motifs --book <name>` for a per-chapter motif
  density table (configure `books/<name>/motifs.md` first).
- Run `/autonovel:chapter-summary --book <name>` for the
  one-line-per-chapter overview.
- Run `/autonovel:dashboard --book <name>` for the at-a-glance
  shape — score / tension sparklines, aggregates, and tension-
  drop alarms re-rendered from the latest eval log without
  firing another evaluate.
- Run `/autonovel:summaries --book <name> --where '<expr>'` to
  filter the chapter-summary index. Pure mechanical query DSL
  (no LLM): `pov == "Lucia"`, `cast contains Niccolò`,
  `story_time >= "1521-11"`, `chapter in 5..12`,
  `score < 7.0 and word_count > 3000`. Distinct from
  `/autonovel:talk` (LLM Q+A) by being free + scriptable.
- Run `/autonovel:dialogue --book <name>` for the dialogue-
  mechanics linter (adverb tags, said-bookisms, stutters).
- Run `/autonovel:period-register --book <name>` for a roll-up
  of period-bans hits across every chapter — useful before
  typeset.
- Run `/autonovel:pov-bleed --book <name>` for a heuristic POV-
  bleed scan. Suggestion list, not a gate — false positives are
  common.
- Run `/autonovel:extract-chapter-titles --book <name>` to backfill
  evocative chapter titles into frontmatter for chapters drafted
  before titles became standard. typeset's TOC reads the
  frontmatter `title:` field; without backfill the TOC reads
  `Chapter I, II, …` instead of `Chapter VII — The Apothecary's
  Mortar`. `/autonovel:next` surfaces missing titles as a LOW
  polish signal; light-tier (~$0.001/chapter).
- Run `/autonovel:glossary --book <name> --from auto` for a
  period-vocabulary reference in the front matter (right before
  chapter 1). Critical for historical fiction. Run
  `/autonovel:appendix --book <name> --sections timeline,bios
  --from auto` for the back-matter timeline + real-character
  bios; the timeline merges in-narrative dates (📖) with real
  events the prose mentions (🏛️ referenced) and optionally
  context-setting events (🏛️ context, opt-in via
  `--include-context`).
- Run `/autonovel:import-book --book <name> --from <path>
  [--reverse-engineer]` to import an externally-written manuscript.
  Flips the book to `mode: edit-imported`; the rest of the pipeline
  (evaluate / revise / panel / review / typeset) is unchanged. With
  `--reverse-engineer`, the import scans the imported prose for
  candidate character names and seeds (or appends to)
  `shared/characters.md` with an auto-detected block. After
  importing, run `/autonovel:summarize-chapter --all --book <name>`
  so revise/brief have continuity summaries to read; then
  `/autonovel:voice-discovery --book <name>` and
  `/autonovel:gen-outline --book <name>` to fill in the rest of
  the foundation against the imported prose.
- Run `/autonovel:research --query "<question>"` to ask
  cross-source synthesis questions over your existing
  `shared/research/notes/` — no web search, just LLM synthesis with
  inline `[shortname]` citations. Distinct from `/autonovel:talk`
  (queries prose) and `/autonovel:research "<topic>"` (live web
  research that writes new notes).
- Run `/autonovel:series-arc` (no `--book`) when the series
  has ≥2 books for the cross-book scoreboard — completion,
  cross-book cast, story-time discipline, unresolved threads,
  composite arc score 0-10.
- Run `/autonovel:show-dont-tell --book <name>` for the wider-
  net tell-candidate scanner (emotion-state, interiority verbs,
  perception filters, narrator labels). Suggestion list — the
  LLM judge in `/autonovel:evaluate` produces the actual show-
  vs-tell ratio.
- Run `autonovel cost` (CLI, not slash-command) for the token
  + cost rollup across the whole series. Estimates only — the
  runtime's session-usage report is the source. Mechanical-only
  commands count as $0 runs.
- Run `/autonovel:syntax-drift --book <name>` for per-chapter
  Flesch-Kincaid grade against the book's voice/seed
  baseline. Pure math, catches modern syntax in period-
  correct vocabulary. Review list, not a gate.

## If you (the agent) hit `API Error: Extra usage is required for 1M context`

This is a Claude Code billing-gate, not an autonovel bug. Surface
this to the user verbatim and stop, do not retry:

> Your Claude Code session model is a 1M-context variant (e.g.
> `claude-opus-4-7[1m]`) and 1M billing is not yet enabled on your
> account. autonovel benefits from 1M context, especially in
> reader-panel and review. Two paths:
>
> 1. **Recommended:** run `/extra-usage` to enable 1M billing —
>    this is the path the error message itself suggests.
> 2. **Mechanical workaround:** run `/model` and pick a non-`[1m]`
>    variant (Sonnet 4.6 is the default tier for standard-tier
>    autonovel commands).
>
> Then re-run the command that just failed.

## Movie / teaser mode

Adapting a book to the screen, in order. **The pipeline defaults to
`--mode short` (Phase 13):** a 45–60s, ≤12-shot self-contained micro-story
carried by a single first-person **voiceover spine** — the shape that
actually coheres as AI video (independently-generated clips don't stitch into
a 30-shot montage; one narrator's voice does). `--mode trailer` keeps the
older longer montage shape for live/stock footage or an X-Prize-length cut.

1. `/autonovel:treatment --book <name>` — film treatment + 2-page brief
   (reveals the ending; `--audience xprize` default frames it for the
   Future Vision X-Prize: optimistic future, real problem solved, stakes
   + arc, visual ambition).
1b. `/autonovel:teaser-brief --book <name>` — **distil** the treatment into
   a one-page teaser brief: the single filmable through-line, the midpoint
   **turn/reversal**, the 3 must-have dramatic moments, and the killer
   lines — so the beats are chosen from a sharp brief, not the sprawling
   story. Writes `teaser/brief.md` (the `/autonovel:teaser` orchestrator
   runs this for you when a treatment exists).
2. `/autonovel:teaser --book <name> [--length 180] [--provider <p>]` —
   the one-command trailer pipeline: it runs `teaser-brief` (distil), then
   `teaser-beats` (fix the **story spine** — the dramatic question, logline,
   want vs. opposing force, **the turn**, emotional arc — then pick the hook
   → escalation → title → button beats that serve it and escalate) then
   `shot-prompts` (turn them into provider-ready shot prompts, **mine the
   length-scaled loaded dialogue lines** from the manuscript + author premise
   **text cards** + tag want/cost character beats), then the **critique →
   revise loop** (`teaser-critique` scores the **interestingness rubric** →
   `teaser-revise` lifts the weak dimensions + de-borings the flattest beats),
   each in a fresh subagent, looping until **both render gates are READY**
   (story complete AND quality ≥ 7). Writes `teaser/brief.md` +
   `teaser/beats.md` + `teaser/teaser.json` + `teaser/shots/shot_*.md` +
   `teaser/critique.md` + `teaser/quality.json` (all free). Run the
   sub-commands individually if you want to hand-edit between them.
   Re-running with `--force` archives the prior scripts to
   `teaser/script-takes/` and reuses the approved `teaser/refs/` originals,
   so a full re-run changes the scripts without losing them or the
   portraits/location plates.
3. `/autonovel:teaser-critique --book <name>` — re-check a hand-edited
   `teaser.json` (mechanical linter + LLM critic) AND score the
   interestingness rubric **plus a viewer-blind legibility read** (each shot
   judged as a first-time viewer from on-screen action + spoken line only —
   so an illegible "tour of objects" can't self-pass) to `teaser/quality.json`;
   writes an advisory `teaser/critique.md` and the render-gate verdict (story
   + quality + legibility). Read-only on the teaser; free.
   `/autonovel:teaser-revise` then APPLIES the findings in place (fills the
   spine, lifts weak quality dimensions, centers **people not objects**, adds
   **identify** lower-thirds, de-borings the flattest beats) — no hand edits.
3b. `/autonovel:teaser-refs --book <name> [--init]` — develop + **approve**
   a reference image per recurring character before spending a real
   render (public-domain art via wikimedia, a local image, or generate;
   locks appearance/period/likeness in `teaser/refs.yaml`). Keeps identity
   from drifting across clips; the offline `stub` backend is exempt.
4. `/autonovel:teaser-render --book <name> [--provider <p>] [--kind auto|image|video] [--dry-run]`
   — render the shot prompts into actual clips. On a fresh teaser it first
   does a **free, offline `stub` render** (local placeholder keyframes —
   no network/key/quota) so you can validate the whole render→assemble
   chain for $0 before spending. The default real backend is **`grok`**
   (free dialogue+music, no credit card — needs a free `XAI_API_KEY`);
   `kie` / `veo` / `magichour` / `fal` / manual `flow` are alternatives.
   A vision critique marks each clip KEEP / REGENERATE / UPGRADE-TO-PAID.
   Clips land in `teaser/clips/`; stateless, nothing assembled.
   `--dry-run` prints the plan + key status for $0. **Two render gates** must
   be green first (real backends only; `stub` is exempt): the story gate (a
   complete spine + dialogue/cards) AND the **quality gate** (the
   `teaser/quality.json` rubric clears overall ≥ 7, no dimension < 5) — a
   structurally-complete-but-boring teaser is refused until you revise it.
5. `/autonovel:teaser-assemble --book <name> [--audio <path>]` — stitch
   the clips into one teaser video with ffmpeg (builds an editable
   `teaser/cut_list.json`), then a viewer-panel cut critique (hook lands?
   accelerates? button withholds?) → `teaser/assembly-report.md`. Add the
   title/subtitle cards in an editor (the report lists them). ffmpeg
   required.

Validate the pipeline free with `stub`, then render real video with
`grok` (or another backend). Put provider keys in a gitignored `.env` at
the series root. Backend/key map: `docs/teaser-render-providers.md`; the
creative how-to lives in `docs/teaser-craft.md`.

## Where to find more

- README at the series-template repo (autonovel project) — install
  + per-OS guidance + the seed-writing template.
- `docs/commands.md` — every `/autonovel:*` command reference.
- `docs/multi-book.md` — story-time gating and event ledger details.
- `docs/writing-a-historical-series.md` — end-to-end walkthrough.
- `docs/teaser-craft.md` — making a 1–3 min AI-video teaser;
  `docs/prd-movie-teaser-mode.md` — the movie-mode build spec.
