# Etapa 0 — Fundações e especificação · relatório

**Data:** 2026-11-17/18 · **Status:** concluída em 2026-11-18. A formulação física aguarda a revisão do usuário, e o usuário autorizou iniciar a Etapa 1.

## Feito

- Repositório git criado (`main`), sem commits (ADR 0010).
- Estrutura de pastas do CLAUDE.md §5 criada (`src/kfem/*`, `tests/`, `build/recipes/`,
  `packaging/`, `samples/`, `docs/*`).
- `LICENSE` (texto oficial GPL-3.0), `README.md`, `.gitignore` (exclui `samples/*.mph`),
  `THIRD_PARTY_NOTICES.md` (estrutura).
- `build/versions.env`: versões estáveis compatíveis entre si, conferidas nas fontes
  oficiais em 2026-11-17. Destaques: DOLFINx/Basix/FFCx 0.11.0 + UFL 2026.1.0 (faixa
  exigida pelo DOLFINx 0.11), PETSc 3.26.1, Python 3.14.10, Qt/PySide6 6.12.0 (LTS),
  VTK 9.7.2, Gmsh 4.15.2, MPICH 5.0.2. Confirmado que o PETSc 3.26.1 ainda tem o backend
  ViennaCL (OpenCL).
- 10 ADRs em `docs/decisions/` (4 decididos pelo usuário, 1 aceito a partir do pedido de
  GPU, 5 propostos aguardando aprovação).
- `CLAUDE.md` atualizado com as decisões, a regra de commits e o estado do OpenCL/Docker.
- `docs/physics/README.md`: formas padrão (fortes e fracas) de Brinkman, corrente
  secundária e transporte diluído em meio poroso, acoplamentos e **9 lacunas**.

## Como verificar

- `git status` → arquivos novos, nenhum commit.
- Ler `docs/decisions/README.md` e aprovar ou ajustar os ADRs "Propostos":
  0003 (AlmaLinux 8 + Podman), 0004 (MPICH), 0006 (formato `.kfem`), 0009 (arquitetura GUI).
- Conferir `build/versions.env`.

## Pendente para fechar a Etapa 0

1. ~~Arquivo `.mph`~~: recebido em 2026-11-18 e extraído
   (`docs/mph-format/CDI_ionic_diode-extracao.md`). Restam 5 confirmações (§7 da extração).
2. ~~Aprovação dos ADRs~~: 0004, 0006 e 0009 aceitos; 0003 substituído pelo 0011 (build
   nativo, sem container); novo 0012 (MPI + OpenMP). Pendente: decidir a compatibilidade
   do AppImage (glibc 2.39, ver ADR 0011).
3. ~~Formulação final~~: escrita em `docs/physics/README.md` (Opus 5.5) a partir do `.mph`. Falta a revisão do usuário; 4 pontos a confirmar (§6), que não bloqueiam as Etapas 1–5.
4. SHA-256 das fontes: serão preenchidos na Etapa 1, ao baixar cada pacote.

## Achados importantes

- OpenCL na RX 580 (2026-11-18): o usuário corrigiu as fontes do apt e instalou
  `mesa-opencl-icd` 25.2.8 + `clinfo`. Resultado: com `RUSTICL_ENABLE=radeonsi` a placa
  aparece como OpenCL 3.0 (32 CUs, 8 GiB); fp64 desligado por padrão e disponível com
  `RUSTICL_FEATURES=fp64` (experimental — validar numericamente contra a CPU nas Etapas 3
  e 11). Registrado no ADR 0005.
- Pasta temporária criada em `/media/walber/CODES/kfem/` (disco FAT32: só downloads,
  ccache, logs e arquivos compactados; builds ficam no disco interno).
- Docker é snap e o usuário não está no grupo `docker` → proposta de Podman rootless.
- Disco livre ~92 GB: suficiente com limpeza entre componentes, mas apertado para manter
  builds de Qt + VTK + 4 variantes de PETSc ao mesmo tempo.

## Mensagem de commit sugerida

```
Etapa 0: estrutura do repositório, versões fixadas, ADRs e rascunho da física
```
