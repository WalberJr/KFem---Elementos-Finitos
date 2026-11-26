# Etapa 12 — Empacotamento AppImage (2026-11-23)

## Feito

- **`build/appimage.sh`** monta o AppDir a partir do SDK e gera o AppImage:
  - deixa de fora ferramentas de build, estáticas, documentação e cabeçalhos, exceto os do
    Python (o JIT da DOLFINx precisa deles);
  - remove o `.pth` com caminho absoluto;
  - não empacota drivers nem runtime de GPU (libGL/EGL/Vulkan/DRM, libcuda, ICDs OpenCL,
    libamdhip64, hsa, rocSPARSE, rocBLAS);
  - inclui ícone/logo, `.desktop`, AppStream, licenças e o script `kfem-gpu-setup`;
  - usa o `appimagetool` se existir; senão, `mksquashfs` (zstd) + o runtime oficial
    (type2-runtime) com SHA-256 conferido.
- **`packaging/AppRun`**:
  - escolhe o backend **com teste de sanidade**, guardado em `~/.cache/kfem/backend.json`
    com uma impressão digital de hardware, drivers e variantes (a 1ª execução leva ~3 s);
  - aponta `PETSC_DIR`, `LD_LIBRARY_PATH` e `PYTHONPATH` para a variante escolhida;
  - avisa se não houver `gcc`.
- **Variantes no pacote:** `petsc-cpu`, `petsc-opencl` e `petsc-hip`. A HIP foi recompilada
  para 10 arquiteturas AMD (gfx803, 900, 906, 908, 90a, 1010, 1030, 1100, 1101, 1102: as que
  o ROCm do Ubuntu suporta). A montagem em GPU (`libkfem_gpu_asm.so`) compila os núcleos na
  hora para qualquer GPU HIP.
- A **montagem em GPU passou a independer da variante do PETSc**: basta haver runtime HIP e
  uma GPU; a conferência da 1ª iteração decide.
- **`kfem --solve PROJETO -n N --workdir DIR`**: resolve com MPI pelo `mpiexec` embutido.
- **`packaging/kfem-gpu-setup.sh`** (script à parte, também em `usr/bin/kfem-gpu-setup` no
  AppImage):
  - identifica a placa por `/sys/class/drm` e `lspci` e escolhe a rota: AMD → HIP,
    NVIDIA → CUDA (não testado), outras → CPU;
  - confere o grupo `render` e a arquitetura (`rocminfo`) contra a lista do ROCm da
    distribuição;
  - com `--install`, instala o runtime pelos pacotes do Ubuntu/Debian (pede sudo; nunca
    instala driver de vídeo, só indica o comando);
  - com `--build`, compila a variante do PETSc para a arquitetura da placa e a biblioteca
    de montagem;
  - no fim roda o `--diagnose`. Sem opções, só mostra o plano.
- `THIRD_PARTY_NOTICES.md`: ViennaCL, runtime do AppImage, dependência do ROCm e do gcc do
  sistema.
- O processo do solver iniciado pela interface usa só as bibliotecas da variante escolhida.

## Verificação (AppDir, ambiente limpo: `env -i`, HOME vazio, sem o SDK no PATH)

| Teste | Resultado |
|---|---|
| `AppRun --diagnose` | HIP escolhido; sanidade com erro 7,1·10⁻¹⁴; 3,1 s |
| `AppRun --solve cdi_quick.kfem -n 6` | concluído em 21,6 s; JIT do zero com o gcc do sistema; montagem em GPU carregada do pacote; a conferência escolheu a CPU (malha grossa com 6 processos: 0,051 s contra 0,098 s) |
| Interface pelo AppDir | abre o projeto; barra de status "Cálculo: HIP · Renderização: gpu" |
| `kfem-gpu-setup.sh` (sem opções) | identifica a RX 580 (gfx803, suportada), mostra a rota HIP e o diagnóstico |

Tamanho: AppDir com 1,7 GB (petsc-hip ocupa 578 MB por causa das 10 arquiteturas);
**imagem comprimida (squashfs zstd-19): 315 MB**.

