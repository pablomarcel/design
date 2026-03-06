#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.core.solver

Transmission kinematic solver.

Builds and solves speed equations for planetary gearsets,
clutches, and brakes.

Uses symbolic solving via SymPy.

Supports multiple planetary gearsets (Simpson, Ravigneaux, etc.)

Author: Pablo Montijo Design Project
"""

from typing import Dict, List

import sympy as sp

from .clutch import Clutch, Brake, RotatingMember
from .planetary import PlanetaryGearSet


# ------------------------------------------------------------
# Solver
# ------------------------------------------------------------

class TransmissionSolver:
    """
    Kinematic solver for transmission systems.

    Handles:

    - rotating members
    - planetary gearsets
    - clutches
    - brakes
    """

    def __init__(self):

        self.members: Dict[str, RotatingMember] = {}

        self.gearsets: List[PlanetaryGearSet] = []

        self.clutches: List[Clutch] = []
        self.brakes: List[Brake] = []

    # --------------------------------------------------------
    # Add components
    # --------------------------------------------------------

    def add_member(self, member: RotatingMember):

        if member.name in self.members:
            raise ValueError(f"Duplicate member: {member.name}")

        self.members[member.name] = member

    # --------------------------------------------------------

    def add_gearset(self, gearset: PlanetaryGearSet):

        self.gearsets.append(gearset)

    # --------------------------------------------------------

    def add_clutch(self, clutch: Clutch):

        self.clutches.append(clutch)

    # --------------------------------------------------------

    def add_brake(self, brake: Brake):

        self.brakes.append(brake)

    # --------------------------------------------------------
    # Build symbolic variables
    # --------------------------------------------------------

    def _build_symbols(self):

        symbols = {}

        for name in self.members:

            symbols[name] = sp.symbols(f"w_{name}")

        return symbols

    # --------------------------------------------------------
    # Planetary equations
    # --------------------------------------------------------

    def _planetary_equations(self, symbols):

        """
        Willis equations for each planetary gearset.
        """

        equations = []

        for g in self.gearsets:

            sun = g.sun.name
            ring = g.ring.name
            carrier = g.carrier.name

            ws = symbols[sun]
            wr = symbols[ring]
            wc = symbols[carrier]

            Ns = g.Ns
            Nr = g.Nr

            eq = (ws - wc) / (wr - wc) + Nr / Ns

            equations.append(eq)

        return equations

    # --------------------------------------------------------
    # Clutch equations
    # --------------------------------------------------------

    def _clutch_equations(self, symbols):

        equations = []

        for c in self.clutches:

            if not c.engaged:
                continue

            a, b = c.constraint()

            wa = symbols[a.name]
            wb = symbols[b.name]

            equations.append(wa - wb)

        return equations

    # --------------------------------------------------------
    # Brake equations
    # --------------------------------------------------------

    def _brake_equations(self, symbols):

        equations = []

        for b in self.brakes:

            if not b.engaged:
                continue

            member, ground = b.constraint()

            w = symbols[member.name]

            equations.append(w)

        return equations

    # --------------------------------------------------------
    # Input speed
    # --------------------------------------------------------

    def _input_equation(self, symbols, input_member, speed):

        if input_member not in symbols:
            raise ValueError(f"Unknown input member: {input_member}")

        return [symbols[input_member] - speed]

    # --------------------------------------------------------
    # Solve system
    # --------------------------------------------------------

    def solve(self, input_member: str, input_speed: float = 1.0):

        symbols = self._build_symbols()

        equations = []

        # planetary kinematics
        equations += self._planetary_equations(symbols)

        # clutch constraints
        equations += self._clutch_equations(symbols)

        # brake constraints
        equations += self._brake_equations(symbols)

        # input speed
        equations += self._input_equation(symbols, input_member, input_speed)

        variables = list(symbols.values())

        solution = sp.solve(equations, variables, dict=True)

        if not solution:
            raise RuntimeError("Transmission solver: no solution found")

        sol = solution[0]

        results = {}

        for name, sym in symbols.items():

            if sym not in sol:
                raise RuntimeError(
                    f"Undetermined variable in solution: {name}"
                )

            results[name] = float(sol[sym])

        return results