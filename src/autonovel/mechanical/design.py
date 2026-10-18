"""Validate a book's `design.md` — the stage before the outline.

`autonovel mechanical design-validate <book_dir> [--outline]` parses
`books/<book>/design.md` (written by `/autonovel:design`, grammar below)
and checks the structural promises `shared/craft/DESIGN.md` Part II asks
of a design: a question posed in the first quarter, a climax that spends
at least three plants, every plant planted before it pays, an opponent
on stage in every act and winning once before the climax, at least two
rehearsals with one failure, a cast with wants, fears and secrets,
sequences that cover the book, and the D1–D14 tests recorded with none
failing. With `--outline` it also checks that `outline.md` carries the
design: every plant, test and payoff listed on its chapter, the spine
question the same, the chapter count the same.

Why it exists: a book in this pipeline was revised four times after an
editor's diagnosis and still read as a string of episodes, because the
fault was in a design nobody had written down. The design stage writes
it down; this helper checks its shape. It does not judge whether the
design is good — that is the designer's and the cold reader's job (D14).
Pure parsing, no LLM.

Grammar (the sections `/autonovel:design` writes; `- key: value`
bullets unless noted):

    ## Author's intent        bullets (the author's directions, how each is honoured)
    ## Pitch                  a paragraph
    ## Dramatic question      question (ends in ?), posed_in, posed_by, answered_in
    ## Climax                 chapter, scene, action, spends (P-ids), cost, threads
    ## Shape                  pattern, span, chapters, target_words, redesign_of (optional)
    ## Controlling idea       a paragraph or bullets
    ## Protagonist            name, want, need, misbelief, wound, contradiction, signature
    ## Opponent               name, wants, plan (dated sub-bullets), appears_in, wins_in
    ## Plants                 - P1 <name>: <what> | plant: ch N (<contest>) | test: ch N | payoff: ch N
    ## Rehearsals             - R1 <name> (ch A–B): <what> | teaches: P1, P2 | outcome: <succeeds|fails …>
    ## Cast                   ### <Name> — <function>, then want, fear, secret,
                              contradiction, signature, entrance, arc
    ## Sequences              - S1 (ch A–B) <title>: <question> | hands on: <result>
    ## Clocks                 bullets
    ## Stakes ladder          | Act | Chapters | Stake | Higher because |
    ## Reader questions       bullets
    ## Places                 ### <Place>, then orientation, use, signature, arrival, only here
    ## Terms                  - <term>: ch N — <plain gloss>   (recommended; warning if absent)
    ## Voice                  bullets
    ## Genre contract         bullets
    ## Keep ledger            bullets (required when Shape has redesign_of)
    ## Fault ledger           bullets (required when Shape has redesign_of)
    ## Design tests           - D1 pass: <evidence>   (pass | fail | n/a)

`ch 5`, `ch. 5`, `chapter 5` and `5` all name chapter 5; ranges take
`-` or `–`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_SECTIONS: tuple[str, ...] = (
    "Author's intent", "Pitch", "Dramatic question", "Climax", "Shape",
    "Controlling idea", "Protagonist", "Opponent", "Plants", "Rehearsals",
    "Cast", "Sequences", "Clocks", "Stakes ladder", "Reader questions",
    "Places", "Voice", "Genre contract", "Design tests",
)
REDESIGN_SECTIONS: tuple[str, ...] = ("Keep ledger", "Fault ledger")
DESIGN_TESTS: tuple[str, ...] = tuple(f"D{i}" for i in range(1, 15))
CAST_FIELDS: tuple[str, ...] = ("want", "fear", "secret", "entrance")

_H2 = re.compile(r"^##\s+(.+?)\s*$")
_H3 = re.compile(r"^###\s+(.+?)\s*$")
_KV = re.compile(r"^\s*[-*]\s+([A-Za-z][\w '’/-]*?)\s*:\s*(.*)$")
_CH = re.compile(r"(?:\bch(?:apter)?\.?\s*)?(\d{1,3})\b", re.IGNORECASE)
_RANGE = re.compile(r"\bch(?:apters?)?\.?\s*(\d{1,3})\s*(?:[-–—]|to)\s*(\d{1,3})", re.IGNORECASE)
_PID = re.compile(r"\bP(\d+)\b")
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}


def _canon(name: str) -> str:
    return name.strip().strip("*").replace("’", "'").rstrip(":").strip().lower()


def _first_int(s: str) -> int | None:
    m = _CH.search(s or "")
    return int(m.group(1)) if m else None


def _ints(s: str) -> list[int]:
    out: list[int] = []
    for part in re.split(r"[,;]", s or ""):
        r = re.search(r"(\d{1,3})\s*[-–—]\s*(\d{1,3})", part)
        if r:
            a, b = int(r.group(1)), int(r.group(2))
            out.extend(range(min(a, b), max(a, b) + 1))
        else:
            n = _first_int(part)
            if n is not None:
                out.append(n)
    return out


@dataclass
class Plant:
    pid: str
    name: str
    what: str
    plant: int | None
    test: int | None
    payoff: int | None

    def to_dict(self) -> dict:
        return {"id": self.pid, "name": self.name, "what": self.what,
                "plant": self.plant, "test": self.test, "payoff": self.payoff}


@dataclass
class Design:
    sections: dict[str, str] = field(default_factory=dict)       # canon name -> body
    titles: dict[str, str] = field(default_factory=dict)         # canon name -> heading as written
    kv: dict[str, dict[str, str]] = field(default_factory=dict)  # section -> key -> value
    plants: list[Plant] = field(default_factory=list)
    rehearsals: list[dict] = field(default_factory=list)
    cast: list[dict] = field(default_factory=list)
    places: list[dict] = field(default_factory=list)
    sequences: list[dict] = field(default_factory=list)
    acts: list[dict] = field(default_factory=list)                # {act, first, last}
    tests: dict[str, dict] = field(default_factory=dict)          # D1 -> {verdict, note}
    unparsed: list[str] = field(default_factory=list)            # lines that look like ledger rows but don't parse

    def get(self, section: str, key: str) -> str:
        return self.kv.get(_canon(section), {}).get(_canon(key), "")


def _split_sections(text: str) -> tuple[dict[str, str], dict[str, str]]:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    sections: dict[str, list[str]] = {}
    titles: dict[str, str] = {}
    cur: str | None = None
    for line in text.splitlines():
        m = _H2.match(line)
        if m and not line.startswith("###"):
            cur = _canon(m.group(1))
            titles[cur] = m.group(1).strip()
            sections.setdefault(cur, [])
            continue
        if cur is not None:
            sections[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}, titles


def _kv(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in body.splitlines():
        if line.startswith("  ") and not line.lstrip().startswith(("-", "*")):
            continue
        m = _KV.match(line)
        if m and not line.startswith(("    ", "\t")):
            out.setdefault(_canon(m.group(1)), m.group(2).strip())
    return out


def _subsections(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, list[str]]] = []
    for line in body.splitlines():
        m = _H3.match(line)
        if m:
            out.append((m.group(1).strip(), []))
        elif out:
            out[-1][1].append(line)
    return [(h, "\n".join(b)) for h, b in out]


def _field(parts: list[str], key: str) -> str | None:
    for p in parts:
        m = re.match(rf"\s*{key}\s*:\s*(.*)$", p, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_design(text: str) -> Design:
    d = Design()
    d.sections, d.titles = _split_sections(text)
    for name, body in d.sections.items():
        d.kv[name] = _kv(body)

    for line in d.sections.get("plants", "").splitlines():
        m = re.match(r"^\s*[-*]\s+(P\d+)\b\s*([^:|]*?)\s*:\s*(.*)$", line)
        if not m:
            if re.match(r"^\s*[-*]\s+P\d+\b", line):
                d.unparsed.append(f"## Plants: cannot parse {line.strip()[:80]!r} "
                                  f"(expected `- P1 <name>: <what> | plant: ch N …`)")
            continue
        parts = m.group(3).split("|")
        d.plants.append(Plant(
            pid=m.group(1), name=m.group(2).strip(), what=parts[0].strip(),
            plant=_first_int(_field(parts[1:], "plant") or ""),
            test=_first_int(_field(parts[1:], "test") or ""),
            payoff=_first_int(_field(parts[1:], "payoff") or ""),
        ))

    for line in d.sections.get("rehearsals", "").splitlines():
        m = re.match(r"^\s*[-*]\s+(R\d+)\b(.*)$", line)
        if not m:
            continue
        parts = m.group(2).split("|")
        rng = _RANGE.search(parts[0])
        d.rehearsals.append({
            "id": m.group(1), "text": parts[0].strip(" :"),
            "chapters": [int(rng.group(1)), int(rng.group(2))] if rng else _ints(parts[0])[:1],
            "teaches": sorted({f"P{n}" for n in _PID.findall(_field(parts[1:], "teaches") or "")},
                              key=lambda x: int(x[1:])),
            "outcome": _field(parts[1:], "outcome") or "",
        })

    for head, body in _subsections(d.sections.get("cast", "")):
        name, function = head, ""
        if re.search(r"\s[—–-]\s", head):
            name, function = re.split(r"\s+[—–-]\s+", head, maxsplit=1)
        fields = _kv(body)
        d.cast.append({"name": name.strip(), "function": function.strip(), "fields": fields})

    for head, body in _subsections(d.sections.get("places", "")):
        d.places.append({"name": head, "fields": _kv(body)})

    for line in d.sections.get("sequences", "").splitlines():
        m = re.match(r"^\s*[-*]\s+(S\d+)\b(.*)$", line)
        if not m:
            continue
        rng = _RANGE.search(m.group(2))
        one = re.search(r"\(\s*ch(?:apter)?\.?\s*(\d{1,3})\s*\)", m.group(2), re.IGNORECASE)
        first = int(rng.group(1)) if rng else (int(one.group(1)) if one else None)
        last = int(rng.group(2)) if rng else first
        parts = m.group(2).split("|")
        d.sequences.append({"id": m.group(1), "first": first, "last": last,
                            "text": parts[0].strip(" :"),
                            "hands_on": _field(parts[1:], "hands on") or ""})

    for line in d.sections.get("stakes ladder", "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not line.strip().startswith("|"):
            continue
        act, chs = cells[0].strip("* "), cells[1]
        if act.lower() in ("act", "") or set(act) <= set("-: "):
            continue
        nums = _ints(chs)
        if nums:
            d.acts.append({"act": act, "first": min(nums), "last": max(nums)})

    for line in d.sections.get("design tests", "").splitlines():
        m = re.match(r"^\s*[-*]\s+\**(D\d+)\b[^:]*?\b(pass|fail|n/a)\b\**\s*[:—–-]?\s*(.*)$",
                     line, re.IGNORECASE)
        if m:
            d.tests[m.group(1).upper()] = {"verdict": m.group(2).lower(), "note": m.group(3).strip()}
    return d


def _act_of(design: Design, chapter: int | None) -> str | None:
    if chapter is None:
        return None
    for a in design.acts:
        if a["first"] <= chapter <= a["last"]:
            return a["act"]
    return None


# ------------------------------------------------------------------ outline
_OUT_CH = re.compile(r"^##\s+Chapter\s+(\d+)\b", re.IGNORECASE)


def parse_outline_bindings(text: str) -> dict[int, dict[str, set[str] | str]]:
    """Per outline chapter: the P-ids on its `- plants:`, `- tests:` and
    `- payoffs:` lines, its `- sequence:` id and its whole entry text."""
    out: dict[int, dict] = {}
    cur: int | None = None
    for line in text.splitlines():
        m = _OUT_CH.match(line)
        if m:
            cur = int(m.group(1))
            out[cur] = {"plants": set(), "tests": set(), "payoffs": set(),
                        "sequence": "", "text": line + "\n"}
            continue
        if line.startswith("## "):
            cur = None
            continue
        if cur is None:
            continue
        out[cur]["text"] += line + "\n"
        kv = re.match(r"^\s*[-*]\s+(plants|tests|payoffs|sequence)\s*:\s*(.*)$", line, re.IGNORECASE)
        if kv:
            key = kv.group(1).lower()
            if key == "sequence":
                out[cur]["sequence"] = kv.group(2).strip()
            else:
                out[cur][key] |= {f"P{n}" for n in _PID.findall(kv.group(2))}
    return out


def _outline_question(text: str) -> str:
    m = re.search(r"^##\s+Spine\s*$(.*?)(?=^##\s)", text + "\n## end", re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    return _kv(m.group(1)).get("question", "")


# ------------------------------------------------------------------ checks
@dataclass
class Report:
    present: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.present and not self.errors

    def to_dict(self) -> dict:
        return {"present": self.present, "ok": self.ok, "errors": self.errors,
                "warnings": self.warnings, "summary": self.summary}


def check_design(d: Design, *, outline_text: str | None = None) -> Report:
    rep = Report(present=True)
    err, warn = rep.errors.append, rep.warnings.append
    for u in d.unparsed:
        err(u)
    redesign = bool(d.get("shape", "redesign_of"))
    for s in REQUIRED_SECTIONS + (REDESIGN_SECTIONS if redesign else ()):
        if _canon(s) not in d.sections or not d.sections[_canon(s)].strip():
            err(f"missing or empty section: ## {s}")

    chapters = _first_int(d.get("shape", "chapters"))
    if chapters is None:
        err("## Shape: no `chapters:` count")

    q = d.get("dramatic question", "question")
    if not q:
        err("## Dramatic question: no `question:`")
    elif not q.rstrip().rstrip("*").endswith("?"):
        err(f"## Dramatic question: the question does not end in '?': {q!r}")
    posed = _first_int(d.get("dramatic question", "posed_in"))
    if posed is None:
        err("## Dramatic question: no `posed_in:` chapter")
    elif chapters and posed > max(1, round(chapters * 0.25)):
        err(f"## Dramatic question: posed in ch {posed}, after the first quarter "
            f"(ch {max(1, round(chapters * 0.25))} of {chapters}) — DESIGN.md D3")
    if not d.get("dramatic question", "posed_by"):
        warn("## Dramatic question: no `posed_by:` (who asks it on the page)")
    answered = _first_int(d.get("dramatic question", "answered_in"))

    climax = _first_int(d.get("climax", "chapter"))
    if climax is None:
        err("## Climax: no `chapter:`")
    if answered is not None and climax is not None and answered < climax:
        warn(f"the question is answered in ch {answered}, before the climax (ch {climax})")
    for k in ("action", "cost"):
        if not d.get("climax", k):
            err(f"## Climax: no `{k}:` — DESIGN.md D2")

    pids = {p.pid for p in d.plants}
    spends = sorted({f"P{n}" for n in _PID.findall(d.get("climax", "spends"))},
                    key=lambda x: int(x[1:]))
    spends_known = [p for p in spends if f"{p}" in pids]
    if len(spends_known) < 3:
        err(f"## Climax spends {len(spends_known)} known plant(s) ({', '.join(spends) or 'none'}); "
            f"DESIGN.md D2 asks for at least three")
    for p in spends:
        if p not in pids:
            err(f"## Climax spends {p}, which is not in ## Plants")
    plant_acts = {_act_of(d, p.plant) for p in d.plants if p.pid in spends_known} - {None}
    if d.acts and spends_known and len(plant_acts) < 2:
        warn("the climax's plants are all planted in one act — DESIGN.md D2 asks for two or more")

    if not d.plants:
        err("## Plants: no `- P1 …` lines")
    for p in d.plants:
        if p.plant is None or p.payoff is None:
            err(f"{p.pid}: needs both `plant: ch N` and `payoff: ch N`")
            continue
        if p.test is None:
            warn(f"{p.pid}: no `test:` chapter (plant, test, pay — DESIGN.md §8)")
        if not p.plant < p.payoff:
            err(f"{p.pid}: planted in ch {p.plant} but pays in ch {p.payoff}")
        if p.test is not None and not (p.plant <= p.test <= p.payoff):
            err(f"{p.pid}: test in ch {p.test} is not between plant ch {p.plant} "
                f"and payoff ch {p.payoff}")
        if chapters and max(p.plant, p.payoff) > chapters:
            err(f"{p.pid}: names a chapter beyond the book's {chapters}")

    opp = d.get("opponent", "name")
    if not opp:
        err("## Opponent: no `name:`")
    if not d.get("opponent", "wants"):
        err("## Opponent: no `wants:` (the same prize — DESIGN.md D5)")
    plan_lines = [ln for ln in d.sections.get("opponent", "").splitlines()
                  if re.match(r"^\s{2,}[-*]\s+\S", ln)]
    if not plan_lines:
        err("## Opponent: no dated `plan:` sub-bullets")
    appears = _ints(d.get("opponent", "appears_in"))
    if not appears:
        err("## Opponent: no `appears_in:` chapters")
    elif d.acts:
        missing = [a["act"] for a in d.acts
                   if not any(a["first"] <= c <= a["last"] for c in appears)]
        if missing:
            err(f"## Opponent is not on stage in act(s) {', '.join(missing)} — DESIGN.md D5")
    wins = _ints(d.get("opponent", "wins_in"))
    if not wins:
        err("## Opponent: no `wins_in:` — he must win on the page before the climax")
    elif climax is not None and min(wins) >= climax:
        err(f"## Opponent first wins in ch {min(wins)}, not before the climax (ch {climax})")

    if len(d.rehearsals) < 2:
        err(f"## Rehearsals: {len(d.rehearsals)} found; DESIGN.md D7 asks for at least two")
    elif not any(re.search(r"\bfail", r["outcome"], re.IGNORECASE) for r in d.rehearsals):
        err("## Rehearsals: none has an outcome that fails — DESIGN.md D7")
    for r in d.rehearsals:
        for t in r["teaches"]:
            if t not in pids:
                warn(f"{r['id']} teaches {t}, which is not in ## Plants")

    if not d.cast:
        err("## Cast: no `### <Name> — <function>` entries")
    for c in d.cast:
        lacking = [f for f in CAST_FIELDS if not c["fields"].get(f)]
        if lacking:
            warn(f"Cast: {c['name']} has no {', '.join(lacking)} — DESIGN.md D8")
        if not c["function"]:
            warn(f"Cast: {c['name']} has no function in the heading (### Name — function)")

    if not d.sequences:
        err("## Sequences: no `- S1 (ch A–B) …` lines")
    else:
        if not 6 <= len(d.sequences) <= 10:
            warn(f"## Sequences: {len(d.sequences)}; DESIGN.md §10 suggests six to ten")
        covered: set[int] = set()
        for s in d.sequences:
            if s["first"] is None:
                err(f"{s['id']}: no chapter range `(ch A–B)`")
                continue
            covered |= set(range(s["first"], s["last"] + 1))
        if chapters:
            gaps = sorted(set(range(1, chapters + 1)) - covered)
            if gaps:
                err(f"## Sequences leave chapters {', '.join(map(str, gaps))} uncovered")
        for s in d.sequences[:-1]:
            if not s["hands_on"]:
                warn(f"{s['id']}: no `hands on:` (the result that forces the next sequence)")

    if not d.acts:
        err("## Stakes ladder: no act rows with chapter ranges")
    if not d.places:
        warn("## Places: no `### <Place>` entries")
    if "terms" not in d.sections or not d.sections["terms"].strip():
        warn("## Terms: none listed — the words a reader today may not know, "
             "each with the chapter that explains it (DESIGN.md §13a)")
    for pl in d.places:
        for f in ("orientation", "use", "signature"):
            if not pl["fields"].get(f):
                warn(f"Places: {pl['name']} has no `{f}:` — DESIGN.md D11")

    for t in DESIGN_TESTS:
        if t not in d.tests:
            err(f"## Design tests: {t} not recorded (`- {t} pass|fail|n/a: …`)")
        elif d.tests[t]["verdict"] == "fail":
            err(f"## Design tests: {t} fails — change the design, not the test: "
                f"{d.tests[t]['note'][:160]}")

    if outline_text is not None:
        bind = parse_outline_bindings(outline_text)
        if not bind:
            err("outline.md: no `## Chapter N` entries")
        if chapters and bind and len(bind) != chapters:
            warn(f"outline.md has {len(bind)} chapters; design.md says {chapters}")
        for p in d.plants:
            for role, ch in (("plants", p.plant), ("tests", p.test), ("payoffs", p.payoff)):
                if ch is None:
                    continue
                entry = bind.get(ch)
                if entry is None:
                    err(f"{p.pid}: design puts its {role[:-1]} in ch {ch}, which the outline lacks")
                elif p.pid not in entry[role]:
                    err(f"outline ch {ch}: `- {role}:` does not list {p.pid} ({p.name or p.what[:40]})")
        oq = _outline_question(outline_text)
        if q and oq and _canon(oq) != _canon(q):
            warn("outline ## Spine question differs from design.md's dramatic question")
        if opp and appears:
            # "Ambrosius Höchstetter (b. 1463), head of …" → "Höchstetter"
            bare = re.split(r"[(,;—–]", opp, maxsplit=1)[0].strip() or opp
            surname = bare.split()[-1].strip(",.")
            for c in appears:
                e = bind.get(c)
                if e is not None and surname.lower() not in e["text"].lower():
                    warn(f"outline ch {c}: the opponent ({opp}) should be on stage but is not named")

    rep.summary = {
        "chapters": chapters, "acts": [a["act"] for a in d.acts],
        "question": q, "posed_in": posed, "answered_in": answered, "climax": climax,
        "climax_spends": spends, "plants": [p.to_dict() for p in d.plants],
        "opponent": opp, "opponent_appears_in": appears, "opponent_wins_in": wins,
        "rehearsals": [{"id": r["id"], "chapters": r["chapters"], "outcome": r["outcome"]}
                       for r in d.rehearsals],
        "cast": [c["name"] for c in d.cast], "places": [p["name"] for p in d.places],
        "sequences": [{"id": s["id"], "first": s["first"], "last": s["last"]}
                      for s in d.sequences],
        "tests": {k: v["verdict"] for k, v in d.tests.items()},
        "redesign_of": d.get("shape", "redesign_of") or None,
    }
    return rep


def check(book_root: Path, *, outline: bool = False) -> Report:
    path = book_root / "design.md"
    if not path.is_file():
        rep = Report(present=False)
        rep.errors.append(f"no design.md at {path} — run /autonovel:design")
        return rep
    outline_text = None
    if outline:
        op = book_root / "outline.md"
        outline_text = op.read_text(encoding="utf-8") if op.is_file() else ""
    return check_design(parse_design(path.read_text(encoding="utf-8")), outline_text=outline_text)


def render_markdown(rep: Report, path: Path) -> str:
    lines = [f"# design-validate: {path}", "",
             f"**{'OK' if rep.ok else 'NOT OK'}** — {len(rep.errors)} error(s), "
             f"{len(rep.warnings)} warning(s)", ""]
    if rep.errors:
        lines += ["## Errors", *[f"- {e}" for e in rep.errors], ""]
    if rep.warnings:
        lines += ["## Warnings", *[f"- {w}" for w in rep.warnings], ""]
    s = rep.summary
    if s:
        lines += ["## Summary",
                  f"- chapters: {s.get('chapters')}; acts: {', '.join(s.get('acts') or [])}",
                  f"- question: {s.get('question')} (posed ch {s.get('posed_in')}, "
                  f"climax ch {s.get('climax')})",
                  f"- climax spends: {', '.join(s.get('climax_spends') or [])}",
                  f"- opponent: {s.get('opponent')} — on stage {s.get('opponent_appears_in')}, "
                  f"wins {s.get('opponent_wins_in')}",
                  f"- plants: {len(s.get('plants') or [])}; rehearsals: "
                  f"{len(s.get('rehearsals') or [])}; cast: {len(s.get('cast') or [])}; "
                  f"sequences: {len(s.get('sequences') or [])}"]
    return "\n".join(lines).rstrip() + "\n"


def to_json(rep: Report, path: Path) -> str:
    return json.dumps({"path": str(path), **rep.to_dict()}, indent=2, ensure_ascii=False) + "\n"
