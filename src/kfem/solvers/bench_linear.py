"""Compara solvers lineares num sistema salvo pelo transiente (KFEM_DUMP_SYSTEM).

    python -m kfem.solvers.bench_linear cdi_system_t60.petsc --gpu hip --repeat 3

Referência: LU (MUMPS) na CPU. Para cada configuração de GPU: tempo da conversão da matriz,
tempo do solve, iterações e erro relativo contra a referência.
"""

from __future__ import annotations

import argparse
import time

CONFIGS: dict[str, dict[str, str]] = {
    "jacobi": {"pc_type": "jacobi"},
    "ilu0": {"pc_type": "ilu", "pc_factor_mat_solver_type": "{gpu_solver}"},
    "gamg": {"pc_type": "gamg"},
    "bjacobi-ilu": {"pc_type": "bjacobi", "sub_pc_type": "ilu"},
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("system")
    ap.add_argument("--gpu", default="hip", choices=["hip", "cuda", "opencl", "none"])
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--ksp", default="gmres")
    a = ap.parse_args(argv)

    from petsc4py import PETSc

    from kfem.solvers.gpu_linear import MAT_TYPES

    comm = PETSc.COMM_WORLD
    vw = PETSc.Viewer().createBinary(a.system, "r", comm=comm)
    A = PETSc.Mat().create(comm)
    A.setType("aij")
    A.load(vw)
    b = PETSc.Vec().create(comm)
    b.load(vw)
    vw.destroy()
    n = A.getSize()[0]
    PETSc.Sys.Print(f"sistema: {n} incógnitas, {A.getInfo()['nz_used']:.0f} não nulos")

    def lu() -> tuple[float, object]:
        k = PETSc.KSP().create(comm)
        k.setOperators(A)
        k.setType("preonly")
        k.getPC().setType("lu")
        k.getPC().setFactorSolverType("mumps")
        x = b.duplicate()
        t0 = time.perf_counter()
        k.solve(b, x)
        return time.perf_counter() - t0, x

    t_lu, x_ref = lu()
    t_lu = min([t_lu] + [lu()[0] for _ in range(a.repeat - 1)])
    PETSc.Sys.Print(f"CPU  LU/MUMPS                 solve {t_lu:8.3f} s")
    if a.gpu == "none":
        return 0
    mtype = MAT_TYPES[a.gpu]
    gsolver = {"hip": "hipsparse", "cuda": "cusparse"}.get(a.gpu, "petsc")
    for name in a.configs.split(","):
        opts = PETSc.Options()
        pre = f"b_{name.replace('-', '_')}_"
        for k_, v in {"ksp_type": a.ksp, "ksp_rtol": "1e-10", "ksp_max_it": "2000", **CONFIGS[name]}.items():
            opts[pre + k_] = v.replace("{gpu_solver}", gsolver)
        try:
            t0 = time.perf_counter()
            G = A.convert(mtype)
            t_conv = time.perf_counter() - t0
            xg, bg = G.createVecs()
            b.copy(bg)
            k = PETSc.KSP().create(comm)
            k.setOptionsPrefix(pre)
            k.setOperators(G)
            k.setFromOptions()
            best = 1e300
            for _ in range(a.repeat):
                xg.set(0.0)
                t0 = time.perf_counter()
                k.solve(bg, xg)
                best = min(best, time.perf_counter() - t0)
            r = k.getConvergedReason()
            d = xg.copy()
            d.axpy(-1.0, x_ref)
            err = d.norm() / max(x_ref.norm(), 1e-300)
            PETSc.Sys.Print(
                f"GPU  {name:24s} solve {best:8.3f} s  conv {t_conv:6.3f} s  "
                f"its {k.getIterationNumber():5d}  motivo {r:3d}  erro {err:.2e}"
            )
        except PETSc.Error as exc:
            PETSc.Sys.Print(f"GPU  {name:24s} erro do PETSc: {str(exc).splitlines()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
