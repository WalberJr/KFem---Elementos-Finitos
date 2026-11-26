"""Montagem de elementos finitos da DOLFINx na GPU via HIP (Etapa 11).

O laço por célula da montagem é o que mais pesa no transiente do CDI (o núcleo gerado pelo
FFCx tem dezenas de pontos de quadratura por causa dos termos em exp(ln c)). Aqui esse laço
roda na GPU, uma thread por célula:

1. O código C dos núcleos (FFCx, via `dolfinx.jit.ffcx_jit`) é traduzido para HIP e
   compilado em tempo de execução com o hiprtc para a GPU presente.
2. A DOLFINx continua empacotando coeficientes e constantes na CPU (barato); os arrays vão
   para a GPU a cada montagem.
3. Cada thread calcula a matriz/vetor do elemento e soma direto na posição da matriz CSR
   local (posições pré-calculadas uma vez), com as linhas/colunas de Dirichlet já tratadas
   como na DOLFINx (zeradas, diagonal 1 nas linhas próprias).
4. O termo de "lifting" (A·(g − w) nas colunas de Dirichlet) sai da mesma matriz do elemento,
   sem custo extra.

A matriz CSR local volta para a CPU e entra no PETSc com `setValuesLocalCSR`; o solve segue
como antes (MUMPS). Só integrais de célula são suportadas; formas com integrais de faceta
fazem o chamador ficar na montagem da CPU.
"""

from __future__ import annotations

import ctypes
import os
import re
import time
from pathlib import Path
from typing import Any

import numpy as np

LIB_NAME = "libkfem_gpu_asm.so"


def find_library() -> Path | None:
    cands = []
    if os.environ.get("KFEM_GPU_ASM_LIB"):
        cands.append(Path(os.environ["KFEM_GPU_ASM_LIB"]))
    cands.append(Path(__file__).with_name(LIB_NAME))
    if os.environ.get("KFEM_SDK"):
        cands.append(Path(os.environ["KFEM_SDK"]) / "lib" / LIB_NAME)
    return next((c for c in cands if c.is_file()), None)


class _Lib:
    def __init__(self, path: Path) -> None:
        lib = ctypes.CDLL(str(path))
        u64, sz, vp, cp = ctypes.c_uint64, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_char_p
        lib.kga_device.argtypes = [cp, ctypes.c_int, cp, ctypes.c_int]
        lib.kga_compile.restype = vp
        lib.kga_compile.argtypes = [cp, ctypes.POINTER(cp), ctypes.c_int, cp, cp, ctypes.c_int]
        lib.kga_destroy.argtypes = [vp]
        lib.kga_alloc.restype = u64
        lib.kga_alloc.argtypes = [sz]
        lib.kga_free.argtypes = [u64]
        lib.kga_h2d.argtypes = [u64, vp, sz]
        lib.kga_d2h.argtypes = [vp, u64, sz]
        lib.kga_zero.argtypes = [u64, sz]
        lib.kga_launch.argtypes = [vp, ctypes.c_int, ctypes.c_int, ctypes.c_int, vp, sz]
        lib.kga_error_string.restype = cp
        lib.kga_error_string.argtypes = [ctypes.c_int]
        self.lib = lib

    def ok(self, code: int, what: str) -> None:
        if code != 0:
            raise RuntimeError(f"{what}: {self.lib.kga_error_string(code).decode()}")


class DeviceArray:
    """Array numpy espelhado na GPU (mesmo dtype e tamanho)."""

    def __init__(self, lib: _Lib, n: int, dtype: Any) -> None:
        self.lib = lib
        self.dtype = np.dtype(dtype)
        self.n = int(n)
        self.nbytes = self.n * self.dtype.itemsize
        self.ptr = lib.lib.kga_alloc(self.nbytes)
        if not self.ptr:
            raise MemoryError(f"GPU sem memória para {self.nbytes / 2**20:.1f} MB")

    def upload(self, a: np.ndarray) -> None:
        a = np.ascontiguousarray(a, dtype=self.dtype)
        assert a.size == self.n, (a.size, self.n)
        self.lib.ok(self.lib.lib.kga_h2d(self.ptr, a.ctypes.data, self.nbytes), "cópia para a GPU")

    def download(self, out: np.ndarray) -> None:
        assert out.dtype == self.dtype and out.size == self.n and out.flags.c_contiguous
        self.lib.ok(self.lib.lib.kga_d2h(out.ctypes.data, self.ptr, self.nbytes), "cópia da GPU")

    def zero(self) -> None:
        self.lib.ok(self.lib.lib.kga_zero(self.ptr, self.nbytes), "zerar na GPU")

    def free(self) -> None:
        if self.ptr:
            self.lib.lib.kga_free(self.ptr)
            self.ptr = 0


