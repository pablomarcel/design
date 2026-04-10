from __future__ import annotations

from typing import Any

from core import HelicalGearAnalysisSolver, SpurGearAnalysisSolver, SpurGearDesignSolver


class SolverFactory:
    SOLVERS = {
        "spur_analysis": SpurGearAnalysisSolver,
        "helical_analysis": HelicalGearAnalysisSolver,
        "spur_design": SpurGearDesignSolver,
    }

    @classmethod
    def create(cls, problem: dict[str, Any]):
        solve_path = problem.get("solve_path")
        if solve_path not in cls.SOLVERS:
            supported = ", ".join(sorted(cls.SOLVERS))
            raise ValueError(f"Unsupported solve_path={solve_path!r}. Supported solve paths: {supported}")
        return cls.SOLVERS[solve_path](problem)
