
from __future__ import annotations

import argparse
import json
from typing import Any

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except Exception:  # pragma: no cover
    Console = None
    Table = None
    Panel = None
    RICH_AVAILABLE = False

try:
    from .app import FlexibleElementsApp
except ImportError:  # pragma: no cover
    from app import FlexibleElementsApp


app = FlexibleElementsApp(__file__)


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2))


def _add_common_output_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--outfile", help="Write JSON result to out/<outfile>.")


def _rich_console() -> Any:
    if not RICH_AVAILABLE:
        return None
    return Console()


def _fmt(value: Any, digits: int = 3) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _render_wire_rope_tables(result: dict[str, Any]) -> None:
    console = _rich_console()
    if console is None:
        return

    derived = result.get("derived", {})
    nf_rows = derived.get("nf_table", [])
    if nf_rows:
        table = Table(title="Wire-rope fatigue factor of safety table", show_lines=False)
        table.add_column("d, in", justify="right")
        strand_cols = [key for key in nf_rows[0].keys() if key.startswith("m_")]
        for key in strand_cols:
            table.add_column(key.replace("_", "="), justify="right")
        for row in nf_rows:
            values = [_fmt(row["rope_diameter_in"], 3)] + [_fmt(row[key], 3) for key in strand_cols]
            table.add_row(*values)
        console.print(table)

    max_rows = derived.get("max_nf_by_supporting_ropes", [])
    if max_rows:
        table = Table(title="Best rope diameter by number of supporting ropes", show_lines=False)
        table.add_column("Supporting ropes", justify="right")
        table.add_column("Max nf", justify="right")
        table.add_column("Best d, in", justify="right")
        for row in max_rows:
            table.add_row(
                str(row["number_of_supporting_ropes"]),
                _fmt(row["max_nf"], 3),
                _fmt(row["best_rope_diameter_in"], 3),
            )
        console.print(table)


def _render_roller_chain_tables(result: dict[str, Any]) -> None:
    console = _rich_console()
    if console is None:
        return

    lookups = result.get("lookups", {})
    rows = lookups.get("table_17_20_decision_table", [])
    if rows:
        table = Table(title="Roller-chain decision table", show_lines=False)
        table.add_column("Strands", justify="right")
        table.add_column("K2", justify="right")
        table.add_column("Hd, hp", justify="right")
        table.add_column("Required Htab, hp", justify="right")
        table.add_column("Chain no.", justify="right")
        table.add_column("Available Htab, hp", justify="right")
        table.add_column("Lube", justify="center")
        table.add_column("Estimated", justify="center")
        for row in rows:
            table.add_row(
                str(row["number_of_strands"]),
                _fmt(row["K2"], 3),
                _fmt(row["Hd_hp"], 3),
                _fmt(row["required_Htab_hp"], 3),
                str(row["chain_number"]),
                _fmt(row["available_Htab_hp"], 3),
                str(row["lubrication_type"]),
                "yes" if row.get("estimated_flag") else "no",
            )
        console.print(table)

    derived = result.get("derived", {})
    summary = Table(title="Selected roller-chain solution", show_lines=False)
    summary.add_column("Quantity")
    summary.add_column("Value", justify="right")
    summary.add_row("Selected strands", str(derived.get("selected_number_of_strands", "")))
    summary.add_row("Selected chain number", str(derived.get("selected_chain_number", "")))
    summary.add_row("Lubrication type", str(derived.get("selected_lubrication_type", "")))
    if "center_distance_in" in derived:
        summary.add_row("Center distance, in", _fmt(derived["center_distance_in"], 3))
    if "selected_chain_length_pitches" in derived:
        summary.add_row("Chain length, pitches", str(derived["selected_chain_length_pitches"]))
    console.print(summary)


def _render_vbelt_tables(result: dict[str, Any]) -> None:
    console = _rich_console()
    if console is None:
        return

    derived = result.get("derived", {})
    summary = Table(title="V-belt analysis summary", show_lines=False)
    summary.add_column("Quantity")
    summary.add_column("Value", justify="right")
    keys = [
        ("belt_speed_ft_min", "Belt speed, ft/min"),
        ("allowable_power_per_belt_hp", "Allowable power per belt, hp"),
        ("design_power_hp", "Design power, hp"),
        ("required_number_of_belts", "Required belts"),
        ("factor_of_safety_nfs_using_specified_belts", "nfs"),
        ("life_in_passes_report", "Life in passes"),
        ("reported_life_hours", "Reported life, h"),
    ]
    for key, label in keys:
        if key in derived:
            summary.add_row(label, _fmt(derived[key], 3) if isinstance(derived[key], float) else str(derived[key]))
    console.print(summary)


