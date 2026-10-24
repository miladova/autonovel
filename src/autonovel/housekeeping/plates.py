"""User-supplied image plates — `autonovel art-import`.

A "plate" is a user-supplied image that should appear in the typeset
PDF (and ePub where supported). Use cases that drove the design
2026-04-25:

  - A famous historical map (e.g. Venice c. 1500).
  - A period painting or portrait (e.g. Dürer's Jakob Fugger).
  - A larger-scale map (e.g. Hanseatic / Venetian trade routes).
  - Smaller atmospheric inserts (a bag of spices, a Dürer woodcut of
    an Augsburg church).

Plates live alongside chapter prose, not inside it: the typeset path
inserts each plate as a dedicated page (or a centered block at a
chapter heading) at the position the manifest specifies. The chapter
markdown stays plain prose — nothing in the writing pipeline cares
about plates.

This module is pure I/O + manifest manipulation. The LaTeX
generation that turns the manifest into typeset output lives in
`autonovel.mechanical.latex`.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

import yaml


# Where in the chapter flow a plate goes. `before-chapter` is the
# most common for historical fiction full-page plates; the at-start
# variant inserts the plate inside the chapter just below the heading.
Placement = Literal["before-chapter", "chapter-start", "after-chapter"]
PLACEMENTS: tuple[Placement, ...] = ("before-chapter", "chapter-start", "after-chapter")

# Image kind: a `plate` is a full-quality image with a caption block;
# an `ornament` overrides the AI-generated chapter ornament with the
# user's own art at the chapter heading (small, monochrome by
# convention).
Kind = Literal["plate", "ornament"]
KINDS: tuple[Kind, ...] = ("plate", "ornament")

# Acceptable source extensions. We re-use the user's extension on the
# installed copy so LaTeX/ePub pick the right reader.
ACCEPTED_EXTS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".pdf", ".svg", ".tiff", ".tif")

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_OWN_KEYS = ("slug", "file", "placement", "chapter", "caption", "attribution")


@dataclass
class Plate:
    slug: str
    file: str  # path relative to books/{book}/typeset/, e.g. "plates/venice-1500.png"
    placement: Placement
    chapter: int  # 1-indexed
    caption: str = ""
    attribution: str = ""
    # Keys the importer doesn't own (`layout: landscape`, added by hand),
    # carried through every rewrite of the manifest unchanged.
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "file": self.file,
            "placement": self.placement,
            "chapter": self.chapter,
            "caption": self.caption,
            "attribution": self.attribution,
            **self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plate":
        return cls(
            slug=str(d["slug"]),
            file=str(d["file"]),
            placement=str(d.get("placement", "before-chapter")),
            chapter=int(d["chapter"]),
            caption=str(d.get("caption", "") or ""),
            attribution=str(d.get("attribution", "") or ""),
            extra={k: v for k, v in d.items() if k not in _OWN_KEYS},
        )


@dataclass
class ImportResult:
    plate: Plate | None  # None when kind=ornament (no manifest entry)
    installed_path: Path
    kind: Kind
    overwrote: bool


class ImportError(ValueError):
    pass


def slugify(name: str) -> str:
    """Normalise an arbitrary string into a filename-safe slug."""
    cleaned = _SLUG_RE.sub("-", name.lower()).strip("-")
    return cleaned or "untitled"


def import_image(
    book_root: Path,
    source: Path,
    *,
    chapter: int,
    kind: Kind = "plate",
    placement: Placement = "before-chapter",
    slug: str | None = None,
    caption: str = "",
    attribution: str = "",
    force: bool = False,
) -> ImportResult:
    """Copy `source` into the book's typeset tree and (for plates)
    register it in `plates.yaml`.

    For `kind="plate"`: file goes to
    `books/{book}/typeset/plates/<slug>.<ext>` and a Plate entry is
    appended to `books/{book}/typeset/plates.yaml`.

    For `kind="ornament"`: file goes to
    `books/{book}/art/ornaments/ch_NN.<ext>` (overrides the
    AI-generated ornament at the same path). No manifest entry —
    the typeset path picks up files in that directory directly.

    Idempotent across slug — re-importing the same slug overwrites
    the prior file (with `force=True`) or refuses (default).
    """
    if kind not in KINDS:
        raise ImportError(f"unknown kind {kind!r}; must be one of {KINDS}")
    if placement not in PLACEMENTS:
        raise ImportError(f"unknown placement {placement!r}; must be one of {PLACEMENTS}")
    if not source.is_file():
        raise ImportError(f"source file not found: {source}")
    ext = source.suffix.lower()
    if ext not in ACCEPTED_EXTS:
        raise ImportError(
            f"unsupported image extension {ext!r}; accepted: {ACCEPTED_EXTS}"
        )

    if kind == "ornament":
        return _import_as_ornament(
            book_root, source, chapter=chapter, ext=ext, force=force,
        )

    return _import_as_plate(
        book_root, source,
        chapter=chapter,
        ext=ext,
        placement=placement,
        slug=slug,
        caption=caption,
        attribution=attribution,
        force=force,
    )


def _import_as_ornament(
    book_root: Path, source: Path, *, chapter: int, ext: str, force: bool,
) -> ImportResult:
    target_dir = book_root / "art" / "ornaments"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"ch_{chapter:02d}{ext}"
    overwrote = target.exists()
    if overwrote and not force:
        raise ImportError(
            f"{target} already exists; pass force=True to overwrite"
        )
    shutil.copyfile(source, target)
    return ImportResult(plate=None, installed_path=target, kind="ornament", overwrote=overwrote)


def _import_as_plate(
    book_root: Path, source: Path, *,
    chapter: int, ext: str, placement: Placement,
    slug: str | None, caption: str, attribution: str, force: bool,
) -> ImportResult:
    if slug is None:
        slug = slugify(source.stem)
    typeset = book_root / "typeset"
    plates_dir = typeset / "plates"
    plates_dir.mkdir(parents=True, exist_ok=True)
    target = plates_dir / f"{slug}{ext}"
    overwrote = target.exists()
    if overwrote and not force:
        raise ImportError(
            f"{target} already exists; pass force=True to overwrite"
        )
    shutil.copyfile(source, target)

    manifest_path = typeset / "plates.yaml"
    plates = read_manifest(manifest_path)
    plate = Plate(
        slug=slug,
        file=str(target.relative_to(typeset)),
        placement=placement,  # type: ignore[arg-type]
        chapter=chapter,
        caption=caption,
        attribution=attribution,
    )
    # Replace any existing entry with the same slug (idempotent re-import),
    # keeping the keys added to it by hand.
    old = next((p for p in plates if p.slug == slug), None)
    if old is not None:
        plate.extra = dict(old.extra)
    plates = [p for p in plates if p.slug != slug] + [plate]
    plates.sort(key=lambda p: (p.chapter, _placement_order(p.placement), p.slug))
    write_manifest(manifest_path, plates)

    return ImportResult(plate=plate, installed_path=target, kind="plate", overwrote=overwrote)


def _placement_order(placement: str) -> int:
    try:
        return PLACEMENTS.index(placement)  # type: ignore[arg-type]
    except ValueError:
        return len(PLACEMENTS)


def read_manifest(path: Path) -> list[Plate]:
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ImportError(f"plates manifest is malformed: {e}")
    raw = data.get("plates") or []
    if not isinstance(raw, list):
        raise ImportError(f"plates manifest is malformed: `plates` must be a list, got {type(raw).__name__}")
    return [Plate.from_dict(d) for d in raw]


def write_manifest(path: Path, plates: Iterable[Plate]) -> None:
    payload = {"plates": [p.to_dict() for p in plates]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
