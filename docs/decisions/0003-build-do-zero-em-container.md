# 0003 — Build do zero em container AlmaLinux 8

**Status:** Substituído pelo ADR 0011 (2026-11-18: o usuário decidiu não usar container)

**Contexto:** O usuário decidiu compilar toda a pilha do zero. Um AppImage só roda em
distribuições cuja glibc seja igual ou mais nova que a do sistema onde foi compilado.
DOLFINx 0.11 exige C++20 (GCC moderno).

**Decisão proposta:**
- Imagem base **AlmaLinux 8** (glibc 2.28, gratuita, suporte até 2029) com
  **gcc-toolset** recente para C++20. Isso permite rodar em Ubuntu 20.04+, Debian 11+,
  Fedora e derivados de RHEL 8+.
- Engine de container: **Podman rootless** (livre, sem daemon e sem precisar de sudo). Docker
  também serve, mas na máquina atual o Docker é snap e o usuário não está no grupo `docker`.
- Tudo instalado em um prefixo relocável `/opt/kfem`; PETSc em prefixos por variante
  (`/opt/kfem/petsc-{cpu,cuda,hip,opencl}`).
- Fontes baixadas por URL fixada em `build/versions.env`, conferidas por SHA-256.
- `ccache` e downloads em `/media/walber/CODES/kfem/` (disco FAT32 externo liberado pelo
  usuário); árvores de build, prefixos e armazenamento de containers no disco interno
  (~92 GB livres), com diretórios de build apagados após cada componente.

**Alternativa:** Ubuntu 22.04 (glibc 2.35) — mais simples, mas não roda em distros mais antigas.
