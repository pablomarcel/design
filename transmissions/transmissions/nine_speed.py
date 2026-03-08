#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.nine_speed

Mercedes-Benz 9G-TRONIC / NAG3 9-speed transmission.

Native-core, powerflow-reduced kinematic model.

This file uses the project's native transmission core:
- RotatingMember
- PlanetaryGearSet
- Clutch
- Brake
- TransmissionSolver

Important honesty note
---------------------
This is a native-core solve path, but it is not yet a single monolithic public-
topology solve of the entire 9G train. Instead, each gear is solved as a
reduced native-core submodel derived from the stick diagram, clutch matrix, and
gear-by-gear powerflow interpretation.

That means:
- ratios come from TransmissionSolver.solve_report(...)
- no closed-form nomogram equations are used to print ratios
- each state is modeled with the active/counterheld members needed to close the
  kinematics cleanly in the common solver

Official public shift-element legend
------------------------------------
A : Brake blocking S2
B : Brake blocking R3
C : Brake blocking C1
D : Clutch coupling C3 with R4
E : Clutch coupling C1 with R2
F : Clutch coupling S1 with C1

Official application table used for reporting
---------------------------------------------
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

ALL_SPEED_KEYS: Sequence[str] = (
    "input", "c1", "r1_c2", "s2", "r2_s3_s4", "r3", "output"
)


@dataclass(frozen=True)
class SolveResult:
    state: str
    engaged: tuple[str, ...]
    ok: bool
    ratio: Optional[float]
    speeds: Dict[str, float]
    notes: str = ""
    solver_path: str = "core_v2_powerflow_reduced"
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
            f"Invalid {label} tooth counts under strict geometry mode: (R - S) must be even so the implied planet tooth count is an integer. "
            f"Got S={S}, R={R}, R-S={R - S}."
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
    if hasattr(solver, "solve_report"):
        fn = getattr(solver, "solve_report")
        try:
            return fn(input_member=input_member, input_speed=input_speed)
        except TypeError:
            return fn(input_member, input_speed)
    raise NineSpeedCliError("TransmissionSolver has no solve_report() method.")


def _ratio_from_report(report, *, output_member: str = "output") -> float:
    if not getattr(report, "ok", False):
        cls = getattr(report, "classification", None)
        status = getattr(cls, "status", "error")
        msg = getattr(cls, "message", "")
        raise NineSpeedCliError(f"Core solver failed: status={status} message={msg}")
    speeds = getattr(report, "member_speeds", {})
    if output_member not in speeds:
        raise NineSpeedCliError(f"Core solver did not report '{output_member}' speed.")
    w_out = float(speeds[output_member])
    if abs(w_out) < 1.0e-12:
        raise NineSpeedCliError("Output speed is zero; ratio undefined.")
    return 1.0 / w_out


