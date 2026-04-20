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
class RosetteInput:
    ea: float
    eb: float
    ec: float
    theta_a_deg: float
    theta_b_deg: float
    theta_c_deg: float
    unit: str = ""
    title: str = ""
    E: Optional[float] = None
    nu: Optional[float] = None
    G: Optional[float] = None
    stress_unit: str = ""
    phi_deg: Optional[float] = None


@dataclass
class Hooke3DFromStrainInput:
    exx: float
    eyy: float
    ezz: float
    gxy: float = 0.0
    gyz: float = 0.0
    gxz: float = 0.0
    E: float = 0.0
    nu: Optional[float] = None
    G: Optional[float] = None
    unit: str = ""
    stress_unit: str = ""
    title: str = ""


@dataclass
class SingleGaugePlaneStressInput:
    epsilon_theta: float
    theta_deg: float
    sigma_x_known: float
    E: float
    nu: Optional[float] = None
    G: Optional[float] = None
    unit: str = ""
    stress_unit: str = ""
    title: str = ""
    phi_deg: Optional[float] = None


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
    source_strains: Optional[dict[str, Any]] = None
    stress_components: Optional[dict[str, float]] = None
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
    rosette: Optional[dict[str, Any]] = None
    recovered_plane_stress: Optional[dict[str, Any]] = None
    meta: dict[str, Any] = field(default_factory=dict)


SolverInput = Union[StressTensorInput, StrainTensorInput, RosetteInput, Hooke3DFromStrainInput, SingleGaugePlaneStressInput]
SolverResult = Union[StressAnalysisResult, StrainAnalysisResult]


def _normalize_angle_ccw_0_180(angle_deg: float) -> float:
    angle = angle_deg % 180.0
    if angle < 0.0:
        angle += 180.0
    return angle


def _cw_equivalent_from_ccw_line(angle_deg: float) -> float:
    ccw_0_180 = _normalize_angle_ccw_0_180(angle_deg)
    cw = (180.0 - ccw_0_180) % 180.0
    if abs(cw - 180.0) <= 1e-12:
        cw = 0.0
    return cw


def _smallest_cw_angle_from_x(angle_deg: float) -> float:
    return _cw_equivalent_from_ccw_line(angle_deg)


def _resolve_isotropic_constants(E: float, nu: Optional[float], G: Optional[float]) -> tuple[float, float, float]:
    if E <= 0.0:
        raise ValueError('E must be positive.')
    if nu is None and G is None:
        raise ValueError('Provide nu, G, or both for isotropic Hooke-law calculations.')
    if nu is None:
        nu = E / (2.0 * G) - 1.0
    if G is None:
        G = E / (2.0 * (1.0 + nu))
    if abs(G - E / (2.0 * (1.0 + nu))) > max(1e-9, 1e-9 * abs(G)):
        raise ValueError('Provided E, nu, and G are inconsistent for an isotropic material.')
    return float(E), float(nu), float(G)


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
        return abs(stress[2, 2]) <= tol and abs(stress[1, 2]) <= tol and abs(stress[0, 2]) <= tol

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
        return abs(strain_tensor[2, 2]) <= tol and abs(strain_tensor[1, 2]) <= tol and abs(strain_tensor[0, 2]) <= tol

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

    @staticmethod
    def strain_at_angle(exx: float, eyy: float, gxy: float, theta_deg: float) -> float:
        theta = math.radians(theta_deg)
        c = math.cos(theta)
        s = math.sin(theta)
        return exx * c * c + eyy * s * s + gxy * s * c

    @staticmethod
    def make_in_plane_tensor(exx: float, eyy: float, gxy: float) -> np.ndarray:
        return np.array(
            [
                [exx, 0.5 * gxy, 0.0],
                [0.5 * gxy, eyy, 0.0],
                [0.0, 0.0, 0.0],
            ],
            dtype=float,
        )


