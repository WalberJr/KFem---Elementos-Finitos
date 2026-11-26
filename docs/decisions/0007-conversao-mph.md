# 0007 — Estratégia de leitura/conversão de `.mph`

**Status:** Aceito (usuário pediu leitura e conversão; estratégia em camadas)

**Decisão:** Três caminhos, em ordem de preferência, todos com finalidade de
interoperabilidade com arquivos do próprio usuário, sem descompilar software do COMSOL:
1. Com uma instalação COMSOL licenciada disponível: exportar via pacote livre `mph` (Python)
   ou modo batch — parâmetros, seleções, geometria, malha.
2. Leitor de `.mphtxt` (exportação textual de malha feita pelo próprio COMSOL).
3. Leitura direta do `.mph`: inspecionar a estrutura de um arquivo de exemplo e extrair o
   que for viável; documentar em `docs/mph-format/` o que é e o que não é suportado.

Saída: `.kfem` + relatório de itens não convertidos.

**Pendência:** precisa do arquivo `CDI_ionic_diode.mph` (não está nesta máquina; COMSOL
também não está instalado aqui).
