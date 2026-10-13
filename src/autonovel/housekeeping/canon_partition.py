"""Partition a series-wide `shared/canon.md` into book-scoped canon.

Before 2026-10-12 every promoted fact landed in `shared/canon.md`, so a
finished book's prose-derived inventions (a locked coffer, a favour
never repaid) sat next to real history as *series* canon. A second book
that re-tells the same story — or any sibling book — would then be bound
by the first book's plot choices, and every draft paid the token cost
of the whole file.

This helper moves bullets out of `shared/canon.md` into
`books/<book>/canon.md`:

  1. **Tagged bullets** — any bullet whose `(from <book> …)` provenance
     names a book in `project.yaml` moves to that book's canon.
     `(from research note …)` stays shared (a cited source is a
     universe fact).
  2. **Explicit moves** — `--move-section "<heading>"` moves every
     bullet under that `## heading` to `--to-book`; `--move-key
     "<shortname>"` moves the one bullet whose leading `[shortname]`
     matches. These are how the LLM half of
     `/autonovel:canon-partition` acts on its classification of the
     untagged leftovers.
  3. **Everything else stays** and is reported (section + shortname +
     snippet) so a human or the LLM can classify it.

`## Superseded …` audit blocks always stay in `shared/canon.md`.
Section headings travel with their bullets; a section emptied in
shared is dropped. Bullets keep their continuation lines (indented
sub-bullets) verbatim. Idempotent: a second run moves nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..paths import SeriesLayout
from .. import project as project_mod


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_BULLET_START_RE = re.compile(r"^[-*]\s+")
_PROVENANCE_RE = re.compile(r"\(from\s+([^)]+)\)")
_RESEARCH_PROVENANCE_RE = re.compile(r"^research note\b", re.IGNORECASE)
_SHORTNAME_RE = re.compile(r"^[-*]\s+\[([^\]]+)\]")

BOOK_CANON_HEADER = "# Book canon"


@dataclass
class Bullet:
    section: str              # the `## heading` text it sits under ("" if none)
    lines: list[str]          # the bullet line + its indented continuation lines
    provenance: str | None    # `(from …)` tail text, if any
    shortname: str | None     # leading `[shortname]`, if any

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def snippet(self) -> str:
        first = _BULLET_START_RE.sub("", self.lines[0]).strip()
        return first if len(first) <= 100 else first[:97] + "..."

    def provenance_book(self, book_names: list[str]) -> str | None:
        """The project.yaml book this bullet's provenance names, if any."""
        if not self.provenance:
            return None
        if _RESEARCH_PROVENANCE_RE.match(self.provenance.strip()):
            return None
        head = self.provenance.strip().split()[0]
        return head if head in book_names else None


@dataclass
class Section:
    heading: str              # full heading line, e.g. "## Promoted 2026-04-25"
    title: str                # heading text without the hashes
    level: int
    preamble: list[str] = field(default_factory=list)   # non-bullet lines before the first bullet
    bullets: list[Bullet] = field(default_factory=list)
    trailing: list[str] = field(default_factory=list)   # non-bullet lines after bullets (rare)

    @property
    def is_superseded(self) -> bool:
        return self.title.lower().startswith("superseded")


@dataclass
class LeftoverEntry:
    section: str
    shortname: str | None
    snippet: str

    def to_dict(self) -> dict:
        return {"section": self.section, "shortname": self.shortname, "snippet": self.snippet}


@dataclass
class PartitionReport:
    dry_run: bool
    moved: dict[str, int] = field(default_factory=dict)       # book → bullets moved
    moved_by_tag: int = 0
    moved_by_section: int = 0
    moved_by_key: int = 0
    stayed_shared: int = 0
    superseded_blocks_kept: int = 0
    leftovers: list[LeftoverEntry] = field(default_factory=list)  # untagged, still shared
    unmatched_keys: list[str] = field(default_factory=list)
    unmatched_sections: list[str] = field(default_factory=list)
    shared_words_before: int = 0
    shared_words_after: int = 0

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "moved": dict(self.moved),
            "moved_by_tag": self.moved_by_tag,
            "moved_by_section": self.moved_by_section,
            "moved_by_key": self.moved_by_key,
            "stayed_shared": self.stayed_shared,
            "superseded_blocks_kept": self.superseded_blocks_kept,
            "leftovers": [e.to_dict() for e in self.leftovers],
            "unmatched_keys": list(self.unmatched_keys),
            "unmatched_sections": list(self.unmatched_sections),
            "shared_words_before": self.shared_words_before,
            "shared_words_after": self.shared_words_after,
        }


