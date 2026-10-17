"""Tier-1 tests for `autonovel.mechanical.story_map` — the
/autonovel:story-map reading surface (synopsis, thread grid +
escalation curve, characters, timeline, places)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from autonovel.housekeeping import scaffold
from autonovel.mechanical.__main__ import main as mechanical_main
from autonovel.mechanical.chapter_summary import (
    _index_latest_per_chapter_eval,
    parse_summary_sections,
)
from autonovel.mechanical.pov_bleed import parse_cast, parse_cast_ordered
from autonovel.mechanical.story_map import (
    THREADS_LEDGER_HEADER,
    build_story_map,
    parse_outline,
    parse_story_time,
    parse_threads_ledger,
    render_grid_text,
    render_html,
    write_story_map,
)


# ---------------------------------------------------------- helpers


def _series(tmp_path: Path, book: str = "b") -> tuple[Path, Path]:
    res = scaffold.new_series(tmp_path / "s", series_name="s")
    scaffold.new_book(res.series, book_name=book, pov="Jakob Fugger")
    root = res.series.root
    return root, root / "books" / book


def _chapter(book_root: Path, n: int, *, story_time: str = "", pov: str = "Jakob Fugger",
             title: str = "", events: str = "[]", words: int = 3000) -> None:
    ch = book_root / "chapters"
    ch.mkdir(parents=True, exist_ok=True)
    fm = [f"book: {book_root.name}", f"chapter: {n}", f"pov: {pov}"]
    if title:
        fm.append(f"title: {title}")
    if story_time:
        fm.append(f"story_time: {story_time}")
    fm += [f"events: {events}", "status: drafted", f"word_count: {words}"]
    (ch / f"ch_{n:02d}.md").write_text("---\n" + "\n".join(fm) + "\n---\n\nProse.\n",
                                       encoding="utf-8")


def _summary(book_root: Path, n: int, *, plot: str, cast: str = "Jakob (POV)",
             pov_state: str = "", location: str = "", opened: str = "", closed: str = "",
             story_time: str = "") -> None:
    lines = [f"**Location:** {location}" if location else "",
             f"**Plot:** {plot}",
             f"**POV state:** {pov_state}" if pov_state else "",
             f"**Cast on stage:** {cast}",
             f"**Threads opened:** {opened}" if opened else "",
             f"**Threads closed:** {closed}" if closed else "",
             f"**Story time:** {story_time}" if story_time else ""]
    (book_root / "chapters" / f"ch_{n:02d}.summary.md").write_text(
        "\n\n".join(x for x in lines if x) + "\n", encoding="utf-8")


def _eval(book_root: Path, n: int, ts: str, **fields) -> None:
    d = book_root / "eval_logs"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{ts}_ch{n:02d}.json").write_text(json.dumps(fields), encoding="utf-8")


OUTLINE_WITH_ACTS = """# Outline

Working notes.

---

## ACT ONE — VENICE (1473–1478): the school of secrets

The spine under the first act.

Second paragraph of the act note.

## Chapter 1 — Weapons at the Gate
- story_time: 1473-09
- events: [E-009]
- beats:
  - Jakob arrives.

## Chapter 2 — The Biscuit Book
- story_time: 1474-06
- events: []

---

## ACT TWO — TYROL (1485–1490): the first prince

