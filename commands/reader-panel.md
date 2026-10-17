---
name: autonovel:reader-panel
description: Four-persona reader panel review of a book's complete arc.
argument-hint: "--book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/*.md
  - books/{book}/chapters/ch_*.summary.md
writes:
  - books/{book}/edit_logs/reader_panel.json
context_mode: book
---

<purpose>
Four distinct reader personas review the whole book and answer the same
fourteen questions: ten about the reading (momentum, earned ending,
thinnest character, …) and four about the book as one story (what it is
about and what question it answers, where it fell into separate
episodes, which whole chapter could go, where it pulled forward and
where it merely informed). Where they disagree, that's where the
editorial decisions live. Use this after a full revision cycle, when
you need signal on structural problems that single-chapter evaluation
can't see.

The four book-level questions exist because a panel can say it would
buy a book without ever being asked whether it read as one story; a
book can please all four personas chapter by chapter and still read as
a string of anecdotes. The panel is a reader
signal; the scored structural judgement is `/autonovel:structure-review`.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Expect `--book <short-name>`. Missing is a
   usage error — print a one-line reminder and stop.

2. Use `file_read` on `project.yaml` and `books/{book}/outline.md` for
   scaffolding. Also `file_read` `books/{book}/voice.md` and parse a
   `## Part 3 — Custom rubric` (or `## Custom rubric`) section the
   same way `/autonovel:evaluate` does — strip the HTML comment
   placeholder, treat top-level bullets as the book-specific
   criteria. Empty or absent → skip; many books have no custom
   rubric and that's fine.

3. Use `file_read` to glob `books/{book}/chapters/*.md`. Build an arc
   summary inline: for each chapter, emit its number, word count, the
   first ~500 chars (opening), the last ~500 chars (closing), its
   outline beats, and the **Plot** and **Threads opened / closed**
   lines of its continuity summary
   (`books/{book}/chapters/ch_NN.summary.md`, best-effort — skip a
   missing one). The openings and closings alone cannot show whether
   chapter N+1 happens because of chapter N; the plot lines can. This
   is the material the four personas share; when the runtime's
   context allows, give each persona the full prose as well (the
   book-level questions are answered best from it); otherwise the arc
   summary is enough and keeps the context affordable.

4. Run four sequential LLM calls, each with a distinct system prompt:

   - **The Editor** — senior fiction editor, 200+ novels. Prose texture,
     subtext, sentence-level craft, over-explaining, borrowed vs earned
     metaphor. Not cruel but precise.
   - **The Genre Reader** — 50+ novels a year in this genre. Pacing,
     mystery, worldbuilding payoff, wanting-to-turn-the-page. Bored by
     beautiful prose that doesn't go anywhere.
   - **The Writer** — published author. Structure, beat placement,
     foreshadowing payoff, the gap between what a novel attempts and
     achieves. Highest compliment: "I forgot I was reading." Worst
     verdict: "I can see the outline."
   - **The First Reader** — thoughtful general reader. No craft
     terminology. Emotional honesty: "I didn't care about this part,"
     "I had to put the book down after this scene."

