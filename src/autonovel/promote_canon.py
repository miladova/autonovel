"""Pure-Python promote-canon engine — moves candidate facts from
`books/{book}/pending_canon.md` into canon.

Two canon files (book-scoped canon, 2026-10-12):

  - `books/{book}/canon.md` — facts THIS book's prose established. They
    bind this book only; a sibling book (different POV, later period, or
    a rewrite of the same story) may decide them differently.
  - `shared/canon.md` — series-wide facts every book must respect.

Routing (`scope`):
  - "auto" (default): research-cited entries (`[research:<slug>]`, a
    primary source behind them) → shared; everything else → book canon.
  - "book" / "series": force every survivor into that one file.

De-dup / contradiction checks run against shared canon + the book's OWN
canon + world + characters — never against another book's canon, so a
rewrite is free to diverge from the original.

This module is the single source of truth for the promote-canon
logic. Three callers consume it:

  1. `commands/promote-canon.md` (the slash-command body) — invokes
     `autonovel _promote-canon --book <name>` with the lock acquired
     by its own preamble.
  2. `commands/revision-pass.md` step 3f (per-chapter sub-agent) —
     invokes `autonovel _promote-canon --book <name> --no-lock`
     because the parent revision-pass already holds the lock.
  3. `commands/draft-pass.md` step 5 (per-chapter sub-agent) — same
     invocation as (2).

The `--no-lock` flag is the load-bearing piece: it lets sub-agents
inside a sweep call this helper without colliding with the parent's
already-acquired `.autonovel/in-progress.lock`. Without it, the
sub-agent's preamble would deadlock on the lock and the per-chapter
canon promotion would silently fail (author bug-report 2026-04-26).

Behaviour matches `commands/promote-canon.md` step-for-step:

  - Parse pending entries (skip `no new facts`).
  - Classify each as Duplicate / Contradiction / Survivor against
    `shared/canon.md`, `shared/world.md`, `shared/characters.md`.
  - Research-tagged entries (carrying `[research:<slug>]`) win
    contradictions; the prior canon line gets recorded under a
    `## Superseded <UTC-date>` block.
  - Survivors get appended to `shared/canon.md` under a single
    `## Promoted <UTC-date>` heading.
  - Conflicts (non-research-tagged contradictions) get rewritten
    back to `pending_canon.md` under the structured `## Conflict N`
    format with the mandatory HTML-comment instruction block at
    top.
  - When no conflicts remain, `pending_canon.md` is reset to the
    single line `no new facts`.

Returns a `PromotionReport` with per-book counts the caller turns
into a status line / JSON.

Important: this engine does NOT do contradiction-detection via LLM.
It uses heuristic string matching (case-insensitive substring +
shared-token overlap) — good enough for the deterministic-Python
layer; the LLM-driven slash-command body can add semantic checks if
we ever decide to. The simpler layer covers the lock-collision bug
class without introducing any new LLM-time dependency in sweeps.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .paths import SeriesLayout


# A pending bullet line: `- <fact> [shortname?] [research:<slug>?]
# (from <book> ch_<NN>?)` — only the leading `- ` is required;
# everything else is optional metadata we preserve verbatim when
# present.
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_RESEARCH_TAG_RE = re.compile(r"\[research:([a-zA-Z0-9_\-]+)\]")
_PROVENANCE_RE = re.compile(r"\(from\s+([^)]+)\)")
_SHORTNAME_RE = re.compile(r"\[([a-zA-Z][a-zA-Z0-9_:\-]*)\]")
_NO_NEW_FACTS_RE = re.compile(r"^\s*no\s+new\s+facts\s*$", re.IGNORECASE)


@dataclass
class PendingEntry:
    """One bullet line from `pending_canon.md`."""
    raw_line: str
    fact_text: str            # the bullet content with metadata stripped
    research_slug: str | None # `[research:<slug>]` if present
    shortnames: list[str]     # `[shortname]` citation(s)
    provenance: str | None    # `(from ...)` tail


@dataclass
class ConflictRecord:
    """A pending entry that contradicts an existing canon line. Gets
    written back to pending_canon.md in the structured format the
    user resolves by hand."""
    candidate: PendingEntry
    existing_line: str
    existing_file: str        # relative path: `shared/canon.md` etc.
    rationale: str            # one-sentence "why they conflict"


@dataclass
class SupersedureRecord:
    """A research-tagged entry that beat an existing canon line. The
    new entry gets promoted; the prior line is recorded under a
    `## Superseded` block in shared/canon.md with the citation."""
    new_entry: PendingEntry
    superseded_line: str
    superseded_file: str
    rationale: str


@dataclass
class BookReport:
    book: str
    promoted: int = 0
    duplicates: int = 0
    conflicts: int = 0
    supersedures: int = 0
    promoted_to_book: int = 0     # landed in books/{book}/canon.md
    promoted_to_shared: int = 0   # landed in shared/canon.md
    promoted_lines: list[str] = field(default_factory=list)
    conflict_records: list[ConflictRecord] = field(default_factory=list)
    supersedure_records: list[SupersedureRecord] = field(default_factory=list)


@dataclass
class PromotionReport:
    """Aggregate report across all books promoted in one invocation."""
    timestamp: str
    books: list[BookReport] = field(default_factory=list)
    dry_run: bool = False
    no_lock: bool = False
    scope: str = "auto"

    def to_dict(self) -> dict:
        out = asdict(self)
        # asdict serialises nested dataclasses; JSON-clean the
        # PendingEntry inside ConflictRecord/SupersedureRecord too.
        return out


# -------------------------------------------------------- core API


SCOPES = ("auto", "book", "series")


def book_canon_path(series: SeriesLayout, book: str) -> Path:
    return series.books / book / "canon.md"


def _target_for(entry: "PendingEntry", *, scope: str) -> str:
    """`"shared"` or `"book"` — which canon file a survivor lands in."""
    if scope == "series":
        return "shared"
    if scope == "book":
        return "book"
    return "shared" if entry.research_slug else "book"


def promote(
    series: SeriesLayout,
    *,
    book: str | None = None,
    dry_run: bool = False,
    no_lock: bool = False,
    now: datetime | None = None,
    scope: str = "auto",
) -> PromotionReport:
    """Promote pending canon entries for `book` (or every book if
    None). When `dry_run`, no files are modified. `scope` routes
    survivors (see module docstring).

    The `no_lock` flag does NOT affect this function's file
    operations directly — it's recorded in the report for the
    caller's audit trail. The lock is acquired/released by the
    caller (the slash-command's preamble); this function just
    reads/writes files.
    """
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {list(SCOPES)}, got {scope!r}")
    when = now or datetime.now(timezone.utc)
    timestamp = when.strftime("%Y-%m-%d")
    report = PromotionReport(
        timestamp=when.isoformat(),
        dry_run=dry_run,
        no_lock=no_lock,
        scope=scope,
    )

    book_names = _resolve_books(series, book)
    canon_path = series.shared / "canon.md"
    world_path = series.shared / "world.md"
    characters_path = series.shared / "characters.md"

    canon_text = canon_path.read_text(encoding="utf-8") if canon_path.is_file() else ""
    world_text = world_path.read_text(encoding="utf-8") if world_path.is_file() else ""
    characters_text = characters_path.read_text(encoding="utf-8") if characters_path.is_file() else ""

    # Survivors + supersedures are grouped by TARGET FILE, then each
    # target gets a single `## Promoted` block (and zero or more
    # `## Superseded` blocks) appended at the end. Per-book pending
    # files get rewritten individually.
    #   key "shared"      → shared/canon.md
    #   key "book:<name>" → books/<name>/canon.md
    survivors_by_target: dict[str, list[tuple[str, PendingEntry]]] = {}
    supersedures_by_target: dict[str, list[SupersedureRecord]] = {}

    def _add_survivor(target_key: str, book_name: str, entry: PendingEntry) -> None:
        survivors_by_target.setdefault(target_key, []).append((book_name, entry))

    for book_name in book_names:
        book_report = BookReport(book=book_name)
        report.books.append(book_report)
        pending_path = series.books / book_name / "pending_canon.md"
        if not pending_path.is_file():
            continue
        pending_text = pending_path.read_text(encoding="utf-8")
        entries = _parse_pending(pending_text)
        if not entries:
            continue

        own_canon_path = book_canon_path(series, book_name)
        own_canon_text = (
            own_canon_path.read_text(encoding="utf-8") if own_canon_path.is_file() else ""
        )
        own_canon_rel = f"books/{book_name}/canon.md"

        kept_after_classify: list[ConflictRecord] = []
        for entry in entries:
            classification = _classify(
                entry,
                canon_text=canon_text,
                world_text=world_text,
                characters_text=characters_text,
                book_canon_text=own_canon_text,
                book_canon_rel=own_canon_rel,
            )
            target = _target_for(entry, scope=scope)
            target_key = "shared" if target == "shared" else f"book:{book_name}"
            if classification["kind"] == "duplicate":
                book_report.duplicates += 1
            elif classification["kind"] == "contradiction":
                if entry.research_slug:
                    # Research-tagged: promote, supersede prior line.
                    # The supersedure audit block lands in the file
                    # that held the superseded line.
                    sup = SupersedureRecord(
                        new_entry=entry,
                        superseded_line=classification["existing_line"],
                        superseded_file=classification["existing_file"],
                        rationale=classification["rationale"],
                    )
                    sup_key = (
                        f"book:{book_name}"
                        if classification["existing_file"] == own_canon_rel
                        else "shared"
                    )
                    supersedures_by_target.setdefault(sup_key, []).append(sup)
                    book_report.supersedure_records.append(sup)
                    book_report.supersedures += 1
                    _add_survivor(target_key, book_name, entry)
                    book_report.promoted += 1
                    _count_target(book_report, target)
                else:
                    conflict = ConflictRecord(
                        candidate=entry,
                        existing_line=classification["existing_line"],
                        existing_file=classification["existing_file"],
                        rationale=classification["rationale"],
                    )
                    kept_after_classify.append(conflict)
                    book_report.conflict_records.append(conflict)
                    book_report.conflicts += 1
            else:  # survivor
                _add_survivor(target_key, book_name, entry)
                book_report.promoted += 1
                _count_target(book_report, target)

        if dry_run:
            continue

        # Rewrite pending_canon.md per-book.
        new_pending = _render_pending_canon(kept_after_classify)
        pending_path.write_text(new_pending, encoding="utf-8")

    # Record survivor lines for the report (string form the canon
    # file will see) — in dry-run too, so the caller can show them.
    for survivors in survivors_by_target.values():
        for book_name, entry in survivors:
            line = _render_canon_line(entry, book_name)
            for br in report.books:
                if br.book == book_name:
                    br.promoted_lines.append(line)
                    break

    if dry_run:
        return report

    # Append survivors + supersedures to each target canon file.
    for target_key in sorted(set(survivors_by_target) | set(supersedures_by_target)):
        survivors = survivors_by_target.get(target_key, [])
        supersedures = supersedures_by_target.get(target_key, [])
        if not survivors and not supersedures:
            continue
        if target_key == "shared":
            path = canon_path
            header = "# Canon"
        else:
            path = book_canon_path(series, target_key.split(":", 1)[1])
            header = "# Book canon"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        appended = _render_canon_appendage(
            survivors=survivors,
            supersedures=supersedures,
            timestamp=timestamp,
        )
        if existing.strip():
            new_text = existing.rstrip() + "\n\n" + appended
        else:
            new_text = f"{header}\n\n" + appended
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")

    return report


def _count_target(book_report: BookReport, target: str) -> None:
    if target == "shared":
        book_report.promoted_to_shared += 1
    else:
        book_report.promoted_to_book += 1


# -------------------------------------------------- pending parsing


def _parse_pending(text: str) -> list[PendingEntry]:
    """Parse the bulleted candidate list from a pending_canon.md
    body. Lines that already live inside a `# Conflicts` or
    `## Conflict N` section ARE included — those are pending entries
    that previously failed to promote and should be retried.

    `no new facts` markers are skipped silently.
    """
    out: list[PendingEntry] = []
    in_html_comment = False
    for raw in text.splitlines():
        # Skip everything inside an HTML comment block (the
        # instruction sheet inside Conflicts).
        if "<!--" in raw and "-->" not in raw:
            in_html_comment = True
            continue
        if in_html_comment:
            if "-->" in raw:
                in_html_comment = False
            continue
        line = raw.strip()
        if not line:
            continue
        if _NO_NEW_FACTS_RE.match(line):
            continue
        if line.startswith("#"):
            continue  # heading
        # Skip the labelled key-value rows inside a `## Conflict N` block:
        # `- **New candidate:** \`<line>\`` — we want the wrapped
        # candidate line, but parsing it requires a more complex
        # pass; for v1, treat any conflict-block "New candidate"
        # line as a re-pending entry by stripping the label.
        labelled = re.match(r"^\s*[-*]\s+\*\*New candidate:\*\*\s*`?([^`]+)`?\s*$", raw)
        if labelled:
            inner = labelled.group(1).strip()
            if inner.startswith("- "):
                line = inner
            else:
                line = "- " + inner
        bullet_match = _BULLET_RE.match(line)
        if not bullet_match:
            continue
        body = bullet_match.group(1).strip()
        # Skip the labelled rows (Existing canon / Why they conflict /
        # Source) inside `## Conflict N` blocks.
        if body.startswith("**") and ":**" in body:
            continue
        research_slug_match = _RESEARCH_TAG_RE.search(body)
        research_slug = research_slug_match.group(1) if research_slug_match else None
        shortnames = [
            m.group(1) for m in _SHORTNAME_RE.finditer(body)
            if not m.group(1).startswith("research:")
        ]
        provenance_match = _PROVENANCE_RE.search(body)
        provenance = provenance_match.group(1).strip() if provenance_match else None
        # Strip metadata from the fact text for classification purposes.
        fact_text = body
        for m in _RESEARCH_TAG_RE.finditer(body):
            fact_text = fact_text.replace(m.group(0), "")
        for m in _SHORTNAME_RE.finditer(body):
            fact_text = fact_text.replace(m.group(0), "")
        if provenance_match:
            fact_text = fact_text.replace(provenance_match.group(0), "")
        fact_text = fact_text.strip().rstrip(".").strip()
        out.append(PendingEntry(
            raw_line=raw,
            fact_text=fact_text,
            research_slug=research_slug,
            shortnames=shortnames,
            provenance=provenance,
        ))
    # De-dup within one pending file by fact_text (case-insensitive).
    seen: set[str] = set()
    uniq: list[PendingEntry] = []
    for e in out:
        key = e.fact_text.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


# ---------------------------------------------------- classification


def _classify(
    entry: PendingEntry,
    *,
    canon_text: str,
    world_text: str,
    characters_text: str,
    book_canon_text: str = "",
    book_canon_rel: str = "books/{book}/canon.md",
) -> dict:
    """Return one of:
      {"kind": "duplicate"}
      {"kind": "contradiction", "existing_line": ..., "existing_file": ..., "rationale": ...}
      {"kind": "survivor"}

    Heuristic — case-insensitive substring + shared-token overlap.
    Not LLM-grade; deliberately conservative: if uncertain, return
    survivor (don't drop facts on a heuristic).
    """
    fact_norm = _normalise(entry.fact_text)
    if not fact_norm:
        return {"kind": "survivor"}

    candidates = (
        (book_canon_rel, book_canon_text),
        ("shared/canon.md", canon_text),
        ("shared/world.md", world_text),
        ("shared/characters.md", characters_text),
    )

    # Tokens that recur across the corpus (a series about the Fuggers
    # has "fugger" / "venice" / "augsburg" on most lines) carry no
    # evidence that two lines describe the SAME fact. Learn them from
    # the corpus itself rather than from a hardcoded stop-list.
    common = _common_tokens(body for _name, body in candidates)

    for file_name, body in candidates:
        # Compare against whole facts, not physical lines: world.md and
        # characters.md are hard-wrapped prose, and a 70-character
        # fragment ("Head of the Höchstetter house (born 1463), the")
        # shares a couple of words with almost anything.
        for stripped in _units(body):
            line_norm = _normalise(stripped)
            if not line_norm:
                continue

            # Duplicate: substantively the same fact.
            if fact_norm == line_norm or _is_substring_dup(fact_norm, line_norm):
                return {"kind": "duplicate"}

            # Contradiction heuristic: high token overlap (≥3 shared
            # 4+ char tokens) but a numeric / year mismatch, OR a
            # negation flip ("is" vs "is not"). Conservative —
            # we'd rather miss a contradiction (and let the LLM judge
            # catch it later) than falsely flag a survivor.
            if _looks_contradictory(entry.fact_text, stripped, common=common):
                return {
                    "kind": "contradiction",
                    "existing_line": stripped,
                    "existing_file": file_name,
                    "rationale": _contradiction_rationale(entry.fact_text, stripped),
                }
    return {"kind": "survivor"}


def _normalise(s: str) -> str:
    """Lowercase, strip leading bullet marker, collapse whitespace."""
    s = re.sub(r"^[-*\s]+", "", s)
    # Strip parenthetical provenance for comparison purposes.
    s = _PROVENANCE_RE.sub("", s)
    s = _RESEARCH_TAG_RE.sub("", s)
    s = _SHORTNAME_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s.rstrip(".")


def _is_substring_dup(a: str, b: str) -> bool:
    """True when one normalised string is contained in the other AND
    the shorter is at least 60% of the longer's length — guards
    against a 5-char shared phrase counting as a dup of a long
    sentence."""
    if not a or not b:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) < 12:  # too short to trust as a duplicate
        return False
    if short not in long:
        return False
    return len(short) / max(1, len(long)) >= 0.6


_TOKEN_RE = re.compile(r"\b[a-zA-Z]{4,}\b")
# 3 or 4 digit numbers — covers early-medieval years (421 CE) through
# modern (2024). Conservative enough that "1.5 hours" won't match
# (the regex requires word boundaries on both sides) but broad enough
# for the historical-fiction year-disagreement case the helper exists
# to flag.
_YEAR_RE = re.compile(r"\b[1-9][0-9]{2,3}\b")


_HEADLINE_RE = re.compile(r"^\s*[-*]?\s*\[([^\]]+)\]")

# A token is "common" when it appears on at least this many lines of the
# corpus AND on at least this share of them. Both guards matter: the
# share keeps a 10-line fixture from declaring everything common, the
# floor keeps a 3-line fixture from declaring anything common.
_COMMON_MIN_LINES = 5
_COMMON_MIN_SHARE = 0.15


def _headline(s: str) -> str:
    """The `[Key]` a canon line opens with, normalised; '' when absent."""
    m = _HEADLINE_RE.match(s)
    return re.sub(r"\s+", " ", m.group(1)).strip().lower() if m else ""


_BULLET_START_RE = re.compile(r"^[-*]\s")


def _units(body: str) -> list[str]:
    """Split a markdown body into comparable facts: one unit per bullet
    (with its wrapped continuation lines joined) and one unit per prose
    paragraph. Headings and blank lines are separators, never units."""
    units: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            units.append(" ".join(current))
            current.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            flush()
            continue
        if _BULLET_START_RE.match(stripped):
            flush()
        current.append(stripped)
    flush()
    return units


def _common_tokens(bodies) -> frozenset[str]:
    """Tokens that recur across the corpus and therefore say nothing
    about whether two particular lines describe the same fact."""
    counts: dict[str, int] = {}
    n_lines = 0
    for body in bodies:
        for unit in _units(body):
            n_lines += 1
            for tok in {t.lower() for t in _TOKEN_RE.findall(unit)}:
                counts[tok] = counts.get(tok, 0) + 1
    if n_lines == 0:
        return frozenset()
    floor = max(_COMMON_MIN_LINES, int(n_lines * _COMMON_MIN_SHARE))
    return frozenset(t for t, c in counts.items() if c >= floor)


def _looks_contradictory(a: str, b: str, *, common: frozenset[str] = frozenset()) -> bool:
    """Heuristic: the two lines describe the SAME fact and disagree on
    a year or a negation.

    "Same fact" is judged three ways, strongest first:

    1. Both lines open with a `[Key]` headline and the keys match.
       Any year or negation mismatch is then a real contradiction.
    2. Both have headlines and they differ. The lines are about
       different facts unless the overlap is overwhelming (≥4 shared
       informative tokens and a Jaccard overlap of at least 0.5).
       Without this guard, "[Battle of Calliano] ... 1487 ... Venetian
       force" retired "[Fugger Venice loss, 1477] ... Venetian force"
       (2026-10-13), and an earlier run retired `[Jakob Fugger birth]`
       on the strength of the word "Fugger".
    3. At least one line is unkeyed (world.md / characters.md prose,
       legacy canon). Year mismatch needs ≥2 shared informative tokens
       and Jaccard ≥ 0.3; a negation flip needs ≥3 shared tokens.
       "Venice founded in 421 CE" vs "Venice was founded in 697 CE
       during the early Byzantine period" still contradicts (two
       shared tokens out of six).

    Overlap is Jaccard (shared / union) rather than coverage of the
    shorter line, so a four-word fact cannot be "fully covered" by a
    long paragraph that happens to mention the same fair and the same
    prince. "Informative" excludes `common` — tokens the corpus uses
    on most lines (the series' own proper nouns). Conservative by
    design: if uncertain, return False and let the LLM judge catch it
    later.
    """
    a_tokens = {t.lower() for t in _TOKEN_RE.findall(a)} - common
    b_tokens = {t.lower() for t in _TOKEN_RE.findall(b)} - common
    shared = a_tokens & b_tokens
    union = a_tokens | b_tokens
    jaccard = len(shared) / len(union) if union else 0.0
    a_years = set(_YEAR_RE.findall(a))
    b_years = set(_YEAR_RE.findall(b))
    year_mismatch = bool(a_years and b_years and a_years.isdisjoint(b_years))
    negation_flip = _negations(a) != _negations(b)

    ka, kb = _headline(a), _headline(b)
    if ka and kb:
        if ka == kb:
            # Same headline = same fact by declaration. Any numeric
            # difference counts (23 vs 26 October is a two-digit
            # disagreement the year regex cannot see).
            return year_mismatch or negation_flip or _numbers(a) != _numbers(b)
        if len(shared) < 4 or jaccard < 0.5:
            return False
        return year_mismatch or negation_flip

    if year_mismatch and len(shared) >= 2 and jaccard >= 0.3:
        return True
    if negation_flip and len(shared) >= 3 and jaccard >= 0.3:
        return True
    return False


def _negations(s: str) -> bool:
    """True if the sentence carries a negation marker (`not`,
    `never`, `no `, contractions ending `n't`)."""
    s_low = s.lower()
    return bool(
        re.search(r"\bnot\b|\bnever\b|\bno\b|n't\b", s_low)
    )


_NUMBER_RE = re.compile(r"\b\d[\d,]*\b")


def _numbers(s: str) -> set[str]:
    """Every integer in the fact text (commas stripped), for same-key
    comparisons where a day-of-month or a sum is the disagreement."""
    return {n.replace(",", "") for n in _NUMBER_RE.findall(_normalise(s))}


def _contradiction_rationale(a: str, b: str) -> str:
    a_years = set(_YEAR_RE.findall(a))
    b_years = set(_YEAR_RE.findall(b))
    if a_years and b_years and a_years.isdisjoint(b_years):
        return f"date mismatch: {sorted(a_years)} vs {sorted(b_years)}"
    if _negations(a) != _negations(b):
        return "negation mismatch (one asserts, the other negates)"
    if _headline(a) and _headline(a) == _headline(b) and _numbers(a) != _numbers(b):
        return (f"same key [{_headline(a)}], number mismatch: "
                f"{sorted(_numbers(a))} vs {sorted(_numbers(b))}")
    return "shared subject; exact disagreement uncertain"


# --------------------------------------------------------- rendering


def _render_canon_line(entry: PendingEntry, book_name: str) -> str:
    """The canonical line shape that lands in a canon file per
    `commands/promote-canon.md` step 5."""
    base = entry.fact_text
    if entry.shortnames:
        base = f"{base} [{entry.shortnames[0]}]"
    if entry.research_slug:
        return f"- {base} (from research note {entry.research_slug})"
    if entry.provenance:
        return f"- {base} (from {entry.provenance})"
    return f"- {base} (from {book_name})"


def _render_canon_appendage(
    *,
    survivors: list[tuple[str, PendingEntry]],
    supersedures: list[SupersedureRecord],
    timestamp: str,
) -> str:
    parts: list[str] = []
    if survivors:
        parts.append(f"## Promoted {timestamp}\n")
        for book_name, entry in survivors:
            parts.append(_render_canon_line(entry, book_name))
        parts.append("")  # trailing newline
    if supersedures:
        parts.append(f"## Superseded {timestamp}\n")
        for sup in supersedures:
            parts.append(f"- Prior canon line: `{sup.superseded_line}`")
            parts.append(f"  - Superseded by: `{_render_canon_line(sup.new_entry, '').lstrip('- ')}`")
            parts.append(f"  - Rationale: {sup.rationale}")
            if sup.new_entry.research_slug:
                parts.append(f"  - Research note: {sup.new_entry.research_slug}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


_CONFLICT_INSTRUCTION_BLOCK = """\
<!--
HOW TO RESOLVE A CONFLICT
=========================

Each `## Conflict N` block below names a pending candidate that
couldn't be promoted because it contradicts something in this
book's canon (books/<book>/canon.md), shared/canon.md,
shared/world.md, or shared/characters.md. For each conflict, pick
ONE of the three resolutions and act:

  (A) ACCEPT the new fact (replace the existing one)
      1. Open the file named in `Existing canon (in: ...)`.
      2. Replace the old line (quoted under `Existing canon`)
         with the new line (quoted under `New candidate`). Keep
         the canonical bullet shape: `- <fact> (from <source>)`.
      3. Delete the entire `## Conflict N` block from THIS file.
      4. Re-run /autonovel:promote-canon. The conflict is gone.

  (B) REJECT the new fact (the existing one stays)
      1. Delete the entire `## Conflict N` block from THIS file.
      2. (Optional but recommended) fix the chapter that
         re-introduced the wrong fact, so it doesn't come back
         on the next draft / revise. The chapter is named under
         `Source`. Run:
           /autonovel:brief <N> --book <book>
           /autonovel:revise <N> --book <book>

  (C) BOTH ARE WRONG
      1. Edit the file named in `Existing canon (in: ...)` to
         the correct value.
      2. Delete the entire `## Conflict N` block from THIS file.
      3. Re-run /autonovel:promote-canon to land any newly
         consistent pending entries.

After your edits, re-run /autonovel:promote-canon. Resolved
conflicts disappear; anything still contradictory is re-emitted
on the next run with the same instructions.
-->
"""


def _render_pending_canon(conflicts: list[ConflictRecord]) -> str:
    """Either the structured conflict file, or `no new facts`.
    Mutually exclusive — never mix the two states."""
    if not conflicts:
        return "no new facts\n"
    parts: list[str] = ["# Conflicts — resolve before next promote-canon", ""]
    parts.append(_CONFLICT_INSTRUCTION_BLOCK)
    parts.append("")
    for i, conflict in enumerate(conflicts, start=1):
        candidate_line = conflict.candidate.raw_line.strip()
        if not candidate_line.startswith("-"):
            candidate_line = f"- {candidate_line}"
        source = (
            f"(from research note {conflict.candidate.research_slug})"
            if conflict.candidate.research_slug
            else (
                f"(from {conflict.candidate.provenance})"
                if conflict.candidate.provenance
                else "(source unknown)"
            )
        )
        parts.append(f"## Conflict {i}")
        parts.append(f"- **New candidate:** `{candidate_line}`")
        parts.append(f"- **Existing canon (in: {conflict.existing_file}):** `{conflict.existing_line}`")
        parts.append(f"- **Why they conflict:** {conflict.rationale}")
        parts.append(f"- **Source:** {source}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


# ------------------------------------------------------- book resolution


def _resolve_books(series: SeriesLayout, book: str | None) -> list[str]:
    """Read project.yaml; return the requested book or all books."""
    from . import project as project_mod
    cfg = project_mod.load(series.project_file)
    all_books = [b.name for b in cfg.books]
    if book is None:
        return all_books
    if book not in all_books:
        raise ValueError(f"unknown book: {book!r}; known: {all_books}")
    return [book]
