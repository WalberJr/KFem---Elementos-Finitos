"""Janela principal do KFem (Etapas 8 e 9).

Layout: barra de menus, faixa de ferramentas em abas, árvore do modelo à esquerda,
configurações no centro, janela gráfica à direita e, embaixo, as abas Mensagens, Progresso,
Log e Tabela. Os painéis são acopláveis. Nomes, ícones e textos são próprios do KFem.
"""

from __future__ import annotations

import contextlib
import csv
import os
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kfem import __version__
from kfem.gui.graphics import GraphicsView
from kfem.gui.icons import icon
from kfem.gui.settings_panel import SettingsPanel
from kfem.gui.solver_process import SolverProcess, physical_cores
from kfem.io import kfem_format
from kfem.model.catalog import CATALOG, children_kinds
from kfem.model.tree import Model, Node, Selection, unique_tag

ROLE = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    hw_checked = Signal(object)  # Selection do backend, ou str com o erro

    def __init__(self) -> None:
        super().__init__()
        self.model = Model(name="Sem título")
        self.path: Path | None = None
        self.dirty = False
        self.last_workdir: Path | None = None
        self.setWindowTitle(f"KFem {__version__}")
        self.resize(1500, 900)
        self.solver = SolverProcess(self)
        self._build_ui()
        self._connect_solver()
        self.refresh_tree()
        self._hw_status()

    # ================================================================== UI
    def _build_ui(self) -> None:
        # ---- árvore
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        self.tree.currentItemChanged.connect(self._on_select)
        dock_tree = QDockWidget("Árvore do modelo", self)
        dock_tree.setObjectName("dock_tree")
        dock_tree.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_tree)
        # ---- configurações
        self.settings = SettingsPanel()
        self.settings.changed.connect(self._on_changed)
        dock_set = QDockWidget("Configurações", self)
        dock_set.setObjectName("dock_settings")
        dock_set.setWidget(self.settings)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_set)
        self.splitDockWidget(dock_tree, dock_set, Qt.Orientation.Horizontal)
        # ---- gráficos (centro)
        self.graphics = GraphicsView()
        self.setCentralWidget(self.graphics)
        # ---- painel inferior
        self.messages = QPlainTextEdit(readOnly=True)
        self.logview = QPlainTextEdit(readOnly=True)
        self.logview.setMaximumBlockCount(20000)
        prog_w = QWidget()
        pl = QVBoxLayout(prog_w)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress_label = QLabel("Nenhum cálculo em andamento.")
        self.progress_label.setObjectName("muted")
        pl.addWidget(self.progress)
        pl.addWidget(self.progress_label)
        pl.addStretch(1)
        self.table = QTableWidget()
        self.bottom = QTabWidget()
        self.bottom.addTab(self.messages, "Mensagens")
        self.bottom.addTab(prog_w, "Progresso")
        self.bottom.addTab(self.logview, "Log")
        self.bottom.addTab(self.table, "Tabela")
        dock_bot = QDockWidget("Saídas", self)
        dock_bot.setObjectName("dock_bottom")
        dock_bot.setWidget(self.bottom)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock_bot)
        self._build_actions()
        self._build_ribbon()
        self.resizeDocks([dock_tree, dock_set], [290, 470], Qt.Orientation.Horizontal)
        self.resizeDocks([dock_bot], [190], Qt.Orientation.Vertical)
        self.statusBar().showMessage("Pronto")

    def _act(self, text: str, slot: Any, ic: str | None = None, shortcut: str | None = None) -> QAction:
        a = QAction(icon(ic) if ic else QAction().icon(), text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        return a

    def _build_actions(self) -> None:
        self.a_new = self._act("Novo", self.new_model, "new", "Ctrl+N")
        self.a_open = self._act("Abrir…", self.open_dialog, "open", "Ctrl+O")
        self.a_save = self._act("Salvar", self.save, "save", "Ctrl+S")
        self.a_saveas = self._act("Salvar como…", self.save_as, "save", "Ctrl+Shift+S")
        self.a_import = self._act("Importar arquivo .mph…", self.import_mph, "import")
        self.a_quit = self._act("Sair", self.close, None, "Ctrl+Q")
        self.a_geom = self._act("Pré-visualizar geometria", self.preview_geometry, "geometry")
        self.a_mesh = self._act("Gerar malha", self.build_mesh, "mesh")
        self.a_run = self._act("Calcular", self.run_study, "run", "F8")
        self.a_stop = self._act("Parar cálculo", self.cancel_study, "stop", "Shift+F8")
        self.a_stop.setEnabled(False)
        self.a_results = self._act("Abrir resultados", self.open_results_dialog, "results")
        self.a_export_png = self._act("Exportar imagem (PNG)…", self.export_png, "surface")
        self.a_export_csv = self._act("Exportar tabela (CSV)…", self.export_csv, "plot")
        self.a_diag = self._act("Diagnóstico de hardware", self.show_diagnose, "gpu")
        self.a_gpu_setup = self._act("Configurar placa de vídeo…", lambda: self.offer_gpu_setup(force=True), "gpu")
        self.a_manual = self._act("Manual do usuário (PDF)", lambda: self.open_doc("KFem-Manual.pdf"), None, "F1")
        self.a_tutorial = self._act("Tutorial (PDF)", lambda: self.open_doc("KFem-Tutorial.pdf"), None)
        self.a_about = self._act("Sobre o KFem", self.about, None)
        mb = self.menuBar()
        m = mb.addMenu("&Arquivo")
        for a in (self.a_new, self.a_open, self.a_save, self.a_saveas):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_import)
        self.recent_menu = m.addMenu(icon("open"), "Trabalhos recentes")
        self.recent_menu.aboutToShow.connect(lambda: self._fill_recent(self.recent_menu))
        m.addSeparator()
        m.addAction(self.a_quit)
        m = mb.addMenu("&Modelo")
        m.addAction(self.a_geom)
        m.addAction(self.a_mesh)
        m = mb.addMenu("&Estudo")
        m.addAction(self.a_run)
        m.addAction(self.a_stop)
        m = mb.addMenu("&Resultados")
        for a in (self.a_results, self.a_export_png, self.a_export_csv):
            m.addAction(a)
        m = mb.addMenu("A&juda")
        m.addAction(self.a_diag)
        m.addAction(self.a_gpu_setup)
        m.addAction(self.a_manual)
        m.addAction(self.a_tutorial)
        m.addSeparator()
        m.addAction(self.a_about)

    def _build_ribbon(self) -> None:
        ribbon = QTabWidget()
        ribbon.setMaximumHeight(92)

        def bar(actions: list[QAction | QWidget]) -> QToolBar:
            tb = QToolBar()
            tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            for a in actions:
                if isinstance(a, QAction):
                    tb.addAction(a)
                else:
                    tb.addWidget(a)
            return tb

        recent_btn = QToolButton()
        recent_btn.setText("Trabalhos recentes")
        recent_btn.setIcon(icon("folder"))
        recent_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        recent_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        rmenu = QMenu(recent_btn)
        rmenu.aboutToShow.connect(lambda: self._fill_recent(rmenu))
        recent_btn.setMenu(rmenu)
        ribbon.addTab(bar([self.a_new, self.a_open, self.a_save, self.a_import, recent_btn]), "Início")
        ribbon.addTab(bar([self.a_geom]), "Geometria")
        ribbon.addTab(bar([self.a_mesh]), "Malha")
        par = QWidget()
        hl = QHBoxLayout(par)
        hl.setContentsMargins(6, 0, 6, 0)
        self.n_procs = QSpinBox()
        self.n_procs.setRange(1, 256)
        self.n_procs.setValue(max(1, physical_cores()))
        self.n_threads = QSpinBox()
        self.n_threads.setRange(1, 64)
        self.n_threads.setValue(1)
        hl.addWidget(QLabel("Processos MPI"))
        hl.addWidget(self.n_procs)
        hl.addWidget(QLabel("Threads OpenMP"))
        hl.addWidget(self.n_threads)
        run_btn = QPushButton("Calcular")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self.run_study)
        ribbon.addTab(bar([run_btn, self.a_stop, par]), "Estudo")
        ribbon.addTab(bar([self.a_results, self.a_export_png, self.a_export_csv]), "Resultados")
        tb = QToolBar("Faixa")
        tb.setObjectName("ribbon")
        tb.setMovable(False)
        tb.addWidget(ribbon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

    # ================================================================== árvore
    def refresh_tree(self) -> None:
        sel_path = self._current_path()
        self.tree.blockSignals(True)
        self.tree.clear()
        root = QTreeWidgetItem([self.model.name or "Modelo"])
        root.setIcon(0, icon("component"))
        root.setData(0, ROLE, ("model", ""))
        self.tree.addTopLevelItem(root)
        glob = QTreeWidgetItem(["Definições globais"])
        glob.setIcon(0, icon("folder"))
        glob.setData(0, ROLE, ("section", "global"))
        root.addChild(glob)
        par = QTreeWidgetItem([f"Parâmetros ({len(self.model.parameters.params)})"])
        par.setIcon(0, icon("parameters"))
        par.setData(0, ROLE, ("parameters", ""))
        glob.addChild(par)
        self._add_node_item(glob, self.model.functions, "functions")
        for comp in self.model.components:
            ci = QTreeWidgetItem([f"{comp.label} ({comp.dim}D)"])
            ci.setIcon(0, icon("component"))
            ci.setData(0, ROLE, ("component", comp.tag))
            root.addChild(ci)
            for sec in comp.sections.values():
                self._add_node_item(ci, sec, f"{comp.tag}/{sec.tag}")
        self._add_node_item(root, self.model.studies, "studies")
        self._add_node_item(root, self.model.results, "results")
        self.tree.expandToDepth(2)
        self.tree.blockSignals(False)
        if sel_path:
            self._select_path(sel_path)

    def _add_node_item(self, parent: QTreeWidgetItem, node: Node, path: str) -> None:
        spec = CATALOG.get(node.kind)
        text = node.label or (spec.label if spec else node.tag)
        if node.kind.startswith("section."):
            text = node.label
        it = QTreeWidgetItem([text if node.active else f"{text} (inativo)"])
        it.setIcon(
            0,
            icon(
                spec.icon if spec else ("folder" if node.kind.startswith("section.") else "node"),
                None if node.active else "#6B6577",
            ),
        )
        it.setData(0, ROLE, ("node", path))
        if node.selection is not None and node.selection.dim >= 0 and node.selection.entities != "all":
            it.setToolTip(0, f"seleção: {node.selection.entities}")
        parent.addChild(it)
        for c in node.children:
            self._add_node_item(it, c, f"{path}/{c.tag}")

    def _current_path(self) -> tuple[str, str] | None:
        it = self.tree.currentItem()
        return it.data(0, ROLE) if it else None

    def _select_path(self, key: tuple[str, str]) -> None:
        def walk(it: QTreeWidgetItem) -> bool:
            if it.data(0, ROLE) == key:
                self.tree.setCurrentItem(it)
                return True
            return any(walk(it.child(i)) for i in range(it.childCount()))

        for i in range(self.tree.topLevelItemCount()):
            if walk(self.tree.topLevelItem(i)):
                return

    def _on_select(self, cur: QTreeWidgetItem | None, _prev: Any) -> None:
        if cur is None:
            return
        kind, path = cur.data(0, ROLE)
        if kind == "parameters":
            try:
                vals = {k: f"{v:.6g}" for k, v in self.model.parameters.to_si().items()}
            except Exception as exc:
                vals = {}
                self.message(f"Parâmetros: {exc}", "erro")
            self.settings.show_parameters(self.model.parameters, vals)
        elif kind == "node":
            node = self._node(path)
            info = ""
            if node.kind == "section.physics":
                info = "Clique com o botão direito para adicionar uma física."
            self.settings.show_node(node, info)
        else:
            self.settings.show_node(Node("info", path or "modelo", self.model.name), "")

    def _node(self, path: str) -> Node:
        if path in ("functions", "studies", "results"):
            return getattr(self.model, path)
        parts = path.split("/")
        if len(parts) == 2 and parts[0] == self.model.comp.tag:
            return self.model.comp.sections[parts[1]]
        return self.model.find(path)

    def _tree_menu(self, pos: Any) -> None:
        it = self.tree.itemAt(pos)
        if it is None:
            return
        kind, path = it.data(0, ROLE)
        if kind != "node":
            return
        node = self._node(path)
        menu = QMenu(self)
        for spec in children_kinds(node.kind):
            a = menu.addAction(icon(spec.icon), f"Adicionar: {spec.label}")
            a.triggered.connect(lambda _c=False, s=spec, n=node: self._add_child(n, s))
        if not node.kind.startswith("section."):
            menu.addSeparator()
            act = menu.addAction("Desativar" if node.active else "Ativar")
            act.triggered.connect(lambda: self._toggle(node))
            rm = menu.addAction("Remover")
            rm.triggered.connect(lambda: self._remove(path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _add_child(self, parent: Node, spec: Any) -> None:
        tag = unique_tag(parent.children, spec.tag_prefix)
        dims = {"domínio": self.model.comp.dim, "contorno": self.model.comp.dim - 1, "global": -1}
        sel = Selection(dims[spec.selection]) if spec.selection in dims else None
        n = Node(spec.kind, tag, spec.label, props=spec.defaults(), selection=sel)
        parent.add(n)
        for ch in children_kinds(spec.kind):  # nós padrão (iniciais, paredes…)
            if ch.default_child:
                csel = Selection(dims[ch.selection]) if ch.selection in dims else None
                n.add(
                    Node(ch.kind, unique_tag(n.children, ch.tag_prefix), ch.label, props=ch.defaults(), selection=csel)
                )
        self._on_changed()
        self.refresh_tree()

    def _toggle(self, node: Node) -> None:
        node.active = not node.active
        self._on_changed()
        self.refresh_tree()

    def _remove(self, path: str) -> None:
        parent_path, tag = path.rsplit("/", 1)
        self._node(parent_path).remove(tag)
        self._on_changed()
        self.refresh_tree()

    def _on_changed(self) -> None:
        self.dirty = True
        self._update_title()

    def _update_title(self) -> None:
        name = self.path.name if self.path else "Sem título"
        self.setWindowTitle(f"{'• ' if self.dirty else ''}{name} — KFem {__version__}")

    # ================================================================== arquivos
    def new_model(self) -> None:
        if not self._confirm_discard():
            return
        self.model = Model(name="Sem título")
        self.path = None
        self.dirty = False
        self.refresh_tree()
        self._update_title()

    def ask(self, question: str) -> bool:
        """Pergunta sim/não ao usuário (substituível em testes)."""
        r = QMessageBox.question(self, "KFem", question)
        return r == QMessageBox.StandardButton.Yes

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        return self.ask("Descartar as alterações não salvas?")

    # ------------------------------------------------------------------ trabalhos recentes
    MAX_RECENT = 10

    def recent_projects(self) -> list[Path]:
        """Projetos abertos/salvos, do mais recente ao mais antigo, só os que ainda existem."""
        raw = QSettings("KFem", "KFem").value("recent", []) or []
        items = [raw] if isinstance(raw, str) else list(raw)
        return [Path(x) for x in items if x and Path(x).is_file()][: self.MAX_RECENT]

    def _add_recent(self, p: Path) -> None:
        p = p.resolve()
        items = [str(p)] + [str(x) for x in self.recent_projects() if x.resolve() != p]
        QSettings("KFem", "KFem").setValue("recent", items[: self.MAX_RECENT])

    def _fill_recent(self, menu: QMenu) -> None:
        menu.clear()
        recent = self.recent_projects()
        if not recent:
            a = menu.addAction("Nenhum trabalho recente")
            a.setEnabled(False)
            return
        for p in recent:
            a = menu.addAction(icon("open"), f"{p.stem}   —   {p.parent}")
            a.setToolTip(str(p))
            a.triggered.connect(lambda _c=False, path=p: self._open_recent(path))
        menu.addSeparator()
        menu.addAction("Limpar lista", lambda: QSettings("KFem", "KFem").setValue("recent", []))

    def _open_recent(self, p: Path) -> None:
        if self._confirm_discard():
            self.open_path(p)

    def open_dialog(self) -> None:
        if not self._confirm_discard():
            return
        fn, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", "", "Projetos KFem (*.kfem)")
        if fn:
            self.open_path(Path(fn))

    def open_path(self, p: Path) -> None:
        try:
            self.model = kfem_format.load(p)
        except Exception as exc:
            QMessageBox.critical(self, "KFem", f"Não foi possível abrir o projeto:\n{exc}")
            return
        self.path = p
        self.dirty = False
        self.refresh_tree()
        self._update_title()
        self._add_recent(p)
        self.message(f"Projeto aberto: {p}")
        if self.model.meta.get("conversion_report"):
            self.logview.appendPlainText(self.model.meta["conversion_report"])

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        kfem_format.save(self.model, self.path)
        self.dirty = False
        self._update_title()
        self._add_recent(self.path)
        self.message(f"Salvo: {self.path}")
        return True

    def save_as(self) -> bool:
        fn, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", "", "Projetos KFem (*.kfem)")
        if not fn:
            return False
        self.path = Path(fn if fn.endswith(".kfem") else fn + ".kfem")
        return self.save()

    def import_mph(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "Importar .mph", "", "Arquivos .mph (*.mph)")
        if not fn:
            return
        from kfem.io.mph import read_mph

        try:
            self.model, rep = read_mph(fn)
        except Exception as exc:
            QMessageBox.critical(self, "KFem", f"Falha na importação:\n{exc}")
            return
        self.path = None
        self.dirty = True
        self.refresh_tree()
        self._update_title()
        self.logview.appendPlainText(rep.summary())
        self.message(
            f"Importado de {Path(fn).name}: {len(rep.converted)} itens convertidos, "
            f"{len(rep.skipped)} não convertidos (detalhes no Log)"
        )

    def load_cdi_example(self) -> None:
        from kfem.samples import cdi_model

        if not self._confirm_discard():
            return
        self.model = cdi_model()
        self.path = None
        self.dirty = True
        self.refresh_tree()
        self._update_title()
        self.message("Exemplo da célula CDI carregado (criado com os nós do KFem).")

    # ================================================================== geometria/malha
    def preview_geometry(self) -> None:
        from kfem.geometry.build import LENGTH_FACTORS, _num
        from kfem.model.expressions import constants

        try:
            env = {**constants(), **self.model.parameters.evaluate()}
            s = LENGTH_FACTORS.get(self.model.comp.length_unit, 1.0)
            rects, labels = [], []
            for n in self.model.comp.geometry.active_children("geom.rectangle"):
                p = n.props
                rects.append(tuple(_num(p[k], env, s) * 1e3 for k in ("x", "y", "width", "height")))
                labels.append(n.label or n.tag)
            self.graphics.show_geometry_preview(rects, labels)
            self.message(f"Geometria: {len(rects)} retângulos (coordenadas em mm)")
        except Exception as exc:
            self.message(f"Geometria: {exc}", "erro")

    def build_mesh(self) -> None:
        """Gera a malha num processo separado (rápido) e mostra o resultado."""
        self._start_solver(extra_args=["--mesh-only"], label="malha")

    # ================================================================== estudo
    def _connect_solver(self) -> None:
        s = self.solver
        s.log.connect(lambda m: self.logview.appendPlainText(m))
        s.log.connect(self._live_refresh)
        s.progress.connect(self._on_progress)
        s.started_run.connect(
            lambda wd, be, n: self.message(f"Cálculo iniciado: backend {be}, {n} processo(s) MPI; saídas em {wd}")
        )
        s.finished_ok.connect(self._on_done)
        s.cancelled.connect(lambda m: self._on_end(f"Cálculo cancelado: {m}", "aviso"))
        s.failed.connect(lambda m: self._on_end(f"O cálculo falhou: {m}", "erro"))

    def _start_solver(self, extra_args: list[str] | None = None, label: str = "estudo") -> None:
        if self.solver.is_running():
            self.message("Já existe um cálculo em andamento.", "aviso")
            return
        if (self.path is None or self.dirty) and not self.save():
            return
        assert self.path is not None
        from kfem.hw.backend import select_backend_checked

        self.message("Verificando o backend de cálculo (teste de sanidade da GPU)…")
        QApplication.processEvents()
        sel = select_backend_checked()[1]
        study = self.model.studies.children[0].tag if self.model.studies.children else None
        self.progress.setValue(0)
        self.bottom.setCurrentIndex(1)
        self.a_run.setEnabled(False)
        self.a_stop.setEnabled(True)
        self.solver.start(
            str(self.path),
            study,
            procs=self.n_procs.value(),
            threads=self.n_threads.value(),
            env_extra=sel.env,
            extra_args=extra_args,
        )
        self.statusBar().showMessage(f"Calculando ({label})… backend {sel.compute}")

    def watch_run(self, log_file: Path, workdir: Path) -> None:
        """Acompanha na interface um cálculo iniciado fora dela (linha de comando)."""
        self.progress.setValue(0)
        self.bottom.setCurrentIndex(1)
        self.a_run.setEnabled(False)
        self.a_stop.setEnabled(True)
        self.last_workdir = workdir
        self.statusBar().showMessage(f"Acompanhando cálculo externo em {workdir}")
        self.solver.attach(log_file, workdir)

    def _live_refresh(self, msg: str) -> None:
        """A cada instante de saída gravado ("t = …"), recarrega os campos durante o cálculo."""
        wd = self.solver.workdir
        if not msg.startswith("t = ") or wd is None or not self.solver.is_running():
            return
        with contextlib.suppress(Exception):  # arquivo pode estar sendo escrito neste instante
            idx = self.graphics.field_box.currentText()
            self.graphics.load_results(wd)
            if idx:
                self.graphics.field_box.setCurrentText(idx)

    def run_study(self) -> None:
        if not self.model.studies.children:
            self.message("O modelo não tem estudo.", "aviso")
            return
        self._start_solver()

    def cancel_study(self) -> None:
        self.solver.cancel()

    def _on_progress(self, f: float, msg: str) -> None:
        self.progress.setValue(int(1000 * f))
        self.progress_label.setText(msg)

    def _on_end(self, msg: str, level: str = "info") -> None:
        self.a_run.setEnabled(True)
        self.a_stop.setEnabled(False)
        self.statusBar().showMessage(msg)
        self.message(msg, level)

    def _on_done(self, workdir: str, summary: dict[str, Any]) -> None:
        self.last_workdir = Path(workdir)
        self._on_end(f"Cálculo concluído em {summary.get('wall_s', 0):.1f} s (backend {summary.get('backend')}).")
        self.load_results(self.last_workdir)

    # ================================================================== resultados
    def open_results_dialog(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Diretório de resultados")
        if d:
            self.load_results(Path(d))

    def load_results(self, wd: Path) -> None:
        if any(wd.glob("field_*.xdmf")):
            try:
                names = self.graphics.load_results(wd)
                self.message(f"Resultados carregados: {', '.join(names)}")
            except Exception as exc:
                self.message(f"Falha ao ler resultados: {exc}", "erro")
        elif (wd / "mesh.xdmf").exists():
            self.graphics.show_mesh_file(wd / "mesh.xdmf")
        g = wd / "globals.csv"
        if g.exists():
            with open(g) as fh:
                rows = list(csv.reader(fh))
            self.table.setColumnCount(len(rows[0]))
            self.table.setRowCount(len(rows) - 1)
            self.table.setHorizontalHeaderLabels(rows[0])
            for r, row in enumerate(rows[1:]):
                for c, v in enumerate(row):
                    with contextlib.suppress(ValueError):
                        v = f"{float(v):.6g}"
                    self.table.setItem(r, c, QTableWidgetItem(v))
            self.bottom.setCurrentIndex(3)

    def export_png(self) -> None:
        fn, _ = QFileDialog.getSaveFileName(self, "Exportar imagem", "", "PNG (*.png)")
        if fn:
            self.graphics.screenshot(Path(fn))

    def export_csv(self) -> None:
        if self.last_workdir is None or not (self.last_workdir / "globals.csv").exists():
            self.message("Não há tabela para exportar.", "aviso")
            return
        fn, _ = QFileDialog.getSaveFileName(self, "Exportar tabela", "", "CSV (*.csv)")
        if fn:
            Path(fn).write_bytes((self.last_workdir / "globals.csv").read_bytes())

    # ================================================================== diversos
    def message(self, text: str, level: str = "info") -> None:
        prefix = {"erro": "✘ ", "aviso": "⚠ "}.get(level, "• ")
        self.messages.appendPlainText(prefix + text)
        if level == "erro":
            self.bottom.setCurrentIndex(0)

    def _hw_status(self) -> None:
        from kfem.gui.usage_bar import UsageBar

        self.usage_bar = UsageBar(self)
        self.statusBar().addPermanentWidget(self.usage_bar)
        self.hw_label = QLabel("  Cálculo: verificando GPU…  ")
        self.hw_label.setObjectName("muted")
        self.statusBar().addPermanentWidget(self.hw_label)
        self.hw_checked.connect(self._show_hw)

        def check() -> None:  # teste de sanidade em segundo plano: a janela abre sem esperar
            try:
                from kfem.hw.backend import select_backend_checked

                self.hw_checked.emit(select_backend_checked()[1])
            except Exception as exc:
                self.hw_checked.emit(str(exc))

        threading.Thread(target=check, daemon=True).start()

    def _show_hw(self, sel: object) -> None:
        if isinstance(sel, str):
            self.hw_label.setText("  Cálculo: CPU · diagnóstico indisponível  ")
            self.message(f"diagnóstico de hardware indisponível: {sel}", "aviso")
            return
        compute = getattr(sel, "compute", "cpu")
        self.hw_label.setText(f"  Cálculo: {compute.upper()} · Renderização: {getattr(sel, 'render', '?')}  ")
        failed = [a for a in getattr(sel, "attempts", []) if not a.ok and "sanidade" in a.reason]
        for a in failed:
            self.message(f"GPU ({a.backend}) não usada: {a.reason}", "aviso")
        if compute == "cpu" and self.auto_gpu_offer:
            self.offer_gpu_setup(force=False)

    # ------------------------------------------------------------------ instalação da GPU
    auto_gpu_offer = True  # os testes desligam

    @staticmethod
    def gpu_setup_script() -> Path | None:
        """O instalador: dentro do AppImage (usr/bin) ou no repositório (packaging/)."""
        cands = []
        if os.environ.get("KFEM_SDK"):
            cands.append(Path(os.environ["KFEM_SDK"]) / "bin" / "kfem-gpu-setup")
        cands.append(Path(__file__).resolve().parents[3] / "packaging" / "kfem-gpu-setup.sh")
        return next((c for c in cands if c.is_file()), None)

    @staticmethod
    def gpu_needing_setup() -> str | None:
        """Nome da placa AMD/NVIDIA que ficou sem cálculo na GPU, ou None."""
        from kfem.hw.backend import select_backend_checked

        hw, sel = select_backend_checked()
        if sel.compute != "cpu":
            return None
        for vendor in ("amd", "nvidia"):
            gs = hw.gpus_of(vendor)
            if gs:
                return f"{vendor.upper()} (dispositivo 0x{gs[0].device_id:04x})"
        return None

    def offer_gpu_setup(self, force: bool = False) -> None:
        st = QSettings("KFem", "KFem")
        if not force and st.value("gpu_setup_offered", False, type=bool):
            return
        card = self.gpu_needing_setup()
        if card is None:
            if force:
                self.message("A placa de vídeo já está em uso para o cálculo, ou não há placa AMD/NVIDIA.")
            return
        st.setValue("gpu_setup_offered", True)  # pergunta sozinho uma vez só
        script = self.gpu_setup_script()
        if script is None:
            self.message("Instalador da placa de vídeo não encontrado neste pacote.", "aviso")
            return
        r = QMessageBox.question(
            self,
            "Placa de vídeo",
            f"Placa {card} detectada, mas o cálculo está na CPU porque falta o driver ou o runtime "
            "da GPU.\n\nInstalar agora? O sistema vai pedir a sua senha de administrador "
            "(o KFem não a vê).\n\nVocê pode fazer isso depois em Ajuda → Configurar placa de vídeo…",
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        self.run_gpu_setup(script)

    def run_gpu_setup(self, script: Path) -> None:
        import shutil

        from PySide6.QtCore import QProcess

        # o AppImage é montado com FUSE e o root (pkexec) não lê lá dentro: copia para o cache
        cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kfem"
        cache.mkdir(parents=True, exist_ok=True)
        local = cache / "kfem-gpu-setup.sh"
        shutil.copy(script, local)
        pk = shutil.which("pkexec")
        if pk is None:
            self.message(f"Sem pkexec neste sistema. Rode no terminal: sudo bash {local} --auto", "aviso")
            return
        self.bottom.setCurrentIndex(2)
        self.logview.appendPlainText(f"$ pkexec bash {local} --auto")
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(
            lambda: self.logview.appendPlainText(
                bytes(proc.readAllStandardOutput().data()).decode(errors="replace").rstrip()
            )
        )
        proc.finished.connect(lambda code, _st: self._gpu_setup_done(code, cache))
        self._gpu_proc = proc
        proc.start(pk, ["bash", str(local), "--auto"])

    def _gpu_setup_done(self, code: int, cache: Path) -> None:
        (cache / "backend.json").unlink(missing_ok=True)  # o AppImage refaz o teste na próxima vez
        if code != 0:
            self.message(f"Instalação da placa de vídeo terminou com código {code} (veja o Log).", "aviso")
            return
        from kfem.hw.backend import select_backend_checked

        sel = select_backend_checked(refresh=True)[1]
        self.hw_label.setText(f"  Cálculo: {sel.compute.upper()} · Renderização: {sel.render}  ")
        self.message(
            f"Instalação concluída. Cálculo agora: {sel.compute.upper()}. "
            "Se pediu reinício (driver NVIDIA) ou novo login (grupo render), faça isso e abra o KFem de novo."
        )

    def show_diagnose(self) -> None:
        from kfem.hw.backend import format_report, select_backend_checked

        hw, sel = select_backend_checked()
        txt = format_report(hw, sel) + f"\n\nRenderizador VTK: {self.graphics.renderer_info}"
        self.logview.appendPlainText(txt)
        QMessageBox.information(self, "Diagnóstico de hardware", txt)

    @staticmethod
    def doc_path(name: str) -> Path | None:
        """PDF da documentação: dentro do AppImage (usr/share/doc/kfem) ou no repositório."""
        cands = []
        if os.environ.get("KFEM_SDK"):
            cands.append(Path(os.environ["KFEM_SDK"]) / "share" / "doc" / "kfem" / name)
        cands.append(Path(__file__).resolve().parents[3] / "docs" / "usuario" / name)
        return next((c for c in cands if c.is_file()), None)

    def open_doc(self, name: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        p = self.doc_path(name)
        if p is None:
            self.message(f"Documento não encontrado: {name}", "aviso")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(p))):
            self.message(f"Não foi possível abrir {p}: nenhum leitor de PDF configurado", "aviso")
        else:
            self.message(f"Abrindo {p.name}")

    def about(self) -> None:
        logo = Path(__file__).parent / "assets" / "kfem-logo.png"
        QMessageBox.about(
            self,
            "Sobre o KFem",
            f'<p style="background:#ffffff; padding:8px"><img src="{logo.as_uri()}" width="320"></p>'
            f"<b>KFem {__version__}</b><br>Simulador multifísico livre "
            "baseado no FEniCSx (DOLFINx).<br>Licença GPL-3.0-or-later.",
        )

    def closeEvent(self, ev: Any) -> None:
        if self.solver.is_running():
            if not self.ask("Há um cálculo em andamento. Cancelar e sair?"):
                ev.ignore()
                return
            self.solver.cancel()
        if not self._confirm_discard():
            ev.ignore()
            return
        QSettings("KFem", "KFem").setValue("geometry", self.saveGeometry())
        if self.graphics.plotter is not None:
            self.graphics.plotter.close()
        ev.accept()
