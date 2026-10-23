"""Onboarding wizard — `autonovel onboard <book>`.

Surfaced 2026-04-30 by author testing: the new-series + new-book
flow drops the user into a series root with a stub seed.txt, no
title, no author, and no signal of which file to fill in next.
The wizard collapses that into one prompt-driven session that
produces a structured seed.txt + populated project.yaml fields,
and prints a clear "next: open Claude Code and run /autonovel:next"
guidance.

Architecture: pure-Python prompts (no LLM). The wizard does NOT
generate working titles itself — that's the runtime's
`/autonovel:title` job. Instead, the wizard captures the user's
inputs into a structured shape that `/autonovel:title` can read
without re-asking, and prints the next-step command.

Public API:

    Wizard(series, book_name).run(*, prompt_fn=input,
                                    print_fn=print) -> WizardResult

    write_seed(book_root, answers) -> Path
    apply_to_project_yaml(project_path, book_name, answers) -> None
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import project as project_mod
from .paths import SeriesLayout


@dataclass
class WizardAnswers:
    """Structured capture of the user's onboarding inputs. Each
    field is optional — the wizard skips missing values rather
    than blocking, and prints a final `## Onboarding TODO` block
    listing what's still empty."""
    pitch: str = ""                 # one-paragraph book pitch
    period_start: str = ""          # year, e.g. "1480"
    period_end: str = ""            # year, e.g. "1550"
    period_region: str = ""         # e.g. "Venice"
    genre: str = ""                 # e.g. "historical fiction"
    subgenres: list[str] = field(default_factory=list)  # registry ids or "other: …"
    working_title: str = ""         # user-typed working title; empty → defer to /autonovel:title
    human_author: str = ""          # the writer's name
    attribution_style: str = "seed-by-human"  # see ATTRIBUTION_STYLES below
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pitch": self.pitch,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "period_region": self.period_region,
            "genre": self.genre,
            "subgenres": list(self.subgenres),
            "working_title": self.working_title,
            "human_author": self.human_author,
            "attribution_style": self.attribution_style,
            "skipped": list(self.skipped),
        }


# Attribution rendering rules — mapped to the string written to
# `BookEntry.author`. Keep the autonovel side of the credit
# explicit and honest by default; the human can override in
# project.yaml after the wizard finishes.
ATTRIBUTION_STYLES: dict[str, str] = {
    "seed-by-human": "Seed by {human}; drafted with Autonovel",
    "human-only": "{human}",
    "ai-only": "Autonovel",
    "co-author": "{human} with Autonovel",
}


def render_attribution(style: str, human: str) -> str:
    """Build the `BookEntry.author` string from the wizard's
    answers. The human's name slots into the template; an empty
    human fallback to the literal placeholder so the user sees
    something to fix."""
    template = ATTRIBUTION_STYLES.get(style, ATTRIBUTION_STYLES["seed-by-human"])
    return template.format(human=human or "<your name>")


# ----------------------------------------------------- prompts


@dataclass
class WizardResult:
    answers: WizardAnswers
    seed_path: Path
    project_yaml_updated: bool
    next_steps: list[str]

    def to_dict(self) -> dict:
        return {
            "answers": self.answers.to_dict(),
            "seed_path": str(self.seed_path),
            "project_yaml_updated": self.project_yaml_updated,
            "next_steps": list(self.next_steps),
        }


def _ask(prompt_fn, label: str, *,
          help_text: str = "",
          default: str = "",
          allow_skip: bool = True) -> str:
    """Single prompt with `(skip — fill later)` always available
    as `<empty input>` (the user just hits return).

    Returns `""` when the user skipped; non-empty when they
    answered."""
    parts = [f"\n{label}"]
    if help_text:
        parts.append(f"  ({help_text})")
    if default:
        parts.append(f"  [default: {default}]")
    if allow_skip:
        parts.append("  Press return to skip.")
    parts.append("> ")
    raw = prompt_fn("\n".join(parts))
    answer = (raw or "").strip()
    if not answer and default:
        return default
    return answer


