# Extração do `CDI_ionic_diode.mph` (Etapa 0, 2026-11-18)

Fonte: arquivo do usuário, salvo no COMSOL 6.4 (build 293). Ele fica em
`samples/CDI_ionic_diode.mph`, fora do git. A extração foi feita lendo o `dmodel.xml`
contido no arquivo, que é um ZIP: a árvore atual do modelo mais o histórico de construção.
Os scripts de extração serão reescritos como código do `kfem.io.mph` na Etapa 7.

**O que o arquivo contém**
- `dmodel.xml`: a árvore completa do modelo, com parâmetros, físicas, seleções, materiais,
  estudo, malha e resultados. É texto legível.
- `geometry*.mphbin`: a geometria, em formato binário.
- A malha (`mesh2.mphbin`, com 135 B) e as soluções (`solution*.mphbin`, com cerca de 4 kB)
  estão **vazias**: o modelo foi salvo sem malha e sem solução. A malha precisa ser
  regerada a partir das configurações listadas abaixo, e a validação (Etapa 10) depende de
  CSVs exportados pelo usuário.
- Ponto em aberto: o histórico de construção contém valores antigos (por exemplo,
  `te=0.65 mm`), mas o que vale é a árvore atual. Tudo o que está abaixo vem da árvore
  atual; o histórico só foi usado para separar o que o usuário configurou do que é padrão.

**Codificação das seleções**
- Exemplos: `entities='4,2,3'` (domínios) e `'-14,-1,9'` (contornos).
- Os primeiros números são um cabeçalho; os números seguintes são as entidades, contadas
  a partir de 1.
- A numeração foi conferida reconstruindo a geometria (ver abaixo).

## 1. Parâmetros (valores atuais)

| Grupo | Nome | Expressão | Descrição no arquivo |
|---|---|---|---|
| Structure | L | 100 [mm] | |
| Structure | W | 20 [mm] | espessura fora do plano |
| Structure | te | 0.4 [mm] | espessura do eletrodo |
| Structure | ts | 0.8 [mm] | espessura do espaçador (canal) |
| Structure | Lp | L/10 | comprimento dos tubos de entrada e saída |
| Fitting | C | 20.01 [F/g]*mass | Capacitance |
| Fitting | Rc | 57.4 [ohm] | Circuit Resistance |
| Fitting | V0 | 0.29 [V] | Adsorption zero-intercept |
| Internal | Cdl | 2*C/vol | |
| Internal | molar_cond | 2*D/R_const/295[K]*F_const^2 | |
| Internal | vol | te*W*L | |
| Internal | tSmooth | 10 [s] | |
| Internal | a | 1e6 [1/m] | Dummy |
| Internal | lam | 1-V0/Vext_0 | |
| Internal | v0 | volFlow/W/ts | |
| Internal | pM | ptot-pm | |
| Operation | volFlow | 0.42e-3 [L/min] | |
| Operation | tMax | 7200 [s] | |
| Operation | tSwitch | 7500 [s] | |
| Operation | c0 | 20 [mM] | |
| Operation | tPer | 2*tSwitch | |
| Operation | Vext_0 | 1 [V] | |
| Operation | batchVol | 20e-3 [L] | opcional |
| Operation | iCC_0 | C*Vext_0/tSwitch | opcional |
| Operation | V_ext0 | 1.2 [V] | |
| Material and Liquid | sigma_ACC | 106 [S/m] | |
| Material and Liquid | zK, zCl, zNa | 1, −1, 1 | |
| Material and Liquid | D | 1.9e-9 [m²/s] | KCl diffusion free |
| Material and Liquid | DNa, DCl | 1.2e-9, 2.0e-9 [m²/s] | |
| Material and Liquid | mass | 1.42 [g] | |
| Material and Liquid | Mw | 74.55 [g/mol] | |
| Material and Liquid | ptot, pm | 0.7, 0.3 | |
| Material and Liquid | R_L | 5*Rc | opcional (fuga) |
| (sem grupo) | currentiter | 0 | |
| (sem grupo) | cond | F²/(R·295 K)·(cNa·zNa²·DNa + cCl·zCl²·DCl) | aparece também como variável |

