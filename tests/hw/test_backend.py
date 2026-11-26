"""Etapa 3 — detecção e seleção de backend com /sys e bibliotecas simulados."""

from __future__ import annotations

from pathlib import Path

import pytest

from kfem.hw.backend import format_report, select_backend
from kfem.hw.detect import SystemRoots, detect


def make_sys(tmp: Path, cards: list[tuple[str, int, int, str]], icds: list[str] = (), libs: list[str] = ()):
    sysd, etc, lib = tmp / "sys", tmp / "etc", tmp / "lib"
    for i, (name, ven, dev, drv) in enumerate(cards):
        d = sysd / "class" / "drm" / name / "device"
        d.mkdir(parents=True)
        (d / "vendor").write_text(f"0x{ven:04x}\n")
        (d / "device").write_text(f"0x{dev:04x}\n")
        (d / "class").write_text("0x030000\n")
        (d / "uevent").write_text(f"DRIVER={drv}\nPCI_SLOT_NAME=0000:0{i}:00.0\n")
        (sysd / "class" / "drm" / f"{name}-HDMI-A-1").mkdir()  # conector: deve ser ignorado
    (etc / "OpenCL" / "vendors").mkdir(parents=True)
    for icd in icds:
        (etc / "OpenCL" / "vendors" / icd).write_text("lib.so\n")
    lib.mkdir()
    for name in libs:
        (lib / name).write_text("")
    return SystemRoots(sys=sysd, etc=etc, lib_dirs=(lib,), use_ldconfig=False)


def sdk(tmp: Path, variants: list[str]) -> Path:
    root = tmp / "sdk"
    for v in variants:
        (root / f"petsc-{v}" / "lib").mkdir(parents=True)
    return root


ALL = ["cpu", "cuda", "hip", "opencl"]
OK = lambda b: (True, "ok")
FAIL = lambda b: (False, "resultado diverge da CPU")


def test_nvidia_with_driver_picks_cuda(tmp_path):
    hw = detect(make_sys(tmp_path, [("card0", 0x10DE, 0x2484, "nvidia")], libs=["libcuda.so.1"]), which=lambda t: None)
    sel = select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL))
    assert sel.compute == "cuda" and sel.render == "gpu"


def test_nvidia_without_driver_falls_to_cpu(tmp_path):
    hw = detect(make_sys(tmp_path, [("card0", 0x10DE, 0x2484, "nouveau")]), which=lambda t: None)
    sel = select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL))
    assert sel.compute == "cpu"
    assert "sem driver" in sel.reason_for("cuda")


def test_nvidia_nouveau_with_opencl_uses_opencl(tmp_path):
    hw = detect(make_sys(tmp_path, [("card0", 0x10DE, 0x2484, "nouveau")], icds=["rusticl.icd"]), which=lambda t: None)
    sel = select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL))
    assert sel.compute == "opencl"


def test_amd_with_rocm_picks_hip(tmp_path):
    hw = detect(
        make_sys(tmp_path, [("card0", 0x1002, 0x744C, "amdgpu")], libs=["libamdhip64.so.6"]), which=lambda t: None
    )
    assert select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL)).compute == "hip"


def test_rx580_no_rocm_uses_opencl_and_sets_rusticl(tmp_path):
    hw = detect(
        make_sys(tmp_path, [("card0", 0x1002, 0x67DF, "amdgpu")], icds=["intel64.icd", "rusticl.icd"]),
        which=lambda t: None,
    )
    sel = select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL))
    assert sel.compute == "opencl"
    assert "sem suporte ROCm" in sel.reason_for("hip")
    assert sel.env["RUSTICL_ENABLE"] == "radeonsi" and sel.env["RUSTICL_FEATURES"] == "fp64"


def test_rusticl_user_env_not_overridden(tmp_path):
    hw = detect(make_sys(tmp_path, [("card0", 0x1002, 0x67DF, "amdgpu")], icds=["rusticl.icd"]), which=lambda t: None)
    sel = select_backend(hw, env={"RUSTICL_ENABLE": "radeonsi:1"}, sanity=OK, root=sdk(tmp_path, ALL))
    assert "RUSTICL_ENABLE" not in sel.env


def test_amd_old_only_cpu_icd_falls_to_cpu(tmp_path):
    hw = detect(make_sys(tmp_path, [("card0", 0x1002, 0x67DF, "amdgpu")], icds=["intel64.icd"]), which=lambda t: None)
    sel = select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL))
    assert sel.compute == "cpu" and "CPU" in sel.reason_for("opencl")


def test_intel_opencl(tmp_path):
    hw = detect(make_sys(tmp_path, [("card0", 0x8086, 0x46A6, "i915")], icds=["rusticl.icd"]), which=lambda t: None)
    sel = select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL))
    assert sel.compute == "opencl" and sel.env["RUSTICL_ENABLE"] == "iris"


def test_no_gpu(tmp_path):
    hw = detect(make_sys(tmp_path, []), which=lambda t: None)
    sel = select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL))
    assert sel.compute == "cpu" and sel.render.startswith("software")


def test_sanity_failure_falls_through(tmp_path):
    hw = detect(
        make_sys(tmp_path, [("card0", 0x10DE, 0x2484, "nvidia")], icds=["nvidia.icd"], libs=["libcuda.so.1"]),
        which=lambda t: None,
    )
    sel = select_backend(hw, env={}, sanity=FAIL, root=sdk(tmp_path, ALL))
    assert sel.compute == "cpu"
    assert "sanidade falhou" in sel.reason_for("cuda") and "sanidade falhou" in sel.reason_for("opencl")


def test_variant_missing(tmp_path):
    hw = detect(make_sys(tmp_path, [("card0", 0x10DE, 0x2484, "nvidia")], libs=["libcuda.so.1"]), which=lambda t: None)
    sel = select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ["cpu"]))
    assert sel.compute == "cpu" and "não incluída" in sel.reason_for("cuda")


@pytest.mark.parametrize("value,expected", [("cpu", "cpu"), ("opencl", "opencl"), ("CUDA", "cpu"), ("lixo", "opencl")])
def test_override(tmp_path, value, expected):
    hw = detect(make_sys(tmp_path, [("card0", 0x1002, 0x67DF, "amdgpu")], icds=["rusticl.icd"]), which=lambda t: None)
    sel = select_backend(hw, env={"KFEM_GPU": value}, sanity=OK, root=sdk(tmp_path, ALL))
    assert sel.compute == expected


def test_report_is_text(tmp_path):
    hw = detect(make_sys(tmp_path, [("card0", 0x1002, 0x67DF, "amdgpu")], icds=["rusticl.icd"]), which=lambda t: None)
    txt = format_report(hw, select_backend(hw, env={}, sanity=OK, root=sdk(tmp_path, ALL)))
    assert "Backend de cálculo escolhido: opencl" in txt
