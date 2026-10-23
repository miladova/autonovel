# Writing a historical series, end-to-end

A worked walkthrough using a trimmed Renaissance-Europe series as the
running example. Three books, 1450–1550, tied together by a shared
world and a single inter-book event ledger.

This guide is the long-form complement to `multi-book.md`. Read that
first for the cross-cutting rules; this file shows them in motion.

## 1. Decide the period

The 1450–1550 window is what `shared/period_bans.txt` ships pre-seeded
for (~90 entries: modern register, 19–20th-century technology
metaphors, modern institutional concepts, forensics, managerial
idioms). If your period is different, you'll seed your own — see
`commands/check-anachronism.md` for the format.

For our example:

```yaml
# project.yaml
period:
  start: 1450
  end: 1550
  region: italy   # also: france, england, spain, holy-roman-empire, ottoman
genre: historical-fiction
```

## 2. Scaffold the series

```bash
autonovel new-series renaissance-europe --genre historical-fiction
cd renaissance-europe
autonovel new-book the-coiner       --pov Anselmo --story-time-range 1456-1465
autonovel new-book the-cartographer --pov Lucia   --story-time-range 1492-1502
autonovel new-book the-inquisitor   --pov Tommaso --story-time-range 1519-1523
```

Each book gets its own `seed.txt`; you fill them in by hand. Treat
the seed as a 1–3 paragraph pitch: who the POV is, what they want,
what stands in their way, what changes.

## 3. Install commands into your runtime

```bash
# Auto-detects your installed runtimes and installs to all of them.
autonovel install
# Or pin one:
autonovel install --only claude
```

Then open the series folder in Claude Code, Codex CLI, or Gemini CLI.
The `/autonovel:*` namespace is now available.

## 4. Build the shared lore (foundation phase)

```text
/autonovel:gen-world
/autonovel:gen-characters
/autonovel:gen-canon
```

These three are series-level: they read every book's `seed.txt` plus
`project.yaml` and write into `shared/`. After they run:

```text
/autonovel:evaluate --phase foundation --book the-coiner
```

If the foundation score is ≥7.5 you're ready to draft. Below that,
re-run `gen-*` with the eval feedback in context, or hand-edit
`shared/*.md`.

## 5. Research before drafting

The `/autonovel:research` command does live web search and writes a
sourced notes file under `shared/research/notes/`. Per
`REWRITE-PLAN.md` §12, it consults primary URLs you've pre-loaded into
`shared/research/sources.yaml`:

```yaml
# shared/research/sources.yaml
sources:
  - url: https://archive.org/details/historyofvenice00brown
    title: A history of Venice (Brown, 1893)
    weight: primary
  - url: https://www.britannica.com/topic/Venice
    title: Britannica — Venice
    weight: secondary
```

Then in your runtime:

```text
/autonovel:research "Venetian apothecaries 1520"
```

Output (`shared/research/notes/venetian-apothecaries-1520.md`):

- A `## Sources` section with BibTeX shortname citations.
- Period-specific detail (theriac, mithridate, Zecca, speziale, …).
- Uncertainty hedges where the search was inconclusive.
- A `## Candidate Canon Entries` section the next
  `/autonovel:promote-canon` will merge into `shared/canon.md`.

## 6. Period guardrail

Before a draft goes live, run:

```text
/autonovel:check-anachronism 5 --book the-inquisitor
```

This is the two-pass guardrail (PR-5):

- Deterministic half: regex against `shared/period_bans.txt`. Cheap.
- Semantic half: LLM overlay for concepts, mental frames, metaphors
  the word list cannot catch. ~Sonnet-class.

The report lands in `books/the-inquisitor/edit_logs/`. The chapter
file is never modified by this command.

## 7. Voice discovery + draft

```text
/autonovel:voice-discovery --book the-inquisitor
/autonovel:gen-outline --book the-inquisitor
/autonovel:gen-canon --book the-inquisitor     # this book's outline facts → books/<name>/canon.md
/autonovel:draft 1 --book the-inquisitor
```

Voice discovery produces five distinct trial passages in
`books/<name>/voice.md` Part 2 and picks one with a written
justification. Drafting reads voice + outline + canon + events and
writes `books/<name>/chapters/ch_01.md` with frontmatter:

```yaml
---
book: the-inquisitor
chapter: 1
pov: Tommaso
story_time: 1519-04-12
events: [E-001]
status: draft
---
```

`story_time` and `events` are load-bearing — they're how the
multi-book context loader gates spoilers (`multi-book.md`).

## 8. Revision loop

