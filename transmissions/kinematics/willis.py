
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.kinematics.willis

Reusable Willis-equation helpers for simple planetary gearsets.

Purpose
-------
This module centralizes the kinematic relations that were previously scattered
across transmission-specific scripts and solver code.

For a simple planetary gearset with:
    sun speed     = ws
    ring speed    = wr
    carrier speed = wc
    sun teeth     = Ns
    ring teeth    = Nr

the linear Willis relation is:

    Ns * (ws - wc) + Nr * (wr - wc) = 0

Equivalent fractional form:

    (ws - wc) / (wr - wc) = -Nr / Ns

This module provides:
- symbolic equation builders
- direct closed-form solutions for any one unknown speed
- common ratio formulas for standard modes
- lightweight validation helpers

This is kinematics only. No torque, strength, AGMA, or geometry enforcement
is performed here beyond basic sanity checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Optional

import sympy as sp


class WillisError(ValueError):
    """User-facing Willis / planetary kinematics error."""


def validate_tooth_counts(Ns: int, Nr: int) -> None:
    """Basic kinematic sanity checks."""
    if int(Ns) <= 0 or int(Nr) <= 0:
        raise WillisError(f"Ns and Nr must be positive integers. Got Ns={Ns}, Nr={Nr}.")
    if int(Nr) <= int(Ns):
        raise WillisError(
            f"For the simple planetary convention used here, Nr must be greater than Ns. "
            f"Got Ns={Ns}, Nr={Nr}."
        )


def linear_willis_expr(
    Ns: int,
    Nr: int,
    ws: sp.Expr,
    wr: sp.Expr,
    wc: sp.Expr,
) -> sp.Expr:
    """
    Return the linear Willis expression:

        Ns*(ws - wc) + Nr*(wr - wc)

    A valid kinematic state satisfies:
        linear_willis_expr(...) = 0
    """
    validate_tooth_counts(Ns, Nr)
    return int(Ns) * (ws - wc) + int(Nr) * (wr - wc)


def fractional_willis_expr(
    Ns: int,
    Nr: int,
    ws: sp.Expr,
    wr: sp.Expr,
    wc: sp.Expr,
) -> sp.Expr:
    """
    Return the fractional Willis expression:

        (ws - wc)/(wr - wc) + Nr/Ns

    Notes
    -----
    The linear form is preferred in solvers because it avoids division by zero
    at direct-drive / degenerate states.
    """
    validate_tooth_counts(Ns, Nr)
    return (ws - wc) / (wr - wc) + sp.Rational(int(Nr), int(Ns))


def willis_equation(
    Ns: int,
    Nr: int,
    *,
    symbol_names: tuple[str, str, str] = ("ws", "wr", "wc"),
    form: Literal["linear", "fractional"] = "linear",
) -> sp.Eq:
    """
    Build a symbolic Willis equation using new SymPy symbols.
    """
    ws, wr, wc = sp.symbols(" ".join(symbol_names), real=True)
    if form == "linear":
        return sp.Eq(linear_willis_expr(Ns, Nr, ws, wr, wc), 0)
    if form == "fractional":
        return sp.Eq(fractional_willis_expr(Ns, Nr, ws, wr, wc), 0)
    raise WillisError(f"Unknown Willis equation form: {form}")


def solve_for_carrier(Ns: int, Nr: int, *, ws: float, wr: float) -> float:
    """
    Closed-form solution for carrier speed:

        wc = (Ns*ws + Nr*wr) / (Ns + Nr)
    """
    validate_tooth_counts(Ns, Nr)
    return (int(Ns) * float(ws) + int(Nr) * float(wr)) / (int(Ns) + int(Nr))


def solve_for_sun(Ns: int, Nr: int, *, wr: float, wc: float) -> float:
    """
    Closed-form solution for sun speed:

        ws = ((Ns + Nr)*wc - Nr*wr) / Ns
    """
    validate_tooth_counts(Ns, Nr)
    return (((int(Ns) + int(Nr)) * float(wc)) - int(Nr) * float(wr)) / int(Ns)


def solve_for_ring(Ns: int, Nr: int, *, ws: float, wc: float) -> float:
    """
    Closed-form solution for ring speed:

        wr = ((Ns + Nr)*wc - Ns*ws) / Nr
    """
    validate_tooth_counts(Ns, Nr)
    return (((int(Ns) + int(Nr)) * float(wc)) - int(Ns) * float(ws)) / int(Nr)


