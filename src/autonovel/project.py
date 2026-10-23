"""project.yaml read/write and validation.

See REWRITE-PLAN.md §6 for the schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BookEntry:
    name: str
    pov: str | None = None
    story_time_range: list[int] | None = None
    status: str = "seed"
    # Display metadata, set by /autonovel:title (or hand-edited).
    # All optional — typeset falls back to `name` for `title` and to
    # the series-level `author` (or the placeholder "Anonymous") for
    # `author` when a book entry doesn't override.
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
    # Authoring mode (FUTURE-TODOS edit-imported):
    #   "draft" (default): autonovel writes chapters via /autonovel:draft.
    #   "edit-imported": prose was supplied by the user via
    #     /autonovel:import-book; /autonovel:draft refuses without
    #     --force so we don't accidentally overwrite the import.
    # Future modes welcome (e.g. "translate-imported") under the same
    # field; downstream commands check for "draft" specifically.
    mode: str = "draft"
    # Sibling-context policy for the story-time spoiler gate
    # (`context_loader.py`):
    #   "series" (default): other books' chapters whose story_time is
    #     <= this chapter's are legal drafting context.
    #   "isolated": NO sibling-book chapter is ever loaded as context.
    #     For a book that re-tells the same story as an existing book
    #     (a rewrite / second version) — the old prose must not anchor
    #     the new draft. Shared lore (world, characters, shared canon,
    #     events, research) is still read.
    context: str = "series"

    @property
    def is_isolated(self) -> bool:
        return self.context == "isolated"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.pov is not None:
            d["pov"] = self.pov
        if self.story_time_range is not None:
            d["story_time_range"] = list(self.story_time_range)
        d["status"] = self.status
        if self.title is not None:
            d["title"] = self.title
        if self.subtitle is not None:
            d["subtitle"] = self.subtitle
        if self.author is not None:
            d["author"] = self.author
        if self.mode != "draft":
            d["mode"] = self.mode
        if self.context != "series":
            d["context"] = self.context
        return d

    def display_title(self, fallback: str | None = None) -> str:
        """Return the book's display title — explicit `title` field if
        set, otherwise *fallback* (typically the series name) or the
        book's `name` slug as a last resort."""
        if self.title:
            return self.title
        if fallback:
            return fallback
        return self.name

    def display_author(self, fallback: str | None = None) -> str:
        """Return the book's author — explicit `author` field if set,
        otherwise *fallback* (typically the series-level author) or
        "Anonymous" as a last resort. Typeset uses this to fill the
        title page and ePub metadata."""
        if self.author:
            return self.author
        if fallback:
            return fallback
        return "Anonymous"


@dataclass
class ProjectConfig:
    series_name: str
    genre: str = "general"
    period: dict[str, Any] = field(default_factory=dict)
    llm: dict[str, Any] = field(default_factory=dict)
    books: list[BookEntry] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)
    # Per-series typeset overrides (PDF + ePub). Currently honoured:
    #   chapter_titles: bool = True — when False, the typeset path
    #     drops the per-chapter `title:` extraction so the TOC and
    #     chapter pages render numbers-only ("Chapter VII") instead
    #     of the evocative title ("Chapter VII — The Apothecary's
    #     Mortar"). Pairs with the `commands/draft.md` step that
    #     generates the title in the first place.
    # Other keys are reserved for future typeset toggles; unknown
    # keys are tolerated (no validation enforcement).
    typeset: dict[str, Any] = field(default_factory=dict)
    # Default image provider for art-curate / cover commands when no
    # `--provider` flag is passed. Common values: "pollinations",
    # "openai", "wikimedia". CLI flag overrides this.
    image: dict[str, Any] = field(default_factory=dict)
    # Per-series movie/teaser overrides (FUTURE-TODOS movie-teaser mode;
    # see docs/prd-movie-teaser-mode.md). Reserved keys include teaser
    # defaults (length_s, pace, ending, aspect_ratio). Unknown keys are
    # tolerated. Optional — omitted from YAML when empty.
    teaser: dict[str, Any] = field(default_factory=dict)
    # Default video provider + settings for teaser render (twin of
    # `image`). Common `provider` values: "pollinations" (no-auth free
    # default), "veo", "sora", "runway", "kling", "luma". CLI flag
    # overrides. Optional — omitted from YAML when empty.
    video: dict[str, Any] = field(default_factory=dict)
    # Series-level author — inherited by any BookEntry whose own
    # `author` field is unset. Optional; "Anonymous" if neither is set.
    author: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "series_name": self.series_name,
            "genre": self.genre,
            "period": dict(self.period),
            "llm": dict(self.llm),
            "books": [b.to_dict() for b in self.books],
            "defaults": dict(self.defaults),
        }
        if self.typeset:
            d["typeset"] = dict(self.typeset)
        if self.image:
            d["image"] = dict(self.image)
        if self.teaser:
            d["teaser"] = dict(self.teaser)
        if self.video:
            d["video"] = dict(self.video)
        if self.author is not None:
            d["author"] = self.author
        return d

    def book_by_name(self, name: str) -> BookEntry | None:
        for b in self.books:
            if b.name == name:
                return b
        return None

    @classmethod
    def default(cls, series_name: str, genre: str = "general") -> "ProjectConfig":
        return cls(
            series_name=series_name,
            genre=genre,
            period={},
            llm={
                "heavy": "claude-opus-4-7",
                "standard": "claude-sonnet-4-6",
                "light": "claude-haiku-4-5-20251001",
                "thinking": {"heavy": True, "standard": False},
            },
            books=[],
            defaults={
                "chapter_target_words": 3200,
                "foundation_threshold": 7.5,
                "chapter_threshold": 7.0,
                # Any one dimension under this sends a chapter to revise
                # even when its mean passes (the worst item, not the mean).
                "dimension_floor": 7.0,
            },
        )


