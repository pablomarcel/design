#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.five_speed

Mercedes-Benz W5A-580 5-speed automatic transmission kinematic model.

Reference basis
---------------
This module is built from the user-provided gearbox diagram and mechanism
summary for the Mercedes-Benz W5A-580 / 722.6 family style 5-speed layout:

- three simple planetary gearsets
    * forward set
    * rear set
    * middle set
- forward ring is driven by the turbine / input
- forward carrier drives the rear ring
- rear carrier drives the middle ring
- middle carrier is the output
- C1 locks the forward sun to input
- C2 connects input to the rear-carrier / middle-ring node
- C3 connects the rear sun to the middle sun
- B1 grounds the forward sun
- B2 grounds the middle sun
- BR grounds the rear-carrier / middle-ring node
- F1 and F2 are one-way holding elements used in some states

Important honesty note
----------------------
This is a *kinematic* central-topology model reconstructed from the provided
reference figure and text. It is meant for ratio/state analysis, not for clutch
hydraulics, torque capacity, overrunning logic under all transients, or OEM
service procedures.

Modeled rotating members
------------------------
    input  : turbine / transmission input
    fs     : forward-set sun
    fc     : forward-set carrier = rear-set ring
    rs     : rear-set sun
    rc     : rear-set carrier = middle-set ring
    ms     : middle-set sun
    out    : middle-set carrier = output shaft

Planetary relations
-------------------
Forward set:
    Ns_f * (w_fs - w_fc) + Nr_f * (w_in - w_fc) = 0

Rear set:
    Ns_r * (w_rs - w_rc) + Nr_r * (w_fc - w_rc) = 0

Middle set:
    Ns_m * (w_ms - w_out) + Nr_m * (w_rc - w_out) = 0
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import sympy as sp


class FiveSpeedCliError(ValueError):
    """User-facing CLI/configuration error for five_speed.py."""


@dataclass(frozen=True)
class GearState:
    name: str
    display_elements: tuple[str, ...]
    constrained_equalities: tuple[tuple[str, str], ...]
    constrained_grounds: tuple[str, ...]
    notes: str = ""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    # Candidate set chosen to reproduce the published W5A-580 ratios closely:
    # 1st ≈ 3.59, 2nd ≈ 2.19, 3rd ≈ 1.41, 4th = 1.00, 5th ≈ 0.83,
    # R1 ≈ -3.16, R2 ≈ -1.93
    "Ns_f": 46,
    "Nr_f": 72,
    "Ns_r": 68,
    "Nr_r": 122,
    "Ns_m": 37,
    "Nr_m": 91,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "w5a580_candidate": {
        "Ns_f": 46,
        "Nr_f": 72,
        "Ns_r": 68,
        "Nr_r": 122,
        "Ns_m": 37,
        "Nr_m": 91,
    },
}

PRESET_NOTES: Mapping[str, str] = {
    "w5a580_candidate": "Candidate tooth-count set fitted to the published W5A-580 ratio spread; not claimed as OEM-confirmed tooth data.",
}


STATE_ALIASES: Mapping[str, str] = {
    "1": "1st",
    "1st": "1st",
    "first": "1st",
    "2": "2nd",
    "2nd": "2nd",
    "second": "2nd",
    "3": "3rd",
    "3rd": "3rd",
    "third": "3rd",
    "4": "4th",
    "4th": "4th",
    "fourth": "4th",
    "5": "5th",
    "5th": "5th",
    "fifth": "5th",
    "r1": "R1",
    "rev1": "R1",
    "reverse1": "R1",
    "reverse_1": "R1",
    "reverse-first": "R1",
    "r2": "R2",
    "rev2": "R2",
    "reverse2": "R2",
    "reverse_2": "R2",
    "reverse-second": "R2",
    "n": "N",
    "neutral": "N",
}


