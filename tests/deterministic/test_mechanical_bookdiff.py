"""Tier-1 tests for `autonovel.mechanical.bookdiff` (`mechanical diff-chapters`).

The reader-facing diff between two versions of a book: paragraph
alignment, word-level inline markup, similar-paragraph pairing,
added/removed chapters, filename sanitising, the HTML page (hunk list,
counter, self-contained), why annotations, the last-read bookmark, and
checkpoint mode.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from autonovel import checkpoints
from autonovel.mechanical import bookdiff
from autonovel.mechanical.bookdiff import (
    DiffError,
    apply_why,
    build_diff,
    diff_file,
    load_why,
    pair_paragraphs,
    read_bookmark,
    render_html,
    resolve_snapshot,
    sanitize_ref,
    split_paragraphs,
    tokenize,
    word_diff,
    write_bookmark,
)


FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "tiny-series-historical"
BOOK = "tiny-inquisitor"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_NOSYSTEM": "1",
}

P1 = "Jakob crossed the lagoon at dawn, counting his ducats by feel."
P2 = "The boatman watched him and reached the wrong conclusion about the knife."
P3 = '"You\'ll lose that at the gate," he said.'
P4 = "A long unchanged paragraph about the Fondaco and the Germans who lived in it."
P5 = ("The clerk wrote everything down slowly, without once looking up, and the "
      "porters stood behind him with their staves.")


def _chapter(n: int, paras: list[str], *, title: str = "The Gate",
             word_count: int = 100) -> str:
    return (f"---\nbook: {BOOK}\nchapter: {n}\ntitle: {title}\n"
            f"word_count: {word_count}\n---\n\n" + "\n\n".join(paras) + "\n")


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=root,
                          env=GIT_ENV, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def _commit(root: Path, msg: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)
    return _git(root, "rev-parse", "HEAD")


def _series(tmp_path: Path, *, git: bool = True) -> Path:
    root = tmp_path / "series"
    shutil.copytree(FIXTURE, root)
    if git:
        _git(root, "init", "-q")
    return root


def _chapters_dir(root: Path) -> Path:
    d = root / "books" / BOOK / "chapters"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(root: Path, n: int, paras: list[str], **kw) -> Path:
    p = _chapters_dir(root) / f"ch_{n:02d}.md"
    p.write_text(_chapter(n, paras, **kw), encoding="utf-8")
    return p


# ------------------------------------------------------------ text model


def test_split_paragraphs_normalises_whitespace_and_soft_wraps() -> None:
    text = "One  two\nthree.\n\n\n  Four   five. \n\n- item a\n- item b\n  continued\n"
    assert split_paragraphs(text) == [
        "One two three.",
        "Four five.",
        "- item a\n- item b continued",
    ]


def test_tokenize_keeps_punctuation_attached() -> None:
    assert tokenize('"Arma," the clerk said.') == ['"Arma,"', "the", "clerk", "said."]


# ------------------------------------------------------- paragraph alignment


def test_unchanged_file_has_no_hunks() -> None:
    text = _chapter(1, [P1, P2, P3])
    fd = diff_file(text, text, key="ch01", file="ch_01.md", kind="chapter",
                   label="Chapter 1", chapter=1)
    assert fd.status == "unchanged"
    assert fd.hunks == []
    assert fd.words_added == fd.words_removed == 0


def test_paragraph_alignment_isolates_the_changed_paragraph() -> None:
    old = _chapter(1, [P1, P2, P3, P4, P5])
    new = _chapter(1, [P1, P2, P3.replace("gate", "water-gate"), P4, P5])
    fd = diff_file(old, new, key="ch01", file="ch_01.md", kind="chapter",
                   label="Chapter 1", chapter=1)
    assert len(fd.hunks) == 1
    h = fd.hunks[0]
    assert h.index == 2 and h.old_index == 2
    assert h.old_paragraphs == [P3]
    assert h.context_before == P2
    assert h.context_after == P4
    kinds = [k for k, _ in fd.flow]
    assert kinds == ["equal", "hunk", "equal"]


# ------------------------------------------------------- word-level markup


def test_one_word_insert_is_one_inline_change() -> None:
    old = _chapter(1, [P1, P2])
    new = _chapter(1, [P1.replace("his ducats", "his eleven ducats"), P2])
    fd = diff_file(old, new, key="ch01", file="ch_01.md", kind="chapter",
                   label="Chapter 1", chapter=1)
    (h,) = fd.hunks
    assert "<ins>eleven</ins>" in h.inline_html
    assert "<del>" not in h.inline_html
    assert 'class="p-chg"' in h.inline_html          # edited, not replaced
    assert "counting his <ins>eleven</ins> ducats" in h.inline_html
    assert (h.words_added, h.words_removed) == (1, 0)


def test_one_word_replacement_pairs_the_paragraphs() -> None:
    old_p = "Jüterbog lay on the Archbishop's side of the Brandenburg border, and lived on cattle."
    new_p = old_p.replace("Brandenburg", "Saxon")
    fd = diff_file(_chapter(1, [old_p]), _chapter(1, [new_p]), key="ch01",
                   file="ch_01.md", kind="chapter", label="Chapter 1", chapter=1)
    (h,) = fd.hunks
    assert "<del>Brandenburg</del> <ins>Saxon</ins>" in h.inline_html
    assert 'class="p-del' not in h.inline_html
    assert 'class="p-ins' not in h.inline_html
    assert (h.words_added, h.words_removed) == (1, 1)


def test_unrelated_paragraphs_are_not_paired() -> None:
    old_p = "The bells started at ten, every bell in the town at once, and the market filled."
    new_p = "Sibylla's calendar hung by the kitchen stair with the fast days marked in red ink."
    fd = diff_file(_chapter(1, [P1, old_p, P2]), _chapter(1, [P1, new_p, P2]),
                   key="ch01", file="ch_01.md", kind="chapter", label="Chapter 1", chapter=1)
    (h,) = fd.hunks
    assert 'class="p-del"' in h.inline_html
    assert 'class="p-ins"' in h.inline_html
    assert 'class="p-chg"' not in h.inline_html


def test_semantic_cleanup_folds_coincidental_equalities() -> None:
    old = tokenize("the most dangerous thing he ever signed.")
    new = tokenize("the boldest line he ever wrote.")
    segs = word_diff(old, new)
    # "he ever" is a two-word coincidence between two rewrites: folded.
    assert [s.tag for s in segs] == ["eq", "chg"]
    assert segs[1].old == ["most", "dangerous", "thing", "he", "ever", "signed."]


def test_split_paragraph_shows_inserted_pilcrow() -> None:
    old = _chapter(1, [P1, P5])
    a, b = P5.split(", and the ")
    new = _chapter(1, [P1, a + ".", "The " + b])
    fd = diff_file(old, new, key="ch01", file="ch_01.md", kind="chapter",
                   label="Chapter 1", chapter=1)
    (h,) = fd.hunks
    assert 'class="pilcrow"' in h.inline_html and "<ins" in h.inline_html
    # Rendered as two paragraphs, not a 20-word delete + insert.
    assert h.inline_html.count("<p ") == 2
    assert h.words_removed <= 3


def test_merged_paragraphs_show_deleted_pilcrow() -> None:
    fd = diff_file(_chapter(1, [P1, P2]), _chapter(1, [P1 + " " + P2]),
                   key="ch01", file="ch_01.md", kind="chapter", label="Chapter 1", chapter=1)
    (h,) = fd.hunks
    assert '<del class="pilcrow"' in h.inline_html
    assert h.inline_html.count("<p ") == 1
    assert (h.words_added, h.words_removed) == (0, 0)


def test_moved_paragraph_is_tagged_and_not_counted_as_words() -> None:
    fd = diff_file(_chapter(1, [P1, P2, P3, P4, P5]), _chapter(1, [P1, P2, P4, P5, P3]),
                   key="ch01", file="ch_01.md", kind="chapter", label="Chapter 1", chapter=1)
    html = "\n".join(h.inline_html for h in fd.hunks)
    assert "moved from here" in html and "moved here" in html
    assert sum(h.moved for h in fd.hunks) == 2
    assert fd.words_added == fd.words_removed == 0


def test_pair_paragraphs_prefers_one_to_one_then_dels_before_ins() -> None:
    old = [tokenize(P1), tokenize(P2)]
    new = [tokenize(P1.replace("dawn", "first light")), tokenize(P4)]
    items = pair_paragraphs(old, new)
    assert items[0] == ("pair", [0], [0])
    assert [k for k, _, _ in items[1:]] == ["del", "ins"]


def test_frontmatter_title_change_listed_and_word_count_ignored() -> None:
    old = _chapter(1, [P1], title="The Gate", word_count=10)
    new = _chapter(1, [P1], title="Weapons at the Gate", word_count=11)
    fd = diff_file(old, new, key="ch01", file="ch_01.md", kind="chapter",
                   label="Chapter 1", chapter=1)
    assert fd.frontmatter_changes == {"title": ["The Gate", "Weapons at the Gate"]}
    assert fd.status == "changed"
    assert fd.title == "Weapons at the Gate"


# ------------------------------------------------------------ git versions


@pytest.fixture
def tagged_series(tmp_path: Path) -> Path:
    """ch1 + ch3 committed and tagged draft_1; worktree then edits ch1,
    adds ch2, removes ch3, and edits ch1's summary and voice.md."""
    root = _series(tmp_path)
    _write(root, 1, [P1, P2, P3, P4, P5])
    (_chapters_dir(root) / "ch_01.summary.md").write_text("**Plot:** Jakob arrives.\n")
    _write(root, 3, ["A chapter that will be cut.", "Its second paragraph."], title="Cut")
    _commit(root, "draft")
    _git(root, "tag", "draft_1")
    _write(root, 1, [P1.replace("his ducats", "his eleven ducats"), P2, P3, P4, P5])
    _write(root, 2, ["A brand new chapter about the mint."], title="New")
    (_chapters_dir(root) / "ch_03.md").unlink()
    (_chapters_dir(root) / "ch_01.summary.md").write_text("**Plot:** Jakob arrives in Venice.\n")
    voice = root / "books" / BOOK / "voice.md"
    voice.write_text(voice.read_text(encoding="utf-8") + "\nNew register rule.\n",
                     encoding="utf-8")
    return root


