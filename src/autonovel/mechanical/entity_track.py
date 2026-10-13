"""Per-chapter named-entity tracker.

Generalises `motifs.py`. Where `motifs.py` counts symbolic image
keywords (the bell, the mortar, the river), this module counts
named-entity occurrences across chapters (a character's name, a
specific object that returns through the book — "the cipher diary",
"the book of accounts") with optional aliases.

Use cases (from author session 2026-04-28):

- "Check how many times Jakob added an entry to his cipher diary
  versus how many times he later referred to one." → count entity
  mentions per chapter, surface the table to the LLM, let
  `/autonovel:talk` do the semantic added-vs-referred pairing.
- "Where does Niccolò appear?" → presence/absence per chapter.
- "Track 'mint fire' across the book." → arc-spanning thread
  density.

Config can come from two places:

1. **Explicit, per-book**: `books/<book>/entities.md` (same bullet
   shape as `motifs.md`). When present, this is the canonical list.
2. **Auto-derived from canon.md**: when no `entities.md` exists,
   parse `[shortname]` keys out of `shared/canon.md` bullets
   (e.g. `- [Tommaso birthday] 1487-05-12`) and use each as a
   single-keyword entity. Lossy but useful as a starting point.

The helper intentionally DOES NOT do the "added vs referred"
semantic pairing — that's an LLM's job. This module surfaces the
counts; the slash-command stitches the meaning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from ..paths import iter_chapter_files


_BULLET_RE = re.compile(r"^\s*-\s*([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*$")
_CANON_BULLET_RE = re.compile(r"^\s*-\s*\[([^\]]+)\]\s*(.+?)\s*$")


@dataclass
class Entity:
    slug: str
    keywords: list[str]

    def pattern(self) -> re.Pattern[str]:
        kws = sorted(self.keywords, key=len, reverse=True)
        alt = "|".join(re.escape(k) for k in kws)
        return re.compile(rf"\b(?:{alt})\b", re.IGNORECASE)


@dataclass
class ChapterRow:
    chapter: int
    word_count: int
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class EntityReport:
    entities: list[Entity]
    rows: list[ChapterRow]
    source: str  # "entities.md" | "canon.md" | "none"

    def to_dict(self) -> dict:
        return {
            "entities": [e.slug for e in self.entities],
            "source": self.source,
            "rows": [
                {"chapter": r.chapter, "word_count": r.word_count,
                 "counts": dict(r.counts)} for r in self.rows
            ],
        }


def parse_entities_file(path: Path) -> list[Entity]:
    """Parse `books/<book>/entities.md` bullets `- slug: kw1, kw2`.
    Same shape as motifs.md. Returns [] when the file is missing or
    contains no parseable bullets."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    out: list[Entity] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = _BULLET_RE.match(line)
        if not m:
            continue
        slug = m.group(1).lower()
        kw_raw = m.group(2)
        keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
        if not keywords:
            continue
        if slug in seen:
            continue
        seen.add(slug)
        out.append(Entity(slug=slug, keywords=keywords))
    return out


def derive_entities_from_canon(canon_path: Path) -> list[Entity]:
    """Fallback: pull the `[shortname]` heads out of canon.md bullets
    and use the shortname token as a single keyword.

    Caveat: many canon shortnames are dates or abstract concepts
    (`[Tommaso birthday]`, `[Mint fire date]`) — those keyword scans
    will be noisy. This is a starting point, not a substitute for a
    hand-authored `entities.md`. The `EntityReport.source` field
    surfaces which path was used so the caller can mention it.
    """
    if not canon_path.is_file():
        return []
    text = canon_path.read_text(encoding="utf-8")
    out: list[Entity] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = _CANON_BULLET_RE.match(line)
        if not m:
            continue
        shortname = m.group(1).strip()
        # Use the first token of the shortname as the slug, the
        # whole shortname as the (single) keyword. Skip pure
        # numeric / date-only shortnames since they generate
        # noise rather than signal in prose. Slug strips ASCII
        # punctuation but preserves Unicode letters so e.g.
        # `Niccolò` slugs to `niccolò` not `niccol-`.
        slug = re.sub(r"[\s\W]+", "-", shortname.split(" ")[0],
                       flags=re.UNICODE).strip("-").lower()
        if not slug or slug in seen:
            continue
        if slug.isdigit():
            continue
        seen.add(slug)
        # Keyword: the head token (typically the named entity).
        head = shortname.split(" ")[0]
        if len(head) < 3:
            continue
        out.append(Entity(slug=slug, keywords=[head]))
    return out


