# Series layout

After `autonovel new-series demo && autonovel new-book one --series demo`, the
tree is:

```
demo/
  project.yaml                    # series config (genre, subgenres, period, books…); see REWRITE-PLAN.md §6
  .gitignore
  .autonovel/                     # pipeline working directory (checked in)
    state.json
    last-action.json              # written after the first command runs
    command-log.jsonl             # append-only
    checkpoints/                  # one dir per destructive command
    session-notes/                # kept in git via .gitkeep
  shared/
    world.md
    characters.md
    canon.md
    events.md
    timeline.md
    MYSTERY.md
    period_bans.txt
    sources.bib
    craft/                        # package-owned craft docs (refresh-templates)
      genres/                     # one guide per genre: what its reader comes for
        README.md                 # the fixed sections and which command reads each
        historical.md
    genres/                       # (optional) this series' own guides, from /autonovel:genre --add
    research/
      seed/
      notes/
      sources.yaml
  books/
    one/
      seed.txt
      voice.md
      outline.md
      canon.md                      # book-scoped canon (this book's own facts)
      pending_canon.md
      state.json                    # phase, chapters_drafted, chapters_total: refreshed by every command's _end
      results.tsv
      chapters/
      briefs/
      edit_logs/
      eval_logs/
      typeset/
```

All files start empty or as stubs. Commands fill them in.
