from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core import (
    D_from_OD,
    ID_from_D,
    OD_from_D,
    SpringData,
    buckling_l0_cr_steel,
    equation_10_23,
    equation_10_23_d_from_strength,
    fatigue_forces,
    extension_active_turns,
    extension_free_length,
    extension_hook_bending_factor,
    extension_hook_bending_stress,
    extension_hook_torsion_factor,
    extension_hook_torsion_stress,
    torsion_ki,
    torsion_static_yield_strength,
    torsion_max_moment_for_yield,
    torsion_body_deflection_turns,
    torsion_active_turns,
    torsion_rate_per_turn,
    torsion_loaded_diameter,
    torsion_diametral_clearance,
    torsion_bending_stress,
    torsion_fatigue_endurance_from_Sr,
    extension_initial_tension_preferred_range_psi,
    figure_of_merit,
    fs_solid,
    gerber_allowable_shear_amplitude,
    gerber_nf,
    gerber_sse_from_zimmerli,
    goodman_allowable_shear_amplitude,
    goodman_sse_from_zimmerli,
    kb,
    load_line_slope,
    natural_frequency_hz,
    spring_index,
    spring_rate,
    sines_nf,
    ssu_from_sut,
    sut_from_table_104,
    tau_max,
    weight_lbf,
    zimmerli,
)
from utils import round_dict


class BaseSpringSolver:
    solve_path = "base"

    def __init__(self, spring_data: Optional[SpringData] = None) -> None:
        self.db = spring_data or SpringData()

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def _material_context(self, material: str, d_in: float, set_removed: bool = False, percent_strategy: str = "min") -> Dict[str, Any]:
        t104 = self.db.get_material_104(material, d_in)
        t105 = self.db.get_material_105(material, d_in)
        percent = self.db.get_allowable_percent_106(material, set_removed=set_removed, strategy=percent_strategy)
        Sut_kpsi = sut_from_table_104(t104["A_kpsi_in_m"], t104["m"], d_in)
        Ssy_kpsi = percent * Sut_kpsi
        return {
            "table_10_4": t104,
            "table_10_5": t105,
            "percent_of_Sut_for_Ssy": percent,
            "Sut_kpsi": Sut_kpsi,
            "Ssy_kpsi": Ssy_kpsi,
            "G_psi": t105["G_Mpsi"] * 1e6,
            "E_psi": t105["E_Mpsi"] * 1e6,
            "relative_cost": t104.get("relative_cost") or 1.0,
        }


    def _extension_material_context(self, material: str, d_in: float, percent_strategy: str = "min", high_initial_tension: bool = False) -> Dict[str, Any]:
        t104 = self.db.get_material_104(material, d_in)
        t105 = self.db.get_material_105(material, d_in)
        Sut_kpsi = sut_from_table_104(t104["A_kpsi_in_m"], t104["m"], d_in)
        Ssu_kpsi = ssu_from_sut(Sut_kpsi)
        pct_body_torsion = self.db.get_allowable_percent_107(material, location="body", mode="torsion", strategy=percent_strategy, high_initial_tension=high_initial_tension)
        pct_end_torsion = self.db.get_allowable_percent_107(material, location="end", mode="torsion", strategy=percent_strategy, high_initial_tension=high_initial_tension)
        pct_end_bending = self.db.get_allowable_percent_107(material, location="end", mode="bending", strategy=percent_strategy, high_initial_tension=high_initial_tension)
        return {
            "table_10_4": t104,
            "table_10_5": t105,
            "Sut_kpsi": Sut_kpsi,
            "Ssu_kpsi": Ssu_kpsi,
            "G_psi": t105["G_Mpsi"] * 1e6,
            "E_psi": t105["E_Mpsi"] * 1e6,
            "body_torsion_pct": pct_body_torsion,
            "end_torsion_pct": pct_end_torsion,
            "end_bending_pct": pct_end_bending,
            "Ssy_body_kpsi": pct_body_torsion * Sut_kpsi,
            "Ssy_end_torsion_kpsi": pct_end_torsion * Sut_kpsi,
            "Sy_end_bending_kpsi": pct_end_bending * Sut_kpsi,
            "relative_cost": t104.get("relative_cost") or 1.0,
        }


