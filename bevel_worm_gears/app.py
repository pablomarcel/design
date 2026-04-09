from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    from .apis import BevelWormGearAPI
    from .in_out import data_dir, read_problem, write_solution
except ImportError:  # pragma: no cover
    from apis import BevelWormGearAPI
    from in_out import data_dir, read_problem, write_solution


class BevelWormGearApp:
    def __init__(self):
        self.api = BevelWormGearAPI(data_dir())

    def run_file(self, infile: str | Path, outfile: str | Path) -> Path:
        problem = read_problem(infile)
        result = self.api.solve(problem)
        return write_solution(result, outfile)

    def solve_problem(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.solve(problem)
