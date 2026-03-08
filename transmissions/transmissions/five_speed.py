#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.five_speed

Mercedes-Benz W5A-580 / 722.6-family 5-speed automatic transmission
kinematic model using the shared Core V2 transmission objects.

Core V2 refactor
----------------
This version is intentionally built on the reusable transmission core stack:
- core.planetary.PlanetaryGearSet
- core.clutch.{RotatingMember, Clutch, Brake, Sprag}
- core.solver.TransmissionSolver

Reference topology from the provided W5A-580 description
--------------------------------------------------------
The transmission is modeled as three simple planetary gearsets in cascade:

Forward set:
    - ring     = input / turbine
    - sun      = forward_sun
    - carrier  = forward_carrier

Rear set:
    - ring     = forward_carrier
    - sun      = rear_sun
    - carrier  = rear_carrier

Middle set:
    - ring     = rear_carrier
    - sun      = middle_sun
    - carrier  = output

Shift elements:
    C1 : input ↔ forward_sun
    C2 : input ↔ rear_carrier
    C3 : rear_sun ↔ middle_sun
    B1 : forward_sun → ground
    B2 : middle_sun → ground
    BR : rear_carrier → ground
    F1 : forward_sun one-way hold
    F2 : rear_sun one-way hold

Design note
-----------
This is a legitimate Core V2 kinematic reconstruction, not a hardcoded-ratio
script. The tooth counts remain a fitted candidate set chosen to reproduce the
published W5A-580 ratio spread closely; they are not claimed to be OEM-
confirmed geometry data.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

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


class FiveSpeedCliError(ValueError):
    """User-facing CLI/configuration error for five_speed.py."""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
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
    "w5a580_candidate": (
        "Candidate tooth-count set fitted to the published W5A-580 ratio spread; "
        "not claimed as OEM-confirmed tooth data."
    ),
}


@dataclass(frozen=True)
class GearState:
    name: str
    active_constraints: tuple[str, ...]
    display_elements: tuple[str, ...]
    notes: str = ""
    manual_neutral: bool = False


@dataclass(frozen=True)
class SolveResult:
    state: str
    engaged: tuple[str, ...]
    speeds: Dict[str, float]
    ratio: float
    notes: str = ""
    solver_path: str = "core_v2"


def _validate_counts_basic(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise FiveSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise FiveSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )


def _validate_counts_strict(*, Ns: int, Nr: int, label: str) -> None:
    _validate_counts_basic(Ns=Ns, Nr=Nr, label=label)
    if (Nr - Ns) % 2 != 0:
        raise FiveSpeedCliError(
            f"Invalid {label} tooth counts under strict geometry mode: (Nr - Ns) must be even so the implied "
            f"planet tooth count is an integer. Got Ns={Ns}, Nr={Nr}, Nr-Ns={Nr - Ns}."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    validator = _validate_counts_strict if strict_geometry else _validate_counts_basic
    validator(Ns=int(counts["Ns_f"]), Nr=int(counts["Nr_f"]), label="Forward gearset")
    validator(Ns=int(counts["Ns_r"]), Nr=int(counts["Nr_r"]), label="Rear gearset")
    validator(Ns=int(counts["Ns_m"]), Nr=int(counts["Nr_m"]), label="Middle gearset")


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

    return PlanetaryGearSet(
        Ns=Ns,
        Nr=Nr,
        name=name,
        sun=sun,
        ring=ring,
        carrier=carrier,
    )


class MercedesW5A580FiveSpeedTransmission:
    """Three-simple-planetary W5A-580 style transmission model on Core V2."""

    SHIFT_SCHEDULE: Mapping[str, GearState] = {
        "1st": GearState(
            name="1st",
            active_constraints=("C3", "B1", "B2", "F1", "F2"),
            display_elements=("C3(overrun)", "B1(overrun)", "B2", "F1", "F2"),
            notes=(
                "Forward, rear, and middle suns are all held; the three planetary sets reduce speed in cascade."
            ),
        ),
        "2nd": GearState(
            name="2nd",
            active_constraints=("C1", "C3", "B2", "F2"),
            display_elements=("C1", "C3(overrun)", "B2", "F2"),
            notes=(
                "C1 locks the forward set so it rotates as a block; rear and middle sets still provide reduction."
            ),
        ),
        "3rd": GearState(
            name="3rd",
            active_constraints=("C1", "C2", "B2"),
            display_elements=("C1", "C2", "B2"),
            notes="Drive reaches the middle ring directly through C2; the ratio occurs only through the middle set.",
        ),
        "4th": GearState(
            name="4th",
            active_constraints=("C1", "C2", "C3"),
            display_elements=("C1", "C2", "C3"),
            notes="All three planetary gearsets are locked; direct drive.",
        ),
        "5th": GearState(
            name="5th",
            active_constraints=("C2", "C3", "B1"),
            display_elements=("C2", "C3", "B1", "F1(overrun)"),
            notes=(
                "The forward set is shifted like 1st while C2 drives the rear-carrier/middle-ring node, producing overdrive."
            ),
        ),
        "R1": GearState(
            name="R1",
            active_constraints=("C3", "BR", "F1", "B1"),
            display_elements=("C3(overrun)", "B1(overrun)", "BR", "F1", "F2"),
            notes=(
                "Forward set reduced speed feeds the rear ring while BR grounds the rear-carrier/middle-ring node; output reverses."
            ),
        ),
        "R2": GearState(
            name="R2",
            active_constraints=("C1", "C3", "BR"),
            display_elements=("C1", "C3(overrun)", "BR", "F2"),
            notes="Second reverse analogous to second gear with BR grounding the rear-carrier/middle-ring node.",
        ),
        "N": GearState(
            name="N",
            active_constraints=("C3", "B1"),
            display_elements=("C3", "B1"),
            notes="Neutral is reported by operating convention; output is shown stationary.",
            manual_neutral=True,
        ),
    }

    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "R1", "R2", "N")

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
        "r2": "R2",
        "rev2": "R2",
        "reverse2": "R2",
        "reverse_2": "R2",
        "n": "N",
        "neutral": "N",
    }

    def __init__(
        self,
        *,
        Ns_f: int,
        Nr_f: int,
        Ns_r: int,
        Nr_r: int,
        Ns_m: int,
        Nr_m: int,
        strict_geometry: bool = True,
    ) -> None:
        self.strict_geometry = bool(strict_geometry)
        self.tooth_counts: Dict[str, int] = {
            "Ns_f": int(Ns_f),
            "Nr_f": int(Nr_f),
            "Ns_r": int(Ns_r),
            "Nr_r": int(Nr_r),
            "Ns_m": int(Ns_m),
            "Nr_m": int(Nr_m),
        }
        self._build_topology(**self.tooth_counts)

    @classmethod
    def normalize_state_name(cls, state: str) -> str:
        key = state.strip().lower()
        if key == "all":
            return "all"
        if key not in cls.STATE_ALIASES:
            raise FiveSpeedCliError(
                f"Unknown state: {state}. Valid states are 1st, 2nd, 3rd, 4th, 5th, R1, R2, N, or all."
            )
        return cls.STATE_ALIASES[key]

    def _build_topology(self, *, Ns_f: int, Nr_f: int, Ns_r: int, Nr_r: int, Ns_m: int, Nr_m: int) -> None:
        self.input = RotatingMember("input")
        self.forward_sun = RotatingMember("forward_sun")
        self.forward_carrier = RotatingMember("forward_carrier")
        self.rear_sun = RotatingMember("rear_sun")
        self.rear_carrier = RotatingMember("rear_carrier")
        self.middle_sun = RotatingMember("middle_sun")
        self.output = RotatingMember("output")

        self.members: Dict[str, RotatingMember] = {
            "input": self.input,
            "forward_sun": self.forward_sun,
            "forward_carrier": self.forward_carrier,
            "rear_sun": self.rear_sun,
            "rear_carrier": self.rear_carrier,
            "middle_sun": self.middle_sun,
            "output": self.output,
        }

        self.pg_forward = _make_planetary(
            Ns=Ns_f,
            Nr=Nr_f,
            name="PG_forward",
            sun=self.forward_sun,
            ring=self.input,
            carrier=self.forward_carrier,
            strict_geometry=self.strict_geometry,
        )
        self.pg_rear = _make_planetary(
            Ns=Ns_r,
            Nr=Nr_r,
            name="PG_rear",
            sun=self.rear_sun,
            ring=self.forward_carrier,
            carrier=self.rear_carrier,
            strict_geometry=self.strict_geometry,
        )
        self.pg_middle = _make_planetary(
            Ns=Ns_m,
            Nr=Nr_m,
            name="PG_middle",
            sun=self.middle_sun,
            ring=self.rear_carrier,
            carrier=self.output,
            strict_geometry=self.strict_geometry,
        )
        self.gearsets: List[PlanetaryGearSet] = [self.pg_forward, self.pg_rear, self.pg_middle]

        self.C1 = Clutch(self.input, self.forward_sun, name="C1")
        self.C2 = Clutch(self.input, self.rear_carrier, name="C2")
        self.C3 = Clutch(self.rear_sun, self.middle_sun, name="C3")
        self.B1 = Brake(self.forward_sun, name="B1")
        self.B2 = Brake(self.middle_sun, name="B2")
        self.BR = Brake(self.rear_carrier, name="BR")
        self.F1 = Sprag(self.forward_sun, hold_direction="negative", name="F1")
        self.F2 = Sprag(self.rear_sun, hold_direction="negative", name="F2")

        self.constraints: Dict[str, object] = {
            "C1": self.C1,
            "C2": self.C2,
            "C3": self.C3,
            "B1": self.B1,
            "B2": self.B2,
            "BR": self.BR,
            "F1": self.F1,
            "F2": self.F2,
        }

    def release_all(self) -> None:
        for c in self.constraints.values():
            c.release()  # type: ignore[attr-defined]

    def set_state(self, state: str) -> GearState:
        key = self.normalize_state_name(state)
        if key == "all":
            raise FiveSpeedCliError("Use solve_all() when state='all'.")
        gs = self.SHIFT_SCHEDULE[key]
        self.release_all()
        for name in gs.active_constraints:
            self.constraints[name].engage()  # type: ignore[attr-defined]
        return gs

    def _solve_core_v2(self, *, input_speed: float) -> Dict[str, float]:
        solver = TransmissionSolver()

        if hasattr(solver, "add_members"):
            solver.add_members(self.members.values())  # type: ignore[attr-defined]
        else:
            for member in self.members.values():
                solver.add_member(member)

        solver.add_gearset(self.pg_forward)
        solver.add_gearset(self.pg_rear)
        solver.add_gearset(self.pg_middle)

        solver.add_clutch(self.C1)
        solver.add_clutch(self.C2)
        solver.add_clutch(self.C3)
        solver.add_brake(self.B1)
        solver.add_brake(self.B2)
        solver.add_brake(self.BR)
        solver.add_brake(self.F1)  # type: ignore[arg-type]
        solver.add_brake(self.F2)  # type: ignore[arg-type]

        if hasattr(solver, "solve_report"):
            report = solver.solve_report(input_member="input", input_speed=float(input_speed))  # type: ignore[attr-defined]
            if not getattr(report, "ok", False):
                message = getattr(getattr(report, "classification", None), "message", "Solver failed")
                raise FiveSpeedCliError(str(message))
            speeds = dict(report.member_speeds)  # type: ignore[attr-defined]
        else:
            speeds = dict(solver.solve("input", float(input_speed)))

        if "input" not in speeds:
            speeds["input"] = float(input_speed)
        return {name: float(value) for name, value in speeds.items()}

    def solve_state(self, state: str, *, input_speed: float = 1.0) -> SolveResult:
        gs = self.set_state(state)

        if gs.manual_neutral:
            speeds = {
                "input": float(input_speed),
                "forward_sun": 0.0,
                "forward_carrier": 0.0,
                "rear_sun": 0.0,
                "rear_carrier": 0.0,
                "middle_sun": 0.0,
                "output": 0.0,
            }
            return SolveResult(gs.name, gs.display_elements, speeds, 0.0, gs.notes, solver_path="core_v2")

        speeds = self._solve_core_v2(input_speed=float(input_speed))

        if abs(float(speeds["output"])) < 1.0e-12:
            raise FiveSpeedCliError(f"Output speed is zero for state {gs.name}; ratio is undefined.")

        ratio_signed = float(input_speed) / float(speeds["output"])
        ratio = ratio_signed if gs.name in {"R1", "R2"} else abs(ratio_signed)
        display_speeds = {
            "input": float(speeds["input"]),
            "forward_sun": float(speeds["forward_sun"]),
            "forward_carrier": float(speeds["forward_carrier"]),
            "rear_sun": float(speeds["rear_sun"]),
            "rear_carrier": float(speeds["rear_carrier"]),
            "middle_sun": float(speeds["middle_sun"]),
            "output": float(speeds["output"]),
        }
        return SolveResult(gs.name, gs.display_elements, display_speeds, float(ratio), gs.notes, solver_path="core_v2")

    def solve_all(self, *, input_speed: float = 1.0) -> Dict[str, SolveResult]:
        return {state: self.solve_state(state, input_speed=float(input_speed)) for state in self.DISPLAY_ORDER}


