# Chapter frontmatter schema

Every chapter file under `books/<name>/chapters/ch_NN.md` starts with a YAML
frontmatter block. It is the contract the Tier-1 validator enforces and the
basis for multi-book story-time coordination (REWRITE-PLAN.md §7).

```yaml
---
book: inquisitor            # required; string; must match a book name in project.yaml
chapter: 5                  # required; positive integer
pov: Tommaso                # required; string; POV character
story_time: 1522-03-15      # required; ISO date (YYYY-MM-DD)
                            # or ISO range (YYYY-MM-DD..YYYY-MM-DD)
events: [E-047, E-048]      # required; list of event IDs from shared/events.md
                            # (empty list is allowed)
status: drafted             # required; one of: drafted | revised | locked
word_count: 3214            # optional; integer
dateline: "Venice, autumn 1473"   # optional; place and date printed under the
                            # chapter title by typeset and the ePub (set it in any
                            # book whose chapters move between times or places)
score: 7.8                  # optional; number
---
```

Additional fields are permitted and ignored by the validator; commands may
add their own keys (for example `score_breakdown`, `revision_cycle`).
