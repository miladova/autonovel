"""`autonovel` command-line entry point.

This CLI does housekeeping only — it never calls an LLM. The `install`
subcommand renders the generic `commands/*.md` files through a runtime-
specific adapter and writes them into the runtime's expected location.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .adapters import detect as detect_mod
from .adapters import installer as installer_mod
from .housekeeping import doctor, lifecycle, plates as plates_mod, rollback, scaffold, status, statusline as statusline_mod, statusline_setup, test_fixture
from .paths import SeriesNotFound, load_series


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autonovel")
    p.add_argument("--version", action="version", version=f"autonovel {__version__}")
    sub = p.add_subparsers(dest="command")

    new_series = sub.add_parser("new-series", help="Create a new series folder.")
    new_series.add_argument("name")
    new_series.add_argument("--genre", default="general")
    new_series.add_argument("--dest", default=None, help="Parent directory (default: cwd)")
    new_series.set_defaults(func=_cmd_new_series)

    new_book = sub.add_parser("new-book", help="Add a book to a series.")
    new_book.add_argument("name")
    new_book.add_argument("--series", default=None, help="Series name or path; default: walk up from cwd")
    new_book.add_argument("--pov", default=None)
    new_book.add_argument(
        "--story-time-range",
        default=None,
        help="Inclusive year range, e.g. `1519-1523`",
    )
    new_book.add_argument(
        "--isolated", action="store_true",
        help="Set `context: isolated` — never load sibling-book chapters as "
             "drafting context. Use for a rewrite / second version of a story "
             "another book in this series already tells.",
    )
    new_book.set_defaults(func=_cmd_new_book)

    cp = sub.add_parser(
        "canon-partition",
        help="Move book-scoped bullets out of shared/canon.md into books/<book>/canon.md.",
        description=(
            "Bullets whose `(from <book> …)` provenance names a book move to that "
            "book's canon.md automatically. `--move-section` / `--move-key` move "
            "untagged bullets to `--to-book`. Research-cited bullets and "
            "`## Superseded` audit blocks always stay in shared/canon.md. "
            "Idempotent. The slash command /autonovel:canon-partition wraps this "
            "with an LLM pass that classifies the untagged leftovers."
        ),
    )
    cp.add_argument("--series", default=None, help="Series name or path; default: walk up from cwd")
    cp.add_argument("--to-book", default=None,
                    help="Target book for --move-section / --move-key.")
    cp.add_argument("--move-section", action="append", default=[], metavar="HEADING",
                    help="Move every bullet under this `## heading` to --to-book (repeatable).")
    cp.add_argument("--move-key", action="append", default=[], metavar="SHORTNAME",
                    help="Move the bullet whose leading `[shortname]` matches to --to-book (repeatable).")
    cp.add_argument("--dry-run", action="store_true", help="Report only; write nothing.")
    cp.add_argument("--no-lock", action="store_true",
                    help="Skip the in-progress.lock check (inside a slash command whose preamble holds it).")
    cp.add_argument("--format", choices=("markdown", "json"), default="markdown")
    cp.set_defaults(func=_cmd_canon_partition)

    imp = sub.add_parser(
        "import-book",
        help="Import an externally-written manuscript into a book's chapters/.",
        description=(
            "Split a directory of `*.md` files OR a single combined "
            "manuscript file into autonovel-shape ch_NN.md files. "
            "Marks the book as `mode: edit-imported` so /autonovel:draft "
            "refuses to overwrite without --force."
        ),
    )
    imp.add_argument("name", help="Book name (must already exist in project.yaml).")
    imp.add_argument("--series", default=None, help="Series name or path; default: walk up from cwd")
    imp.add_argument("--from", dest="source", required=True,
                      help="Path to a manuscript file or directory of *.md files.")
    imp.add_argument("--split-on", dest="split_on", default=None,
                      help="Regex (multiline) to split a single-file manuscript on. "
                            "Default: split on `^# ` then `^## ` headings.")
    imp.add_argument("--start", dest="start_at", type=int, default=None,
                      help="Chapter number to start at (default: append after existing).")
    imp.add_argument("--pov", default=None,
                      help="POV name to write into the imported chapters' frontmatter "
                            "(default: `inferred`).")
    imp.add_argument("--keep-mode", dest="keep_mode", action="store_true",
                      help="Leave project.yaml :: books[].mode untouched. Default flips "
                            "the book to `mode: edit-imported`.")
    imp.add_argument("--overwrite", action="store_true",
                      help="Overwrite chapter files that already exist at the target paths.")
    imp.add_argument("--dry-run", dest="dry_run", action="store_true",
                      help="Print what would be written without touching disk.")
    imp.add_argument("--reverse-engineer", dest="reverse_engineer",
                      action="store_true",
                      help="After import, scan the imported prose for candidate "
                            "character names and write/append `shared/characters.md` "
                            "with auto-detected entries. Mechanical only; voice "
                            "and outline reverse-engineering belong in the "
                            "follow-up LLM commands (voice-discovery / "
                            "summarize-chapter / gen-outline).")
    imp.set_defaults(func=_cmd_import_book)

    st = sub.add_parser("status", help="Show series status.")
    st.add_argument("--series", default=None)
    st.set_defaults(func=_cmd_status)

    cs = sub.add_parser(
        "cost",
        help="Roll up token + cost figures from .autonovel/command-log.jsonl.",
        description=(
            "Read every entry in the series command-log and aggregate "
            "by book / tier / command. Token counts and cost figures "
            "are LLM-self-reported estimates, not invoices. Mechanical-"
            "only commands count as $0 runs."
        ),
    )
    cs.add_argument("--series", default=None)
    cs.add_argument("--format", choices=("markdown", "json"), default="markdown")
    cs.set_defaults(func=_cmd_cost)

    doc = sub.add_parser("doctor", help="Sanity-check a series directory.")
    doc.add_argument("--series", default=None)
    doc.add_argument("--fix", action="store_true", help="Recreate missing directories")
    doc.add_argument("--install-missing", dest="install_missing",
                      action="store_true",
                      help="After the report, install any missing external "
                            "export tools (tectonic / pandoc / ffmpeg / "
                            "Pillow / fontconfig / etc.) by handing off to "
                            "`install-export-tools` for the missing subset. "
                            "Requires sudo for system packages; prompts "
                            "before each tool unless `--yes` is also passed.")
    doc.add_argument("--yes", action="store_true",
                      help="With `--install-missing`, skip per-tool "
                            "confirmation prompts.")
    doc.set_defaults(func=_cmd_doctor)

    tui_p = sub.add_parser("tui",
                            help="Long-running terminal UI for browsing series state. Read-only; never acquires the lock. Run in a separate terminal window from the series root.")
    tui_p.add_argument("--series", default=None,
                        help="Series root path; default: walk up from cwd.")
    tui_p.add_argument("--book", default=None,
                        help="Initial book to display; default: first book in project.yaml.")
    tui_p.set_defaults(func=_cmd_tui)

    onb = sub.add_parser("onboard",
                          help="Interactive onboarding wizard — captures pitch, period, title, author into seed.txt + project.yaml.")
    onb.add_argument("book", help="Book name (must already exist in project.yaml; run `autonovel new-book` first).")
    onb.add_argument("--series", default=None, help="Series name or path; default: walk up from cwd.")
    onb.add_argument("--non-interactive", action="store_true",
                      help="Skip the wizard; just print the next-step guidance based on what's already in seed.txt + project.yaml.")
    onb.set_defaults(func=_cmd_onboard)

    iet = sub.add_parser("install-export-tools",
                          help="Interactive installer for the external tools the export commands depend on (tectonic / pandoc / ffmpeg / Pillow / fontconfig / etc.).")
    iet.add_argument("--exports", default=None,
                      help="Comma-list of exports to install for: pdf, epub, cover, audiobook, art. Default: all.")
    iet.add_argument("--apply", action="store_true",
                      help="Run the install commands instead of printing them. Prompts before each tool unless --yes.")
    iet.add_argument("--yes", action="store_true",
                      help="Skip per-tool confirmation prompts under --apply.")
    iet.set_defaults(func=_cmd_install_export_tools)

    rt = sub.add_parser(
        "refresh-templates",
        help="Refresh package-shipped templates (default: typeset/) over the live series.",
        description=(
            "Re-copy package-shipped series templates over the live "
            "series. Default refreshes only `typeset/` — that's where "
            "the PDF page-header fixes live and the only subtree the "
            "user is unlikely to have hand-edited. Pass `--only` to "
            "refresh a different set of subtrees."
        ),
    )
    rt.add_argument("--series", default=None)
    rt.add_argument("--only", action="append", default=None,
                    help="Subtree to refresh (repeatable). Default: typeset.")
    rt.add_argument("--dry-run", action="store_true",
                    help="Print what would change; write no files.")
    rt.set_defaults(func=_cmd_refresh_templates)

    rb = sub.add_parser("rollback", help="List checkpoints and restore one.")
    rb.add_argument("--series", default=None)
    rb.add_argument("--to", default=None, help="Checkpoint timestamp (default: interactive pick)")
    rb.add_argument("--list", action="store_true", help="List only; do not restore")
    rb.set_defaults(func=_cmd_rollback)

    ver = sub.add_parser("version", help="Print version and exit.")
    ver.set_defaults(func=lambda _args: (print(__version__), 0)[1])

    inst = sub.add_parser("install", help="Install /autonovel:* commands into a CLI runtime.")
    inst.add_argument("--only", default=None, choices=["claude", "codex", "gemini"])
    inst.add_argument("--path", default=None,
                      help="Override the install root (default: the adapter's default).")
    inst.add_argument("--pin-model", dest="pin_model", action="store_true",
                      help=("Pin each command to its per-tier model via a "
                             "`model:` frontmatter field. OFF by default: a "
                             "per-command pin silently downshifts Claude Code "
                             "users on a `[1m]` session model to the non-`[1m]` "
                             "variant of the same tier (the 1M-context billing "
                             "gate). Leave this off to let the session model win. "
                             "See docs/troubleshooting.md."))
    inst.add_argument("--no-model-pin", dest="no_model_pin", action="store_true",
                      help=("Deprecated no-op — omitting the `model:` field is "
                             "now the default. Kept so existing scripts/aliases "
                             "don't break."))
    inst.add_argument("--dry-run", dest="dry_run", action="store_true",
                      help=("Print the list of files that WOULD be written into "
                             "each detected runtime's commands directory; touch "
                             "no disk. Useful for `npx autonovel install --dry-run` "
                             "before letting the install mutate `~/.claude/`."))
    inst.set_defaults(func=_cmd_install)

    uninst = sub.add_parser("uninstall", help="Uninstall /autonovel:* commands.")
    uninst.add_argument("--only", default=None, choices=["claude", "codex", "gemini"])
    uninst.add_argument("--path", default=None)
    uninst.set_defaults(func=_cmd_uninstall)

    ai = sub.add_parser(
        "art-import",
        help="Import a user-supplied image as a typeset plate or chapter ornament.",
    )
    ai.add_argument("--file", required=True, help="Source image path (PNG/JPG/PDF/SVG/TIFF).")
    ai.add_argument("--book", default=None, help="Book short-name (defaults to inferred book).")
    ai.add_argument("--chapter", type=int, required=True, help="Anchor chapter (1-indexed).")
    ai.add_argument("--as", dest="kind", default="plate", choices=["plate", "ornament"],
                    help="`plate`: full-page captioned image (historical maps, paintings). "
                         "`ornament`: replaces the AI-generated chapter ornament.")
    ai.add_argument("--placement", default="before-chapter",
                    choices=["before-chapter", "chapter-start", "after-chapter"],
                    help="Where the plate goes relative to its chapter (plate mode only).")
    ai.add_argument("--slug", default=None, help="Slug for the registered plate (default: derived from filename).")
    ai.add_argument("--caption", default="", help="Italic caption under the plate (e.g. \"Map of Venice, c. 1500\").")
    ai.add_argument("--attribution", default="", help="Small-print credit line under the caption.")
    ai.add_argument("--force", action="store_true", help="Overwrite an existing import with the same slug or chapter.")
    ai.set_defaults(func=_cmd_art_import)

    sl = sub.add_parser("statusline", help="Print one-line status for Claude Code's status bar.")
    sl.set_defaults(func=_cmd_statusline)

    sl_setup = sub.add_parser("statusline-setup",
                              help="Wire the statusline + permissions into a series's .claude/settings.json.")
    sl_setup.add_argument("--series", default=None,
                          help="Path to the series root (default: walk up from cwd).")
    sl_setup.add_argument("--force", action="store_true",
                          help="Overwrite an existing statusLine config and skip the malformed-file guard.")
    sl_setup.set_defaults(func=_cmd_statusline_setup)

    tf = sub.add_parser("test-fixture", help="Manage genre-fixture series under tests/fixtures/.")
    tf_sub = tf.add_subparsers(dest="action", required=True)

    tf_new = tf_sub.add_parser("new", help="Scaffold a new genre fixture + smoke test.")
    tf_new.add_argument("name", help="Short fixture name, e.g. `mystery`")
    tf_new.add_argument("--genre", default=None, help="Genre label (default: same as name)")
    tf_new.add_argument("--book-name", default="book-one")
    tf_new.add_argument("--repo-root", default=None,
                        help="Override repo root (default: walk up to find tests/fixtures/)")
    tf_new.set_defaults(func=_cmd_fixture_new)

    tf_list = tf_sub.add_parser("list", help="List available fixtures.")
    tf_list.add_argument("--repo-root", default=None)
    tf_list.set_defaults(func=_cmd_fixture_list)

    tf_run = tf_sub.add_parser("run", help="Run one fixture's smoke test via pytest.")
    tf_run.add_argument("name")
    tf_run.add_argument("--repo-root", default=None)
    tf_run.add_argument("pytest_args", nargs=argparse.REMAINDER,
                        help="Extra args passed verbatim to pytest after `--`.")
    tf_run.set_defaults(func=_cmd_fixture_run)

    mech = sub.add_parser(
        "mechanical",
        help="Run a deterministic mechanical helper (slop, period-bans, apply-cuts, spine-width, audio-*, build-tex).",
        description=(
            "Forwards the rest of $ARGV to `autonovel.mechanical`'s CLI. "
            "Use `autonovel mechanical <subcmd> --help` for per-subcommand "
            "help. This is the entry point command-body authors should "
            "invoke from the `bash` tool — it survives pipx install (which "
            "isolates the `autonovel` Python module so `python -m "
            "autonovel.mechanical` does not work outside the pipx venv)."
        ),
        add_help=False,  # let mechanical.main handle --help itself
    )
    mech.add_argument("mech_args", nargs=argparse.REMAINDER)
    mech.set_defaults(func=_cmd_mechanical)

    _tc = sub.add_parser("_tail-chapter", help=argparse.SUPPRESS)
    _tc.add_argument("--book", required=True)
    _tc.add_argument("--chapter", type=int, required=True)
    _tc.add_argument("--words", type=int, default=1000,
                     help="Number of trailing words to print (default 1000).")
    _tc.set_defaults(func=_cmd_tail_chapter)

    _begin = sub.add_parser("_begin", help=argparse.SUPPRESS)
    _begin.add_argument("--command", required=True)
    _begin.add_argument("--args", default="")
    _begin.add_argument("--runtime", default="claude")
    _begin.set_defaults(func=_cmd_begin)

    _end = sub.add_parser("_end", help=argparse.SUPPRESS)
    _end.add_argument("--command", required=True)
    _end.add_argument("--args", default="")
    _end.add_argument("--status", default="ok")
    _end.add_argument("--wrote", action="append", default=[])
    # Token + cost telemetry — populated by the postamble when the
    # runtime exposes its session's usage report. All optional;
    # missing fields land as None in the command log.
    _end.add_argument("--model", default=None,
                       help="Provider model id used for this run (telemetry).")
    _end.add_argument("--tier", default=None,
                       help="Resolved model tier — heavy / standard / light / mechanical.")
    _end.add_argument("--input-tokens", dest="input_tokens", type=int, default=None)
    _end.add_argument("--output-tokens", dest="output_tokens", type=int, default=None)
    _end.add_argument("--cache-read-tokens", dest="cache_read_tokens",
                       type=int, default=None)
    _end.add_argument("--cache-creation-tokens", dest="cache_creation_tokens",
                       type=int, default=None)
    _end.add_argument("--cost-usd", dest="cost_usd", type=float, default=None,
                       help="Estimated USD cost (NOT authoritative).")
    # Sweep commands (revision-pass, draft-pass) and any postamble
    # that wants to write a custom multi-line action plan instead of
    # the auto-computed `_next_step_for(series, book)` result. Without
    # this flag, the sweep's carefully-crafted closer never makes it
    # into last-action.json — `/autonovel:next` then sees only the
    # canonical "draft N+1" step. This was the bug behind the
    # 2026-04-30 revision-pass postamble report. accepts a single
    # string with embedded newlines (the runtime quotes appropriately).
    _end.add_argument("--next-standard-step", dest="next_standard_step_override",
                       default=None,
                       help="Override the auto-computed canonical next step. "
                            "Used by sweep commands to write multi-line action "
                            "plans (verify→panel→backup closer). Pass the full "
                            "rendered text; newlines preserved.")
    _end.add_argument("--next-rationale", dest="next_rationale_override",
                       default=None,
                       help="Optional rationale shown after the canonical next "
                            "step. Defaults to the auto-computed one when "
                            "--next-standard-step is set without --next-rationale.")
    _end.set_defaults(func=_cmd_end)

    _na = sub.add_parser("_next-actions", help=argparse.SUPPRESS)
    _na.add_argument("--book", default=None,
                     help="Restrict to one book; default: every book in project.yaml.")
    _na.add_argument("--format", choices=("human", "json"), default="human",
                     help="Output format (default: human markdown).")
    _na.set_defaults(func=_cmd_next_actions)

    _sp_start = sub.add_parser("_sweep-start", help=argparse.SUPPRESS)
    _sp_start.add_argument("--command", required=True,
                            help="The sweep command name, e.g. autonovel:draft-pass.")
    _sp_start.add_argument("--book", default=None,
                            help="Book name; defaults to current book if inferable.")
    _sp_start.add_argument("--chapters", required=True,
                            help="Comma-separated chapter list, e.g. 5,6,7,8 or a range like 5-8.")
    _sp_start.set_defaults(func=_cmd_sweep_start)

    _sp_done = sub.add_parser("_sweep-mark-done", help=argparse.SUPPRESS)
    _sp_done.add_argument("--chapter", required=True, type=int)
    _sp_done.add_argument("--summary", default="")
    _sp_done.set_defaults(func=_cmd_sweep_mark_done)

    _sp_fail = sub.add_parser("_sweep-mark-fail", help=argparse.SUPPRESS)
    _sp_fail.add_argument("--chapter", required=True, type=int)
    _sp_fail.add_argument("--error", default="")
    _sp_fail.set_defaults(func=_cmd_sweep_mark_fail)

    _sp_status = sub.add_parser("_sweep-status", help=argparse.SUPPRESS)
    _sp_status.add_argument("--format", choices=("human", "json"), default="human")
    _sp_status.set_defaults(func=_cmd_sweep_status)

    _sp_clear = sub.add_parser("_sweep-clear", help=argparse.SUPPRESS)
    _sp_clear.set_defaults(func=_cmd_sweep_clear)

    _pc = sub.add_parser("_promote-canon", help=argparse.SUPPRESS)
    _pc.add_argument("--book", default=None,
                     help="Book name to promote; default: every book in project.yaml.")
    _pc.add_argument("--no-lock", action="store_true",
                     help="Do not check in-progress.lock — for use inside a sweep "
                          "subagent whose parent already holds the lock. Without this "
                          "flag the helper refuses to run when a lock is held.")
    _pc.add_argument("--dry-run", action="store_true",
                     help="Print what would be promoted without writing.")
    _pc.add_argument("--format", choices=("json", "human"), default="human",
                     help="Output format (default: human).")
    _pc.add_argument("--scope", choices=("auto", "book", "series"), default="auto",
                     help="Where survivors land. auto (default): research-cited entries → "
                          "shared/canon.md, chapter-derived entries → books/<book>/canon.md; "
                          "book / series force one target.")
    _pc.set_defaults(func=_cmd_promote_canon)

    return p


def _cmd_new_series(args: argparse.Namespace) -> int:
    parent = Path(args.dest).resolve() if args.dest else Path.cwd()
    root = parent / args.name
    try:
        result = scaffold.new_series(root, series_name=args.name, genre=args.genre)
    except scaffold.ScaffoldError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    rel = result.series.root
    print(f"Created {rel}/")
    print(f"Next: cd {rel.name} && autonovel new-book <name>")
    return 0


def _cmd_new_book(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    story_time_range: list[int] | None = None
    if args.story_time_range:
        try:
            start_s, end_s = args.story_time_range.split("-", 1)
            story_time_range = [int(start_s), int(end_s)]
        except ValueError:
            print(f"error: --story-time-range must be `START-END` e.g. `1519-1523`", file=sys.stderr)
            return 2
    try:
        result = scaffold.new_book(
            series, book_name=args.name, pov=args.pov, story_time_range=story_time_range,
            context="isolated" if args.isolated else "series",
        )
    except scaffold.ScaffoldError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"Created {result.book_root.relative_to(series.root.parent)}/")
    print(f"Edit {result.book_root.name}/seed.txt, then open the series in your runtime.")
    if args.isolated:
        print("context: isolated — this book will never read sibling-book chapters "
              "as drafting context (shared/ lore is still read).")
    from .paths import nesting_note
    note = nesting_note(series.root, args.name)
    if note:
        print(f"note: {note}")
    return 0


def _cmd_import_book(args: argparse.Namespace) -> int:
    """Import an externally-written manuscript into a book's chapters/."""
    from . import import_book as import_book_mod
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    source = Path(args.source).expanduser().resolve()
    try:
        result = import_book_mod.import_manuscript(
            series.root,
            book_name=args.name,
            source=source,
            split_on=args.split_on,
            start_at=args.start_at,
            pov=args.pov,
            keep_mode=args.keep_mode,
            overwrite_existing=args.overwrite,
            dry_run=args.dry_run,
        )
    except import_book_mod.ImportError_ as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    verb = "would write" if args.dry_run else "wrote"
    print(f"{verb} {len(result.chapters_written)} chapter file(s) "
          f"into books/{args.name}/chapters/:")
    for path in result.chapters_written:
        print(f"  + {path.relative_to(series.root)}")
    if result.skipped_existing:
        print(f"skipped (already exist; pass --overwrite to replace): "
              f"{len(result.skipped_existing)}")
        for path in result.skipped_existing:
            print(f"  · {path.relative_to(series.root)}")
    if result.mode_set == "edit-imported":
        print(
            "project.yaml: book mode set to `edit-imported`. "
            "/autonovel:draft will refuse without --force; the rest of the "
            "pipeline (evaluate / brief / revise / panel / review / typeset) "
            "treats imported chapters identically to drafted ones."
        )
    if args.reverse_engineer and not args.dry_run:
        from . import import_foundation
        book_root = series.root / "books" / args.name
        re_result = import_foundation.reverse_engineer(
            series.root, book_root, dry_run=args.dry_run,
        )
        print()
        print(f"Reverse-engineered foundation candidates: "
              f"{len(re_result.candidates)} character name(s) detected.")
        if re_result.candidates:
            for c in re_result.candidates[:10]:
                print(f"  · {c.name} ({c.occurrences}x in "
                      f"{len(c.sample_chapters)} chapter(s))")
            if len(re_result.candidates) > 10:
                print(f"  · … and {len(re_result.candidates) - 10} more "
                      f"(see `shared/characters.md`).")
        print(f"`shared/characters.md`: {re_result.characters_md_action}.")
        print()
        print("Next steps:")
        for i, step in enumerate(re_result.next_steps, 1):
            print(f"  {i}. {step}")
    elif args.reverse_engineer and args.dry_run:
        print("(--reverse-engineer is a no-op under --dry-run)")
    if args.dry_run:
        print("(dry-run — no files modified)")
    return 0


