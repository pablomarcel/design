from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

try:
    from .utils import PI, cubic_root, product, rad_to_deg, vector_sum_2d
except ImportError:  # pragma: no cover - local package execution shim
    from utils import PI, cubic_root, product, rad_to_deg, vector_sum_2d


@dataclass
class EnduranceLimitInput:
    se_prime: float
    ka: float = 1.0
    kb: float = 1.0
    kc: float = 1.0
    kd: float = 1.0
    ke: float = 1.0
    kf_misc: float = 1.0


class EnduranceLimitCalculator:
    def __init__(self, inputs: EnduranceLimitInput) -> None:
        self.inputs = inputs

    def solve(self) -> dict[str, Any]:
        modifiers = {
            "ka": self.inputs.ka,
            "kb": self.inputs.kb,
            "kc": self.inputs.kc,
            "kd": self.inputs.kd,
            "ke": self.inputs.ke,
            "kf_misc": self.inputs.kf_misc,
        }
        se = self.inputs.se_prime * product(modifiers.values())
        return {
            "calculation": "endurance_limit",
            "inputs": asdict(self.inputs),
            "modifiers": modifiers,
            "Se": se,
        }


@dataclass
class ShaftStressInput:
    Kf: float
    Kfs: float
    Ma: float = 0.0
    Mm: float = 0.0
    Ta: float = 0.0
    Tm: float = 0.0
    d: float = 1.0


class ShaftStressCalculator:
    def __init__(self, inputs: ShaftStressInput) -> None:
        self.i = inputs

    def sigma_a(self) -> float:
        return self.i.Kf * 32.0 * self.i.Ma / (PI * self.i.d**3)

    def sigma_m(self) -> float:
        return self.i.Kf * 32.0 * self.i.Mm / (PI * self.i.d**3)

    def tau_a(self) -> float:
        return self.i.Kfs * 16.0 * self.i.Ta / (PI * self.i.d**3)

    def tau_m(self) -> float:
        return self.i.Kfs * 16.0 * self.i.Tm / (PI * self.i.d**3)

    def sigma_a_vm(self) -> float:
        return math.sqrt(self.sigma_a() ** 2 + 3.0 * self.tau_a() ** 2)

    def sigma_m_vm(self) -> float:
        return math.sqrt(self.sigma_m() ** 2 + 3.0 * self.tau_m() ** 2)

    def A(self) -> float:
        return math.sqrt(4.0 * (self.i.Kf * self.i.Ma) ** 2 + 3.0 * (self.i.Kfs * self.i.Ta) ** 2)

    def B(self) -> float:
        return math.sqrt(4.0 * (self.i.Kf * self.i.Mm) ** 2 + 3.0 * (self.i.Kfs * self.i.Tm) ** 2)

    def sigma_max_vm(self) -> float:
        return math.sqrt(
            (32.0 * self.i.Kf * (self.i.Mm + self.i.Ma) / (PI * self.i.d**3)) ** 2
            + 3.0 * (16.0 * self.i.Kfs * (self.i.Tm + self.i.Ta) / (PI * self.i.d**3)) ** 2
        )

    def solve(self) -> dict[str, Any]:
        return {
            "calculation": "shaft_stresses",
            "inputs": asdict(self.i),
            "sigma_a": self.sigma_a(),
            "sigma_m": self.sigma_m(),
            "tau_a": self.tau_a(),
            "tau_m": self.tau_m(),
            "sigma_a_prime": self.sigma_a_vm(),
            "sigma_m_prime": self.sigma_m_vm(),
            "A": self.A(),
            "B": self.B(),
            "sigma_max_prime": self.sigma_max_vm(),
        }


@dataclass
class FatigueInput:
    criterion: str
    Kf: float
    Kfs: float
    Se: float
    Sut: float | None = None
    Sy: float | None = None
    Ma: float = 0.0
    Mm: float = 0.0
    Ta: float = 0.0
    Tm: float = 0.0
    d: float | None = None
    n: float | None = None


