#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; begin dolfinx "dolfinx-${DOLFINX_VERSION}.tar.gz"
export CC="$KFEM_SDK/bin/mpicc" CXX="$KFEM_SDK/bin/mpicxx"
cmake -S cpp -B b -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$KFEM_SDK" \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
  -DDOLFINX_ENABLE_PETSC=ON -DDOLFINX_ENABLE_ADIOS2=ON -DDOLFINX_ENABLE_SCOTCH=ON \
  -DDOLFINX_ENABLE_PARMETIS=OFF -DDOLFINX_ENABLE_KAHIP=OFF -DDOLFINX_ENABLE_SLEPC=OFF \
  -DBoost_INCLUDE_DIR="$KFEM_SDK/include"
cmake --build b; cmake --install b
export PYTHONPATH="$PETSC_DIR/lib:${PYTHONPATH:-}" LD_LIBRARY_PATH="$KFEM_RUN_LD"
bash "$KFEM_ROOT/build/patches/dolfinx-0.11.0-cffi-int.sh" ./python
pyinst ./python -Ccmake.define.CMAKE_PREFIX_PATH="$KFEM_SDK;$PETSC_DIR"
pycheck "import dolfinx; print('dolfinx', dolfinx.__version__, dolfinx.has_petsc)"; finish
