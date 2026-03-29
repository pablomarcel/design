from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from core import BearingInputs, ManualChartInputs, ManualChartProvider, PROBLEM_REGISTRY
from utils import normalize_problem_name


class JournalBearingApp:
    def solve(
        self,
        problem: str,
        inputs: Dict[str, Any],
        chart_inputs: Optional[Dict[str, Any]] = None,
        interactive: bool = False,
    ) -> Dict[str, Any]:
        key = normalize_problem_name(problem)
        if key not in PROBLEM_REGISTRY:
            known = ", ".join(sorted(PROBLEM_REGISTRY))
            raise ValueError(f"Unknown problem '{problem}'. Known problems: {known}")
        input_obj = BearingInputs.from_mapping(inputs)
        chart_obj = ManualChartInputs.from_mapping(chart_inputs)
        provider = ManualChartProvider(chart_obj, interactive=interactive)
        solver_cls = PROBLEM_REGISTRY[key]
        solver = solver_cls(input_obj, provider)
        result = solver.solve()
        return asdict(result)
