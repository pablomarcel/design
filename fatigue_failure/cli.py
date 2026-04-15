from __future__ import annotations

import argparse
import sys
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

        sf_parser = subparsers.add_parser(
            "surface_factor",
            help="Direct CLI entry point for Example 6-3 style Marin surface-factor calculations.",
        )
        sf_parser.add_argument("--title", default="Surface factor analysis from CLI flags")
        sf_parser.add_argument("--surface-finish", required=True, help="Surface finish from Table 6-2, e.g. 'Machined or cold-drawn'.")
        sf_parser.add_argument("--sut-kpsi", type=float, help="Ultimate tensile strength in kpsi.")
        sf_parser.add_argument("--sut-mpa", type=float, help="Ultimate tensile strength in MPa.")
        sf_parser.add_argument("--strength-unit", choices=["kpsi", "MPa"], help="Preferred unit form for Eq. (6-19).")
        sf_parser.add_argument("--expected-ka", type=float, help="Optional reference ka value for verification.")
        sf_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        sf_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        sf_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        size_parser = subparsers.add_parser(
            "size_factor",
            help="Direct CLI entry point for Example 6-4 style Marin size-factor calculations.",
        )
        size_parser.add_argument("--title", default="Size factor analysis from CLI flags")
        size_parser.add_argument("--loading-type", choices=["bending", "torsion", "axial"], default="bending")
        size_parser.add_argument("--mode", choices=["rotating", "nonrotating"], default="rotating")
        size_parser.add_argument("--diameter-mm", type=float, help="Diameter in mm for rotating mode, or for nonrotating solid_round.")
        size_parser.add_argument("--shape", choices=["solid_round", "rectangle", "i_shape", "channel"], help="Nonrotating Table 6-3 shape.")
        size_parser.add_argument("--axis", choices=["axis_1_1", "axis_2_2"], help="Axis selection for nonrotating I-shape or channel.")
        size_parser.add_argument("--sut-mpa", type=float, help="Problem statement ultimate tensile strength in MPa.")
        size_parser.add_argument("--expected-kb", type=float, help="Optional reference kb value for verification.")
        size_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        size_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        size_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        tf_parser = subparsers.add_parser(
            "temperature_factor",
            help="Direct CLI entry point for Example 6-5 style Marin temperature-factor calculations.",
        )
        tf_parser.add_argument("--title", default="Temperature factor analysis from CLI flags")
        tf_parser.add_argument("--service-temperature-f", type=float, required=True, help="Service temperature in °F.")
        tf_parser.add_argument("--sut-room-temperature-kpsi", type=float, required=True, help="Room-temperature tensile strength in kpsi.")
        tf_parser.add_argument("--se-prime-room-temperature-kpsi", type=float, help="Known room-temperature endurance limit in kpsi for the tested-material route.")
        tf_parser.add_argument("--temperature-factor-method", choices=["polynomial", "table_interpolation"], default="polynomial")
        tf_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        tf_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        tf_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")


        scns_parser = subparsers.add_parser(
            "stress_concentration_notch_sensitivity",
            help="Direct CLI entry point for Example 6-6 style stress concentration and notch sensitivity calculations.",
        )
        scns_parser.add_argument("--title", default="Stress concentration and notch sensitivity analysis from CLI flags")
        scns_parser.add_argument("--sut-mpa", type=float, help="Ultimate tensile strength in MPa.")
        scns_parser.add_argument("--sut-kpsi", type=float, help="Ultimate tensile strength in kpsi.")
        scns_parser.add_argument("--small-diameter-mm", type=float, required=True, help="Small shaft diameter d in mm.")
        scns_parser.add_argument("--large-diameter-mm", type=float, required=True, help="Large shaft diameter D in mm.")
        scns_parser.add_argument("--fillet-radius-mm", type=float, required=True, help="Shoulder fillet radius r in mm.")
        scns_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        scns_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        scns_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

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

    def _payload_from_surface_factor_args(self, args: argparse.Namespace) -> dict[str, Any]:
        inputs: dict[str, Any] = {
            "solve_path": "surface_factor",
            "surface_finish": args.surface_finish,
            "sut_kpsi": args.sut_kpsi,
            "sut_MPa": args.sut_mpa,
            "strength_unit": args.strength_unit,
        }
        if args.expected_ka is not None:
            inputs["expected_textbook_reference_values"] = {"ka": args.expected_ka}
        return {
            "problem": "surface_factor",
            "title": args.title,
            "inputs": inputs,
        }

    def _payload_from_size_factor_args(self, args: argparse.Namespace) -> dict[str, Any]:
        case: dict[str, Any] = {
            "name": "size_factor_case",
            "mode": args.mode,
        }
        if args.mode == "rotating":
            case["diameter_mm"] = args.diameter_mm
        else:
            case["shape"] = args.shape or "solid_round"
            case["axis"] = args.axis
            if (args.shape or "solid_round") == "solid_round" and args.diameter_mm is not None:
                case["shape_parameters_mm"] = {"d": args.diameter_mm}
        inputs: dict[str, Any] = {
            "solve_path": "size_factor",
            "loading_type": args.loading_type,
            "sut_MPa": args.sut_mpa,
            "cases": [case],
        }
        if args.expected_kb is not None:
            inputs["expected_textbook_reference_values"] = {"case_results": {"size_factor_case": args.expected_kb}}
        return {
            "problem": "size_factor",
            "title": args.title,
            "inputs": inputs,
        }

    def _payload_from_temperature_factor_args(self, args: argparse.Namespace) -> dict[str, Any]:
        cases = []
        if args.se_prime_room_temperature_kpsi is not None:
            cases.append(
                {
                    "name": "known_room_temperature_endurance_limit",
                    "case_type": "known_room_temperature_endurance_limit",
                    "temperature_factor_method": args.temperature_factor_method,
                    "se_prime_room_temperature_kpsi": args.se_prime_room_temperature_kpsi,
                }
            )
        cases.append(
            {
                "name": "only_room_temperature_tensile_strength_known",
                "case_type": "only_room_temperature_tensile_strength_known",
                "temperature_factor_method": "table_interpolation",
            }
        )
        return {
            "problem": "temperature_factor",
            "title": args.title,
            "inputs": {
                "solve_path": "temperature_factor",
                "service_temperature_F": args.service_temperature_f,
                "sut_room_temperature_kpsi": args.sut_room_temperature_kpsi,
                "cases": cases,
            },
        }


    def _payload_from_stress_concentration_notch_sensitivity_args(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "problem": "stress_concentration_notch_sensitivity",
            "title": args.title,
            "inputs": {
                "solve_path": "stress_concentration_notch_sensitivity",
                "sut_MPa": args.sut_mpa,
                "sut_kpsi": args.sut_kpsi,
                "small_diameter_mm": args.small_diameter_mm,
                "large_diameter_mm": args.large_diameter_mm,
                "fillet_radius_mm": args.fillet_radius_mm,
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
            elif args.command == "surface_factor":
                payload = self._payload_from_surface_factor_args(args)
            elif args.command == "size_factor":
                payload = self._payload_from_size_factor_args(args)
            elif args.command == "temperature_factor":
                payload = self._payload_from_temperature_factor_args(args)
            elif args.command == "stress_concentration_notch_sensitivity":
                payload = self._payload_from_stress_concentration_notch_sensitivity_args(args)
            else:
                self.parser.error(f"Unsupported command: {args.command}")
                return 2

            result = self.app.solve_payload(payload, outfile=args.outfile, pretty=args.pretty)
            if args.show or not args.outfile:
                print(json_text(result, pretty=args.pretty or True))
            else:
                resolved = self.app.io.resolve_output_path(args.outfile)
                print(f"Wrote {resolved}")
            return 0

        except FatigueFailureError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1


def main(argv: list[str] | None = None) -> int:
    return FatigueFailureCLI().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
