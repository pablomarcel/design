from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

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

        # Purely data-driven behavior: if the exact point exists in the CSV,
        # return it directly; otherwise use the interpolator on the chart data.
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


@dataclass
class StraightBevelCommon:
    repo: DataRepository
    spec: Mapping[str, Any]

    def geometry(self, np_teeth: float, ng_teeth: float, pd: float, face_width_in: float) -> Dict[str, float]:
        d_p = np_teeth / pd
        d_g = ng_teeth / pd
        gamma = __import__("math").atan(np_teeth / ng_teeth)
        Gamma = __import__("math").atan(ng_teeth / np_teeth)
        d_av = d_p - face_width_in * __import__("math").cos(Gamma)
        return {
            "N_P": np_teeth,
            "N_G": ng_teeth,
            "P_d": pd,
            "F_in": face_width_in,
            "d_P_in": d_p,
            "d_G_in": d_g,
            "gamma_rad": gamma,
            "Gamma_rad": Gamma,
            "gamma_deg": gamma * 180.0 / __import__("math").pi,
            "Gamma_deg": Gamma * 180.0 / __import__("math").pi,
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
        kl_branch = d.get("K_L_branch", "general")

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
            cycles=float(d["pinion_cycles"]),
            pinion_hb=float(material["pinion_hb"]),
            gear_hb=float(material["gear_hb"]),
            case_hardened_pinion=bool(material.get("case_hardened_pinion", False)),
            kl_branch=kl_branch,
            pinion_surface_finish_um=material.get("pinion_surface_finish_um"),
        )

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
                common_pre=common_pre,
                spec=d,
                material=material,
                kl_branch=kl_branch,
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

    def _evaluate_candidate(self, *, pd: float, np_teeth: float, ng_teeth: float, rpm: float, horsepower: float, qv: float,
                            sf_target: float, sh_target: float, common_pre: Dict[str, Any], spec: Mapping[str, Any],
                            material: Mapping[str, Any], kl_branch: str) -> Dict[str, Any]:
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
            cycles=float(spec["pinion_cycles"]),
            pinion_hb=float(material["pinion_hb"]),
            gear_hb=float(material["gear_hb"]),
            case_hardened_pinion=bool(material.get("case_hardened_pinion", False)),
            kl_branch=kl_branch,
            pinion_surface_finish_um=material.get("pinion_surface_finish_um"),
        )
        geom = common["geometry"]
        sat = self.repo.steel_table_value("table_15_6.csv", material["heat_treatment"], int(material["agma_grade"]))["lbf_per_in2"]
        sac = self.repo.steel_table_value("table_15_4.csv", material["heat_treatment"], int(material["agma_grade"]))["lbf_per_in2"]
        cp = float(material.get("C_P", elastic_coefficient_cp_steel_default()))

        sigma_gear = (wt / geom["F_in"]) * geom["P_d"] * common["K_o"] * common["K_v"] * common["K_s"] * common["K_m"] / (common["K_x"] * common["J_G"])
        sigma_pinion = (wt / geom["F_in"]) * geom["P_d"] * common["K_o"] * common["K_v"] * common["K_s"] * common["K_m"] / (common["K_x"] * common["J_P"])
        sigma_all_bending = sat * common["K_L"] / (sf_target * common["K_T"] * common["K_R"])
        ratio_gear_bending = sigma_all_bending / sigma_gear
        ratio_pinion_bending = sigma_all_bending / sigma_pinion
        actual_sf_gear = sf_target * ratio_gear_bending
        actual_sf_pinion = sf_target * ratio_pinion_bending

        sigma_c = cp * ((wt / (geom["F_in"] * geom["d_P_in"] * common["I"])) * common["K_o"] * common["K_v"] * common["K_m"] * common["C_s"] * common["C_xc"]) ** 0.5
        sigma_all_contact = sac * common["C_L"] * common["C_H"] / (sh_target * common["K_T"] * common["C_R"])
        ratio_contact = sigma_all_contact / sigma_c
        actual_sh_squared_gear = (ratio_contact * sh_target) ** 2
        actual_sh_squared_pinion = actual_sh_squared_gear

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
                "sigma_allowable_psi": sigma_all_bending,
            },
            "wear": {
                "s_ac_psi": sac,
                "sigma_contact_psi": sigma_c,
                "sigma_contact_allowable_psi": sigma_all_contact,
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