def run_wizard(series: SeriesLayout, book_name: str, *,
                prompt_fn=input, print_fn=print) -> WizardResult:
    """Run the interactive wizard. The two function seams
    (`prompt_fn` / `print_fn`) let tests inject scripted answers
    instead of real stdin / stdout."""
    book_root = series.books / book_name
    if not book_root.is_dir():
        raise FileNotFoundError(
            f"book {book_name!r} doesn't exist under {series.books}. "
            f"Run `autonovel new-book {book_name}` first."
        )

    print_fn(
        "\n=========================================================\n"
        f"  Onboarding `{book_name}` in series `{series.root.name}`\n"
        "=========================================================\n"
        "  This wizard captures the load-bearing inputs autonovel needs\n"
        "  to start drafting: a pitch, a period, a working title, and an\n"
        "  author credit. Every prompt has a (skip) option — you can\n"
        "  fill anything in later by editing seed.txt or running the\n"
        "  matching /autonovel:* command in Claude Code.\n"
    )

    answers = WizardAnswers()

    # Pitch — one paragraph; the most load-bearing input.
    answers.pitch = _ask(
        prompt_fn,
        "📖 One-paragraph pitch:",
        help_text=(
            "Period, protagonist, central conflict, tone in 60-180 words. "
            "Concrete > abstract. Example: 'In 1492 Venice, an apothecary's "
            "apprentice discovers his late master forged a guild seal — and "
            "must decide whether to publish the truth, knowing it'll burn "
            "his future. A slow-burn historical mystery in a register that "
            "echoes Eco and Mantel.'"
        ),
    )
    if not answers.pitch:
        answers.skipped.append("pitch")

    # Period (historical fiction signal).
    print_fn("\n📅 Period:")
    answers.period_start = _ask(
        prompt_fn, "  Start year:", help_text="e.g. 1480 — leave empty for contemporary fiction",
    )
    if answers.period_start:
        answers.period_end = _ask(
            prompt_fn, "  End year:", help_text="e.g. 1550",
        )
        answers.period_region = _ask(
            prompt_fn, "  Region:", help_text="e.g. Venice / Italy / Mediterranean",
        )
    else:
        answers.skipped.append("period")

    # Genre.
    answers.genre = _ask(
        prompt_fn, "🎭 Genre:",
        help_text="e.g. historical fiction, sci-fi, literary, mystery — or any combination",
        default="literary",
    )
    # Subgenres, when the genre is in the registry and has them: each
    # genre's guide says what its reader comes for (`genres.py`).
    from . import genres as genres_mod
    g = genres_mod.find(answers.genre)
    if g is not None and g.subgenres:
        menu = "; ".join(f"{x.id} ({x.name})" for x in g.subgenres)
        raw = _ask(
            prompt_fn, "🎭 Subgenre(s):",
            help_text=(f"comma-separated, a book can be two. {g.name}: {menu}. "
                       f"Anything else as 'other: <words>'"),
        )
        for part in [x.strip() for x in raw.split(",") if x.strip()]:
            sg = None if part.lower().startswith("other:") else g.subgenre(part)
            answers.subgenres.append(sg.id if sg else
                                     (part if part.lower().startswith("other:")
                                      else f"other: {part}"))

    # Working title.
    answers.working_title = _ask(
        prompt_fn, "📚 Working title:",
        help_text=(
            "Optional — leave empty and `/autonovel:title --book "
            + book_name + "` will propose 5 candidates from your pitch later. "
            "Adds `(working)` suffix automatically so the title page never reads 'Untitled'."
        ),
    )
    if not answers.working_title:
        answers.skipped.append("working_title")

    # Author.
    answers.human_author = _ask(
        prompt_fn, "✍️  Your name (the human author):",
        help_text="Used in the title page + ePub metadata. Pen name is fine.",
    )
    if not answers.human_author:
        answers.skipped.append("human_author")

    # Attribution style.
    print_fn(
        "\n📝 Author credit style:\n"
        "  How autonovel should render the author line on the title page.\n"
        "  Options:\n"
        "    1. seed-by-human (default) — 'Seed by <you>; drafted with Autonovel.' "
        "Honest about AI involvement, credits the human seed.\n"
        "    2. human-only — '<you>'. Right when YOU substantially edit / rewrite drafts.\n"
        "    3. ai-only — 'Autonovel'. Honest for unedited drafts.\n"
        "    4. co-author — '<you> with Autonovel'. Symmetric credit."
    )
    style_input = _ask(
        prompt_fn, "  Pick 1-4 (or press return for default):",
        default="1",
    )
    style_map = {
        "1": "seed-by-human", "2": "human-only",
        "3": "ai-only", "4": "co-author",
    }
    answers.attribution_style = style_map.get(
        style_input.strip(), "seed-by-human"
    )

    # Write outputs.
    seed_path = write_seed(book_root, answers)
    project_yaml_updated = apply_to_project_yaml(
        series.project_file, book_name, answers,
    )

    # Build next-step guidance.
    next_steps: list[str] = []
    if "pitch" in answers.skipped:
        next_steps.append(
            f"⚠️  Pitch is empty. Open `{seed_path.relative_to(series.root)}` "
            f"and replace the [pitch placeholder] before running gen-world."
        )
    if "working_title" in answers.skipped:
        next_steps.append(
            f"In Claude Code: `/autonovel:title --book {book_name}` to get "
            f"5 LLM-suggested candidates. Pick one with `--pick N`."
        )
    if "period" in answers.skipped:
        next_steps.append(
            "Contemporary or genre fiction — no period set. Skip "
            "/autonovel:research and /autonovel:glossary unless your "
            "world has invented vocabulary the reader needs."
        )
    else:
        next_steps.append(
            f"Period set ({answers.period_start}-{answers.period_end} "
            f"{answers.period_region}). After foundation, run "
            f"`/autonovel:research --from-seed --book {book_name}` "
            f"to seed shared/research/notes/, then "
            f"`/autonovel:glossary --book {book_name}` once 3+ chapters "
            f"are drafted."
        )
    next_steps.append(
        f"Now open Claude Code in this folder and run "
        f"`/autonovel:next` — it'll walk you through the rest of "
        f"the foundation (gen-world, gen-characters, voice-discovery, "
        f"gen-canon, gen-outline) in the right order."
    )

    print_fn("\n" + "=" * 57)
    print_fn(f"✅ Onboarding complete for `{book_name}`.")
    print_fn(f"   Seed:     {seed_path.relative_to(series.root)}")
    print_fn(f"   Title:    {answers.working_title or '<deferred to /autonovel:title>'}")
    print_fn(f"   Author:   {render_attribution(answers.attribution_style, answers.human_author)}")
    print_fn("=" * 57)
    print_fn("\nNext steps:\n")
    for i, step in enumerate(next_steps, 1):
        print_fn(f"  {i}. {step}\n")

    return WizardResult(
        answers=answers,
        seed_path=seed_path,
        project_yaml_updated=project_yaml_updated,
        next_steps=next_steps,
    )


