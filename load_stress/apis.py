from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Type

try:
    from .core import General3DStressSolver, PlaneStressRotationSolver, StressSolverBase, StressTensorInput
except ImportError:
    from core import General3DStressSolver, PlaneStressRotationSolver, StressSolverBase, StressTensorInput



@dataclass
class SolverRequest:
    solve_path: str
    inputs: StressTensorInput


class SolverRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Type[StressSolverBase]] = {}

    def register(self, solver_cls: Type[StressSolverBase]) -> None:
        self._registry[solver_cls.solve_path] = solver_cls

    def create(self, solve_path: str) -> StressSolverBase:
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
        self.registry.register(General3DStressSolver)
        self.registry.register(PlaneStressRotationSolver)

    def solve(self, request: SolverRequest):
        solver = self.registry.create(request.solve_path)
        return solver.solve(request.inputs)
