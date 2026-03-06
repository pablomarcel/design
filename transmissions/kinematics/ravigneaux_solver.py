#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.ravigneaux_solver

State-based Ravignaux transmission kinematic solver.

Honesty note
------------
This module models a **simplified kinematic Ravignaux abstraction** with four
rotating members:

    sun_small, sun_large, ring, carrier

and two linear Willis relations sharing one ring and one carrier:

    Ns_small (w_s_small - w_c) + Nr (w_r - w_c) = 0
    Ns_large (w_s_large - w_c) + Nr (w_r - w_c) = 0

This is useful for ratio exploration and state consistency checking, but it is
not a full compound-pinion production transmission synthesis.

Upgraded standard states
------------------------
The standard states below are chosen to make the 4-forward-speed explorer more
informative than the earlier version where 3rd dropped the large sun out of the
ratio completely:

1st:
    input = sun_small, ring grounded, output = carrier

2nd:
    input = sun_large, ring grounded, output = carrier

3rd:
    input = ring, sun_large grounded, output = carrier

4th:
    direct clutch locks ring and carrier, input = ring, output = carrier

Reverse:
    input = sun_small, carrier grounded, output = ring

Important limitation
--------------------
Within this 4-member abstraction, the standard reverse state still depends only
on sun_small and ring. The large sun does not participate in the standard
reverse state unless the topology itself is enriched beyond the present model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import sys
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import sympy as sp

try:
    from transmissions.core.clutch import RotatingMember, Clutch, Brake
    from transmissions.core.planetary import PlanetaryGearSet
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
        from core.clutch import RotatingMember, Clutch, Brake  # type: ignore
        from core.planetary import PlanetaryGearSet  # type: ignore


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
    output_member: str
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
    input_member: str
    output_member: str
    speeds: Dict[str, float] = field(default_factory=dict)
    symbolic_solution: Dict[str, str] = field(default_factory=dict)
    residuals: Dict[str, float] = field(default_factory=dict)
    ratio: Optional[float] = None
    rank: int = 0
    unknown_count: int = 0
    equation_count: int = 0
    message: str = ""


@dataclass
class RatioAudit:
    state_name: str
    ratio_expression: str
    depends_on: List[str]
    input_member: str
    output_member: str
    notes: str = ""


