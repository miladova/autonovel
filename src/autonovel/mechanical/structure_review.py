"""Shape validator + stop-revising gate for `edit_logs/structure_review.json`.

`/autonovel:structure-review` (an LLM command) writes the file; this module
checks it and computes the book-level gate that `/autonovel:review` and
`/autonovel:next` consult before anyone is told to stop revising.

What is checked, and what is not:

  - **Shape.** Required keys, enums, one causal link per consecutive
    chapter pair, one removability verdict per chapter, 3–7 structural
    brief candidates with per-chapter instructions, an exact command for
    cross-chapter operations (merge / cut / reorder / split), a
    through-line stated as a question.
  - **Internal consistency.** `removable_chapters` must equal the
    chapters the reviewer's own removability table calls removable; the
    causal counts must equal the table. The rubric caps in
    `commands/structure-review.md` are arithmetic over the reviewer's own
    tables (e.g. "any removable chapter caps the score at 3"), so they
    are checked here too: a 4/5 next to a table that says a third of the
    links are "happens after" is an invalid file, not a judgement call.
    That is the one mechanical guard against a sycophantic score.
  - **Not checked:** whether any link really is causal, whether a stake
    really is higher, whether a chapter really could be cut. Those are
    the LLM's judgements; Python never second-guesses them.

The gate passes only when the file is present, valid, newer than every
chapter file, scores ``structure_score >= 4`` and flags no chapter
removable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_ID = "autonovel.structure_review/1"
GATE_MIN_SCORE = 4

LINK_KINDS = ("because", "after", "unrelated")
REMOVABILITY_VERDICTS = ("load-bearing", "weak", "removable")
ESCALATION_VS_PREVIOUS = ("first", "higher", "level", "lower", "reset")
ENDING_ANSWERS = ("yes", "partly", "no")
CLIMAX_VERDICTS = ("converges", "mixed", "finishes")
EPISODIC_RISK = ("low", "medium", "high")
THREAD_ENDINGS = ("converged", "finished", "dropped")
CANDIDATE_KINDS = (
    "move-reveal", "merge", "add-consequence-scene", "cut", "plant-earlier",
    "reorder", "split", "retarget-stake", "thread-the-antagonist",
    "pose-question-earlier", "converge-climax", "other",
)
# Kinds that change the chapter list. `revise` never executes these; the
# brief surfaces `command` for the author to run.
CROSS_CHAPTER_KINDS = ("merge", "cut", "reorder", "split")
COMMAND_PREFIX = {
    "merge": "/autonovel:merge-chapters",
    "cut": "/autonovel:remove-chapter",
    "reorder": "/autonovel:reorder",
    "split": "/autonovel:split-chapter",
}
FAILURE_MODES = (
    "anecdote-chain", "motif-spine", "chronicle-spine", "late-through-line",
    "reset-ladder", "finishing-not-converging", "missing-antagonist",
    "promise-line-architecture",
)


@dataclass
class ValidationReport:
    present: bool = True
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    caps: list[dict] = field(default_factory=list)
    gate: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"present": self.present, "valid": self.valid,
                "errors": list(self.errors), "warnings": list(self.warnings),
                "caps": list(self.caps), "gate": dict(self.gate),
                "summary": dict(self.summary)}


def blank_template(chapter_count: int = 3, book: str = "<book>") -> dict:
    """A skeleton the command fills in. Every enum shows its legal values."""
    n = max(1, chapter_count)
    return {
        "schema": SCHEMA_ID,
        "book": book,
        "timestamp": "<UTC ISO-8601>",
        "chapter_count": n,
        "scope": "chapters 1-%d: full prose + outline + summaries" % n,
        "through_line": {
            "question": "<one question the book asks, ending with ?>",
            "posed_in": 1, "posed_at_pct": 0.0,
            "answered_in": n, "ending_answers": "|".join(ENDING_ANSWERS),
            "answer": "<how the ending answers it, or why it does not>",
            "seed_intent": "<the question the seed promises, quoted or paraphrased>",
        },
        "causal_chain": [
            {"from": i, "to": i + 1, "link": "|".join(LINK_KINDS),
             "cause_chapters": [i],
             "evidence": "<the plot fact in an earlier chapter that forces this one>"}
            for i in range(1, n)
        ],
        "causal_summary": {"because": 0, "after": 0, "unrelated": 0, "because_ratio": 0.0},
        "escalation": [
            {"act": "I", "title": "<act name>", "chapters": [1, n],
             "stake": "<what the protagonist can lose in this act, concretely>",
             "same_question": True, "vs_previous": "first",
             "evidence": "<why higher / level / reset vs the previous act>"},
        ],
        "removability": [
            {"chapter": i, "verdict": "|".join(REMOVABILITY_VERDICTS),
             "breaks": [], "what_breaks": "<the later action that fails if this chapter is cut>"}
            for i in range(1, n + 1)
        ],
        "removable_chapters": [],
        "climax": {
            "window": [n, n],
            "threads": [{"thread": "<thread>", "opened_in": 1,
                         "ending": "|".join(THREAD_ENDINGS), "where": n}],
            "verdict": "|".join(CLIMAX_VERDICTS),
            "evidence": "<do the threads meet in one decision, or close one by one?>",
        },
        "failure_modes": [],
        "episodic_risk": "|".join(EPISODIC_RISK),
        "verdict": "<plain words: is this one story building to a climax, or a string of episodes?>",
        "structure_score": 0,
        "candidates": [
            {"id": "S1", "kind": "|".join(CANDIDATE_KINDS), "title": "<short>",
             "chapters": [1], "edits": [{"chapter": 1, "instruction": "<what changes on the page>"}],
             "command": None, "expected_effect": "<which links / rungs / chapters this fixes>",
             "fixes": ["<e.g. link 3->4, removable ch 5>"], "priority": 1},
        ],
    }


# ------------------------------------------------------------------ helpers


def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _int_list(x: object) -> bool:
    return isinstance(x, list) and all(_is_int(v) for v in x)


def _nonempty_str(x: object) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _chapter_numbers(book_root: Path | None) -> list[int]:
    if book_root is None:
        return []
    from ..paths import iter_chapter_files
    nums: list[int] = []
    for p in iter_chapter_files(book_root / "chapters"):
        try:
            nums.append(int(p.stem.split("_")[-1]))
        except ValueError:
            continue
    return sorted(nums)


# --------------------------------------------------------------- validation


def validate(data: object, *, chapter_numbers: list[int] | None = None) -> ValidationReport:
    """Validate a parsed structure_review.json. `chapter_numbers` (the
    drafted chapters on disk) tightens the coverage checks when given."""
    rep = ValidationReport()
    err, warn = rep.errors.append, rep.warnings.append
    if not isinstance(data, dict):
        rep.valid = False
        err("top level must be a JSON object")
        return rep

    for key in ("book", "timestamp", "through_line", "causal_chain", "escalation",
                "removability", "removable_chapters", "climax", "episodic_risk",
                "verdict", "structure_score", "candidates"):
        if key not in data:
            err(f"missing required key `{key}`")
    if rep.errors:
        rep.valid = False
        return rep

    # Chapter universe.
    declared = data.get("chapter_count")
    removability = data.get("removability")
    if chapter_numbers:
        chapters = sorted(chapter_numbers)
    elif _is_int(declared) and declared > 0:
        chapters = list(range(1, declared + 1))
    elif isinstance(removability, list):
        chapters = sorted({r.get("chapter") for r in removability
                           if isinstance(r, dict) and _is_int(r.get("chapter"))})
    else:
        chapters = []
    if chapter_numbers and _is_int(declared) and declared != len(chapter_numbers):
        err(f"chapter_count {declared} but {len(chapter_numbers)} chapter file(s) on disk")
    chapter_set = set(chapters)
    n = len(chapters)

    # Score.
    score = data.get("structure_score")
    if not _is_int(score) or not 1 <= score <= 5:
        err("structure_score must be an integer 1-5")
        score = None

    # Through-line.
    tl = data.get("through_line")
    posed_pct = None
    ending_answers = None
    if not isinstance(tl, dict):
        err("through_line must be an object")
    else:
        q = tl.get("question")
        if not _nonempty_str(q) or not q.strip().endswith("?"):
            err("through_line.question must be one question ending with `?`")
        for k in ("posed_in", "answered_in"):
            v = tl.get(k)
            if v is not None and not _is_int(v):
                err(f"through_line.{k} must be a chapter number or null")
            elif _is_int(v) and chapter_set and v not in chapter_set:
                err(f"through_line.{k} = {v} is not a chapter of this book")
        if not _is_int(tl.get("posed_in")):
            warn("through_line.posed_in is null: the reviewer found no chapter that poses the question")
        posed_pct = tl.get("posed_at_pct")
        if posed_pct is not None and not isinstance(posed_pct, (int, float)):
            err("through_line.posed_at_pct must be a number (0-100)")
            posed_pct = None
        ending_answers = tl.get("ending_answers")
        if ending_answers not in ENDING_ANSWERS:
            err(f"through_line.ending_answers must be one of {', '.join(ENDING_ANSWERS)}")
            ending_answers = None
        if not _nonempty_str(tl.get("answer")):
            err("through_line.answer must say how (or whether) the ending answers the question")

    # Causal chain: one entry per consecutive pair.
    counts = {k: 0 for k in LINK_KINDS}
    chain = data.get("causal_chain")
    if not isinstance(chain, list):
        err("causal_chain must be a list")
        chain = []
    seen_pairs: set[tuple[int, int]] = set()
    for i, link in enumerate(chain):
        where = f"causal_chain[{i}]"
        if not isinstance(link, dict):
            err(f"{where} must be an object")
            continue
        a, b, kind = link.get("from"), link.get("to"), link.get("link")
        if not (_is_int(a) and _is_int(b)):
            err(f"{where}: `from` and `to` must be chapter numbers")
            continue
        seen_pairs.add((a, b))
        if kind not in LINK_KINDS:
            err(f"{where} ({a}->{b}): link must be one of {', '.join(LINK_KINDS)}")
            continue
        counts[kind] += 1
        if not _nonempty_str(link.get("evidence")):
            err(f"{where} ({a}->{b}): evidence must name a concrete plot fact")
        if kind == "because":
            causes = link.get("cause_chapters", [a])
            if not _int_list(causes) or not causes:
                err(f"{where} ({a}->{b}): a `because` link needs cause_chapters")
            elif any(c >= b for c in causes):
                err(f"{where} ({a}->{b}): cause_chapters must be earlier than chapter {b}")
    if chapters:
        expected = {(chapters[i], chapters[i + 1]) for i in range(n - 1)}
        missing = sorted(expected - seen_pairs)
        if missing:
            err("causal_chain is missing link(s) " + ", ".join(f"{x}->{y}" for x, y in missing))
    total_links = sum(counts.values())
    because_ratio = round(counts["because"] / total_links, 3) if total_links else None
    cs = data.get("causal_summary")
    if isinstance(cs, dict):
        for k in LINK_KINDS:
            if _is_int(cs.get(k)) and cs[k] != counts[k]:
                err(f"causal_summary.{k} = {cs[k]} but the table has {counts[k]}")
    else:
        warn("causal_summary missing; computed from the table")

    # Escalation ladder.
    ladder = data.get("escalation")
    vs_values: list[str] = []
    if not isinstance(ladder, list) or not ladder:
        err("escalation must be a non-empty list (one entry per act)")
        ladder = []
    elif n >= 6 and len(ladder) < 2:
        err("escalation needs at least two acts for a book of six or more chapters")
    for i, act in enumerate(ladder):
        where = f"escalation[{i}]"
        if not isinstance(act, dict):
            err(f"{where} must be an object")
            continue
        if not _nonempty_str(act.get("stake")):
            err(f"{where}: stake must say concretely what can be lost")
        vs = act.get("vs_previous")
        if vs not in ESCALATION_VS_PREVIOUS:
            err(f"{where}: vs_previous must be one of {', '.join(ESCALATION_VS_PREVIOUS)}")
            continue
        if i == 0 and vs != "first":
            err(f"{where}: the first act's vs_previous must be `first`")
        if i > 0:
            if vs == "first":
                err(f"{where}: only the first act may be `first`")
            vs_values.append(vs)
            if not _nonempty_str(act.get("evidence")):
                err(f"{where}: evidence must compare this act's stake with the previous act's")
        if not isinstance(act.get("same_question"), bool):
            err(f"{where}: same_question must be true or false")
        rng = act.get("chapters")
        if rng is not None and not _int_list(rng):
            err(f"{where}: chapters must be [first, last] chapter numbers")

    # Removability.
    if not isinstance(removability, list):
        err("removability must be a list (one entry per chapter)")
        removability = []
    removable: list[int] = []
    verdict_by_ch: dict[int, str] = {}
    # The last chapter has no later chapter to break; it is judged by the
    # through-line, so it may be load-bearing with `breaks == []`.
    last_chapter = chapters[-1] if chapters else None
    for i, row in enumerate(removability):
        where = f"removability[{i}]"
        if not isinstance(row, dict) or not _is_int(row.get("chapter")):
            err(f"{where} must be an object with a chapter number")
            continue
        ch, verdict = row["chapter"], row.get("verdict")
        if verdict not in REMOVABILITY_VERDICTS:
            err(f"{where} (ch {ch}): verdict must be one of {', '.join(REMOVABILITY_VERDICTS)}")
            continue
        verdict_by_ch[ch] = verdict
        breaks = row.get("breaks", [])
        if not _int_list(breaks):
            err(f"{where} (ch {ch}): breaks must be a list of chapter numbers")
            breaks = []
        if verdict == "removable":
            removable.append(ch)
            if breaks:
                err(f"{where} (ch {ch}): a removable chapter breaks nothing — `breaks` must be empty")
        else:
            if not breaks and ch != last_chapter:
                err(f"{where} (ch {ch}): `{verdict}` must name the later chapter(s) that break")
            elif any(b <= ch for b in breaks):
                err(f"{where} (ch {ch}): breaks must be later chapters")
            if not _nonempty_str(row.get("what_breaks")):
                err(f"{where} (ch {ch}): what_breaks must name the later action that fails")
    if chapters:
        missing_rows = sorted(chapter_set - set(verdict_by_ch))
        if missing_rows:
            err("removability has no verdict for chapter(s) " + ", ".join(map(str, missing_rows)))
    listed = data.get("removable_chapters")
    if not _int_list(listed):
        err("removable_chapters must be a list of chapter numbers")
    elif sorted(listed) != sorted(removable):
        err(f"removable_chapters {sorted(listed)} does not match the removability table {sorted(removable)}")

    # Climax.
    climax = data.get("climax")
    climax_verdict = None
    if not isinstance(climax, dict):
        err("climax must be an object")
    else:
        climax_verdict = climax.get("verdict")
        if climax_verdict not in CLIMAX_VERDICTS:
            err(f"climax.verdict must be one of {', '.join(CLIMAX_VERDICTS)}")
            climax_verdict = None
        threads = climax.get("threads", [])
        if not isinstance(threads, list) or not threads:
            err("climax.threads must list the threads open at the climax window")
        else:
            for i, t in enumerate(threads):
                if not isinstance(t, dict) or t.get("ending") not in THREAD_ENDINGS:
                    err(f"climax.threads[{i}].ending must be one of {', '.join(THREAD_ENDINGS)}")
        if not _nonempty_str(climax.get("evidence")):
            err("climax.evidence must say whether the threads meet in one decision")

    # Verdict + risk + failure modes.
    risk = data.get("episodic_risk")
    if risk not in EPISODIC_RISK:
        err(f"episodic_risk must be one of {', '.join(EPISODIC_RISK)}")
        risk = None
    if not _nonempty_str(data.get("verdict")):
        err("verdict must be plain words")
    modes = data.get("failure_modes", [])
    if not isinstance(modes, list) or not all(isinstance(m, str) for m in modes):
        err("failure_modes must be a list of names")
        modes = []
    for m in modes:
        if m not in FAILURE_MODES:
            warn(f"failure mode `{m}` is not one of the named modes ({', '.join(FAILURE_MODES)})")

    # Candidates.
    cands = data.get("candidates")
    if not isinstance(cands, list):
        err("candidates must be a list")
        cands = []
    lo = 0 if score == 5 else 3
    if not lo <= len(cands) <= 7:
        err(f"candidates must hold {lo}-7 structural brief candidates (found {len(cands)})")
    ids: set[str] = set()
    for i, c in enumerate(cands):
        where = f"candidates[{i}]"
        if not isinstance(c, dict):
            err(f"{where} must be an object")
            continue
        cid = c.get("id")
        if not _nonempty_str(cid):
            err(f"{where}: id is required (S1, S2, …)")
        elif cid in ids:
            err(f"{where}: duplicate id {cid}")
        else:
            ids.add(cid)
        kind = c.get("kind")
        if kind not in CANDIDATE_KINDS:
            err(f"{where}: kind must be one of {', '.join(CANDIDATE_KINDS)}")
        cchaps = c.get("chapters")
        if not _int_list(cchaps) or not cchaps:
            err(f"{where}: chapters must list the chapters affected")
            cchaps = []
        elif chapter_set and any(x not in chapter_set for x in cchaps):
            err(f"{where}: chapters {cchaps} include a chapter not in the book")
        edits = c.get("edits")
        if not isinstance(edits, list) or not edits:
            err(f"{where}: edits must give one instruction per chapter touched")
        else:
            for j, e in enumerate(edits):
                if not isinstance(e, dict) or not _is_int(e.get("chapter")) \
                        or not _nonempty_str(e.get("instruction")):
                    err(f"{where}.edits[{j}]: needs a chapter number and an instruction")
                elif cchaps and e["chapter"] not in cchaps:
                    err(f"{where}.edits[{j}]: chapter {e['chapter']} is not in the candidate's chapters")
        if not _nonempty_str(c.get("expected_effect")):
            err(f"{where}: expected_effect must say what the change fixes")
        cmd = c.get("command")
        if kind in CROSS_CHAPTER_KINDS:
            prefix = COMMAND_PREFIX[kind]
            if not _nonempty_str(cmd) or not cmd.strip().startswith(prefix):
                err(f"{where}: a `{kind}` candidate needs the exact command, starting `{prefix}`")
        elif cmd not in (None, "") and not (isinstance(cmd, str) and cmd.strip().startswith("/autonovel:")):
            err(f"{where}: command must be null or an /autonovel:* command")
    for ch in removable:
        if not any(isinstance(c, dict) and ch in (c.get("chapters") or []) for c in cands):
            warn(f"chapter {ch} is removable but no candidate addresses it")

    # Rubric caps — arithmetic over the reviewer's own tables.
    caps: list[dict] = []

    def cap(limit: int, reason: str) -> None:
        caps.append({"max_score": limit, "reason": reason})

    if n and removable:
        share = len(removable) / n
        if share >= 0.25:
            cap(2, f"{len(removable)} of {n} chapters removable (≥25%)")
        else:
            cap(3, f"{len(removable)} removable chapter(s)")
    if because_ratio is not None:
        if because_ratio < 0.5:
            cap(2, f"because-ratio {because_ratio:.2f} < 0.50")
        elif because_ratio < 0.65:
            cap(3, f"because-ratio {because_ratio:.2f} < 0.65")
        elif because_ratio < 0.8:
            cap(4, f"because-ratio {because_ratio:.2f} < 0.80")
    if ending_answers == "no":
        cap(2, "the ending does not answer the through-line")
    elif ending_answers == "partly":
        cap(3, "the ending only partly answers the through-line")
    if isinstance(posed_pct, (int, float)):
        if posed_pct > 50:
            cap(2, f"through-line posed at {posed_pct:.0f}% (after the midpoint)")
        elif posed_pct > 25:
            cap(3, f"through-line posed at {posed_pct:.0f}% (after the first quarter)")
    if isinstance(tl, dict) and tl.get("posed_in") is None:
        cap(2, "no chapter poses the through-line")
    if climax_verdict == "finishes":
        cap(3, "the last ~20% finishes threads instead of converging them")
    if vs_values:
        weak = [v for v in vs_values if v in ("level", "lower", "reset")]
        if len(weak) * 2 >= len(vs_values):
            cap(2, f"{len(weak)} of {len(vs_values)} act transitions do not raise the stake")
        elif weak:
            cap(3, f"act transition(s) that {'/'.join(sorted(set(weak)))} the stake")
    if risk == "high":
        cap(2, "episodic_risk high")
    elif risk == "medium":
        cap(3, "episodic_risk medium")
    if "anecdote-chain" in modes:
        cap(2, "named failure mode: anecdote-chain")
    rep.caps = caps
    if score is not None and caps:
        limit = min(c["max_score"] for c in caps)
        if score > limit:
            worst = [c["reason"] for c in caps if c["max_score"] == limit]
            err(f"structure_score {score} exceeds the rubric cap {limit} "
                f"({'; '.join(worst)}) — lower the score or correct the table")

    rep.summary = {
        "chapter_count": n,
        "links": counts, "because_ratio": because_ratio,
        "removable_chapters": sorted(removable),
        "structure_score": score,
        "max_score_by_rubric": min((c["max_score"] for c in caps), default=5),
        "candidates": len(cands),
        "cross_chapter_commands": [c.get("command") for c in cands
                                   if isinstance(c, dict) and c.get("kind") in CROSS_CHAPTER_KINDS],
    }
    rep.valid = not rep.errors
    return rep


# --------------------------------------------------------------------- gate


def _stale_chapters(path: Path, book_root: Path | None) -> list[int]:
    if book_root is None or not path.is_file():
        return []
    from ..paths import iter_chapter_files
    mtime = path.stat().st_mtime
    out: list[int] = []
    for p in iter_chapter_files(book_root / "chapters"):
        if p.stat().st_mtime > mtime:
            try:
                out.append(int(p.stem.split("_")[-1]))
            except ValueError:
                continue
    return sorted(out)


def check(path: Path, *, book_root: Path | None = None) -> ValidationReport:
    """Load + validate `path` and compute the stop-revising gate."""
    path = Path(path)
    if book_root is None and path.parent.name == "edit_logs":
        candidate = path.parent.parent
        if (candidate / "chapters").is_dir():
            book_root = candidate
    if not path.is_file():
        rep = ValidationReport(present=False, valid=False)
        rep.errors.append(f"no structure review at {path}")
        rep.gate = {"present": False, "passes": False, "stale": None,
                    "structure_score": None, "removable_chapters": None,
                    "reasons": ["no structure_review.json — run /autonovel:structure-review first"]}
        return rep
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        rep = ValidationReport(present=True, valid=False)
        rep.errors.append(f"cannot parse {path}: {exc}")
        rep.gate = {"present": True, "passes": False, "stale": None,
                    "structure_score": None, "removable_chapters": None,
                    "reasons": ["structure_review.json does not parse — re-run /autonovel:structure-review"]}
        return rep
    chapter_numbers = _chapter_numbers(book_root) or None
    rep = validate(data, chapter_numbers=chapter_numbers)
    stale = _stale_chapters(path, book_root)
    score = data.get("structure_score") if isinstance(data, dict) else None
    removable = rep.summary.get("removable_chapters", [])
    reasons: list[str] = []
    if not rep.valid:
        reasons.append("structure_review.json is invalid — re-run /autonovel:structure-review")
    if stale:
        reasons.append("stale: chapter(s) " + ", ".join(map(str, stale))
                       + " changed since the structure review — re-run /autonovel:structure-review")
    if _is_int(score) and score < GATE_MIN_SCORE:
        reasons.append(f"structure score {score}/5 is below {GATE_MIN_SCORE}")
    if removable:
        reasons.append("removable chapter(s): " + ", ".join(map(str, removable)))
    rep.gate = {
        "present": True,
        "passes": not reasons,
        "stale": bool(stale),
        "stale_chapters": stale,
        "structure_score": score if _is_int(score) else None,
        "removable_chapters": removable,
        "reasons": reasons,
    }
    return rep


def render_markdown(rep: ValidationReport, path: Path) -> str:
    lines = [f"# structure-validate — {path}", ""]
    if not rep.present:
        lines.append("⛔ No structure review yet. Run `/autonovel:structure-review --book <book>`.")
        return "\n".join(lines) + "\n"
    lines.append(("✅ valid" if rep.valid else f"❌ invalid ({len(rep.errors)} error(s))"))
    s = rep.summary
    if s:
        links = s.get("links", {})
        lines.append(
            f"- score {s.get('structure_score')}/5 (rubric max {s.get('max_score_by_rubric')}); "
            f"links because/after/unrelated = {links.get('because', 0)}/"
            f"{links.get('after', 0)}/{links.get('unrelated', 0)}; "
            f"removable: {', '.join(map(str, s.get('removable_chapters') or [])) or 'none'}")
    g = rep.gate
    lines.append(f"- book-level gate: {'PASS' if g.get('passes') else 'BLOCK'}")
    for r in g.get("reasons", []):
        lines.append(f"  - {r}")
    if rep.errors:
        lines += ["", "## Errors"] + [f"- {e}" for e in rep.errors]
    if rep.warnings:
        lines += ["", "## Warnings"] + [f"- {w}" for w in rep.warnings]
    return "\n".join(lines) + "\n"
