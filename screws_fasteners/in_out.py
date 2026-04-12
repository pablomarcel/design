from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    from .utils import IN_DIR, OUT_DIR, dump_json, ensure_dirs
except ImportError:  # pragma: no cover
    from utils import IN_DIR, OUT_DIR, dump_json, ensure_dirs


class IOHandler:
    def __init__(self) -> None:
        ensure_dirs()

    def input_path(self, infile: str) -> Path:
        path = Path(infile)
        if not path.is_absolute():
            path = IN_DIR / infile
        return path

    def output_path(self, outfile: str) -> Path:
        path = Path(outfile)
        if not path.is_absolute():
            path = OUT_DIR / outfile
        return path

    def read_json(self, infile: str) -> Dict[str, Any]:
        path = self.input_path(infile)
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, data: Dict[str, Any], outfile: str, pretty: bool = True) -> Path:
        path = self.output_path(outfile)
        dump_json(data, path, pretty=pretty)
        return path
