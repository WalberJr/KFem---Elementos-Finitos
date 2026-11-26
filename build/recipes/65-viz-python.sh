#!/usr/bin/env bash
# Matplotlib (compilado das fontes), PyVista e pyvistaqt + dependências puras (travadas em python-viz.lock).
. "$(dirname "$0")/_common.sh"; NAME=viz-python
[[ -f "$STAMPS/$NAME" ]] && { echo "== $NAME já instalado"; exit 0; }
PY="$KFEM_SDK/bin/python3"
for f in "matplotlib-${MATPLOTLIB_VERSION}.tar.gz"; do
  (cd "$KFEM_DL"; grep "  $f\$" "$KFEM_ROOT/build/sha256.lock" | sha256sum -c --quiet -)
done
$PY -m pip install --no-binary pillow,kiwisolver,contourpy pillow kiwisolver contourpy cycler fonttools pyparsing python-dateutil
pyinst "$KFEM_DL/matplotlib-${MATPLOTLIB_VERSION}.tar.gz" -Csetup-args=-Dsystem-freetype=true -Csetup-args=-Dsystem-qhull=false
$PY -m pip install pooch scooby typing-extensions qtpy "pyvista-validation==0.2.2" "cyclopts>=4.0.0"
pyinst "$KFEM_DL/pyvista-${PYVISTA_VERSION}.tar.gz" "$KFEM_DL/pyvistaqt-${PYVISTAQT_VERSION}.tar.gz"
$PY -m pip freeze > "$KFEM_ROOT/build/python-viz.lock"
touch "$STAMPS/$NAME"
