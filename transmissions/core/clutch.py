#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.core.clutch

Core shift-element abstractions for transmission kinematics.

This Core V2 upgrade keeps the original project concepts:
- RotatingMember
- Ground / GROUND
- Constraint
- Clutch
- Brake

and adds:
- OneWayClutch / Sprag
- richer summaries / diagnostics
- explicit naming and validation
- backward-friendly behavior for all existing transmission scripts

Design note
-----------
These classes are intentionally kinematic. They express idealized speed
constraints such as:

    clutch engaged   ->  w_a = w_b
    brake engaged    ->  w_member = 0

The new OneWayClutch class provides a core abstraction for a sprag / overrunning
clutch, but it does not by itself solve torque-direction logic. In current Core
V2 it mainly serves as:
- a first-class topology object
- a brake-like kinematic hold when engaged in a specified direction
- metadata for future richer state logic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any


class ClutchError(ValueError):
    """User-facing clutch / constraint modeling error."""


@dataclass(frozen=True)
class Ground:
    """Ground / housing sentinel used in brake constraints."""

    name: str = "ground"

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.name

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        return "GROUND"


GROUND = Ground()


@dataclass
class RotatingMember:
    """
    Kinematic rotating member.

    Examples
    --------
    - sun gear
    - ring gear
    - carrier
    - output shaft
    - intermediate node
    """

    name: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ClutchError("RotatingMember name must be a non-empty string.")

    def summary_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "notes": self.notes,
        }

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.name

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        return f"RotatingMember({self.name})"


class Constraint:
    """
    Base class for shift elements / kinematic constraints.

    State
    -----
    - engaged = True  -> constraint active
    - engaged = False -> constraint inactive
    """

    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name
        self.engaged: bool = False

    def engage(self) -> None:
        self.engaged = True

    def release(self) -> None:
        self.engaged = False

    def set_engaged(self, value: bool) -> None:
        self.engaged = bool(value)

    def is_engaged(self) -> bool:
        return bool(self.engaged)

    def constraint(self):
        raise NotImplementedError

    def summary_dict(self) -> Dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "name": self.name,
            "engaged": bool(self.engaged),
        }


class Clutch(Constraint):
    """
    Locks two rotating members together when engaged.

    Kinematic meaning:
        w_a = w_b
    """

    def __init__(
        self,
        member_a: RotatingMember,
        member_b: RotatingMember,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name)

        if not isinstance(member_a, RotatingMember) or not isinstance(member_b, RotatingMember):
            raise ClutchError("Clutch requires two RotatingMember objects.")
        if member_a.name == member_b.name:
            raise ClutchError("Clutch member_a and member_b must be different members.")

        self.member_a = member_a
        self.member_b = member_b

        if self.name is None:
            self.name = f"{member_a.name}_{member_b.name}_clutch"

    def constraint(self) -> Optional[Tuple[RotatingMember, RotatingMember]]:
        """
        Return the active equality constraint, if engaged.

        Returns
        -------
        tuple(member_a, member_b) or None
        """
        if not self.engaged:
            return None
        return (self.member_a, self.member_b)

    def summary_dict(self) -> Dict[str, Any]:
        d = super().summary_dict()
        d.update(
            {
                "member_a": self.member_a.name,
                "member_b": self.member_b.name,
                "relation": "equal_speed",
            }
        )
        return d

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        state = "ENGAGED" if self.engaged else "OPEN"
        return f"Clutch({self.member_a} ↔ {self.member_b}, state={state})"


class Brake(Constraint):
    """
    Locks a rotating member to ground when engaged.

    Kinematic meaning:
        w_member = 0
    """

    def __init__(self, member: RotatingMember, name: Optional[str] = None) -> None:
        super().__init__(name)

        if not isinstance(member, RotatingMember):
            raise ClutchError("Brake requires a RotatingMember object.")

        self.member = member

        if self.name is None:
            self.name = f"{member.name}_brake"

    def constraint(self) -> Optional[Tuple[RotatingMember, Ground]]:
        if not self.engaged:
            return None
        return (self.member, GROUND)

    def summary_dict(self) -> Dict[str, Any]:
        d = super().summary_dict()
        d.update(
            {
                "member": self.member.name,
                "relation": "grounded",
            }
        )
        return d

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        state = "ENGAGED" if self.engaged else "OPEN"
        return f"Brake({self.member} → ground, state={state})"


