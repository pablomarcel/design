#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.four_speed

Ravigneaux 4-speed automatic transmission kinematic model.

Core V2 refactor
----------------
This version is refactored to match the newer transmission-script patterns:
- upgraded CLI with tooth-count overrides and presets
- graceful exception handling
- explicit geometry mode reporting
- explicit solver path reporting
- upgraded core shift-element abstractions:
    * core.clutch.{RotatingMember, Clutch, Brake}

Important design note
---------------------
Unlike the refactored Ford C4 / Allison scripts, this model does NOT solve
through core.solver.TransmissionSolver because Core V2 currently understands
simple planetary gearsets, while this Ravigneaux transmission is modeled via
its own central-member equations.

So this script uses:
- upgraded core objects for members and shift elements
- a local symbolic solve path for the Ravigneaux central-member kinematics

If this script reports:
    Solver path: ravigneaux_local_core_v2
then it is working as intended for the current project architecture.

Modeled members
---------------
- sun_small
- sun_large
- ring
- carrier

Output convention
-----------------
The ring gear is always the output member for this transmission model.

Kinematic relations
-------------------
The present project model uses the following two central-member relations:

    Ns_small * (w_small - w_carrier) - Nr * (w_ring - w_carrier) = 0
    Ns_large * (w_large - w_carrier) + Nr * (w_ring - w_carrier) = 0

These signs reflect the two different mesh paths in the simplified
Ravigneaux central-member abstraction used by this app.

Standard states
---------------
1st:
    carrier fixed, small sun input, ring output
2nd:
    large sun fixed, small sun input, ring output
3rd:
    direct clutch locks ring and carrier, ring input, ring output
4th:
    large sun fixed, carrier input, ring output
Rev:
    carrier fixed, large sun input, ring output
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
except Exception:  # pragma: no cover
    try:
        from core.clutch import Brake, Clutch, RotatingMember  # type: ignore
    except Exception:  # pragma: no cover
        from clutch import Brake, Clutch, RotatingMember  # type: ignore


class FourSpeedCliError(ValueError):
    """User-facing CLI/configuration error for four_speed.py."""


@dataclass(frozen=True)
class GearState:
    name: str
    engaged: tuple[str, ...]
    input_member: str
    output_member: str = "ring"
    notes: str = ""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    # Demo values chosen to land near the screenshot-style ratios.
    "Ns_small": 22,
    "Ns_large": 44,
    "Nr": 70,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "ravigneaux_demo": {
        "Ns_small": 22,
        "Ns_large": 44,
        "Nr": 70,
    },
}

PRESET_NOTES: Mapping[str, str] = {
    "ravigneaux_demo": "Demo set that lands near the screenshot-style ratios for the current simplified Ravigneaux model.",
}


def _validate_counts_basic(*, Ns_small: int, Ns_large: int, Nr: int) -> None:
    if Ns_small <= 0 or Ns_large <= 0 or Nr <= 0:
        raise FourSpeedCliError("Tooth counts must all be positive integers.")
    if Ns_large <= Ns_small:
        raise FourSpeedCliError(
            f"Expected large sun teeth > small sun teeth. Got Ns_small={Ns_small}, Ns_large={Ns_large}."
        )
    if Nr <= Ns_large:
        raise FourSpeedCliError(
            f"Expected ring teeth > large sun teeth. Got Ns_large={Ns_large}, Nr={Nr}."
        )


