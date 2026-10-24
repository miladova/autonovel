"""Command file parser + adapter base class.

The repo ships generic command files under `commands/`. Each adapter
translates a generic CommandDef into the runtime-specific on-disk form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FRONTMATTER = ("name", "description", "model_tier", "allowed-tools")
VALID_MODEL_TIERS = {"heavy", "standard", "light"}
VALID_CONTEXT_MODES = {"none", "book", "series"}
# `summaries:` — what a command that reads chapter summaries needs of
# them. `refresh` (the default when `reads:` names a `.summary.md`):
# `_begin` lists every summary that no longer matches its chapter and the
# preamble brings each up to date before the workflow reads any.
# `report`: the command only displays summaries (a table, a map, a
# status line) and marks the out-of-date ones instead.
VALID_SUMMARY_MODES = {"refresh", "report"}
GENERIC_TOOL_NAMES = {
    "file_read",
    "file_write",
    "task",
    "web_search",
    "web_fetch",
    "bash",
}

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?\n)---\s*\n(?P<body>.*)\Z",
    re.DOTALL,
)


class CommandParseError(ValueError):
    pass


@dataclass
class CommandDef:
    name: str
    description: str
    argument_hint: str | None
    model_tier: str
    allowed_tools: list[str]
    reads: list[str]
    writes: list[str]
    context_mode: str
    body: str
    source_path: Path | None
    raw_frontmatter: dict[str, Any]

    @property
    def stem(self) -> str:
        return self.name.split(":", 1)[1] if ":" in self.name else self.name

    @property
    def reads_summaries(self) -> bool:
        return any(r.endswith(".summary.md") for r in self.reads)

    @property
    def refreshes_summaries(self) -> bool:
        """True when `_begin` must list out-of-date chapter summaries
        and the preamble must refresh them before the workflow reads
        one (see VALID_SUMMARY_MODES)."""
        mode = self.raw_frontmatter.get("summaries")
        if mode is None:
            return self.reads_summaries
        return mode == "refresh"


def parse_command(path: Path) -> CommandDef:
    text = path.read_text(encoding="utf-8")
    return parse_command_text(text, source_path=path)


def parse_command_text(text: str, *, source_path: Path | None = None) -> CommandDef:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise CommandParseError(f"{source_path or '<text>'}: missing YAML frontmatter block")
    fm = yaml.safe_load(m.group("fm")) or {}
    if not isinstance(fm, dict):
        raise CommandParseError(f"{source_path or '<text>'}: frontmatter is not a mapping")
    body = m.group("body")

    problems = validate_frontmatter(fm)
    if problems:
        raise CommandParseError(
            f"{source_path or '<text>'}: " + "; ".join(problems)
        )

    return CommandDef(
        name=fm["name"],
        description=fm["description"],
        argument_hint=fm.get("argument-hint"),
        model_tier=fm["model_tier"],
        allowed_tools=list(fm.get("allowed-tools") or []),
        reads=list(fm.get("reads") or []),
        writes=list(fm.get("writes") or []),
        context_mode=fm.get("context_mode", "book"),
        body=body,
        source_path=source_path,
        raw_frontmatter=fm,
    )


def validate_frontmatter(fm: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for k in REQUIRED_FRONTMATTER:
        if k not in fm:
            problems.append(f"missing frontmatter field: {k}")
    name = fm.get("name")
    if name is not None and not (isinstance(name, str) and name.startswith("autonovel:")):
        problems.append("`name` must be a string starting with `autonovel:`")
    tier = fm.get("model_tier")
    if tier is not None and tier not in VALID_MODEL_TIERS:
        problems.append(
            f"`model_tier` must be one of {sorted(VALID_MODEL_TIERS)}; got {tier!r}"
        )
    ctx = fm.get("context_mode")
    if ctx is not None and ctx not in VALID_CONTEXT_MODES:
        problems.append(
            f"`context_mode` must be one of {sorted(VALID_CONTEXT_MODES)}; got {ctx!r}"
        )
    tools = fm.get("allowed-tools") or []
    if not isinstance(tools, list):
        problems.append("`allowed-tools` must be a list")
    else:
        for t in tools:
            if t not in GENERIC_TOOL_NAMES:
                problems.append(
                    f"unknown generic tool: {t!r} (valid: {sorted(GENERIC_TOOL_NAMES)})"
                )
    for key in ("reads", "writes"):
        if key in fm and not isinstance(fm[key], list):
            problems.append(f"`{key}` must be a list")
    mode = fm.get("summaries")
    if mode is not None and mode not in VALID_SUMMARY_MODES:
        problems.append(
            f"`summaries` must be one of {sorted(VALID_SUMMARY_MODES)}; got {mode!r}"
        )
    return problems


def summary_refresh_step(cmd: "CommandDef", *, shell: str, task: str,
                         book: str = "{book}") -> str:
    """The preamble step that brings out-of-date chapter summaries up
    to date before a command reads them. Empty for commands that don't
    read summaries (or only display them). One text for every adapter;
    each passes its own tool names."""
    if not cmd.refreshes_summaries:
        return ""
    return f"""
**Chapter summaries are checked before this command reads them.** If
`_begin` printed a `summaries to refresh:` line, each chapter it names
has a continuity summary that no longer matches the chapter as it now
stands (or has none). Do not read those summaries. Bring each one up to
date first, with one `{task}` subagent per chapter, up to three at a
time, so the chapters don't fill this conversation. Each subagent reads
`books/{book}/chapters/ch_NN.md` in full; overwrites
`books/{book}/chapters/ch_NN.summary.md` with a 150–250-word continuity
summary in seven labelled sections, `**Location:**`, `**Plot:**`,
`**POV state:**`, `**Cast on stage:**`, `**Threads opened:**`,
`**Threads closed:**` and `**Story time:**` (the format
`/autonovel:summarize-chapter` defines); and then uses `{shell}` to run
`autonovel _stamp-summary --book {book} --chapter N`, which records that
the summary matches the chapter. When every subagent has finished, run
`autonovel mechanical summary-check books/{book}` with `{shell}`, and
continue only when its `needs_refresh` list holds none of the chapters
`_begin` named. Never draft, revise, judge or answer from one of those
summaries before it has been refreshed.
"""


def summary_gate_note(*, shell: str) -> str:
    """The postamble paragraph that tells the model what to do when
    `_end` refuses to close because a chapter this command changed has
    a summary that no longer matches it."""
    return f"""
**The summary gate.** If `_end` exits 3 and prints `SUMMARY GATE`, this
command changed a chapter's text and left its continuity summary
describing the old text. Do what the banner says for each chapter it
lists (rewrite the summary from the chapter as it now stands, then run
`autonovel _stamp-summary`), then run the same `_end` again with the
same flags. The lock stays held until `_end` exits 0. Do not end your
turn while the gate is shut.
"""


def discover_commands(commands_dir: Path) -> list[CommandDef]:
    """Parse every commands/*.md (non-recursive)."""
    return [parse_command(p) for p in sorted(commands_dir.glob("*.md"))]


class RuntimeAdapter:
    """Base class for runtime-specific adapters."""

    name: str = "base"

    def default_install_root(self) -> Path:
        raise NotImplementedError

    def target_path(self, install_root: Path, cmd: CommandDef) -> Path:
        raise NotImplementedError

    def render(self, cmd: CommandDef, *, model_map: dict[str, str] | None = None) -> str:
        raise NotImplementedError

    def install_dir_marker(self, install_root: Path) -> Path:
        """Directory the adapter owns under install_root (for uninstall)."""
        raise NotImplementedError
