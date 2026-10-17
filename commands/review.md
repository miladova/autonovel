---
name: autonovel:review
description: Deep dual-persona manuscript review — literary critic plus professor of fiction.
argument-hint: "--book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - books/{book}/outline.md
  - books/{book}/chapters/*.md
  - books/{book}/edit_logs/structure_review.json
writes:
  - books/{book}/edit_logs/review.json
  - books/{book}/edit_logs/review.md
context_mode: book
---

<purpose>
Send the full manuscript to a heavy-tier model for a two-persona review:
first a literary critic (newspaper book review style), then a professor
of fiction giving specific, actionable craft suggestions. This is
phase 3b of the revision loop — the signal that the book has stopped
improving in measurable ways. Successor to the deleted `review.py`.

This review is prose-weighted by design: an editorial letter. It is not
the book-level structure judge. `/autonovel:structure-review` is, and
the stop-revising verdict below is gated on it, because on *kingmaker*
this review held at 4★ for ten passes, praised "the spine" (a recurring
ledger image), typed none of its eleven items `structural`, and hedged
the one structural observation it made ("Individually each scene is
fine, and the strain is a cost of ambition") into a qualified item that
counted toward stopping — while the author read the book as "a bunch of
short anecdotes, not a continuing story building to a climax."

Stop revising only when BOTH hold:

  1. **Book-level gate.** `autonovel mechanical structure-validate
     books/{book}` reports `gate.passes: true`: a valid
     `books/{book}/edit_logs/structure_review.json`, newer than every
     chapter, with `structure_score` ≥ 4 and no chapter flagged
     removable. Missing or stale → not stop; the reason says "run
     /autonovel:structure-review first".
  2. **Prose-level** (the Bells rule), any of:
     - ★★★★½ or better AND no major unqualified items, OR
     - most flagged items are qualified hedges ("individually fine",
       "largely successful", "cost of ambition"), OR
     - fewer than 3 total items surface.
     Items typed `structural` are never qualified, and any unqualified
     `structural` item of severity `major` or `moderate` blocks this
     half on its own.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. Missing is a usage
   error — print a reminder and stop.

2. Use `file_read` on `project.yaml` to get the book title (fall back to
   the book's `seed.txt` first-line title or `books/{book}/outline.md`
   first heading if the config has no explicit title).

3. Use `file_read` to glob `books/{book}/chapters/*.md` in order.
   Concatenate with `\n\n---\n\n` separators into one manuscript
   payload.

4. Run the dual-persona review as a single LLM call with a combined
   prompt: "Read this novel. Review it first as a literary critic
   (like a newspaper book review), then as a professor of fiction with
   specific, actionable craft suggestions. Be fair but honest; you
   don't have to find defects." Use a heavy-tier model (Opus-class);
   Claude Code's runtime picks this via `model_tier: heavy`.

   Add these instructions to the professor stage, verbatim in spirit:
   - "Strong prose is not evidence of structure. If you say the book
     has a spine, name it as a chain of causes — one sentence per act
     saying what in the previous act forces this one. A recurring
     image, object, motif or narrator promise line is not a spine."
   - "Any finding about chapter order, causation between chapters,
     stakes across acts, a chapter that could be cut, a stretch that
     reads as separate episodes, or a climax that closes threads one by
     one is typed `structural`. State it as a defect with chapter
     numbers and a fix. Do not frame it as a cost of ambition, as
     individually fine, or as largely successful."

5. Parse the review. Extract:
   - star rating if present (`★★★★½` or similar)
   - professor-stage items as `[{number, title, severity, type,
     qualified, suggestion, full_text}]`
   - severity: `major` | `moderate` | `minor` (keyword match)
   - type: `compression` | `addition` | `mechanical` | `structural` | `revision`
     — an item about chapter order, between-chapter causation, act
     stakes, a removable chapter or an episodic stretch is `structural`
     whatever the professor called it
   - qualified: true if the item hedges ("individually fine",
     "largely successful", "costs of ambition", "thematically coherent")
     — **except** `structural` items, which are always `qualified:
     false` (a hedged structural defect is still a structural defect)

6. Compute the stop-revising verdict per <purpose> above:
   - Use `bash` to run `autonovel mechanical structure-validate
     books/{book}` and parse its JSON `gate` object (`passes`,
     `structure_score`, `removable_chapters`, `stale`, `reasons`). Exit
     code 2 means no `structure_review.json` yet. Record the object as
     `structure_gate` in the review JSON.
   - `stop_revising` is true only when `structure_gate.passes` is true
     AND the prose-level half holds.
   - `stop_reason` names whichever half blocked. When the gate is
     missing or stale it reads "book-level gate: run
     /autonovel:structure-review --book {book} first"; when it fails it
     names the structure score and the removable chapters.

7. Use `file_write` twice:
   - `books/{book}/edit_logs/review.json` — the parsed, structured review
   - `books/{book}/edit_logs/review.md` — the raw human-readable review text

8. Print the star rating, item counts (total, major, qualified,
   structural), the book-level gate (PASS / BLOCK and its reasons), and
   the stop verdict with its reason. When the gate is missing or
   stale, print `/autonovel:structure-review --book {book}` as the next
   command.
</workflow>

<acceptance>
- Both `books/{book}/edit_logs/review.json` and
  `books/{book}/edit_logs/review.md` exist.
- The JSON contains `stars` (number or null), `total_items`,
  `major_items`, `qualified_items`, `structural_items`, a
  `structure_gate` object (`passes`, `structure_score`,
  `removable_chapters`, `stale`, `reasons`), and a top-level
  `stop_revising` boolean plus `stop_reason` string.
- `stop_revising` is false whenever `structure_gate.passes` is false.
- No item with `type: structural` has `qualified: true`.
- The Markdown file is at least 500 words of review prose.
</acceptance>
