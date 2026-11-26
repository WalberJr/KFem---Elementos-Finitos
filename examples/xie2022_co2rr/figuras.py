"""Figuras e tabela de indicadores da reprodução de Xie et al. (2022) no KFem.

    python figuras.py SAIDA

Lê os resultados em ~/kfem-build/xie/{transiente/res, diag/*, varredura/*} (saídas de
`kfem --solve`), extrai os perfis estacionários (analisar.py) e gera as figuras em SAIDA.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import analisar
import matplotlib.pyplot as plt
import numpy as np

BASE = Path.home() / "kfem-build" / "xie"
J_LIT = (100, 150, 200, 250, 500, 750)
J_HYP = (10, 15, 20, 25, 50, 75)
COLORS = {100: "#E8642A", 150: "#F2A23A", 200: "#E9CF6B", 250: "#7FC8B5", 500: "#2BA3C9", 750: "#1D3E8C"}

# Indicadores lidos das Figuras S2 e S3 do artigo (aproximados, leitura visual)
PAPER = {
    (2, 750): {"co2_min": 19, "x_co2_min": 15, "front": 78, "pH_s": 12},
    (2, 500): {"co2_min": 25, "x_co2_min": 12, "front": 68, "pH_s": 12},
    (2, 250): {"co2_min": 31, "x_co2_min": 10, "front": 37, "pH_s": 11.5},
    (2, 200): {"co2_min": 32, "front": 23, "pH_s": 11.5},
    (2, 150): {"co2_min": 32.5, "front": 5, "pH_s": 10},
    (2, 100): {"co2_min": 33, "front": None, "pH_s": 2.5},
    (3, 750): {"co2_min": 12, "x_co2_min": 22, "front": 96, "pH_s": 12},
    (3, 500): {"co2_min": 19, "x_co2_min": 22, "front": 95, "pH_s": 11.8},
    (3, 250): {"co2_min": 26, "front": 92, "pH_s": 11.5},
    (3, 100): {"co2_min": 30, "front": 83, "pH_s": 11},
    (4, 750): {"co2_min": 11, "x_co2_min": 25, "front": 98, "pH_s": 12},
    (4, 500): {"co2_min": 18, "x_co2_min": 25, "front": 98, "pH_s": 11.8},
    (4, 250): {"co2_min": 25, "front": 97, "pH_s": 11.5},
    (4, 100): {"co2_min": 29, "front": 96, "pH_s": 11},
    (0, 750): {"co2_min": 32, "front": None, "pH_s": 0.1},
    (1, 750): {"co2_min": 32, "front": None, "pH_s": 1.3},
}


def _finished(d: Path) -> bool:
    """Só casos concluídos (o log do `kfem --solve` registra o fim do transiente)."""
    log = d.with_suffix(".log")
    return log.exists() and "transiente concluído" in log.read_text(errors="replace")


def run_stats(d: Path) -> dict:
    """Passos, rejeições, iterações de Newton e tempo do log do `kfem --solve`."""
    import re

    for log in (d.with_suffix(".log"), d.parent / "calculo.log"):
        if log.exists():
            m = re.search(r"transiente concluído: (\d+) passos, (\d+) rejeitados, (\d+) iterações de Newton, "
                          r"([\d.]+) s", log.read_text(errors="replace"))
            if m:
                return {"steps": int(m[1]), "rejected": int(m[2]), "newton": int(m[3]), "wall": float(m[4])}
    return {}


def case_dir(pH: float, j: float) -> Path | None:
    for d in (BASE / "varredura" / f"pH{pH:g}_j{j:g}", BASE / "diag" / f"pH{pH:g}_j{j:g}"):
        if (d / "field_CO2.xdmf").exists() and _finished(d):
            return d
    if pH == 2 and j == 750 and (BASE / "transiente" / "res" / "field_CO2.xdmf").exists():
        return BASE / "transiente" / "res"
    return None


def load(pH: float, j: float) -> dict | None:
    d = case_dir(pH, j)
    if d is None:
        return None
    try:
        return analisar.summarize(d)
    except Exception as exc:  # caso incompleto
        print(f"pH {pH} j {j}: {exc}")
        return None


def profiles_figure(data: dict, key: str, ylabel: str, fname: Path, js=J_LIT, ylim=None) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.2))
    for ax, pH in zip(axes.ravel(), (0, 1, 2, 3, 4), strict=False):
        for j in js:
            r = data.get((pH, j))
            if r is None:
                continue
            ax.plot(r["x_um"], np.array(r[key] if key != "pH" else r["pH"], dtype=float), color=COLORS.get(j), lw=1.6,
                    label=f"{j:g} mA cm$^{{-2}}$")
        ax.set_title(f"pH = {pH:g}")
        ax.set_xlim(0, 100)
        if ylim:
            ax.set_ylim(*ylim)
        ax.set_xlabel("Distância à superfície do eletrodo (µm)")
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
    axes.ravel()[-1].axis("off")
    h, lab = axes.ravel()[2].get_legend_handles_labels()
    if h:
        axes.ravel()[-1].legend(h, lab, loc="center", frameon=False, fontsize=11)
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def map_figure(data: dict, fname: Path) -> None:
    phs = (0, 1, 2, 3, 4)
    Z = np.full((len(J_LIT), len(phs)), np.nan)
    for a, j in enumerate(J_LIT):
        for b, pH in enumerate(phs):
            r = data.get((pH, j))
            if r is not None:
                Z[a, b] = r["pH_surface"]
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    im = ax.imshow(Z, origin="lower", aspect="auto", cmap="jet_r", vmin=0, vmax=14,
                   extent=(-0.5, 4.5, -0.5, len(J_LIT) - 0.5))
    ax.set_xticks(range(5), [str(p) for p in phs])
    ax.set_yticks(range(len(J_LIT)), [str(j) for j in J_LIT])
    ax.set_xlabel("pH do eletrólito")
    ax.set_ylabel("j (mA cm$^{-2}$)")
    for a in range(len(J_LIT)):
        for b in range(5):
            if not np.isnan(Z[a, b]):
                ax.text(b, a, f"{Z[a, b]:.1f}", ha="center", va="center", fontsize=8, color="white")
    fig.colorbar(im, ax=ax, label="pH na superfície")
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def hypothesis_figure(data: dict, fname: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for j_lit, j_h in zip(J_LIT, J_HYP, strict=True):
        r = data.get((2, j_h))
        if r is None:
            continue
        axes[0].plot(r["x_um"], r["CO2"], color=COLORS[j_lit], lw=1.6, label=f"{j_h:g} (≙ {j_lit} no artigo)")
        axes[1].plot(r["x_um"], np.array(r["pH"], dtype=float), color=COLORS[j_lit], lw=1.6)
    axes[0].set_ylabel("CO$_2$ (mM)")
    axes[1].set_ylabel("pH")
    for ax in axes:
        ax.set_xlabel("Distância à superfície do eletrodo (µm)")
        ax.set_xlim(0, 100)
        ax.grid(alpha=0.3)
    axes[0].legend(title="j no KFem (mA cm$^{-2}$)", fontsize=8)
    fig.suptitle("pH 2 com a corrente dividida por 10 (teste da hipótese)")
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def comparison_figure(data: dict, fname: Path) -> None:
    """Indicadores do KFem (linhas) contra os lidos no artigo (marcadores)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    cols = {2: "#1D3E8C", 3: "#2E7D4F", 4: "#B0562A"}
    for pH, c in cols.items():
        js = [j for j in J_LIT if (pH, j) in data]
        axes[0].plot(js, [data[(pH, j)]["co2_min"] for j in js], "-", color=c, label=f"KFem, pH {pH}")
        pj = [j for j in J_LIT if (pH, j) in PAPER]
        axes[0].plot(pj, [PAPER[(pH, j)]["co2_min"] for j in pj], "o", mfc="none", color=c, label=f"artigo, pH {pH}")
    axes[0].set_xlabel("j (mA cm$^{-2}$)")
    axes[0].set_ylabel("CO$_2$ mínimo no domínio (mM)")
    axes[0].legend(fontsize=8, ncol=2)
    jl = [j for j in J_HYP + J_LIT if (2, j) in data]
    jl = sorted(set(jl))
    axes[1].semilogx(jl, [data[(2, j)]["pH_surface"] for j in jl], "-o", color="#1D3E8C", ms=4,
                     label="KFem (j literal)")
    pj = [j for j in J_LIT if (2, j) in PAPER]
    axes[1].semilogx(pj, [PAPER[(2, j)]["pH_s"] for j in pj], "s", mfc="none", color="#B0562A", label="artigo")
    axes[1].set_xlabel("j (mA cm$^{-2}$)")
    axes[1].set_ylabel("pH na superfície (x = 0)")
    axes[1].set_title("Transição ácido → alcalino, pH 2")
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def transient_figure(d: Path, fname: Path) -> None:
    """Evolução temporal (como a Figura S6 do artigo: pH 2, 500 mA/cm²)."""
    import meshio

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    with meshio.xdmf.TimeSeriesReader(str(d / "field_CO2.xdmf")) as r:
        pts, _ = r.read_points_cells()
        series_c = [r.read_data(k) for k in range(r.num_steps)]
    with meshio.xdmf.TimeSeriesReader(str(d / "field_H.xdmf")) as r:
        r.read_points_cells()
        series_h = [r.read_data(k) for k in range(r.num_steps)]
    sel = np.isclose(pts[:, 1], 0.0)
    o = np.argsort(pts[sel, 0])
    x = pts[sel, 0][o] * 1e6
    cmap = plt.get_cmap("viridis")
    n = len(series_c)
    for k, ((t, dc, _), (_, dh, _)) in enumerate(zip(series_c, series_h, strict=True)):
        if t == 0:
            continue
        c = next(iter(dc.values())).ravel()[sel][o]
        h = next(iter(dh.values())).ravel()[sel][o]
        col = cmap(k / max(n - 1, 1))
        axes[0].plot(x, c, color=col, lw=1.3, label=f"t = {t:g} s")
        axes[1].plot(x, analisar.ph(h), color=col, lw=1.3)
    axes[0].set_ylabel("CO$_2$ (mM)")
    axes[1].set_ylabel("pH")
    axes[1].set_ylim(-0.5, 14)
    for ax in axes:
        ax.set_xlabel("Distância à superfície do eletrodo (µm)")
        ax.set_xlim(0, 100)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    for pH in (0, 1, 2, 3, 4):
        for j in J_LIT:
            r = load(pH, j)
            if r is not None:
                data[(pH, j)] = r
    for j in J_HYP:
        r = load(2, j)
        if r is not None:
            data[(2, j)] = r
    profiles_figure(data, "CO2", "CO$_2$ (mM)", out / "fig_co2.png")
    profiles_figure(data, "pH", "pH", out / "fig_ph.png", ylim=(-0.5, 14))
    map_figure(data, out / "fig_mapa_ph.png")
    hypothesis_figure(data, out / "fig_hipotese.png")
    comparison_figure(data, out / "fig_comparacao.png")
    d500 = case_dir(2, 500)
    if d500 is not None:
        transient_figure(d500, out / "fig_transiente.png")
    table = []
    for (pH, j), r in sorted(data.items()):
        p = PAPER.get((pH, j * (10 if j in J_HYP and pH == 2 else 1)), {})
        table.append({"pH": pH, "j": j, "co2_min": r["co2_min"], "x_co2_min": r["x_co2_min"],
                      "pH_s": r["pH_surface"], "front": r["x_front"], "dCO2": r["dCO2_last"],
                      "neg": r["neg"], "co2_max": max(r["CO2"]), "stats": run_stats(case_dir(pH, j)),
                      "paper": p, "hyp": j in J_HYP and pH == 2})
    (out / "indicadores.json").write_text(json.dumps(table, indent=1))
    print(f"{len(data)} casos; figuras em {out}")
