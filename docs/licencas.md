# Notas de licença do KFem

Resumo de como o projeto trata licenças. Não é parecer jurídico: em caso de dúvida,
consulte o texto de cada licença.

## O KFem

- Código, ícones, tema e textos do KFem: **GPL-3.0-or-later** (ADR 0001). O logotipo foi
  fornecido pelo autor do projeto.
- Isso inclui a biblioteca de montagem em GPU (`src/kfem/solvers/gpu_asm/`) e o tradutor
  FFCx → HIP (`src/kfem/solvers/gpu_assembly.py`), escritos do zero. Nenhum código do
  cuDOLFINx foi usado.
- O KFem não usa nome, ícones, telas nem textos do COMSOL ou de outro software proprietário.
  A leitura de `.mph` existe só para interoperabilidade com arquivos do próprio usuário.

## Componentes dentro do AppImage

A lista completa, com versão, licença e origem, está em `THIRD_PARTY_NOTICES.md`. Os textos
das licenças vão em `usr/share/licenses/` dentro do AppImage. Em resumo:

| Tipo de licença | Componentes | O que implica para quem distribui o AppImage |
|---|---|---|
| Permissivas (BSD, MIT, Apache-2.0, PSF, BSL) | Python, NumPy, PETSc, OpenBLAS, HDF5, VTK, PyVista, Basix, ADIOS2, Matplotlib, ViennaCL, runtime do AppImage… | manter os avisos de copyright e as licenças (já no pacote) |
| LGPL (2.1/3) | Qt, PySide6/Shiboken6, DOLFINx, FFCx, UFL, OCCT | bibliotecas dinâmicas e substituíveis: o AppImage pode ser extraído (`--appimage-extract`) e cada `.so` trocado por outra versão compatível; fontes e receitas de build disponíveis |
| CeCILL-C | MUMPS, PT-Scotch | equivalente à LGPL; mesmas providências |
| GPL-2.0-or-later | Gmsh | compatível com a GPL-3.0 do KFem; exige oferecer as fontes correspondentes |

### Fontes correspondentes

Por causa da GPL (KFem e Gmsh), quem distribui o AppImage precisa oferecer as fontes
correspondentes. O projeto cumpre isso com:

- o repositório do KFem (código + `build/`);
- a lista de fontes com URL e SHA-256 (`build/sources.list`, `build/sha256.lock`) e o guia
  `docs/build.md`. Ao publicar um AppImage, publique junto (ou ofereça) os tarballs dessa
  lista, como estão em `$KFEM_TMP/downloads`.

## O que NÃO vai no AppImage

- Drivers de vídeo e bibliotecas gráficas do sistema (libGL, EGL, Vulkan, DRM), ICDs
  OpenCL, CUDA (`libcuda`) e o runtime ROCm (libamdhip64, rocSPARSE, rocBLAS, hiprtc…).
  Vêm do sistema do usuário, cada um com a licença do fabricante. O script `kfem-gpu-setup`
  só os instala pelos pacotes da distribuição.
- O compilador C (`gcc`) que a DOLFINx usa em tempo de execução.
- `libclang`/LLVM, usados só para gerar os bindings do PySide6 no build.

## Ferramentas de desenvolvimento

Todas gratuitas e livres (CMake, Ninja, ccache, bison, flex, pytest, ruff, mypy,
squashfs-tools), usadas só no build. Nenhuma ferramenta paga é necessária (CLAUDE.md §8).
