from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping

try:
    from .utils import (
        BevelWormGearError,
        ChartPoint,
        GridInterpolator2D,
        crowning_factor_cxc,
        dump_json,
        dynamic_factor_kv,
        elastic_coefficient_cp_steel_default,
        hardness_ratio_factor_ch,
        hp_from_tangential_force,
        life_factor_cl,
        life_factor_kl,
        load_csv_rows,
        load_distribution_factor_km,
        load_json,
        overload_factor_ko,
        reliability_factor_kr,
        round_up,
        rpm_to_pitchline_velocity_ft_min,
        size_factor_bending_kx,
        size_factor_ks,
        size_factor_pitting_cs,
        tangential_force_from_hp,
        temperature_factor_kt,
        to_float,
    )
except ImportError:  # pragma: no cover
    from utils import (
        BevelWormGearError,
        ChartPoint,
        GridInterpolator2D,
        crowning_factor_cxc,
        dump_json,
        dynamic_factor_kv,
        elastic_coefficient_cp_steel_default,
        hardness_ratio_factor_ch,
        hp_from_tangential_force,
        life_factor_cl,
        life_factor_kl,
        load_csv_rows,
        load_distribution_factor_km,
        load_json,
        overload_factor_ko,
        reliability_factor_kr,
        round_up,
        rpm_to_pitchline_velocity_ft_min,
        size_factor_bending_kx,
        size_factor_ks,
        size_factor_pitting_cs,
        tangential_force_from_hp,
        temperature_factor_kt,
        to_float,
    )

import math


class DataRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._cache: Dict[str, Any] = {}

    def csv(self, name: str) -> List[Dict[str, str]]:
        key = f"csv:{name}"
        if key not in self._cache:
            self._cache[key] = load_csv_rows(self.data_dir / name)
        return self._cache[key]

    def json(self, name: str) -> Dict[str, Any]:
        key = f"json:{name}"
        if key not in self._cache:
            self._cache[key] = load_json(self.data_dir / name)
        return self._cache[key]

    def interpolate_I(self, pinion_teeth: float, gear_teeth: float) -> float:
        rows = self.csv("figure_15_6.csv")
        pts = [ChartPoint(float(r["pinion_teeth"]), float(r["gear_teeth"]), float(r["geometry_factor_I"])) for r in rows]
        return GridInterpolator2D(pts).interpolate(pinion_teeth, gear_teeth)

    def interpolate_J(self, gear_teeth_for_which_J_is_desired: float, mate_teeth: float) -> float:
        rows = self.csv("figure_15_7.csv")

        target_gear = float(gear_teeth_for_which_J_is_desired)
        target_mate = float(mate_teeth)

        for r in rows:
            gear_val = float(r["gear_teeth_for_which_J_is_desired"])
            mate_val = float(r["mate_teeth"])
            if abs(gear_val - target_gear) < 1e-12 and abs(mate_val - target_mate) < 1e-12:
                return float(r["geometry_factor_J"])

        pts = [
            ChartPoint(
                float(r["gear_teeth_for_which_J_is_desired"]),
                float(r["mate_teeth"]),
                float(r["geometry_factor_J"]),
            )
            for r in rows
        ]
        return GridInterpolator2D(pts).interpolate(gear_teeth_for_which_J_is_desired, mate_teeth)

    def through_hardened_sac(self, hb: float, grade: int) -> Dict[str, float]:
        fig = self.json("figure_15_12.json")
        for corr in fig["correlations"]:
            if int(corr["grade"]) == int(grade):
                return {
                    "s_ac_psi": eval(corr["expressions"]["s_ac_psi"], {}, {"H_B": hb}),
                    "sigma_H_lim_MPa": eval(corr["expressions"]["sigma_H_lim_MPa"], {}, {"H_B": hb}),
                    "grade": grade,
                    "source": "figure_15_12.json",
                }
        raise BevelWormGearError(f"Could not find through-hardened s_ac for grade {grade}.")

    def through_hardened_sat(self, hb: float, grade: int) -> Dict[str, float]:
        fig = self.json("figure_15_13.json")
        for corr in fig["correlations"]:
            if int(corr["grade"]) == int(grade):
                return {
                    "s_at_psi": eval(corr["expressions"]["s_at_psi"], {}, {"H_B": hb}),
                    "sigma_F_lim_MPa": eval(corr["expressions"]["sigma_F_lim_MPa"], {}, {"H_B": hb}),
                    "grade": grade,
                    "source": "figure_15_13.json",
                }
        raise BevelWormGearError(f"Could not find through-hardened s_at for grade {grade}.")

    def steel_table_value(self, table_name: str, heat_treatment: str, grade: int) -> Dict[str, Any]:
        rows = self.csv(table_name)
        for row in rows:
            if heat_treatment.lower() in row["heat_treatment"].lower():
                lbf = row.get(f"allowable_contact_stress_grade_{grade}_lbf_per_in2") or row.get(f"bending_stress_grade_{grade}_lbf_per_in2")
                metric = row.get(f"allowable_contact_stress_grade_{grade}_N_per_mm2") or row.get(f"bending_stress_grade_{grade}_N_per_mm2")
                if lbf:
                    return {"lbf_per_in2": float(lbf), "N_per_mm2": float(metric) if metric else None, "row": row}
        raise BevelWormGearError(f"Could not find heat treatment '{heat_treatment}' grade {grade} in {table_name}.")

    def worm_table_15_8(self) -> Dict[str, Any]:
        return self.json("table_15_8.json")

    def worm_max_lead_angle_deg(self, phi_n_deg: float) -> float:
        rows = self.csv("table_15_9.csv")
        phi = float(phi_n_deg)
        best = min(rows, key=lambda r: abs(float(r.get("phi_n_deg", r.get("normal_pressure_angle_phi_n_deg"))) - phi))
        return float(best.get("lambda_max_deg", best.get("maximum_lead_angle_lambda_max_deg")))

    def worm_min_gear_teeth(self, phi_n_deg: float) -> int:
        rows = self.csv("table_15_10.csv")
        phi = float(phi_n_deg)
        best = min(rows, key=lambda r: abs(float(r.get("phi_n_deg", r.get("normal_pressure_angle_phi_n_deg"))) - phi))
        return int(float(best.get("gear_teeth_min", best.get("minimum_number_of_gear_teeth_NG_min"))))