class OneWayClutch(Constraint):
    """
    One-way clutch / overrunning clutch / sprag abstraction.

    Current Core V2 behavior
    ------------------------
    In current kinematic usage, when engaged this behaves like a directional
    hold of one member relative to ground:

        w_member = 0

    but it also records the intended hold direction so higher-level logic can
    distinguish between:
    - a regular brake
    - a sprag / one-way clutch

    Parameters
    ----------
    member:
        Member being held when the one-way element is active in its holding mode.
    hold_direction:
        Metadata describing the holding direction. Examples:
        - "negative"
        - "counter_clockwise"
        - "ccw"
        - "reverse"

        The solver does not yet infer engagement from torque direction. This is
        reserved for future richer state logic.
    locked_when_engaged:
        If True (default), `.constraint()` returns a brake-like ground relation
        when engaged. If False, the object becomes pure metadata unless a future
        solver interprets it.
    """

    _VALID_DIRECTIONS = {
        "negative",
        "positive",
        "ccw",
        "cw",
        "counter_clockwise",
        "clockwise",
        "reverse",
        "forward",
        "either",
        "unknown",
    }

    def __init__(
        self,
        member: RotatingMember,
        *,
        hold_direction: str = "unknown",
        locked_when_engaged: bool = True,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name)

        if not isinstance(member, RotatingMember):
            raise ClutchError("OneWayClutch requires a RotatingMember object.")

        hd = str(hold_direction).strip().lower() or "unknown"
        if hd not in self._VALID_DIRECTIONS:
            valid = ", ".join(sorted(self._VALID_DIRECTIONS))
            raise ClutchError(f"Invalid hold_direction '{hold_direction}'. Valid values: {valid}")

        self.member = member
        self.hold_direction = hd
        self.locked_when_engaged = bool(locked_when_engaged)

        if self.name is None:
            self.name = f"{member.name}_one_way_clutch"

    def constraint(self) -> Optional[Tuple[RotatingMember, Ground]]:
        """
        Return the active hold constraint, if engaged and configured to lock.

        Returns
        -------
        tuple(member, GROUND) or None
        """
        if not self.engaged or not self.locked_when_engaged:
            return None
        return (self.member, GROUND)

    def holds_direction(self, direction: str) -> bool:
        """Return True if the stored hold direction matches the queried one."""
        d = str(direction).strip().lower()
        if self.hold_direction in {"either", "unknown"}:
            return self.hold_direction == "either"
        aliases = {
            "counter_clockwise": {"counter_clockwise", "ccw", "negative", "reverse"},
            "ccw": {"counter_clockwise", "ccw", "negative", "reverse"},
            "negative": {"counter_clockwise", "ccw", "negative", "reverse"},
            "reverse": {"counter_clockwise", "ccw", "negative", "reverse"},
            "clockwise": {"clockwise", "cw", "positive", "forward"},
            "cw": {"clockwise", "cw", "positive", "forward"},
            "positive": {"clockwise", "cw", "positive", "forward"},
            "forward": {"clockwise", "cw", "positive", "forward"},
        }
        if self.hold_direction not in aliases:
            return d == self.hold_direction
        return d in aliases[self.hold_direction]

    def summary_dict(self) -> Dict[str, Any]:
        d = super().summary_dict()
        d.update(
            {
                "member": self.member.name,
                "relation": "one_way_hold",
                "hold_direction": self.hold_direction,
                "locked_when_engaged": self.locked_when_engaged,
            }
        )
        return d

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        state = "ENGAGED" if self.engaged else "OPEN"
        lock_txt = "locks" if self.locked_when_engaged else "metadata-only"
        return (
            f"OneWayClutch({self.member} → ground, hold_direction={self.hold_direction}, "
            f"mode={lock_txt}, state={state})"
        )


class Sprag(OneWayClutch):
    """
    Thin alias/subclass for a transmission sprag.

    Defaults to a counter-clockwise / negative-direction hold convention, but the
    caller can override it explicitly.
    """

    def __init__(
        self,
        member: RotatingMember,
        *,
        hold_direction: str = "counter_clockwise",
        locked_when_engaged: bool = True,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(
            member,
            hold_direction=hold_direction,
            locked_when_engaged=locked_when_engaged,
            name=name or f"{member.name}_sprag",
        )
