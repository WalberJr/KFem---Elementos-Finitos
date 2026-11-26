# ruff: noqa: E501
"""MAIN do artigo (Nature Catalysis): modelo contínuo 1D/2D (resultados reais), DFT QE+Environ e
experimentos (espaços reservados [TO FILL]). Usa o MAIN.docx do usuário como modelo de estilo.

    PYTHONPATH=<python-docx> python artigo_main.py MODELO.docx DIR_EN DIR_FIGS SAIDA.docx

DIR_EN: figuras e indicadores em inglês (indicadores.json, indicadores2d.json, integrado.json);
DIR_FIGS: figuras compostas do artigo (Fig1..Fig3).
"""

from __future__ import annotations

import copy
import json
import math
import re
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_TAB_ALIGNMENT
from docx.shared import Cm, Pt
from PIL import Image

TEMPLATE, EN, FIGS, OUT = (Path(a) for a in sys.argv[1:5])
TMP = Path(tempfile.mkdtemp())

# ------------------------------------------------------------------ dados
D1 = {(r["pH"], r["j"]): r for r in json.loads((EN / "indicadores.json").read_text())}
D2J = json.loads((EN / "indicadores2d.json").read_text())
D2 = {(r["pH"], r["j"], r["shape"]): r for r in D2J["casos"]}
VER = D2J["verificacao_1d"]
INT = json.loads((EN / "integrado.json").read_text())
F_C, D_H, EPS, L = 96485.33, 9.311e-9, 0.6, 100e-6


def jstar(pH):
    return F_C * D_H * 1000 * 10 ** (-pH) / (EPS * L) / 10


LS, RD = 20.0, 20.0 / math.pi
AC = math.sqrt(100 - RD**2)
W = {"plano": 20.0, "convexo": 2 * RD + 1.2, "conico": 2 * AC}
FAC = {s: LS / W[s] for s in W}
phis = [(r["pH_2d_mean"] - r["pH_1d_nominal"]) / (r["pH_1d_proj"] - r["pH_1d_nominal"]) for r in INT if r["shape"] != "plano"]
fronts = [abs(r["front_2d"] - r["front_1d_proj"]) for r in INT if r["front_2d"] is not None]
cl2 = [r["co2_cl_2d_mean"] for r in INT if r["j"] == 500]
cl1 = [r["co2_cl_1d_proj"] for r in INT if r["j"] == 500 and r["shape"] != "plano"]
vmax = max(v["max_dCO2_mM"] for v in VER.values())
dmax = max(D2[(pH, j, s)]["pH_el_mean"] - D2[(pH, j, "plano")]["pH_el_mean"] for pH, j in ((2, 500), (2, 200), (4, 500)) for s in ("convexo", "conico"))


def n(v, nd=1):
    return f"{v:.{nd}f}"


def p2(pH, j, s, k="pH_el_mean", nd=2):
    return n(D2[(pH, j, s)][k], nd)


