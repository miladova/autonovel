---
name: autonovel:first-read
description: A cold first reader for one chapter — someone who knows nothing about the subject and has read only the earlier chapters — reports every word, name or sentence they didn't understand, where they got lost, crowded or bored, and whether they'd turn the page. Draft runs it on every new chapter; run it yourself on any chapter you've changed.
argument-hint: "<chapter-number> --book <short-name>"
model_tier: heavy
allowed-tools:
  - file_read
  - file_write
  - task
reads:
  - shared/craft/FIRST-READER.md
  - books/{book}/voice.md
  - books/{book}/chapters/ch_{chapter}.md
  - books/{book}/chapters/ch_*.md
  - books/{book}/chapters/ch_*.summary.md
  - shared/craft/genres/*.md
  - shared/genres/*.md
writes:
  - books/{book}/edit_logs/first_read_ch{chapter}.md
context_mode: book
---

<purpose>
Find, before the author does, what a reader can't follow: the
unexplained word, the name with no introduction, the scene that never
says where or when it is, the clever sentence that has to be read
twice, the opening that crowds in six new people, the page where the
reader stops. The writer can't see these in their own chapter (they
know what everything means), and a reviewer judging against the
writer's style sheet doesn't look. On one book the author found all of
them themselves, after every check had passed. The author should never be
the first reader.

The reader is a separate agent that sees only the book — the chapter
and what came before it — never the outline, design, research or voice
file. `shared/craft/FIRST-READER.md` is its brief.
</purpose>

<workflow>
1. Parse `$ARGUMENTS`: `<chapter-number>` and `--book`. Missing either →
   stop with a one-line usage reminder.

2. Use `file_read` on `shared/craft/FIRST-READER.md` and on
   `books/{book}/voice.md` (Part 1's **Reader** line, if present, names
   the reader; otherwise use the brief's default reader). Then read the
   `## The first reader` section of the book's genre guide: the file
   `_begin`'s `genre:` line names (`autonovel genre show --book {book}`
   prints it when no preamble ran; it is
   `shared/craft/genres/<genre>.md`, or the series' own
   `shared/genres/<genre>.md`), when the book has one: it
   says who this genre's reader is (a reader of historical fiction reads
   partly to learn the period) and adds report sections. The voice
   file's Reader line still wins.

3. Gather what the reader may see: `books/{book}/chapters/ch_{chapter}.md`
   and the chapters before it. If the earlier chapters together run
   under about 60,000 words, give them in full; otherwise give the last
   three in full and `books/{book}/chapters/ch_*.summary.md` for the
   rest. Strip YAML frontmatter except each chapter's title and
   `dateline`.

4. Use `task` to spawn **one** fresh heavy-tier reader. Its prompt is
   the brief's "Who the reader is", "What the reader reports" sections
   (verbatim), the genre guide's `## The first reader` section
   (verbatim) when there is one, the reader line from voice.md if any, then the earlier
   chapters and the chapter. It must not be given anything else, and
   it must answer in the brief's ten sections, quoting the text.

5. Use `file_write` to save its report, unedited, at
   `books/{book}/edit_logs/first_read_ch{chapter}.md`, headed with the
   date and one count line: `lost N · didn't know N · read twice N ·
   too many N · forgot N · couldn't picture N · types N · skimmed N ·
   turn the page: yes|no` (types = the people it read as a type), plus
   `learned N` when the genre guide added "What I learned".

6. Report the count line, the three most serious items (quoted), and
   **Next:** when there are items under Lost, Didn't know, Read twice,
   Too many at once, Forgot who, Couldn't picture or Who felt real, a
   "no" to the page turn, or an empty "What I learned" in a genre that
   adds it,
   `/autonovel:revise {chapter} --book {book}` with the report as the
   brief (or fix them by hand); otherwise "the chapter reads clean to a
   first reader". Do not edit the chapter here.
</workflow>

<acceptance>
- `books/{book}/edit_logs/first_read_ch{chapter}.md` exists with the
  ten sections and the count line.
- The reader was given only chapter text and summaries — never the
  outline, design, research or voice file.
- The chapter is unchanged.
</acceptance>