def validate_tooth_counts(counts: Mapping[str, int]) -> None:
    labels = (
        ("forward", int(counts["Ns_f"]), int(counts["Nr_f"])),
        ("rear", int(counts["Ns_r"]), int(counts["Nr_r"])),
        ("middle", int(counts["Ns_m"]), int(counts["Nr_m"])),
    )
    for label, Ns, Nr in labels:
        if Ns <= 0 or Nr <= 0:
            raise FiveSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
        if Nr <= Ns:
            raise FiveSpeedCliError(
                f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
            )
        if (Nr - Ns) % 2 != 0:
            raise FiveSpeedCliError(
                f"Invalid {label} tooth counts: (Nr - Ns) must be even for a simple planetary interpretation. "
                f"Got Ns={Ns}, Nr={Nr}, Nr-Ns={Nr - Ns}."
            )


class MercedesW5A580FiveSpeedTransmission:
    """Three-planetary W5A-580 style transmission kinematic model."""

    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "R1", "R2", "N")

    SHIFT_SCHEDULE: Mapping[str, GearState] = {
        "1st": GearState(
            name="1st",
            display_elements=("C3(overrun)", "B1(overrun)", "B2", "F1", "F2"),
            constrained_equalities=(),
            constrained_grounds=("fs", "rs", "ms"),
            notes="Forward sun held, rear sun held, middle sun held. Three reductions in cascade.",
        ),
        "2nd": GearState(
            name="2nd",
            display_elements=("C1", "C3(overrun)", "B2", "F2"),
            constrained_equalities=(("fs", "input"),),
            constrained_grounds=("rs", "ms"),
            notes="Forward set rotates as a block; rear and middle sets still reduce speed.",
        ),
        "3rd": GearState(
            name="3rd",
            display_elements=("C1", "C2", "B2"),
            constrained_equalities=(("fs", "input"), ("rc", "input")),
            constrained_grounds=("ms",),
            notes="Drive reaches the middle ring directly through C2; ratio occurs only in the middle set.",
        ),
        "4th": GearState(
            name="4th",
            display_elements=("C1", "C2", "C3"),
            constrained_equalities=(("fs", "input"), ("rc", "input"), ("rs", "ms")),
            constrained_grounds=(),
            notes="All three planetary sets are locked; direct drive.",
        ),
        "5th": GearState(
            name="5th",
            display_elements=("C2", "C3", "B1", "F1(overrun)"),
            constrained_equalities=(("rc", "input"), ("rs", "ms")),
            constrained_grounds=("fs",),
            notes="Forward set reduces the rear-ring speed while C2 drives the middle-ring / rear-carrier node, producing overdrive.",
        ),
        "R1": GearState(
            name="R1",
            display_elements=("C3(overrun)", "B1(overrun)", "BR", "F1", "F2"),
            constrained_equalities=(("rs", "ms"),),
            constrained_grounds=("fs", "rc"),
            notes="Forward set reduced speed feeds the rear ring while BR grounds the rear-carrier / middle-ring node; output reverses.",
        ),
        "R2": GearState(
            name="R2",
            display_elements=("C1", "C3(overrun)", "BR", "F2"),
            constrained_equalities=(("fs", "input"), ("rs", "ms")),
            constrained_grounds=("rc",),
            notes="Second reverse analogous to second gear: forward set locked, BR grounds the rear-carrier / middle-ring node.",
        ),
        "N": GearState(
            name="N",
            display_elements=("C3", "B1"),
            constrained_equalities=(("rs", "ms"),),
            constrained_grounds=("fs",),
            notes="Neutral is reported by operating convention. The output is treated as stationary for display purposes.",
        ),
    }

    def __init__(self, *, Ns_f: int, Nr_f: int, Ns_r: int, Nr_r: int, Ns_m: int, Nr_m: int) -> None:
        self.tooth_counts: Dict[str, int] = {
            "Ns_f": int(Ns_f),
            "Nr_f": int(Nr_f),
            "Ns_r": int(Ns_r),
            "Nr_r": int(Nr_r),
            "Ns_m": int(Ns_m),
            "Nr_m": int(Nr_m),
        }
        validate_tooth_counts(self.tooth_counts)
        self.Ns_f = int(Ns_f)
        self.Nr_f = int(Nr_f)
        self.Ns_r = int(Ns_r)
        self.Nr_r = int(Nr_r)
        self.Ns_m = int(Ns_m)
        self.Nr_m = int(Nr_m)
        self.member_names: tuple[str, ...] = ("input", "fs", "fc", "rs", "rc", "ms", "out")

    @staticmethod
    def normalize_state_name(state: str) -> str:
        key = state.strip().lower()
        if key == "all":
            return "all"
        if key not in STATE_ALIASES:
            raise FiveSpeedCliError(
                "Unknown state: {}. Valid states are 1st, 2nd, 3rd, 4th, 5th, R1, R2, N, or all.".format(state)
            )
        return STATE_ALIASES[key]

    def _symbols(self) -> Dict[str, sp.Symbol]:
        return {name: sp.symbols(f"w_{name}") for name in self.member_names}

    def _planetary_equations(self, s: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        return [
            self.Ns_f * (s["fs"] - s["fc"]) + self.Nr_f * (s["input"] - s["fc"]),
            self.Ns_r * (s["rs"] - s["rc"]) + self.Nr_r * (s["fc"] - s["rc"]),
            self.Ns_m * (s["ms"] - s["out"]) + self.Nr_m * (s["rc"] - s["out"]),
        ]

    @staticmethod
    def _constraint_equations(state: GearState, s: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        eqs: List[sp.Expr] = []
        for a, b in state.constrained_equalities:
            eqs.append(s[a] - s[b])
        for name in state.constrained_grounds:
            eqs.append(s[name])
        return eqs

    def solve(self, state: str, *, input_speed: float = 1.0) -> Dict[str, object]:
        normalized = self.normalize_state_name(state)
        if normalized == "all":
            raise FiveSpeedCliError("Use solve_all() when state='all'.")

        gear_state = self.SHIFT_SCHEDULE[normalized]

        if normalized == "N":
            return {
                "state": gear_state.name,
                "engaged": list(gear_state.display_elements),
                "speeds": {
                    "input": float(input_speed),
                    "fs": 0.0,
                    "fc": 0.0,
                    "rs": 0.0,
                    "rc": 0.0,
                    "ms": 0.0,
                    "out": 0.0,
                },
                "ratio": 0.0,
                "ratio_signed": 0.0,
                "notes": gear_state.notes,
            }

        s = self._symbols()
        equations: List[sp.Expr] = []
        equations.extend(self._planetary_equations(s))
        equations.extend(self._constraint_equations(gear_state, s))
        equations.append(s["input"] - float(input_speed))

        variables = [s[name] for name in self.member_names]
        solutions = sp.solve(equations, variables, dict=True)
        if not solutions:
            raise RuntimeError(f"No kinematic solution found for state {normalized}")

        sol = solutions[0]
        speeds: Dict[str, float] = {}
        for name in self.member_names:
            sym = s[name]
            if sym not in sol:
                raise RuntimeError(f"Undetermined variable in state {normalized}: {name}")
            speeds[name] = float(sol[sym])

        output_speed = speeds["out"]
        if abs(output_speed) < 1.0e-12:
            raise RuntimeError(f"Output speed is zero in state {normalized}; ratio undefined")

        ratio_signed = float(input_speed) / output_speed
        ratio_display = ratio_signed if normalized in {"R1", "R2"} else abs(ratio_signed)

        return {
            "state": gear_state.name,
            "engaged": list(gear_state.display_elements),
            "speeds": speeds,
            "ratio": float(ratio_display),
            "ratio_signed": float(ratio_signed),
            "notes": gear_state.notes,
        }

    def solve_all(self) -> Dict[str, Dict[str, object]]:
        return {label: self.solve(label) for label in self.DISPLAY_ORDER}



def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    counts = dict(DEFAULT_TOOTH_COUNTS)

    if args.preset:
        if args.preset not in PRESETS:
            raise FiveSpeedCliError(
                f"Unknown preset '{args.preset}'. Available presets: {', '.join(sorted(PRESETS))}"
            )
        counts.update(PRESETS[args.preset])

    overrides = {
        "Ns_f": args.Ns_f,
        "Nr_f": args.Nr_f,
        "Ns_r": args.Ns_r,
        "Nr_r": args.Nr_r,
        "Ns_m": args.Ns_m,
        "Nr_m": args.Nr_m,
    }
    for key, value in overrides.items():
        if value is not None:
            counts[key] = int(value)

    validate_tooth_counts(counts)
    return counts



def _print_tooth_counts(counts: Mapping[str, int], *, preset: Optional[str] = None) -> None:
    print("Tooth Counts")
    print("------------------------------------------------------------")
    print(f"Forward set: Ns_f={counts['Ns_f']}, Nr_f={counts['Nr_f']}")
    print(f"Rear set   : Ns_r={counts['Ns_r']}, Nr_r={counts['Nr_r']}")
    print(f"Middle set : Ns_m={counts['Ns_m']}, Nr_m={counts['Nr_m']}")
    if preset and preset in PRESET_NOTES:
        print(f"Preset note: {PRESET_NOTES[preset]}")
    print()



def _print_single(result: Mapping[str, object], *, tooth_counts: Mapping[str, int], preset: Optional[str]) -> None:
    _print_tooth_counts(tooth_counts, preset=preset)
    print(f"State: {result['state']}")
    print(f"Engaged: {' + '.join(result['engaged'])}")
    print(f"Ratio (input/output): {float(result['ratio']):.6f}")
    print(f"Notes: {result['notes']}")
    print(json.dumps(result['speeds'], indent=2))



def _print_all(results: Mapping[str, Mapping[str, object]], *, tooth_counts: Mapping[str, int], preset: Optional[str]) -> None:
    _print_tooth_counts(tooth_counts, preset=preset)
    print("Mercedes-Benz W5A-580 5-Speed Kinematic Summary")
    print("-" * 128)
    print(f"{'State':<6} {'Elems':<34} {'Ratio':>8} {'Input':>9} {'F.sun':>9} {'F.car':>9} {'R.sun':>9} {'R.car':>9} {'M.sun':>9} {'Out':>9}")
    print("-" * 128)
    for key in MercedesW5A580FiveSpeedTransmission.DISPLAY_ORDER:
        r = results[key]
        s = r['speeds']
        print(
            f"{key:<6} {'+'.join(r['engaged']):<34} "
            f"{float(r['ratio']):>8.3f} "
            f"{float(s['input']):>9.3f} "
            f"{float(s['fs']):>9.3f} "
            f"{float(s['fc']):>9.3f} "
            f"{float(s['rs']):>9.3f} "
            f"{float(s['rc']):>9.3f} "
            f"{float(s['ms']):>9.3f} "
            f"{float(s['out']):>9.3f}"
        )



def _print_ratios_only(results: Mapping[str, Mapping[str, object]], *, as_json: bool = False) -> None:
    payload = {key: float(results[key]['ratio']) for key in MercedesW5A580FiveSpeedTransmission.DISPLAY_ORDER}
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    print("Ratios Only")
    print("------------------------------------------------------------")
    for key in MercedesW5A580FiveSpeedTransmission.DISPLAY_ORDER:
        print(f"{key:>3}: {payload[key]:.6f}")



def _emit_cli_error(*, args: argparse.Namespace, message: str, tooth_counts: Optional[Mapping[str, int]] = None) -> int:
    payload = {
        "ok": False,
        "error": message,
        "preset": getattr(args, "preset", None),
    }
    if tooth_counts is not None:
        payload["tooth_counts"] = dict(tooth_counts)

    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        print("five_speed.py error", file=sys.stderr)
        print("-------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                f"Forward: Ns_f={tooth_counts['Ns_f']}, Nr_f={tooth_counts['Nr_f']} | "
                f"Rear: Ns_r={tooth_counts['Ns_r']}, Nr_r={tooth_counts['Nr_r']} | "
                f"Middle: Ns_m={tooth_counts['Ns_m']}, Nr_m={tooth_counts['Nr_m']}",
                file=sys.stderr,
            )
    return 2



def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Mercedes-Benz W5A-580 5-speed automatic transmission kinematic solver")
    p.add_argument("--state", default="all", help="State to solve: 1st, 2nd, 3rd, 4th, 5th, R1, R2, N, or all")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Print only the ratios")
    p.add_argument("--preset", choices=sorted(PRESETS.keys()), default="w5a580_candidate", help="Named tooth-count preset")
    p.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    p.add_argument("--Ns-f", dest="Ns_f", type=int, default=None, help="Forward-set sun tooth count")
    p.add_argument("--Nr-f", dest="Nr_f", type=int, default=None, help="Forward-set ring tooth count")
    p.add_argument("--Ns-r", dest="Ns_r", type=int, default=None, help="Rear-set sun tooth count")
    p.add_argument("--Nr-r", dest="Nr_r", type=int, default=None, help="Rear-set ring tooth count")
    p.add_argument("--Ns-m", dest="Ns_m", type=int, default=None, help="Middle-set sun tooth count")
    p.add_argument("--Nr-m", dest="Nr_m", type=int, default=None, help="Middle-set ring tooth count")
    return p



def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_presets:
        payload = {
            name: {
                "tooth_counts": dict(values),
                "note": PRESET_NOTES.get(name, ""),
            }
            for name, values in PRESETS.items()
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Available presets")
            print("------------------------------------------------------------")
            for name, data in payload.items():
                values = data["tooth_counts"]
                print(
                    f"{name}: Ns_f={values['Ns_f']}, Nr_f={values['Nr_f']}, "
                    f"Ns_r={values['Ns_r']}, Nr_r={values['Nr_r']}, "
                    f"Ns_m={values['Ns_m']}, Nr_m={values['Nr_m']}"
                )
                if data["note"]:
                    print(f"  note: {data['note']}")
        return 0

    tooth_counts: Dict[str, int] = {}
    try:
        tooth_counts = _resolve_tooth_counts(args)
        tx = MercedesW5A580FiveSpeedTransmission(**tooth_counts)
        normalized = MercedesW5A580FiveSpeedTransmission.normalize_state_name(args.state)

        if normalized == "all":
            results = tx.solve_all()
            if args.json:
                payload = {
                    "ok": True,
                    "preset": args.preset,
                    "preset_note": PRESET_NOTES.get(args.preset, ""),
                    "tooth_counts": tooth_counts,
                    "results": results,
                }
                if args.ratios_only:
                    payload = {
                        "ok": True,
                        "preset": args.preset,
                        "preset_note": PRESET_NOTES.get(args.preset, ""),
                        "tooth_counts": tooth_counts,
                        "ratios": {key: float(results[key]['ratio']) for key in tx.DISPLAY_ORDER},
                    }
                print(json.dumps(payload, indent=2))
                return 0
            if args.ratios_only:
                _print_tooth_counts(tooth_counts, preset=args.preset)
                _print_ratios_only(results, as_json=False)
                return 0
            _print_all(results, tooth_counts=tooth_counts, preset=args.preset)
            return 0

        result = tx.solve(normalized)
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
                "preset_note": PRESET_NOTES.get(args.preset, ""),
                "tooth_counts": tooth_counts,
                "result": result,
            }
            if args.ratios_only:
                payload = {
                    "ok": True,
                    "preset": args.preset,
                    "preset_note": PRESET_NOTES.get(args.preset, ""),
                    "tooth_counts": tooth_counts,
                    "state": result['state'],
                    "ratio": float(result['ratio']),
                }
            print(json.dumps(payload, indent=2))
            return 0

        if args.ratios_only:
            _print_tooth_counts(tooth_counts, preset=args.preset)
            print(f"{result['state']}: {float(result['ratio']):.6f}")
            return 0

        _print_single(result, tooth_counts=tooth_counts, preset=args.preset)
        return 0

    except FiveSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts or None)
    except Exception as exc:
        return _emit_cli_error(args=args, message=f"Unexpected runtime failure: {exc}", tooth_counts=tooth_counts or None)


if __name__ == "__main__":
    raise SystemExit(main())
