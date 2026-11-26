"""Etapa 8 — tema (contraste WCAG AA) e ícones próprios."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from kfem.gui.icons import names, svg
from kfem.gui.theme import TOKENS, contrast_ratio, stylesheet


def test_text_contrast_aa():
    for bg in ("bg", "surface", "surface2", "primary_soft"):
        assert contrast_ratio(TOKENS["text"], TOKENS[bg]) >= 4.5, bg
    for bg in ("bg", "surface"):
        assert contrast_ratio(TOKENS["text_muted"], TOKENS[bg]) >= 4.5, bg
        assert contrast_ratio(TOKENS["primary"], TOKENS[bg]) >= 4.5, bg
    assert contrast_ratio(TOKENS["text"], TOKENS["accent_strong"]) >= 4.5


def test_stylesheet_uses_tokens():
    qss = stylesheet()
    assert TOKENS["primary"] in qss and TOKENS["accent_strong"] in qss and TOKENS["bg"] in qss


def test_icons_are_valid_svg():
    assert len(names()) > 40
    for n in names():
        ET.fromstring(svg(n))
