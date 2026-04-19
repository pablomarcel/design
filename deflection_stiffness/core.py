from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from .design import issues_from_stability, stability_heuristic
from .utils import Issue, ensure_unique, require

# ------------------------------ domain models ------------------------------

SupportType = Literal["fixed", "hinged", "roller", "spring"]

LoadType = Literal["point", "distributed", "moment"]

PlotBackend = Literal["anastruct", "plotly"]
PlotFormat = Literal["png", "html", "json"]


@dataclass(frozen=True)
class NodeSpec:
    id: str
    x: float
    y: float


@dataclass(frozen=True)
class ElementSpec:
    id: str
    n1: str
    n2: str
    EA: float | None = None
    EI: float | None = None


@dataclass(frozen=True)
class SupportSpec:
    node: str
    type: SupportType
    # Optional: for roller/spring choose dof: ux, uy, rz
    dof: str | None = None
    k: float | None = None  # spring stiffness


@dataclass(frozen=True)
class LoadSpec:
    type: LoadType


@dataclass(frozen=True)
class PointLoad(LoadSpec):
    node: str
    Fx: float = 0.0
    Fy: float = 0.0

    def __init__(self, *, node: str, Fx: float = 0.0, Fy: float = 0.0) -> None:
        object.__setattr__(self, "type", "point")
        object.__setattr__(self, "node", node)
        object.__setattr__(self, "Fx", Fx)
        object.__setattr__(self, "Fy", Fy)


@dataclass(frozen=True)
class DistributedLoad(LoadSpec):
    element: str
    q: float
    direction: Literal["x", "y"] = "y"

    def __init__(self, *, element: str, q: float, direction: Literal["x", "y"] = "y") -> None:
        object.__setattr__(self, "type", "distributed")
        object.__setattr__(self, "element", element)
        object.__setattr__(self, "q", q)
        object.__setattr__(self, "direction", direction)


@dataclass(frozen=True)
class MomentLoad(LoadSpec):
    node: str
    Ty: float  # anastruct uses Ty for out-of-plane moment

    def __init__(self, *, node: str, Ty: float) -> None:
        object.__setattr__(self, "type", "moment")
        object.__setattr__(self, "node", node)
        object.__setattr__(self, "Ty", Ty)


@dataclass(frozen=True)
class Units:
    length: str = "m"
    force: str = "N"
    moment: str = "N*m"


@dataclass(frozen=True)
class BeamOptions:
    solver: str = "anastruct"

    # outputs
    plots: bool = True
    plot_backend: PlotBackend = "anastruct"
    plot_format: PlotFormat = "png"
    deform_scale: float = 1.0

    # defaults (used when element EA/EI are omitted)
    EA_default: float | None = None
    EI_default: float | None = None

    # anastruct-only plot tuning
    anastruct_plots: tuple[str, ...] = (
        "structure",
        "reaction_force",
        "axial_force",
        "shear_force",
        "bending_moment",
        "displacement",
    )
    anastruct_dpi: int = 150
    anastruct_figsize: tuple[float, float] = (12.0, 8.0)
    anastruct_zip: bool = False


@dataclass(frozen=True)
class BeamProblem:
    schema: str
    nodes: tuple[NodeSpec, ...]
    elements: tuple[ElementSpec, ...]
    supports: tuple[SupportSpec, ...] = ()
    loads: tuple[LoadSpec, ...] = ()
    units: Units = Units()
    options: BeamOptions = BeamOptions()
    meta: dict[str, Any] = field(default_factory=dict)

    def validate(self, *, strict: bool = True) -> list[Issue]:
        issues: list[Issue] = []

        require(self.schema.startswith("beams."), f"Unsupported schema: {self.schema!r}")

        ensure_unique([n.id for n in self.nodes], what="node ids")
        ensure_unique([e.id for e in self.elements], what="element ids")

        node_ids = {n.id for n in self.nodes}
        el_ids = {e.id for e in self.elements}

        # elements reference nodes
        for e in self.elements:
            if e.n1 not in node_ids:
                issues.append(Issue("error", f"Element {e.id} references missing node {e.n1}", path=f"elements[{e.id}].n1"))
            if e.n2 not in node_ids:
                issues.append(Issue("error", f"Element {e.id} references missing node {e.n2}", path=f"elements[{e.id}].n2"))
            if e.n1 == e.n2:
                issues.append(Issue("error", f"Element {e.id} has identical endpoints", path=f"elements[{e.id}]"))

        # supports reference nodes
        for s in self.supports:
            if s.node not in node_ids:
                issues.append(Issue("error", f"Support references missing node {s.node}", path=f"supports[{s.node}]"))
            st = s.type.lower()
            if st not in ("fixed", "hinged", "roller", "spring"):
                issues.append(Issue("error", f"Unknown support type {s.type!r}", path=f"supports[{s.node}].type"))
            if st in ("roller", "spring"):
                if s.dof not in ("ux", "uy", "rz"):
                    issues.append(Issue("error", f"{s.type} support requires dof='ux'|'uy'|'rz'", path=f"supports[{s.node}].dof"))
            if st == "spring":
                if s.k is None or s.k <= 0:
                    issues.append(Issue("error", "spring support requires positive k", path=f"supports[{s.node}].k"))

        # loads reference nodes/elements
        for ld in self.loads:
            if ld.type == "point":
                if getattr(ld, "node", None) not in node_ids:
                    issues.append(Issue("error", f"Point load references missing node {getattr(ld,'node',None)}", path="loads.point"))
            elif ld.type == "moment":
                if getattr(ld, "node", None) not in node_ids:
                    issues.append(Issue("error", f"Moment load references missing node {getattr(ld,'node',None)}", path="loads.moment"))
            elif ld.type == "distributed":
                if getattr(ld, "element", None) not in el_ids:
                    issues.append(Issue("error", f"Distributed load references missing element {getattr(ld,'element',None)}", path="loads.distributed"))

        # stability heuristic
        supports_for_r = tuple((s.type, s.dof) for s in self.supports)
        stab = stability_heuristic(n_nodes=len(self.nodes), n_elements=len(self.elements), supports=supports_for_r)
        issues.extend(issues_from_stability(stab))

        if strict:
            errors = [i for i in issues if i.level == "error"]
            if errors:
                msg = "Problem validation failed:\n" + "\n".join(f"- {e.message} ({e.path})" for e in errors)
                raise ValueError(msg)

        return issues


# ------------------------------ results ------------------------------

@dataclass(frozen=True)
class NodeResult:
    node: str
    ux: float
    uy: float
    rz: float


@dataclass(frozen=True)
class ReactionResult:
    node: str
    Rx: float
    Ry: float
    Mz: float


@dataclass(frozen=True)
class ElementResult:
    element: str
    axial: float
    shear: float
    moment: float


@dataclass(frozen=True)
class BeamResults:
    nodes: tuple[NodeResult, ...] = ()
    reactions: tuple[ReactionResult, ...] = ()
    elements: tuple[ElementResult, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)
