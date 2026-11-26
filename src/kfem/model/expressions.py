"""Expressões com unidades, avaliadas de forma segura (sem `eval`) — Etapa 4.

Sintaxe (compatível com a usada nos arquivos do usuário):
- números `1.5e-3`; identificadores `te`, `F_const`; operadores `+ - * / ^`; parênteses;
- unidade pós-fixa entre colchetes, que **multiplica** a expressão anterior:
  `100 [mm]`, `t[1/s]`, `20.01 [F/g]*mass`;
- chamadas de função `sqrt(x)`, `step1(t[1/s])`;
- comparações `< <= > >= == !=`, que valem 1 ou 0. Servem para chaves tipo `(ON>0)`.

`parse()` devolve uma AST imutável. `free_symbols()` lista as dependências, e `evaluate()`
calcula o valor com o `UnitRegistry` do pint.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Union

# --------------------------------------------------------------------------- AST


@dataclass(frozen=True)
class Num:
    value: float


@dataclass(frozen=True)
class Sym:
    name: str


@dataclass(frozen=True)
class Unit:
    """Expressão multiplicada por uma unidade (texto da unidade, sem colchetes)."""

    expr: Node
    unit: str


@dataclass(frozen=True)
class BinOp:
    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Neg:
    operand: Node


@dataclass(frozen=True)
class Call:
    func: str
    args: tuple[Node, ...]


Node = Union[Num, Sym, Unit, BinOp, Neg, Call]  # noqa: UP007


class ExpressionError(ValueError):
    pass


# ----------------------------------------------------------------------- tokenizer

_TOKEN = re.compile(
    r"\s*(?:"
    r"(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<unit>\[[^\]]*\])"
    r"|(?P<id>[A-Za-z_][A-Za-z_0-9.]*)"
    r"|(?P<op><=|>=|==|!=|[-+*/^(),<>])"
    r")"
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    pos, out = 0, []
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise ExpressionError(f"caractere inesperado em '{text}' na posição {pos}: '{text[pos]}'")
        kind = m.lastgroup
        assert kind is not None
        out.append((kind, m.group(kind)))
        pos = m.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return out


# -------------------------------------------------------------------------- parser

_CMP = ("<", "<=", ">", ">=", "==", "!=")


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0

    def peek(self) -> tuple[str, str] | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, value: str | None = None) -> tuple[str, str]:
        t = self.peek()
        if t is None or (value is not None and t[1] != value):
            raise ExpressionError(f"esperado '{value or 'expressão'}' em '{self.text}'")
        self.i += 1
        return t

    def parse(self) -> Node:
        if not self.toks:
            raise ExpressionError("expressão vazia")
        node = self.comparison()
        if self.peek() is not None:
            raise ExpressionError(f"sobra '{self.peek()[1]}' em '{self.text}'")  # type: ignore[index]
        return node

    def comparison(self) -> Node:
        node = self.additive()
        while (t := self.peek()) and t[1] in _CMP:
            self.take()
            node = BinOp(t[1], node, self.additive())
        return node

    def additive(self) -> Node:
        node = self.term()
        while (t := self.peek()) and t[1] in "+-" and t[0] == "op":
            self.take()
            node = BinOp(t[1], node, self.term())
        return node

    def term(self) -> Node:
        node = self.unary()
        while (t := self.peek()) and t[0] == "op" and t[1] in "*/":
            self.take()
            node = BinOp(t[1], node, self.unary())
        return node

    def unary(self) -> Node:
        t = self.peek()
        if t and t[0] == "op" and t[1] in "+-":
            self.take()
            inner = self.unary()
            return Neg(inner) if t[1] == "-" else inner
        return self.power()

    def power(self) -> Node:
        base = self.postfix()
        t = self.peek()
        if t and t[1] == "^":
            self.take()
            return BinOp("^", base, self.unary())  # associativo à direita, aceita 2^-1
        return base

    def postfix(self) -> Node:
        node = self.atom()
        while (t := self.peek()) and t[0] == "unit":
            self.take()
            node = Unit(node, t[1][1:-1].strip())
        return node

    def atom(self) -> Node:
        t = self.take()
        kind, val = t
        if kind == "num":
            return Num(float(val))
        if kind == "unit":  # unidade sozinha: "[mm]" = 1 mm
            return Unit(Num(1.0), val[1:-1].strip())
        if kind == "id":
            nxt = self.peek()
            if nxt and nxt[1] == "(":
                self.take("(")
                args: list[Node] = []
                if self.peek() and self.peek()[1] != ")":  # type: ignore[index]
                    args.append(self.comparison())
                    while self.peek() and self.peek()[1] == ",":  # type: ignore[index]
                        self.take(",")
                        args.append(self.comparison())
                self.take(")")
                return Call(val, tuple(args))
            return Sym(val)
        if val == "(":
            node = self.comparison()
            self.take(")")
            return node
        raise ExpressionError(f"token inesperado '{val}' em '{self.text}'")


_cache: dict[str, Node] = {}


def parse(text: str) -> Node:
    if text not in _cache:
        _cache[text] = _Parser(text).parse()
    return _cache[text]


def free_symbols(node: Node | str) -> set[str]:
    if isinstance(node, str):
        node = parse(node)
    if isinstance(node, Sym):
        return {node.name}
    if isinstance(node, Unit):
        return free_symbols(node.expr)
    if isinstance(node, Neg):
        return free_symbols(node.operand)
    if isinstance(node, BinOp):
        return free_symbols(node.left) | free_symbols(node.right)
    if isinstance(node, Call):
        out: set[str] = set()
        for a in node.args:
            out |= free_symbols(a)
        return out
    return set()


def called_functions(node: Node | str) -> set[str]:
    if isinstance(node, str):
        node = parse(node)
    if isinstance(node, Call):
        out = {node.func}
        for a in node.args:
            out |= called_functions(a)
        return out
    if isinstance(node, Unit):
        return called_functions(node.expr)
    if isinstance(node, Neg):
        return called_functions(node.operand)
    if isinstance(node, BinOp):
        return called_functions(node.left) | called_functions(node.right)
    return set()


# ---------------------------------------------------------------------- avaliação

_ureg: Any = None


def ureg() -> Any:
    """UnitRegistry compartilhado (pint), com as grafias usadas nos modelos."""
    global _ureg
    if _ureg is None:
        import pint

        r = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
        r.define("mM = millimole / liter")
        _ureg = r
    return _ureg


_unit_cache: dict[str, Any] = {}


def unit(text: str) -> Any:
    """Converte o texto de uma unidade ('mm', 'm^2/s', 'L/min', '1/s') em Quantity de valor 1."""
    if text not in _unit_cache:
        t = text.replace("^", "**").strip()
        q = ureg().Quantity(1.0, "") if t in ("", "1") else ureg().parse_expression(t)
        if not hasattr(q, "units"):
            q = ureg().Quantity(float(q), "")
        _unit_cache[text] = q
    return _unit_cache[text]


def _pint_math(name: str) -> Callable[..., Any]:
    def f(x: Any) -> Any:
        q = x.to("dimensionless") if hasattr(x, "to") else x
        v = q.magnitude if hasattr(q, "magnitude") else q
        return ureg().Quantity(getattr(math, name)(float(v)), "dimensionless")

    return f


def _sqrt(x: Any) -> Any:
    return x**0.5


def _abs(x: Any) -> Any:
    return abs(x)


BUILTIN_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "sqrt": _sqrt,
    "abs": _abs,
    "exp": _pint_math("exp"),
    "log": _pint_math("log"),
    "log10": _pint_math("log10"),
    "sin": _pint_math("sin"),
    "cos": _pint_math("cos"),
    "tan": _pint_math("tan"),
    "tanh": _pint_math("tanh"),
    "min": lambda a, b: a if a <= b else b,
    "max": lambda a, b: a if a >= b else b,
}


def constants() -> dict[str, Any]:
    """Constantes físicas (CODATA 2018, valores exatos do SI quando definidos)."""
    Q = ureg().Quantity
    return {
        "pi": Q(math.pi, ""),
        "F_const": Q(96485.33212, "C/mol"),
        "R_const": Q(8.314462618, "J/(mol*K)"),
        "N_A_const": Q(6.02214076e23, "1/mol"),
        "k_B_const": Q(1.380649e-23, "J/K"),
        "e_const": Q(1.602176634e-19, "C"),
        "epsilon0_const": Q(8.8541878128e-12, "F/m"),
        "g_const": Q(9.80665, "m/s^2"),
    }


def evaluate(
    node: Node | str,
    symbols: Mapping[str, Any],
    functions: Mapping[str, Callable[..., Any]] | None = None,
) -> Any:
    """Avalia a expressão. `symbols` mapeia nome -> Quantity (pint) ou número."""
    if isinstance(node, str):
        node = parse(node)
    Q = ureg().Quantity
    funcs = {**BUILTIN_FUNCTIONS, **(functions or {})}

    def ev(n: Node) -> Any:
        if isinstance(n, Num):
            return Q(n.value, "")
        if isinstance(n, Sym):
            if n.name not in symbols:
                raise ExpressionError(f"símbolo desconhecido: {n.name}")
            v = symbols[n.name]
            return v if hasattr(v, "units") else Q(float(v), "")
        if isinstance(n, Unit):
            return ev(n.expr) * unit(n.unit)
        if isinstance(n, Neg):
            return -ev(n.operand)
        if isinstance(n, Call):
            if n.func not in funcs:
                raise ExpressionError(f"função desconhecida: {n.func}")
            return funcs[n.func](*[ev(a) for a in n.args])
        if isinstance(n, BinOp):
            a, b = ev(n.left), ev(n.right)
            if n.op == "+":
                return a + b
            if n.op == "-":
                return a - b
            if n.op == "*":
                return a * b
            if n.op == "/":
                return a / b
            if n.op == "^":
                exp = b.to("dimensionless").magnitude
                return a ** float(exp)
            res = {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b}[n.op]
            return Q(1.0 if res else 0.0, "")
        raise ExpressionError(f"nó desconhecido: {n!r}")

    return ev(node)


def to_text(node: Node) -> str:
    """Reescreve a AST como texto (com parênteses mínimos seguros)."""
    if isinstance(node, Num):
        return repr(node.value).removesuffix(".0") if node.value == int(node.value) else repr(node.value)
    if isinstance(node, Sym):
        return node.name
    if isinstance(node, Unit):
        return f"{to_text(node.expr)}[{node.unit}]"
    if isinstance(node, Neg):
        return f"-({to_text(node.operand)})"
    if isinstance(node, Call):
        return f"{node.func}({', '.join(to_text(a) for a in node.args)})"
    return f"({to_text(node.left)}{node.op}{to_text(node.right)})"