# ------------------------------------------------------------------ referências (estilo Nature)
REFS = {
    "rabinowitz2020": "Rabinowitz, J. A. & Kanan, M. W. The future of low-temperature carbon dioxide electrolysis depends on solving one basic problem. Nat. Commun. 11, 5231 (2020).",
    "ma2020": "Ma, M. et al. Insights into the carbon balance for CO2 electroreduction on Cu using gas diffusion electrode reactor designs. Energy Environ. Sci. 13, 977–985 (2020).",
    "nitopi2019": "Nitopi, S. et al. Progress and perspectives of electrochemical CO2 reduction on copper in aqueous electrolyte. Chem. Rev. 119, 7610–7672 (2019).",
    "kuhl2012": "Kuhl, K. P., Cave, E. R., Abram, D. N. & Jaramillo, T. F. New insights into the electrochemical reduction of carbon dioxide on metallic copper surfaces. Energy Environ. Sci. 5, 7050–7059 (2012).",
    "hori2008": "Hori, Y. in Modern Aspects of Electrochemistry Vol. 42 (eds Vayenas, C. G., White, R. E. & Gamboa-Aldeco, M. E.) 89–189 (Springer, 2008).",
    "dinh2018": "Dinh, C.-T. et al. CO2 electroreduction to ethylene via hydroxide-mediated copper catalysis at an abrupt interface. Science 360, 783–787 (2018).",
    "huang2021": "Huang, J. E. et al. CO2 electrolysis to multicarbon products in strong acid. Science 372, 1074–1078 (2021).",
    "xie2022": "Xie, Y. et al. High carbon utilization in CO2 reduction to multi-carbon products in acidic media. Nat. Catal. 5, 564–570 (2022).",
    "bondue2021": "Bondue, C. J., Graf, M., Goyal, A. & Koper, M. T. M. Suppression of hydrogen evolution in acidic electrolytes by electrochemical CO2 reduction. J. Am. Chem. Soc. 143, 279–285 (2021).",
    "monteiro2021": "Monteiro, M. C. O. et al. Absence of CO2 electroreduction on copper, gold and silver electrodes without metal cations in solution. Nat. Catal. 4, 654–662 (2021).",
    "gu2022": "Gu, J. et al. Modulating electric field distribution by alkali cations for CO2 electroreduction in strongly acidic medium. Nat. Catal. 5, 268–276 (2022).",
    "varela2016": "Varela, A. S., Kroschel, M., Reier, T. & Strasser, P. Controlling the selectivity of CO2 electroreduction on copper: the effect of the electrolyte concentration and the importance of the local pH. Catal. Today 260, 8–13 (2016).",
    "gupta2006": "Gupta, N., Gattrell, M. & MacDougall, B. Calculation for the cathode surface concentrations in the electrochemical reduction of CO2 in KHCO3 solutions. J. Appl. Electrochem. 36, 161–172 (2006).",
    "burdyny2019": "Burdyny, T. & Smith, W. A. CO2 reduction on gas-diffusion electrodes and why catalytic performance must be assessed at commercially-relevant conditions. Energy Environ. Sci. 12, 1442–1453 (2019).",
    "weng2018": "Weng, L.-C., Bell, A. T. & Weber, A. Z. Modeling gas-diffusion electrodes for CO2 reduction. Phys. Chem. Chem. Phys. 20, 16973–16984 (2018).",
    "bui2022": "Bui, J. C. et al. Continuum modeling of porous electrodes for electrochemical synthesis. Chem. Rev. 122, 11022–11084 (2022).",
    "hori2003": "Hori, Y., Takahashi, I., Koga, O. & Hoshi, N. Electrochemical reduction of carbon dioxide at various series of copper single crystal electrodes. J. Mol. Catal. A 199, 39–47 (2003).",
    "schouten2012": "Schouten, K. J. P., Qin, Z., Pérez Gallent, E. & Koper, M. T. M. Two pathways for the formation of ethylene in CO reduction on single-crystal copper electrodes. J. Am. Chem. Soc. 134, 9864–9867 (2012).",
    "calle2013": "Calle-Vallejo, F. & Koper, M. T. M. Theoretical considerations on the electroreduction of CO to C2 species on Cu(100) electrodes. Angew. Chem. Int. Ed. 52, 7282–7285 (2013).",
    "peterson2010": "Peterson, A. A., Abild-Pedersen, F., Studt, F., Rossmeisl, J. & Nørskov, J. K. How copper catalyzes the electroreduction of carbon dioxide into hydrocarbon fuels. Energy Environ. Sci. 3, 1311–1315 (2010).",
    "liu2016": "Liu, M. et al. Enhanced electrocatalytic CO2 reduction via field-induced reagent concentration. Nature 537, 382–386 (2016).",
    "resasco2017": "Resasco, J. et al. Promoter effects of alkali metal cations on the electrochemical reduction of carbon dioxide. J. Am. Chem. Soc. 139, 11277–11287 (2017).",
    "norskov2004": "Nørskov, J. K. et al. Origin of the overpotential for oxygen reduction at a fuel-cell cathode. J. Phys. Chem. B 108, 17886–17892 (2004).",
    "zeebe2001": "Zeebe, R. E. & Wolf-Gladrow, D. CO2 in Seawater: Equilibrium, Kinetics, Isotopes (Elsevier, 2001).",
    "weisenberger1996": "Weisenberger, S. & Schumpe, A. Estimation of gas solubilities in salt solutions at temperatures from 273 K to 363 K. AIChE J. 42, 298–300 (1996).",
    "baratta2023": "Baratta, I. A. et al. DOLFINx: the next generation FEniCS problem solving environment. Zenodo https://doi.org/10.5281/zenodo.10447666 (2023).",
    "geuzaine2009": "Geuzaine, C. & Remacle, J.-F. Gmsh: a 3-D finite element mesh generator with built-in pre- and post-processing facilities. Int. J. Numer. Methods Eng. 79, 1309–1331 (2009).",
    "amestoy2001": "Amestoy, P. R., Duff, I. S., L'Excellent, J.-Y. & Koster, J. A fully asynchronous multifrontal solver using distributed dynamic scheduling. SIAM J. Matrix Anal. Appl. 23, 15–41 (2001).",
    "giannozzi2017": "Giannozzi, P. et al. Advanced capabilities for materials modelling with Quantum ESPRESSO. J. Phys. Condens. Matter 29, 465901 (2017).",
    "giannozzi2020": "Giannozzi, P. et al. Quantum ESPRESSO toward the exascale. J. Chem. Phys. 152, 154105 (2020).",
    "andreussi2012": "Andreussi, O., Dabo, I. & Marzari, N. Revised self-consistent continuum solvation in electronic-structure calculations. J. Chem. Phys. 136, 064102 (2012).",
    "nattino2019": "Nattino, F., Truscott, M., Marzari, N. & Andreussi, O. Continuum models of the electrochemical diffuse layer in electronic-structure calculations. J. Chem. Phys. 150, 041722 (2019).",
    "hammer1999": "Hammer, B., Hansen, L. B. & Nørskov, J. K. Improved adsorption energetics within density-functional theory using revised Perdew–Burke–Ernzerhof functionals. Phys. Rev. B 59, 7413–7421 (1999).",
    "grimme2010": "Grimme, S., Antony, J., Ehrlich, S. & Krieg, H. A consistent and accurate ab initio parametrization of density functional dispersion correction (DFT-D) for the 94 elements H–Pu. J. Chem. Phys. 132, 154104 (2010).",
    "prandini2018": "Prandini, G., Marrazzo, A., Castelli, I. E., Mounet, N. & Marzari, N. Precision and efficiency in solid-state pseudopotential calculations. npj Comput. Mater. 4, 72 (2018).",
    "henkelman2000": "Henkelman, G., Uberuaga, B. P. & Jónsson, H. A climbing image nudged elastic band method for finding saddle points and minimum energy paths. J. Chem. Phys. 113, 9901–9904 (2000).",
    "chan2015": "Chan, K. & Nørskov, J. K. Electrochemical barriers made simple. J. Phys. Chem. Lett. 6, 2663–2668 (2015).",
    "trasatti1986": "Trasatti, S. The absolute electrode potential: an explanatory note. Pure Appl. Chem. 58, 955–966 (1986).",
}
ORDER: list[str] = []


