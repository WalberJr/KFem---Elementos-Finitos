"""Etapa 9 — fluxo pela interface: calcular em processo separado, cancelar, carregar resultados.

A interface continua respondendo durante o cálculo e depois do cancelamento.
"""

from __future__ import annotations

import os
import time

import pytest

pytest.importorskip("PySide6")
import importlib.util

# não importar dolfinx/petsc4py no processo da interface (o PETSc instala tratadores de sinal);
# o solver roda em outro processo, como na aplicação real
if importlib.util.find_spec("dolfinx") is None:
    pytest.skip("dolfinx ausente", allow_module_level=True)
pytestmark = [pytest.mark.gui, pytest.mark.fem, pytest.mark.slow]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def wait(qapp, cond, timeout):
    t0 = time.time()
    while not cond() and time.time() - t0 < timeout:
        qapp.processEvents()
        time.sleep(0.02)
    return cond()


def make_window(tmp_path, tlist):
    from kfem.gui.main_window import MainWindow

    w = MainWindow()
    w.ask = lambda q: True  # sem diálogos modais nos testes
    w.load_cdi_example()
    w.model.meta["mesh_scale"] = 3.0
    w.model.find("studies/std1/time").props["tlist"] = tlist
    w.path = tmp_path / "cdi.kfem"
    w.save()
    w.n_procs.setValue(2)
    return w


def test_run_and_results(qapp, tmp_path):
    w = make_window(tmp_path, "range(0,5,15)")
    done = []
    w.solver.finished_ok.connect(lambda wd, s: done.append(wd))
    w.run_study()
    assert w.solver.is_running()
    beats = []
    ok = wait(qapp, lambda: bool(done) or not w.solver.is_running(), 900) if True else None
    beats.append(1)
    assert ok and done, w.logview.toPlainText()[-3000:]
    assert w.table.rowCount() == 4  # t = 0, 5, 10, 15
    assert w.a_run.isEnabled() and not w.a_stop.isEnabled()
    w.dirty = False
    w.close()


def test_cancel_keeps_gui_alive(qapp, tmp_path):
    w = make_window(tmp_path, "range(0,5,7200)")
    ended = []
    w.solver.cancelled.connect(lambda m: ended.append("cancel"))
    w.solver.failed.connect(lambda m: ended.append("fail:" + m))
    w.run_study()
    assert wait(qapp, lambda: "t = 5 s" in w.logview.toPlainText(), 600), w.logview.toPlainText()[-2000:]
    w.cancel_study()
    assert wait(qapp, lambda: bool(ended), 60)
    assert ended[0] == "cancel"
    assert not w.solver.is_running()
    # a interface segue utilizável: abre outro exemplo e seleciona nós
    w.load_cdi_example()
    w._select_path(("node", "comp1/physics/tds"))
    assert w.settings.node.tag == "tds"
    w.dirty = False
    w.close()
