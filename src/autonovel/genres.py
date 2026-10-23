"""Genres and subgenres: what each kind of book promises its reader.

A book's genre decides what its reader comes for, and so what every
writing, reading and judging command must protect. A reader of
historical fiction comes partly to learn the period (real people and
events, daily life, places that still stand); a reader of hard science
fiction comes for science followed to its consequences. Before this
registry the pipeline knew neither, and its cold readers and judges
pushed to cut the very material the reader came for (kingmaker2,
2026-10-23).

`project.yaml` names the series' `genre:` and optional `subgenres:`; a
book may override either (`books[].genre`, `books[].subgenres`). Each
genre in the registry has a one-line promise per subgenre; a genre with a
written guide points at `shared/craft/genres/<id>.md` (package-owned,
refreshed by `autonovel refresh-templates`). A guide written for one
series by `/autonovel:genre --add` lives at `shared/genres/<id>.md` and
wins over the package's.

Every guide has the same sections, so a command can be told which to
read: see `GUIDE_SECTIONS`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# The sections every genre guide carries, in order, and who reads each.
GUIDE_SECTIONS: tuple[tuple[str, str], ...] = (
    ("The promise", "what this reader comes for; every command reads it"),
    ("Subgenres", "one ### per subgenre: its promise, conventions, obligatory scenes, comparables"),
    ("Research", "what to find out before designing: /autonovel:research, gen-world"),
    ("Design", "what the design must decide for this genre: design, gen-outline, cast"),
    ("Drafting", "how the payload reaches the page: draft, revise, brief"),
    ("The first reader", "who this genre's cold reader is and what else they report: first-read, draft"),
    ("Judging", "the genre's evaluate dimensions and what the judge must not mark down: evaluate, review, reader-panel"),
    ("Cutting", "what never counts as over-explaining: adversarial-edit, apply-cuts"),
    ("Editing", "what the developmental editor checks; typical failures: developmental-edit, structure-review"),
    ("Back matter", "notes and appendices this reader expects: appendix"),
    ("Sources", "every claim's source"),
)


@dataclass(frozen=True)
class Subgenre:
    id: str
    name: str
    promise: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Genre:
    id: str
    name: str
    promise: str
    subgenres: tuple[Subgenre, ...] = ()
    aliases: tuple[str, ...] = ()
    guide: str | None = None            # filename under shared/craft/genres/

    def subgenre(self, key: str) -> Subgenre | None:
        k = _norm(key)
        for s in self.subgenres:
            if k == s.id or k in s.aliases:
                return s
        return None


def _norm(text: str) -> str:
    return "-".join(str(text).strip().lower().replace("_", " ").replace("/", " ").split())


def _sg(id: str, name: str, promise: str, *aliases: str) -> Subgenre:
    return Subgenre(id=id, name=name, promise=promise, aliases=tuple(aliases))


GENRES: tuple[Genre, ...] = (
    Genre(
        id="historical",
        name="Historical fiction",
        promise=("The past made present: real events and people met on the page, how people "
                 "lived, worked and saw the world, and places, many still standing, under the "
                 "names they had then."),
        aliases=("historical-fiction", "historical-novel", "history"),
        guide="historical.md",
        subgenres=(
            _sg("biographical", "Biographical novel",
                "A real person's life, or its decisive stretch, from inside: the record kept, "
                "the motive imagined.", "fictional-biography", "biographical-novel",
                "biographical-fiction", "biofiction"),
            _sg("political-thriller", "Historical thriller (political)",
                "A contest for power against a deadline in a past whose outcome the reader may "
                "know: the suspense is how, how close and at what cost.",
                "historical-thriller", "thriller", "political", "intrigue"),
            _sg("traditional", "Traditional historical novel",
                "Invented people among real events, the period rendered whole."),
            _sg("adventure", "Adventures in history",
                "Campaigns, voyages and escapes: what soldiers and sailors did, carried and "
                "feared.", "military", "naval", "nautical", "war"),
            _sg("mystery", "Historical mystery",
                "A crime solved inside the period, with the period's own means of finding out.",
                "historical-mystery", "crime"),
            _sg("romance", "Romancing the past",
                "A love story whose obstacles are the period's: rank, law, faith, war.",
                "historical-romance", "romantic-historical"),
            _sg("saga", "Saga",
                "A family or a business followed across years or generations, living through "
                "the history that changes it.", "family-saga"),
            _sg("multi-period-epic", "Multi-period epic",
                "One place across centuries.", "epic"),
            _sg("western", "Western historical",
                "The American frontier as it was: land, law, labour and violence."),
            _sg("literary", "Literary historical",
                "The past as a way of seeing a life or an idea; language and interior first.",
                "literary-historical"),
            _sg("christian", "Christian historical",
                "Faith as the story's question, in a past setting.", "inspirational"),
            _sg("time-slip", "Time-slip / dual timeline",
                "A past and a present story that light each other.", "dual-timeline"),
            _sg("alternate-history", "Alternate history",
                "One recorded outcome changed, and its consequences followed honestly.",
                "alternative-history", "counterfactual"),
            _sg("historical-fantasy", "Historical fantasy",
                "The real past with one magical or uncanny element let in.", "fantasy"),
        ),
    ),
    Genre(
        id="science-fiction",
        name="Science fiction",
        promise=("A world changed by science or technology, and what the change does to people."),
        aliases=("scifi", "sci-fi", "sf"),
        subgenres=(
            _sg("hard-sf", "Hard SF",
                "Science that could be true, followed to its consequences; the science is part "
                "of the payload.", "hard-science-fiction"),
            _sg("space-opera", "Space opera",
                "Scale, wonder and adventure across worlds, with empires and their politics."),
            _sg("post-apocalyptic", "Post-apocalyptic",
                "Survival after the collapse, and what is rebuilt.", "post-apocalypse"),
            _sg("first-contact", "First contact",
                "The alien made truly other, and what meeting it does to us.",
                "alien-encounter", "first-alien-encounter"),
            _sg("dystopian", "Dystopian",
                "A society's logic followed to its human cost.", "dystopia"),
            _sg("cyberpunk", "Cyberpunk",
                "High tech and low life: bodies, networks and the companies that own them."),
            _sg("military-sf", "Military SF",
                "War with future means: command, duty and the cost of both."),
            _sg("time-travel", "Time travel",
                "Cause and paradox: a past or future changed by a visit."),
            _sg("near-future", "Near future",
                "Tomorrow's technology or politics, close enough to recognise."),
            _sg("climate", "Climate fiction",
                "A changed climate and how people live inside it.", "cli-fi"),
        ),
    ),
    Genre(
        id="fantasy",
        name="Fantasy",
        promise="A world with magic or wonder in it, with rules the story keeps.",
        subgenres=(
            _sg("epic", "Epic fantasy",
                "A whole secondary world at stake: wars, quests, a long road.", "high-fantasy"),
            _sg("urban", "Urban fantasy",
                "Magic hidden in, or loose in, a modern city.", "urban-fantasy"),
            _sg("sword-and-sorcery", "Sword and sorcery",
                "Danger and wonder at personal scale."),
            _sg("grimdark", "Grimdark",
                "Power struggles without clean sides, where every victory costs."),
            _sg("portal", "Portal fantasy",
                "A crossing from our world into another."),
            _sg("fairy-tale", "Fairy-tale retelling",
                "A known tale told anew.", "retelling"),
            _sg("historical-fantasy", "Historical fantasy",
                "The real past with one magical or uncanny element let in."),
        ),
    ),
    Genre(
        id="mystery",
        name="Mystery",
        promise="A puzzle the reader can solve alongside the detective, and justice at the end.",
        aliases=("crime", "detective"),
        subgenres=(
            _sg("cozy", "Cozy mystery",
                "A small community, an amateur sleuth, violence off the page.", "cosy"),
            _sg("private-eye", "Private eye",
                "A professional outsider working a case through a city.", "hardboiled", "pi"),
            _sg("police-procedural", "Police procedural",
                "How a real investigation works, from the inside.", "procedural"),
            _sg("fair-play", "Fair-play puzzle",
                "Every clue on the page before the solution; the locked room.",
                "golden-age", "locked-room"),
            _sg("historical", "Historical mystery",
                "A crime solved inside the period, with the period's own means.",
                "historical-mystery"),
            _sg("legal", "Legal mystery",
                "The case decided in court.", "courtroom"),
        ),
    ),
    Genre(
        id="thriller",
        name="Thriller",
        promise="A threat, a clock and a protagonist who must stop it: suspense to the last page.",
        aliases=("suspense",),
        subgenres=(
            _sg("political", "Political thriller",
                "Power, conspiracy and the state, against a deadline.", "political-thriller"),
            _sg("espionage", "Espionage",
                "Spies, secrets and betrayal.", "spy"),
            _sg("financial", "Financial thriller",
                "The money trail as the hunt; exposure as the stake.", "financial-thriller"),
            _sg("legal", "Legal thriller",
                "A case where losing costs a life or a career.", "legal-thriller"),
            _sg("psychological", "Psychological thriller",
                "The danger is in someone's mind, perhaps the narrator's.",
                "psychological-thriller"),
            _sg("techno", "Techno-thriller",
                "Technology as the weapon and the clue.", "techno-thriller"),
            _sg("action", "Action thriller",
                "Pursuit and physical danger, at pace."),
        ),
    ),
    Genre(
        id="romance",
        name="Romance",
        promise="Two people falling in love against what keeps them apart, and a happy ending.",
        subgenres=(
            _sg("contemporary", "Contemporary romance", "Love in the present day."),
            _sg("historical", "Historical romance",
                "Love in a past whose rules are the obstacle.", "historical-romance", "regency"),
            _sg("romantic-suspense", "Romantic suspense",
                "Love under threat; the danger brings them together.", "suspense"),
            _sg("paranormal", "Paranormal romance",
                "Love across a supernatural line."),
            _sg("romantic-comedy", "Romantic comedy",
                "Love as comedy of errors and wit.", "romcom"),
        ),
    ),
    Genre(
        id="horror",
        name="Horror",
        promise="Dread that builds to terror, and what fear shows about the people in it.",
        subgenres=(
            _sg("supernatural", "Supernatural horror", "Ghosts, demons, the dead that return."),
            _sg("psychological", "Psychological horror", "The terror is in the mind."),
            _sg("cosmic", "Cosmic horror",
                "A universe indifferent and too large to know.", "lovecraftian"),
            _sg("gothic", "Gothic",
                "Old houses, old families, old sins.", "gothic-horror"),
            _sg("folk", "Folk horror",
                "The land and its customs turned against the stranger.", "folk-horror"),
            _sg("body", "Body horror", "The body changed against its owner's will."),
        ),
    ),
    Genre(
        id="literary",
        name="Literary fiction",
        promise="A life or an idea seen freshly; language, interior and meaning first.",
    ),
    Genre(
        id="general",
        name="General fiction",
        promise="A story for its own sake, with no genre contract beyond the craft documents.",
    ),
)

_BY_KEY: dict[str, Genre] = {}
for _g in GENRES:
    _BY_KEY[_g.id] = _g
    for _a in _g.aliases:
        _BY_KEY[_a] = _g


def find(key: str | None) -> Genre | None:
    """The registry genre for `key` (id or alias, any case/spacing)."""
    if not key:
        return None
    return _BY_KEY.get(_norm(key))


@dataclass
class ResolvedGenre:
    """A book's genre after aliases and book-level overrides."""
    book: str | None
    raw_genre: str
    genre: Genre | None
    subgenres: list[Subgenre] = field(default_factory=list)
    other_subgenres: list[str] = field(default_factory=list)   # "other: …" or unknown
    guide_path: str | None = None          # series-relative, when the file exists
    guide_expected: str | None = None      # where the guide would be
    dimensions: list[str] = field(default_factory=list)  # from the guide's ## Judging
    warnings: list[str] = field(default_factory=list)

    @property
    def has_guide(self) -> bool:
        return self.guide_path is not None

    def label(self) -> str:
        name = self.genre.name if self.genre else (self.raw_genre or "general")
        subs = [s.name for s in self.subgenres] + self.other_subgenres
        return f"{name} ({', '.join(subs)})" if subs else name

    def to_dict(self) -> dict[str, Any]:
        g = self.genre
        return {
            "book": self.book,
            "genre": g.id if g else self.raw_genre,
            "genre_name": g.name if g else self.raw_genre,
            "promise": g.promise if g else None,
            "subgenres": [{"id": s.id, "name": s.name, "promise": s.promise}
                          for s in self.subgenres],
            "other_subgenres": list(self.other_subgenres),
            "guide": self.guide_path,
            "guide_expected": self.guide_expected,
            "dimensions": list(self.dimensions),
            "sections": [name for name, _ in GUIDE_SECTIONS],
            "warnings": list(self.warnings),
        }


