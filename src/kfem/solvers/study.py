"""Execução de um estudo: passos em sequência, com saídas em disco (Etapas 6 e 9).

Saídas no diretório de trabalho:
- `mesh.xdmf`: malha com marcadores;
- `flow.bp`: campos do escoamento (VTX/ADIOS2);
- `fields.bp`: campos do transiente nos instantes de saída;
- `globals.csv`: grandezas globais (V, corrente, concentrações médias…) por instante;
- `summary.json`: tempos de execução, backend usado e número de passos.
"""

from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kfem.model.tree import Model, Node


def run_study(
    model: Model,
    study_tag: str,
    workdir: str | Path,
    *,
    log: Callable[[str], None] = print,
    progress: Callable[[float, str], None] | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from dolfinx import io
    from mpi4py import MPI

    from kfem.solvers.electrochem import solve_transient
    from kfem.solvers.flow import solve_brinkman
    from kfem.solvers.setup import Materials, build_mesh, parameters_si

    comm = MPI.COMM_WORLD
    wd = Path(workdir)
    if comm.rank == 0:
        wd.mkdir(parents=True, exist_ok=True)
    comm.barrier()
    t0 = time.time()
    study: Node = model.studies.child(study_tag)
    si = parameters_si(model, overrides)
    md = build_mesh(model, si, comm, log)
    with io.XDMFFile(comm, str(wd / "mesh.xdmf"), "w") as xf:
        xf.write_mesh(md.mesh)
        md.mesh.topology.create_connectivity(md.mesh.topology.dim - 1, md.mesh.topology.dim)
        xf.write_meshtags(md.cell_tags, md.mesh.geometry)
        xf.write_meshtags(md.facet_tags, md.mesh.geometry)
    mats = Materials(model, md)
    velocity = None
    summary: dict[str, Any] = {"study": study_tag, "mpi_procs": comm.size, "steps": []}
    steps = [s for s in study.active_children("step.")]
    # peso de cada passo na barra de progresso: um transiente custa muito mais que um
    # estacionário (no CDI, horas contra segundos); pesos iguais deixavam a barra em 50% no
    # início do transiente
    weights = [20.0 if s.kind == "step.time" else 1.0 for s in steps]
    edges = [sum(weights[:k]) / sum(weights) for k in range(len(steps) + 1)] if steps else [0.0]
    for k, step in enumerate(steps):
        frac0, frac1 = edges[k], edges[k + 1]

        def sub_progress(f: float, msg: str, frac0: float = frac0, frac1: float = frac1) -> None:
            if progress:
                progress(frac0 + (frac1 - frac0) * f, msg)

        phys = [model.comp.physics.child(t) for t in step.props.get("physics", [])]
        log(f"passo '{step.label or step.tag}': físicas {', '.join(p.tag for p in phys)}")
        ts = time.time()
        from kfem.solvers.weakform import GENERIC_KINDS
        from kfem.solvers.weakform import solve_model as solve_generic

        generic = [p for p in phys if p.kind in GENERIC_KINDS]
        if generic and step.kind in ("step.stationary", "step.time"):
            if len(generic) != len(phys):
                raise NotImplementedError(
                    "misturar a equação personalizada com as físicas do CDI no mesmo passo ainda não é suportado"
                )
            gxdmf: dict[str, str] = {}

            def gen_out(t: float, fields: dict[str, Any], gxdmf: dict[str, str] = gxdmf) -> None:
                for nm, f in fields.items():  # abre/fecha a cada saída: legível durante o cálculo
                    path = str(wd / f"field_{nm}.xdmf")
                    with io.XDMFFile(comm, path, "a" if nm in gxdmf else "w") as xf:
                        if nm not in gxdmf:
                            xf.write_mesh(md.mesh)
                            gxdmf[nm] = path
                        xf.write_function(f, t)

            gres = solve_generic(
                model, step, generic, md, si, gen_out, log=log, progress=sub_progress, should_stop=should_stop
            )
            summary["steps"].append(
                {
                    "step": step.tag,
                    "kind": "stationary" if step.kind == "step.stationary" else "time",
                    "wall_s": time.time() - ts,
                    "accepted": gres.steps,
                    "newton": gres.newton_its,
                }
            )
            sub_progress(1.0, "equação personalizada resolvida")
            continue
        if step.kind == "step.stationary":
            br = next((p for p in phys if p.kind == "physics.brinkman"), None)
            if br is None:
                raise NotImplementedError("passo estacionário sem escoamento não é suportado nesta versão")
            uh, ph = solve_brinkman(br, md, mats, si, log)
            velocity = uh
            with io.VTXWriter(comm, str(wd / "flow.bp"), [uh], engine="BP4") as vtx:
                vtx.write(0.0)
            with io.VTXWriter(comm, str(wd / "pressure.bp"), [ph], engine="BP4") as vtx:
                vtx.write(0.0)
            _write_flow_xdmf(comm, wd, md, uh, ph)
            summary["steps"].append({"step": step.tag, "kind": "stationary", "wall_s": time.time() - ts})
            sub_progress(1.0, "escoamento resolvido")
        elif step.kind == "step.time":
            writer: list[Any] = []
            xdmfs: dict[str, Any] = {}  # um XDMF por campo (o leitor espera um campo por grade)

            def on_output(t: float, fields: dict[str, Any], vals: dict[str, float]) -> None:
                # Abre e fecha o arquivo a cada instante: o HDF5 só fica legível fechado, e
                # assim a interface consegue mostrar os campos durante o cálculo.
                for nm, f in fields.items():
                    path = str(wd / f"field_{nm}.xdmf")
                    with io.XDMFFile(comm, path, "a" if nm in xdmfs else "w") as xf:
                        if nm not in xdmfs:
                            xf.write_mesh(md.mesh)
                            xdmfs[nm] = path
                        xf.write_function(f, t)
                if not writer:
                    writer.append(io.VTXWriter(comm, str(wd / "fields.bp"), list(fields.values()), engine="BP4"))
                    writer.append(list(fields.values()))
                else:  # atualiza as funções registradas no escritor
                    for f_old, f_new in zip(writer[1], fields.values(), strict=True):
                        f_old.x.array[:] = f_new.x.array
                writer[0].write(t)

            res = solve_transient(
                model,
                step,
                md,
                mats,
                si,
                velocity,
                on_output=on_output,
                log=log,
                progress=sub_progress,
                should_stop=should_stop,
            )
            if writer:
                writer[0].close()
            if comm.rank == 0:
                keys = list(res.globals)
                with open(wd / "globals.csv", "w", newline="") as fh:
                    wr = csv.writer(fh)
                    wr.writerow(keys)
                    for i in range(len(res.globals["t"])):
                        wr.writerow([res.globals[k][i] for k in keys])
            summary["steps"].append(
                {
                    "step": step.tag,
                    "kind": "time",
                    "wall_s": time.time() - ts,
                    "accepted": res.steps,
                    "rejected": res.rejected,
                    "newton": res.newton_its,
                }
            )
        else:
            log(f"passo {step.tag} ({step.kind}) ignorado nesta versão")
    summary["wall_s"] = time.time() - t0
    if comm.rank == 0:
        (wd / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def _write_flow_xdmf(comm: Any, wd: Path, md: Any, uh: Any, ph: Any) -> None:
    """Escoamento em XDMF (P1) para a visualização: o XDMF exige o grau da malha."""
    import basix.ufl
    from dolfinx import fem, io

    gdim = md.mesh.geometry.dim
    V1 = fem.functionspace(md.mesh, basix.ufl.element("Lagrange", md.mesh.basix_cell(), 1, shape=(gdim,)))
    Q1 = fem.functionspace(md.mesh, ("Lagrange", 1))
    u1, p1 = fem.Function(V1, name="u"), fem.Function(Q1, name="p")
    u1.interpolate(uh)
    p1.interpolate(ph)
    for nm, f in (("u", u1), ("p", p1)):
        with io.XDMFFile(comm, str(wd / f"field_{nm}.xdmf"), "w") as xf:
            xf.write_mesh(md.mesh)
            xf.write_function(f, 0.0)
