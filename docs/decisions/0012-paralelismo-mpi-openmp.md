# 0012 — Paralelismo híbrido MPI + OpenMP (+ GPU quando houver)

**Status:** Aceito (usuário, 2026-11-18).

**Decisão:**
- **MPI** (MPICH, ADR 0004) é o nível principal. O DOLFINx particiona a malha, monta as
  matrizes e o PETSc resolve o sistema distribuído. O processo do solver é iniciado com
  `mpiexec -n N` (ADR 0009).
- **OpenMP** é o segundo nível, dentro de cada processo MPI, onde as bibliotecas suportam:
  - OpenBLAS compilado com `USE_OPENMP=1`;
  - hypre com OpenMP;
  - MUMPS com OpenMP (`--with-openmp` no PETSc);
  - Gmsh com OpenMP para gerar a malha.
- A montagem do DOLFINx não usa OpenMP: o paralelismo dela é só por MPI.
- A interface escolhe N processos × T threads, com o padrão `N × T = núcleos físicos`, e
  define `OMP_NUM_THREADS=T`. O padrão é T = 1; o usuário pode ajustar nas preferências.
- **GPU** (ADR 0005): quando há uma GPU utilizável, os vetores e matrizes do PETSc vão
  para ela, com um processo MPI por GPU por padrão.

**Consequência:** o ganho do OpenMP fica concentrado nas etapas do solver (fatoração e
precondicionador). Os números de desempenho serão medidos, sem promessa antecipada.
