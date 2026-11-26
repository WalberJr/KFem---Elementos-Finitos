#!/usr/bin/env bash
# cffi, pybind11, nanobind (compilados a partir das fontes)
. "$(dirname "$0")/_common.sh"; NAME=pypkgs-c
[[ -f "$STAMPS/$NAME" ]] && { echo "== $NAME já instalado"; exit 0; }
for f in "cffi-${CFFI_VERSION}.tar.gz" "pybind11-${PYBIND11_VERSION}.tar.gz" "nanobind-${NANOBIND_VERSION}.tar.gz"; do
  (cd "$KFEM_DL"; grep "  $f\$" "$KFEM_ROOT/build/sha256.lock" | sha256sum -c --quiet -)
  pyinst "$KFEM_DL/$f"
done
"$KFEM_SDK/bin/python3" -m pip install pycparser
touch "$STAMPS/$NAME"
