from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .apis import SolverAPI
    from .in_out import IOHandler
    from .utils import OUT_DIR
except ImportError:  # pragma: no cover
    from apis import SolverAPI
    from in_out import IOHandler
    from utils import OUT_DIR


class ScrewsFastenersApp:
    def __init__(self) -> None:
        self.io = IOHandler()

    def solve_payload(self, payload: Dict[str, Any], outfile: Optional[str] = None, pretty: bool = True) -> Dict[str, Any]:
        result = SolverAPI.solve(payload)
        if outfile:
            self.io.write_json(result, outfile, pretty=pretty)
        return result

    def solve_file(self, infile: str, outfile: Optional[str] = None, pretty: bool = True) -> Dict[str, Any]:
        payload = self.io.read_json(infile)
        if outfile is None:
            stem = Path(infile).stem
            outfile = f"{stem}_out.json"
        return self.solve_payload(payload, outfile=outfile, pretty=pretty)

    @property
    def out_dir(self) -> Path:
        return OUT_DIR
