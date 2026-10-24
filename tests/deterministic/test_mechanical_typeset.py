"""Tier-1 tests for `autonovel mechanical render-novel-tex` and
`typeset-filename`.

Locks two helpers introduced 2026-04-25 to replace fragile bash in
the typeset workflow:

  - render_novel_tex() replaces sed-based @KEY@ substitution. sed
    silently breaks on titles containing `/` or `&`; the Python
    helper does pure string replacement.
  - output_filename() / latest_filename() produce canonical
    `<slug>_<YYYYMMDD>_<HHMM>.<ext>` filenames so writers can keep
    every build for side-by-side comparison.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from autonovel.mechanical.typeset import (
    latest_filename,
    output_filename,
    render_novel_tex,
)


# -------------------------------------------------- render_novel_tex


def test_basic_substitution() -> None:
    template = "title: @TITLE@\nauthor: @AUTHOR@\n"
    out = render_novel_tex(template, {"TITLE": "The Bell", "AUTHOR": "P. M."})
    assert out == "title: The Bell\nauthor: P. M.\n"


def test_title_with_slash_does_not_break() -> None:
    """The bug that motivated this helper: sed's `s/@TITLE@/.../`
    breaks when the value contains `/` (e.g. a date "1521/12/04" or
    a publisher slug "abc/def"). String replacement handles it."""
    template = "title: @TITLE@\n"
    out = render_novel_tex(template, {"TITLE": "1521/12/04: A Reckoning"})
    assert out == "title: 1521/12/04: A Reckoning\n"


def test_title_with_ampersand_does_not_break() -> None:
    """sed's replacement string treats `&` as "the matched text",
    silently producing wrong output. Pure replace doesn't."""
    template = "title: @TITLE@\n"
    out = render_novel_tex(template, {"TITLE": "Crown & Coin"})
    assert out == "title: Crown & Coin\n"


def test_title_with_backslash_does_not_break() -> None:
    """sed's replacement string treats `\\` as escape; pure replace
    doesn't. (Real titles rarely have backslashes, but a LaTeX
    escape sequence pre-pasted by mistake would otherwise produce
    a malformed .tex.)"""
    template = "title: @TITLE@\n"
    out = render_novel_tex(template, {"TITLE": r"X\Y\Z"})
    assert out == r"title: X\Y\Z" + "\n"


def test_unknown_placeholder_is_left_as_is() -> None:
    """A new placeholder added to the template that the caller
    doesn't know about should NOT be silently dropped. Leave it so
    the broken render is visible in the .tex itself."""
    template = "title: @TITLE@\nfuture: @FUTURE_FIELD@\n"
    out = render_novel_tex(template, {"TITLE": "X"})
    assert "@FUTURE_FIELD@" in out


def test_substitution_repeats_all_occurrences() -> None:
    template = "@TITLE@ — @TITLE@"
    out = render_novel_tex(template, {"TITLE": "X"})
    assert out == "X — X"


def test_empty_substitution_value_works() -> None:
    template = "subtitle: @SUBTITLE@\n"
    out = render_novel_tex(template, {"SUBTITLE": ""})
    assert out == "subtitle: \n"


# -------------------------------------------------- output_filename


def test_output_filename_shape() -> None:
    when = datetime(2026, 4, 25, 15, 40)
    name = output_filename("the-inquisitor", "pdf", when=when)
    assert name == "the-inquisitor_20260425_1540.pdf"


def test_output_filename_normalises_slug() -> None:
    """Spaces and other non-alphanumerics collapse to `-`; underscores
    survive (book names can be `the_inquisitor`)."""
    when = datetime(2026, 4, 25, 15, 40)
    assert output_filename("The Inquisitor", "pdf", when=when) == "the-inquisitor_20260425_1540.pdf"
    assert output_filename("the_inquisitor", "pdf", when=when) == "the_inquisitor_20260425_1540.pdf"
    assert output_filename("foo!!bar", "pdf", when=when) == "foo-bar_20260425_1540.pdf"


