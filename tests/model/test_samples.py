"""O exemplo CDI montado com nós do KFem equivale ao convertido do .mph."""

from __future__ import annotations

from pathlib import Path

import pytest

from kfem.io import kfem_format
from kfem.model.catalog import CATALOG
from kfem.samples import cdi_model

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "CDI_ionic_diode.mph"


def test_cdi_example_valid(tmp_path):
    m = cdi_model()
    si = m.parameters.to_si()
    assert si["v0"] == pytest.approx(4.375e-4)
    for n in m.comp.physics.walk():
        if not n.kind.startswith("section."):
            assert n.kind in CATALOG
    p = kfem_format.save(m, tmp_path / "cdi.kfem")
    assert kfem_format.model_to_dict(kfem_format.load(p)) == kfem_format.model_to_dict(m)


@pytest.mark.skipif(not SAMPLE.exists(), reason="arquivo do usuário ausente")
def test_example_matches_import():
    from kfem.io.mph import read_mph

    imp, _ = read_mph(SAMPLE)
    ex = cdi_model()
    a, b = imp.parameters.to_si(), ex.parameters.to_si()
    for k in b:
        assert a[k] == pytest.approx(b[k]), k
    for path in ("comp1/physics/cd/pot1", "comp1/physics/tds/conc1", "comp1/physics/tds/in1", "comp1/physics/br/inl1"):
        assert imp.find(path).selection.entities == ex.find(path).selection.entities, path
