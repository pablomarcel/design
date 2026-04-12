from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Tuple

try:
    from .app import ScrewsFastenersApp
    from .utils import try_render_key_value_table
except ImportError:  # pragma: no cover
    from app import ScrewsFastenersApp
    from utils import try_render_key_value_table


RowList = List[Tuple[str, Any]]


def _print_summary(result: Dict[str, Any]) -> None:
    outputs = result.get("outputs", {})
    derived = result.get("derived", {})
    problem = result.get("problem", "result")
    title = result.get("title", problem)
    rows: RowList = []

    if problem == "square_thread_power_screw":
        principal = outputs.get("principal_stresses_root_MPa", {})
        rows = [
            ("Pitch diameter (mm)", derived.get("pitch_diameter_mm")),
            ("Minor diameter (mm)", derived.get("minor_diameter_mm")),
            ("Lead (mm)", derived.get("lead_mm")),
            ("Raise torque (N·m)", outputs.get("total_torque_raise_N_m")),
            ("Lower torque (N·m)", outputs.get("total_torque_lower_N_m")),
            ("Efficiency (%)", outputs.get("raising_efficiency_percent")),
            ("Principal stress σ1 (MPa)", principal.get("sigma_1")),
            ("Principal stress σ2 (MPa)", principal.get("sigma_2")),
            ("Principal stress σ3 (MPa)", principal.get("sigma_3")),
            ("Von Mises root stress (MPa)", outputs.get("von_mises_stress_root_MPa")),
            ("Max shear root stress (MPa)", outputs.get("maximum_shear_stress_root_MPa")),
            ("Self-locking on threads", outputs.get("self_locking_on_threads")),
        ]
    elif problem == "fastener_member_stiffness":
        rows = [
            ("Grip length (in)", derived.get("grip_length_in")),
            ("Clamp face diameter used (in)", derived.get("clamp_face_diameter_in_used")),
            ("Member stiffness, frusta (Mlbf/in)", outputs.get("member_stiffness_frusta_Mlbf_per_in")),
            ("Member stiffness, Eq. 8-23 (Mlbf/in)", outputs.get("member_stiffness_eq_8_23_Mlbf_per_in")),
            ("Bolt stiffness (Mlbf/in)", outputs.get("bolt_stiffness_Mlbf_per_in")),
            ("Joint constant C", outputs.get("stiffness_ratio_C_bolt_over_joint")),
        ]
    elif problem == "bolt_strength":
        rows = [
            ("Tensile-stress area At (in^2)", derived.get("tensile_stress_area_At_in2")),
            ("Joint constant C", derived.get("stiffness_ratio_C_bolt_over_joint")),
            ("Preload stress (kpsi)", outputs.get("preload_stress_kpsi")),
            ("Service stress (kpsi)", outputs.get("service_stress_kpsi")),
            ("Proof strength (kpsi)", outputs.get("proof_strength_kpsi")),
            ("Yielding factor of safety np", outputs.get("yielding_factor_of_safety_np")),
            ("Load factor nL", outputs.get("load_factor_nL")),
            ("Separation safety factor", outputs.get("separation_safety_factor")),
            ("Torque, Eq. 8-27 (lbf·in)", outputs.get("torque_eq_8_27_lbf_in")),
            ("Torque, Eq. 8-26 (lbf·in)", outputs.get("torque_eq_8_26_lbf_in")),
            ("Joint remains clamped", outputs.get("joint_remains_clamped")),
        ]
    elif problem == "statically_loaded_tension_joint_with_preload":
        rows = [
            ("Selected bolt length (in)", derived.get("selected_bolt_length_in")),
            ("Selected bolt length label", derived.get("selected_bolt_length_label")),
            ("Bolt stiffness kb (Mlbf/in)", outputs.get("bolt_stiffness_kb_Mlbf_per_in")),
            ("Member stiffness km, Eq. 8-22 (Mlbf/in)", outputs.get("member_stiffness_km_eq_8_22_Mlbf_per_in")),
            ("Member stiffness km, Eq. 8-23 (Mlbf/in)", outputs.get("member_stiffness_km_eq_8_23_Mlbf_per_in")),
            ("Joint constant C", outputs.get("stiffness_constant_C")),
            ("Required number of bolts", outputs.get("required_number_of_bolts")),
            ("Realized load factor nL", outputs.get("realized_load_factor_nL")),
            ("Yielding factor of safety np", outputs.get("yielding_factor_of_safety_np")),
            ("Joint separation load factor n0", outputs.get("joint_separation_load_factor_n0")),
        ]
    elif problem == "fatigue_loading_tension_joint":
        rows = [
            ("Bolt stiffness kb (Mlbf/in)", outputs.get("bolt_stiffness_kb_Mlbf_per_in")),
            ("Member stiffness km (Mlbf/in)", outputs.get("member_stiffness_km_Mlbf_per_in")),
            ("Joint constant C", outputs.get("joint_constant_C")),
            ("Yielding factor of safety np", outputs.get("traditional_yielding_factor_of_safety_np")),
            ("Load factor nL", outputs.get("load_factor_nL")),
            ("Separation factor n0", outputs.get("joint_separation_factor_n0")),
            ("Fatigue FoS Goodman", outputs.get("fatigue_factor_of_safety_goodman")),
            ("Fatigue FoS Gerber", outputs.get("fatigue_factor_of_safety_gerber")),
            ("Fatigue FoS ASME-elliptic", outputs.get("fatigue_factor_of_safety_asme_elliptic")),
            ("Selected fatigue FoS", outputs.get("selected_fatigue_factor_of_safety")),
        ]

    if rows:
        try_render_key_value_table(title, rows)
    else:
        print(json.dumps(result, indent=2))