def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    if args.preset is None:
        counts = dict(DEFAULT_TOOTH_COUNTS)
    else:
        if args.preset not in PRESETS:
            valid = ", ".join(sorted(PRESETS))
            raise FiveSpeedCliError(f"Unknown preset: {args.preset}. Valid presets: {valid}")
        counts = dict(PRESETS[args.preset])

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

    validate_tooth_counts(counts, strict_geometry=bool(args.strict_geometry))
    return counts


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
        print("five_speed.py error", file=sys.stderr)
        print("-------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                "Tooth counts: "
                f"Forward(Ns_f={tooth_counts['Ns_f']}, Nr_f={tooth_counts['Nr_f']}), "
                f"Rear(Ns_r={tooth_counts['Ns_r']}, Nr_r={tooth_counts['Nr_r']}), "
                f"Middle(Ns_m={tooth_counts['Ns_m']}, Nr_m={tooth_counts['Nr_m']})",
                file=sys.stderr,
            )
    return 2


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Mercedes-Benz W5A-580 5-speed automatic transmission kinematic solver")
    p.add_argument("--state", default="all", help="State to solve: all, 1st, 2nd, 3rd, 4th, 5th, R1, R2, N")
    p.add_argument("--preset", default="w5a580_candidate", help="Named tooth-count configuration")
    p.add_argument("--strict-geometry", action="store_true", help="Enforce strict simple-planetary integer-planet geometry checks")
    p.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Emit only ratios")
    p.add_argument("--Ns-f", dest="Ns_f", type=int, default=None, help="Forward gearset sun tooth count")
    p.add_argument("--Nr-f", dest="Nr_f", type=int, default=None, help="Forward gearset ring tooth count")
    p.add_argument("--Ns-r", dest="Ns_r", type=int, default=None, help="Rear gearset sun tooth count")
    p.add_argument("--Nr-r", dest="Nr_r", type=int, default=None, help="Rear gearset ring tooth count")
    p.add_argument("--Ns-m", dest="Ns_m", type=int, default=None, help="Middle gearset sun tooth count")
    p.add_argument("--Nr-m", dest="Nr_m", type=int, default=None, help="Middle gearset ring tooth count")
    return p


