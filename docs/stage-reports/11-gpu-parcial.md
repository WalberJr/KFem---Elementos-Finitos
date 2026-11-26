# Etapa 11 — Cálculo em GPU (relatório parcial, 2026-11-18)

## Feito

- **Variante `petsc-opencl`** compilada (PETSc 3.26.1 + ViennaCL 1.7.1 + OpenCL, com MUMPS,
  hypre, ScaLAPACK e petsc4py), em `~/kfem-sdk/petsc-opencl`, pela receita
  `build/recipes/30-petsc.sh` com `KFEM_PETSC_VARIANT=opencl`.
- **Solver linear híbrido** `src/kfem/solvers/gpu_linear.py`: converte a matriz montada pela
  DOLFINx para o tipo de GPU do backend (`aijviennacl`, `aijcusparse`, `aijhipsparse`) e
  resolve com GMRES na GPU. Se o Krylov não convergir, o mesmo sistema é resolvido na CPU
  (MUMPS). Depois de 8 falhas seguidas, a GPU é desligada no resto do cálculo, com o motivo
  no log. Ligado ao transiente (`electrochem.py`) quando `KFEM_COMPUTE_BACKEND` é uma GPU.
  Testes: `tests/fem/test_gpu_linear.py`.
- **Perfil por fase do Newton** registrado no log ao fim de todo transiente.

## Resultado na RX 580 (OpenCL)

| Teste | Resultado |
|---|---|
| Kernel OpenCL mínimo em `float` e `double` (rusticl + `RUSTICL_FEATURES=fp64`) | funciona |
| Vetor `viennacl` do PETSc (norma) | funciona, com dezenas de "radeonsi: LLVM failed to upload shader" |
| Conversão de matriz para `aijviennacl` | **falha de segmentação** |
| `kfem --diagnose` | teste de sanidade OpenCL falha → escolhe CPU, sem abortar (comportamento previsto) |

Parte dos kernels do ViennaCL 1.7.1 (2016), em especial os de matriz esparsa, não carrega
no driver Mesa rusticl/radeonsi do Polaris. Trocar o compilador de shader
(`AMD_DEBUG=useaco/nouseaco`) não muda nada. Pela regra de duas falhas, esta rota parou.

## Perfil do transiente CDI (CPU, MUMPS)

| Malha | Processos | s/iteração | Montagem J | Montagem F | Lifting/contorno | Solve |
|---|---|---|---|---|---|---|
| 7 012 células | 1 | 0,46 | 35% | 10% | 22% | 33% |
| 7 012 células | 4 | 0,14 | 32% | 9% | 21% | 37% |
| 43 128 células | 4 | 0,75 | 36% | 10% | 16% | 37% |

Os três primeiros grupos (≈ 62%) são laços de núcleo por elemento na DOLFINx (C++). O
restante (≈ 37%) é a fatoração LU do MUMPS. Sondas, sensibilidade de V e atualizações
somam menos de 1%.

Teste de otimização na CPU: gravar os valores de Dirichlet em `w` antes da montagem zera o
lifting (−25% por iteração, mesmo resultado até a 5ª casa). Mas o Newton passou de 255 para
400 iterações e o tempo total piorou. Foi revertido; pendente rever o critério de parada.

## Onde a GPU compensaria (em ordem)

1. **Montagem da Jacobiana e do resíduo (≈ 46%) e do lifting (≈ 16–22%)**: laço
   independente por célula com o núcleo gerado pelo FFCx, o caso ideal para GPU. Existe o
   cuDOLFINx (montagem da DOLFINx em GPU, só CUDA; licença ainda a verificar). Na RX 580 o
   caminho seria portá-lo para HIP.
2. **Solve (≈ 37%)**: Krylov + precondicionador na GPU (rocSPARSE/hipSPARSE via
   `aijhipsparse`). A convergência para este sistema rígido (formulação ln c) não está
   garantida; o solver híbrido já volta ao MUMPS por sistema quando falha.
3. Atualizações pontuais, estimador de erro e sondas: < 1%, não compensa.

