from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from apis import JournalBearingAPI
from in_out import ConsoleRenderer, read_problem_file, write_result_file
from utils import normalize_problem_name


def _add_common_bearing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mu", type=float, required=True, help="Absolute viscosity.")
    parser.add_argument("--N", type=float, required=True, help="Journal speed in rev/s.")
    parser.add_argument("--W", type=float, required=True, help="Bearing load.")
    parser.add_argument("--r", type=float, required=True, help="Journal radius.")
    parser.add_argument("--c", type=float, required=True, help="Radial clearance.")
    parser.add_argument("--l", type=float, required=True, help="Bearing length.")
    parser.add_argument("--Ps", type=float, default=0.0, help="Supply pressure. Default is 0 for non-pressure-fed bearings.")
    parser.add_argument(
        "--unit-system",
        default="ips",
        choices=["ips", "custom"],
        help="ips is the current reference system for convenience outputs like hp and Btu/s.",
    )
    parser.add_argument("--outfile", help="Optional JSON output file.")


def _add_temperature_rise_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--oil-grade", required=True, help="SAE oil grade such as 10, 20, 30, 40, 50, 60.")
    parser.add_argument("--inlet-temp-f", type=float, required=True, help="Inlet temperature in degrees F.")
    parser.add_argument("--rho", type=float, default=0.0315, help="Oil density in lbm/in^3 for ips workflows.")
    parser.add_argument("--cp", type=float, default=0.48, help="Specific heat in Btu/(lbm*F) for ips workflows.")
    parser.add_argument("--J", type=float, default=778.0 * 12.0, help="Mechanical equivalent of heat. Default 778*12 in·lbf/Btu.")
    parser.add_argument("--temp-tol-f", type=float, default=2.0, help="Convergence tolerance on successive effective temperatures.")
    parser.add_argument("--max-iter", type=int, default=50, help="Maximum number of temperature-viscosity iterations.")


def _add_self_contained_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--N", type=float, required=True, help="Journal speed in rev/s.")
    parser.add_argument("--W", type=float, required=True, help="Bearing load.")
    parser.add_argument("--r", type=float, required=True, help="Journal radius.")
    parser.add_argument("--c", type=float, required=True, help="Radial clearance.")
    parser.add_argument("--l", type=float, required=True, help="Bearing length.")
    parser.add_argument("--oil-grade", required=True, help="SAE oil grade such as 10, 20, 30, 40, 50, 60.")
    parser.add_argument("--ambient-temp-f", type=float, required=True, help="Ambient air temperature in degrees F.")
    parser.add_argument("--alpha", type=float, required=True, help="Geometry factor alpha from Shigley Eq. (12-19).")
    parser.add_argument("--area-in2", type=float, required=True, help="Lateral bearing area A in in^2.")
    parser.add_argument("--h-cr", type=float, required=True, help="Heat-transfer coefficient h_CR in Btu/(h*ft^2*F).")
    parser.add_argument(
        "--unit-system",
        default="ips",
        choices=["ips", "custom"],
        help="ips is the current reference system for convenience outputs like hp and Btu/s.",
    )
    parser.add_argument("--temp-tol-f", type=float, default=2.0, help="Convergence tolerance on the final temperature bracket width.")
    parser.add_argument("--max-iter", type=int, default=60, help="Maximum number of heat-balance bisection iterations.")
    parser.add_argument("--outfile", help="Optional JSON output file.")


def _common_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "mu": args.mu,
        "N": args.N,
        "W": args.W,
        "r": args.r,
        "c": args.c,
        "l": args.l,
        "Ps": args.Ps,
        "unit_system": args.unit_system,
    }
    for key, argname in (
        ("oil_grade", "oil_grade"),
        ("inlet_temp_F", "inlet_temp_f"),
        ("rho", "rho"),
        ("cp", "cp"),
        ("J", "J"),
        ("temp_tol_F", "temp_tol_f"),
        ("max_iter", "max_iter"),
    ):
        if hasattr(args, argname):
            data[key] = getattr(args, argname)
    return data


def _self_contained_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "N": args.N,
        "W": args.W,
        "r": args.r,
        "c": args.c,
        "l": args.l,
        "oil_grade": args.oil_grade,
        "ambient_temp_F": args.ambient_temp_f,
        "alpha": args.alpha,
        "area_in2": args.area_in2,
        "h_cr": args.h_cr,
        "unit_system": args.unit_system,
        "temp_tol_F": args.temp_tol_f,
        "max_iter": args.max_iter,
    }


