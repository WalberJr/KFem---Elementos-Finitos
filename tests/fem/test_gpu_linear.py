"""Etapa 11 — solver linear híbrido: GPU quando der, CPU (direto) quando não."""

from __future__ import annotations

import numpy as np
import pytest

from kfem.solvers.gpu_linear import HybridLinearSolver, default_gpu_options, gpu_backend

PETSc = pytest.importorskip("petsc4py.PETSc")
pytestmark = pytest.mark.fem


def test_backend_from_env():
    assert gpu_backend({"KFEM_COMPUTE_BACKEND": "opencl"}) == "opencl"
    assert gpu_backend({"KFEM_COMPUTE_BACKEND": "cpu"}) is None
    assert gpu_backend({}) is None
    assert default_gpu_options("opencl", 1, {})["pc_type"] == "chowiluviennacl"
    assert default_gpu_options("opencl", 4, {})["pc_type"] == "jacobi"
    assert default_gpu_options("hip", 1, {})["pc_factor_mat_solver_type"] == "hipsparse"
    o = default_gpu_options("hip", 1, {"KFEM_GPU_OPTS": "pc_type=jacobi -ksp_rtol=1e-8"})
    assert o["pc_type"] == "jacobi" and o["ksp_rtol"] == "1e-8"


def _system(n=50):
    A = PETSc.Mat().createAIJ([n, n], nnz=3, comm=PETSc.COMM_SELF)
    for i in range(n):
        A.setValue(i, i, 4.0)
        if i > 0:
            A.setValue(i, i - 1, -1.0)
        if i < n - 1:
            A.setValue(i, i + 1, -1.0)
    A.assemble()
    x_ref, b = A.createVecs()
    x_ref.setArray(np.linspace(1, 2, n))
    A.mult(x_ref, b)
    return A, b, x_ref


def _cpu_ksp(A):
    k = PETSc.KSP().create(PETSc.COMM_SELF)
    k.setType("preonly")
    k.getPC().setType("lu")
    k.setOperators(A)
    return k


def test_hybrid_solves_on_gpu_or_falls_back_to_cpu():
    A, b, x_ref = _system()
    msgs: list[str] = []
    lin = HybridLinearSolver(PETSc.COMM_SELF, _cpu_ksp(A), "opencl", log=msgs.append)
    x = x_ref.duplicate()
    for _ in range(2):
        lin.set_operator(A)
        lin.solve(b, x)
        assert np.allclose(x.array, x_ref.array, rtol=1e-8)
    assert lin.n_gpu + lin.n_cpu == 2
    if "viennacl" not in PETSc.Sys.getVersionInfo().get("configure", "") and lin.n_cpu:
        assert not lin.enabled and msgs  # variante sem ViennaCL: desliga a GPU e avisa
    assert "sistemas lineares" in lin.report()
