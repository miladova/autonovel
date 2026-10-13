"""Mechanical impact analysis: "what should I revise after <command>?"

Surfaced 2026-04-29 by author testing
(`feedback_no_shell_in_user_workflow.md`): after promote-canon
the natural next question is "which chapters reference the
flipped facts?" — and today that's an `ls` + `grep` workflow,
which is exactly what autonovel exists to collapse.

This module is the mechanical first pass:

  - parse `## Superseded` blocks at the bottom of `shared/canon.md`
  - extract token diffs between each (prior, new) pair (tokens in
    prior that aren't in new = the "wrong values" still potentially
    referenced in chapter prose)
  - grep every chapter for those tokens, emit per-chapter line
    snippets as evidence

It deliberately does NOT do semantic / cross-chapter reasoning —
that's an LLM-judge follow-up listed in FUTURE-TODOS. The
mechanical surface here is a candidate generator (per
`feedback_avoid_brittle_python.md`) — a review list with
quoted snippets, not a scoring gate.

Public API:

    parse_canon_supersedures(canon_md_text) -> list[Supersedure]
    tokenise_for_grep(text) -> set[str]
    find_chapter_references(chapter_path, supersedures) -> list[ChapterMatch]
    build_impact_report(book_root, series_root, *, source) -> ImpactReport
    render_impact_markdown(report) -> str
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from ..paths import iter_chapter_files


# Words too generic to grep on — every chapter would match these.
# Kept short on purpose (per feedback_avoid_brittle_python.md):
# this is structural English, not domain vocabulary.
_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "to", "in", "on", "at", "by", "for",
    "with", "and", "or", "but", "as", "is", "was", "were", "be",
    "been", "being", "are", "this", "that", "these", "those", "his",
    "her", "him", "she", "he", "they", "their", "them", "it", "its",
    "from", "up", "out", "over", "into", "had", "has", "have",
    "do", "does", "did", "not", "no", "yes", "all", "any", "some",
    "one", "two", "three", "first", "last", "new", "old",
})

# Only treat tokens of 3+ letters as significant (filters out
# punctuation, articles, and short noise like "ad", "et").
_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ]{3,}|\d{3,4}")


@dataclass
class Supersedure:
    """One (prior, new) pair from a `## Superseded <date>` block."""
    shortname: str          # bracketed key, e.g. "Fugger arrived Augsburg"
    prior_value: str        # part after the bracket in the prior line
    new_value: str          # part after the bracket in the new line
    rationale: str = ""     # optional rationale text
    research_slug: str | None = None
    timestamp: str = ""     # the block's UTC date

    def grep_tokens(self) -> set[str]:
        """Tokens unique to `prior_value` (not in `new_value`) — the
        "wrong values" potentially still referenced in chapter prose.
        Stopwords removed; both 3+letter words and 3-4 digit years
        kept.
        """
        prior_tokens = tokenise_for_grep(self.prior_value)
        new_tokens = tokenise_for_grep(self.new_value)
        return prior_tokens - new_tokens


@dataclass
class ChapterMatch:
    """One chapter line that references a superseded value."""
    chapter: int
    line_no: int           # 1-indexed line number within the chapter
    line_text: str         # the matched line, trimmed
    matched_tokens: list[str]  # which tokens fired
    supersedure: Supersedure


@dataclass
class ImpactReport:
    source_command: str         # "promote-canon" for now
    supersedures: list[Supersedure]
    matches: list[ChapterMatch] = field(default_factory=list)
    chapters_with_matches: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_command": self.source_command,
            "supersedures": [
                {
                    "shortname": s.shortname,
                    "prior_value": s.prior_value,
                    "new_value": s.new_value,
                    "rationale": s.rationale,
                    "research_slug": s.research_slug,
                    "timestamp": s.timestamp,
                } for s in self.supersedures
            ],
            "matches": [
                {
                    "chapter": m.chapter,
                    "line_no": m.line_no,
                    "line_text": m.line_text,
                    "matched_tokens": m.matched_tokens,
                    "shortname": m.supersedure.shortname,
                } for m in self.matches
            ],
            "chapters_with_matches": self.chapters_with_matches,
        }


def tokenise_for_grep(text: str) -> set[str]:
    """Split `text` into significant tokens (3+ letters or 3-4 digit
    years), case-folded, with stopwords removed."""
    raw = _TOKEN_RE.findall(text)
    return {t.lower() for t in raw if t.lower() not in _STOPWORDS}


# ----------------------------------------------------- canon parsing


_SUPERSEDED_HEADER_RE = re.compile(
    r"^##\s+Superseded\s+(?P<ts>\S+)\s*$",
    re.MULTILINE,
)


def parse_canon_supersedures(canon_text: str) -> list[Supersedure]:
    """Parse every `## Superseded <date>` block in `canon_text`.

    Each block contains entries shaped like:
        - Prior canon line: `[<shortname>] <prior_value>`
          - Superseded by: `[<shortname>] <new_value>`
          - Rationale: <text>
          - Research note: <slug>     (optional)
    """
    supersedures: list[Supersedure] = []
    headers = list(_SUPERSEDED_HEADER_RE.finditer(canon_text))
    for i, h in enumerate(headers):
        block_start = h.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(canon_text)
        block = canon_text[block_start:block_end]
        timestamp = h.group("ts")
        supersedures.extend(_parse_supersede_block(block, timestamp))
    return supersedures


_PRIOR_RE = re.compile(
    r"^-\s+Prior canon line:\s+`(?P<prior>[^`]+)`\s*$",
    re.MULTILINE,
)
_NEW_RE = re.compile(
    r"^\s+-\s+Superseded by:\s+`(?P<new>[^`]+)`\s*$",
    re.MULTILINE,
)
_RATIONALE_RE = re.compile(
    r"^\s+-\s+Rationale:\s+(?P<rat>.+?)\s*$",
    re.MULTILINE,
)
_RESEARCH_RE = re.compile(
    r"^\s+-\s+Research note:\s+(?P<slug>\S+)\s*$",
    re.MULTILINE,
)
_BRACKET_RE = re.compile(r"^\[(?P<short>[^\]]+)\]\s*(?P<value>.*)$")


def _parse_supersede_block(block: str, timestamp: str) -> list[Supersedure]:
    """One block may contain multiple supersede entries, each spanning
    several lines. The format is unambiguous: each entry begins with
    `- Prior canon line:` and is followed (in order) by Superseded by
    / Rationale / Research note (optional)."""
    out: list[Supersedure] = []
    priors = list(_PRIOR_RE.finditer(block))
    for i, p in enumerate(priors):
        entry_start = p.start()
        entry_end = priors[i + 1].start() if i + 1 < len(priors) else len(block)
        entry = block[entry_start:entry_end]
        prior_line = p.group("prior")
        new_match = _NEW_RE.search(entry)
        if not new_match:
            continue
        new_line = new_match.group("new")
        prior_short, prior_value = _split_canon_line(prior_line)
        new_short, new_value = _split_canon_line(new_line)
        # Use the prior's shortname; new line should match anyway.
        shortname = prior_short or new_short
        rat = _RATIONALE_RE.search(entry)
        slug = _RESEARCH_RE.search(entry)
        out.append(Supersedure(
            shortname=shortname,
            prior_value=prior_value,
            new_value=new_value,
            rationale=rat.group("rat") if rat else "",
            research_slug=slug.group("slug") if slug else None,
            timestamp=timestamp,
        ))
    return out


def _split_canon_line(line: str) -> tuple[str, str]:
    """A canon line is shaped `[shortname] value`. Return both halves;
    `("", line)` when the bracket isn't present (defensive)."""
    m = _BRACKET_RE.match(line.strip())
    if not m:
        return ("", line.strip())
    return (m.group("short").strip(), m.group("value").strip())


