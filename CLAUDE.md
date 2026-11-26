# KFem — Simulador multifísico livre (FEniCSx) com interface própria, empacotado em AppImage

> **REGRA Nº 1 — UMA ETAPA POR VEZ.**
> Cada etapa abaixo é executada **separadamente**. Ao concluir uma etapa, o agente
> **para**, apresenta o relatório de conclusão (o que foi feito, como verificar, o que
> ficou pendente) e **aguarda autorização explícita do usuário** antes de iniciar a próxima.
> Nunca avance de etapa, nem adiante trabalho de etapas futuras, sem pedido do usuário.
> Se uma etapa revelar a necessidade de mudar uma decisão já registrada, pare e pergunte.
>
> **Autorização em vigor (usuário, 2026-11-18):** "Quero que implemente tudo." O agente
> executa as etapas **em sequência, sem esperar autorização entre elas**. Mesmo assim,
> continua escrevendo o relatório de cada etapa em `docs/stage-reports/` e para quando
> precisar de algo que só o usuário pode dar: decisões, dados (CSVs), comandos com `sudo`
> ou hardware.

---

## 1. Objetivo

Construir um aplicativo desktop Linux, distribuído como **AppImage** único, que:

1. Usa **FEniCSx (DOLFINx)** como motor de elementos finitos.
2. Oferece uma interface gráfica no **estilo de fluxo de trabalho** de suítes multifísicas
   comerciais (árvore do modelo → painel de configurações → janela gráfica → mensagens),
   **com identidade visual, nomes, ícones e textos próprios**, sem ferir direitos autorais
   ou marcas de terceiros (ver §7).
3. **Detecta automaticamente a placa de vídeo de qualquer máquina** (NVIDIA, AMD ou Intel)
   e **roda a simulação nela**, além de usá-la para renderização. Um único AppImage
   carrega vários backends de cálculo e escolhe o melhor em tempo de execução; se nenhuma
   GPU utilizável existir (ou o driver do sistema faltar), cai para CPU + MPI sem erro.
4. Tem tema visual **lilás + verde-escuro + preto**.
5. Na v1, resolve o **caso de referência CDI** (deionização capacitiva / diodo iônico) do
   usuário: Brinkman + distribuição secundária de corrente + transporte de espécies diluídas
   em meio poroso (convecção, migração, transferência de massa em meio poroso).
6. **Lê/converte arquivos `.mph`** para um formato aberto que o FEniCSx lê (ver Etapa 7).
7. Usa **somente ferramentas gratuitas** em todo o desenvolvimento e build.

## 2. Contexto

- Máquina de desenvolvimento: Ubuntu 24.04, x86_64, 12 threads, 31 GB RAM,
  ~92 GB livres em disco (atenção: compilar Qt + VTK + PETSc do zero consome muito disco —
  usar ccache e limpar diretórios de build intermediários).
- GPU da máquina: **AMD Radeon RX 580 (Polaris, gfx803)** — sem suporte oficial ROCm/HIP
  atual. Nesta máquina o cálculo na GPU deve usar o backend **OpenCL** (driver Mesa
  rusticl/radeonsi ou outro ICD OpenCL instalado no sistema). Em 2026-11-18 foi instalado o
  `mesa-opencl-icd` 25.2.8: a RX 580 aparece no OpenCL com `RUSTICL_ENABLE=radeonsi`, e a
  precisão dupla só com `RUSTICL_FEATURES=fp64` (experimental; validar contra a CPU).
  Docker está instalado via snap, mas o usuário não está no grupo `docker`. Os backends CUDA e HIP
  não podem ser testados aqui: exigem acesso a uma GPU NVIDIA e a uma AMD suportada pelo
  ROCm (ver Etapa 11).
- COMSOL **não** está instalado nesta máquina e não há arquivos `.mph` aqui. O arquivo de
  referência (`CDI_ionic_diode.mph`) precisa ser fornecido pelo usuário quando a Etapa 7
  (e a Etapa 0, para extrair parâmetros/equações) começar.
