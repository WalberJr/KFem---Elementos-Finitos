"""Tema visual do KFem: lilás + verde-escuro + preto (CLAUDE.md §9).

Os tokens de cor ficam num só lugar. O QSS é gerado a partir deles, e `contrast_ratio`
confere o contraste mínimo WCAG AA (4,5:1 para texto).
"""

from __future__ import annotations

TOKENS: dict[str, str] = {
    "bg": "#0B0B0D",
    "surface": "#16161A",
    "surface2": "#1D1D23",
    "primary": "#B79CDB",
    "primary_soft": "#3A2F4D",
    "accent": "#1F5B3A",
    "accent_strong": "#2A7448",  # CLAUDE.md sugeria #2E7D4F (contraste 4,18 < AA); ajustado
    "text": "#ECE8F2",
    "text_muted": "#A59FB0",
    "border": "#2A2A31",
    "danger": "#E07A7A",
    "warning": "#E0C27A",
    "view_top": "#000000",
    "view_bottom": "#1A1426",
    "geometry": "#B79CDB",
    "selection": "#3FBF73",
}


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def stylesheet(t: dict[str, str] = TOKENS) -> str:
    return f"""
* {{ color: {t["text"]}; font-size: 10pt; }}
QMainWindow, QWidget {{ background: {t["bg"]}; }}
QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{ background: {t["surface"]}; padding: 4px 8px; border-bottom: 1px solid {t["border"]};
    color: {t["primary"]}; font-weight: bold; }}
QMenuBar {{ background: {t["surface"]}; border-bottom: 1px solid {t["border"]}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {t["primary_soft"]}; }}
QMenu {{ background: {t["surface"]}; border: 1px solid {t["border"]}; }}
QTabWidget::pane {{ border: 1px solid {t["border"]}; background: {t["surface"]}; }}
QTabBar::tab {{ background: {t["surface"]}; color: {t["text_muted"]}; padding: 6px 14px;
    border: 1px solid {t["border"]}; border-bottom: none; }}
QTabBar::tab:selected {{ color: {t["text"]}; background: {t["surface2"]}; border-top: 2px solid {t["primary"]}; }}
QToolBar {{ background: {t["surface2"]}; border: none; spacing: 4px; padding: 3px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 4px 6px; }}
QToolButton:hover {{ background: {t["primary_soft"]}; border-color: {t["primary"]}; }}
QToolButton:pressed, QToolButton:checked {{ background: {t["accent"]}; }}
QPushButton {{ background: {t["surface2"]}; border: 1px solid {t["border"]}; border-radius: 4px; padding: 5px 12px; }}
QPushButton:hover {{ border-color: {t["primary"]}; }}
QPushButton#primary {{ background: {t["accent_strong"]}; border-color: {t["accent_strong"]}; font-weight: bold; }}
QPushButton#primary:hover {{ background: {t["accent"]}; }}
QPushButton#danger {{ border-color: {t["danger"]}; color: {t["danger"]}; }}
QTreeView, QTableView, QListView, QPlainTextEdit, QTextEdit {{ background: {t["surface"]};
    border: 1px solid {t["border"]}; alternate-background-color: {t["surface2"]};
    selection-background-color: {t["primary_soft"]}; selection-color: {t["text"]}; }}
QTreeView::item:selected {{ background: {t["primary_soft"]}; border-left: 2px solid {t["primary"]}; }}
QHeaderView::section {{ background: {t["surface2"]}; color: {t["text_muted"]}; border: none;
    border-right: 1px solid {t["border"]}; padding: 4px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {t["bg"]}; border: 1px solid {t["border"]};
    border-radius: 3px; padding: 3px 5px; selection-background-color: {t["primary_soft"]}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {t["primary"]}; }}
QLineEdit[invalid="true"] {{ border-color: {t["danger"]}; }}
QGroupBox {{ border: 1px solid {t["border"]}; border-radius: 4px; margin-top: 14px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {t["primary"]}; font-weight: bold; }}
QCheckBox::indicator:checked {{ background: {t["accent_strong"]}; border: 1px solid {t["primary"]}; }}
QProgressBar {{ background: {t["surface"]}; border: 1px solid {t["border"]}; border-radius: 3px; text-align: center; }}
QProgressBar::chunk {{ background: {t["accent_strong"]}; }}
QProgressBar#usageMeter {{ font-size: 9pt; color: {t["text"]}; }}
QProgressBar#usageMeter::chunk {{ background: {t["primary_soft"]}; }}
QStatusBar {{ background: {t["surface"]}; color: {t["text_muted"]}; border-top: 1px solid {t["border"]}; }}
QSplitter::handle {{ background: {t["border"]}; }}
QScrollBar:vertical {{ background: {t["surface"]}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {t["primary_soft"]}; border-radius: 4px; min-height: 20px; }}
QLabel#muted {{ color: {t["text_muted"]}; }}
QLabel#title {{ color: {t["primary"]}; font-size: 13pt; font-weight: bold; }}
"""
