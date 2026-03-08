#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.eight_speed

ZF 8HP45 / 8HP70 family 8-speed automatic transmission kinematic model.

Core V2 refactor
----------------
This version stays on the reusable shared core stack:

- core.planetary.PlanetaryGearSet
- core.clutch.{RotatingMember, Clutch, Brake}
- core.solver.TransmissionSolver

Latest topology interpretation
------------------------------
This upgrade implements the topology change discussed in the latest 8HP review:

- input shaft drives the P2 carrier and the C-clutch housing input
- P1 sun and P2 sun are common -> sun12
- A brake holds sun12
- B brake holds the P1 ring (annulus)
- C clutch drives the P3 ring, the P4 sun, and the E-clutch housing -> c_out
- D clutch ties the P3 carrier to the P4 carrier / output shaft
- ATSG point 6 says the E clutch connects the P2 annulus to the P3 sun gear
- ATSG assembly language also refers to a "P2 annulus / P3 sun gear" assembly

To stay honest to those notes while still using the common simple-planetary core,
this script now models:

    p23 = P2 ring = P3 sun

as one permanent rotating member, and E becomes a single clutch that connects:

    c_out <-> p23

This is the key change that closes 5th and 7th without resorting to ad-hoc local
solvers.

Modeled rotating members
------------------------
input      : turbine / transmission input shaft, also P2 carrier
sun12      : common sun for P1 and P2
p1r        : P1 ring
p1c_p4r    : P1 carrier = P4 ring
p23        : P2 ring = P3 sun
c_out      : C-clutch output = P3 ring = P4 sun = E housing
p3c        : P3 carrier
output     : P4 carrier / output shaft

Planetary relations
-------------------
P1: Ns1 * (w_sun12   - w_p1c_p4r) + Nr1 * (w_p1r   - w_p1c_p4r) = 0
P2: Ns2 * (w_sun12   - w_input)    + Nr2 * (w_p23   - w_input)    = 0
P3: Ns3 * (w_p23     - w_p3c)      + Nr3 * (w_c_out - w_p3c)      = 0
P4: Ns4 * (w_c_out   - w_output)   + Nr4 * (w_p1c_p4r - w_output) = 0

Shift-element interpretation
----------------------------
A : sun12 -> ground
B : p1r   -> ground
C : input <-> c_out
D : p3c   <-> output
E : p23   <-> c_out

Shift chart (ATSG)
------------------
Rev : A + B + D
1st : A + B + C
2nd : A + B + E
3rd : B + C + E
4th : B + D + E
5th : B + C + D
6th : C + D + E
7th : A + C + D
8th : A + D + E

Important honesty note
----------------------
This is still a core-class kinematic reconstruction from public ATSG-style
member-relationship notes. It is not an OEM hydraulic model, torque model, or
pinion-by-pinion synthesis. The important change here is that the model no
longer leaves the P2-ring / P3-sun path artificially split when E is released.
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


class EightSpeedCliError(ValueError):
    """User-facing CLI/configuration error for eight_speed.py."""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    # Fitted candidate set for the upgraded shared-p23 topology.
    # This reproduces the published ATSG ratio spread very closely:
    # 1st  4.714, 2nd 3.143, 3rd 2.106, 4th 1.667,
    # 5th  1.285, 6th 1.000, 7th 0.839, 8th 0.667, Rev -3.289.
    "Ns1": 48,
    "Nr1": 96,
    "Ns2": 48,
    "Nr2": 96,
    "Ns3": 38,
    "Nr3": 61,
    "Ns4": 21,
    "Nr4": 78,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "zf_8hp_point6_candidate": dict(DEFAULT_TOOTH_COUNTS),
    "zf_8hp45_reference_legacy": {
        "Ns1": 48,
        "Nr1": 96,
        "Ns2": 48,
        "Nr2": 96,
        "Ns3": 38,
        "Nr3": 96,
        "Ns4": 23,
        "Nr4": 85,
    },
}

