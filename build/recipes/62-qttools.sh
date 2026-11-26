#!/usr/bin/env bash
# Só o Linguist (lupdate/lrelease) para as traduções (ADR 0002); sem designer/assistant/clang.
. "$(dirname "$0")/_common.sh"; begin qttools "qttools-everywhere-src-${QT_VERSION}.tar.xz"
"$KFEM_SDK/qt6/bin/qt-configure-module" . -- -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
  -DFEATURE_designer=OFF -DFEATURE_assistant=OFF -DFEATURE_qdoc=OFF -DFEATURE_clang=OFF -DFEATURE_pixeltool=OFF \
  -DFEATURE_qtdiag=OFF -DFEATURE_qtplugininfo=OFF -DFEATURE_distancefieldgenerator=OFF -DFEATURE_qev=OFF
cmake --build .; cmake --install .; finish
