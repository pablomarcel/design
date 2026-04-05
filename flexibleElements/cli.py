from __future__ import annotations

import argparse
import json
from typing import Any

try:
    from .app import FlexibleElementsApp
except ImportError:  # pragma: no cover
    from app import FlexibleElementsApp


app = FlexibleElementsApp(__file__)



def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2))



def _add_common_output_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--outfile", help="Write JSON result to out/<outfile>.")



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cli",
        description="Flexible mechanical elements solver (Shigley chapter 17 starter app).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Solve a problem from an input JSON file in ./in.")
    p_run.add_argument("--infile", required=True, help="Input JSON file name located in ./in.")
    _add_common_output_arg(p_run)

    p_list = sub.add_parser("list", help="List available solve paths.")

    p_a = sub.add_parser("flat_analysis", help="Analysis of a flat belt via CLI flags.")
    p_a.add_argument("--material", required=True)
    p_a.add_argument("--specification", required=True)
    p_a.add_argument("--belt-width-in", required=True, type=float)
    p_a.add_argument("--driver-pulley-diameter-in", required=True, type=float)
    p_a.add_argument("--driven-pulley-diameter-in", required=True, type=float)
    p_a.add_argument("--center-distance-ft", required=True, type=float)
    p_a.add_argument("--driver-rpm", required=True, type=float)
    p_a.add_argument("--nominal-power-hp", required=True, type=float)
    p_a.add_argument("--service-factor", required=True, type=float)
    p_a.add_argument("--design-factor", type=float, default=1.0)
    p_a.add_argument("--velocity-correction-factor", type=float, default=1.0)
    p_a.add_argument("--required-factor-of-safety", type=float, default=0.0)
    _add_common_output_arg(p_a)

    p_d = sub.add_parser("flat_design", help="Design of a flat belt drive via CLI flags.")
    p_d.add_argument("--material", required=True)
    p_d.add_argument("--specification", required=True)
    p_d.add_argument("--small-pulley-diameter-in", required=True, type=float)
    p_d.add_argument("--large-pulley-diameter-in", required=True, type=float)
    p_d.add_argument("--center-distance-ft", required=True, type=float)
    p_d.add_argument("--small-pulley-rpm", required=True, type=float)
    p_d.add_argument("--nominal-power-hp", required=True, type=float)
    p_d.add_argument("--service-factor", required=True, type=float)
    p_d.add_argument("--design-factor", required=True, type=float)
    p_d.add_argument("--velocity-correction-factor", type=float, default=1.0)
    p_d.add_argument("--initial-tension-maintenance", default="catenary")
    p_d.add_argument(
        "--available-widths-in",
        nargs="*",
        type=float,
        help="Optional explicit stock widths in inches. If omitted, flat_belt_a_3.csv is used.",
    )
    _add_common_output_arg(p_d)

    p_m = sub.add_parser("metal_flat_selection", help="Selection of a flat metal belt via CLI flags.")
    p_m.add_argument("--alloy", required=True)
    p_m.add_argument("--thickness-in", required=True, type=float)
    p_m.add_argument("--pulley-diameter-in", required=True, type=float)
    p_m.add_argument("--friction-coefficient", required=True, type=float)
    p_m.add_argument("--torque-lbf-in", required=True, type=float)
    p_m.add_argument("--required-belt-passes", required=True, type=float)
    p_m.add_argument("--available-widths-in", nargs="+", required=True, type=float)
    p_m.add_argument("--contact-angle-rad", type=float)
    _add_common_output_arg(p_m)

    return parser



def _namespace_to_payload(ns: argparse.Namespace) -> dict[str, Any]:
    d = vars(ns).copy()
    d.pop("command", None)
    d.pop("outfile", None)
    return {
        k.replace("_", "-"): v for k, v in d.items()
    }



def _payload_from_args(ns: argparse.Namespace) -> dict[str, Any]:
    if ns.command == "flat_analysis":
        return {
            "solve_path": "flat_analysis",
            "material": ns.material,
            "specification": ns.specification,
            "belt_width_in": ns.belt_width_in,
            "driver_pulley_diameter_in": ns.driver_pulley_diameter_in,
            "driven_pulley_diameter_in": ns.driven_pulley_diameter_in,
            "center_distance_ft": ns.center_distance_ft,
            "driver_rpm": ns.driver_rpm,
            "nominal_power_hp": ns.nominal_power_hp,
            "service_factor": ns.service_factor,
            "design_factor": ns.design_factor,
            "velocity_correction_factor": ns.velocity_correction_factor,
            "required_factor_of_safety": ns.required_factor_of_safety,
        }
    if ns.command == "flat_design":
        payload = {
            "solve_path": "flat_design",
            "material": ns.material,
            "specification": ns.specification,
            "small_pulley_diameter_in": ns.small_pulley_diameter_in,
            "large_pulley_diameter_in": ns.large_pulley_diameter_in,
            "center_distance_ft": ns.center_distance_ft,
            "small_pulley_rpm": ns.small_pulley_rpm,
            "nominal_power_hp": ns.nominal_power_hp,
            "service_factor": ns.service_factor,
            "design_factor": ns.design_factor,
            "velocity_correction_factor": ns.velocity_correction_factor,
            "initial_tension_maintenance": ns.initial_tension_maintenance,
        }
        if ns.available_widths_in:
            payload["available_widths_in"] = ns.available_widths_in
        return payload
    if ns.command == "metal_flat_selection":
        payload = {
            "solve_path": "metal_flat_selection",
            "alloy": ns.alloy,
            "thickness_in": ns.thickness_in,
            "pulley_diameter_in": ns.pulley_diameter_in,
            "friction_coefficient": ns.friction_coefficient,
            "torque_lbf_in": ns.torque_lbf_in,
            "required_belt_passes": ns.required_belt_passes,
            "available_widths_in": ns.available_widths_in,
        }
        if ns.contact_angle_rad is not None:
            payload["contact_angle_rad"] = ns.contact_angle_rad
        return payload
    raise ValueError(f"Unsupported command: {ns.command}")



def main() -> int:
    parser = build_parser()
    ns = parser.parse_args()

    if ns.command == "list":
        for name in app.api.solve_paths:
            print(name)
        return 0

    if ns.command == "run":
        result, out_path = app.solve_file(ns.infile, ns.outfile)
        _print_json(result)
        if out_path:
            print(f"\nWrote: {out_path}")
        return 0

    payload = _payload_from_args(ns)
    result = app.solve(payload["solve_path"], payload)
    _print_json(result)
    if ns.outfile:
        out_path = app.write_output(result, ns.outfile)
        print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
