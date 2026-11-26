#!/usr/bin/env bash
# PT-Scotch (CeCILL-C), com SCOTCHConfig.cmake para o DOLFINx; o PETSc usa esta mesma instalação.
. "$(dirname "$0")/_common.sh"; begin scotch "scotch-v${SCOTCH_VERSION}.tar.gz"
export PATH="$KFEM_SDK/tools/bin:$PATH"
cmake -B b -G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$KFEM_SDK" \
  -DCMAKE_C_COMPILER="$KFEM_SDK/bin/mpicc" -DBUILD_SHARED_LIBS=ON -DBUILD_PTSCOTCH=ON -DBUILD_LIBESMUMPS=ON \
  -DBUILD_LIBSCOTCHMETIS=ON -DBUILD_FORTRAN=OFF -DENABLE_TESTS=OFF -DINTSIZE=32 \
  -DBISON_EXECUTABLE="$KFEM_SDK/tools/bin/bison" -DFLEX_EXECUTABLE="$KFEM_SDK/tools/bin/flex"
cmake --build b -j"$JOBS"; cmake --install b
# os cabeçalhos de compatibilidade METIS do Scotch conflitam com o METIS real (MUMPS); ficam à parte
mkdir -p "$KFEM_SDK/include/scotch-metis-compat"
for h in metis.h metisf.h parmetis.h; do [[ ! -f "$KFEM_SDK/include/$h" ]] || mv "$KFEM_SDK/include/$h" "$KFEM_SDK/include/scotch-metis-compat/"; done
finish
