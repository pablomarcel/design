from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

import sympy as sp

from utils import project_root, vec_add, vec_cross, vec_mag_dict, vec_magnitude, vec_scale, vec_unit

AXES = ["x", "y", "z"]
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


@dataclass
class ForceVector:
    name: str
    position: List[float]
    vector: List[float]
    kind: str = "applied_force"


class BaseGearSolver:
    solve_path: str = "base"

    def __init__(self, problem: Dict[str, Any]) -> None:
        self.problem = problem
        self.data_dir = project_root() / "data"

    def solve(self) -> Dict[str, Any]:
        raise NotImplementedError

    def hp_to_tangential_load_lbf(self, horsepower: float, pitch_line_velocity_ft_min: float) -> float:
        return 33000.0 * horsepower / pitch_line_velocity_ft_min

    def kw_to_tangential_load_N(self, power_kw: float, pitch_line_velocity_m_s: float) -> float:
        return power_kw * 1000.0 / pitch_line_velocity_m_s

    def compose_force(self, magnitudes: Dict[str, float], directions: Dict[str, Sequence[float]]) -> List[float]:
        force = [0.0, 0.0, 0.0]
        for key, mag in magnitudes.items():
            u = vec_unit(directions[key])
            force = vec_add(force, vec_scale(mag, u))
        return force

    def _build_validation_block(self, actual: Dict[str, Any], expected: Dict[str, Any] | None) -> Dict[str, Any]:
        if not expected:
            return {}

        comparisons: Dict[str, Any] = {}
        all_within = True

        def compare_map(actual_map: Dict[str, Any], expected_map: Dict[str, Any], prefix: str = "") -> None:
            nonlocal all_within
            for key, exp in expected_map.items():
                label = f"{prefix}.{key}" if prefix else key
                if isinstance(exp, dict):
                    act_sub = actual_map.get(key, {})
                    if isinstance(act_sub, dict):
                        compare_map(act_sub, exp, label)
                    else:
                        comparisons[label] = {
                            "expected": exp,
                            "actual": act_sub,
                            "status": "missing_or_type_mismatch",
                        }
                        all_within = False
                    continue

                act = actual_map.get(key)
                if isinstance(exp, (int, float)) and isinstance(act, (int, float)):
                    abs_diff = float(act) - float(exp)
                    rel_pct = 0.0 if float(exp) == 0.0 else (abs(abs_diff) / abs(float(exp)) * 100.0)
                    status = "ok" if rel_pct <= 2.0 else "check"
                    comparisons[label] = {
                        "expected": float(exp),
                        "actual": float(act),
                        "abs_diff": abs_diff,
                        "rel_diff_percent": rel_pct,
                        "status": status,
                    }
                    if status != "ok":
                        all_within = False
                else:
                    status = "ok" if act == exp else "check"
                    comparisons[label] = {
                        "expected": exp,
                        "actual": act,
                        "status": status,
                    }
                    if status != "ok":
                        all_within = False

        compare_map(actual, expected)
        return {
            "has_expected_reference": True,
            "all_numeric_values_within_2_percent": all_within,
            "comparisons": comparisons,
        }

    def solve_statics(
        self,
        supports: List[Dict[str, Any]],
        loads: List[ForceVector],
        moments: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        moments = moments or []
        unknown_syms: List[sp.Symbol] = []
        support_unknowns: Dict[str, Dict[str, sp.Symbol]] = {}
        equations: List[sp.Expr] = []

        total_force_expr = [sp.Integer(0), sp.Integer(0), sp.Integer(0)]
        total_moment_expr = [sp.Integer(0), sp.Integer(0), sp.Integer(0)]

        for support in supports:
            pos = support["position"]
            comp_map: Dict[str, sp.Symbol] = {}
            for axis in AXES:
                if support.get("allow_components", {}).get(axis, False):
                    sym = sp.symbols(f"R_{support['name']}_{axis}")
                    comp_map[axis] = sym
                    unknown_syms.append(sym)
            support_unknowns[support["name"]] = comp_map
            rvec = [sp.Float(pos[0]), sp.Float(pos[1]), sp.Float(pos[2])]
            fvec = [comp_map.get("x", 0), comp_map.get("y", 0), comp_map.get("z", 0)]
            for i in range(3):
                total_force_expr[i] += fvec[i]
            m = vec_cross(rvec, fvec)
            for i in range(3):
                total_moment_expr[i] += m[i]

        for load in loads:
            rvec = [sp.Float(load.position[0]), sp.Float(load.position[1]), sp.Float(load.position[2])]
            fvec = [sp.Float(load.vector[0]), sp.Float(load.vector[1]), sp.Float(load.vector[2])]
            for i in range(3):
                total_force_expr[i] += fvec[i]
            m = vec_cross(rvec, fvec)
            for i in range(3):
                total_moment_expr[i] += m[i]

        moment_unknowns: Dict[str, sp.Symbol] = {}
        for moment in moments:
            axis = moment["axis"]
            name = moment["name"]
            sym = sp.symbols(name)
            unknown_syms.append(sym)
            moment_unknowns[name] = sym
            idx = AXIS_INDEX[axis]
            total_moment_expr[idx] += sym

        equations.extend(total_force_expr)
        equations.extend(total_moment_expr)
        solution = sp.solve(equations, unknown_syms, dict=True)
        if not solution:
            raise ValueError("Statics system did not yield a solution. Check support constraints and geometry.")
        sol = solution[0]

        reactions: Dict[str, Dict[str, float]] = {}
        reaction_magnitudes: Dict[str, Dict[str, float]] = {}
        for support in supports:
            comp = support_unknowns[support["name"]]
            vec = {
                axis: float(sol.get(sym, 0.0)) if sym else 0.0
                for axis, sym in ((a, comp.get(a)) for a in AXES)
            }
            reactions[support["name"]] = vec
            reaction_magnitudes[support["name"]] = vec_mag_dict(vec)

        solved_moments = {name: float(sol[sym]) for name, sym in moment_unknowns.items()}
        applied_loads = [
            {
                "name": load.name,
                "position": load.position,
                "vector": load.vector,
                "magnitude": vec_magnitude(load.vector),
                "kind": load.kind,
            }
            for load in loads
        ]
        return {
            "reactions": reactions,
            "reaction_magnitudes": reaction_magnitudes,
            "solved_moments": solved_moments,
            "applied_loads": applied_loads,
            "equations_count": len(equations),
        }


class SpurForceSolver(BaseGearSolver):
    solve_path = "spur_force"

    def solve(self) -> Dict[str, Any]:
        p = self.problem["inputs"]
        selected = p["selected_gear"]
        module_mm = float(p["module_mm"])
        pressure_angle_deg = float(p["pressure_angle_deg"])
        power_kw = float(p["power_kw"])
        driver_id = p["driver_gear_id"]
        driver = p["gears"][driver_id]
        driver_speed_rpm = float(driver["speed_rpm"])
        driver_pitch_diameter_mm = float(driver["teeth"]) * module_mm
        pitch_line_velocity_m_s = math.pi * (driver_pitch_diameter_mm / 1000.0) * driver_speed_rpm / 60.0
        Wt_N = self.kw_to_tangential_load_N(power_kw, pitch_line_velocity_m_s)
        Wr_N = Wt_N * math.tan(math.radians(pressure_angle_deg))
        W_N = Wt_N / math.cos(math.radians(pressure_angle_deg))

        forces: List[Dict[str, Any]] = []
        resultant = [0.0, 0.0, 0.0]
        for mesh in p["meshes_on_selected_gear"]:
            force = self.compose_force(
                {"tangential": Wt_N, "radial": Wr_N},
                {
                    "tangential": mesh["tangential_unit_on_selected"],
                    "radial": mesh["radial_unit_on_selected"],
                },
            )
            resultant = vec_add(resultant, force)
            forces.append(
                {
                    "mesh": mesh["name"],
                    "position_mm": mesh.get("position_mm", [0.0, 0.0, 0.0]),
                    "vector_N": force,
                    "vector_magnitude_N": vec_magnitude(force),
                    "tangential_magnitude_N": Wt_N,
                    "radial_magnitude_N": Wr_N,
                    "total_tooth_force_N": W_N,
                }
            )

        shaft_reaction = [-x for x in resultant]
        shaft_reaction_resultant = vec_magnitude(shaft_reaction)
        outputs = {
            "resultant_force_on_selected_gear_N": resultant,
            "resultant_force_on_selected_gear_magnitude_N": vec_magnitude(resultant),
            "shaft_reaction_at_center_N": shaft_reaction,
            "shaft_reaction_resultant_N": shaft_reaction_resultant,
            "shaft_reaction_component_magnitudes_N": {
                "x": abs(shaft_reaction[0]),
                "y": abs(shaft_reaction[1]),
                "z": abs(shaft_reaction[2]),
            },
        }

        actual_reference = {
            "driver_pitch_diameter_mm": driver_pitch_diameter_mm,
            "transmitted_tangential_load_N": Wt_N,
            "radial_load_N": Wr_N,
            "normal_tooth_force_N": W_N,
            "shaft_reaction_component_x_N": abs(shaft_reaction[0]),
            "shaft_reaction_component_y_N": abs(shaft_reaction[1]),
            "shaft_resultant_reaction_N": shaft_reaction_resultant,
        }
        validation = self._build_validation_block(actual_reference, p.get("expected_textbook_reference_values"))

        return {
            "problem": self.solve_path,
            "title": self.problem.get("title", "Spur force analysis"),
            "inputs": p,
            "derived": {
                "selected_gear": selected,
                "driver_pitch_diameter_mm": driver_pitch_diameter_mm,
                "pitch_line_velocity_m_per_s": pitch_line_velocity_m_s,
                "transmitted_tangential_load_N": Wt_N,
                "radial_load_N": Wr_N,
                "normal_tooth_force_N": W_N,
            },
            "mesh_forces": forces,
            "outputs": outputs,
            "validation": validation,
        }


class BevelForceSolver(BaseGearSolver):
    solve_path = "bevel_force"

    def solve(self) -> Dict[str, Any]:
        p = self.problem["inputs"]
        horsepower = float(p["power_hp"])
        speed_rpm = float(p["pinion_speed_rpm"])
        pressure_angle_deg = float(p["pressure_angle_deg"])
        use_gear_angle = p.get("analyze_member", "gear") == "gear"

        pag = p.get("pitch_angle_geometry", {})
        r_pinion_in = float(pag.get("average_pitch_radius_pinion_in", p.get("average_pitch_radius_pinion_in")))
        r_gear_in = float(pag.get("average_pitch_radius_gear_in", p.get("average_pitch_radius_gear_in")))

        tli = p.get("transmitted_load_inputs", {})
        pitch_line_velocity_radius_in = float(tli.get("pitch_line_velocity_radius_in", r_pinion_in))

        gamma_deg = math.degrees(math.atan(r_pinion_in / r_gear_in))
        Gamma_deg = math.degrees(math.atan(r_gear_in / r_pinion_in))
        used_angle_deg = Gamma_deg if use_gear_angle else gamma_deg

        V_ft_min = 2.0 * math.pi * pitch_line_velocity_radius_in * speed_rpm / 12.0
        Wt = self.hp_to_tangential_load_lbf(horsepower, V_ft_min)
        Wr = Wt * math.tan(math.radians(pressure_angle_deg)) * math.cos(math.radians(used_angle_deg))
        Wa = Wt * math.tan(math.radians(pressure_angle_deg)) * math.sin(math.radians(used_angle_deg))

        force = self.compose_force(
            {"tangential": Wt, "radial": Wr, "axial": Wa},
            {
                "tangential": p["force_directions"]["tangential_unit"],
                "radial": p["force_directions"]["radial_unit"],
                "axial": p["force_directions"]["axial_unit"],
            },
        )

        load = ForceVector(name="gear_mesh", position=p["load_position_in"], vector=force)
        statics = self.solve_statics(p["supports"], [load], moments=p.get("unknown_moments", []))

        actual_reference = {
            "pitch_line_velocity_ft_per_min": V_ft_min,
            "transmitted_tangential_load_lbf": Wt,
            "radial_load_lbf": Wr,
            "axial_load_lbf": Wa,
            "reaction_C_lbf": statics["reactions"].get("C", {}),
            "reaction_D_lbf": statics["reactions"].get("D", {}),
        }
        validation = self._build_validation_block(actual_reference, p.get("expected_textbook_reference_values"))

        return {
            "problem": self.solve_path,
            "title": self.problem.get("title", "Bevel force analysis"),
            "inputs": p,
            "derived": {
                "pitch_angle_geometry": {
                    "average_pitch_radius_pinion_in": r_pinion_in,
                    "average_pitch_radius_gear_in": r_gear_in,
                    "gamma_deg": gamma_deg,
                    "Gamma_deg": Gamma_deg,
                    "used_pitch_angle_deg": used_angle_deg,
                },
                "transmitted_load_geometry": {
                    "pitch_line_velocity_radius_in": pitch_line_velocity_radius_in,
                    "pitch_line_velocity_ft_per_min": V_ft_min,
                    "transmitted_tangential_load_lbf": Wt,
                    "radial_load_lbf": Wr,
                    "axial_load_lbf": Wa,
                },
                "statics_geometry": {
                    "load_position_in": p["load_position_in"],
                    "support_positions": {s["name"]: s["position"] for s in p["supports"]},
                },
                "gear_force_vector_lbf": force,
                "gear_force_resultant_lbf": vec_magnitude(force),
            },
            "outputs": statics,
            "validation": validation,
        }


class HelicalForceSolver(BaseGearSolver):
    solve_path = "helical_force"

    def solve(self) -> Dict[str, Any]:
        p = self.problem["inputs"]
        horsepower = float(p["power_hp"])
        speed_rpm = float(p["pinion_speed_rpm"])
        teeth = float(p["pinion_teeth"])
        phi_n_deg = float(p["normal_pressure_angle_deg"])
        psi_deg = float(p["helix_angle_deg"])
        Pn = float(p["normal_diametral_pitch_teeth_per_in"])

        phi_t_deg = math.degrees(math.atan(math.tan(math.radians(phi_n_deg)) / math.cos(math.radians(psi_deg))))
        Pt = Pn * math.cos(math.radians(psi_deg))
        dp = teeth / Pt
        V_ft_min = math.pi * dp * speed_rpm / 12.0
        Wt = self.hp_to_tangential_load_lbf(horsepower, V_ft_min)
        Wr = Wt * math.tan(math.radians(phi_t_deg))
        Wa = Wt * math.tan(math.radians(psi_deg))
        W = Wt / (math.cos(math.radians(phi_n_deg)) * math.cos(math.radians(psi_deg)))

        force = self.compose_force(
            {"tangential": Wt, "radial": Wr, "axial": Wa},
            {
                "tangential": p["force_directions"]["tangential_unit"],
                "radial": p["force_directions"]["radial_unit"],
                "axial": p["force_directions"]["axial_unit"],
            },
        )
        load = ForceVector(name="gear_mesh", position=p["load_position_in"], vector=force)
        statics = self.solve_statics(p["supports"], [load], moments=p.get("unknown_moments", []))
        torque_lbf_in = Wt * float(p["pitch_radius_in"])

        actual_reference = {
            "transverse_pressure_angle_deg": phi_t_deg,
            "transverse_diametral_pitch_teeth_per_in": Pt,
            "pitch_diameter_in": dp,
            "pitch_line_velocity_ft_per_min": V_ft_min,
            "transmitted_tangential_load_lbf": Wt,
            "radial_load_lbf": Wr,
            "axial_load_lbf": Wa,
            "normal_tooth_force_lbf": W,
        }
        validation = self._build_validation_block(actual_reference, p.get("expected_textbook_reference_values"))

        return {
            "problem": self.solve_path,
            "title": self.problem.get("title", "Helical force analysis"),
            "inputs": p,
            "derived": {
                "transverse_pressure_angle_deg": phi_t_deg,
                "transverse_diametral_pitch_teeth_per_in": Pt,
                "pitch_diameter_in": dp,
                "pitch_line_velocity_ft_per_min": V_ft_min,
                "transmitted_tangential_load_lbf": Wt,
                "radial_load_lbf": Wr,
                "axial_load_lbf": Wa,
                "normal_tooth_force_lbf": W,
                "gear_force_vector_lbf": force,
                "gear_force_component_magnitudes_lbf": {
                    "x": abs(force[0]),
                    "y": abs(force[1]),
                    "z": abs(force[2]),
                },
                "gear_force_resultant_lbf": vec_magnitude(force),
                "applied_torque_from_Wt_lbf_in": torque_lbf_in,
            },
            "outputs": {
                **statics,
                "sign_convention_notes": [
                    "Reaction vectors are reported with algebraic signs in the chosen global coordinate system.",
                    "Use reaction_magnitudes for textbook-style component comparison when the book reports magnitudes with implied directions from the free-body diagram.",
                ],
            },
            "validation": validation,
        }


class WormForceSolver(BaseGearSolver):
    solve_path = "worm_force"

    def _read_friction_curve(self, curve_name: str) -> List[Dict[str, float]]:
        path = self.data_dir / "figure_13_42.csv"
        if not path.exists():
            path = project_root().parent / "figure_13_42.csv"
        rows = []
        with path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(
                    {
                        "Vs": float(row["sliding_velocity_ft_per_min"]),
                        "A": float(row["friction_coefficient_curve_A"]),
                        "B": float(row["friction_coefficient_curve_B"]),
                    }
                )
        rows.sort(key=lambda r: r["Vs"])
        if curve_name not in ("A", "B"):
            raise ValueError("curve_name must be 'A' or 'B'")
        return rows

    def _interp_friction(self, curve_name: str, Vs: float) -> float:
        rows = self._read_friction_curve(curve_name)
        if Vs <= rows[0]["Vs"]:
            return rows[0][curve_name]
        if Vs >= rows[-1]["Vs"]:
            return rows[-1][curve_name]
        for lo, hi in zip(rows[:-1], rows[1:]):
            if lo["Vs"] <= Vs <= hi["Vs"]:
                t = (Vs - lo["Vs"]) / (hi["Vs"] - lo["Vs"])
                return lo[curve_name] + t * (hi[curve_name] - lo[curve_name])
        raise RuntimeError("Interpolation failed")

    def solve(self) -> Dict[str, Any]:
        p = self.problem["inputs"]
        horsepower = float(p["power_hp"])
        n_w = float(p["worm_speed_rpm"])
        N_w = float(p["worm_threads"])
        N_g = float(p["gear_teeth"])
        P_t = float(p["transverse_diametral_pitch_teeth_per_in"])
        d_w = float(p["worm_pitch_diameter_in"])
        phi_n_deg = float(p["normal_pressure_angle_deg"])

        p_x = math.pi / P_t
        d_g = N_g / P_t
        center_distance = 0.5 * (d_w + d_g)
        lead = p_x * N_w
        lambda_deg = math.degrees(math.atan(lead / (math.pi * d_w)))
        V_w = math.pi * d_w * n_w / 12.0
        n_g = (N_w / N_g) * n_w
        V_g = math.pi * d_g * n_g / 12.0
        V_s = V_w / math.cos(math.radians(lambda_deg))
        friction_curve = p.get("friction_curve", "B")
        f = self._interp_friction(friction_curve, V_s)
        W_wt = self.hp_to_tangential_load_lbf(horsepower, V_w)
        W = W_wt / (
            math.cos(math.radians(phi_n_deg)) * math.sin(math.radians(lambda_deg))
            + f * math.cos(math.radians(lambda_deg))
        )
        W_y = W * math.sin(math.radians(phi_n_deg))
        W_z = W * (
            math.cos(math.radians(phi_n_deg)) * math.cos(math.radians(lambda_deg))
            - f * math.sin(math.radians(lambda_deg))
        )
        gear_force = self.compose_force(
            {"axial": W_wt, "radial": -W_y, "tangential": -W_z},
            {
                "axial": p["gear_force_directions"]["axial_unit"],
                "radial": p["gear_force_directions"]["radial_unit"],
                "tangential": p["gear_force_directions"]["tangential_unit"],
            },
        )
        load = ForceVector(name="gear_mesh", position=p["load_position_in"], vector=gear_force)
        statics = self.solve_statics(p["supports"], [load], moments=p.get("unknown_moments", []))
        efficiency = (
            math.cos(math.radians(phi_n_deg)) - f * math.tan(math.radians(lambda_deg))
        ) / (
            math.cos(math.radians(phi_n_deg)) + f / math.tan(math.radians(lambda_deg))
        )
        return {
            "problem": self.solve_path,
            "title": self.problem.get("title", "Worm force analysis"),
            "inputs": p,
            "derived": {
                "axial_pitch_in": p_x,
                "gear_pitch_diameter_in": d_g,
                "center_distance_in": center_distance,
                "lead_in": lead,
                "lead_angle_deg": lambda_deg,
                "worm_pitch_line_velocity_ft_per_min": V_w,
                "gear_speed_rpm": n_g,
                "gear_pitch_line_velocity_ft_per_min": V_g,
                "sliding_velocity_ft_per_min": V_s,
                "friction_coefficient": f,
                "worm_tangential_load_lbf": W_wt,
                "normal_tooth_force_lbf": W,
                "W_y_lbf": W_y,
                "W_z_lbf": W_z,
                "gear_force_vector_lbf": gear_force,
                "gear_force_resultant_lbf": vec_magnitude(gear_force),
                "efficiency": efficiency,
            },
            "outputs": statics,
        }


SOLVER_REGISTRY = {
    SpurForceSolver.solve_path: SpurForceSolver,
    BevelForceSolver.solve_path: BevelForceSolver,
    HelicalForceSolver.solve_path: HelicalForceSolver,
    WormForceSolver.solve_path: WormForceSolver,
}
