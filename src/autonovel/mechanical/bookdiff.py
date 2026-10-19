"""Reader-facing diff between two versions of a book.

`autonovel mechanical diff-chapters --book <name> [--from REF] [--to REF]`
shows what changed between two versions of a book's prose -- git
refs/tags, `.autonovel/checkpoints/` snapshots, or the working tree --
as one self-contained HTML page (plus a JSON sidecar) the author opens
in a browser. `git diff` on markdown is line-based, so a one-word trim
lights up a whole paragraph and there is no reading surface; this is
the reading surface.

Three layers, all `difflib`:

1. **Paragraph alignment.** Each file is split into paragraphs on blank
   lines; `SequenceMatcher` over the paragraph list finds the unchanged
   anchors. Each run of changed paragraphs between two anchors is one
   *hunk* -- the unit of next/prev navigation.
2. **Pairing inside a hunk.** The hunk's old and new paragraphs are
   paired by similarity (1:1, or 1:2 / 2:1 for a split or merged
   paragraph) with a monotonic DP that maximises the summed similarity
   ratio of the pairs, so a one-word edit shows as one inline change
   instead of a whole paragraph deleted and re-inserted, and a paragraph
   pushed down past newly written ones is still shown as an edit of
   itself. Unpaired paragraphs are pure deletions or insertions (and
   "moved" when the same text is deleted in one place and inserted in
   another).
3. **Word-level diff inside a pair.** Tokens are whitespace-split words
   with punctuation attached; `SequenceMatcher` over the token lists,
   then unchanged islands of one or two words between edits are folded
   into the edit and a semantic cleanup folds short coincidental
   equalities (a stray "the" inside a rewritten sentence), as
   diff-match-patch's ``cleanupSemantic`` does. A pair that kept too
   little of the old paragraph is shown *rewritten*: the new text, with
   the earlier draft in a fold.

The page has three views of one text -- Changes (unchanged runs
folded), Whole chapter, and Clean text (the new version only) -- and a
"big changes only" filter. Pure mechanical; no LLM.
`/autonovel:diff --annotate` adds a plain *what* note, a *why* and a
big/small flag per change by writing a sidecar JSON that ``--why``
feeds back in.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html as _html
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import checkpoints as _checkpoints
from ..paths import AUTONOVEL_DIR, CHAPTER_FILENAME_RE


DEFAULT_THRESHOLD = 0.4
"""Minimum `SequenceMatcher.ratio()` (over word tokens) for an old and a
new paragraph to be shown as one edited paragraph rather than a deletion
plus an insertion."""

PARA = " "
"""Paragraph-boundary token inside a paired group (U+2029 PARAGRAPH
SEPARATOR is whitespace to `re`, so it can never occur inside a word
token)."""

LB = "\n"
"""Hard line-break token (list items, table rows inside one block)."""

BOOKMARK_NAME = "last_read.json"

ISLAND_WORDS = 2
"""An unchanged run of at most this many words between two edits is
folded into them, so a reworded phrase reads as one change."""

REWRITE_RULES = ((0.5, 4), (0.6, 10))
"""``(kept, runs)``: a paired paragraph is shown rewritten -- the new
text, the earlier draft folded away -- when under ``kept`` of the old
paragraph's words survive and the diff has at least ``runs`` deleted or
inserted runs (interleaved fragments that dense are unreadable)."""

BIG_WORDS = 40
"""Without annotations, a change is "big" (kept by the big-changes
filter) when it adds plus removes at least this many words, or moves a
paragraph."""

# Frontmatter keys that change on every revision and say nothing to a
# reader (word_count is recomputed by the pipeline).
_IGNORED_FRONTMATTER_KEYS = frozenset({"word_count"})

_TOKEN_RE = re.compile(r"\n|[^\s]+")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")
# Lines that start their own visual line in markdown (list item, table
# row, heading, blockquote). Every other line is a soft-wrapped
# continuation of the previous one.
_BLOCK_LINE_RE = re.compile(r"^(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|>|\|)")
_CHAPTER_NUM_RE = re.compile(r"^ch_(\d+)\.md$")
_HEX_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_WORDISH_RE = re.compile(r"\w")


class DiffError(Exception):
    """A user-facing resolution error (bad ref, no git, no checkpoint)."""


# ===================================================================
# Text model
# ===================================================================


def _normalise_paragraph(raw: str) -> str:
    lines = [" ".join(ln.split()) for ln in raw.split("\n")]
    out: list[str] = []
    for ln in lines:
        if not ln:
            continue
        if out and not _BLOCK_LINE_RE.match(ln):
            out[-1] = out[-1] + " " + ln
        else:
            out.append(ln)
    return "\n".join(out)


def split_paragraphs(text: str) -> list[str]:
    """Split a markdown body into normalised paragraphs.

    Paragraphs are separated by blank lines. Inside a paragraph,
    whitespace runs collapse to one space and soft-wrapped lines are
    joined; lines that start a list item / table row / heading /
    blockquote keep their own line, so foundation files (canon.md
    bullet lists) diff line-by-line inside a block.
    """
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    for chunk in _PARA_SPLIT_RE.split(body):
        p = _normalise_paragraph(chunk)
        if p:
            out.append(p)
    return out


def tokenize(paragraph: str) -> list[str]:
    """Words with punctuation attached, plus `LB` for kept line breaks."""
    return _TOKEN_RE.findall(paragraph)


def _word_count_tokens(tokens: list[str]) -> int:
    return sum(1 for t in tokens if t not in (PARA, LB))


def _word_count_paras(paras: list[str]) -> int:
    return sum(_word_count_tokens(tokenize(p)) for p in paras)


def _join_tokens(groups: list[list[str]]) -> list[str]:
    out: list[str] = []
    for k, toks in enumerate(groups):
        if k:
            out.append(PARA)
        out.extend(toks)
    return out


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return ``(frontmatter_dict, body)``. Non-YAML / malformed
    frontmatter yields an empty dict and the text after the fence."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            raw = "".join(lines[1:i])
            body = "".join(lines[i + 1:])
            try:
                import yaml
                data = yaml.safe_load(raw) or {}
            except Exception:  # noqa: BLE001 -- display-only metadata
                data = {}
            return (data if isinstance(data, dict) else {}), body
    return {}, text


def _jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return str(v)


# ===================================================================
# Word-level diff
# ===================================================================


@dataclass
class Seg:
    """One run of a token-level diff: ``eq`` (old == new) or ``chg``
    (``old`` tokens deleted, ``new`` tokens inserted)."""
    tag: str
    old: list[str]
    new: list[str]


def _clen(tokens: list[str]) -> int:
    return sum(len(t) + 1 for t in tokens)


def _cleanup_semantic(segs: list[Seg]) -> list[Seg]:
    """Fold short equalities sandwiched between two edits into one edit.

    diff-match-patch's rule: an equality no longer (in characters) than
    the larger side of the edit on *each* side of it is coincidence, not
    shared text -- showing it as kept makes a rewritten sentence read as
    confetti. Equalities that carry a paragraph boundary are never
    folded (the boundary is structure the reader needs to see)."""
    changed = True
    while changed:
        changed = False
        for k in range(1, len(segs) - 1):
            s = segs[k]
            if s.tag != "eq" or PARA in s.old:
                continue
            prev, nxt = segs[k - 1], segs[k + 1]
            if prev.tag != "chg" or nxt.tag != "chg":
                continue
            el = _clen(s.old)
            if (el <= max(_clen(prev.old), _clen(prev.new))
                    and el <= max(_clen(nxt.old), _clen(nxt.new))):
                segs[k - 1:k + 2] = [Seg(
                    "chg", prev.old + s.old + nxt.old, prev.new + s.new + nxt.new,
                )]
                changed = True
                break
    return segs


def _fold_islands(segs: list[Seg]) -> list[Seg]:
    """Fold an unchanged run of at most `ISLAND_WORDS` words (tokens with
    no letter or digit don't count) sitting between two edits into one
    edit, so "the old man" -> "an old woman" reads as one phrase, not
    three fragments. Runs that hold a paragraph or line break stay."""
    out: list[Seg] = []
    for k, s in enumerate(segs):
        island = (
            s.tag == "eq" and k + 1 < len(segs) and segs[k + 1].tag == "chg"
            and bool(out) and out[-1].tag == "chg"
            and PARA not in s.old and LB not in s.old
            and sum(1 for t in s.old if _WORDISH_RE.search(t)) <= ISLAND_WORDS
        )
        if island or (s.tag == "chg" and out and out[-1].tag == "chg"):
            out[-1] = Seg("chg", out[-1].old + s.old, out[-1].new + s.new)
        else:
            out.append(Seg(s.tag, list(s.old), list(s.new)))
    return out


def word_diff(old_tokens: list[str], new_tokens: list[str]) -> list[Seg]:
    """Token-level diff, small islands folded, with semantic cleanup."""
    sm = difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False)
    segs: list[Seg] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            segs.append(Seg("eq", old_tokens[i1:i2], new_tokens[j1:j2]))
        elif segs and segs[-1].tag == "chg":
            segs[-1].old.extend(old_tokens[i1:i2])
            segs[-1].new.extend(new_tokens[j1:j2])
        else:
            segs.append(Seg("chg", list(old_tokens[i1:i2]), list(new_tokens[j1:j2])))
    return _cleanup_semantic(_fold_islands(segs))


def _seg_counts(segs: list[Seg]) -> tuple[int, int]:
    added = sum(_word_count_tokens(s.new) for s in segs if s.tag == "chg")
    removed = sum(_word_count_tokens(s.old) for s in segs if s.tag == "chg")
    return added, removed


def is_rewritten(segs: list[Seg]) -> bool:
    """True when a paired paragraph kept so little of its old words, in
    so many fragments, that it reads better as new text (`REWRITE_RULES`)."""
    old_words = sum(_word_count_tokens(s.old) for s in segs)
    if not old_words:
        return False
    kept = sum(_word_count_tokens(s.new) for s in segs if s.tag == "eq") / old_words
    runs = sum(bool(_word_count_tokens(s.old)) + bool(_word_count_tokens(s.new))
               for s in segs if s.tag == "chg")
    return any(kept < k and runs >= r for k, r in REWRITE_RULES)


# ===================================================================
# Paragraph pairing inside a hunk
# ===================================================================


def _ratio(sm: difflib.SequenceMatcher, threshold: float) -> float | None:
    """``sm.ratio()`` when it reaches ``threshold``, else None; the two
    cheap upper bounds reject most unrelated paragraphs first."""
    if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
        return None
    r = sm.ratio()
    return r if r >= threshold else None


def _similarities(old_toks: list[list[str]], new_toks: list[list[str]],
                  threshold: float) -> dict[tuple[int, int], float]:
    """Every 1:1 old/new paragraph ratio that reaches ``threshold``.
    One matcher per new paragraph, so its index is built once."""
    out: dict[tuple[int, int], float] = {}
    sm = difflib.SequenceMatcher(None, autojunk=False)
    for j, b in enumerate(new_toks):
        if not b:
            continue
        sm.set_seq2(b)
        for i, a in enumerate(old_toks):
            if a:
                sm.set_seq1(a)
                r = _ratio(sm, threshold)
                if r is not None:
                    out[(i, j)] = r
    return out


def pair_paragraphs(old_toks: list[list[str]], new_toks: list[list[str]],
                    *, threshold: float = DEFAULT_THRESHOLD,
                    ) -> list[tuple[str, list[int], list[int]]]:
    """Align the old and new paragraphs of one hunk.

    Returns display-ordered items ``(kind, old_indices, new_indices)``
    with kind ``pair`` (1:1, 1:2 split, 2:1 merge), ``del`` or ``ins``.
    A monotonic DP maximises the summed similarity ratio of the pairs
    (each at least ``threshold``), over the whole hunk: a paragraph that
    moved down past newly written ones still pairs with its new self. A
    split or merge scores the ratio of the joined text, so it only beats
    a 1:1 pair when the joined text really is more alike -- a neighbour
    that merely shares a few words is not glued on -- and is only tried
    beside a 1:1 pair that passed. Ties prefer a 1:1 pair, then
    deletions before insertions.
    """
    n, m = len(old_toks), len(new_toks)
    if n == 0:
        return [("ins", [], [j]) for j in range(m)]
    if m == 0:
        return [("del", [i], []) for i in range(n)]
    sims = _similarities(old_toks, new_toks, threshold)
    joined: dict[tuple[int, int, int, int], float | None] = {}

    def group(i0: int, i1: int, j0: int, j1: int) -> float | None:
        key = (i0, i1, j0, j1)
        if key not in joined:
            joined[key] = _ratio(difflib.SequenceMatcher(
                None, _join_tokens(old_toks[i0:i1]), _join_tokens(new_toks[j0:j1]),
                autojunk=False), threshold)
        return joined[key]

    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    move: list[list[tuple[str, int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if i == n and j == m:
                continue
            # (score, priority, move) -- max() picks the highest score
            # (rounded, so float noise never beats a preference), then
            # the highest priority.
            cands: list[tuple[float, int, tuple[str, int, int]]] = []
            if i < n and j < m:
                g = sims.get((i, j))
                if g is not None:
                    cands.append((best[i + 1][j + 1] + g, 0, ("pair", 1, 1)))
                if j + 1 < m and (g is not None or (i, j + 1) in sims):
                    g2 = group(i, i + 1, j, j + 2)
                    if g2 is not None:
                        cands.append((best[i + 1][j + 2] + g2, -1, ("pair", 1, 2)))
                if i + 1 < n and (g is not None or (i + 1, j) in sims):
                    g2 = group(i, i + 2, j, j + 1)
                    if g2 is not None:
                        cands.append((best[i + 2][j + 1] + g2, -1, ("pair", 2, 1)))
            if i < n:
                cands.append((best[i + 1][j], -2, ("del", 1, 0)))
            if j < m:
                cands.append((best[i][j + 1], -3, ("ins", 0, 1)))
            score, _, mv = max(cands, key=lambda c: (round(c[0], 9), c[1]))
            best[i][j] = score
            move[i][j] = mv
    items: list[tuple[str, list[int], list[int]]] = []
    i = j = 0
    while i < n or j < m:
        kind, di, dj = move[i][j]  # type: ignore[misc]
        items.append((kind, list(range(i, i + di)), list(range(j, j + dj))))
        i += di
        j += dj
    return items


# ===================================================================
# Inline HTML rendering
# ===================================================================


_HEADING_TOKEN_RE = re.compile(r"^#{1,6}$")
_BREAK_RE = re.compile(r"^(?:(?:\*\s*){3,}|(?:-\s*){3,}|⁂|#)$")
_STARS_RE = re.compile(r"(\*+)")
_ONLY_STARS_RE = re.compile(r"^\*+$")

EM, STRONG = 1, 2
_STAR_STYLE = {1: EM, 2: STRONG, 3: EM | STRONG}

Pieces = list[tuple[str, int]]
"""One token as ``(text, style)`` runs, emphasis markers dropped."""


def _esc(s: str) -> str:
    return _html.escape(s, quote=True)


def _emphasis(tokens: list[str]) -> list[Pieces]:
    """Markdown emphasis, token by token: each token becomes its
    ``(text, style)`` pieces with the asterisks dropped (style bits `EM`,
    `STRONG`; ``*`` toggles italic, ``**`` bold, ``***`` both).

    Working on tokens, not on the rendered HTML, keeps an italic span
    that an insertion cuts through italic on both sides of the cut.
    Emphasis never runs past a paragraph or line break; a line whose
    markers don't balance keeps its asterisks as text, and so does a
    token that is only asterisks (a ``* * *`` break, a list bullet)."""
    out: list[Pieces] = [[(t, 0)] for t in tokens]
    start = 0
    for end in range(len(tokens) + 1):
        if end < len(tokens) and tokens[end] not in (PARA, LB):
            continue
        style = 0
        line: list[Pieces] = []
        for t in tokens[start:end]:
            if "*" not in t or _ONLY_STARS_RE.match(t):
                line.append([(t, style)])
                continue
            pieces: Pieces = []
            for part in _STARS_RE.split(t):
                if part.startswith("*") and len(part) in _STAR_STYLE:
                    style ^= _STAR_STYLE[len(part)]
                elif part:
                    pieces.append((part, style))
            line.append(pieces)
        if not style:  # balanced: keep it; else the asterisks stay text
            out[start:end] = line
        start = end + 1
    return out


def _pieces_html(tokens: list[Pieces]) -> str:
    """Escape a run of tokens (joined by spaces) and wrap each stretch of
    one style in ``<em>`` / ``<strong>``; `LB` tokens become ``<br>``."""
    chunks: list[tuple[str, int]] = []
    for k, pieces in enumerate(tokens):
        if k and pieces and chunks:
            # The space between two italic words is italic too.
            chunks.append((" ", chunks[-1][1] & pieces[0][1] if chunks[-1][1] >= 0 else 0))
        for text, style in pieces:
            chunks.append(("<br>", -1) if text == LB else (text, style))
    out: list[str] = []
    k = 0
    while k < len(chunks):
        style = chunks[k][1]
        if style < 0:
            out.append(chunks[k][0])
            k += 1
            continue
        run: list[str] = []
        while k < len(chunks) and chunks[k][1] == style:
            run.append(chunks[k][0])
            k += 1
        text = _esc("".join(run))
        if style & EM:
            text = f"<em>{text}</em>"
        if style & STRONG:
            text = f"<strong>{text}</strong>"
        out.append(text)
    return "".join(out)


def md_inline_html(text: str) -> str:
    """One line of markdown (a note, a snippet) as escaped HTML with its
    emphasis rendered."""
    return _pieces_html(_emphasis(tokenize(" ".join(text.split()))))


def _plain(pieces: Pieces) -> str:
    return "".join(t for t, _ in pieces)


def _styled(segs: list[Seg]) -> list[tuple[list[Pieces], list[Pieces]]]:
    """Per segment, the emphasis pieces of its old and new tokens, worked
    out over each side's whole text (an unchanged run takes the new
    side's styling, as it reads in the new version)."""
    old_side = _emphasis([t for s in segs for t in s.old])
    new_side = _emphasis([t for s in segs for t in s.new])
    out: list[tuple[list[Pieces], list[Pieces]]] = []
    oi = ni = 0
    for s in segs:
        out.append((old_side[oi:oi + len(s.old)], new_side[ni:ni + len(s.new)]))
        oi += len(s.old)
        ni += len(s.new)
    return out


def render_segments(segs: list[Seg], *, para_class: str = "",
                    tag_html: str = "") -> list[str]:
    """Render token segments as one or more ``<p>`` elements.

    A `PARA` token inside an ``eq`` run is an unchanged paragraph break;
    inside a deletion it is a merged break (shown as a struck pilcrow,
    text continues in the same paragraph); inside an insertion it is a
    new break (an inserted pilcrow, then a new paragraph).
    """
    out: list[str] = []
    parts: list[str] = []
    kinds: set[str] = set()
    plain: list[str] = []

    def flush() -> None:
        if not parts:
            return
        if kinds <= {"eq"}:
            cls = "p-eq"
        elif kinds <= {"ins"}:
            cls = "p-ins"
        elif kinds <= {"del"}:
            cls = "p-del"
        else:
            cls = "p-chg"
        classes = [cls]
        if para_class:
            classes.append(para_class)
        text = " ".join(plain).strip()
        if plain and _HEADING_TOKEN_RE.match(plain[0]):
            classes.append("md-h")
        elif _BREAK_RE.match(text):
            classes.append("md-break")
        out.append(f'<p class="{" ".join(classes)}">{tag_html}{" ".join(parts)}</p>')
        parts.clear()
        kinds.clear()
        plain.clear()

    def run(tokens: list[str], styled: list[Pieces], tag: str) -> None:
        buf: list[Pieces] = []

        def emit() -> None:
            if buf:
                inner = _pieces_html(buf)
                parts.append(inner if tag == "eq" else f"<{tag}>{inner}</{tag}>")
                kinds.add(tag)
                buf.clear()

        for t, pieces in zip(tokens, styled):
            if t == PARA:
                emit()
                if tag == "eq":
                    flush()
                elif tag == "del":
                    parts.append('<del class="pilcrow" title="paragraph break removed">¶</del>')
                    kinds.add("del")
                else:
                    parts.append('<ins class="pilcrow" title="paragraph break added">¶</ins>')
                    kinds.add("ins")
                    flush()
            else:
                buf.append(pieces)
                if t != LB:
                    plain.append(t)
        emit()

    for s, (old_styled, new_styled) in zip(segs, _styled(segs)):
        if s.tag == "eq":
            run(s.new, new_styled, "eq")
        else:
            run(s.old, old_styled, "del")
            run(s.new, new_styled, "ins")
    flush()
    return out


def render_plain_paragraph(p: str, *, extra_class: str = "") -> str:
    """An unchanged paragraph as one ``<p class="p-eq ...">``."""
    toks = tokenize(p)
    return render_segments([Seg("eq", toks, toks)], para_class=extra_class)[0]


def _split_at_para(tokens: list[str]) -> list[list[str]]:
    groups: list[list[str]] = [[]]
    for t in tokens:
        if t == PARA:
            groups.append([])
        else:
            groups[-1].append(t)
    return [g for g in groups if g]


def render_rewritten(old_tokens: list[str], new_tokens: list[str]) -> list[str]:
    """A paragraph rewritten past inline marking (`is_rewritten`): its
    new text, marked new, then the earlier draft in a closed fold."""
    out: list[str] = []
    for g in _split_at_para(new_tokens):
        out += render_segments([Seg("chg", [], g)], para_class="p-rewritten")
    old = "\n".join(render_segments([Seg("eq", old_tokens, old_tokens)], para_class="p-old"))
    out.append('<details class="earlier"><summary>Rewritten — show the earlier '
               f'draft</summary>{old}</details>')
    return out


# ===================================================================
# File diff
# ===================================================================


@dataclass
class Hunk:
    id: str
    key: str
    file: str
    chapter: int | None
    kind: str                  # chapter | summary | foundation
    index: int                 # paragraph index in the NEW text
    old_index: int             # paragraph index in the OLD text
    old_paragraphs: list[str]
    new_paragraphs: list[str]
    inline_html: str
    words_added: int
    words_removed: int
    context_before: str | None
    context_after: str | None
    fp: str
    moved: int = 0             # paragraphs in this hunk that moved
    rewritten: int = 0         # paired paragraphs shown as rewritten
    n: int = 0                 # 1-based ordinal across the whole report
    # Annotations (`--why`): a plain note on what the change is, why it
    # was made, and whether the author would want to read it (None =
    # not annotated; `is_big` then falls back to its size).
    what: str | None = None
    why: str | None = None
    big: bool | None = None
    snippet: str = ""
    snippet_html: str = ""
    # The changed runs only, in reading order, as [old, new] pairs
    # ("" on one side for a pure deletion / insertion; a rewritten
    # paragraph is one whole [old, new] pair) -- what the annotation
    # step reads instead of whole paragraphs.
    changes: list[list[str]] = field(default_factory=list)

    @property
    def is_big(self) -> bool:
        if self.big is not None:
            return self.big
        return self.words_added + self.words_removed >= BIG_WORDS or self.moved > 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "n": self.n, "key": self.key, "file": self.file,
            "chapter": self.chapter, "kind": self.kind,
            "index": self.index, "old_index": self.old_index,
            "old_paragraphs": self.old_paragraphs,
            "new_paragraphs": self.new_paragraphs,
            "changes": self.changes,
            "inline_html": self.inline_html,
            "words_added": self.words_added,
            "words_removed": self.words_removed,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "moved": self.moved, "rewritten": self.rewritten, "fp": self.fp,
            "what": self.what, "why": self.why,
            "big": self.is_big, "big_source": "note" if self.big is not None else "size",
            "snippet": self.snippet,
        }


