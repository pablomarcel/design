from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class ClutchesBrakesError(Exception):
    """Base application error."""


class ValidationError(ClutchesBrakesError):
    """Raised when user input is invalid."""



def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)



def deg_to_rad(value_deg: float) -> float:
    return math.radians(value_deg)



def rad_to_deg(value_rad: float) -> float:
    return math.degrees(value_rad)



def round_floats(obj: Any, digits: int = 6) -> Any:
    if isinstance(obj, float):
        return round(obj, digits)
    if isinstance(obj, dict):
        return {k: round_floats(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, digits) for v in obj]
    if is_dataclass(obj):
        return round_floats(asdict(obj), digits)
    return obj



def dump_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(round_floats(data), f, indent=2)
        f.write("\n")



def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