# ----------------------------------------------------- writers


def write_seed(book_root: Path, answers: WizardAnswers) -> Path:
    """Write a structured seed.txt with the wizard's answers + a
    HOW-TO-EDIT block. Section headings let the user (and the
    runtime) find each input quickly. Skipped sections render as
    `[<placeholder>]` so /autonovel:next can flag them as TODO."""
    seed_path = book_root / "seed.txt"
    parts: list[str] = []
    parts.append("# Seed")
    parts.append("")
    parts.append("<!--")
    parts.append("HOW TO EDIT THIS FILE")
    parts.append("=====================")
    parts.append("Each `## <Section>` block below is a load-bearing input.")
    parts.append("- `## Pitch` is read by gen-world / gen-characters / gen-outline.")
    parts.append("- `## Period` is read by /autonovel:research --from-seed.")
    parts.append("- `## Genre` is read by /autonovel:title proposals.")
    parts.append("- `## Working title` is read by /autonovel:title (defers to it when empty).")
    parts.append("Sections marked `[<placeholder>]` are still empty —")
    parts.append("`/autonovel:next` will keep flagging them until filled.")
    parts.append("-->")
    parts.append("")

    parts.append("## Pitch")
    parts.append("")
    parts.append(answers.pitch or "[Replace this with your one-paragraph pitch — period, protagonist, central conflict, tone. 60-180 words.]")
    parts.append("")

    parts.append("## Period")
    parts.append("")
    if answers.period_start:
        parts.append(f"- start: {answers.period_start}")
        parts.append(f"- end:   {answers.period_end}")
        parts.append(f"- region: {answers.period_region}")
    else:
        parts.append("[Contemporary or genre fiction — no period set. Delete this section if you don't need it.]")
    parts.append("")

    parts.append("## Genre")
    parts.append("")
    parts.append(answers.genre or "[Replace with: historical fiction / sci-fi / literary / mystery / etc.]")
    if answers.subgenres:
        parts.append(f"Subgenres: {', '.join(answers.subgenres)}")
    parts.append("")

    parts.append("## Working title")
    parts.append("")
    if answers.working_title:
        parts.append(f"{answers.working_title} (working)")
    else:
        parts.append("[Run `/autonovel:title --book <name>` in Claude Code to get 5 candidates and pick one.]")
    parts.append("")

    parts.append("## Author")
    parts.append("")
    parts.append(f"- human: {answers.human_author or '[your name]'}")
    parts.append(f"- attribution_style: {answers.attribution_style}")
    parts.append(f"- rendered: {render_attribution(answers.attribution_style, answers.human_author)}")
    parts.append("")

    if answers.skipped:
        parts.append("## Onboarding TODO")
        parts.append("")
        parts.append(
            "These inputs were skipped during onboarding. Fill them in "
            "by editing the sections above, OR by running the matching "
            "command in Claude Code (see `/autonovel:next` for the "
            "current state-aware action list)."
        )
        parts.append("")
        for s in answers.skipped:
            parts.append(f"- [ ] {s}")
        parts.append("")

    seed_path.write_text("\n".join(parts), encoding="utf-8")
    return seed_path


