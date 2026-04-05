from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import csv
import json


PKG_DIR = Path(__file__).resolve().parent
DATA_DIR = PKG_DIR / "data"
IN_DIR = PKG_DIR / "in"
OUT_DIR = PKG_DIR / "out"


def resolve_infile(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.exists():
        return p
    candidate = IN_DIR / name_or_path
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Could not find input file: {name_or_path}")


def resolve_outfile(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.is_absolute():
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR / name_or_path


def load_json(name_or_path: str) -> Dict[str, Any]:
    path = resolve_infile(name_or_path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(payload: Dict[str, Any], name_or_path: str) -> Path:
    path = resolve_outfile(name_or_path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return path


def load_csv_dicts(filename: str):
    path = DATA_DIR / filename
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
