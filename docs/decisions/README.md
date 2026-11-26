# Registro de decisões (ADRs)

Uma decisão por arquivo, `NNNN-titulo.md`, com: Status, Contexto, Decisão, Consequências.
Mudar uma decisão aceita exige um novo ADR que a substitua (e autorização do usuário).

| ADR | Título | Status |
|---|---|---|
| [0001](0001-licenca.md) | Licença GPL-3.0-or-later | Aceito |
| [0002](0002-idioma.md) | Interface em pt-BR preparada para tradução | Aceito |
| [0003](0003-build-do-zero-em-container.md) | Build do zero em container AlmaLinux 8 | Substituído (0011) |
| [0004](0004-mpi.md) | MPICH como implementação MPI | Aceito |
| [0005](0005-backends-gpu.md) | Backends de cálculo em GPU e seleção em tempo de execução | Aceito |
| [0006](0006-formato-projeto.md) | Formato de projeto `.kfem` | Aceito |
| [0007](0007-conversao-mph.md) | Estratégia de leitura/conversão de `.mph` | Aceito |
| [0008](0008-tolerancia-validacao.md) | Tolerâncias de validação contra o COMSOL | Aceito |
| [0009](0009-arquitetura-gui.md) | PySide6 + VTK, solver em processo separado | Aceito |
| [0010](0010-commits.md) | O agente não faz commits | Aceito |
| [0011](0011-build-nativo-sem-container.md) | Build do zero nativo, sem container | Aceito |
| [0012](0012-paralelismo-mpi-openmp.md) | Paralelismo híbrido MPI + OpenMP (+ GPU) | Aceito |
| [0013](0013-montagem-em-gpu.md) | Montagem de elementos finitos na GPU (HIP) e solve na CPU | Proposto |
| [0014](0014-plataforma-multifisica-geral.md) | KFem como plataforma multifísica geral (pós-v1) | Aceito |

"Aceito" = decidido pelo usuário. "Proposto" = recomendação técnica aguardando aprovação.
