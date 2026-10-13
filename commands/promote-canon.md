---
name: autonovel:promote-canon
description: Promote pending canon entries from every book's pending_canon.md into canon — chapter-derived facts into that book's canon.md, research-cited facts into shared/canon.md.
argument-hint: "[--book <short-name>] [--dry-run] [--scope auto|book|series]"
model_tier: standard
allowed-tools:
  - file_read
  - file_write
reads:
  - project.yaml
  - shared/canon.md
  - books/*/canon.md
  - shared/world.md
  - shared/characters.md
  - books/*/pending_canon.md
writes:
  - books/*/canon.md
  - shared/canon.md
  - books/*/pending_canon.md
context_mode: series
---

<purpose>
Move candidate facts out of per-book scratchpads
(`books/{book}/pending_canon.md`) and into canon. **Canon is
book-scoped (2026-10-12):** a chapter-derived fact lands in the book's
own `books/{book}/canon.md` — it binds that book only, so a sibling book
(a different POV, a later period, or a *rewrite of the same story*) is
free to decide it differently. Only research-cited facts
(`[research:<slug>]`, a primary source behind them) land in the
series-wide `shared/canon.md`. `--scope book|series` forces one target.

This is the one command that writes either canon file —
`/autonovel:revise`, `/autonovel:draft`, and every other chapter
command are forbidden from editing them directly (§19), because two books
drafting chapters in parallel both appending to the same file is a
cross-book race condition.

Single-threading is enforced by `.autonovel/in-progress.lock` (acquired
by the preamble); inside the critical section the command:
1. reads every pending file,
2. de-duplicates against existing canon (`shared/canon.md` + the book's
   OWN `books/{book}/canon.md` + world + characters — never another
   book's canon),
3. rejects contradictions,
4. appends the survivors to `books/{book}/canon.md` (chapter-derived)
   or `shared/canon.md` (research-cited) with provenance (which book /
   chapter proposed them),
5. empties every pending file it consumed.

The preamble's checkpoint captures both canon files and the pending
files, so `autonovel rollback` undoes the whole promotion.
</purpose>

<workflow>
> **Implementation note (2026-04-26):** the entire de-dup /
> contradiction-detection / supersedure / conflict-block logic is
> implemented in `src/autonovel/promote_canon.py` and exposed as
> the hidden CLI subcommand `autonovel _promote-canon`. This
> command's body simply invokes the helper (with the lock acquired
> by the standard preamble); the prose below describes the
> behaviour the helper implements, NOT a separate inline workflow
> the LLM should reproduce. The same helper is invoked by sweep
> sub-agents with `--no-lock` (see `revision-pass.md` step 3f and
> `draft-pass.md` step 5) so there's exactly one source of truth
> for the file-operation semantics.

1. Parse `$ARGUMENTS`. `--book <short-name>` restricts the sweep to
   one book's pending file. `--dry-run` prints what would be
   promoted without writing. `--scope auto|book|series` (default
   `auto`) routes survivors: auto = research-cited → `shared/canon.md`,
   everything else → `books/{book}/canon.md`. No positional arguments.

2. **Invoke the helper.** Use the `Bash` tool to run:

   ```
   autonovel _promote-canon [--book <name>] [--dry-run] [--scope auto|book|series] --format json
   ```

   The CLI does steps 3–8 inline (parse pending, classify against
   shared canon / the book's own canon / world / characters, emit
   `## Promoted` and `## Superseded` blocks in the target canon file,
   rewrite `pending_canon.md` with
   either the structured `# Conflicts` block or `no new facts`).
   The JSON report carries `promoted_to_book` / `promoted_to_shared`
   per book.
   Parse the JSON output for the per-book counts to feed step 9's
   summary. Steps 3–8 below remain authoritative descriptions of
   the helper's behaviour for review purposes — they are NOT a
   separate inline workflow.

   When `--book` is omitted, the helper iterates every book in
   `project.yaml`. When `--dry-run` is passed, no files are
   modified — the JSON report names what would have happened.

   The slash-command's preamble already acquired the in-progress
   lock; the helper runs without `--no-lock`. Sub-agents in
   sweeps invoke the same helper with `--no-lock` (see
   `revision-pass.md` step 3f and `draft-pass.md` step 5) which
   bypasses the lock check — that's the safe in-sweep entry point
   for the same logic.

3. For each selected book, use `file_read` on
   `books/{book}/pending_canon.md`. Parse it as a plain bullet list
   (each non-empty line starting with `-` is one candidate entry).
   Lines that read `no new facts` (case-insensitive) are skipped —
   they are the `revise` command's placeholder for "I wrote nothing
   new" and carry no payload.