def test_added_and_removed_chapters(tagged_series: Path) -> None:
    rep = build_diff(tagged_series, BOOK)          # last-tag -> worktree
    by_ch = {f.chapter: f for f in rep.chapters}
    assert by_ch[1].status == "changed"
    assert by_ch[2].status == "added"
    assert by_ch[3].status == "removed"
    assert by_ch[2].words_added == 7 and by_ch[2].words_old == 0
    assert by_ch[3].words_removed == 9 and by_ch[3].words_new == 0
    assert 'class="p-ins"' in by_ch[2].hunks[0].inline_html
    assert 'class="p-del"' in by_ch[3].hunks[0].inline_html
    t = rep.totals()
    assert t["chapters_changed"] == 3
    assert t["net_words"] == 1 + 7 - 9
    assert rep.old.label == "draft_1" and rep.new.label == "worktree"


def test_summaries_and_foundation_in_their_own_section(tagged_series: Path) -> None:
    rep = build_diff(tagged_series, BOOK)
    keys = [f.key for f in rep.foundation]
    assert "voice" in keys and "ch01-summary" in keys
    # Hunks are numbered chapters first, then foundation.
    ns = [h.n for h in rep.all_hunks]
    assert ns == list(range(1, len(ns) + 1))
    assert rep.all_hunks[-1].kind in ("summary", "foundation")


