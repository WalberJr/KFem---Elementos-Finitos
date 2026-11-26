# ruff: noqa: E501
"""SI do artigo (Nature Catalysis): notas suplementares do modelo contínuo 1D/2D (completas), DFT
(protocolo) e experimentos ([TO FILL]). Usa o SI.docx do usuário como modelo de estilo.

    PYTHONPATH=<python-docx> python artigo_si.py MODELO_SI.docx DIR_EN SAIDA.docx
"""

from __future__ import annotations

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
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from PIL import Image

TEMPLATE, EN, OUT = (Path(a) for a in sys.argv[1:4])
TMP = Path(tempfile.mkdtemp())
BASE = Path.home() / "kfem-build" / "xie"

D1 = {(r["pH"], r["j"]): r for r in json.loads((EN / "indicadores.json").read_text())}
D2J = json.loads((EN / "indicadores2d.json").read_text())
D2 = {(r["pH"], r["j"], r["shape"]): r for r in D2J["casos"]}
VER2 = D2J["verificacao_1d"]
INT = json.loads((EN / "integrado.json").read_text())
VER = json.loads((BASE / "relatorio_final" / "verificacao.json").read_text())
LAB = {"plano": "Flat", "convexo": "Convex", "conico": "Pointed"}
F_C, D_H, EPS, L = 96485.33, 9.311e-9, 0.6, 100e-6


def jstar(pH):
    return F_C * D_H * 1000 * 10 ** (-pH) / (EPS * L) / 10


def n(v, nd=2):
    return "—" if v is None else f"{v:.{nd}f}"


doc = Document(str(TEMPLATE))
body = doc.element.body
paras = list(doc.paragraphs)
last = paras[8]._element
for el in list(body):
    if el.tag.endswith("sectPr"):
        continue
    if list(body).index(el) > list(body).index(last):
        body.remove(el)
t0 = paras[0]
for r in t0.runs[1:]:
    r._r.getparent().remove(r._r)
t0.runs[0].text = "Supplementary Information for: Interfacial alkalinization and electrode morphology govern CO₂ electroreduction on copper in acidic media"
FONT = "Times New Roman"


def _rich(p, text, bold=False, italic=False, size=None, hl=False):
    if not hl and "[TO FILL" in text:
        for seg in re.split(r"(\[TO FILL[^\]]*\])", text):
            if seg:
                _rich(p, seg, bold, italic, size, hl=seg.startswith("[TO FILL"))
        return
    for tok in re.split(r"(_\{[^}]*\}|\^\{[^}]*\}|\*\*[^*]+\*\*)", text):
        if not tok:
            continue
        sub, sup, b = tok.startswith("_{"), tok.startswith("^{"), tok.startswith("**")
        r = p.add_run(tok[2:-1] if (sub or sup) else tok[2:-2] if b else tok)
        r.font.name = FONT
        r.font.size = Pt(size or 12)
        r.font.subscript, r.font.superscript = sub, sup
        r.bold, r.italic = bold or b, italic
        if hl:
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW


def P(text="", bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=None, after=6):
    p = doc.add_paragraph(style="Normal")
    p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.5
    _rich(p, text, bold, italic, size)
    return p


def H(text, level=1):
    p = doc.add_paragraph(style="Heading 1" if level == 1 else "Normal")
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(12)
    _rich(p, text, bold=True, italic=level == 2, size=12)
    return p


_eq, _fig, _tab = [0], [0], [0]


def EQ(tex, scale=0.75):
    _eq[0] += 1
    img = TMP / f"eq{_eq[0]}.png"
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=15)
    fig.savefig(img, dpi=220, bbox_inches="tight", pad_inches=0.05, facecolor="white")
    plt.close(fig)
    w = Image.open(img).size[0]
    s = doc.sections[0]
    tw = s.page_width.cm - s.left_margin.cm - s.right_margin.cm
    p = doc.add_paragraph(style="Normal")
    p.paragraph_format.tab_stops.add_tab_stop(Cm(tw / 2), WD_TAB_ALIGNMENT.CENTER)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(tw), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run("\t")
    p.add_run().add_picture(str(img), width=Cm(min(w / 220 * 2.54 * scale, tw - 2)))
    r = p.add_run(f"\t(S{_eq[0]})")
    r.font.name = FONT


