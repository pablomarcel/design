#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.core.solver

Core V2 transmission kinematic solver.

This module upgrades the original solver by adding:

- linear Willis/simple-planetary equations
- permanent member ties
- optional shaft-node equality constraints
- better solve classification
- cleaner diagnostics for underdetermined / inconsistent systems
- backward-friendly support for the existing component classes

Design intent
-------------
This solver is still kinematic only. It solves angular-speed relationships for:

- rotating members
- planetary gearsets
- clutches_brakes_flywheels
- brakes
- permanent equalities (e.g. front carrier = rear ring = output)
- optional shaft-node equalities

It is designed to become the common engine behind specific transmission scripts
such as Simpson, Ravigneaux, Allison 6-speed, Ford C4, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

import sympy as sp

try:
    from .clutch import Brake, Clutch, RotatingMember
    from .planetary import PlanetaryGearSet
    from .shaft import ShaftNode
except Exception:  # pragma: no cover
    try:
        from clutch import Brake, Clutch, RotatingMember  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore
        from shaft import ShaftNode  # type: ignore
    except Exception:  # pragma: no cover
        from core.clutch import Brake, Clutch, RotatingMember  # type: ignore
        from core.planetary import PlanetaryGearSet  # type: ignore
        from core.shaft import ShaftNode  # type: ignore


class TransmissionSolverError(RuntimeError):
    """Base solver error."""


class DuplicateMemberError(TransmissionSolverError):
    """Raised when duplicate member names are added."""


class UnknownMemberError(TransmissionSolverError):
    """Raised when a required member is missing."""


class InconsistentSystemError(TransmissionSolverError):
    """Raised when the equation system has no solution."""


class UnderdeterminedSystemError(TransmissionSolverError):
    """Raised when a solve exists but does not determine all tracked members."""


@dataclass(frozen=True)
class SolveClassification:
    """
    Human-readable solve classification.

    status:
        One of:
        - ok
        - underdetermined
        - inconsistent
    """

    status: str
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass
class SolveReport:
    """
    Structured solver result/report.
    """

    ok: bool
    classification: SolveClassification
    member_speeds: Dict[str, float] = field(default_factory=dict)
    raw_solution: Optional[dict] = None
    equations: List[sp.Expr] = field(default_factory=list)
    symbols: Dict[str, sp.Symbol] = field(default_factory=dict)
    engaged_clutches: Tuple[str, ...] = ()
    engaged_brakes: Tuple[str, ...] = ()
    permanent_ties: Tuple[Tuple[str, str], ...] = ()
    input_member: Optional[str] = None
    input_speed: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "classification": {
                "status": self.classification.status,
                "message": self.classification.message,
            },
            "member_speeds": dict(self.member_speeds),
            "engaged_clutches": list(self.engaged_clutches),
            "engaged_brakes": list(self.engaged_brakes),
            "permanent_ties": [list(t) for t in self.permanent_ties],
            "input_member": self.input_member,
            "input_speed": self.input_speed,
            "notes": self.notes,
        }


