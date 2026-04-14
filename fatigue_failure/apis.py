from __future__ import annotations

from typing import Any

try:
    from .core import DigitizedDataRepository, FatigueStrengthSolver
    from .utils import ValidationError
except ImportError:  # pragma: no cover
    from core import DigitizedDataRepository, FatigueStrengthSolver
    from utils import ValidationError


class SolverAPI:
    """Registry-based API layer for extensible solve-path routing."""

    def __init__(self, data_dir: str | None = None) -> None:
        repository = DigitizedDataRepository(data_dir=data_dir)
        fatigue_strength_solver = FatigueStrengthSolver(repository=repository)
        self._solvers = {
            fatigue_strength_solver.solve_path: fatigue_strength_solver,
        }

    def available_solve_paths(self) -> list[str]:
        return sorted(self._solvers)

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        solve_path = inputs.get("solve_path")
        if not solve_path:
            raise ValidationError(
                "Input payload is missing 'solve_path'. Available solve paths: "
                + ", ".join(self.available_solve_paths())
            )
        solver = self._solvers.get(str(solve_path))
        if solver is None:
            raise ValidationError(
                f"Unsupported solve_path={solve_path!r}. Available solve paths: "
                + ", ".join(self.available_solve_paths())
            )
        return solver.solve(payload)
