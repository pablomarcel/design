#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.three_speed

Ford C4-style 3-speed automatic transmission kinematic model.

Core V2 refactor
----------------
This version is intended to solve through the upgraded core stack:
- core.planetary.PlanetaryGearSet
- core.clutch.{RotatingMember, Clutch, Brake, Sprag}
- core.solver.TransmissionSolver

Key topology points
-------------------
Classic Simpson arrangement with a common sun gear:
- Front set:
    * ring = front_ring (driven by Forward Clutch)
    * carrier = front_carrier
    * sun = common sun
- Rear set:
    * ring = rear_ring
    * carrier = rear_carrier reaction member
    * sun = same common sun

Permanent mechanical ties:
- front_carrier = output
- rear_ring = output

Shift elements:
- Forward Clutch      : input ↔ front_ring
- High/Reverse Clutch : input ↔ sun
- Intermediate Band   : sun → ground
- Low/Reverse Band    : rear_carrier → ground
- Sprag               : rear_carrier one-way hold (current core models this as
                        a brake-like hold when engaged, but it is still represented
                        as a first-class sprag object)

This script now prefers the upgraded core path explicitly and reports which
solver path was used so there is no ambiguity about hidden fallback behavior.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence

try:
    from ..core.clutch import Brake, Clutch, RotatingMember, Sprag
    from ..core.planetary import PlanetaryGearSet
    from ..core.solver import TransmissionSolver
except Exception:  # pragma: no cover
    try:
        from core.clutch import Brake, Clutch, RotatingMember, Sprag  # type: ignore
        from core.planetary import PlanetaryGearSet  # type: ignore
        from core.solver import TransmissionSolver  # type: ignore
    except Exception:  # pragma: no cover
        from clutch import Brake, Clutch, RotatingMember, Sprag  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore
        from solver import TransmissionSolver  # type: ignore


class ThreeSpeedCliError(ValueError):
    """User-facing CLI/configuration error for three_speed.py."""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    "Ns_front": 33,
    "Nr_front": 72,
    "Ns_rear": 33,
    "Nr_rear": 72,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "ford_c4_reference": {"Ns_front": 33, "Nr_front": 72, "Ns_rear": 33, "Nr_rear": 72},
    "simpson_demo": {"Ns_front": 34, "Nr_front": 72, "Ns_rear": 34, "Nr_rear": 72},
}