Com a malha atual (43 mil células, ~0,75 s por iteração em 4 núcleos), o ganho depende do
custo de transferência CPU↔GPU a cada iteração. Precisa ser medido, não prometido.

## Rota HIP na RX 580 (2026-11-19): funciona

O usuário instalou os pacotes ROCm 5.5–5.7 do Ubuntu. As bibliotecas rocSPARSE e rocBLAS
trazem código para `gfx803`, e um kernel HIP de teste em `double` roda na RX 580.

- **Variante `petsc-hip`** compilada pela receita, com três ajustes para o ROCm do Ubuntu:
  versão lida de `hip/hip_version.h` (não há `rocm-core`), bibliotecas passadas
  explicitamente (ficam em `lib/x86_64-linux-gnu`) e `LC_ALL=C.UTF-8` (o `hipcc` é um
  script Perl e avisos de locale no stderr fazem o configure recusar os testes).
- **`kfem --diagnose` escolhe HIP**: o teste de sanidade resolve na GPU com erro 7·10⁻¹⁴.
- Dois erros do teste de sanidade foram corrigidos: o subtipo `seqhip` era recusado, e o
  subprocesso herdava a `libpetsc` de outra variante.
- **A interface agora usa a escolha com teste de sanidade**, feita uma vez em segundo plano.
  Antes ela mostrava "OPENCL" e mandaria o cálculo para a rota quebrada.

### Solve na GPU × CPU (sistema real do CDI em t = 60 s)

| Sistema | MUMPS 1 proc. | MUMPS 4 proc. | GPU GMRES+ILU(0) | GPU BiCGStab+ILU(0) | GPU Jacobi |
|---|---|---|---|---|---|
| 15 920 incógnitas | 0,065 s | — | 0,385 s (28 it.) | — | 0,210 s, erro 2·10⁻⁵ |
| 91 108 incógnitas | 0,51 s | **0,285 s** | 0,91 s (75 it.) | 1,41 s | não converge |

GAMG na GPU diverge. **Transiente com a GPU forçada** (`KFEM_GPU_FORCE=1`): 486/486
sistemas resolvidos na RX 580, nenhuma falha, resultados **idênticos** aos da CPU em todos
os dígitos impressos, mas 295 s contra 114 s na CPU.

Política adotada: o solver híbrido **calibra** nos 6 primeiros sistemas (resolve nos dois e
compara a soma dos tempos) e fica com o mais rápido, registrando o motivo no log. Na RX 580
ele fica com a CPU.

### Escalonamento na CPU (malha completa, 43 mil células)

| Processos MPI | Tempo (20 s simulados) | s/iteração |
|---|---|---|
| 4 | 124 s | 0,77 |
| 6 (núcleos físicos, padrão da interface) | 91 s | 0,57 |

## Montagem da DOLFINx na GPU (2026-11-19) — ADR 0013

Diagnóstico (`KFEM_ASM_PROFILE`), malha completa, serial: montar J leva 1,02 s, dos quais
empacotar coeficientes leva 0,005 s; inserir no PETSc custa o mesmo que numa CSR nativa.
Quase todo o tempo é o núcleo do FFCx (79 pontos de quadratura por causa dos `exp`). J e F
só têm integrais de célula.

Implementação (código próprio, GPL; detalhes no ADR 0013):

- `src/kfem/solvers/gpu_asm/kfem_gpu_asm.cpp`: biblioteca HIP mínima (hiprtc, memória,
  lançamento), compilada por `build/recipes/66-kfem-gpu-asm.sh`.
- `src/kfem/solvers/gpu_assembly.py`: traduz o C do FFCx para HIP. Uma thread por célula
  soma a matriz do elemento direto na CSR local; o lifting (inclusive o do sistema de
  sensibilidade da tensão) sai da mesma matriz do elemento.
- `electrochem.py`: conferência na 1ª iteração (resultado e tempo), com volta automática à
  CPU.

Problemas encontrados e resolvidos no caminho:

- Extração das funções do FFCx (blocos internos fechados na coluna 0).
- O JIT do FFCx não devolve o código quando o módulo já está em cache; o código passa a ser
  gerado direto pelo compilador do FFCx.