Constantes `F_const` e `R_const`: valores CODATA (definir no KFem com os mesmos valores).

**Funções**
- `step1` (voltage_ramp): degrau suave de 0 para `Vext_0`, centrado em `tSmooth/2`, com
  largura de suavização `tSmooth`. Está ativa, mas o nó CV atual não a usa.
- `step2`: desativada.

**Variável de componente:** `cond` (a mesma expressão da tabela), usada como condutividade
do eletrólito.

**Sonda de domínio `current`:** integral de `cd.ivtot*W` no domínio 3 (eletrodo superior),
em A. Ela entra na equação global (§4.4).

## 2. Geometria (2D, unidade mm)

| Retângulo | Rótulo | Posição | Tamanho |
|---|---|---|---|
| r1 | electrode_bottom | (0, 0) | L × te |
| r2 | spacer | (0, te) | L × ts |
| r3 | electrode_top | (0, te+ts) | L × te |
| r4 | pipe_in | (−Lp, te) | Lp × ts |
| r5 | pipe_out | (L, te) | Lp × ts |

- A geometria é a união dos 5 retângulos, seguida de "ignorar arestas" nas 2 arestas
  internas entre os tubos e o espaçador.
- O resultado tem **3 domínios e 14 contornos**.

**Domínios**
1. Canal: tubo de entrada + espaçador + tubo de saída.
2. Eletrodo inferior.
3. Eletrodo superior.

**Contornos usados**

| Contorno | Lugar | Uso |
|---|---|---|
| 1 | x = −Lp | entrada |
| 14 | x = L+Lp | saída |
| 5 | y = 0 | face externa do eletrodo inferior |
| 9 | y = 2te+ts | face externa do eletrodo superior |
| 6 e 8 | interfaces eletrodo/canal | refino de malha |

## 3. Materiais

**mat1 "ACC electrode"**, em todos os domínios; no domínio 1 a água o substitui.
- Porosidade: `pM`.
- Permeabilidade: 8.9e-12 m² (isotrópica).
- Condutividade elétrica: `sigma_ACC`.
- Condutividade do eletrólito: `cond`.

**mat2 "H2O (water) [liquid]"**, no domínio 1.
- Densidade e viscosidade são funções de T, tiradas da biblioteca de materiais e salvas
  dentro do `.mph` (`rho_liquid_2(T)`, `eta_liquid_1(T)`).
- Condutividade do eletrólito: `cond`.
- T vem das entradas padrão do modelo; o valor ainda **não foi confirmado** (ver lacunas).

## 4. Físicas e condições

### 4.1 Brinkman (`br`) — escoamento
- Opção **Stokes–Brinkman**: sem termo inercial, incompressível.
- Domínio 1: propriedades de fluido livre, com a água.
- Domínios 2 e 3: meio poroso, com porosidade e permeabilidade de mat1.
- Contornos:
  - entrada (1): velocidade normal `v0`;
  - saída (14): pressão (padrão 0);
  - demais contornos: parede.

### 4.2 Distribuição secundária de corrente (`cd`)
- Espessura fora do plano: `d = W`.
- **Eletrólito** em todos os domínios: σ_l da mat1/mat2 = `cond(cNa, cCl)`.
- **Eletrodo poroso** nos domínios 2 e 3:
  - ε_l = `pM`;
  - ε_s = `1−ptot`;
  - σ_s = `sigma_ACC`;
  - condutividade efetiva: correção padrão do COMSOL, valor **a confirmar**.
  - Subnó **capacitância de dupla camada**: a_v = `a`, C_dl = `Cdl/a`, ou seja,
    capacitância volumétrica `Cdl` = 2C/vol.
  - Subnó **reação de fuga**: desativado.
