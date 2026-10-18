---
name: autonovel:help
description: Discoverability layer over every autonovel command. Zero-arg shows category-grouped overview; `<topic>` shows in-depth guide for a workflow.
argument-hint: "[<topic>]   topics: art, foundation, drafting, revising, structure, reading, typeset, research, front-matter, sweeps, tui, cli, next-steps"
model_tier: light
allowed-tools: []
reads: []
writes: []
context_mode: none
---

<purpose>
Single discoverability layer over autonovel's ~70 slash-commands +
CLI subcommands. Zero-arg: category-grouped overview so a new user
doesn't have to read 70 frontmatters to find the right tool.
`<topic>`: in-depth guide for a single workflow with the exact
command sequence, when to use what, and the no-key paths where
they exist.

Surfaced 2026-04-30 by author testing: "I couldn't see what to do
with the art commands there, I had to look at the version github."
The TUI's Help tab is per-state (situational); this command is
per-topic. Both are needed.
</purpose>

<workflow>
Parse `$ARGUMENTS` to one of: empty (overview), or one of the
canonical topics below. Anything else: print "no help topic
`<input>`; pick from: art, foundation, drafting, revising, structure, reading,
typeset, research, rewrite, front-matter, sweeps, tui, cli, next-steps"
and stop.

For each mode, print a self-contained chat block matching the
shape below verbatim. The blocks are intentionally concrete:
exact command sequences, exact flag names, the no-key path where
one exists.

================================ EMPTY (overview) =================

```
# autonovel commands at a glance

Run `/autonovel:help <topic>` for an in-depth guide on one
workflow. Topics:

  art          — covers / chapter ornaments / book images.
                 Three free paths (typographic / pollinations /
                 wikimedia) + paid (fal / replicate / openai).
  foundation   — gen-world → gen-characters → voice-discovery →
                 gen-canon → design → gen-outline. The
                 before-drafting sequence. design makes the
                 book-level decisions (climax, question, opponent,
                 plants, sequences) the outline then carries.
  drafting     — draft / draft-pass / sidequest. Writing prose.
  revising     — revise / revision-pass / brief / evaluate /
                 adversarial-edit / apply-cuts / lengthen /
                 shorten. Iterative quality work. diff shows
                 what changed since a tag / your last read.
  structure    — structure-review: one story building to a climax,
                 or a string of episodes? Causal chain, stakes
                 ladder, removable chapters, structural briefs; the
                 gate review's stop-revising verdict waits on.
                 developmental-edit: an editor's full read of the
                 whole book and a ranked letter on the story.
  reading      — see the book's shape without re-reading it:
                 story-map (one HTML page: synopsis, plot-thread
                 grid + score/tension curve, characters, timeline,
                 places) / chapter-summary / summaries / dashboard.
  typeset      — typeset / package / front matter / back matter.
                 Output (PDF, ePub, audiobook).
  front-matter — title / introduction / glossary / appendix /
                 cover-composite / cover-print.
  movie        — full teaser pipeline (default mode: SHORT — a 45-60s,
                 <=12-shot micro-story carried by one first-person voiceover
                 spine; the coherent AI-video shape. --mode trailer = older
                 longer montage). treatment (film treatment +
                 2-page brief) → teaser-brief (distil the through-line +
                 turn + killer lines) → teaser (teaser-beats →
                 shot-prompts → teaser-critique scores the interestingness
                 rubric + a viewer-blind legibility read ⟳ teaser-revise
                 lifts weak dims + de-borings) → teaser-refs (approve
                 character refs before spend) → teaser-render (offline
                 `stub` to validate free, then `grok` real clips + vision
                 critique) → teaser-vo (free Edge-TTS narration spine) →
                 teaser-assemble (ffmpeg stitch + narration over a ducked
                 bed + figure-ID lower-thirds + cut critique). Default mode
                 SHORT (45-60s, <=12 shots, first-person VO spine). Two
                 render gates: story-complete AND quality (≥7, every scene
                 legible) — "boring" AND "who is this?" are blocked. Built in
                 the book's genre, people not objects. X-Prize-shaped. See
                 docs/teaser-craft.md + docs/teaser-render-providers.md.
  research     — research --from-seed / promote-canon /
                 impact-of / research --query.
  rewrite      — a second version of a story a finished book
                 already tells: new-book --isolated, book-scoped
                 canon (canon-partition), evaluate --compare
                 --vs-book, which foundation steps to skip.
  sweeps       — multi-chapter operations: draft-pass,
                 revision-pass, summarize-chapter --stale.
  tui          — `autonovel tui` long-running terminal browser.
  cli          — autonovel onboard / status / cost / doctor /
                 install / install-export-tools.
  next-steps   — /autonovel:next / /autonovel:resume,
                 situational signals, the postamble hint line.

Don't see what you need? `/autonovel:next` shows the prioritised
state-aware action list — most of the time it answers "what now?"
without you having to know command names.
```

