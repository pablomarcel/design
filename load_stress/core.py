from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class StressTensorInput:
    sxx: float
    syy: float
    szz: float
    txy: float = 0.0
    tyz: float = 0.0
    txz: float = 0.0
    unit: str = ""
    phi_deg: Optional[float] = None
    title: str = ""


@dataclass
class PlaneStressResults:
    sigma_avg: float
    radius: float
    sigma1: float
    sigma2: float
    tau_max_in_plane: float
    theta_p_deg_ccw: float
    theta_s_deg_ccw: float
    point_x: tuple[float, float]
    point_y: tuple[float, float]


@dataclass
class RotatedPlaneStressResults:
    phi_deg_ccw: float
    sigma_x_prime: float
    sigma_y_prime: float
    tau_x_prime_y_prime: float
    point_x_prime: tuple[float, float]
    point_y_prime: tuple[float, float]


@dataclass
class StressAnalysisResult:
    problem: str
    solve_path: str
    title: str
    inputs: dict[str, Any]
    tensor: list[list[float]]
    principal_stresses: list[float]
    mean_stress: float
    max_shear_tresca: float
    von_mises: float
    invariants: dict[str, float]
    is_plane_stress: bool
    plane_stress: Optional[dict[str, Any]] = None
    rotated_plane_stress: Optional[dict[str, Any]] = None
    meta: dict[str, Any] = field(default_factory=dict)


class StressMath:
    @staticmethod
    def make_tensor(inputs: StressTensorInput) -> np.ndarray:
        return np.array(
            [
                [inputs.sxx, inputs.txy, inputs.txz],
                [inputs.txy, inputs.syy, inputs.tyz],
                [inputs.txz, inputs.tyz, inputs.szz],
            ],
            dtype=float,
        )

    @staticmethod
    def compute_invariants(stress: np.ndarray) -> dict[str, float]:
        i1 = float(np.trace(stress))
        i2 = float(
            stress[0, 0] * stress[1, 1]
            + stress[1, 1] * stress[2, 2]
            + stress[2, 2] * stress[0, 0]
            - stress[0, 1] ** 2
            - stress[1, 2] ** 2
            - stress[0, 2] ** 2
        )
        i3 = float(np.linalg.det(stress))
        return {"I1": i1, "I2": i2, "I3": i3}

    @staticmethod
    def compute_von_mises(stress: np.ndarray) -> float:
        sxx, syy, szz = stress[0, 0], stress[1, 1], stress[2, 2]
        txy, tyz, txz = stress[0, 1], stress[1, 2], stress[0, 2]
        vm = math.sqrt(
            0.5
            * (
                (sxx - syy) ** 2
                + (syy - szz) ** 2
                + (szz - sxx) ** 2
                + 6.0 * (txy**2 + tyz**2 + txz**2)
            )
        )
        return float(vm)

    @staticmethod
    def principal_stresses(stress: np.ndarray) -> np.ndarray:
        eigenvalues, _ = np.linalg.eigh(stress)
        return np.sort(eigenvalues)[::-1]

    @staticmethod
    def is_plane_stress_case(stress: np.ndarray, tol: float = 1e-12) -> bool:
        return (
            abs(stress[2, 2]) <= tol
            and abs(stress[1, 2]) <= tol
            and abs(stress[0, 2]) <= tol
        )

    @staticmethod
    def analyze_plane_stress(stress: np.ndarray) -> PlaneStressResults:
        sxx = float(stress[0, 0])
        syy = float(stress[1, 1])
        txy = float(stress[0, 1])

        sigma_avg = 0.5 * (sxx + syy)
        radius = math.sqrt((0.5 * (sxx - syy)) ** 2 + txy**2)
        sigma1 = sigma_avg + radius
        sigma2 = sigma_avg - radius
        tau_max = radius

        theta_p_rad = 0.5 * math.atan2(2.0 * txy, sxx - syy)
        theta_s_rad = theta_p_rad + math.pi / 4.0

        point_x = (sxx, -txy)
        point_y = (syy, txy)

        return PlaneStressResults(
            sigma_avg=sigma_avg,
            radius=radius,
            sigma1=sigma1,
            sigma2=sigma2,
            tau_max_in_plane=tau_max,
            theta_p_deg_ccw=math.degrees(theta_p_rad),
            theta_s_deg_ccw=math.degrees(theta_s_rad),
            point_x=point_x,
            point_y=point_y,
        )

    @staticmethod
    def analyze_rotated_plane_stress(stress: np.ndarray, phi_deg_ccw: float) -> RotatedPlaneStressResults:
        sxx = float(stress[0, 0])
        syy = float(stress[1, 1])
        txy = float(stress[0, 1])

        phi_rad = math.radians(phi_deg_ccw)
        c2 = math.cos(2.0 * phi_rad)
        s2 = math.sin(2.0 * phi_rad)
        avg = 0.5 * (sxx + syy)
        half_diff = 0.5 * (sxx - syy)

        sigma_x_prime = avg + half_diff * c2 + txy * s2
        sigma_y_prime = avg - half_diff * c2 - txy * s2
        tau_x_prime_y_prime = -half_diff * s2 + txy * c2

        point_x_prime = (sigma_x_prime, -tau_x_prime_y_prime)
        point_y_prime = (sigma_y_prime, tau_x_prime_y_prime)

        return RotatedPlaneStressResults(
            phi_deg_ccw=phi_deg_ccw,
            sigma_x_prime=sigma_x_prime,
            sigma_y_prime=sigma_y_prime,
            tau_x_prime_y_prime=tau_x_prime_y_prime,
            point_x_prime=point_x_prime,
            point_y_prime=point_y_prime,
        )


