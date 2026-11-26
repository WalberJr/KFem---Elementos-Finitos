"""Ponto de entrada `kfem`."""

from __future__ import annotations

import argparse
import sys

from kfem import __version__


def _diagnose(run_sanity: bool) -> int:
    from kfem.hw.backend import format_report, select_backend
    from kfem.hw.detect import detect

    hw = detect()
    sanity = None
    if run_sanity:
        from kfem.hw.backend import make_sanity

        sanity = make_sanity(hw)

    print(format_report(hw, select_backend(hw, sanity=sanity)))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kfem", description="KFem — simulador multifísico livre (FEniCSx)")
    p.add_argument("--version", action="version", version=f"KFem {__version__}")
    p.add_argument("--diagnose", action="store_true", help="mostra GPUs, drivers e o backend de cálculo")
    p.add_argument("--no-sanity", action="store_true", help="com --diagnose: não roda o teste de sanidade")
    p.add_argument("--solve", metavar="PROJETO.kfem", help="resolve um projeto sem interface")
    p.add_argument("-n", "--procs", type=int, default=1, help="com --solve: número de processos MPI")
    p.add_argument("--workdir", default=None, help="com --solve: diretório dos resultados")
    p.add_argument("--import-mph", metavar="ARQ.mph", help="converte um .mph para .kfem")
    p.add_argument("-o", "--output", metavar="SAIDA", help="arquivo de saída (com --import-mph)")
    p.add_argument(
        "--watch",
        nargs=2,
        metavar=("LOG", "DIR"),
        help="acompanha na interface um cálculo já em execução (log JSON e diretório de saídas)",
    )
    p.add_argument("project", nargs="?", help="projeto .kfem para abrir na interface")
    a = p.parse_args(argv)
    if a.diagnose:
        return _diagnose(not a.no_sanity)
    if a.import_mph:
        from kfem.io.mph import convert_mph

        out = a.output or a.import_mph.rsplit(".", 1)[0] + ".kfem"
        report = convert_mph(a.import_mph, out)
        print(report.summary())
        return 0
    if a.solve:
        args = [a.solve] + (["--workdir", a.workdir] if a.workdir else [])
        if a.procs > 1:
            import os
            import shutil

            from kfem.gui.solver_process import find_mpiexec

            mpiexec = find_mpiexec() or shutil.which("mpiexec")
            if not mpiexec:
                print("mpiexec não encontrado; resolvendo com 1 processo", file=sys.stderr)
            else:
                cmd = [mpiexec, "-n", str(a.procs), sys.executable, "-m", "kfem.solvers.runner", *args]
                os.execv(mpiexec, cmd)
        from kfem.solvers.runner import main as run_main

        return run_main(args)
    from kfem.gui.app import run_gui

    return run_gui(a.project, tuple(a.watch) if a.watch else None)


if __name__ == "__main__":
    sys.exit(main())