- Em paralelo, a conferência copiava o vetor com `VecCopy`, que ignora as entradas
  fantasmas: dava uma diferença falsa. A montagem em si estava certa (três caminhos de
  lifting batem em 10⁻¹⁸).
- O lifting passou a valer em todas as linhas, como na DOLFINx: em paralelo, um dof fantasma
  pode ser de Dirichlet num processo e livre no dono.
- `__launch_bounds__(64)`: sem isso o compilador limitava a 64 registradores e derramava
  4–5 kB por thread na memória de rascunho. Com ele, **o núcleo ficou 3,4× mais rápido**.
- O solver linear híbrido HIP travava com vários processos: passou a ficar desligado em
  paralelo (`KFEM_GPU_SOLVE=1` força).

### Resultados

Conferência: J igual à da DOLFINx em 10⁻¹⁶ e F em 10⁻²¹ (serial e com 2, 3 e 6 processos).
As sondas são idênticas em todos os dígitos impressos.

| Malha, intervalo | Configuração | Tempo |
|---|---|---|
| grossa (7 mil células), 0–80 s | CPU, 1 processo | 114,5 s |
| grossa, 0–80 s | montagem na GPU, 1 processo | **39,2 s** (2,9×) |
| completa (43 mil), 0–5 s | CPU, 6 processos | 62,3 s |
| completa, 0–5 s | montagem na GPU + MUMPS, 2 processos | 49,0 s |
| completa, 0–5 s | montagem na GPU + MUMPS, 3 processos | 42,2 s |
| completa, 0–5 s | **montagem na GPU + MUMPS, 6 processos** | **40,1 s** (1,55×) |

Montagem por iteração na malha completa: 1,6 s na CPU com 1 núcleo, 0,30 s com 6 núcleos e
0,17–0,19 s na GPU. Agora o MUMPS é a maior parte do tempo.

Não funcionou: 1 processo com MUMPS em 6 threads OpenMP ficou parado no passo do escoamento
(provável conflito entre threads do OpenBLAS e OpenMP; não investigado).

## Teste de 7200 s na malha completa (2026-11-19)

43 036 células, 6 processos, montagem na GPU (conferida: J 1,2·10⁻¹⁶, F 1,1·10⁻²¹) e solve
com MUMPS. **Concluído em 4465 s (1 h 14 min)**: 679 passos aceitos, 234 rejeitados, 7081
iterações de Newton. Gráfico: `docs/stage-reports/cdi_7200s_gpu.png`.

| t (s) | Corrente (mA) | V (V) | c saída Na (mol/m³) | c saída Cl (mol/m³) |
|---|---|---|---|---|
| 1200 | 9,34 | 0,664 | 4,73 | 2,30 |
| 2400 | 5,11 | 0,907 | 8,35 | 5,63 |
| 3600 | 2,84 | 1,037 | 10,81 | 8,24 |
| 4800 | 1,58 | 1,110 | 13,01 | 10,86 |
| 6000 | 0,83 | 1,153 | 14,65 | 12,62 |
| 7200 | 0,42 | 1,176 | 15,50 | 13,50 |

A saída dessaliniza até cerca de 500 s e depois volta a subir, enquanto a tensão sobe e a
corrente cai: os eletrodos se carregam. A validação contra o COMSOL depende dos CSVs de
referência (Etapa 10).

Também corrigido: a barra de progresso dava o mesmo peso a cada passo do estudo (o
escoamento estacionário ocupava 50%). Agora um passo transiente pesa 20× um estacionário.

## Pendente

- Aprovação do ADR 0013 (montagem na GPU).
- Solver híbrido HIP travando em paralelo (investigar se o solve na GPU voltar a interessar).
- Teste da malha completa até 7200 s (com a CPU sozinha, estimado em muitas horas).
- Variante CUDA: compilada só quando houver máquina NVIDIA para testar.

Sugestão de commit (o usuário faz):
`Etapa 11 (parcial): montagem da DOLFINx na GPU via HIP/hiprtc (1,55× no CDI), variantes PETSc OpenCL/HIP, sanidade na interface`
