"""Etapa 1 — verificação: Poisson com solução analítica, taxa de convergência em L2.

-Δu = f em [0,1]², u = 0 no contorno, u_e = sin(πx)·sin(πy).
Esperado: erro L2 ~ h^(p+1) (P1 → 2, P2 → 3). Roda em serial ou com mpirun -n N.
"""

from __future__ import annotations

import sys

import numpy as np
import ufl
from dolfinx import fem, mesh
from dolfinx.fem.petsc import LinearProblem
from mpi4py import MPI


def solve(n: int, degree: int) -> tuple[float, float]:
    comm = MPI.COMM_WORLD
    domain = mesh.create_unit_square(comm, n, n, mesh.CellType.triangle)
    V = fem.functionspace(domain, ("Lagrange", degree))
    x = ufl.SpatialCoordinate(domain)
    u_ex = ufl.sin(ufl.pi * x[0]) * ufl.sin(ufl.pi * x[1])
    f = 2 * ufl.pi**2 * u_ex
    u, v = ufl.TrialFunction(V), ufl.TestFunction(V)
    a = ufl.inner(ufl.grad(u), ufl.grad(v)) * ufl.dx
    L = f * v * ufl.dx
    tdim = domain.topology.dim
    domain.topology.create_connectivity(tdim - 1, tdim)
    facets = mesh.exterior_facet_indices(domain.topology)
    dofs = fem.locate_dofs_topological(V, tdim - 1, facets)
    bc = fem.dirichletbc(0.0, dofs, V)
    problem = LinearProblem(
        a,
        L,
        bcs=[bc],
        petsc_options_prefix="poisson_",
        petsc_options={"ksp_type": "cg", "pc_type": "hypre", "ksp_rtol": 1e-12},
    )
    uh = problem.solve()
    err = fem.form(ufl.inner(uh - u_ex, uh - u_ex) * ufl.dx)
    e = np.sqrt(comm.allreduce(fem.assemble_scalar(err), op=MPI.SUM))
    return 1.0 / n, e


def main() -> int:
    comm = MPI.COMM_WORLD
    ok = True
    for degree, expected in ((1, 2.0), (2, 3.0)):
        res = [solve(n, degree) for n in (8, 16, 32, 64)]
        rates = [np.log(res[i][1] / res[i + 1][1]) / np.log(res[i][0] / res[i + 1][0]) for i in range(3)]
        if comm.rank == 0:
            print(
                f"P{degree} (procs={comm.size}): erros={[f'{e:.3e}' for _, e in res]} taxas={[f'{r:.2f}' for r in rates]}"
            )
        ok &= abs(rates[-1] - expected) < 0.15
    if comm.rank == 0:
        print("RESULTADO:", "OK" if ok else "FALHOU")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
