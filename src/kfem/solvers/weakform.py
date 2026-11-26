"""Motor genérico de formas fracas (ADR 0014, fase M0/M1).

Resolve um conjunto de campos escalares (Lagrange P1/P2) definido por resíduos em forma fraca
escritos como texto, com o analisador seguro de `kfem.model.expressions` (sem `eval`).
Funções disponíveis nas expressões:

- campos pelo nome (`u`, `T`…) e `test(u)` (função-teste do campo `u`);
- `dt(u)`: derivada no tempo (BDF1 no 1º passo, BDF2 de passo fixo depois);
- `grad`, `div`, `inner`, `dot`, `curl` (2D: escalar), `vec(a, b[, c])`, `x`, `y`, `z`, `t`;
- medidas: `dx` (domínios da física), `dx(k)` (domínio k), `ds` (contorno externo), `ds(k)`;
- as funções matemáticas de sempre (`exp`, `log`, `sqrt`, `sin`…), parâmetros e unidades.

O resíduo total é a soma das equações e dos termos de contorno; o problema é
`resíduo = 0` para toda função-teste. Newton (SNES do PETSc) com MUMPS.

Duas camadas: `WeakProblem` não conhece o modelo (testável com soluções manufaturadas) e
`solve_model` traduz os nós da árvore (`physics.weakform` e filhos).
"""

from __future__ import annotations

import time as _time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from kfem.model.expressions import ExpressionError


@dataclass
class BCSpec:
    field: str
    value: str  # expressão (pode depender de x, y, t e parâmetros)
    markers: list[int]  # marcadores de contorno


@dataclass
class WeakResult:
    times: list[float] = field(default_factory=list)
    steps: int = 0
    newton_its: int = 0
    rejected: int = 0
    wall: float = 0.0


def _setter(fun: Any, val: Any, comm: Any) -> Callable[[], None]:
    """Função que (re)preenche `fun` com `val`: número → valor direto; expressão UFL →
    interpolação. Expressões sem malha (só números e constantes puras) viram número."""
    import ufl
    from dolfinx import fem

    if isinstance(val, (int, float)):
        c = float(val)
        return lambda: fun.x.array.__setitem__(slice(None), c)
    val = ufl.as_ufl(val)
    if ufl.domain.extract_unique_domain(val) is None:
        c = float(val)
        return lambda: fun.x.array.__setitem__(slice(None), c)
    expr = fem.Expression(val, fun.function_space.element.interpolation_points, comm=comm)
    return lambda: fun.interpolate(expr)