@dataclass
class StraightBevelCommon:
    repo: DataRepository
    spec: Mapping[str, Any]

    def geometry(self, np_teeth: float, ng_teeth: float, pd: float, face_width_in: float) -> Dict[str, float]:
        d_p = np_teeth / pd
        d_g = ng_teeth / pd
        gamma = math.atan(np_teeth / ng_teeth)
        Gamma = math.atan(ng_teeth / np_teeth)
        d_av = d_p - face_width_in * math.cos(Gamma)
        return {
            "N_P": np_teeth,
            "N_G": ng_teeth,
            "P_d": pd,
            "F_in": face_width_in,
            "d_P_in": d_p,
            "d_G_in": d_g,
            "gamma_rad": gamma,
            "Gamma_rad": Gamma,
            "gamma_deg": math.degrees(gamma),
            "Gamma_deg": math.degrees(Gamma),
            "d_av_in": d_av,
            "gear_ratio": ng_teeth / np_teeth,
        }

    def common_factors(self, *, np_teeth: float, ng_teeth: float, pd: float, face_width_in: float, rpm: float, qv: float,
                       prime_mover: str, driven_machine: str, mounting: str, crowned: bool,
                       temperature_f: float, reliability: float, cycles: float,
                       pinion_hb: float, gear_hb: float, case_hardened_pinion: bool = False,
                       kl_branch: str = "general", pinion_surface_finish_um: float | None = None) -> Dict[str, Any]:
        geom = self.geometry(np_teeth, ng_teeth, pd, face_width_in)
        vt = rpm_to_pitchline_velocity_ft_min(geom["d_P_in"], rpm)
        ko = overload_factor_ko(self.repo.csv("table_15_2.csv"), prime_mover, driven_machine)
        kv_data = dynamic_factor_kv(qv, vt)
        ks = size_factor_ks(pd)
        km_data = load_distribution_factor_km(face_width_in, mounting)
        kx = size_factor_bending_kx()
        i_factor = self.repo.interpolate_I(np_teeth, ng_teeth)
        j_p = self.repo.interpolate_J(np_teeth, ng_teeth)
        j_g = self.repo.interpolate_J(ng_teeth, np_teeth)
        k_l = life_factor_kl(cycles, branch=kl_branch)
        c_l = life_factor_cl(cycles)
        ch_data = hardness_ratio_factor_ch(
            pinion_hb=pinion_hb,
            gear_hb=gear_hb,
            ratio_n_over_n=geom["gear_ratio"],
            case_hardened_pinion=case_hardened_pinion,
            pinion_surface_finish_um=pinion_surface_finish_um,
        )
        kt = temperature_factor_kt(temperature_f)
        rel = reliability_factor_kr(reliability)
        c_s = size_factor_pitting_cs(face_width_in)
        c_xc = crowning_factor_cxc(crowned)
        return {
            "geometry": geom,
            "v_t_ft_per_min": vt,
            "K_o": ko,
            **kv_data,
            "K_s": ks,
            **km_data,
            "K_x": kx,
            "I": i_factor,
            "J_P": j_p,
            "J_G": j_g,
            "K_L": k_l,
            "C_L": c_l,
            **ch_data,
            "K_T": kt,
            **rel,
            "C_s": c_s,
            "C_xc": c_xc,
        }


