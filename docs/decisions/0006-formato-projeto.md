# 0006 — Formato de projeto `.kfem`

**Status:** Aceito (usuário, 2026-11-18)

**Decisão proposta:** `.kfem` é um arquivo ZIP contendo:
- `model.json` — árvore do modelo (parâmetros, geometria, materiais, físicas, malha,
  estudos, resultados), com `format_version` e validação por esquema;
- `mesh/*.xdmf` + `*.h5` — malhas com marcadores de domínio/contorno (lidas pelo DOLFINx);
- `results/` — soluções (XDMF/HDF5 ou VTX/ADIOS2), opcional;
- `thumbnail.png`.

**Consequências:** Formato aberto, legível por FEniCSx sem o KFem; migrações de versão
explícitas.
