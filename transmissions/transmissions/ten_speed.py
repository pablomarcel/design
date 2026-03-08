#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.ten_speed

Ford 10R80 / 10R family 10-speed automatic transmission kinematic model.

This implementation uses the shared core classes and TransmissionSolver.
It is a kinematic reconstruction from the patent/article-style stick diagram and
per-gear power-flow narrative, not an OEM hydraulic or torque model.

Modeled topology
----------------
The four simple planetary sets are represented with shared rotating nodes:

    input       : transmission input shaft = P2 carrier
    r1          : P1 ring
    s12         : P1 sun = P2 sun
    r4c1        : P4 ring = P1 carrier
    r2s3        : P2 ring = P3 sun
    r3s4        : P3 ring = P4 sun
    interm      : intermediate shaft
    p3c         : P3 carrier
    output      : P4 carrier = output shaft

Planetary relations
-------------------
P1: Ns1 * (w_s12  - w_r4c1) + Nr1 * (w_r1   - w_r4c1) = 0
P2: Ns2 * (w_s12  - w_input) + Nr2 * (w_r2s3 - w_input) = 0
P3: Ns3 * (w_r2s3 - w_p3c)   + Nr3 * (w_r3s4 - w_p3c) = 0
P4: Ns4 * (w_r3s4 - w_output)+ Nr4 * (w_r4c1 - w_output) = 0

Shift-element interpretation used here
--------------------------------------
A : grounds P1 ring                                -> r1 -> ground
B : grounds common P1/P2 sun node                  -> s12 -> ground
C : ties P2 ring / P3 sun to intermediate shaft    -> r2s3 <-> interm
D : ties P3 carrier to intermediate shaft          -> p3c  <-> interm
E : drives P3 ring / P4 sun from input             -> input <-> r3s4
F : ties P1 carrier / P4 ring to intermediate      -> r4c1 <-> interm

Important note on E and F
-------------------------
The plain-language article summary around E/F is internally inconsistent in one
place. This script follows the per-gear power-flow descriptions and the ratios,
which require:

- E to drive the P3-ring / P4-sun node from input
- F to connect the intermediate shaft to the P1-carrier / P4-ring node

That interpretation reproduces the published ratio set for the cited tooth counts.

Shift schedule used
-------------------
1st  : A + B + D + E
2nd  : A + B + C + D
3rd  : A + C + D + E
4th  : A + C + D + F
5th  : A + C + E + F
6th  : A + D + E + F
7th  : C + D + E + F
8th  : B + D + E + F
9th  : B + C + E + F
10th : B + C + D + F
Rev  : A + B + D + F

Default tooth counts
--------------------
Estimated set from the patent/article summary:
- P1: S1=45, R1=99
- P2: S2=51, R2=89
- P3: S3=63, R3=101
- P4: S4=23, R4=85
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence

import sympy as sp

try:
    from ..core.clutch import Brake, Clutch, RotatingMember
    from ..core.planetary import PlanetaryGearSet
    from ..core.solver import TransmissionSolver, TransmissionSolverError
except Exception:  # pragma: no cover
    try:
        from core.clutch import Brake, Clutch, RotatingMember  # type: ignore
        from core.planetary import PlanetaryGearSet  # type: ignore
        from core.solver import TransmissionSolver, TransmissionSolverError  # type: ignore
    except Exception:  # pragma: no cover
        from clutch import Brake, Clutch, RotatingMember  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore
        from solver import TransmissionSolver, TransmissionSolverError  # type: ignore


class TenSpeedCliError(ValueError):
    """User-facing CLI/configuration error for ten_speed.py."""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    "Ns1": 45,
    "Nr1": 99,
    "Ns2": 51,
    "Nr2": 89,
    "Ns3": 63,
    "Nr3": 101,
    "Ns4": 23,
    "Nr4": 85,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "ford_10r80_estimated": dict(DEFAULT_TOOTH_COUNTS),
}