# ---------------------------------------------------- chapter scanning


def find_chapter_references(chapter_path: Path,
                             supersedures: list[Supersedure]
                             ) -> list[ChapterMatch]:
    """Grep one chapter file for tokens unique to each supersedure's
    prior value. Returns one ChapterMatch per (chapter-line,
    supersedure) pair where ≥1 token fires."""
    if not chapter_path.is_file():
        return []
    text = strip_yaml_frontmatter(chapter_path.read_text(encoding="utf-8"))
    try:
        ch_num = int(chapter_path.stem.split("_")[-1])
    except ValueError:
        return []
    out: list[ChapterMatch] = []
    lines = text.splitlines()
    for sup in supersedures:
        tokens = sup.grep_tokens()
        if not tokens:
            continue
        # Compile a single OR-of-tokens regex with word boundaries.
        # Tokens are already lowercased; we match case-insensitively.
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in sorted(tokens)) + r")\b",
            re.IGNORECASE,
        )
        for line_no, line in enumerate(lines, start=1):
            hits = pattern.findall(line)
            if not hits:
                continue
            out.append(ChapterMatch(
                chapter=ch_num,
                line_no=line_no,
                line_text=line.strip(),
                matched_tokens=sorted({h.lower() for h in hits}),
                supersedure=sup,
            ))
    return out