def test_chapters_filter_drops_foundation_by_default(tagged_series: Path) -> None:
    rep = build_diff(tagged_series, BOOK, chapters={1})
    assert [f.chapter for f in rep.chapters] == [1]
    assert rep.foundation == []   # summaries are pipeline notes; they follow --foundation
    rep2 = build_diff(tagged_series, BOOK, chapters={1}, foundation=True)
    assert "voice" in [f.key for f in rep2.foundation]
    assert "ch01-summary" in [f.key for f in rep2.foundation]


def test_git_ref_to_git_ref(tagged_series: Path) -> None:
    head2 = _commit(tagged_series, "revise")
    rep = build_diff(tagged_series, BOOK, from_spec="draft_1", to_spec=head2)
    assert rep.new.sha == head2
    assert {f.chapter: f.status for f in rep.chapters} == {1: "changed", 2: "added", 3: "removed"}


def test_last_tag_skips_the_tag_on_the_to_commit(tagged_series: Path) -> None:
    _commit(tagged_series, "revise")
    _git(tagged_series, "tag", "draft_2")
    rep = build_diff(tagged_series, BOOK, from_spec="last-tag", to_spec="draft_2")
    assert rep.old.label == "draft_1"
    assert rep.totals()["chapters_changed"] == 3


def test_series_in_a_subdirectory_of_the_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    root = repo / "novels" / "series"
    shutil.copytree(FIXTURE, root)
    _write(root, 1, [P1, P2])
    _commit(repo, "one")
    _git(repo, "tag", "v1")
    _write(root, 1, [P1, P2.replace("knife", "blade")])
    rep = build_diff(root, BOOK, from_spec="v1")
    (h,) = rep.chapters[0].hunks
    assert "<del>knife.</del> <ins>blade.</ins>" in h.inline_html
    assert rep.chapters[0].file == f"books/{BOOK}/chapters/ch_01.md"


def test_unknown_ref_is_a_clean_error(tagged_series: Path) -> None:
    with pytest.raises(DiffError, match="unknown version"):
        build_diff(tagged_series, BOOK, from_spec="no-such-tag")


def test_not_a_git_repo_points_at_checkpoints(tmp_path: Path) -> None:
    root = _series(tmp_path, git=False)
    _write(root, 1, [P1])
    with pytest.raises(DiffError, match="checkpoint"):
        build_diff(root, BOOK, from_spec="last-tag")


# ------------------------------------------------------------ sanitising


@pytest.mark.parametrize("ref,expected", [
    ("draft_1", "draft_1"),
    ("HEAD~3", "HEAD-3"),
    ("refs/tags/v1.0", "refs-tags-v1.0"),
    ("../../etc/passwd", "etc-passwd"),
    ("checkpoint:2026-10-17T05-30-33", "checkpoint-2026-10-17T05-30-33"),
    ("a..b", "a-b"),
    ("   ", "ref"),
    ("x" * 200, "x" * 60),
])
def test_sanitize_ref(ref: str, expected: str) -> None:
    out = sanitize_ref(ref)
    assert out == expected
    assert "/" not in out and not out.startswith(".")


def test_default_output_paths_use_sanitised_labels(tagged_series: Path) -> None:
    _commit(tagged_series, "revise")
    rep = build_diff(tagged_series, BOOK, from_spec="draft_1", to_spec="HEAD~0")
    html_path, json_path = bookdiff.default_paths(tagged_series, BOOK, rep)
    assert html_path.name == "diff_draft_1_HEAD-0.html"
    assert json_path.name == "diff_draft_1_HEAD-0.json"
    assert html_path.parent == tagged_series / "books" / BOOK / "edit_logs"
    assert bookdiff.why_path_for(html_path).name == "diff_draft_1_HEAD-0.why.json"


# ------------------------------------------------------------ HTML


def test_html_has_hunk_list_counter_and_is_self_contained(tagged_series: Path) -> None:
    rep = build_diff(tagged_series, BOOK)
    html = render_html(rep)
    total = len(rep.all_hunks)
    assert f'<b id="total">{total}</b>' in html
    assert 'id="cur"' in html and 'id="next"' in html and 'id="prev"' in html
    for h in rep.all_hunks:
        assert f'id="{h.id}"' in html                 # the hunk itself
        assert f'href="#{h.id}"' in html              # its sidebar entry
        assert f"Change {h.n} of {total}" in html
    assert "<ins>eleven</ins>" in html
    assert "prefers-color-scheme: dark" in html
    assert 'name="viewport"' in html
    assert "fold-toggle" in html                      # unchanged runs collapse
    # Three views on one page, a big-changes filter, the view remembered.
    for view in ("changes", "whole", "clean"):
        assert f'data-view="{view}"' in html
    assert '<body class="view-changes">' in html
    assert 'id="bigonly"' in html
    assert "try{var v=localStorage.getItem(" in html
    assert "try { localStorage.setItem(KEY, v); } catch (e) {}" in html
    # Self-contained: no external scripts, styles, fonts or images.
    for needle in ('src="http', "src='http", 'href="http', "@import", "url(http"):
        assert needle not in html
    assert "e.key === 'j'" in html and "e.key === 'p'" in html