class HookeMath:
    @staticmethod
    def plane_stress_from_strain(exx: float, eyy: float, gxy: float, *, E: float, nu: Optional[float], G: Optional[float]) -> dict[str, float]:
        E, nu, G = _resolve_isotropic_constants(E, nu, G)
        coeff = E / (1.0 - nu**2)
        sxx = coeff * (exx + nu * eyy)
        syy = coeff * (eyy + nu * exx)
        txy = G * gxy
        ezz = -(nu / E) * (sxx + syy)
        stress = np.array([[sxx, txy, 0.0], [txy, syy, 0.0], [0.0, 0.0, 0.0]], dtype=float)
        principal = StressMath.principal_stresses(stress)
        plane = StressMath.analyze_plane_stress(stress)
        sigma_sorted = np.sort(np.array([principal[0], 0.0, principal[-1]], dtype=float))[::-1]
        tau_abs = 0.5 * (sigma_sorted[0] - sigma_sorted[-1])
        return {
            'E': E, 'nu': nu, 'G': G,
            'sigma_x': float(sxx), 'sigma_y': float(syy), 'sigma_z': 0.0, 'tau_xy': float(txy), 'tau_yz': 0.0, 'tau_xz': 0.0,
            'epsilon_z_plane_stress': float(ezz),
            'sigma1': float(principal[0]), 'sigma2': float(principal[1]), 'sigma3': float(principal[2]),
            'tau_max_in_plane': float(plane.tau_max_in_plane),
            'tau_abs_max_3d': float(tau_abs),
            'theta_p_deg_ccw': float(plane.theta_p_deg_ccw),
            'theta_s_deg_ccw': float(plane.theta_s_deg_ccw),
        }

    @staticmethod
    def stress_from_strain_tensor(strain_tensor: np.ndarray, *, E: float, nu: Optional[float], G: Optional[float]) -> np.ndarray:
        E, nu, G = _resolve_isotropic_constants(E, nu, G)
        lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
        return 2.0 * G * strain_tensor + lam * float(np.trace(strain_tensor)) * np.eye(3)


class RosetteMath:
    @staticmethod
    def solve_general(ea: float, eb: float, ec: float, theta_a_deg: float, theta_b_deg: float, theta_c_deg: float) -> dict[str, Any]:
        thetas = [theta_a_deg, theta_b_deg, theta_c_deg]
        meas = np.array([ea, eb, ec], dtype=float)
        rows = []
        for theta_deg in thetas:
            th = math.radians(theta_deg)
            c = math.cos(th)
            s = math.sin(th)
            rows.append([c * c, s * s, s * c])
        A = np.array(rows, dtype=float)
        exx, eyy, gxy = np.linalg.solve(A, meas)
        back = A @ np.array([exx, eyy, gxy], dtype=float)
        residual = back - meas
        return {
            'exx': float(exx), 'eyy': float(eyy), 'gxy': float(gxy),
            'measurement_matrix': A.tolist(),
            'back_calculated': back.tolist(),
            'residuals': residual.tolist(),
        }


class SolverBase:
    solve_path = 'base'

    def solve(self, inputs: SolverInput) -> SolverResult:
        raise NotImplementedError


