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
        mu = float(payload["mu"])
        p_a = float(payload["p_a"])
        b = float(payload["b"])
        r = float(payload["r"])
        a = float(payload["a"])
        c = float(payload["c"])
        theta1_deg = float(payload["theta1_deg"])
        theta2_deg = float(payload["theta2_deg"])
        theta_a_deg = float(payload.get("theta_a_deg", 90.0))
        rotation = payload.get("rotation", "clockwise")
        force_units = payload.get("actuator_force_units", payload.get("force_units", "auto"))
        Fx_raw = float(payload.get("Fx", 0.0))
        Fy_raw = float(payload.get("Fy", 0.0))
        paired_shoe = payload.get("paired_shoe")

        ensure(mu >= 0 and p_a > 0 and b > 0 and r > 0 and a > 0 and c > 0, "Invalid rim-brake inputs.")
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
        Fx, Fy, force_unit_note = self._normalize_force_components(Fx_raw, Fy_raw, D, force_units)

        M_f = mu * D * (r * (math.cos(th1) - math.cos(th2)) - a * A)
        M_n = D * a * B
        if rotation == "clockwise":
            F = (M_n - M_f) / c
            R_x = D * (A - mu * B) - Fx
            R_y = D * (B + mu * A) - Fy
        else:
            F = (M_n + M_f) / c
            R_x = D * (A + mu * B) + Fx
            R_y = D * (B - mu * A) - Fy

        T = mu * p_a * b * (r ** 2) * (math.cos(th1) - math.cos(th2)) / stha
        resultant = math.hypot(R_x, R_y)
        self_locking_margin = M_n - M_f

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

        notes = []
        if rotation == "clockwise":
            notes.append("Clockwise rotation uses the self-energizing form F = (M_n - M_f)/c.")
        else:
            notes.append("Counterclockwise rotation uses the de-energized form F = (M_n + M_f)/c.")
        if force_unit_note:
            notes.append(force_unit_note)

        derived = {
            "theta1_rad": th1,
            "theta2_rad": th2,
            "theta_a_rad": tha,
            "Fx_used": Fx,
            "Fy_used": Fy,
            "actuator_force_units_used": "N",
        }

        if paired_shoe:
            pair = self._solve_paired_shoe(F, paired_shoe)
            outputs["paired_shoe"] = pair
            outputs["total_torque_pair"] = T + pair["torque_T"]

        return SolveResult(
            problem_type=self.problem_type,
            title=self.title,
            inputs=payload,
            outputs=outputs,
            derived=derived,
            notes=notes,
        )

    def _normalize_force_components(self, Fx_raw: float, Fy_raw: float, D_force_scale: float, force_units: str) -> tuple[float, float, str | None]:
        ensure(force_units in {"auto", "N", "kN"}, "actuator_force_units must be one of: auto, N, kN.")
        if force_units == "N":
            return Fx_raw, Fy_raw, None
        if force_units == "kN":
            return 1000.0 * Fx_raw, 1000.0 * Fy_raw, "Converted actuator force components from kN to N."

        # Auto-detect for textbook-style inputs where p_a is in Pa and geometry in meters,
        # but actuator components are often entered from the textbook in kN.
        force_mag = max(abs(Fx_raw), abs(Fy_raw))
        if D_force_scale > 100.0 and force_mag < 50.0:
            return 1000.0 * Fx_raw, 1000.0 * Fy_raw, "Auto-detected actuator force components as kN and converted to N."
        return Fx_raw, Fy_raw, None

    def _solve_paired_shoe(self, target_F: float, pair_payload: Dict[str, Any]) -> Dict[str, Any]:
        mu = float(pair_payload["mu"])
        b = float(pair_payload["b"])
        r = float(pair_payload["r"])
        a = float(pair_payload["a"])
        c = float(pair_payload["c"])
        theta1_deg = float(pair_payload["theta1_deg"])
        theta2_deg = float(pair_payload["theta2_deg"])
        theta_a_deg = float(pair_payload.get("theta_a_deg", 90.0))
        rotation = pair_payload.get("rotation", "counterclockwise")
        force_units = pair_payload.get("actuator_force_units", pair_payload.get("force_units", "auto"))
        Fx_raw = float(pair_payload.get("Fx", 0.0))
        Fy_raw = float(pair_payload.get("Fy", 0.0))

        th1 = deg_to_rad(theta1_deg)
        th2 = deg_to_rad(theta2_deg)
        tha = deg_to_rad(theta_a_deg)
        stha = math.sin(tha)
        A = 0.5 * (math.sin(th2) ** 2 - math.sin(th1) ** 2)
        B = (th2 - th1) / 2.0 - (math.sin(2.0 * th2) - math.sin(2.0 * th1)) / 4.0

        coeff_Mf = mu * b * r / stha * (r * (math.cos(th1) - math.cos(th2)) - a * A)
        coeff_Mn = b * r / stha * a * B
        if rotation == "clockwise":
            coeff_F = (coeff_Mn - coeff_Mf) / c
        else:
            coeff_F = (coeff_Mn + coeff_Mf) / c
        ensure(abs(coeff_F) > 1e-12, "Paired shoe produces zero F coefficient; cannot back-solve pressure.")
        p_a = target_F / coeff_F

        D = p_a * b * r / stha
        Fx, Fy, force_unit_note = self._normalize_force_components(Fx_raw, Fy_raw, D, force_units)
        M_f = coeff_Mf * p_a
        M_n = coeff_Mn * p_a
        if rotation == "clockwise":
            R_x = D * (A - mu * B) - Fx
            R_y = D * (B + mu * A) - Fy
        else:
            R_x = D * (A + mu * B) + Fx
            R_y = D * (B - mu * A) - Fy
        T = mu * p_a * b * (r ** 2) * (math.cos(th1) - math.cos(th2)) / stha
        out = {
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
            "Fx_used": Fx,
            "Fy_used": Fy,
            "actuator_force_units_used": "N",
        }
        if force_unit_note:
            out["force_unit_note"] = force_unit_note
        return out