def _build_power_screw_payload(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "problem": "square_thread_power_screw",
        "title": args.title or "Square-thread power screw analysis",
        "inputs": {
            "solve_path": "square_thread_power_screw",
            "major_diameter_mm": args.major_diameter_mm,
            "pitch_mm": args.pitch_mm,
            "starts": args.starts,
            "friction_thread": args.friction_thread,
            "friction_collar": args.friction_collar,
            "collar_mean_diameter_mm": args.collar_mean_diameter_mm,
            "axial_load_N": args.axial_load_N,
            "engaged_threads": args.engaged_threads,
            "first_thread_load_fraction": args.first_thread_load_fraction,
        },
    }


def _parse_layers(raw_items: list[str]) -> list[Dict[str, Any]]:
    layers = []
    for item in raw_items:
        material, thickness = item.split(":", 1)
        layers.append({"material": material.strip(), "thickness_in": float(thickness)})
    return layers


def _build_fastener_payload(args: argparse.Namespace) -> Dict[str, Any]:
    payload = {
        "problem": "fastener_member_stiffness",
        "title": args.title or "Fastener/member stiffness analysis",
        "inputs": {
            "solve_path": "fastener_member_stiffness",
            "nominal_diameter_in": args.nominal_diameter_in,
            "threads_per_inch": args.threads_per_inch,
            "thread_series": args.thread_series,
            "bolt_length_in": args.bolt_length_in,
            "bolt_modulus_psi": args.bolt_modulus_psi,
            "washer_type": args.washer_type,
            "cone_half_angle_deg": args.cone_half_angle_deg,
            "layers": _parse_layers(args.layer),
        },
    }
    if args.clamp_face_diameter_in is not None:
        payload["inputs"]["clamp_face_diameter_in"] = args.clamp_face_diameter_in
    if args.eq_8_23_material is not None:
        payload["inputs"]["eq_8_23_material"] = args.eq_8_23_material
    return payload


