from __future__ import annotations

from typing import Any, Dict

from app import ClutchesBrakesApp


class ClutchesBrakesAPI:
    def __init__(self) -> None:
        self.app = ClutchesBrakesApp()

    def solve(self, problem_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.app.solve(problem_type, payload).to_dict()

    def solve_from_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.app.solve_from_payload(payload).to_dict()
