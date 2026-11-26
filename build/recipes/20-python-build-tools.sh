#!/usr/bin/env bash
# Ferramentas de build Python (só usadas para compilar; versões travadas em python-build-tools.lock).
. "$(dirname "$0")/_common.sh"; NAME=pytools
[[ -f "$STAMPS/$NAME" ]] && { echo "== $NAME já instalado"; exit 0; }
PY="$KFEM_SDK/bin/python3"; LOCK="$KFEM_ROOT/build/python-build-tools.lock"
if [[ -s "$LOCK" ]]; then $PY -m pip install -r "$LOCK"
else
  $PY -m pip install --upgrade pip setuptools wheel cython meson meson-python scikit-build-core packaging \
     pyproject-metadata pathspec setuptools-scm flit-core hatchling poetry-core pkgconfig
  $PY -m pip freeze > "$LOCK"
fi
touch "$STAMPS/$NAME"