REQUIRED_FIELDS = ("series_name",)
LLM_REQUIRED = ("heavy", "standard", "light")
BOOK_CONTEXT_MODES = ("series", "isolated")


class ProjectValidationError(ValueError):
    pass


def load(path: Path) -> ProjectConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ProjectValidationError(f"{path}: project.yaml must be a mapping")
    return _from_dict(raw)


def dump(cfg: ProjectConfig, path: Path) -> None:
    path.write_text(
        yaml.safe_dump(cfg.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _from_dict(raw: dict[str, Any]) -> ProjectConfig:
    for field_name in REQUIRED_FIELDS:
        if field_name not in raw:
            raise ProjectValidationError(f"project.yaml missing required field: {field_name}")

    books_raw = raw.get("books") or []
    if not isinstance(books_raw, list):
        raise ProjectValidationError("project.yaml: `books` must be a list")
    books: list[BookEntry] = []
    for i, b in enumerate(books_raw):
        if not isinstance(b, dict):
            raise ProjectValidationError(f"project.yaml: books[{i}] must be a mapping")
        if "name" not in b:
            raise ProjectValidationError(f"project.yaml: books[{i}] missing `name`")
        books.append(
            BookEntry(
                name=b["name"],
                pov=b.get("pov"),
                story_time_range=b.get("story_time_range"),
                status=b.get("status", "seed"),
                title=b.get("title"),
                subtitle=b.get("subtitle"),
                author=b.get("author"),
                mode=b.get("mode", "draft"),
                context=b.get("context", "series"),
            )
        )

    llm = raw.get("llm") or {}
    if llm and not isinstance(llm, dict):
        raise ProjectValidationError("project.yaml: `llm` must be a mapping")

    return ProjectConfig(
        series_name=raw["series_name"],
        genre=raw.get("genre", "general"),
        period=raw.get("period") or {},
        llm=llm,
        books=books,
        defaults=raw.get("defaults") or {},
        typeset=raw.get("typeset") or {},
        image=raw.get("image") or {},
        teaser=raw.get("teaser") or {},
        video=raw.get("video") or {},
        author=raw.get("author"),
    )


def validate(cfg: ProjectConfig) -> list[str]:
    """Return a list of validation problems (empty list == valid)."""
    problems: list[str] = []
    if not cfg.series_name or not isinstance(cfg.series_name, str):
        problems.append("series_name must be a non-empty string")
    if cfg.llm:
        for k in LLM_REQUIRED:
            if k not in cfg.llm:
                problems.append(f"llm.{k} missing")
    seen: set[str] = set()
    for b in cfg.books:
        if b.name in seen:
            problems.append(f"book name `{b.name}` appears more than once")
        seen.add(b.name)
        if b.story_time_range is not None:
            if (
                not isinstance(b.story_time_range, list)
                or len(b.story_time_range) != 2
                or not all(isinstance(x, int) for x in b.story_time_range)
                or b.story_time_range[0] > b.story_time_range[1]
            ):
                problems.append(
                    f"book `{b.name}` story_time_range must be [start, end] with start<=end"
                )
        if b.context not in BOOK_CONTEXT_MODES:
            problems.append(
                f"book `{b.name}` context must be one of {list(BOOK_CONTEXT_MODES)}, got {b.context!r}"
            )
    return problems
