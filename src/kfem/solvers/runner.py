"""Processo do solver (ADR 0009): `mpiexec -n N python -m kfem.solvers.runner PROJETO.kfem [opções]`.

- Comunica com a interface por **linhas JSON em stdout** (só o rank 0 escreve):
  `{"type": "log"|"progress"|"done"|"error"|"cancelled", ...}`.
- **Cancelamento:** SIGTERM/SIGINT ou o arquivo `<workdir>/CANCEL`. O passo em andamento
  termina num ponto seguro e o processo sai com o código 3. A interface nunca é afetada:
  ela só lê esta saída.
- O backend de cálculo vem do ambiente preparado pela interface (`KFEM_COMPUTE_BACKEND`,
  `PETSC_DIR`); quando esse backend falha, o próprio runner refaz o cálculo na CPU (Etapa 11).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

_stop = False


def _on_signal(signum: int, frame: Any) -> None:
    global _stop
    _stop = True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kfem-solver")
    ap.add_argument("project")
    ap.add_argument("--study", default=None)
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--set", action="append", default=[], metavar="PARAM=EXPR", help="sobrescreve parâmetro")
    ap.add_argument("--tlist", default=None, help="sobrescreve os instantes de saída do passo transiente")
    ap.add_argument("--mesh-scale", type=float, default=1.0, help="multiplica os tamanhos de malha (teste rápido)")
    ap.add_argument("--mesh-only", action="store_true", help="só gera a malha (mesh.xdmf)")
    a = ap.parse_args(argv)
    # ADR 0012: 1 thread OpenMP por processo MPI, salvo escolha explícita (evita sobreposição de threads)
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", os.environ["OMP_NUM_THREADS"])

    from mpi4py import MPI

    comm = MPI.COMM_WORLD
    rank0 = comm.rank == 0

    def emit(kind: str, **kw: Any) -> None:
        if rank0:
            sys.stdout.write(json.dumps({"type": kind, **kw}, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    from kfem.io.kfem_format import load

    model = load(a.project)
    if a.mesh_scale != 1.0:
        model.meta["mesh_scale"] = a.mesh_scale
    if a.tlist:
        for st in model.studies.walk():
            if st.kind == "step.time":
                st.props["tlist"] = a.tlist
    study = a.study or (model.studies.children[0].tag if model.studies.children else None)
    if study is None:
        emit("error", message="o projeto não tem estudos")
        return 2
    wd = Path(a.workdir or tempfile.mkdtemp(prefix="kfem-run-"))
    overrides = dict(s.split("=", 1) for s in a.set)
    backend = os.environ.get("KFEM_COMPUTE_BACKEND", "cpu")
    emit(
        "log",
        message=f"KFem solver: estudo '{study}', {comm.size} processo(s) MPI, "
        f"{os.environ.get('OMP_NUM_THREADS', '1')} thread(s) OpenMP, backend {backend}",
    )
    emit("start", workdir=str(wd), backend=backend, procs=comm.size)

    def should_stop() -> bool:
        flag = _stop or (wd / "CANCEL").exists()
        return bool(comm.allreduce(1 if flag else 0, op=MPI.MAX))

    from kfem.solvers.electrochem import Cancelled
    from kfem.solvers.study import run_study

    if a.mesh_only:
        from dolfinx import io

        from kfem.solvers.setup import build_mesh, parameters_si

        try:
            wd.mkdir(parents=True, exist_ok=True)
            md = build_mesh(model, parameters_si(model, overrides), comm, lambda m: emit("log", message=m))
            with io.XDMFFile(comm, str(wd / "mesh.xdmf"), "w") as xf:
                xf.write_mesh(md.mesh)
                xf.write_meshtags(md.cell_tags, md.mesh.geometry)
            areas = {str(k): v for k, v in md.areas.items()}
            emit("log", message=f"áreas dos domínios (m²): {areas}")
            emit("done", workdir=str(wd), summary={"mesh_only": True, "areas": areas, "backend": backend})
            return 0
        except Exception as exc:
            emit("error", message=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
            return 1
    try:
        summary = run_study(
            model,
            study,
            wd,
            log=lambda m: emit("log", message=m),
            progress=lambda f, m: emit("progress", fraction=round(f, 5), message=m),
            should_stop=should_stop,
            overrides=overrides,
        )
    except Cancelled:
        emit("cancelled", message="cálculo cancelado pelo usuário", workdir=str(wd))
        return 3
    except Exception as exc:
        emit("error", message=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
        return 1
    summary["backend"] = backend
    emit("done", workdir=str(wd), summary=summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