class StraightBevelGearAnalysisSolver(StraightBevelCommon):
    solve_path = "straight_bevel_analysis"

    def solve(self) -> Dict[str, Any]:
        p = self.spec
        gear = p["gearset"]
        material = p["material"]
        operating = p["operating"]
        parts = p["parts"]

        np_teeth = float(gear["pinion_teeth"])
        ng_teeth = float(gear["gear_teeth"])
        pd = float(gear["diametral_pitch_large_end"])
        face = float(gear["face_width_in"])
        rpm = float(operating["rpm"])
        qv = float(gear["Q_v"])

        common = self.common_factors(
            np_teeth=np_teeth,
            ng_teeth=ng_teeth,
            pd=pd,
            face_width_in=face,
            rpm=rpm,
            qv=qv,
            prime_mover=operating["prime_mover"],
            driven_machine=operating["driven_machine"],
            mounting=gear["mounting"],
            crowned=bool(gear["crowned"]),
            temperature_f=float(operating["temperature_F"]),
            reliability=float(parts["a"]["reliability"]),
            cycles=float(parts["a"]["cycles"]),
            pinion_hb=float(material["pinion_hb"]),
            gear_hb=float(material["gear_hb"]),
            case_hardened_pinion=bool(material.get("case_hardened_pinion", False)),
            kl_branch=parts["a"].get("K_L_branch", "general"),
            pinion_surface_finish_um=material.get("pinion_surface_finish_um"),
        )

        part_a = self._solve_bending(common, sf=float(parts["a"]["S_F"]), material=material, member="pinion")
        part_b = self._solve_wear(common, sh=float(parts["a"]["S_H"]), material=material)

        common_c = self.common_factors(
            np_teeth=np_teeth,
            ng_teeth=ng_teeth,
            pd=pd,
            face_width_in=face,
            rpm=rpm,
            qv=qv,
            prime_mover=operating["prime_mover"],
            driven_machine=operating["driven_machine"],
            mounting=gear["mounting"],
            crowned=bool(gear["crowned"]),
            temperature_f=float(operating["temperature_F"]),
            reliability=float(parts["c"]["reliability"]),
            cycles=float(parts["c"]["cycles"]),
            pinion_hb=float(material["pinion_hb"]),
            gear_hb=float(material["gear_hb"]),
            case_hardened_pinion=bool(material.get("case_hardened_pinion", False)),
            kl_branch=parts["c"].get("K_L_branch", "general"),
            pinion_surface_finish_um=material.get("pinion_surface_finish_um"),
        )
        part_c_bending = self._solve_bending(common_c, sf=float(parts["c"]["S_F"]), material=material, member="pinion")
        part_c_wear = self._solve_wear(common_c, sh=float(parts["c"]["S_H"]), material=material)
        part_c = {
            "bending_based_power_hp": part_c_bending["power_hp"],
            "wear_based_power_hp": part_c_wear["power_hp"],
            "mesh_rated_power_hp": min(part_c_bending["power_hp"], part_c_wear["power_hp"]),
            "bending_details": part_c_bending,
            "wear_details": part_c_wear,
        }
        return {
            "problem": self.solve_path,
            "title": p.get("title", "Straight bevel gear analysis"),
            "inputs": p,
            "derived_common_part_a": common,
            "outputs": {
                "part_a_bending_power_hp": part_a["power_hp"],
                "part_b_wear_power_hp": part_b["power_hp"],
                "part_c": part_c,
            },
            "details": {
                "part_a_bending": part_a,
                "part_b_wear": part_b,
            },
        }

    def _solve_bending(self, common: Dict[str, Any], *, sf: float, material: Mapping[str, Any], member: str) -> Dict[str, Any]:
        hb = float(material[f"{member}_hb"])
        grade = int(material["agma_grade"])
        sat_data = self.repo.through_hardened_sat(hb, grade) if material["heat_treatment"].lower() == "through-hardened" else self.repo.steel_table_value("table_15_6.csv", material["heat_treatment"], grade)
        s_at = sat_data["s_at_psi"] if "s_at_psi" in sat_data else sat_data["lbf_per_in2"]
        j = common["J_P"] if member == "pinion" else common["J_G"]
        coeff = (common["geometry"]["P_d"] / common["geometry"]["F_in"]) * common["K_o"] * common["K_v"] * common["K_s"] * common["K_m"] / (common["K_x"] * j)
        s_allow = s_at * common["K_L"] / (sf * common["K_T"] * common["K_R"])
        wt = s_allow / coeff
        hp = hp_from_tangential_force(wt, common["v_t_ft_per_min"])
        return {
            "member": member,
            "s_at_psi": s_at,
            "sigma_allowable_psi": s_allow,
            "stress_coefficient_sigma_over_Wt": coeff,
            "solved_W_t_lbf": wt,
            "power_hp": hp,
        }

    def _solve_wear(self, common: Dict[str, Any], *, sh: float, material: Mapping[str, Any]) -> Dict[str, Any]:
        hb = float(material["gear_hb"])
        grade = int(material["agma_grade"])
        sac_data = self.repo.through_hardened_sac(hb, grade) if material["heat_treatment"].lower() == "through-hardened" else self.repo.steel_table_value("table_15_4.csv", material["heat_treatment"], grade)
        s_ac = sac_data["s_ac_psi"] if "s_ac_psi" in sac_data else sac_data["lbf_per_in2"]
        sigma_allow = s_ac * common["C_L"] * common["C_H"] / (sh * common["K_T"] * common["C_R"])
        cp = float(material.get("C_P", elastic_coefficient_cp_steel_default()))
        geom = common["geometry"]
        coeff = cp * (((common["K_o"] * common["K_v"] * common["K_m"] * common["C_s"] * common["C_xc"]) / (geom["F_in"] * geom["d_P_in"] * common["I"])) ** 0.5)
        wt = (sigma_allow / coeff) ** 2
        hp = hp_from_tangential_force(wt, common["v_t_ft_per_min"])
        return {
            "s_ac_psi": s_ac,
            "sigma_contact_allowable_psi": sigma_allow,
            "contact_stress_coefficient_sigma_over_sqrtWt": coeff,
            "solved_W_t_lbf": wt,
            "power_hp": hp,
        }