PRESET_NOTES: Mapping[str, str] = {
    "zf_8hp_point6_candidate": (
        "Candidate tooth-count set fitted after adopting the shared P2-annulus / P3-sun node "
        "suggested by ATSG point 6 and assembly wording; not claimed as OEM-confirmed tooth data."
    ),
    "zf_8hp45_reference_legacy": (
        "Older ATSG-style reference set from the earlier split-node model. Kept for comparison only."
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
    "6": "6th",
    "6th": "6th",
    "sixth": "6th",
    "7": "7th",
    "7th": "7th",
    "seventh": "7th",
    "8": "8th",
    "8th": "8th",
    "eighth": "8th",
    "r": "Rev",
    "rev": "Rev",
    "reverse": "Rev",
}


def _validate_counts_basic(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise EightSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise EightSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )


def _validate_counts_strict(*, Ns: int, Nr: int, label: str) -> None:
    _validate_counts_basic(Ns=Ns, Nr=Nr, label=label)
    if (Nr - Ns) % 2 != 0:
        raise EightSpeedCliError(
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


class ZF8HPEightSpeedTransmission:
    """ZF 8HP family kinematic model solved through the shared core stack."""

    SHIFT_SCHEDULE: Mapping[str, tuple[str, ...]] = {
        "1st": ("A", "B", "C"),
        "2nd": ("A", "B", "E"),
        "3rd": ("B", "C", "E"),
        "4th": ("B", "D", "E"),
        "5th": ("B", "C", "D"),
        "6th": ("C", "D", "E"),
        "7th": ("A", "C", "D"),
        "8th": ("A", "D", "E"),
        "Rev": ("A", "B", "D"),
    }
    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "Rev")

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
            "Ns1": int(Ns1),
            "Nr1": int(Nr1),
            "Ns2": int(Ns2),
            "Nr2": int(Nr2),
            "Ns3": int(Ns3),
            "Nr3": int(Nr3),
            "Ns4": int(Ns4),
            "Nr4": int(Nr4),
        }
        self._build_topology(**self.tooth_counts)

    def _build_topology(
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
    ) -> None:
        self.input = RotatingMember("input")
        self.sun12 = RotatingMember("sun12")
        self.p1r = RotatingMember("p1r")
        self.p1c_p4r = RotatingMember("p1c_p4r")
        self.p23 = RotatingMember("p23")
        self.c_out = RotatingMember("c_out")
        self.p3c = RotatingMember("p3c")
        self.output = RotatingMember("output")

        self.members: Dict[str, RotatingMember] = {
            "input": self.input,
            "sun12": self.sun12,
            "p1r": self.p1r,
            "p1c_p4r": self.p1c_p4r,
            "p23": self.p23,
            "c_out": self.c_out,
            "p3c": self.p3c,
            "output": self.output,
        }

        self.pg1 = _make_planetary(
            Ns=Ns1,
            Nr=Nr1,
            name="P1",
            sun=self.sun12,
            ring=self.p1r,
            carrier=self.p1c_p4r,
            strict_geometry=self.strict_geometry,
        )
        self.pg2 = _make_planetary(
            Ns=Ns2,
            Nr=Nr2,
            name="P2",
            sun=self.sun12,
            ring=self.p23,
            carrier=self.input,
            strict_geometry=self.strict_geometry,
        )
        self.pg3 = _make_planetary(
            Ns=Ns3,
            Nr=Nr3,
            name="P3",
            sun=self.p23,
            ring=self.c_out,
            carrier=self.p3c,
            strict_geometry=self.strict_geometry,
        )
        self.pg4 = _make_planetary(
            Ns=Ns4,
            Nr=Nr4,
            name="P4",
            sun=self.c_out,
            ring=self.p1c_p4r,
            carrier=self.output,
            strict_geometry=self.strict_geometry,
        )

        self.A = Brake(self.sun12, name="A")
        self.B = Brake(self.p1r, name="B")
        self.C = Clutch(self.input, self.c_out, name="C")
        self.D = Clutch(self.p3c, self.output, name="D")
        self.E = Clutch(self.p23, self.c_out, name="E")

        self.constraints: Dict[str, object] = {
            "A": self.A,
            "B": self.B,
            "C": self.C,
            "D": self.D,
            "E": self.E,
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
            raise EightSpeedCliError(f"Unknown state: {state}")
        return mapped

    def set_state(self, state: str) -> GearState:
        key = self.normalize_state_name(state)
        if key == "all":
            raise EightSpeedCliError("Use solve_all() when state='all'.")
        self.release_all()
        engaged = self.SHIFT_SCHEDULE[key]
        for name in engaged:
            self.constraints[name].engage()  # type: ignore[index,attr-defined]
        return GearState(name=key, engaged=tuple(engaged), notes="ATSG-based shift-element application")

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
        return solver

    def _member_speeds_from_report(self, report: object) -> Dict[str, float]:
        member_speeds = dict(getattr(report, "member_speeds", {}))
        out = {name: float(value) for name, value in member_speeds.items()}
        # Backward-friendly display aliases: the upgraded topology merges P2 ring and P3 sun.
        if "p23" in out:
            out.setdefault("p2r", out["p23"])
            out.setdefault("p3s", out["p23"])
        return out

    def _augment_with_numeric_raw_solution(self, *, report: object, speeds: Dict[str, float]) -> Dict[str, float]:
        raw_solution = getattr(report, "raw_solution", None)
        symbols = getattr(report, "symbols", None)
        if not isinstance(raw_solution, dict) or not isinstance(symbols, dict):
            return speeds
        out = dict(speeds)
        for name, sym in symbols.items():
            if name in out:
                continue
            if sym not in raw_solution:
                continue
            expr = sp.simplify(raw_solution[sym])
            if expr.free_symbols:
                continue
            out[name] = float(sp.N(expr))
        if "p23" in out:
            out.setdefault("p2r", out["p23"])
            out.setdefault("p3s", out["p23"])
        return out

    def _solve_report_safe(self, solver: TransmissionSolver, *, input_speed: float) -> object:
        try:
            return solver.solve_report(input_member="input", input_speed=float(input_speed))  # type: ignore[attr-defined]
        except TypeError:
            equations, symbols = solver.build_equations(input_member="input", input_speed=float(input_speed))
            variables = list(symbols.values())
            try:
                solution_list = sp.solve(equations, variables, dict=True)
            except Exception as exc:
                raise EightSpeedCliError(f"Core-equation solve failure: {exc}") from exc

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
            raise EightSpeedCliError(f"Core solver failure: {exc}") from exc

    def solve_state(self, state: str, input_speed: float = 1.0) -> SolveResult:
        gs = self.set_state(state)
        solver = self._build_solver()
        if not hasattr(solver, "solve_report"):
            raise EightSpeedCliError(
                "Loaded core solver does not support solve_report. This refactored eight_speed.py expects the upgraded Core V2 solver."
            )
        report = self._solve_report_safe(solver, input_speed=float(input_speed))

        classification = getattr(report, "classification", None)
        status = getattr(classification, "status", "unknown")
        message = getattr(classification, "message", "")

        speeds = self._member_speeds_from_report(report)
        speeds = self._augment_with_numeric_raw_solution(report=report, speeds=speeds)

        ratio: Optional[float] = None
        out_speed = speeds.get("output")
        if out_speed is not None and abs(out_speed) > 1.0e-12:
            ratio_val = float(input_speed) / float(out_speed)
            ratio = ratio_val if gs.name == "Rev" else abs(ratio_val)

        notes = gs.notes
        if message:
            notes = message if not notes else f"{notes}; {message}"

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
            "source": "ATSG-style ZF8HP planetary relationship reconstruction with shared P2-annulus / P3-sun node",
            "permanent_connections": {
                "input": "P2 carrier",
                "sun12": "P1 sun = P2 sun",
                "p1c_p4r": "P1 carrier = P4 ring",
                "p23": "P2 ring = P3 sun",
                "c_out": "C clutch output = P3 ring = P4 sun = E housing",
                "output": "P4 carrier / output shaft",
            },
            "shift_elements": {
                "A": "sun12 -> ground",
                "B": "p1r -> ground",
                "C": "input -> c_out",
                "D": "p3c -> output",
                "E": "p23 -> c_out",
            },
        }


