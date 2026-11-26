"""Leitura direta de `.mph` e conversão para `.kfem` (Etapa 7, ADR 0007, abordagem c).

Serve só à **interoperabilidade** com arquivos do próprio usuário. O `.mph` é um ZIP com
`dmodel.xml`: a árvore do modelo em XML legível. O leitor:
- extrai parâmetros, funções, variáveis, sondas, geometria, materiais, físicas, acoplamentos,
  malha e estudos;
- mapeia tudo para os tipos de nó do KFem (`kfem.model.catalog`);
- lista no relatório o que não foi convertido.

Achados sobre o formato: `docs/mph-format/`.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kfem.io import kfem_format
from kfem.model.catalog import CATALOG
from kfem.model.tree import ALL, Model, Node, Selection

# ------------------------------------------------------------------ valores do XML

_ITEM = re.compile(r"'((?:[^'\\]|\\.)*)'")


def parse_values(raw: str | None) -> list[str]:
    """`"2|1,'c0'|1,'c0'"` → `['c0', 'c0']`; trata vírgulas escapadas (`\\,`)."""
    if not raw:
        return []
    return [m.group(1).replace("\\,", ",").replace("\\\\", "\\") for m in _ITEM.finditer(raw)]


def first(raw: str | None, default: str = "") -> str:
    v = parse_values(raw)
    return v[0] if v else default


def parse_entities(raw: str | None) -> list[int] | str:
    """Seleção codificada (`'4,2,3'`, `'-14,-1,9'`) → entidades, sem o cabeçalho.

    Cabeçalho observado: 1 número (positivo) ou 2 números (o primeiro negativo).
    """
    if raw is None:
        return ALL
    nums = [int(x) for x in raw.split(",") if x.strip()]
    if not nums:
        return []
    body = nums[2:] if nums[0] < 0 else nums[1:]
    return body


def _params(e: ET.Element) -> dict[str, str]:
    return {c.attrib["param"]: c.attrib.get("value", "") for c in e if c.tag == "param" and "param" in c.attrib}


def _disabled(e: ET.Element) -> bool:
    return any(c.tag == "entityFlags" and "DISABLED" in (c.text or "") for c in e)


def _selection(e: ET.Element) -> Selection | None:
    s = e.find("selection")
    if s is None:
        return None
    if s.attrib.get("selType") == "GLOBAL":
        return Selection(-1)
    for sub in s.iter():
        if "dim" in sub.attrib:
            ents = parse_entities(sub.attrib.get("entities"))
            return Selection(int(sub.attrib["dim"]), ents)
    return None


def _prop_values(e: ET.Element) -> dict[str, str]:
    """propertyValue (geometria, funções, malha, estudo): nome sem 'p:' → valor/primeiro item."""
    out: dict[str, str] = {}
    for c in e:
        if c.tag != "propertyValue" or "name" not in c.attrib:
            continue
        name = c.attrib["name"].removeprefix("p:")
        if "valueMatrix" in c.attrib:
            vals = parse_values(c.attrib["valueMatrix"])
            out[name] = "|".join(vals)
        elif "value" in c.attrib:
            out[name] = c.attrib["value"]
    return out


# ------------------------------------------------------------------ relatório


@dataclass
class ConversionReport:
    source: str
    converted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Conversão de {self.source}", f"  convertidos: {len(self.converted)} itens"]
        if self.skipped:
            lines.append(f"  não convertidos ({len(self.skipped)}):")
            lines += [f"    - {s}" for s in self.skipped]
        if self.warnings:
            lines.append("  avisos:")
            lines += [f"    - {w}" for w in self.warnings]
        return "\n".join(lines)


# ------------------------------------------------------------------ conversor


class MphReader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        with zipfile.ZipFile(self.path) as z:
            names = set(z.namelist())
            if "dmodel.xml" not in names:
                raise ValueError("arquivo .mph sem dmodel.xml (versão não suportada)")
            self.root = ET.fromstring(z.read("dmodel.xml"))
            self.file_version = z.read("fileversion").decode(errors="replace") if "fileversion" in names else ""
        self.report = ConversionReport(self.path.name)

    # -------------------------------------------------------------- partes
    def parameters(self, m: Model) -> None:
        mp = self.root.find("ModelParam")
        if mp is None:
            return
        groups: dict[str, str] = {}
        for g in mp.iter("ModelParamGroup"):
            groups[g.attrib["tag"]] = g.attrib.get("name", g.attrib["tag"]).strip()
        m.parameters.groups = [groups.get("default", "Parâmetros")] + [v for k, v in groups.items() if k != "default"]
        for ex in mp.iter("expressions"):
            if "name" not in ex.attrib or "expr" not in ex.attrib:
                continue
            grp = groups.get(ex.attrib.get("groupTag", "default"), m.parameters.groups[0])
            name = ex.attrib["name"]
            if name in m.parameters.params:
                continue
            m.parameters.add(name, ex.attrib["expr"], ex.attrib.get("descr", ""), grp)
        self.report.converted.append(f"{len(m.parameters.params)} parâmetros em {len(m.parameters.groups)} grupos")

    def functions(self, m: Model) -> None:
        fl = self.root.find("FunctionFeatureList")
        for f in [] if fl is None else fl.findall("FunctionFeature"):
            pv = _prop_values(f)
            op = f.attrib.get("op", "")
            tag = pv.get("funcname", f.attrib["tag"])
            if op.lower().startswith("step") or "smooth" in pv:
                m.functions.add(
                    Node(
                        "func.step",
                        tag,
                        f.attrib.get("name", ""),
                        props={
                            "location": pv.get("location", "0"),
                            "from": pv.get("from", "0"),
                            "to": pv.get("to", "1"),
                            "smooth": pv.get("smooth", "0"),
                        },
                        active=not _disabled(f),
                    )
                )
                self.report.converted.append(f"função {tag}")
            else:
                self.report.skipped.append(f"função {tag} (tipo {op or 'desconhecido'})")

    def definitions(self, m: Model) -> None:
        d = m.comp.definitions
        el = self.root.find("ExprList")
        for ex in [] if el is None else el.findall("Expr"):
            vars_ = [[e.attrib["name"], e.attrib["expr"]] for e in ex.iter("expressions") if "name" in e.attrib]
            d.add(
                Node(
                    "def.variables",
                    ex.attrib["tag"],
                    ex.attrib.get("name", ""),
                    props={"vars": vars_},
                    selection=Selection(-1),
                    active=not _disabled(ex),
                )
            )
            self.report.converted.append(f"variáveis {ex.attrib['tag']} ({len(vars_)})")
        pl = self.root.find("ProbeFeatureList")
        for pr in [] if pl is None else pl.findall("ProbeFeature"):
            pv = _prop_values(pr)
            sel = _selection(pr)
            kind = "def.probe_integral" if pv.get("type") == "integral" else "def.probe_boundary_avg"
            if sel is not None and sel.dim == 1 and kind == "def.probe_integral":
                self.report.warnings.append(f"sonda {pr.attrib['tag']}: integral em contorno tratada como média")
            d.add(
                Node(
                    kind,
                    pr.attrib["tag"],
                    pr.attrib.get("name", ""),
                    props={
                        "name": pv.get("probename", pr.attrib["tag"]),
                        "expr": pv.get("expr", ""),
                        "unit": pv.get("unit", ""),
                    },
                    selection=sel,
                )
            )
            self.report.converted.append(f"sonda {pv.get('probename', pr.attrib['tag'])}")

    def geometry(self, m: Model) -> None:
        geo = self.root.find("GeomList/GeomSequence")
        if geo is None:
            self.report.skipped.append("geometria (sequência não encontrada)")
            return
        g = m.comp.geometry
        flist = geo.find("GeomFeatureList")
        for f in [] if flist is None else flist.findall("GeomFeature"):
            op = f.attrib.get("op", "")
            pv = _prop_values(f)
            tag, label = f.attrib["tag"], f.attrib.get("name", "")
            key = next((c.text or "" for c in f if c.tag == "key"), "")
            if op == "Rectangle" or ("typesolid" in key and "size" in pv):
                size = pv.get("size", "1|1").split("|")
                pos = pv.get("pos", "0|0").split("|")
                if "basecenter" in key:
                    self.report.warnings.append(f"{tag}: retângulo com base no centro convertido para canto")
                g.add(
                    Node(
                        "geom.rectangle",
                        tag,
                        label,
                        props={"x": pos[0], "y": pos[1], "width": size[0], "height": size[1]},
                        active=not _disabled(f),
                    )
                )
                self.report.converted.append(f"geometria {tag} ({label})")
            elif op == "Union" or tag == "fin" or "actionunion" in key:
                g.add(Node("geom.form_union", tag, "Formar união"))
                self.report.converted.append("geometria: formar união")
            elif op == "IgnoreEdges" or tag.startswith("ige"):
                ents: list[int] = []
                for s in f.iter():
                    if "entities" in s.attrib:
                        ents = list(parse_entities(s.attrib["entities"]))  # type: ignore[arg-type]
                g.add(Node("geom.ignore_edges", tag, label, props={"edges": ents}))
                self.report.converted.append(f"geometria {tag}: remover arestas {ents}")
            else:
                self.report.skipped.append(f"geometria {tag} ({label}, operação {op or 'desconhecida'})")
        lu = next((c.text for c in geo.iter() if c.tag == "lengthUnit"), None)
        key = next((c.text or "" for f in geo.findall("GeomFeatureList/GeomFeature") for c in f if c.tag == "key"), "")
        m.comp.length_unit = lu or ("mm" if "lx100.0" in key else "m")
        if lu is None:
            self.report.warnings.append(f"unidade de comprimento inferida: {m.comp.length_unit}")

    def materials(self, m: Model) -> None:
        names = {
            "porosity": "porosity",
            "hydraulicpermeability": "permeability",
            "electricconductivity": "sigma",
            "sigmal": "sigmal",
            "density": "density",
            "dynamicviscosity": "viscosity",
        }
        ml = self.root.find("MaterialList")
        for mat in [] if ml is None else ml.findall("Material"):
            props: dict[str, str] = {}
            for mm in mat.iter("MaterialModel"):
                for k, v in _params(mm).items():
                    if k in names and v:
                        props[names[k]] = first(v)
            if "viscosity" in props and "eta_liquid" in props["viscosity"]:
                self.report.warnings.append(
                    f"{mat.attrib['tag']}: viscosidade/densidade dependem de funções internas de T da biblioteca "
                    "de materiais de origem; substituídas por valores da água a T (ver docs/physics §6)"
                )
                props["viscosity"] = "1.002e-3[Pa*s]"
                props["density"] = "998.2[kg/m^3]"
            m.comp.materials.add(
                Node(
                    "material",
                    mat.attrib["tag"],
                    mat.attrib.get("name", ""),
                    props={"properties": props},
                    selection=_selection(mat) or Selection(2),
                )
            )
            self.report.converted.append(f"material {mat.attrib.get('name', '')}")

    # -------------------------------------------------------------- físicas
    def physics(self, m: Model) -> None:
        pl = self.root.find("PhysicsList")
        for ph in [] if pl is None else pl.findall("Physics"):
            op, tag = ph.attrib.get("op", ""), ph.attrib["tag"]
            conv = {
                "Brinkman": self._brinkman,
                "SecondaryCurrentDistribution": self._current,
                "DilutedSpeciesPorousMedia": self._transport,
                "GlobalEquations": self._global,
            }.get(op)
            if conv is None:
                self.report.skipped.append(f"física {tag} ({ph.attrib.get('name', '')}, tipo {op})")
                continue
            node = conv(ph)
            node.label = ph.attrib.get("name", node.label)
            node.active = not _disabled(ph)
            m.comp.physics.add(node)
            self.report.converted.append(f"física {tag} ({ph.attrib.get('name', '')})")

    def _features(self, ph: ET.Element) -> list[ET.Element]:
        fl = ph.find("PhysicsFeatureList")
        return [] if fl is None else fl.findall("PhysicsFeature")

    def _sub(self, f: ET.Element) -> list[ET.Element]:
        fl = f.find("PhysicsFeatureList")
        return [] if fl is None else fl.findall("PhysicsFeature")

    def _mk(self, kind: str, f: ET.Element, props: dict[str, Any]) -> Node:
        base = CATALOG[kind].defaults()
        base.update(props)
        return Node(
            kind,
            f.attrib["tag"],
            f.attrib.get("name", ""),
            props=base,
            selection=_selection(f),
            active=not _disabled(f),
        )

    def _skip(self, ph: ET.Element, f: ET.Element) -> None:
        self.report.skipped.append(
            f"{ph.attrib['tag']}/{f.attrib['tag']} ({f.attrib.get('name', '')}, {f.attrib.get('op')})"
        )

    def _brinkman(self, ph: ET.Element) -> Node:
        pm_el = ph.find("PhysicsPropList/PhysicsProp[@tag='PhysicalModelProperty']")
        p = _params(pm_el if pm_el is not None else ph)
        n = Node(
            "physics.brinkman",
            ph.attrib["tag"],
            props={**CATALOG["physics.brinkman"].defaults(), "stokes": first(p.get("StokesFlowProp"), "1") == "1"},
            selection=_selection(ph),
        )
        for f in self._features(ph):
            op, pr = f.attrib.get("op"), _params(f)
            if op == "PorousMedium":
                n.add(self._mk("brinkman.porous", f, {}))
            elif op == "FluidAndMatrixProperties" or f.attrib["tag"].startswith("fmp"):
                n.add(self._mk("brinkman.properties", f, {"fluid_material": first(pr.get("FluidMaterial"), "")}))
            elif op == "FluidProperties":
                n.add(self._mk("brinkman.fluid", f, {}))
            elif op == "InitialValues" or f.attrib["tag"].startswith("init"):
                n.add(self._mk("brinkman.init", f, {}))
            elif op == "WallBC" or f.attrib["tag"].startswith("wallbc"):
                n.add(self._mk("brinkman.wall", f, {}))
            elif op == "InletBoundary":
                n.add(self._mk("brinkman.inlet", f, {"U0": first(pr.get("U0in"), "0")}))
                if first(pr.get("ComponentWise")) not in ("", "NormalInflowVelocity"):
                    self.report.warnings.append(f"{f.attrib['tag']}: só velocidade normal é suportada")
            elif op == "OutletBoundary":
                n.add(self._mk("brinkman.outlet", f, {"p0": first(pr.get("p0"), "0")}))
            elif op in ("Gravity", "RotatingFrame", "Continuity", "dcont") or f.attrib["tag"] in (
                "dcont1",
                "grav1",
                "rtfr1",
            ):
                continue  # inativos/neutros neste caso (ver docs/physics §1)
            else:
                self._skip(ph, f)
        return n

    def _current(self, ph: ET.Element) -> Node:
        thick = "1[m]"
        for pp in ph.iter("PhysicsProp"):
            if pp.attrib.get("tag") in ("d", "dz"):
                thick = first(_params(pp).get("dz") or _params(pp).get("d"), thick)
        n = Node(
            "physics.current",
            ph.attrib["tag"],
            props={**CATALOG["physics.current"].defaults(), "thickness": thick},
            selection=_selection(ph),
        )
        for f in self._features(ph):
            op, pr = f.attrib.get("op"), _params(f)
            if op == "Electrolyte" or f.attrib["tag"].startswith("ice"):
                n.add(self._mk("current.electrolyte", f, {}))
            elif op == "Insulation" or f.attrib["tag"].startswith("ins"):
                n.add(self._mk("current.insulation", f, {}))
            elif op == "InitialValues" or f.attrib["tag"].startswith("init"):
                n.add(self._mk("current.init", f, {}))
            elif op == "ElectricPotential":
                n.add(self._mk("current.potential", f, {"phis": first(pr.get("phisbnd"), "0")}))
            elif op == "PorousElectrode":
                e = n.add(
                    self._mk(
                        "current.porous_electrode",
                        f,
                        {"epsl": first(pr.get("epsl"), "0.4"), "epss": first(pr.get("epss"), "0.6")},
                    )
                )
                for s in self._sub(f):
                    sop, sp = s.attrib.get("op"), _params(s)
                    if sop == "PorousMatrixDoubleLayerCapacitance":
                        e.add(
                            self._mk(
                                "current.double_layer",
                                s,
                                {"av": first(sp.get("av_dl"), "1"), "Cdl": first(sp.get("Cdl"), "0.2")},
                            )
                        )
                    elif sop == "PorousElectrodeReaction" or s.attrib["tag"].startswith("per"):
                        e.add(
                            self._mk(
                                "current.reaction_linear",
                                s,
                                {
                                    "i0": first(sp.get("i0"), "1"),
                                    "av": first(sp.get("Av"), "1"),
                                    "Eeq": first(sp.get("Eeq"), "0"),
                                    "alphaa": first(sp.get("alphaa"), "0.5"),
                                    "alphac": first(sp.get("alphac"), "0.5"),
                                },
                            )
                        )
                        kin = first(sp.get("ElectrodeKinetics"))
                        if kin and kin != "LinButlerVolmer":
                            self.report.warnings.append(f"{s.attrib['tag']}: cinética {kin} convertida como linear")
                    else:
                        self._skip(ph, s)
            elif f.attrib["tag"].startswith("dcont"):
                continue
            else:
                self._skip(ph, f)
        return n

    def _transport(self, ph: ET.Element) -> Node:
        species: list[str] = []
        for fl in ph.iter("PhysicsField"):
            if fl.attrib.get("tag") == "concentration":
                comp = next((c.text for c in fl if c.tag == "components"), "")
                species = parse_values("0|" + (comp or "").split(",", 1)[1]) if comp else []
                species = [s for s in re.findall(r"'([^']*)'", comp or "")]
        mig = True
        for pp in ph.iter("PhysicsProp"):
            if pp.attrib.get("tag") == "TransportMechanism":
                mig = first(_params(pp).get("Migration"), "1") in ("1", "true")
        n = Node(
            "physics.transport",
            ph.attrib["tag"],
            props={**CATALOG["physics.transport"].defaults(), "species": species, "migration": mig},
            selection=_selection(ph),
        )
        for f in self._features(ph):
            op, pr, tag = f.attrib.get("op"), _params(f), f.attrib["tag"]
            if op == "ConvectionDiffusionMigration" or tag.startswith("cdm"):
                D = [first(pr.get(f"D_{s}"), "1e-9") for s in species]
                n.add(self._mk("transport.free", f, {"D": D, "z": parse_values(pr.get("z"))}))
                pot = first(pr.get("V"), "phil")
                n.props["potential"] = pot
            elif op == "PorousMedium":
                fluid_el = next((s for s in self._sub(f) if s.attrib["tag"].startswith("fluid")), None)
                fp = _params(fluid_el) if fluid_el is not None else {}
                DF = [first(fp.get(f"DF_{s}"), "1e-9") for s in species]
                model = "bruggeman" if "Bruggeman" in first(fp.get("FluidDiffusivityModelType"), "") else "nenhuma"
                n.add(self._mk("transport.porous", f, {"DF": DF, "z": parse_values(fp.get("z")), "model": model}))
            elif op == "NoFlux" or tag.startswith("nflx"):
                n.add(self._mk("transport.noflux", f, {}))
            elif op == "InitialValues" or tag.startswith("init"):
                n.add(self._mk("transport.init", f, {"c": parse_values(pr.get("initc"))}))
            elif op == "Inflow":
                n.add(self._mk("transport.inflow", f, {"c0": parse_values(pr.get("c0"))}))
            elif op == "Outflow":
                n.add(self._mk("transport.outflow", f, {}))
            elif op == "Concentration":
                n.add(
                    self._mk(
                        "transport.concentration",
                        f,
                        {
                            "apply": [v in ("1", "true") for v in parse_values(pr.get("species"))],
                            "c": parse_values(pr.get("c0")),
                        },
                    )
                )
            elif op == "PorousElectrodeCoupling":
                pec = n.add(self._mk("transport.electrode_coupling", f, {}))
                for s in self._sub(f):
                    sp = _params(s)
                    pec.add(
                        self._mk(
                            "transport.reaction_coeffs",
                            s,
                            {
                                "iv": first(sp.get("iv"), "0"),
                                "n": first(sp.get("nm"), "1"),
                                "nu": parse_values(sp.get("Vi")),
                            },
                        )
                    )
            elif op == "SpeciesCharges" or tag.startswith("sp"):
                n.props["charges"] = parse_values(pr.get("z")) or n.props["charges"]
                t = first(pr.get("minput_temperature"))
                if t:
                    n.props["temperature"] = t
            elif tag.startswith("dcont") or op in ("PorousMediaTransportProperties",):
                if op == "PorousMediaTransportProperties" and not _disabled(f):
                    self._skip(ph, f)
                continue
            else:
                self._skip(ph, f)
        return n

    def _global(self, ph: ET.Element) -> Node:
        n = Node("physics.global", ph.attrib["tag"], selection=Selection(-1))
        for f in self._features(ph):
            pr = _params(f)
            names, eqs = parse_values(pr.get("name")), parse_values(pr.get("equation"))
            inits = parse_values(pr.get("initialValueU"))
            units = parse_values(pr.get("CustomDependentVariableUnit"))
            rows = [
                [
                    nm,
                    eqs[i] if i < len(eqs) else "0",
                    inits[i] if i < len(inits) else "0",
                    units[i] if i < len(units) else "",
                ]
                for i, nm in enumerate(names)
            ]
            n.add(self._mk("global.equations", f, {"equations": rows}))
        return n

    def multiphysics(self, m: Model) -> None:
        ml = self.root.find("MultiphysicsCouplingList")
        for c in [] if ml is None else ml.findall("MultiphysicsCoupling"):
            pr = _params(c)
            if c.attrib.get("op", "").startswith("ReactingFlow") or c.attrib["tag"].startswith("rfd"):
                m.comp.multiphysics.add(
                    Node(
                        "multi.flow_transport",
                        c.attrib["tag"],
                        c.attrib.get("name", ""),
                        props={
                            "flow": first(pr.get("Fluid_physics"), "br"),
                            "transport": first(pr.get("Species_physics"), "tds"),
                        },
                        selection=Selection(2),
                    )
                )
                self.report.converted.append(f"acoplamento {c.attrib['tag']}")
            else:
                self.report.skipped.append(f"acoplamento {c.attrib['tag']} ({c.attrib.get('op')})")

    def mesh(self, m: Model) -> None:
        ms = self.root.find("MeshList/MeshSequence/MeshFeatureList")
        for f in [] if ms is None else ms.findall("MeshFeature"):
            tag, pv = f.attrib["tag"], _prop_values(f)
            sel = None
            for s in f.iter("selection"):
                for sub in s.iter():
                    if "dim" in sub.attrib:
                        sel = Selection(int(sub.attrib["dim"]), parse_entities(sub.attrib.get("entities")))
                        break
                break
            op = f.attrib.get("op", "")
            if tag == "size" or (op == "Size" and sel is None):
                m.comp.mesh.add(
                    Node(
                        "mesh.size",
                        tag,
                        f.attrib.get("name", ""),
                        props={
                            k: pv.get(k, CATALOG["mesh.size"].defaults()[k])
                            for k in ("hmax", "hmin", "hgrad", "hcurve")
                        },
                    )
                )
            elif op == "Size" or tag.startswith("size"):
                m.comp.mesh.add(
                    Node(
                        "mesh.size_local",
                        tag,
                        f.attrib.get("name", ""),
                        props={
                            k: pv.get(k, CATALOG["mesh.size_local"].defaults()[k]) for k in ("hmax", "hmin", "hgrad")
                        },
                        selection=sel,
                    )
                )
            elif op == "FreeTri" or tag.startswith("ftri"):
                m.comp.mesh.add(Node("mesh.triangles", tag, f.attrib.get("name", "")))
            elif op == "BndLayer" or tag.startswith("bl"):
                blp = next((s for s in f.iter("MeshFeature") if s.attrib["tag"].startswith("blp")), None)
                bsel = None
                if blp is not None:
                    for sub in blp.iter():
                        if sub.tag == "selection":
                            for x in sub.iter():
                                if "dim" in x.attrib:
                                    bsel = Selection(int(x.attrib["dim"]), parse_entities(x.attrib.get("entities")))
                                    break
                            break
                bp = _prop_values(blp) if blp is not None else {}
                m.comp.mesh.add(
                    Node(
                        "mesh.boundary_layers",
                        tag,
                        f.attrib.get("name", ""),
                        props={
                            "n": int(bp.get("blnlayers", 8)),
                            "stretch": bp.get("blstretch", "1.2"),
                            "first": bp.get("blhminfact", "1"),
                        },
                        selection=bsel,
                    )
                )
                self.report.warnings.append("camadas-limite: número de camadas padrão assumido quando ausente")
            else:
                self.report.skipped.append(f"malha {tag} ({f.attrib.get('name', '')})")
        self.report.converted.append(
            "configurações de malha (a malha em si não é lida: o arquivo pode estar sem malha)"
        )

    def studies(self, m: Model) -> None:
        sl = self.root.find("StudyList")
        for st in [] if sl is None else sl.findall("Study"):
            sn = m.studies.add(Node("study", st.attrib["tag"], st.attrib.get("name", "")))
            fl = st.find("StudyFeatureList")
            for f in [] if fl is None else fl.findall("StudyFeature"):
                pv, tag = _prop_values(f), f.attrib["tag"]
                key = next((c.text or "" for c in f if c.tag == "key"), "")
                act = pv.get("activate", "").split("|")
                phys = [
                    act[i]
                    for i in range(0, len(act) - 1, 2)
                    if act[i + 1] == "on" and not act[i].startswith(("frame:", "comp"))
                ]
                cpl = pv.get("activateCoupling", "").split("|")
                cpls = [cpl[i] for i in range(0, len(cpl) - 1, 2) if cpl[i + 1] == "on"]
                op = f.attrib.get("op", "")
                if op == "Transient" or tag.startswith("time"):
                    mt = re.search(r"tlist(range\(.*?\)(?:\s+range\(.*?\))*)", key)
                    tlist = (
                        mt.group(1)
                        if mt
                        else "range({},{},{})".format(
                            pv.get("tlist_vector_start", "0"),
                            pv.get("tlist_vector_step", "1"),
                            pv.get("tlist_vector_stop", "1"),
                        )
                    )
                    sn.add(
                        Node(
                            "step.time",
                            tag,
                            f.attrib.get("name", ""),
                            props={
                                "physics": phys,
                                "couplings": cpls,
                                "tlist": tlist,
                                "rtol": pv.get("rtol", "1e-3"),
                                "bdf_max_order": 2,
                            },
                            active=not _disabled(f),
                        )
                    )
                elif op == "Stationary" or tag.startswith("stat"):
                    sn.add(
                        Node(
                            "step.stationary",
                            tag,
                            f.attrib.get("name", ""),
                            props={"physics": phys, "couplings": cpls},
                            active=not _disabled(f),
                        )
                    )
                elif op == "Parametric" or tag.startswith("param"):
                    names = pv.get("pname", "").split("|")
                    rows = []
                    for c in f:
                        if c.tag == "propertyValue" and c.attrib.get("name") == "p:plistarr":
                            rows = parse_values(c.attrib.get("ValueRows"))
                    units = pv.get("punit", "").split("|")
                    table = [
                        [n, rows[i] if i < len(rows) else "", units[i] if i < len(units) else ""]
                        for i, n in enumerate(names)
                        if n
                    ]
                    sn.add(
                        Node(
                            "step.sweep",
                            tag,
                            f.attrib.get("name", ""),
                            props={"params": table},
                            active=not _disabled(f),
                        )
                    )
                else:
                    self.report.skipped.append(f"estudo {tag} ({op})")
            self.report.converted.append(f"estudo {st.attrib['tag']} ({len(sn.children)} passos)")

    def to_model(self) -> Model:
        m = Model(name=self.path.stem, description=f"Convertido de {self.path.name} ({self.file_version.strip()})")
        m.comp.sections["definitions"].children.clear()
        for step in (
            self.parameters,
            self.functions,
            self.definitions,
            self.geometry,
            self.materials,
            self.physics,
            self.multiphysics,
            self.mesh,
            self.studies,
        ):
            try:
                step(m)
            except Exception as exc:  # um bloco com problema não impede o resto da conversão
                self.report.warnings.append(f"falha ao converter {step.__name__}: {exc}")
        m.meta["source"] = {"file": self.path.name, "format": "mph", "version": self.file_version.strip()}
        m.meta["conversion_report"] = self.report.summary()
        return m


def read_mph(path: str | Path) -> tuple[Model, ConversionReport]:
    r = MphReader(path)
    m = r.to_model()
    return m, r.report


def convert_mph(src: str | Path, dest: str | Path) -> ConversionReport:
    m, rep = read_mph(src)
    kfem_format.save(m, dest, {"conversion_report.txt": rep.summary().encode()})
    return rep
