# ruff: noqa: E501
"""Metodologia (DOCX): cálculos DFT com Quantum ESPRESSO + Environ em Cu(111), Cu(110) e Cu(100)
para corroborar o modelo de transporte e reação (1D/2D) da CO2RR em meio ácido.

    PYTHONPATH=<python-docx> python qe_metodologia.py SAIDA.docx [DIR_FIGURAS]

DIR_FIGURAS (opcional) é a pasta do relatório do KFem: se tiver indicadores.json e
indicadores2d.json, os valores de pH local e CO2 na camada catalítica entram no texto.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

OUT = Path(sys.argv[1])
FIG = Path(sys.argv[2]) if len(sys.argv) > 2 else None
TMP = Path(tempfile.mkdtemp())
LILAS, VERDE = RGBColor(0x5B, 0x3F, 0x86), RGBColor(0x1F, 0x5B, 0x3A)

# valores do contínuo (KFem) usados como entradas, se disponíveis
CONT = {}
if FIG and (FIG / "indicadores2d.json").exists():
    for r in json.loads((FIG / "indicadores2d.json").read_text())["casos"]:
        CONT[(r["pH"], r["j"], r["shape"])] = r

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.3)
sec.top_margin = sec.bottom_margin = Cm(2.2)
TEXT_W = 21.0 - 4.6
st = doc.styles
st["Normal"].font.name = "Calibri"
st["Normal"].font.size = Pt(11)
st["Normal"].paragraph_format.space_after = Pt(6)
st["Normal"].paragraph_format.line_spacing = 1.15
for name, size, color in (("Title", 21, LILAS), ("Heading 1", 15, LILAS), ("Heading 2", 12.5, VERDE), ("Heading 3", 11.5, VERDE)):
    s = st[name]
    s.font.name, s.font.size, s.font.bold = "Calibri", Pt(size), True
    s.font.color.rgb = color
    s.paragraph_format.keep_with_next = True
    s.paragraph_format.space_before = Pt(14 if name != "Title" else 0)
    s.paragraph_format.space_after = Pt(6)
    rpr = s.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(a), "Calibri")
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
    r = fp.add_run()
    if kind:
        el = OxmlElement("w:fldChar")
        el.set(qn("w:fldCharType"), kind)
    else:
        el = OxmlElement("w:instrText")
        el.set(qn("xml:space"), "preserve")
        el.text = text
    r._r.append(el)

_eq, _tab, _fig = [0], [0], [0]


def _rich(p, text: str, italic: bool = False, size=None, bold=False):
    import re

    for tok in re.split(r"(_\{[^}]*\}|\^\{[^}]*\})", text):
        if not tok:
            continue
        r = p.add_run(tok[2:-1] if tok[:2] in ("_{", "^{") else tok)
        r.font.subscript = tok.startswith("_{")
        r.font.superscript = tok.startswith("^{")
        r.italic, r.bold = italic, bold
        if size:
            r.font.size = Pt(size)


def para(text: str = "", bold_prefix: str | None = None, italic=False, size=None):
    p = doc.add_paragraph()
    if bold_prefix:
        _rich(p, bold_prefix, bold=True)
    _rich(p, text, italic=italic, size=size)
    return p


def bullet(text: str, bold_prefix: str | None = None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        _rich(p, bold_prefix, bold=True)
    _rich(p, text)
    p.paragraph_format.space_after = Pt(3)


def numbered(text: str):
    p = doc.add_paragraph(style="List Number")
    _rich(p, text)
    p.paragraph_format.space_after = Pt(3)


def equation(tex: str, scale: float = 0.8) -> int:
    _eq[0] += 1
    img = TMP / f"eq{_eq[0]}.png"
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=15)
    fig.savefig(img, dpi=220, bbox_inches="tight", pad_inches=0.06, facecolor="white")
    plt.close(fig)
    w_px, _ = Image.open(img).size
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.tab_stops.add_tab_stop(Cm(TEXT_W / 2), WD_TAB_ALIGNMENT.CENTER)
    pf.tab_stops.add_tab_stop(Cm(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
    p.add_run("\t")
    p.add_run().add_picture(str(img), width=Cm(min(w_px / 220 * 2.54 * scale, TEXT_W - 2.0)))
    p.add_run(f"\t({_eq[0]})")
    return _eq[0]


def _shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def table(header, rows, caption, widths=None, size=9.5) -> int:
    _tab[0] += 1
    c = doc.add_paragraph()
    c.add_run(f"Tabela {_tab[0]}. ").bold = True
    _rich(c, caption, size=9.5)
    c.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate([header, *rows]):
        for k, val in enumerate(row):
            cell = t.cell(i, k)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            _rich(p, str(val), size=size)
            if i == 0:
                for r in p.runs:
                    r.bold = True
                    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                _shade(cell, "5B3F86")
            elif i % 2 == 0:
                _shade(cell, "F1ECF7")
            if widths:
                cell.width = Cm(widths[k])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return _tab[0]


def figure(path: Path, caption: str, width_cm: float = TEXT_W) -> int:
    _fig[0] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    c = doc.add_paragraph()
    c.add_run(f"Figura {_fig[0]}. ").bold = True
    _rich(c, caption, size=9.5)
    return _fig[0]


def code(text: str):
    for line in text.strip("\n").splitlines():
        p = doc.add_paragraph()
        r = p.add_run(line if line else " ")
        r.font.name = "DejaVu Sans Mono"
        r.font.size = Pt(8)
        pf = p.paragraph_format
        pf.left_indent = Cm(0.5)
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        pf.line_spacing = 1.0
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def fv(v, nd=2):
    return "n/d" if v is None else f"{v:.{nd}f}".replace(".", ",")


def workflow_figure(path: Path) -> None:
    """Diagrama do acoplamento contínuo (KFem) ↔ atomístico (QE + Environ)."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    boxes = {
        "kfem": (0.2, 2.9, 3.4, 2.0, "#E9E1F4", "KFem (contínuo, 1D/2D)\n• pH local na superfície\n• CO$_2$ na camada catalítica\n• OH$^-$, HCO$_3^-$, CO$_3^{2-}$\n• efeito da forma do eletrodo"),
        "ponte": (4.0, 2.9, 3.0, 2.0, "#F6E7B8", "Ponte termodinâmica\n• escala RHE local:\n  U$_{RHE}$ = U$_{SHE}$ + 0,059 pH$_{loc}$\n• μ$_{CO_2}$ = μ° + k$_B$T ln(c/c°)\n• força iônica do eletrólito"),
        "qe": (7.4, 2.9, 3.4, 2.0, "#DCEBF7", "QE + Environ (atomístico)\n• Cu(111), Cu(100), Cu(110)\n• solvente implícito + eletrólito\n• carga/potencial do eletrodo\n• ΔG e barreiras por faceta"),
        "volta": (2.6, 0.3, 5.8, 1.7, "#E3F1E7", "De volta ao contínuo\n• OH$^-$ por CO$_2$ conforme o produto (CO: 2; C$_2$H$_4$: 6)\n• lei de taxa por faceta j(U, pH$_{loc}$, c$_{CO_2}$)\n• ponderação pelas facetas expostas em cada forma"),
    }
    for x, y, w, h, c, txt in boxes.values():
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05", facecolor=c, edgecolor="#3A3640"))
        ax.text(x + 0.12, y + h - 0.15, txt, va="top", ha="left", fontsize=9)
    for p0, p1 in (((3.65, 3.9), (3.95, 3.9)), ((7.05, 3.9), (7.35, 3.9)), ((9.1, 2.85), (8.2, 1.6)), ((2.8, 1.6), (1.9, 2.85))):
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14, color="#3A3640", lw=1.4))
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


