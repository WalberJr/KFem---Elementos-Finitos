#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin python "Python-${PYTHON_VERSION}.tar.xz"
CC=gcc CXX=g++ ./configure --prefix="$KFEM_SDK" --enable-shared --with-ensurepip=install --without-static-libpython \
  LDFLAGS="$LDFLAGS"
make -j"$JOBS"; make install
pycheck "import ssl, ctypes, sqlite3, lzma, bz2, zlib; print('python ok')"
finish