- Caso de referência visto na captura de tela do usuário (para orientação; confirmar com o
  arquivo real): componente 2D com 3 domínios — retângulo ~0–100 mm × 0–1,2 mm e retângulo
  ~−10–110 mm × 0,2–1,0 mm; espessura fora do plano `W`; grupos de parâmetros:
  Structure, Fitting, Internal, Operation, Material and Liquid, Fictitious Membrane,
  Default Model Inputs; físicas: Brinkman, Corrente Secundária, Transporte Diluído em Meio
  Poroso, um componente "Charging Mode (Veff)" e acoplamentos multifísicos.
  **Não inventar equações, parâmetros ou valores**: tudo deve vir do arquivo `.mph`,
  de exportações do usuário ou de perguntas diretas a ele.

## 3. Decisões já tomadas (com o usuário)

| Tema | Decisão |
|---|---|
| Uso da GPU | **Obrigatório no AppImage final:** detectar a GPU de qualquer máquina e rodar a simulação nela. Um só AppImage com variantes de backend: CUDA (NVIDIA), HIP (AMD com ROCm), OpenCL/ViennaCL (fallback universal: AMD antigas como a RX 580, Intel, NVIDIA sem CUDA) e CPU + MPI (último recurso). Renderização na GPU sempre que houver. |
| Escopo de física v1 | O caso CDI do usuário (3 físicas + acoplamentos), estacionário e transiente. |
| Arquivos `.mph` | Ler e converter para formato aberto lido pelo FEniCSx (XDMF/HDF5 + projeto JSON). |
| Build | **Compilar tudo do zero** (pilha numérica e gráfica), **nativo, sem container** (ADR 0011), com versões fixadas, em `~/kfem-sdk/`. |
| Ferramentas | Apenas gratuitas. |

| Licença | GPL-3.0-or-later (ADR 0001). |
| Idioma | Interface em pt-BR via sistema de tradução do Qt (ADR 0002). |
| Tolerância de validação | ≤ 2% em grandezas integrais, ≤ 5% em perfis (ADR 0008). |
| Commits | O agente **não** faz commits nem push; sugere a mensagem e o usuário faz (ADR 0010). |
| Paralelismo | MPI + OpenMP híbrido, mais GPU quando houver (ADR 0012). |
| Projeto / GUI | Formato `.kfem` (ADR 0006); solver em processo separado, que pode ser cancelado sem derrubar a interface (ADR 0009). |

Detalhes e decisões ainda "Propostas" (aguardando aprovação): `docs/decisions/`.
Versões fixadas: `build/versions.env`.

## 4. Tecnologias (todas livres)

| Camada | Tecnologia | Licença (verificar na Etapa 0) |
|---|---|---|
| FEM | DOLFINx, Basix, FFCx, UFL (FEniCSx) | LGPL-3 / MIT |
| Álgebra linear | PETSc (+ MUMPS, hypre), OpenBLAS, MPICH ou Open MPI | BSD-2 / várias livres |
| Cálculo em GPU | PETSc com backends CUDA (CUDA Toolkit, gratuito mas proprietário; só as bibliotecas redistribuíveis entram no AppImage), HIP (ROCm), ViennaCL/OpenCL + OpenCL ICD loader; Kokkos se a Etapa 0 indicar | NVIDIA EULA / MIT / Apache / BSD |
| I/O | HDF5, ADIOS2 (VTX), meshio, h5py | BSD / MIT |
| Geometria e malha | Gmsh (API Python, kernel OCC) | GPL-2+ |
| GUI | Qt 6 + PySide6/Shiboken6 | LGPL-3 |
| Visualização 3D | VTK (com Qt) + PyVista + pyvistaqt | BSD-3 / MIT |
| Gráficos 1D | Matplotlib (backend Qt) | PSF-like |
| Unidades | pint | BSD |
| Linguagem | Python 3 (compilado do zero) + C/C++ via pilha acima | — |
| Build | Docker/Podman, CMake, Ninja, ccache, appimagetool, linuxdeploy (opcional) | livres |
| Testes | pytest, pytest-qt, pytest-xdist; ruff; mypy | livres |

Versões exatas: escolher as **últimas estáveis compatíveis entre si** na Etapa 0 e fixá-las
em `build/versions.env` (com URL e SHA-256 de cada fonte). Nunca usar "latest" no build.

## 5. Estrutura do repositório (alvo)

