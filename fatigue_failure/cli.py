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

        run_parser = subparsers.add_parser(
            "run",
            help="Solve a fatigue-failure problem from a JSON input file.",
        )
        run_parser.add_argument(
            "--infile",
            required=True,
            help="Input JSON path. If relative, the package in/ folder is searched.",
        )
        run_parser.add_argument(
            "--outfile",
            help="Output JSON path. If relative without directories, it is written under out/.",
        )
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

        ctf_parser = subparsers.add_parser(
            "cycles_to_failure",
            help="Direct CLI entry point for Example 6-7 style fully reversed cycles-to-failure calculations.",
        )
        ctf_parser.add_argument("--title", default="Cycles to failure analysis from CLI flags")
        ctf_parser.add_argument("--sut-mpa", type=float, help="Ultimate tensile strength in MPa.")
        ctf_parser.add_argument("--sut-kpsi", type=float, help="Ultimate tensile strength in kpsi.")
        ctf_parser.add_argument("--se-mpa", type=float, help="Fully corrected endurance limit in MPa.")
        ctf_parser.add_argument("--se-kpsi", type=float, help="Fully corrected endurance limit in kpsi.")
        ctf_parser.add_argument("--sigma-rev-nom-mpa", type=float, help="Nominal fully reversing stress in MPa.")
        ctf_parser.add_argument("--sigma-rev-nom-kpsi", type=float, help="Nominal fully reversing stress in kpsi.")
        ctf_parser.add_argument("--k-f", "--K-f", dest="K_f", type=float, required=True, help="Fatigue stress concentration factor Kf.")
        ctf_parser.add_argument("--f-override", dest="fatigue_strength_fraction_f_override", type=float, help="Override Figure 6-18 fatigue strength fraction f.")
        ctf_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        ctf_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        ctf_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        e68_parser = subparsers.add_parser(
            "endurance_limit_and_fatigue_strength",
            help="Direct CLI entry point for Example 6-8 style endurance-limit and fatigue-strength calculations.",
        )
        e68_parser.add_argument("--title", default="Endurance limit and fatigue strength analysis from CLI flags")
        e68_parser.add_argument("--sae-aisi-no", dest="sae_aisi_no", required=True, help="SAE/AISI steel designation for Table A-20 lookup, e.g. 1015.")
        e68_parser.add_argument("--processing", required=True, help="Processing variant for Table A-20 lookup, e.g. HR or CD.")
        e68_parser.add_argument("--surface-finish", default="Machined or cold-drawn", help="Surface finish used for k_a, e.g. 'Machined or cold-drawn'.")
        e68_parser.add_argument("--diameter-in", type=float, help="Bar diameter in inches.")
        e68_parser.add_argument("--diameter-mm", type=float, help="Bar diameter in mm.")
        e68_parser.add_argument("--loading-type", choices=["axial", "bending", "torsion"], default="axial")
        e68_parser.add_argument("--service-temperature-f", type=float, help="Service temperature in °F.")
        e68_parser.add_argument("--service-temperature-c", type=float, help="Service temperature in °C.")
        e68_parser.add_argument("--reliability-percent", type=float, required=True, help="Required reliability percentage, e.g. 99.")
        e68_parser.add_argument("--cycles", type=float, required=True, help="Target cycles to failure for fatigue-strength evaluation.")
        e68_parser.add_argument("--misc-factor", type=float, default=1.0, help="Miscellaneous Marin factor k_f. Defaults to 1.0.")
        e68_parser.add_argument("--size-factor-k-b", dest="size_factor_k_b", type=float, help="Optional direct override for size factor k_b.")
        e68_parser.add_argument("--load-factor-k-c", dest="load_factor_k_c", type=float, help="Optional direct override for load factor k_c.")
        e68_parser.add_argument("--temperature-factor-k-d", dest="temperature_factor_k_d", type=float, help="Optional direct override for temperature factor k_d.")
        e68_parser.add_argument("--reliability-factor-k-e", dest="reliability_factor_k_e", type=float, help="Optional direct override for reliability factor k_e.")
        e68_parser.add_argument("--f-override", dest="fatigue_strength_fraction_f_override", type=float, help="Override the Figure 6-18 fatigue strength fraction f.")
        e68_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        e68_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        e68_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        lop_parser = subparsers.add_parser(
            "life_of_part",
            help="Direct CLI entry point for Example 6-9 style life-of-a-part calculations in reversed bending.",
        )
        lop_parser.add_argument("--title", default="Life of a part analysis from CLI flags")
        lop_parser.add_argument("--sae-aisi-no", dest="sae_aisi_no", required=True, help="SAE/AISI steel designation for Table A-20 lookup, e.g. 1050.")
        lop_parser.add_argument("--processing", required=True, help="Processing variant for Table A-20 lookup, e.g. HR or CD.")
        lop_parser.add_argument("--surface-finish", default="Machined or cold-drawn", help="Surface finish used for k_a, e.g. 'Machined or cold-drawn'.")
        lop_parser.add_argument("--small-diameter-mm", type=float, required=True, help="Small shaft diameter d in mm.")
        lop_parser.add_argument("--large-diameter-mm", type=float, required=True, help="Large shaft diameter D in mm.")
        lop_parser.add_argument("--fillet-radius-mm", type=float, required=True, help="Shoulder fillet radius r in mm.")
        lop_parser.add_argument("--m-b-n-m", dest="M_B_N_m", type=float, required=True, help="Bending moment at the critical section B in N·m.")
        lop_parser.add_argument("--service-temperature-f", type=float, help="Service temperature in °F. Defaults to 70°F if omitted.")
        lop_parser.add_argument("--service-temperature-c", type=float, help="Service temperature in °C.")
        lop_parser.add_argument("--reliability-percent", type=float, default=50.0, help="Required reliability percentage. Defaults to 50.")
        lop_parser.add_argument("--misc-factor", type=float, default=1.0, help="Miscellaneous Marin factor k_f. Defaults to 1.0.")
        lop_parser.add_argument("--size-factor-k-b", dest="size_factor_k_b", type=float, help="Optional direct override for size factor k_b.")
        lop_parser.add_argument("--load-factor-k-c", dest="load_factor_k_c", type=float, help="Optional direct override for load factor k_c.")
        lop_parser.add_argument("--temperature-factor-k-d", dest="temperature_factor_k_d", type=float, help="Optional direct override for temperature factor k_d.")
        lop_parser.add_argument("--reliability-factor-k-e", dest="reliability_factor_k_e", type=float, help="Optional direct override for reliability factor k_e.")
        lop_parser.add_argument("--k-t", dest="K_t", type=float, help="Optional direct override for theoretical stress concentration factor K_t.")
        lop_parser.add_argument("--q", type=float, help="Optional direct override for notch sensitivity q.")
        lop_parser.add_argument("--k-f", "--K-f", dest="K_f", type=float, help="Optional direct override for fatigue stress concentration factor K_f.")
        lop_parser.add_argument("--f-override", dest="fatigue_strength_fraction_f_override", type=float, help="Override the Figure 6-18 fatigue strength fraction f.")
        lop_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        lop_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        lop_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        ffs_parser = subparsers.add_parser(
            "fatigue_factor_of_safety",
            help="Direct CLI entry point for Example 6-10 style fatigue factor-of-safety calculations.",
        )
        ffs_parser.add_argument("--title", default="Fatigue factor of safety analysis from CLI flags")
        ffs_parser.add_argument("--sae-aisi-no", dest="sae_aisi_no", required=True, help="SAE/AISI steel designation for Table A-20 lookup, e.g. 1050.")
        ffs_parser.add_argument("--processing", required=True, help="Processing variant for Table A-20 lookup, e.g. HR or CD.")
        ffs_parser.add_argument("--surface-finish", default="Machined or cold-drawn", help="Surface finish used for k_a, e.g. 'Machined or cold-drawn'.")
        ffs_parser.add_argument("--diameter-in", type=float, help="Bar diameter in inches.")
        ffs_parser.add_argument("--diameter-mm", type=float, help="Bar diameter in mm.")
        ffs_parser.add_argument("--load-min-kip", type=float, help="Minimum fluctuating axial load in kip.")
        ffs_parser.add_argument("--load-max-kip", type=float, help="Maximum fluctuating axial load in kip.")
        ffs_parser.add_argument("--load-min-lbf", type=float, help="Minimum fluctuating axial load in lbf.")
        ffs_parser.add_argument("--load-max-lbf", type=float, help="Maximum fluctuating axial load in lbf.")
        ffs_parser.add_argument("--sigma-a-kpsi", type=float, help="Local alternating stress in kpsi.")
        ffs_parser.add_argument("--sigma-m-kpsi", type=float, help="Local mean stress in kpsi.")
        ffs_parser.add_argument("--sigma-a-nom-kpsi", type=float, help="Nominal alternating stress in kpsi.")
        ffs_parser.add_argument("--sigma-m-nom-kpsi", type=float, help="Nominal mean stress in kpsi.")
        ffs_parser.add_argument("--k-f", "--K-f", dest="K_f", type=float, required=True, help="Fatigue stress concentration factor K_f.")
        ffs_parser.add_argument("--service-temperature-f", type=float, help="Service temperature in °F. Defaults to 70°F.")
        ffs_parser.add_argument("--service-temperature-c", type=float, help="Service temperature in °C.")
        ffs_parser.add_argument("--reliability-percent", type=float, default=50.0, help="Required reliability percentage. Defaults to 50.")
        ffs_parser.add_argument("--misc-factor", type=float, default=1.0, help="Miscellaneous Marin factor k_f. Defaults to 1.0.")
        ffs_parser.add_argument("--size-factor-k-b", dest="size_factor_k_b", type=float, help="Optional direct override for size factor k_b.")
        ffs_parser.add_argument("--load-factor-k-c", dest="load_factor_k_c", type=float, help="Optional direct override for load factor k_c.")
        ffs_parser.add_argument("--temperature-factor-k-d", dest="temperature_factor_k_d", type=float, help="Optional direct override for temperature factor k_d.")
        ffs_parser.add_argument("--reliability-factor-k-e", dest="reliability_factor_k_e", type=float, help="Optional direct override for reliability factor k_e.")
        ffs_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        ffs_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        ffs_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        glfl_parser = subparsers.add_parser(
            "gerber_langer_failure_lines",
            help="Direct CLI entry point for Example 6-11 style Gerber-Langer failure-line calculations.",
        )
        glfl_parser.add_argument("--title", default="Gerber-Langer failure lines analysis from CLI flags")
        glfl_parser.add_argument("--length-in", type=float, required=True, help="Cantilever length in inches.")
        glfl_parser.add_argument("--width-in", type=float, required=True, help="Cantilever width in inches.")
        glfl_parser.add_argument("--thickness-in", type=float, required=True, help="Cantilever thickness in inches.")
        glfl_parser.add_argument("--elastic-modulus-psi", type=float, required=True, help="Elastic modulus in psi.")
        glfl_parser.add_argument("--total-motion-in", type=float, required=True, help="Total follower motion in inches.")
        glfl_parser.add_argument("--sut-kpsi", type=float, required=True, help="Ultimate tensile strength in kpsi.")
        glfl_parser.add_argument("--sy-kpsi", type=float, required=True, help="Yield strength in kpsi.")
        glfl_parser.add_argument("--se-kpsi", type=float, required=True, help="Fully corrected endurance limit in kpsi.")
        glfl_parser.add_argument("--preload-deflection-in", action="append", type=float, dest="preload_deflections_in", required=True, help="Preload deflection in inches. Repeat for multiple preload cases.")
        glfl_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        glfl_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        glfl_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        mcctf_parser = subparsers.add_parser(
            "multiple_criteria_cycles_to_failure",
            help="Direct CLI entry point for Example 6-12 style cycles-to-failure calculations using multiple criteria.",
        )
        mcctf_parser.add_argument("--title", default="Multiple criteria cycles to failure analysis from CLI flags")
        mcctf_parser.add_argument("--sigma-max-kpsi", type=float, help="Maximum cyclic stress in kpsi.")
        mcctf_parser.add_argument("--sigma-min-kpsi", type=float, help="Minimum cyclic stress in kpsi.")
        mcctf_parser.add_argument("--sigma-max-mpa", type=float, help="Maximum cyclic stress in MPa.")
        mcctf_parser.add_argument("--sigma-min-mpa", type=float, help="Minimum cyclic stress in MPa.")
        mcctf_parser.add_argument("--sut-kpsi", dest="Sut_kpsi", type=float, help="Ultimate tensile strength in kpsi.")
        mcctf_parser.add_argument("--sut-mpa", dest="Sut_MPa", type=float, help="Ultimate tensile strength in MPa.")
        mcctf_parser.add_argument("--sy-kpsi", dest="Sy_kpsi", type=float, help="Yield strength in kpsi.")
        mcctf_parser.add_argument("--sy-mpa", dest="Sy_MPa", type=float, help="Yield strength in MPa.")
        mcctf_parser.add_argument("--se-kpsi", dest="Se_kpsi", type=float, help="Fully corrected endurance limit in kpsi.")
        mcctf_parser.add_argument("--se-mpa", dest="Se_MPa", type=float, help="Fully corrected endurance limit in MPa.")
        mcctf_parser.add_argument("--f", type=float, required=True, help="Fatigue strength fraction f.")
        mcctf_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        mcctf_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        mcctf_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

        bmaf_parser = subparsers.add_parser(
            "brittle_material_axial_fatigue",
            help="Direct CLI entry point for Example 6-13 style brittle-material axial fatigue calculations.",
        )
        bmaf_parser.add_argument("--title", default="Brittle material axial fatigue analysis from CLI flags")
        bmaf_parser.add_argument("--astm-number", type=int, required=True, help="Gray cast iron ASTM grade number from Table A-24, e.g. 30.")
        bmaf_parser.add_argument("--width-in", type=float, required=True, help="Link width w in inches.")
        bmaf_parser.add_argument("--thickness-in", type=float, required=True, help="Link thickness t in inches.")
        bmaf_parser.add_argument("--hole-diameter-in", type=float, required=True, help="Transverse-hole diameter d in inches.")
        bmaf_parser.add_argument("--q-brittle", dest="q_brittle", type=float, required=True, help="Brittle-material notch sensitivity q to use for the example.")
        bmaf_parser.add_argument("--axial-load-factor-k-c", dest="axial_load_factor_k_c", type=float, default=0.9, help="Axial load factor k_c for the corrected endurance limit.")
        bmaf_parser.add_argument("--temperature-factor-k-d", dest="temperature_factor_k_d", type=float, default=1.0, help="Temperature factor k_d.")
        bmaf_parser.add_argument("--reliability-factor-k-e", dest="reliability_factor_k_e", type=float, default=1.0, help="Reliability factor k_e.")
        bmaf_parser.add_argument("--misc-factor", type=float, default=1.0, help="Miscellaneous factor k_f. Defaults to 1.0.")
        bmaf_parser.add_argument("--steady-load-lbf", type=float, default=1000.0, help="Steady tensile load for part (a), in lbf.")
        bmaf_parser.add_argument("--repeated-max-load-lbf", type=float, default=1000.0, help="Repeated maximum tensile load for part (b), in lbf. Minimum is taken as 0.")
        bmaf_parser.add_argument("--fluctuating-min-load-lbf", type=float, default=-1000.0, help="Minimum fluctuating load for part (c), in lbf.")
        bmaf_parser.add_argument("--fluctuating-max-load-lbf", type=float, default=300.0, help="Maximum fluctuating load for part (c), in lbf.")
        bmaf_parser.add_argument("--outfile", help="Output JSON path. If relative without directories, it is written under out/.")
        bmaf_parser.add_argument("--pretty", action="store_true", help="Write and print formatted JSON.")
        bmaf_parser.add_argument("--show", action="store_true", help="Print result JSON to stdout.")

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
        return {"problem": "surface_factor", "title": args.title, "inputs": inputs}

    def _payload_from_size_factor_args(self, args: argparse.Namespace) -> dict[str, Any]:
        case: dict[str, Any] = {"name": "size_factor_case", "mode": args.mode}
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
        return {"problem": "size_factor", "title": args.title, "inputs": inputs}

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

    def _payload_from_cycles_to_failure_args(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "problem": "cycles_to_failure",
            "title": args.title,
            "inputs": {
                "solve_path": "cycles_to_failure",
                "sut_MPa": args.sut_mpa,
                "sut_kpsi": args.sut_kpsi,
                "Se_MPa": args.se_mpa,
                "Se_kpsi": args.se_kpsi,
                "sigma_rev_nom_MPa": args.sigma_rev_nom_mpa,
                "sigma_rev_nom_kpsi": args.sigma_rev_nom_kpsi,
                "K_f": args.K_f,
                "fatigue_strength_fraction_f_override": args.fatigue_strength_fraction_f_override,
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

    def _payload_from_endurance_limit_and_fatigue_strength_args(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "problem": "endurance_limit_and_fatigue_strength",
            "title": args.title,
            "inputs": {
                "solve_path": "endurance_limit_and_fatigue_strength",
                "sae_aisi_no": args.sae_aisi_no,
                "processing": args.processing,
                "surface_finish": args.surface_finish,
                "diameter_in": args.diameter_in,
                "diameter_mm": args.diameter_mm,
                "loading_type": args.loading_type,
                "service_temperature_F": args.service_temperature_f,
                "service_temperature_C": args.service_temperature_c,
                "reliability_percent": args.reliability_percent,
                "cycles": args.cycles,
                "miscellaneous_factor_k_f": args.misc_factor,
                "size_factor_k_b": args.size_factor_k_b,
                "load_factor_k_c": args.load_factor_k_c,
                "temperature_factor_k_d": args.temperature_factor_k_d,
                "reliability_factor_k_e": args.reliability_factor_k_e,
                "fatigue_strength_fraction_f_override": args.fatigue_strength_fraction_f_override,
            },
        }

    def _payload_from_life_of_part_args(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "problem": "life_of_part",
            "title": args.title,
            "inputs": {
                "solve_path": "life_of_part",
                "sae_aisi_no": args.sae_aisi_no,
                "processing": args.processing,
                "surface_finish": args.surface_finish,
                "small_diameter_mm": args.small_diameter_mm,
                "large_diameter_mm": args.large_diameter_mm,
                "fillet_radius_mm": args.fillet_radius_mm,
                "M_B_N_m": args.M_B_N_m,
                "service_temperature_F": args.service_temperature_f,
                "service_temperature_C": args.service_temperature_c,
                "reliability_percent": args.reliability_percent,
                "miscellaneous_factor_k_f": args.misc_factor,
                "size_factor_k_b": args.size_factor_k_b,
                "load_factor_k_c": args.load_factor_k_c,
                "temperature_factor_k_d": args.temperature_factor_k_d,
                "reliability_factor_k_e": args.reliability_factor_k_e,
                "K_t": args.K_t,
                "q": args.q,
                "K_f": args.K_f,
                "fatigue_strength_fraction_f_override": args.fatigue_strength_fraction_f_override,
            },
        }

    def _payload_from_fatigue_factor_of_safety_args(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "problem": "fatigue_factor_of_safety",
            "title": args.title,
            "inputs": {
                "solve_path": "fatigue_factor_of_safety",
                "sae_aisi_no": args.sae_aisi_no,
                "processing": args.processing,
                "surface_finish": args.surface_finish,
                "diameter_in": args.diameter_in,
                "diameter_mm": args.diameter_mm,
                "load_min_kip": args.load_min_kip,
                "load_max_kip": args.load_max_kip,
                "load_min_lbf": args.load_min_lbf,
                "load_max_lbf": args.load_max_lbf,
                "sigma_a_kpsi": args.sigma_a_kpsi,
                "sigma_m_kpsi": args.sigma_m_kpsi,
                "sigma_a_nom_kpsi": args.sigma_a_nom_kpsi,
                "sigma_m_nom_kpsi": args.sigma_m_nom_kpsi,
                "K_f": args.K_f,
                "service_temperature_F": args.service_temperature_f,
                "service_temperature_C": args.service_temperature_c,
                "reliability_percent": args.reliability_percent,
                "miscellaneous_factor_k_f": args.misc_factor,
                "size_factor_k_b": args.size_factor_k_b,
                "load_factor_k_c": args.load_factor_k_c,
                "temperature_factor_k_d": args.temperature_factor_k_d,
                "reliability_factor_k_e": args.reliability_factor_k_e,
            },
        }

    def _payload_from_gerber_langer_failure_lines_args(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "problem": "gerber_langer_failure_lines",
            "title": args.title,
            "inputs": {
                "solve_path": "gerber_langer_failure_lines",
                "length_in": args.length_in,
                "width_in": args.width_in,
                "thickness_in": args.thickness_in,
                "elastic_modulus_psi": args.elastic_modulus_psi,
                "total_motion_in": args.total_motion_in,
                "Sut_kpsi": args.sut_kpsi,
                "Sy_kpsi": args.sy_kpsi,
                "Se_kpsi": args.se_kpsi,
                "preload_deflections_in": args.preload_deflections_in,
            },
        }

    def _payload_from_multiple_criteria_cycles_to_failure_args(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "problem": "multiple_criteria_cycles_to_failure",
            "title": args.title,
            "inputs": {
                "solve_path": "multiple_criteria_cycles_to_failure",
                "sigma_max_kpsi": args.sigma_max_kpsi,
                "sigma_min_kpsi": args.sigma_min_kpsi,
                "sigma_max_MPa": args.sigma_max_mpa,
                "sigma_min_MPa": args.sigma_min_mpa,
                "Sut_kpsi": args.Sut_kpsi,
                "Sut_MPa": args.Sut_MPa,
                "Sy_kpsi": args.Sy_kpsi,
                "Sy_MPa": args.Sy_MPa,
                "Se_kpsi": args.Se_kpsi,
                "Se_MPa": args.Se_MPa,
                "f": args.f,
            },
        }

    def _payload_from_brittle_material_axial_fatigue_args(self, args: argparse.Namespace) -> dict[str, Any]:
        return {
            "problem": "brittle_material_axial_fatigue",
            "title": args.title,
            "inputs": {
                "solve_path": "brittle_material_axial_fatigue",
                "astm_number": args.astm_number,
                "width_in": args.width_in,
                "thickness_in": args.thickness_in,
                "hole_diameter_in": args.hole_diameter_in,
                "brittle_notch_sensitivity_q": args.q_brittle,
                "axial_load_factor_k_c": args.axial_load_factor_k_c,
                "temperature_factor_k_d": args.temperature_factor_k_d,
                "reliability_factor_k_e": args.reliability_factor_k_e,
                "miscellaneous_factor_k_f": args.misc_factor,
                "cases": [
                    {
                        "name": "part_a_steady_tension",
                        "case_type": "steady",
                        "load_min_lbf": args.steady_load_lbf,
                        "load_max_lbf": args.steady_load_lbf,
                    },
                    {
                        "name": "part_b_repeated_application",
                        "case_type": "repeated",
                        "load_min_lbf": 0.0,
                        "load_max_lbf": args.repeated_max_load_lbf,
                    },
                    {
                        "name": "part_c_fluctuating_with_compression",
                        "case_type": "fluctuating",
                        "load_min_lbf": args.fluctuating_min_load_lbf,
                        "load_max_lbf": args.fluctuating_max_load_lbf,
                    },
                ],
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
            elif args.command == "cycles_to_failure":
                payload = self._payload_from_cycles_to_failure_args(args)
            elif args.command == "endurance_limit_and_fatigue_strength":
                payload = self._payload_from_endurance_limit_and_fatigue_strength_args(args)
            elif args.command == "life_of_part":
                payload = self._payload_from_life_of_part_args(args)
            elif args.command == "fatigue_factor_of_safety":
                payload = self._payload_from_fatigue_factor_of_safety_args(args)
            elif args.command == "gerber_langer_failure_lines":
                payload = self._payload_from_gerber_langer_failure_lines_args(args)
            elif args.command == "multiple_criteria_cycles_to_failure":
                payload = self._payload_from_multiple_criteria_cycles_to_failure_args(args)
            elif args.command == "brittle_material_axial_fatigue":
                payload = self._payload_from_brittle_material_axial_fatigue_args(args)
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
