"""Insert inline translation glosses into `the-tuning.md`.

Two mechanisms, because one does not fit both cases:

* `{{English}}` at the end of a paragraph -> the translation is set on its own
  line, in the smaller italic, under the German. Used where the paragraph *is*
  the German line (a speech, or a speech with a said-tag).
* `[[English]]` after the German inside a paragraph -> the translation runs on
  in brackets, in the same smaller italic. Used where the German sits inside
  narration, because a gloss line under five lines of narration reads as though
  it glossed the narration.

Idempotent: refuses to double-apply.
"""
from __future__ import annotations

import pathlib
import sys

MD = pathlib.Path(__file__).parent / "the-tuning.md"

# (exact German run including its quotes, translation, mechanism)
GLOSSES: list[tuple[str, str, str]] = [
    ('"Beruf?"', "Occupation?", "line"),

    ('"Sie sind sp\u00e4t."', "You are late.", "inline"),
    ('"Der Fl\u00fcgel ist im Salon. Nicht anfassen, was Sie nicht stimmen '
     'm\u00fcssen."',
     "The grand is in the drawing room. Don't touch anything you don't have "
     "to tune.", "inline"),
    ('"Das ist ein guter Fl\u00fcgel."', "That is a good grand.", "inline"),
    ('"Ja," Marianna said. "Er ist sehr gut."', "Yes. It is very good.", "line"),

    ('"Frau Frontczak. Es ist lange her."',
     "Mrs Frontczak. It has been a long time.", "inline"),
    ('"Bleiben Sie."', "Stay.", "line"),
    ('"Sie sind also Klavierstimmerin,"', "So you are a piano tuner.", "line"),
    ('"Meine Tante hatte einen Stimmer. Ich habe von ihm gelernt."',
     "My aunt had a tuner. I learned from him.", "line"),
    ('"Ich erinnere mich."', "I remember.", "inline"),
    ('"Ihr Mann?"', "Your husband?", "line"),
    ('"Er lebt."', "He is alive.", "line"),
    ('"Was macht er?"', "What does he do?", "line"),
    ('"Er arbeitet."', "He works.", "inline"),
    ('"Und das ist Ihre Tochter,"', "And this is your daughter.", "line"),
    ('"Wie alt bist du?"', "How old are you?", "inline"),
    ('"Vierzehn," Zosia said', "Fourteen.", "line"),
    ('"Seit neun Tagen,"', "For nine days.", "line"),
    ('"Es ist eine gute Zeit, vierzehn zu sein."',
     "Fourteen is a good age to be.", "inline"),
    ('"Ich habe dir geschrieben," she said.', "I wrote to you.", "after"),
    ('"Wann?"', "When?", "line"),
    ('"Ich habe keinen Brief bekommen," he said.', "I never received a letter.",
     "after"),
    ('"Keinen einzigen."', "Not one.", "line"),
    ('"Was war das andere?"', "What was the other thing?", "line"),
    ('"Czy to prawda, \u017ce oni ich pal\u0105?"',
     "Mama, is it true they are burning them?", "line"),

    # the window paragraph: one gloss per speech, set after the closing quote
    # rather than between the quote and its said-tag
    ('"Bewaffnete M\u00e4nner. Es ist eine milit\u00e4rische Angelegenheit, '
     'und sie ist fast zu Ende."',
     "There are partisans there. Armed men. It is a military matter, and it is "
     "nearly over.", "inline"),
    ('"Der Fl\u00fcgel ist noch nicht fertig,"',
     "The grand is not finished yet.", "inline"),

    ('"Spielen Sie etwas,"', "Play something. Please.", "line"),
    ('"Sie spielen es langsamer,"', "You play it slower.", "line"),
    ('"Fr\u00fcher hast du es schneller gespielt."',
     "You used to play it faster.", "line"),
    ('"Ich war j\u00fcnger."', "I was younger.", "inline"),
    ('"Vorname."', "First name.", "line"),
    ('"Geburtsname."', "Maiden name.", "line"),
    ('"Ich wei\u00df, wie man das schreibt,"',
     "I know how to spell it.", "line"),

    # the permit: first speech glossed as one, second after the closing quote
    ('"Bis zum einunddrei\u00dfigsten Dezember. Ihre Tochter ist '
     'Angeh\u00f6rige, sie steht mit darauf."',
     "You are employed by the staff household. Until the thirty-first of "
     "December. Your daughter is a dependent; she is covered on it.", "inline"),
    ('"Sie kommen zweimal in der Woche. Dienstag und Freitag. Sie stimmen den '
     'Fl\u00fcgel, und was sonst im Haus an Arbeit ist."',
     "You will come twice a week. Tuesday and Friday. You tune the grand, and "
     "whatever else there is to do in the house.", "inline"),

    ('"Hast du noch das Metronom?"', "Do you still have the metronome?", "line"),
    ('"Es hat nie richtig getickt."', "It never kept proper time.", "inline"),
    ('"Ihre Tochter spricht sehr gut Deutsch."',
     "Your daughter speaks very good German.", "inline"),
    ("Guten Abend, gut' Nacht.", "Good evening, good night.", "line"),
]

