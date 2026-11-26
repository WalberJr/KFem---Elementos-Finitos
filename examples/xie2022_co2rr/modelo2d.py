"""Modelo 2D de Xie et al. (2022) com eletrodo plano, convexo (semicírculo) ou pontiagudo (cone).

    python modelo2d.py FORMA PH J SAIDA.kfem      (FORMA = plano | convexo | conico)

Mesmas equações, parâmetros e condições de contorno do modelo 1D (modelo.py); muda só a forma
da interface gás-líquido, onde fica a camada catalítica (CL) de 0,4 µm que acompanha a
superfície. Escolhas do usuário (2026-11-24):

- as três superfícies têm o mesmo comprimento ativo Ls = 20 µm (a "mesma área" em 2D), com a
  mesma densidade de corrente j por área ativa, logo a mesma corrente total;
- convexo = semicírculo (pi R = Ls); cônico = triângulo com a mesma altura do semicírculo
  (2 x lado = Ls);
- célula com paredes laterais de simetria (fluxo nulo) na largura da base de cada forma (no
  convexo, 0,6 µm além do pé do semicírculo, com base inerte entre os dois); o
  eletrólito (equilíbrio do seio) fica em y = 100 µm acima da base, como no modelo 1D.

A taxa da CO2RR usa a área real da CL, A_cl, para que a corrente total seja j·Ls nos três casos:
R = j ε Ls / (F n A_cl). No eletrodo plano A_cl = Ls·Lcat e isso é exatamente a Eq. S2.
"""

from __future__ import annotations

import math
import sys

import modelo
from modelo import SPECIES, _n

from kfem.model.tree import Model, Selection

LS = 20.0  # µm, comprimento ativo do eletrodo
LCAT = 0.4  # µm
HTOT = 100.0  # µm, base -> eletrólito
R_DOME = LS / math.pi
H_CONE = R_DOME
HALF_CONE = math.sqrt((LS / 2) ** 2 - H_CONE**2)
GAP_DOME = 0.6  # µm
SHAPES = ("plano", "convexo", "conico")


def half_width(shape: str) -> float:
    # convexo: a parede fica 0,6 µm além do pé do semicírculo; com a parede no pé (x = R), o arco
    # a tocaria tangencialmente (ângulo nulo) e a malha teria elementos degenerados ali
    return {"plano": LS / 2, "convexo": R_DOME + GAP_DOME, "conico": HALF_CONE}[shape]


def _fmt(pts: list[tuple[float, float]]) -> str:
    return "; ".join(f"{x:.6f} {y:.6f}" for x, y in pts)


def cone_band_polygon(t: float = LCAT) -> list[tuple[float, float]]:
    """Contorno externo da CL do cone: lados deslocados de t para fora; no ápice, o canto
    (mitra) é cortado na altura h + t, de modo que a espessura no ápice também é t.

    Um arco de raio t no ápice teria vértices a ~0,02 µm uns dos outros, abaixo da tolerância
    geométrica do OCC; o corte reto difere do arco em menos de 0,05 µm. Os lados descem abaixo
    de y = 0, e a interseção com a célula corta o excesso."""
    a, h = HALF_CONE, H_CONE
    L = math.hypot(a, h)
    # lado esquerdo deslocado: pontos (-a,0)+t*nl ... ; reta x = -a + nl_x t + s a/L, y = nl_y t + s h/L
    nlx, nly = -h / L, a / L
    yt = h + t

    def x_left(y: float) -> float:
        s_ = (y - nly * t) / (h / L)
        return -a + nlx * t + s_ * a / L

    ext = -2.0  # prolonga abaixo da base
    return [(x_left(ext), ext), (x_left(yt), yt), (-x_left(yt), yt), (-x_left(ext), ext)]