def cite(*keys: str) -> str:
    """Números dos citados, na ordem da primeira citação, como 1,2 ou 3–5."""
    nums = []
    for k in keys:
        assert k in REFS, k
        if k not in ORDER:
            ORDER.append(k)
        nums.append(ORDER.index(k) + 1)
    nums = sorted(set(nums))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(f"{nums[i]}–{nums[j]}" if j - i >= 2 else ",".join(map(str, nums[i:j + 1])))
        i = j + 1
    return "^{" + ",".join(out) + "}"


# ------------------------------------------------------------------ documento a partir do MAIN
doc = Document(str(TEMPLATE))
body = doc.element.body
paras = list(doc.paragraphs)
keep = 9  # título, autores, afiliações e e-mails
ack_text = next((p.text for p in paras if p.text.startswith("We thank the financial support")), "")
title_p = paras[0]
# remove tudo o que vem depois do bloco de autores (parágrafos, tabelas, campos/sdt da lista antiga)
last_kept = paras[keep - 1]._element
for el in list(body):
    if el.tag.endswith("sectPr"):
        continue
    if el.getparent() is body and el is not last_kept and list(body).index(el) > list(body).index(last_kept):
        body.remove(el)
# título novo, mesma formatação
r0 = copy.deepcopy(title_p.runs[0]._r)
for r in list(title_p.runs):
    r._r.getparent().remove(r._r)
title_p._p.append(r0)
title_p.runs[0].text = "Interfacial alkalinization and electrode morphology govern CO₂ electroreduction on copper in acidic media"

FONT = "Times New Roman"


def _rich(p, text: str, bold=False, italic=False, size=None, hl=False):
    if not hl and "[TO FILL" in text:  # trechos a preencher: destacados, com sub/sobrescritos
        for seg in re.split(r"(\[TO FILL[^\]]*\])", text):
            if seg:
                _rich(p, seg, bold, italic, size, hl=seg.startswith("[TO FILL"))
        return
    for tok in re.split(r"(_\{[^}]*\}|\^\{[^}]*\}|\*\*[^*]+\*\*)", text):
        if not tok:
            continue
        sub, sup, b, h = tok.startswith("_{"), tok.startswith("^{"), tok.startswith("**"), False
        txt = tok[2:-1] if (sub or sup) else tok[2:-2] if b else tok
        r = p.add_run(txt)
        r.font.name = FONT
        r.font.subscript, r.font.superscript = sub, sup
        r.bold = bold or b
        r.italic = italic
        if size:
            r.font.size = Pt(size)
        if h or hl:
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW


def P(text: str = "", bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=None, style="Standard", after=6):
    p = doc.add_paragraph(style=style)
    p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.5
    _rich(p, text, bold=bold, italic=italic, size=size)
    return p


def H(text: str, level: int = 1):
    p = doc.add_paragraph(style="Standard")
    p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    _rich(p, text, bold=True, italic=level == 2, size=12 if level == 1 else None)
    return p


_eq = [0]


def EQ(tex: str, scale: float = 0.75):
    _eq[0] += 1
    img = TMP / f"eq{_eq[0]}.png"
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=15)
    fig.savefig(img, dpi=220, bbox_inches="tight", pad_inches=0.05, facecolor="white")
    plt.close(fig)
    w = Image.open(img).size[0]
    p = doc.add_paragraph(style="Standard")
    tw = doc.sections[0].page_width.cm - doc.sections[0].left_margin.cm - doc.sections[0].right_margin.cm
    p.paragraph_format.tab_stops.add_tab_stop(Cm(tw / 2), WD_TAB_ALIGNMENT.CENTER)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(tw), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run("\t")
    p.add_run().add_picture(str(img), width=Cm(min(w / 220 * 2.54 * scale, tw - 2)))
    r = p.add_run(f"\t({_eq[0]})")
    r.font.name = FONT
    return _eq[0]