def _build_strain_result(
    *,
    solve_path: str,
    title: str,
    inputs_dict: dict[str, Any],
    strain_tensor: np.ndarray,
    unit: str,
    phi_deg: Optional[float],
    meta_notes: list[str],
    rosette: Optional[dict[str, Any]] = None,
    recovered_plane_stress: Optional[dict[str, Any]] = None,
    in_plane_tensor: Optional[np.ndarray] = None,
) -> StrainAnalysisResult:
    principal = StrainMath.principal_strains(strain_tensor)
    e1, _, e3 = principal
    invariants = StrainMath.compute_invariants(strain_tensor)
    is_plane = StrainMath.is_plane_strain_case(strain_tensor)

    plane_source = in_plane_tensor if in_plane_tensor is not None else (strain_tensor if is_plane else None)
    plane = StrainMath.analyze_plane_strain(plane_source) if plane_source is not None else None
    rotated = None
    if phi_deg is not None:
        if plane_source is None:
            raise ValueError('--phi-deg is only supported for in-plane strain states in this release.')
        rotated = StrainMath.analyze_rotated_plane_strain(plane_source, phi_deg)

    gamma_abs_max_3d = float(e1 - e3)
    gamma_abs_max_tensor_3d = float(0.5 * (e1 - e3))

    plane_payload = None
    if plane is not None:
        plane_payload = {
            'epsilon_avg': plane.epsilon_avg,
            'radius': plane.radius,
            'epsilon1': plane.epsilon1,
            'epsilon2': plane.epsilon2,
            'gamma_max_in_plane': plane.gamma_max_in_plane,
            'gamma_max_in_plane_over_2': plane.gamma_max_in_plane / 2.0,
            'gamma_abs_max_3d': gamma_abs_max_3d,
            'gamma_abs_max_3d_over_2': gamma_abs_max_tensor_3d,
            'abs_max_equals_in_plane': bool(abs(gamma_abs_max_3d - plane.gamma_max_in_plane) <= 1e-12),
            'theta_p_deg_ccw': plane.theta_p_deg_ccw,
            'theta_s_deg_ccw': plane.theta_s_deg_ccw,
            'theta_epsilon1_deg_ccw': plane.theta_epsilon1_deg_ccw,
            'theta_epsilon2_deg_ccw': plane.theta_epsilon2_deg_ccw,
            'theta_epsilon1_deg_cw': plane.theta_epsilon1_deg_cw,
            'theta_epsilon2_deg_cw': plane.theta_epsilon2_deg_cw,
            'point_x': list(plane.point_x),
            'point_y': list(plane.point_y),
        }

    rotated_payload = None
    if rotated is not None:
        rotated_payload = {
            'phi_deg_ccw': rotated.phi_deg_ccw,
            'epsilon_x_prime': rotated.epsilon_x_prime,
            'epsilon_y_prime': rotated.epsilon_y_prime,
            'gamma_x_prime_y_prime': rotated.gamma_x_prime_y_prime,
            'gamma_x_prime_y_prime_over_2': rotated.gamma_x_prime_y_prime_over_2,
            'point_x_prime': list(rotated.point_x_prime),
            'point_y_prime': list(rotated.point_y_prime),
        }

    return StrainAnalysisResult(
        problem='load_stress',
        solve_path=solve_path,
        title=title,
        analysis_type='strain',
        inputs=inputs_dict,
        tensor=strain_tensor.tolist(),
        principal_strains=[float(x) for x in principal],
        mean_strain=float(np.mean(principal)),
        max_tensor_shear_strain_3d=gamma_abs_max_tensor_3d,
        max_engineering_shear_strain_3d=gamma_abs_max_3d,
        invariants=invariants,
        is_plane_strain=bool(is_plane),
        plane_strain=plane_payload,
        rotated_plane_strain=rotated_payload,
        rosette=rosette,
        recovered_plane_stress=recovered_plane_stress,
        meta={
            'applicability': 'General symmetric 3D/in-plane strain analysis using engineering shear strain inputs and γ/2 for Mohr-circle plotting.',
            'notes': meta_notes,
        },
    )


class General3DStressSolver(SolverBase):
    solve_path = 'general_3d_stress'

    def solve(self, inputs: SolverInput) -> StressAnalysisResult:
        if not isinstance(inputs, StressTensorInput):
            raise TypeError('general_3d_stress requires StressTensorInput.')
        stress = StressMath.make_tensor(inputs)
        principal = StressMath.principal_stresses(stress)
        sigma1, _, sigma3 = principal
        invariants = StressMath.compute_invariants(stress)
        is_plane = StressMath.is_plane_stress_case(stress)
        plane = StressMath.analyze_plane_stress(stress) if is_plane else None
        rotated = None
        if inputs.phi_deg is not None:
            if not is_plane:
                raise ValueError('--phi-deg is only supported for plane-stress states in this release.')
            rotated = StressMath.analyze_rotated_plane_stress(stress, inputs.phi_deg)
        return StressAnalysisResult(
            problem='load_stress',
            solve_path=self.solve_path,
            title=inputs.title or 'General three-dimensional stress analysis',
            analysis_type='stress',
            inputs={'sxx': inputs.sxx, 'syy': inputs.syy, 'szz': inputs.szz, 'txy': inputs.txy, 'tyz': inputs.tyz, 'txz': inputs.txz, 'unit': inputs.unit, 'phi_deg': inputs.phi_deg},
            tensor=stress.tolist(),
            principal_stresses=[float(x) for x in principal],
            mean_stress=float(np.mean(principal)),
            max_shear_tresca=float((sigma1 - sigma3) / 2.0),
            von_mises=StressMath.compute_von_mises(stress),
            invariants=invariants,
            is_plane_stress=bool(is_plane),
            plane_stress=({'sigma_avg': plane.sigma_avg, 'radius': plane.radius, 'sigma1': plane.sigma1, 'sigma2': plane.sigma2, 'tau_max_in_plane': plane.tau_max_in_plane, 'theta_p_deg_ccw': plane.theta_p_deg_ccw, 'theta_s_deg_ccw': plane.theta_s_deg_ccw, 'point_x': list(plane.point_x), 'point_y': list(plane.point_y)} if plane else None),
            rotated_plane_stress=({'phi_deg_ccw': rotated.phi_deg_ccw, 'sigma_x_prime': rotated.sigma_x_prime, 'sigma_y_prime': rotated.sigma_y_prime, 'tau_x_prime_y_prime': rotated.tau_x_prime_y_prime, 'point_x_prime': list(rotated.point_x_prime), 'point_y_prime': list(rotated.point_y_prime)} if rotated else None),
            stress_components={'sigma_x': float(stress[0, 0]), 'sigma_y': float(stress[1, 1]), 'sigma_z': float(stress[2, 2]), 'tau_xy': float(stress[0, 1]), 'tau_yz': float(stress[1, 2]), 'tau_xz': float(stress[0, 2])},
            meta={'applicability': 'General symmetric 3D stress tensor analysis with optional plane-stress rotation.', 'notes': ['Positive tension sign convention for normal stress.', 'Tensor is assumed symmetric.']},
        )


