#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin pugixml "pugixml-${PUGIXML_VERSION}.tar.gz"
cmake -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$KFEM_SDK" -DBUILD_SHARED_LIBS=ON -DPUGIXML_BUILD_TESTS=OFF
cmake --build b; cmake --install b; finish