def FIG(path: Path | None, caption: str, label: str, width_cm: float = 16.5, placeholder: str | None = None):
    p = doc.add_paragraph(style="Standard")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    if path is not None:
        p.add_run().add_picture(str(path), width=Cm(width_cm))
    else:
        _rich(p, f"[TO FILL: {placeholder}]")
    c = doc.add_paragraph(style="Standard")
    c.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    c.paragraph_format.space_after = Pt(10)
    _rich(c, f"**{label} | **", size=10)
    _rich(c, caption, size=10)


# ------------------------------------------------------------------ texto
P("", after=0)
P("**Abstract**", align=WD_ALIGN_PARAGRAPH.LEFT)
P(
    "Acidic electrolytes avoid the carbonate losses of CO_{2} electrolysis only if the catalyst surface becomes locally alkaline. "
    "Here we resolve this local environment on copper by combining one- and two-dimensional reaction–diffusion simulations, density functional theory with implicit solvent and electrolyte, and experiments. "
    f"A proton balance sets the alkalinization threshold ({n(jstar(2))} mA cm^{{-2}} at pH 2), above which the surface reaches pH 12–13 and an acid–base front regenerates CO_{{2}} from carbonate. "
    f"For the same active area and current, convex and pointed electrodes raise the surface pH by up to {n(dmax, 2)} units: they concentrate current over a narrower footprint, which sets the far field, while their larger gas–liquid interface keeps CO_{{2}} in the catalyst layer at the flat-electrode level. "
    "[TO FILL: facet-resolved DFT result; experimental Faradaic efficiency and carbon utilization.]"
)

P(
    "Electrochemical CO_{2} reduction (CO_{2}RR) powered by renewable electricity offers a route to fuels and chemicals with a low carbon footprint, and copper remains the only metal that converts CO_{2} into multi-carbon products with substantial selectivity"
    + cite("hori2008", "kuhl2012", "nitopi2019")
    + ". In neutral and alkaline electrolytes, however, the hydroxide generated at the cathode reacts with CO_{2} to form carbonate, so that most of the CO_{2} fed to the reactor is lost to the electrolyte rather than reduced"
    + cite("rabinowitz2020", "ma2020")
    + ". Acidic electrolytes avoid this loss and regenerate CO_{2} from carbonate, but they also favour the hydrogen evolution reaction (HER)"
    + cite("huang2021", "bondue2021")
    + ". CO_{2}RR in acid is therefore viable only when the electrode itself creates a locally alkaline environment that protects the catalyst from the bulk protons while the bulk acid recovers the carbonate"
    + cite("huang2021", "xie2022", "gu2022")
    + "."
)
P(
    "This local environment is not a property of the catalyst alone. It results from the competition between the hydroxide produced at the surface and the protons supplied by the electrolyte, and it is shaped by the reaction–diffusion of the carbonate system"
    + cite("gupta2006", "varela2016", "weng2018", "bui2022")
    + ". It is also sensitive to the morphology of the electrode: sharp or curved features change the local fields and concentrations around the active sites"
    + cite("liu2016")
    + ", and the selectivity of copper itself depends on the exposed facet, with Cu(100) favouring C–C coupling and Cu(111) favouring methane and hydrogen"
    + cite("hori2003", "schouten2012", "calle2013")
    + ". Cations further modulate the interfacial field and the stabilization of CO_{2}-derived intermediates"
    + cite("resasco2017", "monteiro2021", "gu2022")
    + ". A quantitative link between the electrolyte conditions, the shape of the electrode and the energetics of the copper facets is still missing."
)
P(
    "Here we build that link in three steps. First, we reproduce the reaction–diffusion model of acidic CO_{2}RR"
    + cite("xie2022")
    + " in one dimension and map the regimes of the local environment as a function of bulk pH and current density. Second, we extend the model to two dimensions to compare flat, convex and pointed electrodes with the same active area, and we use the one-dimensional model to separate the effect of current concentration from the effect of local geometry. "
    "Third, we evaluate the energetics of the key intermediates on Cu(111), Cu(100) and Cu(110) with density functional theory, implicit solvent and electrolyte, at the local pH predicted by the continuum model, and we test the predictions experimentally. [TO FILL: one sentence summarizing the experimental validation.]"
)

