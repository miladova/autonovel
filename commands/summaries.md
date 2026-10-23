---
name: autonovel:summaries
description: Filter the per-chapter summary table by a small query DSL (pov / score / story_time / cast / location / plot).
argument-hint: "[--book <short-name>] [--where '<expr>'] [--format markdown|json]"
model_tier: light
allowed-tools:
  - bash
reads:
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - books/{book}/eval_logs/*.json
writes: []
context_mode: book
---

<purpose>
A pure-mechanical filter over the structured chapter-summary
index. Distinct from `/autonovel:talk` (which uses the LLM for
fuzzy semantic questions) and from `/autonovel:chapter-summary`
(which prints the whole table); this command is the in-between
when you know exactly which chapters you want.

Example queries:

```
/autonovel:summaries --where 'pov == "Lucia"'
/autonovel:summaries --where 'score < 7.0 and word_count > 3000'
/autonovel:summaries --where 'low_score < 7.0'   # a dimension fails, whatever the mean
/autonovel:summaries --where 'story_time >= "1521-11" and story_time <= "1522-02"'
/autonovel:summaries --where 'cast contains Niccolò'
/autonovel:summaries --where 'plot contains "book of accounts"'
/autonovel:summaries --where 'chapter in 5..12'
/autonovel:summaries --where 'location contains Padua or location contains Venice'
```

Free, scriptable, stable semantics, no LLM drift.

The DSL supports:

- Fields: `pov`, `score`, `story_time`, `word_count`, `cast`,
  `plot`, `location`, `chapter`, `status`, `low_score` and
  `low_dim` (the chapter's lowest-scoring dimension in its latest
  eval, e.g. `low_dim == "sense_of_place"`).
- Comparison: `==`, `!=`, `<`, `<=`, `>`, `>=`. Numeric on
  `score`, `word_count`, `chapter`; lexicographic on the rest
  (works for ISO dates on `story_time`).
- `<field> contains <literal>` — substring (case-insensitive on
  cast lists).
- `<field> in <num>..<num>` — closed numeric range.
- `and` / `or` (`&&` / `||`); `not <pred>`; parenthesise to
  override left-to-right.
- String literals quoted with `"…"` or `'…'`. Bare-word
  literals (`Lucia`, `Padua`) are accepted for the common
  single-token case.

Pure mechanical. No LLM call. Light tier — runs in
milliseconds.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`. `--book <short-name>` defaults via
   `_begin`. `--where '<expr>'` is the filter (omit for "every
   row"). `--format markdown|json` (default `markdown`).

2. Use the `Bash` tool to call the housekeeping helper:

   ```
   autonovel mechanical summary-query books/{book} --where '<expr>' --format <format>
   ```

   The helper reads the same per-chapter index that
   `/autonovel:chapter-summary` uses (chapter frontmatter +
   summary file + latest eval log), applies the DSL filter, and
   emits a markdown table of the surviving chapters in
   chapter-number order.

3. Print the helper's stdout verbatim. Do not editorialise.
   The `score` column comes from each chapter's latest entry in
   `books/{book}/eval_logs/`, so a chapter that has never been
   evaluated shows `—` and is excluded from any `score < N` /
   `score >= N` filter.

4. When the helper exits non-zero (parse error in the
   expression), surface its stderr message verbatim — the
   parser names the offending token and position so the user
   can fix the expression in one shot.

5. Do not touch disk. This command is read-only by contract.
</workflow>

<acceptance>
- No files are written.
- When `--where` is empty or omitted, every drafted chapter
  appears in the output table.
- When `--where` matches no chapters, the markdown output
  contains `_No matching chapters._` and exits 0.
- A syntactically-invalid `--where` expression exits non-zero
  and prints a single-line error naming the offending token.
- The output ends with `_<N> chapter(s) matched._` for non-empty
  results.
</acceptance>
