"""Janela gráfica: geometria, malha e resultados com VTK/PyVista (renderização na GPU).

Se o VTK não puder abrir um contexto OpenGL, por exemplo sem servidor gráfico, a janela
mostra um aviso e o resto da interface continua funcionando.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from kfem.gui.theme import TOKENS


def _hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


LILAC_MAP = ["#0B0B0D", "#2A2140", "#5B3F86", "#8E6BC0", "#B79CDB", "#9FD9B4", "#3FBF73", "#E7F5EC"]


class GraphicsView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.title = QLabel("Janela gráfica")
        self.title.setObjectName("muted")
        self.field_box = QComboBox()
        self.field_box.setVisible(False)
        self.time_box = QComboBox()
        self.time_box.setVisible(False)
        bar.addWidget(self.title, 1)
        bar.addWidget(self.field_box)
        bar.addWidget(self.time_box)
        lay.addLayout(bar)
        self.plotter: Any = None
        self.renderer_info = "indisponível"
        try:
            import pyvista as pv
            from pyvistaqt import QtInteractor

            pv.global_theme.font.color = TOKENS["text"]
            self.plotter = QtInteractor(self)
            self.plotter.set_background(_hex_rgb(TOKENS["view_bottom"]), top=_hex_rgb(TOKENS["view_top"]))
            self.plotter.enable_parallel_projection()
            lay.addWidget(self.plotter.interactor, 1)
            try:
                rw = self.plotter.ren_win
                self.renderer_info = rw.ReportCapabilities().splitlines()[1] if rw else "?"
            except Exception:
                self.renderer_info = "OpenGL"
        except Exception as exc:  # sem OpenGL/VTK: a interface continua utilizável
            lab = QLabel(f"Visualização 3D indisponível: {exc}")
            lab.setObjectName("muted")
            lab.setWordWrap(True)
            lay.addWidget(lab, 1)
        self._series: dict[str, Any] = {}
        self.field_box.currentTextChanged.connect(lambda _t: (self._refresh_times(), self._redraw_result()))
        self.time_box.currentIndexChanged.connect(lambda _i: self._redraw_result())

    # ------------------------------------------------------------------ desenho
    MAX_ASPECT = 8.0  # acima disso (ex.: célula CDI de 100 × 1,2 mm) o desenho estica a vertical

    @staticmethod
    def y_scale(points: np.ndarray, max_aspect: float = MAX_ASPECT) -> float:
        """Fator de escala vertical só para desenho: geometrias muito alongadas viram uma linha."""
        if points.size == 0:
            return 1.0
        w = float(np.ptp(points[:, 0]))
        h = float(np.ptp(points[:, 1])) if points.shape[1] > 1 else 0.0
        if h <= 0 or w / h <= max_aspect:
            return 1.0
        return round(w / h / (max_aspect / 2), 1)

    def _scale_note(self, f: float) -> str:
        return f"  (escala vertical ×{f:g}, só no desenho)" if f != 1.0 else ""

    def _grid_from_mesh(self, points: np.ndarray, cells: np.ndarray, celltype: int, yscale: float = 1.0) -> Any:
        import pyvista as pv

        n = cells.shape[1]
        flat = np.hstack([np.full((cells.shape[0], 1), n), cells]).ravel()
        pts = points if points.shape[1] == 3 else np.c_[points, np.zeros(len(points))]
        if yscale != 1.0:
            pts = pts.copy()
            pts[:, 1] *= yscale
        return pv.UnstructuredGrid(flat, np.full(cells.shape[0], celltype, dtype=np.uint8), pts)

    def show_geometry_preview(self, rects: list[tuple[float, float, float, float]], labels: list[str]) -> None:
        if self.plotter is None:
            return
        import pyvista as pv

        self.plotter.clear()
        corners = (
            np.array([[x, y] for x, y, _w, _h in rects] + [[x + w, y + h] for x, y, w, h in rects])
            if rects
            else np.zeros((0, 2))
        )
        f = self.y_scale(corners)
        for (x, y0, w, h0), lab in zip(rects, labels, strict=False):
            y, h = y0 * f, h0 * f
            pl = pv.Rectangle([[x, y, 0], [x + w, y, 0], [x + w, y + h, 0]])
            self.plotter.add_mesh(
                pl, color=TOKENS["geometry"], opacity=0.35, show_edges=True, edge_color=TOKENS["primary"], line_width=2
            )
            self.plotter.add_point_labels(
                [[x + w / 2, y + h / 2, 0]],
                [lab],
                text_color=TOKENS["text"],
                shape_opacity=0.0,
                font_size=10,
                show_points=False,
            )
        self.plotter.view_xy()
        self.plotter.reset_camera()
        self.title.setText("Geometria (pré-visualização)" + self._scale_note(f))

    @staticmethod
    def read_dolfinx_mesh(xdmf: Path) -> tuple[np.ndarray, np.ndarray, str, np.ndarray | None]:
        """Lê o mesh.xdmf da DOLFINx: malha + marcadores de domínio (`cell_tags`).

        O meshio não lê esse arquivo (vários grids no mesmo XDMF). Devolve pontos, células,
        tipo ("triangle"/"tetra") e, se houver, o marcador de domínio de cada célula na mesma
        ordem das células devolvidas.
        """
        import xml.etree.ElementTree as ET

        import h5py

        root = ET.parse(xdmf).getroot()
        grids = {g.get("Name"): g for g in root.iter("Grid")}

        def data(item: ET.Element) -> np.ndarray:
            fname, _, dset = (item.text or "").strip().partition(":")
            with h5py.File(Path(xdmf).parent / fname, "r") as h:
                return np.asarray(h[dset][...])

        mesh = grids.get("mesh") or next(iter(grids.values()))
        geo = mesh.find("Geometry")
        if geo is None or geo.find("DataItem") is None:
            raise ValueError("XDMF sem geometria")
        pts = data(geo.find("DataItem"))
        tags = grids.get("cell_tags")
        src = tags if tags is not None else mesh
        topo = src.find("Topology")
        if topo is None or topo.find("DataItem") is None:
            raise ValueError("XDMF sem topologia")
        cells = data(topo.find("DataItem")).astype(np.int64)
        ctype = "tetra" if topo.get("TopologyType", "").lower().startswith("tetra") else "triangle"
        vals = None
        if tags is not None:
            att = tags.find("Attribute")
            if att is not None and att.find("DataItem") is not None:
                vals = data(att.find("DataItem")).ravel()
        return pts, cells, ctype, vals

    def show_mesh_file(self, xdmf: Path) -> None:
        """Malha colorida por domínio (mesh.xdmf da DOLFINx; meshio como alternativa)."""
        if self.plotter is None:
            return
        try:
            pts, cells, ctype, vals = self.read_dolfinx_mesh(xdmf)
        except Exception:
            import meshio

            m = meshio.read(xdmf)
            tri = next((c for c in m.cells if c.type in ("triangle", "tetra")), None)
            if tri is None:
                return
            pts, cells, ctype, vals = m.points, tri.data, tri.type, None
        f = self.y_scale(pts)
        grid = self._grid_from_mesh(pts, cells, 5 if ctype == "triangle" else 10, f)
        self.plotter.clear()
        if vals is not None and len(vals) == cells.shape[0]:
            grid.cell_data["domínio"] = vals
            ndom = len(np.unique(vals))
            self.plotter.add_mesh(
                grid,
                scalars="domínio",
                cmap=LILAC_MAP[2:7],
                categories=True,
                n_colors=max(ndom, 1),
                show_edges=True,
                edge_color="#2A2140",
                line_width=0.4,
                scalar_bar_args={"title": "domínio", "color": TOKENS["text"], "n_labels": ndom},
            )
        else:
            self.plotter.add_mesh(grid, color=TOKENS["geometry"], show_edges=True, edge_color="#5B3F86", line_width=0.5)
        self.plotter.view_xy()
        self.plotter.reset_camera()
        self.title.setText(f"Malha: {cells.shape[0]} elementos" + self._scale_note(f))

    def load_results(self, workdir: Path) -> list[str]:
        """Lê os campos `field_<nome>.xdmf` do diretório de resultados (séries temporais)."""
        import meshio

        self._series = {"fields": {}, "points": None, "cells": None}
        for f in sorted(Path(workdir).glob("field_*.xdmf")):
            name = f.stem.removeprefix("field_")
            times, data = [], []
            with meshio.xdmf.TimeSeriesReader(str(f)) as r:
                pts, cells = r.read_points_cells()
                for k in range(r.num_steps):
                    t, pdata, _ = r.read_data(k)
                    times.append(t)
                    data.append(next(iter(pdata.values())))
            self._series["points"], self._series["cells"] = pts, cells
            self._series["fields"][name] = (times, data)
        names = list(self._series["fields"])
        self.field_box.blockSignals(True)
        self.field_box.clear()
        self.field_box.addItems(names)
        if "cNa" in names:
            self.field_box.setCurrentText("cNa")
        self.field_box.blockSignals(False)
        self.field_box.setVisible(bool(names))
        self._refresh_times()
        self._redraw_result()
        return names

    def _refresh_times(self) -> None:
        name = self.field_box.currentText()
        times = self._series.get("fields", {}).get(name, ([], []))[0]
        self.time_box.blockSignals(True)
        self.time_box.clear()
        self.time_box.addItems([f"t = {t:g} s" for t in times])
        self.time_box.setCurrentIndex(len(times) - 1)
        self.time_box.blockSignals(False)
        self.time_box.setVisible(len(times) > 1)

    def _redraw_result(self) -> None:
        if self.plotter is None or not self._series.get("fields"):
            return
        name = self.field_box.currentText()
        if name not in self._series["fields"]:
            return
        times, series = self._series["fields"][name]
        if self.time_box.count() != len(times):
            self._refresh_times()
        k = min(max(0, self.time_box.currentIndex()), len(series) - 1)
        data = series[k]
        cells = self._series["cells"]
        tri = next((c for c in cells if c.type in ("triangle", "tetra")), None)
        f = self.y_scale(self._series["points"])
        grid = self._grid_from_mesh(self._series["points"], tri.data, 5 if tri.type == "triangle" else 10, f)
        arr = np.asarray(data)
        if arr.ndim == 2 and arr.shape[1] > 1:
            grid.point_data[name] = np.linalg.norm(arr, axis=1)
            vec = arr if arr.shape[1] == 3 else np.c_[arr, np.zeros(len(arr))]
            grid.point_data[name + "_vec"] = vec
        else:
            grid.point_data[name] = arr.ravel()
        self.plotter.clear()
        self.plotter.add_mesh(
            grid,
            scalars=name,
            cmap=LILAC_MAP,
            show_scalar_bar=True,
            scalar_bar_args={"title": name, "color": TOKENS["text"]},
        )
        self.plotter.view_xy()
        self.plotter.reset_camera()
        self.title.setText(f"{name} — {self.time_box.currentText()}" + self._scale_note(f))

    def screenshot(self, path: Path) -> None:
        if self.plotter is not None:
            self.plotter.screenshot(str(path))