# --------------------------------------------------------------------------- tradução FFCx → HIP
_FN_RE = re.compile(r"^void (tabulate_tensor_integral_\w+)\(", re.M)


def extract_kernels(code: str) -> list[tuple[str, str]]:
    """(nome, corpo) de cada `tabulate_tensor_*` do código C do FFCx, na ordem do arquivo."""
    out = []
    for m in _FN_RE.finditer(code):
        start = m.start()
        # o corpo tem blocos internos fechados na coluna 0; o fim seguro é a declaração que o
        # FFCx sempre emite logo depois da função
        nxt = code.find("\nbool enabled_coefficients_", start)
        end = code.rindex("\n}", start, nxt if nxt >= 0 else len(code)) + 2
        out.append((m.group(1), code[start:end] + "\n"))
    return out


def integral_order(code: str) -> list[str]:
    """Nomes das integrais na ordem do formulário (form_integrals), para casar com a DOLFINx."""
    m = re.search(r"form_integrals_form_\w+\[\d+\] = \{([^}]*)\}", code)
    if not m:
        return []
    return [s.strip().lstrip("&") for s in m.group(1).split(",") if s.strip()]


def integral_types(code: str) -> list[int]:
    m = re.search(r"form_integral_offsets_form_\w+\[\d+\] = \{([^}]*)\}", code)
    return [int(x) for x in m.group(1).split(",")] if m else []


def to_hip(name: str, body: str, new_name: str) -> str:
    s = body.replace("restrict", "__restrict__")
    s = s.replace(f"void {name}(", f"static __device__ void {new_name}(", 1)
    return s


def ffcx_code(ufl_form: Any) -> str:
    """Código C do FFCx para a forma, com as opções padrão da DOLFINx (float64).

    Gerado direto pelo compilador do FFCx: o JIT devolve o código só quando compila, e não
    quando o módulo já está no cache.
    """
    import ffcx.compiler
    import ffcx.options

    opts = ffcx.options.get_options({"scalar_type": np.float64})
    code, _ = ffcx.compiler.compile_ufl_objects([ufl_form], options=opts, namespace="kfem_gpu")
    return str(code[1])


PRELUDE = """
typedef unsigned char uint8_t;
typedef int int32_t;
"""

_CELL_J = """
extern "C" __global__ __launch_bounds__(64) void {kname}(
    const int* __restrict__ cells, int n, const double* __restrict__ coeffs, int ncoef,
    const double* __restrict__ consts, const double* __restrict__ gx, const int* __restrict__ gdm,
    const int* __restrict__ dofs, const int* __restrict__ pos, double* __restrict__ vals,
    const double* __restrict__ g1, double* __restrict__ out1, const double* __restrict__ g2,
    double* __restrict__ out2, const unsigned char* __restrict__ isbc)
{{
  int e = blockIdx.x * blockDim.x + threadIdx.x;
  if (e >= n) return;
  int c = cells[e];
  double cd[{ng} * 3];
  for (int v = 0; v < {ng}; ++v)
    for (int d = 0; d < 3; ++d) cd[3 * v + d] = gx[3 * gdm[{ng} * c + v] + d];
  double A[{nd} * {nd}];
  for (int k = 0; k < {nd} * {nd}; ++k) A[k] = 0.0;
  {tname}(A, coeffs + (long)e * ncoef, consts, cd, 0, 0, 0);
  const int* p = pos + (long)e * {nd} * {nd};
  for (int k = 0; k < {nd} * {nd}; ++k)
    if (p[k] >= 0) atomicAdd(&vals[p[k]], A[k]);
  // lifting: out[i] += Σ_j A_ij g[j] nas colunas j de Dirichlet, em TODAS as linhas (como a
  // DOLFINx). O set_bc sobrescreve depois só as linhas de Dirichlet próprias; em paralelo um dof
  // fantasma pode ser de Dirichlet aqui e livre no processo dono, que precisa desta parcela.
  const int* cdofs = dofs + (long){nd} * c;
  if (g1 != 0) {{
    for (int i = 0; i < {nd}; ++i) {{
      int di = cdofs[i];
      double s1 = 0.0, s2 = 0.0;
      for (int j = 0; j < {nd}; ++j) {{
        int dj = cdofs[j];
        if (isbc[dj]) {{ s1 += A[{nd} * i + j] * g1[dj]; if (g2 != 0) s2 += A[{nd} * i + j] * g2[dj]; }}
      }}
      if (s1 != 0.0) atomicAdd(&out1[di], s1);
      if (g2 != 0 && s2 != 0.0) atomicAdd(&out2[di], s2);
    }}
  }}
}}
"""

