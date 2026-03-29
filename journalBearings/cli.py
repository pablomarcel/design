from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from apis import JournalBearingAPI
from in_out import ConsoleRenderer, read_problem_file, write_result_file
from utils import normalize_problem_name, prompt_float


def _add_common_bearing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mu", type=float, required=True, help="Absolute viscosity.")
    parser.add_argument("--N", type=float, required=True, help="Journal speed in rev/s.")
    parser.add_argument("--W", type=float, required=True, help="Bearing load.")
    parser.add_argument("--r", type=float, required=True, help="Journal radius.")
    parser.add_argument("--c", type=float, required=True, help="Radial clearance.")
    parser.add_argument("--l", type=float, required=True, help="Bearing length.")
    parser.add_argument(
        "--unit-system",
        default="ips",
        choices=["ips", "custom"],
        help="Current implementation is ips-first, but custom is allowed for dimensionless calculations.",
    )
    parser.add_argument("--outfile", help="Optional JSON output file.")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Disable holding-pattern chart prompts. If chart values are missing, the run errors out.",
    )


def _common_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "mu": args.mu,
        "N": args.N,
        "W": args.W,
        "r": args.r,
        "c": args.c,
        "l": args.l,
        "unit_system": args.unit_system,
    }


def _chart_inputs_for_command(command: str, args: argparse.Namespace) -> Dict[str, Any]:
    if command == "ex12_1":
        return {"h0_over_c": args.h0_over_c, "epsilon": args.epsilon, "phi_deg": args.phi_deg}
    if command == "ex12_2":
        return {"rcf": args.rcf}
    if command == "ex12_3":
        return {"q_over_rcNl": args.q_over_rcNl, "qs_over_q": args.qs_over_q}
    if command == "ex12_4":
        return {
            "p_over_pmax": args.p_over_pmax,
            "theta_pmax_deg": args.theta_pmax_deg,
            "theta_p0_deg": args.theta_p0_deg,
        }
    return {}


def _prune_none(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


def _default_outfile_for_input(infile: str | Path) -> Path:
    infile = Path(infile)
    return Path("out") / f"{infile.stem}_result.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cli",
        description=(
            "CLI app for Shigley Chapter 12 journal-bearing calculations. "
            "When chart values are missing, the app pauses and asks for them."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pmenu = sub.add_parser("menu", help="Launch an interactive menu workflow.")
    pmenu.add_argument("--outfile", help="Optional JSON output file.")

    p1 = sub.add_parser("ex12_1", help="Example 12-1 workflow.")
    _add_common_bearing_args(p1)
    p1.add_argument("--h0-over-c", type=float, help="Optional pre-known chart value from Fig. 12-16.")
    p1.add_argument("--epsilon", type=float, help="Optional pre-known chart value from Fig. 12-16.")
    p1.add_argument("--phi-deg", type=float, help="Optional pre-known chart value from Fig. 12-17.")

    p2 = sub.add_parser("ex12_2", help="Example 12-2 workflow.")
    _add_common_bearing_args(p2)
    p2.add_argument("--rcf", type=float, help="Optional pre-known chart value from Fig. 12-18.")

    p3 = sub.add_parser("ex12_3", help="Example 12-3 workflow.")
    _add_common_bearing_args(p3)
    p3.add_argument("--q-over-rcNl", type=float, help="Optional pre-known chart value from Fig. 12-19.")
    p3.add_argument("--qs-over-q", type=float, help="Optional pre-known chart value from Fig. 12-20.")

    p4 = sub.add_parser("ex12_4", help="Example 12-4 workflow.")
    _add_common_bearing_args(p4)
    p4.add_argument("--p-over-pmax", type=float, help="Optional pre-known chart value from Fig. 12-21.")
    p4.add_argument("--theta-pmax-deg", type=float, help="Optional pre-known chart value from Fig. 12-22.")
    p4.add_argument("--theta-p0-deg", type=float, help="Optional pre-known chart value from Fig. 12-22.")

    prun = sub.add_parser("run", help="Solve a problem from an input JSON file.")
    prun.add_argument("--infile", required=True, help="Input JSON file in the in/ folder or any path.")
    prun.add_argument("--outfile", help="Output JSON filename or path.")
    prun.add_argument(
        "--no-prompt",
        action="store_true",
        help="Disable chart prompting for missing values in the JSON workflow.",
    )
    return parser


def _interactive_common_inputs() -> Dict[str, Any]:
    print("\nEnter the bearing givens. The app will do the boring algebra and stop when a chart is needed.")
    return {
        "mu": prompt_float("mu") or 0.0,
        "N": prompt_float("N") or 0.0,
        "W": prompt_float("W") or 0.0,
        "r": prompt_float("r") or 0.0,
        "c": prompt_float("c") or 0.0,
        "l": prompt_float("l") or 0.0,
        "unit_system": input("unit system [default ips]: ").strip().lower() or "ips",
    }


def _menu_problem_choice() -> str:
    options = {
        "1": "ex12_1",
        "2": "ex12_2",
        "3": "ex12_3",
        "4": "ex12_4",
    }
    print("\nJournal Bearings Menu")
    print("  1) Example 12-1  minimum film thickness, eccentricity, phi")
    print("  2) Example 12-2  coefficient of friction, torque, power loss")
    print("  3) Example 12-3  total flow and side flow")
    print("  4) Example 12-4  maximum film pressure and angles")
    while True:
        choice = input("Choose an option [1-4]: ").strip()
        if choice in options:
            return options[choice]
        print("Invalid option. Try again.")


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
        inputs = _interactive_common_inputs()
        result = api.solve_problem(problem=problem, inputs=inputs, chart_inputs=None, interactive=True)
        _render_and_write(renderer, result, args.outfile)
        return 0

    if args.command == "run":
        payload = read_problem_file(args.infile)
        result = api.solve_problem(
            problem=payload["problem"],
            inputs=payload["inputs"],
            chart_inputs=payload.get("chart_inputs"),
            interactive=not args.no_prompt,
        )
        outpath = Path(args.outfile) if args.outfile else _default_outfile_for_input(args.infile)
        _render_and_write(renderer, result, outpath)
        return 0

    problem = normalize_problem_name(args.command)
    result = api.solve_problem(
        problem=problem,
        inputs=_common_inputs_from_args(args),
        chart_inputs=_prune_none(_chart_inputs_for_command(problem, args)),
        interactive=not args.no_prompt,
    )
    _render_and_write(renderer, result, args.outfile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