# ================================================================= documento
t = doc.add_paragraph(style="Title")
t.add_run("Metodologia: cálculos DFT com Quantum ESPRESSO + Environ em Cu(111), Cu(110) e Cu(100) para corroborar o modelo contínuo da CO₂RR em meio ácido")
para("Plano de cálculo, parâmetros, entradas e ligação com os resultados 1D/2D do KFem (Xie et al., 2022)", italic=True)
para("Documento de metodologia — 25 de novembro de 2026", size=9.5)

doc.add_heading("1. Objetivo", level=1)
para(
    "O modelo contínuo do KFem (1D e 2D) descreve o transporte e as reações homogêneas do sistema carbonato junto ao eletrodo, mas trata "
    "a reação de eletrodo de forma agregada: uma taxa uniforme na camada catalítica, com 2 OH^{-} produzidos por CO_{2} (produto CO) e sem "
    "dependência do potencial nem da faceta do cobre. Ele prevê, por outro lado, as condições locais em que o catalisador trabalha:"
)
bullet("pH local de 12–13 na superfície com eletrólito de pH 2–4, desde que a corrente passe do limiar de alcalinização;")
bullet("CO_{2} na camada catalítica de 27–30 mM, um pouco abaixo da saturação (32 mM), porque a CL fica colada à interface gás-líquido; o esgotamento quase total do CO_{2} ocorre mais longe, num vale a 10–30 µm da superfície, onde o OH^{-} o converte em carbonato;")
bullet("diferenças locais de pH e de CO_{2} ao longo de eletrodos curvos (pés mais alcalinos que o topo).")
para(
    "Os cálculos de primeiros princípios propostos aqui têm três objetivos: (i) verificar se, nessas condições locais, as facetas de "
    "cobre de baixo índice levam aos produtos e às taxas implícitos no modelo contínuo; (ii) obter, por faceta, as energias livres e "
    "as barreiras das etapas-chave em função do potencial e do pH local; (iii) devolver ao contínuo uma lei de taxa e uma "
    "estequiometria de OH^{-} por faceta, que substituam a taxa uniforme."
)
fw = TMP / "fluxo.png"
workflow_figure(fw)
n_fl = figure(fw, "Acoplamento entre o modelo contínuo (KFem) e os cálculos atomísticos (Quantum ESPRESSO + Environ).")
para(f"A Figura {n_fl} resume o acoplamento. As seções 2–7 descrevem os cálculos; a seção 8 descreve a ligação com o KFem; a seção 9 traz as entradas.")

