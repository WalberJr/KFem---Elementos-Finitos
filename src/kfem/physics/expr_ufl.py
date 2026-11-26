"""Tradução das expressões do modelo (AST de `kfem.model.expressions`) para UFL.

- As unidades entre colchetes viram fatores de conversão para SI (ex.: `[mm]` → 1e-3).
- Parâmetros entram como números SI; campos (`cNa`, `phil`…) e variáveis do solver entram
  como objetos UFL.
- As verificações dimensionais ficam em `ParameterSet.evaluate`: aqui só há conversão.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any

import ufl

from kfem.model.expressions import BinOp, Call, ExpressionError, Neg, Node, Num, Sym, Unit, parse, unit

_UFL_FUNCS: dict[str, Callable[..., Any]] = {
    "sqrt": ufl.sqrt,
    "exp": ufl.exp,
    "log": ufl.ln,
    "sin": ufl.sin,
    "cos": ufl.cos,
    "tan": ufl.tan,
    "tanh": ufl.tanh,
    "abs": abs,
    "min": ufl.min_value,
    "max": ufl.max_value,
}


def si_factor(unit_text: str) -> float:
    """Fator que converte um valor na unidade dada para a unidade SI de base."""
    q = unit(unit_text)
    return float(q.to_base_units().magnitude)


def to_ufl(
    expr: str | Node,
    symbols: Mapping[str, Any],
    functions: Mapping[str, Callable[..., Any]] | None = None,
) -> Any:
    """`symbols`: nome → float (SI) ou expressão UFL. Devolve float ou expressão UFL."""
    node = parse(expr) if isinstance(expr, str) else expr
    funcs = {**_UFL_FUNCS, **(functions or {})}

    def ev(n: Node) -> Any:
        if isinstance(n, Num):
            return n.value
        if isinstance(n, Sym):
            if n.name in symbols:
                return symbols[n.name]
            if n.name == "pi":
                return math.pi
            raise ExpressionError(f"símbolo desconhecido no solver: {n.name}")
        if isinstance(n, Unit):
            return ev(n.expr) * si_factor(n.unit)
        if isinstance(n, Neg):
            return -ev(n.operand)
        if isinstance(n, Call):
            if n.func not in funcs:
                raise ExpressionError(f"função desconhecida no solver: {n.func}")
            return funcs[n.func](*[ev(a) for a in n.args])
        if isinstance(n, BinOp):
            a, b = ev(n.left), ev(n.right)
            match n.op:
                case "+":
                    return a + b
                case "-":
                    return a - b
                case "*":
                    return a * b
                case "/":
                    return a / b
                case "^":
                    return a**b
                case "<":
                    return ufl.conditional(ufl.lt(a, b), 1.0, 0.0)
                case "<=":
                    return ufl.conditional(ufl.le(a, b), 1.0, 0.0)
                case ">":
                    return ufl.conditional(ufl.gt(a, b), 1.0, 0.0)
                case ">=":
                    return ufl.conditional(ufl.ge(a, b), 1.0, 0.0)
                case "==":
                    return ufl.conditional(ufl.eq(a, b), 1.0, 0.0)
                case "!=":
                    return ufl.conditional(ufl.ne(a, b), 1.0, 0.0)
        raise ExpressionError(f"nó desconhecido: {n!r}")

    return ev(node)


def to_float(expr: str, symbols: Mapping[str, float]) -> float:
    v = to_ufl(expr, symbols)
    if isinstance(v, (int, float)):
        return float(v)
    raise ExpressionError(f"'{expr}' não é constante")
