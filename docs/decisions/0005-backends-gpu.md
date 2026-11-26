# 0005 — Backends de cálculo em GPU e seleção em tempo de execução

**Status:** Aceito (usuário, 2026-11-17: "o AppImage final deve identificar a placa de vídeo
de qualquer máquina automaticamente e rodar a simulação")

**Decisão:**
- Um único AppImage com quatro variantes de PETSc (e petsc4py/DOLFINx ligados a cada uma):
  `cuda` (NVIDIA), `hip` (AMD com ROCm), `opencl` (ViennaCL; fallback universal) e `cpu`.
- Ordem de escolha automática: CUDA → HIP → OpenCL → CPU. Um backend só é usado se a
  variante existir, o driver do sistema estiver presente e um teste rápido (sistema linear
  pequeno comparado com a CPU) passar. Falha em qualquer ponto → próximo backend, com o
  motivo no log. A simulação nunca aborta por falta de GPU.
- Override: `KFEM_GPU=auto|cuda|hip|opencl|cpu` e opção nas preferências.
- Drivers de GPU nunca são empacotados (vêm do sistema).

**Consequências e riscos conhecidos:**
- Na máquina de desenvolvimento (AMD RX 580, Polaris) só o backend OpenCL é testável, e hoje
  não havia ICD OpenCL da AMD. **Em 2026-11-18 o usuário instalou `mesa-opencl-icd`
  25.2.8 (Rusticl)** e o `clinfo` confirmou: com `RUSTICL_ENABLE=radeonsi` a RX 580 aparece
  como dispositivo OpenCL 3.0 (32 CUs, 8 GiB). **Precisão dupla (fp64) vem desligada por
  padrão**; com `RUSTICL_FEATURES=fp64` o Rusticl expõe `cl_khr_fp64`. Esse fp64 é
  experimental no Rusticl: a correção numérica tem de ser comprovada pelo teste de sanidade
  contra a CPU (Etapa 3) e pelo caso CDI (Etapa 11). O `AppRun`/`kfem.hw` deve definir
  `RUSTICL_ENABLE=radeonsi` e `RUSTICL_FEATURES=fp64` antes de testar o backend OpenCL,
  sem sobrescrever valores já definidos pelo usuário.
- CUDA e HIP só podem ser validados em hardware NVIDIA/AMD-ROCm; até lá ficam marcados
  como "compilados, não testados em hardware real".
- Versões novas do CUDA abandonam arquiteturas antigas de GPU; placas NVIDIA antigas podem
  cair para OpenCL. Lista de arquiteturas a definir na Etapa 11.
- A montagem do sistema (DOLFINx) roda na CPU; a GPU acelera a solução linear. Ganho de
  velocidade depende do tamanho do problema e será medido, não prometido.
- As bibliotecas CUDA/ROCm aumentam bastante o tamanho do AppImage.