doc.add_heading("2. Programas e versões", level=1)
table(
    ["Programa", "Uso", "Observação"],
    [
        ["Quantum ESPRESSO (pw.x, neb.x, ph.x, pp.x)", "DFT de ondas planas, relaxações, NEB, frequências, densidades e potenciais", "versão 7.x; compilado com o Environ"],
        ["Environ", "solvatação implícita (SCCS), eletrólito (Poisson–Boltzmann modificado), correções de contorno 2D", "versão compatível com o QE instalado; ativado com pw.x --environ"],
        ["ASE", "construção das lâminas, sítios de adsorção, análise vibracional e termoquímica", "livre (LGPL)"],
        ["Pseudopotenciais SSSP", "Cu, C, O, H (e K, para cátion explícito)", "biblioteca SSSP (efficiency ou precision), com cortes recomendados"],
    ],
    "Programas. Todos são livres.",
    widths=[4.8, 6.6, 5.0],
    size=9,
)
para(
    "Os nomes das palavras-chave do Environ citados neste documento devem ser conferidos na documentação da versão instalada, pois "
    "algumas mudaram entre versões. As entradas da Seção 9 são modelos para adaptar, não arquivos testados."
)

doc.add_heading("3. Sistemas", level=1)
doc.add_heading("3.1 Cobre maciço", level=2)
para(
    "O parâmetro de rede do Cu cfc é otimizado com o mesmo funcional, corte e pseudopotencial usados nas lâminas (ajuste de "
    "Birch–Murnaghan a 7–9 volumes, malha de pontos k de 16×16×16 ou mais). O valor experimental, 3,615 Å, serve de referência; GGA "
    "costuma superestimá-lo em cerca de 1%. Todas as lâminas usam o parâmetro otimizado, não o experimental."
)
doc.add_heading("3.2 Lâminas", level=2)
table(
    ["Faceta", "Supercélula", "Camadas (fixas)", "Sítios de adsorção", "Pontos k (sugestão)"],
    [
        ["Cu(111)", "p(3×3), 9 átomos por camada", "4 (2 de baixo)", "topo, ponte, cavidade fcc e hcp", "5×5×1"],
        ["Cu(100)", "p(3×3), 9 átomos por camada", "4 (2 de baixo)", "topo, ponte, cavidade de 4", "5×5×1"],
        ["Cu(110)", "p(3×2), 6 átomos por camada", "6 (3 de baixo)", "topo, ponte curta, ponte longa, cavidade", "4×6×1"],
    ],
    "Modelos de lâmina. A cobertura de um adsorbato por supercélula é 1/9 ML em (111) e (100) e 1/6 ML em (110).",
    widths=[2.2, 4.0, 2.8, 4.4, 3.0],
    size=9,
)
bullet("vácuo de pelo menos 15 Å entre as imagens periódicas; com o Environ, o vácuo é ocupado pelo solvente implícito e deve ser testado (15–20 Å);")
bullet("as camadas de baixo ficam fixas nas posições do maciço; as de cima e os adsorbatos relaxam;")
bullet("a convergência em número de camadas é conferida pela energia de superfície e pela energia de adsorção do CO (variação < 0,03 eV ao acrescentar uma camada);")
bullet("as lâminas são simétricas em espessura, mas os adsorbatos ficam só na face de cima; o dipolo resultante é tratado pela correção de contorno do Environ (Seção 5.3), e não se combina com tefield/dipfield do pw.x.")

