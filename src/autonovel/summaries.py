"""Is each chapter's continuity summary still a summary of that chapter?

Every drafter and reviser reads the earlier chapters'
`ch_NN.summary.md` as its memory of the book. A summary written before
the chapter's prose last changed hands the next chapter a story that is
no longer on the page.

Freshness used to be judged by file mtimes. That flagged every revised
chapter as stale (revise writes the summary, then the chapter's
frontmatter), so the warning was ignored, and it was blind to a summary
touched after the prose changed (the `touch` workaround) or to a fresh
clone, where checkout order sets the mtimes. Now a summary records a
fingerprint of the chapter body it was written from, `summary_of:` in
its frontmatter, written by `autonovel _stamp-summary`. A summary is
fresh when that fingerprint matches the chapter as it now stands.

States:

  - `fresh`      stamped, and the fingerprint matches the chapter body.
  - `stale`      stamped with a different body; or, for a summary from
                 before fingerprints, the chapter file is newer.
  - `unverified` from before fingerprints and not older than its
                 chapter: probably right, but nothing proves it.
  - `missing`    no summary, or only a stub.

Anything but `fresh` is refreshed before a command reads it (the
preamble's summary step, driven by `_begin`), and `_end` refuses to
close a command that changed a chapter and left its summary behind.
Pure Python; no LLM.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .mechanical.frontmatter import strip_yaml_frontmatter

STAMP_KEY = "summary_of"
# A summary shorter than this is a stub, not a summary (the threshold
# `/autonovel:summarize-chapter` has always used to refuse overwriting).
MIN_SUMMARY_CHARS = 100

_CHAPTER_RE = re.compile(r"^ch_(\d+)\.md$")
_STAMP_RE = re.compile(rf"^{STAMP_KEY}:\s*(\S+)\s*$", re.MULTILINE)

REASONS = {
    "fresh": "matches the chapter as it now stands",
    "stale": "the chapter's text changed after this summary was written",
    "unverified": "written before summaries carried a fingerprint of their chapter",
    "missing": "no summary yet",
}


def body_hash(chapter_text: str) -> str:
    """Fingerprint of a chapter's prose: the text after its YAML
    frontmatter and its `# Title` line, with line endings and trailing
    whitespace normalised. Frontmatter edits (`word_count`, `status`,
    `title`) leave it unchanged; any change to the prose changes it."""
    body = strip_yaml_frontmatter(chapter_text).replace("\r\n", "\n")
    lines = [ln.rstrip() for ln in body.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    if lines and lines[0].startswith("# "):
        lines.pop(0)
    body = "\n".join(lines).strip("\n")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def summary_path_for(chapter_path: Path) -> Path:
    return chapter_path.with_name(f"{chapter_path.stem}.summary.md")


def read_stamp(summary_text: str) -> str | None:
    """The `summary_of:` fingerprint from a summary's frontmatter."""
    if not summary_text.startswith("---"):
        return None
    head = summary_text[: len(summary_text) - len(strip_yaml_frontmatter(summary_text))]
    m = _STAMP_RE.search(head)
    return m.group(1) if m else None


def summary_body(summary_text: str) -> str:
    return strip_yaml_frontmatter(summary_text).strip()


@dataclass
class SummaryState:
    chapter: int
    chapter_path: Path
    summary_path: Path
    status: str  # fresh | stale | unverified | missing
    stamped: bool = True  # False for a summary from before fingerprints

    @property
    def needs_refresh(self) -> bool:
        return self.status != "fresh"

    @property
    def reason(self) -> str:
        if self.status == "stale" and not self.stamped:
            return ("the chapter file is newer than this summary, which was written "
                    "before summaries carried a fingerprint")
        return REASONS[self.status]

    def to_dict(self, root: Path | None = None) -> dict:
        def rel(p: Path) -> str:
            if root is None:
                return str(p)
            try:
                return str(p.resolve().relative_to(root.resolve()))
            except ValueError:
                return str(p)
        return {
            "chapter": self.chapter,
            "status": self.status,
            "reason": self.reason,
            "chapter_file": rel(self.chapter_path),
            "summary_file": rel(self.summary_path),
        }


def state(chapter_path: Path) -> SummaryState:
    m = _CHAPTER_RE.match(chapter_path.name)
    chapter = int(m.group(1)) if m else 0
    spath = summary_path_for(chapter_path)
    if not spath.is_file():
        return SummaryState(chapter, chapter_path, spath, "missing")
    stext = spath.read_text(encoding="utf-8")
    if len(summary_body(stext)) < MIN_SUMMARY_CHARS:
        return SummaryState(chapter, chapter_path, spath, "missing")
    stamp = read_stamp(stext)
    if stamp is not None:
        current = body_hash(chapter_path.read_text(encoding="utf-8"))
        status = "fresh" if stamp == current else "stale"
        return SummaryState(chapter, chapter_path, spath, status)
    try:
        newer = chapter_path.stat().st_mtime > spath.stat().st_mtime
    except OSError:  # pragma: no cover
        newer = False
    return SummaryState(chapter, chapter_path, spath, "stale" if newer else "unverified",
                        stamped=False)


def chapter_files(book_root: Path) -> list[Path]:
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []
    out = [p for p in chapters_dir.iterdir() if _CHAPTER_RE.match(p.name)]
    return sorted(out, key=lambda p: int(_CHAPTER_RE.match(p.name).group(1)))  # type: ignore[union-attr]


def book_states(book_root: Path, chapters: set[int] | None = None) -> list[SummaryState]:
    """One state per drafted chapter, in chapter order; `chapters`
    restricts the scan."""
    out: list[SummaryState] = []
    for path in chapter_files(book_root):
        s = state(path)
        if chapters is None or s.chapter in chapters:
            out.append(s)
    return out


class StampError(ValueError):
    pass


def stamp(chapter_path: Path) -> str:
    """Record in the chapter's summary that it summarises the chapter
    as it now stands. Call it right after writing the summary from the
    chapter, or after re-reading an existing summary against the chapter
    and finding it still true. Returns the fingerprint."""
    spath = summary_path_for(chapter_path)
    if not chapter_path.is_file():
        raise StampError(f"no chapter file at {chapter_path}")
    if not spath.is_file():
        raise StampError(f"no summary at {spath}; write the summary first")
    stext = spath.read_text(encoding="utf-8")
    body = summary_body(stext)
    if len(body) < MIN_SUMMARY_CHARS:
        raise StampError(f"{spath} is a stub ({len(body)} characters); write the summary first")
    fp = body_hash(chapter_path.read_text(encoding="utf-8"))
    line = f"{STAMP_KEY}: {fp}"
    if stext.startswith("---") and strip_yaml_frontmatter(stext) != stext:
        head = stext[: len(stext) - len(strip_yaml_frontmatter(stext))]
        rest = stext[len(head):]
        if _STAMP_RE.search(head):
            head = _STAMP_RE.sub(line, head, count=1)
        else:
            first_nl = head.index("\n") + 1
            head = head[:first_nl] + line + "\n" + head[first_nl:]
        new = head + rest
    else:
        new = f"---\n{line}\n---\n\n{body}\n"
    spath.write_text(new, encoding="utf-8")
    return fp
