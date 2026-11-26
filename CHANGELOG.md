# Registro de mudanças

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versões
seguem [SemVer](https://semver.org/lang/pt-BR/).

## [0.1.0.dev0] — 2026-11-23 (pré-lançamento)

Primeira versão funcional completa, ainda sem validação contra o COMSOL (Etapa 10 aguarda os
dados de referência do usuário).

### Simulação
- Caso CDI (deionização capacitiva / diodo iônico): Brinkman em meio poroso, corrente
  secundária com dupla camada capacitiva e reação Butler–Volmer linear, transporte de Na⁺ e
  Cl⁻ diluídos com convecção e migração, equações globais (modo de carga com rampa de
  tensão), em regime estacionário e transiente.
- Transiente com BDF2 de passo variável, formulação em ln c com limites físicos, estimador
  de erro em concentração e recuperação automática de falhas do PETSc.
- Pilha FEniCSx 0.11 (DOLFINx, Basix, FFCx, UFL 2026.1) + PETSc 3.26.1 (MUMPS, hypre),
  compilada do zero.

### GPU (ADR 0005, 0013)
- Detecção de GPUs NVIDIA, AMD e Intel com teste de sanidade real; nunca escolhe uma
  variante quebrada e cai para a CPU sem erro (`--diagnose`).
- **Montagem dos elementos finitos da DOLFINx na GPU (HIP)**: núcleos do FFCx traduzidos e
  compilados na hora (hiprtc) para a GPU presente. Conferida contra a CPU na 1ª iteração
  (resultado e tempo). Caso CDI, malha completa, RX 580: 40 s contra 62 s só na CPU, com
  resultados idênticos.
- Variantes do PETSc: CPU, OpenCL/ViennaCL e HIP (10 arquiteturas AMD). Solver linear
  híbrido GPU/CPU com calibração automática.
- `kfem-gpu-setup`: identifica a placa e instala o runtime/variante para ela.

### Interface
- Árvore do modelo → configurações → janela gráfica 3D (VTK) → saídas (mensagens,
  progresso, log, tabela); tema lilás/verde-escuro/preto; ícones e logotipo próprios;
  interface em pt-BR.
- Cálculo em processo separado (MPI), cancelável, com campos e sondas atualizados ao vivo
  e modo de acompanhamento de cálculos externos (`--watch`).
- Indicador de uso de CPU, RAM, GPU e VRAM na barra de status.
- **Trabalhos recentes** (aba Início e menu Arquivo) no lugar do exemplo embutido: a
  interface mostra só os projetos do usuário.
- **Ajuda → Manual do usuário (PDF)** (F1) e **Ajuda → Tutorial (PDF)**, incluídos no AppImage.
- Malha mostrada colorida por domínio; escala vertical automática (só no desenho) para
  geometrias muito alongadas.

### Arquivos
- Formato de projeto aberto `.kfem` (JSON versionado + malha XDMF/HDF5).
- Importação de `.mph` (parâmetros, geometria, malha; relatório do que não foi convertido).
- Resultados em XDMF/HDF5; exportação PNG e CSV.

### Empacotamento
- AppImage único (314 MB, com o manual e o tutorial em PDF) para Ubuntu 24.04+, Debian 13+ e Fedora 40+ (glibc ≥ 2.39), sem
  drivers embutidos; escolha do backend em cache por máquina.
- `kfem --solve projeto.kfem -n N` para rodar sem interface com MPI.

### GPU — instalação automática (2026-11-24)
- Na 1ª execução, placa AMD/NVIDIA sem cálculo na GPU → oferta de instalação com pkexec;
  **Ajuda → Configurar placa de vídeo…** a qualquer momento.
- `kfem-gpu-setup`: rota NVIDIA completa (modelo e compute capability via nvidia-smi, driver
  via ubuntu-drivers, CUDA Toolkit, PETSc CUDA para `sm_XX` da placa), grupo `render` para
  AMD, troca automática dos cabeçalhos `thrust` ROCm × CUDA, modos `--auto` e `--dry-run`.
- Motor genérico de formas fracas e **Equação personalizada** (fases M0/M1).

### Corrigido
- "Gerar malha" não mostrava a malha (o arquivo da DOLFINx tem vários grids e o meshio não o lê).
- Painel de configurações mostrava nomes internos (`section.geometry`, `info`) como título.

### Problemas conhecidos
- Variante CUDA (NVIDIA) não incluída: não houve placa para testar.
- Montagem em GPU só para integrais de célula.
- O solver linear híbrido na GPU trava com vários processos; fica desligado em paralelo.
- MUMPS com várias threads OpenMP num só processo pode travar (conflito OpenBLAS/OpenMP);
  use processos MPI.
- Testado só no Ubuntu 24.04.

### Artefato

| Arquivo | SHA-256 |
|---|---|
| `KFem-x86_64.AppImage` | `e420eb81b7593a46651977398634cc1bb17b2a15a151df205d35dd373a2cb908` |
