#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.six_speed

Allison-style 6-speed automatic transmission kinematic model.

This module encodes the topology described in the project discussion:

Topology (left to right, engine to output)
------------------------------------------
PG1:
    - PG1.sun permanently connected to engine input
    - PG1.carrier permanently connected to PG2.ring
    - PG1.ring can be braked by C3

PG2:
    - PG2.sun can be connected to engine input by C1
    - PG2.carrier can be connected to engine input by C2
    - PG2.sun permanently connected to PG3.sun
    - PG2.carrier permanently connected to PG3.ring
    - PG2.ring can be braked by C4

PG3:
    - PG3.carrier is output
    - PG3.ring can be braked by C5

Shift schedule
--------------
    1st : C1 + C5
    2nd : C1 + C4
    3rd : C1 + C3
    4th : C1 + C2
    5th : C2 + C3
    6th : C2 + C4
    Rev : C3 + C5

Important note
--------------
This file uses a *linear* Willis-equation solve:

    Ns (ws - wc) + Nr (wr - wc) = 0

instead of the older fractional form in core/solver.py. That avoids the
0/0 singularity that appears in direct-drive states such as 4th gear.

What this upgrade adds
----------------------
- explicit CLI tooth-count flags for all six gear tooth counts
- presets for known Allison-family configurations
- reporting of the active tooth counts actually used in the run
- optional ratio-only JSON/text output
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

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

LOG = logging.getLogger(__name__)

class SixSpeedCliError(ValueError):
    """User-facing CLI/configuration error for six_speed.py."""


def _validate_simple_planetary_counts(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise SixSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise SixSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )
    if (Nr - Ns) % 2 != 0:
        planet = Nr - Ns
        raise SixSpeedCliError(
            f"Invalid {label} tooth counts: (Nr - Ns) must be even so the implied planet tooth count is an integer. "
            f"Got Ns={Ns}, Nr={Nr}, Nr-Ns={planet}."
        )


def validate_tooth_counts(counts: Mapping[str, int]) -> None:
    _validate_simple_planetary_counts(Ns=int(counts["Ns1"]), Nr=int(counts["Nr1"]), label="PG1")
    _validate_simple_planetary_counts(Ns=int(counts["Ns2"]), Nr=int(counts["Nr2"]), label="PG2")
    _validate_simple_planetary_counts(Ns=int(counts["Ns3"]), Nr=int(counts["Nr3"]), label="PG3")


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
        print("six_speed.py error", file=sys.stderr)
        print("------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                f"Tooth counts: PG1(Ns1={tooth_counts['Ns1']}, Nr1={tooth_counts['Nr1']}), "
                f"PG2(Ns2={tooth_counts['Ns2']}, Nr2={tooth_counts['Nr2']}), "
                f"PG3(Ns3={tooth_counts['Ns3']}, Nr3={tooth_counts['Nr3']})",
                file=sys.stderr,
            )
    return 2


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    "Ns1": 67,
    "Nr1": 109,
    "Ns2": 49,
    "Nr2": 91,
    "Ns3": 39,
    "Nr3": 97,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "allison_3000": {
        "Ns1": 67,
        "Nr1": 109,
        "Ns2": 49,
        "Nr2": 91,
        "Ns3": 39,
        "Nr3": 97,
    },
    # Working candidate preset for Allison 1000/2000-style exploration.
    # This is intentionally labeled exploratory rather than OEM-confirmed.
    "allison_1000_candidate": {
        "Ns1": 61,
        "Nr1": 100,
        "Ns2": 41,
        "Nr2": 79,
        "Ns3": 41,
        "Nr3": 79,
    },
}


@dataclass(frozen=True)
class GearState:
    name: str
    engaged: tuple[str, ...]


