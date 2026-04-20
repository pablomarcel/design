from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional, Union

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
class StrainTensorInput:
    exx: float
    eyy: float
    ezz: float
    gxy: float = 0.0
    gyz: float = 0.0
    gxz: float = 0.0
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
class PlaneStrainResults:
    epsilon_avg: float
    radius: float
    epsilon1: float
    epsilon2: float
    gamma_max_in_plane: float
    theta_p_deg_ccw: float
    theta_s_deg_ccw: float
    theta_epsilon1_deg_ccw: float
    theta_epsilon2_deg_ccw: float
    theta_epsilon1_deg_cw: float
    theta_epsilon2_deg_cw: float
    point_x: tuple[float, float]
    point_y: tuple[float, float]


@dataclass
class RotatedPlaneStrainResults:
    phi_deg_ccw: float
    epsilon_x_prime: float
    epsilon_y_prime: float
    gamma_x_prime_y_prime: float
    gamma_x_prime_y_prime_over_2: float
    point_x_prime: tuple[float, float]
    point_y_prime: tuple[float, float]


@dataclass
class StressAnalysisResult:
    problem: str
    solve_path: str
    title: str
    analysis_type: str
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


@dataclass
class StrainAnalysisResult:
    problem: str
    solve_path: str
    title: str
    analysis_type: str
    inputs: dict[str, Any]
    tensor: list[list[float]]
    principal_strains: list[float]
    mean_strain: float
    max_tensor_shear_strain_3d: float
    max_engineering_shear_strain_3d: float
    invariants: dict[str, float]
    is_plane_strain: bool
    plane_strain: Optional[dict[str, Any]] = None
    rotated_plane_strain: Optional[dict[str, Any]] = None
    meta: dict[str, Any] = field(default_factory=dict)


SolverInput = Union[StressTensorInput, StrainTensorInput]
SolverResult = Union[StressAnalysisResult, StrainAnalysisResult]


def _normalize_angle_ccw_0_180(angle_deg: float) -> float:
    angle = angle_deg % 180.0
    if angle < 0.0:
        angle += 180.0
    return angle


def _smallest_cw_angle_from_x(angle_deg: float) -> float:
    ccw_0_180 = _normalize_angle_ccw_0_180(angle_deg)
    return min(ccw_0_180, 180.0 - ccw_0_180)


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


