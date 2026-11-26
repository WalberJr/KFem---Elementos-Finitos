"""Etapa 7 — conversão de .mph. Usa o arquivo do usuário se presente (fora do git)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from kfem.io.kfem_format import load
from kfem.io.mph import convert_mph, parse_entities, parse_values, read_mph

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "CDI_ionic_diode.mph"


def test_value_parsing():
    assert parse_values("2|1,'c0'|1,'c0'") == ["c0", "c0"]
    assert parse_values("1|2,'L','te'") == ["L", "te"]
    assert parse_values("1|1,'Note\\, ok'") == ["Note, ok"]
    assert parse_entities("4,2,3") == [2, 3]
    assert parse_entities("-14,-1,9") == [9]
    assert parse_entities(None) == "all"


def test_minimal_synthetic(tmp_path):
    xml = """<?xml version="1.0"?><Model tag="M">
    <ModelParam tag="param"><ModelParamGroupList tag="group">
      <ModelParamGroup tag="default" name="Geo"/></ModelParamGroupList>
      <expressions T="31" name="L" expr="2 [mm]"/><expressions T="31" name="H" expr="L/2"/></ModelParam>
    </Model>"""
    p = tmp_path / "m.mph"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("dmodel.xml", xml)
        z.writestr("fileversion", "x")
    m, _rep = read_mph(p)
    assert m.parameters.to_si()["H"] == pytest.approx(1e-3)
    assert m.parameters.groups[0] == "Geo"


@pytest.mark.skipif(not SAMPLE.exists(), reason="arquivo do usuário ausente")
def test_cdi_conversion(tmp_path):
    rep = convert_mph(SAMPLE, tmp_path / "cdi.kfem")
    m = load(tmp_path / "cdi.kfem")
    si = m.parameters.to_si()
    assert si["te"] == pytest.approx(0.4e-3) and si["V_ext0"] == pytest.approx(1.2)
    assert len([n for n in m.comp.geometry.children if n.kind == "geom.rectangle"]) == 5
    assert m.find("comp1/geometry/ige1").props["edges"] == [6, 12]
    assert m.find("comp1/physics/cd/pot1").selection.entities == [9]
    assert m.find("comp1/physics/cd/pot2").props["phis"] == "-V/2"
    assert m.find("comp1/physics/cd").props["thickness"] == "W"
    tds = m.find("comp1/physics/tds")
    assert tds.props["species"] == ["cNa", "cCl"] and tds.props["charges"] == ["zNa", "zCl"]
    assert m.find("comp1/physics/tds/conc1").props["apply"] == [False, True]
    assert m.find("comp1/physics/tds/pec1/rc3").props["nu"] == ["0", "-1"]
    assert m.find("comp1/physics/tds/pec1/rc1").active is False
    assert m.find("comp1/physics/Veff/ge1").props["equations"][0][1] == "V-(V_ext0-Rc*current)"
    assert m.find("comp1/physics/Veff/ge2").active is False
    assert m.find("studies/std1/time").props["physics"] == ["cd", "tds", "Veff"]
    assert "Corner" in " ".join(rep.skipped)
