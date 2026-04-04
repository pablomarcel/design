from __future__ import annotations

import math
from dataclasses import dataclass
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
            # Shigley Example 16-1(c),(d): p(u) = C2 (c + u)
            # The moment contribution of the friction term includes mu and was the source of the old scaling bug.
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

        # Eqs. (16-8), (16-2), (16-3)
        A = 0.5 * (math.sin(th2) ** 2 - math.sin(th1) ** 2)
        B = (th2 - th1) / 2.0 - (math.sin(2.0 * th2) - math.sin(2.0 * th1)) / 4.0
        D = p_a * b * r / stha
        M_f = mu * D * (r * (math.cos(th1) - math.cos(th2)) - a * A)
        M_n = D * a * B

        # Eq. (16-4)
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

        # Eq. (16-6)
        T = mu * p_a * b * (r ** 2) * (math.cos(th1) - math.cos(th2)) / stha

        # Eqs. (16-9) and (16-10) force-resultant forms.
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
            # Backward-compatible path for legacy payloads.
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
            # Example 16-3 states each cylinder supplies the pad actuating force F.
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
