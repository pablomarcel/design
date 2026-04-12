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
        result = app.solve_payload(
            _build_power_screw_payload(args),
            outfile=args.outfile,
            pretty=args.pretty,
        )
        if args.show:
            _print_summary(result)
        else:
            print(json.dumps(result, indent=2 if args.pretty else None))
        return

    if args.command == "fastener_stiffness":
        result = app.solve_payload(
            _build_fastener_payload(args),
            outfile=args.outfile,
            pretty=args.pretty,
        )
        if args.show:
            _print_summary(result)
        else:
            print(json.dumps(result, indent=2 if args.pretty else None))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
