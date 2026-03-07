#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.four_speed

Ravigneaux 4-speed automatic transmission kinematic model.

This module encodes a single Ravigneaux gearset with four central members:

    - small sun gear
    - large sun gear
    - ring gear
    - planet carrier

Output convention
-----------------
For this transmission model, the ring gear is always the output member.

Kinematic model
---------------
For a Ravigneaux gearset, the short/long planet mesh topology leads to two
independent linear relations among the central members:

    Ns_small * (w_small - w_carrier) - Nr * (w_ring - w_carrier) = 0
    Ns_large * (w_large - w_carrier) + Nr * (w_ring - w_carrier) = 0

These signs differ because the small-sun branch and the large-sun branch couple
through different external/internal mesh paths.

Standard operating states modeled here
--------------------------------------
1st:
    carrier fixed
    small sun input
    ring output

2nd:
    large sun fixed
    small sun input
    ring output

3rd:
    direct drive / gearset locked
    ring input
    ring output

4th:
    large sun fixed
    carrier input
    ring output

Reverse:
    carrier fixed
    large sun input
    ring output

Important honesty note
----------------------
This is a kinematic central-member solver. It does not model tooth loads,
planet bearing loads, clutch hydraulic details, or power flow losses.
It is intended for ratio/state analysis.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

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


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    # Matches the screenshot ratios very closely:
    # 1st ~= 3.18, 2nd ~= 1.84, 3rd = 1.0, 4th ~= 0.61, Rev ~= -1.59
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


def validate_tooth_counts(counts: Mapping[str, int]) -> None:
    Ns_small = int(counts["Ns_small"])
    Ns_large = int(counts["Ns_large"])
    Nr = int(counts["Nr"])

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

    def __init__(self, *, Ns_small: int, Ns_large: int, Nr: int) -> None:
        self.tooth_counts: Dict[str, int] = {
            "Ns_small": int(Ns_small),
            "Ns_large": int(Ns_large),
            "Nr": int(Nr),
        }
        validate_tooth_counts(self.tooth_counts)
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

        # Constraint elements inferred from the operating description.
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
        return GearState(display, engaged, input_member=str(spec["input"]))

    def _symbols(self) -> Dict[str, sp.Symbol]:
        return {name: sp.symbols(f"w_{name}") for name in self.members}

    def _ravigneaux_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        ws = symbols["sun_small"]
        wl = symbols["sun_large"]
        wr = symbols["ring"]
        wc = symbols["carrier"]
        return [
            self.Ns_small * (ws - wc) - self.Nr * (wr - wc),
            self.Ns_large * (wl - wc) + self.Nr * (wr - wc),
        ]

    def _constraint_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        eqs: List[sp.Expr] = []
        for c in self.constraints.values():
            if not c.engaged:  # type: ignore[attr-defined]
                continue
            data = c.constraint()  # type: ignore[attr-defined]
            if data is None:
                continue
            if isinstance(c, Clutch):
                a, b = data
                eqs.append(symbols[a.name] - symbols[b.name])
            elif isinstance(c, Brake):
                member, _ground = data
                eqs.append(symbols[member.name])
        return eqs

    def solve(self, state: str, *, input_speed: float = 1.0) -> Dict[str, object]:
        gear_state = self.set_state(state)
        symbols = self._symbols()
        equations = []
        equations.extend(self._ravigneaux_equations(symbols))
        equations.extend(self._constraint_equations(symbols))
        equations.append(symbols[gear_state.input_member] - float(input_speed))

        variables = list(symbols.values())
        solution = sp.solve(equations, variables, dict=True)
        if not solution:
            raise RuntimeError(f"No kinematic solution found for state {state}")
        sol = solution[0]

        speeds: Dict[str, float] = {}
        for name, sym in symbols.items():
            if sym not in sol:
                raise RuntimeError(f"Undetermined variable in state {state}: {name}")
            speeds[name] = float(sol[sym])

        output_speed = speeds[gear_state.output_member]
        if abs(output_speed) < 1.0e-12:
            raise RuntimeError(f"Output speed is zero in state {state}; ratio undefined")

        ratio_signed = float(input_speed) / output_speed
        ratio_display = ratio_signed
        if gear_state.name != "Rev":
            ratio_display = abs(ratio_signed)

        return {
            "state": gear_state.name,
            "engaged": list(gear_state.engaged),
            "input_member": gear_state.input_member,
            "output_member": gear_state.output_member,
            "speeds": speeds,
            "ratio_signed": ratio_signed,
            "ratio": ratio_display,
            "notes": self.SHIFT_SCHEDULE[state.strip().lower()]["notes"],
        }

    def solve_all(self) -> Dict[str, Dict[str, object]]:
        order = ["1st", "2nd", "3rd", "4th", "Rev"]
        results: Dict[str, Dict[str, object]] = {}
        state_map = {"1st": "1st", "2nd": "2nd", "3rd": "3rd", "4th": "4th", "Rev": "rev"}
        for label in order:
            results[label] = self.solve(state_map[label])
        return results



def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    counts = dict(DEFAULT_TOOTH_COUNTS)

    if args.preset:
        if args.preset not in PRESETS:
            raise FourSpeedCliError(
                f"Unknown preset '{args.preset}'. Available presets: {', '.join(sorted(PRESETS))}"
            )
        counts.update(PRESETS[args.preset])

    manual_overrides = {
        "Ns_small": args.Ns_small,
        "Ns_large": args.Ns_large,
        "Nr": args.Nr,
    }
    for key, value in manual_overrides.items():
        if value is not None:
            counts[key] = int(value)

    validate_tooth_counts(counts)
    return counts



