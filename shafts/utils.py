from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence


PI = math.pi


def require_keys(data: dict[str, Any], keys: Sequence[str], context: str = "input") -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise KeyError(f"Missing required keys for {context}: {', '.join(missing)}")



def product(values: Iterable[float]) -> float:
    out = 1.0
    for v in values:
        out *= float(v)
    return out



def cubic_root(x: float) -> float:
    if x >= 0:
        return x ** (1.0 / 3.0)
    return -((-x) ** (1.0 / 3.0))



def vector_sum_2d(x: float, y: float) -> float:
    return math.hypot(float(x), float(y))



def deg_to_rad(deg: float) -> float:
    return math.radians(float(deg))



def rad_to_deg(rad: float) -> float:
    return math.degrees(float(rad))



def to_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Could not convert {name!r} to float: {value!r}") from exc



def safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("_", "-", ".") else "_" for ch in name)



def dumps_pretty(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=False)



def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
