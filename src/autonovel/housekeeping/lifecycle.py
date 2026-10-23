"""Implementation of `autonovel _begin` and `autonovel _end`.

The adapter-injected preamble/postamble invokes these via Bash. They do all
the lock, checkpoint, last-action, and command-log bookkeeping that
REWRITE-PLAN.md §21.2 requires, so command authors don't reimplement it.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from .. import checkpoints, command_log, last_action, lock, project as project_mod
from ..adapters.base import CommandDef, discover_commands
from ..adapters.installer import _commands_source_dir
from ..paths import SeriesLayout, load_series, outline_chapter_numbers
from . import next_actions
from .next_step import PipelineState, next_step


@dataclass
class BeginResult:
    lock_info: lock.LockInfo
    checkpoint: checkpoints.Checkpoint | None
    resolved_writes: list[Path]
    resolved_book: str | None = None
    book_inferred: bool = False  # True if `--book` was missing and we filled it in
    abandoned_lock: lock.LockInfo | None = None  # set when we took over a stale lock


class BeginError(RuntimeError):
    pass


def begin(command_name: str, arg_string: str, *, runtime: str = "claude",
          series: SeriesLayout | None = None) -> BeginResult:
    series = series or load_series()
    # Self-heal the one runtime dir git cannot track when empty: a
    # series cloned from backup (or created before `.gitkeep` shipped)
    # arrives without `.autonovel/session-notes/` and `doctor` flags it.
    series.session_notes.mkdir(parents=True, exist_ok=True)
    cmd = _load_command(command_name)
    ctx = _parse_arguments(cmd, arg_string)

    book_was_explicit = "book" in ctx
    ctx = _infer_book(ctx, series)
    book_inferred = "book" in ctx and not book_was_explicit
    resolved_book = ctx.get("book")

    resolved = _resolve_writes(cmd, ctx, series.root)

    lock_info, abandoned = lock.acquire_with_takeover(
        series.lock_file,
        runtime=runtime,
        command=command_name,
        args=shlex.split(arg_string) if arg_string else [],
    )

    cp: checkpoints.Checkpoint | None = None
    if resolved:
        cp = checkpoints.create(
            series.checkpoints,
            series.root,
            resolved,
            command=command_name,
            args=shlex.split(arg_string) if arg_string else [],
        )

    return BeginResult(
        lock_info=lock_info,
        checkpoint=cp,
        resolved_writes=resolved,
        resolved_book=resolved_book,
        book_inferred=book_inferred,
        abandoned_lock=abandoned,
    )


@dataclass
class EndResult:
    last_action: last_action.LastAction | None
    footer: str
    verify_report: checkpoints.WriteVerificationReport | None = None


def end(command_name: str, arg_string: str, *, status: str, wrote: list[str],
        series: SeriesLayout | None = None,
        usage: dict | None = None,
        next_standard_step_override: str | None = None,
        next_rationale_override: str | None = None) -> EndResult:
    """`usage` carries optional telemetry from the runtime session
    (model, tier, input/output/cache tokens, estimated USD cost).
    Each field lands on the command-log entry so `autonovel cost`
    can roll it up. Missing keys land as None — mechanical-only
    commands typically pass the dict empty.

    `next_standard_step_override` lets sweep commands
    (revision-pass, draft-pass) supply a multi-line custom action
    plan that gets stored in last-action.json and surfaced as the
    canonical Next: line. Without it, the auto-computed
    `_next_step_for(series, book)` result wins — which is correct
    for single-chapter commands but wrong for sweeps where the
    closer is verify→panel→backup, not "draft N+1"."""
    series = series or load_series()
    cmd = _load_command(command_name)
    ctx = _parse_arguments(cmd, arg_string)
    ctx = _infer_book(ctx, series)
    book = ctx.get("book")
    usage = usage or {}

    if status != "ok":
        lock.mark_interrupted(series.lock_file)
        command_log.append(
            series.command_log_file,
            command=command_name,
            args=shlex.split(arg_string) if arg_string else [],
            status=status,
            wrote=list(wrote),
            note="workflow reported failure",
            book=book,
            **_usage_kwargs(usage),
        )
        return EndResult(last_action=None, footer="")

    # Verify the LLM's `--wrote` claims against the checkpoint
    # snapshot. The LLM can pass `--wrote books/x/y.md` without
    # having actually invoked Write / Edit. Compare each claimed
    # path against the begin-time backup and warn on mismatches.
    verify = _verify_writes(series, command_name, wrote)

    lock.release(series.lock_file)
    if book:
        _sync_book_state(series, book)

    # Teaser-family commands chain among themselves; everything else uses
    # the chapter pipeline. This stops "draft chapter N+1" from showing as
    # the next step during teaser/movie work (flow clarity, Phase 6+).
    ns = None
    if book:
        ns = _teaser_next_step(command_name, book) or _next_step_for(series, book)
    if next_standard_step_override is not None:
        # Sweep commands writing a custom multi-line closer. Use
        # provided rationale, or fall back to the auto-computed one
        # (rationale on the override-path is usually `None` because
        # the multi-line block is self-explanatory).
        canonical_next = next_standard_step_override
        canonical_rationale = (
            next_rationale_override
            if next_rationale_override is not None
            else (ns.rationale if ns else None)
        )
    elif ns is not None:
        canonical_next = ns.command
        canonical_rationale = ns.rationale
    else:
        canonical_next = None
        canonical_rationale = None
    la = last_action.write(
        series.last_action_file,
        command=command_name,
        args=shlex.split(arg_string) if arg_string else [],
        wrote=list(wrote),
        book=book,
        next_standard_step=canonical_next,
        next_rationale=canonical_rationale,
        sidequests=_default_sidequests(command_name, ctx),
    )

    log_note: str | None = None
    if verify is not None and verify.has_any_warning:
        bits: list[str] = []
        if verify.warnings:
            names = ", ".join(w.path for w in verify.warnings[:5])
            bits.append(
                f"verify-writes: {len(verify.warnings)} claimed path(s) "
                f"unchanged or missing — {names}"
            )
        if verify.unpaired_chapter_writes:
            bits.append(
                f"unpaired-chapter-writes: "
                f"{len(verify.unpaired_chapter_writes)} chapter(s) "
                f"modified without regenerating their .summary.md"
            )
        log_note = "; ".join(bits)
    command_log.append(
        series.command_log_file,
        command=command_name,
        args=shlex.split(arg_string) if arg_string else [],
        status="ok",
        wrote=list(wrote),
        note=log_note,
        book=book,
        **_usage_kwargs(usage),
    )
    footer = _render_footer(command_name, arg_string, wrote, la, series)
    if verify is not None and verify.has_any_warning:
        # Surface verify-writes warnings (unchanged / missing /
        # unpaired-chapter) at the TOP of the postamble, BEFORE
        # the Done / Wrote / Next block. A warning at the bottom
        # gets buried under long sweep closers — that's how the
        # 2026-04-30 revision-pass silent-failure-of-five-
        # chapters bug went unnoticed.
        footer = _render_verify_warning(verify) + "\n\n" + footer.lstrip("\n")
    return EndResult(last_action=la, footer=footer, verify_report=verify)


def _usage_kwargs(usage: dict) -> dict:
    """Forward only the recognised usage keys to command_log.append.
    Unknown keys are dropped silently so future telemetry shape
    changes don't break existing log entries."""
    keys = (
        "model", "tier", "input_tokens", "output_tokens",
        "cache_read_tokens", "cache_creation_tokens", "cost_usd",
    )
    return {k: usage.get(k) for k in keys}