def _print_tooth_counts(counts: Mapping[str, int]) -> None:
    print("Tooth Counts")
    print("----------------------------------------")
    print(f"Ns_small = {counts['Ns_small']}")
    print(f"Ns_large = {counts['Ns_large']}")
    print(f"Nr       = {counts['Nr']}")
    print()



def _print_single(result: Mapping[str, object], *, show_tooth_counts: Optional[Mapping[str, int]] = None) -> None:
    if show_tooth_counts is not None:
        _print_tooth_counts(show_tooth_counts)
    print(f"State: {result['state']}")
    print(f"Engaged: {' + '.join(result['engaged'])}")
    print(f"Input member: {result['input_member']}")
    print(f"Output member: {result['output_member']}")
    print(f"Ratio (input/output): {float(result['ratio']):.6f}")
    print(json.dumps(result["speeds"], indent=2))



def _print_all(results: Mapping[str, Mapping[str, object]], *, show_tooth_counts: Optional[Mapping[str, int]] = None) -> None:
    if show_tooth_counts is not None:
        _print_tooth_counts(show_tooth_counts)
    print("Ravigneaux 4-Speed Kinematic Summary")
    print("-" * 104)
    print(f"{'State':<7} {'Elems':<18} {'Ratio':>8} {'SmallSun':>10} {'LargeSun':>10} {'Carrier':>10} {'RingOut':>10}")
    print("-" * 104)
    for key in ["1st", "2nd", "3rd", "4th", "Rev"]:
        r = results[key]
        s = r["speeds"]
        print(
            f"{key:<7} {'+'.join(r['engaged']):<18} "
            f"{float(r['ratio']):>8.3f} "
            f"{float(s['sun_small']):>10.3f} "
            f"{float(s['sun_large']):>10.3f} "
            f"{float(s['carrier']):>10.3f} "
            f"{float(s['ring']):>10.3f}"
        )



def _print_ratios_only(results: Mapping[str, Mapping[str, object]], *, as_json: bool = False) -> None:
    payload = {key: float(results[key]["ratio"]) for key in ["1st", "2nd", "3rd", "4th", "Rev"]}
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    print("Ratios Only")
    print("----------------------------------------")
    for key in ["1st", "2nd", "3rd", "4th", "Rev"]:
        print(f"{key:>4}: {payload[key]:.6f}")



def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Ravigneaux 4-speed automatic transmission kinematic solver")
    p.add_argument("--state", default="all", help="State to solve: 1st, 2nd, 3rd, 4th, rev, reverse, or all")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Print only the ratios")
    p.add_argument("--preset", choices=sorted(PRESETS.keys()), default="ravigneaux_demo", help="Named tooth-count preset")
    p.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    p.add_argument("--Ns-small", dest="Ns_small", type=int, default=None, help="Small sun tooth count")
    p.add_argument("--Ns-large", dest="Ns_large", type=int, default=None, help="Large sun tooth count")
    p.add_argument("--Nr", type=int, default=None, help="Ring gear tooth count")
    return p



def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_presets:
        payload = {name: dict(values) for name, values in PRESETS.items()}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Available presets")
            print("----------------------------------------")
            for name, values in payload.items():
                print(
                    f"{name}: Ns_small={values['Ns_small']}, "
                    f"Ns_large={values['Ns_large']}, Nr={values['Nr']}"
                )
        return 0

    tooth_counts: Dict[str, int] = {}
    try:
        tooth_counts = _resolve_tooth_counts(args)
        tx = RavigneauxFourSpeedTransmission(**tooth_counts)

        if args.state.strip().lower() == "all":
            results = tx.solve_all()
            if args.json:
                payload = {
                    "ok": True,
                    "tooth_counts": tooth_counts,
                    "results": results,
                }
                if args.ratios_only:
                    payload = {
                        "ok": True,
                        "tooth_counts": tooth_counts,
                        "ratios": {key: float(results[key]["ratio"]) for key in ["1st", "2nd", "3rd", "4th", "Rev"]},
                    }
                print(json.dumps(payload, indent=2))
                return 0
            if args.ratios_only:
                _print_tooth_counts(tooth_counts)
                _print_ratios_only(results, as_json=False)
                return 0
            _print_all(results, show_tooth_counts=tooth_counts)
            return 0

        result = tx.solve(args.state)
        if args.json:
            payload = {"ok": True, "tooth_counts": tooth_counts, "result": result}
            if args.ratios_only:
                payload = {
                    "ok": True,
                    "tooth_counts": tooth_counts,
                    "ratio": float(result["ratio"]),
                    "state": result["state"],
                }
            print(json.dumps(payload, indent=2))
            return 0
        if args.ratios_only:
            _print_tooth_counts(tooth_counts)
            print(f"{result['state']}: {float(result['ratio']):.6f}")
            return 0
        _print_single(result, show_tooth_counts=tooth_counts)
        return 0

    except FourSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts or None)
    except Exception as exc:
        return _emit_cli_error(
            args=args,
            message=f"Unexpected runtime failure: {exc}",
            tooth_counts=tooth_counts or None,
        )


if __name__ == "__main__":
    raise SystemExit(main())
