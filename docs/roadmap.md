# Roteiro do KFem depois da v1 (ADR 0014)

Objetivo: transformar o KFem numa plataforma multifísica geral sobre o FEniCSx, módulo a
módulo, com física primeiro e 3D depois.

Ordem (usuário, 2026-11-23): M0 → N1 (NVIDIA) → M1 → **eletroquímica completa (E1–E5)** → M2 → M3 → M4 → M5 → G1.
Aplicações de eletroquímica escolhidas: CDI/dessalinização, baterias, corrosão/deposição e
eletroanálise (todas).

| Fase | Entrega | Critério de aceite | Situação |
|---|---|---|---|
| M0 | Motor genérico de formas fracas (estacionário/transiente, Newton, BDF, Dirichlet/Neumann/Robin por seleção, GPU) | o caso CDI continua igual; MMS de Poisson e calor transiente na taxa teórica | **feito (2026-11-24)** |
| N1 | **GPU NVIDIA**: reconhecimento (modelo, compute capability, driver) e instalador shell (`kfem-gpu-setup`: driver, CUDA Toolkit, PETSc CUDA para a arquitetura da placa) + oferta automática na 1ª execução (pkexec). Sem CUDA nesta máquina (decisão do usuário, 2026-11-24) | testes com placas NVIDIA simuladas (com/sem driver, antiga); **não testado em hardware real** | **feito (2026-11-24)** |
| M1 | **Equação personalizada (forma fraca)** com analisador seguro | MMS de Poisson, reação-difusão não linear e um caso transiente | **feito (2026-11-24)** |
| E1 | **Eletroquímica — distribuição de corrente**: primária, secundária e terciária; Butler–Volmer completo, Tafel, cinética dependente de concentração, várias reações por eletrodo, potencial de equilíbrio | MMS + casos analíticos (Wagner, eletrodo rotatório) | a fazer |
| E2 | **Eletroquímica — transporte**: Nernst–Planck com eletroneutralidade, Nernst–Planck–Poisson (dupla camada resolvida), eletrólitos concentrados; eletrodos porosos e capacitância de dupla camada (aprofunda o CDI/dessalinização) | MMS + caso CDI validado (Etapa 10) | a fazer |
| E3 | **Baterias**: modelo P2D de Newman (íon-lítio), carga/descarga, capacidade | benchmark publicado (ex.: curvas de descarga da literatura) | a fazer |
| E4 | **Corrosão e eletrodeposição**: corrosão galvânica, deposição com fronteira móvel | casos da literatura | a fazer |
| E5 | **Eletroanálise**: voltametria cíclica, cronoamperometria, impedância (EIS) | soluções analíticas (Randles–Ševčík, Cottrell) | a fazer |
| M2 | **Transferência de calor** (condução, convecção, fontes, contorno convectivo/radiativo) | MMS + benchmark da literatura | a fazer |
| M3 | **Mecânica dos sólidos** (elasticidade linear; depois termomecânica) | MMS + viga/placa com solução analítica | a fazer |
| M4 | **Escoamento laminar** (Navier–Stokes, Taylor–Hood) | MMS + cavidade com tampa / cilindro (benchmark DFG) | a fazer |
| M5 | **Eletromagnetismo** (eletrostática/correntes, magnetostática, Maxwell harmônico com Nédélec) | MMS + casos analíticos | a fazer |
| G1 | 3D: geometria por primitivas 3D, importação STEP/IGES, visualização 3D | um caso de cada módulo em 3D | a fazer |
| Depois | acústica, reações químicas, turbulência, não linear/contato, autovalores, otimização, malha adaptativa | — | — |

Cada fase gera um relatório em `docs/stage-reports/` (prefixo `M`/`G`), a formulação em
`docs/physics/` e uma seção no manual.
