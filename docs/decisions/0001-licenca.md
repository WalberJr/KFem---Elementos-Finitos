# 0001 — Licença GPL-3.0-or-later

**Status:** Aceito (usuário, 2026-11-17)

**Contexto:** O AppImage embute o Gmsh (GPL-2.0-or-later). DOLFINx/Basix são LGPL-3.0,
PySide6/Qt são LGPL-3.0, PETSc/VTK/PyVista são BSD/MIT. Distribuir o conjunto exige
licença compatível com GPL.

**Decisão:** O código do KFem é licenciado sob GPL-3.0-or-later. Arquivo `LICENSE` com o
texto oficial da GPL-3.0. Cabeçalho SPDX `GPL-3.0-or-later` em cada arquivo-fonte.

**Consequências:** Quem receber o AppImage tem direito ao código-fonte. Todas as
dependências embutidas e suas licenças entram em `THIRD_PARTY_NOTICES.md`. Bibliotecas
CUDA (EULA NVIDIA) entram apenas como redistribuíveis permitidos, como bibliotecas de
sistema separadas; isso será revisado na Etapa 11 antes de empacotar.
