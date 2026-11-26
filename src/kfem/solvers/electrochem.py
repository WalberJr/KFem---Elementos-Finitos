"""Passo transiente acoplado: corrente secundária + transporte diluído + equação global.

Formulação: docs/physics §2–§4. Incógnitas no espaço misto P1⁴ (φ_l, φ_s, c₁, c₂) e uma
incógnita global escalar (V).

Newton com "bordejamento" exato para a incógnita global:
1. Monta-se o Jacobiano J das PDEs e faz-se **uma** fatoração LU por iteração.
2. Com ela resolvem-se dois sistemas:
   - J·x₁ = −F, o passo de Newton com V fixo;
   - J·x₂ = 0, com x₂ = ∂(valor de Dirichlet)/∂V nos contornos que dependem de V
     (sensibilidade em relação a V).
3. A equação global linearizada g(V, I(w)) = 0 dá δV. A atualização é δw = x₁ + δV·x₂.

O resultado é exato, sem iterações externas, e custa só duas substituições por iteração.

Tempo: BDF1 no primeiro passo e BDF2 de passo variável depois, com controle de passo pela
diferença entre preditor e corretor. O passo é ajustado para cair exatamente nos instantes
de saída.
"""

from __future__ import annotations

import math
import os
import time as _time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from kfem.model.expressions import free_symbols
from kfem.model.tree import Model, Node
from kfem.physics.expr_ufl import to_ufl
from kfem.solvers.gpu_linear import HybridLinearSolver, gpu_backend
from kfem.solvers.setup import Materials, MeshData, model_functions, resolve


class Cancelled(Exception):
    pass


@dataclass
class TransientResult:
    times: list[float] = field(default_factory=list)
    globals: dict[str, list[float]] = field(default_factory=dict)
    steps: int = 0
    rejected: int = 0
    newton_its: int = 0
    wall: float = 0.0
    profile: dict[str, float] = field(default_factory=dict)  # s por fase do Newton


LN_C_MIN = math.log(1e-14)  # mol/m³
LN_C_MAX = math.log(1e5)


def _num(v: Any) -> float:
    return float(v)


def _sigma_floor(sig: Any, smin: float) -> Any:
    """max suave: ½(σ + √(σ² + σ_min²)) ≥ σ_min/2 e ≈ σ quando σ ≫ σ_min."""
    if smin <= 0 or isinstance(sig, (int, float)):
        return sig
    import ufl

    return 0.5 * (sig + ufl.sqrt(sig * sig + smin * smin))


def _sum_forms(forms: list[Any]) -> Any:
    if not forms:
        raise ValueError("seleção vazia em uma sonda")
    total = forms[0]
    for f in forms[1:]:
        total = total + f
    return total


def _profile_assembly(comm: Any, J: Any, Fres: Any, J_form: Any, F_form: Any, A: Any, bcs: Any, log: Any) -> None:
    """Diagnóstico (KFEM_ASM_PROFILE): divide o tempo da montagem e salva os núcleos do FFCx."""
    from dolfinx import fem, jit
    from dolfinx.fem import petsc as fpetsc

    def tm(fn: Callable[[], Any], n: int = 3) -> float:
        best = 1e300
        for _ in range(n):
            t0 = _time.perf_counter()
            fn()
            best = min(best, _time.perf_counter() - t0)
        return comm.allreduce(best, op=MPI_MAX())

    coeffs = fem.pack_coefficients(J_form)
    consts = fem.pack_constants(J_form)
    t_pack = tm(lambda: (fem.pack_coefficients(J_form), fem.pack_constants(J_form)))
    t_petsc = tm(lambda: (A.zeroEntries(), fpetsc.assemble_matrix(A, J_form, bcs=bcs), A.assemble()))
    t_pre = tm(
        lambda: (
            A.zeroEntries(),
            fpetsc.assemble_matrix(A, J_form, bcs=bcs, constants=consts, coeffs=coeffs),
            A.assemble(),
        )
    )
    t_csr = tm(lambda: fem.assemble_matrix(J_form, bcs=bcs, constants=consts, coeffs=coeffs))
    t_vec = tm(lambda: fem.assemble_vector(F_form))
    ncells = {k: v.shape[0] for k, v in coeffs.items()}
    log(
        f"montagem J: total PETSc {t_petsc:.3f} s; empacotar coeficientes {t_pack:.3f} s; "
        f"com coef. prontos: PETSc {t_pre:.3f} s, CSR nativa {t_csr:.3f} s; vetor F {t_vec:.3f} s; "
        f"integrais (tipo, id): entidades {ncells}"
    )
    for nm, form in (("J", J), ("F", Fres)):
        _, _, (hdr, code) = jit.ffcx_jit(comm, form)
        if comm.rank == 0:
            with open(f"kernel_{nm}.c", "w") as fh:
                fh.write(code)
            with open(f"kernel_{nm}.h", "w") as fh:
                fh.write(hdr)
    if comm.size == 1:  # dados reais para o protótipo da montagem em GPU
        msh = J_form.mesh
        Wsp = J_form.function_spaces[0]
        ref = fem.assemble_matrix(J_form, constants=consts, coeffs=coeffs)
        fv = fem.assemble_vector(F_form)
        data: dict[str, Any] = {
            "geom_x": msh.geometry.x,
            "geom_dofmap": msh.geometry.dofmap,
            "dofmap": Wsp.dofmap.list,
            "consts": consts,
            "ref_indptr": ref.indptr,
            "ref_indices": ref.indices,
            "ref_data": ref.data,
            "F_ref": fv.array,
        }
        for (itype, iid), arr in coeffs.items():
            data[f"coeffs_{iid}"] = arr
            data[f"cells_{iid}"] = J_form._cpp_object.domains(itype, iid)
        np.savez("asm_data.npz", **data)
    log("núcleos do FFCx salvos em kernel_J.c e kernel_F.c")


def MPI_MAX() -> Any:
    from mpi4py import MPI

    return MPI.MAX


