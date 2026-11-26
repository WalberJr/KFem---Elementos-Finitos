#!/usr/bin/env bash
# KFem — identifica a placa de vídeo e instala o necessário para o FEniCSx do KFem calcular nela.
#
#   kfem-gpu-setup.sh                 # só identifica e mostra o plano (não muda nada)
#   kfem-gpu-setup.sh --install       # instala driver/runtime da GPU (pede sudo)
#   kfem-gpu-setup.sh --install --build   # idem + compila, a partir do código-fonte do KFem,
#                                     # a variante do PETSc para ESTA placa
#   opções: --yes (não pergunta), --auto (modo da 1ª execução do KFem: --install --yes, só
#           runtime, sem compilar), --dry-run (mostra os comandos sem executá-los),
#           --appimage CAMINHO (verifica com o AppImage no fim), --src DIR (código-fonte)
#
# Rotas, conforme o fabricante (ADR 0005/0013):
#   AMD com ROCm  → HIP: montagem dos elementos finitos na GPU (testado na RX 580 / gfx803)
#                   e PETSc HIP; runtime ROCm dos pacotes da distribuição.
#   NVIDIA        → CUDA: driver proprietário + CUDA Toolkit; PETSc CUDA compilado para a
#                   arquitetura da placa (--build). NÃO TESTADO em hardware real.
#   Intel/outras  → sem rota de cálculo estável; o KFem calcula na CPU e desenha na GPU.
# Nunca roda `apt autoremove` e nunca remove um pacote sem dizer qual e por quê.
# Variável para testes: KFEM_SYSFS (raiz de um /sys simulado).
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

INSTALL=0; BUILD=0; YES=0; DRY=0; AUTO=0; APPIMAGE=""; SRC=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL=1 ;;
    --build) BUILD=1 ;;
    --yes|-y) YES=1 ;;
    --auto) AUTO=1; INSTALL=1; YES=1 ;;
    --dry-run) DRY=1 ;;
    --appimage) APPIMAGE="$2"; shift ;;
    --src) SRC="$2"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
  shift
done
[[ -n "$SRC" ]] || SRC="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
SYSFS="${KFEM_SYSFS:-/sys}"
SUDO="sudo"; [[ $EUID -eq 0 ]] && SUDO=""   # via pkexec já é root

say()  { printf '%s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
ask()  { [[ $YES == 1 ]] && return 0; read -r -p "$1 [s/N] " r; [[ "$r" =~ ^[sSyY] ]]; }
run()  { say "  \$ $*"; [[ $DRY == 1 ]] || "$@"; }
installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed"; }

# Pacotes que disputam os mesmos cabeçalhos (/usr/include/thrust): o do ROCm só é preciso para
# compilar a variante HIP; o da NVIDIA só para compilar a CUDA. Troca um pelo outro avisando.
swap_out() {  # swap_out <pacote_que_atrapalha> <motivo>
  local p="$1"
  if installed "$p"; then
    say "  O pacote '$p' conflita com o que será instalado ($2)."
    say "  Removê-lo não afeta o KFem já instalado (só é usado para compilar)."
    if ask "  Remover '$p'?"; then run $SUDO apt-get remove -y "$p"; else say "  mantido; a instalação pode falhar."; fi
  fi
}

ROCM_ARCHS="gfx803 gfx900 gfx906 gfx908 gfx90a gfx1010 gfx1030 gfx1100 gfx1101 gfx1102"
APT_ROCM_RUNTIME="libamdhip64-5 libhsa-runtime64-1 libamd-comgr2 libhiprtc-builtins5 rocminfo \
librocsparse0 libhipsparse0 librocblas0 libhipblas0 librocsolver0 libhipsolver0 librocrand1 libhiprand1"
APT_ROCM_DEV="hipcc librocsparse-dev libhipsparse-dev librocblas-dev libhipblas-dev librocsolver-dev \
libhipsolver-dev librocprim-dev librocthrust-dev libhipcub-dev librocrand-dev libhiprand-dev"
APT_CUDA="nvidia-cuda-toolkit"

# ------------------------------------------------------------------------------ 1. identificar
step "Placas de vídeo"
declare -a VENDORS=() NAMES=()
for dev in "$SYSFS"/class/drm/card[0-9]*/device; do
  [[ -r "$dev/vendor" ]] || continue
  case "$(basename "$(dirname "$dev")")" in *-*) continue ;; esac
  v=$(cat "$dev/vendor"); d=$(cat "$dev/device")
  drv=$(basename "$(readlink -f "$dev/driver" 2>/dev/null || echo '-')")
  name=""
  command -v lspci >/dev/null && [[ "$SYSFS" == /sys ]] && \
    name=$(lspci -d "${v#0x}:${d#0x}" -mm 2>/dev/null | head -1 | cut -d'"' -f6-7 | tr -d '"')
  say "  - vendor $v device $d driver $drv ${name:+($name)}"
  VENDORS+=("$v"); NAMES+=("$name")
