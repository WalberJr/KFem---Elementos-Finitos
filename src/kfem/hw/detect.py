"""Detecção de GPUs, drivers e bibliotecas de cálculo (Etapa 3, ADR 0005).

Tudo aqui é só leitura e tolera falhas: nenhuma função levanta exceção por falta de
hardware, driver ou permissão. As raízes do sistema de arquivos podem ser trocadas, o que
permite testar com um /sys e um /etc simulados.
"""

from __future__ import annotations

import ctypes.util
import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

VENDORS: dict[int, str] = {0x10DE: "nvidia", 0x1002: "amd", 0x8086: "intel"}

# AMD sem suporte ROCm/HIP atual (Polaris/Vega10 antigas e anteriores). Lista conservadora:
# é só uma dica. A decisão real vem da presença do runtime HIP e do teste de sanidade.
AMD_NO_ROCM_DEVICE_IDS: frozenset[int] = frozenset(
    {0x67DF, 0x67EF, 0x67FF, 0x6FDF, 0x67C0, 0x67C4, 0x67C7, 0x67CF, 0x699F, 0x6987, 0x6985}
)


@dataclass(frozen=True)
class Gpu:
    """Uma GPU encontrada no barramento PCI (via /sys/class/drm)."""

    card: str
    vendor_id: int
    device_id: int
    driver: str
    pci_slot: str = ""

    @property
    def vendor(self) -> str:
        return VENDORS.get(self.vendor_id, f"desconhecido(0x{self.vendor_id:04x})")

    @property
    def label(self) -> str:
        return f"{self.vendor.upper()} 0x{self.device_id:04x} (driver {self.driver or '—'}, {self.card})"


@dataclass(frozen=True)
class SystemRoots:
    """Raízes do sistema consultado (trocadas nos testes)."""

    sys: Path = Path("/sys")
    etc: Path = Path("/etc")
    lib_dirs: tuple[Path, ...] = (
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/usr/lib64"),
        Path("/usr/lib"),
        Path("/lib/x86_64-linux-gnu"),
        Path("/opt/rocm/lib"),
        Path("/usr/local/cuda/lib64"),
    )
    use_ldconfig: bool = True


@dataclass
class HardwareReport:
    gpus: list[Gpu] = field(default_factory=list)
    libcuda: Path | None = None
    libhip: Path | None = None
    opencl_icds: list[Path] = field(default_factory=list)
    tools: dict[str, str] = field(default_factory=dict)  # nome -> caminho
    notes: list[str] = field(default_factory=list)

    def gpus_of(self, vendor: str) -> list[Gpu]:
        return [g for g in self.gpus if g.vendor == vendor]


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _hex(text: str) -> int | None:
    try:
        return int(text, 16)
    except ValueError:
        return None


def enumerate_gpus(roots: SystemRoots = SystemRoots()) -> list[Gpu]:
    """Lista GPUs a partir de /sys/class/drm/card*/device (sem duplicar o mesmo slot PCI)."""
    drm = roots.sys / "class" / "drm"
    found: dict[str, Gpu] = {}
    if not drm.is_dir():
        return []
    for card in sorted(drm.iterdir()):
        name = card.name
        if not name.startswith("card") or "-" in name:  # ignora conectores (card0-HDMI-A-1)
            continue
        dev = card / "device"
        vendor = _hex(_read(dev / "vendor"))
        device = _hex(_read(dev / "device"))
        if vendor is None or device is None:
            continue
        cls = _hex(_read(dev / "class"))
        if cls is not None and (cls >> 16) != 0x03:  # 0x03xxxx = controlador de vídeo
            continue
        driver = ""
        slot = ""
        for line in _read(dev / "uevent").splitlines():
            key, _, val = line.partition("=")
            if key == "DRIVER":
                driver = val
            elif key == "PCI_SLOT_NAME":
                slot = val
        key = slot or name
        if key not in found:
            found[key] = Gpu(card=name, vendor_id=vendor, device_id=device, driver=driver, pci_slot=slot)
    return list(found.values())


def find_library(names: Iterable[str], roots: SystemRoots = SystemRoots()) -> Path | None:
    """Procura uma biblioteca do sistema pelo nome exato (ex.: libcuda.so.1)."""
    names = list(names)
    for d in roots.lib_dirs:
        for n in names:
            p = d / n
            if p.exists():
                return p
    if roots.use_ldconfig:
        for n in names:
            base = n.removeprefix("lib").split(".so")[0]
            hit = ctypes.util.find_library(base)
            if hit:
                return Path(hit)
    return None


def opencl_icds(roots: SystemRoots = SystemRoots()) -> list[Path]:
    """ICDs OpenCL registrados (OCL_ICD_VENDORS tem prioridade, como no ocl-icd)."""
    env_dir = os.environ.get("OCL_ICD_VENDORS")
    d = Path(env_dir) if env_dir and roots.etc == Path("/etc") else roots.etc / "OpenCL" / "vendors"
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix == ".icd")


def detect(roots: SystemRoots = SystemRoots(), which: Callable[[str], str | None] = shutil.which) -> HardwareReport:
    rep = HardwareReport(gpus=enumerate_gpus(roots))
    rep.libcuda = find_library(["libcuda.so.1", "libcuda.so"], roots)
    rep.libhip = find_library(["libamdhip64.so.7", "libamdhip64.so.6", "libamdhip64.so"], roots)
    rep.opencl_icds = opencl_icds(roots)
    for tool in ("nvidia-smi", "rocminfo", "clinfo", "lspci"):
        path = which(tool)
        if path:
            rep.tools[tool] = path
    if not rep.gpus:
        rep.notes.append("nenhuma GPU encontrada em /sys/class/drm")
    return rep


def run_tool(args: list[str], timeout: float = 5.0) -> str:
    """Executa uma ferramenta de diagnóstico; devolve stdout ou '' em qualquer falha."""
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout
