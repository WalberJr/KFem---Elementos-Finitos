"""Etapa 6 — caso CDI acoplado (malha grossa, tempo curto) pelo processo do solver.

Confere:
- conservação de carga: W·∫ i_v nos dois eletrodos soma zero;
- equação do circuito: V = V_ext0 − Rc·I em todos os instantes;
- coerência física: a corrente decai com o tempo durante a carga em tensão constante.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("dolfinx")
pytestmark = [pytest.mark.fem, pytest.mark.slow]

from kfem.io import kfem_format  # noqa: E402
from kfem.model.tree import Node, Selection  # noqa: E402
from kfem.samples import cdi_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def run_case(tmp_path: Path, nprocs: int = 1, extra: list[str] | None = None) -> tuple[list[dict], dict]:
    m = cdi_model()
    m.comp.definitions.add(
        Node(
            "def.probe_integral",
            "dom2",
            "corrente eletrodo inferior",
            selection=Selection(2, [2]),
            props={"name": "I_bottom", "expr": "cd.ivtot*W", "unit": "A"},
        )
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    proj = kfem_format.save(m, tmp_path / "cdi.kfem")
    wd = tmp_path / "run"
    cmd = [
        sys.executable,
        "-m",
        "kfem.solvers.runner",
        str(proj),
        "--workdir",
        str(wd),
        "--mesh-scale",
        "3",
        "--tlist",
        "range(0,5,30)",
        *(extra or []),
    ]
    if nprocs > 1:
        import os
        import shutil

        sdk = Path(os.environ.get("KFEM_SDK", Path.home() / "kfem-sdk"))
        mpiexec = sdk / "bin" / "mpiexec" if (sdk / "bin" / "mpiexec").exists() else Path(shutil.which("mpiexec"))
        cmd = [str(mpiexec), "-n", str(nprocs), *cmd]
    out = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={
            "PYTHONPATH": str(ROOT / "src"),
            "PATH": "/usr/bin:/bin",
            "OMP_NUM_THREADS": "1",
            "HOME": str(Path.home()),
        },
        timeout=1800,
    )
    msgs = [json.loads(line) for line in out.stdout.splitlines() if line.startswith("{")]
    done = [x for x in msgs if x["type"] == "done"]
    assert done, out.stdout[-3000:] + out.stderr[-3000:]
    with open(wd / "globals.csv") as fh:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]
    return rows, done[0]["summary"]


def test_cdi_short_transient(tmp_path):
    rows, summary = run_case(tmp_path)
    si = cdi_model().parameters.to_si()
    for r in rows[1:]:
        assert abs(r["I_bottom"] + r["current"]) <= 1e-6 * max(abs(r["current"]), 1e-12) + 1e-12
        assert r["V"] == pytest.approx(si["V_ext0"] - si["Rc"] * r["current"], rel=1e-6, abs=1e-9)
    I = [abs(r["current"]) for r in rows[1:]]
    assert I[0] > 0 and I[-1] < I[0]
    assert summary["steps"][1]["accepted"] > 0


def test_cdi_mpi_matches_serial(tmp_path):
    rows1, _ = run_case(tmp_path / "s")
    rows4, _ = run_case(tmp_path / "p", nprocs=4)
    for a, b in zip(rows1, rows4, strict=True):
        assert b["current"] == pytest.approx(a["current"], rel=2e-2, abs=1e-9)
