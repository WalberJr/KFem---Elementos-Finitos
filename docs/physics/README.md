# Formulação física — caso CDI (diodo iônico)

**Status:** formulação final da Etapa 0, escrita em 2026-11-18 a partir do arquivo
`CDI_ionic_diode.mph` (ver `docs/mph-format/CDI_ionic_diode-extracao.md`).
**Aguarda revisão do usuário.**

- Itens marcados **[A CONFIRMAR]** dependem de padrões internos do software de origem que
  não estão gravados no arquivo. Eles serão fixados pela validação (Etapa 10).
- Unidades SI em todo o código. A geometria do arquivo está em mm e é convertida para m.

## 0. Domínios, incógnitas e números de referência

**Domínios**
- Ω₁ = canal (tubos de entrada e saída + espaçador).
- Ω₂ = eletrodo inferior.
- Ω₃ = eletrodo superior.
- Ω = Ω₁ ∪ Ω₂ ∪ Ω₃, em 2D, com espessura fora do plano W.

**Contornos**
- Γ_in = contorno 1 (x = −Lp).
- Γ_out = 14 (x = L+Lp).
- Γ_b = 5 (y = 0, face externa de Ω₂).
- Γ_t = 9 (y = 2te+ts, face externa de Ω₃).

**Incógnitas**

| Símbolo | Significado | Onde |
|---|---|---|
| **u**, p | velocidade superficial (Darcy) e pressão | Ω, estacionário |
| φ_l | potencial do eletrólito | Ω |
| φ_s | potencial da fase sólida | Ω₂ ∪ Ω₃ |
| c_Na, c_Cl | concentrações | Ω |
| V | tensão de célula (incógnita global, escalar) | — |

**Valores derivados dos parâmetros** (para ter noção de escala)
- C = 28,41 F.
- vol = 8,0·10⁻⁷ m³.
- Capacitância volumétrica C_v = 2C/vol = 7,10·10⁷ F/m³.
- v0 = 4,375·10⁻⁴ m/s.
- σ_l(c0) = 0,243 S/m.
- Péclet de malha ≈ 66 com h = 0,181 mm, o que exige estabilização (§5).

## 1. Escoamento — Stokes–Brinkman, estacionário (passo 1 do estudo)

Forma forte:
- **Em Ω₁:** −∇·[−p𝐈 + μ(∇**u** + ∇**u**ᵀ)] = 0, com ∇·**u** = 0.
- **Em Ω₂ e Ω₃:** −∇·[−p𝐈 + (μ/ε_p)(∇**u** + ∇**u**ᵀ)] + (μ/κ)**u** = 0, com ∇·**u** = 0.

Propriedades:
- ε_p = pM = 0,4.
- κ = 8,9·10⁻¹² m².
- μ = viscosidade da água em T **[A CONFIRMAR T; ver §6]**.
- Não há termo inercial (opção Stokes–Brinkman). A gravidade, com densidade constante, só
  muda a pressão hidrostática e não altera **u**.

Contorno:
- Em Γ_in: **u** = −v0·**n** (velocidade normal de entrada).
- Em Γ_out: [−p𝐈 + μ(∇**u** + ∇**u**ᵀ)]**n** = 0 (pressão 0).
- Demais contornos: **u** = 0.

Forma fraca (Taylor–Hood P2/P1): achar (**u**, p) tal que, para todo (**v**, q),

  Σ_k ⟨(μ/ε_k)(∇**u**+∇**u**ᵀ), ∇**v**⟩_Ωk + ⟨(μ/κ)**u**, **v**⟩_Ω₂∪Ω₃
  − ⟨p, ∇·**v**⟩ − ⟨q, ∇·**u**⟩ = 0,

com ε₁ = 1, ε₂ = ε₃ = ε_p, e **u** imposto em Γ_in e nas paredes.

## 2. Distribuição secundária de corrente (passo 2, transiente)

Densidades de corrente: **i**_l = −σ_l,eff ∇φ_l e **i**_s = −σ_s,eff ∇φ_s.

- **Em Ω₁:** ∇·**i**_l = 0, com σ_l,eff = σ_l.
- **Em Ω₂ e Ω₃:**
  - ∇·**i**_l = i_v;
  - ∇·**i**_s = −i_v;
  - i_v = C_v ∂(φ_s − φ_l)/∂t (corrente volumétrica da dupla camada; não há reação
    faradaica ativa).

Condutividades:
- σ_l = cond(c) = F²/(R·295 K)·Σ_i z_i² D_i c_i. Depende das concentrações, o que faz o
  acoplamento ser não linear.
- σ_l,eff = ε_l^1,5 σ_l, com ε_l = pM = 0,4 **[A CONFIRMAR expoente]**.
- σ_s,eff = ε_s^1,5 σ_s, com ε_s = 1−ptot = 0,3 e σ_s = sigma_ACC **[A CONFIRMAR]**.

Contorno:
- φ_s = +V/2 em Γ_t e φ_s = −V/2 em Γ_b.
- Demais contornos e interfaces: **n**·**i**_s = 0.
- Em ∂Ω: **n**·**i**_l = 0.
- φ_l e **i**_l·**n** são contínuos nas interfaces eletrodo/canal.

Iniciais: φ_l = φ_s = 0.

Observação: φ_l não tem condição de Dirichlet. Ele fica determinado pelo termo ∂φ_l/∂t da
dupla camada, junto com a condição inicial.

