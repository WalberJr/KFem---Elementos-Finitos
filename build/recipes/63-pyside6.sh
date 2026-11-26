#!/usr/bin/env bash
# Shiboken6 + PySide6 (só os módulos usados). libclang do sistema como ferramenta de build (ADR 0011).
. "$(dirname "$0")/_common.sh"; begin pyside6 "pyside-setup-everywhere-src-${PYSIDE6_VERSION}.tar.xz"
export LLVM_INSTALL_DIR="${LLVM_INSTALL_DIR:-$(llvm-config --prefix)}"
"$KFEM_SDK/bin/python3" -m pip install -r requirements.txt
"$KFEM_SDK/bin/python3" setup.py install --qtpaths="$KFEM_SDK/qt6/bin/qtpaths" --parallel="$JOBS" \
  --module-subset=Core,Gui,Widgets,OpenGL,OpenGLWidgets,Svg,SvgWidgets,PrintSupport,Concurrent \
  --skip-docs --ignore-git --no-qt-tools
LD_LIBRARY_PATH="$KFEM_SDK/qt6/lib" QT_QPA_PLATFORM=offscreen pycheck "from PySide6 import QtWidgets, QtSvg; import PySide6; print('PySide6', PySide6.__version__)"
finish
