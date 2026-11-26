# ruff: noqa: E501
"""Renderiza as equações do relatório como imagens PNG (matplotlib mathtext).

    python equacoes.py SAIDA
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

EQ = {
    "eq01_reacao": r"$\mathrm{CO_2 + H_2O + 2e^- \;\longrightarrow\; CO + 2OH^-}$",
    "eq02_taxa": r"$R_{\mathrm{CO_2RR}} = \dfrac{j\,\varepsilon}{F\, n\, L_{\mathrm{cat}}},\qquad 0 \leq x \leq L_{\mathrm{cat}}$",
    "eq03_r1": r"$\mathrm{CO_2 + H_2O \;\leftrightarrow\; HCO_3^- + H^+}\qquad r_1 = k_{1f}\,c_{\mathrm{CO_2}} - k_{1r}\,c_{\mathrm{H^+}}\,c_{\mathrm{HCO_3^-}}$",
    "eq04_r2": r"$\mathrm{HCO_3^- \;\leftrightarrow\; CO_3^{2-} + H^+}\qquad r_2 = k_{2f}\,c_{\mathrm{HCO_3^-}} - k_{2r}\,c_{\mathrm{H^+}}\,c_{\mathrm{CO_3^{2-}}}$",
    "eq05_r3": r"$\mathrm{CO_2 + OH^- \;\leftrightarrow\; HCO_3^-}\qquad r_3 = k_{3f}\,c_{\mathrm{CO_2}}\,c_{\mathrm{OH^-}} - k_{3r}\,c_{\mathrm{HCO_3^-}}$",
    "eq06_r4": r"$\mathrm{HCO_3^- + OH^- \;\leftrightarrow\; CO_3^{2-} + H_2O}\qquad r_4 = k_{4f}\,c_{\mathrm{HCO_3^-}}\,c_{\mathrm{OH^-}} - k_{4r}\,c_{\mathrm{CO_3^{2-}}}$",
    "eq07_rw": r"$\mathrm{H_2O \;\leftrightarrow\; OH^- + H^+}\qquad r_w = k_{wf} - k_{wr}\,c_{\mathrm{H^+}}\,c_{\mathrm{OH^-}}$",
    "eq08a_reversas": r"$k_{1r} = \dfrac{k_{1f}}{K_1},\quad k_{2r} = \dfrac{k_{2f}}{K_2},\quad k_{3r} = \dfrac{k_{3f}}{K_3},\quad k_{4r} = \dfrac{k_{4f}}{K_4},\quad k_{wr} = \dfrac{k_{wf}}{K_w}$",
    "eq08b_reversas": r"$K_3 = \dfrac{K_1}{K_w},\qquad K_4 = \dfrac{K_2}{K_w}$",
    "eq09a_fonte": r"$R_{\mathrm{CO_2}} = -r_1 - r_3 - \chi\,R_{\mathrm{CO_2RR}}$",
    "eq09b_fonte": r"$R_{\mathrm{HCO_3^-}} = r_1 - r_2 + r_3 - r_4$",
    "eq09c_fonte": r"$R_{\mathrm{CO_3^{2-}}} = r_2 + r_4$",
    "eq09d_fonte": r"$R_{\mathrm{H^+}} = r_1 + r_2 + r_w$",
    "eq09e_fonte": r"$R_{\mathrm{OH^-}} = -r_3 - r_4 + r_w + 2\,\chi\,R_{\mathrm{CO_2RR}}\qquad (\chi = 1\ \mathrm{na\ camada\ catal\acute{\imath}tica},\ 0\ \mathrm{fora})$",
    "eq10_transporte": r"$\dfrac{\partial c_i}{\partial t} + \nabla\cdot\mathbf{J}_i = R_i,\qquad \mathbf{J}_i = -D_{e,i}\,\nabla c_i$",
    "eq11_bruggeman": r"$D_{e,i} = \dfrac{\varepsilon}{\tau}\,D_i = \varepsilon^{3/2}\,D_i\quad (0 \leq x \leq L_{\mathrm{cat}}),\qquad D_{e,i} = D_i\quad (x > L_{\mathrm{cat}})$",
    "eq12_henry": r"$c_{\mathrm{CO_2},0} = K_0\, p_{\mathrm{CO_2}}$",
    "eq13_sechenov": r"$\log_{10}\dfrac{c_{\mathrm{CO_2},0}}{c_{\mathrm{CO_2}}} = K_s\,C_s,\qquad K_s = \sum_{\mathrm{ion}}(h_{\mathrm{ion}} + h_G),\qquad h_G = h_{G,0} + h_T\,(T - 298{,}15)$",
    "eq14_fraca": r"$\int_\Omega \left( \dfrac{\partial c_i}{\partial t}\, v_i + D_{e,i}\,\nabla c_i\cdot\nabla v_i - R_i\, v_i \right) d\Omega = 0\qquad \forall\, v_i$",
    "eq15_bdf2": r"$\left.\dfrac{\partial c}{\partial t}\right|_{n+1} \approx \dfrac{1+2\omega}{(1+\omega)\,h}\,c^{n+1} - \dfrac{1+\omega}{h}\,c^{n} + \dfrac{\omega^2}{(1+\omega)\,h}\,c^{n-1},\qquad \omega = \dfrac{h}{h_{\mathrm{ant}}}$",
    "eq16_balanco": r"$N_{\mathrm{OH^-}} = \dfrac{\varepsilon\, j}{F}\qquad N_{\mathrm{H^+}}^{\max} \approx \dfrac{D_{\mathrm{H^+}}\, c_{\mathrm{H^+},b}}{L}\qquad j^{*} \approx \dfrac{F\, D_{\mathrm{H^+}}\, c_{\mathrm{H^+},b}}{\varepsilon\, L}$",
    "eq17_eps": r"$c_i \;\rightarrow\; \max(c_i,\;\epsilon)\ \ \mathrm{nas\ taxas}\ r_k,\qquad \epsilon = 10^{-15}\ \mathrm{mol\,m^{-3}}$",
    "eq18_geom2d": r"$\pi R = L_s,\qquad h_{\mathrm{cone}} = R,\qquad 2\sqrt{a^2 + h_{\mathrm{cone}}^2} = L_s\qquad (L_s = 20\ \mu\mathrm{m})$",
    "eq19_taxa2d": r"$R_{\mathrm{CO_2RR}} = \dfrac{j\,\varepsilon\,L_s}{F\,n\,A_{\mathrm{cl}}}\quad \mathrm{em}\ \Omega_{\mathrm{cl}},\qquad \int_{\Omega_{\mathrm{cl}}} \dfrac{n F\,R_{\mathrm{CO_2RR}}}{\varepsilon}\, d\Omega = j\,L_s$",
    "eq20_contornos2d": r"$c_{\mathrm{CO_2}} = c_{\mathrm{sat}}\ \mathrm{em}\ \Gamma_{\mathrm{gl}},\qquad c_i = c_{i,b}\ \mathrm{em}\ y = H,\qquad \mathbf{n}\cdot\mathbf{J}_i = 0\ \mathrm{nas\ paredes\ e\ na\ base\ inerte}$",
    "eq21_jproj": r"$j_{\mathrm{proj}} = \dfrac{j\,L_s}{w}\qquad w_{\mathrm{plano}} = 20,\ \ w_{\mathrm{convexo}} = 2R + 2g = 13{,}93,\ \ w_{\mathrm{c\hat{o}nico}} = 2a = 15{,}42\ \mu\mathrm{m}$",
}


def render(tex: str, path: Path, fontsize: int = 15) -> None:
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=fontsize)
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.06, transparent=False, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, tex in EQ.items():
        try:
            render(tex, out / f"{name}.png")
        except Exception as exc:
            print(f"{name}: {exc}")
    print(f"{len(list(out.glob('eq*.png')))} equações em {out}")
