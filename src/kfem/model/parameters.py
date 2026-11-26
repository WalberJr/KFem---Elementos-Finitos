"""Parâmetros globais com expressões e unidades (Etapa 4)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from kfem.model.expressions import ExpressionError, constants, evaluate, free_symbols, parse


@dataclass
class Parameter:
    name: str
    expr: str
    description: str = ""
    group: str = "Parâmetros"

    def __post_init__(self) -> None:
        if not self.name.isidentifier():
            raise ExpressionError(f"nome de parâmetro inválido: '{self.name}'")
        parse(self.expr)  # valida a sintaxe já na criação


class CycleError(ExpressionError):
    pass


@dataclass
class ParameterSet:
    """Conjunto ordenado de parâmetros; os grupos servem só para organizar a interface."""

    params: dict[str, Parameter] = field(default_factory=dict)
    groups: list[str] = field(default_factory=lambda: ["Parâmetros"])

    def add(self, name: str, expr: str, description: str = "", group: str | None = None) -> Parameter:
        g = group or self.groups[0]
        if g not in self.groups:
            self.groups.append(g)
        p = Parameter(name, expr, description, g)
        self.params[name] = p
        return p

    def remove(self, name: str) -> None:
        self.params.pop(name, None)

    def rename(self, old: str, new: str) -> None:
        p = self.params.pop(old)
        p.name = new
        self.params[new] = p

    def in_group(self, group: str) -> list[Parameter]:
        return [p for p in self.params.values() if p.group == group]

    def order(self, extra_known: set[str] | None = None) -> list[str]:
        """Ordem topológica de avaliação. Ciclos ou símbolos desconhecidos geram erro claro."""
        known = set(constants()) | (extra_known or set())
        deps = {n: free_symbols(p.expr) for n, p in self.params.items()}
        for n, d in deps.items():
            unknown = d - known - set(self.params)
            if unknown:
                raise ExpressionError(f"parâmetro '{n}' usa símbolo(s) desconhecido(s): {', '.join(sorted(unknown))}")
        out: list[str] = []
        state: dict[str, int] = {}

        def visit(n: str, stack: list[str]) -> None:
            if state.get(n) == 2:
                return
            if state.get(n) == 1:
                cyc = [*stack[stack.index(n) :], n]
                raise CycleError("dependência circular: " + " → ".join(cyc))
            state[n] = 1
            for d in sorted(deps[n] & set(self.params)):
                visit(d, [*stack, n])
            state[n] = 2
            out.append(n)

        for n in self.params:
            visit(n, [])
        return out

    def evaluate(
        self,
        overrides: Mapping[str, Any] | None = None,
        functions: Mapping[str, Callable[..., Any]] | None = None,
        extra_symbols: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Valores (pint.Quantity) de todos os parâmetros. `overrides` serve às varreduras."""
        env: dict[str, Any] = {**constants(), **(extra_symbols or {})}
        overrides = dict(overrides or {})
        for n in self.order(set(extra_symbols or {})):
            if n in overrides:
                v = overrides[n]
                env[n] = evaluate(v, env, functions) if isinstance(v, str) else v
            else:
                try:
                    env[n] = evaluate(self.params[n].expr, env, functions)
                except ExpressionError as exc:
                    raise ExpressionError(f"parâmetro '{n}': {exc}") from exc
                except Exception as exc:  # erros de unidade do pint, divisão por zero…
                    raise ExpressionError(f"parâmetro '{n}' = {self.params[n].expr}: {exc}") from exc
        return {n: env[n] for n in self.params}

    def to_si(self, **kw: Any) -> dict[str, float]:
        """Valores numéricos em unidades SI de base (para o solver)."""
        return {n: float(q.to_base_units().magnitude) for n, q in self.evaluate(**kw).items()}