def FIG(path, caption, width=16.0):
    _fig[0] += 1
    p = doc.add_paragraph(style="Normal")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Cm(width))
    c = doc.add_paragraph(style="Normal")
    c.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    _rich(c, f"**Supplementary Figure {_fig[0]} – **", size=11)
    _rich(c, caption, size=11)
    return _fig[0]


def _shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def TAB(header, rows, caption, widths=None, size=9):
    _tab[0] += 1
    c = doc.add_paragraph(style="Normal")
    c.paragraph_format.keep_with_next = True
    _rich(c, f"**Supplementary Table {_tab[0]} – **", size=11)
    _rich(c, caption, size=11)
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    if widths:
        t.autofit = False
        for k, w in enumerate(widths):
            t.columns[k].width = Cm(w)
    for i, row in enumerate([header, *rows]):
        t.rows[i]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for k, val in enumerate(row):
            cell = t.cell(i, k)
            cell.text = ""
            pp = cell.paragraphs[0]
            pp.paragraph_format.space_after = Pt(0)
            _rich(pp, str(val), size=size, bold=i == 0)
            if i == 0:
                _shade(cell, "D9D9D9")
            if widths:
                cell.width = Cm(widths[k])
    doc.add_paragraph(style="Normal")
    return _tab[0]


# ================================================================= conteúdo
H("Summary")
for s in ("Supplementary Note 1 – Continuum model: equations, parameters and boundary conditions",
          "Supplementary Note 2 – Two-dimensional electrodes: geometry and normalization",
          "Supplementary Note 3 – Numerical implementation and verification",
          "Supplementary Note 4 – One-dimensional results and comparison with ref. 1",
          "Supplementary Note 5 – Two-dimensional results and integrated 1D + 2D analysis",
          "Supplementary Note 6 – DFT protocol (Quantum ESPRESSO + Environ)",
          "Supplementary Note 7 – Experimental details"):
    P(s, after=2)

H("Supplementary Note 1 – Continuum model: equations, parameters and boundary conditions")
P("The model follows Supplementary Note 1 of ref. 1. The domain spans the catalyst layer (CL; 0 ≤ x ≤ L_{cat} = 0.4 µm, porosity ε = 0.6) and the diffusion layer up to the bulk electrolyte at x = L = 100 µm. CO_{2} is reduced to CO in the CL:")
EQ(r"$\mathrm{CO_2 + H_2O + 2e^- \;\rightarrow\; CO + 2OH^-},\qquad R_{\mathrm{CO_2RR}} = \dfrac{j\,\varepsilon}{F\,n\,L_{\mathrm{cat}}}$")
P("The carbonate system is described by five reversible reactions:")
for tex in (r"$r_1 = k_{1f}c_{\mathrm{CO_2}} - k_{1r}c_{\mathrm{H^+}}c_{\mathrm{HCO_3^-}}\qquad (\mathrm{CO_2 + H_2O \rightleftharpoons HCO_3^- + H^+})$",
            r"$r_2 = k_{2f}c_{\mathrm{HCO_3^-}} - k_{2r}c_{\mathrm{H^+}}c_{\mathrm{CO_3^{2-}}}\qquad (\mathrm{HCO_3^- \rightleftharpoons CO_3^{2-} + H^+})$",
            r"$r_3 = k_{3f}c_{\mathrm{CO_2}}c_{\mathrm{OH^-}} - k_{3r}c_{\mathrm{HCO_3^-}}\qquad (\mathrm{CO_2 + OH^- \rightleftharpoons HCO_3^-})$",
            r"$r_4 = k_{4f}c_{\mathrm{HCO_3^-}}c_{\mathrm{OH^-}} - k_{4r}c_{\mathrm{CO_3^{2-}}}\qquad (\mathrm{HCO_3^- + OH^- \rightleftharpoons CO_3^{2-} + H_2O})$",
            r"$r_w = k_{wf} - k_{wr}c_{\mathrm{H^+}}c_{\mathrm{OH^-}}\qquad (\mathrm{H_2O \rightleftharpoons H^+ + OH^-})$"):
    EQ(tex)
