from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from utils import (
    GearDataLookup,
    GearMath,
    ResultBuilder,
    parse_range_text,
    pretty_float,
)


@dataclass
class CommonGearInputs:
    power_hp: float
    pinion_speed_rpm: float
    pinion_teeth: int
    gear_teeth: int
    quality_number: float
    reliability: float
    pinion_cycles: float
    power_source: str
    driven_machine: str
    face_width_in: float | None = None
    temperature_F: float = 70.0
    c_f: float = 1.0
    uncrowned: bool = True
    enclosure_condition: str = "commercial_enclosed_units"
    adjusted_at_assembly: bool = False
    mounting_type: str = "straddle_adjacent"
    kb: float = 1.0


class GearSolverBase:
    def __init__(self, problem: dict[str, Any]) -> None:
        self.problem = problem
        self.lookup = GearDataLookup()
        self.results = ResultBuilder()

    def solve(self) -> dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def dynamic_factor_constants(q_v: float) -> tuple[float, float]:
        b = 0.25 * (12.0 - q_v) ** (2.0 / 3.0)
        a = 50.0 + 56.0 * (1.0 - b)
        return a, b

    @staticmethod
    def dynamic_factor(a: float, b: float, pitchline_velocity_ft_min: float) -> float:
        return ((a + math.sqrt(pitchline_velocity_ft_min)) / a) ** b

    @staticmethod
    def size_factor(face_width_in: float, lewis_y: float, pitch_value: float) -> float:
        return 1.192 * ((face_width_in * math.sqrt(lewis_y)) / pitch_value) ** 0.0535

    @staticmethod
    def c_mc(uncrowned: bool) -> float:
        return 1.0 if uncrowned else 0.8

    @staticmethod
    def c_pf(face_width_in: float, pinion_pitch_diameter_in: float) -> float:
        ratio = face_width_in / (10.0 * pinion_pitch_diameter_in)
        return ratio - 0.025 if ratio <= 0.05 else ratio - 0.0375 + 0.0125 * face_width_in

    @staticmethod
    def c_pm(mounting_type: str) -> float:
        mapping = {
            "straddle_adjacent": 1.0,
            "straddle_offset": 1.1,
            "single_overhung": 1.1,
        }
        if mounting_type not in mapping:
            raise ValueError(f"Unsupported mounting_type={mounting_type!r}")
        return mapping[mounting_type]

    @staticmethod
    def c_ma(face_width_in: float, a: float, b: float, c: float) -> float:
        return a + b * face_width_in + c * face_width_in * face_width_in

    @staticmethod
    def c_e(adjusted_at_assembly: bool) -> float:
        return 0.8 if adjusted_at_assembly else 1.0

    @classmethod
    def km(cls, c_mc: float, c_pf: float, c_pm: float, c_ma: float, c_e: float) -> float:
        return 1.0 + c_mc * (c_pf * c_pm + c_ma * c_e)

    @staticmethod
    def kt(temperature_F: float) -> float:
        return 1.0 if temperature_F < 250.0 else 1.0

    @staticmethod
    def hardness_ratio_factor(hb_p: float, hb_g: float) -> float:
        ratio = hb_p / hb_g
        if ratio < 1.2:
            return 0.0
        if ratio > 1.7:
            return 0.00689
        return 0.00898 * ratio - 0.00829

    @staticmethod
    def ch_for_gear(hb_p: float, hb_g: float, gear_ratio: float) -> float:
        a_prime = GearSolverBase.hardness_ratio_factor(hb_p, hb_g)
        return 1.0 + a_prime * (gear_ratio - 1.0)

    @staticmethod
    def pitchline_velocity(diameter_in: float, speed_rpm: float) -> float:
        return math.pi * diameter_in * speed_rpm / 12.0

    @staticmethod
    def transmitted_tangential_load(power_hp: float, velocity_ft_min: float) -> float:
        return 33000.0 * power_hp / velocity_ft_min

    @staticmethod
    def spur_I(pressure_angle_deg: float, gear_ratio: float) -> float:
        phi = math.radians(pressure_angle_deg)
        return math.cos(phi) * math.sin(phi) / 2.0 * (gear_ratio / (gear_ratio + 1.0))

    @staticmethod
    def helical_transverse_pressure_angle(normal_pressure_angle_deg: float, helix_angle_deg: float) -> float:
        phi_n = math.radians(normal_pressure_angle_deg)
        psi = math.radians(helix_angle_deg)
        return math.degrees(math.atan(math.tan(phi_n) / math.cos(psi)))

    @staticmethod
    def base_circle_radius(radius: float, pressure_angle_deg: float) -> float:
        return radius * math.cos(math.radians(pressure_angle_deg))

    @staticmethod
    def helical_Z(r_p: float, r_g: float, a: float, rb_p: float, rb_g: float, phi_t_deg: float) -> float:
        phi_t = math.radians(phi_t_deg)
        t1 = math.sqrt(max((r_p + a) ** 2 - rb_p**2, 0.0))
        t2 = math.sqrt(max((r_g + a) ** 2 - rb_g**2, 0.0))
        t3 = (r_p + r_g) * math.sin(phi_t)
        t1_eff = min(t1, t3) if t1 > t3 else t1
        t2_eff = min(t2, t3) if t2 > t3 else t2
        return t1_eff + t2_eff - t3

    @staticmethod
    def normal_circular_pitch(normal_diametral_pitch: float, normal_pressure_angle_deg: float) -> float:
        return math.pi / normal_diametral_pitch * math.cos(math.radians(normal_pressure_angle_deg))

    @staticmethod
    def helical_mn(p_n_circular: float, z: float) -> float:
        return p_n_circular / (0.95 * z)

    @staticmethod
    def helical_I(phi_t_deg: float, mn: float, gear_ratio: float) -> float:
        phi_t = math.radians(phi_t_deg)
        return math.sin(phi_t) * math.cos(phi_t) / (2.0 * mn) * (gear_ratio / (gear_ratio + 1.0))

    @staticmethod
    def bending_stress(w_t: float, k_o: float, k_v: float, k_s: float, pitch_value: float, face_width: float, k_m: float, k_b: float, j: float) -> float:
        return w_t * k_o * k_v * k_s * (pitch_value / face_width) * (k_m * k_b / j)

    @staticmethod
    def contact_stress(c_p: float, w_t: float, k_o: float, k_v: float, k_s: float, k_m: float, diameter_p: float, face_width: float, c_f: float, i_factor: float) -> float:
        return c_p * math.sqrt(w_t * k_o * k_v * k_s * (k_m / (diameter_p * face_width)) * (c_f / i_factor))

    @staticmethod
    def bending_factor_of_safety(s_t: float, y_n: float, k_t: float, k_r: float, sigma: float) -> float:
        return (s_t * y_n / (k_t * k_r)) / sigma

    @staticmethod
    def wear_factor_of_safety(s_c: float, z_n: float, c_h: float, k_t: float, k_r: float, sigma_c: float) -> float:
        return (s_c * z_n * c_h / (k_t * k_r)) / sigma_c

    @staticmethod
    def decide_threat(s_f: float, s_h: float) -> str:
        return "wear" if (s_h ** 2) < s_f else "bending"

    def common_analysis_setup(self, p: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        out["gear_ratio"] = p["gear_teeth"] / p["pinion_teeth"]
        out["K_o"] = self.lookup.overload_factor(p["power_source"], p["driven_machine"])
        self.results.add_lookup("K_o", out["K_o"])
        a, b = self.dynamic_factor_constants(p["quality_number"])
        out["A"] = a
        out["B"] = b
        out["K_R"] = self.lookup.reliability_factor(p["reliability"])
        out["K_T"] = self.kt(p.get("temperature_F", 70.0))
        out["Y_P"] = self.lookup.lewis_form_factor(p["pinion_teeth"])
        out["Y_G"] = self.lookup.lewis_form_factor(p["gear_teeth"])
        out["Y_N_P"] = self.lookup.y_n(p["pinion_cycles"], p.get("yn_selection", "upper"))
        out["Y_N_G"] = self.lookup.y_n(p["pinion_cycles"] / out["gear_ratio"], p.get("yn_selection", "upper"))
        out["Z_N_P"] = self.lookup.z_n(p["pinion_cycles"], p.get("zn_selection", "upper"))
        out["Z_N_G"] = self.lookup.z_n(p["pinion_cycles"] / out["gear_ratio"], p.get("zn_selection", "upper"))
        out["C_p"] = self.lookup.cp_for_material_pair(p.get("pinion_cp_material", "Steel"), p.get("gear_cp_material", "Steel"))
        return out


class SpurGearAnalysisSolver(GearSolverBase):
    def solve(self) -> dict[str, Any]:
        p = self.problem
        c = self.common_analysis_setup(p)
        d_p = p["pinion_teeth"] / p["diametral_pitch"]
        d_g = p["gear_teeth"] / p["diametral_pitch"]
        v = self.pitchline_velocity(d_p, p["pinion_speed_rpm"])
        w_t = self.transmitted_tangential_load(p["power_hp"], v)
        k_v = self.dynamic_factor(c["A"], c["B"], v)
        k_s_p = self.size_factor(p["face_width_in"], c["Y_P"], p["diametral_pitch"])
        k_s_g = self.size_factor(p["face_width_in"], c["Y_G"], p["diametral_pitch"])

        table_14_9 = {row["condition"]: row for row in self.lookup.repo.csv_rows("table_14_9.csv")}
        cma_row = table_14_9[p["enclosure_condition_label"]]
        c_mc = self.c_mc(p.get("uncrowned", True))
        c_pf = self.c_pf(p["face_width_in"], d_p)
        c_pm = self.c_pm(p.get("mounting_type", "straddle_adjacent"))
        c_ma = self.c_ma(p["face_width_in"], float(cma_row["A"]), float(cma_row["B"]), float(cma_row["C"]))
        c_e = self.c_e(p.get("adjusted_at_assembly", False))
        k_m = self.km(c_mc, c_pf, c_pm, c_ma, c_e)
        i_factor = self.spur_I(p["pressure_angle_deg"], c["gear_ratio"])

        s_t_p = self.lookup.bending_strength_from_figure("figure_14_2.json", p["pinion_grade"], p["pinion_hb"])
        s_t_g = self.lookup.bending_strength_from_figure("figure_14_2.json", p["gear_grade"], p["gear_hb"])
        s_c_p = self.lookup.contact_strength_from_figure("figure_14_5.json", p["pinion_grade"], p["pinion_hb"])
        s_c_g = self.lookup.contact_strength_from_figure("figure_14_5.json", p["gear_grade"], p["gear_hb"])

        c_h = self.ch_for_gear(p["pinion_hb"], p["gear_hb"], c["gear_ratio"])
        j_p = p.get("J_P") or self.lookup.spur_j(p["pinion_teeth"], p["gear_teeth"])
        j_g = p.get("J_G") or self.lookup.spur_j(p["gear_teeth"], p["pinion_teeth"])

        sigma_p = self.bending_stress(w_t, c["K_o"], k_v, k_s_p, p["diametral_pitch"], p["face_width_in"], k_m, p.get("kb", 1.0), j_p)
        sigma_g = self.bending_stress(w_t, c["K_o"], k_v, k_s_g, p["diametral_pitch"], p["face_width_in"], k_m, p.get("kb", 1.0), j_g)
        sf_p = self.bending_factor_of_safety(s_t_p, c["Y_N_P"], c["K_T"], c["K_R"], sigma_p)
        sf_g = self.bending_factor_of_safety(s_t_g, c["Y_N_G"], c["K_T"], c["K_R"], sigma_g)

        sigma_c_p = self.contact_stress(c["C_p"], w_t, c["K_o"], k_v, k_s_p, k_m, d_p, p["face_width_in"], p.get("c_f", 1.0), i_factor)
        sigma_c_g = self.contact_stress(c["C_p"], w_t, c["K_o"], k_v, k_s_g, k_m, d_p, p["face_width_in"], p.get("c_f", 1.0), i_factor)
        sh_p = self.wear_factor_of_safety(s_c_p, c["Z_N_P"], 1.0, c["K_T"], c["K_R"], sigma_c_p)
        sh_g = self.wear_factor_of_safety(s_c_g, c["Z_N_G"], c_h, c["K_T"], c["K_R"], sigma_c_g)

        self.results.derived.update({
            "d_P_in": pretty_float(d_p),
            "d_G_in": pretty_float(d_g),
            "pitchline_velocity_ft_min": pretty_float(v),
            "transmitted_tangential_load_lbf": pretty_float(w_t),
            "A": pretty_float(c["A"]),
            "B": pretty_float(c["B"]),
            "K_v": pretty_float(k_v),
            "Y_P": pretty_float(c["Y_P"]),
            "Y_G": pretty_float(c["Y_G"]),
            "K_s_P": pretty_float(k_s_p),
            "K_s_G": pretty_float(k_s_g),
            "C_mc": pretty_float(c_mc),
            "C_pf": pretty_float(c_pf),
            "C_pm": pretty_float(c_pm),
            "C_ma": pretty_float(c_ma),
            "C_e": pretty_float(c_e),
            "K_m": pretty_float(k_m),
            "I": pretty_float(i_factor),
            "C_p_sqrt_psi": pretty_float(c["C_p"]),
            "S_t_P_psi": pretty_float(s_t_p),
            "S_t_G_psi": pretty_float(s_t_g),
            "S_c_P_psi": pretty_float(s_c_p),
            "S_c_G_psi": pretty_float(s_c_g),
            "Y_N_P": pretty_float(c["Y_N_P"]),
            "Y_N_G": pretty_float(c["Y_N_G"]),
            "Z_N_P": pretty_float(c["Z_N_P"]),
            "Z_N_G": pretty_float(c["Z_N_G"]),
            "C_H_G": pretty_float(c_h),
            "J_P": pretty_float(j_p),
            "J_G": pretty_float(j_g),
        })
        self.results.outputs.update({
            "sigma_P_psi": pretty_float(sigma_p),
            "sigma_G_psi": pretty_float(sigma_g),
            "S_F_P": pretty_float(sf_p),
            "S_F_G": pretty_float(sf_g),
            "sigma_c_P_psi": pretty_float(sigma_c_p),
            "sigma_c_G_psi": pretty_float(sigma_c_g),
            "S_H_P": pretty_float(sh_p),
            "S_H_G": pretty_float(sh_g),
            "pinion_threat": self.decide_threat(sf_p, sh_p),
            "gear_threat": self.decide_threat(sf_g, sh_g),
            "mesh_threat": "wear" if min(sh_p ** 2, sh_g ** 2) < min(sf_p, sf_g) else "bending",
        })
        return {
            "problem": "spur_analysis",
            "title": p.get("title", "Spur gearset analysis"),
            "inputs": p,
            "lookups": self.results.lookups,
            "derived": self.results.derived,
            "outputs": self.results.outputs,
        }


class HelicalGearAnalysisSolver(GearSolverBase):
    def solve(self) -> dict[str, Any]:
        p = self.problem
        c = self.common_analysis_setup(p)

        k_s_p = self.size_factor(p["face_width_in"], c["Y_P"], p["normal_diametral_pitch"])
        k_s_g = self.size_factor(p["face_width_in"], c["Y_G"], p["normal_diametral_pitch"])

        s_t_p = self.lookup.bending_strength_from_figure("figure_14_2.json", p["pinion_grade"], p["pinion_hb"])
        s_t_g = self.lookup.bending_strength_from_figure("figure_14_2.json", p["gear_grade"], p["gear_hb"])
        s_c_p = self.lookup.contact_strength_from_figure("figure_14_5.json", p["pinion_grade"], p["pinion_hb"])
        s_c_g = self.lookup.contact_strength_from_figure("figure_14_5.json", p["gear_grade"], p["gear_hb"])
        c_h = self.ch_for_gear(p["pinion_hb"], p["gear_hb"], c["gear_ratio"])

        p_t = p["normal_diametral_pitch"] * math.cos(math.radians(p["helix_angle_deg"]))
        d_p = p["pinion_teeth"] / p_t
        d_g = p["gear_teeth"] / p_t
        v = self.pitchline_velocity(d_p, p["pinion_speed_rpm"])
        w_t = self.transmitted_tangential_load(p["power_hp"], v)
        k_v = self.dynamic_factor(c["A"], c["B"], v)

        phi_t = self.helical_transverse_pressure_angle(p["normal_pressure_angle_deg"], p["helix_angle_deg"])
        r_p = d_p / 2.0
        r_g = d_g / 2.0
        a = 1.0 / p["normal_diametral_pitch"]
        rb_p = self.base_circle_radius(r_p, phi_t)
        rb_g = self.base_circle_radius(r_g, phi_t)
        z_geom = self.helical_Z(r_p, r_g, a, rb_p, rb_g, phi_t)
        p_n = self.normal_circular_pitch(p["normal_diametral_pitch"], p["normal_pressure_angle_deg"])
        m_n = self.helical_mn(p_n, z_geom)
        i_factor = self.helical_I(phi_t, m_n, c["gear_ratio"])

        j_prime_p = self.lookup.helical_j_prime(p["helix_angle_deg"], p["pinion_teeth"])
        j_prime_g = self.lookup.helical_j_prime(p["helix_angle_deg"], p["gear_teeth"])
        j_mult_p = self.lookup.helical_j_multiplier(p["helix_angle_deg"], p["gear_teeth"])
        j_mult_g = self.lookup.helical_j_multiplier(p["helix_angle_deg"], p["pinion_teeth"])
        j_p = j_prime_p * j_mult_p
        j_g = j_prime_g * j_mult_g

        table_14_9 = {row["condition"]: row for row in self.lookup.repo.csv_rows("table_14_9.csv")}
        cma_row = table_14_9[p["enclosure_condition_label"]]
        c_mc = self.c_mc(p.get("uncrowned", True))
        c_pf = self.c_pf(p["face_width_in"], d_p)
        c_pm = self.c_pm(p.get("mounting_type", "straddle_adjacent"))
        c_ma = self.c_ma(p["face_width_in"], float(cma_row["A"]), float(cma_row["B"]), float(cma_row["C"]))
        c_e = self.c_e(p.get("adjusted_at_assembly", False))
        k_m = self.km(c_mc, c_pf, c_pm, c_ma, c_e)

        sigma_p = self.bending_stress(w_t, c["K_o"], k_v, k_s_p, p_t, p["face_width_in"], k_m, p.get("kb", 1.0), j_p)
        sigma_g = self.bending_stress(w_t, c["K_o"], k_v, k_s_g, p_t, p["face_width_in"], k_m, p.get("kb", 1.0), j_g)
        sf_p = self.bending_factor_of_safety(s_t_p, c["Y_N_P"], c["K_T"], c["K_R"], sigma_p)
        sf_g = self.bending_factor_of_safety(s_t_g, c["Y_N_G"], c["K_T"], c["K_R"], sigma_g)

        sigma_c_p = self.contact_stress(c["C_p"], w_t, c["K_o"], k_v, k_s_p, k_m, d_p, p["face_width_in"], p.get("c_f", 1.0), i_factor)
        sigma_c_g = self.contact_stress(c["C_p"], w_t, c["K_o"], k_v, k_s_g, k_m, d_p, p["face_width_in"], p.get("c_f", 1.0), i_factor)
        sh_p = self.wear_factor_of_safety(s_c_p, c["Z_N_P"], 1.0, c["K_T"], c["K_R"], sigma_c_p)
        sh_g = self.wear_factor_of_safety(s_c_g, c["Z_N_G"], c_h, c["K_T"], c["K_R"], sigma_c_g)

        self.results.derived.update({
            "P_t_teeth_per_in": pretty_float(p_t),
            "d_P_in": pretty_float(d_p),
            "d_G_in": pretty_float(d_g),
            "pitchline_velocity_ft_min": pretty_float(v),
            "transmitted_tangential_load_lbf": pretty_float(w_t),
            "A": pretty_float(c["A"]),
            "B": pretty_float(c["B"]),
            "K_v": pretty_float(k_v),
            "phi_t_deg": pretty_float(phi_t),
            "r_P_in": pretty_float(r_p),
            "r_G_in": pretty_float(r_g),
            "addendum_in": pretty_float(a),
            "rb_P_in": pretty_float(rb_p),
            "rb_G_in": pretty_float(rb_g),
            "Z_geometry_in": pretty_float(z_geom),
            "p_N_in": pretty_float(p_n),
            "m_N": pretty_float(m_n),
            "I": pretty_float(i_factor),
            "J_prime_P": pretty_float(j_prime_p),
            "J_prime_G": pretty_float(j_prime_g),
            "J_multiplier_P": pretty_float(j_mult_p),
            "J_multiplier_G": pretty_float(j_mult_g),
            "J_P": pretty_float(j_p),
            "J_G": pretty_float(j_g),
            "K_s_P": pretty_float(k_s_p),
            "K_s_G": pretty_float(k_s_g),
            "K_m": pretty_float(k_m),
            "C_p_sqrt_psi": pretty_float(c["C_p"]),
            "S_t_P_psi": pretty_float(s_t_p),
            "S_t_G_psi": pretty_float(s_t_g),
            "S_c_P_psi": pretty_float(s_c_p),
            "S_c_G_psi": pretty_float(s_c_g),
            "C_H_G": pretty_float(c_h),
            "Y_N_P": pretty_float(c["Y_N_P"]),
            "Y_N_G": pretty_float(c["Y_N_G"]),
            "Z_N_P": pretty_float(c["Z_N_P"]),
            "Z_N_G": pretty_float(c["Z_N_G"]),
        })
        self.results.outputs.update({
            "sigma_P_psi": pretty_float(sigma_p),
            "sigma_G_psi": pretty_float(sigma_g),
            "S_F_P": pretty_float(sf_p),
            "S_F_G": pretty_float(sf_g),
            "sigma_c_P_psi": pretty_float(sigma_c_p),
            "sigma_c_G_psi": pretty_float(sigma_c_g),
            "S_H_P": pretty_float(sh_p),
            "S_H_G": pretty_float(sh_g),
            "pinion_threat": self.decide_threat(sf_p, sh_p),
            "gear_threat": self.decide_threat(sf_g, sh_g),
            "mesh_threat": "wear" if min(sh_p ** 2, sh_g ** 2) < min(sf_p, sf_g) else "bending",
        })
        return {
            "problem": "helical_analysis",
            "title": p.get("title", "Helical gearset analysis"),
            "inputs": p,
            "lookups": self.results.lookups,
            "derived": self.results.derived,
            "outputs": self.results.outputs,
        }


class SpurGearDesignSolver(GearSolverBase):
    def solve(self) -> dict[str, Any]:
        p = self.problem
        iterations: list[dict[str, Any]] = []
        k_o = self.lookup.overload_factor(p["power_source"], p["driven_machine"])
        k_r = self.lookup.reliability_factor(p["reliability"])
        k_t = self.kt(p.get("temperature_F", 70.0))
        gear_ratio = p["gear_teeth"] / p["pinion_teeth"]
        yn_p = self.lookup.y_n(p["pinion_cycles"], p.get("yn_selection", "upper"))
        yn_g = self.lookup.y_n(p["pinion_cycles"] / gear_ratio, p.get("yn_selection", "upper"))
        zn_p = self.lookup.z_n(p["pinion_cycles"], p.get("zn_selection", "upper"))
        zn_g = self.lookup.z_n(p["pinion_cycles"] / gear_ratio, p.get("zn_selection", "upper"))
        c_p = self.lookup.cp_for_material_pair(p.get("pinion_cp_material", "Steel"), p.get("gear_cp_material", "Steel"))

        nitr_row = self.lookup.nitriding_material_row(p["material"])
        low_hrc, high_hrc = parse_range_text(nitr_row["hardness_core_HRC"])
        hb_mid = self.lookup.hardness_scale_hb_midrange_from_hrc_range(low_hrc, high_hrc)
        s_t = self.lookup.bending_strength_from_figure("figure_14_4.json", p["material_grade_key"], hb_mid)

        sc_rows = self.lookup.repo.csv_rows("table_14_6.csv")
        s_c = None
        for row in sc_rows:
            if row["material_designation"] == p["material_table_14_6_designation"] and row["minimum_surface_hardness"] == p["material_table_14_6_surface_hardness"]:
                s_c = float(row[f"grade_{p['material_grade_number']}_Sc_psi"])
                break
        if s_c is None:
            raise KeyError("Could not find material row in table_14_6.csv")

        c_h = 1.0
        table_14_9 = {row["condition"]: row for row in self.lookup.repo.csv_rows("table_14_9.csv")}
        cma_row = table_14_9[p["enclosure_condition_label"]]
        c_mc = self.c_mc(p.get("uncrowned", True))
        c_pm = self.c_pm(p.get("mounting_type", "straddle_adjacent"))
        c_e = self.c_e(p.get("adjusted_at_assembly", False))
        y_p = self.lookup.lewis_form_factor(p["pinion_teeth"])
        y_g = self.lookup.lewis_form_factor(p["gear_teeth"])
        j_p = p.get("J_P") or self.lookup.spur_j(p["pinion_teeth"], p["gear_teeth"])
        j_g = p.get("J_G") or self.lookup.spur_j(p["gear_teeth"], p["pinion_teeth"])

        for pd in p["diametral_pitch_candidates"]:
            d_p = p["pinion_teeth"] / pd
            d_g = p["gear_teeth"] / pd
            v = self.pitchline_velocity(d_p, p["pinion_speed_rpm"])
            w_t = self.transmitted_tangential_load(p["power_hp"], v)
            a_dyn, b_dyn = self.dynamic_factor_constants(p["quality_number"])
            k_v = self.dynamic_factor(a_dyn, b_dyn, v)
            face_width_trial = 4.0 * math.pi / pd
            k_s_p_trial = self.size_factor(face_width_trial, y_p, pd)
            k_s_g_trial = self.size_factor(face_width_trial, y_g, pd)
            c_pf_trial = self.c_pf(face_width_trial, d_p)
            c_ma_trial = self.c_ma(face_width_trial, float(cma_row["A"]), float(cma_row["B"]), float(cma_row["C"]))
            k_m_trial = self.km(c_mc, c_pf_trial, c_pm, c_ma_trial, c_e)
            i_factor = self.spur_I(p["pressure_angle_deg"], gear_ratio)

            f_bend = (
                p["design_factor"]
                * w_t
                * k_o
                * k_v
                * k_s_p_trial
                * pd
                * ((k_m_trial * p.get("kb", 1.0) * k_t * k_r) / (j_p * s_t * yn_p))
            )
            f_wear = (
                ((c_p * k_t * k_r) / (s_c * zn_p)) ** 2
                * p["design_factor"]
                * w_t
                * k_o
                * k_v
                * k_s_p_trial
                * (k_m_trial * p.get("c_f", 1.0) / (d_p * i_factor))
            )
            face_width_selected = GearMath.round_up_to_increment(max(f_bend, f_wear), 0.5)
            k_s_p = self.size_factor(face_width_selected, y_p, pd)
            k_s_g = self.size_factor(face_width_selected, y_g, pd)
            c_pf = self.c_pf(face_width_selected, d_p)
            c_ma = self.c_ma(face_width_selected, float(cma_row["A"]), float(cma_row["B"]), float(cma_row["C"]))
            k_m = self.km(c_mc, c_pf, c_pm, c_ma, c_e)

            sigma_p = self.bending_stress(w_t, k_o, k_v, k_s_p, pd, face_width_selected, k_m, p.get("kb", 1.0), j_p)
            sigma_g = self.bending_stress(w_t, k_o, k_v, k_s_g, pd, face_width_selected, k_m, p.get("kb", 1.0), j_g)
            sf_p = self.bending_factor_of_safety(s_t, yn_p, k_t, k_r, sigma_p)
            sf_g = self.bending_factor_of_safety(s_t, yn_g, k_t, k_r, sigma_g)

            sigma_c_p = self.contact_stress(c_p, w_t, k_o, k_v, k_s_p, k_m, d_p, face_width_selected, p.get("c_f", 1.0), i_factor)
            sigma_c_g = sigma_c_p
            sh_p = self.wear_factor_of_safety(s_c, zn_p, 1.0, k_t, k_r, sigma_c_p)
            sh_g = self.wear_factor_of_safety(s_c, zn_g, c_h, k_t, k_r, sigma_c_g)

            h_t = 2.25 / pd
            t_r_min = p["rim_thickness_factor_mb"] * h_t
            iterations.append({
                "P_d": pd,
                "d_P_in": pretty_float(d_p),
                "d_G_in": pretty_float(d_g),
                "V_ft_min": pretty_float(v),
                "W_t_lbf": pretty_float(w_t),
                "K_v": pretty_float(k_v),
                "F_trial_in": pretty_float(face_width_trial),
                "F_bend_in": pretty_float(f_bend),
                "F_wear_in": pretty_float(f_wear),
                "F_selected_in": pretty_float(face_width_selected),
                "K_s_P": pretty_float(k_s_p),
                "K_s_G": pretty_float(k_s_g),
                "K_m": pretty_float(k_m),
                "I": pretty_float(i_factor),
                "S_t_psi": pretty_float(s_t),
                "S_c_psi": pretty_float(s_c),
                "sigma_P_psi": pretty_float(sigma_p),
                "sigma_G_psi": pretty_float(sigma_g),
                "S_F_P": pretty_float(sf_p),
                "S_F_G": pretty_float(sf_g),
                "sigma_c_P_psi": pretty_float(sigma_c_p),
                "sigma_c_G_psi": pretty_float(sigma_c_g),
                "S_H_P": pretty_float(sh_p),
                "S_H_G": pretty_float(sh_g),
                "pinion_threat": self.decide_threat(sf_p, sh_p),
                "gear_threat": self.decide_threat(sf_g, sh_g),
                "rim_ht_in": pretty_float(h_t),
                "rim_tR_min_in": pretty_float(t_r_min),
            })

        preferred = p.get("preferred_diametral_pitch")
        selected_iteration = next((it for it in iterations if it["P_d"] == preferred), iterations[0])
        self.results.iterations = iterations
        self.results.derived.update({
            "Y_P": pretty_float(y_p),
            "Y_G": pretty_float(y_g),
            "J_P": pretty_float(j_p),
            "J_G": pretty_float(j_g),
            "Y_N_P": pretty_float(yn_p),
            "Y_N_G": pretty_float(yn_g),
            "Z_N_P": pretty_float(zn_p),
            "Z_N_G": pretty_float(zn_g),
            "K_R": pretty_float(k_r),
            "K_T": pretty_float(k_t),
            "C_p_sqrt_psi": pretty_float(c_p),
            "core_hardness_mid_HB": pretty_float(hb_mid),
            "S_t_psi": pretty_float(s_t),
            "S_c_psi": pretty_float(s_c),
        })
        self.results.outputs.update({
            "preferred_iteration": selected_iteration,
            "iteration_count": len(iterations),
        })
        return {
            "problem": "spur_design",
            "title": p.get("title", "Spur gearset design"),
            "inputs": p,
            "lookups": self.results.lookups,
            "derived": self.results.derived,
            "iterations": iterations,
            "outputs": self.results.outputs,
        }
