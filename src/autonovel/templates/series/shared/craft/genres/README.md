# Genre guides

What each kind of book promises its reader, and what every command does
about it. Package-owned: `autonovel refresh-templates` keeps this folder
current. A guide written for one series by `/autonovel:genre --add` lives
in `shared/genres/<id>.md` instead and is never overwritten.

**Why they exist.** The other craft documents say how to write any novel.
They do not say what a particular reader comes for, so every loop that
reads for pace and clarity treats that material as fat: in a historical
novel, the cold readers skimmed the history and the editor proposed
cutting it, when learning the period is part of why its readers read. A
genre guide names the payload, so the commands protect it.

## Which genre a book is

`project.yaml` names the series' `genre:` and optional `subgenres:` (a
list; a book can be two, such as a biographical novel with a political
thriller's engine). A book may override either under its `books:` entry.
`autonovel genre list` prints the registry (every genre, its subgenres and
their one-line promises); `autonovel genre show --book <name>` prints the
book's genre, subgenres, guide path and extra evaluate dimensions;
`/autonovel:genre --set` changes them. A subgenre the registry lacks can be
given as `other: <words>`.

## The sections every guide has

Each guide has these `##` sections, in this order. A command reads the
sections named for it, plus `## The promise` and the `###` entries under
`## Subgenres` for the book's active subgenres.

| Section | What it holds | Read by |
|---|---|---|
| The promise | What this reader comes for, with the evidence; the payload item by item; what readers object to | every command below |
| Subgenres | One `### \`id\` — name` per subgenre: promise, what it must deliver, payload weighting, failures, comparables | design, gen-outline, structure-review, developmental-edit, reader-panel |
| Research | What to find out beyond the events | research, gen-world |
| Design | The ledger the design writes (`## What the reader comes to learn` for historical fiction) and the genre contract | design, gen-outline, cast |
| Drafting | How the payload reaches the page | draft, revise, brief |
| The first reader | Who this genre's cold reader is; sections it adds to the report | first-read, draft's cold reader |
| Judging | The extra evaluate dimension(s) and their rubric; what other dimensions must not mark down | evaluate, review, reader-panel |
| Cutting | What never counts as over-explaining; the `MISPLACED` type | adversarial-edit, apply-cuts |
| Editing | Questions for the developmental editor; typical failures | developmental-edit, structure-review, review |
| Back matter | Notes and appendices this reader expects | appendix |
| Sources | Every claim's source | — |

Where a guide and `books/<book>/voice.md` disagree, the voice file wins,
as it does over every craft document.

## Guides written

- `historical.md` — Historical fiction: biographical, political thriller,
  traditional, adventure, mystery, romance, saga, multi-period epic,
  western, literary, Christian, time-slip, alternate history, historical
  fantasy. Extra dimension: `history`.

Other genres in the registry (science fiction, fantasy, mystery, thriller,
romance, horror, literary) have one-line promises per subgenre but no guide
yet; `/autonovel:genre --add <genre>` researches and writes one, sourced,
in these sections.
