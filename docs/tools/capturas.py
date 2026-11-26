"""Gera as capturas de tela do manual e do tutorial dirigindo a interface real do KFem.

    python docs/tools/capturas.py SAIDA PROJETO.kfem [RESULTADOS_LONGOS]

Precisa de um servidor gráfico (DISPLAY) e do `import` (ImageMagick). As configurações do
usuário (trabalhos recentes) não são tocadas: QSettings vai para um diretório temporário.
RESULTADOS_LONGOS (opcional) é um diretório de resultados de um transiente longo, usado para
mostrar campos com mais contraste que o cálculo curto feito na hora.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

OUT = Path(sys.argv[1])
PROJ = Path(sys.argv[2])
LONG = Path(sys.argv[3]) if len(sys.argv) > 3 else None
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

from PySide6.QtCore import QSettings, QTimer  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="kfem-capturas-"))
for fmt in (QSettings.Format.NativeFormat, QSettings.Format.IniFormat):
    QSettings.setPath(fmt, QSettings.Scope.UserScope, str(tmp / "cfg"))
work = tmp / "projetos"
work.mkdir()
proj = work / "celula_cdi.kfem"
shutil.copy(PROJ, proj)
for extra in ("celula_cdi_malha_fina.kfem", "estudo_vazao.kfem"):
    shutil.copy(PROJ, work / extra)

from kfem.gui.main_window import MainWindow  # noqa: E402
from kfem.gui.theme import stylesheet  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
app.setApplicationName("KFem")
app.setOrganizationName("KFem")
app.setStyle("Fusion")
app.setStyleSheet(stylesheet())
app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[2] / "src/kfem/gui/assets/kfem-icon.png")))

w = MainWindow()
w.ask = lambda q: True  # type: ignore[method-assign]
w.resize(1500, 900)
w.move(40, 40)
w.show()


def shot(name: str, whole_screen_region: bool = False) -> None:
    app.processEvents()
    path = OUT / f"{name}.png"
    if whole_screen_region:  # janelas flutuantes (menus) não aparecem na captura da janela
        g = w.frameGeometry()
        crop = f"{g.width()}x{g.height()}+{g.x()}+{g.y()}"
        subprocess.run(["import", "-window", "root", "-crop", crop, str(path)], check=True)
    else:
        subprocess.run(["import", "-window", hex(int(w.winId())), str(path)], check=True)
    print("captura:", path, flush=True)


def find_item(text_start: str):
    def walk(it):
        if it.text(0).startswith(text_start):
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


def select(text_start: str) -> None:
    it = find_item(text_start)
    if it is not None:
        w.tree.setCurrentItem(it)
        w.tree.scrollToItem(it)


# --------------------------------------------------------------------------- roteiro
steps: list[tuple[Callable[[], bool], Callable[[], None]]] = []


def step(cond: Callable[[], bool] = lambda: True) -> Callable[[Callable[[], None]], Callable[[], None]]:
    def deco(fn: Callable[[], None]) -> Callable[[], None]:
        steps.append((cond, fn))
        return fn

    return deco


@step()
def s_open() -> None:
    w.open_path(work / "estudo_vazao.kfem")
    w.open_path(work / "celula_cdi_malha_fina.kfem")
    w.open_path(proj)  # fica no topo da lista de recentes


@step()
def s_window() -> None:
    w.bottom.setCurrentIndex(0)
    shot("01-janela")


@step()
def s_recent_menu() -> None:
    btn = next(b for b in w.findChildren(QToolButton) if b.text() == "Trabalhos recentes")
    m = btn.menu()
    m.popup(btn.mapToGlobal(btn.rect().bottomLeft()))


@step()
def s_recent_shot() -> None:
    shot("02-trabalhos-recentes", whole_screen_region=True)
    btn = next(b for b in w.findChildren(QToolButton) if b.text() == "Trabalhos recentes")
    btn.menu().hide()


@step()
def s_params() -> None:
    select("Parâmetros")


@step()
def s_params_shot() -> None:
    shot("03-parametros")
    select("Transporte")


@step()
def s_physics_shot() -> None:
    it = find_item("Transporte")
    if it is not None:
        it.setExpanded(True)
    shot("04-fisica-configuracoes")
    select("Geometria")
    w.preview_geometry()


@step()
def s_geom_shot() -> None:
    shot("05-geometria")
    select("Malha")
    w.build_mesh()


@step(lambda: not w.solver.is_running())
def s_mesh_shot() -> None:
    shot("06-malha")
    select("Estudo")
    w.n_procs.setValue(min(6, w.n_procs.maximum()))
    w.run_study()


@step(lambda: w.progress.value() > 450)
def s_running_shot() -> None:
    w.bottom.setCurrentIndex(1)
    shot("07-calculando")


@step(lambda: not w.solver.is_running())
def s_done() -> None:
    w.bottom.setCurrentIndex(2)
    shot("08-log")
    w.bottom.setCurrentIndex(3)
    shot("09-tabela")
    if LONG is not None and LONG.is_dir():
        w.load_results(LONG)


@step()
def s_field() -> None:
    gv = w.graphics
    gv.field_box.setCurrentText("cNa")
    k = gv.time_box.findText("t = 600 s")  # instante com o esgotamento visível
    if k >= 0:
        gv.time_box.setCurrentIndex(k)
        gv._redraw_result()
    w.bottom.setCurrentIndex(0)
    shot("10-resultado-cNa")
    if "phil" in [gv.field_box.itemText(i) for i in range(gv.field_box.count())]:
        gv.field_box.setCurrentText("phil")


@step()
def s_field2() -> None:
    shot("11-resultado-phil")
    app.quit()


idx = [0]


def tick() -> None:
    if idx[0] >= len(steps):
        return
    cond, fn = steps[idx[0]]
    if cond():
        idx[0] += 1
        fn()
    QTimer.singleShot(1500, tick)


QTimer.singleShot(2500, tick)
QTimer.singleShot(15 * 60 * 1000, app.quit)  # trava de segurança
rc = app.exec()
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(rc)