class CompressionAnalysisSolver(BaseSpringSolver):
    solve_path = "compression_analysis"

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material = payload["material"]
        d = float(payload["d_in"])
        OD = float(payload["OD_in"])
        Nt = float(payload["Nt"])
        end_type = payload["end_type"]
        support = payload.get("end_condition", "fixed_fixed")
        set_removed = bool(payload.get("set_removed", False))
        ctx = self._material_context(material, d, set_removed=set_removed, percent_strategy=payload.get("percent_strategy", "min"))

        D = D_from_OD(OD, d)
        C = spring_index(D, d)
        KB = kb(C)
        F = ctx["Ssy_kpsi"] * 1000.0 * 3.141592653589793 * d ** 3 / (8.0 * KB * D)
        eqs = self.db.get_end_equations(end_type)
        Ne = eval(eqs["Ne"], {}, {})
        Na = Nt - Ne
        k = spring_rate(D, d, Na, ctx["G_psi"])
        y = F / k
        Ls = eval(eqs["Ls"], {}, {"d": d, "Nt": Nt})
        L0 = y + Ls
        alpha_end = self.db.get_end_condition_alpha(support)
        L0_cr = buckling_l0_cr_steel(D, alpha_end)
        stable = L0 < L0_cr
        p = eval(eqs["p"], {}, {"L0": L0, "d": d, "Na": Na})

        result = {
            "solve_path": self.solve_path,
            "inputs": payload,
            "material": material,
            "material_context": ctx,
            "computed": {
                "D_in": D,
                "C": C,
                "KB": KB,
                "F_lbf": F,
                "Na": Na,
                "k_lbf_per_in": k,
                "y_in": y,
                "Ls_in": Ls,
                "L0_in": L0,
                "L0_critical_in": L0_cr,
                "buckling_safe": stable,
                "pitch_in": p,
            },
        }
        return round_dict(result)


class StaticSelectionSolver(BaseSpringSolver):
    solve_path = "static_select"

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material = payload["material"]
        Fmax = float(payload["Fmax_lbf"])
        ymax = float(payload["ymax_in"])
        ns = float(payload["design_factor_solid"])
        xi = float(payload.get("robust_linearity", 0.15))
        end_type = payload["end_type"]
        support = payload.get("end_condition", "fixed_fixed")
        mode = payload.get("mode", "free")
        set_removed = bool(payload.get("set_removed", False))
        gamma = float(payload.get("gamma_lb_per_in3", 0.284))
        d_values = [float(x) for x in payload["d_values_in"]]
        Ls_max = payload.get("Ls_max_in")
        L0_max = payload.get("L0_max_in")
        freq_required = payload.get("operating_frequency_hz")
        min_fn_ratio = float(payload.get("frequency_ratio", 20.0))

        rows = []
        alpha_end = self.db.get_end_condition_alpha(support)
        for d in d_values:
            ctx = self._material_context(material, d, set_removed=set_removed, percent_strategy=payload.get("percent_strategy", "min"))
            if mode == "free":
                alpha = ctx["Ssy_kpsi"] * 1000.0 / ns
                beta = 8.0 * (1.0 + xi) * Fmax / (3.141592653589793 * d ** 2)
                C = equation_10_23(alpha, beta)
                D = C * d
            elif mode == "over_rod":
                D = float(payload["rod_diameter_in"]) + d + float(payload.get("allowance_in", 0.0))
                C = D / d
            elif mode == "in_hole":
                D = float(payload["hole_diameter_in"]) - d - float(payload.get("allowance_in", 0.0))
                C = D / d
            else:
                raise ValueError(f"Unknown mode: {mode}")

            KB = kb(C)
            Fs = fs_solid(Fmax, xi)
            tau_s_psi = tau_max(Fs, D, d, KB)
            ns_actual = ctx["Ssy_kpsi"] * 1000.0 / tau_s_psi

            OD = OD_from_D(D, d)
            ID = ID_from_D(D, d)

            # Example 10-2 path:
            # use the service deflection ymax to size Na from k = Fmax / ymax,
            # then use the solid-load deflection ys = Fs / k to compute free length.
            Na = ctx["G_psi"] * d ** 4 * ymax / (8.0 * D ** 3 * Fmax)
            k = spring_rate(D, d, Na, ctx["G_psi"])
            ys = Fs / k

            end_eqs = self.db.get_end_equations(end_type)
            Nt = eval(end_eqs["Nt"], {}, {"Na": Na})
            Ls = eval(end_eqs["Ls"], {}, {"d": d, "Nt": Nt})
            L0 = Ls + ys

            L0_cr = buckling_l0_cr_steel(D, alpha_end)

            # For the textbook-style comparison in Example 10-2, omit gamma
            # from the figure of merit when comparing steel candidates.
            fom = figure_of_merit(ctx["relative_cost"], d, D, Nt, include_gamma=False)

            W = weight_lbf(d, D, Na, gamma)
            fn = natural_frequency_hz(k, W)

            constraints = {
                "Na_range": 3.0 <= Na <= 15.0,
                "C_range": 4.0 <= C <= 12.0,
                "buckling": L0_cr > L0,
                "Ls_limit": True if Ls_max is None else Ls <= float(Ls_max),
                "L0_limit": True if L0_max is None else L0 <= float(L0_max),
                "fn_limit": True if freq_required is None else fn >= min_fn_ratio * float(freq_required),
            }
            feasible = all(constraints.values())
            rows.append({
                "d_in": d,
                "D_in": D,
                "ID_in": ID,
                "OD_in": OD,
                "C": C,
                "Na": Na,
                "Nt": Nt,
                "Ls_in": Ls,
                "L0_in": L0,
                "L0_cr_in": L0_cr,
                "ns": ns_actual,
                "fn_hz": fn,
                "fom": fom,
                "feasible": feasible,
                "active_constraints": [k for k, v in constraints.items() if not v],
            })

        feasible_rows = [r for r in rows if r["feasible"]]
        selected = None
        if feasible_rows:
            selected = max(feasible_rows, key=lambda r: r["fom"])
        return round_dict({
            "solve_path": self.solve_path,
            "inputs": payload,
            "candidate_rows": rows,
            "selected": selected,
            "selection_rule": "highest figure of merit among feasible rows",
        })