doc.add_heading("4. Parâmetros de DFT", level=1)
table(
    ["Parâmetro", "Valor proposto", "Justificativa"],
    [
        ["Funcional", "RPBE + D3 (vdw_corr = 'grimme-d3'); BEEF-vdW como verificação", "RPBE corrige a superligação do CO do PBE; D3 inclui dispersão; BEEF-vdW dá barras de erro por conjunto"],
        ["Spin", "não polarizado", "Cu metálico, sem momento; conferir para O e OH isolados"],
        ["Corte (ecutwfc / ecutrho)", "o maior recomendado pelo SSSP entre Cu, C, O, H; testar ±10 Ry", "convergência de ΔE de adsorção < 0,01 eV"],
        ["Ocupações", "smearing Marzari–Vanderbilt, degauss = 0,01 Ry", "metal; extrapolar a energia para σ → 0"],
        ["SCF", "conv_thr = 10^{-8} Ry por célula; mixing_mode = 'local-TF', mixing_beta = 0,2", "lâminas com vácuo e solvente convergem melhor com local-TF"],
        ["Relaxação", "BFGS; forc_conv_thr = 10^{-3} Ry/bohr (≈ 0,026 eV/Å); etot_conv_thr = 10^{-5} Ry", "suficiente para ΔG com precisão de ~0,02 eV"],
        ["Pontos k", "Monkhorst–Pack com espaçamento ≤ 0,15 Å^{-1} no plano; 1 na normal", "ver Tabela 2"],
    ],
    "Parâmetros de DFT.",
    widths=[3.4, 6.2, 6.8],
    size=9,
)

doc.add_heading("5. Solvatação e eletrólito implícitos (Environ)", level=1)
doc.add_heading("5.1 Dielétrico contínuo autoconsistente (SCCS)", level=2)
para(
    "O Environ resolve a equação de Poisson generalizada com uma permissividade que depende da densidade eletrônica do soluto. A "
    "cavidade é definida pela própria densidade (SCCS), sem raios atômicos ajustáveis:"
)
equation(r"$\nabla\cdot\left[\varepsilon(\mathbf{r})\,\nabla\phi(\mathbf{r})\right] = -4\pi\,\rho_{\mathrm{sol}}(\mathbf{r})$")
equation(r"$\varepsilon(\rho) = \exp\!\left[\,\zeta(\rho)\,\ln\varepsilon_0\right],\qquad \zeta(\rho) = \dfrac{1}{2\pi}\left[2\pi\,\dfrac{\ln\rho_{\max} - \ln\rho}{\ln\rho_{\max} - \ln\rho_{\min}} - \sin\!\left(2\pi\,\dfrac{\ln\rho_{\max} - \ln\rho}{\ln\rho_{\max} - \ln\rho_{\min}}\right)\right]$", scale=0.7)
para(
    "com ε = 1 dentro do soluto (ρ > ρ_{max}) e ε = ε_{0} = 78,3 no solvente (ρ < ρ_{min}). Os termos não eletrostáticos (cavitação, "
    "repulsão, dispersão) entram pela tensão superficial e pela pressão externa efetivas:"
)
equation(r"$G_{\mathrm{sol}} = G_{\mathrm{el}} + (\alpha + \gamma)\,S(\rho) + \beta\,V(\rho)$")
para(
    "Usa-se a parametrização de água do Environ (environ_type = 'water': ε_{0} = 78,3, ρ_{max} = 0,005 e ρ_{min} = 0,0001 u.a., com os "
    "valores de α + γ e β dessa parametrização). Para conferir o efeito do modelo de cavidade, a parametrização 'water-cation' pode ser "
    "usada nos estados carregados negativamente."
)
doc.add_heading("5.2 Eletrólito: Poisson–Boltzmann modificado e camada de Stern", level=2)
para(
    "O eletrólito do artigo e do KFem é K_{2}SO_{4} 0,5 M (força iônica de 1,5 M), mais o H^{+} do pH do seio. No Environ, ele entra como "
    "duas espécies iônicas contínuas (K^{+}, z = +1, 1,0 M; SO_{4}^{2-}, z = −2, 0,5 M), com distribuição de Boltzmann modificada "
    "pelo tamanho finito dos íons e excluídas de uma camada de Stern junto à superfície:"
)
equation(r"$\nabla\cdot\varepsilon\nabla\phi = -4\pi\left[\rho_{\mathrm{sol}} + \gamma(\mathbf{r})\sum_i z_i e\, c_i^{\infty}\, \dfrac{e^{-z_i e\phi/k_BT}}{1 - \sum_k \dfrac{c_k^{\infty}}{c_{\max}}\left(1 - e^{-z_k e\phi/k_BT}\right)}\right]$", scale=0.72)
para(
    "γ(r) é a função que liga o eletrólito fora da camada de Stern e c_{max} é a concentração máxima de empacotamento. Duas escolhas "
    "estão disponíveis: (a) eletrólito definido sobre a densidade do soluto (como a cavidade dielétrica) ou (b) um plano de Stern a uma "
    "distância fixa da superfície (electrolyte_mode = 'system', com electrolyte_distance e electrolyte_spread). Recomenda-se (b) para "
    "lâminas metálicas, com distância de Stern testada entre 2 e 4 Å."
)
para(
    "Os íons OH^{-}, HCO_{3}^{-} e CO_{3}^{2-} que o KFem prevê na superfície (dezenas de mM a mais de 1 M de OH^{-} quando o pH local é "
    "12–13) podem ser acrescentados como espécies do eletrólito, com as concentrações locais do contínuo, para avaliar se mudam a "
    "capacitância e o potencial de carga zero."
)
doc.add_heading("5.3 Condições de contorno da lâmina", level=2)
para(
    "A célula é periódica no plano e não periódica na normal (z). A correção de contorno do Environ remove a interação espúria entre "
    "imagens e define a referência do potencial:"
)
bullet("pbc_correction = 'parabolic' (pbc_dim = 2, pbc_axis = 3): para lâminas neutras ou carregadas sem eletrólito;")
bullet("pbc_correction = 'gcs' (Gouy–Chapman–Stern): com eletrólito, resolve analiticamente a parte difusa da dupla camada; o potencial vai a zero longe da superfície, o que fixa a referência da energia de Fermi.")