done
[[ ${#VENDORS[@]} -gt 0 ]] || { say "  nenhuma GPU encontrada: o KFem calcula na CPU."; exit 0; }

has() { local x; for x in "${VENDORS[@]}"; do [[ "$x" == "$1" ]] && return 0; done; return 1; }
if has 0x1002; then ROUTE=hip; elif has 0x10de; then ROUTE=cuda; else ROUTE=none; fi
. /etc/os-release 2>/dev/null || true
PKG=""; command -v apt-get >/dev/null && PKG=apt; command -v dnf >/dev/null && [[ -z "$PKG" ]] && PKG=dnf
say "  sistema: ${PRETTY_NAME:-desconhecido}; gerenciador de pacotes: ${PKG:-nenhum suportado}"

# ------------------------------------------------------------------------------ 2. plano e conferência
ARCH=""; CC=""; NVDRV=0
step "Rota de cálculo"
case "$ROUTE" in
  hip)
    say "  AMD → HIP/ROCm (montagem dos elementos finitos na GPU + PETSc HIP)."
    if ! id -nG | tr ' ' '\n' | grep -qx render; then
      say "  ! seu usuário não está no grupo 'render' (necessário para o ROCm acessar a GPU):"
      say "      sudo usermod -aG render,video \$USER   (depois saia e entre de novo na sessão)"
    fi ;;
  cuda)
    say "  NVIDIA → CUDA (driver proprietário + CUDA Toolkit; PETSc CUDA para esta placa)."
    say "  NÃO TESTADO em hardware real: a conferência do KFem protege o resultado (cai para a CPU)."
    if command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; then
      NVDRV=1
      line=$(nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv,noheader 2>/dev/null | head -1 || true)
      say "  placa: ${line:-?}"
      CC=$(echo "$line" | awk -F', ' '{print $2}' | tr -d ' ')
      if [[ -n "$CC" ]]; then
        ARCH="${CC/./}"   # 8.6 → 86 (sm_86)
        if (( ${CC%%.*} < 6 )); then
          say "  ! compute capability $CC: anterior à Pascal (6.0); sem suporte no KFem (falta atomicAdd em double)."
        fi
      fi
    else
      say "  ! driver NVIDIA não encontrado (nvidia-smi ausente ou sem placa visível)."
    fi ;;
  none)
    say "  Sem rota de cálculo em GPU estável para esta placa: o KFem calcula na CPU (MPI)"
    say "  e usa a GPU para desenhar. Nada a instalar."
    exit 0 ;;
esac

# ------------------------------------------------------------------------------ 3. instalar
if [[ $INSTALL == 1 ]]; then
  step "Instalação"
  if [[ "$PKG" != apt ]]; then
    say "  Instalação automática só para Ubuntu/Debian (apt). Nesta distribuição instale pelos"
    say "  pacotes dela: AMD → runtime ROCm (hip, rocsparse, rocblas); NVIDIA → driver e CUDA."
  elif [[ $ROUTE == hip ]]; then
    # o ROCm só acessa a GPU para quem está no grupo 'render' (sob pkexec/sudo: o usuário original)
    TU="${SUDO_USER:-}"; [[ -z "$TU" && -n "${PKEXEC_UID:-}" ]] && TU=$(id -nu "$PKEXEC_UID")
    TU="${TU:-$(id -nu)}"
    if ! id -nG "$TU" | tr ' ' '\n' | grep -qx render; then
      if ask "  Adicionar o usuário '$TU' aos grupos render e video?"; then
        run $SUDO usermod -aG render,video "$TU"
        say "  (vale a partir do próximo login)"
      fi
    fi
    pk="$APT_ROCM_RUNTIME"
    if [[ $BUILD == 1 ]]; then pk="$pk $APT_ROCM_DEV"; swap_out libthrust-dev "librocthrust-dev para compilar a variante HIP"; fi
    say "  pacotes: $pk"
    if ask "  Instalar agora?"; then run $SUDO apt-get update; run $SUDO apt-get install -y $pk; fi
  else
    if [[ $NVDRV == 0 ]]; then
      if command -v ubuntu-drivers >/dev/null; then
        say "  O driver proprietário NVIDIA é necessário. Depois de instalado, REINICIE o computador"
        say "  e rode este instalador de novo para concluir."
        if ask "  Instalar o driver recomendado agora (ubuntu-drivers)?"; then run $SUDO ubuntu-drivers install; fi
      else
        say "  Instale o driver proprietário NVIDIA pela ferramenta da sua distribuição e reinicie."
      fi
    fi
    if [[ $AUTO == 1 && $BUILD == 0 ]]; then
      say "  O CUDA Toolkit só é preciso para compilar a variante (--build); nada mais a instalar agora."
    else
      swap_out librocthrust-dev "libthrust-dev, dependência do CUDA Toolkit"
      say "  pacotes: $APT_CUDA"
      if ask "  Instalar o CUDA Toolkit agora?"; then run $SUDO apt-get update; run $SUDO apt-get install -y $APT_CUDA; fi
    fi
  fi
