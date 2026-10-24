"""Tier-2: a rename reaches every file the next rewrite reads.

Bug class (author, 2026-10-24): renaming an invented character would have
left the old name in `cast.md`, `design.md` and the staged turns in
`briefs/conversation.md`. `/autonovel:revise` reads all three, so the
next revision pass would have put the old name back into the chapters.
And the overlap rule refused outright when a longer, unrelated word
contained the name (`Negroponte` beside `Negro`), although the
word-boundary replace never touches it. Locked here so a refactor can't
narrow the targets again.
"""

from __future__ import annotations

from autonovel.adapters.base import discover_commands
from autonovel.adapters.installer import _commands_source_dir


def _cmd():
    (cmd,) = [c for c in discover_commands(_commands_source_dir())
              if c.name == "autonovel:rename-character"]
    return cmd


def test_rename_writes_every_file_revise_reads() -> None:
    cmd = _cmd()
    for path in ("books/{book}/cast.md", "books/{book}/design.md",
                 "books/{book}/briefs/*.md", "books/{book}/chapters/*.md",
                 "books/{book}/outline.md", "shared/world.md"):
        assert path in cmd.writes, path


def test_research_notes_and_edit_logs_are_left_and_listed() -> None:
    flat = " ".join(_cmd().body.split())
    assert "Leave the research notes (`shared/research/`) and the edit logs" in flat
    assert "still names `<old-name>` as a whole word" in flat


def test_a_different_longer_word_does_not_block_the_rename() -> None:
    flat = " ".join(_cmd().body.split())
    assert "A different word" in flat and "is left as it is" in flat
    assert "which the word-boundary replace would miss" in flat


def test_book_flag_limits_canon_and_briefs_keep_their_time() -> None:
    flat = " ".join(_cmd().body.split())
    assert "when `--book` is passed, only that book's" in flat
    assert "keep its modification time" in flat