class PartitionError(ValueError):
    pass


# ------------------------------------------------------------ parsing


def parse_canon(text: str) -> tuple[list[str], list[Section]]:
    """Split a canon file into (document preamble lines, sections).

    The document preamble is everything before the first `##` heading
    (typically `# Canon` plus a comment). Bullets are `- ` / `* ` lines
    plus any immediately following indented lines (continuations,
    sub-bullets)."""
    preamble: list[str] = []
    sections: list[Section] = []
    current: Section | None = None
    bullet: Bullet | None = None

    def _flush_bullet() -> None:
        nonlocal bullet
        if bullet is not None and current is not None:
            current.bullets.append(bullet)
        bullet = None

    for raw in text.splitlines():
        m = _HEADING_RE.match(raw)
        if m and len(m.group(1)) >= 2:
            _flush_bullet()
            current = Section(heading=raw, title=m.group(2), level=len(m.group(1)))
            sections.append(current)
            continue
        if current is None:
            preamble.append(raw)
            continue
        if _BULLET_START_RE.match(raw):
            _flush_bullet()
            prov = _PROVENANCE_RE.search(raw)
            sn = _SHORTNAME_RE.match(raw)
            bullet = Bullet(
                section=current.title,
                lines=[raw],
                provenance=prov.group(1).strip() if prov else None,
                shortname=sn.group(1).strip() if sn else None,
            )
            continue
        if bullet is not None and (raw.startswith(" ") or raw.startswith("\t")) and raw.strip():
            bullet.lines.append(raw)
            continue
        if bullet is not None and not raw.strip():
            # Blank line ends a bullet; keep the blank as section spacing
            # only if more bullets follow (handled at render time).
            _flush_bullet()
            continue
        # Non-bullet prose.
        if current.bullets or bullet is not None:
            _flush_bullet()
            current.trailing.append(raw)
        else:
            current.preamble.append(raw)
    _flush_bullet()
    return preamble, sections


def render_sections(preamble: list[str], sections: list[Section]) -> str:
    parts: list[str] = []
    pre = "\n".join(preamble).rstrip()
    if pre:
        parts.append(pre)
    for sec in sections:
        block: list[str] = [sec.heading]
        pre_lines = [ln for ln in sec.preamble if ln.strip()]
        if pre_lines:
            block.append("")
            block.extend(pre_lines)
        if sec.bullets:
            block.append("")
            for b in sec.bullets:
                block.extend(b.lines)
        trailing = [ln for ln in sec.trailing if ln.strip()]
        if trailing:
            block.append("")
            block.extend(trailing)
        parts.append("\n".join(block))
    return "\n\n".join(parts).rstrip() + "\n"


# ------------------------------------------------------------ partition


