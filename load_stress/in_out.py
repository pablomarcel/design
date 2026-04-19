from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(data: dict[str, Any], outfile: Path, pretty: bool = True) -> Path:
    ensure_directory(outfile.parent)
    with outfile.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2 if pretty else None)
        f.write("\n")
    return outfile
