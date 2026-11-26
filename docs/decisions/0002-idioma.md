# 0002 — Interface em pt-BR preparada para tradução

**Status:** Aceito (usuário, 2026-11-17)

**Decisão:** Textos da interface em português do Brasil, sempre via `QCoreApplication.translate`
/ `self.tr()` (sistema de tradução do Qt, arquivos `.ts`/`.qm`), para permitir inglês depois
sem reescrever código. Código, nomes de variáveis e comentários técnicos em inglês;
documentação do usuário em pt-BR.

**Consequências:** Nenhuma string visível ao usuário fica fixa no código sem `tr()`.