class StressSolverBase:
    solve_path = "base"

    def solve(self, inputs: StressTensorInput) -> StressAnalysisResult:
        raise NotImplementedError


class General3DStressSolver(StressSolverBase):
    solve_path = "general_3d_stress"

    def solve(self, inputs: StressTensorInput) -> StressAnalysisResult:
        stress = StressMath.make_tensor(inputs)
        principal = StressMath.principal_stresses(stress)
        sigma1, _, sigma3 = principal
        invariants = StressMath.compute_invariants(stress)
        is_plane = StressMath.is_plane_stress_case(stress)
        plane = StressMath.analyze_plane_stress(stress) if is_plane else None
        rotated = None
        if inputs.phi_deg is not None:
            if not is_plane:
                raise ValueError("--phi-deg is only supported for plane-stress states in this release.")
            rotated = StressMath.analyze_rotated_plane_stress(stress, inputs.phi_deg)

        return StressAnalysisResult(
            problem="load_stress",
            solve_path=self.solve_path,
            title=inputs.title or "General three-dimensional stress analysis",
            inputs={
                "sxx": inputs.sxx,
                "syy": inputs.syy,
                "szz": inputs.szz,
                "txy": inputs.txy,
                "tyz": inputs.tyz,
                "txz": inputs.txz,
                "unit": inputs.unit,
                "phi_deg": inputs.phi_deg,
            },
            tensor=stress.tolist(),
            principal_stresses=[float(x) for x in principal],
            mean_stress=float(np.mean(principal)),
            max_shear_tresca=float((sigma1 - sigma3) / 2.0),
            von_mises=StressMath.compute_von_mises(stress),
            invariants=invariants,
            is_plane_stress=bool(is_plane),
            plane_stress=(
                {
                    "sigma_avg": plane.sigma_avg,
                    "radius": plane.radius,
                    "sigma1": plane.sigma1,
                    "sigma2": plane.sigma2,
                    "tau_max_in_plane": plane.tau_max_in_plane,
                    "theta_p_deg_ccw": plane.theta_p_deg_ccw,
                    "theta_s_deg_ccw": plane.theta_s_deg_ccw,
                    "point_x": list(plane.point_x),
                    "point_y": list(plane.point_y),
                }
                if plane is not None
                else None
            ),
            rotated_plane_stress=(
                {
                    "phi_deg_ccw": rotated.phi_deg_ccw,
                    "sigma_x_prime": rotated.sigma_x_prime,
                    "sigma_y_prime": rotated.sigma_y_prime,
                    "tau_x_prime_y_prime": rotated.tau_x_prime_y_prime,
                    "point_x_prime": list(rotated.point_x_prime),
                    "point_y_prime": list(rotated.point_y_prime),
                }
                if rotated is not None
                else None
            ),
            meta={
                "applicability": "General symmetric 3D stress tensor analysis with optional plane-stress rotation.",
                "notes": [
                    "Positive tension sign convention for normal stress.",
                    "Tensor is assumed symmetric.",
                    "For some Shigley plane-stress examples, clockwise tau_xy may be entered as negative under the standard tensor convention.",
                ],
            },
        )


class PlaneStressRotationSolver(StressSolverBase):
    solve_path = "plane_stress_rotation"

    def solve(self, inputs: StressTensorInput) -> StressAnalysisResult:
        if inputs.phi_deg is None:
            raise ValueError("plane_stress_rotation requires --phi-deg.")
        return General3DStressSolver().solve(inputs)
