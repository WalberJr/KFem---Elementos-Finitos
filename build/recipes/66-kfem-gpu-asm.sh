#!/usr/bin/env bash
# Biblioteca de montagem em GPU do KFem (HIP + hiprtc), código do próprio projeto.
# Só é compilada se houver hipcc; sem ela o KFem monta na CPU.
set -euo pipefail
. "$(dirname "$0")/../env.sh"
SRC="$KFEM_ROOT/src/kfem/solvers/gpu_asm/kfem_gpu_asm.cpp"
HIPCC="${KFEM_ROCM_DIR:-/usr}/bin/hipcc"
if [[ ! -x "$HIPCC" ]]; then echo "== kfem-gpu-asm: hipcc ausente, pulando"; exit 0; fi
# hipcc é script Perl: locale inexistente gera avisos
LC_ALL=C.UTF-8 "$HIPCC" -O2 -fPIC -shared -Wl,-rpath,'$ORIGIN' -o "$KFEM_SDK/lib/libkfem_gpu_asm.so" "$SRC"
echo "== kfem-gpu-asm: ok ($KFEM_SDK/lib/libkfem_gpu_asm.so)"