def test_html_escapes_prose(tmp_path: Path) -> None:
    old = _chapter(1, ["He wrote <b>nothing</b> & left."])
    new = _chapter(1, ["He wrote <script>x</script> & left."])
    fd = diff_file(old, new, key="ch01", file="ch_01.md", kind="chapter",
                   label="Chapter 1", chapter=1)
    assert "<script>" not in fd.hunks[0].inline_html
    assert "&lt;script&gt;x&lt;/script&gt;" in fd.hunks[0].inline_html


def test_no_changes_page(tagged_series: Path) -> None:
    rep = build_diff(tagged_series, BOOK, from_spec="draft_1", to_spec="draft_1")
    assert rep.all_hunks == []
    assert "No differences" in render_html(rep)


# ------------------------------------------------------------ annotation inputs


def test_hunk_list_is_compact_and_ordered(tagged_series: Path) -> None:
    rep = build_diff(tagged_series, BOOK)
    listing = bookdiff.render_hunk_list(rep)
    h1 = rep.chapters[0].hunks[0]
    assert f"- {h1.id} (fp {h1.fp}) ¶1 +1 −0" in listing
    assert "  + `eleven`" in listing
    assert P2 not in listing                       # kept text stays out
    assert "whole file (7 words)" in listing        # the added chapter
    assert "[ch01-summary]" in listing
    assert h1.changes == [["", "eleven"]]


def test_pinned_names_the_exact_version(tagged_series: Path) -> None:
    rep = build_diff(tagged_series, BOOK)
    tag_sha = _git(tagged_series, "rev-parse", "draft_1^{commit}")
    assert rep.old.to_dict()["pinned"] == tag_sha
    assert rep.new.to_dict()["pinned"] == "worktree"
    again = build_diff(tagged_series, BOOK, from_spec=rep.old.pinned,
                       to_spec=rep.new.pinned)
    assert [h.fp for h in again.all_hunks] == [h.fp for h in rep.all_hunks]


def test_cli_format_hunks_writes_nothing(tagged_series: Path) -> None:
    proc = _cli("--book", BOOK, "--format", "hunks", "--mark-read", cwd=tagged_series)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("# Changes in tiny-inquisitor")
    edit_logs = tagged_series / "books" / BOOK / "edit_logs"
    assert not list(edit_logs.glob("diff_*"))
    assert not (edit_logs / "last_read.json").exists()


# ------------------------------------------------------------ why annotations


def test_why_annotations_render_and_stale_ones_are_skipped(tagged_series: Path,
                                                           tmp_path: Path) -> None:
    rep = build_diff(tagged_series, BOOK)
    h1 = rep.chapters[0].hunks[0]
    removed = next(f for f in rep.chapters if f.status == "removed").hunks[0]
    why = tmp_path / "why.json"
    why.write_text(json.dumps({
        h1.id: "Brief ch01 §2: give the count a number <exact>.",
        removed.id: {"why": "stale note", "fp": "0000000000"},
        "ch01": "One number added to the opening.",
    }), encoding="utf-8")
    apply_why(rep, load_why(why))
    assert rep.why_applied == 2
    assert rep.why_stale == [removed.id]
    html = render_html(rep)
    assert "<b>Why:</b> Brief ch01 §2: give the count a number &lt;exact&gt;." in html
    assert "<b>What changed:</b> One number added to the opening." in html
    assert "stale note" not in html


# ------------------------------------------------------------ last-read bookmark


def test_bookmark_write_then_last_read_resolves_to_it(tagged_series: Path) -> None:
    head2 = _commit(tagged_series, "revise")
    snap = resolve_snapshot(tagged_series, BOOK, head2)
    bm = write_bookmark(tagged_series, BOOK, snap,
                        now=datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc))
    assert bm["sha"] == head2 and bm["when"] == "2026-10-17T12:00:00Z"
    stored = read_bookmark(tagged_series, BOOK)
    assert stored["sha"] == head2 and stored["ref"] == head2
    old = resolve_snapshot(tagged_series, BOOK, "last-read")
    assert old.sha == head2
    assert old.label == f"last-read-{head2[:7]}"
    assert "last read 2026-10-17T12:00:00Z" in (old.note or "")


def test_bookmark_for_worktree_records_head(tagged_series: Path) -> None:
    head = _git(tagged_series, "rev-parse", "HEAD")
    bm = write_bookmark(tagged_series, BOOK, resolve_snapshot(tagged_series, BOOK, "worktree"))
    assert bm["ref"] == "HEAD" and bm["sha"] == head
    assert bm["dirty"] is True                     # the fixture has uncommitted edits


def test_last_read_falls_back_to_last_tag_then_first_commit(tmp_path: Path) -> None:
    root = _series(tmp_path)
    _write(root, 1, [P1])
    first = _commit(root, "ch1")
    _write(root, 1, [P1, P2])
    _commit(root, "ch1 more")
    snap = resolve_snapshot(root, BOOK, "last-read")
    assert snap.sha == first                          # no bookmark, no tag
    assert "no last-read bookmark" in (snap.note or "")
    _git(root, "tag", "t1", first)
    snap = resolve_snapshot(root, BOOK, "last-read")
    assert snap.label == "t1"


# ------------------------------------------------------------ checkpoint mode


