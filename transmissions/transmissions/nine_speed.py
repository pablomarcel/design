#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.nine_speed

Mercedes-Benz 9G-TRONIC / NAG3 9-speed transmission.

EXPERIMENTAL monolithic public-topology solve using the native core solver.

This file is a best-effort single global topology reconstruction using:
- RotatingMember
- PlanetaryGearSet
- Clutch
- Brake
- TransmissionSolver

Single source of truth
----------------------
This script follows the Mercedes manual stick diagram and clutch table as the
authoritative source.

Encoded monolithic topology
---------------------------
P1:
    sun     = input_s1
    carrier = c1
    ring    = r1_c2

P2:
    sun     = s2
    carrier = r1_c2
    ring    = r2_s3_s4

P3:
    sun     = r2_s3_s4
    carrier = output_c3
    ring    = r3

P4:
    sun     = r2_s3_s4
    carrier = input_s1
    ring    = r4

Shift elements encoded exactly as requested:
    A : brake  on s2
    B : brake  on r3
    C : brake  on c1
    D : clutch between output_c3 and r4
    E : clutch between c1 and r2_s3_s4
    F : clutch between input_s1 and c1

Important honesty note
----------------------
This is a true monolithic native-core solve attempt.
It does not use closed-form nomogram equations to generate the reported ratio.
It reports the raw core-solver result for the encoded global topology.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence

try:
    from ..core.clutch import Brake, Clutch, RotatingMember
    from ..core.planetary import PlanetaryGearSet
    from ..core.solver import TransmissionSolver
except Exception:  # pragma: no cover
    try:
        from core.clutch import Brake, Clutch, RotatingMember  # type: ignore
        from core.planetary import PlanetaryGearSet  # type: ignore
        from core.solver import TransmissionSolver  # type: ignore
    except Exception:  # pragma: no cover
        from clutch import Brake, Clutch, RotatingMember  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore
        from solver import TransmissionSolver  # type: ignore


class NineSpeedCliError(ValueError):
    """User-facing CLI/configuration error."""


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
    "mb_9gtronic_2013": "2013 public 9G-TRONIC tooth-count set.",
    "mb_9gtronic_2016": "2016 public 9G-TRONIC tooth-count set.",
}

SHIFT_SCHEDULE: Mapping[str, tuple[str, ...]] = {
    "1st": ("A", "B", "E"),
    "2nd": ("F", "E", "B"),
    "3rd": ("F", "A", "B"),
    "4th": ("A", "B", "D"),
    "5th": ("F", "A", "D"),
    "6th": ("F", "E", "D"),
    "7th": ("E", "A", "D"),
    "8th": ("C", "E", "D"),
    "9th": ("C", "A", "D"),
    "Rev": ("C", "A", "B"),
}

DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "Rev")
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

SPEED_KEYS: Sequence[str] = (
    "input_s1", "c1", "r1_c2", "s2", "r2_s3_s4", "r3", "r4", "output_c3"
)


@dataclass(frozen=True)
class SolveResult:
    state: str
    engaged: tuple[str, ...]
    ok: bool
    ratio: Optional[float]
    speeds: Dict[str, float]
    notes: str = ""
    solver_path: str = "core_v2_monolithic_public_topology"
    status: str = "ok"
    message: str = ""


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
            f"Invalid {label} tooth counts under strict geometry mode: (R - S) must be even."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    validator = _validate_counts_strict if strict_geometry else _validate_counts_basic
    for i in range(1, 5):
        validator(S=int(counts[f"S{i}"]), R=int(counts[f"R{i}"]), label=f"P{i}")


def _make_planetary(*, S: int, R: int, name: str, sun: RotatingMember, ring: RotatingMember, carrier: RotatingMember, strict_geometry: bool):
    geometry_mode = "strict" if strict_geometry else "relaxed"
    try:
        sig = inspect.signature(PlanetaryGearSet)
        if "geometry_mode" in sig.parameters:
            return PlanetaryGearSet(Ns=S, Nr=R, name=name, sun=sun, ring=ring, carrier=carrier, geometry_mode=geometry_mode)
    except Exception:
        pass
    return PlanetaryGearSet(Ns=S, Nr=R, name=name, sun=sun, ring=ring, carrier=carrier)


