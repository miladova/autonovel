---
name: autonovel:compare-models
description: Draft one chapter with two models in parallel, evaluate head-to-head, report which one wrote better prose for this book.
argument-hint: "--chapter <N> [--book <name>] [--models <a>,<b>]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - task
reads:
  - project.yaml
  - shared/world.md
  - shared/characters.md
  - shared/canon.md
  - books/{book}/canon.md
  - shared/events.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/chapters/ch_{prev}.md
  - books/{book}/chapters/ch_*.summary.md
writes:
  - books/{book}/eval_logs/compare_ch{chapter:02d}_<model_a>_vs_<model_b>.md
  - books/{book}/eval_logs/compare_ch{chapter:02d}_<model_a>.draft.md
  - books/{book}/eval_logs/compare_ch{chapter:02d}_<model_b>.draft.md
context_mode: book
---

<purpose>
A/B-compare two models on the same chapter draft. Useful when:

  - Anthropic / OpenAI / Google ship a new model and you want to see
    if it's worth switching for *this* book's voice.
  - You're not sure whether Opus's higher cost is justified vs.
    Sonnet for this genre / chapter type.
  - You're calibrating expectations for the writer-vs-judge tier
    split (Bells used Sonnet to write, Opus to judge).

This command does NOT touch `books/{book}/chapters/ch_{chapter}.md` —
it writes both candidate drafts to `eval_logs/` so the live chapter
file is preserved. After reading the verdict, the user can copy the
winner into place manually.

V1 is single-provider: it compares two Claude models within the
runtime currently in use. Cross-provider comparison (Claude vs GPT
vs Gemini) is in `FUTURE-TODOS.md` — that's a different shape because
it would need to spawn the other providers' runtimes, which only the
adapter layer can mediate.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. Required: `--chapter <N>`. Optional:
   `--book` (defaults via `_begin`), `--models <a>,<b>` (defaults
   to `claude-opus-4-7,claude-sonnet-4-6`). Missing `--chapter` →
   stop with usage hint.

2. Use `file_read` on `project.yaml` for the book entry, `pov`, and
   `defaults.chapter_target_words`.

3. Use `file_read` on the standard drafting context:
   `shared/world.md`, `shared/characters.md`, `shared/canon.md`,
   `books/{book}/canon.md`, `shared/events.md`, `books/{book}/voice.md`,
   `books/{book}/outline.md`. Pull the chapter `{chapter}`'s entry
   from the outline (story_time, events, beats). If the chapter is
   not in the outline, stop with a one-line gap message.

4. Use `file_read` on `books/{book}/chapters/ch_{prev}.md` (last
   ~1000 words for continuity) and on every existing
   `books/{book}/chapters/ch_*.summary.md` for chapters 1 through
   `{prev}`. This is the same context-bundle a regular
   `/autonovel:draft` builds.

5. **Spawn two parallel `task` invocations** to draft the chapter,
   one per model. Each `task` invocation specifies `model: <name>`
   so the subagent runs at the requested model regardless of the
   parent session's model.

   - Task A (`{model_a}`): write a draft of chapter `{chapter}`
     respecting voice, world, canon, outline beats, and the
     continuity context above. Save to
     `books/{book}/eval_logs/compare_ch{chapter:02d}_<model_a>.draft.md`.
   - Task B (`{model_b}`): same prompt, same context, save to
     `books/{book}/eval_logs/compare_ch{chapter:02d}_<model_b>.draft.md`.

   Both tasks return their draft text. Wait for both before
   proceeding. Budget: each draft targets
   `defaults.chapter_target_words` words.

6. **Spawn a third `task` to judge head-to-head.** This evaluator
   should run at the heaviest tier available (default
   `claude-opus-4-7`, regardless of the candidate models). Hand it:

   - The chapter outline entry.
   - The voice fingerprint.
   - Both drafts, anonymized as Draft A and Draft B (so the judge
     does not know which model wrote which).

   Ask the judge to score each draft on the standard chapter
   dimensions (`voice_adherence`, `beat_coverage`, `character_voice`,
   `prose_quality`, `engagement`, `internal_consistency`), then
   declare a winner with a one-paragraph rationale that names
   specific passages from each draft.

7. Use `file_write` to save the verdict to
   `books/{book}/eval_logs/compare_ch{chapter:02d}_<model_a>_vs_<model_b>.md`.
   Layout:

   ```
   # Model comparison — chapter {chapter}

   - Date: <UTC>
   - Book: {book}
   - Chapter: {chapter}
   - Model A: <model_a>
   - Model B: <model_b>
   - Judge: <judge_model>

   ## Scores

   | Dimension | Draft A | Draft B |
   |---|---|---|
   ...

   ## Verdict

   Winner: <A | B | tie> — <model name>

   <one-paragraph rationale citing specific lines>

   ## Drafts

   See:
   - books/{book}/eval_logs/compare_ch{chapter:02d}_<model_a>.draft.md
   - books/{book}/eval_logs/compare_ch{chapter:02d}_<model_b>.draft.md
   ```

8. Print a one-screen summary in the postamble footer: winner +
   rationale's first sentence + the three eval_logs/ paths so the
   user can open them. The user decides whether to promote a draft
   into `chapters/` themselves.
</workflow>

<acceptance>
- The verdict file at
  `books/{book}/eval_logs/compare_ch{chapter:02d}_*_vs_*.md`
  exists, names both models, contains a per-dimension score table
  for each draft, and declares one of "Winner: A", "Winner: B",
  or "Winner: tie".
- Both candidate draft files exist and are >= 1500 words each.
- `books/{book}/chapters/ch_{chapter}.md` is unchanged (this command
  is non-destructive).
</acceptance>