class StraightBevelMeshDesignSolver(StraightBevelCommon):
    solve_path = "straight_bevel_mesh_design"

    def _member_cycles(self, design: Mapping[str, Any]) -> Dict[str, float]:
        pinion_cycles = float(design["pinion_cycles"])
        gear_cycles = float(design.get("gear_cycles", pinion_cycles / float(design["gear_ratio"])))
        return {"pinion_cycles": pinion_cycles, "gear_cycles": gear_cycles}

    def _member_branches(self, design: Mapping[str, Any]) -> Dict[str, str]:
        common_branch = design.get("K_L_branch", "general")
        return {
            "pinion_K_L_branch": design.get("pinion_K_L_branch", common_branch),
            "gear_K_L_branch": design.get("gear_K_L_branch", common_branch),
        }

    def _member_life_factors(self, design: Mapping[str, Any]) -> Dict[str, float | str]:
        cyc = self._member_cycles(design)
        branches = self._member_branches(design)
        return {
            **cyc,
            **branches,
            "K_L_pinion": life_factor_kl(cyc["pinion_cycles"], branch=branches["pinion_K_L_branch"]),
            "K_L_gear": life_factor_kl(cyc["gear_cycles"], branch=branches["gear_K_L_branch"]),
            "C_L_pinion": life_factor_cl(cyc["pinion_cycles"]),
            "C_L_gear": life_factor_cl(cyc["gear_cycles"]),
        }

    def solve(self) -> Dict[str, Any]:
        p = self.spec
        d = p["design"]
        material = p["material"]
        np_teeth = float(d["pinion_teeth"])
        ng_teeth = float(d["gear_ratio"] * np_teeth)
        rpm = float(d["rpm"])
        qv = float(d["Q_v"])
        design_factor = float(d["design_factor"])
        sf_target = design_factor
        sh_target = design_factor ** 0.5
        life_factors = self._member_life_factors(d)

        common_pre = self.common_factors(
            np_teeth=np_teeth,
            ng_teeth=ng_teeth,
            pd=float(d["initial_diametral_pitch"]),
            face_width_in=1.0,
            rpm=rpm,
            qv=qv,
            prime_mover=d["prime_mover"],
            driven_machine=d["driven_machine"],
            mounting=d["mounting"],
            crowned=bool(d["crowned"]),
            temperature_f=float(d["temperature_F"]),
            reliability=float(d["reliability"]),
            cycles=life_factors["pinion_cycles"],
            pinion_hb=float(material["pinion_hb"]),
            gear_hb=float(material["gear_hb"]),
            case_hardened_pinion=bool(material.get("case_hardened_pinion", False)),
            kl_branch=life_factors["pinion_K_L_branch"],
            pinion_surface_finish_um=material.get("pinion_surface_finish_um"),
        )
        common_pre["member_life_factors"] = dict(life_factors)

        candidates = d.get("candidate_diametral_pitches", [d["initial_diametral_pitch"]])
        iterations: List[Dict[str, Any]] = []
        accepted = None
        for pd in candidates:
            result = self._evaluate_candidate(
                pd=float(pd),
                np_teeth=np_teeth,
                ng_teeth=ng_teeth,
                rpm=rpm,
                horsepower=float(d["horsepower"]),
                qv=qv,
                sf_target=sf_target,
                sh_target=sh_target,
                spec=d,
                material=material,
                life_factors=life_factors,
            )
            iterations.append(result)
            if result["meets_design"] and accepted is None:
                accepted = result
                if not d.get("continue_after_first_accept", False):
                    break

        if accepted is None:
            accepted = iterations[-1]

        comparable = {
            "gear_bending": accepted["actual_safety_factors"]["gear_bending"],
            "pinion_bending": accepted["actual_safety_factors"]["pinion_bending"],
            "gear_wear_comparable": accepted["actual_safety_factors"]["gear_wear_squared"] ** 0.5,
            "pinion_wear_comparable": accepted["actual_safety_factors"]["pinion_wear_squared"] ** 0.5,
        }
        primary_threat = min(comparable, key=comparable.get)
        return {
            "problem": self.solve_path,
            "title": p.get("title", "Design of a straight bevel gear mesh"),
            "inputs": p,
            "precomputed_common": common_pre,
            "iterations": iterations,
            "selected_design": accepted,
            "primary_threat": {
                "name": primary_threat,
                "comparable_safety_factor": comparable[primary_threat],
            },
        }

    def _evaluate_candidate(
        self,
        *,
        pd: float,
        np_teeth: float,
        ng_teeth: float,
        rpm: float,
        horsepower: float,
        qv: float,
        sf_target: float,
        sh_target: float,
        spec: Mapping[str, Any],
        material: Mapping[str, Any],
        life_factors: Mapping[str, Any],
    ) -> Dict[str, Any]:
        geom0 = self.geometry(np_teeth, ng_teeth, pd, 1.0)
        v_t = rpm_to_pitchline_velocity_ft_min(geom0["d_P_in"], rpm)
        wt = tangential_force_from_hp(horsepower, v_t)
        a0 = ((geom0["d_P_in"] / 2.0) ** 2 + (geom0["d_G_in"] / 2.0) ** 2) ** 0.5
        face_calc = 0.30 * a0
        face_selected = round_up(face_calc, spec.get("face_width_rounding_increment_in", 0.25))
        face_selected = min(face_selected, a0)
        common = self.common_factors(
            np_teeth=np_teeth,
            ng_teeth=ng_teeth,
            pd=pd,
            face_width_in=face_selected,
            rpm=rpm,
            qv=qv,
            prime_mover=spec["prime_mover"],
            driven_machine=spec["driven_machine"],
            mounting=spec["mounting"],
            crowned=bool(spec["crowned"]),
            temperature_f=float(spec["temperature_F"]),
            reliability=float(spec["reliability"]),
            cycles=life_factors["pinion_cycles"],
            pinion_hb=float(material["pinion_hb"]),
            gear_hb=float(material["gear_hb"]),
            case_hardened_pinion=bool(material.get("case_hardened_pinion", False)),
            kl_branch=life_factors["pinion_K_L_branch"],
            pinion_surface_finish_um=material.get("pinion_surface_finish_um"),
        )
        common["member_life_factors"] = dict(life_factors)

        geom = common["geometry"]
        sat = self.repo.steel_table_value("table_15_6.csv", material["heat_treatment"], int(material["agma_grade"]))["lbf_per_in2"]
        sac = self.repo.steel_table_value("table_15_4.csv", material["heat_treatment"], int(material["agma_grade"]))["lbf_per_in2"]
        cp = float(material.get("C_P", elastic_coefficient_cp_steel_default()))

        sigma_gear = (wt / geom["F_in"]) * geom["P_d"] * common["K_o"] * common["K_v"] * common["K_s"] * common["K_m"] / (common["K_x"] * common["J_G"])
        sigma_pinion = (wt / geom["F_in"]) * geom["P_d"] * common["K_o"] * common["K_v"] * common["K_s"] * common["K_m"] / (common["K_x"] * common["J_P"])

        sigma_allowable_gear_bending = sat * float(life_factors["K_L_gear"]) / (sf_target * common["K_T"] * common["K_R"])
        sigma_allowable_pinion_bending = sat * float(life_factors["K_L_pinion"]) / (sf_target * common["K_T"] * common["K_R"])

        ratio_gear_bending = sigma_allowable_gear_bending / sigma_gear
        ratio_pinion_bending = sigma_allowable_pinion_bending / sigma_pinion
        actual_sf_gear = sf_target * ratio_gear_bending
        actual_sf_pinion = sf_target * ratio_pinion_bending

        sigma_c = cp * ((wt / (geom["F_in"] * geom["d_P_in"] * common["I"])) * common["K_o"] * common["K_v"] * common["K_m"] * common["C_s"] * common["C_xc"]) ** 0.5

        sigma_allowable_gear_contact = sac * float(life_factors["C_L_gear"]) * common["C_H"] / (sh_target * common["K_T"] * common["C_R"])
        sigma_allowable_pinion_contact = sac * float(life_factors["C_L_pinion"]) * common["C_H"] / (sh_target * common["K_T"] * common["C_R"])

        ratio_gear_contact = sigma_allowable_gear_contact / sigma_c
        ratio_pinion_contact = sigma_allowable_pinion_contact / sigma_c
        actual_sh_squared_gear = (ratio_gear_contact * sh_target) ** 2
        actual_sh_squared_pinion = (ratio_pinion_contact * sh_target) ** 2

        meets = all([
            actual_sf_gear >= sf_target,
            actual_sf_pinion >= sf_target,
            actual_sh_squared_gear >= design_factor_from_sh(sh_target),
            actual_sh_squared_pinion >= design_factor_from_sh(sh_target),
            common["valid"],
        ])
        return {
            "candidate_P_d": pd,
            "A_0_in": a0,
            "F_calculated_in": face_calc,
            "F_selected_in": face_selected,
            "power_hp": horsepower,
            "W_t_lbf": wt,
            "common": common,
            "bending": {
                "s_at_psi": sat,
                "sigma_gear_psi": sigma_gear,
                "sigma_pinion_psi": sigma_pinion,
                "sigma_allowable_gear_psi": sigma_allowable_gear_bending,
                "sigma_allowable_pinion_psi": sigma_allowable_pinion_bending,
            },
            "wear": {
                "s_ac_psi": sac,
                "sigma_contact_psi": sigma_c,
                "sigma_contact_allowable_gear_psi": sigma_allowable_gear_contact,
                "sigma_contact_allowable_pinion_psi": sigma_allowable_pinion_contact,
            },
            "actual_safety_factors": {
                "gear_bending": actual_sf_gear,
                "pinion_bending": actual_sf_pinion,
                "gear_wear_squared": actual_sh_squared_gear,
                "pinion_wear_squared": actual_sh_squared_pinion,
            },
            "meets_design": meets,
        }


