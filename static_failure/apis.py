from __future__ import annotations

from typing import Any

try:
    from .core import Example51FactorOfSafetySolver, Example52CoulombMohrSolver
except ImportError:  # pragma: no cover
    from core import Example51FactorOfSafetySolver, Example52CoulombMohrSolver


class SolverAPI:
    """Registry-backed API surface for static failure solve paths."""

    def __init__(self) -> None:
        self._registry = {
            Example51FactorOfSafetySolver.solve_path: Example51FactorOfSafetySolver(),
            Example52CoulombMohrSolver.solve_path: Example52CoulombMohrSolver(),
        }

    def available_solve_paths(self) -> list[str]:
        return sorted(self._registry.keys())

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        solve_path = inputs.get("solve_path")
        if not solve_path:
            raise ValueError("Missing required field 'solve_path' in the inputs payload.")
        solver = self._registry.get(str(solve_path))
        if solver is None:
            available = ", ".join(self.available_solve_paths())
            raise ValueError(f"Unsupported solve_path '{solve_path}'. Available solve paths: {available}")
        return solver.solve(payload)