def _default_outfile_for_input(infile: str | Path) -> Path:
    infile = Path(infile)
    return Path("out") / f"{infile.stem}_result.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cli",
        description="Automatic journal-bearing app backed by finite_journal_bearing.csv and interpolation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pmenu = sub.add_parser("menu", help="Launch an interactive menu workflow.")
    pmenu.add_argument("--outfile", help="Optional JSON output file.")

    for name, help_text in (
        ("minimum_film_thickness", "Compute minimum film thickness, eccentricity, and phi automatically."),
        ("coefficient_of_friction", "Compute coefficient of friction, torque, and power loss automatically."),
        ("volumetric_flow_rate", "Compute flow rates automatically."),
        ("maximum_film_pressure", "Compute maximum film pressure automatically."),
    ):
        p = sub.add_parser(name, help=help_text)
        _add_common_bearing_args(p)

    ptemp = sub.add_parser("temperature_rise", help="Compute temperature rise with iterative viscosity update.")
    _add_common_bearing_args(ptemp)
    _add_temperature_rise_args(ptemp)

    pself = sub.add_parser("self_contained_steady_state", help="Solve Shigley self-contained steady-state bearing problems like Example 12-5.")
    _add_self_contained_args(pself)

    prun = sub.add_parser("run", help="Solve a problem from an input JSON file.")
    prun.add_argument("--infile", required=True, help="Input JSON file in the in/ folder or any path.")
    prun.add_argument("--outfile", help="Output JSON filename or path.")
    return parser


def _menu_problem_choice() -> str:
    options = {
        "1": "minimum_film_thickness",
        "2": "coefficient_of_friction",
        "3": "volumetric_flow_rate",
        "4": "maximum_film_pressure",
        "5": "temperature_rise",
        "6": "self_contained_steady_state",
    }
    print("\nJournal Bearings Menu")
    print("  1) minimum film thickness")
    print("  2) coefficient of friction")
    print("  3) volumetric flow rate")
    print("  4) maximum film pressure")
    print("  5) temperature rise")
    print("  6) self-contained steady state")
    while True:
        choice = input("Choose an option [1-6]: ").strip()
        if choice in options:
            return options[choice]
        print("Invalid option. Try again.")


def _prompt_float(label: str, default: float | None = None) -> float:
    while True:
        suffix = f" [default {default}]" if default is not None else ""
        raw = input(f"{label}{suffix}: ").strip()
        if raw == "" and default is not None:
            return float(default)
        try:
            return float(raw)
        except ValueError:
            print(f"Could not parse a number from {raw!r}. Try again.")


def _interactive_common_inputs(problem: str) -> Dict[str, Any]:
    if problem == "self_contained_steady_state":
        print("\nEnter the self-contained steady-state bearing givens.")
        unit_system = input("unit system [default ips]: ").strip().lower() or "ips"
        return {
            "N": _prompt_float("N"),
            "W": _prompt_float("W"),
            "r": _prompt_float("r"),
            "c": _prompt_float("c"),
            "l": _prompt_float("l"),
            "oil_grade": input("oil grade (SAE) [e.g. 20]: ").strip(),
            "ambient_temp_F": _prompt_float("ambient_temp_F"),
            "alpha": _prompt_float("alpha"),
            "area_in2": _prompt_float("area_in2"),
            "h_cr": _prompt_float("h_cr"),
            "unit_system": unit_system,
            "temp_tol_F": _prompt_float("temp_tol_F", 2.0),
            "max_iter": int(_prompt_float("max_iter", 60)),
        }

    print("\nEnter the bearing givens. The app will compute the dimensionless state, interpolate the table, and finish automatically.")
    unit_system = input("unit system [default ips]: ").strip().lower() or "ips"
    data: Dict[str, Any] = {
        "mu": _prompt_float("mu"),
        "N": _prompt_float("N"),
        "W": _prompt_float("W"),
        "r": _prompt_float("r"),
        "c": _prompt_float("c"),
        "l": _prompt_float("l"),
        "Ps": _prompt_float("Ps", 0.0),
        "unit_system": unit_system,
    }
    if problem == "temperature_rise":
        data.update(
            {
                "oil_grade": input("oil grade (SAE) [e.g. 10]: ").strip(),
                "inlet_temp_F": _prompt_float("inlet_temp_F"),
                "rho": _prompt_float("rho", 0.0315),
                "cp": _prompt_float("cp", 0.48),
                "J": _prompt_float("J", 778.0 * 12.0),
                "temp_tol_F": _prompt_float("temp_tol_F", 2.0),
                "max_iter": int(_prompt_float("max_iter", 50)),
            }
        )
    return data


def _render_and_write(renderer: ConsoleRenderer, result: Dict[str, Any], outfile: str | Path | None) -> None:
    renderer.render_result(result)
    if outfile:
        write_result_file(outfile, result)
        print(f"\nWrote result file: {outfile}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    api = JournalBearingAPI()
    renderer = ConsoleRenderer()

    if args.command == "menu":
        problem = _menu_problem_choice()
        result = api.solve_problem(problem=problem, inputs=_interactive_common_inputs(problem))
        _render_and_write(renderer, result, args.outfile)
        return 0

    if args.command == "run":
        payload = read_problem_file(args.infile)
        result = api.solve_problem(problem=payload["problem"], inputs=payload["inputs"])
        outpath = Path(args.outfile) if args.outfile else _default_outfile_for_input(args.infile)
        _render_and_write(renderer, result, outpath)
        return 0

    problem = normalize_problem_name(args.command)
    if problem == "self_contained_steady_state":
        result = api.solve_problem(problem=problem, inputs=_self_contained_inputs_from_args(args))
    else:
        result = api.solve_problem(problem=problem, inputs=_common_inputs_from_args(args))
    _render_and_write(renderer, result, args.outfile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
