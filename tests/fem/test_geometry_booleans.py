"""Polígono, diferença e interseção na sequência de geometria."""

from __future__ import annotations

import math

import pytest

gmsh = pytest.importorskip("gmsh")
pytestmark = pytest.mark.fem

from kfem.geometry.build import generate  # noqa: E402
from kfem.model.catalog import CATALOG  # noqa: E402
from kfem.model.tree import Model, Node  # noqa: E402


def _n(kind: str, tag: str, **props: object) -> Node:
    base = CATALOG[kind].defaults()
    base.update(props)
    return Node(kind, tag, tag, props=base)


def _model(*nodes: Node) -> Model:
    m = Model(name="bool")
    m.comp.length_unit = "m"
    for n in nodes:
        m.comp.geometry.add(n)
    m.comp.mesh.add(_n("mesh.size", "size", hmax="0.2"))
    return m


def test_polygon_area():
    geo = generate(_model(_n("geom.polygon", "tri", points="0 0; 2 0; 0 1")))
    assert list(geo.areas.values()) == [pytest.approx(1.0)]
    gmsh.finalize()


def test_difference_and_intersection_annulus_in_cell():
    R, t = 1.0, 0.2
    m = _model(
        _n("geom.rectangle", "cell", x=str(-R), y="0", width=str(2 * R), height="3"),
        _n("geom.disk", "body", x="0", y="0", r=str(R)),
        _n("geom.disk", "outer", x="0", y="0", r=str(R + t)),
        _n("geom.rectangle", "cell2", x=str(-R), y="0", width=str(2 * R), height="3"),
        _n("geom.intersection", "clip", objects=["outer", "cell2"]),
        _n("geom.difference", "cut", add=["cell", "clip"], subtract=["body"]),
        _n("geom.form_union", "fin"),
    )
    geo = generate(m)
    areas = sorted(geo.areas.values())
    assert len(areas) == 2
    # faixa catalítica: anel recortado pela célula |x| <= R, y >= 0
    yc = math.sqrt((R + t) ** 2 - R**2)  # altura em que o anel encontra a parede x = R
    seg = (R + t) ** 2 * math.acos(R / (R + t)) - R * yc  # segmento além de x = R (y > 0 e y < 0)
    band = math.pi / 2 * ((R + t) ** 2 - R**2) - seg  # remove as metades y > 0 em x > R e x < -R
    assert areas[0] == pytest.approx(band, rel=1e-6)
    assert sum(areas) == pytest.approx(2 * R * 3 - math.pi * R**2 / 2, rel=1e-6)
    gmsh.finalize()


def test_unknown_object_raises():
    with pytest.raises(ValueError, match="não existe"):
        generate(_model(_n("geom.rectangle", "a"), _n("geom.difference", "d", add=["a"], subtract=["zz"])))
    gmsh.finalize()