def _cmd_cost(args: argparse.Namespace) -> int:
    """Roll up token + cost figures from the series command log."""
    import json as _json
    from . import cost as cost_mod
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report = cost_mod.build_report(series.command_log_file)
    if args.format == "json":
        _json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(cost_mod.render_markdown(report))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report = status.gather(series)
    print(status.render(report))
    return 0


def _cmd_tui(args: argparse.Namespace) -> int:
    """Launch the read-only TUI."""
    from . import tui
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return tui.run_tui(series, initial_book=args.book)


def _cmd_onboard(args: argparse.Namespace) -> int:
    """Run the onboarding wizard for one book."""
    from . import onboard
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        if args.non_interactive:
            # Just print the current state without prompting.
            book_root = series.books / args.book
            if not book_root.is_dir():
                print(f"error: book {args.book!r} not found under "
                      f"{series.books}. Run `autonovel new-book "
                      f"{args.book}` first.", file=sys.stderr)
                return 2
            print(f"Series: {series.root.name}")
            print(f"Book:   {args.book}")
            seed = book_root / "seed.txt"
            print(f"Seed:   {seed.relative_to(series.root)}"
                  + (" (exists)" if seed.is_file() else " (missing)"))
            from . import project as project_mod
            cfg = project_mod.load(series.project_file)
            entry = cfg.book_by_name(args.book)
            if entry:
                print(f"Title:  {entry.title or '<unset — run /autonovel:title>'}")
                print(f"Author: {entry.author or '<unset — run autonovel onboard ' + args.book + '>'}")
            return 0
        result = onboard.run_wizard(series, args.book)
        return 0 if result is not None else 2
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


