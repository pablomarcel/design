from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

try:
    from .apis import SolverAPI
    from .in_out import IOHandler
except ImportError:  # pragma: no cover
    from apis import SolverAPI
    from in_out import IOHandler


class WeldingBondingApp:
    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.io = IOHandler(root_dir=root_dir)
        self.api = SolverAPI()

    def solve_payload(self, payload: Mapping[str, Any], outfile: str | Path | None = None, pretty: bool = True) -> Dict[str, Any]:
        result = self.api.solve(payload)
        if outfile is not None:
            self.io.write_output_file(outfile, result, pretty=pretty)
        return result

    def solve_file(self, infile: str | Path, outfile: str | Path | None = None, pretty: bool = True) -> Dict[str, Any]:
        payload = self.io.read_input_file(infile)
        return self.solve_payload(payload, outfile=outfile, pretty=pretty)
