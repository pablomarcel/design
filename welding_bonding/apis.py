from __future__ import annotations

from typing import Any, Dict, Mapping

try:
    from .core import (
        DesignWeldStaticLoadingSolver,
        ParallelWeldStaticLoadingSolver,
        WeldGroupTorsionSolver,
        WeldedJointBendingStaticLoadingSolver,
    )
except ImportError:  # pragma: no cover
    from core import (
        DesignWeldStaticLoadingSolver,
        ParallelWeldStaticLoadingSolver,
        WeldGroupTorsionSolver,
        WeldedJointBendingStaticLoadingSolver,
    )


class SolverAPI:
    def __init__(self) -> None:
        solvers = [
            WeldGroupTorsionSolver(),
            ParallelWeldStaticLoadingSolver(),
            DesignWeldStaticLoadingSolver(),
            WeldedJointBendingStaticLoadingSolver(),
        ]
        self._solvers = {solver.solve_path: solver for solver in solvers}

    def available_solve_paths(self) -> list[str]:
        return sorted(self._solvers.keys())

    def solve(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        solve_path = payload.get('solve_path')
        if not solve_path:
            raise ValueError("Input payload is missing 'solve_path'")
        if solve_path not in self._solvers:
            raise ValueError(
                f"Unsupported solve_path {solve_path!r}. Available solve paths: {', '.join(self.available_solve_paths())}"
            )
        return self._solvers[solve_path].solve(payload)
