"""Escolha dos backends de cálculo e de renderização (Etapa 3, ADR 0005).

Ordem automática: CUDA → HIP → OpenCL → CPU. Um backend só é escolhido se:
1. a variante existe no SDK/AppImage (`$KFEM_SDK/petsc-<nome>`);
2. o driver ou runtime do sistema está presente;
3. o teste de sanidade passa (um sistema linear pequeno comparado com a CPU).

Quando um backend falha, o motivo é registrado e o próximo é tentado. A CPU nunca falha.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from kfem.hw.detect import AMD_NO_ROCM_DEVICE_IDS, HardwareReport

BACKENDS: tuple[str, ...] = ("cuda", "hip", "opencl", "cpu")
VALID_OVERRIDES: frozenset[str] = frozenset({"auto", *BACKENDS})

SanityTest = Callable[[str], tuple[bool, str]]  # backend -> (passou, detalhe)


@dataclass
class Attempt:
    backend: str
    ok: bool
    reason: str


@dataclass
class Selection:
    compute: str
    render: str
    attempts: list[Attempt] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)  # variáveis a definir no processo do solver
    override: str = "auto"

    def reason_for(self, backend: str) -> str:
        for a in self.attempts:
            if a.backend == backend:
                return a.reason
        return "não avaliado"


def sdk_root(env: Mapping[str, str] = os.environ) -> Path:
    return Path(env.get("KFEM_SDK", str(Path.home() / "kfem-sdk")))


def variant_present(backend: str, root: Path) -> bool:
    return (root / f"petsc-{backend}" / "lib").is_dir()


def opencl_env(hw: HardwareReport, env: Mapping[str, str]) -> dict[str, str]:
    """Ambiente para o Rusticl (Mesa) expor GPUs AMD/Intel com precisão dupla.

    Variáveis já definidas pelo usuário não são alteradas.
    """
    out: dict[str, str] = {}
    drivers = {g.driver for g in hw.gpus}
    rusticl = [p for p in hw.opencl_icds if "rusticl" in p.name]
    if rusticl:
        enable: list[str] = []
        if drivers & {"amdgpu", "radeon"}:
            enable.append("radeonsi")
        if drivers & {"i915", "xe"}:
            enable.append("iris")
        if enable and "RUSTICL_ENABLE" not in env:
            out["RUSTICL_ENABLE"] = ",".join(enable)
        if "RUSTICL_FEATURES" not in env:
            out["RUSTICL_FEATURES"] = "fp64"
    return out


def _driver_check(backend: str, hw: HardwareReport) -> tuple[bool, str]:
    if backend == "cuda":
        if not hw.gpus_of("nvidia"):
            return False, "nenhuma GPU NVIDIA"
        if hw.libcuda is None:
            return False, "GPU NVIDIA sem driver (libcuda.so não encontrada)"
        return True, f"libcuda em {hw.libcuda}"
    if backend == "hip":
        amd = hw.gpus_of("amd")
        if not amd:
            return False, "nenhuma GPU AMD"
        if hw.libhip is None:
            legacy = any(g.device_id in AMD_NO_ROCM_DEVICE_IDS for g in amd)
            extra = " (placa sem suporte ROCm atual)" if legacy else ""
            return False, f"runtime HIP/ROCm ausente{extra}"
        return True, f"libamdhip64 em {hw.libhip}"
    if backend == "opencl":
        if not hw.gpus:
            return False, "nenhuma GPU"
        if not hw.opencl_icds:
            return False, "nenhum ICD OpenCL em /etc/OpenCL/vendors"
        gpu_icds = [p for p in hw.opencl_icds if "intel64" not in p.name]  # intel64 = runtime de CPU
        if not gpu_icds:
            return False, "só há ICD OpenCL de CPU"
        return True, "ICDs: " + ", ".join(p.name for p in gpu_icds)
    return True, "sempre disponível"


def select_backend(
    hw: HardwareReport,
    *,
    env: Mapping[str, str] = os.environ,
    sanity: SanityTest | None = None,
    root: Path | None = None,
    override: str | None = None,
) -> Selection:
    """Escolhe o backend de cálculo e o de renderização. Nunca levanta exceção."""
    root = root if root is not None else sdk_root(env)
    choice = (override or env.get("KFEM_GPU", "auto")).strip().lower() or "auto"
    attempts: list[Attempt] = []
    if choice not in VALID_OVERRIDES:
        attempts.append(Attempt(choice, False, f"valor inválido de KFEM_GPU ('{choice}'); usando auto"))
        choice = "auto"
    order = list(BACKENDS) if choice == "auto" else [choice] + (["cpu"] if choice != "cpu" else [])

    solver_env: dict[str, str] = {}
    chosen = "cpu"
    for b in order:
        if b == "cpu":
            attempts.append(Attempt("cpu", True, "CPU + MPI (sempre disponível)"))
            chosen = "cpu"
            break
        ok, why = _driver_check(b, hw)
        if not ok:
            attempts.append(Attempt(b, False, why))
            continue
        if not variant_present(b, root):
            attempts.append(Attempt(b, False, f"variante petsc-{b} não incluída nesta instalação"))
            continue
        extra_env = opencl_env(hw, env) if b == "opencl" else {}
        if sanity is not None:
            passed, detail = sanity(b)
            if not passed:
                attempts.append(Attempt(b, False, f"teste de sanidade falhou: {detail}"))
                continue
            why = f"{why}; sanidade: {detail}"
        else:
            why = f"{why}; sanidade: não executada"
        attempts.append(Attempt(b, True, why))
        solver_env.update(extra_env)
        chosen = b
        break

    solver_env["KFEM_COMPUTE_BACKEND"] = chosen
    solver_env["PETSC_DIR"] = str(root / f"petsc-{chosen}")
    render = "gpu" if any(g.driver for g in hw.gpus) else "software (Mesa llvmpipe)"
    return Selection(compute=chosen, render=render, attempts=attempts, env=solver_env, override=choice)


def format_report(hw: HardwareReport, sel: Selection) -> str:
    lines = ["KFem — diagnóstico de hardware", "", "GPUs:"]
    lines += [f"  - {g.label}" for g in hw.gpus] or ["  (nenhuma)"]
    lines += [
        "",
        "Drivers/bibliotecas do sistema:",
        f"  libcuda:   {hw.libcuda or 'ausente'}",
        f"  libamdhip: {hw.libhip or 'ausente'}",
        f"  OpenCL:    {', '.join(p.name for p in hw.opencl_icds) or 'nenhum ICD'}",
        f"  ferramentas: {', '.join(sorted(hw.tools)) or 'nenhuma'}",
        "",
        f"Seleção de cálculo (KFEM_GPU={sel.override}):",
    ]
    lines += [f"  {'✔' if a.ok else '✘'} {a.backend:<7} {a.reason}" for a in sel.attempts]
    lines += ["", f"Backend de cálculo escolhido: {sel.compute}", f"Renderização: {sel.render}"]
    env_shown = {k: v for k, v in sel.env.items() if k.startswith("RUSTICL")}
    if env_shown:
        lines.append("Ambiente OpenCL: " + " ".join(f"{k}={v}" for k, v in env_shown.items()))
    lines += [f"Nota: {n}" for n in hw.notes]
    return "\n".join(lines)


def make_sanity(hw: HardwareReport, root: Path | None = None) -> SanityTest:
    """Teste de sanidade real: resolve um sistema pequeno em subprocesso, com a variante do PETSc."""
    from kfem.hw.sanity import run_sanity

    r = root if root is not None else sdk_root()

    def sanity(b: str) -> tuple[bool, str]:
        env = {"PETSC_DIR": str(r / f"petsc-{b}")}
        if b == "opencl":
            env.update(opencl_env(hw, {}))
        return run_sanity(b, env)

    return sanity


_checked: tuple[HardwareReport, Selection] | None = None
_checked_lock = threading.Lock()


def select_backend_checked(refresh: bool = False) -> tuple[HardwareReport, Selection]:
    """Detecção + escolha COM teste de sanidade, feita uma vez por processo (a interface usa esta).

    Sem o teste, uma variante instalada mas quebrada no driver (ex.: OpenCL na RX 580) seria
    escolhida e o cálculo cairia. Chamadas simultâneas esperam a primeira terminar.
    """
    global _checked
    with _checked_lock:
        if _checked is None or refresh:
            from kfem.hw.detect import detect

            hw = detect()
            _checked = (hw, select_backend(hw, sanity=make_sanity(hw)))
        return _checked
