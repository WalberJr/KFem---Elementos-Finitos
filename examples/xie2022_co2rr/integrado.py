# ruff: noqa: E501
"""Análise integrada 1D + 2D: cada forma 2D comparada com o 1D na corrente projetada.

    python integrado.py DIR_FIGURAS

Lê DIR_FIGURAS/indicadores.json (1D, de figuras.py) e DIR_FIGURAS/indicadores2d.json (2D, de
figuras2d.py), mais os casos 1D na corrente projetada em ~/kfem-build/xie/proj1d (mapa.json).
A corrente projetada j_proj = j·L_s/w é a corrente por área de base da célula: com a mesma
corrente total, a forma mais estreita concentra mais corrente sobre a mesma área de base.

Grava DIR_FIGURAS/fig_integrado.png e DIR_FIGURAS/integrado.json.
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
SHAPES = ("plano", "convexo", "conico")
LABEL = {"plano": "Plano", "convexo": "Convexo", "conico": "Pontiagudo"}
COL = {"plano": "#1D3E8C", "convexo": "#2E7D4F", "conico": "#B0562A"}
MK = {"plano": "o", "convexo": "s", "conico": "^"}
CASES = ((2, 500), (2, 200), (4, 500))


def one_d(d: Path) -> dict:
    """Indicadores 1D de um diretório de resultados (CO2 no meio da CL = x = 0,2 µm)."""
    s = analisar.summarize(d)
    x, c = np.asarray(s["x_um"]), np.asarray(s["CO2"])
    return {"pH_s": s["pH_surface"], "co2_min": s["co2_min"], "front": s["x_front"],
            "co2_mid_cl": float(np.interp(0.2, x, c))}


def main(fig_dir: Path) -> None:
    d1 = {(r["pH"], r["j"]): r for r in json.loads((fig_dir / "indicadores.json").read_text())}
    d2 = {(r["pH"], r["j"], r["shape"]): r for r in json.loads((fig_dir / "indicadores2d.json").read_text())["casos"]}
    mapa = json.loads((BASE / "proj1d" / "mapa.json").read_text())
    proj: dict = {}
    for k, v in mapa.items():
        d = BASE / "proj1d" / v["case"]
        if (d / "field_CO2.xdmf").exists() and "transiente concluído" in (d.parent / (d.name + ".log")).read_text(errors="replace"):
            pH, j, shape = k.split("_")
            proj[(int(pH), int(j), shape)] = {**v, **one_d(d)}
    # 1D na corrente nominal: CO2 no meio da CL a partir dos perfis
    nominal: dict = {}
    for pH, j in CASES:
        for sub in ("diag", "varredura"):
            d = BASE / sub / f"pH{pH}_j{j}"
            if (d / "field_CO2.xdmf").exists():
                nominal[(pH, j)] = one_d(d)
                break

    rows = []
    for pH, j in CASES:
        for shape in SHAPES:
            r2 = d2.get((pH, j, shape))
            if r2 is None:
                continue
            ref = nominal.get((pH, j)) if shape == "plano" else proj.get((pH, j, shape))
            rows.append({
                "pH": pH, "j": j, "shape": shape,
                "j_proj": j if shape == "plano" else (mapa[f"{pH}_{j}_{shape}"]["j_proj"]),
                "pH_2d_mean": r2["pH_el_mean"], "pH_2d_min": r2["pH_el_min"], "pH_2d_max": r2["pH_el_max"],
                "co2min_2d": r2["co2_min"], "front_2d": r2["y_front"],
                "co2_cl_2d_mean": r2.get("co2_cl_mean"),
                "pH_1d_nominal": d1.get((pH, j), {}).get("pH_s"),
                "pH_1d_proj": ref["pH_s"] if ref else None,
                "co2min_1d_proj": ref["co2_min"] if ref else None,
                "front_1d_proj": ref["front"] if ref else None,
                "co2_cl_1d_proj": ref["co2_mid_cl"] if ref else None,
            })
    (fig_dir / "integrado.json").write_text(json.dumps(rows, indent=1))

    # figura: pH na superfície e CO2 no meio da CL contra a corrente por área de base
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.2))
    for col, pH in enumerate((2, 4)):
        # curva 1D com todos os casos disponíveis deste pH (inclui os da corrente projetada)
        pts = {j: r["pH_s"] for (p, j), r in d1.items() if p == pH and j >= 100}
        for (p, _, _), r in proj.items():
            if p == pH:
                pts[r["j_proj"]] = r["pH_s"]
        js = sorted(pts)
        axes[0, col].plot(js, [pts[j] for j in js], "k-", lw=1.4, alpha=0.6, label="1D")
        co2 = {j: nominal[(pH, j)]["co2_mid_cl"] for (p, j) in nominal if p == pH}
        for (p, _, _), r in proj.items():
            if p == pH:
                co2[r["j_proj"]] = r["co2_mid_cl"]
        jc = sorted(co2)
        axes[1, col].plot(jc, [co2[j] for j in jc], "k-", lw=1.4, alpha=0.6, marker=".", label="1D")
        for r in rows:
            if r["pH"] != pH:
                continue
            s = r["shape"]
            for ax, y, lo, hi in ((axes[0, col], r["pH_2d_mean"], r["pH_2d_min"], r["pH_2d_max"]),
                                  (axes[1, col], r["co2_cl_2d_mean"], None, None)):
                if y is None:
                    continue
                yerr = None if lo is None else [[y - lo], [hi - y]]
                ax.errorbar(r["j_proj"], y, yerr=yerr, fmt=MK[s], color=COL[s], ms=7, capsize=3,
                            label=f"2D {LABEL[s]}" if r["j"] == 500 else None)
                if s != "plano":  # seta da corrente nominal para a projetada
                    ax.annotate("", (r["j_proj"], y), (r["j"], y),
                                arrowprops={"arrowstyle": "->", "color": COL[s], "lw": 0.8, "alpha": 0.6})
        axes[0, col].set_title(f"Eletrólito pH {pH}")
        axes[0, col].set_ylabel("pH na superfície do eletrodo")
        axes[1, col].set_ylabel("CO$_2$ no meio da CL (mM)")
        for ax in axes[:, col]:
            ax.set_xlabel("corrente por área de base, j$_{proj}$ = j L$_s$/w (mA cm$^{-2}$)")
            ax.grid(alpha=0.3)
        axes[0, col].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_integrado.png", dpi=150)
    plt.close(fig)
    print(f"{len(rows)} linhas; {len(proj)} casos 1D projetados")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
