from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from utils import ensure_dir, project_root, round_floats


class IOHandler:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or project_root()
        self.in_dir = self.base_dir / "in"
        self.out_dir = self.base_dir / "out"
        ensure_dir(self.in_dir)
        ensure_dir(self.out_dir)

    def load_json(self, infile: str | Path) -> Dict[str, Any]:
        path = Path(infile)
        if not path.is_absolute():
            path = self.in_dir / path
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_json(self, obj: Dict[str, Any], outfile: str | Path) -> Path:
        path = Path(outfile)
        if not path.is_absolute():
            path = self.out_dir / path
        ensure_dir(path.parent)
        with path.open("w", encoding="utf-8") as f:
            json.dump(round_floats(obj, 8), f, indent=2, ensure_ascii=False)
        return path
