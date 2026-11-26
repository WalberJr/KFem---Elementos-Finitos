"""Etapa 11 — montagem da DOLFINx na GPU (HIP) igual à da CPU."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("dolfinx")
from kfem.solvers import gpu_assembly as ga

pytestmark = pytest.mark.fem


def _gpu_or_skip():
    path = ga.find_library()
    if path is None:
        pytest.skip("libkfem_gpu_asm.so ausente")
    try:
        lib = ga._Lib(path)
    except OSError as exc:
        pytest.skip(f"biblioteca HIP não carrega: {exc}")
    import ctypes

    a, n = ctypes.create_string_buffer(64), ctypes.create_string_buffer(256)
    if lib.lib.kga_device(a, 64, n, 256) != 0:
        pytest.skip("sem GPU HIP")


def _problem():
    import basix.ufl
    import ufl
    from dolfinx import fem, mesh
    from mpi4py import MPI

    msh = mesh.create_unit_square(MPI.COMM_WORLD, 12, 10)
    tdim = msh.topology.dim
    nc = msh.topology.index_map(tdim).size_local
    mid = mesh.compute_midpoints(msh, tdim, np.arange(nc, dtype=np.int32))
    tags = mesh.meshtags(msh, tdim, np.arange(nc, dtype=np.int32), np.where(mid[:, 0] < 0.5, 1, 2).astype(np.int32))
    P1 = basix.ufl.element("Lagrange", msh.basix_cell(), 1)
    W = fem.functionspace(msh, basix.ufl.mixed_element([P1, P1]))
    w = fem.Function(W)
    x = ufl.SpatialCoordinate(msh)
    w.sub(0).interpolate(lambda p: 0.3 + 0.2 * p[0])
    w.sub(1).interpolate(lambda p: -0.1 + p[1] ** 2)
    u, c = ufl.split(w)
    v, q = ufl.TestFunctions(W)
    k = fem.Constant(msh, 1.7)
    dx = ufl.Measure("dx", domain=msh, subdomain_data=tags)
    F = (
        ufl.inner(ufl.exp(c) * ufl.grad(u), ufl.grad(v)) * dx(1)
        + k * ufl.inner(ufl.grad(u), ufl.grad(v)) * dx(2)
        + ufl.inner(ufl.grad(c), ufl.grad(q)) * dx
        + (ufl.exp(c) - u * x[0]) * q * dx
    )
    J = ufl.derivative(F, w, ufl.TrialFunction(W))
    facets = mesh.locate_entities_boundary(msh, tdim - 1, lambda p: np.isclose(p[0], 0.0))
    W0, _ = W.sub(0).collapse()
    g = fem.Function(W0)
    g.interpolate(lambda p: 1.0 + p[1])
    dofs = fem.locate_dofs_topological((W.sub(0), W0), tdim - 1, facets)
    bc = fem.dirichletbc(g, dofs, W.sub(0))
    # como o φ_s "inativo" do CDI: dofs de um subespaço fora de uma região, achados por células
    # (próprias + fantasmas), valor 0; em paralelo um dof de fronteira pode ser de Dirichlet num
    # processo e livre no dono
    msh.topology.create_connectivity(tdim, tdim)
    ncg = nc + msh.topology.index_map(tdim).num_ghosts
    midg = mesh.compute_midpoints(msh, tdim, np.arange(ncg, dtype=np.int32))
    inside = np.flatnonzero(midg[:, 0] < 0.6).astype(np.int32)
    d_all = fem.locate_dofs_topological(W.sub(1), tdim, np.arange(ncg, dtype=np.int32))
    d_in = fem.locate_dofs_topological(W.sub(1), tdim, inside)
    inactive = np.setdiff1d(d_all, d_in).astype(np.int32)
    zero = fem.Constant(msh, 0.0)
    bc2 = fem.dirichletbc(zero, inactive, W.sub(1))
    return msh, W, w, F, J, [bc, bc2]


def test_gpu_matches_dolfinx():
    _gpu_or_skip()
    from dolfinx import fem
    from dolfinx.fem import petsc as fpetsc
    from petsc4py import PETSc

    msh, W, w, F, J, bcs = _problem()
    Jf, Ff = fem.form(J), fem.form(F)
    asm = ga.GpuAssembler(msh.comm, J, F, Jf, Ff, bcs)

    A_ref = fpetsc.assemble_matrix(Jf, bcs=bcs)
    A_ref.assemble()
    A = fpetsc.create_matrix(Jf)
    g = np.zeros(asm.n_local)
    for bc in bcs:
        bc.set(g, x0=w.x.array, alpha=1.0)
    (lift,) = asm.assemble_matrix(A, [g])
    D = A.copy()
    D.axpy(-1.0, A_ref)
    assert D.norm() <= 1e-12 * A_ref.norm()

    b_ref = fpetsc.assemble_vector(Ff)
    fpetsc.apply_lifting(b_ref, [Jf], bcs=[bcs], x0=[w.x.petsc_vec], alpha=-1.0)
    b_ref.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
    fpetsc.set_bc(b_ref, bcs, w.x.petsc_vec, -1.0)

    b = fpetsc.create_vector(W)
    with b.localForm() as bl:
        arr = bl.array_w
        arr[:] = 0.0
        asm.assemble_vector(arr)
        arr += lift  # lifting com alpha = −1: b += A (g − w)
    b.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
    fpetsc.set_bc(b, bcs, w.x.petsc_vec, -1.0)
    assert np.allclose(b.array, b_ref.array, rtol=1e-11, atol=1e-13 * np.abs(b_ref.array).max())
    asm.free()


def test_translation_helpers():
    code = (
        "void tabulate_tensor_integral_ab(double* restrict A)\n{\n{\nA[0] += 1.0;\n}\n\n}\n\n"
        "bool enabled_coefficients_integral_ab[1] = {0};\n"
        "int form_integral_offsets_form_x[6] = {0, 1, 1, 1, 1, 1};\n"
        "static ufcx_integral* form_integrals_form_x[1] = {&integral_ab};\n"
    )
    ks = ga.extract_kernels(code)
    assert ks[0][0] == "tabulate_tensor_integral_ab"
    assert ks[0][1].count("{") == ks[0][1].count("}")  # bloco interno na coluna 0 não corta a função
    assert ga.integral_order(code) == ["integral_ab"]
    assert ga.integral_types(code) == [0, 1, 1, 1, 1, 1]
    assert "__restrict__" in ga.to_hip(ks[0][0], ks[0][1], "tt0")