def design_factor_from_sh(sh: float) -> float:
    return sh**2


# -------------------- Worm gearing helpers --------------------

LEWIS_Y_BY_PHI = {
    14.5: 0.100,
    20.0: 0.125,
    25.0: 0.150,
    30.0: 0.175,
}

WORM_TOOTH_SYSTEM_COEFFS = {
    (14.5, "le2"): {"a": 0.3183, "b": 0.3683, "ht": 0.6866},
    (20.0, "le2"): {"a": 0.3183, "b": 0.3683, "ht": 0.6866},
    (25.0, "gt2"): {"a": 0.2860, "b": 0.3490, "ht": 0.6350},
}


def worm_tooth_system_coeffs(phi_n_deg: float, worm_threads: int) -> Dict[str, float]:
    phi = float(phi_n_deg)
    key = "le2" if int(worm_threads) <= 2 else "gt2"
    if (phi, key) in WORM_TOOTH_SYSTEM_COEFFS:
        return dict(WORM_TOOTH_SYSTEM_COEFFS[(phi, key)])
    if key == "le2" and phi in (14.5, 20.0):
        return dict(WORM_TOOTH_SYSTEM_COEFFS[(phi, key)])
    raise BevelWormGearError(f"Unsupported worm tooth system for phi_n={phi_n_deg} and N_W={worm_threads}.")


def worm_material_factor_cs(material_class: str, center_distance_in: float, mean_gear_diameter_in: float) -> Dict[str, Any]:
    material = material_class.strip().lower().replace("-", " ").replace("_", " ")
    C = float(center_distance_in)
    Dm = float(mean_gear_diameter_in)

    if material in {"sand cast bronze", "sand cast", "sand cast bronze gear", "sand cast gear"}:
        if C <= 3.0:
            cs = 720.0 + 10.37 * C**3
            eq = "15-32"
        elif Dm <= 2.5:
            cs = 1000.0
            eq = "15-33a"
        else:
            cs = 1190.0 - 477.0 * math.log10(Dm)
            eq = "15-33b"
        return {"material_factor_Cs": cs, "material_family": "sand_cast_bronze", "equation": eq}

    if material in {"chill cast bronze", "chill cast", "chill cast bronze gear", "chilled cast bronze"}:
        if Dm <= 8.0:
            cs = 1000.0
            eq = "15-34a"
        else:
            cs = 1412.0 - 456.0 * math.log10(Dm)
            eq = "15-34b"
        return {"material_factor_Cs": cs, "material_family": "chill_cast_bronze", "equation": eq}

    if material in {"centrifugally cast bronze", "centrifugally cast", "centrifugal cast bronze", "centrifugal cast"}:
        if Dm <= 25.0:
            cs = 1000.0
            eq = "15-35a"
        else:
            cs = 1251.0 - 180.0 * math.log10(Dm)
            eq = "15-35b"
        return {"material_factor_Cs": cs, "material_family": "centrifugally_cast_bronze", "equation": eq}

    raise BevelWormGearError(f"Unsupported worm-gear material class '{material_class}'.")


def worm_ratio_correction_cm(mg: float) -> float:
    mg = float(mg)
    if 3.0 < mg <= 20.0:
        return 0.02 * math.sqrt(-mg**2 + 40.0 * mg - 76.0) + 0.46
    if 20.0 < mg <= 76.0:
        return 0.0107 * math.sqrt(-mg**2 + 56.0 * mg + 5145.0)
    if mg > 76.0:
        return 1.1483 - 0.00658 * mg
    raise BevelWormGearError("Eq. (15-36) requires m_G > 3.")


def worm_velocity_factor_cv(vs_ft_min: float) -> float:
    vs = float(vs_ft_min)
    if vs < 700.0:
        return 0.659 * math.exp(-0.0011 * vs)
    if vs < 3000.0:
        return 13.31 * vs ** (-0.571)
    return 65.52 * vs ** (-0.774)


def worm_friction_coeff(vs_ft_min: float) -> float:
    vs = float(vs_ft_min)
    if vs <= 10.0:
        return 0.124 * math.exp(-0.074 * vs**0.645)
    return 0.103 * math.exp(-0.110 * vs**0.450) + 0.012


def worm_lewis_y(phi_n_deg: float) -> float:
    phi = float(phi_n_deg)
    for key, val in LEWIS_Y_BY_PHI.items():
        if abs(key - phi) < 1e-9:
            return val
    raise BevelWormGearError(f"Unsupported phi_n={phi_n_deg} for worm Lewis factor y.")


def worm_efficiency_worm_drives(phi_n_deg: float, friction_coeff: float, lead_angle_rad: float) -> float:
    cphi = math.cos(math.radians(float(phi_n_deg)))
    f = float(friction_coeff)
    lam = float(lead_angle_rad)
    return (cphi - f * math.tan(lam)) / (cphi + f / math.tan(lam))


def worm_efficiency_gear_drives(phi_n_deg: float, friction_coeff: float, lead_angle_rad: float) -> float:
    cphi = math.cos(math.radians(float(phi_n_deg)))
    f = float(friction_coeff)
    lam = float(lead_angle_rad)
    return (cphi - f / math.tan(lam)) / (cphi + f * math.tan(lam))


def worm_force_worm_tangential(wg_t: float, phi_n_deg: float, lead_angle_rad: float, friction_coeff: float) -> float:
    cphi = math.cos(math.radians(float(phi_n_deg)))
    lam = float(lead_angle_rad)
    f = float(friction_coeff)
    return wg_t * (cphi * math.sin(lam) + f * math.cos(lam)) / (cphi * math.cos(lam) - f * math.sin(lam))


def worm_force_friction(wg_t: float, phi_n_deg: float, lead_angle_rad: float, friction_coeff: float) -> float:
    cphi = math.cos(math.radians(float(phi_n_deg)))
    lam = float(lead_angle_rad)
    f = float(friction_coeff)
    return abs((f * wg_t) / (f * math.sin(lam) - cphi * math.cos(lam)))


