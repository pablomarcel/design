#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.core.shaft

Core shaft / rotating-node abstractions for transmission kinematics.

Why this file exists
--------------------
The first version of the transmissions app modeled rotating members directly
(`sun`, `ring`, `carrier`, etc.) but did not provide a clean abstraction for
the *shaft node* that ties several physical members together.

Real automatic transmissions often have situations like:

- front carrier = output shaft = rear ring
- front sun = rear sun (common sun)
- node23 = PG2 carrier = PG3 ring
- input shaft connected to several members through clutches_brakes_flywheels

Those are not “new gears”; they are *the same rotating node* seen by multiple
components.  This module provides a simple, explicit representation for that.

Design goals
------------
- lightweight and solver-friendly
- no heavy geometry assumptions
- compatible with the existing `RotatingMember` concept used elsewhere
- useful for topology definition, reporting, and equation assembly
- able to emit symbolic equality constraints for permanent member ties

Key classes
-----------
- `ShaftNode`
    A rotating node / shaft station with one angular speed shared by all
    attached members.

- `MemberAttachment`
    Metadata linking a named physical member (e.g. `PG1.carrier`) to a node.

Typical use
-----------
    output = ShaftNode("output")
    output.attach("PG1.carrier")
    output.attach("PG2.ring")
    output.attach("output_shaft")

    sun_common = ShaftNode("sun_common")
    sun_common.attach("PG1.sun")
    sun_common.attach("PG2.sun")

Then a higher-level solver can assert that all attachments to the same node
share one rotational speed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

import sympy as sp


class ShaftError(ValueError):
    """User-facing shaft / node modeling error."""


@dataclass(frozen=True)
class MemberAttachment:
    """
    A physical member attached to a shaft node.

    Parameters
    ----------
    member_name:
        Human-readable identifier such as `PG1.carrier`, `rear_ring`, etc.
    role:
        Optional role descriptor such as `output`, `sun`, `carrier`, `ring`.
    notes:
        Optional free-form notes.
    """

    member_name: str
    role: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not str(self.member_name).strip():
            raise ShaftError("Attachment member_name must be a non-empty string.")


