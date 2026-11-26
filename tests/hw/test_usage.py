from pathlib import Path

from kfem.hw.usage import UsageSampler, format_usage


def _fake(tmp: Path, busy: str = "37") -> UsageSampler:
    proc, drm = tmp / "proc", tmp / "drm"
    proc.mkdir()
    (proc / "meminfo").write_text("MemTotal:       32000000 kB\nMemAvailable:   16000000 kB\n")
    (proc / "stat").write_text("cpu  100 0 100 800 0 0 0 0 0 0\n")
    dev = drm / "card1" / "device"
    dev.mkdir(parents=True)
    (drm / "card1-HDMI-A-1").mkdir()
    (dev / "vendor").write_text("0x1002\n")
    (dev / "gpu_busy_percent").write_text(busy + "\n")
    (dev / "mem_info_vram_used").write_text(str(2 * 2**30))
    (dev / "mem_info_vram_total").write_text(str(8 * 2**30))
    s = UsageSampler(proc, drm)
    s._nvsmi = None
    return s


def test_usage_amd(tmp_path: Path) -> None:
    s = _fake(tmp_path)
    assert s.sample().cpu is None  # primeira leitura: só referência
    (tmp_path / "proc" / "stat").write_text("cpu  150 0 150 900 0 0 0 0 0 0\n")
    u = s.sample()
    assert u.cpu is not None and abs(u.cpu - 50.0) < 1e-9
    assert u.ram_total == 32000000 * 1024 and u.ram_used == 16000000 * 1024
    assert len(u.gpus) == 1 and u.gpus[0].busy == 37.0 and u.gpus[0].vram_total == 8 * 2**30
    txt = format_usage(u)
    assert "CPU 50%" in txt and "GPU 37%" in txt and "VRAM 2.0/8.0 GB" in txt


def test_usage_missing(tmp_path: Path) -> None:
    u = UsageSampler(tmp_path / "nada", tmp_path / "nada2")
    u._nvsmi = None
    r = u.sample()
    assert r.cpu is None and r.ram_total is None and r.gpus == []
    assert "GPU –" in format_usage(r)