P("with k_{1r} = k_{1f}/K_{1}, k_{2r} = k_{2f}/K_{2}, k_{3r} = k_{3f}K_{w}/K_{1}, k_{4r} = k_{4f}K_{w}/K_{2} and k_{wr} = k_{wf}/K_{w}. The source terms are")
EQ(r"$R_{\mathrm{CO_2}} = -r_1 - r_3 - \chi R_{\mathrm{CO_2RR}},\quad R_{\mathrm{HCO_3^-}} = r_1 - r_2 + r_3 - r_4,\quad R_{\mathrm{CO_3^{2-}}} = r_2 + r_4$")
EQ(r"$R_{\mathrm{H^+}} = r_1 + r_2 + r_w,\qquad R_{\mathrm{OH^-}} = -r_3 - r_4 + r_w + 2\chi R_{\mathrm{CO_2RR}}$")
P("where χ = 1 in the CL and 0 elsewhere. Each species obeys")
EQ(r"$\dfrac{\partial c_i}{\partial t} = \nabla\cdot(D_{e,i}\nabla c_i) + R_i,\qquad D_{e,i} = \varepsilon^{3/2}D_i\ (\mathrm{CL}),\quad D_{e,i} = D_i\ (\mathrm{diffusion\ layer})$")
P("At the gas–liquid interface the aqueous species have zero flux and CO_{2} is fixed at saturation (Henry's law with the Sechenov correction):")
EQ(r"$c_{\mathrm{CO_2},0} = K_0\,p_{\mathrm{CO_2}},\qquad \log_{10}\dfrac{c_{\mathrm{CO_2},0}}{c_{\mathrm{CO_2}}} = K_sC_s,\qquad K_s = \sum_{\mathrm{ion}}(h_{\mathrm{ion}} + h_G),\quad h_G = h_{G,0} + h_T(T - 298.15)$")
P("At x = L all species are at the bulk equilibrium: [H^{+}] = 10^{−pH}, [OH^{−}] = K_{w}/[H^{+}], [HCO_{3}^{−}] = K_{1}c_{CO2}/[H^{+}], [CO_{3}^{2−}] = K_{2}[HCO_{3}^{−}]/[H^{+}], with saturated CO_{2}; the same state is the initial condition.")
TAB(["Parameter", "Value", "Parameter", "Value"],
    [["K_{1}", "10^{−5.73} mol L^{−1}", "k_{1f}", "3.71×10^{−2} s^{−1}"],
     ["K_{2}", "10^{−8.58} mol L^{−1}", "k_{2f}", "59.44 s^{−1}"],
     ["K_{w}", "10^{−14} mol^{2} L^{−2}", "k_{3f}", "2.23×10^{3} L mol^{−1} s^{−1}"],
     ["K_{0}", "3.92×10^{−2} mol L^{−1} atm^{−1}", "k_{4f}", "6.0×10^{9} L mol^{−1} s^{−1}"],
     ["T", "293.15 K", "k_{wf}", "2.4×10^{−5} mol L^{−1} s^{−1}"]],
    "Equilibrium and rate constants (ref. 1, Supplementary Table 1). Water activity is taken as unity.", widths=[2.4, 5.2, 2.4, 5.6])
