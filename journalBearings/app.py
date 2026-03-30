from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from core import BearingInputs, FiniteJournalBearingTable, PROBLEM_REGISTRY
from utils import normalize_problem_name


class JournalBearingApp:
    def __init__(self, table_path: str | Path | None = None) -> None:
        if table_path is None:
            table_path = Path(__file__).resolve().parent / "data" / "finite_journal_bearing.csv"
        self.table = FiniteJournalBearingTable(table_path)

    def _preprocess_inputs(self, problem: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(inputs)
        if problem == 'boundary_lubricated_bearing':
            if 'dj' in data and 'r' not in data:
                data['r'] = float(data['dj']) / 2.0
            data.setdefault('c', 1.0)
            data.setdefault('N', 1.0)
            data.setdefault('mu', None)
            data.setdefault('Ps', 0.0)
            data.setdefault('unit_system', 'ips')
        return data

    def solve(self, problem: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        key = normalize_problem_name(problem)
        if key not in PROBLEM_REGISTRY:
            known = ", ".join(sorted(PROBLEM_REGISTRY))
            raise ValueError(f"Unknown problem '{problem}'. Known problems: {known}")
        input_obj = BearingInputs.from_mapping(self._preprocess_inputs(key, inputs))
        solver_cls = PROBLEM_REGISTRY[key]
        solver = solver_cls(input_obj, self.table)
        payload = asdict(solver.solve())
        payload["session"] = {
            "table_path": str(self.table.csv_path),
            "lookup_mode": "automatic",
        }
        return payload
