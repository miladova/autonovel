"""Filesystem layout helpers.

A series repo looks like:

    <series_root>/
      project.yaml
      .autonovel/
      shared/
      books/<book_name>/

These helpers resolve roots and produce the canonical subpaths. They do not
touch disk beyond existence checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SERIES_MARKER = "project.yaml"
AUTONOVEL_DIR = ".autonovel"


# Match exactly `ch_NN.md` — NOT `ch_NN.summary.md` or any other
# adjunct file alongside the prose. Introduced 2026-04-25 after the
# per-chapter-summary commit caused chapter-counts to double.
CHAPTER_FILENAME_RE = re.compile(r"^ch_\d+\.md$")


def iter_chapter_files(chapters_dir: Path) -> list[Path]:
    """Return every `ch_NN.md` chapter file under `chapters_dir`,
    sorted by name. Excludes `ch_NN.summary.md` and any other adjunct
    files. Caller can iterate or count the result."""
    if not chapters_dir.is_dir():
        return []
    return sorted(
        p for p in chapters_dir.iterdir()
        if p.is_file() and CHAPTER_FILENAME_RE.match(p.name)
    )


@dataclass(frozen=True)
class SeriesLayout:
    root: Path

    @property
    def project_file(self) -> Path:
        return self.root / SERIES_MARKER

    @property
    def shared(self) -> Path:
        return self.root / "shared"

    @property
    def books(self) -> Path:
        return self.root / "books"

    @property
    def autonovel(self) -> Path:
        return self.root / AUTONOVEL_DIR

    @property
    def state_file(self) -> Path:
        return self.autonovel / "state.json"

    @property
    def lock_file(self) -> Path:
        return self.autonovel / "in-progress.lock"

    @property
    def last_action_file(self) -> Path:
        return self.autonovel / "last-action.json"

    @property
    def command_log_file(self) -> Path:
        return self.autonovel / "command-log.jsonl"

    @property
    def checkpoints(self) -> Path:
        return self.autonovel / "checkpoints"

    @property
    def session_notes(self) -> Path:
        return self.autonovel / "session-notes"

    def book(self, name: str) -> "BookLayout":
        return BookLayout(series=self, name=name)


@dataclass(frozen=True)
class BookLayout:
    series: SeriesLayout
    name: str

    @property
    def root(self) -> Path:
        return self.series.books / self.name

    @property
    def seed_file(self) -> Path:
        return self.root / "seed.txt"

    @property
    def voice_file(self) -> Path:
        return self.root / "voice.md"

    @property
    def outline_file(self) -> Path:
        return self.root / "outline.md"

    @property
    def chapters(self) -> Path:
        return self.root / "chapters"

    @property
    def pending_canon(self) -> Path:
        return self.root / "pending_canon.md"

    @property
    def canon_file(self) -> Path:
        """Book-scoped canon: facts this book's prose/outline established
        that bind THIS book only. Series-wide facts stay in
        `shared/canon.md`."""
        return self.root / "canon.md"

    @property
    def state_file(self) -> Path:
        return self.root / "state.json"

    @property
    def results_file(self) -> Path:
        return self.root / "results.tsv"

    @property
    def briefs(self) -> Path:
        return self.root / "briefs"

    @property
    def edit_logs(self) -> Path:
        return self.root / "edit_logs"

    @property
    def eval_logs(self) -> Path:
        return self.root / "eval_logs"

    @property
    def typeset(self) -> Path:
        return self.root / "typeset"


class SeriesNotFound(Exception):
    """Raised when no project.yaml is found walking upward from a path."""


def find_series_root(start: Path | None = None) -> Path:
    """Walk upward from *start* (default: cwd) until project.yaml is found."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / SERIES_MARKER).is_file():
            return candidate
    raise SeriesNotFound(
        f"No {SERIES_MARKER} found walking upward from {cur}. "
        f"Run `autonovel new-series <name>` to create one."
    )


def load_series(start: Path | None = None) -> SeriesLayout:
    return SeriesLayout(root=find_series_root(start))


def looks_doubled(series_root: Path, book_name: str) -> bool:
    """True when a book's name equals its series-root directory name, so the
    (correct) ``<series>/books/<book>/`` layout reads as a doubled path
    (``…/medieval-king-maker/books/medieval-king-maker/``). Structurally fine
    — the series *contains* ``books/<name>/`` — but confusing; surfaced by
    ``autonovel doctor`` and ``new-book`` so it never looks like a bug."""
    return Path(series_root).name == book_name


def nesting_note(series_root: Path, book_name: str) -> str:
    """A one-line explanation of the doubled-looking path for a
    series-name == book-name collision (empty when there is none)."""
    if not looks_doubled(series_root, book_name):
        return ""
    return (
        f"book {book_name!r} has the same name as its series, so its files "
        f"live at {Path(series_root).name}/books/{book_name}/ — that doubled "
        f"path is correct (a series contains books/<name>/), not a bug. Use a "
        f"distinct book short-name if you'd rather avoid the repetition."
    )
