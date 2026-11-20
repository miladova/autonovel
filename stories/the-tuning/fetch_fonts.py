"""Fetch Crimson Text (SIL OFL) from google/fonts via the GitHub API.

raw.githubusercontent.com is not reachable from this sandbox, but
api.github.com is; the contents endpoint returns base64 for files <1 MB,
which covers every TTF in ofl/crimsontext.
"""
from __future__ import annotations

import base64
import json
import pathlib
import urllib.request

FILES = [
    "CrimsonText-Regular.ttf",
    "CrimsonText-Italic.ttf",
    "CrimsonText-Bold.ttf",
    "CrimsonText-BoldItalic.ttf",
    "CrimsonText-SemiBold.ttf",
    "OFL.txt",
]
BASE = "https://api.github.com/repos/google/fonts/contents/ofl/crimsontext/"


def main() -> None:
    here = pathlib.Path(__file__).parent / "fonts"
    here.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        req = urllib.request.Request(
            BASE + name, headers={"User-Agent": "autonovel", "Accept": "application/vnd.github+json"}
        )
        payload = json.load(urllib.request.urlopen(req, timeout=60))
        data = base64.b64decode(payload["content"])
        (here / name).write_bytes(data)
        print(f"{name}\t{len(data):,} bytes")


if __name__ == "__main__":
    main()