def test_checkpoint_mode_diffs_against_the_pre_command_state(tmp_path: Path) -> None:
    root = _series(tmp_path, git=False)
    ch1 = _write(root, 1, [P1, P2])
    _write(root, 2, ["Second chapter, untouched."])
    cp_dir = root / ".autonovel" / "checkpoints"
    checkpoints.create(cp_dir, root, [ch1], command="autonovel:revise", args=["1"],
                       now=datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc))
    _write(root, 1, [P1.replace("dawn", "first light"), P2])
    # A later command edits ch1 again and creates ch3.
    ch3 = _chapters_dir(root) / "ch_03.md"
    checkpoints.create(cp_dir, root, [ch1, ch3], command="autonovel:draft", args=["3"],
                       now=datetime(2026, 10, 17, 11, 0, tzinfo=timezone.utc))
    _write(root, 1, [P1.replace("dawn", "first light"), P2 + " He kept quiet."])
    _write(root, 3, ["Third chapter."])

    latest = build_diff(root, BOOK, from_spec="checkpoint:latest")
    st = {f.chapter: f.status for f in latest.chapters}
    assert st == {1: "changed", 2: "unchanged", 3: "added"}
    assert latest.chapters[0].words_added == 3      # only the second edit
    assert latest.old.label == "checkpoint-2026-10-17T11-00-00"

    first = build_diff(root, BOOK, from_spec="checkpoint:2026-10-17T10")  # unique prefix
    html = "\n".join(h.inline_html for h in first.chapters[0].hunks)
    assert "<del>dawn,</del>" in html and "<ins>first light,</ins>" in html
    assert "<ins>He kept quiet.</ins>" in html
    assert {f.chapter: f.status for f in first.chapters}[3] == "added"
    assert first.old.meta["command"] == "autonovel:revise"


def test_checkpoint_dir_path_and_missing_checkpoint(tmp_path: Path) -> None:
    root = _series(tmp_path, git=False)
    ch1 = _write(root, 1, [P1])
    cp = checkpoints.create(root / ".autonovel" / "checkpoints", root, [ch1],
                            command="autonovel:revise", args=["1"])
    _write(root, 1, [P1, P2])
    rep = build_diff(root, BOOK, from_spec=str(cp.directory))
    assert rep.chapters[0].words_added == len(P2.split())
    with pytest.raises(DiffError, match="no checkpoint named"):
        build_diff(root, BOOK, from_spec="checkpoint:1999")


# ------------------------------------------------------------ series template


def test_series_gitignore_drops_pages_but_keeps_annotations(tmp_path: Path) -> None:
    from autonovel.housekeeping import scaffold
    root = scaffold.new_series(tmp_path / "s", series_name="s").series.root
    _git(root, "init", "-q")
    logs = "books/b/edit_logs"

    def ignored(rel: str) -> bool:
        return subprocess.run(["git", "check-ignore", "-q", rel], cwd=root,
                              env=GIT_ENV).returncode == 0

    assert ignored(f"{logs}/diff_draft_1_worktree.html")
    assert ignored(f"{logs}/diff_draft_1_worktree.json")
    assert not ignored(f"{logs}/diff_draft_1_worktree.why.json")
    assert not ignored(f"{logs}/last_read.json")
    assert not ignored(f"{logs}/review.md")


# ------------------------------------------------------------ CLI round-trip