H("Results")
H("Local reaction environment in acidic CO₂RR", 2)
P(
    "The one-dimensional model describes a porous catalyst layer (CL, 0.4 µm, porosity 0.6) at the gas–liquid interface, followed by a 100 µm diffusion layer that ends in the bulk electrolyte (**Fig. 1a**). "
    "CO_{2} enters at the interface at its saturation concentration, is reduced in the CL (CO_{2} + H_{2}O + 2e^{−} → CO + 2OH^{−}) and takes part in the five acid–base equilibria of the carbonate system, while protons diffuse from the bulk"
    + cite("xie2022", "zeebe2001")
    + ". We solved the model with the finite-element method for bulk pH 0–4 and 10–750 mA cm^{−2} (36 cases), reaching steady state with a time-dependent study as in the original work (Methods)."
)
P(
    f"The surface pH separates into two regimes (**Fig. 1b**). At pH 0 the surface stays acidic at all current densities (pH ≤ {n(D1[(0, 750)]['pH_s'], 2)} at 750 mA cm^{{−2}}). At pH 2–4, once the current exceeds a threshold, the surface becomes strongly alkaline, with pH {n(D1[(2, 100)]['pH_s'])}–{n(D1[(2, 750)]['pH_s'])} at pH 2 for 100–750 mA cm^{{−2}}, and a front narrower than 1 µm separates the alkaline region from the acidic bulk. "
    "The threshold follows from a proton balance: in steady state all OH^{−} produced in the CL (εj/F per unit area) must be neutralized by the protons that reach the surface by diffusion, which is bounded by D_{H}c_{H,b}/L. This gives"
)
EQ(r"$j^{*} \approx \dfrac{F\,D_{\mathrm{H^+}}\,c_{\mathrm{H^+},b}}{\varepsilon\,L}$")
P(
    f"which is {n(jstar(2))} mA cm^{{−2}} at pH 2 and {n(jstar(1), 0)} mA cm^{{−2}} at pH 1. The simulations place the transition exactly there: at pH 2 the surface is near neutral at 15 mA cm^{{−2}} (pH {n(D1[(2, 15)]['pH_s'], 2)}) and alkaline at 20 mA cm^{{−2}} (pH {n(D1[(2, 20)]['pH_s'], 2)}), and at pH 1 it is near neutral at 150 mA cm^{{−2}} (pH {n(D1[(1, 150)]['pH_s'], 2)}) and alkaline from 200 mA cm^{{−2}}. "
    "Because the balance is exact for the published equations and parameters and does not depend on the numerical scheme, it also explains why the transition reported in the original study, at 100–150 mA cm^{−2} for pH 2"
    + cite("xie2022")
    + ", lies about an order of magnitude above j*: the minimum CO_{2} reported there is reproduced here at current densities about 3.5 times lower (**Fig. 1c** and Supplementary Note 4)."
)
P(
    f"In the alkaline regime, CO_{{2}} is captured by OH^{{−}} and a CO_{{2}} valley develops 10–30 µm from the surface, reaching {n(D1[(4, 500)]['co2_min'], 2)} mM at pH 4 and 500 mA cm^{{−2}}. Near the acid–base front, the bicarbonate and carbonate formed in the alkaline region meet the bulk protons and are converted back into CO_{{2}}, which exceeds saturation ({n(D1[(2, 100)]['co2_max'])} mM against 32.1 mM at pH 2 and 100 mA cm^{{−2}}; up to {n(D1[(1, 750)]['co2_max'], 0)} mM at pH 1). "
    "This regeneration is the mechanism that underlies the high carbon utilization of acidic CO_{2}RR. The model has no gas phase, so these values are upper bounds for the regenerated CO_{2}."
)
FIG(FIGS / "Fig1_local_environment.png",
    "**Local reaction environment in one dimension.** **a**, Model domain: gas–liquid interface (x = 0), catalyst layer (0–0.4 µm, drawn thicker) and diffusion layer to the bulk electrolyte at x = 100 µm. **b**, Steady-state surface pH as a function of bulk pH and current density. **c**, Minimum CO_{2} in the domain versus current density (lines, this work; circles, values read from ref. "
    + cite("xie2022").strip("^{}") + ") and surface pH at bulk pH 2 across the alkalinization threshold.",
    "Fig. 1")