doc.add_heading("6. Potencial do eletrodo", level=1)
para(
    "A DFT trabalha com número fixo de elétrons. O potencial do eletrodo entra variando a carga da lâmina (tot_charge), compensada "
    "pelo eletrólito implícito, e lendo a energia de Fermi em relação ao potencial do seio do eletrólito:"
)
equation(r"$U_{\mathrm{SHE}} = \dfrac{-\,\mu_e}{e} - \Phi_{\mathrm{SHE}},\qquad \mu_e = E_F - e\,\phi(\infty),\qquad \Phi_{\mathrm{SHE}} \approx 4{,}44\ \mathrm{V}$")
para(
    "Para cada faceta e cada estado (superfície limpa, adsorbatos, estados de transição), calcula-se uma série de cargas, tipicamente "
    "q = −0,6 … +0,2 e por supercélula, e ajusta-se a energia ao potencial. A grandeza a comparar a potencial constante é o grande "
    "potencial eletrônico:"
)
equation(r"$\Omega(U) = E(q) + \dfrac{q}{e}\,\mu_e(q)\ \ \Rightarrow\ \ \Omega(U) \approx \Omega(U_{\mathrm{pzc}}) - \dfrac{1}{2}\,C\,A\,(U - U_{\mathrm{pzc}})^2$")
para(
    "onde U_{pzc} é o potencial de carga zero e C a capacitância por área. O U_{pzc} de cada faceta (lâmina limpa, q = 0) e a "
    "capacitância são as primeiras verificações do modelo de interface: as funções trabalho no vácuo devem ficar perto dos valores "
    "experimentais (Cu(111) ≈ 4,9 eV, Cu(100) ≈ 4,6 eV, Cu(110) ≈ 4,5 eV), e a capacitância de dupla camada na faixa de 10–30 µF cm^{-2}."
)
para(
    "A conversão para a escala do eletrodo reversível de hidrogênio usa o pH local na superfície, e não o pH do seio. Esse é o ponto "
    "central da ligação com o contínuo:"
)
equation(r"$U_{\mathrm{RHE,loc}} = U_{\mathrm{SHE}} + \dfrac{k_BT\ln 10}{e}\,\mathrm{pH_{loc}}\qquad (0{,}059\ \mathrm{V\ por\ unidade\ de\ pH\ a\ 298\ K})$")
p2 = CONT.get((2, 500, "plano"), {}).get("pH_el_mean")
if p2:
    para(
        f"Com pH 2 no seio e pH local de {fv(p2)} (KFem, eletrodo plano a 500 mA cm^{{-2}}), a mesma escala SHE corresponde a uma escala "
        f"RHE local deslocada de cerca de {fv(0.0592 * (p2 - 2), 2)} V em relação à escala RHE do seio."
    )

