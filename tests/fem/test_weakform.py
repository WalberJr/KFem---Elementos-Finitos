"""Fase M0/M1 — motor genérico de formas fracas: soluções manufaturadas (MMS)."""

from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("dolfinx")
pytestmark = pytest.mark.fem


def _square(n: int):
    from dolfinx import mesh
    from mpi4py import MPI

    msh = mesh.create_unit_square(MPI.COMM_WORLD, n, n)
    tdim = msh.topology.dim
    nc = msh.topology.index_map(tdim).size_local
    ct = mesh.meshtags(msh, tdim, np.arange(nc, dtype=np.int32), np.ones(nc, dtype=np.int32))
    msh.topology.create_connectivity(tdim - 1, tdim)
    fac = mesh.exterior_facet_indices(msh.topology)
    ft = mesh.meshtags(msh, tdim - 1, fac, np.ones(len(fac), dtype=np.int32))
    return msh, ct, ft


def _l2_error(prob, field: str, exact: str) -> float:
    import ufl
    from dolfinx import fem
    from mpi4py import MPI

    from kfem.physics.expr_ufl import to_ufl

    ue = to_ufl(exact, prob.syms, prob.funcs)
    e = fem.form((prob.u_of[field] - ue) ** 2 * ufl.dx(domain=prob.mesh))
    return math.sqrt(prob.mesh.comm.allreduce(fem.assemble_scalar(e), op=MPI.SUM))


def _rate(errs: list[float]) -> float:
    return math.log2(errs[-2] / errs[-1])


@pytest.mark.parametrize("order, expected", [(1, 2.0), (2, 3.0)])
def test_poisson_convergence(order: int, expected: float) -> None:
    from kfem.solvers.weakform import BCSpec, WeakProblem

    exact = "sin(pi*x)*sin(pi*y)"
    errs = []
    for n in (8, 16, 32):
        msh, ct, ft = _square(n)
        prob = WeakProblem(
            msh,
            ct,
            ft,
            ["u"],
            ["inner(grad(u), grad(test(u)))*dx - 2*pi^2*sin(pi*x)*sin(pi*y)*test(u)*dx"],
            bcs=[BCSpec("u", "0", [1])],
            order=order,
        )
        prob.solve_stationary()
        errs.append(_l2_error(prob, "u", exact))
    assert abs(_rate(errs) - expected) < 0.25, errs


def test_nonlinear_diffusion_exact() -> None:
    """−∇·((1+u²)∇u) = −10u com u = 1 + x + 2y (linear: P1 exato)."""
    from kfem.solvers.weakform import BCSpec, WeakProblem

    msh, ct, ft = _square(10)
    exact = "1 + x + 2*y"
    prob = WeakProblem(
        msh,
        ct,
        ft,
        ["u"],
        ["inner((1 + u^2)*grad(u), grad(test(u)))*dx + 10*(1 + x + 2*y)*test(u)*dx"],
        bcs=[BCSpec("u", exact, [1])],
        initial={"u": "1"},
    )
    its = prob.solve_stationary()
    assert its >= 2  # o problema é de fato não linear
    assert _l2_error(prob, "u", exact) < 1e-10


def test_transient_heat_exact() -> None:
    """∂u/∂t − Δu = f, u = (1+x²+y²)(1+t): BDF exato no tempo, P2 exato no espaço."""
    from kfem.solvers.weakform import BCSpec, WeakProblem

    msh, ct, ft = _square(6)
    exact = "(1 + x^2 + y^2)*(1 + t)"
    prob = WeakProblem(
        msh,
        ct,
        ft,
        ["u"],
        ["dt(u)*test(u)*dx + inner(grad(u), grad(test(u)))*dx - ((1 + x^2 + y^2) - 4*(1 + t))*test(u)*dx"],
        bcs=[BCSpec("u", exact, [1])],
        initial={"u": "1 + x^2 + y^2"},
        order=2,
        transient=True,
    )
    res = prob.solve_transient([0.0, 0.5, 1.0], substeps=4)
    assert res.steps == 8 and res.times == [0.0, 0.5, 1.0]
    assert _l2_error(prob, "u", exact) < 1e-9


def test_two_fields_coupled() -> None:
    """Sistema acoplado de dois campos: −Δu = v, −Δv = f (biharmônico em forma mista)."""
    from kfem.solvers.weakform import BCSpec, WeakProblem

    # u = x(1−x)y(1−y) ⇒ v = −Δu = 2[x(1−x) + y(1−y)], f = −Δv = 8
    errs = []
    for n in (8, 16):
        msh, ct, ft = _square(n)
        prob = WeakProblem(
            msh,
            ct,
            ft,
            ["u", "v"],
            [
                "inner(grad(u), grad(test(u)))*dx - v*test(u)*dx",
                "inner(grad(v), grad(test(v)))*dx - 8*test(v)*dx",
            ],
            bcs=[BCSpec("u", "0", [1]), BCSpec("v", "2*(x*(1-x) + y*(1-y))", [1])],
            order=2,
        )
        prob.solve_stationary()
        errs.append(_l2_error(prob, "u", "x*(1-x)*y*(1-y)"))
    assert errs[-1] < 1e-9 or _rate(errs) > 2.5, errs


def test_safety_and_errors() -> None:
    from kfem.model.expressions import ExpressionError
    from kfem.solvers.weakform import WeakProblem

    msh, ct, ft = _square(4)
    with pytest.raises(ExpressionError):  # sem medida: não é integral
        WeakProblem(msh, ct, ft, ["u"], ["u*test(u)"])
    with pytest.raises(ExpressionError):  # nada de código: só a gramática de expressões
        WeakProblem(msh, ct, ft, ["u"], ["__import__('os')*dx"])
    with pytest.raises(ExpressionError):
        WeakProblem(msh, ct, ft, ["1u"], ["u*dx"])


def test_dt_of_expression_log_variable() -> None:
    """Variável em ln: c = exp(u), com dt(exp(u)) — mesma solução do problema em c."""
    from kfem.solvers.weakform import BCSpec, WeakProblem

    msh, ct, ft = _square(6)
    exact = "(1 + x^2 + y^2)*(1 + t)"
    c = "exp(u)"
    prob = WeakProblem(
        msh,
        ct,
        ft,
        ["u"],
        [f"dt({c})*test(u)*dx + inner(grad({c}), grad(test(u)))*dx - ((1 + x^2 + y^2) - 4*(1 + t))*test(u)*dx"],
        bcs=[BCSpec("u", f"log({exact})", [1])],
        initial={"u": "log(1 + x^2 + y^2)"},
        order=2,
        transient=True,
    )
    prob.solve_transient([0.0, 0.5, 1.0], substeps=8)
    import ufl
    from dolfinx import fem
    from mpi4py import MPI

    from kfem.physics.expr_ufl import to_ufl

    ue = to_ufl(exact, prob.syms, prob.funcs)
    e = fem.form((ufl.exp(prob.u_of["u"]) - ue) ** 2 * ufl.dx(domain=msh))
    err = math.sqrt(msh.comm.allreduce(fem.assemble_scalar(e), op=MPI.SUM))
    assert err < 2e-3, err  # P2 em ln c não é exato (c não é polinomial em u), mas converge
