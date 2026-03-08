#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.nine_speed

Mercedes-Benz 9G-TRONIC / NAG3 9-speed automatic transmission ratio model.

Important honesty note
----------------------
This script is intentionally implemented as a closed-form kinematic ratio model
based on the public 9G-Tronic nomogram / gear-ratio formulas and shift-element
legend, plus the service-manual 1st-gear power-flow description.

It is NOT yet a full reusable-core TransmissionSolver reconstruction like the
best simple-planetary scripts in this project. The reason is that the public
stick diagram / nomogram material gives an excellent shift matrix, gear-tooth
sets, and exact closed-form ratios, but the permanent hard-part topology is not
as unambiguous from the public sources as the 8HP or 10R cases.

What this script does very well
-------------------------------
- reproduces the published 9G-Tronic ratio family exactly for the public tooth
  counts
- supports tooth-count overrides from the CLI
- supports known 2013 and 2016 public tooth-count variants
- prints a clean summary with shift-element applications

Public reference interpretation used here
-----------------------------------------
Shift elements:
    A : brake on S2
    B : brake on R3
    C : brake on C1
    D : clutch coupling C3 <-> R4
    E : clutch coupling C1 <-> R2
    F : clutch coupling S1 <-> C1

Shift schedule used:
    1st : B + C + E
    2nd : C + D + E
    3rd : B + C + D
    4th : B + C + F
    5th : B + D + F
    6th : D + E + F
    7th : B + E + F
    8th : A + E + F
    9th : A + B + F
    Rev : A + B + C

Closed-form ratio equations used
--------------------------------
For 2013 public tooth counts (S1=46,R1=98,S2=44,R2=100,S3=36,R3=84,S4=34,R4=86),
these equations reproduce the published ratios exactly.

Odd gears:
    1st = ((S1*(S2+R2) + R1*S2) * (S3+R3)) / (S1*(S2+R2)*S3)
    3rd = (R2*(S3+R3)) / ((S2+R2)*S3)
    5th = (R2*R4) / (R2*R4 - S2*S4)
    7th = (R4*(S1*(S2+R2) + R1*S2)) / (S1*R4*(S2+R2) + R1*S2*(S4+R4))
    9th = (R1*R2*R4) / (((R1*R2) + S1*(S2+R2))*S4 + R1*R2*R4)

Even gears + reverse:
    2nd = (S3+R3) / S3
    4th = (S4*(S3+R3) + S3*R4) / (S3*(S4+R4))
    6th = 1
    8th = R4 / (S4+R4)
    Rev = -(R1*R2*(S3+R3)) / (S1*(S2+R2)*S3)

This script treats those equations as the authoritative public kinematic model
for the 9G-Tronic ratio family.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence


class NineSpeedCliError(ValueError):
    """User-facing CLI/configuration error for nine_speed.py."""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    "S1": 46,
    "R1": 98,
    "S2": 44,
    "R2": 100,
    "S3": 36,
    "R3": 84,
    "S4": 34,
    "R4": 86,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "mb_9gtronic_2013": dict(DEFAULT_TOOTH_COUNTS),
    "mb_9gtronic_2016": {
        "S1": 46,
        "R1": 98,
        "S2": 44,
        "R2": 100,
        "S3": 37,
        "R3": 83,
        "S4": 34,
        "R4": 86,
    },
}

PRESET_NOTES: Mapping[str, str] = {
    "mb_9gtronic_2013": (
        "2013 public 9G-TRONIC tooth-count set from the published nomogram / ratio table family."
    ),
    "mb_9gtronic_2016": (
        "2016 public 9G-TRONIC tooth-count set from the published nomogram / ratio table family."
    ),
}


@dataclass(frozen=True)
class GearState:
    name: str
    engaged: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class SolveResult:
    state: str
    engaged: tuple[str, ...]
    ok: bool
    ratio: Optional[float]
    notes: str = ""
    solver_path: str = "closed_form_nomogram"
    status: str = "ok"
    message: str = ""