doc.add_heading("7. Intermediários, energias livres e barreiras", level=1)
doc.add_heading("7.1 Intermediários", level=2)
table(
    ["Grupo", "Espécies", "Por quê"],
    [
        ["Competição", "H*, OH*", "evolução de H_{2} (HER) e ocupação de sítios por OH em pH local alto"],
        ["Ativação do CO_{2}", "CO_{2}* (ligado e fisissorvido), COOH*, OCHO*", "primeira etapa; OCHO* leva a formiato"],
        ["Via do CO", "CO*", "intermediário comum; a cobertura de CO decide a seletividade"],
        ["Hidrogenação do CO", "CHO*, COH*", "rota para CH_{4} (favorecida em (111))"],
        ["Acoplamento C–C", "OCCO*, OCCOH*, CO* + CO*", "rota para C_{2+} (favorecida em (100))"],
        ["Espécies do eletrólito", "HCO_{3}^{-}*, CO_{3}^{2-}* (opcional), K^{+} explícito", "adsorção de carbonato em pH local alto; efeito do cátion"],
    ],
    "Intermediários por faceta. Cada um em todos os sítios de alta simetria da Tabela 2; o de menor energia entra na análise.",
    widths=[3.4, 5.6, 7.4],
    size=9,
)
doc.add_heading("7.2 Energias livres", level=2)
para("A energia livre de adsorção combina a energia eletrônica (com solvente e potencial) com as correções térmicas:")
equation(r"$\Delta G = \Delta E_{\mathrm{DFT+Environ}} + \Delta E_{\mathrm{ZPE}} + \int_0^T \Delta C_p\, dT - T\,\Delta S$")
para(
    "Para os adsorbatos, ZPE, C_{p} e S vêm da aproximação harmônica, com frequências por diferenças finitas (só o adsorbato e a "
    "primeira camada de Cu se movem; ph.x em Γ ou ASE). Frequências abaixo de 50 cm^{-1} são elevadas a 50 cm^{-1}. As moléculas de "
    "referência (CO_{2}, CO, H_{2}, H_{2}O, C_{2}H_{4}) usam a aproximação de gás ideal; os erros sistemáticos conhecidos do GGA para "
    "moléculas com ligação C=O devem ser corrigidos por um esquema da literatura, documentado junto aos resultados."
)
para(
    "As etapas de transferência acoplada próton-elétron seguem o eletrodo computacional de hidrogênio, com o potencial na escala RHE "
    "local (Eq. da Seção 6):"
)
equation(r"$\Delta G_k(U) = \Delta G_k(0) + e\,U_{\mathrm{RHE,loc}}\qquad U_L = -\max_k \dfrac{\Delta G_k(0)}{e}$")
para(
    "As etapas sem transferência de elétron (adsorção de CO_{2}, acoplamento CO–CO) não dependem de U_{RHE} pelo eletrodo "
    "computacional de hidrogênio, mas dependem do campo interfacial, ou seja, de U_{SHE}. É nessas etapas que o pH local muda a "
    "seletividade: com o mesmo U_{RHE}, um pH local maior significa um U_{SHE} mais negativo e um campo mais forte."
)
para("As concentrações locais do contínuo entram no potencial químico das espécies em solução:")
equation(r"$\mu_{\mathrm{CO_2(aq)}} = \mu^{\circ}_{\mathrm{CO_2(aq)}} + k_BT\ln\dfrac{c_{\mathrm{CO_2,loc}}}{c^{\circ}},\qquad \mu_{\mathrm{OH^-}} = \mu^{\circ}_{\mathrm{OH^-}} + k_BT\ln\dfrac{c_{\mathrm{OH^-,loc}}}{c^{\circ}}$")
rows = []
for (pH, j) in ((2, 500), (2, 200), (4, 500)):
    for s, lab in (("plano", "plano"), ("convexo", "convexo"), ("conico", "pontiagudo")):
        r = CONT.get((pH, j, s))
        if r:
            rows.append([str(pH), str(j), lab, f"{fv(r['pH_el_mean'])} ({fv(r['pH_el_min'])}–{fv(r['pH_el_max'])})", fv(r.get("co2_cl_mean"), 1)])
n_cond = None
if rows:
    n_cond = table(["pH do seio", "j (mA cm^{-2})", "forma", "pH local (faixa)", "CO_{2} na CL (mM)"], rows,
          "Condições locais previstas pelo KFem (2D, estado estacionário), usadas como entradas dos cálculos.", widths=[2.4, 2.8, 2.8, 4.2, 3.6], size=9)
doc.add_heading("7.3 Barreiras", level=2)
para(
    "As barreiras das etapas que decidem a seletividade — acoplamento CO* + CO* → OCCO*, hidrogenação CO* → CHO*/COH* e a formação de "
    "H* (Volmer) — são calculadas com o método NEB com imagem de escalada (neb.x, 7–9 imagens, com o Environ). Cada estado inicial, de "
    "transição e final é calculado em três ou mais cargas, e a barreira a potencial constante é obtida pela interpolação de Ω(U) "
    "(Seção 6). Barreiras de transferência de próton com água explícita (uma ou duas camadas de H_{2}O sobre a superfície, com o "
    "restante implícito) servem para conferir as barreiras do modelo puramente implícito em (100) e (111)."
)

