
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console

try:
    from .apis import SolverAPI
    from .in_out import StaticFailureIO
    from .utils import DisplayUtils
except ImportError:  # pragma: no cover
    from apis import SolverAPI
    from in_out import StaticFailureIO
    from utils import DisplayUtils


class StaticFailureApp:
    """Application orchestrator for the static_failure package."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.io = StaticFailureIO()
        self.api = SolverAPI()
        self.display = DisplayUtils(console=self.console)

    def solve_payload(
        self,
        payload: dict[str, Any],
        outfile: str | Path | None = None,
        pretty: bool = True,
        show: bool = False,
    ) -> dict[str, Any]:
        result = self.api.solve(payload)
        written = self.io.save_json(result, outfile=outfile, pretty=pretty)
        if written is not None:
            result["output_file"] = str(written)
        if show:
            self.render_result(result)
        return result

    def solve_file(
        self,
        infile: str | Path,
        outfile: str | Path | None = None,
        pretty: bool = True,
        show: bool = False,
    ) -> dict[str, Any]:
        payload = self.io.load_json(infile)
        return self.solve_payload(payload, outfile=outfile, pretty=pretty, show=show)

    def render_result(self, result: dict[str, Any]) -> None:
        self.display.print_banner(result.get("title", "Static Failure Result"))
        self.display.print_key_value_block("Meta", result.get("meta", {}))
        self.display.print_key_value_block("Material", result.get("material", {}))
        inputs = result.get("inputs", {})
        input_preview = {k: v for k, v in inputs.items() if k not in {"stress_states"}}
        self.display.print_key_value_block("Inputs", input_preview)

        results = result.get("results", {})

        critical_section = results.get("critical_section")
        if critical_section:
            self.display.print_nested_mapping("Critical Section", critical_section)

        strength_predictions = results.get("strength_predictions")
        if strength_predictions:
            self.display.print_nested_mapping("Strength Predictions", strength_predictions)

        selected_candidate = results.get("selected_candidate")
        if selected_candidate:
            self.display.print_nested_mapping("Selected Candidate", selected_candidate)

        summary_rows = results.get("summary_table", [])
        if summary_rows:
            df = pd.DataFrame(summary_rows)
            self.display.print_dataframe(df, title="Factor of Safety Summary")