5. Each persona answers the same fourteen questions, JSON-formatted.
   The ten reading questions: `momentum_loss`, `earned_ending`,
   `cut_candidate`, `missing_scene`, `thinnest_character`,
   `best_scene`, `worst_scene`, `would_recommend`, `haunts_you`,
   `next_book`. Answers name specific chapter numbers and quote
   passages when possible. For `earned_ending`: an object or a
   narrator promise line planted early and paid at the end is a
   callback, not an earned ending — earned means the ending's
   decision is caused by what the book did before it.

   The four book-level questions, answered in the persona's own voice
   (the First Reader without craft terms):
   - `book_in_one_sentence` — say in one sentence what the book is
     about AND the one question it asks and answers. If you cannot
     name a single question, say so; that is an answer.
   - `felt_like_episodes` — where did it feel like separate episodes
     rather than one continuing story? Name the chapter ranges and
     what reset at each seam (a new problem, a new opponent, a time
     jump that started over). "Nowhere" is allowed only with the
     reason it held together.
   - `chapter_to_cut` — which WHOLE chapter could be cut with nothing
     later breaking? Name it and say what, if anything, would have to
     move to a neighbour; or "none", naming the later chapter that
     each candidate is needed for. (Distinct from `cut_candidate`,
     which may be a passage.)
   - `pulled_vs_informed` — list the chapters where you felt pulled
     forward (you had to know what happened next because of what had
     just happened) and the chapters where you were merely informed
     (interesting, but nothing made you turn the page).

   **When a custom rubric was parsed in step 2**, each persona also
   answers one extra free-text field per criterion: `custom_rubric:
   {criterion_text: persona_finding}`. The persona evaluates the
   whole book against the rule and names the chapters that violate
   it. Different personas often catch different violations — that's
   the value of running it through the panel rather than only
   `/autonovel:evaluate`.

6. After all four have responded, compute disagreements. For each of
   `momentum_loss`, `cut_candidate`, `thinnest_character`,
   `worst_scene`, `felt_like_episodes`, `chapter_to_cut`, extract any
   `Ch N` references. A chapter flagged by some personas but not
   others is a disagreement — record
   `{question, chapter, flagged_by, not_flagged}`.

   Then build the `book_level` block from the four book-level answers:
   - `one_sentence_agreement` — `same` when the four
     `book_in_one_sentence` answers name the same question, `different`
     when they name different questions, `none` when two or more could
     not name one. Four readers who each say the book is about
     something different is the episodic signal.
   - `episode_votes` — `{chapter: count}`, the number of personas who
     placed the chapter in an episodic stretch.
   - `cut_votes` — `{chapter: count}`, the number of personas who
     named the chapter in `chapter_to_cut`.
   - `informed_not_pulled` — chapters that two or more personas listed
     as merely informed.
   A chapter with two or more `cut_votes` is worth a
   `/autonovel:structure-review` removability check before the next
   revision pass.

7. Use `file_write` to save the full panel to
   `books/{book}/edit_logs/reader_panel.json`:
   ```json
   {
     "readers": {"editor": {...}, "genre_reader": {...}, ...},
     "disagreements": [{"question": "...", "chapter": N,
                        "flagged_by": [...], "not_flagged": [...]}],
     "book_level": {"one_sentence_agreement": "same|different|none",
                    "episode_votes": {"15": 3}, "cut_votes": {"16": 2},
                    "informed_not_pulled": [15, 16, 20]},
     "custom_rubric": [{"criterion": "...",
                        "violations_per_reader": {"editor": ["Ch 3", "Ch 7"], ...}}],
     "timestamp": "..."
   }
   ```
   Omit the `custom_rubric` key when no rubric was parsed in step 2.

8. Print a one-screen summary: per-persona one-line takes, the four
   `book_in_one_sentence` answers side by side, the `book_level`
   votes, plus the disagreements section (the one the user actually
   needs to act on). When `one_sentence_agreement` is not `same`, or
   any chapter has two or more `cut_votes`, end with
   `/autonovel:structure-review --book {book}` as the next command.
</workflow>

<acceptance>
- `books/{book}/edit_logs/reader_panel.json` exists.
- Contains a `readers` object with exactly four keys:
  `editor`, `genre_reader`, `writer`, `first_reader`.
- Each reader has answers to all fourteen questions (no null values),
  including `book_in_one_sentence`, `felt_like_episodes`,
  `chapter_to_cut` and `pulled_vs_informed`.
- `book_level` holds `one_sentence_agreement`, `episode_votes`,
  `cut_votes` and `informed_not_pulled`.
- `disagreements` is a list (may be empty if all four agreed).
- When voice.md Part 3 contains at least one bullet criterion,
  `custom_rubric` is a list with one entry per criterion; each
  entry's `violations_per_reader` is a dict keyed by reader name
  (chapters they flagged for that rule, possibly empty).
</acceptance>
