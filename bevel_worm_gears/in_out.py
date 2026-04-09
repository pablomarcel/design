from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    from .utils import dump_json, load_json
except ImportError:  # pragma: no cover
    from utils import dump_json, load_json


def package_root() -> Path:
    return Path(__file__).resolve().parent


def in_dir() -> Path:
    return package_root() / "in"


def out_dir() -> Path:
    return package_root() / "out"


def data_dir() -> Path:
    return package_root() / "data"


def read_problem(infile: str | Path) -> Dict[str, Any]:
    path = Path(infile)
    if not path.is_absolute():
        path = in_dir() / path
    return load_json(path)


def write_solution(payload: Dict[str, Any], outfile: str | Path) -> Path:
    path = Path(outfile)
    if not path.is_absolute():
        path = out_dir() / path
    dump_json(path, payload)
    return path
