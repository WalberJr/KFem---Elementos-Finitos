#!/usr/bin/env bash
# OpenCASCADE mínimo para o Gmsh (sem visualização, sem Draw).
. "$(dirname "$0")/_common.sh"; begin occt "occt-${OCCT_VERSION}.tar.gz"
cmake -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DINSTALL_DIR="$KFEM_SDK" -DCMAKE_INSTALL_PREFIX="$KFEM_SDK" \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DBUILD_MODULE_Draw=OFF -DBUILD_MODULE_Visualization=OFF -DBUILD_MODULE_ApplicationFramework=OFF \
  -DBUILD_MODULE_DataExchange=ON -DUSE_FREETYPE=OFF -DUSE_TK=OFF -DUSE_TCL=OFF -DUSE_OPENGL=OFF -DUSE_XLIB=OFF \
  -DBUILD_DOC_Overview=OFF -DBUILD_SAMPLES_QT=OFF -DINSTALL_SAMPLES=OFF -DINSTALL_TEST_CASES=OFF
cmake --build b; cmake --install b; finish