4. Use `file_read` on `shared/canon.md`, the book's own
   `books/{book}/canon.md`, `shared/world.md`, and
   `shared/characters.md`. The existing canon is the baseline for
   de-duplication and contradiction detection (another book's
   `canon.md` is NOT consulted — a rewrite may diverge from the
   original freely):
   - **Duplicate**: an entry whose substantive content is already
     stated (possibly in different words) in either canon file.
     Discard silently; record it under the per-book discard list
     for the summary.
   - **Contradiction**: an entry that contradicts either canon file,
     `shared/world.md`, or `shared/characters.md`. Default-discard
     and record under the per-book conflict list — but with one
     exception below. "Contradicts" means the two lines describe the
     *same fact* and disagree on a year, a number or a negation. The
     helper judges "same fact" by the `[Key]` headline first (same
     key = same fact; different keys = different facts unless the
     wording overlaps almost completely) and, for unkeyed prose,
     by word overlap with the series' ubiquitous proper nouns
     discounted. Wrapped paragraphs are compared whole. Two facts
     that merely share "Fugger" and "Venice" and happen to carry
     different years are *not* a contradiction (2026-10-13). **Capture which of the three files holds the
     contradicting line** along with the line itself; both fields
     are required by step 8's conflict-block output so the user knows
     which file to edit when resolving.

     **Exception — research-tagged entries win contradictions.** A
     pending entry carrying a `[research:<slug>]` tag was written
     by `/autonovel:research --from-seed` and is backed by a cited
     primary source (the `[shortname]` next to it resolves in
     `shared/sources.bib`). When such an entry contradicts existing
     canon, prefer the research entry: promote it (to
     `shared/canon.md`), AND additionally
     emit a `## Superseded <UTC-date>` block in the canon file that
     held the prior line
     listing the prior canonical line and a one-sentence rationale
     ("research note `<slug>` cites [<shortname>] for <new value>;
     prior value was <old value>"). The user reviewing
     `shared/canon.md` then sees both the new fact and the old one
     with a clear paper trail. This is what makes
     `/autonovel:research --from-seed` → `/autonovel:promote-canon`
     a fully automatic update path: research's citations beat the
     LLM's general-knowledge guesses, and the supersedure is
     visible.
   - **Survivor**: neither duplicate nor contradiction. Promote.

5. For each surviving entry, rewrite it into the canonical form:

   ```
   - <fact> (from {book} ch_{chapter:02d})
   ```

   For research-tagged entries, use:

   ```
   - <fact> [shortname] (from research note <slug>)
   ```

   so the citation makes it into the canonical entry. The
   `(from …)` provenance lets future audits trace every canon
   fact back to the chapter or research note that established it.
   If the pending entry already carries a provenance tail, keep it
   verbatim.

6. If `--dry-run`, print a per-book report and stop — do NOT write
   anything. Format:

   ```
   book: {book}
     promoted: N
     duplicates: M
     conflicts:
       - <entry> — contradicts: <canon line>
   ```

7. Otherwise, use `file_write` to append the survivors to their
   target — `books/{book}/canon.md` for chapter-derived entries (the
   file is created with a `# Book canon` header on first use),
   `shared/canon.md` for research-cited ones. Append under a dated
   heading: `## Promoted <UTC-date>` (one heading per invocation per
   file). Keep the existing body of each file verbatim; do not
   rewrite it.

8. Use `file_write` to rewrite each consumed
   `books/{book}/pending_canon.md`. After a successful promotion the
   file contains either:

   **(a) Conflicts to resolve.** When at least one entry was rejected
   as a contradiction, write the file in this exact self-documenting
   format. The HTML-comment block at the top is mandatory — it is
   the user's instruction sheet for *how* to act on each conflict,
   and the previous "just dump the bullet lines" format was
   reported (2026-04-26) as making resolution unclear:

   ````markdown
   # Conflicts — resolve before next promote-canon

   <!--
   HOW TO RESOLVE A CONFLICT
   =========================

   Each `## Conflict N` block below names a pending candidate that
   couldn't be promoted because it contradicts something in
   shared/canon.md, shared/world.md, or shared/characters.md. For
   each conflict, pick ONE of the three resolutions and act:

     (A) ACCEPT the new fact (replace the existing one)
         1. Open the file named in `Existing canon (in: ...)`.
         2. Replace the old line (quoted under `Existing canon`)
            with the new line (quoted under `New candidate`). Keep
            the canonical bullet shape: `- <fact> (from <source>)`.
         3. Delete the entire `## Conflict N` block from THIS file.
         4. Re-run /autonovel:promote-canon. The conflict is gone.

     (B) REJECT the new fact (the existing one stays)
         1. Delete the entire `## Conflict N` block from THIS file.
         2. (Optional but recommended) fix the chapter that
            re-introduced the wrong fact, so it doesn't come back
            on the next draft / revise. The chapter is named under
            `Source`. Run:
              /autonovel:brief <N> --book <book>
              /autonovel:revise <N> --book <book>

     (C) BOTH ARE WRONG
         1. Edit the file named in `Existing canon (in: ...)` to
            the correct value.
         2. Delete the entire `## Conflict N` block from THIS file.
         3. Re-run /autonovel:promote-canon to land any newly
            consistent pending entries.

   After your edits, re-run /autonovel:promote-canon. Resolved
   conflicts disappear; anything still contradictory is re-emitted
   on the next run with the same instructions.
   -->

   ## Conflict 1
   - **New candidate:** `- <pending entry as it would have been promoted>`
   - **Existing canon (in: <relative file path>):** `- <existing line, verbatim>`
   - **Why they conflict:** <one sentence — what specifically disagrees>
   - **Source:** (from <book> ch_<NN>) — *or* — (from research note <slug>)

   ## Conflict 2
   ...
   ````

   Each conflict gets its own `## Conflict N` block. Number the
   blocks 1..K in the order conflicts were detected (stable across
   re-runs so the user editing N=3 doesn't have it renumber under
   them). The `Existing canon (in: ...)` field is required — name
   the actual file path that holds the contradicting line, NOT
   just "canon" — because conflicts can be against `shared/canon.md`,
   `shared/world.md`, or `shared/characters.md` and the user
   needs to know which file to edit.

   **(b) No conflicts.** When every pending entry was either
   promoted or dropped as duplicate, write a single line:

   ```
   no new facts
   ```

   That single-line form is what `revise` / `draft` / `revision-pass`
   then append fresh candidates to on subsequent runs. Do NOT leave
   the file empty (some tooling treats an empty file as
   "uninitialised" rather than "settled").

9. **Print the postamble summary AND specific next-step guidance.**
   The user sees this output the moment promote-canon finishes;
   they should never have to read docs to know what to do next.
   Format:

   ```
   promoted: <N>
   duplicates: <M>
   conflicts:  <K>
   supersedures: <S>   (research-tagged entries that replaced existing canon)

   Next:
     <one or more of the lines below, depending on what happened>
   ```

   Pick the next-step lines from this decision tree. **Print every
   line that applies; do not collapse them into a single
   recommendation.** Multiple categories can apply in one run.

   **(a) Supersedures landed (S > 0).** For each `## Superseded`
   block written to `shared/canon.md` this run, identify the
   chapter that introduced the OLD canon line by parsing its
   provenance tail (`(from <book> ch_<NN>)`). That chapter likely
   still references the now-wrong value in its prose. **Always
   recommend `/autonovel:revision-pass`** — it runs the whole
   per-chapter loop (anachronism → brief → revise → evaluate →
   promote-canon) in one command, which is what the user wants
   regardless of whether 1 chapter or 10 are affected. The 3-step
   atomic sequence (check-anachronism → brief → revise) is for
   surgical work where the user wants to inspect each artifact
   between steps; almost no post-promote-canon revision is that
   surgical.

   Single chapter:

   ```
     - Chapter <NN> (<book>) introduced the prior value of
       "<short description>". Update its prose:
           /autonovel:revision-pass --chapters <NN> --book <book>
   ```

   Multiple chapters:

   ```
     - <S> chapters introduced now-superseded values:
       <list of "ch_NN (<book>)" with the prior values>.
       Update them in one sweep:
           /autonovel:revision-pass --chapters <comma-list> --book <book>
   ```

   For users who specifically want the surgical 3-step path (rare),
   add a one-line "or run them individually" footnote ONLY when
   exactly 1 chapter is affected:

   ```
       (Surgical alternative — inspect between steps:
            /autonovel:check-anachronism <NN> --book <book>
            /autonovel:brief <NN> --book <book> --from auto
            /autonovel:revise <NN> --book <book>)
   ```

   **(b) Conflicts written back (K > 0).** Print:

   ```
     - <K> conflict(s) need human resolution. Open
           books/<book>/pending_canon.md
       and follow the HOW TO RESOLVE A CONFLICT block at the top
       of the file (three resolution paths: accept / reject / both
       wrong). Re-run /autonovel:promote-canon after editing.
   ```

   **(c) Plain successful promote (N > 0, S = 0, K = 0).** Print:

   ```
     - Canon updated. Continue with /autonovel:next.
   ```

   **(d) Nothing to do (N = M = K = S = 0; every pending file
   said `no new facts`).** Print:

   ```
     - No pending facts to promote. Continue with /autonovel:next.
   ```

   The point of (a) specifically is the answer to "what now?"
   after a successful research-driven supersedure. Without it the
   user has to grep their own chapters to find what referenced the
   old value — the command already knows the answer (the
   provenance tail of the superseded line) and should print it.
</workflow>

<acceptance>
- If `--dry-run`, no files under `shared/` or `books/*/` change.
- Otherwise, `shared/canon.md` contains a `## Promoted <UTC-date>`
  heading with at least one entry, unless every pending file was
  empty or said `no new facts`.
- For every book whose pending file contained only non-conflicting
  entries, `books/{book}/pending_canon.md` ends with `no new facts`.
- Contradictions are never silently merged: they are preserved under
  the `# Conflicts — resolve before next promote-canon` header in
  the pending file using the structured `## Conflict N` block format
  from step 8, including the mandatory HTML-comment instruction
  block at the top. Each conflict block names: the new candidate,
  the existing canon line, the file the existing line lives in, a
  one-sentence rationale, and the source (chapter or research note).
- A pending file containing conflicts NEVER also contains a
  `no new facts` marker — the two states are mutually exclusive.
</acceptance>