TAB(["Species", "D (cm^{2} s^{−1})", "Quantity", "Value"],
    [["H^{+}", "9.311×10^{−5}", "h_{K+}; h_{SO4 2−}", "0.0922; 0.1117 L mol^{−1}"],
     ["OH^{−}", "5.293×10^{−5}", "h_{G,0}; h_{T}", "−0.0172 L mol^{−1}; −0.000338 L mol^{−1} K^{−1}"],
     ["HCO_{3}^{−}", "1.185×10^{−5}", "C_{s} (K_{2}SO_{4}); p_{CO2}", "0.5 mol L^{−1}; 1 atm"],
     ["CO_{3}^{2−}", "0.923×10^{−5}", "c_{CO2} at saturation", "32.13 mM"],
     ["CO_{2}", "1.910×10^{−5}", "L_{cat}; ε; L", "0.4 µm; 0.6; 100 µm"]],
    "Diffusion coefficients, solubility parameters and geometry (ref. 1, Supplementary Tables 2 and 3).", widths=[2.4, 3.2, 4.4, 5.6])
TAB(["Point", "Reading adopted", "Reason"],
    [["[H_{2}O] in the rates", "water activity = 1", "k_{1f} and k_{wf} are pseudo-first-order; units do not close with 55.5 M"],
     ["Units of k_{wf}", "mol L^{−1} s^{−1}", "consequence of unit water activity"],
     ["Sechenov constant", "K_{s} = Σ(h_{ion} + h_{G}) times C_{s} = 0.5 M", "direct reading of Eq. S19 of ref. 1; gives 32.13 mM"],
     ["Concentration floor (“eps”)", "max(c, 10^{−15} mol m^{−3}) in the rates", "value not reported in ref. 1"],
     ["Temperature", "293.15 K", "temperature of K_{0}"]],
    "Points of ref. 1 that admit more than one reading, and the choice made.", widths=[4.0, 5.4, 6.2])

H("Supplementary Note 2 – Two-dimensional electrodes: geometry and normalization")
R = 20 / math.pi
a = math.sqrt(100 - R**2)
P("The three electrodes have the same active length L_{s} = 20 µm, the two-dimensional analogue of the same active area:")
EQ(r"$\pi R = L_s,\qquad h_{\mathrm{cone}} = R,\qquad 2\sqrt{a^2 + h_{\mathrm{cone}}^2} = L_s$")
P(f"giving R = {R:.3f} µm for the convex electrode and a half-base a = {a:.3f} µm (each side 10 µm) for the pointed electrode. Each case is a periodic cell bounded by symmetry walls; the cell width equals the footprint of the shape: w = 20.00 µm (flat), 2R + 2g = {2 * R + 1.2:.2f} µm (convex, with an inert base g = 0.6 µm on each side that avoids a tangential contact between the arc and the wall) and 2a = {2 * a:.2f} µm (pointed). The electrolyte boundary is 100 µm above the base, as in one dimension. The CL (0.4 µm) follows the surface. The reaction rate uses the real CL area A_{{cl}} of each shape, so that the total current is j·L_{{s}} in all cases:")
EQ(r"$R_{\mathrm{CO_2RR}} = \dfrac{j\,\varepsilon\,L_s}{F\,n\,A_{\mathrm{cl}}},\qquad \int_{\Omega_{\mathrm{cl}}}\dfrac{nF\,R_{\mathrm{CO_2RR}}}{\varepsilon}\,d\Omega = j\,L_s$")
P("The boundary conditions are c_{CO2} = c_{sat} on the gas–liquid interface, bulk equilibrium at y = 100 µm and zero flux on symmetry walls and inert base segments. For the integrated analysis, the current per footprint area is")
EQ(r"$j_{\mathrm{proj}} = \dfrac{j\,L_s}{w}\qquad (L_s/w = 1,\ 1.436,\ 1.297\ \mathrm{for\ flat,\ convex,\ pointed})$")

