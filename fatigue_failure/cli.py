from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    from .app import FatigueFailureApp
    from .utils import FatigueFailureError, json_text
except ImportError:  # pragma: no cover
    from app import FatigueFailureApp
    from utils import FatigueFailureError, json_text


class FatigueFailureCLI:
    def __init__(self) -> None:
        self.app = FatigueFailureApp()
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="python -m cli",
            description="CLI for Shigley Chapter 6 fatigue-failure calculations.",
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        run_parser = subparsers.add_parser("run", help="Solve a fatigue-failure problem from a JSON input file.")
        run_parser.add_argument("--infile", required=True, help="Input JSON path. If relative, the package in/ folder is searched.")
        run_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        run_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        run_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        fs_parser = subparsers.add_parser(
            "fatigue_strength",
            help="Direct CLI entry point for Example 6-2 style fatigue-strength calculations.",
        )
        fs_parser.add_argument("--title", default="Fatigue strength analysis from CLI flags")
        fs_parser.add_argument("--sae-aisi-no", dest="sae_aisi_no", help="SAE/AISI steel designation for Table A-20 lookup, e.g. 1050.")
        fs_parser.add_argument("--processing", help="Processing variant for Table A-20 lookup, e.g. HR or CD.")
        fs_parser.add_argument("--sut-kpsi", type=float, help="Ultimate tensile strength in kpsi.")
        fs_parser.add_argument("--sut-mpa", type=float, help="Ultimate tensile strength in MPa.")
        fs_parser.add_argument("--se-kpsi", type=float, help="Actual component endurance limit in kpsi. If omitted, Eq. (6-8) is used.")
        fs_parser.add_argument("--se-prime-kpsi", type=float, help="Specimen endurance limit S'e in kpsi.")
        fs_parser.add_argument("--f-override", dest="fatigue_strength_fraction_f_override", type=float, help="Override the Figure 6-18 fatigue strength fraction f.")
        fs_parser.add_argument("--strength-at-cycles", type=float, dest="strength_at_cycles", help="Compute fatigue strength at the specified cycles using Eq. (6-13).")
        fs_parser.add_argument("--life-at-stress-kpsi", type=float, dest="life_at_stress_kpsi", help="Compute life at the specified completely reversed stress using Eq. (6-16).")
        fs_parser.add_argument("--low-cycle-stress-at-cycles", type=float, dest="low_cycle_stress_at_cycles", help="Compute low-cycle lower-bound stress using Eq. (6-17).")
        fs_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        fs_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        fs_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        paths_parser = subparsers.add_parser("list-solve-paths", help="List supported solve paths.")
        paths_parser.add_argument("--json", action="store_true", help="Emit the solve paths as JSON.")

        return parser

    def _payload_from_fatigue_strength_args(self, args: argparse.Namespace) -> dict[str, Any]:
        stress_queries = []
        if args.strength_at_cycles is not None:
            stress_queries.append({"name": "strength_query", "cycles": args.strength_at_cycles})

        life_queries = []
        if args.life_at_stress_kpsi is not None:
            life_queries.append({"name": "life_query", "stress_kpsi": args.life_at_stress_kpsi})

        low_cycle_queries = []
        if args.low_cycle_stress_at_cycles is not None:
            low_cycle_queries.append({"name": "low_cycle_query", "cycles": args.low_cycle_stress_at_cycles})

        return {
            "problem": "fatigue_strength",
            "title": args.title,
            "inputs": {
                "solve_path": "fatigue_strength",
                "sae_aisi_no": args.sae_aisi_no,
                "processing": args.processing,
                "sut_kpsi": args.sut_kpsi,
                "sut_MPa": args.sut_mpa,
                "se_kpsi": args.se_kpsi,
                "se_prime_kpsi": args.se_prime_kpsi,
                "fatigue_strength_fraction_f_override": args.fatigue_strength_fraction_f_override,
                "stress_queries": stress_queries,
                "life_queries": life_queries,
                "low_cycle_queries": low_cycle_queries,
            },
        }

    def run(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        try:
            if args.command == "list-solve-paths":
                solve_paths = self.app.api.available_solve_paths()
                if args.json:
                    print(json_text({"solve_paths": solve_paths}, pretty=True))
                else:
                    for path in solve_paths:
                        print(path)
                return 0

            if args.command == "run":
                result = self.app.solve_file(args.infile, outfile=args.outfile, pretty=args.pretty)
                if args.show:
                    print(json_text(result, pretty=args.pretty or True))
                elif args.outfile:
                    resolved = self.app.io.resolve_output_path(args.outfile)
                    print(f"Wrote {resolved}")
                return 0

            if args.command == "fatigue_strength":
                payload = self._payload_from_fatigue_strength_args(args)
                result = self.app.solve_payload(payload, outfile=args.outfile, pretty=args.pretty)
                if args.show or not args.outfile:
                    print(json_text(result, pretty=args.pretty or True))
                else:
                    resolved = self.app.io.resolve_output_path(args.outfile)
                    print(f"Wrote {resolved}")
                return 0

            self.parser.error(f"Unsupported command: {args.command}")
            return 2
        except FatigueFailureError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1


def main(argv: list[str] | None = None) -> int:
    return FatigueFailureCLI().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
