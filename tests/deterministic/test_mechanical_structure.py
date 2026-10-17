"""Tier-1 tests for the book-level structure helpers.

  - `autonovel mechanical structure-dossier` — data assembly (outline +
    summaries + word counts + story_time + eval scores) for
    `/autonovel:structure-review`. No judgement.
  - `autonovel mechanical structure-validate` — shape + internal
    consistency of `edit_logs/structure_review.json` and the book-level
    stop-revising gate `/autonovel:review` consults.
  - the `/autonovel:next` signals built on them.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from autonovel.housekeeping import next_actions
from autonovel.mechanical import structure_dossier as sd
from autonovel.mechanical import structure_review as sr
from autonovel.paths import SeriesLayout


# ------------------------------------------------------------------ fixtures


OUTLINE_WITH_SPINE = """# Outline

Working title: *Test*. Three acts.

## Spine
- question: Will Ana get the ledger back before the Ten hang her brother?
- posed_in: 1
- answered_in: 6
- want: the ledger
- opposing_force: the Ten's clerk

## Stakes ladder
| Act | Chapters | Stake | Higher because |
|---|---|---|---|
| I | 1-2 | her post | (opening) |
| II | 3-4 | her brother's life | a life outranks a post |
| III | 5–6 | the city's bank | everyone's money |

## Causal spine
- 2 because 1: the clerk saw her copy the page
- ch 3 because 2: the copy is found on her desk
- 4 because 2, 3: the brother is arrested for the copy
- 5 after 4: the plague year (planned weak link)
- this line does not parse

## ACT ONE — THE OFFICE
Ana works the night desk.

## Chapter 1 — The Page (POV: Ana)
- story_time: 1500-01
- events: []
- beats:
  - Ana copies the page. Stake: her post.
  - The clerk sees her
    and says nothing.

## Chapter 2 — The Desk
- story_time: 1500-03
- beats:
  - The copy is found.

## ACT TWO — THE CELL

## Chapter 3 — The Cell
- story_time: 1501-01
- beats:
  - Her brother is taken.

## Chapter 4 — The Bargain
- story_time: 1501-02
- beats:
  - She trades the page.

## Chapter 5 — Plague
- story_time: 1503-06
- beats:
  - The city shuts.

## Chapter 6 — The Bank
- story_time: 1503-07
- beats:
  - The bank fails.

