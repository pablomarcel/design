from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

import sympy as sp

from utils import project_root, vec_add, vec_cross, vec_scale, vec_unit

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

    def solve_statics(self, supports: List[Dict[str, Any]], loads: List[ForceVector], moments: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
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
        for support in supports:
            comp = support_unknowns[support["name"]]
            reactions[support["name"]] = {
                axis: float(sol.get(sym, 0.0)) if sym else 0.0
                for axis, sym in ((a, comp.get(a)) for a in AXES)
            }

        solved_moments = {name: float(sol[sym]) for name, sym in moment_unknowns.items()}
        return {
            "reactions": reactions,
            "solved_moments": solved_moments,
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
                    "tangential_magnitude_N": Wt_N,
                    "radial_magnitude_N": Wr_N,
                    "total_tooth_force_N": W_N,
                }
            )

        shaft_reaction = [-x for x in resultant]
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
            "outputs": {
                "resultant_force_on_selected_gear_N": resultant,
                "shaft_reaction_at_center_N": shaft_reaction,
            },
        }


class BevelForceSolver(BaseGearSolver):
    solve_path = "bevel_force"

    def solve(self) -> Dict[str, Any]:
        p = self.problem["inputs"]
        horsepower = float(p["power_hp"])
        speed_rpm = float(p["pinion_speed_rpm"])
        pressure_angle_deg = float(p["pressure_angle_deg"])
        r_pinion_in = float(p["average_pitch_radius_pinion_in"])
        r_gear_in = float(p["average_pitch_radius_gear_in"])
        use_gear_angle = p.get("analyze_member", "gear") == "gear"

        gamma_deg = math.degrees(math.atan(r_pinion_in / r_gear_in))
        Gamma_deg = math.degrees(math.atan(r_gear_in / r_pinion_in))
        used_angle_deg = Gamma_deg if use_gear_angle else gamma_deg
        V_ft_min = 2.0 * math.pi * r_pinion_in * speed_rpm / 12.0
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
        return {
            "problem": self.solve_path,
            "title": self.problem.get("title", "Bevel force analysis"),
            "inputs": p,
            "derived": {
                "gamma_deg": gamma_deg,
                "Gamma_deg": Gamma_deg,
                "pitch_line_velocity_ft_per_min": V_ft_min,
                "transmitted_tangential_load_lbf": Wt,
                "radial_load_lbf": Wr,
                "axial_load_lbf": Wa,
                "gear_force_vector_lbf": force,
            },
            "outputs": statics,
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
                "applied_torque_from_Wt_lbf_in": torque_lbf_in,
            },
            "outputs": statics,
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
