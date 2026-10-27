#!/usr/bin/env python3
"""Splice expansion inserts into chapter files.

Usage: python3 novel/apply_expansions.py MANIFEST.json
Manifest: [{"chapter": 1, "after_para": 3, "file": "ch01_a.txt"}, ...]
Paragraph indices refer to the chapter body as split on blank lines,
excluding the title line, in the file's state before this run.
Inserts for one chapter are applied from the highest index downward
so earlier indices stay valid. Each insert file is plain text with
paragraphs separated by blank lines. Run once per manifest.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent


def load_chapter(n):
    p = ROOT / "chapters" / f"ch{n:02d}.txt"
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    title, body = lines[0].strip(), "\n".join(lines[1:])
    paras = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    return p, title, paras


def main():
    manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    by_chapter = {}
    for item in manifest:
        by_chapter.setdefault(item["chapter"], []).append(item)
    for n, items in sorted(by_chapter.items()):
        p, title, paras = load_chapter(n)
        for item in sorted(items, key=lambda x: -x["after_para"]):
            insert_text = (ROOT / "expansions" / item["file"]).read_text(encoding="utf-8").strip()
            insert_paras = [b.strip() for b in re.split(r"\n\s*\n", insert_text) if b.strip()]
            idx = item["after_para"] + 1
            paras[idx:idx] = insert_paras
            print(f"ch{n:02d}: +{sum(len(x.split()) for x in insert_paras)} words after para {item['after_para']}")
        p.write_text(title + "\n\n" + "\n\n".join(paras) + "\n", encoding="utf-8")
        print(f"ch{n:02d}: total {sum(len(x.split()) for x in paras)} words")


if __name__ == "__main__":
    main()