class FatigueCalculator:
    VALID = {"de_goodman", "de_gerber", "de_asme_elliptic", "de_soderberg"}

    def __init__(self, inputs: FatigueInput) -> None:
        if inputs.criterion not in self.VALID:
            raise ValueError(f"Unsupported criterion: {inputs.criterion}")
        self.i = inputs

    def _stress(self, d: float) -> ShaftStressCalculator:
        return ShaftStressCalculator(
            ShaftStressInput(
                Kf=self.i.Kf,
                Kfs=self.i.Kfs,
                Ma=self.i.Ma,
                Mm=self.i.Mm,
                Ta=self.i.Ta,
                Tm=self.i.Tm,
                d=d,
            )
        )

    def factor_of_safety(self, d: float) -> dict[str, Any]:
        sc = self._stress(d)
        A = sc.A()
        B = sc.B()
        base = 16.0 / (PI * d**3)
        criterion = self.i.criterion
        if criterion == "de_goodman":
            if self.i.Sut is None:
                raise ValueError("Sut is required for DE-Goodman")
            inv_n = base * (A / self.i.Se + B / self.i.Sut)
        elif criterion == "de_gerber":
            if self.i.Sut is None:
                raise ValueError("Sut is required for DE-Gerber")
            inv_n = (8.0 * A / (PI * d**3 * self.i.Se)) * (
                1.0 + math.sqrt(1.0 + (2.0 * B * self.i.Se / (A * self.i.Sut)) ** 2)
            )
        elif criterion == "de_asme_elliptic":
            if self.i.Sy is None:
                raise ValueError("Sy is required for DE-ASME Elliptic")
            inv_n = base * math.sqrt(
                4.0 * (self.i.Kf * self.i.Ma / self.i.Se) ** 2
                + 3.0 * (self.i.Kfs * self.i.Ta / self.i.Se) ** 2
                + 4.0 * (self.i.Kf * self.i.Mm / self.i.Sy) ** 2
                + 3.0 * (self.i.Kfs * self.i.Tm / self.i.Sy) ** 2
            )
        elif criterion == "de_soderberg":
            if self.i.Sy is None:
                raise ValueError("Sy is required for DE-Soderberg")
            inv_n = base * (A / self.i.Se + B / self.i.Sy)
        else:  # pragma: no cover
            raise RuntimeError("unreachable")
        n = 1.0 / inv_n
        return {
            "criterion": criterion,
            "d": d,
            "n": n,
            "A": A,
            "B": B,
            "sigma_a_prime": sc.sigma_a_vm(),
            "sigma_m_prime": sc.sigma_m_vm(),
        }

    def required_diameter(self, n: float) -> dict[str, Any]:
        criterion = self.i.criterion
        dummy_d = 1.0
        sc = self._stress(dummy_d)
        A = sc.A()
        B = sc.B()
        if criterion == "de_goodman":
            if self.i.Sut is None:
                raise ValueError("Sut is required for DE-Goodman")
            val = (16.0 * n / PI) * (A / self.i.Se + B / self.i.Sut)
            d = cubic_root(val)
        elif criterion == "de_gerber":
            if self.i.Sut is None:
                raise ValueError("Sut is required for DE-Gerber")
            val = (8.0 * n * A / (PI * self.i.Se)) * (
                1.0 + math.sqrt(1.0 + (2.0 * B * self.i.Se / (A * self.i.Sut)) ** 2)
            )
            d = cubic_root(val)
        elif criterion == "de_asme_elliptic":
            if self.i.Sy is None:
                raise ValueError("Sy is required for DE-ASME Elliptic")
            val = (16.0 * n / PI) * math.sqrt(
                4.0 * (self.i.Kf * self.i.Ma / self.i.Se) ** 2
                + 3.0 * (self.i.Kfs * self.i.Ta / self.i.Se) ** 2
                + 4.0 * (self.i.Kf * self.i.Mm / self.i.Sy) ** 2
                + 3.0 * (self.i.Kfs * self.i.Tm / self.i.Sy) ** 2
            )
            d = cubic_root(val)
        elif criterion == "de_soderberg":
            if self.i.Sy is None:
                raise ValueError("Sy is required for DE-Soderberg")
            val = (16.0 * n / PI) * (A / self.i.Se + B / self.i.Sy)
            d = cubic_root(val)
        else:  # pragma: no cover
            raise RuntimeError("unreachable")
        return {
            "criterion": criterion,
            "n": n,
            "d": d,
            "A": A,
            "B": B,
        }

    def solve(self) -> dict[str, Any]:
        if self.i.d is not None and self.i.n is not None:
            raise ValueError("Provide either d for factor-of-safety mode or n for diameter mode, not both")
        if self.i.d is None and self.i.n is None:
            raise ValueError("Provide d for factor-of-safety mode or n for diameter mode")
        if self.i.d is not None:
            out = self.factor_of_safety(self.i.d)
            mode = "factor_of_safety"
        else:
            out = self.required_diameter(self.i.n or 0.0)
            mode = "diameter"
        return {
            "calculation": "fatigue",
            "mode": mode,
            "inputs": asdict(self.i),
            "result": out,
        }