# German embedded in narration, where a bracket would break the sentence
INLINE_WORDS = [
    ("the word *Wagen*", "the word *Wagen*[[car]]"),
    ("a board on the front of it that said NUR F\u00dcR DEUTSCHE",
     "a board on the front of it that said NUR F\u00dcR DEUTSCHE[[Germans only]]"),
    ("*Donnerstag*, and a number, and *mit den anderen*, and *nein, die gleiche Liste*",
     "*Donnerstag*[[Thursday]], and a number, and *mit den anderen*[[with the "
     "others]], and *nein, die gleiche Liste*[[no, the same list]]"),
]

BARE_JA = 2


def main() -> int:
    text = MD.read_text(encoding="utf-8")
    if "{{" in text or "[[" in text:
        print("glosses already applied; nothing to do")
        return 1

    line_mode: list[tuple[str, str]] = []
    inline_mode: list[tuple[str, str]] = []
    after_mode: list[tuple[str, str]] = []
    for german, english, how in GLOSSES:
        {"line": line_mode, "inline": inline_mode, "after": after_mode}[how].append(
            (german, english))

    # inline first: these edit inside paragraphs
    for german, english in inline_mode:
        if text.count(german) != 1:
            print(f"  !! {german[:56]!r}: found {text.count(german)} times")
            return 2
        text = text.replace(german, german + "[[" + english + "]]")

    # "after": the gloss goes behind a said-tag, not between the quote and it
    for anchor, english in after_mode:
        if text.count(anchor) != 1:
            print(f"  !! {anchor[:56]!r}: found {text.count(anchor)} times")
            return 7
        text = text.replace(anchor, anchor + "[[" + english + "]]")

    # then line glosses, appended to the paragraph that holds them
    blocks = text.split("\n\n")
    for german, english in line_mode:
        hits = [i for i, b in enumerate(blocks) if german in b]
        if len(hits) != 1:
            print(f"  !! {german[:56]!r}: {len(hits)} paragraphs")
            return 3
        i = hits[0]
        if "{{" in blocks[i]:
            print(f"  !! {german[:56]!r}: paragraph already glossed")
            return 4
        blocks[i] = blocks[i].rstrip() + " {{" + english + "}}"

    ja = [i for i, b in enumerate(blocks) if b.strip() == '"Ja."']
    if len(ja) != BARE_JA:
        print(f"  !! expected {BARE_JA} bare 'Ja.' lines, found {len(ja)}")
        return 5
    for i in ja:
        blocks[i] = blocks[i].rstrip() + " {{Yes.}}"

    text = "\n\n".join(blocks)
    for old, new in INLINE_WORDS:
        if old not in text:
            print(f"  !! missing: {old[:56]!r}")
            return 6
        text = text.replace(old, new)

    MD.write_text(text, encoding="utf-8")
    print(f"applied {len(line_mode) + BARE_JA} line glosses, "
          f"{len(inline_mode)} inline, {len(after_mode)} behind a said-tag, "
          f"{len(INLINE_WORDS)} word glosses")
    return 0


if __name__ == "__main__":
    sys.exit(main())
