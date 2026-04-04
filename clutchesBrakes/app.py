from __future__ import annotations

from typing import Any, Dict

from core import AnnularPadCaliperSolver, DoorstopSolver, InternalExpandingRimBrakeSolver, SolveResult
from utils import ValidationError


class ClutchesBrakesApp:
    def __init__(self) -> None:
        self._solvers = {
            "doorstop": DoorstopSolver(),
            "rim_brake": InternalExpandingRimBrakeSolver(),
            "annular_pad": AnnularPadCaliperSolver(),
        }

    def solve(self, problem_type: str, payload: Dict[str, Any]) -> SolveResult:
        solver = self._solvers.get(problem_type)
        if solver is None:
            raise ValidationError(f"Unknown problem_type '{problem_type}'. Valid types: {', '.join(sorted(self._solvers))}")
        return solver.solve(payload)

    def solve_from_payload(self, payload: Dict[str, Any]) -> SolveResult:
        problem_type = payload.get("problem_type")
        if not problem_type:
            raise ValidationError("Input JSON must include 'problem_type'.")
        body = dict(payload)
        body.pop("problem_type", None)
        body.pop("schema", None)
        body.pop("meta", None)
        return self.solve(problem_type, body)
