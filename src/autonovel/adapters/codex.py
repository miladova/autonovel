"""Codex CLI adapter — translates generic commands into Codex skills.

Codex (>= 0.125) discovers skills from `~/.codex/skills/<name>/SKILL.md`.
Each skill is a directory with a YAML-front-matter markdown file; Codex
loads the frontmatter for routing and the body when the skill is
invoked. There is no slash-command syntax — the user invokes a skill
conversationally ("run autonovel-draft for chapter 1") or by name.

We install the autonovel skills under one parent directory so uninstall
can remove the whole tree cleanly:

    ~/.codex/skills/autonovel/<stem>/SKILL.md

Codex's tool set is fixed (it has shell, file read/write, web search,
and sub-agent fan-out via its own scheduler), so the adapter's job for
the body is to translate the generic tool names that command authors
write (`file_read`, `web_search`, `bash`, …) into Codex's actual
tool/verb names so the model doesn't try to invoke a Claude-shaped tool
that does not exist. The map below is the source of truth.

Codex skills cannot pin a model per-skill; the user picks one with
`codex --model` or in `~/.codex/config.toml`. We surface the intended
tier as a `metadata.model_tier` field so a future Codex version can
honour it, and we record the resolved model name in the same metadata
block as documentation.
"""

from __future__ import annotations

from pathlib import Path

from .base import CommandDef, RuntimeAdapter, summary_gate_note, summary_refresh_step


# Codex's built-in tool surface as of CLI 0.125. The keys are autonovel's
# generic tool names; the values are how Codex refers to the same
# capability in skill prose. Codex's own docs use these verbs in their
# example skills, so a skill body that mentions `shell` or `file_read`
# routes to the right Codex tool unambiguously.
CODEX_TOOL_MAP = {
    "file_read": "file_read",
    "file_write": "file_write",
    "task": "spawn",
    "web_search": "web_search",
    "web_fetch": "web_fetch",
    "bash": "shell",
}

# Codex picks the model globally; per-skill pinning is not yet supported.
# This map is informational only — it appears in the SKILL.md metadata
# block so a user reading the file can see which tier a command was
# designed for and pick `codex --model` accordingly.
DEFAULT_MODEL_MAP = {
    "heavy": "gpt-5.4-thinking",
    "standard": "gpt-5.4",
    "light": "gpt-5.4-mini",
}

# Codex's shell tool is implicit — the preamble/postamble use it to call
# `autonovel _begin` / `_end`, but there is no `allowed-tools` field in
# Codex skill frontmatter to declare it. Kept as documentation only.
IMPLICIT_TOOLS = ("file_read", "file_write", "shell")


class CodexAdapter(RuntimeAdapter):
    name = "codex"

    def default_install_root(self) -> Path:
        return Path.home() / ".codex" / "skills"

    def install_dir_marker(self, install_root: Path) -> Path:
        return install_root / "autonovel"

    def target_path(self, install_root: Path, cmd: CommandDef) -> Path:
        return install_root / "autonovel" / cmd.stem / "SKILL.md"

    def render(
        self,
        cmd: CommandDef,
        *,
        model_map: dict[str, str] | None = None,
    ) -> str:
        # Skill name must be unique across the user's Codex install. Prefix
        # with `autonovel-` so a future skill the user installs from
        # elsewhere with the same stem (e.g. `draft`) doesn't collide.
        skill_name = f"autonovel-{cmd.stem}"
        model = (model_map or DEFAULT_MODEL_MAP)[cmd.model_tier]

        body = _translate_tool_names(cmd.body)

        lines: list[str] = ["---"]
        lines.append(f"name: {skill_name}")
        lines.append(f"description: {cmd.description}")
        lines.append("metadata:")
        lines.append(f"  short-description: {cmd.description}")
        lines.append(f"  model_tier: {cmd.model_tier}")
        lines.append(f"  suggested_model: {model}")
        if cmd.argument_hint:
            lines.append(f"  argument-hint: {cmd.argument_hint}")
        lines.append("---")
        lines.append("")
        lines.append(_preamble(cmd))
        lines.append("")
        lines.append(body.strip("\n"))
        lines.append("")
        lines.append(_postamble(cmd))
        lines.append("")
        return "\n".join(lines)


def _translate_tool_names(body: str) -> str:
    """Rewrite backticked tool references in the body to Codex's vocabulary.

    Only `` `task` `` and `` `bash` `` need rewriting; the rest already
    match Codex's verbs. Restrict to backtick-wrapped tokens so prose
    like "creative task" or "bash your seed.txt" is left alone.
    """
    import re

    rewrites = {
        "task": "spawn",
        "bash": "shell",
    }
    out = body
    for src, dst in rewrites.items():
        out = re.sub(rf"`{re.escape(src)}`", f"`{dst}`", out)
    return out


def _preamble(cmd: CommandDef) -> str:
    summary_step = summary_refresh_step(cmd, shell="shell", task="spawn")
    writes_bullet = "\n".join(f"  - {p}" for p in cmd.writes) or "  (none)"
    return f"""<autonovel-preamble>
Before following the <workflow> below, run the autonovel preamble. This is
mechanical; it handles the lock and checkpoints described in the
autonovel rewrite plan (§21.2) so that every command is interruptible and
every destructive change is reversible.

1. Run the shell command:
   `autonovel _begin --command {cmd.name} --runtime codex --args "$ARGUMENTS"`
   The helper resolves `$ARGUMENTS` against this command's `writes:` paths
   (listed below), acquires `.autonovel/in-progress.lock`, and snapshots
   the current state of every write target into
   `.autonovel/checkpoints/<UTC-timestamp>/`. If it exits non-zero —
   another command is in flight or the series is malformed — stop and
   surface the message verbatim.

2. Only proceed to the <workflow> below once `_begin` has succeeded.
{summary_step}
Writes this command will perform (for context):
{writes_bullet}
</autonovel-preamble>"""


def _postamble(cmd: CommandDef) -> str:
    summary_gate = summary_gate_note(shell="shell")
    return f"""<autonovel-postamble>
After the <workflow> succeeds, run the autonovel postamble:

1. Run the shell command:
   `autonovel _end --command {cmd.name} --args "$ARGUMENTS" --status ok`
   passing `--wrote <path>` once for each file that was actually written.
   This releases the lock, writes `.autonovel/last-action.json` with the
   standard next step, and appends a JSON line to
   `.autonovel/command-log.jsonl`.

2. Print the user-facing footer exactly as emitted by `_end` (it includes
   the next standard step and a few sidequest alternatives). That footer is
   the primary UX for "what do I do next"; always show it.
{summary_gate}
If the <workflow> fails partway through:
- Run `autonovel _end --command {cmd.name} --args "$ARGUMENTS" --status error`
  (no `--wrote` paths). That leaves the lock marked `interrupted` so
  `/autonovel:resume` can offer recovery, and records the error in the
  command log without overwriting `last-action.json`.
</autonovel-postamble>"""
