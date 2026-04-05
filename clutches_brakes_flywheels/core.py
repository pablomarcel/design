from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from utils import ValidationError, deg_to_rad, ensure


@dataclass
class SolveResult:
    problem_type: str
    title: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    derived: Dict[str, Any]
    notes: list[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_type": self.problem_type,
            "title": self.title,
            "inputs": self.inputs,
            "derived": self.derived,
            "outputs": self.outputs,
            "notes": self.notes,
        }


class SolverBase:
    problem_type: str = "base"
    title: str = "Base solver"

    def solve(self, payload: Dict[str, Any]) -> SolveResult:
        raise NotImplementedError


class DoorstopSolver(SolverBase):
    problem_type = "doorstop"
    title = "Doorstop / hinged friction pad"

    def solve(self, payload: Dict[str, Any]) -> SolveResult:
        F = float(payload["F"])
        a = float(payload["a"])
        b = float(payload["b"])
        c = float(payload["c"])
        w1 = float(payload["w1"])
        w2 = float(payload["w2"])
        mu = float(payload["mu"])
        pressure_model = payload.get("pressure_model", "uniform")
        motion = payload.get("motion", "leftward")

        ensure(F > 0 and a > 0 and b > 0 and c >= 0 and w1 > 0 and w2 > 0, "All geometry values and F must be positive.")
        ensure(mu >= 0, "mu must be nonnegative.")
        ensure(pressure_model in {"uniform", "linear"}, "pressure_model must be 'uniform' or 'linear'.")
        ensure(motion in {"leftward", "rightward"}, "motion must be 'leftward' or 'rightward'.")

        sign = 1.0 if motion == "leftward" else -1.0
        notes: list[str] = []
        derived: Dict[str, Any] = {}

        if pressure_model == "uniform":
            denom = (w2 / b) * (c + 0.5 * w1 + sign * a * mu)
            ensure(abs(denom) > 1e-12, "Doorstop moment denominator is zero; self-locking singular case.")
            p_avg = F / denom
            p_max = p_avg
            u_bar = 0.5 * w1
            critical_mu = (c + u_bar) / a
            derived["model_equations"] = {
                "p_avg": "F / [(w2/b)(c + w1/2 ± a*mu)]",
                "p_max": "p_avg",
            }
        else:
            normal_moment_coeff = c * c + c * w1 + (w1 * w1) / 3.0
            friction_moment_coeff = mu * a * (c + 0.5 * w1)
            denom = (w2 / b) * (normal_moment_coeff + sign * friction_moment_coeff)
            ensure(abs(denom) > 1e-12, "Doorstop moment denominator is zero; self-locking singular case.")
            C2 = F / denom
            p_avg = C2 * (c + 0.5 * w1)
            p_max = C2 * (c + w1)
            numerator = c * (w1 ** 2) / 2.0 + (w1 ** 3) / 3.0
            denominator = c * w1 + (w1 ** 2) / 2.0
            u_bar = numerator / denominator
            critical_mu = (c + u_bar) / a
            derived["pressure_distribution"] = "p(u) = C2 * (c + u)"
            derived["C2"] = C2
            derived["normal_moment_coefficient"] = normal_moment_coeff
            derived["friction_moment_coefficient"] = friction_moment_coeff

        pad_area = w1 * w2
        N = pad_area * p_avg
        friction_force = mu * N
        R_x = sign * friction_force
        R_y = F - N
        center_of_pressure_from_pivot_x = c + u_bar

        self_acting = mu >= critical_mu if motion == "rightward" else False
        if motion == "rightward":
            notes.append("Rightward motion is the potentially self-energizing / self-locking case in this geometry.")
            notes.append(f"Self-acting criterion: mu >= {critical_mu:.6f}.")
        else:
            notes.append("Leftward motion is the de-energizing case for this geometry.")

        outputs = {
            "p_avg": p_avg,
            "p_max": p_max,
            "R_x": R_x,
            "R_y": R_y,
            "normal_force_N": N,
            "friction_force": friction_force,
            "u_bar_from_right_edge": u_bar,
            "center_of_pressure_from_pivot_x": center_of_pressure_from_pivot_x,
            "critical_mu_for_self_acting": critical_mu,
            "is_self_acting": self_acting,
        }

        return SolveResult(
            problem_type=self.problem_type,
            title=self.title,
            inputs=payload,
            outputs=outputs,
            derived=derived,
            notes=notes,
        )


