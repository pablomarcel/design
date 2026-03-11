from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}

    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object/dict in file: {path}")
    return data


def save_json(payload: dict[str, Any], path: str | None) -> None:
    if not path:
        return

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=False, ensure_ascii=False)
        f.write("\n")