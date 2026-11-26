# 0014 — KFem como plataforma multifísica geral (pós-v1)

**Status:** Aceito (usuário, 2026-11-23). Amplia o escopo do CLAUDE.md §1 (que era só o caso
CDI na v1).

## Contexto

O usuário pediu que o KFem faça "tudo o que o COMSOL faz, usando o FEniCSx". O FEniCSx
resolve praticamente qualquer EDP na forma fraca; o que falta no KFem é, para cada física,
a formulação, os nós da árvore, as condições de contorno, os testes e a validação. O COMSOL
tem dezenas de módulos construídos ao longo de décadas: igualar tudo é um trabalho de anos,
feito módulo a módulo.

## Decisão

1. **Física primeiro, 3D depois** (escolha do usuário). Cada física nasce em 2D sobre a base
   já testada; o 3D com importação de CAD (STEP/IGES via Gmsh/OCC) vem em seguida,
   reaproveitando as formulações.
2. **Motor genérico de formas fracas.** Um núcleo comum monta e resolve qualquer conjunto de
   equações escritas em UFL (estacionário e transiente, Newton, BDF, condições de Dirichlet,
   Neumann e Robin por seleção, montagem em GPU quando houver). Cada módulo de física passa a
   ser um **gerador de forma fraca** sobre esse motor, e não um solver próprio.
3. **Prioridades** (todas escolhidas pelo usuário), nesta ordem:
   1. **Equação personalizada (forma fraca):** o usuário escreve a EDP; a expressão é
      interpretada por um analisador seguro (sem `eval`).
   2. **Eletroquímica completa** (usuário, 2026-11-23: logo após o núcleo): distribuição de
      corrente primária/secundária/terciária, cinética de eletrodo completa,
      Nernst–Planck(–Poisson), eletrodos porosos e dupla camada, e as aplicações CDI/
      dessalinização, baterias (P2D), corrosão/eletrodeposição e eletroanálise (CV, EIS).
   3. **Transferência de calor:** condução, convecção, fontes, contorno convectivo e
      radiativo, transiente.
   4. **Mecânica dos sólidos:** elasticidade linear, depois tensões térmicas
      (acoplamento termomecânico).
   5. **Escoamento laminar e eletromagnetismo:** Navier–Stokes incompressível, eletrostática
      e correntes, magnetostática, Maxwell no domínio da frequência (elementos de Nédélec).
   6. Depois: acústica, reações químicas, turbulência, mecânica não linear e contato,
      autovalores e domínio da frequência gerais, otimização, malha adaptativa e
      pós-processamento avançado.
4. **Critérios de aceite por módulo** (mesmo padrão do CDI): formulação forte e fraca em
   `docs/physics/`, soluções manufaturadas (MMS) com a taxa de convergência esperada, nós e
   painéis na interface, um caso de referência publicado (benchmark da literatura) e uma
   seção no manual. Não inventar equações nem valores: tudo vem da literatura citada ou do
   usuário.
5. O caso CDI continua como está e segue sendo o caso de validação principal (Etapa 10,
   aguardando os CSVs do usuário).

## Consequências

- O CLAUDE.md §1 e §11 descrevem só a v1; este ADR registra a ampliação. As etapas novas
  seguem a mesma regra de relatório por etapa em `docs/stage-reports/`.
- O motor genérico exige refatorar a forma como o estudo chama as físicas (hoje há solvers
  dedicados ao CDI). O caso CDI precisa continuar passando nos testes durante a transição.
- O tamanho do AppImage cresce pouco (o código é Python; a pilha numérica já está lá).