============================== TOPIC: art =========================

```
# Art workflow — covers, ornaments, plates

Three FREE paths (no API key) + paid AI providers:

(1) TYPOGRAPHIC-ONLY (NYRB Classics shape: title + author on
    solid color; no AI, no key, no install):

      /autonovel:cover-print --book <name> --pages <N> \
          --typographic-only [--bg-color "#1a3b5c"]

(2) POLLINATIONS.AI (free AI, no key, rate-limited):

      /autonovel:art-style --book <name>
      /autonovel:art-directions --book <name> --surface cover
      /autonovel:art-curate --book <name> --surface cover \
          --provider pollinations
      /autonovel:art-pick --book <name> --surface cover --variant 2
      /autonovel:cover-composite --book <name>
      /autonovel:cover-print --book <name> --pages <N>

(3) WIKIMEDIA COMMONS (public-domain art; perfect for historical
    fiction). Same flow as (2) but `--provider wikimedia`. Searches
    the Commons API, returns candidates with license + attribution
    metadata, downloads + center-crops to target aspect.

(4) PAID providers — fal / replicate / openai. Same flow as
    (2) but `--provider fal` / `replicate` / `openai` and the
    corresponding env-var key. Costs money; more consistent
    quality; no rate limits.

Provider precedence: `--provider` (per-call) wins over
`project.yaml :: image.provider` (per-series default), which
wins over the repo default `pollinations`. Set `image.provider`
once in project.yaml and you can drop the flag from every
art-* call.

Per-chapter ornaments (a small image at each chapter opening):

      /autonovel:art-style --book <name>             # one-time
      /autonovel:art-prompts --book <name> \         # one .md per chapter
          --surface ornament
      /autonovel:art-ornaments-all --book <name> \   # generate every
          --provider pollinations                     # chapter's PNG
      /autonovel:art-vectorize --book <name>         # PNGs → SVGs
                                                      # for sharper print
                                                      # rendering

Bring-your-own image (a painting you scanned, a map you drew):

      /autonovel:art-import --book <name> \
          --file ~/Downloads/painting.jpg \
          --surface plate --slug fugger-portrait \
          --caption "..." --attribution "..."

Skips the AI flow entirely. Typeset weaves the imported plate
into the manuscript at the placement you set.

The 10 art commands at a glance:

  /autonovel:art-style          derive visual style (run once)
  /autonovel:art-directions     N prompt directions for a surface
  /autonovel:art-curate         run directions through provider
  /autonovel:art-pick           select one variant as final
  /autonovel:art-prompts        per-chapter authored prompts
  /autonovel:art-ornaments-all  generate every chapter ornament
  /autonovel:art-import         import existing image (skip AI)
  /autonovel:art-vectorize      PNGs → SVGs (potrace)
  /autonovel:cover-composite    overlay title/author on cover art
  /autonovel:cover-print        wraparound print + thumbnails

`/autonovel:typeset` auto-prepares vectorize / composite /
cover-print at print time; pass `--no-auto-prepare-art` to opt
out. Detail: docs/operating-guide.md §5c.1.
```