def _cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    # Run from inside the series (as the slash-command does) against the
    # same source tree this test imported.
    src = str(Path(bookdiff.__file__).resolve().parents[2])
    env = {**GIT_ENV, "PYTHONPATH": src + os.pathsep + os.environ.get("PYTHONPATH", "")}
    return subprocess.run(
        [sys.executable, "-m", "autonovel.mechanical", "diff-chapters", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def test_cli_default_paths_summary_and_mark_read(tagged_series: Path) -> None:
    proc = _cli("--book", BOOK, "--mark-read", cwd=tagged_series)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    for key in ("html", "json", "hunks", "chapters_changed", "words_added", "words_removed"):
        assert key in out
    edit_logs = tagged_series / "books" / BOOK / "edit_logs"
    assert Path(out["html"]) == (edit_logs / "diff_draft_1_worktree.html").resolve()
    assert Path(out["json"]).is_file() and Path(out["html"]).is_file()
    assert out["chapters_changed"] == 3
    assert out["bookmark"]["ref"] == "HEAD"
    assert (edit_logs / "last_read.json").is_file()
    data = json.loads(Path(out["json"]).read_text(encoding="utf-8"))
    assert len(data["hunks_detail"]) == out["hunks"]
    first = data["hunks_detail"][0]
    for key in ("id", "chapter", "index", "old_paragraphs", "new_paragraphs",
                "inline_html", "words_added", "words_removed",
                "context_before", "context_after"):
        assert key in first


def test_cli_format_json_out_and_why(tagged_series: Path, tmp_path: Path) -> None:
    out_json = tmp_path / "o" / "d.json"
    proc = _cli("--book", BOOK, "--from", "draft_1", "--chapters", "1-2",
                "--format", "json", "--out", str(out_json), cwd=tagged_series)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["html"] is None and Path(out["json"]) == out_json.resolve()
    assert not (tmp_path / "o" / "d.html").exists()
    hid = json.loads(out_json.read_text())["hunks_detail"][0]["id"]
    why = tmp_path / "why.json"
    why.write_text(json.dumps({hid: "Asked for in the brief."}))
    out_html = tmp_path / "o" / "d.html"
    proc = _cli("--book", BOOK, "--from", "draft_1", "--chapters", "1-2",
                "--out", str(out_html), "--why", str(why), cwd=tagged_series)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["why_applied"] == 1
    assert "Asked for in the brief." in out_html.read_text(encoding="utf-8")


def test_cli_bad_ref_exits_2(tagged_series: Path) -> None:
    proc = _cli("--book", BOOK, "--from", "nope", cwd=tagged_series)
    assert proc.returncode == 2
    assert "unknown version" in proc.stderr


# ------------------------------------------------------------ the author's read (2026-10-18)
#
# The author reviewed revised kingmaker2 chapters on a page built by hand
# because this one lacked: a plain what-changed note per change, Changes /
# Whole chapter / Clean text views, a big-changes filter, rewritten
# paragraphs shown as new text with the earlier draft folded, italics
# rendered, a next-change button that visibly works, and dark mode.

LONG = ("Sibylla came down the stairs behind him with a candle and a fur over her "
        "nightdress; she was thirty-nine, twenty years younger than he was, and they "
        "had been married for twenty-one years, long enough for her to know what a "
        "rider at that hour meant and not to ask it in front of the porter.")


@pytest.fixture
def two_change_series(tmp_path: Path) -> Path:
    """ch1 tagged v1, then a one-word edit in P1 (small) and a 50-word
    paragraph added after P5 (big)."""
    root = _series(tmp_path)
    _write(root, 1, [P1, P2, P3, P4, P5])
    _commit(root, "v1")
    _git(root, "tag", "v1")
    _write(root, 1, [P1.replace("dawn", "first light"), P2, P3, P4, P5, LONG])
    return root


def test_big_falls_back_to_the_size_rule(two_change_series: Path) -> None:
    rep = build_diff(two_change_series, BOOK, from_spec="v1", chapters={1})
    small, big = rep.chapters[0].hunks
    assert (small.is_big, big.is_big) == (False, True)
    assert big.words_added >= bookdiff.BIG_WORDS
    html = render_html(rep)
    assert f'<div class="hunk is-minor" id="{small.id}"' in html
    assert f'<div class="hunk is-big" id="{big.id}"' in html
    # The big ones listed, as links, at the head of the chapter.
    assert "The biggest changes (1 of 2: 40+ words, or a paragraph moved)" in html
    assert f'<li><a href="#{big.id}">' in html
    # Context paragraphs hide with the change they belong to.
    assert f'<p class="p-eq ctx is-minor">{P2}</p>' in html
    assert f'<p class="p-eq ctx">{P5}</p>' in html
    assert rep.totals()["big_hunks"] == 1


def _esc(s: str) -> str:
    import html as _h
    return _h.escape(s, quote=True)


def test_what_why_big_annotations_render(two_change_series: Path, tmp_path: Path) -> None:
    rep = build_diff(two_change_series, BOOK, from_spec="v1", chapters={1})
    small, big = rep.chapters[0].hunks
    why = tmp_path / "why.json"
    why.write_text(json.dumps({
        small.id: {"what": "Dawn becomes *first light*.", "why": "brief ch01 — the time of day",
                   "big": True, "fp": small.fp},
        big.id: {"what": "Sibylla introduced: thirty-nine, married twenty-one years.",
                 "why": "brief ch01 — Sibylla's Must line", "big": False, "fp": big.fp},
    }), encoding="utf-8")
    apply_why(rep, load_why(why))
    assert rep.why_applied == 2
    assert (small.is_big, big.is_big) == (True, False)       # the note's flag wins
    html = render_html(rep)
    # The what note heads the change, the why sits under it, quieter.
    head = html.index(f'id="{big.id}"')
    what_at = html.index('<div class="what">Sibylla introduced', head)
    why_at = html.index("<div class=\"why\"><b>Why:</b> brief ch01 — Sibylla", head)
    assert what_at < why_at
    assert "Dawn becomes <em>first light</em>." in html      # emphasis in notes
    # Notes in the change list; the big list uses the notes.
    assert f'<li class="is-big noted"><a href="#{small.id}" title="Dawn becomes first light.">' in html
    assert "The big changes (1 of 2)" in html
    assert f'<li><a href="#{small.id}">Dawn becomes <em>first light</em>.</a></li>' in html
    data = rep.to_dict()["hunks_detail"]
    assert data[0]["what"] == "Dawn becomes *first light*." and data[0]["big"] is True
    assert data[0]["big_source"] == "note" and data[1]["big"] is False


def test_old_why_sidecars_still_load(tmp_path: Path) -> None:
    p = tmp_path / "why.json"
    p.write_text(json.dumps({
        "ch01-001": "Brief ch01 asked for it.",
        "ch01-002": {"why": "talk turn 4", "fp": "abc"},
        "ch01-003": {"what": "Wording."},
        "ch01-004": {"big": True},
        "ch01-005": {"fp": "only a fingerprint"},
        "ch01": "One number added.",
    }), encoding="utf-8")
    w = load_why(p)
    assert w["ch01-001"] == {"why": "Brief ch01 asked for it.", "fp": None}
    assert w["ch01-002"] == {"why": "talk turn 4", "fp": "abc"}
    assert w["ch01-003"] == {"what": "Wording.", "fp": None}
    assert w["ch01-004"] == {"big": True, "fp": None}
    assert "ch01-005" not in w
    assert w["ch01"]["why"] == "One number added."


# Four phrases replaced, three long islands kept: 12 of 28 words survive.
RW_OLD = ("red fox ran by across the wide meadow old dog lay low beneath the tall oak "
          "six men sat on beside the stone wall rain fell all day")
RW_NEW = ("a cat woke up across the wide meadow two owls flew in beneath the tall oak "
          "ten boys ate it beside the stone wall snow came at dusk")


def test_rewritten_paragraph_shows_new_text_and_the_earlier_draft() -> None:
    fd = diff_file(_chapter(1, [P1, RW_OLD, P2]), _chapter(1, [P1, RW_NEW, P2]),
                   key="ch01", file="ch_01.md", kind="chapter", label="Chapter 1", chapter=1)
    (h,) = fd.hunks
    assert h.rewritten == 1
    new_part, fold = h.inline_html.split('<details class="earlier">')
    assert 'class="p-ins p-rewritten"' in new_part and "snow came at dusk" in new_part
    assert "<del>" not in new_part                       # no interleaved fragments
    assert "Rewritten — show the earlier draft</summary>" in fold
    assert "rain fell all day" in fold and 'class="p-eq p-old"' in fold
    assert h.changes == [[RW_OLD, RW_NEW]]               # one whole pair for the annotator
    assert (h.words_added, h.words_removed) == (16, 16)
    assert "(rewritten)" in bookdiff.render_hunk_list(_report_of(fd))


def _report_of(fd) -> bookdiff.DiffReport:
    snap = bookdiff.Snapshot(spec="a", label="a", description="a")
    rep = bookdiff.DiffReport(book=BOOK, series_root=".", old=snap, new=snap, chapters=[fd],
                              foundation=[], threshold=0.4, chapter_filter=None, generated="now")
    for k, h in enumerate(rep.all_hunks, 1):
        h.n = k
    return rep


def test_is_rewritten_thresholds() -> None:
    Seg = bookdiff.Seg

    def segs(kept: int, replacements: int, per: int) -> list:
        """`kept` unchanged words, then `replacements` runs of `per` words
        replaced (each counts as two runs: deleted and inserted)."""
        return ([Seg("eq", ["k"] * kept, ["k"] * kept)]
                + [Seg("chg", ["o"] * per, ["n"] * per) for _ in range(replacements)])

    # kept 9/19 = 0.47 with 4 runs: rewritten
    assert bookdiff.is_rewritten(segs(9, 2, 5))
    # kept 11/20 = 0.55 with 6 runs: not yet ...
    assert not bookdiff.is_rewritten(segs(11, 3, 3))
    # ... but with 10 runs (kept 11/21 = 0.52) it is
    assert bookdiff.is_rewritten(segs(11, 5, 2))
    # a one-word edit never is
    assert not bookdiff.is_rewritten([Seg("eq", ["k"] * 19, ["k"] * 19), Seg("chg", ["a"], ["b"])])


def test_tiny_unchanged_islands_fold_into_the_edit() -> None:
    segs = word_diff(tokenize("Then the old man walked home."),
                     tokenize("Then an old woman walked home."))
    assert [s.tag for s in segs] == ["eq", "chg", "eq"]
    assert segs[1].old == ["the", "old", "man"] and segs[1].new == ["an", "old", "woman"]
    # A three-word island is shared text and stays.
    segs = word_diff(tokenize("He saw the red fox run under the gate at dusk."),
                     tokenize("He saw the grey fox run under the gate at dawn."))
    assert "".join(s.tag[0] for s in segs) == "ecec"


def test_pairing_finds_a_paragraph_pushed_down_past_new_ones() -> None:
    a_new = P1.replace("dawn", "first light")
    glue = "The boatman crossed the lagoon too, at dawn, and his ducats were counted."
    old = [tokenize(P1), tokenize(P4)]
    new = [tokenize("Snow fell on the Weinmarkt all night."),
           tokenize("Nobody moved in the street below."),
           tokenize(glue), tokenize(a_new), tokenize(P4 + " Again.")]
    items = pair_paragraphs(old, new)
    # A neighbour sharing a few words is not glued on as a "split".
    assert ("pair", [0], [3]) in items and ("ins", [], [2]) in items
    assert ("pair", [1], [4]) in items


def test_pairing_reaches_far_off_the_diagonal_in_a_big_hunk() -> None:
    old_p = [P1, P2, P3, P4, P5]
    filler = [f"Filler {k}: the wagons stood in the snow and the drivers waited for word."
              for k in range(85)]
    new_p = filler + [p.replace(" the ", " that ", 1) if " the " in p else p + " Then."
                      for p in old_p]
    items = pair_paragraphs([tokenize(p) for p in old_p], [tokenize(p) for p in new_p])
    pairs = {tuple(o): tuple(n) for k, o, n in items if k == "pair"}
    assert pairs == {(i,): (85 + i,) for i in range(5)}


def test_markdown_emphasis_is_rendered_at_token_level() -> None:
    old = "*He crossed the lagoon at dawn,* Jakob wrote."
    new = "*He crossed the wide lagoon at dawn,* Jakob wrote."
    fd = diff_file(_chapter(1, [old]), _chapter(1, [new]), key="ch01", file="ch_01.md",
                   kind="chapter", label="Chapter 1", chapter=1)
    (h,) = fd.hunks
    assert ("<em>He crossed the</em> <ins><em>wide</em></ins> "
            "<em>lagoon at dawn,</em> Jakob wrote.") in h.inline_html
    assert "*" not in h.inline_html
    assert h.snippet == "… He crossed the wide lagoon at"
    assert h.snippet_html == "… <em>He crossed the wide lagoon at</em>"
    plain = bookdiff.render_plain_paragraph
    assert plain("**Plot:** Jakob arrives.") == \
        '<p class="p-eq"><strong>Plot:</strong> Jakob arrives.</p>'
    assert "*there" in plain("A lone * mark and *there it stops.")   # unbalanced: literal
    assert plain("* * *") == '<p class="p-eq md-break">* * *</p>'
    assert bookdiff.md_inline_html("Konrad *Mair* <b>") == "Konrad <em>Mair</em> &lt;b&gt;"


def test_page_has_three_views_and_a_filter_with_distinct_state_classes(
        two_change_series: Path) -> None:
    import re
    html = render_html(build_diff(two_change_series, BOOK, from_spec="v1"))
    css = html[html.index("<style>"):html.index("</style>")]
    # Changes folds; Whole chapter opens every fold; Clean text shows the
    # new version only (no deletions, cut paragraphs, notes or earlier drafts).
    assert "body.view-whole .fold-body, body.view-clean .fold-body { display: block; }" in css
    for hidden in ("body.view-clean del", "body.view-clean .p-del", "body.view-clean .what",
                   "body.view-clean .why", "body.view-clean details.earlier",
                   "body.view-clean .hunk-head", "body.view-clean section.st-removed"):
        assert hidden in css
    assert "body.view-clean ins { background: none;" in css
    # The filter's state class lives on <body>, set by script only, and is
    # never a component's class (the hand-built page broke on that).
    assert "body.view-changes.filter-big .is-minor { display: none; }" in css
    assert "body.classList.toggle('filter-big', on)" in html
    assert 'class="bigfilter"' in html
    classes = " ".join(re.findall(r'class="([^"]*)"', html)).split()
    assert "filter-big" not in classes and "bigonly" not in classes


def test_page_shell_fits_an_artifact_frame_and_a_phone(tagged_series: Path) -> None:
    html = render_html(build_diff(tagged_series, BOOK))
    assert ('@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) '
            '{ color-scheme: dark;') in html
    assert ':root[data-theme="dark"] { color-scheme: dark;' in html
    assert "body { margin: 0; background: var(--bg); color: var(--fg);" in html
    assert "position: sticky; top: env(safe-area-inset-top, 0px)" in html
    assert "max(16px, env(safe-area-inset-left, 0px))" in html
    assert "max(16px, env(safe-area-inset-right, 0px))" in html
    assert "viewport-fit=cover" in html
    assert "--ins-bg: #173b23" in html                   # dark tokens present


def test_change_navigation_steps_by_index_and_resyncs(tagged_series: Path) -> None:
    html = render_html(build_diff(tagged_series, BOOK))
    js = html[html.rindex("<script>"):]
    assert 'class="counter" aria-live="polite"' in html
    assert "new IntersectionObserver(" in js             # resync after manual scrolling
    assert "vs[i]._k > cur" in js and "vs[i]._k < cur" in js   # index, not position
    assert "h.getClientRects().length > 0" in js         # only changes the view/filter shows
    assert "prefers-reduced-motion: reduce" in js and "prefers-reduced-motion: reduce" in html
    assert "h.classList.add('flash')" in js
    assert "root.style.setProperty('--bar-h'" in js       # toolbar height measured
    assert "scroll-padding-top: calc(var(--bar-h)" in html
    assert "/^(TEXTAREA|SELECT)$/" in js and "t.isContentEditable" in js
    assert "e.key === 'n'" in js and "e.key === 'k'" in js


def test_default_paths_name_the_chapters(tagged_series: Path) -> None:
    rep = build_diff(tagged_series, BOOK, chapters={1, 2})
    html_path, _ = bookdiff.default_paths(tagged_series, BOOK, rep)
    assert html_path.name == "diff_draft_1_worktree_ch01-02.html"
    assert bookdiff._chapters_slug([1, 5, 9, 10, 11]) == "ch01_05_09-11"
    whole, _ = bookdiff.default_paths(tagged_series, BOOK, build_diff(tagged_series, BOOK))
    assert whole.name == "diff_draft_1_worktree.html"


def test_if_read_skips_without_a_bookmark(tagged_series: Path) -> None:
    proc = _cli("--book", BOOK, "--from", "last-read", "--chapters", "1", "--if-read",
                cwd=tagged_series)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["html"] is None and out["skipped"].startswith("no last-read bookmark")
    assert not list((tagged_series / "books" / BOOK / "edit_logs").glob("diff_*"))


def test_if_read_hands_back_only_chapters_the_author_read(tagged_series: Path) -> None:
    head = _commit(tagged_series, "revise")              # ch1 + ch2 now in HEAD
    _git(tagged_series, "checkout", "-q", "draft_1")     # bookmark the version without ch2
    write_bookmark(tagged_series, BOOK, resolve_snapshot(tagged_series, BOOK, "draft_1"))
    _git(tagged_series, "checkout", "-q", head)
    proc = _cli("--book", BOOK, "--from", "last-read", "--chapters", "2", "--if-read",
                cwd=tagged_series)
    assert json.loads(proc.stdout)["skipped"] == "chapter 2 did not exist in the version last read"
    proc = _cli("--book", BOOK, "--from", "last-read", "--chapters", "1", "--if-read",
                cwd=tagged_series)
    out = json.loads(proc.stdout)
    assert "skipped" not in out and out["from"]["from_bookmark"] is True
    assert Path(out["html"]).name.endswith("_worktree_ch01.html")
    assert out["big_hunks"] == 0 and out["hunks"] == 1   # the edit; its summary is left out with --chapters


def test_if_read_needs_last_read(tagged_series: Path) -> None:
    proc = _cli("--book", BOOK, "--from", "draft_1", "--if-read", cwd=tagged_series)
    assert proc.returncode == 2 and "--if-read needs --from last-read" in proc.stderr


def test_hunk_list_asks_for_what_why_and_big(tagged_series: Path) -> None:
    listing = bookdiff.render_hunk_list(build_diff(tagged_series, BOOK))
    assert '`{"what": "...", "why": "...", "big": true, "fp": "<fp>"}`' in listing