PRESET_NOTES: Mapping[str, str] = {
    "ford_10r80_estimated": (
        "Estimated tooth-count set from the patent/article-style 10R80 saturation dive; "
        "not claimed as OEM-confirmed tooth data."
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
    speeds: Dict[str, float]
    notes: str = ""
    solver_path: str = "core_v2"
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
    "10": "10th", "10th": "10th", "tenth": "10th",
    "r": "Rev", "rev": "Rev", "reverse": "Rev",
}


def _validate_counts_basic(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise TenSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise TenSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )


def _validate_counts_strict(*, Ns: int, Nr: int, label: str) -> None:
    _validate_counts_basic(Ns=Ns, Nr=Nr, label=label)
    if (Nr - Ns) % 2 != 0:
        raise TenSpeedCliError(
            f"Invalid {label} tooth counts under strict geometry mode: (Nr - Ns) must be even so the implied "
            f"planet tooth count is an integer. Got Ns={Ns}, Nr={Nr}, Nr-Ns={Nr - Ns}."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    validator = _validate_counts_strict if strict_geometry else _validate_counts_basic
    for i in range(1, 5):
        validator(Ns=int(counts[f"Ns{i}"]), Nr=int(counts[f"Nr{i}"]), label=f"P{i}")


def _make_planetary(
    *,
    Ns: int,
    Nr: int,
    name: str,
    sun: RotatingMember,
    ring: RotatingMember,
    carrier: RotatingMember,
    strict_geometry: bool,
):
    geometry_mode = "strict" if strict_geometry else "relaxed"
    try:
        sig = inspect.signature(PlanetaryGearSet)
        if "geometry_mode" in sig.parameters:
            return PlanetaryGearSet(
                Ns=Ns,
                Nr=Nr,
                name=name,
                sun=sun,
                ring=ring,
                carrier=carrier,
                geometry_mode=geometry_mode,
            )
    except Exception:
        pass
    return PlanetaryGearSet(Ns=Ns, Nr=Nr, name=name, sun=sun, ring=ring, carrier=carrier)


class Ford10RTenSpeedTransmission:
    """Ford 10R family kinematic model solved through the shared core stack."""

    SHIFT_SCHEDULE: Mapping[str, tuple[str, ...]] = {
        "1st": ("A", "B", "D", "E"),
        "2nd": ("A", "B", "C", "D"),
        "3rd": ("A", "C", "D", "E"),
        "4th": ("A", "C", "D", "F"),
        "5th": ("A", "C", "E", "F"),
        "6th": ("A", "D", "E", "F"),
        "7th": ("C", "D", "E", "F"),
        "8th": ("B", "D", "E", "F"),
        "9th": ("B", "C", "E", "F"),
        "10th": ("B", "C", "D", "F"),
        "Rev": ("A", "B", "D", "F"),
    }
    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "Rev")

    def __init__(
        self,
        *,
        Ns1: int,
        Nr1: int,
        Ns2: int,
        Nr2: int,
        Ns3: int,
        Nr3: int,
        Ns4: int,
        Nr4: int,
        strict_geometry: bool = False,
    ) -> None:
        self.strict_geometry = bool(strict_geometry)
        self.tooth_counts: Dict[str, int] = {
            "Ns1": int(Ns1), "Nr1": int(Nr1),
            "Ns2": int(Ns2), "Nr2": int(Nr2),
            "Ns3": int(Ns3), "Nr3": int(Nr3),
            "Ns4": int(Ns4), "Nr4": int(Nr4),
        }
        self._build_topology(**self.tooth_counts)

    def _build_topology(self, *, Ns1: int, Nr1: int, Ns2: int, Nr2: int, Ns3: int, Nr3: int, Ns4: int, Nr4: int) -> None:
        self.input = RotatingMember("input")
        self.r1 = RotatingMember("r1")
        self.s12 = RotatingMember("s12")
        self.r4c1 = RotatingMember("r4c1")
        self.r2s3 = RotatingMember("r2s3")
        self.r3s4 = RotatingMember("r3s4")
        self.interm = RotatingMember("interm")
        self.p3c = RotatingMember("p3c")
        self.output = RotatingMember("output")

        self.members: Dict[str, RotatingMember] = {
            "input": self.input,
            "r1": self.r1,
            "s12": self.s12,
            "r4c1": self.r4c1,
            "r2s3": self.r2s3,
            "r3s4": self.r3s4,
            "interm": self.interm,
            "p3c": self.p3c,
            "output": self.output,
        }

        self.pg1 = _make_planetary(Ns=Ns1, Nr=Nr1, name="P1", sun=self.s12, ring=self.r1, carrier=self.r4c1, strict_geometry=self.strict_geometry)
        self.pg2 = _make_planetary(Ns=Ns2, Nr=Nr2, name="P2", sun=self.s12, ring=self.r2s3, carrier=self.input, strict_geometry=self.strict_geometry)
        self.pg3 = _make_planetary(Ns=Ns3, Nr=Nr3, name="P3", sun=self.r2s3, ring=self.r3s4, carrier=self.p3c, strict_geometry=self.strict_geometry)
        self.pg4 = _make_planetary(Ns=Ns4, Nr=Nr4, name="P4", sun=self.r3s4, ring=self.r4c1, carrier=self.output, strict_geometry=self.strict_geometry)

        self.A = Brake(self.r1, name="A")
        self.B = Brake(self.s12, name="B")
        self.C = Clutch(self.r2s3, self.interm, name="C")
        self.D = Clutch(self.p3c, self.interm, name="D")
        self.E = Clutch(self.input, self.r3s4, name="E")
        self.F = Clutch(self.r4c1, self.interm, name="F")

        self.constraints: Dict[str, object] = {
            "A": self.A,
            "B": self.B,
            "C": self.C,
            "D": self.D,
            "E": self.E,
            "F": self.F,
        }

    def release_all(self) -> None:
        for obj in self.constraints.values():
            obj.release()  # type: ignore[attr-defined]

    def normalize_state_name(self, state: str) -> str:
        key = state.strip().lower()
        if key == "all":
            return "all"
        mapped = STATE_ALIASES.get(key)
        if mapped is None:
            raise TenSpeedCliError(f"Unknown state: {state}")
        return mapped

    def set_state(self, state: str) -> GearState:
        key = self.normalize_state_name(state)
        if key == "all":
            raise TenSpeedCliError("Use solve_all() when state='all'.")
        self.release_all()
        engaged = self.SHIFT_SCHEDULE[key]
        for name in engaged:
            self.constraints[name].engage()  # type: ignore[index,attr-defined]
        return GearState(name=key, engaged=tuple(engaged), notes="Patent/article-based shift-element application")

    def _build_solver(self) -> TransmissionSolver:
        solver = TransmissionSolver()
        if hasattr(solver, "add_members"):
            solver.add_members(self.members.values())  # type: ignore[attr-defined]
        else:
            for member in self.members.values():
                solver.add_member(member)

        solver.add_gearset(self.pg1)
        solver.add_gearset(self.pg2)
        solver.add_gearset(self.pg3)
        solver.add_gearset(self.pg4)

        solver.add_brake(self.A)
        solver.add_brake(self.B)
        solver.add_clutch(self.C)
        solver.add_clutch(self.D)
        solver.add_clutch(self.E)
        solver.add_clutch(self.F)
        return solver

    def _solve_report_safe(self, solver: TransmissionSolver, *, input_speed: float) -> object:
        try:
            return solver.solve_report(input_member="input", input_speed=float(input_speed))  # type: ignore[attr-defined]
        except TypeError:
            equations, symbols = solver.build_equations(input_member="input", input_speed=float(input_speed))
            variables = list(symbols.values())
            try:
                solution_list = sp.solve(equations, variables, dict=True)
            except Exception as exc:
                raise TenSpeedCliError(f"Core-equation solve failure: {exc}") from exc

            sol0 = solution_list[0] if solution_list else None
            status = "inconsistent"
            message = "No solution found for the assembled transmission equations."
            if sol0 is not None:
                unresolved = []
                for name, sym in symbols.items():
                    expr = sol0.get(sym, None)
                    if expr is None or getattr(expr, "free_symbols", set()):
                        unresolved.append(name)
                if unresolved:
                    status = "underdetermined"
                    message = "Underdetermined member speeds: " + ", ".join(unresolved)
                else:
                    status = "ok"
                    message = "Fully determined member-speed solution."

            class _Classification:
                def __init__(self, status: str, message: str) -> None:
                    self.status = status
                    self.message = message
                    self.ok = status == "ok"

            class _Report:
                pass

            report = _Report()
            report.classification = _Classification(status, message)
            report.raw_solution = sol0
            report.symbols = dict(symbols)
            report.equations = list(equations)
            report.member_speeds = {}
            if sol0 is not None:
                for name, sym in symbols.items():
                    expr = sol0.get(sym, None)
                    if expr is None:
                        continue
                    expr = sp.simplify(expr)
                    if expr.free_symbols:
                        continue
                    report.member_speeds[name] = float(sp.N(expr))
            report.ok = status == "ok"
            return report
        except TransmissionSolverError as exc:
            raise TenSpeedCliError(f"Core solver failure: {exc}") from exc

    def solve_state(self, state: str, input_speed: float = 1.0) -> SolveResult:
        gs = self.set_state(state)
        solver = self._build_solver()
        if not hasattr(solver, "solve_report"):
            raise TenSpeedCliError(
                "Loaded core solver does not support solve_report. This ten_speed.py expects the upgraded Core V2 solver."
            )
        report = self._solve_report_safe(solver, input_speed=float(input_speed))
        classification = getattr(report, "classification", None)
        status = getattr(classification, "status", "unknown")
        message = getattr(classification, "message", "")
        speeds = {name: float(value) for name, value in dict(getattr(report, "member_speeds", {})).items()}
        ratio: Optional[float] = None
        out_speed = speeds.get("output")
        if out_speed is not None and abs(out_speed) > 1.0e-12:
            ratio_val = float(input_speed) / float(out_speed)
            ratio = ratio_val if gs.name == "Rev" else abs(ratio_val)
        notes = message or gs.notes
        return SolveResult(
            state=gs.name,
            engaged=gs.engaged,
            ok=bool(getattr(report, "ok", False)),
            ratio=ratio,
            speeds=speeds,
            notes=notes,
            solver_path="core_v2",
            status=status,
            message=message,
        )

    def solve_all(self, input_speed: float = 1.0) -> Dict[str, SolveResult]:
        return {state: self.solve_state(state, input_speed=input_speed) for state in self.DISPLAY_ORDER}

    def topology_summary(self) -> dict:
        return {
            "source": "Patent/article-derived Ford 10R80 stick-diagram reconstruction",
            "permanent_connections": {
                "input": "P2 carrier",
                "s12": "P1 sun = P2 sun",
                "r4c1": "P4 ring = P1 carrier",
                "r2s3": "P2 ring = P3 sun",
                "r3s4": "P3 ring = P4 sun",
                "output": "P4 carrier / output shaft",
            },
            "shift_elements": {
                "A": "r1 -> ground",
                "B": "s12 -> ground",
                "C": "r2s3 -> interm",
                "D": "p3c -> interm",
                "E": "input -> r3s4",
                "F": "r4c1 -> interm",
            },
        }


def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    if args.preset is None:
        counts = dict(DEFAULT_TOOTH_COUNTS)
    else:
        if args.preset not in PRESETS:
            valid = ", ".join(sorted(PRESETS))
            raise TenSpeedCliError(f"Unknown preset: {args.preset}. Valid presets: {valid}")
        counts = dict(PRESETS[args.preset])
    for i in range(1, 5):
        ns_val = getattr(args, f"Ns{i}")
        nr_val = getattr(args, f"Nr{i}")
        if ns_val is not None:
            counts[f"Ns{i}"] = int(ns_val)
        if nr_val is not None:
            counts[f"Nr{i}"] = int(nr_val)
    validate_tooth_counts(counts, strict_geometry=bool(args.strict_geometry))
    return counts


def _payload(result: SolveResult) -> Dict[str, object]:
    return {
        "state": result.state,
        "engaged": list(result.engaged),
        "ok": result.ok,
        "status": result.status,
        "ratio": result.ratio,
        "speeds": dict(result.speeds),
        "notes": result.notes,
        "solver_path": result.solver_path,
        "message": result.message,
    }


def _emit_cli_error(*, args: argparse.Namespace, message: str, tooth_counts: Optional[Mapping[str, int]] = None) -> int:
    payload = {
        "ok": False,
        "error": message,
        "preset": getattr(args, "preset", None),
        "strict_geometry": bool(getattr(args, "strict_geometry", False)),
    }
    if tooth_counts is not None:
        payload["tooth_counts"] = dict(tooth_counts)
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        print("ten_speed.py error", file=sys.stderr)
        print("------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                "Tooth counts: "
                f"P1(Ns1={tooth_counts['Ns1']}, Nr1={tooth_counts['Nr1']}), "
                f"P2(Ns2={tooth_counts['Ns2']}, Nr2={tooth_counts['Nr2']}), "
                f"P3(Ns3={tooth_counts['Ns3']}, Nr3={tooth_counts['Nr3']}), "
                f"P4(Ns4={tooth_counts['Ns4']}, Nr4={tooth_counts['Nr4']})",
                file=sys.stderr,
            )
    return 2


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ford 10R80 / 10R family 10-speed transmission kinematic model")
    p.add_argument("--state", default="all", help="State to solve: all, 1st..10th, rev")
    for i in range(1, 5):
        p.add_argument(f"--Ns{i}", type=int, default=None, help=f"P{i} sun tooth count")
        p.add_argument(f"--Nr{i}", type=int, default=None, help=f"P{i} ring tooth count")
    p.add_argument("--preset", default=None, choices=sorted(PRESETS), help="Optional tooth-count preset")
    p.add_argument("--input-speed", type=float, default=1.0, help="Input speed used for normalized solve/report")
    p.add_argument("--strict-geometry", action="store_true", help="Require even (Nr-Ns) for each gearset")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Print only state and ratio")
    p.add_argument("--show-topology", action="store_true", help="Emit modeled topology summary")
    p.add_argument("--verbose-report", action="store_true", help="Always show status and note columns")
    return p


def _fmt_speed(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if abs(value) < 5.0e-13:
        value = 0.0
    return f"{value:.3f}"


def _fmt_ratio(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.3f}"


def _print_ratios_only(results: Mapping[str, SolveResult], order: Sequence[str]) -> None:
    print("Ford 10R80 / 10R 10-Speed Ratio Summary")
    print("---------------------------------------")
    for state in order:
        ratio = results[state].ratio
        print(f"{state:<4}  {_fmt_ratio(ratio)}")


def _print_report(
    *,
    tx: Ford10RTenSpeedTransmission,
    results: Mapping[str, SolveResult],
    order: Sequence[str],
    tooth_counts: Mapping[str, int],
    preset_note: str,
    verbose: bool,
) -> None:
    print("Ford 10R80 / 10R 10-Speed Kinematic Summary")
    print("----------------------------------------------------------------------------------------------------------------------------------------------------------------")
    print(
        "Tooth counts: "
        f"P1(Ns1={tooth_counts['Ns1']}, Nr1={tooth_counts['Nr1']}), "
        f"P2(Ns2={tooth_counts['Ns2']}, Nr2={tooth_counts['Nr2']}), "
        f"P3(Ns3={tooth_counts['Ns3']}, Nr3={tooth_counts['Nr3']}), "
        f"P4(Ns4={tooth_counts['Ns4']}, Nr4={tooth_counts['Nr4']})"
    )
    print(f"Geometry mode: {'strict' if tx.strict_geometry else 'relaxed'}")
    print(f"Preset note: {preset_note}")
    print("Solver path: core_v2")
    print("----------------------------------------------------------------------------------------------------------------------------------------------------------------")

    need_diag = verbose or any((not r.ok) or r.status != "ok" for r in results.values())
    if need_diag:
        print(
            f"{'State':<6}  {'Elems':<13}  {'Status':<16}  {'Ratio':>8}  {'Input':>8}  {'r1':>8}  {'s12':>8}  {'r4c1':>8}  {'r2s3':>8}  {'r3s4':>8}  {'interm':>8}  {'p3c':>8}  {'Output':>8}"
        )
        print("----------------------------------------------------------------------------------------------------------------------------------------------------------------")
        for state in order:
            r = results[state]
            s = r.speeds
            print(
                f"{state:<6}  {'+'.join(r.engaged):<13}  {r.status:<16}  {_fmt_ratio(r.ratio):>8}  {_fmt_speed(s.get('input')):>8}  {_fmt_speed(s.get('r1')):>8}  {_fmt_speed(s.get('s12')):>8}  {_fmt_speed(s.get('r4c1')):>8}  {_fmt_speed(s.get('r2s3')):>8}  {_fmt_speed(s.get('r3s4')):>8}  {_fmt_speed(s.get('interm')):>8}  {_fmt_speed(s.get('p3c')):>8}  {_fmt_speed(s.get('output')):>8}"
            )
            if r.message:
                print(f"  note: {r.message}")
    else:
        print(
            f"{'State':<6}  {'Elems':<13}  {'Ratio':>8}  {'Input':>8}  {'r1':>8}  {'s12':>8}  {'r4c1':>8}  {'r2s3':>8}  {'r3s4':>8}  {'interm':>8}  {'p3c':>8}  {'Output':>8}"
        )
        print("----------------------------------------------------------------------------------------------------------------------------------------------------------------")
        for state in order:
            r = results[state]
            s = r.speeds
            print(
                f"{state:<6}  {'+'.join(r.engaged):<13}  {_fmt_ratio(r.ratio):>8}  {_fmt_speed(s.get('input')):>8}  {_fmt_speed(s.get('r1')):>8}  {_fmt_speed(s.get('s12')):>8}  {_fmt_speed(s.get('r4c1')):>8}  {_fmt_speed(s.get('r2s3')):>8}  {_fmt_speed(s.get('r3s4')):>8}  {_fmt_speed(s.get('interm')):>8}  {_fmt_speed(s.get('p3c')):>8}  {_fmt_speed(s.get('output')):>8}"
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        tooth_counts = _resolve_tooth_counts(args)
        tx = Ford10RTenSpeedTransmission(
            Ns1=tooth_counts["Ns1"], Nr1=tooth_counts["Nr1"],
            Ns2=tooth_counts["Ns2"], Nr2=tooth_counts["Nr2"],
            Ns3=tooth_counts["Ns3"], Nr3=tooth_counts["Nr3"],
            Ns4=tooth_counts["Ns4"], Nr4=tooth_counts["Nr4"],
            strict_geometry=bool(args.strict_geometry),
        )
    except TenSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc))

    preset_note = PRESET_NOTES.get(args.preset or "ford_10r80_estimated", PRESET_NOTES["ford_10r80_estimated"])

    try:
        state = tx.normalize_state_name(args.state)
        if state == "all":
            results = tx.solve_all(input_speed=float(args.input_speed))
            order = tx.DISPLAY_ORDER
        else:
            single = tx.solve_state(state, input_speed=float(args.input_speed))
            results = {state: single}
            order = (state,)
    except TenSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts)

    if args.json:
        payload = {
            "ok": all(r.ok for r in results.values()),
            "model": "Ford 10R80 / 10R 10-speed",
            "solver_path": "core_v2",
            "strict_geometry": bool(args.strict_geometry),
            "tooth_counts": dict(tooth_counts),
            "preset_note": preset_note,
            "results": [_payload(results[state]) for state in order],
        }
        if args.show_topology:
            payload["topology"] = tx.topology_summary()
        print(json.dumps(payload, indent=2))
        return 0

    if args.show_topology:
        print("Topology summary")
        print("----------------")
        print(json.dumps(tx.topology_summary(), indent=2))
        print()

    if args.ratios_only:
        _print_ratios_only(results, order)
    else:
        _print_report(
            tx=tx,
            results=results,
            order=order,
            tooth_counts=tooth_counts,
            preset_note=preset_note,
            verbose=bool(args.verbose_report),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