def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    if args.preset is None:
        counts = dict(DEFAULT_TOOTH_COUNTS)
    else:
        if args.preset not in PRESETS:
            valid = ", ".join(sorted(PRESETS))
            raise EightSpeedCliError(f"Unknown preset: {args.preset}. Valid presets: {valid}")
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
        print("eight_speed.py error", file=sys.stderr)
        print("--------------------", file=sys.stderr)
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
    p = argparse.ArgumentParser(description="ZF 8HP ATSG-based 8-speed transmission kinematic model")
    p.add_argument("--state", default="all", help="State to solve: all, 1st..8th, rev")
    for i in range(1, 5):
        p.add_argument(f"--Ns{i}", type=int, default=None, help=f"P{i} sun tooth count")
        p.add_argument(f"--Nr{i}", type=int, default=None, help=f"P{i} ring tooth count")
    p.add_argument("--preset", default="zf_8hp_point6_candidate", help="Named preset tooth-count configuration")
    p.add_argument("--strict-geometry", action="store_true", help="Enforce strict simple-planetary integer-planet geometry checks")
    p.add_argument("--list-presets", action="store_true", help="List presets and exit")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Emit only ratios")
    p.add_argument("--show-topology", action="store_true", help="Show modeled topology and exit")
    p.add_argument("--verbose-report", action="store_true", help="Show solver status and note lines even when all states solve cleanly")
    return p


