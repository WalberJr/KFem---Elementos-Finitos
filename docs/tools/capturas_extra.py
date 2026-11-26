"""Capturas extras do manual: geometria por polígono/booleanas, equação personalizada e
resultados do modelo 2D de redução de CO2 (exemplo Xie et al. 2022).

    python docs/tools/capturas_extra.py SAIDA PROJETO_2D.kfem DIR_RESULTADOS

Mesmo esquema de docs/tools/capturas.py: interface real, QSettings temporário, `import`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

OUT, PROJ, RES = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

from PySide6.QtCore import QSettings, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="kfem-capturas-"))
for fmt in (QSettings.Format.NativeFormat, QSettings.Format.IniFormat):
    QSettings.setPath(fmt, QSettings.Scope.UserScope, str(tmp / "cfg"))
proj = tmp / PROJ.name
shutil.copy(PROJ, proj)

from kfem.gui.main_window import MainWindow  # noqa: E402
from kfem.gui.theme import stylesheet  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
app.setApplicationName("KFem")
app.setStyle("Fusion")
app.setStyleSheet(stylesheet())
w = MainWindow()
w.ask = lambda q: True  # type: ignore[method-assign]
w.resize(1500, 900)
w.move(40, 40)
w.show()


def shot(name: str) -> None:
    app.processEvents()
    path = OUT / f"{name}.png"
    subprocess.run(["import", "-window", hex(int(w.winId())), str(path)], check=True)
    print("captura:", path, flush=True)


def find_item(pred: Callable[[str], bool]):
    def walk(it):
        if pred(it.text(0)):
            return it
        for i in range(it.childCount()):
            r = walk(it.child(i))
            if r is not None:
                return r
        return None

    for i in range(w.tree.topLevelItemCount()):
        r = walk(w.tree.topLevelItem(i))
        if r is not None:
            return r
    return None


def select(pred: Callable[[str], bool], expand: bool = False) -> None:
    it = find_item(pred)
    if it is not None:
        w.tree.setCurrentItem(it)
        w.tree.scrollToItem(it)
        if expand:
            it.setExpanded(True)


steps: list[tuple[Callable[[], bool], Callable[[], None]]] = []


def step(cond: Callable[[], bool] = lambda: True):
    def deco(fn):
        steps.append((cond, fn))
        return fn

    return deco


@step()
def s_open() -> None:
    w.open_path(proj)


@step()
def s_geom() -> None:
    select(lambda t: t.startswith("Geometria"), expand=True)
    select(lambda t: "clip" in t.lower() or t.startswith("Interseção"))
    w.preview_geometry()


@step()
def s_geom_shot() -> None:
    shot("13-geometria-booleana")
    select(lambda t: t.startswith("Físicas"), expand=True)
    it = find_item(lambda t: t.startswith("Espécies") or "forma fraca" in t.lower())
    if it is not None:
        it.setExpanded(True)
        w.tree.setCurrentItem(it)


@step()
def s_wf_shot() -> None:
    shot("14-equacao-personalizada")
    select(lambda t: t.startswith("Malha"), expand=True)
    w.build_mesh()


@step(lambda: not w.solver.is_running())
def s_mesh_shot() -> None:
    shot("15-malha-2d")
    w.load_results(RES)


@step()
def s_res_shot() -> None:
    shot("16-resultado-2d")
    app.quit()


idx = [0]


def tick() -> None:
    if idx[0] >= len(steps):
        return
    cond, fn = steps[idx[0]]
    if cond():
        idx[0] += 1
        fn()
    QTimer.singleShot(2500, tick)


QTimer.singleShot(3000, tick)
QTimer.singleShot(10 * 60 * 1000, app.quit)
rc = app.exec()
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(rc)
