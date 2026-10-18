"""`python -m autonovel.mechanical <subcmd>` — deterministic helpers for commands.

Subcommands:
  slop <path>                      JSON slop-score of a prose file.
  period-bans <path> <bans>        JSON hits of bans list against a prose file.
  apply-cuts <chapter> <cuts>      Apply a cuts.json file to a chapter in place.
  spine-width --pages N [...]      Cover canvas spec (spine + canvas + px).
  audio-validate <script> [<v>]    Validate a parsed audiobook script.
  audio-chunk <script> <voices>    Pack segments into TTS-budget chunks.
  audio-marks <rows> [--pause S]   Compute cumulative chapter marks.
  scenes <path> [--full]           Split a chapter into scenes by *** / --- breaks.
  motifs <book> [--format]         Per-chapter motif density (reads books/<book>/motifs.md).
  chapter-summary <book> [--format] One-line-per-chapter overview (date/POV/score/cast/plot).
  structure-dossier <book>         Pack outline + summaries + word counts + story_time + scores for structure-review.
  structure-validate <book|json>   Validate structure_review.json + compute the book-level stop-revising gate.
  prolepsis <book>                 Candidate narrator flash-forwards per chapter (for developmental-edit).
  story-map --book <name> [--out P]  One-page HTML story map (synopsis/threads/characters/timeline).
  impact-of <book> [--source N]    Grep chapters for tokens unique to superseded canon facts.
  diff-chapters --book B [--from R] [--to R]  Word-level HTML diff between two book versions.
  research-index <series>          Per-note metadata table for shared/research/notes/.
  resolve-image-provider [...]     Resolve image provider from CLI flag + project.yaml + default.
  build-epub-md <chapters_dir>     Concatenate ch_NN.md → one ePub-ready markdown.
  build-tex <chapters_dir> [--art] Build chapters_content.tex from md.
  build-front-matter-tex <book>    Build front_matter.tex from preface + introduction + glossary.
  build-back-matter-tex <book>     Build back_matter.tex from appendix.md.
  wikimedia-search <query>         Search Commons for public-domain images (free, no key).
  wikimedia-fetch <File:title>     Download + center-crop one Commons image.
  render-novel-tex <template> [-s KEY=V ...]  Substitute @KEY@ placeholders (safer than sed).
  typeset-filename <slug> <kind>   Print canonical timestamped + latest filenames.
  teaser-plan --length S [...]     Recommend a teaser beat/shot budget + per-role timing.
  teaser-validate <teaser.json>    Validate the shot schema (hard errors; provider clip-cap).
  teaser-critique <teaser.json>    Mechanical pre-generation critique (advisory flags).
  teaser-quality <quality.json>    Validate the interestingness scorecard + HARD quality gate.
  teaser-vo <teaser.json>          Synthesize the voiceover spine (edge = free TTS; stub = offline).
  teaser-render-prompt <t.json>    Render shot prompt markdown in the provider's dialect.
  teaser-refs-plan <teaser.json>   Plan the canonical reference image per recurring subject.
  teaser-refs <teaser.json>        Character-reference manifest + approval status (Phase 5).
  resolve-video-provider [...]     Resolve video provider from CLI + project.yaml + default.
  teaser-render <teaser.json>      Render clips via the free no-key adapter (Pollinations).
  teaser-cut-list <teaser.json>    Build an editable cut_list.json from teaser + clips on disk.
  teaser-transitions <teaser.json> Suggest scene-transition points (advisory; structured signals).
  teaser-takes <teaser.json>       List archived render takes per shot (versioned takes).
  teaser-take-pick <teaser.json>   Promote an archived take back to the latest pointer.
  teaser-reset <teaser-dir>        Archive all teaser artifacts except refs/ for a --fresh run.
  teaser-music <teaser.json>       Generate a cohesive music bed from a prompt (Phase 9).
  teaser-archive-script <file>     Timestamp-archive a script before a --force re-run (Phase 6).
  teaser-ffmpeg-cmd <cut_list>     Print the ffmpeg command that stitches the cut-list to mp4.

All subcommands print a single JSON object to stdout. Commands invoke
this via the `bash` tool, read the JSON, and fold it into their own work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audio import (
    chapter_marks,
    chunk_segments,
    format_chapter_marks_mp4chaps,
    load_script,
    validate_script,
)
from .chapter_summary import render_markdown_table, summarize_chapters
from .cliches import cliche_density, cliche_hits
from .cuts import VALID_TYPES, apply_cuts
from .epub import build_epub_md
from .back_matter import build_back_matter_tex
from .chapter_titles import (
    inspect_titles,
    render_markdown as render_chapter_titles_md,
)
from .timeline import (
    extract_in_narrative_dates,
    render_markdown as render_timeline_md,
)
from .front_matter import build_front_matter_tex
from .latex import build_chapters_tex
from .dashboard import (
    build_dashboard,
    render_markdown as render_dashboard_md,
)
from .dialogue import (
    build_report as build_dialogue_report,
    render_markdown as render_dialogue_md,
)
from .entity_track import (
    build_report as build_entity_report,
    render_markdown as render_entity_md,
)
from .impact import (
    build_impact_report,
    build_rename_verify_report,
    build_renumber_refs_report,
    build_stale_chapters_report,
    render_impact_markdown,
    render_rename_verify_markdown,
    render_renumber_refs_markdown,
    render_stale_chapters_markdown,
)
from .research_index import (
    build_index as build_research_index,
    render_markdown as render_research_index_md,
)
from .period_register import (
    build_report as build_period_report,
    build_syntax_drift_report,
    render_markdown as render_period_md,
    render_syntax_drift_markdown,
)
from .pov_bleed import (
    build_report as build_pov_bleed_report,
    render_markdown as render_pov_bleed_md,
)
from .register import (
    build_report as build_register_report,
    render_markdown as render_register_md,
)
from .series_arc import (
    build_report as build_series_arc_report,
    render_markdown as render_series_arc_md,
)
from .show_dont_tell import (
    build_report as build_show_dont_tell_report,
    render_markdown as render_show_dont_tell_md,
)
from .motifs import build_report as build_motif_report, render_markdown as render_motif_md
from .summary_query import (
    QueryError,
    filter_rows as summary_filter_rows,
    render_markdown as render_summary_query_md,
)
from .scenes import split_scenes
from .sensory import channel_balance
from .slop import period_ban_hits, slop_score
from .spine import cover_spec
from .structure_dossier import (
    build_dossier as build_structure_dossier,
    render_markdown as render_structure_dossier_md,
)
from . import structure_review as structure_review_mod
from ..export import wikimedia as wikimedia_mod
from .typeset import latest_filename, output_filename, render_novel_tex


def _cmd_slop(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    report = slop_score(text)
    json.dump(report.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_period_bans(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    bans_text = Path(args.bans_path).read_text(encoding="utf-8")
    bans = [line for line in bans_text.splitlines() if line.strip() and not line.strip().startswith("#")]
    hits = period_ban_hits(text, bans)
    json.dump({"hits": hits, "total": sum(c for _, c in hits)}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_apply_cuts(args: argparse.Namespace) -> int:
    cuts_data = json.loads(Path(args.cuts_path).read_text(encoding="utf-8"))
    cuts = cuts_data.get("cuts", [])
    overall_fat = int(cuts_data.get("overall_fat_percentage", 0))
    types = set(args.types) if args.types else None
    if types:
        invalid = types - VALID_TYPES
        if invalid:
            print(f"error: unknown types {sorted(invalid)}", file=sys.stderr)
            return 2
    stats = apply_cuts(
        Path(args.chapter_path),
        cuts,
        types=types,
        min_fat=args.min_fat,
        overall_fat_percentage=overall_fat,
        dry_run=args.dry_run,
    )
    json.dump(stats.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if stats.failed == 0 else 3


def _cmd_spine_width(args: argparse.Namespace) -> int:
    spec = cover_spec(
        trim_w=args.trim_w,
        trim_h=args.trim_h,
        pages=args.pages,
        paper=args.paper,
        bleed=args.bleed,
        dpi=args.dpi,
        spine_override=args.spine_override,
    )
    json.dump(spec.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_audio_validate(args: argparse.Namespace) -> int:
    script = load_script(Path(args.script_path))
    voices = None
    if args.voices_path:
        voices = json.loads(Path(args.voices_path).read_text(encoding="utf-8"))
    problems = validate_script(script, voices)
    json.dump(problems.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if problems.ok else 4


def _cmd_audio_chunk(args: argparse.Namespace) -> int:
    script = load_script(Path(args.script_path))
    voices = json.loads(Path(args.voices_path).read_text(encoding="utf-8"))
    chunks = chunk_segments(
        script["segments"],
        voices,
        max_chars=args.max_chars,
    )
    json.dump(
        {
            "chapter": script.get("chapter"),
            "total_chunks": len(chunks),
            "total_chars": sum(c.chars for c in chunks),
            "chunks": [c.to_dict() for c in chunks],
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_audio_marks(args: argparse.Namespace) -> int:
    rows_data = json.loads(Path(args.rows_path).read_text(encoding="utf-8"))
    rows = [(int(r["chapter"]), str(r["title"]), float(r["duration"])) for r in rows_data]
    marks = chapter_marks(rows, pause=args.pause)
    payload: dict = {"marks": [m.to_dict() for m in marks]}
    if args.format == "ffmetadata":
        payload["ffmetadata"] = format_chapter_marks_mp4chaps(marks)
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_cliches(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    hits = cliche_hits(text)
    payload = {
        "hits": [h.to_dict() for h in hits],
        "total": sum(h.count for h in hits),
        "density_per_1000_words": round(cliche_density(text), 3),
        "word_count": len(text.split()),
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_sensory(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    report = channel_balance(text, dominance_threshold=args.dominance_threshold)
    json.dump(report.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_scenes(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text(encoding="utf-8")
    scenes = split_scenes(text)
    payload = {
        "path": args.path,
        "scene_count": len(scenes),
        "total_words": sum(s["word_count"] for s in scenes),
        # `text` field is heavy and the LLM judge in evaluate.md
        # already has the chapter file open; emit only the lightweight
        # index per scene by default. `--full` opts back in to the prose.
        "scenes": [
            ({k: v for k, v in s.items() if k != "text"} if not args.full else s)
            for s in scenes
        ],
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_dialogue(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_dialogue_report(book_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_dialogue_md(report, book=book_root.name,
                                              show_hits=not args.summary_only))
    return 0


def _cmd_period_register(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    series_root = Path(args.series_root) if args.series_root else None
    report = build_period_report(book_root, series_root=series_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_period_md(report, book=book_root.name,
                                            show_hits=not args.summary_only))
    return 0


def _cmd_show_dont_tell(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_show_dont_tell_report(book_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_show_dont_tell_md(
            report, book=book_root.name,
            show_hits=not args.summary_only,
        ))
    return 0


def _cmd_vagueness(args: argparse.Namespace) -> int:
    from .vagueness import build_report as _bvr, render_markdown as _rvm
    book_root = Path(args.book_root)
    report = _bvr(book_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_rvm(report, book=book_root.name,
                              show_hits=not args.summary_only))
    return 0


def _cmd_series_arc(args: argparse.Namespace) -> int:
    series_root = Path(args.series_root)
    report = build_series_arc_report(series_root, threshold=args.threshold)
    if args.format == "json":
        json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_series_arc_md(report))
    return 0


def _cmd_register(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_register_report(
        book_root, long_utterance=args.long_utterance, chapter=args.chapter,
    )
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_register_md(
            report, book=book_root.name, show_hits=not args.summary_only,
        ))
    return 0


def _cmd_syntax_drift(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    series_root = Path(args.series_root) if args.series_root else None
    report = build_syntax_drift_report(
        book_root, series_root=series_root,
        threshold=args.threshold,
    )
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_syntax_drift_markdown(
            report, book=book_root.name,
        ))
    return 0


def _cmd_pov_bleed(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    series_root = Path(args.series_root) if args.series_root else None
    report = build_pov_bleed_report(book_root, series_root=series_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_pov_bleed_md(report, book=book_root.name,
                                               show_hits=not args.summary_only))
    return 0


def _cmd_summary_query(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    rows = summarize_chapters(book_root)
    try:
        filtered = summary_filter_rows(rows, args.where or "")
    except QueryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.format == "json":
        json.dump(
            {
                "book_root": str(book_root),
                "expr": args.where,
                "matched": len(filtered),
                "rows": [
                    {
                        "chapter": r.chapter,
                        "pov": r.pov,
                        "story_time": r.story_time,
                        "score": r.score,
                        "word_count": r.word_count,
                        "location": r.location,
                        "plot": r.plot,
                        "cast": r.cast,
                        "status": r.status,
                    } for r in filtered
                ],
            },
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_summary_query_md(
            filtered, expr=args.where, book=book_root.name,
        ))
    return 0


_CANON_DRIVEN_SOURCES = ("promote-canon", "gen-canon")
_MTIME_DRIVEN_SOURCES = (
    "voice-discovery", "add-character", "gen-characters", "gen-world",
    "add-source",
)
_RENAME_VERIFY_SOURCES = ("rename-character",)
_RENUMBER_REFS_SOURCES = ("merge-chapters", "reorder", "remove-chapter")


def _cmd_impact_of(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    series_root = Path(args.series_root) if args.series_root else None
    if args.source in _CANON_DRIVEN_SOURCES:
        report = build_impact_report(
            book_root,
            series_root=series_root,
            source_command=args.source,
        )
        if args.format == "json":
            json.dump(
                {
                    "book_root": str(book_root),
                    "series_root": str(series_root) if series_root else None,
                    "report_kind": "canon-driven",
                    **report.to_dict(),
                },
                sys.stdout, indent=2,
            )
            sys.stdout.write("\n")
        else:
            sys.stdout.write(
                render_impact_markdown(report, book=book_root.name)
            )
    elif args.source in _MTIME_DRIVEN_SOURCES:
        stale = build_stale_chapters_report(
            book_root,
            series_root=series_root,
            source_command=args.source,
        )
        if args.format == "json":
            json.dump(
                {
                    "book_root": str(book_root),
                    "series_root": str(series_root) if series_root else None,
                    "report_kind": "mtime-driven",
                    **stale.to_dict(),
                },
                sys.stdout, indent=2,
            )
            sys.stdout.write("\n")
        else:
            sys.stdout.write(
                render_stale_chapters_markdown(stale, book=book_root.name)
            )
    elif args.source in _RENAME_VERIFY_SOURCES:
        rv = build_rename_verify_report(
            book_root, series_root=series_root,
        )
        if args.format == "json":
            json.dump(
                {
                    "book_root": str(book_root),
                    "series_root": str(series_root) if series_root else None,
                    "report_kind": "rename-verify",
                    **rv.to_dict(),
                },
                sys.stdout, indent=2,
            )
            sys.stdout.write("\n")
        else:
            sys.stdout.write(
                render_rename_verify_markdown(rv, book=book_root.name)
            )
    elif args.source in _RENUMBER_REFS_SOURCES:
        rr = build_renumber_refs_report(
            book_root, series_root=series_root,
            source_command=args.source,
        )
        if args.format == "json":
            json.dump(
                {
                    "book_root": str(book_root),
                    "series_root": str(series_root) if series_root else None,
                    "report_kind": "renumber-refs",
                    **rr.to_dict(),
                },
                sys.stdout, indent=2,
            )
            sys.stdout.write("\n")
        else:
            sys.stdout.write(
                render_renumber_refs_markdown(rr, book=book_root.name)
            )
    else:
        # Should not happen given the argparse choices=, but defend
        # anyway for direct API callers.
        print(f"error: unsupported --source {args.source!r}", file=sys.stderr)
        return 2
    return 0


def _cmd_diff_chapters(args: argparse.Namespace) -> int:
    from .bookdiff import cli as _bookdiff_cli
    return _bookdiff_cli(args)


def _cmd_research_index(args: argparse.Namespace) -> int:
    series_root = Path(args.series_root)
    index = build_research_index(series_root)
    if args.format == "json":
        from .research_index import filter_index
        rows = filter_index(index, grep=args.grep, cites_match=args.cites)
        json.dump(
            {
                "series_root": str(series_root),
                "filters": {"grep": args.grep, "cites": args.cites},
                "notes": [n.to_dict() for n in rows],
                "total_notes": len(index.notes),
            },
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_research_index_md(
            index, grep=args.grep, cites_match=args.cites,
            series_root=series_root,
        ))
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_dashboard(book_root, threshold=args.threshold)
    if args.format == "json":
        json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_dashboard_md(report, threshold=args.threshold))
    return 0


def _cmd_entity_track(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    series_root = Path(args.series_root) if args.series_root else None
    report = build_entity_report(book_root, series_root=series_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_entity_md(report, book=book_root.name))
    return 0


def _cmd_motifs(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    report = build_motif_report(book_root)
    if args.format == "json":
        json.dump({"book_root": str(book_root), **report.to_dict()},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_motif_md(report, book=book_root.name))
    return 0


def _cmd_chapter_summary(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    rows = summarize_chapters(book_root)
    if args.format == "json":
        json.dump(
            {"book_root": str(book_root),
             "chapter_count": len(rows),
             "rows": [r.to_dict() for r in rows]},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown_table(rows))
    return 0


def _cmd_prolepsis(args: argparse.Namespace) -> int:
    """Candidate narrator flash-forwards per chapter. A counter for
    /autonovel:developmental-edit; candidates only, never a gate."""
    from .prolepsis import render_markdown as render_prolepsis_md, scan_book
    book_root = Path(args.book_root)
    if not (book_root / "chapters").is_dir():
        print(f"prolepsis: no chapters/ under {book_root}", file=sys.stderr)
        return 2
    report = scan_book(book_root)
    if args.format == "markdown":
        sys.stdout.write(render_prolepsis_md(report))
    else:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


def _cmd_structure_dossier(args: argparse.Namespace) -> int:
    """Data assembly for /autonovel:structure-review (and evaluate --full).
    No judgement: the LLM reviewer decides causation, escalation and
    removability; this only packs what it reads besides the prose."""
    book_root = Path(args.book_root)
    if not book_root.is_dir():
        print(f"structure-dossier: no book directory at {book_root}", file=sys.stderr)
        return 2
    dossier = build_structure_dossier(book_root)
    if args.format == "markdown":
        sys.stdout.write(render_structure_dossier_md(dossier))
    else:
        json.dump(dossier, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


def _cmd_structure_validate(args: argparse.Namespace) -> int:
    """Validate edit_logs/structure_review.json and compute the book-level
    gate. Exit 0 = valid (the gate may still BLOCK — read `gate.passes`),
    1 = invalid, 2 = missing / unreadable."""
    if getattr(args, "template", False):
        json.dump(structure_review_mod.blank_template(args.chapters or 3),
                  sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    if not args.path:
        print("structure-validate: a book directory or structure_review.json path is "
              "required (or pass --template)", file=sys.stderr)
        return 2
    target = Path(args.path)
    if target.is_dir():
        book_root = target
        path = target / "edit_logs" / "structure_review.json"
    else:
        book_root = None
        path = target
    rep = structure_review_mod.check(path, book_root=book_root)
    if args.format == "markdown":
        sys.stdout.write(structure_review_mod.render_markdown(rep, path))
    else:
        json.dump({"path": str(path), **rep.to_dict()}, sys.stdout, indent=2,
                  ensure_ascii=False)
        sys.stdout.write("\n")
    if not rep.present:
        return 2
    return 0 if rep.valid else 1


def _cmd_story_map(args: argparse.Namespace) -> int:
    """Build the story-map page. Book from a positional book dir, or
    `--book <name>` under `--series-root` (default: walk up from cwd)."""
    from .story_map import THREADS_LEDGER_HEADER, build_story_map, write_story_map
    if args.threads_template:
        sys.stdout.write(THREADS_LEDGER_HEADER.format(book=args.book or "<book>"))
        return 0
    series_root: Path | None = Path(args.series_root) if args.series_root else None
    if args.book_root:
        book_root = Path(args.book_root)
    elif args.book:
        if series_root is None:
            from ..paths import SeriesNotFound, find_series_root
            try:
                series_root = find_series_root()
            except SeriesNotFound as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
        book_root = series_root / "books" / args.book
    else:
        print("error: pass --book <name> (or a book directory)", file=sys.stderr)
        return 2
    if not book_root.is_dir():
        print(f"error: no book directory at {book_root}", file=sys.stderr)
        return 2
    sm = build_story_map(book_root, series_root=series_root)
    summary = write_story_map(sm, out=Path(args.out) if args.out else None,
                              fmt=args.format)
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_build_front_matter_tex(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    output = Path(args.output) if args.output else None
    content, titles = build_front_matter_tex(book_root, output=output)
    json.dump(
        {
            "sections": titles,
            "bytes": len(content),
            "output": str(output) if output else None,
            "wrote": output is not None and content != "",
        },
        sys.stdout, indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_wikimedia_search(args: argparse.Namespace) -> int:
    """Search Wikimedia Commons for public-domain images. Free
    no-API-key alternative to fal/replicate/openai for cover art —
    especially useful for historical fiction where a period-
    appropriate painting is on-genre."""
    candidates = wikimedia_mod.search_images(args.query, limit=args.limit)
    detailed = []
    if args.detailed:
        for c in candidates:
            details = wikimedia_mod.fetch_image_metadata(c.title)
            entry = {**c.to_dict()}
            if details is not None:
                entry["details"] = details.to_dict()
            detailed.append(entry)
    payload = {
        "query": args.query,
        "results": detailed if args.detailed else [c.to_dict() for c in candidates],
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_wikimedia_fetch(args: argparse.Namespace) -> int:
    """Download one Commons image and center-crop to target size.
    The slash-command body invokes this after the user picks one
    candidate from `wikimedia-search`."""
    details = wikimedia_mod.fetch_image_metadata(args.title)
    if details is None:
        print(f"error: no metadata for {args.title!r}", file=sys.stderr)
        return 2
    target_size = (args.width, args.height)
    try:
        result = wikimedia_mod.download_and_crop(
            details,
            target_size=target_size,
            output_path=Path(args.output),
            allow_non_pd=args.allow_non_pd,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    json.dump(result.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_timeline_extract(args: argparse.Namespace) -> int:
    """Extract in-narrative dates from chapter summaries +
    frontmatter for the appendix timeline. Pure mechanical (1) of
    the three timeline sources; (2) referenced and (3) context
    rows merge in via the slash-command body's LLM step."""
    book_root = Path(args.book_root)
    rows = extract_in_narrative_dates(book_root)
    if args.format == "json":
        json.dump(
            {
                "rows": [r.to_dict() for r in rows],
                "count": len(rows),
            },
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_timeline_md(rows))
    return 0


