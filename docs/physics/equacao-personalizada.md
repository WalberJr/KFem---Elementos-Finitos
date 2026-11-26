# Equação personalizada (forma fraca) — fase M1 (ADR 0014)

O usuário escreve o **resíduo** em forma fraca; o KFem resolve `R(u; v) = 0` para toda
função-teste `v`, com Newton (SNES do PETSc) e MUMPS.

## Formulação

Para campos escalares `u₁…uₙ` em Lagrange P1 ou P2 (espaço misto quando n > 1):

R = Σ (equações das físicas) + Σ (termos de domínio adicionais)·dx(k) + Σ (termos de contorno)·ds(k)

- Dirichlet: `uᵢ = g(x, y, t)` nos contornos selecionados (interpolado a cada passo).
- Neumann/Robin: entram como termos de contorno escritos pelo usuário. Exemplo, fluxo
  prescrito `-k ∂u/∂n = q`: termo `q*test(u)`; convecção `h(u - u∞)`: termo
  `h*(u - uinf)*test(u)`.
- Graus de liberdade fora dos domínios selecionados ficam fixos em zero.

## Tempo

`dt(u)` = BDF1 no primeiro passo (`(u - uⁿ)/h`) e BDF2 de passo fixo depois
(`(1,5u - 2uⁿ + 0,5uⁿ⁻¹)/h`), com `substeps` passos (padrão 10) entre instantes de saída.
No passo estacionário `dt(u) = 0`.

## Gramática (analisador seguro, sem `eval`)

Campos, `test(u)`, `dt(u)`, `grad`, `div`, `inner`, `dot`, `curl`, `vec(a, b[, c])`,
`x`, `y`, `z`, `t`, `dx`, `dx(k)`, `ds`, `ds(k)`, funções matemáticas (`exp`, `log`, `sqrt`,
`sin`, `cos`, `tanh`, `min`, `max`…), parâmetros do modelo e unidades entre colchetes.

## Verificação (tests/fem/test_weakform.py, test_weakform_model.py)

| Caso | Resultado esperado | Obtido |
|---|---|---|
| Poisson, u = sin(πx)sin(πy), P1 | taxa L² ≈ 2 | ✔ |
| Poisson, P2 | taxa L² ≈ 3 | ✔ |
| −∇·((1+u²)∇u) = f, u linear (P1 exato) | erro < 10⁻¹⁰, Newton com ≥ 2 iterações | ✔ |
| ∂u/∂t − Δu = f, u = (1+x²+y²)(1+t), P2 | erro < 10⁻⁹ (BDF e P2 exatos) | ✔ |
| Sistema acoplado de 2 campos (biharmônico misto) | exato em P2 | ✔ |
| Modelo completo: −k ΔT = q no quadrado, T = 0 | máximo = 0,07367·q/k (±2 %) | ✔ |
| Expressões com código, sem medida, nomes inválidos | recusadas | ✔ |