_CELL_F = """
extern "C" __global__ __launch_bounds__(64) void {kname}(
    const int* __restrict__ cells, int n, const double* __restrict__ coeffs, int ncoef,
    const double* __restrict__ consts, const double* __restrict__ gx, const int* __restrict__ gdm,
    const int* __restrict__ dofs, double* __restrict__ vec)
{{
  int e = blockIdx.x * blockDim.x + threadIdx.x;
  if (e >= n) return;
  int c = cells[e];
  double cd[{ng} * 3];
  for (int v = 0; v < {ng}; ++v)
    for (int d = 0; d < 3; ++d) cd[3 * v + d] = gx[3 * gdm[{ng} * c + v] + d];
  double b[{nd}];
  for (int k = 0; k < {nd}; ++k) b[k] = 0.0;
  {tname}(b, coeffs + (long)e * ncoef, consts, cd, 0, 0, 0);
  const int* cdofs = dofs + (long){nd} * c;
  for (int i = 0; i < {nd}; ++i) atomicAdd(&vec[cdofs[i]], b[i]);
}}
"""


class _JArgs(ctypes.Structure):
    _fields_ = [
        ("cells", ctypes.c_uint64),
        ("n", ctypes.c_int),
        ("coeffs", ctypes.c_uint64),
        ("ncoef", ctypes.c_int),
        ("consts", ctypes.c_uint64),
        ("gx", ctypes.c_uint64),
        ("gdm", ctypes.c_uint64),
        ("dofs", ctypes.c_uint64),
        ("pos", ctypes.c_uint64),
        ("vals", ctypes.c_uint64),
        ("g1", ctypes.c_uint64),
        ("out1", ctypes.c_uint64),
        ("g2", ctypes.c_uint64),
        ("out2", ctypes.c_uint64),
        ("isbc", ctypes.c_uint64),
    ]


class _FArgs(ctypes.Structure):
    _fields_ = [
        ("cells", ctypes.c_uint64),
        ("n", ctypes.c_int),
        ("coeffs", ctypes.c_uint64),
        ("ncoef", ctypes.c_int),
        ("consts", ctypes.c_uint64),
        ("gx", ctypes.c_uint64),
        ("gdm", ctypes.c_uint64),
        ("dofs", ctypes.c_uint64),
        ("vec", ctypes.c_uint64),
    ]


