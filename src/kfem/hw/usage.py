"""Uso de CPU, RAM e GPU da máquina, para o indicador da barra de status.

Lê só arquivos do kernel (`/proc`, `/sys/class/drm`) e, para NVIDIA, o `nvidia-smi` quando
existir. Nunca levanta exceção: o que não puder ser lido vem como `None`.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GpuUsage:
    name: str
    busy: float | None  # %
    vram_used: int | None  # bytes
    vram_total: int | None


@dataclass
class Usage:
    cpu: float | None  # % de todos os núcleos
    ram_used: int | None  # bytes
    ram_total: int | None
    gpus: list[GpuUsage]


def _read(p: Path) -> str | None:
    try:
        return p.read_text().strip()
    except OSError:
        return None


def _int(p: Path) -> int | None:
    s = _read(p)
    try:
        return int(s, 0) if s is not None else None
    except ValueError:
        return None


class UsageSampler:
    """Amostrador: o uso de CPU é a diferença entre duas leituras de /proc/stat."""

    def __init__(self, proc: Path = Path("/proc"), drm: Path = Path("/sys/class/drm")) -> None:
        self.proc = proc
        self.drm = drm
        self._last: tuple[int, int] | None = None
        self._nvsmi = shutil.which("nvidia-smi")

    def _cpu(self) -> float | None:
        s = _read(self.proc / "stat")
        if not s:
            return None
        f = [int(x) for x in s.splitlines()[0].split()[1:]]
        idle = f[3] + (f[4] if len(f) > 4 else 0)
        total = sum(f[:8])
        last, self._last = self._last, (idle, total)
        if last is None or total == last[1]:
            return None
        return max(0.0, min(100.0, 100.0 * (1.0 - (idle - last[0]) / (total - last[1]))))

    def _ram(self) -> tuple[int | None, int | None]:
        s = _read(self.proc / "meminfo")
        if not s:
            return None, None
        kv = {}
        for line in s.splitlines():
            k, _, v = line.partition(":")
            parts = v.split()
            if parts:
                kv[k] = int(parts[0]) * 1024
        tot, avail = kv.get("MemTotal"), kv.get("MemAvailable")
        return (tot - avail if tot is not None and avail is not None else None), tot

    def _gpus(self) -> list[GpuUsage]:
        out: list[GpuUsage] = []
        if self.drm.is_dir():
            for card in sorted(self.drm.glob("card[0-9]*")):
                if "-" in card.name:  # conectores (card1-HDMI-A-1)
                    continue
                dev = card / "device"
                vendor = _int(dev / "vendor")
                if vendor == 0x10DE:
                    continue  # NVIDIA: via nvidia-smi abaixo
                busy = _int(dev / "gpu_busy_percent")  # amdgpu
                used, tot = _int(dev / "mem_info_vram_used"), _int(dev / "mem_info_vram_total")
                if busy is None and used is None:
                    continue  # i915 e outros não expõem uso por sysfs
                name = {0x1002: "AMD", 0x8086: "Intel"}.get(vendor or 0, card.name)
                out.append(GpuUsage(name, float(busy) if busy is not None else None, used, tot))
        if self._nvsmi:
            try:
                r = subprocess.run(
                    [
                        self._nvsmi,
                        "--query-gpu=utilization.gpu,memory.used,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                for line in r.stdout.splitlines():
                    b, u, t = (x.strip() for x in line.split(","))
                    out.append(GpuUsage("NVIDIA", float(b), int(float(u)) << 20, int(float(t)) << 20))
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        return out

    def sample(self) -> Usage:
        try:
            cpu = self._cpu()
        except (ValueError, IndexError):
            cpu = None
        used, tot = self._ram()
        return Usage(cpu, used, tot, self._gpus())


def gib(n: int | None) -> str:
    return "?" if n is None else f"{n / 2**30:.1f}"


def format_usage(u: Usage) -> str:
    parts = [f"CPU {u.cpu:.0f}%" if u.cpu is not None else "CPU –"]
    parts.append(f"RAM {gib(u.ram_used)}/{gib(u.ram_total)} GB")
    for g in u.gpus:
        s = f"GPU {g.busy:.0f}%" if g.busy is not None else "GPU –"
        if g.vram_used is not None:
            s += f" · VRAM {gib(g.vram_used)}/{gib(g.vram_total)} GB"
        parts.append(s)
    if not u.gpus:
        parts.append("GPU –")
    return "   ".join(parts)