def _build_bolt_strength_payload(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "problem": "bolt_strength",
        "title": args.title or "Bolt strength analysis",
        "inputs": {
            "solve_path": "bolt_strength",
            "nominal_diameter_in": args.nominal_diameter_in,
            "threads_per_inch": args.threads_per_inch,
            "thread_series": args.thread_series,
            "bolt_length_in": args.bolt_length_in,
            "sae_grade": args.sae_grade,
            "external_load_kip": args.external_load_kip,
            "initial_bolt_tension_kip": args.initial_bolt_tension_kip,
            "bolt_stiffness_Mlbf_per_in": args.bolt_stiffness_Mlbf_per_in,
            "member_stiffness_Mlbf_per_in": args.member_stiffness_Mlbf_per_in,
            "torque_factor_K": args.torque_factor_K,
            "thread_friction": args.thread_friction,
            "collar_friction": args.collar_friction,
            "half_thread_angle_deg": args.half_thread_angle_deg,
        },
    }


def _build_tension_joint_preload_payload(args: argparse.Namespace) -> Dict[str, Any]:
    payload = {
        "problem": "statically_loaded_tension_joint_with_preload",
        "title": args.title or "Statically loaded tension joint with preload",
        "inputs": {
            "solve_path": "statically_loaded_tension_joint_with_preload",
            "nominal_diameter_in": args.nominal_diameter_in,
            "threads_per_inch": args.threads_per_inch,
            "thread_series": args.thread_series,
            "sae_grade": args.sae_grade,
            "grip_length_in": args.grip_length_in,
            "total_separating_force_kip": args.total_separating_force_kip,
            "desired_load_factor_nL": args.desired_load_factor_nL,
            "bolts_reused": args.bolts_reused,
            "extra_threads_beyond_nut": args.extra_threads_beyond_nut,
            "bolt_modulus_material": args.bolt_modulus_material,
            "member_material_astm_number": args.member_material_astm_number,
            "use_eq_8_22_for_design": not args.use_eq_8_23_for_design,
        },
    }
    if args.member_modulus_Mpsi_override is not None:
        payload["inputs"]["member_modulus_Mpsi_override"] = args.member_modulus_Mpsi_override
    if args.eq_8_23_material is not None:
        payload["inputs"]["eq_8_23_material"] = args.eq_8_23_material
    return payload



