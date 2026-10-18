"""ePub-ready combined-markdown builder.

Bug story (2026-04-25): the previous ePub path passed
`books/{book}/chapters/ch_*.md` directly to pandoc as a shell glob,
which:

  1. Matched `ch_NN.summary.md` as well as `ch_NN.md`, so the
     continuity-handoff summaries (POV / threads_opened /
     threads_closed) leaked into the rendered ePub as if they were
     reader content.
  2. Did not strip YAML frontmatter from each chapter, so `book:`,
     `word_count:`, `pov:` etc. rendered as visible prose at the top
     of every chapter.
  3. Did not normalise chapter headings, so pandoc's chapter-detection
     was unreliable — "chapters were not well marked in the epub" per
     the user.

This module takes the same chapters dir and emits one combined
markdown file with:

  - Only `ch_NN.md` files included (`iter_chapter_files()` already
    excludes `ch_NN.summary.md` and other adjuncts).
  - YAML frontmatter stripped from each chapter (shared helper).
  - A canonical `# Chapter N: Title` (or `# Chapter N` when the
    chapter file has no `# …` heading) at the top of each chapter,
    so pandoc reliably sees a top-level division per chapter.
  - Chapter bodies separated by blank lines (no extra delimiter
    needed — pandoc treats every `# …` line as a top-level division).

Pandoc invocation paired with this output: pass the combined file
plus `--top-level-division=chapter --toc` and the resulting ePub
has a clean per-chapter spine with proper TOC entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .frontmatter import strip_yaml_frontmatter
from .latex import frontmatter_value


@dataclass
class CombinedChapter:
    chapter: int
    title: str
    word_count: int


def build_epub_md(
    chapters_dir: Path,
    *,
    output: Path | None = None,
    art_dir: Path | None = None,
    plates_manifest: Path | None = None,
    chapter_titles: bool = True,
) -> tuple[str, list[CombinedChapter]]:
    """Concatenate `ch_NN.md` files into one ePub-ready markdown blob.

    Returns the combined text and a per-chapter report. Writing to
    disk is optional — if `output` is given the text is also written.

    Excludes `ch_NN.summary.md` and any adjunct files via the shared
    `iter_chapter_files()` filter.

    Image inclusion (the user-2026-04-30 ePub-images bug):

      - **Per-chapter ornaments** — `art_dir` (defaults to
        `chapters_dir.parent / "art"`) is searched for
        `ornament_chNN.png`; when found, a markdown `<img>` tag
        renders the ornament at the chapter opening.
      - **User-imported plates** — `plates_manifest` (defaults to
        `chapters_dir.parent / "typeset" / "plates.yaml"`) is read
        for plate entries (the same manifest `mechanical/latex.py`
        uses for the PDF). Plates with `placement: before-chapter`
        render BEFORE the chapter heading; `chapter-start` renders
        between heading and prose; `after-chapter` renders after
        the chapter prose. Each plate emits a centered figure with
        caption + attribution, matching the LaTeX layout. User
        2026-04-30 had 3 imported plates that appeared in the PDF
        but were missing from the ePub — root cause was that
        build_epub_md never read the plates manifest.

    Both image inclusions are best-effort: missing files / missing
    manifest / malformed YAML all degrade silently to "no image
    here" rather than failing the build.
    """
    from ..paths import iter_chapter_files
    chapter_files = iter_chapter_files(chapters_dir)
    if not chapter_files:
        raise FileNotFoundError(f"no ch_*.md under {chapters_dir}")
    if art_dir is None:
        art_dir = chapters_dir.parent / "art"
    if plates_manifest is None:
        # Default location matches what `/autonovel:art-import` writes
        # and what build_chapters_tex (LaTeX path) reads. Both paths
        # share the same manifest so a plate appears identically in
        # PDF and ePub.
        default_manifest = chapters_dir.parent / "typeset" / "plates.yaml"
        plates_manifest = default_manifest if default_manifest.is_file() else None
    plates_index = _load_plates_for_epub(plates_manifest, chapters_dir.parent)

    pieces: list[str] = []
    reports: list[CombinedChapter] = []
    for ch_path in chapter_files:
        num_str = ch_path.stem.split("_")[-1]
        try:
            num = int(num_str)
        except ValueError as exc:
            raise ValueError(f"cannot parse chapter number from {ch_path.name!r}") from exc

        raw_text = ch_path.read_text(encoding="utf-8")
        body = strip_yaml_frontmatter(raw_text).strip()

        # Find the chapter's title in priority order: frontmatter
        # `title:` field, then `# Heading` line, then "Chapter N".
        # Pass the raw text (with frontmatter intact) so the
        # extractor can read the YAML — bug 2026-04-30 was that
        # only the body was passed, so frontmatter titles were
        # invisible and the ePub TOC defaulted to "Chapter N".
        if chapter_titles:
            title = _extract_chapter_title(
                body, default=f"Chapter {num}",
                text_with_frontmatter=raw_text,
            )
        else:
            # Numbers-only mode (project.yaml :: typeset.chapter_titles
            # = false). Drop the per-chapter title; render every
            # chapter as `# Chapter N` so pandoc's TOC reads cleanly.
            title = f"Chapter {num}"
        # If body opens with a `# Title` line, drop it — we're going to
        # emit our own canonical header in front of the prose.
        body_without_title = _strip_leading_heading(body)

        canonical_heading = f"# Chapter {num}: {title}" if title and not title.lower().startswith("chapter ") else f"# {title}"
        dateline = frontmatter_value(raw_text, "dateline")
        if dateline:
            canonical_heading += (f'\n\n<p class="dateline">{_html_escape(dateline)}</p>\n')

        # Per-chapter ornament — auto-generated by /autonovel:art-
        # ornaments-all. Renders as a small centered image at chapter
        # opening, parallel to the LaTeX `\includegraphics` in
        # build_chapters_tex. Pandoc embeds the referenced PNG into
        # the ePub bundle automatically when it sees a markdown
        # image. Path is relative to chapters_dir.parent so pandoc
        # resolves it correctly.
        ornament_md = ""
        ornament_png = art_dir / f"ornament_ch{num:02d}.png"
        if ornament_png.is_file():
            try:
                rel = ornament_png.relative_to(chapters_dir.parent)
            except ValueError:
                rel = ornament_png
            ornament_md = _epub_image_block(
                src=str(rel), caption="", attribution="",
                width_pct=60,
            )

        # User-imported plates from plates.yaml — placed before the
        # chapter heading, between heading and prose, or after prose,
        # matching the PDF's behaviour.
        before_md = "".join(
            _epub_image_block(src=p[0], caption=p[1], attribution=p[2],
                              width_pct=100 if p[3] == "landscape" else 80,
                              max_px=1400 if p[3] == "landscape" else 600)
            for p in plates_index.get((num, "before-chapter"), [])
        )
        start_md = "".join(
            _epub_image_block(src=p[0], caption=p[1], attribution=p[2],
                              width_pct=100 if p[3] == "landscape" else 80,
                              max_px=1400 if p[3] == "landscape" else 600)
            for p in plates_index.get((num, "chapter-start"), [])
        )
        after_md = "".join(
            _epub_image_block(src=p[0], caption=p[1], attribution=p[2],
                              width_pct=100 if p[3] == "landscape" else 80,
                              max_px=1400 if p[3] == "landscape" else 600)
            for p in plates_index.get((num, "after-chapter"), [])
        )

        pieces.append(
            f"{before_md}{canonical_heading}\n{ornament_md}{start_md}\n"
            f"{body_without_title}\n{after_md}".rstrip() + "\n"
        )
        reports.append(CombinedChapter(
            chapter=num,
            title=title,
            word_count=len(body_without_title.split()),
        ))

    content = "\n".join(pieces)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    return content, reports


def _extract_chapter_title(body: str, *, default: str,
                            text_with_frontmatter: str | None = None
                            ) -> str:
    """Return the chapter's title in priority order:

      1. YAML frontmatter `title:` field (the explicit slot —
         what `/autonovel:draft` step 11 and
         `/autonovel:extract-chapter-titles` write).
      2. The first non-empty line if it's a markdown `# Heading`
         (legacy convention from before the `title:` field
         existed).
      3. *default* (typically "Chapter N").

    Bug 2026-04-30: the prior implementation skipped step 1
    entirely — only read the markdown heading. Chapters with
    titles in YAML but no prose-level `# Heading` (the new
    canonical shape) defaulted to "Chapter N" → pandoc's ePub
    TOC showed `Chapter 1, Chapter 2, …` instead of the titles.
    Mirrors `mechanical/latex._extract_chapter_title`'s priority
    so PDF and ePub render the same titles.

    `text_with_frontmatter` is the raw chapter file pre-strip
    (build_epub_md passes it explicitly); when None, fall through
    to step 2 immediately.
    """
    # Step 1: YAML frontmatter `title:` field.
    if text_with_frontmatter and text_with_frontmatter.startswith("---"):
        for raw_line in text_with_frontmatter.splitlines()[1:]:
            if raw_line.strip() == "---":
                break
            if raw_line.startswith("title:"):
                value = raw_line.split(":", 1)[1].strip()
                if value.startswith(('"', "'")) and value.endswith(('"', "'")):
                    value = value[1:-1]
                if value:
                    return value
    # Step 2: first non-empty line if `# Heading`.
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("# ").strip()
            # `Chapter N: Real Title` → `Real Title`
            if ": " in heading:
                _, right = heading.split(": ", 1)
                if right.strip():
                    return right.strip()
            # `N. Real Title` → `Real Title`
            if ". " in heading and heading.split(". ", 1)[0].isdigit():
                return heading.split(". ", 1)[1].strip()
            return heading or default
        return default
    return default


def _epub_image_block(*, src: str, caption: str, attribution: str,
                       width_pct: int, max_px: int = 600) -> str:
    """Render one centered image with optional caption + attribution
    as inline HTML — pandoc passes inline HTML through to the ePub
    XHTML untouched. Caption and attribution are italicised and
    sized smaller, matching the LaTeX layout in
    `mechanical/latex.py::_render_plate_block`."""
    parts = [
        f'\n<p style="text-align: center; margin: 1em 0;">',
        f'<img src="{src}" alt="{_html_escape(caption)}" '
        f'style="width: {width_pct}%; max-width: {max_px}px;" />',
    ]
    if caption:
        parts.append(
            f'<br/><em>{_html_escape(caption)}</em>'
        )
    if attribution:
        parts.append(
            f'<br/><small>{_html_escape(attribution)}</small>'
        )
    parts.append("</p>\n\n")
    return "".join(parts)


def _html_escape(text: str) -> str:
    """HTML-escape user-supplied caption/attribution strings."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _load_plates_for_epub(
    manifest: Path | None, book_root: Path,
) -> dict[tuple[int, str], list[tuple[str, str, str, str]]]:
    """Same shape as `mechanical/latex._load_plates_index` but
    returns paths RELATIVE to the chapters_dir parent (so pandoc
    can find them) rather than absolute LaTeX paths.

    The returned dict's keys are `(chapter_number, placement)`;
    values are lists of `(rel_path, caption, attribution, layout)` tuples.
    """
    out: dict[tuple[int, str], list[tuple[str, str, str]]] = {}
    if manifest is None or not manifest.is_file():
        return out
    try:
        import yaml as _yaml
        data = _yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return out
    plates = data.get("plates") or []
    if not isinstance(plates, list):
        return out
    base = manifest.parent
    for entry in plates:
        if not isinstance(entry, dict):
            continue
        try:
            chapter = int(entry["chapter"])
            file_rel = str(entry["file"])
        except (KeyError, ValueError, TypeError):
            continue
        placement = str(entry.get("placement", "before-chapter"))
        caption = str(entry.get("caption", "") or "")
        attribution = str(entry.get("attribution", "") or "")
        file_abs = (base / file_rel).resolve()
        # Compute path relative to book_root so pandoc (which
        # resolves image paths relative to the input markdown
        # file's directory — i.e. the typeset/ dir or wherever
        # chapters_combined.md lives) can find it.
        try:
            rel = file_abs.relative_to(book_root)
        except ValueError:
            rel = file_abs
        layout = str(entry.get("layout", "portrait") or "portrait").strip().lower()
        out.setdefault((chapter, placement), []).append(
            (str(rel), caption, attribution, layout)
        )
    return out


def _strip_leading_heading(body: str) -> str:
    """If *body* opens with a `# …` line, drop that line plus any
    immediately-following blank line. Used because we emit our own
    canonical heading and don't want it to appear twice.
    """
    lines = body.splitlines()
    if not lines:
        return body
    first = lines[0].strip()
    if not first.startswith("#"):
        return body
    out = lines[1:]
    while out and out[0].strip() == "":
        out.pop(0)
    return "\n".join(out)
