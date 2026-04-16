from __future__ import annotations

import argparse
import sys
from typing import Any

from rich.console import Console

try:
    from .app import StaticFailureApp
except ImportError:  # pragma: no cover
    from app import StaticFailureApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="static_failure",
        description="CLI app for Shigley static-failure calculations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Solve a problem from an input JSON file.")
    run_parser.add_argument("--infile", required=True, help="Input JSON file, absolute or package-relative.")
    run_parser.add_argument("--outfile", help="Output JSON file. Defaults to package out/ when filename only is given.")
    run_parser.add_argument("--pretty", action="store_true", help="Write pretty-printed JSON output.")
    run_parser.add_argument("--show", action="store_true", help="Render the summary table in the terminal.")

    direct_parser = subparsers.add_parser(
        "ductile_failure_fos",
        help="Direct CLI solve for the Example 5-1 style ductile static-failure problem.",
    )
    direct_parser.add_argument("--Syt", type=float, required=True, help="Yield strength in tension.")
    direct_parser.add_argument("--Syc", type=float, help="Yield strength in compression. Defaults to Syt.")
    direct_parser.add_argument("--ef", type=float, help="True strain at fracture.")
    direct_parser.add_argument("--strength-unit", default="kpsi", help="Strength unit label for reporting.")
    direct_parser.add_argument(
        "--case",
        action="append",
        nargs="+",
        metavar="VALUE",
        help=(
            "Plane-stress case definition as four values: label sigma_x sigma_y tau_xy. "
            "May be repeated."
        ),
    )
    direct_parser.add_argument("--outfile", help="Output JSON file.")
    direct_parser.add_argument("--pretty", action="store_true", help="Write pretty-printed JSON output.")
    direct_parser.add_argument("--show", action="store_true", help="Render the summary table in the terminal.")

    cm_parser = subparsers.add_parser(
        "coulomb_mohr_fos",
        help="Direct CLI solve for Example 5-2 style Coulomb-Mohr factor of safety.",
    )
    cm_parser.add_argument("--material-lookup", help="material_id from data/static_failure_materials.csv")
    cm_parser.add_argument("--Syt", type=float, help="Yield strength in tension.")
    cm_parser.add_argument("--Syc", type=float, help="Yield strength in compression.")
    cm_parser.add_argument("--strength-unit", default="MPa", help="Strength unit label for reporting.")
    cm_parser.add_argument(
        "--stress-input-mode",
        choices=["torsion_shaft", "plane_stress", "principal_stresses"],
        default="torsion_shaft",
        help="How the stress state is defined.",
    )
    cm_parser.add_argument("--diameter-mm", type=float, help="Shaft diameter for torsion_shaft mode.")
    cm_parser.add_argument("--torque-N-m", type=float, help="Applied torque for torsion_shaft mode.")
    cm_parser.add_argument("--sigma-x", type=float, help="Plane-stress sigma_x.")
    cm_parser.add_argument("--sigma-y", type=float, help="Plane-stress sigma_y.")
    cm_parser.add_argument("--tau-xy", type=float, help="Plane-stress tau_xy.")
    cm_parser.add_argument(
        "--principal-stresses",
        nargs=3,
        type=float,
        metavar=("S1", "S2", "S3"),
        help="Principal stresses for principal_stresses mode.",
    )
    cm_parser.add_argument("--label", default="coulomb_mohr_case", help="Case label for reporting.")
    cm_parser.add_argument("--outfile", help="Output JSON file.")
    cm_parser.add_argument("--pretty", action="store_true", help="Write pretty-printed JSON output.")
    cm_parser.add_argument("--show", action="store_true", help="Render the summary table in the terminal.")

    return parser


def build_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for raw_case in args.case or []:
        if len(raw_case) != 4:
            raise ValueError(
                "Each --case entry must contain exactly four values: label sigma_x sigma_y tau_xy"
            )
        label, sigma_x, sigma_y, tau_xy = raw_case
        cases.append(
            {
                "label": label,
                "sigma_x": float(sigma_x),
                "sigma_y": float(sigma_y),
                "tau_xy": float(tau_xy),
            }
        )

    return {
        "problem": "static_failure",
        "title": "Static failure factor-of-safety analysis",
        "inputs": {
            "solve_path": "ductile_failure_fos",
            "Syt": args.Syt,
            "Syc": args.Syc if args.Syc is not None else args.Syt,
            "ef": args.ef,
            "strength_unit": args.strength_unit,
            "stress_states": cases,
        },
    }


def build_coulomb_mohr_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "solve_path": "coulomb_mohr_fos",
        "strength_unit": args.strength_unit,
        "stress_input_mode": args.stress_input_mode,
        "label": args.label,
    }
    if args.material_lookup:
        inputs["material_lookup"] = args.material_lookup
    if args.Syt is not None:
        inputs["Syt"] = args.Syt
    if args.Syc is not None:
        inputs["Syc"] = args.Syc

    if args.stress_input_mode == "torsion_shaft":
        if args.diameter_mm is None or args.torque_N_m is None:
            raise ValueError("torsion_shaft mode requires --diameter-mm and --torque-N-m")
        inputs["diameter_mm"] = args.diameter_mm
        inputs["torque_N_m"] = args.torque_N_m
    elif args.stress_input_mode == "plane_stress":
        if args.sigma_x is None or args.sigma_y is None or args.tau_xy is None:
            raise ValueError("plane_stress mode requires --sigma-x --sigma-y --tau-xy")
        inputs["sigma_x"] = args.sigma_x
        inputs["sigma_y"] = args.sigma_y
        inputs["tau_xy"] = args.tau_xy
    elif args.stress_input_mode == "principal_stresses":
        if args.principal_stresses is None:
            raise ValueError("principal_stresses mode requires --principal-stresses S1 S2 S3")
        inputs["principal_stresses"] = list(args.principal_stresses)

    return {
        "problem": "static_failure",
        "title": "Coulomb-Mohr factor-of-safety analysis",
        "inputs": inputs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    console = Console()
    app = StaticFailureApp(console=console)

    try:
        if args.command == "run":
            app.solve_file(
                infile=args.infile,
                outfile=args.outfile,
                pretty=args.pretty,
                show=args.show,
            )
            return 0

        if args.command == "ductile_failure_fos":
            payload = build_payload_from_args(args)
            app.solve_payload(
                payload,
                outfile=args.outfile,
                pretty=args.pretty,
                show=args.show,
            )
            return 0

        if args.command == "coulomb_mohr_fos":
            payload = build_coulomb_mohr_payload_from_args(args)
            app.solve_payload(
                payload,
                outfile=args.outfile,
                pretty=args.pretty,
                show=args.show,
            )
            return 0

        parser.error(f"Unsupported command: {args.command}")
        return 2
    except Exception as exc:  # pragma: no cover
        console.print(f"[bold red]Error:[/bold red] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