class StaticCDesignSolver(BaseSpringSolver):
    solve_path = "static_iter_c"

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material = payload["material"]
        F = float(payload["F_lbf"])
        y = float(payload["y_in"])
        Fs = float(payload["Fs_lbf"])
        ns_target = float(payload["design_factor_solid"])
        end_type = payload["end_type"]
        support = payload.get("end_condition", "fixed_fixed")
        table_system = payload.get("wire_table_system", "steel_wire_washburn_moen")
        set_removed = bool(payload.get("set_removed", False))
        C_start = float(payload.get("C_start", 4.0))
        C_stop = float(payload.get("C_stop", 16.0))
        C_step = float(payload.get("C_step", 0.1))
        alpha_end = self.db.get_end_condition_alpha(support)
        k_required = F / y
        candidates = []
        percent = self.db.get_allowable_percent_106(material, set_removed=set_removed, strategy=payload.get("percent_strategy", "min"))
        t104 = self.db.get_material_104(material)
        G_psi_ref = self.db.get_material_105(material)["G_Mpsi"] * 1e6
        C = C_start
        while C <= C_stop + 1e-12:
            d_calc = equation_10_23_d_from_strength(t104["A_kpsi_in_m"], t104["m"], percent, ns_target, Fs, C)
            sel = self.db.select_wire_from_a28(table_system, d_calc, prefer="at_or_above")
            d_sel = sel["diameter_in"]
            ctx = self._material_context(material, d_sel, set_removed=set_removed, percent_strategy=payload.get("percent_strategy", "min"))
            D = C * d_sel
            KB = kb(C)
            tau_s_psi = tau_max(Fs, D, d_sel, KB)
            ns_actual = ctx["Ssy_kpsi"] * 1000.0 / tau_s_psi
            Na = ctx["G_psi"] * d_sel ** 4 / (8.0 * D ** 3 * k_required)
            end_eqs = self.db.get_end_equations(end_type)
            Nt = eval(end_eqs["Nt"], {}, {"Na": Na})
            ys = Fs / k_required
            Ls = eval(end_eqs["Ls"], {}, {"d": d_sel, "Nt": Nt})
            L0 = Ls + ys
            OD = OD_from_D(D, d_sel)
            stable = L0 < buckling_l0_cr_steel(D, alpha_end)
            constraints = {
                "Na_range": 3.0 <= Na <= 15.0,
                "C_range": 4.0 <= C <= 12.0,
                "buckling": stable,
                "ns_target": ns_actual >= ns_target,
            }
            feasible = all(constraints.values())
            candidates.append({
                "C_trial": C,
                "d_required_in": d_calc,
                "selected_gauge": sel["gauge"],
                "selected_d_in": d_sel,
                "Na": Na,
                "Nt": Nt,
                "ys_in": ys,
                "Ls_in": Ls,
                "L0_in": L0,
                "D_in": D,
                "OD_in": OD,
                "ns": ns_actual,
                "feasible": feasible,
                "active_constraints": [k for k, v in constraints.items() if not v],
            })
            C += C_step
        feasible_rows = [r for r in candidates if r["feasible"]]
        selected = None
        if feasible_rows:
            selected = min(feasible_rows, key=lambda r: (r["selected_d_in"], r["C_trial"]))
        return round_dict({
            "solve_path": self.solve_path,
            "inputs": payload,
            "k_required_lbf_per_in": k_required,
            "candidate_rows": candidates,
            "selected": selected,
            "selection_rule": "smallest feasible selected wire diameter, then smallest C trial",
        })