def _call_solve_report(solver: TransmissionSolver, *, input_member: str, input_speed: float = 1.0):
    if not hasattr(solver, "solve_report"):
        raise NineSpeedCliError("TransmissionSolver has no solve_report() method.")
    fn = getattr(solver, "solve_report")
    try:
        return fn(input_member=input_member, input_speed=input_speed)
    except TypeError:
        return fn(input_member, input_speed)


class MercedesNineSpeedMonolithic:
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
        validate_tooth_counts(counts, strict_geometry=bool(strict_geometry))
        self.counts = {k: int(v) for k, v in counts.items()}
        self.strict_geometry = bool(strict_geometry)
        self.preset_name = preset_name

    @staticmethod
    def normalize_state_name(name: str) -> str:
        key = name.strip().lower()
        if key == "all":
            return "all"
        if key not in STATE_ALIASES:
            valid = ", ".join(sorted(set(STATE_ALIASES.values())))
            raise NineSpeedCliError(f"Unknown state '{name}'. Valid states: {valid}, or 'all'.")
        return STATE_ALIASES[key]

    def _build_solver(self, engaged: Sequence[str]) -> TransmissionSolver:
        c = self.counts
        solver = TransmissionSolver()

        input_s1 = RotatingMember("input_s1")
        c1 = RotatingMember("c1")
        r1_c2 = RotatingMember("r1_c2")
        s2 = RotatingMember("s2")
        r2_s3_s4 = RotatingMember("r2_s3_s4")
        r3 = RotatingMember("r3")
        output_c3 = RotatingMember("output_c3")
        r4 = RotatingMember("r4")

        p1 = _make_planetary(S=c["S1"], R=c["R1"], name="P1", sun=input_s1, ring=r1_c2, carrier=c1, strict_geometry=self.strict_geometry)
        p2 = _make_planetary(S=c["S2"], R=c["R2"], name="P2", sun=s2, ring=r2_s3_s4, carrier=r1_c2, strict_geometry=self.strict_geometry)
        p3 = _make_planetary(S=c["S3"], R=c["R3"], name="P3", sun=r2_s3_s4, ring=r3, carrier=output_c3, strict_geometry=self.strict_geometry)
        p4 = _make_planetary(S=c["S4"], R=c["R4"], name="P4", sun=r2_s3_s4, ring=r4, carrier=input_s1, strict_geometry=self.strict_geometry)

        for g in (p1, p2, p3, p4):
            solver.add_gearset(g)

        A = Brake(s2, name="A")
        B = Brake(r3, name="B")
        C = Brake(c1, name="C")
        D = Clutch(output_c3, r4, name="D")
        E = Clutch(c1, r2_s3_s4, name="E")
        F = Clutch(input_s1, c1, name="F")

        for obj in (A, B, C):
            solver.add_brake(obj)
        for obj in (D, E, F):
            solver.add_clutch(obj)

        if "A" in engaged:
            A.engage()
        if "B" in engaged:
            B.engage()
        if "C" in engaged:
            C.engage()
        if "D" in engaged:
            D.engage()
        if "E" in engaged:
            E.engage()
        if "F" in engaged:
            F.engage()

        return solver

    def solve_state(self, state: str) -> SolveResult:
        key = self.normalize_state_name(state)
        engaged = SHIFT_SCHEDULE[key]
        solver = self._build_solver(engaged)
        report = _call_solve_report(solver, input_member="input_s1", input_speed=1.0)

        cls = getattr(report, "classification", None)
        status = getattr(cls, "status", "ok")
        message = getattr(cls, "message", "")
        speeds_raw = getattr(report, "member_speeds", {})
        speeds: Dict[str, float] = {k: float(speeds_raw[k]) for k in SPEED_KEYS if k in speeds_raw}

        ratio: Optional[float] = None
        if report.ok and "output_c3" in speeds and abs(speeds["output_c3"]) > 1.0e-12:
            ratio = 1.0 / speeds["output_c3"]

        return SolveResult(
            state=key,
            engaged=engaged,
            ok=bool(report.ok),
            ratio=ratio,
            speeds=speeds,
            notes="Experimental monolithic public-topology native-core solve.",
            solver_path="core_v2_monolithic_public_topology",
            status=status,
            message=message,
        )

    def solve_many(self, states: Sequence[str]) -> list[SolveResult]:
        return [self.solve_state(s) for s in states]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mercedes-Benz 9G-TRONIC / NAG3 monolithic public-topology native-core solve."
    )
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), default="mb_9gtronic_2013")
    parser.add_argument("--state", default="all", help="Gear state to solve: 1st..9th, Rev, or all")
    parser.add_argument("--strict-geometry", action="store_true", help="Require (R-S) even for each gearset.")
    parser.add_argument("--ratios-only", action="store_true", help="Print only state, status, and ratio.")
    parser.add_argument("--show-speeds", action="store_true", help="Show per-member solved speeds.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")
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