H("Supplementary Note 3 – Numerical implementation and verification")
P("The equations were implemented as a custom weak form in KFem (FEniCSx/DOLFINx 0.11) with P1 elements for the five concentrations, and solved with Newton iterations (PETSc SNES, backtracking line search, relative tolerance 10^{−10}) and MUMPS. Time integration is BDF1 for the first step and variable-step BDF2 afterwards, with adaptive steps (relative tolerance 0.01), from the bulk equilibrium to 120 s; outputs at 0, 10^{−5}, 10^{−4}, 10^{−3}, 10^{−2}, 0.1, 0.3, 1, 3, 10, 30, 60 and 120 s. Steady state was verified by the change between 60 and 120 s.")
rows = []
for (pH, j), r in sorted(D1.items()):
    s = r.get("stats") or {}
    rows.append([str(pH), str(j), f"{r['dCO2']:.1e}", str(s.get("steps", "—")), str(s.get("rejected", "—")), str(s.get("newton", "—")), n(s.get("wall"), 0)])
TAB(["pH", "j (mA cm^{−2})", "max |ΔCO_{2}| 60→120 s (mM)", "steps", "rejected", "Newton its.", "wall time (s)"], rows,
    "Steady-state criterion and cost of each one-dimensional case (one MPI process per case).", widths=[1.2, 2.2, 3.6, 1.8, 2.0, 2.4, 2.4], size=8.5)
rows = [[f"1D, h = {r['h_um']:g} µm", str(r["cells"]), n(r["pH_s"], 4), n(r["co2_min"], 4), n(r["max_dCO2_vs_fina"], 3)] for r in VER["malha_1d"]]
lab2 = {"padrão (h_meio 1 µm)": "2D flat, standard (mid 1 µm)", "fina no topo (0,1 µm)": "2D flat, fine near electrolyte (0.1 µm)", "h_meio 0,5 µm": "2D flat, mid 0.5 µm", "h_meio 0,25 µm": "2D flat, mid 0.25 µm"}
rows += [[lab2.get(r["caso"], r["caso"]), str(r["cells"]), n(r["pH_s"], 4), n(r["co2_min"], 4), n(r["max_dCO2_vs_1d"], 3)] for r in VER["malha_2d"]]
TAB(["Mesh", "elements", "surface pH", "min CO_{2} (mM)", "max |ΔCO_{2}| (mM)"], rows,
    "Mesh convergence at pH 4 and 500 mA cm^{−2}. One-dimensional differences are relative to the finest mesh (0.025 µm); two-dimensional differences are relative to the finest one-dimensional solution.", widths=[6.2, 2.2, 2.4, 2.6, 2.8])
P(f"The flat electrode in two dimensions reproduces the one-dimensional solution: the largest CO_{{2}} difference is {max(v['max_dCO2_mM'] for v in VER2.values()):.2f} mM and the surface pH agrees to 10^{{−4}} at pH 2 / 200, pH 2 / 500 and pH 4 / 500 (Supplementary Fig. 1). For the convex and pointed electrodes, refining the mesh near the electrolyte leaves the arc-averaged surface pH unchanged (difference < 10^{{−5}}) and only reduces the small negative H^{{+}} values at the acid–base front, an artefact of primitive variables shared with ref. 1.")
FIG(EN / "fig2d_verificacao_1d.png", "Flat electrode in two dimensions (points: all mesh nodes) against the one-dimensional solution (lines) for CO_{2} and pH.")

H("Supplementary Note 4 – One-dimensional results and comparison with ref. 1")
FIG(EN / "fig_co2.png", "Steady-state CO_{2} profiles for bulk pH 0–4 and 100–750 mA cm^{−2}.")
FIG(EN / "fig_ph.png", "Steady-state pH profiles for bulk pH 0–4 and 100–750 mA cm^{−2}. Gaps near the acid–base front correspond to nodes with [H^{+}] ≤ 0 (primitive-variable artefact, widths ≤ 0.5 µm).")
FIG(EN / "fig_transiente.png", "Transient formation of the steady state at pH 2 and 500 mA cm^{−2}, starting from the bulk equilibrium.")
TAB(["bulk pH", "j* (mA cm^{−2})"], [[str(p), n(jstar(p), 2 if jstar(p) < 10 else 1)] for p in range(5)],
    "Alkalinization threshold from the proton balance, j* = F D_{H} c_{H,b}/(ε L).", widths=[4, 4])
