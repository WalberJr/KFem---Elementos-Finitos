"""Cache do backend: o AppImage monta num diretório diferente a cada execução."""

from pathlib import Path

from kfem.hw.env_shell import from_rel, to_rel


def test_cache_paths_follow_new_mount():
    first = Path("/tmp/.mount_KFem-aaaa/usr")
    env = {"PETSC_DIR": f"{first}/petsc-hip", "KFEM_COMPUTE_BACKEND": "hip"}
    stored = to_rel(env, first)
    assert "/tmp/.mount_KFem-aaaa" not in stored["PETSC_DIR"]
    second = Path("/tmp/.mount_KFem-bbbb/usr")
    got = from_rel(stored, second)
    assert got["PETSC_DIR"] == f"{second}/petsc-hip"
    assert got["KFEM_COMPUTE_BACKEND"] == "hip"
