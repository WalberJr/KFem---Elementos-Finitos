"""Teste de sanidade de um backend de cálculo (Etapa 3; ligação real na Etapa 11).

Executado em um **processo separado** (`python -m kfem.hw.sanity <backend>`), com
PETSC_DIR/PYTHONPATH da variante. Se o driver travar ou quebrar, só esse processo morre.
O teste resolve um sistema de Poisson 1D (n=2000) com os tipos de vetor e matriz do backend
e compara com a solução exata do sistema discreto.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

TYPES: dict[str, tuple[str, str]] = {
    "cpu": ("standard", "aij"),
    "cuda": ("cuda", "aijcusparse"),
    "hip": ("hip", "aijhipsparse"),
    "opencl": ("viennacl", "aijviennacl"),
}


def _run_inside(backend: str, n: int = 2000) -> dict[str, object]:
    import numpy as np
    import petsc4py

    petsc4py.init([])
    from petsc4py import PETSc

    vtype, mtype = TYPES[backend]
    A = PETSc.Mat().create(comm=PETSc.COMM_SELF)
    A.setSizes((n, n))
    A.setType(mtype)
    A.setPreallocationNNZ(3)
    for i in range(n):
        A.setValue(i, i, 2.0)
        if i > 0:
            A.setValue(i, i - 1, -1.0)
        if i < n - 1:
            A.setValue(i, i + 1, -1.0)
    A.assemble()
    x_exact = np.sin(np.linspace(0.0, np.pi, n))
    xe = PETSc.Vec().create(comm=PETSc.COMM_SELF)
    xe.setSizes(n)
    xe.setType(vtype)
    xe.setArray(x_exact.tolist())
    b = xe.duplicate()
    A.mult(xe, b)
    x = xe.duplicate()
    ksp = PETSc.KSP().create(comm=PETSc.COMM_SELF)
    ksp.setOperators(A)
    ksp.setType("cg")
    ksp.getPC().setType("jacobi")
    ksp.setTolerances(rtol=1e-12, max_it=20 * n)
    ksp.solve(b, x)
    err = float(np.linalg.norm(x.getArray() - x_exact) / np.linalg.norm(x_exact))
    return {"backend": backend, "err": err, "its": ksp.getIterationNumber(), "vec_type": x.getType()}


def run_sanity(backend: str, env: dict[str, str] | None = None, timeout: float = 60.0) -> tuple[bool, str]:
    """Roda o teste em subprocesso. Passa se o erro relativo for < 1e-6."""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    petsc_dir = full_env.get("PETSC_DIR", "")
    if petsc_dir:
        # só a variante testada no caminho: outra petsc-*/lib herdada carregaria a libpetsc errada
        lib = str(Path(petsc_dir) / "lib")
        for var in ("PYTHONPATH", "LD_LIBRARY_PATH"):
            keep = [p for p in full_env.get(var, "").split(os.pathsep) if p and "/petsc-" not in p]
            full_env[var] = os.pathsep.join([lib, *keep])
    try:
        out = subprocess.run(
            [sys.executable, "-m", "kfem.hw.sanity", backend],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=full_env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"tempo esgotado ({timeout:.0f} s)"
    except OSError as exc:
        return False, str(exc)
    if out.returncode != 0:
        tail = (out.stderr.strip().splitlines() or ["sem saída"])[-1]
        return False, f"processo terminou com código {out.returncode}: {tail}"
    try:
        res = json.loads(out.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return False, "saída inválida"
    err = float(res["err"])
    vt = str(res.get("vec_type", ""))
    # o PETSc informa o subtipo serial/paralelo (seqhip, mpicuda, seqviennacl...)
    if backend != "cpu" and vt.removeprefix("seq").removeprefix("mpi") != TYPES[backend][0]:
        return False, f"vetor não ficou no tipo {TYPES[backend][0]} (obtido {res.get('vec_type')})"
    return err < 1e-6, f"erro relativo {err:.1e} em {res['its']} iterações"


if __name__ == "__main__":
    print(json.dumps(_run_inside(sys.argv[1])))
