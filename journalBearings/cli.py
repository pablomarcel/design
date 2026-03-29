from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from apis import JournalBearingAPI
from in_out import ConsoleRenderer, read_problem_file, write_result_file


def _add_common_bearing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mu", type=float, required=True, help="Absolute viscosity, typically reyn in ips workflows.")
    parser.add_argument("--N", type=float, required=True, help="Journal speed in rev/s.")
    parser.add_argument("--W", type=float, required=True, help="Bearing load.")
    parser.add_argument("--r", type=float, required=True, help="Journal radius.")
    parser.add_argument("--c", type=float, required=True, help="Radial clearance.")
    parser.add_argument("--l", type=float, required=True, help="Bearing length.")
    parser.add_argument(
        "--unit-system",
        default="ips",
        choices=["ips", "custom"],
        help="'ips' follows the textbook Example 12-1 to 12-4 conventions. 'custom' keeps the same core dimensionless calculations but skips ips-only power conversions.",
    )
    parser.add_argument("--interactive", action="store_true", help="Prompt for missing manual chart values.")
    parser.add_argument("--outfile", help="Optional JSON output file.")


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cli",
        description="CLI app for Shigley Chapter 12 journal-bearing calculations (initial scope: Examples 12-1 to 12-4).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("ex12_1", help="Solve Example 12-1 style minimum-film-thickness problem.")
    _add_common_bearing_args(p1)
    p1.add_argument("--h0-over-c", type=float, help="Manual chart value from Fig. 12-16.")
    p1.add_argument("--epsilon", type=float, help="Manual chart value e/c from Fig. 12-16.")
    p1.add_argument("--phi-deg", type=float, help="Manual chart value from Fig. 12-17.")

    p2 = sub.add_parser("ex12_2", help="Solve Example 12-2 style friction problem.")
    _add_common_bearing_args(p2)
    p2.add_argument("--rcf", type=float, help="Manual chart value (r/c)f from Fig. 12-18.")

    p3 = sub.add_parser("ex12_3", help="Solve Example 12-3 style flow problem.")
    _add_common_bearing_args(p3)
    p3.add_argument("--q-over-rcNl", type=float, help="Manual chart value Q/(rcNl) from Fig. 12-19.")
    p3.add_argument("--qs-over-q", type=float, help="Manual chart value Qs/Q from Fig. 12-20.")

    p4 = sub.add_parser("ex12_4", help="Solve Example 12-4 style film-pressure problem.")
    _add_common_bearing_args(p4)
    p4.add_argument("--p-over-pmax", type=float, help="Manual chart value P/pmax from Fig. 12-21.")
    p4.add_argument("--theta-pmax-deg", type=float, help="Manual chart value from Fig. 12-22.")
    p4.add_argument("--theta-p0-deg", type=float, help="Manual chart value from Fig. 12-22.")

    prun = sub.add_parser("run", help="Solve a problem from an input JSON file.")
    prun.add_argument("--infile", required=True, help="Input JSON file in the in/ folder or any path.")
    prun.add_argument("--outfile", help="Output JSON filename or path.")
    prun.add_argument("--interactive", action="store_true", help="Prompt for any missing manual chart values.")

    return parser


def _chart_inputs_for_command(command: str, args: argparse.Namespace) -> Dict[str, Any]:
    if command == "ex12_1":
        return {
            "h0_over_c": args.h0_over_c,
            "epsilon": args.epsilon,
            "phi_deg": args.phi_deg,
        }
    if command == "ex12_2":
        return {"rcf": args.rcf}
    if command == "ex12_3":
        return {
            "q_over_rcNl": args.q_over_rcNl,
            "qs_over_q": args.qs_over_q,
        }
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
    stem = infile.stem
    return Path("out") / f"{stem}_result.json"


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    api = JournalBearingAPI()
    renderer = ConsoleRenderer()

    if args.command == "run":
        payload = read_problem_file(args.infile)
        result = api.solve_problem(
            problem=payload["problem"],
            inputs=payload["inputs"],
            chart_inputs=payload.get("chart_inputs"),
            interactive=bool(args.interactive or payload.get("interactive", False)),
        )
        renderer.render_result(result)
        outpath = Path(args.outfile) if args.outfile else _default_outfile_for_input(args.infile)
        write_result_file(outpath, result)
        print(f"\nWrote result file: {outpath}")
        return 0

    result = api.solve_problem(
        problem=args.command,
        inputs=_common_inputs_from_args(args),
        chart_inputs=_prune_none(_chart_inputs_for_command(args.command, args)),
        interactive=args.interactive,
    )
    renderer.render_result(result)
    if args.outfile:
        write_result_file(args.outfile, result)
        print(f"\nWrote result file: {args.outfile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