def _render_result_tables(result: dict[str, Any]) -> None:
    if not RICH_AVAILABLE:
        return

    problem = result.get("problem", "")
    console = _rich_console()
    title = result.get("title", problem)
    console.print(Panel.fit(title, title="CLI table view"))

    if problem == "wire_rope_fatigue_analysis":
        _render_wire_rope_tables(result)
    elif problem == "roller_chain_selection":
        _render_roller_chain_tables(result)
    elif problem == "v_belt_analysis":
        _render_vbelt_tables(result)


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

    p_v = sub.add_parser("v_belt_analysis", help="Analysis of a V-belt drive via CLI flags.")
    p_v.add_argument("--belt-section", required=True)
    p_v.add_argument("--inside-circumference-in", required=True, type=float)
    p_v.add_argument("--small-sheave-pitch-diameter-in", required=True, type=float)
    p_v.add_argument("--large-sheave-pitch-diameter-in", required=True, type=float)
    p_v.add_argument("--driver-rpm", required=True, type=float)
    p_v.add_argument("--nominal-power-hp", required=True, type=float)
    p_v.add_argument("--service-factor", required=True, type=float)
    p_v.add_argument("--specified-number-of-belts", required=True, type=int)
    p_v.add_argument("--design-factor", type=float, default=1.0)
    p_v.add_argument("--effective-friction-coefficient", type=float, default=0.5123)
    _add_common_output_arg(p_v)

    p_r = sub.add_parser("roller_chain_selection", help="Selection of a roller-chain drive via CLI flags.")
    p_r.add_argument("--nominal-power-hp", required=True, type=float)
    p_r.add_argument("--input-speed-rpm", required=True, type=float)
    p_r.add_argument("--reduction-ratio", required=True, type=float)
    p_r.add_argument("--service-factor", required=True, type=float)
    p_r.add_argument("--design-factor", required=True, type=float)
    p_r.add_argument("--driving-sprocket-teeth", required=True, type=int)
    p_r.add_argument("--driven-sprocket-teeth", required=True, type=int)
    p_r.add_argument("--target-center-distance-over-pitch", required=True, type=float)
    p_r.add_argument("--candidate-number-of-strands", nargs="*", type=int, default=[1, 2, 3, 4])
    _add_common_output_arg(p_r)

    p_w = sub.add_parser("wire_rope_fatigue_analysis", help="Wire-rope fatigue analysis via CLI flags.")
    p_w.add_argument("--bends-to-failure-millions", required=True, type=float)
    p_w.add_argument("--rope-type", required=True)
    p_w.add_argument("--material", required=True)
    p_w.add_argument("--ultimate-strength-kpsi", required=True, type=float)
    p_w.add_argument("--rope-diameters-in", nargs="+", required=True, type=float)
    p_w.add_argument("--suspended-length-ft", required=True, type=float)
    p_w.add_argument("--payload-weight-lbf", required=True, type=float)
    p_w.add_argument("--acceleration-ft-per-s2", required=True, type=float)
    p_w.add_argument("--sheave-diameter-in", required=True, type=float)
    p_w.add_argument("--number-of-supporting-ropes", nargs="*", type=int, default=[1, 2, 3, 4])
    p_w.add_argument("--g-ft-per-s2", type=float, default=32.2)
    _add_common_output_arg(p_w)

    return parser


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
    if ns.command == "v_belt_analysis":
        return {
            "solve_path": "v_belt_analysis",
            "belt_section": ns.belt_section,
            "inside_circumference_in": ns.inside_circumference_in,
            "small_sheave_pitch_diameter_in": ns.small_sheave_pitch_diameter_in,
            "large_sheave_pitch_diameter_in": ns.large_sheave_pitch_diameter_in,
            "driver_rpm": ns.driver_rpm,
            "nominal_power_hp": ns.nominal_power_hp,
            "service_factor": ns.service_factor,
            "specified_number_of_belts": ns.specified_number_of_belts,
            "design_factor": ns.design_factor,
            "effective_friction_coefficient": ns.effective_friction_coefficient,
        }
    if ns.command == "roller_chain_selection":
        return {
            "solve_path": "roller_chain_selection",
            "nominal_power_hp": ns.nominal_power_hp,
            "input_speed_rpm": ns.input_speed_rpm,
            "reduction_ratio": ns.reduction_ratio,
            "service_factor": ns.service_factor,
            "design_factor": ns.design_factor,
            "driving_sprocket_teeth": ns.driving_sprocket_teeth,
            "driven_sprocket_teeth": ns.driven_sprocket_teeth,
            "target_center_distance_over_pitch": ns.target_center_distance_over_pitch,
            "candidate_number_of_strands": ns.candidate_number_of_strands,
        }
    if ns.command == "wire_rope_fatigue_analysis":
        return {
            "solve_path": "wire_rope_fatigue_analysis",
            "bends_to_failure_millions": ns.bends_to_failure_millions,
            "rope_type": ns.rope_type,
            "material": ns.material,
            "ultimate_strength_kpsi": ns.ultimate_strength_kpsi,
            "rope_diameters_in": ns.rope_diameters_in,
            "suspended_length_ft": ns.suspended_length_ft,
            "payload_weight_lbf": ns.payload_weight_lbf,
            "acceleration_ft_per_s2": ns.acceleration_ft_per_s2,
            "sheave_diameter_in": ns.sheave_diameter_in,
            "number_of_supporting_ropes": ns.number_of_supporting_ropes,
            "g_ft_per_s2": ns.g_ft_per_s2,
        }
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
        _render_result_tables(result)
        if out_path:
            print(f"\nWrote: {out_path}")
        return 0

    payload = _payload_from_args(ns)
    result = app.solve(payload["solve_path"], payload)
    _print_json(result)
    _render_result_tables(result)
    if ns.outfile:
        out_path = app.write_output(result, ns.outfile)
        print(f"\nWrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
