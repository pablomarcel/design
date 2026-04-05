from __future__ import annotations

from typing import Any, Dict

from app import SpringApplication


class MechanicalSpringsAPI:
    def __init__(self) -> None:
        self.app = SpringApplication()

    def solve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.app.solve(payload)
