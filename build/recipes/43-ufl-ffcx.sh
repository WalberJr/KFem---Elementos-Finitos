#!/usr/bin/env bash
. "$(dirname "$0")/_common.sh"; NAME=ufl-ffcx
[[ -f "$STAMPS/$NAME" ]] && { echo "== $NAME já instalado"; exit 0; }
for f in "ufl-${UFL_VERSION}.tar.gz" "ffcx-${FFCX_VERSION}.tar.gz"; do
  (cd "$KFEM_DL"; grep "  $f\$" "$KFEM_ROOT/build/sha256.lock" | sha256sum -c --quiet -)
  pyinst "$KFEM_DL/$f"
done
touch "$STAMPS/$NAME"
