"""Ícones próprios do KFem: SVG de linhas simples, gerados aqui e recoloridos pelo tema.

São desenhos originais e geométricos (traço 1,6 px em grade 24×24). Não vêm de nenhum
conjunto de terceiros.
"""

from __future__ import annotations

from typing import Any

from kfem.gui.theme import TOKENS

_P: dict[str, str] = {
    "node": '<circle cx="12" cy="12" r="5"/>',
    "folder": '<path d="M3 7h7l2 2h9v10H3z"/>',
    "parameters": '<path d="M5 6h14M5 12h14M5 18h14"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/>'
    '<circle cx="8" cy="18" r="2"/>',
    "function": '<path d="M4 18c4 0 4-12 8-12s4 12 8 12"/>',
    "variables": '<path d="M6 5l-2 7 2 7M18 5l2 7-2 7M9 9l6 6M15 9l-6 6"/>',
    "probe": '<path d="M12 3v9"/><circle cx="12" cy="16" r="4"/>',
    "component": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 12h16M12 4v16"/>',
    "geometry": '<path d="M4 18l8-13 8 13z"/>',
    "rectangle": '<rect x="4" y="7" width="16" height="10"/>',
    "disk": '<circle cx="12" cy="12" r="8"/>',
    "box": '<path d="M4 8l8-4 8 4v8l-8 4-8-4z M4 8l8 4 8-4 M12 12v8"/>',
    "union": '<circle cx="9" cy="12" r="5"/><circle cx="15" cy="12" r="5"/>',
    "polygon": '<path d="M5 18 L4 9 L12 4 L20 10 L16 19 Z"/>',
    "difference": (
        '<path d="M9 7 a5 5 0 1 0 0 10 a6 6 0 0 1 0 -10 Z"/>'
        '<circle cx="15" cy="12" r="5" stroke-dasharray="2 2"/>'
    ),
    "intersection": (
        '<circle cx="9" cy="12" r="5" stroke-dasharray="2 2"/>'
        '<circle cx="15" cy="12" r="5" stroke-dasharray="2 2"/>'
        '<path d="M12 8 a5 5 0 0 1 0 8 a5 5 0 0 1 0 -8 Z"/>'
    ),
    "eraser": '<path d="M4 16l8-8 6 6-6 6H8z M10 10l6 6"/>',
    "material": '<path d="M12 3l7 4v10l-7 4-7-4V7z"/><path d="M12 3v18"/>',
    "physics": '<path d="M12 4a8 8 0 1 0 0 16a8 8 0 1 0 0-16 M4 12h16"/>',
    "flow": '<path d="M3 8c3-2 6 2 9 0s6 2 9 0 M3 13c3-2 6 2 9 0s6 2 9 0 M3 18c3-2 6 2 9 0s6 2 9 0"/>',
    "porous": '<rect x="4" y="4" width="16" height="16"/><circle cx="9" cy="9" r="1.6"/>'
    '<circle cx="15" cy="10" r="1.6"/><circle cx="10" cy="15" r="1.6"/>',
    "fluid": '<path d="M12 3c4 6 6 9 6 12a6 6 0 0 1-12 0c0-3 2-6 6-12z"/>',
    "wall": '<path d="M5 4v16 M5 6l-2 2 M5 10l-2 2 M5 14l-2 2 M5 18l-2 2"/>',
    "inlet": '<path d="M3 12h13 M12 7l5 5-5 5 M20 4v16"/>',
    "outlet": '<path d="M4 4v16 M7 12h13 M16 7l5 5-5 5"/>',
    "init": '<path d="M6 4v16 M6 5h11l-3 4 3 4H6"/>',
    "current": '<path d="M13 3L6 13h6l-1 8 7-10h-6z"/>',
    "electrolyte": '<path d="M5 8h14v10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z M9 12h2 M14 14h2"/>',
    "electrode": '<rect x="5" y="3" width="5" height="18"/><rect x="14" y="3" width="5" height="18"/>',
    "capacitor": '<path d="M3 12h6 M15 12h6 M9 5v14 M15 5v14"/>',
    "reaction": '<path d="M4 9h14l-3-3 M20 15H6l3 3"/>',
    "insulation": '<path d="M4 4h16v16H4z M4 4l16 16"/>',
    "potential": '<path d="M12 3v6 M8 9h8 M9 12h6 M10 15h4"/>',
    "transport": '<circle cx="7" cy="12" r="2.5"/><circle cx="17" cy="8" r="2.5"/><circle cx="15" cy="17" r="2.5"/>'
    '<path d="M9.5 12h3"/>',
    "concentration": '<path d="M7 4h10 M9 4v6l-4 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-4-8V4"/>',
    "global": '<circle cx="12" cy="12" r="8"/><path d="M4 12h16 M12 4c3 3 3 13 0 16 M12 4c-3 3-3 13 0 16"/>',
    "equation": '<path d="M5 9h14 M5 15h14"/>',
    "coupling": '<path d="M9 7a4 4 0 0 0 0 10h2 M15 7a4 4 0 0 1 0 10h-2 M8 12h8"/>',
    "mesh": '<path d="M4 20L20 4 M4 4h16v16H4z M4 12l8 8 M12 4l8 8"/>',
    "layers": '<path d="M3 18h18 M3 15h18 M3 12h18"/>',
    "study": '<path d="M7 4h10v4l-3 4 3 4v4H7v-4l3-4-3-4z"/>',
    "stationary": '<path d="M5 12h14 M12 5v14"/>',
    "time": '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 3"/>',
    "sweep": '<path d="M4 18L9 8l4 6 3-5 4 9"/>',
    "results": '<path d="M4 20V10 M10 20V4 M16 20v-7 M3 20h18"/>',
    "surface": '<path d="M3 17c4-8 7 2 9-5s5-4 9-2v9H3z"/>',
    "plot": '<path d="M4 4v16h16 M7 15l4-5 3 3 5-6"/>',
    "run": '<path d="M7 4l12 8-12 8z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12"/>',
    "open": '<path d="M3 7h7l2 2h9v10H3z M12 13v5 M9.5 15.5L12 13l2.5 2.5"/>',
    "save": '<path d="M5 4h11l3 3v13H5z M8 4v5h7V4 M8 20v-6h8v6"/>',
    "new": '<path d="M6 3h8l4 4v14H6z M14 3v4h4 M12 11v6 M9 14h6"/>',
    "import": '<path d="M12 3v12 M7 10l5 5 5-5 M4 20h16"/>',
    "zoom": '<circle cx="10" cy="10" r="6"/><path d="M15 15l5 5"/>',
    "build": '<path d="M14 4l6 6-9 9H5v-6z"/>',
    "gpu": '<rect x="3" y="7" width="18" height="10" rx="1"/><circle cx="9" cy="12" r="2.5"/>'
    '<circle cx="16" cy="12" r="2.5"/><path d="M6 17v3 M18 17v3"/>',
}


def svg(name: str, color: str | None = None, size: int = 24) -> str:
    body = _P.get(name, _P["node"])
    c = color or TOKENS["primary"]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )


_cache: dict[tuple[str, str], Any] = {}


def icon(name: str, color: str | None = None) -> Any:
    """QIcon a partir do SVG (precisa do módulo QtSvg)."""
    from PySide6.QtCore import QByteArray, QSize
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    key = (name, color or "")
    if key not in _cache:
        ic = QIcon()
        for px in (16, 24, 32, 48):
            r = QSvgRenderer(QByteArray(svg(name, color).encode()))
            pm = QPixmap(QSize(px, px))
            pm.fill(0)  # transparente
            p = QPainter(pm)
            r.render(p)
            p.end()
            ic.addPixmap(pm)
        _cache[key] = ic
    return _cache[key]


def names() -> list[str]:
    return sorted(_P)
