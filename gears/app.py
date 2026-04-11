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
        validation = result.get("validation", {})

        self.report.print_mapping_sections("Derived", derived)

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
                        "vector_mag_N": item.get("vector_magnitude_N"),
                    }
                )
            self.report.print_rows(
                "Mesh forces",
                rows,
                ["mesh", "tangential_N", "radial_N", "total_N", "vector_N", "vector_mag_N"],
            )

        if "resultant_force_on_selected_gear_N" in outputs:
            self.report.print_kv_table(
                "Spur resultant summary",
                {
                    "resultant_force_on_selected_gear_N": outputs.get("resultant_force_on_selected_gear_N"),
                    "resultant_force_on_selected_gear_magnitude_N": outputs.get("resultant_force_on_selected_gear_magnitude_N"),
                    "shaft_reaction_at_center_N": outputs.get("shaft_reaction_at_center_N"),
                    "shaft_reaction_resultant_N": outputs.get("shaft_reaction_resultant_N"),
                },
            )

        reactions = outputs.get("reactions", {})
        reaction_magnitudes = outputs.get("reaction_magnitudes", {})
        if reactions:
            rows = []
            for support, comps in reactions.items():
                mag = reaction_magnitudes.get(support, {})
                rows.append(
                    {
                        "support": support,
                        "x": comps.get("x", 0.0),
                        "y": comps.get("y", 0.0),
                        "z": comps.get("z", 0.0),
                        "resultant": mag.get("resultant", ""),
                    }
                )
            self.report.print_rows("Support reactions", rows, ["support", "x", "y", "z", "resultant"])

        if reaction_magnitudes:
            rows = []
            for support, mag in reaction_magnitudes.items():
                rows.append(
                    {
                        "support": support,
                        "|x|": mag.get("x", 0.0),
                        "|y|": mag.get("y", 0.0),
                        "|z|": mag.get("z", 0.0),
                        "resultant": mag.get("resultant", 0.0),
                    }
                )
            self.report.print_rows("Support reaction magnitudes", rows, ["support", "|x|", "|y|", "|z|", "resultant"])

        moments = outputs.get("solved_moments", {})
        if moments:
            self.report.print_kv_table("Solved moments", moments)

        sign_notes = outputs.get("sign_convention_notes", [])
        if sign_notes:
            self.report.print_list("Sign convention notes", sign_notes)

        comparisons = validation.get("comparisons", {})
        if comparisons:
            rows = []
            for item, comp in comparisons.items():
                rows.append(
                    {
                        "item": item,
                        "expected": comp.get("expected", ""),
                        "actual": comp.get("actual", ""),
                        "abs_diff": comp.get("abs_diff", ""),
                        "rel_diff_%": comp.get("rel_diff_percent", ""),
                        "status": comp.get("status", ""),
                    }
                )
            self.report.print_rows(
                "Validation against expected_textbook_reference_values",
                rows,
                ["item", "expected", "actual", "abs_diff", "rel_diff_%", "status"],
            )
