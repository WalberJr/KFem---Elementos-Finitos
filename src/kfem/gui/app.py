"""Inicialização da interface."""

from __future__ import annotations

import sys
from pathlib import Path


def run_gui(project: str | None = None, watch: tuple[str, str] | None = None) -> int:
    import os

    from PySide6.QtCore import QLocale, QTranslator
    from PySide6.QtWidgets import QApplication

    # leitura dos resultados enquanto o solver grava (o solver abre/fecha o HDF5 a cada saída)
    os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")
    from kfem.gui.main_window import MainWindow
    from kfem.gui.theme import stylesheet

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("KFem")
    app.setOrganizationName("KFem")
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    from PySide6.QtGui import QIcon

    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "kfem-icon.png")))
    # traduções (ADR 0002): textos-fonte em pt-BR; outros idiomas por arquivos .qm em gui/i18n
    tr = QTranslator(app)
    qm_dir = Path(__file__).parent / "i18n"
    if tr.load(QLocale.system(), "kfem", "_", str(qm_dir)):
        app.installTranslator(tr)
    w = MainWindow()
    w.show()
    if project:
        w.open_path(Path(project))
    if watch:
        w.watch_run(Path(watch[0]), Path(watch[1]))
    return int(app.exec())