## Threads
- the page: planted 1, paid 6
"""


def _write_book(root: Path, *, chapters: int = 6, outline: str = OUTLINE_WITH_SPINE,
                summaries: bool = True) -> Path:
    book = root / "books" / "the-book"
    (book / "chapters").mkdir(parents=True)
    (book / "edit_logs").mkdir()
    (book / "eval_logs").mkdir()
    (book / "outline.md").write_text(outline, encoding="utf-8")
    times = ["1500-01", "1500-03", "1501-01", "1501-02", "1503-06", "1503-07",
             "1503-08", "1503-09"]
    for n in range(1, chapters + 1):
        (book / "chapters" / f"ch_{n:02d}.md").write_text(
            f"---\nbook: the-book\nchapter: {n}\npov: Ana\ntitle: Title {n}\n"
            f"story_time: {times[n - 1]}\nstatus: drafted\nword_count: {1000 * n}\n---\n\n"
            + ("word " * 50), encoding="utf-8")
        if summaries:
            (book / "chapters" / f"ch_{n:02d}.summary.md").write_text(
                f"**Plot:** Chapter {n} happens.\n\n**Threads opened:** t{n}.\n",
                encoding="utf-8")
        (book / "eval_logs" / f"20260101_000000_ch{n:02d}_eval.json").write_text(
            json.dumps({"overall_score": 7.0 + n / 10}), encoding="utf-8")
    return book


def _valid_review(n: int = 6, **overrides) -> dict:
    data = {
        "schema": sr.SCHEMA_ID,
        "book": "the-book",
        "timestamp": "2026-10-17T00:00:00Z",
        "chapter_count": n,
        "through_line": {
            "question": "Will Ana get the ledger back before the Ten hang her brother?",
            "posed_in": 1, "posed_at_pct": 3.0, "answered_in": n,
            "ending_answers": "yes", "answer": "She burns it to save him.",
            "seed_intent": "the ledger",
        },
        "causal_chain": [
            {"from": i, "to": i + 1, "link": "because", "cause_chapters": [i],
             "evidence": f"ch {i} event forces ch {i + 1}"}
            for i in range(1, n)
        ],
        "causal_summary": {"because": n - 1, "after": 0, "unrelated": 0,
                           "because_ratio": 1.0},
        "escalation": [
            {"act": "I", "title": "Office", "chapters": [1, 2], "stake": "her post",
             "same_question": True, "vs_previous": "first", "evidence": "opening"},
            {"act": "II", "title": "Cell", "chapters": [3, n], "stake": "her brother",
             "same_question": True, "vs_previous": "higher", "evidence": "a life > a post"},
        ],
        "removability": [
            {"chapter": i, "verdict": "load-bearing",
             "breaks": [i + 1] if i < n else [],
             "what_breaks": "the next chapter's arrest" if i < n else "the ending answers the question"}
            for i in range(1, n + 1)
        ],
        "removable_chapters": [],
        "climax": {"window": [n - 1, n],
                   "threads": [{"thread": "ledger", "opened_in": 1,
                                "ending": "converged", "where": n}],
                   "verdict": "converges", "evidence": "the ledger and the brother meet in one choice"},
        "failure_modes": [],
        "episodic_risk": "low",
        "verdict": "One story: each chapter is caused by the last.",
        "structure_score": 4,
        "candidates": [
            {"id": f"S{k}", "kind": "plant-earlier", "title": f"plant {k}",
             "chapters": [1, n], "edits": [{"chapter": 1, "instruction": "plant the seal"},
                                           {"chapter": n, "instruction": "pay the seal"}],
             "command": None, "expected_effect": "the climax uses a planted object",
             "fixes": [f"thread {k}"], "priority": k}
            for k in range(1, 4)
        ],
    }
    data.update(overrides)
    return data


def _anecdote_chain(n: int = 6) -> dict:
    """The kingmaker shape: strong chapters, each a closed wager; most
    links are 'happens after'; two chapters removable."""
    data = _valid_review(n)
    for link in data["causal_chain"]:
        if link["to"] in (3, 4, 6):
            link["link"] = "after"
            link["evidence"] = "a new counterparty arrives after a time jump"
    data["causal_summary"] = {"because": 2, "after": 3, "unrelated": 0, "because_ratio": 0.4}
    for row in data["removability"]:
        if row["chapter"] in (3, 5):
            row.update({"verdict": "removable", "breaks": [],
                        "what_breaks": "nothing later needs the wager it settles"})
    data["removable_chapters"] = [3, 5]
    data["episodic_risk"] = "high"
    data["failure_modes"] = ["anecdote-chain", "motif-spine"]
    data["candidates"][0].update({"kind": "merge", "chapters": [3, 4],
                                  "edits": [{"chapter": 3, "instruction": "fold into 4"}],
                                  "command": "/autonovel:merge-chapters --chapters 3,4 --book the-book"})
    return data


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    src = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-m", "autonovel.mechanical", *args],
                          capture_output=True, text=True, env=env, cwd=cwd)


# ----------------------------------------------------------- outline parser


def test_parse_outline_reads_acts_chapters_and_spine_sections() -> None:
    info = sd.parse_outline(OUTLINE_WITH_SPINE)
    assert [a["heading"] for a in info.acts] == ["ACT ONE — THE OFFICE", "ACT TWO — THE CELL"]
    assert info.acts[0]["chapters"] == [1, 2]
    assert info.acts[1]["chapters"] == [3, 4, 5, 6]
    ch1 = info.chapters[0]
    assert ch1.title == "The Page" and ch1.pov == "Ana" and ch1.story_time == "1500-01"
    assert ch1.beats[1] == "The clerk sees her and says nothing."
    assert info.spine["fields"]["question"].endswith("brother?")
    assert info.spine["fields"]["opposing_force"] == "the Ten's clerk"
    rows = info.stakes_ladder["rows"]
    assert [r["chapters_list"] for r in rows] == [[1, 2], [3, 4], [5, 6]]
    links = {lk["chapter"]: lk for lk in info.causal_spine["links"]}
    assert links[4]["cause_chapters"] == [2, 3]
    assert links[5]["link"] == "after"
    assert info.causal_spine["planned_after_links"] == [5]
    assert info.causal_spine["missing_chapters"] == [6]
    assert info.causal_spine["unparsed_lines"] == ["- this line does not parse"]
    assert any("no line for chapter(s) 6" in w for w in info.warnings)
    # The `## Threads` ledger is not an act.
    assert "Threads" not in [a["heading"] for a in info.acts]


def test_parse_outline_warns_when_spine_sections_absent() -> None:
    old = "# Outline\n\n## Chapter 1 — A\n- story_time: 1500\n- beats:\n  - x\n"
    info = sd.parse_outline(old)
    joined = " ".join(info.warnings)
    assert "## Spine" in joined and "## Stakes ladder" in joined and "## Causal spine" in joined
    assert "--add-spine" in joined
    assert info.acts == []  # no act headings → no acts, not an error


def test_parse_outline_empty() -> None:
    info = sd.parse_outline("")
    assert info.present is False
    assert info.warnings == ["outline.md is missing or empty."]


# ------------------------------------------------------------------ dossier


def test_build_dossier_packs_positions_gaps_scores_and_summaries(tmp_path: Path) -> None:
    book = _write_book(tmp_path)
    (book / "threads.md").write_text("## The ledger\n- plant: 1\n- payoff: 6\n", encoding="utf-8")
    d = sd.build_dossier(book)
    assert d["chapter_count"] == 6
    assert d["total_words"] == 21000
    first, last = d["chapters"][0], d["chapters"][-1]
    assert first["start_pct"] == 0.0 and last["end_pct"] == 100.0
    assert first["title"] == "Title 1" and first["pov"] == "Ana"
    assert first["outline_title"] == "The Page"
    assert "Chapter 1 happens" in first["summary"]
    assert first["latest_score"] == pytest.approx(7.1)
    # 1501-02 → 1503-06 is 28 months.
    assert d["chapters"][4]["gap_months_from_previous"] == 28
    assert {"from": 4, "to": 5, "months": 28} in d["story_time_gaps_of_a_year_or_more"]
    # Chapter 6 (start 15000/21000 ≈ 71%) is before 80% → window falls back to last.
    assert d["climax_window_chapters"] == [6]
    assert d["threads"]["present"] is True and "The ledger" in d["threads"]["text"]
    assert d["artifacts"]["structure_review"]["present"] is False
    assert d["outline"]["causal_spine"]["present"] is True


def test_build_dossier_reports_missing_summaries_and_outline_mismatch(tmp_path: Path) -> None:
    book = _write_book(tmp_path, chapters=4, summaries=False)
    d = sd.build_dossier(book)
    joined = " ".join(d["warnings"])
    assert "no continuity summary for chapter(s) 1, 2, 3, 4" in joined
    assert "outlined but not drafted: chapter(s) 5, 6" in joined


def test_build_dossier_marks_whole_book_reports_stale(tmp_path: Path) -> None:
    book = _write_book(tmp_path)
    review = book / "edit_logs" / "review.md"
    review.write_text("# review", encoding="utf-8")
    old = time.time() - 10_000
    os.utime(review, (old, old))
    d = sd.build_dossier(book)
    assert d["artifacts"]["review"]["present"] is True
    assert d["artifacts"]["review"]["stale"] is True


def test_cli_structure_dossier_json_and_markdown(tmp_path: Path) -> None:
    book = _write_book(tmp_path)
    out = _run_cli("structure-dossier", str(book))
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data["book"] == "the-book"
    md = _run_cli("structure-dossier", str(book), "--format", "markdown")
    assert md.returncode == 0
    assert "| Ch | Words | Start % |" in md.stdout
    missing = _run_cli("structure-dossier", str(tmp_path / "nope"))
    assert missing.returncode == 2


# --------------------------------------------------------------- validator


def test_valid_review_passes_and_gate_passes(tmp_path: Path) -> None:
    rep = sr.validate(_valid_review())
    assert rep.valid, rep.errors
    assert rep.summary["because_ratio"] == 1.0
    book = _write_book(tmp_path)
    path = book / "edit_logs" / "structure_review.json"
    path.write_text(json.dumps(_valid_review()), encoding="utf-8")
    checked = sr.check(path, book_root=book)
    assert checked.valid, checked.errors
    assert checked.gate["passes"] is True
    assert checked.gate["reasons"] == []


def test_missing_required_key_is_invalid() -> None:
    data = _valid_review()
    del data["removability"]
    rep = sr.validate(data)
    assert not rep.valid
    assert any("removability" in e for e in rep.errors)


def test_missing_causal_link_is_reported() -> None:
    data = _valid_review()
    data["causal_chain"] = [lk for lk in data["causal_chain"] if lk["to"] != 4]
    data["causal_summary"]["because"] = 4
    rep = sr.validate(data)
    assert any("missing link(s) 3->4" in e for e in rep.errors)


def test_because_link_needs_evidence_and_earlier_cause() -> None:
    data = _valid_review()
    data["causal_chain"][0]["evidence"] = " "
    data["causal_chain"][1]["cause_chapters"] = [5]
    rep = sr.validate(data)
    assert any("evidence must name a concrete plot fact" in e for e in rep.errors)
    assert any("cause_chapters must be earlier" in e for e in rep.errors)


def test_removable_list_must_match_table() -> None:
    data = _valid_review()
    data["removable_chapters"] = [2]
    rep = sr.validate(data)
    assert any("does not match the removability table" in e for e in rep.errors)


def test_load_bearing_needs_a_later_chapter_except_the_last() -> None:
    data = _valid_review()
    data["removability"][1]["breaks"] = []
    rep = sr.validate(data)
    assert any("(ch 2): `load-bearing` must name" in e for e in rep.errors)
    # The last chapter (6) has breaks == [] in the fixture and is fine.
    assert not any("(ch 6)" in e for e in rep.errors)


def test_score_above_rubric_cap_is_invalid() -> None:
    """A 4/5 next to the reviewer's own table of an anecdote chain is a
    sycophantic score; the validator refuses it."""
    data = _anecdote_chain()
    data["structure_score"] = 4
    rep = sr.validate(data)
    assert not rep.valid
    cap_errors = [e for e in rep.errors if "exceeds the rubric cap" in e]
    assert cap_errors and "cap 2" in cap_errors[0]
    assert rep.summary["max_score_by_rubric"] == 2


def test_anecdote_chain_at_honest_score_is_valid_but_blocks_gate(tmp_path: Path) -> None:
    data = _anecdote_chain()
    data["structure_score"] = 2
    rep = sr.validate(data)
    assert rep.valid, rep.errors
    book = _write_book(tmp_path)
    path = book / "edit_logs" / "structure_review.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    checked = sr.check(path, book_root=book)
    assert checked.gate["passes"] is False
    joined = " ".join(checked.gate["reasons"])
    assert "below 4" in joined and "removable chapter(s): 3, 5" in joined
    assert checked.summary["cross_chapter_commands"] == [
        "/autonovel:merge-chapters --chapters 3,4 --book the-book"]


@pytest.mark.parametrize("mutate, cap", [
    (lambda d: d["through_line"].update({"posed_at_pct": 76.0}), 2),
    (lambda d: d["through_line"].update({"posed_at_pct": 30.0}), 3),
    (lambda d: d["through_line"].update({"ending_answers": "partly"}), 3),
    (lambda d: d["climax"].update({"verdict": "finishes"}), 3),
    (lambda d: d["escalation"][1].update({"vs_previous": "reset"}), 2),
    (lambda d: d.update({"episodic_risk": "medium"}), 3),
])
def test_each_rubric_cap(mutate, cap) -> None:
    data = _valid_review()
    data["structure_score"] = 5
    mutate(data)
    rep = sr.validate(data)
    assert rep.summary["max_score_by_rubric"] == cap
    assert any("exceeds the rubric cap" in e for e in rep.errors)


def test_cross_chapter_candidate_needs_exact_command() -> None:
    data = _valid_review()
    data["candidates"][0]["kind"] = "cut"
    rep = sr.validate(data)
    assert any("needs the exact command, starting `/autonovel:remove-chapter`" in e
               for e in rep.errors)
    data["candidates"][0]["command"] = "/autonovel:remove-chapter 1 --book the-book"
    assert sr.validate(data).valid


def test_candidate_count_bounds() -> None:
    data = _valid_review()
    data["candidates"] = data["candidates"][:2]
    assert any("3-7 structural brief candidates" in e for e in sr.validate(data).errors)
    data["structure_score"] = 5
    assert not any("structural brief candidates" in e for e in sr.validate(data).errors)


def test_through_line_must_be_a_question() -> None:
    data = _valid_review()
    data["through_line"]["question"] = "Money and the soul."
    assert any("ending with `?`" in e for e in sr.validate(data).errors)


def test_stale_review_blocks_gate(tmp_path: Path) -> None:
    book = _write_book(tmp_path)
    path = book / "edit_logs" / "structure_review.json"
    path.write_text(json.dumps(_valid_review()), encoding="utf-8")
    old = time.time() - 10_000
    os.utime(path, (old, old))
    checked = sr.check(path, book_root=book)
    assert checked.gate["stale"] is True
    assert checked.gate["passes"] is False
    assert checked.gate["stale_chapters"] == [1, 2, 3, 4, 5, 6]


def test_chapter_count_must_match_disk(tmp_path: Path) -> None:
    book = _write_book(tmp_path, chapters=5)
    path = book / "edit_logs" / "structure_review.json"
    path.write_text(json.dumps(_valid_review(6)), encoding="utf-8")
    checked = sr.check(path)  # book_root derived from edit_logs/
    assert any("chapter_count 6 but 5 chapter file(s)" in e for e in checked.errors)


def test_missing_file_gate_says_run_structure_review(tmp_path: Path) -> None:
    rep = sr.check(tmp_path / "edit_logs" / "structure_review.json")
    assert rep.present is False
    assert rep.gate["passes"] is False
    assert "run /autonovel:structure-review first" in rep.gate["reasons"][0]


def test_cli_structure_validate_exit_codes(tmp_path: Path) -> None:
    book = _write_book(tmp_path)
    missing = _run_cli("structure-validate", str(book))
    assert missing.returncode == 2
    assert json.loads(missing.stdout)["gate"]["passes"] is False
    path = book / "edit_logs" / "structure_review.json"
    path.write_text(json.dumps(_valid_review()), encoding="utf-8")
    ok = _run_cli("structure-validate", str(book))
    assert ok.returncode == 0, ok.stdout
    assert json.loads(ok.stdout)["gate"]["passes"] is True
    bad = _anecdote_chain()
    bad["structure_score"] = 4
    path.write_text(json.dumps(bad), encoding="utf-8")
    invalid = _run_cli("structure-validate", str(path))
    assert invalid.returncode == 1
    md = _run_cli("structure-validate", str(book), "--format", "markdown")
    assert "BLOCK" in md.stdout and "exceeds the rubric cap" in md.stdout


def test_cli_template_has_every_required_key() -> None:
    out = _run_cli("structure-validate", "--template", "--chapters", "4")
    assert out.returncode == 0
    tpl = json.loads(out.stdout)
    for key in ("through_line", "causal_chain", "escalation", "removability",
                "removable_chapters", "climax", "episodic_risk", "verdict",
                "structure_score", "candidates"):
        assert key in tpl
    assert len(tpl["causal_chain"]) == 3 and len(tpl["removability"]) == 4


# ------------------------------------------------------------ /autonovel:next


def _series_with_book(tmp_path: Path, chapters: int = 6) -> tuple[Path, str]:
    from autonovel.housekeeping import scaffold
    res = scaffold.new_series(tmp_path / "s", series_name="s")
    scaffold.new_book(res.series, book_name="the-book", pov="Ana")
    root = res.series.root
    book = root / "books" / "the-book"
    (book / "outline.md").write_text(OUTLINE_WITH_SPINE, encoding="utf-8")
    for n in range(1, chapters + 1):
        (book / "chapters" / f"ch_{n:02d}.md").write_text(
            f"---\nchapter: {n}\nstatus: drafted\nword_count: 2000\n---\n\nProse.\n",
            encoding="utf-8")
    return root, "the-book"


def _structure_actions(root: Path, book: str) -> list:
    acts = next_actions.enumerate_actions(SeriesLayout(root=root), book=book)
    return [a for a in acts if a.command and "structure" in a.command
            or "structure review" in a.title.lower()]


def test_next_suggests_structure_review_on_a_drafted_book(tmp_path: Path) -> None:
    root, book = _series_with_book(tmp_path)
    found = _structure_actions(root, book)
    assert len(found) == 1
    assert found[0].priority == "MEDIUM"
    assert found[0].command == "/autonovel:structure-review --book the-book"


def test_next_silent_below_six_chapters(tmp_path: Path) -> None:
    root, book = _series_with_book(tmp_path, chapters=5)
    (root / "books" / book / "edit_logs" / "review.md").write_text("x", encoding="utf-8")
    assert _structure_actions(root, book) == []


def test_next_flags_stale_structure_review(tmp_path: Path) -> None:
    root, book = _series_with_book(tmp_path)
    path = root / "books" / book / "edit_logs" / "structure_review.json"
    path.write_text(json.dumps(_valid_review()), encoding="utf-8")
    old = time.time() - 10_000
    os.utime(path, (old, old))
    found = _structure_actions(root, book)
    assert len(found) == 1 and found[0].title.startswith("Re-run")


def test_next_routes_failing_gate_to_structural_revision_pass(tmp_path: Path) -> None:
    root, book = _series_with_book(tmp_path)
    data = _anecdote_chain()
    data["structure_score"] = 2
    (root / "books" / book / "edit_logs" / "structure_review.json").write_text(
        json.dumps(data), encoding="utf-8")
    found = _structure_actions(root, book)
    assert len(found) == 1
    assert found[0].command == "/autonovel:revision-pass --chapters structural --book the-book"
    assert "/autonovel:merge-chapters --chapters 3,4" in found[0].rationale


def test_next_silent_when_gate_passes(tmp_path: Path) -> None:
    root, book = _series_with_book(tmp_path)
    (root / "books" / book / "edit_logs" / "structure_review.json").write_text(
        json.dumps(_valid_review()), encoding="utf-8")
    assert _structure_actions(root, book) == []


def test_validate_does_not_mutate_input() -> None:
    data = _anecdote_chain()
    before = copy.deepcopy(data)
    sr.validate(data)
    assert data == before
