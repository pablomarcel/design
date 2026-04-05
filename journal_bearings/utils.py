from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict
import json
import math
import re


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
    with path.open('w', encoding='utf-8') as f:
        json.dump(to_plain_data(data), f, indent=2, sort_keys=False)
        f.write('\n')


def load_json(path: str | Path) -> Dict[str, Any]:
    with Path(path).open('r', encoding='utf-8') as f:
        return json.load(f)


def fmt(x: Any, digits: int = 6) -> str:
    if x is None:
        return '-'
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return str(x)
        ax = abs(x)
        if ax != 0.0 and (ax < 1e-4 or ax >= 1e8):
            return f"{x:.6e}"
        return f"{x:.{digits}f}".rstrip('0').rstrip('.')
    return str(x)


def safe_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Field '{field_name}' must be a real number; got {value!r}.") from exc


def normalize_problem_name(name: str) -> str:
    key = str(name).strip().lower().replace('-', '_').replace(' ', '_')
    aliases = {
        '12_1': 'minimum_film_thickness',
        '12_2': 'coefficient_of_friction',
        '12_3': 'volumetric_flow_rate',
        '12_4': 'maximum_film_pressure',
        '12_5': 'self_contained_steady_state',
        '12_6': 'pressure_fed_circumferential',
        'example_12_1': 'minimum_film_thickness',
        'example_12_2': 'coefficient_of_friction',
        'example_12_3': 'volumetric_flow_rate',
        'example_12_4': 'maximum_film_pressure',
        'example_12_5': 'self_contained_steady_state',
        'example_12_6': 'pressure_fed_circumferential',
        'example_12_7': 'boundary_lubricated_bearing',
        '12_8': 'boundary_lubricated_temperature_rise',
        'example_12_8': 'boundary_lubricated_temperature_rise',
        'boundary_lubricated_temperature_rise_bearing': 'boundary_lubricated_temperature_rise',
        'boundary_lubricated_temperature_rise': 'boundary_lubricated_temperature_rise',
        'boundary_lubricated_with_temperature_rise': 'boundary_lubricated_temperature_rise',
        'minimumfilmthickness': 'minimum_film_thickness',
        'coefficientoffriction': 'coefficient_of_friction',
        'volumetricflowrate': 'volumetric_flow_rate',
        'maximumfilmpressure': 'maximum_film_pressure',
        'selfcontainedsteadystate': 'self_contained_steady_state',
        'self_contained': 'self_contained_steady_state',
        'steady_state_self_contained': 'self_contained_steady_state',
        'steady_state_conditions_in_self_contained_bearings': 'self_contained_steady_state',
        'temperaturerise': 'temperature_rise',
        'temp_rise': 'temperature_rise',
        'temperature': 'temperature_rise',
        'pressure_fed': 'pressure_fed_circumferential',
        'pressurefed': 'pressure_fed_circumferential',
        'pressure_fed_bearing': 'pressure_fed_circumferential',
        'pressure_fed_bearings': 'pressure_fed_circumferential',
        'pressure_fed_circumferential_bearing': 'pressure_fed_circumferential',
        'boundary_lubricated': 'boundary_lubricated_bearing',
        'boundary_lubricated_bearings': 'boundary_lubricated_bearing',
        'boundarylubricatedbearing': 'boundary_lubricated_bearing',
        'circumferential_pressure_fed': 'pressure_fed_circumferential',
        'friction': 'coefficient_of_friction',
        'flow': 'volumetric_flow_rate',
        'pressure': 'maximum_film_pressure',
    }
    return aliases.get(key, key)


def normalize_oil_grade(name: str) -> str:
    raw = str(name).strip().lower()
    raw = raw.replace('sae', '').strip()
    raw = re.sub(r'\s+', '', raw)
    return raw
