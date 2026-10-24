"""Gemini CLI adapter — translates generic commands to TOML command files.

Gemini CLI discovers user commands under `~/.gemini/commands/`, organised
in subfolders by namespace. Each command is a `.toml` file with a
`description` field and a `prompt` field; the file's path under
`commands/` becomes the slash-command name. So:

    ~/.gemini/commands/autonovel/draft.toml  →  /autonovel:draft

Tool names in Gemini differ from Claude and Codex (see §11 of
REWRITE-PLAN.md): file reads use `read_file`, web search is
`google_web_search`, sub-agent fan-out is `run_agent`. The body of the
generic command refers to tools as `file_read`, `web_search`, `task`,
etc.; this adapter rewrites those references to Gemini's vocabulary so
the model isn't asked to invoke a tool that does not exist.

Gemini CLI does not currently allow per-command model pinning, so the
intended tier is recorded as a comment-style metadata block at the top
of the prompt. Users select the model with `gemini -m <name>` or
`~/.gemini/settings.json`.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import CommandDef, RuntimeAdapter, summary_gate_note, summary_refresh_step


GEMINI_TOOL_MAP = {
    "file_read": "read_file",
    "file_write": "write_file",
    "task": "run_agent",
    "web_search": "google_web_search",
    "web_fetch": "web_fetch",
    "bash": "run_shell_command",
}

# Documentation only — Gemini CLI doesn't honour per-command model
# selection yet, but recording the design tier helps a user pick
# `gemini -m` for cost vs. quality.
DEFAULT_MODEL_MAP = {
    "heavy": "gemini-2.5-pro",
    "standard": "gemini-2.5-flash",
    "light": "gemini-2.5-flash-lite",
}


class GeminiAdapter(RuntimeAdapter):
    name = "gemini"

    def default_install_root(self) -> Path:
        return Path.home() / ".gemini" / "commands"

    def install_dir_marker(self, install_root: Path) -> Path:
        return install_root / "autonovel"

    def target_path(self, install_root: Path, cmd: CommandDef) -> Path:
        return install_root / "autonovel" / f"{cmd.stem}.toml"

    def render(
        self,
        cmd: CommandDef,
        *,
        model_map: dict[str, str] | None = None,
    ) -> str:
        model = (model_map or DEFAULT_MODEL_MAP)[cmd.model_tier]
        body = _translate_tool_names(cmd.body)

        prompt_lines: list[str] = []
        prompt_lines.append(_metadata_block(cmd, model))
        prompt_lines.append("")
        prompt_lines.append(_preamble(cmd))
        prompt_lines.append("")
        prompt_lines.append(body.strip("\n"))
        prompt_lines.append("")
        prompt_lines.append(_postamble(cmd))
        prompt = "\n".join(prompt_lines)

        if "'''" in prompt:
            # TOML literal multi-line strings (`'''…'''`) are the only way
            # to ship arbitrary backslash content without escaping. If a
            # command body ever contains a literal triple-quote we'd need
            # to fall back to a basic string with full escape — easier to
            # require commands not contain `'''`.
            raise ValueError(
                f"command {cmd.name!r}: body contains `'''` which conflicts "
                "with the Gemini TOML literal-string delimiter; rewrite the "
                "body or extend the adapter."
            )

        out: list[str] = []
        out.append(f"description = {_toml_string(cmd.description)}")
        if cmd.argument_hint:
            out.append(f"arg_hint = {_toml_string(cmd.argument_hint)}")
        out.append(f"prompt = '''\n{prompt}\n'''")
        out.append("")
        return "\n".join(out)


def _translate_tool_names(body: str) -> str:
    """Rewrite backticked generic tool names in the body to Gemini's verbs.

    Restrict to backtick-wrapped tokens so prose words that happen to
    collide ("a creative task", "bash your seed.txt") are left alone.
    """
    out = body
    for src, dst in GEMINI_TOOL_MAP.items():
        out = re.sub(rf"`{re.escape(src)}`", f"`{dst}`", out)
    return out


def _toml_string(value: str) -> str:
    """Encode a single-line value as a TOML basic string.

    Escapes `\\` and `"` per TOML 1.0 §String. Multi-line content goes in
    a triple-quoted block above; this helper is only for the
    `description` and `arg_hint` fields, which are short and single-line.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _metadata_block(cmd: CommandDef, model: str) -> str:
    return (
        f"<!-- autonovel:{cmd.name}\n"
        f"     model_tier: {cmd.model_tier}\n"
        f"     suggested_model: {model}\n"
        f"     argument_hint: {cmd.argument_hint or '(none)'} -->"
    )


def _preamble(cmd: CommandDef) -> str:
    summary_step = summary_refresh_step(cmd, shell="run_shell_command", task="run_agent")
    writes_bullet = "\n".join(f"  - {p}" for p in cmd.writes) or "  (none)"
    return f"""<autonovel-preamble>
Before following the <workflow> below, run the autonovel preamble. This is
mechanical; it handles the lock and checkpoints described in the
autonovel rewrite plan (§21.2) so that every command is interruptible and
every destructive change is reversible.

1. Use the `run_shell_command` tool to run:
   `autonovel _begin --command {cmd.name} --runtime gemini --args "{{{{args}}}}"`
   The helper resolves the args against this command's `writes:` paths
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
    summary_gate = summary_gate_note(shell="run_shell_command")
    return f"""<autonovel-postamble>
After the <workflow> succeeds, run the autonovel postamble:

1. Use the `run_shell_command` tool to run:
   `autonovel _end --command {cmd.name} --args "{{{{args}}}}" --status ok`
   passing `--wrote <path>` once for each file that was actually written.
   This releases the lock, writes `.autonovel/last-action.json` with the
   standard next step, and appends a JSON line to
   `.autonovel/command-log.jsonl`.

2. Print the user-facing footer exactly as emitted by `_end` (it includes
   the next standard step and a few sidequest alternatives). That footer is
   the primary UX for "what do I do next"; always show it.
{summary_gate}
If the <workflow> fails partway through:
- Run `autonovel _end --command {cmd.name} --args "{{{{args}}}}" --status error`
  (no `--wrote` paths). That leaves the lock marked `interrupted` so
  `/autonovel:resume` can offer recovery, and records the error in the
  command log without overwriting `last-action.json`.
</autonovel-postamble>"""