============================== TOPIC: foundation ==================

```
# Foundation — the before-drafting sequence

Order matters; each step reads what previous steps wrote:

  1. /autonovel:gen-world --book <name>
        → shared/world.md
  2. /autonovel:gen-characters --book <name>
        → shared/characters.md
  3. /autonovel:voice-discovery --book <name>
        → books/<name>/voice.md (Parts 1-4)
  4. /autonovel:gen-canon
        → shared/canon.md (series-wide hard facts)
  5. /autonovel:design --book <name>
        → books/<name>/design.md: the climax first, then the question
          it answers (posed in the first quarter), the one action and
          span, the rival who wants the same prize (a dated plan, on
          stage every act), the skills the climax spends (each planted
          inside its own contest, tested, paid), rehearsals, the cast
          as a web, sequences, clocks, places, voice. Tested against
          shared/craft/DESIGN.md and read cold by a second reader.
  6. /autonovel:gen-outline --book <name>
        → books/<name>/outline.md (chapter beats, bound to the design:
          each chapter lists its sequence, plants, tests, payoffs)
  7. /autonovel:gen-canon --book <name>
        → books/<name>/canon.md (this book's outline-committed facts;
          seeded FROM the outline, so it runs after step 6)
  8. /autonovel:evaluate --phase foundation --book <name>
        → score the foundation (incl. `design`); iterate any stage
          that flagged.

`/autonovel:next` walks you through this in order; it knows
which stage is missing and recommends the right command. Don't
memorise — read the action list.

For period fiction (project.yaml :: period.start set):

  /autonovel:research --from-seed --book <name>

Runs BEFORE gen-world; populates shared/research/notes/ so
gen-world has primary-source citations to ground itself in. The
foundation gap detector at /autonovel:next surfaces this when
period is set and the notes dir is empty.

Onboarding (BEFORE foundation):

  autonovel new-series <name>
  cd <name>
  autonovel new-book <book>
  autonovel onboard <book>      # interactive wizard

Wizard captures pitch / period / genre / working title / human
author / attribution style into seed.txt + project.yaml. Every
prompt has a (skip) option that lands a `## Onboarding TODO`
block in seed.txt for /autonovel:next to surface later.
```

============================== TOPIC: drafting ====================

```
# Drafting — writing prose

Single chapter:

  /autonovel:draft <N> --book <name>

Reads world / characters / canon / voice / outline / prior-chapter
summaries; writes books/<name>/chapters/ch_NN.md +
books/<name>/chapters/ch_NN.summary.md.

Sweep (write the rest of the book in one invocation):

  /autonovel:draft-pass --chapters <range> --book <name>

Per chapter: draft → check-anachronism → evaluate → if score
< threshold, brief + revise + re-eval (keep best) → per-chapter
promote-canon. A SPINE CHECK against the outline's ## Causal spine
also sends a chapter to the revise loop when it doesn't follow from
the one before. End of sweep: final promote-canon. With `--deep`:
also structure-review + reader-panel + Opus review on the finished
pass.

Single-chapter sidequests (cut a chapter, add a character, change
ending, etc.):

  /autonovel:sidequest

Dispatcher menu for non-standard operations.
```

============================== TOPIC: revising ====================

```
# Revising — iterative quality work

Single-chapter quality cycle:

  /autonovel:evaluate --chapter <N> --book <name>
  /autonovel:adversarial-edit <N> --book <name>     (optional)
  /autonovel:apply-cuts <N> --book <name>           (optional;
                                                     deterministic)
  /autonovel:brief --chapter <N> --book <name>
  /autonovel:revise --chapter <N> --book <name>
  /autonovel:evaluate --chapter <N> --book <name>   (re-score)

Sweep:

  /autonovel:revision-pass --chapters <range> --book <name>

Bundles brief + revise + re-eval per chapter, with the
verify→panel→backup closer documented in operating-guide §2b.1.

