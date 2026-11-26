# Etapa 13 — Documentação e entrega (2026-11-23)

## Feito

| Documento | Conteúdo |
|---|---|
| `docs/usuario/manual.md` | Manual do usuário em pt-BR: instalação e requisitos (glibc, gcc, FUSE), conferência do SHA-256, a janela e os atalhos, o exemplo CDI passo a passo, todos os nós do catálogo, resultados e formatos, importação de `.mph`, GPU (o que roda nela, a conferência automática, números medidos), **drivers por fabricante** (AMD/ROCm com pacotes e grupo `render`, NVIDIA, Intel, sem GPU), `kfem-gpu-setup`, variáveis de ambiente, linha de comando, problemas comuns e limites da v0.1 |
| `docs/build.md` | Guia de build do zero: pacotes do sistema (lista conferida contra os instalados na máquina de build), ROCm opcional, diretórios e variáveis, `fetch.sh`, `build-all.sh` com a tabela das receitas, variantes OpenCL/HIP, testes (em processos separados), geração e conferência do AppImage, limites de reprodutibilidade |
| `CHANGELOG.md` | Versão 0.1.0.dev0: simulação, GPU, interface, arquivos, empacotamento, problemas conhecidos e o SHA-256 do AppImage |
| `docs/licencas.md` | Como o projeto trata licenças: GPL do KFem, componentes permissivos/LGPL/CeCILL-C/GPL, fontes correspondentes, o que não vai no AppImage |
| `README.md` | Atualizado: como usar e índice da documentação |

Conferências feitas: as opções citadas existem no `kfem --help` (`--solve`, `-n`,
`--workdir`, `--import-mph`, `-o`, `--version`, `--diagnose`, `--watch`); os nomes dos
campos batem com os arquivos de resultado (`cNa`, `cCl`, `phil`, `phis`, `u`, `p`); o
comando de extração do `kfem-gpu-setup` de dentro do AppImage funciona; os nós do manual
vêm de `kfem.model.catalog`; nenhum link interno quebrado.

## Verificação pedida pelo CLAUDE.md — não executada

"Um build limpo seguindo apenas o guia reproduz o AppImage" não foi feito nesta etapa:

- leva várias horas e precisa das fontes baixadas, que estão no disco `CODES`, não montado
  hoje;
- o ambiente do agente não alcança o `github.com` (filtro de rede), de onde vem parte das
  fontes.

Feito no lugar: a parte final do guia (§7–8) foi seguida hoje e gerou o AppImage de
307 MB, conferido em ambiente limpo (ver relatório da Etapa 12). Para a verificação
completa: montar o `CODES` (ou copiar os downloads), apontar `KFEM_SDK` e `KFEM_BUILD` para
diretórios vazios e seguir `docs/build.md` do §3 ao §8. O mais simples é o usuário rodar no
próprio terminal, onde o GitHub funciona.

## Pendente no projeto (fora desta etapa)

- Etapa 10 (validação contra o COMSOL): aguarda os CSVs de referência do usuário.
- Relatórios das Etapas 1, 2, 5, 6, 8 e 9: não foram escritos na época. Precisam ser
  reconstituídos a partir dos logs e do código, sem inventar dados.
- Aprovação dos ADRs em estado "Proposto" (entre eles o 0013).
- Variante CUDA e teste em Debian 13/Fedora.

Sugestão de commit (o usuário faz):
`Etapa 13: manual do usuário, guia de build, changelog, notas de licença e README`