def build_impact_report(book_root: Path, *, series_root: Path | None = None,
                         source_command: str = "promote-canon") -> ImpactReport:
    """Assemble the per-book impact report.

    Two surfaces share this report shape:

      - `promote-canon` / `gen-canon` — parse `## Superseded` blocks
        in `shared/canon.md` and grep prior-value tokens out of
        chapter prose. Same logic; gen-canon is just the regenerate-
        from-foundation variant of promote-canon and writes the
        same Superseded blocks when it changes a fact.
      - Other sources (`voice-discovery`, `add-character`,
        `add-source`, `research`) — return empty here; callers
        looking for stale-chapter analysis should use
        `build_stale_chapters_report` instead, which is mtime-based
        rather than token-based.
    """
    canon_sources = {"promote-canon", "gen-canon"}
    if source_command not in canon_sources:
        return ImpactReport(source_command=source_command, supersedures=[])
    series_root = series_root or book_root.parent.parent
    # Supersedure audit blocks live in whichever canon file held the
    # superseded line: series-wide `shared/canon.md` or this book's
    # own `books/<book>/canon.md` (book-scoped canon, 2026-10-12).
    supersedures: list[Supersedure] = []
    for canon_path in (series_root / "shared" / "canon.md", book_root / "canon.md"):
        if canon_path.is_file():
            supersedures.extend(
                parse_canon_supersedures(canon_path.read_text(encoding="utf-8")))
    if not supersedures:
        return ImpactReport(source_command=source_command, supersedures=[])
    matches: list[ChapterMatch] = []
    for ch_path in iter_chapter_files(book_root / "chapters"):
        matches.extend(find_chapter_references(ch_path, supersedures))
    chapters_with_matches = sorted({m.chapter for m in matches})
    return ImpactReport(
        source_command=source_command,
        supersedures=supersedures,
        matches=matches,
        chapters_with_matches=chapters_with_matches,
    )


# ---------------------------------------------- mtime-based stale detection


# Source command → foundation file path (relative to series_root for
# shared files, relative to book_root for per-book files). Tuple is
# `(rel_to_series, rel_to_book)` — exactly one of the two is set per
# entry.
_FOUNDATION_FILE_FOR: dict[str, tuple[str | None, str | None]] = {
    "voice-discovery": (None, "voice.md"),
    "add-character": ("shared/characters.md", None),
    "gen-characters": ("shared/characters.md", None),
    "gen-world": ("shared/world.md", None),
    "add-source": ("shared/sources.bib", None),
}


@dataclass
class StaleChapter:
    chapter: int
    chapter_mtime: str    # ISO
    foundation_mtime: str  # ISO

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "chapter_mtime": self.chapter_mtime,
            "foundation_mtime": self.foundation_mtime,
        }