def _validate_counts_strict(*, Ns_small: int, Ns_large: int, Nr: int) -> None:
    _validate_counts_basic(Ns_small=Ns_small, Ns_large=Ns_large, Nr=Nr)
    if (Nr - Ns_small) % 2 != 0:
        raise FourSpeedCliError(
            f"Invalid small-sun branch under strict geometry mode: (Nr - Ns_small) must be even. "
            f"Got Ns_small={Ns_small}, Nr={Nr}, Nr-Ns_small={Nr - Ns_small}."
        )
    if (Nr - Ns_large) % 2 != 0:
        raise FourSpeedCliError(
            f"Invalid large-sun branch under strict geometry mode: (Nr - Ns_large) must be even. "
            f"Got Ns_large={Ns_large}, Nr={Nr}, Nr-Ns_large={Nr - Ns_large}."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    Ns_small = int(counts["Ns_small"])
    Ns_large = int(counts["Ns_large"])
    Nr = int(counts["Nr"])
    if strict_geometry:
        _validate_counts_strict(Ns_small=Ns_small, Ns_large=Ns_large, Nr=Nr)
    else:
        _validate_counts_basic(Ns_small=Ns_small, Ns_large=Ns_large, Nr=Nr)


class RavigneauxFourSpeedTransmission:
    """Single-Ravigneaux 4-speed automatic transmission model."""

    SHIFT_SCHEDULE: Mapping[str, Dict[str, object]] = {
        "1st": {
            "input": "sun_small",
            "elements": ("B_carrier",),
            "notes": "Carrier fixed, small sun input, ring output",
        },
        "2nd": {
            "input": "sun_small",
            "elements": ("B_large",),
            "notes": "Large sun fixed, small sun input, ring output",
        },
        "3rd": {
            "input": "ring",
            "elements": ("C_direct",),
            "notes": "Gearset locked as a unit, direct drive",
        },
        "4th": {
            "input": "carrier",
            "elements": ("B_large",),
            "notes": "Large sun fixed, carrier input, ring output (overdrive)",
        },
        "rev": {
            "input": "sun_large",
            "elements": ("B_carrier",),
            "notes": "Carrier fixed, large sun input, ring output",
        },
        "reverse": {
            "input": "sun_large",
            "elements": ("B_carrier",),
            "notes": "Carrier fixed, large sun input, ring output",
        },
    }

    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "rev")

    def __init__(self, *, Ns_small: int, Ns_large: int, Nr: int, strict_geometry: bool = False) -> None:
        self.strict_geometry = bool(strict_geometry)
        self.tooth_counts: Dict[str, int] = {
            "Ns_small": int(Ns_small),
            "Ns_large": int(Ns_large),
            "Nr": int(Nr),
        }
        validate_tooth_counts(self.tooth_counts, strict_geometry=self.strict_geometry)
        self._build_topology(**self.tooth_counts)

    def _build_topology(self, *, Ns_small: int, Ns_large: int, Nr: int) -> None:
        self.sun_small = RotatingMember("sun_small")
        self.sun_large = RotatingMember("sun_large")
        self.ring = RotatingMember("ring")
        self.carrier = RotatingMember("carrier")

        self.members: Dict[str, RotatingMember] = {
            "sun_small": self.sun_small,
            "sun_large": self.sun_large,
            "ring": self.ring,
            "carrier": self.carrier,
        }

        self.Ns_small = int(Ns_small)
        self.Ns_large = int(Ns_large)
        self.Nr = int(Nr)

        self.B_carrier = Brake(self.carrier, name="B_carrier")
        self.B_large = Brake(self.sun_large, name="B_large")
        self.C_direct = Clutch(self.ring, self.carrier, name="C_direct")

        self.constraints: Dict[str, object] = {
            "B_carrier": self.B_carrier,
            "B_large": self.B_large,
            "C_direct": self.C_direct,
        }

    def release_all(self) -> None:
        for c in self.constraints.values():
            c.release()  # type: ignore[attr-defined]

    def set_state(self, state: str) -> GearState:
        key = state.strip().lower()
        if key not in self.SHIFT_SCHEDULE:
            raise FourSpeedCliError(f"Unknown state: {state}")
        self.release_all()
        spec = self.SHIFT_SCHEDULE[key]
        engaged = tuple(spec["elements"])
        for name in engaged:
            self.constraints[name].engage()  # type: ignore[attr-defined]
        display = "Rev" if key in {"rev", "reverse"} else state.strip()
        return GearState(
            display,
            engaged,
            input_member=str(spec["input"]),
            notes=str(spec.get("notes", "")),
        )

    def _symbols(self) -> Dict[str, sp.Symbol]:
        return {name: sp.Symbol(f"w_{name}", real=True) for name in self.members}

    def _ravigneaux_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        ws = symbols["sun_small"]
        wl = symbols["sun_large"]
        wr = symbols["ring"]
        wc = symbols["carrier"]

        return [
            self.Ns_small * (ws - wc) - self.Nr * (wr - wc),
            self.Ns_large * (wl - wc) + self.Nr * (wr - wc),
        ]

    def _constraint_equations(self, symbols: Mapping[str, sp.Symbol], *, input_member: str, input_speed: float) -> List[sp.Expr]:
        eqs: List[sp.Expr] = []
        if self.B_carrier.engaged:
            eqs.append(symbols["carrier"])
        if self.B_large.engaged:
            eqs.append(symbols["sun_large"])
        if self.C_direct.engaged:
            eqs.append(symbols["ring"] - symbols["carrier"])
        if input_member not in symbols:
            raise FourSpeedCliError(f"Unknown input member: {input_member}")
        eqs.append(symbols[input_member] - float(input_speed))
        return eqs

    def _solve_local(self, *, input_member: str, input_speed: float) -> Dict[str, float]:
        syms = self._symbols()
        eqs = self._ravigneaux_equations(syms) + self._constraint_equations(syms, input_member=input_member, input_speed=input_speed)
        unknowns = [syms["sun_small"], syms["sun_large"], syms["ring"], syms["carrier"]]
        sols = sp.solve(eqs, unknowns, dict=True)
        if not sols:
            raise FourSpeedCliError("No kinematic solution found for this state.")
        sol = sols[0]
        unresolved = [sym for sym in unknowns if sym not in sol]
        if unresolved:
            names = ", ".join(str(sym) for sym in unresolved)
            raise FourSpeedCliError(f"Underdetermined kinematic solution: {names}")
        return {
            "sun_small": float(sp.N(sol[syms["sun_small"]])),
            "sun_large": float(sp.N(sol[syms["sun_large"]])),
            "ring": float(sp.N(sol[syms["ring"]])),
            "carrier": float(sp.N(sol[syms["carrier"]])),
        }

    def solve_state(self, state: str, input_speed: float = 1.0) -> Dict[str, object]:
        info = self.set_state(state)
        speeds = self._solve_local(input_member=info.input_member, input_speed=float(input_speed))
        output_speed = float(speeds[info.output_member])
        if abs(output_speed) < 1.0e-12:
            raise FourSpeedCliError(f"Output speed is zero for state {info.name}; ratio is undefined.")
        ratio = float(input_speed) / output_speed
        ordered_speeds = {
            "input": float(input_speed),
            "sun_small": float(speeds["sun_small"]),
            "sun_large": float(speeds["sun_large"]),
            "ring": float(speeds["ring"]),
            "carrier": float(speeds["carrier"]),
        }
        return {
            "state": info.name,
            "engaged": list(info.engaged),
            "input_member": info.input_member,
            "output_member": info.output_member,
            "speeds": ordered_speeds,
            "ratio": ratio,
            "notes": info.notes,
            "solver_path": "ravigneaux_local_core_v2",
        }

    def solve_all(self, input_speed: float = 1.0) -> Dict[str, Dict[str, object]]:
        out: Dict[str, Dict[str, object]] = {}
        for state in self.DISPLAY_ORDER:
            label = "Rev" if state == "rev" else state
            out[label] = self.solve_state(state, input_speed=input_speed)
        return out

    def topology_description(self) -> str:
        return (
            "Ravigneaux 4-Speed Topology\n"
            "--------------------------\n"
            "Members: sun_small, sun_large, ring, carrier\n"
            "Output member: ring\n"
            "Shift elements:\n"
            "  B_carrier : carrier -> ground\n"
            "  B_large   : sun_large -> ground\n"
            "  C_direct  : ring <-> carrier\n"
            "States:\n"
            "  1st : B_carrier, input=sun_small, output=ring\n"
            "  2nd : B_large,   input=sun_small, output=ring\n"
            "  3rd : C_direct,  input=ring,      output=ring\n"
            "  4th : B_large,   input=carrier,   output=ring\n"
            "  Rev : B_carrier, input=sun_large, output=ring\n"
            "Kinematics: simplified Ravigneaux central-member equations\n"
            "Solver path: ravigneaux_local_core_v2"
        )

    def tooth_count_summary(self) -> str:
        c = self.tooth_counts
        mode = "strict" if self.strict_geometry else "relaxed"
        return (
            f"Tooth counts: Ns_small={c['Ns_small']}, Ns_large={c['Ns_large']}, Nr={c['Nr']}\n"
            f"Geometry mode: {mode}\n"
            "Solver path: ravigneaux_local_core_v2"
        )

    def summary_table(self, input_speed: float = 1.0) -> str:
        results = self.solve_all(input_speed=input_speed)
        lines = [
            "Ravigneaux 4-Speed Kinematic Summary",
            "-" * 116,
            self.tooth_count_summary(),
            "-" * 116,
            f"{'State':<10s} {'Elems':<24s} {'Ratio':>10s} {'Input':>9s} {'SmallSun':>9s} {'LargeSun':>9s} {'Ring':>9s} {'Carrier':>9s}",
            "-" * 116,
        ]
        for label in ("1st", "2nd", "3rd", "4th", "Rev"):
            r = results[label]
            elems = "+".join(r["engaged"])
            s = r["speeds"]
            lines.append(
                f"{label:<10s} {elems:<24.24s} {r['ratio']:>10.3f} "
                f"{s['input']:>9.3f} {s['sun_small']:>9.3f} {s['sun_large']:>9.3f} {s['ring']:>9.3f} {s['carrier']:>9.3f}"
            )
        return "\n".join(lines)

    def ratio_table(self, input_speed: float = 1.0) -> str:
        results = self.solve_all(input_speed=input_speed)
        lines = [
            "Ravigneaux 4-Speed Ratio Summary",
            "-" * 52,
            self.tooth_count_summary(),
            "-" * 52,
            f"{'State':<10s} {'Elems':<24s} {'Ratio':>10s}",
            "-" * 52,
        ]
        for label in ("1st", "2nd", "3rd", "4th", "Rev"):
            r = results[label]
            elems = "+".join(r["engaged"])
            lines.append(f"{label:<10s} {elems:<24.24s} {r['ratio']:>10.3f}")
        return "\n".join(lines)