def scan_chapter(text: str, entities: list[Entity]) -> tuple[int, dict[str, int]]:
    """Strip YAML frontmatter, then count word-boundary matches per
    entity. Returns (word_count, {slug: hits})."""
    body = strip_yaml_frontmatter(text)
    counts: dict[str, int] = {}
    for entity in entities:
        counts[entity.slug] = len(entity.pattern().findall(body))
    word_count = len(re.findall(r"\b\w+\b", body))
    return word_count, counts


def build_report(book_root: Path, *, series_root: Path | None = None,
                  entities_override: list[Entity] | None = None
                  ) -> EntityReport:
    """Build a per-chapter entity-density report.

    Resolution order for the entity list:
      1. `entities_override` argument (caller supplies, e.g.
         `/autonovel:talk` parses an ad-hoc list from the user's
         question).
      2. `books/<book>/entities.md` (hand-authored config).
      3. `books/<book>/canon.md` + `<series_root>/shared/canon.md`
         (auto-derived from `[shortname]` keys; lossy).
    """
    source = "none"
    if entities_override is not None:
        entities = entities_override
        source = "override"
    else:
        entities = parse_entities_file(book_root / "entities.md")
        if entities:
            source = "entities.md"
        elif series_root is not None:
            # Book canon first (this book's own named things), then the
            # series-wide file; de-dup by key.
            entities = derive_entities_from_canon(book_root / "canon.md")
            seen = {e.slug for e in entities}
            for e in derive_entities_from_canon(series_root / "shared" / "canon.md"):
                if e.slug not in seen:
                    entities.append(e)
                    seen.add(e.slug)
            if entities:
                source = "canon.md"
    rows: list[ChapterRow] = []
    for path in iter_chapter_files(book_root / "chapters"):
        m = re.match(r"^ch_(\d+)\.md$", path.name)
        if not m:
            continue
        text = path.read_text(encoding="utf-8")
        wc, counts = scan_chapter(text, entities)
        rows.append(ChapterRow(
            chapter=int(m.group(1)), word_count=wc, counts=counts,
        ))
    rows.sort(key=lambda r: r.chapter)
    return EntityReport(entities=entities, rows=rows, source=source)


def render_markdown(report: EntityReport, *, book: str | None = None) -> str:
    if not report.entities:
        head = f"# Entity tracker — {book}" if book else "# Entity tracker"
        return (
            f"{head}\n\n_No entities to track. Either create "
            f"`books/{book or '<book>'}/entities.md` (`- slug: keyword1, "
            f"keyword2`) or seed `shared/canon.md` with `[name]` bullets._\n"
        )
    parts: list[str] = []
    parts.append(f"# Entity tracker — {book}" if book else "# Entity tracker")
    parts.append("")
    parts.append(f"_source: {report.source}_")
    parts.append("")
    headers = ["Chapter", "Words", *[e.slug for e in report.entities]]
    parts.append("| " + " | ".join(headers) + " |")
    parts.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in report.rows:
        cells = [str(r.chapter), str(r.word_count)]
        for e in report.entities:
            n = r.counts.get(e.slug, 0)
            cells.append(str(n) if n else "·")
        parts.append("| " + " | ".join(cells) + " |")
    return "\n".join(parts) + "\n"
