"""Fase M1 — equação personalizada pelo caminho completo: modelo → malha → estudo → XDMF."""

from __future__ import annotations

import json

import numpy as np
import pytest

pytest.importorskip("dolfinx")
pytestmark = pytest.mark.fem


def _model(step_kind: str = "step.stationary"):
    from kfem.model.catalog import CATALOG
    from kfem.model.tree import Model, Node, Selection

    def n(kind, tag, sel=None, **props):
        base = CATALOG[kind].defaults()
        base.update(props)
        return Node(kind, tag, CATALOG[kind].label, props=base, selection=sel)

    m = Model(name="Placa aquecida")
    m.parameters.add("k", "2[W/(m*K)]", "condutividade")
    m.parameters.add("q", "10[W/m^3]", "fonte volumétrica")
    c = m.comp
    c.length_unit = "m"
    c.geometry.add(n("geom.rectangle", "r1", x="0", y="0", width="1", height="1"))
    c.geometry.add(n("geom.form_union", "fin"))
    wf = c.physics.add(
        n(
            "physics.weakform",
            "wf",
            Selection(2),
            fields="T",
            equation="dt(T)*test(T)*dx + k*inner(grad(T), grad(test(T)))*dx - q*test(T)*dx",
        )
    )
    wf.add(n("weakform.dirichlet", "d1", Selection(1), field="T", value="0"))
    wf.add(n("weakform.initial", "i1", Selection(2), field="T", value="0"))
    c.mesh.add(n("mesh.size", "size", hmax="0.04"))
    c.mesh.add(n("mesh.triangles", "tri"))
    st = m.studies.add(Node("study", "std1", "Estudo 1"))
    props = {"physics": ["wf"], "couplings": []}
    if step_kind == "step.time":
        props["tlist"] = "range(0,0.25,1)"
    st.add(n(step_kind, "s1", **props))
    return m


def _read_last(path):
    import meshio

    with meshio.xdmf.TimeSeriesReader(str(path)) as r:
        r.read_points_cells()
        t, pdata, _ = r.read_data(r.num_steps - 1)
        return t, next(iter(pdata.values())).ravel(), r.num_steps


def test_custom_equation_stationary(tmp_path):
    from kfem.solvers.study import run_study

    summary = run_study(_model(), "std1", tmp_path, log=lambda m: None)
    assert summary["steps"][0]["kind"] == "stationary"
    _, T, _ = _read_last(tmp_path / "field_T.xdmf")
    # −k ΔT = q no quadrado unitário com T=0: máximo = 0,07367·q/k (série de Fourier clássica)
    assert abs(T.max() - 0.07367 * 10 / 2) < 0.02 * 0.07367 * 5, T.max()
    assert json.loads((tmp_path / "summary.json").read_text())["steps"]


def test_custom_equation_transient(tmp_path):
    from kfem.solvers.study import run_study

    run_study(_model("step.time"), "std1", tmp_path, log=lambda m: None)
    t, T, nsteps = _read_last(tmp_path / "field_T.xdmf")
    assert nsteps == 5 and abs(t - 1.0) < 1e-12
    # difusividade efetiva k (ρc = 1): em t = 1 s o perfil já está perto do estacionário
    assert 0.9 * 0.368 < T.max() <= 0.368 * 1.02 and np.all(T >= -1e-9)
