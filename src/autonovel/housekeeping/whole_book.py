"""The whole-book reviewers, in order, once a book is drafted.

After the outline's last chapter is drafted the pipeline's work is
book-level, and it has one order:

  1. `/autonovel:developmental-edit` — the editor's letter (read cold);
  2. `/autonovel:structure-review` — the book-level gate the letter
     compares itself with;
  3. `/autonovel:revision-pass` — on the letter's open recommendations
     and the structure review's candidates;
  4. the re-read: the structure review again (the revision made it
     stale), then the editor's second letter;
  5. `/autonovel:reader-panel` and `/autonovel:review` once the structure
     gate passes and the letter has nothing left open;
  6. `/autonovel:typeset`.

Before this the canonical next step after the last chapter was an
adversarial cut pass, then (2026-10-23) the letter and a revision pass
that offered itself again forever; no step named the structure review,
and a 19-chapter book was revised with no structure review, reader
panel or dual-persona review (kingmaker2). `gather` reads the book's
files into a `WholeBookState`; `next_whole_book_step` is the pure
decision `next_step` calls.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..paths import iter_chapter_files


@dataclass
class WholeBookState:
    letter: str = "missing"              # missing | fresh | stale (a chapter changed since)
    letter_open_chapters: list[int] = field(default_factory=list)
    structure: str = "missing"           # missing | stale | invalid | blocks | passes
    structure_chapters: list[int] = field(default_factory=list)  # its candidates' chapters
    structure_reasons: list[str] = field(default_factory=list)
    panel: str = "missing"               # missing | stale | fresh
    review: str = "missing"              # missing | stale | fresh


@dataclass
class Step:
    command: str
    rationale: str


def next_whole_book_step(book: str, s: WholeBookState) -> Step:
    """The next whole-book step for a drafted book, in the order above."""
    b = book
    if s.letter == "missing":
        return Step(f"/autonovel:developmental-edit --book {b}",
                    "the book is drafted; the editor's whole-book read comes first")
    if s.structure in ("missing", "stale", "invalid"):
        why = {"missing": "no structure review yet",
               "stale": "chapters changed since the structure review",
               "invalid": "the structure review does not validate"}[s.structure]
        return Step(f"/autonovel:structure-review --book {b}",
                    f"{why}; the book-level gate (one story or a string of episodes?) "
                    f"runs before the next revision or read")
    if s.letter == "fresh" and (s.letter_open_chapters or s.structure == "blocks"):
        chapters = sorted(set(s.letter_open_chapters) | (
            set(s.structure_chapters) if s.structure == "blocks" else set()))
        if chapters:
            what = []
            if s.letter_open_chapters:
                what.append("the editor's letter's open recommendations")
            if s.structure == "blocks":
                what.append("the structure review's candidates")
            return Step(
                f"/autonovel:revision-pass --chapters {','.join(map(str, chapters))} --book {b}",
                f"act on {' and '.join(what)}")
        return Step(f"/autonovel:revision-pass --chapters structural --book {b}",
                    "the structure gate blocks: " + "; ".join(s.structure_reasons[:2]))
    if s.letter == "stale":
        return Step(f"/autonovel:developmental-edit --book {b}",
                    "chapters changed since the editor's letter; the re-read writes the "
                    "second letter and says whether the revision did what it asked")
    if s.structure == "blocks":
        return Step(f"/autonovel:revision-pass --chapters structural --book {b}",
                    "the structure gate blocks: " + "; ".join(s.structure_reasons[:2]))
    if s.panel != "fresh":
        return Step(f"/autonovel:reader-panel --book {b}",
                    "the structure gate passes and the letter has nothing open; "
                    "four readers' reactions to the finished arc")
    if s.review != "fresh":
        return Step(f"/autonovel:review --book {b}",
                    "the dual-persona review: a critic's verdict and the stop-revising call")
    return Step(f"/autonovel:typeset --book {b}",
                "every whole-book reviewer is current; typeset the manuscript")


# ------------------------------------------------------------------ gather

_LEDGER_HEAD_RE = re.compile(r"^##\s+Recommendations ledger\s*$", re.MULTILINE | re.IGNORECASE)
_RANGE_RE = re.compile(r"(\d+)\s*[–—-]\s*(\d+)")
_INT_RE = re.compile(r"\d+")


def ledger_open_chapters(letter_text: str) -> list[int]:
    """Chapters named by the letter's `## Recommendations ledger` rows whose
    kind is `in-chapter` and whose status is still `proposed` or `staged`."""
    m = _LEDGER_HEAD_RE.search(letter_text)
    if not m:
        return []
    rows = [ln.strip() for ln in letter_text[m.end():].splitlines() if ln.strip().startswith("|")]
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0].strip("|").split("|")]
    try:
        ci, ki, si = header.index("chapters"), header.index("kind"), header.index("status")
    except ValueError:
        return []
    out: set[int] = set()
    for row in rows[1:]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) <= max(ci, ki, si) or set(cells[0]) <= set("-: "):
            continue
        if cells[ki].lower() != "in-chapter":
            continue
        status = cells[si].lower()
        if not (status.startswith("proposed") or status.startswith("staged")):
            continue
        text = cells[ci]
        for a, z in _RANGE_RE.findall(text):
            out.update(range(int(a), int(z) + 1))
        text = _RANGE_RE.sub(" ", text)
        out.update(int(x) for x in _INT_RE.findall(text))
    return sorted(out)


def _newest_chapter_mtime(book_root: Path) -> float | None:
    files = iter_chapter_files(book_root / "chapters")
    return max((p.stat().st_mtime for p in files), default=None)


def _freshness(path: Path, newest: float | None) -> str:
    if not path.is_file():
        return "missing"
    if newest is not None and newest > path.stat().st_mtime:
        return "stale"
    return "fresh"


def gather(book_root: Path) -> WholeBookState:
    """Read the book's whole-book reports into a WholeBookState."""
    s = WholeBookState()
    newest = _newest_chapter_mtime(book_root)
    logs = book_root / "edit_logs"
    letter = logs / "editor_letter.md"
    s.letter = _freshness(letter, newest)
    if letter.is_file():
        try:
            s.letter_open_chapters = ledger_open_chapters(letter.read_text(encoding="utf-8"))
        except OSError:
            pass
    sr_path = logs / "structure_review.json"
    if sr_path.is_file():
        from ..mechanical import structure_review as sr
        try:
            rep = sr.check(sr_path, book_root=book_root)
        except Exception:  # noqa: BLE001 — a broken report reads as invalid
            s.structure = "invalid"
        else:
            gate = rep.gate
            if not rep.valid:
                s.structure = "invalid"
            elif gate.get("stale"):
                s.structure = "stale"
            elif gate.get("passes"):
                s.structure = "passes"
            else:
                s.structure = "blocks"
            s.structure_reasons = list(gate.get("reasons") or [])
            s.structure_chapters = _candidate_chapters(sr_path)
    s.panel = _freshness(logs / "reader_panel.json", newest)
    review = logs / "review.md"
    if not review.is_file() and (logs / "opus_review.md").is_file():
        review = logs / "opus_review.md"
    s.review = _freshness(review, newest)
    return s


def _candidate_chapters(path: Path) -> list[int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    out: set[int] = set()
    for c in (data.get("candidates") or []) if isinstance(data, dict) else []:
        for e in (c.get("edits") or []) if isinstance(c, dict) else []:
            ch = e.get("chapter") if isinstance(e, dict) else None
            if isinstance(ch, int):
                out.add(ch)
    return sorted(out)