class WeakProblem:
    """Campos escalares + resíduos em texto → problema não linear da DOLFINx."""

    def __init__(
        self,
        mesh: Any,
        cell_tags: Any,
        facet_tags: Any,
        fields: list[str],
        residuals: list[str],
        bcs: list[BCSpec] | None = None,
        initial: Mapping[str, str] | None = None,
        order: int = 1,
        symbols: Mapping[str, Any] | None = None,
        functions: Mapping[str, Callable[..., Any]] | None = None,
        domains: list[int] | None = None,
        transient: bool = False,
        newton_tol: float = 1e-10,
    ) -> None:
        import basix.ufl
        import ufl
        from dolfinx import fem
        from petsc4py import PETSc

        self.mesh, self.ct, self.ft = mesh, cell_tags, facet_tags
        self.newton_tol = float(newton_tol)
        self.fields = list(fields)
        if not self.fields:
            raise ExpressionError("nenhuma variável dependente")
        for f in self.fields:
            if not f.isidentifier():
                raise ExpressionError(f"nome de variável inválido: {f!r}")
        el = basix.ufl.element("Lagrange", mesh.basix_cell(), order)
        self.W = fem.functionspace(
            mesh, basix.ufl.mixed_element([el] * len(self.fields)) if len(self.fields) > 1 else el
        )
        self.w = fem.Function(self.W)
        self.w_n = fem.Function(self.W)
        self.w_nm1 = fem.Function(self.W)
        nf = len(self.fields)
        us = ufl.split(self.w) if nf > 1 else [self.w]
        un = ufl.split(self.w_n) if nf > 1 else [self.w_n]
        unm1 = ufl.split(self.w_nm1) if nf > 1 else [self.w_nm1]
        vs = ufl.TestFunctions(self.W) if nf > 1 else [ufl.TestFunction(self.W)]
        self.u_of = dict(zip(self.fields, us, strict=True))
        test_of = {id(u): v for u, v in zip(us, vs, strict=True)}
        prev = {id(u): (a, b) for u, a, b in zip(us, un, unm1, strict=True)}

        self.tconst = fem.Constant(mesh, PETSc.ScalarType(0.0))
        self.a0 = fem.Constant(mesh, PETSc.ScalarType(0.0))
        self.a1 = fem.Constant(mesh, PETSc.ScalarType(0.0))
        self.a2 = fem.Constant(mesh, PETSc.ScalarType(0.0))
        self.transient = transient
        X = ufl.SpatialCoordinate(mesh)
        gdim = mesh.geometry.dim
        dx_all = ufl.Measure("dx", domain=mesh, subdomain_data=cell_tags)
        ds_all = ufl.Measure("ds", domain=mesh, subdomain_data=facet_tags)
        self.domains = domains
        dx_phys = sum((dx_all(int(d)) for d in domains[1:]), dx_all(int(domains[0]))) if domains else dx_all

        def _field_arg(u: Any, fname: str) -> Any:
            if id(u) not in test_of:
                raise ExpressionError(f"{fname}() precisa de uma variável dependente")
            return u

        def test(u: Any) -> Any:
            return test_of[id(_field_arg(u, "test"))]

        def dt(u: Any) -> Any:
            """Derivada no tempo (BDF) de um campo ou de uma expressão dos campos, ex.: dt(exp(u))."""
            if not transient:
                return 0.0 * u  # estacionário: derivada nula
            if id(u) in prev:
                a, b = prev[id(u)]
                return self.a0 * u + self.a1 * a + self.a2 * b
            e = ufl.as_ufl(u)
            e_n = ufl.replace(e, {self.w: self.w_n})
            e_nm1 = ufl.replace(e, {self.w: self.w_nm1})
            return self.a0 * e + self.a1 * e_n + self.a2 * e_nm1

        def vec(*c: Any) -> Any:
            return ufl.as_vector(list(c))

        def curl(a: Any) -> Any:
            return ufl.curl(a) if gdim == 3 else a[1].dx(0) - a[0].dx(1)

        funcs: dict[str, Callable[..., Any]] = {
            "test": test,
            "dt": dt,
            "grad": ufl.grad,
            "div": ufl.div,
            "inner": ufl.inner,
            "dot": ufl.dot,
            "vec": vec,
            "curl": curl,
            "dx": lambda k: dx_all(int(k)),
            "ds": lambda k: ds_all(int(k)),
            **(functions or {}),
        }
        syms: dict[str, Any] = {
            **(symbols or {}),
            **self.u_of,
            "x": X[0],
            "y": X[1] if gdim > 1 else 0.0,
            "z": X[2] if gdim > 2 else 0.0,
            "t": self.tconst,
            "dx": dx_phys,
            "ds": ds_all,
        }
        self.syms, self.funcs = syms, funcs
        from kfem.physics.expr_ufl import to_ufl

        F = None
        for r in residuals:
            term = to_ufl(r, syms, funcs)
            if not isinstance(term, ufl.Form):
                raise ExpressionError(f"o termo '{r}' não é uma integral: multiplique por dx ou ds")
            F = term if F is None else F + term
        if F is None:
            raise ExpressionError("nenhuma equação")
        self.F = F

        # condições de Dirichlet: valor (expressão de x, y, t) interpolado a cada passo
        tdim = mesh.topology.dim
        mesh.topology.create_connectivity(tdim - 1, tdim)
        self._bc_updates: list[Callable[[], None]] = []
        self.bcs = []
        for spec in bcs or []:
            if spec.field not in self.u_of:
                raise ExpressionError(f"condição de contorno para variável desconhecida: {spec.field}")
            i = self.fields.index(spec.field)
            Vi, _ = self.W.sub(i).collapse() if nf > 1 else (self.W, None)
            g = fem.Function(Vi)
            facets = (
                np.concatenate([facet_tags.find(int(m)) for m in spec.markers])
                if spec.markers
                else np.zeros(0, np.int32)
            )
            if nf > 1:
                dofs = fem.locate_dofs_topological((self.W.sub(i), Vi), tdim - 1, facets.astype(np.int32))
                bc = fem.dirichletbc(g, dofs, self.W.sub(i))
            else:
                dofs = fem.locate_dofs_topological(Vi, tdim - 1, facets.astype(np.int32))
                bc = fem.dirichletbc(g, dofs)
            self._bc_updates.append(_setter(g, to_ufl(spec.value, syms, funcs), mesh.comm))
            self.bcs.append(bc)

        # graus de liberdade fora dos domínios da física: fixos em zero
        if domains:
            allc = np.arange(
                mesh.topology.index_map(tdim).size_local + mesh.topology.index_map(tdim).num_ghosts, dtype=np.int32
            )
            inc = np.concatenate([cell_tags.find(int(d)) for d in domains]).astype(np.int32)
            for i in range(nf):
                Vi = self.W.sub(i) if nf > 1 else self.W
                da = fem.locate_dofs_topological(Vi, tdim, allc)
                di = fem.locate_dofs_topological(Vi, tdim, inc)
                inactive = np.setdiff1d(da, di).astype(np.int32)
                zero = fem.Constant(mesh, PETSc.ScalarType(0.0))  # vazio é válido (coletivo em MPI)
                self.bcs.append(fem.dirichletbc(zero, inactive, Vi))

        # valores iniciais (e chute do Newton no estacionário)
        for name, text in (initial or {}).items():
            if name not in self.u_of:
                continue
            i = self.fields.index(name)
            val = to_ufl(text, syms, funcs)
            Vi, mp = self.W.sub(i).collapse() if nf > 1 else (self.W, None)
            fi = fem.Function(Vi)
            _setter(fi, val, mesh.comm)()
            if mp is None:
                self.w.x.array[:] = fi.x.array
            else:
                self.w.x.array[mp] = fi.x.array
        self.w.x.scatter_forward()

        self._make_problem()

    def _make_problem(self) -> None:
        """(Re)cria o problema não linear. Depois de um erro do PETSc no meio do Newton (ex.: exp
        estourando num passo ruim) um vetor interno fica bloqueado: recriar deixa o próximo limpo."""
        from dolfinx.fem import petsc as fpetsc

        self._nprob = getattr(self, "_nprob", 0) + 1
        self.problem = fpetsc.NonlinearProblem(
            self.F,
            self.w,
            bcs=self.bcs,
            petsc_options_prefix=f"kfem_wf_{id(self)}_{self._nprob}_",
            petsc_options={
                "snes_type": "newtonls",
                "snes_linesearch_type": "bt",
                "snes_divergence_tolerance": -1.0,
                "snes_rtol": self.newton_tol,
                "snes_atol": 0.0,  # resíduo absoluto depende da escala do domínio (µm²…): não usar
                "snes_stol": self.newton_tol,
                "snes_max_it": 80,
                "ksp_type": "preonly",
                "pc_type": "lu",
                "pc_factor_mat_solver_type": "mumps",
            },
        )

    # ------------------------------------------------------------------ resolução
    def _newton(self) -> int:
        from petsc4py import PETSc

        for up in self._bc_updates:
            up()
        try:
            self.problem.solve()
        except PETSc.Error as exc:
            self._make_problem()
            raise RuntimeError(f"erro do PETSc no Newton: {str(exc).splitlines()[0]}") from exc
        snes = self.problem.solver
        reason = snes.getConvergedReason()
        if reason <= 0 or not np.all(np.isfinite(self.w.x.array)):
            raise RuntimeError(f"Newton não convergiu (motivo {reason}, {snes.getIterationNumber()} iterações)")
        self.w.x.scatter_forward()
        return int(snes.getIterationNumber())

    def solve_stationary(self) -> int:
        self.a0.value = self.a1.value = self.a2.value = 0.0
        return self._newton()

    def solve_transient(
        self,
        tlist: list[float],
        substeps: int = 10,
        on_output: Callable[[float], None] | None = None,
        progress: Callable[[float, str], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> WeakResult:
        """BDF1 no 1º passo e BDF2 de passo variável depois. Passo nominal = intervalo/`substeps`;
        um passo cujo Newton falha é refeito com 1/4 do tamanho e o passo volta a crescer até o nominal."""
        res = WeakResult()
        t0w = _time.time()
        t = tlist[0]
        self.tconst.value = t
        for up in self._bc_updates:  # condição inicial coerente com os valores impostos
            up()
        self.w_n.x.array[:] = self.w.x.array
        self.w_nm1.x.array[:] = self.w.x.array
        if on_output:
            on_output(t)
        res.times.append(t)
        tend = tlist[-1]
        h_prev: float | None = None  # passo aceito anterior (None: próximo passo é BDF1)
        for k in range(1, len(tlist)):
            t_out = tlist[k]
            h_nom = (t_out - tlist[k - 1]) / substeps
            h = h_nom
            while t < t_out - 1e-12 * max(1.0, abs(t_out)):
                if should_stop and should_stop():
                    from kfem.solvers.electrochem import Cancelled

                    raise Cancelled()
                h = min(h, t_out - t)
                if h_prev is None:  # BDF1
                    self.a0.value, self.a1.value, self.a2.value = 1.0 / h, -1.0 / h, 0.0
                else:  # BDF2 de passo variável
                    om = h / h_prev
                    self.a0.value = (1 + 2 * om) / (1 + om) / h
                    self.a1.value = -(1 + om) / h
                    self.a2.value = om * om / (1 + om) / h
                self.tconst.value = t + h
                w_save = self.w.x.array.copy()
                try:
                    res.newton_its += self._newton()
                except RuntimeError:
                    # passo rejeitado: volta ao estado anterior e tenta com um quarto do passo
                    self.w.x.array[:] = w_save
                    self.w.x.scatter_forward()
                    res.rejected += 1
                    h *= 0.25
                    if h < 1e-14 * max(1.0, abs(t_out)):
                        raise
                    continue
                t += h
                self.w_nm1.x.array[:] = self.w_n.x.array
                self.w_n.x.array[:] = self.w.x.array
                res.steps += 1
                h_prev = h
                h = min(2.0 * h, h_nom)  # recupera o passo nominal depois de uma rejeição
            t = t_out
            if on_output:
                on_output(t)
            res.times.append(t)
            if progress:
                progress(t / tend if tend else 1.0, f"t = {t:.4g} s de {tend:.4g} s")
        res.wall = _time.time() - t0w
        return res

    # ------------------------------------------------------------------ saídas
    def field_functions(self, p1: bool = True) -> dict[str, Any]:
        """Cada campo como função P1 (para XDMF) com o nome do campo."""
        from dolfinx import fem

        out = {}
        nf = len(self.fields)
        for i, name in enumerate(self.fields):
            sub = self.w.sub(i).collapse() if nf > 1 else self.w
            if p1:
                V1 = fem.functionspace(self.mesh, ("Lagrange", 1))
                f = fem.Function(V1, name=name)
                f.interpolate(sub)
            else:
                f = sub
                f.name = name
            out[name] = f
        return out


# --------------------------------------------------------------------------- modelo → motor
GENERIC_KINDS = ("physics.weakform",)


def _markers(node: Any, available: list[int]) -> list[int]:
    from kfem.model.tree import ALL

    if node.selection is None:
        return []
    if node.selection.entities == ALL:
        return list(available)
    return [int(e) for e in node.selection.entities if int(e) in available]


def problem_from_model(model: Any, phys: list[Any], md: Any, si: Mapping[str, Any], transient: bool) -> WeakProblem:
    """Junta as físicas genéricas ativas de um passo num único problema."""
    from kfem.solvers.setup import model_functions

    fields: list[str] = []
    residuals: list[str] = []
    bcs: list[BCSpec] = []
    initial: dict[str, str] = {}
    domains: set[int] = set()
    order = 1
    tol = 1e-10
    for p in phys:
        if not p.active or p.kind != "physics.weakform":
            continue
        names = [f.strip() for f in str(p.props.get("fields", "u")).split(",") if f.strip()]
        for f in names:
            if f in fields:
                raise ExpressionError(f"variável '{f}' definida em mais de uma física")
        fields += names
        order = max(order, 2 if str(p.props.get("order", "P1")).upper() == "P2" else 1)
        tol = max(tol, float(p.props.get("newton_tol", 1e-10) or 1e-10))
        doms = _markers(p, md.domains) or list(md.domains)
        domains.update(doms)
        eq = str(p.props.get("equation", "")).strip()
        if eq:
            residuals.append(eq)
        for ch in p.children:
            if not ch.active:
                continue
            if ch.kind == "weakform.dirichlet":
                bcs.append(
                    BCSpec(
                        str(ch.props.get("field", names[0])),
                        str(ch.props.get("value", "0")),
                        _markers(ch, md.boundaries),
                    )
                )
            elif ch.kind == "weakform.boundary_term":
                ms = _markers(ch, md.boundaries)
                if ms and str(ch.props.get("term", "")).strip():
                    residuals.append(" + ".join(f"({ch.props['term']})*ds({m})" for m in ms))
            elif ch.kind == "weakform.domain_term":
                ms = _markers(ch, md.domains)
                if ms and str(ch.props.get("term", "")).strip():
                    residuals.append(" + ".join(f"({ch.props['term']})*dx({m})" for m in ms))
            elif ch.kind == "weakform.initial":
                initial[str(ch.props.get("field", names[0]))] = str(ch.props.get("value", "0"))
    if not fields:
        raise ExpressionError("nenhuma equação personalizada ativa neste passo")
    all_doms = sorted(domains) == sorted(md.domains)
    return WeakProblem(
        md.mesh,
        md.cell_tags,
        md.facet_tags,
        fields,
        residuals,
        bcs=bcs,
        initial=initial,
        order=order,
        symbols=dict(si),
        functions=model_functions(model, dict(si)),
        domains=None if all_doms else sorted(domains),
        transient=transient,
        newton_tol=tol,
    )


def solve_model(
    model: Any,
    step: Any,
    phys: list[Any],
    md: Any,
    si: Mapping[str, Any],
    on_output: Callable[[float, dict[str, Any]], None],
    log: Callable[[str], None] = print,
    progress: Callable[[float, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> WeakResult:
    from kfem.solvers.setup import parse_tlist

    transient = step.kind == "step.time"
    prob = problem_from_model(model, phys, md, si, transient)
    ndof = prob.W.dofmap.index_map.size_global * prob.W.dofmap.index_map_bs
    log(f"equação personalizada: campos {', '.join(prob.fields)}, {ndof} graus de liberdade")

    def out(t: float) -> None:
        on_output(t, prob.field_functions())
        log(f"t = {t:g} s")  # a interface recarrega os campos a cada linha "t = " (acompanhamento ao vivo)

    if not transient:
        t0 = _time.time()
        its = prob.solve_stationary()
        out(0.0)
        log(f"estacionário resolvido: {its} iterações de Newton")
        return WeakResult(times=[0.0], steps=1, newton_its=its, wall=_time.time() - t0)
    tlist = parse_tlist(str(step.props.get("tlist", "range(0,1,10)")), dict(si))
    res = prob.solve_transient(
        tlist,
        substeps=int(step.props.get("substeps", 10) or 10),
        on_output=out,
        progress=progress,
        should_stop=should_stop,
    )
    log(
        f"transiente concluído: {res.steps} passos, {res.rejected} rejeitados, "
        f"{res.newton_its} iterações de Newton, {res.wall:.1f} s"
    )
    return res
