from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List

try:
    from .utils import (
        ValidationError,
        find_gray_cast_iron_row,
        find_material_stiffness_row,
        find_nut_dimensions_row,
        find_preferred_fraction_size_ge,
        find_proof_strength_row,
        find_thread_row,
        find_washer_row,
        math_exp_safe,
        order_desc,
        validate_nonnegative,
        validate_positive,
    )
except ImportError:  # pragma: no cover
    from utils import (
        ValidationError,
        find_gray_cast_iron_row,
        find_material_stiffness_row,
        find_nut_dimensions_row,
        find_preferred_fraction_size_ge,
        find_proof_strength_row,
        find_thread_row,
        find_washer_row,
        math_exp_safe,
        order_desc,
        validate_nonnegative,
        validate_positive,
    )


@dataclass
class SolveResult:
    problem: str
    title: str
    inputs: Dict[str, Any]
    derived: Dict[str, Any]
    lookups: Dict[str, Any]
    outputs: Dict[str, Any]
    notes: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "problem": self.problem,
            "title": self.title,
            "inputs": self.inputs,
            "derived": self.derived,
            "lookups": self.lookups,
            "outputs": self.outputs,
            "notes": self.notes,
        }


class BaseSolver:
    solve_path: str = ""

    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        self.problem = payload.get("problem", self.solve_path)
        self.title = payload.get("title", self.solve_path)
        self.inputs = payload.get("inputs", payload)

    def solve(self) -> SolveResult:  # pragma: no cover
        raise NotImplementedError


