# Guia de build do KFem (do zero até o AppImage)

Toda a pilha numérica e gráfica é compilada a partir das fontes, nativamente, sem
container (ADR 0011). As versões, URLs e SHA-256 ficam fixados no repositório. Este guia
reproduz o `KFem-x86_64.AppImage`.

## 1. Máquina de build

- **Ubuntu 24.04 x86_64** (glibc 2.39). O AppImage só roda em sistemas com glibc igual ou
  mais nova (ADR 0011).
- Disco: ~10 GB para o SDK e o AppDir, mais o espaço temporário de cada componente. Compilar
  Qt e VTK chega a vários GB por vez; as árvores de build são apagadas ao fim de cada receita.
- Tempo: várias horas com 12 threads (Qt, VTK, PETSc e OCCT são os mais longos). O ccache
  acelera recompilações.
- Rede: `pypi.org`, `github.com` e os sites de cada projeto (ver `build/sources.list`). O
  configure do PETSc baixa MUMPS, ScaLAPACK, METIS, hypre e ViennaCL pelas versões que o
  próprio PETSc fixa.

### Pacotes do sistema (compilador, cabeçalhos de vídeo/janela, ferramentas)

```bash
sudo apt install gcc g++ gfortran make patch perl m4 autoconf automake pkg-config rsync curl xz-utils zstd squashfs-tools zlib1g-dev libssl-dev libffi-dev libbz2-dev liblzma-dev libsqlite3-dev libncurses-dev uuid-dev libexpat1-dev libx11-dev libx11-xcb-dev libxext-dev libxrender-dev libxi-dev libxkbcommon-dev libxkbcommon-x11-dev libxcb1-dev libxcb-cursor-dev libxcb-glx0-dev libxcb-icccm4-dev libxcb-image0-dev libxcb-keysyms1-dev libxcb-randr0-dev libxcb-render0-dev libxcb-render-util0-dev libxcb-shape0-dev libxcb-shm0-dev libxcb-sync-dev libxcb-util-dev libxcb-xfixes0-dev libxcb-xinerama0-dev libxcb-xinput-dev libxcb-xkb-dev libgl-dev libgl1-mesa-dev libegl-dev libegl1-mesa-dev libdrm-dev libwayland-dev libfontconfig-dev libfreetype-dev libclang-18-dev llvm-18-dev ocl-icd-opencl-dev
```

O `libclang`/`llvm` só servem para gerar os bindings do PySide6 e não entram no AppImage.

### Para a variante de GPU AMD (HIP), opcional

ROCm dos pacotes do Ubuntu 24.04 (o mesmo que `packaging/kfem-gpu-setup.sh --install --build`
instala):

```bash
sudo apt install hipcc librocsparse-dev libhipsparse-dev librocblas-dev libhipblas-dev librocsolver-dev libhipsolver-dev librocprim-dev librocthrust-dev libhipcub-dev librocrand-dev libhiprand-dev rocminfo
```

## 2. Diretórios

`build/env.sh` define tudo (nada é instalado no sistema):

| Variável | Padrão | Conteúdo |
|---|---|---|
| `KFEM_SDK` | `~/kfem-sdk` | prefixo de instalação (Python, bibliotecas, `petsc-{cpu,opencl,hip}`) |
| `KFEM_BUILD` | `~/kfem-build` | árvores de build temporárias, AppDir e o AppImage gerado |
| `KFEM_TMP` | `/media/walber/CODES/kfem` | downloads (`downloads/`), `ccache/` e `logs/`; **mude** para um diretório seu |
| `JOBS` | 12 | compilações em paralelo |

Exemplo, tudo no disco interno:

```bash
export KFEM_TMP=$HOME/kfem-tmp
```

## 3. Baixar e conferir as fontes

```bash
bash build/fetch.sh
```

Cada arquivo de `build/sources.list` é baixado para `$KFEM_TMP/downloads` e conferido
contra `build/sha256.lock`. Hash diferente faz o script falhar; nunca edite o lock para
"consertar" um download.

## 4. Compilar a pilha (variante CPU)

```bash
bash build/build-all.sh
```

As receitas rodam em ordem (`build/recipes/NN-*.sh`), com log em `$KFEM_TMP/logs/NN-*.log`:

| Faixa | Componentes |
|---|---|
| 01–05 | bison, flex, CMake, Ninja, ccache (ferramentas, em `$KFEM_SDK/tools`) |
| 10–15 | Python, OpenBLAS, MPICH, HDF5, PT-Scotch, cabeçalhos do Boost |
| 20–23 | ferramentas de build Python, NumPy, pacotes com C, mpi4py |
| 30–31 | PETSc + petsc4py (variante de `KFEM_PETSC_VARIANT`, padrão `cpu`), h5py |
| 40–45 | spdlog, pugixml, Basix, UFL/FFCx, ADIOS2, DOLFINx |
| 50–52 | OCCT, Gmsh, pacotes Python puros (meshio, pint…) |
| 60–65 | Qt (base, svg, tools), PySide6/Shiboken6, VTK, PyVista/pyvistaqt/Matplotlib |
| 66 | biblioteca de montagem em GPU do KFem (só se houver `hipcc`) |