@dataclass
class StaleChaptersReport:
    """For sources where the natural impact signal is "the
    foundation file changed; chapters drafted before that change
    haven't been reviewed against the new version" — voice-
    discovery, add-character, gen-world, add-source.
    """
    source_command: str
    foundation_path: str | None     # path that changed (or None when missing)
    foundation_mtime: str | None
    stale_chapters: list[StaleChapter] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_command": self.source_command,
            "foundation_path": self.foundation_path,
            "foundation_mtime": self.foundation_mtime,
            "stale_chapters": [s.to_dict() for s in self.stale_chapters],
        }


def build_stale_chapters_report(book_root: Path, *,
                                  series_root: Path | None = None,
                                  source_command: str
                                  ) -> StaleChaptersReport:
    """Find chapters with mtime older than the relevant foundation
    file. Used by sources that mutate a foundation surface in a way
    that doesn't lend itself to token-grep — voice register,
    character entries, world-bible facts, bibliography.
    """
    series_root = series_root or book_root.parent.parent
    if source_command not in _FOUNDATION_FILE_FOR:
        return StaleChaptersReport(
            source_command=source_command,
            foundation_path=None, foundation_mtime=None,
        )
    rel_series, rel_book = _FOUNDATION_FILE_FOR[source_command]
    foundation: Path | None = None
    if rel_series:
        foundation = series_root / rel_series
    elif rel_book:
        foundation = book_root / rel_book
    if foundation is None or not foundation.is_file():
        return StaleChaptersReport(
            source_command=source_command,
            foundation_path=str(foundation) if foundation else None,
            foundation_mtime=None,
        )
    found_mtime = foundation.stat().st_mtime
    found_iso = _to_iso(found_mtime)
    stale: list[StaleChapter] = []
    for ch_path in iter_chapter_files(book_root / "chapters"):
        ch_mtime = ch_path.stat().st_mtime
        if ch_mtime >= found_mtime:
            continue
        try:
            ch_num = int(ch_path.stem.split("_")[-1])
        except ValueError:
            continue
        stale.append(StaleChapter(
            chapter=ch_num,
            chapter_mtime=_to_iso(ch_mtime),
            foundation_mtime=found_iso,
        ))
    stale.sort(key=lambda s: s.chapter)
    return StaleChaptersReport(
        source_command=source_command,
        foundation_path=str(foundation),
        foundation_mtime=found_iso,
        stale_chapters=stale,
    )