def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    if args.preset not in PRESETS:
        valid = ", ".join(sorted(PRESETS))
        raise FourSpeedCliError(f"Unknown preset: {args.preset}. Valid presets: {valid}")
    counts = dict(PRESETS[args.preset])

    if args.Ns_small is not None:
        counts["Ns_small"] = int(args.Ns_small)
    if args.Ns_large is not None:
        counts["Ns_large"] = int(args.Ns_large)
    if args.Nr is not None:
        counts["Nr"] = int(args.Nr)

    validate_tooth_counts(counts, strict_geometry=bool(args.strict_geometry))
    return counts


def _presets_payload() -> Dict[str, Dict[str, int]]:
    return {name: dict(values) for name, values in PRESETS.items()}


def _print_presets() -> None:
    print("Available presets")
    print("-----------------")
    for name, counts in PRESETS.items():
        note = PRESET_NOTES.get(name, "")
        print(f"{name:18s} Ns_small={counts['Ns_small']} Ns_large={counts['Ns_large']} Nr={counts['Nr']}")
        if note:
            print(f"  note: {note}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ravigneaux 4-speed transmission kinematic solver")
    p.add_argument(
        "--preset",
        type=str,
        default="ravigneaux_demo",
        choices=sorted(PRESETS.keys()),
        help="Named tooth-count preset. Manual tooth-count flags override the preset.",
    )
    p.add_argument("--Ns-small", dest="Ns_small", type=int, default=None, help="Small sun tooth count")
    p.add_argument("--Ns-large", dest="Ns_large", type=int, default=None, help="Large sun tooth count")
    p.add_argument("--Nr", type=int, default=None, help="Ring tooth count")
    p.add_argument("--input-speed", type=float, default=1.0)
    p.add_argument("--state", type=str, default="all", help="Specific state: 1st, 2nd, 3rd, 4th, rev, or all")
    p.add_argument("--strict-geometry", action="store_true", help="Enforce simplified strict geometry checks on both sun branches")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    p.add_argument("--ratios-only", action="store_true", help="Print only the ratio summary for all states")
    p.add_argument("--show-topology", action="store_true")
    p.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    return p


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
        print("four_speed.py error", file=sys.stderr)
        print("-------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                f"Tooth counts: Ns_small={tooth_counts['Ns_small']}, "
                f"Ns_large={tooth_counts['Ns_large']}, Nr={tooth_counts['Nr']}",
                file=sys.stderr,
            )
    return 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_presets:
        if args.json:
            print(json.dumps(_presets_payload(), indent=2))
        else:
            _print_presets()
        return 0

    tooth_counts: Optional[Dict[str, int]] = None
    try:
        tooth_counts = _resolve_tooth_counts(args)
        tx = RavigneauxFourSpeedTransmission(**tooth_counts, strict_geometry=bool(args.strict_geometry))

        if args.show_topology and not args.json:
            print(tx.topology_description())

        if str(args.state).strip().lower() == "all":
            result = tx.solve_all(input_speed=float(args.input_speed))
            if args.json:
                payload: Dict[str, object] = {
                    "ok": True,
                    "preset": args.preset,
                    "strict_geometry": bool(args.strict_geometry),
                    "tooth_counts": tooth_counts,
                    "states": result,
                }
                if args.ratios_only:
                    payload["ratios"] = {name: state["ratio"] for name, state in result.items()}
                print(json.dumps(payload, indent=2))
            else:
                print(tx.ratio_table(input_speed=float(args.input_speed)) if args.ratios_only else tx.summary_table(input_speed=float(args.input_speed)))
            return 0

        result = tx.solve_state(args.state, input_speed=float(args.input_speed))
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
                "strict_geometry": bool(args.strict_geometry),
                "tooth_counts": tooth_counts,
                **result,
            }
            print(json.dumps(payload, indent=2))
        else:
            if args.ratios_only:
                print(f"{result['state']}: {result['ratio']:.6f}")
            else:
                print(f"State: {result['state']}")
                print(f"Engaged: {' + '.join(result['engaged'])}")
                print(tx.tooth_count_summary())
                print(f"Ratio (input/output): {result['ratio']:.6f}")
                print(json.dumps(result['speeds'], indent=2))
        return 0

    except (FourSpeedCliError, ValueError) as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts)
    except Exception as exc:  # pragma: no cover
        return _emit_cli_error(
            args=args,
            message=f"Unexpected solver/runtime failure: {exc}",
            tooth_counts=tooth_counts,
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
