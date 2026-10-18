"""Candidate narrator flash-forwards (prolepsis), per chapter.

`autonovel mechanical prolepsis <book_dir>` lists sentences in which the
narration reaches past the chapter's own story time: a year later than
the chapter's `story_time` upper bound next to a future-in-the-past
marker ("would", "was to", "later"…), or a relative jump ("thirty years
later", "for the rest of his life"). Quoted dialogue is ignored; a
character may predict, the count is about the narrator.

Why it exists: on *kingmaker* an editor's full read traced the book's
"string of anecdotes" feel mostly to flash-forwards in 19 of 24
chapters. Each one moves the reader from inside the scene to the end of
the life looking back, and spends the suspense the scene has built.
The reviewers never counted them; `/autonovel:developmental-edit`
does, and this helper is its counter.

This is a candidate generator, not a gate (author rule: no brittle
regex quality gates). It over-reports (a character's backstory in
"would" mood, a year inside a quoted letter) and under-reports
(prolepsis without a year or a stock phrase). The editor reads every
candidate in its paragraph and keeps the real ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..paths import iter_chapter_files
from .frontmatter import strip_yaml_frontmatter

_YEAR = re.compile(r"\b(1[0-9]\d\d|20\d\d)\b")
_FUTURE_MARKER = re.compile(
    r"\b(?:would|was to|were to|later|afterwards|thereafter|by then|"
    r"one day|in time|until (?:his|her|their) death)\b|\b\w+['\u2019]d\b",
    re.IGNORECASE,
)
_RELATIVE_JUMP = re.compile(
    r"\b(?:\w+|\d+)[- ]years? later\b|\bdecades? later\b|"
    r"\bfor the rest of (?:his|her|their) li(?:fe|ves)\b|"
    r"\b(?:his|her|their) whole life long\b",
    re.IGNORECASE,
)
# Straight or curly double quotes; dialogue is the characters' talk.
_DIALOGUE = re.compile(r"“[^”]*”|\"[^\"\n]*\"")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(])")
_STORY_TIME = re.compile(r"^story_time:\s*(.+)$", re.MULTILINE)
_CHAPTER = re.compile(r"^chapter:\s*(\d+)", re.MULTILINE)


@dataclass
class Candidate:
    sentence: str
    reason: str          # "year 1519 with 'would'" | "relative jump"
    year: int | None = None

    def to_dict(self) -> dict:
        return {"sentence": self.sentence, "reason": self.reason, "year": self.year}


@dataclass
class ChapterProlepsis:
    chapter: int
    file: str
    story_time: str | None
    story_time_end_year: int | None
    candidates: list[Candidate] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "file": self.file,
            "story_time": self.story_time,
            "story_time_end_year": self.story_time_end_year,
            "candidates": [c.to_dict() for c in self.candidates],
        }


def _end_year(story_time: str | None) -> int | None:
    if not story_time:
        return None
    years = [int(y) for y in _YEAR.findall(story_time)]
    return max(years) if years else None


def scan_text(body: str, end_year: int | None) -> list[Candidate]:
    """Candidates in one chapter body (frontmatter already stripped)."""
    out: list[Candidate] = []
    for para in re.split(r"\n\s*\n", body):
        narration = _DIALOGUE.sub(" ", para).strip()
        if not narration or narration.startswith(("#", "*" * 3)):
            continue
        for sent in _SENTENCE_SPLIT.split(narration):
            s = " ".join(sent.split())
            if not s:
                continue
            years = [int(y) for y in _YEAR.findall(s)]
            later = [y for y in years if end_year is not None and y > end_year]
            if _RELATIVE_JUMP.search(s):
                # "In March 1485, six years later, …" inside a chapter that
                # runs to 1485 is a scene jump, not a flash-forward.
                if end_year is not None and years and not later:
                    continue
                out.append(Candidate(sentence=s, reason="relative jump",
                                     year=later[0] if later else None))
                continue
            if end_year is None:
                continue
            marker = _FUTURE_MARKER.search(s)
            if later and marker:
                out.append(Candidate(
                    sentence=s,
                    reason=f"year {later[0]} with '{marker.group(0)}'",
                    year=later[0]))
    return out


def scan_book(book_root: Path) -> dict:
    chapters: list[ChapterProlepsis] = []
    for path in iter_chapter_files(book_root / "chapters"):
        text = path.read_text(encoding="utf-8")
        m_st = _STORY_TIME.search(text.split("\n---", 1)[0] if text.startswith("---") else "")
        story_time = m_st.group(1).strip() if m_st else None
        m_ch = _CHAPTER.search(text)
        try:
            num = int(m_ch.group(1)) if m_ch else int(path.stem.split("_")[-1])
        except ValueError:
            continue
        cp = ChapterProlepsis(
            chapter=num, file=path.name, story_time=story_time,
            story_time_end_year=_end_year(story_time))
        cp.candidates = scan_text(strip_yaml_frontmatter(text), cp.story_time_end_year)
        chapters.append(cp)
    with_hits = [c.chapter for c in chapters if c.candidates]
    return {
        "book_root": str(book_root),
        "chapter_count": len(chapters),
        "chapters_with_candidates": with_hits,
        "candidate_count": sum(len(c.candidates) for c in chapters),
        "chapters": [c.to_dict() for c in chapters],
        "note": ("Candidates only: read each sentence in its paragraph and keep the "
                 "narrator flash-forwards. A character's prediction in dialogue is "
                 "excluded; a year inside a quoted letter may still appear."),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Prolepsis candidates (narrator flash-forwards)",
        "",
        f"{len(report['chapters_with_candidates'])} of {report['chapter_count']} chapters, "
        f"{report['candidate_count']} candidate sentence(s). {report['note']}",
        "",
    ]
    for ch in report["chapters"]:
        if not ch["candidates"]:
            continue
        lines.append(f"## Chapter {ch['chapter']} ({ch['story_time'] or 'no story_time'})")
        for c in ch["candidates"]:
            lines.append(f"- *{c['reason']}*: {c['sentence']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
