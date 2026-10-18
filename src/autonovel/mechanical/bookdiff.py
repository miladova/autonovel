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
   paragraph) with a small monotonic DP that maximises matched words, so
   a one-word edit shows as one inline change instead of a whole
   paragraph deleted and re-inserted. Unpaired paragraphs are pure
   deletions or insertions (and "moved" when the same text is deleted in
   one place and inserted in another).
3. **Word-level diff inside a pair.** Tokens are whitespace-split words
   with punctuation attached; `SequenceMatcher` over the token lists,
   then a semantic cleanup that folds short coincidental equalities (a
   stray "the" inside a rewritten sentence) into the surrounding edit,
   as diff-match-patch's ``cleanupSemantic`` does.

Pure mechanical; no LLM. `/autonovel:diff --annotate` adds one-line
*why* annotations by writing a sidecar JSON that ``--why`` feeds back in.
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


def word_diff(old_tokens: list[str], new_tokens: list[str]) -> list[Seg]:
    """Token-level diff with semantic cleanup."""
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
    return _cleanup_semantic(segs)


def _seg_counts(segs: list[Seg]) -> tuple[int, int]:
    added = sum(_word_count_tokens(s.new) for s in segs if s.tag == "chg")
    removed = sum(_word_count_tokens(s.old) for s in segs if s.tag == "chg")
    return added, removed


# ===================================================================
# Paragraph pairing inside a hunk
# ===================================================================


def _matched_tokens(a: list[str], b: list[str], threshold: float) -> int | None:
    """Matched-token count when ``a`` and ``b`` are similar enough to
    pair (ratio >= threshold), else None."""
    if not a or not b:
        return None
    la, lb = len(a), len(b)
    if 2.0 * min(la, lb) / (la + lb) < threshold:  # real_quick_ratio bound
        return None
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.quick_ratio() < threshold:
        return None
    matched = sum(blk.size for blk in sm.get_matching_blocks())
    if 2.0 * matched / (la + lb) < threshold:
        return None
    return matched