```
KFem/
├── CLAUDE.md                 # este arquivo
├── README.md
├── LICENSE                   # definida na Etapa 0
├── THIRD_PARTY_NOTICES.md    # licenças de tudo que vai dentro do AppImage
├── docs/
│   ├── decisions/            # ADRs: uma decisão por arquivo (NNNN-titulo.md)
│   ├── physics/              # formulação forte e fraca de cada física (Etapa 0/6)
│   ├── mph-format/           # achados sobre o .mph (Etapa 7)
│   └── stage-reports/        # relatório de conclusão de cada etapa
├── build/
│   ├── versions.env          # versões + SHA-256 fixados
│   ├── env.sh                # ambiente do build nativo (prefixo ~/kfem-sdk)
│   └── recipes/              # um script por componente (petsc.sh, dolfinx.sh, qt.sh...)
├── src/kfem/
│   ├── app/                  # entrada, CLI (kfem, kfem --diagnose)
│   ├── hw/                   # detecção de GPU/CPU e escolha de backend
│   ├── model/                # modelo de dados (árvore), parâmetros, unidades, (de)serialização
│   ├── geometry/             # geometria e malha (Gmsh) → DOLFINx
│   ├── physics/              # brinkman, current_secondary, transport_diluted, couplings
│   ├── solvers/              # estudos estacionário/transiente, configuração PETSc
│   ├── io/                   # formato .kfem, XDMF/VTX, importadores (mph, mphtxt)
│   ├── results/              # pós-processamento, avaliações, exportações
│   └── gui/                  # janela, árvore, painéis, gráficos, tema, ícones próprios
├── tests/                    # unitários, MMS, GUI, regressão
├── samples/                  # casos de exemplo (o .mph do usuário fica fora do git)
└── packaging/
    ├── AppRun
    ├── kfem.desktop
    ├── kfem.appdata.xml
    └── icons/
```

## 6. Etapas do projeto (ordem de execução)

Cada etapa termina com: testes passando, relatório em `docs/stage-reports/NN-nome.md`,
e **parada para autorização do usuário**.

### Etapa 0 — Fundações e especificação
- `git init`, estrutura de pastas, `.gitignore` (incluindo `samples/*.mph` e builds), README.
- Pesquisar e fixar versões compatíveis em `build/versions.env`.
- Registrar decisões (ADRs) e resolver as pendências do §3 com o usuário.
- Escrever `docs/physics/`: equações fortes e fracas de cada física e dos acoplamentos,
  **a partir do `.mph`/informações do usuário** (listar lacunas como perguntas, não supor).
- **Verificação:** usuário revisa e aprova ADRs, versões e formulação física.

### Etapa 1 — Pilha numérica compilada do zero
- Build nativo (ADR 0011) em `~/kfem-sdk/`, com MPI + OpenMP (ADR 0012). Receitas para: Python, OpenBLAS, MPI, HDF5, PETSc (+MUMPS, hypre), pybind11/
  nanobind, Basix, UFL, FFCx, DOLFINx (C++ e Python), Gmsh, ADIOS2, meshio, pint.
- Prefixo de instalação único (ex.: `/opt/kfem`), relocável. Nesta etapa compila-se a
  variante **CPU**; as receitas já devem prever as variantes de GPU (Etapa 11), com PETSc
  em prefixos separados (`/opt/kfem/petsc-{cpu,cuda,hip,opencl}`) e DOLFINx/petsc4py
  ligados a cada uma.
- **Verificação:** demo de Poisson do DOLFINx roda em serial e com `mpirun -n 4`;
  erro L2 contra solução analítica cai na taxa teórica; `petsc4py`/`dolfinx` importam.

### Etapa 2 — Pilha gráfica compilada do zero
- Qt 6 (módulos mínimos necessários), Shiboken6/PySide6, VTK com módulo Qt e wrappers
  Python, PyVista, pyvistaqt, Matplotlib.
- **Verificação:** janela PySide6 com widget VTK renderizando uma malha DOLFINx;
  captura de tela off-screen salva e conferida; `vtk` reporta o renderer OpenGL.

