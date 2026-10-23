"""Tier-1 tests for `onboard.py` and the
`autonovel onboard` CLI subcommand.

The wizard's interactivity is exercised via injected `prompt_fn` /
`print_fn` seams; the CLI is tested via a non-interactive path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from autonovel import onboard, project as project_mod
from autonovel.housekeeping import scaffold


# ----------------------------------------------------- helpers


def _make_book(tmp_path: Path, *, genre: str = "general"):
    """Returns (series_layout, book_name). Genre defaults to
    `general` (the scaffolder's literal default) so wizard tests
    that want to set genre are exercising the empty-current
    path."""
    res = scaffold.new_series(
        tmp_path / "series", series_name="series", genre=genre,
    )
    scaffold.new_book(res.series, book_name="the-book", pov="POV")
    return res.series, "the-book"


def _scripted_prompts(answers: list[str]):
    """Return a prompt_fn that yields the given answers in order
    and raises if exhausted (so a regression that adds a prompt
    surfaces immediately)."""
    iterator = iter(answers)
    def fn(label: str) -> str:
        try:
            return next(iterator)
        except StopIteration as e:
            raise AssertionError(
                f"wizard asked an unscripted prompt: {label!r}"
            ) from e
    return fn


# ----------------------------------------------------- attribution rendering


def test_render_attribution_seed_by_human() -> None:
    out = onboard.render_attribution("seed-by-human", "Renata Calvi")
    assert "Renata Calvi" in out
    assert "Autonovel" in out


def test_render_attribution_human_only() -> None:
    assert onboard.render_attribution("human-only", "P. M. James") == "P. M. James"


def test_render_attribution_ai_only() -> None:
    assert onboard.render_attribution("ai-only", "anyone") == "Autonovel"


def test_render_attribution_unknown_falls_back_to_default() -> None:
    """Unrecognised style → use seed-by-human (the safest default
    that names both human and AI)."""
    out = onboard.render_attribution("totally-made-up", "Jane Doe")
    assert "Jane Doe" in out
    assert "Autonovel" in out


# ----------------------------------------------------- run_wizard


def test_full_run_with_all_answers(tmp_path: Path) -> None:
    series, book = _make_book(tmp_path)
    answers = [
        "An apothecary's apprentice in 1492 Venice…",  # pitch
        "1480",   # period start
        "1550",   # period end
        "Venice", # period region
        "historical fiction",  # genre
        "mystery, other: apothecary",  # subgenres (historical fiction has them)
        "The Apothecary's Mortar",  # working title
        "Renata Calvi",  # human author
        "1",  # attribution style → seed-by-human
    ]
    printed: list[str] = []
    result = onboard.run_wizard(
        series, book,
        prompt_fn=_scripted_prompts(answers),
        print_fn=lambda s: printed.append(s),
    )
    assert result.answers.pitch.startswith("An apothecary")
    assert result.answers.period_start == "1480"
    assert result.answers.working_title == "The Apothecary's Mortar"
    assert result.answers.attribution_style == "seed-by-human"
    assert result.answers.skipped == []
    # seed.txt was written with the structured shape.
    seed = result.seed_path
    text = seed.read_text(encoding="utf-8")
    assert "## Pitch" in text and "An apothecary" in text
    assert "## Period" in text and "1480" in text
    assert "## Working title" in text
    assert "Renata Calvi" in text
    # project.yaml updated.
    cfg = project_mod.load(series.project_file)
    entry = cfg.book_by_name(book)
    assert entry is not None
    assert entry.title and "Apothecary" in entry.title
    assert entry.title.endswith("(working)")
    assert "Renata Calvi" in (entry.author or "")
    assert "Autonovel" in (entry.author or "")
    assert cfg.period == {"start": "1480", "end": "1550", "region": "Venice"}
    assert cfg.genre == "historical fiction"
    assert entry.subgenres == ["mystery", "other: apothecary"]
    assert "Subgenres: mystery, other: apothecary" in text


def test_run_with_all_skipped(tmp_path: Path) -> None:
    """Every prompt skipped — wizard still completes and seed.txt
    has placeholder text + an Onboarding TODO block."""
    series, book = _make_book(tmp_path)
    answers = [""] * 9  # all empty
    result = onboard.run_wizard(
        series, book,
        prompt_fn=_scripted_prompts(answers),
        print_fn=lambda s: None,
    )
    text = result.seed_path.read_text(encoding="utf-8")
    assert "[Replace this with your one-paragraph pitch" in text
    assert "## Onboarding TODO" in text
    assert "pitch" in result.answers.skipped
    assert "human_author" in result.answers.skipped
    assert "working_title" in result.answers.skipped


def test_skipped_period_doesnt_ask_end_or_region(tmp_path: Path) -> None:
    """Empty period start → wizard SHOULD NOT prompt for end / region.
    The scripted prompt count enforces this."""
    series, book = _make_book(tmp_path)
    # 6 prompts: pitch, period_start, genre, working_title, human, style
    answers = ["pitch", "", "literary", "", "", "1"]
    result = onboard.run_wizard(
        series, book,
        prompt_fn=_scripted_prompts(answers),
        print_fn=lambda s: None,
    )
    assert result.answers.period_start == ""
    assert "period" in result.answers.skipped


def test_attribution_style_default_to_seed_by_human(tmp_path: Path) -> None:
    """Empty style input → default 'seed-by-human'."""
    series, book = _make_book(tmp_path)
    answers = ["pitch", "", "literary", "", "human", ""]  # 6 prompts; style empty
    result = onboard.run_wizard(
        series, book,
        prompt_fn=_scripted_prompts(answers),
        print_fn=lambda s: None,
    )
    assert result.answers.attribution_style == "seed-by-human"


def test_wizard_refuses_when_book_missing(tmp_path: Path) -> None:
    res = scaffold.new_series(tmp_path / "s", series_name="s")
    with pytest.raises(FileNotFoundError):
        onboard.run_wizard(res.series, "nonexistent-book")


# ----------------------------------------------------- writers


def test_write_seed_skipped_period_section_renders_placeholder(
    tmp_path: Path,
) -> None:
    series, book = _make_book(tmp_path)
    book_root = series.books / book
    answers = onboard.WizardAnswers(
        pitch="A pitch.", genre="lit", human_author="x",
        attribution_style="human-only",
    )
    answers.skipped.append("period")
    seed = onboard.write_seed(book_root, answers)
    text = seed.read_text(encoding="utf-8")
    assert "[Contemporary or genre fiction" in text
    assert "## Onboarding TODO" in text


def test_apply_to_project_yaml_does_not_overwrite_existing_title(
    tmp_path: Path,
) -> None:
    """If the user already set a title (e.g. via
    /autonovel:title --set), the wizard must not clobber it."""
    series, book = _make_book(tmp_path)
    cfg = project_mod.load(series.project_file)
    entry = cfg.book_by_name(book)
    assert entry is not None
    entry.title = "Already Set"
    project_mod.dump(cfg, series.project_file)
    answers = onboard.WizardAnswers(
        working_title="Wizard's Suggestion",
        human_author="Renata",
        attribution_style="seed-by-human",
    )
    onboard.apply_to_project_yaml(series.project_file, book, answers)
    cfg = project_mod.load(series.project_file)
    entry = cfg.book_by_name(book)
    assert entry.title == "Already Set"  # not "Wizard's Suggestion (working)"


# ----------------------------------------------------- CLI


def test_cli_onboard_non_interactive_prints_state(tmp_path: Path) -> None:
    """The --non-interactive path doesn't run the wizard; it just
    summarises the current seed/title/author state. Useful for
    testing that the CLI is wired without scripting prompts."""
    series, book = _make_book(tmp_path)
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "onboard",
         book, "--series", str(series.root), "--non-interactive"],
        capture_output=True, text=True, check=True,
    )
    assert "Book:" in out.stdout
    assert book in out.stdout


def test_cli_onboard_unknown_book_returns_2(tmp_path: Path) -> None:
    series, _ = _make_book(tmp_path)
    out = subprocess.run(
        [sys.executable, "-m", "autonovel.cli", "onboard",
         "nope", "--series", str(series.root), "--non-interactive"],
        capture_output=True, text=True,
    )
    assert out.returncode == 2
