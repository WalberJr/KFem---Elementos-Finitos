# Reprodução de Xie et al. (2022) — estado (2026-11-24)

Feito: modelo completo no KFem (`modelo.py`: 5 espécies em ln c, equilíbrios S3–S7, CO2RR na
camada catalítica, Bruggeman, Henry + Séchenov = 32,1 mM, contornos e malha do artigo).
Melhorias no motor genérico feitas no caminho: passo de tempo adaptativo com rejeição, BDF2
de passo variável, `dt()` de expressões, recuperação de erro do PETSc, tolerância do Newton
configurável e **correção da tolerância absoluta do Newton** (declarava convergência falsa em
domínios pequenos).

Bloqueio (2 falhas, mesma causa): o solver não atravessa a transição ácido → alcalino perto
do eletrodo (≈ 17 mA/cm² em pH 2, quando a produção de OH⁻ iguala o suprimento difusivo de
H⁺). (1) Transiente em variáveis primitivas: passos minúsculos, ~5 min para 10 ms simulados.
(2) Continuação estacionária em ln c: Newton com 30–80 iterações por incremento minúsculo.

Alternativas propostas ao usuário (ver conversa): A) pseudo-transiente (passo que cresce com
a queda do resíduo, ln c); B) transiente do artigo em variáveis primitivas com "eps", em
segundo plano por horas; C) malha refinada na frente + continuação.

## Rota B escolhida pelo usuário (2026-11-24): transiente do artigo

Variáveis primitivas, eps = max(c, 1e-15 mol/m³) nas reações, 0–120 s. Caso pH 2, 750 mA/cm²
rodando em segundo plano (~/kfem-build/xie/transiente, log calculo.log): t = 1 s em 30 min.
Pausa por uso (90% da janela de 5 h). Ao retomar: ler o fim de calculo.log; se concluído,
extrair perfis (simular.py read_profiles adaptado a variáveis primitivas: field_<espécie>.xdmf)
e comparar com Fig. S2c/S3c (CO2 mín ~19 mM em ~15 µm; frente de pH ~78 µm; pH superfície ~12);
depois rodar os outros 29 casos em paralelo.

## 2026-11-24 17:10 — relatório
- 27 de 36 casos concluídos; faltam pH1 j200/250/500, pH2 j25/50 (rodando) e j750 em pH 0/1/3/4 (na fila da tarefa xargs).
- Geração do relatório: `python figuras.py ~/kfem-build/xie/relatorio` e depois
  `PYTHONPATH=<python-docx> python relatorio.py ~/kfem-build/xie/relatorio Relatorio_Xie2022_KFem.docx`
  (python-docx instalado só no scratchpad, com `pip --target`; node não existe nesta máquina).

## 2026-11-25 — correção da geometria 1D e reexecução da varredura

- Com a geometria montada na unidade do componente (necessário para o 2D), a interface
  CL|DL (x = 0,4 µm) passou a existir como contorno; antes ela se perdia na tolerância do OCC
  (faixa de 0,4 × 0,2 µm montada em metros) e a malha antiga da CL era degenerada.
  O contorno x = 100 µm passou de 6 para 7: `modelo.py` corrigido (Selection(1, [7])).
- 1D corrigido (pH 4, 500 mA/cm²): pH na superfície 12,756 (antes 12,702), CO2 mín 0,056 mM
  (antes 0,126); independe da malha (h = 0,1/0,05/0,025 µm, diferenças < 0,01 mM) e coincide
  com o 2D plano (máx |ΔCO2| = 0,02 mM). A diferença de 1,8 mM 2D×1D era da geometria antiga.
- Malha do 2D: h_mid 1 / 0,5 / 0,25 µm dão o mesmo resultado (0,001 mM): malha de produção ok.
- Os 36 casos 1D (varredura, diag, transiente pH 2/750) foram corrigidos (.kfem com contorno 7)
  e estão sendo recalculados; resultados antigos em ~/kfem-build/xie/antigo_geom/.
