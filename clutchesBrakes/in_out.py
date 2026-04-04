from __future__ import annotations

from pathlib import Path
from typing import Any

from utils import dump_json, load_json


class IOManager:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.in_dir = base_dir / "in"
        self.out_dir = base_dir / "out"

    def resolve_infile(self, name: str | None) -> Path | None:
        if name is None:
            return None
        path = Path(name)
        return path if path.is_absolute() else self.in_dir / path

    def resolve_outfile(self, name: str | None) -> Path | None:
        if name is None:
            return None
        path = Path(name)
        return path if path.is_absolute() else self.out_dir / path

    def read_json(self, name: str) -> Any:
        return load_json(self.resolve_infile(name))

    def write_json(self, data: Any, name: str) -> Path:
        outpath = self.resolve_outfile(name)
        dump_json(data, outpath)
        return outpath