class AllisonSixSpeedTransmission:
    """Allison-style 3-planetary, 5-friction-element transmission model."""

    SHIFT_SCHEDULE: Mapping[str, tuple[str, str]] = {
        "1st": ("C1", "C5"),
        "2nd": ("C1", "C4"),
        "3rd": ("C1", "C3"),
        "4th": ("C1", "C2"),
        "5th": ("C2", "C3"),
        "6th": ("C2", "C4"),
        "rev": ("C3", "C5"),
        "reverse": ("C3", "C5"),
    }

    def __init__(
        self,
        *,
        Ns1: int,
        Nr1: int,
        Ns2: int,
        Nr2: int,
        Ns3: int,
        Nr3: int,
    ) -> None:
        self.tooth_counts: Dict[str, int] = {
            "Ns1": int(Ns1),
            "Nr1": int(Nr1),
            "Ns2": int(Ns2),
            "Nr2": int(Nr2),
            "Ns3": int(Ns3),
            "Nr3": int(Nr3),
        }
        self._build_topology(**self.tooth_counts)

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def _build_topology(self, *, Ns1: int, Nr1: int, Ns2: int, Nr2: int, Ns3: int, Nr3: int) -> None:
        self.input = RotatingMember("input")
        self.ring1 = RotatingMember("ring1")
        self.node12 = RotatingMember("node12")
        self.sun23 = RotatingMember("sun23")
        self.node23 = RotatingMember("node23")
        self.output = RotatingMember("output")

        self.members: Dict[str, RotatingMember] = {
            "input": self.input,
            "ring1": self.ring1,
            "node12": self.node12,
            "sun23": self.sun23,
            "node23": self.node23,
            "output": self.output,
        }

        self.pg1 = PlanetaryGearSet(Ns1, Nr1, name="PG1", sun=self.input, ring=self.ring1, carrier=self.node12)
        self.pg2 = PlanetaryGearSet(Ns2, Nr2, name="PG2", sun=self.sun23, ring=self.node12, carrier=self.node23)
        self.pg3 = PlanetaryGearSet(Ns3, Nr3, name="PG3", sun=self.sun23, ring=self.node23, carrier=self.output)

        self.gearsets: List[PlanetaryGearSet] = [self.pg1, self.pg2, self.pg3]

        self.C1 = Clutch(self.input, self.sun23, name="C1")
        self.C2 = Clutch(self.input, self.node23, name="C2")
        self.C3 = Brake(self.ring1, name="C3")
        self.C4 = Brake(self.node12, name="C4")
        self.C5 = Brake(self.node23, name="C5")

        self.constraints: Dict[str, object] = {
            "C1": self.C1,
            "C2": self.C2,
            "C3": self.C3,
            "C4": self.C4,
            "C5": self.C5,
        }

    # ------------------------------------------------------------------
    # State control
    # ------------------------------------------------------------------

    def release_all(self) -> None:
        for c in self.constraints.values():
            c.release()  # type: ignore[attr-defined]

    def set_state(self, state: str) -> GearState:
        key = state.strip().lower()
        if key not in self.SHIFT_SCHEDULE:
            raise ValueError(f"Unknown state: {state}")
        self.release_all()
        engaged = self.SHIFT_SCHEDULE[key]
        for name in engaged:
            self.constraints[name].engage()  # type: ignore[attr-defined]
        display = "Rev" if key in {"rev", "reverse"} else state.strip()
        return GearState(display, engaged)

    # ------------------------------------------------------------------
    # Linear kinematic solve
    # ------------------------------------------------------------------

    def _symbols(self) -> Dict[str, sp.Symbol]:
        return {name: sp.symbols(f"w_{name}") for name in self.members}

    def _planetary_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        eqs: List[sp.Expr] = []
        for g in self.gearsets:
            ws = symbols[g.sun.name]
            wr = symbols[g.ring.name]
            wc = symbols[g.carrier.name]
            eqs.append(g.Ns * (ws - wc) + g.Nr * (wr - wc))
        return eqs

    def _constraint_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        eqs: List[sp.Expr] = []
        for name, c in self.constraints.items():
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
            else:  # pragma: no cover
                raise TypeError(f"Unsupported constraint type: {name}")
        return eqs

    def solve_state(self, state: str, input_speed: float = 1.0) -> Dict[str, object]:
        info = self.set_state(state)
        symbols = self._symbols()
        eqs = []
        eqs.extend(self._planetary_equations(symbols))
        eqs.extend(self._constraint_equations(symbols))
        eqs.append(symbols["input"] - float(input_speed))

        unknowns = [symbols[name] for name in self.members]
        LOG.debug("Solving state %s with engaged=%s", info.name, info.engaged)
        sol_set = sp.linsolve(eqs, unknowns)
        if not sol_set:
            raise RuntimeError(f"No solution found for state {state}")

        tuples = list(sol_set)
        if len(tuples) != 1:
            raise RuntimeError(f"Unexpected non-unique solution for state {state}: {tuples}")

        sol = tuples[0]
        results: Dict[str, float] = {}
        for name, value in zip(self.members, sol):
            if getattr(value, "free_symbols", None):
                raise RuntimeError(f"Underdetermined variable in state {state}: {name} = {value}")
            results[name] = float(sp.N(value))

        win = results["input"]
        wout = results["output"]
        ratio = float("inf") if abs(wout) < 1e-12 else win / wout

        return {
            "state": info.name,
            "engaged": list(info.engaged),
            "speeds": results,
            "ratio": ratio,
            "tooth_counts": dict(self.tooth_counts),
        }

    def solve_all(self, input_speed: float = 1.0) -> Dict[str, Dict[str, object]]:
        order = ["1st", "2nd", "3rd", "4th", "5th", "6th", "Rev"]
        out: Dict[str, Dict[str, object]] = {}
        for state in order:
            key = "rev" if state == "Rev" else state
            out[state] = self.solve_state(key, input_speed=input_speed)
        return out

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary_table(self, input_speed: float = 1.0) -> str:
        solved = self.solve_all(input_speed=input_speed)
        lines = []
        lines.append("Allison 6-Speed Kinematic Summary")
        lines.append(self.tooth_count_summary())
        lines.append("-" * 104)
        lines.append(
            f"{'State':<8}{'Elems':<12}{'Ratio':>10}{'Input':>10}{'Ring1':>10}{'Node12':>10}{'Sun23':>10}{'Node23':>10}{'Output':>10}"
        )
        lines.append("-" * 104)
        for state in ["1st", "2nd", "3rd", "4th", "5th", "6th", "Rev"]:
            item = solved[state]
            s = item["speeds"]
            assert isinstance(s, dict)
            elems = "+".join(item["engaged"])
            lines.append(
                f"{state:<8}{elems:<12}{item['ratio']:>10.3f}"
                f"{s['input']:>10.3f}{s['ring1']:>10.3f}{s['node12']:>10.3f}"
                f"{s['sun23']:>10.3f}{s['node23']:>10.3f}{s['output']:>10.3f}"
            )
        return "\n".join(lines)

    def ratio_table(self, input_speed: float = 1.0) -> str:
        solved = self.solve_all(input_speed=input_speed)
        lines = []
        lines.append("Allison 6-Speed Ratio Summary")
        lines.append(self.tooth_count_summary())
        lines.append("-" * 42)
        lines.append(f"{'State':<8}{'Elems':<12}{'Ratio':>10}")
        lines.append("-" * 42)
        for state in ["1st", "2nd", "3rd", "4th", "5th", "6th", "Rev"]:
            item = solved[state]
            elems = "+".join(item["engaged"])
            lines.append(f"{state:<8}{elems:<12}{item['ratio']:>10.3f}")
        return "\n".join(lines)

    def tooth_count_summary(self) -> str:
        tc = self.tooth_counts
        return (
            f"Tooth counts: "
            f"PG1(Ns1={tc['Ns1']}, Nr1={tc['Nr1']}), "
            f"PG2(Ns2={tc['Ns2']}, Nr2={tc['Nr2']}), "
            f"PG3(Ns3={tc['Ns3']}, Nr3={tc['Nr3']})"
        )

    def topology_description(self) -> str:
        return (
            "Topology\n"
            "--------\n"
            "PG1: sun=input, ring=ring1, carrier=node12\n"
            "PG2: sun=sun23, ring=node12, carrier=node23\n"
            "PG3: sun=sun23, ring=node23, carrier=output\n"
            "\n"
            "Shift elements\n"
            "--------------\n"
            "C1: clutch(input <-> sun23)\n"
            "C2: clutch(input <-> node23)\n"
            "C3: brake(ring1 -> ground)\n"
            "C4: brake(node12 -> ground)\n"
            "C5: brake(node23 -> ground)\n"
        )


