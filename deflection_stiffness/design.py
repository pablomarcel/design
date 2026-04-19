from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .utils import Issue, require


# ------------------------------ stability heuristics ------------------------------

@dataclass(frozen=True)
class BeamStability:
    """Heuristic stability summary for a planar 2D beam/frame model.

    NOTE: This is a necessary-but-not-sufficient check. It helps catch under-constrained
    models early and produces actionable messages.
    """
    n_nodes: int
    n_elements: int
    r: int  # restrained DOF count (heuristic)
    rule_ok: bool  # r >= 3 (rigid-body modes removed, necessary)

    @property
    def metric(self) -> int:
        return self.r - 3


def restrained_dofs_for_support(support_type: str, *, dof: str | None = None) -> int:
    """Return number of restrained DOFs for a support (heuristic).

    For 2D frame/beam: node DOFs are (ux, uy, rz).

    Mappings:
      - fixed  => 3 (ux, uy, rz)
      - hinged => 2 (ux, uy)  (rotation free)
      - roller => 1 (typically uy or ux depending on dof/direction)
      - spring => 1 (in specified dof: ux/uy/rz)
    """
    st = support_type.lower()
    if st == "fixed":
        return 3
    if st == "hinged":
        return 2
    if st == "roller":
        return 1
    if st == "spring":
        return 1
    return 0


def stability_heuristic(*, n_nodes: int, n_elements: int, supports: Sequence[tuple[str, str | None]]) -> BeamStability:
    r = sum(restrained_dofs_for_support(t, dof=dof) for t, dof in supports)
    rule_ok = r >= 3
    return BeamStability(n_nodes=n_nodes, n_elements=n_elements, r=r, rule_ok=rule_ok)


def issues_from_stability(stab: BeamStability) -> list[Issue]:
    issues: list[Issue] = []
    if stab.n_elements <= 0:
        issues.append(Issue("error", "No elements provided.", path="elements"))
        return issues

    if not stab.rule_ok:
        issues.append(Issue(
            level="error",
            message=(
                "Model is under-constrained for a 2D beam/frame. "
                "Necessary condition: restrained DOFs >= 3. "
                f"Here: r={stab.r} (need >=3)."
            ),
            path="design.stability",
        ))
    return issues
