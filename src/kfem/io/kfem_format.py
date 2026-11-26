"""Formato de projeto `.kfem` (ADR 0006).

É um ZIP com:
- `model.json`: a árvore do modelo, com esquema versionado (`format_version`);
- `mesh/`: malha em XDMF/HDF5, com os marcadores de domínio e de contorno;
- `results/`: resultados (XDMF/HDF5 ou VTX/BP) e tabelas CSV.

O JSON é texto aberto, legível e fácil de versionar. A gravação é atômica: escreve um
arquivo temporário e depois renomeia, para que uma queda no meio não corrompa o projeto.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from kfem import __version__
from kfem.model.parameters import ParameterSet
from kfem.model.tree import Component, Model, Node

FORMAT = "kfem"
FORMAT_VERSION = 1


class ProjectFormatError(ValueError):
    pass


def model_to_dict(m: Model) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "kfem_version": __version__,
        "name": m.name,
        "description": m.description,
        "parameters": {
            "groups": m.parameters.groups,
            "items": [
                {"name": p.name, "expr": p.expr, "description": p.description, "group": p.group}
                for p in m.parameters.params.values()
            ],
        },
        "functions": m.functions.to_dict(),
        "components": [c.to_dict() for c in m.components],
        "studies": m.studies.to_dict(),
        "results": m.results.to_dict(),
        "meta": m.meta,
    }


def model_from_dict(d: dict[str, Any]) -> Model:
    if d.get("format") != FORMAT:
        raise ProjectFormatError("não é um projeto KFem")
    v = int(d.get("format_version", 0))
    if v > FORMAT_VERSION:
        raise ProjectFormatError(f"projeto gravado por versão mais nova do formato ({v} > {FORMAT_VERSION})")
    ps = ParameterSet(groups=list(d["parameters"].get("groups", ["Parâmetros"])))
    for it in d["parameters"]["items"]:
        ps.add(it["name"], it["expr"], it.get("description", ""), it.get("group"))
    return Model(
        name=d.get("name", ""),
        description=d.get("description", ""),
        parameters=ps,
        functions=Node.from_dict(d["functions"]),
        components=[Component.from_dict(c) for c in d["components"]],
        studies=Node.from_dict(d["studies"]),
        results=Node.from_dict(d["results"]),
        meta=dict(d.get("meta", {})),
    )


def save(m: Model, path: str | Path, attachments: dict[str, Path | bytes] | None = None) -> Path:
    """Grava o projeto. `attachments`: nome no ZIP ('mesh/mesh.xdmf') → arquivo ou bytes.

    Anexos que já existem no projeto e não foram substituídos são mantidos.
    """
    path = Path(path)
    keep: dict[str, bytes] = {}
    if path.exists():
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n != "model.json" and (attachments is None or n not in attachments):
                    keep[n] = z.read(n)
    fd, tmp = tempfile.mkstemp(prefix=".kfem-", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("model.json", json.dumps(model_to_dict(m), indent=2, ensure_ascii=False))
            for n, data in keep.items():
                z.writestr(n, data)
            for n, src in (attachments or {}).items():
                if isinstance(src, bytes):
                    z.writestr(n, src)
                else:
                    z.write(src, n)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def load(path: str | Path) -> Model:
    with zipfile.ZipFile(path) as z:
        return model_from_dict(json.loads(z.read("model.json").decode("utf-8")))


def list_attachments(path: str | Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        return [n for n in z.namelist() if n != "model.json"]


def extract(path: str | Path, prefix: str, dest: str | Path) -> list[Path]:
    """Extrai os anexos que começam com `prefix` (ex.: 'mesh/') para `dest`."""
    out = []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.startswith(prefix) and not n.endswith("/"):
                target = Path(dest) / n
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(n))
                out.append(target)
    return out
