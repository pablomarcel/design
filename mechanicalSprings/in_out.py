from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from utils import dump_json, ensure_dir, load_json


class IOHandler:
    def read_json(self, path: str | Path) -> Dict[str, Any]:
        return load_json(Path(path))

    def write_json(self, path: str | Path, payload: Dict[str, Any]) -> None:
        dump_json(Path(path), payload)

    def write_csv_rows(self, path: str | Path, rows: List[Dict[str, Any]]) -> None:
        out = Path(path)
        ensure_dir(out.parent)
        if not rows:
            with out.open("w", encoding="utf-8") as f:
                f.write("")
            return
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