def _states_from_arg(model: MercedesNineSpeedMonolithic, state_arg: str) -> list[str]:
    if model.normalize_state_name(state_arg) == "all":
        return list(DISPLAY_ORDER)
    return [model.normalize_state_name(state_arg)]


def _print_text_summary(model: MercedesNineSpeedMonolithic, results: Sequence[SolveResult], *, ratios_only: bool, show_speeds: bool) -> None:
    c = model.counts
    print("Mercedes-Benz 9G-TRONIC / NAG3 9-Speed Kinematic Summary")
    print("-" * 156)
    print(
        f"Tooth counts: P1(S1={c['S1']}, R1={c['R1']}), P2(S2={c['S2']}, R2={c['R2']}), "
        f"P3(S3={c['S3']}, R3={c['R3']}), P4(S4={c['S4']}, R4={c['R4']})"
    )
    print(f"Geometry mode: {'strict' if model.strict_geometry else 'relaxed'}")
    print(f"Preset note: {PRESET_NOTES.get(model.preset_name, 'Custom tooth-count set.')}")
    print("Solver path: core_v2_monolithic_public_topology")
    print("-" * 156)

    if ratios_only:
        print(f"{'State':<8} {'Elems':<16} {'Status':<18} {'Ratio':>10}")
        print("-" * 60)
        for r in results:
            ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
            print(f"{r.state:<8} {'+'.join(r.engaged):<16} {r.status:<18} {ratio_txt}")
        return

    if show_speeds:
        header = (
            f"{'State':<8} {'Elems':<16} {'Status':<16} {'Ratio':>10} "
            f"{'input_s1':>10} {'c1':>10} {'r1_c2':>10} {'s2':>10} {'r2_s3_s4':>10} {'r3':>10} {'r4':>10} {'output_c3':>10}"
        )
        print(header)
        print("-" * len(header))
        for r in results:
            ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
            row = [
                f"{r.state:<8}",
                f"{'+'.join(r.engaged):<16}",
                f"{r.status:<16}",
                ratio_txt,
            ]
            for key in SPEED_KEYS:
                if key in r.speeds:
                    row.append(f"{r.speeds[key]:10.3f}")
                else:
                    row.append(f"{'-':>10}")
            print(" ".join(row))
    else:
        print(f"{'State':<8} {'Elems':<16} {'Status':<16} {'Ratio':>10}  {'Message'}")
        print("-" * 156)
        for r in results:
            ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
            print(f"{r.state:<8} {'+'.join(r.engaged):<16} {r.status:<16} {ratio_txt}  {r.message}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        counts = _merged_counts_from_args(args)
        model = MercedesNineSpeedMonolithic(
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
                "solver": "core_v2_monolithic_public_topology",
                "preset": args.preset,
                "geometry_mode": "strict" if args.strict_geometry else "relaxed",
                "counts": counts,
                "results": [
                    {
                        "state": r.state,
                        "engaged": list(r.engaged),
                        "ok": r.ok,
                        "status": r.status,
                        "message": r.message,
                        "ratio": r.ratio,
                        "speeds": dict(r.speeds),
                        "notes": r.notes,
                        "solver_path": r.solver_path,
                    }
                    for r in results
                ],
            }
            print(json.dumps(payload, indent=2))
        else:
            _print_text_summary(model, results, ratios_only=bool(args.ratios_only), show_speeds=bool(args.show_speeds))
        return 0
    except NineSpeedCliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
