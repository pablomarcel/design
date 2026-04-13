from __future__ import annotations

import csv
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

ROOT_DIR = Path(__file__).resolve().parent
DATA_CANDIDATES = [ROOT_DIR / 'data', ROOT_DIR.parent / 'data', Path('/mnt/data')]


def find_data_file(filename: str) -> Path:
    for base in DATA_CANDIDATES:
        candidate = base / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f'Could not locate data file: {filename}')


def load_json(path: Path) -> Dict[str, Any]:
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


SAFE_NAMES = {
    'pi': math.pi,
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'asin': math.asin,
    'acos': math.acos,
    'atan': math.atan,
    'atan2': math.atan2,
    'degrees': math.degrees,
    'radians': math.radians,
    'abs': abs,
    'min': min,
    'max': max,
}


def _normalize_expression(expr: str) -> str:
    normalized = expr.strip()
    if '=' in normalized:
        normalized = normalized.split('=', 1)[1].strip()
    normalized = normalized.replace('^', '**')
    return normalized


def evaluate_expression(expr: str, variables: Mapping[str, float]) -> float:
    compiled = _normalize_expression(expr)
    scope = dict(SAFE_NAMES)
    scope.update(variables)
    return float(eval(compiled, {'__builtins__': {}}, scope))


def magnitude_2d(x: float, y: float) -> float:
    return math.hypot(x, y)


def angle_deg_from_x(x: float, y: float) -> float:
    return math.degrees(math.atan2(y, x))


def format_json(data: Mapping[str, Any], pretty: bool = True) -> str:
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, separators=(',', ':'), ensure_ascii=False)


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Mapping[str, Any], pretty: bool = True) -> None:
    ensure_parent_dir(path)
    with path.open('w', encoding='utf-8') as f:
        f.write(format_json(data, pretty=pretty))
        f.write('\n')


def coerce_path(path_like: str | Path, base_dir: Optional[Path] = None) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    if base_dir is not None:
        candidate = base_dir / path
        if candidate.exists() or not path.exists():
            return candidate
    return path


def parse_decimal_or_fraction(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(' ', '')
    if '-' in text and '/' in text:
        whole, frac = text.split('-', 1)
        return float(int(whole) + Fraction(frac))
    if '/' in text:
        return float(Fraction(text))
    return float(text)


class ValidationError(ValueError):
    pass