class GpuAssembler:
    """Monta J (matriz), F (vetor) e o lifting de um par (J, F) na GPU.

    `J_ufl`/`F_ufl`: formas UFL; `J_form`/`F_form`: as mesmas compiladas pela DOLFINx (para
    empacotar coeficientes e obter domínios); `bcs`: condições de Dirichlet de J.
    """

    # frente de onda das GPUs AMD GCN. Os kernels declaram __launch_bounds__(64): sem isso o
    # compilador supõe blocos de 1024 threads, limita a 64 registradores e derrama a matriz do
    # elemento (12×12 doubles) na memória de rascunho, várias vezes mais lenta
    BLOCK = 64

    def __init__(self, comm: Any, J_ufl: Any, F_ufl: Any, J_form: Any, F_form: Any, bcs: list[Any]) -> None:
        from dolfinx import fem

        path = find_library()
        if path is None:
            raise RuntimeError(f"{LIB_NAME} não encontrada")
        self.L = _Lib(path)
        arch, name = ctypes.create_string_buffer(64), ctypes.create_string_buffer(256)
        if self.L.lib.kga_device(arch, 64, name, 256) != 0:
            raise RuntimeError("nenhuma GPU HIP disponível")
        self.device = f"{name.value.decode()} ({arch.value.decode()})"
        self.comm, self.J_form, self.F_form, self.bcs = comm, J_form, F_form, bcs
        self.fem = fem

        msh = J_form.mesh
        W = J_form.function_spaces[0]
        dmap = W.dofmap
        dl = dmap.list if hasattr(dmap, "list") else dmap.map()  # wrapper Python ou objeto C++
        if dmap.bs != 1:
            raise NotImplementedError("dofmap com bloco > 1 ainda não suportado na GPU")
        self.dofmap = np.ascontiguousarray(dl, dtype=np.int32)
        self.nd = self.dofmap.shape[1]
        gd = msh.geometry.dofmaps
        gdm = gd[0] if isinstance(gd, list) else gd(0)  # lista (C++) ou método
        self.ng = gdm.shape[1]
        imap = W.dofmap.index_map
        self.n_owned = imap.size_local * W.dofmap.index_map_bs
        self.n_local = (imap.size_local + imap.num_ghosts) * W.dofmap.index_map_bs

        # ---- código: traduz e compila os núcleos de J e F
        src = [PRELUDE]
        knames: list[str] = []
        self.j_kernels: list[tuple[int, int]] = []  # (índice do kernel, índice da integral)
        self.f_kernels: list[tuple[int, int]] = []
        for tag, ufl_form, form, tmpl, lst in (
            ("J", J_ufl, J_form, _CELL_J, self.j_kernels),
            ("F", F_ufl, F_form, _CELL_F, self.f_kernels),
        ):
            code = ffcx_code(ufl_form)
            offs = integral_types(code)
            if offs and any(o != offs[1] for o in offs[1:]):
                raise NotImplementedError(f"forma {tag} tem integrais de faceta (só células na GPU)")
            bodies = dict(extract_kernels(code))
            order = integral_order(code)
            ncell = form._cpp_object.num_integrals(fem.IntegralType.cell, 0)
            if len(order) != ncell:
                raise NotImplementedError(f"forma {tag}: {len(order)} integrais no FFCx, {ncell} na DOLFINx")
            for i, integ in enumerate(order):
                fname = "tabulate_tensor_" + integ
                tname = f"tt_{tag}{i}"
                kname = f"asm_{tag}{i}"
                src.append(to_hip(fname, bodies[fname], tname))
                src.append(tmpl.format(kname=kname, tname=tname, nd=self.nd, ng=self.ng))
                lst.append((len(knames), i))
                knames.append(kname)
        self.source = "\n".join(src)
        if os.environ.get("KFEM_GPU_ASM_SAVE"):
            Path(os.environ["KFEM_GPU_ASM_SAVE"]).write_text(self.source)
        err = ctypes.create_string_buffer(65536)
        names = (ctypes.c_char_p * len(knames))(*[k.encode() for k in knames])
        self.h = self.L.lib.kga_compile(self.source.encode(), names, len(knames), b"", err, 65536)
        if not self.h:
            raise RuntimeError(err.value.decode(errors="replace")[:4000])

        # ---- dados fixos na GPU: geometria, dofmap, células de cada integral
        self.d_gx = self._dev(np.ascontiguousarray(msh.geometry.x, dtype=np.float64))
        self.d_gdm = self._dev(np.ascontiguousarray(gdm, dtype=np.int32))
        self.d_dofs = self._dev(self.dofmap)
        self.cells: dict[str, list[np.ndarray]] = {"J": [], "F": []}
        self.d_cells: dict[str, list[DeviceArray]] = {"J": [], "F": []}
        for tag, form in (("J", J_form), ("F", F_form)):
            for i in range(form._cpp_object.num_integrals(fem.IntegralType.cell, 0)):
                cl = np.ascontiguousarray(form._cpp_object.domains(fem.IntegralType.cell, i), dtype=np.int32)
                self.cells[tag].append(cl)
                self.d_cells[tag].append(self._dev(cl))

        # ---- matriz CSR local (linhas próprias + fantasmas) e posições de cada entrada
        csr = fem.create_matrix(J_form)
        self.indptr = np.ascontiguousarray(csr.indptr, dtype=np.int32)
        self.indices = np.ascontiguousarray(csr.indices, dtype=np.int32)
        self.nnz = int(self.indptr[-1])
        isbc = np.zeros(self.n_local, dtype=np.uint8)
        for bc in bcs:
            d, _ = bc.dof_indices()
            isbc[d] = 1
        self.isbc = isbc
        self.d_isbc = self._dev(isbc)
        self.d_pos: list[DeviceArray] = []
        for cl in self.cells["J"]:
            self.d_pos.append(self._dev(self._positions(cl)))
        # diagonal 1 nas linhas de Dirichlet próprias (como insert_diagonal da DOLFINx)
        bc_rows = np.flatnonzero(isbc[: self.n_owned])
        self.diag_pos = np.array([self._find(r, r) for r in bc_rows], dtype=np.int64)
        self.vals = np.zeros(self.nnz, dtype=np.float64)
        self.d_vals = DeviceArray(self.L, self.nnz, np.float64)
        self.d_vec = DeviceArray(self.L, self.n_local, np.float64)
        self.d_out = [DeviceArray(self.L, self.n_local, np.float64) for _ in range(2)]
        self.d_g = [DeviceArray(self.L, self.n_local, np.float64) for _ in range(2)]
        self.timing: dict[str, float] = dict.fromkeys(("empacotar", "kernel_J", "kernel_F", "petsc"), 0.0)
        self._coef_buf: dict[tuple[str, int], DeviceArray] = {}
        self._const_buf: dict[str, DeviceArray] = {}

    # ------------------------------------------------------------------ auxiliares
    def _dev(self, a: np.ndarray) -> DeviceArray:
        d = DeviceArray(self.L, a.size, a.dtype)
        d.upload(a)
        return d

    def _find(self, r: int, c: int) -> int:
        lo, hi = self.indptr[r], self.indptr[r + 1]
        k = lo + int(np.searchsorted(self.indices[lo:hi], c))
        if k >= hi or self.indices[k] != c:
            raise RuntimeError(f"entrada ({r},{c}) fora da esparsidade")
        return k

    def _positions(self, cells: np.ndarray) -> np.ndarray:
        """Para cada célula e cada par (i, j): índice no array CSR, ou −1 (linha/coluna de Dirichlet)."""
        nd = self.nd
        dm = self.dofmap[cells]  # (n, nd)
        rows = np.repeat(dm, nd, axis=1).ravel()
        cols = np.tile(dm, (1, nd)).ravel()
        pos = np.empty(rows.size, dtype=np.int64)
        # busca vetorizada: chave linha*ncols + coluna nas listas ordenadas de cada linha
        ncol = int(self.indices.max()) + 1 if self.indices.size else 1
        row_of = np.repeat(np.arange(len(self.indptr) - 1, dtype=np.int64), np.diff(self.indptr))
        keys = row_of * ncol + self.indices.astype(np.int64)
        q = rows.astype(np.int64) * ncol + cols
        k = np.searchsorted(keys, q)
        if np.any(k >= keys.size) or np.any(keys[np.minimum(k, keys.size - 1)] != q):
            raise RuntimeError("célula com entrada fora da esparsidade da matriz")
        pos[:] = k
        pos[(self.isbc[rows] == 1) | (self.isbc[cols] == 1)] = -1
        return pos.astype(np.int32)

    def _upload_data(self, tag: str, form: Any) -> tuple[list[tuple[DeviceArray, int]], DeviceArray]:
        coeffs = self.fem.pack_coefficients(form)
        consts = np.ascontiguousarray(self.fem.pack_constants(form), dtype=np.float64)
        if consts.size == 0:
            consts = np.zeros(1)
        cb = self._const_buf.get(tag)
        if cb is None or cb.n != consts.size:
            cb = self._const_buf[tag] = DeviceArray(self.L, consts.size, np.float64)
        cb.upload(consts)
        out = []
        for i in range(len(self.cells[tag])):
            arr = coeffs[(self.fem.IntegralType.cell, i)]
            arr = np.ascontiguousarray(arr, dtype=np.float64)
            ncoef = arr.shape[1] if arr.ndim == 2 else 0
            buf = self._coef_buf.get((tag, i))
            n = max(arr.size, 1)
            if buf is None or buf.n != n:
                buf = self._coef_buf[(tag, i)] = DeviceArray(self.L, n, np.float64)
            if arr.size:
                buf.upload(arr)
            out.append((buf, ncoef))
        return out, cb

    def _launch(self, k: int, n: int, args: ctypes.Structure) -> None:
        self.L.ok(self.L.lib.kga_launch(self.h, k, n, self.BLOCK, ctypes.byref(args), ctypes.sizeof(args)), "kernel")

    # ------------------------------------------------------------------ montagem
    def assemble_matrix(self, A: Any, lifts: list[np.ndarray] | None = None) -> list[np.ndarray]:
        """Monta J em A (PETSc, mesma esparsidade e numeração local da DOLFINx).

        `lifts`: até 2 vetores locais g (valores de Dirichlet menos x0 nas linhas de Dirichlet,
        0 fora delas). Devolve, para cada g, o vetor local Σ_j A_ij g_j (todas as linhas).
        """
        from petsc4py import PETSc

        lifts = lifts or []
        t0 = time.perf_counter()
        coefs, cb = self._upload_data("J", self.J_form)
        t1 = time.perf_counter()
        self.d_vals.zero()
        ptrs = [0, 0]
        outp = [0, 0]
        for k_, g in enumerate(lifts[:2]):
            self.d_g[k_].upload(g)
            self.d_out[k_].zero()
            ptrs[k_] = self.d_g[k_].ptr
            outp[k_] = self.d_out[k_].ptr
        for (kidx, i), (buf, ncoef) in zip(self.j_kernels, coefs, strict=True):
            cl = self.d_cells["J"][i]
            args = _JArgs(
                cl.ptr,
                cl.n,
                buf.ptr,
                ncoef,
                cb.ptr,
                self.d_gx.ptr,
                self.d_gdm.ptr,
                self.d_dofs.ptr,
                self.d_pos[i].ptr,
                self.d_vals.ptr,
                ptrs[0],
                outp[0],
                ptrs[1],
                outp[1],
                self.d_isbc.ptr,
            )
            self._launch(kidx, cl.n, args)
        self.d_vals.download(self.vals)  # síncrono: inclui o tempo do kernel
        t2 = time.perf_counter()
        self.vals[self.diag_pos] = 1.0
        A.zeroEntries()
        A.setValuesLocalCSR(self.indptr, self.indices, self.vals, addv=PETSc.InsertMode.ADD_VALUES)
        A.assemble()
        t3 = time.perf_counter()
        self.timing["empacotar"] += t1 - t0
        self.timing["kernel_J"] += t2 - t1
        self.timing["petsc"] += t3 - t2
        res = []
        for k_ in range(len(lifts[:2])):
            o = np.empty(self.n_local)
            self.d_out[k_].download(o)
            res.append(o)
        return res

    def assemble_vector(self, b_local: np.ndarray) -> None:
        """Soma F no array local (próprios + fantasmas) `b_local`; o chamador faz o ghostUpdate."""
        t0 = time.perf_counter()
        coefs, cb = self._upload_data("F", self.F_form)
        t1 = time.perf_counter()
        self.d_vec.zero()
        for (kidx, i), (buf, ncoef) in zip(self.f_kernels, coefs, strict=True):
            cl = self.d_cells["F"][i]
            args = _FArgs(
                cl.ptr, cl.n, buf.ptr, ncoef, cb.ptr, self.d_gx.ptr, self.d_gdm.ptr, self.d_dofs.ptr, self.d_vec.ptr
            )
            self._launch(kidx, cl.n, args)
        tmp = np.empty(self.n_local)
        self.d_vec.download(tmp)
        b_local += tmp
        self.timing["empacotar"] += t1 - t0
        self.timing["kernel_F"] += time.perf_counter() - t1

    def free(self) -> None:
        for a in [
            self.d_gx,
            self.d_gdm,
            self.d_dofs,
            self.d_isbc,
            self.d_vals,
            self.d_vec,
            *self.d_out,
            *self.d_g,
            *self.d_pos,
            *self.d_cells["J"],
            *self.d_cells["F"],
            *self._coef_buf.values(),
            *self._const_buf.values(),
        ]:
            a.free()
        if self.h:
            self.L.lib.kga_destroy(self.h)
            self.h = None
