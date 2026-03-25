from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

try:
    from .apis import ShaftAPI
    from .io import ShaftIO
except ImportError:  # pragma: no cover - local package execution shim
    from apis import ShaftAPI

    _here = Path(__file__).resolve().parent
    _io_path = _here / "io.py"
    _spec = importlib.util.spec_from_file_location("shafts_local_io", _io_path)
    if _spec is None or _spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Could not load local io module from {_io_path}")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ShaftIO = _mod.ShaftIO


class ShaftApp:
    def __init__(self, io: ShaftIO | None = None, api: ShaftAPI | None = None) -> None:
        self.io = io or ShaftIO()
        self.api = api or ShaftAPI()

    def run_request(self, calc: str, payload: dict[str, Any], save: bool = False, outfile: str | None = None) -> dict[str, Any]:
        result = self.api.dispatch(calc, payload)
        if save:
            path = self.io.write_json(result, outfile)
            result["saved_to"] = str(path)
        return result

    def run_json(self, infile: str | Path, save: bool = True, outfile: str | None = None) -> dict[str, Any]:
        data = self.io.read_json(infile)
        calc = data["calculation"]
        payload = data.get("payload", {})
        return self.run_request(calc, payload, save=save, outfile=outfile)