@dataclass
class FileDiff:
    key: str
    file: str
    kind: str
    label: str
    chapter: int | None
    status: str                # added | removed | changed | unchanged
    title: str | None
    words_old: int
    words_new: int
    words_added: int
    words_removed: int
    frontmatter_changes: dict[str, list]
    hunks: list[Hunk]
    # Display flow, new-text order: ("equal", [paragraphs]) | ("hunk", Hunk)
    flow: list[tuple[str, Any]] = field(default_factory=list)
    why: str | None = None

    @property
    def net(self) -> int:
        return self.words_new - self.words_old

    def to_dict(self) -> dict:
        return {
            "key": self.key, "file": self.file, "kind": self.kind,
            "label": self.label, "chapter": self.chapter,
            "status": self.status, "title": self.title,
            "hunks": len(self.hunks),
            "words_old": self.words_old, "words_new": self.words_new,
            "words_added": self.words_added,
            "words_removed": self.words_removed, "net": self.net,
            "frontmatter_changes": self.frontmatter_changes,
            "why": self.why,
        }


def _fingerprint(old: list[str], new: list[str]) -> str:
    h = hashlib.sha1()
    h.update("\x1e".join(old).encode("utf-8"))
    h.update(b"\x1d")
    h.update("\x1e".join(new).encode("utf-8"))
    return h.hexdigest()[:10]


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _words(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in (PARA, LB)]


def _word_pieces(tokens: list[str], styled: list[Pieces]) -> list[Pieces]:
    return [p for t, p in zip(tokens, styled) if t not in (PARA, LB)]


def _clip_pieces(toks: list[Pieces], limit: int, lead: str = "") -> tuple[str, str]:
    """As many whole words as fit in ``limit`` characters, as
    ``(text, html)``; "…" marks a cut."""
    keep: list[Pieces] = []
    size = len(lead)
    for p in toks:
        w = len(_plain(p)) + (1 if keep else 0)
        if keep and size + w > limit:
            break
        keep.append(p)
        size += w
    text = lead + " ".join(_plain(p) for p in keep)
    html = _esc(lead) + _pieces_html(keep)
    if len(keep) < len(toks):
        text, html = text + "…", html + "…"
    return text, html


def _snippet(segs: list[Seg], limit: int = 60) -> tuple[str, str]:
    """Locator for the change list, as ``(text, html)``: the first changed
    words with two or three words of unchanged context either side,
    emphasis rendered in the html and dropped from the text."""
    styled = _styled(segs)
    for k, s in enumerate(segs):
        if s.tag != "chg":
            continue
        changed = (_word_pieces(s.new, styled[k][1])
                   or _word_pieces(s.old, styled[k][0]))
        if not changed:
            continue
        before = _word_pieces(segs[k - 1].new, styled[k - 1][1])[-3:] if k > 0 else []
        after = (_word_pieces(segs[k + 1].new, styled[k + 1][1])[:2]
                 if k + 1 < len(segs) else [])
        return _clip_pieces(before + changed[:8] + after, limit,
                            lead="… " if before else "")
    return "", ""


