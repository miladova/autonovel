"""Tier-3 smoke: `/autonovel:draft 1 --book tiny-inquisitor` on Claude Code.

Opt-in. Skips when `claude` is not on $PATH. Uses whatever auth `claude`
already has (subscription OAuth or `ANTHROPIC_API_KEY`). Runs the real
runtime against tests/fixtures/tiny-series-historical/. Asserts the
acceptance block from commands/draft.md.

Retried once on failure by the top-level tests/conftest.py flakiness hook
(§12 item 1); only a double-failure is treated as a real signal.
"""

from __future__ import annotations

import re

import pytest

from autonovel.validators.chapter_frontmatter import parse

from .conftest import run_command_in_runtime


@pytest.mark.smoke
@pytest.mark.genre("historical")
def test_draft_chapter_one(tmp_runtime_series) -> None:
    series = tmp_runtime_series("tiny-series-historical")

    result = run_command_in_runtime(
        runtime="claude",
        command="/autonovel:draft 1 --book tiny-inquisitor",
        cwd=series.path,
        allowed_tools=["Read", "Write", "Bash", "Task"],
        # A draft now spawns a cold first reader (and a second when the
        # first finds serious items) and reads the design, cast and genre
        # guide; it no longer fits the 600 s default set in April.
        timeout=1800,
    )
    assert result.returncode == 0, (
        f"claude returned {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    chapter_path = series.path / "books" / "tiny-inquisitor" / "chapters" / "ch_01.md"
    assert chapter_path.exists(), "ch_01.md was not written"

    text = chapter_path.read_text(encoding="utf-8")
    # Frontmatter parses and has the required fields with legal values.
    fm = parse(text)
    assert fm.book == "tiny-inquisitor"
    assert fm.chapter == 1
    assert fm.pov == "Tommaso"
    assert fm.status == "drafted"
    assert fm.story_time.startswith("15")  # 16th century

    # Word count between 1800 (§13 PR 4 "do not go below 1800w") and 5000
    # (headroom above gen_revision's ~+30% overshoot). Tighter ranges are
    # caught by the mechanical evaluator in later PRs, not the smoke test.
    body = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, count=1, flags=re.DOTALL)
    words = len(body.split())
    assert 1800 <= words <= 5000, f"word count {words} outside [1800, 5000]"

    # At least one line appended to pending_canon.md.
    pending = series.path / "books" / "tiny-inquisitor" / "pending_canon.md"
    new_lines = [ln for ln in pending.read_text(encoding="utf-8").splitlines()
                 if ln.strip().startswith("- ")]
    assert new_lines, "no new pending_canon lines appended"

    # No period-banned words appear in the body (case-insensitive word-match).
    bans_path = series.path / "shared" / "period_bans.txt"
    bans = [
        ln.strip().lower() for ln in bans_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    lower = body.lower()
    hit = [b for b in bans if re.search(rf"\b{re.escape(b)}\b", lower)]
    assert not hit, f"period-banned words appeared: {hit}"

    # The lifecycle wrote last-action.json and command-log.jsonl.
    la = series.path / ".autonovel" / "last-action.json"
    log = series.path / ".autonovel" / "command-log.jsonl"
    assert la.exists(), ".autonovel/last-action.json was not written"
    assert log.exists(), ".autonovel/command-log.jsonl was not written"
