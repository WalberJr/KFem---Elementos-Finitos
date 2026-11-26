"""Perfis estacionários de um cálculo do modelo de Xie et al. (2022) e indicadores do artigo.

    python analisar.py DIR_RESULTADOS [DIR ...]

Para cada diretório (saída de `kfem --solve`): confere o estado estacionário (dois últimos
instantes), imprime CO2 mínimo e posição, pH na superfície e posição da frente de pH (primeiro
x com pH < 6), e grava perfis.json ao lado (x, CO2, pH e as 5 concentrações em mM).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SPECIES = ("CO2", "HCO3", "CO3", "OH", "H")


def read(wd: Path, sp: str, k: int = -1) -> tuple[float, np.ndarray, np.ndarray]:
    import meshio

    with meshio.xdmf.TimeSeriesReader(str(wd / f"field_{sp}.xdmf")) as r:
        pts, _ = r.read_points_cells()
        t, d, _ = r.read_data(r.num_steps - 1 if k == -1 else r.num_steps + k if k < 0 else k)
    v = next(iter(d.values())).ravel()
    sel = np.isclose(pts[:, 1], 0.0)
    o = np.argsort(pts[sel, 0])
    return float(t), pts[sel, 0][o] * 1e6, v[sel][o]


def ph(H_mM: np.ndarray) -> np.ndarray:
    """pH; NaN onde H+ <= 0 (artefato das variáveis primitivas na frente ácido-base)."""
    H = np.asarray(H_mM, dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(H > 0, -np.log10(np.where(H > 0, H, 1.0) / 1000.0), np.nan)


def summarize(wd: Path) -> dict:
    t, x, co2 = read(wd, "CO2")
    t0, _, co2_prev = read(wd, "CO2", -2)
    out = {"t": t, "x_um": x.tolist()}
    for sp in SPECIES:
        out[sp] = read(wd, sp)[2].tolist()
    p = ph(np.array(out["H"]))
    p_prev = ph(read(wd, "H", -2)[2])
    i = int(np.argmin(co2))
    # frente de pH: primeiro x em que o pH cai abaixo de 6, partindo de uma superfície alcalina
    k = np.where(p < 6)[0] if p[0] >= 6 else np.array([], dtype=int)
    out.update(
        pH=[None if np.isnan(v) else float(v) for v in p],
        neg={sp: float(min(out[sp])) for sp in SPECIES},
        dCO2_last=float(np.abs(co2 - co2_prev).max()),
        dpH_last=float(np.nanmax(np.abs(p - p_prev))),
        t_prev=t0,
        co2_min=float(co2[i]),
        x_co2_min=float(x[i]),
        pH_surface=float(p[0]),
        x_front=float(x[k[0]]) if len(k) else None,
    )
    (wd / "perfis.json").write_text(json.dumps(out))
    return out


if __name__ == "__main__":
    for d in sys.argv[1:]:
        s = summarize(Path(d))
        front = f"{s['x_front']:.1f} µm" if s["x_front"] is not None else "—"
        print(
            f"{Path(d).name}: CO2 mín {s['co2_min']:.2f} mM em {s['x_co2_min']:.1f} µm; pH superfície "
            f"{s['pH_surface']:.2f}; frente {front}; estacionário? Δ(t={s['t_prev']:g}→{s['t']:g}) "
            f"CO2 {s['dCO2_last']:.2g} mM, pH {s['dpH_last']:.2g}"
        )