def _print_presets() -> None:
    print("Available presets")
    print("-----------------")
    for name, counts in PRESETS.items():
        note = PRESET_NOTES.get(name, "")
        print(
            f"{name:24s} "
            f"Ns1={counts['Ns1']} Nr1={counts['Nr1']} "
            f"Ns2={counts['Ns2']} Nr2={counts['Nr2']} "
            f"Ns3={counts['Ns3']} Nr3={counts['Nr3']} "
            f"Ns4={counts['Ns4']} Nr4={counts['Nr4']}"
        )
        if note:
            print(f"  note: {note}")


def _print_summary(
    *,
    counts: Mapping[str, int],
    results: Dict[str, SolveResult],
    ratios_only: bool,
    strict_geometry: bool,
    preset_note: str = "",
    verbose_report: bool = False,
) -> None:
    print("ZF 8HP 8-Speed Kinematic Summary")
    print("-" * 140)
    print(
        f"Tooth counts: P1(Ns1={counts['Ns1']}, Nr1={counts['Nr1']}), "
        f"P2(Ns2={counts['Ns2']}, Nr2={counts['Nr2']}), "
        f"P3(Ns3={counts['Ns3']}, Nr3={counts['Nr3']}), "
        f"P4(Ns4={counts['Ns4']}, Nr4={counts['Nr4']})"
    )
    print(f"Geometry mode: {'strict' if strict_geometry else 'relaxed'}")
    if preset_note:
        print(f"Preset note: {preset_note}")
    print("Solver path: core_v2")
    print("-" * 140)

    any_issue = any((not r.ok) or (r.status != 'ok') for r in results.values())
    show_diag = bool(verbose_report or any_issue)

    if ratios_only:
        if show_diag:
            print(f"{'State':<8s} {'Elems':<14s} {'Status':<18s} {'Ratio':>10s}")
        else:
            print(f"{'State':<8s} {'Elems':<14s} {'Ratio':>10s}")
        print("-" * 140)
        for name, result in results.items():
            elems = "+".join(result.engaged)
            ratio_txt = "-" if result.ratio is None else f"{result.ratio:.3f}"
            if show_diag:
                print(f"{name:<8s} {elems:<14s} {result.status:<18s} {ratio_txt:>10s}")
                if result.message:
                    print(f"  note: {result.message}")
            else:
                print(f"{name:<8s} {elems:<14s} {ratio_txt:>10s}")
        return

    if show_diag:
        headers = (
            f"{'State':<8s} {'Elems':<14s} {'Status':<18s} {'Ratio':>10s} {'Input':>9s} {'sun12':>9s} {'p1r':>9s} "
            f"{'p23':>9s} {'c_out':>9s} {'p1c_p4r':>9s} {'p3c':>9s} {'Output':>9s}"
        )
    else:
        headers = (
            f"{'State':<8s} {'Elems':<14s} {'Ratio':>10s} {'Input':>9s} {'sun12':>9s} {'p1r':>9s} "
            f"{'p23':>9s} {'c_out':>9s} {'p1c_p4r':>9s} {'p3c':>9s} {'Output':>9s}"
        )
    print(headers)
    print("-" * 140)

    def fmt(speeds: Mapping[str, float], key: str) -> str:
        return f"{speeds[key]:>9.3f}" if key in speeds else f"{'-':>9s}"

    for name, result in results.items():
        elems = "+".join(result.engaged)
        s = result.speeds
        ratio_txt = "-" if result.ratio is None else f"{result.ratio:.3f}"
        common = (
            f"{name:<8s} {elems:<14.14s} {ratio_txt:>10s} "
            f"{fmt(s, 'input')} {fmt(s, 'sun12')} {fmt(s, 'p1r')} {fmt(s, 'p23')} {fmt(s, 'c_out')} "
            f"{fmt(s, 'p1c_p4r')} {fmt(s, 'p3c')} {fmt(s, 'output')}"
        )
        if show_diag:
            print(f"{name:<8s} {elems:<14.14s} {result.status:<18s} {ratio_txt:>10s} "
                  f"{fmt(s, 'input')} {fmt(s, 'sun12')} {fmt(s, 'p1r')} {fmt(s, 'p23')} {fmt(s, 'c_out')} "
                  f"{fmt(s, 'p1c_p4r')} {fmt(s, 'p3c')} {fmt(s, 'output')}")
            if result.message:
                print(f"  note: {result.message}")
        else:
            print(common)

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.list_presets:
        _print_presets()
        return 0

    try:
        counts = _resolve_tooth_counts(args)
    except EightSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc))

    tx = ZF8HPEightSpeedTransmission(
        Ns1=counts["Ns1"],
        Nr1=counts["Nr1"],
        Ns2=counts["Ns2"],
        Nr2=counts["Nr2"],
        Ns3=counts["Ns3"],
        Nr3=counts["Nr3"],
        Ns4=counts["Ns4"],
        Nr4=counts["Nr4"],
        strict_geometry=bool(args.strict_geometry),
    )

    if args.show_topology:
        payload = tx.topology_summary()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("ZF 8HP Topology Summary")
            print("-" * 32)
            print(json.dumps(payload, indent=2))
        return 0

    state_key = args.state.strip().lower()
    preset_note = PRESET_NOTES.get(args.preset, "")

    try:
        if state_key == "all":
            results = tx.solve_all(input_speed=1.0)
            if args.json:
                print(json.dumps({
                    "ok": all(r.ok for r in results.values()),
                    "solver_path": "core_v2",
                    "preset": args.preset,
                    "strict_geometry": bool(args.strict_geometry),
                    "tooth_counts": counts,
                    "results": {name: _payload(res) for name, res in results.items()},
                }, indent=2))
            else:
                _print_summary(
                    counts=counts,
                    results=results,
                    ratios_only=bool(args.ratios_only),
                    strict_geometry=bool(args.strict_geometry),
                    preset_note=preset_note,
                    verbose_report=bool(args.verbose_report),
                )
            return 0

        state = tx.normalize_state_name(args.state)
        result = tx.solve_state(state, input_speed=1.0)
        if args.json:
            print(json.dumps({
                "ok": result.ok,
                "solver_path": result.solver_path,
                "preset": args.preset,
                "strict_geometry": bool(args.strict_geometry),
                "tooth_counts": counts,
                "result": _payload(result),
            }, indent=2))
        else:
            _print_summary(
                counts=counts,
                results={result.state: result},
                ratios_only=bool(args.ratios_only),
                strict_geometry=bool(args.strict_geometry),
                preset_note=preset_note,
                verbose_report=bool(args.verbose_report),
            )
        return 0
    except EightSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=counts)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
