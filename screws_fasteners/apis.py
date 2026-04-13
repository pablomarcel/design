from __future__ import annotations

from typing import Any, Dict

try:
    from .core import (
        BoltStrengthSolver,
        FastenerMemberStiffnessSolver,
        SquareThreadPowerScrewSolver,
        StaticallyLoadedTensionJointWithPreloadSolver,
        FatigueLoadingTensionJointSolver,
        ShearLoadedBoltedJointSolver,
    )
    from .utils import ValidationError
except ImportError:  # pragma: no cover
    from core import (
        BoltStrengthSolver,
        FastenerMemberStiffnessSolver,
        SquareThreadPowerScrewSolver,
        StaticallyLoadedTensionJointWithPreloadSolver,
        FatigueLoadingTensionJointSolver,
        ShearLoadedBoltedJointSolver,
    )
    from utils import ValidationError


SOLVER_REGISTRY = {
    SquareThreadPowerScrewSolver.solve_path: SquareThreadPowerScrewSolver,
    FastenerMemberStiffnessSolver.solve_path: FastenerMemberStiffnessSolver,
    BoltStrengthSolver.solve_path: BoltStrengthSolver,
    StaticallyLoadedTensionJointWithPreloadSolver.solve_path: StaticallyLoadedTensionJointWithPreloadSolver,
    FatigueLoadingTensionJointSolver.solve_path: FatigueLoadingTensionJointSolver,
    ShearLoadedBoltedJointSolver.solve_path: ShearLoadedBoltedJointSolver,
}


class SolverAPI:
    @staticmethod
    def solve(payload: Dict[str, Any]) -> Dict[str, Any]:
        if "inputs" in payload:
            solve_path = payload["inputs"].get("solve_path", payload.get("problem"))
        else:
            solve_path = payload.get("solve_path", payload.get("problem"))
        if not solve_path:
            raise ValidationError("No solve_path found in payload.")
        solver_cls = SOLVER_REGISTRY.get(solve_path)
        if solver_cls is None:
            supported = ", ".join(sorted(SOLVER_REGISTRY))
            raise ValidationError(f"Unsupported solve_path '{solve_path}'. Supported solve paths: {supported}")
        solver = solver_cls(payload)
        return solver.solve().as_dict()