def worm_heat_transfer_coeff(nw_rpm: float, fan_on_worm_shaft: bool) -> float:
    if fan_on_worm_shaft:
        return nw_rpm / 3939.0 + 0.13
    return nw_rpm / 6494.0 + 0.13


class WormGearCommon:
    repo: DataRepository

    def _gearset_geometry(self, *, worm_threads: int, gear_teeth: int, worm_pitch_diameter_in: float,
                          tangential_diametral_pitch: float, phi_n_deg: float) -> Dict[str, Any]:
        N_W = int(worm_threads)
        N_G = int(gear_teeth)
        d = float(worm_pitch_diameter_in)
        P_t = float(tangential_diametral_pitch)
        m_G = N_G / N_W
        D = N_G / P_t
        p_x = math.pi / P_t
        C = (d + D) / 2.0
        coeffs = worm_tooth_system_coeffs(phi_n_deg, N_W)
        a = coeffs["a"] * p_x
        b = coeffs["b"] * p_x
        h_t = coeffs["ht"] * p_x if p_x >= 0.16 else 0.7003 * p_x + 0.002
        d_o = d + 2.0 * a
        d_r = d - 2.0 * b
        D_t = D + 2.0 * a
        D_r = D - 2.0 * b
        c = b - a
        F_W_max = 2.0 * math.sqrt(2.0 * D * a)
        return {
            "m_G": m_G,
            "N_W": N_W,
            "N_G": N_G,
            "d_in": d,
            "D_in": D,
            "P_t": P_t,
            "phi_n_deg": float(phi_n_deg),
            "p_x_in": p_x,
            "center_distance_in": C,
            "a_in": a,
            "b_in": b,
            "h_t_in": h_t,
            "worm_outside_diameter_do_in": d_o,
            "worm_root_diameter_dr_in": d_r,
            "gear_throat_diameter_Dt_in": D_t,
            "gear_root_diameter_Dr_in": D_r,
            "clearance_c_in": c,
            "worm_face_width_max_in": F_W_max,
        }

    def _kinematics(self, *, d_in: float, D_in: float, nw_rpm: float, gear_ratio: float, P_t: float,
                    worm_threads: int) -> Dict[str, Any]:
        V_W = math.pi * d_in * nw_rpm / 12.0
        n_g = nw_rpm / gear_ratio
        V_G = math.pi * D_in * n_g / 12.0
        L = (math.pi / P_t) * worm_threads
        lambda_rad = math.atan(L / (math.pi * d_in))
        P_n = P_t / math.cos(lambda_rad)
        V_s = math.pi * d_in * nw_rpm / (12.0 * math.cos(lambda_rad))
        return {
            "V_W_ft_per_min": V_W,
            "V_G_ft_per_min": V_G,
            "n_G_rpm": n_g,
            "lead_L_in": L,
            "lambda_rad": lambda_rad,
            "lambda_deg": math.degrees(lambda_rad),
            "P_n": P_n,
            "p_n_in": math.pi / P_n,
            "V_s_ft_per_min": V_s,
        }

    def _force_capacity_factors(self, *, gear_ratio: float, center_distance_in: float,
                                mean_gear_diameter_in: float, sliding_velocity_ft_min: float,
                                gear_material_class: str) -> Dict[str, Any]:
        cs_data = worm_material_factor_cs(gear_material_class, center_distance_in, mean_gear_diameter_in)
        return {
            **cs_data,
            "C_m": worm_ratio_correction_cm(gear_ratio),
            "C_v": worm_velocity_factor_cv(sliding_velocity_ft_min),
        }

    def _gear_face_width_effective(self, actual_face_width_in: float, worm_pitch_diameter_in: float) -> float:
        return min(float(actual_face_width_in), 2.0 * float(worm_pitch_diameter_in) / 3.0)


