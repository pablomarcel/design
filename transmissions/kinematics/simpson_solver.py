#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.simpson_solver

State-based Simpson transmission kinematic solver.

Why this upgrade exists
-----------------------
The older project versions mixed two styles:

1. a generic symbolic TransmissionSolver path, and
2. gear-specific helper methods that acted like hardcoded operating modes.

That was enough to make the ratio explorer run, but it had two weaknesses:

- the generic solver used the fractional Willis form, which is awkward near
  singular cases
- underdetermined / overconstrained states were discovered only after solve

This upgraded module solves the current Simpson architecture with an explicit
linear state solver built from the canonical planetary relation:

    Ns (ws - wc) + Nr (wr - wc) = 0

The modeled members remain the same as in the current project:

    sun, ring1, ring2, carrier

with two planetary sets sharing the same sun and the same carrier.

Important honesty note
----------------------
This is a more rigorous *kinematic* solver for the current simplified
4-member architecture, but it does not change the underlying mechanical
architecture. So:

- 3rd gear is now solved from active constraints instead of being forced by the
  caller.
- reverse is only as physically rigorous as this simplified topology allows. If
  a negative output does not emerge naturally, that is a topology limitation,
  not a math bug.

Public API preserved
--------------------
The legacy methods are still available:

    SimpsonTransmission(...).first_gear()
    SimpsonTransmission(...).second_gear()
    SimpsonTransmission(...).third_gear()
    SimpsonTransmission(...).reverse()
    gear_ratio(result, input_member, output_member)

New API added
-------------
- solve_state(...)
- solve_named_state(...)
- state_report(...)
- validate_state(...)
- ratio_for_state(...)
- standard_states()
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import sympy as sp

# -----------------------------------------------------------------------------
# Imports: support package execution and flat-file execution.
# -----------------------------------------------------------------------------

try:
    from core.clutch import RotatingMember, Clutch, Brake
    from core.planetary import PlanetaryGearSet
except Exception:
    try:
        from transmissions.core.clutch import RotatingMember, Clutch, Brake
        from transmissions.core.planetary import PlanetaryGearSet
    except Exception:
        _HERE = Path(__file__).resolve().parent
        _PARENT = _HERE.parent
        for _candidate in (str(_HERE), str(_PARENT)):
            if _candidate not in sys.path:
                sys.path.insert(0, _candidate)
        from clutch import RotatingMember, Clutch, Brake  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore


LOGGER = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure logging unless the host app already did so."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        )
    LOGGER.setLevel(level)


@dataclass(frozen=True)
class SimpsonShiftState:
    name: str
    input_member: str
    input_speed: float = 1.0
    engaged_brakes: Tuple[str, ...] = ()
    engaged_clutches: Tuple[str, ...] = ()
    notes: str = ""


@dataclass
class SimpsonSolveReport:
    ok: bool
    state_name: str
    status: str
    classification: str
    equations: List[str]
    active_brakes: List[str]
    active_clutches: List[str]
    speeds: Dict[str, float] = field(default_factory=dict)
    symbolic_solution: Dict[str, str] = field(default_factory=dict)
    residuals: Dict[str, float] = field(default_factory=dict)
    rank: int = 0
    unknown_count: int = 0
    equation_count: int = 0
    message: str = ""


