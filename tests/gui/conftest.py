"""Os testes da interface nunca tocam nas configurações reais do usuário (trabalhos recentes,
geometria da janela): QSettings vai para um diretório temporário da sessão de testes."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolated_qsettings(tmp_path_factory):
    try:
        from PySide6.QtCore import QSettings
    except ImportError:
        yield
        return
    d = str(tmp_path_factory.mktemp("qsettings"))
    for fmt in (QSettings.Format.NativeFormat, QSettings.Format.IniFormat):
        QSettings.setPath(fmt, QSettings.Scope.UserScope, d)
    yield


@pytest.fixture(autouse=True)
def _no_gpu_offer():
    """A oferta de instalação da GPU (diálogo modal) fica desligada nos testes."""
    try:
        from kfem.gui.main_window import MainWindow
    except ImportError:
        yield
        return
    MainWindow.auto_gpu_offer = False
    yield