H("Electrode morphology redistributes the local environment", 2)
P(
    "To isolate the role of geometry we compared three electrodes with the same active length (L_{s} = 20 µm, the two-dimensional equivalent of the same area), the same current density per active area and therefore the same total current (**Fig. 2a**): a flat electrode, a convex electrode (semicircle, πR = L_{s}) and a pointed electrode (triangle with the height of the semicircle). "
    "Each case is a periodic cell of identical electrodes bounded by symmetry walls, so that the cell width w equals the footprint of each shape: 20.00, 13.93 and 15.42 µm. The same equations, parameters and boundary conditions of the one-dimensional model were used, and the reaction rate was normalized by the real area of each catalyst layer so that the total current is j·L_{s} in all cases (Methods). "
    f"The flat electrode in two dimensions reproduces the one-dimensional solution within {n(vmax, 2)} mM in CO_{{2}} and 10^{{−4}} in surface pH, which validates the geometric construction and the normalization."
)
P(
    f"At pH 2 and 500 mA cm^{{−2}}, the three electrodes deplete CO_{{2}} within about 15 µm and keep most of the cell alkaline (**Fig. 2b**). The surface is, however, more alkaline on the curved electrodes: the arc-averaged surface pH is {p2(2, 500, 'convexo')} on the convex, {p2(2, 500, 'conico')} on the pointed and {p2(2, 500, 'plano')} on the flat electrode, and the same order holds at pH 2 / 200 mA cm^{{−2}} ({p2(2, 200, 'convexo')}, {p2(2, 200, 'conico')}, {p2(2, 200, 'plano')}) and at pH 4 / 500 mA cm^{{−2}} ({p2(4, 500, 'convexo')}, {p2(4, 500, 'conico')}, {p2(4, 500, 'plano')}). "
    "Along the curved electrodes the surface pH is not uniform (**Fig. 2c**): it is highest at the feet, in the confined corner between neighbouring electrodes where OH^{−} accumulates, and lowest at the centre or apex, which protrudes towards the electrolyte. "
    f"In contrast, the arc-averaged CO_{{2}} in the middle of the catalyst layer is almost the same for the three shapes ({n(min(cl2))}–{n(max(cl2))} mM at 500 mA cm^{{−2}}), because the layer is fed directly by the gas–liquid interface."
)
FIG(FIGS / "Fig2_electrode_morphology.png",
    "**Flat, convex and pointed electrodes with the same active area.** **a**, Two-dimensional cells (catalyst layer drawn three times thicker) with symmetry walls; the electrolyte is at y = 100 µm. **b**, Steady-state CO_{2} and pH near the electrode at pH 2 and 500 mA cm^{−2}. **c**, Surface pH (top) and CO_{2} at the middle of the catalyst layer (bottom) along the electrode for the three conditions studied.",
    "Fig. 2")

H("Current concentration and local geometry", 2)
P(
    f"With the same total current, the curved electrodes deliver more current per unit of footprint: j_{{proj}} = j·L_{{s}}/w, that is, {n(FAC['convexo'], 2)} j for the convex and {n(FAC['conico'], 2)} j for the pointed electrode. The ranking of the surface pH follows exactly this factor. "
    "To test whether current concentration alone explains the effect, we ran the one-dimensional model at the projected current of each curved electrode and compared it with the two-dimensional solution in two regions (**Fig. 3**)."
)
P(
    f"Far from the electrode, the projected current is all that matters: the position of the acid–base front in two dimensions agrees with the one-dimensional prediction at j_{{proj}} within {n(max(fronts), 1)} µm. At the surface, however, the one-dimensional model at j_{{proj}} overestimates the pH. "
    f"The two-dimensional surface pH lies between the one-dimensional values at the nominal and projected currents, recovering {n(100 * min(phis), 0)}–{n(100 * max(phis), 0)}% of the gain predicted by current concentration. "
    f"The reason is that a curved electrode multiplies by L_{{s}}/w not only the current but also the gas–liquid interface through which CO_{{2}} enters. CO_{{2}} in the catalyst layer therefore stays near the flat-electrode level ({n(min(cl2))}–{n(max(cl2))} mM) instead of dropping to the {n(min(cl1))}–{n(max(cl1))} mM of the equivalent one-dimensional case, and the additional CO_{{2}} consumes part of the OH^{{−}} through CO_{{2}} + OH^{{−}} → HCO_{{3}}^{{−}} near the surface. "
    "The one-dimensional model at the nominal and projected currents thus brackets the surface pH of a structured electrode, while the two-dimensional model adds the distribution along the surface, which is where facet- and site-dependent selectivity enters."
)
FIG(FIGS / "Fig3_integrated_1D_2D.png",
    "**Separating current concentration from local geometry.** Surface pH (top) and CO_{2} at the middle of the catalyst layer (bottom) versus current per footprint area, j_{proj} = j·L_{s}/w, at bulk pH 2 (left) and pH 4 (right). Lines: one-dimensional model. Symbols: arc-averaged two-dimensional values placed at their projected current; bars show the minimum and maximum along the electrode and arrows start at the nominal current.",
    "Fig. 3")

H("Facet-resolved energetics under the local environment", 2)
P(
    "The continuum results define the conditions under which the copper surface operates: a local pH of 12–13 at bulk pH 2–4, CO_{2} in the catalyst layer of 27–30 mM, and different conditions at the feet and at the apex of structured electrodes. "
    "We evaluated the energetics of the key intermediates on Cu(111), Cu(100) and Cu(110) under these conditions with density functional theory, self-consistent continuum solvation and a modified Poisson–Boltzmann electrolyte for 0.5 M K_{2}SO_{4}"
    + cite("andreussi2012", "nattino2019")
    + ". The electrode potential was set by charging the slab and referenced to the bulk electrolyte, and the reversible hydrogen electrode scale was defined with the local pH from the continuum model rather than the bulk pH (Methods). "
    f"At bulk pH 2 and a local pH of {p2(2, 500, 'plano')}, this shifts the local RHE scale by {n(0.0592 * (D2[(2, 500, 'plano')]['pH_el_mean'] - 2), 2)} V with respect to the bulk RHE scale, which changes the driving force of the steps that are not proton-coupled, such as CO_{{2}} activation and C–C coupling"
    + cite("chan2015")
    + "."
)
P("[TO FILL: free-energy diagrams of *CO_{2}, *COOH, *CO, *CHO/*COH and *OCCO/*OCCOH on Cu(111), Cu(100) and Cu(110) at the local pH and potential; limiting potentials; C–C coupling barriers; competition with *H and *OH; comparison of feet- and apex-like conditions.]")
FIG(None, "**Facet-resolved energetics of CO_{2}RR on copper under the local reaction environment.** [TO FILL: legend for the DFT figure.]", "Fig. 4",
    placeholder="Fig. 4 — free-energy diagrams and C–C coupling barriers on Cu(111), Cu(100) and Cu(110) at the local pH (QE + Environ)")

