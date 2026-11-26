"""Gera os PDFs do manual e do tutorial a partir dos Markdown de docs/usuario.

    python docs/tools/gerar_pdfs.py

Entrada: docs/usuario/manual.md e docs/usuario/tutorial.md (subconjunto de Markdown:
títulos, parágrafos, listas, tabelas, blocos de código, citações e imagens).
Saída: docs/usuario/KFem-Manual.pdf e docs/usuario/KFem-Tutorial.pdf.
Precisa do reportlab (ferramenta de documentação; não vai no AppImage).
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "usuario"
LOGO = ROOT / "packaging" / "icons" / "kfem-source.png"
VERSION = "0.1.0.dev0"

# paleta do KFem (CLAUDE.md §9), ajustada para papel branco
LILAC = colors.HexColor("#6E4FA3")  # lilás escurecido: contraste AA sobre branco
LILAC_SOFT = colors.HexColor("#EFE8F8")
GREEN = colors.HexColor("#1F5B3A")
GREEN_SOFT = colors.HexColor("#E6F2EA")
INK = colors.HexColor("#1B1B22")
MUTED = colors.HexColor("#5C5666")
CODE_BG = colors.HexColor("#F3F1F6")
COVER_BG = colors.HexColor("#0B0B0D")

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Oblique", str(FONT_DIR / "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONT_DIR / "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Oblique", boldItalic="Sans-Bold")

S = {
    "body": ParagraphStyle("body", fontName="Sans", fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5),
    "h1": ParagraphStyle(
        "h1", fontName="Sans-Bold", fontSize=19, leading=24, textColor=LILAC, spaceBefore=4, spaceAfter=10
    ),
    "h2": ParagraphStyle(
        "h2", fontName="Sans-Bold", fontSize=13.5, leading=18, textColor=GREEN, spaceBefore=12, spaceAfter=6
    ),
    "h3": ParagraphStyle(
        "h3", fontName="Sans-Bold", fontSize=11, leading=15, textColor=INK, spaceBefore=8, spaceAfter=4
    ),
    "cell": ParagraphStyle("cell", fontName="Sans", fontSize=8.3, leading=11, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="Sans-Bold", fontSize=8.3, leading=11, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.2, leading=11, textColor=INK),
    "caption": ParagraphStyle(
        "caption",
        fontName="Sans-Oblique",
        fontSize=8.3,
        leading=11,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceBefore=3,
        spaceAfter=10,
    ),
    "note": ParagraphStyle(
        "note",
        fontName="Sans",
        fontSize=9.2,
        leading=13,
        textColor=INK,
        backColor=GREEN_SOFT,
        borderPadding=(6, 8, 6, 8),
        spaceBefore=4,
        spaceAfter=9,
        leftIndent=4,
        rightIndent=4,
    ),
    "toc0": ParagraphStyle("toc0", fontName="Sans-Bold", fontSize=10.5, leading=16, leftIndent=0),
    "toc1": ParagraphStyle("toc1", fontName="Sans", fontSize=9.4, leading=13, leftIndent=14),
}

_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+−")


def inline(text: str) -> str:
    """Markdown inline → marcação do reportlab (negrito, código, links, sobrescritos)."""
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    codes: list[str] = []

    def keep_code(m: re.Match[str]) -> str:
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    t = re.sub(r"`([^`]+)`", keep_code, t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)  # links: só o texto
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+", lambda m: f"<super>{m.group(0).translate(_SUP)}</super>", t)
    for i, c in enumerate(codes):
        t = t.replace(f"\x00{i}\x00", f'<font name="Mono" size="8.6" color="#4B2E83">{c}</font>')
    return t


def image_flow(path: Path, caption: str, max_w: float, max_h: float = 15 * cm) -> list:
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    img = Image(str(path), width=w * scale, height=h * scale)
    img.hAlign = "CENTER"
    return [KeepTogether([img, Paragraph(inline(caption), S["caption"])])]


def table_flow(rows: list[list[str]], width: float) -> Table:
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    lens = [max(len(r[i]) for r in rows) for i in range(ncol)]
    tot = sum(min(max(n, 6), 70) for n in lens)
    colw = [width * min(max(n, 6), 70) / tot for n in lens]
    data = [[Paragraph(inline(c), S["cellh"] if i == 0 else S["cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=colw, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LILAC_SOFT]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CFC6DC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def md_to_flowables(md: str, base: Path, width: float) -> list:
    out: list = []
    lines = md.splitlines()
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(Paragraph(inline(" ".join(s.strip() for s in para)), S["body"]))
            para.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            flush()
            i += 1
            continue
        m = re.match(r"^(#{1,3}) (.+)$", s)
        if m:
            flush()
            level = len(m.group(1))
            if level == 1 and out:
                out.append(PageBreak())
            out.append(Paragraph(inline(m.group(2)), S[f"h{level}"]))
            i += 1
            continue
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", s)
        if m:
            flush()
            out += image_flow((base / m.group(2)).resolve(), m.group(1), width)
            i += 1
            continue
        if s.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            txt = "\n".join(code)
            # quebra linhas longas (comandos apt) para caber na página
            wrapped = []
            for cl in txt.splitlines():
                while len(cl) > 92:
                    cut = cl.rfind(" ", 0, 92)
                    cut = cut if cut > 20 else 92
                    wrapped.append(cl[:cut] + " \\")
                    cl = "    " + cl[cut:].lstrip()
                wrapped.append(cl)
            box = Table([[Preformatted("\n".join(wrapped), S["code"])]], colWidths=[width])
            box.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                        ("LINEBEFORE", (0, 0), (0, -1), 2.2, LILAC),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            out.append(box)
            out.append(Spacer(1, 6))
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append(table_flow(rows, width))
            out.append(Spacer(1, 7))
            continue
        if s.startswith("> "):
            flush()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(Paragraph(inline(" ".join(q)), S["note"]))
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.) (.+)$", ln)
        if m:
            flush()
            ordered = m.group(2)[0].isdigit()
            contents: list[list] = []  # cada item: [parágrafo, (sub-lista)]
            while i < len(lines):
                mm = re.match(r"^(\s*)([-*]|\d+\.) (.+)$", lines[i])
                if mm and len(mm.group(1)) == len(m.group(1)):
                    text = [mm.group(3)]
                    i += 1
                    while (
                        i < len(lines)
                        and lines[i].startswith(" " * (len(m.group(1)) + 2))
                        and not re.match(r"^\s*([-*]|\d+\.) ", lines[i])
                    ):
                        text.append(lines[i].strip())
                        i += 1
                    contents.append([Paragraph(inline(" ".join(text)), S["body"])])
                elif mm and len(mm.group(1)) > len(m.group(1)) and contents:
                    sub = []
                    while i < len(lines) and re.match(rf"^\s{{{len(m.group(1)) + 1},}}([-*]|\d+\.) ", lines[i]):
                        sub.append(lines[i].strip()[2:].strip())
                        i += 1
                    contents[-1].append(
                        ListFlowable(
                            [ListItem(Paragraph(inline(x), S["body"]), leftIndent=12) for x in sub],
                            bulletType="bullet",
                            start="◦",
                            leftIndent=12,
                            bulletFontName="Sans",
                            bulletColor=LILAC,
                        )
                    )
                else:
                    break
            items = [ListItem(c if len(c) > 1 else c[0], leftIndent=14) for c in contents]
            out.append(
                ListFlowable(
                    items,
                    bulletType="1" if ordered else "bullet",
                    start="1" if ordered else "•",
                    leftIndent=14,
                    bulletFontName="Sans",
                    bulletColor=LILAC,
                )
            )
            continue
        para.append(s)
        i += 1
    flush()
    return out


class Doc(BaseDocTemplate):
    def __init__(self, path: Path, title: str, subtitle: str) -> None:
        super().__init__(
            str(path),
            pagesize=A4,
            leftMargin=2.0 * cm,
            rightMargin=2.0 * cm,
            topMargin=2.2 * cm,
            bottomMargin=2.0 * cm,
            title=title,
            author="Projeto KFem",
            subject=subtitle,
            creator="KFem docs",
        )
        self.doc_title, self.subtitle = title, subtitle
        fr = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[fr], onPage=self.cover),
                PageTemplate(id="body", frames=[fr], onPage=self.decor),
            ]
        )

    def cover(self, c, doc) -> None:
        W, H = A4
        c.saveState()
        c.setFillColor(COVER_BG)
        c.rect(0, 0, W, H, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#3A2F4D"))
        c.rect(0, 0, W, 5.2 * cm, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1F5B3A"))
        c.rect(0, 5.2 * cm, W, 0.25 * cm, stroke=0, fill=1)
        size = 9.5 * cm
        c.drawImage(str(LOGO), (W - size) / 2, H - 3.2 * cm - size, size, size, mask="auto")
        c.setFillColor(colors.HexColor("#ECE8F2"))
        c.setFont("Sans-Bold", 30)
        c.drawCentredString(W / 2, H - 15.2 * cm, self.doc_title)
        c.setFillColor(colors.HexColor("#B79CDB"))
        c.setFont("Sans", 13)
        c.drawCentredString(W / 2, H - 16.4 * cm, self.subtitle)
        c.setFillColor(colors.HexColor("#A59FB0"))
        c.setFont("Sans", 10)
        c.drawCentredString(W / 2, H - 17.4 * cm, "Simulador multifísico livre baseado em FEniCSx")
        c.setFillColor(colors.HexColor("#ECE8F2"))
        c.setFont("Sans", 10)
        c.drawString(2 * cm, 3.4 * cm, f"Versão {VERSION}")
        c.drawString(2 * cm, 2.8 * cm, _dt.date.today().strftime("%d/%m/%Y"))
        c.setFillColor(colors.HexColor("#A59FB0"))
        c.setFont("Sans", 8)
        c.drawString(2 * cm, 1.6 * cm, "Software livre sob a licença GPL-3.0-or-later.")
        c.restoreState()

    def decor(self, c, doc) -> None:
        W, H = A4
        c.saveState()
        c.setStrokeColor(LILAC)
        c.setLineWidth(0.6)
        c.line(self.leftMargin, H - 1.5 * cm, W - self.rightMargin, H - 1.5 * cm)
        c.drawImage(str(LOGO), self.leftMargin, H - 1.38 * cm, 0.62 * cm, 0.62 * cm, mask="auto")
        c.setFont("Sans", 8)
        c.setFillColor(MUTED)
        c.drawString(self.leftMargin + 0.8 * cm, H - 1.18 * cm, f"KFem — {self.doc_title}")
        c.drawRightString(W - self.rightMargin, 1.2 * cm, f"{doc.page}")
        c.setFillColor(GREEN)
        c.rect(self.leftMargin, 1.05 * cm, 1.2 * cm, 0.12 * cm, stroke=0, fill=1)
        c.restoreState()

    def afterFlowable(self, fl) -> None:
        if isinstance(fl, Paragraph) and fl.style.name in ("h1", "h2"):
            level = 0 if fl.style.name == "h1" else 1
            text = fl.getPlainText()
            key = f"h{id(fl)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, text, self.page, key))


def build(md_file: Path, pdf: Path, title: str, subtitle: str) -> None:
    md = md_file.read_text(encoding="utf-8")
    md = re.sub(r"^# .+\n", "", md, count=1)  # o título do arquivo vira a capa
    doc = Doc(pdf, title, subtitle)
    toc = TableOfContents()
    toc.levelStyles = [S["toc0"], S["toc1"]]
    story: list = [NextPageTemplate("body"), PageBreak()]
    story += [Paragraph("Sumário", S["h1"]), toc, PageBreak()]
    story += md_to_flowables(md, md_file.parent, doc.width)
    doc.multiBuild(story)
    print(f"{pdf}  ({pdf.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    which = sys.argv[1:] or ["manual", "tutorial"]
    if "manual" in which:
        build(DOCS / "manual.md", DOCS / "KFem-Manual.pdf", "Manual do usuário", "Referência completa")
    if "tutorial" in which:
        build(
            DOCS / "tutorial.md", DOCS / "KFem-Tutorial.pdf", "Tutorial", "Sua primeira simulação de CDI, passo a passo"
        )