def _verify_writes(series: SeriesLayout, command_name: str,
                    claimed: list[str]) -> checkpoints.WriteVerificationReport | None:
    """Find the most recent checkpoint that matches `command_name`
    in the series's checkpoint dir and verify the claimed writes
    against it. Returns None when no checkpoint can be located —
    e.g. when the command has empty `writes:` and `begin` skipped
    checkpoint creation."""
    if not claimed:
        return None
    cps = checkpoints.list_checkpoints(series.checkpoints)
    if not cps:
        return None
    # Most recent first. Match on command name to skip checkpoints
    # from earlier commands (e.g. nested sub-agent invocations).
    matching = [cp for cp in reversed(cps) if cp.command == command_name]
    cp = matching[0] if matching else cps[-1]
    return checkpoints.verify_writes(cp, series.root, claimed)


def _render_verify_warning(report: "checkpoints.WriteVerificationReport") -> str:
    """User-facing block surfaced at the TOP of the postamble when
    one or more `--wrote` claims couldn't be verified against the
    checkpoint. Has to lead the footer because long sweep closers
    (verify→panel→backup multi-line block) would otherwise push it
    off screen — exactly how the 2026-04-30 revision-pass silent-
    failure went unnoticed.

    Specifically calls out chapter files (the load-bearing case)
    so the user immediately sees which chapters look like the
    revise step no-op'd on them."""
    chapter_unchanged: list[str] = []
    other_unchanged: list[str] = []
    missing: list[str] = []
    other: list[tuple[str, str]] = []
    for w in report.warnings:
        if w.status == "missing":
            missing.append(w.path)
        elif w.status == "unchanged":
            if "/chapters/ch_" in w.path and w.path.endswith(".md"):
                chapter_unchanged.append(w.path)
            else:
                other_unchanged.append(w.path)
        else:
            other.append((w.path, w.status))

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("🔴 VERIFY-WRITES: claims do not match disk")
    lines.append("=" * 60)
    if chapter_unchanged:
        lines.append(
            f"\n⚠️  {len(chapter_unchanged)} chapter file(s) were "
            f"claimed modified but the bytes match the pre-command "
            f"checkpoint — the LLM said it revised them but did not. "
            f"Likely cause: the per-chapter task subagent reported "
            f"success without invoking Write/Edit for these chapters. "
            f"Re-run the sweep targeting just these chapters:"
        )
        for p in chapter_unchanged:
            lines.append(f"    {p}")
    if missing:
        lines.append(
            f"\n❌ {len(missing)} claimed-created path(s) do not exist:"
        )
        for p in missing:
            lines.append(f"    {p}")
    if other_unchanged:
        lines.append(
            f"\n⚠️  {len(other_unchanged)} non-chapter path(s) "
            f"unchanged (likely OK if the command was conditionally "
            f"writing — review):"
        )
        for p in other_unchanged:
            lines.append(f"    {p}")
    if other:
        lines.append("")
        for p, s in other:
            lines.append(f"  - {p}: {s}")
    if report.unpaired_chapter_writes:
        lines.append(
            f"\n⚠️  {len(report.unpaired_chapter_writes)} chapter "
            f"file(s) were modified WITHOUT regenerating their "
            f"`.summary.md`. The per-chapter summary is the rolling-"
            f"context surface every downstream drafter / reviser "
            f"reads — when chapter prose drifts from the summary, "
            f"continuity breaks (the next chapter sees the OLD "
            f"cast / threads / POV state). Regenerate now:"
        )
        for p in report.unpaired_chapter_writes:
            try:
                ch_num = int(p.rsplit("/ch_", 1)[1].rstrip(".md"))
                book = p.split("/", 2)[1]
                lines.append(
                    f"    /autonovel:summarize-chapter {ch_num} "
                    f"--book {book} --force"
                )
            except (ValueError, IndexError):
                lines.append(f"    {p}  (unable to parse chapter number)")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers


