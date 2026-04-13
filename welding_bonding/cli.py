from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from .app import WeldingBondingApp
    from .utils import ROOT_DIR, ValidationError, format_json
except ImportError:  # pragma: no cover
    from app import WeldingBondingApp
    from utils import ROOT_DIR, ValidationError, format_json


class WeldingBondingCLI:
    def __init__(self) -> None:
        self.app = WeldingBondingApp(root_dir=ROOT_DIR)
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="python -m cli",
            description="CLI app for welding and bonding calculations per Shigley.",
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        run_parser = subparsers.add_parser("run", help="Solve a problem from an input JSON file")
        run_parser.add_argument("--infile", required=True, help="Input JSON file name or path")
        run_parser.add_argument("--outfile", help="Output JSON file name or path")
        run_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
        run_parser.add_argument("--show", action="store_true", help="Print solution JSON to stdout")

        torsion = subparsers.add_parser("torsion", help="Solve a welded-joint torsion problem from CLI flags")
        torsion.add_argument("--title", default="Weld-group torsion analysis")
        torsion.add_argument("--weld-type", type=int, required=True, dest="weld_type")
        torsion.add_argument("--weld-size-mm", type=float, required=True)
        torsion.add_argument("--b-mm", type=float)
        torsion.add_argument("--d-mm", type=float)
        torsion.add_argument("--r-mm", type=float)
        torsion.add_argument("--analyzed-group-force-N", type=float)
        torsion.add_argument("--total-force-N", type=float)
        torsion.add_argument("--group-share-count", type=int, default=1)
        torsion.add_argument("--load-line-x-mm", type=float)
        torsion.add_argument("--load-line-y-mm", type=float)
        torsion.add_argument("--moment-arm-mm", type=float)
        torsion.add_argument(
            "--primary-shear-direction",
            default="negative_x",
            choices=["positive_x", "negative_x", "positive_y", "negative_y"],
        )
        torsion.add_argument("--torsion-sign", default="ccw", choices=["ccw", "cw"])
        torsion.add_argument(
            "--combination-model",
            default="shigley_radial",
            choices=["shigley_radial", "tangential"],
            help="Direction model used to combine primary and secondary shear components.",
        )
        torsion.add_argument("--outfile")
        torsion.add_argument("--pretty", action="store_true")
        torsion.add_argument("--show", action="store_true")

        list_parser = subparsers.add_parser("list", help="List available solve paths")
        list_parser.add_argument("--show", action="store_true", help="Unused compatibility flag")

        return parser

    def run(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        try:
            if args.command == "run":
                result = self.app.solve_file(args.infile, outfile=args.outfile, pretty=args.pretty)
                if args.show:
                    print(format_json(result, pretty=args.pretty))
                return 0

            if args.command == "torsion":
                payload = self._payload_from_torsion_args(args)
                result = self.app.solve_payload(payload, outfile=args.outfile, pretty=args.pretty)
                if args.show:
                    print(format_json(result, pretty=args.pretty))
                return 0

            if args.command == "list":
                print("Available solve paths:")
                for item in self.app.api.available_solve_paths():
                    print(f"- {item}")
                return 0

            self.parser.error(f"Unsupported command: {args.command}")
            return 2
        except (ValidationError, ValueError, FileNotFoundError, KeyError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    def _payload_from_torsion_args(self, args: argparse.Namespace) -> Dict[str, Any]:
        geometry = {}
        if args.b_mm is not None:
            geometry["b"] = args.b_mm
        if args.d_mm is not None:
            geometry["d"] = args.d_mm
        if args.r_mm is not None:
            geometry["r"] = args.r_mm
        payload: Dict[str, Any] = {
            "problem": "weld_group_torsion",
            "title": args.title,
            "solve_path": "weld_group_torsion",
            "weld_type": args.weld_type,
            "weld_size_mm": args.weld_size_mm,
            "geometry": geometry,
            "group_share_count": args.group_share_count,
            "primary_shear_direction": args.primary_shear_direction,
            "torsion_sign": args.torsion_sign,
            "combination_model": args.combination_model,
        }
        if args.analyzed_group_force_N is not None:
            payload["analyzed_group_force_N"] = args.analyzed_group_force_N
        if args.total_force_N is not None:
            payload["total_force_N"] = args.total_force_N
        if args.load_line_x_mm is not None:
            payload["load_line_x_mm"] = args.load_line_x_mm
        if args.load_line_y_mm is not None:
            payload["load_line_y_mm"] = args.load_line_y_mm
        if args.moment_arm_mm is not None:
            payload["moment_arm_mm"] = args.moment_arm_mm
        return payload


def main(argv: list[str] | None = None) -> int:
    return WeldingBondingCLI().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