class SimpsonTransmission:
    """
    State-based Simpson transmission solver for the current project topology.
    """

    _VALID_MEMBERS = ("sun", "ring1", "ring2", "carrier")

    def __init__(self, Ns: int, Nr1: int, Nr2: int, *, enable_logging: bool = False):
        self.Ns = int(Ns)
        self.Nr1 = int(Nr1)
        self.Nr2 = int(Nr2)
        self.enable_logging = bool(enable_logging)

        if self.Ns <= 0 or self.Nr1 <= 0 or self.Nr2 <= 0:
            raise ValueError("All tooth counts must be positive")
        if self.Nr1 <= self.Ns or self.Nr2 <= self.Ns:
            raise ValueError("Ring tooth counts must be greater than the sun tooth count")
        if (self.Nr1 - self.Ns) % 2 != 0 or (self.Nr2 - self.Ns) % 2 != 0:
            raise ValueError(
                "Invalid simple planetary geometry: (Nr - Ns) must be even for both gearsets"
            )

        self.sun = RotatingMember("sun")
        self.ring1 = RotatingMember("ring1")
        self.ring2 = RotatingMember("ring2")
        self.carrier = RotatingMember("carrier")

        self.p1 = PlanetaryGearSet(
            Ns=self.Ns,
            Nr=self.Nr1,
            sun=self.sun,
            ring=self.ring1,
            carrier=self.carrier,
            name="PGS1",
        )
        self.p2 = PlanetaryGearSet(
            Ns=self.Ns,
            Nr=self.Nr2,
            sun=self.sun,
            ring=self.ring2,
            carrier=self.carrier,
            name="PGS2",
        )

        self.ring1_brake = Brake(self.ring1)
        self.ring2_brake = Brake(self.ring2)
        self.direct_clutch = Clutch(self.sun, self.carrier)

        self._log(
            "Initialized SimpsonTransmission Ns=%s Nr1=%s Nr2=%s",
            self.Ns,
            self.Nr1,
            self.Nr2,
        )

    def _log(self, msg: str, *args) -> None:
        if self.enable_logging:
            LOGGER.info(msg, *args)

    def reset(self) -> None:
        self.ring1_brake.release()
        self.ring2_brake.release()
        self.direct_clutch.release()
        self._log("Released all clutches_brakes_flywheels/brakes")

    def _apply_state_elements(
        self,
        *,
        engaged_brakes: Sequence[str],
        engaged_clutches: Sequence[str],
    ) -> None:
        self.reset()

        brake_map = {
            "ring1_brake": self.ring1_brake,
            "ring2_brake": self.ring2_brake,
        }
        clutch_map = {
            "direct_clutch": self.direct_clutch,
        }

        for brake_name in engaged_brakes:
            if brake_name not in brake_map:
                raise ValueError(f"Unknown brake name: {brake_name}")
            brake_map[brake_name].engage()

        for clutch_name in engaged_clutches:
            if clutch_name not in clutch_map:
                raise ValueError(f"Unknown clutch name: {clutch_name}")
            clutch_map[clutch_name].engage()

        self._log(
            "Applied state elements: brakes=%s clutches_brakes_flywheels=%s",
            list(engaged_brakes),
            list(engaged_clutches),
        )

    @staticmethod
    def standard_states() -> Dict[str, SimpsonShiftState]:
        return {
            "first": SimpsonShiftState(
                name="first",
                input_member="carrier",
                input_speed=1.0,
                engaged_brakes=("ring2_brake",),
                notes="Carrier input, ring2 grounded",
            ),
            "second": SimpsonShiftState(
                name="second",
                input_member="carrier",
                input_speed=1.0,
                engaged_brakes=("ring1_brake",),
                notes="Carrier input, ring1 grounded",
            ),
            "third": SimpsonShiftState(
                name="third",
                input_member="carrier",
                input_speed=1.0,
                engaged_clutches=("direct_clutch",),
                notes="Direct clutch locks sun and carrier",
            ),
            "reverse": SimpsonShiftState(
                name="reverse",
                input_member="sun",
                input_speed=1.0,
                engaged_brakes=("ring1_brake",),
                notes="Sun input, ring1 grounded",
            ),
        }

    def _build_symbols(self) -> Dict[str, sp.Symbol]:
        return {
            "sun": sp.Symbol("w_sun", real=True),
            "ring1": sp.Symbol("w_ring1", real=True),
            "ring2": sp.Symbol("w_ring2", real=True),
            "carrier": sp.Symbol("w_carrier", real=True),
        }

    def _planetary_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        ws = symbols["sun"]
        wr1 = symbols["ring1"]
        wr2 = symbols["ring2"]
        wc = symbols["carrier"]
        return [
            self.Ns * (ws - wc) + self.Nr1 * (wr1 - wc),
            self.Ns * (ws - wc) + self.Nr2 * (wr2 - wc),
        ]

    def _clutch_equations(self, symbols: Mapping[str, sp.Symbol], engaged_clutches: Sequence[str]) -> List[sp.Expr]:
        equations: List[sp.Expr] = []
        for clutch_name in engaged_clutches:
            if clutch_name == "direct_clutch":
                equations.append(symbols["sun"] - symbols["carrier"])
            else:
                raise ValueError(f"Unknown clutch name: {clutch_name}")
        return equations

    def _brake_equations(self, symbols: Mapping[str, sp.Symbol], engaged_brakes: Sequence[str]) -> List[sp.Expr]:
        equations: List[sp.Expr] = []
        for brake_name in engaged_brakes:
            if brake_name == "ring1_brake":
                equations.append(symbols["ring1"])
            elif brake_name == "ring2_brake":
                equations.append(symbols["ring2"])
            else:
                raise ValueError(f"Unknown brake name: {brake_name}")
        return equations

    def _input_equation(self, symbols: Mapping[str, sp.Symbol], input_member: str, input_speed: float) -> List[sp.Expr]:
        if input_member not in symbols:
            raise ValueError(f"Unknown input member: {input_member}")
        return [symbols[input_member] - float(input_speed)]

    def _assemble_equations(
        self,
        *,
        input_member: str,
        input_speed: float,
        engaged_brakes: Sequence[str],
        engaged_clutches: Sequence[str],
    ) -> Tuple[Dict[str, sp.Symbol], List[sp.Expr], List[str]]:
        symbols = self._build_symbols()
        equations: List[sp.Expr] = []
        labels: List[str] = []

        equations.extend(self._planetary_equations(symbols))
        labels.extend([
            f"PGS1: {self.Ns}(ws-wc) + {self.Nr1}(wr1-wc) = 0",
            f"PGS2: {self.Ns}(ws-wc) + {self.Nr2}(wr2-wc) = 0",
        ])

        clutch_equations = self._clutch_equations(symbols, engaged_clutches)
        equations.extend(clutch_equations)
        labels.extend(["direct_clutch: ws - wc = 0" for _ in clutch_equations])

        brake_equations = self._brake_equations(symbols, engaged_brakes)
        equations.extend(brake_equations)
        for brake_name in engaged_brakes:
            if brake_name == "ring1_brake":
                labels.append("ring1_brake: wr1 = 0")
            elif brake_name == "ring2_brake":
                labels.append("ring2_brake: wr2 = 0")

        equations.extend(self._input_equation(symbols, input_member, input_speed))
        labels.append(f"input: w_{input_member} = {float(input_speed):g}")

        return symbols, equations, labels

    def _solve_linear_system(
        self,
        symbols: Mapping[str, sp.Symbol],
        equations: Sequence[sp.Expr],
    ) -> Tuple[str, str, Dict[str, sp.Expr], int]:
        variables = [symbols[name] for name in self._VALID_MEMBERS]
        A, b = sp.linear_eq_to_matrix(list(equations), variables)
        rank_A = int(A.rank())
        rank_aug = int(A.row_join(b).rank())
        unknown_count = len(variables)

        if rank_aug > rank_A:
            return "no_solution", "inconsistent", {}, rank_A

        result = sp.linsolve((A, b), variables)
        if not result:
            return "no_solution", "inconsistent", {}, rank_A

        tuple_solution = list(result)[0]
        symbolic_solution = {
            name: sp.simplify(expr)
            for name, expr in zip(self._VALID_MEMBERS, tuple_solution)
        }

        if rank_A < unknown_count:
            return "underdetermined", "underdetermined", symbolic_solution, rank_A

        return "ok", "fully_determined", symbolic_solution, rank_A

    def _compute_residuals(
        self,
        symbols: Mapping[str, sp.Symbol],
        equations: Sequence[sp.Expr],
        speeds: Mapping[str, float],
    ) -> Dict[str, float]:
        subs = {
            symbols["sun"]: float(speeds["sun"]),
            symbols["ring1"]: float(speeds["ring1"]),
            symbols["ring2"]: float(speeds["ring2"]),
            symbols["carrier"]: float(speeds["carrier"]),
        }
        return {
            f"eq_{i + 1}": float(sp.N(eq.subs(subs)))
            for i, eq in enumerate(equations)
        }

    def solve_state(
        self,
        *,
        input_member: str,
        input_speed: float = 1.0,
        engaged_brakes: Sequence[str] = (),
        engaged_clutches: Sequence[str] = (),
        state_name: str = "custom",
    ) -> SimpsonSolveReport:
        if input_member not in self._VALID_MEMBERS:
            raise ValueError(f"Unknown input member: {input_member}")

        self._apply_state_elements(
            engaged_brakes=engaged_brakes,
            engaged_clutches=engaged_clutches,
        )
        symbols, equations, equation_labels = self._assemble_equations(
            input_member=input_member,
            input_speed=input_speed,
            engaged_brakes=engaged_brakes,
            engaged_clutches=engaged_clutches,
        )

        self._log(
            "Solving state '%s': input=%s speed=%s brakes=%s clutches_brakes_flywheels=%s",
            state_name,
            input_member,
            input_speed,
            list(engaged_brakes),
            list(engaged_clutches),
        )

        status, classification, symbolic_solution, rank = self._solve_linear_system(symbols, equations)
        report = SimpsonSolveReport(
            ok=(status == "ok"),
            state_name=state_name,
            status=status,
            classification=classification,
            equations=equation_labels,
            active_brakes=list(engaged_brakes),
            active_clutches=list(engaged_clutches),
            symbolic_solution={k: str(v) for k, v in symbolic_solution.items()},
            rank=rank,
            unknown_count=len(symbols),
            equation_count=len(equations),
        )

        if status == "ok":
            speeds = {name: float(sp.N(expr)) for name, expr in symbolic_solution.items()}
            report.speeds = speeds
            report.residuals = self._compute_residuals(symbols, equations, speeds)
            report.message = "State solved successfully"
            self._log("State '%s' solved successfully: %s", state_name, speeds)
            return report

        if status == "underdetermined":
            report.message = "State is underdetermined for the current topology / constraints"
            self._log("State '%s' is underdetermined", state_name)
            return report

        report.message = "State is inconsistent / overconstrained; no physical solution found"
        self._log("State '%s' has no solution", state_name)
        return report

    def solve_named_state(self, name: str, *, input_speed: Optional[float] = None) -> SimpsonSolveReport:
        states = self.standard_states()
        if name not in states:
            raise ValueError(f"Unknown named state: {name}")
        state = states[name]
        return self.solve_state(
            input_member=state.input_member,
            input_speed=state.input_speed if input_speed is None else float(input_speed),
            engaged_brakes=state.engaged_brakes,
            engaged_clutches=state.engaged_clutches,
            state_name=state.name,
        )

    def validate_state(self, name: str) -> bool:
        return self.solve_named_state(name).ok

    def state_report(self, name: str, *, input_speed: Optional[float] = None) -> Dict[str, object]:
        report = self.solve_named_state(name, input_speed=input_speed)
        return {
            "ok": report.ok,
            "state_name": report.state_name,
            "status": report.status,
            "classification": report.classification,
            "equation_count": report.equation_count,
            "unknown_count": report.unknown_count,
            "rank": report.rank,
            "active_brakes": report.active_brakes,
            "active_clutches": report.active_clutches,
            "equations": report.equations,
            "message": report.message,
            "speeds": report.speeds,
            "symbolic_solution": report.symbolic_solution,
            "residuals": report.residuals,
        }

    @staticmethod
    def _speeds_from_report(report: SimpsonSolveReport) -> Dict[str, float]:
        if not report.ok:
            raise RuntimeError(
                f"State '{report.state_name}' did not solve cleanly: "
                f"status={report.status}, classification={report.classification}, message={report.message}"
            )
        return dict(report.speeds)

    def ratio_for_state(
        self,
        state_name: str,
        *,
        numerator_member: str,
        denominator_member: str,
        input_speed: Optional[float] = None,
    ) -> float:
        report = self.solve_named_state(state_name, input_speed=input_speed)
        return gear_ratio(self._speeds_from_report(report), numerator_member, denominator_member)

    def first_gear(self) -> Dict[str, float]:
        return self._speeds_from_report(self.solve_named_state("first"))

    def second_gear(self) -> Dict[str, float]:
        return self._speeds_from_report(self.solve_named_state("second"))

    def third_gear(self) -> Dict[str, float]:
        return self._speeds_from_report(self.solve_named_state("third"))

    def reverse(self) -> Dict[str, float]:
        return self._speeds_from_report(self.solve_named_state("reverse"))


def gear_ratio(result: Mapping[str, float], input_member: str, output_member: str) -> float:
    if input_member not in result:
        raise KeyError(f"Missing input member in result: {input_member}")
    if output_member not in result:
        raise KeyError(f"Missing output member in result: {output_member}")

    denominator = float(result[output_member])
    if abs(denominator) < 1.0e-12:
        raise ZeroDivisionError(f"Output member '{output_member}' has zero speed")

    return float(result[input_member]) / denominator


__all__ = [
    "SimpsonShiftState",
    "SimpsonSolveReport",
    "SimpsonTransmission",
    "configure_logging",
    "gear_ratio",
]
