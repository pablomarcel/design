from __future__ import annotations

from typing import Any

try:
    from .core import (
        DigitizedDataRepository,
        FatigueStrengthSolver,
        SurfaceFactorSolver,
        SizeFactorSolver,
        TemperatureFactorSolver,
        StressConcentrationNotchSensitivitySolver,
    )
    from .utils import ValidationError
except ImportError:  # pragma: no cover
    from core import (
        DigitizedDataRepository,
        FatigueStrengthSolver,
        SurfaceFactorSolver,
        SizeFactorSolver,
        TemperatureFactorSolver,
        StressConcentrationNotchSensitivitySolver,
    )
    from utils import ValidationError


class SolverAPI:
    """Registry-based API layer for extensible solve-path routing."""

    def __init__(self, data_dir: str | None = None) -> None:
        repository = DigitizedDataRepository(data_dir=data_dir)
        fatigue_strength_solver = FatigueStrengthSolver(repository=repository)
        surface_factor_solver = SurfaceFactorSolver(repository=repository)
        size_factor_solver = SizeFactorSolver(repository=repository)
        temperature_factor_solver = TemperatureFactorSolver(repository=repository)
        stress_concentration_notch_sensitivity_solver = StressConcentrationNotchSensitivitySolver(repository=repository)
        self._solvers = {
            fatigue_strength_solver.solve_path: fatigue_strength_solver,
            surface_factor_solver.solve_path: surface_factor_solver,
            size_factor_solver.solve_path: size_factor_solver,
            temperature_factor_solver.solve_path: temperature_factor_solver,
            stress_concentration_notch_sensitivity_solver.solve_path: stress_concentration_notch_sensitivity_solver,
        }

    def available_solve_paths(self) -> list[str]:
        return sorted(self._solvers)

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        solve_path = inputs.get("solve_path")
        if not solve_path:
            raise ValidationError(
                "Input payload is missing 'solve_path'. Available solve paths: "
                + ", ".join(self.available_solve_paths())
            )
        solver = self._solvers.get(str(solve_path))
        if solver is None:
            raise ValidationError(
                f"Unsupported solve_path={solve_path!r}. Available solve paths: "
                + ", ".join(self.available_solve_paths())
            )
        return solver.solve(payload)