class SquareThreadPowerScrewSolver(BaseSolver):
    solve_path = "square_thread_power_screw"

    def solve(self) -> SolveResult:
        p = self.inputs
        d = float(p["major_diameter_mm"])
        pitch = float(p["pitch_mm"])
        starts = int(p.get("starts", 1))
        f = float(p["friction_thread"])
        fc = float(p.get("friction_collar", f))
        dc = float(p["collar_mean_diameter_mm"])
        F = float(p["axial_load_N"])
        engaged_threads = float(p.get("engaged_threads", 1.0))
        first_thread_load_fraction = float(p.get("first_thread_load_fraction", 0.38))

        for name, value in [
            ("major_diameter_mm", d),
            ("pitch_mm", pitch),
            ("starts", starts),
            ("collar_mean_diameter_mm", dc),
            ("axial_load_N", F),
            ("engaged_threads", engaged_threads),
        ]:
            validate_positive(name, value)
        for name, value in [
            ("friction_thread", f),
            ("friction_collar", fc),
            ("first_thread_load_fraction", first_thread_load_fraction),
        ]:
            validate_nonnegative(name, value)

        h = pitch / 2.0
        w = pitch / 2.0
        dm = d - pitch / 2.0
        dr = d - pitch
        lead = starts * pitch
        helix_angle_rad = math.atan(lead / (math.pi * dm))

        t_thread_raise = F * (dm / 2.0) * ((lead + math.pi * f * dm) / (math.pi * dm - f * lead))
        t_thread_lower = F * (dm / 2.0) * ((math.pi * f * dm - lead) / (math.pi * dm + f * lead))
        t_collar = F * fc * dc / 2.0
        t_raise = t_thread_raise + t_collar
        t_lower = t_thread_lower + t_collar
        efficiency_raise = F * lead / (2.0 * math.pi * t_raise)
        self_locking = t_thread_lower > 0

        sigma_compressive = -4.0 * F / (math.pi * dr**2)
        tau_torsion = 16.0 * t_raise / (math.pi * dr**3)
        bearing_stress = -2.0 * first_thread_load_fraction * F / (math.pi * dm * engaged_threads * pitch)
        thread_bending_stress = 6.0 * first_thread_load_fraction * F / (math.pi * dr * engaged_threads * pitch)

        sigma_x = thread_bending_stress
        sigma_y = sigma_compressive
        sigma_z = 0.0
        tau_xy = 0.0
        tau_yz = tau_torsion
        tau_zx = 0.0

        sigma_yz_avg = 0.5 * (sigma_y + sigma_z)
        sigma_yz_radius = math.sqrt(((sigma_y - sigma_z) / 2.0) ** 2 + tau_yz**2)
        sigma_yz_1 = sigma_yz_avg + sigma_yz_radius
        sigma_yz_2 = sigma_yz_avg - sigma_yz_radius
        sigma1, sigma2, sigma3 = order_desc([sigma_x, sigma_yz_1, sigma_yz_2])

        von_mises = math.sqrt(((sigma1 - sigma2) ** 2 + (sigma2 - sigma3) ** 2 + (sigma3 - sigma1) ** 2) / 2.0)
        tau_max = (sigma1 - sigma3) / 2.0

        derived = {
            "thread_depth_mm": h,
            "thread_width_mm": w,
            "pitch_diameter_mm": dm,
            "minor_diameter_mm": dr,
            "lead_mm": lead,
            "helix_angle_deg": math.degrees(helix_angle_rad),
            "first_thread_axial_load_N": first_thread_load_fraction * F,
        }
        lookups: Dict[str, Any] = {}
        outputs = {
            "thread_torque_raise_N_mm": t_thread_raise,
            "thread_torque_lower_N_mm": t_thread_lower,
            "collar_torque_N_mm": t_collar,
            "total_torque_raise_N_mm": t_raise,
            "total_torque_raise_N_m": t_raise / 1000.0,
            "total_torque_lower_N_mm": t_lower,
            "total_torque_lower_N_m": t_lower / 1000.0,
            "raising_efficiency": efficiency_raise,
            "raising_efficiency_percent": 100.0 * efficiency_raise,
            "self_locking_on_threads": self_locking,
            "body_compressive_stress_MPa": sigma_compressive,
            "body_torsional_shear_stress_MPa": tau_torsion,
            "thread_bearing_stress_MPa": bearing_stress,
            "thread_bending_stress_MPa": thread_bending_stress,
            "root_stress_state_MPa": {
                "sigma_x": sigma_x,
                "sigma_y": sigma_y,
                "sigma_z": sigma_z,
                "tau_xy": tau_xy,
                "tau_yz": tau_yz,
                "tau_zx": tau_zx,
            },
            "principal_stresses_root_MPa": {
                "sigma_1": sigma1,
                "sigma_2": sigma2,
                "sigma_3": sigma3,
            },
            "von_mises_stress_root_MPa": von_mises,
            "maximum_shear_stress_root_MPa": tau_max,
        }
        notes = [
            "Square-thread geometry follows Shigley Example 8-1 conventions: thread depth = p/2 and thread width = p/2.",
            "Stresses are reported as N/mm^2, numerically equal to MPa.",
            "Thread-root bending and bearing stresses use the user-specified first_thread_load_fraction and engaged_threads.",
            "The root stress state follows textbook Example 8-1: sigma_x = bending, sigma_y = axial compression, sigma_z = 0, tau_yz = torsional shear, with no shear on the x-face.",
            "The remaining two principal stresses are obtained from the yz-plane stress transformation (Shigley Eq. 3-13 / 3-15).",
            "The von Mises stress is computed from the three principal stresses using the 3D form consistent with Shigley Sec. 5-5.",
            "The maximum shear stress is computed from the ordered principal stresses using Shigley Eq. 3-16.",
        ]
        return SolveResult(self.problem, self.title, p, derived, lookups, outputs, notes)