class InternalExpandingRimBrakeSolver(SolverBase):
    problem_type = "rim_brake"
    title = "Internal expanding rim brake / shoe brake"

    def solve(self, payload: Dict[str, Any]) -> SolveResult:
        raw_inputs = dict(payload)
        givens = dict(payload.get("givens", payload))
        paired_shoe = payload.get("paired_shoe")

        mu = float(givens["mu"])
        p_a = float(givens["p_a"])
        b = float(givens["b"])
        r = float(givens["r"])
        a = float(givens["a"])
        c = float(givens["c"])
        theta1_deg = float(givens["theta1_deg"])
        theta2_deg = float(givens["theta2_deg"])
        theta_a_deg = float(givens.get("theta_a_deg", 90.0))
        rotation = givens.get("rotation", "clockwise")

        ensure(mu >= 0 and p_a > 0 and b > 0 and r > 0 and a > 0 and c > 0, "Invalid rim-brake givens.")
        ensure(rotation in {"clockwise", "counterclockwise"}, "rotation must be clockwise or counterclockwise.")

        th1 = deg_to_rad(theta1_deg)
        th2 = deg_to_rad(theta2_deg)
        tha = deg_to_rad(theta_a_deg)
        ensure(th2 > th1, "theta2 must be greater than theta1.")
        ensure(abs(math.sin(tha)) > 1e-12, "sin(theta_a) cannot be zero.")
        stha = math.sin(tha)

        A = 0.5 * (math.sin(th2) ** 2 - math.sin(th1) ** 2)
        B = (th2 - th1) / 2.0 - (math.sin(2.0 * th2) - math.sin(2.0 * th1)) / 4.0
        D = p_a * b * r / stha
        M_f = mu * D * (r * (math.cos(th1) - math.cos(th2)) - a * A)
        M_n = D * a * B

        if rotation == "clockwise":
            F = (M_n - M_f) / c
            force_equation = "F = (M_n - M_f) / c"
        else:
            F = (M_n + M_f) / c
            force_equation = "F = (M_n + M_f) / c"
        ensure(F > 0, "Solved actuating force F must be positive.")

        Fx, Fy, actuator_resolution, actuator_notes = self._resolve_actuator_components(
            givens=givens,
            solved_force=F,
            default_x_sign=1 if rotation == "clockwise" else -1,
            default_y_sign=1,
        )

        T = mu * p_a * b * (r ** 2) * (math.cos(th1) - math.cos(th2)) / stha

        if rotation == "clockwise":
            R_x = D * (A - mu * B) - Fx
            R_y = D * (B + mu * A) - Fy
            reaction_equation = "Right/self-energizing shoe: Eq. (16-9)"
        else:
            R_x = D * (A + mu * B) + Fx
            R_y = D * (B - mu * A) - Fy
            reaction_equation = "Left/de-energized shoe: Eq. (16-10)"

        resultant = math.hypot(R_x, R_y)
        self_locking_margin = M_n - M_f

        notes = []
        if rotation == "clockwise":
            notes.append("Clockwise rotation uses the self-energizing form F = (M_n - M_f)/c.")
        else:
            notes.append("Counterclockwise rotation uses the de-energized form F = (M_n + M_f)/c.")
        notes.extend(actuator_notes)

        derived = {
            "givens": {
                "main_shoe": {
                    "mu": mu,
                    "p_a": p_a,
                    "b": b,
                    "r": r,
                    "a": a,
                    "c": c,
                    "theta1_deg": theta1_deg,
                    "theta2_deg": theta2_deg,
                    "theta_a_deg": theta_a_deg,
                    "rotation": rotation,
                    "actuation_angle_deg": actuator_resolution["actuation_angle_deg"],
                    "actuation_x_sign": actuator_resolution["actuation_x_sign"],
                    "actuation_y_sign": actuator_resolution["actuation_y_sign"],
                }
            },
            "geometry_and_coefficients": {
                "theta1_rad": th1,
                "theta2_rad": th2,
                "theta_a_rad": tha,
                "A": A,
                "B": B,
                "D": D,
            },
            "intermediate_calculations": {
                "M_f": M_f,
                "M_n": M_n,
                "force_equation": force_equation,
                "reaction_equation": reaction_equation,
                "actuator_force_resolved": {
                    "F": F,
                    "Fx": Fx,
                    "Fy": Fy,
                    **actuator_resolution,
                },
            },
        }

        outputs = {
            "A": A,
            "B": B,
            "D": D,
            "M_f": M_f,
            "M_n": M_n,
            "actuating_force_F": F,
            "torque_T": T,
            "R_x": R_x,
            "R_y": R_y,
            "hinge_reaction_resultant": resultant,
            "self_locking_margin_Mn_minus_Mf": self_locking_margin,
            "is_self_locking": self_locking_margin <= 0 if rotation == "clockwise" else False,
        }

        if paired_shoe:
            pair = self._solve_paired_shoe(target_F=F, pair_payload=paired_shoe, main_rotation=rotation)
            outputs["paired_shoe"] = pair["outputs"]
            outputs["total_torque_pair"] = T + pair["outputs"]["torque_T"]
            derived["givens"]["paired_shoe"] = pair["givens"]
            derived["paired_shoe_intermediate_calculations"] = pair["derived"]
            notes.extend(pair["notes"])

        return SolveResult(
            problem_type=self.problem_type,
            title=self.title,
            inputs=raw_inputs,
            outputs=outputs,
            derived=derived,
            notes=notes,
        )

    def _resolve_actuator_components(
        self,
        givens: Dict[str, Any],
        solved_force: float,
        default_x_sign: int,
        default_y_sign: int,
    ) -> tuple[float, float, Dict[str, Any], list[str]]:
        notes: list[str] = []
        if "Fx" in givens or "Fy" in givens:
            force_units = givens.get("actuator_force_units", givens.get("force_units", "auto"))
            Fx_raw = float(givens.get("Fx", 0.0))
            Fy_raw = float(givens.get("Fy", 0.0))
            D_force_scale = max(abs(solved_force), 1.0)
            Fx, Fy, force_unit_note = self._normalize_force_components(Fx_raw, Fy_raw, D_force_scale, force_units)
            if force_unit_note:
                notes.append(force_unit_note)
            notes.append("Legacy actuator component inputs Fx/Fy were used. Prefer actuation_angle_deg plus sign conventions for new work.")
            resolution = {
                "component_source": "legacy_components",
                "actuation_angle_deg": None,
                "actuation_x_sign": None,
                "actuation_y_sign": None,
                "actuator_force_units_used": "N",
            }
            return Fx, Fy, resolution, notes

        ensure(givens.get("actuation_angle_deg") is not None, "Rim-brake givens must include actuation_angle_deg when Fx/Fy are not provided.")
        actuation_angle_deg = float(givens["actuation_angle_deg"])
        x_sign = int(givens.get("actuation_x_sign", default_x_sign))
        y_sign = int(givens.get("actuation_y_sign", default_y_sign))
        ensure(x_sign in {-1, 1}, "actuation_x_sign must be either -1 or 1.")
        ensure(y_sign in {-1, 1}, "actuation_y_sign must be either -1 or 1.")
        angle_rad = deg_to_rad(actuation_angle_deg)
        Fx = x_sign * solved_force * math.sin(angle_rad)
        Fy = y_sign * solved_force * math.cos(angle_rad)
        notes.append("Actuator force components were derived internally from the solved actuating force and actuation angle.")
        resolution = {
            "component_source": "derived_from_force_and_angle",
            "actuation_angle_deg": actuation_angle_deg,
            "actuation_x_sign": x_sign,
            "actuation_y_sign": y_sign,
            "actuator_force_units_used": "N",
        }
        return Fx, Fy, resolution, notes

    def _normalize_force_components(self, Fx_raw: float, Fy_raw: float, D_force_scale: float, force_units: str) -> tuple[float, float, str | None]:
        ensure(force_units in {"auto", "N", "kN"}, "actuator_force_units must be one of: auto, N, kN.")
        if force_units == "N":
            return Fx_raw, Fy_raw, None
        if force_units == "kN":
            return 1000.0 * Fx_raw, 1000.0 * Fy_raw, "Converted actuator force components from kN to N."
        force_mag = max(abs(Fx_raw), abs(Fy_raw))
        if D_force_scale > 100.0 and force_mag < 50.0:
            return 1000.0 * Fx_raw, 1000.0 * Fy_raw, "Auto-detected actuator force components as kN and converted to N."
        return Fx_raw, Fy_raw, None

    def _solve_paired_shoe(self, target_F: float, pair_payload: Dict[str, Any], main_rotation: str) -> Dict[str, Any]:
        givens = dict(pair_payload.get("givens", pair_payload))
        mu = float(givens["mu"])
        b = float(givens["b"])
        r = float(givens["r"])
        a = float(givens["a"])
        c = float(givens["c"])
        theta1_deg = float(givens["theta1_deg"])
        theta2_deg = float(givens["theta2_deg"])
        theta_a_deg = float(givens.get("theta_a_deg", 90.0))
        rotation = givens.get("rotation", "counterclockwise" if main_rotation == "clockwise" else "clockwise")
        ensure(rotation in {"clockwise", "counterclockwise"}, "paired_shoe rotation must be clockwise or counterclockwise.")

        th1 = deg_to_rad(theta1_deg)
        th2 = deg_to_rad(theta2_deg)
        tha = deg_to_rad(theta_a_deg)
        ensure(th2 > th1, "paired_shoe theta2 must exceed theta1.")
        ensure(abs(math.sin(tha)) > 1e-12, "paired_shoe sin(theta_a) cannot be zero.")
        stha = math.sin(tha)

        A = 0.5 * (math.sin(th2) ** 2 - math.sin(th1) ** 2)
        B = (th2 - th1) / 2.0 - (math.sin(2.0 * th2) - math.sin(2.0 * th1)) / 4.0
        coeff_Mf = mu * b * r / stha * (r * (math.cos(th1) - math.cos(th2)) - a * A)
        coeff_Mn = b * r / stha * a * B
        if rotation == "clockwise":
            coeff_F = (coeff_Mn - coeff_Mf) / c
            force_equation = "F = (M_n - M_f) / c"
        else:
            coeff_F = (coeff_Mn + coeff_Mf) / c
            force_equation = "F = (M_n + M_f) / c"
        ensure(abs(coeff_F) > 1e-12, "Paired shoe produces zero F coefficient; cannot back-solve pressure.")
        p_a = target_F / coeff_F
        ensure(p_a > 0, "Paired shoe solved p_a must be positive.")

        D = p_a * b * r / stha
        M_f = coeff_Mf * p_a
        M_n = coeff_Mn * p_a
        Fx, Fy, actuator_resolution, notes = self._resolve_actuator_components(
            givens=givens,
            solved_force=target_F,
            default_x_sign=-1 if main_rotation == "clockwise" else 1,
            default_y_sign=1,
        )
        if rotation == "clockwise":
            R_x = D * (A - mu * B) - Fx
            R_y = D * (B + mu * A) - Fy
            reaction_equation = "Right/self-energizing shoe: Eq. (16-9)"
        else:
            R_x = D * (A + mu * B) + Fx
            R_y = D * (B - mu * A) - Fy
            reaction_equation = "Left/de-energized shoe: Eq. (16-10)"
        T = mu * p_a * b * (r ** 2) * (math.cos(th1) - math.cos(th2)) / stha

        return {
            "givens": {
                "mu": mu,
                "b": b,
                "r": r,
                "a": a,
                "c": c,
                "theta1_deg": theta1_deg,
                "theta2_deg": theta2_deg,
                "theta_a_deg": theta_a_deg,
                "rotation": rotation,
                "actuation_angle_deg": actuator_resolution["actuation_angle_deg"],
                "actuation_x_sign": actuator_resolution["actuation_x_sign"],
                "actuation_y_sign": actuator_resolution["actuation_y_sign"],
                "solve_mode": "match_actuating_force",
            },
            "derived": {
                "theta1_rad": th1,
                "theta2_rad": th2,
                "theta_a_rad": tha,
                "A": A,
                "B": B,
                "D": D,
                "M_f": M_f,
                "M_n": M_n,
                "force_equation": force_equation,
                "reaction_equation": reaction_equation,
                "actuator_force_resolved": {
                    "F": target_F,
                    "Fx": Fx,
                    "Fy": Fy,
                    **actuator_resolution,
                },
            },
            "outputs": {
                "solved_p_a": p_a,
                "A": A,
                "B": B,
                "D": D,
                "M_f": M_f,
                "M_n": M_n,
                "actuating_force_F": target_F,
                "torque_T": T,
                "R_x": R_x,
                "R_y": R_y,
                "hinge_reaction_resultant": math.hypot(R_x, R_y),
            },
            "notes": notes,
        }