class StrainMath:
    @staticmethod
    def make_tensor(inputs: StrainTensorInput) -> np.ndarray:
        return np.array(
            [
                [inputs.exx, 0.5 * inputs.gxy, 0.5 * inputs.gxz],
                [0.5 * inputs.gxy, inputs.eyy, 0.5 * inputs.gyz],
                [0.5 * inputs.gxz, 0.5 * inputs.gyz, inputs.ezz],
            ],
            dtype=float,
        )

    @staticmethod
    def compute_invariants(strain_tensor: np.ndarray) -> dict[str, float]:
        i1 = float(np.trace(strain_tensor))
        i2 = float(
            strain_tensor[0, 0] * strain_tensor[1, 1]
            + strain_tensor[1, 1] * strain_tensor[2, 2]
            + strain_tensor[2, 2] * strain_tensor[0, 0]
            - strain_tensor[0, 1] ** 2
            - strain_tensor[1, 2] ** 2
            - strain_tensor[0, 2] ** 2
        )
        i3 = float(np.linalg.det(strain_tensor))
        return {"I1": i1, "I2": i2, "I3": i3}

    @staticmethod
    def principal_strains(strain_tensor: np.ndarray) -> np.ndarray:
        eigenvalues, _ = np.linalg.eigh(strain_tensor)
        return np.sort(eigenvalues)[::-1]

    @staticmethod
    def is_plane_strain_case(strain_tensor: np.ndarray, tol: float = 1e-12) -> bool:
        return (
            abs(strain_tensor[2, 2]) <= tol
            and abs(strain_tensor[1, 2]) <= tol
            and abs(strain_tensor[0, 2]) <= tol
        )

    @staticmethod
    def analyze_plane_strain(strain_tensor: np.ndarray) -> PlaneStrainResults:
        exx = float(strain_tensor[0, 0])
        eyy = float(strain_tensor[1, 1])
        gxy_over_2 = float(strain_tensor[0, 1])

        epsilon_avg = 0.5 * (exx + eyy)
        radius = math.sqrt((0.5 * (exx - eyy)) ** 2 + gxy_over_2**2)
        epsilon1 = epsilon_avg + radius
        epsilon2 = epsilon_avg - radius
        gamma_max_in_plane = 2.0 * radius

        theta_p_rad = 0.5 * math.atan2(2.0 * gxy_over_2, exx - eyy)
        theta_s_rad = theta_p_rad + math.pi / 4.0
        theta_p_deg = math.degrees(theta_p_rad)
        theta_e1_ccw = _normalize_angle_ccw_0_180(theta_p_deg)
        theta_e2_ccw = _normalize_angle_ccw_0_180(theta_p_deg + 90.0)

        point_x = (exx, -gxy_over_2)
        point_y = (eyy, gxy_over_2)

        return PlaneStrainResults(
            epsilon_avg=epsilon_avg,
            radius=radius,
            epsilon1=epsilon1,
            epsilon2=epsilon2,
            gamma_max_in_plane=gamma_max_in_plane,
            theta_p_deg_ccw=theta_p_deg,
            theta_s_deg_ccw=math.degrees(theta_s_rad),
            theta_epsilon1_deg_ccw=theta_e1_ccw,
            theta_epsilon2_deg_ccw=theta_e2_ccw,
            theta_epsilon1_deg_cw=_smallest_cw_angle_from_x(theta_e1_ccw),
            theta_epsilon2_deg_cw=_smallest_cw_angle_from_x(theta_e2_ccw),
            point_x=point_x,
            point_y=point_y,
        )

    @staticmethod
    def analyze_rotated_plane_strain(strain_tensor: np.ndarray, phi_deg_ccw: float) -> RotatedPlaneStrainResults:
        exx = float(strain_tensor[0, 0])
        eyy = float(strain_tensor[1, 1])
        gxy_over_2 = float(strain_tensor[0, 1])

        phi_rad = math.radians(phi_deg_ccw)
        c2 = math.cos(2.0 * phi_rad)
        s2 = math.sin(2.0 * phi_rad)
        avg = 0.5 * (exx + eyy)
        half_diff = 0.5 * (exx - eyy)

        epsilon_x_prime = avg + half_diff * c2 + gxy_over_2 * s2
        epsilon_y_prime = avg - half_diff * c2 - gxy_over_2 * s2
        gamma_x_prime_y_prime_over_2 = -half_diff * s2 + gxy_over_2 * c2
        gamma_x_prime_y_prime = 2.0 * gamma_x_prime_y_prime_over_2

        point_x_prime = (epsilon_x_prime, -gamma_x_prime_y_prime_over_2)
        point_y_prime = (epsilon_y_prime, gamma_x_prime_y_prime_over_2)

        return RotatedPlaneStrainResults(
            phi_deg_ccw=phi_deg_ccw,
            epsilon_x_prime=epsilon_x_prime,
            epsilon_y_prime=epsilon_y_prime,
            gamma_x_prime_y_prime=gamma_x_prime_y_prime,
            gamma_x_prime_y_prime_over_2=gamma_x_prime_y_prime_over_2,
            point_x_prime=point_x_prime,
            point_y_prime=point_y_prime,
        )


class SolverBase:
    solve_path = "base"

    def solve(self, inputs: SolverInput) -> SolverResult:
        raise NotImplementedError


class General3DStressSolver(SolverBase):
    solve_path = "general_3d_stress"

    def solve(self, inputs: SolverInput) -> StressAnalysisResult:
        if not isinstance(inputs, StressTensorInput):
            raise TypeError("general_3d_stress requires StressTensorInput.")
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
            analysis_type="stress",
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


class PlaneStressRotationSolver(SolverBase):
    solve_path = "plane_stress_rotation"

    def solve(self, inputs: SolverInput) -> StressAnalysisResult:
        if not isinstance(inputs, StressTensorInput):
            raise TypeError("plane_stress_rotation requires StressTensorInput.")
        if inputs.phi_deg is None:
            raise ValueError("plane_stress_rotation requires --phi-deg.")
        return General3DStressSolver().solve(inputs)


