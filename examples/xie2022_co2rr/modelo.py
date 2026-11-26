"""Modelo 1D de espécies locais na redução de CO2 em meio ácido — reprodução no KFem.

Referência: Y. Xie et al., "High carbon utilization in CO2 reduction to multi-carbon products
in acidic media", Nature Catalysis 5, 564–570 (2022), Supplementary Note 1 e Tabelas S1–S3
(modelo original em COMSOL 5.6). Tudo aqui vem do artigo; as escolhas de leitura estão em
README.md ("Leitura do modelo").

O domínio 1D (0–100 µm, camada catalítica 0–0,4 µm junto à interface gás-líquido) é uma faixa
fina com fluxo nulo em cima e embaixo, o que equivale exatamente ao problema 1D. As cinco
espécies (CO2, HCO3-, CO3 2-, OH-, H+) entram como uma Equação personalizada (forma fraca)
do KFem, com difusão (Bruggeman na camada catalítica), equilíbrios do carbonato e a reação
CO2 + H2O + 2e- -> CO + 2OH- na camada catalítica.
"""

from __future__ import annotations

from kfem.model.catalog import CATALOG
from kfem.model.tree import Model, Node, Selection

SPECIES = ("CO2", "HCO3", "CO3", "OH", "H")
STRIP_H = "0.2"  # altura da faixa (µm): só precisa conter a malha; o problema é 1D


def _n(kind: str, tag: str, label: str = "", sel: Selection | None = None, **props: object) -> Node:
    base = CATALOG[kind].defaults()
    base.update(props)
    return Node(kind, tag, label or CATALOG[kind].label, props=base, selection=sel)


VARIABLES = "primitive"  # "primitive" (como no artigo, com eps) ou "log" (incógnita ln c)


def unknown(s: str) -> str:
    return s if VARIABLES == "primitive" else f"u{s}"


def conc(s: str, in_reaction: bool = False) -> str:
    """Concentração da espécie s (mol/m³).

    primitive: a própria incógnita; nos termos de reação entra max(c, ceps), o "eps" do artigo
    para evitar concentração nula ou negativa. log: c = exp(u)."""
    if VARIABLES == "primitive":
        return f"max({s}, ceps)" if in_reaction else s
    return f"exp(u{s})"


def residual() -> str:
    """Forma fraca das 5 espécies (Supplementary Eqs. 2, 8–16), em unidades SI.

    As incógnitas são u_s = ln c_s (c nunca fica negativa; o artigo usou um "eps" para isso).
    As equações são as mesmas: ∂c/∂t − ∇·(De ∇c) = R, com c = exp(u).
    """
    C = {sp: conc(sp, in_reaction=True) for sp in SPECIES}
    Cd = {sp: conc(sp) for sp in SPECIES}
    chi = "(x < Lcl)"  # 1 na camada catalítica, 0 na camada de difusão
    r = {
        "r1": f"(k1f*{C['CO2']} - k1r*{C['H']}*{C['HCO3']})",  # CO2 + H2O <-> HCO3- + H+
        "r2": f"(k2f*{C['HCO3']} - k2r*{C['H']}*{C['CO3']})",  # HCO3- <-> CO3 2- + H+
        "r3": f"(k3f*{C['CO2']}*{C['OH']} - k3r*{C['HCO3']})",  # CO2 + OH- <-> HCO3-
        "r4": f"(k4f*{C['HCO3']}*{C['OH']} - k4r*{C['CO3']})",  # HCO3- + OH- <-> CO3 2- + H2O
        "rw": f"(kwf - kwr*{C['H']}*{C['OH']})",  # H2O <-> OH- + H+
    }
    rr = f"Rrxn*{chi}"  # Supplementary Eq. 2, só em 0 <= x <= Lcl
    R = {
        "CO2": f"-{r['r1']} - {r['r3']} - {rr}",
        "HCO3": f"{r['r1']} - {r['r2']} + {r['r3']} - {r['r4']}",
        "CO3": f"{r['r2']} + {r['r4']}",
        "H": f"{r['r1']} + {r['r2']} + {r['rw']}",
        "OH": f"-{r['r3']} - {r['r4']} + {r['rw']} + 2*{rr}",
    }
    terms = []
    for sp in SPECIES:
        deff = f"D{sp}*(1 + (eps_cl^1.5 - 1)*{chi})"  # Bruggeman: De = eps^(3/2) D (Eq. 16)
        v = f"test({unknown(sp)})"
        terms.append(f"dt({Cd[sp]})*{v}*dx + {deff}*inner(grad({Cd[sp]}), grad({v}))*dx - ({R[sp]})*{v}*dx")
    return " + ".join(terms)


