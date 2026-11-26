"""Imprime `export ...` com o backend escolhido; usado pelo AppRun antes de iniciar.

A escolha roda o teste de sanidade (uma variante instalada mas quebrada no driver não pode
ser escolhida) e fica guardada em `~/.cache/kfem/backend.json`, com uma impressão digital do
hardware, dos drivers e da instalação. Muda algo, o teste roda de novo.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import sys
from pathlib import Path

ROOT_TOKEN = "${KFEM_SDK}"


def to_rel(env: dict[str, str], root: Path) -> dict[str, str]:
    return {k: str(v).replace(str(root), ROOT_TOKEN) for k, v in env.items()}


def from_rel(env: dict[str, str], root: Path) -> dict[str, str]:
    return {k: str(v).replace(ROOT_TOKEN, str(root)) for k, v in env.items()}


def _cache_file() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "kfem" / "backend.json"


def fingerprint(hw: object, root: Path) -> str:
    parts = [repr(getattr(hw, "gpus", "")), str(getattr(hw, "libcuda", "")), str(getattr(hw, "libhip", ""))]
    parts += [str(p) for p in getattr(hw, "opencl_icds", [])]
    parts += [os.environ.get("KFEM_GPU", "auto")]
    for v in sorted(root.glob("petsc-*")):
        lib = v / "lib" / "libpetsc.so"
        parts.append(f"{v.name}:{lib.stat().st_mtime if lib.exists() else 0}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def main() -> None:
    from kfem.hw.backend import make_sanity, sdk_root, select_backend
    from kfem.hw.detect import detect

    hw = detect()
    root = sdk_root()
    fp = fingerprint(hw, root)
    cf = _cache_file()
    env: dict[str, str] | None = None
    try:
        data = json.loads(cf.read_text())
        if data.get("fingerprint") == fp and "--refresh" not in sys.argv:
            # caminhos guardados relativos à instalação: o AppImage monta num diretório
            # diferente a cada execução (/tmp/.mount_KFem-XXXX)
            env = from_rel(data["env"], root)
    except (OSError, ValueError, KeyError):
        pass
    if env is None:
        sel = select_backend(hw, sanity=make_sanity(hw, root))
        env = dict(sel.env)
        try:
            cf.parent.mkdir(parents=True, exist_ok=True)
            rel = to_rel(env, root)
            cf.write_text(json.dumps({"fingerprint": fp, "env": rel, "compute": sel.compute}, indent=1))
        except OSError:
            pass
    for k, v in env.items():
        print(f"export {k}={shlex.quote(v)}")


if __name__ == "__main__":
    main()