class TransmissionSolver:
    """
    Kinematic solver for transmission systems.

    Core capabilities
    -----------------
    - add rotating members
    - add simple planetary gearsets
    - add clutches_brakes_flywheels and brakes
    - add permanent equalities between members
    - optionally add shaft nodes and tie them by speed
    - solve with a specified input member and speed

    Backward compatibility
    ----------------------
    The existing project uses:
        add_member()
        add_gearset()
        add_clutch()
        add_brake()
        solve(input_member, input_speed)

    Those are preserved.
    """

    def __init__(self) -> None:
        self.members: Dict[str, RotatingMember] = {}
        self.gearsets: List[PlanetaryGearSet] = []
        self.clutches: List[Clutch] = []
        self.brakes: List[Brake] = []
        self.permanent_ties: List[Tuple[str, str]] = []
        self.nodes: Dict[str, ShaftNode] = {}
        self.node_ties: List[Tuple[str, str]] = []

    def add_member(self, member: RotatingMember) -> None:
        if member.name in self.members:
            raise DuplicateMemberError(f"Duplicate member: {member.name}")
        self.members[member.name] = member

    def add_members(self, members: Iterable[RotatingMember]) -> None:
        for member in members:
            self.add_member(member)

    def add_gearset(self, gearset: PlanetaryGearSet) -> None:
        self.gearsets.append(gearset)
        for member in (gearset.sun, gearset.ring, gearset.carrier):
            if member.name not in self.members:
                self.members[member.name] = member

    def add_clutch(self, clutch: Clutch) -> None:
        self.clutches.append(clutch)
        for member in (clutch.member_a, clutch.member_b):
            if member.name not in self.members:
                self.members[member.name] = member

    def add_brake(self, brake: Brake) -> None:
        self.brakes.append(brake)
        if brake.member.name not in self.members:
            self.members[brake.member.name] = brake.member

    def add_permanent_tie(self, member_a: str | RotatingMember, member_b: str | RotatingMember) -> None:
        a = member_a.name if isinstance(member_a, RotatingMember) else str(member_a)
        b = member_b.name if isinstance(member_b, RotatingMember) else str(member_b)
        if not a or not b:
            raise TransmissionSolverError("Permanent tie member names must be non-empty.")
        self.permanent_ties.append((a, b))

    def clear_permanent_ties(self) -> None:
        self.permanent_ties.clear()

    def add_node(self, node: ShaftNode) -> None:
        if node.name in self.nodes:
            raise TransmissionSolverError(f"Duplicate node: {node.name}")
        self.nodes[node.name] = node

    def add_node_tie(self, node_a: str | ShaftNode, node_b: str | ShaftNode) -> None:
        a = node_a.name if isinstance(node_a, ShaftNode) else str(node_a)
        b = node_b.name if isinstance(node_b, ShaftNode) else str(node_b)
        if not a or not b:
            raise TransmissionSolverError("Node tie names must be non-empty.")
        self.node_ties.append((a, b))

    def _build_symbols(self) -> Dict[str, sp.Symbol]:
        return {name: sp.Symbol(f"w_{name}", real=True) for name in self.members}

    def _require_member(self, member_name: str, *, context: str = "") -> None:
        if member_name not in self.members:
            if context:
                raise UnknownMemberError(f"Unknown member '{member_name}' required by {context}.")
            raise UnknownMemberError(f"Unknown member: {member_name}")

    def _planetary_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        equations: List[sp.Expr] = []
        for gearset in self.gearsets:
            sun = gearset.sun.name
            ring = gearset.ring.name
            carrier = gearset.carrier.name
            self._require_member(sun, context=f"gearset {gearset.name}")
            self._require_member(ring, context=f"gearset {gearset.name}")
            self._require_member(carrier, context=f"gearset {gearset.name}")
            ws = symbols[sun]
            wr = symbols[ring]
            wc = symbols[carrier]
            eq = gearset.Ns * (ws - wc) + gearset.Nr * (wr - wc)
            equations.append(eq)
        return equations

    def _clutch_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        equations: List[sp.Expr] = []
        for clutch in self.clutches:
            if not clutch.engaged:
                continue
            pair = clutch.constraint()
            if pair is None:
                continue
            member_a, member_b = pair
            self._require_member(member_a.name, context=f"clutch {clutch.name}")
            self._require_member(member_b.name, context=f"clutch {clutch.name}")
            equations.append(symbols[member_a.name] - symbols[member_b.name])
        return equations

    def _brake_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        equations: List[sp.Expr] = []
        for brake in self.brakes:
            if not brake.engaged:
                continue
            pair = brake.constraint()
            if pair is None:
                continue
            member, _ground = pair
            self._require_member(member.name, context=f"brake {brake.name}")
            equations.append(symbols[member.name])
        return equations

    def _permanent_tie_equations(self, symbols: Mapping[str, sp.Symbol]) -> List[sp.Expr]:
        equations: List[sp.Expr] = []
        for a, b in self.permanent_ties:
            self._require_member(a, context="permanent tie")
            self._require_member(b, context="permanent tie")
            equations.append(symbols[a] - symbols[b])
        return equations

    def _node_equations(self) -> List[sp.Expr]:
        equations: List[sp.Expr] = []
        for node in self.nodes.values():
            if node.is_ground:
                equations.append(node.ground_equation())
        for a, b in self.node_ties:
            if a not in self.nodes:
                raise TransmissionSolverError(f"Unknown node in node tie: {a}")
            if b not in self.nodes:
                raise TransmissionSolverError(f"Unknown node in node tie: {b}")
            equations.append(self.nodes[a].equality_equation(self.nodes[b]))
        return equations

    def _input_equation(self, symbols: Mapping[str, sp.Symbol], input_member: str, speed: float) -> List[sp.Expr]:
        self._require_member(input_member, context="input condition")
        return [symbols[input_member] - float(speed)]

    def build_equations(
        self,
        *,
        input_member: str,
        input_speed: float = 1.0,
        include_nodes: bool = False,
    ) -> Tuple[List[sp.Expr], Dict[str, sp.Symbol]]:
        symbols = self._build_symbols()
        equations: List[sp.Expr] = []
        equations += self._planetary_equations(symbols)
        equations += self._clutch_equations(symbols)
        equations += self._brake_equations(symbols)
        equations += self._permanent_tie_equations(symbols)
        equations += self._input_equation(symbols, input_member, input_speed)
        if include_nodes:
            equations += self._node_equations()
        return equations, symbols

    def _classify_solution(self, *, solution_list: List[dict], symbols: Mapping[str, sp.Symbol]) -> SolveClassification:
        if not solution_list:
            return SolveClassification("inconsistent", "No solution found for the assembled transmission equations.")
        sol0 = solution_list[0]
        unresolved = [name for name, sym in symbols.items() if sym not in sol0]
        if unresolved:
            msg = "Underdetermined member speeds: " + ", ".join(unresolved)
            return SolveClassification("underdetermined", msg)
        return SolveClassification("ok", "Fully determined member-speed solution.")

    def solve_report(self, input_member: str, input_speed: float = 1.0, *, include_nodes: bool = False) -> SolveReport:
        equations, symbols = self.build_equations(
            input_member=input_member,
            input_speed=input_speed,
            include_nodes=include_nodes,
        )
        variables = list(symbols.values())
        try:
            solution_list = sp.solve(equations, variables, dict=True)
        except Exception as exc:  # pragma: no cover
            raise TransmissionSolverError(f"SymPy solve failure: {exc}") from exc

        classification = self._classify_solution(solution_list=solution_list, symbols=symbols)
        engaged_clutches = tuple(c.name or "" for c in self.clutches if c.engaged)
        engaged_brakes = tuple(b.name or "" for b in self.brakes if b.engaged)

        if not solution_list:
            return SolveReport(
                ok=False,
                classification=classification,
                member_speeds={},
                raw_solution=None,
                equations=equations,
                symbols=dict(symbols),
                engaged_clutches=engaged_clutches,
                engaged_brakes=engaged_brakes,
                permanent_ties=tuple(self.permanent_ties),
                input_member=input_member,
                input_speed=float(input_speed),
            )

        sol0 = solution_list[0]
        member_speeds: Dict[str, float] = {}
        for name, sym in symbols.items():
            if sym in sol0:
                member_speeds[name] = float(sp.N(sol0[sym]))

        return SolveReport(
            ok=classification.ok,
            classification=classification,
            member_speeds=member_speeds,
            raw_solution=sol0,
            equations=equations,
            symbols=dict(symbols),
            engaged_clutches=engaged_clutches,
            engaged_brakes=engaged_brakes,
            permanent_ties=tuple(self.permanent_ties),
            input_member=input_member,
            input_speed=float(input_speed),
        )

    def solve(
        self,
        input_member: str,
        input_speed: float = 1.0,
        *,
        allow_underdetermined: bool = False,
        include_nodes: bool = False,
    ) -> Dict[str, float]:
        report = self.solve_report(
            input_member=input_member,
            input_speed=input_speed,
            include_nodes=include_nodes,
        )
        if report.classification.status == "inconsistent":
            raise InconsistentSystemError(report.classification.message)
        if report.classification.status == "underdetermined" and not allow_underdetermined:
            raise UnderdeterminedSystemError(report.classification.message)
        return dict(report.member_speeds)

    def release_all(self) -> None:
        for clutch in self.clutches:
            clutch.release()
        for brake in self.brakes:
            brake.release()

    def active_constraint_names(self) -> Dict[str, Tuple[str, ...]]:
        return {
            "clutches_brakes_flywheels": tuple(c.name or "" for c in self.clutches if c.engaged),
            "brakes": tuple(b.name or "" for b in self.brakes if b.engaged),
        }

    def summary_dict(self) -> dict:
        return {
            "members": sorted(self.members.keys()),
            "gearsets": [
                {
                    "name": g.name,
                    "Ns": g.Ns,
                    "Nr": g.Nr,
                    "sun": g.sun.name,
                    "ring": g.ring.name,
                    "carrier": g.carrier.name,
                    "geometry_mode": getattr(g, "geometry_mode", "relaxed"),
                }
                for g in self.gearsets
            ],
            "clutches_brakes_flywheels": [
                {
                    "name": c.name,
                    "member_a": c.member_a.name,
                    "member_b": c.member_b.name,
                    "engaged": bool(c.engaged),
                }
                for c in self.clutches
            ],
            "brakes": [
                {
                    "name": b.name,
                    "member": b.member.name,
                    "engaged": bool(b.engaged),
                }
                for b in self.brakes
            ],
            "permanent_ties": [list(t) for t in self.permanent_ties],
            "nodes": [node.summary_dict() for node in self.nodes.values()],
            "node_ties": [list(t) for t in self.node_ties],
        }