class WormGearAnalysisSolver(WormGearCommon):
    solve_path = "worm_analysis"

    def __init__(self, repo: DataRepository, spec: Mapping[str, Any]):
        self.repo = repo
        self.spec = spec

    def solve(self) -> Dict[str, Any]:
        p = self.spec
        geom_in = p["gearset"]
        operating = p["operating"]
        thermal = p["thermal"]

        geom = self._gearset_geometry(
            worm_threads=int(geom_in["worm_threads"]),
            gear_teeth=int(geom_in["gear_teeth"]),
            worm_pitch_diameter_in=float(geom_in["worm_pitch_diameter_in"]),
            tangential_diametral_pitch=float(geom_in["tangential_diametral_pitch"]),
            phi_n_deg=float(geom_in["normal_pressure_angle_deg"]),
        )
        kin = self._kinematics(
            d_in=geom["d_in"],
            D_in=geom["D_in"],
            nw_rpm=float(operating["worm_rpm"]),
            gear_ratio=geom["m_G"],
            P_t=geom["P_t"],
            worm_threads=geom["N_W"],
        )
        capacity_factors = self._force_capacity_factors(
            gear_ratio=geom["m_G"],
            center_distance_in=geom["center_distance_in"],
            mean_gear_diameter_in=geom["D_in"],
            sliding_velocity_ft_min=kin["V_s_ft_per_min"],
            gear_material_class=geom_in["gear_material_class"],
        )

        friction_coeff = worm_friction_coeff(kin["V_s_ft_per_min"])
        eff = worm_efficiency_worm_drives(geom["phi_n_deg"], friction_coeff, kin["lambda_rad"])

        W_G_t = 33000.0 * float(operating["design_factor"]) * float(operating["output_power_hp"]) * float(operating["application_factor"]) / (kin["V_G_ft_per_min"] * eff)
        W_W_t = worm_force_worm_tangential(W_G_t, geom["phi_n_deg"], kin["lambda_rad"], friction_coeff)

        F_e_G = self._gear_face_width_effective(float(geom_in["gear_face_width_in"]), geom["d_in"])
        W_t_all = capacity_factors["material_factor_Cs"] * geom["D_in"]**0.8 * F_e_G * capacity_factors["C_m"] * capacity_factors["C_v"]
        force_ok = W_G_t < W_t_all
        excess_capacity_margin_lbf = W_t_all - W_G_t
        excess_capacity_ratio = W_t_all / W_G_t if W_G_t != 0.0 else math.inf

        W_f = worm_force_friction(W_G_t, geom["phi_n_deg"], kin["lambda_rad"], friction_coeff)
        H_f = W_f * kin["V_s_ft_per_min"] / 33000.0
        H_W = W_W_t * kin["V_W_ft_per_min"] / 33000.0
        H_G = W_G_t * kin["V_G_ft_per_min"] / 33000.0
        gear_power_ok = H_G >= float(operating["output_power_hp"])

        y = worm_lewis_y(geom["phi_n_deg"])
        sigma_G = W_G_t / (kin["p_n_in"] * F_e_G * y)
        sigma_allow = float(geom_in.get("gear_allowable_stress_psi", 10000.0))
        stress_ok = sigma_G <= sigma_allow

        A_min = 43.2 * geom["center_distance_in"]**1.7
        H_loss = 33000.0 * (1.0 - eff) * H_W
        h_bar_CR = worm_heat_transfer_coeff(float(operating["worm_rpm"]), bool(thermal["fan_on_worm_shaft"]))
        t_s = float(thermal["ambient_temp_F"]) + H_loss / (h_bar_CR * float(thermal["case_lateral_area_in2"]))
        acceptable_sump_temperature_F = float(thermal.get("acceptable_sump_temperature_F", 200.0))
        sump_temperature_ok = t_s <= acceptable_sump_temperature_F

        return {
            "problem": self.solve_path,
            "title": p.get("title", "Worm gear analysis"),
            "inputs": p,
            "geometry": geom,
            "kinematics": kin,
            "capacity_factors": capacity_factors,
            "results": {
                "friction_coefficient_f": friction_coeff,
                "mesh_efficiency_e_worm_drives": eff,
                "worm_tangential_force_W_W_t_lbf": W_W_t,
                "gear_tangential_force_W_G_t_lbf": W_G_t,
                "effective_gear_face_width_F_e_G_in": F_e_G,
                "allowable_tangential_force_W_t_all_lbf": W_t_all,
                "force_capacity_ok": force_ok,
                "excess_capacity_margin_lbf": excess_capacity_margin_lbf,
                "excess_capacity_ratio": excess_capacity_ratio,
                "capacity_check_note": "Passes excess-capacity check when W_G_t < W_t_all.",
                "friction_force_W_f_lbf": W_f,
                "friction_power_H_f_hp": H_f,
                "worm_power_H_W_hp": H_W,
                "gear_power_H_G_hp": H_G,
                "gear_power_satisfactory": gear_power_ok,
                "gear_bending_stress_sigma_G_psi": sigma_G,
                "assumed_allowable_gear_bending_stress_psi": sigma_allow,
                "gear_stress_satisfactory": stress_ok,
                "minimum_case_lateral_area_A_min_in2": A_min,
                "heat_loss_rate_H_loss_ft_lbf_per_min": H_loss,
                "h_bar_CR_ft_lbf_per_min_in2_F": h_bar_CR,
                "sump_temperature_t_s_F": t_s,
                "acceptable_sump_temperature_F": acceptable_sump_temperature_F,
                "sump_temperature_satisfactory": sump_temperature_ok,
                "sump_temperature_check_note": "Common practice target from Ugural-style guidance: lubricant temperature should typically not exceed about 200 F.",
            },
        }


