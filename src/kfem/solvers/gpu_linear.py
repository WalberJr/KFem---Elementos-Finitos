"""Solver linear híbrido GPU/CPU para os sistemas do Newton (Etapa 11).

A montagem da DOLFINx fica na CPU. A cada iteração a matriz montada (AIJ) é convertida para
o tipo de GPU do backend escolhido (ViennaCL/OpenCL, cuSPARSE/CUDA ou hipSPARSE/HIP) e
resolvida com um método de Krylov na GPU. Se o Krylov não convergir, o mesmo sistema é
resolvido na CPU com o solver direto (MUMPS): o passo de tempo não é perdido. Depois de
muitas falhas seguidas a GPU é desligada no resto do cálculo, com o motivo no log.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

MAT_TYPES = {"opencl": "aijviennacl", "cuda": "aijcusparse", "hip": "aijhipsparse"}


def gpu_backend(env: dict[str, str] | None = None) -> str | None:
    """Backend de GPU pedido pelo ambiente (`KFEM_COMPUTE_BACKEND`), ou None para CPU."""
    b = (env if env is not None else os.environ).get("KFEM_COMPUTE_BACKEND", "cpu")
    return b if b in MAT_TYPES else None


def default_gpu_options(backend: str, nprocs: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Opções do Krylov na GPU. `KFEM_GPU_OPTS="chave=valor ..."` (sem o hífen) sobrescreve."""
    base: dict[str, Any] = {"ksp_type": "gmres", "ksp_gmres_restart": 100, "ksp_rtol": 1e-10, "ksp_max_it": 600}
    if backend == "opencl":
        # Chow–Patel ILU (granulação fina) só existe para ViennaCL em serial
        base["pc_type"] = "chowiluviennacl" if nprocs == 1 else "jacobi"
    elif nprocs == 1:
        # ILU(0) com fatoração e substituições triangulares na GPU (cuSPARSE/hipSPARSE)
        base.update(pc_type="ilu", pc_factor_mat_solver_type="cusparse" if backend == "cuda" else "hipsparse")
    else:
        base.update(pc_type="bjacobi", sub_pc_type="ilu")
    for item in (env if env is not None else os.environ).get("KFEM_GPU_OPTS", "").split():
        k, _, v = item.partition("=")
        base[k.lstrip("-")] = v
    return base


