"""Execução do solver em processo separado (ADR 0009, Etapa 9).

A interface nunca roda o solver na thread principal.
- Inicia `mpiexec -n N python -m kfem.solvers.runner`, com N processos MPI × T threads OpenMP.
- Lê as linhas JSON da saída e as repassa como sinais Qt.
- **Cancelar:**
  1. cria o arquivo `CANCEL` no diretório de trabalho, para o solver parar num ponto seguro;
  2. se em 10 s ele não parou, manda SIGTERM;
  3. em 20 s, SIGKILL.
- Se o solver quebrar (falta de memória, falha de driver), só esse processo morre. A
  interface recebe `failed` e segue funcionando.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


def physical_cores() -> int:
    try:
        cores = set()
        cur: dict[str, str] = {}
        for line in [*Path("/proc/cpuinfo").read_text().splitlines(), ""]:
            if not line.strip():
                if "physical id" in cur and "core id" in cur:
                    cores.add((cur["physical id"], cur["core id"]))
                cur = {}
                continue
            k, _, v = line.partition(":")
            cur[k.strip()] = v.strip()
        return max(1, len(cores)) if cores else max(1, (os.cpu_count() or 2) // 2)
    except OSError:
        return max(1, (os.cpu_count() or 2) // 2)


def find_mpiexec() -> str | None:
    sdk = os.environ.get("KFEM_SDK", str(Path.home() / "kfem-sdk"))
    for cand in (Path(sdk) / "bin" / "mpiexec", Path(sys.prefix) / "bin" / "mpiexec"):
        if cand.exists():
            return str(cand)
    return shutil.which("mpiexec")


class SolverProcess(QObject):
    log = Signal(str)
    progress = Signal(float, str)
    started_run = Signal(str, str, int)  # workdir, backend, procs
    finished_ok = Signal(str, dict)  # workdir, summary
    cancelled = Signal(str)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.proc: QProcess | None = None
        self.workdir: Path | None = None
        self._buf = b""
        self._terminal_seen = False
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._escalate)
        self._stage = 0
        # acompanhamento de um cálculo iniciado fora da interface (log JSON em arquivo)
        self._watch_file: Path | None = None
        self._watch_pos = 0
        self._watch_timer = QTimer(self)
        self._watch_timer.timeout.connect(self._poll_watch)

    def is_running(self) -> bool:
        """Cálculo em andamento (depois da mensagem final o processo só está encerrando)."""
        if self._watch_file is not None:
            return not self._terminal_seen
        return (
            self.proc is not None and self.proc.state() != QProcess.ProcessState.NotRunning and not self._terminal_seen
        )

    def attach(self, log_file: str | Path, workdir: str | Path) -> None:
        """Acompanha um cálculo já em execução lendo o log JSON que ele grava.

        O cálculo continua independente da interface; "Parar" cria o arquivo CANCEL no
        diretório de trabalho, que o solver verifica a cada passo.
        """
        if self.is_running():
            raise RuntimeError("já existe um cálculo em andamento")
        self._watch_file = Path(log_file)
        self.workdir = Path(workdir)
        self._watch_pos = 0
        self._buf = b""
        self._terminal_seen = False
        self._stage = 0
        self.log.emit(f"acompanhando cálculo externo: log {self._watch_file}, saídas em {self.workdir}")
        self._poll_watch()
        if not self._terminal_seen:
            self._watch_timer.start(1000)

    def _poll_watch(self) -> None:
        if self._watch_file is None:
            return
        try:
            with open(self._watch_file, "rb") as fh:
                fh.seek(self._watch_pos)
                data = fh.read()
                self._watch_pos = fh.tell()
        except OSError:
            return
        self._buf += data
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            self._handle(line.decode("utf-8", errors="replace"))
        if self._terminal_seen:
            self._watch_timer.stop()

    def start(
        self,
        project: str,
        study: str | None,
        *,
        procs: int = 1,
        threads: int = 1,
        env_extra: dict[str, str] | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        if self.is_running():
            raise RuntimeError("já existe um cálculo em andamento")
        self.workdir = Path(tempfile.mkdtemp(prefix="kfem-run-"))
        args = ["-m", "kfem.solvers.runner", project, "--workdir", str(self.workdir)]
        if study:
            args += ["--study", study]
        args += extra_args or []
        mpiexec = find_mpiexec()
        proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("OMP_NUM_THREADS", str(threads))
        env.insert("OPENBLAS_NUM_THREADS", str(threads))
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("HDF5_USE_FILE_LOCKING", "FALSE")  # a interface lê os campos durante o cálculo
        src = str(Path(__file__).resolve().parents[2])
        env.insert("PYTHONPATH", src + os.pathsep + env.value("PYTHONPATH", ""))
        for k, v in (env_extra or {}).items():
            env.insert(k, v)
        pdir = (env_extra or {}).get("PETSC_DIR")
        if pdir:
            # só a variante escolhida no caminho (outra petsc-*/lib herdada carregaria a libpetsc errada)
            lib = str(Path(pdir) / "lib")
            for var in ("PYTHONPATH", "LD_LIBRARY_PATH"):
                keep = [p for p in env.value(var, "").split(os.pathsep) if p and "/petsc-" not in p]
                env.insert(var, os.pathsep.join([lib, *keep]))
        proc.setProcessEnvironment(env)
        if mpiexec and procs > 1:
            proc.setProgram(mpiexec)
            proc.setArguments(["-n", str(procs), sys.executable, *args])
        else:
            proc.setProgram(sys.executable)
            proc.setArguments(args)
        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.readyReadStandardError.connect(self._on_stderr)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self.proc = proc
        self._buf = b""
        self._terminal_seen = False
        self._stage = 0
        self.log.emit(f"iniciando: {proc.program()} {' '.join(proc.arguments())}")
        proc.start()

    def cancel(self) -> None:
        if not self.is_running() or self.workdir is None:
            return
        (self.workdir / "CANCEL").write_text("1")
        self.log.emit("cancelamento pedido; aguardando o solver parar num ponto seguro…")
        self._stage = 1
        if self._watch_file is not None:
            return  # processo externo: só o arquivo CANCEL (não há como mandar sinais)
        self._kill_timer.start(10_000)

    def _escalate(self) -> None:
        if not self.is_running() or self.proc is None:
            return
        if self._stage == 1:
            self.log.emit("solver não respondeu; enviando SIGTERM")
            self.proc.terminate()
            self._stage = 2
            self._kill_timer.start(10_000)
        else:
            self.log.emit("encerrando o solver à força (SIGKILL)")
            self.proc.kill()

    def _on_stdout(self) -> None:
        assert self.proc is not None
        self._buf += bytes(self.proc.readAllStandardOutput().data())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            self._handle(line.decode("utf-8", errors="replace"))

    def _on_stderr(self) -> None:
        assert self.proc is not None
        txt = bytes(self.proc.readAllStandardError().data()).decode("utf-8", errors="replace")
        for line in txt.splitlines():
            if line.strip():
                self.log.emit(f"[stderr] {line}")

    def _handle(self, line: str) -> None:
        try:
            msg: dict[str, Any] = json.loads(line)
        except ValueError:
            if line.strip():
                self.log.emit(line)
            # cálculo externo: o processo pode morrer sem mensagem final (sinal, MPI_Abort)
            if self._watch_file is not None and not self._terminal_seen and ("MPI_Abort" in line or "Killed" in line):
                self._terminal_seen = True
                self.failed.emit(f"o processo do solver terminou sem concluir: {line.strip()}")
            return
        t = msg.get("type")
        if t == "log":
            self.log.emit(str(msg.get("message", "")))
        elif t == "progress":
            self.progress.emit(float(msg.get("fraction", 0.0)), str(msg.get("message", "")))
        elif t == "start":
            self.started_run.emit(str(msg.get("workdir")), str(msg.get("backend")), int(msg.get("procs", 1)))
        elif t == "done":
            self._terminal_seen = True
            self.finished_ok.emit(str(msg.get("workdir")), dict(msg.get("summary", {})))
        elif t == "cancelled":
            self._terminal_seen = True
            self.cancelled.emit(str(msg.get("message", "")))
        elif t == "error":
            self._terminal_seen = True
            self.log.emit(str(msg.get("traceback", "")))
            self.failed.emit(str(msg.get("message", "erro desconhecido")))

    def _on_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._kill_timer.stop()
        if self._buf:
            self._handle(self._buf.decode("utf-8", errors="replace"))
            self._buf = b""
        if not self._terminal_seen:
            if self._stage > 0:
                self.cancelled.emit("cálculo interrompido")
            else:
                self.failed.emit(f"o processo do solver terminou inesperadamente (código {code})")
        self.proc = None

    def _on_error(self, err: QProcess.ProcessError) -> None:
        if err == QProcess.ProcessError.FailedToStart:
            self._terminal_seen = True
            self.failed.emit("não foi possível iniciar o processo do solver")