class PlaneStressRotationSolver(SolverBase):
    solve_path = 'plane_stress_rotation'

    def solve(self, inputs: SolverInput) -> StressAnalysisResult:
        if not isinstance(inputs, StressTensorInput):
            raise TypeError('plane_stress_rotation requires StressTensorInput.')
        if inputs.phi_deg is None:
            raise ValueError('plane_stress_rotation requires --phi-deg.')
        return General3DStressSolver().solve(inputs)


class General3DStrainSolver(SolverBase):
    solve_path = 'general_3d_strain'

    def solve(self, inputs: SolverInput) -> StrainAnalysisResult:
        if not isinstance(inputs, StrainTensorInput):
            raise TypeError('general_3d_strain requires StrainTensorInput.')
        strain_tensor = StrainMath.make_tensor(inputs)
        return _build_strain_result(
            solve_path=self.solve_path,
            title=inputs.title or 'General three-dimensional strain analysis',
            inputs_dict={'exx': inputs.exx, 'eyy': inputs.eyy, 'ezz': inputs.ezz, 'gxy': inputs.gxy, 'gyz': inputs.gyz, 'gxz': inputs.gxz, 'unit': inputs.unit, 'phi_deg': inputs.phi_deg},
            strain_tensor=strain_tensor,
            unit=inputs.unit,
            phi_deg=inputs.phi_deg,
            meta_notes=['User-facing shear inputs are engineering shear strains γxy, γyz, γxz.', 'Internal tensor off-diagonal entries use γ/2.', 'In-plane Mohr circle is plotted with γ/2 on the vertical axis to match common machine design textbook conventions.'],
            in_plane_tensor=(StrainMath.make_in_plane_tensor(inputs.exx, inputs.eyy, inputs.gxy) if abs(inputs.gyz) <= 1e-12 and abs(inputs.gxz) <= 1e-12 else None),
        )


class PlaneStrainRotationSolver(SolverBase):
    solve_path = 'plane_strain_rotation'

    def solve(self, inputs: SolverInput) -> StrainAnalysisResult:
        if not isinstance(inputs, StrainTensorInput):
            raise TypeError('plane_strain_rotation requires StrainTensorInput.')
        if inputs.phi_deg is None:
            raise ValueError('plane_strain_rotation requires --phi-deg.')
        return General3DStrainSolver().solve(inputs)