def _cmd_chapter_titles(args: argparse.Namespace) -> int:
    """Inspect every chapter's title status (frontmatter / heading
    fallback / missing). Used by /autonovel:next as a polish
    signal and by /autonovel:extract-chapter-titles to identify
    which chapters need backfill."""
    book_root = Path(args.book_root)
    report = inspect_titles(book_root)
    if args.format == "json":
        json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_chapter_titles_md(report))
    return 0


def _cmd_build_back_matter_tex(args: argparse.Namespace) -> int:
    book_root = Path(args.book_root)
    output = Path(args.output) if args.output else None
    content, titles = build_back_matter_tex(book_root, output=output)
    json.dump(
        {
            "sections": titles,
            "bytes": len(content),
            "output": str(output) if output else None,
            "wrote": output is not None and content != "",
        },
        sys.stdout, indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_render_novel_tex(args: argparse.Namespace) -> int:
    template = Path(args.template).read_text(encoding="utf-8")
    subs: dict[str, str] = {}
    for kv in (args.substitutions or []):
        if "=" not in kv:
            print(f"error: substitutions must be KEY=VALUE; got {kv!r}", file=sys.stderr)
            return 2
        key, _, value = kv.partition("=")
        subs[key] = value
    rendered = render_novel_tex(template, subs)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    json.dump({"output": str(output), "bytes": len(rendered),
               "substitutions_applied": sorted(subs.keys())},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _cmd_typeset_filename(args: argparse.Namespace) -> int:
    """Print the canonical timestamped filename. Used by typeset.md
    so the bash side doesn't have to do its own date math."""
    name = output_filename(args.slug, args.kind)
    latest = latest_filename(args.slug, args.kind)
    json.dump({"timestamped": name, "latest": latest},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _resolve_chapter_titles(args: argparse.Namespace) -> bool:
    """Resolve the chapter_titles flag from CLI args + project.yaml.

    Precedence (highest to lowest):
      1. `--no-chapter-titles` flag — explicit opt-out, wins.
      2. `--project-yaml <path>` — read `typeset.chapter_titles`
         (default True when missing).
      3. Default: True.
    """
    if getattr(args, "no_chapter_titles", False):
        return False
    project_yaml = getattr(args, "project_yaml", None)
    if project_yaml:
        try:
            from ..project import load as load_project
            cfg = load_project(Path(project_yaml))
            value = cfg.typeset.get("chapter_titles", True)
            return bool(value)
        except Exception:  # noqa: BLE001
            # Missing / malformed project.yaml falls back to default.
            # The typeset path will fail elsewhere if the file is
            # actually broken; here we want to be tolerant.
            return True
    return True


def _cmd_build_epub_md(args: argparse.Namespace) -> int:
    chapters_dir = Path(args.chapters_dir)
    output = Path(args.output) if args.output else None
    plates_manifest = (
        Path(args.plates_manifest) if args.plates_manifest else None
    )
    chapter_titles = _resolve_chapter_titles(args)
    content, reports = build_epub_md(
        chapters_dir, output=output, plates_manifest=plates_manifest,
        chapter_titles=chapter_titles,
    )
    json.dump(
        {
            "chapters": len(reports),
            "bytes": len(content),
            "output": str(output) if output else None,
            "reports": [
                {
                    "chapter": r.chapter,
                    "title": r.title,
                    "word_count": r.word_count,
                }
                for r in reports
            ],
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_build_tex(args: argparse.Namespace) -> int:
    chapters_dir = Path(args.chapters_dir)
    art_dir = Path(args.art_dir) if args.art_dir else None
    output = Path(args.output) if args.output else None
    plates_manifest = Path(args.plates_manifest) if args.plates_manifest else None
    plates_root = Path(args.plates_root) if args.plates_root else None
    chapter_titles = _resolve_chapter_titles(args)
    content, reports = build_chapters_tex(
        chapters_dir,
        art_dir=art_dir,
        output=output,
        plates_manifest=plates_manifest,
        plates_root=plates_root,
        chapter_titles=chapter_titles,
    )
    json.dump(
        {
            "chapters": len(reports),
            "bytes": len(content),
            "output": str(output) if output else None,
            "reports": [
                {
                    "chapter": r.chapter,
                    "title": r.title,
                    "ornament": str(r.ornament) if r.ornament else None,
                }
                for r in reports
            ],
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


_DEFAULT_IMAGE_PROVIDER = "pollinations"


def _cmd_resolve_image_provider(args: argparse.Namespace) -> int:
    """Resolve the active image provider from CLI args + project.yaml.

    Precedence (highest to lowest):
      1. `--cli-provider <X>` — explicit per-call override (the
         slash-command's `--provider` flag passed through).
      2. `project.yaml :: image.provider` — the per-series default.
      3. `pollinations` — repo-wide free-tier default.

    The slash-command body invokes:
        autonovel mechanical resolve-image-provider --project-yaml project.yaml \
            [--cli-provider <X>]
    and reads the JSON `{"provider": "<name>", "source": "cli|project.yaml|default"}`
    so the precedence rule lives in one place instead of being
    re-implemented in every art-* command body.
    """
    cli_provider = getattr(args, "cli_provider", None)
    if cli_provider:
        json.dump(
            {"provider": cli_provider, "source": "cli"},
            sys.stdout, indent=2,
        )
        sys.stdout.write("\n")
        return 0
    project_yaml = getattr(args, "project_yaml", None)
    if project_yaml:
        try:
            from ..project import load as load_project
            cfg = load_project(Path(project_yaml))
            value = cfg.image.get("provider")
            if value:
                json.dump(
                    {"provider": str(value), "source": "project.yaml"},
                    sys.stdout, indent=2,
                )
                sys.stdout.write("\n")
                return 0
        except Exception:  # noqa: BLE001
            pass
    json.dump(
        {"provider": _DEFAULT_IMAGE_PROVIDER, "source": "default"},
        sys.stdout, indent=2,
    )
    sys.stdout.write("\n")
    return 0


# --------------------------------------------------------------------------
# Movie-teaser mode (docs/prd-movie-teaser-mode.md). Mechanical only — the
# creative generation + LLM critique live in the slash-command bodies; these
# helpers plan the budget, validate the schema, and run the mechanical
# pre-generation critique so the precedence/rules live in one place.
# --------------------------------------------------------------------------


def _cmd_teaser_plan(args: argparse.Namespace) -> int:
    from ..teaser import beats as _beats
    data = _beats.plan(int(args.length), provider=getattr(args, "provider", "generic"),
                       mode=getattr(args, "mode", "short"))
    if getattr(args, "format", "json") == "human":
        st = data["structure"]
        print(f"Teaser plan — {data['mode']} · {data['length_s']}s on {data['provider']} "
              f"(clip cap {data['provider_clip_cap_s']:g}s, "
              f"native audio: {data['provider_native_audio']})")
        if data.get("warn_long_for_ai_video"):
            print("  ⚠️  >90s is long for an AI-video short — coherence degrades; "
                  "consider 45-60s or `--mode trailer`.")
        cap = f" (cap {data['shot_cap']})" if data.get("shot_cap") else ""
        print(f"  beats: ~{data['beat_target']} (range {data['beat_range'][0]}-{data['beat_range'][1]})")
        print(f"  shots: ~{data['shot_target']}{cap} (avg {data['avg_shot_s']:g}s each)")
        if data['mode'] == "short":
            print(f"  movements: {data['movements']} · VOICEOVER lines (the spine): "
                  f"~{data['voiceover_target']} · in-scene dialogue: ~{data['dialogue_target']}")
        else:
            print(f"  movements: {data['movements']} · dialogue lines to mine: ~{data['dialogue_target']}")
        print(f"  hook:       {st['hook']['seconds_each'][0]:g}-{st['hook']['seconds_each'][1]:g}s — {st['hook']['note']}")
        print(f"  escalation: {st['escalation']['seconds_each'][0]:g}-{st['escalation']['seconds_each'][1]:g}s "
              f"in {st['escalation']['movements']} movements — {st['escalation']['note']}")
        print(f"  turn:       {st['turn']['seconds'][0]:g}-{st['turn']['seconds'][1]:g}s @ {st['turn']['placement']} — {st['turn']['note']}")
        print(f"  title:      {st['title']['placement']} — {st['title']['note']}")
        print(f"  button:     {st['button']['seconds'][0]:g}-{st['button']['seconds'][1]:g}s — {st['button']['note']}")
    else:
        json.dump(data, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


def _cmd_teaser_validate(args: argparse.Namespace) -> int:
    from ..teaser import shots as _shots, providers as _prov
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-validate: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    prof = _prov.get(getattr(args, "provider", None) or teaser.provider)
    problems = _shots.validate(teaser, prof)
    if getattr(args, "format", "human") == "json":
        json.dump({"valid": not problems, "problems": problems}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if problems:
            print(f"❌ teaser invalid ({len(problems)} problem(s)):")
            for p_ in problems:
                print(f"  - {p_}")
        else:
            print(f"✅ teaser valid — {len(teaser.shots)} shots, "
                  f"{teaser.total_duration_s():g}s total on {prof.name}.")
    return 1 if problems else 0


def _cmd_teaser_critique(args: argparse.Namespace) -> int:
    from ..teaser import shots as _shots, critique as _crit, providers as _prov
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-critique: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    prof = _prov.get(getattr(args, "provider", None) or teaser.provider)
    rep = _crit.critique(teaser, prof)
    if getattr(args, "format", "human") == "json":
        json.dump(rep.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not rep.findings:
            print("✅ mechanical critique: no flags.")
        else:
            print(f"⚠️  mechanical critique: {len(rep.findings)} flag(s) "
                  f"(advisory — fix the high-value ones before generating):")
            for f in rep.findings:
                where = f.shot_id or "teaser"
                print(f"  - [{where}] {f.code}: {f.message}")
    return 0


def _cmd_teaser_quality(args: argparse.Namespace) -> int:
    """Validate a teaser quality scorecard and compute the HARD quality gate
    (Phase 11). The *scores* are authored by the LLM judge (taste is not
    mechanical); this command only checks the structure and applies the gate
    rule (overall ≥ 7 AND no dimension < 5) in one place, so the render gate
    and the commands agree. Exit 0 = PASS, 3 = BLOCK (or missing/invalid)."""
    from ..teaser import quality as _q
    if getattr(args, "template", False):
        json.dump(_q.blank_template(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if not getattr(args, "path", None):
        print("teaser-quality: a path is required (or pass --template)", file=sys.stderr)
        return 2
    # Accept either quality.json directly or a teaser.json (derive sibling).
    p = Path(args.path)
    if p.name != "quality.json":
        p = _q.quality_path(p)
    human = getattr(args, "format", "human") == "human"
    if not p.is_file():
        if human:
            print(f"⛔ quality gate: no scorecard at {p} — score the teaser first "
                  f"with /autonovel:teaser-critique (it writes quality.json).",
                  file=sys.stderr)
        else:
            json.dump({"present": False, "passes": False, "verdict": "BLOCK",
                       "reasons": ["no quality.json — score with teaser-critique"]},
                      sys.stdout, indent=2)
            sys.stdout.write("\n")
        return 3
    try:
        score = _q.load(p)
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-quality: cannot read {p}: {exc}", file=sys.stderr)
        return 2
    passes = score.passes()
    reasons = score.gate_reasons()
    if human:
        ks = score.known_scores()
        if passes:
            print(f"✅ quality gate: PASS — overall {score.overall():g}/10 "
                  f"(no dimension below {_q.DIM_MIN}).")
        else:
            print(f"⛔ quality gate: BLOCK — overall {score.overall():g}/10. "
                  f"It's not interesting enough yet:")
            for r in reasons:
                print(f"  - {r}")
            wk = ", ".join(f"{k}={v}" for k, v in score.weakest())
            print(f"  Lift the weakest first: {wk}. Run /autonovel:teaser-revise.")
        for k, _q_prompt in _q.DIMENSIONS:
            if k in ks:
                note = score.notes.get(k, "")
                print(f"    {k}: {ks[k]}/10{(' — ' + note) if note else ''}")
        if score.legibility:
            bad = score.illegible_shots()
            print(f"  viewer-blind legibility: {len(score.legibility) - len(bad)}/"
                  f"{len(score.legibility)} scenes clear"
                  f"{(' — illegible: ' + ', '.join(bad)) if bad else ''}")
            if score.would_watch is not None:
                print(f"  would a stranger watch the film? "
                      f"{'yes' if score.would_watch else 'NO'}")
            if score.viewer_takeaway.strip():
                print(f"  stranger's takeaway: {score.viewer_takeaway.strip()}")
        else:
            print("  ⚠️  no viewer-blind legibility read (the gate's un-gameable "
                  "half) — re-score with /autonovel:teaser-critique")
    else:
        out = score.to_dict()
        out.update({"present": True, "passes": passes, "reasons": reasons})
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0 if passes else 3


def _cmd_teaser_render_prompt(args: argparse.Namespace) -> int:
    from ..teaser import shots as _shots, render_prompt as _rp
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-render-prompt: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    provider = getattr(args, "provider", None) or teaser.provider
    want = getattr(args, "shot", None)
    rendered = [s for s in teaser.shots if (want is None or s.id == want)]
    if want is not None and not rendered:
        print(f"teaser-render-prompt: no shot with id {want!r}", file=sys.stderr)
        return 2
    out_dir = getattr(args, "out_dir", None)
    if out_dir:
        d = Path(out_dir)
        d.mkdir(parents=True, exist_ok=True)
        written = []
        for s in rendered:
            fn = d / f"shot_{s.id}.md"
            fn.write_text(_rp.render_markdown(s, provider), encoding="utf-8")
            written.append(str(fn))
        print(f"wrote {len(written)} shot file(s) to {out_dir}/")
        return 0
    for s in rendered:
        print(_rp.render_markdown(s, provider))
    return 0


_DEFAULT_VIDEO_PROVIDER = "grok"


def _cmd_resolve_video_provider(args: argparse.Namespace) -> int:
    """Resolve the active *video* provider from CLI args + project.yaml.

    Twin of ``resolve-image-provider`` (PRD §23). Precedence:
      1. ``--cli-provider <X>`` — explicit per-call override.
      2. ``project.yaml :: video.provider`` — the per-series default.
      3. ``grok`` — repo-wide free default video backend (native
         dialogue+music, 5 free gens/day + $25 signup, no card; needs a
         free XAI_API_KEY). Pollinations no longer offers free video, so
         it is the image/keyframe default only (resolve-image-provider).
    """
    cli_provider = getattr(args, "cli_provider", None)
    if cli_provider:
        json.dump({"provider": cli_provider, "source": "cli"}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    project_yaml = getattr(args, "project_yaml", None)
    if project_yaml:
        try:
            from ..project import load as load_project
            cfg = load_project(Path(project_yaml))
            value = cfg.video.get("provider")
            if value:
                json.dump({"provider": str(value), "source": "project.yaml"},
                          sys.stdout, indent=2)
                sys.stdout.write("\n")
                return 0
        except Exception:  # noqa: BLE001
            pass
    json.dump({"provider": _DEFAULT_VIDEO_PROVIDER, "source": "default"},
              sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _load_teaser_refs_map(teaser_path: Path, manifest: str | None) -> dict[str, list[str]]:
    """Map each shot id → an ordered list of its **approved** reference images.

    Reads the `refs.yaml` manifest (`/autonovel:teaser-refs`). For each
    subject that is **approved/locked** (the approval gate — pending
    subjects contribute nothing), the canonical realistic portrait
    ``refs/<slug>_ref.png`` is preferred over the raw approved plate
    (``ref_path``). The subject's shots come from its manifest `shots:`
    list, falling back to the auto plan (which groups shots by
    subject_name). Characters lead; locations/props follow, so the face is
    the first (primary) reference a reference-capable backend sees. Only
    images present on disk are included; paths are absolute.
    """
    from ..teaser import refs as _refs, refmanifest as _rm, shots as _shots
    base = teaser_path.resolve().parent
    man_path = Path(manifest) if manifest else base / "refs.yaml"
    if not man_path.exists():
        return {}
    try:
        man = _rm.load(man_path)
    except Exception:  # noqa: BLE001
        return {}
    # Auto plan gives subject → shot ids when a manifest entry omits `shots`.
    shots_by_slug: dict[str, list[str]] = {}
    try:
        teaser = _shots.load(teaser_path)
        for e in _refs.plan_refs(teaser, base_dir=base, include_locations=True).entries:
            shots_by_slug[_refs.slug(e.subject)] = list(e.shots)
    except Exception:  # noqa: BLE001
        pass

    out: dict[str, list[list[str]]] = {}
    for cr in man.subjects:
        if not cr.approved:  # APPROVAL GATE — only locked/approved refs flow
            continue
        slug = _refs.slug(cr.subject)
        portrait = base / "refs" / f"{slug}_ref.png"
        plate = base / cr.ref_path if cr.ref_path else None
        chosen = (portrait if portrait.exists()
                  else (plate if (plate and plate.exists()) else None))
        if chosen is None:
            continue
        sids = list(cr.shots) or shots_by_slug.get(slug, [])
        is_secondary = cr.kind in ("location", "prop")
        for sid in sids:
            out.setdefault(sid, [[], []])  # [characters, others]
            (out[sid][1] if is_secondary else out[sid][0]).append(str(chosen))
    # Flatten characters-then-others into one ordered list per shot.
    return {sid: groups[0] + groups[1] for sid, groups in out.items()}


def _load_teaser_voices_map(teaser_path: Path, manifest: str | None) -> dict[str, dict[str, str]]:
    """Map each shot id → {speaker → locked, age-resolved voice descriptor}.

    Reads `refs.yaml`; for each dialogue speaker whose character is
    **approved/locked** (the same approval gate as faces), resolves the
    voice for that shot's `story_year` (auto-aging). Only speakers with a
    descriptor are included. Empty when no manifest / no voices defined.
    """
    from ..teaser import refs as _refs, refmanifest as _rm, shots as _shots
    base = teaser_path.resolve().parent
    man_path = Path(manifest) if manifest else base / "refs.yaml"
    if not man_path.exists():
        return {}
    try:
        man = _rm.load(man_path)
        teaser = _shots.load(teaser_path)
    except Exception:  # noqa: BLE001
        return {}
    by_slug = {_refs.slug(cr.subject): cr for cr in man.subjects if cr.approved}
    out: dict[str, dict[str, str]] = {}
    for s in teaser.shots:
        speakers: dict[str, str] = {}
        for d in s.dialogue():
            spk = (d.get("speaker") or "").strip()
            if not spk:
                continue
            cr = by_slug.get(_refs.slug(spk))
            if cr is None:
                continue
            desc = cr.resolve_voice(getattr(s, "story_year", None))
            if desc:
                speakers[spk] = desc
        if speakers:
            out[s.id] = speakers
    return out


def _load_teaser_appearances_map(teaser_path: Path, manifest: str | None) -> dict[str, str]:
    """Map each shot id → its subject's age-resolved appearance string (Phase 7).

    Reads `refs.yaml`; for each shot whose named subject is **approved/locked**
    and has an `appearance_ages` ladder, resolves the appearance for that
    shot's `story_year` so the prompt text matches the age-correct reference
    image (the `appearance_override`). Empty when no manifest / no age ladders.
    """
    from ..teaser import refs as _refs, refmanifest as _rm, shots as _shots
    base = teaser_path.resolve().parent
    man_path = Path(manifest) if manifest else base / "refs.yaml"
    if not man_path.exists():
        return {}
    try:
        man = _rm.load(man_path)
        teaser = _shots.load(teaser_path)
    except Exception:  # noqa: BLE001
        return {}
    by_slug = {_refs.slug(cr.subject): cr for cr in man.subjects if cr.approved}
    out: dict[str, str] = {}
    for s in teaser.shots:
        cr = by_slug.get(_refs.slug(s.subject_name))
        if cr is None or not cr.appearance_ages:
            continue
        resolved = cr.resolve_appearance(getattr(s, "story_year", None))
        if resolved and resolved != (s.subject_appearance or "").strip():
            out[s.id] = resolved
    return out


def _cmd_teaser_render(args: argparse.Namespace) -> int:
    """Render teaser clips via the thin free render adapter (Phase 3.5).

    Stateless: builds the per-shot request plan, then (unless --dry-run)
    downloads each clip to --out-dir. No state file, no assembly.
    """
    from ..teaser import shots as _shots, render as _render
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-render: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    provider = getattr(args, "provider", None) or teaser.provider or "grok"
    # `--kind auto` (default): pick image for image-only backends
    # (pollinations), video for video backends (grok/veo/kie/...).
    kind = args.kind
    if kind == "auto":
        from ..teaser import providers as _prov
        prof = _prov.get(provider)
        kind = "image" if prof.kinds == ("image",) else "video"
    out_dir = (Path(args.out_dir) if getattr(args, "out_dir", None)
               else Path(args.path).resolve().parent / "clips")
    # Reference-image consistency: map each subject → its canonical portrait
    # (refs/<slug>_ref.png if generated, else the approved plate) from
    # refs.yaml, so a reference-capable backend keeps characters consistent.
    refs_map = None
    if getattr(args, "use_refs", False):
        refs_map = _load_teaser_refs_map(
            Path(args.path), getattr(args, "refs_manifest", None))
        if not refs_map:
            print("teaser-render: --refs given but no usable reference images "
                  "found in refs.yaml (run /autonovel:teaser-refs first).",
                  file=sys.stderr)
    kf_dir = (Path(args.keyframe_dir) if getattr(args, "keyframe_dir", None)
              else None)
    # Locked, age-resolved voices for spoken shots (video only).
    voices_map = None
    if getattr(args, "use_voices", False) and kind == "video":
        voices_map = _load_teaser_voices_map(
            Path(args.path), getattr(args, "refs_manifest", None))
        if not voices_map:
            print("teaser-render: --voices given but no approved character "
                  "voices found in refs.yaml (set `voice:`/`voice_ages:` and "
                  "approve the speakers in /autonovel:teaser-refs).",
                  file=sys.stderr)
    # Age-correct appearance text per shot (Phase 7) — applied whenever the
    # refs.yaml manifest has an appearance age ladder, so the prompt's
    # "boy of fourteen" matches the youth/elder reference actually used.
    appearances_map = _load_teaser_appearances_map(
        Path(args.path), getattr(args, "refs_manifest", None))
    reqs = _render.plan(
        teaser, provider=provider, kind=kind, out_dir=out_dir,
        width=getattr(args, "width", None), height=args.height,
        takes=args.takes, model=getattr(args, "model", None),
        only_shot=getattr(args, "shot", None),
        shot_refs=refs_map, style_override=getattr(args, "film_style", None),
        from_keyframes=getattr(args, "from_keyframes", False),
        keyframe_dir=kf_dir, shot_voices=voices_map,
        shot_appearances=appearances_map,
        score=getattr(args, "score", "native"),
    )
    if getattr(args, "shot", None) and not reqs:
        print(f"teaser-render: no shot with id {args.shot!r}", file=sys.stderr)
        return 2
    # --- Narrative gate (Phase 6, bp 12). Before spending a REAL generation,
    # refuse a teaser with no story (no dramatic question, no stakes, thin
    # dialogue/cards, …) so quota isn't wasted on a meaningless set of clips.
    # The offline `stub` backend is exempt (it validates the chain for free);
    # `--skip-narrative-gate` is the explicit override; `--shot` (single-shot
    # iteration) skips the whole-teaser gate.
    from ..teaser import critique as _crit, providers as _prov_g
    gate_fail = []
    if provider != "stub" and not getattr(args, "shot", None):
        gate_fail = _crit.story_gate_failures(_crit.critique(teaser, _prov_g.get(provider)))
    gate_override = getattr(args, "skip_narrative_gate", False)
    if gate_fail and not gate_override and not getattr(args, "dry_run", False):
        # A totally-absent spine means the teaser.json predates the Phase-6
        # storytelling pass — the cleanest fix is to regenerate it.
        no_spine = teaser.spine.is_empty()
        print("teaser-render: ⛔ narrative gate — this teaser has no story yet, so "
              "a real render would waste quota. Fix these for free, then re-run:",
              file=sys.stderr)
        for f in gate_fail:
            print(f"  - {f.code}: {f.message}", file=sys.stderr)
        if no_spine:
            print("  This teaser.json has NO `spine` block (it predates the story "
                  "pass). Regenerate it: `/autonovel:shot-prompts --book <b> --force` "
                  "(authors the spine + mines dialogue + writes cards; the old script "
                  "is archived). Or paste the spine block from teaser/critique.md into "
                  "teaser.json by hand.", file=sys.stderr)
        else:
            print("  Re-author with `/autonovel:shot-prompts --book <b> --force`, or "
                  "hand-edit teaser.json (see teaser/critique.md for the exact text).",
                  file=sys.stderr)
        print("  Validate offline anytime with `--provider stub`; override with "
              "--skip-narrative-gate. See /autonovel:teaser-critique + "
              "docs/teaser-craft.md §0.", file=sys.stderr)
        return 3
    # --- Quality gate (Phase 11). Structure isn't enough — a story-complete
    # teaser can still be boring (the user's exact complaint). Before a REAL
    # render, require an LLM interestingness scorecard (teaser/quality.json,
    # authored by teaser-critique) to clear the bar (overall ≥ 7 AND no
    # dimension < 5). Same exemptions as the narrative gate (stub / --shot /
    # --skip-narrative-gate), and only once the story gate itself is clear —
    # there's no point scoring interestingness on a teaser with no story.
    from ..teaser import quality as _q
    quality_block = False
    quality_reasons: list[str] = []
    quality_overall = None
    check_quality = (provider != "stub" and not getattr(args, "shot", None)
                     and not gate_fail and not gate_override)
    if check_quality:
        qpath = _q.quality_path(Path(args.path))
        if qpath.is_file():
            try:
                qscore = _q.load(qpath)
                quality_overall = qscore.overall()
                if not qscore.passes():
                    quality_block = True
                    quality_reasons = qscore.gate_reasons()
            except Exception:  # noqa: BLE001
                quality_block = True
                quality_reasons = [f"unreadable quality.json at {qpath}"]
        else:
            quality_block = True
            quality_reasons = ["no quality.json — score the teaser first with "
                               "/autonovel:teaser-critique (it writes the scorecard)"]
    if quality_block and not getattr(args, "dry_run", False):
        print("teaser-render: ⛔ quality gate — the teaser is structurally complete "
              "but not interesting/legible enough to spend a real render on:", file=sys.stderr)
        for r in quality_reasons:
            print(f"  - {r}", file=sys.stderr)
        print("  Fix it for free: /autonovel:teaser-critique re-scores it, then "
              "/autonovel:teaser-revise lifts the weakest dimensions (a turn, sharper "
              "dialogue, real escalation). Validate offline with `--provider stub`; "
              "override with --skip-narrative-gate. See docs/teaser-craft.md §0/§11.",
              file=sys.stderr)
        return 3
    human = getattr(args, "format", "human") == "human"
    # Surface the key/manual status of the resolved provider up front so
    # the dry-run plan honestly reports whether a live run can proceed.
    from ..teaser import providers as _prov, backends as _be
    prof = _prov.get(provider)
    manual = _be.is_manual(provider)
    key = None if (provider == "pollinations" or manual) else _be.resolve_key(
        provider, token=getattr(args, "token", None))
    key_ok = bool(key) or not prof.needs_key
    if getattr(args, "dry_run", False):
        if human:
            if gate_fail and not gate_override:
                print(f"⚠️  narrative gate would BLOCK a real render "
                      f"({len(gate_fail)} story flag(s)): "
                      f"{', '.join(f.code for f in gate_fail)} — fix or pass "
                      f"--skip-narrative-gate. See teaser-critique.")
            if quality_block:
                print(f"⚠️  quality gate would BLOCK a real render "
                      f"(overall {quality_overall if quality_overall is not None else '—'}): "
                      f"{'; '.join(quality_reasons)} — score/revise it or pass "
                      f"--skip-narrative-gate. See teaser-critique.")
            print(f"DRY RUN — {len(reqs)} request(s) ({kind}, {provider}); "
                  f"nothing downloaded:")
            if manual:
                print(f"  ⚠️  {provider} is MANUAL (GUI-only): {prof.free_note}")
            elif prof.needs_key and not key:
                print(f"  ⚠️  no API key for {provider} — "
                      f"{_be.KEY_HELP.get(provider, 'set the provider key')}")
            for r in reqs:
                print(f"  {r.shot_id} take{r.take} → {r.out_path}")
                print(f"     {r.url}")
        else:
            json.dump({"dry_run": True, "count": len(reqs),
                       "provider": provider, "kind": kind,
                       "needs_key": prof.needs_key, "key_present": bool(key),
                       "manual": manual, "free_note": prof.free_note,
                       "narrative_gate_blocks": bool(gate_fail) and not gate_override,
                       "narrative_gate_flags": [f.code for f in gate_fail],
                       "quality_gate_blocks": quality_block,
                       "quality_gate_reasons": quality_reasons,
                       "quality_overall": quality_overall,
                       "requests": [r.to_dict() for r in reqs]},
                      sys.stdout, indent=2)
            sys.stdout.write("\n")
        return 0
    results = _render.render(
        reqs, token=getattr(args, "token", None),
        delay=getattr(args, "delay", None),
        max_retries=getattr(args, "max_retries", 4),
    )
    ok = [r for r in results if r.ok]
    bad = [r for r in results if not r.ok]
    # Versioned takes (Phase 5.8): archive each successful clip into
    # <out_dir>/takes/ under a fresh take number so re-renders never
    # destroy an earlier one. The primary shot_<id>.<ext> stays "latest".
    archived = 0
    if ok and not getattr(args, "no_archive", False):
        from ..teaser import takes as _takes
        takes_dir = out_dir / "takes"
        for r in ok:
            try:
                _takes.archive_take(Path(r.out_path), takes_dir)
                archived += 1
            except Exception:  # noqa: BLE001
                pass  # archiving is best-effort; never fail a render over it
    if human:
        for r in results:
            mark = "✅" if r.ok else "❌"
            tail = f"{r.bytes} bytes" if r.ok else r.error
            print(f"  {mark} {r.shot_id} take{r.take} → {r.out_path} ({tail})")
        print(f"\n{len(ok)} rendered, {len(bad)} failed → {out_dir}/")
        if archived:
            print(f"  archived {archived} take(s) → {out_dir}/takes/ "
                  f"(earlier renders kept; promote one with teaser-take-pick)")
        if bad:
            print("Re-run teaser-render for the failed shots (free); then "
                  "critique the clips in /autonovel:teaser-render.")
    else:
        json.dump({"dry_run": False, "rendered": len(ok), "failed": len(bad),
                   "archived": archived, "out_dir": str(out_dir),
                   "results": [r.to_dict() for r in results]},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


def _cmd_teaser_takes(args: argparse.Namespace) -> int:
    """List the archived takes per shot (Phase 5.8)."""
    from ..teaser import takes as _takes
    base = Path(args.path).resolve().parent
    clips_dir = Path(args.clips_dir) if getattr(args, "clips_dir", None) else base / "clips"
    takes_dir = clips_dir / "takes"
    listing = _takes.list_takes(takes_dir)
    if getattr(args, "format", "human") == "json":
        json.dump({"takes_dir": str(takes_dir),
                   "shots": {sid: [t.to_dict() for t in ts]
                             for sid, ts in listing.items()}},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if not listing:
        print(f"No archived takes yet in {takes_dir}/ "
              f"(render some: /autonovel:teaser-render).")
        return 0
    print(f"Archived takes — {sum(len(v) for v in listing.values())} across "
          f"{len(listing)} shot(s):")
    for sid in sorted(listing):
        latest = clips_dir / f"shot_{sid}.png"
        takes = listing[sid]
        print(f"  {sid}: {len(takes)} take(s) — "
              + ", ".join(f"take{t.take} ({t.bytes}b)" for t in takes))
    print("\nPromote an earlier take to 'latest':\n"
          "  autonovel mechanical teaser-take-pick <teaser.json> --shot <id> --take <N>")
    return 0


def _cmd_teaser_take_pick(args: argparse.Namespace) -> int:
    """Promote an archived take back to the latest pointer (Phase 5.8)."""
    from ..teaser import takes as _takes
    base = Path(args.path).resolve().parent
    clips_dir = Path(args.clips_dir) if getattr(args, "clips_dir", None) else base / "clips"
    takes_dir = clips_dir / "takes"
    try:
        dest = _takes.promote_take(takes_dir, clips_dir, args.shot, args.take)
    except FileNotFoundError as exc:
        print(f"teaser-take-pick: {exc}", file=sys.stderr)
        return 2
    if getattr(args, "format", "human") == "json":
        json.dump({"shot": args.shot, "take": args.take, "latest": str(dest)},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"✅ shot {args.shot}: take {args.take} is now latest → {dest}\n"
              f"   Re-assemble to use it: /autonovel:teaser-assemble.")
    return 0


def _cmd_teaser_archive_script(args: argparse.Namespace) -> int:
    """Timestamp-archive a teaser script artifact before a --force re-run
    overwrites it (Phase 6). No-op (exit 0) if the file does not exist —
    so a first run never errors. The refs/ originals are untouched."""
    from ..teaser import takes as _takes
    archive_dir = Path(args.archive_dir) if getattr(args, "archive_dir", None) else None
    dest = _takes.archive_script(Path(args.path), archive_dir)
    if getattr(args, "format", "human") == "json":
        json.dump({"archived": str(dest) if dest else None,
                   "source": args.path}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if dest:
            print(f"🗄️  archived previous script → {dest}")
        else:
            print(f"(nothing to archive — {args.path} does not exist yet)")
    return 0


def _cmd_teaser_music(args: argparse.Namespace) -> int:
    """Generate one cohesive music bed for the teaser (Phase 9).

    Defaults the prompt to the teaser spine's `score_direction`; writes a
    versioned, never-overwritten file under `teaser/music/` (the `stub`
    provider makes a silent WAV offline so the chain works for $0). Feed the
    result to `teaser-assemble --audio <path>`."""
    from ..teaser import shots as _shots, music as _music
    from ..teaser.backends import RenderError as _RErr
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-music: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    base = Path(args.path).resolve().parent
    provider = getattr(args, "provider", "stub") or "stub"
    prompt = (getattr(args, "prompt", None)
              or (teaser.spine.score_direction or "").strip()
              or "cinematic trailer score, single building cue, no vocals")
    music_dir = (Path(args.out_dir) if getattr(args, "out_dir", None)
                 else base / "music")
    from .typeset import output_filename, latest_filename
    ext = _music.output_ext(provider)
    slug = f"{_slugify_title(teaser.title)}_bed"
    out = music_dir / output_filename(slug, ext)
    latest = music_dir / latest_filename(slug, ext)
    if getattr(args, "dry_run", False):
        need = _music.needs_key(provider)
        key = _music.music_key(provider, token=getattr(args, "token", None)) if need else None
        json.dump({"dry_run": True, "provider": provider, "prompt": prompt,
                   "needs_key": need, "key_present": bool(key),
                   "out": str(out), "duration_s": float(args.duration)},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    try:
        path = _music.generate_bed(
            prompt, out, provider=provider, duration_s=float(args.duration),
            token=getattr(args, "token", None), model=getattr(args, "model", None))
    except _RErr as exc:
        print(f"teaser-music: {exc}", file=sys.stderr)
        return 2
    import shutil as _sh
    _sh.copy2(path, latest)
    if getattr(args, "format", "human") == "json":
        json.dump({"out": str(path), "latest": str(latest), "provider": provider,
                   "prompt": prompt}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"🎵 Wrote {path} (+ {latest.name})\n"
              f"   prompt: {prompt}\n"
              f"   Lay it under the cut: /autonovel:teaser-assemble --book <b> "
              f"--audio {path}")
    return 0


def _cmd_teaser_vo(args: argparse.Namespace) -> int:
    """Synthesize the teaser's VOICEOVER spine into a narration track (P13).

    Joins the shots' `voiceover` lines (in cut order) into one script and
    renders it: `stub` = silent WAV ($0, offline); `edge` = free Microsoft
    Edge TTS (no key); `elevenlabs` = paid. Writes a versioned file under
    `teaser/vo/`; feed it to `teaser-assemble --narration <path>`."""
    from ..teaser import shots as _shots, vo as _vo
    from ..teaser.backends import RenderError as _RErr
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-vo: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    base = Path(args.path).resolve().parent
    provider = getattr(args, "provider", "stub") or "stub"
    script = _vo.narration_script(teaser)
    if not script.strip():
        print("teaser-vo: no voiceover lines in teaser.json — author the VO spine "
              "first (short mode; see /autonovel:shot-prompts).", file=sys.stderr)
        return 2
    vo_dir = (Path(args.out_dir) if getattr(args, "out_dir", None) else base / "vo")
    from .typeset import output_filename, latest_filename
    ext = _vo.output_ext(provider)
    slug = f"{_slugify_title(teaser.title)}_vo"
    out = vo_dir / output_filename(slug, ext)
    latest = vo_dir / latest_filename(slug, ext)
    est = _vo.estimate_duration_s(script)
    voice = getattr(args, "voice", None)
    if getattr(args, "dry_run", False):
        need = _vo.needs_key(provider)
        key = _vo.vo_key(provider, token=getattr(args, "token", None)) if need else None
        json.dump({"dry_run": True, "provider": provider, "needs_key": need,
                   "key_present": bool(key), "out": str(out),
                   "lines": teaser.voiceover_line_count(),
                   "estimated_narration_s": est, "cut_length_s": teaser.length_s,
                   "script": script}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    try:
        path = _vo.generate_vo(script, out, provider=provider, voice=voice,
                               token=getattr(args, "token", None),
                               model=getattr(args, "model", None))
    except _RErr as exc:
        print(f"teaser-vo: {exc}", file=sys.stderr)
        return 2
    import shutil as _sh
    _sh.copy2(path, latest)
    if getattr(args, "format", "human") == "json":
        json.dump({"out": str(path), "latest": str(latest), "provider": provider,
                   "lines": teaser.voiceover_line_count(),
                   "estimated_narration_s": est, "cut_length_s": teaser.length_s},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        warn = ""
        if teaser.length_s and est > teaser.length_s * 1.1:
            warn = (f"\n   ⚠️  narration ~{est:g}s vs cut {teaser.length_s}s — "
                    f"trim VO lines or lengthen the cut.")
        print(f"🎙️  Wrote {path} (+ {latest.name}) — {teaser.voiceover_line_count()} "
              f"lines, ~{est:g}s on {provider}.{warn}\n"
              f"   Lay it under the cut: /autonovel:teaser-assemble --book <b> "
              f"--narration {path}")
    return 0


def _cmd_teaser_reset(args: argparse.Namespace) -> int:
    """Archive every teaser artifact EXCEPT the reference images, for a clean
    --fresh run (Phase: fresh). Non-destructive: moves to teaser/reset-archive/.
    Accepts a teaser dir OR a teaser.json path."""
    from ..teaser import takes as _takes
    p = Path(args.path)
    teaser_dir = p.parent if p.suffix == ".json" else p
    if getattr(args, "dry_run", False):
        keep = set(_takes.RESET_KEEP)
        would = [e.name for e in sorted(teaser_dir.iterdir())
                 if e.name not in keep] if teaser_dir.is_dir() else []
        json.dump({"dry_run": True, "teaser_dir": str(teaser_dir),
                   "would_archive": would, "keep": list(_takes.RESET_KEEP)},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    report = _takes.reset_teaser(teaser_dir)
    if getattr(args, "format", "human") == "json":
        json.dump({"teaser_dir": str(teaser_dir), **report}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if report["archived"]:
            print(f"🧹 Fresh teaser reset — archived {len(report['archived'])} "
                  f"item(s) to {teaser_dir}/reset-archive/ "
                  f"({', '.join(report['archived'])}).")
        else:
            print(f"(nothing to archive in {teaser_dir})")
        print(f"   Kept: {', '.join(report['kept']) or '(none)'} — references "
              f"survive a fresh run.")
    return 0


def _cmd_teaser_refs_plan(args: argparse.Namespace) -> int:
    from ..teaser import shots as _shots, refs as _refs
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-refs-plan: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    base_dir = Path(args.path).resolve().parent
    refs_dir = Path(args.refs_dir) if getattr(args, "refs_dir", None) else None
    art_dir = (Path(args.art_references_dir)
               if getattr(args, "art_references_dir", None) else None)
    # When --refs-dir is given, resolve ref paths against its parent so a
    # ref_path like "refs/jakob.png" lines up with the supplied dir.
    resolve_base = refs_dir.parent if refs_dir else base_dir
    plan = _refs.plan_refs(teaser, base_dir=resolve_base, art_references_dir=art_dir,
                           include_locations=getattr(args, "with_locations", False))
    if getattr(args, "format", "human") == "json":
        json.dump(plan.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    n, miss = len(plan.entries), len(plan.missing)
    if not plan.entries:
        print("no named subjects in this teaser — nothing to anchor.")
        return 0
    print(f"Reference-image plan — {n} subject(s), {miss} missing:")
    for e in plan.entries:
        mark = "✅" if e.exists else "⬜"
        src = "" if e.source == "missing" else f" [{e.source}]"
        drift = "" if e.appearance_variants <= 1 else f" ⚠️{e.appearance_variants} appearances"
        print(f"  {mark} {e.subject} → {e.ref_path}{src} "
              f"({len(e.shots)} shot(s)){drift}")
        if e.suggested_ref:
            print(f"      ↳ reuse shared plate: {e.suggested_ref}")
    if miss:
        print(f"\nGenerate the {miss} missing reference image(s) "
              f"(art-curate / teaser-render), then re-run.")
    return 0


def _cmd_teaser_refs(args: argparse.Namespace) -> int:
    """Character-reference manifest + approval status (Phase 5).

    Merges the teaser's auto reference plan with a declared `refs.yaml`
    manifest and reports, per recurring subject: the declared source, the
    approval status, whether the plate exists on disk, and the one next
    action (declare-source / fetch-source / generate / approve / ready).
    `--init` scaffolds a starter manifest from the teaser when none exists.
    """
    from ..teaser import shots as _shots, refmanifest as _rm
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-refs: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    base = Path(args.path).resolve().parent
    manifest_path = (Path(args.manifest) if getattr(args, "manifest", None)
                     else base / "refs.yaml")
    art_dir = (Path(args.art_references_dir)
               if getattr(args, "art_references_dir", None) else None)

    if getattr(args, "init", False):
        if manifest_path.exists() and not getattr(args, "force", False):
            print(f"teaser-refs: {manifest_path} exists — pass --force to overwrite.",
                  file=sys.stderr)
            return 2
        # Non-destructive merge (data-loss fix): on --force, load the existing
        # manifest and PRESERVE every declared/locked entry — a re-scaffold
        # must never wipe hand-locked plates / approvals.
        preserve = None
        kept = 0
        if manifest_path.exists():
            try:
                preserve = _rm.load(manifest_path)
                kept = sum(1 for s in preserve.subjects if s.status in ("approved", "locked"))
            except Exception:  # noqa: BLE001
                preserve = None
        manifest = _rm.scaffold_from_teaser(
            teaser, base_dir=base, art_references_dir=art_dir,
            include_locations=getattr(args, "with_locations", False),
            preserve=preserve)
        _rm.dump(manifest, manifest_path)
        n_loc = sum(1 for s in manifest.subjects if s.kind == "location")
        extra = f" (incl. {n_loc} location(s))" if n_loc else ""
        kept_msg = (f" Preserved {kept} approved/locked entry(ies)." if kept else "")
        print(f"Scaffolded {manifest_path} — {len(manifest.subjects)} subject(s){extra}."
              f"{kept_msg} Edit each `source`/`source_ref`/`constraints`, then approve. "
              f"For period places, set a period-correct `source_ref` to dodge "
              f"anachronisms (e.g. the wooden Rialto, not the 1591 stone bridge).")
        return 0

    if manifest_path.exists():
        try:
            manifest = _rm.load(manifest_path)
        except Exception as exc:  # noqa: BLE001
            print(f"teaser-refs: cannot read {manifest_path}: {exc}", file=sys.stderr)
            return 2
    else:
        manifest = _rm.RefManifest()  # empty → every subject "declare-source"

    status = _rm.build_status(teaser, manifest, base_dir=base,
                              art_references_dir=art_dir,
                              include_locations=getattr(args, "with_locations", False))
    if getattr(args, "format", "human") == "json":
        json.dump({"manifest": str(manifest_path),
                   "manifest_exists": manifest_path.exists(),
                   **status.to_dict()}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not status.rows:
        print("no named subjects in this teaser — nothing to anchor.")
        return 0
    if not manifest_path.exists():
        print(f"No manifest yet ({manifest_path.name}). Scaffold one with "
              f"`--init`, then declare a source per subject.\n")
    _MARK = {"ready": "✅", "approve": "🟡", "fetch-source": "⬜",
             "generate": "⬜", "declare-source": "❓"}
    print(f"Character references — {len(status.ready)}/{len(status.rows)} ready:")
    for r in status.rows:
        mark = _MARK.get(r.next_action, "•")
        src = r.source if r.source != "undeclared" else "undeclared"
        ref = f" ← {r.source_ref}" if r.source_ref else ""
        drift = "" if r.appearance_variants <= 1 else f" ⚠️{r.appearance_variants} appearances"
        print(f"  {mark} {r.subject} [{src}{ref}] status={r.status} "
              f"({len(r.shots)} shot(s)){drift} → {r.next_action}")
    if status.blocked:
        print(f"\nApproval gate: {len(status.blocked)} subject(s) not yet "
              f"approved/locked. Real renders should wait until these are "
              f"locked (the offline `stub` backend is exempt).")
    return 0


def _cmd_teaser_transitions(args: argparse.Namespace) -> int:
    """Suggest where non-cut scene transitions are worth considering
    (Phase 5.7) — from structured signals (time jumps, location changes,
    pace shifts, open/close). Advisory: the artistic choice is the LLM's in
    /autonovel:teaser-assemble; this just surfaces candidates."""
    from ..teaser import shots as _shots, assemble as _asm
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-transitions: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    sugg = _asm.suggest_transitions(
        teaser, year_gap=getattr(args, "year_gap", 2.0),
        slow_ratio=getattr(args, "slow_ratio", 1.5))
    if getattr(args, "format", "human") == "json":
        json.dump({"suggestions": [s.to_dict() for s in sugg]}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if not sugg:
        print("no shots — nothing to suggest.")
        return 0
    print(f"Transition suggestions — {len(sugg)} candidate point(s) "
          f"(advisory; default elsewhere is a hard cut):")
    for s in sugg:
        where = f"{s.after_shot} → {s.into_shot}" if s.after_shot else f"open @ {s.into_shot}"
        print(f"  [{where}] {s.suggested}: {'; '.join(s.reasons)}")
    return 0


def _cmd_teaser_cut_list(args: argparse.Namespace) -> int:
    """Build an editable cut_list.json from teaser.json + the clips on
    disk (Phase 3). Plan-only — never runs ffmpeg."""
    from ..teaser import shots as _shots, assemble as _asm
    try:
        teaser = _shots.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-cut-list: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    base = Path(args.path).resolve().parent
    clips_dir = Path(args.clips_dir) if getattr(args, "clips_dir", None) else base / "clips"
    cut, missing = _asm.build_cut_list(
        teaser, clips_dir, kind=args.kind,
        width=args.width, height=args.height, fps=args.fps,
        audio_bed=getattr(args, "audio", None), take=args.take,
        audio_mode=getattr(args, "audio_mode", "auto"),
        clip_audio=getattr(args, "clip_audio", None),
        transitions=not getattr(args, "no_transitions", False),
        audio_seam_fade=getattr(args, "audio_seam_fade", 0.0),
        burn_titles=getattr(args, "burn_titles", False),
        font_file=getattr(args, "font", None),
        narration_track=getattr(args, "narration", None),
    )
    out = Path(args.out) if getattr(args, "out", None) else base / "cut_list.json"
    if not cut.entries:
        print(f"teaser-cut-list: no clips found in {clips_dir}/ "
              f"(render them first: /autonovel:teaser-render). "
              f"{len(missing)} shot(s) missing.", file=sys.stderr)
        return 2
    _asm.dump(cut, out)
    if getattr(args, "format", "human") == "json":
        json.dump({"out": str(out), "entries": len(cut.entries),
                   "total_s": cut.total_duration_s(), "missing": missing},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        breakdown = ""
        if cut.kind == "mixed":
            nv = sum(1 for e in cut.entries if e.media_kind("mixed") == "video")
            breakdown = f", {nv} video + {len(cut.entries) - nv} still"
        burn = " · titles burned-in" if cut.burn_titles else ""
        print(f"Wrote {out} — {len(cut.entries)} clip(s), "
              f"{cut.total_duration_s():g}s ({cut.kind}{breakdown}){burn}.")
        if missing:
            print(f"  ⬜ {len(missing)} shot(s) with no clip yet: {', '.join(missing)}")
    return 0


def _cmd_teaser_ffmpeg_cmd(args: argparse.Namespace) -> int:
    """Print the ffmpeg command that stitches a cut_list.json into one
    mp4. The command body runs it via the `bash` tool."""
    from ..teaser import assemble as _asm
    try:
        cut = _asm.load(Path(args.path))
    except Exception as exc:  # noqa: BLE001
        print(f"teaser-ffmpeg-cmd: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    base = Path(args.path).resolve().parent
    # Versioned output (Phase 5.8): timestamp the mp4 so a re-assemble never
    # clobbers a cut you preferred; the command body copies it to `latest`.
    latest = None
    slug = f"{_slugify_title(cut.title)}_teaser"
    if getattr(args, "out", None):
        out_path = Path(args.out)
    elif getattr(args, "versioned", False):
        from .typeset import output_filename, latest_filename
        out_path = base / output_filename(slug, "mp4")
        latest = str(base / latest_filename(slug, "mp4"))
    else:
        out_path = base / f"{slug}.mp4"
    try:
        cmd = _asm.ffmpeg_command_str(cut, out_path)
    except ValueError as exc:
        print(f"teaser-ffmpeg-cmd: {exc}", file=sys.stderr)
        return 2
    if getattr(args, "format", "human") == "json":
        payload = {"command": cmd, "out": str(out_path), "entries": len(cut.entries)}
        if latest:
            payload["latest"] = latest
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(cmd)
        if latest:
            import shlex as _shlex
            print(f"# then: cp {_shlex.quote(str(out_path))} {_shlex.quote(latest)}")
    return 0


def _teaser_audio_modes() -> tuple[str, ...]:
    from ..teaser.assemble import AUDIO_MODES
    return AUDIO_MODES


def _slugify_title(title: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "_", (title or "teaser").strip().lower())
    return s.strip("_") or "teaser"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m autonovel.mechanical")
    sub = p.add_subparsers(dest="subcmd")

    s = sub.add_parser("slop", help="Score a prose file for AI-slop patterns.")
    s.add_argument("path")
    s.set_defaults(func=_cmd_slop)

    b = sub.add_parser("period-bans", help="Count banned-word hits.")
    b.add_argument("path")
    b.add_argument("bans_path")
    b.set_defaults(func=_cmd_period_bans)

    a = sub.add_parser("apply-cuts", help="Apply a cuts.json file to a chapter in place.")
    a.add_argument("chapter_path")
    a.add_argument("cuts_path")
    a.add_argument("--types", nargs="+", choices=sorted(VALID_TYPES))
    a.add_argument("--min-fat", type=int, default=0)
    a.add_argument("--dry-run", action="store_true")
    a.set_defaults(func=_cmd_apply_cuts)

    sw = sub.add_parser("spine-width", help="Cover spine + canvas calculator.")
    sw.add_argument("--trim-w", dest="trim_w", type=float, default=5.5)
    sw.add_argument("--trim-h", dest="trim_h", type=float, default=8.5)
    sw.add_argument("--pages", type=int, required=True)
    sw.add_argument("--paper", default="cream")
    sw.add_argument("--bleed", type=float, default=0.125)
    sw.add_argument("--dpi", type=int, default=300)
    sw.add_argument("--spine-override", dest="spine_override", type=float, default=None)
    sw.set_defaults(func=_cmd_spine_width)

    av = sub.add_parser("audio-validate", help="Validate a chapter script JSON.")
    av.add_argument("script_path")
    av.add_argument("voices_path", nargs="?", default=None)
    av.set_defaults(func=_cmd_audio_validate)

    ac = sub.add_parser("audio-chunk", help="Pack script segments into TTS-budget chunks.")
    ac.add_argument("script_path")
    ac.add_argument("voices_path")
    ac.add_argument("--max-chars", dest="max_chars", type=int, default=4500)
    ac.set_defaults(func=_cmd_audio_chunk)

    am = sub.add_parser("audio-marks", help="Compute chapter timestamps.")
    am.add_argument("rows_path")
    am.add_argument("--pause", type=float, default=2.0)
    am.add_argument("--format", choices=["json", "ffmetadata"], default="json")
    am.set_defaults(func=_cmd_audio_marks)

    cl = sub.add_parser("cliches", help="Bigram-cliche scan; complements slop.")
    cl.add_argument("path")
    cl.set_defaults(func=_cmd_cliches)

    sens = sub.add_parser("sensory", help="Per-channel keyword balance (visual/auditory/...).")
    sens.add_argument("path")
    sens.add_argument("--dominance-threshold", type=float, default=0.70,
                      help="Single-channel fraction above which the channel is flagged dominant (default 0.70).")
    sens.set_defaults(func=_cmd_sensory)

    sc = sub.add_parser("scenes", help="Split a chapter into scenes by *** / --- breaks.")
    sc.add_argument("path")
    sc.add_argument("--full", action="store_true",
                    help="Include each scene's full prose in the output (heavy; default off).")
    sc.set_defaults(func=_cmd_scenes)

    mt = sub.add_parser("motifs",
                        help="Per-chapter motif density tracker (reads books/<book>/motifs.md).")
    mt.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    mt.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown table).")
    mt.set_defaults(func=_cmd_motifs)

    dlg = sub.add_parser("dialogue",
                          help="Per-chapter dialogue-mechanics linter (adverb tags, said-bookisms, stutters).")
    dlg.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    dlg.add_argument("--format", choices=("markdown", "json"), default="markdown")
    dlg.add_argument("--summary-only", action="store_true",
                      help="Skip the per-hit lines block; emit only the per-chapter table.")
    dlg.set_defaults(func=_cmd_dialogue)

    pr = sub.add_parser("period-register",
                         help="Per-chapter period-bans hits across the whole book.")
    pr.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    pr.add_argument("--series-root", default=None,
                     help="Series root for shared/period_bans.txt (default: book_root.parent.parent).")
    pr.add_argument("--format", choices=("markdown", "json"), default="markdown")
    pr.add_argument("--summary-only", action="store_true")
    pr.set_defaults(func=_cmd_period_register)

    sdt = sub.add_parser("show-dont-tell",
                          help="Per-chapter pre-flight scanner for tell-candidate lines.")
    sdt.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    sdt.add_argument("--format", choices=("markdown", "json"), default="markdown")
    sdt.add_argument("--summary-only", action="store_true",
                      help="Skip the per-line block; emit only the per-chapter table.")
    sdt.set_defaults(func=_cmd_show_dont_tell)

    vg = sub.add_parser("vagueness",
                        help="Per-chapter pre-flight scanner for vague/abstract lines "
                             "(filler nouns, empty intensifiers/evaluatives, hedges).")
    vg.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    vg.add_argument("--format", choices=("markdown", "json"), default="markdown")
    vg.add_argument("--summary-only", action="store_true",
                    help="Skip the per-line block; emit only the per-chapter table.")
    vg.set_defaults(func=_cmd_vagueness)

    sa = sub.add_parser("series-arc",
                         help="Series-arc score across ≥2 books — completion, cross-book cast, story-time discipline, unresolved threads.")
    sa.add_argument("series_root", help="Path to the series root (parent of books/).")
    sa.add_argument("--threshold", type=float, default=7.0,
                     help="Chapter score threshold for ≥thr count (default 7.0).")
    sa.add_argument("--format", choices=("markdown", "json"), default="markdown")
    sa.set_defaults(func=_cmd_series_arc)

    rg = sub.add_parser("register",
                        help="Per-chapter register markers, narration and dialogue separately: "
                             "FK grade, contraction ratio, uncontracted negatives, formal "
                             "connectives, utterance length, explaining-to-the-listener candidates.")
    rg.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    rg.add_argument("--chapter", type=int, default=None,
                    help="Scan one chapter only (default: every chapter).")
    rg.add_argument("--long-utterance", type=int, default=40,
                    help="Words per quoted utterance above which it is a candidate (default 40).")
    rg.add_argument("--format", choices=("markdown", "json"), default="markdown")
    rg.add_argument("--summary-only", action="store_true",
                    help="Skip the per-line block; emit only the per-chapter table.")
    rg.set_defaults(func=_cmd_register)

    sd = sub.add_parser("syntax-drift",
                          help="Per-chapter Flesch-Kincaid grade vs the voice file's declared band (or seed/median fallback).")
    sd.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    sd.add_argument("--series-root", default=None,
                      help="Series root (default: book_root.parent.parent).")
    sd.add_argument("--threshold", type=float, default=1.0,
                      help="Drift threshold in FK grade levels (default 1.0).")
    sd.add_argument("--format", choices=("markdown", "json"), default="markdown")
    sd.set_defaults(func=_cmd_syntax_drift)

    pb = sub.add_parser("pov-bleed",
                         help="Heuristic POV-bleed scan — flag interiority lines naming non-POV characters.")
    pb.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    pb.add_argument("--series-root", default=None,
                     help="Series root for shared/characters.md (default: book_root.parent.parent).")
    pb.add_argument("--format", choices=("markdown", "json"), default="markdown")
    pb.add_argument("--summary-only", action="store_true")
    pb.set_defaults(func=_cmd_pov_bleed)

    sq = sub.add_parser("summary-query",
                        help="Filter the chapter-summary table by a small DSL (pov / score / story_time / cast / etc.).")
    sq.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    sq.add_argument("--where", default=None,
                    help="Filter expression, e.g. 'pov == \"Lucia\" and score < 7.0'.")
    sq.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown).")
    sq.set_defaults(func=_cmd_summary_query)

    ri = sub.add_parser("research-index",
                        help='Per-note metadata table for `shared/research/notes/` (slug / title / sources / citations / words).')
    ri.add_argument("series_root", help="Path to the series root (parent of shared/).")
    ri.add_argument("--grep", default=None,
                     help="Filter to notes containing this substring (case-insensitive, full body).")
    ri.add_argument("--cites", default=None,
                     help="Filter to notes whose ## Sources block contains this substring (URL or DOI).")
    ri.add_argument("--format", choices=("markdown", "json"), default="markdown",
                     help="Output format (default: markdown).")
    ri.set_defaults(func=_cmd_research_index)

    io = sub.add_parser("impact-of",
                        help='"What should I revise after <foundation-mutation>?" — token-grep for canon supersedures, mtime-stale-detection for voice/character/world/bibliography updates.')
    io.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    io.add_argument("--series-root", default=None,
                     help="Series root for shared/canon.md (default: book_root.parent.parent).")
    io.add_argument("--source",
                     choices=(_CANON_DRIVEN_SOURCES + _MTIME_DRIVEN_SOURCES
                              + _RENAME_VERIFY_SOURCES + _RENUMBER_REFS_SOURCES),
                     default="promote-canon",
                     help="Which command's impact to analyse. Canon-driven: promote-canon, gen-canon (parse Superseded blocks). Mtime-driven: voice-discovery, add-character, gen-characters, gen-world, add-source (find chapters drafted before the foundation file's last update). Rename-verify: rename-character (grep for stragglers of the OLD name from command-log). Renumber-refs: merge-chapters, reorder, remove-chapter (grep prose for chapter-number cross-references that may now point at the wrong chapter).")
    io.add_argument("--format", choices=("markdown", "json"), default="markdown",
                     help="Output format (default: markdown).")
    io.set_defaults(func=_cmd_impact_of)

    from .bookdiff import add_arguments as _bookdiff_args
    dc = sub.add_parser("diff-chapters",
                        help="Reader-facing word-level diff between two versions of a book "
                             "(git ref / tag / checkpoint / last-read / working tree) as a "
                             "self-contained HTML page + JSON sidecar.")
    _bookdiff_args(dc)
    dc.set_defaults(func=_cmd_diff_chapters)

    db = sub.add_parser("dashboard",
                        help="Per-book dashboard re-renders eval log + augments mechanical dimensions; no LLM call.")
    db.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    db.add_argument("--threshold", type=float, default=7.0,
                    help="Chapter score threshold for sub-threshold streak (default 7.0).")
    db.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown).")
    db.set_defaults(func=_cmd_dashboard)

    et = sub.add_parser("entity-track",
                        help="Per-chapter named-entity tracker (reads books/<book>/entities.md or shared/canon.md).")
    et.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    et.add_argument("--series-root", default=None,
                    help="Series root for canon.md fallback (default: parent of book_root's parent).")
    et.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown table).")
    et.set_defaults(func=_cmd_entity_track)

    em = sub.add_parser("build-epub-md",
                        help="Concatenate ch_NN.md files into one pandoc-ready markdown; weaves in user-imported plates from plates.yaml.")
    em.add_argument("chapters_dir")
    em.add_argument("--output", default=None,
                    help="Write the combined markdown to this path; otherwise stdout-JSON only.")
    em.add_argument("--plates-manifest", dest="plates_manifest", default=None,
                    help="Path to plates.yaml — typically books/<name>/typeset/plates.yaml. "
                         "Defaults to <chapters_dir>/../typeset/plates.yaml when present.")
    em.add_argument("--project-yaml", dest="project_yaml", default=None,
                    help="Path to project.yaml. When given, `typeset.chapter_titles` "
                         "controls whether per-chapter `title:` extraction runs (default true).")
    em.add_argument("--no-chapter-titles", dest="no_chapter_titles", action="store_true",
                    help="Force numbers-only chapter rendering (overrides project.yaml).")
    em.set_defaults(func=_cmd_build_epub_md)

    cs = sub.add_parser("chapter-summary",
                        help="One-line-per-chapter overview (date / POV / score / cast / plot).")
    cs.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    cs.add_argument("--format", choices=("markdown", "json"), default="markdown",
                    help="Output format (default: markdown table).")
    cs.set_defaults(func=_cmd_chapter_summary)

    plp = sub.add_parser("prolepsis",
                         help="Candidate narrator flash-forwards per chapter (sentences that reach "
                              "past the chapter's story_time). Candidates for the editor, not a gate.")
    plp.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    plp.add_argument("--format", choices=("json", "markdown"), default="json",
                     help="Output format (default: json).")
    plp.set_defaults(func=_cmd_prolepsis)

    sdo = sub.add_parser("structure-dossier",
                         help="Pack outline + summaries + word counts + story_time + eval scores "
                              "into one JSON for /autonovel:structure-review (data only, no judgement).")
    sdo.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    sdo.add_argument("--format", choices=("json", "markdown"), default="json",
                     help="Output format (default: json).")
    sdo.set_defaults(func=_cmd_structure_dossier)

    svl = sub.add_parser("structure-validate",
                         help="Validate edit_logs/structure_review.json (shape + the rubric caps over its "
                              "own tables) and compute the book-level stop-revising gate.")
    svl.add_argument("path", nargs="?", default=None,
                     help="A book dir (reads edit_logs/structure_review.json and checks staleness "
                          "against chapters/) or a structure_review.json path.")
    svl.add_argument("--format", choices=("json", "markdown"), default="json",
                     help="Output format (default: json).")
    svl.add_argument("--template", action="store_true",
                     help="Print a blank structure_review.json skeleton and exit.")
    svl.add_argument("--chapters", type=int, default=None,
                     help="Chapter count for --template (default 3).")
    svl.set_defaults(func=_cmd_structure_validate)
    smp = sub.add_parser("story-map",
                         help="One self-contained HTML story map of a book — synopsis, "
                              "thread grid + escalation curve, characters, timeline, places.")
    smp.add_argument("book_root", nargs="?", default=None,
                     help="Path to the book dir (alternative to --book).")
    smp.add_argument("--book", default=None, help="Book short-name under <series>/books/.")
    smp.add_argument("--series-root", default=None,
                     help="Series root (default: walk up from cwd; with a book dir, its parent's parent).")
    smp.add_argument("--format", choices=("html", "json"), default="html",
                     help="html (default) writes story_map.html + story_map.json; json writes only the JSON.")
    smp.add_argument("--out", default=None,
                     help="Output path (default books/<book>/edit_logs/story_map.html; the .json sits beside it).")
    smp.add_argument("--threads-template", action="store_true",
                     help="Print the documented header for books/<book>/threads.md and exit.")
    smp.set_defaults(func=_cmd_story_map)

    fm = sub.add_parser("build-front-matter-tex",
                        help="Concatenate preface.md + introduction.md + glossary.md into front_matter.tex.")
    fm.add_argument("book_root", help="Path to the book dir (the parent of preface.md).")
    fm.add_argument("--output", default=None, help="Write to this path; otherwise stdout-JSON only.")
    fm.set_defaults(func=_cmd_build_front_matter_tex)

    tl = sub.add_parser("timeline-extract",
                        help="Mechanical pass for the appendix timeline — pulls in-narrative dates from chapter summaries + frontmatter.")
    tl.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    tl.add_argument("--format", choices=("markdown", "json"), default="markdown")
    tl.set_defaults(func=_cmd_timeline_extract)

    ct = sub.add_parser("chapter-titles",
                        help="Inspect every chapter's `title:` frontmatter (or `# Heading` fallback) and report which need backfill.")
    ct.add_argument("book_root", help="Path to the book dir (parent of chapters/).")
    ct.add_argument("--format", choices=("markdown", "json"), default="markdown")
    ct.set_defaults(func=_cmd_chapter_titles)

    bm = sub.add_parser("build-back-matter-tex",
                        help="Wrap appendix.md into back_matter.tex (post-`\\backmatter` block).")
    bm.add_argument("book_root", help="Path to the book dir (the parent of appendix.md).")
    bm.add_argument("--output", default=None, help="Write to this path; otherwise stdout-JSON only.")
    bm.set_defaults(func=_cmd_build_back_matter_tex)

    ws = sub.add_parser("wikimedia-search",
                        help="Free public-domain art via Wikimedia Commons. Search by query; print candidates as JSON.")
    ws.add_argument("query", help="Search query, e.g. 'Venice 1500 painting' or 'Jakob Fugger portrait'.")
    ws.add_argument("--limit", type=int, default=10,
                     help="Max candidates to return (default 10).")
    ws.add_argument("--detailed", action="store_true",
                     help="Also fetch full metadata for each candidate (license, dimensions, artist). Slower (one extra HTTP call per candidate) but lets the LLM judge which to download without a second round-trip.")
    ws.set_defaults(func=_cmd_wikimedia_search)

    wf = sub.add_parser("wikimedia-fetch",
                        help="Download one Wikimedia Commons image and center-crop to target size. Refuses non-PD/CC0 images by default.")
    wf.add_argument("title", help="Commons file title, e.g. `File:Jakob_Fugger_(Albrecht_Dürer).jpg`.")
    wf.add_argument("--width", type=int, required=True,
                     help="Target width in pixels.")
    wf.add_argument("--height", type=int, required=True,
                     help="Target height in pixels.")
    wf.add_argument("--output", required=True,
                     help="Output path for the cropped PNG.")
    wf.add_argument("--allow-non-pd", action="store_true",
                     help="Permit fetching non-public-domain images (CC-BY etc.). You're responsible for attribution.")
    wf.set_defaults(func=_cmd_wikimedia_fetch)

    rt = sub.add_parser("render-novel-tex",
                        help="Substitute @KEY@ placeholders in a novel.tex template (replaces fragile sed).")
    rt.add_argument("template", help="Path to the novel.tex template.")
    rt.add_argument("--output", required=True, help="Destination path for the rendered .tex.")
    rt.add_argument("--substitution", "-s", dest="substitutions", action="append",
                    help="KEY=VALUE pair. Repeat for multiple. KEY substitutes @KEY@ in the template.")
    rt.set_defaults(func=_cmd_render_novel_tex)

    tf = sub.add_parser("typeset-filename",
                        help="Print canonical typeset output filename `<slug>_<YYYYMMDD>_<HHMM>.<kind>` plus latest.")
    tf.add_argument("slug", help="Book slug (will be normalised).")
    tf.add_argument("kind", help="Extension without dot (`pdf` or `epub`).")
    tf.set_defaults(func=_cmd_typeset_filename)

    bt = sub.add_parser("build-tex", help="Build chapters_content.tex from a chapters dir.")
    bt.add_argument("chapters_dir")
    bt.add_argument("--art-dir", dest="art_dir", default=None)
    bt.add_argument("--output", default=None)
    bt.add_argument("--plates-manifest", dest="plates_manifest", default=None,
                    help="Path to plates.yaml; user-supplied images get woven in.")
    bt.add_argument("--plates-root", dest="plates_root", default=None,
                    help="Base directory plate `file:` paths are resolved against "
                         "(default: parent of --plates-manifest).")
    bt.add_argument("--project-yaml", dest="project_yaml", default=None,
                    help="Path to project.yaml. When given, `typeset.chapter_titles` "
                         "controls whether per-chapter `title:` extraction runs (default true).")
    bt.add_argument("--no-chapter-titles", dest="no_chapter_titles", action="store_true",
                    help="Force numbers-only chapter rendering (overrides project.yaml).")
    bt.set_defaults(func=_cmd_build_tex)

    rip = sub.add_parser("resolve-image-provider",
                          help="Resolve the active image provider from CLI override + project.yaml + default.")
    rip.add_argument("--project-yaml", dest="project_yaml", default=None,
                     help="Path to project.yaml (typically `project.yaml`). "
                          "When set, `image.provider` is the per-series default.")
    rip.add_argument("--cli-provider", dest="cli_provider", default=None,
                     help="Explicit per-call provider (the slash-command's --provider). Wins over project.yaml.")
    rip.set_defaults(func=_cmd_resolve_image_provider)

    # --- movie-teaser mode (Phase 1) ---
    tpl = sub.add_parser("teaser-plan",
                         help="Recommend a beat/shot budget + per-role timing for a teaser length.")
    tpl.add_argument("--length", type=int, required=True, help="Teaser length in seconds.")
    tpl.add_argument("--provider", default="generic", help="Target video provider (clip cap shapes the budget).")
    tpl.add_argument("--mode", choices=["short", "trailer"], default="short",
                     help="short (45-60s VO-spine micro-story; default) | trailer (longer montage).")
    tpl.add_argument("--format", choices=["json", "human"], default="json")
    tpl.set_defaults(func=_cmd_teaser_plan)

    tvl = sub.add_parser("teaser-validate",
                         help="Validate a teaser.json against the shot schema (hard structural errors).")
    tvl.add_argument("path", help="Path to teaser.json.")
    tvl.add_argument("--provider", default=None, help="Override the provider for the clip-cap check.")
    tvl.add_argument("--format", choices=["json", "human"], default="human")
    tvl.set_defaults(func=_cmd_teaser_validate)

    tcr = sub.add_parser("teaser-critique",
                         help="Mechanical pre-generation critique of a teaser.json (advisory flags).")
    tcr.add_argument("path", help="Path to teaser.json.")
    tcr.add_argument("--provider", default=None)
    tcr.add_argument("--format", choices=["json", "human"], default="human")
    tcr.set_defaults(func=_cmd_teaser_critique)

    tql = sub.add_parser("teaser-quality",
                         help="Validate a teaser quality scorecard + compute the HARD "
                              "quality gate (Phase 11; exit 3 = BLOCK/missing).")
    tql.add_argument("path", nargs="?", default=None,
                     help="Path to quality.json (or teaser.json — derives the sibling).")
    tql.add_argument("--template", action="store_true",
                     help="Print a blank scorecard scaffold (all dimensions, 0=un-scored).")
    tql.add_argument("--format", choices=["json", "human"], default="human")
    tql.set_defaults(func=_cmd_teaser_quality)

    trp = sub.add_parser("teaser-render-prompt",
                         help="Render a shot's provider-ready prompt markdown from teaser.json.")
    trp.add_argument("path", help="Path to teaser.json.")
    trp.add_argument("--shot", default=None, help="Render only this shot id (default: all).")
    trp.add_argument("--provider", default=None)
    trp.add_argument("--out-dir", dest="out_dir", default=None,
                     help="Write each shot to <out-dir>/shot_<id>.md instead of stdout.")
    trp.set_defaults(func=_cmd_teaser_render_prompt)

    # --- movie-teaser mode (Phase 2: reference-image consistency) ---
    trf = sub.add_parser("teaser-refs-plan",
                         help="Plan the canonical reference image per recurring subject "
                              "(which shots use each, which already exist on disk).")
    trf.add_argument("path", help="Path to teaser.json.")
    trf.add_argument("--refs-dir", dest="refs_dir", default=None,
                     help="Reference-image dir (default: <teaser.json dir>/refs). "
                          "ref paths are tested for existence here.")
    trf.add_argument("--art-references-dir", dest="art_references_dir", default=None,
                     help="Optional shared plate library (e.g. shared/art_references/) "
                          "used as a fallback source for an existing reference.")
    trf.add_argument("--with-locations", dest="with_locations", action="store_true",
                     help="Also plan a reference plate per distinct setting/location "
                          "(Phase 7) — period-correct place plates to dodge anachronisms.")
    trf.add_argument("--format", choices=["json", "human"], default="human")
    trf.set_defaults(func=_cmd_teaser_refs_plan)

    # --- movie-teaser mode (Phase 5: character-reference manifest + approval) ---
    trfm = sub.add_parser("teaser-refs",
                          help="Character-reference manifest + approval status: declared "
                               "source per subject, approval gate, next action. --init "
                               "scaffolds refs.yaml from the teaser.")
    trfm.add_argument("path", help="Path to teaser.json.")
    trfm.add_argument("--manifest", default=None,
                      help="Path to refs.yaml (default: <teaser.json dir>/refs.yaml).")
    trfm.add_argument("--art-references-dir", dest="art_references_dir", default=None,
                      help="Optional shared plate library (e.g. shared/art_references/).")
    trfm.add_argument("--init", action="store_true",
                      help="Scaffold a starter refs.yaml from the teaser (one pending "
                           "subject each) instead of reporting status.")
    trfm.add_argument("--force", action="store_true",
                      help="With --init, overwrite an existing refs.yaml.")
    trfm.add_argument("--with-locations", dest="with_locations", action="store_true",
                      help="Also scaffold/track a reference plate per distinct "
                           "setting/location (Phase 7) — period-correct place plates "
                           "to dodge anachronisms.")
    trfm.add_argument("--format", choices=["json", "human"], default="human")
    trfm.set_defaults(func=_cmd_teaser_refs)

    # --- movie-teaser mode (Phase 3.5: free render adapter) ---
    rvp = sub.add_parser("resolve-video-provider",
                         help="Resolve the active video provider from CLI override + "
                              "project.yaml (video.provider) + default (pollinations).")
    rvp.add_argument("--project-yaml", dest="project_yaml", default=None,
                     help="Path to project.yaml; `video.provider` is the per-series default.")
    rvp.add_argument("--cli-provider", dest="cli_provider", default=None,
                     help="Explicit per-call provider (wins over project.yaml).")
    rvp.set_defaults(func=_cmd_resolve_video_provider)

    tre = sub.add_parser("teaser-render",
                         help="Render teaser clips. Default video backend is "
                              "grok (free dialogue+music, no card); pollinations "
                              "is the free keyframe-image backend. Stateless "
                              "create→poll→download; --dry-run builds the plan "
                              "(and reports key status) without spending anything.")
    tre.add_argument("path", help="Path to teaser.json.")
    tre.add_argument("--out-dir", dest="out_dir", default=None,
                     help="Where clips land (default: <teaser.json dir>/clips).")
    tre.add_argument("--provider", default=None,
                     help="Provider (default: teaser.json provider, else grok). "
                          "One of: gemini grok kie veo magichour fal flow "
                          "pollinations. gemini = reference-conditioned photoreal "
                          "image keyframes (Nano Banana).")
    tre.add_argument("--kind", choices=["auto", "image", "video"], default="auto",
                     help="auto = image for image-only backends (gemini/"
                          "pollinations), video for video backends (default); "
                          "or force image|video.")
    tre.add_argument("--refs", dest="use_refs", action="store_true",
                     help="Condition each shot on its subject's canonical "
                          "reference portrait from refs.yaml (gemini/fal/"
                          "pollinations-kontext) so characters stay consistent.")
    tre.add_argument("--refs-manifest", dest="refs_manifest", default=None,
                     help="Path to refs.yaml (default: <teaser.json dir>/refs.yaml).")
    tre.add_argument("--film-style", dest="film_style", default=None,
                     help="Replace each shot's `style` text with this string in "
                          "the prompt (e.g. a photoreal cinematic look for the "
                          "movie path, without touching teaser.json).")
    tre.add_argument("--voices", dest="use_voices", action="store_true",
                     help="Inject each speaker's locked, age-resolved voice "
                          "descriptor (refs.yaml `voice`/`voice_ages`, picked by "
                          "the shot's story_year) into the video prompt so the "
                          "voice holds scene-to-scene. Video only; approval-gated.")
    tre.add_argument("--from-keyframes", dest="from_keyframes", action="store_true",
                     help="Image-to-video: animate each shot from its existing "
                          "keyframe (shot_<id>.png) as the start frame "
                          "(grok/veo/kie). Use after a --kind image pass.")
    tre.add_argument("--keyframe-dir", dest="keyframe_dir", default=None,
                     help="Where the keyframes live for --from-keyframes "
                          "(default: the clips/out dir).")
    tre.add_argument("--shot", default=None, help="Render only this shot id.")
    tre.add_argument("--takes", type=int, default=1, help="Takes per shot (default 1).")
    tre.add_argument("--width", type=int, default=None,
                     help="Override width (default: derived from aspect ratio).")
    tre.add_argument("--height", type=int, default=480,
                     help="Output height in px (default 480 — low-res dev pass).")
    tre.add_argument("--model", default=None, help="Optional backend model hint.")
    tre.add_argument("--token", default=None,
                     help="Explicit provider API key/token (wins over env/.env).")
    tre.add_argument("--delay", type=float, default=None,
                     help="Seconds between requests (default: provider's polite "
                          "interval). Backoff on 429/503 is automatic.")
    tre.add_argument("--max-retries", dest="max_retries", type=int, default=4,
                     help="Max retries on transient 429/503 (default 4).")
    tre.add_argument("--no-archive", dest="no_archive", action="store_true",
                     help="Don't archive each render into clips/takes/ "
                          "(default: keep every take so an earlier one survives).")
    tre.add_argument("--score", choices=["native", "bed", "none"], default="native",
                     help="Background-MUSIC policy for video (5.9): native = let "
                          "the model score each clip; bed/none = tell it to add NO "
                          "score (diegetic sound only) so a single teaser-wide bed "
                          "carries the music (bed) or it stays scoreless (none). "
                          "Dialogue/SFX/ambience are unaffected.")
    tre.add_argument("--skip-narrative-gate", dest="skip_narrative_gate",
                     action="store_true",
                     help="Override the Phase-6 narrative gate (bp 12): render even "
                          "when the teaser has no story spine / thin dialogue. The "
                          "gate never blocks `--provider stub` or `--shot` runs.")
    tre.add_argument("--dry-run", dest="dry_run", action="store_true",
                     help="Build + print the request plan; download nothing.")
    tre.add_argument("--format", choices=["json", "human"], default="human")
    tre.set_defaults(func=_cmd_teaser_render)

    # --- movie-teaser mode (Phase 3: ffmpeg assembly) ---
    tcl = sub.add_parser("teaser-cut-list",
                         help="Build an editable cut_list.json from teaser.json + the "
                              "rendered clips on disk (plan only; never runs ffmpeg).")
    tcl.add_argument("path", help="Path to teaser.json.")
    tcl.add_argument("--clips-dir", dest="clips_dir", default=None,
                     help="Where the clips live (default: <teaser.json dir>/clips).")
    tcl.add_argument("--kind", choices=["image", "video", "mixed"], default="image",
                     help="image = still-image slideshow (default); video = clips; "
                          "mixed (Phase 8) = per shot, the video clip if present "
                          "(native audio) else the still keyframe (silent).")
    tcl.add_argument("--audio", default=None, help="Optional audio-bed file to mix in.")
    tcl.add_argument("--narration", default=None,
                     help="Optional VOICEOVER narration track (from teaser-vo) laid on "
                          "top as the primary voice; a music bed ducks under it (Phase 13).")
    tcl.add_argument("--audio-mode", dest="audio_mode",
                     choices=list(_teaser_audio_modes()), default="auto",
                     help="How clip audio + the bed combine (default auto): "
                          "duck = music ducks under dialogue; mix = equal; "
                          "clip-only = keep native dialogue, no bed; bed-only; none.")
    tcl.add_argument("--clip-audio", dest="clip_audio", action="store_true",
                     default=None, help="Declare the video clips DO carry native "
                          "audio (grok/veo/kie). Default: inferred from --kind.")
    tcl.add_argument("--no-clip-audio", dest="clip_audio", action="store_false",
                     help="Declare the clips are SILENT (e.g. magichour/stub).")
    tcl.add_argument("--fps", type=int, default=30)
    tcl.add_argument("--width", type=int, default=854)
    tcl.add_argument("--height", type=int, default=480)
    tcl.add_argument("--take", type=int, default=1, help="Which take to use per shot.")
    tcl.add_argument("--no-transitions", dest="no_transitions", action="store_true",
                     help="Disable the safe transition defaults (first→fade-in, "
                          "last→fade-out, title→fade); everything stays a hard cut.")
    tcl.add_argument("--audio-seam-fade", dest="audio_seam_fade", type=float, default=0.0,
                     help="Seconds of audio fade-in/out per clip at cut boundaries "
                          "(5.9) — softens per-clip native music pops on the "
                          "`--score native` path. 0 = off (default).")
    tcl.add_argument("--burn-titles", dest="burn_titles", action="store_true",
                     help="Burn the text cards into the picture with ffmpeg drawtext "
                          "(Phase 8; opt-in — default is to add them in an editor). "
                          "Title-role cards center large; others ride the lower third.")
    tcl.add_argument("--font", default=None,
                     help="Font file (.ttf/.otf) for --burn-titles, e.g. an EB "
                          "Garamond path. Omit to use ffmpeg's default (needs fontconfig).")
    tcl.add_argument("--out", default=None, help="Output path (default: <dir>/cut_list.json).")
    tcl.add_argument("--format", choices=["json", "human"], default="human")
    tcl.set_defaults(func=_cmd_teaser_cut_list)

    ttk = sub.add_parser("teaser-takes",
                         help="List archived render takes per shot (Phase 5.8).")
    ttk.add_argument("path", help="Path to teaser.json (clips dir = <dir>/clips).")
    ttk.add_argument("--clips-dir", dest="clips_dir", default=None,
                     help="Clips dir (default: <teaser.json dir>/clips).")
    ttk.add_argument("--format", choices=["json", "human"], default="human")
    ttk.set_defaults(func=_cmd_teaser_takes)

    tkp = sub.add_parser("teaser-take-pick",
                         help="Promote an archived take back to the latest "
                              "pointer so the next assemble uses it (Phase 5.8).")
    tkp.add_argument("path", help="Path to teaser.json (clips dir = <dir>/clips).")
    tkp.add_argument("--shot", required=True, help="Shot id to promote a take for.")
    tkp.add_argument("--take", required=True, type=int, help="Take number to promote.")
    tkp.add_argument("--clips-dir", dest="clips_dir", default=None,
                     help="Clips dir (default: <teaser.json dir>/clips).")
    tkp.add_argument("--format", choices=["json", "human"], default="human")
    tkp.set_defaults(func=_cmd_teaser_take_pick)

    trs = sub.add_parser("teaser-reset",
                         help="Archive every teaser artifact EXCEPT the reference "
                              "images (refs/, refs.yaml) for a clean --fresh run; "
                              "non-destructive (moves to teaser/reset-archive/).")
    trs.add_argument("path", help="Teaser dir or teaser.json path.")
    trs.add_argument("--dry-run", dest="dry_run", action="store_true",
                     help="Show what would be archived; move nothing.")
    trs.add_argument("--format", choices=["json", "human"], default="human")
    trs.set_defaults(func=_cmd_teaser_reset)

    tmu = sub.add_parser("teaser-music",
                         help="Generate one cohesive music bed from a prompt "
                              "(default: the spine's score_direction); stub = "
                              "offline silent WAV (Phase 9).")
    tmu.add_argument("path", help="Path to teaser.json.")
    tmu.add_argument("--provider", choices=["stub", "musicgen", "elevenlabs"],
                     default="stub", help="Music backend (default stub = offline).")
    tmu.add_argument("--prompt", default=None,
                     help="Music prompt (default: teaser spine score_direction).")
    tmu.add_argument("--duration", type=float, default=30.0,
                     help="Bed length in seconds (default 30).")
    tmu.add_argument("--out-dir", dest="out_dir", default=None,
                     help="Output dir (default: <teaser dir>/music).")
    tmu.add_argument("--model", default=None, help="Optional backend model hint.")
    tmu.add_argument("--token", default=None, help="Explicit API key (wins over env/.env).")
    tmu.add_argument("--dry-run", dest="dry_run", action="store_true",
                     help="Show the plan + key status; generate nothing.")
    tmu.add_argument("--format", choices=["json", "human"], default="human")
    tmu.set_defaults(func=_cmd_teaser_music)

    tvo = sub.add_parser("teaser-vo",
                         help="Synthesize the VOICEOVER spine (the shots' voiceover "
                              "lines) into a narration track; edge = free no-key TTS, "
                              "stub = offline silent WAV (Phase 13).")
    tvo.add_argument("path", help="Path to teaser.json.")
    tvo.add_argument("--provider", choices=["stub", "edge", "elevenlabs"],
                     default="edge", help="VO backend (default edge = free, no key).")
    tvo.add_argument("--voice", default=None,
                     help="Voice id/name (edge: e.g. en-US-GuyNeural; elevenlabs: a voice id).")
    tvo.add_argument("--out-dir", dest="out_dir", default=None,
                     help="Output dir (default: <teaser dir>/vo).")
    tvo.add_argument("--model", default=None, help="Optional backend model hint.")
    tvo.add_argument("--token", default=None, help="Explicit API key (wins over env/.env).")
    tvo.add_argument("--dry-run", dest="dry_run", action="store_true",
                     help="Show the script + key status + estimated length; render nothing.")
    tvo.add_argument("--format", choices=["json", "human"], default="human")
    tvo.set_defaults(func=_cmd_teaser_vo)

    tas = sub.add_parser("teaser-archive-script",
                         help="Timestamp-archive a teaser script (beats.md / "
                              "teaser.json / shot file) before a --force re-run "
                              "overwrites it; refs/ originals untouched (Phase 6).")
    tas.add_argument("path", help="Path to the script file to archive (no-op if absent).")
    tas.add_argument("--archive-dir", dest="archive_dir", default=None,
                     help="Archive dir (default: <file dir>/script-takes).")
    tas.add_argument("--format", choices=["json", "human"], default="human")
    tas.set_defaults(func=_cmd_teaser_archive_script)

    ttr = sub.add_parser("teaser-transitions",
                         help="Suggest where non-cut scene transitions are worth "
                              "considering (time jumps, location changes, pace shifts, "
                              "open/close). Advisory; structured signals only.")
    ttr.add_argument("path", help="Path to teaser.json.")
    ttr.add_argument("--year-gap", dest="year_gap", type=float, default=2.0,
                     help="Min |Δstory_year| between shots to flag a time jump (default 2).")
    ttr.add_argument("--slow-ratio", dest="slow_ratio", type=float, default=1.5,
                     help="duration_s increase ratio that flags a fast→slow pace shift.")
    ttr.add_argument("--format", choices=["json", "human"], default="human")
    ttr.set_defaults(func=_cmd_teaser_transitions)

    tfc = sub.add_parser("teaser-ffmpeg-cmd",
                         help="Print the ffmpeg command that stitches a cut_list.json into "
                              "one mp4 (the command body runs it via bash).")
    tfc.add_argument("path", help="Path to cut_list.json.")
    tfc.add_argument("--versioned", action="store_true",
                     help="Timestamp the output (`<title>_teaser_<UTC>.mp4`) and "
                          "report a `latest` pointer the command body copies to, so "
                          "a re-assemble never clobbers an earlier cut (Phase 5.8).")
    tfc.add_argument("--out", default=None,
                     help="Output mp4 (default: <dir>/<title>_teaser.mp4).")
    tfc.add_argument("--format", choices=["json", "human"], default="human")
    tfc.set_defaults(func=_cmd_teaser_ffmpeg_cmd)

    args = p.parse_args(argv)
    if not hasattr(args, "func"):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