Cada componente pronto ganha um carimbo em `$KFEM_SDK/.stamps/`. Para refazer um, apague o
carimbo dele. Para continuar a partir de uma receita: `bash build/build-all.sh 40` (da 40
até o fim) ou `bash build/build-all.sh 30 31`.

## 5. Variantes de GPU do PETSc

A mesma receita, com outra variante, em prefixo separado:

```bash
KFEM_PETSC_VARIANT=opencl bash build/recipes/30-petsc.sh
```

```bash
KFEM_PETSC_VARIANT=hip KFEM_HIP_ARCH="gfx803,gfx900,gfx906,gfx908,gfx90a,gfx1010,gfx1030,gfx1100,gfx1101,gfx1102" bash build/recipes/30-petsc.sh
```

```bash
bash build/recipes/66-kfem-gpu-asm.sh
```

A receita da variante HIP já resolve as diferenças do ROCm do Ubuntu: versão lida de
`hip/hip_version.h`, bibliotecas em `lib/x86_64-linux-gnu` e `LC_ALL=C.UTF-8` para o
`hipcc`. A variante CUDA (`KFEM_PETSC_VARIANT=cuda`) está prevista na receita, mas não foi
compilada nem testada (ADR 0005).

## 6. Testes

```bash
source build/env.sh
```

```bash
export LD_LIBRARY_PATH=$KFEM_RUN_LD:$LD_LIBRARY_PATH PYTHONPATH=src
```

Rode os grupos em processos separados (os testes de FEM iniciam o MPI no processo do
pytest, e o teste da interface que lança o solver não convive com isso):

```bash
$KFEM_SDK/bin/python3 -m pytest -q tests/hw tests/gui
```

```bash
$KFEM_SDK/bin/python3 -m pytest -q tests/fem
```

Qualidade do código:

```bash
ruff check src tests && mypy src
```

(`ruff`, `mypy` e `pytest` ficam num venv de desenvolvimento sobre o Python do SDK:
`$KFEM_SDK/bin/python3 -m venv --system-site-packages ~/kfem-build/devvenv`.)

## 7. Gerar o AppImage

Precisa do runtime oficial do AppImage (`type2-runtime`), baixado e conferido pelo hash:

```bash
bash build/fetch.sh appimage-runtime
```

```bash
bash build/appimage.sh
```

Resultado: `$KFEM_BUILD/KFem-x86_64.AppImage` e `KFem-x86_64.AppImage.sha256`. O script:

1. copia o SDK para o AppDir, sem ferramentas de build, bibliotecas estáticas, documentação
   e cabeçalhos (exceto os do Python, que o JIT da DOLFINx usa);
2. remove drivers e runtimes de GPU, que sempre vêm do sistema;
3. inclui o código do KFem, o `AppRun`, ícone, `.desktop`, AppStream, licenças e o
   `kfem-gpu-setup`;
4. comprime com `mksquashfs` (zstd 19) e junta ao runtime (ou usa o `appimagetool`, se
   estiver em `$KFEM_SDK/tools/bin`).

Tamanho de referência (variantes cpu + opencl + hip para 10 arquiteturas): AppDir com
1,7 GB; **AppImage com 307 MB**.

## 8. Conferir o AppImage em ambiente limpo

```bash
env -i HOME=$(mktemp -d) PATH=/usr/bin:/bin LANG=C.UTF-8 ./KFem-x86_64.AppImage --diagnose
```

```bash
env -i HOME=$(mktemp -d) PATH=/usr/bin:/bin LANG=C.UTF-8 ./KFem-x86_64.AppImage --solve projeto.kfem -n 6
```

O primeiro comando deve mostrar o backend escolhido e o motivo. O segundo, no log, a
conferência da montagem em GPU ("montagem na GPU conferida" ou "montagem na CPU foi mais
rápida").

## 9. Reprodutibilidade

- Fontes: URL e SHA-256 fixados (`build/sources.list`, `build/sha256.lock`); pacotes Python
  com versões travadas (`build/python-*.lock`).
- Compilador: o do Ubuntu 24.04 (gcc 13). Outra versão de gcc gera binários diferentes, mas
  equivalentes.
- O AppImage não é byte a byte reprodutível (datas nos arquivos e na squashfs). A
  conferência de um build refeito é funcional: `--diagnose`, a bateria de testes e um caso
  CDI curto com os mesmos valores das sondas.