def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    counts = dict(DEFAULT_TOOTH_COUNTS)

    if args.preset is not None:
        if args.preset not in PRESETS:
            raise ValueError(f"Unknown preset: {args.preset}")
        counts.update(PRESETS[args.preset])

    for key in ("Ns1", "Nr1", "Ns2", "Nr2", "Ns3", "Nr3"):
        value = getattr(args, key)
        if value is not None:
            counts[key] = int(value)

    return counts


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Allison-style 6-speed transmission kinematic solver")
    p.add_argument(
        "--preset",
        type=str,
        default="allison_3000",
        choices=sorted(PRESETS.keys()),
        help="Named tooth-count preset. Manual tooth-count flags override the preset.",
    )
    p.add_argument("--Ns1", type=int, default=None, help="PG1 sun tooth count")
    p.add_argument("--Nr1", type=int, default=None, help="PG1 ring tooth count")
    p.add_argument("--Ns2", type=int, default=None, help="PG2 sun tooth count")
    p.add_argument("--Nr2", type=int, default=None, help="PG2 ring tooth count")
    p.add_argument("--Ns3", type=int, default=None, help="PG3 sun tooth count")
    p.add_argument("--Nr3", type=int, default=None, help="PG3 ring tooth count")
    p.add_argument("--input-speed", type=float, default=1.0)
    p.add_argument("--state", type=str, default="all", help="Specific state: 1st, 2nd, 3rd, 4th, 5th, 6th, rev, or all")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    p.add_argument("--ratios-only", action="store_true", help="Print only the ratio summary for all states")
    p.add_argument("--show-topology", action="store_true")
    p.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    p.add_argument("--log-level", default="WARNING")
    return p