_DIMENSION_HEADING_RE = re.compile(r"^###\s+The\s+`([a-z][a-z0-9_]*)`\s+dimension", re.MULTILINE)


def guide_dimensions(path: Path) -> list[str]:
    """The extra evaluate dimensions a guide defines: each `### The
    `<name>` dimension` heading (under `## Judging`)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return list(dict.fromkeys(_DIMENSION_HEADING_RE.findall(text)))


_LEDGER_RE = re.compile(r"ledger:\s*`##\s+([^`]+)`", re.IGNORECASE)


def guide_ledger_heading(path: Path) -> str | None:
    """The design section a guide's `## Design` asks for (written as
    "The ledger: `## <Heading>`"), or None."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _LEDGER_RE.search(text)
    return m.group(1).strip() if m else None


def resolve(cfg: Any, book: str | None = None, *, series_root: Path | None = None) -> ResolvedGenre:
    """Resolve the genre for `book` (or the series when None) from a
    `ProjectConfig`. Book-level `genre` / `subgenres` override the
    series'. With `series_root`, the guide path is checked on disk:
    `shared/genres/<id>.md` (series-owned) before
    `shared/craft/genres/<id>.md` (package-owned)."""
    entry = cfg.book_by_name(book) if book else None
    raw = (getattr(entry, "genre", None) or cfg.genre or "general")
    subs_raw = getattr(entry, "subgenres", None)
    if not subs_raw:
        subs_raw = getattr(cfg, "subgenres", None) or []
    g = find(raw)
    out = ResolvedGenre(book=book, raw_genre=str(raw), genre=g)
    if g is None:
        out.warnings.append(
            f"genre {raw!r} is not in the registry (autonovel genre list); commands "
            f"use the craft documents alone. `/autonovel:genre --add {_norm(raw)}` "
            f"researches and writes a guide for it.")
    for sraw in subs_raw:
        text = str(sraw).strip()
        if text.lower().startswith("other:"):
            out.other_subgenres.append(text.split(":", 1)[1].strip())
            continue
        s = g.subgenre(text) if g else None
        if s is None:
            out.other_subgenres.append(text)
            if g is not None:
                out.warnings.append(
                    f"subgenre {text!r} is not one of {g.name}'s "
                    f"({', '.join(x.id for x in g.subgenres) or 'none listed'}); "
                    f"write it as `other: {text}` to silence this")
        elif s not in out.subgenres:
            out.subgenres.append(s)
    gid = g.id if g else _norm(raw)
    candidates = [f"shared/genres/{gid}.md"]
    if g and g.guide:
        candidates.append(f"shared/craft/genres/{g.guide}")
    out.guide_expected = candidates[-1]
    if series_root is not None:
        for rel in candidates:
            if (series_root / rel).is_file():
                out.guide_path = rel
                out.dimensions = guide_dimensions(series_root / rel)
                break
        if out.guide_path is None and g is not None and g.guide:
            out.warnings.append(
                f"the {g.name} guide is missing at {candidates[-1]}; run "
                f"`autonovel refresh-templates`")
        elif out.guide_path is None and g is not None and g.id != "general":
            out.warnings.append(
                f"no guide written for {g.name} yet; `/autonovel:genre --add {g.id}` "
                f"researches and writes one")
    return out


