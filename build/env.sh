# KFem — ambiente do build nativo (ADR 0011). Uso: `source build/env.sh`
# Não altera o sistema; tudo vai para o prefixo $KFEM_SDK.

export KFEM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export KFEM_SDK="${KFEM_SDK:-$HOME/kfem-sdk}"            # prefixo de instalação (disco interno)
export KFEM_BUILD="${KFEM_BUILD:-$HOME/kfem-build}"      # árvores de build (disco interno, temporárias)
export KFEM_TMP="${KFEM_TMP:-/media/walber/CODES/kfem}"  # FAT32: só downloads, ccache, logs, archives
export KFEM_DL="$KFEM_TMP/downloads"
export KFEM_LOGS="$KFEM_TMP/logs"
export KFEM_PETSC_VARIANT="${KFEM_PETSC_VARIANT:-cpu}"
export PETSC_DIR="$KFEM_SDK/petsc-$KFEM_PETSC_VARIANT"
export PETSC_ARCH=""

# shellcheck disable=SC1091
set -a; . "$KFEM_ROOT/build/versions.env"; set +a

export CCACHE_DIR="$KFEM_TMP/ccache"
export CCACHE_MAXSIZE=30G
export CCACHE_TEMPDIR="$KFEM_BUILD/.ccache-tmp"   # FAT32 não serve para arquivos temporários do ccache

export JOBS="${JOBS:-12}"
export PATH="$KFEM_SDK/bin:$KFEM_SDK/tools/bin:$PETSC_DIR/bin:$PATH"
export PKG_CONFIG_PATH="$KFEM_SDK/lib/pkgconfig:$KFEM_SDK/lib64/pkgconfig:$PETSC_DIR/lib/pkgconfig:$KFEM_SDK/share/pkgconfig"
export CMAKE_PREFIX_PATH="$KFEM_SDK:$PETSC_DIR:$KFEM_SDK/qt6"
export CPATH=""
# RPATH relativo nas receitas ($ORIGIN/../lib); LD_LIBRARY_PATH só para executar testes no build:
export KFEM_RUN_LD="$KFEM_SDK/lib:$KFEM_SDK/lib64:$PETSC_DIR/lib:$KFEM_SDK/qt6/lib"

# Paralelismo híbrido (ADR 0012): padrão 1 thread OpenMP por processo MPI.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-$OMP_NUM_THREADS}"

mkdir -p "$KFEM_SDK" "$KFEM_BUILD" "$CCACHE_TEMPDIR" "$KFEM_DL" "$KFEM_LOGS"
