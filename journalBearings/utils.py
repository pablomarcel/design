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
        return f"{x:.{digits}f}".rstrip("0").rstrip(".") if abs(x) < 1e8 else f"{x:.6e}"
    return str(x)


def safe_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Field '{field_name}' must be a real number; got {value!r}.") from exc


def normalize_problem_name(name: str) -> str:
    key = str(name).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "12_1": "ex12_1",
        "12_2": "ex12_2",
        "12_3": "ex12_3",
        "12_4": "ex12_4",
        "example_12_1": "ex12_1",
        "example_12_2": "ex12_2",
        "example_12_3": "ex12_3",
        "example_12_4": "ex12_4",
        "menu": "menu",
    }
    return aliases.get(key, key)


def prompt_float(label: str, *, allow_blank: bool = False, default: float | None = None) -> float | None:
    while True:
        suffix = ""
        if default is not None:
            suffix += f" [default {fmt(default)}]"
        if allow_blank:
            suffix += " [blank allowed]"
        raw = input(f"{label}{suffix}: ").strip()
        if raw == "":
            if default is not None:
                return float(default)
            if allow_blank:
                return None
        try:
            return float(raw)
        except ValueError:
            print(f"Could not parse a number from {raw!r}. Try again.")
