from __future__ import annotations

from typing import Any

try:
    from .core import (
        DeflectionVectorCalculator,
        DiameterResizeCalculator,
        DiameterResizeInput,
        EnduranceLimitCalculator,
        EnduranceLimitInput,
        FatigueCalculator,
        FatigueInput,
        TorsionCalculator,
        TorsionInput,
        TorsionSegment,
        VectorPair,
        YieldCalculator,
        YieldInput,
    )
except ImportError:  # pragma: no cover - local package execution shim
    from core import (
        DeflectionVectorCalculator,
        DiameterResizeCalculator,
        DiameterResizeInput,
        EnduranceLimitCalculator,
        EnduranceLimitInput,
        FatigueCalculator,
        FatigueInput,
        TorsionCalculator,
        TorsionInput,
        TorsionSegment,
        VectorPair,
        YieldCalculator,
        YieldInput,
    )


class ShaftAPI:
    def endurance_limit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return EnduranceLimitCalculator(EnduranceLimitInput(**payload)).solve()

    def fatigue(self, payload: dict[str, Any]) -> dict[str, Any]:
        return FatigueCalculator(FatigueInput(**payload)).solve()

    def yielding(self, payload: dict[str, Any]) -> dict[str, Any]:
        return YieldCalculator(YieldInput(**payload)).solve()

    def vector_sum(self, payload: dict[str, Any]) -> dict[str, Any]:
        pairs = [VectorPair(**item) for item in payload["pairs"]]
        return DeflectionVectorCalculator(pairs).solve()

    def diameter_resize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return DiameterResizeCalculator(DiameterResizeInput(**payload)).solve()

    def torsion_angle(self, payload: dict[str, Any]) -> dict[str, Any]:
        segments = [TorsionSegment(**seg) for seg in payload["segments"]]
        return TorsionCalculator(TorsionInput(G=payload.get("G"), T=payload.get("T"), segments=segments)).angle_of_twist()

    def torsional_stiffness(self, payload: dict[str, Any]) -> dict[str, Any]:
        segments = [TorsionSegment(**seg) for seg in payload["segments"]]
        return TorsionCalculator(TorsionInput(G=payload.get("G"), T=payload.get("T"), segments=segments)).stiffness()

    def dispatch(self, calc: str, payload: dict[str, Any]) -> dict[str, Any]:
        table = {
            "endurance_limit": self.endurance_limit,
            "fatigue": self.fatigue,
            "yield": self.yielding,
            "vector_sum": self.vector_sum,
            "diameter_resize": self.diameter_resize,
            "torsion_angle": self.torsion_angle,
            "torsional_stiffness": self.torsional_stiffness,
        }
        if calc not in table:
            raise ValueError(f"Unsupported calculation: {calc}")
        return table[calc](payload)
