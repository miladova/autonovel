"""Register scanner — structural markers of prose register, per chapter.

Why this exists (2026-10-14). A plain-register historical thriller kept
reading as "1500s style" to its author after three revision passes,
and the pipeline's judge never caught it. The vocabulary was modern;
the GRAMMAR was formal: narration that never contracted a negative
(27 "did not" to 0 "didn't" in one chapter), "whether" for "if",
"perhaps" for "maybe", fronted objects, elliptical participles, and
dialogue in which a character explained to the listener things the
listener could see ("That's San Giacomo's bell, at the end there").
Word-list scanners (period-bans, slop) cannot see any of that, and the
LLM judge shares the writer's defaults. This scanner measures the
markers the register literature actually uses (Biber's involved vs
informational dimension; Flesch-Kincaid grade; utterance length) and
surfaces line-level CANDIDATES. It does not score; the book's voice.md
declares the band and the judge in `/autonovel:evaluate` decides.

Per chapter it reports, separately for NARRATION (text outside quotes)
and DIALOGUE (text inside double quotes):

  - word counts and share;
  - Flesch-Kincaid grade (narration, dialogue, whole);
  - mean sentence length in narration;
  - contractions vs uncontracted negatives in narration, with the
    uncontracted ones listed (line + snippet);
  - formal-connective / formal-tag candidates in narration (whether,
    perhaps, upon, thus, whilst, amid, moreover, nevertheless,
    scarcely, ought, "put in that", remarked, observed, inquired);
  - fronted-object openers ("That part Jakob had decided …") and
    elliptical participles ("watched it hung") as candidates;
  - dialogue utterances: count, mean words per utterance, and the
    long ones (over `long_utterance` words, default 40);
  - "explaining to the listener" candidates: utterances that name
    where the speaker and listener are standing, what the listener
    can see, or what the listener already knows ("that's the …",
    "over there", "at the end there", "as you know", "you know
    about", "you can see", "this is the", "here we have").

Everything here is a candidate generator, never a gate (project rule).
The narration/dialogue split is by straight double quotes, which is
the pipeline's house style; curly quotes are normalised first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .period_register import flesch_kincaid_grade
from ..paths import iter_chapter_files

_QUOTE_RE = re.compile(r'"([^"\n]*)"')
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

UNCONTRACTED_NEGATIVES = (
    "did not", "could not", "was not", "were not", "had not", "would not",
    "is not", "are not", "does not", "do not", "has not", "have not",
    "will not", "cannot", "can not", "should not", "must not", "need not",
)
CONTRACTION_RE = re.compile(r"\b\w+n't\b|\b\w+'(?:d|ll|re|ve|m)\b|\bit's\b|\bthat's\b|\bthere's\b|\bhe's\b|\bshe's\b|\bwhat's\b|\bwho's\b|\blet's\b", re.IGNORECASE)

FORMAL_CONNECTIVES = (
    "whether", "perhaps", "upon", "thus", "hence", "whilst", "amid",
    "amidst", "moreover", "nevertheless", "nonetheless", "scarcely",
    "ought", "henceforth", "whereupon", "forthwith",
)
FORMAL_TAGS = (
    "put in that", "remarked", "observed that", "inquired", "enquired",
    "opined", "interjected", "rejoined", "averred",
)
LISTENER_EXPLAINING = (
    r"\bthat's the\b", r"\bthat is the\b", r"\bover there\b",
    r"\bat the end there\b", r"\bas you know\b", r"\byou know about\b",
    r"\byou can see\b", r"\bthis is the\b", r"\bhere we have\b",
    r"\bthat building\b", r"\bthe one you\b", r"\byou'll have noticed\b",
    r"\byou've seen\b",
)

_UNCONTR_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in UNCONTRACTED_NEGATIVES) + r")\b", re.IGNORECASE)
_FORMAL_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in FORMAL_CONNECTIVES + FORMAL_TAGS) + r")\b", re.IGNORECASE)
_FRONTED_RE = re.compile(r"(?:^|(?<=[.!?]\s))(That|This|Those|These) \w+ (?:[A-Z]\w+|he|she|they) (?:had|would|could|did)\b")
_ELLIPTICAL_RE = re.compile(r"\b(?:watched|saw|heard|felt) (?:it|them|him|her) (?:hung|tagged|carried|taken|counted|read|weighed|written|brought|done)\b", re.IGNORECASE)
_LISTENER_RE = re.compile("|".join(LISTENER_EXPLAINING), re.IGNORECASE)


@dataclass
class Candidate:
    kind: str          # uncontracted-negative | formal | fronted | elliptical | long-utterance | listener-explaining
    line_no: int
    match: str
    snippet: str


@dataclass
class ChapterRegister:
    chapter: int
    words: int
    narration_words: int
    dialogue_words: int
    fk_overall: float | None
    fk_narration: float | None
    fk_dialogue: float | None
    narration_mean_sentence_words: float | None
    contractions: int
    uncontracted_negatives: int
    utterances: int
    mean_utterance_words: float | None
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def dialogue_share(self) -> float:
        return round(self.dialogue_words / self.words, 3) if self.words else 0.0

    @property
    def contraction_ratio(self) -> float | None:
        total = self.contractions + self.uncontracted_negatives
        return round(self.contractions / total, 2) if total else None

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "words": self.words,
            "narration_words": self.narration_words,
            "dialogue_words": self.dialogue_words,
            "dialogue_share": self.dialogue_share,
            "fk_overall": self.fk_overall,
            "fk_narration": self.fk_narration,
            "fk_dialogue": self.fk_dialogue,
            "narration_mean_sentence_words": self.narration_mean_sentence_words,
            "contractions": self.contractions,
            "uncontracted_negatives": self.uncontracted_negatives,
            "contraction_ratio": self.contraction_ratio,
            "utterances": self.utterances,
            "mean_utterance_words": self.mean_utterance_words,
            "candidates": [
                {"kind": c.kind, "line_no": c.line_no, "match": c.match, "snippet": c.snippet}
                for c in self.candidates
            ],
        }


@dataclass
class RegisterReport:
    chapters: list[ChapterRegister]
    long_utterance: int

    def to_dict(self) -> dict:
        return {"long_utterance": self.long_utterance,
                "chapters": [c.to_dict() for c in self.chapters]}


def _normalise_quotes(text: str) -> str:
    return (text.replace("“", '"').replace("”", '"')
                .replace("‘", "'").replace("’", "'"))


def _snippet(line: str, start: int, *, window: int = 60) -> str:
    lo = max(0, start - window)
    hi = min(len(line), start + window)
    out = line[lo:hi]
    if lo > 0:
        out = "…" + out
    if hi < len(line):
        out = out + "…"
    return out.strip()


def _mean_sentence_words(text: str) -> float | None:
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if _WORD_RE.search(s)]
    if not sentences:
        return None
    return round(sum(len(_WORD_RE.findall(s)) for s in sentences) / len(sentences), 1)


def scan_chapter(text: str, *, chapter: int = 1, long_utterance: int = 40) -> ChapterRegister:
    body = _normalise_quotes(strip_yaml_frontmatter(text))
    lines = body.splitlines()

    dialogue_parts: list[str] = []
    narration_lines: list[tuple[int, str]] = []
    candidates: list[Candidate] = []
    utterance_lengths: list[int] = []

    for line_no, line in enumerate(lines, start=1):
        if line.strip() == "***":
            continue
        for m in _QUOTE_RE.finditer(line):
            utt = m.group(1)
            dialogue_parts.append(utt)
            n = len(_WORD_RE.findall(utt))
            if n:
                utterance_lengths.append(n)
            if n > long_utterance:
                candidates.append(Candidate("long-utterance", line_no, f"{n} words", _snippet(line, m.start())))
            lm = _LISTENER_RE.search(utt)
            if lm:
                candidates.append(Candidate("listener-explaining", line_no, lm.group(0), _snippet(line, m.start() + lm.start())))
        narr = _QUOTE_RE.sub(" ", line)
        if _WORD_RE.search(narr):
            narration_lines.append((line_no, narr))

    narration_text = "\n".join(n for _, n in narration_lines)
    dialogue_text = " ".join(dialogue_parts)

    contractions = 0
    uncontracted = 0
    for line_no, narr in narration_lines:
        contractions += len(CONTRACTION_RE.findall(narr))
        for m in _UNCONTR_RE.finditer(narr):
            uncontracted += 1
            candidates.append(Candidate("uncontracted-negative", line_no, m.group(0), _snippet(narr, m.start())))
        for m in _FORMAL_RE.finditer(narr):
            candidates.append(Candidate("formal", line_no, m.group(0), _snippet(narr, m.start())))
        for m in _FRONTED_RE.finditer(narr):
            candidates.append(Candidate("fronted", line_no, m.group(0), _snippet(narr, m.start())))
        for m in _ELLIPTICAL_RE.finditer(narr):
            candidates.append(Candidate("elliptical", line_no, m.group(0), _snippet(narr, m.start())))

    candidates.sort(key=lambda c: (c.line_no, c.kind))
    words = len(_WORD_RE.findall(body))
    nw = len(_WORD_RE.findall(narration_text))
    dw = len(_WORD_RE.findall(dialogue_text))
    return ChapterRegister(
        chapter=chapter,
        words=words,
        narration_words=nw,
        dialogue_words=dw,
        fk_overall=flesch_kincaid_grade(body),
        fk_narration=flesch_kincaid_grade(narration_text),
        fk_dialogue=flesch_kincaid_grade(dialogue_text),
        narration_mean_sentence_words=_mean_sentence_words(narration_text),
        contractions=contractions,
        uncontracted_negatives=uncontracted,
        utterances=len(utterance_lengths),
        mean_utterance_words=(round(sum(utterance_lengths) / len(utterance_lengths), 1)
                              if utterance_lengths else None),
        candidates=candidates,
    )


def build_report(book_root: Path, *, long_utterance: int = 40,
                 chapter: int | None = None) -> RegisterReport:
    chapters: list[ChapterRegister] = []
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        n = int(m.group(1))
        if chapter is not None and n != chapter:
            continue
        chapters.append(scan_chapter(path.read_text(encoding="utf-8"),
                                     chapter=n, long_utterance=long_utterance))
    chapters.sort(key=lambda c: c.chapter)
    return RegisterReport(chapters=chapters, long_utterance=long_utterance)


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:g}"


def render_markdown(report: RegisterReport, *, book: str | None = None,
                    show_hits: bool = True) -> str:
    parts: list[str] = [f"# Register scan — {book}" if book else "# Register scan", ""]
    if not report.chapters:
        parts.append("_No chapters drafted yet._")
        return "\n".join(parts) + "\n"
    parts.append(
        "_Structural register markers, narration and dialogue measured "
        "separately. Candidates are a review queue, not a gate: the book's "
        "voice.md declares the band and the judge in `/autonovel:evaluate` "
        "decides. FK = Flesch-Kincaid grade; contraction ratio = contractions "
        "/ (contractions + uncontracted negatives) in narration._")
    parts.append("")
    parts.append("| Ch | Words | Dlg % | FK narr | FK dlg | Narr sent. len | Contr. ratio | Uncontr. neg. | Utterances | Mean utt. | Candidates |")
    parts.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for c in report.chapters:
        parts.append(
            f"| {c.chapter} | {c.words} | {round(100 * c.dialogue_share)} | {_fmt(c.fk_narration)} | "
            f"{_fmt(c.fk_dialogue)} | {_fmt(c.narration_mean_sentence_words)} | {_fmt(c.contraction_ratio)} | "
            f"{c.uncontracted_negatives} | {c.utterances} | {_fmt(c.mean_utterance_words)} | {len(c.candidates)} |")
    if show_hits:
        for c in report.chapters:
            if not c.candidates:
                continue
            parts.append("")
            parts.append(f"## Chapter {c.chapter}")
            for h in c.candidates:
                parts.append(f"- L{h.line_no} `{h.kind}` **{h.match}** — {h.snippet}")
    return "\n".join(parts) + "\n"
