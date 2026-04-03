from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
IN_DIR = PACKAGE_DIR / "in"
OUT_DIR = PACKAGE_DIR / "out"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def pretty_float(value: Any, ndigits: int = 6) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return round(value, ndigits)
    return value


def round_dict(obj: Any, ndigits: int = 6) -> Any:
    if isinstance(obj, dict):
        return {k: round_dict(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_dict(v, ndigits) for v in obj]
    return pretty_float(obj, ndigits)


def first_non_none(values: Iterable[Any]) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
