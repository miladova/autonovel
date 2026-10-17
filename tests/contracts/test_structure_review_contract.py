"""Tier-2 contract: the book-level structure tier.

`/autonovel:structure-review` (an LLM prompt) writes
`edit_logs/structure_review.json`; `autonovel mechanical
structure-validate` (Python) checks it; `/autonovel:review`,
`/autonovel:brief`, `/autonovel:revise`, `/autonovel:revision-pass` and
`/autonovel:next` consume it. Producer and consumers must agree on the
vocabulary, and the anti-sycophancy wording is load-bearing — the
kingmaker miss (4★ for ten passes on a book the author read as "a bunch
of short anecdotes") is what it exists to prevent. If you reword any of
this deliberately, update the test deliberately.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from autonovel.mechanical import structure_review as sr

_COMMANDS = Path(__file__).resolve().parent.parent.parent / "commands"


def _body(stem: str) -> str:
    return (_COMMANDS / f"{stem}.md").read_text(encoding="utf-8")


def _section(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    assert m, f"<{tag}> block missing"
    return m.group(1)


# ------------------------------------------------- producer ↔ validator vocab


def test_failure_mode_ids_match_validator() -> None:
    block = _section(_body("structure-review"), "failure-modes")
    named = set(re.findall(r"^- `([a-z-]+)`", block, re.MULTILINE))
    assert named == set(sr.FAILURE_MODES)


def test_candidate_kinds_named_in_prompt_are_valid() -> None:
    body = _body("structure-review")
    step = body.split("13. **Structural brief candidates**", 1)[1].split("14. **", 1)[0]
    kinds = set(re.findall(r"`([a-z]+(?:-[a-z]+)*)`", step))
    for k in sr.CANDIDATE_KINDS:
        assert k in kinds, f"candidate kind `{k}` not explained in structure-review step 13"
    for kind, prefix in sr.COMMAND_PREFIX.items():
        assert prefix in step, f"`{kind}` command prefix {prefix} not given in step 13"


@pytest.mark.parametrize("values", [
    sr.LINK_KINDS, sr.REMOVABILITY_VERDICTS, sr.ESCALATION_VS_PREVIOUS,
    sr.ENDING_ANSWERS, sr.CLIMAX_VERDICTS, sr.EPISODIC_RISK, sr.THREAD_ENDINGS,
])
def test_validator_enums_appear_in_prompt(values: tuple[str, ...]) -> None:
    body = _body("structure-review")
    for v in values:
        assert f"`{v}`" in body, f"enum value `{v}` never named in structure-review.md"


def test_prompt_caps_match_validator_thresholds() -> None:
    scoring = _section(_body("structure-review"), "scoring")
    for fragment in ("any removable chapter → ≤ 3", "≥ 25% of the book → ≤ 2",
                     "< 0.80 → ≤ 4", "< 0.65 → ≤ 3", "< 0.50 → ≤ 2",
                     "`partly` → ≤ 3", "`no` → ≤ 2", "after 25% → ≤ 3",
                     "after 50%, or never → ≤ 2", "`finishes` → ≤ 3",
                     "`medium` → ≤ 3", "`high` → ≤ 2", "`anecdote-chain` named → ≤ 2"):
        assert fragment in scoring, fragment
    assert sr.GATE_MIN_SCORE == 4


# --------------------------------------------------------- anti-sycophancy


def test_structure_review_ground_rules_are_present() -> None:
    body = _body("structure-review")
    rules = _section(body, "ground-rules")
    assert "Strong prose is not evidence of structure" in rules
    assert "concrete plot fact" in rules
    assert "History is not causation" in rules
    assert "Do not hedge a structural defect" in rules
    for hedge in ("cost of", "individually fine", "largely successful"):
        assert hedge in rules
    assert "Do not read the other reviewers first" in rules
    # The kingmaker symptom is a named failure mode.
    assert "kingmaker" in _section(body, "failure-modes")
    assert "autonovel mechanical structure-validate books/{book}" in body
    assert "autonovel mechanical structure-dossier books/{book}" in body


def test_review_stop_rule_is_gated_on_structure() -> None:
    body = _body("review")
    assert "autonovel mechanical structure-validate" in body
    assert "gate.passes" in body
    assert "run\n     /autonovel:structure-review first" in body or \
        "/autonovel:structure-review --book {book} first" in body
    assert "always `qualified:\n     false`" in body or "always `qualified: false`" in body


def test_reader_panel_asks_book_level_questions() -> None:
    body = _body("reader-panel")
    for key in ("book_in_one_sentence", "felt_like_episodes", "chapter_to_cut",
                "pulled_vs_informed", "book_level"):
        assert f"`{key}`" in body
    assert "fourteen questions" in body


# ------------------------------------------------------ structural briefs


def test_brief_writes_structural_kind_marker() -> None:
    body = _body("brief")
    assert "kind: structural" in body and "kind: prose" in body
    assert "## Structural brief" in body
    assert "## Cross-chapter operations — run these yourself" in body
    assert "--from structure" in body or "`structure`" in body


def test_revise_acts_on_structural_brief_without_touching_neighbours() -> None:
    body = _body("revise")
    assert "kind: structural" in body
    assert "Never touch another chapter." in body
    for cmd in ("/autonovel:merge-chapters", "/autonovel:remove-chapter",
                "/autonovel:reorder", "/autonovel:split-chapter"):
        assert cmd in body


def test_revision_pass_resolves_structural_range() -> None:
    body = _body("revision-pass")
    assert "`structural`" in body
    assert "structure-validate" in body
    assert "/autonovel:structure-review --book {book}" in body


# ------------------------------------------------------- outline + drafting


def test_gen_outline_requires_parseable_spine_sections() -> None:
    body = _body("gen-outline")
    for heading in ("## Spine", "## Stakes ladder", "## Causal spine"):
        assert heading in body
    assert "--add-spine" in body
    assert "- 2 because 1:" in body


def test_draft_and_draft_pass_hold_to_the_causal_spine() -> None:
    draft = _body("draft")
    assert "## Causal spine" in draft and "--add-spine" in draft
    dp = _body("draft-pass")
    assert "SPINE CHECK" in dp and "no-spine" in dp
    assert "/autonovel:structure-review --book {book}" in dp


def test_evaluate_full_caps_aggregate_by_structure() -> None:
    body = _body("evaluate")
    assert "structure_subscore + 1.0" in body
    for dim in ("causal_chain", "through_line", "escalation", "removability",
                "climax_convergence", "causal_spine"):
        assert f"`{dim}`" in body
