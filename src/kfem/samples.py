"""Modelo de exemplo: célula CDI (diodo iônico), montado só com os nós do KFem.

É o caminho "criado do zero pela interface" (CLAUDE.md §11). Os valores vêm do arquivo do
usuário (docs/mph-format/CDI_ionic_diode-extracao.md); os rótulos são do KFem.
"""

from __future__ import annotations

from kfem.model.catalog import CATALOG
from kfem.model.tree import Model, Node, Selection


def _n(
    kind: str, tag: str, label: str = "", sel: Selection | None = None, active: bool = True, **props: object
) -> Node:
    base = CATALOG[kind].defaults()
    base.update(props)
    return Node(kind, tag, label or CATALOG[kind].label, props=base, selection=sel, active=active)


def cdi_model() -> Model:
    m = Model(name="Célula CDI — diodo iônico")
    ps = m.parameters
    ps.groups = ["Estrutura", "Ajuste", "Internos", "Operação", "Material e líquido"]
    for name, expr, desc, grp in [
        ("L", "100 [mm]", "comprimento dos eletrodos", "Estrutura"),
        ("W", "20[mm]", "espessura fora do plano", "Estrutura"),
        ("te", "0.4[mm]", "espessura do eletrodo", "Estrutura"),
        ("ts", "0.8[mm]", "espessura do espaçador", "Estrutura"),
        ("Lp", "L/10", "tubos de entrada/saída", "Estrutura"),
        ("C", "20.01 [F/g]*mass", "capacitância", "Ajuste"),
        ("Rc", "57.4 [ohm]", "resistência do circuito", "Ajuste"),
        ("V0", "0.29[V]", "intercepto de adsorção", "Ajuste"),
        ("Cdl", "2*C/vol", "capacitância volumétrica", "Internos"),
        ("vol", "te*W*L", "volume de um eletrodo", "Internos"),
        ("tSmooth", "10[s]", "", "Internos"),
        ("a", "1e6[1/m]", "área específica (fictícia)", "Internos"),
        ("lam", "1-V0/Vext_0", "", "Internos"),
        ("v0", "volFlow/W/ts", "velocidade média de entrada", "Internos"),
        ("pM", "ptot-pm", "porosidade de macroporos", "Internos"),
        ("volFlow", "0.42e-3[L/min]", "vazão", "Operação"),
        ("tMax", "7200[s]", "duração", "Operação"),
        ("tSwitch", "7500[s]", "", "Operação"),
        ("c0", "20 [mM]", "concentração de entrada", "Operação"),
        ("Vext_0", "1[V]", "", "Operação"),
        ("V_ext0", "1.2[V]", "tensão aplicada", "Operação"),
        ("iCC_0", "C*Vext_0/tSwitch", "corrente (modo CC)", "Operação"),
        ("sigma_ACC", "106 [S/m]", "condutividade do carbono", "Material e líquido"),
        ("zNa", "1", "", "Material e líquido"),
        ("zCl", "-1", "", "Material e líquido"),
        ("DNa", "1.2e-9 [m^2/s]", "", "Material e líquido"),
        ("DCl", "2.0e-9 [m^2/s]", "", "Material e líquido"),
        ("mass", "1.42[g]", "massa de um eletrodo", "Material e líquido"),
        ("ptot", "0.7", "porosidade total", "Material e líquido"),
        ("pm", "0.3", "porosidade de microporos", "Material e líquido"),
        ("R_L", "5*Rc", "resistência de fuga (opcional)", "Material e líquido"),
    ]:
        ps.add(name, expr, desc, grp)
    m.functions.add(_n("func.step", "step1", "Rampa de tensão", location="tSmooth/2", to="Vext_0", smooth="tSmooth"))

    c = m.comp
    c.length_unit = "mm"
    c.definitions.add(
        Node(
            "def.variables",
            "var1",
            "Variáveis",
            selection=Selection(-1),
            props={"vars": [["cond", "F_const^2/R_const/295[K] * (cNa*zNa^2*DNa + cCl*zCl^2*DCl)"]]},
        )
    )
    c.definitions.add(
        _n(
            "def.probe_integral",
            "dom1",
            "Corrente total",
            Selection(2, [3]),
            name="current",
            expr="cd.ivtot*W",
            unit="A",
        )
    )
    c.definitions.add(
        _n(
            "def.probe_boundary_avg",
            "bnd1",
            "Na na saída",
            Selection(1, [14]),
            name="c_out_Na",
            expr="cNa",
            unit="mol/m^3",
        )
    )
    c.definitions.add(
        _n(
            "def.probe_boundary_avg",
            "bnd2",
            "Cl na saída",
            Selection(1, [14]),
            name="c_out_Cl",
            expr="cCl",
            unit="mol/m^3",
        )
    )

    g = c.geometry
    g.add(_n("geom.rectangle", "r1", "eletrodo inferior", x="0", y="0", width="L", height="te"))
    g.add(_n("geom.rectangle", "r2", "espaçador", x="0", y="te", width="L", height="ts"))
    g.add(_n("geom.rectangle", "r3", "eletrodo superior", x="0", y="te+ts", width="L", height="te"))
    g.add(_n("geom.rectangle", "r4", "tubo de entrada", x="-Lp", y="te", width="Lp", height="ts"))
    g.add(_n("geom.rectangle", "r5", "tubo de saída", x="L", y="te", width="Lp", height="ts"))
    g.add(_n("geom.form_union", "fin", "Formar união"))
    g.add(_n("geom.ignore_edges", "ige1", "Unir canal e tubos", edges=[6, 12]))

    c.materials.add(
        Node(
            "material",
            "mat1",
            "Eletrodo de carbono ativado",
            selection=Selection(2),
            props={
                "properties": {"porosity": "pM", "permeability": "8.9e-12[m^2]", "sigma": "sigma_ACC", "sigmal": "cond"}
            },
        )
    )
    c.materials.add(
        Node(
            "material",
            "mat2",
            "Água (líquida, 20 °C)",
            selection=Selection(2, [1]),
            props={"properties": {"density": "998.2[kg/m^3]", "viscosity": "1.002e-3[Pa*s]", "sigmal": "cond"}},
        )
    )

    br = c.physics.add(_n("physics.brinkman", "br", "Escoamento (Brinkman)", Selection(2)))
    br.add(_n("brinkman.porous", "porous1", sel=Selection(2)))
    br.add(_n("brinkman.properties", "fmp1", sel=Selection(2), fluid_material="mat2"))
    br.add(_n("brinkman.init", "init1", sel=Selection(2)))
    br.add(_n("brinkman.wall", "wall1", sel=Selection(1)))
    br.add(_n("brinkman.inlet", "inl1", sel=Selection(1, [1]), U0="v0"))
    br.add(_n("brinkman.outlet", "out1", sel=Selection(1, [14]), p0="0"))
    br.add(_n("brinkman.fluid", "fp1", sel=Selection(2, [1])))

    cd = c.physics.add(_n("physics.current", "cd", "Corrente secundária", Selection(2), thickness="W"))
    cd.add(_n("current.electrolyte", "ice1", sel=Selection(2)))
    cd.add(_n("current.insulation", "ins1", sel=Selection(1)))
    cd.add(_n("current.init", "init1", sel=Selection(2)))
    cd.add(_n("current.potential", "pot1", "Potencial: eletrodo superior", Selection(1, [9]), phis="V/2"))
    cd.add(_n("current.potential", "pot2", "Potencial: eletrodo inferior", Selection(1, [5]), phis="-V/2"))
    pce = cd.add(_n("current.porous_electrode", "pce1", sel=Selection(2, [2, 3]), epsl="pM", epss="1-ptot"))
    pce.add(_n("current.double_layer", "pdl1", sel=Selection(2), av="a", Cdl="Cdl/a"))
    pce.add(
        _n(
            "current.reaction_linear",
            "per1",
            "Reação de fuga (opcional)",
            Selection(2),
            active=False,
            i0="1/R_L*1/a*1/(F_const/(R_const*295[K]))/vol",
            av="a",
            Eeq="0",
        )
    )

    tds = c.physics.add(
        _n(
            "physics.transport",
            "tds",
            "Transporte de Na⁺ e Cl⁻",
            Selection(2),
            species=["cNa", "cCl"],
            charges=["zNa", "zCl"],
        )
    )
    tds.add(_n("transport.porous", "porous1", sel=Selection(2), DF=["DNa", "DCl"]))
    tds.add(_n("transport.noflux", "nflx1", sel=Selection(1)))
    tds.add(_n("transport.init", "init1", sel=Selection(2), c=["c0", "c0"]))
    tds.add(_n("transport.free", "cdm1", "Propriedades no canal", Selection(2, [1]), D=["DNa", "DCl"]))
    tds.add(_n("transport.inflow", "in1", sel=Selection(1, [1]), c0=["c0", "c0"]))
    tds.add(_n("transport.outflow", "out1", sel=Selection(1, [14])))
    pec = tds.add(_n("transport.electrode_coupling", "pec1", sel=Selection(2, [2, 3])))
    pec.add(_n("transport.reaction_coeffs", "rc2", "Eletrodo superior: Na⁺", Selection(2, [3]), nu=["1", "0"]))
    pec.add(_n("transport.reaction_coeffs", "rc3", "Eletrodo inferior: Cl⁻", Selection(2, [2]), nu=["0", "-1"]))
    tds.add(
        _n(
            "transport.concentration",
            "conc1",
            "Membrana: Cl⁻ = 0 no topo",
            Selection(1, [9]),
            apply=[False, True],
            c=["0", "0"],
        )
    )
    tds.add(
        _n(
            "transport.concentration",
            "conc2",
            "Membrana: Na⁺ = 0 na base",
            Selection(1, [5]),
            apply=[True, False],
            c=["0", "0"],
        )
    )

    ge = c.physics.add(Node("physics.global", "Veff", "Modo de carga", selection=Selection(-1)))
    ge.add(
        Node(
            "global.equations",
            "ge1",
            "Tensão constante (CV)",
            selection=Selection(-1),
            props={"equations": [["V", "V-(V_ext0-Rc*current)", "0", "V"]]},
        )
    )

    c.multiphysics.add(_n("multi.flow_transport", "rfd1", sel=Selection(2), flow="br", transport="tds"))

    c.mesh.add(_n("mesh.size", "size", hmax="0.181", hmin="0.00831", hgrad="1.25", hcurve="0.6"))
    c.mesh.add(
        _n(
            "mesh.size_local",
            "size1",
            "Refino nas faces dos eletrodos",
            Selection(1, [5, 6, 8, 9]),
            hmax="0.0727",
            hmin="0.00208",
            hgrad="1.13",
        )
    )
    c.mesh.add(_n("mesh.triangles", "ftri1"))

    st = m.studies.add(Node("study", "std1", "Estudo 1"))
    st.add(_n("step.stationary", "stat", "Escoamento estacionário", physics=["br"], couplings=[]))
    st.add(
        _n(
            "step.time",
            "time",
            "Carga (transiente)",
            physics=["cd", "tds", "Veff"],
            couplings=["rfd1"],
            tlist="range(0,5,50) range(55,15,2000) range(2030,30,tMax)",
            rtol="1e-3",
        )
    )
    return m
