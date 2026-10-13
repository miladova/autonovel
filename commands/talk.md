---
name: autonovel:talk
description: Conversational query+suggest layer over the finished prose. Q+A explains the book; Suggest-and-stage queues edits for the next revise pass.
argument-hint: "--book <short-name> \"<question or suggestion>\" [--target <chapter>]"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - bash
reads:
  - project.yaml
  - shared/canon.md
  - books/{book}/canon.md
  - shared/characters.md
  - shared/world.md
  - books/{book}/voice.md
  - books/{book}/outline.md
  - books/{book}/entities.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/briefs/conversation.md
writes:
  - books/{book}/briefs/conversation.md
context_mode: book
---

<purpose>
Convert ad-hoc author questions and editing requests into either
*answers* (read-only Q+A citing chapter and line) or *staged edits*
(structured entries the next `/autonovel:revise` pass folds into
its brief). This is the surface the author lives in once drafting
is done: instead of opening individual chapters and hand-editing,
you ask the book questions and queue improvements.

Three modes the command must distinguish from the user's prompt:

1. **Q+A** — the user wants an explanation. *"Explain why Jakob
   decided to open the book of accounts."* The command answers,
   citing the chapter, the proximate motive line, the prior setup,
   the consequence. No file is written beyond appending the turn
   to `briefs/conversation.md`.

2. **Suggest-and-stage** — the user proposes an edit. *"Add some
   more details — the book of accounts looked like it had been
   recently opened and hurriedly returned to its place as it was
   out of alignment with the other books."* The command resolves
   the target (chapter / scene), writes a structured suggestion
   block to `briefs/conversation.md` with `Status: queued`, and
   tells the user when it'll be applied (next
   `/autonovel:revise <N>` reads queued entries with
   `Target: chapter N`).

3. **Mechanical+suggest** — the user asks a mechanical question
   that drives a structural cut/add. *"Check how many times Jakob
   added an entry to his cipher diary, and how many times he
   referred to each entry. Reduce entries that aren't referred
   to later."* The command first calls
   `autonovel mechanical entity-track` to surface the per-chapter
   counts, then performs the semantic added-vs-referred pairing
   itself, then writes a structured cut-list to
   `briefs/conversation.md`.

The conversation log is **append-only**. Each invocation reads
the existing log, processes one new turn, and appends. The author
can hand-edit the log between turns (correcting a misread target,
escalating a queued suggestion, marking something as
`Status: rejected`); the command treats whatever is on disk as
authoritative.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` and a positional
   string (the question or suggestion) are required. Optional
   `--target <chapter>` overrides the LLM's target inference for
   suggest mode.

2. **Read context.** Use `file_read` on:
   - `project.yaml` (book entry, defaults).
   - `shared/canon.md`, `books/{book}/canon.md` (this book's own
     established facts) and `shared/characters.md` (cast registry —
     resolves who `Jakob`, `Niccolò`, etc. actually are).
   - `shared/world.md` for setting cues when the user's question
     touches geography / institutions / period.
   - `books/{book}/voice.md` so suggested edits respect the book's
     voice rules — a cut-list that violates Part 3's custom rubric
     would just be reverted at revise time.
   - `books/{book}/outline.md` to ground "where does X happen?"
     answers in the book's plan rather than guessing from prose
     alone.
   - `books/{book}/entities.md` if it exists (the per-book entity
     config the entity-track helper consumes).
   - The relevant per-chapter `ch_NN.summary.md` files (or all of
     them if the user's question is whole-book).
   - `books/{book}/briefs/conversation.md` (history of past turns
     — the LLM's memory across invocations).

3. **Classify the turn.** From the user's prompt, decide which
   mode applies:
   - Words like *"explain"*, *"why did"*, *"how does"*, *"where
     does"* → **Q+A**.
   - Words like *"add"*, *"change"*, *"cut"*, *"rewrite"*,
     *"make it so"* → **Suggest-and-stage**.
   - Words like *"how many times"*, *"check whether"*, *"count"*,
     *"track"* → **Mechanical+suggest**. Run
     `autonovel mechanical entity-track books/{book}` (or
     `mechanical motifs books/{book}` if the query is about
     symbolic images) via the `bash` tool; read its JSON output;
     fold the counts into your reasoning. If the user's prompt
     names a specific entity (e.g. "Jakob's cipher diary") that
     isn't in `entities.md`, write a one-line bullet
     `- diary: cipher diary, diary` to `entities.md` first
     (creating it if missing) so future turns can re-use it.

4. **Resolve the target chapter.** For suggest modes, infer the
   chapter from prose-evidence:
     a. If `--target N` is set, use it.
     b. Otherwise scan summaries / chapter headers for the
        scene the user named (e.g. "the book of accounts" → find
        the chapter where the book of accounts appears). Pick
        the chapter with the strongest prose match (most hits
        on the named object / character / location).
     c. If unresolved, append the suggestion with
        `Target: unresolved` and surface a one-line follow-up to
        the user asking which chapter.

5. **Render the answer or suggestion.** For Q+A, produce a
   concise answer (3-8 sentences) citing chapter + line(s) where
   the supporting evidence lives. For suggest modes, produce
   the user-facing acknowledgement *and* the structured log
   entry. Cut-lists for mechanical+suggest must name specific
   chapters and entries (no vague "trim the diary entries").

6. **Append to the conversation log.** Use `file_write` (read-
   modify-write) on `books/{book}/briefs/conversation.md` to
   append a single new turn block in this exact shape:

   ```markdown
   ## <ISO date> — turn <N> — <mode>
   **Question / suggestion:** <user's prompt verbatim>
   **Mode:** Q+A | suggest | mechanical+suggest
   **Target:** chapter <N> | unresolved | series-wide
   **Answer / suggestion:** <the agent's answer or the structured
   change request>
   **Status:** answered | queued | applied | rejected
   ```

   For Q+A turns, `Status: answered` (no edit pending). For
   suggest modes, `Status: queued` until `/autonovel:revise N`
   marks it `applied` (or the author marks it `rejected`).

7. **Print the user-facing reply** to stdout. Print the same
   answer + (for suggest modes) a one-line trailing note like
   `→ queued under /briefs/conversation.md as turn 7. Run
   /autonovel:revise <N> --book {book} to apply.`

8. **Idempotency contract.** Re-running an identical question
   appends a new turn. Re-running an identical suggestion
   appends a new turn (the LLM cannot reliably detect "this is
   the same edit as turn 4"); rely on the author to mark
   superseded turns `Status: rejected` by hand-edit if needed.
</workflow>

<acceptance>
- A new turn block is appended to
  `books/{book}/briefs/conversation.md` on every invocation.
- Q+A turns write `Status: answered`; suggest turns write
  `Status: queued`.
- Mechanical+suggest turns include the per-chapter table the
  helper produced (in the **Answer / suggestion** body) so the
  author can audit the count before approving the cut-list.
- The new turn block has the six labeled fields above. No
  prior turn is rewritten.
- The user-facing reply on stdout matches the answer in the
  log.
- For suggest modes, the **Target:** field is one of `chapter N`,
  `series-wide`, or `unresolved` — never blank.
</acceptance>