class FatigueAnalysisSolver(BaseSpringSolver):
    solve_path = "fatigue_check"

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material = payload["material"]
        d = float(payload["d_in"])
        OD = float(payload["OD_in"])
        Na = float(payload["Na"])
        Fmin = float(payload["Fmin_lbf"])
        Fmax = float(payload["Fmax_lbf"])
        surface = payload.get("surface_treatment", "unpeened")
        gamma = float(payload.get("gamma_lb_per_in3", 0.284))
        operating_freq = payload.get("operating_frequency_hz")
        ctx = self._material_context(material, d, set_removed=False, percent_strategy=payload.get("percent_strategy", "min"))
        D = D_from_OD(OD, d)
        C = spring_index(D, d)
        KB = kb(C)
        forces = fatigue_forces(Fmin, Fmax)
        tau_a_kpsi = tau_max(forces["Fa"], D, d, KB) / 1000.0
        tau_m_kpsi = tau_max(forces["Fm"], D, d, KB) / 1000.0
        Ssu_kpsi = ssu_from_sut(ctx["Sut_kpsi"])
        r = load_line_slope(tau_a_kpsi, tau_m_kpsi)
        z = zimmerli(unpeened=(surface == "unpeened"))
        Sse_gerber = gerber_sse_from_zimmerli(z["Ssa_kpsi"], z["Ssm_kpsi"], Ssu_kpsi)
        Ssa_gerber = gerber_allowable_shear_amplitude(r, Sse_gerber, Ssu_kpsi)
        nf_gerber = Ssa_gerber / tau_a_kpsi
        nf_sines = sines_nf(z["Ssa_kpsi"], tau_a_kpsi)
        Sse_goodman = goodman_sse_from_zimmerli(z["Ssa_kpsi"], z["Ssm_kpsi"], Ssu_kpsi)
        Ssa_goodman = goodman_allowable_shear_amplitude(r, Sse_goodman, Ssu_kpsi)
        nf_goodman = Ssa_goodman / tau_a_kpsi
        k = spring_rate(D, d, Na, ctx["G_psi"])
        W = weight_lbf(d, D, Na, gamma)
        fn = natural_frequency_hz(k, W)
        frequency_check = None if operating_freq is None else (fn >= float(payload.get("frequency_ratio", 20.0)) * float(operating_freq))
        return round_dict({
            "solve_path": self.solve_path,
            "inputs": payload,
            "material_context": ctx,
            "computed": {
                "D_in": D,
                "C": C,
                "KB": KB,
                "Fa_lbf": forces["Fa"],
                "Fm_lbf": forces["Fm"],
                "tau_a_kpsi": tau_a_kpsi,
                "tau_m_kpsi": tau_m_kpsi,
                "Ssu_kpsi": Ssu_kpsi,
                "r": r,
                "zimmerli": z,
                "gerber": {"Sse_kpsi": Sse_gerber, "Ssa_allowable_kpsi": Ssa_gerber, "nf": nf_gerber},
                "sines": {"Ssa_allowable_kpsi": z["Ssa_kpsi"], "nf": nf_sines},
                "goodman": {"Sse_kpsi": Sse_goodman, "Ssa_allowable_kpsi": Ssa_goodman, "nf": nf_goodman},
                "k_lbf_per_in": k,
                "weight_lbf": W,
                "fundamental_frequency_hz": fn,
                "frequency_safe": frequency_check,
            },
        })


