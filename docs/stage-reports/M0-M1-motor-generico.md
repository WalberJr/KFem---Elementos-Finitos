# Fases M0 e M1 — motor genérico de formas fracas e equação personalizada (2026-11-24)

## Feito

- `src/kfem/solvers/weakform.py`:
  - `WeakProblem`: núcleo sem dependência do modelo. Campos escalares P1/P2 (espaço misto),
    resíduos em texto pelo analisador seguro, Dirichlet dependente de x/y/t, termos de
    contorno e de domínio, valores iniciais, domínios inativos fixos, Newton (SNES) + MUMPS,
    estacionário e transiente (BDF1 → BDF2), saída P1 para XDMF.
  - `problem_from_model`/`solve_model`: traduzem os nós da árvore.
- Catálogo: "Equação personalizada (forma fraca)" com os filhos Valor imposto (Dirichlet),
  Termo de contorno (Neumann/Robin), Termo de domínio adicional e Valores iniciais. A
  interface monta árvore e painéis sozinha a partir do catálogo.
- Estudo (`study.py`): passos com físicas genéricas vão para o motor novo; o caminho do CDI
  ficou intacto. Misturar os dois no mesmo passo é recusado com mensagem clara (por ora).
- Formulação e verificação: `docs/physics/equacao-personalizada.md`.

## Verificação

- `tests/fem/test_weakform.py`: 6 testes MMS (taxas P1 = 2 e P2 = 3, não linear exato,
  transiente exato, 2 campos acoplados, segurança).
- `tests/fem/test_weakform_model.py`: modelo completo (geometria → Gmsh → estudo → XDMF),
  estacionário (máximo analítico ±2 %) e transiente.
- Regressão completa: 31 testes de interface/hardware e 37 de FEM/modelo/arquivos (CDI igual).
- ruff e mypy limpos.

## Limites atuais

- Campos escalares apenas (vetoriais vêm com a mecânica dos sólidos e o escoamento).
- Passo de tempo fixo (`substeps` entre saídas); o controle adaptativo do CDI será levado ao
  motor depois.
- Ainda sem montagem em GPU no motor genérico (a infraestrutura da Etapa 11 serve; falta
  ligar).
- N1 (GPU NVIDIA) aguarda o CUDA Toolkit, que não pôde ser instalado (conflito resolvível:
  `sudo apt remove librocthrust-dev` e depois `sudo apt install nvidia-cuda-toolkit`).

## Próximo

E1 — eletroquímica: distribuição de corrente primária, secundária e terciária sobre o motor.

Sugestão de commit (o usuário faz):
`M0/M1: motor genérico de formas fracas e nó Equação personalizada, com MMS`