doc.add_heading("8. Ligação com o modelo contínuo (KFem)", level=1)
doc.add_heading("8.1 Entradas do contínuo para a DFT", level=2)
bullet("pH local: converte o potencial para a escala RHE local (Seção 6) e define o potencial químico do OH^{-};", "")
bullet("CO_{2} na camada catalítica: entra no potencial químico do CO_{2} dissolvido (Seção 7.2); como ele varia pouco (27–30 mM), o efeito no potencial químico é pequeno (k_{B}T ln(32/27) ≈ 4 meV), e o pH local é a entrada que mais pesa;", "")
bullet("força iônica e composição: definem o eletrólito implícito (Seção 5.2);", "")
bullet("distribuição ao longo do eletrodo (2D): pés e topo das formas curvas trabalham em pH e CO_{2} diferentes, o que pede cálculos nas duas condições.", "")
doc.add_heading("8.2 Saídas da DFT para o contínuo", level=2)
para(
    "O modelo contínuo usa n_{OH} = 2 OH^{-} por CO_{2} convertido (produto CO, Eq. S1). Se os cálculos indicarem que, numa faceta e "
    "nas condições locais, o produto dominante é C_{2}H_{4} (CO_{2} → ½ C_{2}H_{4}, 6 e^{-} e 6 OH^{-} por CO_{2}), a estequiometria "
    "muda a produção de OH^{-} por elétron e, portanto, o pH local e a depleção de CO_{2}:"
)
equation(r"$R_{\mathrm{OH^-}} = \sum_p \dfrac{\nu_{\mathrm{OH},p}\,\mathrm{FE}_p}{n_p}\,\dfrac{j\,\varepsilon}{F\,L_{\mathrm{cat}}},\qquad R_{\mathrm{CO_2}} = -\sum_p \dfrac{\nu_{\mathrm{CO_2},p}\,\mathrm{FE}_p}{n_p}\,\dfrac{j\,\varepsilon}{F\,L_{\mathrm{cat}}}$")
para(
    "FE_{p} é a eficiência faradaica do produto p, n_{p} os elétrons, ν_{OH,p} e ν_{CO2,p} os OH^{-} produzidos e os CO_{2} consumidos por "
    "molécula (H_{2}: 2 OH^{-}, 0 CO_{2}; CO: 2 e 1; HCOO^{-}: 1 e 1; C_{2}H_{4}: 12 e 2). Essa expressão entra diretamente na equação "
    "personalizada do KFem no lugar da Eq. S2, com FE_{p}(U, pH_{loc}, c_{CO2}) de um modelo microcinético alimentado pelas energias "
    "e barreiras por faceta."
)
doc.add_heading("8.3 Facetas e forma do eletrodo", level=2)
para(
    "Os eletrodos convexo e pontiagudo do estudo 2D expõem orientações cristalinas diferentes ao longo da superfície. Num policristal "
    "com textura (100), o eletrodo plano expõe sobretudo (100); uma superfície curva varre continuamente as orientações entre os pés e "
    "o topo, com degraus que se aproximam de (110) e de facetas vicinais. Com as energias de superfície em solvente (Seção 3) "
    "constrói-se a forma de Wulff do Cu em água e no potencial de trabalho, e pondera-se a taxa local pelas facetas expostas em cada "
    "ponto do eletrodo 2D."
)

doc.add_heading("9. Entradas (modelos)", level=1)
doc.add_heading("9.1 pw.x: Cu(100) p(3×3) com CO adsorvido", level=2)
code("""
&CONTROL
  calculation = 'relax', prefix = 'cu100_co', outdir = './tmp', pseudo_dir = './pseudo'
  tprnfor = .true., forc_conv_thr = 1.0d-3, etot_conv_thr = 1.0d-5
/
&SYSTEM
  ibrav = 0, nat = 38, ntyp = 3
  ecutwfc = 50, ecutrho = 400          ! ajustar ao SSSP e ao teste de convergência
  occupations = 'smearing', smearing = 'mv', degauss = 0.01
  input_dft = 'rpbe', vdw_corr = 'grimme-d3'
  tot_charge = 0.0                      ! série de cargas para o potencial (Seção 6)
/
&ELECTRONS
  conv_thr = 1.0d-8, mixing_mode = 'local-TF', mixing_beta = 0.2
/
&IONS
  ion_dynamics = 'bfgs'
/
ATOMIC_SPECIES
  Cu  63.546  Cu.<pseudo-SSSP>.UPF
  C   12.011  C.<pseudo-SSSP>.UPF
  O   15.999  O.<pseudo-SSSP>.UPF
K_POINTS automatic
  5 5 1 0 0 0
CELL_PARAMETERS angstrom
  ...                                   ! gerado com ase.build.fcc100(..., a=a_otimizado, vacuum=...)
ATOMIC_POSITIONS angstrom
  ...                                   ! camadas de baixo com "0 0 0" (fixas)
""")
doc.add_heading("9.2 environ.in: água + K₂SO₄ 0,5 M com correção GCS", level=2)
code("""
&ENVIRON
  verbose = 0
  environ_thr = 1.d-1
  environ_type = 'water'                ! eps = 78.3, rhomax = 0.005, rhomin = 0.0001
  env_electrolyte_ntyp = 2
  zion(1) =  1,  cion(1) = 1.0          ! K+    (mol/L)
  zion(2) = -2,  cion(2) = 0.5          ! SO4-- (mol/L)
  cionmax = 15.0                        ! Poisson-Boltzmann modificado (tamanho finito)
  temperature = 298.15
/
&BOUNDARY
  solvent_mode = 'full'
  electrolyte_mode = 'system'           ! plano de Stern a distância fixa
  electrolyte_distance = 20.0           ! bohr, a partir do centro da lâmina: testar
  electrolyte_spread = 0.5
/
&ELECTROSTATIC
  pbc_correction = 'gcs'
  pbc_dim = 2, pbc_axis = 3
  solver = 'cg', auxiliary = 'none', tol = 1.d-11
/
""")
doc.add_heading("9.3 Execução", level=2)
code("""
mpirun -np 12 pw.x --environ -in cu100_co.in > cu100_co.out
# série de cargas para Omega(U): repetir com tot_charge = -0.6, -0.4, -0.2, 0.0, +0.2
# NEB a carga fixa:
mpirun -np 12 neb.x --environ -inp neb_coco_cu100.in > neb_coco_cu100.out
""")

