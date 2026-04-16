from __future__ import annotations

from dataclasses import dataclass
from math import sqrt, isclose, inf
from typing import Any

import pandas as pd


@dataclass
class MaterialProperties:
    Syt: float
    Syc: float | None = None
    ef: float | None = None
    strength_unit: str = "kpsi"

    def to_dict(self) -> dict[str, Any]:
        return {
            "Syt": self.Syt,
            "Syc": self.Syc,
            "ef": self.ef,
            "strength_unit": self.strength_unit,
            "is_ductile_by_strain": self.is_ductile_by_strain,
            "has_equal_tension_compression_yield": self.has_equal_yield_strengths,
        }

    @property
    def is_ductile_by_strain(self) -> bool | None:
        if self.ef is None:
            return None
        return self.ef >= 0.05

    @property
    def has_equal_yield_strengths(self) -> bool:
        if self.Syc is None:
            return True
        return isclose(self.Syt, self.Syc, rel_tol=1e-9, abs_tol=1e-12)


class StressState:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.label = str(payload.get("label", payload.get("id", "case")))
        self.description = payload.get("description", "")
        self.input_mode = self._detect_input_mode(payload)

    @staticmethod
    def _detect_input_mode(payload: dict[str, Any]) -> str:
        if "principal_stresses" in payload:
            return "principal_stresses"
        plane_keys = {"sigma_x", "sigma_y", "tau_xy"}
        if plane_keys.issubset(payload.keys()):
            return "plane_stress"
        raise ValueError(
            "Each stress state must define either 'principal_stresses' or all of "
            "'sigma_x', 'sigma_y', and 'tau_xy'."
        )

    def principal_stresses(self) -> tuple[float, float, float]:
        if self.input_mode == "principal_stresses":
            values = self.payload["principal_stresses"]
            if len(values) != 3:
                raise ValueError("principal_stresses must contain exactly three values.")
            ordered = sorted((float(v) for v in values), reverse=True)
            return ordered[0], ordered[1], ordered[2]

        sigma_x = float(self.payload["sigma_x"])
        sigma_y = float(self.payload["sigma_y"])
        tau_xy = float(self.payload["tau_xy"])
        avg = 0.5 * (sigma_x + sigma_y)
        radius = sqrt(((sigma_x - sigma_y) / 2.0) ** 2 + tau_xy**2)
        sigma_a = avg + radius
        sigma_b = avg - radius
        ordered = sorted((sigma_a, sigma_b, 0.0), reverse=True)
        return ordered[0], ordered[1], ordered[2]

    def principal_pair_in_plane(self) -> tuple[float, float] | None:
        if self.input_mode != "plane_stress":
            return None
        sigma_x = float(self.payload["sigma_x"])
        sigma_y = float(self.payload["sigma_y"])
        tau_xy = float(self.payload["tau_xy"])
        avg = 0.5 * (sigma_x + sigma_y)
        radius = sqrt(((sigma_x - sigma_y) / 2.0) ** 2 + tau_xy**2)
        return avg + radius, avg - radius

    def von_mises_stress(self) -> float:
        if self.input_mode == "plane_stress":
            sigma_x = float(self.payload["sigma_x"])
            sigma_y = float(self.payload["sigma_y"])
            tau_xy = float(self.payload["tau_xy"])
            return sqrt(sigma_x**2 - sigma_x * sigma_y + sigma_y**2 + 3.0 * tau_xy**2)
        s1, s2, s3 = self.principal_stresses()
        return sqrt(((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2) / 2.0)

    def max_shear_stress(self) -> float:
        s1, _, s3 = self.principal_stresses()
        return 0.5 * (s1 - s3)

    def mss_factor_of_safety(self, Sy: float) -> float:
        s1, _, s3 = self.principal_stresses()
        denominator = s1 - s3
        if isclose(denominator, 0.0, abs_tol=1e-12):
            return inf
        return Sy / denominator

    def de_factor_of_safety(self, Sy: float) -> float:
        sigma_vm = self.von_mises_stress()
        if isclose(sigma_vm, 0.0, abs_tol=1e-12):
            return inf
        return Sy / sigma_vm

    def mss_plane_case(self) -> str | None:
        if self.input_mode != "plane_stress":
            return None
        sigma_a, sigma_b = self.principal_pair_in_plane() or (None, None)
        if sigma_a is None or sigma_b is None:
            return None
        if sigma_a >= sigma_b >= 0.0:
            return "case_1_sigmaA>=sigmaB>=0"
        if sigma_a >= 0.0 >= sigma_b:
            return "case_2_sigmaA>=0>=sigmaB"
        return "case_3_0>=sigmaA>=sigmaB"

    def to_result(self, material: MaterialProperties) -> dict[str, Any]:
        s1, s2, s3 = self.principal_stresses()
        result = {
            "label": self.label,
            "description": self.description,
            "input_mode": self.input_mode,
            "ordered_principal_stresses": {
                "sigma_1": s1,
                "sigma_2": s2,
                "sigma_3": s3,
            },
            "derived": {
                "von_mises_stress": self.von_mises_stress(),
                "maximum_shear_stress": self.max_shear_stress(),
            },
            "factor_of_safety": {
                "DE": self.de_factor_of_safety(material.Syt),
                "MSS": self.mss_factor_of_safety(material.Syt),
            },
        }
        if self.input_mode == "plane_stress":
            sigma_a, sigma_b = self.principal_pair_in_plane() or (None, None)
            result["plane_stress_inputs"] = {
                "sigma_x": float(self.payload["sigma_x"]),
                "sigma_y": float(self.payload["sigma_y"]),
                "tau_xy": float(self.payload["tau_xy"]),
            }
            result["derived"]["in_plane_principal_stresses"] = {
                "sigma_A": sigma_a,
                "sigma_B": sigma_b,
            }
            result["derived"]["mss_plane_case"] = self.mss_plane_case()
        else:
            result["principal_stress_inputs"] = {
                "sigma_1": s1,
                "sigma_2": s2,
                "sigma_3": s3,
            }
        return result


class Example51FactorOfSafetySolver:
    """Implements the first static-failure solve path for Shigley Example 5-1 style problems."""

    solve_path = "ductile_failure_fos"

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        solve_path = inputs.get("solve_path")
        if solve_path != self.solve_path:
            raise ValueError(f"Unsupported solve_path '{solve_path}'. Expected '{self.solve_path}'.")

        material = MaterialProperties(
            Syt=float(inputs["Syt"]),
            Syc=float(inputs.get("Syc", inputs["Syt"])),
            ef=float(inputs["ef"]) if inputs.get("ef") is not None else None,
            strength_unit=str(inputs.get("strength_unit", "kpsi")),
        )

        cases = inputs.get("stress_states", [])
        if not cases:
            raise ValueError("At least one stress state must be provided in 'stress_states'.")

        case_results = [StressState(case).to_result(material) for case in cases]
        summary_df = self._build_summary_dataframe(case_results, material.strength_unit)

        return {
            "problem": payload.get("problem", "static_failure"),
            "title": payload.get("title", "Static failure factor-of-safety analysis"),
            "inputs": inputs,
            "material": material.to_dict(),
            "meta": {
                "solve_path": self.solve_path,
                "applicability": "ductile materials with equal tension/compression yield strengths",
                "implemented_theories": ["DE", "MSS"],
            },
            "results": {
                "cases": case_results,
                "summary_table": summary_df.to_dict(orient="records"),
            },
        }

    @staticmethod
    def _build_summary_dataframe(case_results: list[dict[str, Any]], unit: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for case in case_results:
            principals = case["ordered_principal_stresses"]
            fos = case["factor_of_safety"]
            row = {
                "Case": case["label"],
                f"s1 {unit}": principals["sigma_1"],
                f"s2 {unit}": principals["sigma_2"],
                f"s3 {unit}": principals["sigma_3"],
                f"svm {unit}": case["derived"]["von_mises_stress"],
                f"tmax {unit}": case["derived"]["maximum_shear_stress"],
                "n_DE": fos["DE"],
                "n_MSS": fos["MSS"],
            }
            rows.append(row)
        return pd.DataFrame(rows)