class FatigueDesignSolver(BaseSpringSolver):
    solve_path = "fatigue_design_iter"

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material = payload["material"]
        d_values = [float(x) for x in payload["d_values_in"]]
        Fmin = float(payload["Fmin_lbf"])
        Fmax = float(payload["Fmax_lbf"])
        ymin = float(payload["ymin_in"])
        ymax = float(payload["ymax_in"])
        freq_load = float(payload["load_frequency_hz"])
        xi = float(payload.get("robust_linearity", 0.15))
        gamma = float(payload.get("gamma_lb_per_in3", 0.284))
        nf_target = float(payload["nf_target"])
        end_type = payload["end_type"]
        support = payload.get("end_condition", "fixed_fixed")
        alpha_end = self.db.get_end_condition_alpha(support)
        surface = payload.get("surface_treatment", "unpeened")
        set_removed = bool(payload.get("set_removed", False))
        rows = []
        Fa = 0.5 * (Fmax - Fmin)
        Fm = 0.5 * (Fmax + Fmin)
        k_req = Fmax / ymax
        Ssa_zimmerli = zimmerli(unpeened=(surface == "unpeened"))["Ssa_kpsi"]
        for d in sorted(d_values, reverse=True):
            ctx = self._material_context(material, d, set_removed=set_removed, percent_strategy=payload.get("percent_strategy", "min"))
            Ssu_kpsi = ssu_from_sut(ctx["Sut_kpsi"])
            Sse_kpsi = Ssa_zimmerli  # Sines-Zimmerli path
            alpha = Sse_kpsi * 1000.0 / nf_target
            beta = 8.0 * Fa / (3.141592653589793 * d ** 2)
            C = equation_10_23(alpha, beta)
            D = C * d
            Fs = fs_solid(Fmax, xi)
            Na = ctx["G_psi"] * d ** 4 / (8.0 * D ** 3 * k_req)
            end_eqs = self.db.get_end_equations(end_type)
            Nt = eval(end_eqs["Nt"], {}, {"Na": Na})
            Ls = eval(end_eqs["Ls"], {}, {"d": d, "Nt": Nt})
            L0 = Ls + Fs / k_req
            ID = ID_from_D(D, d)
            OD = OD_from_D(D, d)
            ys = L0 - Ls
            L0_cr = buckling_l0_cr_steel(D, alpha_end)
            KB = kb(C)
            W = weight_lbf(d, D, Na, gamma)
            fn = natural_frequency_hz(k_req, W)
            tau_a_psi = tau_max(Fa, D, d, KB)
            tau_m_psi = tau_max(Fm, D, d, KB)
            tau_s_psi = tau_a_psi * Fs / Fa
            nf = (Ssa_zimmerli * 1000.0) / tau_a_psi
            ns = (ctx["Ssy_kpsi"] * 1000.0) / tau_s_psi
            fom = figure_of_merit(ctx["relative_cost"], d, D, Nt, include_gamma=False)
            constraints = {
                "Ls_limit": Ls <= float(payload["Ls_max_in"]),
                "L0_limit": L0 <= float(payload["L0_max_in"]),
                "fn_limit": fn >= float(payload.get("frequency_ratio", 20.0)) * freq_load,
                "Na_range": 3.0 <= Na <= 15.0,
                "C_range": 4.0 <= C <= 12.0,
                "buckling": L0_cr > L0,
            }
            feasible = all(constraints.values())
            rows.append({
                "d_in": d,
                "D_in": D,
                "ID_in": ID,
                "OD_in": OD,
                "C": C,
                "Na": Na,
                "Nt": Nt,
                "Ls_in": Ls,
                "L0_in": L0,
                "L0_cr_in": L0_cr,
                "nf": nf,
                "ns": ns,
                "fn_hz": fn,
                "fom": fom,
                "tau_a_psi": tau_a_psi,
                "tau_m_psi": tau_m_psi,
                "tau_s_psi": tau_s_psi,
                "feasible": feasible,
                "active_constraints": [k for k, v in constraints.items() if not v],
            })
        feasible_rows = [r for r in rows if r["feasible"]]
        selected = None if not feasible_rows else max(feasible_rows, key=lambda r: r["fom"])
        return round_dict({
            "solve_path": self.solve_path,
            "inputs": payload,
            "criterion_path": "Sines-Zimmerli",
            "candidate_rows": rows,
            "selected": selected,
            "selection_rule": "highest figure of merit among feasible rows",
            "note": "If no row is feasible, user should inspect the table and make an engineering decision.",
        })




