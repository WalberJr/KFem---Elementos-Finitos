# Funções comuns das receitas. Cada receita: `. _common.sh; begin <nome> <arquivo>; ...; finish`
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/../env.sh"
if command -v ccache >/dev/null; then export CC="ccache gcc" CXX="ccache g++"; else export CC=gcc CXX=g++; fi; export FC=gfortran
export CFLAGS="-O2 -pipe -fPIC" CXXFLAGS="-O2 -pipe -fPIC" FFLAGS="-O2 -fPIC" FCFLAGS="-O2 -fPIC"
export LDFLAGS="-L$KFEM_SDK/lib -Wl,-rpath,\$ORIGIN/../lib -Wl,-rpath,$KFEM_SDK/lib -Wl,-rpath,$KFEM_SDK/qt6/lib"
STAMPS="$KFEM_SDK/.stamps"; mkdir -p "$STAMPS"
begin() {  # begin <nome> <tarball>
  NAME="$1"; SRC_TAR="$KFEM_DL/$2"
  if [[ -f "$STAMPS/$NAME" ]]; then echo "== $NAME já instalado (apague $STAMPS/$NAME para refazer)"; exit 0; fi
  grep -q "  $2\$" "$KFEM_ROOT/build/sha256.lock" || { echo "!! $2 sem SHA-256 registrado"; exit 1; }
  (cd "$KFEM_DL" && grep "  $2\$" "$KFEM_ROOT/build/sha256.lock" | sha256sum -c --quiet -) || { echo "!! SHA-256 não confere: $2"; exit 1; }
  WORK="$KFEM_BUILD/$NAME"; rm -rf "$WORK"; mkdir -p "$WORK"
  tar -xf "$SRC_TAR" -C "$WORK"
  SRC="$(find "$WORK" -mindepth 1 -maxdepth 1 -type d | head -1)"
  cd "$SRC"; echo "== $NAME: compilando em $SRC"
}
finish() { touch "$STAMPS/$NAME"; cd /; rm -rf "$WORK"; echo "== $NAME: ok"; }
pyinst() {  # instala pacote Python a partir de um diretório de fontes, sem binários prontos
  "$KFEM_SDK/bin/python3" -m pip install --no-deps --no-build-isolation --no-binary :all: -v "$@"
}
pycheck() { (cd / ; LD_LIBRARY_PATH="$KFEM_RUN_LD" "$KFEM_SDK/bin/python3" -c "$1"); }