class HybridLinearSolver:
    def __init__(
        self,
        comm: Any,
        cpu_ksp: Any,
        backend: str,
        options: dict[str, Any] | None = None,
        log: Callable[[str], None] = print,
        max_consecutive_failures: int = 8,
        calibrate: int = 6,
    ) -> None:
        from petsc4py import PETSc

        self.PETSc = PETSc
        self.comm = comm
        self.cpu = cpu_ksp
        self.backend = backend
        self.mat_type = MAT_TYPES[backend]
        self.log = log
        self.enabled = True
        self.max_fail = max_consecutive_failures
        self.n_gpu = self.n_cpu = self.n_fail = self.gpu_its = 0
        self._consecutive = 0
        self._A: Any = None
        self._Ag: Any = None
        self._ksp: Any = None
        self._bg: Any = None
        self._xg: Any = None
        self._cpu_pending = True
        # calibração: nos primeiros sistemas resolve nos dois e fica com o mais rápido
        # (numa GPU modesta, ou num problema pequeno, o direto da CPU costuma ganhar)
        self.calibrate = calibrate
        self._t_gpu: list[float] = []
        self._t_cpu: list[float] = []
        prefix = "kfem_gpu_"
        opts = PETSc.Options()
        for k, v in (options or default_gpu_options(backend, comm.size)).items():
            opts[f"{prefix}{k}"] = v
        self._prefix = prefix

    def set_cpu_ksp(self, ksp: Any) -> None:
        self.cpu = ksp
        self._cpu_pending = True

    def set_operator(self, A: Any) -> None:
        self._A = A
        self._cpu_pending = True
        if not self.enabled:
            return
        try:
            self._Ag = A.convert(self.mat_type, self._Ag) if self._Ag is not None else A.convert(self.mat_type)
            if self._ksp is None:
                k = self.PETSc.KSP().create(self.comm)
                k.setOptionsPrefix(self._prefix)
                k.setOperators(self._Ag)
                k.setFromOptions()
                self._ksp = k
                self._xg, self._bg = self._Ag.createVecs()
            else:
                self._ksp.setOperators(self._Ag)
        except self.PETSc.Error as exc:
            self._disable(f"conversão da matriz para {self.mat_type} falhou ({exc})")

    def _disable(self, why: str) -> None:
        if self.enabled:
            self.enabled = False
            self.log(f"GPU ({self.backend}) desligada no resto do cálculo: {why}; seguindo na CPU")

    def solve(self, b: Any, x: Any) -> None:
        if self.enabled and self._ksp is not None:
            try:
                t0 = time.perf_counter()
                b.copy(self._bg)
                self._xg.set(0.0)
                self._ksp.solve(self._bg, self._xg)
                reason = self._ksp.getConvergedReason()
                if reason > 0:
                    self._xg.copy(x)
                    tg = time.perf_counter() - t0
                    self.n_gpu += 1
                    self.gpu_its += self._ksp.getIterationNumber()
                    self._consecutive = 0
                    if len(self._t_gpu) < self.calibrate:
                        self._calibrate_step(b, tg)
                    return
                self.n_fail += 1
                self._consecutive += 1
                if self._consecutive >= self.max_fail:
                    self._disable(f"{self._consecutive} sistemas seguidos sem convergir no Krylov (motivo {reason})")
            except self.PETSc.Error as exc:
                self.n_fail += 1
                self._disable(f"erro do PETSc na GPU ({str(exc).splitlines()[0]})")
        if self._cpu_pending:
            self.cpu.setOperators(self._A)
            self._cpu_pending = False
        self.cpu.solve(b, x)
        if self.cpu.getConvergedReason() < 0:
            raise RuntimeError(f"solver linear falhou (motivo {self.cpu.getConvergedReason()})")
        self.n_cpu += 1

    def _calibrate_step(self, b: Any, tg: float) -> None:
        """Mede também o solve da CPU neste sistema; ao fim da calibração decide."""
        xc = b.duplicate()
        t0 = time.perf_counter()
        if self._cpu_pending:
            self.cpu.setOperators(self._A)
            self._cpu_pending = False
        self.cpu.solve(b, xc)
        tc = time.perf_counter() - t0
        xc.destroy()
        # cada processo decide igual: usa o maior tempo entre os processos
        self._t_gpu.append(self.comm.tompi4py().allreduce(tg, op=_mpi_max()) if self.comm.size > 1 else tg)
        self._t_cpu.append(self.comm.tompi4py().allreduce(tc, op=_mpi_max()) if self.comm.size > 1 else tc)
        if len(self._t_gpu) == self.calibrate:
            # soma sobre os mesmos sistemas: a CPU reaproveita a fatoração LU entre o solve do
            # Newton e o da sensibilidade, a GPU refaz o Krylov; comparar a soma é o justo
            g, c = sum(self._t_gpu), sum(self._t_cpu)
            if g >= c:
                self._disable(
                    f"a CPU foi mais rápida na calibração ({c:.3f} s contra {g:.3f} s na GPU, "
                    f"em {self.calibrate} sistemas)"
                )
            else:
                self.log(
                    f"GPU ({self.backend}) mantida: {g:.3f} s contra {c:.3f} s na CPU em {self.calibrate} sistemas"
                )

    def report(self) -> str:
        tot = self.n_gpu + self.n_cpu
        avg = self.gpu_its / self.n_gpu if self.n_gpu else 0.0
        return (
            f"sistemas lineares: {self.n_gpu}/{tot} na GPU ({self.backend}, {self.mat_type}, "
            f"{avg:.0f} iterações de Krylov em média), {self.n_cpu} na CPU, {self.n_fail} falhas do Krylov na GPU"
        )


def _mpi_max() -> Any:
    from mpi4py import MPI

    return MPI.MAX
