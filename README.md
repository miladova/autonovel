# autonovel

An autonomous novel-writing pipeline that drops a `/autonovel:*` command
suite into your AI CLI runtime — Claude Code, OpenAI Codex, or Gemini
CLI — and turns a seed concept into a finished novel: manuscript,
typeset PDF, ePub, cover art, audiobook, landing page.

The runtime owns the model, the auth, and the file I/O. autonovel just
ships markdown commands and a small Python housekeeping CLI.

## Acknowledgements

This repository is a **fork and complete re-architecting** of two
upstream projects:

- **[NousResearch/autonovel](https://github.com/NousResearch/autonovel)** — the original autonomous-fiction
  pipeline, including the production framework that wrote the novel
  *The Second Son of the House of Bells* (see the [Bells production](#the-bells-production)
  section below). Every craft principle, every prompt heuristic,
  every gotcha learned from a real production run came from there.
- **[karpathy/autoresearch](https://github.com/karpathy/autoresearch)** — the modify → evaluate →
  keep/discard loop applied to research, which we apply here to
  fiction.

What changed in this re-architecture: the original was a set of
~27 Python scripts that called the Anthropic API directly. This
version replaces them with markdown commands installed into your
existing AI CLI runtime, so the runtime owns the model and auth, and
the same pipeline runs on Claude Code, Codex CLI, or Gemini CLI
without changes to the prompts. See [`REWRITE-PLAN.md`](REWRITE-PLAN.md)
for the full architecture write-up.

---

## Install

> Pick the section for your machine. Each one assumes you have
> **never set up programming tools on this machine before**. If you
> already have `git` and `pipx`, jump to "Get the source".

### Chromebook (ChromeOS Linux)

1. **Enable the Linux development environment.** This is a one-time
   ChromeOS setting. Open *Settings → Advanced → Developers → Linux
   development environment* and click *Turn on*. ChromeOS will
   download a small Linux container; this takes a few minutes.

2. **Open the Terminal app.** It appears in your launcher after
   step 1. When it opens you'll see a prompt like:

   ```
   yourname@penguin:~$
   ```

   The `~` means you're sitting in your Linux home folder. That
   folder lives at `/home/yourname/` and starts empty.

3. **Install `git` and `pipx`.** Copy and paste these two lines, one
   at a time, pressing Enter after each:

   ```bash
   sudo apt update
   sudo apt install -y git pipx
   ```

   The first time you use `sudo` it will ask for your password.

4. **Tell pipx to put installed tools on your PATH:**

   ```bash
   pipx ensurepath
   ```

   Then **close the Terminal window and open a fresh one** so the
   PATH change takes effect. (This is annoying but unavoidable —
   pipx is updating a shell configuration file that only fresh
   terminals re-read.)

5. **Get the source.** Continue at "Get the source" below.

### Windows (WSL)

1. **Enable Windows Subsystem for Linux** if you haven't. In a
   PowerShell window run `wsl --install` and follow the prompts;
   reboot when asked. Microsoft's full guide:
   <https://learn.microsoft.com/en-us/windows/wsl/install>.

2. **Open your WSL distribution** (it shows up as "Ubuntu" or
   similar in the Start menu). You'll see a prompt like:

   ```
   yourname@machine:~$
   ```

   Same as the Chromebook — `~` is your Linux home folder.

3. **Install `git` and `pipx`** with the same two `apt` commands as
   the Chromebook step 3 above, followed by `pipx ensurepath` and
   a fresh terminal window (Chromebook step 4).

4. **Get the source.** Continue below.

### macOS

1. Open the **Terminal** app (Applications → Utilities → Terminal).

2. Install [Homebrew](https://brew.sh/) if you don't have it.

3. Install `git` and `pipx`:

   ```bash
   brew install git pipx
   pipx ensurepath
   ```

   Open a fresh Terminal window after `pipx ensurepath`.

4. **Get the source.** Continue below.

### Linux desktop

You almost certainly know what to do. `apt`/`dnf`/`pacman` install
`git` and `pipx`, run `pipx ensurepath`, open a fresh terminal,
continue.

---

### Get the source

These steps are the same on every operating system once a fresh
terminal is open with `git` and `pipx` available.

1. **Clone the repository.** This downloads the autonovel source
   into a new folder named `autonovel` next to whatever folder you
   were already in:

   ```bash
   git clone https://github.com/pmilford/autonovel.git
   ```

   Before this command: your terminal sits in `/home/yourname/`
   (an empty folder).
   After this command: there's a new folder at
   `/home/yourname/autonovel/` holding the source. Your terminal
   is **still** sitting in `/home/yourname/` — cloning a repo does
   not move you into it.

2. **Step into the folder and install:**

   ```bash
   cd autonovel
   pipx install '.[export]'
   # or, to also pull in the read-only TUI dep up front:
   pipx install '.[export,tui]'
   ```

   `cd` ("change directory") moves you into the cloned folder.
   `pipx install '.[export]'` reads the `pyproject.toml` here,
   installs autonovel as a tool you can run from anywhere, and
   pulls in the Python image + audio libraries (`Pillow`, `pydub`)
   that the export commands (cover art, audiobook) need. Quotes
   around `'.[export]'` matter — your shell will otherwise try to
   glob the brackets. The optional `tui` extra pulls in `textual`
   for `autonovel tui` (long-running terminal browser); skip it if
   you'll only use the slash-commands and the `autonovel status` /
   `autonovel cost` one-shots.

   If you only ever plan to draft and revise (no PDF / cover /
   audiobook export), `pipx install .` without the extras works
   too and is faster. You can add the extras later with
   `pipx inject autonovel Pillow pydub`.

   **If pipx complains about Python version** ("requires Python
   3.11 or newer; default python3 is 3.10.X"): your default
   `python3` is older than autonovel needs. The fix is to point
   pipx at a newer Python you already have installed (most
   Chromebook / WSL setups have 3.11 or 3.13 available even when
   `python3` defaults to something older):

   ```bash
   # Find a newer Python you have:
   ls /usr/bin/python3.* 2>/dev/null
   # → e.g. /usr/bin/python3.11  /usr/bin/python3.13

   # Point pipx at it:
   pipx install '.[export]' --python python3.13
   ```

   No need to change your system default — this only tells pipx
   which Python to put autonovel on. Other tools you've installed
   via pipx are unaffected.

3. **Confirm it worked:**

   ```bash
   autonovel --version
   ```

   You should see `autonovel 0.2.0`. If you see "command not found",
   the most common cause is that you didn't open a fresh terminal
   after `pipx ensurepath` — close this terminal, open a new one,
   try again.

4. **Install your AI CLI runtime.** Pick at least one:

   - [Claude Code](https://docs.claude.com/en/docs/claude-code) — the original target. After install, run `claude login`
     once. Most users want this one.
   - [OpenAI Codex CLI](https://github.com/openai/codex)
   - [Google Gemini CLI](https://github.com/google-gemini/gemini-cli)

5. **Install the autonovel commands into your runtime:**

   ```bash
   autonovel install
   # Want to see what would land first?
   autonovel install --dry-run
   ```

   This auto-detects which runtimes you installed in step 4 and
   drops the `/autonovel:*` command files into each one. You can pin
   a single runtime with `--only claude` (or `codex` / `gemini`).
   `--dry-run` prints the would-be paths without touching disk —
   useful before letting `npx autonovel install` mutate
   `~/.claude/commands/`.

6. **(Claude Code only — heads up) The 1M-context billing gate.**
   autonovel benefits from 1M context — `/autonovel:reader-panel` and
   `/autonovel:review` read whole manuscripts, and a 1M-capable
   model lets cross-book review work without context-budget
   trickery. If your default Claude Code model is a `[1m]`-suffixed
   variant (e.g. `claude-opus-4-7[1m]`), you may hit this error
   mid-pipeline:

   ```
   API Error: Extra usage is required for 1M context - run
   /extra-usage to enable or /model to switch to standard context
   ```

   Two paths:

   - **Recommended — enable 1M.** Inside Claude Code run
     `/extra-usage` to opt into the 1M billing surface. On a Max
     $200/month plan this is the right default: 1M context is
     genuinely useful in autonovel's review and multi-book phases.
   - **Workaround — drop `[1m]`.** If `/extra-usage` doesn't unlock
     1M for you, run `/model` and pick a non-`[1m]` variant
     (Sonnet 4.6 is the default tier autonovel's standard commands
     target). Foundation, drafting, and per-chapter eval all fit in
     200k; you only feel the loss in whole-book review.

   See [`docs/troubleshooting.md`](docs/troubleshooting.md) for the
   full diagnosis and the open question this raises about
   per-command model overrides on Claude Max plans.

You're done with installation. The next section is for using it.

---

## For users — writing a novel

You don't open the autonovel folder when you write. autonovel is a
**tool you installed**; your novel lives in its own folder somewhere
else. (Same way you don't write a book inside your word processor's
install folder.)

### 1. Make a folder for your novel

Pick somewhere convenient:

```bash
mkdir -p ~/novels
cd ~/novels
```

### 2. Scaffold a series

A "series" in autonovel is the unit of co-evolving lore. A standalone
novel is a series with one book.

```bash
autonovel new-series renaissance-europe --genre historical-fiction
cd renaissance-europe
autonovel new-book the-inquisitor --pov Tommaso --story-time-range 1519-1523
```

This creates:

```
renaissance-europe/
  project.yaml             # series config
  shared/
    world.md               # filled in later by /autonovel:gen-world
    characters.md
    canon.md               # series-wide hard facts (each book also gets its own books/<name>/canon.md)
    events.md              # inter-book event ledger
    period_bans.txt        # period-anachronism word list (pre-seeded for 1400-1600)
    research/              # forced URLs and notes
  books/
    the-inquisitor/
      seed.txt             # ← you edit this first
      voice.md
      outline.md
      chapters/            # generated by /autonovel:draft
      …
```

### 3. Write the seed

The seed file is the **one piece of writing autonovel needs from
you**. Everything else (world, characters, outline, prose) is built
from it. The new book template ships a guided template with six
prompts — the pitch, your POV character, the obstacles, what
changes by the end, period and place, and anything else you want
the AI to know. There's an example answer under each prompt so you
can see the depth expected.

You're currently in `~/novels/renaissance-europe/`. The seed lives
one folder down at `books/the-inquisitor/seed.txt`. Open it in any
text editor — pick whichever you have:

- **Chromebook:** the *Text* app from your launcher works. Or, in
  the terminal: `nano books/the-inquisitor/seed.txt`.
- **Windows / WSL:** type `notepad.exe books/the-inquisitor/seed.txt`
  (Notepad opens on the Windows side, editing the WSL file). Or in
  the terminal: `nano books/the-inquisitor/seed.txt`.
- **macOS:** `open -e books/the-inquisitor/seed.txt` opens it in
  TextEdit. Or in the terminal: `nano books/the-inquisitor/seed.txt`.
- **VS Code on any OS** (if installed): `code books/the-inquisitor/seed.txt`.

If you've never used `nano` before, it shows the keyboard shortcuts
along the bottom of the window: `Ctrl-O` saves, `Ctrl-X` quits.

Plan to spend **20–30 minutes** on the seed. You don't need to
write elegantly — bullet points are fine; the AI will turn them
into prose.

### 4. Open the series in your runtime and run commands

**Be in the series root** — the folder that contains `project.yaml`.
For our example that's `~/novels/renaissance-europe/`. The
`/autonovel:*` commands resolve paths like `shared/world.md` and
`books/the-inquisitor/seed.txt` relative to wherever you launch the
runtime, so being one folder too deep produces "file not found"
errors that look mysterious.

Sanity-check your location first:

```bash
pwd                       # should end in /renaissance-europe
ls project.yaml           # should print "project.yaml" with no error
```

If `ls project.yaml` errors, you're in the wrong place. The fastest
fix is `cd ~/novels/renaissance-europe`. (If you `cd`-ed into the
book directory to edit the seed, `cd ..` once is enough.)

Then launch your runtime:

```bash
claude            # or `codex`, or `gemini`
```

#### How to drive the pipeline

The simplest pattern: **run one command, then read the postamble's
"💡 Maybe try:" hint** — every successful command now ends with a
one-line situational suggestion drawn from the same enumerator
that powers `/autonovel:next`. So most of the time you don't have
to ask anything; the next step is right there in the response.
When you want the full picture, `/autonovel:next` inspects what's
on disk — pending canon conflicts, chapter regressions, briefs
newer than their chapters (the brief→revise pair is the most
common signal), stale reader-panel/Opus review reports, git
backup state, missing title or author, missing front matter — and
emits a prioritised action list. The canonical pipeline next step
appears at the bottom; situational actions take precedence. You do
not have to memorise the order.

After `/autonovel:promote-canon` flips facts, run
`/autonovel:impact-of --book <name>` to get a per-chapter
checklist of `/autonovel:revise --chapter N` calls with
line-snippet evidence — no `ls` + `grep` required to find which
chapters now disagree with canon.

Want a long-running window on the series state instead of one-shot
commands? `autonovel tui` (in a separate terminal from the series
root, with `pip install 'autonovel[tui]'` or `pipx inject autonovel
textual`) is a read-only browser for chapters / scores / research /
front matter / reviews / next actions. The Help tab shows, for each
suggested next command, *why* it's suggested, *what it reads*, and
*what it writes* — so you can decide before invoking it in your
runtime. Read-only by contract; never acquires the lock.

**Lost? Run `/autonovel:help`.** Zero-arg gives a category-grouped
overview of every command. `/autonovel:help <topic>` walks one
workflow with the exact command sequence — useful topics include
`art` (the 10 art-* / cover-* commands; four cover paths from
free-typographic to paid AI), `foundation`, `drafting`,
`revising`, `typeset`, `research`, `front-matter`, `sweeps`,
`tui`, `cli`, `next-steps`.

**Quickest start:** run the onboarding wizard from the shell:

```bash
autonovel new-series my-novel && cd my-novel
autonovel new-book book-one
autonovel onboard book-one          # interactive prompts
```

`autonovel onboard` captures pitch / period / genre / working
title / human author / attribution style into a structured
`seed.txt` + `project.yaml`. Every prompt has a `(skip)` option;
skipped items land in an `## Onboarding TODO` block that
`/autonovel:next` surfaces later. After the wizard finishes, open
Claude Code in the series root and `/autonovel:next` walks you
through gen-world / gen-characters / voice-discovery / gen-canon
/ gen-outline / draft 1 in order.

For a fresh series, `/autonovel:next` will walk you through the
foundation in this order:

1. `/autonovel:gen-world` — series-level world bible.
2. `/autonovel:gen-characters` — cast registry.
3. `/autonovel:voice-discovery --book <book>` — voice fingerprint.
4. `/autonovel:gen-canon` — hard-fact database.
5. `/autonovel:gen-outline --book <book>` — chapter plan.
6. `/autonovel:evaluate --phase foundation --book <book>` — score the foundation.
7. `/autonovel:draft 1 --book <book>` — first chapter when foundation is solid.

Each command's footer prints the next step automatically. **All five
foundation commands are required before drafting** — `gen-canon`
needs voice and characters; the chapter draft needs all of them. Skip
one and the eval score will surface the gap, but it's faster to just
run them in order.

If you'd rather drive the whole thing end-to-end without typing
commands one at a time:

```text
/autonovel:run-pipeline --books the-inquisitor
```

This is the orchestrator. It walks foundation → drafting → revision
→ export and stops only when you need to make a real decision (e.g.
which voice trial to keep, whether to merge two chapters).

#### Automation patterns for power users

Three commands that batch the per-chapter loop so you don't type the
same command N times:

| Command | What it batches |
|---|---|
| `/autonovel:draft-pass --chapters 1-10` | "Write the rest of the book." Per chapter: draft → anachronism check → evaluate → if score < threshold (default 7.0; tunable via `project.yaml::defaults.chapter_threshold` or per-call `--retry-below`), brief + revise + re-eval (keep best). At sweep end: promote pending canon (chapter-derived facts → the book's own `canon.md`; research-cited → `shared/canon.md`). Add `--deep` to also run reader-panel + Opus review at the end and surface the resulting flagged-chapter list. Sequential. |
| `/autonovel:revision-pass --chapters 1-10` | The deeper revision pass. Sweeps `check-anachronism → brief → revise → evaluate` across the range; add `--parallel [N]` (default 3) for speed. Use after `draft-pass` (or after any change that needs deepening). |
| `/autonovel:compare-models --chapter 5 --models claude-opus-4-7,claude-sonnet-4-6` | A/B-draft the same chapter with two models in parallel, judge head-to-head, write verdict to `eval_logs/`. |

When to use the sweeps vs per-chapter typing:

- **Per-chapter** when you're calibrating (early chapters, voice
  shake-out). Lets you stop and fix before drift compounds.
- **Sweep** when the foundation is solid and you want forward
  progress. Quality of each chapter is identical; the only thing
  you give up is the human inspection point between chapters.

You can also chain commands by **asking the agent in plain English**.
*"Run check-anachronism, brief --from auto, then revise on chapters
1, 2, and 3"* will invoke each command in sequence — no chained
`/`-syntax needed.

### 5. Read the worked example

For a 12-step end-to-end walkthrough on a 3-book historical series
— including research, period guardrails, cross-book events, and
publishing to PDF/ePub/audiobook — see
[`docs/writing-a-historical-series.md`](docs/writing-a-historical-series.md).

### How much do you write, and when?

You write the seed (~20–30 minutes). After that, your job is to
**read what the AI produces and steer**, not to write prose. Rough
expectations for a single ~70,000-word novel:

| Phase | What you do | Realistic time |
|---|---|---|
| Seed | Answer the six prompts in `seed.txt`. | 20–30 min |
| Foundation review | Read `shared/world.md`, `shared/characters.md`, the outline. Re-run any of `/autonovel:gen-world`, `/autonovel:gen-characters`, `/autonovel:gen-outline` if something is off — they reference your seed each time. | 30–90 min total, spread across 1–3 cycles |
| Voice discovery | `/autonovel:voice-discovery` produces five trial passages; you pick one (or rerun for new trials). | 5–15 min |
| Drafting | The runtime drafts chapters one at a time. You can let it run unattended; later, glance at chapters that scored low in `/autonovel:evaluate` and decide whether to retry. | 5–30 min of attention per chapter, mostly skimming |
| Revision | Read the briefs from `/autonovel:reader-panel` and `/autonovel:review`. Override anything you disagree with before running `/autonovel:revise`. | 30–90 min per book per cycle; usually 2–3 cycles |
| Export | `/autonovel:typeset`, `/autonovel:cover-print`, `/autonovel:audiobook-*` are mostly pushbutton if you have the tools and keys. | 1–2 hours, mostly waiting |

**Total wall-clock time** for a tiny 3-chapter book (like the smoke
fixtures): an afternoon. For a 70k-word novel: **a few full days of
on-and-off attention**, with the AI doing the heavy lifting and you
reading + steering. The Bells production took about a week of part-time
work spread across several months.

**Where to invest the most thought, in order:**

1. **The seed** — every downstream layer derives from it. A vague seed
   produces a vague book.
2. **The outline review** — fixing a structural issue in the outline
   takes minutes; fixing it after eight chapters are drafted takes
   hours.
3. **The first chapter eval** — voice problems caught in chapter 1
   compound across the book. Read `/autonovel:evaluate --chapter 1`
   carefully and rerun voice-discovery if needed before drafting more.
4. **Reader-panel / review feedback** in the revision phase — you'll
   want to override some items and prioritise others. The AI will
   otherwise try to address every comment, even ones that conflict.

### What the commands do

Three categories. Full reference: [`docs/commands.md`](docs/commands.md).

- **Foundation:** `gen-world`, `gen-characters`, `gen-outline`,
  `voice-discovery`, `gen-canon`, `research`.
- **Drafting & revision:** `draft`, `evaluate`, `adversarial-edit`,
  `apply-cuts`, `reader-panel`, `review`, `brief`, `revise`,
  `check-anachronism`, plus the sweep commands `draft-pass` and
  `revision-pass` that loop those across many chapters. Plus
  `chapter-summary` for a one-line-per-chapter overview table
  ("which chapters happen in <date range>?", "where does
  <character> appear?"); `motifs` for per-chapter motif density
  with back-half drop warnings (configure
  `books/{book}/motifs.md`); `talk` — a conversational
  query+suggest layer where you ask the book questions or queue
  edits that the next `revise` picks up automatically;
  `dashboard` — score / tension / pacing curve / aggregates with
  sparklines, re-rendered from existing eval logs without firing
  another evaluate; `summaries --where '<expr>'` for a
  pure-mechanical query DSL over the chapter-summary index; and
  three pre-flight scanners — `dialogue` (adverb tags / said-
  bookisms / stutters), `period-register` (period-bans roll-up),
  `pov-bleed` (interiority verbs attached to non-POV characters);
  `import-book` to bring an externally-written manuscript into
  the pipeline (`mode: edit-imported` flips draft to refuse-mode
  so the import isn't accidentally overwritten); and
  `series-arc` for the cross-book scoreboard once your series
  has ≥2 books; and `show-dont-tell` to surface every
  tell-candidate line (emotion states, interiority verbs,
  perception filters, narrator labels) for line-level revise
  targeting.
- **Export:** `art-*`, `cover-*`, `audiobook-*`, `typeset`,
  `title`, `introduction`, `landing`, `package`. The art family
  now includes `art-prompts` — author per-chapter art prompt
  files (one `.md` per chapter+surface) under
  `books/{book}/art/prompts/` for hand-editing or feeding to a
  different generator. `art-ornaments-all` reads them when
  present.

Plus 11 sidequests for non-standard operations (`shorten`, `lengthen`,
`revoice`, `split-chapter`, `merge-chapters`, `reorder`,
`remove-chapter`, `deepen-character`, `add-subplot`, `foreshadow`,
`rename-character`).

- **Movie / teaser:** `treatment` turns a book's
  foundation into a film **treatment + 2-page brief** (the prose
  deliverables a screen story — and the Future Vision X-Prize — needs
  alongside a trailer); the teaser pipeline defaults to **`mode: short`** —
  a 45–60s, ≤12-shot self-contained micro-story carried by a single
  first-person **voiceover spine** (the one thing that makes independently-
  generated AI-video clips cohere into a story; `--mode trailer` keeps the
  older longer montage shape). `teaser-brief` then **distils** that treatment into
  a one-page teaser brief (the single filmable through-line, the midpoint
  **turn**, the 3 must-have moments, the killer lines); `teaser` is the
  one-command trailer pipeline (`teaser-beats` fixes the **story spine** —
  the dramatic question, logline, want vs. opposing force, **the turn**,
  emotional arc — then selects the hook → escalation → title → button beats
  that serve it and escalate, grouped into movements; `shot-prompts` turns
  them into provider-ready, heavily-described **shot prompts**, **mining
  loaded dialogue lines** from the manuscript, authoring premise **text
  cards**, and tagging want/cost character beats so the teaser actually
  tells a story); `teaser-critique` re-checks a hand-edited teaser with the
  mechanical linter + an LLM critic that judges the story spine first **and
  scores an eight-dimension interestingness rubric plus a viewer-blind
  legibility read** (`quality.json`) — re-watching each shot **as a
  first-time viewer** (action + spoken line only, names hidden) so an
  illegible "tour of objects" can't self-pass — and `teaser-revise` applies
  the findings in place: filling the spine, lifting the weak dimensions,
  centering **people not objects**, giving each figure an **identify
  lower-third**, and running an adversarial **de-boring pass** (swap the
  flattest beats/lines for the most dramatic moments) — all with a free
  pre-generation critique, no generation cost. `teaser-render` then turns
  the prompts into **actual clips** — it validates the whole chain for **$0
  and zero quota** with an offline `stub` backend first, then renders for real
  via `grok` (free dialogue+music, no credit card) or any of `kie` / `veo` /
  `magichour` / `fal` / manual `flow` — behind **two render gates** (the
  story must be complete AND the quality rubric must clear overall ≥ 7 with no
  dimension < 5 AND every scene must be legible to a first-time viewer, so a
  structurally-complete-but-*boring-or-confusing* teaser is refused) —
  and runs a vision critique (KEEP / REGENERATE / UPGRADE-TO-PAID);
  `teaser-assemble` stitches the clips into one video with ffmpeg and runs a
  viewer-panel cut critique — the whole pipeline from a finished book to a
  teaser. See
  [`docs/prd-movie-teaser-mode.md`](docs/prd-movie-teaser-mode.md), the
  creative guide [`docs/teaser-craft.md`](docs/teaser-craft.md), and the
  backend/key map [`docs/teaser-render-providers.md`](docs/teaser-render-providers.md).

> **Confused which one to run when?** The drafting/revision commands
> have a layered relationship — `draft-pass` and `revision-pass`
> are *sweeps* that automatically call the atomic `draft` /
> `evaluate` / `brief` / `revise`; `review` and `reader-panel` only
> write *reports*, never modify chapters. The single explainer is
> [`docs/operating-guide.md` §0 — How the editing commands relate](docs/operating-guide.md#0-how-the-editing-commands-relate).
> Read it once before your second pass; the question you're about
> to ask is answered there.

### Two immune systems against AI slop

- **Mechanical:** regex scanners for banned vocabulary
  (`delve`, `tapestry`, …), em-dash overuse, sentence-length
  uniformity, fiction clichés, period-bans.
- **LLM judge:** a model distinct from the writer scores prose,
  voice, character, beat coverage. Tiers configurable in
  `project.yaml`.

### User-relevant docs

- [`docs/operating-guide.md`](docs/operating-guide.md) — **start here after install:** where human input matters, time costs, common workflows (first-pass / minor revision / factual fix / major change / adding a plot point), updating tools, restarting after a crash, starting new books or series, installing PDF/ePub/audiobook tools step-by-step.
- [`docs/commands.md`](docs/commands.md) — every `/autonovel:*` command.
- [`docs/multi-book.md`](docs/multi-book.md) — coordinating multiple books in one series.
- [`docs/writing-a-historical-series.md`](docs/writing-a-historical-series.md) — end-to-end walkthrough.
- [`docs/series-layout.md`](docs/series-layout.md) — `shared/` vs `books/`.
- [`docs/chapter-frontmatter.md`](docs/chapter-frontmatter.md) — chapter file frontmatter schema.
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — common errors and fixes.

### Optional API keys (for export only)

The pipeline does not need any keys for ordinary drafting and
revision — your AI CLI's session auth handles everything. Only the
*export* commands need third-party services:

| Service | Env var | Used by |
|---|---|---|
| fal.ai | `FAL_KEY` | cover art, ornament generation |
| ElevenLabs | `ELEVENLABS_API_KEY` | audiobook generation |

Drop a `.env` file at the root of your series folder — see
[`.env.example`](.env.example) for the shape.

### Optional external tools (for export only)

You don't need any of these to draft or revise. Install only the
ones for the export you actually want, when you want it.
`autonovel doctor` reports anything missing as a **warning** (not
an error), so you can drift through writing without thinking about
this section.

#### Pick what you actually want

| Goal | OS tools | Python extras |
|---|---|---|
| PDF only | `tectonic` | — |
| PDF + ePub | `tectonic`, `pandoc` | — |
| AI-generated cover | (above) + `fontconfig`, `potrace` | `Pillow` |
| Vector ornaments in PDF | (above) + `rsvg-convert` | `Pillow` |
| Audiobook (m4b) | `ffmpeg` (+ `ELEVENLABS_API_KEY`) | `pydub` |

#### Install the OS tools

**macOS — one shot, everything:**

```bash
brew install tectonic pandoc potrace ffmpeg librsvg fontconfig
```

**Chromebook / Debian / WSL — almost everything:**

```bash
sudo apt install -y pandoc potrace ffmpeg librsvg2-bin fontconfig
```

**Chromebook / Debian / WSL — `tectonic` is a special case.** The
`tectonic` in apt is often too old or broken; `autonovel doctor`
will flag it after install if so. If `apt install tectonic` works
for you, great. Otherwise grab the prebuilt static binary from the
official quick-install:

  <https://tectonic-typesetting.github.io/book/latest/installation/index.html>

The Linux instructions there install one self-contained binary into
`~/.local/bin/`. Verify with `tectonic --version`.

#### Install the Python extras

If you ran `pipx install '.[export]'` during the main install, you
already have these. If you ran the bare `pipx install .` and now
want to export:

```bash
pipx inject autonovel Pillow pydub
```

`pipx inject` adds packages into the same isolated environment that
holds `autonovel`, so you don't have to reinstall.

#### Verify

```bash
autonovel doctor
```

The export-tools warnings should disappear for whatever you
installed. Anything still flagged is something you don't need yet.

---

## For developers — working on autonovel itself

This section is only relevant if you want to **modify the autonovel
pipeline**, not just use it to write a novel.

### Repo layout

```
autonovel/
  package.json              # npm shim (forwards to the Python CLI)
  pyproject.toml            # the actual Python package
  bin/autonovel.js          # node wrapper that runs `python -m autonovel.cli`
  commands/                 # /autonovel:* command source — one md per command
  src/autonovel/            # housekeeping Python (CLI, adapters, validators, mechanical, templates)
  docs/                     # user-facing documentation
  tests/
    deterministic/          # Tier 1 — frontmatter, mechanical, adapters, CLI
    contracts/              # Tier 2 — every reads:/writes: backed by command body
    smoke/                  # Tier 3 — opt-in, real runtime invocation, costs money
    fixtures/
      tiny-series-{historical,scifi,literary,mystery,thriller,romance,fantasy,horror}/
      bells-reference/      # Tier-4 regression — populated from the autonovel/bells branch
  CRAFT.md, ANTI-SLOP.md, ANTI-PATTERNS.md   # prompt material consumed by writer/judge
  CLAUDE.md, AGENTS.md, GEMINI.md            # AGENTS/GEMINI symlink to CLAUDE.md
```

### Editable install

```bash
git clone https://github.com/pmilford/autonovel.git
cd autonovel
pip install -e .[test,export]
pytest tests/deterministic tests/contracts -q   # Tier 1 + 2 — fast, free
```

**CI** runs Tier 1+2 on every push and PR via
`.github/workflows/test.yml` (matrix: Python 3.11 / 3.12 / 3.13).
A weekly cron at `.github/workflows/smoke-weekly.yml` runs Tier-3
against Claude Code if a `CLAUDE_CODE_OAUTH_TOKEN` (preferred) or
`ANTHROPIC_API_KEY` repo secret is configured; without either, the
job logs the missing-auth state and exits 0 (config gap, not a
regression).

### Project memory and conventions

- [`REWRITE-PLAN.md`](REWRITE-PLAN.md) — the architecture and PR sequence.
- [`STATE.md`](STATE.md) — append-only decisions log + current Tier-1+2
  green count.
- [`ROADMAP.md`](ROADMAP.md) — PR sequence status.
- [`FUTURE-TODOS.md`](FUTURE-TODOS.md) — output-quality / portability /
  testing items deferred past v0.1.0.
- [`CLAUDE.md`](CLAUDE.md) — agent-side conventions (auth policy, tool-name
  translation, preamble/postamble contract). `AGENTS.md` and
  `GEMINI.md` symlink here.

### Test tiers

| Tier | Cost | Run when |
|---|---|---|
| 1 — deterministic | free | every commit |
| 2 — command contracts | free | every commit |
| 3 — smoke | costs (or subscription auth) | manual / pre-merge |
| 4 — Bells regression | costs | manual; gates prompt changes |

See [`docs/testing.md`](docs/testing.md).

### Adding a genre fixture

```bash
autonovel test-fixture new my-western
# Edit the produced fixture + smoke-test stub.
autonovel test-fixture run my-western
```

See [`docs/adding-a-genre-fixture.md`](docs/adding-a-genre-fixture.md).

---

## The Bells production

The **first novel produced through this pipeline**, by NousResearch:

> *The Second Son of the House of Bells*
> 19 chapters · 79,456 words · 6 automated revision cycles ·
> 6 Opus dual-persona review rounds · 24 → 19 chapters through 4
> structural merges · linocut cover (fal.ai Nano Banana 2) · 19
> woodcut chapter ornaments (vectorised) · audiobook with 4,179
> speaker-attributed segments via ElevenLabs.

The Bells production lives on the [`autonovel/bells` branch](https://github.com/pmilford/autonovel/tree/autonovel/bells)
of this repo and is the source of every "gotcha learned in
production" line in [`CLAUDE.md`](CLAUDE.md):

- Don't compress chapters below ~1800 words — they become the new weakest.
- `revise` overshoots brief targets by ~30%.
- Pacing ≈ 7 is a likely ceiling for investigation-heavy plots.
- OVER-EXPLAIN (~32%) and REDUNDANT (~26%) dominate adversarial cuts.
- Chapter renumbering must be by script, never hand-edit.
- The Stability Trap — AI defaults to safe, round-edged endings;
  push toward irreversible change, real cost, mystery.

The voice metadata for every Bells character (NARRATOR through MINOR)
is preserved verbatim in
[`src/autonovel/templates/book/audiobook/voices.yaml.example`](src/autonovel/templates/book/audiobook/voices.yaml.example) — it ships
into every new book scaffolded with `autonovel new-book` so you have
a real production reference next to your own `voices.yaml`.

The Tier-4 regression harness at `tests/fixtures/bells-reference/`
tests changes to `/autonovel:evaluate` against the frozen Bells
chapter scores so prompt drift can't silently degrade what was once
known to work.

---

## License

MIT. The original `NousResearch/autonovel` and `karpathy/autoresearch`
upstreams retain their respective licenses; see those repositories
for terms.
