from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

try:
    from .utils import PI, cubic_root, product, rad_to_deg, vector_sum_2d
except ImportError:  # pragma: no cover - local package execution shim
    from utils import PI, cubic_root, product, rad_to_deg, vector_sum_2d


VALID_STRENGTH_UNITS = {"psi", "ksi", "mpa", "pa"}


def _validate_positive(name: str, value: float) -> None:
    if value <= 0.0:
        raise ValueError(f"{name} must be > 0")


def _strength_to_psi(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u not in VALID_STRENGTH_UNITS:
        raise ValueError(
            f"Unsupported strength unit: {unit}. "
            f"Valid options are: {sorted(VALID_STRENGTH_UNITS)}"
        )
    if u == "psi":
        return value
    if u == "ksi":
        return value * 1000.0
    if u == "mpa":
        return value * 145.03773773020923
    if u == "pa":
        return value * 0.00014503773773020923
    raise RuntimeError("unreachable")


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
        _validate_positive("se_prime", self.inputs.se_prime)
        for name in ("ka", "kb", "kc", "kd", "ke", "kf_misc"):
            _validate_positive(name, getattr(self.inputs, name))

    def solve(self) -> dict[str, Any]:
        modifiers = {
            "ka": self.inputs.ka,
            "kb": self.inputs.kb,
            "kc": self.inputs.kc,
            "kd": self.inputs.kd,
            "ke": self.inputs.ke,
            "kf_misc": self.inputs.kf_misc,
        }
        modifier_product = product(modifiers.values())
        se = self.inputs.se_prime * modifier_product
        return {
            "calculation": "endurance_limit",
            "equation": "Se = ka * kb * kc * kd * ke * kf_misc * Se_prime",
            "inputs": asdict(self.inputs),
            "modifiers": modifiers,
            "modifier_product": modifier_product,
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
        _validate_positive("Kf", self.i.Kf)
        _validate_positive("Kfs", self.i.Kfs)
        _validate_positive("d", self.i.d)

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
        return math.sqrt(
            4.0 * (self.i.Kf * self.i.Ma) ** 2
            + 3.0 * (self.i.Kfs * self.i.Ta) ** 2
        )

    def B(self) -> float:
        return math.sqrt(
            4.0 * (self.i.Kf * self.i.Mm) ** 2
            + 3.0 * (self.i.Kfs * self.i.Tm) ** 2
        )

    def sigma_max_vm(self) -> float:
        return math.sqrt(
            (32.0 * self.i.Kf * (self.i.Mm + self.i.Ma) / (PI * self.i.d**3)) ** 2
            + 3.0
            * (16.0 * self.i.Kfs * (self.i.Tm + self.i.Ta) / (PI * self.i.d**3)) ** 2
        )

    def solve(self) -> dict[str, Any]:
        return {
            "calculation": "shaft_stresses",
            "inputs": asdict(self.i),
            "units": {
                "moments_torques": "assumed consistent with d",
                "stresses": "same base stress unit implied by input system",
            },
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
    strength_unit: str = "ksi"


class FatigueCalculator:
    VALID = {"de_goodman", "de_gerber", "de_asme_elliptic", "de_soderberg"}

    def __init__(self, inputs: FatigueInput) -> None:
        if inputs.criterion not in self.VALID:
            raise ValueError(f"Unsupported criterion: {inputs.criterion}")
        self.i = inputs
        _validate_positive("Kf", self.i.Kf)
        _validate_positive("Kfs", self.i.Kfs)
        _validate_positive("Se", self.i.Se)
        if self.i.Sut is not None:
            _validate_positive("Sut", self.i.Sut)
        if self.i.Sy is not None:
            _validate_positive("Sy", self.i.Sy)

    def _Se_psi(self) -> float:
        return _strength_to_psi(self.i.Se, self.i.strength_unit)

    def _Sut_psi(self) -> float:
        if self.i.Sut is None:
            raise ValueError("Sut is required for this criterion")
        return _strength_to_psi(self.i.Sut, self.i.strength_unit)

    def _Sy_psi(self) -> float:
        if self.i.Sy is None:
            raise ValueError("Sy is required for this criterion")
        return _strength_to_psi(self.i.Sy, self.i.strength_unit)

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
        _validate_positive("d", d)

        sc = self._stress(d)
        A = sc.A()
        B = sc.B()
        base = 16.0 / (PI * d**3)

        Se = self._Se_psi()
        criterion = self.i.criterion

        if criterion == "de_goodman":
            Sut = self._Sut_psi()
            inv_n = base * (A / Se + B / Sut)

        elif criterion == "de_gerber":
            Sut = self._Sut_psi()

            if A == 0.0:
                if B == 0.0:
                    n = math.inf
                else:
                    # Gerber collapses to pure mean-stress limit when alternating part is zero.
                    # Use a conservative linear mean-stress fallback instead of dividing by zero.
                    inv_n = base * (B / Sut)
                    n = 1.0 / inv_n
                return {
                    "criterion": criterion,
                    "d": d,
                    "n": n,
                    "A": A,
                    "B": B,
                    "sigma_a_prime": sc.sigma_a_vm(),
                    "sigma_m_prime": sc.sigma_m_vm(),
                    "strength_unit_in": self.i.strength_unit,
                    "strength_unit_internal": "psi",
                    "Se_internal": Se,
                    "Sut_internal": Sut,
                    "Sy_internal": _strength_to_psi(self.i.Sy, self.i.strength_unit)
                    if self.i.Sy is not None
                    else None,
                    "note": "A=0 Gerber special case handled without division by zero.",
                }

            inv_n = (8.0 * A / (PI * d**3 * Se)) * (
                1.0 + math.sqrt(1.0 + (2.0 * B * Se / (A * Sut)) ** 2)
            )

        elif criterion == "de_asme_elliptic":
            Sy = self._Sy_psi()
            inv_n = base * math.sqrt(
                4.0 * (self.i.Kf * self.i.Ma / Se) ** 2
                + 3.0 * (self.i.Kfs * self.i.Ta / Se) ** 2
                + 4.0 * (self.i.Kf * self.i.Mm / Sy) ** 2
                + 3.0 * (self.i.Kfs * self.i.Tm / Sy) ** 2
            )

        elif criterion == "de_soderberg":
            Sy = self._Sy_psi()
            inv_n = base * (A / Se + B / Sy)

        else:  # pragma: no cover
            raise RuntimeError("unreachable")

        n = math.inf if inv_n == 0.0 else 1.0 / inv_n
        return {
            "criterion": criterion,
            "d": d,
            "n": n,
            "A": A,
            "B": B,
            "sigma_a_prime": sc.sigma_a_vm(),
            "sigma_m_prime": sc.sigma_m_vm(),
            "strength_unit_in": self.i.strength_unit,
            "strength_unit_internal": "psi",
            "Se_internal": Se,
            "Sut_internal": _strength_to_psi(self.i.Sut, self.i.strength_unit)
            if self.i.Sut is not None
            else None,
            "Sy_internal": _strength_to_psi(self.i.Sy, self.i.strength_unit)
            if self.i.Sy is not None
            else None,
        }

    def required_diameter(self, n: float) -> dict[str, Any]:
        _validate_positive("n", n)

        criterion = self.i.criterion
        dummy_d = 1.0
        sc = self._stress(dummy_d)
        A = sc.A()
        B = sc.B()
        Se = self._Se_psi()

        if criterion == "de_goodman":
            Sut = self._Sut_psi()
            val = (16.0 * n / PI) * (A / Se + B / Sut)
            d = cubic_root(val)

        elif criterion == "de_gerber":
            Sut = self._Sut_psi()

            if A == 0.0:
                if B == 0.0:
                    d = 0.0
                else:
                    # Conservative fallback for zero alternating component.
                    val = (16.0 * n / PI) * (B / Sut)
                    d = cubic_root(val)
                return {
                    "criterion": criterion,
                    "n": n,
                    "d": d,
                    "A": A,
                    "B": B,
                    "strength_unit_in": self.i.strength_unit,
                    "strength_unit_internal": "psi",
                    "Se_internal": Se,
                    "Sut_internal": Sut,
                    "Sy_internal": _strength_to_psi(self.i.Sy, self.i.strength_unit)
                    if self.i.Sy is not None
                    else None,
                    "note": "A=0 Gerber special case handled without division by zero.",
                }

            val = (8.0 * n * A / (PI * Se)) * (
                1.0 + math.sqrt(1.0 + (2.0 * B * Se / (A * Sut)) ** 2)
            )
            d = cubic_root(val)

        elif criterion == "de_asme_elliptic":
            Sy = self._Sy_psi()
            val = (16.0 * n / PI) * math.sqrt(
                4.0 * (self.i.Kf * self.i.Ma / Se) ** 2
                + 3.0 * (self.i.Kfs * self.i.Ta / Se) ** 2
                + 4.0 * (self.i.Kf * self.i.Mm / Sy) ** 2
                + 3.0 * (self.i.Kfs * self.i.Tm / Sy) ** 2
            )
            d = cubic_root(val)

        elif criterion == "de_soderberg":
            Sy = self._Sy_psi()
            val = (16.0 * n / PI) * (A / Se + B / Sy)
            d = cubic_root(val)

        else:  # pragma: no cover
            raise RuntimeError("unreachable")

        return {
            "criterion": criterion,
            "n": n,
            "d": d,
            "A": A,
            "B": B,
            "strength_unit_in": self.i.strength_unit,
            "strength_unit_internal": "psi",
            "Se_internal": Se,
            "Sut_internal": _strength_to_psi(self.i.Sut, self.i.strength_unit)
            if self.i.Sut is not None
            else None,
            "Sy_internal": _strength_to_psi(self.i.Sy, self.i.strength_unit)
            if self.i.Sy is not None
            else None,
        }

    def solve(self) -> dict[str, Any]:
        if self.i.d is not None and self.i.n is not None:
            raise ValueError(
                "Provide either d for factor-of-safety mode or n for diameter mode, not both"
            )
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
    strength_unit: str = "ksi"


class YieldCalculator:
    def __init__(self, inputs: YieldInput) -> None:
        self.i = inputs
        _validate_positive("Kf", self.i.Kf)
        _validate_positive("Kfs", self.i.Kfs)
        _validate_positive("Sy", self.i.Sy)
        _validate_positive("d", self.i.d)

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
        Sy_psi = _strength_to_psi(self.i.Sy, self.i.strength_unit)
        ny = math.inf if sigma_max == 0.0 else Sy_psi / sigma_max
        return {
            "calculation": "yield",
            "inputs": asdict(self.i),
            "strength_unit_in": self.i.strength_unit,
            "strength_unit_internal": "psi",
            "Sy_internal": Sy_psi,
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
            items.append(
                {
                    "label": p.label,
                    "xz": p.xz,
                    "xy": p.xy,
                    "total": total,
                    "units": p.units,
                }
            )
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
            details.append(
                {
                    "segment": idx,
                    "length": seg.length,
                    "torque": torque,
                    "J": seg.J,
                    "theta_i_rad": theta_i,
                    "theta_i_deg": rad_to_deg(theta_i),
                }
            )
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
            details.append(
                {
                    "segment": idx,
                    "length": seg.length,
                    "k_i": k_i,
                }
            )
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