def _to_iso(epoch: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def render_stale_chapters_markdown(report: StaleChaptersReport, *,
                                     book: str = "") -> str:
    if report.foundation_path is None:
        return (
            f"_No foundation file mapped for source "
            f"`{report.source_command}`. Supported sources: "
            f"{sorted(_FOUNDATION_FILE_FOR.keys())}._\n"
        )
    if report.foundation_mtime is None:
        return (
            f"_Foundation file `{report.foundation_path}` does not "
            f"exist; nothing to stale-check against._\n"
        )
    parts: list[str] = []
    parts.append(f"# Impact of `/autonovel:{report.source_command}`\n")
    parts.append(
        f"_Foundation file:_ `{report.foundation_path}` "
        f"(updated {report.foundation_mtime}).\n"
    )
    if not report.stale_chapters:
        parts.append(
            "✅ Every chapter is newer than the updated foundation "
            "file. Nothing to revise.\n"
        )
        return "\n".join(parts) + "\n"
    parts.append(
        f"⚠️  **{len(report.stale_chapters)} chapter(s)** were drafted "
        f"BEFORE the foundation file was last updated. Their prose "
        f"may not reflect what the foundation now says.\n"
    )
    parts.append("| ch | drafted | foundation updated |")
    parts.append("|---:|---|---|")
    for s in report.stale_chapters:
        parts.append(f"| {s.chapter} | {s.chapter_mtime} | {s.foundation_mtime} |")
    parts.append("")
    parts.append("## Action plan\n")
    book_arg = f" --book {book}" if book else ""
    chapters_str = ",".join(str(s.chapter) for s in report.stale_chapters)
    parts.append(
        f"Review each stale chapter against the updated foundation. "
        f"Most cases need a brief + revise pass; a few may be "
        f"untouched-since-the-foundation-update by coincidence and "
        f"actually fine.\n"
    )
    for s in report.stale_chapters:
        parts.append(
            f"- [ ] `/autonovel:revise --chapter {s.chapter}{book_arg}` "
            f"— reconcile against `{report.foundation_path}`."
        )
    parts.append("")
    parts.append(
        f"Or sweep the contiguous run with "
        f"`/autonovel:revision-pass --chapters {chapters_str}{book_arg}`."
    )
    parts.append("")
    parts.append(
        "_mtime-based candidate generator (per "
        "feedback_avoid_brittle_python.md). False positives are "
        "common — a chapter that happens not to reference the "
        "changed surface is fine as-is. Skim each before revising._"
    )
    return "\n".join(parts) + "\n"


# ----------------------------------------------------------- render


def render_impact_markdown(report: ImpactReport, *, book: str = "",
                            limit_per_supersedure: int = 5) -> str:
    """Markdown rendering: one section per supersedure with the
    matched chapter lines, then a final action checklist of
    `/autonovel:revise --chapter N` calls."""
    if not report.supersedures:
        return (
            "_No supersedures found in `shared/canon.md` or this book's `canon.md`. "
            "If you just ran `/autonovel:promote-canon`, this means "
            "no facts were superseded — nothing to act on here._\n"
        )
    parts: list[str] = []
    parts.append(f"# Impact of `/autonovel:{report.source_command}`")
    parts.append("")
    parts.append(
        f"_{len(report.supersedures)} fact(s) flipped; "
        f"{len(report.chapters_with_matches)} chapter(s) reference the "
        f"prior value and may need revising._\n"
    )
    parts.append("> Mechanical scan — token matches in chapter prose. ")
    parts.append("> A match means the chapter text contains a token from ")
    parts.append("> the OLD canon line. Some matches will be false ")
    parts.append("> positives (a year that coincides with the flipped ")
    parts.append("> fact, a name used in a different context); skim each ")
    parts.append("> snippet before revising.")
    parts.append("")
    by_sup: dict[int, list[ChapterMatch]] = {}
    for i, _ in enumerate(report.supersedures):
        by_sup[i] = []
    for m in report.matches:
        i = report.supersedures.index(m.supersedure)
        by_sup[i].append(m)
    for i, sup in enumerate(report.supersedures):
        parts.append(f"## {sup.shortname}")
        parts.append("")
        parts.append(f"- **Was:** `{sup.prior_value}`")
        parts.append(f"- **Now:** `{sup.new_value}`")
        if sup.rationale:
            parts.append(f"- **Why:** {sup.rationale}")
        if sup.research_slug:
            parts.append(f"- **Research note:** `{sup.research_slug}`")
        sup_matches = by_sup[i]
        if not sup_matches:
            parts.append("- _No chapter references found for this fact._")
            parts.append("")
            continue
        parts.append("")
        parts.append("Chapter references:")
        for m in sup_matches[:limit_per_supersedure]:
            snippet = (m.line_text[:140] + "…") if len(m.line_text) > 140 else m.line_text
            parts.append(
                f"- ch {m.chapter:02d} line {m.line_no} "
                f"(matched: {', '.join(m.matched_tokens)}): "
                f"`{snippet}`"
            )
        if len(sup_matches) > limit_per_supersedure:
            parts.append(
                f"- _… and {len(sup_matches) - limit_per_supersedure} "
                f"more line(s); use `--format json` for the full list._"
            )
        parts.append("")
    parts.append("## Action plan")
    parts.append("")
    if report.chapters_with_matches:
        for ch in report.chapters_with_matches:
            book_arg = f" --book {book}" if book else ""
            parts.append(
                f"- [ ] `/autonovel:revise --chapter {ch}{book_arg}` — "
                f"reconcile against the updated canon."
            )
        if len(report.chapters_with_matches) > 1:
            chapters_str = ",".join(str(c) for c in report.chapters_with_matches)
            book_arg = f" --book {book}" if book else ""
            parts.append("")
            parts.append(
                f"For contiguous runs you can sweep with "
                f"`/autonovel:revision-pass --chapters <range>{book_arg}` "
                f"(the comma-list above is non-contiguous: "
                f"{chapters_str})."
            )
    else:
        parts.append("- _No chapters reference the flipped facts. Nothing to revise._")
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"


# ----------------------- log-driven sources (rename / renumber)


_RENAME_SOURCES: frozenset[str] = frozenset({"rename-character"})
_RENUMBER_SOURCES: frozenset[str] = frozenset({
    "merge-chapters", "reorder", "remove-chapter",
})


def _read_command_log(series_root: Path):
    """Lazy import to avoid pulling command_log into mechanical's hot
    path. Returns [] when the log file is absent."""
    from ..command_log import read_all
    log = series_root / ".autonovel" / "command-log.jsonl"
    return read_all(log) if log.is_file() else []


def _most_recent(entries, slash_command: str):
    """Most recent successful entry for `autonovel:<slash_command>`,
    or None. Entries are timestamp-sorted by append order; we walk
    from the end."""
    target = f"autonovel:{slash_command}"
    for e in reversed(entries):
        if e.command == target and e.status == "ok":
            return e
    return None


def _flag_value(args: list[str], *flags: str) -> str | None:
    """Pull the value following any of `flags` in an argparse-style
    args list. Supports both `--flag value` and `--flag=value`."""
    for i, tok in enumerate(args):
        for f in flags:
            if tok == f and i + 1 < len(args):
                return args[i + 1]
            if tok.startswith(f + "="):
                return tok.split("=", 1)[1]
    return None


# ---------------------------------------- rename-character verify


@dataclass
class RenamePair:
    old: str
    new: str
    timestamp: str


@dataclass
class RenameVerifyReport:
    """After `/autonovel:rename-character`, scan chapters for the OLD
    name. The slash-command's word-boundary sed is supposed to catch
    every occurrence, but unicode names, hyphens, possessives, and
    HTML entities can slip through. This is the verify pass.
    """
    source_command: str = "rename-character"
    rename: RenamePair | None = None
    matches: list[ChapterMatch] = field(default_factory=list)
    chapters_with_matches: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_command": self.source_command,
            "rename": (
                {"old": self.rename.old, "new": self.rename.new,
                 "timestamp": self.rename.timestamp}
                if self.rename else None
            ),
            "matches": [
                {"chapter": m.chapter, "line_no": m.line_no,
                 "line_text": m.line_text,
                 "matched_tokens": m.matched_tokens}
                for m in self.matches
            ],
            "chapters_with_matches": self.chapters_with_matches,
        }


