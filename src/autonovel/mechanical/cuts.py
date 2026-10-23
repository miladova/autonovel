"""Deterministic cut-application helpers.

Ported from `apply_cuts.py` so `/autonovel:apply-cuts` doesn't ask the LLM
to do string removal. The command writes a `cuts.json` artifact and then
shells out to `python -m autonovel.mechanical apply-cuts <chapter> <cuts>`
which runs this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


VALID_TYPES: frozenset[str] = frozenset(
    {"OVER-EXPLAIN", "REDUNDANT", "FAT", "TELL", "STRUCTURAL", "GENERIC", "MISPLACED"}
)
# Content the reader came for, delivered in the wrong place or the wrong
# way (a genre guide's `## Cutting` section: in historical fiction, the
# period). It is moved or dramatised by the revise, never removed here,
# whatever `--types` says.
HELD_TYPES: frozenset[str] = frozenset({"MISPLACED"})
HELD_ACTIONS: frozenset[str] = frozenset({"MOVE"})
MIN_QUOTE_LEN = 25


@dataclass(frozen=True)
class CutStats:
    applied: int = 0
    failed: int = 0
    skipped: int = 0
    rewritten: int = 0     # REWRITE cuts applied as replacements
    held: tuple[str, ...] = ()  # MISPLACED / MOVE candidates kept for the brief
    words_removed: int = 0
    original_words: int = 0
    new_words: int = 0
    failures: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict:
        return {
            "applied": self.applied,
            "failed": self.failed,
            "skipped": self.skipped,
            "rewritten": self.rewritten,
            "held": [{"quote_preview": q} for q in self.held],
            "words_removed": self.words_removed,
            "original_words": self.original_words,
            "new_words": self.new_words,
            "failures": [{"reason": r, "quote_preview": q} for r, q in self.failures],
        }


def find_and_remove(text: str, quote: str, replacement: str = "") -> tuple[str, bool, str]:
    """Return (new_text, success, reason): `quote` removed, or replaced by
    `replacement` when one is given.

    Exact match first, then whitespace-normalised; ambiguous matches refuse.
    """
    count = text.count(quote)
    if count == 1:
        return text.replace(quote, replacement, 1), True, ""
    if count > 1:
        return text, False, f"ambiguous ({count} matches)"

    norm_quote = re.sub(r"\s+", " ", quote).strip()
    if len(norm_quote) < MIN_QUOTE_LEN:
        return text, False, "quote too short after normalisation"

    tokens = norm_quote.split(" ")
    pattern = r"\s+".join(re.escape(t) for t in tokens)
    matches = list(re.finditer(pattern, text))
    if len(matches) == 1:
        m = matches[0]
        return text[: m.start()] + replacement + text[m.end() :], True, ""
    if len(matches) > 1:
        return text, False, f"ambiguous after ws-norm ({len(matches)} matches)"
    return text, False, "not found"


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def apply_cuts(
    chapter_path: Path,
    cuts: list[dict],
    *,
    types: set[str] | None = None,
    min_fat: int = 0,
    overall_fat_percentage: int = 0,
    dry_run: bool = False,
) -> CutStats:
    """Apply a list of cut dicts (shape: {quote, type, reason, action, rewrite}).

    A `REWRITE` with a non-empty `rewrite` replaces the quote; any other
    cut removes it. A `MISPLACED` cut or a `MOVE` action is never applied:
    it is listed under `held` for the brief.

    Returns a CutStats report. Writes back to disk unless `dry_run`.
    """
    if overall_fat_percentage < min_fat:
        return CutStats(skipped=len(cuts))

    if not chapter_path.exists():
        return CutStats(failed=len(cuts), failures=(("chapter file not found", str(chapter_path)),))

    text = chapter_path.read_text(encoding="utf-8")
    original_words = len(text.split())

    applied = skipped = failed = words_removed = rewritten = 0
    failures: list[tuple[str, str]] = []
    held: list[str] = []

    for cut in cuts:
        quote = cut.get("quote", "")
        cut_type = cut.get("type", "UNKNOWN")
        action = str(cut.get("action") or "CUT").upper()
        replacement = ""
        if action == "REWRITE" and isinstance(cut.get("rewrite"), str):
            replacement = cut["rewrite"].strip()

        if cut_type in HELD_TYPES or action in HELD_ACTIONS:
            held.append(quote[:80].replace("\n", "\\n"))
            continue
        if types and cut_type not in types:
            skipped += 1
            continue
        if len(quote.strip()) < MIN_QUOTE_LEN:
            skipped += 1
            continue

        if dry_run:
            applied += 1
            rewritten += 1 if replacement else 0
            words_removed += len(quote.split()) - len(replacement.split())
            continue

        new_text, success, reason = find_and_remove(text, quote, replacement)
        if success:
            applied += 1
            rewritten += 1 if replacement else 0
            words_removed += len(quote.split()) - len(replacement.split())
            text = new_text
        else:
            failed += 1
            failures.append((reason, quote[:80].replace("\n", "\\n")))

    if not dry_run and applied:
        text = collapse_blank_lines(text)
        chapter_path.write_text(text, encoding="utf-8")

    new_words = len(text.split())
    return CutStats(
        applied=applied,
        failed=failed,
        skipped=skipped,
        rewritten=rewritten,
        held=tuple(held),
        words_removed=words_removed,
        original_words=original_words,
        new_words=new_words,
        failures=tuple(failures),
    )