### Etapa 3 — Detecção de hardware e GPU
- `kfem.hw`: enumera GPUs via `/sys/class/drm` (vendor/device IDs), `lspci` (fallback),
  presença de driver/bibliotecas do sistema (`libcuda.so`, `libamdhip64.so`/ROCm,
  ICDs OpenCL em `/etc/OpenCL/vendors`), `nvidia-smi`, `rocminfo`, `clinfo` quando houver,
  e renderer OpenGL do VTK.
- Decide o backend de **renderização** (hardware → fallback Mesa software) e o de
  **cálculo**, na ordem: CUDA → HIP → OpenCL → CPU. Um backend só é escolhido se:
  a variante existe no AppImage, o driver do sistema está presente e um teste rápido de
  sanidade (pequeno sistema linear resolvido e comparado com a CPU) passa. Falhou → tenta o
  próximo, registra o motivo no log, nunca aborta a simulação.
- Override: variável `KFEM_GPU=auto|cuda|hip|opencl|cpu` e opção nas preferências.
- `kfem --diagnose` imprime GPUs encontradas, drivers, backend escolhido e motivos.
- Nesta etapa a lógica é implementada e testada com simulação; a ligação real com as
  variantes de PETSc acontece na Etapa 11.
- **Verificação:** testes com sysfs/bibliotecas simulados (NVIDIA com e sem driver,
  AMD com e sem ROCm, AMD antiga, Intel, sem GPU); na RX 580 real → render = GPU,
  cálculo escolhido = OpenCL se houver ICD OpenCL, senão CPU, com o motivo no relatório.

### Etapa 4 — Núcleo do modelo (sem GUI)
- Árvore do modelo: definições globais (grupos de parâmetros), componentes, geometria,
  materiais, físicas, multifísica, malha, estudos, resultados.
- Parâmetros com expressões e unidades (avaliação segura, sem `eval` livre).
- Formato de projeto aberto `.kfem` (JSON versionado + malha XDMF/HDF5).
- **Verificação:** testes de ida-e-volta (salvar/abrir) e de avaliação de parâmetros.

### Etapa 5 — Geometria e malha
- Primitivas 2D/3D, booleanas, seleções (domínios/contornos) e controle de malha via Gmsh;
  conversão para DOLFINx preservando marcadores.
- **Verificação:** geometria de referência (3 domínios) gerada; áreas e marcadores
  conferidos; malha importada no DOLFINx sem elementos degenerados.

### Etapa 6 — Físicas do caso CDI
- Brinkman (escoamento livre/poroso), distribuição secundária de corrente,
  transporte diluído com convecção + migração em meio poroso, componente de carga
  (equivalente ao "Charging Mode") e acoplamentos; estacionário e transiente;
  estabilização (ex.: SUPG) onde necessário.
- **Verificação:** soluções manufaturadas (MMS) para cada física com taxas de convergência
  esperadas; caso acoplado converge; conservação de massa/carga dentro da tolerância.

### Etapa 7 — Leitura e conversão de `.mph`
- Abordagens, em ordem de preferência (todas para interoperabilidade, sem descompilar
  software do COMSOL):
  a) **Via instalação COMSOL licenciada do usuário** (quando existir), com o pacote livre
     `mph` (Python) ou o modo batch, exportando parâmetros, seleções, geometria e malha;
  b) **Leitor de `.mphtxt`** (exportação textual de malha do próprio COMSOL);
  c) **Leitura direta do `.mph`** (arquivo compactado): inspecionar a estrutura de um
     arquivo de exemplo e extrair o que for viável (parâmetros, malha), documentando em
     `docs/mph-format/` o que é suportado e o que não é.
- Saída: projeto `.kfem` + malha XDMF/HDF5 + relatório de itens não convertidos.
- **Verificação:** converter `CDI_ionic_diode.mph` (fornecido pelo usuário) e conferir
  parâmetros, domínios e malha contra o que o usuário vê no COMSOL.

### Etapa 8 — Interface gráfica (casca + tema)
- Layout: barra de menus, faixa de ferramentas por abas, árvore do modelo (esquerda),
  painel de configurações (centro), janela gráfica 3D (direita), painel inferior com
  Mensagens / Progresso / Log / Tabela. Painéis acopláveis.