## AppImage final (2026-11-23)

O usuário baixou o runtime oficial (`runtime-x86_64`, type2-runtime "continuous").
SHA-256 registrado em `build/sha256.lock`:
`617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46`. O `github.com` está
bloqueado pelo filtro de rede do ambiente do agente, não pela máquina. O disco `CODES` não
estava montado, então o build usou `KFEM_TMP=~/kfem-build/tmp`.

**Arquivo:** `~/kfem-build/KFem-x86_64.AppImage`, **307 MB**, com SHA-256 em
`KFem-x86_64.AppImage.sha256`.

Testes com o arquivo final, em ambiente limpo (`env -i`, HOME vazio):

| Teste | Resultado |
|---|---|
| `--diagnose` | monta o AppImage e escolhe HIP (sanidade 7,1·10⁻¹⁴), 5 s |
| `--solve cdi_quick.kfem -n 6` (2ª execução, outra montagem, com cache) | ok, 26 s |
| `--solve cdi_full_quick.kfem -n 6` (malha completa, 0–5 s) | **montagem na GPU conferida** (0,195 s contra 0,313 s na CPU), transiente em 42,5 s, mesmo resultado do ambiente de desenvolvimento (V = 0,058027 em t = 5 s) |
| Interface | abre o projeto; "Cálculo: HIP · Renderização: gpu" |

Defeito achado só no arquivo final e corrigido: o cache do backend guardava `PETSC_DIR`
absoluto, mas o AppImage monta num diretório diferente a cada execução. A 2ª execução
perdia o `petsc4py`. Agora os caminhos ficam relativos (`${KFEM_SDK}/petsc-hip`); teste em
`tests/hw/test_env_shell.py`.

## Pendente

- Teste em sistemas limpos (Ubuntu 24.04, Debian 13, Fedora) sem acesso a containers/VMs
  (o usuário não está no grupo `docker`). Feito só o ambiente limpo (`env -i`) nesta máquina.
- A máquina de destino precisa de `gcc` para os modelos (JIT da DOLFINx).
- Para NVIDIA: variante CUDA não compilada (sem CUDA Toolkit nem placa para testar).

Sugestão de commit (o usuário faz):
`Etapa 12: AppImage (307 MB) relocável com variantes CPU/OpenCL/HIP, seleção de backend com sanidade em cache, kfem-gpu-setup e --solve -n`

## Reconstrução e exportação (2026-11-25)

- AppImage refeito com o código atual (geometria por polígono/diferença/interseção, `dfine`):
  314 MB, SHA-256 `a1a53c9cddc9ea4a6d17f0ef8fddc17471ae96cdf7730e166e206025c1b8c4ae`.
- Pacote de distribuição em `/media/walber/HDD_I/KFem` (cópia de `~/kfem-build/export`):
  AppImage + SHA-256, `instalar.sh` (instala por usuário, sem sudo: confere o SHA-256, copia
  para `~/Aplicativos/KFem`, cria o atalho no menu, confere gcc, FUSE e glibc e roda o
  `--diagnose`), `LEIA-ME.txt`, manuais, exemplos (CDI e Xie 2022) e o código-fonte.
- Teste numa cópia tirada do HD, ambiente limpo (`env -i`, HOME vazio): instalação ok;
  `--solve cdi_quick.kfem -n 2` ok com HIP (15,6 s) e com `KFEM_GPU=cpu` (14,8 s).
- `AppRun --python SCRIPT.py`: roda scripts com o Python e o KFem do pacote (gerar projetos,
  pós-processar). AppImage refeito: SHA-256
  `801d085c674a0360891248f49f6bc7097175dc5601ef383bb920cafe6272a799`.
- `HDD_I/KFem/Simulations/{1D,2D}`: entradas `.kfem` das simulações de Xie 2022 (36 casos 1D
  corrigidos, 9 casos 2D e 5 testes de malha), `rodar.sh`, scripts e tutoriais (md + pdf).
  Teste numa cópia: `1D/rodar.sh pH0_j100` e `figuras2d.py` pelo `--python`, ok.