def residual(cl: int = 1, dl: int = 2) -> str:
    """Forma fraca das 5 espécies; CL = domínio cl, camada de difusão = domínio dl."""
    C = {sp: f"max({sp}, ceps)" for sp in SPECIES}
    r = {
        "r1": f"(k1f*{C['CO2']} - k1r*{C['H']}*{C['HCO3']})",
        "r2": f"(k2f*{C['HCO3']} - k2r*{C['H']}*{C['CO3']})",
        "r3": f"(k3f*{C['CO2']}*{C['OH']} - k3r*{C['HCO3']})",
        "r4": f"(k4f*{C['HCO3']}*{C['OH']} - k4r*{C['CO3']})",
        "rw": f"(kwf - kwr*{C['H']}*{C['OH']})",
    }
    R = {
        "CO2": f"-{r['r1']} - {r['r3']}",
        "HCO3": f"{r['r1']} - {r['r2']} + {r['r3']} - {r['r4']}",
        "CO3": f"{r['r2']} + {r['r4']}",
        "H": f"{r['r1']} + {r['r2']} + {r['rw']}",
        "OH": f"-{r['r3']} - {r['r4']} + {r['rw']}",
    }
    rr = {"CO2": "-Rrxn", "OH": "2*Rrxn"}  # Eq. S2, só na CL
    terms = []
    for sp in SPECIES:
        v = f"test({sp})"
        g = f"inner(grad({sp}), grad({v}))"
        t = f"dt({sp})*{v}*dx + D{sp}*eps_cl^1.5*{g}*dx({cl}) + D{sp}*{g}*dx({dl}) - ({R[sp]})*{v}*dx"
        if sp in rr:
            t += f" - ({rr[sp]})*{v}*dx({cl})"
        terms.append(t)
    return " + ".join(terms)


def _geometry(m: Model, shape: str) -> None:
    g = m.comp.geometry
    a = half_width(shape)
    if shape == "plano":
        g.add(_n("geom.rectangle", "cl", "camada catalítica", x=str(-a), y="0", width=str(2 * a), height=str(LCAT)))
        g.add(_n("geom.rectangle", "dl", "camada de difusão", x=str(-a), y=str(LCAT), width=str(2 * a),
                 height=str(HTOT - LCAT)))
    else:
        g.add(_n("geom.rectangle", "cell", "célula", x=str(-a), y="0", width=str(2 * a), height=str(HTOT)))
        if shape == "convexo":
            g.add(_n("geom.disk", "body", "eletrodo", x="0", y="0", r=f"{R_DOME:.6f}"))
            g.add(_n("geom.disk", "outer", "limite da CL", x="0", y="0", r=f"{R_DOME + LCAT:.6f}"))
        else:
            tri = [(-a, 0.0), (a, 0.0), (0.0, H_CONE)]
            g.add(_n("geom.polygon", "body", "eletrodo", points=_fmt(tri)))
            g.add(_n("geom.polygon", "outer", "limite da CL", points=_fmt(cone_band_polygon())))
        g.add(_n("geom.rectangle", "cell2", "célula (recorte)", x=str(-a), y="0", width=str(2 * a), height=str(HTOT)))
        g.add(_n("geom.intersection", "clip", "CL na célula", objects=["outer", "cell2"]))
        g.add(_n("geom.difference", "cut", "remove o eletrodo", add=["cell", "clip"], subtract=["body"]))
    g.add(_n("geom.form_union", "fin", "Formar união"))


def markers(m: Model) -> tuple[dict[int, float], int, list[int], list[int], list[int]]:
    """Gera a geometria e devolve áreas por domínio e os contornos: eletrodo, topo e paredes."""
    import gmsh

    from kfem.geometry.build import generate

    geo = generate(m)
    s = geo.scale
    if len(geo.domains) != 2:
        raise RuntimeError(f"geometria inesperada: {len(geo.domains)} domínios")
    cl = min(geo.areas, key=geo.areas.get)  # a CL é o domínio de menor área
    dl = 3 - cl
    cl_curves = {abs(t) for _, t in gmsh.model.getBoundary([(2, geo.domains[cl])], oriented=False)}
    dl_curves = {abs(t) for _, t in gmsh.model.getBoundary([(2, geo.domains[dl])], oriented=False)}
    electrode, top, walls = [], [], []
    tol = 1e-3 * s  # 1 nm
    for mk, tag in geo.boundaries.items():
        ends = [gmsh.model.getValue(0, abs(pt), []) for _, pt in gmsh.model.getBoundary([(1, tag)], oriented=False)]
        (x0, y0, _), (x1, y1, _) = ends[0], ends[-1]
        if abs(y0 - HTOT * s) < tol and abs(y1 - HTOT * s) < tol:
            top.append(mk)
        elif abs(x1 - x0) < tol and abs(abs(x0) - half_width(m.meta["xie2d_shape"]) * s) < tol:
            walls.append(mk)
        elif (m.meta["xie2d_shape"] != "plano" and abs(y0) < tol and abs(y1) < tol
              and abs(gmsh.model.occ.getMass(1, tag) - abs(x1 - x0)) < tol):  # segmento reto em y = 0
            walls.append(mk)  # pé do semicírculo: base inerte, fluxo nulo
        elif tag in cl_curves and tag not in dl_curves:
            electrode.append(mk)
    areas = dict(geo.areas)
    gmsh.finalize()
    return areas, cl, electrode, top, walls


