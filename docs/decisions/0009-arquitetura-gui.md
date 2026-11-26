# 0009 — PySide6 + VTK, solver em processo separado

**Status:** Aceito (usuário, 2026-11-18). O usuário reforçou: o cálculo pode ser encerrado pela interface e uma falha ou cancelamento do solver nunca derruba a interface.

**Decisão proposta:**
- GUI em PySide6 (Qt 6, LGPL); visualização 3D com VTK + PyVista/pyvistaqt; gráficos 1D com
  Matplotlib (backend QtAgg).
- O solver roda em **processo separado** (`mpiexec -n N python -m kfem.solvers.run ...`)
  iniciado por `QProcess`; comunicação por arquivos de projeto + mensagens JSON em
  stdout (progresso, log, erros). A GUI nunca bloqueia e pode cancelar.
- A detecção de GPU (`kfem.hw`) escolhe o backend antes de iniciar o processo do solver.
- Layout: árvore do modelo | configurações | janela gráfica; painel inferior com
  Mensagens / Progresso / Log / Tabela; nomes, ícones e textos próprios (ver CLAUDE.md §7).
