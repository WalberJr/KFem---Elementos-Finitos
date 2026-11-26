# Etapa 3 — Detecção de hardware e GPU · relatório

**Data:** 2026-11-18 · **Status:** concluída. A ligação real com as variantes de PETSc em GPU
fica para a Etapa 11.

## Feito
- `kfem.hw.detect`: enumera GPUs por `/sys/class/drm` (fornecedor, dispositivo, driver,
  slot), sem contar os conectores. Encontra `libcuda`, `libamdhip64` e os ICDs OpenCL, e
  registra as ferramentas `nvidia-smi`, `rocminfo`, `clinfo` e `lspci`.
- `kfem.hw.backend`: escolhe na ordem CUDA → HIP → OpenCL → CPU. Cada candidato precisa de
  (1) variante no SDK, (2) driver e (3) teste de sanidade. Quando um falha, o motivo fica
  registrado e o próximo é tentado. Também:
  - aceita o override `KFEM_GPU`;
  - prepara o ambiente do Rusticl (`RUSTICL_ENABLE`, `RUSTICL_FEATURES=fp64`) sem
    sobrescrever valores do usuário;
  - escolhe a renderização: GPU, ou Mesa software quando não há driver.
- `kfem.hw.sanity`: teste de sanidade em **subprocesso**. Resolve Poisson 1D com os tipos
  `cuda`/`hip`/`viennacl` do PETSc e compara com a solução exata.
- `kfem --diagnose` e `python -m kfem.hw.env_shell`, este último usado pelo AppRun.

## Verificação
- `pytest tests/hw`: 16 testes com `/sys` e bibliotecas simulados. Cobrem NVIDIA com e sem
  driver, NVIDIA com nouveau + OpenCL, AMD com ROCm, RX 580 sem ROCm, AMD só com ICD de CPU,
  Intel, máquina sem GPU, falha de sanidade, variante ausente e override.
- Na máquina real: a RX 580 (0x6fdf, amdgpu) é detectada; renderização = GPU; ICDs
  `intel64` e `rusticl`. Há um `libamdhip64.so` instalado no sistema, mas a placa (Polaris)
  está na lista "sem suporte ROCm". Quando a variante HIP existir, o teste de sanidade
  decide, e a escolha cai para OpenCL. Enquanto as variantes de GPU não forem compiladas
  (Etapa 11), o cálculo escolhido é CPU, com esse motivo no relatório.

## Pendente
- Etapa 11: compilar as variantes de PETSc em GPU e rodar o teste de sanidade de verdade.

## Commit sugerido
`Etapa 3: detecção de GPU, seleção de backend e kfem --diagnose`