def solve_transient(
    model: Model,
    step: Node,
    md: MeshData,
    mats: Materials,
    si: dict[str, float],
    velocity: Any | None,
    *,
    on_output: Callable[[float, dict[str, Any], dict[str, float]], None] | None = None,
    log: Callable[[str], None] = print,
    progress: Callable[[float, str], None] | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    petsc_options: dict[str, Any] | None = None,
) -> TransientResult:
    import basix.ufl
    import ufl
    from dolfinx import fem
    from dolfinx.fem import petsc as fpetsc
    from mpi4py import MPI
    from petsc4py import PETSc

    from kfem.solvers.setup import parse_tlist

    comm = md.mesh.comm
    msh = md.mesh
    comp = model.comp
    active = set(step.props.get("physics", []))
    phys = {n.tag: n for n in comp.physics.active_children() if n.tag in active}
    cd = next((n for n in phys.values() if n.kind == "physics.current"), None)
    tds = next((n for n in phys.values() if n.kind == "physics.transport"), None)
    glob = next((n for n in phys.values() if n.kind == "physics.global"), None)
    if cd is None or tds is None:
        raise ValueError("este passo transiente precisa das físicas de corrente e de transporte ativas")
    couplings = set(step.props.get("couplings", []))
    use_conv = velocity is not None and any(
        m.kind == "multi.flow_transport" and m.tag in couplings for m in comp.multiphysics.active_children()
    )
    funcs = model_functions(model, si)

    species: list[str] = list(tds.props["species"])
    ns = len(species)
    charges = [_num(to_ufl(z, si)) for z in tds.props.get("charges", ["0"] * ns)]
    T = _num(to_ufl(tds.props.get("temperature", "293.15[K]"), si))
    F, R = si["F_const"], si["R_const"]

    # ---------------------------------------------------------------- espaços e funções
    P1 = basix.ufl.element("Lagrange", msh.basix_cell(), 1)
    W = fem.functionspace(msh, basix.ufl.mixed_element([P1] * (2 + ns)))
    w, w_n, w_nm1 = fem.Function(W), fem.Function(W), fem.Function(W)
    dw = ufl.TrialFunction(W)
    tests = ufl.TestFunctions(W)
    fields = ufl.split(w)
    log_c = str(tds.props.get("formulation", "log")) == "log"
    c_eps = float(model.meta.get("c_floor", 1e-6))  # mol/m³: valor de c=0 em Dirichlet na forma ln c
    phil, phis = fields[0], fields[1]
    cs = [ufl.exp(u) for u in fields[2:]] if log_c else list(fields[2:])
    psil, psis, cts = tests[0], tests[1], list(tests[2:])
    names = ["phil", "phis", *species]
    sub_maps = [np.asarray(W.sub(i).collapse()[1], dtype=np.int64).ravel() for i in range(2 + ns)]

    dt = fem.Constant(msh, PETSc.ScalarType(1e-2))
    a0 = fem.Constant(msh, PETSc.ScalarType(1.0))  # coeficientes BDF (já divididos por dt)
    a1 = fem.Constant(msh, PETSc.ScalarType(-1.0))
    a2 = fem.Constant(msh, PETSc.ScalarType(0.0))
    tconst = fem.Constant(msh, PETSc.ScalarType(0.0))

    def ddt_c(i: int) -> Any:
        """∂c/∂t por BDF; na forma ln c usa exp(u) em cada nível de tempo."""
        if not log_c:
            return ddt(i)
        return a0 * ufl.exp(ufl.split(w)[i]) + a1 * ufl.exp(ufl.split(w_n)[i]) + a2 * ufl.exp(ufl.split(w_nm1)[i])

    def ddt(i: int) -> Any:
        return a0 * ufl.split(w)[i] + a1 * ufl.split(w_n)[i] + a2 * ufl.split(w_nm1)[i]

    sym: dict[str, Any] = dict(si)
    sym.update({"phil": phil, "phis": phis, "t": tconst})
    for s, c in zip(species, cs, strict=True):
        sym[s] = c
    # variáveis do componente (ex.: cond) — dependem dos campos
    for vn in comp.definitions.active_children("def.variables"):
        for name, expr in vn.props.get("vars", []):
            sym[name] = to_ufl(expr, sym, funcs)

    dx = ufl.Measure("dx", domain=msh, subdomain_data=md.cell_tags)

    # ---------------------------------------------------------------- corrente secundária
    cd_nodes = cd.children
    dom_cd = resolve(cd_nodes, md.domains, ("current.electrolyte", "current.porous_electrode"))
    electrode_doms = [d for d, n in dom_cd.items() if n.kind == "current.porous_electrode"]
    _num(to_ufl(cd.props.get("thickness", "1[m]"), si))

    # salvaguarda numérica (docs/physics §5): piso suave em σ_l para manter a equação elíptica
    # se as concentrações ficarem negativas; não altera nada enquanto σ_l ≫ sigma_min
    sigma_min = float(model.meta.get("sigma_l_floor", 1e-4))  # S/m (σ_l(c0) ≈ 0,24 S/m no caso CDI)
    res_l: Any = 0
    res_s: Any = 0
    iv_d: dict[int, Any] = {}
    for d in md.domains:
        n = dom_cd.get(d)
        if n is None:
            continue
        if n.kind == "current.electrolyte":
            sig = _sigma_floor(mats.resolve_prop(n.props["sigmal"], d, sym), sigma_min)
            res_l += sig * ufl.inner(ufl.grad(phil), ufl.grad(psil)) * dx(d)
        else:
            epsl = to_ufl(n.props["epsl"], sym)
            epss = to_ufl(n.props["epss"], sym)
            brug = _num(to_ufl(n.props.get("brug", "1.5"), si)) if n.props.get("correction") == "bruggeman" else 0.0
            fl = epsl**brug if brug else 1.0
            fs = epss**brug if brug else 1.0
            sigl = _sigma_floor(mats.resolve_prop(n.props["sigmal"], d, sym), sigma_min) * fl
            sigs = mats.resolve_prop(n.props["sigmas"], d, sym) * fs
            iv: Any = 0
            for ch in n.children:
                if not ch.active:
                    continue
                if ch.kind == "current.double_layer":
                    Cv = to_ufl(ch.props["av"], sym) * to_ufl(ch.props["Cdl"], sym)
                    iv = iv + Cv * (ddt(1) - ddt(0))
                elif ch.kind == "current.reaction_linear":
                    i0 = to_ufl(ch.props["i0"], sym)
                    av = to_ufl(ch.props["av"], sym)
                    eta = phis - phil - to_ufl(ch.props["Eeq"], sym)
                    aa, ac = to_ufl(ch.props["alphaa"], sym), to_ufl(ch.props["alphac"], sym)
                    iv = iv + av * i0 * (aa + ac) * F / (R * T) * eta
            iv_d[d] = iv
            res_l += sigl * ufl.inner(ufl.grad(phil), ufl.grad(psil)) * dx(d) - iv * psil * dx(d)
            res_s += sigs * ufl.inner(ufl.grad(phis), ufl.grad(psis)) * dx(d) + iv * psis * dx(d)
    iv_total = mats.piecewise(iv_d) if iv_d else 0.0
    sym["cd.ivdl"] = iv_total
    sym["cd.ivtot"] = iv_total
    sym[f"{cd.tag}.ivdl"] = iv_total
    sym[f"{cd.tag}.ivtot"] = iv_total

    # ---------------------------------------------------------------- transporte
    tnodes = tds.children
    dom_t = resolve(tnodes, md.domains, ("transport.free", "transport.porous"))
    migr = bool(tds.props.get("migration", True))
    res_c: Any = 0
    h = ufl.CellDiameter(msh)
    for d in md.domains:
        n = dom_t.get(d)
        if n is None:
            continue
        if n.kind == "transport.free":
            eps: Any = 1.0
            Ds = [to_ufl(x, sym) for x in n.props["D"]]
        else:
            eps = mats.resolve_prop(n.props["porosity"], d, sym)
            factor = eps**1.5 if n.props.get("model", "bruggeman") == "bruggeman" else 1.0
            Ds = [to_ufl(x, sym) * factor for x in n.props["DF"]]
        for i in range(ns):
            c, ct, D, z = cs[i], cts[i], Ds[i], charges[i]
            flux = D * ufl.grad(c)
            if migr and z != 0:
                flux = flux + z * D / (R * T) * F * c * ufl.grad(phil)
            r = eps * ddt_c(2 + i) * ct + ufl.inner(flux, ufl.grad(ct))
            if use_conv:
                r = r + ufl.inner(velocity, ufl.grad(c)) * ct
                if tds.props.get("supg", True):
                    unorm = ufl.sqrt(ufl.inner(velocity, velocity) + 1e-30)
                    pe = unorm * h / (2 * D)
                    tau = h / (2 * unorm) * ufl.min_value(pe / 3.0, 1.0)  # aproximação de coth(Pe)−1/Pe
                    strong = eps * ddt_c(2 + i) + ufl.inner(velocity, ufl.grad(c))
                    r = r + tau * strong * ufl.inner(velocity, ufl.grad(ct))
            res_c += r * dx(d)
    # fontes por acoplamento com eletrodo poroso: R_i = −ν_i·i_v/(nF)
    c_ref = float(model.meta.get("depletion_c_ref", tds.props.get("depletion_c_ref", 1e-2)))  # mol/m³; 0 desliga
    for pec in [n for n in tnodes if n.active and n.kind == "transport.electrode_coupling"]:
        pec_doms = resolve([pec], md.domains, ("transport.electrode_coupling",))
        rc_map = resolve(pec.children, md.domains, ("transport.reaction_coeffs",))
        for d in pec_doms:
            rc = rc_map.get(d)
            if rc is None:
                continue
            ivx = to_ufl(rc.props["iv"], sym)
            nel = to_ufl(rc.props["n"], sym)
            for i, nu in enumerate(rc.props.get("nu", [])):
                nuv = to_ufl(nu, sym)
                if isinstance(nuv, (int, float)) and nuv == 0:
                    continue
                sgn = float(model.meta.get("reaction_sign", -1.0))  # R_i = sgn·ν_i·i_v/(nF); −1 = convenção documentada
                Ri = sgn * nuv * ivx / (nel * F)
                if c_ref > 0:
                    # limitador de esgotamento (docs/physics §5): a remoção da espécie i → 0 quando c_i → 0
                    lim = cs[i] / (cs[i] + c_ref)
                    Ri = ufl.conditional(ufl.lt(Ri, 0.0), Ri * lim, Ri)
                res_c += (-Ri) * cts[i] * dx(d)  # −R·ĉ

    Fres = res_l + res_s + res_c
    J = ufl.derivative(Fres, w, dw)
    F_form = fem.form(Fres)
    J_form = fem.form(J)

    # ---------------------------------------------------------------- funcionais globais (sondas)
    probe_forms: dict[str, Any] = {}
    probe_dforms: dict[str, Any] = {}
    xprobe = fem.Function(W)
    for pn in comp.definitions.active_children("def.probe_integral"):
        pdoms = resolve([pn], md.domains, ("def.probe_integral",))
        expr = to_ufl(pn.props["expr"], sym)
        form = _sum_forms([expr * dx(d) for d in pdoms])
        probe_forms[pn.props["name"]] = fem.form(form)
        probe_dforms[pn.props["name"]] = fem.form(ufl.derivative(form, w, xprobe))
    ds = ufl.Measure("ds", domain=msh, subdomain_data=md.facet_tags)
    bavg_forms: dict[str, tuple[Any, float]] = {}
    for pn in comp.definitions.active_children("def.probe_boundary_avg"):
        mks = [e for e in (md.boundaries if pn.selection.entities == "all" else pn.selection.entities)]
        expr = to_ufl(pn.props["expr"], sym)
        f_num = fem.form(_sum_forms([expr * ds(m) for m in mks]))
        one = fem.Constant(msh, PETSc.ScalarType(1.0))
        length = comm.allreduce(fem.assemble_scalar(fem.form(_sum_forms([one * ds(m) for m in mks]))), op=MPI.SUM)
        bavg_forms[pn.props["name"]] = (f_num, length)

    def assemble_probe(form: Any) -> float:
        return float(comm.allreduce(fem.assemble_scalar(form), op=MPI.SUM))

    # ---------------------------------------------------------------- equação global
    gvars: list[tuple[str, str, float]] = []
    if glob is not None:
        for ge in glob.active_children("global.equations"):
            for row in ge.props.get("equations", []):
                gvars.append((row[0], row[1], _num(to_ufl(row[2] or "0", si))))
    if len(gvars) > 1:
        raise NotImplementedError("só uma incógnita global ativa é suportada nesta versão")
    gname, gexpr, g0 = gvars[0] if gvars else ("", "", 0.0)
    gvalue = g0
    gprobes = sorted(free_symbols(gexpr) & set(probe_forms)) if gname else []

    def g_eval(Vv: float, probes: dict[str, float]) -> float:
        env = {**si, **probes, gname: Vv, "t": float(tconst.value)}
        return _num(to_ufl(gexpr, env, funcs))

    # ---------------------------------------------------------------- condições de Dirichlet
    fdim = msh.topology.dim - 1
    bc_specs: list[tuple[int, Any, str]] = []  # (subespaço, facetas, expressão do valor)
    bnd_cd = resolve(cd_nodes, md.boundaries, ("current.insulation", "current.potential"))
    for mk, n in bnd_cd.items():
        if n.kind == "current.potential":
            bc_specs.append((1, md.facet_tags.find(mk), n.props["phis"]))
    bnd_t = resolve(
        tnodes, md.boundaries, ("transport.noflux", "transport.inflow", "transport.outflow", "transport.concentration")
    )
    for mk, n in bnd_t.items():
        if n.kind == "transport.inflow":
            for i in range(ns):
                bc_specs.append((2 + i, md.facet_tags.find(mk), n.props["c0"][i]))
        elif n.kind == "transport.concentration":
            for i in range(ns):
                if i < len(n.props["apply"]) and n.props["apply"][i]:
                    bc_specs.append((2 + i, md.facet_tags.find(mk), n.props["c"][i]))

    bcs, bcs_sens, bc_info = [], [], []
    bc_subs = [sub for sub, _f, _e in bc_specs]
    for sub, facets, expr in bc_specs:
        dofs = fem.locate_dofs_topological(W.sub(sub), fdim, facets)
        val = fem.Constant(msh, PETSc.ScalarType(0.0))
        sens = fem.Constant(msh, PETSc.ScalarType(0.0))
        bcs.append(fem.dirichletbc(val, dofs, W.sub(sub)))
        bcs_sens.append(fem.dirichletbc(sens, dofs, W.sub(sub)))
        bc_info.append((expr, val, sens, gname in free_symbols(expr) if gname else False))
    # φ_s fora dos eletrodos: graus de liberdade inativos fixados em 0
    tdim = msh.topology.dim
    el_cells = (
        np.concatenate([md.cell_tags.find(d) for d in electrode_doms]) if electrode_doms else np.array([], np.int32)
    )
    all_cells = np.arange(
        msh.topology.index_map(tdim).size_local + msh.topology.index_map(tdim).num_ghosts, dtype=np.int32
    )
    dofs_all = fem.locate_dofs_topological(W.sub(1), tdim, all_cells)
    dofs_el = fem.locate_dofs_topological(W.sub(1), tdim, el_cells.astype(np.int32))
    inactive = np.setdiff1d(dofs_all, dofs_el).astype(np.int32)
    zero_c = fem.Constant(msh, PETSc.ScalarType(0.0))
    bcs.append(fem.dirichletbc(zero_c, inactive, W.sub(1)))
    bcs_sens.append(fem.dirichletbc(zero_c, inactive, W.sub(1)))

    def update_bc_values(Vv: float) -> None:
        env = {**si, "t": float(tconst.value)}
        if gname:
            env[gname] = Vv
        for (expr, val, sens, dep), sub in zip(bc_info, bc_subs, strict=True):
            v0 = _num(to_ufl(expr, env, funcs))
            if log_c and sub >= 2:
                v0 = math.log(max(v0, c_eps))
            val.value = v0
            if dep:
                eps_fd = 1e-6 * max(1.0, abs(Vv))
                env2 = dict(env)
                env2[gname] = Vv + eps_fd
                sens.value = (_num(to_ufl(expr, env2, funcs)) - v0) / eps_fd
            else:
                sens.value = 0.0

    # ---------------------------------------------------------------- condições iniciais
    init_t = resolve(tnodes, md.domains, ("transport.init",))
    init_c = resolve(cd_nodes, md.domains, ("current.init",))
    for i in range(2 + ns):
        Vi, mp = W.sub(i).collapse()
        f = fem.Function(Vi)
        for d in md.domains:
            if i < 2:
                n = init_c.get(d)
                expr = (n.props["phil"] if i == 0 else n.props["phis"]) if n else "0"
            else:
                n = init_t.get(d)
                expr = n.props["c"][i - 2] if n else "0"
            val = _num(to_ufl(expr, si))
            if log_c and i >= 2:
                val = math.log(max(val, c_eps))
            cells = md.cell_tags.find(d)
            dofs = fem.locate_dofs_topological(Vi, tdim, cells)
            f.x.array[dofs] = val
        w.x.array[mp] = f.x.array
    w.x.scatter_forward()
    w_n.x.array[:] = w.x.array
    w_nm1.x.array[:] = w.x.array

    # ---------------------------------------------------------------- álgebra linear
    A = fpetsc.create_matrix(J_form)
    opts = PETSc.Options()
    prefix = "kfem_tr_"
    for k, v in (
        petsc_options
        or {"ksp_type": "preonly", "pc_type": "lu", "pc_factor_mat_solver_type": "mumps", "mat_mumps_icntl_14": 200}
    ).items():
        opts[f"{prefix}{k}"] = v

    def make_linear() -> tuple[Any, Any, Any, Any, Any]:
        """Vetores e KSP novos. Depois de um erro do PETSc no meio de uma operação, um vetor
        pode ficar bloqueado e a fatoração inválida; recriar tudo deixa o passo seguinte limpo."""
        b_ = fpetsc.create_vector(W)
        k_ = PETSc.KSP().create(comm)
        k_.setOperators(A)
        k_.setOptionsPrefix(prefix)
        k_.setFromOptions()
        return b_, b_.duplicate(), b_.duplicate(), b_.duplicate(), k_

    b, b2, x1, x2, ksp = make_linear()
    gb = gpu_backend()
    calib = 0 if os.environ.get("KFEM_GPU_FORCE") == "1" else 6  # 1 = sempre GPU (validação)
    # solve na GPU: só em serial por padrão. Em paralelo o solver híbrido trava na RX 580 (a
    # investigar) e, nas medidas, o MUMPS da CPU já é mais rápido; KFEM_GPU_SOLVE=1 força.
    use_gpu_solve = bool(gb) and (comm.size == 1 or os.environ.get("KFEM_GPU_SOLVE") == "1")
    if gb and not use_gpu_solve:
        log(f"solve linear na CPU (MUMPS): com {comm.size} processos o solve na GPU fica desligado")
    lin: Any = HybridLinearSolver(comm, ksp, gb, log=log, calibrate=calib) if use_gpu_solve else None
    # montagem de J/F na GPU (HIP). Independe da variante do PETSc: só precisa do runtime HIP
    # e de uma GPU; a conferência da 1ª iteração decide se fica. KFEM_GPU_ASM=0 desliga.
    gasm: Any = None
    gasm_state = {"checked": False}
    want_gasm = os.environ.get("KFEM_GPU_ASM", "auto")
    if want_gasm in ("1", "auto"):
        try:
            from kfem.solvers.gpu_assembly import GpuAssembler

            t0g = _time.perf_counter()
            gasm = GpuAssembler(comm, J, Fres, J_form, F_form, bcs)
            log(f"montagem na GPU preparada em {gasm.device} ({_time.perf_counter() - t0g:.1f} s)")
        except Exception as exc:  # sem GPU/biblioteca ou forma não suportada: fica na CPU
            log(f"montagem na GPU indisponível ({str(exc).splitlines()[0][:200]}); seguindo na CPU")
            gasm = None

    scale = np.array(
        [1.0, 1.0]
        + [
            max(1e-12, abs(_num(to_ufl(init_t[md.domains[0]].props["c"][i], si)))) if md.domains[0] in init_t else 1.0
            for i in range(ns)
        ]
    )
    vscale = 1.0
    for expr, _v, _s, dep in bc_info:
        if dep:
            vscale = max(vscale, abs(_num(to_ufl(expr, {**si, gname: max(1.0, abs(si.get("V_ext0", 1.0)))}, funcs))))
    scale[0] = scale[1] = vscale
    # escala do erro de truncamento no tempo: sempre em concentração (c0), mesmo na forma ln c
    est_scale = scale.copy()
    if log_c:
        scale[2:] = 1.0  # Newton: incremento em ln c já é relativo

    prof: dict[str, float] = dict.fromkeys(
        ("montagem_J", "montagem_F", "contorno", "solve", "sensib_sondas", "atualiza"), 0.0
    )
    pc = _time.perf_counter

    asm_env = os.environ.get("KFEM_ASM_PROFILE")
    asm_prof_at = float(asm_env) if asm_env else None
    asm_profiled: list[float] = []
    dump_env = os.environ.get("KFEM_DUMP_SYSTEM")
    dump_at = float(dump_env) if dump_env else None
    dumped: list[float] = []

    def gpu_assemble(ga: Any, A_: Any, b_: Any) -> Any:
        """J em A_, F + lifting em b_ (local, antes do ghostUpdate); devolve Σ A·g_sens."""
        g = np.zeros(ga.n_local)
        for bc in bcs:
            bc.set(g, x0=w.x.array, alpha=1.0)  # g − w nas linhas de Dirichlet
        lifts = [g]
        if gname:
            gs = np.zeros(ga.n_local)
            for bc in bcs_sens:
                bc.set(gs)
            lifts.append(gs)
        outs = ga.assemble_matrix(A_, lifts)
        with b_.localForm() as bl:
            arr = bl.array_w
            arr[:] = 0.0
            ga.assemble_vector(arr)
            arr += outs[0]  # lifting com alpha = −1: b += A (g − w)
        return outs[1] if gname else None

    def gpu_check(ga: Any, A_: Any, b_: Any, t_gpu: float) -> bool:
        """1ª iteração: confere a montagem da GPU contra a da DOLFINx e compara os tempos."""
        Ac = A_.duplicate()
        bc_ = b_.duplicate()
        t0c = _time.perf_counter()
        Ac.zeroEntries()
        fpetsc.assemble_matrix(Ac, J_form, bcs=bcs)
        Ac.assemble()
        with bc_.localForm() as bl:
            bl.set(0.0)
        fpetsc.assemble_vector(bc_, F_form)
        fpetsc.apply_lifting(bc_, [J_form], bcs=[bcs], x0=[w.x.petsc_vec], alpha=-1.0)
        t_cpu = _time.perf_counter() - t0c
        # compara o que o solver vê: depois do ghostUpdate e do set_bc (nas linhas de Dirichlet a
        # DOLFINx deixa valores do lifting que o set_bc sobrescreve; a GPU nem os calcula)
        # VecCopy de um vetor com fantasmas copia só a parte própria; aqui é preciso a forma local
        # inteira (as parcelas fantasmas vão para os donos no ghostUpdate)
        bg_ = b_.duplicate()
        with b_.localForm() as src_, bg_.localForm() as dst_:
            dst_.array_w[:] = src_.array_r
        for v_ in (bc_, bg_):
            v_.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
            fpetsc.set_bc(v_, bcs, w.x.petsc_vec, -1.0)
        Ac.axpy(-1.0, A_)
        ea = Ac.norm() / max(A_.norm(), 1e-300)
        bc_.axpy(-1.0, bg_)
        eb = bc_.norm() / max(bg_.norm(), 1e-300)
        t_gpu = comm.allreduce(t_gpu, op=MPI.MAX)
        t_cpu = comm.allreduce(t_cpu, op=MPI.MAX)
        if os.environ.get("KFEM_GPU_ASM_DEBUG") == "1":
            # lifting por três caminhos, local (sem comunicação)
            g = np.zeros(ga.n_local)
            for bc in bcs:
                bc.set(g, x0=w.x.array, alpha=1.0)
            (l_gpu,) = ga.assemble_matrix(Ac, [g])
            lc = b_.duplicate()
            with lc.localForm() as bl:
                bl.set(0.0)
            fpetsc.apply_lifting(lc, [J_form], bcs=[bcs], x0=[w.x.petsc_vec], alpha=-1.0)
            with lc.localForm() as bl:
                l_dfx = bl.array_r.copy()
            Afull = fem.assemble_matrix(J_form)  # sem condições: linhas próprias + fantasmas, local
            nr = len(Afull.indptr) - 1
            ind, ip, dat = Afull.indices, Afull.indptr, Afull.data
            gcol = np.zeros(max(int(ind.max()) + 1, ga.n_local))
            gcol[: ga.n_local] = np.where(ga.isbc == 1, g, 0.0)
            l_def = np.zeros(max(nr, ga.n_local))
            rows = np.repeat(np.arange(nr), np.diff(ip))
            np.add.at(l_def, rows, dat * gcol[ind])
            l_def = l_def[: ga.n_local]
            e1 = float(np.abs(l_gpu - l_def).max())
            e2 = float(np.abs(l_dfx - l_def).max())
            k1 = int(np.argmax(np.abs(l_dfx - l_def)))
            log(
                f"  [depuração] processo {comm.rank}: lifting |GPU−def| {e1:.2e}, |DOLFINx−def| {e2:.2e}, "
                f"máx |def| {np.abs(l_def).max():.2e}; pior dof DOLFINx {k1} (próprio: {k1 < ga.n_owned}, "
                f"Dirichlet: {ga.isbc[k1]}), linhas da CSR {nr}, n_local {ga.n_local}"
            )
            lc.destroy()
            fc = b_.duplicate()
            with fc.localForm() as bl:
                bl.set(0.0)
            fpetsc.assemble_vector(fc, F_form)
            fc.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
            for rep_ in range(2):
                loc_arr = np.zeros(ga.n_local)
                ga.assemble_vector(loc_arr)
                fg = b_.duplicate()
                with fg.localForm() as bl:
                    bl.array_w[:] = loc_arr
                fg.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
                fg.axpy(-1.0, fc)
                bad = int(np.count_nonzero(~np.isfinite(loc_arr)))
                mx = float(np.abs(loc_arr[np.isfinite(loc_arr)]).max()) if loc_arr.size else 0.0
                log(
                    f"  [depuração] só F, repetição {rep_}: dif. relativa {fg.norm() / max(fc.norm(), 1e-300):.1e}; "
                    f"processo {comm.rank}: {bad} não finitos, máx |F_gpu| {mx:.3e}, n_local {ga.n_local}"
                )
                fg.destroy()
            fc.destroy()
        if not (ea < 1e-9 and eb < 1e-9):
            d_ = np.abs(bc_.array)
            k_ = int(np.argmax(d_)) if d_.size else -1
            loc = None
            if k_ >= 0:
                fld = next((i for i, mp in enumerate(sub_maps) if k_ in set(mp.tolist())), -1)
                loc = (comm.rank, k_, fld, int(ga.isbc[k_]), float(d_[k_]), float(bg_.array[k_]))
            locs = [x for x in comm.allgather(loc) if x is not None]
            worst = max(locs, key=lambda x: x[4]) if locs else None
            log(
                f"montagem na GPU difere da CPU (J {ea:.1e}, F {eb:.1e}); seguindo na CPU. "
                f"Maior diferença (processo, dof próprio, campo, Dirichlet, |dif|, valor): {worst}"
            )
            Ac.destroy()
            bc_.destroy()
            bg_.destroy()
            return False
        Ac.destroy()
        bc_.destroy()
        bg_.destroy()
        if t_gpu >= t_cpu and os.environ.get("KFEM_GPU_ASM") != "1":
            log(f"montagem na CPU foi mais rápida ({t_cpu:.3f} s contra {t_gpu:.3f} s); seguindo na CPU")
            return False
        log(f"montagem na GPU conferida (diferença J {ea:.1e}, F {eb:.1e}); {t_gpu:.3f} s contra {t_cpu:.3f} s na CPU")
        return True

    def newton(tn: float) -> int:
        nonlocal gvalue, gasm
        Vv = gvalue
        hist: list[float] = [1.0]
        for it in range(1, 26):
            t_ = pc()
            update_bc_values(Vv)
            sens_lift: Any = None
            if gasm is not None:
                sens_lift = gpu_assemble(gasm, A, b)
                t1_ = t2_ = pc()
                prof["montagem_J"] += t1_ - t_
                if not gasm_state["checked"]:
                    gasm_state["checked"] = True
                    if not gpu_check(gasm, A, b, pc() - t_):
                        gasm = None
                        sens_lift = None
                        t_ = pc()
            if gasm is None:
                A.zeroEntries()
                fpetsc.assemble_matrix(A, J_form, bcs=bcs)
                A.assemble()
                t1_ = pc()
                prof["montagem_J"] += t1_ - t_
                with b.localForm() as bl:
                    bl.set(0.0)
                fpetsc.assemble_vector(b, F_form)
                t2_ = pc()
                prof["montagem_F"] += t2_ - t1_
                fpetsc.apply_lifting(b, [J_form], bcs=[bcs], x0=[w.x.petsc_vec], alpha=-1.0)
            b.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
            fpetsc.set_bc(b, bcs, w.x.petsc_vec, -1.0)
            if not np.isfinite(b.norm()):
                raise RuntimeError("resíduo não finito")
            t3_ = pc()
            prof["contorno"] += t3_ - t2_
            if asm_prof_at is not None and tn >= asm_prof_at and not asm_profiled:
                asm_profiled.append(tn)
                _profile_assembly(comm, J, Fres, J_form, F_form, A, bcs, log)
            if dump_at is not None and tn >= dump_at and not dumped:
                # sistema real do Newton para testar solvers fora do laço (KFEM_DUMP_SYSTEM=<t em s>)
                vw = PETSc.Viewer().createBinary(f"cdi_system_t{tn:.0f}.petsc", "w", comm=comm)
                A.view(vw)
                b.view(vw)
                vw.destroy()
                dumped.append(tn)
                log(f"sistema linear salvo em cdi_system_t{tn:.0f}.petsc ({A.getSize()[0]} incógnitas)")
            if lin is not None:
                lin.set_operator(A)
                lin.solve(b, x1)  # x1 = w − w_novo (convenção da DOLFINx: w ← w − x1)
            else:
                ksp.setOperators(A)
                ksp.solve(b, x1)
                if ksp.getConvergedReason() < 0:
                    raise RuntimeError(f"solver linear falhou (motivo {ksp.getConvergedReason()})")
            x1.scale(-1.0)
            t4_ = pc()
            prof["solve"] += t4_ - t3_
            dV = 0.0
            if gname:
                with b2.localForm() as bl:
                    bl.set(0.0)
                    if sens_lift is not None:  # já calculado na GPU com a mesma matriz do elemento
                        bl.array_w[:] = -sens_lift
                if sens_lift is None:
                    fpetsc.apply_lifting(b2, [J_form], bcs=[bcs_sens])
                b2.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
                fpetsc.set_bc(b2, bcs_sens)
                if lin is not None:
                    lin.solve(b2, x2)
                else:
                    ksp.solve(b2, x2)
                t5_ = pc()
                prof["solve"] += t5_ - t4_
                t4_ = t5_
                probes = {p: assemble_probe(probe_forms[p]) for p in gprobes}
                gval = g_eval(Vv, probes)
                epsV = 1e-6 * max(1.0, abs(Vv))
                gV = (g_eval(Vv + epsV, probes) - gval) / epsV
                dI1 = dI2 = 0.0
                for p in gprobes:
                    eps_p = 1e-6 * max(1.0, abs(probes[p]))
                    gp = (g_eval(Vv, {**probes, p: probes[p] + eps_p}) - gval) / eps_p
                    xprobe.x.petsc_vec.array_w[:] = x1.array_r
                    xprobe.x.scatter_forward()
                    d1 = assemble_probe(probe_dforms[p])
                    xprobe.x.petsc_vec.array_w[:] = x2.array_r
                    xprobe.x.scatter_forward()
                    d2 = assemble_probe(probe_dforms[p])
                    dI1 += gp * d1
                    dI2 += gp * d2
                dV = -(gval + dI1) / (gV + dI2)
                x1.axpy(dV, x2)
                Vv += dV
            t6_ = pc()
            prof["sensib_sondas"] += t6_ - t4_
            w_old = w.x.array.copy()
            w.x.petsc_vec.axpy(1.0, x1)
            w.x.scatter_forward()
            if log_c:
                # ln c limitado a uma faixa física: abaixo de ~1e-14 mol/m³ a espécie está esgotada
                # e valores menores só levam o Newton a e^u fora do ponto flutuante
                for i in range(ns):
                    m_ = sub_maps[2 + i]
                    w.x.array[m_] = np.clip(w.x.array[m_], LN_C_MIN, LN_C_MAX)
            # critério de convergência por componente (escalado)
            arr = (w.x.array - w_old)[: len(x1.array_r)]  # incremento efetivo (após o limite em ln c)
            err = 0.0
            for i, mp in enumerate(sub_maps):
                loc = mp[mp < len(arr)]
                e = float(np.dot(arr[loc], arr[loc]))
                n_ = comm.allreduce(len(loc), op=MPI.SUM)
                err = max(err, math.sqrt(comm.allreduce(e, op=MPI.SUM) / max(n_, 1)) / scale[i])
            hist.append(err)
            prof["atualiza"] += pc() - t6_
            # convergência: incremento RMS escalado (em ln c ele já é relativo); aceita estagnação no
            # nível de arredondamento (exp/condicionamento), comum quando c → 0
            stagnated = it >= 4 and err < 1e-4 and err > 0.5 * hist[-2]
            if (err < 1e-6 and abs(dV) < 1e-7 * max(1.0, abs(Vv))) or stagnated:
                gvalue = Vv
                return it
        raise RuntimeError(f"Newton não convergiu em t={tn:.6g} s (erro {err:.2e})")

    # ---------------------------------------------------------------- laço no tempo
    tlist = parse_tlist(str(step.props.get("tlist", "range(0,1,10)")), si)
    rtol = _num(to_ufl(str(step.props.get("rtol", "1e-3")), si))
    tend = tlist[-1]
    res = TransientResult(
        globals={
            "t": [],
            **({gname: []} if gname else {}),
            **{p: [] for p in probe_forms},
            **{p: [] for p in bavg_forms},
        }
    )
    t0w = _time.time()

    def probe_values() -> dict[str, float]:
        vals = {p: assemble_probe(f) for p, f in probe_forms.items()}
        for p, (f, length) in bavg_forms.items():
            vals[p] = assemble_probe(f) / max(length, 1e-300)
        if gname:
            vals[gname] = gvalue
        return vals

    def record(tn: float, vals: dict[str, float] | None = None) -> None:
        if vals is None:
            vals = probe_values()
        res.times.append(tn)
        res.globals["t"].append(tn)
        for k, v in vals.items():
            res.globals.setdefault(k, []).append(v)
        if on_output:
            outs = {}
            for i, nm in enumerate(names):
                f = w.sub(i).collapse()
                if log_c and i >= 2:
                    f.x.array[:] = np.exp(f.x.array)
                f.name = nm
                outs[nm] = f
            on_output(tn, outs, vals)
        for i, nm in enumerate(species):
            loc = w.x.array[sub_maps[2 + i]]
            loc = np.exp(loc) if log_c else loc
            vals[f"min_{nm}"] = float(comm.allreduce(float(loc.min()) if loc.size else 1e300, op=MPI.MIN))
        if comm.rank == 0:
            msg = ", ".join(f"{k}={v:.5g}" for k, v in vals.items())
            log(f"t = {tn:.6g} s: {msg}")

    t = tlist[0]
    tconst.value = t
    if gname:
        # valor inicial consistente de V: resolve g(V, I(w0)) = 0 com w0 (I = 0 se w estacionário)
        pass
    out_idx = 1
    record(t)
    # 1º passo: Euler implícito (L-estável) atravessa a descontinuidade de V em t=0 (DAE)
    hdt = min(1e-3, (tlist[1] - tlist[0]) / 10 if len(tlist) > 1 else 1e-3)
    dt_prev = None
    while t < tend - 1e-12 * max(1.0, tend) and out_idx < len(tlist):
        if should_stop():
            raise Cancelled()
        target = tlist[out_idx]
        hdt = min(hdt, target - t)
        if dt_prev is None:  # BDF1
            a0.value, a1.value, a2.value = 1.0 / hdt, -1.0 / hdt, 0.0
        else:  # BDF2 de passo variável
            om = hdt / dt_prev
            a0.value = (1 + 2 * om) / (1 + om) / hdt
            a1.value = -(1 + om) / hdt
            a2.value = om * om / (1 + om) / hdt
        dt.value = hdt
        tconst.value = t + hdt
        g_save = gvalue
        w_save = w.x.array.copy()
        # preditor (extrapolação linear) como chute inicial e estimador de erro
        if dt_prev is not None:
            om = hdt / dt_prev
            pred = w_n.x.array + om * (w_n.x.array - w_nm1.x.array)
        else:
            pred = w_n.x.array.copy()
        w.x.array[:] = pred
        try:
            its = newton(t + hdt)
        except (RuntimeError, PETSc.Error) as exc:
            res.rejected += 1
            if isinstance(exc, PETSc.Error) or "solver linear" in str(exc):
                for v_ in (b, b2, x1, x2, ksp):
                    v_.destroy()
                b, b2, x1, x2, ksp = make_linear()
                if lin is not None:
                    lin.set_cpu_ksp(ksp)
            w.x.array[:] = w_save
            gvalue = g_save
            hdt *= 0.25
            log(f"passo rejeitado ({str(exc).splitlines()[0][:200]}); dt → {hdt:.3g} s")
            if hdt < 1e-12:
                raise
            continue
        res.newton_its += its
        # estimativa de erro local (escalada por componente)
        # Na forma ln c o erro é medido em c (= e^u): onde a espécie está esgotada (c ~ 0)
        # ln c oscila muito sem importância física, e medir em ln c faria dt despencar.
        diff = w.x.array - pred
        est = 0.0
        for i, mp in enumerate(sub_maps):
            loc = mp
            d_i = np.exp(w.x.array[loc]) - np.exp(pred[loc]) if (log_c and i >= 2) else diff[loc]
            e = comm.allreduce(float(np.dot(d_i, d_i)), op=MPI.SUM)
            n_ = comm.allreduce(len(loc), op=MPI.SUM)
            est = max(est, math.sqrt(e / max(n_, 1)) / est_scale[i])
        est = est / 3.0 if dt_prev is not None else est / 2.0
        if est > 5 * rtol and hdt > 1e-9 and res.steps >= 2:
            res.rejected += 1
            w.x.array[:] = w_save
            gvalue = g_save
            hdt *= max(0.2, 0.8 * math.sqrt(rtol / est))
            continue
        # aceito: sondas com os coeficientes BDF deste passo, antes de deslocar o histórico
        step_vals = probe_values()
        w_nm1.x.array[:] = w_n.x.array
        w_n.x.array[:] = w.x.array
        dt_prev = hdt
        t += hdt
        res.steps += 1
        fac = 0.9 * math.sqrt(rtol / max(est, 1e-14))
        hdt = hdt * min(2.0, max(0.3, fac))
        if abs(t - target) <= 1e-9 * max(1.0, target):
            t = target
            record(t, step_vals)
            out_idx += 1
        if progress:
            progress(t / tend, f"t = {t:.4g} s de {tend:.4g} s (dt = {dt_prev:.3g} s)")
    res.wall = _time.time() - t0w
    if lin is not None:
        log(lin.report())
    if gasm is not None:
        log("montagem na GPU (s): " + ", ".join(f"{k} {v:.1f}" for k, v in gasm.timing.items()))
    res.profile = {k: comm.allreduce(v, op=MPI.MAX) for k, v in prof.items()}
    tot = sum(res.profile.values()) or 1.0
    log(
        "perfil do Newton (s, máx. entre processos): "
        + ", ".join(f"{k} {v:.1f} ({100 * v / tot:.0f}%)" for k, v in res.profile.items())
    )
    log(
        f"transiente concluído: {res.steps} passos aceitos, {res.rejected} rejeitados, "
        f"{res.newton_its} iterações de Newton, {res.wall:.1f} s"
    )
    return res
