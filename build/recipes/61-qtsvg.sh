#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin qtsvg "qtsvg-everywhere-src-${QT_VERSION}.tar.xz"
"$KFEM_SDK/qt6/bin/qt-configure-module" . -- -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
cmake --build .; cmake --install .; finish