_ARG_HINT_PLACEHOLDER = re.compile(r"<([^>]+)>")
_PATH_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _infer_book(ctx: dict[str, str], series: SeriesLayout) -> dict[str, str]:
    """If `--book` was not in `$ARGUMENTS`, fill it in from
    `last-action.json` (the book of the most recent command) or, failing
    that, from a single-book project. If neither yields a book and the
    project has multiple books, leave `ctx` untouched — the caller
    surfaces a usage error.
    """
    if "book" in ctx:
        return ctx

    # 1. Most recent book the user worked on.
    try:
        la = last_action.read(series.last_action_file)
    except Exception:  # noqa: BLE001 — last-action file may be malformed
        la = None
    if la is not None and la.book:
        try:
            cfg = project_mod.load(series.project_file)
        except Exception:  # noqa: BLE001
            cfg = None
        if cfg is not None and cfg.book_by_name(la.book) is not None:
            ctx = dict(ctx)
            ctx["book"] = la.book
            return ctx

    # 2. Single-book series — only one possible book.
    try:
        cfg = project_mod.load(series.project_file)
    except Exception:  # noqa: BLE001
        return ctx
    if len(cfg.books) == 1:
        ctx = dict(ctx)
        ctx["book"] = cfg.books[0].name
        return ctx

    return ctx


def _load_command(name: str) -> CommandDef:
    for cmd in discover_commands(_commands_source_dir()):
        if cmd.name == name:
            return cmd
    raise BeginError(f"unknown command: {name!r}")


def _parse_arguments(cmd: CommandDef, arg_string: str) -> dict[str, str]:
    """Best-effort parse of $ARGUMENTS into a dict keyed by placeholder name."""
    tokens = shlex.split(arg_string) if arg_string else []
    ctx: dict[str, str] = {}

    # Pull out `--key value` pairs; collect bare positionals separately.
    positionals: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("--"):
            key = t[2:]
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                ctx[key] = tokens[i + 1]
                i += 2
                continue
            ctx[key] = "true"
            i += 1
            continue
        positionals.append(t)
        i += 1

    # Map positional tokens to `<foo>` entries in the argument-hint, in order.
    if cmd.argument_hint:
        pos_names = [
            m.group(1) for m in _ARG_HINT_PLACEHOLDER.finditer(cmd.argument_hint)
            if not m.group(1).startswith("--")
        ]
        # Skip placeholders that look like `--book <short-name>` (those are flag values).
        bare_positions = [n for n in pos_names if not _looks_like_flag_value(n, cmd.argument_hint)]
        for name, value in zip(bare_positions, positionals):
            key = _normalize_key(name)
            ctx.setdefault(key, value)

    # Derived convenience: chapter → chapter, {prev} → chapter-1 zero-padded.
    if "chapter" in ctx or "chapter_number" in ctx:
        ch = ctx.get("chapter") or ctx.get("chapter_number")
        try:
            n = int(ch)
        except (TypeError, ValueError):
            pass
        else:
            ctx["chapter"] = f"{n:02d}"
            ctx["prev"] = f"{max(n - 1, 0):02d}"
    return ctx


