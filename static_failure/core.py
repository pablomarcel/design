from __future__ import annotations

from dataclasses import dataclass
from math import inf, isclose, pi, sqrt
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class MaterialProperties:
    Syt: float
    Syc: float | None = None
    ef: float | None = None
    strength_unit: str = "kpsi"
    name: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "Syt": self.Syt,
            "Syc": self.Syc,
            "ef": self.ef,
            "strength_unit": self.strength_unit,
            "source": self.source,
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


class MaterialTable:
    """CSV-backed material lookup table for static-failure examples."""

    def __init__(self, csv_path: str | Path | None = None) -> None:
        self.csv_path = Path(csv_path) if csv_path is not None else Path(__file__).resolve().parent / "data" / "static_failure_materials.csv"
        self._table: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._table is None:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"Material table not found: {self.csv_path}")
            self._table = pd.read_csv(self.csv_path)
        return self._table.copy()

    def lookup(self, material_id: str) -> dict[str, Any]:
        table = self._load()
        mask = table["material_id"].astype(str).str.lower() == str(material_id).lower()
        matches = table.loc[mask]
        if matches.empty:
            known = ", ".join(sorted(table["material_id"].astype(str).tolist()))
            raise ValueError(f"Unknown material_id '{material_id}'. Available material ids: {known}")
        row = matches.iloc[0].to_dict()
        return row


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

    def coulomb_mohr_plane_case(self) -> str | None:
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

    def coulomb_mohr_factor_of_safety(self, St: float, Sc: float) -> float:
        s1, _, s3 = self.principal_stresses()
        denominator = (s1 / St) - (s3 / Sc)
        if isclose(denominator, 0.0, abs_tol=1e-12):
            return inf
        return 1.0 / denominator

    @staticmethod
    def torsional_shear_yield_strength(St: float, Sc: float) -> float:
        denominator = St + Sc
        if isclose(denominator, 0.0, abs_tol=1e-12):
            raise ValueError("Syt + Syc must be nonzero to compute torsional shear yield strength.")
        return (St * Sc) / denominator

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
            name=inputs.get("material_name"),
            source=inputs.get("material_source"),
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
            rows.append(
                {
                    "Case": case["label"],
                    f"s1 {unit}": principals["sigma_1"],
                    f"s2 {unit}": principals["sigma_2"],
                    f"s3 {unit}": principals["sigma_3"],
                    f"svm {unit}": case["derived"]["von_mises_stress"],
                    f"tmax {unit}": case["derived"]["maximum_shear_stress"],
                    "n_DE": fos["DE"],
                    "n_MSS": fos["MSS"],
                }
            )
        return pd.DataFrame(rows)


