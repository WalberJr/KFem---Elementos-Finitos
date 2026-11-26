#!/usr/bin/env bash
# Qt 6 base mínimo: Widgets, OpenGL, xcb (vídeo/janelas do sistema; drivers não são empacotados).
. "$(dirname "$0")/_common.sh"; begin qtbase "qtbase-everywhere-src-${QT_VERSION}.tar.xz"
cmake -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$KFEM_SDK/qt6" \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DQT_BUILD_EXAMPLES=OFF -DQT_BUILD_TESTS=OFF -DBUILD_SHARED_LIBS=ON \
  -DFEATURE_xcb=ON -DFEATURE_opengl=ON -DFEATURE_opengl_desktop=ON -DFEATURE_dbus=ON -DFEATURE_sql=OFF \
  -DFEATURE_network=ON -DFEATURE_printsupport=ON -DFEATURE_testlib=ON -DFEATURE_concurrent=ON \
  -DINPUT_openssl=no -DFEATURE_system_zlib=ON -DFEATURE_system_png=ON -DFEATURE_system_jpeg=ON \
  -DFEATURE_system_harfbuzz=OFF -DFEATURE_system_pcre2=OFF -DFEATURE_system_doubleconversion=OFF \
  -DFEATURE_glib=OFF -DFEATURE_icu=OFF
cmake --build b; cmake --install b; finish