def _looks_like_flag_value(name: str, hint: str) -> bool:
    # A `<short-name>` placeholder that sits after `--book` is a flag value.
    m = re.search(r"--[a-z-]+\s+<" + re.escape(name) + r">", hint)
    return m is not None


def _normalize_key(name: str) -> str:
    return name.replace("-", "_").replace(" ", "_")


def _resolve_writes(cmd: CommandDef, ctx: dict[str, str], series_root: Path) -> list[Path]:
    out: list[Path] = []
    ctx_for_paths = dict(ctx)
    # The argument-hint uses `<short-name>` for the book, but `writes:` uses
    # `{book}`. Remap common aliases.
    if "book" not in ctx_for_paths:
        for alias in ("short-name", "short_name"):
            if alias in ctx_for_paths:
                ctx_for_paths["book"] = ctx_for_paths[alias]
                break
    if "chapter" not in ctx_for_paths and "chapter_number" in ctx_for_paths:
        ctx_for_paths["chapter"] = ctx_for_paths["chapter_number"]

    for raw in cmd.writes:
        resolved = _substitute_placeholders(raw, ctx_for_paths)
        if resolved is None:
            # Unresolved placeholder — skip rather than crash; the command
            # body is responsible for the real write.
            continue
        if any(ch in resolved for ch in "*?["):
            # A glob in `writes:` (e.g. `edit_logs/editor_letter_*.md`)
            # snapshots the files that exist now; a file the command
            # creates later is new by definition. Appending the literal
            # pattern checkpointed a path named "…_*.md".
            out.extend(sorted(p for p in series_root.glob(resolved) if p.is_file()))
            continue
        out.append(series_root / resolved)
    return out


def _substitute_placeholders(path: str, ctx: dict[str, str]) -> str | None:
    def repl(match: re.Match[str]) -> str:
        key = _normalize_key(match.group(1))
        if key not in ctx:
            raise KeyError(key)
        return ctx[key]

    try:
        return _PATH_PLACEHOLDER.sub(repl, path)
    except KeyError:
        return None


# Teaser/movie-mode commands chain among THEMSELVES, not into the chapter
# pipeline — so after `teaser-render` the next step is `teaser-assemble`, not
# "draft chapter N+1". Each maps to (next command template, rationale). The
# `{book}` placeholder is filled with the active book. (Phase 6+ flow clarity.)
_TEASER_NEXT: dict[str, tuple[str, str]] = {
    "autonovel:treatment": (
        "/autonovel:teaser --book {book} --length 180",
        "Treatment written — build the teaser beat-sheet + shot prompts from it."),
    "autonovel:teaser-brief": (
        "/autonovel:teaser-beats --book {book}",
        "Teaser brief distilled (through-line + turn + killer lines) — select "
        "the beats from it."),
    "autonovel:teaser": (
        "/autonovel:teaser-render --book {book} --provider stub",
        "Beats + shots authored AND the critique→revise loop ran to a READY "
        "gate — validate the chain FREE with the stub, then develop references "
        "(/autonovel:teaser-refs) and render on a real backend."),
    "autonovel:teaser-beats": (
        "/autonovel:shot-prompts --book {book}",
        "Beat-sheet written — turn the spine + beats into provider-ready shots."),
    "autonovel:shot-prompts": (
        "/autonovel:teaser-critique --book {book}",
        "Shots written — re-check the story spine / dialogue / cards before render."),
    "autonovel:teaser-critique": (
        "/autonovel:teaser-render --book {book} --provider stub",
        "If the critique flagged must-fix issues, run `/autonovel:teaser-revise "
        "--book {book}` to APPLY them (no hand edits); when the render gate is "
        "READY, validate the chain FREE with the stub before a real backend."),
    "autonovel:teaser-revise": (
        "/autonovel:teaser-critique --book {book}",
        "Critique findings applied in place — re-critique to confirm the gate is "
        "READY, then render."),
    "autonovel:teaser-refs": (
        "/autonovel:teaser-render --book {book} --provider gemini --kind image --refs",
        "References developed — render reference-conditioned keyframes, then "
        "--from-keyframes for motion."),
    "autonovel:teaser-render": (
        "/autonovel:teaser-assemble --book {book}",
        "Clips rendered to teaser/clips/ — stitch them into one teaser video."),
    "autonovel:teaser-assemble": (
        "/autonovel:teaser-assemble --book {book} --force",
        "Cut assembled — review teaser/<title>_teaser_latest.mp4; re-cut by "
        "editing teaser/cut_list.json (reorder/trim/transitions) and re-running."),
    "autonovel:teaser-transitions": (
        "/autonovel:teaser-assemble --book {book}",
        "Transition candidates surfaced — apply the ones you like, then assemble."),
    "autonovel:teaser-takes": (
        "/autonovel:teaser-assemble --book {book}",
        "Takes listed — promote one with teaser-take-pick, then assemble."),
    "autonovel:teaser-take-pick": (
        "/autonovel:teaser-assemble --book {book}",
        "Take promoted — re-assemble to use it."),
}


