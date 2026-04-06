from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .core import (
        FlatBeltAnalysisSolver,
        FlatBeltDriveDesignSolver,
        MetalFlatBeltSelectionSolver,
        VBeltAnalysisSolver,
        RollerChainSelectionSolver,
        WireRopeFatigueAnalysisSolver,
    )
    from .in_out import CsvRepository
except ImportError:  # pragma: no cover
    from core import FlatBeltAnalysisSolver, FlatBeltDriveDesignSolver, MetalFlatBeltSelectionSolver, VBeltAnalysisSolver, RollerChainSelectionSolver, WireRopeFatigueAnalysisSolver
    from in_out import CsvRepository


class FlexibleElementsAPI:
    def __init__(self, data_dir: Path):
        repo = CsvRepository(data_dir)
        self._solvers = {
            "flat_analysis": FlatBeltAnalysisSolver(repo),
            "flat_design": FlatBeltDriveDesignSolver(repo),
            "metal_flat_selection": MetalFlatBeltSelectionSolver(repo),
            "v_belt_analysis": VBeltAnalysisSolver(repo),
            "roller_chain_selection": RollerChainSelectionSolver(repo),
            "wire_rope_fatigue_analysis": WireRopeFatigueAnalysisSolver(repo),
        }

    @property
    def solve_paths(self) -> list[str]:
        return sorted(self._solvers)

    def solve(self, solve_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            solver = self._solvers[solve_path]
        except KeyError as exc:
            raise KeyError(
                f"Unknown solve path '{solve_path}'. Available: {', '.join(self.solve_paths)}"
            ) from exc
        return solver.solve(payload)