- Tema QSS próprio com tokens de cor (lilás, verde-escuro, preto + neutros), contraste
  mínimo WCAG AA, ícones próprios ou de conjuntos livres (ex.: Lucide/Tabler) recoloridos.
- **Verificação:** pytest-qt; capturas de tela off-screen revisadas pelo usuário.

### Etapa 9 — Integração GUI ↔ núcleo
- Editar o modelo pela GUI, gerar malha, executar estudo em **processo separado**
  (GUI nunca trava; suporte a MPI), barra de progresso, cancelar, log.
- Resultados: superfície, isolinhas, setas, gráficos 1D, avaliações integrais;
  exportação PNG/CSV/VTK/XDMF.
- **Verificação:** fluxo completo do caso CDI feito só pela GUI; cancelar e reabrir funciona.

### Etapa 10 — Validação contra o COMSOL
- Comparar com resultados de referência exportados pelo usuário (CSV/TXT do COMSOL):
  grandezas integrais e perfis.
- **Verificação:** diferenças dentro da tolerância acordada na Etapa 0; relatório com gráficos.

### Etapa 11 — Cálculo em GPU em qualquer máquina
- Compilar as variantes de PETSc (+ petsc4py e ligação com DOLFINx):
  **CUDA** (NVIDIA; arquiteturas de GPU definidas na Etapa 0 para cobrir placas antigas e
  novas), **HIP** (AMD com ROCm), **OpenCL/ViennaCL** (fallback universal) e **CPU**.
- Adaptar os solvers da Etapa 6 para que vetores, matrizes e precondicionadores rodem no
  backend escolhido (tipos `cuda`/`hip`/`viennacl` do PETSc e precondicionadores
  compatíveis com GPU). Onde uma parte não roda na GPU (ex.: montagem do DOLFINx), deixar
  documentado que ela fica na CPU.
- Política "auto": usar a GPU detectada; registrar no log e na GUI qual backend rodou;
  fallback automático para o próximo backend se o solver falhar na GPU.
- **Verificação:**
  - na RX 580 local: caso CDI roda no backend OpenCL e o resultado bate com a CPU dentro
    da tolerância;
  - CUDA e HIP: rodar o mesmo teste em máquinas com essas GPUs (a combinar com o usuário).
    Enquanto não houver acesso, o relatório deve marcar essas variantes como
    **compiladas, mas não testadas em hardware real**;
  - medir e relatar o tempo GPU × CPU no caso CDI e num caso maior (o ganho depende do
    tamanho do problema; não prometer aceleração sem medir).

### Etapa 12 — Empacotamento AppImage
- AppDir a partir do prefixo `/opt/kfem`, com todas as variantes de backend; `AppRun`
  configura o ambiente (Python, Qt, MPI, plugins), roda a detecção de GPU, aponta
  `LD_LIBRARY_PATH`/`PETSC_DIR` para a variante escolhida e inicia a GUI.
  **Não empacotar** drivers de vídeo nem `libGL`/`libvulkan`/`libdrm`/`libcuda`/ICDs OpenCL
  do fabricante (usar os do sistema). `.desktop`, ícone, AppStream,
  `THIRD_PARTY_NOTICES.md` e textos de licença dentro do AppImage. `appimagetool`.
- Medir e relatar o tamanho final (as bibliotecas CUDA/ROCm aumentam muito o AppImage) e
  propor ao usuário cortes se ficar grande demais.
- **Verificação:** AppImage roda em sistemas limpos (Ubuntu 24.04, Debian 13,
  Fedora) caindo corretamente para CPU, e na máquina real usando a GPU;
  `kfem --diagnose` correto; caso CDI resolvido.

### Etapa 13 — Documentação e entrega
- Manual do usuário (pt-BR), incluindo quais drivers instalar para cada fabricante de GPU,
  guia de build, notas de licença, checksums, changelog.
- **Verificação:** um build limpo seguindo apenas o guia reproduz o AppImage.

## 7. Regras de direitos autorais e marcas (obrigatórias)

- Proibido usar nome, logotipo, ícones, telas, sons, textos de documentação ou ajuda do
  COMSOL (ou de qualquer software proprietário). Não copiar capturas de tela como assets.
