from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

try:
    from .utils import ROOT_DIR, coerce_path, load_json, write_json
except ImportError:  # pragma: no cover
    from utils import ROOT_DIR, coerce_path, load_json, write_json


class IOHandler:
    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = Path(root_dir) if root_dir else ROOT_DIR
        self.in_dir = self.root_dir / "in"
        self.out_dir = self.root_dir / "out"

    def read_input_file(self, infile: str | Path) -> Dict[str, Any]:
        path = coerce_path(infile, base_dir=self.in_dir)
        return load_json(path)

    def write_output_file(self, outfile: str | Path, payload: Mapping[str, Any], pretty: bool = True) -> Path:
        path = coerce_path(outfile, base_dir=self.out_dir)
        write_json(path, payload, pretty=pretty)
        return path
