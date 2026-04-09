from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    from .core import DataRepository, StraightBevelGearAnalysisSolver, StraightBevelMeshDesignSolver
except ImportError:  # pragma: no cover
    from core import DataRepository, StraightBevelGearAnalysisSolver, StraightBevelMeshDesignSolver


class BevelWormGearAPI:
    def __init__(self, data_dir: Path):
        self.repo = DataRepository(data_dir)

    def solve(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        solve_path = problem.get("solve_path")
        if solve_path == StraightBevelGearAnalysisSolver.solve_path:
            return StraightBevelGearAnalysisSolver(self.repo, problem).solve()
        if solve_path == StraightBevelMeshDesignSolver.solve_path:
            return StraightBevelMeshDesignSolver(self.repo, problem).solve()
        raise ValueError(f"Unsupported solve_path '{solve_path}'.")
