"""Catálogo dos tipos de nó do KFem (nomes e rótulos próprios, em pt-BR).

Cada `NodeSpec` diz:
- onde o nó entra na árvore;
- que tipo de seleção ele usa;
- quais propriedades aceita, com valores padrão.

A interface monta os painéis de configuração a partir daqui; o conversor de `.mph` e o
solver usam os mesmos `kind`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DOMAIN, BOUNDARY, GLOBAL, NONE = "domínio", "contorno", "global", "nenhuma"


@dataclass(frozen=True)
class PropSpec:
    name: str
    label: str
    default: Any = ""
    kind: str = "expr"  # expr | choice | bool | list | text | int | table
    unit: str = ""
    choices: tuple[str, ...] = ()
    help: str = ""


@dataclass(frozen=True)
class NodeSpec:
    kind: str
    label: str
    parent: str  # kind do pai (ou seção)
    selection: str = NONE
    props: tuple[PropSpec, ...] = ()
    tag_prefix: str = "n"
    default_child: bool = False  # criado junto com o pai e não removível
    icon: str = "node"

    def defaults(self) -> dict[str, Any]:
        return {p.name: p.default for p in self.props}


P = PropSpec
_SPECS: list[NodeSpec] = [
    # ---------------------------------------------------------------- definições globais
    NodeSpec(
        "func.step",
        "Degrau suave",
        "section.functions",
        props=(
            P("location", "Posição", "0", unit="—"),
            P("from", "Valor inicial", "0"),
            P("to", "Valor final", "1"),
            P("smooth", "Largura de suavização", "0"),
        ),
        tag_prefix="step",
        icon="function",
    ),
    NodeSpec(
        "func.analytic",
        "Função analítica",
        "section.functions",
        props=(
            P("args", "Argumentos", "x", kind="text"),
            P("expr", "Expressão", "x"),
        ),
        tag_prefix="an",
        icon="function",
    ),
    # ---------------------------------------------------------------- definições do componente
    NodeSpec(
        "def.variables",
        "Variáveis",
        "section.definitions",
        selection=GLOBAL,
        props=(P("vars", "Variáveis (nome, expressão)", [], kind="table"),),
        tag_prefix="var",
        icon="variables",
    ),
    NodeSpec(
        "def.probe_integral",
        "Sonda: integral em domínio",
        "section.definitions",
        selection=DOMAIN,
        props=(
            P("name", "Nome da variável", "probe", kind="text"),
            P("expr", "Expressão", "1"),
            P("unit", "Unidade", "", kind="text"),
        ),
        tag_prefix="dom",
        icon="probe",
    ),
    NodeSpec(
        "def.probe_boundary_avg",
        "Sonda: média em contorno",
        "section.definitions",
        selection=BOUNDARY,
        props=(
            P("name", "Nome da variável", "probe", kind="text"),
            P("expr", "Expressão", "1"),
            P("unit", "Unidade", "", kind="text"),
        ),
        tag_prefix="bnd",
        icon="probe",
    ),
    # ---------------------------------------------------------------- geometria
    NodeSpec(
        "geom.rectangle",
        "Retângulo",
        "section.geometry",
        props=(
            P("x", "Canto x", "0"),
            P("y", "Canto y", "0"),
            P("width", "Largura", "1"),
            P("height", "Altura", "1"),
        ),
        tag_prefix="r",
        icon="rectangle",
    ),
    NodeSpec(
        "geom.disk",
        "Disco",
        "section.geometry",
        props=(
            P("x", "Centro x", "0"),
            P("y", "Centro y", "0"),
            P("r", "Raio", "1"),
        ),
        tag_prefix="c",
        icon="disk",
    ),
    NodeSpec(
        "geom.box",
        "Bloco",
        "section.geometry",
        props=(
            P("x", "Canto x", "0"),
            P("y", "Canto y", "0"),
            P("z", "Canto z", "0"),
            P("dx", "Comprimento x", "1"),
            P("dy", "Comprimento y", "1"),
            P("dz", "Comprimento z", "1"),
        ),
        tag_prefix="blk",
        icon="box",
    ),
    NodeSpec(
        "geom.polygon",
        "Polígono",
        "section.geometry",
        props=(P("points", "Vértices (x y; x y; ...)", "0 0; 1 0; 0 1", kind="text"),),
        tag_prefix="pol",
        icon="polygon",
    ),
    NodeSpec(
        "geom.difference",
        "Diferença",
        "section.geometry",
        props=(
            P("add", "Objetos a manter", [], kind="list"),
            P("subtract", "Objetos a subtrair", [], kind="list"),
        ),
        tag_prefix="dif",
        icon="difference",
    ),
    NodeSpec(
        "geom.intersection",
        "Interseção",
        "section.geometry",
        props=(P("objects", "Objetos", [], kind="list"),),
        tag_prefix="int",
        icon="intersection",
    ),
    NodeSpec(
        "geom.form_union",
        "Formar união",
        "section.geometry",
        tag_prefix="fin",
        icon="union",
        props=(P("info", "Funde todos os objetos mantendo as interfaces internas", "", kind="text"),),
    ),
    NodeSpec(
        "geom.ignore_edges",
        "Remover arestas internas",
        "section.geometry",
        props=(P("edges", "Arestas (numeração após a união)", [], kind="list"),),
        tag_prefix="ige",
        icon="eraser",
    ),
    # ---------------------------------------------------------------- materiais
    NodeSpec(
        "material",
        "Material",
        "section.materials",
        selection=DOMAIN,
        props=(P("properties", "Propriedades (nome, expressão)", {}, kind="table"),),
        tag_prefix="mat",
        icon="material",
    ),
    # ---------------------------------------------------------------- escoamento (Brinkman)
    NodeSpec(
        "physics.brinkman",
        "Escoamento em meio poroso (Brinkman)",
        "section.physics",
        selection=DOMAIN,
        props=(
            P("stokes", "Desprezar inércia (Stokes–Brinkman)", True, kind="bool"),
            P("order", "Ordem dos elementos (u/p)", "P2/P1", kind="choice", choices=("P2/P1", "P3/P2")),
        ),
        tag_prefix="br",
        icon="flow",
    ),
    NodeSpec(
        "brinkman.porous",
        "Matriz porosa",
        "physics.brinkman",
        DOMAIN,
        props=(
            P("porosity", "Porosidade ε_p", "mat:porosity"),
            P("permeability", "Permeabilidade κ", "mat:permeability", unit="m^2"),
        ),
        tag_prefix="porous",
        default_child=True,
        icon="porous",
    ),
    NodeSpec("brinkman.fluid", "Fluido livre", "physics.brinkman", DOMAIN, tag_prefix="fp", icon="fluid"),
    NodeSpec(
        "brinkman.properties",
        "Propriedades do fluido",
        "physics.brinkman",
        DOMAIN,
        props=(
            P("density", "Densidade ρ", "mat:density", unit="kg/m^3"),
            P("viscosity", "Viscosidade μ", "mat:viscosity", unit="Pa*s"),
        ),
        tag_prefix="fmp",
        default_child=True,
        icon="fluid",
    ),
    NodeSpec(
        "brinkman.wall",
        "Parede (sem deslizamento)",
        "physics.brinkman",
        BOUNDARY,
        tag_prefix="wall",
        default_child=True,
        icon="wall",
    ),
    NodeSpec(
        "brinkman.inlet",
        "Entrada (velocidade normal)",
        "physics.brinkman",
        BOUNDARY,
        props=(P("U0", "Velocidade normal de entrada", "0", unit="m/s"),),
        tag_prefix="inl",
        icon="inlet",
    ),
    NodeSpec(
        "brinkman.outlet",
        "Saída (pressão)",
        "physics.brinkman",
        BOUNDARY,
        props=(P("p0", "Pressão", "0", unit="Pa"),),
        tag_prefix="out",
        icon="outlet",
    ),
    NodeSpec(
        "brinkman.init",
        "Valores iniciais",
        "physics.brinkman",
        DOMAIN,
        props=(
            P("u0", "Velocidade inicial", ["0", "0"], kind="list"),
            P("p0", "Pressão inicial", "0"),
        ),
        tag_prefix="init",
        default_child=True,
        icon="init",
    ),
    # ---------------------------------------------------------------- corrente secundária
    NodeSpec(
        "physics.current",
        "Corrente secundária",
        "section.physics",
        selection=DOMAIN,
        props=(
            P("thickness", "Espessura fora do plano", "1[m]", unit="m"),
            P("order", "Ordem dos elementos", "P1", kind="choice", choices=("P1", "P2")),
        ),
        tag_prefix="cd",
        icon="current",
    ),
    NodeSpec(
        "current.electrolyte",
        "Eletrólito",
        "physics.current",
        DOMAIN,
        props=(P("sigmal", "Condutividade do eletrólito σ_l", "mat:sigmal", unit="S/m"),),
        tag_prefix="ice",
        default_child=True,
        icon="electrolyte",
    ),
    NodeSpec(
        "current.porous_electrode",
        "Eletrodo poroso",
        "physics.current",
        DOMAIN,
        props=(
            P("sigmal", "Condutividade do eletrólito σ_l", "mat:sigmal", unit="S/m"),
            P("epsl", "Fração de eletrólito ε_l", "0.4"),
            P("sigmas", "Condutividade do sólido σ_s", "mat:sigma", unit="S/m"),
            P("epss", "Fração de sólido ε_s", "0.6"),
            P(
                "correction",
                "Correção de condutividade efetiva",
                "bruggeman",
                kind="choice",
                choices=("bruggeman", "nenhuma"),
            ),
            P("brug", "Expoente de Bruggeman", "1.5"),
        ),
        tag_prefix="pce",
        icon="electrode",
    ),
    NodeSpec(
        "current.double_layer",
        "Dupla camada (capacitiva)",
        "current.porous_electrode",
        DOMAIN,
        props=(
            P("av", "Área específica a_v", "1e6[1/m]", unit="1/m"),
            P("Cdl", "Capacitância por área C_dl", "0.2[F/m^2]", unit="F/m^2"),
        ),
        tag_prefix="pdl",
        icon="capacitor",
    ),
    NodeSpec(
        "current.reaction_linear",
        "Reação de eletrodo (Butler–Volmer linear)",
        "current.porous_electrode",
        DOMAIN,
        props=(
            P("i0", "Corrente de troca i0", "1[A/m^2]"),
            P("av", "Área específica", "1e6[1/m]"),
            P("Eeq", "Potencial de equilíbrio", "0[V]"),
            P("alphaa", "α anódico", "0.5"),
            P("alphac", "α catódico", "0.5"),
        ),
        tag_prefix="per",
        icon="reaction",
    ),
    NodeSpec(
        "current.insulation",
        "Isolamento",
        "physics.current",
        BOUNDARY,
        tag_prefix="ins",
        default_child=True,
        icon="insulation",
    ),
    NodeSpec(
        "current.potential",
        "Potencial elétrico (sólido)",
        "physics.current",
        BOUNDARY,
        props=(P("phis", "Potencial φ_s", "0[V]", unit="V"),),
        tag_prefix="pot",
        icon="potential",
    ),
    NodeSpec(
        "current.init",
        "Valores iniciais",
        "physics.current",
        DOMAIN,
        props=(
            P("phil", "φ_l inicial", "0"),
            P("phis", "φ_s inicial", "0"),
        ),
        tag_prefix="init",
        default_child=True,
        icon="init",
    ),
    # ---------------------------------------------------------------- transporte diluído
    NodeSpec(
        "physics.transport",
        "Transporte de espécies diluídas (meio poroso)",
        "section.physics",
        DOMAIN,
        props=(
            P("species", "Espécies", ["c"], kind="list"),
            P("charges", "Cargas z", ["0"], kind="list"),
            P("migration", "Migração no campo elétrico", True, kind="bool"),
            P("convection", "Convecção", True, kind="bool"),
            P("potential", "Potencial para migração", "phil", kind="text"),
            P("temperature", "Temperatura", "293.15[K]", unit="K"),
            P("supg", "Estabilização SUPG", True, kind="bool"),
            P(
                "formulation",
                "Variável de concentração",
                "log",
                kind="choice",
                choices=("log", "linear"),
                help="log: resolve ln c (positividade garantida); linear: resolve c",
            ),
            P("order", "Ordem dos elementos", "P1", kind="choice", choices=("P1", "P2")),
        ),
        tag_prefix="tds",
        icon="transport",
    ),
    NodeSpec(
        "transport.free",
        "Propriedades de transporte (fluido livre)",
        "physics.transport",
        DOMAIN,
        props=(
            P("D", "Difusividades", [], kind="list", unit="m^2/s"),
            P("z", "Cargas", [], kind="list"),
        ),
        tag_prefix="cdm",
        icon="transport",
    ),
    NodeSpec(
        "transport.porous",
        "Meio poroso",
        "physics.transport",
        DOMAIN,
        props=(
            P("DF", "Difusividades no fluido", [], kind="list", unit="m^2/s"),
            P("z", "Cargas", [], kind="list"),
            P("porosity", "Porosidade ε_p", "mat:porosity"),
            P("model", "Difusividade efetiva", "bruggeman", kind="choice", choices=("bruggeman", "nenhuma")),
        ),
        tag_prefix="porous",
        default_child=True,
        icon="porous",
    ),
    NodeSpec(
        "transport.noflux",
        "Fluxo nulo",
        "physics.transport",
        BOUNDARY,
        tag_prefix="nflx",
        default_child=True,
        icon="wall",
    ),
    NodeSpec(
        "transport.init",
        "Valores iniciais",
        "physics.transport",
        DOMAIN,
        props=(P("c", "Concentrações iniciais", [], kind="list", unit="mol/m^3"),),
        tag_prefix="init",
        default_child=True,
        icon="init",
    ),
    NodeSpec(
        "transport.inflow",
        "Entrada (concentração)",
        "physics.transport",
        BOUNDARY,
        props=(P("c0", "Concentrações", [], kind="list", unit="mol/m^3"),),
        tag_prefix="in",
        icon="inlet",
    ),
    NodeSpec("transport.outflow", "Saída", "physics.transport", BOUNDARY, tag_prefix="out", icon="outlet"),
    NodeSpec(
        "transport.concentration",
        "Concentração imposta",
        "physics.transport",
        BOUNDARY,
        props=(
            P("apply", "Aplicar à espécie", [], kind="list"),
            P("c", "Valores", [], kind="list", unit="mol/m^3"),
        ),
        tag_prefix="conc",
        icon="concentration",
    ),
    NodeSpec(
        "transport.electrode_coupling",
        "Acoplamento com eletrodo poroso",
        "physics.transport",
        DOMAIN,
        tag_prefix="pec",
        icon="electrode",
    ),
    NodeSpec(
        "transport.reaction_coeffs",
        "Coeficientes de reação",
        "transport.electrode_coupling",
        DOMAIN,
        props=(
            P("iv", "Corrente volumétrica", "cd.ivdl"),
            P("n", "Elétrons transferidos n", "1"),
            P("nu", "Coeficientes estequiométricos", [], kind="list"),
        ),
        tag_prefix="rc",
        icon="reaction",
    ),
    # ---------------------------------------------------------------- equação personalizada (ADR 0014, M1)
    NodeSpec(
        "physics.weakform",
        "Equação personalizada (forma fraca)",
        "section.physics",
        selection=DOMAIN,
        props=(
            P("fields", "Variáveis dependentes", "u", kind="text", help="nomes separados por vírgula"),
            P("order", "Ordem dos elementos", "P1", kind="choice", choices=("P1", "P2")),
            P(
                "equation",
                "Forma fraca (resíduo = 0)",
                "inner(grad(u), grad(test(u)))*dx - 1*test(u)*dx",
                kind="text",
                help="use test(u), dt(u), grad, div, inner, dot, dx, ds, dx(k), ds(k), x, y, t",
            ),
            P(
                "newton_tol",
                "Tolerância do Newton (relativa)",
                "1e-10",
                help="resíduo e passo relativos; 1e-8 basta para variáveis em ln c ou problemas muito rígidos",
            ),
        ),
        tag_prefix="wf",
        icon="equation",
    ),
    NodeSpec(
        "weakform.dirichlet",
        "Valor imposto (Dirichlet)",
        "physics.weakform",
        BOUNDARY,
        props=(P("field", "Variável", "u", kind="text"), P("value", "Valor", "0")),
        tag_prefix="dir",
        icon="potential",
    ),
    NodeSpec(
        "weakform.boundary_term",
        "Termo de contorno (Neumann/Robin)",
        "physics.weakform",
        BOUNDARY,
        props=(
            P(
                "term",
                "Termo somado ao resíduo (sem ds)",
                "-0*test(u)",
                kind="text",
                help="integrado nos contornos selecionados; ex.: -g*test(u) para fluxo g",
            ),
        ),
        tag_prefix="bt",
        icon="inlet",
    ),
    NodeSpec(
        "weakform.domain_term",
        "Termo de domínio adicional",
        "physics.weakform",
        DOMAIN,
        props=(P("term", "Termo somado ao resíduo (sem dx)", "-0*test(u)", kind="text"),),
        tag_prefix="dt",
        icon="equation",
    ),
    NodeSpec(
        "weakform.initial",
        "Valores iniciais",
        "physics.weakform",
        DOMAIN,
        props=(P("field", "Variável", "u", kind="text"), P("value", "Valor inicial", "0")),
        tag_prefix="init",
        default_child=True,
        icon="init",
    ),
    # ---------------------------------------------------------------- equações globais
    NodeSpec("physics.global", "Equações globais", "section.physics", GLOBAL, tag_prefix="ge", icon="global"),
    NodeSpec(
        "global.equations",
        "Equações",
        "physics.global",
        GLOBAL,
        props=(P("equations", "Equações (variável, f(...)=0, valor inicial, unidade)", [], kind="table"),),
        tag_prefix="ge",
        icon="equation",
    ),
    # ---------------------------------------------------------------- multifísica
    NodeSpec(
        "multi.flow_transport",
        "Escoamento → transporte (convecção)",
        "section.multiphysics",
        DOMAIN,
        props=(
            P("flow", "Física de escoamento", "br", kind="text"),
            P("transport", "Física de transporte", "tds", kind="text"),
        ),
        tag_prefix="rfd",
        icon="coupling",
    ),
    # ---------------------------------------------------------------- malha
    NodeSpec(
        "mesh.size",
        "Tamanho",
        "section.mesh",
        props=(
            P("hmax", "Tamanho máximo", "0.1"),
            P("hmin", "Tamanho mínimo", "0.001"),
            P("hgrad", "Taxa de crescimento", "1.3"),
            P("hcurve", "Fator de curvatura", "0.3"),
        ),
        tag_prefix="size",
        icon="mesh",
    ),
    NodeSpec(
        "mesh.size_local",
        "Tamanho local",
        "section.mesh",
        BOUNDARY,
        props=(
            P("hmax", "Tamanho máximo", "0.05"),
            P("hmin", "Tamanho mínimo", "0.001"),
            P("hgrad", "Taxa de crescimento", "1.2"),
            P("dfine", "Largura da faixa fina", "0"),
        ),
        tag_prefix="size",
        icon="mesh",
    ),
    NodeSpec("mesh.triangles", "Triângulos livres", "section.mesh", DOMAIN, tag_prefix="ftri", icon="mesh"),
    NodeSpec(
        "mesh.boundary_layers",
        "Camadas-limite",
        "section.mesh",
        BOUNDARY,
        props=(
            P("n", "Número de camadas", 4, kind="int"),
            P("stretch", "Fator de crescimento", "1.2"),
            P("first", "Espessura da 1ª camada (fator)", "1"),
        ),
        tag_prefix="bl",
        icon="layers",
    ),
    # ---------------------------------------------------------------- estudos
    NodeSpec("study", "Estudo", "section.studies", tag_prefix="std", icon="study"),
    NodeSpec(
        "step.stationary",
        "Estacionário",
        "study",
        props=(
            P("physics", "Físicas resolvidas", [], kind="list"),
            P("couplings", "Acoplamentos ativos", [], kind="list"),
        ),
        tag_prefix="stat",
        icon="stationary",
    ),
    NodeSpec(
        "step.time",
        "Dependente do tempo",
        "study",
        props=(
            P("physics", "Físicas resolvidas", [], kind="list"),
            P("couplings", "Acoplamentos ativos", [], kind="list"),
            P("tlist", "Instantes de saída", "range(0,1,10)", kind="text", unit="s"),
            P("rtol", "Tolerância relativa", "1e-3"),
            P("bdf_max_order", "Ordem máxima BDF", 2, kind="int"),
        ),
        tag_prefix="time",
        icon="time",
    ),
    NodeSpec(
        "step.sweep",
        "Varredura paramétrica",
        "study",
        props=(P("params", "Parâmetros e listas", [], kind="table"),),
        tag_prefix="param",
        icon="sweep",
    ),
    # ---------------------------------------------------------------- resultados
    NodeSpec(
        "result.surface",
        "Superfície",
        "section.results",
        props=(
            P("expr", "Expressão", "", kind="text"),
            P("time", "Instante", "last", kind="text"),
        ),
        tag_prefix="surf",
        icon="surface",
    ),
    NodeSpec(
        "result.plot1d",
        "Gráfico 1D (global)",
        "section.results",
        props=(P("exprs", "Expressões", [], kind="list"),),
        tag_prefix="plot",
        icon="plot",
    ),
]

CATALOG: dict[str, NodeSpec] = {s.kind: s for s in _SPECS}


def spec(kind: str) -> NodeSpec:
    if kind not in CATALOG:
        raise KeyError(f"tipo de nó desconhecido: {kind}")
    return CATALOG[kind]


def children_kinds(parent_kind: str) -> list[NodeSpec]:
    return [s for s in _SPECS if s.parent == parent_kind]


@dataclass
class Field:
    name: str
    label: str
    unit: str
    components: int = 1


PHYSICS_FIELDS: dict[str, list[Field]] = {
    "physics.brinkman": [Field("u", "Velocidade", "m/s", 2), Field("p", "Pressão", "Pa")],
    "physics.current": [Field("phil", "Potencial do eletrólito", "V"), Field("phis", "Potencial do sólido", "V")],
    "physics.transport": [],  # uma concentração por espécie (prop 'species')
    "physics.global": [],
    "physics.weakform": [],  # campos definidos pelo usuário (prop 'fields')
}