class ExtensionStaticServiceSolver(BaseSpringSolver):
    solve_path = "extension_static_service"

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material = payload["material"]
        d = float(payload["d_in"])
        OD = float(payload["OD_in"])
        r1 = float(payload["r1_in"])
        r2 = float(payload["r2_in"])
        Fi = float(payload["Fi_lbf"])
        Nb = float(payload["Nb"])
        Fmax = float(payload["Fmax_lbf"])
        high_initial_tension = bool(payload.get("high_initial_tension", False))
        ctx = self._extension_material_context(material, d, percent_strategy=payload.get("percent_strategy", "min"), high_initial_tension=high_initial_tension)
        D = D_from_OD(OD, d)
        C = spring_index(D, d)
        KB_body = kb(C)
        Na = extension_active_turns(Nb, ctx["G_psi"], ctx["E_psi"])
        k = spring_rate(D, d, Na, ctx["G_psi"])
        L0 = extension_free_length(D, d, Nb)
        y_service = (Fmax - Fi) / k
        L_service = L0 + y_service
        tau_i_uncorrected_kpsi = (8.0 * Fi * D / (3.141592653589793 * d ** 3)) / 1000.0
        tau_i_pref = extension_initial_tension_preferred_range_psi(C)
        initial_tension_preferred_range_ok = tau_i_pref["low_psi"] <= tau_i_uncorrected_kpsi * 1000.0 <= tau_i_pref["high_psi"]
        tau_body_kpsi = tau_max(Fmax, D, d, KB_body) / 1000.0
        n_body = ctx["Ssy_body_kpsi"] / tau_body_kpsi
        hookA = extension_hook_bending_factor(r1, d)
        sigma_A_kpsi = extension_hook_bending_stress(Fmax, D, d, hookA["K_A"]) / 1000.0
        n_A = ctx["Sy_end_bending_kpsi"] / sigma_A_kpsi
        hookB = extension_hook_torsion_factor(r2, d)
        tau_B_kpsi = extension_hook_torsion_stress(Fmax, D, d, hookB["K_B_hook"]) / 1000.0
        n_B = ctx["Ssy_end_torsion_kpsi"] / tau_B_kpsi
        checks = {"body_torsion": n_body, "hook_bending_A": n_A, "hook_torsion_B": n_B}
        failure_first = min(checks, key=checks.get)
        return round_dict({"solve_path": self.solve_path, "inputs": payload, "material_context": ctx, "computed": {"D_in": D, "C": C, "KB_body": KB_body, "Na": Na, "Nb": Nb, "k_lbf_per_in": k, "L0_in": L0, "y_service_in": y_service, "L_service_in": L_service, "tau_i_uncorrected_kpsi": tau_i_uncorrected_kpsi, "tau_i_preferred_range_kpsi": {"center": tau_i_pref["center_psi"] / 1000.0, "low": tau_i_pref["low_psi"] / 1000.0, "high": tau_i_pref["high_psi"] / 1000.0}, "initial_tension_preferred_range_ok": initial_tension_preferred_range_ok, "body": {"Ssy_kpsi": ctx["Ssy_body_kpsi"], "tau_max_kpsi": tau_body_kpsi, "n": n_body}, "hook_bending_A": {"C1": hookA["C1"], "K_A": hookA["K_A"], "sigma_A_kpsi": sigma_A_kpsi, "Sy_bending_kpsi": ctx["Sy_end_bending_kpsi"], "n": n_A}, "hook_torsion_B": {"C2": hookB["C2"], "K_B_hook": hookB["K_B_hook"], "tau_B_kpsi": tau_B_kpsi, "Ssy_torsion_kpsi": ctx["Ssy_end_torsion_kpsi"], "n": n_B}, "failure_first": failure_first}})