Targeted sub-tasks (use one or more between revise cycles):

  /autonovel:lengthen <N> --book <name> --target-words <W>
  /autonovel:shorten <N> --book <name> --target-words <W>
  /autonovel:deepen-character <N> --book <name> --character <X>
  /autonovel:revoice <N> --book <name>
  /autonovel:foreshadow <N> --book <name>
  /autonovel:add-subplot <N> --book <name>

After foundation mutations (promote-canon flipped facts / research
added new notes): which chapters reference the now-wrong fact?

  /autonovel:impact-of --book <name>
                       --source promote-canon|gen-canon|
                                voice-discovery|add-character|
                                gen-characters|gen-world|add-source|
                                rename-character|merge-chapters|
                                reorder|remove-chapter|research

Five report shapes:
  • canon-driven (promote-canon, gen-canon) — Superseded-block grep.
  • mtime-driven (voice-discovery, add-character, gen-characters,
    gen-world, add-source) — chapters older than the foundation file.
  • rename-verify (rename-character) — straggler grep for the OLD
    name from the most recent rename in command-log.
  • renumber-refs (merge-chapters, reorder, remove-chapter) — prose
    grep for chapter-number cross-references after a renumber.
  • research — LLM scan of new notes vs every chapter.

Mechanical first; --with-llm classifier for canon-driven sources
cuts the false-positive review burden.

Checking what a revision actually changed (without re-reading):

  /autonovel:diff --book <name>                       (last tag → now)
  /autonovel:diff --book <name> --from last-read --mark-read
  /autonovel:diff --book <name> --from draft_1 --to HEAD --chapters 14
  /autonovel:diff --book <name> --from checkpoint:latest   (no git needed)

Writes books/<name>/edit_logs/diff_<from>_<to>.html — open it in a
browser: word-level changes inside their paragraphs, unchanged text
folded, j/k jumps change to change ("change N of M"), word deltas
per chapter. Add --annotate for a one-line "why" per change traced
to the brief / talk turn / review item that asked for it. The same
run rebuilds story_map.html (synopsis, threads, characters, timeline,
places) beside it: a Story map button in the diff toolbar, and each
changed chapter in the map links back to its changes.

