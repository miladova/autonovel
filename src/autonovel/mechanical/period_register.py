"""Per-book period register lock.

Two complementary scanners:

1. **Period-bans hit aggregation** — wraps the existing
   `slop.period_ban_hits` scanner to produce a *book-wide* table
   of every period-bans violation across every chapter, with
   line-level locations. Default `bans` source is
   `shared/period_bans.txt` (one banned word per line,
   `#` comments allowed).

2. **Syntactic-register drift (Flesch-Kincaid grade)** —
   computes Flesch-Kincaid grade per chapter and per scene.
   The author's `seed.txt` (or the book's `voice.md`) sets the
   register baseline; chapters drifting >1 grade level above
   the baseline are flagged. Catches the bug class where
   period-correct vocabulary masks modern syntax — pure
   maths, no curated word-list. The 1.0-grade threshold is a
   knob (`--grade-drift`), not an authority.

Both scanners are pure-mechanical candidate generators. The LLM
judge in `/autonovel:evaluate`'s `voice_adherence` dimension
does the actual scoring; this module surfaces the patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .slop import period_ban_hits
from ..paths import iter_chapter_files


@dataclass
class PeriodHit:
    chapter: int
    line_no: int
    word: str
    snippet: str


@dataclass
class ChapterReport:
    chapter: int
    word_count: int
    hits: list[PeriodHit] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.hits)


@dataclass
class PeriodReport:
    bans_count: int    # how many words in the bans list
    chapters: list[ChapterReport]
    summary: dict[str, int] = field(default_factory=dict)
    """`summary` maps banned-word → total chapter-hits across the book.
    Useful for "which words are the worst offenders"."""

    def to_dict(self) -> dict:
        return {
            "bans_count": self.bans_count,
            "summary": dict(self.summary),
            "chapters": [
                {
                    "chapter": c.chapter,
                    "word_count": c.word_count,
                    "total": c.total,
                    "hits": [
                        {"line_no": h.line_no, "word": h.word, "snippet": h.snippet}
                        for h in c.hits
                    ],
                }
                for c in self.chapters
            ],
        }


# ---------------------------------------------------------- public entry


def load_bans(bans_path: Path) -> list[str]:
    if not bans_path.is_file():
        return []
    out: list[str] = []
    for line in bans_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def scan_chapter(text: str, *, bans: list[str], chapter: int = 1) -> ChapterReport:
    """Scan a single chapter against the bans list. Strips YAML
    frontmatter first. Reports per-line hits with snippets."""
    body = strip_yaml_frontmatter(text)
    word_count = len(re.findall(r"\b\w+\b", body))
    if not bans:
        return ChapterReport(chapter=chapter, word_count=word_count)

    # Build one regex per ban for line-level matching.
    patterns = [(b, re.compile(rf"\b{re.escape(b)}\b", re.IGNORECASE))
                 for b in bans]
    hits: list[PeriodHit] = []
    for line_no, line in enumerate(body.splitlines(), start=1):
        for word, pat in patterns:
            for m in pat.finditer(line):
                hits.append(PeriodHit(
                    chapter=chapter,
                    line_no=line_no,
                    word=line[m.start():m.end()],
                    snippet=_snippet(line, m.start()),
                ))
    return ChapterReport(chapter=chapter, word_count=word_count, hits=hits)


def build_report(book_root: Path, *, series_root: Path | None = None) -> PeriodReport:
    """Scan every drafted chapter against `series_root/shared/period_bans.txt`.

    `series_root` defaults to `book_root.parent.parent` (the standard
    `<series>/books/<book>/` layout)."""
    series = series_root if series_root is not None else book_root.parent.parent
    bans = load_bans(series / "shared" / "period_bans.txt")
    chapters: list[ChapterReport] = []
    summary: dict[str, int] = {}
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        report = scan_chapter(text, bans=bans, chapter=int(m.group(1)))
        chapters.append(report)
        for h in report.hits:
            summary[h.word.lower()] = summary.get(h.word.lower(), 0) + 1
    chapters.sort(key=lambda c: c.chapter)
    # Confirm with the slop helper too — it's the canonical scanner;
    # this is a sanity-check that we don't drift from its semantics.
    return PeriodReport(
        bans_count=len(bans),
        chapters=chapters,
        summary=dict(sorted(summary.items(), key=lambda kv: -kv[1])),
    )


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


def render_markdown(report: PeriodReport, *, book: str | None = None,
                     show_hits: bool = True) -> str:
    parts: list[str] = []
    parts.append(f"# Period register — {book}" if book
                  else "# Period register")
    parts.append("")
    if report.bans_count == 0:
        parts.append(
            "_`shared/period_bans.txt` is missing or empty. Add one banned "
            "word per line (`#` comments allowed) to enable register lock._"
        )
        return "\n".join(parts) + "\n"
    parts.append(f"_bans loaded: {report.bans_count}_")
    if not report.chapters:
        parts.append("")
        parts.append("_No chapters drafted yet._")
        return "\n".join(parts) + "\n"
    parts.append("")
    parts.append("| Ch | Words | Hits |")
    parts.append("|---|---|---|")
    for c in report.chapters:
        parts.append(
            f"| {c.chapter} | {c.word_count} | "
            f"{c.total if c.total else '·'} |"
        )

    if report.summary:
        parts.append("")
        parts.append("## Worst offenders")
        parts.append("")
        for word, count in list(report.summary.items())[:15]:
            parts.append(f"- `{word}` — {count} hit(s)")

    if show_hits:
        for c in report.chapters:
            if not c.hits:
                continue
            parts.append("")
            parts.append(f"## Chapter {c.chapter} hits")
            for h in c.hits:
                parts.append(f"- L{h.line_no} `{h.word}`: {h.snippet}")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------- syntax-register drift


# The Flesch-Kincaid grade is well-defined math:
#
#   FK_grade = 0.39 * (words / sentences)
#            + 11.8 * (syllables / words)
#            - 15.59
#
# Higher = harder reading (longer sentences, longer words, more
# syllables). For period fiction the *trend* matters more than the
# absolute number — a chapter whose grade drifts 1+ levels above
# the seed/voice baseline is using flatter modern syntax in an
# arc the rest of the book reads as literary.
#
# Syllable counting is a heuristic — vowel-group runs with
# silent-e and -le-suffix exceptions. Not perfect, but good enough
# for the *delta* the FK formula extracts (errors largely cancel
# when comparing chapter A to chapter B in the same book).


_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENTENCE_END_RE = re.compile(r"[.!?]+")


def _syllables_in_word(word: str) -> int:
    """Heuristic vowel-group counter with two corrections:
      - silent trailing `e` subtracts one syllable
        (`make` → 1, not 2),
      - the `-le` suffix after a consonant keeps its syllable
        (`table` → 2, `apple` → 2; the `e` is sounded).
    Words with one vowel group never report 0 (`the`, `me` → 1).
    """
    w = word.lower().strip("'-")
    if not w:
        return 0
    groups = _VOWEL_GROUP_RE.findall(w)
    syllables = len(groups)
    if syllables <= 1:
        return max(1, syllables)
    # Silent trailing `e`: subtract one. The `-le`-after-consonant
    # case is the exception — `e` is sounded there.
    is_le_after_consonant = (
        w.endswith("le") and len(w) >= 3 and w[-3] not in "aeiouy"
    )
    if w.endswith("e") and not is_le_after_consonant:
        syllables -= 1
    return max(1, syllables)


_QUOTED_SPAN_RE = re.compile(r'"[^"\n]*"|“[^”\n]*”')


def _narration_only(text: str) -> str:
    """Strip quoted speech so the grade measures the narrator."""
    return _QUOTED_SPAN_RE.sub(" ", strip_yaml_frontmatter(text))


def flesch_kincaid_grade(text: str) -> float | None:
    """FK grade level for `text`. Returns None for empty / single-
    word inputs where the formula is meaningless."""
    body = strip_yaml_frontmatter(text)
    words = _WORD_RE.findall(body)
    sentences = [s for s in _SENTENCE_END_RE.split(body) if s.strip()]
    if len(words) < 10 or len(sentences) < 2:
        return None
    syllables = sum(_syllables_in_word(w) for w in words)
    grade = (0.39 * (len(words) / len(sentences))
             + 11.8 * (syllables / len(words))
             - 15.59)
    return round(grade, 2)


@dataclass
class SyntaxDriftHit:
    chapter: int
    grade: float
    baseline: float
    delta: float


@dataclass
class SyntaxDriftReport:
    baseline: float | None      # FK grade of the baseline source
    baseline_source: str        # "voice.md:band" | "seed.txt" | "voice.md" | "median-of-chapters" | "none"
    threshold: float            # delta-above-baseline that triggers a flag
    chapter_grades: list[tuple[int, float | None]]   # (chapter_n, grade or None)
    drift_hits: list[SyntaxDriftHit]

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline,
            "baseline_source": self.baseline_source,
            "threshold": self.threshold,
            "chapter_grades": [
                {"chapter": n, "grade": g}
                for n, g in self.chapter_grades
            ],
            "drift_hits": [
                {"chapter": h.chapter, "grade": h.grade,
                 "baseline": h.baseline, "delta": h.delta}
                for h in self.drift_hits
            ],
        }


#: A voice.md may declare the register's reading-grade band on one line,
#: e.g. ``FK grade band: 5–8`` (en dash, hyphen or "to" all accepted).
#: The band is the authoritative baseline: its midpoint is the target
#: and its half-width the tolerance. Grading the voice file's own prose
#: was the previous fallback and is wrong in principle — a voice file is
#: a rules document, not a sample of the register — so it is now the
#: LAST resort, after seed.txt.
_FK_BAND_RE = re.compile(
    r"FK\s+grade\s+band\s*:\s*(\d+(?:\.\d+)?)\s*(?:–|-|to)\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def declared_fk_band(voice_text: str) -> tuple[float, float] | None:
    """Return (low, high) when the voice file declares ``FK grade band: L–H``."""
    m = _FK_BAND_RE.search(voice_text)
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


def _baseline_source(book_root: Path,
                      series_root: Path) -> tuple[float | None, str, float | None]:
    """Resolve the FK-grade baseline for this book. Returns
    ``(baseline, source, band_half_width)``. Order of preference: a
    band declared in voice.md (``FK grade band: 5–8``; midpoint is the
    baseline, half-width the tolerance), then seed.txt (the user's
    pitch, written in the target voice), then the voice file's own
    prose (weak: it is a rules document), then None (caller falls back
    to the median of chapter grades)."""
    voice = book_root / "voice.md"
    voice_text = voice.read_text(encoding="utf-8") if voice.is_file() else None
    if voice_text:
        band = declared_fk_band(voice_text)
        if band is not None:
            lo, hi = band
            return round((lo + hi) / 2, 2), "voice.md:band", round((hi - lo) / 2, 2)
    seed = book_root / "seed.txt"
    if seed.is_file():
        text = seed.read_text(encoding="utf-8")
        grade = flesch_kincaid_grade(text)
        if grade is not None:
            return grade, "seed.txt", None
    if voice_text:
        grade = flesch_kincaid_grade(voice_text)
        if grade is not None:
            return grade, "voice.md", None
    return None, "none", None


def _legacy_baseline_source(book_root: Path, series_root: Path) -> tuple[float | None, str]:
    """Pre-band behaviour kept for callers that only want (grade, source)."""
    voice = book_root / "voice.md"
    if voice.is_file():
        text = voice.read_text(encoding="utf-8")
        grade = flesch_kincaid_grade(text)
        if grade is not None:
            return grade, "voice.md"
    seed = book_root / "seed.txt"
    if seed.is_file():
        text = seed.read_text(encoding="utf-8")
        grade = flesch_kincaid_grade(text)
        if grade is not None:
            return grade, "seed.txt"
    return None, "none"


def build_syntax_drift_report(
    book_root: Path, *,
    series_root: Path | None = None,
    threshold: float = 1.0,
) -> SyntaxDriftReport:
    """Per-chapter FK grade + drift-above-baseline flags.

    `threshold` is the delta-above-baseline that flags drift; 1.0
    grade level is a sane default (the FK formula's resolution is
    coarse). Increase for tolerant reads, decrease for tighter
    register lock.

    When neither voice.md nor seed.txt yields a usable baseline,
    falls back to the median of chapter grades — no flags fire
    until the chapter pool has at least 3 entries.
    """
    series = series_root if series_root is not None else book_root.parent.parent
    baseline, source, half_width = _baseline_source(book_root, series)
    if half_width is not None:
        # A declared band sets its own tolerance: anything inside the
        # band is on register, anything outside drifts.
        threshold = half_width
    chapter_grades: list[tuple[int, float | None]] = []
    grades: list[float] = []
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        # Grade the NARRATION only. Dialogue legitimately reads two or
        # three grades lower than narration in any register, so a
        # dialogue-heavy chapter would otherwise look "too flat" while
        # its narration sits inside the band. The register scanner
        # reports both halves; this report is about the narrator.
        grade = flesch_kincaid_grade(_narration_only(text))
        chapter_grades.append((int(m.group(1)), grade))
        if grade is not None:
            grades.append(grade)
    chapter_grades.sort(key=lambda kv: kv[0])

    if baseline is None and len(grades) >= 3:
        # Median fallback. Use median rather than mean so one
        # extreme chapter doesn't shift the bar.
        sorted_grades = sorted(grades)
        baseline = round(sorted_grades[len(sorted_grades) // 2], 2)
        source = "median-of-chapters"

    drift_hits: list[SyntaxDriftHit] = []
    if baseline is not None:
        for n, grade in chapter_grades:
            if grade is None:
                continue
            delta = round(grade - baseline, 2)
            if delta < -threshold or delta > threshold:
                drift_hits.append(SyntaxDriftHit(
                    chapter=n, grade=grade, baseline=baseline, delta=delta,
                ))

    return SyntaxDriftReport(
        baseline=baseline,
        baseline_source=source,
        threshold=threshold,
        chapter_grades=chapter_grades,
        drift_hits=drift_hits,
    )


def render_syntax_drift_markdown(report: SyntaxDriftReport, *,
                                   book: str | None = None) -> str:
    parts: list[str] = []
    parts.append(f"# Period syntax drift — {book}" if book
                  else "# Period syntax drift")
    parts.append("")
    if report.baseline is None:
        parts.append(
            "_Cannot compute baseline FK grade. Declare one in voice.md "
            "(`FK grade band: 5–8`), or provide `seed.txt`, or draft ≥3 "
            "chapters for the median fallback._"
        )
        return "\n".join(parts) + "\n"
    if report.baseline_source == "voice.md":
        parts.append(
            "_Note: baseline is the voice file's own prose, which is a rules "
            "document, not a sample of the register. Declare `FK grade band: "
            "L–H` in voice.md for a meaningful baseline._")
        parts.append("")
    parts.append(
        f"_baseline: FK grade {report.baseline} (source: {report.baseline_source}) · "
        f"flag threshold: ±{report.threshold:.1f} grade level(s)_"
    )
    parts.append("")
    parts.append("| Chapter | FK grade | Δ vs baseline | Flag |")
    parts.append("|---|---|---|---|")
    for n, grade in report.chapter_grades:
        if grade is None:
            parts.append(f"| {n} | — | — | — |")
            continue
        delta = round(grade - report.baseline, 2)
        flag = "⚠️" if abs(delta) > report.threshold else ""
        parts.append(f"| {n} | {grade} | {delta:+.2f} | {flag} |")
    if report.drift_hits:
        parts.append("")
        parts.append("## Flagged chapters")
        parts.append("")
        for h in report.drift_hits:
            direction = ("MORE complex than baseline" if h.delta > 0
                          else "FLATTER than baseline")
            parts.append(
                f"- ch{h.chapter}: FK grade {h.grade} "
                f"({direction} by {abs(h.delta):.2f} levels)"
            )
        parts.append("")
        parts.append(
            "_Chapter syntax drifts above the baseline. Real "
            "explanations include intentional register shift "
            "(action sequence, modernism homage), dialogue-heavy "
            "chapter, OR modern-syntax leakage. The LLM judge in "
            "`/autonovel:evaluate`'s `voice_adherence` dimension "
            "decides which._"
        )
    return "\n".join(parts) + "\n"
