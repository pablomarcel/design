from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .apis import SolverAPI
    from .in_out import IOManager
except ImportError:  # pragma: no cover
    from apis import SolverAPI
    from in_out import IOManager


class FatigueFailureApp:
    """Orchestrator for payload-based and file-based fatigue-failure solves."""

    def __init__(self, root: str | Path | None = None, data_dir: str | None = None) -> None:
        self.io = IOManager(root=root)
        self.api = SolverAPI(data_dir=data_dir or str(self.io.root / "data"))

    def solve_payload(self, payload: dict[str, Any], outfile: str | Path | None = None, pretty: bool = True) -> dict[str, Any]:
        result = self.api.solve(payload)
        self.io.write_json(result, outfile, pretty=pretty)
        return result

    def solve_file(self, infile: str | Path, outfile: str | Path | None = None, pretty: bool = True) -> dict[str, Any]:
        payload = self.io.read_json(infile)
        return self.solve_payload(payload, outfile=outfile, pretty=pretty)