def apply_to_project_yaml(project_path: Path, book_name: str,
                            answers: WizardAnswers) -> bool:
    """Update project.yaml with the wizard's structured outputs.
    Returns True when changes were written; False when no fields
    needed updating."""
    cfg = project_mod.load(project_path)
    entry = cfg.book_by_name(book_name)
    if entry is None:
        # Defensive — wizard caller should have created the book.
        return False

    changed = False
    # Title is the one field the wizard preserves rather than
    # overwrites — the canonical title-setting tool is
    # /autonovel:title (with proposals + --pick), and a previous
    # title value is likely the user's intentional pick. Wizard
    # answer fills in only when title is empty.
    if answers.working_title and not entry.title:
        entry.title = f"{answers.working_title} (working)"
        changed = True
    # Author / period / genre — the wizard is the canonical
    # interactive input source for these. The user explicitly
    # hits return (empty answer) when they want to preserve.
    # Anything they typed wins.
    if answers.human_author:
        rendered = render_attribution(answers.attribution_style, answers.human_author)
        if entry.author != rendered:
            entry.author = rendered
            changed = True
    if answers.period_start:
        new_period = {
            "start": answers.period_start,
            "end": answers.period_end,
            "region": answers.period_region,
        }
        if cfg.period != new_period:
            cfg.period = new_period
            changed = True
    if answers.genre and answers.genre != cfg.genre:
        cfg.genre = answers.genre
        changed = True
    if answers.subgenres and entry.subgenres != answers.subgenres:
        entry.subgenres = list(answers.subgenres)
        changed = True

    if changed:
        project_mod.dump(cfg, project_path)
    return changed