class AnnularPadCaliperSolver(SolverBase):
    problem_type = "annular_pad"
    title = "Annular-pad caliper brake"

    def solve(self, payload: Dict[str, Any]) -> SolveResult:
        raw_inputs = dict(payload)
        givens = dict(payload.get("givens", payload))

        mu = float(givens["mu"])
        ri = float(givens["ri"])
        ro = float(givens["ro"])
        theta1_deg = float(givens.get("theta1_deg", 0.0))
        theta2_deg = float(givens["theta2_deg"])
        model = givens.get("model", "uniform_wear")
        n_pads = int(givens.get("n_pads", 2))
        torque_total = givens.get("torque_total")
        pa_in = givens.get("p_a")
        F_in = givens.get("F")
        cylinder_diameter = givens.get("cylinder_diameter")
        n_cylinders = int(givens.get("n_cylinders", 1)) if cylinder_diameter is not None else None

        ensure(mu >= 0 and ri > 0 and ro > ri, "Invalid annular-pad geometry.")
        ensure(model in {"uniform_wear", "uniform_pressure"}, "model must be uniform_wear or uniform_pressure.")
        ensure(n_pads >= 1, "n_pads must be >= 1.")

        th1 = deg_to_rad(theta1_deg)
        th2 = deg_to_rad(theta2_deg)
        theta_span = th2 - th1
        ensure(theta_span > 0, "theta2 must exceed theta1.")

        notes: list[str] = []
        if model == "uniform_wear":
            force_coeff = theta_span * ri * (ro - ri)
            torque_coeff_per_pad = 0.5 * theta_span * mu * ri * (ro ** 2 - ri ** 2)
            re = 0.5 * (ro + ri)
            rbar = ((math.cos(th1) - math.cos(th2)) / theta_span) * re
            pressure_distribution = "p = p_a r_i / r"
        else:
            force_coeff = 0.5 * theta_span * (ro ** 2 - ri ** 2)
            torque_coeff_per_pad = (1.0 / 3.0) * theta_span * mu * (ro ** 3 - ri ** 3)
            re = (2.0 / 3.0) * (ro ** 3 - ri ** 3) / (ro ** 2 - ri ** 2)
            rbar = ((math.cos(th1) - math.cos(th2)) / theta_span) * re
            pressure_distribution = "p = p_a"

        if pa_in is None:
            if torque_total is not None:
                torque_per_pad_target = float(torque_total) / n_pads
                pa = torque_per_pad_target / torque_coeff_per_pad
                notes.append("Solved p_a from torque requirement per pad.")
            elif F_in is not None:
                pa = float(F_in) / force_coeff
                notes.append("Solved p_a from actuating force per pad.")
            else:
                raise ValidationError("Provide at least one of p_a, F, or torque_total.")
        else:
            pa = float(pa_in)
        ensure(pa > 0, "p_a must be positive.")

        F_per_pad = force_coeff * pa if F_in is None else float(F_in)
        torque_per_pad = torque_coeff_per_pad * pa
        torque_total_calc = n_pads * torque_per_pad

        hydraulic_pressure = None
        cyl_area_each = None
        cyl_area_total = None
        if cylinder_diameter is not None:
            d_cyl = float(cylinder_diameter)
            ensure(d_cyl > 0 and n_cylinders >= 1, "Invalid hydraulic cylinder definition.")
            cyl_area_each = math.pi * d_cyl ** 2 / 4.0
            cyl_area_total = n_cylinders * cyl_area_each
            hydraulic_pressure = F_per_pad / cyl_area_each
            if n_cylinders != n_pads:
                notes.append(
                    "Hydraulic pressure was computed from force per pad divided by area of one cylinder. "
                    "This assumes one cylinder supplies each pad; if your hardware is different, adjust the interpretation."
                )

        outputs = {
            "p_a": pa,
            "F_per_pad": F_per_pad,
            "torque_per_pad": torque_per_pad,
            "torque_total": torque_total_calc,
            "effective_radius_re": re,
            "force_location_rbar": rbar,
            "theta_span_deg": math.degrees(theta_span),
        }
        if hydraulic_pressure is not None:
            outputs["hydraulic_pressure"] = hydraulic_pressure
            outputs["cylinder_area_each"] = cyl_area_each
            outputs["total_cylinder_area"] = cyl_area_total

        derived = {
            "givens": {
                "model": model,
                "mu": mu,
                "ri": ri,
                "ro": ro,
                "theta1_deg": theta1_deg,
                "theta2_deg": theta2_deg,
                "n_pads": n_pads,
                "torque_total_target": torque_total,
                "cylinder_diameter": cylinder_diameter,
                "n_cylinders": n_cylinders,
            },
            "angles": {
                "theta1_rad": th1,
                "theta2_rad": th2,
                "theta_span_rad": theta_span,
                "theta_span_deg": math.degrees(theta_span),
            },
            "model_details": {
                "pressure_distribution": pressure_distribution,
                "force_coefficient_per_pad": force_coeff,
                "torque_coefficient_per_pad": torque_coeff_per_pad,
            },
            "intermediate_calculations": {
                "torque_per_pad_target": (float(torque_total) / n_pads) if torque_total is not None else None,
                "effective_radius_re": re,
                "force_location_rbar": rbar,
            },
        }

        return SolveResult(
            problem_type=self.problem_type,
            title=self.title,
            inputs={"givens": givens},
            outputs=outputs,
            derived=derived,
            notes=notes,
        )


