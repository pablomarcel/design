from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app import JournalBearingApp


class JournalBearingAPI:
    def __init__(self, table_path: str | Path | None = None) -> None:
        self.app = JournalBearingApp(table_path=table_path)

    def solve_problem(self, problem: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return self.app.solve(problem=problem, inputs=inputs)
