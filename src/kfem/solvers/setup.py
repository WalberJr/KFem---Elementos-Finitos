"""Preparação comum aos estudos: parâmetros SI, funções, malha, marcadores e materiais."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from kfem.model.expressions import constants
from kfem.model.tree import ALL, Model, Node
from kfem.physics.expr_ufl import to_float, to_ufl


def smooth_step_float(x: float, loc: float, y0: float, y1: float, width: float) -> float:
    """Degrau suave C² (polinômio de grau 5) entre loc−w/2 e loc+w/2. Implementação própria."""
    if width <= 0:
        return y1 if x >= loc else y0
    s = (x - (loc - width / 2)) / width
    s = min(max(s, 0.0), 1.0)
    return y0 + (y1 - y0) * s**3 * (10 - 15 * s + 6 * s**2)


def model_functions(model: Model, si: dict[str, float]) -> dict[str, Callable[..., Any]]:
    out: dict[str, Callable[..., Any]] = {}
    for f in model.functions.active_children():
        if f.kind == "func.step":
            loc = to_float(f.props["location"], si)
            y0 = to_float(f.props["from"], si)
            y1 = to_float(f.props["to"], si)
            w = to_float(f.props["smooth"], si)

            def step(x: Any, loc: float = loc, y0: float = y0, y1: float = y1, w: float = w) -> Any:
                if isinstance(x, (int, float)):
                    return smooth_step_float(float(x), loc, y0, y1, w)
                import ufl

                s = ufl.min_value(ufl.max_value((x - (loc - w / 2)) / max(w, 1e-300), 0.0), 1.0)
                return y0 + (y1 - y0) * s**3 * (10 - 15 * s + 6 * s**2)

            out[f.tag] = step
    return out


def parameters_si(model: Model, overrides: dict[str, Any] | None = None) -> dict[str, float]:
    si = {k: float(v.to_base_units().magnitude) for k, v in constants().items()}
    si.update(model.parameters.to_si(overrides=overrides))
    return si


def parse_tlist(text: str, si: dict[str, float]) -> list[float]:
    """'range(0,5,50) range(55,15,2000)' (início, passo, fim) ou números separados por espaço."""
    out: list[float] = []
    for m in re.finditer(r"range\(([^)]*)\)|([^\s]+)", text):
        if m.group(1) is not None:
            a, st, b = (to_float(x.strip(), si) for x in m.group(1).split(","))
            n = math.floor((b - a) / st + 1e-9) + 1
            out += [a + i * st for i in range(n)]
            if out[-1] < b - 1e-9 * max(1.0, abs(b)):
                out.append(b)
        else:
            out.append(to_float(m.group(2), si))
    return sorted(set(round(t, 12) for t in out))


def resolve(nodes: list[Node], markers: list[int], kinds: tuple[str, ...]) -> dict[int, Node]:
    """Para cada marcador, o último nó ativo (de um dos `kinds`) cuja seleção o contém.

    A regra é a da árvore: nós mais abaixo têm prioridade sobre os de cima.
    """
    out: dict[int, Node] = {}
    for n in nodes:
        if not n.active or n.kind not in kinds or n.selection is None:
            continue
        ents = markers if n.selection.entities == ALL else [e for e in n.selection.entities if e in markers]
        for e in ents:
            out[e] = n
    return out


@dataclass
class MeshData:
    mesh: Any
    cell_tags: Any
    facet_tags: Any
    domains: list[int]
    boundaries: list[int]
    exterior: list[int]
    areas: dict[int, float] = field(default_factory=dict)


def build_mesh(model: Model, si: dict[str, float], comm: Any, log: Callable[[str], None] = print) -> MeshData:
    """Geometria + malha (gmsh no rank 0) → DOLFINx distribuída."""
    from dolfinx import mesh as dmesh

    from kfem.geometry.build import generate, to_dolfinx

    env = {**constants(), **model.parameters.evaluate()}
    geo = None
    if comm.rank == 0:
        geo = generate(model, env)
        log(f"geometria: {len(geo.domains)} domínios, {len(geo.boundaries)} contornos")
    geo = comm.bcast(geo, root=0)
    md = to_dolfinx(comm, geo, rank=0)
    msh, ct, ft = md.mesh, md.cell_tags, md.facet_tags
    if comm.rank == 0:
        import gmsh

        gmsh.finalize()
    tdim = msh.topology.dim
    msh.topology.create_connectivity(tdim - 1, tdim)
    ext = set(dmesh.exterior_facet_indices(msh.topology).tolist())
    ext_markers = sorted({int(v) for f, v in zip(ft.indices, ft.values, strict=True) if int(f) in ext})
    ext_markers = sorted(set(comm.allgather(ext_markers)[0]).union(*comm.allgather(ext_markers)))
    ncell = comm.allreduce(msh.topology.index_map(tdim).size_local, op=__import__("mpi4py").MPI.SUM)
    log(f"malha: {ncell} células, {comm.size} processo(s) MPI")
    return MeshData(msh, ct, ft, sorted(geo.domains), sorted(geo.boundaries), ext_markers, geo.areas)


class Materials:
    """Valores de propriedades por domínio (`mat:nome`), como UFL por partes (indicadores DG0)."""

    def __init__(self, model: Model, md: MeshData) -> None:
        from dolfinx import fem

        self.by_domain: dict[int, dict[str, str]] = {}
        self.by_tag: dict[str, dict[str, str]] = {}
        for mat in model.comp.materials.active_children():
            self.by_tag[mat.tag] = dict(mat.props.get("properties", {}))
            sel = mat.selection.entities if mat.selection else ALL
            ents = md.domains if sel == ALL else [e for e in sel if e in md.domains]
            for d in ents:
                self.by_domain.setdefault(d, {}).update(mat.props.get("properties", {}))
        V0 = fem.functionspace(md.mesh, ("DG", 0))
        self.chi: dict[int, Any] = {}
        for d in md.domains:
            f = fem.Function(V0)
            cells = md.cell_tags.find(d)
            f.x.array[:] = 0.0
            f.x.array[cells] = 1.0
            f.x.scatter_forward()
            self.chi[d] = f

    def material_value(self, tag: str, prop: str, symbols: dict[str, Any]) -> Any:
        if tag not in self.by_tag or prop not in self.by_tag[tag]:
            raise KeyError(f"material '{tag}' não define '{prop}'")
        return to_ufl(self.by_tag[tag][prop], symbols)

    def piecewise(self, per_domain: dict[int, Any]) -> Any:
        """Soma Σ χ_d · valor_d (UFL)."""
        total: Any = 0.0
        for d, v in per_domain.items():
            total = total + self.chi[d] * v
        return total

    def value(self, prop: str, domain: int, symbols: dict[str, Any]) -> Any:
        props = self.by_domain.get(domain, {})
        if prop not in props:
            raise KeyError(f"material do domínio {domain} não define '{prop}'")
        return to_ufl(props[prop], symbols)

    def resolve_prop(self, text: Any, domain: int, symbols: dict[str, Any]) -> Any:
        """Valor de propriedade de nó: 'mat:xxx' (do material) ou expressão."""
        if isinstance(text, str) and text.startswith("mat:"):
            return self.value(text[4:], domain, symbols)
        return to_ufl(str(text), symbols)


def boundary_normal(md: MeshData, marker: int) -> np.ndarray:
    """Normal externa média de um contorno marcado (para entradas com velocidade normal)."""
    from mpi4py import MPI

    msh = md.mesh
    tdim = msh.topology.dim
    fdim = tdim - 1
    facets = md.facet_tags.find(marker)
    msh.topology.create_connectivity(fdim, 0)
    msh.topology.create_connectivity(fdim, tdim)
    f2v = msh.topology.connectivity(fdim, 0)
    f2c = msh.topology.connectivity(fdim, tdim)
    x = msh.geometry.x
    from dolfinx.mesh import entities_to_geometry

    acc = np.zeros(3)
    for f in facets:
        gv = entities_to_geometry(msh, fdim, np.array([f], dtype=np.int32))[0]
        p = x[gv]
        if tdim == 2:
            t = p[1] - p[0]
            n = np.array([t[1], -t[0], 0.0])
        else:
            n = np.cross(p[1] - p[0], p[2] - p[0])
        c = f2c.links(f)[0]
        cg = entities_to_geometry(msh, tdim, np.array([c], dtype=np.int32))[0]
        if np.dot(n, p.mean(axis=0) - x[cg].mean(axis=0)) < 0:
            n = -n
        acc += n
        _ = f2v
    acc = msh.comm.allreduce(acc, op=MPI.SUM)
    nrm = np.linalg.norm(acc)
    return acc / nrm if nrm > 0 else acc
