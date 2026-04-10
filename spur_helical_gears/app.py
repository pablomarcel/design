from __future__ import annotations

from typing import Any

from apis import SolverFactory
from in_out import IOHandler


class SpurHelicalGearsApp:
    def __init__(self) -> None:
        self.io = IOHandler()

    def run_problem(self, problem: dict[str, Any]) -> dict[str, Any]:
        solver = SolverFactory.create(problem)
        return solver.solve()

    def run_from_file(self, infile: str, outfile: str | None = None) -> tuple[dict[str, Any], str | None]:
        problem = self.io.load_json(infile)
        result = self.run_problem(problem)
        saved_path = None
        if outfile:
            saved_path = str(self.io.save_json(result, outfile))
        return result, saved_path