H("Experimental validation", 2)
P("[TO FILL: catalyst synthesis and morphology (flat, convex-like and pointed-like Cu structures); structural and compositional characterization (SEM, XRD, XPS); exposed facets.]")
P("[TO FILL: CO_{2}RR performance in acidic electrolyte (K_{2}SO_{4} 0.5 M, pH 2–4): Faradaic efficiencies, partial current densities, single-pass carbon utilization and stability; comparison with the predicted alkalinization threshold and morphology effect.]")
FIG(None, "**CO_{2}RR performance in acidic media.** [TO FILL: legend for the experimental figure.]", "Fig. 5",
    placeholder="Fig. 5 — FE, partial current densities and carbon utilization of the Cu electrodes")

H("Discussion")
P(
    "The local environment of acidic CO_{2}RR is governed by a simple balance between the hydroxide produced at the electrode and the protons supplied by the electrolyte. This balance sets the alkalinization threshold, j* ∝ 10^{−pH}, and it holds in two dimensions when the current is referred to the electrode footprint. "
    "Electrode morphology acts on this balance in two ways: it concentrates current over a narrower footprint, which pushes the acid–base front towards the electrolyte exactly as a flat electrode at higher current would, and it redistributes OH^{−} along the surface, so that confined regions become more alkaline than protruding ones."
)
P(
    "For catalyst design this has two consequences. First, a structured electrode can reach the alkaline regime at a lower current per active area than a flat one; by the proton balance, an array of convex electrodes would alkalinize at about j*/1.44 at pH 2, an estimate that remains to be tested. "
    "Second, because CO_{2} in the catalyst layer is supplied by the gas–liquid interface, structuring the electrode raises the local pH without starving the catalyst of CO_{2}, which is the combination that favours C–C coupling and suppresses HER. "
    "[TO FILL: how the DFT and experimental results confirm or qualify these predictions; which facet and morphology give the best C_{2+} selectivity and carbon utilization.]"
)
P(
    "The continuum model shares the assumptions of the original study"
    + cite("xie2022")
    + ": a uniform reaction rate in the catalyst layer, no migration or electroneutrality and no gas phase. A two-dimensional cut describes an infinitely long ridge rather than an isolated dome or cone, for which current concentration at the apex would be stronger. "
    "Coupling the facet-resolved product distribution from DFT to the continuum model, through the number of OH^{−} released per CO_{2} for each product, is the natural next step to make these predictions quantitative."
)

