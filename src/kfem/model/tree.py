"""Árvore do modelo (Etapa 4).

Estrutura (rótulos próprios do KFem; o fluxo árvore → configurações → gráficos é genérico):

    Modelo
    ├── Definições globais: parâmetros (grupos), funções
    ├── Componente (comp1, 2D/3D)
    │   ├── Definições: variáveis, sondas
    │   ├── Geometria: sequência de operações
    │   ├── Materiais
    │   ├── Físicas: interfaces, cada uma com nós de domínio e de contorno
    │   ├── Multifísica: acoplamentos
    │   └── Malha: sequência de operações
    ├── Estudos: passos (estacionário, transiente, varredura)
    └── Resultados: conjuntos de dados, gráficos, avaliações

Cada item da árvore é um `Node` genérico: `kind`, `tag`, `label`, `props` (valores ou
expressões em texto), `selection` (dimensão e entidades), `active` e `children`. Quais
`kind` existem e quais `props` cada um aceita fica nos catálogos de física, geometria e
estudo (`kfem.model.catalog`).
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from kfem.model.parameters import ParameterSet

ALL = "all"


@dataclass
class Selection:
    """dim: -1 = global, 0 = pontos, 1 = arestas/contornos 2D, 2 = superfícies/domínios 2D, 3 = volumes."""

    dim: int
    entities: list[int] | str = ALL  # ALL ou lista de marcadores (começando em 1)

    def to_dict(self) -> dict[str, Any]:
        return {"dim": self.dim, "entities": self.entities}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Selection:
        return cls(int(d["dim"]), d.get("entities", ALL))

    def resolve(self, available: list[int]) -> list[int]:
        return list(available) if self.entities == ALL else [e for e in self.entities if e in available]


@dataclass
class Node:
    kind: str
    tag: str
    label: str = ""
    props: dict[str, Any] = field(default_factory=dict)
    selection: Selection | None = None
    active: bool = True
    children: list[Node] = field(default_factory=list)

    def child(self, tag: str) -> Node:
        for c in self.children:
            if c.tag == tag:
                return c
        raise KeyError(f"'{self.tag}' não tem filho '{tag}'")

    def add(self, node: Node) -> Node:
        if any(c.tag == node.tag for c in self.children):
            raise ValueError(f"tag repetida em '{self.tag}': {node.tag}")
        self.children.append(node)
        return node

    def remove(self, tag: str) -> None:
        self.children = [c for c in self.children if c.tag != tag]

    def walk(self) -> Iterator[Node]:
        yield self
        for c in self.children:
            yield from c.walk()

    def active_children(self, kind_prefix: str = "") -> list[Node]:
        return [c for c in self.children if c.active and c.kind.startswith(kind_prefix)]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "tag": self.tag}
        if self.label:
            d["label"] = self.label
        if self.props:
            d["props"] = self.props
        if self.selection is not None:
            d["selection"] = self.selection.to_dict()
        if not self.active:
            d["active"] = False
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Node:
        return cls(
            kind=d["kind"],
            tag=d["tag"],
            label=d.get("label", ""),
            props=dict(d.get("props", {})),
            selection=Selection.from_dict(d["selection"]) if "selection" in d else None,
            active=bool(d.get("active", True)),
            children=[cls.from_dict(c) for c in d.get("children", [])],
        )


def unique_tag(siblings: list[Node], prefix: str) -> str:
    used = {c.tag for c in siblings}
    i = 1
    while f"{prefix}{i}" in used:
        i += 1
    return f"{prefix}{i}"


SECTIONS = ("definitions", "geometry", "materials", "physics", "multiphysics", "mesh")


@dataclass
class Component:
    tag: str = "comp1"
    label: str = "Componente 1"
    dim: int = 2
    length_unit: str = "mm"
    sections: dict[str, Node] = field(default_factory=dict)

    def __post_init__(self) -> None:
        titles = {
            "definitions": "Definições",
            "geometry": "Geometria",
            "materials": "Materiais",
            "physics": "Físicas",
            "multiphysics": "Multifísica",
            "mesh": "Malha",
        }
        for s in SECTIONS:
            self.sections.setdefault(s, Node(kind=f"section.{s}", tag=s, label=titles[s]))

    def __getattr__(self, name: str) -> Node:
        if name in SECTIONS:
            return self.sections[name]
        raise AttributeError(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "label": self.label,
            "dim": self.dim,
            "length_unit": self.length_unit,
            "sections": {k: v.to_dict() for k, v in self.sections.items()},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Component:
        c = cls(tag=d["tag"], label=d.get("label", ""), dim=int(d["dim"]), length_unit=d.get("length_unit", "m"))
        for k, v in d.get("sections", {}).items():
            c.sections[k] = Node.from_dict(v)
        return c


@dataclass
class Model:
    name: str = "Sem título"
    description: str = ""
    parameters: ParameterSet = field(default_factory=ParameterSet)
    functions: Node = field(default_factory=lambda: Node("section.functions", "functions", "Funções"))
    components: list[Component] = field(default_factory=lambda: [Component()])
    studies: Node = field(default_factory=lambda: Node("section.studies", "studies", "Estudos"))
    results: Node = field(default_factory=lambda: Node("section.results", "results", "Resultados"))
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def comp(self) -> Component:
        return self.components[0]

    def find(self, path: str) -> Node:
        """Caminho tipo 'comp1/physics/tds/in1', 'studies/std1/time' ou 'functions/step1'."""
        parts = [p for p in path.split("/") if p]
        if not parts:
            raise KeyError(path)
        if parts[0] in ("functions", "studies", "results"):
            node: Node = getattr(self, parts[0])
            rest = parts[1:]
        else:
            comp = next((c for c in self.components if c.tag == parts[0]), None)
            if comp is None or len(parts) < 2:
                raise KeyError(path)
            node = comp.sections[parts[1]]
            rest = parts[2:]
        for p in rest:
            node = node.child(p)
        return node

    def copy(self) -> Model:
        return copy.deepcopy(self)