@dataclass
class ShaftNode:
    """
    A rotating shaft/node to which one or more physical members are permanently attached.

    Conceptually, every attached member rotates at the same angular speed.

    Parameters
    ----------
    name:
        Node name, e.g. `input`, `output`, `sun_common`, `node12`.
    is_ground:
        If True, this node is permanently grounded (speed = 0).
    speed_symbol_name:
        Optional explicit symbolic variable name. If omitted, a name is derived
        from `name`.
    notes:
        Optional descriptive notes.

    Notes
    -----
    This class is intentionally *kinematic*, not geometric. It does not care
    about tooth counts or physical packaging.
    """

    name: str
    is_ground: bool = False
    speed_symbol_name: Optional[str] = None
    notes: str = ""
    _attachments: List[MemberAttachment] = field(default_factory=list, init=False, repr=False)
    _speed_symbol: Optional[sp.Symbol] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ShaftError("ShaftNode name must be a non-empty string.")

    # ------------------------------------------------------------------
    # Attachment management
    # ------------------------------------------------------------------
    def attach(self, member_name: str, *, role: str = "", notes: str = "") -> MemberAttachment:
        """
        Attach a physical member name to this node.

        Raises
        ------
        ShaftError
            If the member is already attached to this node.
        """
        attachment = MemberAttachment(member_name=member_name, role=role, notes=notes)
        if any(a.member_name == attachment.member_name for a in self._attachments):
            raise ShaftError(
                f"Member '{attachment.member_name}' is already attached to node '{self.name}'."
            )
        self._attachments.append(attachment)
        return attachment

    def detach(self, member_name: str) -> None:
        """Detach a member by name."""
        before = len(self._attachments)
        self._attachments = [a for a in self._attachments if a.member_name != member_name]
        if len(self._attachments) == before:
            raise ShaftError(f"Member '{member_name}' is not attached to node '{self.name}'.")

    def clear_attachments(self) -> None:
        """Remove all attachments from this node."""
        self._attachments.clear()

    @property
    def attachments(self) -> tuple[MemberAttachment, ...]:
        """Immutable view of attachments."""
        return tuple(self._attachments)

    @property
    def attachment_names(self) -> tuple[str, ...]:
        """Names of all attached members."""
        return tuple(a.member_name for a in self._attachments)

    def has_attachment(self, member_name: str) -> bool:
        """Return True if `member_name` is attached to this node."""
        return any(a.member_name == member_name for a in self._attachments)

    # ------------------------------------------------------------------
    # Symbolic speed
    # ------------------------------------------------------------------
    @property
    def speed_symbol(self) -> sp.Symbol:
        """
        SymPy symbol representing the angular speed of this node.

        Ground nodes still get a symbol for consistency, but higher-level
        equation builders will typically constrain it to zero.
        """
        if self._speed_symbol is None:
            sym_name = self.speed_symbol_name or f"w_{self.name}"
            self._speed_symbol = sp.Symbol(sym_name, real=True)
        return self._speed_symbol

    # ------------------------------------------------------------------
    # Constraint helpers
    # ------------------------------------------------------------------
    def ground_equation(self) -> sp.Expr:
        """
        Return the grounding equation for this node.

        Returns
        -------
        sympy.Expr
            `w_node` if grounded; otherwise raises.
        """
        if not self.is_ground:
            raise ShaftError(f"Node '{self.name}' is not marked as ground.")
        return self.speed_symbol

    def equality_equation(self, other: "ShaftNode") -> sp.Expr:
        """
        Return a symbolic equality equation enforcing equal speed between nodes.

        Useful when two nodes are permanently tied.
        """
        if not isinstance(other, ShaftNode):
            raise ShaftError("equality_equation expects another ShaftNode.")
        return self.speed_symbol - other.speed_symbol

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------
    def summary_dict(self) -> dict:
        """Structured summary for logging / JSON."""
        return {
            "name": self.name,
            "is_ground": self.is_ground,
            "speed_symbol": str(self.speed_symbol),
            "attachments": [
                {
                    "member_name": a.member_name,
                    "role": a.role,
                    "notes": a.notes,
                }
                for a in self._attachments
            ],
            "notes": self.notes,
        }

    def summary_text(self) -> str:
        """Human-readable one-node summary."""
        atts = ", ".join(self.attachment_names) if self._attachments else "(none)"
        ground_txt = "ground" if self.is_ground else "free"
        return (
            f"ShaftNode(name={self.name}, state={ground_txt}, "
            f"speed_symbol={self.speed_symbol}, attachments=[{atts}])"
        )

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.summary_text()


def build_node(name: str, *members: str, is_ground: bool = False, notes: str = "") -> ShaftNode:
    """
    Convenience factory for a node with multiple attachments.

    Example
    -------
        output = build_node("output", "PG1.carrier", "PG2.ring", "output_shaft")
    """
    node = ShaftNode(name=name, is_ground=is_ground, notes=notes)
    for member in members:
        node.attach(member)
    return node


def permanent_tie_equations(nodes: Sequence[ShaftNode]) -> List[sp.Expr]:
    """
    Build equality equations tying all listed nodes to the first node.

    Example
    -------
        permanent_tie_equations([node_a, node_b, node_c])
        -> [w_a - w_b, w_a - w_c]

    Notes
    -----
    In many cases you will not need this if several physical members are
    modeled directly as a single `ShaftNode`. This helper is for situations
    where separate nodes were created first and later discovered to be tied.
    """
    if len(nodes) < 2:
        return []
    first = nodes[0]
    return [first.equality_equation(node) for node in nodes[1:]]


def summarize_nodes(nodes: Iterable[ShaftNode]) -> List[dict]:
    """Return structured summaries for a collection of nodes."""
    return [node.summary_dict() for node in nodes]
