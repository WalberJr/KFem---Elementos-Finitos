# Plataforma multifísica — estado para retomar (2026-11-23)

Pausa por limite de uso (5 h em 72%, regra de pausar em 80%). Feito: ADR 0014 e
`docs/roadmap.md`. Próximo passo ao retomar: **M0/M1** — estudar `kfem.physics.expr_ufl`
(analisador seguro), `kfem.solvers.study` (despacho das físicas) e o catálogo de nós; então
criar o motor genérico de formas fracas e o nó "Equação personalizada", com MMS.
Nada foi alterado no código nesta pausa; o AppImage atual (SHA-256 no CHANGELOG) segue válido.

## Pedido do usuário para o fim da implementação (2026-11-23)

Ao concluir os módulos novos (M0–M5): criar um **manual completo à parte, em PDF**, cobrindo
toda a plataforma (CDI + equação personalizada + **eletroquímica completa** + calor +
sólidos + escoamento + eletromagnetismo), com telas reais. Gerar com `docs/tools/gerar_pdfs.py` (e capturas novas
com `docs/tools/capturas.py`) e deixar o PDF na **pasta principal do projeto**
(`/home/walber/KFem/`), além de `docs/usuario/`.

Ordem atualizada (2026-11-23): M0 → N1 (GPU NVIDIA: PETSc CUDA + montagem via NVRTC; precisa do CUDA Toolkit instalado pelo usuário) → M1 → eletroquímica E1–E5 → M2 → M3 → M4 → M5 → G1.

## Pedido (2026-11-23): instalação automática da GPU

Na 1ª execução do KFem, identificar a placa automaticamente e oferecer a instalação do que
falta (runtime ROCm/CUDA) com um clique: diálogo na interface → `pkexec kfem-gpu-setup
--install --yes` (a senha é pedida pelo próprio sistema; o KFem nunca a vê). O script deve
resolver sozinho o conflito `librocthrust-dev` × `libthrust-dev` (mesmos cabeçalhos
/usr/include/thrust) e nunca rodar `apt autoremove`. Fazer junto com N1.