STATE_ALIASES: Mapping[str, str] = {
    "1": "1st", "1st": "1st", "first": "1st",
    "2": "2nd", "2nd": "2nd", "second": "2nd",
    "3": "3rd", "3rd": "3rd", "third": "3rd",
    "4": "4th", "4th": "4th", "fourth": "4th",
    "5": "5th", "5th": "5th", "fifth": "5th",
    "6": "6th", "6th": "6th", "sixth": "6th",
    "7": "7th", "7th": "7th", "seventh": "7th",
    "8": "8th", "8th": "8th", "eighth": "8th",
    "9": "9th", "9th": "9th", "ninth": "9th",
    "r": "Rev", "rev": "Rev", "reverse": "Rev",
}


def _validate_counts_basic(*, S: int, R: int, label: str) -> None:
    if S <= 0 or R <= 0:
        raise NineSpeedCliError(f"Invalid {label} tooth counts: S and R must both be positive integers.")
    if R <= S:
        raise NineSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth R ({R}) must be greater than sun gear teeth S ({S})."
        )


def _validate_counts_strict(*, S: int, R: int, label: str) -> None:
    _validate_counts_basic(S=S, R=R, label=label)
    if (R - S) % 2 != 0:
        raise NineSpeedCliError(
            f"Invalid {label} tooth counts under strict geometry mode: (R - S) must be even so the implied "
            f"planet tooth count is an integer. Got S={S}, R={R}, R-S={R - S}."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    validator = _validate_counts_strict if strict_geometry else _validate_counts_basic
    for i in range(1, 5):
        validator(S=int(counts[f"S{i}"]), R=int(counts[f"R{i}"]), label=f"P{i}")


def _safe_div(num: float, den: float, *, label: str) -> float:
    if abs(den) < 1e-12:
        raise NineSpeedCliError(f"Degenerate tooth-count set for {label}: denominator is zero.")
    return num / den


class MercedesNineSpeedTransmission:
    """Closed-form public ratio model for the Mercedes 9G-TRONIC / NAG3."""

    SHIFT_SCHEDULE: Mapping[str, tuple[str, ...]] = {
        "1st": ("B", "C", "E"),
        "2nd": ("C", "D", "E"),
        "3rd": ("B", "C", "D"),
        "4th": ("B", "C", "F"),
        "5th": ("B", "D", "F"),
        "6th": ("D", "E", "F"),
        "7th": ("B", "E", "F"),
        "8th": ("A", "E", "F"),
        "9th": ("A", "B", "F"),
        "Rev": ("A", "B", "C"),
    }
    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "Rev")

    def __init__(
        self,
        *,
        S1: int,
        R1: int,
        S2: int,
        R2: int,
        S3: int,
        R3: int,
        S4: int,
        R4: int,
        strict_geometry: bool = False,
        preset_name: str = "mb_9gtronic_2013",
    ) -> None:
        counts = {"S1": S1, "R1": R1, "S2": S2, "R2": R2, "S3": S3, "R3": R3, "S4": S4, "R4": R4}
        validate_tooth_counts(counts, strict_geometry=strict_geometry)
        self.counts = counts
        self.strict_geometry = bool(strict_geometry)
        self.preset_name = preset_name

        self.states: Dict[str, GearState] = {
            name: GearState(name=name, engaged=tuple(elems))
            for name, elems in self.SHIFT_SCHEDULE.items()
        }

    def _ratio_1st(self) -> float:
        S1, R1, S2, R2, S3, R3 = self.counts["S1"], self.counts["R1"], self.counts["S2"], self.counts["R2"], self.counts["S3"], self.counts["R3"]
        num = (S1 * (S2 + R2) + R1 * S2) * (S3 + R3)
        den = S1 * (S2 + R2) * S3
        return _safe_div(num, den, label="1st gear")

    def _ratio_2nd(self) -> float:
        S3, R3 = self.counts["S3"], self.counts["R3"]
        return _safe_div(S3 + R3, S3, label="2nd gear")

    def _ratio_3rd(self) -> float:
        S2, R2, S3, R3 = self.counts["S2"], self.counts["R2"], self.counts["S3"], self.counts["R3"]
        num = R2 * (S3 + R3)
        den = (S2 + R2) * S3
        return _safe_div(num, den, label="3rd gear")

    def _ratio_4th(self) -> float:
        S3, R3, S4, R4 = self.counts["S3"], self.counts["R3"], self.counts["S4"], self.counts["R4"]
        num = S4 * (S3 + R3) + S3 * R4
        den = S3 * (S4 + R4)
        return _safe_div(num, den, label="4th gear")

    def _ratio_5th(self) -> float:
        S2, R2, S4, R4 = self.counts["S2"], self.counts["R2"], self.counts["S4"], self.counts["R4"]
        num = R2 * R4
        den = R2 * R4 - S2 * S4
        return _safe_div(num, den, label="5th gear")

    def _ratio_6th(self) -> float:
        return 1.0

    def _ratio_7th(self) -> float:
        S1, R1, S2, R2, S4, R4 = self.counts["S1"], self.counts["R1"], self.counts["S2"], self.counts["R2"], self.counts["S4"], self.counts["R4"]
        num = R4 * (S1 * (S2 + R2) + R1 * S2)
        den = S1 * R4 * (S2 + R2) + R1 * S2 * (S4 + R4)
        return _safe_div(num, den, label="7th gear")

    def _ratio_8th(self) -> float:
        S4, R4 = self.counts["S4"], self.counts["R4"]
        return _safe_div(R4, S4 + R4, label="8th gear")

    def _ratio_9th(self) -> float:
        S1, R1, S2, R2, S4, R4 = self.counts["S1"], self.counts["R1"], self.counts["S2"], self.counts["R2"], self.counts["S4"], self.counts["R4"]
        num = R1 * R2 * R4
        den = ((R1 * R2) + S1 * (S2 + R2)) * S4 + R1 * R2 * R4
        return _safe_div(num, den, label="9th gear")

    def _ratio_rev(self) -> float:
        S1, R1, S2, R2, S3, R3 = self.counts["S1"], self.counts["R1"], self.counts["S2"], self.counts["R2"], self.counts["S3"], self.counts["R3"]
        num = -(R1 * R2 * (S3 + R3))
        den = S1 * (S2 + R2) * S3
        return _safe_div(num, den, label="Reverse gear")

    def ratio_for_state(self, state: str) -> float:
        key = self.normalize_state_name(state)
        if key == "1st":
            return self._ratio_1st()
        if key == "2nd":
            return self._ratio_2nd()
        if key == "3rd":
            return self._ratio_3rd()
        if key == "4th":
            return self._ratio_4th()
        if key == "5th":
            return self._ratio_5th()
        if key == "6th":
            return self._ratio_6th()
        if key == "7th":
            return self._ratio_7th()
        if key == "8th":
            return self._ratio_8th()
        if key == "9th":
            return self._ratio_9th()
        if key == "Rev":
            return self._ratio_rev()
        raise NineSpeedCliError(f"Unknown state: {state}")

    def solve_state(self, state: str) -> SolveResult:
        key = self.normalize_state_name(state)
        gs = self.states[key]
        ratio = self.ratio_for_state(key)
        return SolveResult(
            state=key,
            engaged=gs.engaged,
            ok=True,
            ratio=float(ratio),
            notes="Closed-form public nomogram / ratio-family equation.",
            solver_path="closed_form_nomogram",
            status="ok",
            message="Ratio computed from published 9G-Tronic closed-form kinematic equations.",
        )

    def solve_many(self, states: Sequence[str]) -> list[SolveResult]:
        return [self.solve_state(s) for s in states]

    @staticmethod
    def normalize_state_name(name: str) -> str:
        key = name.strip().lower()
        if key == "all":
            return "all"
        if key not in STATE_ALIASES:
            valid = ", ".join(sorted(set(STATE_ALIASES.values())))
            raise NineSpeedCliError(f"Unknown state '{name}'. Valid states: {valid}, or 'all'.")
        return STATE_ALIASES[key]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mercedes-Benz 9G-TRONIC / NAG3 9-speed ratio model using public closed-form formulas."
        )
    )
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), default="mb_9gtronic_2013")
    parser.add_argument("--state", default="all", help="Gear state to solve: 1st..9th, Rev, or all")
    parser.add_argument("--strict-geometry", action="store_true", help="Require (R-S) even for each gearset.")
    parser.add_argument("--ratios-only", action="store_true", help="Print only state and ratio columns.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text table.")

    for i in range(1, 5):
        parser.add_argument(f"--S{i}", type=int, default=None, help=f"Override sun tooth count for P{i}")
        parser.add_argument(f"--R{i}", type=int, default=None, help=f"Override ring tooth count for P{i}")
    return parser