def render_list() -> str:
    """The registry as markdown: each genre, its promise, guide status and
    subgenres with their one-line promises."""
    lines = ["# Genres", ""]
    for g in GENRES:
        guide = f"guide: shared/craft/genres/{g.guide}" if g.guide else "no guide yet"
        lines.append(f"## {g.name} (`{g.id}`) — {guide}")
        lines.append("")
        lines.append(g.promise)
        if g.subgenres:
            lines.append("")
            for s in g.subgenres:
                lines.append(f"- `{s.id}` **{s.name}**: {s.promise}")
        lines.append("")
    lines.append("Set a book's genre with `/autonovel:genre --set <genre> --subgenres a,b "
                 "--book <name>`; a subgenre not listed can be given as `other: <text>`.")
    return "\n".join(lines) + "\n"


def render_show(r: ResolvedGenre) -> str:
    lines = [f"# Genre — {r.book or 'series'}", "", f"**{r.label()}**", ""]
    if r.genre:
        lines.append(f"- Promise: {r.genre.promise}")
    for s in r.subgenres:
        lines.append(f"- {s.name}: {s.promise}")
    for o in r.other_subgenres:
        lines.append(f"- {o} (not in the registry)")
    lines.append(f"- Guide: {r.guide_path or '(none: ' + (r.guide_expected or '—') + ')'}")
    if r.dimensions:
        lines.append(f"- Extra evaluate dimensions: {', '.join(r.dimensions)}")
    for w in r.warnings:
        lines.append(f"- ⚠ {w}")
    return "\n".join(lines) + "\n"