def _cmd_install_export_tools(args: argparse.Namespace) -> int:
    """Interactive installer for export-side external tools."""
    from . import install_export_tools as iet
    if args.exports:
        try:
            exports = [e.strip() for e in args.exports.split(",") if e.strip()]
        except Exception:  # noqa: BLE001
            print("error: --exports must be a comma list", file=sys.stderr)
            return 2
    else:
        # Default: every export. The user can narrow with --exports.
        exports = list(iet.EXPORT_REQUIREMENTS)
    try:
        plan = iet.plan(exports=exports)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(iet.render_plan(plan))
    if not args.apply:
        return 0
    print("\n--- applying ---\n")
    result = iet.apply(plan, confirm=not args.yes)
    print(f"\nSucceeded: {result.succeeded}")
    if result.skipped:
        print(f"Skipped: {result.skipped}")
    if result.failed:
        print(f"Failed: {result.failed}")
        return 1
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report = doctor.run(series.root, fix=args.fix)
    print(doctor.render(report))

    # `--install-missing` hands the missing export-tools subset off
    # to install_export_tools so the user can fix shell-side gaps
    # in one command instead of switching between `doctor` (reports)
    # and `install-export-tools` (acts). Tools already present on
    # PATH are skipped.
    if args.install_missing:
        from . import install_export_tools as iet
        missing = doctor.missing_export_tools()
        if not missing:
            print("\nAll declared export tools are already on PATH; "
                   "nothing to install.")
            return 0 if report.ok else 1
        # Map each missing tool back to the export(s) that need it
        # so the planner can build a focused plan.
        wanted_exports: list[str] = []
        for export, tools in iet.EXPORT_REQUIREMENTS.items():
            if any(t in missing for t in tools) and export not in wanted_exports:
                wanted_exports.append(export)
        print(f"\n--- installing missing tools "
               f"({', '.join(missing)}) ---\n")
        try:
            plan = iet.plan(exports=wanted_exports)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        # Filter the plan to ONLY the tools that are actually
        # missing. Already-present tools shouldn't trigger another
        # install pass.
        plan.selected_tools = [
            t for t in plan.selected_tools
            if t.name.lower() in {m.lower() for m in missing}
            or t.name in missing
        ]
        sys.stdout.write(iet.render_plan(plan))
        result = iet.apply(plan, confirm=not args.yes)
        if result.failed:
            print(f"\nFailed: {result.failed}")
            return 1
        if result.skipped:
            print(f"\nSkipped (user declined or no-op): {result.skipped}")
        if result.succeeded:
            print(f"\n✅ Installed: {result.succeeded}")
            print("Re-run `autonovel doctor` to confirm everything is ok.")

    return 0 if report.ok else 1


