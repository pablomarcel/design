from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

try:
    from .utils import DataLookupError
except ImportError:  # pragma: no cover
    from utils import DataLookupError


class CsvRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def read_csv(self, filename: str) -> list[dict[str, str]]:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def _normalize(self, value: Any) -> str:
        return str(value).strip().lower()

    def find_one(self, filename: str, **criteria: Any) -> dict[str, str]:
        rows = self.read_csv(filename)
        normalized = {k: self._normalize(v) for k, v in criteria.items()}
        for row in rows:
            ok = True
            for key, expected in normalized.items():
                got = self._normalize(row.get(key, ""))
                if got != expected:
                    ok = False
                    break
            if ok:
                return row
        raise DataLookupError(
            f"No row found in {filename} for criteria: "
            + ", ".join(f"{k}={v!r}" for k, v in criteria.items())
        )

    def list_column_floats(self, filename: str, column: str, *, nonblank_only: bool = True) -> list[float]:
        values: list[float] = []
        for row in self.read_csv(filename):
            raw = row.get(column, "")
            if raw is None or raw == "":
                if nonblank_only:
                    continue
            values.append(float(raw))
        return values
