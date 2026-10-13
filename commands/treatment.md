---
name: autonovel:treatment
description: Generate a film treatment plus a 2-page brief/synopsis from a book's foundation — the prose deliverables a screen story (and the Future Vision X-Prize) requires alongside a trailer.
argument-hint: "--book <short-name> [--pages <n>] [--audience xprize|general] [--no-brief] [--force]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - books/{book}/seed.txt
  - books/{book}/outline.md
  - books/{book}/voice.md
  - books/{book}/chapters/*.md
  - books/{book}/treatment.md
  - books/{book}/brief.md
writes:
  - books/{book}/treatment.md
  - books/{book}/brief.md
context_mode: book
---

<purpose>
Turn a book's foundation into the two **prose** deliverables a screen
story is judged on — *before* a single frame of video exists:

  - **`books/{book}/treatment.md`** — a present-tense film treatment:
    the whole story told as a film would unfold it, scene block by
    scene block, **including the ending**. Unlike a teaser (which
    withholds), a treatment reveals everything — it's the document a
    producer or competition jury reads to understand the film. Length
    is capped by `--pages` (default 12, the Future Vision X-Prize
    limit; ~450–500 words per page → ≤ ~6000 words).

  - **`books/{book}/brief.md`** — a 2-page written brief: a one-line
    logline, a tight synopsis, the central theme, the world's
    distinctive idea, the protagonist's arc, and (for `--audience
    xprize`) an explicit "why this is a future worth building" framing.

This is the same medium-agnostic foundation the novel pipeline already
produced (world / cast / outline / canon / voice), re-expressed for the
screen. It is the cheapest, lowest-risk movie-mode deliverable —
pure prose, no generation cost — and it is **required** by the X-Prize
(3-minute trailer **+ ≤12-page treatment + 2-page brief**). Pair it
later with `/autonovel:teaser` for the trailer itself.

`--audience xprize` (default) shapes both files for the competition's
judging criteria: technology solving real problems, an *optimistic*
(non-dystopian) future, genuine stakes + a real character arc, and
visual ambition. `--audience general` drops the X-Prize framing for an
ordinary film treatment.

`--force` permits overwriting existing files (otherwise the command
refuses to clobber author-edited content).
</purpose>

<workflow>
**Read-failure policy.** `project.yaml`, `books/{book}/outline.md`, and
the foundation files are load-bearing — stop if `outline.md` is missing
(there's no story spine to adapt). Treat `books/{book}/chapters/*.md`,
`shared/canon.md`, `books/{book}/canon.md`, and `books/{book}/voice.md` as best-effort
enrichment: if a read fails, note the gap and proceed. Do NOT retry on
`file_read` errors for the best-effort inputs.

1. Parse `$ARGUMENTS`. Required: `--book <short-name>`. Optional:
   `--pages <n>` (default `12`), `--audience <xprize|general>`
   (default `xprize`), `--no-brief`, `--force`.

2. **Refusal-on-overwrite check.** For each file the run would write
   (`books/{book}/treatment.md`, and `books/{book}/brief.md` unless
   `--no-brief`), check whether it already exists with substantive
   author content. If yes and `--force` was not supplied, stop with:
   "books/{book}/<file> already has content; pass `--force` to
   overwrite or hand-edit it directly".

3. **Load the story.** Use `file_read` on:
   - `project.yaml` — genre, period/region, the book's display title.
   - `books/{book}/outline.md` — the **spine**: chapter beats, turning
     points, the planted/paid-off threads. This is the primary source
     for the scene-block structure.
   - `books/{book}/seed.txt` — the original pitch / premise.
   - `shared/world.md` — the world's distinctive idea (load-bearing for
     the X-Prize "future worth building").
   - `shared/characters.md` — the cast, their wants, their arcs.
   - `shared/canon.md` — hard facts (dates, names, rules) to keep the
     treatment consistent (best-effort).
   - `books/{book}/voice.md` — Part 1's register and tone, so the
     treatment's prose matches the story's voice (best-effort).
   - `books/{book}/chapters/*.md` — if chapters exist (an adapted
     novel like the Fugger book), skim them to ground scene detail and
     the real ending. If no chapters exist yet (a from-scratch screen
     story), work from the outline alone (best-effort).

4. **Write `books/{book}/treatment.md`.** A film treatment, present
   tense, third person, active. Structure:

   ```markdown
   # {Display Title} — Treatment

   *Logline:* [one sentence: protagonist + goal + obstacle + stakes.]

   *Genre / format:* [e.g. optimistic sci-fi feature.]  *Setting:*
   [time + place, one line.]

   ## Treatment

   [Present-tense narrative of the film, told in scene blocks. Open on
   the opening image. Move through the acts. Render turning points as
   beats the camera could see (externalised action, not interiority).
   REVEAL the ending — a treatment hides nothing. Each paragraph ≈ one
   scene/sequence.]
   ```

   Discipline:
   - **Externalise.** Convert interior states into visible behaviour
     and choices — film shows, it cannot narrate thought. (This is the
     same show-don't-tell discipline the novel pipeline enforces, run
     forward: interiority → action.)
   - **Visual ambition.** Name the images that make this cinema —
     scale, the world's signature technology, the moments worth
     watching. The X-Prize rewards visual ambition; the treatment must
     promise it.
   - **Real stakes + a real arc.** Make clear what the protagonist
     wants, what it costs, and how they change. Juries reward genuine
     character arcs over spectacle alone.
   - **(xprize) Optimism earned, not given.** Show a hopeful future
     that humanity *earns through struggle and ingenuity* — technology
     solving a real problem (climate, health, exploration). Avoid both
     dystopia and frictionless utopia.
   - Respect `--pages`: ≤ `<n> × ~500` words. Cut, don't pad.
   - No AI-tells (`ANTI-SLOP.md`); match `voice.md` Part 1 register.

5. **Write `books/{book}/brief.md`** (unless `--no-brief`). Two pages
   (~700–1000 words):

   ```markdown
   # {Display Title} — Brief

   **Logline:** [one sentence.]

   **Synopsis:** [3–5 tight paragraphs covering the whole story,
   ending included.]

   **Theme:** [the question the film asks.]

   **World / the idea:** [the distinctive premise in 2–3 sentences.]

   **Protagonist & arc:** [who they are → who they become.]

   **Why this future is worth building:** [xprize only — the optimistic
   thesis: the real problem solved, the cost paid, the hope earned.]

   **Visual ambition:** [2–3 signature images/sequences.]
   ```

6. Print a one-screen summary: which files were written, their page/word
   counts, the `--audience` mode used, and the natural next step:

   ```
   📄 Wrote books/{book}/treatment.md (film treatment, N words ≈ P pages of <pages> max).
   📄 Wrote books/{book}/brief.md (brief, N words ≈ 2 pages).

   Both are drafts — read them before submitting. The treatment reveals
   the ending (that's correct for a treatment, NOT for a teaser).

   Next: /autonovel:teaser --book {book}   (the trailer that pairs with these)
   Re-run with --force to regenerate from scratch.
   ```
</workflow>

<acceptance>
- `books/{book}/treatment.md` exists, opens with a `# ... Treatment`
  heading, contains a `*Logline:*` line, is present-tense narrative,
  and is ≤ `--pages × ~500` words.
- Unless `--no-brief`, `books/{book}/brief.md` exists with a
  `**Logline:**` and a `**Synopsis:**` section.
- With `--audience xprize` (default), both files include an explicit
  "future worth building" / optimism-earned framing and name the real
  problem the story's technology addresses.
- The treatment reveals the ending; the (separate) teaser does not.
- Refusal on overwrite without `--force` is the default; the command
  never silently destroys author-edited content.
- Works from `outline.md` alone when no `chapters/` exist (from-scratch
  screen story) and enriches from `chapters/*.md` when they do (adapted
  novel).
</acceptance>