class FastenerMemberStiffnessSolver(BaseSolver):
    solve_path = "fastener_member_stiffness"

    @staticmethod
    def _frustum_stiffness(E_psi: float, d_in: float, t_in: float, D_in: float, half_angle_deg: float) -> float:
        alpha = math.radians(half_angle_deg)
        tan_alpha = math.tan(alpha)
        if abs(tan_alpha - math.tan(math.radians(30.0))) < 1e-12:
            a = 1.155 * t_in + D_in - d_in
            b = 1.155 * t_in + D_in + d_in
            c = D_in + d_in
            d = D_in - d_in
            if min(a, b, c, d) <= 0:
                raise ValidationError(
                    f"Invalid frustum stiffness geometry encountered with d={d_in}, t={t_in}, D={D_in}."
                )
            numerator = 0.5774 * math.pi * E_psi * d_in
            denominator = math.log((a * c) / (b * d))
            return numerator / denominator
        return math.pi * E_psi * d_in * tan_alpha / max(
            1e-12,
            math.log(
                ((D_in + 2.0 * t_in * tan_alpha - d_in) * (D_in + d_in))
                / ((D_in + 2.0 * t_in * tan_alpha + d_in) * (D_in - d_in))
            ),
        )

    @staticmethod
    def _split_layers_for_half(
        layers: List[Dict[str, Any]],
        total_thickness: float,
        from_top: bool = True,
    ) -> List[Dict[str, Any]]:
        midpoint = total_thickness / 2.0
        path = layers if from_top else list(reversed(layers))
        traversed = 0.0
        segments: List[Dict[str, Any]] = []
        for layer in path:
            t = float(layer["thickness_in"])
            if traversed >= midpoint:
                break
            remaining = midpoint - traversed
            use_t = min(t, remaining)
            if use_t > 0:
                segments.append(
                    {
                        "material": str(layer["material"]),
                        "thickness_in": use_t,
                    }
                )
                traversed += use_t
        return segments

    @staticmethod
    def _merge_consecutive_same_material(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not segments:
            return []
        merged: List[Dict[str, Any]] = [dict(segments[0])]
        for seg in segments[1:]:
            if str(seg["material"]).strip().lower() == str(merged[-1]["material"]).strip().lower():
                merged[-1]["thickness_in"] = float(merged[-1]["thickness_in"]) + float(seg["thickness_in"])
            else:
                merged.append(dict(seg))
        return merged

    def _build_material_lookup(self, material_names: List[str], overrides: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for name in material_names:
            key = str(name)
            if key in result:
                continue
            row = find_material_stiffness_row(key)
            E = float(overrides.get(key, row["E_psi"]))
            result[key] = {
                "table_row": row,
                "E_psi": E,
                "A": row.get("A"),
                "B": row.get("B"),
            }
        return result

    def _segment_stiffness_series(
        self,
        segments: List[Dict[str, Any]],
        side: str,
        d_in: float,
        D_start: float,
        cone_half_angle_deg: float,
        material_lookup: Dict[str, Dict[str, Any]],
    ) -> tuple[float, List[Dict[str, Any]]]:
        compliance = 0.0
        results: List[Dict[str, Any]] = []
        D_current = D_start
        for idx, seg in enumerate(segments, start=1):
            material = str(seg["material"])
            t = float(seg["thickness_in"])
            E = float(material_lookup[material]["E_psi"])
            k = self._frustum_stiffness(E, d_in, t, D_current, cone_half_angle_deg)
            results.append(
                {
                    "side": side,
                    "index": idx,
                    "material": material,
                    "thickness_in": t,
                    "start_diameter_in": D_current,
                    "stiffness_lbf_per_in": k,
                }
            )
            compliance += 1.0 / k
            D_current += 2.0 * t * math.tan(math.radians(cone_half_angle_deg))
        return compliance, results

    def solve(self) -> SolveResult:
        p = self.inputs
        d = float(p["nominal_diameter_in"])
        tpi = int(p["threads_per_inch"])
        bolt_length = float(p["bolt_length_in"])
        E_bolt = float(p.get("bolt_modulus_psi", 30e6))
        thread_series = str(p.get("thread_series", "UNF")).upper()
        washer_type = str(p.get("washer_type", "N"))
        cone_half_angle_deg = float(p.get("cone_half_angle_deg", 30.0))
        clamp_face_diameter = p.get("clamp_face_diameter_in")
        layers = p.get("layers", [])
        if not layers:
            raise ValidationError("fastener_member_stiffness requires a non-empty 'layers' list.")

        for name, value in [
            ("nominal_diameter_in", d),
            ("threads_per_inch", tpi),
            ("bolt_length_in", bolt_length),
            ("bolt_modulus_psi", E_bolt),
        ]:
            validate_positive(name, value)

        washer_lookup = None
        if clamp_face_diameter is None:
            washer_lookup = find_washer_row(d, washer_type=washer_type)
            clamp_face_diameter = float(washer_lookup["diameter_od_in"])
        else:
            clamp_face_diameter = float(clamp_face_diameter)
        validate_positive("clamp_face_diameter_in", clamp_face_diameter)

        thread_row = find_thread_row(d, thread_series, threads_per_inch=tpi)
        At = float(thread_row["tensile_stress_area_in2"])
        Ad = math.pi * d**2 / 4.0
        pitch = 1.0 / tpi

        material_overrides = p.get("material_modulus_overrides_psi", {})
        material_names = [str(layer["material"]) for layer in layers]
        material_lookup = self._build_material_lookup(material_names, material_overrides)
        total_grip = sum(float(layer["thickness_in"]) for layer in layers)

        top_segments_raw = self._split_layers_for_half(layers, total_grip, from_top=True)
        bottom_segments_raw = self._split_layers_for_half(layers, total_grip, from_top=False)

        top_segments = self._merge_consecutive_same_material(top_segments_raw)
        bottom_segments = self._merge_consecutive_same_material(bottom_segments_raw)

        top_compliance, top_results = self._segment_stiffness_series(
            top_segments,
            "top",
            d,
            clamp_face_diameter,
            cone_half_angle_deg,
            material_lookup,
        )
        bottom_compliance, bottom_results = self._segment_stiffness_series(
            bottom_segments,
            "bottom",
            d,
            clamp_face_diameter,
            cone_half_angle_deg,
            material_lookup,
        )

        compliance = top_compliance + bottom_compliance
        km_frusta = 1.0 / compliance

        homogeneous_material = p.get("eq_8_23_material")
        km_eq_8_23 = None
        eq_8_23_lookup = None
        if homogeneous_material:
            row = find_material_stiffness_row(str(homogeneous_material))
            E_eq = float(material_overrides.get(str(homogeneous_material), row["E_psi"]))
            A = float(row["A"])
            B = float(row["B"])
            km_eq_8_23 = E_eq * d * A * math_exp_safe(B * d / total_grip)
            eq_8_23_lookup = {
                "material": homogeneous_material,
                "E_psi": E_eq,
                "A": A,
                "B": B,
            }

        LT = 2.0 * d + (0.25 if bolt_length <= 6.0 else 0.5)
        ld_unthreaded_in_grip = min(max(bolt_length - LT, 0.0), total_grip)
        lt_threaded_in_grip = total_grip - ld_unthreaded_in_grip
        kb = Ad * At * E_bolt / (Ad * lt_threaded_in_grip + At * ld_unthreaded_in_grip)

        derived = {
            "thread_pitch_in": pitch,
            "nominal_area_Ad_in2": Ad,
            "grip_length_in": total_grip,
            "estimated_threaded_length_LT_in": LT,
            "unthreaded_length_in_grip_ld_in": ld_unthreaded_in_grip,
            "threaded_length_in_grip_lt_in": lt_threaded_in_grip,
            "clamp_face_diameter_in_used": clamp_face_diameter,
            "top_half_segments_raw": top_segments_raw,
            "bottom_half_segments_raw": bottom_segments_raw,
            "top_half_segments": top_segments,
            "bottom_half_segments": bottom_segments,
        }
        lookups: Dict[str, Any] = {
            "table_8_2": thread_row,
            "table_8_8": material_lookup,
            "frusta_segments": top_results + bottom_results,
        }
        if washer_lookup is not None:
            lookups["table_a_32"] = washer_lookup
        if eq_8_23_lookup is not None:
            lookups["eq_8_23_material"] = eq_8_23_lookup

        outputs = {
            "member_stiffness_frusta_lbf_per_in": km_frusta,
            "member_stiffness_frusta_Mlbf_per_in": km_frusta / 1e6,
            "bolt_stiffness_lbf_per_in": kb,
            "bolt_stiffness_Mlbf_per_in": kb / 1e6,
            "stiffness_ratio_C_bolt_over_joint": kb / (kb + km_frusta),
        }
        if km_eq_8_23 is not None:
            outputs["member_stiffness_eq_8_23_lbf_per_in"] = km_eq_8_23
            outputs["member_stiffness_eq_8_23_Mlbf_per_in"] = km_eq_8_23 / 1e6
            outputs["eq_8_23_to_frusta_ratio"] = km_eq_8_23 / km_frusta
            outputs["eq_8_23_percent_difference_from_frusta"] = 100.0 * (km_eq_8_23 - km_frusta) / km_frusta

        notes = [
            "The frusta route treats the compressed member as conical segments in series from each clamp face to the joint midplane.",
            "Consecutive same-material half-segments are merged before stiffness evaluation so the reported frusta match the textbook Example 8-2 grouping.",
            "If clamp_face_diameter_in is omitted, the solver fetches the washer OD from table_a_32.csv.",
            "Bolt stiffness follows Shigley Eq. (8-17) using the tensile-stress area from table_8_2.csv.",
            "Eq. (8-23) is only evaluated when eq_8_23_material is explicitly provided, since it is intended for a single effective member material.",
        ]
        return SolveResult(self.problem, self.title, p, derived, lookups, outputs, notes)


class BoltStrengthSolver(BaseSolver):
    solve_path = "bolt_strength"

    def solve(self) -> SolveResult:
        p = self.inputs
        nominal_diameter_in = float(p["nominal_diameter_in"])
        threads_per_inch = int(p["threads_per_inch"])
        thread_series = str(p.get("thread_series", "UNF")).upper()
        bolt_length_in = float(p["bolt_length_in"])
        sae_grade = p["sae_grade"]
        external_load_kip = float(p["external_load_kip"])
        initial_bolt_tension_kip = float(p["initial_bolt_tension_kip"])
        kb_Mlbf_per_in = float(p["bolt_stiffness_Mlbf_per_in"])
        km_Mlbf_per_in = float(p["member_stiffness_Mlbf_per_in"])
        torque_factor_K = float(p.get("torque_factor_K", 0.2))
        thread_friction = float(p.get("thread_friction", 0.15))
        collar_friction = float(p.get("collar_friction", thread_friction))
        half_thread_angle_deg = float(p.get("half_thread_angle_deg", 30.0))

        for name, value in [
            ("nominal_diameter_in", nominal_diameter_in),
            ("threads_per_inch", threads_per_inch),
            ("bolt_length_in", bolt_length_in),
            ("external_load_kip", external_load_kip),
            ("initial_bolt_tension_kip", initial_bolt_tension_kip),
            ("bolt_stiffness_Mlbf_per_in", kb_Mlbf_per_in),
            ("member_stiffness_Mlbf_per_in", km_Mlbf_per_in),
            ("torque_factor_K", torque_factor_K),
        ]:
            validate_positive(name, value)
        for name, value in [
            ("thread_friction", thread_friction),
            ("collar_friction", collar_friction),
            ("half_thread_angle_deg", half_thread_angle_deg),
        ]:
            validate_nonnegative(name, value)

        thread_row = find_thread_row(nominal_diameter_in, thread_series, threads_per_inch=threads_per_inch)
        proof_row = find_proof_strength_row(sae_grade, nominal_diameter_in)

        At_in2 = float(thread_row["tensile_stress_area_in2"])
        Ar_in2 = float(thread_row.get("minor_diameter_area_in2"))
        dr_in = math.sqrt(4.0 * Ar_in2 / math.pi)
        dm_in = 0.5 * (nominal_diameter_in + dr_in)
        lead_in = 1.0 / threads_per_inch
        lead_angle_rad = math.atan(lead_in / (math.pi * dm_in))

        kb_lbf_per_in = kb_Mlbf_per_in * 1_000_000.0
        km_lbf_per_in = km_Mlbf_per_in * 1_000_000.0
        C = kb_lbf_per_in / (kb_lbf_per_in + km_lbf_per_in)

        preload_stress_kpsi = initial_bolt_tension_kip / At_in2
        bolt_load_due_to_service_kip = C * external_load_kip
        service_bolt_load_kip = initial_bolt_tension_kip + bolt_load_due_to_service_kip
        service_stress_kpsi = service_bolt_load_kip / At_in2
        member_load_due_to_service_kip = (1.0 - C) * external_load_kip
        resultant_member_load_kip = member_load_due_to_service_kip - initial_bolt_tension_kip

        Sp_kpsi = float(proof_row["minimum_proof_strength_kpsi"])
        preload_margin_to_proof_kpsi = Sp_kpsi - preload_stress_kpsi
        service_margin_to_proof_kpsi = Sp_kpsi - service_stress_kpsi
        preload_margin_percent_of_proof = 100.0 * preload_margin_to_proof_kpsi / Sp_kpsi
        service_margin_percent_of_proof = 100.0 * service_margin_to_proof_kpsi / Sp_kpsi

        proof_load_kip = Sp_kpsi * At_in2
        yielding_factor_of_safety_np = proof_load_kip / service_bolt_load_kip
        load_factor_nL = (proof_load_kip - initial_bolt_tension_kip) / (C * external_load_kip)
        separation_load_kip = initial_bolt_tension_kip / (1.0 - C)
        separation_safety_factor = separation_load_kip / external_load_kip

        torque_eq_8_27_lbf_in = torque_factor_K * initial_bolt_tension_kip * 1000.0 * nominal_diameter_in
        sec_alpha = 1.0 / math.cos(math.radians(half_thread_angle_deg))
        tan_lambda = math.tan(lead_angle_rad)
        torque_coefficient_eq_8_26 = (
            (dm_in / (2.0 * nominal_diameter_in))
            * ((tan_lambda + thread_friction * sec_alpha) / (1.0 - thread_friction * tan_lambda * sec_alpha))
            + 0.625 * collar_friction
        )
        torque_eq_8_26_lbf_in = torque_coefficient_eq_8_26 * initial_bolt_tension_kip * 1000.0 * nominal_diameter_in
        torque_difference_percent_vs_eq_8_27 = 100.0 * (torque_eq_8_26_lbf_in - torque_eq_8_27_lbf_in) / torque_eq_8_27_lbf_in

        derived = {
            "tensile_stress_area_At_in2": At_in2,
            "minor_diameter_area_Ar_in2": Ar_in2,
            "minor_diameter_dr_in": dr_in,
            "mean_thread_diameter_dm_in": dm_in,
            "lead_in": lead_in,
            "lead_angle_deg": math.degrees(lead_angle_rad),
            "stiffness_ratio_C_bolt_over_joint": C,
            "bolt_load_due_to_service_kip": bolt_load_due_to_service_kip,
            "member_load_due_to_service_kip": member_load_due_to_service_kip,
            "proof_load_kip": proof_load_kip,
            "separation_load_kip": separation_load_kip,
            "torque_coefficient_eq_8_26": torque_coefficient_eq_8_26,
        }
        lookups = {
            "table_8_2": thread_row,
            "table_8_9": proof_row,
        }
        outputs = {
            "preload_stress_kpsi": preload_stress_kpsi,
            "service_stress_kpsi": service_stress_kpsi,
            "proof_strength_kpsi": Sp_kpsi,
            "preload_margin_to_proof_kpsi": preload_margin_to_proof_kpsi,
            "service_margin_to_proof_kpsi": service_margin_to_proof_kpsi,
            "preload_margin_to_proof_percent": preload_margin_percent_of_proof,
            "service_margin_to_proof_percent": service_margin_percent_of_proof,
            "resultant_bolt_load_kip": service_bolt_load_kip,
            "resultant_member_load_kip": resultant_member_load_kip,
            "joint_remains_clamped": resultant_member_load_kip < 0.0,
            "yielding_factor_of_safety_np": yielding_factor_of_safety_np,
            "load_factor_nL": load_factor_nL,
            "separation_safety_factor": separation_safety_factor,
            "torque_eq_8_27_lbf_in": torque_eq_8_27_lbf_in,
            "torque_eq_8_27_lbf_ft": torque_eq_8_27_lbf_in / 12.0,
            "torque_eq_8_26_lbf_in": torque_eq_8_26_lbf_in,
            "torque_eq_8_26_lbf_ft": torque_eq_8_26_lbf_in / 12.0,
            "torque_eq_8_26_percent_difference_vs_eq_8_27": torque_difference_percent_vs_eq_8_27,
        }
        notes = [
            "This solve path follows Shigley Example 8-3 for a preloaded tension joint and keeps the pre-existing solve paths unchanged.",
            "The preload and service stresses are computed with the tensile-stress area At from table_8_2.csv.",
            "The service bolt load uses Eq. (8-24): Fb = CP + Fi, with C = kb / (kb + km).",
            "The proof-strength comparison uses the SAE grade row from table_8_9.csv matched by nominal diameter range.",
            "Eq. (8-27) uses T = K F_i d. Eq. (8-26) uses the thread/friction model with dm based on the average of the major and minor diameters.",
            "The yielding factor of safety and load factor are additionally reported from Eqs. (8-28) and (8-29) on the following page because they are natural extensions of the same example family.",
        ]
        return SolveResult(self.problem, self.title, p, derived, lookups, outputs, notes)


class StaticallyLoadedTensionJointWithPreloadSolver(BaseSolver):
    solve_path = "statically_loaded_tension_joint_with_preload"

    def solve(self) -> SolveResult:
        p = self.inputs
        nominal_diameter_in = float(p["nominal_diameter_in"])
        threads_per_inch = int(p["threads_per_inch"])
        thread_series = str(p.get("thread_series", "UNC")).upper()
        sae_grade = p["sae_grade"]
        grip_length_in = float(p["grip_length_in"])
        total_separating_force_kip = float(p["total_separating_force_kip"])
        desired_load_factor_nL = float(p["desired_load_factor_nL"])
        bolts_reused = bool(p.get("bolts_reused", True))
        extra_threads_beyond_nut = float(p.get("extra_threads_beyond_nut", 2.0))
        bolt_modulus_material = str(p.get("bolt_modulus_material", "Steel"))
        member_material_astm_number = p["member_material_astm_number"]
        member_modulus_Mpsi_override = p.get("member_modulus_Mpsi_override")
        eq_8_23_material = p.get("eq_8_23_material")
        if eq_8_23_material in (None, ""):
            eq_8_23_material = "Gray Cast Iron"
        eq_8_23_material = str(eq_8_23_material)
        use_eq_8_22_for_design = bool(p.get("use_eq_8_22_for_design", True))

        for name, value in [
            ("nominal_diameter_in", nominal_diameter_in),
            ("threads_per_inch", threads_per_inch),
            ("grip_length_in", grip_length_in),
            ("total_separating_force_kip", total_separating_force_kip),
            ("desired_load_factor_nL", desired_load_factor_nL),
            ("extra_threads_beyond_nut", extra_threads_beyond_nut),
        ]:
            validate_positive(name, value)

        thread_row = find_thread_row(nominal_diameter_in, thread_series, threads_per_inch=threads_per_inch)
        proof_row = find_proof_strength_row(sae_grade, nominal_diameter_in)
        nut_row = find_nut_dimensions_row(nominal_diameter_in)
        preferred_length_row = find_preferred_fraction_size_ge(
            float(nut_row["height_regular_hex_value"]) + grip_length_in + extra_threads_beyond_nut / threads_per_inch
        )
        bolt_material_row = find_material_stiffness_row(bolt_modulus_material)
        eq_8_23_row = find_material_stiffness_row(eq_8_23_material)
        cast_iron_row = find_gray_cast_iron_row(member_material_astm_number)

        nut_thickness_in = float(nut_row["height_regular_hex_value"])
        extra_thread_allowance_in = extra_threads_beyond_nut / threads_per_inch
        minimum_required_bolt_length_in = nut_thickness_in + grip_length_in + extra_thread_allowance_in
        selected_bolt_length_in = float(preferred_length_row["value_in"])

        At_in2 = float(thread_row["tensile_stress_area_in2"])
        Ad_in2 = math.pi * nominal_diameter_in**2 / 4.0

        LT_in = 2.0 * nominal_diameter_in + (0.25 if selected_bolt_length_in <= 6.0 else 0.5)
        ld_in = min(max(selected_bolt_length_in - LT_in, 0.0), grip_length_in)
        lt_in = grip_length_in - ld_in

        E_bolt_Mpsi = float(bolt_material_row["E_psi"]) / 1e6
        kb_Mlbf_per_in = Ad_in2 * At_in2 * E_bolt_Mpsi / (Ad_in2 * lt_in + At_in2 * ld_in)

        if member_modulus_Mpsi_override is not None:
            E_member_Mpsi = float(member_modulus_Mpsi_override)
        else:
            E_member_Mpsi = float(cast_iron_row["modulus_of_elasticity_tension_max_Mpsi"])

        num_eq_8_22 = 0.5774 * math.pi * E_member_Mpsi * nominal_diameter_in
        den_eq_8_22 = 2.0 * math.log(
            5.0 * (0.5774 * grip_length_in + 0.5 * nominal_diameter_in)
            / (0.5774 * grip_length_in + 2.5 * nominal_diameter_in)
        )
        km_eq_8_22_Mlbf_per_in = num_eq_8_22 / den_eq_8_22

        A = float(eq_8_23_row["A"])
        B = float(eq_8_23_row["B"])
        km_eq_8_23_Mlbf_per_in = E_member_Mpsi * nominal_diameter_in * A * math_exp_safe(B * nominal_diameter_in / grip_length_in)

        km_design_Mlbf_per_in = km_eq_8_22_Mlbf_per_in if use_eq_8_22_for_design else km_eq_8_23_Mlbf_per_in
        C = kb_Mlbf_per_in / (kb_Mlbf_per_in + km_design_Mlbf_per_in)

        Sp_kpsi = float(proof_row["minimum_proof_strength_kpsi"])
        proof_load_kip = Sp_kpsi * At_in2
        preload_fraction = 0.75 if bolts_reused else 0.90
        Fi_kip = preload_fraction * proof_load_kip

        required_bolt_count_real = C * desired_load_factor_nL * total_separating_force_kip / (proof_load_kip - Fi_kip)
        required_bolt_count = math.ceil(required_bolt_count_real)
        force_per_bolt_kip = total_separating_force_kip / required_bolt_count

        realized_load_factor_nL = (proof_load_kip - Fi_kip) / (C * force_per_bolt_kip)
        yielding_factor_of_safety_np = proof_load_kip / (C * force_per_bolt_kip + Fi_kip)
        separation_load_factor_n0 = Fi_kip / (force_per_bolt_kip * (1.0 - C))

        derived = {
            "nut_thickness_in": nut_thickness_in,
            "extra_thread_allowance_in": extra_thread_allowance_in,
            "minimum_required_bolt_length_in": minimum_required_bolt_length_in,
            "selected_bolt_length_in": selected_bolt_length_in,
            "selected_bolt_length_label": preferred_length_row["label"],
            "estimated_thread_length_LT_in": LT_in,
            "unthreaded_length_in_grip_ld_in": ld_in,
            "threaded_length_in_grip_lt_in": lt_in,
            "tensile_stress_area_At_in2": At_in2,
            "major_diameter_area_Ad_in2": Ad_in2,
            "bolt_modulus_Mpsi": E_bolt_Mpsi,
            "member_modulus_Mpsi_used": E_member_Mpsi,
            "proof_load_per_bolt_kip": proof_load_kip,
            "recommended_preload_per_bolt_kip": Fi_kip,
            "required_bolt_count_real": required_bolt_count_real,
            "force_per_bolt_with_selected_N_kip": force_per_bolt_kip,
        }
        lookups = {
            "table_8_2": thread_row,
            "table_8_9": proof_row,
            "table_a_17_selected_length": preferred_length_row,
            "table_a_31": nut_row,
            "table_a_24_gray_cast_iron": cast_iron_row,
            "table_8_8_bolt_material": bolt_material_row,
            "table_8_8_eq_8_23_material": eq_8_23_row,
        }
        outputs = {
            "bolt_stiffness_kb_Mlbf_per_in": kb_Mlbf_per_in,
            "member_stiffness_km_eq_8_22_Mlbf_per_in": km_eq_8_22_Mlbf_per_in,
            "member_stiffness_km_eq_8_23_Mlbf_per_in": km_eq_8_23_Mlbf_per_in,
            "stiffness_constant_C": C,
            "recommended_preload_fraction_of_proof": preload_fraction,
            "recommended_preload_per_bolt_kip": Fi_kip,
            "required_number_of_bolts": required_bolt_count,
            "realized_load_factor_nL": realized_load_factor_nL,
            "yielding_factor_of_safety_np": yielding_factor_of_safety_np,
            "joint_separation_load_factor_n0": separation_load_factor_n0,
        }
        notes = [
            "This solve path follows Shigley Example 8-4 additively and leaves the existing solve paths intact.",
            "The minimum bolt length is computed from grip length + regular-hex nut thickness from table_a_31.csv + the specified extra exposed threads.",
            "The selected bolt length is the next preferred fractional inch size from table_a_17.csv.",
            "Bolt stiffness uses Shigley Eq. (8-17) with At from table_8_2.csv and E from table_8_8.csv.",
            "Member stiffness is reported by both Eq. (8-22) and Eq. (8-23). The design value of C uses the route selected by use_eq_8_22_for_design.",
            "If eq_8_23_material is omitted, the solver defaults the Eq. (8-23) comparison material to the member side for this example family: Gray Cast Iron.",
            "The preload recommendation follows Eq. (8-31): 0.75 Fp for reused nonpermanent fasteners, or 0.90 Fp otherwise.",
            "The number of bolts is obtained from the overload load-factor relation rearranged from Eq. (8-29), then rounded up to the next integer.",
        ]
        return SolveResult(self.problem, self.title, p, derived, lookups, outputs, notes)