def _presets_payload() -> Dict[str, Dict[str, int]]:
    return {name: dict(values) for name, values in PRESETS.items()}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.WARNING),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    try:
        if args.list_presets:
            if args.json:
                print(json.dumps(_presets_payload(), indent=2))
            else:
                print("Available presets")
                print("-" * 18)
                for name, values in PRESETS.items():
                    print(f"{name}: {dict(values)}")
            return 0

        tooth_counts = _resolve_tooth_counts(args)
        validate_tooth_counts(tooth_counts)
        tx = AllisonSixSpeedTransmission(**tooth_counts)

        if args.show_topology and not args.json:
            print(tx.topology_description())

        if args.state.lower() == "all":
            result = tx.solve_all(input_speed=args.input_speed)
            if args.json:
                payload: Dict[str, object] = {
                    "ok": True,
                    "preset": args.preset,
                    "tooth_counts": tooth_counts,
                    "states": result,
                }
                print(json.dumps(payload, indent=2))
            else:
                print(tx.ratio_table(input_speed=args.input_speed) if args.ratios_only else tx.summary_table(input_speed=args.input_speed))
            return 0

        result = tx.solve_state(args.state, input_speed=args.input_speed)
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
                "tooth_counts": tooth_counts,
                **result,
            }
            print(json.dumps(payload, indent=2))
        else:
            print(tx.tooth_count_summary())
            print(f"State: {result['state']}")
            print(f"Engaged: {' + '.join(result['engaged'])}")
            print(f"Ratio (input/output): {result['ratio']:.6f}")
            print(json.dumps(result['speeds'], indent=2))
        return 0
    except SixSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=locals().get('tooth_counts'))
    except ValueError as exc:
        return _emit_cli_error(args=args, message=f"Invalid input: {exc}", tooth_counts=locals().get('tooth_counts'))
    except RuntimeError as exc:
        return _emit_cli_error(args=args, message=f"Solver failure: {exc}", tooth_counts=locals().get('tooth_counts'))
    except KeyboardInterrupt:
        return _emit_cli_error(args=args, message="Interrupted by user.", tooth_counts=locals().get('tooth_counts'))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
