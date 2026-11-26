"""A janela gráfica lê o mesh.xdmf da DOLFINx (malha + marcadores), que o meshio não lê."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("dolfinx")
pytestmark = pytest.mark.fem


def test_read_dolfinx_mesh_with_tags(tmp_path):
    from dolfinx import io, mesh
    from mpi4py import MPI

    from kfem.gui.graphics import GraphicsView

    msh = mesh.create_unit_square(MPI.COMM_SELF, 4, 3)
    tdim = msh.topology.dim
    nc = msh.topology.index_map(tdim).size_local
    mid = mesh.compute_midpoints(msh, tdim, np.arange(nc, dtype=np.int32))
    tags = mesh.meshtags(msh, tdim, np.arange(nc, dtype=np.int32), np.where(mid[:, 0] < 0.5, 1, 2).astype(np.int32))
    tags.name = "cell_tags"
    f = tmp_path / "mesh.xdmf"
    with io.XDMFFile(MPI.COMM_SELF, str(f), "w") as xf:
        xf.write_mesh(msh)
        xf.write_meshtags(tags, msh.geometry)
    pts, cells, ctype, vals = GraphicsView.read_dolfinx_mesh(f)
    assert ctype == "triangle" and cells.shape == (nc, 3) and pts.shape[0] == msh.geometry.x.shape[0]
    assert vals is not None and sorted(set(vals.tolist())) == [1, 2]