from figuras import PAPER  # noqa: E402

rows = []
for (pH, j), p in sorted(PAPER.items()):
    r = D1.get((pH, j))
    rows.append([str(pH), str(j), n(r["co2_min"], 1) if r else "—", n(p.get("co2_min"), 0), n(r["pH_s"], 1) if r else "—", n(p.get("pH_s"), 1),
                 n(r["front"], 1) if r and r["front"] is not None else "—", n(p.get("front"), 0)])
TAB(["pH", "j", "min CO_{2}, this work", "ref. 1", "surface pH, this work", "ref. 1", "front (µm), this work", "ref. 1"], rows,
    "Steady-state indicators of this work and values read from Supplementary Figs. 2 and 3 of ref. 1 (CO_{2} in mM; front = first position with pH < 6). Values from ref. 1 are read from figures (±1 mM, ±0.3 pH, ±3 µm).", widths=[1.0, 1.1, 2.4, 1.6, 2.4, 1.6, 2.4, 1.6], size=8.5)
FIG(EN / "fig_comparacao.png", "Minimum CO_{2} versus current density (this work: lines; ref. 1: circles) and surface pH at bulk pH 2.")
FIG(EN / "fig_hipotese.png", "pH 2 with the current densities divided by 10 (10–75 mA cm^{−2}), testing whether a factor of 10 in the current scale reconciles the threshold of ref. 1. It reproduces the pH threshold but underestimates CO_{2} depletion.")

H("Supplementary Note 5 – Two-dimensional results and integrated 1D + 2D analysis")
for pH, j in ((2, 500), (2, 200), (4, 500)):
    FIG(EN / f"fig2d_mapa_pH{pH}_j{j}.png", f"CO_{{2}} and pH over the full domain for the three electrodes at pH {pH} and {j} mA cm^{{−2}}. The white line marks pH = 6.")
rows = []
for pH, j in ((2, 500), (2, 200), (4, 500)):
    for s in ("plano", "convexo", "conico"):
        r = D2[(pH, j, s)]
        rows.append([str(pH), str(j), LAB[s], n(r["pH_el_mean"]), f"{n(r['pH_el_min'])}–{n(r['pH_el_max'])}", n(r["co2_cl_mean"], 1), n(r["co2_min"], 3), n(r["y_front"], 1)])
TAB(["pH", "j", "electrode", "surface pH (mean)", "range", "mid-CL CO_{2} (mM)", "min CO_{2} (mM)", "front (µm)"], rows,
    "Two-dimensional steady-state indicators. Means are arc-length weighted along the electrode; the front is the lowest height with pH < 6.", widths=[1.0, 1.1, 2.2, 2.4, 2.6, 2.4, 2.4, 1.9], size=9)
rows = []
for r in INT:
    phi = "—" if r["shape"] == "plano" else n((r["pH_2d_mean"] - r["pH_1d_nominal"]) / (r["pH_1d_proj"] - r["pH_1d_nominal"]))
    rows.append([str(r["pH"]), str(r["j"]), LAB[r["shape"]], n(r["j_proj"], 1), n(r["pH_2d_mean"], 3), n(r["pH_1d_nominal"], 3), n(r["pH_1d_proj"], 3), phi,
                 "—" if r["front_2d"] is None else f"{n(r['front_2d'], 1)} / {n(r['front_1d_proj'], 1)}", f"{n(r['co2_cl_2d_mean'], 1)} / {n(r['co2_cl_1d_proj'], 1)}"])
