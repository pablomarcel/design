from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .utils import (
        DataLookupError,
        RangeError,
        ValidationError,
        coalesce,
        ensure_at_least,
        ensure_positive,
        linear_interpolate,
        log10,
        normalize_processing,
        normalize_steel_name,
        package_root,
        relative_error_percent,
        safe_round,
        summarize_matches,
    )
except ImportError:  # pragma: no cover
    from utils import (
        DataLookupError,
        RangeError,
        ValidationError,
        coalesce,
        ensure_at_least,
        ensure_positive,
        linear_interpolate,
        log10,
        normalize_processing,
        normalize_steel_name,
        package_root,
        relative_error_percent,
        safe_round,
        summarize_matches,
    )


@dataclass
class SteelRecord:
    uns_no: str
    sae_aisi_no: str
    processing: str
    tensile_strength_MPa: float
    tensile_strength_kpsi: float
    yield_strength_MPa: float
    yield_strength_kpsi: float
    elongation_percent_in_2in: float
    reduction_in_area_percent: float
    brinell_hardness: float

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "SteelRecord":
        return cls(
            uns_no=row["uns_no"],
            sae_aisi_no=row["sae_aisi_no"],
            processing=normalize_processing(row["processing"]) or "",
            tensile_strength_MPa=float(row["tensile_strength_MPa"]),
            tensile_strength_kpsi=float(row["tensile_strength_kpsi"]),
            yield_strength_MPa=float(row["yield_strength_MPa"]),
            yield_strength_kpsi=float(row["yield_strength_kpsi"]),
            elongation_percent_in_2in=float(row["elongation_percent_in_2in"]),
            reduction_in_area_percent=float(row["reduction_in_area_percent"]),
            brinell_hardness=float(row["brinell_hardness"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uns_no": self.uns_no,
            "sae_aisi_no": self.sae_aisi_no,
            "processing": self.processing,
            "tensile_strength_MPa": self.tensile_strength_MPa,
            "tensile_strength_kpsi": self.tensile_strength_kpsi,
            "yield_strength_MPa": self.yield_strength_MPa,
            "yield_strength_kpsi": self.yield_strength_kpsi,
            "elongation_percent_in_2in": self.elongation_percent_in_2in,
            "reduction_in_area_percent": self.reduction_in_area_percent,
            "brinell_hardness": self.brinell_hardness,
        }


class DigitizedDataRepository:
    """Programmatic access to digitized tables and figures used by the solver."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else package_root() / "data"
        self._steel_rows: list[SteelRecord] | None = None
        self._figure_6_18_rows: list[dict[str, float]] | None = None

    def _read_csv(self, filename: str) -> list[dict[str, str]]:
        path = self.data_dir / filename
        if not path.exists():
            raise DataLookupError(f"Required data file was not found: {path}")
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @property
    def steel_rows(self) -> list[SteelRecord]:
        if self._steel_rows is None:
            self._steel_rows = [SteelRecord.from_row(row) for row in self._read_csv("table_a_20.csv")]
        return self._steel_rows

    @property
    def figure_6_18_rows(self) -> list[dict[str, float]]:
        if self._figure_6_18_rows is None:
            raw_rows = self._read_csv("figure_6_18.csv")
            self._figure_6_18_rows = [
                {
                    "sut_kpsi": float(row["sut_kpsi"]),
                    "fatigue_strength_fraction_f": float(row["fatigue_strength_fraction_f"]),
                }
                for row in raw_rows
            ]
        return self._figure_6_18_rows

    def find_steel_record(self, sae_aisi_no: str | int, processing: str | None = None) -> SteelRecord:
        target_grade = normalize_steel_name(sae_aisi_no)
        target_processing = normalize_processing(processing)
        matches = [row for row in self.steel_rows if normalize_steel_name(row.sae_aisi_no) == target_grade]
        if not matches:
            raise DataLookupError(f"No Table A-20 record was found for SAE/AISI steel '{sae_aisi_no}'.")
        if target_processing:
            narrowed = [row for row in matches if row.processing == target_processing]
            if not narrowed:
                raise DataLookupError(
                    f"Table A-20 contains steel '{sae_aisi_no}', but not with processing '{processing}'. "
                    f"Available variants: {[row.processing for row in matches]}"
                )
            matches = narrowed
        if len(matches) > 1:
            raise DataLookupError(
                f"Multiple Table A-20 matches were found for steel '{sae_aisi_no}'. "
                f"Please specify processing. Matches: {summarize_matches([row.to_dict() for row in matches])}"
            )
        return matches[0]

    def fatigue_strength_fraction_from_figure_6_18(self, sut_kpsi: float) -> dict[str, Any]:
        sut_kpsi = float(sut_kpsi)
        if sut_kpsi < 70.0:
            return {
                "f": 0.9,
                "source": "text_rule_below_70_kpsi",
                "note": "Per p293, use f = 0.9 conservatively for Sut < 70 kpsi.",
            }
        xs = [row["sut_kpsi"] for row in self.figure_6_18_rows]
        ys = [row["fatigue_strength_fraction_f"] for row in self.figure_6_18_rows]
        if sut_kpsi > max(xs):
            raise RangeError(
                f"Figure 6-18 only covers 70 <= Sut <= {max(xs)} kpsi. "
                "Provide fatigue_strength_fraction_f_override for higher Sut values."
            )
        return {
            "f": linear_interpolate(sut_kpsi, xs, ys),
            "source": "figure_6_18_interpolated",
            "note": "Interpolated from figure_6_18.csv.",
        }


class FatigueStrengthSolver:
    """Implements Shigley Chapter 6 Example 6-2 style fatigue-strength relations."""

    solve_path = "fatigue_strength"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    def _resolve_material(self, inputs: dict[str, Any]) -> dict[str, Any]:
        material = inputs.get("material") or {}
        sae_aisi_no = coalesce(
            inputs.get("sae_aisi_no"),
            inputs.get("steel_grade"),
            material.get("sae_aisi_no"),
            material.get("steel_grade"),
        )
        processing = coalesce(inputs.get("processing"), material.get("processing"))
        if sae_aisi_no is None:
            return {"record": None, "match_strategy": "not_used"}
        record = self.repository.find_steel_record(sae_aisi_no=sae_aisi_no, processing=processing)
        return {
            "record": record,
            "match_strategy": "table_a_20_lookup",
        }

    def _resolve_sut(self, inputs: dict[str, Any], material_info: dict[str, Any]) -> dict[str, Any]:
        sut_kpsi = coalesce(inputs.get("sut_kpsi"), inputs.get("ultimate_tensile_strength_kpsi"))
        sut_mpa = coalesce(inputs.get("sut_MPa"), inputs.get("ultimate_tensile_strength_MPa"))

        if sut_kpsi is not None and sut_mpa is not None:
            return {
                "sut_kpsi": float(sut_kpsi),
                "sut_MPa": float(sut_mpa),
                "source": "user_input_both_units",
            }

        if sut_kpsi is not None:
            return {
                "sut_kpsi": float(sut_kpsi),
                "sut_MPa": float(sut_kpsi) * 6.894757293168361,
                "source": "user_input_kpsi",
            }

        if sut_mpa is not None:
            return {
                "sut_kpsi": float(sut_mpa) / 6.894757293168361,
                "sut_MPa": float(sut_mpa),
                "source": "user_input_MPa",
            }

        record: SteelRecord | None = material_info.get("record")
        if record is not None:
            return {
                "sut_kpsi": record.tensile_strength_kpsi,
                "sut_MPa": record.tensile_strength_MPa,
                "source": "table_a_20_lookup",
            }

        raise ValidationError(
            "Ultimate tensile strength is required. Provide sut_kpsi or sut_MPa, "
            "or provide a Table A-20 material lookup such as sae_aisi_no and processing."
        )

    def _resolve_endurance_limit(self, inputs: dict[str, Any], sut_kpsi: float) -> dict[str, Any]:
        se_component = inputs.get("se_kpsi")
        se_specimen = inputs.get("se_prime_kpsi")
        ne_cycles = float(inputs.get("endurance_limit_cycles", 1.0e6))

        if se_component is not None:
            return {
                "se_kpsi": float(se_component),
                "se_prime_kpsi": float(se_specimen) if se_specimen is not None else None,
                "endurance_limit_cycles": ne_cycles,
                "source": "user_input_se_kpsi",
            }

        if se_specimen is not None:
            return {
                "se_kpsi": float(se_specimen),
                "se_prime_kpsi": float(se_specimen),
                "endurance_limit_cycles": ne_cycles,
                "source": "user_input_se_prime_kpsi",
            }

        if sut_kpsi <= 200.0:
            se_prime = 0.5 * sut_kpsi
            rule = "eq_6_8_low_strength_branch"
        else:
            se_prime = 100.0
            rule = "eq_6_8_high_strength_branch"

        return {
            "se_kpsi": se_prime,
            "se_prime_kpsi": se_prime,
            "endurance_limit_cycles": ne_cycles,
            "source": rule,
        }

    def _resolve_f(self, inputs: dict[str, Any], sut_kpsi: float) -> dict[str, Any]:
        override = inputs.get("fatigue_strength_fraction_f_override")
        if override is not None:
            return {
                "f": float(override),
                "source": "user_override",
                "note": "User provided fatigue_strength_fraction_f_override.",
            }
        return self.repository.fatigue_strength_fraction_from_figure_6_18(sut_kpsi=sut_kpsi)

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"FatigueStrengthSolver received solve_path={inputs.get('solve_path')!r}; "
                f"expected {self.solve_path!r}."
            )

        material_info = self._resolve_material(inputs)
        sut_info = self._resolve_sut(inputs, material_info)
        endurance_info = self._resolve_endurance_limit(inputs, sut_info["sut_kpsi"])
        f_info = self._resolve_f(inputs, sut_info["sut_kpsi"])

        n_low = ensure_at_least("sn_low_cycle_anchor_cycles", inputs.get("sn_low_cycle_anchor_cycles", 1.0e3), 1.0)
        n_endurance = ensure_at_least(
            "endurance_limit_cycles",
            endurance_info["endurance_limit_cycles"],
            n_low,
        )
        if math.isclose(n_endurance, n_low, rel_tol=0.0, abs_tol=1e-12):
            raise ValidationError("endurance_limit_cycles must be different from sn_low_cycle_anchor_cycles.")

        sut_kpsi = float(sut_info["sut_kpsi"])
        se_kpsi = ensure_positive("se_kpsi", endurance_info["se_kpsi"])
        f_value = ensure_positive("fatigue_strength_fraction_f", f_info["f"])
        sf_low_kpsi = f_value * sut_kpsi
        if sf_low_kpsi <= 0 or se_kpsi <= 0:
            raise ValidationError("Resolved S-N anchor stresses must be positive.")

        a_kpsi = (sf_low_kpsi ** 2) / se_kpsi
        b = log10(se_kpsi / sf_low_kpsi) / log10(n_endurance / n_low)
        if math.isclose(b, 0.0, rel_tol=0.0, abs_tol=1e-15):
            raise ValidationError("Resolved exponent b is zero, so the S-N relation would be singular.")

        stress_queries: list[dict[str, Any]] = []
        for entry in inputs.get("stress_queries", []):
            cycles = ensure_positive("stress_queries[].cycles", entry.get("cycles"))
            stress = a_kpsi * (cycles ** b)
            stress_queries.append(
                {
                    "name": entry.get("name") or f"stress_at_{cycles:g}_cycles",
                    "cycles": cycles,
                    "stress_kpsi": safe_round(stress),
                    "stress_MPa": safe_round(stress * 6.894757293168361),
                    "equation": "eq_6_13",
                }
            )

        life_queries: list[dict[str, Any]] = []
        for entry in inputs.get("life_queries", []):
            sigma_rev = ensure_positive("life_queries[].stress_kpsi", entry.get("stress_kpsi"))
            cycles = (sigma_rev / a_kpsi) ** (1.0 / b)
            life_queries.append(
                {
                    "name": entry.get("name") or f"life_at_{sigma_rev:g}_kpsi",
                    "stress_kpsi": sigma_rev,
                    "stress_MPa": safe_round(sigma_rev * 6.894757293168361),
                    "cycles": safe_round(cycles),
                    "equation": "eq_6_16",
                }
            )

        low_cycle_queries: list[dict[str, Any]] = []
        for entry in inputs.get("low_cycle_queries", []):
            cycles = ensure_at_least("low_cycle_queries[].cycles", entry.get("cycles"), 1.0)
            if cycles > n_low:
                raise ValidationError(
                    f"Eq. (6-17) is only intended for 1 <= N <= {n_low:g} cycles. Got N={cycles}."
                )
            stress = sut_kpsi * (cycles ** (log10(f_value) / 3.0))
            low_cycle_queries.append(
                {
                    "name": entry.get("name") or f"low_cycle_stress_at_{cycles:g}_cycles",
                    "cycles": cycles,
                    "stress_kpsi_lower_bound": safe_round(stress),
                    "stress_MPa_lower_bound": safe_round(stress * 6.894757293168361),
                    "equation": "eq_6_17",
                }
            )

        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        verification: dict[str, Any] = {}
        if expected_ref:
            for key, actual in {
                "sut_kpsi": sut_kpsi,
                "se_prime_kpsi": endurance_info.get("se_prime_kpsi"),
                "se_kpsi": se_kpsi,
                "fatigue_strength_fraction_f": f_value,
                "a_kpsi": a_kpsi,
                "b": b,
            }.items():
                if key in expected_ref and actual is not None:
                    verification[key] = {
                        "actual": safe_round(actual),
                        "reference": expected_ref[key],
                        "relative_error_percent": safe_round(relative_error_percent(actual, float(expected_ref[key]))),
                    }
            if stress_queries:
                expected_strength = expected_ref.get("stress_query_results", {})
                for item in stress_queries:
                    if item["name"] in expected_strength:
                        verification[f"stress_query::{item['name']}"] = {
                            "actual": item["stress_kpsi"],
                            "reference": expected_strength[item["name"]],
                            "relative_error_percent": safe_round(
                                relative_error_percent(item["stress_kpsi"], float(expected_strength[item["name"]]))
                            ),
                        }
            if life_queries:
                expected_life = expected_ref.get("life_query_results", {})
                for item in life_queries:
                    if item["name"] in expected_life:
                        verification[f"life_query::{item['name']}"] = {
                            "actual": item["cycles"],
                            "reference": expected_life[item["name"]],
                            "relative_error_percent": safe_round(
                                relative_error_percent(item["cycles"], float(expected_life[item["name"]]))
                            ),
                        }

        output = {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Fatigue strength analysis"),
            "inputs": inputs,
            "lookups": {
                "table_a_20": material_info["record"].to_dict() if material_info.get("record") else None,
                "figure_6_18": {
                    "sut_kpsi_for_lookup": safe_round(sut_kpsi),
                    "fatigue_strength_fraction_f": safe_round(f_value),
                    "source": f_info.get("source"),
                    "note": f_info.get("note"),
                },
            },
            "derived": {
                "sut_kpsi": safe_round(sut_kpsi),
                "sut_MPa": safe_round(sut_info["sut_MPa"]),
                "se_prime_kpsi": safe_round(endurance_info.get("se_prime_kpsi")),
                "se_kpsi": safe_round(se_kpsi),
                "se_MPa": safe_round(se_kpsi * 6.894757293168361),
                "fatigue_strength_fraction_f": safe_round(f_value),
                "sn_low_cycle_anchor_cycles": n_low,
                "endurance_limit_cycles": n_endurance,
                "sf_at_low_cycle_anchor_kpsi": safe_round(sf_low_kpsi),
                "sf_at_low_cycle_anchor_MPa": safe_round(sf_low_kpsi * 6.894757293168361),
                "a_kpsi": safe_round(a_kpsi),
                "a_MPa": safe_round(a_kpsi * 6.894757293168361),
                "b": safe_round(b),
                "sn_equation_kpsi": f"S_f = {safe_round(a_kpsi)} * N^({safe_round(b)})",
                "sn_equation_MPa": f"S_f = {safe_round(a_kpsi * 6.894757293168361)} * N^({safe_round(b)})",
            },
            "results": {
                "stress_queries": stress_queries,
                "life_queries": life_queries,
                "low_cycle_queries": low_cycle_queries,
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-8", "6-13", "6-14", "6-15", "6-16", "6-17"],
                "notes": [
                    "This first-pass solver targets Example 6-2 style polished rotating-beam fatigue-strength calculations.",
                    "When se_kpsi is omitted, the solver uses Eq. (6-8) to estimate the rotating-beam specimen endurance limit S'e.",
                    "For Sut < 70 kpsi, the solver applies the conservative text rule f = 0.9 from p293.",
                    "Eq. (6-16) is only valid for completely reversed loading, matching the textbook statement.",
                ],
            },
        }
        if verification:
            output["verification"] = verification
        return output
