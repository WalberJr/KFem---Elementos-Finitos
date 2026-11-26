#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin mpi4py "mpi4py-${MPI4PY_VERSION}.tar.gz"
MPICC="$KFEM_SDK/bin/mpicc" pyinst .
pycheck "from mpi4py import MPI; print(MPI.Get_library_version()[:40])"; finish