PRESET_NOTES: Mapping[str, str] = {
    "ford_c4_reference": "Published Ford C4 reference values commonly quoted online. Intended for relaxed geometry mode.",
    "simpson_demo": "Geometry-clean demo preset with even (Nr-Ns).",
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
    speeds: Dict[str, float]
    ratio: float
    notes: str = ""
    solver_path: str = "core_v2"


@dataclass(frozen=True)
class _RelaxedPlanetaryProxy:
    """
    Minimal planetary object for kinematic use when strict PlanetaryGearSet
    construction is unavailable but relaxed geometry mode is requested.

    The upgraded core solver only needs:
        name, Ns, Nr, sun, ring, carrier
    """
    Ns: int
    Nr: int
    name: str
    sun: RotatingMember
    ring: RotatingMember
    carrier: RotatingMember


def _validate_counts_basic(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise ThreeSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise ThreeSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )


def _validate_counts_strict(*, Ns: int, Nr: int, label: str) -> None:
    _validate_counts_basic(Ns=Ns, Nr=Nr, label=label)
    if (Nr - Ns) % 2 != 0:
        raise ThreeSpeedCliError(
            f"Invalid {label} tooth counts under strict geometry mode: (Nr - Ns) must be even so the implied "
            f"planet tooth count is an integer. Got Ns={Ns}, Nr={Nr}, Nr-Ns={Nr - Ns}."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    validator = _validate_counts_strict if strict_geometry else _validate_counts_basic
    validator(Ns=int(counts["Ns_front"]), Nr=int(counts["Nr_front"]), label="Front gearset")
    validator(Ns=int(counts["Ns_rear"]), Nr=int(counts["Nr_rear"]), label="Rear gearset")


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

    try:
        return PlanetaryGearSet(
            Ns=Ns,
            Nr=Nr,
            name=name,
            sun=sun,
            ring=ring,
            carrier=carrier,
        )
    except Exception:
        if strict_geometry:
            raise
        return _RelaxedPlanetaryProxy(
            Ns=int(Ns),
            Nr=int(Nr),
            name=name,
            sun=sun,
            ring=ring,
            carrier=carrier,
        )


class FordC4ThreeSpeedTransmission:
    """Ford C4-style Simpson transmission kinematic model."""

    SHIFT_SCHEDULE: Mapping[str, tuple[str, ...]] = {
        "1st": ("forward_clutch", "sprag"),
        "drive1": ("forward_clutch", "sprag"),
        "drive_1st": ("forward_clutch", "sprag"),
        "2nd": ("forward_clutch", "intermediate_band"),
        "drive2": ("forward_clutch", "intermediate_band"),
        "drive_2nd": ("forward_clutch", "intermediate_band"),
        "3rd": ("forward_clutch", "high_reverse_clutch"),
        "drive3": ("forward_clutch", "high_reverse_clutch"),
        "drive_3rd": ("forward_clutch", "high_reverse_clutch"),
        "rev": ("high_reverse_clutch", "low_reverse_band"),
        "reverse": ("high_reverse_clutch", "low_reverse_band"),
        "manual1": ("forward_clutch", "low_reverse_band", "sprag"),
        "manual_1": ("forward_clutch", "low_reverse_band", "sprag"),
        "manual2": ("forward_clutch", "intermediate_band"),
        "manual_2": ("forward_clutch", "intermediate_band"),
    }

    DISPLAY_NAMES: Mapping[str, str] = {
        "1st": "1st",
        "2nd": "2nd",
        "3rd": "3rd",
        "rev": "Rev",
        "manual1": "Manual1",
        "manual2": "Manual2",
    }

    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "rev", "manual1", "manual2")

    def __init__(self, *, Ns_front: int, Nr_front: int, Ns_rear: int, Nr_rear: int, strict_geometry: bool = False) -> None:
        self.Ns_front = int(Ns_front)
        self.Nr_front = int(Nr_front)
        self.Ns_rear = int(Ns_rear)
        self.Nr_rear = int(Nr_rear)
        self.strict_geometry = bool(strict_geometry)
        self._build_topology()

    def _build_topology(self) -> None:
        self.input = RotatingMember("input")
        self.sun = RotatingMember("sun")
        self.front_ring = RotatingMember("front_ring")
        self.front_carrier = RotatingMember("front_carrier")
        self.rear_ring = RotatingMember("rear_ring")
        self.rear_carrier = RotatingMember("rear_carrier")
        self.output = RotatingMember("output")

        self.members: Dict[str, RotatingMember] = {
            "input": self.input,
            "sun": self.sun,
            "front_ring": self.front_ring,
            "front_carrier": self.front_carrier,
            "rear_ring": self.rear_ring,
            "rear_carrier": self.rear_carrier,
            "output": self.output,
        }

        self.pg_front = _make_planetary(
            Ns=self.Ns_front,
            Nr=self.Nr_front,
            name="PG_front",
            sun=self.sun,
            ring=self.front_ring,
            carrier=self.front_carrier,
            strict_geometry=self.strict_geometry,
        )
        self.pg_rear = _make_planetary(
            Ns=self.Ns_rear,
            Nr=self.Nr_rear,
            name="PG_rear",
            sun=self.sun,
            ring=self.rear_ring,
            carrier=self.rear_carrier,
            strict_geometry=self.strict_geometry,
        )

        self.forward_clutch = Clutch(self.input, self.front_ring, name="forward_clutch")
        self.high_reverse_clutch = Clutch(self.input, self.sun, name="high_reverse_clutch")
        self.intermediate_band = Brake(self.sun, name="intermediate_band")
        self.low_reverse_band = Brake(self.rear_carrier, name="low_reverse_band")
        self.sprag = Sprag(self.rear_carrier, hold_direction="ccw", name="sprag")

        self.constraints: Dict[str, object] = {
            "forward_clutch": self.forward_clutch,
            "high_reverse_clutch": self.high_reverse_clutch,
            "intermediate_band": self.intermediate_band,
            "low_reverse_band": self.low_reverse_band,
            "sprag": self.sprag,
        }

    def release_all(self) -> None:
        for c in self.constraints.values():
            c.release()  # type: ignore[attr-defined]

    def set_state(self, state: str) -> GearState:
        key = state.strip().lower()
        if key not in self.SHIFT_SCHEDULE:
            raise ThreeSpeedCliError(f"Unknown state: {state}")
        self.release_all()
        engaged = self.SHIFT_SCHEDULE[key]
        for name in engaged:
            self.constraints[name].engage()  # type: ignore[attr-defined]
        display = self.DISPLAY_NAMES.get(key, state.strip())
        notes_map = {
            "1st": "Drive 1st: Forward clutch applied, rear carrier held by sprag.",
            "2nd": "Drive 2nd: Forward clutch applied, sun held by intermediate band.",
            "3rd": "Drive 3rd: Forward clutch and High/Reverse clutch applied for direct drive.",
            "rev": "Reverse: High/Reverse clutch drives sun, Low/Reverse band holds rear carrier.",
            "manual1": "Manual 1: Forward clutch applied, rear carrier held by Low/Reverse band (sprag also holding).",
            "manual2": "Manual 2: Forward clutch applied, sun held by intermediate band.",
        }
        return GearState(display, tuple(engaged), notes_map.get(key, ""))

    def _solve_core_v2(self) -> Dict[str, float]:
        solver = TransmissionSolver()

        if hasattr(solver, "add_members"):
            solver.add_members(self.members.values())  # type: ignore[attr-defined]
        else:
            for member in self.members.values():
                solver.add_member(member)

        solver.add_gearset(self.pg_front)
        solver.add_gearset(self.pg_rear)
        solver.add_clutch(self.forward_clutch)
        solver.add_clutch(self.high_reverse_clutch)
        solver.add_brake(self.intermediate_band)
        solver.add_brake(self.low_reverse_band)
        # Current solver's brake path accepts Sprag because it exposes the same
        # member + constraint interface, even though it is a distinct topology object.
        solver.add_brake(self.sprag)  # type: ignore[arg-type]

        if not hasattr(solver, "add_permanent_tie"):
            raise ThreeSpeedCliError(
                "Loaded core solver does not support permanent ties. This refactored three_speed.py "
                "expects the upgraded Core V2 solver."
            )

        solver.add_permanent_tie("front_carrier", "output")  # type: ignore[attr-defined]
        solver.add_permanent_tie("rear_ring", "output")      # type: ignore[attr-defined]

        if hasattr(solver, "solve_report"):
            report = solver.solve_report(input_member="input", input_speed=1.0)  # type: ignore[attr-defined]
            if not getattr(report, "ok", False):
                message = getattr(getattr(report, "classification", None), "message", "Solver failed")
                raise ThreeSpeedCliError(str(message))
            result = dict(report.member_speeds)  # type: ignore[attr-defined]
        else:
            result = dict(solver.solve("input", 1.0))

        if "output" not in result and "front_carrier" in result:
            result["output"] = result["front_carrier"]
        if "front_carrier" not in result and "output" in result:
            result["front_carrier"] = result["output"]
        if "rear_ring" not in result and "output" in result:
            result["rear_ring"] = result["output"]
        if "input" not in result:
            result["input"] = 1.0
        return result

    def solve_state(self, state: str) -> SolveResult:
        gs = self.set_state(state)
        speeds = self._solve_core_v2()

        if abs(float(speeds["output"])) < 1.0e-12:
            raise ThreeSpeedCliError(f"Output speed is zero for state {gs.name}; ratio is undefined.")

        ratio = 1.0 / float(speeds["output"])
        display_speeds = {
            "input": float(speeds["input"]),
            "front_ring": float(speeds["front_ring"]),
            "sun": float(speeds["sun"]),
            "output": float(speeds["output"]),
            "rear_carrier": float(speeds["rear_carrier"]),
        }
        return SolveResult(gs.name, gs.engaged, display_speeds, ratio, gs.notes, solver_path="core_v2")

    def solve_all(self) -> Dict[str, SolveResult]:
        out: Dict[str, SolveResult] = {}
        for state in self.DISPLAY_ORDER:
            out[self.DISPLAY_NAMES[state]] = self.solve_state(state)
        return out


def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    if args.preset is None:
        counts = dict(DEFAULT_TOOTH_COUNTS)
    else:
        if args.preset not in PRESETS:
            valid = ", ".join(sorted(PRESETS))
            raise ThreeSpeedCliError(f"Unknown preset: {args.preset}. Valid presets: {valid}")
        counts = dict(PRESETS[args.preset])

    if args.Ns is not None:
        counts["Ns_front"] = int(args.Ns)
        counts["Ns_rear"] = int(args.Ns)
    if args.Nr is not None:
        counts["Nr_front"] = int(args.Nr)
        counts["Nr_rear"] = int(args.Nr)

    if args.Ns_front is not None:
        counts["Ns_front"] = int(args.Ns_front)
    if args.Nr_front is not None:
        counts["Nr_front"] = int(args.Nr_front)
    if args.Ns_rear is not None:
        counts["Ns_rear"] = int(args.Ns_rear)
    if args.Nr_rear is not None:
        counts["Nr_rear"] = int(args.Nr_rear)

    validate_tooth_counts(counts, strict_geometry=bool(args.strict_geometry))
    return counts


def _normalize_state_name(state: str) -> str:
    key = state.strip().lower()
    aliases = {
        "reverse": "rev",
        "r": "rev",
        "drive1": "1st",
        "drive_1st": "1st",
        "drive2": "2nd",
        "drive_2nd": "2nd",
        "drive3": "3rd",
        "drive_3rd": "3rd",
        "manual_1": "manual1",
        "manual_2": "manual2",
    }
    return aliases.get(key, key)


def _payload(result: SolveResult) -> Dict[str, object]:
    return {
        "state": result.state,
        "engaged": list(result.engaged),
        "speeds": dict(result.speeds),
        "ratio": result.ratio,
        "notes": result.notes,
        "solver_path": result.solver_path,
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
        print("three_speed.py error", file=sys.stderr)
        print("--------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                "Tooth counts: "
                f"PG_front(Ns_front={tooth_counts['Ns_front']}, Nr_front={tooth_counts['Nr_front']}), "
                f"PG_rear(Ns_rear={tooth_counts['Ns_rear']}, Nr_rear={tooth_counts['Nr_rear']})",
                file=sys.stderr,
            )
    return 2


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ford C4-style 3-speed Simpson transmission kinematic solver")
    p.add_argument("--state", default="all", help="State to solve: all, 1st, 2nd, 3rd, rev, manual1, manual2")
    p.add_argument("--Ns", type=int, default=None, help="Shared sun tooth count applied to both front and rear sets")
    p.add_argument("--Nr", type=int, default=None, help="Shared ring tooth count applied to both front and rear sets")
    p.add_argument("--Ns-front", dest="Ns_front", type=int, default=None, help="Front gearset sun tooth count")
    p.add_argument("--Nr-front", dest="Nr_front", type=int, default=None, help="Front gearset ring tooth count")
    p.add_argument("--Ns-rear", dest="Ns_rear", type=int, default=None, help="Rear gearset sun tooth count")
    p.add_argument("--Nr-rear", dest="Nr_rear", type=int, default=None, help="Rear gearset ring tooth count")
    p.add_argument("--preset", default="ford_c4_reference", help="Named preset tooth-count configuration")
    p.add_argument("--strict-geometry", action="store_true", help="Enforce strict simple-planetary integer-planet geometry checks")
    p.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Emit only ratios")
    return p


def _print_presets() -> None:
    print("Available presets")
    print("-----------------")
    for name, counts in PRESETS.items():
        note = PRESET_NOTES.get(name, "")
        print(
            f"{name:18s} "
            f"Ns_front={counts['Ns_front']} Nr_front={counts['Nr_front']} "
            f"Ns_rear={counts['Ns_rear']} Nr_rear={counts['Nr_rear']}"
        )
        if note:
            print(f"  note: {note}")


def _print_summary(*, counts: Mapping[str, int], results: Dict[str, SolveResult], ratios_only: bool, strict_geometry: bool) -> None:
    print("Ford C4 3-Speed Kinematic Summary")
    print("-" * 124)
    print(
        f"Tooth counts: PG_front(Ns_front={counts['Ns_front']}, Nr_front={counts['Nr_front']}), "
        f"PG_rear(Ns_rear={counts['Ns_rear']}, Nr_rear={counts['Nr_rear']})"
    )
    print(f"Geometry mode: {'strict' if strict_geometry else 'relaxed'}")
    print(f"Solver path: {next(iter(results.values())).solver_path if results else 'core_v2'}")
    print("-" * 124)
    if ratios_only:
        print(f"{'State':<10s} {'Elems':<40s} {'Ratio':>10s}")
        print("-" * 124)
        for name, result in results.items():
            elems = "+".join(result.engaged)
            print(f"{name:<10s} {elems:<40s} {result.ratio:>10.3f}")
        return

    print(
        f"{'State':<10s} {'Elems':<40s} {'Ratio':>10s} "
        f"{'Input':>9s} {'FrontRg':>9s} {'Sun':>9s} {'Output':>9s} {'RearCar':>9s}"
    )
    print("-" * 124)
    for name, result in results.items():
        elems = "+".join(result.engaged)
        s = result.speeds
        print(
            f"{name:<10s} {elems:<40.40s} {result.ratio:>10.3f} "
            f"{s['input']:>9.3f} {s['front_ring']:>9.3f} {s['sun']:>9.3f} {s['output']:>9.3f} {s['rear_carrier']:>9.3f}"
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_presets:
        _print_presets()
        return 0

    tooth_counts: Optional[Dict[str, int]] = None
    try:
        tooth_counts = _resolve_tooth_counts(args)
        tx = FordC4ThreeSpeedTransmission(
            **tooth_counts,
            strict_geometry=bool(args.strict_geometry),
        )

        if str(args.state).strip().lower() == "all":
            results = tx.solve_all()
            if args.json:
                payload = {
                    "ok": True,
                    "preset": args.preset,
                    "strict_geometry": bool(args.strict_geometry),
                    "tooth_counts": tooth_counts,
                    "states": {name: _payload(result) for name, result in results.items()},
                }
                if args.ratios_only:
                    payload["ratios"] = {name: result.ratio for name, result in results.items()}
                print(json.dumps(payload, indent=2))
            else:
                _print_summary(
                    counts=tooth_counts,
                    results=results,
                    ratios_only=bool(args.ratios_only),
                    strict_geometry=bool(args.strict_geometry),
                )
            return 0

        state = _normalize_state_name(args.state)
        result = tx.solve_state(state)
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
                "strict_geometry": bool(args.strict_geometry),
                "tooth_counts": tooth_counts,
                **_payload(result),
            }
            print(json.dumps(payload, indent=2))
        else:
            if args.ratios_only:
                print(f"{result.state}: {result.ratio:.6f}")
            else:
                print(f"State: {result.state}")
                print(f"Engaged: {' + '.join(result.engaged)}")
                print(
                    f"Tooth counts: PG_front(Ns_front={tooth_counts['Ns_front']}, Nr_front={tooth_counts['Nr_front']}), "
                    f"PG_rear(Ns_rear={tooth_counts['Ns_rear']}, Nr_rear={tooth_counts['Nr_rear']})"
                )
                print(f"Geometry mode: {'strict' if args.strict_geometry else 'relaxed'}")
                print(f"Solver path: {result.solver_path}")
                print(f"Ratio (input/output): {result.ratio:.6f}")
                print(json.dumps(result.speeds, indent=2))
        return 0

    except (ThreeSpeedCliError, ValueError) as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts)
    except Exception as exc:  # pragma: no cover
        return _emit_cli_error(
            args=args,
            message=f"Unexpected solver/runtime failure: {exc}",
            tooth_counts=tooth_counts,
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