def _build_fatigue_tension_joint_payload(args: argparse.Namespace) -> Dict[str, Any]:
    payload = {
        "problem": "fatigue_loading_tension_joint",
        "title": args.title or "Fatigue loading of tension joints",
        "inputs": {
            "solve_path": "fatigue_loading_tension_joint",
            "nominal_diameter_in": args.nominal_diameter_in,
            "threads_per_inch": args.threads_per_inch,
            "thread_series": args.thread_series,
            "sae_grade": args.sae_grade,
            "washer_thickness_in": args.washer_thickness_in,
            "steel_cover_thickness_in": args.steel_cover_thickness_in,
            "steel_modulus_Mpsi": args.steel_modulus_Mpsi,
            "cast_iron_base_thickness_in": args.cast_iron_base_thickness_in,
            "cast_iron_modulus_Mpsi": args.cast_iron_modulus_Mpsi,
            "max_force_per_screw_kip": args.max_force_per_screw_kip,
            "min_force_per_screw_kip": args.min_force_per_screw_kip,
            "preload_fraction_of_proof": args.preload_fraction_of_proof,
            "effective_washer_diameter_factor": args.effective_washer_diameter_factor,
            "cone_half_angle_deg": args.cone_half_angle_deg,
            "threaded_all_the_way": not args.not_threaded_all_the_way,
            "fatigue_criterion": args.fatigue_criterion,
        },
    }
    if args.endurance_grade_override is not None:
        payload["inputs"]["endurance_grade_override"] = args.endurance_grade_override
    return payload

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shigley Chapter 8 screws and fasteners CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Solve from an input JSON file in ./in or by absolute path")
    run_p.add_argument("--infile", required=True)
    run_p.add_argument("--outfile", required=False)
    run_p.add_argument("--pretty", action="store_true", help="Write indented JSON")
    run_p.add_argument("--show", action="store_true", help="Print a CLI summary table")

    ps = sub.add_parser("power_screw", help="Direct square-thread power screw calculation")
    ps.add_argument("--title")
    ps.add_argument("--major-diameter-mm", type=float, required=True)
    ps.add_argument("--pitch-mm", type=float, required=True)
    ps.add_argument("--starts", type=int, default=1)
    ps.add_argument("--friction-thread", type=float, required=True)
    ps.add_argument("--friction-collar", type=float, required=True)
    ps.add_argument("--collar-mean-diameter-mm", type=float, required=True)
    ps.add_argument("--axial-load-N", type=float, required=True)
    ps.add_argument("--engaged-threads", type=float, default=1.0)
    ps.add_argument("--first-thread-load-fraction", type=float, default=0.38)
    ps.add_argument("--outfile")
    ps.add_argument("--pretty", action="store_true")
    ps.add_argument("--show", action="store_true")

    fm = sub.add_parser("fastener_stiffness", help="Direct fastener/member stiffness calculation")
    fm.add_argument("--title")
    fm.add_argument("--nominal-diameter-in", type=float, required=True)
    fm.add_argument("--threads-per-inch", type=int, required=True)
    fm.add_argument("--thread-series", default="UNF")
    fm.add_argument("--bolt-length-in", type=float, required=True)
    fm.add_argument("--bolt-modulus-psi", type=float, default=30_000_000.0)
    fm.add_argument("--washer-type", default="N")
    fm.add_argument("--clamp-face-diameter-in", type=float)
    fm.add_argument("--cone-half-angle-deg", type=float, default=30.0)
    fm.add_argument(
        "--layer",
        action="append",
        required=True,
        help="Member layer as material:thickness_in, in top-to-bottom order. Repeat the flag for each layer.",
    )
    fm.add_argument("--eq-8-23-material")
    fm.add_argument("--outfile")
    fm.add_argument("--pretty", action="store_true")
    fm.add_argument("--show", action="store_true")

    bs = sub.add_parser("bolt_strength", help="Direct preloaded-bolt strength calculation")
    bs.add_argument("--title")
    bs.add_argument("--nominal-diameter-in", type=float, required=True)
    bs.add_argument("--threads-per-inch", type=int, required=True)
    bs.add_argument("--thread-series", default="UNF")
    bs.add_argument("--bolt-length-in", type=float, required=True)
    bs.add_argument("--sae-grade", required=True)
    bs.add_argument("--external-load-kip", type=float, required=True)
    bs.add_argument("--initial-bolt-tension-kip", type=float, required=True)
    bs.add_argument("--bolt-stiffness-Mlbf-per-in", type=float, required=True)
    bs.add_argument("--member-stiffness-Mlbf-per-in", type=float, required=True)
    bs.add_argument("--torque-factor-K", type=float, default=0.2)
    bs.add_argument("--thread-friction", type=float, default=0.15)
    bs.add_argument("--collar-friction", type=float, default=0.15)
    bs.add_argument("--half-thread-angle-deg", type=float, default=30.0)
    bs.add_argument("--outfile")
    bs.add_argument("--pretty", action="store_true")
    bs.add_argument("--show", action="store_true")

    tj = sub.add_parser("tension_joint_preload", help="Direct statically loaded tension joint with preload calculation")
    tj.add_argument("--title")
    tj.add_argument("--nominal-diameter-in", type=float, required=True)
    tj.add_argument("--threads-per-inch", type=int, required=True)
    tj.add_argument("--thread-series", default="UNC")
    tj.add_argument("--sae-grade", required=True)
    tj.add_argument("--grip-length-in", type=float, required=True)
    tj.add_argument("--total-separating-force-kip", type=float, required=True)
    tj.add_argument("--desired-load-factor-nL", type=float, required=True)
    tj.set_defaults(bolts_reused=True)
    tj.add_argument("--bolts-reused", dest="bolts_reused", action="store_true")
    tj.add_argument("--no-bolts-reused", dest="bolts_reused", action="store_false")
    tj.add_argument("--extra-threads-beyond-nut", type=float, default=2.0)
    tj.add_argument("--bolt-modulus-material", default="Steel")
    tj.add_argument("--member-material-astm-number", required=True)
    tj.add_argument("--member-modulus-Mpsi-override", type=float)
    tj.add_argument("--eq-8-23-material")
    tj.add_argument("--use-eq-8-23-for-design", action="store_true")
    tj.add_argument("--outfile")
    tj.add_argument("--pretty", action="store_true")
    tj.add_argument("--show", action="store_true")


    ft = sub.add_parser("fatigue_tension_joint", help="Direct fatigue loading of tension joints calculation")
    ft.add_argument("--title")
    ft.add_argument("--nominal-diameter-in", type=float, required=True)
    ft.add_argument("--threads-per-inch", type=int, required=True)
    ft.add_argument("--thread-series", default="UNC")
    ft.add_argument("--sae-grade", required=True)
    ft.add_argument("--washer-thickness-in", type=float, required=True)
    ft.add_argument("--steel-cover-thickness-in", type=float, required=True)
    ft.add_argument("--steel-modulus-Mpsi", type=float, required=True)
    ft.add_argument("--cast-iron-base-thickness-in", type=float, required=True)
    ft.add_argument("--cast-iron-modulus-Mpsi", type=float, required=True)
    ft.add_argument("--max-force-per-screw-kip", type=float, required=True)
    ft.add_argument("--min-force-per-screw-kip", type=float, default=0.0)
    ft.add_argument("--preload-fraction-of-proof", type=float, default=0.75)
    ft.add_argument("--effective-washer-diameter-factor", type=float, default=1.5)
    ft.add_argument("--cone-half-angle-deg", type=float, default=30.0)
    ft.add_argument("--endurance-grade-override")
    ft.add_argument("--fatigue-criterion", default="goodman", choices=["goodman", "gerber", "asme_elliptic"])
    ft.add_argument("--not-threaded-all-the-way", action="store_true")
    ft.add_argument("--outfile")
    ft.add_argument("--pretty", action="store_true")
    ft.add_argument("--show", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    app = ScrewsFastenersApp()

    if args.command == "run":
        result = app.solve_file(args.infile, outfile=args.outfile, pretty=args.pretty)
        if args.show:
            _print_summary(result)
        else:
            print(json.dumps(result, indent=2 if args.pretty else None))
        return

    if args.command == "power_screw":
        result = app.solve_payload(_build_power_screw_payload(args), outfile=args.outfile, pretty=args.pretty)
        if args.show:
            _print_summary(result)
        else:
            print(json.dumps(result, indent=2 if args.pretty else None))
        return

    if args.command == "fastener_stiffness":
        result = app.solve_payload(_build_fastener_payload(args), outfile=args.outfile, pretty=args.pretty)
        if args.show:
            _print_summary(result)
        else:
            print(json.dumps(result, indent=2 if args.pretty else None))
        return

    if args.command == "bolt_strength":
        result = app.solve_payload(_build_bolt_strength_payload(args), outfile=args.outfile, pretty=args.pretty)
        if args.show:
            _print_summary(result)
        else:
            print(json.dumps(result, indent=2 if args.pretty else None))
        return


    if args.command == "fatigue_tension_joint":
        result = app.solve_payload(_build_fatigue_tension_joint_payload(args), outfile=args.outfile, pretty=args.pretty)
        if args.show:
            _print_summary(result)
        else:
            print(json.dumps(result, indent=2 if args.pretty else None))
        return

    if args.command == "tension_joint_preload":
        result = app.solve_payload(_build_tension_joint_preload_payload(args), outfile=args.outfile, pretty=args.pretty)
        if args.show:
            _print_summary(result)
        else:
            print(json.dumps(result, indent=2 if args.pretty else None))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
