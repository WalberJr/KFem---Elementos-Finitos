"""Painel de configurações: formulário gerado a partir do catálogo para o nó selecionado."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kfem.model.catalog import CATALOG, PropSpec
from kfem.model.expressions import ExpressionError, parse
from kfem.model.parameters import ParameterSet
from kfem.model.tree import ALL, Node, Selection


def _validate_expr(edit: QLineEdit) -> None:
    txt = edit.text().strip()
    ok = True
    if txt and not txt.startswith("mat:"):
        try:
            parse(txt)
        except ExpressionError:
            ok = False
    edit.setProperty("invalid", "false" if ok else "true")
    edit.style().unpolish(edit)
    edit.style().polish(edit)
    edit.setToolTip("" if ok else "expressão inválida")


class SettingsPanel(QScrollArea):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.node: Node | None = None
        self._show_empty()

    def _show_empty(self, text: str = "Selecione um item na árvore do modelo.") -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        lab = QLabel(text)
        lab.setObjectName("muted")
        lay.addWidget(lab)
        lay.addStretch(1)
        self.setWidget(w)

    # ------------------------------------------------------------ parâmetros globais
    def show_parameters(self, ps: ParameterSet, values: dict[str, str] | None = None) -> None:
        self.node = None
        w = QWidget()
        lay = QVBoxLayout(w)
        title = QLabel("Parâmetros")
        title.setObjectName("title")
        lay.addWidget(title)
        for g in ps.groups:
            box = QGroupBox(g)
            bl = QVBoxLayout(box)
            items = ps.in_group(g)
            tab = QTableWidget(len(items) + 1, 4)
            tab.setHorizontalHeaderLabels(["Nome", "Expressão", "Valor (SI)", "Descrição"])
            tab.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            for r, p in enumerate(items):
                tab.setItem(r, 0, QTableWidgetItem(p.name))
                tab.setItem(r, 1, QTableWidgetItem(p.expr))
                v = QTableWidgetItem((values or {}).get(p.name, ""))
                v.setFlags(v.flags() & ~v.flags().ItemIsEditable)
                tab.setItem(r, 2, v)
                tab.setItem(r, 3, QTableWidgetItem(p.description))

            def on_edit(item: QTableWidgetItem, tab: QTableWidget = tab, g: str = g) -> None:
                r = item.row()
                name_it, expr_it = tab.item(r, 0), tab.item(r, 1)
                if not name_it or not expr_it or not name_it.text().strip() or not expr_it.text().strip():
                    return
                desc_it = tab.item(r, 3)
                try:
                    ps.add(name_it.text().strip(), expr_it.text().strip(), desc_it.text() if desc_it else "", g)
                    expr_it.setToolTip("")
                except ExpressionError as exc:
                    expr_it.setToolTip(str(exc))
                    return
                self.changed.emit()

            tab.itemChanged.connect(on_edit)
            tab.setMinimumHeight(min(400, 30 * (len(items) + 2)))
            bl.addWidget(tab)
            lay.addWidget(box)
        lay.addStretch(1)
        self.setWidget(w)

    # ------------------------------------------------------------ nó genérico
    def show_node(self, node: Node, info: str = "") -> None:
        self.node = node
        spec = CATALOG.get(node.kind)
        w = QWidget()
        lay = QVBoxLayout(w)
        title = QLabel(spec.label if spec else (node.label or node.kind))  # seções e raiz: o nome do nó
        title.setObjectName("title")
        lay.addWidget(title)
        if info:
            lab = QLabel(info)
            lab.setObjectName("muted")
            lab.setWordWrap(True)
            lay.addWidget(lab)
        form_box = QGroupBox("Identificação")
        form = QFormLayout(form_box)
        label = QLineEdit(node.label)
        label.textEdited.connect(lambda t: (setattr(node, "label", t), self.changed.emit()))
        form.addRow("Rótulo", label)
        form.addRow("Etiqueta", QLabel(node.tag))
        active = QCheckBox("Ativo")
        active.setChecked(node.active)
        active.toggled.connect(lambda v: (setattr(node, "active", v), self.changed.emit()))
        form.addRow("", active)
        lay.addWidget(form_box)

        if node.selection is not None and node.selection.dim >= 0:
            lay.addWidget(self._selection_box(node))
        if spec and spec.props:
            box = QGroupBox("Configurações")
            fl = QFormLayout(box)
            for ps in spec.props:
                fl.addRow(ps.label + (f" [{ps.unit}]" if ps.unit else ""), self._editor(node, ps))
            lay.addWidget(box)
        lay.addStretch(1)
        self.setWidget(w)

    def _selection_box(self, node: Node) -> QGroupBox:
        sel = node.selection
        assert sel is not None
        kind = {0: "Pontos", 1: "Contornos", 2: "Domínios", 3: "Volumes"}.get(sel.dim, "Entidades")
        if sel.dim == 2 and node.kind.split(".")[0] in ("brinkman", "current", "transport", "physics", "material"):
            kind = "Domínios"
        box = QGroupBox(f"Seleção — {kind}")
        hl = QHBoxLayout(box)
        all_cb = QCheckBox("Todos")
        all_cb.setChecked(sel.entities == ALL)
        ed = QLineEdit("" if sel.entities == ALL else ", ".join(str(e) for e in sel.entities))
        ed.setPlaceholderText("ex.: 1, 5, 9")
        ed.setEnabled(sel.entities != ALL)

        def apply() -> None:
            if all_cb.isChecked():
                node.selection = Selection(sel.dim, ALL)
                ed.setEnabled(False)
            else:
                ed.setEnabled(True)
                try:
                    ents = sorted({int(x) for x in ed.text().replace(";", ",").split(",") if x.strip()})
                except ValueError:
                    ed.setProperty("invalid", "true")
                    return
                ed.setProperty("invalid", "false")
                node.selection = Selection(sel.dim, ents)
            self.changed.emit()

        all_cb.toggled.connect(lambda _: apply())
        ed.editingFinished.connect(apply)
        hl.addWidget(all_cb)
        hl.addWidget(ed, 1)
        return box

    def _editor(self, node: Node, ps: PropSpec) -> QWidget:
        val = node.props.get(ps.name, ps.default)

        def setv(v: Any) -> None:
            node.props[ps.name] = v
            self.changed.emit()

        if ps.kind == "bool":
            cb = QCheckBox()
            cb.setChecked(bool(val))
            cb.toggled.connect(setv)
            return cb
        if ps.kind == "choice":
            co = QComboBox()
            co.addItems(list(ps.choices))
            if str(val) in ps.choices:
                co.setCurrentText(str(val))
            co.currentTextChanged.connect(setv)
            return co
        if ps.kind == "int":
            sp = QSpinBox()
            sp.setRange(0, 10000)
            sp.setValue(int(val or 0))
            sp.valueChanged.connect(setv)
            return sp
        if ps.kind == "list":
            ed = QLineEdit(", ".join(str(x) for x in (val or [])))
            ed.setToolTip("valores separados por vírgula")

            def on_list() -> None:
                items = [x.strip() for x in ed.text().split(",") if x.strip()]
                if items and all(x.lower() in ("true", "false") for x in items):
                    setv([x.lower() == "true" for x in items])
                else:
                    setv(items)

            ed.editingFinished.connect(on_list)
            return ed
        if ps.kind == "table":
            return self._table_editor(node, ps, val)
        ed = QLineEdit(str(val))
        if ps.kind == "expr":
            ed.textEdited.connect(lambda _t: _validate_expr(ed))
        ed.editingFinished.connect(lambda: setv(ed.text().strip()))
        if ps.help:
            ed.setToolTip(ps.help)
        return ed

    def _table_editor(self, node: Node, ps: PropSpec, val: Any) -> QWidget:
        if isinstance(val, dict):
            rows = [[k, v] for k, v in val.items()]
            ncol, heads = 2, ["Propriedade", "Expressão"]
        else:
            rows = [list(r) for r in (val or [])]
            ncol = max([len(r) for r in rows] + [2])
            heads = {
                "equations": ["Variável", "Equação f = 0", "Inicial", "Unidade"],
                "vars": ["Nome", "Expressão"],
                "params": ["Parâmetro", "Valores", "Unidade"],
            }.get(ps.name, [f"Coluna {i + 1}" for i in range(ncol)])
            ncol = len(heads)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        tab = QTableWidget(len(rows), ncol)
        tab.setHorizontalHeaderLabels(heads)
        tab.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(rows):
            for c in range(ncol):
                tab.setItem(r, c, QTableWidgetItem(str(row[c]) if c < len(row) else ""))

        def collect() -> None:
            data = []
            for r in range(tab.rowCount()):
                data.append([(tab.item(r, c).text() if tab.item(r, c) else "") for c in range(ncol)])
            data = [d for d in data if any(x.strip() for x in d)]
            node.props[ps.name] = {d[0]: d[1] for d in data} if isinstance(val, dict) else data
            self.changed.emit()

        tab.itemChanged.connect(lambda _i: collect())
        add = QPushButton("Adicionar linha")
        add.clicked.connect(lambda: tab.insertRow(tab.rowCount()))
        lay.addWidget(tab)
        lay.addWidget(add)
        tab.setMinimumHeight(120)
        return w
