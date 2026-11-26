#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin ninja "ninja-${NINJA_VERSION}.tar.gz"
export PATH="$KFEM_SDK/tools/bin:$PATH"
cmake -B b -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DCMAKE_INSTALL_PREFIX="$KFEM_SDK/tools"; cmake --build b -j"$JOBS"; cmake --install b; finish
