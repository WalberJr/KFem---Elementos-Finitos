#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; NAME=pure-python
[[ -f "$STAMPS/$NAME" ]] && { echo "== $NAME já instalado"; exit 0; }
for f in "meshio-${MESHIO_VERSION}.tar.gz" "pint-${PINT_VERSION}.tar.gz"; do
  (cd "$KFEM_DL"; grep "  $f\$" "$KFEM_ROOT/build/sha256.lock" | sha256sum -c --quiet -)
  pyinst "$KFEM_DL/$f"
done
# dependências puras de runtime (rich p/ meshio; flexcache/flexparser/platformdirs/typing-extensions p/ pint) e testes
"$KFEM_SDK/bin/python3" -m pip install rich flexcache flexparser platformdirs typing-extensions pytest
"$KFEM_SDK/bin/python3" -m pip freeze > "$KFEM_ROOT/build/python-runtime.lock"
touch "$STAMPS/$NAME"
