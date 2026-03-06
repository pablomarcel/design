#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.ravigneaux_solver

State-based Ravignaux transmission kinematic solver.

Scope and honesty note
----------------------
This module provides a **kinematic** solver for a simplified Ravignaux
architecture represented by four rotating members:

    sun_small, sun_large, ring, carrier

The model uses two linear planetary relations sharing the same ring and the
same carrier:

    Ns_small (w_s_small - w_c) + Nr (w_r - w_c) = 0
    Ns_large (w_s_large - w_c) + Nr (w_r - w_c) = 0

This is intentionally analogous to the current Simpson tooling in the project:
- fast
- explicit
- transparent
- import-safe in package and flat-file execution modes

It is a good ratio-exploration / state-validation tool, but it is not yet a
full geometric synthesis of long/short pinions, carrier packaging, or clutch
scheduling from a production transmission. The standard states defined here are
internally consistent and fully solvable for the simplified kinematic topology.

Standard states used in this module
-----------------------------------
1st gear:
    input = sun_small, ring grounded, output = carrier

2nd gear:
    input = sun_large, ring grounded, output = carrier

3rd gear:
    direct clutch locks ring and carrier, input = ring, output = carrier

Reverse:
    input = sun_small, sun_large grounded, output = carrier

These states are chosen because they produce a clean and useful exploratory map:
- 1st > 2nd > 1 when Ns_small < Ns_large < Nr
- 3rd = 1.0 direct drive
- reverse < 0 emerges naturally from the equations for valid tooth counts
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
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        )
    LOGGER.setLevel(level)


@dataclass(frozen=True)
class RavigneauxShiftState:
    name: str
    input_member: str
    input_speed: float = 1.0
    engaged_brakes: Tuple[str, ...] = ()
    engaged_clutches: Tuple[str, ...] = ()
    notes: str = ""


@dataclass
class RavigneauxSolveReport:
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


