"""Tier-1, in a real browser: the diff page's change navigation, views and
filter. Skipped when Playwright or its Chromium is not installed.

Bug class (author, 2026-10-18): "I wasn't sure the next-change button
worked" -- the first changes sat a few lines apart, and position-based
"first change below the toolbar" stepping is fragile. The page now steps
by index among the changes the current view and filter show, with a
"change N of M" counter, and keeps the reader's place across views.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from autonovel.mechanical import bookdiff  # noqa: E402


LONG = ("Sibylla came down the stairs behind him with a candle and a fur over her "
        "nightdress; she was thirty-nine, twenty years younger than he was, and they "
        "had been married for twenty-one years, long enough for her to know what a "
        "rider at that hour meant and not to ask it in front of the porter.")


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    try:
        b = pw.chromium.launch()
    except Exception as e:  # noqa: BLE001 -- no browser binary here
        pw.stop()
        pytest.skip(f"Playwright has no Chromium: {e}")
    yield b
    b.close()
    pw.stop()


def _page(tmp_path: Path) -> Path:
    paras = [f"Paragraph {k} tells how the rider number {k} came through the gate in the snow."
             for k in range(12)]
    new = list(paras)
    for k in (0, 2, 4):                       # three small edits, a few lines apart
        new[k] = new[k].replace("snow", "sleet")
    new.insert(10, LONG)                      # one big change
    md = lambda ps: "---\ntitle: T\n---\n\n" + "\n\n".join(ps) + "\n"  # noqa: E731
    fd = bookdiff.diff_file(md(paras), md(new), key="ch01", file="ch_01.md",
                            kind="chapter", label="Chapter 1", chapter=1)
    snap = bookdiff.Snapshot(spec="a", label="a", description="a")
    rep = bookdiff.DiffReport(book="b", series_root=".", old=snap, new=snap, chapters=[fd],
                              foundation=[], threshold=0.4, chapter_filter=None,
                              generated="now")
    for k, h in enumerate(rep.all_hunks, 1):
        h.n = k
    out = tmp_path / "diff.html"
    out.write_text(bookdiff.render_html(rep), encoding="utf-8")
    return out


STATE = """() => ({
  counter: document.querySelector('.counter').textContent.replace(/\\s+/g, ' ').trim(),
  current: (document.querySelector('.hunk.current') || {}).id || null,
  gap: (() => { const h = document.querySelector('.hunk.current'); if (!h) return null;
    return h.getBoundingClientRect().top - document.querySelector('.toolbar').getBoundingClientRect().bottom; })(),
  overflow: document.documentElement.scrollWidth - window.innerWidth,
  view: document.body.className,
})"""


def test_next_change_steps_through_close_changes_on_a_phone(browser, tmp_path: Path) -> None:
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(_page(tmp_path).as_uri())
    assert page.evaluate(STATE)["counter"] == "change – of 4"
    seen = []
    for _ in range(3):
        page.click("#next")
        page.wait_for_timeout(700)
        s = page.evaluate(STATE)
        seen.append((s["counter"], s["current"]))
        assert 0 <= s["gap"] < 40                 # landed just below the two-line toolbar
        assert s["overflow"] == 0                 # no horizontal scroll at 390px
    assert seen == [("change 1 of 4", "ch01-001"), ("change 2 of 4", "ch01-002"),
                    ("change 3 of 4", "ch01-003")]
    page.keyboard.press("j")
    page.wait_for_timeout(700)
    assert page.evaluate(STATE)["counter"] == "change 4 of 4"
    page.keyboard.press("k")
    page.wait_for_timeout(700)
    assert page.evaluate(STATE)["current"] == "ch01-003"


def test_filter_and_views_change_what_next_visits(browser, tmp_path: Path) -> None:
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(_page(tmp_path).as_uri())
    page.click("#next")
    page.wait_for_timeout(700)
    page.check("#bigonly")                        # the current (small) change hides
    page.wait_for_timeout(200)
    assert page.evaluate(STATE)["counter"] == "change – of 1"
    page.click("#next")
    page.wait_for_timeout(700)
    s = page.evaluate(STATE)
    assert (s["counter"], s["current"]) == ("change 1 of 1", "ch01-004")
    page.uncheck("#bigonly")
    page.click('[data-view="clean"]')
    page.wait_for_timeout(200)
    hidden = page.evaluate("""() => ({
      del: [...document.querySelectorAll('del')].filter(e => e.getClientRects().length).length,
      nav: document.querySelector('.nav').getClientRects().length,
      folds: [...document.querySelectorAll('.fold-body')].every(e => e.getClientRects().length)})""")
    assert hidden == {"del": 0, "nav": 0, "folds": True}
    page.reload()                                  # the view is remembered
    assert "view-clean" in page.evaluate(STATE)["view"]
    page.click('[data-view="whole"]')
    assert page.evaluate(STATE)["overflow"] == 0
