#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.core.planetary

Planetary gearset kinematic model.

Implements the canonical planetary gear equation:

    Ns (ωs − ωc) + Nr (ωr − ωc) = 0

Equivalent to the Willis equation.

Where:
    s = sun
    r = ring
    c = carrier

This module solves planetary speed relationships for any
combination of input/output/fixed members.

Author: Pablo Montijo Design Project
"""

from dataclasses import dataclass
from typing import Dict


# ------------------------------------------------------------
# Gear components
# ------------------------------------------------------------

@dataclass
class Gear:
    name: str
    teeth: int

    def __repr__(self):
        return f"{self.name}(N={self.teeth})"


# ------------------------------------------------------------
# Planetary gearset
# ------------------------------------------------------------

class PlanetaryGearSet:
    """
    Represents a simple planetary gearset.

           Ring (Nr)
        ----------------
        |      o       |
        |   o     o    |
        |      Sun     |
        ----------------
             Carrier
    """

    def __init__(self, Ns: int, Nr: int, name: str = "PGS"):

        if Ns <= 0 or Nr <= 0:
            raise ValueError("Gear tooth counts must be positive")

        if Nr <= Ns:
            raise ValueError("Ring must have more teeth than sun")

        self.name = name

        self.Ns = Ns
        self.Nr = Nr
        self.Np = (Nr - Ns) // 2

        if self.Np <= 0:
            raise ValueError("Invalid planetary geometry")

        self.sun = Gear("sun", Ns)
        self.ring = Gear("ring", Nr)
        self.carrier = Gear("carrier", 0)

    # --------------------------------------------------------
    # Core planetary equation
    # --------------------------------------------------------

    def planetary_equation(self, ws: float, wr: float, wc: float) -> float:
        """
        Residual of the planetary constraint equation.
        """

        return self.Ns * (ws - wc) + self.Nr * (wr - wc)

    # --------------------------------------------------------
    # Solve speeds
    # --------------------------------------------------------

    def solve(
        self,
        input_member: str,
        output_member: str,
        fixed_member: str,
        input_speed: float = 1.0
    ) -> Dict[str, float]:

        members = {"sun", "ring", "carrier"}

        if len({input_member, output_member, fixed_member}) != 3:
            raise ValueError("input, output, and fixed must all be different")

        if input_member not in members:
            raise ValueError("invalid input member")

        if output_member not in members:
            raise ValueError("invalid output member")

        if fixed_member not in members:
            raise ValueError("invalid fixed member")

        ws = None
        wr = None
        wc = None

        # assign input speed
        if input_member == "sun":
            ws = input_speed
        elif input_member == "ring":
            wr = input_speed
        elif input_member == "carrier":
            wc = input_speed

        # assign fixed member
        if fixed_member == "sun":
            ws = 0
        elif fixed_member == "ring":
            wr = 0
        elif fixed_member == "carrier":
            wc = 0

        # solve missing variable using planetary equation

        if wc is None:

            wc = (self.Ns * ws + self.Nr * wr) / (self.Ns + self.Nr)

        elif ws is None:

            ws = ((self.Ns + self.Nr) * wc - self.Nr * wr) / self.Ns

        elif wr is None:

            wr = ((self.Ns + self.Nr) * wc - self.Ns * ws) / self.Nr

        speeds = {
            "sun": ws,
            "ring": wr,
            "carrier": wc
        }

        return speeds

    # --------------------------------------------------------
    # Gear ratio
    # --------------------------------------------------------

    def ratio(
        self,
        input_member: str,
        output_member: str,
        fixed_member: str
    ) -> float:

        speeds = self.solve(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member,
            input_speed=1.0
        )

        win = speeds[input_member]
        wout = speeds[output_member]

        if wout == 0:
            raise ZeroDivisionError("Output speed is zero")

        return win / wout

    # --------------------------------------------------------
    # Mode classification
    # --------------------------------------------------------

    def describe_mode(
        self,
        input_member: str,
        output_member: str,
        fixed_member: str
    ) -> str:

        r = self.ratio(input_member, output_member, fixed_member)

        if r < 0:
            return "reverse"

        if r > 1:
            return "reduction"

        if r < 1:
            return "overdrive"

        return "direct"

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    def summary(
        self,
        input_member: str,
        output_member: str,
        fixed_member: str
    ):

        speeds = self.solve(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member,
            input_speed=1.0
        )

        ratio = self.ratio(input_member, output_member, fixed_member)
        mode = self.describe_mode(input_member, output_member, fixed_member)

        print("\nPlanetary Gearset")
        print("------------------------")

        print(f"Name: {self.name}")
        print(f"Sun teeth: {self.Ns}")
        print(f"Ring teeth: {self.Nr}")
        print(f"Planet teeth: {self.Np}")

        print("\nConfiguration")
        print("------------------------")

        print(f"Input:  {input_member}")
        print(f"Output: {output_member}")
        print(f"Fixed:  {fixed_member}")

        print("\nSpeeds (normalized)")
        print("------------------------")

        print(f"Sun speed:     {speeds['sun']:.5f}")
        print(f"Ring speed:    {speeds['ring']:.5f}")
        print(f"Carrier speed: {speeds['carrier']:.5f}")

        print("\nResults")
        print("------------------------")

        print(f"Gear ratio: {ratio:.3f}")
        print(f"Mode: {mode}")

    # --------------------------------------------------------
    # repr
    # --------------------------------------------------------

    def __repr__(self):

        return (
            f"PlanetaryGearSet("
            f"Ns={self.Ns}, "
            f"Nr={self.Nr}, "
            f"Np={self.Np})"
        )