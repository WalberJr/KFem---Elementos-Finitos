#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin mpich "mpich-${MPICH_VERSION}.tar.gz"
export CC=gcc CXX=g++ FC=gfortran F77=gfortran
FFLAGS="$FFLAGS -fallow-argument-mismatch" FCFLAGS="$FCFLAGS -fallow-argument-mismatch" \
./configure --prefix="$KFEM_SDK" --with-device=ch4:ofi --with-pm=hydra --enable-fortran=all --enable-shared --disable-static --disable-doc
make -j"$JOBS"; make install; finish
