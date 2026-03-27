from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List


def ensure_positive(name: str, value: float) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value}")
    return value


def ensure_nonnegative(name: str, value: float) -> float:
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    return value


def lerp(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def interp_piecewise(xs: List[float], ys: List[float], x: float) -> float:
    if len(xs) != len(ys):
        raise ValueError("xs and ys must have the same length")
    if len(xs) < 2:
        raise ValueError("need at least two points")
    if any(xs[i] > xs[i + 1] for i in range(len(xs) - 1)):
        raise ValueError("xs must be sorted ascending")

    if x <= xs[0]:
        return lerp(xs[0], ys[0], xs[1], ys[1], x)
    if x >= xs[-1]:
        return lerp(xs[-2], ys[-2], xs[-1], ys[-1], x)

    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            return lerp(xs[i], ys[i], xs[i + 1], ys[i + 1], x)
    raise RuntimeError("interpolation failed")


def product(values: Iterable[float]) -> float:
    out = 1.0
    for v in values:
        out *= v
    return out


def pretty_float(x: Any, digits: int = 6) -> Any:
    if isinstance(x, float):
        return round(x, digits)
    return x


def pretty_data(obj: Any, digits: int = 6) -> Any:
    if isinstance(obj, dict):
        return {k: pretty_data(v, digits=digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [pretty_data(v, digits=digits) for v in obj]
    if isinstance(obj, tuple):
        return [pretty_data(v, digits=digits) for v in obj]
    return pretty_float(obj, digits=digits)


@dataclass
class WeibullParams:
    a: float
    x0: float
    theta_minus_x0: float
    b: float

    @property
    def theta(self) -> float:
        return self.x0 + self.theta_minus_x0

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)