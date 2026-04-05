from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence


G_FTPS2 = 32.17
HP_TORQUE_CONSTANT = 63025.0


class FlexibleElementsError(Exception):
    """Base exception for the package."""


class DataLookupError(FlexibleElementsError):
    """Raised when a lookup in a data table cannot be completed."""


class InputValidationError(FlexibleElementsError):
    """Raised when the user input is inconsistent or incomplete."""


class IterationError(FlexibleElementsError):
    """Raised when an iterative routine cannot find a satisfactory solution."""


class PathHelper:
    """Locate package-relative folders without depending on cwd."""

    def __init__(self, anchor_file: str):
        self.package_dir = Path(anchor_file).resolve().parent
        self.in_dir = self.package_dir / "in"
        self.out_dir = self.package_dir / "out"
        self.data_dir = self.package_dir / "data"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(data: dict[str, Any], path: Path) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")


def first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def infer_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    raise InputValidationError(f"Cannot interpret boolean value: {value!r}")


def to_float(value: Any, *, field_name: str) -> float:
    try:
        return float(value)
    except Exception as exc:
        raise InputValidationError(f"Field '{field_name}' must be numeric, got {value!r}") from exc


def belt_speed_ft_min(diameter_in: float, rpm: float) -> float:
    return math.pi * diameter_in * rpm / 12.0


def weight_per_foot_lbf_ft(gamma_lbf_in3: float, width_in: float, thickness_in: float) -> float:
    return 12.0 * gamma_lbf_in3 * width_in * thickness_in


def centrifugal_tension_lbf(weight_per_ft_lbf_ft: float, belt_speed_ft_min_value: float) -> float:
    return (weight_per_ft_lbf_ft / G_FTPS2) * (belt_speed_ft_min_value / 60.0) ** 2


def open_belt_contact_angle_rad(big_diameter_in: float, small_diameter_in: float, center_distance_ft: float) -> float:
    c_in = center_distance_ft * 12.0
    ratio = (big_diameter_in - small_diameter_in) / (2.0 * c_in)
    if abs(ratio) > 1.0:
        raise InputValidationError(
            f"Invalid geometry. asin argument {(ratio):.6f} is outside [-1, 1]."
        )
    return math.pi - 2.0 * math.asin(ratio)


def transmitted_torque_lbf_in(power_hp: float, rpm: float) -> float:
    return HP_TORQUE_CONSTANT * power_hp / rpm


def next_larger_value(target: float, candidates: Sequence[float]) -> float:
    ordered = sorted(float(x) for x in candidates)
    for value in ordered:
        if value >= target:
            return value
    raise DataLookupError(f"No candidate value is greater than or equal to required target {target:.6g}.")


def format_float(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return float(f"{value:.{digits}f}")


def sanitize_for_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, float):
        if math.isfinite(obj):
            return format_float(obj, 6)
        return str(obj)
    return obj


def require_fields(payload: dict[str, Any], fields: Iterable[str]) -> None:
    missing = [name for name in fields if name not in payload]
    if missing:
        raise InputValidationError(f"Missing required fields: {', '.join(missing)}")


def linear_interpolate(x: float, x0: float, y0: float, x1: float, y1: float) -> float:
    if x1 == x0:
        return float(y0)
    return float(y0) + (float(y1) - float(y0)) * (float(x) - float(x0)) / (float(x1) - float(x0))
