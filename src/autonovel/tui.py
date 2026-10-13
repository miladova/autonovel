"""`autonovel tui` — read-only terminal UI for browsing series state.

Surfaced 2026-04-29: with a 24-chapter book, scrolling chat output
isn't a good way to view scores / research / reviews / next-actions.
The right shape is a long-running TUI in a second terminal window
that polls filesystem state and refreshes the view every few
seconds.

Read-only by contract:
  - never acquires `.autonovel/in-progress.lock`
  - never writes any file under `.autonovel/`
  - all state comes from filesystem reads + existing housekeeping
    helpers that are themselves read-only
  - lock state is *displayed* (so the user sees what's running)
    but never modified

Layout (textual TabbedContent):
  Header:   series name · book selector · lock · sweep · cost
  Tabs:     Chapters · Research · Foundation · Front + back matter · Reviews · Commands
  Footer:   q quit · r refresh · 1-6 jump to tab · b switch book

Refresh: 5-second timer + manual `r`. State load is cheap (mtime
+ small JSON/markdown reads); refresh during an active sweep is
fine.

Optional dep: requires `textual>=0.70`. Install via
`pipx inject autonovel '.[tui]'` or `pip install 'autonovel[tui]'`.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

# Textual is an optional extra. Defer the import so the module loads
# even when textual is absent — `autonovel tui` then prints a clear
# install hint instead of a stack trace.
try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.reactive import reactive
    from textual.widgets import (
        DataTable, Footer, Header, Markdown, Select, Static, TabbedContent,
        TabPane,
    )
    _TEXTUAL_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised by the entrypoint
    _TEXTUAL_AVAILABLE = False
    App = object  # type: ignore[misc,assignment]


from . import command_log, lock as lock_mod, project as project_mod
from .adapters.base import discover_commands
from .adapters.installer import _commands_source_dir
from .cost import build_report as build_cost_report
from .housekeeping import next_actions, sweep_progress
from .mechanical.chapter_summary import summarize_chapters
from .mechanical.dashboard import build_dashboard
from .mechanical.research_index import build_index as build_research_index
from .paths import SeriesLayout, load_series


# Module-level cache of every shipped command's frontmatter — read once
# and reused for the live help pane. Loading the source dir is cheap
# but happens often enough to be worth a one-time cache.
_COMMAND_INDEX: dict[str, "object"] | None = None


def _command_index() -> dict[str, object]:
    """Map slash-command name → CommandDef. Loaded lazily; the
    underlying directory hasn't been touched in any session that
    runs the TUI, so this is safe to cache for the process lifetime."""
    global _COMMAND_INDEX
    if _COMMAND_INDEX is None:
        try:
            cmds = discover_commands(_commands_source_dir())
            _COMMAND_INDEX = {c.name: c for c in cmds}
        except Exception:  # noqa: BLE001
            _COMMAND_INDEX = {}
    return _COMMAND_INDEX


# --------------------------------------------------------- state load


def _load_state(series: SeriesLayout, book: str) -> dict:
    """One pass of filesystem read into a flat dict the TUI binds
    against. Cheap; safe to call on a 5-second timer."""
    cfg = project_mod.load(series.project_file)
    book_entry = cfg.book_by_name(book)
    book_root = series.books / book

    # Chapter table — pull from the chapter-summary helper which
    # already merges frontmatter + summary + latest eval into one row.
    rows: list[dict] = []
    tension_drops: list[dict] = []
    try:
        # Pull score + cast + plot + status from chapter-summary
        # helper, then layer tension from dashboard's eval-log
        # reader. dashboard.build_dashboard already reads the
        # per-chapter latest-eval log and extracts tension; we
        # piggyback on it instead of re-parsing the JSON ourselves.
        summary_rows = list(summarize_chapters(book_root))
        try:
            dash = build_dashboard(book_root)
            tension_by_ch = {m.chapter: m.tension for m in dash.metrics}
            tension_drops = [
                {"start": td.start, "end": td.end,
                 "values": td.values}
                for td in dash.tension_drops
            ]
        except Exception:  # noqa: BLE001
            tension_by_ch = {}
        for r in summary_rows:
            rows.append({
                "chapter": r.chapter,
                "pov": r.pov or "",
                "story_time": r.story_time or "",
                "word_count": r.word_count or 0,
                "score": r.score,
                "tension": tension_by_ch.get(r.chapter),
                "location": r.location or "",
                "cast": ", ".join(r.cast) if r.cast else "",
                "plot": r.plot or "",
                "pov_state": r.pov_state or "",
                "threads_opened": r.threads_opened or "",
                "threads_closed": r.threads_closed or "",
                "status": r.status or "",
                "display_status": r.display_status,
                "revision_count": r.revision_count,
                "summary_stale": r.summary_stale,
            })
    except Exception:  # noqa: BLE001
        rows = []

    # Lock state.
    lock_state = "idle"
    try:
        info = lock_mod.read(series.lock_file)
        if info is not None and info.status == "running":
            lock_state = f"🔴 {info.command}"
        elif info is not None and info.status == "interrupted":
            lock_state = "⚠️  interrupted"
    except Exception:  # noqa: BLE001
        pass

    # Sweep progress.
    sweep_str = ""
    try:
        sw = sweep_progress.read(series)
        if sw is not None:
            done = len(sw.completed)
            total = len(sw.chapters)
            sweep_str = f"⏱  {sw.command} {done}/{total}"
    except Exception:  # noqa: BLE001
        pass

    # Cost: today + total.
    cost_today = 0.0
    cost_total = 0.0
    try:
        cr = build_cost_report(series.command_log_file)
        cost_total = cr.total.cost_usd or 0.0
        today = datetime.now(timezone.utc).date().isoformat()
        for entry in command_log.read_all(series.command_log_file):
            if entry.cost_usd and entry.timestamp.startswith(today):
                cost_today += entry.cost_usd
    except Exception:  # noqa: BLE001
        pass

    # Next actions.
    try:
        actions = next_actions.enumerate_actions(series, book=book)
        canonical = next_actions.canonical_pipeline_action(series, book=book)
    except Exception:  # noqa: BLE001
        actions = []
        canonical = None

    # Recent commands.
    try:
        recent = command_log.read_all(series.command_log_file)[-15:]
    except Exception:  # noqa: BLE001
        recent = []

    # Foundation status.
    foundation = {
        "world.md": (series.shared / "world.md").is_file(),
        "characters.md": (series.shared / "characters.md").is_file(),
        "canon.md": (series.shared / "canon.md").is_file(),
        "book_canon.md": (book_root / "canon.md").is_file(),
        "voice.md": (book_root / "voice.md").is_file(),
        "outline.md": (book_root / "outline.md").is_file(),
        "seed.txt": (book_root / "seed.txt").is_file(),
    }

    # Front + back matter.
    front_matter = {
        "title": book_entry.title if book_entry else "",
        "author": (book_entry.author if book_entry else "") or cfg.author or "",
        "preface": (book_root / "preface.md").is_file(),
        "introduction": (book_root / "introduction.md").is_file(),
        "glossary": (book_root / "glossary.md").is_file(),
        "appendix": (book_root / "appendix.md").is_file(),
        "back_cover_image": (book_root / "art" / "back_cover.png").is_file(),
        "preface_words": _word_count_if(book_root / "preface.md"),
        "introduction_words": _word_count_if(book_root / "introduction.md"),
        "glossary_words": _word_count_if(book_root / "glossary.md"),
        "appendix_words": _word_count_if(book_root / "appendix.md"),
    }

    # Reviews.
    edit_logs = book_root / "edit_logs"
    reviews = {
        "reader_panel": (edit_logs / "reader_panel.json").is_file(),
        "opus_review": (edit_logs / "opus_review.md").is_file(),
        "reader_panel_mtime": _mtime_if(edit_logs / "reader_panel.json"),
        "opus_review_mtime": _mtime_if(edit_logs / "opus_review.md"),
    }

    # Pending canon.
    pending = book_root / "pending_canon.md"
    pending_status = "none"
    pending_conflicts = 0
    if pending.is_file():
        text = pending.read_text(encoding="utf-8")
        if "# Conflicts — resolve before next promote-canon" in text:
            pending_conflicts = len(re.findall(
                r"^## Conflict \d+\s*$", text, re.MULTILINE
            ))
            pending_status = f"{pending_conflicts} conflict(s)"
        elif "no new facts" in text.lower():
            pending_status = "clean"
        else:
            pending_status = "pending entries"

    # Research notes.
    try:
        idx = build_research_index(series.root)
        research_notes = [
            {
                "slug": n.slug,
                "title": n.title,
                "updated": n.last_updated,
                "word_count": n.word_count,
                "sources": n.source_count,
                "candidates": n.candidate_canon_count,
            }
            for n in idx.notes
        ]
    except Exception:  # noqa: BLE001
        research_notes = []

    return {
        "series_name": series.root.name,
        "book": book,
        "book_names": [b.name for b in cfg.books],
        "rows": rows,
        "lock_state": lock_state,
        "sweep": sweep_str,
        "cost_today": cost_today,
        "cost_total": cost_total,
        "next_actions": [a.to_dict() for a in actions],
        "canonical_action": canonical.to_dict() if canonical else None,
        "recent": [
            {"command": e.command, "status": e.status,
             "ts": e.timestamp, "cost_usd": e.cost_usd}
            for e in recent
        ],
        "foundation": foundation,
        "front_matter": front_matter,
        "reviews": reviews,
        "pending_canon": pending_status,
        "pending_conflicts": pending_conflicts,
        "research_notes": research_notes,
        "tension_drops": tension_drops,
    }


def _mtime_if(p: Path) -> str:
    if not p.is_file():
        return ""
    return datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")


def _word_count_if(p: Path) -> int:
    if not p.is_file():
        return 0
    try:
        return len(p.read_text(encoding="utf-8").split())
    except OSError:
        return 0


# --------------------------------------------------------- sparkline


_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


_SLASH_COMMAND_RE = re.compile(r"/(autonovel:[A-Za-z0-9_-]+)")


def _extract_slash_command_name(command_str: str) -> str | None:
    """Pull the canonical `autonovel:<name>` slug out of a recommended
    command string like `/autonovel:revise --chapter 5 --book b`.
    Returns None for non-slash commands (e.g. raw `autonovel <subcmd>`
    bash invocations from `next_actions`)."""
    if not command_str:
        return None
    m = _SLASH_COMMAND_RE.search(command_str)
    return m.group(1) if m else None


def _sparkline(values: list[float | None]) -> str:
    """Render a list of optional float values as a unicode sparkline.
    None values render as `·` so missing chapters are visible."""
    real = [v for v in values if v is not None]
    if not real:
        return ""
    lo = min(real)
    hi = max(real)
    span = hi - lo if hi > lo else 1.0
    out: list[str] = []
    for v in values:
        if v is None:
            out.append("·")
            continue
        idx = int((v - lo) / span * (len(_SPARK_BLOCKS) - 1))
        out.append(_SPARK_BLOCKS[idx])
    return "".join(out)


# --------------------------------------------------------- app


if _TEXTUAL_AVAILABLE:

    class AutonovelTUI(App):
        """Read-only series browser. Polls FS every 5 seconds.

        Bindings:
          q       quit
          r       refresh now (don't wait for the timer)
          1-6     jump to tab
          b       cycle to next book in the series
        """

        CSS = """
        Screen { background: $surface; }
        #status_bar {
            dock: top;
            height: 3;
            background: $boost;
            padding: 0 1;
        }
        #status_bar Static { width: 1fr; }
        #chapter_table { height: 1fr; }
        #chapter_detail { width: 40; padding: 0 1; }
        #spark_box { height: 12; padding: 1; border: round $accent; }
        DataTable { height: 1fr; }
        """

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("r", "refresh", "Refresh now"),
            Binding("b", "next_book", "Next book"),
            Binding("p", "toggle_pause", "Pause refresh"),
            Binding("0", "tab(0)", "Help"),
            Binding("1", "tab(1)", "Chapters"),
            Binding("2", "tab(2)", "Research"),
            Binding("3", "tab(3)", "Foundation"),
            Binding("4", "tab(4)", "Front + back matter"),
            Binding("5", "tab(5)", "Reviews"),
            Binding("6", "tab(6)", "Commands"),
        ]

        REFRESH_INTERVAL_SECONDS: float = 5.0

        active_book: reactive[str] = reactive("")
        paused: reactive[bool] = reactive(False)

        def __init__(self, series: SeriesLayout, *,
                      initial_book: str | None = None,
                      poll_interval: float | None = None) -> None:
            super().__init__()
            self.series = series
            self.poll_interval = poll_interval or self.REFRESH_INTERVAL_SECONDS
            cfg = project_mod.load(series.project_file)
            book_names = [b.name for b in cfg.books]
            self.active_book = initial_book or (book_names[0] if book_names else "")
            self._book_names = book_names
            self._state: dict = {}

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="status_bar"):
                yield Static("", id="status_series")
                yield Static("", id="status_lock")
                yield Static("", id="status_sweep")
                yield Static("", id="status_cost")
            with TabbedContent(initial="tab_chapters"):
                with TabPane("Help (live)", id="tab_help"):
                    with VerticalScroll():
                        yield Markdown("", id="help_md")
                with TabPane("Chapters", id="tab_chapters"):
                    with Horizontal():
                        with Vertical():
                            yield DataTable(id="chapter_table",
                                             cursor_type="row")
                            yield Static("", id="spark_box")
                        with VerticalScroll(id="chapter_detail"):
                            yield Markdown("", id="chapter_detail_md")
                with TabPane("Research", id="tab_research"):
                    with Horizontal():
                        yield DataTable(id="research_table",
                                         cursor_type="row")
                        with VerticalScroll(id="research_detail"):
                            yield Markdown("", id="research_detail_md")
                with TabPane("Foundation", id="tab_foundation"):
                    yield Markdown("", id="foundation_md")
                with TabPane("Front + back matter", id="tab_front_matter"):
                    yield Markdown("", id="front_matter_md")
                with TabPane("Reviews", id="tab_reviews"):
                    yield Markdown("", id="reviews_md")
                with TabPane("Commands", id="tab_commands"):
                    yield Markdown("", id="commands_md")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#chapter_table", DataTable)
            table.add_columns("ch", "words", "pov", "story_time", "score", "status")
            rt = self.query_one("#research_table", DataTable)
            rt.add_columns("slug", "title", "updated", "words", "sources", "cands")
            self.refresh_state()
            self.set_interval(self.poll_interval, self._on_timer_refresh)

        def action_refresh(self) -> None:
            self.refresh_state()

        def action_toggle_pause(self) -> None:
            """Pause auto-refresh so the user can read prose / copy
            text out of a panel without the cursor / row order
            jumping around. Press `p` again to resume; `r` still
            refreshes manually while paused."""
            self.paused = not self.paused
            self._render_status_bar()

        def action_next_book(self) -> None:
            if not self._book_names:
                return
            try:
                i = self._book_names.index(self.active_book)
            except ValueError:
                i = 0
            self.active_book = self._book_names[(i + 1) % len(self._book_names)]
            self.refresh_state()

        def action_tab(self, idx: int) -> None:
            tabs = self.query_one(TabbedContent)
            ids = ["tab_help", "tab_chapters", "tab_research",
                   "tab_foundation", "tab_front_matter", "tab_reviews",
                   "tab_commands"]
            if 0 <= idx < len(ids):
                tabs.active = ids[idx]

        def refresh_state(self) -> None:
            # Auto-refresh tick is suppressed while paused; the manual
            # `r` action calls refresh_state() directly so that path
            # still works.
            try:
                state = _load_state(self.series, self.active_book)
            except Exception as e:  # noqa: BLE001 — TUI must not crash
                state = {"_error": str(e)}
            self._state = state
            # Capture every VerticalScroll's scroll_y BEFORE re-rendering
            # so we can restore them after. Without this, refreshing a
            # research note preview at line 200 snaps you back to line
            # 0 every 5 s — the same UX bug as the cursor-reset, just
            # in the scrollers instead of the tables.
            saved_scrolls: dict[str, float] = {}
            for sid in ("chapter_detail", "research_detail"):
                try:
                    w = self.query_one(f"#{sid}", VerticalScroll)
                    saved_scrolls[sid] = w.scroll_y
                except Exception:  # noqa: BLE001
                    pass
            self._render_status_bar()
            self._render_help()
            self._render_chapters()
            self._render_research()
            self._render_foundation()
            self._render_front_matter()
            self._render_reviews()
            self._render_commands()
            # Restore scroll positions. The new content's height may be
            # smaller than the old; clamp to the new scroll range so we
            # don't end up scrolled past the bottom.
            for sid, y in saved_scrolls.items():
                try:
                    w = self.query_one(f"#{sid}", VerticalScroll)
                    self.call_after_refresh(
                        lambda w=w, y=y: w.scroll_to(y=y, animate=False)
                    )
                except Exception:  # noqa: BLE001
                    pass

        def _on_timer_refresh(self) -> None:
            """Timer-driven refresh — skipped while paused so the
            user can read or copy without the view churning."""
            if self.paused:
                return
            self.refresh_state()

        # ------------------------------------------------- renderers

        def _render_status_bar(self) -> None:
            s = self._state
            self.query_one("#status_series", Static).update(
                f"📚 {s.get('series_name', '?')} / {self.active_book}"
            )
            paused_marker = "  ⏸ paused" if self.paused else ""
            self.query_one("#status_lock", Static).update(
                f"⚪ {s.get('lock_state', 'idle')}{paused_marker}"
            )
            self.query_one("#status_sweep", Static).update(s.get("sweep", ""))
            today = s.get("cost_today", 0.0)
            total = s.get("cost_total", 0.0)
            self.query_one("#status_cost", Static).update(
                f"💵 ${today:.2f} today · ${total:.2f} total"
            )

        def _render_chapters(self) -> None:
            table = self.query_one("#chapter_table", DataTable)
            # Preserve the cursor row across refresh so reading a
            # specific chapter doesn't reset to row 0 every 5 s.
            prior_cursor = table.cursor_row if table.row_count else 0
            table.clear()
            rows = self._state.get("rows", [])
            for r in rows:
                # Use display_status (e.g. "revised ×6") rather than
                # the raw frontmatter `status:` so the user sees how
                # many times the chapter has been re-evaluated. The
                # revision count is derived from eval-log file count,
                # not the LLM's self-reported status string — honest.
                status_cell = (r.get("display_status") or r.get("status") or "")[:14]
                if r.get("summary_stale"):
                    status_cell = (status_cell + " ⚠")[:16]
                table.add_row(
                    str(r.get("chapter", "")),
                    str(r.get("word_count", 0)),
                    str(r.get("pov", ""))[:12],
                    str(r.get("story_time", ""))[:10],
                    f"{r['score']:.1f}" if r.get("score") is not None else "—",
                    status_cell,
                )
            # Restore cursor row (clamped to new row count).
            if rows:
                target = min(prior_cursor, len(rows) - 1)
                try:
                    table.move_cursor(row=target)
                except Exception:  # noqa: BLE001 — cursor restoration is decorative
                    pass
            scores = [r.get("score") for r in rows]
            tensions = [r.get("tension") for r in rows]
            real_scores = [s for s in scores if s is not None]
            real_tensions = [t for t in tensions if t is not None]
            score_spark = _sparkline(scores)
            tension_spark = _sparkline(tensions)
            n_eval = len(real_scores)
            n_total = len(scores)
            below = sum(1 for s in real_scores if s < 7.0)
            score_stats = ""
            if real_scores:
                score_stats = (
                    f" range {min(real_scores):.1f}–{max(real_scores):.1f}"
                    f" mean {sum(real_scores)/len(real_scores):.2f}"
                    f" · {below} below 7.0"
                )
            tension_stats = ""
            if real_tensions:
                tension_stats = (
                    f" range {min(real_tensions):.1f}–{max(real_tensions):.1f}"
                    f" mean {sum(real_tensions)/len(real_tensions):.2f}"
                )
            else:
                tension_stats = " (no whole-book eval — run /autonovel:evaluate --full)"
            drops = self._state.get("tension_drops", []) or []
            drops_line = ""
            if drops:
                ranges = ", ".join(
                    f"ch{d['start']}→ch{d['end']}" for d in drops
                )
                drops_line = (
                    f"\n  ⚠️  Tension drops (≥3 consecutive declines): {ranges}"
                )
            stale_count = sum(1 for r in rows if r.get("summary_stale"))
            stale_legend = ""
            if stale_count:
                stale_legend = (
                    f"\n  ⚠ next to status (status column): chapter "
                    f"`.md` is newer than its `.summary.md`. The "
                    f"rolling-context surface every drafter reads is "
                    f"out of date. Fix: `/autonovel:summarize-chapter "
                    f"--stale --book {self.active_book}` (refreshes all "
                    f"{stale_count} stale chapter(s)). Continuity-"
                    f"critical."
                )
            self.query_one("#spark_box", Static).update(
                f"Score   {score_spark}{score_stats}\n"
                f"Tension {tension_spark}{tension_stats}\n"
                f"  Score = overall_score from per-chapter evaluate "
                f"(0–10, ≥7 = above threshold).\n"
                f"  Tension = `tension` dimension from /autonovel:evaluate "
                f"--full (0–10, higher = more pull-through).\n"
                f"  · = chapter has no eval data yet."
                f"  ({n_eval} of {n_total} chapters evaluated; "
                f"pending canon: {self._state.get('pending_canon', 'none')})"
                + drops_line
                + stale_legend
            )
            # Restore detail view to the previously-cursored chapter.
            if rows:
                target = min(prior_cursor, len(rows) - 1)
                self._render_chapter_detail(rows[target])

        def _render_chapter_detail(self, row: dict) -> None:
            md = self.query_one("#chapter_detail_md", Markdown)
            ch = row.get("chapter", "?")
            score = row.get("score")
            score_line = f"{score:.2f}" if score is not None else "—"
            stale_banner = ""
            if row.get("summary_stale"):
                stale_banner = (
                    "\n> ⚠️  **Summary is stale** — chapter file is "
                    "newer than `.summary.md`. The rolling-context "
                    "surface downstream drafters read is out of date. "
                    "Re-run `/autonovel:summarize-chapter` or revise "
                    "again (revise step 9 regenerates the summary).\n"
                )
            sections: list[str] = [
                f"## Chapter {ch}",
                "",
                f"- **POV:** {row.get('pov') or '—'}",
                f"- **Story time:** {row.get('story_time') or '—'}",
                f"- **Location:** {row.get('location') or '—'}",
                f"- **Words:** {row.get('word_count', 0)}",
                f"- **Score:** {score_line}",
                f"- **Status:** {row.get('display_status') or row.get('status') or '—'}"
                + (f"  (raw frontmatter: `{row.get('status')}`)"
                    if row.get('display_status') and row.get('display_status') != row.get('status')
                    else ""),
                stale_banner,
                "### Cast",
                row.get("cast") or "—",
                "",
                "### Plot",
                row.get("plot") or "—",
                "",
                "### POV state at close",
                row.get("pov_state") or "_(summary doesn't include POV state — older format or partial summary)_",
                "",
                "### Threads opened",
                row.get("threads_opened") or "_(none recorded)_",
                "",
                "### Threads closed",
                row.get("threads_closed") or "_(none recorded)_",
            ]
            md.update("\n".join(sections))

        def on_data_table_row_highlighted(
            self, message
        ) -> None:
            if message.data_table.id == "chapter_table":
                row_idx = message.cursor_row
                rows = self._state.get("rows", [])
                if 0 <= row_idx < len(rows):
                    self._render_chapter_detail(rows[row_idx])
            elif message.data_table.id == "research_table":
                row_idx = message.cursor_row
                notes = self._state.get("research_notes", [])
                if 0 <= row_idx < len(notes):
                    self._render_research_detail(notes[row_idx])

        def _render_research(self) -> None:
            rt = self.query_one("#research_table", DataTable)
            # Preserve cursor row across refresh — same fix as the
            # chapter table; the user shouldn't lose their place
            # while reading a note.
            prior_cursor = rt.cursor_row if rt.row_count else 0
            rt.clear()
            notes = self._state.get("research_notes", [])
            for n in notes:
                rt.add_row(
                    n["slug"][:30],
                    (n.get("title") or "")[:40],
                    n.get("updated") or "—",
                    str(n.get("word_count", 0)),
                    str(n.get("sources", 0)),
                    str(n.get("candidates", 0)),
                )
            if notes:
                target = min(prior_cursor, len(notes) - 1)
                try:
                    rt.move_cursor(row=target)
                except Exception:  # noqa: BLE001
                    pass
                self._render_research_detail(notes[target])

        def _render_research_detail(self, note: dict) -> None:
            md = self.query_one("#research_detail_md", Markdown)
            slug = note.get("slug", "")
            path = self.series.root / "shared" / "research" / "notes" / f"{slug}.md"
            if path.is_file():
                # Cap the preview to keep render snappy.
                text = path.read_text(encoding="utf-8")
                if len(text) > 8000:
                    text = text[:8000] + "\n\n_… (truncated; open the file directly for the rest)_"
                md.update(text)
            else:
                md.update("_(file not found)_")

        def _render_foundation(self) -> None:
            f = self._state.get("foundation", {})
            tick = lambda b: "✅" if b else "❌"  # noqa: E731
            text = (
                "## Foundation status\n\n"
                f"- **Series-shared**\n"
                f"  - {tick(f.get('world.md'))} `shared/world.md`\n"
                f"  - {tick(f.get('characters.md'))} `shared/characters.md`\n"
                f"  - {tick(f.get('canon.md'))} `shared/canon.md`\n\n"
                f"- **Per-book ({self.active_book})**\n"
                f"  - {tick(f.get('book_canon.md'))} `canon.md` (book-scoped facts)\n"
                f"  - {tick(f.get('voice.md'))} `voice.md`\n"
                f"  - {tick(f.get('outline.md'))} `outline.md`\n"
                f"  - {tick(f.get('seed.txt'))} `seed.txt`\n\n"
                f"_Pending canon:_ {self._state.get('pending_canon', 'none')}\n"
            )
            self.query_one("#foundation_md", Markdown).update(text)

        def _render_front_matter(self) -> None:
            fm = self._state.get("front_matter", {})
            tick = lambda b: "✅" if b else "❌"  # noqa: E731

            def line(present_key: str, words_key: str, file_name: str,
                      role: str, command_hint: str) -> str:
                present = fm.get(present_key)
                marker = tick(present)
                if present:
                    words = fm.get(words_key, 0)
                    return (f"- {marker} `{file_name}` ({role}) — "
                            f"{words} words")
                return (f"- {marker} `{file_name}` ({role}) — "
                        f"run `{command_hint}` to create")

            text = (
                "## Title page\n\n"
                f"- **Title:** {fm.get('title') or '— (run `/autonovel:title --book <name>`)'}\n"
                f"- **Author:** {fm.get('author') or '— (run `autonovel onboard <name>` or set in project.yaml)'}\n"
                "\n"
                "## Front matter (before chapter 1)\n\n"
                + line("preface", "preface_words", "preface.md",
                        "user-authored",
                        "/autonovel:introduction --from user --book <name>")
                + "\n"
                + line("introduction", "introduction_words",
                        "introduction.md", "AI-drafted essay",
                        "/autonovel:introduction --from auto --book <name>")
                + "\n"
                + line("glossary", "glossary_words", "glossary.md",
                        "period-vocabulary reference",
                        "/autonovel:glossary --book <name> --from auto")
                + "\n"
                "\n"
                "## Back matter (after the last chapter)\n\n"
                + line("appendix", "appendix_words", "appendix.md",
                        "timeline / bios / sources / notes",
                        "/autonovel:appendix --book <name> --sections timeline,bios")
                + "\n"
                f"- {tick(fm.get('back_cover_image'))} "
                f"`art/back_cover.png` (full-bleed back-cover image) — "
                f"{'present; renders as a full-page image after the colophon' if fm.get('back_cover_image') else 'drop a PNG at this path to add a back-cover image to the PDF (printed wraparound is a separate flow via `/autonovel:cover-print`)'}"
                "\n"
                "\n"
                "_Order in the typeset PDF:_ Title page → Preface → "
                "Introduction → Glossary → chapters → Appendix → "
                "colophon → back-cover image. Each item is optional; "
                "absence is respected by the typeset front-/back-matter "
                "builder via `\\IfFileExists` guards."
            )
            self.query_one("#front_matter_md", Markdown).update(text)

        def _render_reviews(self) -> None:
            r = self._state.get("reviews", {})
            tick = lambda b: "✅" if b else "❌"  # noqa: E731
            text = (
                "## Reviews\n\n"
                f"- {tick(r.get('reader_panel'))} `reader_panel.json` "
                f"(four-persona) — last run: "
                f"{r.get('reader_panel_mtime') or '—'}\n"
                f"- {tick(r.get('opus_review'))} `opus_review.md` "
                f"(dual-persona Opus) — last run: "
                f"{r.get('opus_review_mtime') or '—'}\n\n"
                "Run `/autonovel:reader-panel --book <name>` and "
                "`/autonovel:review --book <name>` after a substantive "
                "revision sweep — both are stale by default once any "
                "chapter changed.\n"
            )
            self.query_one("#reviews_md", Markdown).update(text)

        def _render_help(self) -> None:
            """Live help: for each suggested next command, show why,
            what it reads, what it writes. Pulls reads:/writes: from
            the command frontmatter so the user knows exactly which
            artifacts the command will touch before running it."""
            actions = self._state.get("next_actions", [])
            canonical = self._state.get("canonical_action")
            parts: list[str] = []
            parts.append(f"# Live help — `{self.active_book}`\n")
            parts.append(
                "The TUI is read-only — running commands still happens "
                "in your runtime (Claude Code / Codex / Gemini) in a "
                "different terminal. This pane previews **what each "
                "suggested command will do**, **why it's suggested**, "
                "and **which artifacts it will read or change** so you "
                "can decide before invoking.\n"
                "\n"
                "**Topic-based reference (in your runtime):** "
                "`/autonovel:help` lists every category; "
                "`/autonovel:help art` walks the art workflow with the "
                "exact command sequence (typographic-only, "
                "pollinations, wikimedia, fal/replicate/openai). Other "
                "topics: `foundation`, `drafting`, `revising`, "
                "`typeset`, `research`, `front-matter`, `sweeps`, "
                "`tui`, `cli`, `next-steps`.\n"
            )
            # Per-book context summary.
            parts.append("## Where you are")
            rows = self._state.get("rows", [])
            scored = [r for r in rows if r.get("score") is not None]
            below = [r for r in scored if r.get("score", 10) < 7.0]
            parts.append(
                f"- **{len(rows)}** chapter(s); "
                f"**{len(scored)}** evaluated; "
                f"**{len(below)}** below threshold.\n"
                f"- Pending canon: **{self._state.get('pending_canon', 'none')}**.\n"
                f"- Lock: {self._state.get('lock_state', 'idle')}.\n"
                f"- Sweep: {self._state.get('sweep') or '_(none in flight)_'}.\n"
            )
            parts.append("")
            parts.append("## Suggested next commands")
            if not actions and not canonical:
                parts.append("_Series is clean — nothing situational queued._\n")
            for a in actions:
                self._append_command_help(parts, a, prefix="")
            if canonical:
                parts.append("\n### Canonical pipeline next step")
                self._append_command_help(parts, canonical, prefix="(default)")
            parts.append(
                "\n---\n"
                "## Reading the Chapters tab\n\n"
                "The Chapters tab shows two **sparklines** at the bottom — "
                "the *shape* of the book at a glance:\n\n"
                "- **Score** — overall_score from per-chapter "
                "`/autonovel:evaluate`. 0–10 scale; 10 best; threshold "
                "is 7.0. Anything below 7.0 is a `revise` candidate. "
                "Stats line shows range / mean / count below threshold.\n"
                "- **Tension** — `tension` dimension from "
                "`/autonovel:evaluate --full`. 0–10 scale; higher = "
                "more pull-through (the reader can't put it down). If "
                "you haven't run `--full` yet, the line says so. A "
                "`⚠️  Tension drops` line surfaces any range of ≥3 "
                "consecutive declining chapters — same as the dashboard "
                "alarm.\n"
                "- A `·` block in either row means that chapter has no "
                "eval data yet for that dimension. Run "
                "`/autonovel:evaluate --chapter N` (single) or "
                "`--full` (whole book) to fill them in.\n\n"
                "**Cursor and scroll are preserved across refresh** — "
                "highlight chapter 14, walk away for coffee, come back "
                "to chapter 14 still highlighted (not chapter 1). Same "
                "for the chapter detail and research note preview "
                "panes: scroll position survives the 5 s tick.\n\n"
                "**Front + back matter tab** lists every front-/back-"
                "matter file the typeset PDF assembles, in render "
                "order (preface → introduction → glossary → chapters "
                "→ appendix → colophon). Each row shows ✅ or ❌ for "
                "presence, the word count when present, and the "
                "exact slash-command to create it when absent. "
                "/autonovel:typeset auto-skips missing files via "
                "`\\IfFileExists` guards — no need to scaffold every "
                "one.\n\n"
                "**Status column** uses a canonical scheme:\n\n"
                "- `drafted` — initial draft; never re-evaluated.\n"
                "- `revised ×N` — re-evaluated N times after the "
                "initial draft. The count is derived from eval-log "
                "file count (mechanical, can't be hallucinated), "
                "NOT the LLM's self-reported `status:` string. "
                "If you see `revised-v6` or similar, that's a legacy "
                "frontmatter value passed through verbatim — the "
                "chapter detail pane shows both forms when they "
                "differ.\n"
                "- `imported` — externally-imported manuscript "
                "(via `/autonovel:import-book`); the autonovel "
                "draft→revise cycle hasn't been applied.\n\n"
                "**Stale-summary indicator (`⚠` after status):** the "
                "chapter's `.md` mtime is newer than its `.summary.md` "
                "— revise didn't regenerate the summary, so the "
                "rolling-context surface every downstream drafter "
                "reads is out of date. Continuity-critical: the next "
                "chapter's drafter sees the OLD cast / threads / POV "
                "state. Fix with `/autonovel:summarize-chapter "
                "<N> --force` or just `/autonovel:revise --chapter N` "
                "(revise step 9 regenerates the summary as part of "
                "the rewrite). The Help tab's suggested-commands list "
                "surfaces this as HIGH priority via "
                "`/autonovel:next`'s situational signal.\n\n"
                "**Reading the chapter detail (right pane):** shows "
                "every section the per-chapter summary captures — POV / "
                "Story time / Location / Words / Score / Status / Cast "
                "on stage / Plot / POV state at close / Threads opened "
                "/ Threads closed. If a section reads "
                "_(summary doesn't include POV state — older format or "
                "partial summary)_, that chapter's summary predates the "
                "current 7-section template; backfill with "
                "`/autonovel:summarize-chapter <N> --force` to refresh.\n\n"
                "## Keyboard\n\n"
                "- **`r`** — refresh now (don't wait for the 5 s timer)\n"
                "- **`p`** — pause / resume auto-refresh. Pause when "
                "you're reading a long research note or copying text "
                "out of a panel; the `⏸ paused` indicator shows in the "
                "header.\n"
                "- **`b`** — switch to the next book in the series\n"
                "- **`0`–`6`** — jump to a tab (Help, Chapters, "
                "Research, Foundation, Front + back matter, Reviews, Commands)\n"
                "- **`q`** — quit\n\n"
                "## Copy / paste from the TUI\n\n"
                "Textual captures mouse events by default, which "
                "blocks normal terminal selection. Two workarounds:\n\n"
                "1. **Hold `shift` while dragging** — most terminals "
                "(GNOME Terminal, iTerm2, Windows Terminal, kitty, "
                "Alacritty) bypass the app's mouse capture under "
                "shift, so the selection goes through to the terminal "
                "and Ctrl+Shift+C / Cmd+C copies it. This is the path "
                "that works everywhere.\n"
                "2. **Press `p` first** to pause auto-refresh, so the "
                "view isn't redrawn while you're selecting. Then "
                "shift+drag, copy, and resume with `p`.\n\n"
                "_To act on any of the suggested commands above, copy "
                "the command into your runtime. The TUI will pick up "
                "the resulting state on the next refresh (5 s) — "
                "press `r` to refresh now._\n"
            )
            self.query_one("#help_md", Markdown).update(
                "\n".join(parts)
            )

        def _append_command_help(self, parts: list[str], action: dict,
                                   *, prefix: str = "") -> None:
            cmd = action.get("command") or ""
            title = action.get("title", "")
            rationale = action.get("rationale", "")
            priority = action.get("priority", "")
            marker = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢",
                       "INFO": "⚪"}.get(priority, "·")
            slug = _extract_slash_command_name(cmd)
            cdef = _command_index().get(slug) if slug else None
            heading = (f"### {marker} {title}" +
                        (f" {prefix}" if prefix else ""))
            parts.append(heading)
            if cmd:
                parts.append(f"```\n{cmd}\n```")
            if rationale:
                parts.append(f"**Why:** {rationale}")
            if cdef is not None:
                reads = list(getattr(cdef, "reads", []) or [])
                writes = list(getattr(cdef, "writes", []) or [])
                description = getattr(cdef, "description", "") or ""
                tier = getattr(cdef, "model_tier", "") or ""
                if description:
                    parts.append(f"**What it does:** {description}")
                if tier:
                    parts.append(f"**Model tier:** `{tier}` "
                                 f"(`light` ≈ Haiku · `standard` ≈ "
                                 f"Sonnet · `heavy` ≈ Opus)")
                if reads:
                    parts.append("**Reads:**")
                    for r in reads:
                        parts.append(f"  - `{r}`")
                if writes:
                    parts.append("**Writes:**")
                    for w in writes:
                        parts.append(f"  - `{w}`")
                else:
                    parts.append("**Writes:** _(read-only — no files changed)_")
            else:
                parts.append(
                    "_(no frontmatter found for this command — "
                    "it may be a `bash` invocation rather than a "
                    "slash-command)_"
                )
            parts.append("")

        def _render_commands(self) -> None:
            recent = self._state.get("recent", [])
            actions = self._state.get("next_actions", [])
            canonical = self._state.get("canonical_action")
            text_parts: list[str] = ["## Recent commands\n"]
            if recent:
                for r in reversed(recent):
                    cost_str = (
                        f" ({r['cost_usd']:.4f}$)"
                        if r.get("cost_usd") else ""
                    )
                    text_parts.append(
                        f"- `{r.get('ts', '')[:16]}` "
                        f"`/{r.get('command', '?')}` "
                        f"[{r.get('status', '?')}]{cost_str}"
                    )
            else:
                text_parts.append("_No commands logged yet._")
            text_parts.append("\n## Next actions\n")
            if actions:
                for a in actions:
                    marker = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢",
                                "INFO": "⚪"}.get(a.get("priority", ""), "·")
                    cmd = a.get("command")
                    text_parts.append(
                        f"- {marker} **{a.get('title', '')}**"
                        + (f"\n  - `{cmd}`" if cmd else "")
                    )
            else:
                text_parts.append("_No situational actions queued._")
            if canonical:
                text_parts.append("\n### Canonical pipeline next step\n")
                text_parts.append(f"- {canonical.get('title', '')}")
                if canonical.get("command"):
                    text_parts.append(f"  - `{canonical['command']}`")
            self.query_one("#commands_md", Markdown).update(
                "\n".join(text_parts)
            )

else:

    class AutonovelTUI:  # type: ignore[no-redef]
        """Stub when textual is unavailable. Constructed only by tests
        that don't import textual."""
        def __init__(self, series, **kwargs):
            self.series = series


# --------------------------------------------------------- entrypoint


def run_tui(series: SeriesLayout | None = None,
             initial_book: str | None = None) -> int:
    if not _TEXTUAL_AVAILABLE:
        print(
            "error: `autonovel tui` requires the `textual` package.\n"
            "Install via:\n"
            "  pip install 'autonovel[tui]'   # if you installed via pip\n"
            "  pipx inject autonovel textual  # if you installed via pipx",
        )
        return 2
    if series is None:
        series = load_series()
    AutonovelTUI(series, initial_book=initial_book).run()
    return 0
