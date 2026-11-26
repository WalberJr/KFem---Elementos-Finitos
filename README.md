# KFem

Simulador multifísico livre baseado em **FEniCSx (DOLFINx)**, com interface gráfica própria
(tema lilás, verde-escuro e preto), distribuído como **AppImage** para Linux. Detecta a
placa de vídeo e calcula nela quando compensa (montagem de elementos finitos em GPU via HIP),
com volta automática para a CPU.

Versão 0.1 (pré-lançamento): caso de deionização capacitiva (CDI) — escoamento de Brinkman,
corrente secundária e transporte de espécies diluídas em meio poroso, estacionário e
transiente.

## Usar

```bash
chmod +x KFem-x86_64.AppImage && ./KFem-x86_64.AppImage
```

Requer Ubuntu 24.04+, Debian 13+ ou Fedora 40+ e o `gcc` instalado. Para a placa de vídeo,
rode o `kfem-gpu-setup` (ver o manual).

## Documentação

- **Manual do usuário** — [PDF](docs/usuario/KFem-Manual.pdf) · [texto](docs/usuario/manual.md): instalação,
  interface, GPU e drivers, linha de comando
- **Tutorial** — [PDF](docs/usuario/KFem-Tutorial.pdf) · [texto](docs/usuario/tutorial.md): a primeira simulação
  de CDI, passo a passo
- [Guia de build](docs/build.md) — da fonte ao AppImage
- [Registro de mudanças](CHANGELOG.md)
- [Notas de licença](docs/licencas.md) e [avisos de terceiros](THIRD_PARTY_NOTICES.md)
- Decisões de projeto: [docs/decisions](docs/decisions); formulação física:
  [docs/physics](docs/physics); andamento: [docs/stage-reports](docs/stage-reports)
- Versões fixadas da pilha: [build/versions.env](build/versions.env)

KFem não é afiliado a nenhum fornecedor de software comercial de simulação.

Licença: [GPL-3.0-or-later](LICENSE).