def _teaser_next_step(command_name: str, book: str) -> object | None:
    """Teaser-flow next step for a movie-mode command (else None so the
    caller falls back to the chapter pipeline). Keeps the postamble from
    suggesting "draft chapter N+1" in the middle of teaser work."""
    entry = _TEASER_NEXT.get(command_name)
    if entry is None:
        return None
    from .next_step import NextStep
    cmd, rationale = entry
    return NextStep(command=cmd.format(book=book), rationale=rationale)


def _next_step_for(series: SeriesLayout, book: str) -> object:
    """Build a PipelineState for `book` and ask next_step what to suggest.

    Decision order:
      1. Foundation gap — if any of the five foundation artefacts is
         empty, recommend running it. Walks world → characters → voice
         → canon → outline so the user never has to remember the
         sequence.
      2. Pending-canon gate — if `pending_canon.md` has entries that
         haven't been promoted, surface that *between* chapters (after
         a draft is evaluated, before the next is started) so chapter
         N+1 sees the new facts. Skipped during foundation phase since
         no canon candidates exist yet.
      3. Generic next_step decision tree — phase-driven (drafting →
         evaluate → revise / advance, etc.). Phase is inferred from the
         filesystem rather than `project.yaml :: books[].status` to
         keep the recommendation self-correcting after rollbacks.
    """
    cfg = project_mod.load(series.project_file)
    entry = cfg.book_by_name(book)
    book_root = series.books / book

    missing = _foundation_gap(series, book_root)
    if missing is not None:
        from .next_step import NextStep
        return NextStep(command=missing.command, rationale=missing.rationale)

    pending = _pending_canon_gate(series, book_root)
    if pending is not None:
        from .next_step import NextStep
        return NextStep(command=pending.command, rationale=pending.rationale)

    phase, chapters_drafted = _infer_phase(series, book_root)
    state = PipelineState(
        book=book,
        phase=phase,
        chapters_drafted=chapters_drafted,
        # The outline declares the book's length. Without it the drafting
        # branch can't tell the last chapter from any other and offers to
        # draft one past the end (kingmaker2, 2026-10-22: "draft 20" after
        # a 19-chapter outline was finished).
        chapters_total=len(outline_chapter_numbers(book_root / "outline.md")),
        editor_letter_done=(book_root / "edit_logs" / "editor_letter.md").is_file(),
        foundation_threshold=cfg.defaults.get("foundation_threshold", 7.5),
        chapter_threshold=cfg.defaults.get("chapter_threshold", 7.0),
        dimension_floor=cfg.defaults.get("dimension_floor"),
    )

    # Read the latest chapter's eval score from eval_logs/ if any
    # exists. Without this, /autonovel:next loops on "evaluate
    # --chapter N" because next_step's drafting branch can't decide
    # between "advance" and "revise" without a score, and falls back
    # to recommending evaluate. Author hit this 2026-04-25.
    if chapters_drafted > 0:
        last_n = chapters_drafted
        score = _last_eval_score(book_root, last_n)
        state.last_chapter_number = last_n
        state.last_chapter_score = score
        from ..mechanical.chapter_summary import chapter_score_details
        detail = chapter_score_details(book_root / "eval_logs").get(last_n)
        if detail is not None and detail.low_dim is not None and detail.low_score is not None:
            state.last_chapter_low = (detail.low_dim, detail.low_score)
    elif phase == "foundation":
        # Same shape of bug for the foundation phase (hit 2026-10-13):
        # without the latest `--phase foundation` score, next_step's
        # foundation branch can never recommend `draft 1` and the
        # footer says "below threshold; re-evaluate" after a 7.8.
        found = _last_foundation_score(book_root)
        if found is not None:
            state.foundation_score = found

    if entry is not None and _phase_rank(entry.status) > _phase_rank(state.phase):
        state.phase = entry.status
    return next_step(state)