class RavigneauxTransmission:
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
        self.carrier_brake = Brake(self.carrier, name="carrier_brake")

        self.direct_clutch = Clutch(self.ring, self.carrier, name="direct_clutch")
        self.sun_sync_clutch = Clutch(self.sun_small, self.sun_large, name="sun_sync_clutch")

    def _log(self, msg: str, *args) -> None:
        if self.enable_logging:
            LOGGER.info(msg, *args)

    def reset(self) -> None:
        self.ring_brake.release()
        self.sun_small_brake.release()
        self.sun_large_brake.release()
        self.carrier_brake.release()
        self.direct_clutch.release()
        self.sun_sync_clutch.release()

    def _apply_state_elements(self, *, engaged_brakes: Sequence[str], engaged_clutches: Sequence[str]) -> None:
        self.reset()
        brake_map = {
            "ring_brake": self.ring_brake,
            "sun_small_brake": self.sun_small_brake,
            "sun_large_brake": self.sun_large_brake,
            "carrier_brake": self.carrier_brake,
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

    @staticmethod
    def standard_states() -> Dict[str, RavigneauxShiftState]:
        return {
            "first": RavigneauxShiftState(
                name="first",
                input_member="sun_small",
                output_member="carrier",
                engaged_brakes=("ring_brake",),
                notes="Small sun input, ring grounded, carrier output",
            ),
            "second": RavigneauxShiftState(
                name="second",
                input_member="sun_large",
                output_member="carrier",
                engaged_brakes=("ring_brake",),
                notes="Large sun input, ring grounded, carrier output",
            ),
            "third": RavigneauxShiftState(
                name="third",
                input_member="ring",
                output_member="carrier",
                engaged_brakes=("sun_large_brake",),
                notes="Ring input, large sun grounded, carrier output",
            ),
            "fourth": RavigneauxShiftState(
                name="fourth",
                input_member="ring",
                output_member="carrier",
                engaged_clutches=("direct_clutch",),
                notes="Direct clutch locks ring and carrier",
            ),
            "reverse": RavigneauxShiftState(
                name="reverse",
                input_member="sun_small",
                output_member="ring",
                engaged_brakes=("carrier_brake",),
                notes="Small sun input, carrier grounded, ring output",
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
        for brake in (self.ring_brake, self.sun_small_brake, self.sun_large_brake, self.carrier_brake):
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
        output_member: str,
        input_speed: float = 1.0,
        engaged_brakes: Sequence[str] = (),
        engaged_clutches: Sequence[str] = (),
    ) -> RavigneauxSolveReport:
        if input_member not in self._VALID_MEMBERS:
            raise ValueError(f"Unknown input member: {input_member}")
        if output_member not in self._VALID_MEMBERS:
            raise ValueError(f"Unknown output member: {output_member}")

        self._apply_state_elements(engaged_brakes=engaged_brakes, engaged_clutches=engaged_clutches)

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
        ratio: Optional[float] = None
        message = ""

        if ok:
            solution_vec, _params = matrix.gauss_jordan_solve(vector)
            substitutions = {}
            for idx, name in enumerate(self._VALID_MEMBERS):
                expr = sp.simplify(solution_vec[idx, 0])
                symbolic_solution[name] = str(expr)
                numeric_speeds[name] = float(expr.evalf())
                substitutions[symbols[name]] = numeric_speeds[name]
            for i, eq in enumerate(equations, start=1):
                residuals[f"eq_{i}"] = float(sp.N(eq.subs(substitutions)))
            try:
                ratio = gear_ratio(numeric_speeds, input_member, output_member)
            except Exception:
                ratio = None
            message = "Solved cleanly"
        else:
            message = (
                "State is underdetermined for the current engaged elements"
                if status == "underdetermined"
                else "State is inconsistent / overconstrained"
            )

        return RavigneauxSolveReport(
            ok=ok,
            state_name=state_name,
            status=status,
            classification=classification,
            equations=[str(sp.expand(eq)) for eq in equations],
            active_brakes=list(engaged_brakes),
            active_clutches=list(engaged_clutches),
            input_member=input_member,
            output_member=output_member,
            speeds=numeric_speeds,
            symbolic_solution=symbolic_solution,
            residuals=residuals,
            ratio=ratio,
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
            output_member=state.output_member,
            input_speed=state.input_speed if input_speed is None else float(input_speed),
            engaged_brakes=state.engaged_brakes,
            engaged_clutches=state.engaged_clutches,
        )

    def ratio_for_state(self, state_name: str, *, input_speed: Optional[float] = None) -> float:
        report = self.solve_named_state(state_name, input_speed=input_speed)
        if not report.ok:
            raise RuntimeError(
                f"State '{state_name}' did not solve cleanly: "
                f"status={report.status}, classification={report.classification}, message={report.message}"
            )
        return gear_ratio(report.speeds, report.input_member, report.output_member)

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
            "input_member": report.input_member,
            "output_member": report.output_member,
            "ratio": report.ratio,
            "speeds": report.speeds,
            "symbolic_solution": report.symbolic_solution,
            "residuals": report.residuals,
        }

    def _symbolic_solve_named_state(self, state_name: str) -> Tuple[Dict[str, sp.Expr], RavigneauxShiftState]:
        states = self.standard_states()
        if state_name not in states:
            raise ValueError(f"Unknown standard state: {state_name}")
        state = states[state_name]
        symbols = self._member_symbols()
        self._apply_state_elements(
            engaged_brakes=state.engaged_brakes,
            engaged_clutches=state.engaged_clutches,
        )
        equations = self._base_equations(symbols)
        equations.extend(self._constraint_equations(symbols))
        equations.append(symbols[state.input_member] - 1.0)
        unknowns = [symbols[name] for name in self._VALID_MEMBERS]
        matrix, vector = sp.linear_eq_to_matrix(equations, unknowns)
        augmented = matrix.row_join(vector)
        rank = int(matrix.rank())
        augmented_rank = int(augmented.rank())
        status, classification, ok = self._classification(rank, len(unknowns), augmented_rank)
        if not ok:
            raise RuntimeError(
                f"State '{state_name}' is not fully determined symbolically: status={status}, classification={classification}"
            )
        solution_vec, _params = matrix.gauss_jordan_solve(vector)
        return {name: sp.simplify(solution_vec[idx, 0]) for idx, name in enumerate(self._VALID_MEMBERS)}, state

    def ratio_expression_for_state(self, state_name: str) -> sp.Expr:
        solution, state = self._symbolic_solve_named_state(state_name)
        return sp.simplify(solution[state.input_member] / solution[state.output_member])

    def audit_standard_states(self) -> Dict[str, RatioAudit]:
        Ns_small, Ns_large, Nr = sp.symbols("Ns_small Ns_large Nr", positive=True)
        audits: Dict[str, RatioAudit] = {}
        expressions = {
            "first": sp.simplify(1 + Nr / Ns_small),
            "second": sp.simplify(1 + Nr / Ns_large),
            "third": sp.simplify(1 + Ns_large / Nr),
            "fourth": sp.Integer(1),
            "reverse": sp.simplify(-Nr / Ns_small),
        }
        for name, state in self.standard_states().items():
            expr = expressions[name]
            depends = []
            if sp.simplify(sp.diff(expr, Ns_small)) != 0:
                depends.append("Ns_small")
            if sp.simplify(sp.diff(expr, Ns_large)) != 0:
                depends.append("Ns_large")
            if sp.simplify(sp.diff(expr, Nr)) != 0:
                depends.append("Nr")
            note = state.notes
            if name == "reverse":
                note += "; large sun does not participate in standard reverse within this simplified topology"
            audits[name] = RatioAudit(
                state_name=name,
                ratio_expression=str(expr),
                depends_on=depends,
                input_member=state.input_member,
                output_member=state.output_member,
                notes=note,
            )
        return audits

    def first_gear(self) -> Dict[str, float]:
        report = self.solve_named_state("first")
        if not report.ok:
            raise RuntimeError(report.message)
        return dict(report.speeds)

    def second_gear(self) -> Dict[str, float]:
        report = self.solve_named_state("second")
        if not report.ok:
            raise RuntimeError(report.message)
        return dict(report.speeds)

    def third_gear(self) -> Dict[str, float]:
        report = self.solve_named_state("third")
        if not report.ok:
            raise RuntimeError(report.message)
        return dict(report.speeds)

    def fourth_gear(self) -> Dict[str, float]:
        report = self.solve_named_state("fourth")
        if not report.ok:
            raise RuntimeError(report.message)
        return dict(report.speeds)

    def reverse(self) -> Dict[str, float]:
        report = self.solve_named_state("reverse")
        if not report.ok:
            raise RuntimeError(report.message)
        return dict(report.speeds)


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
    "RatioAudit",
    "RavigneauxTransmission",
    "configure_logging",
    "gear_ratio",
]