def pair_paragraphs(old_toks: list[list[str]], new_toks: list[list[str]],
                    *, threshold: float = DEFAULT_THRESHOLD,
                    ) -> list[tuple[str, list[int], list[int]]]:
    """Align the old and new paragraphs of one hunk.

    Returns display-ordered items ``(kind, old_indices, new_indices)``
    with kind ``pair`` (1:1, 1:2 split, 2:1 merge), ``del`` or ``ins``.
    A monotonic DP maximises the total matched-token count; ties prefer
    a 1:1 pair, then deletions before insertions. Large hunks restrict
    pairing to a diagonal band so a whole-chapter rewrite stays fast.
    """
    n, m = len(old_toks), len(new_toks)
    if n == 0:
        return [("ins", [], [j]) for j in range(m)]
    if m == 0:
        return [("del", [i], []) for i in range(n)]
    band = None if n * m <= 400 else 6
    cache: dict[tuple[int, int, int, int], int | None] = {}

    def gain(i0: int, i1: int, j0: int, j1: int) -> int | None:
        key = (i0, i1, j0, j1)
        if key not in cache:
            cache[key] = _matched_tokens(
                _join_tokens(old_toks[i0:i1]), _join_tokens(new_toks[j0:j1]),
                threshold,
            )
        return cache[key]

    def in_band(i: int, j: int) -> bool:
        return band is None or abs(i * m / n - j) <= band

    best = [[0] * (m + 1) for _ in range(n + 1)]
    move: list[list[tuple[str, int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if i == n and j == m:
                continue
            # (score, -priority, move) -- max() picks highest score,
            # then lowest priority number.
            cands: list[tuple[int, int, tuple[str, int, int]]] = []
            if i < n and j < m and in_band(i, j):
                g = gain(i, i + 1, j, j + 1)
                if g is not None:
                    cands.append((best[i + 1][j + 1] + g, 0, ("pair", 1, 1)))
                if j + 1 < m:
                    g = gain(i, i + 1, j, j + 2)
                    if g is not None:
                        cands.append((best[i + 1][j + 2] + g, -1, ("pair", 1, 2)))
                if i + 1 < n:
                    g = gain(i, i + 2, j, j + 1)
                    if g is not None:
                        cands.append((best[i + 2][j + 1] + g, -1, ("pair", 2, 1)))
            if i < n:
                cands.append((best[i + 1][j], -2, ("del", 1, 0)))
            if j < m:
                cands.append((best[i][j + 1], -3, ("ins", 0, 1)))
            score, _, mv = max(cands, key=lambda c: (c[0], c[1]))
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


_BOLD_RE = re.compile(r"\*\*(?=\S)([^*<>]+?)(?<=\S)\*\*")
_ITAL_RE = re.compile(r"(?<![\w*])\*(?=\S)([^*<>]+?)(?<=\S)\*(?![\w*])")
_HEADING_TOKEN_RE = re.compile(r"^#{1,6}$")
_BREAK_RE = re.compile(r"^(?:(?:\*\s*){3,}|(?:-\s*){3,}|⁂|#)$")


def _inline_md(inner: str) -> str:
    """Render ``**bold**`` / ``*italic*`` that sit inside one text run
    (a span crossing an ins/del boundary is left as literal asterisks)."""
    inner = _BOLD_RE.sub(r"<strong>\1</strong>", inner)
    return _ITAL_RE.sub(r"<em>\1</em>", inner)


def _esc(s: str) -> str:
    return _html.escape(s, quote=True)


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
        inner = _inline_md(" ".join(parts))
        out.append(f'<p class="{" ".join(classes)}">{tag_html}{inner}</p>')
        parts.clear()
        kinds.clear()
        plain.clear()

    def run(tokens: list[str], tag: str) -> None:
        buf: list[str] = []

        def emit() -> None:
            if buf:
                inner = " ".join(buf)
                parts.append(inner if tag == "eq" else f"<{tag}>{inner}</{tag}>")
                kinds.add(tag)
                buf.clear()

        for t in tokens:
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
            elif t == LB:
                buf.append("<br>")
            else:
                buf.append(_esc(t))
                plain.append(t)
        emit()

    for s in segs:
        if s.tag == "eq":
            run(s.old, "eq")
        else:
            run(s.old, "del")
            run(s.new, "ins")
    flush()
    return out


def render_plain_paragraph(p: str, *, extra_class: str = "") -> str:
    """An unchanged paragraph as one ``<p class="p-eq ...">``."""
    toks = tokenize(p)
    return render_segments([Seg("eq", toks, toks)], para_class=extra_class)[0]


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
    n: int = 0                 # 1-based ordinal across the whole report
    why: str | None = None
    snippet: str = ""
    # The changed runs only, in reading order, as [old, new] pairs
    # ("" on one side for a pure deletion / insertion) -- what the
    # annotation step reads instead of whole paragraphs.
    changes: list[list[str]] = field(default_factory=list)

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
            "moved": self.moved, "fp": self.fp, "why": self.why,
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


def _snippet(segs_or_text: list[Seg] | str, limit: int = 60) -> str:
    """Plain-text locator for the sidebar: the first changed words with
    two or three words of unchanged context either side."""
    if isinstance(segs_or_text, str):
        return _clip(" ".join(_words(tokenize(segs_or_text))), limit)
    segs = segs_or_text
    for k, s in enumerate(segs):
        if s.tag != "chg":
            continue
        changed = _words(s.new) or _words(s.old)
        if not changed:
            continue
        before = _words(segs[k - 1].old)[-3:] if k > 0 else []
        after = _words(segs[k + 1].old)[:2] if k + 1 < len(segs) else []
        text = " ".join(before + changed[:8] + after)
        return _clip(("… " if before else "") + text, limit)
    return ""


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
        added = removed = moved = 0
        snippet = ""
        changes: list[list[str]] = []
        for kind_, ii, jj in b["items"]:
            if kind_ == "pair":
                segs = word_diff(
                    _join_tokens([old_toks[i1 + i] for i in ii]),
                    _join_tokens([new_toks[j1 + j] for j in jj]),
                )
                html_parts += render_segments(segs)
                a, r = _seg_counts(segs)
                added += a
                removed += r
                snippet = snippet or _snippet(segs)
                for s in segs:
                    if s.tag == "chg" and (_words(s.old) or _words(s.new)):
                        changes.append([" ".join(_words(s.old)), " ".join(_words(s.new))])
            elif kind_ == "del":
                text = old_paras[i1 + ii[0]]
                is_moved = text in moved_texts
                html_parts += render_segments(
                    [Seg("chg", old_toks[i1 + ii[0]], [])],
                    para_class="p-moved" if is_moved else "",
                    tag_html='<span class="tag">moved from here</span> ' if is_moved else "",
                )
                if is_moved:
                    moved += 1
                else:
                    removed += _word_count_tokens(old_toks[i1 + ii[0]])
                    changes.append([" ".join(_words(old_toks[i1 + ii[0]])), ""])
                snippet = snippet or _snippet(text)
            else:
                text = new_paras[j1 + jj[0]]
                is_moved = text in moved_texts
                html_parts += render_segments(
                    [Seg("chg", [], new_toks[j1 + jj[0]])],
                    para_class="p-moved" if is_moved else "",
                    tag_html='<span class="tag">moved here</span> ' if is_moved else "",
                )
                if is_moved:
                    moved += 1
                else:
                    added += _word_count_tokens(new_toks[j1 + jj[0]])
                    changes.append(["", " ".join(_words(new_toks[j1 + jj[0]]))])
                snippet = snippet or _snippet(text)
        hunks.append(Hunk(
            id=f"{key}-{bi + 1:03d}", key=key, file=file, chapter=chapter,
            kind=kind, index=j1, old_index=i1,
            old_paragraphs=old_paras[i1:i2], new_paragraphs=new_paras[j1:j2],
            inline_html="\n".join(html_parts),
            words_added=added, words_removed=removed,
            context_before=new_paras[j1 - 1] if j1 > 0 else None,
            context_after=new_paras[j2] if j2 < len(new_paras) else None,
            fp=_fingerprint(old_paras[i1:i2], new_paras[j1:j2]),
            moved=moved, snippet=snippet,
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
            "pinned": self.pinned, "note": self.note, **self.meta,
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
                return snap
            for cand in (sha, ref):
                if cand and is_git_repo(series_root) and resolve_commit(series_root, str(cand)):
                    full = resolve_commit(series_root, str(cand)) or ""
                    return _git_snapshot_for_ref(
                        series_root, full, spec=spec, label=f"last-read-{full[:7]}",
                        note=f"last read {when} at {ref or full[:7]}",
                    )
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


def load_why(path: Path) -> dict[str, dict]:
    """Load a why sidecar: ``{id: "why"}`` or ``{id: {"why": ..., "fp": ...}}``.

    Keys are hunk ids (``ch05-002``) or chapter keys (``ch05``) for a
    per-chapter change summary."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DiffError(f"{path}: expected a JSON object mapping hunk id -> why")
    out: dict[str, dict] = {}
    for k, v in data.items():
        if isinstance(v, str):
            out[str(k)] = {"why": v}
        elif isinstance(v, dict) and isinstance(v.get("why"), str):
            out[str(k)] = {"why": v["why"], "fp": v.get("fp")}
    return out


def apply_why(report: DiffReport, why: dict[str, dict]) -> None:
    applied = 0
    stale: list[str] = []
    for h in report.all_hunks:
        w = why.get(h.id)
        if not w or not w["why"].strip():
            continue
        if w.get("fp") and w["fp"] != h.fp:
            stale.append(h.id)
            continue
        h.why = w["why"].strip()
        applied += 1
    for f in report.chapters + report.foundation:
        w = why.get(f.key)
        if w and w["why"].strip() and f.kind != "summary":
            f.why = w["why"].strip()
            applied += 1
    report.why_applied = applied
    report.why_stale = stale


# ===================================================================
# HTML
# ===================================================================


_CSS = r"""
:root {
  --bg: #fbfaf7; --fg: #1f1d1a; --muted: #6b665e; --rule: #e2ddd3;
  --panel: #f2efe8; --link: #2f5d8a; --accent: #2f5d8a; --current: #d9a400;
  --ins-bg: #d9f2dd; --ins-fg: #0d5520; --del-bg: #fadede; --del-fg: #8f1d1d;
  --why-bg: #eaf1f8; --why-fg: #1d3b57; --badge: #e6e1d6;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15171a; --fg: #e5e2dc; --muted: #9b968d; --rule: #2d3136;
    --panel: #1d2024; --link: #8fb9e6; --accent: #6f9fd3; --current: #e0b33a;
    --ins-bg: #173b23; --ins-fg: #a9e6b8; --del-bg: #4a1e20; --del-fg: #f4b3b0;
    --why-bg: #1b2a3a; --why-fg: #cfe0f2; --badge: #2a2e33;
  }
}
* { box-sizing: border-box; }
html { scroll-padding-top: 4.25rem; -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--link); }
.toolbar { position: sticky; top: 0; z-index: 20; display: flex; flex-wrap: wrap;
  align-items: center; gap: .4rem .6rem; padding: .45rem 16px;
  background: var(--panel); border-bottom: 1px solid var(--rule); }
.toolbar .title { font-weight: 600; margin-right: auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toolbar button { font: inherit; padding: .3rem .7rem; border-radius: 6px;
  border: 1px solid var(--rule); background: var(--bg); color: var(--fg); cursor: pointer; }
.toolbar button:hover { border-color: var(--accent); }
.toolbar label { white-space: nowrap; color: var(--muted); }
.toolbar .maplink { white-space: nowrap; font-weight: 600; }
.counter { font-variant-numeric: tabular-nums; white-space: nowrap; }
#navtoggle { display: none; }
.layout { display: grid; grid-template-columns: 18rem minmax(0, 1fr); }
aside { position: sticky; top: 2.9rem; align-self: start; height: calc(100vh - 2.9rem);
  overflow: auto; border-right: 1px solid var(--rule); padding: .75rem 12px 2rem;
  font-size: .82rem; background: var(--bg); }
aside h3 { font-size: .8rem; margin: .9rem 0 .3rem; text-transform: none; }
aside h3 a { color: var(--fg); text-decoration: none; }
aside ol { list-style: none; margin: 0; padding: 0; }
aside li a { display: block; padding: .15rem .35rem; border-radius: 4px;
  color: var(--fg); text-decoration: none; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
aside li a:hover { background: var(--panel); }
aside li a.active { background: var(--why-bg); outline: 1px solid var(--accent); }
aside .n { display: inline-block; min-width: 2.2em; color: var(--muted);
  font-variant-numeric: tabular-nums; }
.plus { color: var(--ins-fg); } .minus { color: var(--del-fg); }
main { padding: 1rem 16px 5rem; min-width: 0; }
.wrap { max-width: 44rem; margin: 0 auto; }
header.report h1 { font-size: 1.35rem; margin: .2rem 0 .4rem; }
.meta { color: var(--muted); margin: .15rem 0; overflow-wrap: anywhere; }
.note { color: var(--muted); font-style: italic; }
.legend { margin: .6rem 0 1rem; color: var(--muted); }
.tablewrap { overflow-x: auto; margin: .8rem 0 1.2rem; }
table { border-collapse: collapse; width: 100%; font-size: .9rem;
  font-variant-numeric: tabular-nums; }
th, td { padding: .3rem .5rem; border-bottom: 1px solid var(--rule); text-align: right;
  white-space: nowrap; }
th:nth-child(1), td:nth-child(1), th:nth-child(2), td:nth-child(2) { text-align: left; }
td:nth-child(2) { white-space: normal; min-width: 8rem; }
tr.total td { font-weight: 600; border-top: 2px solid var(--rule); }
.badge { display: inline-block; font: 600 .7rem/1.6 system-ui, sans-serif;
  padding: 0 .45rem; border-radius: 999px; background: var(--badge); color: var(--muted);
  vertical-align: middle; text-transform: uppercase; letter-spacing: .03em; }
.badge.added { background: var(--ins-bg); color: var(--ins-fg); }
.badge.removed { background: var(--del-bg); color: var(--del-fg); }
section.file { margin: 2.2rem 0 0; }
section.file > h2 { font-size: 1.15rem; margin: 0 0 .25rem; padding-top: .3rem;
  border-top: 1px solid var(--rule); }
section.group > h2 { font-size: 1.2rem; margin: 3rem 0 0; }
section.file.doc > h2 { font-size: 1rem; }
.file-why, .why { background: var(--why-bg); color: var(--why-fg); border-radius: 6px;
  padding: .35rem .6rem; margin: .4rem 0 .6rem; font-size: .9rem; }
.why b, .file-why b { font-weight: 600; }
.fm { color: var(--muted); font-size: .85rem; margin: .2rem 0 .6rem; padding-left: 1.1rem; }
.prose p { font-family: Georgia, "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
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
/* A wholly added / removed file reads as plain text under a coloured rule,
   not as a wall of highlight. */
.st-added .hunk { border-left-color: var(--ins-fg); }
.st-removed .hunk { border-left-color: var(--del-fg); }
.st-added .hunk ins { background: none; border-bottom: 0; color: inherit; padding: 0; }
.st-removed .hunk del { background: none; color: var(--del-fg); text-decoration: none; padding: 0; }
.p-moved { outline: 1px dashed var(--muted); outline-offset: 2px; }
.tag { font: 600 .68rem/1 system-ui, sans-serif; text-transform: uppercase;
  color: var(--muted); letter-spacing: .04em; }
.hunk { position: relative; border-left: 3px solid var(--accent);
  padding: .3rem 0 .1rem .8rem; margin: .9rem 0 1rem -.95rem; }
.hunk.current { border-left-color: var(--current); background:
  linear-gradient(to right, color-mix(in srgb, var(--current) 10%, transparent), transparent 60%); }
.hunk-head { font-size: .8rem; color: var(--muted); margin-bottom: .35rem;
  font-variant-numeric: tabular-nums; }
.hunk-head a { color: var(--muted); text-decoration: none; font-weight: 600; }
.hunk-head a:hover { color: var(--link); }
.fold { margin: .2rem 0 .7rem; }
.fold-toggle { font: .82rem/1.4 system-ui, sans-serif; color: var(--muted); width: 100%;
  text-align: left; background: none; border: 1px dashed var(--rule); border-radius: 6px;
  padding: .3rem .6rem; cursor: pointer; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.fold-toggle:hover { border-color: var(--accent); color: var(--fg); }
.fold-body { display: none; padding-top: .6rem; }
.fold.open .fold-body, body.show-all .fold-body { display: block; }
.fold.open .fold-toggle .peek, body.show-all .fold-toggle .peek { display: none; }
.empty { padding: 2rem 0; color: var(--muted); }
footer { color: var(--muted); font-size: .8rem; margin-top: 3rem; }
kbd { font: .75rem ui-monospace, monospace; border: 1px solid var(--rule);
  border-bottom-width: 2px; border-radius: 4px; padding: 0 .3rem; background: var(--panel); }
@media (max-width: 900px) {
  #navtoggle { display: inline-block; }
  .layout { display: block; }
  aside { display: none; position: fixed; z-index: 30; top: 2.9rem; left: 0;
    width: min(88vw, 22rem); height: calc(100vh - 2.9rem);
    box-shadow: 0 0 0 100vmax rgba(0,0,0,.35); }
  body.nav-open aside { display: block; }
  .hunk { margin-left: -.6rem; padding-left: .55rem; }
  .toolbar label .long { display: none; }
}
th .s { display: none; }
@media (max-width: 600px) {
  th:nth-child(3), td:nth-child(3), th:nth-child(7), td:nth-child(7) { display: none; }
  th, td { padding: .3rem .3rem; }
  td:nth-child(2) { min-width: 0; }
  th .l { display: none; } th .s { display: inline; }
}
@media print {
  .toolbar, aside, .fold-toggle { display: none !important; }
  .layout { display: block; } .fold-body { display: block !important; }
}
"""

_JS = r"""
(function () {
  var hunks = Array.prototype.slice.call(document.querySelectorAll('.hunk'));
  var total = hunks.length, cur = -1, lockUntil = 0;
  var curEl = document.getElementById('cur');
  var bar = document.querySelector('.toolbar');
  function link(h) { return document.querySelector('aside a[href="#' + h.id + '"]'); }
  function setCurrent(i, jump) {
    if (!total) return;
    i = Math.max(0, Math.min(total - 1, i));
    if (cur >= 0) {
      hunks[cur].classList.remove('current');
      var old = link(hunks[cur]); if (old) old.classList.remove('active');
    }
    cur = i;
    var h = hunks[cur];
    h.classList.add('current');
    curEl.textContent = String(cur + 1);
    var a = link(h);
    if (a) { a.classList.add('active'); a.scrollIntoView({block: 'nearest'}); }
    if (jump) {
      lockUntil = Date.now() + 600;
      h.scrollIntoView({block: 'start'});
      if (history.replaceState) history.replaceState(null, '', '#' + h.id);
    }
  }
  function next() { setCurrent(cur + 1, true); }
  function prev() { setCurrent(cur <= 0 ? 0 : cur - 1, true); }
  var nb = document.getElementById('next'), pb = document.getElementById('prev');
  if (nb) nb.addEventListener('click', next);
  if (pb) pb.addEventListener('click', prev);
  var all = document.getElementById('showall');
  function setAll(v) { document.body.classList.toggle('show-all', v); if (all) all.checked = v; }
  if (all) all.addEventListener('change', function () { setAll(all.checked); });
  var nt = document.getElementById('navtoggle');
  if (nt) nt.addEventListener('click', function () { document.body.classList.toggle('nav-open'); });
  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (e.key === 'j' || e.key === 'n') { next(); e.preventDefault(); }
    else if (e.key === 'k' || e.key === 'p') { prev(); e.preventDefault(); }
    else if (e.key === 'e') { setAll(!document.body.classList.contains('show-all')); }
    else if (e.key === 'Escape') { document.body.classList.remove('nav-open'); }
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.fold-toggle') : null;
    if (b) {
      var f = b.parentNode, open = !f.classList.contains('open');
      f.classList.toggle('open', open);
      b.setAttribute('aria-expanded', open ? 'true' : 'false');
      return;
    }
    var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
    if (a) {
      var target = document.getElementById(a.getAttribute('href').slice(1));
      var k = hunks.indexOf(target);
      if (k >= 0) { e.preventDefault(); setCurrent(k, true); }
      else if (target) { k = firstHunkFrom(target); if (k >= 0) { lockUntil = Date.now() + 600; setCurrent(k, false); } }
      document.body.classList.remove('nav-open');
    }
  });
  // First change inside or after a section heading / anchor.
  function firstHunkFrom(el) {
    for (var i = 0; i < total; i++) {
      if (el.contains(hunks[i]) || (el.compareDocumentPosition(hunks[i]) & 4)) return i;
    }
    return -1;
  }
  function spy() {
    if (!total || Date.now() < lockUntil) return;
    var top = (bar ? bar.getBoundingClientRect().bottom : 0) + 24, idx = -1;
    if (cur >= 0) {
      var r = hunks[cur].getBoundingClientRect();
      if (r.top >= top - 24 && r.bottom <= window.innerHeight) return;
    }
    for (var i = 0; i < total; i++) {
      if (hunks[i].getBoundingClientRect().top <= top) idx = i; else break;
    }
    if (idx >= 0 && idx !== cur) setCurrent(idx, false);
  }
  var ticking = false;
  window.addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function () { ticking = false; spy(); });
  }, {passive: true});
  if (location.hash) {
    var el = document.getElementById(location.hash.slice(1));
    var k = hunks.indexOf(el);
    if (k >= 0) setCurrent(k, true);
    else if (el) { k = firstHunkFrom(el); if (k >= 0) { lockUntil = Date.now() + 600; setCurrent(k, false); } }
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


def _render_flow(f: FileDiff, *, context: int, total: int) -> str:
    out: list[str] = []
    flow = f.flow
    for idx, (kind, val) in enumerate(flow):
        if kind == "hunk":
            h: Hunk = val
            stats = (f'<span class="plus">+{h.words_added}</span> '
                     f'<span class="minus">−{h.words_removed}</span>')
            moved = f" · {h.moved} moved" if h.moved else ""
            why = (f'<div class="why"><b>Why:</b> {_esc(h.why)}</div>' if h.why else "")
            out.append(
                f'<div class="hunk" id="{_esc(h.id)}" data-n="{h.n}">'
                f'<div class="hunk-head"><a href="#{_esc(h.id)}">Change {h.n} of {total}</a>'
                f' · ¶{h.index + 1} · {stats} words{moved}</div>{why}'
                f'{h.inline_html}</div>'
            )
            continue
        paras: list[str] = val
        has_prev = idx > 0
        has_next = idx < len(flow) - 1
        head = paras[:context] if has_prev else []
        tail = paras[len(paras) - context:] if has_next and context else []
        if len(head) + len(tail) >= len(paras):
            for p in paras:
                out.append(render_plain_paragraph(p, extra_class="ctx"))
            continue
        middle = paras[len(head):len(paras) - len(tail)]
        for p in head:
            out.append(render_plain_paragraph(p, extra_class="ctx"))
        if len(middle) == 1:
            out.append(render_plain_paragraph(middle[0], extra_class="ctx"))
        elif middle:
            words = _word_count_paras(middle)
            peek = _esc(_snippet(middle[0], 70))
            body = "\n".join(render_plain_paragraph(p) for p in middle)
            out.append(
                f'<div class="fold"><button type="button" class="fold-toggle" '
                f'aria-expanded="false">⋯ {len(middle)} unchanged paragraphs · '
                f'{_fmt_int(words)} words <span class="peek">— {peek}</span></button>'
                f'<div class="fold-body">{body}</div></div>'
            )
        for p in tail:
            out.append(render_plain_paragraph(p, extra_class="ctx"))
    return "\n".join(out)


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
        f'<p class="meta">{_esc(f.file)} · {stats}'
        + (f' · <a href="{_esc(story_map_href)}#ch-{f.chapter}">this chapter in the '
           f'story map</a>' if story_map_href and f.kind == "chapter" and f.chapter else "")
        + '</p>',
    ]
    if f.why:
        parts.append(f'<div class="file-why"><b>What changed:</b> {_esc(f.why)}</div>')
    if f.frontmatter_changes:
        items = "".join(
            f"<li>{_esc(k)}: <del>{_esc(str(o))}</del> → <ins>{_esc(str(n))}</ins></li>"
            for k, (o, n) in f.frontmatter_changes.items()
        )
        parts.append(f'<ul class="fm">{items}</ul>')
    parts.append(f'<div class="prose">{_render_flow(f, context=context, total=total)}</div>')
    parts.append("</section>")
    return "\n".join(parts)


def _sidebar(report: DiffReport) -> str:
    out: list[str] = []
    for f in report.chapters + report.foundation:
        if not f.hunks:
            continue
        label = f.label + (f" · {f.title}" if f.title and f.kind == "chapter" else "")
        out.append(f'<h3><a href="#file-{_esc(f.key)}">{_esc(label)}</a> '
                   f'<span class="n">({len(f.hunks)})</span></h3><ol>')
        for h in f.hunks:
            out.append(
                f'<li><a href="#{_esc(h.id)}" title="{_esc(h.snippet)}">'
                f'<span class="n">{h.n}</span>'
                f'<span class="plus">+{h.words_added}</span> '
                f'<span class="minus">−{h.words_removed}</span> '
                f'{_esc(h.snippet)}</a></li>'
            )
        out.append("</ol>")
    return "\n".join(out) or '<p class="note">No changes.</p>'


def render_html(report: DiffReport, *, context: int = 1,
                story_map_href: str | None = None) -> str:
    """One self-contained page: inline CSS + JS, no external requests.
    `story_map_href` (the story map written beside it) adds a Story map
    link to the toolbar and to every chapter's heading line."""
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

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="generator" content="autonovel mechanical diff-chapters">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="toolbar" role="toolbar" aria-label="Change navigation">
  <button type="button" id="navtoggle" aria-label="List of changes">☰ Changes</button>
  <span class="title">{_esc(title)}</span>
  <button type="button" id="prev" title="Previous change (k or p)">◀ Prev</button>
  <span class="counter">change <b id="cur">–</b> of <b id="total">{total}</b></span>
  <button type="button" id="next" title="Next change (j or n)">Next ▶</button>
  {f'<a class="maplink" href="{_esc(story_map_href)}" title="Synopsis, threads, characters, timeline and places">Story map</a>' if story_map_href else ''}
  <label title="Expand every unchanged paragraph (e)"><input type="checkbox" id="showall"> <span class="long">show all </span>context</label>
</div>
<div class="layout">
<aside aria-label="Changes by chapter">{_sidebar(report)}</aside>
<main><div class="wrap">
<header class="report">
<h1>{_esc(report.book)}: what changed</h1>
<p class="meta">From {_snap_line(report.old)}</p>
<p class="meta">To {_snap_line(report.new)}</p>
<p class="meta">{total} change{"s" if total != 1 else ""} · generated {_esc(report.generated)}</p>
{table}
{"".join(f'<p class="meta">{n}</p>' for n in notes)}
<p class="legend"><ins>inserted</ins> <del>deleted</del> · <ins class="pilcrow">¶</ins> paragraph split, <del class="pilcrow">¶</del> paragraphs joined · <kbd>j</kbd>/<kbd>k</kbd> or <kbd>n</kbd>/<kbd>p</kbd> next/previous change · <kbd>e</kbd> show all context</p>
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
    --annotate` step, which writes one `why` per hunk id. Keeps the
    annotator's context small (the JSON sidecar carries whole
    paragraphs and rendered HTML)."""
    t = report.totals()
    out = [
        f"# Changes in {report.book}: {report.old.description} → "
        f"{report.new.description} ({t['hunks']})",
        "",
        "Annotate with a JSON object keyed by hunk id (and optionally by "
        "chapter key, e.g. `ch05`, for a one-line chapter summary).",
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
                       + (f", {h.moved} moved" if h.moved else ""))
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


def default_paths(series_root: Path, book: str, report: DiffReport) -> tuple[Path, Path]:
    stem = f"diff_{sanitize_ref(report.old.label)}_{sanitize_ref(report.new.label)}"
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
                   help="Annotation sidecar {hunk_id|chapter_key: why} rendered into the page.")
    p.add_argument("--mark-read", action="store_true",
                   help="After writing the diff, record --to as the last-read bookmark "
                        "(books/<book>/edit_logs/last_read.json).")
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
        **{k: t[k] for k in ("hunks", "chapter_hunks", "foundation_hunks",
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