class StrainRosetteRectangularSolver(SolverBase):
    solve_path = 'strain_rosette_rectangular'

    def solve(self, inputs: SolverInput) -> StrainAnalysisResult:
        if not isinstance(inputs, RosetteInput):
            raise TypeError('strain_rosette_rectangular requires RosetteInput.')
        solved = RosetteMath.solve_general(inputs.ea, inputs.eb, inputs.ec, inputs.theta_a_deg, inputs.theta_b_deg, inputs.theta_c_deg)
        in_plane_tensor = StrainMath.make_in_plane_tensor(solved['exx'], solved['eyy'], solved['gxy'])
        ezz_effective = 0.0
        recovered = None
        notes = [
            'Three gage strains are inverted through the general rosette transformation equations εθ = εx cos²θ + εy sin²θ + γxy sinθ cosθ.',
            'The reconstructed in-plane strain state is then analyzed with the same Mohr-circle strain path used elsewhere in the app.',
        ]
        if inputs.nu is not None:
            ezz_effective = float(-(inputs.nu / (1.0 - inputs.nu)) * (solved['exx'] + solved['eyy']))
            notes.append('Because the rosette is bonded to a free surface, the strain state is interpreted as plane stress; εz is recovered from εz = -ν(εx + εy)/(1-ν) when ν is available.')
        else:
            notes.append('Without ν, εz cannot be recovered for the free-surface plane-stress case, so the out-of-plane strain is left at zero as a display fallback only.')
        if inputs.E is not None and (inputs.nu is not None or inputs.G is not None):
            recovered = HookeMath.plane_stress_from_strain(solved['exx'], solved['eyy'], solved['gxy'], E=inputs.E, nu=inputs.nu, G=inputs.G)
            recovered['stress_unit'] = inputs.stress_unit or ''
            recovered['stress_along_gages'] = [
                {'name': 'a', 'theta_deg': inputs.theta_a_deg, 'sigma_normal': StressMath.analyze_rotated_plane_stress(np.array([[recovered['sigma_x'], recovered['tau_xy'], 0.0], [recovered['tau_xy'], recovered['sigma_y'], 0.0], [0.0, 0.0, 0.0]], dtype=float), inputs.theta_a_deg).sigma_x_prime},
                {'name': 'b', 'theta_deg': inputs.theta_b_deg, 'sigma_normal': StressMath.analyze_rotated_plane_stress(np.array([[recovered['sigma_x'], recovered['tau_xy'], 0.0], [recovered['tau_xy'], recovered['sigma_y'], 0.0], [0.0, 0.0, 0.0]], dtype=float), inputs.theta_b_deg).sigma_x_prime},
                {'name': 'c', 'theta_deg': inputs.theta_c_deg, 'sigma_normal': StressMath.analyze_rotated_plane_stress(np.array([[recovered['sigma_x'], recovered['tau_xy'], 0.0], [recovered['tau_xy'], recovered['sigma_y'], 0.0], [0.0, 0.0, 0.0]], dtype=float), inputs.theta_c_deg).sigma_x_prime},
            ]
            ezz_effective = float(recovered['epsilon_z_plane_stress'])
            notes.append('When E and ν (or E and G) are supplied, plane-stress Hooke-law recovery is performed to obtain σx, σy, τxy, principal stresses, and maximum shear stresses on the free surface.')

        strain_tensor = StrainMath.make_tensor(StrainTensorInput(exx=solved['exx'], eyy=solved['eyy'], ezz=ezz_effective, gxy=solved['gxy'], unit=inputs.unit, phi_deg=inputs.phi_deg, title=inputs.title))
        rosette = {
            'rosette_type': 'rectangular',
            'gages': [
                {'name': 'a', 'theta_deg': inputs.theta_a_deg, 'strain': inputs.ea, 'back_calculated': solved['back_calculated'][0]},
                {'name': 'b', 'theta_deg': inputs.theta_b_deg, 'strain': inputs.eb, 'back_calculated': solved['back_calculated'][1]},
                {'name': 'c', 'theta_deg': inputs.theta_c_deg, 'strain': inputs.ec, 'back_calculated': solved['back_calculated'][2]},
            ],
            'measurement_matrix': solved['measurement_matrix'],
            'residuals': solved['residuals'],
            'reconstructed_exx': solved['exx'],
            'reconstructed_eyy': solved['eyy'],
            'reconstructed_gxy': solved['gxy'],
            'plane_stress_free_surface': bool(recovered is not None),
            'effective_ezz': ezz_effective,
        }
        return _build_strain_result(
            solve_path=self.solve_path,
            title=inputs.title or 'Rectangular strain rosette analysis',
            inputs_dict={'ea': inputs.ea, 'eb': inputs.eb, 'ec': inputs.ec, 'theta_a_deg': inputs.theta_a_deg, 'theta_b_deg': inputs.theta_b_deg, 'theta_c_deg': inputs.theta_c_deg, 'unit': inputs.unit, 'phi_deg': inputs.phi_deg, 'E': inputs.E, 'nu': inputs.nu, 'G': inputs.G, 'strain_unit': inputs.unit, 'stress_unit': inputs.stress_unit},
            strain_tensor=strain_tensor,
            unit=inputs.unit,
            phi_deg=inputs.phi_deg,
            meta_notes=notes,
            rosette=rosette,
            recovered_plane_stress=recovered,
            in_plane_tensor=in_plane_tensor,
        )