doc.add_heading("10. Plano de cálculo e verificações", level=1)
table(
    ["Etapa", "Cálculos", "Verificação"],
    [
        ["1. Maciço", "a_{0} por Birch–Murnaghan", "a_{0} dentro de ~1% de 3,615 Å"],
        ["2. Lâminas limpas", "3 facetas × camadas (3–7) × vácuo; energia de superfície no vácuo e no solvente", "ordem γ(111) < γ(100) < γ(110); função trabalho perto dos valores experimentais"],
        ["3. Interface carregada", "3 facetas × 5 cargas; U_{pzc} e capacitância", "C na faixa de 10–30 µF cm^{-2}"],
        ["4. Adsorção", "3 facetas × ~12 espécies × sítios, neutro e carregado", "sítio do CO em Cu(111) (o GGA tende a preferir cavidade; experimentalmente, topo)"],
        ["5. Frequências", "adsorbatos dos estados de menor energia", "nenhuma frequência imaginária nos mínimos"],
        ["6. Barreiras", "CO–CO, CO hidrogenação, Volmer; 3 facetas × 3 cargas", "uma frequência imaginária no estado de transição"],
        ["7. Condições locais", f"pH_{{loc}} e c_{{CO2}} do KFem{f' (Tabela {n_cond})' if n_cond else ''} nas Eqs. de RHE local e de μ", "tendência: C_{2+} favorecido em (100) com pH local alto"],
        ["8. Volta ao contínuo", "FE_{p}(U, pH_{loc}, c_{CO2}) → equação personalizada do KFem", "o KFem com estequiometria por produto reproduz a tendência de pH local"],
    ],
    "Sequência de cálculos e o que conferir em cada etapa.",
    widths=[3.0, 7.0, 6.4],
    size=9,
)
para(
    "As tendências esperadas, conhecidas da literatura experimental, servem de controle qualitativo: Cu(100) favorece o acoplamento "
    "C–C e os produtos C_{2+}, sobretudo em pH local alto; Cu(111) favorece CH_{4} e a HER; Cu(110) tem comportamento intermediário. Se "
    "os cálculos não recuperarem essas tendências, o modelo de interface (funcional, cavidade, cargas, cobertura) deve ser revisto antes "
    "de devolver os resultados ao contínuo."
)

doc.add_heading("11. Limitações", level=1)
bullet("Solvente e eletrólito implícitos não descrevem ligações de hidrogênio específicas nem a estrutura da água junto ao metal; por isso as barreiras de transferência de próton são conferidas com água explícita (Seção 7.3).")
bullet("Os cátions (K^{+}) afetam a CO_{2}RR por campo e por coordenação direta; o contínuo os inclui só na média; um K^{+} explícito junto aos intermediários é recomendado nas etapas-chave.")
bullet("O funcional GGA tem erros conhecidos para CO adsorvido e para moléculas com C=O; usar RPBE e BEEF-vdW e relatar a faixa.")
bullet("Coberturas altas de CO (comuns em correntes altas) mudam as energias de adsorção; repetir as etapas-chave em 2/9 e 3/9 ML.")
bullet("A escala SHE absoluta (Φ_{SHE} ≈ 4,44 V) tem incerteza de ~0,1–0,2 V; as comparações entre facetas são mais robustas que os potenciais absolutos.")

doc.save(OUT)
print("salvo:", OUT, f"({_fig[0]} figuras, {_tab[0]} tabelas, {_eq[0]} equações)")