def _print_presets() -> None:
    print("Available presets")
    print("-----------------")
    for name, counts in PRESETS.items():
        note = PRESET_NOTES.get(name, "")
        print(
            f"{name:18s} "
            f"Ns_f={counts['Ns_f']} Nr_f={counts['Nr_f']} "
            f"Ns_r={counts['Ns_r']} Nr_r={counts['Nr_r']} "
            f"Ns_m={counts['Ns_m']} Nr_m={counts['Nr_m']}"
        )
        if note:
            print(f"  note: {note}")


def _print_summary(*, counts: Mapping[str, int], results: Dict[str, SolveResult], ratios_only: bool, strict_geometry: bool, preset: Optional[str]) -> None:
    print("Tooth Counts")
    print("------------------------------------------------------------")
    print(f"Forward set: Ns_f={counts['Ns_f']}, Nr_f={counts['Nr_f']}")
    print(f"Rear set   : Ns_r={counts['Ns_r']}, Nr_r={counts['Nr_r']}")
    print(f"Middle set : Ns_m={counts['Ns_m']}, Nr_m={counts['Nr_m']}")
    if preset and preset in PRESET_NOTES:
        print(f"Preset note: {PRESET_NOTES[preset]}")
    print()

    print("Mercedes-Benz W5A-580 5-Speed Kinematic Summary")
    print("-" * 144)
    print(f"Geometry mode: {'strict' if strict_geometry else 'relaxed'}")
    print(f"Solver path: {next(iter(results.values())).solver_path if results else 'core_v2'}")
    print("-" * 144)
    if ratios_only:
        print(f"{'State':<6s} {'Elems':<34s} {'Ratio':>10s}")
        print("-" * 144)
        for state, result in results.items():
            elems = "+".join(result.engaged)
            print(f"{state:<6s} {elems:<34s} {result.ratio:>10.3f}")
        return

    print(
        f"{'State':<6s} {'Elems':<34s} {'Ratio':>8s} "
        f"{'Input':>9s} {'F.sun':>9s} {'F.car':>9s} {'R.sun':>9s} {'R.car':>9s} {'M.sun':>9s} {'Out':>9s}"
    )
    print("-" * 144)
    for state, result in results.items():
        s = result.speeds
        print(
            f"{state:<6s} {'+'.join(result.engaged):<34s} "
            f"{result.ratio:>8.3f} "
            f"{s['input']:>9.3f} "
            f"{s['forward_sun']:>9.3f} "
            f"{s['forward_carrier']:>9.3f} "
            f"{s['rear_sun']:>9.3f} "
            f"{s['rear_carrier']:>9.3f} "
            f"{s['middle_sun']:>9.3f} "
            f"{s['output']:>9.3f}"
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_presets:
        if args.json:
            payload = {
                name: {
                    "tooth_counts": dict(values),
                    "note": PRESET_NOTES.get(name, ""),
                }
                for name, values in PRESETS.items()
            }
            print(json.dumps(payload, indent=2))
        else:
            _print_presets()
        return 0

    tooth_counts: Dict[str, int] = {}
    try:
        tooth_counts = _resolve_tooth_counts(args)
        tx = MercedesW5A580FiveSpeedTransmission(
            **tooth_counts,
            strict_geometry=bool(args.strict_geometry),
        )
        normalized = tx.normalize_state_name(args.state)

        if normalized == "all":
            results = tx.solve_all()
            if args.json:
                payload: Dict[str, object] = {
                    "ok": True,
                    "preset": args.preset,
                    "preset_note": PRESET_NOTES.get(args.preset, ""),
                    "strict_geometry": bool(args.strict_geometry),
                    "tooth_counts": tooth_counts,
                    "results": {state: _payload(result) for state, result in results.items()},
                }
                if args.ratios_only:
                    payload = {
                        "ok": True,
                        "preset": args.preset,
                        "preset_note": PRESET_NOTES.get(args.preset, ""),
                        "strict_geometry": bool(args.strict_geometry),
                        "tooth_counts": tooth_counts,
                        "ratios": {state: results[state].ratio for state in tx.DISPLAY_ORDER},
                    }
                print(json.dumps(payload, indent=2))
                return 0

            _print_summary(
                counts=tooth_counts,
                results=results,
                ratios_only=bool(args.ratios_only),
                strict_geometry=bool(args.strict_geometry),
                preset=args.preset,
            )
            return 0

        result = tx.solve_state(normalized)
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
                "preset_note": PRESET_NOTES.get(args.preset, ""),
                "strict_geometry": bool(args.strict_geometry),
                "tooth_counts": tooth_counts,
                "result": _payload(result),
            }
            if args.ratios_only:
                payload = {
                    "ok": True,
                    "preset": args.preset,
                    "preset_note": PRESET_NOTES.get(args.preset, ""),
                    "strict_geometry": bool(args.strict_geometry),
                    "tooth_counts": tooth_counts,
                    "state": result.state,
                    "ratio": result.ratio,
                }
            print(json.dumps(payload, indent=2))
            return 0

        _print_summary(
            counts=tooth_counts,
            results={result.state: result},
            ratios_only=bool(args.ratios_only),
            strict_geometry=bool(args.strict_geometry),
            preset=args.preset,
        )
        return 0

    except FiveSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts or None)
    except Exception as exc:
        return _emit_cli_error(args=args, message=f"Unexpected runtime failure: {exc}", tooth_counts=tooth_counts or None)


if __name__ == "__main__":
    raise SystemExit(main())