def build_rename_verify_report(book_root: Path, *,
                                series_root: Path | None = None,
                                ) -> RenameVerifyReport:
    series_root = series_root or book_root.parent.parent
    entries = _read_command_log(series_root)
    entry = _most_recent(entries, "rename-character")
    if entry is None:
        return RenameVerifyReport()
    old = _flag_value(entry.args, "--old")
    new = _flag_value(entry.args, "--new")
    if not old or not new:
        return RenameVerifyReport()
    rename = RenamePair(old=old, new=new, timestamp=entry.timestamp)
    # Build a synthetic Supersedure so we can reuse ChapterMatch shape.
    sup = Supersedure(
        shortname=f"{old} → {new}",
        prior_value=old,
        new_value=new,
        rationale=f"rename logged at {entry.timestamp}",
        timestamp=entry.timestamp,
    )
    pattern = re.compile(rf"\b{re.escape(old)}\b")
    matches: list[ChapterMatch] = []
    for ch_path in iter_chapter_files(book_root / "chapters"):
        text = strip_yaml_frontmatter(ch_path.read_text(encoding="utf-8"))
        try:
            ch_num = int(ch_path.stem.split("_")[-1])
        except ValueError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                matches.append(ChapterMatch(
                    chapter=ch_num, line_no=line_no,
                    line_text=line.strip(),
                    matched_tokens=[old], supersedure=sup,
                ))
    chapters_with_matches = sorted({m.chapter for m in matches})
    return RenameVerifyReport(
        rename=rename, matches=matches,
        chapters_with_matches=chapters_with_matches,
    )


