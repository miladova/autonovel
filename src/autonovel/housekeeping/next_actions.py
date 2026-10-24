"""State-aware next-action enumerator for `/autonovel:next`.

Today's `next_step()` (in next_step.py) returns a single canonical
"what to do next in the pipeline" given a PipelineState. That's
correct for the simple case but misses situations where multiple
concurrent actions matter — pending canon conflicts, chapter
regressions, stale panel reports, ungit-backed changes, missing
title/author, missing front matter, stale typeset.

This module reads filesystem state directly (no last-action.json
replay; no LLM) and returns a *list* of NextAction records ordered
by priority. The /autonovel:next slash-command body invokes the
underlying CLI helper and prints the list verbatim.

Why two modules:
  - next_step.py answers "given this PipelineState, what's the
    canonical next pipeline step?". It's pure-function, no I/O,
    deeply testable. Used by the postamble's footer.
  - next_actions.py answers "given the live filesystem RIGHT NOW,
    what concurrent things should the user be aware of?". I/O-
    heavy; covers state next_step.py doesn't model (regressions,
    backup status, front matter, etc.). Used by /autonovel:next.

Both are invoked together by the slash-command: the canonical
next-step is included as one of the actions (always present, lowest
priority because it's the "if nothing more urgent, do this" line),
and the situational actions are sorted ahead of it by severity.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .. import last_action as last_action_mod, project as project_mod
from ..paths import SeriesLayout, iter_chapter_files


@dataclass
class NextAction:
    """One actionable line in the /autonovel:next output."""
    priority: str           # "HIGH" | "MEDIUM" | "LOW" | "INFO"
    title: str              # one-line summary
    command: str | None     # the canonical command to run, if any
    rationale: str          # why this matters (2-3 sentences max)
    book: str | None = None # which book this concerns (None = series-wide)

    def to_dict(self) -> dict:
        return {
            "priority": self.priority,
            "title": self.title,
            "command": self.command,
            "rationale": self.rationale,
            "book": self.book,
        }


# Priority ordering: HIGH first, then MEDIUM, LOW, INFO.
_PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}


def enumerate_actions(series: SeriesLayout, *, book: str | None = None) -> list[NextAction]:
    """Inspect filesystem state for one book (or every book in the
    series if `book` is None) and return a prioritised action list.
    """
    actions: list[NextAction] = []
    cfg = project_mod.load(series.project_file)
    book_names = [b.name for b in cfg.books] if book is None else [book]
    for b in book_names:
        actions.extend(_actions_for_book(series, cfg, b))
    actions.extend(_series_wide_actions(series, cfg))
    actions.sort(key=lambda a: _PRIORITY_ORDER.get(a.priority, 99))
    return actions


def _actions_for_book(series: SeriesLayout, cfg: project_mod.ProjectConfig,
                      book: str) -> list[NextAction]:
    book_root = series.books / book
    if not book_root.is_dir():
        return []
    out: list[NextAction] = []
    out.extend(_pending_canon_conflict_actions(book_root, book))
    out.extend(_chapter_regression_actions(book_root, book))
    out.extend(_weakest_item_actions(book_root, book, cfg))
    out.extend(_brief_newer_than_chapter_actions(book_root, book))
    out.extend(_summary_stale_actions(book_root, book))
    out.extend(_panel_staleness_actions(book_root, book))
    out.extend(_review_staleness_actions(book_root, book))
    out.extend(_genre_actions(series, cfg, book))
    out.extend(_design_actions(book_root, book))
    out.extend(_cast_actions(book_root, book))
    out.extend(_developmental_edit_actions(book_root, book))
    out.extend(_structure_review_actions(book_root, book))
    out.extend(_typeset_staleness_actions(book_root, book, series.root))
    out.extend(_missing_title_author_actions(cfg, book))
    out.extend(_missing_front_matter_actions(book_root, book))
    out.extend(_missing_glossary_actions(cfg, book_root, book))
    out.extend(_missing_chapter_titles_actions(book_root, book))
    out.extend(_teaser_actions(book_root, book))
    return out


def _teaser_actions(book_root: Path, book: str) -> list[NextAction]:
    """Teaser/movie-mode next steps (Phase 6+). Fires ONLY when a teaser is
    in progress (a `teaser/` artifact exists) so it never nags a book that
    isn't making one. Walks the same flow the orchestrator does — beats →
    shots → critique→revise (render gate) → render → assemble — and surfaces
    the single next teaser step. LOW/MEDIUM priority (never outranks
    data-integrity HIGH items)."""
    tdir = book_root / "teaser"
    if not tdir.is_dir():
        return []
    beats = tdir / "beats.md"
    teaser_json = tdir / "teaser.json"
    clips = tdir / "clips"
    # An assembled cut already exists → the teaser is done; say nothing.
    if any(tdir.glob("*_teaser*.mp4")):
        return []
    brief = tdir / "brief.md"
    if not beats.exists() and not teaser_json.exists():
        # Only a distilled brief so far → select the beats from it.
        if brief.exists():
            return [NextAction(
                priority="MEDIUM",
                title=f"Teaser brief distilled for {book} — select the beats",
                command=f"/autonovel:teaser-beats --book {book}",
                rationale=(
                    f"books/{book}/teaser/brief.md exists (through-line + turn + "
                    f"killer lines) but no beat-sheet yet. Pick the beats from "
                    f"the brief — free, no generation."),
                book=book)]
        return []  # teaser dir but nothing started — don't guess

    if beats.exists() and not teaser_json.exists():
        return [NextAction(
            priority="MEDIUM",
            title=f"Teaser beats written for {book} — author the shot prompts",
            command=f"/autonovel:shot-prompts --book {book}",
            rationale=(
                f"books/{book}/teaser/beats.md exists but there's no teaser.json "
                f"yet. Turn the spine + beats into provider-ready shot prompts "
                f"(dialogue mined, text cards) — free, no generation."),
            book=book)]

    # teaser.json exists — check the render gate (story-spine flags) cheaply.
    gate_blocked: list[str] = []
    try:
        out = subprocess.run(
            ["autonovel", "mechanical", "teaser-critique", str(teaser_json),
             "--format", "json"],
            capture_output=True, text=True, timeout=20)
        if out.returncode == 0:
            from ..teaser import critique as _crit  # local import: optional dep
            data = json.loads(out.stdout)
            codes = {f.get("code") for f in data.get("findings", [])}
            gate_blocked = sorted(codes & set(_crit.STORY_GATE_CODES))
    except Exception:  # noqa: BLE001 — never let next crash on teaser checks
        gate_blocked = []

    if gate_blocked:
        return [NextAction(
            priority="MEDIUM",
            title=f"Teaser for {book} — render gate BLOCKED, apply the critique",
            command=f"/autonovel:teaser-revise --book {book}",
            rationale=(
                f"books/{book}/teaser/teaser.json has must-fix story flags "
                f"({', '.join(gate_blocked)}) — a real render is refused until "
                f"they clear. teaser-revise applies the critique in place (no "
                f"hand edits); or shot-prompts --force for a clean re-author."),
            book=book)]

    # Story gate is clear — now the Phase-11 QUALITY gate. A real render is
    # also refused if the teaser is structurally complete but boring
    # (quality.json missing or below overall ≥ 7 / no dimension < 5).
    quality_json = tdir / "quality.json"
    quality_blocked = False
    quality_overall = None
    if not quality_json.exists():
        quality_blocked = True
    else:
        try:
            from ..teaser import quality as _q  # local import: optional dep
            qscore = _q.load(quality_json)
            quality_overall = qscore.overall()
            quality_blocked = not qscore.passes()
        except Exception:  # noqa: BLE001
            quality_blocked = True
    if quality_blocked:
        if not quality_json.exists():
            return [NextAction(
                priority="MEDIUM",
                title=f"Teaser for {book} — story complete, score it for interest",
                command=f"/autonovel:teaser-critique --book {book}",
                rationale=(
                    f"books/{book}/teaser/teaser.json passes the story gate but "
                    f"has no quality.json scorecard yet — a real render is refused "
                    f"until the interestingness rubric clears (overall ≥ 7, no "
                    f"dimension < 5). teaser-critique scores it for free."),
                book=book)]
        return [NextAction(
            priority="MEDIUM",
            title=f"Teaser for {book} — quality gate BLOCKED, de-boring revise",
            command=f"/autonovel:teaser-revise --book {book}",
            rationale=(
                f"books/{book}/teaser/quality.json is below the bar "
                f"(overall {quality_overall}/10) — a real render is refused until "
                f"it clears. teaser-revise lifts the weak dimensions and de-borings "
                f"the flattest beats in place (no hand edits)."),
            book=book)]

    rendered = clips.is_dir() and any(
        clips.glob("shot_*.png")) or (clips.is_dir() and any(clips.glob("shot_*.mp4")))
    if not rendered:
        return [NextAction(
            priority="LOW",
            title=f"Teaser for {book} is READY to render",
            command=f"/autonovel:teaser-render --book {book} --provider stub",
            rationale=(
                f"Both gates are READY (story complete + quality "
                f"{quality_overall}/10). Validate the render→assemble chain FREE "
                f"with the offline stub, then develop references "
                f"(/autonovel:teaser-refs) and render on a real backend."),
            book=book)]

    # Clips on disk, no assembled cut yet → stitch it.
    return [NextAction(
        priority="LOW",
        title=f"Teaser clips rendered for {book} — assemble the cut",
        command=f"/autonovel:teaser-assemble --book {book}",
        rationale=(
            f"books/{book}/teaser/clips/ has rendered shots but no assembled "
            f"video yet. Stitch them into one teaser (mixed video+stills, "
            f"ducked bed, burned titles) and run the viewer-panel cut critique."),
        book=book)]


def _series_wide_actions(series: SeriesLayout,
                          cfg: project_mod.ProjectConfig) -> list[NextAction]:
    out: list[NextAction] = []
    out.extend(_git_backup_actions(series.root))
    return out


# ---------------------------------------------------------- per-book


def _pending_canon_conflict_actions(book_root: Path, book: str) -> list[NextAction]:
    pending = book_root / "pending_canon.md"
    if not pending.is_file():
        return []
    text = pending.read_text(encoding="utf-8")
    if "# Conflicts — resolve before next promote-canon" not in text:
        return []
    conflict_count = len(re.findall(r"^## Conflict \d+\s*$", text, re.MULTILINE))
    return [NextAction(
        priority="HIGH",
        title=f"Resolve {conflict_count} canon conflict(s) in {book}",
        command=None,  # manual edit; no single command resolves it
        rationale=(
            f"books/{book}/pending_canon.md has {conflict_count} "
            f"## Conflict N block(s) needing human resolution. Open "
            f"the file and follow the HOW TO RESOLVE A CONFLICT block "
            f"at the top (three labelled paths: accept / reject / "
            f"both wrong). Re-run /autonovel:promote-canon after "
            f"editing."
        ),
        book=book,
    )]


def _weakest_item_actions(book_root: Path, book: str,
                          cfg: project_mod.ProjectConfig) -> list[NextAction]:
    """The worst item, not the mean (2026-10-23). Two signals a passing
    chapter score hides:

      - a dimension under `defaults.dimension_floor` (the chapter
        threshold when unset) → MEDIUM, revision-pass on those chapters;
      - serious items from a chapter's cold first reader that no second
        reader confirmed fixed → LOW, re-read them with first-read.
    """
    from ..mechanical.chapter_summary import chapter_score_details, format_low
    details = chapter_score_details(book_root / "eval_logs")
    if not details:
        return []
    threshold = float(cfg.defaults.get("chapter_threshold", 7.0))
    floor = cfg.defaults.get("dimension_floor")
    floor = float(floor) if floor is not None else threshold
    out: list[NextAction] = []
    weak = sorted((d for d in details.values()
                   if d.low_score is not None and d.low_score < floor),
                  key=lambda d: (d.low_score, d.chapter))
    if weak:
        chapters = ",".join(str(d.chapter) for d in sorted(weak, key=lambda d: d.chapter))
        listing = "; ".join(f"ch {d.chapter} {format_low(d.low_dim, d.low_score)}"
                            for d in weak)
        out.append(NextAction(
            priority="MEDIUM",
            title=f"Dimension under the {floor:.1f} floor: {listing}",
            command=f"/autonovel:revision-pass --chapters {chapters} --book {book}",
            rationale=(
                f"A chapter's mean can pass while one dimension fails. These "
                f"chapters' weakest dimensions are under the floor; the brief "
                f"leads with them. `/autonovel:dashboard --book {book}` ranks "
                f"the book's lowest scores under \"Needs attention first\"."),
            book=book,
        ))
    unchecked = sorted((d for d in details.values()
                        if d.reader_open and d.reader_second is None),
                       key=lambda d: d.chapter)
    if unchecked:
        listing = ", ".join(f"ch {d.chapter} ({d.reader_open})" for d in unchecked)
        out.append(NextAction(
            priority="LOW",
            title=f"Cold-reader items never re-read: {listing}",
            command=f"/autonovel:first-read {unchecked[0].chapter} --book {book}",
            rationale=(
                "The first reader found serious items in these chapters and the "
                "draft fixed them, but no second reader confirmed the fixes. "
                "Re-read each with /autonovel:first-read <N>."),
            book=book,
        ))
    return out


def _chapter_regression_actions(book_root: Path, book: str) -> list[NextAction]:
    """Find chapters whose latest eval score is LOWER than a prior
    eval score for the same chapter — those are regressions worth
    re-running.

    Only flags real regressions (drop ≥0.3) to filter eval-noise.
    """
    eval_dir = book_root / "eval_logs"
    if not eval_dir.is_dir():
        return []
    by_chapter: dict[int, list[tuple[str, float]]] = {}
    for path in eval_dir.iterdir():
        if not path.is_file() or path.suffix != ".json":
            continue
        # Tolerate the same three filename shapes as
        # mechanical/chapter_summary.py: `<ts>_chNN_eval.json`,
        # `<ts>_chNN.json`, plain `chNN_eval.json`. Plain shape has no
        # timestamp prefix → fall back to mtime so we can still order.
        m = re.match(r"^(?P<ts>\d{8}_\d{6})_ch(?P<ch>\d+)(_eval)?\.json$", path.name)
        if m:
            ts = m.group("ts")
            ch = int(m.group("ch"))
        else:
            plain = re.match(r"^ch(?P<ch>\d+)_eval\.json$", path.name)
            if not plain:
                continue
            ts = f"mtime_{path.stat().st_mtime:.0f}"
            ch = int(plain.group("ch"))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        score = data.get("overall_score")
        if not isinstance(score, (int, float)):
            continue
        by_chapter.setdefault(ch, []).append((ts, float(score)))

    regressed: list[tuple[int, float, float]] = []
    for ch, entries in by_chapter.items():
        entries.sort(key=lambda x: x[0])
        if len(entries) < 2:
            continue
        prior_max = max(s for _, s in entries[:-1])
        latest = entries[-1][1]
        if prior_max - latest >= 0.3:
            regressed.append((ch, prior_max, latest))

    if not regressed:
        return []
    chapters_str = ",".join(str(c) for c, _, _ in sorted(regressed))
    deltas = ", ".join(
        f"ch{c} {p:.1f}→{l:.1f}" for c, p, l in sorted(regressed)
    )
    return [NextAction(
        priority="HIGH",
        title=f"Re-run regressed chapter(s): {chapters_str}",
        command=f"/autonovel:revision-pass --chapters {chapters_str} --book {book}",
        rationale=(
            f"{len(regressed)} chapter(s) ended below their prior best "
            f"by ≥0.3 ({deltas}). The latest revise made them worse, "
            f"not better. Re-run the brief→revise cycle (without "
            f"--enrich-with this time) so the brief reconsiders from "
            f"cuts/eval evidence alone."
        ),
        book=book,
    )]


def _brief_newer_than_chapter_actions(book_root: Path, book: str) -> list[NextAction]:
    """Brief files are written by `/autonovel:brief` and consumed by
    `/autonovel:revise`. When a brief's mtime is newer than the
    chapter it targets, the obvious next step is to revise that
    chapter — but the canonical pipeline default keeps marching
    forward instead. Surface this as a HIGH situational action.

    Brief files live at `books/<book>/briefs/ch{NN:02d}.md`. We skip
    `briefs/conversation.md` (a different shape — that's `talk`'s
    queue, consumed by revise's per-chapter loop, not a per-chapter
    brief).
    """
    briefs_dir = book_root / "briefs"
    if not briefs_dir.is_dir():
        return []
    chapters_dir = book_root / "chapters"
    pending: list[int] = []
    for path in sorted(briefs_dir.iterdir()):
        if not path.is_file():
            continue
        m = re.match(r"^ch(?P<ch>\d+)\.md$", path.name)
        if not m:
            continue
        ch_num = int(m.group("ch"))
        chapter_path = chapters_dir / f"ch_{ch_num:02d}.md"
        if not chapter_path.is_file():
            continue
        if path.stat().st_mtime > chapter_path.stat().st_mtime:
            pending.append(ch_num)
    if not pending:
        return []
    pending.sort()
    chapters_str = ",".join(str(c) for c in pending)
    if len(pending) == 1:
        command = f"/autonovel:revise --chapter {pending[0]} --book {book}"
    else:
        command = f"/autonovel:revision-pass --chapters {chapters_str} --book {book}"
    return [NextAction(
        priority="HIGH",
        title=f"Revise chapter(s) with fresh briefs: {chapters_str}",
        command=command,
        rationale=(
            f"books/{book}/briefs/ has {len(pending)} brief file(s) "
            f"newer than their chapters (ch {chapters_str}). The brief "
            f"is the input revise consumes — until revise runs, the "
            f"work the brief captures isn't applied to the prose. "
            f"For non-contiguous chapters, run `/autonovel:revise "
            f"--chapter <N>` per chapter (revision-pass takes a range)."
        ),
        book=book,
    )]


def _summary_stale_actions(book_root: Path, book: str) -> list[NextAction]:
    """Per-chapter `.summary.md` files are the load-bearing
    continuity surface. The next chapter's drafter reads them as
    rolling context; evaluate, the sweeps and the reviewers read them for
    cast, threads and story time. A summary that no longer matches its
    chapter hands them a story that is no longer on the page.

    Freshness is the fingerprint `autonovel _stamp-summary` records
    (`summaries.state`), not file mtimes, which flagged every revised
    chapter and missed a summary touched after the prose changed.
    `_end` refuses to close a command that leaves one behind, and every
    command that reads summaries refreshes them first, so a stale one
    here means the prose was edited outside a command (by hand).
    Summaries from before fingerprints that are not older than their
    chapter (`unverified`) are not listed: the next command that reads
    them refreshes them.

    HIGH priority: continuity is data-integrity, not polish.
    """
    from .. import summaries
    stale = [s.chapter for s in summaries.book_states(book_root) if s.status == "stale"]
    if not stale:
        return []
    chapters_str = ",".join(str(c) for c in stale)
    if len(stale) == 1:
        command = f"/autonovel:summarize-chapter {stale[0]} --book {book} --force"
    else:
        command = f"/autonovel:summarize-chapter --stale --book {book}"
    return [NextAction(
        priority="HIGH",
        title=f"Stale chapter summaries: {chapters_str}",
        command=command,
        rationale=(
            f"The text of chapter(s) {chapters_str} changed after their "
            f"continuity summaries were written, outside a command (a "
            f"command can't close until its summaries match). Every "
            f"command that reads summaries (draft, the sweeps, evaluate, "
            f"the reviewers) refreshes these before reading them; run "
            f"`/autonovel:summarize-chapter` to refresh them now."
        ),
        book=book,
    )]


def _panel_staleness_actions(book_root: Path, book: str) -> list[NextAction]:
    panel = book_root / "edit_logs" / "reader_panel.json"
    return _staleness_check(
        report_path=panel,
        book_root=book_root,
        book=book,
        report_label="reader-panel report",
        rerun_command=f"/autonovel:reader-panel --book {book}",
        priority="MEDIUM",
    )


def _review_report_path(book_root: Path) -> Path:
    """`/autonovel:review` writes `edit_logs/review.md`; series reviewed
    before 2026-10 carry the legacy name `opus_review.md`. Prefer the
    current name, fall back to the legacy one when only it exists."""
    edit_logs = book_root / "edit_logs"
    current = edit_logs / "review.md"
    legacy = edit_logs / "opus_review.md"
    return current if current.is_file() or not legacy.is_file() else legacy


def _review_staleness_actions(book_root: Path, book: str) -> list[NextAction]:
    review = _review_report_path(book_root)
    return _staleness_check(
        report_path=review,
        book_root=book_root,
        book=book,
        report_label="Opus review",
        rerun_command=f"/autonovel:review --book {book}",
        priority="MEDIUM",
    )


def _genre_actions(series: SeriesLayout, cfg: project_mod.ProjectConfig,
                   book: str) -> list[NextAction]:
    """What the book's reader comes for (`/autonovel:genre`): LOW when the
    genre's guide is missing from the series (refresh-templates), when the
    genre has subgenres but the book names none, or when the genre has no
    guide yet. Every writing and judging command reads the guide; without
    the right one they judge by general craft alone."""
    from .. import genres as genres_mod
    r = genres_mod.resolve(cfg, book, series_root=series.root)
    g = r.genre
    if g is None or g.id == "general":
        return []
    if g.guide and r.guide_path is None:
        return [NextAction(
            priority="MEDIUM",
            title=f"The {g.name} guide is missing from this series",
            command="autonovel refresh-templates",
            rationale=(f"{r.guide_expected} tells every command what a {g.name} reader "
                       f"comes for; refresh-templates copies it in."),
            book=book)]
    if g.subgenres and not r.subgenres and not r.other_subgenres:
        return [NextAction(
            priority="LOW",
            title=f"Name {book}'s subgenre ({g.name})",
            command=f"/autonovel:genre --book {book} --list",
            rationale=("Each subgenre promises its reader something different (a "
                       "biographical novel, a political thriller, a mystery…) and the "
                       "guide's subgenre entry says what the design, the draft and the "
                       "judges owe it. A book can be two."),
            book=book)]
    if r.guide_path is None:
        return [NextAction(
            priority="LOW",
            title=f"No guide yet for {g.name}",
            command=f"/autonovel:genre --add {g.id}",
            rationale=("Commands judge by general craft alone until the genre has a "
                       "guide saying what its reader comes for."),
            book=book)]
    return []


def _design_actions(book_root: Path, book: str) -> list[NextAction]:
    """The design stage (`/autonovel:design`), before any chapter exists:

      - no `design.md` → design the book before outlining it (HIGH: every
        later stage executes what the design decides, and a book outlined
        without one drafts into episodes);
      - `design.md` fails `design-validate` → fix it (MEDIUM);
      - `design.md` newer than a populated `outline.md` → re-outline from
        it (MEDIUM).

    Silent once chapters are drafted: a drafted book is re-designed as a
    new book (`--from-book`), which `/autonovel:developmental-edit`
    recommends when its diagnosis is design-level.
    """
    if iter_chapter_files(book_root / "chapters"):
        return []
    design = book_root / "design.md"
    if not design.is_file():
        if not (book_root / "seed.txt").is_file():
            return []
        return [NextAction(
            priority="HIGH",
            title="Design the book before outlining it",
            command=f"/autonovel:design --book {book}",
            rationale=(
                f"books/{book} has no design.md. The design decides the climax, "
                f"the question it answers, the opponent, the plants the climax "
                f"spends and the sequences; the outline and every chapter execute "
                f"it. Outlined without one, a book drafts into a string of "
                f"episodes."),
            book=book,
        )]
    from ..mechanical import design as design_mod
    rep = design_mod.check(book_root)
    if not rep.ok:
        return [NextAction(
            priority="MEDIUM",
            title="Fix the design (design-validate reports errors)",
            command=f"/autonovel:design --book {book} --force",
            rationale="; ".join(rep.errors[:3])
            + (f" (+{len(rep.errors) - 3} more)" if len(rep.errors) > 3 else ""),
            book=book,
        )]
    outline = book_root / "outline.md"
    if (outline.is_file() and "## Chapter" in outline.read_text(encoding="utf-8")
            and design.stat().st_mtime > outline.stat().st_mtime):
        return [NextAction(
            priority="MEDIUM",
            title="Re-outline from the revised design",
            command=f"/autonovel:gen-outline --book {book} --force",
            rationale=(f"books/{book}/design.md changed after outline.md was "
                       f"written; the outline must carry the design before drafting."),
            book=book,
        )]
    return []


def _cast_actions(book_root: Path, book: str) -> list[NextAction]:
    """The character dossiers (`/autonovel:cast`): a book with a design but
    no `cast.md` drafts its people from one-line labels, and readers find
    them "too simple". MEDIUM before any chapter is drafted (cheapest
    then); LOW once chapters exist (the dossiers then drive revisions)."""
    if not (book_root / "design.md").is_file() or (book_root / "cast.md").is_file():
        return []
    drafted = bool(iter_chapter_files(book_root / "chapters"))
    return [NextAction(
        priority="LOW" if drafted else "MEDIUM",
        title="Build the character dossiers (cast.md)",
        command=f"/autonovel:cast --book {book}",
        rationale=(
            f"books/{book} has a design but no cast.md. The design gives each "
            f"character a line; the dossier gives the drafter a person: the "
            f"contradiction acted out, the choices that test them by chapter, "
            f"their history with each other, a private monologue and a return "
            f"tag for when they come back."),
        book=book,
    )]


def _developmental_edit_actions(book_root: Path, book: str) -> list[NextAction]:
    """The editor's full read (`/autonovel:developmental-edit`). Two states:

      - no `edit_logs/editor_letter.md` on a drafted book (same threshold
        as the structure review: ≥6 chapters AND either a whole-book
        reviewer report exists or every outlined chapter is drafted) →
        get one;
      - a letter older than some chapter → the revision it prompted (or
        any other) has changed the book since the last read; re-read.

    MEDIUM when missing: the reviewers' scores are not an editor's read,
    and on kingmaker the read found what four stars hid. LOW when stale:
    a re-read is due but not urgent after every small revise.
    """
    chapters = iter_chapter_files(book_root / "chapters")
    if len(chapters) < _STRUCTURE_REVIEW_MIN_CHAPTERS:
        return []
    letter = book_root / "edit_logs" / "editor_letter.md"
    command = f"/autonovel:developmental-edit --book {book}"
    if not letter.is_file():
        edit_logs = book_root / "edit_logs"
        whole_book_report = any((edit_logs / name).is_file() for name in (
            "review.md", "opus_review.md", "review.json", "reader_panel.json",
            "structure_review.json"))
        if not whole_book_report and not _every_outlined_chapter_drafted(book_root, chapters):
            return []
        return [NextAction(
            priority="MEDIUM",
            title="Get a developmental editor's full read",
            command=command,
            rationale=(
                f"books/{book} has {len(chapters)} chapters drafted and no "
                f"edit_logs/editor_letter.md. The panel, the review and the "
                f"structure review score the book; none of them reads it whole "
                f"as an editor and writes the author a ranked letter on the "
                f"story: what must survive, what is wrong and why, what to do "
                f"first."),
            book=book,
        )]
    newer = [p for p in chapters if p.stat().st_mtime > letter.stat().st_mtime]
    if not newer:
        return []
    nums = []
    for p in newer:
        try:
            nums.append(int(p.stem.split("_")[-1]))
        except ValueError:
            continue
    return [NextAction(
        priority="LOW",
        title="Re-read the book (chapters changed since the editor's letter)",
        command=command,
        rationale=(
            f"Chapter(s) {', '.join(map(str, sorted(nums)))} changed after "
            f"edit_logs/editor_letter.md was written. The next read archives "
            f"the old letter and says whether the revision did what it "
            f"recommended."),
        book=book,
    )]


# A structure review needs a book to judge: below this many drafted
# chapters there is no causal chain or act ladder worth reviewing.
_STRUCTURE_REVIEW_MIN_CHAPTERS = 6


def _structure_review_actions(book_root: Path, book: str) -> list[NextAction]:
    """The book-level gate (`/autonovel:structure-review`). Three states:

      - no `edit_logs/structure_review.json` on a book that is drafted
        (≥6 chapters AND either a whole-book reviewer report exists or
        every outlined chapter is drafted) → run it;
      - present but older than a chapter, or invalid → re-run it;
      - fresh and the gate blocks (score < 4 or a chapter removable) →
        act on its structural brief candidates.

    Silent when the gate passes. MEDIUM: this is the signal that the
    book is a string of episodes, which no per-chapter score shows; it
    must not outrank data-integrity HIGH items.
    """
    chapters = iter_chapter_files(book_root / "chapters")
    if len(chapters) < _STRUCTURE_REVIEW_MIN_CHAPTERS:
        return []
    from ..mechanical import structure_review as sr
    path = book_root / "edit_logs" / "structure_review.json"
    command = f"/autonovel:structure-review --book {book}"
    if not path.is_file():
        edit_logs = book_root / "edit_logs"
        whole_book_report = any((edit_logs / name).is_file() for name in (
            "review.md", "opus_review.md", "review.json", "reader_panel.json"))
        if not whole_book_report and not _every_outlined_chapter_drafted(book_root, chapters):
            return []
        return [NextAction(
            priority="MEDIUM",
            title="Run the book-level structure review",
            command=command,
            rationale=(
                f"books/{book} has {len(chapters)} chapters drafted but no "
                f"edit_logs/structure_review.json. Chapter scores, the panel "
                f"and the dual-persona review are prose-weighted: none of them "
                f"tests whether chapter N+1 happens *because of* chapter N, "
                f"whether stakes rise per act, or which chapters could be cut "
                f"without breaking anything. /autonovel:review will not "
                f"declare stop-revising until this gate passes."),
            book=book,
        )]
    try:
        rep = sr.check(path, book_root=book_root)
    except Exception:  # noqa: BLE001 — never let /autonovel:next crash
        return []
    gate = rep.gate
    if gate.get("stale") or not rep.valid:
        why = (f"chapter(s) {', '.join(map(str, gate.get('stale_chapters') or []))} changed since it ran"
               if gate.get("stale") else "the file does not validate "
               f"(`autonovel mechanical structure-validate books/{book}` lists the errors)")
        return [NextAction(
            priority="MEDIUM",
            title="Re-run the book-level structure review",
            command=command,
            rationale=(
                f"books/{book}/edit_logs/structure_review.json is no longer "
                f"usable: {why}. The stop-revising gate reads it, so a stale "
                f"or invalid review blocks the gate until it is re-run."),
            book=book,
        )]
    if gate.get("passes"):
        return []
    score = gate.get("structure_score")
    removable = gate.get("removable_chapters") or []
    cross = [c for c in rep.summary.get("cross_chapter_commands") or [] if c]
    rationale = (
        f"The structure review scored the book {score}/5"
        + (f" and flagged chapter(s) {', '.join(map(str, removable))} as removable "
           f"(no later chapter needs them)" if removable else "")
        + ". Its structural brief candidates feed `brief --from auto`: the sweep "
          "below briefs and revises every chapter they touch, inside each chapter.")
    if cross:
        rationale += (" Cross-chapter moves are yours to run (revise never "
                      "executes them): " + "; ".join(cross) + ".")
    return [NextAction(
        priority="MEDIUM",
        title=f"Act on the structure review ({score}/5; gate blocked)",
        command=f"/autonovel:revision-pass --chapters structural --book {book}",
        rationale=rationale,
        book=book,
    )]


def _every_outlined_chapter_drafted(book_root: Path, chapters: list[Path]) -> bool:
    outline = book_root / "outline.md"
    if not outline.is_file():
        return False
    nums = {int(m) for m in re.findall(r"^##\s+Chapter\s+(\d+)\b",
                                        outline.read_text(encoding="utf-8"),
                                        re.MULTILINE | re.IGNORECASE)}
    if not nums:
        return False
    drafted: set[int] = set()
    for p in chapters:
        try:
            drafted.add(int(p.stem.split("_")[-1]))
        except ValueError:
            continue
    return nums <= drafted


def _staleness_check(*, report_path: Path, book_root: Path, book: str,
                      report_label: str, rerun_command: str,
                      priority: str) -> list[NextAction]:
    """Generic mtime check: if the report exists but a chapter has
    been touched since, the report is stale."""
    if not report_path.is_file():
        return []
    report_mtime = report_path.stat().st_mtime
    newer_chapters: list[int] = []
    for ch_path in iter_chapter_files(book_root / "chapters"):
        if ch_path.stat().st_mtime > report_mtime:
            try:
                newer_chapters.append(int(ch_path.stem.split("_")[-1]))
            except ValueError:
                continue
    if not newer_chapters:
        return []
    return [NextAction(
        priority=priority,
        title=f"Re-run {report_label} ({len(newer_chapters)} chapter(s) changed since)",
        command=rerun_command,
        rationale=(
            f"{report_label} at {report_path.relative_to(book_root.parent.parent)} "
            f"was last written before chapters {sorted(newer_chapters)} were "
            f"touched. The prior report describes a manuscript that no "
            f"longer exists; re-running gives you a fresh flagged-chapter "
            f"list against the current prose."
        ),
        book=book,
    )]


def _typeset_staleness_actions(book_root: Path, book: str,
                                series_root: Path) -> list[NextAction]:
    typeset_dir = book_root / "typeset"
    if not typeset_dir.is_dir():
        return []
    # Look for the canonical *_latest.pdf written by typeset.
    latest_pdf = list(typeset_dir.glob("*_latest.pdf"))
    if not latest_pdf:
        return []
    pdf_mtime = latest_pdf[0].stat().st_mtime
    newer = [p for p in iter_chapter_files(book_root / "chapters")
             if p.stat().st_mtime > pdf_mtime]
    if not newer:
        return []
    return [NextAction(
        priority="LOW",
        title=f"Rebuild PDF + ePub ({len(newer)} chapter(s) changed since last typeset)",
        command=f"/autonovel:typeset --book {book}",
        rationale=(
            f"books/{book}/typeset/{latest_pdf[0].name} predates "
            f"{len(newer)} of your chapter files. Rebuild to read "
            f"the current state in PDF form (cheap; safe; read-only "
            f"against chapter prose)."
        ),
        book=book,
    )]


def _missing_title_author_actions(cfg: project_mod.ProjectConfig,
                                   book: str) -> list[NextAction]:
    """Suggest /autonovel:title only when the book is far enough
    along that the title page would actually appear in a typeset
    output (skip during foundation/early drafting)."""
    book_entry = cfg.book_by_name(book)
    if book_entry is None:
        return []
    has_title = bool(book_entry.title)
    has_author = bool(book_entry.author or cfg.author)
    if has_title and has_author:
        return []
    missing: list[str] = []
    if not has_title:
        missing.append("title")
    if not has_author:
        missing.append("author")
    return [NextAction(
        priority="LOW",
        title=f"Set the book's display {' + '.join(missing)} for typeset",
        command=f"/autonovel:title --book {book}",
        rationale=(
            f"project.yaml :: books[{book}].title and/or .author "
            f"is unset. Typeset will fall back to the series "
            f"slug / 'Anonymous' on the title page. Run "
            f"/autonovel:title to propose candidates from the "
            f"outline + seed (or use --set / --author to set "
            f"explicit values)."
        ),
        book=book,
    )]


def _missing_chapter_titles_actions(book_root: Path, book: str) -> list[NextAction]:
    """Polish signal — chapters with no `title:` frontmatter and no
    `# Heading` line. typeset's TOC reads as `Chapter I`,
    `Chapter II`, … rather than the publishing convention
    `Chapter VII — The Apothecary's Mortar`. Surfaces the
    `/autonovel:extract-chapter-titles` recommendation. Silenced
    when fewer than 3 chapters are drafted (too early to titulate)
    OR when every chapter has a title (already polished).

    LOW priority — typeset still works; this is reader-experience
    polish, not data integrity.
    """
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return []
    try:
        from ..mechanical.chapter_titles import inspect_titles
    except Exception:  # noqa: BLE001
        return []
    report = inspect_titles(book_root)
    if report.total < 3:
        return []
    if not report.missing:
        return []
    chapters_str = ",".join(str(c) for c in report.missing)
    return [NextAction(
        priority="LOW",
        title=f"Backfill chapter titles for {len(report.missing)} chapter(s)",
        command=(f"/autonovel:extract-chapter-titles --book {book} "
                 f"--chapters {chapters_str}"),
        rationale=(
            f"books/{book}/chapters/ has {len(report.missing)} "
            f"chapter(s) with no `title:` frontmatter (ch "
            f"{chapters_str}). typeset's TOC reads `Chapter I`, "
            f"`Chapter II`, … rather than the publishing "
            f"convention `Chapter VII — The Apothecary's Mortar`. "
            f"Light-tier LLM call generates a 2-6 word evocative "
            f"phrase per chapter from the summary + opening "
            f"prose; ~$0.001 per chapter."
        ),
        book=book,
    )]


def _missing_glossary_actions(cfg: project_mod.ProjectConfig,
                                 book_root: Path, book: str) -> list[NextAction]:
    """For period fiction (project.yaml :: period.start set), once
    the book has 3+ chapters drafted, suggest generating a
    glossary. Period vocabulary readers can't decode (a *grosso*,
    a *podestà*, a Doge) is the most common reason historical
    fiction loses readers — the published convention is a one-page
    front-matter glossary.

    LOW priority because it's polish, not data integrity. Silenced
    when the file already exists (even as a stub, since the user
    has explicitly opted in)."""
    period = getattr(cfg, "period", None) or {}
    period_start = (
        period.get("start") if isinstance(period, dict)
        else getattr(period, "start", None)
    )
    if not period_start:
        return []
    glossary = book_root / "glossary.md"
    if glossary.is_file():
        return []
    chapters = iter_chapter_files(book_root / "chapters")
    if len(chapters) < 3:
        return []
    return [NextAction(
        priority="LOW",
        title=f"Add a period glossary for typeset front matter",
        command=f"/autonovel:glossary --book {book} --from auto",
        rationale=(
            f"books/{book} is period fiction "
            f"(project.yaml :: period.start = {period_start}) and has "
            f"{len(chapters)} chapter(s) drafted, but no `glossary.md`. "
            f"Period vocabulary the reader can't decode (a *grosso*, "
            f"a *podestà*, a Doge) is the most common reason historical "
            f"fiction loses readers; the published convention is a one-"
            f"page glossary in the front matter, right before chapter 1. "
            f"`--from auto` extracts terms from the prose + research "
            f"notes; you refine before typeset."
        ),
        book=book,
    )]


def _missing_front_matter_actions(book_root: Path, book: str) -> list[NextAction]:
    """Suggest /autonovel:introduction only once the book has
    chapters drafted — front matter doesn't matter during
    foundation."""
    chapters = iter_chapter_files(book_root / "chapters")
    if len(chapters) < 3:
        return []
    has_preface = (book_root / "preface.md").is_file()
    has_intro = (book_root / "introduction.md").is_file()
    if has_preface or has_intro:
        return []
    return [NextAction(
        priority="LOW",
        title=f"Add a preface or introduction for the typeset front matter",
        command=f"/autonovel:introduction --book {book} --from both",
        rationale=(
            f"books/{book} has neither preface.md nor "
            f"introduction.md. Optional, but a typeset book without "
            f"either feels truncated at the title page. --from both "
            f"scaffolds preface.md (you write) and AI-drafts "
            f"introduction.md (you edit)."
        ),
        book=book,
    )]


# ---------------------------------------------------------- series-wide


def _git_backup_actions(series_root: Path) -> list[NextAction]:
    """Three states:
      - no git repo at all → suggest setting up the backup
      - git repo with no remote → suggest setting up the backup
      - git repo with remote AND uncommitted/unpushed changes →
        suggest commit + push
      - git repo, all clean → no action
    """
    if not (series_root / ".git").is_dir():
        return [NextAction(
            priority="MEDIUM",
            title="Back up your novel to a private GitHub repo",
            command=None,  # multi-step; see operating-guide §3e.1
            rationale=(
                f"{series_root} is not a git repository. Your novel "
                f"is local-only. See operating-guide §3e.1 for the "
                f"one-time setup (git init + .gitignore copy + "
                f"`gh repo create my-novel-backup --private "
                f"--source=. --remote=origin --push`)."
            ),
            book=None,
        )]
    # Check remote.
    try:
        remotes = subprocess.run(
            ["git", "-C", str(series_root), "remote"],
            capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    if not remotes:
        return [NextAction(
            priority="MEDIUM",
            title="Add a GitHub remote and push your novel as backup",
            command=None,
            rationale=(
                f"{series_root} is git-tracked but has no remote. "
                f"`gh repo create my-novel-backup --private --source=. "
                f"--remote=origin --push` from the series root sets "
                f"up the private backup. See operating-guide §3e.1."
            ),
            book=None,
        )]
    # Check for uncommitted or unpushed changes.
    try:
        status = subprocess.run(
            ["git", "-C", str(series_root), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return []
    if status:
        return [NextAction(
            priority="MEDIUM",
            title="Commit + push uncommitted changes to the GitHub backup",
            command=None,
            rationale=(
                f"{series_root} has uncommitted changes. From the "
                f"series root: `git add . && git commit -m \"Snapshot\" "
                f"&& git push`. Substantive revision passes are the "
                f"right cadence for a snapshot."
            ),
            book=None,
        )]
    # Check unpushed commits.
    try:
        ahead = subprocess.run(
            ["git", "-C", str(series_root), "rev-list", "--count",
             "@{u}..HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return []
    if ahead and ahead != "0":
        return [NextAction(
            priority="MEDIUM",
            title=f"Push {ahead} unpushed commit(s) to GitHub",
            command=None,
            rationale=(
                f"{series_root} is {ahead} commit(s) ahead of the "
                f"remote. `git push` from the series root sends them."
            ),
            book=None,
        )]
    return []


# ------------------------------------------------------- canonical step


def canonical_pipeline_action(series: SeriesLayout, *, book: str | None = None) -> NextAction | None:
    """Read the most recent last-action.json and return its
    next_standard_step as an INFO-priority action. This is the
    pipeline-canonical "if nothing more urgent applies, do this"
    line. None when no last-action.json exists yet (fresh series).

    Past-end-of-book guard: when the next_standard_step is a draft
    command targeting a chapter beyond `existing_chapters + 1`, the
    canonical line is misleading (the book is at or past its planned
    end). Replace with a "book appears complete" suggestion pointing
    at evaluate --full / typeset.
    """
    la = last_action_mod.read(series.last_action_file)
    if la is None or not la.next_standard_step:
        return None
    if book is not None and la.book and la.book != book:
        return None
    target_book = la.book or book
    guard = _past_end_of_book_replacement(
        series, target_book, la.next_standard_step
    )
    if guard is not None:
        return guard
    return NextAction(
        priority="INFO",
        title="Pipeline-standard next step (from last command's footer)",
        command=la.next_standard_step,
        rationale=(
            la.next_rationale or
            f"After {la.command}, the standard next step in the "
            f"pipeline is what's stored in last-action.json. (Note: "
            f"this is replayed from the prior command — situational "
            f"actions above this line, when present, take "
            f"precedence.)"
        ),
        book=la.book,
    )


_DRAFT_TARGET_RE = re.compile(
    r"/autonovel:draft\b.*?(?:--chapter\s+|\s)(?P<n>\d+)\b"
)


def _past_end_of_book_replacement(series: SeriesLayout, book: str | None,
                                   command: str) -> NextAction | None:
    """If `command` is a draft command targeting a chapter beyond
    `existing_chapters + 1` for `book`, return a replacement
    "book may be complete" INFO action. Otherwise None.

    The +1 slack lets the legitimate "draft the next chapter" case
    pass through (existing 24 chapters → draft 25 is fine; existing
    24 chapters → draft 30 is past the end).
    """
    if book is None:
        return None
    m = _DRAFT_TARGET_RE.search(command)
    if m is None:
        return None
    target = int(m.group("n"))
    book_root = series.books / book
    chapters_dir = book_root / "chapters"
    if not chapters_dir.is_dir():
        return None
    existing = len(list(iter_chapter_files(chapters_dir)))
    if target <= existing + 1:
        return None
    return NextAction(
        priority="INFO",
        title=f"Book {book} appears complete — try evaluate or typeset",
        command=f"/autonovel:evaluate --full --book {book}",
        rationale=(
            f"The pipeline-canonical next step says draft chapter "
            f"{target}, but books/{book}/chapters/ already has "
            f"{existing} chapter(s) — chapter {target} is past the "
            f"end. The book likely doesn't need another draft; "
            f"`/autonovel:evaluate --full --book {book}` for whole-"
            f"book scoring or `/autonovel:typeset --book {book}` to "
            f"build the PDF + ePub. If the book really should grow, "
            f"`/autonovel:draft {existing + 1} --book {book}` is the "
            f"next sequential chapter."
        ),
        book=book,
    )


# --------------------------------------------------------- postamble hint


# Small rotating pool of general "did you know" hints. Used when no
# situational signal applies. Indexed by a stable hash of the just-ran
# command name so a user pressing the same command twice doesn't see
# the same general hint, but a single command run is deterministic.
_GENERAL_HINTS: tuple[str, ...] = (
    "`/autonovel:help` lists every command grouped by topic — "
    "`/autonovel:help art`, `/autonovel:help typeset`, etc. for in-"
    "depth workflow guides",
    "`/autonovel:summaries --where 'score < 7'` filters chapters by score "
    "without firing evaluate",
    "`/autonovel:dashboard` re-renders the latest evaluate output (sparklines "
    "+ tension drops) for free",
    "`/autonovel:talk --book <name> \"<question>\"` lets you ask the book "
    "questions or queue revise-suggestions inline",
    "`/autonovel:syntax-drift` flags chapters drifting from the voice "
    "baseline by Flesch-Kincaid grade",
    "`/autonovel:next` shows every situational signal autonovel knows "
    "about — pending conflicts, regressions, fresh briefs, stale reports",
    "`autonovel cost` rolls up token + USD spend per book / per tier "
    "/ per command from the command log",
    "`autonovel tui` is a read-only long-running browser for the whole "
    "series — chapters, scores, research, front+back matter, next actions",
    "`/autonovel:diff --from last-read --mark-read` shows what changed since "
    "you last read — word by word, in context — as one HTML page",
)


def top_hint(series: SeriesLayout, *, just_ran: str | None = None,
              book: str | None = None) -> str | None:
    """One-line "💡 Maybe try:" suggestion for the postamble footer.

    Prefer situational: read every action `enumerate_actions` would
    surface and pick the highest-priority one with a runnable
    command. Skip actions whose command is `just_ran` (so we don't
    suggest re-running the same command — the canonical Next: line
    already covers the legitimate "next sequential step" case).

    Fall back to a small rotating pool of general hints when no
    situational signal applies. Selection is deterministic on
    `just_ran` so the user sees variety across commands but not
    randomness within one command.

    Returns None when no command-bearing signal exists (rare; only
    on a brand-new series with no chapters drafted) — caller should
    skip the hint line entirely.
    """
    actions = enumerate_actions(series, book=book)
    for a in actions:
        if a.command is None:
            continue
        if just_ran and _action_command_targets(a.command, just_ran):
            continue
        return f"💡 Maybe try: `{a.command}` *({_short_reason(a)})*"
    return _general_hint(just_ran=just_ran)


def _action_command_targets(command: str, just_ran: str) -> bool:
    """Did `command` (an action's recommended invocation) target the
    same slash-command name as `just_ran`? `just_ran` is bare
    (`autonovel:revise`); `command` includes the slash and args
    (`/autonovel:revise --chapter 2 --book x`)."""
    bare = just_ran.lstrip("/").strip()
    return f"/{bare}" in command or f"/autonovel:{bare}" in command


def _short_reason(a: NextAction) -> str:
    """Compress the action's rationale into a half-sentence postamble
    fragment. Use the title (already short) when no obvious shorter
    form exists."""
    return a.title.lower()


def _general_hint(*, just_ran: str | None) -> str:
    seed = just_ran or ""
    idx = sum(ord(c) for c in seed) % len(_GENERAL_HINTS)
    return f"💡 Did you know? {_GENERAL_HINTS[idx]}"


# ------------------------------------------------------------- render


def render_human(actions: list[NextAction], *, canonical: NextAction | None) -> str:
    """Markdown rendering for the slash-command's output. Groups by
    priority; canonical pipeline action comes last with its own
    block."""
    if not actions and canonical is None:
        return "_No actions queued. Series is clean._\n"
    parts: list[str] = []
    grouped: dict[str, list[NextAction]] = {}
    for a in actions:
        grouped.setdefault(a.priority, []).append(a)
    for prio in ("HIGH", "MEDIUM", "LOW"):
        if prio not in grouped:
            continue
        marker = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}[prio]
        parts.append(f"### {marker} {prio} priority\n")
        for a in grouped[prio]:
            parts.append(f"**{a.title}**" + (f" *({a.book})*" if a.book else ""))
            if a.command:
                parts.append(f"```text\n{a.command}\n```")
            parts.append(a.rationale)
            parts.append("")
    if canonical is not None:
        parts.append("### ⚪ Canonical pipeline next step\n")
        parts.append(f"**{canonical.title}**")
        if canonical.command:
            parts.append(f"```text\n{canonical.command}\n```")
        parts.append(canonical.rationale)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
