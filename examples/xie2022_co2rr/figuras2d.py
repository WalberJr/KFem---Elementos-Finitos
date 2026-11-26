"""Figuras e indicadores do modelo 2D (eletrodo plano, convexo e cônico).

    python figuras2d.py SAIDA [DIR_2D [DIR_1D]]

Lê DIR_2D/pH{pH}_j{j}_{forma} (saídas de `kfem --solve`; padrão ~/kfem-build/xie/2d) e,
se houver, o caso 1D DIR_1D/pH{pH}_j{j} com perfis.json (de analisar.py) para a verificação:
o eletrodo plano em 2D tem de reproduzir o 1D.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import analisar
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np

BASE = Path.home() / "kfem-build" / "xie"
DIR_2D = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE / "2d"
DIRS_1D = [Path(sys.argv[3])] if len(sys.argv) > 3 else [BASE / "diag", BASE / "varredura"]
SHAPES = ("plano", "convexo", "conico")
LABEL = {"plano": "Plano", "convexo": "Convexo", "conico": "Pontiagudo (cônico)"}
COL = {"plano": "#1D3E8C", "convexo": "#2E7D4F", "conico": "#B0562A"}
CASES = ((2, 500), (2, 200), (4, 500))
SPECIES = ("CO2", "HCO3", "CO3", "OH", "H")


def finished(d: Path) -> bool:
    """Cálculo terminado: o log ao lado (DIR.log) diz "concluído" ou, sem log, há resultados."""
    log = d.parent / (d.name + ".log")
    if log.exists():
        return "transiente concluído" in log.read_text(errors="replace")
    return (d / "field_CO2.xdmf").exists()


def read_case(d: Path, k: int = -1) -> dict:
    import meshio

    out: dict = {}
    for sp in SPECIES:
        with meshio.xdmf.TimeSeriesReader(str(d / f"field_{sp}.xdmf")) as r:
            pts, cells = r.read_points_cells()
            kk = r.num_steps + k if k < 0 else k
            t, data, _ = r.read_data(kk)
        out[sp] = next(iter(data.values())).ravel()
        out["t"] = float(t)
    out["xy"] = pts[:, :2] * 1e6
    out["tri"] = next(c.data for c in cells if c.type == "triangle")
    return out


def electrode_nodes(xy: np.ndarray, shape: str) -> np.ndarray:
    """Nós sobre a interface gás-líquido (onde o CO2 é fixo)."""
    import modelo2d as m2

    x, y = xy[:, 0], xy[:, 1]
    tol = 1e-3
    if shape == "plano":
        return np.where(np.abs(y) < tol)[0]
    if shape == "convexo":
        return np.where((np.abs(np.hypot(x, y) - m2.R_DOME) < tol) & (y >= -tol))[0]
    a, h = m2.HALF_CONE, m2.H_CONE
    return np.where(np.abs(y - h * (1 - np.abs(x) / a)) < tol)[0]


def arc_coordinate(xy: np.ndarray, shape: str) -> np.ndarray:
    """Coordenada ao longo do eletrodo, de -Ls/2 (pé esquerdo) a +Ls/2 (pé direito); 0 = centro/ápice."""
    import modelo2d as m2

    x, y = xy[:, 0], xy[:, 1]
    if shape == "plano":
        return x
    if shape == "convexo":
        return m2.R_DOME * (np.pi / 2 - np.arctan2(y, x))
    return np.sign(x) * (m2.LS / 2) * np.abs(x) / m2.HALF_CONE


def normals(xy: np.ndarray, shape: str) -> np.ndarray:
    """Normal unitária para fora do eletrodo (para dentro do líquido) em cada ponto da superfície."""
    import modelo2d as m2

    x, y = xy[:, 0], xy[:, 1]
    if shape == "plano":
        return np.column_stack([np.zeros_like(x), np.ones_like(x)])
    if shape == "convexo":
        r = np.hypot(x, y)
        return np.column_stack([x / r, y / r])
    a, h = m2.HALF_CONE, m2.H_CONE
    n = np.column_stack([np.sign(x) * h, np.full_like(x, a)])
    return n / np.hypot(n[:, 0], n[:, 1])[:, None]


def co2_mid_cl(r: dict, ie: np.ndarray, shape: str, depth: float = 0.2) -> np.ndarray:
    """CO2 no meio da camada catalítica (0,2 µm da interface, ao longo da normal)."""
    tri = mtri.Triangulation(r["xy"][:, 0], r["xy"][:, 1], r["tri"])
    p = r["xy"][ie] + depth * normals(r["xy"][ie], shape)
    return np.asarray(mtri.LinearTriInterpolator(tri, r["CO2"])(p[:, 0], p[:, 1]).filled(np.nan))


def arc_mean(s: np.ndarray, v: np.ndarray) -> float:
    """Média ao longo do eletrodo ponderada pelo comprimento de arco (trapézios)."""
    ok = ~np.isnan(v)
    s, v = np.asarray(s)[ok], np.asarray(v)[ok]
    return float(np.trapezoid(v, s) / (s[-1] - s[0]))


def ph(H: np.ndarray) -> np.ndarray:
    return analisar.ph(H)


def summarize(d: Path, shape: str) -> dict:
    r = read_case(d)
    rp = read_case(d, -2)
    xy = r["xy"]
    p = ph(r["H"])
    ie = electrode_nodes(xy, shape)
    s = arc_coordinate(xy[ie], shape)
    o = np.argsort(s)
    ie, s = ie[o], s[o]
    top = np.abs(xy[:, 1] - 100) < 1e-3
    # frente de pH: menor y (em qualquer x) com pH < 6, se a superfície é alcalina
    pe = p[ie]
    alk = np.nanmean(pe) >= 6
    acid = np.where((p < 6) & ~top)[0] if alk else np.array([], dtype=int)
    i_min = int(np.argmin(r["CO2"]))
    cmid = co2_mid_cl(r, ie, shape)
    # CO2 médio na CL: média dos nós a menos de 0,4 µm do eletrodo
    return {
        "t": r["t"],
        "dCO2": float(np.abs(r["CO2"] - rp["CO2"]).max()),
        "s": s.tolist(),
        "pH_el": [None if np.isnan(v) else float(v) for v in pe],
        "CO2_el": [None if np.isnan(v) else float(v) for v in cmid],
        "co2_cl_mean": arc_mean(s, cmid),
        "pH_el_mean": arc_mean(s, pe),
        "pH_el_min": float(np.nanmin(pe)),
        "pH_el_max": float(np.nanmax(pe)),
        "co2_min": float(r["CO2"][i_min]),
        "xy_co2_min": xy[i_min].tolist(),
        "y_front": float(xy[acid, 1].min()) if len(acid) else None,
        "neg_H": float(r["H"].min()),
    }


BASE_T = 2.0  # µm de "substrato" desenhado abaixo da base (só ilustração)


def draw_electrode(ax, shape: str) -> None:
    """Corpo do eletrodo (fora do domínio de cálculo) em cinza: base + forma."""
    import modelo2d as m2
    from matplotlib.patches import Polygon, Rectangle, Wedge

    a = m2.half_width(shape)
    kw = {"facecolor": "#9A96A3", "edgecolor": "#3A3640", "lw": 0.8, "zorder": 3}
    ax.add_patch(Rectangle((-a, -BASE_T), 2 * a, BASE_T, **kw))
    if shape == "convexo":
        ax.add_patch(Wedge((0, 0), m2.R_DOME, 0, 180, **kw))
    elif shape == "conico":
        ax.add_patch(Polygon([(-m2.HALF_CONE, 0), (m2.HALF_CONE, 0), (0, m2.H_CONE)], closed=True, **kw))


def field_maps(cases: dict, pH: int, j: int, fname: Path, ymax: float = 100.0) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12, 8.5 if ymax > 50 else 6.5))
    for col, shape in enumerate(SHAPES):
        r = cases.get(shape)
        for row, (key, lab, cmap, lim) in enumerate(
            (("CO2", "CO$_2$ (mM)", "viridis", (0, 45)), ("pH", "pH", "jet_r", (0, 14)))
        ):
            ax = axes[row, col]
            if r is None:
                ax.axis("off")
                continue
            tri = mtri.Triangulation(r["xy"][:, 0], r["xy"][:, 1], r["tri"])
            v = ph(r["H"]) if key == "pH" else r[key]
            v = np.where(np.isnan(v), 14.0, v) if key == "pH" else v
            im = ax.tripcolor(tri, v, shading="gouraud", cmap=cmap, vmin=lim[0], vmax=lim[1])
            if key == "pH":
                ax.tricontour(tri, v, levels=[6], colors="w", linewidths=0.8)
            ax.set_aspect("equal")
            draw_electrode(ax, shape)
            ax.set_ylim(-BASE_T, ymax)
            ax.set_title(f"{LABEL[shape]} — {lab}", fontsize=10)
            ax.set_xlabel("x (µm)")
            if col == 0:
                ax.set_ylabel("y (µm)")
            fig.colorbar(im, ax=ax, shrink=0.8)
    fig.suptitle(f"pH {pH}, {j} mA cm$^{{-2}}$ (estado estacionário)", fontsize=12)
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def electrode_profiles(summ: dict, fname: Path) -> None:
    fig, axes = plt.subplots(2, len(CASES), figsize=(4.2 * len(CASES), 7), squeeze=False)
    for c, (pH, j) in enumerate(CASES):
        for shape in SHAPES:
            sm = summ.get((pH, j, shape))
            if sm is None:
                continue
            axes[0, c].plot(sm["s"], np.array(sm["pH_el"], dtype=float), color=COL[shape], label=LABEL[shape])
            axes[1, c].plot(sm["s"], np.array(sm["CO2_el"], dtype=float), color=COL[shape])
        axes[0, c].set_title(f"pH {pH}, {j} mA cm$^{{-2}}$")
        axes[0, c].set_ylabel("pH na superfície do eletrodo")
        axes[1, c].set_ylabel("CO$_2$ no meio da CL (mM)")
        for ax in axes[:, c]:
            ax.set_xlabel("posição ao longo do eletrodo (µm; 0 = centro/ápice)")
            ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def verification_1d(summ_cases: dict, fname: Path) -> dict:
    """Plano 2D (linha x = 0) contra o 1D, pH 2 / 500 mA cm⁻²."""
    out = {}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for (pH, j), r in summ_cases.items():
        d1 = next((p for p in (d / f"pH{pH}_j{j}" for d in DIRS_1D)
                   if (p / "perfis.json").exists()), None)
        if d1 is None:
            continue
        p1 = json.loads((d1 / "perfis.json").read_text())
        # o caso plano é uniforme em x: todos os nós entram, ordenados por y
        xy = r["xy"]
        o = np.argsort(xy[:, 1])
        y2, c2, h2 = xy[o, 1], r["CO2"][o], r["H"][o]
        ys = np.unique(np.round(xy[:, 1], 6))[:200]
        lat = float(np.max([np.ptp(r["CO2"][np.abs(xy[:, 1] - yy) < 1e-6]) for yy in ys]))
        c1 = np.interp(y2, p1["x_um"], p1["CO2"])
        out[f"pH{pH}_j{j}"] = {"max_dCO2_mM": float(np.abs(c2 - c1).max()), "co2_min_2d": float(c2.min()),
                               "co2_min_1d": float(min(p1["CO2"])),
                               "pH_s_2d": float(np.nanmean(ph(h2[y2 < 1e-3]))), "pH_s_1d": float(p1["pH"][0]),
                               "nonuniform_x_mM": lat}
        axes[0].plot(p1["x_um"], p1["CO2"], "k-", lw=2.5, alpha=0.35, label=f"1D pH {pH}, {j}")
        axes[0].plot(y2, c2, ".", ms=1.5, label=f"2D plano pH {pH}, {j}")
        axes[1].plot(p1["x_um"], np.array(p1["pH"], dtype=float), "k-", lw=2.5, alpha=0.35)
        axes[1].plot(y2, ph(h2), ".", ms=1.5)
    axes[0].set_ylabel("CO$_2$ (mM)")
    axes[1].set_ylabel("pH")
    for ax in axes:
        ax.set_xlabel("distância à superfície (µm)")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)
    return out


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    summ: dict = {}
    flat: dict = {}
    for pH, j in CASES:
        cases = {}
        for shape in SHAPES:
            d = DIR_2D / f"pH{pH}_j{j}_{shape}"
            if not finished(d):
                continue
            cases[shape] = read_case(d)
            summ[(pH, j, shape)] = summarize(d, shape)
        if cases:
            field_maps(cases, pH, j, out / f"fig2d_mapa_pH{pH}_j{j}.png")
            field_maps(cases, pH, j, out / f"fig2d_zoom_pH{pH}_j{j}.png", ymax=25)
        if "plano" in cases:
            flat[(pH, j)] = cases["plano"]
    electrode_profiles(summ, out / "fig2d_eletrodo.png")
    ver = verification_1d(flat, out / "fig2d_verificacao_1d.png")
    skip = ("s", "pH_el", "CO2_el")
    table = [{"pH": k[0], "j": k[1], "shape": k[2], **{kk: v for kk, v in s.items() if kk not in skip}}
             for k, s in summ.items()]
    (out / "indicadores2d.json").write_text(json.dumps({"casos": table, "verificacao_1d": ver}, indent=1))
    print(f"{len(summ)} casos 2D; figuras em {out}")