class StrainRosetteEquiangularSolver(StrainRosetteRectangularSolver):
    solve_path = 'strain_rosette_equiangular'

    def solve(self, inputs: SolverInput) -> StrainAnalysisResult:
        if not isinstance(inputs, RosetteInput):
            raise TypeError('strain_rosette_equiangular requires RosetteInput.')
        result = super().solve(inputs)
        result.solve_path = self.solve_path
        result.title = inputs.title or 'Equiangular strain rosette analysis'
        if result.rosette is not None:
            result.rosette['rosette_type'] = 'equiangular'
        return result


class StrainRosetteGeneralSolver(StrainRosetteRectangularSolver):
    solve_path = 'strain_rosette_general'

    def solve(self, inputs: SolverInput) -> StrainAnalysisResult:
        if not isinstance(inputs, RosetteInput):
            raise TypeError('strain_rosette_general requires RosetteInput.')
        result = super().solve(inputs)
        result.solve_path = self.solve_path
        result.title = inputs.title or 'General strain rosette analysis'
        if result.rosette is not None:
            result.rosette['rosette_type'] = 'general'
        return result


class Hooke3DFromStrainSolver(SolverBase):
    solve_path = 'hooke_3d_from_strain'

    def solve(self, inputs: SolverInput) -> StressAnalysisResult:
        if not isinstance(inputs, Hooke3DFromStrainInput):
            raise TypeError('hooke_3d_from_strain requires Hooke3DFromStrainInput.')
        strain_inputs = StrainTensorInput(exx=inputs.exx, eyy=inputs.eyy, ezz=inputs.ezz, gxy=inputs.gxy, gyz=inputs.gyz, gxz=inputs.gxz, unit=inputs.unit)
        strain_tensor = StrainMath.make_tensor(strain_inputs)
        E, nu, G = _resolve_isotropic_constants(inputs.E, inputs.nu, inputs.G)
        stress = HookeMath.stress_from_strain_tensor(strain_tensor, E=E, nu=nu, G=G)
        principal = StressMath.principal_stresses(stress)
        sigma1, _, sigma3 = principal
        invariants = StressMath.compute_invariants(stress)
        is_plane = StressMath.is_plane_stress_case(stress)
        plane = StressMath.analyze_plane_stress(stress) if is_plane else None
        return StressAnalysisResult(
            problem='load_stress',
            solve_path=self.solve_path,
            title=inputs.title or 'Generalized Hooke law: 3D stress from strain',
            analysis_type='stress',
            inputs={'exx': inputs.exx, 'eyy': inputs.eyy, 'ezz': inputs.ezz, 'gxy': inputs.gxy, 'gyz': inputs.gyz, 'gxz': inputs.gxz, 'E': E, 'nu': nu, 'G': G, 'unit': inputs.unit, 'strain_unit': inputs.unit, 'stress_unit': inputs.stress_unit},
            tensor=stress.tolist(),
            principal_stresses=[float(x) for x in principal],
            mean_stress=float(np.mean(principal)),
            max_shear_tresca=float((sigma1 - sigma3) / 2.0),
            von_mises=StressMath.compute_von_mises(stress),
            invariants=invariants,
            is_plane_stress=bool(is_plane),
            plane_stress=({'sigma_avg': plane.sigma_avg, 'radius': plane.radius, 'sigma1': plane.sigma1, 'sigma2': plane.sigma2, 'tau_max_in_plane': plane.tau_max_in_plane, 'theta_p_deg_ccw': plane.theta_p_deg_ccw, 'theta_s_deg_ccw': plane.theta_s_deg_ccw, 'point_x': list(plane.point_x), 'point_y': list(plane.point_y)} if plane else None),
            rotated_plane_stress=None,
            source_strains={'exx': inputs.exx, 'eyy': inputs.eyy, 'ezz': inputs.ezz, 'gxy': inputs.gxy, 'gyz': inputs.gyz, 'gxz': inputs.gxz, 'strain_unit': inputs.unit},
            stress_components={'sigma_x': float(stress[0, 0]), 'sigma_y': float(stress[1, 1]), 'sigma_z': float(stress[2, 2]), 'tau_xy': float(stress[0, 1]), 'tau_yz': float(stress[1, 2]), 'tau_xz': float(stress[0, 2])},
            meta={'applicability': 'Generalized Hooke law for isotropic materials in full 3D using σ = 2Gε + λ tr(ε) I.', 'notes': ['Provide E with ν or G. When both ν and G are supplied, consistency is checked.', 'Stress off-diagonal terms are recovered from τij = G γij.', 'For full 3D Hooke-law recovery, σx, σy, and σz remain the primary reported component stresses even when principal stresses are also listed as derived quantities.']},
        )


