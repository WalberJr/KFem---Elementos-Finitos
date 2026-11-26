#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin ccache "ccache-${CCACHE_VERSION}.tar.xz"
export PATH="$KFEM_SDK/tools/bin:$PATH"; export CC=gcc CXX=g++
cmake -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTING=OFF -DREDIS_STORAGE_BACKEND=OFF -DHTTP_STORAGE_BACKEND=OFF \
  -DDEPS=AUTO -DCMAKE_INSTALL_PREFIX="$KFEM_SDK/tools"; cmake --build b; cmake --install b; finish
