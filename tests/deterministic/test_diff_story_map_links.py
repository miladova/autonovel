"""Tier-1: `/autonovel:diff` and `/autonovel:story-map` link each other.

Bug class: the author expected the storyline, characters and places on
the diff page; the story map was a separate page that nothing linked and
that had never been built for the book. Now `diff-chapters` rebuilds the
story map beside the diff page and the two pages cross-link; a story-map
failure never fails the diff.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autonovel.mechanical import bookdiff, story_map


def _book(tmp: Path) -> Path:
    root = tmp / "series"
    ch = root / "books" / "demo" / "chapters"
    ch.mkdir(parents=True)
    (root / "project.yaml").write_text("series_name: s\nbooks:\n- name: demo\n", encoding="utf-8")
    for n, body in ((1, "Old first."), (2, "Second stays.")):
        (ch / f"ch_{n:02d}.md").write_text(
            f"---\nbook: demo\nchapter: {n}\ntitle: T{n}\nstory_time: 1473-0{n}\n---\n\n{body}\n",
            encoding="utf-8")
        (ch / f"ch_{n:02d}.summary.md").write_text(
            f"## Plot\nChapter {n} happens.\n", encoding="utf-8")
    return root


def _args(root: Path, **kw) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    bookdiff.add_arguments(p)
    ns = p.parse_args(["--book", "demo", "--series-root", str(root)])
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def test_diff_writes_a_linked_story_map(tmp_path: Path, capsys, monkeypatch) -> None:
    root = _book(tmp_path)
    import subprocess
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True,
                                    capture_output=True)
    git("init", "-q"); git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "v1")
    git("tag", "v1")
    old = (root / "books/demo/chapters/ch_01.md").read_text(encoding="utf-8")
    (root / "books/demo/chapters/ch_01.md").write_text(
        old.replace("Old first.", "New first."), encoding="utf-8")
    rc = bookdiff.cli(_args(root, from_spec="v1", to_spec="worktree"))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    sm = out["story_map"]
    assert sm and sm["html"], out
    edit_logs = root / "books/demo/edit_logs"
    diff_html = Path(out["html"]).read_text(encoding="utf-8")
    assert 'href="story_map.html"' in diff_html
    assert 'href="story_map.html#ch-1"' in diff_html
    map_html = (edit_logs / "story_map.html").read_text(encoding="utf-8")
    page = Path(out["html"]).name
    assert f'href="{page}#file-ch01"' in map_html      # changed chapter links its changes
    assert f'href="{page}#file-ch02"' not in map_html  # unchanged chapter does not


def test_no_story_map_flag_and_failure_are_safe(tmp_path: Path, capsys, monkeypatch) -> None:
    root = _book(tmp_path)
    rc = bookdiff.cli(_args(root, from_spec="worktree", to_spec="worktree", story_map=False))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["story_map"] is None
    assert "story_map.html" not in Path(out["html"]).read_text(encoding="utf-8")

    def boom(*a, **k):
        raise RuntimeError("no map today")
    monkeypatch.setattr(story_map, "build_story_map", boom)
    rc = bookdiff.cli(_args(root, from_spec="worktree", to_spec="worktree"))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["story_map"]["html"] is None and "no map today" in out["story_map"]["error"]
    assert 'class="maplink"' not in Path(out["html"]).read_text(encoding="utf-8")


def test_standalone_story_map_finds_the_newest_diff(tmp_path: Path) -> None:
    root = _book(tmp_path)
    logs = root / "books/demo/edit_logs"
    logs.mkdir(parents=True)
    (logs / "diff_a_b.html").write_text("<html></html>", encoding="utf-8")
    (logs / "diff_a_b.json").write_text(json.dumps(
        {"chapters": [{"chapter": 2, "hunks": 3}, {"chapter": 1, "hunks": 0}]}), encoding="utf-8")
    sm = story_map.build_story_map(root / "books/demo", series_root=root)
    res = story_map.write_story_map(sm)
    assert res["diff_page"] == "diff_a_b.html"
    html = (logs / "story_map.html").read_text(encoding="utf-8")
    assert 'href="diff_a_b.html#file-ch02">3 changes</a>' in html
    assert "#file-ch01" not in html
