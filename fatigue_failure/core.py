from __future__ import annotations

import csv
import json
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
        in_to_mm,
        kpsi_to_mpa,
        linear_interpolate,
        log10,
        mm_to_in,
        mpa_to_kpsi,
        normalize_axis_name,
        normalize_processing,
        normalize_shape_name,
        normalize_steel_name,
        normalize_surface_finish,
        package_root,
        relative_error_percent,
        safe_eval_expression,
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
        in_to_mm,
        kpsi_to_mpa,
        linear_interpolate,
        log10,
        mm_to_in,
        mpa_to_kpsi,
        normalize_axis_name,
        normalize_processing,
        normalize_shape_name,
        normalize_steel_name,
        normalize_surface_finish,
        package_root,
        relative_error_percent,
        safe_eval_expression,
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


@dataclass
class SurfaceFinishRecord:
    surface_finish: str
    a_factor_kpsi: float
    a_factor_MPa: float
    b_exponent: float

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "SurfaceFinishRecord":
        return cls(
            surface_finish=row["surface_finish"].strip(),
            a_factor_kpsi=float(row["a_factor_kpsi"]),
            a_factor_MPa=float(row["a_factor_MPa"]),
            b_exponent=float(row["b_exponent"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_finish": self.surface_finish,
            "a_factor_kpsi": self.a_factor_kpsi,
            "a_factor_MPa": self.a_factor_MPa,
            "b_exponent": self.b_exponent,
        }


class DigitizedDataRepository:
    """Programmatic access to digitized tables and figures used by the solvers."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else package_root() / "data"
        self._steel_rows: list[SteelRecord] | None = None
        self._figure_6_18_rows: list[dict[str, float]] | None = None
        self._surface_finish_rows: list[SurfaceFinishRecord] | None = None
        self._table_6_3_payload: dict[str, Any] | None = None
        self._table_6_4_rows: list[dict[str, float]] | None = None
        self._table_6_5_rows: list[dict[str, float]] | None = None
        self._table_a_15_9_payload: dict[str, Any] | None = None
        self._figure_6_20_payload: dict[str, Any] | None = None

    def _read_csv(self, filename: str) -> list[dict[str, str]]:
        path = self.data_dir / filename
        if not path.exists():
            raise DataLookupError(f"Required data file was not found: {path}")
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def _read_json(self, filename: str) -> dict[str, Any]:
        path = self.data_dir / filename
        if not path.exists():
            raise DataLookupError(f"Required data file was not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

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

    @property
    def surface_finish_rows(self) -> list[SurfaceFinishRecord]:
        if self._surface_finish_rows is None:
            self._surface_finish_rows = [
                SurfaceFinishRecord.from_row(row) for row in self._read_csv("table_6_2.csv")
            ]
        return self._surface_finish_rows

    @property
    def table_6_3_payload(self) -> dict[str, Any]:
        if self._table_6_3_payload is None:
            self._table_6_3_payload = self._read_json("table_6_3.json")
        return self._table_6_3_payload

    @staticmethod
    def _clean_csv_value(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _first_present_value(row: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            if key in row:
                value = DigitizedDataRepository._clean_csv_value(row.get(key))
                if value != "":
                    return value
        return ""

    @property
    def table_6_4_rows(self) -> list[dict[str, float]]:
        if self._table_6_4_rows is None:
            raw_rows = self._read_csv("table_6_4.csv")
            rows: list[dict[str, float]] = []

            for row in raw_rows:
                temperature_f_text = self._first_present_value(
                    row,
                    [
                        "temperature_F",
                        "temperature_f",
                        "Temperature_F",
                        "Temperature_f",
                        "temperature_imperial_F",
                    ],
                )
                ratio_f_text = self._first_present_value(
                    row,
                    [
                        "ST_over_SRT_imperial",
                        "st_over_srt_imperial",
                        "ST_over_SRT_F",
                        "st_over_srt_f",
                        "st_over_srt",
                    ],
                )

                if temperature_f_text and ratio_f_text:
                    rows.append(
                        {
                            "temperature_f": float(temperature_f_text),
                            "st_over_srt": float(ratio_f_text),
                        }
                    )
                    continue

                temperature_c_text = self._first_present_value(
                    row,
                    [
                        "temperature_C",
                        "temperature_c",
                        "Temperature_C",
                        "Temperature_c",
                    ],
                )
                ratio_c_text = self._first_present_value(
                    row,
                    [
                        "ST_over_SRT_metric",
                        "st_over_srt_metric",
                        "ST_over_SRT_C",
                        "st_over_srt_c",
                    ],
                )

                if temperature_c_text and ratio_c_text:
                    temperature_f = float(temperature_c_text) * 9.0 / 5.0 + 32.0
                    rows.append(
                        {
                            "temperature_f": temperature_f,
                            "st_over_srt": float(ratio_c_text),
                        }
                    )

            deduped: dict[float, float] = {}
            for row in rows:
                deduped[float(row["temperature_f"])] = float(row["st_over_srt"])

            normalized_rows = [
                {"temperature_f": temp_f, "st_over_srt": ratio}
                for temp_f, ratio in sorted(deduped.items(), key=lambda item: item[0])
            ]

            if len(normalized_rows) < 2:
                raise DataLookupError(
                    "table_6_4.csv could not be parsed into at least two usable Fahrenheit data points. "
                    "Expected columns like temperature_F/ST_over_SRT_imperial or temperature_C/ST_over_SRT_metric."
                )

            self._table_6_4_rows = normalized_rows

        return self._table_6_4_rows


    @property
    def table_6_5_rows(self) -> list[dict[str, float]]:
        if self._table_6_5_rows is None:
            raw_rows = self._read_csv("table_6_5.csv")
            rows: list[dict[str, float]] = []
            for row in raw_rows:
                reliability_text = self._first_present_value(row, ["reliability_percent", "Reliability_percent", "reliability"])
                ke_text = self._first_present_value(row, ["reliability_factor_k_e", "reliability_factor_ke", "k_e", "ke"])
                za_text = self._first_present_value(row, ["transformation_variate_z_a", "transformation_variate_za", "z_a", "za"])
                if reliability_text and ke_text:
                    rows.append({
                        "reliability_percent": float(reliability_text),
                        "reliability_factor_k_e": float(ke_text),
                        "transformation_variate_z_a": float(za_text) if za_text else None,
                    })
            rows.sort(key=lambda item: item["reliability_percent"])
            if len(rows) < 2:
                raise DataLookupError("table_6_5.csv could not be parsed into at least two usable reliability points.")
            self._table_6_5_rows = rows
        return self._table_6_5_rows

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

    def find_surface_finish_record(self, surface_finish: str) -> SurfaceFinishRecord:
        target = normalize_surface_finish(surface_finish)
        matches = [
            row for row in self.surface_finish_rows
            if normalize_surface_finish(row.surface_finish) == target
        ]
        if not matches:
            available = [row.surface_finish for row in self.surface_finish_rows]
            raise DataLookupError(
                f"No Table 6-2 record was found for surface_finish={surface_finish!r}. "
                f"Available finishes: {available}"
            )
        if len(matches) > 1:
            raise DataLookupError(
                f"Multiple Table 6-2 matches were found for surface_finish={surface_finish!r}."
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

    def table_6_3_entry(self, shape: str) -> dict[str, Any]:
        target = normalize_shape_name(shape)
        entries = self.table_6_3_payload.get("entries", [])
        for entry in entries:
            if normalize_shape_name(entry.get("shape")) == target:
                return entry
        available = [entry.get("shape") for entry in entries]
        raise DataLookupError(f"No Table 6-3 entry was found for shape={shape!r}. Available shapes: {available}")

    def table_6_4_ratio_from_f(self, temperature_f: float) -> dict[str, Any]:
        rows = self.table_6_4_rows
        xs = [row["temperature_f"] for row in rows]
        ys = [row["st_over_srt"] for row in rows]
        ratio = linear_interpolate(float(temperature_f), xs, ys)
        return {
            "temperature_f": float(temperature_f),
            "st_over_srt": ratio,
            "source": "table_6_4_interpolated",
        }


    def reliability_factor_from_table_6_5(self, reliability_percent: float) -> dict[str, Any]:
        rows = self.table_6_5_rows
        xs = [row["reliability_percent"] for row in rows]
        ys = [row["reliability_factor_k_e"] for row in rows]
        if any(abs(float(reliability_percent) - x) <= 1e-12 for x in xs):
            source = "table_6_5_exact"
        else:
            source = "table_6_5_interpolated"
        k_e = linear_interpolate(float(reliability_percent), xs, ys)
        return {
            "reliability_percent": float(reliability_percent),
            "reliability_factor_k_e": k_e,
            "source": source,
        }


    @property
    def table_a_15_9_payload(self) -> dict[str, Any]:
        if self._table_a_15_9_payload is None:
            self._table_a_15_9_payload = self._read_json("table_a_15_9.json")
        return self._table_a_15_9_payload

    @property
    def figure_6_20_payload(self) -> dict[str, Any]:
        if self._figure_6_20_payload is None:
            self._figure_6_20_payload = self._read_json("figure_6_20.json")
        return self._figure_6_20_payload

    @staticmethod
    def _interp_from_points(x: float, points: list[dict[str, Any]], x_key: str, y_key: str) -> float:
        xs = [float(point[x_key]) for point in points]
        ys = [float(point[y_key]) for point in points]
        return linear_interpolate(float(x), xs, ys)

    def stress_concentration_kt_shoulder_bending(self, D_over_d: float, r_over_d: float) -> dict[str, Any]:
        payload = self.table_a_15_9_payload
        traces = payload.get("traces", [])
        if len(traces) < 2:
            raise DataLookupError("table_a_15_9.json must contain at least two traces.")
        trace_values: list[tuple[float, float]] = []
        for trace in traces:
            dd = float(trace["D_over_d"])
            kt = self._interp_from_points(
                x=float(r_over_d),
                points=trace["points"],
                x_key="r_over_d",
                y_key="K_t",
            )
            trace_values.append((dd, kt))
        trace_values.sort(key=lambda item: item[0])
        dds = [item[0] for item in trace_values]
        kts = [item[1] for item in trace_values]
        kt_final = linear_interpolate(float(D_over_d), dds, kts)
        return {
            "D_over_d": float(D_over_d),
            "r_over_d": float(r_over_d),
            "K_t": kt_final,
            "source": "table_a_15_9_interpolated",
            "intermediate_trace_values": [
                {"D_over_d": dd, "K_t_at_requested_r_over_d": kt}
                for dd, kt in trace_values
            ],
        }

    def notch_sensitivity_q_bending(self, sut_kpsi: float, r_in: float) -> dict[str, Any]:
        payload = self.figure_6_20_payload
        traces = payload.get("traces", [])
        steel_traces = [trace for trace in traces if str(trace.get("material", "")).lower() == "steel"]
        if len(steel_traces) < 2:
            raise DataLookupError("figure_6_20.json must contain at least two steel traces.")
        trace_values: list[tuple[float, float]] = []
        for trace in steel_traces:
            sut_trace = float(trace["Sut_kpsi"])
            q_val = self._interp_from_points(
                x=float(r_in),
                points=trace["points"],
                x_key="r_in",
                y_key="q",
            )
            trace_values.append((sut_trace, q_val))
        trace_values.sort(key=lambda item: item[0])
        suts = [item[0] for item in trace_values]
        qs = [item[1] for item in trace_values]
        q_final = linear_interpolate(float(sut_kpsi), suts, qs)
        return {
            "sut_kpsi": float(sut_kpsi),
            "r_in": float(r_in),
            "r_mm": float(in_to_mm(r_in)),
            "q": q_final,
            "source": "figure_6_20_interpolated",
            "intermediate_trace_values": [
                {"Sut_kpsi": sut_val, "q_at_requested_r_in": q_val}
                for sut_val, q_val in trace_values
            ],
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
                "sut_MPa": kpsi_to_mpa(float(sut_kpsi)),
                "source": "user_input_kpsi",
            }

        if sut_mpa is not None:
            return {
                "sut_kpsi": mpa_to_kpsi(float(sut_mpa)),
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
                    "stress_MPa": safe_round(kpsi_to_mpa(stress)),
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
                    "stress_MPa": safe_round(kpsi_to_mpa(sigma_rev)),
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
                    "stress_MPa_lower_bound": safe_round(kpsi_to_mpa(stress)),
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
                "se_MPa": safe_round(kpsi_to_mpa(se_kpsi)),
                "fatigue_strength_fraction_f": safe_round(f_value),
                "sn_low_cycle_anchor_cycles": n_low,
                "endurance_limit_cycles": n_endurance,
                "sf_at_low_cycle_anchor_kpsi": safe_round(sf_low_kpsi),
                "sf_at_low_cycle_anchor_MPa": safe_round(kpsi_to_mpa(sf_low_kpsi)),
                "a_kpsi": safe_round(a_kpsi),
                "a_MPa": safe_round(kpsi_to_mpa(a_kpsi)),
                "b": safe_round(b),
                "sn_equation_kpsi": f"S_f = {safe_round(a_kpsi)} * N^({safe_round(b)})",
                "sn_equation_MPa": f"S_f = {safe_round(kpsi_to_mpa(a_kpsi))} * N^({safe_round(b)})",
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


class SurfaceFactorSolver:
    """Implements Shigley Chapter 6 Example 6-3 surface-factor calculations."""

    solve_path = "surface_factor"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    def _resolve_surface_finish(self, inputs: dict[str, Any]) -> SurfaceFinishRecord:
        value = coalesce(inputs.get("surface_finish"), inputs.get("finish"), inputs.get("surface_condition"))
        if value is None:
            raise ValidationError(
                "surface_finish is required for solve_path='surface_factor'. "
                "Example values: Ground, Machined or cold-drawn, Hot-rolled, As-forged."
            )
        return self.repository.find_surface_finish_record(str(value))

    def _resolve_sut(self, inputs: dict[str, Any]) -> dict[str, Any]:
        sut_kpsi = coalesce(inputs.get("sut_kpsi"), inputs.get("ultimate_tensile_strength_kpsi"))
        sut_mpa = coalesce(inputs.get("sut_MPa"), inputs.get("ultimate_tensile_strength_MPa"))

        if sut_kpsi is None and sut_mpa is None:
            raise ValidationError(
                "Ultimate tensile strength is required for solve_path='surface_factor'. "
                "Provide sut_kpsi or sut_MPa."
            )

        if sut_kpsi is not None and sut_mpa is not None:
            return {
                "sut_kpsi": float(sut_kpsi),
                "sut_MPa": float(sut_mpa),
                "source": "user_input_both_units",
            }

        if sut_kpsi is not None:
            return {
                "sut_kpsi": float(sut_kpsi),
                "sut_MPa": kpsi_to_mpa(float(sut_kpsi)),
                "source": "user_input_kpsi",
            }

        return {
            "sut_kpsi": mpa_to_kpsi(float(sut_mpa)),
            "sut_MPa": float(sut_mpa),
            "source": "user_input_MPa",
        }

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"SurfaceFactorSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        finish_record = self._resolve_surface_finish(inputs)
        sut_info = self._resolve_sut(inputs)

        strength_unit = coalesce(inputs.get("strength_unit"), inputs.get("preferred_strength_unit"))
        if strength_unit is None:
            strength_unit = "MPa" if inputs.get("sut_MPa") is not None else "kpsi"
        strength_unit = str(strength_unit).strip()
        unit_key = strength_unit.lower()
        if unit_key not in {"mpa", "kpsi"}:
            raise ValidationError("strength_unit must be either 'MPa' or 'kpsi'.")

        a_selected = finish_record.a_factor_MPa if unit_key == "mpa" else finish_record.a_factor_kpsi
        sut_selected = sut_info["sut_MPa"] if unit_key == "mpa" else sut_info["sut_kpsi"]
        b_selected = finish_record.b_exponent
        ka_selected = a_selected * (sut_selected ** b_selected)

        ka_from_mpa = finish_record.a_factor_MPa * (sut_info["sut_MPa"] ** finish_record.b_exponent)
        ka_from_kpsi = finish_record.a_factor_kpsi * (sut_info["sut_kpsi"] ** finish_record.b_exponent)

        verification: dict[str, Any] = {}
        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        expected_ka = coalesce(expected_ref.get("ka"), expected_ref.get("k_a"), inputs.get("expected_ka"))
        if expected_ka is not None:
            verification["ka"] = {
                "actual": safe_round(ka_selected),
                "reference": float(expected_ka),
                "relative_error_percent": safe_round(relative_error_percent(ka_selected, float(expected_ka))),
            }

        output = {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Surface factor analysis"),
            "inputs": inputs,
            "lookups": {"table_6_2": finish_record.to_dict()},
            "derived": {
                "surface_finish_normalized": normalize_surface_finish(finish_record.surface_finish),
                "sut_kpsi": safe_round(sut_info["sut_kpsi"]),
                "sut_MPa": safe_round(sut_info["sut_MPa"]),
                "a_factor_selected": safe_round(a_selected),
                "b_exponent": safe_round(b_selected),
                "strength_unit_used_for_eq_6_19": "MPa" if unit_key == "mpa" else "kpsi",
                "sut_used_in_eq_6_19": safe_round(sut_selected),
                "eq_6_19_selected": f"k_a = {safe_round(a_selected)} * Sut^({safe_round(b_selected)}) [{'MPa' if unit_key == 'mpa' else 'kpsi'}]",
                "ka_from_MPa_form": safe_round(ka_from_mpa),
                "ka_from_kpsi_form": safe_round(ka_from_kpsi),
                "cross_unit_difference_percent": safe_round(relative_error_percent(ka_from_kpsi, ka_from_mpa)),
            },
            "results": {"ka": safe_round(ka_selected)},
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-19"],
                "notes": [
                    "This solver targets Example 6-3 style Marin surface-factor calculations.",
                    "The Table 6-2 coefficients are read from table_6_2.csv, not hardcoded in the input file.",
                    "If both MPa and kpsi strengths are provided, the selected strength_unit controls which Table 6-2 coefficient set is used for the reported Eq. (6-19) result.",
                ],
            },
        }
        if verification:
            output["verification"] = verification
        return output


class SizeFactorSolver:
    """Implements Shigley Chapter 6 Example 6-4 style Marin size-factor calculations."""

    solve_path = "size_factor"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    def _resolve_strengths(self, inputs: dict[str, Any]) -> dict[str, Any]:
        sut_mpa = coalesce(
            inputs.get("sut_MPa"),
            inputs.get("ultimate_tensile_strength_MPa"),
            inputs.get("mean_ultimate_tensile_strength_MPa"),
        )
        sut_kpsi = coalesce(
            inputs.get("sut_kpsi"),
            inputs.get("ultimate_tensile_strength_kpsi"),
            inputs.get("mean_ultimate_tensile_strength_kpsi"),
        )
        if sut_mpa is None and sut_kpsi is None:
            return {"sut_MPa": None, "sut_kpsi": None, "source": "not_provided"}
        if sut_mpa is not None and sut_kpsi is not None:
            return {"sut_MPa": float(sut_mpa), "sut_kpsi": float(sut_kpsi), "source": "user_input_both_units"}
        if sut_mpa is not None:
            return {"sut_MPa": float(sut_mpa), "sut_kpsi": mpa_to_kpsi(float(sut_mpa)), "source": "user_input_MPa"}
        return {"sut_MPa": kpsi_to_mpa(float(sut_kpsi)), "sut_kpsi": float(sut_kpsi), "source": "user_input_kpsi"}

    def _resolve_size_factor_from_diameter_mm(self, diameter_mm: float, loading_type: str) -> dict[str, Any]:
        d_mm = ensure_positive("diameter_mm", diameter_mm)
        load = str(loading_type).strip().lower()

        if load == "axial":
            return {
                "kb": 1.0,
                "equation": "eq_6_21",
                "diameter_mm_used": d_mm,
                "diameter_in_used": mm_to_in(d_mm),
                "branch": "axial_no_size_effect",
            }

        if load not in {"bending", "torsion"}:
            raise ValidationError("loading_type must be one of: bending, torsion, axial.")

        if 2.79 <= d_mm <= 51.0:
            kb = (d_mm / 7.62) ** (-0.107)
            return {
                "kb": kb,
                "equation": "eq_6_20",
                "diameter_mm_used": d_mm,
                "diameter_in_used": mm_to_in(d_mm),
                "branch": "metric_small_diameter_branch",
                "expression": "k_b = (d/7.62)^(-0.107)",
            }

        if 51.0 < d_mm <= 254.0:
            kb = 1.51 * (d_mm ** (-0.157))
            return {
                "kb": kb,
                "equation": "eq_6_20",
                "diameter_mm_used": d_mm,
                "diameter_in_used": mm_to_in(d_mm),
                "branch": "metric_large_diameter_branch",
                "expression": "k_b = 1.51*d^(-0.157)",
            }

        raise RangeError(
            "Eq. (6-20) metric diameter range is 2.79 <= d <= 254 mm for bending/torsion. "
            f"Got d = {d_mm} mm."
        )

    def _evaluate_table_6_3_effective_diameter_mm(self, shape: str, parameters_mm: dict[str, Any], axis: str | None) -> dict[str, Any]:
        entry = self.repository.table_6_3_entry(shape)
        normalized_shape = normalize_shape_name(shape)
        params = {key: float(value) for key, value in (parameters_mm or {}).items()}

        if "expressions" in entry and "d_e" in entry["expressions"]:
            de_mm = safe_eval_expression(entry["expressions"]["d_e"], params)
            area = None
            if "A_0.95sigma" in entry["expressions"]:
                area = safe_eval_expression(entry["expressions"]["A_0.95sigma"], params)
            return {
                "shape": normalized_shape,
                "display_name": entry.get("display_name"),
                "axis": None,
                "parameters_mm": params,
                "A_0.95sigma_mm2": area,
                "effective_diameter_mm": de_mm,
                "source": "table_6_3_expression",
                "condition": entry.get("condition"),
            }

        axis_key = normalize_axis_name(axis)
        if axis_key is None:
            raise ValidationError(
                f"Table 6-3 shape {shape!r} requires an axis selection such as axis_1_1 or axis_2_2."
            )

        expressions_by_axis = entry.get("expressions_by_axis") or {}
        axis_entry = expressions_by_axis.get(axis_key)
        if axis_entry is None:
            raise ValidationError(
                f"Axis {axis!r} is not valid for shape {shape!r}. Available axes: {list(expressions_by_axis)}"
            )

        area = safe_eval_expression(axis_entry["A_0.95sigma"], params)
        de_mm = math.sqrt(area / 0.01046)
        return {
            "shape": normalized_shape,
            "display_name": entry.get("display_name"),
            "axis": axis_key,
            "parameters_mm": params,
            "A_0.95sigma_mm2": area,
            "effective_diameter_mm": de_mm,
            "source": "table_6_3_area_equivalence",
            "condition": entry.get("condition"),
            "back_calculation": "d_e = sqrt(A_0.95sigma / 0.01046)",
        }

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"SizeFactorSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        loading_type = str(coalesce(inputs.get("loading_type"), "bending")).strip().lower()
        strengths = self._resolve_strengths(inputs)

        cases = inputs.get("cases")
        if not cases:
            default_d = coalesce(
                inputs.get("diameter_mm"),
                inputs.get("shaft_diameter_mm"),
                inputs.get("small_diameter_mm"),
            )
            if default_d is None:
                raise ValidationError(
                    "solve_path='size_factor' requires 'cases', or a default diameter such as diameter_mm/shaft_diameter_mm."
                )
            cases = [{"name": "size_factor", "mode": "rotating", "diameter_mm": default_d}]

        results = []
        lookup_cases = []
        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        expected_case_results = expected_ref.get("case_results", {})
        verification = {}

        for case in cases:
            name = case.get("name") or "size_factor_case"
            mode = str(coalesce(case.get("mode"), case.get("rotation_mode"), "rotating")).strip().lower()
            if mode not in {"rotating", "nonrotating"}:
                raise ValidationError(f"Case {name!r} has unsupported mode={mode!r}. Use 'rotating' or 'nonrotating'.")

            if mode == "rotating":
                d_mm = coalesce(
                    case.get("diameter_mm"),
                    case.get("shaft_diameter_mm"),
                    inputs.get("diameter_mm"),
                    inputs.get("shaft_diameter_mm"),
                    inputs.get("small_diameter_mm"),
                    inputs.get("shaft_small_diameter_mm"),
                )
                d_mm = ensure_positive(f"cases[{name}].diameter_mm", d_mm)
                resolved = self._resolve_size_factor_from_diameter_mm(d_mm, loading_type=loading_type)
                lookup_cases.append(
                    {
                        "name": name,
                        "mode": mode,
                        "table_6_3": None,
                    }
                )
                result_item = {
                    "name": name,
                    "mode": mode,
                    "loading_type": loading_type,
                    "diameter_mm_used": safe_round(resolved["diameter_mm_used"]),
                    "diameter_in_used": safe_round(resolved["diameter_in_used"]),
                    "effective_diameter_mm": safe_round(resolved["diameter_mm_used"]),
                    "effective_diameter_in": safe_round(resolved["diameter_in_used"]),
                    "kb": safe_round(resolved["kb"]),
                    "equation": resolved["equation"],
                    "eq_6_20_branch": resolved.get("branch"),
                    "expression": resolved.get("expression"),
                }
            else:
                shape = coalesce(case.get("shape"), inputs.get("shape"), "solid_round")
                axis = coalesce(case.get("axis"), inputs.get("axis"))
                params_mm = case.get("shape_parameters_mm") or case.get("shape_parameters") or {}
                if not params_mm:
                    d_mm = coalesce(
                        case.get("diameter_mm"),
                        case.get("shaft_diameter_mm"),
                        inputs.get("diameter_mm"),
                        inputs.get("shaft_diameter_mm"),
                        inputs.get("small_diameter_mm"),
                        inputs.get("shaft_small_diameter_mm"),
                    )
                    if normalize_shape_name(shape) == "solid_round" and d_mm is not None:
                        params_mm = {"d": float(d_mm)}
                    else:
                        raise ValidationError(
                            f"Case {name!r} requires shape_parameters_mm for nonrotating Table 6-3 evaluation."
                        )

                table_eval = self._evaluate_table_6_3_effective_diameter_mm(shape=shape, parameters_mm=params_mm, axis=axis)
                resolved = self._resolve_size_factor_from_diameter_mm(table_eval["effective_diameter_mm"], loading_type=loading_type)

                lookup_cases.append(
                    {
                        "name": name,
                        "mode": mode,
                        "table_6_3": {
                            "shape": table_eval["shape"],
                            "display_name": table_eval["display_name"],
                            "axis": table_eval["axis"],
                            "parameters_mm": table_eval["parameters_mm"],
                            "A_0.95sigma_mm2": safe_round(table_eval["A_0.95sigma_mm2"]),
                            "effective_diameter_mm": safe_round(table_eval["effective_diameter_mm"]),
                            "source": table_eval["source"],
                            "condition": table_eval.get("condition"),
                            "back_calculation": table_eval.get("back_calculation"),
                        },
                    }
                )

                result_item = {
                    "name": name,
                    "mode": mode,
                    "loading_type": loading_type,
                    "diameter_mm_used": None,
                    "diameter_in_used": None,
                    "effective_diameter_mm": safe_round(table_eval["effective_diameter_mm"]),
                    "effective_diameter_in": safe_round(mm_to_in(table_eval["effective_diameter_mm"])),
                    "kb": safe_round(resolved["kb"]),
                    "equation": resolved["equation"],
                    "eq_6_20_branch": resolved.get("branch"),
                    "expression": resolved.get("expression"),
                }

            results.append(result_item)

            if name in expected_case_results:
                verification[f"case::{name}"] = {
                    "actual": result_item["kb"],
                    "reference": float(expected_case_results[name]),
                    "relative_error_percent": safe_round(
                        relative_error_percent(result_item["kb"], float(expected_case_results[name]))
                    ),
                }

        output = {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Size factor analysis"),
            "inputs": inputs,
            "lookups": {
                "table_6_3": {
                    "table": self.repository.table_6_3_payload.get("table"),
                    "title": self.repository.table_6_3_payload.get("title"),
                    "cases": lookup_cases,
                }
            },
            "derived": {
                "sut_MPa": safe_round(strengths.get("sut_MPa")),
                "sut_kpsi": safe_round(strengths.get("sut_kpsi")),
                "loading_type": loading_type,
                "equation_6_20_metric_small_diameter": "k_b = (d/7.62)^(-0.107) for 2.79 <= d <= 51 mm",
                "equation_6_20_metric_large_diameter": "k_b = 1.51*d^(-0.157) for 51 < d <= 254 mm",
                "equation_6_21_axial": "k_b = 1 for axial loading",
                "note_on_strength": "Ultimate strength is part of the problem statement but is not used directly in Eqs. (6-20) and (6-21).",
            },
            "results": {
                "cases": results,
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-20", "6-21", "6-22", "6-23", "6-24", "6-25"],
                "notes": [
                    "This solver targets Example 6-4 style Marin size-factor calculations.",
                    "For rotating round sections, Eq. (6-20) is applied directly with the actual diameter.",
                    "For nonrotating sections, the solver fetches the Table 6-3 geometry relation, computes the equivalent diameter d_e, and then applies Eq. (6-20).",
                    "For axial loading, Eq. (6-21) gives k_b = 1.",
                ],
            },
        }
        if verification:
            output["verification"] = verification
        return output


class TemperatureFactorSolver:
    """Implements Shigley Chapter 6 Example 6-5 temperature-factor calculations."""

    solve_path = "temperature_factor"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    @staticmethod
    def _to_fahrenheit(temperature: float, unit: str) -> float:
        unit_norm = str(unit).strip().upper()
        if unit_norm in {"F", "°F", "DEGF"}:
            return float(temperature)
        if unit_norm in {"C", "°C", "DEGC"}:
            return float(temperature) * 9.0 / 5.0 + 32.0
        raise ValidationError("temperature_unit must be either 'F' or 'C'.")

    @staticmethod
    def _kd_polynomial(temperature_f: float) -> float:
        tf = float(temperature_f)
        return (
            0.975
            + 0.432e-3 * tf
            - 0.115e-5 * tf**2
            + 0.104e-8 * tf**3
            - 0.595e-12 * tf**4
        )

    @staticmethod
    def _se_from_sut_eq_6_8(sut_kpsi: float) -> tuple[float, str]:
        if sut_kpsi <= 200.0:
            return 0.5 * sut_kpsi, "eq_6_8_low_strength_branch"
        return 100.0, "eq_6_8_high_strength_branch"

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"TemperatureFactorSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        temperature_value = coalesce(
            inputs.get("service_temperature"),
            inputs.get("service_temperature_F"),
            inputs.get("service_temperature_C"),
        )
        if temperature_value is None:
            raise ValidationError("service_temperature is required for solve_path='temperature_factor'.")

        if inputs.get("service_temperature_F") is not None:
            service_temperature_f = float(inputs["service_temperature_F"])
        elif inputs.get("service_temperature_C") is not None:
            service_temperature_f = self._to_fahrenheit(float(inputs["service_temperature_C"]), "C")
        else:
            temperature_unit = coalesce(inputs.get("temperature_unit"), "F")
            service_temperature_f = self._to_fahrenheit(float(temperature_value), str(temperature_unit))

        if not (70.0 <= service_temperature_f <= 1000.0):
            raise RangeError("Eq. (6-27) and Table 6-4 are intended for 70 <= T_F <= 1000 °F.")

        sut_rt_kpsi = coalesce(
            inputs.get("sut_room_temperature_kpsi"),
            inputs.get("sut_kpsi"),
            inputs.get("ultimate_tensile_strength_room_temperature_kpsi"),
        )
        sut_rt_mpa = coalesce(
            inputs.get("sut_room_temperature_MPa"),
            inputs.get("sut_MPa"),
            inputs.get("ultimate_tensile_strength_room_temperature_MPa"),
        )

        if sut_rt_kpsi is None and sut_rt_mpa is None:
            raise ValidationError(
                "Room-temperature tensile strength is required. Provide sut_room_temperature_kpsi or sut_room_temperature_MPa."
            )

        if sut_rt_kpsi is None:
            sut_rt_kpsi = mpa_to_kpsi(float(sut_rt_mpa))
        else:
            sut_rt_kpsi = float(sut_rt_kpsi)

        if sut_rt_mpa is None:
            sut_rt_mpa = kpsi_to_mpa(float(sut_rt_kpsi))
        else:
            sut_rt_mpa = float(sut_rt_mpa)

        kd_poly = self._kd_polynomial(service_temperature_f)
        table_ratio = self.repository.table_6_4_ratio_from_f(service_temperature_f)
        kd_table = table_ratio["st_over_srt"]

        cases = inputs.get("cases") or []
        if not cases:
            cases = [
                {
                    "name": "known_room_temperature_endurance_limit",
                    "case_type": "known_room_temperature_endurance_limit",
                    "temperature_factor_method": "polynomial",
                    "se_prime_room_temperature_kpsi": inputs.get("se_prime_room_temperature_kpsi"),
                },
                {
                    "name": "only_room_temperature_tensile_strength_known",
                    "case_type": "only_room_temperature_tensile_strength_known",
                    "temperature_factor_method": "table_interpolation",
                },
            ]

        results: list[dict[str, Any]] = []
        verification: dict[str, Any] = {}
        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        expected_case_results = expected_ref.get("case_results", {})

        for case in cases:
            name = case.get("name") or "temperature_factor_case"
            case_type = str(coalesce(case.get("case_type"), case.get("mode"))).strip().lower()
            method = str(coalesce(case.get("temperature_factor_method"), "table_interpolation")).strip().lower()

            if method not in {"polynomial", "table_interpolation"}:
                raise ValidationError(
                    f"Case {name!r} has unsupported temperature_factor_method={method!r}. "
                    "Use 'polynomial' or 'table_interpolation'."
                )

            kd_used = kd_poly if method == "polynomial" else kd_table
            kd_source = "eq_6_27" if method == "polynomial" else "table_6_4_interpolated"

            if case_type == "known_room_temperature_endurance_limit":
                se_rt = coalesce(
                    case.get("se_prime_room_temperature_kpsi"),
                    inputs.get("se_prime_room_temperature_kpsi"),
                    inputs.get("se_room_temperature_kpsi"),
                )
                se_rt = ensure_positive(f"cases[{name}].se_prime_room_temperature_kpsi", se_rt)
                se_service = kd_used * se_rt
                result_item = {
                    "name": name,
                    "case_type": case_type,
                    "temperature_factor_method": method,
                    "k_d": safe_round(kd_used),
                    "k_d_source": kd_source,
                    "se_prime_room_temperature_kpsi": safe_round(se_rt),
                    "se_prime_room_temperature_MPa": safe_round(kpsi_to_mpa(se_rt)),
                    "se_at_service_temperature_kpsi": safe_round(se_service),
                    "se_at_service_temperature_MPa": safe_round(kpsi_to_mpa(se_service)),
                    "equation": "eq_6_28",
                }

            elif case_type == "only_room_temperature_tensile_strength_known":
                sut_service = kd_used * sut_rt_kpsi
                se_service, se_rule = self._se_from_sut_eq_6_8(sut_service)
                result_item = {
                    "name": name,
                    "case_type": case_type,
                    "temperature_factor_method": method,
                    "k_d": safe_round(kd_used),
                    "k_d_source": kd_source,
                    "sut_room_temperature_kpsi": safe_round(sut_rt_kpsi),
                    "sut_room_temperature_MPa": safe_round(sut_rt_mpa),
                    "sut_at_service_temperature_kpsi": safe_round(sut_service),
                    "sut_at_service_temperature_MPa": safe_round(kpsi_to_mpa(sut_service)),
                    "se_at_service_temperature_kpsi": safe_round(se_service),
                    "se_at_service_temperature_MPa": safe_round(kpsi_to_mpa(se_service)),
                    "equation": se_rule,
                }
            else:
                raise ValidationError(
                    f"Case {name!r} has unsupported case_type={case_type!r}. "
                    "Use 'known_room_temperature_endurance_limit' or 'only_room_temperature_tensile_strength_known'."
                )

            results.append(result_item)

            if name in expected_case_results:
                ref = expected_case_results[name]
                if "k_d" in ref:
                    verification[f"case::{name}::k_d"] = {
                        "actual": result_item["k_d"],
                        "reference": float(ref["k_d"]),
                        "relative_error_percent": safe_round(relative_error_percent(result_item["k_d"], float(ref["k_d"]))),
                    }
                if "se_at_service_temperature_kpsi" in ref:
                    verification[f"case::{name}::se_at_service_temperature_kpsi"] = {
                        "actual": result_item["se_at_service_temperature_kpsi"],
                        "reference": float(ref["se_at_service_temperature_kpsi"]),
                        "relative_error_percent": safe_round(
                            relative_error_percent(
                                result_item["se_at_service_temperature_kpsi"],
                                float(ref["se_at_service_temperature_kpsi"]),
                            )
                        ),
                    }
                if "sut_at_service_temperature_kpsi" in ref and "sut_at_service_temperature_kpsi" in result_item:
                    verification[f"case::{name}::sut_at_service_temperature_kpsi"] = {
                        "actual": result_item["sut_at_service_temperature_kpsi"],
                        "reference": float(ref["sut_at_service_temperature_kpsi"]),
                        "relative_error_percent": safe_round(
                            relative_error_percent(
                                result_item["sut_at_service_temperature_kpsi"],
                                float(ref["sut_at_service_temperature_kpsi"]),
                            )
                        ),
                    }

        output = {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Temperature factor analysis"),
            "inputs": inputs,
            "lookups": {
                "table_6_4": {
                    "temperature_f": safe_round(service_temperature_f),
                    "st_over_srt": safe_round(kd_table),
                    "source": table_ratio["source"],
                }
            },
            "derived": {
                "service_temperature_f": safe_round(service_temperature_f),
                "service_temperature_c": safe_round((service_temperature_f - 32.0) * 5.0 / 9.0),
                "sut_room_temperature_kpsi": safe_round(sut_rt_kpsi),
                "sut_room_temperature_MPa": safe_round(sut_rt_mpa),
                "k_d_from_eq_6_27": safe_round(kd_poly),
                "k_d_from_table_6_4": safe_round(kd_table),
                "eq_6_27": "k_d = 0.975 + 0.432e-3*T_F - 0.115e-5*T_F^2 + 0.104e-8*T_F^3 - 0.595e-12*T_F^4",
                "eq_6_28": "k_d = S_T / S_RT",
            },
            "results": {
                "cases": results,
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-8", "6-27", "6-28"],
                "notes": [
                    "This solver targets Example 6-5 style Marin temperature-factor calculations.",
                    "When the room-temperature endurance limit is known by test, compute k_d from Eq. (6-27) or Table 6-4 and multiply by the known room-temperature endurance limit.",
                    "When only room-temperature tensile strength is known, first estimate the temperature-corrected tensile strength using Table 6-4 or Eq. (6-27), then estimate endurance limit using Eq. (6-8), and use k_d = 1 thereafter as in the textbook discussion.",
                ],
            },
        }
        if verification:
            output["verification"] = verification
        return output


class CyclesToFailureSolver:
    """Implements Shigley Chapter 6 Example 6-7 style cycles-to-failure calculations."""

    solve_path = "cycles_to_failure"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    def _resolve_strengths(self, inputs: dict[str, Any]) -> dict[str, Any]:
        sut_mpa = coalesce(
            inputs.get("sut_MPa"),
            inputs.get("ultimate_tensile_strength_MPa"),
            inputs.get("mean_ultimate_tensile_strength_MPa"),
        )
        sut_kpsi = coalesce(
            inputs.get("sut_kpsi"),
            inputs.get("ultimate_tensile_strength_kpsi"),
            inputs.get("mean_ultimate_tensile_strength_kpsi"),
        )

        if sut_mpa is None and sut_kpsi is None:
            raise ValidationError(
                "Ultimate tensile strength is required for solve_path='cycles_to_failure'. "
                "Provide sut_MPa or sut_kpsi."
            )

        if sut_mpa is not None and sut_kpsi is not None:
            return {"sut_MPa": float(sut_mpa), "sut_kpsi": float(sut_kpsi), "source": "user_input_both_units"}
        if sut_mpa is not None:
            return {"sut_MPa": float(sut_mpa), "sut_kpsi": mpa_to_kpsi(float(sut_mpa)), "source": "user_input_MPa"}
        return {"sut_MPa": kpsi_to_mpa(float(sut_kpsi)), "sut_kpsi": float(sut_kpsi), "source": "user_input_kpsi"}

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"CyclesToFailureSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        strengths = self._resolve_strengths(inputs)
        se_mpa = coalesce(inputs.get("Se_MPa"), inputs.get("se_MPa"), inputs.get("endurance_limit_MPa"))
        se_kpsi = coalesce(inputs.get("Se_kpsi"), inputs.get("se_kpsi"), inputs.get("endurance_limit_kpsi"))

        if se_mpa is None and se_kpsi is None:
            raise ValidationError(
                "Fully corrected endurance limit is required for solve_path='cycles_to_failure'. "
                "Provide Se_MPa or Se_kpsi."
            )
        if se_mpa is not None and se_kpsi is not None:
            se_mpa = float(se_mpa)
            se_kpsi = float(se_kpsi)
        elif se_mpa is not None:
            se_mpa = float(se_mpa)
            se_kpsi = mpa_to_kpsi(se_mpa)
        else:
            se_kpsi = float(se_kpsi)
            se_mpa = kpsi_to_mpa(se_kpsi)

        sigma_nom_mpa = coalesce(
            inputs.get("sigma_rev_nom_MPa"),
            inputs.get("sigma_rev_nominal_MPa"),
            inputs.get("sigma_nominal_reversing_MPa"),
        )
        sigma_nom_kpsi = coalesce(
            inputs.get("sigma_rev_nom_kpsi"),
            inputs.get("sigma_rev_nominal_kpsi"),
            inputs.get("sigma_nominal_reversing_kpsi"),
        )
        if sigma_nom_mpa is None and sigma_nom_kpsi is None:
            raise ValidationError(
                "Nominal fully reversing stress is required. "
                "Provide sigma_rev_nom_MPa or sigma_rev_nom_kpsi."
            )
        if sigma_nom_mpa is not None and sigma_nom_kpsi is not None:
            sigma_nom_mpa = float(sigma_nom_mpa)
            sigma_nom_kpsi = float(sigma_nom_kpsi)
        elif sigma_nom_mpa is not None:
            sigma_nom_mpa = float(sigma_nom_mpa)
            sigma_nom_kpsi = mpa_to_kpsi(sigma_nom_mpa)
        else:
            sigma_nom_kpsi = float(sigma_nom_kpsi)
            sigma_nom_mpa = kpsi_to_mpa(sigma_nom_kpsi)

        K_f = ensure_positive("K_f", coalesce(inputs.get("K_f"), inputs.get("kf"), inputs.get("fatigue_stress_concentration_factor")))
        n_low = ensure_at_least("sn_low_cycle_anchor_cycles", inputs.get("sn_low_cycle_anchor_cycles", 1.0e3), 1.0)
        n_endurance = ensure_at_least("endurance_limit_cycles", inputs.get("endurance_limit_cycles", 1.0e6), n_low)

        sigma_local_mpa = K_f * sigma_nom_mpa
        sigma_local_kpsi = K_f * sigma_nom_kpsi

        f_override = inputs.get("fatigue_strength_fraction_f_override")
        if f_override is not None:
            f_lookup = {
                "f": float(f_override),
                "source": "user_override",
                "note": "User provided fatigue_strength_fraction_f_override.",
            }
        else:
            f_lookup = self.repository.fatigue_strength_fraction_from_figure_6_18(strengths["sut_kpsi"])

        f_value = ensure_positive("fatigue_strength_fraction_f", f_lookup["f"])
        sf_low_kpsi = f_value * strengths["sut_kpsi"]
        sf_low_mpa = kpsi_to_mpa(sf_low_kpsi)

        if math.isclose(n_endurance, n_low, rel_tol=0.0, abs_tol=1e-12):
            raise ValidationError("endurance_limit_cycles must be different from sn_low_cycle_anchor_cycles.")

        b = log10(se_kpsi / sf_low_kpsi) / log10(n_endurance / n_low)
        if math.isclose(b, 0.0, rel_tol=0.0, abs_tol=1e-15):
            raise ValidationError("Resolved exponent b is zero, so the S-N relation would be singular.")
        a_kpsi = sf_low_kpsi / (n_low ** b)
        a_mpa = kpsi_to_mpa(a_kpsi)

        life_regime = "finite_life"
        if sigma_local_kpsi <= se_kpsi:
            life_regime = "endurance_or_infinite_life"
            cycles = math.inf
        else:
            cycles = (sigma_local_kpsi / a_kpsi) ** (1.0 / b)

        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        verification: dict[str, Any] = {}
        for key, actual in {
            "fatigue_strength_fraction_f": f_value,
            "a_kpsi": a_kpsi,
            "b": b,
            "sigma_rev_local_kpsi": sigma_local_kpsi,
            "sigma_rev_local_MPa": sigma_local_mpa,
            "cycles_to_failure": None if math.isinf(cycles) else cycles,
        }.items():
            if key in expected_ref and actual is not None:
                verification[key] = {
                    "actual": safe_round(actual),
                    "reference": float(expected_ref[key]),
                    "relative_error_percent": safe_round(relative_error_percent(actual, float(expected_ref[key]))),
                }

        output = {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Cycles to failure analysis"),
            "inputs": inputs,
            "lookups": {
                "figure_6_18": {
                    "sut_kpsi_for_lookup": safe_round(strengths["sut_kpsi"]),
                    "fatigue_strength_fraction_f": safe_round(f_value),
                    "source": f_lookup.get("source"),
                    "note": f_lookup.get("note"),
                }
            },
            "derived": {
                "sut_MPa": safe_round(strengths["sut_MPa"]),
                "sut_kpsi": safe_round(strengths["sut_kpsi"]),
                "Se_MPa": safe_round(se_mpa),
                "Se_kpsi": safe_round(se_kpsi),
                "K_f": safe_round(K_f),
                "sigma_rev_nom_MPa": safe_round(sigma_nom_mpa),
                "sigma_rev_nom_kpsi": safe_round(sigma_nom_kpsi),
                "sigma_rev_local_MPa": safe_round(sigma_local_mpa),
                "sigma_rev_local_kpsi": safe_round(sigma_local_kpsi),
                "fatigue_strength_fraction_f": safe_round(f_value),
                "sf_at_1e3_cycles_kpsi": safe_round(sf_low_kpsi),
                "sf_at_1e3_cycles_MPa": safe_round(sf_low_mpa),
                "sn_low_cycle_anchor_cycles": safe_round(n_low),
                "endurance_limit_cycles": safe_round(n_endurance),
                "a_kpsi": safe_round(a_kpsi),
                "a_MPa": safe_round(a_mpa),
                "b": safe_round(b),
                "sn_equation_kpsi": f"S_f = {safe_round(a_kpsi)} * N^({safe_round(b)})",
                "sn_equation_MPa": f"S_f = {safe_round(a_mpa)} * N^({safe_round(b)})",
            },
            "results": {
                "life_regime": life_regime,
                "cycles_to_failure": None if math.isinf(cycles) else safe_round(cycles),
                "cycles_to_failure_note": (
                    f"Predicted life is at least {int(n_endurance):d} cycles because the local fully reversed stress does not exceed Se."
                    if math.isinf(cycles)
                    else None
                ),
                "equations": ["6-8", "6-13", "6-16"],
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-8", "6-13", "6-16"],
                "notes": [
                    "This solver targets Example 6-7 style fully reversed life calculations.",
                    "The local fully reversed stress is computed from K_f times the nominal fully reversed stress.",
                    "The finite-life S-N line is fit between f*Sut at 10^3 cycles and the fully corrected endurance limit Se at 10^6 cycles.",
                    "If the local fully reversed stress is less than or equal to Se, the result is reported as endurance or infinite life.",
                ],
            },
        }
        if verification:
            output["verification"] = verification
        return output

class StressConcentrationNotchSensitivitySolver:
    """Implements Shigley Chapter 6 Example 6-6 for K_t, q, and K_f in bending."""

    solve_path = "stress_concentration_notch_sensitivity"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    def _resolve_strengths(self, inputs: dict[str, Any]) -> dict[str, Any]:
        sut_mpa = coalesce(
            inputs.get("sut_MPa"),
            inputs.get("ultimate_tensile_strength_MPa"),
            inputs.get("mean_ultimate_tensile_strength_MPa"),
        )
        sut_kpsi = coalesce(
            inputs.get("sut_kpsi"),
            inputs.get("ultimate_tensile_strength_kpsi"),
            inputs.get("mean_ultimate_tensile_strength_kpsi"),
        )
        if sut_mpa is None and sut_kpsi is None:
            raise ValidationError(
                "Ultimate tensile strength is required for solve_path='stress_concentration_notch_sensitivity'. "
                "Provide sut_MPa or sut_kpsi."
            )
        if sut_mpa is not None and sut_kpsi is not None:
            return {"sut_MPa": float(sut_mpa), "sut_kpsi": float(sut_kpsi), "source": "user_input_both_units"}
        if sut_mpa is not None:
            return {"sut_MPa": float(sut_mpa), "sut_kpsi": mpa_to_kpsi(float(sut_mpa)), "source": "user_input_MPa"}
        return {"sut_MPa": kpsi_to_mpa(float(sut_kpsi)), "sut_kpsi": float(sut_kpsi), "source": "user_input_kpsi"}

    @staticmethod
    def _sqrt_a_bending_in(sut_kpsi: float) -> float:
        sut = float(sut_kpsi)
        return 0.246 - 3.08e-3 * sut + 1.51e-5 * sut**2 - 2.67e-8 * sut**3

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"StressConcentrationNotchSensitivitySolver received solve_path={inputs.get('solve_path')!r}; "
                f"expected {self.solve_path!r}."
            )

        strengths = self._resolve_strengths(inputs)

        d_mm = ensure_positive("small_diameter_mm", coalesce(inputs.get("small_diameter_mm"), inputs.get("d_mm"), inputs.get("diameter_small_mm")))
        D_mm = ensure_positive("large_diameter_mm", coalesce(inputs.get("large_diameter_mm"), inputs.get("D_mm"), inputs.get("diameter_large_mm")))
        r_mm = ensure_positive("fillet_radius_mm", coalesce(inputs.get("fillet_radius_mm"), inputs.get("r_mm"), inputs.get("notch_radius_mm")))

        if D_mm <= d_mm:
            raise ValidationError(f"large_diameter_mm must be greater than small_diameter_mm. Got D={D_mm} and d={d_mm}.")

        D_over_d = D_mm / d_mm
        r_over_d = r_mm / d_mm
        r_in = mm_to_in(r_mm)

        kt_lookup = self.repository.stress_concentration_kt_shoulder_bending(D_over_d=D_over_d, r_over_d=r_over_d)
        K_t = float(kt_lookup["K_t"])

        q_chart_lookup = self.repository.notch_sensitivity_q_bending(
            sut_kpsi=strengths["sut_kpsi"],
            r_in=r_in,
        )
        q_chart = float(q_chart_lookup["q"])
        K_f_chart = 1.0 + q_chart * (K_t - 1.0)

        sqrt_a_in = self._sqrt_a_bending_in(strengths["sut_kpsi"])
        sqrt_a_mm = sqrt_a_in * math.sqrt(25.4)
        q_eq = 1.0 / (1.0 + sqrt_a_mm / math.sqrt(r_mm))
        K_f_eq = 1.0 + (K_t - 1.0) / (1.0 + sqrt_a_mm / math.sqrt(r_mm))

        results_cases = [
            {
                "name": "part_a_from_figure_6_20",
                "method": "figure_6_20",
                "q": safe_round(q_chart),
                "K_f": safe_round(K_f_chart),
                "equations": ["6-32"],
            },
            {
                "name": "part_b_from_eq_6_33_and_6_35a",
                "method": "eq_6_33_and_6_35a",
                "sqrt_a_sqrt_in": safe_round(sqrt_a_in),
                "sqrt_a_sqrt_mm": safe_round(sqrt_a_mm),
                "q": safe_round(q_eq),
                "K_f": safe_round(K_f_eq),
                "equations": ["6-33", "6-34", "6-35a"],
            },
        ]

        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        verification: dict[str, Any] = {}
        if "K_t" in expected_ref:
            verification["K_t"] = {
                "actual": safe_round(K_t),
                "reference": float(expected_ref["K_t"]),
                "relative_error_percent": safe_round(relative_error_percent(K_t, float(expected_ref["K_t"]))),
            }
        if "part_a" in expected_ref:
            ref = expected_ref["part_a"]
            if "q" in ref:
                verification["part_a::q"] = {
                    "actual": safe_round(q_chart),
                    "reference": float(ref["q"]),
                    "relative_error_percent": safe_round(relative_error_percent(q_chart, float(ref["q"]))),
                }
            if "K_f" in ref:
                verification["part_a::K_f"] = {
                    "actual": safe_round(K_f_chart),
                    "reference": float(ref["K_f"]),
                    "relative_error_percent": safe_round(relative_error_percent(K_f_chart, float(ref["K_f"]))),
                }
        if "part_b" in expected_ref:
            ref = expected_ref["part_b"]
            if "sqrt_a_sqrt_in" in ref:
                verification["part_b::sqrt_a_sqrt_in"] = {
                    "actual": safe_round(sqrt_a_in),
                    "reference": float(ref["sqrt_a_sqrt_in"]),
                    "relative_error_percent": safe_round(relative_error_percent(sqrt_a_in, float(ref["sqrt_a_sqrt_in"]))),
                }
            if "sqrt_a_sqrt_mm" in ref:
                verification["part_b::sqrt_a_sqrt_mm"] = {
                    "actual": safe_round(sqrt_a_mm),
                    "reference": float(ref["sqrt_a_sqrt_mm"]),
                    "relative_error_percent": safe_round(relative_error_percent(sqrt_a_mm, float(ref["sqrt_a_sqrt_mm"]))),
                }
            if "q" in ref:
                verification["part_b::q"] = {
                    "actual": safe_round(q_eq),
                    "reference": float(ref["q"]),
                    "relative_error_percent": safe_round(relative_error_percent(q_eq, float(ref["q"]))),
                }
            if "K_f" in ref:
                verification["part_b::K_f"] = {
                    "actual": safe_round(K_f_eq),
                    "reference": float(ref["K_f"]),
                    "relative_error_percent": safe_round(relative_error_percent(K_f_eq, float(ref["K_f"]))),
                }

        output = {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Stress concentration and notch sensitivity analysis"),
            "inputs": inputs,
            "lookups": {
                "table_a_15_9": kt_lookup,
                "figure_6_20": q_chart_lookup,
            },
            "derived": {
                "sut_MPa": safe_round(strengths["sut_MPa"]),
                "sut_kpsi": safe_round(strengths["sut_kpsi"]),
                "small_diameter_mm": safe_round(d_mm),
                "large_diameter_mm": safe_round(D_mm),
                "fillet_radius_mm": safe_round(r_mm),
                "small_diameter_in": safe_round(mm_to_in(d_mm)),
                "large_diameter_in": safe_round(mm_to_in(D_mm)),
                "fillet_radius_in": safe_round(r_in),
                "D_over_d": safe_round(D_over_d),
                "r_over_d": safe_round(r_over_d),
                "K_t": safe_round(K_t),
                "sqrt_a_sqrt_in_from_eq_6_35a": safe_round(sqrt_a_in),
                "sqrt_a_sqrt_mm_from_eq_6_35a": safe_round(sqrt_a_mm),
                "q_from_eq_6_34_using_mm": safe_round(q_eq),
                "K_f_from_eq_6_33_using_mm": safe_round(K_f_eq),
            },
            "results": {
                "cases": results_cases,
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-32", "6-33", "6-34", "6-35a"],
                "notes": [
                    "This solver targets Example 6-6 style stress concentration and notch sensitivity calculations for a round shaft shoulder fillet in bending.",
                    "K_t is interpolated from table_a_15_9.json using D/d and r/d.",
                    "Part (a) uses Figure 6-20 to interpolate q for steels in bending/axial loading.",
                    "Part (b) uses Eq. (6-35a) for the Neuber constant and Eq. (6-33) or Eq. (6-34).",
                    "Eq. (6-35a) requires S_ut in kpsi.",
                ],
            },
        }
        if verification:
            output["verification"] = verification
        return output


class EnduranceLimitAndFatigueStrengthSolver:
    """Implements Shigley Chapter 6 Example 6-8 for endurance limit and finite-life fatigue strength."""

    solve_path = "endurance_limit_and_fatigue_strength"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    def _resolve_material(self, inputs: dict[str, Any]) -> SteelRecord:
        sae_aisi_no = coalesce(inputs.get("sae_aisi_no"), inputs.get("steel_grade"))
        processing = coalesce(inputs.get("processing"), inputs.get("material_processing"))
        if sae_aisi_no is None:
            raise ValidationError(
                "sae_aisi_no is required for solve_path='endurance_limit_and_fatigue_strength'."
            )
        return self.repository.find_steel_record(sae_aisi_no=sae_aisi_no, processing=processing)

    def _resolve_temperature_f(self, inputs: dict[str, Any]) -> float:
        if inputs.get("service_temperature_F") is not None:
            return float(inputs["service_temperature_F"])
        if inputs.get("service_temperature_C") is not None:
            return float(inputs["service_temperature_C"]) * 9.0 / 5.0 + 32.0
        temp = inputs.get("service_temperature")
        unit = str(coalesce(inputs.get("temperature_unit"), "F")).strip().upper()
        if temp is None:
            raise ValidationError("service_temperature_F or service_temperature_C is required.")
        if unit in {"F", "°F", "DEGF"}:
            return float(temp)
        if unit in {"C", "°C", "DEGC"}:
            return float(temp) * 9.0 / 5.0 + 32.0
        raise ValidationError("temperature_unit must be either 'F' or 'C'.")

    def _resolve_diameter(self, inputs: dict[str, Any]) -> dict[str, float]:
        diameter_in = coalesce(inputs.get("diameter_in"), inputs.get("bar_diameter_in"))
        diameter_mm = coalesce(inputs.get("diameter_mm"), inputs.get("bar_diameter_mm"))
        if diameter_in is None and diameter_mm is None:
            raise ValidationError("diameter_in or diameter_mm is required.")
        if diameter_in is not None and diameter_mm is not None:
            return {"diameter_in": float(diameter_in), "diameter_mm": float(diameter_mm), "source": "user_input_both_units"}
        if diameter_in is not None:
            return {"diameter_in": float(diameter_in), "diameter_mm": in_to_mm(float(diameter_in)), "source": "user_input_in"}
        return {"diameter_in": mm_to_in(float(diameter_mm)), "diameter_mm": float(diameter_mm), "source": "user_input_mm"}

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"EnduranceLimitAndFatigueStrengthSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        record = self._resolve_material(inputs)
        temp_f = self._resolve_temperature_f(inputs)
        diameter = self._resolve_diameter(inputs)
        cycles = ensure_positive("cycles_to_failure", coalesce(inputs.get("cycles_to_failure"), inputs.get("cycles"), inputs.get("target_cycles")))
        reliability_percent = ensure_positive("reliability_percent", inputs.get("reliability_percent"))
        surface_finish = coalesce(inputs.get("surface_finish"), "Machined or cold-drawn")
        loading_type = str(coalesce(inputs.get("loading_type"), "axial")).strip().lower()
        misc_factor = float(coalesce(inputs.get("miscellaneous_factor_k_f"), inputs.get("misc_factor"), 1.0))
        size_factor_override = inputs.get("size_factor_k_b")
        load_factor_override = inputs.get("load_factor_k_c")
        temp_factor_override = inputs.get("temperature_factor_k_d")
        reliability_factor_override = inputs.get("reliability_factor_k_e")

        if loading_type not in {"axial", "bending", "torsion"}:
            raise ValidationError("loading_type must be one of: axial, bending, torsion.")

        sut_room_kpsi = record.tensile_strength_kpsi
        sut_room_mpa = record.tensile_strength_MPa

        temp_lookup = self.repository.table_6_4_ratio_from_f(temp_f)
        st_over_srt = float(temp_lookup["st_over_srt"])
        sut_temp_kpsi = st_over_srt * sut_room_kpsi
        sut_temp_mpa = kpsi_to_mpa(sut_temp_kpsi)

        if sut_temp_kpsi <= 200.0:
            se_prime_kpsi = 0.5 * sut_temp_kpsi
            se_prime_rule = "eq_6_8_low_strength_branch"
        else:
            se_prime_kpsi = 100.0
            se_prime_rule = "eq_6_8_high_strength_branch"
        se_prime_mpa = kpsi_to_mpa(se_prime_kpsi)

        finish_record = self.repository.find_surface_finish_record(str(surface_finish))
        strength_unit = str(coalesce(inputs.get("surface_factor_strength_unit"), "kpsi")).strip().lower()
        if strength_unit == "mpa":
            ka = finish_record.a_factor_MPa * (sut_temp_mpa ** finish_record.b_exponent)
            ka_expression = f"k_a = {safe_round(finish_record.a_factor_MPa)} * Sut^({safe_round(finish_record.b_exponent)}) [MPa]"
            ka_strength_used = sut_temp_mpa
        else:
            ka = finish_record.a_factor_kpsi * (sut_temp_kpsi ** finish_record.b_exponent)
            ka_expression = f"k_a = {safe_round(finish_record.a_factor_kpsi)} * Sut^({safe_round(finish_record.b_exponent)}) [kpsi]"
            ka_strength_used = sut_temp_kpsi

        if size_factor_override is not None:
            kb = float(size_factor_override)
            kb_source = "user_override"
        elif loading_type == "axial":
            kb = 1.0
            kb_source = "eq_6_21_axial"
        else:
            d_mm = diameter["diameter_mm"]
            if 2.79 <= d_mm <= 51.0:
                kb = (d_mm / 7.62) ** (-0.107)
                kb_source = "eq_6_20_metric_small_diameter_branch"
            elif 51.0 < d_mm <= 254.0:
                kb = 1.51 * (d_mm ** (-0.157))
                kb_source = "eq_6_20_metric_large_diameter_branch"
            else:
                raise RangeError(f"Diameter {d_mm} mm is outside the supported Eq. (6-20) range.")

        if load_factor_override is not None:
            kc = float(load_factor_override)
            kc_source = "user_override"
        elif loading_type == "axial":
            kc = 0.85
            kc_source = "eq_6_26_axial"
        elif loading_type == "bending":
            kc = 1.0
            kc_source = "eq_6_26_bending"
        else:
            kc = 0.59
            kc_source = "eq_6_26_torsion"

        if temp_factor_override is not None:
            kd = float(temp_factor_override)
            kd_source = "user_override"
        else:
            kd = 1.0
            kd_source = "example_6_8_policy"

        if reliability_factor_override is not None:
            ke = float(reliability_factor_override)
            ke_lookup = {
                "reliability_percent": float(reliability_percent),
                "reliability_factor_k_e": ke,
                "source": "user_override",
            }
        else:
            ke_lookup = self.repository.reliability_factor_from_table_6_5(reliability_percent)
            ke = float(ke_lookup["reliability_factor_k_e"])

        se_part_kpsi = ka * kb * kc * kd * ke * misc_factor * se_prime_kpsi
        se_part_mpa = kpsi_to_mpa(se_part_kpsi)

        f_override = inputs.get("fatigue_strength_fraction_f_override")
        if f_override is not None:
            f_lookup = {
                "f": float(f_override),
                "source": "user_override",
                "note": "User provided fatigue_strength_fraction_f_override.",
            }
        else:
            f_lookup = self.repository.fatigue_strength_fraction_from_figure_6_18(sut_temp_kpsi)

        f_value = float(f_lookup["f"])
        sf_low_kpsi = f_value * sut_temp_kpsi
        sf_low_mpa = kpsi_to_mpa(sf_low_kpsi)
        n_low = 1.0e3
        n_endurance = 1.0e6
        a_kpsi = (sf_low_kpsi ** 2) / se_part_kpsi
        b = log10(se_part_kpsi / sf_low_kpsi) / log10(n_endurance / n_low)
        a_mpa = kpsi_to_mpa(a_kpsi)

        fatigue_strength_kpsi = a_kpsi * (cycles ** b)
        fatigue_strength_mpa = kpsi_to_mpa(fatigue_strength_kpsi)

        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        verification: dict[str, Any] = {}
        for key, actual in {
            "st_over_srt": st_over_srt,
            "sut_at_service_temperature_kpsi": sut_temp_kpsi,
            "se_prime_kpsi": se_prime_kpsi,
            "ka": ka,
            "kb": kb,
            "kc": kc,
            "kd": kd,
            "ke": ke,
            "endurance_limit_kpsi": se_part_kpsi,
            "fatigue_strength_fraction_f": f_value,
            "a_kpsi": a_kpsi,
            "b": b,
            "fatigue_strength_kpsi": fatigue_strength_kpsi,
        }.items():
            if key in expected_ref:
                verification[key] = {
                    "actual": safe_round(actual),
                    "reference": float(expected_ref[key]),
                    "relative_error_percent": safe_round(relative_error_percent(actual, float(expected_ref[key]))),
                }

        return {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Endurance limit and fatigue strength analysis"),
            "inputs": inputs,
            "lookups": {
                "table_a_20": record.to_dict(),
                "table_6_4": temp_lookup,
                "table_6_2": finish_record.to_dict(),
                "table_6_5": ke_lookup,
                "figure_6_18": {
                    "sut_kpsi_for_lookup": safe_round(sut_temp_kpsi),
                    "fatigue_strength_fraction_f": safe_round(f_value),
                    "source": f_lookup.get("source"),
                    "note": f_lookup.get("note"),
                },
            },
            "derived": {
                "service_temperature_f": safe_round(temp_f),
                "service_temperature_c": safe_round((temp_f - 32.0) * 5.0 / 9.0),
                "diameter_in": safe_round(diameter["diameter_in"]),
                "diameter_mm": safe_round(diameter["diameter_mm"]),
                "sut_room_temperature_kpsi": safe_round(sut_room_kpsi),
                "sut_room_temperature_MPa": safe_round(sut_room_mpa),
                "st_over_srt": safe_round(st_over_srt),
                "sut_at_service_temperature_kpsi": safe_round(sut_temp_kpsi),
                "sut_at_service_temperature_MPa": safe_round(sut_temp_mpa),
                "se_prime_kpsi": safe_round(se_prime_kpsi),
                "se_prime_MPa": safe_round(se_prime_mpa),
                "se_prime_source": se_prime_rule,
                "surface_finish_normalized": normalize_surface_finish(str(surface_finish)),
                "ka": safe_round(ka),
                "ka_expression": ka_expression,
                "ka_strength_used": safe_round(ka_strength_used),
                "kb": safe_round(kb),
                "kb_source": kb_source,
                "kc": safe_round(kc),
                "kc_source": kc_source,
                "kd": safe_round(kd),
                "kd_source": kd_source,
                "ke": safe_round(ke),
                "miscellaneous_factor_k_f": safe_round(misc_factor),
                "endurance_limit_kpsi": safe_round(se_part_kpsi),
                "endurance_limit_MPa": safe_round(se_part_mpa),
                "fatigue_strength_fraction_f": safe_round(f_value),
                "sf_at_1e3_cycles_kpsi": safe_round(sf_low_kpsi),
                "sf_at_1e3_cycles_MPa": safe_round(sf_low_mpa),
                "a_kpsi": safe_round(a_kpsi),
                "a_MPa": safe_round(a_mpa),
                "b": safe_round(b),
                "sn_equation_kpsi": f"S_f = {safe_round(a_kpsi)} * N^({safe_round(b)})",
                "sn_equation_MPa": f"S_f = {safe_round(a_mpa)} * N^({safe_round(b)})",
            },
            "results": {
                "endurance_limit_kpsi": safe_round(se_part_kpsi),
                "endurance_limit_MPa": safe_round(se_part_mpa),
                "fatigue_strength_at_cycles_kpsi": safe_round(fatigue_strength_kpsi),
                "fatigue_strength_at_cycles_MPa": safe_round(fatigue_strength_mpa),
                "cycles": safe_round(cycles),
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-8", "6-18", "6-19", "6-21", "6-26", "6-13", "6-14", "6-15"],
                "notes": [
                    "This solver targets Example 6-8 style endurance-limit and finite-life fatigue-strength calculations.",
                    "The room-temperature ASTM minimum strength is fetched from Table A-20, then modified to service temperature using Table 6-4 before estimating S'e by Eq. (6-8).",
                    "Following Example 6-8, the temperature effect is absorbed into the modified Sut and S'e first, so k_d is taken as 1 thereafter.",
                    "The part endurance limit is computed from Eq. (6-18) using Marin factors k_a, k_b, k_c, k_d, k_e, and k_f (miscellaneous).",
                    "The finite-life S-N line is then built using f*Sut at 10^3 cycles and the corrected endurance limit at 10^6 cycles.",
                ],
            },
            **({"verification": verification} if verification else {}),
        }



class LifeOfPartSolver:
    """Implements Shigley Chapter 6 Example 6-9 style life-of-a-part calculations for a rotating shaft in reversed bending."""

    solve_path = "life_of_part"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    @staticmethod
    def _sqrt_a_bending_in(sut_kpsi: float) -> float:
        sut = float(sut_kpsi)
        return 0.246 - 3.08e-3 * sut + 1.51e-5 * sut**2 - 2.67e-8 * sut**3

    def _resolve_material(self, inputs: dict[str, Any]) -> SteelRecord:
        sae_aisi_no = coalesce(inputs.get("sae_aisi_no"), inputs.get("steel_grade"))
        processing = coalesce(inputs.get("processing"), inputs.get("material_processing"))
        if sae_aisi_no is None:
            raise ValidationError("sae_aisi_no is required for solve_path='life_of_part'.")
        return self.repository.find_steel_record(sae_aisi_no=sae_aisi_no, processing=processing)

    def _resolve_temperature_f(self, inputs: dict[str, Any]) -> float:
        if inputs.get("service_temperature_F") is not None:
            return float(inputs["service_temperature_F"])
        if inputs.get("service_temperature_C") is not None:
            return float(inputs["service_temperature_C"]) * 9.0 / 5.0 + 32.0
        return 70.0

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"LifeOfPartSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        record = self._resolve_material(inputs)
        surface_finish = coalesce(inputs.get("surface_finish"), "Machined or cold-drawn")
        d_mm = ensure_positive("small_diameter_mm", coalesce(inputs.get("small_diameter_mm"), inputs.get("d_mm"), inputs.get("diameter_small_mm")))
        D_mm = ensure_positive("large_diameter_mm", coalesce(inputs.get("large_diameter_mm"), inputs.get("D_mm"), inputs.get("diameter_large_mm")))
        r_mm = ensure_positive("fillet_radius_mm", coalesce(inputs.get("fillet_radius_mm"), inputs.get("r_mm"), inputs.get("notch_radius_mm")))
        M_B_N_m = ensure_positive("M_B_N_m", coalesce(inputs.get("M_B_N_m"), inputs.get("bending_moment_B_N_m"), inputs.get("moment_at_B_N_m")))
        reliability_percent = float(coalesce(inputs.get("reliability_percent"), 50.0))
        misc_factor = float(coalesce(inputs.get("miscellaneous_factor_k_f"), inputs.get("misc_factor"), 1.0))
        size_factor_override = inputs.get("size_factor_k_b")
        load_factor_override = inputs.get("load_factor_k_c")
        temp_factor_override = inputs.get("temperature_factor_k_d")
        reliability_factor_override = inputs.get("reliability_factor_k_e")
        fatigue_strength_fraction_f_override = inputs.get("fatigue_strength_fraction_f_override")
        stress_concentration_factor_override = inputs.get("K_t")
        fatigue_stress_concentration_factor_override = inputs.get("K_f")
        q_override = inputs.get("q")
        service_temperature_f = self._resolve_temperature_f(inputs)

        if D_mm <= d_mm:
            raise ValidationError(f"large_diameter_mm must be greater than small_diameter_mm. Got D={D_mm} and d={d_mm}.")

        sut_room_kpsi = record.tensile_strength_kpsi
        sut_room_mpa = record.tensile_strength_MPa
        sy_room_kpsi = record.yield_strength_kpsi
        sy_room_mpa = record.yield_strength_MPa

        if abs(service_temperature_f - 70.0) <= 1e-12:
            temp_lookup = {
                "temperature_f": 70.0,
                "st_over_srt": 1.0,
                "source": "room_temperature_default",
            }
            st_over_srt = 1.0
        else:
            temp_lookup = self.repository.table_6_4_ratio_from_f(service_temperature_f)
            st_over_srt = float(temp_lookup["st_over_srt"])

        sut_kpsi = st_over_srt * sut_room_kpsi
        sut_mpa = kpsi_to_mpa(sut_kpsi)
        sy_kpsi = st_over_srt * sy_room_kpsi
        sy_mpa = kpsi_to_mpa(sy_kpsi)

        if sut_kpsi <= 200.0:
            se_prime_kpsi = 0.5 * sut_kpsi
            se_prime_rule = "eq_6_8_low_strength_branch"
        else:
            se_prime_kpsi = 100.0
            se_prime_rule = "eq_6_8_high_strength_branch"
        se_prime_mpa = kpsi_to_mpa(se_prime_kpsi)

        finish_record = self.repository.find_surface_finish_record(str(surface_finish))
        ka = finish_record.a_factor_MPa * (sut_mpa ** finish_record.b_exponent)
        ka_expression = f"k_a = {safe_round(finish_record.a_factor_MPa)} * Sut^({safe_round(finish_record.b_exponent)}) [MPa]"

        if size_factor_override is not None:
            kb = float(size_factor_override)
            kb_source = "user_override"
        else:
            if 2.79 <= d_mm <= 51.0:
                kb = (d_mm / 7.62) ** (-0.107)
                kb_source = "eq_6_20_metric_small_diameter_branch"
            elif 51.0 < d_mm <= 254.0:
                kb = 1.51 * (d_mm ** (-0.157))
                kb_source = "eq_6_20_metric_large_diameter_branch"
            else:
                raise RangeError(f"Diameter {d_mm} mm is outside the supported Eq. (6-20) range.")

        if load_factor_override is not None:
            kc = float(load_factor_override)
            kc_source = "user_override"
        else:
            kc = 1.0
            kc_source = "eq_6_26_bending"

        if temp_factor_override is not None:
            kd = float(temp_factor_override)
            kd_source = "user_override"
        else:
            kd = 1.0
            kd_source = "room_temperature_or_absorbed_into_sut_policy"

        if reliability_factor_override is not None:
            ke = float(reliability_factor_override)
            ke_lookup = {
                "reliability_percent": float(reliability_percent),
                "reliability_factor_k_e": ke,
                "source": "user_override",
            }
        else:
            ke_lookup = self.repository.reliability_factor_from_table_6_5(reliability_percent)
            ke = float(ke_lookup["reliability_factor_k_e"])

        se_kpsi = ka * kb * kc * kd * ke * misc_factor * se_prime_kpsi
        se_mpa = kpsi_to_mpa(se_kpsi)

        D_over_d = D_mm / d_mm
        r_over_d = r_mm / d_mm
        r_in = mm_to_in(r_mm)

        if stress_concentration_factor_override is not None:
            kt_lookup = {
                "D_over_d": float(D_over_d),
                "r_over_d": float(r_over_d),
                "K_t": float(stress_concentration_factor_override),
                "source": "user_override",
                "intermediate_trace_values": None,
            }
            K_t = float(stress_concentration_factor_override)
        else:
            kt_lookup = self.repository.stress_concentration_kt_shoulder_bending(D_over_d=D_over_d, r_over_d=r_over_d)
            K_t = float(kt_lookup["K_t"])

        sqrt_a_in = self._sqrt_a_bending_in(sut_kpsi)
        sqrt_a_mm = sqrt_a_in * math.sqrt(25.4)

        if q_override is not None:
            q = float(q_override)
            q_source = "user_override"
        else:
            q = 1.0 / (1.0 + sqrt_a_mm / math.sqrt(r_mm))
            q_source = "eq_6_34_using_eq_6_35a"

        if fatigue_stress_concentration_factor_override is not None:
            K_f = float(fatigue_stress_concentration_factor_override)
            kf_source = "user_override"
        else:
            K_f = 1.0 + q * (K_t - 1.0)
            kf_source = "eq_6_33"

        section_modulus_mm3 = math.pi * d_mm**3 / 32.0
        sigma_rev_mpa = K_f * (M_B_N_m * 1000.0) / section_modulus_mm3
        sigma_rev_kpsi = mpa_to_kpsi(sigma_rev_mpa)

        if fatigue_strength_fraction_f_override is not None:
            f_lookup = {
                "f": float(fatigue_strength_fraction_f_override),
                "source": "user_override",
                "note": "User provided fatigue_strength_fraction_f_override.",
            }
        else:
            f_lookup = self.repository.fatigue_strength_fraction_from_figure_6_18(sut_kpsi)
        f_value = float(f_lookup["f"])

        sf_low_kpsi = f_value * sut_kpsi
        sf_low_mpa = kpsi_to_mpa(sf_low_kpsi)
        n_low = 1.0e3
        n_endurance = 1.0e6
        a_kpsi = (sf_low_kpsi ** 2) / se_kpsi
        a_mpa = kpsi_to_mpa(a_kpsi)
        b = log10(se_kpsi / sf_low_kpsi) / log10(n_endurance / n_low)

        if sigma_rev_kpsi <= se_kpsi:
            life_regime = "endurance_or_infinite_life"
            cycles_to_failure = math.inf
            cycles_note = f"Predicted life is at least {int(n_endurance):d} cycles because sigma_rev <= Se."
        else:
            life_regime = "finite_life"
            cycles_to_failure = (sigma_rev_kpsi / a_kpsi) ** (1.0 / b)
            cycles_note = None

        no_yield_on_first_cycle = sigma_rev_mpa < sy_mpa

        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        verification: dict[str, Any] = {}
        for key, actual in {
            "se_prime_MPa": se_prime_mpa,
            "ka": ka,
            "kb": kb,
            "kc": kc,
            "kd": kd,
            "ke": ke,
            "endurance_limit_MPa": se_mpa,
            "K_t": K_t,
            "sqrt_a_sqrt_in": sqrt_a_in,
            "sqrt_a_sqrt_mm": sqrt_a_mm,
            "q": q,
            "K_f": K_f,
            "sigma_rev_MPa": sigma_rev_mpa,
            "fatigue_strength_fraction_f": f_value,
            "a_MPa": a_mpa,
            "b": b,
            "cycles_to_failure": None if math.isinf(cycles_to_failure) else cycles_to_failure,
        }.items():
            if key in expected_ref and actual is not None:
                verification[key] = {
                    "actual": safe_round(actual),
                    "reference": float(expected_ref[key]),
                    "relative_error_percent": safe_round(relative_error_percent(actual, float(expected_ref[key]))),
                }

        return {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Life of a part analysis"),
            "inputs": inputs,
            "lookups": {
                "table_a_20": record.to_dict(),
                "table_6_4": temp_lookup,
                "table_6_2": finish_record.to_dict(),
                "table_6_5": ke_lookup,
                "table_a_15_9": kt_lookup,
                "figure_6_18": {
                    "sut_kpsi_for_lookup": safe_round(sut_kpsi),
                    "fatigue_strength_fraction_f": safe_round(f_value),
                    "source": f_lookup.get("source"),
                    "note": f_lookup.get("note"),
                },
            },
            "derived": {
                "service_temperature_f": safe_round(service_temperature_f),
                "service_temperature_c": safe_round((service_temperature_f - 32.0) * 5.0 / 9.0),
                "sut_room_temperature_kpsi": safe_round(sut_room_kpsi),
                "sut_room_temperature_MPa": safe_round(sut_room_mpa),
                "sy_room_temperature_kpsi": safe_round(sy_room_kpsi),
                "sy_room_temperature_MPa": safe_round(sy_room_mpa),
                "st_over_srt": safe_round(st_over_srt),
                "sut_at_service_temperature_kpsi": safe_round(sut_kpsi),
                "sut_at_service_temperature_MPa": safe_round(sut_mpa),
                "sy_at_service_temperature_kpsi": safe_round(sy_kpsi),
                "sy_at_service_temperature_MPa": safe_round(sy_mpa),
                "se_prime_kpsi": safe_round(se_prime_kpsi),
                "se_prime_MPa": safe_round(se_prime_mpa),
                "se_prime_source": se_prime_rule,
                "surface_finish_normalized": normalize_surface_finish(str(surface_finish)),
                "small_diameter_mm": safe_round(d_mm),
                "large_diameter_mm": safe_round(D_mm),
                "fillet_radius_mm": safe_round(r_mm),
                "small_diameter_in": safe_round(mm_to_in(d_mm)),
                "large_diameter_in": safe_round(mm_to_in(D_mm)),
                "fillet_radius_in": safe_round(r_in),
                "D_over_d": safe_round(D_over_d),
                "r_over_d": safe_round(r_over_d),
                "M_B_N_m": safe_round(M_B_N_m),
                "section_modulus_mm3": safe_round(section_modulus_mm3),
                "section_modulus_in3": safe_round(section_modulus_mm3 / (25.4**3)),
                "ka": safe_round(ka),
                "ka_expression": ka_expression,
                "kb": safe_round(kb),
                "kb_source": kb_source,
                "kc": safe_round(kc),
                "kc_source": kc_source,
                "kd": safe_round(kd),
                "kd_source": kd_source,
                "ke": safe_round(ke),
                "miscellaneous_factor_k_f": safe_round(misc_factor),
                "endurance_limit_kpsi": safe_round(se_kpsi),
                "endurance_limit_MPa": safe_round(se_mpa),
                "K_t": safe_round(K_t),
                "sqrt_a_sqrt_in": safe_round(sqrt_a_in),
                "sqrt_a_sqrt_mm": safe_round(sqrt_a_mm),
                "q": safe_round(q),
                "q_source": q_source,
                "K_f": safe_round(K_f),
                "K_f_source": kf_source,
                "sigma_rev_kpsi": safe_round(sigma_rev_kpsi),
                "sigma_rev_MPa": safe_round(sigma_rev_mpa),
                "fatigue_strength_fraction_f": safe_round(f_value),
                "sf_at_1e3_cycles_kpsi": safe_round(sf_low_kpsi),
                "sf_at_1e3_cycles_MPa": safe_round(sf_low_mpa),
                "a_kpsi": safe_round(a_kpsi),
                "a_MPa": safe_round(a_mpa),
                "b": safe_round(b),
                "sn_equation_kpsi": f"S_f = {safe_round(a_kpsi)} * N^({safe_round(b)})",
                "sn_equation_MPa": f"S_f = {safe_round(a_mpa)} * N^({safe_round(b)})",
            },
            "results": {
                "life_regime": life_regime,
                "cycles_to_failure": None if math.isinf(cycles_to_failure) else safe_round(cycles_to_failure),
                "cycles_to_failure_note": cycles_note,
                "no_yield_on_first_cycle": no_yield_on_first_cycle,
                "yield_check_ratio_sigma_rev_over_sy": safe_round(sigma_rev_mpa / sy_mpa),
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-8", "6-18", "6-19", "6-20", "6-26", "6-33", "6-34", "6-35a", "6-13", "6-14", "6-15", "6-16"],
                "notes": [
                    "This solver targets Example 6-9 style life calculations for a rotating shaft under a stationary transverse load, producing fully reversed bending stress at the critical section.",
                    "The human can analyze the beam statics separately and feed the bending moment at the critical section into the app, as requested.",
                    "K_t is interpolated from table_a_15_9.json using D/d and r/d, then K_f is computed using Eq. (6-35a), Eq. (6-34), and Eq. (6-33) unless overridden.",
                    "The local reversing bending stress is computed with sigma_rev = K_f * M / (I/c), where I/c = pi*d^3/32 for a round section.",
                    "The finite-life S-N line is built using f*Sut at 10^3 cycles and the corrected endurance limit at 10^6 cycles.",
                ],
            },
            **({"verification": verification} if verification else {}),
        }


def _repo_table_6_7_payload(self) -> dict[str, Any]:
    if getattr(self, "_table_6_7_payload", None) is None:
        self._table_6_7_payload = self._read_json("table_6_7.json")
    return self._table_6_7_payload


def _repo_table_6_8_payload(self) -> dict[str, Any]:
    if getattr(self, "_table_6_8_payload", None) is None:
        self._table_6_8_payload = self._read_json("table_6_8.json")
    return self._table_6_8_payload


DigitizedDataRepository.table_6_7_payload = property(_repo_table_6_7_payload)
DigitizedDataRepository.table_6_8_payload = property(_repo_table_6_8_payload)



class FatigueFactorOfSafetySolver:
    """Implements Shigley Chapter 6 Example 6-10 for fatigue factor of safety using Gerber and ASME-elliptic criteria."""

    solve_path = "fatigue_factor_of_safety"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    def _resolve_material(self, inputs: dict[str, Any]) -> SteelRecord:
        sae_aisi_no = coalesce(inputs.get("sae_aisi_no"), inputs.get("steel_grade"))
        processing = coalesce(inputs.get("processing"), inputs.get("material_processing"))
        if sae_aisi_no is None:
            raise ValidationError("sae_aisi_no is required for solve_path='fatigue_factor_of_safety'.")
        return self.repository.find_steel_record(sae_aisi_no=sae_aisi_no, processing=processing)

    def _resolve_temperature_f(self, inputs: dict[str, Any]) -> float:
        if inputs.get("service_temperature_F") is not None:
            return float(inputs["service_temperature_F"])
        if inputs.get("service_temperature_C") is not None:
            return float(inputs["service_temperature_C"]) * 9.0 / 5.0 + 32.0
        return 70.0

    def _resolve_diameter(self, inputs: dict[str, Any]) -> dict[str, float]:
        diameter_in = coalesce(inputs.get("diameter_in"), inputs.get("bar_diameter_in"))
        diameter_mm = coalesce(inputs.get("diameter_mm"), inputs.get("bar_diameter_mm"))
        if diameter_in is None and diameter_mm is None:
            raise ValidationError("diameter_in or diameter_mm is required.")
        if diameter_in is not None and diameter_mm is not None:
            return {"diameter_in": float(diameter_in), "diameter_mm": float(diameter_mm), "source": "user_input_both_units"}
        if diameter_in is not None:
            return {"diameter_in": float(diameter_in), "diameter_mm": in_to_mm(float(diameter_in)), "source": "user_input_in"}
        return {"diameter_in": mm_to_in(float(diameter_mm)), "diameter_mm": float(diameter_mm), "source": "user_input_mm"}

    def _resolve_local_stresses(self, inputs: dict[str, Any], diameter_in: float, K_f: float) -> dict[str, float]:
        sigma_a_kpsi = coalesce(inputs.get("sigma_a_kpsi"), inputs.get("stress_amplitude_kpsi"))
        sigma_m_kpsi = coalesce(inputs.get("sigma_m_kpsi"), inputs.get("mean_stress_kpsi"))
        sigma_a_nom_kpsi = coalesce(inputs.get("sigma_a_nom_kpsi"), inputs.get("nominal_stress_amplitude_kpsi"))
        sigma_m_nom_kpsi = coalesce(inputs.get("sigma_m_nom_kpsi"), inputs.get("nominal_mean_stress_kpsi"))

        if sigma_a_kpsi is not None and sigma_m_kpsi is not None:
            sigma_a_kpsi = float(sigma_a_kpsi)
            sigma_m_kpsi = float(sigma_m_kpsi)
            sigma_a_nom_kpsi = sigma_a_kpsi / K_f
            sigma_m_nom_kpsi = sigma_m_kpsi / K_f
            F_a_kip = sigma_a_nom_kpsi * math.pi * diameter_in**2 / 4.0
            F_m_kip = sigma_m_nom_kpsi * math.pi * diameter_in**2 / 4.0
            F_max_kip = F_m_kip + F_a_kip
            F_min_kip = F_m_kip - F_a_kip
            return {
                "F_min_kip": F_min_kip,
                "F_max_kip": F_max_kip,
                "F_a_kip": F_a_kip,
                "F_m_kip": F_m_kip,
                "sigma_a_nom_kpsi": sigma_a_nom_kpsi,
                "sigma_m_nom_kpsi": sigma_m_nom_kpsi,
                "sigma_a_kpsi": sigma_a_kpsi,
                "sigma_m_kpsi": sigma_m_kpsi,
            }

        if sigma_a_nom_kpsi is not None and sigma_m_nom_kpsi is not None:
            sigma_a_nom_kpsi = float(sigma_a_nom_kpsi)
            sigma_m_nom_kpsi = float(sigma_m_nom_kpsi)
            sigma_a_kpsi = K_f * sigma_a_nom_kpsi
            sigma_m_kpsi = K_f * sigma_m_nom_kpsi
            F_a_kip = sigma_a_nom_kpsi * math.pi * diameter_in**2 / 4.0
            F_m_kip = sigma_m_nom_kpsi * math.pi * diameter_in**2 / 4.0
            F_max_kip = F_m_kip + F_a_kip
            F_min_kip = F_m_kip - F_a_kip
            return {
                "F_min_kip": F_min_kip,
                "F_max_kip": F_max_kip,
                "F_a_kip": F_a_kip,
                "F_m_kip": F_m_kip,
                "sigma_a_nom_kpsi": sigma_a_nom_kpsi,
                "sigma_m_nom_kpsi": sigma_m_nom_kpsi,
                "sigma_a_kpsi": sigma_a_kpsi,
                "sigma_m_kpsi": sigma_m_kpsi,
            }

        load_min_kip = coalesce(inputs.get("load_min_kip"), inputs.get("P_min_kip"), inputs.get("F_min_kip"))
        load_max_kip = coalesce(inputs.get("load_max_kip"), inputs.get("P_max_kip"), inputs.get("F_max_kip"))
        if load_min_kip is None and load_max_kip is None:
            load_min_lbf = coalesce(inputs.get("load_min_lbf"), inputs.get("P_min_lbf"), inputs.get("F_min_lbf"))
            load_max_lbf = coalesce(inputs.get("load_max_lbf"), inputs.get("P_max_lbf"), inputs.get("F_max_lbf"))
            if load_min_lbf is not None or load_max_lbf is not None:
                load_min_kip = 0.001 * float(coalesce(load_min_lbf, 0.0))
                load_max_kip = 0.001 * float(coalesce(load_max_lbf, 0.0))

        if load_min_kip is None or load_max_kip is None:
            raise ValidationError(
                "Provide either load_min/load_max, nominal stresses, or local stresses for solve_path='fatigue_factor_of_safety'."
            )

        F_min_kip = float(load_min_kip)
        F_max_kip = float(load_max_kip)
        F_a_kip = 0.5 * (F_max_kip - F_min_kip)
        F_m_kip = 0.5 * (F_max_kip + F_min_kip)
        area_in2 = math.pi * diameter_in**2 / 4.0
        sigma_a_nom_kpsi = F_a_kip / area_in2
        sigma_m_nom_kpsi = F_m_kip / area_in2
        sigma_a_kpsi = K_f * sigma_a_nom_kpsi
        sigma_m_kpsi = K_f * sigma_m_nom_kpsi
        return {
            "F_min_kip": F_min_kip,
            "F_max_kip": F_max_kip,
            "F_a_kip": F_a_kip,
            "F_m_kip": F_m_kip,
            "sigma_a_nom_kpsi": sigma_a_nom_kpsi,
            "sigma_m_nom_kpsi": sigma_m_nom_kpsi,
            "sigma_a_kpsi": sigma_a_kpsi,
            "sigma_m_kpsi": sigma_m_kpsi,
        }

    @staticmethod
    def _get_row_by_criterion(payload: dict[str, Any], criterion: str) -> dict[str, Any]:
        for row in payload.get("rows", []):
            if row.get("criterion") == criterion and row.get("row_type") == "fatigue_criterion":
                return row
        raise DataLookupError(f"No fatigue_criterion row found for criterion={criterion!r}.")

    @staticmethod
    def _get_langer_row(payload: dict[str, Any]) -> dict[str, Any]:
        for row in payload.get("rows", []):
            if row.get("criterion") == "langer" and row.get("row_type") == "static_langer_criterion":
                return row
        raise DataLookupError("No static_langer_criterion row found.")

    @staticmethod
    def _get_crossover_row(payload: dict[str, Any]) -> dict[str, Any] | None:
        for row in payload.get("rows", []):
            if row.get("row_type") == "intersection_static_and_fatigue":
                return row
        return None

    @staticmethod
    def _eval_formula(expression: str, variables: dict[str, float]) -> float:
        text = str(expression).strip()
        if "=" in text:
            text = text.split("=", 1)[1].strip()
        return safe_eval_expression(text.replace("^", "**"), variables)

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"FatigueFactorOfSafetySolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        record = self._resolve_material(inputs)
        surface_finish = coalesce(inputs.get("surface_finish"), "Machined or cold-drawn")
        diameter = self._resolve_diameter(inputs)
        reliability_percent = float(coalesce(inputs.get("reliability_percent"), 50.0))
        service_temperature_f = self._resolve_temperature_f(inputs)
        misc_factor = float(coalesce(inputs.get("miscellaneous_factor_k_f"), inputs.get("misc_factor"), 1.0))
        K_f = ensure_positive("K_f", coalesce(inputs.get("K_f"), inputs.get("kf"), inputs.get("fatigue_stress_concentration_factor")))
        size_factor_override = inputs.get("size_factor_k_b")
        load_factor_override = inputs.get("load_factor_k_c")
        temp_factor_override = inputs.get("temperature_factor_k_d")
        reliability_factor_override = inputs.get("reliability_factor_k_e")

        sut_room_kpsi = record.tensile_strength_kpsi
        sut_room_mpa = record.tensile_strength_MPa
        sy_room_kpsi = record.yield_strength_kpsi
        sy_room_mpa = record.yield_strength_MPa

        if abs(service_temperature_f - 70.0) <= 1e-12:
            temp_lookup = {"temperature_f": 70.0, "st_over_srt": 1.0, "source": "room_temperature_default"}
            st_over_srt = 1.0
        else:
            temp_lookup = self.repository.table_6_4_ratio_from_f(service_temperature_f)
            st_over_srt = float(temp_lookup["st_over_srt"])

        sut_kpsi = st_over_srt * sut_room_kpsi
        sut_mpa = kpsi_to_mpa(sut_kpsi)
        sy_kpsi = st_over_srt * sy_room_kpsi
        sy_mpa = kpsi_to_mpa(sy_kpsi)

        if sut_kpsi <= 200.0:
            se_prime_kpsi = 0.5 * sut_kpsi
            se_prime_source = "eq_6_8_low_strength_branch"
        else:
            se_prime_kpsi = 100.0
            se_prime_source = "eq_6_8_high_strength_branch"
        se_prime_mpa = kpsi_to_mpa(se_prime_kpsi)

        finish_record = self.repository.find_surface_finish_record(str(surface_finish))
        ka = finish_record.a_factor_kpsi * (sut_kpsi ** finish_record.b_exponent)
        ka_expression = f"k_a = {safe_round(finish_record.a_factor_kpsi)} * Sut^({safe_round(finish_record.b_exponent)}) [kpsi]"

        if size_factor_override is not None:
            kb = float(size_factor_override)
            kb_source = "user_override"
        else:
            kb = 1.0
            kb_source = "eq_6_21_axial"

        if load_factor_override is not None:
            kc = float(load_factor_override)
            kc_source = "user_override"
        else:
            kc = 0.85
            kc_source = "eq_6_26_axial"

        if temp_factor_override is not None:
            kd = float(temp_factor_override)
            kd_source = "user_override"
        else:
            kd = 1.0
            kd_source = "room_temperature_or_absorbed_into_sut_policy"

        if reliability_factor_override is not None:
            ke = float(reliability_factor_override)
            ke_lookup = {
                "reliability_percent": float(reliability_percent),
                "reliability_factor_k_e": ke,
                "source": "user_override",
            }
        else:
            ke_lookup = self.repository.reliability_factor_from_table_6_5(reliability_percent)
            ke = float(ke_lookup["reliability_factor_k_e"])

        se_kpsi = ka * kb * kc * kd * ke * misc_factor * se_prime_kpsi
        se_mpa = kpsi_to_mpa(se_kpsi)

        local = self._resolve_local_stresses(inputs, diameter["diameter_in"], K_f)
        sigma_a_kpsi = local["sigma_a_kpsi"]
        sigma_m_kpsi = local["sigma_m_kpsi"]
        sigma_a_mpa = kpsi_to_mpa(sigma_a_kpsi)
        sigma_m_mpa = kpsi_to_mpa(sigma_m_kpsi)

        if math.isclose(sigma_m_kpsi, 0.0, rel_tol=0.0, abs_tol=1e-15):
            raise ValidationError("This solve path requires a nonzero mean stress to define the load-line slope r = sigma_a/sigma_m.")
        r = sigma_a_kpsi / sigma_m_kpsi

        table_6_7 = self.repository.table_6_7_payload
        table_6_8 = self.repository.table_6_8_payload
        gerber_row = self._get_row_by_criterion(table_6_7, "gerber")
        asme_row = self._get_row_by_criterion(table_6_8, "asme_elliptic")

        vars_common = {
            "r": r,
            "Se": se_kpsi,
            "Sut": sut_kpsi,
            "Sy": sy_kpsi,
            "sigma_a": sigma_a_kpsi,
            "sigma_m": sigma_m_kpsi,
        }

        gerber_Sa = self._eval_formula(gerber_row["intersection_coordinates"]["Sa"], vars_common)
        gerber_Sm = self._eval_formula(gerber_row["intersection_coordinates"]["Sm"], {**vars_common, "Sa": gerber_Sa})
        gerber_nf = self._eval_formula(table_6_7["fatigue_factor_of_safety"]["equation"], vars_common)

        asme_Sa = self._eval_formula(asme_row["intersection_coordinates"]["Sa"], vars_common)
        asme_Sm = self._eval_formula(asme_row["intersection_coordinates"]["Sm"], {**vars_common, "Sa": asme_Sa})
        asme_nf = self._eval_formula(table_6_8["fatigue_factor_of_safety"]["equation"], vars_common)

        n_y = sy_kpsi / (sigma_a_kpsi + sigma_m_kpsi)

        gerber_langer = self._get_langer_row(table_6_7)
        gerber_static_Sa = self._eval_formula(gerber_langer["intersection_coordinates"]["Sa"], vars_common)
        gerber_static_Sm = self._eval_formula(gerber_langer["intersection_coordinates"]["Sm"], vars_common)
        gerber_crossover = self._get_crossover_row(table_6_7)
        gerber_r_crit = None
        gerber_crossover_Sa = None
        gerber_crossover_Sm = None
        if gerber_crossover is not None:
            gerber_crossover_Sm = self._eval_formula(gerber_crossover["intersection_coordinates"]["Sm"], vars_common)
            gerber_crossover_Sa = self._eval_formula(gerber_crossover["intersection_coordinates"]["Sa"], {**vars_common, "Sm": gerber_crossover_Sm})
            gerber_r_crit = self._eval_formula(gerber_crossover["intersection_coordinates"]["r_crit"], {**vars_common, "Sa": gerber_crossover_Sa, "Sm": gerber_crossover_Sm})

        asme_langer = self._get_langer_row(table_6_8)
        asme_static_Sa = self._eval_formula(asme_langer["intersection_coordinates"]["Sa"], vars_common)
        asme_static_Sm = self._eval_formula(asme_langer["intersection_coordinates"]["Sm"], vars_common)
        asme_crossover = self._get_crossover_row(table_6_8)
        asme_r_crit = None
        asme_crossover_Sa = None
        asme_crossover_Sm = None
        if asme_crossover is not None:
            solutions = asme_crossover["intersection_coordinates"].get("solutions", [])
            practical = None
            for sol in solutions:
                if sol.get("is_practical_crossover"):
                    practical = sol
                    break
            if practical is not None:
                asme_crossover_Sa = self._eval_formula(practical["Sa"], vars_common)
                asme_crossover_Sm = self._eval_formula(practical["Sm"], {**vars_common, "Sa": asme_crossover_Sa})
                asme_r_crit = self._eval_formula(practical["r_crit"], {**vars_common, "Sa": asme_crossover_Sa, "Sm": asme_crossover_Sm})

        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        verification: dict[str, Any] = {}
        for key, actual in {
            "ka": ka,
            "kb": kb,
            "kc": kc,
            "kd": kd,
            "ke": ke,
            "endurance_limit_kpsi": se_kpsi,
            "endurance_limit_MPa": se_mpa,
            "sigma_a_nom_kpsi": local["sigma_a_nom_kpsi"],
            "sigma_m_nom_kpsi": local["sigma_m_nom_kpsi"],
            "sigma_a_kpsi": sigma_a_kpsi,
            "sigma_m_kpsi": sigma_m_kpsi,
            "sigma_a_MPa": sigma_a_mpa,
            "sigma_m_MPa": sigma_m_mpa,
            "n_y": n_y,
            "gerber_n_f": gerber_nf,
            "gerber_Sa_kpsi": gerber_Sa,
            "gerber_Sm_kpsi": gerber_Sm,
            "asme_elliptic_n_f": asme_nf,
            "asme_elliptic_Sa_kpsi": asme_Sa,
            "asme_elliptic_Sm_kpsi": asme_Sm,
        }.items():
            if key in expected_ref:
                verification[key] = {
                    "actual": safe_round(actual),
                    "reference": float(expected_ref[key]),
                    "relative_error_percent": safe_round(relative_error_percent(actual, float(expected_ref[key]))),
                }

        return {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Fatigue factor of safety analysis"),
            "inputs": inputs,
            "lookups": {
                "table_a_20": record.to_dict(),
                "table_6_4": temp_lookup,
                "table_6_2": finish_record.to_dict(),
                "table_6_5": ke_lookup,
                "table_6_7": {
                    "table_id": table_6_7.get("table_id"),
                    "criterion": "gerber",
                    "fatigue_factor_of_safety_equation": table_6_7.get("fatigue_factor_of_safety", {}).get("equation"),
                    "fatigue_intersection_coordinates": gerber_row.get("intersection_coordinates"),
                    "langer_intersection_coordinates": gerber_langer.get("intersection_coordinates"),
                },
                "table_6_8": {
                    "table_id": table_6_8.get("table_id"),
                    "criterion": "asme_elliptic",
                    "fatigue_factor_of_safety_equation": table_6_8.get("fatigue_factor_of_safety", {}).get("equation"),
                    "fatigue_intersection_coordinates": asme_row.get("intersection_coordinates"),
                    "langer_intersection_coordinates": asme_langer.get("intersection_coordinates"),
                },
            },
            "derived": {
                "service_temperature_f": safe_round(service_temperature_f),
                "service_temperature_c": safe_round((service_temperature_f - 32.0) * 5.0 / 9.0),
                "diameter_in": safe_round(diameter["diameter_in"]),
                "diameter_mm": safe_round(diameter["diameter_mm"]),
                "area_in2": safe_round(math.pi * diameter["diameter_in"]**2 / 4.0),
                "area_mm2": safe_round(math.pi * diameter["diameter_mm"]**2 / 4.0),
                "sut_room_temperature_kpsi": safe_round(sut_room_kpsi),
                "sut_room_temperature_MPa": safe_round(sut_room_mpa),
                "sy_room_temperature_kpsi": safe_round(sy_room_kpsi),
                "sy_room_temperature_MPa": safe_round(sy_room_mpa),
                "st_over_srt": safe_round(st_over_srt),
                "sut_at_service_temperature_kpsi": safe_round(sut_kpsi),
                "sut_at_service_temperature_MPa": safe_round(sut_mpa),
                "sy_at_service_temperature_kpsi": safe_round(sy_kpsi),
                "sy_at_service_temperature_MPa": safe_round(sy_mpa),
                "se_prime_kpsi": safe_round(se_prime_kpsi),
                "se_prime_MPa": safe_round(se_prime_mpa),
                "se_prime_source": se_prime_source,
                "surface_finish_normalized": normalize_surface_finish(str(surface_finish)),
                "ka": safe_round(ka),
                "ka_expression": ka_expression,
                "kb": safe_round(kb),
                "kb_source": kb_source,
                "kc": safe_round(kc),
                "kc_source": kc_source,
                "kd": safe_round(kd),
                "kd_source": kd_source,
                "ke": safe_round(ke),
                "miscellaneous_factor_k_f": safe_round(misc_factor),
                "endurance_limit_kpsi": safe_round(se_kpsi),
                "endurance_limit_MPa": safe_round(se_mpa),
                "K_f": safe_round(K_f),
                "load_min_kip": safe_round(local["F_min_kip"]),
                "load_max_kip": safe_round(local["F_max_kip"]),
                "alternating_load_kip": safe_round(local["F_a_kip"]),
                "mean_load_kip": safe_round(local["F_m_kip"]),
                "sigma_a_nom_kpsi": safe_round(local["sigma_a_nom_kpsi"]),
                "sigma_m_nom_kpsi": safe_round(local["sigma_m_nom_kpsi"]),
                "sigma_a_nom_MPa": safe_round(kpsi_to_mpa(local["sigma_a_nom_kpsi"])),
                "sigma_m_nom_MPa": safe_round(kpsi_to_mpa(local["sigma_m_nom_kpsi"])),
                "sigma_a_kpsi": safe_round(sigma_a_kpsi),
                "sigma_m_kpsi": safe_round(sigma_m_kpsi),
                "sigma_a_MPa": safe_round(sigma_a_mpa),
                "sigma_m_MPa": safe_round(sigma_m_mpa),
                "load_line_slope_r": safe_round(r),
                "n_y": safe_round(n_y),
                "langer_static_yield_equation": "n_y = S_y / (sigma_a + sigma_m)",
            },
            "results": {
                "gerber": {
                    "criterion": "gerber",
                    "Sa_kpsi": safe_round(gerber_Sa),
                    "Sm_kpsi": safe_round(gerber_Sm),
                    "Sa_MPa": safe_round(kpsi_to_mpa(gerber_Sa)),
                    "Sm_MPa": safe_round(kpsi_to_mpa(gerber_Sm)),
                    "fatigue_factor_of_safety_n_f": safe_round(gerber_nf),
                    "first_cycle_yield_factor_n_y": safe_round(n_y),
                    "governing_mode": "fatigue" if gerber_nf < n_y else "first_cycle_yield",
                    "critical_crossover_r": safe_round(gerber_r_crit),
                    "critical_crossover_Sa_kpsi": safe_round(gerber_crossover_Sa),
                    "critical_crossover_Sm_kpsi": safe_round(gerber_crossover_Sm),
                    "langer_intersection_Sa_kpsi": safe_round(gerber_static_Sa),
                    "langer_intersection_Sm_kpsi": safe_round(gerber_static_Sm),
                },
                "asme_elliptic": {
                    "criterion": "asme_elliptic",
                    "Sa_kpsi": safe_round(asme_Sa),
                    "Sm_kpsi": safe_round(asme_Sm),
                    "Sa_MPa": safe_round(kpsi_to_mpa(asme_Sa)),
                    "Sm_MPa": safe_round(kpsi_to_mpa(asme_Sm)),
                    "fatigue_factor_of_safety_n_f": safe_round(asme_nf),
                    "first_cycle_yield_factor_n_y": safe_round(n_y),
                    "governing_mode": "fatigue" if asme_nf < n_y else "first_cycle_yield",
                    "critical_crossover_r": safe_round(asme_r_crit),
                    "critical_crossover_Sa_kpsi": safe_round(asme_crossover_Sa),
                    "critical_crossover_Sm_kpsi": safe_round(asme_crossover_Sm),
                    "langer_intersection_Sa_kpsi": safe_round(asme_static_Sa),
                    "langer_intersection_Sm_kpsi": safe_round(asme_static_Sm),
                },
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-8", "6-18", "6-19", "6-21", "6-26", "6-45", "6-47", "6-48", "6-49"],
                "notes": [
                    "This solver targets Example 6-10 style fatigue factor-of-safety calculations for axial loading.",
                    "The alternating and mean loads are resolved from the minimum and maximum fluctuating tensile load unless stresses are provided directly.",
                    "Nominal axial stresses are computed from sigma = F/A using the provided bar diameter.",
                    "Following Example 6-10, the fatigue stress concentration factor K_f is applied to both sigma_a and sigma_m for the no-notch-yielding prescription.",
                    "The corrected endurance limit is computed from Marin factors using Eqs. (6-18), (6-19), (6-21), and (6-26).",
                    "Gerber and ASME-elliptic fatigue safety factors and strength coordinates are evaluated using the digitized Table 6-7 and Table 6-8 relations.",
                    "First-cycle yielding is checked using the Langer relation from Eq. (6-49).",
                ],
            },
            **({"verification": verification} if verification else {}),
        }


class GerberLangerFailureLinesSolver:
    """Implements Shigley Chapter 6 Example 6-11 for Gerber-Langer failure lines of a preloaded spring."""

    solve_path = "gerber_langer_failure_lines"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    @staticmethod
    def _resolve_preload_cases(inputs: dict[str, Any]) -> list[dict[str, Any]]:
        cases = inputs.get("preload_cases")
        if cases:
            return cases
        preload_values = inputs.get("preload_deflections_in")
        if preload_values:
            return [
                {"name": f"preload_{value}_in", "preload_deflection_in": float(value)}
                for value in preload_values
            ]
        raise ValidationError(
            "preload_cases or preload_deflections_in is required for solve_path='gerber_langer_failure_lines'."
        )

    @staticmethod
    def _gerber_allowable_sm_at_fixed_sa(Sa_kpsi: float, Se_kpsi: float, Sut_kpsi: float) -> float:
        if Sa_kpsi < 0:
            raise ValidationError("Sa must be nonnegative for Gerber evaluation.")
        if Sa_kpsi > Se_kpsi:
            return 0.0
        return Sut_kpsi * math.sqrt(max(0.0, 1.0 - Sa_kpsi / Se_kpsi))

    @staticmethod
    def _langer_allowable_sm_at_fixed_sa(Sa_kpsi: float, Sy_kpsi: float) -> float:
        return max(0.0, Sy_kpsi - Sa_kpsi)

    @staticmethod
    def _gerber_nf_horizontal(sigma_a_kpsi: float, sigma_m_kpsi: float, Se_kpsi: float, Sut_kpsi: float) -> float:
        allowable_sm = GerberLangerFailureLinesSolver._gerber_allowable_sm_at_fixed_sa(sigma_a_kpsi, Se_kpsi, Sut_kpsi)
        if math.isclose(sigma_m_kpsi, 0.0, rel_tol=0.0, abs_tol=1e-15):
            return math.inf
        return allowable_sm / sigma_m_kpsi

    @staticmethod
    def _langer_ny_horizontal(sigma_a_kpsi: float, sigma_m_kpsi: float, Sy_kpsi: float) -> float:
        allowable_sm = GerberLangerFailureLinesSolver._langer_allowable_sm_at_fixed_sa(sigma_a_kpsi, Sy_kpsi)
        if math.isclose(sigma_m_kpsi, 0.0, rel_tol=0.0, abs_tol=1e-15):
            return math.inf
        return allowable_sm / sigma_m_kpsi

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"GerberLangerFailureLinesSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        length_in = ensure_positive("length_in", coalesce(inputs.get("length_in"), inputs.get("cantilever_length_in"), inputs.get("spring_length_in")))
        width_in = ensure_positive("width_in", coalesce(inputs.get("width_in"), inputs.get("cantilever_width_in"), inputs.get("spring_width_in")))
        thickness_in = ensure_positive("thickness_in", coalesce(inputs.get("thickness_in"), inputs.get("cantilever_thickness_in"), inputs.get("spring_thickness_in")))
        elastic_modulus_psi = ensure_positive("elastic_modulus_psi", coalesce(inputs.get("elastic_modulus_psi"), inputs.get("E_psi"), inputs.get("modulus_psi")))
        total_motion_in = ensure_positive("total_motion_in", coalesce(inputs.get("total_motion_in"), inputs.get("follower_total_motion_in"), inputs.get("motion_range_in")))

        Sut_kpsi = ensure_positive("Sut_kpsi", coalesce(inputs.get("Sut_kpsi"), inputs.get("sut_kpsi"), inputs.get("ultimate_tensile_strength_kpsi")))
        Sy_kpsi = ensure_positive("Sy_kpsi", coalesce(inputs.get("Sy_kpsi"), inputs.get("sy_kpsi"), inputs.get("yield_strength_kpsi")))
        Se_kpsi = ensure_positive("Se_kpsi", coalesce(inputs.get("Se_kpsi"), inputs.get("se_kpsi"), inputs.get("endurance_limit_kpsi")))

        cases = self._resolve_preload_cases(inputs)

        I_in4 = width_in * thickness_in**3 / 12.0
        c_in = thickness_in / 2.0
        K_psi_per_in = 96.0 * elastic_modulus_psi * c_in / length_in**3
        K_kpsi_per_in = K_psi_per_in / 1000.0

        gerber_langer_crossover_Sm = (Sut_kpsi**2 / (2.0 * Se_kpsi)) * (
            1.0 - math.sqrt(1.0 + (2.0 * Se_kpsi / Sut_kpsi) ** 2 * (1.0 - Sy_kpsi / Se_kpsi))
        )
        gerber_langer_crossover_Sa = Sy_kpsi - gerber_langer_crossover_Sm
        gerber_langer_crossover_r = (
            gerber_langer_crossover_Sa / gerber_langer_crossover_Sm
            if not math.isclose(gerber_langer_crossover_Sm, 0.0, rel_tol=0.0, abs_tol=1e-15)
            else math.inf
        )

        results_cases = []
        verification: dict[str, Any] = {}
        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        expected_case_results = expected_ref.get("case_results", {})

        for case in cases:
            name = str(coalesce(case.get("name"), f"preload_{case.get('preload_deflection_in')}"))
            preload_in = ensure_positive(
                f"preload_deflection_in for case {name}",
                coalesce(case.get("preload_deflection_in"), case.get("delta_in"), case.get("preload_in")),
            )

            y_min = preload_in
            y_max = preload_in + total_motion_in

            sigma_min_kpsi = K_kpsi_per_in * y_min
            sigma_max_kpsi = K_kpsi_per_in * y_max
            sigma_a_kpsi = 0.5 * (sigma_max_kpsi - sigma_min_kpsi)
            sigma_m_kpsi = 0.5 * (sigma_max_kpsi + sigma_min_kpsi)
            sigma_a_mpa = kpsi_to_mpa(sigma_a_kpsi)
            sigma_m_mpa = kpsi_to_mpa(sigma_m_kpsi)
            r = sigma_a_kpsi / sigma_m_kpsi if not math.isclose(sigma_m_kpsi, 0.0, rel_tol=0.0, abs_tol=1e-15) else math.inf

            gerber_allowable_Sm = self._gerber_allowable_sm_at_fixed_sa(sigma_a_kpsi, Se_kpsi, Sut_kpsi)
            gerber_nf = self._gerber_nf_horizontal(sigma_a_kpsi, sigma_m_kpsi, Se_kpsi, Sut_kpsi)

            langer_allowable_Sm = self._langer_allowable_sm_at_fixed_sa(sigma_a_kpsi, Sy_kpsi)
            n_y = self._langer_ny_horizontal(sigma_a_kpsi, sigma_m_kpsi, Sy_kpsi)

            case_result = {
                "name": name,
                "preload_deflection_in": safe_round(preload_in),
                "y_min_in": safe_round(y_min),
                "y_max_in": safe_round(y_max),
                "sigma_min_kpsi": safe_round(sigma_min_kpsi),
                "sigma_max_kpsi": safe_round(sigma_max_kpsi),
                "sigma_a_kpsi": safe_round(sigma_a_kpsi),
                "sigma_m_kpsi": safe_round(sigma_m_kpsi),
                "sigma_a_MPa": safe_round(sigma_a_mpa),
                "sigma_m_MPa": safe_round(sigma_m_mpa),
                "load_line_slope_r": safe_round(r),
                "horizontal_operating_line": {
                    "equation": f"Sa = {safe_round(sigma_a_kpsi)} kpsi",
                    "Sa_kpsi": safe_round(sigma_a_kpsi),
                },
                "gerber": {
                    "Sa_kpsi": safe_round(sigma_a_kpsi),
                    "Sm_kpsi": safe_round(gerber_allowable_Sm),
                    "Sa_MPa": safe_round(kpsi_to_mpa(sigma_a_kpsi)),
                    "Sm_MPa": safe_round(kpsi_to_mpa(gerber_allowable_Sm)),
                    "fatigue_factor_of_safety_n_f": None if math.isinf(gerber_nf) else safe_round(gerber_nf),
                    "governing_mode": "fatigue" if gerber_nf < n_y else "first_cycle_yield",
                },
                "langer": {
                    "Sa_kpsi": safe_round(sigma_a_kpsi),
                    "Sm_kpsi": safe_round(langer_allowable_Sm),
                    "Sa_MPa": safe_round(kpsi_to_mpa(sigma_a_kpsi)),
                    "Sm_MPa": safe_round(kpsi_to_mpa(langer_allowable_Sm)),
                    "first_cycle_yield_factor_n_y": None if math.isinf(n_y) else safe_round(n_y),
                },
            }
            results_cases.append(case_result)

            if name in expected_case_results:
                ref = expected_case_results[name]
                for key, actual in {
                    "sigma_a_kpsi": sigma_a_kpsi,
                    "sigma_m_kpsi": sigma_m_kpsi,
                    "load_line_slope_r": r,
                    "gerber_n_f": None if math.isinf(gerber_nf) else gerber_nf,
                    "gerber_Sa_kpsi": sigma_a_kpsi,
                    "gerber_Sm_kpsi": gerber_allowable_Sm,
                    "n_y": None if math.isinf(n_y) else n_y,
                    "langer_Sa_kpsi": sigma_a_kpsi,
                    "langer_Sm_kpsi": langer_allowable_Sm,
                }.items():
                    if key in ref and actual is not None:
                        verification[f"{name}::{key}"] = {
                            "actual": safe_round(actual),
                            "reference": float(ref[key]),
                            "relative_error_percent": safe_round(relative_error_percent(actual, float(ref[key]))),
                        }

        return {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Gerber-Langer failure lines analysis"),
            "inputs": inputs,
            "lookups": {
                "table_6_7": {
                    "table_id": self.repository.table_6_7_payload.get("table_id"),
                    "criterion": "gerber_langer_horizontal_line_method",
                    "gerber_equation": "Sa/Se + (Sm/Sut)^2 = 1",
                    "langer_equation": "Sa/Sy + Sm/Sy = 1",
                    "horizontal_line_policy": "For Example 6-11, alternating stress is fixed by follower motion, so the operating path is horizontal in (Sm, Sa) space rather than a load line through the origin.",
                }
            },
            "derived": {
                "length_in": safe_round(length_in),
                "width_in": safe_round(width_in),
                "thickness_in": safe_round(thickness_in),
                "elastic_modulus_psi": safe_round(elastic_modulus_psi),
                "elastic_modulus_MPa": safe_round(elastic_modulus_psi * 0.006894757293168361),
                "total_motion_in": safe_round(total_motion_in),
                "I_in4": safe_round(I_in4),
                "c_in": safe_round(c_in),
                "stress_per_deflection_kpsi_per_in": safe_round(K_kpsi_per_in),
                "stress_per_deflection_psi_per_in": safe_round(K_psi_per_in),
                "Sut_kpsi": safe_round(Sut_kpsi),
                "Sut_MPa": safe_round(kpsi_to_mpa(Sut_kpsi)),
                "Sy_kpsi": safe_round(Sy_kpsi),
                "Sy_MPa": safe_round(kpsi_to_mpa(Sy_kpsi)),
                "Se_kpsi": safe_round(Se_kpsi),
                "Se_MPa": safe_round(kpsi_to_mpa(Se_kpsi)),
            },
            "results": {
                "plot_data": {
                    "gerber_line": {
                        "equation": "Sa/Se + (Sm/Sut)^2 = 1",
                        "Sm_intercept_kpsi": safe_round(Sut_kpsi),
                        "Sa_intercept_kpsi": safe_round(Se_kpsi),
                    },
                    "langer_line": {
                        "equation": "Sa/Sy + Sm/Sy = 1",
                        "Sm_intercept_kpsi": safe_round(Sy_kpsi),
                        "Sa_intercept_kpsi": safe_round(Sy_kpsi),
                    },
                    "gerber_langer_crossover": {
                        "Sa_kpsi": safe_round(gerber_langer_crossover_Sa),
                        "Sm_kpsi": safe_round(gerber_langer_crossover_Sm),
                        "r_crit": safe_round(gerber_langer_crossover_r),
                    },
                },
                "preload_cases": results_cases,
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-47", "6-49"],
                "notes": [
                    "This solver targets Example 6-11 style Gerber-Langer failure-line calculations for a preloaded cantilever spring.",
                    "The spring stress is related to tip deflection by sigma = K*y, where K = 96*E*c/l^3.",
                    "Because the total follower motion is fixed, the alternating stress is fixed and only the mean stress changes with preload.",
                    "Therefore Example 6-11 must be evaluated with horizontal operating lines at fixed Sa, not with origin-based load lines of slope r = Sa/Sm.",
                    "Gerber allowable mean stress is computed from Sm = Sut*sqrt(1 - Sa/Se).",
                    "Langer allowable mean stress is computed from Sm = Sy - Sa, and first-cycle yield safety factor is n_y = Sm_allowable / sigma_m.",
                ],
            },
            **({"verification": verification} if verification else {}),
        }



def _repo_table_6_6_payload(self) -> dict[str, Any]:
    if getattr(self, "_table_6_6_payload", None) is None:
        self._table_6_6_payload = self._read_json("table_6_6.json")
    return self._table_6_6_payload


DigitizedDataRepository.table_6_6_payload = property(_repo_table_6_6_payload)



class MultipleCriteriaCyclesToFailureSolver:
    """Implements Shigley Chapter 6 Example 6-12 using multiple fatigue criteria."""

    solve_path = "multiple_criteria_cycles_to_failure"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    @staticmethod
    def _eval_formula(expression: str, variables: dict[str, float]) -> float:
        text = str(expression).strip()
        if "=" in text:
            text = text.split("=", 1)[1].strip()
        return safe_eval_expression(text.replace("^", "**"), variables)

    @staticmethod
    def _resolve_stress_pair(inputs: dict[str, Any]) -> dict[str, float]:
        sigma_max_kpsi = coalesce(inputs.get("sigma_max_kpsi"), inputs.get("smax_kpsi"), inputs.get("stress_max_kpsi"))
        sigma_min_kpsi = coalesce(inputs.get("sigma_min_kpsi"), inputs.get("smin_kpsi"), inputs.get("stress_min_kpsi"))
        sigma_max_mpa = coalesce(inputs.get("sigma_max_MPa"), inputs.get("smax_MPa"), inputs.get("stress_max_MPa"))
        sigma_min_mpa = coalesce(inputs.get("sigma_min_MPa"), inputs.get("smin_MPa"), inputs.get("stress_min_MPa"))

        if sigma_max_kpsi is not None or sigma_min_kpsi is not None:
            if sigma_max_kpsi is None or sigma_min_kpsi is None:
                raise ValidationError("Provide both sigma_max_kpsi and sigma_min_kpsi.")
            sigma_max_kpsi = float(sigma_max_kpsi)
            sigma_min_kpsi = float(sigma_min_kpsi)
            return {
                "sigma_max_kpsi": sigma_max_kpsi,
                "sigma_min_kpsi": sigma_min_kpsi,
                "sigma_max_MPa": kpsi_to_mpa(sigma_max_kpsi),
                "sigma_min_MPa": kpsi_to_mpa(sigma_min_kpsi),
                "source": "user_input_kpsi",
            }

        if sigma_max_mpa is not None or sigma_min_mpa is not None:
            if sigma_max_mpa is None or sigma_min_mpa is None:
                raise ValidationError("Provide both sigma_max_MPa and sigma_min_MPa.")
            sigma_max_mpa = float(sigma_max_mpa)
            sigma_min_mpa = float(sigma_min_mpa)
            return {
                "sigma_max_kpsi": mpa_to_kpsi(sigma_max_mpa),
                "sigma_min_kpsi": mpa_to_kpsi(sigma_min_mpa),
                "sigma_max_MPa": sigma_max_mpa,
                "sigma_min_MPa": sigma_min_mpa,
                "source": "user_input_MPa",
            }

        raise ValidationError(
            "Provide cyclic stress limits via sigma_max_kpsi/sigma_min_kpsi or sigma_max_MPa/sigma_min_MPa."
        )

    @staticmethod
    def _resolve_strength_pair(inputs: dict[str, Any], kpsi_key: str, mpa_key: str, label: str) -> dict[str, float]:
        value_kpsi = inputs.get(kpsi_key)
        value_mpa = inputs.get(mpa_key)
        if value_kpsi is None and value_mpa is None:
            raise ValidationError(f"{label} is required. Provide {kpsi_key} or {mpa_key}.")
        if value_kpsi is not None and value_mpa is not None:
            return {kpsi_key: float(value_kpsi), mpa_key: float(value_mpa)}
        if value_kpsi is not None:
            return {kpsi_key: float(value_kpsi), mpa_key: kpsi_to_mpa(float(value_kpsi))}
        return {kpsi_key: mpa_to_kpsi(float(value_mpa)), mpa_key: float(value_mpa)}

    @staticmethod
    def _sn_constants(sut_kpsi: float, se_kpsi: float, f_value: float) -> dict[str, float]:
        n_low = 1.0e3
        n_endurance = 1.0e6
        sf_low_kpsi = f_value * sut_kpsi
        a_kpsi = (sf_low_kpsi ** 2) / se_kpsi
        b = log10(se_kpsi / sf_low_kpsi) / log10(n_endurance / n_low)
        return {
            "n_low": n_low,
            "n_endurance": n_endurance,
            "sf_low_kpsi": sf_low_kpsi,
            "a_kpsi": a_kpsi,
            "b": b,
        }

    @staticmethod
    def _cycles_from_sigma_rev(a_kpsi: float, b: float, sigma_rev_kpsi: float, se_kpsi: float) -> tuple[str, float | None, str | None]:
        if sigma_rev_kpsi <= se_kpsi:
            return (
                "endurance_or_infinite_life",
                None,
                "Predicted life is at least 1e6 cycles because the equivalent completely reversed stress does not exceed Se.",
            )
        cycles = (sigma_rev_kpsi / a_kpsi) ** (1.0 / b)
        return ("finite_life", cycles, None)

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"MultipleCriteriaCyclesToFailureSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        stress_info = self._resolve_stress_pair(inputs)
        sut_info = self._resolve_strength_pair(inputs, "Sut_kpsi", "Sut_MPa", "Ultimate tensile strength")
        sy_info = self._resolve_strength_pair(inputs, "Sy_kpsi", "Sy_MPa", "Yield strength")
        se_info = self._resolve_strength_pair(inputs, "Se_kpsi", "Se_MPa", "Fully corrected endurance limit")

        f_value = coalesce(inputs.get("f"), inputs.get("fatigue_strength_fraction_f"), inputs.get("fatigue_strength_fraction_f_override"))
        f_value = ensure_positive("f", f_value)

        sigma_max_kpsi = stress_info["sigma_max_kpsi"]
        sigma_min_kpsi = stress_info["sigma_min_kpsi"]
        sigma_a_kpsi = 0.5 * (sigma_max_kpsi - sigma_min_kpsi)
        sigma_m_kpsi = 0.5 * (sigma_max_kpsi + sigma_min_kpsi)
        sigma_a_mpa = kpsi_to_mpa(sigma_a_kpsi)
        sigma_m_mpa = kpsi_to_mpa(sigma_m_kpsi)

        if sigma_m_kpsi <= 0:
            raise ValidationError(
                "Example 6-12 style multi-criteria life solve path expects positive mean stress in the first quadrant."
            )

        table_6_6 = self.repository.table_6_6_payload
        table_6_7 = self.repository.table_6_7_payload

        modified_goodman_eq = table_6_6.get("fatigue_factor_of_safety", {}).get("equation")
        gerber_eq = table_6_7.get("fatigue_factor_of_safety", {}).get("equation")

        vars_common = {
            "sigma_a": sigma_a_kpsi,
            "sigma_m": sigma_m_kpsi,
            "Se": se_info["Se_kpsi"],
            "Sut": sut_info["Sut_kpsi"],
            "Sy": sy_info["Sy_kpsi"],
        }

        nf_modified_goodman = self._eval_formula(modified_goodman_eq, vars_common)
        nf_gerber = self._eval_formula(gerber_eq, vars_common)

        sigma_rev_modified_goodman_kpsi = sigma_a_kpsi / (1.0 - sigma_m_kpsi / sut_info["Sut_kpsi"])
        sigma_rev_gerber_kpsi = sigma_a_kpsi / (1.0 - (sigma_m_kpsi / sut_info["Sut_kpsi"]) ** 2)

        sn = self._sn_constants(sut_info["Sut_kpsi"], se_info["Se_kpsi"], f_value)
        a_kpsi = sn["a_kpsi"]
        b = sn["b"]

        mg_life_regime, mg_cycles, mg_note = self._cycles_from_sigma_rev(
            a_kpsi=a_kpsi,
            b=b,
            sigma_rev_kpsi=sigma_rev_modified_goodman_kpsi,
            se_kpsi=se_info["Se_kpsi"],
        )
        ge_life_regime, ge_cycles, ge_note = self._cycles_from_sigma_rev(
            a_kpsi=a_kpsi,
            b=b,
            sigma_rev_kpsi=sigma_rev_gerber_kpsi,
            se_kpsi=se_info["Se_kpsi"],
        )

        expected_ref = inputs.get("expected_textbook_reference_values") or {}
        verification = {}
        checks = {
            "sigma_a_kpsi": sigma_a_kpsi,
            "sigma_m_kpsi": sigma_m_kpsi,
            "modified_goodman_nf_infinite_life": nf_modified_goodman,
            "modified_goodman_sigma_rev_kpsi": sigma_rev_modified_goodman_kpsi,
            "gerber_sigma_rev_kpsi": sigma_rev_gerber_kpsi,
            "a_kpsi": a_kpsi,
            "b": b,
            "modified_goodman_cycles_to_failure": mg_cycles,
            "gerber_cycles_to_failure": ge_cycles,
        }
        for key, actual in checks.items():
            if key in expected_ref and actual is not None:
                verification[key] = {
                    "actual": safe_round(actual),
                    "reference": float(expected_ref[key]),
                    "relative_error_percent": safe_round(relative_error_percent(actual, float(expected_ref[key]))),
                }

        return {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Number of cycles to fatigue failure using multiple criteria"),
            "inputs": inputs,
            "lookups": {
                "table_6_6": {
                    "table_id": table_6_6.get("table_id"),
                    "criterion": "modified_goodman",
                    "fatigue_factor_of_safety_equation": modified_goodman_eq,
                },
                "table_6_7": {
                    "table_id": table_6_7.get("table_id"),
                    "criterion": "gerber",
                    "fatigue_factor_of_safety_equation": gerber_eq,
                },
            },
            "derived": {
                "sigma_max_kpsi": safe_round(sigma_max_kpsi),
                "sigma_min_kpsi": safe_round(sigma_min_kpsi),
                "sigma_max_MPa": safe_round(stress_info["sigma_max_MPa"]),
                "sigma_min_MPa": safe_round(stress_info["sigma_min_MPa"]),
                "sigma_a_kpsi": safe_round(sigma_a_kpsi),
                "sigma_m_kpsi": safe_round(sigma_m_kpsi),
                "sigma_a_MPa": safe_round(sigma_a_mpa),
                "sigma_m_MPa": safe_round(sigma_m_mpa),
                "Sut_kpsi": safe_round(sut_info["Sut_kpsi"]),
                "Sut_MPa": safe_round(sut_info["Sut_MPa"]),
                "Sy_kpsi": safe_round(sy_info["Sy_kpsi"]),
                "Sy_MPa": safe_round(sy_info["Sy_MPa"]),
                "Se_kpsi": safe_round(se_info["Se_kpsi"]),
                "Se_MPa": safe_round(se_info["Se_MPa"]),
                "fatigue_strength_fraction_f": safe_round(f_value),
                "sf_at_1e3_cycles_kpsi": safe_round(sn["sf_low_kpsi"]),
                "sf_at_1e3_cycles_MPa": safe_round(kpsi_to_mpa(sn["sf_low_kpsi"])),
                "a_kpsi": safe_round(a_kpsi),
                "a_MPa": safe_round(kpsi_to_mpa(a_kpsi)),
                "b": safe_round(b),
                "sn_equation_kpsi": f"S_f = {safe_round(a_kpsi)} * N^({safe_round(b)})",
                "sn_equation_MPa": f"S_f = {safe_round(kpsi_to_mpa(a_kpsi))} * N^({safe_round(b)})",
            },
            "results": {
                "modified_goodman": {
                    "criterion": "modified_goodman",
                    "fatigue_factor_of_safety_infinite_life_n_f": safe_round(nf_modified_goodman),
                    "sigma_rev_equivalent_kpsi": safe_round(sigma_rev_modified_goodman_kpsi),
                    "sigma_rev_equivalent_MPa": safe_round(kpsi_to_mpa(sigma_rev_modified_goodman_kpsi)),
                    "life_regime": mg_life_regime,
                    "cycles_to_failure": None if mg_cycles is None else safe_round(mg_cycles),
                    "cycles_to_failure_note": mg_note,
                },
                "gerber": {
                    "criterion": "gerber",
                    "fatigue_factor_of_safety_infinite_life_n_f": safe_round(nf_gerber),
                    "sigma_rev_equivalent_kpsi": safe_round(sigma_rev_gerber_kpsi),
                    "sigma_rev_equivalent_MPa": safe_round(kpsi_to_mpa(sigma_rev_gerber_kpsi)),
                    "life_regime": ge_life_regime,
                    "cycles_to_failure": None if ge_cycles is None else safe_round(ge_cycles),
                    "cycles_to_failure_note": ge_note,
                },
            },
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-13", "6-14", "6-15", "6-16", "6-46", "6-47"],
                "notes": [
                    "This solver targets Example 6-12 style life estimation for a fluctuating stress state using multiple fatigue criteria.",
                    "First the alternating and mean stresses are formed from sigma_max and sigma_min.",
                    "Then each fatigue criterion is used to compute an equivalent completely reversed stress sigma_rev that causes the same damage.",
                    "Finally the finite-life S-N relation is used to estimate cycles to failure from that equivalent completely reversed stress.",
                ],
            },
            **({"verification": verification} if verification else {}),
        }



def _repo_table_6_6_payload(self) -> dict[str, Any]:
    if getattr(self, "_table_6_6_payload", None) is None:
        self._table_6_6_payload = self._read_json("table_6_6.json")
    return self._table_6_6_payload


def _repo_table_a_15_1_rows(self) -> list[dict[str, float]]:
    if getattr(self, "_table_a_15_1_rows", None) is None:
        raw_rows = self._read_csv("table_a_15_1.csv")
        self._table_a_15_1_rows = [
            {"d_over_w": float(row["d_over_w"]), "K_t": float(row["K_t"])}
            for row in raw_rows
        ]
    return self._table_a_15_1_rows


def _repo_table_a_24_gray_cast_iron_rows(self) -> list[dict[str, Any]]:
    if getattr(self, "_table_a_24_gray_cast_iron_rows", None) is None:
        raw_rows = self._read_csv("table_a_24_gray_cast_iron.csv")
        self._table_a_24_gray_cast_iron_rows = []
        for row in raw_rows:
            self._table_a_24_gray_cast_iron_rows.append(
                {
                    "astm_number": int(float(row["astm_number"])),
                    "tensile_strength_Sut_kpsi": float(row["tensile_strength_Sut_kpsi"]),
                    "compressive_strength_Suc_kpsi": float(row["compressive_strength_Suc_kpsi"]),
                    "shear_modulus_of_rupture_Ssu_kpsi": float(row["shear_modulus_of_rupture_Ssu_kpsi"]),
                    "modulus_of_elasticity_tension_min_Mpsi": float(row["modulus_of_elasticity_tension_min_Mpsi"]),
                    "modulus_of_elasticity_tension_max_Mpsi": float(row["modulus_of_elasticity_tension_max_Mpsi"]),
                    "modulus_of_elasticity_torsion_min_Mpsi": float(row["modulus_of_elasticity_torsion_min_Mpsi"]),
                    "modulus_of_elasticity_torsion_max_Mpsi": float(row["modulus_of_elasticity_torsion_max_Mpsi"]),
                    "endurance_limit_Se_kpsi": float(row["endurance_limit_Se_kpsi"]),
                    "brinell_hardness_HB": float(row["brinell_hardness_HB"]),
                    "fatigue_stress_concentration_factor_Kf": float(row["fatigue_stress_concentration_factor_Kf"]),
                    "notes": row.get("notes"),
                }
            )
    return self._table_a_24_gray_cast_iron_rows


def _repo_transverse_hole_kt_tension(self, d_over_w: float) -> dict[str, Any]:
    rows = self.table_a_15_1_rows
    xs = [row["d_over_w"] for row in rows]
    ys = [row["K_t"] for row in rows]
    kt = linear_interpolate(float(d_over_w), xs, ys)
    return {"d_over_w": float(d_over_w), "K_t": kt, "source": "table_a_15_1_interpolated"}


def _repo_find_gray_cast_iron_record(self, astm_number: int | float | str) -> dict[str, Any]:
    target = int(float(astm_number))
    for row in self.table_a_24_gray_cast_iron_rows:
        if int(row["astm_number"]) == target:
            return row
    raise DataLookupError(f"No Table A-24 gray cast iron record was found for ASTM number {astm_number!r}.")


DigitizedDataRepository.table_6_6_payload = property(_repo_table_6_6_payload)
DigitizedDataRepository.table_a_15_1_rows = property(_repo_table_a_15_1_rows)
DigitizedDataRepository.table_a_24_gray_cast_iron_rows = property(_repo_table_a_24_gray_cast_iron_rows)
DigitizedDataRepository.transverse_hole_kt_tension = _repo_transverse_hole_kt_tension
DigitizedDataRepository.find_gray_cast_iron_record = _repo_find_gray_cast_iron_record



class BrittleMaterialAxialFatigueSolver:
    """Implements Shigley Chapter 6 Example 6-13 for brittle material axial fatigue near a transverse hole."""

    solve_path = "brittle_material_axial_fatigue"

    def __init__(self, repository: DigitizedDataRepository | None = None) -> None:
        self.repository = repository or DigitizedDataRepository()

    @staticmethod
    def _smith_dolan_first_quadrant_intersection_sa(se_kpsi: float, sut_kpsi: float, r: float) -> float:
        if math.isclose(r, 0.0, rel_tol=0.0, abs_tol=1e-15):
            raise ValidationError("Smith-Dolan first-quadrant intersection requires nonzero r.")
        term = 1.0 + 4.0 * r * sut_kpsi * se_kpsi / ((r * sut_kpsi + se_kpsi) ** 2)
        return ((r * sut_kpsi + se_kpsi) / 2.0) * (-1.0 + math.sqrt(term))

    @staticmethod
    def _smith_dolan_second_quadrant_intersection_sa(se_kpsi: float, sut_kpsi: float, r: float) -> float:
        if math.isclose(r, 0.0, rel_tol=0.0, abs_tol=1e-15):
            raise ValidationError("Second-quadrant brittle locus intersection requires nonzero r.")
        denom = 1.0 - (1.0 / r) * (se_kpsi / sut_kpsi - 1.0)
        if math.isclose(denom, 0.0, rel_tol=0.0, abs_tol=1e-15):
            raise ValidationError("Second-quadrant brittle locus intersection became singular.")
        return se_kpsi / denom

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") not in (None, self.solve_path):
            raise ValidationError(
                f"BrittleMaterialAxialFatigueSolver received solve_path={inputs.get('solve_path')!r}; expected {self.solve_path!r}."
            )

        astm_number = coalesce(inputs.get("astm_number"), inputs.get("gray_cast_iron_grade_astm_number"), inputs.get("grade"))
        if astm_number is None:
            raise ValidationError("astm_number is required for solve_path='brittle_material_axial_fatigue'.")
        material = self.repository.find_gray_cast_iron_record(astm_number)

        width_in = ensure_positive("width_in", coalesce(inputs.get("width_in"), inputs.get("w_in")))
        thickness_in = ensure_positive("thickness_in", coalesce(inputs.get("thickness_in"), inputs.get("t_in")))
        hole_diameter_in = ensure_positive("hole_diameter_in", coalesce(inputs.get("hole_diameter_in"), inputs.get("d_in")))
        if hole_diameter_in >= width_in:
            raise ValidationError("hole_diameter_in must be smaller than width_in.")

        net_area_in2 = coalesce(inputs.get("net_area_in2"), inputs.get("area_in2"))
        if net_area_in2 is None:
            net_area_in2 = thickness_in * (width_in - hole_diameter_in)
            net_area_source = "t*(w-d)"
        else:
            net_area_in2 = ensure_positive("net_area_in2", net_area_in2)
            net_area_source = "user_input"

        d_over_w = hole_diameter_in / width_in

        kt_override = inputs.get("K_t_override")
        if kt_override is not None:
            kt_lookup = {"d_over_w": float(d_over_w), "K_t": float(kt_override), "source": "user_override"}
            K_t = float(kt_override)
        else:
            kt_lookup = self.repository.transverse_hole_kt_tension(d_over_w)
            K_t = float(kt_lookup["K_t"])

        q_brittle = ensure_positive(
            "brittle_notch_sensitivity_q",
            coalesce(inputs.get("brittle_notch_sensitivity_q"), inputs.get("q"), inputs.get("q_brittle")),
        )
        K_f = 1.0 + q_brittle * (K_t - 1.0)

        kc_axial = ensure_positive("axial_load_factor_k_c", coalesce(inputs.get("axial_load_factor_k_c"), inputs.get("kc_axial"), inputs.get("k_c")))
        kd = float(coalesce(inputs.get("temperature_factor_k_d"), inputs.get("k_d"), 1.0))
        ke = float(coalesce(inputs.get("reliability_factor_k_e"), inputs.get("k_e"), 1.0))
        misc_factor = float(coalesce(inputs.get("miscellaneous_factor_k_f"), inputs.get("misc_factor"), 1.0))

        sut_kpsi = float(material["tensile_strength_Sut_kpsi"])
        suc_kpsi = float(material["compressive_strength_Suc_kpsi"])
        se_base_kpsi = float(material["endurance_limit_Se_kpsi"])
        se_kpsi = se_base_kpsi * kc_axial * kd * ke * misc_factor

        cases = inputs.get("cases")
        if not cases:
            cases = [
                {"name": "part_a_steady_tension", "case_type": "steady", "load_min_lbf": 1000.0, "load_max_lbf": 1000.0},
                {"name": "part_b_repeated_application", "case_type": "repeated", "load_min_lbf": 0.0, "load_max_lbf": 1000.0},
                {"name": "part_c_fluctuating_with_compression", "case_type": "fluctuating", "load_min_lbf": -1000.0, "load_max_lbf": 300.0},
            ]

        results = []
        verification = {}
        expected = inputs.get("expected_textbook_reference_values") or {}
        expected_case_results = expected.get("case_results", {})

        for case in cases:
            name = case.get("name") or "case"
            case_type = str(coalesce(case.get("case_type"), "fluctuating")).strip().lower()
            F_min_lbf = float(coalesce(case.get("load_min_lbf"), case.get("F_min_lbf"), 0.0))
            F_max_lbf = float(coalesce(case.get("load_max_lbf"), case.get("F_max_lbf")))

            F_a_lbf = 0.5 * abs(F_max_lbf - F_min_lbf)
            F_m_lbf = 0.5 * (F_max_lbf + F_min_lbf)

            if case_type == "steady":
                sigma_a_kpsi = 0.0
                sigma_m_kpsi = (F_m_lbf / net_area_in2) * 1.0e-3
                if sigma_m_kpsi >= 0:
                    governing_strength = sut_kpsi
                    criterion = "steady_tension"
                else:
                    governing_strength = suc_kpsi
                    criterion = "steady_compression"
                n = governing_strength / abs(sigma_m_kpsi)
                result_item = {
                    "name": name,
                    "case_type": case_type,
                    "load_min_lbf": safe_round(F_min_lbf),
                    "load_max_lbf": safe_round(F_max_lbf),
                    "alternating_load_lbf": safe_round(F_a_lbf),
                    "mean_load_lbf": safe_round(F_m_lbf),
                    "sigma_a_kpsi": safe_round(sigma_a_kpsi),
                    "sigma_m_kpsi": safe_round(sigma_m_kpsi),
                    "sigma_a_MPa": safe_round(kpsi_to_mpa(sigma_a_kpsi)),
                    "sigma_m_MPa": safe_round(kpsi_to_mpa(sigma_m_kpsi)),
                    "applied_Kf_to_stress": False,
                    "factor_of_safety_n": safe_round(n),
                    "criterion": criterion,
                }
            else:
                sigma_a_kpsi = K_f * (F_a_lbf / net_area_in2) * 1.0e-3
                sigma_m_kpsi = K_f * (F_m_lbf / net_area_in2) * 1.0e-3
                r = sigma_a_kpsi / sigma_m_kpsi if not math.isclose(sigma_m_kpsi, 0.0, rel_tol=0.0, abs_tol=1e-15) else math.inf

                if sigma_m_kpsi >= 0:
                    Sa_intersection = self._smith_dolan_first_quadrant_intersection_sa(se_kpsi, sut_kpsi, r)
                    Sm_intersection = Sa_intersection / r
                    criterion = "smith_dolan_first_quadrant"
                    equation = "eq_6_52"
                else:
                    Sa_intersection = self._smith_dolan_second_quadrant_intersection_sa(se_kpsi, sut_kpsi, r)
                    Sm_intersection = Sa_intersection / r
                    criterion = "cast_iron_second_quadrant"
                    equation = "eq_6_53"

                n = Sa_intersection / sigma_a_kpsi
                result_item = {
                    "name": name,
                    "case_type": case_type,
                    "load_min_lbf": safe_round(F_min_lbf),
                    "load_max_lbf": safe_round(F_max_lbf),
                    "alternating_load_lbf": safe_round(F_a_lbf),
                    "mean_load_lbf": safe_round(F_m_lbf),
                    "sigma_a_kpsi": safe_round(sigma_a_kpsi),
                    "sigma_m_kpsi": safe_round(sigma_m_kpsi),
                    "sigma_a_MPa": safe_round(kpsi_to_mpa(sigma_a_kpsi)),
                    "sigma_m_MPa": safe_round(kpsi_to_mpa(sigma_m_kpsi)),
                    "load_line_slope_r": None if math.isinf(r) else safe_round(r),
                    "Sa_intersection_kpsi": safe_round(Sa_intersection),
                    "Sm_intersection_kpsi": safe_round(Sm_intersection),
                    "Sa_intersection_MPa": safe_round(kpsi_to_mpa(Sa_intersection)),
                    "Sm_intersection_MPa": safe_round(kpsi_to_mpa(Sm_intersection)),
                    "factor_of_safety_n": safe_round(n),
                    "criterion": criterion,
                    "equation": equation,
                    "applied_Kf_to_stress": True,
                }

            results.append(result_item)

            ref = expected_case_results.get(name)
            if ref:
                for key in ["sigma_a_kpsi", "sigma_m_kpsi", "load_line_slope_r", "Sa_intersection_kpsi", "Sm_intersection_kpsi", "factor_of_safety_n"]:
                    if key in ref and result_item.get(key) is not None:
                        verification[f"{name}::{key}"] = {
                            "actual": result_item[key],
                            "reference": float(ref[key]),
                            "relative_error_percent": safe_round(relative_error_percent(float(result_item[key]), float(ref[key]))),
                        }

        output = {
            "problem": payload.get("problem", self.solve_path),
            "title": payload.get("title", "Brittle material axial fatigue analysis"),
            "inputs": inputs,
            "lookups": {"table_a_24_gray_cast_iron": material, "table_a_15_1": kt_lookup},
            "derived": {
                "astm_number": int(material["astm_number"]),
                "width_in": safe_round(width_in),
                "thickness_in": safe_round(thickness_in),
                "hole_diameter_in": safe_round(hole_diameter_in),
                "net_area_in2": safe_round(net_area_in2),
                "net_area_source": net_area_source,
                "d_over_w": safe_round(d_over_w),
                "Sut_kpsi": safe_round(sut_kpsi),
                "Sut_MPa": safe_round(kpsi_to_mpa(sut_kpsi)),
                "Suc_kpsi": safe_round(suc_kpsi),
                "Suc_MPa": safe_round(kpsi_to_mpa(suc_kpsi)),
                "table_a_24_endurance_limit_kpsi": safe_round(se_base_kpsi),
                "table_a_24_endurance_limit_MPa": safe_round(kpsi_to_mpa(se_base_kpsi)),
                "axial_load_factor_k_c": safe_round(kc_axial),
                "temperature_factor_k_d": safe_round(kd),
                "reliability_factor_k_e": safe_round(ke),
                "miscellaneous_factor_k_f": safe_round(misc_factor),
                "corrected_endurance_limit_kpsi": safe_round(se_kpsi),
                "corrected_endurance_limit_MPa": safe_round(kpsi_to_mpa(se_kpsi)),
                "K_t": safe_round(K_t),
                "brittle_notch_sensitivity_q": safe_round(q_brittle),
                "K_f": safe_round(K_f),
            },
            "results": {"cases": results},
            "meta": {
                "solve_path": self.solve_path,
                "implemented_equations": ["6-50", "6-51", "6-52", "6-53"],
                "notes": [
                    "This solver targets Example 6-13 style factor-of-safety calculations for a brittle gray cast iron link in axial loading near a transverse hole.",
                    "The net section area is A = t(w - d), matching the figure and the textbook setup.",
                    "K_t for the transverse hole is interpolated from table_a_15_1.csv using d/w.",
                    "For the steady tensile case, the textbook does not apply K_t or K_f because the load is static.",
                    "For the fluctuating cases, K_f is applied to both sigma_a and sigma_m as shown in the worked example.",
                    "In the first quadrant, the Smith-Dolan fatigue locus uses Eq. (6-52). In the second quadrant for cast iron, the straight-line segment uses Eq. (6-53).",
                ],
            },
        }
        if verification:
            output["verification"] = verification
        return output