class ExtensionDynamicLoadingSolver(BaseSpringSolver):
    solve_path = "extension_dynamic_loading"

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        import math
        material = payload["material"]
        surface = payload.get("surface_treatment", "unpeened")
        d = float(payload["d_in"])
        OD = float(payload["OD_in"])
        r1 = float(payload["r1_in"])
        r2 = float(payload["r2_in"])
        Fi = float(payload["Fi_lbf"])
        Nb = float(payload["Nb"])
        Fmin = float(payload["Fmin_lbf"])
        Fmax = float(payload["Fmax_lbf"])
        ctx = self._extension_material_context(material, d, percent_strategy=payload.get("percent_strategy", "min"))
        D = D_from_OD(OD, d)
        C = spring_index(D, d)
        KB_body = kb(C)
        Na = extension_active_turns(Nb, ctx["G_psi"], ctx["E_psi"])
        k = spring_rate(D, d, Na, ctx["G_psi"])
        L0 = extension_free_length(D, d, Nb)
        Fa = 0.5 * (Fmax - Fmin)
        Fm = 0.5 * (Fmax + Fmin)
        tau_a_body_kpsi = tau_max(Fa, D, d, KB_body) / 1000.0
        tau_m_body_kpsi = tau_max(Fm, D, d, KB_body) / 1000.0
        tau_i_corr_kpsi = tau_max(Fi, D, d, KB_body) / 1000.0
        z = zimmerli(unpeened=(surface == "unpeened"))
        Sse_shear_kpsi = gerber_sse_from_zimmerli(z["Ssa_kpsi"], z["Ssm_kpsi"], ctx["Ssu_kpsi"])
        nf_body = gerber_nf(tau_a_body_kpsi, tau_m_body_kpsi, Sse_shear_kpsi, ctx["Ssu_kpsi"])
        denom = tau_m_body_kpsi - tau_i_corr_kpsi
        r_yield = tau_a_body_kpsi / denom if abs(denom) > 1e-12 else float("inf")
        Ssa_y = (r_yield / (1.0 + r_yield)) * (ctx["Ssy_body_kpsi"] - tau_i_corr_kpsi) if math.isfinite(r_yield) else ctx["Ssy_body_kpsi"] - tau_i_corr_kpsi
        ny_body = Ssa_y / tau_a_body_kpsi
        hookA = extension_hook_bending_factor(r1, d)
        sigma_a_A_kpsi = extension_hook_bending_stress(Fa, D, d, hookA["K_A"]) / 1000.0
        sigma_m_A_kpsi = extension_hook_bending_stress(Fm, D, d, hookA["K_A"]) / 1000.0
        Se_tension_kpsi = Sse_shear_kpsi / 0.577
        nf_A = gerber_nf(sigma_a_A_kpsi, sigma_m_A_kpsi, Se_tension_kpsi, ctx["Sut_kpsi"])
        hookB = extension_hook_torsion_factor(r2, d)
        tau_a_B_kpsi = extension_hook_torsion_stress(Fa, D, d, hookB["K_B_hook"]) / 1000.0
        tau_m_B_kpsi = extension_hook_torsion_stress(Fm, D, d, hookB["K_B_hook"]) / 1000.0
        nf_B = gerber_nf(tau_a_B_kpsi, tau_m_B_kpsi, Sse_shear_kpsi, ctx["Ssu_kpsi"])
        alt_108 = None
        if payload.get("cycles") is not None:
            try:
                row_b = self.db.get_allowable_percent_108(float(payload["cycles"]), location="end", mode="bending", material_query=material)
                row_t = self.db.get_allowable_percent_108(float(payload["cycles"]), location="body", mode="torsion", material_query=material)
                alt_108 = {"bending_end": row_b, "torsion_body": row_t}
            except Exception:
                alt_108 = None
        checks = {"body_fatigue": nf_body, "body_yield": ny_body, "hook_bending_A_fatigue": nf_A, "hook_torsion_B_fatigue": nf_B}
        failure_first = min(checks, key=checks.get)
        return round_dict({"solve_path": self.solve_path, "inputs": payload, "material_context": ctx, "computed": {"D_in": D, "C": C, "KB_body": KB_body, "Na": Na, "Nb": Nb, "L0_in": L0, "k_lbf_per_in": k, "Fa_lbf": Fa, "Fm_lbf": Fm, "body": {"tau_a_kpsi": tau_a_body_kpsi, "tau_m_kpsi": tau_m_body_kpsi, "tau_i_corrected_kpsi": tau_i_corr_kpsi, "zimmerli": z, "Sse_kpsi": Sse_shear_kpsi, "nf_gerber": nf_body, "r_yield": r_yield, "Ssa_y_kpsi": Ssa_y, "ny": ny_body}, "hook_bending_A": {"C1": hookA["C1"], "K_A": hookA["K_A"], "sigma_a_kpsi": sigma_a_A_kpsi, "sigma_m_kpsi": sigma_m_A_kpsi, "Se_tension_kpsi": Se_tension_kpsi, "nf_gerber": nf_A}, "hook_torsion_B": {"C2": hookB["C2"], "K_B_hook": hookB["K_B_hook"], "tau_a_kpsi": tau_a_B_kpsi, "tau_m_kpsi": tau_m_B_kpsi, "Sse_kpsi": Sse_shear_kpsi, "nf_gerber": nf_B}, "table_10_8_reference": alt_108, "failure_first": failure_first}})


