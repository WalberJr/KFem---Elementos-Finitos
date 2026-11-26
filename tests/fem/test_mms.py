"""Etapa 6 — soluções manufaturadas (MMS) para as formas fracas usadas pelo solver.

Brinkman (Taylor–Hood), condução (corrente secundária) e Nernst–Planck com convecção e
migração (P1 + SUPG). Erro em L2 cai na taxa esperada.
"""

from __future__ import annotations

import numpy as np
import pytest

dolfinx = pytest.importorskip("dolfinx")
pytestmark = pytest.mark.fem

import basix.ufl  # noqa: E402
import ufl  # noqa: E402
from dolfinx import fem, mesh  # noqa: E402
from dolfinx.fem.petsc import LinearProblem, NonlinearProblem  # noqa: E402
from mpi4py import MPI  # noqa: E402

LU = {"ksp_type": "preonly", "pc_type": "lu", "pc_factor_mat_solver_type": "mumps"}


def rates(errs, hs):
    return [np.log(errs[i] / errs[i + 1]) / np.log(hs[i] / hs[i + 1]) for i in range(len(errs) - 1)]


def l2(e):
    return np.sqrt(MPI.COMM_WORLD.allreduce(fem.assemble_scalar(fem.form(ufl.inner(e, e) * ufl.dx)), op=MPI.SUM))


def all_boundary_dofs(V, msh, sub=None):
    tdim = msh.topology.dim
    msh.topology.create_connectivity(tdim - 1, tdim)
    facets = mesh.exterior_facet_indices(msh.topology)
    return fem.locate_dofs_topological(V, tdim - 1, facets)


def brinkman_error(n: int) -> float:
    msh = mesh.create_unit_square(MPI.COMM_WORLD, n, n)
    x = ufl.SpatialCoordinate(msh)
    mu, eps, kinv = 1.0, 0.4, 50.0
    ue = ufl.as_vector(
        [ufl.sin(ufl.pi * x[1]) * ufl.cos(ufl.pi * x[0]), -ufl.sin(ufl.pi * x[0]) * ufl.cos(ufl.pi * x[1])]
    )
    pe = ufl.cos(ufl.pi * x[0]) * ufl.cos(ufl.pi * x[1])
    sig = (mu / eps) * (ufl.grad(ue) + ufl.grad(ue).T) - pe * ufl.Identity(2)
    f = -ufl.div(sig) + mu * kinv * ue
    W = fem.functionspace(
        msh,
        basix.ufl.mixed_element(
            [
                basix.ufl.element("Lagrange", msh.basix_cell(), 2, shape=(2,)),
                basix.ufl.element("Lagrange", msh.basix_cell(), 1),
            ]
        ),
    )
    (u, p), (v, q) = ufl.TrialFunctions(W), ufl.TestFunctions(W)
    a = (
        ufl.inner((mu / eps) * (ufl.grad(u) + ufl.grad(u).T), ufl.grad(v))
        + mu * kinv * ufl.inner(u, v)
        - p * ufl.div(v)
        - q * ufl.div(u)
    ) * ufl.dx
    nrm = ufl.FacetNormal(msh)
    L = ufl.inner(f, v) * ufl.dx
    V0, _ = W.sub(0).collapse()
    g = fem.Function(V0)
    g.interpolate(fem.Expression(ue, V0.element.interpolation_points))
    dofs = fem.locate_dofs_topological(
        (W.sub(0), V0), 1, mesh.locate_entities_boundary(msh, 1, lambda X: X[0] < 1.0 - 1e-12)
    )
    # contorno x=1: tensão imposta (natural), como na saída do caso CDI
    L += ufl.inner(sig * nrm, v) * ufl.ds
    wh = LinearProblem(
        a, L, bcs=[fem.dirichletbc(g, dofs, W.sub(0))], petsc_options=LU, petsc_options_prefix="mmsb_"
    ).solve()
    wh = wh[0] if isinstance(wh, tuple) else wh
    return l2(wh.sub(0).collapse() - ue)


