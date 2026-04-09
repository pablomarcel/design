from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    from .core import (
        DataRepository,
        StraightBevelGearAnalysisSolver,
        StraightBevelMeshDesignSolver,
        WormGearAnalysisSolver,
        WormGearMeshDesignSolver,
    )
except ImportError:  # pragma: no cover
    from core import (
        DataRepository,
        StraightBevelGearAnalysisSolver,
        StraightBevelMeshDesignSolver,
        WormGearAnalysisSolver,
        WormGearMeshDesignSolver,
    )


class BevelWormGearAPI:
    def __init__(self, data_dir: Path):
        self.repo = DataRepository(data_dir)

    def solve(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        solve_path = problem.get("solve_path")
        if solve_path == StraightBevelGearAnalysisSolver.solve_path:
            return StraightBevelGearAnalysisSolver(self.repo, problem).solve()
        if solve_path == StraightBevelMeshDesignSolver.solve_path:
            return StraightBevelMeshDesignSolver(self.repo, problem).solve()
        if solve_path == WormGearAnalysisSolver.solve_path:
            return WormGearAnalysisSolver(self.repo, problem).solve()
        if solve_path == WormGearMeshDesignSolver.solve_path:
            return WormGearMeshDesignSolver(self.repo, problem).solve()
        raise ValueError(f"Unsupported solve_path '{solve_path}'.")
