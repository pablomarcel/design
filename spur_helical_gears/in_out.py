from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils import IN_DIR, OUT_DIR, ensure_out_dir


class IOHandler:
    def __init__(self, in_dir: Path | None = None, out_dir: Path | None = None) -> None:
        self.in_dir = Path(in_dir) if in_dir else IN_DIR
        self.out_dir = Path(out_dir) if out_dir else OUT_DIR
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def load_json(self, infile: str | Path) -> dict[str, Any]:
        path = Path(infile)
        if not path.is_absolute():
            candidate = self.in_dir / path
            path = candidate if candidate.exists() else path
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_json(self, data: dict[str, Any], outfile: str | Path) -> Path:
        ensure_out_dir()
        path = Path(outfile)
        if not path.is_absolute():
            path = self.out_dir / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return path
