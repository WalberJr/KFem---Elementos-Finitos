"""Estados estacionários do modelo de Xie et al. (2022) no KFem, por continuação em corrente.

    python simular.py SAIDA [pH ...]

O artigo chegou ao estado estacionário com um estudo dependente do tempo; aqui o mesmo
estado estacionário (mesmas equações, domínio, contornos e parâmetros) é obtido com Newton
direto, subindo a corrente de 0 até 750 mA/cm² a partir do equilíbrio do eletrólito. Cada
corrente do artigo (100…750 mA/cm²) é um ponto da mesma continuação; o perfil estacionário
de cada uma vai para SAIDA/perfis_pH<pH>.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import modelo
import numpy as np

J_LIST = (100, 150, 200, 250, 500, 750)  # mA/cm², as do artigo


def profiles(prob) -> dict[str, list[float]]:
    V0 = prob.W.sub(0).collapse()[0]
    X = V0.tabulate_dof_coordinates()
    sel = np.isclose(X[:, 1], 0.0)  # borda inferior da faixa (o problema é 1D)
    order = np.argsort(X[sel, 0])
    out: dict[str, list[float]] = {"x_um": (X[sel, 0][order] * 1e6).tolist()}
    for i, sp in enumerate(modelo.SPECIES):
        u = prob.w.sub(i).collapse().x.array
        out[sp] = np.exp(u[sel][order]).tolist()  # mol/m³ = mM
    return out


def run_pH(pH: float, out: Path, log=print) -> list[dict]:
    from dolfinx import fem
    from mpi4py import MPI

    from kfem.solvers.setup import build_mesh, parameters_si
    from kfem.solvers.weakform import problem_from_model

    m = modelo.build(pH, J_LIST[-1])
    si = parameters_si(m)
    md = build_mesh(m, si, MPI.COMM_WORLD, log=lambda s: None)
    r_per_j = si["Rrxn"] / J_LIST[-1]  # Rrxn é proporcional a j
    R = fem.Constant(md.mesh, 0.0)
    prob = problem_from_model(m, [m.comp.physics.child("sp")], md, {**si, "Rrxn": R}, transient=False)
    t0 = time.time()
    j, dj, steps, fails, results = 0.0, 0.5, 0, 0, []
    for jt in J_LIST:
        while j < jt - 1e-9:
            jn = min(jt, j + dj)
            R.value = r_per_j * jn
            w0 = prob.w.x.array.copy()
            try:
                its = prob.solve_stationary()
            except RuntimeError:
                prob.w.x.array[:] = w0
                prob.w.x.scatter_forward()
                fails += 1
                dj *= 0.3
                if dj < 1e-6:
                    raise
                continue
            j, steps = jn, steps + 1
            dj = min(dj * (1.6 if its < 15 else 1.0 if its < 40 else 0.6), 50.0)
        p = profiles(prob)
        p.update(pH=pH, j=jt, wall_s=time.time() - t0, steps=steps, fails=fails)
        results.append(p)
        H = np.array(p["H"]) / 1000.0
        log(
            f"pH {pH:g}  j {jt:g} mA/cm²: CO2 mín {min(p['CO2']):.2f} mM em x = "
            f"{p['x_um'][int(np.argmin(p['CO2']))]:.1f} µm; pH na superfície {-np.log10(H[0]):.2f}; "
            f"{steps} passos, {fails} rejeições, {time.time() - t0:.0f} s"
        )
        (out / f"perfis_pH{pH:g}.json").write_text(json.dumps(results))
    return results


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for pH in [float(a) for a in sys.argv[2:]] or [0, 1, 2, 3, 4]:
        run_pH(pH, out, log=lambda s: print(s, flush=True))
