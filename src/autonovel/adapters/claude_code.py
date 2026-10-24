"""Claude Code adapter — translates generic commands to `.claude/commands/...`."""

from __future__ import annotations

from pathlib import Path

from .base import CommandDef, RuntimeAdapter, summary_gate_note, summary_refresh_step


CLAUDE_TOOL_MAP = {
    "file_read": "Read",
    "file_write": "Write",
    "task": "Task",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
    "bash": "Bash",
}

DEFAULT_MODEL_MAP = {
    "heavy": "claude-opus-4-7",
    "standard": "claude-sonnet-4-6",
    "light": "claude-haiku-4-5-20251001",
}

# Bash is used by the injected preamble/postamble itself, so every command
# ends up needing it at runtime even if its generic frontmatter didn't list it.
IMPLICIT_TOOLS = ("Read", "Write", "Bash")


class ClaudeCodeAdapter(RuntimeAdapter):
    name = "claude"

    def default_install_root(self) -> Path:
        return Path.home() / ".claude" / "commands"

    def install_dir_marker(self, install_root: Path) -> Path:
        return install_root / "autonovel"

    def target_path(self, install_root: Path, cmd: CommandDef) -> Path:
        return install_root / "autonovel" / f"{cmd.stem}.md"

    def render(
        self,
        cmd: CommandDef,
        *,
        model_map: dict[str, str] | None = None,
        pin_model: bool = False,
    ) -> str:
        tools = [CLAUDE_TOOL_MAP[t] for t in cmd.allowed_tools]
        for implicit in IMPLICIT_TOOLS:
            if implicit not in tools:
                tools.append(implicit)
        # The preamble's summary step fans the refresh out to subagents.
        if cmd.refreshes_summaries and "Task" not in tools:
            tools.append("Task")

        model = (model_map or DEFAULT_MODEL_MAP)[cmd.model_tier]

        lines: list[str] = ["---"]
        lines.append(f"description: {cmd.description}")
        if cmd.argument_hint:
            lines.append(f"argument-hint: {cmd.argument_hint}")
        lines.append(f"allowed-tools: {', '.join(tools)}")
        # Default (`pin_model=False`): omit the `model:` field entirely
        # so Claude Code's session model always wins. This is the
        # default because a per-command pin silently downshifts users
        # on a session-level `[1m]` model to the non-`[1m]` variant of
        # the same tier (the 1M-context billing gate). Opt back in to
        # per-tier pinning with `autonovel install --pin-model`. See
        # docs/troubleshooting.md "1M context billing gate" +
        # docs/lessons-from-author-testing.md §8.
        if pin_model:
            lines.append(f"model: {model}")
        lines.append("---")
        lines.append("")
        lines.append(_preamble(cmd))
        lines.append("")
        lines.append(cmd.body.strip("\n"))
        lines.append("")
        lines.append(_postamble(cmd))
        lines.append("")
        return "\n".join(lines)


def _preamble(cmd: CommandDef) -> str:
    summary_step = summary_refresh_step(cmd, shell="Bash", task="Task")
    writes_bullet = "\n".join(f"  - {p}" for p in cmd.writes) or "  (none)"
    return f"""<autonovel-preamble>
Before following the <workflow> below, run the autonovel preamble. This is
mechanical; it handles the lock and checkpoints described in the
autonovel rewrite plan (§21.2) so that every command is interruptible and
every destructive change is reversible.

1. Use the `Bash` tool to run:
   `autonovel _begin --command {cmd.name} --args "$ARGUMENTS"`
   The helper resolves `$ARGUMENTS` against this command's `writes:` paths
   (listed below), acquires `.autonovel/in-progress.lock`, and snapshots
   the current state of every write target into
   `.autonovel/checkpoints/<UTC-timestamp>/`. If it exits non-zero —
   another command is in flight or the series is malformed — stop and
   surface the message verbatim.

2. **Read `_begin`'s stdout for the active book.** If the user did not
   pass `--book <name>` in `$ARGUMENTS`, autonovel will infer the book
   from `.autonovel/last-action.json` (the most recent book worked on)
   or — when there's only one book in the series — from `project.yaml`.
   `_begin` prints a `book: <name>` line in that case. Use that name
   for every `{{book}}` placeholder in the workflow below as if the user
   had typed `--book <name>` themselves. If `_begin` did not print a
   `book:` line and `$ARGUMENTS` lacks `--book`, surface this to the
   user verbatim and stop:

   > Multiple books exist in this series and no `--book` was
   > specified. Re-run with `--book <name>` (one of the names in
   > `project.yaml`).

3. Only proceed to the <workflow> below once `_begin` has succeeded
   and the active book is resolved.
{summary_step}
Writes this command will perform (for context):
{writes_bullet}
</autonovel-preamble>"""


def _postamble(cmd: CommandDef) -> str:
    summary_gate = summary_gate_note(shell="Bash")
    return f"""<autonovel-postamble>
**Mandatory** — run this even if the workflow felt anticlimactic. The
postamble releases the lock, records the next step, and prints the
"what do I do next" footer. Skipping it leaves the series locked and
the user without guidance — the most common failure mode in autonovel.

After the <workflow> succeeds, do BOTH of these — in order, do not
stop after step 1:

1. Use the `Bash` tool to run:
   `autonovel _end --command {cmd.name} --args "$ARGUMENTS" --status ok`
   passing `--wrote <path>` once for each file that was actually written.
   This releases the lock, writes `.autonovel/last-action.json` with the
   standard next step, and appends a JSON line to
   `.autonovel/command-log.jsonl`.

   **Telemetry (token + cost tracking).** When the runtime exposes
   the session's usage report — Claude Code's
   `[!@usage]`-style block, an Anthropic SDK `Usage` object, etc.
   — also pass:
     - `--tier {cmd.model_tier}` (this command's resolved tier)
     - `--input-tokens <N>` (or whatever the runtime calls it)
     - `--output-tokens <N>`
     - `--cache-read-tokens <N>` (if reported)
     - `--cache-creation-tokens <N>` (if reported)
     - `--cost-usd <decimal>` (when the runtime estimates a cost)
   These are best-effort: pass what the runtime reports, omit
   the rest. The `autonovel cost` rollup tolerates partial
   data. Mechanical-only commands (no LLM call) skip every
   token / cost flag — this command is `model_tier:
   {cmd.model_tier}`, so light-tier commands without LLM work
   should still pass `--tier mechanical` so the rollup
   classifies them correctly.

   The bash output of this call IS the user-facing footer. It looks
   roughly like:

       ---
       **Done:** /{cmd.name} <args>
       **Wrote:** <path>, ...
       **Next:** /autonovel:<command> <args>
         *(rationale)*

       Other options (see `/autonovel:sidequest` for the full list):
       - /autonovel:<sidequest> <args>
           *<why>*

2. Reproduce that footer verbatim in your reply to the user as the
   final visible block. The Bash tool's stdout captures it, but you
   must echo it back as the closing message — that is the user's only
   "what do I do next" signal. **Do not summarise; do not skip; do not
   end your turn before it.** If you reply "Done!" without the footer,
   the user cannot continue.
{summary_gate}
If the <workflow> fails partway through:
- Run `autonovel _end --command {cmd.name} --args "$ARGUMENTS" --status error`
  (no `--wrote` paths). That leaves the lock marked `interrupted` so
  `/autonovel:resume` can offer recovery, and records the error in the
  command log without overwriting `last-action.json`. Then describe
  what failed to the user.
</autonovel-postamble>"""
