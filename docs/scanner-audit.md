# Scanner audit — where the brittle bits are

The autonovel mechanical scanners (`src/autonovel/mechanical/*.py`)
fall into three groups by how they're parameterised. This page
documents each scanner's load-bearing inputs so you know which
levers exist when behaviour drifts.

The constraint shaping this layout (per the
`feedback_avoid_brittle_python.md` memory): mechanical scanners
are **candidate generators**, not quality gates. Standalone
mechanical scoring drifts. The pattern that works is "small
mechanical pre-flight" + "LLM judge in `/autonovel:evaluate`
classifies and scores." When a scanner uses a hand-curated
list, the list should be ≤20 entries OR live in per-book
config the user can extend.

## Group A — fully config-driven (zero hardcoded taste)

These scanners take **all** their judgement inputs from per-book
config files the user owns. The codebase ships no opinion about
what the right answers are; you tell each scanner what to look
for.

| Scanner | Per-book config | Notes |
|---|---|---|
| `mechanical/motifs.py` | `books/<book>/motifs.md` | Bullet list `- slug: keyword1, keyword2` |
| `mechanical/entity_track.py` | `books/<book>/entities.md` (preferred) or `shared/canon.md` | Falls back to canon `[shortname]` heads when the explicit file is absent |
| `mechanical/period_register.py` (literal-bans pass) | `shared/period_bans.txt` | One banned word per line, `#` comments |
| `mechanical/pov_bleed.py` (cast input) | `shared/characters.md` | `**Name** — role` bullets or `## Name` headings |

If these scanners produce wrong results, the fix is **in your
per-book config file**, not in Python.

## Group B — pure math, no curated lists

These scanners use real math (Flesch-Kincaid, frequency stats,
mtime comparisons, regex over neutral structural shapes like
scene-break markers). They don't drift with vocabulary.

| Scanner | Math | Knobs |
|---|---|---|
| `mechanical/period_register.py` (syntax-drift pass) | Flesch-Kincaid grade vs voice/seed/median baseline | `--threshold` (grade levels) |
| `mechanical/dashboard.py` | Word counts, scene counts (`***`/`---`), dialogue density (paragraph-opening `"`), score statistics | none |
| `mechanical/series_arc.py` | Story-time monotonicity, summary-coverage fractions, completion ratios | `--threshold` (chapter score) |
| `mechanical/summary_query.py` | DSL parser (no judgement; pure filter) | the user's `--where` expression |
| `mechanical/chapter_summary.py` | Eval-log indexing, frontmatter parsing | none |

These don't have a "wrong answer" condition — if they look off,
the input data is the issue, not the scanner.

## Group C — small curated lists (the brittle bits)

These scanners ship a hand-curated word list. **Per the
brittle-Python rule, the lists are kept ≤25 entries each**, the
LLM judge in `/autonovel:evaluate` does the actual scoring, and
the scanner is documented as a "review list, not a gate."

| Scanner | Curated lists | Size | LLM judge that does the scoring |
|---|---|---|---|
| `mechanical/dialogue.py` | `ADVERBS`, `SAID_BOOKISMS`, `SPEECH_VERBS`, `ACTION_BEAT_VERBS`, `SOFTENING_QUALIFIERS` | ~50 / ~35 / ~40 / ~25 / ~13 | `prose_quality`, `voice_adherence` (chapter mode) |
| `mechanical/show_dont_tell.py` | `EMOTIONS`, `INTERIORITY_VERBS`, `FILTER_ADVERBS` | ~50 / ~20 / ~20 | `show_dont_tell_ratio` (chapter mode), `show_dont_tell_arc` (full mode) |
| `mechanical/pov_bleed.py` (verb input) | `INTERIORITY_VERBS`, `INTERIORITY_NOUNS` | ~25 / ~15 | `voice_adherence` (chapter mode) |

If a Group C scanner's list misses the pattern in *your* book,
the right next step is:

1. Note the missed pattern. Does the LLM judge in `evaluate`
   catch it? (Run `/autonovel:evaluate --chapter N` and look at
   `prose_quality` / `voice_adherence` notes.)
2. If the LLM judge catches it, the scanner just needs a
   one-line addition to the curated list — small PR, low risk.
3. If the LLM judge ALSO misses it, the right fix is to extend
   the LLM-judge dimension's rubric in `commands/evaluate.md`,
   not to layer more regex onto the scanner.

## Group D — LLM-side dimensions in `commands/evaluate.md`

Every Group A / B / C scanner pairs (or should pair) with an
LLM judge dimension. The judge:

- reads the scanner's candidates as evidence,
- applies the rubric block in `evaluate.md` to classify each,
- emits the actual score that drives brief / revise.

| Scanner output | LLM-judge dimension | Mode |
|---|---|---|
| `show-dont-tell` candidates | `show_dont_tell_ratio` | `--chapter` |
| `show-dont-tell` candidates | `show_dont_tell_arc` | `--full` |
| `series-arc` evidence | `series_question` + 4 sibling dimensions | `--phase series` |
| `motifs` density (book-wide) | (consumed in `--full` evaluate; surfaces as motif-arc commentary) | `--full` |
| `pov-bleed` candidates | `voice_adherence` | `--chapter` |
| `period-register` literal hits | `canon_compliance` | `--chapter`, `--full` |
| `period-register` syntax-drift | `voice_adherence` | `--chapter`, `--full` |
| `dialogue` candidates | `prose_quality` | `--chapter` |
| `repeats` echoes, phrases, similar sentences | `repetition` (and `repeats`, which the brief turns into `## Said already`) | `--chapter` |
| `repeats` echoes (book-wide) | `overall_engagement` (`repeated_across_book`) | `--full` |

This file is the canonical "where to look when behaviour drifts"
reference. Update it when adding a new scanner.