class TorsionSpringSolver(BaseSpringSolver):
    solve_path = "torsion_spring"

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        material = payload["material"]
        shot_peened = bool(payload.get("shot_peened", False))
        d = float(payload["d_in"])
        Nb = float(payload["Nb"])
        OD = float(payload["OD_in"])
        Dp = float(payload["Dp_in"])
        l1 = float(payload.get("l1_in", 1.0))
        l2 = float(payload.get("l2_in", 1.0))
        Mmin = float(payload.get("Mmin_lbf_in", 1.0))
        Mmax_fatigue = float(payload.get("Mmax_lbf_in", 5.0))
        fatigue_cycles = float(payload.get("fatigue_cycles", 1e6))

        t104 = self.db.get_material_104(material, d)
        t105 = self.db.get_material_105(material, d)
        Sut_kpsi = sut_from_table_104(t104["A_kpsi_in_m"], t104["m"], d)
        Sy_kpsi = torsion_static_yield_strength(Sut_kpsi, material)

        D = D_from_OD(OD, d)
        C = spring_index(D, d)
        Ki = torsion_ki(C)
        Mmax_static = torsion_max_moment_for_yield(d, Sy_kpsi * 1000.0, Ki)

        E_psi = t105["E_Mpsi"] * 1e6
        theta_c_prime_turns = torsion_body_deflection_turns(Mmax_static, D, Nb, d, E_psi)
        theta_c_prime_deg = theta_c_prime_turns * 360.0

        Na = torsion_active_turns(Nb, D, l1, l2)
        k_prime = torsion_rate_per_turn(d, D, Na, E_psi)
        theta_prime_turns = Mmax_static / k_prime
        theta_prime_deg = theta_prime_turns * 360.0

        D_prime = torsion_loaded_diameter(Nb, D, theta_c_prime_turns)
        delta = torsion_diametral_clearance(D_prime, d, Dp)

        Ma = 0.5 * (Mmax_fatigue - Mmin)
        Mm = 0.5 * (Mmax_fatigue + Mmin)
        r = Ma / Mm
        sigma_a_kpsi = torsion_bending_stress(Ma, d, Ki) / 1000.0
        sigma_m_kpsi = torsion_bending_stress(Mm, d, Ki) / 1000.0

        row1010 = self.db.get_allowable_percent_1010(fatigue_cycles, material, shot_peened=shot_peened)
        Sr_kpsi = row1010["percent"] * Sut_kpsi
        Se_kpsi = torsion_fatigue_endurance_from_Sr(Sr_kpsi, Sut_kpsi)
        Sa_kpsi = gerber_allowable_shear_amplitude(r, Se_kpsi, Sut_kpsi)
        nf = Sa_kpsi / sigma_a_kpsi

        return round_dict({
            "solve_path": self.solve_path,
            "inputs": payload,
            "material_context": {
                "table_10_4": t104,
                "table_10_5": t105,
                "Sut_kpsi": Sut_kpsi,
                "Sy_kpsi": Sy_kpsi,
                "E_psi": E_psi,
                "table_10_10": row1010,
            },
            "computed": {
                "D_in": D,
                "C": C,
                "Ki": Ki,
                "Mmax_static_lbf_in": Mmax_static,
                "theta_c_prime_turns": theta_c_prime_turns,
                "theta_c_prime_deg": theta_c_prime_deg,
                "Na": Na,
                "k_prime_lbf_in_per_turn": k_prime,
                "theta_prime_turns": theta_prime_turns,
                "theta_prime_deg": theta_prime_deg,
                "D_prime_in": D_prime,
                "diametral_clearance_in": delta,
                "fatigue": {
                    "Ma_lbf_in": Ma,
                    "Mm_lbf_in": Mm,
                    "r": r,
                    "sigma_a_kpsi": sigma_a_kpsi,
                    "sigma_m_kpsi": sigma_m_kpsi,
                    "Sr_kpsi": Sr_kpsi,
                    "Se_kpsi": Se_kpsi,
                    "Sa_kpsi": Sa_kpsi,
                    "nf": nf,
                },
            },
        })


class SpringApplication:
    def __init__(self) -> None:
        self.solvers = {
            CompressionAnalysisSolver.solve_path: CompressionAnalysisSolver(),
            StaticSelectionSolver.solve_path: StaticSelectionSolver(),
            StaticCDesignSolver.solve_path: StaticCDesignSolver(),
            FatigueAnalysisSolver.solve_path: FatigueAnalysisSolver(),
            FatigueDesignSolver.solve_path: FatigueDesignSolver(),
            ExtensionStaticServiceSolver.solve_path: ExtensionStaticServiceSolver(),
            ExtensionDynamicLoadingSolver.solve_path: ExtensionDynamicLoadingSolver(),
            TorsionSpringSolver.solve_path: TorsionSpringSolver(),
        }

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        solve_path = payload["solve_path"]
        if solve_path not in self.solvers:
            raise KeyError(f"Unsupported solve_path={solve_path!r}. Available: {sorted(self.solvers)}")
        return self.solvers[solve_path].solve(payload)