def _merged_counts_from_args(args: argparse.Namespace) -> Dict[str, int]:
    counts = dict(PRESETS[args.preset])
    for i in range(1, 5):
        s_attr = getattr(args, f"S{i}")
        r_attr = getattr(args, f"R{i}")
        if s_attr is not None:
            counts[f"S{i}"] = int(s_attr)
        if r_attr is not None:
            counts[f"R{i}"] = int(r_attr)
    return counts


def _states_from_arg(model: MercedesNineSpeedTransmission, state_arg: str) -> list[str]:
    if model.normalize_state_name(state_arg) == "all":
        return list(model.DISPLAY_ORDER)
    return [model.normalize_state_name(state_arg)]


def _result_to_json_obj(result: SolveResult) -> Dict[str, object]:
    return {
        "state": result.state,
        "engaged": list(result.engaged),
        "ok": result.ok,
        "ratio": result.ratio,
        "notes": result.notes,
        "solver_path": result.solver_path,
        "status": result.status,
        "message": result.message,
    }


def _print_text_summary(model: MercedesNineSpeedTransmission, results: Sequence[SolveResult], *, ratios_only: bool) -> None:
    c = model.counts
    print("Mercedes-Benz 9G-TRONIC / NAG3 9-Speed Kinematic Summary")
    print("-" * 118)
    print(
        f"Tooth counts: P1(S1={c['S1']}, R1={c['R1']}), P2(S2={c['S2']}, R2={c['R2']}), "
        f"P3(S3={c['S3']}, R3={c['R3']}), P4(S4={c['S4']}, R4={c['R4']})"
    )
    print(f"Geometry mode: {'strict' if model.strict_geometry else 'relaxed'}")
    print(f"Preset note: {PRESET_NOTES.get(model.preset_name, 'Custom tooth-count set.')}")
    print("Solver path: closed_form_nomogram")
    print("-" * 118)

    if ratios_only:
        print(f"{'State':<8} {'Ratio':>10}")
        print("-" * 20)
        for r in results:
            ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
            print(f"{r.state:<8} {ratio_txt}")
        return

    print(f"{'State':<8} {'Elems':<16} {'Ratio':>10}  {'Notes'}")
    print("-" * 118)
    for r in results:
        elems = "+".join(r.engaged)
        ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
        print(f"{r.state:<8} {elems:<16} {ratio_txt}  {r.notes}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        counts = _merged_counts_from_args(args)
        model = MercedesNineSpeedTransmission(
            S1=counts["S1"], R1=counts["R1"],
            S2=counts["S2"], R2=counts["R2"],
            S3=counts["S3"], R3=counts["R3"],
            S4=counts["S4"], R4=counts["R4"],
            strict_geometry=bool(args.strict_geometry),
            preset_name=args.preset,
        )
        states = _states_from_arg(model, args.state)
        results = model.solve_many(states)

        if args.json:
            payload = {
                "ok": True,
                "solver": "closed_form_nomogram",
                "preset": args.preset,
                "geometry_mode": "strict" if args.strict_geometry else "relaxed",
                "counts": counts,
                "results": [_result_to_json_obj(r) for r in results],
            }
            print(json.dumps(payload, indent=2))
        else:
            _print_text_summary(model, results, ratios_only=bool(args.ratios_only))
        return 0

    except NineSpeedCliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