def partition(
    series: SeriesLayout,
    *,
    to_book: str | None = None,
    move_sections: list[str] | None = None,
    move_keys: list[str] | None = None,
    dry_run: bool = False,
) -> PartitionReport:
    """Move book-scoped bullets out of `shared/canon.md`. See module doc."""
    cfg = project_mod.load(series.project_file)
    book_names = [b.name for b in cfg.books]
    move_sections = list(move_sections or [])
    move_keys = list(move_keys or [])
    if (move_sections or move_keys) and not to_book:
        raise PartitionError("--move-section / --move-key require --to-book <name>")
    if to_book is not None and to_book not in book_names:
        raise PartitionError(f"unknown book {to_book!r}; known: {book_names}")

    canon_path = series.shared / "canon.md"
    text = canon_path.read_text(encoding="utf-8") if canon_path.is_file() else ""
    report = PartitionReport(dry_run=dry_run, shared_words_before=len(text.split()))
    if not text.strip():
        return report

    preamble, sections = parse_canon(text)
    wanted_sections = {s.strip().lower() for s in move_sections}
    wanted_keys = {k.strip().lower() for k in move_keys}
    seen_sections: set[str] = set()
    seen_keys: set[str] = set()

    # book → list of (section title, bullet) in document order
    outgoing: dict[str, list[tuple[str, Bullet]]] = {}
    kept_sections: list[Section] = []

    for sec in sections:
        if sec.is_superseded:
            report.superseded_blocks_kept += 1
            kept_sections.append(sec)
            continue
        kept_bullets: list[Bullet] = []
        sec_key = sec.title.strip().lower()
        for b in sec.bullets:
            target: str | None = None
            tagged = b.provenance_book(book_names)
            if tagged is not None:
                target = tagged
                report.moved_by_tag += 1
            elif sec_key in wanted_sections:
                target = to_book
                report.moved_by_section += 1
                seen_sections.add(sec_key)
            elif b.shortname and b.shortname.strip().lower() in wanted_keys:
                target = to_book
                report.moved_by_key += 1
                seen_keys.add(b.shortname.strip().lower())
            if target is None:
                kept_bullets.append(b)
                report.stayed_shared += 1
                report.leftovers.append(LeftoverEntry(
                    section=sec.title, shortname=b.shortname, snippet=b.snippet))
            else:
                outgoing.setdefault(target, []).append((sec.title, b))
                report.moved[target] = report.moved.get(target, 0) + 1
        had_bullets = bool(sec.bullets)
        sec.bullets = kept_bullets
        if kept_bullets:
            kept_sections.append(sec)
        elif not had_bullets and any(ln.strip() for ln in sec.preamble + sec.trailing):
            # A prose-only section (no bullets to begin with) is kept;
            # a section whose every bullet moved is dropped even if it
            # had an introductory line — that line described the
            # bullets, which now live in the book canon.
            kept_sections.append(sec)

    report.unmatched_sections = sorted(wanted_sections - seen_sections)
    report.unmatched_keys = sorted(wanted_keys - seen_keys)

    new_shared = render_sections(preamble, kept_sections)
    report.shared_words_after = len(new_shared.split())

    if dry_run or not outgoing:
        return report

    canon_path.write_text(new_shared, encoding="utf-8")
    for book, items in outgoing.items():
        _append_to_book_canon(series.books / book / "canon.md", items)
    return report


def _append_to_book_canon(path: Path, items: list[tuple[str, Bullet]]) -> None:
    """Append moved bullets, grouped under their original section
    headings (prefixed so provenance of the move is visible)."""
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    body = existing.rstrip()
    if not body.strip() or _is_stub(body):
        body = BOOK_CANON_HEADER
    out: list[str] = [body, ""]
    current_title: str | None = None
    for title, b in items:
        if title != current_title:
            out.append(f"## {title} (partitioned from shared/canon.md)")
            out.append("")
            current_title = title
        out.extend(b.lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _is_stub(text: str) -> bool:
    """True when the file holds only the template header + comment."""
    stripped = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    stripped = stripped.replace(BOOK_CANON_HEADER, "").strip()
    return not stripped


# ------------------------------------------------------------ rendering


def render_markdown(report: PartitionReport) -> str:
    parts: list[str] = ["# Canon partition" + (" (dry-run)" if report.dry_run else "")]
    parts.append("")
    parts.append(f"- shared/canon.md: {report.shared_words_before} → "
                 f"{report.shared_words_after} words")
    for book, n in sorted(report.moved.items()):
        parts.append(f"- moved to books/{book}/canon.md: {n} "
                     f"(by provenance tag {report.moved_by_tag}, by section "
                     f"{report.moved_by_section}, by key {report.moved_by_key})")
    parts.append(f"- stayed in shared/canon.md: {report.stayed_shared} bullets; "
                 f"{report.superseded_blocks_kept} `## Superseded` block(s) kept")
    if report.unmatched_sections:
        parts.append(f"- WARNING no section matched: {', '.join(report.unmatched_sections)}")
    if report.unmatched_keys:
        parts.append(f"- WARNING no key matched: {', '.join(report.unmatched_keys)}")
    if report.leftovers:
        parts.append("")
        parts.append("## Untagged bullets still in shared/canon.md")
        parts.append("")
        parts.append("_Classify each: series-wide (real history, world rule → stays) "
                     "or a book's own invention (→ `--move-key`)._")
        parts.append("")
        parts.append("| section | key | snippet |")
        parts.append("|---|---|---|")
        for e in report.leftovers:
            key = f"`{e.shortname}`" if e.shortname else "—"
            parts.append(f"| {e.section} | {key} | {e.snippet.replace('|', '/')} |")
    return "\n".join(parts) + "\n"