def _sync_book_state(series: SeriesLayout, book: str) -> None:
    """Refresh `books/<book>/state.json` from disk after every command:
    `chapters_drafted` (chapter files), `chapters_total` (the outline's
    chapters) and `phase`, which only moves forward (`drafting` once a
    chapter exists, `revision` once every outlined chapter is drafted).
    Before this, nothing after `new-book` wrote the file, so a finished
    19-chapter book still read `phase: seed`, `chapters_total: 0`.
    Best-effort: a missing or unreadable file is left alone."""
    import json
    from ..paths import iter_chapter_files
    book_root = series.books / book
    path = book_root / "state.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    drafted = {int(p.stem.split("_")[-1]) for p in iter_chapter_files(book_root / "chapters")
               if p.stem.split("_")[-1].isdigit()}
    outlined = outline_chapter_numbers(book_root / "outline.md")
    phase = data.get("phase") or "seed"
    if drafted:
        inferred = "revision" if outlined and set(outlined) <= drafted else "drafting"
        if _phase_rank(inferred) > _phase_rank(phase):
            phase = inferred
    updated = dict(data, chapters_drafted=len(drafted),
                   chapters_total=len(outlined) or data.get("chapters_total", 0),
                   phase=phase)
    if updated != data:
        try:
            path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass


def _last_eval_score(book_root: Path, chapter: int) -> float | None:
    """Return the most recent `overall_score` recorded for `chapter`
    in `books/<book>/eval_logs/`, or None if no eval has run yet.

    Delegates to the chapter-summary indexer so the three production
    naming conventions all resolve identically: `<ts>_chNN_eval.json`
    (draft-pass / revision-pass timestamped), `<ts>_chNN.json`
    (evaluate.md timestamped), and plain `chNN_eval.json` (legacy
    paired with mtime ordering). Bug fixed 2026-04-28: the prior
    `glob('chNN*.json')` only caught the third shape, so after a
    user ran `/autonovel:evaluate --chapter N` (which writes the
    timestamped form) `/autonovel:next` saw no score and looped on
    "evaluate" — exactly the regression the realistic-fixture pass
    was supposed to catch.
    """
    from ..mechanical.chapter_summary import _index_latest_per_chapter_eval
    index = _index_latest_per_chapter_eval(book_root / "eval_logs")
    return index.get(chapter)


def _last_foundation_score(book_root: Path) -> float | None:
    """Return the `overall_score` of the newest
    `books/<book>/eval_logs/<ts>_foundation.json` written by
    `/autonovel:evaluate --phase foundation`, or None when no
    foundation eval has run (or none parses). Newest = highest
    `YYYYMMDD_HHMMSS` prefix, with mtime as the tie-break."""
    import json
    logs_dir = book_root / "eval_logs"
    if not logs_dir.is_dir():
        return None
    candidates = sorted(
        logs_dir.glob("*_foundation.json"),
        key=lambda p: (p.name, p.stat().st_mtime),
    )
    for path in reversed(candidates):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        score = data.get("overall_score") if isinstance(data, dict) else None
        if isinstance(score, (int, float)):
            return float(score)
    return None


@dataclass
class _FoundationGap:
    command: str
    rationale: str


def _pending_canon_gate(series: SeriesLayout, book_root: Path) -> "_FoundationGap | None":
    """Return a `promote-canon` recommendation when:
      - the user has at least one drafted chapter (drafting / revision
        phase — no canon candidates exist before drafting starts),
      - `books/<book>/pending_canon.md` has content beyond its
        template stub,
      - and the file's modification time is newer than the most recent
        run of `/autonovel:promote-canon` for this series (so we don't
        re-suggest a freshly-emptied pending file).

    Returning None means "no gate" — fall through to the generic
    next_step decision tree.
    """
    from ..paths import iter_chapter_files
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return None
    drafted = bool(iter_chapter_files(chapters_dir))
    if not drafted:
        return None

    pending = book_root / "pending_canon.md"
    if not _pending_canon_has_entries(pending):
        return None

    # Skip if pending_canon.md is older than the last successful
    # /autonovel:promote-canon run (logged in command-log.jsonl).
    last_promote = _last_command_run(series, "autonovel:promote-canon")
    if last_promote is not None and pending.stat().st_mtime <= last_promote:
        return None

    book_name = book_root.name
    return _FoundationGap(
        command=f"/autonovel:promote-canon --book {book_name}",
        rationale=(
            "pending_canon.md has new candidate facts; promote them so "
            "the next chapter draft sees them"
        ),
    )


def _pending_canon_has_entries(pending_path: Path) -> bool:
    """True if `pending_canon.md` carries at least one bullet entry of
    its expected `- [headline] body` shape. Robust to template length
    drift; we don't compare byte counts because real candidate entries
    are often shorter than the template's explanatory text."""
    if not pending_path.is_file():
        return False
    try:
        text = pending_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "+ ")) and len(stripped) > 4:
            return True
    return False


