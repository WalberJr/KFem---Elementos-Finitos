# ruff: noqa: E501
"""Relatório (DOCX) do estudo de Xie et al. (2022) no KFem: modelo 1D, modelo 2D e análise integrada.

    PYTHONPATH=<python-docx> python relatorio.py DIR_FIGURAS SAIDA.docx

DIR_FIGURAS reúne as saídas de figuras.py (indicadores.json), figuras2d.py (indicadores2d.json),
integrado.py (integrado.json), verifica.py (verificacao.json), esquema.py e equacoes.py (eq/).
Os números do texto vêm desses arquivos.
"""

from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

FIG = Path(sys.argv[1])
OUT = Path(sys.argv[2])
EQ = FIG / "eq"
DATA = {(r["pH"], r["j"]): r for r in json.loads((FIG / "indicadores.json").read_text())}
J_LIT = (100, 150, 200, 250, 500, 750)
J_HYP = (10, 15, 20, 25, 50, 75)

LILAS = RGBColor(0x5B, 0x3F, 0x86)
VERDE = RGBColor(0x1F, 0x5B, 0x3A)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
for side in ("left_margin", "right_margin"):
    setattr(sec, side, Cm(2.3))
sec.top_margin = sec.bottom_margin = Cm(2.2)
TEXT_W = 21.0 - 4.6  # cm

st = doc.styles
st["Normal"].font.name = "Calibri"
st["Normal"].font.size = Pt(11)
st["Normal"].paragraph_format.space_after = Pt(6)
st["Normal"].paragraph_format.line_spacing = 1.15
for name, size, color in (("Title", 22, LILAS), ("Heading 1", 16, LILAS), ("Heading 2", 13, VERDE), ("Heading 3", 11.5, VERDE)):
    s = st[name]
    s.font.name = "Calibri"
    s.font.size = Pt(size)
    s.font.bold = True
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

# rodapé com número de página
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

_fig = [0]
_tab = [0]
_eq = [0]


def para(text: str = "", bold_prefix: str | None = None, italic: bool = False, align=None, size=None):
    p = doc.add_paragraph()
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    _rich(p, text, italic=italic, size=size)
    if align:
        p.alignment = align
    return p


def _rich(p, text: str, italic: bool = False, size=None):
    """Texto com _{sub} e ^{sup} simples."""
    import re

    for tok in re.split(r"(_\{[^}]*\}|\^\{[^}]*\})", text):
        if not tok:
            continue
        if tok.startswith("_{"):
            r = p.add_run(tok[2:-1])
            r.font.subscript = True
        elif tok.startswith("^{"):
            r = p.add_run(tok[2:-1])
            r.font.superscript = True
        else:
            r = p.add_run(tok)
        r.italic = italic
        if size:
            r.font.size = Pt(size)


