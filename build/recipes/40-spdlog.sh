#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin spdlog "spdlog-${SPDLOG_VERSION}.tar.gz"
cmake -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$KFEM_SDK" -DSPDLOG_BUILD_SHARED=ON -DSPDLOG_BUILD_EXAMPLE=OFF -DSPDLOG_BUILD_TESTS=OFF
cmake --build b; cmake --install b; finish