class ButtonPadCaliperSolver(SolverBase):
    problem_type = "button_pad_caliper"
    title = "Circular button-pad caliper brake"

    TABLE_16_1 = {
        "R_over_e": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
        "delta": [1.000, 0.983, 0.969, 0.957, 0.947, 0.938],
        "pmax_over_pav": [1.000, 1.093, 1.212, 1.367, 1.578, 1.875],
    }

    def solve(self, payload: Dict[str, Any]) -> SolveResult:
        raw_inputs = dict(payload)
        givens = dict(payload.get("givens", payload))

        mu = float(givens["mu"])
        R = float(givens["pad_radius"])
        e = float(givens["eccentricity"])

        ensure(mu >= 0.0, "mu must be nonnegative.")
        ensure(R > 0.0 and e > 0.0, "pad_radius and eccentricity must be positive.")

        ratio = R / e
        table = self.TABLE_16_1
        x = table["R_over_e"]
        ensure(x[0] <= ratio <= x[-1], f"R/e = {ratio:.6f} is outside Table 16-1 range [{x[0]}, {x[-1]}].")

        delta = self._interp(ratio, x, table["delta"])
        pmax_over_pav = self._interp(ratio, x, table["pmax_over_pav"])

        pmax_operating, pressure_mode_note, pressure_inputs = self._resolve_pmax_operating(givens, pmax_over_pav)
        ensure(pmax_operating > 0.0, "Operating maximum pressure must be positive.")

        re = delta * e
        pav = pmax_operating / pmax_over_pav
        F = math.pi * R * R * pav
        T_one_side = mu * F * re

        n_active_sides = int(givens.get("n_active_sides", 1))
        ensure(n_active_sides >= 1, "n_active_sides must be >= 1.")
        T_total = n_active_sides * T_one_side

        disk_diameter = givens.get("disk_diameter")
        disk_radius = None
        outer_contact_radius = e + R
        notes: list[str] = []
        if pressure_mode_note:
            notes.append(pressure_mode_note)
        notes.append("Table 16-1 was interpolated linearly in R/e.")
        notes.append("Eq. (16-41), Eq. (16-42), and Eq. (16-43) were applied in sequence.")
        if n_active_sides == 1:
            notes.append("Returned torque is for one active friction side, matching Example 16-4.")
        else:
            notes.append("Returned total torque multiplies one-side torque by n_active_sides.")

        if disk_diameter is not None:
            disk_diameter = float(disk_diameter)
            ensure(disk_diameter > 0.0, "disk_diameter must be positive when provided.")
            disk_radius = 0.5 * disk_diameter
            if outer_contact_radius > disk_radius:
                notes.append(
                    "Provided disk_diameter was not used in Eqs. (16-41) to (16-43). "
                    "Also, e + R exceeds the stated disk radius, so the disk geometry appears inconsistent with the pressure-law example data."
                )

        outputs = {
            "R_over_e": ratio,
            "delta": delta,
            "pmax_over_pav": pmax_over_pav,
            "effective_radius_re": re,
            "average_pressure_pav": pav,
            "actuating_force_F": F,
            "torque_one_side": T_one_side,
            "torque_total": T_total,
            "operating_max_pressure_pmax": pmax_operating,
            "n_active_sides": n_active_sides,
        }

        derived = {
            "givens": {
                "mu": mu,
                "pad_radius": R,
                "eccentricity": e,
                "disk_diameter": disk_diameter,
                "n_active_sides": n_active_sides,
                **pressure_inputs,
            },
            "table_16_1": {
                "R_over_e": x,
                "delta": table["delta"],
                "pmax_over_pav": table["pmax_over_pav"],
                "interpolation_ratio": ratio,
            },
            "equations": {
                "eq_16_41": "r_e = delta * e",
                "eq_16_42": "F = pi * R^2 * p_av",
                "eq_16_43": "T = f * F * r_e",
            },
            "intermediate_calculations": {
                "disk_radius": disk_radius,
                "outer_contact_radius_e_plus_R": outer_contact_radius,
                "average_pressure_pav": pav,
                "effective_radius_re": re,
                "friction_force_muF": mu * F,
            },
        }

        return SolveResult(
            problem_type=self.problem_type,
            title=self.title,
            inputs={"givens": givens},
            outputs=outputs,
            derived=derived,
            notes=notes,
        )

    @staticmethod
    def _interp(xi: float, xs: list[float], ys: list[float]) -> float:
        for i in range(len(xs) - 1):
            x0 = xs[i]
            x1 = xs[i + 1]
            if abs(xi - x0) <= 1e-12:
                return ys[i]
            if x0 <= xi <= x1:
                y0 = ys[i]
                y1 = ys[i + 1]
                if abs(x1 - x0) <= 1e-12:
                    return y0
                return y0 + (xi - x0) * (y1 - y0) / (x1 - x0)
        return ys[-1]

    @staticmethod
    def _resolve_pmax_operating(givens: Dict[str, Any], pmax_over_pav: float) -> tuple[float, str | None, Dict[str, Any]]:
        if givens.get("pmax_operating") is not None:
            return float(givens["pmax_operating"]), "Used provided operating maximum pressure pmax_operating.", {
                "pmax_operating": float(givens["pmax_operating"]),
            }

        pmax_allowable = givens.get("pmax_allowable")
        operating_fraction = givens.get("operating_fraction_of_allowable")
        if pmax_allowable is not None and operating_fraction is not None:
            pmax_operating = float(pmax_allowable) * float(operating_fraction)
            return pmax_operating, "Computed operating maximum pressure from pmax_allowable * operating_fraction_of_allowable.", {
                "pmax_allowable": float(pmax_allowable),
                "operating_fraction_of_allowable": float(operating_fraction),
                "pmax_operating": pmax_operating,
            }

        p_avg = givens.get("p_avg")
        if p_avg is not None:
            pmax_operating = float(p_avg) * pmax_over_pav
            return pmax_operating, "Back-computed pmax_operating from provided p_avg and interpolated pmax/pav.", {
                "p_avg": float(p_avg),
                "pmax_operating": pmax_operating,
            }

        raise ValidationError(
            "Button-pad caliper input must provide either pmax_operating, or both pmax_allowable and operating_fraction_of_allowable, or p_avg."
        )


