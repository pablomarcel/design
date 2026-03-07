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
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping

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
        Ns1: int = 30,
        Nr1: int = 72,
        Ns2: int = 30,
        Nr2: int = 72,
        Ns3: int = 30,
        Nr3: int = 72,
    ) -> None:
        self._build_topology(Ns1=Ns1, Nr1=Nr1, Ns2=Ns2, Nr2=Nr2, Ns3=Ns3, Nr3=Nr3)

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def _build_topology(self, *, Ns1: int, Nr1: int, Ns2: int, Nr2: int, Ns3: int, Nr3: int) -> None:
        # Permanent nodes
        self.input = RotatingMember("input")
        self.ring1 = RotatingMember("ring1")
        self.node12 = RotatingMember("node12")  # PG1 carrier = PG2 ring
        self.sun23 = RotatingMember("sun23")    # PG2 sun = PG3 sun
        self.node23 = RotatingMember("node23")  # PG2 carrier = PG3 ring
        self.output = RotatingMember("output")  # PG3 carrier

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

        # Shift elements
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

    def ratio_row(self, state: str, input_speed: float = 1.0) -> Dict[str, float]:
        solved = self.solve_state(state, input_speed=input_speed)
        row = {"ratio": solved["ratio"]}
        row.update(solved["speeds"])  # type: ignore[arg-type]
        return row

    def summary_table(self, input_speed: float = 1.0) -> str:
        solved = self.solve_all(input_speed=input_speed)
        lines = []
        lines.append("Allison 6-Speed Kinematic Summary")
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


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Allison-style 6-speed transmission kinematic solver")
    p.add_argument("--Ns1", type=int, default=67)
    p.add_argument("--Nr1", type=int, default=109)
    p.add_argument("--Ns2", type=int, default=49)
    p.add_argument("--Nr2", type=int, default=91)
    p.add_argument("--Ns3", type=int, default=39)
    p.add_argument("--Nr3", type=int, default=97)
    p.add_argument("--input-speed", type=float, default=1.0)
    p.add_argument("--state", type=str, default="all", help="Specific state: 1st, 2nd, 3rd, 4th, 5th, 6th, rev, or all")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    p.add_argument("--show-topology", action="store_true")
    p.add_argument("--log-level", default="WARNING")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.WARNING),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    tx = AllisonSixSpeedTransmission(
        Ns1=args.Ns1,
        Nr1=args.Nr1,
        Ns2=args.Ns2,
        Nr2=args.Nr2,
        Ns3=args.Ns3,
        Nr3=args.Nr3,
    )

    if args.show_topology and not args.json:
        print(tx.topology_description())

    if args.state.lower() == "all":
        result = tx.solve_all(input_speed=args.input_speed)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(tx.summary_table(input_speed=args.input_speed))
        return 0

    result = tx.solve_state(args.state, input_speed=args.input_speed)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"State: {result['state']}")
        print(f"Engaged: {' + '.join(result['engaged'])}")
        print(f"Ratio (input/output): {result['ratio']:.6f}")
        print(json.dumps(result['speeds'], indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
