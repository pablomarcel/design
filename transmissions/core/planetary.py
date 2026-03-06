#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.core.planetary

Planetary gearset kinematic model.

Implements the canonical simple planetary relation:

    Ns (ωs − ωc) + Nr (ωr − ωc) = 0

Equivalent to:

    (ωs − ωc) / (ωr − ωc) = -Nr / Ns

This module is built to work with the existing TransmissionSolver and
SimpsonTransmission architecture in this project.

Key compatibility requirement:
- self.sun, self.ring, self.carrier must be RotatingMember objects because
  solver.py accesses `.name` on those attributes directly.

Author: Pablo Montijo Design Project
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

try:
    from .clutch import RotatingMember
except Exception:  # pragma: no cover
    from clutch import RotatingMember  # type: ignore


# ------------------------------------------------------------
# Gear metadata
# ------------------------------------------------------------

@dataclass(frozen=True)
class GearGeometry:
    """
    Metadata for a toothed member.
    """

    label: str
    teeth: int

    def __repr__(self) -> str:
        return f"{self.label}(N={self.teeth})"


# ------------------------------------------------------------
# Planetary gearset
# ------------------------------------------------------------

class PlanetaryGearSet:
    """
    Represents a simple planetary gearset.

    Parameters
    ----------
    Ns : int
        Sun tooth count.
    Nr : int
        Ring tooth count.
    name : str
        Name of gearset.
    sun, ring, carrier : RotatingMember | None
        Optional injected rotating members for compound architectures.
        If omitted, local members are created.

    Notes
    -----
    For a simple planetary with a common planet meshing sun and ring,
    the implied planet tooth count is:

        Np = (Nr - Ns) / 2

    This must be a positive integer for physically valid geometry.
    """

    def __init__(
        self,
        Ns: int,
        Nr: int,
        name: str = "PGS",
        sun: Optional[RotatingMember] = None,
        ring: Optional[RotatingMember] = None,
        carrier: Optional[RotatingMember] = None,
    ) -> None:

        if Ns <= 0 or Nr <= 0:
            raise ValueError("Gear tooth counts must be positive")

        if Nr <= Ns:
            raise ValueError("Ring tooth count must be greater than sun tooth count")

        if (Nr - Ns) % 2 != 0:
            raise ValueError(
                "Invalid simple planetary geometry: (Nr - Ns) must be even so planet tooth count is integer"
            )

        self.name = name
        self.Ns = int(Ns)
        self.Nr = int(Nr)
        self.Np = (self.Nr - self.Ns) // 2

        if self.Np <= 0:
            raise ValueError("Invalid planetary geometry: computed planet tooth count must be positive")

        # Rotating members exposed directly for solver compatibility.
        self.sun = sun if sun is not None else RotatingMember(f"{name}_sun")
        self.ring = ring if ring is not None else RotatingMember(f"{name}_ring")
        self.carrier = carrier if carrier is not None else RotatingMember(f"{name}_carrier")

        # Optional geometry metadata.
        self.sun_geometry = GearGeometry("sun", self.Ns)
        self.ring_geometry = GearGeometry("ring", self.Nr)
        self.carrier_geometry = GearGeometry("carrier", 0)

    # --------------------------------------------------------
    # Core kinematic relation
    # --------------------------------------------------------

    def planetary_equation(self, ws: float, wr: float, wc: float) -> float:
        """
        Residual of the Willis/simple planetary constraint.
        """

        return self.Ns * (ws - wc) + self.Nr * (wr - wc)

    def willis_ratio(self, ws: float, wr: float, wc: float) -> float:
        """
        Returns the Willis ratio (ws - wc)/(wr - wc).
        """

        denom = wr - wc
        if denom == 0:
            raise ZeroDivisionError("Willis ratio undefined because wr == wc")
        return (ws - wc) / denom

    # --------------------------------------------------------
    # Standalone solve helpers
    # --------------------------------------------------------

    def solve(
        self,
        input_member: str,
        output_member: str,
        fixed_member: str,
        input_speed: float = 1.0,
    ) -> Dict[str, float]:
        """
        Solve the simple planetary for one input, one output, and one fixed member.

        Member names must be one of: 'sun', 'ring', 'carrier'.
        """

        members = {"sun", "ring", "carrier"}

        if input_member not in members:
            raise ValueError("invalid input member")
        if output_member not in members:
            raise ValueError("invalid output member")
        if fixed_member not in members:
            raise ValueError("invalid fixed member")
        if len({input_member, output_member, fixed_member}) != 3:
            raise ValueError("input_member, output_member, and fixed_member must all be different")

        ws: Optional[float] = None
        wr: Optional[float] = None
        wc: Optional[float] = None

        if input_member == "sun":
            ws = float(input_speed)
        elif input_member == "ring":
            wr = float(input_speed)
        else:
            wc = float(input_speed)

        if fixed_member == "sun":
            ws = 0.0
        elif fixed_member == "ring":
            wr = 0.0
        else:
            wc = 0.0

        if wc is None:
            assert ws is not None and wr is not None
            wc = (self.Ns * ws + self.Nr * wr) / (self.Ns + self.Nr)
        elif ws is None:
            assert wr is not None
            ws = ((self.Ns + self.Nr) * wc - self.Nr * wr) / self.Ns
        elif wr is None:
            wr = ((self.Ns + self.Nr) * wc - self.Ns * ws) / self.Nr

        return {
            "sun": float(ws),
            "ring": float(wr),
            "carrier": float(wc),
        }

    def ratio(
        self,
        input_member: str,
        output_member: str,
        fixed_member: str,
        input_speed: float = 1.0,
    ) -> float:
        """
        Returns ω_in / ω_out.
        """

        speeds = self.solve(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member,
            input_speed=input_speed,
        )

        win = speeds[input_member]
        wout = speeds[output_member]

        if wout == 0:
            raise ZeroDivisionError("Output speed is zero")

        return win / wout

    def describe_mode(
        self,
        input_member: str,
        output_member: str,
        fixed_member: str,
        input_speed: float = 1.0,
    ) -> str:
        """
        Qualitative classification of the ratio.
        """

        r = self.ratio(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member,
            input_speed=input_speed,
        )

        if r < 0:
            return "reverse"
        if r > 1:
            return "reduction"
        if 0 < r < 1:
            return "overdrive"
        return "direct"

    def summary(
        self,
        input_member: str,
        output_member: str,
        fixed_member: str,
        input_speed: float = 1.0,
    ) -> None:
        """
        Print a standalone summary.
        """

        speeds = self.solve(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member,
            input_speed=input_speed,
        )
        ratio = self.ratio(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member,
            input_speed=input_speed,
        )
        mode = self.describe_mode(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member,
            input_speed=input_speed,
        )

        print("\nPlanetary Gearset")
        print("------------------------")
        print(f"Name: {self.name}")
        print(f"Sun teeth: {self.Ns}")
        print(f"Ring teeth: {self.Nr}")
        print(f"Planet teeth: {self.Np}")
        print()
        print("Members")
        print("------------------------")
        print(f"Sun:     {self.sun.name}")
        print(f"Ring:    {self.ring.name}")
        print(f"Carrier: {self.carrier.name}")
        print()
        print("Configuration")
        print("------------------------")
        print(f"Input:  {input_member}")
        print(f"Output: {output_member}")
        print(f"Fixed:  {fixed_member}")
        print()
        print("Speeds")
        print("------------------------")
        print(f"Sun speed:     {speeds['sun']:.6f}")
        print(f"Ring speed:    {speeds['ring']:.6f}")
        print(f"Carrier speed: {speeds['carrier']:.6f}")
        print()
        print("Results")
        print("------------------------")
        print(f"Gear ratio: {ratio:.6f}")
        print(f"Mode: {mode}")

    def __repr__(self) -> str:
        return (
            "PlanetaryGearSet("
            f"name={self.name!r}, "
            f"Ns={self.Ns}, "
            f"Nr={self.Nr}, "
            f"Np={self.Np}, "
            f"sun={self.sun.name!r}, "
            f"ring={self.ring.name!r}, "
            f"carrier={self.carrier.name!r}"
            ")"
        )
