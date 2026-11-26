"""Etapa 8/9 — janela principal (offscreen): árvore, painel, exemplo CDI, captura de tela."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp):
    from kfem.gui.main_window import MainWindow
    from kfem.gui.theme import stylesheet

    w = MainWindow()
    w.ask = lambda q: True  # sem diálogos modais nos testes
    w.setStyleSheet(stylesheet())
    w.dirty = False
    yield w
    w.dirty = False
    w.close()
    w.deleteLater()


def test_tree_and_settings(win):
    win.load_cdi_example()
    win.dirty = False
    root = win.tree.topLevelItem(0)
    assert root.childCount() >= 3
    win._select_path(("node", "comp1/physics/tds/conc1"))
    assert win.settings.node is not None and win.settings.node.tag == "conc1"
    win._select_path(("parameters", ""))
    assert win.settings.node is None


def test_add_physics_creates_defaults(win):
    from kfem.model.catalog import CATALOG

    win._add_child(win.model.comp.physics, CATALOG["physics.transport"])
    n = win.model.comp.physics.children[-1]
    kinds = {c.kind for c in n.children}
    assert {"transport.porous", "transport.noflux", "transport.init"} <= kinds
    win.dirty = False


def test_save_open_roundtrip(win, tmp_path):
    win.load_cdi_example()
    win.path = tmp_path / "x.kfem"
    assert win.save()
    win.open_path(win.path)
    assert win.model.find("comp1/physics/cd/pot2").props["phis"] == "-V/2"


def test_screenshot(win, tmp_path, qapp):
    win.load_cdi_example()
    win.dirty = False
    win.show()
    win._select_path(("node", "comp1/physics/cd/pce1"))
    for _ in range(20):
        qapp.processEvents()
    img = win.grab()
    out = Path(os.environ.get("KFEM_SCREENSHOT_DIR", tmp_path)) / "kfem_main_window.png"
    assert img.save(str(out))
    assert out.stat().st_size > 10_000


def test_recent_projects(win, tmp_path):
    """Sem exemplo embutido na interface: a aba Início lista só os trabalhos do usuário."""
    from PySide6.QtWidgets import QMenu

    texts = [a.text() for a in win.findChildren(type(win.a_new))]
    assert not any("Exemplo" in t for t in texts)
    win.load_cdi_example()  # modelo de teste (método interno, sem botão)
    a, b = tmp_path / "a.kfem", tmp_path / "b.kfem"
    win.path = a
    win.save()
    win.path = b
    win.save()
    assert win.recent_projects()[:2] == [b.resolve(), a.resolve()]
    win.open_path(a)  # reabrir sobe para o topo, sem duplicar
    rec = win.recent_projects()
    assert rec[0] == a.resolve() and rec.count(a.resolve()) == 1
    b.unlink()  # arquivo apagado some da lista
    assert b.resolve() not in win.recent_projects()
    m = QMenu()
    win._fill_recent(m)
    assert any(act.text().split()[0] == "a" for act in m.actions())


def test_vertical_display_scale():
    """Geometria muito alongada (CDI: 100 × 1,2 mm) ganha escala vertical só no desenho."""
    import numpy as np

    from kfem.gui.graphics import GraphicsView

    thin = np.array([[0.0, 0.0], [100.0, 1.2]])
    square = np.array([[0.0, 0.0], [1.0, 1.0]])
    f = GraphicsView.y_scale(thin)
    assert f > 1 and 100 / (1.2 * f) <= GraphicsView.MAX_ASPECT
    assert GraphicsView.y_scale(square) == 1.0


def test_help_docs_found(win):
    """Ajuda → Manual/Tutorial: os PDFs são encontrados (repositório ou usr/share/doc/kfem)."""
    for name in ("KFem-Manual.pdf", "KFem-Tutorial.pdf"):
        p = win.doc_path(name)
        assert p is not None and p.stat().st_size > 10_000


def test_gpu_setup_offer(win, monkeypatch):
    """A oferta aparece uma vez só, com placa AMD/NVIDIA sem cálculo na GPU; nunca sem placa."""
    from PySide6.QtWidgets import QMessageBox

    from kfem.gui import main_window as mw

    assert win.gpu_setup_script() is not None
    asked: list[str] = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.No)
    monkeypatch.setattr(mw.MainWindow, "gpu_needing_setup", staticmethod(lambda: "NVIDIA (dispositivo 0x2504)"))
    win.offer_gpu_setup(force=False)
    win.offer_gpu_setup(force=False)  # segunda vez: não pergunta de novo
    assert len(asked) == 1 and "NVIDIA" in asked[0]
    monkeypatch.setattr(mw.MainWindow, "gpu_needing_setup", staticmethod(lambda: None))
    win.offer_gpu_setup(force=True)
    assert len(asked) == 1
