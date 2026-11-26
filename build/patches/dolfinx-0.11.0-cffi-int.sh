#!/usr/bin/env bash
# DOLFINx 0.11.0 + cffi 2.x + nanobind 2.x/3.x: os ponteiros de cffi.cast("uintptr_t") não têm __index__
# e o nanobind recusa como int. Envolve as conversões em int(...). Aplicar no diretório python/ das fontes.
set -euo pipefail
cd "$1"
sed -i -E 's/(form\.)?(module\.)?ffi\.cast\("uintptr_t", ([^)]*\)[^)]*)\)/int(\1\2ffi.cast("uintptr_t", \3))/' dolfinx/fem/forms.py dolfinx/fem/function.py
grep -n 'int(.*ffi.cast("uintptr_t"' dolfinx/fem/forms.py dolfinx/fem/function.py
