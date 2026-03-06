#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.core.clutch

Clutch and brake models for transmission kinematics.

A clutch locks two rotating members together.

A brake locks a rotating member to ground.

These components impose speed constraints used by
the transmission solver.

Author: Pablo Montijo Design Project
"""

from dataclasses import dataclass
from typing import Optional, Tuple


# ------------------------------------------------------------
# Ground reference
# ------------------------------------------------------------

class Ground:
    """
    Represents the transmission housing / ground reference.
    """

    name = "ground"
    speed = 0.0

    def __repr__(self):
        return "ground"


GROUND = Ground()


# ------------------------------------------------------------
# Rotating member
# ------------------------------------------------------------

class RotatingMember:
    """
    Represents a rotating mechanical component.
    """

    def __init__(self, name: str):

        self.name = name
        self.speed: Optional[float] = None

    def __repr__(self):

        return f"{self.name}"


# ------------------------------------------------------------
# Base constraint class
# ------------------------------------------------------------

class Constraint:
    """
    Base class for transmission constraints.
    """

    def __init__(self, name: Optional[str] = None):

        self.name = name
        self.engaged = False

    # --------------------------------------------------------

    def engage(self):

        self.engaged = True

    # --------------------------------------------------------

    def release(self):

        self.engaged = False

    # --------------------------------------------------------

    def is_active(self) -> bool:

        return self.engaged

    # --------------------------------------------------------

    def constraint(self):

        """
        Must be implemented by subclasses.
        """
        raise NotImplementedError


# ------------------------------------------------------------
# Clutch
# ------------------------------------------------------------

class Clutch(Constraint):
    """
    Locks two rotating members together.

    Example:
        sun ↔ carrier
    """

    def __init__(
        self,
        member_a: RotatingMember,
        member_b: RotatingMember,
        name: Optional[str] = None
    ):

        super().__init__(name)

        self.member_a = member_a
        self.member_b = member_b

        if self.name is None:
            self.name = f"{member_a}_{member_b}_clutch"

    # --------------------------------------------------------

    def constraint(self) -> Optional[Tuple[RotatingMember, RotatingMember]]:

        """
        Returns the speed constraint if engaged.

        Meaning:
            ωA = ωB
        """

        if not self.engaged:
            return None

        return (self.member_a, self.member_b)

    # --------------------------------------------------------

    def __repr__(self):

        state = "ENGAGED" if self.engaged else "OPEN"

        return (
            f"Clutch("
            f"{self.member_a} ↔ {self.member_b}, "
            f"state={state})"
        )


# ------------------------------------------------------------
# Brake
# ------------------------------------------------------------

class Brake(Constraint):
    """
    Locks a rotating member to ground.

    Example:
        ring → housing
    """

    def __init__(
        self,
        member: RotatingMember,
        name: Optional[str] = None
    ):

        super().__init__(name)

        self.member = member

        if self.name is None:
            self.name = f"{member}_brake"

    # --------------------------------------------------------

    def constraint(self) -> Optional[Tuple[RotatingMember, Ground]]:

        """
        Returns constraint if brake engaged.

        Meaning:
            ω_member = 0
        """

        if not self.engaged:
            return None

        return (self.member, GROUND)

    # --------------------------------------------------------

    def __repr__(self):

        state = "ENGAGED" if self.engaged else "OPEN"

        return f"Brake({self.member} → ground, state={state})"