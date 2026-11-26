# 0011 — Build do zero, nativo, sem container

**Status:** Aceito (usuário, 2026-11-18). Substitui o ADR 0003.

**Decisão:**
- Toda a pilha continua compilada do zero, com versões, URLs e SHA-256 fixados em
  `build/versions.env`, mas **direto na máquina** (Ubuntu 24.04), sem Docker nem Podman.
- O prefixo de instalação fica no disco interno, num local que não exige sudo:
  `~/kfem-sdk/` (relocável, com subprefixos `petsc-{cpu,cuda,hip,opencl}`). O `/opt/kfem`
  exigiria root.
- Para não misturar com o sistema: o compilador vem do sistema (gcc/g++/gfortran 13), mas
  as bibliotecas da pilha (MPICH, OpenBLAS, HDF5, PETSc…) são as compiladas no prefixo. As
  receitas usam `PATH`/`PKG_CONFIG_PATH`/`CMAKE_PREFIX_PATH` explícitos, sem
  `LD_LIBRARY_PATH` global.
- ccache e downloads ficam em `/media/walber/CODES/kfem/`; as árvores de build ficam no
  disco interno e são apagadas após cada componente.

**Consequência importante (compatibilidade do AppImage):**
- Um AppImage só roda em sistemas com glibc **igual ou mais nova** que a da máquina de
  build. Aqui a glibc é 2.39, então o AppImage rodaria em Ubuntu 24.04+, Fedora 40+ e
  Debian 13+, mas **não** em Ubuntu 22.04 nem em Debian 12. O critério do CLAUDE.md §11
  ("Ubuntu 22.04+, Debian estável") precisa ser ajustado, ou então será preciso montar uma
  toolchain com glibc antiga (sysroot), que dá bem mais trabalho.
- **Escolha do usuário (2026-11-18): aceitar Ubuntu 24.04+, Fedora 40+ e Debian 13+.**
  Não haverá sysroot com glibc antiga.
- O teste em "containers limpos" da Etapa 12 vira teste em máquinas ou VMs, ou num
  container usado **só para testar**, nunca para compilar (a confirmar com o usuário).

**Pacotes do sistema (não compilados), definidos em 2026-11-18:**
- Cabeçalhos de vídeo e janelas (X11/xcb, xkbcommon, GL/EGL, drm, wayland, fontconfig,
  freetype) vêm do sistema via apt. As bibliotecas correspondentes **também vêm do
  sistema** em tempo de execução: drivers e servidor gráfico não se empacotam.
- `libclang`/`llvm` do sistema entram só como **ferramenta de build** do Shiboken6/PySide6.
  Compilar o LLVM do zero custaria horas e dezenas de GB, e o libclang não vai no AppImage.