class Example52CoulombMohrSolver:
    """Implements the Example 5-2 style Coulomb-Mohr solve path."""

    solve_path = "coulomb_mohr_fos"

    def __init__(self, material_table: MaterialTable | None = None) -> None:
        self.material_table = material_table or MaterialTable()

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        solve_path = inputs.get("solve_path")
        if solve_path != self.solve_path:
            raise ValueError(f"Unsupported solve_path '{solve_path}'. Expected '{self.solve_path}'.")

        material = self._build_material(inputs)
        strength_unit = material.strength_unit
        stress_state_payload, geometry_result = self._build_stress_state_payload(inputs)
        state = StressState(stress_state_payload)

        s1, s2, s3 = state.principal_stresses()
        max_shear = state.max_shear_stress()
        n_cm = state.coulomb_mohr_factor_of_safety(material.Syt, float(material.Syc))
        Ssy = state.torsional_shear_yield_strength(material.Syt, float(material.Syc))
        n_shear = inf if isclose(max_shear, 0.0, abs_tol=1e-12) else Ssy / max_shear

        case_label = stress_state_payload.get("label", "case")
        summary_df = pd.DataFrame(
            [
                {
                    "Case": case_label,
                    "Input": stress_state_payload.get("reported_input_mode", state.input_mode),
                    f"s1 {strength_unit}": s1,
                    f"s2 {strength_unit}": s2,
                    f"s3 {strength_unit}": s3,
                    f"tmax {strength_unit}": max_shear,
                    f"Ssy {strength_unit}": Ssy,
                    "n_CM": n_cm,
                    "n_Ssy/tmax": n_shear,
                }
            ]
        )

        result_case = {
            "label": case_label,
            "description": stress_state_payload.get("description", ""),
            "input_mode": stress_state_payload.get("reported_input_mode", state.input_mode),
            "resolved_stress_representation": state.input_mode,
            "ordered_principal_stresses": {
                "sigma_1": s1,
                "sigma_2": s2,
                "sigma_3": s3,
            },
            "derived": {
                "maximum_shear_stress": max_shear,
                "torsional_shear_yield_strength_Ssy": Ssy,
                "coulomb_mohr_plane_case": state.coulomb_mohr_plane_case() if state.input_mode == "plane_stress" else None,
            },
            "factor_of_safety": {
                "Coulomb_Mohr": n_cm,
                "Ssy_over_tau_max": n_shear,
            },
        }
        if geometry_result is not None:
            result_case["geometry_and_loading"] = geometry_result
        if state.input_mode == "plane_stress":
            sigma_a, sigma_b = state.principal_pair_in_plane() or (None, None)
            result_case["plane_stress_inputs"] = {
                "sigma_x": float(stress_state_payload["sigma_x"]),
                "sigma_y": float(stress_state_payload["sigma_y"]),
                "tau_xy": float(stress_state_payload["tau_xy"]),
            }
            result_case["derived"]["in_plane_principal_stresses"] = {
                "sigma_A": sigma_a,
                "sigma_B": sigma_b,
            }
        else:
            result_case["principal_stress_inputs"] = {
                "sigma_1": s1,
                "sigma_2": s2,
                "sigma_3": s3,
            }

        return {
            "problem": payload.get("problem", "static_failure"),
            "title": payload.get("title", "Coulomb-Mohr factor-of-safety analysis"),
            "inputs": inputs,
            "material": material.to_dict(),
            "meta": {
                "solve_path": self.solve_path,
                "applicability": "materials with unequal tensile/compressive yield strengths",
                "implemented_theories": ["Coulomb-Mohr", "Ssy_from_Eq_5_27"],
            },
            "results": {
                "cases": [result_case],
                "summary_table": summary_df.to_dict(orient="records"),
            },
        }

    def _build_material(self, inputs: dict[str, Any]) -> MaterialProperties:
        if inputs.get("material_lookup"):
            row = self.material_table.lookup(str(inputs["material_lookup"]))
            return MaterialProperties(
                Syt=float(inputs.get("Syt", row["Syt"])),
                Syc=float(inputs.get("Syc", row["Syc"])),
                ef=float(inputs["ef"]) if inputs.get("ef") is not None else (float(row["ef"]) if pd.notna(row.get("ef")) else None),
                strength_unit=str(inputs.get("strength_unit", row.get("strength_unit", "MPa"))),
                name=str(inputs.get("material_name", row.get("material_name", inputs["material_lookup"]))),
                source=str(row.get("source", "material_table")),
            )

        if "Syt" not in inputs or "Syc" not in inputs:
            raise ValueError("Provide either 'material_lookup' or both 'Syt' and 'Syc'.")
        return MaterialProperties(
            Syt=float(inputs["Syt"]),
            Syc=float(inputs["Syc"]),
            ef=float(inputs["ef"]) if inputs.get("ef") is not None else None,
            strength_unit=str(inputs.get("strength_unit", "MPa")),
            name=inputs.get("material_name"),
            source=inputs.get("material_source"),
        )

    @staticmethod
    def _build_stress_state_payload(inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        mode = str(inputs.get("stress_input_mode", "torsion_shaft"))

        if mode == "torsion_shaft":
            diameter_mm = float(inputs["diameter_mm"])
            torque_N_m = float(inputs["torque_N_m"])
            diameter_m = diameter_mm * 1e-3
            tau_pa = 16.0 * torque_N_m / (pi * diameter_m**3)
            tau_mpa = tau_pa / 1e6
            stress_state = {
                "label": inputs.get("label", "torsion_shaft"),
                "description": inputs.get("description", "Solid circular shaft in pure torsion."),
                "reported_input_mode": mode,
                "sigma_x": 0.0,
                "sigma_y": 0.0,
                "tau_xy": tau_mpa,
            }
            geometry = {
                "stress_input_mode": mode,
                "diameter_mm": diameter_mm,
                "torque_N_m": torque_N_m,
                "computed_tau_xy_MPa": tau_mpa,
                "equation": "tau = 16*T/(pi*d^3)",
                "unit_note": "Torque entered in N·m and diameter in mm; shear stress reported in MPa.",
            }
            return stress_state, geometry

        if mode == "plane_stress":
            required = {"sigma_x", "sigma_y", "tau_xy"}
            missing = sorted(required.difference(inputs.keys()))
            if missing:
                raise ValueError(f"Missing required plane-stress inputs: {', '.join(missing)}")
            return {
                "label": inputs.get("label", "plane_stress_case"),
                "description": inputs.get("description", "Plane-stress state for Coulomb-Mohr evaluation."),
                "reported_input_mode": mode,
                "sigma_x": float(inputs["sigma_x"]),
                "sigma_y": float(inputs["sigma_y"]),
                "tau_xy": float(inputs["tau_xy"]),
            }, {
                "stress_input_mode": mode,
            }

        if mode == "principal_stresses":
            principal = inputs.get("principal_stresses")
            if principal is None or len(principal) != 3:
                raise ValueError("For stress_input_mode='principal_stresses', provide three values in 'principal_stresses'.")
            return {
                "label": inputs.get("label", "principal_stress_case"),
                "description": inputs.get("description", "Principal-stress state for Coulomb-Mohr evaluation."),
                "reported_input_mode": mode,
                "principal_stresses": [float(v) for v in principal],
            }, {
                "stress_input_mode": mode,
            }

        raise ValueError(
            "Unsupported stress_input_mode. Use one of: 'torsion_shaft', 'plane_stress', 'principal_stresses'."
        )