- **Potencial elétrico:**
  - φ_s = +V/2 no contorno 9;
  - φ_s = −V/2 no contorno 5.
- Demais contornos: isolamento.

### 4.3 Transporte diluído em meio poroso (`tds`), espécies cNa e cCl
- Mecanismos: convecção (pelo acoplamento rfd1) e **migração** no potencial `phil`.
- Domínio 1, fluido livre:
  - D = DNa, DCl;
  - z = zNa, zCl.
- Domínios 2 e 3, meio poroso:
  - Fluido com D_F = DNa, DCl;
  - difusividade efetiva pelo **modelo de Bruggeman**;
  - porosidade de mat1 (`pM`).
- **Acoplamento com o eletrodo poroso** nos domínios 2 e 3, com corrente `cd.ivdl` e n = 1:
  - domínio 3: coeficiente ν_Na = 1, ν_Cl = 0;
  - domínio 2: ν_Na = 0, ν_Cl = −1;
  - a variante "fuga" está desativada.
- Condições:
  - inicial c = c0 nas duas espécies;
  - entrada (1): c = c0;
  - saída (14): fluxo de saída;
  - **cCl = 0 no contorno 9 e cNa = 0 no contorno 5** — são as condições do "diodo";
  - demais contornos: fluxo nulo, sem convecção.

### 4.4 "Charging Mode" (`Veff`) — equação global
- Nó ativo **CV**: incógnita V [V], com a equação `V − (V_ext0 − Rc·current) = 0`.
  Condição inicial V = 0.
- Nó **CC** (corrente constante): desativado.

### 4.5 Acoplamento `rfd1` (escoamento ↔ espécies)
- Leva a velocidade de `br` para o termo convectivo de `tds`.
- Usa a forma convectiva não conservativa.

## 5. Estudo
- **Passo 1, estacionário:** só `br` (rfd1 desligado).
- **Passo 2, dependente do tempo:** `cd` + `tds` + `Veff`, com rfd1 ligado e a velocidade
  do passo 1 congelada.
  - Saídas em t = range(0,5,50), range(55,15,2000), range(2030,30,tMax); tMax = 7200 s.
  - Tolerância relativa 0,001.
- Varreduras paramétricas desativadas, guardadas para referência:
  - c0 ∈ {20, 40} mM;
  - te ∈ {0.2, 0.4} mm;
  - V_ext0 ∈ {0.8, 1.2} V;
  - volFlow ∈ {5e-3, 10e-3} L/min.

**Saídas de interesse (sondas)**
- concentração efluente de Na e de Cl no contorno 14;
- corrente total `current`.

## 6. Malha (configurações; a malha não está salva)
- **Tamanho global:** hmax 0,181, hmin 0,00831, hgrad 1,25, curvatura 0,6.
- **Tamanho nos contornos 5, 6, 8 e 9:** hmax 0,0727, hmin 0,00208, hgrad 1,13.
- Refino de cantos.
- Triangular livre.
- Camadas-limite nos contornos internos e externos (número de camadas: padrão, a
  conferir).

## 7. Lacunas que ainda dependem do usuário ou de confirmação
1. Temperatura usada nas propriedades da água: as entradas padrão do modelo não guardam
   valor explícito, o que sugere o padrão de 293,15 K. Já a condutividade usa 295 K.
   Confirmar.
2. Correção de Bruggeman: confirmar se os expoentes padrão (ε^1,5) valem para σ_l, σ_s e D
   nos eletrodos.
3. Sinal da fonte de espécies no eletrodo poroso: convenção R_i = −ν_i·i_v/(nF). Confirmar
   com um resultado de referência (CSV).
4. A captura de tela citava um grupo "Fictitious Membrane", que **não existe** no arquivo.
   **Confirmado pelo usuário (2026-11-18):** o papel de membrana está nas condições
   cCl = 0 (contorno 9) e cNa = 0 (contorno 5).
5. CSVs de referência do COMSOL (corrente × t, concentração efluente × t), para a Etapa 10.
