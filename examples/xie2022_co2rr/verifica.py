"""Indicadores de verificação numérica para o relatório (malha 1D, malha 2D, 2D × 1D).

    python verifica.py DIR_FIGURAS

Grava DIR_FIGURAS/verificacao.json a partir de ~/kfem-build/xie/{conv1d,2d}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import analisar
import figuras2d as f2
import numpy as np

BASE = Path.home() / "kfem-build" / "xie"


def main(out: Path) -> None:
    res: dict = {"malha_1d": [], "malha_2d": [], "formas_fino": []}
    # 1D: h = 0,1 / 0,05 / 0,025 µm (pH 4, 500 mA/cm²), contra a mais fina
    ref = analisar.summarize(BASE / "conv1d" / "h0.025")
    xr, cr = np.asarray(ref["x_um"]), np.asarray(ref["CO2"])
    for h in ("0.1", "0.05", "0.025"):
        d = BASE / "conv1d" / f"h{h}"
        s = analisar.summarize(d)
        x, c = np.asarray(s["x_um"]), np.asarray(s["CO2"])
        res["malha_1d"].append({"h_um": float(h), "cells": f2_cells(d.parent / (d.name + ".log")),
                                "pH_s": s["pH_surface"], "co2_min": s["co2_min"],
                                "max_dCO2_vs_fina": float(np.abs(np.interp(xr, x, c) - cr).max())})
    # 2D plano: malhas cada vez mais finas, contra o 1D mais fino
    for name, lab in (("pH4_j500_plano", "padrão (h_meio 1 µm)"), ("fino_pH4_j500_plano", "fina no topo (0,1 µm)"),
                      ("conv_h0.5_pH4_j500_plano", "h_meio 0,5 µm"), ("conv_h0.25_pH4_j500_plano", "h_meio 0,25 µm")):
        d = BASE / "2d" / name
        r = f2.read_case(d)
        y = r["xy"][:, 1]
        sm = f2.summarize(d, "plano")
        res["malha_2d"].append({"caso": lab, "cells": f2_cells(d.parent / (d.name + ".log")), "pH_s": sm["pH_el_mean"],
                                "co2_min": sm["co2_min"], "neg_H": sm["neg_H"],
                                "max_dCO2_vs_1d": float(np.abs(r["CO2"] - np.interp(y, xr, cr)).max())})
    # convexo e cônico: malha padrão × malha fina no topo
    for shape in ("convexo", "conico"):
        a = f2.summarize(BASE / "2d" / f"pH4_j500_{shape}", shape)
        b = f2.summarize(BASE / "2d" / f"fino_pH4_j500_{shape}", shape)
        res["formas_fino"].append({"shape": shape, "pH_mean": [a["pH_el_mean"], b["pH_el_mean"]],
                                   "co2_min": [a["co2_min"], b["co2_min"]], "neg_H": [a["neg_H"], b["neg_H"]],
                                   "cells": [f2_cells(BASE / "2d" / f"pH4_j500_{shape}.log"),
                                             f2_cells(BASE / "2d" / f"fino_pH4_j500_{shape}.log")]})
    (out / "verificacao.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def f2_cells(log: Path) -> int | None:
    import re

    m = re.search(r"malha: (\d+) células", log.read_text(errors="replace")) if log.exists() else None
    return int(m[1]) if m else None


if __name__ == "__main__":
    main(Path(sys.argv[1]))
