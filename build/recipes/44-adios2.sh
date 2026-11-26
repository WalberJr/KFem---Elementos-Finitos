#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin adios2 "adios2-${ADIOS2_VERSION}.tar.gz"
OFF=""; for o in Fortran Python HDF5 ZeroMQ SST Blosc2 BZip2 ZFP SZ MGARD PNG CUDA Kokkos DataMan DataSpaces Campaign AWSSDK Catalyst LIBPRESSIO IME UCX SysVShMem; do OFF+=" -DADIOS2_USE_$o=OFF"; done
cmake -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$KFEM_SDK" -DADIOS2_USE_MPI=ON \
  -DMPI_C_COMPILER="$KFEM_SDK/bin/mpicc" -DMPI_CXX_COMPILER="$KFEM_SDK/bin/mpicxx" \
  -DBUILD_TESTING=OFF -DADIOS2_BUILD_EXAMPLES=OFF $OFF
cmake --build b; cmake --install b; finish
