"""Structured query DSL over the per-chapter summary index.

Background: `/autonovel:talk` handles fuzzy semantic questions via
the LLM; `/autonovel:chapter-summary` prints the whole table.
This module is the lightweight middle ground — a small filter DSL
that runs over the already-structured `ChapterRow` records (POV,
story_time, score, cast, location, plot, word_count) returned by
`chapter_summary.summarize_chapters()`. No LLM, fully scriptable,
stable semantics, free.

Supported predicates:

  pov == "Lucia"
  pov != "Niccolò"
  score < 7.0
  score >= 7.5
  low_score < 7.0          (the chapter's lowest dimension)
  low_dim == "sense_of_place"
  story_time >= "1521-11"
  story_time <= "1522-02"
  word_count > 3000
  cast contains Niccolò
  cast contains \"two-word name\"
  plot contains \"book of accounts\"
  location contains Padua
  chapter == 5
  chapter in 3..8

Predicates combine with `and` (`&&`) and `or` (`||`). Parenthesise
to override left-to-right evaluation. `not <pred>` negates.

Why a custom mini-language and not `eval()`: safety (no arbitrary
code), better error messages, and a stable contract independent
of Python syntax (the DSL is a published interface for users).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .chapter_summary import ChapterRow, format_low


# ---------------------------------------------------------- public entry


def filter_rows(rows: list[ChapterRow], expr: str) -> list[ChapterRow]:
    """Apply `expr` to `rows` and return the matching subset.
    Empty / whitespace-only expressions return all rows."""
    if not expr or not expr.strip():
        return list(rows)
    ast = _parse(expr)
    return [r for r in rows if _eval_node(ast, r)]


class QueryError(ValueError):
    """Raised on parse or evaluation failure. Message is user-
    facing — name the offending token and the position when
    possible."""


# ---------------------------------------------------------- tokeniser


_TOKEN_RE = re.compile(
    r"""
    \s*
    (?:
      (?P<num>     -?\d+(?:\.\d+)?)     |
      (?P<str>     "(?:[^"\\]|\\.)*")  |
      (?P<sstr>    '(?:[^'\\]|\\.)*')  |
      (?P<op>      ==|!=|<=|>=|<|>|&&|\|\|) |
      (?P<lparen>  \()                  |
      (?P<rparen>  \))                  |
      (?P<range>   \.\.)                |
      (?P<word>    [^\W\d][\w-]*)
    )
    """,
    re.VERBOSE | re.UNICODE,
)


@dataclass
class Token:
    kind: str
    value: Any
    pos: int


def _tokenise(s: str) -> list[Token]:
    out: list[Token] = []
    i = 0
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        m = _TOKEN_RE.match(s, i)
        if not m:
            raise QueryError(
                f"unexpected character at position {i}: {s[i]!r}"
            )
        kind = m.lastgroup
        text = m.group(kind)
        if kind == "num":
            value = float(text) if "." in text else int(text)
        elif kind in ("str", "sstr"):
            value = bytes(text[1:-1], "utf-8").decode("unicode_escape")
        else:
            value = text
        out.append(Token(kind=kind, value=value, pos=i))
        i = m.end()
    return out


# ---------------------------------------------------------- parser


@dataclass
class Node:
    """One AST node. `kind` is one of:
       'cmp' (binary comparison), 'and', 'or', 'not', 'contains',
       'in_range'."""
    kind: str
    children: list[Any]


_FIELDS = {"pov", "score", "story_time", "word_count",
            "cast", "plot", "location", "chapter", "status",
            "low_score", "low_dim"}


class _Parser:
    def __init__(self, tokens: list[Token], expr: str) -> None:
        self.tokens = tokens
        self.pos = 0
        self.expr = expr

    def peek(self) -> Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def expect(self, kind: str, value: Any | None = None) -> Token:
        t = self.peek()
        if t is None:
            raise QueryError(f"expected {kind} at end of expression")
        if t.kind != kind or (value is not None and t.value != value):
            raise QueryError(
                f"expected {value or kind} at position {t.pos}, got {t.value!r}"
            )
        return self.consume()

    # Grammar:
    #   expr     := or_expr
    #   or_expr  := and_expr ( '||'|'or'  and_expr )*
    #   and_expr := unary    ( '&&'|'and' unary    )*
    #   unary    := ('not' unary) | atom
    #   atom     := '(' expr ')' | predicate
    #   predicate := <field> <op> <literal>
    #              | <field> 'contains' <literal>
    #              | <field> 'in' <num> '..' <num>

    def parse(self) -> Node:
        node = self._or()
        if self.pos != len(self.tokens):
            t = self.tokens[self.pos]
            raise QueryError(f"unexpected token at position {t.pos}: {t.value!r}")
        return node

    def _or(self) -> Node:
        left = self._and()
        while True:
            t = self.peek()
            if t is None:
                break
            if t.kind == "op" and t.value == "||":
                self.consume()
                right = self._and()
                left = Node(kind="or", children=[left, right])
            elif t.kind == "word" and t.value == "or":
                self.consume()
                right = self._and()
                left = Node(kind="or", children=[left, right])
            else:
                break
        return left

    def _and(self) -> Node:
        left = self._unary()
        while True:
            t = self.peek()
            if t is None:
                break
            if t.kind == "op" and t.value == "&&":
                self.consume()
                right = self._unary()
                left = Node(kind="and", children=[left, right])
            elif t.kind == "word" and t.value == "and":
                self.consume()
                right = self._unary()
                left = Node(kind="and", children=[left, right])
            else:
                break
        return left

    def _unary(self) -> Node:
        t = self.peek()
        if t is not None and t.kind == "word" and t.value == "not":
            self.consume()
            return Node(kind="not", children=[self._unary()])
        return self._atom()

    def _atom(self) -> Node:
        t = self.peek()
        if t is None:
            raise QueryError("unexpected end of expression")
        if t.kind == "lparen":
            self.consume()
            node = self._or()
            self.expect("rparen")
            return node
        return self._predicate()

    def _predicate(self) -> Node:
        field_tok = self.expect("word")
        field = field_tok.value
        if field not in _FIELDS:
            raise QueryError(
                f"unknown field {field!r} at position {field_tok.pos}; "
                f"valid: {', '.join(sorted(_FIELDS))}"
            )
        nxt = self.peek()
        if nxt is None:
            raise QueryError(f"expected operator after {field!r}")
        # `<field> contains <literal>`
        if nxt.kind == "word" and nxt.value == "contains":
            self.consume()
            lit = self._literal()
            return Node(kind="contains", children=[field, lit])
        # `<field> in <num>..<num>`
        if nxt.kind == "word" and nxt.value == "in":
            self.consume()
            lo = self._number()
            self.expect("range")
            hi = self._number()
            return Node(kind="in_range", children=[field, lo, hi])
        # `<field> <op> <literal>`
        if nxt.kind == "op" and nxt.value in ("==", "!=", "<", ">", "<=", ">="):
            op = self.consume().value
            lit = self._literal()
            return Node(kind="cmp", children=[field, op, lit])
        raise QueryError(
            f"expected operator (==, !=, <, >, <=, >=, contains, in) "
            f"after {field!r} at position {nxt.pos}"
        )

    def _literal(self) -> Any:
        t = self.peek()
        if t is None:
            raise QueryError("expected literal")
        if t.kind in ("str", "sstr"):
            return self.consume().value
        if t.kind == "num":
            return self.consume().value
        if t.kind == "word":
            return self.consume().value
        raise QueryError(f"expected literal at position {t.pos}, got {t.value!r}")

    def _number(self) -> int | float:
        t = self.peek()
        if t is None or t.kind != "num":
            pos = t.pos if t else len(self.expr)
            raise QueryError(f"expected number at position {pos}")
        return self.consume().value


def _parse(expr: str) -> Node:
    tokens = _tokenise(expr)
    if not tokens:
        raise QueryError("empty expression")
    return _Parser(tokens, expr).parse()


# ---------------------------------------------------------- evaluator


def _row_field(row: ChapterRow, field: str) -> Any:
    return getattr(row, field, None)


def _eval_node(node: Node, row: ChapterRow) -> bool:
    if node.kind == "and":
        a, b = node.children
        return _eval_node(a, row) and _eval_node(b, row)
    if node.kind == "or":
        a, b = node.children
        return _eval_node(a, row) or _eval_node(b, row)
    if node.kind == "not":
        (sub,) = node.children
        return not _eval_node(sub, row)
    if node.kind == "cmp":
        field, op, lit = node.children
        value = _row_field(row, field)
        return _compare(value, op, lit)
    if node.kind == "contains":
        field, lit = node.children
        return _contains(_row_field(row, field), lit)
    if node.kind == "in_range":
        field, lo, hi = node.children
        value = _row_field(row, field)
        if value is None:
            return False
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False
        return lo <= v <= hi
    raise QueryError(f"unknown node kind: {node.kind}")


def _compare(value: Any, op: str, lit: Any) -> bool:
    if value is None:
        return op == "!="  # NULL != X is True; everything else False
    # Numeric comparison when both sides look numeric.
    try:
        a = float(value)
        b = float(lit)
        is_numeric = True
    except (TypeError, ValueError):
        is_numeric = False
    if is_numeric:
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
    # String comparison (lexicographic — works for ISO dates).
    s_value = str(value)
    s_lit = str(lit)
    if op == "==":
        return s_value == s_lit
    if op == "!=":
        return s_value != s_lit
    if op == "<":
        return s_value < s_lit
    if op == "<=":
        return s_value <= s_lit
    if op == ">":
        return s_value > s_lit
    if op == ">=":
        return s_value >= s_lit
    raise QueryError(f"unknown operator: {op}")


def _contains(value: Any, needle: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        s_needle = str(needle).lower()
        return any(s_needle in str(v).lower() for v in value)
    return str(needle).lower() in str(value).lower()


# ---------------------------------------------------------- render


def render_markdown(rows: list[ChapterRow], *, expr: str | None = None,
                     book: str | None = None) -> str:
    """Markdown table of the surviving rows. Mirrors
    chapter_summary.render_markdown_table's column order so users
    can correlate query output with the full table."""
    parts: list[str] = []
    if book:
        parts.append(f"# Summary query — {book}")
    else:
        parts.append("# Summary query")
    if expr:
        parts.append("")
        parts.append(f"_filter:_ `{expr}`")
    parts.append("")
    if not rows:
        parts.append(f"_No matching chapters._")
        return "\n".join(parts) + "\n"
    parts.append("| Ch | Date | POV | Score | Lowest | Words | Location | Plot |")
    parts.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        parts.append("| " + " | ".join([
            str(r.chapter),
            r.story_time or "—",
            r.pov or "—",
            f"{r.score:.1f}" if r.score is not None else "—",
            format_low(r.low_dim, r.low_score),
            str(r.word_count) if r.word_count is not None else "—",
            (r.location or "—").replace("|", "\\|"),
            (r.plot or "—").replace("|", "\\|"),
        ]) + " |")
    parts.append("")
    parts.append(f"_{len(rows)} chapter(s) matched._")
    return "\n".join(parts) + "\n"
