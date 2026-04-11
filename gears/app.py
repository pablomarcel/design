from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from apis import GearForceAPI
from in_out import IOHandler
from utils import ReportBuilder


class GearForceApp:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.io = IOHandler(base_dir=base_dir)
        self.api = GearForceAPI()
        self.report = ReportBuilder()

    def run_from_file(self, infile: str, outfile: str | None = None, pretty: bool = True) -> Dict[str, Any]:
        problem = self.io.load_json(infile)
        result = self.api.solve(problem)
        if outfile:
            self.io.save_json(result, outfile)
        if pretty:
            self.print_report(result)
        return result

    def run_from_dict(self, problem: Dict[str, Any], outfile: str | None = None, pretty: bool = True) -> Dict[str, Any]:
        result = self.api.solve(problem)
        if outfile:
            self.io.save_json(result, outfile)
        if pretty:
            self.print_report(result)
        return result

    def print_report(self, result: Dict[str, Any]) -> None:
        self.report.print_title(result.get("title", result.get("problem", "Gear force analysis")))
        derived = result.get("derived", {})
        outputs = result.get("outputs", {})
        self.report.print_kv_table("Derived", derived)

        if "mesh_forces" in result:
            rows = []
            for item in result["mesh_forces"]:
                rows.append(
                    {
                        "mesh": item["mesh"],
                        "tangential_N": item["tangential_magnitude_N"],
                        "radial_N": item["radial_magnitude_N"],
                        "total_N": item["total_tooth_force_N"],
                        "vector_N": item["vector_N"],
                    }
                )
            self.report.print_rows(
                "Mesh forces",
                rows,
                ["mesh", "tangential_N", "radial_N", "total_N", "vector_N"],
            )

        reactions = outputs.get("reactions", {})
        if reactions:
            rows = [{"support": k, **v} for k, v in reactions.items()]
            self.report.print_rows("Support reactions", rows, ["support", "x", "y", "z"])

        moments = outputs.get("solved_moments", {})
        if moments:
            self.report.print_kv_table("Solved moments", moments)
