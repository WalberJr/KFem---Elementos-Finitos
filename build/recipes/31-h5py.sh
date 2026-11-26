#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin h5py "h5py-${H5PY_VERSION}.tar.gz"
HDF5_MPI=ON HDF5_DIR="$KFEM_SDK" CC="$KFEM_SDK/bin/mpicc" pyinst .; finish
