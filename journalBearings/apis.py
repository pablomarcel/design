from __future__ import annotations

from typing import Any, Dict, Optional

from app import JournalBearingApp


class JournalBearingAPI:
    def __init__(self) -> None:
        self.app = JournalBearingApp()

    def solve_problem(
        self,
        problem: str,
        inputs: Dict[str, Any],
        chart_inputs: Optional[Dict[str, Any]] = None,
        interactive: bool = False,
    ) -> Dict[str, Any]:
        return self.app.solve(
            problem=problem,
            inputs=inputs,
            chart_inputs=chart_inputs,
            interactive=interactive,
        )