## Chapter 3 — The Coin-Rich Prince
- story_time: 1485-03 to 1485-11
- events: [E-009, E-010]
"""


# ---------------------------------------------------------- synopsis


def test_synopsis_in_reading_order_with_anchors(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    for n in (3, 1, 2):     # created out of order on purpose
        _chapter(book, n, story_time=f"147{n}-01", title=f"Title {n}")
        _summary(book, n, plot=f"Plot of chapter {n}. More happens.",
                 pov_state=f"State after {n}.")
    sm = build_story_map(book)
    assert [c.chapter for c in sm.chapters] == [1, 2, 3]
    html = render_html(sm)
    anchors = [m.group(1) for m in re.finditer(r'id="ch-(\d+)"', html)]
    assert anchors == ["1", "2", "3"]
    pos = [html.index(f"Plot of chapter {n}.") for n in (1, 2, 3)]
    assert pos == sorted(pos)
    assert "Title 2" in html
    assert "At the close: State after 2." in html
    # The full Plot paragraph, not just its first sentence.
    assert "Plot of chapter 1. More happens." in html
    assert sm.synopsis_words == 3 * 6
    assert sm.synopsis_minutes == 1


def test_act_headers_from_outline(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    (book / "outline.md").write_text(OUTLINE_WITH_ACTS, encoding="utf-8")
    for n in (1, 2, 3):
        _chapter(book, n)
        _summary(book, n, plot=f"Plot {n}.")
    sm = build_story_map(book)
    assert [a.title for a in sm.acts] == [
        "ACT ONE — VENICE (1473–1478): the school of secrets",
        "ACT TWO — TYROL (1485–1490): the first prince",
    ]
    assert [c.act for c in sm.chapters] == [0, 0, 1]
    assert sm.acts[0].short == "Act One"
    assert "The spine under the first act." in sm.acts[0].intro
    html = render_html(sm)
    act1, act2 = html.index("ACT ONE — VENICE"), html.index("ACT TWO — TYROL")
    assert act1 < html.index('id="ch-1"') < html.index('id="ch-2"') < act2 < html.index('id="ch-3"')
    # Outline titles stand in when the frontmatter has none.
    assert sm.chapters[0].title == "Weapons at the Gate"


def test_parse_outline_h3_chapters_under_acts() -> None:
    info = parse_outline("# Outline\n\n## Part One — Home\n\nIntro.\n\n"
                         "### Chapter 1 — Leaving\n- story_time: 1500\n\n"
                         "## Part Two — Away\n\n### Chapter 2: Arriving\n- events: [E-1]\n")
    assert [a.title for a in info.acts] == ["Part One — Home", "Part Two — Away"]
    assert info.acts[0].intro == "Intro."
    assert info.chapter_act == {1: 0, 2: 1}
    assert info.chapter_titles == {1: "Leaving", 2: "Arriving"}
    assert info.chapter_events[2] == ["E-1"]


def test_parse_outline_story_time_and_events() -> None:
    info = parse_outline(OUTLINE_WITH_ACTS)
    assert info.chapter_story_time[3] == "1485-03 to 1485-11"
    assert info.chapter_events == {1: ["E-009"], 2: [], 3: ["E-009", "E-010"]}
    assert info.chapter_titles[2] == "The Biscuit Book"


# ---------------------------------------------------------- threads


def test_thread_grid_from_outline_events(tmp_path: Path) -> None:
    root, book = _series(tmp_path)
    (book / "outline.md").write_text(OUTLINE_WITH_ACTS, encoding="utf-8")
    (root / "shared" / "events.md").write_text(
        "# Events ledger\n\n## E-009: Jakob arrives in Venice\n- date: 1473-09\n"
        "- rendered_in:\n    b/ch_03: Jakob, remembering the gate\n    other/ch_01: elsewhere\n\n"
        "## E-010: Jubilee Rome\n- date: 1500\n",
        encoding="utf-8")
    for n in (1, 2, 3):
        _chapter(book, n)
        _summary(book, n, plot=f"Plot {n}.")
    sm = build_story_map(book, series_root=root)
    assert sm.thread_source == "outline events"
    names = [t.name for t in sm.threads]
    assert names == ["E-009 · Jakob arrives in Venice", "E-010 · Jubilee Rome"]
    e9 = sm.threads[0]
    assert e9.chapters == [1, 3]
    assert e9.notes_for(3)[0].note == "Jakob, remembering the gate"
    assert e9.cell_role(1) == "touch" and e9.cell_role(2) is None
    grid = render_grid_text(sm)
    assert "o.o" in grid.splitlines()[-2]          # E-009 row: ch 1 and ch 3
    html = render_html(sm)
    assert "event ids, not plot threads" in html


def test_thread_grid_from_outline_threads_ledger(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    (book / "outline.md").write_text(
        OUTLINE_WITH_ACTS + "\n## Threads\n\n"
        "- Plant ch_01 / Payoff ch_03: the sewn letter\n\n"
        "### Thread: The steward's register\n"
        "- Description: Who reads the register?\n"
        "- Plant: ch_01 — Negro writes Jakob's name\n"
        "- Turn: ch_02 — Negro knows the winnings\n"
        "- Payoff: ch_03 — Jakob buys Negro\n"
        "- Consequence: the letters come north\n",
        encoding="utf-8")
    for n in (1, 2, 3):
        _chapter(book, n)
        _summary(book, n, plot=f"Plot {n}.")
    sm = build_story_map(book)
    assert sm.thread_source == "outline.md ## Threads"
    by = {t.name: t for t in sm.threads}
    assert by["the sewn letter"].cell_role(1) == "plant"
    assert by["the sewn letter"].cell_role(3) == "payoff"
    reg = by["The steward's register"]
    assert reg.question == "Who reads the register?"
    assert reg.consequence == "the letters come north"
    assert [(t.chapter, t.role) for t in reg.touches] == [(1, "plant"), (2, "turn"), (3, "payoff")]


LEDGER = THREADS_LEDGER_HEADER.format(book="b") + """
## Thread: Michaelmas clock
- question: Can Jakob put the 300 back in time?
- ch 1 plant: Jakob promises the 300 by Michaelmas.
- ch 2 turn: Pepper rises; he borrows.
- ch 3 payoff: The 300 stands in the book.
- ch 3 touch: Trevisan repaid.
- ch 4

