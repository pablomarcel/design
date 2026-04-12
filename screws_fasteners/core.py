from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List

try:
    from .utils import (
        ValidationError,
        find_material_stiffness_row,
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
        find_material_stiffness_row,
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
