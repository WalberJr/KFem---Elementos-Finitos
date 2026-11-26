# ruff: noqa: E501
"""Esquemas do domínio 1D e das três geometrias 2D para o relatório.

    python esquema.py SAIDA

Gera SAIDA/fig_esquema_1d.png e SAIDA/fig_esquema_2d.png. Desenhos fora de escala onde
indicado (a CL de 0,4 µm é engrossada para ficar visível).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import modelo2d as m2
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle, Wedge

GRAY = "#9A96A3"
CLC = "#C9472B"
DLC = "#DCEBF7"
EDGE = "#3A3640"


def arrow(ax, p0, p1, color="k", text=None, tpos=None, **kw):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=12, color=color, lw=1.4))
    if text:
        ax.text(*(tpos or p1), text, color=color, fontsize=9, **kw)


def scheme_1d(fname: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 3.3))
    ax.set_xlim(-14, 112)
    ax.set_ylim(-3.2, 5.2)
    ax.axis("off")
    # gás, CL (engrossada), camada de difusão, eletrólito
    ax.add_patch(Rectangle((-12, 0), 12, 2, facecolor="#EEEEEE", edgecolor=EDGE))
    ax.text(-6, 1, "gás\nCO$_2$, 1 atm", ha="center", va="center", fontsize=9)
    ax.add_patch(Rectangle((0, 0), 4, 2, facecolor=CLC, edgecolor=EDGE))
    ax.add_patch(Rectangle((4, 0), 96, 2, facecolor=DLC, edgecolor=EDGE))
    ax.add_patch(Rectangle((100, 0), 10, 2, facecolor="#F6E7B8", edgecolor=EDGE))
    ax.text(105, 1, "eletrólito\npH$_b$", ha="center", va="center", fontsize=9)
    ax.text(6, 2.3, "CL: 0–0,4 µm, ε = 0,6", ha="left", va="bottom", fontsize=8.5, color=CLC)
    ax.text(52, 1, "camada de difusão (0,4–100 µm): difusão + 5 equilíbrios do carbonato", ha="center", va="center", fontsize=9)
    # processos
    arrow(ax, (-9, 2.9), (-0.3, 1.2), "#2E7D4F", "CO$_2$ entra (c = c$_{sat}$)", (-13.5, 3.2))
    ax.text(2, -0.45, "CO$_2$ + H$_2$O + 2e$^-$ → CO + 2OH$^-$", ha="left", va="top", fontsize=9, color=CLC)
    arrow(ax, (99, -1.6), (60, -1.6), "#1D3E8C", "H$^+$ do eletrólito (difusão)", (66, -2.4))
    arrow(ax, (10, -1.6), (40, -1.6), "#B0562A", "OH$^-$, HCO$_3^-$, CO$_3^{2-}$ (difusão)", (10, -2.4))
    # contornos
    ax.annotate("x = 0: fluxo nulo exceto CO$_2$", (0, 2), (8, 4.2), ha="center", fontsize=8.5,
                arrowprops={"arrowstyle": "-", "color": "0.4", "ls": ":"})
    ax.annotate("x = 100 µm\nc$_i$ = c$_{i,b}$ (equilíbrio)", (100, 2), (100, 4.2), ha="center", fontsize=8.5,
                arrowprops={"arrowstyle": "-", "color": "0.4", "ls": ":"})
    ax.text(52, 4.6, "Fora de escala: a CL (0,4 µm) foi engrossada 10 vezes", ha="center", fontsize=8, style="italic", color="0.35")
    fig.tight_layout()
    fig.savefig(fname, dpi=170)
    plt.close(fig)


def _cell(ax, shape: str, title: str) -> None:
    a = m2.half_width(shape)
    H = 24.0  # só a parte de baixo da célula; o resto (até 100 µm) é indicado por quebra
    t = 1.2  # espessura desenhada da CL (real: 0,4 µm), exagerada 3×
    ax.add_patch(Rectangle((-a, 0), 2 * a, H, facecolor=DLC, edgecolor="none"))
    ax.add_patch(Rectangle((-a, -2), 2 * a, 2, facecolor=GRAY, edgecolor=EDGE, lw=0.8))
    if shape == "plano":
        ax.add_patch(Rectangle((-a, 0), 2 * a, t, facecolor=CLC, edgecolor=EDGE, lw=0.6))
    elif shape == "convexo":
        R = m2.R_DOME
        band = Wedge((0, 0), R + t, 0, 180, width=t, facecolor=CLC, edgecolor=EDGE, lw=0.6)
        ax.add_patch(band)
        clip = Rectangle((-a, 0), 2 * a, H, transform=ax.transData, facecolor="none", edgecolor="none")
        ax.add_patch(clip)
        band.set_clip_path(clip)
        ax.add_patch(Wedge((0, 0), R, 0, 180, facecolor=GRAY, edgecolor=EDGE, lw=0.8))
        ax.annotate("", (R, -0.4), (0, -0.4), arrowprops={"arrowstyle": "<->", "lw": 0.8})
        ax.text(R / 2, -1.6, "R", ha="center", fontsize=9)
        ax.annotate("", (a, 0.25), (R, 0.25), arrowprops={"arrowstyle": "<->", "lw": 0.7})
        ax.text(a + 0.4, 0.6, "g = 0,6 µm\n(base inerte)", fontsize=7.5, ha="left")
    else:
        h, b = m2.H_CONE, m2.HALF_CONE
        import math

        k = t * math.hypot(b, h) / b  # deslocamento vertical da faixa
        ax.add_patch(Polygon([(-b, 0), (0, h), (b, 0), (b, min(t, h)), (0, h + k), (-b, min(t, h))],
                             closed=True, facecolor=CLC, edgecolor=EDGE, lw=0.6))
        ax.add_patch(Polygon([(-b, 0), (0, h), (b, 0)], closed=True, facecolor=GRAY, edgecolor=EDGE, lw=0.8))
        ax.annotate("", (0.0, h), (0.0, 0.05), arrowprops={"arrowstyle": "<->", "lw": 0.8})
        ax.text(0.5, h / 2, "h = R", fontsize=8.5)
    # paredes de simetria
    for x in (-a, a):
        ax.plot([x, x], [0, H], color="#5B3F86", lw=2.2, ls=(0, (4, 2)))
    # quebra e topo
    ax.text(0, H + 0.6, "⋮  até y = 100 µm: c$_i$ = c$_{i,b}$", ha="center", va="bottom", fontsize=8.5)
    ax.annotate("", (a, -3.3), (-a, -3.3), arrowprops={"arrowstyle": "<->", "lw": 0.8})
    ax.text(0, -4.8, f"w = {2 * a:.2f} µm".replace(".", ","), ha="center", fontsize=9)
    ax.set_title(title, fontsize=10.5)
    ax.set_xlim(-11, 13)
    ax.set_ylim(-5.5, H + 3)
    ax.set_aspect("equal")
    ax.axis("off")


def scheme_2d(fname: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 5.6))
    _cell(axes[0], "plano", "Plano: L$_s$ = 20 µm")
    _cell(axes[1], "convexo", "Convexo: semicírculo, πR = L$_s$")
    _cell(axes[2], "conico", "Pontiagudo: triângulo, 2 × lado = L$_s$")
    from matplotlib.lines import Line2D

    handles = [
        Rectangle((0, 0), 1, 1, facecolor=CLC, edgecolor=EDGE, label="camada catalítica (0,4 µm; desenhada 3× mais grossa)"),
        Rectangle((0, 0), 1, 1, facecolor=DLC, label="camada de difusão (líquido)"),
        Rectangle((0, 0), 1, 1, facecolor=GRAY, edgecolor=EDGE, label="eletrodo / gás (fora do domínio); c$_{CO_2}$ = c$_{sat}$ na interface"),
        Line2D([], [], color="#5B3F86", lw=2.2, ls=(0, (4, 2)), label="paredes de simetria (fluxo nulo)"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=8.5, frameon=False)
    fig.tight_layout(rect=(0, 0.1, 1, 0.96))
    fig.savefig(fname, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    scheme_1d(out / "fig_esquema_1d.png")
    scheme_2d(out / "fig_esquema_2d.png")
    print("esquemas em", out)
