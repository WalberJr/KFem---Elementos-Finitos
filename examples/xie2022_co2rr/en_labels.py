"""Rótulos das figuras em inglês (para o artigo): importe antes de gerar as figuras.

    import en_labels  # noqa: F401  -- troca os textos do matplotlib de pt-BR para en

Cada texto desenhado pelo matplotlib (títulos, eixos, legendas, anotações) passa por
`translate`, que troca trechos conhecidos e a vírgula decimal por ponto.
"""

from __future__ import annotations

import re

import matplotlib.text as mtext

# frases inteiras ou trechos (aplicados na ordem: os mais longos primeiro)
PT_EN = {
    "Fora de escala: a CL (0,4 µm) foi engrossada 10 vezes": "Not to scale: the CL (0.4 µm) is drawn 10× thicker",
    "camada de difusão (0,4–100 µm): difusão + 5 equilíbrios do carbonato": "diffusion layer (0.4–100 µm): diffusion + 5 carbonate equilibria",
    "camada catalítica (0,4 µm; desenhada 3× mais grossa)": "catalyst layer (0.4 µm; drawn 3× thicker)",
    "eletrodo / gás (fora do domínio); c$_{CO_2}$ = c$_{sat}$ na interface": "electrode / gas (outside the domain); c$_{CO_2}$ = c$_{sat}$ at the interface",
    "corrente por área de base, j$_{proj}$ = j L$_s$/w (mA cm$^{-2}$)": "current per base area, j$_{proj}$ = j L$_s$/w (mA cm$^{-2}$)",
    "posição ao longo do eletrodo (µm; 0 = centro/ápice)": "position along the electrode (µm; 0 = centre/apex)",
    "pH 2 com a corrente dividida por 10 (teste da hipótese)": "pH 2 with current divided by 10 (hypothesis test)",
    "Distância à superfície do eletrodo (µm)": "Distance from the electrode surface (µm)",
    "⋮  até y = 100 µm: c$_i$ = c$_{i,b}$": "⋮  up to y = 100 µm: c$_i$ = c$_{i,b}$",
    "x = 100 µm\nc$_i$ = c$_{i,b}$ (equilíbrio)": "x = 100 µm\nc$_i$ = c$_{i,b}$ (equilibrium)",
    "Pontiagudo: triângulo, 2 × lado = L$_s$": "Pointed: triangle, 2 × side = L$_s$",
    "Convexo: semicírculo, πR = L$_s$": "Convex: semicircle, πR = L$_s$",
    "OH$^-$, HCO$_3^-$, CO$_3^{2-}$ (difusão)": "OH$^-$, HCO$_3^-$, CO$_3^{2-}$ (diffusion)",
    "x = 0: fluxo nulo exceto CO$_2$": "x = 0: no flux except CO$_2$",
    "paredes de simetria (fluxo nulo)": "symmetry walls (no flux)",
    "Transição ácido → alcalino, pH 2": "Acid → alkaline transition, pH 2",
    "CO$_2$ mínimo no domínio (mM)": "minimum CO$_2$ in the domain (mM)",
    "H$^+$ do eletrólito (difusão)": "H$^+$ from the electrolyte (diffusion)",
    "pH na superfície do eletrodo": "surface pH",
    "camada de difusão (líquido)": "diffusion layer (liquid)",
    "CO$_2$ entra (c = c$_{sat}$)": "CO$_2$ in (c = c$_{sat}$)",
    "distância à superfície (µm)": "distance from the surface (µm)",
    "CO$_2$ no meio da CL (mM)": "CO$_2$ at mid-CL (mM)",
    "pH na superfície (x = 0)": "surface pH (x = 0)",
    "(estado estacionário)": "(steady state)",
    "j no KFem (mA cm$^{-2}$)": "j in KFem (mA cm$^{-2}$)",
    "Pontiagudo (cônico)": "Pointed",
    "g = 0,6 µm\n(base inerte)": "g = 0.6 µm\n(inert base)",
    "eletrólito\npH$_b$": "electrolyte\npH$_b$",
    "pH do eletrólito": "electrolyte pH",
    "pH na superfície": "surface pH",
    "gás\nCO$_2$, 1 atm": "gas\nCO$_2$, 1 atm",
    "KFem (j literal)": "KFem (literal j)",
    "no artigo": "in ref. 1",
    "Eletrólito pH": "Electrolyte pH",
    "Pontiagudo": "Pointed",
    "Convexo": "Convex",
    "Plano": "Flat",
    "artigo": "Xie et al.",
    "CL: 0–0,4 µm": "CL: 0–0.4 µm",
}
_KEYS = sorted(PT_EN, key=len, reverse=True)
_DEC = re.compile(r"(?<=\d),(?=\d)")


def translate(s: str) -> str:
    if not s:
        return s
    for k in _KEYS:
        if k in s:
            s = s.replace(k, PT_EN[k])
    return _DEC.sub(".", s)


_orig = mtext.Text.set_text


def _set_text(self, s):  # type: ignore[no-untyped-def]
    return _orig(self, translate(str(s)) if s is not None else s)


mtext.Text.set_text = _set_text  # type: ignore[method-assign]