def solve_unknown(
    Ns: int,
    Nr: int,
    *,
    ws: Optional[float] = None,
    wr: Optional[float] = None,
    wc: Optional[float] = None,
) -> Dict[str, float]:
    """
    Solve the simple planetary kinematics when exactly one of ws, wr, wc is unknown.
    """
    provided = {"ws": ws, "wr": wr, "wc": wc}
    unknown = [name for name, value in provided.items() if value is None]
    if len(unknown) != 1:
        raise WillisError(
            "solve_unknown requires exactly one unknown among ws, wr, wc. "
            f"Got unknowns={unknown}."
        )

    if ws is None:
        ws = solve_for_sun(Ns, Nr, wr=float(wr), wc=float(wc))
    elif wr is None:
        wr = solve_for_ring(Ns, Nr, ws=float(ws), wc=float(wc))
    elif wc is None:
        wc = solve_for_carrier(Ns, Nr, ws=float(ws), wr=float(wr))

    return {"ws": float(ws), "wr": float(wr), "wc": float(wc)}


def ratio_sun_to_carrier_with_ring_fixed(Ns: int, Nr: int) -> float:
    """
    Standard reduction:
        input = sun
        output = carrier
        ring fixed

    Ratio = input/output = 1 + Nr/Ns
    """
    validate_tooth_counts(Ns, Nr)
    return 1.0 + int(Nr) / int(Ns)


def ratio_ring_to_carrier_with_sun_fixed(Ns: int, Nr: int) -> float:
    """
    Standard reduction:
        input = ring
        output = carrier
        sun fixed

    Ratio = input/output = 1 + Ns/Nr
    """
    validate_tooth_counts(Ns, Nr)
    return 1.0 + int(Ns) / int(Nr)


def ratio_sun_to_ring_with_carrier_fixed(Ns: int, Nr: int) -> float:
    """
    Standard reverse:
        input = sun
        output = ring
        carrier fixed

    Ratio = input/output = -Nr/Ns
    """
    validate_tooth_counts(Ns, Nr)
    return -int(Nr) / int(Ns)


def ratio_ring_to_sun_with_carrier_fixed(Ns: int, Nr: int) -> float:
    """
    Reverse in the opposite direction:
        input = ring
        output = sun
        carrier fixed

    Ratio = input/output = -Ns/Nr
    """
    validate_tooth_counts(Ns, Nr)
    return -int(Ns) / int(Nr)


@dataclass(frozen=True)
class PlanetaryModeSummary:
    """
    Human-readable summary of a common simple-planetary operating mode.
    """
    mode: str
    input_member: str
    output_member: str
    fixed_member: str
    ratio: float
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "input_member": self.input_member,
            "output_member": self.output_member,
            "fixed_member": self.fixed_member,
            "ratio": self.ratio,
            "notes": self.notes,
        }


def common_mode_summaries(Ns: int, Nr: int) -> Dict[str, PlanetaryModeSummary]:
    """
    Return the standard simple-planetary mode summaries.
    """
    validate_tooth_counts(Ns, Nr)
    return {
        "sun_to_carrier_ring_fixed": PlanetaryModeSummary(
            mode="sun_to_carrier_ring_fixed",
            input_member="sun",
            output_member="carrier",
            fixed_member="ring",
            ratio=ratio_sun_to_carrier_with_ring_fixed(Ns, Nr),
            notes="Classic reduction mode.",
        ),
        "ring_to_carrier_sun_fixed": PlanetaryModeSummary(
            mode="ring_to_carrier_sun_fixed",
            input_member="ring",
            output_member="carrier",
            fixed_member="sun",
            ratio=ratio_ring_to_carrier_with_sun_fixed(Ns, Nr),
            notes="Alternative reduction mode.",
        ),
        "sun_to_ring_carrier_fixed": PlanetaryModeSummary(
            mode="sun_to_ring_carrier_fixed",
            input_member="sun",
            output_member="ring",
            fixed_member="carrier",
            ratio=ratio_sun_to_ring_with_carrier_fixed(Ns, Nr),
            notes="Reverse direction mode.",
        ),
        "ring_to_sun_carrier_fixed": PlanetaryModeSummary(
            mode="ring_to_sun_carrier_fixed",
            input_member="ring",
            output_member="sun",
            fixed_member="carrier",
            ratio=ratio_ring_to_sun_with_carrier_fixed(Ns, Nr),
            notes="Reverse direction mode (opposite input/output).",
        ),
    }


def dependency_audit() -> Dict[str, str]:
    """
    Lightweight description of what the Willis relation depends on.
    """
    return {
        "linear_relation": "Ns, Nr, ws, wr, wc",
        "carrier_solution": "Ns, Nr, ws, wr",
        "sun_solution": "Ns, Nr, wr, wc",
        "ring_solution": "Ns, Nr, ws, wc",
        "sun_to_carrier_ring_fixed_ratio": "Ns, Nr",
        "ring_to_carrier_sun_fixed_ratio": "Ns, Nr",
        "sun_to_ring_carrier_fixed_ratio": "Ns, Nr",
        "ring_to_sun_carrier_fixed_ratio": "Ns, Nr",
    }