TAB(["pH", "j", "electrode", "j_{proj}", "pH 2D", "pH 1D(j)", "pH 1D(j_{proj})", "φ", "front 2D / 1D(j_{proj})", "mid-CL CO_{2} 2D / 1D(j_{proj})"], rows,
    "Integrated analysis. φ = [pH_{2D} − pH_{1D}(j)]/[pH_{1D}(j_{proj}) − pH_{1D}(j)] is the fraction of the pH gain predicted by current concentration that the two-dimensional electrode recovers (currents in mA cm^{−2}, positions in µm, CO_{2} in mM).",
    widths=[0.9, 0.9, 1.8, 1.4, 1.5, 1.5, 1.7, 1.1, 2.6, 2.6], size=8)

H("Supplementary Note 6 – DFT protocol (Quantum ESPRESSO + Environ)")
P("[TO FILL: change to past tense and report the converged values once the calculations are complete.]")
TAB(["Item", "Setting"],
    [["Code", "Quantum ESPRESSO 7.x (pw.x, neb.x, ph.x) with Environ"],
     ["Functional", "RPBE + D3 (vdw_corr = 'grimme-d3'); BEEF-vdW as a check"],
     ["Pseudopotentials / cutoffs", "SSSP; largest recommended cutoff among Cu, C, O, H, tested ±10 Ry"],
     ["Slabs", "Cu(111), Cu(100): p(3×3), 4 layers (2 fixed); Cu(110): p(3×2), 6 layers (3 fixed)"],
     ["k-points", "Monkhorst–Pack, ≤ 0.15 Å^{−1} in plane (5×5×1; 4×6×1 for Cu(110))"],
     ["Smearing / SCF", "Marzari–Vanderbilt 0.01 Ry; conv_thr 10^{−8} Ry; local-TF mixing, β = 0.2"],
     ["Relaxation", "BFGS; forces < 10^{−3} Ry bohr^{−1}"],
     ["Solvent", "SCCS, environ_type = 'water' (ε_{0} = 78.3, ρ_{max} = 0.005, ρ_{min} = 0.0001 a.u.)"],
     ["Electrolyte", "K^{+} (1.0 M) and SO_{4}^{2−} (0.5 M), size-modified Poisson–Boltzmann, Stern plane at 2–4 Å (tested)"],
     ["Boundary correction", "pbc_correction = 'gcs', pbc_dim = 2, pbc_axis = 3"],
     ["Potential", "slab charge q = −0.6 … +0.2 e; U_{SHE} = −μ_{e}/e − 4.44 V; grand potential Ω(U) = E(q) + (q/e)μ_{e}"],
     ["pH scale", "U_{RHE,loc} = U_{SHE} + 0.059 pH_{loc}, pH_{loc} from the continuum model"],
     ["Barriers", "CI-NEB, 7–9 images, three or more charges per state, interpolated to constant potential"]],
    "DFT settings (Environ keyword names to be checked against the installed version).", widths=[4.2, 11.8], size=9)
P("Intermediates: *H, *OH, *CO_{2}, *COOH, *OCHO, *CO, *CHO, *COH, *OCCO and *OCCOH on all high-symmetry sites of each facet (1/9 ML on Cu(111) and Cu(100), 1/6 ML on Cu(110)). Free energies include zero-point energy, heat capacity and entropy from harmonic frequencies; proton–electron steps follow the computational hydrogen electrode on the local RHE scale. The CO_{2} and OH^{−} chemical potentials use the local concentrations from the continuum model, μ = μ° + k_{B}T ln(c/c°).")
P("[TO FILL: Supplementary Figures and Tables with converged settings, adsorption geometries, free-energy diagrams and NEB profiles.]")

H("Supplementary Note 7 – Experimental details")
P("[TO FILL: synthesis, characterization (SEM, XRD, XPS), electrochemical set-up, product quantification and carbon-utilization calculations, with supporting figures and tables.]")

H("Supplementary References")
P("1. Xie, Y. et al. High carbon utilization in CO2 reduction to multi-carbon products in acidic media. Nat. Catal. 5, 564–570 (2022).", size=10)

doc.save(str(OUT))
print("salvo:", OUT, f"({_fig[0]} figuras, {_tab[0]} tabelas, {_eq[0]} equações)")
