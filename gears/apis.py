from __future__ import annotations

from typing import Any, Dict

from core import SOLVER_REGISTRY


class GearForceAPI:
    def solve(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        solve_path = problem.get("inputs", {}).get("solve_path") or problem.get("solve_path")
        if not solve_path:
            raise ValueError("Missing solve_path in problem definition.")
        solver_cls = SOLVER_REGISTRY.get(solve_path)
        if solver_cls is None:
            valid = ", ".join(sorted(SOLVER_REGISTRY))
            raise ValueError(f"Unsupported solve_path '{solve_path}'. Valid options: {valid}")
        solver = solver_cls(problem)
        return solver.solve()