class General3DStrainSolver(SolverBase):
    solve_path = "general_3d_strain"

    def solve(self, inputs: SolverInput) -> StrainAnalysisResult:
        if not isinstance(inputs, StrainTensorInput):
            raise TypeError("general_3d_strain requires StrainTensorInput.")
        strain_tensor = StrainMath.make_tensor(inputs)
        principal = StrainMath.principal_strains(strain_tensor)
        e1, _, e3 = principal
        invariants = StrainMath.compute_invariants(strain_tensor)
        is_plane = StrainMath.is_plane_strain_case(strain_tensor)
        plane = StrainMath.analyze_plane_strain(strain_tensor) if is_plane else None
        rotated = None
        if inputs.phi_deg is not None:
            if not is_plane:
                raise ValueError("--phi-deg is only supported for plane-strain states in this release.")
            rotated = StrainMath.analyze_rotated_plane_strain(strain_tensor, inputs.phi_deg)

        gamma_abs_max_3d = float(e1 - e3)
        gamma_abs_max_tensor_3d = float(0.5 * (e1 - e3))

        plane_payload = None
        if plane is not None:
            plane_payload = {
                "epsilon_avg": plane.epsilon_avg,
                "radius": plane.radius,
                "epsilon1": plane.epsilon1,
                "epsilon2": plane.epsilon2,
                "gamma_max_in_plane": plane.gamma_max_in_plane,
                "gamma_max_in_plane_over_2": plane.gamma_max_in_plane / 2.0,
                "gamma_abs_max_3d": gamma_abs_max_3d,
                "gamma_abs_max_3d_over_2": gamma_abs_max_tensor_3d,
                "abs_max_equals_in_plane": bool(abs(gamma_abs_max_3d - plane.gamma_max_in_plane) <= 1e-12),
                "theta_p_deg_ccw": plane.theta_p_deg_ccw,
                "theta_s_deg_ccw": plane.theta_s_deg_ccw,
                "theta_epsilon1_deg_ccw": plane.theta_epsilon1_deg_ccw,
                "theta_epsilon2_deg_ccw": plane.theta_epsilon2_deg_ccw,
                "theta_epsilon1_deg_cw": plane.theta_epsilon1_deg_cw,
                "theta_epsilon2_deg_cw": plane.theta_epsilon2_deg_cw,
                "point_x": list(plane.point_x),
                "point_y": list(plane.point_y),
            }

        rotated_payload = None
        if rotated is not None:
            rotated_payload = {
                "phi_deg_ccw": rotated.phi_deg_ccw,
                "epsilon_x_prime": rotated.epsilon_x_prime,
                "epsilon_y_prime": rotated.epsilon_y_prime,
                "gamma_x_prime_y_prime": rotated.gamma_x_prime_y_prime,
                "gamma_x_prime_y_prime_over_2": rotated.gamma_x_prime_y_prime_over_2,
                "point_x_prime": list(rotated.point_x_prime),
                "point_y_prime": list(rotated.point_y_prime),
            }

        return StrainAnalysisResult(
            problem="load_stress",
            solve_path=self.solve_path,
            title=inputs.title or "General three-dimensional strain analysis",
            analysis_type="strain",
            inputs={
                "exx": inputs.exx,
                "eyy": inputs.eyy,
                "ezz": inputs.ezz,
                "gxy": inputs.gxy,
                "gyz": inputs.gyz,
                "gxz": inputs.gxz,
                "unit": inputs.unit,
                "phi_deg": inputs.phi_deg,
            },
            tensor=strain_tensor.tolist(),
            principal_strains=[float(x) for x in principal],
            mean_strain=float(np.mean(principal)),
            max_tensor_shear_strain_3d=gamma_abs_max_tensor_3d,
            max_engineering_shear_strain_3d=gamma_abs_max_3d,
            invariants=invariants,
            is_plane_strain=bool(is_plane),
            plane_strain=plane_payload,
            rotated_plane_strain=rotated_payload,
            meta={
                "applicability": "General symmetric 3D strain tensor analysis using engineering shear strain inputs and γ/2 for plane-strain Mohr-circle plotting.",
                "notes": [
                    "User-facing shear inputs are engineering shear strains γxy, γyz, γxz.",
                    "Internal tensor off-diagonal entries use γ/2.",
                    "Plane-strain Mohr circle is plotted with γ/2 on the vertical axis to match common machine design textbook conventions.",
                    "Plane-strain results now report both principal-direction angles and absolute-vs-in-plane maximum shear strain quantities.",
                ],
            },
        )


class PlaneStrainRotationSolver(SolverBase):
    solve_path = "plane_strain_rotation"

    def solve(self, inputs: SolverInput) -> StrainAnalysisResult:
        if not isinstance(inputs, StrainTensorInput):
            raise TypeError("plane_strain_rotation requires StrainTensorInput.")
        if inputs.phi_deg is None:
            raise ValueError("plane_strain_rotation requires --phi-deg.")
        return General3DStrainSolver().solve(inputs)