def build(
    shape: str,
    pH: float,
    j_mA_cm2: float,
    tlist: str | None = None,
    h_top: float = 0.2,
    d_top: float = 15.0,
    h_mid: float = 1.0,
) -> Model:
    m = modelo.build(pH, j_mA_cm2, tlist)  # parâmetros, estudo e unidade (µm) do modelo 1D
    m.name = f"CO2RR ácido 2D — eletrodo {shape} (Xie et al. 2022)"
    c = m.comp
    for coll in (c.geometry, c.physics, c.mesh):
        for ch in list(coll.children):
            coll.remove(ch.tag)
    m.meta["xie2d_shape"] = shape
    _geometry(m, shape)
    c.mesh.add(_n("mesh.size", "size", hmax=f"{h_mid:g}", hmin="0.02"))
    areas, cl, electrode, top, walls = markers(m)
    if not (electrode and len(top) == 1):
        raise RuntimeError(f"geometria inesperada: áreas {areas}, eletrodo {electrode}, topo {top}")
    a_cl = areas[cl] * 1e12  # µm² (por unidade de profundidade)
    ps = m.parameters
    ps.add("Ls", f"{LS}[um]", "comprimento ativo do eletrodo (igual nas três formas)", "Geometria")
    ps.add("A_cl", f"{a_cl:.9g}[um^2]", f"área da CL ({shape}), medida na geometria", "Geometria")
    rx = ps.params["Rrxn"]
    rx.expr = "j_app*eps_cl*Ls/(F_c*n_e*A_cl)"
    rx.description = "taxa da CO2RR na CL, corrente total j·Ls (Eq. S2)"

    wf = c.physics.add(
        _n("physics.weakform", "sp", "Espécies locais (reação-difusão)", Selection(2),
           fields=", ".join(SPECIES), order="P1", equation=residual(cl, 3 - cl), newton_tol="1e-8")
    )
    wf.add(_n("weakform.dirichlet", "co2gas", "CO2 na interface gás-líquido", Selection(1, electrode),
              field="CO2", value="csat"))
    for s, v in (("CO2", "csat"), ("HCO3", "HCO3_b"), ("CO3", "CO3_b"), ("OH", "OH_b"), ("H", "H_b")):
        wf.add(_n("weakform.dirichlet", f"bulk_{s}", f"{s}: eletrólito", Selection(1, top), field=s, value=v))
        wf.add(_n("weakform.initial", f"ini_{s}", f"inicial {s}", Selection(2), field=s, value=v))
    # malha: 0,1 µm na CL e junto ao eletrodo (como no 1D); 0,2 µm nos 15 µm junto ao eletrólito,
    # onde fica a frente ácido-base; até 1 µm no meio
    c.mesh.add(_n("mesh.size_local", "near_el", "junto ao eletrodo", Selection(1, electrode),
                  hmax="0.1", hgrad="1.08", dfine="0.6"))
    c.mesh.add(_n("mesh.size_local", "near_top", "frente ácido-base", Selection(1, top),
                  hmax=f"{h_top:g}", hgrad="1.08", dfine=f"{d_top:g}"))
    c.mesh.add(_n("mesh.triangles", "tri"))
    m.meta["xie2d"] = {"shape": shape, "cl": cl, "electrode": electrode, "top": top, "walls": walls, "A_cl_um2": a_cl}
    return m


if __name__ == "__main__":
    from kfem.io.kfem_format import save

    shape, pH, j, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    extra = [float(v) for v in sys.argv[5:8]]  # opcionais: h_top d_top h_mid (µm)
    mm = build(shape, pH, j, None, *extra)
    save(mm, out)
    print("salvo:", out, mm.meta["xie2d"])
