from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


ROOT_DIR = Path(__file__).resolve().parent
DATA_CANDIDATES = [
    ROOT_DIR / "data",
    ROOT_DIR.parent / "data",
    Path("/mnt/data"),
]


def first_existing_path(candidates: Iterable[Path]) -> Optional[Path]:
    for path in candidates:
        if path.exists():
            return path
    return None


def find_data_file(filename: str) -> Path:
    for base in DATA_CANDIDATES:
        candidate = base / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not locate data file: {filename}")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


SAFE_NAMES = {
    "pi": math.pi,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "degrees": math.degrees,
    "radians": math.radians,
    "abs": abs,
    "min": min,
    "max": max,
}


def _normalize_expression(expr: str) -> str:
    normalized = expr.strip()
    if "=" in normalized:
        normalized = normalized.split("=", 1)[1].strip()
    normalized = normalized.replace("^", "**")
    normalized = normalized.replace("x_bar", "x_bar")
    normalized = normalized.replace("y_bar", "y_bar")
    return normalized


def evaluate_expression(expr: str, variables: Mapping[str, float]) -> float:
    compiled = _normalize_expression(expr)
    scope = dict(SAFE_NAMES)
    scope.update(variables)
    return float(eval(compiled, {"__builtins__": {}}, scope))


ENGINEERING_UNITS = {
    "force": {"N": 1.0, "kN": 1e3, "lbf": 4.4482216152605},
    "length": {"mm": 1.0, "m": 1000.0, "in": 25.4},
    "stress": {"MPa": 1.0, "Pa": 1e-6, "psi": 0.006894757293168361, "ksi": 6.894757293168361},
    "moment": {"N_mm": 1.0, "N_m": 1000.0, "lbf_in": 112.9848290276167, "lbf_ft": 1355.8179483314},
}


def convert_value(value: float, kind: str, from_unit: str, to_unit: str) -> float:
    if from_unit == to_unit:
        return value
    unit_map = ENGINEERING_UNITS[kind]
    if from_unit not in unit_map:
        raise KeyError(f"Unsupported {kind} unit: {from_unit}")
    if to_unit not in unit_map:
        raise KeyError(f"Unsupported {kind} unit: {to_unit}")
    base = value * unit_map[from_unit]
    return base / unit_map[to_unit]


def round_sig(value: float, digits: int = 6) -> float:
    if value == 0:
        return 0.0
    return round(value, digits - int(math.floor(math.log10(abs(value)))) - 1)


def format_json(data: Mapping[str, Any], pretty: bool = True) -> str:
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Mapping[str, Any], pretty: bool = True) -> None:
    ensure_parent_dir(path)
    with path.open("w", encoding="utf-8") as f:
        f.write(format_json(data, pretty=pretty))
        f.write("\n")


def magnitude_2d(x: float, y: float) -> float:
    return math.hypot(x, y)


def angle_deg_from_x(x: float, y: float) -> float:
    return math.degrees(math.atan2(y, x))


def coerce_path(path_like: str | Path, base_dir: Optional[Path] = None) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    if base_dir is not None:
        candidate = base_dir / path
        if candidate.exists() or not path.exists():
            return candidate
    return path


class ValidationError(ValueError):
    """Raised when user inputs are invalid for the selected solve path."""
