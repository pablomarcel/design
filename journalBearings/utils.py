from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict
import json
import math


def to_plain_data(obj: Any) -> Any:
    if is_dataclass(obj):
        return to_plain_data(asdict(obj))
    if isinstance(obj, dict):
        return {k: to_plain_data(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain_data(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def dump_json(data: Any, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(to_plain_data(data), f, indent=2, sort_keys=False)
        f.write("\n")


def load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def fmt(x: Any, digits: int = 6) -> str:
    if x is None:
        return "-"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return str(x)
        if abs(x) < 1e8:
            return f"{x:.{digits}f}".rstrip("0").rstrip(".")
        return f"{x:.6e}"
    return str(x)


def safe_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Field '{field_name}' must be a real number; got {value!r}.") from exc


def normalize_problem_name(name: str) -> str:
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "12_1": "minimum_film_thickness",
        "12_2": "coefficient_of_friction",
        "12_3": "volumetric_flow_rate",
        "12_4": "maximum_film_pressure",
        "example_12_1": "minimum_film_thickness",
        "example_12_2": "coefficient_of_friction",
        "example_12_3": "volumetric_flow_rate",
        "example_12_4": "maximum_film_pressure",
        "minimumfilmthickness": "minimum_film_thickness",
        "coefficientoffriction": "coefficient_of_friction",
        "volumetricflowrate": "volumetric_flow_rate",
        "maximumfilmpressure": "maximum_film_pressure",
        "friction": "coefficient_of_friction",
        "flow": "volumetric_flow_rate",
        "pressure": "maximum_film_pressure",
    }
    return aliases.get(key, key)