H("Methods")
H("Continuum model", 2)
P(
    "Each species i (CO_{2}, HCO_{3}^{−}, CO_{3}^{2−}, OH^{−} and H^{+}) obeys a reaction–diffusion equation without migration or convection,"
)
EQ(r"$\dfrac{\partial c_i}{\partial t} = \nabla\cdot\left(D_{e,i}\nabla c_i\right) + R_i,\qquad D_{e,i} = \varepsilon^{3/2}D_i\ \ (\mathrm{CL}),\qquad D_{e,i} = D_i\ \ (\mathrm{diffusion\ layer})$")
P(
    "where R_{i} combines the rates of CO_{2} + H_{2}O ⇌ HCO_{3}^{−} + H^{+}, HCO_{3}^{−} ⇌ CO_{3}^{2−} + H^{+}, CO_{2} + OH^{−} ⇌ HCO_{3}^{−}, HCO_{3}^{−} + OH^{−} ⇌ CO_{3}^{2−} + H_{2}O and H_{2}O ⇌ H^{+} + OH^{−}, with the rate and equilibrium constants and diffusion coefficients of ref. "
    + cite("xie2022").strip("^{}")
    + " (Supplementary Tables 1 and 2). The electrochemical reaction consumes CO_{2} and produces 2 OH^{−} in the CL at a uniform rate"
)
EQ(r"$R_{\mathrm{CO_2RR}} = \dfrac{j\,\varepsilon\,L_s}{F\,n\,A_{\mathrm{cl}}},\qquad n = 2$")
P(
    "where A_{cl} is the area of the CL (A_{cl} = L_{s}L_{cat} for a flat electrode, which recovers the one-dimensional expression). At the gas–liquid interface CO_{2} is fixed at saturation, combining Henry's law with the Sechenov correction for 0.5 M K_{2}SO_{4}"
    + cite("weisenberger1996")
    + " (32.13 mM at 293.15 K and 1 atm), and the other species have zero flux. At the electrolyte boundary all species are at the bulk equilibrium of the chosen pH, which is also the initial condition. Symmetry walls and inert base segments have zero flux."
)
P(
    "The equations were implemented as a custom weak form in KFem, an open-source interface to FEniCSx/DOLFINx"
    + cite("baratta2023")
    + ", with P1 elements for the five concentrations. Geometries were built with Gmsh"
    + cite("geuzaine2009")
    + " (OpenCASCADE kernel) in micrometres and scaled to metres. The one-dimensional problem was solved on a 100 × 0.2 µm strip with a 0.1 µm mesh (4,012 elements); the two-dimensional meshes used 0.1 µm elements within 0.6 µm of the electrode, 0.2 µm within 15 µm of the electrolyte boundary and up to 1 µm elsewhere (24,000–31,000 elements). "
    "Steady state was reached with an adaptive variable-step BDF2 integration from the bulk equilibrium to 120 s (relative tolerance 0.01), with Newton iterations and the MUMPS direct solver"
    + cite("amestoy2001")
    + "; as in ref. "
    + cite("xie2022").strip("^{}")
    + ", concentrations entering the reaction rates were floored at 10^{−15} mol m^{−3}. Results are independent of the mesh (0.1, 0.05 and 0.025 µm in one dimension; mid-domain elements of 1, 0.5 and 0.25 µm in two dimensions; Supplementary Note 3). Surface pH and mid-CL CO_{2} in two dimensions are arc-length-weighted averages along the electrode."
)
H("Density functional theory", 2)
P(
    "Calculations will be performed with Quantum ESPRESSO"
    + cite("giannozzi2017", "giannozzi2020")
    + " coupled to the Environ module, using the RPBE functional"
    + cite("hammer1999")
    + " with D3 dispersion"
    + cite("grimme2010")
    + " and SSSP pseudopotentials"
    + cite("prandini2018")
    + ". Cu(111) and Cu(100) are modelled as p(3×3) slabs with four layers and Cu(110) as a p(3×2) slab with six layers, with the bottom half fixed at the optimized bulk positions and at least 15 Å of implicit solvent between images. "
    "Solvation uses the self-consistent continuum model with the water parametrization"
    + cite("andreussi2012")
    + ", and the 0.5 M K_{2}SO_{4} electrolyte is described by a size-modified Poisson–Boltzmann model with a Stern layer and a two-dimensional Gouy–Chapman–Stern boundary correction"
    + cite("nattino2019")
    + ". The electrode potential is obtained from the Fermi level referenced to the bulk electrolyte, U_{SHE} = −μ_{e}/e − 4.44 V"
    + cite("trasatti1986")
    + ", over a series of slab charges, and free energies at constant potential are obtained from the grand potential. "
    "Proton–electron transfer steps follow the computational hydrogen electrode"
    + cite("norskov2004", "peterson2010")
    + " on the local RHE scale, U_{RHE,loc} = U_{SHE} + 0.059 pH_{loc}, with pH_{loc} from the continuum model; C–C coupling barriers are obtained with the climbing-image nudged elastic band method"
    + cite("henkelman2000")
    + " and interpolated to constant potential"
    + cite("chan2015")
    + ". Full details and input templates are given in Supplementary Note 5. [TO FILL: change to past tense and add numerical settings once the calculations are complete.]"
)
H("Catalyst preparation and characterization", 2)
P("[TO FILL: synthesis of the copper electrodes and of the structured morphologies; SEM, XRD, XPS and any in situ characterization.]")
H("Electrochemical measurements", 2)
P("[TO FILL: flow-cell configuration, gas-diffusion electrode, membrane, electrolyte (K_{2}SO_{4} 0.5 M, pH adjusted with H_{2}SO_{4}), reference electrode and iR correction, product quantification (GC, NMR), definition of single-pass carbon utilization.]")

H("Data availability")
P("The simulation input files (KFem projects for all one- and two-dimensional cases), the post-processed indicators and the data underlying Figs. 1–3 are provided with this paper. [TO FILL: repository and DOI.]")
H("Code availability")
P("KFem is open source (GPL-3.0-or-later). The scripts that build the models and generate the figures are provided with the simulation inputs. [TO FILL: repository URL.]")

H("References")
ref_anchor = doc.add_paragraph(style="Standard")  # lista vem depois, quando a ordem estiver completa

H("Acknowledgements")
P(ack_text or "[TO FILL: acknowledgements.]")
H("Author contributions")
P("[TO FILL]")
H("Competing interests")
P("The authors declare no competing interests.")

# lista de referências na ordem de citação
for k, key in enumerate(ORDER, 1):
    p = doc.add_paragraph(style="Standard")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(3)
    _rich(p, f"{k}. {REFS[key]}", size=10)
    ref_anchor._p.addprevious(p._p)
ref_anchor._p.getparent().remove(ref_anchor._p)

doc.save(str(OUT))
print("salvo:", OUT, f"({len(ORDER)} referências, {_eq[0]} equações)")