def test_output_filename_strips_leading_trailing_dashes() -> None:
    when = datetime(2026, 4, 25, 15, 40)
    assert output_filename("!the-bell!", "pdf", when=when) == "the-bell_20260425_1540.pdf"


def test_output_filename_kind_extension() -> None:
    when = datetime(2026, 4, 25, 15, 40)
    assert output_filename("x", "pdf", when=when).endswith(".pdf")
    assert output_filename("x", "epub", when=when).endswith(".epub")


def test_output_filename_uses_now_when_no_when_given() -> None:
    """Without an explicit `when`, falls back to datetime.now(). We
    don't pin the value (it's the current minute), but assert shape."""
    name = output_filename("x", "pdf")
    # Format: x_YYYYMMDD_HHMM.pdf — minute granularity → 13 chars after `_`.
    parts = name[:-4].split("_")  # strip .pdf
    assert parts[0] == "x"
    assert len(parts[1]) == 8 and parts[1].isdigit()  # YYYYMMDD
    assert len(parts[2]) == 4 and parts[2].isdigit()  # HHMM


def test_latest_filename_shape() -> None:
    assert latest_filename("the-inquisitor", "pdf") == "the-inquisitor_latest.pdf"
    assert latest_filename("The Inquisitor", "epub") == "the-inquisitor_latest.epub"


# -------------------------------------------------- CLI round-trip


def test_render_cli_writes_substituted_file(tmp_path: Path) -> None:
    template = tmp_path / "novel.tex.tpl"
    template.write_text("title: @TITLE@\nauthor: @AUTHOR@\n", encoding="utf-8")
    out = tmp_path / "novel.tex"
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "render-novel-tex",
         str(template), "--output", str(out),
         "-s", "TITLE=Crown & Coin",
         "-s", "AUTHOR=P. M."],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["substitutions_applied"] == ["AUTHOR", "TITLE"]
    body = out.read_text(encoding="utf-8")
    assert body == "title: Crown & Coin\nauthor: P. M.\n"


def test_render_cli_rejects_malformed_substitution(tmp_path: Path) -> None:
    template = tmp_path / "x.tpl"
    template.write_text("@X@", encoding="utf-8")
    out = tmp_path / "x.tex"
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "render-novel-tex",
         str(template), "--output", str(out), "-s", "no-equals-here"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "KEY=VALUE" in proc.stderr


def test_filename_cli_emits_both_names() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "typeset-filename",
         "the-inquisitor", "pdf"],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["latest"] == "the-inquisitor_latest.pdf"
    # Timestamped name has the canonical shape; we don't pin the
    # specific timestamp.
    assert payload["timestamped"].startswith("the-inquisitor_")
    assert payload["timestamped"].endswith(".pdf")


def test_template_never_drops_letters_in_bold_or_the_timeline_markers() -> None:
    """kingmaker2, 2026-10-24: Debian's EB Garamond 12 Bold has no umlauts
    or curly apostrophe, so bold names lost letters, and the font has no
    ◆ ◇ ○ for the appendix timeline. The template emboldens the Regular when
    no SemiBold is installed and maps the markers to maths symbols."""
    from pathlib import Path
    tex = (Path(__file__).resolve().parents[2] / "src" / "autonovel" / "templates"
           / "series" / "typeset" / "novel.tex").read_text(encoding="utf-8")
    assert "\\IfFontExistsTF{EB Garamond SemiBold}" in tex
    assert "BoldFeatures={FakeBold=1.5}" in tex
    for ch in ("◆", "◇", "○"):
        assert f"\\newunicodechar{{{ch}}}" in tex
    # Lines loosen rather than run into the margin (786 overfull lines
    # in the kingmaker2 build before, one after).
    assert "\\setlength{\\emergencystretch}{2em}" in tex