class TemperatureRiseCaliperSolver(SolverBase):
    problem_type = "temperature_rise_caliper"
    title = "Caliper brake steady-state temperature rise"

    DEFAULT_FIGURE_16_24_A = "data/figure_16_24_a.csv"
    DEFAULT_FIGURE_16_24_B = "data/figure_16_24_b.csv"
    DEFAULT_TABLE_16_3 = "data/table_16_3.csv"

    def solve(self, payload: Dict[str, Any]) -> SolveResult:
        raw_inputs = dict(payload)
        givens = dict(payload.get("givens", payload))
        data_sources = dict(payload.get("data_sources", {}))
        iteration_cfg = dict(payload.get("iteration", {}))
        meta = dict(payload.get("meta", {}))

        n_uses_per_hour = float(givens["number_of_brake_uses_per_hour"])
        speed_initial_rpm = float(givens["initial_speed_rev_per_min"])
        speed_final_rpm = float(givens.get("final_speed_rev_per_min", 0.0))
        mean_air_speed_ft_s = float(givens["mean_air_speed_ft_per_s"])
        inertia = float(givens["equivalent_rotary_inertia_lbm_in_s2"])
        gamma = float(givens["disk_density_lbm_per_in3"])
        cp = float(givens["specific_heat_capacity_Btu_per_lbm_F"])
        disk_diameter_in = float(givens["disk_diameter_in"])
        disk_thickness_in = float(givens["disk_thickness_in"])
        lateral_area_in2 = float(givens["lateral_area_in2"])
        ambient_temp_F = float(givens["ambient_temperature_F"])
        friction_material = str(givens["pad_material"])

        ensure(n_uses_per_hour > 0.0, "number_of_brake_uses_per_hour must be positive.")
        ensure(speed_initial_rpm >= 0.0 and speed_final_rpm >= 0.0, "Speeds must be nonnegative.")
        ensure(speed_initial_rpm >= speed_final_rpm, "initial_speed_rev_per_min must be >= final_speed_rev_per_min.")
        ensure(mean_air_speed_ft_s >= 0.0, "mean_air_speed_ft_per_s must be nonnegative.")
        ensure(inertia > 0.0 and gamma > 0.0 and cp > 0.0, "Inertia, density, and specific heat must be positive.")
        ensure(disk_diameter_in > 0.0 and disk_thickness_in > 0.0 and lateral_area_in2 > 0.0, "Disk geometry and area must be positive.")

        guess_rise_F = float(iteration_cfg.get("initial_temperature_rise_guess_F", 200.0))
        tolerance_F = float(iteration_cfg.get("tolerance_temperature_rise_F", 0.5))
        max_iterations = int(iteration_cfg.get("max_iterations", 50))
        ensure(guess_rise_F > 0.0, "Initial temperature rise guess must be positive.")
        ensure(tolerance_F > 0.0, "Temperature rise tolerance must be positive.")
        ensure(max_iterations >= 1, "max_iterations must be at least 1.")

        base_dir = Path(__file__).resolve().parent
        fig_a_path = self._resolve_data_path(data_sources.get("figure_16_24_a", self.DEFAULT_FIGURE_16_24_A), base_dir)
        fig_b_path = self._resolve_data_path(data_sources.get("figure_16_24_b", self.DEFAULT_FIGURE_16_24_B), base_dir)
        table_16_3_path = self._resolve_data_path(data_sources.get("table_16_3", self.DEFAULT_TABLE_16_3), base_dir)

        fig_a = self._load_xy_csv(
            fig_a_path,
            x_keys=("temperature_rise_F", "delta_T_F", "temperature_rise", "x"),
            y_keys=(("hr", "h_r"), ("hc", "h_c")),
            y_scale=1.0e-6,
        )
        fig_b = self._load_xy_csv(
            fig_b_path,
            x_keys=("air_speed_ft_per_s", "velocity_ft_per_s", "forced_ventilation_velocity_ft_per_s", "v_ft_s", "x"),
            y_keys=(("fv", "f_v", "ventilation_factor"),),
            y_scale=1.0,
        )
        material_limits = self._load_material_limits(table_16_3_path)

        t1_s = 3600.0 / n_uses_per_hour
        disk_mass_lbm = math.pi * gamma * (disk_diameter_in ** 2) * disk_thickness_in / 4.0
        omega_initial = (2.0 * math.pi / 60.0) * speed_initial_rpm
        omega_final = (2.0 * math.pi / 60.0) * speed_final_rpm
        E_Btu = 0.5 * inertia * (omega_initial ** 2 - omega_final ** 2) / 9336.0
        delta_T_single_stop_F = E_Btu / (disk_mass_lbm * cp)
        fv = self._interp(mean_air_speed_ft_s, fig_b["x"], fig_b["y_0"], "Figure 16-24b air-speed axis")

        iteration_rows: list[Dict[str, Any]] = []
        rise_guess = guess_rise_F
        converged = False

        for i in range(1, max_iterations + 1):
            hr = self._interp(rise_guess, fig_a["x"], fig_a["y_0"], "Figure 16-24a temperature-rise axis for hr")
            hc = self._interp(rise_guess, fig_a["x"], fig_a["y_1"], "Figure 16-24a temperature-rise axis for hc")
            hcr = hr + fv * hc
            beta = (hcr * lateral_area_in2) / (disk_mass_lbm * cp)
            exp_term = math.exp(-beta * t1_s)
            denom = 1.0 - exp_term
            ensure(abs(denom) > 1e-12, "Eq. (16-60) denominator collapsed to zero.")
            Tmax_F = ambient_temp_F + delta_T_single_stop_F / denom
            Tmin_F = Tmax_F - delta_T_single_stop_F
            predicted_rise_F = Tmax_F - ambient_temp_F
            residual_F = predicted_rise_F - rise_guess

            iteration_rows.append({
                "iteration": i,
                "guess_temperature_rise_F": rise_guess,
                "hr_Btu_per_in2_s_F": hr,
                "hc_Btu_per_in2_s_F": hc,
                "fv": fv,
                "hcr_Btu_per_in2_s_F": hcr,
                "beta_per_s": beta,
                "exp_minus_beta_t1": exp_term,
                "Tmax_F": Tmax_F,
                "Tmin_F": Tmin_F,
                "predicted_temperature_rise_F": predicted_rise_F,
                "residual_F": residual_F,
            })

            if abs(residual_F) <= tolerance_F:
                converged = True
                break
            rise_guess = predicted_rise_F

        ensure(iteration_rows, "Iteration did not run.")
        final_iter = iteration_rows[-1]
        Tmax_F = final_iter["Tmax_F"]
        Tmin_F = final_iter["Tmin_F"]
        final_rise_F = final_iter["predicted_temperature_rise_F"]
        hr = final_iter["hr_Btu_per_in2_s_F"]
        hc = final_iter["hc_Btu_per_in2_s_F"]
        hcr = final_iter["hcr_Btu_per_in2_s_F"]
        beta = final_iter["beta_per_s"]

        overheat_check = self._evaluate_overheat(material_limits, friction_material, Tmax_F)

        notes = [
            "Figure 16-24a hr and hc values were multiplied by 1e-6, as required by the digitized data convention.",
            "Figure 16-24b air-speed input is treated in ft/s.",
            "Eq. (16-58), Eq. (16-59), and Eq. (16-60) were applied with fixed-point iteration on Tmax - Tinf.",
        ]
        if converged:
            notes.append(f"Iteration converged in {len(iteration_rows)} iteration(s) with |predicted rise - guess| <= {tolerance_F}°F.")
        else:
            notes.append(f"Iteration reached max_iterations={max_iterations} without satisfying the requested tolerance.")
        if overheat_check["material_found"]:
            if overheat_check.get("continuous_limits_available"):
                if overheat_check["within_continuous_range"]:
                    notes.append("Final continuous-temperature check indicates no danger of overheating for the stated friction material.")
                else:
                    notes.append("Final continuous-temperature check indicates the brake exceeds the digitized continuous operating limit for the stated friction material.")
            else:
                notes.append("The friction material was matched in Table 16-3, but continuous-temperature limits were unavailable, so the overheating check is inconclusive.")
        else:
            notes.append("Material name was not found in the digitized Table 16-3, so the overheating check could not be completed.")

        outputs = {
            "t1_s": t1_s,
            "disk_mass_lbm": disk_mass_lbm,
            "E_Btu": E_Btu,
            "delta_T_single_stop_F": delta_T_single_stop_F,
            "fv": fv,
            "hr_Btu_per_in2_s_F": hr,
            "hc_Btu_per_in2_s_F": hc,
            "hcr_Btu_per_in2_s_F": hcr,
            "beta_per_s": beta,
            "Tmax_F": Tmax_F,
            "Tmin_F": Tmin_F,
            "steady_state_temperature_rise_F": final_rise_F,
            "iteration_count": len(iteration_rows),
            "converged": converged,
            "overheat_check": overheat_check,
        }

        derived = {
            "meta": meta,
            "givens": {
                "number_of_brake_uses_per_hour": n_uses_per_hour,
                "initial_speed_rev_per_min": speed_initial_rpm,
                "final_speed_rev_per_min": speed_final_rpm,
                "mean_air_speed_ft_per_s": mean_air_speed_ft_s,
                "equivalent_rotary_inertia_lbm_in_s2": inertia,
                "disk_density_lbm_per_in3": gamma,
                "specific_heat_capacity_Btu_per_lbm_F": cp,
                "disk_diameter_in": disk_diameter_in,
                "disk_thickness_in": disk_thickness_in,
                "lateral_area_in2": lateral_area_in2,
                "ambient_temperature_F": ambient_temp_F,
                "pad_material": friction_material,
            },
            "data_sources": {
                "figure_16_24_a": str(fig_a_path),
                "figure_16_24_b": str(fig_b_path),
                "table_16_3": str(table_16_3_path),
            },
            "equations": {
                "step_0": "t1 = 3600 / uses_per_hour",
                "eq_16_57": "h_CR = h_r + f_v h_c",
                "disk_mass": "W = pi * gamma * D^2 * h / 4",
                "eq_16_58": "E = (1/2)(I/9336)(omega_o^2 - omega_f^2)",
                "eq_16_59": "delta_T = E / (W C_p)",
                "beta": "beta = h_CR A / (W C_p)",
                "eq_16_60": "Tmax = T_inf + delta_T / (1 - exp(-beta t1))",
                "valley": "Tmin = Tmax - delta_T",
            },
            "intermediate_calculations": {
                "omega_initial_rad_per_s": omega_initial,
                "omega_final_rad_per_s": omega_final,
                "disk_mass_formula_inputs": {
                    "gamma_lbm_per_in3": gamma,
                    "diameter_in": disk_diameter_in,
                    "thickness_in": disk_thickness_in,
                },
            },
            "iteration": {
                "initial_temperature_rise_guess_F": guess_rise_F,
                "tolerance_temperature_rise_F": tolerance_F,
                "max_iterations": max_iterations,
                "history": iteration_rows,
            },
        }

        return SolveResult(
            problem_type=self.problem_type,
            title=self.title,
            inputs={"givens": givens, "data_sources": data_sources, "iteration": iteration_cfg},
            outputs=outputs,
            derived=derived,
            notes=notes,
        )

    @staticmethod
    def _resolve_data_path(value: str, base_dir: Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (base_dir / path).resolve()

    @staticmethod
    def _numeric_from_row(row: dict[str, str], key_options: tuple[str, ...]) -> float | None:
        for key in key_options:
            if key in row and row[key] not in (None, ""):
                try:
                    return float(str(row[key]).strip())
                except ValueError:
                    return None
        return None

    def _load_xy_csv(
        self,
        path: Path,
        x_keys: tuple[str, ...],
        y_keys: tuple[tuple[str, ...], ...],
        y_scale: float,
    ) -> dict[str, list[float]]:
        ensure(path.exists(), f"Required data file not found: {path}")
        xs: list[float] = []
        ys: list[list[float]] = [[] for _ in y_keys]
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            ensure(reader.fieldnames is not None, f"CSV file has no header row: {path}")
            for row in reader:
                x = self._numeric_from_row(row, x_keys)
                if x is None:
                    continue
                y_values: list[float] = []
                valid = True
                for group in y_keys:
                    y = self._numeric_from_row(row, group)
                    if y is None:
                        valid = False
                        break
                    y_values.append(y * y_scale)
                if not valid:
                    continue
                xs.append(x)
                for i, y in enumerate(y_values):
                    ys[i].append(y)
        ensure(len(xs) >= 2, f"Need at least two valid rows in {path}")
        combined = sorted(zip(xs, *ys), key=lambda item: item[0])
        out = {"x": [row[0] for row in combined]}
        for i in range(len(y_keys)):
            out[f"y_{i}"] = [row[i + 1] for row in combined]
        return out

    def _load_material_limits(self, path: Path) -> list[dict[str, Any]]:
        ensure(path.exists(), f"Required data file not found: {path}")
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            ensure(reader.fieldnames is not None, f"CSV file has no header row: {path}")
            header_map = {self._normalize_header(name): name for name in reader.fieldnames if name}
            material_key = self._first_matching_header(
                header_map,
                "material",
                "friction_material",
                "pad_material",
                "lining_material",
            )
            ensure(material_key is not None, f"Could not find a material-name column in {path}")
            min_key = self._first_matching_header(
                header_map,
                "continuous_temp_F_min",
                "continuous_min_temp_F",
                "continuous_operating_temp_F_min",
                "continuous_operating_min_temp_F",
                "continuous_min_F",
                "min_continuous_temp_F",
            )
            max_key = self._first_matching_header(
                header_map,
                "continuous_temp_F_max",
                "continuous_max_temp_F",
                "continuous_operating_temp_F_max",
                "continuous_operating_max_temp_F",
                "continuous_max_F",
                "max_continuous_temp_F",
            )

            for row in reader:
                material = str(row.get(material_key, "")).strip()
                if not material:
                    continue
                min_temp = self._numeric_from_any(row, (min_key,) if min_key else ())
                max_temp = self._numeric_from_any(row, (max_key,) if max_key else ())
                rows.append({
                    "material": material,
                    "material_normalized": self._normalize_material_name(material),
                    "continuous_min_temp_F": min_temp,
                    "continuous_max_temp_F": max_temp,
                    "temperature_limits_present": (min_temp is not None) or (max_temp is not None),
                })
        ensure(rows, f"No material rows found in {path}")
        return rows

    def _evaluate_overheat(self, materials: list[dict[str, Any]], material_name: str, Tmax_F: float) -> dict[str, Any]:
        wanted_original = material_name.strip()
        wanted = self._normalize_material_name(wanted_original)

        exact_candidates = [row for row in materials if row.get("material_normalized") == wanted]
        token_candidates = []
        wanted_tokens = set(self._material_tokens(wanted_original))
        if wanted_tokens:
            for row in materials:
                row_tokens = set(self._material_tokens(str(row.get("material", ""))))
                overlap = len(wanted_tokens & row_tokens)
                if overlap > 0:
                    token_candidates.append((overlap, len(row_tokens), row))

        chosen = None
        match_method = None
        candidate_materials = [str(row.get("material", "")) for row in materials]
        if exact_candidates:
            exact_candidates.sort(key=lambda row: (not row.get("temperature_limits_present", False), str(row.get("material", ""))))
            chosen = exact_candidates[0]
            match_method = "normalized_exact"
        elif token_candidates:
            token_candidates.sort(key=lambda item: (-item[0], item[1], not item[2].get("temperature_limits_present", False), str(item[2].get("material", ""))))
            chosen = token_candidates[0][2]
            match_method = "token_overlap"

        if chosen is None:
            return {
                "material_found": False,
                "matched_material": None,
                "match_method": None,
                "input_material": wanted_original,
                "continuous_min_temp_F": None,
                "continuous_max_temp_F": None,
                "continuous_limits_available": False,
                "within_continuous_range": None,
                "overheating_risk": None,
                "margin_to_continuous_max_F": None,
                "candidate_materials": candidate_materials,
            }

        max_temp = chosen.get("continuous_max_temp_F")
        min_temp = chosen.get("continuous_min_temp_F")
        limits_available = (min_temp is not None) or (max_temp is not None)
        upper_ok = True if max_temp is None else (Tmax_F <= max_temp)
        within = upper_ok if limits_available else None

        return {
            "material_found": True,
            "matched_material": chosen.get("material"),
            "match_method": match_method,
            "input_material": wanted_original,
            "continuous_min_temp_F": min_temp,
            "continuous_max_temp_F": max_temp,
            "continuous_limits_available": limits_available,
            "within_continuous_range": within,
            "overheating_risk": (not within) if within is not None else None,
            "margin_to_continuous_max_F": None if max_temp is None else (max_temp - Tmax_F),
            "margin_above_continuous_min_F": None if min_temp is None else (Tmax_F - min_temp),
        }

    @staticmethod
    def _normalize_header(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).strip().casefold()).strip("_")

    @staticmethod
    def _first_matching_header(header_map: dict[str, str], *aliases: str) -> str | None:
        for alias in aliases:
            normalized_alias = TemperatureRiseCaliperSolver._normalize_header(alias)
            if normalized_alias in header_map:
                return header_map[normalized_alias]
        return None

    @staticmethod
    def _numeric_from_any(row: dict[str, Any], key_options: tuple[str, ...]) -> float | None:
        for key in key_options:
            if not key:
                continue
            value = row.get(key)
            if value in (None, ""):
                continue
            try:
                return float(str(value).strip())
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_material_name(value: str) -> str:
        text = str(value).strip().casefold()
        replacements = {
            "non asbestos": "nonasbestos",
            "non-asbestos": "nonasbestos",
            "disk": "disc",
            "caliper disk brakes": "caliper disc brakes",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = re.sub(r"\(.*?\)", lambda m: " " + m.group(0)[1:-1] + " ", text)
        tokens = TemperatureRiseCaliperSolver._material_tokens(text)
        synonyms = {
            "dry sintered metal": "sintered metal dry",
            "sintered metal dry": "sintered metal dry",
            "wet sintered metal": "sintered metal wet",
            "sintered metal wet": "sintered metal wet",
        }
        normalized = " ".join(tokens)
        return synonyms.get(normalized, normalized)

    @staticmethod
    def _material_tokens(value: str) -> list[str]:
        raw = re.split(r"[^a-z0-9]+", str(value).casefold())
        stop = {"and", "for", "the", "of", "material", "materials"}
        return [tok for tok in raw if tok and tok not in stop]

    @staticmethod
    def _interp(xi: float, xs: list[float], ys: list[float], label: str) -> float:
        ensure(len(xs) == len(ys) and len(xs) >= 2, f"Interpolation data for {label} is invalid.")
        ensure(xs[0] <= xi <= xs[-1], f"{label}: value {xi:.6f} is outside digitized range [{xs[0]}, {xs[-1]}].")
        for i in range(len(xs) - 1):
            x0 = xs[i]
            x1 = xs[i + 1]
            if abs(xi - x0) <= 1e-12:
                return ys[i]
            if x0 <= xi <= x1:
                y0 = ys[i]
                y1 = ys[i + 1]
                return y0 + (xi - x0) * (y1 - y0) / (x1 - x0)
        return ys[-1]


class FlywheelSolver(SolverBase):
    problem_type = "flywheel"
    title = "Flywheel energy fluctuation from torque-angle data"

    def solve(self, payload: Dict[str, Any]) -> SolveResult:
        raw_inputs = dict(payload)
        givens = dict(payload.get("givens", payload))
        data_sources = dict(payload.get("data_sources", {}))
        analysis_cfg = dict(payload.get("analysis", {}))
        meta = dict(payload.get("meta", {}))

        nominal_angular_speed = float(givens["nominal_angular_speed_rad_per_s"])
        coefficient_of_speed_fluctuation = float(givens["coefficient_of_speed_fluctuation"])
        ensure(nominal_angular_speed > 0.0, "nominal_angular_speed_rad_per_s must be positive.")
        ensure(coefficient_of_speed_fluctuation > 0.0, "coefficient_of_speed_fluctuation must be positive.")

        torque_table_path_value = data_sources.get("torque_table_csv") or givens.get("torque_table_csv")
        ensure(torque_table_path_value is not None, "Flywheel input must provide data_sources.torque_table_csv or givens.torque_table_csv.")
        base_dir = Path(__file__).resolve().parent
        torque_table_path = self._resolve_data_path(str(torque_table_path_value), base_dir)
        theta_deg, torque = self._load_torque_table(torque_table_path)

        theta_rad = [deg_to_rad(v) for v in theta_deg]
        cycle_angle_deg = theta_deg[-1] - theta_deg[0]
        cycle_angle_rad = theta_rad[-1] - theta_rad[0]
        ensure(cycle_angle_rad > 0.0, "Torque table must span a nonzero cycle angle.")

        interval_count = len(theta_deg) - 1
        dtheta_deg = [theta_deg[i + 1] - theta_deg[i] for i in range(interval_count)]
        dtheta_rad = [theta_rad[i + 1] - theta_rad[i] for i in range(interval_count)]
        uniform_spacing = max(dtheta_deg) - min(dtheta_deg) <= 1e-9

        energy_per_cycle = self._trapz(theta_rad, torque)
        mean_torque = energy_per_cycle / cycle_angle_rad
        delta_torque = [t - mean_torque for t in torque]

        cumulative_energy = [0.0]
        for i in range(interval_count):
            area = 0.5 * (delta_torque[i] + delta_torque[i + 1]) * (theta_rad[i + 1] - theta_rad[i])
            cumulative_energy.append(cumulative_energy[-1] + area)

        max_energy = max(cumulative_energy)
        min_energy = min(cumulative_energy)
        idx_max = cumulative_energy.index(max_energy)
        idx_min = cumulative_energy.index(min_energy)
        greatest_energy_fluctuation = max_energy - min_energy

        fluctuation_override = analysis_cfg.get("fluctuation_interval_deg")
        selected_fluctuation = None
        if fluctuation_override is not None:
            ensure(isinstance(fluctuation_override, dict), "analysis.fluctuation_interval_deg must be an object with start and end.")
            start_deg = float(fluctuation_override["start"])
            end_deg = float(fluctuation_override["end"])
            selected_fluctuation = self._integrate_between(theta_deg, delta_torque, start_deg, end_deg)
            selected_start_deg = start_deg
            selected_end_deg = end_deg
            selected_start_index = None
            selected_end_index = None
            selected_mode = "user_specified_interval"
        else:
            selected_fluctuation = greatest_energy_fluctuation
            selected_start_deg = theta_deg[idx_min]
            selected_end_deg = theta_deg[idx_max]
            selected_start_index = idx_min
            selected_end_index = idx_max
            selected_mode = "largest_cumulative_energy_excursion"

        flywheel_inertia = selected_fluctuation / (coefficient_of_speed_fluctuation * nominal_angular_speed ** 2)
        omega2 = 0.5 * nominal_angular_speed * (2.0 + coefficient_of_speed_fluctuation)
        omega1 = 0.5 * nominal_angular_speed * (2.0 - coefficient_of_speed_fluctuation)

        energy_extrema = {
            "minimum_cumulative_energy_lbf_in": min_energy,
            "minimum_at_theta_deg": theta_deg[idx_min],
            "maximum_cumulative_energy_lbf_in": max_energy,
            "maximum_at_theta_deg": theta_deg[idx_max],
        }

        table_rows = []
        for i in range(len(theta_deg)):
            row = {
                "theta_deg": theta_deg[i],
                "theta_rad": theta_rad[i],
                "T_lbf_in": torque[i],
                "T_minus_Tm_lbf_in": delta_torque[i],
                "cumulative_energy_from_start_lbf_in": cumulative_energy[i],
            }
            table_rows.append(row)

        notes = [
            "Part (a): integrated the torque-displacement curve numerically over one full cycle using the trapezoidal rule.",
            "Part (b): computed mean torque as total cycle energy divided by total cycle angle.",
            "Part (c): formed the energy-deviation curve by integrating T - T_m with respect to crank angle.",
            "Part (d): used Eq. (16-64) together with Eqs. (16-62) and (16-63) to compute flywheel inertia and speed limits.",
        ]
        if uniform_spacing:
            notes.append(f"The torque table uses {interval_count} equal intervals of Δθ = {dtheta_deg[0]:.6g} deg.")
        else:
            notes.append("The torque table spacing is nonuniform; trapezoidal integration was still applied directly in radians.")
        if selected_mode == "largest_cumulative_energy_excursion":
            notes.append(
                "The fluctuation interval was selected automatically as the largest difference between cumulative-energy extrema of the T - T_m diagram."
            )
        else:
            notes.append("The fluctuation interval was taken from analysis.fluctuation_interval_deg.")
            notes.append(
                "For textbook-style part (c), use part_c_selected_energy_fluctuation_lbf_in. "
                "The separate field part_c_largest_energy_excursion_between_extrema_lbf_in is only the full spread of the cumulative-energy curve."
            )

        outputs = {
            "part_a_energy_per_cycle_lbf_in": energy_per_cycle,
            "part_b_mean_torque_lbf_in": mean_torque,
            "part_c_energy_deviation_curve_extrema": {
                "minimum_cumulative_energy_from_start_lbf_in": min_energy,
                "minimum_at_theta_deg": theta_deg[idx_min],
                "maximum_cumulative_energy_from_start_lbf_in": max_energy,
                "maximum_at_theta_deg": theta_deg[idx_max],
            },
            "part_c_largest_energy_excursion_between_extrema_lbf_in": greatest_energy_fluctuation,
            "part_c_selected_energy_fluctuation_lbf_in": selected_fluctuation,
            "part_c_selected_interval": {
                "mode": selected_mode,
                "start_theta_deg": selected_start_deg,
                "end_theta_deg": selected_end_deg,
                "start_index": selected_start_index,
                "end_index": selected_end_index,
            },
            "part_d_flywheel_inertia_lbf_s2_in": flywheel_inertia,
            "part_d_omega2_rad_per_s": omega2,
            "part_d_omega1_rad_per_s": omega1,
            "speed_extrema_locations": {
                "omega2_occurs_at_theta_deg": theta_deg[idx_max],
                "omega1_occurs_at_theta_deg": theta_deg[idx_min],
            },
        }

        derived = {
            "meta": meta,
            "givens": {
                "nominal_angular_speed_rad_per_s": nominal_angular_speed,
                "coefficient_of_speed_fluctuation": coefficient_of_speed_fluctuation,
            },
            "data_sources": {
                "torque_table_csv": str(torque_table_path),
            },
            "cycle_geometry": {
                "theta_start_deg": theta_deg[0],
                "theta_end_deg": theta_deg[-1],
                "cycle_angle_deg": cycle_angle_deg,
                "cycle_angle_rad": cycle_angle_rad,
                "interval_count": interval_count,
                "uniform_spacing": uniform_spacing,
                "delta_theta_deg_values": dtheta_deg,
            },
            "equations": {
                "part_a": "E = integral(T dtheta)",
                "part_b": "T_m = E / theta_cycle",
                "eq_16_61": "E_2 - E_1 = (1/2) I (omega_2^2 - omega_1^2)",
                "eq_16_62": "C_s = (omega_2 - omega_1) / omega",
                "eq_16_63": "omega = (omega_2 + omega_1) / 2",
                "eq_16_64": "E_2 - E_1 = C_s I omega^2",
            },
            "intermediate_calculations": {
                "energy_extrema": energy_extrema,
                "selected_energy_fluctuation_lbf_in": selected_fluctuation,
                "delta_torque_values_lbf_in": delta_torque,
                "cumulative_energy_values_lbf_in": cumulative_energy,
            },
            "table_evaluation": table_rows,
        }

        return SolveResult(
            problem_type=self.problem_type,
            title=self.title,
            inputs={"givens": givens, "data_sources": data_sources, "analysis": analysis_cfg},
            outputs=outputs,
            derived=derived,
            notes=notes,
        )

    @staticmethod
    def _resolve_data_path(value: str, base_dir: Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else (base_dir / path).resolve()

    def _load_torque_table(self, path: Path) -> tuple[list[float], list[float]]:
        ensure(path.exists(), f"Required torque table CSV not found: {path}")
        theta: list[float] = []
        torque: list[float] = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            ensure(reader.fieldnames is not None, f"CSV file has no header row: {path}")
            theta_key = None
            torque_key = None
            normalized = {self._normalize_header(name): name for name in reader.fieldnames if name}
            for alias in ("theta_deg", "theta", "crank_angle_deg"):
                if alias in normalized:
                    theta_key = normalized[alias]
                    break
            for alias in ("t_lbf_in", "torque_lbf_in", "T_lbf_in", "torque"):
                alias_n = self._normalize_header(alias)
                if alias_n in normalized:
                    torque_key = normalized[alias_n]
                    break
            ensure(theta_key is not None and torque_key is not None, f"Could not identify theta and torque columns in {path}")
            for row in reader:
                theta_raw = row.get(theta_key)
                torque_raw = row.get(torque_key)
                if theta_raw in (None, "") or torque_raw in (None, ""):
                    continue
                theta.append(float(str(theta_raw).strip()))
                torque.append(float(str(torque_raw).strip()))
        ensure(len(theta) >= 2, "Torque table must contain at least two valid rows.")
        combined = sorted(zip(theta, torque), key=lambda x: x[0])
        theta = [a for a, _ in combined]
        torque = [b for _, b in combined]
        for i in range(len(theta) - 1):
            ensure(theta[i + 1] > theta[i], "Torque table crank angles must be strictly increasing.")
        return theta, torque

    @staticmethod
    def _normalize_header(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).strip().casefold()).strip("_")

    @staticmethod
    def _trapz(xs: list[float], ys: list[float]) -> float:
        ensure(len(xs) == len(ys) and len(xs) >= 2, "Trapezoidal integration requires equal-length vectors with at least two points.")
        total = 0.0
        for i in range(len(xs) - 1):
            total += 0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i])
        return total

    def _integrate_between(self, theta_deg: list[float], values: list[float], start_deg: float, end_deg: float) -> float:
        ensure(theta_deg[0] <= start_deg < end_deg <= theta_deg[-1], "Requested fluctuation interval must lie inside the torque-table domain.")
        sample_theta = []
        sample_values = []
        all_breaks = [start_deg] + [x for x in theta_deg if start_deg < x < end_deg] + [end_deg]
        for deg in all_breaks:
            sample_theta.append(deg_to_rad(deg))
            sample_values.append(self._interp_piecewise(theta_deg, values, deg))
        return self._trapz(sample_theta, sample_values)

    @staticmethod
    def _interp_piecewise(xs: list[float], ys: list[float], xq: float) -> float:
        ensure(len(xs) == len(ys) and len(xs) >= 2, "Piecewise interpolation vectors are invalid.")
        ensure(xs[0] <= xq <= xs[-1], "Interpolation query lies outside the data domain.")
        for i in range(len(xs) - 1):
            x0, x1 = xs[i], xs[i + 1]
            if abs(xq - x0) <= 1e-12:
                return ys[i]
            if x0 <= xq <= x1:
                y0, y1 = ys[i], ys[i + 1]
                return y0 + (xq - x0) * (y1 - y0) / (x1 - x0)
        return ys[-1]