class SingleGaugeBiaxialPlaneStressSolver(SolverBase):
    solve_path = 'single_gauge_biaxial_plane_stress'

    def solve(self, inputs: SolverInput) -> StrainAnalysisResult:
        if not isinstance(inputs, SingleGaugePlaneStressInput):
            raise TypeError('single_gauge_biaxial_plane_stress requires SingleGaugePlaneStressInput.')
        E, nu, G = _resolve_isotropic_constants(inputs.E, inputs.nu, inputs.G)
        th = math.radians(inputs.theta_deg)
        c2 = math.cos(th) ** 2
        s2 = math.sin(th) ** 2
        denom = s2 - nu * c2
        if abs(denom) <= 1e-14:
            raise ValueError('Single-gage inversion is singular for the supplied angle/material constants.')
        sigma_y = (E * inputs.epsilon_theta - inputs.sigma_x_known * (c2 - nu * s2)) / denom
        exx = (inputs.sigma_x_known - nu * sigma_y) / E
        eyy = (sigma_y - nu * inputs.sigma_x_known) / E
        recovered = HookeMath.plane_stress_from_strain(exx, eyy, 0.0, E=E, nu=nu, G=G)
        recovered['stress_unit'] = inputs.stress_unit or ''
        recovered['known_sigma_x'] = inputs.sigma_x_known
        recovered['stress_along_gages'] = [
            {'name': 'measurement_axis', 'theta_deg': inputs.theta_deg, 'sigma_normal': StressMath.analyze_rotated_plane_stress(np.array([[recovered['sigma_x'], 0.0, 0.0], [0.0, recovered['sigma_y'], 0.0], [0.0, 0.0, 0.0]], dtype=float), inputs.theta_deg).sigma_x_prime}
        ]
        ezz_effective = float(recovered['epsilon_z_plane_stress'])
        strain_tensor = StrainMath.make_tensor(StrainTensorInput(exx=exx, eyy=eyy, ezz=ezz_effective, gxy=0.0, unit=inputs.unit, phi_deg=inputs.phi_deg, title=inputs.title))
        in_plane_tensor = StrainMath.make_in_plane_tensor(exx, eyy, 0.0)
        return _build_strain_result(
            solve_path=self.solve_path,
            title=inputs.title or 'Single-gage biaxial plane-stress analysis',
            inputs_dict={'epsilon_theta': inputs.epsilon_theta, 'theta_deg': inputs.theta_deg, 'sigma_x_known': inputs.sigma_x_known, 'E': E, 'nu': nu, 'G': G, 'unit': inputs.unit, 'stress_unit': inputs.stress_unit, 'phi_deg': inputs.phi_deg},
            strain_tensor=strain_tensor,
            unit=inputs.unit,
            phi_deg=inputs.phi_deg,
            meta_notes=['A single measured normal strain at angle θ is combined with a known σx under the assumptions of biaxial plane stress and τxy = 0.', 'Because the measurement is on a free surface, εz is recovered from plane-stress Hooke-law relations instead of being assumed zero.', 'The missing σy is solved from the strain-transformation equation and isotropic plane-stress Hooke-law relations.'],
            rosette={'rosette_type': 'single_gauge', 'gages': [{'name': 'measurement_axis', 'theta_deg': inputs.theta_deg, 'strain': inputs.epsilon_theta}], 'plane_stress_free_surface': True, 'effective_ezz': ezz_effective},
            recovered_plane_stress=recovered,
            in_plane_tensor=in_plane_tensor,
        )