class MercedesNineSpeedTransmission:
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

    def _new_solver(self) -> TransmissionSolver:
        return TransmissionSolver()

    @staticmethod
    def _m(name: str) -> RotatingMember:
        return RotatingMember(name)

    def _solve_1st(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        c1 = self._m("c1")
        x = self._m("r1_c2")
        s2 = self._m("s2")
        z = self._m("r2_s3_s4")
        r3 = self._m("r3")
        out = self._m("output")
        for g in (
            _make_planetary(S=c["S1"], R=c["R1"], name="P1", sun=inp, ring=x, carrier=c1, strict_geometry=self.strict_geometry),
            _make_planetary(S=c["S2"], R=c["R2"], name="P2", sun=s2, ring=z, carrier=x, strict_geometry=self.strict_geometry),
            _make_planetary(S=c["S3"], R=c["R3"], name="P3", sun=z, ring=r3, carrier=out, strict_geometry=self.strict_geometry),
        ):
            solver.add_gearset(g)
        B = Brake(r3, name="B")
        C = Brake(s2, name="C_reduced")
        E = Clutch(c1, z, name="E")
        B.engage(); C.engage(); E.engage()
        solver.add_brake(B); solver.add_brake(C); solver.add_clutch(E)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_2nd(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        r3 = self._m("r3")
        out = self._m("output")
        solver.add_gearset(_make_planetary(S=c["S3"], R=c["R3"], name="P3", sun=inp, ring=r3, carrier=out, strict_geometry=self.strict_geometry))
        B = Brake(r3, name="B_reduced")
        B.engage(); solver.add_brake(B)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_3rd(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        s2 = self._m("s2")
        z = self._m("r2_s3_s4")
        r3 = self._m("r3")
        out = self._m("output")
        solver.add_gearset(_make_planetary(S=c["S2"], R=c["R2"], name="P2", sun=s2, ring=z, carrier=inp, strict_geometry=self.strict_geometry))
        solver.add_gearset(_make_planetary(S=c["S3"], R=c["R3"], name="P3", sun=z, ring=r3, carrier=out, strict_geometry=self.strict_geometry))
        C = Brake(s2, name="C_reduced")
        B = Brake(r3, name="B")
        C.engage(); B.engage(); solver.add_brake(C); solver.add_brake(B)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_4th(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        z = self._m("r2_s3_s4")
        r3 = self._m("r3")
        out = self._m("output")
        solver.add_gearset(_make_planetary(S=c["S3"], R=c["R3"], name="P3", sun=z, ring=r3, carrier=out, strict_geometry=self.strict_geometry))
        solver.add_gearset(_make_planetary(S=c["S4"], R=c["R4"], name="P4", sun=z, ring=out, carrier=inp, strict_geometry=self.strict_geometry))
        B = Brake(r3, name="B")
        B.engage(); solver.add_brake(B)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_5th(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        s2 = self._m("s2")
        z = self._m("r2_s3_s4")
        out = self._m("output")
        solver.add_gearset(_make_planetary(S=c["S2"], R=c["R2"], name="P2", sun=s2, ring=z, carrier=inp, strict_geometry=self.strict_geometry))
        solver.add_gearset(_make_planetary(S=c["S4"], R=c["R4"], name="P4", sun=z, ring=out, carrier=inp, strict_geometry=self.strict_geometry))
        C = Brake(s2, name="C_reduced")
        C.engage(); solver.add_brake(C)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_6th(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        out = self._m("output")
        solver.add_gearset(_make_planetary(S=c["S4"], R=c["R4"], name="P4", sun=inp, ring=out, carrier=inp, strict_geometry=self.strict_geometry))
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_7th(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        c1 = self._m("c1")
        x = self._m("r1_c2")
        s2 = self._m("s2")
        z = self._m("r2_s3_s4")
        out = self._m("output")
        for g in (
            _make_planetary(S=c["S1"], R=c["R1"], name="P1", sun=inp, ring=x, carrier=c1, strict_geometry=self.strict_geometry),
            _make_planetary(S=c["S2"], R=c["R2"], name="P2", sun=s2, ring=z, carrier=x, strict_geometry=self.strict_geometry),
            _make_planetary(S=c["S4"], R=c["R4"], name="P4", sun=z, ring=out, carrier=inp, strict_geometry=self.strict_geometry),
        ):
            solver.add_gearset(g)
        C = Brake(s2, name="C_reduced")
        E = Clutch(c1, z, name="E")
        C.engage(); E.engage(); solver.add_brake(C); solver.add_clutch(E)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_8th(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        z = self._m("r2_s3_s4")
        out = self._m("output")
        solver.add_gearset(_make_planetary(S=c["S4"], R=c["R4"], name="P4", sun=z, ring=out, carrier=inp, strict_geometry=self.strict_geometry))
        A = Brake(z, name="A_reduced")
        A.engage(); solver.add_brake(A)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_9th(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        c1 = self._m("c1")
        x = self._m("r1_c2")
        s2 = self._m("s2")
        z = self._m("r2_s3_s4")
        out = self._m("output")
        for g in (
            _make_planetary(S=c["S1"], R=c["R1"], name="P1", sun=inp, ring=x, carrier=c1, strict_geometry=self.strict_geometry),
            _make_planetary(S=c["S2"], R=c["R2"], name="P2", sun=s2, ring=z, carrier=x, strict_geometry=self.strict_geometry),
            _make_planetary(S=c["S4"], R=c["R4"], name="P4", sun=z, ring=out, carrier=inp, strict_geometry=self.strict_geometry),
        ):
            solver.add_gearset(g)
        A = Brake(c1, name="A_syn_C1_hold")
        C = Brake(s2, name="C_reduced")
        A.engage(); C.engage(); solver.add_brake(A); solver.add_brake(C)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def _solve_rev(self):
        c = self.counts
        solver = self._new_solver()
        inp = self._m("input")
        c1 = self._m("c1")
        x = self._m("r1_c2")
        s2 = self._m("s2")
        z = self._m("r2_s3_s4")
        r3 = self._m("r3")
        out = self._m("output")
        for g in (
            _make_planetary(S=c["S1"], R=c["R1"], name="P1", sun=inp, ring=x, carrier=c1, strict_geometry=self.strict_geometry),
            _make_planetary(S=c["S2"], R=c["R2"], name="P2", sun=s2, ring=z, carrier=x, strict_geometry=self.strict_geometry),
            _make_planetary(S=c["S3"], R=c["R3"], name="P3", sun=z, ring=r3, carrier=out, strict_geometry=self.strict_geometry),
        ):
            solver.add_gearset(g)
        A = Brake(c1, name="A_syn_C1_hold")
        C = Brake(s2, name="C_reduced")
        B = Brake(r3, name="B")
        A.engage(); B.engage(); C.engage(); solver.add_brake(A); solver.add_brake(B); solver.add_brake(C)
        return _call_solve_report(solver, input_member="input", input_speed=1.0)

    def solve_state(self, state: str) -> SolveResult:
        key = self.normalize_state_name(state)
        if key == "1st":
            report = self._solve_1st(); note = "Native-core reduced solve: front reduction + gearset-3 reduction."
        elif key == "2nd":
            report = self._solve_2nd(); note = "Native-core reduced solve: pure gearset-3 reduction."
        elif key == "3rd":
            report = self._solve_3rd(); note = "Native-core reduced solve: gearset-2 increase + gearset-3 reduction."
        elif key == "4th":
            report = self._solve_4th(); note = "Native-core reduced solve: gearset-3 reduction feeding gearset-4."
        elif key == "5th":
            report = self._solve_5th(); note = "Native-core reduced solve: gearset-2 increase feeding gearset-4."
        elif key == "6th":
            report = self._solve_6th(); note = "Native-core reduced solve: direct drive."
        elif key == "7th":
            report = self._solve_7th(); note = "Native-core reduced solve: front reduction counterholding gearset-4."
        elif key == "8th":
            report = self._solve_8th(); note = "Native-core reduced solve: pure gearset-4 overdrive."
        elif key == "9th":
            report = self._solve_9th(); note = "Native-core reduced solve: front counterhold feeding gearset-4 overdrive."
        elif key == "Rev":
            report = self._solve_rev(); note = "Native-core reduced solve: front counterhold feeding gearset-3 reverse."
        else:
            raise NineSpeedCliError(f"Unknown state: {state}")

        ratio = _ratio_from_report(report, output_member="output")
        cls = getattr(report, "classification", None)
        status = getattr(cls, "status", "ok")
        msg = getattr(cls, "message", "")
        speeds = {k: float(v) for k, v in getattr(report, "member_speeds", {}).items()}
        return SolveResult(
            state=key,
            engaged=SHIFT_SCHEDULE[key],
            ratio=ratio,
            ok=True,
            speeds=speeds,
            solver_path="core_v2_powerflow_reduced",
            status=status,
            message=msg,
            notes=note,
        )

    def solve_many(self, states: Sequence[str]) -> list[SolveResult]:
        return [self.solve_state(s) for s in states]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mercedes-Benz 9G-TRONIC / NAG3 9-speed native-core powerflow-reduced kinematic model."
    )
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), default="mb_9gtronic_2013")
    parser.add_argument("--state", default="all", help="Gear state to solve: 1st..9th, Rev, or all")
    parser.add_argument("--strict-geometry", action="store_true", help="Require (R-S) even for each gearset.")
    parser.add_argument("--ratios-only", action="store_true", help="Print only state and ratio columns.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text table.")
    parser.add_argument("--verbose-report", action="store_true", help="Print note column as well.")
    parser.add_argument("--show-speeds", action="store_true", help="Print reduced-state member speeds like 8HP/10R reports.")
    for i in range(1, 5):
        parser.add_argument(f"--S{i}", type=int, default=None, help=f"Override sun tooth count for P{i}")
        parser.add_argument(f"--R{i}", type=int, default=None, help=f"Override ring tooth count for P{i}")
    return parser


def _merged_counts_from_args(args: argparse.Namespace) -> Dict[str, int]:
    counts = dict(PRESETS[args.preset])
    for i in range(1, 5):
        sval = getattr(args, f"S{i}")
        rval = getattr(args, f"R{i}")
        if sval is not None:
            counts[f"S{i}"] = int(sval)
        if rval is not None:
            counts[f"R{i}"] = int(rval)
    return counts


def _states_from_arg(model: MercedesNineSpeedTransmission, state_arg: str) -> list[str]:
    if model.normalize_state_name(state_arg) == "all":
        return list(DISPLAY_ORDER)
    return [model.normalize_state_name(state_arg)]


def _result_to_json_obj(result: SolveResult) -> Dict[str, object]:
    return {
        "state": result.state,
        "engaged": list(result.engaged),
        "ok": result.ok,
        "ratio": result.ratio,
        "speeds": dict(result.speeds),
        "notes": result.notes,
        "solver_path": result.solver_path,
        "status": result.status,
        "message": result.message,
    }


def _format_speed(result: SolveResult, key: str) -> str:
    if key not in result.speeds:
        return "-"
    return f"{result.speeds[key]:.3f}"


def _print_text_summary(model: MercedesNineSpeedTransmission, results: Sequence[SolveResult], *, ratios_only: bool, verbose_report: bool, show_speeds: bool) -> None:
    c = model.counts
    print("Mercedes-Benz 9G-TRONIC / NAG3 9-Speed Kinematic Summary")
    print("-" * 156)
    print(
        f"Tooth counts: P1(S1={c['S1']}, R1={c['R1']}), P2(S2={c['S2']}, R2={c['R2']}), "
        f"P3(S3={c['S3']}, R3={c['R3']}), P4(S4={c['S4']}, R4={c['R4']})"
    )
    print(f"Geometry mode: {'strict' if model.strict_geometry else 'relaxed'}")
    print(f"Preset note: {PRESET_NOTES.get(model.preset_name, 'Custom tooth-count set.')}")
    print("Solver path: core_v2_powerflow_reduced")
    print("-" * 156)

    if ratios_only:
        print(f"{'State':<8} {'Ratio':>10}")
        print("-" * 20)
        for r in results:
            ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
            print(f"{r.state:<8} {ratio_txt}")
        return

    if show_speeds:
        print(
            f"{'State':<8} {'Elems':<16} {'Ratio':>10}  {'Input':>8} {'c1':>8} {'r1_c2':>8} {'s2':>8} {'r2_s3_s4':>10} {'r3':>8} {'Output':>8}"
        )
        print("-" * 156)
        for r in results:
            ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
            print(
                f"{r.state:<8} {'+'.join(r.engaged):<16} {ratio_txt}  "
                f"{_format_speed(r,'input'):>8} {_format_speed(r,'c1'):>8} {_format_speed(r,'r1_c2'):>8} {_format_speed(r,'s2'):>8} {_format_speed(r,'r2_s3_s4'):>10} {_format_speed(r,'r3'):>8} {_format_speed(r,'output'):>8}"
            )
        return

    if verbose_report:
        print(f"{'State':<8} {'Elems':<16} {'Ratio':>10}  {'Notes'}")
        print("-" * 156)
        for r in results:
            ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
            print(f"{r.state:<8} {'+'.join(r.engaged):<16} {ratio_txt}  {r.notes}")
    else:
        print(f"{'State':<8} {'Elems':<16} {'Ratio':>10}")
        print("-" * 40)
        for r in results:
            ratio_txt = "-" if r.ratio is None else f"{r.ratio:10.3f}"
            print(f"{r.state:<8} {'+'.join(r.engaged):<16} {ratio_txt}")


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
                "solver": "core_v2_powerflow_reduced",
                "preset": args.preset,
                "geometry_mode": "strict" if args.strict_geometry else "relaxed",
                "counts": counts,
                "results": [_result_to_json_obj(r) for r in results],
            }
            print(json.dumps(payload, indent=2))
        else:
            _print_text_summary(
                model,
                results,
                ratios_only=bool(args.ratios_only),
                verbose_report=bool(args.verbose_report),
                show_speeds=bool(args.show_speeds),
            )
        return 0
    except NineSpeedCliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
