#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin flex "flex-${FLEX_VERSION}.tar.gz"
export PATH="$KFEM_SDK/tools/bin:$PATH"
./configure --prefix="$KFEM_SDK/tools" --disable-nls; make -j"$JOBS"; make install; finish
