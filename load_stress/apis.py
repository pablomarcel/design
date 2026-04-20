from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Type

try:
    from .core import (
        General3DStrainSolver,
        General3DStressSolver,
        Hooke3DFromStrainSolver,
        PlaneStrainRotationSolver,
        PlaneStressRotationSolver,
        SingleGaugeBiaxialPlaneStressSolver,
        SolverBase,
        SolverInput,
        StrainRosetteEquiangularSolver,
        StrainRosetteGeneralSolver,
        StrainRosetteRectangularSolver,
    )
except ImportError:
    from core import (
        General3DStrainSolver,
        General3DStressSolver,
        Hooke3DFromStrainSolver,
        PlaneStrainRotationSolver,
        PlaneStressRotationSolver,
        SingleGaugeBiaxialPlaneStressSolver,
        SolverBase,
        SolverInput,
        StrainRosetteEquiangularSolver,
        StrainRosetteGeneralSolver,
        StrainRosetteRectangularSolver,
    )


@dataclass
class SolverRequest:
    solve_path: str
    inputs: SolverInput


class SolverRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Type[SolverBase]] = {}

    def register(self, solver_cls: Type[SolverBase]) -> None:
        self._registry[solver_cls.solve_path] = solver_cls

    def create(self, solve_path: str) -> SolverBase:
        try:
            solver_cls = self._registry[solve_path]
        except KeyError as exc:
            available = ", ".join(sorted(self._registry))
            raise ValueError(f"Unknown solve_path '{solve_path}'. Available: {available}") from exc
        return solver_cls()

    def available(self) -> list[str]:
        return sorted(self._registry)


class SolverAPI:
    def __init__(self) -> None:
        self.registry = SolverRegistry()
        for solver_cls in [
            General3DStressSolver,
            PlaneStressRotationSolver,
            General3DStrainSolver,
            PlaneStrainRotationSolver,
            StrainRosetteRectangularSolver,
            StrainRosetteEquiangularSolver,
            StrainRosetteGeneralSolver,
            Hooke3DFromStrainSolver,
            SingleGaugeBiaxialPlaneStressSolver,
        ]:
            self.registry.register(solver_cls)

    def solve(self, request: SolverRequest):
        solver = self.registry.create(request.solve_path)
        return solver.solve(request.inputs)
