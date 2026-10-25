"""Things said more than once — a candidate list for "say it once".

`autonovel mechanical repeats <book_dir> [--chapter N] [--min-words 6]
[--phrase-min 4] [--top 25] [--format json|markdown]` lists three kinds of
repetition in a book's chapters:

- **echoes**: the same run of words (six or more, at least two of them
  uncommon) at two or more places, in one chapter or across chapters: a
  description repeated word for word every time a person comes back ("the
  Count, the Elector Palatine's younger brother"), a sentence carried over
  from an earlier chapter, a fact restated in the same words;
- **phrases**: a short phrase (three or four words) used four or more times
  in one chapter and at least twice as often there as in the rest of the
  book ("after the vote", eight times in a chapter);
- **similar sentences**: two sentences in one chapter that share most of
  their uncommon words, the same point made twice in different words.

Why it exists: the kingmaker2 author, two-thirds into the third version's
chapter 1, found it "long and a bit slow" with "repetition about the
electors". The chapter explained four times that seven princes choose the
Emperor, stated the pay-after-the-vote rule five times and recited the
vote count four times in twelve lines, and a sweep found the same in
nearly every chapter. The chapter evaluation had asked whether a *term*
was explained twice, never whether an *idea* was, and had passed it.

A candidate generator, not a gate. "Uncommon" is measured on the book
itself (a word outside its most frequent words), so no word list is
involved. It finds repeated wording, not repeated ideas in new words
(only the similar-sentence list reaches toward those); the judge decides
which candidates are repetition and which are a deliberate echo, a letter
quoted again, or a payoff line, and reads for the restatements no scanner
sees (`/autonovel:evaluate`'s `repetition` dimension).
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..paths import iter_chapter_files
from .frontmatter import strip_yaml_frontmatter

_TOKEN = re.compile(r"\w[\w'’\-]*\w|\w")
_SENTENCE = re.compile(r"[^.!?…]+(?:[.!?…]+[\"”’)\]]*|$)")
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
_POSSESSIVE = re.compile(r"['’]s$")


@dataclass
class _Tok:
    norm: str          # lower-cased, curly apostrophes straightened
    base: str          # norm without a possessive 's
    capital: bool      # written with a capital letter
    first: bool        # first word of its sentence
    chapter: int       # index into the scanned chapters
    para: int          # global paragraph id
    sent: int          # global sentence id
    line: int          # line in the chapter file (frontmatter included)
    start: int         # offset in the chapter file
    end: int


@dataclass
class _Chapter:
    num: int
    file: str
    raw: str
    words: int


def _tokenise(chapters: list[_Chapter]) -> tuple[list[_Tok], list[tuple[int, str]]]:
    """Every word of every chapter in reading order, and every sentence
    as (chapter index, text)."""
    toks: list[_Tok] = []
    sentences: list[tuple[int, str]] = []
    para_id = 0
    for ci, ch in enumerate(chapters):
        body = strip_yaml_frontmatter(ch.raw)
        offset = len(ch.raw) - len(body)
        newlines = [m.start() for m in re.finditer("\n", ch.raw)]
        pos = 0
        spans = []
        for m in _PARAGRAPH_BREAK.finditer(body):
            spans.append((pos, m.start()))
            pos = m.end()
        spans.append((pos, len(body)))
        for p_start, p_end in spans:
            para = body[p_start:p_end]
            if not para.strip() or para.strip() in ("---", "***", "* * *"):
                continue
            para_id += 1
            for sm in _SENTENCE.finditer(para):
                s_text = sm.group(0)
                if not _TOKEN.search(s_text):
                    continue
                sent_id = len(sentences)
                sentences.append((ci, s_text.strip()))
                first = True
                for tm in _TOKEN.finditer(s_text):
                    word = tm.group(0)
                    norm = word.lower().replace("’", "'")
                    abs_start = offset + p_start + sm.start() + tm.start()
                    toks.append(_Tok(
                        norm=norm,
                        base=_POSSESSIVE.sub("", norm).rstrip("'"),
                        capital=word[:1].isupper(),
                        first=first,
                        chapter=ci,
                        para=para_id,
                        sent=sent_id,
                        line=bisect_right(newlines, abs_start - 1) + 1,
                        start=abs_start,
                        end=abs_start + len(word),
                    ))
                    first = False
    return toks, sentences


def _common_words(toks: list[_Tok], share: float, cap: int = 100) -> set[str]:
    """The book's own commonest words: those making up at least `share` of
    its words (its function words, and the names and subjects on every
    page), at most `cap` of them. Measured on the book, so no word list;
    a short text needs at least three uses of a word to call it common."""
    counts = Counter(t.base for t in toks)
    floor = max(3.0, share * len(toks))
    return {w for w, n in counts.most_common(cap) if n >= floor}


def _names(toks: list[_Tok]) -> set[str]:
    """Words written with a capital nearly every time they appear in mid
    sentence: names, titles, places."""
    caps: Counter[str] = Counter()
    seen: Counter[str] = Counter()
    for t in toks:
        if t.first:
            continue
        seen[t.base] += 1
        if t.capital:
            caps[t.base] += 1
    return {w for w, n in seen.items() if caps[w] >= 0.8 * n}


def _echoes(toks: list[_Tok], chapters: list[_Chapter], common: set[str],
            min_words: int, max_places: int = 12) -> list[dict]:
    n = min_words
    index: dict[tuple, list[int]] = defaultdict(list)
    for i in range(len(toks) - n + 1):
        if toks[i].para != toks[i + n - 1].para:
            continue
        index[tuple(t.norm for t in toks[i:i + n])].append(i)
    occ: dict[int, tuple[int, ...]] = {}
    for starts in index.values():
        if 2 <= len(starts) <= max_places:
            for s in starts:
                occ[s] = tuple(starts)
    runs: list[tuple[tuple[int, ...], int]] = []      # (starts, length in words)
    for i in sorted(occ):
        starts = occ[i]
        if i != starts[0]:
            continue
        prev = occ.get(i - 1)
        if prev is not None and tuple(q + 1 for q in prev) == starts:
            continue                                  # inside a longer run
        k = 0
        while True:
            nxt = occ.get(i + k + 1)
            if nxt is None or nxt != tuple(q + k + 1 for q in starts):
                break
            k += 1
        runs.append((starts, k + n))
    # Drop a run whose every place sits inside a longer reported run.
    runs.sort(key=lambda r: -r[1])
    covered: list[tuple[int, int]] = []
    out = []
    for starts, length in runs:
        if all(any(a <= s and s + length <= b for a, b in covered) for s in starts):
            continue
        words = toks[starts[0]:starts[0] + length]
        if sum(1 for t in words if t.base not in common) < 2:
            continue
        covered.extend((s, s + length) for s in starts)
        first, last = words[0], words[-1]
        text = chapters[first.chapter].raw[first.start:last.end]
        places = [{"chapter": chapters[toks[s].chapter].num, "line": toks[s].line}
                  for s in starts]
        chs = sorted({p["chapter"] for p in places})
        out.append({
            "words": length,
            "text": " ".join(text.split()),
            "places": places,
            "chapters": chs,
            "same_chapter": len(chs) < len(places),
            "across_chapters": len(chs) > 1,
        })
    out.sort(key=lambda e: (-(len(e["places"]) - 1) * e["words"], e["places"][0]["chapter"],
                            e["places"][0]["line"]))
    return out


def _phrases(toks: list[_Tok], chapters: list[_Chapter], common: set[str],
             names: set[str], phrase_min: int) -> dict[int, list[dict]]:
    book_counts: Counter[tuple] = Counter()
    per_chapter: dict[int, dict[tuple, list[int]]] = defaultdict(lambda: defaultdict(list))
    for n in (3, 4):
        for i in range(len(toks) - n + 1):
            if toks[i].sent != toks[i + n - 1].sent:
                continue
            gram = toks[i:i + n]
            if not any(t.base not in common and t.base not in names for t in gram):
                continue
            key = tuple(t.norm for t in gram)
            book_counts[key] += 1
            per_chapter[gram[0].chapter][key].append(gram[0].line)
    book_words = sum(c.words for c in chapters) or 1
    out: dict[int, list[dict]] = {}
    for ci, grams in per_chapter.items():
        share = chapters[ci].words / book_words
        found = []
        for key, lines in grams.items():
            count = len(lines)
            if count < phrase_min:
                continue
            if len(chapters) > 1:
                expected = book_counts[key] * share
                if count < 2.0 * expected:
                    continue
            found.append({"phrase": " ".join(key), "count": count,
                          "book_count": book_counts[key], "lines": lines})
        # A three-word phrase inside a reported four-word one adds nothing.
        fours = [f for f in found if len(f["phrase"].split()) == 4]
        kept = []
        for f in found:
            if len(f["phrase"].split()) == 3 and any(
                    f["phrase"] in g["phrase"] and f["count"] - g["count"] <= 1 for g in fours):
                continue
            kept.append(f)
        kept.sort(key=lambda f: (-f["count"], f["phrase"]))
        out[chapters[ci].num] = kept[:15]
    return out


def _similar(toks: list[_Tok], sentences: list[tuple[int, str]], chapters: list[_Chapter],
             common: set[str], names: set[str], top: int) -> dict[int, list[dict]]:
    words_of: dict[int, set[str]] = defaultdict(set)
    line_of: dict[int, int] = {}
    for t in toks:
        line_of.setdefault(t.sent, t.line)
        if t.base not in common and len(t.base) > 1:
            words_of[t.sent].add(t.base)
    by_chapter: dict[int, list[int]] = defaultdict(list)
    for sid, (ci, _) in enumerate(sentences):
        if len(words_of[sid]) >= 3:
            by_chapter[ci].append(sid)
    out: dict[int, list[dict]] = {}
    for ci, sids in by_chapter.items():
        inverted: dict[str, list[int]] = defaultdict(list)
        for sid in sids:
            for w in words_of[sid]:
                inverted[w].append(sid)
        pairs: Counter[tuple[int, int]] = Counter()
        for w, members in inverted.items():
            if len(members) > 40:          # a word on every page links nothing
                continue
            for a_i, a in enumerate(members):
                for b in members[a_i + 1:]:
                    pairs[(a, b)] += 1
        found = []
        for (a, b), shared_n in pairs.items():
            if shared_n < 3 or b == a + 1:
                continue
            shared = words_of[a] & words_of[b]
            plain = [w for w in shared if w not in names]
            if len(plain) < 2 or not any(len(w) >= 5 for w in plain):
                continue
            overlap = len(shared) / min(len(words_of[a]), len(words_of[b]))
            if overlap < 0.6:
                continue
            ta, tb = sentences[a][1], sentences[b][1]
            if " ".join(ta.split()).lower() == " ".join(tb.split()).lower():
                continue
            found.append({
                "lines": [line_of[a], line_of[b]],
                "overlap": round(overlap, 2),
                "shared": sorted(shared),
                "first": _clip(ta),
                "second": _clip(tb),
            })
        found.sort(key=lambda f: (-f["overlap"] * len(f["shared"]), f["lines"]))
        seen_lines: set[tuple[int, int]] = set()
        unique = []
        for f in found:                    # one pair per pair of lines
            key = tuple(f["lines"])
            if key in seen_lines:
                continue
            seen_lines.add(key)
            unique.append(f)
        out[chapters[ci].num] = unique[:top]
    return out


def _clip(text: str, limit: int = 180) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def scan_book(book_root: Path, *, chapter: int | None = None, min_words: int = 6,
              phrase_min: int = 4, top: int = 25) -> dict:
    chapters: list[_Chapter] = []
    for path in iter_chapter_files(book_root / "chapters"):
        try:
            num = int(path.stem.split("_")[-1])
        except ValueError:
            continue
        raw = path.read_text(encoding="utf-8")
        chapters.append(_Chapter(num=num, file=path.name, raw=raw,
                                 words=len(strip_yaml_frontmatter(raw).split())))
    toks, sentences = _tokenise(chapters)
    common = _common_words(toks, 0.0015)
    names = _names(toks)
    echoes = _echoes(toks, chapters, common, min_words)
    phrases = _phrases(toks, chapters, common, names, phrase_min)
    # Sentences are short, so the similar-sentence test sets aside fewer of
    # the book's common words, and asks for a longer word in common.
    similar = _similar(toks, sentences, chapters, _common_words(toks, 0.0025), names, top)

    rows = []
    for ch in chapters:
        if chapter is not None and ch.num != chapter:
            continue
        mine = [e for e in echoes if ch.num in e["chapters"]]
        rows.append({
            "chapter": ch.num,
            "file": ch.file,
            "words": ch.words,
            "echoes_within": sum(1 for e in mine if e["same_chapter"]
                                 and sum(p["chapter"] == ch.num for p in e["places"]) > 1),
            "echoes_across": sum(1 for e in mine if e["across_chapters"]),
            "phrases": phrases.get(ch.num, []),
            "similar_sentences": similar.get(ch.num, []),
        })
    if chapter is not None:
        echoes = [e for e in echoes if chapter in e["chapters"]]
    return {
        "book_root": str(book_root),
        "chapters_scanned": [c.num for c in chapters],
        "min_words": min_words,
        "phrase_min": phrase_min,
        "common_words": len(common),
        "line_numbers": "lines in the chapter file, frontmatter included (as file_read shows them)",
        "echoes": echoes[:max(top * 4, 100)] if chapter is None else echoes,
        "chapters": rows,
        "note": ("Candidates only. An echo is the same wording at two or more places; a "
                 "phrase is a short phrase a chapter leans on; a similar pair is two "
                 "sentences sharing most of their uncommon words. Each is repetition unless "
                 "it is a deliberate echo (a payoff line, a letter quoted again, a refrain "
                 "the book sets up). Say each thing once, where it first matters; a later "
                 "mention is at most a clause, after a long absence. The scan cannot see "
                 "the same point made in different words: read for that too."),
    }


def render_markdown(report: dict) -> str:
    lines = ["# Things said more than once", "", report["note"], "",
             f"Lines are {report['line_numbers']}.", ""]
    echoes = report["echoes"]
    lines.append(f"## Echoes: the same {report['min_words']}+ words at two or more places "
                 f"({len(echoes)})")
    lines.append("")
    for e in echoes:
        where = ", ".join(f"ch {p['chapter']}:{p['line']}" for p in e["places"])
        lines.append(f"- “{e['text']}” — {where}")
    lines.append("")
    for ch in report["chapters"]:
        lines.append(f"## Chapter {ch['chapter']} ({ch['words']:,} words) — "
                     f"{ch['echoes_within']} echoes inside it, {ch['echoes_across']} with "
                     f"other chapters")
        if ch["phrases"]:
            lines.append("- phrases leaned on: " + "; ".join(
                f"“{p['phrase']}” ×{p['count']} (lines {', '.join(map(str, p['lines']))})"
                for p in ch["phrases"]))
        for s in ch["similar_sentences"]:
            lines.append(f"- lines {s['lines'][0]} and {s['lines'][1]} share "
                         f"{', '.join(s['shared'])}: “{s['first']}” / “{s['second']}”")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