@dataclass
class YieldInput:
    Kf: float
    Kfs: float
    Sy: float
    d: float
    Ma: float = 0.0
    Mm: float = 0.0
    Ta: float = 0.0
    Tm: float = 0.0


class YieldCalculator:
    def __init__(self, inputs: YieldInput) -> None:
        self.i = inputs

    def solve(self) -> dict[str, Any]:
        sc = ShaftStressCalculator(
            ShaftStressInput(
                Kf=self.i.Kf,
                Kfs=self.i.Kfs,
                Ma=self.i.Ma,
                Mm=self.i.Mm,
                Ta=self.i.Ta,
                Tm=self.i.Tm,
                d=self.i.d,
            )
        )
        sigma_max = sc.sigma_max_vm()
        ny = self.i.Sy / sigma_max
        return {
            "calculation": "yield",
            "inputs": asdict(self.i),
            "sigma_max_prime": sigma_max,
            "n_y": ny,
        }


@dataclass
class VectorPair:
    xz: float
    xy: float
    units: str | None = None
    label: str | None = None


class DeflectionVectorCalculator:
    def __init__(self, pairs: Iterable[VectorPair]) -> None:
        self.pairs = list(pairs)

    def solve(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for p in self.pairs:
            total = vector_sum_2d(p.xz, p.xy)
            items.append({
                "label": p.label,
                "xz": p.xz,
                "xy": p.xy,
                "total": total,
                "units": p.units,
            })
        return {
            "calculation": "vector_sum",
            "count": len(items),
            "items": items,
        }


@dataclass
class DiameterResizeInput:
    d_old: float
    response_old: float
    response_allow: float
    n_design: float = 1.0
    mode: str = "deflection"


class DiameterResizeCalculator:
    def __init__(self, inputs: DiameterResizeInput) -> None:
        if inputs.response_allow <= 0:
            raise ValueError("response_allow must be positive")
        if inputs.d_old <= 0:
            raise ValueError("d_old must be positive")
        self.i = inputs

    def solve(self) -> dict[str, Any]:
        ratio = (self.i.n_design * self.i.response_old / self.i.response_allow) ** 0.25
        d_new = self.i.d_old * ratio
        return {
            "calculation": "diameter_resize",
            "mode": self.i.mode,
            "inputs": asdict(self.i),
            "diameter_ratio": ratio,
            "d_new": d_new,
        }


@dataclass
class TorsionSegment:
    length: float
    torque: float | None = None
    J: float | None = None
    k: float | None = None


@dataclass
class TorsionInput:
    G: float | None = None
    T: float | None = None
    segments: list[TorsionSegment] = field(default_factory=list)


class TorsionCalculator:
    def __init__(self, inputs: TorsionInput) -> None:
        self.i = inputs

    def angle_of_twist(self) -> dict[str, Any]:
        if self.i.G is None:
            raise ValueError("G is required for angle of twist")
        total = 0.0
        details: list[dict[str, Any]] = []
        for idx, seg in enumerate(self.i.segments, start=1):
            if seg.J is None:
                raise ValueError("Each segment needs J for angle of twist")
            torque = self.i.T if self.i.T is not None else seg.torque
            if torque is None:
                raise ValueError("Provide constant T or per-segment torque values")
            theta_i = torque * seg.length / (self.i.G * seg.J)
            total += theta_i
            details.append({
                "segment": idx,
                "length": seg.length,
                "torque": torque,
                "J": seg.J,
                "theta_i_rad": theta_i,
                "theta_i_deg": rad_to_deg(theta_i),
            })
        return {
            "calculation": "torsion_angle",
            "inputs": {
                "G": self.i.G,
                "T": self.i.T,
                "segments": [asdict(s) for s in self.i.segments],
            },
            "theta_total_rad": total,
            "theta_total_deg": rad_to_deg(total),
            "details": details,
        }

    def stiffness(self) -> dict[str, Any]:
        inv_k_total = 0.0
        details: list[dict[str, Any]] = []
        for idx, seg in enumerate(self.i.segments, start=1):
            k_i = seg.k
            if k_i is None:
                if self.i.G is None or seg.J is None:
                    raise ValueError("For stiffness, each segment needs k or both G and J")
                k_i = self.i.G * seg.J / seg.length
            inv_k_total += 1.0 / k_i
            details.append({
                "segment": idx,
                "length": seg.length,
                "k_i": k_i,
            })
        k_total = 1.0 / inv_k_total
        return {
            "calculation": "torsional_stiffness",
            "inputs": {
                "G": self.i.G,
                "segments": [asdict(s) for s in self.i.segments],
            },
            "k_total": k_total,
            "details": details,
        }
