from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .apis import FlexibleElementsAPI
    from .utils import PathHelper, dump_json, load_json, sanitize_for_json
except ImportError:  # pragma: no cover
    from apis import FlexibleElementsAPI
    from utils import PathHelper, dump_json, load_json, sanitize_for_json


class FlexibleElementsApp:
    def __init__(self, anchor_file: str):
        self.paths = PathHelper(anchor_file)
        self.api = FlexibleElementsAPI(self.paths.data_dir)

    def solve(self, solve_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.api.solve(solve_path, payload)
        return sanitize_for_json(result)

    def solve_file(self, infile_name: str, outfile_name: str | None = None) -> tuple[dict[str, Any], Path | None]:
        in_path = self.paths.in_dir / infile_name
        payload = load_json(in_path)
        solve_path = payload["solve_path"]
        result = self.solve(solve_path, payload)
        out_path = None
        if outfile_name:
            out_path = self.paths.out_dir / outfile_name
            dump_json(result, out_path)
        return result, out_path

    def write_output(self, result: dict[str, Any], outfile_name: str) -> Path:
        out_path = self.paths.out_dir / outfile_name
        dump_json(result, out_path)
        return out_path
