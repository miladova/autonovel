"""POV-bleed heuristic scanner.

Close-third POV is the convention for most autonovel drafts. The
classic AI failure mode is bleeding into omniscient: a line in
chapter N narrates what character X *thought*, *felt*, or *knew*,
where X is not the POV character — i.e. the narrator is reaching
inside a head the POV can't reach.

This scanner is a pure-mechanical first pass. It surfaces lines
matching `<NameOfNonPOV> + <interiority verb>` and counts them per
chapter. The LLM judge in `/autonovel:evaluate` already scores
this implicitly under `voice_adherence`; the scanner gives a fast,
free pre-flight so the user can revise before paying for an eval.

Inputs:
- The chapter file (frontmatter `pov:` field is the authoritative
  POV character for that chapter).
- A cast list — usually parsed from `shared/characters.md` or
  passed explicitly. Without a cast, every capitalised name in
  the prose is a candidate; that's noisy. The CLI / slash-command
  reads `shared/characters.md` and extracts named entities.

What's flagged:
- `<Name> thought ...`
- `<Name> felt ...`
- `<Name> knew ...`
- `<Name> realised ...` / `realized ...`
- `<Name> wondered ...`
- `<Name> remembered ...`
- `<Name> hoped ...`
- `<Name> feared ...`
- `<Name> believed ...`
- `<Name>'s mind / heart / thoughts ...`
- `<Name> wanted to ...` (interior desire)
- `<Name> didn't realise ...`

What's NOT flagged:
- Direct dialogue tags ("said", "asked", "replied" — those are
  observed-from-outside).
- Past-tense constructions describing observable behaviour
  ("Lucia walked to the door").
- POV's own name + interiority (the convention).
- Names not in the supplied cast.

False-positive caveat: a non-POV character can legitimately have
their interiority reported by another character ("Niccolò
believed, Lucia could see, that ..."). The scanner can't tell.
The output is a *suggestion list* for human review, not a hard
gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from ..paths import iter_chapter_files


# Interiority verbs that read as POV bleed when applied to a
# non-POV character. The list is intentionally conservative — we'd
# rather miss a real bleed than spam every line with "Niccolò
# nodded" false positives.
INTERIORITY_VERBS = {
    "thought", "felt", "knew", "realised", "realized", "wondered",
    "remembered", "recalled", "imagined", "considered", "supposed",
    "believed", "doubted", "hoped", "feared", "longed", "yearned",
    "wished", "decided", "understood", "recognised", "recognized",
    "noticed", "sensed", "noted",
}

# Possessive-attached interiority nouns: `Niccolò's mind`,
# `Lucia's heart`, etc.
INTERIORITY_NOUNS = {
    "mind", "thoughts", "heart", "soul", "feelings", "emotions",
    "memory", "memories", "desires", "fears", "hopes", "dread",
    "anguish", "joy", "longing",
}


@dataclass
class PovBleedHit:
    chapter: int
    line_no: int
    name: str
    pattern: str  # "verb" | "possessive"
    verb_or_noun: str
    snippet: str


@dataclass
class ChapterReport:
    chapter: int
    pov: str | None
    word_count: int
    hits: list[PovBleedHit] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.hits)


@dataclass
class PovBleedReport:
    cast_size: int
    chapters: list[ChapterReport]

    def to_dict(self) -> dict:
        return {
            "cast_size": self.cast_size,
            "chapters": [
                {
                    "chapter": c.chapter,
                    "pov": c.pov,
                    "word_count": c.word_count,
                    "total": c.total,
                    "hits": [
                        {"line_no": h.line_no, "name": h.name,
                         "pattern": h.pattern,
                         "verb_or_noun": h.verb_or_noun,
                         "snippet": h.snippet}
                        for h in c.hits
                    ],
                }
                for c in self.chapters
            ],
        }


# ---------------------------------------------------------- cast parsing


_CAST_NAME_RE = re.compile(r"^[\s\-\*]*\*\*([^*]+)\*\*", re.MULTILINE)
_CAST_HEADING_RE = re.compile(r"^#{2,3}\s+([^\n#]+?)\s*$", re.MULTILINE)


def parse_cast(characters_md: Path) -> set[str]:
    """Extract named entities from `shared/characters.md`. Honours
    two common shapes: `**Name** — role` bullet form, and `## Name`
    heading form. Returns a set of names."""
    return set(parse_cast_ordered(characters_md))


def parse_cast_ordered(characters_md: Path) -> list[str]:
    """Same extraction as `parse_cast`, in document order and
    de-duplicated — for surfaces (the story map) where the order the
    author listed the cast in is meaningful (principals first)."""
    if not characters_md.is_file():
        return []
    text = characters_md.read_text(encoding="utf-8")
    found: list[tuple[int, str]] = []
    for regex in (_CAST_NAME_RE, _CAST_HEADING_RE):
        for m in regex.finditer(text):
            n = m.group(1).strip()
            if n and len(n) >= 2 and n[0].isupper():
                found.append((m.start(),
                              n.split(" — ")[0].split(",")[0].strip()))
    out: list[str] = []
    for _pos, name in sorted(found):
        if name and name not in out:
            out.append(name)
    return out


# ---------------------------------------------------------- scan


def _frontmatter_field(text: str, key: str) -> str | None:
    if not text.startswith("---"):
        return None
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def scan_chapter(text: str, *, cast: set[str], chapter: int = 1,
                  pov: str | None = None) -> ChapterReport:
    pov = pov or _frontmatter_field(text, "pov")
    body = strip_yaml_frontmatter(text)
    word_count = len(re.findall(r"\b\w+\b", body))
    hits: list[PovBleedHit] = []
    if not cast:
        return ChapterReport(chapter=chapter, pov=pov,
                              word_count=word_count, hits=hits)
    pov_first = pov.split()[0] if pov else None

    # Build a regex alternation of cast first names, longest-first
    # so multi-word names are preferred.
    candidates = sorted(
        (n for n in cast if n and (pov_first is None or n != pov_first
                                     and not n.startswith(pov_first or ""))),
        key=len, reverse=True,
    )
    if not candidates:
        return ChapterReport(chapter=chapter, pov=pov,
                              word_count=word_count, hits=hits)
    name_alt = "|".join(re.escape(n) for n in candidates)

    # Verb pattern: `<Name> <interiority verb>`.
    verb_alt = "|".join(re.escape(v) for v in INTERIORITY_VERBS)
    verb_re = re.compile(
        rf"\b(?P<name>{name_alt})\b\s+(?P<verb>{verb_alt})\b",
    )
    # Possessive pattern: `<Name>'s <interiority noun>`.
    noun_alt = "|".join(re.escape(n) for n in INTERIORITY_NOUNS)
    poss_re = re.compile(
        rf"\b(?P<name>{name_alt})'s\s+(?P<noun>{noun_alt})\b",
    )

    for line_no, line in enumerate(body.splitlines(), start=1):
        for m in verb_re.finditer(line):
            hits.append(PovBleedHit(
                chapter=chapter, line_no=line_no,
                name=m.group("name"), pattern="verb",
                verb_or_noun=m.group("verb"),
                snippet=_snippet(line, m.start()),
            ))
        for m in poss_re.finditer(line):
            hits.append(PovBleedHit(
                chapter=chapter, line_no=line_no,
                name=m.group("name"), pattern="possessive",
                verb_or_noun=m.group("noun"),
                snippet=_snippet(line, m.start()),
            ))
    return ChapterReport(chapter=chapter, pov=pov, word_count=word_count,
                          hits=hits)


def build_report(book_root: Path, *, series_root: Path | None = None,
                  cast_override: set[str] | None = None) -> PovBleedReport:
    series = series_root if series_root is not None else book_root.parent.parent
    cast = cast_override if cast_override is not None else parse_cast(
        series / "shared" / "characters.md"
    )
    chapters: list[ChapterReport] = []
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        chapters.append(scan_chapter(text, cast=cast, chapter=int(m.group(1))))
    chapters.sort(key=lambda c: c.chapter)
    return PovBleedReport(cast_size=len(cast), chapters=chapters)


def _snippet(line: str, start: int, *, window: int = 50) -> str:
    lo = max(0, start - window)
    hi = min(len(line), start + window)
    out = line[lo:hi]
    if lo > 0:
        out = "…" + out
    if hi < len(line):
        out = out + "…"
    return out.strip()


# ---------------------------------------------------------- render


def render_markdown(report: PovBleedReport, *, book: str | None = None,
                     show_hits: bool = True) -> str:
    parts: list[str] = []
    parts.append(f"# POV bleed scan — {book}" if book
                  else "# POV bleed scan")
    parts.append("")
    if report.cast_size == 0:
        parts.append(
            "_No cast loaded. Populate `shared/characters.md` "
            "with `**Name**` or `## Name` entries to enable scanning._"
        )
        return "\n".join(parts) + "\n"
    parts.append(f"_cast loaded: {report.cast_size} characters_")
    if not report.chapters:
        parts.append("")
        parts.append("_No chapters drafted yet._")
        return "\n".join(parts) + "\n"
    parts.append("")
    parts.append("| Ch | POV | Words | Suspect lines |")
    parts.append("|---|---|---|---|")
    for c in report.chapters:
        parts.append(
            f"| {c.chapter} | {c.pov or '—'} | {c.word_count} | "
            f"{c.total if c.total else '·'} |"
        )
    if show_hits:
        for c in report.chapters:
            if not c.hits:
                continue
            parts.append("")
            parts.append(f"## Chapter {c.chapter} (POV: {c.pov or 'unknown'})")
            parts.append(
                f"_Note: false positives are common — a non-POV character's "
                f"interiority can be legitimately reported by another "
                f"character. Treat as a review list, not a gate._"
            )
            parts.append("")
            for h in c.hits:
                parts.append(
                    f"- L{h.line_no} `{h.name} {h.verb_or_noun}` "
                    f"({h.pattern}): {h.snippet}"
                )
    return "\n".join(parts) + "\n"