def _lead(paragraph: str, limit: int) -> tuple[str, str]:
    """The opening words of a paragraph, as ``(text, html)``."""
    toks = tokenize(paragraph)
    return _clip_pieces(_word_pieces(toks, _emphasis(toks)), limit)


def diff_file(old_text: str | None, new_text: str | None, *, key: str,
              file: str, kind: str, label: str, chapter: int | None = None,
              threshold: float = DEFAULT_THRESHOLD) -> FileDiff:
    """Diff one file's two versions (``None`` = absent on that side)."""
    old_fm, old_body = split_frontmatter(old_text) if old_text is not None else ({}, "")
    new_fm, new_body = split_frontmatter(new_text) if new_text is not None else ({}, "")
    old_paras = split_paragraphs(old_body)
    new_paras = split_paragraphs(new_body)
    old_toks = [tokenize(p) for p in old_paras]
    new_toks = [tokenize(p) for p in new_paras]

    fm_changes: dict[str, list] = {}
    if old_text is not None and new_text is not None:
        for k in sorted(set(old_fm) | set(new_fm), key=str):
            if str(k) in _IGNORED_FRONTMATTER_KEYS:
                continue
            if old_fm.get(k) != new_fm.get(k):
                fm_changes[str(k)] = [_jsonable(old_fm.get(k)), _jsonable(new_fm.get(k))]

    sm = difflib.SequenceMatcher(None, old_paras, new_paras, autojunk=False)
    blocks: list[dict] = []
    raw_flow: list[tuple[str, Any]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            raw_flow.append(("equal", new_paras[j1:j2]))
            continue
        items = pair_paragraphs(old_toks[i1:i2], new_toks[j1:j2], threshold=threshold)
        blocks.append({"i1": i1, "i2": i2, "j1": j1, "j2": j2, "items": items})
        raw_flow.append(("hunk", len(blocks) - 1))

    # Moved paragraphs: the same text wholly deleted in one place and
    # wholly inserted in another.
    deleted: set[str] = set()
    inserted: set[str] = set()
    for b in blocks:
        for kind_, ii, jj in b["items"]:
            if kind_ == "del":
                deleted.add(old_paras[b["i1"] + ii[0]])
            elif kind_ == "ins":
                inserted.add(new_paras[b["j1"] + jj[0]])
    moved_texts = deleted & inserted

    hunks: list[Hunk] = []
    for bi, b in enumerate(blocks):
        i1, i2, j1, j2 = b["i1"], b["i2"], b["j1"], b["j2"]
        html_parts: list[str] = []
        added = removed = moved = rewritten = 0
        snippet: tuple[str, str] = ("", "")
        changes: list[list[str]] = []
        for kind_, ii, jj in b["items"]:
            if kind_ == "pair":
                old_g = _join_tokens([old_toks[i1 + i] for i in ii])
                new_g = _join_tokens([new_toks[j1 + j] for j in jj])
                segs = word_diff(old_g, new_g)
                a, r = _seg_counts(segs)
                added += a
                removed += r
                snippet = snippet if snippet[0] else _snippet(segs)
                if is_rewritten(segs):
                    html_parts += render_rewritten(old_g, new_g)
                    rewritten += 1
                    changes.append([" ".join(_words(old_g)), " ".join(_words(new_g))])
                    continue
                html_parts += render_segments(segs)
                for s in segs:
                    if s.tag == "chg" and (_words(s.old) or _words(s.new)):
                        changes.append([" ".join(_words(s.old)), " ".join(_words(s.new))])
            elif kind_ == "del":
                toks = old_toks[i1 + ii[0]]
                is_moved = old_paras[i1 + ii[0]] in moved_texts
                html_parts += render_segments(
                    [Seg("chg", toks, [])],
                    para_class="p-moved" if is_moved else "",
                    tag_html='<span class="tag">moved from here</span> ' if is_moved else "",
                )
                if is_moved:
                    moved += 1
                else:
                    removed += _word_count_tokens(toks)
                    changes.append([" ".join(_words(toks)), ""])
                snippet = snippet if snippet[0] else _snippet([Seg("chg", toks, [])])
            else:
                toks = new_toks[j1 + jj[0]]
                is_moved = new_paras[j1 + jj[0]] in moved_texts
                html_parts += render_segments(
                    [Seg("chg", [], toks)],
                    para_class="p-moved" if is_moved else "",
                    tag_html='<span class="tag">moved here</span> ' if is_moved else "",
                )
                if is_moved:
                    moved += 1
                else:
                    added += _word_count_tokens(toks)
                    changes.append(["", " ".join(_words(toks))])
                snippet = snippet if snippet[0] else _snippet([Seg("chg", [], toks)])
        hunks.append(Hunk(
            id=f"{key}-{bi + 1:03d}", key=key, file=file, chapter=chapter,
            kind=kind, index=j1, old_index=i1,
            old_paragraphs=old_paras[i1:i2], new_paragraphs=new_paras[j1:j2],
            inline_html="\n".join(html_parts),
            words_added=added, words_removed=removed,
            context_before=new_paras[j1 - 1] if j1 > 0 else None,
            context_after=new_paras[j2] if j2 < len(new_paras) else None,
            fp=_fingerprint(old_paras[i1:i2], new_paras[j1:j2]),
            moved=moved, rewritten=rewritten,
            snippet=snippet[0], snippet_html=snippet[1],
            changes=changes,
        ))

    flow: list[tuple[str, Any]] = [
        (k, hunks[v] if k == "hunk" else v) for k, v in raw_flow
    ]
    if old_text is None and new_text is not None:
        status = "added"
    elif new_text is None and old_text is not None:
        status = "removed"
    elif hunks or fm_changes:
        status = "changed"
    else:
        status = "unchanged"
    title = new_fm.get("title") or old_fm.get("title")
    return FileDiff(
        key=key, file=file, kind=kind, label=label, chapter=chapter,
        status=status, title=str(title) if title else None,
        words_old=sum(_word_count_tokens(t) for t in old_toks),
        words_new=sum(_word_count_tokens(t) for t in new_toks),
        words_added=sum(h.words_added for h in hunks),
        words_removed=sum(h.words_removed for h in hunks),
        frontmatter_changes=fm_changes, hunks=hunks, flow=flow,
    )


# ===================================================================
# Snapshots: git ref, working tree, checkpoint
# ===================================================================


def _git(series_root: Path, *args: str, input_bytes: bytes | None = None,
         ) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(series_root), input=input_bytes,
        capture_output=True, check=False,
    )


def _git_out(series_root: Path, *args: str) -> str | None:
    try:
        proc = _git(series_root, *args)
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace").strip()


def is_git_repo(series_root: Path) -> bool:
    return _git_out(series_root, "rev-parse", "--is-inside-work-tree") == "true"