class WormGearMeshDesignSolver(WormGearCommon):
    solve_path = "worm_mesh_design"

    def __init__(self, repo: DataRepository, spec: Mapping[str, Any]):
        self.repo = repo
        self.spec = spec

    def solve(self) -> Dict[str, Any]:
        p = self.spec
        dsg = p["design"]

        N_W = int(dsg["worm_threads"])
        m_G = float(dsg["gear_ratio"])
        N_G = int(round(m_G * N_W))
        phi_n_deg = float(dsg["normal_pressure_angle_deg"])
        min_teeth = self.repo.worm_min_gear_teeth(phi_n_deg)
        acceptable_gear_teeth = N_G >= min_teeth

        p_x = float(dsg["trial_axial_pitch_in"])
        P_t = math.pi / p_x
        D = N_G / P_t
        coeffs = worm_tooth_system_coeffs(phi_n_deg, N_W)
        a = coeffs["a"] * p_x
        b = coeffs["b"] * p_x
        h_t = coeffs["ht"] * p_x if p_x >= 0.16 else 0.7003 * p_x + 0.002

        d0 = float(dsg["initial_worm_pitch_diameter_in"])
        d_step = float(dsg.get("worm_pitch_diameter_step_in", 0.5))
        max_trials = int(dsg.get("max_d_trials", 10))

        d_trials: List[Dict[str, Any]] = []
        chosen_d = None
        current = d0
        for _ in range(max_trials):
            C = (current + D) / 2.0
            dlo = C**0.875 / 3.0
            dhi = C**0.875 / 1.6
            valid = dlo <= current <= dhi
            d_trials.append({
                "candidate_d_in": current,
                "center_distance_C_in": C,
                "d_lo_in": dlo,
                "d_hi_in": dhi,
                "valid_under_eq_15_27": valid,
            })
            if valid:
                chosen_d = current
            current += d_step

        if chosen_d is None:
            raise BevelWormGearError("No valid worm pitch diameter found under Eq. (15-27).")

        C = (chosen_d + D) / 2.0
        kin = self._kinematics(d_in=chosen_d, D_in=D, nw_rpm=float(dsg["worm_rpm"]), gear_ratio=m_G, P_t=P_t, worm_threads=N_W)
        lambda_max_deg = self.repo.worm_max_lead_angle_deg(phi_n_deg)
        lead_angle_ok = kin["lambda_deg"] <= lambda_max_deg

        capacity_factors = self._force_capacity_factors(
            gear_ratio=m_G, center_distance_in=C, mean_gear_diameter_in=D,
            sliding_velocity_ft_min=kin["V_s_ft_per_min"], gear_material_class=dsg["gear_material_class"],
        )

        friction_coeff = worm_friction_coeff(kin["V_s_ft_per_min"])
        e_w = worm_efficiency_worm_drives(phi_n_deg, friction_coeff, kin["lambda_rad"])
        e_g = worm_efficiency_gear_drives(phi_n_deg, friction_coeff, kin["lambda_rad"])
        W_G_t = 33000.0 * float(dsg["design_factor"]) * float(dsg["output_power_hp"]) * float(dsg["application_factor"]) / (kin["V_G_ft_per_min"] * e_w)
        W_W_t = worm_force_worm_tangential(W_G_t, phi_n_deg, kin["lambda_rad"], friction_coeff)
        H_W = W_W_t * kin["V_W_ft_per_min"] / 33000.0
        H_G = W_G_t * kin["V_G_ft_per_min"] / 33000.0
        W_f = worm_force_friction(W_G_t, phi_n_deg, kin["lambda_rad"], friction_coeff)
        H_f = W_f * kin["V_s_ft_per_min"] / 33000.0

        F_e_req = W_G_t / (capacity_factors["material_factor_Cs"] * D**0.8 * capacity_factors["C_m"] * capacity_factors["C_v"])
        F_e_max = 2.0 * chosen_d / 3.0
        F_e_selected = min(round_up(F_e_req, float(dsg.get("face_width_rounding_increment_in", 0.25))), F_e_max)
        if "effective_gear_face_width_selected_in" in dsg:
            F_e_selected = float(dsg["effective_gear_face_width_selected_in"])
        if F_e_selected < F_e_req or F_e_selected > F_e_max + 1e-12:
            raise BevelWormGearError("Selected effective gear face width is outside the allowable range.")
        W_t_all = capacity_factors["material_factor_Cs"] * D**0.8 * F_e_selected * capacity_factors["C_m"] * capacity_factors["C_v"]
        excess_capacity_ok = W_t_all > W_G_t
        excess_capacity_margin_lbf = W_t_all - W_G_t
        excess_capacity_ratio = W_t_all / W_G_t if W_G_t != 0.0 else math.inf

        h_bar_CR = worm_heat_transfer_coeff(float(dsg["worm_rpm"]), bool(dsg["fan_on_worm_shaft"]))
        H_loss = 33000.0 * (1.0 - e_w) * H_W
        A_min = 43.2 * C**1.7

        clearance = float(dsg.get("rough_clearance_in", 6.0))
        vertical = chosen_d + D + clearance
        width = D + clearance
        thickness = chosen_d + clearance
        rough_area = 2.0 * vertical * width + 2.0 * thickness * vertical + width * thickness
        actual_area = round_up(rough_area, float(dsg.get("actual_area_rounding_increment_in2", 100.0)))
        if "actual_lateral_area_in2" in dsg:
            actual_area = float(dsg["actual_lateral_area_in2"])

        ambient = float(dsg["ambient_temp_F"])
        t_s_actual_area = ambient + H_loss / (h_bar_CR * actual_area)
        t_s_min_area = ambient + H_loss / (h_bar_CR * A_min)
        acceptable_sump_temperature_F = float(dsg.get("acceptable_sump_temperature_F", 200.0))
        sump_temperature_ok_actual_area = t_s_actual_area <= acceptable_sump_temperature_F
        sump_temperature_ok_min_area = t_s_min_area <= acceptable_sump_temperature_F

        y = worm_lewis_y(phi_n_deg)
        sigma = W_G_t / (kin["p_n_in"] * F_e_selected * y)

        return {
            "problem": self.solve_path,
            "title": p.get("title", "Design of a worm gear set"),
            "inputs": p,
            "prechecks": {
                "minimum_gear_teeth_required": min_teeth,
                "acceptable_gear_teeth": acceptable_gear_teeth,
            },
            "iterations": {
                "worm_pitch_diameter_trials": d_trials,
            },
            "selected_design": {
                "geometry": {
                    "N_W": N_W,
                    "N_G": N_G,
                    "m_G": m_G,
                    "P_t": P_t,
                    "D_in": D,
                    "a_in": a,
                    "b_in": b,
                    "h_t_in": h_t,
                    "chosen_d_in": chosen_d,
                    "center_distance_C_in": C,
                    "lead_angle_lambda_deg": kin["lambda_deg"],
                    "lambda_max_deg": lambda_max_deg,
                    "lead_angle_ok": lead_angle_ok,
                    "P_n": kin["P_n"],
                    "p_n_in": kin["p_n_in"],
                },
                "kinematics": kin,
                "capacity_factors": capacity_factors,
                "forces_and_powers": {
                    "friction_coefficient_f": friction_coeff,
                    "mesh_efficiency_e_worm_drives": e_w,
                    "mesh_efficiency_e_gear_drives": e_g,
                    "worm_tangential_force_W_W_t_lbf": W_W_t,
                    "gear_tangential_force_W_G_t_lbf": W_G_t,
                    "worm_power_H_W_hp": H_W,
                    "gear_power_H_G_hp": H_G,
                    "friction_force_W_f_lbf": W_f,
                    "friction_power_H_f_hp": H_f,
                },
                "capacity": {
                    "effective_face_width_required_F_e_req_in": F_e_req,
                    "effective_face_width_max_in": F_e_max,
                    "effective_face_width_selected_in": F_e_selected,
                    "allowable_tangential_force_W_t_all_lbf": W_t_all,
                    "force_capacity_ok": excess_capacity_ok,
                    "excess_capacity_margin_lbf": excess_capacity_margin_lbf,
                    "excess_capacity_ratio": excess_capacity_ratio,
                    "capacity_check_note": "Passes excess-capacity check when W_G_t < W_t_all.",
                },
                "thermal": {
                    "h_bar_CR_ft_lbf_per_min_in2_F": h_bar_CR,
                    "heat_loss_rate_H_loss_ft_lbf_per_min": H_loss,
                    "minimum_case_area_A_min_in2": A_min,
                    "rough_case_area_vertical_in": vertical,
                    "rough_case_area_width_in": width,
                    "rough_case_area_thickness_in": thickness,
                    "rough_case_area_in2": rough_area,
                    "actual_lateral_area_in2": actual_area,
                    "sump_temperature_with_actual_area_F": t_s_actual_area,
                    "sump_temperature_with_A_min_F": t_s_min_area,
                    "acceptable_sump_temperature_F": acceptable_sump_temperature_F,
                    "sump_temperature_satisfactory_with_actual_area": sump_temperature_ok_actual_area,
                    "sump_temperature_satisfactory_with_A_min": sump_temperature_ok_min_area,
                    "sump_temperature_check_note": "Common practice target from Ugural-style guidance: lubricant temperature should typically not exceed about 200 F.",
                },
                "bending": {
                    "lewis_y": y,
                    "sigma_gear_psi": sigma,
                },
                "risk_source": "capacity_or_temperature",
            },
        }