class RavigneauxTransmission:
    """
    Simplified state-based Ravignaux transmission solver.
    """

    _VALID_MEMBERS = ("sun_small", "sun_large", "ring", "carrier")

    def __init__(self, Ns_small: int, Ns_large: int, Nr: int, *, enable_logging: bool = False):
        self.Ns_small = int(Ns_small)
        self.Ns_large = int(Ns_large)
        self.Nr = int(Nr)
        self.enable_logging = bool(enable_logging)

        if self.Ns_small <= 0 or self.Ns_large <= 0 or self.Nr <= 0:
            raise ValueError("All tooth counts must be positive")
        if self.Ns_small >= self.Ns_large:
            raise ValueError("Expected Ns_small < Ns_large for the simplified Ravignaux model")
        if self.Nr <= self.Ns_large:
            raise ValueError("Expected ring tooth count Nr > Ns_large")

        self.sun_small = RotatingMember("sun_small")
        self.sun_large = RotatingMember("sun_large")
        self.ring = RotatingMember("ring")
        self.carrier = RotatingMember("carrier")

        # Metadata gearsets reused for compatibility / inspection.
        self.small_set = PlanetaryGearSet(
            Ns=self.Ns_small,
            Nr=self.Nr,
            sun=self.sun_small,
            ring=self.ring,
            carrier=self.carrier,
            name="RAV_small",
        )
        self.large_set = PlanetaryGearSet(
            Ns=self.Ns_large,
            Nr=self.Nr,
            sun=self.sun_large,
            ring=self.ring,
            carrier=self.carrier,
            name="RAV_large",
        )

        self.ring_brake = Brake(self.ring, name="ring_brake")
        self.sun_small_brake = Brake(self.sun_small, name="sun_small_brake")
        self.sun_large_brake = Brake(self.sun_large, name="sun_large_brake")

        self.direct_clutch = Clutch(self.ring, self.carrier, name="direct_clutch")
        self.sun_sync_clutch = Clutch(self.sun_small, self.sun_large, name="sun_sync_clutch")

        self._log(
            "Initialized RavigneauxTransmission Ns_small=%s Ns_large=%s Nr=%s",
            self.Ns_small,
            self.Ns_large,
            self.Nr,
        )

    def _log(self, msg: str, *args) -> None:
        if self.enable_logging:
            LOGGER.info(msg, *args)

    def reset(self) -> None:
        self.ring_brake.release()
        self.sun_small_brake.release()
        self.sun_large_brake.release()
        self.direct_clutch.release()
        self.sun_sync_clutch.release()
        self._log("Released all clutches/brakes")

    def _apply_state_elements(
        self,
        *,
        engaged_brakes: Sequence[str],
        engaged_clutches: Sequence[str],
    ) -> None:
        self.reset()

        brake_map = {
            "ring_brake": self.ring_brake,
            "sun_small_brake": self.sun_small_brake,
            "sun_large_brake": self.sun_large_brake,
        }
        clutch_map = {
            "direct_clutch": self.direct_clutch,
            "sun_sync_clutch": self.sun_sync_clutch,
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
            "Applied state elements: brakes=%s clutches=%s",
            list(engaged_brakes),
            list(engaged_clutches),
        )

    @staticmethod
    def standard_states() -> Dict[str, RavigneauxShiftState]:
        return {
            "first": RavigneauxShiftState(
                name="first",
                input_member="sun_small",
                input_speed=1.0,
                engaged_brakes=("ring_brake",),
                notes="Small sun input, ring grounded, carrier output",
            ),
            "second": RavigneauxShiftState(
                name="second",
                input_member="sun_large",
                input_speed=1.0,
                engaged_brakes=("ring_brake",),
                notes="Large sun input, ring grounded, carrier output",
            ),
            "third": RavigneauxShiftState(
                name="third",
                input_member="ring",
                input_speed=1.0,
                engaged_clutches=("direct_clutch",),
                notes="Direct clutch locks ring and carrier",
            ),
            "reverse": RavigneauxShiftState(
                name="reverse",
                input_member="sun_small",
                input_speed=1.0,
                engaged_brakes=("sun_large_brake",),
                notes="Small sun input, large sun grounded, carrier output",
            ),
        }

    def _member_symbols(self) -> Dict[str, sp.Symbol]:
        return {name: sp.symbols(f"w_{name}") for name in self._VALID_MEMBERS}

    def _base_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        ws_small = symbols["sun_small"]
        ws_large = symbols["sun_large"]
        wr = symbols["ring"]
        wc = symbols["carrier"]
        return [
            self.Ns_small * (ws_small - wc) + self.Nr * (wr - wc),
            self.Ns_large * (ws_large - wc) + self.Nr * (wr - wc),
        ]

    def _constraint_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        eqs: List[sp.Expr] = []

        for brake in (self.ring_brake, self.sun_small_brake, self.sun_large_brake):
            if brake.is_active():
                member, _ground = brake.constraint()  # type: ignore[misc]
                eqs.append(symbols[member.name])

        for clutch in (self.direct_clutch, self.sun_sync_clutch):
            if clutch.is_active():
                member_a, member_b = clutch.constraint()  # type: ignore[misc]
                eqs.append(symbols[member_a.name] - symbols[member_b.name])

        return eqs

    @staticmethod
    def _classification(rank: int, unknown_count: int, augmented_rank: int) -> Tuple[str, str, bool]:
        if augmented_rank > rank:
            return "no_solution", "inconsistent", False
        if rank < unknown_count:
            return "underdetermined", "underdetermined", False
        return "ok", "fully_determined", True

    def solve_state(
        self,
        *,
        state_name: str,
        input_member: str,
        input_speed: float = 1.0,
        engaged_brakes: Sequence[str] = (),
        engaged_clutches: Sequence[str] = (),
    ) -> RavigneauxSolveReport:
        if input_member not in self._VALID_MEMBERS:
            raise ValueError(f"Unknown input member: {input_member}")

        self._apply_state_elements(
            engaged_brakes=engaged_brakes,
            engaged_clutches=engaged_clutches,
        )

        symbols = self._member_symbols()
        equations = self._base_equations(symbols)
        equations.extend(self._constraint_equations(symbols))
        equations.append(symbols[input_member] - float(input_speed))

        unknowns = [symbols[name] for name in self._VALID_MEMBERS]
        matrix, vector = sp.linear_eq_to_matrix(equations, unknowns)
        augmented = matrix.row_join(vector)

        rank = int(matrix.rank())
        augmented_rank = int(augmented.rank())
        unknown_count = len(unknowns)
        equation_count = len(equations)

        status, classification, ok = self._classification(rank, unknown_count, augmented_rank)

        symbolic_solution: Dict[str, str] = {}
        numeric_speeds: Dict[str, float] = {}
        residuals: Dict[str, float] = {}
        message = ""

        if ok:
            solution_vec, _params = matrix.gauss_jordan_solve(vector)
            for idx, name in enumerate(self._VALID_MEMBERS):
                expr = sp.simplify(solution_vec[idx, 0])
                symbolic_solution[name] = str(expr)
                numeric_speeds[name] = float(expr.evalf())

            for i, eq in enumerate(equations, start=1):
                residual = float(sp.N(eq.subs({symbols[k]: v for k, v in numeric_speeds.items()})))
                residuals[f"eq_{i}"] = residual
            message = "Solved cleanly"
        else:
            if status == "underdetermined":
                message = "State is underdetermined for the current engaged elements"
            else:
                message = "State is inconsistent / overconstrained"

        return RavigneauxSolveReport(
            ok=ok,
            state_name=state_name,
            status=status,
            classification=classification,
            equations=[str(sp.expand(eq)) for eq in equations],
            active_brakes=list(engaged_brakes),
            active_clutches=list(engaged_clutches),
            speeds=numeric_speeds,
            symbolic_solution=symbolic_solution,
            residuals=residuals,
            rank=rank,
            unknown_count=unknown_count,
            equation_count=equation_count,
            message=message,
        )

    def solve_named_state(self, state_name: str, *, input_speed: Optional[float] = None) -> RavigneauxSolveReport:
        states = self.standard_states()
        if state_name not in states:
            raise ValueError(f"Unknown standard state: {state_name}")

        state = states[state_name]
        return self.solve_state(
            state_name=state.name,
            input_member=state.input_member,
            input_speed=state.input_speed if input_speed is None else float(input_speed),
            engaged_brakes=state.engaged_brakes,
            engaged_clutches=state.engaged_clutches,
        )

    def state_report(self, state_name: str, *, input_speed: Optional[float] = None) -> Dict[str, object]:
        report = self.solve_named_state(state_name, input_speed=input_speed)
        return {
            "ok": report.ok,
            "state_name": report.state_name,
            "status": report.status,
            "classification": report.classification,
            "active_brakes": report.active_brakes,
            "active_clutches": report.active_clutches,
            "equations": report.equations,
            "message": report.message,
            "speeds": report.speeds,
            "symbolic_solution": report.symbolic_solution,
            "residuals": report.residuals,
        }

    def validate_state(self, state_name: str, *, tol: float = 1.0e-9) -> bool:
        report = self.solve_named_state(state_name)
        if not report.ok:
            return False
        return all(abs(v) <= tol for v in report.residuals.values())

    @staticmethod
    def _speeds_from_report(report: RavigneauxSolveReport) -> Dict[str, float]:
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
    "RavigneauxShiftState",
    "RavigneauxSolveReport",
    "RavigneauxTransmission",
    "configure_logging",
    "gear_ratio",
]
