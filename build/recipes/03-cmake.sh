#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin cmake "cmake-${CMAKE_VERSION}.tar.gz"
CC=gcc CXX=g++ ./bootstrap --prefix="$KFEM_SDK/tools" --parallel="$JOBS" -- -DCMAKE_USE_OPENSSL=ON -DBUILD_TESTING=OFF
make -j"$JOBS"; make install; finish
