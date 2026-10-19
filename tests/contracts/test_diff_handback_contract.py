"""Tier-2: revised chapters go back to the author as a diff.

Bug class (author, 2026-10-18): "it is taking me too long to read the same
text again without the diff view." A revised chapter the author had
already read came back as clean text only. `revise` and `draft` (on a
redraft) now end by running `diff-chapters --from last-read --if-read`
for that chapter, `revision-pass` once for its whole range, and
`/autonovel:diff --annotate` writes a plain what note and a big flag as
well as the why. Locked here so a refactor can't drop them silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autonovel.adapters.base import discover_commands
from autonovel.adapters.installer import _commands_source_dir

COMMANDS = Path(__file__).resolve().parent.parent.parent / "commands"
HANDBACK = "autonovel mechanical diff-chapters --book {book} --from last-read"


def _cmd(name: str):
    (cmd,) = [c for c in discover_commands(_commands_source_dir()) if c.name == f"autonovel:{name}"]
    return cmd


@pytest.mark.parametrize("name,chapters", [
    ("revise", "--chapters {chapter} --if-read"),
    ("draft", "--chapters {chapter} --if-read"),
    ("revision-pass", "--chapters <range> --if-read"),
])
def test_rewriting_commands_hand_the_chapter_back_as_a_diff(name: str, chapters: str) -> None:
    cmd = _cmd(name)
    assert f"{HANDBACK} {chapters}" in cmd.body
    assert "bash" in cmd.allowed_tools
    assert "books/{book}/edit_logs/last_read.json" in cmd.reads
    for path in ("diff_*.html", "diff_*.json", "story_map.html", "story_map.json"):
        assert f"books/{{book}}/edit_logs/{path}" in cmd.writes
    # The author marks a version read after reading it, never the writer.
    line = next(ln for ln in cmd.body.splitlines() if HANDBACK in ln)
    assert "--mark-read" not in line
    flat = " ".join(cmd.body.split())
    assert "Do not pass `--mark-read`" in flat or "Never pass `--mark-read`" in flat
    assert '"skipped"' in flat


def test_revision_pass_subagents_skip_the_per_chapter_handback() -> None:
    body = _cmd("revision-pass").body
    assert "Skip revise's\n      step 12 (the hand-back diff)" in body


def test_redraft_only_when_a_chapter_was_already_there() -> None:
    assert "wrote over a chapter file that was already there" in _cmd("draft").body


def test_annotate_writes_what_why_and_big() -> None:
    body = _cmd("diff").body
    for key in ("**`what`**", "**`why`**", "**`big`**"):
        assert key in body
    assert '{"ch14-002": {"what": "…", "why": "…", "big": true, "fp":' in body
    assert "no jargon" in body and "Introduce each person and term" in body
    assert "An older sidecar holding only `why`\n      strings still loads." in body
    for view in ("**Changes**", "**Whole chapter**", "**Clean\ntext**"):
        assert view in body
