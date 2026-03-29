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


def _common_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "mu": args.mu,
        "N": args.N,
        "W": args.W,
        "r": args.r,
        "c": args.c,
        "l": args.l,
        "Ps": args.Ps,
        "unit_system": args.unit_system,
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
    }
    print("\nJournal Bearings Menu")
    print("  1) minimum film thickness")
    print("  2) coefficient of friction")
    print("  3) volumetric flow rate")
    print("  4) maximum film pressure")
    while True:
        choice = input("Choose an option [1-4]: ").strip()
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



def _interactive_common_inputs() -> Dict[str, Any]:
    print("\nEnter the bearing givens. The app will compute the dimensionless state, interpolate the table, and finish automatically.")
    unit_system = input("unit system [default ips]: ").strip().lower() or "ips"
    return {
        "mu": _prompt_float("mu"),
        "N": _prompt_float("N"),
        "W": _prompt_float("W"),
        "r": _prompt_float("r"),
        "c": _prompt_float("c"),
        "l": _prompt_float("l"),
        "Ps": _prompt_float("Ps", 0.0),
        "unit_system": unit_system,
    }



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
        result = api.solve_problem(problem=problem, inputs=_interactive_common_inputs())
        _render_and_write(renderer, result, args.outfile)
        return 0

    if args.command == "run":
        payload = read_problem_file(args.infile)
        result = api.solve_problem(problem=payload["problem"], inputs=payload["inputs"])
        outpath = Path(args.outfile) if args.outfile else _default_outfile_for_input(args.infile)
        _render_and_write(renderer, result, outpath)
        return 0

    problem = normalize_problem_name(args.command)
    result = api.solve_problem(problem=problem, inputs=_common_inputs_from_args(args))
    _render_and_write(renderer, result, args.outfile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