## Thread: Negro's register
- ch_01 plant: the register
- Ch5 touch: still writing
- chap 6 payoff — malformed on purpose

## Character: Jakob Fugger
- aliases: Jakob
- arc: From boy to banker.
- ch 1: Wants a place; loses his knife.
- arc and nonsense line

## Some other tool's section
- anything at all here is ignored

## Places
- Venice: Rialto
- Augsburg
"""


def test_threads_md_ledger_plant_turn_payoff(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    (book / "outline.md").write_text(
        OUTLINE_WITH_ACTS + "\n## Threads\n\n- Plant ch_01 / Payoff ch_03: outline thread\n",
        encoding="utf-8")
    for n in range(1, 5):
        _chapter(book, n)
        _summary(book, n, plot=f"Plot {n} in Venice.", location="Venice / Fondaco")
    (book / "threads.md").write_text(LEDGER, encoding="utf-8")
    sm = build_story_map(book)
    # threads.md wins over the outline ledger.
    assert sm.thread_source == "threads.md"
    assert [t.name for t in sm.threads] == ["Michaelmas clock", "Negro's register"]
    clock = sm.threads[0]
    assert clock.question == "Can Jakob put the 300 back in time?"
    assert clock.cell_role(1) == "plant"
    assert clock.cell_role(2) == "turn"
    assert clock.cell_role(3) == "payoff"          # payoff outranks the touch
    assert clock.cell_role(4) == "touch"           # note-less line is a touch
    reg = sm.threads[1]
    assert reg.chapters == [1, 5]                  # ch_01 and Ch5 both parse
    assert reg.longest_gap() == (3, 1, 5)
    # Malformed lines are warnings with line numbers, never fatal.
    warn = [w for w in sm.warnings if w.startswith("threads.md:")]
    assert any("chap 6 payoff" in w for w in warn)
    assert any("arc and nonsense line" in w for w in warn)
    assert not any("anything at all" in w for w in sm.warnings)
    # A touch on a chapter with no file is reported as data.
    assert any("touches ch 5" in w for w in sm.warnings)

    html = render_html(sm)
    assert 'class="c f plant"' in html and 'class="c f turn"' in html
    assert 'class="c f payoff"' in html and 'class="c f touch"' in html
    assert "Trevisan repaid." in html               # the cell's note
    grid = render_grid_text(sm)
    row = next(line for line in grid.splitlines() if line.startswith("Michaelmas clock"))
    assert row.split()[-1] == "PTXo."               # columns 1..5


def test_ledger_header_template_parses_clean() -> None:
    """The documented header (whose grammar examples sit inside an
    HTML comment) must not itself produce threads or warnings."""
    ledger = parse_threads_ledger(THREADS_LEDGER_HEADER.format(book="x"))
    assert ledger.threads == [] and ledger.characters == [] and ledger.warnings == []
    for token in ("## Thread:", "## Character:", "## Places", "plant | turn | payoff | touch"):
        assert token in THREADS_LEDGER_HEADER


def test_command_body_documents_the_same_grammar() -> None:
    body = (Path(__file__).resolve().parents[2] / "commands" / "story-map.md").read_text(
        encoding="utf-8")
    for token in ("## Thread: <name>", "- question:", "- ch <N> <role>:", "## Character: <name>",
                  "- aliases:", "- arc:", "- ch <N>:", "## Places",
                  "`plant`, `turn`, `payoff`, `touch`", "--threads-template"):
        assert token in body, token


# ---------------------------------------------------------- timeline


@pytest.mark.parametrize("raw,start,end", [
    ("1477-09", "1477-09", "1477-09"),
    ("1474-06 to 1474-08", "1474-06", "1474-08"),
    ("1477-09-01 to 1477-11-17. Clocks: Michaelmas 1478 set.", "1477-09-01", "1477-11-17"),
    ("1474-12-01 to January 1475. No clock carried.", "1474-12-01", "1475-01"),
    ("1494-11 to 1494-12 (Worms loan agreed for spring 1495).", "1494-11", "1494-12"),
    ("1492", "1492", "1492"),
])
def test_parse_story_time(raw: str, start: str, end: str) -> None:
    got = parse_story_time(raw)
    assert got is not None
    assert got[0] == start and got[1] == end
    assert got[2] < got[3]


def test_parse_story_time_none_when_undated() -> None:
    assert parse_story_time("the third winter of the siege") is None
    assert parse_story_time("") is None


def test_timeline_gap_flagging(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    times = {1: "1473-09", 2: "1474-06", 3: "1480-01 to 1480-03", 4: "1479-06"}
    for n, st in times.items():
        _chapter(book, n, story_time=st)
        _summary(book, n, plot=f"Plot {n}.")
    sm = build_story_map(book)
    ch = {c.chapter: c for c in sm.chapters}
    assert ch[1].gap_before is None
    assert 0.5 < ch[2].gap_before < 1.0           # 8 months, not flagged
    assert ch[3].gap_before > 5                    # 1474-06 → 1480-01
    assert ch[4].backwards                         # starts before ch 3
    html = render_html(sm)
    assert "5.5 years" in html                     # labelled gap (axis + table)
    assert "starts before the previous chapter" in html
    assert sm.span is not None and sm.span[0] == "1473-09"


# ---------------------------------------------------------- characters


def test_characters_from_characters_md_and_summary_cast(tmp_path: Path) -> None:
    root, book = _series(tmp_path)
    (root / "shared" / "characters.md").write_text(
        "# Characters\n\n## Jakob Fugger\n\nThe banker.\n\n**Role:** banker\n\n"
        "## Lorenzo Tucher\n\nFriend.\n\n## Anton Welser\n\nRival.\n\n"
        "## Anton Fugger\n\nNephew.\n\n## Margaret of Austria\n\nNever on stage.\n",
        encoding="utf-8")
    casts = {1: "Jakob (POV); Tucher; Prantl", 2: "Jakob (POV); Anton; Prantl",
             3: "Jakob; Tucher — first loss; Prantl; the courier",
             4: "Konrad (POV, Speyer); Jakob; Anton"}
    for n, cast in casts.items():
        _chapter(book, n, pov="Konrad Mair" if n == 4 else "Jakob Fugger")
        _summary(book, n, plot=f"Plot number {n} happens here. More.", cast=cast,
                 pov_state=f"Jakob state {n}.")
    sm = build_story_map(book, series_root=root)
    by = {p.name: p for p in sm.principals}
    jakob = by["Jakob Fugger"]
    assert [a.chapter for a in jakob.appearances] == [1, 2, 3, 4]
    assert [a.as_pov for a in jakob.appearances] == [True, True, True, False]
    # The POV's summary state fills the state slot; not for a non-POV chapter.
    assert jakob.appearances[0].state == "Jakob state 1."
    assert jakob.appearances[0].state_source == "summary POV state"
    assert jakob.appearances[3].state == ""
    assert jakob.appearances[0].line == "Plot number 1 happens here."
    tucher = by["Lorenzo Tucher"]
    assert [a.chapter for a in tucher.appearances] == [1, 3]
    assert tucher.appearances[1].cast_entry == "Tucher — first loss"
    # Unlisted cast name on stage in 3+ chapters is shown, as data.
    assert by["Prantl"].source == "summary cast / chapter POV"
    assert [a.chapter for a in by["Prantl"].appearances] == [1, 2, 3]
    # "Anton" is ambiguous (two listed Antons) → matched to neither.
    assert not by.get("Anton Welser") and not by.get("Anton Fugger")
    assert "Margaret of Austria" in sm.absent_principals
    assert "Role:" not in sm.absent_principals and "Role:" not in by
    # Konrad is not listed and on stage once: not a principal.
    assert "Konrad" not in by


def test_unlisted_pov_is_not_doubled_by_its_cast_entry(tmp_path: Path) -> None:
    root, book = _series(tmp_path)
    (root / "shared" / "characters.md").unlink()
    for n in (1, 2, 3):
        _chapter(book, n, pov="Konrad Mair")
        _summary(book, n, plot=f"Plot {n}.", cast="Konrad (POV); Els",
                 pov_state=f"Konrad state {n}.")
    sm = build_story_map(book, series_root=root)
    names = [p.name for p in sm.principals]
    assert names.count("Konrad") == 1 and "Konrad Mair" not in names
    konrad = next(p for p in sm.principals if p.name == "Konrad")
    assert all(a.as_pov for a in konrad.appearances)
    assert konrad.appearances[2].state == "Konrad state 3."
    els = next(p for p in sm.principals if p.name == "Els")
    assert all(a.state == "" for a in els.appearances)


def test_threads_md_character_section_aliases_and_states(tmp_path: Path) -> None:
    root, book = _series(tmp_path)
    (root / "shared" / "characters.md").write_text(
        "# Characters\n\n## Anton Welser\n\nRival.\n\n## Anton Fugger\n\nNephew.\n",
        encoding="utf-8")
    for n in (1, 2):
        _chapter(book, n)
        _summary(book, n, plot=f"Plot {n}.", cast="Jakob (POV); Anton")
    (book / "threads.md").write_text(
        "## Character: Anton Fugger\n- aliases: Anton\n- arc: Heir in waiting.\n"
        "- ch 2: Learns the books.\n- ch 3: Takes the keys.\n",
        encoding="utf-8")
    sm = build_story_map(book, series_root=root)
    anton = next(p for p in sm.principals if p.name == "Anton Fugger")
    assert anton.source == "threads.md + characters.md"
    assert anton.arc == "Heir in waiting."
    # Cast "Anton" now resolves via the explicit alias; ch 3 comes from
    # the ledger alone (no chapter file yet).
    assert [a.chapter for a in anton.appearances] == [1, 2, 3]
    assert anton.appearances[1].state == "Learns the books."
    assert anton.appearances[1].state_source == "threads.md"
    assert sm.principals[0] is anton               # ledger characters lead


def test_parse_cast_ordered_keeps_document_order(tmp_path: Path) -> None:
    p = tmp_path / "characters.md"
    p.write_text("# C\n\n## Zed\n\n- **Amy** — friend\n\n## Bob\n", encoding="utf-8")
    assert parse_cast_ordered(p) == ["Zed", "Amy", "Bob"]
    assert parse_cast(p) == {"Zed", "Amy", "Bob"}


# ---------------------------------------------------------- places


def test_places_visited_vs_named_only(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    rows = {1: ("Venice / Fondaco (Ulm table) + the Rialto steps", "Jakob arrives."),
            2: ("Augsburg: counting-room; Jakob's front room", "A letter from Venice arrives."),
            3: ("Augsburg / the yard", "Nothing named.")}
    for n, (loc, plot) in rows.items():
        _chapter(book, n)
        _summary(book, n, plot=plot, location=loc)
    sm = build_story_map(book)
    by = {p.name: p for p in sm.places}
    assert by["Venice"].visited == [1] and by["Venice"].named_only == [2]
    assert by["Augsburg"].visited == [2, 3]
    assert by["Rialto steps"].visited == [1]
    assert "Jakob's front room" not in by          # someone's room is not a place
    assert "summary `Location:` lines" in sm.place_source


def test_places_section_in_threads_md_replaces_derived_list(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    _chapter(book, 1)
    _summary(book, 1, plot="By the Rialto.", location="Venice / Fondaco")
    (book / "threads.md").write_text("## Places\n- Venice: Rialto\n- Augsburg\n",
                                     encoding="utf-8")
    sm = build_story_map(book)
    assert [p.name for p in sm.places] == ["Venice"]    # Augsburg never mentioned
    assert sm.place_source == "threads.md `## Places`"


# ---------------------------------------------------------- escalation


def test_escalation_reuses_dashboard_and_falls_back_to_chapter_logs(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    for n in (1, 2, 3):
        _chapter(book, n)
        _summary(book, n, plot=f"Plot {n}.")
    _eval(book, 1, "20260101_000000", overall_score=8.0, tension=6.5,
          dimensions={"irreversible_change": {"score": 7.5, "note": "x"}})
    _eval(book, 2, "20260101_000000", overall_score=8.5, tension=7.0)
    _eval(book, 2, "20260102_000000", overall_score=9.0)   # newer, no tension
    (book / "eval_logs" / "20260103_000000_full.json").write_text(
        json.dumps({"rows": [{"chapter": 3, "tension": 9.5}]}), encoding="utf-8")
    sm = build_story_map(book)
    assert sm.series["score"] == [8.0, 9.0, None]
    # ch 3 from the --full log (dashboard); ch 1-2 from per-chapter logs,
    # ch 2 taking the latest log that *carries* tension.
    assert sm.series["tension"] == [6.5, 7.0, 9.5]
    assert sm.series["irreversible_change"] == [7.5, None, None]
    assert "--full" in sm.series_sources["tension"]
    html = render_html(sm)
    assert html.count('class="chart"') == 3
    assert "Tension · ch 3: 9.5" in html


def test_index_latest_per_chapter_eval_key(tmp_path: Path) -> None:
    d = tmp_path / "eval_logs"
    d.mkdir()
    (d / "20260101_000000_ch01.json").write_text(json.dumps(
        {"overall_score": 7, "dimensions": {"irreversible_change": {"score": 8.5}}}))
    assert _index_latest_per_chapter_eval(d) == {1: 7.0}
    assert _index_latest_per_chapter_eval(d, key="dimensions.irreversible_change") == {1: 8.5}
    assert _index_latest_per_chapter_eval(d, key="tension") == {}


def test_parse_summary_sections_keeps_full_text() -> None:
    s = parse_summary_sections("**Plot:** One. Two.\nThree.\n\n**Cast on stage:** A; B\n")
    assert s["plot"] == "One. Two. Three."
    assert s["cast on stage"] == "A; B"


# ---------------------------------------------------------- HTML + degradation


def test_html_has_tabs_and_is_self_contained(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    _chapter(book, 1, story_time="1500-01")
    _summary(book, 1, plot="Plot.")
    html = render_html(build_story_map(book))
    for tab in ("synopsis", "threads", "characters", "timeline"):
        assert f'id="{tab}"' in html and f'href="#{tab}"' in html
    assert "<style>" in html and "<script>" in html
    assert "prefers-color-scheme:dark" in html
    assert 'name="viewport"' in html
    assert not re.search(r'(?:src|href)="https?://', html)


def test_graceful_with_no_summaries_evals_characters_or_threads(tmp_path: Path) -> None:
    root, book = _series(tmp_path)
    (root / "shared" / "characters.md").unlink()
    (root / "shared" / "events.md").unlink()
    (book / "outline.md").unlink()
    for n in (1, 2, 3):
        _chapter(book, n)                           # no summaries, no story_time
    sm = build_story_map(book, series_root=root)
    assert sm.thread_source == "none" and sm.threads == []
    assert all(v is None for vals in sm.series.values() for v in vals)
    assert sm.acts == [] and sm.places == []
    # No characters.md, no cast lines: the frontmatter POV still shows up.
    assert [p.name for p in sm.principals] == ["Jakob Fugger"]
    assert all(a.as_pov for a in sm.principals[0].appearances)
    assert any("no summary on disk" in w for w in sm.warnings)
    html = render_html(sm)
    assert "No thread ledger yet" in html
    assert "No eval scores yet" in html
    assert "No chapter has a parseable story_time" in html
    assert 'class="chart"' not in html
    assert "--refresh-threads" in render_grid_text(sm)


def test_empty_book_renders(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    sm = build_story_map(book)
    assert sm.chapters == []
    html = render_html(sm)
    assert "No chapters drafted yet." in html


def test_write_story_map_default_paths_and_summary(tmp_path: Path) -> None:
    _root, book = _series(tmp_path)
    _chapter(book, 1)
    _summary(book, 1, plot="Plot.")
    summary = write_story_map(build_story_map(book))
    html_path = book / "edit_logs" / "story_map.html"
    json_path = book / "edit_logs" / "story_map.json"
    assert Path(summary["html"]) == html_path.resolve() and html_path.is_file()
    assert Path(summary["json"]) == json_path.resolve() and json_path.is_file()
    assert summary["url"].startswith("file://")
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["chapter_count"] == 1 and data["chapters"][0]["plot"] == "Plot."
    for key in ("chapters", "threads", "characters", "thread_source", "grid_text", "warnings"):
        assert key in summary


# ---------------------------------------------------------- CLI


def test_cli_story_map_by_book_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, book = _series(tmp_path)
    _chapter(book, 1)
    _summary(book, 1, plot="Plot.")
    out = tmp_path / "out" / "map.html"
    rc = mechanical_main(["story-map", "--book", "b", "--series-root", str(root),
                          "--out", str(out)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["chapters"] == 1 and payload["threads"] == 0
    assert out.is_file() and out.with_suffix(".json").is_file()
    # Nothing written into the book when --out points elsewhere.
    assert not (book / "edit_logs" / "story_map.html").exists()


def test_cli_story_map_json_only_and_template(tmp_path: Path,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    _root, book = _series(tmp_path)
    _chapter(book, 1)
    rc = mechanical_main(["story-map", str(book), "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["html"] is None
    assert (book / "edit_logs" / "story_map.json").is_file()
    assert not (book / "edit_logs" / "story_map.html").exists()
    rc = mechanical_main(["story-map", "--threads-template", "--book", "kingmaker"])
    assert rc == 0
    assert capsys.readouterr().out.startswith("# Threads — kingmaker")


def test_cli_story_map_missing_book(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _book = _series(tmp_path)
    assert mechanical_main(["story-map", "--book", "nope", "--series-root", str(root)]) == 2
    assert "no book directory" in capsys.readouterr().err
