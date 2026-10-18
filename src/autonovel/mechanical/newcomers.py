"""New and returning names per chapter — a candidate list for the reader's map.

`autonovel mechanical newcomers <book_dir> [--chapter N] [--first-words 500]
[--gap 2]` lists, for each chapter, the capitalised words (people, places,
institutions, foreign terms) that appear for the first time in the book
in that chapter, where each first appears, and how many land in the
chapter's opening words; and the ones *returning* after an absence (last
seen `--gap` or more chapters earlier), which the reader may have
forgotten and the chapter should re-anchor (who they are, what they want).

Why it exists: on kingmaker2 the author found that a chapter "suddenly
introduces several new characters and locations, it seemed jarring", and
didn't know what an elector, fustian or the Marangona was. `draft` step
3c now asks for one new person at a time and plain first-use
explanations; this helper shows the reviewer where to look. A candidate
generator, not a gate: it can't tell a name from a sentence-initial
word that happens to be capitalised everywhere, and it doesn't know
whether a term was explained. The returning list exists because the
author, meeting seven electors in chapter 1, asked for "reminders of who
they are and what they want when they next appear".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..paths import iter_chapter_files
from .frontmatter import strip_yaml_frontmatter

_WORD = re.compile(r"[A-ZÀ-ÖØ-Þ][\w'’\-]*[\w]|[A-ZÀ-ÖØ-Þ]")
_SENT_START = re.compile(r"(?:^|[.!?…]\s+|[\"“‘(]\s*|\n\s*)$")
# Capitalised function words and pronouns that are never newcomers.
_STOP = set("""
I A An The And But Or Nor For So Yet If Then When While Where What Who Whom
Whose Which Why How He She It We They You His Her Its Our Their Your This
That These Those There Here Not No Yes One Two Three Four Five Six Seven
Eight Nine Ten Mr Mrs Sir Madam God Lord Lady Master Mister Saint St Herr
Frau Don Monday Tuesday Wednesday Thursday Friday Saturday Sunday January
February March April May June July August September October November
December Christmas Easter Whitsun Michaelmas Lent Mass
""".split())


@dataclass
class Newcomer:
    word: str
    first_word_index: int
    count: int

    def to_dict(self) -> dict:
        return {"word": self.word, "first_word_index": self.first_word_index,
                "count": self.count}


@dataclass
class Returning:
    word: str
    last_seen_chapter: int
    first_word_index: int
    count: int

    def to_dict(self) -> dict:
        return {"word": self.word, "last_seen_chapter": self.last_seen_chapter,
                "first_word_index": self.first_word_index, "count": self.count}


@dataclass
class ChapterNewcomers:
    chapter: int
    file: str
    words: int
    newcomers: list[Newcomer] = field(default_factory=list)
    returning: list[Returning] = field(default_factory=list)
    opening_limit: int = 500

    @property
    def in_opening(self) -> list[Newcomer]:
        return [n for n in self.newcomers if n.first_word_index < self.opening_limit]

    def to_dict(self) -> dict:
        return {"chapter": self.chapter, "file": self.file, "words": self.words,
                "opening_limit": self.opening_limit,
                "in_opening": [n.word for n in self.in_opening],
                "newcomers": [n.to_dict() for n in self.newcomers],
                "returning": [r.to_dict() for r in self.returning]}


def _capitalised_mid_sentence(text: str) -> dict[str, list[int]]:
    """Capitalised words not at a sentence start, with word positions.
    Sentence-initial words count only if the same word also appears
    capitalised mid-sentence somewhere in the text."""
    positions: dict[str, list[int]] = {}
    starts: dict[str, list[int]] = {}
    word_index = 0
    last = 0
    for m in re.finditer(r"\S+", text):
        token = m.group(0)
        word_index += 1
        opens_quote = token[:1] in "\"“‘(["
        w = _WORD.match(token.lstrip("\"“‘'(["))
        if not w or w.start() != 0:
            last = m.end()
            continue
        word = w.group(0)
        if re.search(r"['’](?:ve|ll|d|re|m|t)$", word, re.IGNORECASE):
            last = m.end()          # a contraction: I've, You'll, Don't
            continue
        word = re.sub(r"['’]s$", "", word).rstrip("'’")
        if word in _STOP or len(word) < 3:
            last = m.end()
            continue
        at_start = (opens_quote or m.start() == 0
                    or bool(_SENT_START.search(text[:m.start()][-6:])))
        (starts if at_start else positions).setdefault(word, []).append(word_index - 1)
        last = m.end()
    for word, idx in starts.items():
        if word in positions:
            positions[word] = sorted(positions[word] + idx)
    return positions


def scan_book(book_root: Path, *, chapter: int | None = None,
              first_words: int = 500, gap: int = 2) -> dict:
    last_seen: dict[str, int] = {}
    out: list[ChapterNewcomers] = []
    for path in iter_chapter_files(book_root / "chapters"):
        try:
            num = int(path.stem.split("_")[-1])
        except ValueError:
            continue
        body = strip_yaml_frontmatter(path.read_text(encoding="utf-8"))
        found = _capitalised_mid_sentence(body)
        cn = ChapterNewcomers(chapter=num, file=path.name, words=len(body.split()),
                              opening_limit=first_words)
        for word, idx in sorted(found.items(), key=lambda kv: kv[1][0]):
            if word not in last_seen:
                cn.newcomers.append(Newcomer(word, idx[0], len(idx)))
            elif num - last_seen[word] >= gap:
                cn.returning.append(Returning(word, last_seen[word], idx[0], len(idx)))
        for word in found:
            last_seen[word] = num
        if chapter is None or num == chapter:
            out.append(cn)
    return {
        "book_root": str(book_root),
        "first_words": first_words,
        "gap": gap,
        "chapters": [c.to_dict() for c in out],
        "note": ("Candidates only: capitalised words first seen in the book in this "
                 "chapter, and words returning after an absence. Check that each new "
                 "person arrives with who they are, that each unfamiliar term is "
                 "explained in plain words, that the opening doesn't introduce too many "
                 "at once, and that each returning person is re-anchored (who they are, "
                 "what they want) the first time they come back (draft step 3c)."),
    }


def render_markdown(report: dict) -> str:
    lines = ["# New names per chapter", "",
             f"{report['note']} Opening = first {report['first_words']} words.", ""]
    for ch in report["chapters"]:
        lines.append(f"## Chapter {ch['chapter']} ({ch['words']:,} words) — "
                     f"{len(ch['newcomers'])} new, {len(ch['in_opening'])} in the opening")
        if ch["in_opening"]:
            lines.append(f"- in the opening: {', '.join(ch['in_opening'])}")
        rest = [n["word"] for n in ch["newcomers"] if n["word"] not in ch["in_opening"]]
        if rest:
            lines.append(f"- later: {', '.join(rest)}")
        if ch["returning"]:
            back = ", ".join(f"{r['word']} (last seen ch {r['last_seen_chapter']})"
                             for r in ch["returning"])
            lines.append(f"- returning after a gap of {report['gap']}+ chapters: {back}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