Book-level (after a full draft or a sweep — every chapter can score
well while the book is a string of episodes):

  /autonovel:developmental-edit --book <name>   (an editor's read + letter)
  /autonovel:first-read <N> --book <name>       (a cold reader: what a newcomer
                                                 can't follow; draft runs it)
  /autonovel:structure-review --book <name>
  /autonovel:revision-pass --chapters structural --book <name>

Detail: /autonovel:help structure.
```

============================== TOPIC: structure ===================

```
# Structure — is it one story, or a string of episodes?

Chapter scores, the reader panel and the dual-persona review are
prose-weighted. All three can stay green (4★, "would buy it") while
the book reads as a string of short anecdotes, not a continuing story
building to a climax. structure-review is the book-level judge:

  /autonovel:structure-review --book <name>
        → books/<name>/edit_logs/structure_review.json + .md
          through-line (one question; does the ending answer it?)
          causal chain  (ch N → N+1: because / after / unrelated)
          stakes ladder (per act: strictly higher, same bet?)
          removability  (which later chapter breaks if this one
                         is cut? none = an anecdote)
          climax build  (do the last 20% converge or just finish?)
          structure score 1–5 (prose is NOT scored here)
          3–7 structural brief candidates

Acting on it:

  1. Cross-chapter moves it lists (merge / cut / reorder / split)
     are yours to run, e.g.
       /autonovel:merge-chapters --chapters 15,16 --book <name>
     then re-run structure-review (numbering changed).
  2. /autonovel:revision-pass --chapters structural --book <name>
       brief --from auto writes `kind: structural` briefs; revise
       restructures inside each chapter (never touches neighbours).
  3. /autonovel:structure-review --book <name>      (re-check)
  4. /autonovel:review --book <name>
       stop-revising needs structure ≥ 4 and no removable chapter.

An editor's read (the judgement no score gives):

  /autonovel:developmental-edit --book <name> [--focus "<your concern>"]
        one reader reads every chapter in order, cold (before the
        seed, outline, summaries and reviews), keeping notes per
        chapter; counts what the diagnosis rests on (time gaps,
        flash-forwards, where the protagonist is wrong, when each
        principal and opponent appears); then writes
        books/<name>/edit_logs/editor_letter.md: what the book is,
        what must survive, the story's problems ranked by what they
        cost the reader, what in the pipeline caused them, what to
        do in order of effect for cost, and where it disagrees with
        the reviewers. The notes behind it: editor_read_notes.md.
  /autonovel:developmental-edit --book <name> --stage
        also queues its in-chapter fixes in briefs/conversation.md
        for the next revision-pass; frames, cuts and merges stay
        your decision.

Before drafting (cheapest place to fix it):

  /autonovel:design --book <name>             the book-level decisions:
                                              climax, question, rival,
                                              plants, rehearsals, cast,
                                              sequences (design.md)
  /autonovel:gen-outline --book <name>        writes ## Spine,
                                              ## Stakes ladder,
                                              ## Causal spine
  /autonovel:gen-outline --book <name> --add-spine
        retrofit the three sections onto an existing outline
  /autonovel:evaluate --phase foundation --book <name>
        scores `causal_spine`

Free data views (no LLM):

  autonovel mechanical structure-dossier books/<name> --format markdown
  autonovel mechanical structure-validate books/<name> --format markdown
  autonovel mechanical prolepsis books/<name> --format markdown
        candidate narrator flash-forwards per chapter
```

============================== TOPIC: reading =====================

```
# Reading — see the book's shape without re-reading it

The page (opens in any browser, works offline and on a phone):

  /autonovel:story-map --book <name>
        → books/<name>/edit_logs/story_map.html  (+ story_map.json)

  Tabs: Synopsis (every chapter summary in reading order, act
  headers from the outline; a one-line-per-chapter switch reads
  the whole book in minutes) · Threads (plot threads × chapters —
  plant / turn / payoff / touch — with the score, tension and
  irreversible-change curves directly under it on the same
  chapter axis) · Characters (who is on stage where, each
  principal's state change per chapter) · Timeline & places
  (story time to scale, gaps over a year labelled; places
  visited vs only named).

  First run writes books/<name>/threads.md — the plot-thread
  ledger — from the outline + chapter summaries (never the
  prose). Edit it by hand any time; re-run to redraw. Rewrite
  it from scratch with:

  /autonovel:story-map --book <name> --refresh-threads

  It shows data, not verdicts: which chapters touch a thread and
  how long it goes untouched; you decide what that means.

Terminal views of the same data:

  /autonovel:chapter-summary --book <name>    one row per chapter
  /autonovel:summaries --book <name> --where 'cast contains X'
  /autonovel:dashboard --book <name>          score/tension sparklines
  /autonovel:talk --book <name> "<question>"  ask the book (LLM)
```

============================== TOPIC: typeset =====================

```
# Typeset — produce the PDF + ePub + audiobook

End-to-end (the command that does everything):

  /autonovel:package --book <name>

Runs: typeset PDF + ePub + cover composite + cover print + landing
page. With ElevenLabs key set, also: audiobook script + assemble.

PDF + ePub only:

  /autonovel:typeset --book <name>

Auto-prepares stale art (vectorize, cover-composite, cover-print)
unless `--no-auto-prepare-art`. Reads front-matter (preface,
introduction, glossary), chapters, back-matter (appendix); writes
PDF + ePub under books/<name>/typeset/.

Front matter (before chapter 1):

  /autonovel:title --book <name>           # 5 candidates → --pick N
  /autonovel:introduction --book <name> \
      --from user|auto|both
  /autonovel:glossary --book <name> --from auto

Back matter (after the last chapter):

  /autonovel:appendix --book <name> \
      --sections timeline,bios,sources,notes \
      --from auto|user|both

External tools required: tectonic (PDF), pandoc (ePub),
fontconfig (cover fonts), potrace (vectorize). The user-facing
helper:

  autonovel install-export-tools --apply

Detects OS + autonovel install method and walks the install with
verify-after-install. Handles the apt-tectonic-too-old fallback
to the upstream prebuilt binary.

Chapter datelines and wide plates: each chapter's frontmatter
`dateline: "Venice, autumn 1473"` prints under its title (set it when
the book moves between times or places); a plate in
books/<name>/typeset/plates.yaml with `layout: landscape` gets a
sideways full page in the PDF.

For a typography-only cover (no AI art at all):

  /autonovel:cover-print --book <name> --pages <N> \
      --typographic-only [--bg-color "#1a3b5c"]
```

============================== TOPIC: research ====================

```
# Research — sourced notes + canon + impact analysis

Three modes of /autonovel:research:

  /autonovel:research "<topic>"
        Live web search; writes shared/research/notes/<slug>.md
        with sourced facts and BibTeX-style citations.

  /autonovel:research --from-seed --book <name>
        Reads seed.txt + project.yaml :: period; auto-derives
        2-4 topics; runs the per-topic workflow for each.

  /autonovel:research --query "<question>"
        LLM Q+A over existing shared/research/notes/ (no web
        search). Cross-source synthesis with [shortname] citations.

Inventory of what's there (free, no LLM):

  autonovel mechanical research-index <series-root>

Per-note metadata table (slug / title / updated / words / sources
/ citations). Optional --grep (full body) and --cites (Sources
block only) filters.

After research adds new facts that conflict with existing canon:

  /autonovel:promote-canon

Promotes pending entries; research-tagged entries beat existing
canon facts with the citation recorded in a `## Superseded` block.

Then which chapters need revising?

  /autonovel:impact-of --book <name> --source promote-canon
                       [--with-llm]

Token-grep finds chapters that reference the now-wrong fact;
--with-llm classifies each match as HIGH/MEDIUM/LOW/FALSE_POSITIVE
so the action checklist is precise.

Free public-domain art via Commons (perfect for historical
fiction):

  /autonovel:art-curate --book <name> --surface cover \
      --provider wikimedia
```

============================== TOPIC: rewrite =====================

```
# Rewrite — a second version of a story a finished book already tells

Same world, same cast, same years; a different approach to the book
(new outline, new voice, new pacing). It is a NEW BOOK in the SAME
series, with two guards so the old book cannot leak into the new one.

  0. (once per series, before the new book) partition canon:
     /autonovel:canon-partition --to-book <old-book>
        Moves the old book's chapter-derived facts out of
        shared/canon.md into books/<old-book>/canon.md and asks
        you to classify any untagged leftovers (real history stays
        shared; the old book's plot inventions move). Without this
        the rewrite is bound by the original's plot choices.

  1. Re-design it as a new book:
       /autonovel:design --book <new-name> --from-book <old-book> \
                         --notes "<what you want the book to be>"
        Creates the book with `context: isolated` (/autonovel:draft
        never reads the old book's chapters), copies its art, reads
        its editor's letters and summaries (never its chapters),
        writes the new seed from your notes and design.md with a
        keep-ledger (what worked and has a place) and a fault-ledger
        (each diagnosed fault and the decision that prevents it).
        Use this when /autonovel:developmental-edit says the problems
        are design-level. (By hand instead: `autonovel new-book
        <new-name> --pov "<same POV>" --story-time-range <same years>
        --isolated`, write its seed.txt, then /autonovel:design.)

  2. Read books/<new-name>/design.md; say what to change.

  3. Foundation — skip the series-scoped steps, in this order:
       /autonovel:gen-outline --book <new-name>      (bound to the design;
                                                      reassigns the plates)
       /autonovel:voice-discovery --book <new-name>   (fresh voice.md)
       /autonovel:gen-canon --book <new-name>         (book half only;
                                                        seeded from the outline)
     Do NOT re-run gen-world / gen-characters — they would rewrite
     the shared files the old book was drafted against. New people
     the rewrite needs go in with /autonovel:add-character --book <new-name>.
     /autonovel:next walks this order for you.

  4. Draft as usual (draft / draft-pass). Measure against the
     original with the cross-book head-to-head:
       /autonovel:evaluate --compare N,N --book <new-name> \
                           --vs-book <old-book>

  /autonovel:series-arc treats the two books' overlapping ranges as
  expected (no backwards-jump penalty at the boundary).
```

============================== TOPIC: front-matter ================

```
# Front matter and back matter — what wraps the chapters

Render order in the typeset PDF:

  Title page → Preface → Introduction → Glossary → chapters
                                       → Appendix → colophon

Each surface is optional; typeset's front-/back-matter builder
uses `\IfFileExists` guards to skip absent files.

  Title page:

      /autonovel:title --book <name>           # 5 candidates
      /autonovel:title --book <name> --pick 3 [--pick-author 2]
      /autonovel:title --book <name> --set "<title>" --author "<X>"

  Preface (hand-authored):

      /autonovel:introduction --book <name> --from user

      Scaffolds preface.md with HOW-TO-EDIT comments and bracketed
      placeholders. You replace them with real prose. Acknowledge
      Autonovel openly in the thanks paragraph if it substantively
      drafted the book.

  Introduction (AI-drafted essay; you edit):

      /autonovel:introduction --book <name> --from auto

      Drafts a 600-1200 word essay framing the book's central
      question. Always review before typeset — over-explanation
      and marketing-copy register are common AI tells in essay
      form.

  Glossary (period-vocabulary reference; critical for historical
  fiction):

      /autonovel:glossary --book <name> --from auto

      AI-extracts period vocabulary from prose + research notes
      + canon; produces an alphabetised list. Appears right
      before chapter 1.

  Appendix (timeline, bios, sources, notes):

      /autonovel:appendix --book <name> \
          --sections timeline,bios \
          --from auto

      Default sections: timeline + bios. Add sources / notes as
      needed.

The TUI's "Front + back matter" tab shows every surface with
✅/❌ for presence + word count + the exact slash-command to
create it when absent.
```

============================== TOPIC: sweeps ======================

```
# Sweeps — multi-chapter operations

Sweeps write a sweep-progress file at .autonovel/sweep-progress.json
per chapter completed. /autonovel:resume reads it and offers
"continue from chapter N" recovery if a sweep gets interrupted
(power loss, /clear, budget exhaustion).

  /autonovel:draft-pass --chapters <range> --book <name>
        Write the rest of the book.

  /autonovel:revision-pass --chapters <range> --book <name>
        Iterative quality pass over a range.

  /autonovel:summarize-chapter --stale --book <name>
        Refresh stale per-chapter .summary.md files (chapters
        whose .md is newer than the summary). Critical after a
        sweep where revise step 9 may have silently no-op'd.

The lifecycle's verify-writes guard fires a 🔴 banner at the TOP
of the postamble when claims don't match disk:
  - chapter file claimed modified but bytes match the checkpoint
    (silent revise-failure)
  - chapter file modified WITHOUT regenerating its .summary.md
    (continuity-breaking)
The banner spells out the exact remediation command per chapter.

Resume after interruption:

  /autonovel:resume

Reads sweep-progress.json; prints the precise "continue from
chapter N" with the remaining chapter list.
```

============================== TOPIC: tui =========================

```
# autonovel tui — long-running terminal browser

  autonovel tui [--book <name>]

Read-only by contract. Never acquires the lock; safe to run
alongside an active sweep. Polls FS every 5 s.

Tabs (numeric keys 0-6):

  0  Help (live)        per-suggested-command rationale + reads
                        + writes
  1  Chapters           DataTable + score+tension sparklines +
                        chapter detail (POV, story-time,
                        cast, plot, threads opened/closed,
                        POV state at close)
  2  Research           per-note table + preview pane
  3  Foundation         status of every foundation file
  4  Front + back matter  presence + word count for preface /
                          introduction / glossary / appendix
  5  Reviews            reader-panel + Opus review + structure
                        review presence, structure score,
                        last-run timestamps
  6  Commands           last 15 logged commands + situational
                        next-actions + canonical next step

Keyboard:

  q  quit
  r  refresh now (don't wait for the 5 s timer)
  p  pause / resume auto-refresh — pause when reading prose or
     copying text
  b  switch to next book in series

⚠ next to the status column = chapter `.md` is newer than its
.summary.md. Fix: /autonovel:summarize-chapter --stale --book
<name>.

Copy / paste: textual captures mouse events. Hold shift while
dragging to bypass — most terminals (GNOME Terminal, iTerm2,
Windows Terminal, kitty, Alacritty) pass shift-drag through.

Optional dep: `pip install 'autonovel[tui]'` or
`pipx inject autonovel textual`.
```

============================== TOPIC: cli =========================

```
# CLI subcommands — run from the shell, not the runtime

Setup:

  autonovel new-series <name>          scaffold a new series
  autonovel new-book <book>            scaffold a book in current series
  autonovel onboard <book>             interactive wizard

Daily workflow:

  autonovel status                     phase, scores, last command
  autonovel cost                       token + USD spend rollup
  autonovel doctor                     sanity-check the series —
                                       required dirs, project.yaml
                                       shape, missing CLI tools
                                       (tectonic / pandoc / ffmpeg /
                                       Pillow / fontconfig), AND
                                       typeset fonts (fc-match
                                       lookup; catches missing
                                       EB Garamond before tectonic
                                       walks fontspec's fallback
                                       chain mid-build).
                                       --install-missing hands off
                                       to install-export-tools.
  autonovel tui                        long-running terminal UI

Environment setup:

  autonovel install-export-tools       install tectonic / pandoc /
                                       ffmpeg / Pillow / fonts /
                                       etc. with per-tool verification

Maintenance:

  autonovel install [--pin-model]      write /autonovel:* into runtime
                                       command paths (idempotent). Default:
                                       no model pin (session model wins);
                                       --pin-model to pin per-tier.
  autonovel rollback                   restore from a checkpoint
  autonovel refresh-templates          re-copy package templates over
                                       a live series (default: typeset/
                                       and the shared/craft/ reference
                                       docs the writer and judge read)

Import:

  autonovel import-book <name> --from <path> [--reverse-engineer]
        Externally-written manuscript → autonovel-shape chapters.

For each, `autonovel <subcmd> --help` shows full flag list.
```

============================== TOPIC: next-steps ==================

```
# /autonovel:next — situational guidance

  /autonovel:next [--book <name>]

Inspects the live filesystem and emits a prioritised action list:

  HIGH    pending canon conflicts; chapter regressions; briefs
          newer than chapters (revise didn't run); summaries
          newer than chapters (continuity drift); past-end-of-
          book draft commands.

  MEDIUM  reader-panel / Opus review reports stale; git backup
          state.
  MEDIUM  book-level structure gate: structure-review missing,
          stale, or blocking (score < 4 / a removable chapter →
          revision-pass --chapters structural).
  MEDIUM  no editor's letter on a drafted book →
          developmental-edit (LOW once chapters change after it).

  LOW     missing title, missing front matter, period fiction
          without a glossary, stale typeset PDF.

Plus the canonical pipeline next step at the bottom.

Every command's postamble ALSO ends with a one-line `💡 Maybe
try:` hint pulled from the same enumerator. Most of the time you
don't need to call /autonovel:next separately — the hint is right
there in the response.

Recovery after interruption:

  /autonovel:resume

Detects an in-flight command (.autonovel/in-progress.lock) AND
an interrupted sweep (.autonovel/sweep-progress.json). For sweep
interrupts, prints the precise "continue from chapter N" with
the remaining chapter list.
```
</workflow>

<acceptance>
- Zero-arg invocation prints the category overview with every topic
  listed (including `structure`).
- Every named topic prints its in-depth block verbatim.
- Unknown topic argument prints a usage line listing valid topics
  and stops cleanly.
- Read-only: no file_read, no file_write, no bash. The command
  is pure documentation surfaced in the runtime chat.
</acceptance>
