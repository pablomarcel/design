from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .utils import DisplayUtils
except ImportError:  # pragma: no cover
    from utils import DisplayUtils


class StaticFailureIO:
    """Handles package-local file loading and saving."""

    def __init__(self, package_root: Path | None = None) -> None:
        self.package_root = package_root or Path(__file__).resolve().parent
        self.in_dir = self.package_root / "in"
        self.out_dir = self.package_root / "out"
        self.in_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def resolve_input_path(self, infile: str | Path) -> Path:
        path = Path(infile)
        if path.is_absolute() and path.exists():
            return path
        candidates = [
            Path.cwd() / path,
            self.in_dir / path,
            self.package_root / path,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise FileNotFoundError(f"Input file not found: {infile}")

    def resolve_output_path(self, outfile: str | Path | None) -> Path | None:
        if outfile is None:
            return None
        path = Path(outfile)
        if path.is_absolute():
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        if path.parent == Path('.'):
            resolved = self.out_dir / path
            resolved.parent.mkdir(parents=True, exist_ok=True)
            return resolved
        resolved = (Path.cwd() / path).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def load_json(self, infile: str | Path) -> dict[str, Any]:
        path = self.resolve_input_path(infile)
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_json(self, payload: dict[str, Any], outfile: str | Path | None, pretty: bool = True) -> Path | None:
        path = self.resolve_output_path(outfile)
        if path is None:
            return None
        serializable = DisplayUtils.deep_round(payload, digits=12)
        with path.open("w", encoding="utf-8") as f:
            if pretty:
                json.dump(serializable, f, indent=2, ensure_ascii=False)
            else:
                json.dump(serializable, f, separators=(",", ":"), ensure_ascii=False)
        return path
