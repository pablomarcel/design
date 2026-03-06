#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.simpson_solver

Simpson transmission kinematic helper.

This upgrade fixes two practical problems from the project version:

1. Import behavior
   - works when invoked as part of the package, e.g.
       python -m kinematics.simpson_ratio_map
       python -m transmissions.kinematics.simpson_ratio_map
   - also works as a flat standalone script if files are side-by-side.

2. Visibility / speed
   - adds logging hooks
   - avoids repeated SymPy solves in the ratio sweep by using closed-form
     relations for the specific Simpson architecture currently modeled in
     this project:

         shared sun, shared carrier, ring1, ring2

Public API preserved:
    SimpsonTransmission(...).first_gear()
    SimpsonTransmission(...).second_gear()
    SimpsonTransmission(...).third_gear()
    SimpsonTransmission(...).reverse()
    gear_ratio(result, input_member, output_member)
"""

from __future__ import annotations

import logging
from typing import Dict

# -----------------------------------------------------------------------------
# Imports: relative first for `python -m kinematics.simpson_ratio_map`
# -----------------------------------------------------------------------------

try:
    from core.clutch import RotatingMember, Clutch, Brake
    from core.planetary import PlanetaryGearSet
except Exception:
    try:
        from transmissions.core.clutch import RotatingMember, Clutch, Brake
        from transmissions.core.planetary import PlanetaryGearSet
    except Exception:
        from clutch import RotatingMember, Clutch, Brake  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore


LOGGER = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure logging unless the host app already did so."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        )
    LOGGER.setLevel(level)


class SimpsonTransmission:
    """
    Simplified Simpson transmission model used by the current project.

    Parameters
    ----------
    Ns : int
        Sun tooth count.
    Nr1 : int
        Ring 1 tooth count.
    Nr2 : int
        Ring 2 tooth count.
    enable_logging : bool, optional
        Emit INFO logs for each gear solve.

    Notes
    -----
    The modeled members are:
        sun, ring1, ring2, carrier

    Both planetary sets share the same sun and carrier.
    """

    def __init__(self, Ns: int, Nr1: int, Nr2: int, *, enable_logging: bool = False):
        self.Ns = int(Ns)
        self.Nr1 = int(Nr1)
        self.Nr2 = int(Nr2)
        self.enable_logging = bool(enable_logging)

        if self.Ns <= 0 or self.Nr1 <= 0 or self.Nr2 <= 0:
            raise ValueError("All tooth counts must be positive")
        if self.Nr1 <= self.Ns or self.Nr2 <= self.Ns:
            raise ValueError("Ring tooth counts must be greater than the sun tooth count")
        if (self.Nr1 - self.Ns) % 2 != 0 or (self.Nr2 - self.Ns) % 2 != 0:
            raise ValueError(
                "Invalid simple planetary geometry: (Nr - Ns) must be even for both gearsets"
            )

        # Keep the same public members for compatibility with the rest of the app.
        self.sun = RotatingMember("sun")
        self.ring1 = RotatingMember("ring1")
        self.ring2 = RotatingMember("ring2")
        self.carrier = RotatingMember("carrier")

        # Retain the gearset objects for compatibility / introspection.
        self.p1 = PlanetaryGearSet(
            Ns=self.Ns,
            Nr=self.Nr1,
            sun=self.sun,
            ring=self.ring1,
            carrier=self.carrier,
            name="PGS1",
        )
        self.p2 = PlanetaryGearSet(
            Ns=self.Ns,
            Nr=self.Nr2,
            sun=self.sun,
            ring=self.ring2,
            carrier=self.carrier,
            name="PGS2",
        )

        self.ring1_brake = Brake(self.ring1)
        self.ring2_brake = Brake(self.ring2)
        self.direct_clutch = Clutch(self.sun, self.carrier)

        self._log(
            "Initialized SimpsonTransmission Ns=%s Nr1=%s Nr2=%s",
            self.Ns,
            self.Nr1,
            self.Nr2,
        )

    def _log(self, msg: str, *args) -> None:
        if self.enable_logging:
            LOGGER.info(msg, *args)

    def reset(self) -> None:
        self.ring1_brake.release()
        self.ring2_brake.release()
        self.direct_clutch.release()
        self._log("Released all clutches/brakes")

    def _state(self, *, ws: float, wr1: float, wr2: float, wc: float) -> Dict[str, float]:
        return {
            "sun": float(ws),
            "ring1": float(wr1),
            "ring2": float(wr2),
            "carrier": float(wc),
        }

    def first_gear(self) -> Dict[str, float]:
        """
        Project convention:
            input_member = carrier = 1.0
            ring2 fixed by brake

        Planetary 2:
            Ns(ws - wc) + Nr2(wr2 - wc) = 0
            with wc=1, wr2=0
            => ws = (Ns + Nr2)/Ns

        Planetary 1 then gives wr1.
        """
        self.reset()
        self.ring2_brake.engage()

        wc = 1.0
        wr2 = 0.0
        ws = (self.Ns + self.Nr2) / self.Ns
        wr1 = ((self.Ns + self.Nr1) * wc - self.Ns * ws) / self.Nr1

        self._log("1st gear solved: ws=%.6f wr1=%.6f wr2=%.6f wc=%.6f", ws, wr1, wr2, wc)
        return self._state(ws=ws, wr1=wr1, wr2=wr2, wc=wc)

    def second_gear(self) -> Dict[str, float]:
        """
        Project convention:
            input_member = carrier = 1.0
            ring1 fixed by brake
        """
        self.reset()
        self.ring1_brake.engage()

        wc = 1.0
        wr1 = 0.0
        ws = (self.Ns + self.Nr1) / self.Ns
        wr2 = ((self.Ns + self.Nr2) * wc - self.Ns * ws) / self.Nr2

        self._log("2nd gear solved: ws=%.6f wr1=%.6f wr2=%.6f wc=%.6f", ws, wr1, wr2, wc)
        return self._state(ws=ws, wr1=wr1, wr2=wr2, wc=wc)

    def third_gear(self) -> Dict[str, float]:
        """
        Direct clutch locks sun and carrier.

        In the current project convention, direct drive is treated as 1:1.
        The ring speeds collapse to the same speed under the Willis relation.
        """
        self.reset()
        self.direct_clutch.engage()

        wc = 1.0
        ws = 1.0
        wr1 = 1.0
        wr2 = 1.0

        self._log("3rd gear solved (direct): ws=%.6f wr1=%.6f wr2=%.6f wc=%.6f", ws, wr1, wr2, wc)
        return self._state(ws=ws, wr1=wr1, wr2=wr2, wc=wc)

    def reverse(self) -> Dict[str, float]:
        """
        Project convention:
            input_member = sun = 1.0
            ring1 fixed by brake

        This simplified 4-member model does not naturally produce a negative
        carrier speed for reverse using only these constraints, so callers may
        choose to report reverse ratio with a negative sign by convention.
        """
        self.reset()
        self.ring1_brake.engage()

        ws = 1.0
        wr1 = 0.0
        wc = self.Ns / (self.Ns + self.Nr1)
        wr2 = ((self.Ns + self.Nr2) * wc - self.Ns * ws) / self.Nr2

        self._log("Reverse solved: ws=%.6f wr1=%.6f wr2=%.6f wc=%.6f", ws, wr1, wr2, wc)
        return self._state(ws=ws, wr1=wr1, wr2=wr2, wc=wc)


def gear_ratio(result: Dict[str, float], input_member: str, output_member: str) -> float:
    if input_member not in result:
        raise KeyError(f"Missing input_member in result: {input_member}")
    if output_member not in result:
        raise KeyError(f"Missing output_member in result: {output_member}")

    denominator = float(result[output_member])
    if abs(denominator) < 1.0e-12:
        raise ZeroDivisionError(f"Output member '{output_member}' has zero speed")

    return float(result[input_member]) / denominator
