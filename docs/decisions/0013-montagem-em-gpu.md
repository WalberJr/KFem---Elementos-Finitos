# 0013 — Montagem de elementos finitos na GPU (HIP) e solve na CPU

**Status:** Proposto (aguardando aprovação do usuário). Complementa o ADR 0005.

## Contexto

Medidas no transiente do caso CDI (malha completa, 43 mil células, RX 580 / gfx803):

- A montagem da Jacobiana, do resíduo e do lifting na DOLFINx ocupa cerca de 60% do tempo.
  Quase todo esse tempo é o núcleo por elemento gerado pelo FFCx: a forma em ln c tem
  `exp()`, e o FFCx usa 79 pontos de quadratura. Empacotar coeficientes e inserir no PETSc
  é desprezível.
- O solve na GPU (PETSc HIP, Krylov + ILU(0)) foi 3× mais lento que o MUMPS na CPU. Jacobi e
  GAMG não convergem neste sistema.
- O cuDOLFINx (montagem da DOLFINx em GPU) existe só para CUDA.

## Decisão

1. **Montagem na GPU com código próprio** (`src/kfem/solvers/gpu_assembly.py` +
   `src/kfem/solvers/gpu_asm/kfem_gpu_asm.cpp`, GPL-3.0-or-later):
   - o código C do FFCx é traduzido para HIP e compilado em tempo de execução com o hiprtc
     para a GPU presente;
   - uma thread por célula calcula a matriz do elemento e soma direto no array CSR local;
   - o lifting das condições de Dirichlet sai da mesma matriz do elemento;
   - a DOLFINx continua empacotando coeficientes; o PETSc recebe a CSR por
     `setValuesLocalCSR`.
2. **Conferência obrigatória** na 1ª iteração de cada cálculo: monta na GPU e na CPU, compara
   J e F (diferença relativa < 10⁻⁹) e os tempos. A GPU só fica se o resultado bater e se for
   mais rápida; senão o cálculo segue na CPU, com o motivo no log.
3. **Solve**: MUMPS na CPU. O solve na GPU fica desligado em paralelo (o solver híbrido
   travou com vários processos) e, em serial, passa por calibração automática.
4. Controles: `KFEM_GPU_ASM=auto|0|1` (padrão `auto`: liga com o backend HIP),
   `KFEM_GPU_SOLVE=1` e `KFEM_GPU_FORCE=1` (validação).
5. Limites atuais: só integrais de célula e dofmap com bloco 1. Formas com integrais de
   faceta ficam na CPU (detectado automaticamente).

## Consequências

- No caso CDI com a malha completa e a RX 580: **40,1 s com montagem na GPU contra 62,3 s só
  na CPU** (6 processos nos dois casos; 1,55× mais rápido), com resultados idênticos.
- A biblioteca HIP precisa do ROCm (hipcc para compilar a biblioteca; libamdhip64, hiprtc e
  comgr em tempo de execução). No AppImage, o runtime do ROCm do sistema é usado se existir;
  sem ele, tudo segue na CPU.
- A tradução depende do formato do código do FFCx 0.11. Uma troca de versão do FFCx exige
  rodar `tests/fem/test_gpu_assembly.py`.
- Uma variante CUDA da mesma ideia (NVRTC) é natural para placas NVIDIA, mas não foi feita
  nem testada.