- Inspirar-se apenas no **paradigma de fluxo de trabalho** (árvore → configurações →
  gráficos), que é genérico; nomes de menus, rótulos, ícones e textos devem ser próprios.
- Termos físicos genéricos ("Brinkman", "transporte de espécies diluídas", "corrente
  secundária") são permitidos; não reproduzir frases ou descrições do manual do COMSOL.
- Não descompilar, decompor ou usar código do COMSOL. A leitura do `.mph` é só para
  interoperabilidade com arquivos do próprio usuário.
- Toda dependência embutida no AppImage deve ter licença compatível e constar em
  `THIRD_PARTY_NOTICES.md`.

## 8. Regras de trabalho

- **Uma etapa por vez; parar e pedir autorização ao fim de cada etapa (Regra Nº 1).**
- Não inventar informações (equações, parâmetros, valores, versões, comportamento do
  `.mph`). Na dúvida, perguntar ao usuário ou verificar na fonte.
- Nada de ferramentas pagas ou serviços que exijam assinatura.
- Builds nativos (sem container, ADR 0011), reproduzíveis, com fontes baixadas por URL + SHA-256.
  Arquivos baixados ficam em diretórios próprios e não são executados sem inspeção.
- Comandos longos (compilações) rodam em segundo plano com log em arquivo; ler apenas o
  final/erros do log para economizar contexto.
- **Não fazer commits nem push** (ADR 0010). Ao fim de cada etapa, sugerir no relatório a
  mensagem de commit para o usuário.
- Código Python: tipado, `ruff` + `mypy` limpos, testes junto do código novo.
- A GUI nunca executa o solver na thread principal.
- Toda decisão relevante vira um ADR em `docs/decisions/`.
- Se uma etapa falhar duas vezes pelo mesmo motivo, parar, resumir o problema e propor
  alternativas ao usuário (incluindo trocar de modelo/esforço, ver §10).

## 8.1 Limite de uso do plano (obrigatório)

- Antes de cada passo longo (compilação, pesquisa extensa, bateria de testes) e
  periodicamente durante a etapa, consultar o uso do plano (`get_usage`).
- Se **qualquer** janela de limite (5 horas ou semanal) chegar a **98%**: parar o trabalho
  num ponto seguro, deixar processos longos terminarem ou registrar como retomá-los,
  anotar o estado em `docs/stage-reports/` e avisar o usuário com o horário de reset.
  Só retomar depois que o limite renovar e o usuário mandar continuar.
- Nunca ativar uso extra/pago para contornar o limite.

## 8.2 Armazenamento temporário

- Disco interno (`/home`): ~92 GB livres. Disco externo `/media/walber/CODES` (~160 GB
  livres) liberado pelo usuário para dados temporários, sempre dentro de
  `/media/walber/CODES/kfem/` (`downloads/`, `ccache/`, `logs/`, `archives/`).
- **Atenção: CODES é FAT32 (vfat)** — sem links simbólicos, sem permissões/bit de execução
  Unix, arquivos de no máximo 4 GB, sem diferenciar maiúsculas/minúsculas. Por isso ali
  ficam apenas: tarballs de fontes baixadas, cache do ccache, logs e arquivos `.tar.zst`
  de artefatos (divididos em partes < 4 GB). **Árvores de build, prefixos de instalação e o
  armazenamento do Podman/Docker ficam no disco interno.**
- Nunca mexer em nada fora de `/media/walber/CODES/kfem/` nesse disco.

## 9. Paleta de cores (ponto de partida; ajustar na Etapa 8 com o usuário)

| Token | Uso | Cor sugerida |
|---|---|---|
| `--bg` | fundo principal | `#0B0B0D` (preto) |
| `--surface` | painéis | `#16161A` |
| `--primary` | destaque, seleção, foco | `#B79CDB` (lilás) |
| `--primary-soft` | hover, fundos de seleção | `#3A2F4D` |
| `--accent` | ações, sucesso, barras de ferramenta | `#1F5B3A` (verde-escuro) |
| `--accent-strong` | botões primários | `#2E7D4F` |
| `--text` | texto | `#ECE8F2` |
| `--text-muted` | texto secundário | `#A59FB0` |
| `--border` | divisórias | `#2A2A31` |

Janela gráfica: fundo em gradiente preto → lilás muito escuro; geometria em lilás;
seleção em verde. Garantir contraste AA para todo texto.

## 10. Modelos e esforço recomendados por etapa (Claude Code)

Selecionar o modelo no seletor do app antes de iniciar cada etapa.

| Etapa | Modelo | Esforço | Motivo |
|---|---|---|---|
| 0 Fundações (estrutura, versões, ADRs) | Opus 5.5 | high | Decisões que afetam todo o projeto. |
| 0 Formulação física (docs/physics) | Opus 5.5 | xhigh | Raciocínio matemático difícil; erro aqui contamina tudo. |
| 1 Pilha numérica | Sonnet 5.5 | medium | Scripts de build e espera de compilação; tarefa mecânica. |
| 2 Pilha gráfica | Sonnet 5.5 | medium | Idem; Qt/VTK são verbosos, não complexos. |
| 3 Detecção de GPU | Sonnet 5.5 | high | Código pequeno, mas com muitos casos de borda. |
| 4 Núcleo do modelo | Opus 5.5 | high | Arquitetura central, difícil de mudar depois. |
| 5 Geometria e malha | Sonnet 5.5 | high | API do Gmsh bem documentada. |
| 6 Físicas CDI | Opus 5.5 | xhigh | Acoplamento não linear, estabilização, convergência. |
| 7 Conversor `.mph` | Opus 5.5 | high | Investigação de formato e mapeamento semântico. |
| 8 GUI e tema | Sonnet 5.5 | high | Muito código de interface, padrões conhecidos. |
| 9 Integração GUI ↔ núcleo | Opus 5.5 | high | Concorrência, processos, MPI, estado. |
| 10 Validação | Opus 5.5 | xhigh | Diagnóstico de discrepâncias numéricas. |
| 11 Cálculo em GPU | Opus 5.5 | xhigh | Vários backends, compatibilidade de solvers e precondicionadores, depuração numérica. |
| 12 AppImage | Opus 5.5 | high | Várias variantes de bibliotecas no mesmo pacote; erros de ligação são prováveis. |
| 13 Documentação | Sonnet 5.5 | medium | Redação técnica. |
| Tarefas mecânicas (varrer logs, coletar licenças, renomear) | Haiku 5.5 | low | Subagente barato. |

Quando trocar/subir:
- **Subir esforço** (medium → high → xhigh) após 2 tentativas falhas no mesmo erro.
- **Sonnet → Opus 5.5 high**: erros persistentes de link/ABI/RPATH no build ou no AppImage,
  ou travamentos/condições de corrida na GUI.
- **Opus 5.5 xhigh → max**: solver acoplado que não converge após ajustes razoáveis,
  discrepância inexplicada na validação, ou revisão final da formulação física.
- **Nunca usar o Fable** (decisão do usuário, 2026-11-18). O teto é Opus 5.5 com esforço max.
- **Descer** para Sonnet/Haiku quando a tarefa virar repetitiva (gerar ícones/QSS em série,
  testes parametrizados, documentação) para economizar tokens.

## 11. Critérios de conclusão do projeto

- [ ] AppImage único, executável sem instalação, em Ubuntu 24.04+, Fedora 40+ e Debian 13+
      (glibc ≥ 2.39; ADR 0011).
- [ ] Em qualquer máquina, a GPU é detectada automaticamente e a simulação roda nela
      (CUDA, HIP ou OpenCL conforme o hardware e o driver), com resultado igual ao da CPU
      dentro da tolerância; sem GPU utilizável, cai para CPU sem erro.
- [ ] Render acelerado na GPU; backend usado sempre visível no log e na interface.
- [ ] Caso CDI criado do zero pela GUI **e** importado do `.mph`, resolvido nos modos
      estacionário e transiente.
- [ ] Resultados dentro da tolerância acordada em relação ao COMSOL.
- [ ] Interface própria, tema lilás/verde-escuro/preto, sem elementos de terceiros protegidos.
- [ ] Testes (unitários, MMS, GUI) passando; `ruff`/`mypy` limpos.
- [ ] Licenças e avisos de terceiros completos; build reproduzível a partir do guia.
- [ ] Somente ferramentas gratuitas usadas.
