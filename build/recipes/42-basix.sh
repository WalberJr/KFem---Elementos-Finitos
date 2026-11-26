#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin basix "basix-${BASIX_VERSION}.tar.gz"
cmake -S cpp -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$KFEM_SDK" \
  -DBLAS_LIBRARIES="$KFEM_SDK/lib/libopenblas.so" -DLAPACK_LIBRARIES="$KFEM_SDK/lib/libopenblas.so"
cmake --build b; cmake --install b
pyinst ./python; finish