def render_rename_verify_markdown(report: RenameVerifyReport, *,
                                    book: str = "",
                                    limit_per_chapter: int = 5) -> str:
    if report.rename is None:
        return (
            "_No `/autonovel:rename-character` invocation found in "
            "`.autonovel/command-log.jsonl`. Run a rename first, "
            "then re-run impact-of to verify it took._\n"
        )
    parts: list[str] = []
    parts.append(f"# Impact of `/autonovel:{report.source_command}`")
    parts.append("")
    parts.append(
        f"_Most recent rename:_ `{report.rename.old}` → "
        f"`{report.rename.new}` (logged {report.rename.timestamp})."
    )
    parts.append("")
    if not report.matches:
        parts.append(
            "✅ No straggler occurrences of the old name found. The "
            "rename took cleanly across every chapter."
        )
        parts.append("")
        return "\n".join(parts).rstrip() + "\n"
    parts.append(
        f"⚠️  **{len(report.chapters_with_matches)} chapter(s)** still "
        f"contain the old name `{report.rename.old}`. The "
        f"`/autonovel:rename-character` word-boundary sed missed these "
        f"— possessives, hyphens, HTML entities, and unicode look-alikes "
        f"are common causes."
    )
    parts.append("")
    by_ch: dict[int, list[ChapterMatch]] = {}
    for m in report.matches:
        by_ch.setdefault(m.chapter, []).append(m)
    for ch in sorted(by_ch):
        parts.append(f"## ch {ch:02d}")
        parts.append("")
        for m in by_ch[ch][:limit_per_chapter]:
            snippet = (m.line_text[:140] + "…") if len(m.line_text) > 140 else m.line_text
            parts.append(f"- line {m.line_no}: `{snippet}`")
        extra = len(by_ch[ch]) - limit_per_chapter
        if extra > 0:
            parts.append(f"- _… and {extra} more line(s)._")
        parts.append("")
    parts.append("## Action plan")
    parts.append("")
    book_arg = f" --book {book}" if book else ""
    for ch in report.chapters_with_matches:
        parts.append(
            f"- [ ] `/autonovel:revise --chapter {ch}{book_arg}` — "
            f"replace remaining `{report.rename.old}` references with "
            f"`{report.rename.new}` (or re-run "
            f"`/autonovel:rename-character --old {report.rename.old} "
            f"--new {report.rename.new}{book_arg}`)."
        )
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"


# --------------------------- merge / reorder / remove cross-references


# Inline chapter-number references in prose: "chapter 7", "Chapter VII",
# "ch. 12", "chapters 5 and 6". Word-boundary on both sides; case-
# insensitive. Roman numerals capped at the common range; deliberately
# NOT a full grammar — review-list shape per
# `feedback_avoid_brittle_python.md`.
_CHAPTER_REF_RE = re.compile(
    r"\b[Cc]h(?:apter|\.)\s+(\d+|[IVXLCDM]+)\b",
)


@dataclass
class ChapterRefMatch:
    chapter: int           # the chapter the reference appears in
    line_no: int
    line_text: str
    referenced: str        # the cited token, e.g. "7" or "VII"

    def to_dict(self) -> dict:
        return {
            "chapter": self.chapter,
            "line_no": self.line_no,
            "line_text": self.line_text,
            "referenced": self.referenced,
        }


@dataclass
class RenumberRefsReport:
    """After a renumber-the-book operation (`merge-chapters`,
    `reorder`, `remove-chapter`), prose references to chapter numbers
    elsewhere may now point at the wrong chapter. This is a candidate
    review list — the user judges each match against the new numbering.
    """
    source_command: str
    most_recent_args: list[str] = field(default_factory=list)
    most_recent_timestamp: str | None = None
    matches: list[ChapterRefMatch] = field(default_factory=list)
    chapters_with_matches: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_command": self.source_command,
            "most_recent_args": list(self.most_recent_args),
            "most_recent_timestamp": self.most_recent_timestamp,
            "matches": [m.to_dict() for m in self.matches],
            "chapters_with_matches": self.chapters_with_matches,
        }


