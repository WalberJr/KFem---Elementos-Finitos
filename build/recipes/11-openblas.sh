#!/usr/bin/env bash
# OpenBLAS com OpenMP (ADR 0012) e DYNAMIC_ARCH (roda em qualquer x86_64; escolhe o kernel em tempo de execução).
. "$(dirname "$0")/_common.sh"; begin openblas "OpenBLAS-${OPENBLAS_VERSION}.tar.gz"
make -j"$JOBS" CC=gcc FC=gfortran USE_OPENMP=1 DYNAMIC_ARCH=1 TARGET=HASWELL NO_AFFINITY=1 NUM_THREADS=64 BUILD_TESTING=0 libs netlib shared
make PREFIX="$KFEM_SDK" install; finish