def _cmd_refresh_templates(args: argparse.Namespace) -> int:
    """Re-copy package-shipped series templates over the live series.

    Catches the bug class where a user runs `autonovel new-series`,
    a fix later lands in the package's `templates/series/typeset/`,
    and the user's series carries the stale copy forever — the
    2026-04-25 PDF running-header fix and the 2026-04-28 chapter-title
    fix were both invisible to in-flight series until refresh.
    """
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    only = tuple(args.only) if args.only else ("typeset",)
    result = scaffold.refresh_templates(series, only=only, dry_run=args.dry_run)
    verb = "would update" if args.dry_run else "updated"
    print(f"{verb}: {len(result.updated)} file(s)")
    for p in result.updated:
        print(f"  {p.relative_to(series.root)}")
    if result.unchanged:
        print(f"unchanged: {len(result.unchanged)} file(s)")
    if result.extra:
        print(f"local-only (preserved): {len(result.extra)} file(s)")
        for p in result.extra:
            print(f"  {p.relative_to(series.root)}")
    if result.skipped:
        print(f"subtrees not refreshed (use --only to include): "
              + ", ".join(c.name for c in result.skipped))
    return 0


def _cmd_rollback(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    cps = rollback.list_recent(series)
    if args.list or args.to is None:
        print(rollback.render_list(cps))
        if args.list:
            return 0
        if not cps:
            return 0
        # Interactive pick
        print("")
        try:
            choice = input(f"Roll back to which? [1-{len(cps)}, 0=cancel]: ").strip()
        except EOFError:
            print("(no input; cancelled)")
            return 0
        if not choice or choice == "0":
            print("cancelled")
            return 0
        try:
            idx = int(choice)
        except ValueError:
            print("error: not a number", file=sys.stderr)
            return 2
        if not 1 <= idx <= len(cps):
            print("error: out of range", file=sys.stderr)
            return 2
        target = cps[idx - 1]
    else:
        match = [c for c in cps if c.timestamp == args.to]
        if not match:
            print(f"error: no checkpoint with timestamp {args.to}", file=sys.stderr)
            return 2
        target = match[0]

    result = rollback.rollback_to(series, target)
    print(f"Restored from {result.restored_from} (new checkpoint {result.new_checkpoint})")
    for f in result.files_restored:
        print(f"  → {f}")
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    adapters = _select_adapters(args.only)
    if not adapters:
        print(
            "error: no known runtimes found on $PATH. Install one of:\n"
            "  - Claude Code (`claude`)\n"
            "  - OpenAI Codex (`codex`)\n"
            "  - Gemini CLI (`gemini`)\n"
            "Or pass `--only <runtime> --path <dir>` to install anyway.",
            file=sys.stderr,
        )
        return 2
    path = Path(args.path).resolve() if args.path else None
    # Default OFF: omit the `model:` pin so the session model wins (the
    # `[1m]` billing-gate fix). `--pin-model` opts back in to per-tier
    # pinning. `--no-model-pin` is now a no-op (kept for back-compat).
    pin_model = getattr(args, "pin_model", False)
    dry_run = getattr(args, "dry_run", False)
    for adapter in adapters:
        result = installer_mod.install(
            adapter, install_root=path, pin_model=pin_model,
            dry_run=dry_run,
        )
        verb = "would install" if dry_run else "installed"
        print(f"{verb} [{result.adapter_name}] → {result.install_root}")
        if pin_model:
            print("  (model: frontmatter pinned per-tier — --pin-model)")
        else:
            print("  (model: frontmatter omitted — session model wins; "
                  "--pin-model to pin per-tier)")
        for w in result.written:
            sigil = "~" if dry_run else "+"
            print(f"  {sigil} {w.relative_to(result.install_root)}")
    if dry_run:
        print("")
        print("(dry-run: no files written. Re-run without --dry-run to apply.)")
    return 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    adapters = _select_adapters(args.only)
    if not adapters:
        print("error: no runtime selected; pass --only <runtime>", file=sys.stderr)
        return 2
    path = Path(args.path).resolve() if args.path else None
    for adapter in adapters:
        result = installer_mod.uninstall(adapter, install_root=path)
        print(f"uninstalled [{result.adapter_name}] from {result.install_root}")
        for r in result.removed:
            print(f"  - {r.name}")
    return 0


def _cmd_art_import(args: argparse.Namespace) -> int:
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    book_name = args.book
    if book_name is None:
        # Walk the same inference path /autonovel:* commands use.
        from .housekeeping.lifecycle import _infer_book
        ctx = _infer_book({}, series)
        book_name = ctx.get("book")
    if book_name is None:
        print("error: --book not provided and could not be inferred. "
              "Pass --book <name> or run from a series with exactly one book.",
              file=sys.stderr)
        return 2
    book_root = series.books / book_name
    if not book_root.is_dir():
        print(f"error: book {book_name!r} not found at {book_root}", file=sys.stderr)
        return 2
    source = Path(args.file).expanduser().resolve()
    try:
        result = plates_mod.import_image(
            book_root, source,
            chapter=args.chapter,
            kind=args.kind,
            placement=args.placement,
            slug=args.slug,
            caption=args.caption,
            attribution=args.attribution,
            force=args.force,
        )
    except plates_mod.ImportError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    rel = result.installed_path.relative_to(series.root)
    verb = "Replaced" if result.overwrote else "Imported"
    print(f"{verb} {result.kind} → {rel}")
    if result.plate is not None:
        print(f"  slug: {result.plate.slug}")
        print(f"  placement: {result.plate.placement} (chapter {result.plate.chapter})")
        if result.plate.caption:
            print(f"  caption: {result.plate.caption}")
        if result.plate.attribution:
            print(f"  attribution: {result.plate.attribution}")
        manifest = book_root / "typeset" / "plates.yaml"
        print(f"  manifest: {manifest.relative_to(series.root)}")
    print("")
    print(f"Next: run /autonovel:typeset --book {book_name} to rebuild the PDF.")
    return 0


def _cmd_statusline(args: argparse.Namespace) -> int:
    return statusline_mod.main()


def _cmd_statusline_setup(args: argparse.Namespace) -> int:
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        result = statusline_setup.setup(series, force=args.force)
    except statusline_setup.SetupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    rel = result.settings_path
    verb = "Created" if result.created else "Updated"
    print(f"{verb} {rel}")
    if result.statusline_added:
        print("  + statusLine: autonovel statusline")
    else:
        print("  · statusLine already configured (use --force to overwrite)")
    if result.permissions_added:
        print(f"  + {result.permissions_added} permissions added "
              f"(scoped Bash + Read/Write/Task/WebSearch/WebFetch)")
    if result.permissions_already_present:
        print(f"  · {result.permissions_already_present} already present")
    print("")
    print("Next: restart Claude Code to pick up the new settings. After")
    print("that, autonovel commands stop prompting for tool approval, and")
    print("the status bar shows series · book · phase · lock | model · "
          "context% · cost.")
    return 0


def _cmd_fixture_new(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    try:
        result = test_fixture.new_fixture(
            args.name,
            repo_root=repo_root,
            genre=args.genre,
            book_name=args.book_name,
        )
    except test_fixture.FixtureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"Created fixture tiny-series-{result.fixture.name}/")
    print(f"  fixture:    {result.fixture.path}")
    print(f"  smoke test: {result.fixture.smoke_test_path}")
    print("")
    print(f"Next: edit the seed files, then:")
    print(f"  autonovel test-fixture run {args.name}")
    return 0


def _cmd_fixture_list(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    try:
        fixtures = test_fixture.list_fixtures(repo_root=repo_root)
    except test_fixture.FixtureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(test_fixture.render_list(fixtures))
    return 0


def _cmd_fixture_run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    extra: list[str] = list(args.pytest_args or [])
    if extra and extra[0] == "--":
        extra = extra[1:]
    try:
        rc = test_fixture.run_fixture(
            args.name,
            repo_root=repo_root,
            extra_pytest_args=extra,
        )
    except test_fixture.FixtureError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return rc


def _cmd_mechanical(args: argparse.Namespace) -> int:
    """Dispatch to autonovel.mechanical's CLI. The whole point is that
    `autonovel` is on $PATH after pipx install, while `python -m
    autonovel.mechanical` only works when `autonovel` is importable
    from the system Python — which is *not* true under pipx isolation.
    Command bodies that previously shelled to `python -m
    autonovel.mechanical` should now shell to `autonovel mechanical`."""
    from .mechanical.__main__ import main as mech_main
    return mech_main(args.mech_args)


def _cmd_tail_chapter(args: argparse.Namespace) -> int:
    """Print the last N words of a chapter file. Replaces an LLM-side
    `Read offset/limit` hack that stalled on author-testing 2026-04-25
    when the LLM's chosen line range overran EOF (e.g. asking for lines
    88-147 of a 146-line chapter, then retrying when fewer lines came
    back than expected). Deterministic, single-shot, no retries."""
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    book_root = series.books / args.book
    chapter_file = book_root / "chapters" / f"ch_{args.chapter:02d}.md"
    if not chapter_file.is_file():
        # Soft failure: prior chapter not drafted is a normal state for
        # chapter 1. Exit zero with no output so the caller falls back
        # to "no prior chapter context".
        return 0
    try:
        text = chapter_file.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: read failed: {e}", file=sys.stderr)
        return 1
    if not text.strip():
        return 0
    # Strip a leading YAML frontmatter block so we don't bleed
    # `book: foo\nchapter: 2\n...` into the continuity quote.
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:]
    words = text.split()
    n = max(1, args.words)
    tail = words[-n:] if len(words) > n else words
    sys.stdout.write(" ".join(tail))
    sys.stdout.write("\n")
    return 0


def _cmd_begin(args: argparse.Namespace) -> int:
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    # Banner: name the series root we resolved + the cwd we're running
    # from. Catches the "I launched claude from inside books/<book>"
    # mistake before the command silently fails because shared/ paths
    # look one folder too deep. Bug class observed during 2026-04-25
    # author testing — the cause was a wrong-cwd launch but the
    # symptom was a command that "ran but wrote nothing".
    import os
    cwd = Path(os.getcwd())
    series_label = series.root.name
    cwd_rel = ""
    try:
        cwd_rel = str(cwd.resolve().relative_to(series.root.resolve()))
    except ValueError:
        cwd_rel = "(outside series)"
    if cwd_rel == "." or cwd_rel == "":
        loc_hint = f"series root `{series_label}`"
    else:
        loc_hint = f"series root `{series_label}` (cwd: `{cwd_rel}`)"
    print(f"_begin: running from {loc_hint}")
    try:
        result = lifecycle.begin(args.command, args.args, runtime=args.runtime, series=series)
    except lifecycle.BeginError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 — surface a clean message for the model
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(f"_begin ok: locked as PID {result.lock_info.pid}; "
          f"checkpoint {result.checkpoint.timestamp if result.checkpoint else '(none)'}")
    if result.resolved_book is not None:
        suffix = " (inferred from last-action / single-book project)" if result.book_inferred else ""
        print(f"book: {result.resolved_book}{suffix}")
    if result.abandoned_lock is not None:
        ab = result.abandoned_lock
        print(
            f"WARNING: previous run of /{ab.command} (PID {ab.pid}, started "
            f"{ab.started_at}) ended without running its postamble. "
            f"Lock taken over. Run `/autonovel:resume` if you want to "
            f"inspect the partial state from that run."
        )
    return 0


def _cmd_end(args: argparse.Namespace) -> int:
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    result = lifecycle.end(
        args.command, args.args, status=args.status,
        wrote=list(args.wrote), series=series,
        usage={
            "model": args.model,
            "tier": args.tier,
            "input_tokens": args.input_tokens,
            "output_tokens": args.output_tokens,
            "cache_read_tokens": args.cache_read_tokens,
            "cache_creation_tokens": args.cache_creation_tokens,
            "cost_usd": args.cost_usd,
        },
        next_standard_step_override=args.next_standard_step_override,
        next_rationale_override=args.next_rationale_override,
    )
    if args.status == "ok" and result.footer:
        print(result.footer)
    else:
        print(f"_end: status={args.status}; log updated")
    return 0


def _cmd_next_actions(args: argparse.Namespace) -> int:
    """Hidden subcommand: enumerate state-aware next actions for
    /autonovel:next. Reads filesystem state directly; never replays
    last-action.json (that's a separate input, surfaced as the
    canonical pipeline action at the bottom of the output)."""
    import json as _json
    from .housekeeping import next_actions
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    actions = next_actions.enumerate_actions(series, book=args.book)
    canonical = next_actions.canonical_pipeline_action(series, book=args.book)
    if args.format == "json":
        payload = {
            "actions": [a.to_dict() for a in actions],
            "canonical": canonical.to_dict() if canonical else None,
        }
        _json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(next_actions.render_human(actions, canonical=canonical))
    return 0


def _parse_chapter_list(spec: str) -> list[int]:
    """Accept `5,6,7,8` or `5-8` or mixed `1,3,5-8,10`. Returns a
    sorted, deduplicated list. Raises ValueError on garbage input."""
    out: set[int] = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            lo, hi = token.split("-", 1)
            for i in range(int(lo), int(hi) + 1):
                out.add(i)
        else:
            out.add(int(token))
    return sorted(out)


def _cmd_sweep_start(args: argparse.Namespace) -> int:
    from .housekeeping import sweep_progress
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        chapters = _parse_chapter_list(args.chapters)
    except ValueError as e:
        print(f"error: bad --chapters value: {e}", file=sys.stderr)
        return 2
    progress = sweep_progress.start(
        series, command=args.command, book=args.book, chapters=chapters,
    )
    print(f"Sweep tracking started: {progress.command} on {chapters}")
    return 0


def _cmd_sweep_mark_done(args: argparse.Namespace) -> int:
    from .housekeeping import sweep_progress
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    progress = sweep_progress.mark_done(
        series, args.chapter, summary=args.summary,
    )
    if progress is None:
        # No sweep in flight — silent no-op so a stray call doesn't
        # fail a chapter run.
        return 0
    rem = sweep_progress.remaining(progress)
    print(f"Marked chapter {args.chapter} done. Remaining: {rem}")
    return 0


def _cmd_sweep_mark_fail(args: argparse.Namespace) -> int:
    from .housekeeping import sweep_progress
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    progress = sweep_progress.mark_failed(
        series, args.chapter, args.error,
    )
    if progress is None:
        return 0
    print(f"Marked chapter {args.chapter} failed.")
    return 0


def _cmd_sweep_status(args: argparse.Namespace) -> int:
    import json as _json
    from .housekeeping import sweep_progress
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    progress = sweep_progress.read(series)
    if progress is None:
        if args.format == "json":
            _json.dump({"in_flight": False}, sys.stdout)
            sys.stdout.write("\n")
        else:
            print("No sweep in flight.")
        return 0
    if args.format == "json":
        payload = {"in_flight": True, **progress.to_dict(),
                    "remaining": sweep_progress.remaining(progress)}
        _json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(sweep_progress.render_human(progress))
    return 0


def _cmd_sweep_clear(args: argparse.Namespace) -> int:
    from .housekeeping import sweep_progress
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sweep_progress.clear(series)
    print("Sweep tracking cleared.")
    return 0


def _cmd_canon_partition(args: argparse.Namespace) -> int:
    """Move book-scoped bullets out of shared/canon.md. See
    housekeeping/canon_partition.py."""
    import json as _json
    from . import lock as lock_mod
    from .housekeeping import canon_partition as cpart
    try:
        series = _resolve_series(args.series)
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not args.no_lock and not args.dry_run:
        info = lock_mod.read(series.lock_file)
        if info is not None and not lock_mod.is_stale(series.lock_file):
            print(
                f"error: another autonovel command is in progress "
                f"(PID {info.pid}, command {info.command!r}). "
                f"Pass --no-lock if invoking from inside that command.",
                file=sys.stderr,
            )
            return 3
    try:
        report = cpart.partition(
            series,
            to_book=args.to_book,
            move_sections=args.move_section,
            move_keys=args.move_key,
            dry_run=args.dry_run,
        )
    except (cpart.PartitionError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 4
    if args.format == "json":
        _json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(cpart.render_markdown(report))
    return 0


def _cmd_promote_canon(args: argparse.Namespace) -> int:
    """Hidden subcommand: promote pending canon entries into
    books/<book>/canon.md (chapter-derived) / shared/canon.md
    (research-cited) atomically. Slash-command body and sweep
    sub-agents both call this; --no-lock lets sweep sub-agents
    bypass the in-progress lock that the parent already holds."""
    import json as _json
    from . import lock as lock_mod, promote_canon as pc
    try:
        series = load_series()
    except SeriesNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not args.no_lock:
        # Refuse if the lock is held by another process, mirroring
        # what `_begin` would have done at the slash-command's
        # preamble. With --no-lock the caller is asserting "I know
        # the parent holds the lock; just do the file ops."
        info = lock_mod.read(series.lock_file)
        if info is not None and not lock_mod.is_stale(series.lock_file):
            print(
                f"error: another autonovel command is in progress "
                f"(PID {info.pid}, command {info.command!r}). "
                f"Pass --no-lock if invoking from inside that command's sub-agent.",
                file=sys.stderr,
            )
            return 3
    try:
        report = pc.promote(
            series,
            book=args.book,
            dry_run=args.dry_run,
            no_lock=args.no_lock,
            scope=args.scope,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 4
    if args.format == "json":
        _json.dump(report.to_dict(), sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        for br in report.books:
            print(f"book: {br.book}")
            print(f"  promoted:    {br.promoted}  (books/{br.book}/canon.md: "
                  f"{br.promoted_to_book}, shared/canon.md: {br.promoted_to_shared})")
            print(f"  duplicates:  {br.duplicates}")
            print(f"  conflicts:   {br.conflicts}")
            print(f"  supersedures: {br.supersedures}")
            for sup in br.supersedure_records:
                print(f"  superseded:  `{sup.superseded_line}` ← `{sup.new_entry.fact_text}` ({sup.rationale})")
            for cr in br.conflict_records:
                print(f"  conflict:    `{cr.candidate.fact_text}` vs `{cr.existing_line}` in {cr.existing_file}")
        if args.dry_run:
            print("(dry-run — no files written)")
    return 0


def _select_adapters(only: str | None):
    if only is not None:
        try:
            return [installer_mod.load_adapter(only)]
        except KeyError as e:
            print(f"error: {e}", file=sys.stderr)
            return []
    return [dr.adapter for dr in detect_mod.detect_all() if dr.available]


def _resolve_series(arg: str | None):
    from .paths import SeriesLayout
    if arg is not None:
        p = Path(arg)
        if p.is_dir() and (p / "project.yaml").is_file():
            return SeriesLayout(root=p.resolve())
        here = Path.cwd() / arg
        if here.is_dir() and (here / "project.yaml").is_file():
            return SeriesLayout(root=here.resolve())
    return load_series()


if __name__ == "__main__":
    raise SystemExit(main())
