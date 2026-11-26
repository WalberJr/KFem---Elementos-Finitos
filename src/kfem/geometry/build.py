"""Geometria e malha via Gmsh (kernel OCC) → DOLFINx (Etapa 5).

Numeração dos marcadores:
- Domínios e contornos recebem números estáveis pela ordem lexicográfica do canto inferior
  da caixa envolvente: x mínimo, depois y, depois z. No empate, a entidade "vertical" vem
  antes, isto é, a de menor extensão em x.
- É a mesma ordem observada nos arquivos `.mph` (ver `docs/mph-format/`). Com isso, as
  seleções importadas apontam para as mesmas entidades.

Todas as coordenadas são convertidas para metros: a unidade de comprimento do componente
define o fator de escala.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kfem.model.expressions import evaluate
from kfem.model.tree import ALL, Model, Node

LENGTH_FACTORS = {"m": 1.0, "mm": 1e-3, "cm": 1e-2, "um": 1e-6, "µm": 1e-6, "km": 1e3}


@dataclass
class GeometryResult:
    domains: dict[int, int] = field(default_factory=dict)  # marcador KFem -> tag gmsh (superfície/volume)
    boundaries: dict[int, int] = field(default_factory=dict)  # marcador KFem -> tag gmsh (curva/superfície)
    areas: dict[int, float] = field(default_factory=dict)  # marcador -> área/volume (m², m³)
    dim: int = 2
    scale: float = 1.0


def _num(expr: str, env: dict[str, Any], scale: float) -> float:
    """Avalia uma coordenada: sem unidade, vale a unidade da geometria; com unidade, converte."""
    q = evaluate(str(expr), env)
    if q.dimensionless:
        return float(q.magnitude) * scale
    return float(q.to("m").magnitude)


def _points(text: str, env: dict[str, Any], scale: float) -> list[tuple[float, float]]:
    """Vértices "x1 y1; x2 y2; ..." (vírgula também separa x de y)."""
    out = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.replace(",", " ").split()
        if len(parts) != 2:
            raise ValueError(f"vértice inválido: '{chunk}' (use 'x y; x y; ...')")
        out.append((_num(parts[0], env, scale), _num(parts[1], env, scale)))
    return out


def _sort_key(bbox: tuple[float, ...], tol: float) -> tuple[float, ...]:
    xmin, ymin, zmin, xmax, ymax, zmax = bbox

    def r(v: float) -> float:
        return round(v / tol)

    vertical = 0 if abs(xmax - xmin) < tol else 1
    return (r(xmin), r(ymin), r(zmin), vertical, r(xmax), r(ymax), r(zmax))


def numbered(gmsh: Any, dim: int, tol: float) -> dict[int, int]:
    ents = [t for d, t in gmsh.model.getEntities(dim)]
    keyed = sorted(ents, key=lambda t: _sort_key(gmsh.model.getBoundingBox(dim, t), tol))
    return {i + 1: t for i, t in enumerate(keyed)}


def build_geometry(gmsh: Any, model: Model, env: dict[str, Any]) -> GeometryResult:
    """Cria a geometria no modelo gmsh ativo a partir da sequência do componente."""
    comp = model.comp
    scale = LENGTH_FACTORS.get(comp.length_unit, 1.0)
    # constrói na unidade do componente e só no fim escala para metros: o OCC tem tolerância
    # geométrica absoluta (~1e-7), que em metros apagaria detalhes micrométricos
    m_scale = scale

    def U(expr: str) -> float:
        return _num(expr, env, m_scale) / m_scale

    occ = gmsh.model.occ
    dim = comp.dim
    objects: list[tuple[int, int]] = []
    lengths: list[float] = []
    named: dict[str, list[tuple[int, int]]] = {}  # tag do nó -> entidades que ele criou

    def take(tags: list[str], who: str) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for t in tags:
            if t not in named:
                raise ValueError(f"{who}: objeto '{t}' não existe (ou já foi consumido)")
            out += named.pop(t)
        return out

    for node in comp.geometry.active_children():
        p = node.props
        n_before = len(objects)
        if node.kind == "geom.polygon":
            pts = [(x / m_scale, y / m_scale) for x, y in _points(str(p["points"]), env, m_scale)]
            if len(pts) < 3:
                raise ValueError(f"{node.tag}: o polígono precisa de pelo menos 3 vértices")
            ptags = [occ.addPoint(x, y, 0.0) for x, y in pts]
            lines = [occ.addLine(ptags[i], ptags[(i + 1) % len(ptags)]) for i in range(len(ptags))]
            objects.append((2, occ.addPlaneSurface([occ.addCurveLoop(lines)])))
            xs, ys = [q[0] for q in pts], [q[1] for q in pts]
            lengths += [max(xs) - min(xs), max(ys) - min(ys)]
        elif node.kind in ("geom.difference", "geom.intersection"):
            occ.synchronize()
            if node.kind == "geom.difference":
                obj = take(list(p.get("add", [])), node.tag)
                tool = take(list(p.get("subtract", [])), node.tag)
                out, _ = occ.cut(obj, tool, removeObject=True, removeTool=True)
            else:
                ents = take(list(p.get("objects", [])), node.tag)
                if len(ents) < 2:
                    raise ValueError(f"{node.tag}: a interseção precisa de pelo menos 2 objetos")
                out, _ = occ.intersect(ents[:1], ents[1:], removeObject=True, removeTool=True)
            occ.synchronize()
            alive = {t for _, t in gmsh.model.getEntities(dim)}
            objects = [o for o in objects if o[1] in alive and o not in out] + list(out)
            named[node.tag] = list(out)
            continue
        elif node.kind == "geom.rectangle":
            x, y = U(p["x"]), U(p["y"])
            w, h = U(p["width"]), U(p["height"])
            objects.append((2, occ.addRectangle(x, y, 0.0, w, h)))
            lengths += [abs(w), abs(h)]
        elif node.kind == "geom.disk":
            r = U(p["r"])
            objects.append((2, occ.addDisk(U(p["x"]), U(p["y"]), 0.0, r, r)))
            lengths.append(2 * r)
        elif node.kind == "geom.box":
            vals = [U(p[k]) for k in ("x", "y", "z", "dx", "dy", "dz")]
            objects.append((3, occ.addBox(*vals)))
            lengths += vals[3:]
        elif node.kind == "geom.form_union":
            if len(objects) > 1:
                out, _ = occ.fragment(objects[:1], objects[1:])
                objects = list(out)
            occ.synchronize()
        elif node.kind == "geom.ignore_edges":
            occ.synchronize()
            tol = 1e-6 * max(lengths or [1.0])
            numbering = numbered(gmsh, dim - 1, tol)
            centers = []
            for e in node.props.get("edges", []):
                ctag = numbering.get(int(e))
                if ctag is None:
                    raise ValueError(f"{node.tag}: aresta {e} não existe (há {len(numbering)})")
                bb = gmsh.model.getBoundingBox(dim - 1, ctag)
                centers.append(((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2))
            # os tags mudam a cada fusão: localiza a aresta pelo centro, que não muda
            for cx, cy, cz in centers:
                cand = []
                for _, t in gmsh.model.getEntities(dim - 1):
                    pt, _ = gmsh.model.getClosestPoint(dim - 1, t, [cx, cy, cz])
                    if (pt[0] - cx) ** 2 + (pt[1] - cy) ** 2 + (pt[2] - cz) ** 2 < tol**2:
                        cand.append(t)
                if not cand:
                    continue
                up, _ = gmsh.model.getAdjacencies(dim - 1, cand[0])
                faces = [(dim, int(t)) for t in up]
                if len(faces) == 2:
                    occ.fuse([faces[0]], [faces[1]], removeObject=True, removeTool=True)
                    occ.synchronize()
            # a fusão deixa os outros contornos intactos; refaz o conjunto de objetos
            objects = list(gmsh.model.getEntities(dim))
            occ.removeAllDuplicates()
        else:
            raise ValueError(f"operação de geometria não suportada: {node.kind}")
        if node.kind in ("geom.rectangle", "geom.disk", "geom.box", "geom.polygon"):
            named[node.tag] = objects[n_before:]
        else:
            named.clear()  # união/remoção de arestas renumeram tudo
    occ.synchronize()
    if m_scale != 1.0:
        occ.dilate(gmsh.model.getEntities(dim), 0.0, 0.0, 0.0, m_scale, m_scale, m_scale)
        occ.synchronize()
    scale = m_scale
    tol = 1e-6 * max(lengths or [1.0]) * scale
    res = GeometryResult(dim=dim, scale=scale)
    res.domains = numbered(gmsh, dim, tol)
    res.boundaries = numbered(gmsh, dim - 1, tol)
    for mk, tag in res.domains.items():
        res.areas[mk] = float(occ.getMass(dim, tag))
        gmsh.model.addPhysicalGroup(dim, [tag], tag=mk, name=f"dom{mk}")
    for mk, tag in res.boundaries.items():
        gmsh.model.addPhysicalGroup(dim - 1, [tag], tag=mk, name=f"bnd{mk}")
    return res


def _sel_tags(node: Node, mapping: dict[int, int]) -> list[int]:
    if node.selection is None or node.selection.entities == ALL:
        return list(mapping.values())
    return [mapping[e] for e in node.selection.entities if e in mapping]


def apply_mesh_settings(gmsh: Any, model: Model, env: dict[str, Any], geo: GeometryResult) -> None:
    """Tamanhos global e local, gradação e camadas-limite (valores na unidade da geometria)."""
    opt = gmsh.option
    s = geo.scale * float(model.meta.get("mesh_scale", 1.0))
    fields: list[int] = []
    hmax_global = None
    for node in model.comp.mesh.active_children():
        p = node.props
        if node.kind == "mesh.size":
            hmax_global = _num(p["hmax"], env, s)
            opt.setNumber("Mesh.MeshSizeMax", hmax_global)
            opt.setNumber("Mesh.MeshSizeMin", _num(p["hmin"], env, s))
            opt.setNumber("Mesh.MeshSizeFromCurvature", 0)
        elif node.kind == "mesh.size_local":
            curves = _sel_tags(node, geo.boundaries)
            hloc = _num(p["hmax"], env, s)
            grad = float(evaluate(str(p.get("hgrad", "1.2")), env).magnitude)
            hfar = hmax_global or 10 * hloc
            d = gmsh.model.mesh.field.add("Distance")
            gmsh.model.mesh.field.setNumbers(d, "CurvesList", curves)
            gmsh.model.mesh.field.setNumber(d, "Sampling", 200)
            t = gmsh.model.mesh.field.add("Threshold")
            gmsh.model.mesh.field.setNumber(t, "InField", d)
            gmsh.model.mesh.field.setNumber(t, "SizeMin", hloc)
            gmsh.model.mesh.field.setNumber(t, "SizeMax", hfar)
            # faixa de largura 'dfine' com tamanho hloc; depois cresce até hfar com razão 'grad'
            dfine = _num(p.get("dfine", "0") or "0", env, s)
            gmsh.model.mesh.field.setNumber(t, "DistMin", dfine)
            dist = hloc * (hfar / hloc - 1.0) / max(grad - 1.0, 1e-3)
            gmsh.model.mesh.field.setNumber(t, "DistMax", dfine + dist)
            fields.append(t)
        elif node.kind == "mesh.boundary_layers" and model.meta.get("mesh_boundary_layers", False):
            curves = _sel_tags(node, geo.boundaries)
            bl = gmsh.model.mesh.field.add("BoundaryLayer")
            gmsh.model.mesh.field.setNumbers(bl, "CurvesList", curves)
            gmsh.model.mesh.field.setNumber(bl, "Ratio", float(evaluate(str(p["stretch"]), env).magnitude))
            gmsh.model.mesh.field.setNumber(bl, "NbLayers", int(p["n"]))
            gmsh.model.mesh.field.setNumber(bl, "Size", (hmax_global or 1.0) / 50)
            gmsh.model.mesh.field.setAsBoundaryLayer(bl)
    if fields:
        mn = gmsh.model.mesh.field.add("Min")
        gmsh.model.mesh.field.setNumbers(mn, "FieldsList", fields)
        gmsh.model.mesh.field.setAsBackgroundMesh(mn)
        opt.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        opt.setNumber("Mesh.MeshSizeFromPoints", 0)
    opt.setNumber("Mesh.Algorithm", 6)  # Frontal-Delaunay


def generate(
    model: Model, env: dict[str, Any] | None = None, *, write_msh: Path | None = None, verbose: bool = False
) -> GeometryResult:
    """Gera geometria + malha no gmsh (processo atual). Deixa o modelo gmsh aberto."""
    import gmsh

    if env is None:
        from kfem.model.expressions import constants

        env = {**constants(), **model.parameters.evaluate()}
    if not gmsh.isInitialized():
        gmsh.initialize(interruptible=False)
    gmsh.option.setNumber("General.Terminal", 1 if verbose else 0)
    gmsh.clear()
    gmsh.model.add(model.name or "kfem")
    geo = build_geometry(gmsh, model, env)
    apply_mesh_settings(gmsh, model, env, geo)
    gmsh.model.mesh.generate(geo.dim)
    if write_msh:
        gmsh.write(str(write_msh))
    return geo


def to_dolfinx(comm: Any, geo: GeometryResult, rank: int = 0) -> Any:
    """Converte o modelo gmsh atual em malha DOLFINx com marcadores de célula e de faceta."""
    from dolfinx.io import gmsh as gmshio

    return gmshio.model_to_mesh(__import__("gmsh").model, comm, rank, gdim=geo.dim)