Forma fraca (P1), para ψ_l em Ω e ψ_s em Ω₂∪Ω₃:

  ⟨σ_l,eff ∇φ_l, ∇ψ_l⟩_Ω − ⟨C_v ∂_t(φ_s−φ_l), ψ_l⟩_Ω₂∪Ω₃ = 0
  ⟨σ_s,eff ∇φ_s, ∇ψ_s⟩_Ω₂∪Ω₃ + ⟨C_v ∂_t(φ_s−φ_l), ψ_s⟩_Ω₂∪Ω₃ = 0

## 3. Transporte de Na⁺ e Cl⁻ em meio poroso (passo 2, transiente)

Para i ∈ {Na, Cl}, com mobilidade de Nernst–Einstein u_m,i = D_i/(RT):

- **Em Ω₁:**
  ∂c_i/∂t + **u**·∇c_i + ∇·**J**_i = 0, com **J**_i = −D_i∇c_i − z_i u_m,i F c_i ∇φ_l.
- **Em Ω₂ e Ω₃:**
  ε_p ∂c_i/∂t + **u**·∇c_i + ∇·**J**_i = R_i, com **J**_i = −D_e,i∇c_i − z_i u_me,i F c_i ∇φ_l,
  - D_e,i = ε_p^1,5 D_i (Bruggeman) e u_me,i = D_e,i/(RT) **[A CONFIRMAR]**;
  - T da migração **[A CONFIRMAR; ver §6]**.

A convecção usa a forma não conservativa **u**·∇c, válida porque ∇·**u** = 0. A velocidade
**u** vem do passo 1, congelada.

Fontes (acoplamento com o eletrodo poroso, n = 1), R_i = −ν_i i_v/(nF):

| Domínio | ν_Na | ν_Cl | Resultado |
|---|---|---|---|
| Ω₃ | 1 | 0 | R_Na = −i_v/F, R_Cl = 0 |
| Ω₂ | 0 | −1 | R_Na = 0, R_Cl = +i_v/F |

**[A CONFIRMAR sinal da convenção com um CSV de referência]**

Contorno:
- Em Γ_in: c_i = c0.
- Em Γ_out: −**n**·D∇c_i = 0 (saída).
- **Em Γ_t: c_Cl = 0; em Γ_b: c_Na = 0.** São as condições de "membrana" do diodo,
  confirmadas pelo usuário.
- Demais contornos: **n**·**J**_i = 0.

Iniciais: c_i = c0.

Forma fraca (P1 + SUPG), para ĉ que se anula onde há Dirichlet:

  ⟨ε ∂_t c_i, ĉ⟩ + ⟨**u**·∇c_i, ĉ⟩ + ⟨D_e∇c_i + z_i u_me F c_i ∇φ_l, ∇ĉ⟩ − ⟨R_i, ĉ⟩
  + Σ_K ⟨τ_K (resíduo forte), **u**·∇ĉ⟩_K = 0

## 4. Circuito externo ("modo de carga", tensão constante)

Equação global algébrica:

  V − (V_ext0 − Rc·I) = 0,  com  I = W ∫_Ω₃ i_v dA

O par (V, I) fecha o sistema: V entra como Dirichlet de φ_s e depende da própria solução,
por meio de I.

Sistema de equações diferenciais e algébricas (DAE): V(0) é obtido por inicialização
consistente.

Nota: V_ext0 é aplicado como degrau em t = 0. A rampa `step1` existe no arquivo, mas não é
usada pelo nó ativo.

O modo de corrente constante (CC) existe no arquivo, desativado. Será suportado como
alternativa, com as equações gravadas no arquivo.

## 5. Estratégia numérica (Etapa 6)

**Ordem de solução**
- Passo 1: Stokes–Brinkman linear, com solução direta (MUMPS) ou com bloco precondicionado.
- Passo 2: sistema monolítico (φ_l, φ_s, c_Na, c_Cl, V), resolvido por Newton (SNES) a
  cada passo de tempo.

**Integração no tempo**
- BDF de ordem variável (1–2) com passo adaptativo.
- rtol = 10⁻³ (o mesmo do arquivo).
- Saídas nos instantes do estudo: 0:5:50, 55:15:2000, 2030:30:7200 s.

**Estabilização**
- SUPG no transporte, porque Pe_h ≫ 1.
- Opção de malha mais fina nas faces dos eletrodos, como no arquivo.

**Incógnita global V (opções avaliadas na Etapa 6, ainda sem decisão)**
- (a) espaço "real" de 1 grau de liberdade (pacote livre `scifem`, MIT);
- (b) linha e coluna extras montadas à mão no sistema PETSc.

**Malha:** gerada no Gmsh a partir das configurações do arquivo:
- hmax 0,181 mm e 0,0727 mm nos contornos 5, 6, 8 e 9;
- camadas-limite.

Os valores de mesh são de partida: a malha exata do software de origem não está gravada.

**Paralelismo:** MPI + OpenMP (ADR 0012), com GPU quando houver (ADR 0005).

**Verificação (Etapa 6):** MMS separado para cada física, seguido do caso acoplado, com
conservação de carga: W·∫i_v nos dois eletrodos = I e −I.

## 6. Pontos a confirmar (não bloqueiam as Etapas 1–5)

1. ~~**Temperatura.**~~ Resolvido na Etapa 7: o nó de cargas das espécies do arquivo grava
   `minput_temperature = 293.15[K]`. Esse valor vale para a mobilidade (Nernst–Einstein) e
   para a água. `cond` continua com 295 K fixo no texto da expressão, como no original.
2. **Expoentes de Bruggeman** (1,5) para σ_l, σ_s e D nos eletrodos.
3. **Sinal da fonte** R_i.
4. **CSVs de referência** (corrente × t e concentração efluente × t) para a Etapa 10.

Os itens 1–3 podem ser fixados comparando com os CSVs.
