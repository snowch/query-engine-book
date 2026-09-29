"""From SQL text to a tree: the engine's parser, for the SQL the book's queries use (ch11).

A query arrives as text. The parser reads it in two steps. The **tokenizer** cuts the text into
tokens: words, numbers, strings, operators. The parser then reads the tokens by **recursive
descent**: one function for each kind of phrase in the grammar (a query, a table, an expression,
a term), each calling the functions for the phrases inside it. What comes out is the query's
syntax tree, :class:`Query`, which says what the text said and nothing more: which tables, which
columns, which conditions, in the order the text wrote them. Choosing how to run it is the
planner's job (:mod:`query_lab.planner`).

The grammar is the book's subset of SQL: ``SELECT`` with expressions and aliases, ``FROM`` a file
or ``read_parquet(...)``, with an alias, ``JOIN ... ON``, ``WHERE``, ``GROUP BY``, ``ORDER BY``
and ``LIMIT``. Expressions are ch06's trees (:mod:`query_lab.expressions`): columns, constants
and calls, with the precedence SQL gives ``OR``, ``AND``, ``NOT``, comparisons, ``+`` and ``-``,
then ``*`` and ``/``. Anything else is an error that names what the parser did not expect.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from .expressions import Call, Column, Expression, Literal


class SQLError(ValueError):
    """Text the parser cannot read: it names the token it did not expect, and where."""


@dataclass(frozen=True)
class Token:
    kind: str
    """``word``, ``number``, ``string``, ``op`` or ``end``."""
    text: str
    at: int
    """Where the token starts in the text: an error points at it."""


TOKEN = re.compile(
    r"""\s*(?:
        (?P<comment>--[^\n]*)
      | (?P<number>\d+\.\d*|\d*\.\d+|\d+)
      | (?P<string>'(?:[^']|'')*')
      | (?P<quoted>"(?:[^"]|"")*")
      | (?P<word>[A-Za-z_][A-Za-z_0-9]*)
      | (?P<op><=|>=|<>|!=|[-+*/=<>(),.;])
    )""",
    re.VERBOSE,
)

#: The words that are part of the grammar, not names: a column may not be called ``from``.
KEYWORDS = {
    "select", "from", "where", "group", "by", "order", "limit", "as", "join", "inner", "on",
    "and", "or", "not", "asc", "desc", "date", "true", "false", "null", "between", "in",
}  # fmt: skip


def tokenize(text: str) -> list[Token]:
    """The tokens of ``text``, comments dropped, ending with an ``end`` token."""
    tokens, at = [], 0
    while at < len(text):
        if not text[at:].strip():
            break
        m = TOKEN.match(text, at)
        if not m or m.end() == at:
            at = len(text) - len(text[at:].lstrip())
            raise SQLError(f"cannot read the text at character {at}: {text[at : at + 20]!r}")
        kind = m.lastgroup
        start = m.start(kind)
        if kind == "quoted":
            tokens.append(Token("word", m.group(kind)[1:-1].replace('""', '"'), start))
        elif kind != "comment":
            tokens.append(Token(kind, m.group(kind), start))
        at = m.end()
    tokens.append(Token("end", "", len(text)))
    return tokens


@dataclass(frozen=True)
class Table:
    """A table the query reads: a Parquet file or a glob of them, and the name the query gives it."""

    path: str
    alias: str
    options: tuple[tuple[str, object], ...] = ()
    """``read_parquet``'s named options, such as ``hive_partitioning = true``."""


@dataclass(frozen=True)
class Join:
    table: Table
    on: Expression


@dataclass(frozen=True)
class Item:
    """One item of the ``SELECT`` list: an expression, and the name it is handed up under."""

    expr: Expression
    alias: str | None = None


@dataclass
class Query:
    """What a ``SELECT`` says, part by part, as written."""

    items: list[Item]
    star: bool
    table: Table
    joins: list[Join] = field(default_factory=list)
    where: Expression | None = None
    group_by: list[Expression] = field(default_factory=list)
    order_by: list[tuple[Expression, bool]] = field(default_factory=list)
    """Each key, and whether it is descending."""
    limit: int | None = None