def test_brinkman_taylor_hood_rate():
    ns = [8, 16, 32]
    e = [brinkman_error(n) for n in ns]
    r = rates(e, [1 / n for n in ns])
    assert r[-1] > 2.8, (e, r)


def conduction_error(n: int) -> float:
    msh = mesh.create_unit_square(MPI.COMM_WORLD, n, n)
    x = ufl.SpatialCoordinate(msh)
    sig = 0.4**1.5 * (1 + x[0])  # condutividade variável (como σ_l(c))
    ue = ufl.exp(x[0]) * ufl.sin(2 * x[1])
    f = -ufl.div(sig * ufl.grad(ue))
    V = fem.functionspace(msh, ("Lagrange", 1))
    u, v = ufl.TrialFunction(V), ufl.TestFunction(V)
    g = fem.Function(V)
    g.interpolate(fem.Expression(ue, V.element.interpolation_points))
    bc = fem.dirichletbc(g, all_boundary_dofs(V, msh))
    uh = LinearProblem(
        sig * ufl.inner(ufl.grad(u), ufl.grad(v)) * ufl.dx,
        f * v * ufl.dx,
        bcs=[bc],
        petsc_options=LU,
        petsc_options_prefix="mmsc_",
    ).solve()
    uh = uh[0] if isinstance(uh, tuple) else uh
    return l2(uh - ue)


def test_conduction_rate():
    ns = [8, 16, 32, 64]
    r = rates([conduction_error(n) for n in ns], [1 / n for n in ns])
    assert abs(r[-1] - 2.0) < 0.15


def nernst_planck_error(n: int, supg: bool) -> float:
    """−∇·(D∇c + zD F/(RT) c ∇φ) + u·∇c = f, com φ dado (não linear em c via migração com c)."""
    msh = mesh.create_unit_square(MPI.COMM_WORLD, n, n)
    x = ufl.SpatialCoordinate(msh)
    D, z, FRT = 1e-2, 1.0, 38.9
    uvel = ufl.as_vector([1.0, 0.3])
    phi = 0.02 * ufl.sin(ufl.pi * x[0]) * x[1]
    ce = 1 + 0.5 * ufl.sin(ufl.pi * x[0]) * ufl.cos(ufl.pi * x[1])
    flux_e = D * ufl.grad(ce) + z * D * FRT * ce * ufl.grad(phi)
    f = -ufl.div(flux_e) + ufl.inner(uvel, ufl.grad(ce))
    V = fem.functionspace(msh, ("Lagrange", 1))
    c, ct = fem.Function(V), ufl.TestFunction(V)
    c.x.array[:] = 1.0
    flux = D * ufl.grad(c) + z * D * FRT * c * ufl.grad(phi)
    F = (ufl.inner(flux, ufl.grad(ct)) + ufl.inner(uvel, ufl.grad(c)) * ct - f * ct) * ufl.dx
    if supg:
        h = ufl.CellDiameter(msh)
        un = ufl.sqrt(ufl.inner(uvel, uvel))
        tau = h / (2 * un) * ufl.min_value(un * h / (2 * D) / 3.0, 1.0)
        F += tau * (ufl.inner(uvel, ufl.grad(c)) - f) * ufl.inner(uvel, ufl.grad(ct)) * ufl.dx
    g = fem.Function(V)
    g.interpolate(fem.Expression(ce, V.element.interpolation_points))
    bc = fem.dirichletbc(g, all_boundary_dofs(V, msh))
    prob = NonlinearProblem(F, c, bcs=[bc], petsc_options_prefix="mmsnp_", petsc_options={"snes_rtol": 1e-10, **LU})
    prob.solve()
    return l2(c - ce)


@pytest.mark.parametrize("supg", [False, True])
def test_nernst_planck_rate(supg):
    ns = [16, 32, 64]
    r = rates([nernst_planck_error(n, supg) for n in ns], [1 / n for n in ns])
    assert r[-1] > 1.8, r
