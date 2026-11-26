"""Etapa 4 — expressões, parâmetros e ida-e-volta do formato .kfem."""

from __future__ import annotations

import math

import pytest

from kfem.io import kfem_format
from kfem.model.expressions import ExpressionError, evaluate, free_symbols, parse
from kfem.model.parameters import CycleError, ParameterSet
from kfem.model.tree import Model, Node, Selection


def q(expr, **sym):
    return evaluate(expr, sym)


def test_units_postfix_and_conversion():
    assert q("100 [mm]").to("m").magnitude == pytest.approx(0.1)
    assert q("0.42e-3[L/min]").to("m^3/s").magnitude == pytest.approx(7e-9)
    assert q("20 [mM]").to("mol/m^3").magnitude == pytest.approx(20.0)
    assert q("1.9e-9 [m^2/s]").to("m**2/s").magnitude == pytest.approx(1.9e-9)


def test_operators_precedence_and_power():
    assert q("2+3*4^2").magnitude == pytest.approx(50)
    assert q("-2^2").magnitude == pytest.approx(-4)
    assert q("2^-1").magnitude == pytest.approx(0.5)
    assert q("(1<2)+(3>=4)").magnitude == 1.0


def test_unit_makes_dimensionless():
    t = evaluate("10 [s]", {})
    assert evaluate("t[1/s]", {"t": t}).to("").magnitude == pytest.approx(10)


def test_functions():
    assert q("sqrt(4[m^2])").to("m").magnitude == pytest.approx(2)
    assert q("exp(0)").magnitude == pytest.approx(1)
    assert q("sin(pi/2)", pi=math.pi).magnitude == pytest.approx(1)


def test_free_symbols_and_errors():
    assert free_symbols("2*C/vol + F_const^2") == {"C", "vol", "F_const"}
    with pytest.raises(ExpressionError):
        parse("2 * (3")
    with pytest.raises(ExpressionError):
        parse("__import__('os')")  # aspas não são aceitas
    with pytest.raises(ExpressionError):
        evaluate("x+1", {})


def test_no_python_eval_possible():
    with pytest.raises(ExpressionError):
        evaluate("os.system(1)", {})


def cdi_params() -> ParameterSet:
    ps = ParameterSet()
    for n, e in [
        ("L", "100 [mm]"),
        ("W", "20[mm]"),
        ("te", "0.4[mm]"),
        ("ts", "0.8[mm]"),
        ("Lp", "L/10"),
        ("mass", "1.42[g]"),
        ("C", "20.01 [F/g]*mass"),
        ("vol", "te*W*L"),
        ("Cdl", "2*C/vol"),
        ("volFlow", "0.42e-3[L/min]"),
        ("v0", "volFlow/W/ts"),
        ("D", "1.9e-9 [m^2/s]"),
        ("molar_cond", "2*D/R_const/295[K]*F_const^2"),
    ]:
        ps.add(n, e)
    return ps


def test_cdi_parameters_values():
    si = cdi_params().to_si()
    assert si["Lp"] == pytest.approx(0.01)
    assert si["C"] == pytest.approx(28.4142)
    assert si["Cdl"] == pytest.approx(7.10355e7, rel=1e-5)
    assert si["v0"] == pytest.approx(4.375e-4)


def test_dependency_order_independent_of_insertion():
    ps = ParameterSet()
    ps.add("b", "2*a")
    ps.add("a", "3 [m]")
    assert ps.order() == ["a", "b"]
    assert ps.to_si()["b"] == pytest.approx(6)


def test_cycle_and_unknown_detected():
    ps = ParameterSet()
    ps.add("a", "b+1")
    ps.add("b", "a+1")
    with pytest.raises(CycleError, match="circular"):
        ps.order()
    ps2 = ParameterSet()
    ps2.add("a", "zz*2")
    with pytest.raises(ExpressionError, match="zz"):
        ps2.evaluate()


def test_override_for_sweeps():
    ps = cdi_params()
    assert ps.to_si(overrides={"te": "0.2[mm]"})["vol"] == pytest.approx(0.2e-3 * 0.02 * 0.1)


def build_model() -> Model:
    m = Model(name="teste")
    m.parameters = cdi_params()
    m.parameters.add("c0", "20 [mM]", "concentração", "Operação")
    phys = m.comp.physics.add(Node("physics.transport", "tds", "Transporte"))
    phys.add(Node("tds.inflow", "in1", "Entrada", props={"c0": ["c0", "c0"]}, selection=Selection(1, [1])))
    phys.add(Node("tds.conc", "conc1", props={"c": "0"}, selection=Selection(1, [9]), active=False))
    m.studies.add(Node("study", "std1", children=[Node("step.time", "time", props={"tlist": "range(0,5,50)"})]))
    return m


def test_roundtrip(tmp_path):
    m = build_model()
    p = kfem_format.save(m, tmp_path / "a.kfem", {"mesh/mesh.xdmf": b"<Xdmf/>"})
    m2 = kfem_format.load(p)
    assert kfem_format.model_to_dict(m2) == kfem_format.model_to_dict(m)
    assert m2.find("comp1/physics/tds/conc1").active is False
    assert m2.find("comp1/physics/tds/in1").selection.entities == [1]
    assert m2.parameters.params["c0"].group == "Operação"
    # regravar mantém anexos
    kfem_format.save(m2, p)
    assert kfem_format.list_attachments(p) == ["mesh/mesh.xdmf"]


def test_rejects_foreign_file(tmp_path):
    import zipfile

    f = tmp_path / "x.kfem"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("model.json", '{"format": "outro"}')
    with pytest.raises(kfem_format.ProjectFormatError):
        kfem_format.load(f)