class AnnularPadCaliperSolver(SolverBase):
    problem_type = "annular_pad"
    title = "Annular-pad caliper brake"

    def solve(self, payload: Dict[str, Any]) -> SolveResult:
        mu = float(payload["mu"])
        ri = float(payload["ri"])
        ro = float(payload["ro"])
        theta1_deg = float(payload.get("theta1_deg", 0.0))
        theta2_deg = float(payload["theta2_deg"])
        model = payload.get("model", "uniform_wear")
        n_pads = int(payload.get("n_pads", 2))
        ensure(mu >= 0 and ri > 0 and ro > ri, "Invalid annular-pad geometry.")
        ensure(model in {"uniform_wear", "uniform_pressure"}, "model must be uniform_wear or uniform_pressure.")
        ensure(n_pads >= 1, "n_pads must be >= 1.")
        th1 = deg_to_rad(theta1_deg)
        th2 = deg_to_rad(theta2_deg)
        theta_span = th2 - th1
        ensure(theta_span > 0, "theta2 must exceed theta1.")

        notes = []

        if model == "uniform_wear":
            torque_coeff_per_pad = 0.5 * theta_span * mu * ri * (ro ** 2 - ri ** 2)
            force_coeff = theta_span * ri * (ro - ri)
            re = 0.5 * (ro + ri)
            rbar = ((math.cos(th1) - math.cos(th2)) / theta_span) * re
        else:
            torque_coeff_per_pad = (1.0 / 3.0) * theta_span * mu * (ro ** 3 - ri ** 3)
            force_coeff = 0.5 * theta_span * (ro ** 2 - ri ** 2)
            re = (2.0 / 3.0) * (ro ** 3 - ri ** 3) / (ro ** 2 - ri ** 2)
            rbar = ((math.cos(th1) - math.cos(th2)) / theta_span) * re

        pa = payload.get("p_a")
        F = payload.get("F")
        torque_total = payload.get("torque_total")

        if pa is None:
            if torque_total is not None:
                pa = float(torque_total) / (n_pads * torque_coeff_per_pad)
                notes.append("Solved p_a from total torque requirement.")
            elif F is not None:
                pa = float(F) / force_coeff
                notes.append("Solved p_a from actuating force per pad.")
            else:
                raise ValidationError("Provide at least one of p_a, F, or torque_total.")
        pa = float(pa)
        ensure(pa > 0, "p_a must be positive.")

        if F is None:
            F = force_coeff * pa
        F = float(F)

        torque_per_pad = torque_coeff_per_pad * pa
        torque_total_calc = n_pads * torque_per_pad

        hydraulic_pressure = None
        cyl_area_total = None
        if payload.get("cylinder_diameter") is not None:
            d_cyl = float(payload["cylinder_diameter"])
            n_cylinders = int(payload.get("n_cylinders", 1))
            ensure(d_cyl > 0 and n_cylinders >= 1, "Invalid hydraulic cylinder definition.")
            cyl_area_total = n_cylinders * math.pi * d_cyl ** 2 / 4.0
            hydraulic_pressure = F / cyl_area_total
            if n_cylinders == 1:
                notes.append("Hydraulic pressure uses one cylinder area. Example 16-3 uses a pair of cylinders, so set n_cylinders=2 to match the textbook statement.")

        outputs = {
            "p_a": pa,
            "F_per_pad": F,
            "torque_per_pad": torque_per_pad,
            "torque_total": torque_total_calc,
            "effective_radius_re": re,
            "force_location_rbar": rbar,
            "theta_span_deg": math.degrees(theta_span),
        }
        if hydraulic_pressure is not None:
            outputs["hydraulic_pressure"] = hydraulic_pressure
            outputs["total_cylinder_area"] = cyl_area_total

        return SolveResult(
            problem_type=self.problem_type,
            title=self.title,
            inputs=payload,
            outputs=outputs,
            derived={
                "theta1_rad": th1,
                "theta2_rad": th2,
                "theta_span_rad": theta_span,
                "force_coefficient": force_coeff,
                "torque_coefficient_per_pad": torque_coeff_per_pad,
            },
            notes=notes,
        )
