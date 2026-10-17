---
name: autonovel:sidequest
description: Dispatcher for non-standard-path operations (menu + routing only).
argument-hint: ""
model_tier: light
allowed-tools:
  - file_read
reads:
  - project.yaml
  - .autonovel/last-action.json
writes: []
context_mode: none
---

<purpose>
Interactive menu of every "off the standard path" operation. This command
is a dispatcher — it prints a numbered list and points the user at the
real slash command. It never modifies files directly; the target commands
each own their own lock / checkpoint / footer.

The menu grows with the project. This version includes the PR 3
foundation + drafting sidequests, the PR 4 evaluation, revision,
and structural-edit sidequests, the PR 5 research, period-guardrail,
canon-promotion, and character/subplot/foreshadowing entries, the
PR 6 orchestrator + reorder/remove-chapter entries, and the PR 7
export commands (art, covers, audiobook, typeset, landing, package).
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. No arguments are expected. If the user passes
   anything, still print the menu — the argument is ignored but not an
   error.

2. Use `file_read` on `project.yaml` to list the books in the series.
   Use `file_read` on `.autonovel/last-action.json` (if it exists) so the
   menu can show the last action at the top. If neither file is present,
   print the menu anyway — the dispatcher is valid even in an empty
   series.

3. Print the menu verbatim:

   ```
   /autonovel:sidequest

   Foundation work:
     1.  Generate the world                → /autonovel:gen-world
     2.  Generate the character roster     → /autonovel:gen-characters
     3.  Generate a book's outline         → /autonovel:gen-outline --book <name>
     4.  Discover a book's voice           → /autonovel:voice-discovery --book <name>
     5.  Seed canon                        → /autonovel:gen-canon

   Drafting:
     6.  Draft a chapter                   → /autonovel:draft <N> --book <name>
     6a. Backfill chapter summary          → /autonovel:summarize-chapter <N> --book <name>
     6b. A/B-compare two models on draft   → /autonovel:compare-models --chapter <N> --book <name>
     6c. Sweep multiple drafts end-to-end  → /autonovel:draft-pass --chapters <range>

   Evaluation:
     7.  Score a chapter / book / compare  → /autonovel:evaluate --chapter <N> --book <name>
     8.  Reader panel (4 personas)         → /autonovel:reader-panel --book <name>
     9.  Deep Opus review                  → /autonovel:review --book <name>
     9a. Book-level structure review       → /autonovel:structure-review --book <name>

   Revision:
     10. Adversarial edit (find cuts)      → /autonovel:adversarial-edit <N> --book <name>
     11. Apply cuts deterministically      → /autonovel:apply-cuts <N> --book <name>
     12. Generate a revision brief         → /autonovel:brief <N> --book <name>
     13. Rewrite a chapter from brief      → /autonovel:revise <N> --book <name>
     13a. Sweep multiple chapters end-to-end → /autonovel:revision-pass --chapters <range>

   Structural edits (one checkpoint each):
     14. Shorten a chapter                 → /autonovel:shorten --chapter <N> --book <name> --target-words <W>
     15. Lengthen a chapter                → /autonovel:lengthen --chapter <N> --book <name> --target-words <W>
     16. Split a chapter in two            → /autonovel:split-chapter --chapter <N> --book <name>
     17. Merge two adjacent chapters       → /autonovel:merge-chapters --chapters <N>,<M> --book <name>
     18. Revoice one chapter               → /autonovel:revoice <N> --book <name> --pov <name>
     19. Reorder a chapter                 → /autonovel:reorder --from <A> --to <B> --book <name>
     20. Remove a chapter                  → /autonovel:remove-chapter <N> --book <name>

   Research and period guardrails:
     21. Research a real-world topic       → /autonovel:research "<topic>"
     22. Check period anachronisms         → /autonovel:check-anachronism <N> --book <name>
     23. Promote pending canon             → /autonovel:promote-canon
     24. Register a new research source    → /autonovel:add-source <url-or-doi>

   Cast and threads:
     25. Add a character                   → /autonovel:add-character --name <name>
     26. Deepen a character                → /autonovel:deepen-character <name> --book <name>
     27. Rename a character (global)       → /autonovel:rename-character --old <X> --new <Y>
     28. Add a two-beat subplot            → /autonovel:add-subplot --thread "<desc>" --plant <N> --payoff <M> --book <name>
     29. Foreshadow a plant+payoff         → /autonovel:foreshadow --plant <N> --payoff <M> --thread "<desc>" --book <name>

   Orchestration:
     30. Run the pipeline                  → /autonovel:run-pipeline --books <name[,name...]>

   Art and cover:
     31. Derive a visual style             → /autonovel:art-style --book <name>
     32. Generate art-direction variants   → /autonovel:art-directions --book <name> --surface <surface>
     33. Generate image variants           → /autonovel:art-curate --book <name> --surface <surface>
     34. Pick one variant as the final     → /autonovel:art-pick --book <name> --surface <surface> --variant <N>
     35. Generate per-chapter ornaments    → /autonovel:art-ornaments-all --book <name>
     36. Vectorise ornaments to SVG        → /autonovel:art-vectorize --book <name>
     37. Composite e-book cover text       → /autonovel:cover-composite --book <name>
     38. Compose print-ready wraparound    → /autonovel:cover-print --book <name> --pages <N>

   Audiobook:
     39. Parse chapters into scripts       → /autonovel:audiobook-script --book <name>
     40. Configure / list voices           → /autonovel:audiobook-voices --book <name> --list
     41. Generate one chapter's audio      → /autonovel:audiobook-generate --book <name> --chapter <N>
     42. Assemble the full audiobook       → /autonovel:audiobook-assemble --book <name>

   Typeset and release:
     43. Build PDF + ePub                  → /autonovel:typeset --book <name>
     44. Render the landing page           → /autonovel:landing --book <name>
     45. Package the full release zip      → /autonovel:package --book <name>

   Navigation:
     46. Where am I?                       → /autonovel:next
     47. Resume an interrupted command     → /autonovel:resume

   Maintenance:
     48. Roll back recent changes          → autonovel rollback
     49. Reconcile state                   → autonovel doctor
     50. Show status                       → autonovel status

   Select [1-50, 0=exit]:
   ```

4. Wait for the user's selection. On `0` or empty input, print "exiting"
   and stop. Valid range is `0-50`. On a valid number, print the corresponding command line and
   a one-line instruction: "Run that command now, or press Enter to stay
   in the menu." Do not invoke the command on the user's behalf — routing
   via a separate slash-command invocation preserves the lock / checkpoint
   guarantees of the target command.

5. If the user chooses a command that requires `--book <name>` and the
   series has exactly one book, substitute that book's name in the
   suggestion; otherwise leave the `<name>` placeholder literal so the
   user picks.
</workflow>

<acceptance>
- No files are written.
- The printed menu contains exactly the fifty options listed
  above (in that order).
- The command does not invoke any other slash command or CLI tool
  automatically — routing is advisory only.
</acceptance>
