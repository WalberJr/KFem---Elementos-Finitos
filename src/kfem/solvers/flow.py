"""Escoamento Stokes–Brinkman estacionário (docs/physics §1)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from kfem.model.tree import Node
from kfem.solvers.setup import Materials, MeshData, boundary_normal, resolve


def solve_brinkman(
    phys: Node,
    md: MeshData,
    mats: Materials,
    si: dict[str, float],
    log: Callable[[str], None] = print,
    petsc_options: dict[str, Any] | None = None,
) -> Any:
    import basix.ufl
    import ufl
    from dolfinx import fem
    from dolfinx.fem.petsc import LinearProblem

    msh = md.mesh
    gdim = msh.geometry.dim
    order_u = 3 if phys.props.get("order") == "P3/P2" else 2
    Ve = basix.ufl.element("Lagrange", msh.basix_cell(), order_u, shape=(gdim,))
    Qe = basix.ufl.element("Lagrange", msh.basix_cell(), order_u - 1)
    W = fem.functionspace(msh, basix.ufl.mixed_element([Ve, Qe]))
    (u, p), (v, q) = ufl.TrialFunctions(W), ufl.TestFunctions(W)

    nodes = phys.children
    dom_nodes = resolve(nodes, md.domains, ("brinkman.porous", "brinkman.fluid"))
    props_nodes = resolve(nodes, md.domains, ("brinkman.properties",))
    eps_d: dict[int, Any] = {}
    kinv_d: dict[int, Any] = {}
    mu_d: dict[int, Any] = {}
    for d in md.domains:
        n = dom_nodes.get(d)
        pn = props_nodes.get(d)
        visc = pn.props["viscosity"] if pn else "mat:viscosity"
        fm = (pn.props.get("fluid_material") or "") if pn else ""
        if fm and isinstance(visc, str) and visc.startswith("mat:"):
            mu_d[d] = mats.material_value(fm, visc[4:], si)
        else:
            mu_d[d] = mats.resolve_prop(visc, d, si)
        if n is not None and n.kind == "brinkman.porous":
            eps_d[d] = mats.resolve_prop(n.props["porosity"], d, si)
            kinv_d[d] = 1.0 / mats.resolve_prop(n.props["permeability"], d, si)
        else:
            eps_d[d], kinv_d[d] = 1.0, 0.0
    mu, eps, kinv = mats.piecewise(mu_d), mats.piecewise(eps_d), mats.piecewise(kinv_d)
    log(
        "escoamento: μ/ε/κ por domínio: "
        + ", ".join(f"{d}: ε={eps_d[d] if isinstance(eps_d[d], float) else '…'}" for d in md.domains)
    )

    def eps_(w: Any) -> Any:
        return ufl.grad(w) + ufl.grad(w).T

    a = (
        ufl.inner((mu / eps) * eps_(u), ufl.grad(v)) * ufl.dx
        + mu * kinv * ufl.inner(u, v) * ufl.dx
        - p * ufl.div(v) * ufl.dx
        - q * ufl.div(u) * ufl.dx
    )
    zero = fem.Constant(msh, np.zeros(gdim))
    L = ufl.inner(zero, v) * ufl.dx

    fdim = msh.topology.dim - 1
    V0, _ = W.sub(0).collapse()
    bnd = resolve(nodes, md.exterior, ("brinkman.wall", "brinkman.inlet", "brinkman.outlet"))
    bcs = []
    for mk, n in bnd.items():
        facets = md.facet_tags.find(mk)
        dofs = fem.locate_dofs_topological((W.sub(0), V0), fdim, facets)
        g = fem.Function(V0)
        if n.kind == "brinkman.wall":
            g.x.array[:] = 0.0
        elif n.kind == "brinkman.inlet":
            U0 = float(mats.resolve_prop(n.props["U0"], md.domains[0], si))
            nrm = boundary_normal(md, mk)[:gdim]
            val = -U0 * nrm
            g.interpolate(lambda x, val=val: np.tile(val.reshape(-1, 1), (1, x.shape[1])))
            log(f"escoamento: entrada no contorno {mk}, U0={U0:.4g} m/s, normal={np.round(nrm, 3)}")
        else:
            continue  # saída: tensão normal nula (natural)
        bcs.append(fem.dirichletbc(g, dofs, W.sub(0)))

    opts = petsc_options or {"ksp_type": "preonly", "pc_type": "lu", "pc_factor_mat_solver_type": "mumps"}
    problem = LinearProblem(a, L, bcs=bcs, petsc_options=opts, petsc_options_prefix="kfem_flow_")
    wh = problem.solve()
    if isinstance(wh, tuple):
        wh = wh[0]
    uh = wh.sub(0).collapse()
    ph = wh.sub(1).collapse()
    uh.name, ph.name = "u", "p"
    umax = msh.comm.allreduce(
        float(np.max(np.abs(uh.x.array))) if uh.x.array.size else 0.0, op=__import__("mpi4py").MPI.MAX
    )
    log(f"escoamento resolvido: |u|max ≈ {umax:.4g} m/s")
    return uh, ph