def bullet(text: str, bold_prefix: str | None = None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        _rich(p, bold_prefix)
        for r in p.runs:
            r.bold = True
    _rich(p, text)
    p.paragraph_format.space_after = Pt(3)
    return p


def numbered(text: str):
    p = doc.add_paragraph(style="List Number")
    _rich(p, text)
    p.paragraph_format.space_after = Pt(3)
    return p


def equation(name: str, scale: float = 0.80) -> int:
    _eq[0] += 1
    img = EQ / f"{name}.png"
    w_px, _ = Image.open(img).size
    w_cm = min(w_px / 220 * 2.54 * scale, TEXT_W - 2.0)
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.tab_stops.add_tab_stop(Cm(TEXT_W / 2), WD_TAB_ALIGNMENT.CENTER)
    pf.tab_stops.add_tab_stop(Cm(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
    pf.space_before = Pt(4)
    pf.space_after = Pt(4)
    p.add_run("\t")
    p.add_run().add_picture(str(img), width=Cm(w_cm))
    p.add_run(f"\t({_eq[0]})")
    return _eq[0]


def figure(fname: str, caption: str, width_cm: float = TEXT_W) -> int:
    _fig[0] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(FIG / fname), width=Cm(width_cm))
    c = doc.add_paragraph()
    c.add_run(f"Figura {_fig[0]}. ").bold = True
    _rich(c, caption, size=9.5)
    c.paragraph_format.space_after = Pt(10)
    return _fig[0]


def _shade(cell, hexcolor: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def table(header: list[str], rows: list[list[str]], caption: str, widths: list[float] | None = None, size: float = 9.5) -> int:
    _tab[0] += 1
    c = doc.add_paragraph()
    c.add_run(f"Tabela {_tab[0]}. ").bold = True
    _rich(c, caption, size=9.5)
    c.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    if widths:
        t.autofit = False
        for k, w in enumerate(widths):
            t.columns[k].width = Cm(w)
    trPr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)
    for i, row in enumerate([header, *rows]):
        cs = OxmlElement("w:cantSplit")
        t.rows[i]._tr.get_or_add_trPr().append(cs)
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


def f(v, nd=1, dash="—"):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return dash
    return f"{v:.{nd}f}".replace(".", ",")


def g(pH, j, key, nd=1):
    r = DATA.get((pH, j))
    return f(r[key], nd) if r else "n/d"


def interp_j(pH: int, target: float) -> float | None:
    """Corrente (literal, KFem) que dá o CO2 mínimo `target` em pH dado (interpolação linear)."""
    pts = sorted((j, DATA[(pH, j)]["co2_min"]) for j in J_LIT if (pH, j) in DATA)
    for (j0, c0), (j1, c1) in itertools.pairwise(pts):
        if (c0 - target) * (c1 - target) <= 0 and c0 != c1:
            return j0 + (target - c0) * (j1 - j0) / (c1 - c0)
    if len(pts) >= 2 and target > pts[0][1]:  # extrapola abaixo da menor corrente
        (j0, c0), (j1, c1) = pts[0], pts[1]
        return j0 + (target - c0) * (j1 - j0) / (c1 - c0)
    return None


# ---------------------------------------------------------------- números derivados
F_C, D_H, EPS, L = 96485.33, 9.311e-9, 0.6, 100e-6


def jstar(pH: float) -> float:
    """Corrente (mA/cm²) em que a produção de OH- iguala o suprimento difusivo de H+."""
    return F_C * D_H * 1000 * 10 ** (-pH) / (EPS * L) / 10


def transition(pH: int, js) -> tuple[float | None, float | None]:
    """Última corrente com superfície ácida e primeira com superfície alcalina."""
    acid = [j for j in js if (pH, j) in DATA and DATA[(pH, j)]["pH_s"] < 7]
    alk = [j for j in js if (pH, j) in DATA and DATA[(pH, j)]["pH_s"] >= 7]
    return (max(acid) if acid else None, min(alk) if alk else None)


PAPER = {k: r["paper"] for k, r in DATA.items() if r["paper"]}
ratios = []
for pH in (3, 4):
    for j in (100, 250, 500, 750):
        p = DATA.get((pH, j), {}).get("paper") or None
        if p is None:
            # o indicador do artigo pode existir para correntes sem cálculo KFem
            from figuras import PAPER as _P

            p = _P.get((pH, j))
        if p and p.get("co2_min") is not None:
            jj = interp_j(pH, p["co2_min"])
            if jj:
                ratios.append((pH, j, p["co2_min"], jj, j / jj))
_rs = sorted(r[4] for r in ratios)
r_mean = (_rs[len(_rs) // 2] if len(_rs) % 2 else 0.5 * (_rs[len(_rs) // 2 - 1] + _rs[len(_rs) // 2])) if _rs else float("nan")  # mediana
tr2_lit = transition(2, sorted(set(J_HYP + J_LIT)))
tr1 = transition(1, J_LIT)
n_cases = len(DATA)
lit = DATA.get((2, 750), {})


# ---------------------------------------------------------------- dados 2D e integrados
D2J = json.loads((FIG / "indicadores2d.json").read_text())
D2 = {(r["pH"], r["j"], r["shape"]): r for r in D2J["casos"]}
VER2D1D = D2J.get("verificacao_1d", {})
VER = json.loads((FIG / "verificacao.json").read_text())
INT = json.loads((FIG / "integrado.json").read_text())
INTD = {(r["pH"], r["j"], r["shape"]): r for r in INT}
SHAPES = ("plano", "convexo", "conico")
SLAB = {"plano": "Plano", "convexo": "Convexo", "conico": "Pontiagudo"}
CASES2D = ((2, 500), (2, 200), (4, 500))
LS_UM, RD = 20.0, 20.0 / math.pi
HC = RD
AC = math.sqrt(100.0 - HC**2)
W = {"plano": 20.0, "convexo": 2 * RD + 1.2, "conico": 2 * AC}
FAC = {s: LS_UM / W[s] for s in SHAPES}


def d2(pH, j, s, key, nd=2):
    r = D2.get((pH, j, s))
    return f(r[key], nd) if r and r.get(key) is not None else "n/d"


def decomp(pH, j, s):
    """Δ total (2D − 1D na corrente nominal), parte da corrente projetada e parte local."""
    r = INTD.get((pH, j, s))
    if not r or r["pH_1d_nominal"] is None or r["pH_1d_proj"] is None:
        return None
    tot = r["pH_2d_mean"] - r["pH_1d_nominal"]
    proj = r["pH_1d_proj"] - r["pH_1d_nominal"]
    return tot, proj, tot - proj


def concl(k: int, text: str):
    p = para(text, bold_prefix=f"{k}. ")
    p.paragraph_format.left_indent = Cm(0.6)
    p.paragraph_format.first_line_indent = Cm(-0.6)
    return p


def mono(text: str):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.name = "DejaVu Sans Mono"
    r.font.size = Pt(8.5)
    p.paragraph_format.left_indent = Cm(0.6)
    p.paragraph_format.space_after = Pt(2)


v1 = VER["malha_1d"]
v2 = VER["malha_2d"]
vf = {r["shape"]: r for r in VER["formas_fino"]}
dec = {(pH, j, s): decomp(pH, j, s) for pH, j in CASES2D for s in ("convexo", "conico")}
phi = [d[0] / d[1] for d in dec.values() if d and abs(d[1]) > 1e-6]  # fração do ganho previsto pela corrente projetada
phi_rng = (min(phi), max(phi)) if phi else (float("nan"), float("nan"))
_fr = [abs(r["front_2d"] - r["front_1d_proj"]) for r in INT if r["front_2d"] is not None and r["front_1d_proj"] is not None]
front_dmax = max(_fr) if _fr else float("nan")
_cl2 = [r["co2_cl_2d_mean"] for r in INT if r["j"] == 500 and r["co2_cl_2d_mean"] is not None]
_cl1 = [r["co2_cl_1d_proj"] for r in INT if r["j"] == 500 and r["shape"] != "plano" and r["co2_cl_1d_proj"] is not None]
_c = [r.get("co2_cl_mean") for r in D2.values() if r.get("co2_cl_mean") is not None and r["j"] == 500]
co2cl_rng = f"{f(min(_c), 1)}–{f(max(_c), 1)} mM a 500 mA cm^{{-2}}" if _c else "n/d"
ver_max = max((v["max_dCO2_mM"] for v in VER2D1D.values()), default=float("nan"))

# ================================================================= documento
t = doc.add_paragraph(style="Title")
t.add_run("Redução de CO₂ em meio ácido no KFem: reprodução 1D de Xie et al. (2022) e efeito da forma do eletrodo em 2D")
para("Relatório técnico — reação-difusão das espécies do carbonato na camada catalítica e na camada de difusão; análise 1D, 2D e integrada", italic=True)
para("KFem (FEniCSx/DOLFINx 0.11) · equação personalizada em forma fraca · estudos dependentes do tempo até o estado estacionário · 25 de novembro de 2026", size=9.5)

doc.add_heading("Resumo", level=1)
para(
    "Este relatório reproduz no KFem o modelo numérico de Xie et al., “High carbon utilization in CO_{2} reduction to multi-carbon "
    "products in acidic media”, Nature Catalysis 5, 564–570 (2022), e o estende a duas dimensões para estudar a forma do eletrodo. "
    "O modelo descreve a redução de CO_{2} (CO_{2}RR) numa camada catalítica porosa de 0,4 µm junto à interface gás-líquido, os cinco "
    "equilíbrios ácido-base do sistema carbonato e a difusão de CO_{2}, HCO_{3}^{-}, CO_{3}^{2-}, OH^{-} e H^{+} numa camada de 100 µm."
)
para(
    f"Modelo 1D. Foram resolvidos {n_cases} casos (pH 0–4, 10–750 mA cm^{{-2}}) com a metodologia do artigo. O KFem recupera os "
    "fenômenos qualitativos publicados: superfície alcalina (pH ≈ 12–13) com eletrólito ácido, frente ácido-base estreita, vale de CO_{2} "
    "e regeneração de CO_{2} na frente. Quantitativamente, a alcalinização com pH 2 começa entre "
    f"{f(tr2_lit[0], 0)} e {f(tr2_lit[1], 0)} mA cm^{{-2}}, contra 100–150 no artigo; o balanço de prótons "
    f"j* = F D_{{H}} c_{{H,b}}/(ε L) ≈ {f(jstar(2), 1)} mA cm^{{-2}} mostra que esse é o resultado das equações publicadas.",
    bold_prefix=None,
)
para(
    "Modelo 2D. Três eletrodos com a mesma área ativa (comprimento ativo de 20 µm) e a mesma corrente total foram comparados: plano, "
    "convexo (semicírculo) e pontiagudo (triângulo com a altura do semicírculo), em pH 2 (200 e 500 mA cm^{-2}) e pH 4 (500 mA cm^{-2}). "
    f"Nas três condições, a superfície é mais alcalina no convexo (pH médio {d2(2, 500, 'convexo', 'pH_el_mean')} com pH 2 / 500), "
    f"depois no pontiagudo ({d2(2, 500, 'conico', 'pH_el_mean')}) e por último no plano ({d2(2, 500, 'plano', 'pH_el_mean')}). "
    "Ao longo de cada eletrodo curvo, o pH é maior junto à base, entre eletrodos vizinhos, e menor no topo, voltado para o eletrólito."
)
para(
    "Análise integrada. Com a mesma corrente total, as formas curvas ocupam uma base mais estreita e concentram mais corrente por área "
    f"de base: {f(FAC['convexo'], 2)} vezes (convexo) e {f(FAC['conico'], 2)} vezes (pontiagudo). Casos 1D extras nessas correntes "
    f"reproduzem a posição da frente ácido-base do 2D (diferença ≤ {f(front_dmax, 1)} µm): longe do eletrodo, a forma equivale a um "
    "eletrodo plano com mais corrente. Na superfície, o 2D recebe só "
    f"{f(100 * phi_rng[0], 0)}–{f(100 * phi_rng[1], 0)}% do ganho de pH que essa corrente maior daria, porque a interface gás-líquido, "
    "por onde entra o CO_{2}, também é maior por área de base, e o CO_{2} na camada catalítica fica no nível do eletrodo plano. "
    "O 1D dá o mapa de regimes em função do pH e da corrente; o 2D mostra como a forma desloca o eletrodo nesse mapa e redistribui o "
    "pH ao longo da superfície."
)

doc.add_heading("1. Introdução e objetivos", level=1)
para(
    "O artigo de Xie et al. mostra que a CO_{2}RR em eletrólito ácido pode ter alta utilização de carbono porque a superfície do "
    "eletrodo fica alcalina e o carbonato formado ali é reconvertido em CO_{2} quando encontra o eletrólito ácido. O material "
    "suplementar (Supplementary Note 1, Equações S1–S21, Tabelas S1–S3, Figuras S2, S3 e S6) traz o modelo 1D que sustenta essa "
    "explicação, resolvido no COMSOL Multiphysics 5.6."
)
para("Este trabalho tem três objetivos:")
numbered("reproduzir o modelo 1D no KFem com a mesma metodologia e comparar os resultados com as figuras do artigo;")
numbered("estender o modelo a 2D para avaliar a forma do eletrodo (plano, convexo e pontiagudo) com a mesma área ativa e as mesmas condições do artigo;")
numbered("combinar as duas análises: usar o 1D para interpretar o 2D e separar o efeito da forma do efeito da corrente por área.")
para(
    "Nenhuma equação ou parâmetro foi inventado. Tudo vem do material suplementar, e as poucas leituras necessárias estão na Tabela 4. "
    "As escolhas do modelo 2D (forma, igualdade de área, normalização da corrente) foram definidas com o usuário e estão na Seção 2.7. "
    "Os valores do artigo usados na comparação foram lidos visualmente das Figuras S2 e S3, com incerteza típica de ±1 mM no CO_{2}, "
    "±0,3 no pH e ±3 µm nas posições."
)

# ------------------------------------------------------------------ metodologia
doc.add_heading("2. Metodologia", level=1)
para(
    "A metodologia tem quatro partes: o modelo físico como publicado (2.1–2.6), a extensão 2D (2.7), a implementação numérica no KFem "
    "(2.8) e o plano de simulações e de verificação (2.9–2.10)."
)
doc.add_heading("2.1 Domínio e visão geral", level=2)
n_esq1 = figure("fig_esquema_1d.png", "Esquema do modelo 1D (fora de escala). O CO_{2} entra pela interface gás-líquido (x = 0) e é reduzido na camada catalítica (CL), que produz OH^{-}. O H^{+} do eletrólito chega por difusão a partir de x = 100 µm.")
para(
    f"O domínio é unidimensional, 0 ≤ x ≤ 100 µm (Figura {n_esq1}). A interface gás-líquido fica em x = 0, onde o CO_{{2}} chega pela "
    "fase gasosa. A camada catalítica ocupa 0 ≤ x ≤ L_{cat} = 0,4 µm, com porosidade ε = 0,6, e é seguida pela camada de difusão "
    "líquida. Em x = 100 µm está o seio do eletrólito, de composição fixa."
)
doc.add_heading("2.2 Reação eletroquímica", level=2)
para("O artigo admite a redução de CO_{2} a CO por 2 elétrons, em meio aquoso:")
equation("eq01_reacao")
para("A taxa volumétrica é uniforme na camada catalítica e proporcional à corrente aplicada j (Eq. S2):")
equation("eq02_taxa")
para("F é a constante de Faraday e n = 2. O termo-fonte é −R_{CO2RR} para o CO_{2} e +2R_{CO2RR} para o OH^{-}.")
doc.add_heading("2.3 Equilíbrios do carbonato (Eqs. S3–S7)", level=2)
for e in ("eq03_r1", "eq04_r2", "eq05_r3", "eq06_r4", "eq07_rw"):
    equation(e)
para("As constantes reversas seguem das constantes de equilíbrio:")
equation("eq08a_reversas")
equation("eq08b_reversas", scale=0.8)
para("Os termos-fonte de cada espécie (Eqs. S8–S12) combinam as taxas acima:")
for e in ("eq09a_fonte", "eq09b_fonte", "eq09c_fonte", "eq09d_fonte", "eq09e_fonte"):
    equation(e)
doc.add_heading("2.4 Transporte (Eqs. S14–S16)", level=2)
para("Cada espécie obedece à equação de reação-difusão, sem migração nem convecção:")
n_transp = equation("eq10_transporte")
para("Na camada catalítica, a difusividade efetiva usa a relação de Bruggeman:")
equation("eq11_bruggeman")
doc.add_heading("2.5 Condições de contorno e inicial (Eqs. S17–S21)", level=2)
para(
    "Em x = 0 o fluxo das espécies aquosas é nulo e o CO_{2} fica fixo na solubilidade de saturação, que combina a lei de Henry com a "
    "correção salina de Séchenov:"
)
equation("eq12_henry")
equation("eq13_sechenov")
para(
    "Em x = 100 µm as cinco concentrações valem o equilíbrio do eletrólito: [H^{+}] = 10^{-pH}, [OH^{-}] = K_{w}/[H^{+}], "
    "[HCO_{3}^{-}] = K_{1}c_{CO2}/[H^{+}] e [CO_{3}^{2-}] = K_{2}[HCO_{3}^{-}]/[H^{+}], com CO_{2} na saturação. "
    "A condição inicial é esse mesmo estado em todo o domínio."
)
doc.add_heading("2.6 Parâmetros", level=2)
table(
    ["Parâmetro", "Valor (artigo)", "Uso no KFem"],
    [
        ["K_{0}", "3,92×10^{-2} mol L^{-1} atm^{-1} (293,15 K)", "K0"],
        ["K_{1}", "10^{-5,73} (mol L^{-1})", "K1"],
        ["K_{2}", "10^{-8,58} mol L^{-1}", "K2"],
        ["K_{3}, K_{4}", "K_{1}/K_{w}, K_{2}/K_{w}", "k3r = k3f K_{w}/K_{1}; k4r = k4f K_{w}/K_{2}"],
        ["K_{w}", "10^{-14} mol^{2} L^{-2}", "Kw"],
        ["k_{1f}", "3,71×10^{-2} s^{-1}", "k1f"],
        ["k_{2f}", "59,44 s^{-1}", "k2f"],
        ["k_{3f}", "2,23×10^{3} L mol^{-1} s^{-1}", "k3f"],
        ["k_{4f}", "6,0×10^{9} L mol^{-1} s^{-1}", "k4f"],
        ["k_{wf}", "2,4×10^{-5} (s^{-1} no artigo)", "2,4×10^{-5} mol L^{-1} s^{-1} (atividade da água = 1)"],
    ],
    "Constantes de equilíbrio e cinéticas (Tabela S1 do artigo).",
    widths=[3.0, 6.5, 6.9],
)
table(
    ["Espécie", "D (cm^{2} s^{-1})"],
    [["H^{+}", "9,311×10^{-5}"], ["OH^{-}", "5,293×10^{-5}"], ["HCO_{3}^{-}", "1,185×10^{-5}"], ["CO_{3}^{2-}", "0,923×10^{-5}"], ["CO_{2}", "1,910×10^{-5}"]],
    "Coeficientes de difusão na fase líquida (Tabela S2).",
    widths=[5.0, 5.0],
)
table(
    ["Grandeza", "Valor"],
    [
        ["h_{K+}", "0,0922 L mol^{-1}"],
        ["h_{SO4 2-}", "0,1117 L mol^{-1}"],
        ["h_{G,0}", "−0,0172 L mol^{-1}"],
        ["h_{T}", "−0,000338 L mol^{-1} K^{-1}"],
        ["T, p_{CO2}, C_{s}", "293,15 K; 1 atm; 0,5 mol L^{-1} (K_{2}SO_{4})"],
        ["c_{CO2} de saturação (calculado)", "32,13 mM"],
        ["L_{cat}, ε, L", "0,4 µm; 0,6; 100 µm"],
    ],
    "Solubilidade (Tabela S3; h_{HCO3-} e h_{CO3 2-} não entram, pois o sal é K_{2}SO_{4}) e geometria.",
    widths=[6.0, 7.0],
)
t_leit = _tab[0] + 1

doc.add_heading("2.7 Extensão 2D: eletrodo plano, convexo e pontiagudo", level=2)
para(
    "O modelo 2D usa as mesmas equações (Eqs. 2–15), os mesmos parâmetros e as mesmas condições do artigo. Muda só a forma da interface "
    "gás-líquido, à qual a camada catalítica de 0,4 µm fica colada, acompanhando a superfície."
)
n_esq2 = figure("fig_esquema_2d.png", "Células 2D das três formas (a CL foi desenhada 3 vezes mais grossa). Cada célula vai da base até y = 100 µm, onde fica o eletrólito; as paredes laterais são de simetria.")
para("Igualdade de área e geometrias", bold_prefix=None).runs[0].bold = True
para(
    f"Em 2D, a área ativa por unidade de profundidade é o comprimento do eletrodo. As três formas têm o mesmo comprimento ativo, "
    f"L_{{s}} = 20 µm (Figura {n_esq2}):"
)
equation("eq18_geom2d")
bullet("segmento reto de 20 µm;", "Plano: ")
bullet(f"semicírculo de raio R = L_{{s}}/π = {f(RD, 3)} µm;", "Convexo: ")
bullet(f"triângulo isósceles com a mesma altura do semicírculo, h = R; cada lado mede L_{{s}}/2 = 10 µm e a meia-base é a = {f(AC, 3)} µm.", "Pontiagudo: ")
para("Célula de simulação", bold_prefix=None).runs[0].bold = True
para(
    "Cada caso é uma célula periódica de um arranjo de eletrodos iguais. As paredes laterais são de simetria (fluxo nulo), o que "
    "equivale a ter vizinhos iguais dos dois lados. A largura da célula é a largura da base de cada forma: "
    f"w = {f(W['plano'], 2)} µm (plano), {f(W['convexo'], 2)} µm (convexo) e {f(W['conico'], 2)} µm (pontiagudo). No convexo há uma "
    "base inerte de g = 0,6 µm de cada lado do semicírculo: sem ela, o arco tocaria a parede tangencialmente e a malha ficaria "
    "degenerada. O eletrólito fica em y = 100 µm acima da base, como no 1D."
)
para("Mesma corrente total", bold_prefix=None).runs[0].bold = True
para(
    "A densidade de corrente j é a mesma por área ativa nas três formas. A taxa da reação usa a área real da camada catalítica de cada "
    "forma, A_{cl}, medida na geometria, para que a corrente total seja j·L_{s} em todas:"
)
n_t2 = equation("eq19_taxa2d")
para(f"No plano, A_{{cl}} = L_{{s}}·L_{{cat}}, e a Eq. {n_t2} coincide com a Eq. S2 do artigo.")
para("Condições de contorno", bold_prefix=None).runs[0].bold = True
equation("eq20_contornos2d")
para(
    "Γ_{gl} é a interface gás-líquido (a face interna da CL); y = H = 100 µm é o contorno do eletrólito. Os trechos retos da base fora "
    "da CL (só no convexo) e as paredes laterais têm fluxo nulo."
)
para("Corrente por área de base", bold_prefix=None).runs[0].bold = True
para(
    "Para a análise integrada (Seção 5) define-se a corrente por área de base da célula. Com a mesma corrente total e base mais "
    "estreita, a forma curva entrega mais corrente por área projetada:"
)
n_jp = equation("eq21_jproj")
para(
    f"O fator L_{{s}}/w vale 1 no plano, {f(FAC['convexo'], 3)} no convexo e {f(FAC['conico'], 3)} no pontiagudo. Longe do eletrodo, o "
    "eletrólito “vê” só essa corrente média por área de base."
)

doc.add_heading("2.8 Implementação no KFem", level=2)
para("Forma fraca", bold_prefix=None).runs[0].bold = True
para(
    "O modelo entrou no KFem como uma Equação personalizada (nó physics.weakform). As cinco concentrações são campos escalares P1 de um "
    "espaço misto, e o resíduo é escrito em texto e interpretado pelo analisador seguro de expressões do KFem (sem eval). Multiplicando "
    "cada equação por uma função-teste v_{i} e integrando por partes, com fluxo nulo nos contornos naturais e valores prescritos nos de "
    "Dirichlet, obtém-se:"
)
equation("eq14_fraca")
para(
    "No 1D, a indicadora χ (1 na CL, 0 fora) ativa a fonte da CO_{2}RR e o fator de Bruggeman. No 2D, os dois termos são integrados só "
    "no subdomínio da CL (dx(cl)). O jacobiano é obtido por diferenciação automática (UFL)."
)
para("Malhas", bold_prefix=None).runs[0].bold = True
para(
    "O problema 1D é resolvido numa faixa de 100 × 0,2 µm com fluxo nulo nas bordas superior e inferior, o que reproduz exatamente a "
    f"solução 1D; malha de 0,1 µm ({v1[0]['cells'] or 4012} triângulos). O artigo usou 0,16 µm na CL e 0,1 µm na camada de difusão. "
    "No 2D, a malha é de triângulos com 0,1 µm numa faixa de 0,6 µm junto ao eletrodo, 0,2 µm numa faixa de 15 µm junto ao eletrólito "
    f"(onde fica a frente ácido-base) e até 1 µm no meio: {v2[0]['cells']} elementos no plano, {vf['convexo']['cells'][0]} no convexo e "
    f"{vf['conico']['cells'][0]} no pontiagudo. A geometria é montada pelo Gmsh (núcleo OCC) na unidade do componente (µm) e depois "
    "escalada para metros, com polígonos, diferenças e interseções booleanas para recortar a CL de cada forma."
)
para("Integração no tempo e Newton", bold_prefix=None).runs[0].bold = True
para(
    "Como no artigo, o estado estacionário é alcançado com um estudo dependente do tempo a partir do equilíbrio do eletrólito, com "
    "saídas em 0, 10^{-5}, 10^{-4}, …, 60 e 120 s. O KFem usa BDF1 no primeiro passo e, depois, BDF2 de passo variável:"
)
equation("eq15_bdf2")
para(
    "O passo é adaptativo, com tolerância relativa de 0,01, a mesma do artigo. O Newton (PETSc SNES) usa busca linear de retrocesso, "
    "tolerância relativa de 10^{-10} sem tolerância absoluta e o solver direto MUMPS, como no artigo. Um passo rejeitado é refeito com ¼ "
    "do tamanho, e o passo volta a crescer até o nominal."
)
para("O “eps” das concentrações", bold_prefix=None).runs[0].bold = True
para("O artigo diz apenas que um “eps” evita concentrações nulas ou negativas. No KFem ele é um piso nas concentrações das taxas:")
equation("eq17_eps")
para(
    "Como no COMSOL com variáveis primitivas, a incógnita pode ficar ligeiramente negativa onde o gradiente é muito forte (Seção 6.5). "
    "A formulação em ln c do KFem eliminaria isso, mas não foi usada, para manter a metodologia do artigo."
)
table(
    ["Ponto", "Leitura adotada", "Motivo"],
    [
        ["[H_{2}O] nas taxas (Eqs. S8–S13)", "Atividade da água = 1", "k_{1f} e k_{wf} são de pseudo-primeira ordem; as unidades da Tabela S1 não fecham com [H_{2}O] = 55,5 M"],
        ["Unidade de k_{wf} (s^{-1})", "mol L^{-1} s^{-1}", "Consequência da atividade unitária"],
        ["K_{1} sem unidade", "mol L^{-1}", "Necessário para a consistência dimensional de k_{1r} = k_{1f}/K_{1}"],
        ["Séchenov (Eqs. S19–S20)", "K_{s} = Σ(h_{ion} + h_{G}) multiplicado por C_{s} = 0,5 M", "Leitura direta da Eq. S19; dá 32,13 mM, próximo dos ≈ 33 mM das Figuras S2"],
        ["“eps”", "max(c, 10^{-15} mol m^{-3}) nas taxas", "O valor não é publicado"],
        ["Temperatura", "293,15 K", "A temperatura de K_{0} na Tabela S1"],
    ],
    "Pontos do material suplementar que admitem mais de uma leitura, e a escolha feita.",
    widths=[4.2, 5.4, 6.8],
    size=9,
)

doc.add_heading("2.9 Casos simulados e indicadores", level=2)
table(
    ["Conjunto", "Casos", "Para quê"],
    [
        ["1D, matriz do artigo", "pH 0–4 × 100, 150, 200, 250, 500, 750 mA cm^{-2} (30)", "reprodução e comparação com as Figuras S2/S3"],
        ["1D, corrente / 10", "pH 2 × 10, 15, 20, 25, 50, 75 mA cm^{-2} (6)", "teste da hipótese de escala (Seção 6.3)"],
        ["2D", "3 formas × (pH 2 / 200, pH 2 / 500, pH 4 / 500) (9)", "efeito da forma"],
        ["2D, malha", "5 malhas mais finas (pH 4 / 500)", "convergência de malha"],
        ["1D na corrente projetada", "pH 2 e 4, j·L_{s}/w de cada forma curva (6)", "análise integrada (Seção 5)"],
    ],
    "Conjuntos de simulações.",
    widths=[3.6, 6.8, 6.0],
    size=9,
)
para("Do estado estacionário (t = 120 s) extraem-se os indicadores do artigo:")
bullet("valor e posição do mínimo de CO_{2} no domínio;", "CO_{2} mínimo: ")
bullet("pH na interface gás-líquido (x = 0 no 1D; média ao longo do eletrodo no 2D, ponderada pelo comprimento de arco, com mínimo e máximo);", "pH na superfície: ")
bullet("primeira posição com pH < 6, definida só quando a superfície é alcalina (no 2D, a menor altura y com pH < 6);", "frente de pH: ")
bullet("CO_{2} a 0,2 µm da interface, na direção normal, ao longo do eletrodo (média ponderada pelo arco);", "CO_{2} no meio da CL (2D): ")
bullet("maior variação de CO_{2} entre t = 60 s e 120 s.", "estado estacionário: ")

doc.add_heading("2.10 Verificação numérica", level=2)
para(
    "O motor de forma fraca do KFem tem testes automatizados (pytest) com solução manufaturada de Poisson, um transiente com solução "
    "analítica (ordem do BDF2) e o operador dt() aplicado a expressões; as operações de geometria usadas no 2D (polígono, diferença, "
    "interseção) têm testes de área contra fórmulas analíticas."
)
rows = []
for (pH, j), r in sorted(DATA.items()):
    s = r.get("stats") or {}
    rows.append([f"{pH}", f"{j}", f"{r['dCO2']:.1e}".replace(".", ","), str(s.get("steps", "—")), str(s.get("rejected", "—")),
                 str(s.get("newton", "—")), f(s.get("wall"), 0)])
n_tconv = table(["pH", "j (mA cm^{-2})", "máx |ΔCO_{2}| 60→120 s (mM)", "passos", "rejeitados", "iterações de Newton", "tempo (s)"], rows,
                "Estado estacionário e custo de cada caso 1D (1 processo, CPU, vários casos em paralelo).", widths=[1.3, 2.2, 3.6, 1.9, 2.2, 2.9, 2.3], size=8.5)
para(
    "Todas as variações finais ficam muito abaixo de 10^{-3} mM, e os perfis de 60 s e 120 s são indistinguíveis. Os casos com frente "
    "ácido-base dentro do domínio (pH 1 e 2 com superfície alcalina) são os mais rígidos: a frente atravessa o domínio e muitos passos "
    "são rejeitados e refeitos com passo menor."
)
table(
    ["Malha", "h (µm)", "pH na superfície", "CO_{2} mín (mM)", "máx |ΔCO_{2}| (mM)"],
    [[f"1D {k + 1}", f(r["h_um"], 3), f(r["pH_s"], 4), f(r["co2_min"], 4), f(r["max_dCO2_vs_fina"], 3)] for k, r in enumerate(v1)]
    + [[f"2D plano: {r['caso']}", "—", f(r["pH_s"], 4), f(r["co2_min"], 4), f(r["max_dCO2_vs_1d"], 3)] for r in v2],
    "Convergência de malha com pH 4 e 500 mA cm^{-2}. No 1D, a diferença é contra a malha mais fina (0,025 µm); no 2D plano, contra o 1D "
    "mais fino.",
    widths=[5.6, 1.6, 3.0, 3.0, 3.2],
    size=9,
)
para(
    f"Os indicadores não mudam com a malha: o pH na superfície fica em {f(v1[0]['pH_s'], 3)} em todas as malhas 1D e 2D, e o CO_{{2}} "
    f"difere menos de {f(max(r['max_dCO2_vs_fina'] for r in v1), 2)} mM. No convexo e no pontiagudo, a malha mais fina junto ao "
    f"eletrólito dá o mesmo pH médio (diferença < 10^{{-5}}) e o mesmo CO_{{2}} mínimo; ela só reduz o H^{{+}} negativo na frente, de "
    f"{f(vf['convexo']['neg_H'][0] * 1000, 0)} para {f(vf['convexo']['neg_H'][1] * 1000, 0)} µM (convexo)."
)
n_v1d = figure("fig2d_verificacao_1d.png", "Verificação: perfis do eletrodo plano em 2D (pontos, todos os nós da malha) sobre os do 1D (linha), com pH 2.")
para(
    f"O eletrodo plano em 2D é o próprio problema 1D, só que resolvido noutra geometria e noutra malha. Os perfis coincidem (Figura "
    f"{n_v1d}): a maior diferença de CO_{{2}} é {f(ver_max, 2)} mM, e o pH na superfície coincide até a quarta casa. Isso valida a "
    "construção da geometria 2D, os marcadores de contorno e a normalização da taxa."
)
para(
    "Uma versão anterior deste relatório usou uma geometria 1D montada diretamente em metros. Nessa escala, a interface entre a CL "
    "(0,4 µm) e a camada de difusão ficava abaixo da tolerância geométrica do OCC, e a malha da CL saía degenerada. A correção (montar "
    "na unidade do componente e escalar depois) mudou pouco os resultados — pH na superfície +0,03 a +0,06 e CO_{2} mínimo até 1,5 mM "
    "menor — e foi confirmada de forma independente pelo acordo 2D × 1D acima. Todos os números deste relatório usam a geometria corrigida."
)

# ------------------------------------------------------------------ resultados 1D
doc.add_heading("3. Resultados do modelo 1D", level=1)
doc.add_heading("3.1 Perfis estacionários de CO₂", level=2)
n1 = figure("fig_co2.png", "Perfis estacionários de CO_{2} dissolvido para pH 0–4 e as correntes do artigo (equivalente à Figura S2). x = 0 é a interface gás-líquido e a CL ocupa 0–0,4 µm.")
para(
    f"Com pH 0 em todas as correntes, e com pH 1 até 150 mA cm^{{-2}} (Figura {n1}), o CO_{{2}} fica próximo da saturação em todo o "
    f"domínio: o mínimo é {g(0, 100, 'co2_min')}–{g(0, 750, 'co2_min')} mM com pH 0, para 100–750 mA cm^{{-2}}. O consumo na CL é "
    "reposto por difusão a partir da interface, e o meio ácido impede a conversão do CO_{2} em carbonato."
)
para(
    "Com pH 2–4 e superfície alcalina, o CO_{2} que entra pela interface é capturado pelo OH^{-} (r_{3}) e vira HCO_{3}^{-}/CO_{3}^{2-}. "
    f"Surge um vale de CO_{{2}} a 10–30 µm da superfície, que se aprofunda com a corrente: com pH 4, o mínimo cai de "
    f"{g(4, 100, 'co2_min')} mM (100 mA cm^{{-2}}) para {g(4, 500, 'co2_min', 2)} mM (500 mA cm^{{-2}}). Com pH 2, o CO_{{2}} passa da "
    f"saturação perto da frente ácida, chegando a {g(2, 100, 'co2_max')} mM a 100 mA cm^{{-2}}; com pH 1 e superfície alcalina, chega a "
    f"{g(1, 750, 'co2_max', 0)} mM a 750 mA cm^{{-2}} (regeneração de CO_{{2}}, Seção 6.4)."
)
doc.add_heading("3.2 Perfis estacionários de pH", level=2)
n2 = figure("fig_ph.png", "Perfis estacionários de pH (equivalente à Figura S3). Trechos interrompidos junto à frente correspondem a pontos com [H^{+}] ≤ 0 (Seção 6.5), em faixas de no máximo 0,5 µm.")
para(
    f"Com eletrólito ácido (pH 2–4) e corrente suficiente, a superfície fica fortemente alcalina (Figura {n2}), com pH de "
    f"{g(2, 100, 'pH_s')} a {g(2, 750, 'pH_s')} com pH 2. Uma frente estreita, de menos de 1 µm, separa essa região do eletrólito ácido. "
    f"Com pH 3 e 4, quase todo o domínio fica alcalino e a frente encosta no eletrólito (x ≈ {g(3, 100, 'front')}–{g(4, 750, 'front')} µm). "
    f"Com pH 1, a superfície é ácida a 100 mA cm^{{-2}} (pH {g(1, 100, 'pH_s', 2)}), quase neutra a 150 mA cm^{{-2}} "
    f"(pH {g(1, 150, 'pH_s', 2)}, praticamente no limiar j* da Seção 6.1) e alcalina a partir de 200 mA cm^{{-2}} (pH {g(1, 200, 'pH_s')}). "
    f"O mesmo acontece com pH 2 em 15 mA cm^{{-2}} (pH {g(2, 15, 'pH_s', 2)}). Com pH 0, a superfície fica ácida "
    f"(pH ≤ {g(0, 750, 'pH_s', 2)}) em toda a faixa."
)
n3 = figure("fig_mapa_ph.png", "pH na superfície do eletrodo (x = 0) em função do pH do eletrólito e da corrente aplicada.", width_cm=11.5)
doc.add_heading("3.3 Evolução temporal", level=2)
n4 = figure("fig_transiente.png", "Evolução temporal com pH 2 e 500 mA cm^{-2} (equivalente à Figura S6), a partir do equilíbrio do eletrólito.")
para(
    f"A Figura {n4} mostra como se forma o estado estacionário. O OH^{{-}} produzido na CL neutraliza o H^{{+}} local em cerca de 1 ms, e a "
    "frente ácido-base avança para o eletrólito em alguns segundos, enquanto o vale de CO_{2} se aprofunda. Depois de cerca de 10 s, os "
    "perfis não mudam mais. A dinâmica é qualitativamente a da Figura S6 do artigo."
)
doc.add_heading("3.4 Comparação com o artigo", level=2)
n5 = figure("fig_comparacao.png", "(a) CO_{2} mínimo em função da corrente: KFem (linhas) e valores lidos das Figuras S2 (círculos). (b) pH na superfície com pH 2: KFem (com as correntes do teste j/10) e artigo (quadrados).")
rows = []
from figuras import PAPER as PAP  # noqa: E402

for (pH, j), p in sorted(PAP.items()):
    r = DATA.get((pH, j))
    rows.append([
        str(pH), str(j),
        f(r["co2_min"]) if r else "n/d", f(p.get("co2_min"), 0) if p.get("co2_min") is not None else "—",
        f(r["x_co2_min"]) if r else "n/d", f(p.get("x_co2_min"), 0) if p.get("x_co2_min") is not None else "—",
        f(r["pH_s"]) if r else "n/d", f(p.get("pH_s")),
        (f(r["front"]) if r and r["front"] is not None else "—") if r else "n/d", f(p.get("front"), 0) if p.get("front") is not None else "—",
    ])
n_tcmp = table(["pH", "j", "CO_{2} mín KFem", "artigo", "x(mín) KFem", "artigo", "pH sup. KFem", "artigo", "frente KFem", "artigo"], rows,
               "Indicadores do estado estacionário: KFem e valores lidos das Figuras S2/S3 (CO_{2} em mM, posições em µm, frente = primeiro x com pH < 6).",
               widths=[1.0, 1.1, 1.9, 1.4, 1.9, 1.4, 1.9, 1.4, 1.9, 1.5], size=8.5)
para("O acordo é bom em três pontos:")
bullet("superfície ácida com pH 0 e com corrente baixa;")
bullet("pH da superfície alcalina entre 11,5 e 13, contra 11–12 no artigo;")
bullet("forma e posição do vale de CO_{2} e da frente com pH 3 e 4.")
para("Há duas diferenças sistemáticas:")
bullet(f"com pH 2, o KFem já alcaliniza a superfície a {f(tr2_lit[1], 0)} mA cm^{{-2}}, enquanto o artigo mostra superfície ácida até 100 mA cm^{{-2}};", "(i) transição ácido→alcalino: ")
bullet(f"o CO_{{2}} mínimo do KFem é sempre menor que o do artigo; com pH 3 e 4, o valor do artigo aparece no KFem com correntes cerca de {f(r_mean, 1)} vezes menores (Seção 6.2).", "(ii) depleção de CO_{2}: ")

# ------------------------------------------------------------------ resultados 2D
doc.add_heading("4. Resultados do modelo 2D", level=1)
doc.add_heading("4.1 Campos de CO₂ e pH", level=2)
n6 = figure("fig2d_zoom_pH2_j500.png", "CO_{2} e pH perto do eletrodo (25 µm inferiores) com pH 2 e 500 mA cm^{-2}, nas três formas. Em cinza, o corpo do eletrodo (fora do domínio de cálculo).")
n7 = figure("fig2d_mapa_pH2_j500.png", "O mesmo caso no domínio inteiro (até o eletrólito, em y = 100 µm). A linha branca é a frente pH = 6.")
para(
    f"Nas três formas, o CO_{{2}} cai de 32 mM na interface para quase zero em cerca de 15 µm, e a região alcalina ocupa quase toda a "
    f"célula (Figuras {n6} e {n7}). A frente ácido-base fica a {d2(2, 500, 'plano', 'y_front', 1)} µm da base no plano, "
    f"{d2(2, 500, 'convexo', 'y_front', 1)} µm no convexo e {d2(2, 500, 'conico', 'y_front', 1)} µm no pontiagudo: quanto mais alcalina a "
    "superfície, mais a frente é empurrada para o eletrólito. Acima da frente, como no 1D, o CO_{2} regenerado passa da saturação."
)
figure("fig2d_zoom_pH2_j200.png", "CO_{2} e pH perto do eletrodo com pH 2 e 200 mA cm^{-2}.")
figure("fig2d_zoom_pH4_j500.png", "CO_{2} e pH perto do eletrodo com pH 4 e 500 mA cm^{-2}.")
doc.add_heading("4.2 pH e CO₂ ao longo do eletrodo", level=2)
n8 = figure("fig2d_eletrodo.png", "Ao longo do eletrodo (0 = centro ou ápice; ±10 µm = pés): pH na interface gás-líquido (em cima) e CO_{2} no meio da CL, a 0,2 µm da interface (embaixo).")
para(
    f"No plano, pH e CO_{{2}} são uniformes ao longo do eletrodo (Figura {n8}). Nas formas curvas há um gradiente claro: o pH é máximo "
    "nos pés, junto às paredes de simetria, e mínimo no centro (convexo) ou no ápice (pontiagudo). O CO_{2} no meio da CL tem o mesmo "
    "padrão, mais alto nos pés e mais baixo no topo."
)
para(
    "Os pés ficam num canto confinado entre o eletrodo e o vizinho (a parede de simetria): o OH^{-} produzido ali se acumula, porque o "
    "volume de líquido disponível para diluí-lo é pequeno. O topo se projeta para o eletrólito e troca espécies com um volume maior, "
    "recebendo mais H^{+} e perdendo OH^{-} mais depressa. No ápice do pontiagudo, o pH tem um mínimo em bico e o CO_{2} no meio da CL "
    "tem uma queda brusca; parte dessa queda é geométrica (num canto vivo, a direção normal não é única e o ponto amostrado a 0,2 µm cai "
    "fora da faixa da CL), por isso as comparações entre formas usam as médias ao longo do eletrodo."
)
doc.add_heading("4.3 Indicadores", level=2)
rows = []
for pH, j in CASES2D:
    for s in SHAPES:
        r = D2.get((pH, j, s))
        if not r:
            continue
        rows.append([str(pH), str(j), SLAB[s], f(r["pH_el_mean"], 2), f"{f(r['pH_el_min'], 2)}–{f(r['pH_el_max'], 2)}",
                     f(r.get("co2_cl_mean"), 1), f(r["co2_min"], 2), f(r["y_front"], 1) if r["y_front"] is not None else "—"])
n_t2d = table(["pH", "j", "Forma", "pH médio", "pH mín–máx", "CO_{2} na CL (mM)", "CO_{2} mín (mM)", "frente (µm)"], rows,
              "Indicadores 2D no estado estacionário. pH e CO_{2} na CL são médias ao longo do eletrodo ponderadas pelo arco; a frente é a menor altura com pH < 6.",
              widths=[1.0, 1.0, 2.7, 1.7, 2.6, 2.5, 2.4, 2.1], size=9)
para(
    f"A ordem convexo > pontiagudo > plano no pH médio vale nas três condições (Tabela {n_t2d}). A diferença convexo − plano é de "
    f"{f(D2[(2, 500, 'convexo')]['pH_el_mean'] - D2[(2, 500, 'plano')]['pH_el_mean'], 2)} unidades de pH com pH 2 / 500, "
    f"{f(D2[(2, 200, 'convexo')]['pH_el_mean'] - D2[(2, 200, 'plano')]['pH_el_mean'], 2)} com pH 2 / 200 e "
    f"{f(D2[(4, 500, 'convexo')]['pH_el_mean'] - D2[(4, 500, 'plano')]['pH_el_mean'], 2)} com pH 4 / 500. Já o CO_{{2}} médio no meio da "
    f"CL é praticamente o mesmo nas três formas ({co2cl_rng}): a CL fica colada à interface gás-líquido, onde o CO_{{2}} é reposto. O que "
    "muda com a forma é a distribuição ao longo do eletrodo (Figura "
    f"{n8}) e o vale de CO_{{2}} mais longe da superfície: o CO_{{2}} mínimo no domínio é menor nas formas curvas."
)

# ------------------------------------------------------------------ análise integrada
doc.add_heading("5. Análise integrada 1D + 2D", level=1)
para(
    "O 1D e o 2D respondem perguntas diferentes. O 1D varre o espaço de condições (pH do eletrólito × corrente) a custo baixo e mostra "
    "onde ficam os regimes: superfície ácida, transição e superfície alcalina com frente ácido-base. O 2D é caro (horas por caso) e "
    "responde como a forma do eletrodo muda o resultado num ponto desse espaço. Esta seção usa o 1D para decompor o efeito da forma."
)
doc.add_heading("5.1 O que a forma muda: corrente por área de base", level=2)
para(
    f"Com a mesma corrente total, as formas curvas ocupam uma base mais estreita (Eq. {n_jp}). Longe do eletrodo, onde o eletrólito "
    "fornece o H^{+} que neutraliza o OH^{-}, só importa o fluxo médio por área de base. Esse fluxo é j_{proj} = j·L_{s}/w: "
    f"{f(FAC['convexo'], 2)} j no convexo e {f(FAC['conico'], 2)} j no pontiagudo. A ordem convexo > pontiagudo > plano do pH médio é "
    "exatamente a ordem de L_{s}/w."
)
para(
    "Para testar essa ideia, rodou-se o 1D nas correntes projetadas de cada forma curva (Seção 2.9) e comparou-se com o 2D em duas "
    "regiões: longe do eletrodo (posição da frente ácido-base) e na superfície (pH médio e CO_{2} na CL). Para a superfície, define-se "
    "a fração φ do ganho de pH previsto pela corrente projetada que o 2D de fato tem:"
)
bullet("φ = [pH_{2D} − pH_{1D}(j)] / [pH_{1D}(j_{proj}) − pH_{1D}(j)]; φ = 1 quer dizer que a forma equivale a um plano com corrente j_{proj}, e φ = 0 que ela equivale ao plano com corrente j.")
n9 = figure("fig_integrado.png", "pH na superfície (em cima) e CO_{2} no meio da CL (embaixo) contra a corrente por área de base. Linha: 1D. Símbolos: média 2D de cada forma, colocada na sua corrente projetada (as barras são o mínimo e o máximo ao longo do eletrodo; as setas partem da corrente nominal).")
rows = []
for pH, j in CASES2D:
    for s_ in SHAPES:
        r = INTD.get((pH, j, s_))
        if not r:
            continue
        dd = decomp(pH, j, s_) if s_ != "plano" else None
        fr = "—" if r["front_2d"] is None else f"{f(r['front_2d'], 1)} / {f(r['front_1d_proj'], 1)}"
        rows.append([str(pH), str(j), SLAB[s_], f(r["j_proj"], 0), fr, f(r["pH_2d_mean"], 3), f(r["pH_1d_nominal"], 3), f(r["pH_1d_proj"], 3),
                     f(dd[0] / dd[1], 2) if dd and abs(dd[1]) > 1e-6 else "—"])
n_tint = table(["pH", "j", "Forma", "j_{proj}", "frente 2D / 1D(j_{proj}) (µm)", "pH 2D (média)", "pH 1D (j)", "pH 1D (j_{proj})", "φ"], rows,
               "Comparação do 2D com o 1D na corrente nominal e na corrente projetada (correntes em mA cm^{-2}). Com pH 4, a frente fica no contorno do eletrólito e não é definida no 2D.",
               widths=[1.0, 0.9, 2.5, 1.3, 3.1, 2.0, 1.7, 2.0, 1.1], size=8.5)
doc.add_heading("5.2 Longe do eletrodo: vale a corrente projetada", level=2)
para(
    f"A posição da frente ácido-base no 2D coincide com a do 1D na corrente projetada, com diferença de no máximo {f(front_dmax, 1)} µm "
    f"(Tabela {n_tint}). A frente fica a 90–97 µm da base, longe da forma do eletrodo, onde o campo de concentrações já é uniforme em x. "
    "Ali o eletrólito só “enxerga” o fluxo médio de OH^{-} por área de base, ou seja, j_{proj}. O mesmo vale para o balanço de prótons da "
    "Seção 6.1, que é um balanço de fluxos entre a superfície e o eletrólito."
)
doc.add_heading("5.3 Na superfície: entre a corrente nominal e a projetada", level=2)
para(
    f"Na superfície, o 1D na corrente projetada superestima o pH do 2D (Figura {n9}). O pH médio 2D fica entre os dois 1D, com φ = "
    f"{f(phi_rng[0], 2)}–{f(phi_rng[1], 2)}: a forma curva entrega à superfície só parte do ganho que a corrente projetada daria."
)
para(
    "A razão é que a forma curva multiplica por L_{s}/w não só a corrente, mas também a interface gás-líquido por onde entra o CO_{2}. "
    f"O CO_{{2}} no meio da CL fica no nível do eletrodo plano ({f(min(_cl2), 1)}–{f(max(_cl2), 1)} mM a 500 mA cm^{{-2}}), enquanto no 1D "
    f"na corrente projetada ele cai para {f(min(_cl1), 1)}–{f(max(_cl1), 1)} mM. Com mais CO_{{2}} junto à superfície, mais OH^{{-}} é "
    "consumido pela reação CO_{2} + OH^{-} → HCO_{3}^{-} (r_{3}) dentro e perto da CL, e o pH sobe menos do que num plano com a mesma "
    "corrente por área. Some-se a isso a redistribuição ao longo do eletrodo (pés mais alcalinos que o topo, Seção 4.2): a média "
    "ponderada pelo arco não é igual ao valor de um eletrodo plano."
)
doc.add_heading("5.4 Como as análises se completam", level=2)
para("Juntas, as duas análises dão uma leitura do sistema que nenhuma dá sozinha:")
bullet(
    f"o 1D mostra que a alcalinização da superfície depende do balanço entre o OH^{{-}} produzido (∝ j) e o H^{{+}} que o eletrólito "
    f"consegue fornecer (∝ 10^{{-pH}}), com limiar j* ≈ {f(jstar(2), 1)} mA cm^{{-2}} para pH 2;",
    "Regime (1D): ",
)
bullet(
    f"para a mesma área ativa, a forma age como um multiplicador da corrente por área de base (L_{{s}}/w) no campo distante. Pelo "
    f"balanço de prótons, um arranjo de eletrodos convexos alcalinizaria com pH 2 já a cerca de j*/{f(FAC['convexo'], 2)} ≈ "
    f"{f(jstar(2) / FAC['convexo'], 1)} mA cm^{{-2}} de corrente por área ativa (estimativa, não simulada);",
    "Deslocamento no mapa (1D + 2D): ",
)
bullet(
    "o 1D na corrente nominal e o 1D na corrente projetada delimitam o pH médio 2D por baixo e por cima; o CO_{2} na CL segue o 1D na "
    "corrente nominal;",
    "Limites para a superfície (1D + 2D): ",
)
bullet(
    "o 2D acrescenta o que o 1D não tem: o gradiente ao longo do eletrodo. Num eletrodo curvo, os pés trabalham mais alcalinos e com "
    "mais CO_{2} na CL do que o topo, ou seja, a seletividade local, que depende do pH, varia ao longo da superfície;",
    "Distribuição (2D): ",
)
bullet("o plano em 2D reproduz o 1D, o que valida as duas implementações uma contra a outra.", "Verificação cruzada: ")

# ------------------------------------------------------------------ discussão
doc.add_heading("6. Discussão", level=1)
doc.add_heading("6.1 Balanço de prótons e o limiar de alcalinização", level=2)
para(
    "A transição ácido→alcalino pode ser estimada sem resolver o modelo. Em regime estacionário, todo o OH^{-} produzido na CL "
    "(2R_{CO2RR}·L_{cat} = εj/F por unidade de área) precisa ser neutralizado pelo H^{+} que chega do eletrólito por difusão. Esse "
    "suprimento tem um máximo, quando [H^{+}] → 0 na superfície:"
)
n_bal = equation("eq16_balanco")
rows = [[str(pH), f(jstar(pH), 2 if jstar(pH) < 10 else 1)] for pH in (0, 1, 2, 3, 4)]
table(["pH do eletrólito", "j* (mA cm^{-2})"], rows, f"Corrente-limiar de alcalinização estimada pela Eq. {n_bal} (D_{{H}} = 9,311×10^{{-5}} cm^{{2}} s^{{-1}}, ε = 0,6, L = 100 µm).", widths=[5.0, 5.0])
para(
    f"Com pH 2, j* ≈ {f(jstar(2), 1)} mA cm^{{-2}}, e o KFem coloca a transição entre {f(tr2_lit[0], 0)} e {f(tr2_lit[1], 0)} mA cm^{{-2}}. "
    f"Com pH 1, j* ≈ {f(jstar(1), 0)} mA cm^{{-2}}"
    + (f", e o KFem dá superfície quase neutra em {f(tr1[0], 0)} (pH {g(1, 150, 'pH_s', 2)}) e alcalina a partir de {f(tr1[1], 0)} mA cm^{{-2}}." if tr1[0] and tr1[1] else ".")
    + " O pequeno excesso vem do tampão carbonato (o CO_{2} consome OH^{-} pela r_{3})."
)
para(
    "O artigo mostra a transição com pH 2 entre 100 e 150 mA cm^{-2}, 8–10 vezes acima de j*, e superfície ácida com pH 1 mesmo a "
    "750 mA cm^{-2}. Essa diferença não é numérica: o balanço é exato para as equações e os parâmetros publicados, não depende da malha "
    "nem do integrador, e o KFem coincide com ele. O modelo original deve diferir do texto em algum ponto, por exemplo na escala da "
    "corrente ou da taxa (Eq. S2), no D do H^{+} ou na espessura da camada de difusão, ou numa fração da corrente que não produz OH^{-}."
)
doc.add_heading("6.2 Depleção de CO₂", level=2)
rows = [[str(pH), str(j), f(c, 0), f(jj, 0), f(rr, 2)] for pH, j, c, jj, rr in ratios]
table(["pH", "j do artigo", "CO_{2} mín no artigo (mM)", "j no KFem com o mesmo CO_{2} mín", "razão"], rows,
      "Corrente do KFem que reproduz o CO_{2} mínimo lido no artigo (interpolação linear entre os casos calculados; abaixo de 100 mA cm^{-2}, extrapolação a partir de 100–150).", widths=[1.5, 2.5, 4.0, 5.0, 2.0])
para(
    f"Com pH 3 e 4, o CO_{{2}} mínimo do artigo é reproduzido no KFem com uma corrente cerca de {f(r_mean, 1)} vezes menor (mediana; faixa "
    f"{f(_rs[0], 1) if _rs else '—'}–{f(_rs[-1], 1) if _rs else '—'}), de forma bastante constante entre 100 e 750 mA cm^{{-2}}. Isso "
    "indica uma diferença de escala no consumo de CO_{2}. Esse fator, porém, é diferente do fator ≈ 8–10 do limiar de pH: uma única "
    "correção de escala na corrente não reconcilia as duas observações."
)
doc.add_heading("6.3 Teste da hipótese “corrente dividida por 10”", level=2)
n10 = figure("fig_hipotese.png", "pH 2 com as correntes divididas por 10 (10–75 mA cm^{-2}), comparadas com as do artigo (100–750 mA cm^{-2}).")
para(
    f"Com a corrente dividida por 10 (Figura {n10}), o limiar de pH com pH 2 fica entre {f(tr2_lit[0], 0)} e {f(tr2_lit[1], 0)} mA cm^{{-2}}, "
    f"o equivalente a {f((tr2_lit[0] or 0) * 10, 0)}–{f((tr2_lit[1] or 0) * 10, 0)} na escala do artigo, perto dos 100–150 publicados. "
    f"Em compensação, a depleção de CO_{{2}} fica fraca demais: a 75 mA cm^{{-2}} (equivalente a 750) o mínimo é {g(2, 75, 'co2_min')} mM, "
    "contra ≈ 19 mM no artigo. A hipótese explica o limiar de pH, mas não o consumo de CO_{2}."
)
doc.add_heading("6.4 Regeneração de CO₂ na frente ácida", level=2)
para(
    f"Com pH 2, o CO_{{2}} passa da saturação ({g(2, 100, 'co2_max')} mM contra 32,1 mM, a 100 mA cm^{{-2}}) logo antes da frente "
    "ácido-base. O HCO_{3}^{-} e o CO_{3}^{2-} formados na região alcalina difundem até a frente, onde o H^{+} do eletrólito os converte "
    "de volta em CO_{2}. Parte desse CO_{2} volta para a superfície e parte sai para o eletrólito. É o mecanismo que o artigo usa para "
    "justificar a alta utilização de carbono em meio ácido, e ele aparece igualmente no 2D (Figura "
    f"{n7}). Com pH 1 e superfície alcalina, o efeito é muito mais forte: {g(1, 500, 'co2_max', 0)} mM a 500 mA cm^{{-2}}. Como o modelo "
    "não tem fase gasosa, esses valores são um limite superior do CO_{2} regenerado, não concentrações reais."
)
doc.add_heading("6.5 Artefatos das variáveis primitivas", level=2)
neg = [(k, r["neg"]["H"]) for k, r in DATA.items() if r.get("neg") and r["neg"]["H"] < 0]
mneg = min(v for _, v in neg) if neg else 0
para(
    f"Em {len(neg)} dos {n_cases} casos 1D, o H^{{+}} fica ligeiramente negativo em poucos nós, exatamente na frente ácido-base "
    f"(mínimo {f(mneg * 1000, 1)} µM, contra [H^{{+}}]_{{b}} = 10 mM com pH 2). Ali o H^{{+}} e o OH^{{-}} se aniquilam numa espessura de "
    "dezenas de nanômetros, menor que a malha, e uma aproximação P1 com variáveis primitivas oscila. O “eps” do artigo impede as taxas "
    "de usarem valores negativos, mas não impede a incógnita de ficar negativa; o COMSOL, com a mesma formulação, tem o mesmo "
    "comportamento. No 2D, refinar a malha junto ao eletrólito reduziu esse valor cerca de 10 vezes sem mudar nenhum indicador (Seção 2.10)."
)
doc.add_heading("6.6 Por que as formas curvas são mais alcalinas", level=2)
para(
    "A análise integrada (Seção 5) mostra que a causa principal é a concentração de corrente sobre uma base mais estreita, atenuada "
    "na superfície pelo CO_{2} que entra por uma interface também maior. A geometria acrescenta um efeito local que redistribui o pH: "
    "o OH^{-} se acumula nos cantos confinados entre eletrodos e é diluído no topo, exposto ao eletrólito. Para a CO_{2}RR isso tem dois lados. Uma superfície mais alcalina favorece o acoplamento C–C (produtos C_{2+}) "
    "e suprime a evolução de hidrogênio, mas também converte mais CO_{2} em carbonato na camada de difusão, o que aprofunda o vale de "
    f"CO_{{2}} (Tabela {n_t2d}). Na própria CL, porém, o CO_{{2}} médio quase não muda com a forma ({co2cl_rng}), porque ela é "
    "alimentada diretamente pela interface gás-líquido. Neste modelo, portanto, a forma mexe sobretudo no pH local, e pouco no CO_{2} "
    "disponível para a reação."
)
para(
    "Este modelo não tem cinética dependente do potencial nem campo elétrico; por isso ele não captura o efeito mais conhecido das "
    "pontas, a concentração de campo e de cátions. O efeito encontrado aqui é puramente de transporte e reação homogênea."
)
doc.add_heading("6.7 Limitações", level=2)
bullet("Valores do artigo lidos visualmente das figuras (±1 mM; ±0,3 de pH; ±3 µm).")
bullet("Sem fase gasosa no eletrólito: o CO_{2} regenerado pode ficar supersaturado.")
bullet("Sem migração eletrostática nem eletroneutralidade, como no artigo; o K^{+} e o SO_{4}^{2-} não entram explicitamente.")
bullet("Constantes a 293,15 K da Tabela S1, sem as correções de salinidade citadas no texto do artigo, que não foram publicadas.")
bullet("Valor do “eps” não publicado (adotado 10^{-15} mol m^{-3}).")
bullet("2D: um corte 2D representa uma crista infinitamente longa (semicilindro, prisma), não um domo ou um cone 3D isolado; num cone 3D a concentração de corrente no ápice seria maior.")
bullet("2D: corrente uniforme na CL (Eq. S2 do artigo); a distribuição real de corrente sobre uma superfície curva depende do potencial local, que o modelo não resolve.")

# ------------------------------------------------------------------ conclusões
doc.add_heading("7. Conclusões", level=1)
concl(1, "O modelo de Xie et al. (2022) foi reproduzido no KFem com a mesma metodologia: equações S1–S21, parâmetros das Tabelas S1–S3, malha de 0,1 µm, estudo dependente do tempo até o estado estacionário, tolerância relativa de 0,01, MUMPS e “eps”.")
concl(2, "O KFem recupera os fenômenos qualitativos do artigo: superfície alcalina em eletrólito ácido, frente ácido-base estreita, vale de CO_{2}, regeneração de CO_{2} na frente e superfície ácida com pH 0.")
concl(3, f"Com os parâmetros literais, o limiar de alcalinização com pH 2 é {f(tr2_lit[0], 0)}–{f(tr2_lit[1], 0)} mA cm^{{-2}}, contra 100–150 no artigo; o balanço de prótons (Eq. {n_bal}) confirma que esse é o resultado das equações publicadas. A depleção de CO_{{2}} do artigo corresponde a correntes cerca de {f(r_mean, 1)} vezes menores.")
concl(4, "Em 2D, com a mesma área ativa e a mesma corrente total, a superfície é mais alcalina no convexo, depois no pontiagudo e por último no plano, em todas as condições estudadas; nas formas curvas, os pés são mais alcalinos que o topo.")
concl(5, f"A forma age pela concentração de corrente sobre a base mais estreita (fator L_{{s}}/w): longe do eletrodo, o 1D na corrente projetada reproduz a frente ácido-base do 2D (diferença ≤ {f(front_dmax, 1)} µm). Na superfície, o 2D recebe {f(100 * phi_rng[0], 0)}–{f(100 * phi_rng[1], 0)}% do ganho de pH dessa corrente maior, porque a interface que fornece CO_{{2}} também cresce; o CO_{{2}} na CL fica no nível do plano.")
concl(6, "O eletrodo plano em 2D reproduz o 1D (diferença de CO_{2} abaixo de 0,1 mM), e os resultados 1D e 2D são independentes da malha.")

# ------------------------------------------------------------------ reprodutibilidade
doc.add_heading("8. Reprodutibilidade", level=1)
para("Os arquivos ficam em examples/xie2022_co2rr/ no repositório do KFem, e as entradas de todos os casos em Simulations/1D e Simulations/2D do pacote de distribuição:")
for nm, d in (
    ("modelo.py", "constrói o modelo 1D para um pH e uma corrente;"),
    ("modelo2d.py", "constrói o modelo 2D para uma forma, um pH e uma corrente;"),
    ("analisar.py", "extrai perfis e indicadores de um caso 1D;"),
    ("figuras.py, figuras2d.py, integrado.py, verifica.py, esquema.py", "geram as figuras e os indicadores deste relatório;"),
    ("equacoes.py, relatorio.py", "renderizam as equações e geram este documento."),
):
    bullet(d, nm + " — ")
para("Com o AppImage do KFem, um caso se calcula assim:")
mono("KFem-x86_64.AppImage --python modelo2d.py conico 2 500 pH2_j500_conico.kfem")
mono("KFem-x86_64.AppImage --solve pH2_j500_conico.kfem --workdir pH2_j500_conico")
mono("KFem-x86_64.AppImage --python figuras2d.py figuras .")
para(
    "Os casos rodaram numa estação Ubuntu 24.04 (12 threads), com 1 processo MPI por caso e vários casos em paralelo, no backend de CPU "
    "com MUMPS, como no artigo. Os casos 1D levam de segundos a 3 h; os 2D, de 1,2 h (pH 4) a 16 h (pH 2 / 200)."
)

doc.add_heading("Apêndice A — Melhorias no KFem feitas para este estudo", level=1)
bullet("Operador dt() aplicado a expressões, além de campos.", "Forma fraca: ")
bullet("BDF1→BDF2 de passo variável com rejeição e recuo de ¼ do passo.", "Passo adaptativo: ")
bullet("O problema PETSc é recriado após erro de estado, e o passo é tratado como rejeitado.", "Recuperação de falhas: ")
bullet("snes_atol = 0 (o resíduo absoluto depende da escala do domínio), busca linear bt e divergence_tolerance desativada.", "Critérios do Newton: ")
bullet("polígono, diferença e interseção booleanas; montagem na unidade do componente e escala para metros no fim, o que evita perder detalhes submicrométricos na tolerância do OCC; faixa fina (dfine) no tamanho local de malha.", "Geometria: ")
bullet("kfem --watch acompanha na interface um cálculo iniciado fora dela; o AppImage roda scripts com --python.", "Uso: ")

doc.save(OUT)
print("salvo:", OUT, f"({n_cases} casos 1D, {len(D2)} casos 2D, {_fig[0]} figuras, {_tab[0]} tabelas, {_eq[0]} equações)")
