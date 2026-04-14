from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .utils import dump_json, json_text, load_json, package_root
except ImportError:  # pragma: no cover
    from utils import dump_json, json_text, load_json, package_root


class IOManager:
    """Handle file-based inputs and outputs for the fatigue_failure package."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else package_root()
        self.in_dir = self.root / "in"
        self.out_dir = self.root / "out"

    def resolve_input_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        if candidate.exists():
            return candidate.resolve()
        in_candidate = self.in_dir / candidate
        if in_candidate.exists():
            return in_candidate.resolve()
        return candidate.resolve()

    def resolve_output_path(self, path: str | Path | None) -> Path | None:
        if path is None:
            return None
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        if candidate.parent == Path("."):
            return self.out_dir / candidate
        return candidate

    def read_json(self, path: str | Path) -> Any:
        return load_json(self.resolve_input_path(path))

    def write_json(self, data: Any, path: str | Path | None, pretty: bool = True) -> Path | None:
        resolved = self.resolve_output_path(path)
        if resolved is None:
            return None
        dump_json(data, resolved, pretty=pretty)
        return resolved

    def json_text(self, data: Any, pretty: bool = True) -> str:
        return json_text(data, pretty=pretty)