class Parser:
    """Recursive descent over the tokens: one method per phrase of the grammar."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = tokenize(text)
        self.at = 0

    # The tokens, one at a time.

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.at + offset, len(self.tokens) - 1)]

    def is_word(self, *words: str) -> bool:
        t = self.peek()
        return t.kind == "word" and t.text.lower() in words

    def is_op(self, *ops: str) -> bool:
        t = self.peek()
        return t.kind == "op" and t.text in ops

    def take(self) -> Token:
        t = self.peek()
        self.at += 1
        return t

    def expect_word(self, word: str) -> None:
        if not self.is_word(word):
            self.fail(f"expected {word.upper()}")
        self.take()

    def expect_op(self, op: str) -> None:
        if not self.is_op(op):
            self.fail(f"expected {op!r}")
        self.take()

    def fail(self, what: str):
        t = self.peek()
        found = "the end of the query" if t.kind == "end" else repr(t.text)
        raise SQLError(f"{what}, found {found} at character {t.at}")

    # The grammar, from the top.

    def query(self) -> Query:
        self.expect_word("select")
        star, items = False, []
        if self.is_op("*"):
            self.take()
            star = True
        else:
            items = [self.item()]
            while self.is_op(","):
                self.take()
                items.append(self.item())
        self.expect_word("from")
        q = Query(items, star, self.table())
        while self.is_word("join", "inner"):
            if self.is_word("inner"):
                self.take()
            self.expect_word("join")
            joined = self.table()
            self.expect_word("on")
            q.joins.append(Join(joined, self.expr()))
        if self.is_word("where"):
            self.take()
            q.where = self.expr()
        if self.is_word("group"):
            self.take()
            self.expect_word("by")
            q.group_by = self.list_of(self.expr)
        if self.is_word("order"):
            self.take()
            self.expect_word("by")
            q.order_by = self.list_of(self.order_key)
        if self.is_word("limit"):
            self.take()
            t = self.take()
            if t.kind != "number" or not t.text.isdigit():
                self.at -= 1
                self.fail("expected a whole number after LIMIT")
            q.limit = int(t.text)
        if self.is_op(";"):
            self.take()
        if self.peek().kind != "end":
            self.fail("expected the end of the query")
        return q

    def list_of(self, phrase):
        out = [phrase()]
        while self.is_op(","):
            self.take()
            out.append(phrase())
        return out

    def item(self) -> Item:
        expr = self.expr()
        alias = None
        if self.is_word("as"):
            self.take()
            alias = self.name()
        elif self.peek().kind == "word" and self.peek().text.lower() not in KEYWORDS:
            alias = self.name()
        return Item(expr, alias)

    def order_key(self) -> tuple[Expression, bool]:
        expr = self.expr()
        descending = False
        if self.is_word("asc", "desc"):
            descending = self.take().text.lower() == "desc"
        return expr, descending

    def name(self) -> str:
        t = self.peek()
        if t.kind != "word" or t.text.lower() in KEYWORDS:
            self.fail("expected a name")
        return self.take().text

    def table(self) -> Table:
        options: list[tuple[str, object]] = []
        t = self.peek()
        if t.kind == "string":
            path = self.string()
        elif self.is_word("read_parquet"):
            self.take()
            self.expect_op("(")
            path = self.string()
            while self.is_op(","):
                self.take()
                key = self.name()
                self.expect_op("=")
                options.append((key.lower(), self.literal_value()))
            self.expect_op(")")
        else:
            self.fail("expected a file, as a string, or read_parquet(...)")
        alias = path
        if self.is_word("as"):
            self.take()
            alias = self.name()
        elif self.peek().kind == "word" and self.peek().text.lower() not in KEYWORDS:
            alias = self.name()
        return Table(path, alias, tuple(options))

    def string(self) -> str:
        t = self.take()
        if t.kind != "string":
            self.at -= 1
            self.fail("expected a string")
        return t.text[1:-1].replace("''", "'")

    def literal_value(self) -> object:
        expr = self.primary()
        if not isinstance(expr, Literal):
            self.fail("expected a constant")
        return expr.value

    # Expressions, loosest binding first: each level calls the next for its operands.

    def expr(self) -> Expression:
        return self.disjunction()

    def disjunction(self) -> Expression:
        left = self.conjunction()
        while self.is_word("or"):
            self.take()
            left = Call("or", (left, self.conjunction()))
        return left

    def conjunction(self) -> Expression:
        left = self.negation()
        while self.is_word("and"):
            self.take()
            left = Call("and", (left, self.negation()))
        return left

    def negation(self) -> Expression:
        if self.is_word("not"):
            self.take()
            return Call("not", (self.negation(),))
        return self.comparison()

    def comparison(self) -> Expression:
        left = self.sum()
        if self.is_op("=", "!=", "<>", "<", "<=", ">", ">="):
            op = self.take().text
            left = Call("!=" if op == "<>" else op, (left, self.sum()))
        return left

    def sum(self) -> Expression:
        left = self.product()
        while self.is_op("+", "-"):
            op = self.take().text
            left = Call(op, (left, self.product()))
        return left

    def product(self) -> Expression:
        left = self.unary()
        while self.is_op("*", "/"):
            op = self.take().text
            left = Call(op, (left, self.unary()))
        return left

    def unary(self) -> Expression:
        if self.is_op("-"):
            self.take()
            operand = self.unary()
            if isinstance(operand, Literal) and isinstance(operand.value, int | float):
                return Literal(-operand.value)
            return Call("-", (Literal(0), operand))
        return self.primary()

    def primary(self) -> Expression:
        t = self.peek()
        if t.kind == "number":
            self.take()
            return Literal(float(t.text) if "." in t.text else int(t.text))
        if t.kind == "string":
            return Literal(self.string())
        if self.is_op("("):
            self.take()
            inner = self.expr()
            self.expect_op(")")
            return inner
        if self.is_word("date"):
            self.take()
            text = self.string()
            try:
                return Literal(dt.date.fromisoformat(text))
            except ValueError:
                self.at -= 1
                self.fail(f"expected a date as YYYY-MM-DD, not {text!r}")
        if self.is_word("true", "false"):
            return Literal(self.take().text.lower() == "true")
        if t.kind == "word" and t.text.lower() not in KEYWORDS:
            name = self.take().text
            if self.is_op("("):
                return self.call(name.lower())
            if self.is_op("."):
                self.take()
                return Column(f"{name}.{self.name()}")
            return Column(name)
        self.fail("expected a value, a column or '('")

    def call(self, function: str) -> Expression:
        self.expect_op("(")
        if function == "count" and self.is_op("*"):
            self.take()
            self.expect_op(")")
            return Call("count", ())
        args = [] if self.is_op(")") else self.list_of(self.expr)
        self.expect_op(")")
        return Call(function, tuple(args))


def parse(text: str) -> Query:
    """The syntax tree of one ``SELECT``."""
    return Parser(text).query()