def _last_command_run(series: SeriesLayout, command_name: str) -> float | None:
    """Return the UNIX timestamp of the most recent successful run of
    `command_name`, or None if there isn't one. Reads
    `.autonovel/command-log.jsonl`."""
    from datetime import datetime
    from .. import command_log
    try:
        entries = command_log.read_all(series.command_log_file)
    except Exception:  # noqa: BLE001
        return None
    latest: float | None = None
    for e in entries:
        if e.command != command_name or e.status != "ok":
            continue
        try:
            ts = datetime.fromisoformat(e.timestamp).timestamp()
        except (ValueError, AttributeError):
            continue
        if latest is None or ts > latest:
            latest = ts
    return latest


def _foundation_gap(series: SeriesLayout, book_root: Path) -> "_FoundationGap | None":
    """Return the first missing foundation artefact, or None if all are
    in place. Order:
      0. (period-only) research-from-seed if `project.yaml :: period.start`
         is set and `shared/research/notes/` is empty. Skipped for
         contemporary projects with no period.
      1-7. world → characters → voice → shared canon → design →
           outline → book canon (`gen-canon --book`, seeded from the
           outline). The design step is a gap only while the book has
           no chapters: a drafted book is re-designed as a new book.
    """
    book_name = book_root.name

    # Step 0: research-from-seed when the project has a period set, so
    # gen-world and gen-canon are built on cited primary sources rather
    # than the LLM's general knowledge.
    if _project_has_period(series) and not _research_notes_populated(series):
        return _FoundationGap(
            command=f"/autonovel:research --from-seed --book {book_name}",
            rationale=(
                "project has a period set but shared/research/notes/ is "
                "empty; research the seed before generating world/canon"
            ),
        )

    checks = [
        (series.shared / "world.md", "/autonovel:gen-world",
         "shared/world.md is empty; foundation starts with the world"),
        (series.shared / "characters.md", "/autonovel:gen-characters",
         "shared/characters.md is empty; cast registry comes after the world"),
        (book_root / "voice.md", f"/autonovel:voice-discovery --book {book_name}",
         "voice.md Part 2 is unfilled; pick a voice before generating canon"),
        (series.shared / "canon.md", "/autonovel:gen-canon",
         "shared/canon.md is empty; seed hard facts before outlining"),
        (book_root / "design.md", f"/autonovel:design --book {book_name}",
         "design.md is missing; design the book (climax, question, opponent, "
         "plants, sequences) before outlining it"),
        (book_root / "outline.md", f"/autonovel:gen-outline --book {book_name}",
         "outline.md is empty; outline before drafting"),
    ]
    markers = ("(empty", "Generated by", "Seeded by", "Filled by", "Leave empty until then")
    from ..paths import iter_chapter_files
    drafted = bool(iter_chapter_files(book_root / "chapters"))
    for path, command, rationale in checks:
        if path.name == "design.md" and (drafted or _is_populated(
                book_root / "outline.md", min_chars=120, exclude_markers=markers)):
            # Books outlined or drafted before the design stage keep
            # their flow; /autonovel:next still suggests a design.
            continue
        if not _is_populated(path, min_chars=120, exclude_markers=markers):
            return _FoundationGap(command=command, rationale=rationale)

    # Step 6: the book-scoped half of gen-canon. It is seeded FROM the
    # outline, so it comes after gen-outline — and it is only a *gap*
    # while the book has no chapters yet. Once drafting has begun,
    # promote-canon owns books/<book>/canon.md (a book imported or
    # drafted before book-scoped canon existed must not be told to
    # re-seed it).
    if (not drafted
            and not _is_populated(book_root / "canon.md", min_chars=120,
                                  exclude_markers=markers)):
        return _FoundationGap(
            command=f"/autonovel:gen-canon --book {book_name}",
            rationale=(f"books/{book_name}/canon.md is empty; seed this book's "
                       "outline-committed facts before drafting"),
        )
    return None


def _project_has_period(series: SeriesLayout) -> bool:
    """True when `project.yaml :: period.start` is non-null. Used to
    decide whether to insert research-from-seed at the front of the
    foundation chain."""
    try:
        cfg = project_mod.load(series.project_file)
    except Exception:  # noqa: BLE001
        return False
    period = cfg.period or {}
    return period.get("start") not in (None, "")