**Per chapter** (when you're calibrating early in the book):

```text
/autonovel:evaluate --chapter 5 --book the-inquisitor
/autonovel:adversarial-edit 5 --book the-inquisitor
/autonovel:apply-cuts 5 --book the-inquisitor --types OVER-EXPLAIN REDUNDANT
/autonovel:brief 5 --book the-inquisitor --from auto
/autonovel:revise 5 --book the-inquisitor
```

**Sweep across chapters** (when the foundation is solid and you want
forward progress on the whole book):

```text
/autonovel:revision-pass --chapters all
```

That sweeps `check-anachronism → brief --from auto → revise → evaluate`
across every drafted chapter, sequentially. Add `--parallel 3` to fan
out across three subagents at once (faster but each chapter's revise
sees one-pass-stale neighbour summaries; a second sweep propagates).

**For the initial drafting too** there's a sweep:

```text
/autonovel:draft-pass --chapters 1-19
```

Drafts every chapter in the outline range in ascending order, with
optional one-shot retry per chapter if the eval scores below
`chapter_threshold`. Same per-chapter quality as
`/autonovel:draft N`, just one rollback point for the whole sweep.

**Per book (after all chapters drafted):**

```text
/autonovel:developmental-edit --book the-inquisitor
/autonovel:structure-review --book the-inquisitor
/autonovel:reader-panel --book the-inquisitor
/autonovel:review --book the-inquisitor
```

The editor's read comes first: `_end` offers it as the next step once
the outline's last chapter is drafted. Its letter says what to revise and
in what order; the reviewers below are instruments it compares itself
against. Then structure. Historical fiction is the genre most exposed to the
anecdote chain: the record is episodic by nature (deals, deaths,
elections, wars arrive on their dates), so a book that follows it
chapter by chapter reads as a chronicle however good each chapter
is. `/autonovel:structure-review` checks that the novel imposes a
spine the history lacks — chapter N+1 happening *because of* chapter
N, stakes rising per act on the same bet, one question the ending
answers, no chapter that could be cut — and its structural brief
candidates feed `/autonovel:revision-pass --chapters structural`.
Stop when the structure gate passes (score ≥ 4, no removable
chapter) and the reader panel and the dual-persona review converge to
hedged / qualified items rather than concrete defects
(`operating-guide.md` §2g).

## 9. Promote canon

After every drafting session, observations land in
`books/<name>/pending_canon.md`. Periodically:

```text
/autonovel:promote-canon
```

This walks every book's pending_canon.md, dedupes against
`shared/canon.md` and the book's own `books/<name>/canon.md`, parks any
contradictions under a `# Conflicts` header, and merges the rest —
chapter-derived facts into the book's `canon.md` (they bind that book
only), research-cited facts into `shared/canon.md`. It's single-threaded
across the series (see the `.autonovel/in-progress.lock` discipline in
`multi-book.md`). Writing a second version of one of these books? See
"A rewrite" in `multi-book.md`.

## 10. Cross-book event coordination

`shared/events.md` is the inter-book ledger. When the same historical
moment is referenced in multiple books, add an `## E-NNN — <title>`
entry with `rendered_in:` listing every chapter that depicts it:

```markdown
## E-007 — Sack of Mantua

- date: 1494-09-12
- location: Mantua
- present: Lucia, Anselmo (offstage)
- canonical: yes
- rendered_in:
  - the-cartographer/ch_04
  - the-inquisitor/ch_12
- book_constraints:
  - the-cartographer: narrate in real time
  - the-inquisitor: reference, do not narrate
```

The drafter reads this when working on either chapter. The validator
at `src/autonovel/validators/events.py` flags `rendered_in:` entries
that name a book missing from `project.yaml`.

## 11. Export

When all three books are revised:

```text
/autonovel:typeset --book the-inquisitor
/autonovel:cover-print --book the-inquisitor --pages 312 --paper cream
/autonovel:audiobook-script --book the-inquisitor
/autonovel:audiobook-voices --book the-inquisitor --list
/autonovel:audiobook-voices --book the-inquisitor --set NARRATOR=abc123 …
/autonovel:audiobook-generate --book the-inquisitor --chapter 1
/autonovel:audiobook-assemble --book the-inquisitor --format m4b
/autonovel:landing --book the-inquisitor
/autonovel:package --book the-inquisitor
```

Or, in one shot:

```text
/autonovel:run-pipeline --books the-coiner,the-cartographer,the-inquisitor --phase export
```

## 12. Tier-3 smoke parity

The three-book Renaissance series is not the same as the shipped
`tiny-series-historical/` smoke fixture, which is one POV / 3 chapters.
But the pipeline is identical — the smoke fixture exists to lock the
contract. Running `pytest tests/smoke -m "smoke and genre('historical')"`
exercises `/autonovel:research` against the same period-bans list
your real series uses.

## Common gotchas (learned in production)

- **Don't over-compress.** Any chapter below ~1800 words becomes the
  new weakest. Sweet spot for compressed chapters is 2200–3000w.
- **`/autonovel:revise` overshoots** by ~30% — brief 3200w, expect
  3800–4200w.
- **Chapter renumbering** after `/autonovel:merge-chapters` /
  `/autonovel:remove-chapter` runs by script (collision-safe `mv`),
  never by hand-edit. Same discipline applies to
  `/autonovel:rename-character` (word-boundary `sed` with overlap
  refusal — refuses `Ana` if `Anatolia` exists).
- **The Stability Trap.** AI defaults to safe, round-edged endings;
  use `/autonovel:revise` with a brief that explicitly demands
  irreversible change, cost, and mystery.
