"""`autonovel status` (REWRITE-PLAN.md §21.9).

Pure filesystem reads; no LLM; no runtime. Used from any shell.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .. import command_log, last_action, lock, project as project_mod
from ..paths import BookLayout, SeriesLayout


@dataclass
class BookStatus:
    name: str
    status: str
    chapters_drafted: int
    chapters_total: int
    pending_canon_count: int


@dataclass
class SeriesStatus:
    series_name: str
    genre: str
    period: dict
    books: list[BookStatus]
    lock_info: lock.LockInfo | None
    last_action: last_action.LastAction | None
    recent_log: list[command_log.LogEntry]


def gather(series: SeriesLayout) -> SeriesStatus:
    cfg = project_mod.load(series.project_file)

    books: list[BookStatus] = []
    for b in cfg.books:
        bl = series.book(b.name)
        books.append(BookStatus(
            name=b.name,
            status=_effective_book_status(series, bl, b.status),
            chapters_drafted=_count_chapters(bl.chapters),
            chapters_total=_chapters_total(bl.state_file),
            pending_canon_count=_count_pending_canon(bl.pending_canon),
        ))

    return SeriesStatus(
        series_name=cfg.series_name,
        genre=cfg.genre,
        period=dict(cfg.period),
        books=books,
        lock_info=lock.read(series.lock_file),
        last_action=last_action.read(series.last_action_file),
        recent_log=command_log.read_all(series.command_log_file)[-10:],
    )


def _count_chapters(chapters_dir: Path) -> int:
    from ..paths import iter_chapter_files
    return len(iter_chapter_files(chapters_dir))


def _chapters_total(state_file: Path) -> int:
    if not state_file.exists():
        return 0
    try:
        return int(json.loads(state_file.read_text(encoding="utf-8")).get("chapters_total", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _effective_book_status(series: SeriesLayout, book: "BookLayout", fallback: str) -> str:
    """Most-advanced of three signals: `books/<b>/state.json :: phase`,
    `project.yaml :: books[].status`, and the phase inferred from what
    is actually on disk (chapters → drafting, outline/voice → foundation).

    Neither state.json nor project.yaml is reliably advanced by the
    pipeline (a 24-chapter book showed `seed` for weeks), so the on-disk
    inference — the same one `/autonovel:next` uses — is the floor."""
    from .lifecycle import _infer_phase, _phase_rank
    candidates = [fallback]
    if book.state_file.exists():
        try:
            data = json.loads(book.state_file.read_text(encoding="utf-8"))
            if data.get("phase"):
                candidates.append(str(data["phase"]))
        except (OSError, json.JSONDecodeError):
            pass
    try:
        inferred, _n = _infer_phase(series, book.root)
        candidates.append(inferred)
    except OSError:
        pass
    return max(candidates, key=_phase_rank)


def _count_pending_canon(path: Path) -> int:
    if not path.exists():
        return 0
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip().startswith("- ")]
    return len(lines)


def render(status: SeriesStatus) -> str:
    out: list[str] = []
    period = ""
    if status.period.get("start") and status.period.get("end"):
        period = f" ({status.period['start']}-{status.period['end']}"
        if status.period.get("region"):
            period += f" {status.period['region']}"
        period += f", {status.genre})"
    else:
        period = f" ({status.genre})"
    out.append(f"Series: {status.series_name}{period}")
    out.append("")

    if not status.books:
        out.append("  (no books yet; run `autonovel new-book <name>`)")
    else:
        out.append("Books:")
        for b in status.books:
            total = b.chapters_total or b.chapters_drafted
            bar = f"{b.chapters_drafted}/{total} chapters" if total else "0 chapters"
            out.append(f"  {b.name:<14} {b.status:<11} {bar}")
            if b.pending_canon_count:
                out.append(f"                 pending canon: {b.pending_canon_count}")
    out.append("")

    if status.lock_info is not None:
        live = "LIVE" if lock._pid_is_live(status.lock_info.pid) else "STALE"
        out.append(
            f"Lock [{live}]: {status.lock_info.command} (PID {status.lock_info.pid}, "
            f"started {status.lock_info.started_at})"
        )
        if live == "STALE":
            out.append("  Run `autonovel resume` or `/autonovel:resume` to recover.")
        out.append("")

    if status.last_action is not None:
        la = status.last_action
        out.append(f"Last action: {la.command} ({la.finished_at})")
        if la.next_standard_step:
            out.append(f"Next step:   {la.next_standard_step}")
        out.append("")

    if status.recent_log:
        out.append("Recent activity:")
        for entry in status.recent_log[-5:]:
            mark = "OK" if entry.status == "ok" else entry.status.upper()
            out.append(f"  {entry.timestamp}  {entry.command}  {mark}")
    return "\n".join(out)
