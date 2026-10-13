"""`autonovel doctor` — sanity-check a series directory.

Reports what is wrong without changing anything (unless `fix=True`, which only
does safe mkdirs).
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .. import lock, project as project_mod
from ..paths import SERIES_MARKER, SeriesLayout, nesting_note


# Map of external tool name → (doc string, install hint). Used by
# `check_export_tools` so the user sees *why* a tool matters and how to
# get it. Every entry surfaces as a WARNING (not a PROBLEM) because
# each tool is only needed by a subset of commands — a user who never
# calls `/autonovel:typeset` doesn't need `tectonic` installed.
EXPORT_TOOLS: dict[str, tuple[str, str]] = {
    "tectonic": (
        "PDF typesetting (/autonovel:typeset)",
        "brew install tectonic  OR  apt install tectonic (often too old) "
        "— if apt fails or doctor still flags it, grab the prebuilt static "
        "binary from https://tectonic-typesetting.github.io/book/latest/installation/",
    ),
    "pandoc": (
        "ePub generation (/autonovel:typeset)",
        "apt install pandoc  OR  brew install pandoc",
    ),
    "potrace": (
        "SVG vectorisation (/autonovel:art-vectorize)",
        "apt install potrace  OR  brew install potrace",
    ),
    "ffmpeg": (
        "m4b audiobook output (/autonovel:audiobook-assemble --format m4b)",
        "apt install ffmpeg  OR  brew install ffmpeg",
    ),
    "rsvg-convert": (
        "SVG→PDF conversion for print-quality vector ornaments (/autonovel:typeset --convert-vectors)",
        "apt install librsvg2-bin  OR  brew install librsvg",
    ),
    "fc-match": (
        "Font lookup for EB Garamond / Bebas Neue covers (/autonovel:cover-composite, cover-print)",
        "apt install fontconfig  OR  brew install fontconfig",
    ),
}


@dataclass
class DoctorReport:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


REQUIRED_DIRS = (
    "shared",
    "shared/research",
    "shared/research/seed",
    "shared/research/notes",
    "books",
    ".autonovel",
    ".autonovel/checkpoints",
    ".autonovel/session-notes",
)

REQUIRED_SHARED_FILES = (
    "shared/world.md",
    "shared/characters.md",
    "shared/canon.md",
    "shared/events.md",
    "shared/timeline.md",
    "shared/MYSTERY.md",
    "shared/period_bans.txt",
    "shared/sources.bib",
    "shared/research/sources.yaml",
)


def check_export_tools() -> list[str]:
    """Return one `<tool>: missing — <purpose>; install: <hint>` line per absent tool.

    Empty list means every known export tool is on `$PATH`. Callers
    surface the lines as WARNINGS — they are never fatal; the
    corresponding command will complain at invocation time if the
    user ever runs it.
    """
    out: list[str] = []
    for tool, (purpose, install_hint) in EXPORT_TOOLS.items():
        if shutil.which(tool) is None:
            out.append(f"{tool}: missing — needed for {purpose}; install: {install_hint}")
    return out


# Fonts the typeset template references via `\setmainfont` /
# `\setsansfont`. When fontconfig can't find these, fontspec walks
# its name-fallback chain and produces noisy "stepping through fonts
# by name" build output before failing — author hit this 2026-04-30.
# We pre-flight check so the user sees a clean "install <font>"
# warning before typeset rather than diagnosing tectonic output.
TYPESET_FONTS: dict[str, tuple[str, str]] = {
    "EB Garamond": (
        "primary serif for chapter prose (`/autonovel:typeset`)",
        "Linux/WSL: sudo apt-get install -y fonts-ebgaramond && fc-cache -fv  "
        "OR macOS: brew install --cask font-eb-garamond  "
        "OR: autonovel install-export-tools --apply",
    ),
}


def check_typeset_fonts() -> list[str]:
    """Use `fc-match` to confirm each TYPESET_FONTS entry resolves
    to an installed font. fc-match always returns *something* (a
    fallback) when the requested name is missing, so we compare
    the requested name against the resolved family name to detect
    fallbacks. When fc-match itself isn't on PATH (no fontconfig
    installed) we emit a single warning rather than per-font noise.
    """
    if shutil.which("fc-match") is None:
        return [
            "fontconfig not installed (no `fc-match` on PATH); typeset font "
            "lookup may fail. Install: see `fc-match` entry above."
        ]
    out: list[str] = []
    import subprocess
    for font_name, (purpose, install_hint) in TYPESET_FONTS.items():
        try:
            r = subprocess.run(
                ["fc-match", "-f", "%{family[0]}", font_name],
                capture_output=True, text=True, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        resolved = (r.stdout or "").strip()
        # When the requested font isn't installed, fc-match returns
        # the system default (usually "DejaVu Serif" or "Liberation
        # Serif" on Linux, "Times New Roman" on macOS). The
        # fallback's family name doesn't include any token from the
        # requested name → flag.
        requested_tokens = {t.lower() for t in font_name.split() if len(t) >= 3}
        resolved_tokens = {t.lower() for t in resolved.split() if len(t) >= 3}
        if not (requested_tokens & resolved_tokens):
            out.append(
                f"font {font_name!r}: missing — needed for {purpose}; "
                f"fc-match resolves to {resolved!r} (fallback). "
                f"Install: {install_hint}"
            )
    return out


_ONE_M_RE = re.compile(r"\[1[mM]\]")


def check_claude_settings(*, home: Path | None = None,
                          project_root: Path | None = None) -> list[str]:
    """Return WARNINGS for known Claude Code session-config gotchas.

    Today: `[1m]`-suffixed model names that fire the "extra usage
    required for 1M context" billing gate even on Claude Max plans.
    The check reads:
      - `~/.claude/settings.json` (user-global), and
      - `<project>/.claude/settings.json` (series-local) when
        `project_root` is supplied.

    Either / both / neither may exist. Missing files are skipped
    silently (the user is allowed to not have customized Claude Code).
    """
    home = home or Path.home()
    candidates: list[Path] = [home / ".claude" / "settings.json"]
    if project_root is not None:
        candidates.append(project_root / ".claude" / "settings.json")

    out: list[str] = []
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue  # malformed settings is its own problem; not our scope
        for hit in _scan_for_one_m(data):
            out.append(
                f"{path}: model `{hit}` uses 1M-context [1m] variant — "
                "this fires Anthropic's extra-usage billing gate even on "
                "Claude Max plans. Either run `/extra-usage` inside Claude "
                "Code to enable 1M billing, or pick a non-`[1m]` model with "
                "`/model`."
            )
    return out


def _scan_for_one_m(value: object, _path: str = "") -> list[str]:
    """Recursively walk a JSON-loaded settings tree looking for any
    string value matching `[1m]`. Returns the matching strings."""
    out: list[str] = []
    if isinstance(value, str):
        if _ONE_M_RE.search(value):
            out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            out.extend(_scan_for_one_m(v, _path=f"{_path}.{k}"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            out.extend(_scan_for_one_m(item, _path=f"{_path}[{i}]"))
    return out


def missing_export_tools() -> list[str]:
    """Names of export-side tools (tectonic, pandoc, ffmpeg, etc.)
    that are not on PATH. Used by `autonovel doctor --install-missing`
    to feed `install_export_tools.apply()` only the tools that
    actually need work — re-running install for already-present
    tools is wasted effort.

    Pure: just re-runs the same `shutil.which` walk that
    `check_export_tools` does, but returns the bare names rather
    than rendered warning lines.
    """
    return [name for name in EXPORT_TOOLS if shutil.which(name) is None]


def run(series_root: Path, *, fix: bool = False, export_tools: bool = True) -> DoctorReport:
    report = DoctorReport()
    if not (series_root / SERIES_MARKER).is_file():
        report.problems.append(f"missing {SERIES_MARKER} in {series_root}")
        return report

    try:
        cfg = project_mod.load(series_root / SERIES_MARKER)
    except Exception as e:  # noqa: BLE001 — doctor must not crash on malformed yaml
        report.problems.append(f"project.yaml did not parse: {e}")
        return report

    problems = project_mod.validate(cfg)
    report.problems.extend(problems)

    series = SeriesLayout(root=series_root)

    for rel in REQUIRED_DIRS:
        p = series_root / rel
        if not p.exists():
            if fix:
                p.mkdir(parents=True, exist_ok=True)
                report.fixed.append(f"created {rel}/")
            else:
                report.problems.append(f"missing directory: {rel}/")

    for rel in REQUIRED_SHARED_FILES:
        if not (series_root / rel).is_file():
            report.warnings.append(f"missing shared file: {rel}")

    for b in cfg.books:
        book = series.book(b.name)
        if not book.root.is_dir():
            report.problems.append(f"book {b.name!r} listed in project.yaml but books/{b.name}/ is missing")
            continue
        for rel in ("seed.txt", "voice.md", "outline.md", "state.json"):
            if not (book.root / rel).is_file():
                report.warnings.append(f"books/{b.name}/{rel} missing")
        if not book.canon_file.is_file():
            report.warnings.append(
                f"books/{b.name}/canon.md missing — book-scoped canon (2026-10). "
                f"Run `autonovel canon-partition` to move this book's chapter-derived "
                f"facts out of shared/canon.md; promote-canon creates it on first use.")
        if not book.chapters.is_dir():
            if fix:
                book.chapters.mkdir(parents=True, exist_ok=True)
                report.fixed.append(f"created books/{b.name}/chapters/")
            else:
                report.problems.append(f"books/{b.name}/chapters/ missing")

    # Directory-nesting sanity (Phase 10). A real `books/books/` level is a
    # bug (a command wrote a second nesting); a book whose name == the
    # series-root name is *valid* but reads as a doubled path — warn so it
    # isn't mistaken for the bug.
    if (series.books / "books").is_dir():
        report.problems.append(
            "books/books/ exists — a doubled nesting level (a command wrote "
            "books/ twice). The layout is <series>/books/<book>/, not "
            "<series>/books/books/<book>/; move the inner book up one level.")
    for b in cfg.books:
        note = nesting_note(series_root, b.name)
        if note:
            report.warnings.append(f"nesting: {note}")

    info = lock.read(series.lock_file)
    if info is not None and lock.is_stale(series.lock_file):
        report.warnings.append(
            f"stale lock from PID {info.pid} ({info.command}); `autonovel resume` to recover"
        )

    if export_tools:
        for line in check_export_tools():
            report.warnings.append(f"export tool {line}")
        for line in check_typeset_fonts():
            report.warnings.append(f"typeset {line}")

    for line in check_claude_settings(project_root=series_root):
        report.warnings.append(f"claude settings: {line}")

    return report


def render(report: DoctorReport) -> str:
    out: list[str] = []
    if report.ok and not report.warnings:
        out.append("ok: no problems found")
    for p in report.problems:
        out.append(f"PROBLEM: {p}")
    for w in report.warnings:
        out.append(f"WARNING: {w}")
    for f in report.fixed:
        out.append(f"FIXED: {f}")
    return "\n".join(out)
