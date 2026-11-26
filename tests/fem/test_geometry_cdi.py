"""Etapa 5 — geometria de referência: 3 domínios, áreas e marcadores conferidos."""

from __future__ import annotations

import pytest

gmsh = pytest.importorskip("gmsh")
pytestmark = pytest.mark.fem

from kfem.geometry.build import generate  # noqa: E402
from kfem.samples import cdi_model  # noqa: E402


def test_cdi_geometry_markers_and_areas():
    m = cdi_model()
    m.meta["mesh_scale"] = 4.0
    geo = generate(m)
    assert sorted(geo.domains) == [1, 2, 3]
    assert len(geo.boundaries) == 14
    L, te, ts, Lp = 0.1, 0.4e-3, 0.8e-3, 0.01
    assert geo.areas[1] == pytest.approx((L + 2 * Lp) * ts, rel=1e-9)
    assert geo.areas[2] == pytest.approx(L * te, rel=1e-9)
    assert geo.areas[3] == pytest.approx(L * te, rel=1e-9)
    bb = {k: gmsh.model.getBoundingBox(1, t) for k, t in geo.boundaries.items()}
    ap = lambda v: pytest.approx(v, abs=1e-6)
    assert bb[1][0] == ap(-Lp) and bb[1][3] == ap(-Lp)  # entrada
    assert bb[14][0] == ap(L + Lp)  # saída
    assert bb[5][1] == ap(0.0) and bb[5][4] == ap(0.0)  # base do eletrodo inferior
    assert bb[9][1] == ap(2 * te + ts)  # topo do eletrodo superior
    assert bb[6][1] == ap(te) and bb[8][1] == ap(te + ts)  # interfaces
    # malha sem elementos degenerados
    gmsh.model.mesh.generate(2)
    _, tags, _ = gmsh.model.mesh.getElements(2)
    q = gmsh.model.mesh.getElementQualities(tags[0], "minSICN")
    assert min(q) > 0.05
    gmsh.finalize()