def _research_notes_populated(series: SeriesLayout) -> bool:
    """True when `shared/research/notes/` contains at least one .md
    file with substantive content. Ignores `.gitkeep` and template
    placeholders."""
    notes_dir = series.shared / "research" / "notes"
    if not notes_dir.is_dir():
        return False
    for p in notes_dir.glob("*.md"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "# Research" in text and len(text.strip()) > 200:
            return True
    return False


# Rank phases so we can pick the more-advanced of "filesystem says X,
# project.yaml says Y". Unknown phases sort below "seed".
_PHASE_ORDER = (
    "unknown", "seed", "foundation", "outlined", "drafting",
    "revision", "review", "export", "done",
)


def _phase_rank(phase: str) -> int:
    try:
        return _PHASE_ORDER.index(phase)
    except ValueError:
        return 0


def _infer_phase(series: SeriesLayout, book_root: Path) -> tuple[str, int]:
    """Walk the on-disk artefacts and return (phase, chapters_drafted).

    Order of checks is most-advanced first: a book that has been drafted
    and reviewed should not regress to "outlined" because outline.md
    still exists.
    """
    from ..paths import iter_chapter_files
    chapters_dir = book_root / "chapters"
    chapter_files = iter_chapter_files(chapters_dir)
    n_chapters = len(chapter_files)

    # Drafting / revision: chapters exist.
    if n_chapters > 0:
        # We don't yet distinguish drafting from revision from review at
        # the filesystem level (the project would need eval_logs / review
        # markers). next_step's drafting branch handles "draft N+1 vs
        # revise N" via last_chapter_score, which we don't have here —
        # so default to drafting and let the user fall through to the
        # standard next-chapter recommendation.
        return ("drafting", n_chapters)

    # Outlined: outline.md is non-trivial.
    outline = book_root / "outline.md"
    if _is_populated(outline, min_chars=120, exclude_markers=("(empty",)):
        return ("foundation", 0)  # foundation phase, but next_step's
        # foundation branch recommends draft-1 when foundation_score
        # ≥ threshold; without that score we let the user run evaluate
        # to advance.

    # Voice discovered.
    voice = book_root / "voice.md"
    if _is_populated(voice, min_chars=400, exclude_markers=("(empty", "Generated by", "Seeded by", "Filled by", "Leave empty until then")):
        return ("foundation", 0)

    # Foundation under way: any of the shared/ files written.
    for fname in ("world.md", "characters.md", "canon.md"):
        if _is_populated(series.shared / fname, min_chars=120,
                         exclude_markers=("(empty", "Generated by", "Seeded by", "Filled by", "Leave empty until then")):
            return ("foundation", 0)

    return ("seed", 0)


def _is_populated(path: Path, *, min_chars: int, exclude_markers: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    stripped = text.strip()
    if len(stripped) < min_chars:
        return False
    if any(marker in text for marker in exclude_markers):
        return False
    return True


def _default_sidequests(command_name: str, ctx: dict[str, str]) -> list[dict[str, str]]:
    book = ctx.get("book")
    chapter = ctx.get("chapter")
    if command_name == "autonovel:draft" and book and chapter:
        try:
            n = int(chapter)
        except ValueError:
            return []
        return [
            {"command": f"/autonovel:shorten --chapter {n} --target-words 2800 --book {book}",
             "why": "compress without dropping below the 1800-word floor"},
            {"command": f"/autonovel:revise {n} --book {book}",
             "why": "rewrite against a revision brief"},
            {"command": "autonovel rollback",
             "why": "undo this draft entirely"},
        ]
    return []


def _render_footer(command_name: str, arg_string: str, wrote: list[str],
                   la: last_action.LastAction,
                   series: SeriesLayout | None = None) -> str:
    lines = [
        "",
        "---",
        f"**Done:** /{command_name} {arg_string}".rstrip(),
    ]
    if wrote:
        lines.append("**Wrote:** " + ", ".join(wrote))
    if la.next_standard_step:
        lines.append(f"**Next:** {la.next_standard_step}")
        if la.next_rationale:
            lines.append(f"  *({la.next_rationale})*")
    hint = _build_postamble_hint(command_name, la.book, series)
    if hint is not None:
        lines.append(hint)
    if la.sidequests:
        lines.append("")
        lines.append("Other options (see `/autonovel:sidequest` for the full list):")
        for sq in la.sidequests:
            lines.append(f"- {sq['command']}")
            if sq.get("why"):
                lines.append(f"    *{sq['why']}*")
    return "\n".join(lines)


def _build_postamble_hint(command_name: str, book: str | None,
                           series: SeriesLayout | None) -> str | None:
    """Wrap `next_actions.top_hint` with belt-and-suspenders so a
    crash in the hint path never breaks postamble rendering. The
    hint is decorative — no command should fail because we couldn't
    suggest a follow-up."""
    if series is None:
        return None
    try:
        return next_actions.top_hint(
            series, just_ran=command_name, book=book
        )
    except Exception:  # noqa: BLE001 — hint is decorative
        return None
