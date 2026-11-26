#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin bison "bison-${BISON_VERSION}.tar.xz"
./configure --prefix="$KFEM_SDK/tools" --disable-nls; make -j"$JOBS"; make install; finish
