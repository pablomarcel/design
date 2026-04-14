from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, List, Sequence, Tuple


class FatigueFailureError(Exception):
    """Base application error for the fatigue_failure package."""


class ValidationError(FatigueFailureError):
    """Raised when user input is incomplete or inconsistent."""


class DataLookupError(FatigueFailureError):
    """Raised when required digitized data cannot be found or used."""


class RangeError(FatigueFailureError):
    """Raised when a numeric value is outside an allowed range."""


_KPSI_TO_MPA = 6.894757293168361
_IN_TO_MM = 25.4


def package_root() -> Path:
    return Path(__file__).resolve().parent


def coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def normalize_processing(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).strip().upper()


def normalize_steel_name(value: str | int | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text.startswith("SAE"):
        text = text.replace("SAE", "", 1).strip()
    if text.startswith("AISI"):
        text = text.replace("AISI", "", 1).strip()
    return text


def normalize_surface_finish(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    aliases = {
        "ground": "ground",
        "machined": "machined or cold-drawn",
        "machined or cold drawn": "machined or cold-drawn",
        "machined or cold-drawn": "machined or cold-drawn",
        "cold drawn": "machined or cold-drawn",
        "cold-drawn": "machined or cold-drawn",
        "machined cold drawn": "machined or cold-drawn",
        "hot rolled": "hot-rolled",
        "hot-rolled": "hot-rolled",
        "as forged": "as-forged",
        "as-forged": "as-forged",
    }
    return aliases.get(text, text)


def normalize_shape_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "solid_round": "solid_round",
        "round": "solid_round",
        "solidround": "solid_round",
        "rectangle": "rectangle",
        "rectangular": "rectangle",
        "i_shape": "i_shape",
        "ishape": "i_shape",
        "i_beam": "i_shape",
        "channel": "channel",
    }
    return aliases.get(text, text)


def normalize_axis_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "1_1": "axis_1_1",
        "axis_1_1": "axis_1_1",
        "axis1_1": "axis_1_1",
        "axis11": "axis_1_1",
        "2_2": "axis_2_2",
        "axis_2_2": "axis_2_2",
        "axis2_2": "axis_2_2",
        "axis22": "axis_2_2",
    }
    return aliases.get(text, text)


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(data: Any, path: str | Path, pretty: bool = True) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        if pretty:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        else:
            json.dump(data, handle, separators=(",", ":"), ensure_ascii=False)


def json_text(data: Any, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def log10(value: float) -> float:
    if value <= 0:
        raise RangeError(f"log10 is undefined for non-positive value {value!r}.")
    return math.log10(value)


def ensure_positive(name: str, value: float | None) -> float:
    if value is None:
        raise ValidationError(f"'{name}' is required.")
    if value <= 0:
        raise ValidationError(f"'{name}' must be positive. Got {value!r}.")
    return float(value)


def ensure_at_least(name: str, value: float | None, minimum: float) -> float:
    numeric = ensure_positive(name, value)
    if numeric < minimum:
        raise ValidationError(f"'{name}' must be at least {minimum}. Got {numeric!r}.")
    return numeric


def sorted_pairs(xs: Sequence[float], ys: Sequence[float]) -> List[Tuple[float, float]]:
    if len(xs) != len(ys):
        raise ValidationError("Interpolation data lengths do not match.")
    if len(xs) < 2:
        raise ValidationError("At least two interpolation points are required.")
    pairs = sorted((float(x), float(y)) for x, y in zip(xs, ys))
    unique_pairs: list[tuple[float, float]] = []
    for x, y in pairs:
        if unique_pairs and math.isclose(unique_pairs[-1][0], x, rel_tol=0.0, abs_tol=1e-12):
            unique_pairs[-1] = (x, y)
        else:
            unique_pairs.append((x, y))
    return unique_pairs


def linear_interpolate(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    points = sorted_pairs(xs, ys)
    x = float(x)
    if x < points[0][0] or x > points[-1][0]:
        raise RangeError(
            f"Interpolation value {x} is outside the available range [{points[0][0]}, {points[-1][0]}]."
        )
    for x_i, y_i in points:
        if math.isclose(x, x_i, rel_tol=0.0, abs_tol=1e-12):
            return y_i
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    raise RangeError(f"Unable to interpolate value {x}.")


def relative_error_percent(actual: float, reference: float) -> float | None:
    if reference == 0:
        return None
    return 100.0 * (actual - reference) / reference


def safe_round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def summarize_matches(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "uns_no",
        "sae_aisi_no",
        "processing",
        "tensile_strength_MPa",
        "tensile_strength_kpsi",
        "yield_strength_MPa",
        "yield_strength_kpsi",
        "brinell_hardness",
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append({key: row.get(key) for key in keys if key in row})
    return result


def kpsi_to_mpa(value: float) -> float:
    return float(value) * _KPSI_TO_MPA


def mpa_to_kpsi(value: float) -> float:
    return float(value) / _KPSI_TO_MPA


def mm_to_in(value: float) -> float:
    return float(value) / _IN_TO_MM


def in_to_mm(value: float) -> float:
    return float(value) * _IN_TO_MM


def safe_eval_expression(expression: str, variables: dict[str, float]) -> float:
    allowed = {"sqrt": math.sqrt, "pi": math.pi, "abs": abs}
    allowed.update({k: float(v) for k, v in variables.items()})
    try:
        return float(eval(expression, {"__builtins__": {}}, allowed))
    except NameError as exc:
        raise ValidationError(f"Missing parameter while evaluating expression {expression!r}: {exc}") from exc
    except Exception as exc:
        raise ValidationError(f"Unable to evaluate expression {expression!r}: {exc}") from exc