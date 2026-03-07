#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.three_speed

Ford C4-style 3-speed automatic transmission kinematic model.

This module models the classic Simpson-gearset architecture used by the
Ford C4 as described in the project discussion.

Topology
--------
- Two simple planetary gearsets share one common sun gear.
- Front set:
    * ring gear is the primary forward-drive input from the Forward Clutch.
    * carrier is splined to the output shaft.
- Rear set:
    * ring gear is also splined to the same output shaft.
    * carrier is the reaction member, held by the sprag in Drive 1st and by
      the Low/Reverse band in Reverse / Manual 1.
- The shared sun gear is driven by the High/Reverse clutch and held by the
  Intermediate band in 2nd gear.

Equivalent node model used here
-------------------------------
Members:
    input        engine/input shaft
    sun          common sun gear shared by both gearsets
    front_ring   front ring gear
    output       common output shaft = front carrier = rear ring
    rear_carrier rear carrier reaction member

Gearsets:
    PG_front: sun=sun, ring=front_ring, carrier=output
    PG_rear : sun=sun, ring=output,    carrier=rear_carrier

CLI highlights
--------------
- manual tooth-count overrides via:
    * --Ns              apply shared sun count to both sets
    * --Nr              apply ring count to both sets
    * --Nr-front        front ring tooth count only
    * --Nr-rear         rear ring tooth count only
- presets are provided for convenience, but manual flags override presets.
- the historical Ford C4 published tooth counts often cited online
  (Ns=33, Nr=72) are included as a reference-only preset because they fail the
  strict simple-planetary integer-planet geometry check used by PlanetaryGearSet.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

import sympy as sp

try:
    from ..core.clutch import Brake, Clutch, RotatingMember
    from ..core.planetary import PlanetaryGearSet
except Exception:  # pragma: no cover
    try:
        from core.clutch import Brake, Clutch, RotatingMember  # type: ignore
        from core.planetary import PlanetaryGearSet  # type: ignore
    except Exception:  # pragma: no cover
        from clutch import Brake, Clutch, RotatingMember  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore


class ThreeSpeedCliError(ValueError):
    """User-facing CLI/configuration error for three_speed.py."""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    "Ns_front": 33,
    "Nr_front": 72,
    "Ns_rear": 33,
    "Nr_rear": 72,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    # Valid demo preset so the script runs out of the box.
    "simpson_demo": {"Ns_front": 33, "Nr_front": 72, "Ns_rear": 33, "Nr_rear": 72},
    # Reference-only published counts often quoted online for Ford C4. These
    # are intentionally not the default because strict geometry validation fails.
    "ford_c4_reference": {"Ns_front": 33, "Nr_front": 72, "Ns_rear": 33, "Nr_rear": 72},
}