def resolve_commit(series_root: Path, ref: str) -> str | None:
    if not ref or ref.startswith("-"):
        return None
    return _git_out(series_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")


def _uncommitted(series_root: Path, *paths: str) -> bool:
    """True when any of *paths* has uncommitted edits. Read-only:
    ``--no-optional-locks`` keeps `git status` from rewriting the index."""
    st = _git_out(series_root, "--no-optional-locks", "status", "--porcelain", "--", *paths)
    return bool(st)


def _commit_meta(series_root: Path, sha: str) -> dict:
    out = _git_out(series_root, "log", "-1", "--format=%h%x1f%cI%x1f%s", sha)
    if not out:
        return {}
    short, date, subject = (out.split("\x1f") + ["", "", ""])[:3]
    return {"short": short, "date": date, "subject": subject}


class Snapshot:
    """One side of the diff."""

    kind = "base"

    def __init__(self, *, spec: str, label: str, description: str,
                 sha: str | None = None, note: str | None = None) -> None:
        self.spec = spec
        self.label = label
        self.description = description
        self.sha = sha
        self.note = note
        self.meta: dict = {}
        # True when `last-read` resolved to the author's bookmark (not
        # to its last-tag fallback).
        self.from_bookmark = False

    def read(self, rel: str) -> str | None:  # pragma: no cover - abstract
        raise NotImplementedError

    def read_many(self, rels: list[str]) -> dict[str, str | None]:
        return {r: self.read(r) for r in rels}

    def chapter_files(self, book: str) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    @property
    def pinned(self) -> str:
        """A --from/--to value that names exactly this version again
        (``last-read`` / ``last-tag`` move; a sha does not)."""
        return self.sha or self.spec

    def to_dict(self) -> dict:
        return {
            "spec": self.spec, "kind": self.kind, "label": self.label,
            "description": self.description, "sha": self.sha,
            "pinned": self.pinned, "note": self.note,
            "from_bookmark": self.from_bookmark, **self.meta,
        }


class WorktreeSnapshot(Snapshot):
    kind = "worktree"

    def __init__(self, series_root: Path, *, spec: str = "worktree") -> None:
        super().__init__(spec=spec, label="worktree", description="working tree")
        self.series_root = series_root

    @property
    def pinned(self) -> str:
        return "worktree"

    def read(self, rel: str) -> str | None:
        p = self.series_root / rel
        if not p.is_file():
            return None
        return p.read_text(encoding="utf-8", errors="replace")

    def chapter_files(self, book: str) -> list[str]:
        d = self.series_root / "books" / book / "chapters"
        if not d.is_dir():
            return []
        return sorted(
            f"books/{book}/chapters/{p.name}" for p in d.iterdir()
            if p.is_file() and CHAPTER_FILENAME_RE.match(p.name)
        )


class GitSnapshot(Snapshot):
    kind = "git"

    def __init__(self, series_root: Path, sha: str, *, spec: str, label: str,
                 description: str, note: str | None = None) -> None:
        super().__init__(spec=spec, label=label, description=description,
                         sha=sha, note=note)
        self.series_root = series_root
        self.prefix = _git_out(series_root, "rev-parse", "--show-prefix") or ""
        self.meta = _commit_meta(series_root, sha)
        self._cache: dict[str, str | None] = {}

    def read(self, rel: str) -> str | None:
        return self.read_many([rel])[rel]

    def read_many(self, rels: list[str]) -> dict[str, str | None]:
        missing = [r for r in rels if r not in self._cache]
        if missing:
            self._cache.update(self._cat_file_batch(missing))
        return {r: self._cache[r] for r in rels}

    def _cat_file_batch(self, rels: list[str]) -> dict[str, str | None]:
        """Read many blobs in one `git cat-file --batch` call."""
        spec = "".join(f"{self.sha}:{self.prefix}{r}\n" for r in rels).encode("utf-8")
        proc = _git(self.series_root, "cat-file", "--batch", input_bytes=spec)
        data = proc.stdout
        out: dict[str, str | None] = {}
        pos = 0
        for r in rels:
            nl = data.find(b"\n", pos)
            if nl < 0:
                out[r] = None
                continue
            header = data[pos:nl].decode("utf-8", errors="replace").split()
            pos = nl + 1
            if len(header) == 3 and header[2].isdigit():
                size = int(header[2])
                body = data[pos:pos + size]
                pos += size + 1  # trailing newline after the content
                out[r] = (body.decode("utf-8", errors="replace")
                          if header[1] == "blob" else None)
            else:  # "<spec> missing" / "ambiguous"
                out[r] = None
        return out

    def chapter_files(self, book: str) -> list[str]:
        out = _git_out(self.series_root, "ls-tree", "-r", "--name-only",
                       "--full-name", self.sha, "--",
                       f"books/{book}/chapters/")
        files: list[str] = []
        for line in (out or "").splitlines():
            rel = line[len(self.prefix):] if self.prefix and line.startswith(self.prefix) else line
            if CHAPTER_FILENAME_RE.match(rel.rsplit("/", 1)[-1]):
                files.append(rel)
        return sorted(files)


class CheckpointSnapshot(Snapshot):
    """The series as it stood just before the checkpointed command ran.

    A checkpoint only holds the files its command was about to write.
    The state of file F at checkpoint time T is the `.bak` (or `.absent`
    marker) in the *earliest* checkpoint at or after T that recorded F;
    a file no later checkpoint recorded is unchanged since T, so the
    working-tree copy is used.
    """

    kind = "checkpoint"

    def __init__(self, series_root: Path, cps: list[_checkpoints.Checkpoint], *,
                 spec: str) -> None:
        first = cps[0]
        super().__init__(
            spec=spec, label=f"checkpoint-{first.directory.name}",
            description=(f"checkpoint {first.directory.name} "
                         f"(before {first.command})"),
        )
        self.series_root = series_root
        self.cps = cps
        self.worktree = WorktreeSnapshot(series_root)
        self.meta = {"timestamp": first.timestamp, "command": first.command,
                     "args": list(first.args)}

    @property
    def pinned(self) -> str:
        return f"checkpoint:{self.cps[0].directory.name}"

    def read(self, rel: str) -> str | None:
        for cp in self.cps:
            if rel in cp.files:
                bak = cp.directory / (rel + ".bak")
                if bak.is_file():
                    return bak.read_text(encoding="utf-8", errors="replace")
                return None  # `.absent` marker: the file did not exist yet
        return self.worktree.read(rel)

    def chapter_files(self, book: str) -> list[str]:
        prefix = f"books/{book}/chapters/"
        cands = set(self.worktree.chapter_files(book))
        for cp in self.cps:
            for f in cp.files:
                if f.startswith(prefix) and CHAPTER_FILENAME_RE.match(f[len(prefix):]):
                    cands.add(f)
        return sorted(c for c in cands if self.read(c) is not None)


def sanitize_ref(ref: str, *, limit: int = 60) -> str:
    """Make a ref/label safe for a filename: ``HEAD~3`` -> ``HEAD-3``,
    ``refs/tags/v1`` -> ``refs-tags-v1``, ``../x`` -> ``x``."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", ref.strip())
    s = s.replace("..", "-")
    s = re.sub(r"-{2,}", "-", s).strip("-.")
    s = s[:limit].rstrip("-.")
    return s or "ref"


def _bookmark_path(series_root: Path, book: str) -> Path:
    return series_root / "books" / book / "edit_logs" / BOOKMARK_NAME


def read_bookmark(series_root: Path, book: str) -> dict | None:
    p = _bookmark_path(series_root, book)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_bookmark(series_root: Path, book: str, snap: Snapshot, *,
                   now: datetime | None = None) -> dict:
    """Record ``snap`` as the version the author last read."""
    when = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(snap, CheckpointSnapshot):
        data = {"ref": f"checkpoint:{snap.cps[0].directory.name}", "sha": None}
    elif isinstance(snap, WorktreeSnapshot):
        head = resolve_commit(series_root, "HEAD") if is_git_repo(series_root) else None
        dirty = _uncommitted(series_root, f"books/{book}") if head else False
        data = {"ref": "HEAD", "sha": head, "worktree": True, "dirty": dirty}
    else:
        data = {"ref": snap.spec, "sha": snap.sha}
    data["when"] = when
    p = _bookmark_path(series_root, book)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"path": str(p), **data}


def _checkpoint_snapshot(series_root: Path, spec: str) -> CheckpointSnapshot:
    cp_dir = series_root / AUTONOVEL_DIR / "checkpoints"
    all_cps = _checkpoints.list_checkpoints(cp_dir)
    if spec.startswith("checkpoint:"):
        want = spec.split(":", 1)[1].strip()
        if not all_cps:
            raise DiffError(f"no checkpoints under {cp_dir}")
        if want in ("", "latest"):
            start = len(all_cps) - 1
        else:
            exact = [k for k, c in enumerate(all_cps) if c.directory.name == want]
            pref = [k for k, c in enumerate(all_cps) if c.directory.name.startswith(want)]
            if exact:
                start = exact[0]
            elif len(pref) == 1:
                start = pref[0]
            elif pref:
                raise DiffError(
                    f"checkpoint {want!r} is ambiguous: "
                    + ", ".join(all_cps[k].directory.name for k in pref[:6]))
            else:
                raise DiffError(f"no checkpoint named {want!r} under {cp_dir}")
        return CheckpointSnapshot(series_root, all_cps[start:], spec=spec)
    # A checkpoint directory path.
    d = Path(spec)
    if not d.is_absolute():
        d = (series_root / d) if (series_root / d).is_dir() else d.resolve()
    cp = _checkpoints.Checkpoint.from_manifest(d)
    later = [c for c in all_cps if c.directory.name > d.name
             and c.directory.resolve() != d.resolve()]
    return CheckpointSnapshot(series_root, [cp, *later], spec=spec)


def _looks_like_checkpoint_dir(series_root: Path, spec: str) -> bool:
    for d in (Path(spec), series_root / spec):
        if d.is_dir() and (d / _checkpoints.MANIFEST_NAME).is_file():
            return True
    return False


def _require_git(series_root: Path, what: str) -> None:
    if not is_git_repo(series_root):
        raise DiffError(
            f"{what} needs a git repository at {series_root}; "
            f"use --from checkpoint:latest (or checkpoint:<timestamp>) instead"
        )


def _first_chapter_commit(series_root: Path, book: str) -> str | None:
    out = _git_out(series_root, "log", "--reverse", "--format=%H", "--",
                   f"books/{book}/chapters")
    return out.splitlines()[0] if out else None


def _last_tag(series_root: Path, base_sha: str | None) -> str | None:
    base = base_sha or "HEAD"
    tag = _git_out(series_root, "describe", "--tags", "--abbrev=0", base)
    if tag and base_sha and resolve_commit(series_root, tag) == base_sha:
        # `--to` is itself tagged: "since the last tag" means the one before.
        tag = _git_out(series_root, "describe", "--tags", "--abbrev=0", f"{base_sha}^")
    return tag or None


def _git_snapshot_for_ref(series_root: Path, ref: str, *, spec: str,
                          note: str | None = None, label: str | None = None,
                          ) -> GitSnapshot:
    sha = resolve_commit(series_root, ref)
    if not sha:
        raise DiffError(
            f"unknown version {ref!r}: not a git ref/tag/commit, a checkpoint "
            f"(checkpoint:<timestamp> | checkpoint:latest), 'last-read', "
            f"'last-tag' or 'worktree'"
        )
    is_sha = bool(_HEX_SHA_RE.match(ref)) and sha.startswith(ref.lower())
    if label is None:
        label = sha[:7] if is_sha else sanitize_ref(ref)
    description = sha[:7] if is_sha else f"{ref} ({sha[:7]})"
    return GitSnapshot(series_root, sha, spec=spec, label=label,
                       description=description, note=note)


def _last_tag_snapshot(series_root: Path, book: str, to: Snapshot | None, *,
                       spec: str, note_prefix: str = "") -> GitSnapshot:
    _require_git(series_root, f"--from {spec}")
    base = to.sha if isinstance(to, GitSnapshot) else None
    tag = _last_tag(series_root, base)
    if tag:
        return _git_snapshot_for_ref(
            series_root, tag, spec=spec, label=sanitize_ref(tag),
            note=(note_prefix + f"last tag is {tag}").strip(),
        )
    first = _first_chapter_commit(series_root, book)
    if not first:
        raise DiffError(f"no tags and no commit touching books/{book}/chapters yet")
    return _git_snapshot_for_ref(
        series_root, first, spec=spec, label=first[:7],
        note=(note_prefix + "no tags yet; using the first commit that touched the chapters").strip(),
    )


def resolve_snapshot(series_root: Path, book: str, spec: str, *,
                     other: Snapshot | None = None) -> Snapshot:
    """Resolve a ``--from`` / ``--to`` value to a Snapshot.

    Accepts: ``worktree``; ``last-tag``; ``last-read``;
    ``checkpoint:<ts>`` / ``checkpoint:latest`` / a checkpoint dir; any
    git ref (tag, branch, sha, ``HEAD~3``). ``other`` is the already
    resolved opposite side (``last-tag`` looks for the tag before it).
    """
    spec = (spec or "").strip()
    if spec in ("worktree", "working-tree", "wt"):
        return WorktreeSnapshot(series_root, spec=spec)
    if spec == "last-tag":
        return _last_tag_snapshot(series_root, book, other, spec=spec)
    if spec == "last-read":
        bm = read_bookmark(series_root, book)
        if bm:
            ref = str(bm.get("ref") or "")
            sha = bm.get("sha")
            when = bm.get("when", "?")
            if ref.startswith("checkpoint:"):
                snap = _checkpoint_snapshot(series_root, ref)
                snap.label = f"last-read-{snap.label}"
                snap.note = f"last read {when}"
                snap.from_bookmark = True
                return snap
            for cand in (sha, ref):
                if cand and is_git_repo(series_root) and resolve_commit(series_root, str(cand)):
                    full = resolve_commit(series_root, str(cand)) or ""
                    snap = _git_snapshot_for_ref(
                        series_root, full, spec=spec, label=f"last-read-{full[:7]}",
                        note=f"last read {when} at {ref or full[:7]}",
                    )
                    snap.from_bookmark = True
                    return snap
            prefix = "last-read bookmark no longer resolves; "
        else:
            prefix = "no last-read bookmark yet; "
        return _last_tag_snapshot(series_root, book, other, spec=spec, note_prefix=prefix)
    if spec.startswith("checkpoint:") or _looks_like_checkpoint_dir(series_root, spec):
        return _checkpoint_snapshot(series_root, spec)
    _require_git(series_root, f"version {spec!r}")
    return _git_snapshot_for_ref(series_root, spec, spec=spec)


# ===================================================================
# Report
# ===================================================================


def parse_chapter_spec(spec: str | None) -> set[int] | None:
    """``"5"`` / ``"5-8"`` / ``"5,7"`` / ``"3-5,9"`` -> set of ints."""
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a), int(b)
            if lo > hi:
                lo, hi = hi, lo
            out.update(range(lo, hi + 1))
        else:
            out.add(int(part))
    return out


def _chapter_number(rel: str) -> int | None:
    m = _CHAPTER_NUM_RE.match(rel.rsplit("/", 1)[-1])
    return int(m.group(1)) if m else None


@dataclass
class DiffReport:
    book: str
    series_root: str
    old: Snapshot
    new: Snapshot
    chapters: list[FileDiff]
    foundation: list[FileDiff]
    threshold: float
    chapter_filter: list[int] | None
    generated: str
    why_applied: int = 0
    why_stale: list[str] = field(default_factory=list)

    @property
    def all_hunks(self) -> list[Hunk]:
        return [h for f in self.chapters + self.foundation for h in f.hunks]

    @property
    def changed_chapters(self) -> list[FileDiff]:
        return [f for f in self.chapters if f.status != "unchanged"]

    def totals(self) -> dict:
        ch = self.chapters
        return {
            "hunks": len(self.all_hunks),
            "big_hunks": sum(h.is_big for h in self.all_hunks),
            "chapter_hunks": sum(len(f.hunks) for f in ch),
            "foundation_hunks": sum(len(f.hunks) for f in self.foundation),
            "chapters_changed": len(self.changed_chapters),
            "chapters_compared": len(ch),
            "words_added": sum(f.words_added for f in ch),
            "words_removed": sum(f.words_removed for f in ch),
            "words_old": sum(f.words_old for f in ch),
            "words_new": sum(f.words_new for f in ch),
            "net_words": sum(f.net for f in ch),
        }

    def to_dict(self) -> dict:
        return {
            "book": self.book, "series_root": self.series_root,
            "from": self.old.to_dict(), "to": self.new.to_dict(),
            "generated": self.generated, "threshold": self.threshold,
            "chapter_filter": self.chapter_filter,
            **self.totals(),
            "why_applied": self.why_applied, "why_stale": self.why_stale,
            "chapters": [f.to_dict() for f in self.chapters],
            "foundation": [f.to_dict() for f in self.foundation],
            "hunks_detail": [h.to_dict() for h in self.all_hunks],
        }


def _foundation_targets(book: str) -> list[tuple[str, str, str]]:
    return [
        ("voice", f"books/{book}/voice.md", "voice.md"),
        ("outline", f"books/{book}/outline.md", "outline.md"),
        ("canon", f"books/{book}/canon.md", "canon.md (this book)"),
        ("shared-canon", "shared/canon.md", "shared/canon.md (series)"),
    ]


def build_diff(series_root: Path, book: str, *, from_spec: str = "last-tag",
               to_spec: str = "worktree", chapters: set[int] | None = None,
               foundation: bool | None = None,
               threshold: float = DEFAULT_THRESHOLD,
               now: datetime | None = None) -> DiffReport:
    """Diff every chapter (and, by default, its summary plus the book's
    voice / outline / canon and shared canon) between two versions."""
    series_root = Path(series_root)
    if not (series_root / "books" / book).is_dir():
        raise DiffError(f"no book {book!r} under {series_root / 'books'}")
    new = resolve_snapshot(series_root, book, to_spec)
    old = resolve_snapshot(series_root, book, from_spec, other=new)
    if foundation is None:
        foundation = chapters is None

    by_num: dict[int, tuple[str | None, str | None]] = {}
    for rel in old.chapter_files(book):
        n = _chapter_number(rel)
        if n is not None:
            by_num[n] = (rel, by_num.get(n, (None, None))[1])
    for rel in new.chapter_files(book):
        n = _chapter_number(rel)
        if n is not None:
            by_num[n] = (by_num.get(n, (None, None))[0], rel)
    nums = sorted(n for n in by_num if chapters is None or n in chapters)

    wanted: list[str] = []
    for n in nums:
        o, w = by_num[n]
        for rel in {o, w} - {None}:
            wanted += [rel, rel[:-3] + ".summary.md"]  # type: ignore[index]
    if foundation:
        wanted += [rel for _, rel, _ in _foundation_targets(book)]
    wanted = sorted(set(wanted))
    old_texts = old.read_many(wanted)
    new_texts = new.read_many(wanted)

    chapter_diffs: list[FileDiff] = []
    summary_diffs: list[FileDiff] = []
    for n in nums:
        o, w = by_num[n]
        rel = w or o or ""
        key = f"ch{n:02d}"
        old_t = old_texts.get(o) if o else None
        new_t = new_texts.get(w) if w else None
        chapter_diffs.append(diff_file(
            old_t, new_t, key=key, file=rel, kind="chapter",
            label=f"Chapter {n}", chapter=n, threshold=threshold,
        ))
        s_old = old_texts.get(o[:-3] + ".summary.md") if o else None
        s_new = new_texts.get(w[:-3] + ".summary.md") if w else None
        if s_old is not None or s_new is not None:
            sd = diff_file(
                s_old, s_new, key=f"{key}-summary", file=rel[:-3] + ".summary.md",
                kind="summary", label=f"Chapter {n} summary", chapter=n,
                threshold=threshold,
            )
            if sd.status != "unchanged":
                summary_diffs.append(sd)

    found_diffs: list[FileDiff] = []
    if foundation:
        for key, rel, label in _foundation_targets(book):
            o_t, n_t = old_texts.get(rel), new_texts.get(rel)
            if o_t is None and n_t is None:
                continue
            fd = diff_file(o_t, n_t, key=key, file=rel, kind="foundation",
                           label=label, threshold=threshold)
            if fd.status != "unchanged":
                found_diffs.append(fd)

    report = DiffReport(
        book=book, series_root=str(series_root), old=old, new=new,
        chapters=chapter_diffs, foundation=found_diffs + summary_diffs,
        threshold=threshold,
        chapter_filter=sorted(chapters) if chapters is not None else None,
        generated=(now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC"),
    )
    for k, h in enumerate(report.all_hunks, 1):
        h.n = k
    if isinstance(new, WorktreeSnapshot) and is_git_repo(series_root):
        head = resolve_commit(series_root, "HEAD")
        if head:
            new.meta = {"head": head, "head_short": head[:7],
                        "dirty": _uncommitted(series_root, f"books/{book}", "shared/canon.md")}
    return report


def unread_reason(report: DiffReport, book: str) -> str | None:
    """Why there is nothing to hand back to the author, or None (`--if-read`).

    The old side must be the author's own last-read bookmark, not its
    last-tag fallback, and at least one chapter must have existed at
    that version and changed since; a chapter new since then is read
    whole, not as a diff."""
    if not report.old.from_bookmark:
        why = (report.old.note or "no last-read bookmark").split(";")[0]
        return f"{why} (books/{book}/edit_logs/{BOOKMARK_NAME})"
    if any(f.status in ("changed", "removed") for f in report.chapters):
        return None
    new = [f.chapter for f in report.chapters if f.status == "added" and f.chapter is not None]
    if new:
        return (f"chapter{'s' if len(new) > 1 else ''} {_ranges(new)} did not exist "
                f"in the version last read")
    return "no changes since the version last read"


def load_why(path: Path) -> dict[str, dict]:
    """Load an annotation sidecar.

    Keys are hunk ids (``ch05-002``) or chapter keys (``ch05``, a
    one-line summary of that chapter's changes). A value is a string
    (the *why*, the original form) or an object with any of ``what``
    (a plain note on what the change is), ``why``, ``big`` (true when the
    author would want to read it) and ``fp`` (the hunk fingerprint it was
    written against)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DiffError(f"{path}: expected a JSON object mapping hunk id -> annotation")
    out: dict[str, dict] = {}
    for k, v in data.items():
        if isinstance(v, str):
            v = {"why": v}
        if not isinstance(v, dict):
            continue
        entry: dict = {f: v[f].strip() for f in ("what", "why")
                       if isinstance(v.get(f), str) and v[f].strip()}
        if isinstance(v.get("big"), bool):
            entry["big"] = v["big"]
        if entry:
            out[str(k)] = {**entry, "fp": v.get("fp")}
    return out


def apply_why(report: DiffReport, why: dict[str, dict]) -> None:
    applied = 0
    stale: list[str] = []
    for h in report.all_hunks:
        w = why.get(h.id)
        if not w:
            continue
        if w.get("fp") and w["fp"] != h.fp:
            stale.append(h.id)
            continue
        h.what, h.why, h.big = w.get("what"), w.get("why"), w.get("big")
        applied += 1
    for f in report.chapters + report.foundation:
        w = why.get(f.key)
        line = (w.get("why") or w.get("what")) if w else None
        if line and f.kind != "summary":
            f.why = line
            applied += 1
    report.why_applied = applied
    report.why_stale = stale


# ===================================================================
# HTML
# ===================================================================


_LIGHT = """
  --bg: #fbfaf7; --fg: #1f1d1a; --muted: #6b665e; --rule: #e2ddd3;
  --panel: #f2efe8; --link: #2f5d8a; --accent: #2f5d8a; --on-accent: #ffffff;
  --current: #b07d00; --flash: #f6e3a1;
  --ins-bg: #d9f2dd; --ins-fg: #0d5520; --ins-bar: #4e9a5f; --new-bg: #eff7ef;
  --del-bg: #fadede; --del-fg: #8f1d1d; --del-bar: #cf8f84;
  --note-bg: #eeebe3; --note-fg: #26241f; --why-fg: #615c53; --badge: #e6e1d6;
"""
_DARK = """
  --bg: #15171a; --fg: #e5e2dc; --muted: #9b968d; --rule: #2d3136;
  --panel: #1d2024; --link: #8fb9e6; --accent: #6f9fd3; --on-accent: #10141a;
  --current: #e0b33a; --flash: #4a3d12;
  --ins-bg: #173b23; --ins-fg: #a9e6b8; --ins-bar: #5fae74; --new-bg: #16241a;
  --del-bg: #4a1e20; --del-fg: #f4b3b0; --del-bar: #a8655c;
  --note-bg: #20242a; --note-fg: #e5e2dc; --why-fg: #a59f95; --badge: #2a2e33;
"""

# Colours are custom properties: the OS dark mode switches them unless
# the host page pins `data-theme="light"`, and `data-theme="dark"` (a
# claude.ai artifact frame, say) switches them on any OS.
_CSS = (
    ":root { color-scheme: light; --bar-h: 3rem;" + _LIGHT + "}\n"
    "@media (prefers-color-scheme: dark) {\n"
    "  :root:not([data-theme=\"light\"]) { color-scheme: dark;" + _DARK + "}\n}\n"
    ":root[data-theme=\"dark\"] { color-scheme: dark;" + _DARK + "}\n"
) + r"""
* { box-sizing: border-box; }
/* The page keeps the reader's place across view switches itself (see the
   script); the browser's own scroll anchoring would fight it. */
html { scroll-padding-top: calc(var(--bar-h) + env(safe-area-inset-top, 0px) + .75rem);
  -webkit-text-size-adjust: 100%; overflow-anchor: none; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
/* Paint the notch strip above the sticky toolbar on a phone. */
body::before { content: ""; position: fixed; inset: 0 0 auto; z-index: 21;
  height: env(safe-area-inset-top, 0px); background: var(--panel); }
a { color: var(--link); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.toolbar { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 20; display: flex;
  flex-wrap: wrap; align-items: center; gap: .4rem .6rem;
  padding: .45rem max(16px, env(safe-area-inset-right, 0px)) .45rem max(16px, env(safe-area-inset-left, 0px));
  background: var(--panel); border-bottom: 1px solid var(--rule); }
.toolbar .title { font-weight: 600; margin-right: auto; min-width: 0; flex: 1 1 8rem;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toolbar button { font: inherit; padding: .3rem .7rem; border-radius: 6px;
  border: 1px solid var(--rule); background: var(--bg); color: var(--fg); cursor: pointer; }
.toolbar button:hover { border-color: var(--accent); }
.toolbar .maplink { white-space: nowrap; font-weight: 600; }
.nav { display: inline-flex; align-items: center; gap: .35rem; }
.counter { font-variant-numeric: tabular-nums; white-space: nowrap; min-width: 7.2em; text-align: center; }
.views { display: inline-flex; border: 1px solid var(--rule); border-radius: 999px; overflow: hidden; }
.toolbar .views button { border: 0; border-radius: 0; padding: .3rem .75rem; background: var(--bg); }
.toolbar .views button + button { border-left: 1px solid var(--rule); }
.toolbar .views button[aria-pressed="true"] { background: var(--accent); color: var(--on-accent); }
.bigfilter { display: inline-flex; align-items: center; gap: .3rem; white-space: nowrap; color: var(--muted); }
body:not(.view-changes) .bigfilter { display: none; }
#navtoggle { display: none; }
.layout { display: grid; grid-template-columns: 18rem minmax(0, 1fr); }
aside { position: sticky; top: calc(var(--bar-h) + env(safe-area-inset-top, 0px)); align-self: start;
  height: calc(100vh - var(--bar-h)); overflow: auto; border-right: 1px solid var(--rule);
  padding: .75rem 12px 2rem; font-size: .82rem; background: var(--bg); }
aside h3 { font-size: .8rem; margin: .9rem 0 .3rem; }
aside h3 a { color: var(--fg); text-decoration: none; }
aside ol { list-style: none; margin: 0; padding: 0; }
aside li a { display: block; padding: .15rem .35rem; border-radius: 4px; color: var(--fg);
  text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
aside li.noted a { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; }
aside li a:hover { background: var(--panel); }
aside li a.active { background: var(--note-bg); outline: 1px solid var(--accent); }
aside .n { display: inline-block; min-width: 2.2em; color: var(--muted); font-variant-numeric: tabular-nums; }
.plus { color: var(--ins-fg); } .minus { color: var(--del-fg); }
main { min-width: 0;
  padding: 1rem max(16px, env(safe-area-inset-right, 0px)) 5rem max(16px, env(safe-area-inset-left, 0px)); }
.wrap { max-width: 44rem; margin: 0 auto; }
header.report h1 { font-size: 1.35rem; margin: .2rem 0 .4rem; }
.meta { color: var(--muted); margin: .15rem 0; overflow-wrap: anywhere; }
.note { color: var(--muted); font-style: italic; }
.legend { margin: .6rem 0 1rem; color: var(--muted); }
.tablewrap { overflow-x: auto; margin: .8rem 0 1.2rem; }
table { border-collapse: collapse; width: 100%; font-size: .9rem; font-variant-numeric: tabular-nums; }
th, td { padding: .3rem .5rem; border-bottom: 1px solid var(--rule); text-align: right; white-space: nowrap; }
th:nth-child(1), td:nth-child(1), th:nth-child(2), td:nth-child(2) { text-align: left; }
td:nth-child(2) { white-space: normal; min-width: 8rem; }
tr.total td { font-weight: 600; border-top: 2px solid var(--rule); }
.badge { display: inline-block; font: 600 .7rem/1.6 system-ui, sans-serif; padding: 0 .45rem;
  border-radius: 999px; background: var(--badge); color: var(--muted); vertical-align: middle;
  text-transform: uppercase; letter-spacing: .03em; }
.badge.added { background: var(--ins-bg); color: var(--ins-fg); }
.badge.removed { background: var(--del-bg); color: var(--del-fg); }
section.file { margin: 2.2rem 0 0; }
section.file > h2 { font-size: 1.15rem; margin: 0 0 .25rem; padding-top: .3rem; border-top: 1px solid var(--rule); }
section.group > h2 { font-size: 1.2rem; margin: 3rem 0 0; }
section.file.doc > h2 { font-size: 1rem; }
.file-why, .what { background: var(--note-bg); color: var(--note-fg); border-radius: 6px;
  padding: .4rem .65rem; margin: .35rem 0 .5rem; font-size: .95rem; line-height: 1.45; }
.why { color: var(--why-fg); font-size: .85rem; line-height: 1.4; margin: 0 0 .6rem; padding: 0 .65rem; }
.why b, .file-why b { font-weight: 600; }
.bigs { background: var(--note-bg); border-radius: 6px; padding: .6rem .8rem; margin: .5rem 0 1.1rem;
  font-size: .92rem; line-height: 1.45; }
.bigs p { margin: 0 0 .3rem; font-weight: 600; }
.bigs ol { margin: 0; padding-left: 1.5rem; }
.bigs li { margin: .2rem 0; }
.bigs a { color: var(--fg); text-decoration-color: var(--accent); }
.fm { color: var(--muted); font-size: .85rem; margin: .2rem 0 .6rem; padding-left: 1.1rem; }
.prose p { font-family: Georgia, "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, serif;
  font-size: 1.06rem; line-height: 1.62; margin: 0 0 .75em; overflow-wrap: break-word; }
.doc .prose p { font-family: inherit; font-size: .95rem; line-height: 1.5; }
.prose p.p-eq { opacity: .82; }
.prose p.md-h { font-weight: 700; }
.prose p.md-break { text-align: center; letter-spacing: .4em; }
ins { background: var(--ins-bg); color: var(--ins-fg); text-decoration: none;
  border-bottom: 1px solid currentColor; border-radius: 2px; padding: 0 1px; }
del { background: var(--del-bg); color: var(--del-fg); text-decoration: line-through;
  border-radius: 2px; padding: 0 1px; }
.pilcrow { font-family: system-ui, sans-serif; font-weight: 700; }
/* A wholly new paragraph (or a rewritten one) reads as text under a green
   rule, not as a wall of highlight; a cut one under a red rule. */
.prose p.p-ins, .prose p.p-rewritten { background: var(--new-bg); box-shadow: inset 3px 0 0 var(--ins-bar);
  padding: .1rem .5rem .1rem .75rem; border-radius: 0 4px 4px 0; }
.prose p.p-ins ins, .prose p.p-rewritten ins { background: none; border-bottom: 0; color: inherit; padding: 0; }
.prose p.p-del { box-shadow: inset 3px 0 0 var(--del-bar); padding-left: .75rem; }
details.earlier { margin: -.35rem 0 .9rem; color: var(--muted); }
details.earlier summary { font: .8rem/1.6 system-ui, sans-serif; cursor: pointer; padding: .15rem 0; }
details.earlier p.p-old { opacity: 1; font-size: .97rem; box-shadow: inset 3px 0 0 var(--del-bar);
  padding-left: .75rem; margin-top: .4rem; }
/* A wholly added / removed file reads as plain text under a coloured rule. */
.st-added .hunk { border-left-color: var(--ins-fg); }
.st-removed .hunk { border-left-color: var(--del-fg); }
.st-added .prose p.p-ins { background: none; box-shadow: none; padding-left: 0; }
.st-removed .hunk del { background: none; color: var(--del-fg); text-decoration: none; padding: 0; }
.prose p.p-moved { background: none; box-shadow: none; outline: 1px dashed var(--muted); outline-offset: 2px; }
.tag { font: 600 .68rem/1 system-ui, sans-serif; text-transform: uppercase; color: var(--muted); letter-spacing: .04em; }
/* No scroll-margin here: html's scroll-padding-top already clears the
   sticky toolbar for scrollIntoView and anchor jumps (both would add up). */
.hunk { position: relative; border-left: 3px solid var(--accent); padding: .3rem 0 .1rem .8rem;
  margin: .9rem 0 1rem -.95rem; }
.hunk.current { border-left-color: var(--current); background:
  linear-gradient(to right, color-mix(in srgb, var(--current) 10%, transparent), transparent 60%); }
@keyframes hunk-flash { from { background-color: var(--flash); } to { background-color: transparent; } }
.hunk.flash { animation: hunk-flash 1.4s ease-out; }
@media (prefers-reduced-motion: reduce) {
  .hunk.flash { animation: none; outline: 2px solid var(--current); outline-offset: 2px; }
}
.hunk-head { font-size: .8rem; color: var(--muted); margin-bottom: .35rem; font-variant-numeric: tabular-nums; }
.hunk-head a { color: var(--muted); text-decoration: none; font-weight: 600; }
.hunk-head a:hover { color: var(--link); }
.hunk-head .big-tag { font-weight: 600; color: var(--current); }
.fold { margin: .2rem 0 .7rem; }
.fold-toggle { font: .82rem/1.4 system-ui, sans-serif; color: var(--muted); width: 100%; text-align: left;
  background: none; border: 1px dashed var(--rule); border-radius: 6px; padding: .3rem .6rem;
  cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fold-toggle:hover { border-color: var(--accent); color: var(--fg); }
.fold-body { display: none; padding-top: .6rem; }
.fold.open .fold-body { display: block; }
.fold.open .fold-toggle .peek { display: none; }
/* Views. Changes (default): unchanged runs folded. Whole chapter: every
   paragraph, changes marked. Clean text: the new version only. */
body.view-whole .fold-body, body.view-clean .fold-body { display: block; }
body.view-whole .fold-toggle, body.view-clean .fold-toggle { display: none; }
body.view-changes.filter-big .is-minor { display: none; }
body.view-clean del, body.view-clean .p-del, body.view-clean .pilcrow, body.view-clean .tag,
body.view-clean .hunk-head, body.view-clean .what, body.view-clean .why, body.view-clean .file-why,
body.view-clean .bigs, body.view-clean details.earlier, body.view-clean .fm, body.view-clean .legend,
body.view-clean .stats, body.view-clean aside, body.view-clean .nav, body.view-clean #navtoggle,
body.view-clean section.st-removed, body.view-clean section.doc, body.view-clean section.group {
  display: none !important; }
body.view-clean .layout { display: block; }
body.view-clean ins { background: none; border: 0; color: inherit; padding: 0; }
body.view-clean .prose p { background: none; box-shadow: none; outline: 0; padding-left: 0; opacity: 1; }
body.view-clean .hunk { border: 0; margin: 0; padding: 0; background: none; animation: none; }
.empty { padding: 2rem 0; color: var(--muted); }
footer { color: var(--muted); font-size: .8rem; margin-top: 3rem; }
kbd { font: .75rem ui-monospace, Menlo, Consolas, monospace; border: 1px solid var(--rule);
  border-bottom-width: 2px; border-radius: 4px; padding: 0 .3rem; background: var(--panel); }
@media (max-width: 900px) {
  #navtoggle { display: inline-block; }
  .layout { display: block; }
  aside { display: none; position: fixed; z-index: 30; top: calc(var(--bar-h) + env(safe-area-inset-top, 0px));
    left: 0; width: min(88vw, 22rem); height: calc(100vh - var(--bar-h));
    box-shadow: 0 0 0 100vmax rgba(0,0,0,.35); }
  body.nav-open aside { display: block; }
  .hunk { margin-left: -.6rem; padding-left: .55rem; }
}
th .s { display: none; }
@media (max-width: 600px) {
  .toolbar .title, .toolbar .long { display: none; }
  .toolbar button, .toolbar .views button { padding: .3rem .55rem; }
  th:nth-child(3), td:nth-child(3), th:nth-child(7), td:nth-child(7) { display: none; }
  th, td { padding: .3rem .3rem; }
  td:nth-child(2) { min-width: 0; }
  th .l { display: none; } th .s { display: inline; }
}
@supports (height: 100dvh) {
  aside { height: calc(100dvh - var(--bar-h)); }
}
@media print {
  .toolbar, aside, .fold-toggle, details.earlier { display: none !important; }
  .layout { display: block; } .fold-body { display: block !important; }
}
"""

# Restores the remembered view before the first paint.
_VIEW_KEY = "autonovel-diff-view"
_HEAD_JS = (
    "try{var v=localStorage.getItem('" + _VIEW_KEY + "');"
    "if(v==='whole'||v==='clean'){document.body.className='view-'+v;}}catch(e){}"
)

_JS = r"""
(function () {
  var KEY = '""" + _VIEW_KEY + r"""', VIEWS = ['changes', 'whole', 'clean'];
  var body = document.body, root = document.documentElement;
  var hunks = Array.prototype.slice.call(document.querySelectorAll('.hunk'));
  hunks.forEach(function (h, k) { h._k = k; });
  var curEl = document.getElementById('cur'), totalEl = document.getElementById('total');
  var bar = document.querySelector('.toolbar'), aside = document.querySelector('aside');
  var bigBox = document.getElementById('bigonly');
  var viewBtns = Array.prototype.slice.call(document.querySelectorAll('[data-view]'));
  var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var links = {};
  if (aside) Array.prototype.forEach.call(aside.querySelectorAll('a[href^="#"]'), function (a) {
    links[a.getAttribute('href').slice(1)] = a;
  });
  // Stepping is by index, not by scroll position: the page may sit in a
  // frame, and the first changes can be a few lines apart. `cur` indexes
  // `hunks`; a half step (2.5) means "between changes 3 and 4", after the
  // reader scrolled there by hand. An IntersectionObserver resyncs it.
  var cur = -1, quietUntil = 0, seen = {}, marked = null;

  function view() {
    for (var i = 0; i < VIEWS.length; i++) if (body.classList.contains('view-' + VIEWS[i])) return VIEWS[i];
    return 'changes';
  }
  function measure() {
    if (bar) root.style.setProperty('--bar-h', Math.ceil(bar.getBoundingClientRect().height) + 'px');
  }
  function visible() {
    if (view() === 'clean') return [];
    return hunks.filter(function (h) { return h.getClientRects().length > 0; });
  }
  function keepInView(a) {
    if (!aside || aside.scrollHeight <= aside.clientHeight) return;
    var top = a.offsetTop, st = aside.scrollTop;
    if (top < st + 24 || top > st + aside.clientHeight - 48) aside.scrollTop = Math.max(0, top - aside.clientHeight / 3);
  }
  function mark() {
    var h = cur % 1 === 0 ? hunks[cur] || null : null;
    if (marked && marked !== h) {
      marked.classList.remove('current');
      if (links[marked.id]) links[marked.id].classList.remove('active');
    }
    marked = h;
    if (!h) return;
    h.classList.add('current');
    if (links[h.id]) { links[h.id].classList.add('active'); keepInView(links[h.id]); }
  }
  function label() {
    var vs = visible(), i = cur % 1 === 0 ? vs.indexOf(hunks[cur]) : -1;
    curEl.textContent = i < 0 ? '–' : String(i + 1);
    totalEl.textContent = String(vs.length);
  }
  function resync() {
    // The current change was hidden by a view or the filter: stand just
    // before it, so "next" lands on the next one still shown.
    if (cur >= 0 && cur % 1 === 0 && hunks[cur] && !hunks[cur].getClientRects().length) cur -= 0.5;
    mark(); label();
  }
  function flash(h) {
    h.classList.remove('flash'); void h.offsetWidth; h.classList.add('flash');
    clearTimeout(h._flashT);
    h._flashT = setTimeout(function () { h.classList.remove('flash'); }, 1600);
  }
  function land(h, smooth) {
    cur = h._k; quietUntil = Date.now() + 1200;
    mark(); label();
    h.scrollIntoView({block: 'start', behavior: smooth && !reduce ? 'smooth' : 'auto'});
    flash(h);
    try { if (history.replaceState) history.replaceState(null, '', '#' + h.id); } catch (e) {}
  }
  function go(dir) {
    var vs = visible(), t = null, i;
    if (!vs.length) return;
    if (dir > 0) {
      for (i = 0; i < vs.length; i++) if (vs[i]._k > cur) { t = vs[i]; break; }
      t = t || vs[vs.length - 1];
    } else {
      for (i = vs.length - 1; i >= 0; i--) if (vs[i]._k < cur) { t = vs[i]; break; }
      t = t || vs[0];
    }
    land(t, true);
  }
  // A view or filter switch reflows the page; keep what the reader was
  // looking at (the element just under the toolbar) where it was.
  function anchor() {
    var wrap = document.querySelector('main .wrap');
    if (!wrap || !document.elementFromPoint) return null;
    var x = wrap.getBoundingClientRect().left + 40, y = (bar ? bar.getBoundingClientRect().bottom : 0) + 4;
    // Step down past the gaps between paragraphs to the first block.
    for (var dy = 0; dy < 240; dy += 12) {
      var el = document.elementFromPoint(x, y + dy);
      el = el && el.closest ? el.closest('p, h2, .hunk-head, .what, .why, .fold, details, .bigs, header') : null;
      if (el) return {el: el, top: el.getBoundingClientRect().top};
    }
    return null;
  }
  function restore(a) {
    if (!a) return;
    var el = a.el;
    while (el && !el.getClientRects().length) el = el.parentElement && el.parentElement.closest('.fold, .hunk, section');
    if (el) { quietUntil = Date.now() + 600; window.scrollBy(0, el.getBoundingClientRect().top - a.top); }
  }
  function setView(v, remember) {
    if (VIEWS.indexOf(v) < 0) v = 'changes';
    var a = remember ? anchor() : null;
    VIEWS.forEach(function (x) { body.classList.toggle('view-' + x, x === v); });
    viewBtns.forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-view') === v ? 'true' : 'false'); });
    if (remember) { try { localStorage.setItem(KEY, v); } catch (e) {} }
    measure(); restore(a); resync();
  }
  function setFilter(on) {
    var a = anchor();
    body.classList.toggle('filter-big', on);
    if (bigBox) bigBox.checked = on;
    restore(a); resync();
  }
  function firstFrom(el) {
    for (var i = 0; i < hunks.length; i++) {
      if (el.contains(hunks[i]) || (el.compareDocumentPosition(hunks[i]) & 4)) return i;
    }
    return -1;
  }
  document.getElementById('next').addEventListener('click', function () { go(1); });
  document.getElementById('prev').addEventListener('click', function () { go(-1); });
  if (bigBox) bigBox.addEventListener('change', function () { setFilter(bigBox.checked); });
  var nt = document.getElementById('navtoggle');
  if (nt) nt.addEventListener('click', function () { body.classList.toggle('nav-open'); });
  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (t && (t.isContentEditable || /^(TEXTAREA|SELECT)$/.test(t.tagName)
        || (t.tagName === 'INPUT' && !/^(checkbox|radio|button)$/i.test(t.type)))) return;
    if (e.key === 'j' || e.key === 'n') { go(1); e.preventDefault(); }
    else if (e.key === 'k' || e.key === 'p') { go(-1); e.preventDefault(); }
    else if (e.key === 'e') { setView(view() === 'whole' ? 'changes' : 'whole', true); }
    else if (e.key === 'Escape') { body.classList.remove('nav-open'); }
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest) return;
    var b = e.target.closest('.fold-toggle');
    if (b) {
      var f = b.parentNode, open = !f.classList.contains('open');
      f.classList.toggle('open', open);
      b.setAttribute('aria-expanded', open ? 'true' : 'false');
      return;
    }
    var vb = e.target.closest('[data-view]');
    if (vb) { setView(vb.getAttribute('data-view'), true); return; }
    var a = e.target.closest('a[href^="#"]');
    if (!a) return;
    var el = document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
    body.classList.remove('nav-open');
    if (!el) return;
    if (el.classList.contains('hunk')) {
      e.preventDefault();
      if (!el.getClientRects().length) { if (view() === 'clean') setView('changes', false); setFilter(false); }
      land(el, true);
      return;
    }
    // A chapter or section heading: the browser jumps there; the next
    // change is the first one in it.
    var k = firstFrom(el);
    if (k >= 0) { cur = k - 0.5; quietUntil = Date.now() + 1200; mark(); label(); }
  });
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) seen[en.target._k] = 1; else delete seen[en.target._k]; });
      if (Date.now() < quietUntil) return;
      if (cur >= 0 && cur % 1 === 0 && seen[cur]) return;   // the current change is still on screen
      var vs = visible(), first = null;
      for (var i = 0; i < vs.length; i++) if (seen[vs[i]._k]) { first = vs[i]; break; }
      if (!first) return;
      // A change that has not yet reached the top third is the next one.
      cur = first.getBoundingClientRect().top > window.innerHeight / 3 ? first._k - 0.5 : first._k;
      mark(); label();
    });
    hunks.forEach(function (h) { io.observe(h); });
  }
  if (window.ResizeObserver && bar) new ResizeObserver(measure).observe(bar);
  window.addEventListener('resize', measure);
  window.addEventListener('load', measure);
  setView(view(), false);
  if (location.hash) {
    var el0 = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (el0 && el0.classList.contains('hunk')) {
      // Clean text stays clean (the remembered view wins): just go there.
      requestAnimationFrame(function () {
        if (view() === 'clean') { cur = el0._k - 0.5; el0.scrollIntoView({block: 'start'}); }
        else land(el0, false);
      });
    } else if (el0) {
      var k0 = firstFrom(el0); if (k0 >= 0) { cur = k0 - 0.5; quietUntil = Date.now() + 1200; label(); }
    }
  }
})();
"""


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _fmt_signed(n: int) -> str:
    if n > 0:
        return f"+{n:,}"
    if n < 0:
        return f"−{abs(n):,}"
    return "0"


def _ranges(nums: list[int]) -> str:
    out: list[str] = []
    start = prev = None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:  # type: ignore[operator]
            prev = n
        else:
            out.append(f"{start}" if start == prev else f"{start}–{prev}")
            start = prev = n
    if start is not None:
        out.append(f"{start}" if start == prev else f"{start}–{prev}")
    return ", ".join(out)


def _snap_line(s: Snapshot) -> str:
    bits = [f"<b>{_esc(s.description)}</b>"]
    if s.kind == "git" and s.meta:
        if s.meta.get("date"):
            bits.append(_esc(s.meta["date"][:10]))
        if s.meta.get("subject"):
            subj = s.meta["subject"]
            bits.append("“" + _esc(subj[:90] + ("…" if len(subj) > 90 else "")) + "”")
    elif s.kind == "worktree" and s.meta.get("head_short"):
        bits.append(f"HEAD {_esc(s.meta['head_short'])}"
                    + (" + uncommitted edits" if s.meta.get("dirty") else ""))
    elif s.kind == "checkpoint" and s.meta.get("args"):
        bits.append(_esc(" ".join(map(str, s.meta["args"]))[:90]))
    if s.note:
        bits.append(f'<span class="note">{_esc(s.note)}</span>')
    return " · ".join(bits)


def md_inline_text(text: str) -> str:
    """One line of markdown as plain text, emphasis markers dropped."""
    return " ".join(_plain(p) for p in _emphasis(tokenize(" ".join(text.split()))))


def _hunk_html(h: Hunk, total: int) -> str:
    stats = (f'<span class="plus">+{h.words_added}</span> '
             f'<span class="minus">−{h.words_removed}</span> words')
    bits = [f'<a href="#{_esc(h.id)}">Change {h.n} of {total}</a>', f"¶{h.index + 1}", stats]
    if h.moved:
        bits.append(f"{h.moved} moved")
    if h.rewritten:
        bits.append("rewritten" if h.rewritten == 1 else f"{h.rewritten} rewritten")
    if h.is_big:
        bits.append('<span class="big-tag">big</span>')
    what = f'<div class="what">{md_inline_html(h.what)}</div>' if h.what else ""
    why = f'<div class="why"><b>Why:</b> {md_inline_html(h.why)}</div>' if h.why else ""
    return (f'<div class="hunk {"is-big" if h.is_big else "is-minor"}" id="{_esc(h.id)}" '
            f'data-n="{h.n}"><div class="hunk-head">{" · ".join(bits)}</div>'
            f'{what}{why}{h.inline_html}</div>')


def _minor(h: Hunk | None) -> bool:
    return h is None or not h.is_big


def _render_flow(f: FileDiff, *, context: int, total: int) -> str:
    out: list[str] = []
    flow = f.flow
    for idx, (kind, val) in enumerate(flow):
        if kind == "hunk":
            out.append(_hunk_html(val, total))
            continue
        paras: list[str] = val
        prev = flow[idx - 1][1] if idx > 0 else None
        nxt = flow[idx + 1][1] if idx < len(flow) - 1 else None
        # Context paragraphs belong to the change beside them and hide
        # with it under the big-changes filter.
        after_prev = "ctx is-minor" if _minor(prev) else "ctx"
        before_next = "ctx is-minor" if _minor(nxt) else "ctx"
        shared = "ctx is-minor" if _minor(prev) and _minor(nxt) else "ctx"
        head = paras[:context] if prev is not None else []
        tail = paras[len(paras) - context:] if nxt is not None and context else []
        if len(head) + len(tail) >= len(paras):
            for p in paras:
                out.append(render_plain_paragraph(p, extra_class=shared))
            continue
        middle = paras[len(head):len(paras) - len(tail)]
        for p in head:
            out.append(render_plain_paragraph(p, extra_class=after_prev))
        if len(middle) == 1:
            out.append(render_plain_paragraph(middle[0], extra_class=shared))
        elif middle:
            words = _word_count_paras(middle)
            peek = _lead(middle[0], 70)[1]
            body = "\n".join(render_plain_paragraph(p) for p in middle)
            out.append(
                f'<div class="fold"><button type="button" class="fold-toggle" '
                f'aria-expanded="false">⋯ {len(middle)} unchanged paragraphs · '
                f'{_fmt_int(words)} words <span class="peek">— {peek}</span></button>'
                f'<div class="fold-body">{body}</div></div>'
            )
        for p in tail:
            out.append(render_plain_paragraph(p, extra_class=before_next))
    return "\n".join(out)


def _big_list(f: FileDiff) -> str:
    """The chapter's big changes, as links, for its heading: the notes
    when annotated, else the changes the size rule calls big."""
    if f.kind != "chapter" or f.status in ("added", "removed"):
        return ""
    bigs = [h for h in f.hunks if h.is_big]
    if not bigs:
        return ""
    if any(h.big is not None for h in f.hunks):
        head = f"The big changes ({len(bigs)} of {len(f.hunks)})"
    else:
        head = (f"The biggest changes ({len(bigs)} of {len(f.hunks)}: "
                f"{BIG_WORDS}+ words, or a paragraph moved)")
    items = "".join(
        f'<li><a href="#{_esc(h.id)}">{md_inline_html(h.what) if h.what else h.snippet_html}</a></li>'
        for h in bigs)
    return (f'<nav class="bigs" aria-label="Big changes in {_esc(f.label)}">'
            f'<p>{_esc(head)}</p><ol>{items}</ol></nav>')


def _file_section(f: FileDiff, *, context: int, total: int,
                  story_map_href: str | None = None) -> str:
    title = f.label + (f" — {f.title}" if f.title and f.kind == "chapter" else "")
    badge = (f' <span class="badge {f.status}">{f.status}</span>'
             if f.status in ("added", "removed") else "")
    stats = (f'<span class="plus">+{_fmt_int(f.words_added)}</span> '
             f'<span class="minus">−{_fmt_int(f.words_removed)}</span> words · '
             f'net {_fmt_signed(f.net)} · now {_fmt_int(f.words_new)} words · '
             f'{len(f.hunks)} change{"s" if len(f.hunks) != 1 else ""}')
    parts = [
        f'<section class="file st-{f.status}{" doc" if f.kind != "chapter" else ""}" '
        f'id="file-{_esc(f.key)}">',
        f'<h2>{_esc(title)}{badge}</h2>',
        f'<p class="meta stats">{_esc(f.file)} · {stats}'
        + (f' · <a href="{_esc(story_map_href)}#ch-{f.chapter}">this chapter in the '
           f'story map</a>' if story_map_href and f.kind == "chapter" and f.chapter else "")
        + '</p>',
    ]
    if f.why:
        parts.append(f'<div class="file-why"><b>What changed:</b> {md_inline_html(f.why)}</div>')
    parts.append(_big_list(f))
    if f.frontmatter_changes:
        items = "".join(
            f"<li>{_esc(k)}: <del>{_esc(str(o))}</del> → <ins>{_esc(str(n))}</ins></li>"
            for k, (o, n) in f.frontmatter_changes.items()
        )
        parts.append(f'<ul class="fm">{items}</ul>')
    parts.append(f'<div class="prose">{_render_flow(f, context=context, total=total)}</div>')
    parts.append("</section>")
    return "\n".join(p for p in parts if p)


def _sidebar(report: DiffReport) -> str:
    out: list[str] = []
    for f in report.chapters + report.foundation:
        if not f.hunks:
            continue
        label = f.label + (f" · {f.title}" if f.title and f.kind == "chapter" else "")
        out.append(f'<h3><a href="#file-{_esc(f.key)}">{_esc(label)}</a> '
                   f'<span class="n">({len(f.hunks)})</span></h3><ol>')
        for h in f.hunks:
            cls = ("is-big" if h.is_big else "is-minor") + (" noted" if h.what else "")
            text = md_inline_html(h.what) if h.what else h.snippet_html
            tip = md_inline_text(h.what) if h.what else h.snippet
            out.append(
                f'<li class="{cls}"><a href="#{_esc(h.id)}" title="{_esc(tip)}">'
                f'<span class="n">{h.n}</span>'
                f'<span class="plus">+{h.words_added}</span> '
                f'<span class="minus">−{h.words_removed}</span> '
                f'{text}</a></li>'
            )
        out.append("</ol>")
    return "\n".join(out) or '<p class="note">No changes.</p>'


def render_html(report: DiffReport, *, context: int = 1,
                story_map_href: str | None = None) -> str:
    """One self-contained page: inline CSS + JS, no external requests.
    Three views of the same text (Changes / Whole chapter / Clean text)
    and a big-changes filter. `story_map_href` (the story map written
    beside it) adds a Story map link to the toolbar and to every
    chapter's heading line."""
    t = report.totals()
    total = t["hunks"]
    title = f"{report.book}: {report.old.label} → {report.new.label}"
    rows: list[str] = []
    for f in report.changed_chapters:
        rows.append(
            f'<tr><td><a href="#file-{_esc(f.key)}">{f.chapter}</a></td>'
            f'<td>{_esc(f.title or "")}'
            + (f' <span class="badge {f.status}">{f.status}</span>'
               if f.status in ("added", "removed") else "")
            + f'</td><td>{len(f.hunks)}</td>'
            f'<td class="plus">+{_fmt_int(f.words_added)}</td>'
            f'<td class="minus">−{_fmt_int(f.words_removed)}</td>'
            f'<td>{_fmt_signed(f.net)}</td><td>{_fmt_int(f.words_new)}</td></tr>'
        )
    unchanged = [f.chapter for f in report.chapters
                 if f.status == "unchanged" and f.chapter is not None]
    table = ""
    if rows:
        table = (
            '<div class="tablewrap"><table><thead><tr><th>Ch</th><th>Title</th>'
            '<th>Changes</th><th><span class="l">Added</span><span class="s">+</span></th>'
            '<th><span class="l">Removed</span><span class="s">−</span></th>'
            '<th>Net</th><th>Words now</th>'
            '</tr></thead><tbody>' + "".join(rows)
            + f'<tr class="total"><td>All</td><td>{t["chapters_changed"]} of '
            f'{t["chapters_compared"]} chapters changed</td><td>{t["chapter_hunks"]}</td>'
            f'<td class="plus">+{_fmt_int(t["words_added"])}</td>'
            f'<td class="minus">−{_fmt_int(t["words_removed"])}</td>'
            f'<td>{_fmt_signed(t["net_words"])}</td><td>{_fmt_int(t["words_new"])}</td></tr>'
            '</tbody></table></div>'
        )
    notes: list[str] = []
    if unchanged:
        notes.append(f"Unchanged chapters: {_ranges(unchanged)}.")
    if report.chapter_filter is not None:
        notes.append(f"Limited to chapters {_ranges(report.chapter_filter)}.")
    if t["foundation_hunks"]:
        notes.append(f'<a href="#foundation">{t["foundation_hunks"]} change'
                     f'{"s" if t["foundation_hunks"] != 1 else ""} in summaries and '
                     f'foundation files</a> follow the chapters.')
    if report.why_stale:
        notes.append(f"{len(report.why_stale)} annotation(s) skipped: the text "
                     f"changed since they were written.")

    body: list[str] = []
    chapter_secs = [_file_section(f, context=context, total=total,
                                  story_map_href=story_map_href)
                    for f in report.chapters if f.hunks or f.status != "unchanged"]
    body += chapter_secs
    if report.foundation:
        body.append('<section class="group" id="foundation"><h2>Summaries and foundation</h2>'
                    '<p class="meta">Chapter summaries, voice.md, outline.md and canon.</p></section>')
        body += [_file_section(f, context=context, total=total) for f in report.foundation]
    if not total and not report.changed_chapters:
        body.append(f'<p class="empty">No differences between {_esc(report.old.description)} '
                    f'and {_esc(report.new.description)}.</p>')
    maplink = (f'<a class="maplink" href="{_esc(story_map_href)}" title="Synopsis, threads, '
               f'characters, timeline and places">Story map</a>' if story_map_href else "")
    big_note = f" · {t['big_hunks']} big" if total else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="generator" content="autonovel mechanical diff-chapters">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body class="view-changes">
<script>{_HEAD_JS}</script>
<div class="toolbar" role="toolbar" aria-label="Changes and views">
  <button type="button" id="navtoggle" aria-label="List of changes">☰ List</button>
  <span class="title">{_esc(title)}</span>
  <span class="nav">
    <button type="button" id="prev" title="Previous change (k or p)" aria-label="Previous change">◀<span class="long"> Prev</span></button>
    <span class="counter" aria-live="polite">change <b id="cur">–</b> of <b id="total">{total}</b></span>
    <button type="button" id="next" title="Next change (j or n)" aria-label="Next change"><span class="long">Next </span>▶</button>
  </span>
  {maplink}
  <span class="views" role="group" aria-label="View">
    <button type="button" data-view="changes" aria-pressed="true" title="The changes, unchanged paragraphs folded">Changes</button>
    <button type="button" data-view="whole" aria-pressed="false" title="Every paragraph, the changes marked (e)">Whole<span class="long"> chapter</span></button>
    <button type="button" data-view="clean" aria-pressed="false" title="The new version as a straight read">Clean<span class="long"> text</span></button>
  </span>
  <label class="bigfilter" title="Hide wording trims; keep new scenes, new lines and changed facts"><input type="checkbox" id="bigonly"> Big<span class="long"> changes</span> only</label>
</div>
<div class="layout">
<aside aria-label="Changes by chapter">{_sidebar(report)}</aside>
<main><div class="wrap">
<header class="report">
<h1>{_esc(report.book)}: what changed</h1>
<p class="meta">From {_snap_line(report.old)}</p>
<p class="meta">To {_snap_line(report.new)}</p>
<p class="meta">{total} change{"s" if total != 1 else ""}{big_note} · generated {_esc(report.generated)}</p>
{table}
{"".join(f'<p class="meta">{n}</p>' for n in notes)}
<p class="legend"><ins>inserted</ins> <del>deleted</del> · a new paragraph sits under a green rule · a rewritten paragraph shows its new text, with “show the earlier draft” under it · <ins class="pilcrow">¶</ins> paragraph split, <del class="pilcrow">¶</del> paragraphs joined · <b>Changes</b> folds the unchanged text, <b>Whole chapter</b> shows it all (<kbd>e</kbd>), <b>Clean text</b> is the new version to read straight through · <kbd>j</kbd>/<kbd>k</kbd> or <kbd>n</kbd>/<kbd>p</kbd> next/previous change</p>
</header>
{"".join(body)}
<footer>autonovel mechanical diff-chapters · pairing threshold {report.threshold:g}</footer>
</div></main>
</div>
<script>{_JS}</script>
</body>
</html>
"""


def render_hunk_list(report: DiffReport, *, clip: int = 400) -> str:
    """Compact markdown listing of every hunk -- id, fingerprint, the
    deleted and inserted runs only -- for the `/autonovel:diff
    --annotate` step, which writes a `what` note, a `why` and a `big`
    flag per hunk id. Keeps the annotator's context small (the JSON
    sidecar carries whole paragraphs and rendered HTML)."""
    t = report.totals()
    out = [
        f"# Changes in {report.book}: {report.old.description} → "
        f"{report.new.description} ({t['hunks']})",
        "",
        "Annotate with a JSON object keyed by hunk id -- "
        '`{"what": "...", "why": "...", "big": true, "fp": "<fp>"}` -- and '
        "optionally by chapter key, e.g. `ch05`, for a one-line chapter summary. "
        "A `(rewritten)` change lists the whole old and new paragraph.",
    ]
    for f in report.chapters + report.foundation:
        if not f.hunks:
            continue
        head = f.label + (f" — {f.title}" if f.title and f.kind == "chapter" else "")
        out += ["", f"## {head} [{f.key}] ({f.status}; {len(f.hunks)} "
                    f"change{'s' if len(f.hunks) != 1 else ''})"]
        for h in f.hunks:
            out.append(f"- {h.id} (fp {h.fp}) ¶{h.index + 1} "
                       f"+{h.words_added} −{h.words_removed}"
                       + (f", {h.moved} moved" if h.moved else "")
                       + (" (rewritten)" if h.rewritten else ""))
            if f.status in ("added", "removed"):
                out.append(f"  {'+' if f.status == 'added' else '−'} whole file "
                           f"({f.words_new or f.words_old} words), opening "
                           f"`{_clip(h.snippet, 120)}`")
                continue
            for old, new in h.changes:
                if old and new:
                    out.append(f"  ~ `{_clip(old, clip)}` → `{_clip(new, clip)}`")
                elif old:
                    out.append(f"  − `{_clip(old, clip)}`")
                else:
                    out.append(f"  + `{_clip(new, clip)}`")
    return "\n".join(out) + "\n"


# ===================================================================
# CLI
# ===================================================================


def _chapters_slug(nums: list[int]) -> str:
    """``[1, 2, 5, 9, 10, 11]`` -> ``ch01-02_05_09-11``."""
    return "ch" + "_".join("-".join(f"{int(x):02d}" for x in part.split("–"))
                           for part in _ranges(nums).split(", "))


def default_paths(series_root: Path, book: str, report: DiffReport) -> tuple[Path, Path]:
    """``edit_logs/diff_<from>_<to>[_chNN-MM]``: a page limited to some
    chapters has its own name, so one chapter's page (a revise hand-back)
    never overwrites another chapter's or the whole book's."""
    stem = f"diff_{sanitize_ref(report.old.label)}_{sanitize_ref(report.new.label)}"
    if report.chapter_filter:
        stem += "_" + sanitize_ref(_chapters_slug(report.chapter_filter))
    d = series_root / "books" / book / "edit_logs"
    return d / f"{stem}.html", d / f"{stem}.json"


def _paths_from_out(out: str) -> tuple[Path, Path]:
    p = Path(out)
    if p.suffix.lower() == ".json":
        return p.with_suffix(".html"), p
    if p.suffix.lower() not in (".html", ".htm"):
        p = p.with_name(p.name + ".html")
    return p, p.with_suffix(".json")


def why_path_for(html_path: Path) -> Path:
    return html_path.with_name(html_path.stem + ".why.json")


def _open_hint(path: Path) -> str:
    """A path the author can paste into a browser. Under WSL the Linux
    path is offered as its Windows UNC form."""
    p = path.resolve()
    distro = os.environ.get("WSL_DISTRO_NAME")
    if distro:
        return "\\\\wsl.localhost\\" + distro + str(p).replace("/", "\\")
    return p.as_uri()


def _infer_book(series_root: Path) -> str:
    books = series_root / "books"
    names = sorted(p.name for p in books.iterdir() if p.is_dir()) if books.is_dir() else []
    if len(names) == 1:
        return names[0]
    raise DiffError("pass --book <name>"
                    + (f" (books: {', '.join(names)})" if names else " (no books/ found)"))


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--book", default=None,
                   help="Book short-name (default: the only book in the series).")
    p.add_argument("--series-root", default=None,
                   help="Series root (default: walk up from cwd to project.yaml, else cwd).")
    p.add_argument("--from", dest="from_spec", default="last-tag",
                   help="Old version: git ref/tag/sha, checkpoint:<ts> | checkpoint:latest, "
                        "a checkpoint dir, last-read, or last-tag (default).")
    p.add_argument("--to", dest="to_spec", default="worktree",
                   help="New version: git ref/tag/sha, checkpoint:<ts>, or worktree (default).")
    p.add_argument("--chapters", default=None,
                   help="Limit to chapters, e.g. 5, 3-7, 2,5,9-11.")
    p.add_argument("--format", choices=("html", "json", "hunks"), default="html",
                   help="html (default) writes the HTML page and its JSON sidecar; "
                        "json writes only the JSON; hunks writes nothing and prints a "
                        "compact markdown list of changes (for annotation).")
    p.add_argument("--out", default=None,
                   help="Output path (.html, or .json for the data file). Default "
                        "books/<book>/edit_logs/diff_<from>_<to>.html.")
    p.add_argument("--why", default=None,
                   help="Annotation sidecar rendered into the page: {hunk_id: why} or "
                        "{hunk_id: {what, why, big, fp}}, plus {chapter_key: summary}.")
    p.add_argument("--mark-read", action="store_true",
                   help="After writing the diff, record --to as the last-read bookmark "
                        "(books/<book>/edit_logs/last_read.json).")
    p.add_argument("--if-read", action="store_true",
                   help="With --from last-read: write the page only when the author has "
                        "read these chapters -- the bookmark resolves and a selected "
                        "chapter existed at that version and has changed since. Otherwise "
                        "write nothing and print {\"skipped\": reason}. For revise / draft "
                        "handing a rewritten chapter back.")
    p.add_argument("--foundation", action=argparse.BooleanOptionalAction, default=None,
                   help="Include voice/outline/canon diffs (default: on unless --chapters).")
    p.add_argument("--context", type=int, default=1,
                   help="Unchanged paragraphs shown around each change (default 1).")
    p.add_argument("--story-map", action=argparse.BooleanOptionalAction, default=True,
                   help="Also rebuild story_map.html (synopsis, threads, characters, "
                        "timeline, places) beside the diff page and link the two "
                        "(default on; html format only).")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                   help="Similarity ratio for showing an old/new paragraph pair as one "
                        f"edited paragraph (default {DEFAULT_THRESHOLD}).")


def _write_story_map_beside(series_root: Path, book: str, report: DiffReport,
                            html_path: Path) -> dict:
    """Rebuild story_map.html in the diff page's folder, linked to this
    diff. A story-map failure never fails the diff: it comes back as
    {"html": None, "error": ...} and the diff page simply has no link."""
    from .story_map import build_story_map, write_story_map
    counts = {f.chapter: len(f.hunks) for f in report.chapters
              if f.chapter is not None and f.hunks}
    try:
        sm = build_story_map(series_root / "books" / book, series_root=series_root)
        out = write_story_map(sm, out=html_path.parent / "story_map.html",
                              diff_page=(html_path.name, counts))
    except Exception as e:  # noqa: BLE001 — the diff is the product here
        return {"html": None, "error": f"{type(e).__name__}: {e}"}
    return {"html": out["html"], "open": _open_hint(Path(out["html"])),
            "warnings": out["warnings"]}


def cli(args: argparse.Namespace) -> int:
    from ..paths import SeriesNotFound, find_series_root
    try:
        if args.series_root:
            series_root = Path(args.series_root).resolve()
        else:
            try:
                series_root = find_series_root(Path.cwd())
            except SeriesNotFound:
                series_root = Path.cwd().resolve()
        book = args.book or _infer_book(series_root)
        chapters = parse_chapter_spec(args.chapters)
        if getattr(args, "if_read", False) and args.from_spec != "last-read":
            raise DiffError("--if-read needs --from last-read")
        report = build_diff(
            series_root, book, from_spec=args.from_spec, to_spec=args.to_spec,
            chapters=chapters, foundation=args.foundation,
            threshold=args.threshold,
        )
        if args.why:
            apply_why(report, load_why(Path(args.why)))
    except (DiffError, ValueError, OSError, json.JSONDecodeError) as e:
        print(f"diff-chapters: {e}", file=sys.stderr)
        return 2

    skipped = unread_reason(report, book) if getattr(args, "if_read", False) else None
    if skipped:
        json.dump({"skipped": skipped, "html": None, "from": report.old.to_dict(),
                   "to": report.new.to_dict()}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if args.format == "hunks":
        sys.stdout.write(render_hunk_list(report))
        return 0

    if args.out:
        html_path, json_path = _paths_from_out(args.out)
    else:
        html_path, json_path = default_paths(series_root, book, report)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    data = report.to_dict()
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    wrote_html = None
    story_map: dict | None = None
    if args.format == "html":
        html_path.parent.mkdir(parents=True, exist_ok=True)
        if getattr(args, "story_map", True):
            story_map = _write_story_map_beside(series_root, book, report, html_path)
        html_path.write_text(
            render_html(report, context=max(0, args.context),
                        story_map_href=("story_map.html"
                                        if story_map and story_map.get("html") else None)),
            encoding="utf-8")
        wrote_html = html_path
    bookmark = write_bookmark(series_root, book, report.new) if args.mark_read else None

    t = report.totals()
    summary = {
        "html": str(wrote_html.resolve()) if wrote_html else None,
        "json": str(json_path.resolve()),
        "open": _open_hint(wrote_html) if wrote_html else None,
        "why_path": str(why_path_for(html_path).resolve()),
        "from": report.old.to_dict(),
        "to": report.new.to_dict(),
        **{k: t[k] for k in ("hunks", "big_hunks", "chapter_hunks", "foundation_hunks",
                              "chapters_changed", "chapters_compared",
                              "words_added", "words_removed", "net_words")},
        "why_applied": report.why_applied,
        "why_stale": report.why_stale,
        "bookmark": bookmark,
        "story_map": story_map,
        "chapters": [
            {"chapter": f.chapter, "title": f.title, "status": f.status,
             "hunks": len(f.hunks), "words_added": f.words_added,
             "words_removed": f.words_removed, "net": f.net}
            for f in report.changed_chapters
        ],
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0