def _val(v: str) -> str:
    return v if VARIABLES == "primitive" else f"log({v})"


def build(pH: float = 2.0, j_mA_cm2: float = 750.0, tlist: str | None = None) -> Model:
    m = Model(name="Redução de CO2 em meio ácido (Xie et al. 2022)")
    ps = m.parameters
    ps.groups = ["Operação", "Geometria", "Equilíbrios", "Cinética", "Difusão", "Solubilidade", "Derivados"]
    rows = [
        # operação
        ("j_app", f"{j_mA_cm2}[mA/cm^2]", "densidade de corrente aplicada", "Operação"),
        ("pH_b", f"{pH}", "pH do eletrólito (contorno direito)", "Operação"),
        ("pCO2", "1[atm]", "pressão parcial de CO2", "Operação"),
        ("Tk", "293.15", "temperatura (K, adimensional nas correlações)", "Operação"),
        ("Cs", "0.5[mol/L]", "salinidade: K2SO4 0,5 M", "Operação"),
        ("F_c", "96485.33[C/mol]", "constante de Faraday", "Operação"),
        ("n_e", "2", "elétrons por CO2 (CO2 -> CO)", "Operação"),
        # geometria
        ("Lcl", "0.4[um]", "espessura da camada catalítica", "Geometria"),
        ("Ltot", "100[um]", "fim da camada de difusão", "Geometria"),
        ("eps_cl", "0.6", "porosidade da camada catalítica", "Geometria"),
        # Supplementary Table 1
        ("K1", "1[mol/L]*10^(-5.73)", "", "Equilíbrios"),
        ("K2", "1[mol/L]*10^(-8.58)", "", "Equilíbrios"),
        ("Kw", "1e-14[mol^2/L^2]", "", "Equilíbrios"),
        ("k1f", "3.71e-2[1/s]", "", "Cinética"),
        ("k2f", "59.44[1/s]", "", "Cinética"),
        ("k3f", "2.23e3[L/(mol*s)]", "", "Cinética"),
        ("k4f", "6.0e9[L/(mol*s)]", "", "Cinética"),
        ("kwf", "2.4e-5[mol/(L*s)]", "atividade da água = 1 (README)", "Cinética"),
        ("k1r", "k1f/K1", "", "Cinética"),
        ("k2r", "k2f/K2", "", "Cinética"),
        ("k3r", "k3f*Kw/K1", "K3 = K1/Kw", "Cinética"),
        ("k4r", "k4f*Kw/K2", "K4 = K2/Kw", "Cinética"),
        ("kwr", "kwf/Kw", "", "Cinética"),
        # Supplementary Table 2
        ("DH", "9.311e-5[cm^2/s]", "", "Difusão"),
        ("DOH", "5.293e-5[cm^2/s]", "", "Difusão"),
        ("DHCO3", "1.185e-5[cm^2/s]", "", "Difusão"),
        ("DCO3", "0.923e-5[cm^2/s]", "", "Difusão"),
        ("DCO2", "1.910e-5[cm^2/s]", "", "Difusão"),
        # Henry + Séchenov (Eqs. 17–21, Supplementary Table 3)
        ("K0", "3.92e-2[mol/(L*atm)]", "Henry a 293,15 K", "Solubilidade"),
        ("hG", "-0.0172 - 0.000338*(Tk - 298.15)", "hG,0 + hT (T − 298,15), L/mol", "Solubilidade"),
        ("Ks", "((0.0922 + hG) + (0.1117 + hG))[L/mol]", "K+ e SO4 2-", "Solubilidade"),
        ("csat", "K0*pCO2*10^(-Ks*Cs)", "CO2 dissolvido na saturação", "Solubilidade"),
        # derivados
        ("Rrxn", "j_app*eps_cl/(F_c*n_e*Lcl)", "taxa da CO2RR na camada catalítica (Eq. 2)", "Derivados"),
        ("ceps", "1e-15[mol/m^3]", "eps do artigo: piso das concentrações nas reações", "Derivados"),
        ("H_b", "1[mol/L]*10^(-pH_b)", "", "Derivados"),
        ("OH_b", "Kw/H_b", "", "Derivados"),
        ("HCO3_b", "K1*csat/H_b", "equilíbrio com CO2 saturado", "Derivados"),
        ("CO3_b", "K2*HCO3_b/H_b", "", "Derivados"),
    ]
    for name, expr, desc, grp in rows:
        ps.add(name, expr, desc, grp)

    c = m.comp
    c.length_unit = "um"
    g = c.geometry
    g.add(_n("geom.rectangle", "cl", "camada catalítica", x="0", y="0", width="0.4", height=STRIP_H))
    g.add(_n("geom.rectangle", "dl", "camada de difusão", x="0.4", y="0", width="99.6", height=STRIP_H))
    g.add(_n("geom.form_union", "fin", "Formar união"))

    wf = c.physics.add(
        _n(
            "physics.weakform",
            "sp",
            "Espécies locais (reação-difusão)",
            Selection(2),
            fields=", ".join(unknown(sp) for sp in SPECIES),
            order="P1",
            equation=residual(),
            newton_tol="1e-8",
        )
    )
    # contorno esquerdo (x = 0, marcador 1): fluxo nulo para todos, CO2 saturado (Henry + Séchenov)
    wf.add(
        _n(
            "weakform.dirichlet",
            "co2gas",
            "CO2 na interface gás-líquido",
            Selection(1, [1]),
            field=unknown("CO2"),
            value=_val("csat"),
        )
    )
    # contorno direito (x = 100 µm, marcador 7): equilíbrio do eletrólito. Os marcadores seguem a
    # ordem de numeração da geometria: 1 x=0, 2/3 base/topo da CL, 4 interface CL|DL (x = Lcl),
    # 5/6 base/topo da DL, 7 x=100 µm. (Antes de a geometria passar a ser montada na unidade do
    # componente, a interface x = Lcl se perdia na tolerância do OCC e o contorno direito era o 6.)
    for s, v in (("CO2", "csat"), ("HCO3", "HCO3_b"), ("CO3", "CO3_b"), ("OH", "OH_b"), ("H", "H_b")):
        wf.add(
            _n(
                "weakform.dirichlet",
                f"bulk_{s}",
                f"{s}: eletrólito",
                Selection(1, [7]),
                field=unknown(s),
                value=_val(v),
            )
        )
    for s, v in (("CO2", "csat"), ("HCO3", "HCO3_b"), ("CO3", "CO3_b"), ("OH", "OH_b"), ("H", "H_b")):
        wf.add(_n("weakform.initial", f"ini_{s}", f"inicial {s}", Selection(2), field=unknown(s), value=_val(v)))

    # malha: 0,16 µm na camada catalítica e 0,1 µm na de difusão (máximos do artigo)
    c.mesh.add(_n("mesh.size", "size", hmax="0.1"))
    c.mesh.add(_n("mesh.triangles", "tri"))

    st = m.studies.add(Node("study", "std1", "Estudo 1"))
    st.add(
        _n(
            "step.time",
            "time",
            "Rumo ao estado estacionário",
            physics=["sp"],
            couplings=[],
            tlist=tlist or "0 1e-5 1e-4 1e-3 1e-2 0.1 0.3 1 3 10 30 60 120",
            rtol="0.01",
        )
    )
    return m


if __name__ == "__main__":
    import sys

    from kfem.io.kfem_format import save

    # python modelo.py [SAIDA.kfem [PH [J_mA_cm2]]]  (padrão: pH 2, 750 mA/cm²)
    out = sys.argv[1] if len(sys.argv) > 1 else "co2rr_acido.kfem"
    pH = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    j = float(sys.argv[3]) if len(sys.argv) > 3 else 750.0
    save(build(pH, j), out)
    print(f"salvo: {out} (pH {pH:g}, {j:g} mA/cm²)")