PRESET_NOTES: Mapping[str, str] = {
    "simpson_demo": "Valid demo preset that satisfies integer-planet geometry.",
    "ford_c4_reference": "Published C4 reference counts commonly quoted online; may fail strict geometry validation.",
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


def _validate_simple_planetary_counts(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise ThreeSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise ThreeSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )
    if (Nr - Ns) % 2 != 0:
        raise ThreeSpeedCliError(
            f"Invalid {label} tooth counts: (Nr - Ns) must be even so the implied planet tooth count is an integer. "
            f"Got Ns={Ns}, Nr={Nr}, Nr-Ns={Nr - Ns}."
        )


def validate_tooth_counts(counts: Mapping[str, int]) -> None:
    _validate_simple_planetary_counts(
        Ns=int(counts["Ns_front"]), Nr=int(counts["Nr_front"]), label="Front gearset"
    )
    _validate_simple_planetary_counts(
        Ns=int(counts["Ns_rear"]), Nr=int(counts["Nr_rear"]), label="Rear gearset"
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

    def __init__(self, *, Ns_front: int, Nr_front: int, Ns_rear: int, Nr_rear: int) -> None:
        self.tooth_counts: Dict[str, int] = {
            "Ns_front": int(Ns_front),
            "Nr_front": int(Nr_front),
            "Ns_rear": int(Ns_rear),
            "Nr_rear": int(Nr_rear),
        }
        self._build_topology(**self.tooth_counts)

    def _build_topology(self, *, Ns_front: int, Nr_front: int, Ns_rear: int, Nr_rear: int) -> None:
        self.input = RotatingMember("input")
        self.sun = RotatingMember("sun")
        self.front_ring = RotatingMember("front_ring")
        self.output = RotatingMember("output")
        self.rear_carrier = RotatingMember("rear_carrier")

        self.members: Dict[str, RotatingMember] = {
            "input": self.input,
            "sun": self.sun,
            "front_ring": self.front_ring,
            "output": self.output,
            "rear_carrier": self.rear_carrier,
        }

        self.pg_front = PlanetaryGearSet(
            Ns_front,
            Nr_front,
            name="PG_front",
            sun=self.sun,
            ring=self.front_ring,
            carrier=self.output,
        )
        self.pg_rear = PlanetaryGearSet(
            Ns_rear,
            Nr_rear,
            name="PG_rear",
            sun=self.sun,
            ring=self.output,
            carrier=self.rear_carrier,
        )

        self.forward_clutch = Clutch(self.input, self.front_ring, name="forward_clutch")
        self.high_reverse_clutch = Clutch(self.input, self.sun, name="high_reverse_clutch")
        self.intermediate_band = Brake(self.sun, name="intermediate_band")
        self.low_reverse_band = Brake(self.rear_carrier, name="low_reverse_band")
        self.sprag = Brake(self.rear_carrier, name="sprag")

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

    def _build_equations(self) -> tuple[List[sp.Expr], Dict[str, sp.Symbol]]:
        ws, wfr, wout, wrc = sp.symbols("ws wfr wout wrc", real=True)
        symbols = {
            "sun": ws,
            "front_ring": wfr,
            "output": wout,
            "rear_carrier": wrc,
        }
        eqs: List[sp.Expr] = []
        eqs.append(self.pg_front.Ns * (ws - wout) + self.pg_front.Nr * (wfr - wout))
        eqs.append(self.pg_rear.Ns * (ws - wrc) + self.pg_rear.Nr * (wout - wrc))

        if self.forward_clutch.engaged:
            eqs.append(wfr - 1.0)
        if self.high_reverse_clutch.engaged:
            eqs.append(ws - 1.0)
        if self.intermediate_band.engaged:
            eqs.append(ws)
        if self.low_reverse_band.engaged:
            eqs.append(wrc)
        if self.sprag.engaged and not self.low_reverse_band.engaged:
            eqs.append(wrc)
        return eqs, symbols

    def solve_state(self, state: str) -> SolveResult:
        gs = self.set_state(state)
        eqs, syms = self._build_equations()
        unknowns = [syms["sun"], syms["front_ring"], syms["output"], syms["rear_carrier"]]
        solution = sp.solve(eqs, unknowns, dict=True)
        if not solution:
            raise ThreeSpeedCliError(f"No kinematic solution found for state {gs.name}.")
        sol = solution[0]
        speeds = {
            "input": 1.0,
            "sun": float(sp.N(sol[syms["sun"]])),
            "front_ring": float(sp.N(sol[syms["front_ring"]])),
            "output": float(sp.N(sol[syms["output"]])),
            "rear_carrier": float(sp.N(sol[syms["rear_carrier"]])),
        }
        if abs(speeds["output"]) < 1e-12:
            raise ThreeSpeedCliError(f"Output speed is zero for state {gs.name}; ratio is undefined.")
        ratio = 1.0 / speeds["output"]
        return SolveResult(gs.name, gs.engaged, speeds, ratio, gs.notes)

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

    # Shared aliases.
    if args.Ns is not None:
        counts["Ns_front"] = int(args.Ns)
        counts["Ns_rear"] = int(args.Ns)
    if args.Nr is not None:
        counts["Nr_front"] = int(args.Nr)
        counts["Nr_rear"] = int(args.Nr)

    # Component-specific overrides win over shared aliases.
    if args.Ns_front is not None:
        counts["Ns_front"] = int(args.Ns_front)
    if args.Nr_front is not None:
        counts["Nr_front"] = int(args.Nr_front)
    if args.Ns_rear is not None:
        counts["Ns_rear"] = int(args.Ns_rear)
    if args.Nr_rear is not None:
        counts["Nr_rear"] = int(args.Nr_rear)

    validate_tooth_counts(counts)
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
    }


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
    p.add_argument("--preset", default="simpson_demo", help="Named preset tooth-count configuration")
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


def _print_summary(*, counts: Mapping[str, int], results: Dict[str, SolveResult], ratios_only: bool) -> None:
    print("Ford C4 3-Speed Kinematic Summary")
    print("-" * 124)
    print(
        f"Tooth counts: PG_front(Ns_front={counts['Ns_front']}, Nr_front={counts['Nr_front']}), "
        f"PG_rear(Ns_rear={counts['Ns_rear']}, Nr_rear={counts['Nr_rear']})"
    )
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
        tx = FordC4ThreeSpeedTransmission(**tooth_counts)

        if str(args.state).strip().lower() == "all":
            results = tx.solve_all()
            if args.json:
                payload = {
                    "ok": True,
                    "preset": args.preset,
                    "tooth_counts": tooth_counts,
                    "states": {name: _payload(result) for name, result in results.items()},
                }
                if args.ratios_only:
                    payload["ratios"] = {name: result.ratio for name, result in results.items()}
                print(json.dumps(payload, indent=2))
            else:
                _print_summary(counts=tooth_counts, results=results, ratios_only=bool(args.ratios_only))
            return 0

        state = _normalize_state_name(args.state)
        result = tx.solve_state(state)
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
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