fi

# ------------------------------------------------------------------------------ 4. arquitetura AMD
if [[ $ROUTE == hip ]]; then
  step "Arquitetura AMD"
  if command -v rocminfo >/dev/null; then
    ARCH=$(rocminfo 2>/dev/null | grep -oE 'gfx[0-9a-f]+' | head -1 || true)
    if [[ -z "$ARCH" ]]; then
      say "  rocminfo não vê a GPU (grupo 'render'? driver amdgpu carregado?)."
    elif [[ " $ROCM_ARCHS " == *" $ARCH "* ]]; then
      say "  $ARCH: suportada pelas bibliotecas ROCm da distribuição."
    else
      say "  $ARCH: fora da lista do ROCm da distribuição ($ROCM_ARCHS)."
      say "  Algumas placas RDNA funcionam com HSA_OVERRIDE_GFX_VERSION (ex.: gfx1031 → 10.3.0); sem"
      say "  garantia. O KFem testa a placa ao iniciar e cai para a CPU se não funcionar."
    fi
  else
    say "  rocminfo ausente (rode com --install)."
  fi
fi

# ------------------------------------------------------------------------------ 5. compilar (opcional)
if [[ $BUILD == 1 && $AUTO == 0 ]]; then
  step "Compilação a partir do código-fonte ($SRC)"
  [[ -f "$SRC/build/recipes/30-petsc.sh" ]] || { say "  código-fonte do KFem não encontrado em $SRC"; exit 1; }
  if [[ $ROUTE == hip ]]; then
    [[ -n "$ARCH" ]] || { say "  arquitetura AMD desconhecida; não dá para compilar."; exit 1; }
    say "  PETSc HIP para $ARCH e biblioteca de montagem em GPU"
    if ask "  Compilar agora (leva ~20 min)?"; then
      run rm -f "${KFEM_SDK:-$HOME/kfem-sdk}/.stamps/petsc-hip"
      KFEM_PETSC_VARIANT=hip KFEM_HIP_ARCH="$ARCH" run bash "$SRC/build/recipes/30-petsc.sh"
      run bash "$SRC/build/recipes/66-kfem-gpu-asm.sh"
    fi
  else
    command -v nvcc >/dev/null || [[ $DRY == 1 ]] || { say "  nvcc ausente: rode com --install antes."; exit 1; }
    say "  PETSc CUDA para sm_${ARCH:-60} (não testado em hardware real)"
    if ask "  Compilar agora (leva ~30 min)?"; then
      run rm -f "${KFEM_SDK:-$HOME/kfem-sdk}/.stamps/petsc-cuda"
      KFEM_PETSC_VARIANT=cuda KFEM_CUDA_ARCH="${ARCH:-60}" run bash "$SRC/build/recipes/30-petsc.sh"
    fi
  fi
fi

# ------------------------------------------------------------------------------ 6. verificar
step "Verificação"
[[ $DRY == 1 ]] || rm -f "${XDG_CACHE_HOME:-$HOME/.cache}/kfem/backend.json"  # força novo teste de sanidade
if [[ $DRY == 1 ]]; then
  say "  (simulação: nada foi alterado)"
elif [[ -n "$APPIMAGE" ]]; then
  "$APPIMAGE" --diagnose || true
elif [[ -x "${KFEM_SDK:-$HOME/kfem-sdk}/bin/python3" && -f "$SRC/build/env.sh" ]]; then
  ( . "$SRC/build/env.sh" >/dev/null 2>&1
    export LD_LIBRARY_PATH="$KFEM_RUN_LD:${LD_LIBRARY_PATH:-}" PYTHONPATH="$SRC/src"
    "$KFEM_SDK/bin/python3" -m kfem.app.cli --diagnose ) || true
else
  say "  Rode 'KFem-x86_64.AppImage --diagnose' para ver o backend escolhido."
fi
say ""
say "A montagem em GPU é conferida contra a CPU na 1ª iteração de cada cálculo; se não bater ou"
say "for mais lenta, o KFem segue na CPU e registra o motivo no log."