def find_chapter_number_references(chapter_path: Path) -> list[ChapterRefMatch]:
    if not chapter_path.is_file():
        return []
    try:
        ch_num = int(chapter_path.stem.split("_")[-1])
    except ValueError:
        return []
    text = strip_yaml_frontmatter(chapter_path.read_text(encoding="utf-8"))
    out: list[ChapterRefMatch] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for m in _CHAPTER_REF_RE.finditer(line):
            out.append(ChapterRefMatch(
                chapter=ch_num, line_no=line_no,
                line_text=line.strip(),
                referenced=m.group(1),
            ))
    return out


def build_renumber_refs_report(book_root: Path, *,
                                 series_root: Path | None = None,
                                 source_command: str
                                 ) -> RenumberRefsReport:
    series_root = series_root or book_root.parent.parent
    if source_command not in _RENUMBER_SOURCES:
        return RenumberRefsReport(source_command=source_command)
    entries = _read_command_log(series_root)
    entry = _most_recent(entries, source_command)
    matches: list[ChapterRefMatch] = []
    for ch_path in iter_chapter_files(book_root / "chapters"):
        matches.extend(find_chapter_number_references(ch_path))
    chapters_with_matches = sorted({m.chapter for m in matches})
    return RenumberRefsReport(
        source_command=source_command,
        most_recent_args=list(entry.args) if entry else [],
        most_recent_timestamp=entry.timestamp if entry else None,
        matches=matches,
        chapters_with_matches=chapters_with_matches,
    )


def render_renumber_refs_markdown(report: RenumberRefsReport, *,
                                    book: str = "",
                                    limit_per_chapter: int = 5) -> str:
    parts: list[str] = []
    parts.append(f"# Impact of `/autonovel:{report.source_command}`")
    parts.append("")
    if report.most_recent_timestamp:
        args_str = " ".join(report.most_recent_args)
        parts.append(
            f"_Most recent invocation:_ `{report.source_command} "
            f"{args_str}` (logged {report.most_recent_timestamp})."
        )
    else:
        parts.append(
            f"_No `/autonovel:{report.source_command}` entry found in "
            f"`.autonovel/command-log.jsonl`._ Showing all chapter-number "
            f"cross-references regardless — review against the current "
            f"chapter ordering."
        )
    parts.append("")
    if not report.matches:
        parts.append(
            "✅ No prose chapter-number cross-references found. Nothing "
            "to reconcile after the renumber."
        )
        parts.append("")
        return "\n".join(parts).rstrip() + "\n"
    parts.append(
        f"⚠️  **{len(report.chapters_with_matches)} chapter(s)** contain "
        f"prose references to chapter numbers (`Chapter VII`, `chapter 7`, "
        f"`ch. 12`, …). After a renumber, these may now point at the "
        f"wrong chapter."
    )
    parts.append("")
    parts.append(
        "> Mechanical scan — every chapter-number mention in prose. "
        "False positives are common (a chapter that meant the right "
        "chapter all along, or a thematic mention rather than a "
        "navigational one); skim each before revising."
    )
    parts.append("")
    by_ch: dict[int, list[ChapterRefMatch]] = {}
    for m in report.matches:
        by_ch.setdefault(m.chapter, []).append(m)
    for ch in sorted(by_ch):
        parts.append(f"## ch {ch:02d}")
        parts.append("")
        for m in by_ch[ch][:limit_per_chapter]:
            snippet = (m.line_text[:140] + "…") if len(m.line_text) > 140 else m.line_text
            parts.append(
                f"- line {m.line_no} (refs `{m.referenced}`): `{snippet}`"
            )
        extra = len(by_ch[ch]) - limit_per_chapter
        if extra > 0:
            parts.append(f"- _… and {extra} more line(s)._")
        parts.append("")
    parts.append("## Action plan")
    parts.append("")
    book_arg = f" --book {book}" if book else ""
    for ch in report.chapters_with_matches:
        parts.append(
            f"- [ ] `/autonovel:revise --chapter {ch}{book_arg}` — "
            f"verify chapter-number references against current ordering."
        )
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"
