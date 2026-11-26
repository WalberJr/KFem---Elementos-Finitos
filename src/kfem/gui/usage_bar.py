"""Indicador compacto de uso de CPU, RAM e GPU na barra de status (atualiza a cada 2 s)."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from kfem.hw.usage import Usage, UsageSampler, format_usage, gib


class _Meter(QWidget):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lab = QLabel(label)
        lab.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setObjectName("usageMeter")
        self.bar.setRange(0, 100)
        self.bar.setFixedSize(84, 14)
        self.bar.setFormat("–")
        lay.addWidget(lab)
        lay.addWidget(self.bar)

    def set(self, pct: float | None, text: str) -> None:
        self.bar.setValue(round(pct) if pct is not None else 0)
        self.bar.setFormat(text)


class UsageBar(QWidget):
    def __init__(self, parent: QWidget | None = None, interval_ms: int = 2000) -> None:
        super().__init__(parent)
        self.sampler = UsageSampler()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(10)
        self.cpu = _Meter("CPU")
        self.ram = _Meter("RAM")
        self.gpu = _Meter("GPU")
        self.vram = _Meter("VRAM")
        for m in (self.cpu, self.ram, self.gpu, self.vram):
            lay.addWidget(m)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.sampler.sample()  # primeira leitura de /proc/stat (referência da CPU)
        self.timer.start(interval_ms)
        self.refresh()

    def refresh(self) -> None:
        self.show_usage(self.sampler.sample())

    def show_usage(self, u: Usage) -> None:
        self.setToolTip(format_usage(u))
        self.cpu.set(u.cpu, f"{u.cpu:.0f}%" if u.cpu is not None else "–")
        ram_pct = 100.0 * u.ram_used / u.ram_total if u.ram_used is not None and u.ram_total else None
        self.ram.set(ram_pct, f"{gib(u.ram_used)}/{gib(u.ram_total)} GB")
        g = u.gpus[0] if u.gpus else None
        self.gpu.set(g.busy if g else None, f"{g.busy:.0f}%" if g and g.busy is not None else "–")
        vpct = 100.0 * g.vram_used / g.vram_total if g and g.vram_used is not None and g.vram_total else None
        self.vram.set(vpct, f"{gib(g.vram_used)}/{gib(g.vram_total)} GB" if vpct is not None else "–")
        self.vram.setVisible(vpct is not None)
