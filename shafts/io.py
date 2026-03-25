from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .utils import dumps_pretty, ensure_dir, safe_name
except ImportError:  # pragma: no cover - local package execution shim
    from utils import dumps_pretty, ensure_dir, safe_name


PKG_DIR = Path(__file__).resolve().parent
IN_DIR = ensure_dir(PKG_DIR / "in")
OUT_DIR = ensure_dir(PKG_DIR / "out")


class ShaftIO:
    def __init__(self, in_dir: Path | None = None, out_dir: Path | None = None) -> None:
        self.in_dir = ensure_dir(in_dir or IN_DIR)
        self.out_dir = ensure_dir(out_dir or OUT_DIR)

    def read_json(self, path: str | Path) -> dict[str, Any]:
        p = Path(path)
        candidates = []
        if p.is_absolute():
            candidates = [p]
        else:
            candidates = [Path.cwd() / p, self.in_dir / p, p]
        for cand in candidates:
            if cand.exists():
                with cand.open("r", encoding="utf-8") as fh:
                    return json.load(fh)
        searched = ", ".join(str(c) for c in candidates)
        raise FileNotFoundError(f"Could not find input JSON. Looked in: {searched}")

    def write_json(self, data: dict[str, Any], filename: str | None = None) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = filename or f"shaft_result_{stamp}.json"
        out_path = self.out_dir / safe_name(name)
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return out_path

    def print_result(self, data: dict[str, Any]) -> None:
        print(dumps_pretty(data))
