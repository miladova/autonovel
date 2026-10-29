#!/usr/bin/env python3
"""Mechanical quality & word-count checker for By Second Intention."""
from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED_PATTERNS = [
    r"\bdelve[ds]?\b",
    r"\btapestr(?:y|ies)\b",
    r"\btestament to\b",
    r"\bmultifaceted\b",
    r"\bparadigm\b",
    r"\bsynerg(?:y|ies)\b",
    r"\bjuxtapos(?:e|ed|ing|ition)\b",
    r"\bmyriad\b",
    r"\bplethora\b",
    r"\bnot just\b.{1,40}\bbut\b",
    r"\bcouldn't help but\b",
    r"\bcould not help but\b",
    r"\ba breath she didn't know\b",
    r"\ba breath she had not known\b",
    r"\bshiver (?:ran|went|shot) down\b",
    r"\bsymphony of\b",
    r"\bkaleidoscope of\b",
    r"\bdance of\b",
    r"\bunbeknownst\b",
    r"\blittle did she know\b",
]


def check_dir(chap_dir: Path) -> int:
    files = sorted(chap_dir.glob("ch_*.md"))
    if not files:
        print("No chapters yet.")
        return 0
    total_words = 0
    issues = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if not ln.startswith("# ")]
        body = "\n".join(lines)
        words = len(re.findall(r"\b[\w'-]+\b", body, flags=re.UNICODE))
        breaks = len(re.findall(r"^\s*\*\s*\*\s*\*\s*$", body, flags=re.MULTILINE))
        scenes = breaks + 1
        total_words += words
        hits = []
        for pat in BANNED_PATTERNS:
            for m in re.finditer(pat, body, flags=re.IGNORECASE):
                hits.append(m.group(0))
        flag = ""
        if words < 5000:
            flag += f" [SHORT:{words}]"
        if scenes < 2 or scenes > 4:
            flag += f" [SCENES:{scenes}]"
        if hits:
            flag += f" [SLOP:{hits[:3]}]"
            issues += len(hits)
        print(f"{f.name}: {words:5d} words | {scenes} scenes{flag}")
    print(f"TOTAL across {len(files)} chapters: {total_words:,} words (avg {total_words // len(files):,}/ch)")
    return issues


if __name__ == "__main__":
    root = Path(__file__).resolve().parent / "chapters"
    sys.exit(check_dir(root))
