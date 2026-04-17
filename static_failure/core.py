from __future__ import annotations

from dataclasses import dataclass
import json
from bisect import bisect_left
from math import inf, isclose, pi, sqrt
from pathlib import Path
from typing import Any

import pandas as pd


def _stress_unit_to_psi_scale(unit: str) -> float:
    normalized = str(unit).strip().lower()
    scales = {
        "psi": 1.0,
        "kpsi": 1000.0,
        "ksi": 1000.0,
        "mpa": 145.03773773020923,
        "gpa": 145037.73773020922,
    }
    if normalized not in scales:
        raise ValueError(f"Unsupported stress unit: {unit}")
    return scales[normalized]


def convert_stress_value(value: float, from_unit: str, to_unit: str) -> float:
    if str(from_unit).strip().lower() == str(to_unit).strip().lower():
        return float(value)
    value_psi = float(value) * _stress_unit_to_psi_scale(from_unit)
    return value_psi / _stress_unit_to_psi_scale(to_unit)


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
        return matches.iloc[0].to_dict()


class TableA8:
    """CSV-backed stock round-tubing table (Table A-8)."""

    def __init__(self, csv_path: str | Path | None = None) -> None:
        self.csv_path = Path(csv_path) if csv_path is not None else Path(__file__).resolve().parent / "data" / "table_a_8.csv"
        self._table: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._table is None:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"Table A-8 not found: {self.csv_path}")
            self._table = pd.read_csv(self.csv_path)
        return self._table.copy()

    @staticmethod
    def _parse_size_mm(size_value: str) -> tuple[float, float]:
        raw = str(size_value).replace("×", "x")
        parts = [p.strip() for p in raw.split("x")]
        if len(parts) != 2:
            raise ValueError(f"Could not parse Table A-8 metric size '{size_value}'. Expected 'OD x t'.")
        return float(parts[0]), float(parts[1])

    def metric_candidates(self) -> list[dict[str, Any]]:
        table = self._load()
        df = table.loc[table["size_system"].astype(str).str.lower() == "mm"].copy()
        if df.empty:
            raise ValueError("No metric rows were found in table_a_8.csv.")
        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            od_mm, thickness_mm = self._parse_size_mm(str(row["size"]))
            area_cm2 = float(row["A"])
            i_cm4 = float(row["I"])
            j_cm4 = float(row["J"])
            rows.append(
                {
                    "size_system": "mm",
                    "size": str(row["size"]),
                    "od_mm": od_mm,
                    "thickness_mm": thickness_mm,
                    "area_cm2": area_cm2,
                    "I_cm4": i_cm4,
                    "J_cm4": j_cm4,
                    "k_cm": float(row["k"]),
                    "Z_cm3": float(row["Z"]),
                    "mass_kg_per_m": float(row["m_kg_per_m"]) if pd.notna(row.get("m_kg_per_m")) else None,
                    "A_mm2": area_cm2 * 100.0,
                    "I_mm4": i_cm4 * 1.0e4,
                    "J_mm4": j_cm4 * 1.0e4,
                }
            )
        return rows


class TableA24GrayCastIron:
    """CSV-backed ASTM gray cast iron table (Table A-24)."""

    def __init__(self, csv_path: str | Path | None = None) -> None:
        self.csv_path = Path(csv_path) if csv_path is not None else Path(__file__).resolve().parent / "data" / "table_a_24_gray_cast_iron.csv"
        self._table: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._table is None:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"Table A-24 not found: {self.csv_path}")
            self._table = pd.read_csv(self.csv_path)
        return self._table.copy()

    def lookup_grade(self, astm_number: int | str) -> dict[str, Any]:
        table = self._load()
        mask = table["astm_number"].astype(str).str.strip() == str(astm_number).strip()
        matches = table.loc[mask]
        if matches.empty:
            known = ", ".join(table["astm_number"].astype(str).tolist())
            raise ValueError(f"Unknown ASTM gray cast iron grade '{astm_number}'. Available grades: {known}")
        return matches.iloc[0].to_dict()


class Table51FractureToughness:
    """CSV-backed fracture-toughness table (Table 5-1)."""

    def __init__(self, csv_path: str | Path | None = None) -> None:
        self.csv_path = Path(csv_path) if csv_path is not None else Path(__file__).resolve().parent / "data" / "table_5_1.csv"
        self._table: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if self._table is None:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"Table 5-1 not found: {self.csv_path}")
            self._table = pd.read_csv(self.csv_path)
        return self._table.copy()

    def lookup_all(self, material_family: str, material_grade: str) -> list[dict[str, Any]]:
        table = self._load()
        fam_mask = table["material_family"].astype(str).str.strip().str.lower() == str(material_family).strip().lower()
        grade_mask = table["material_grade"].astype(str).str.strip().str.lower() == str(material_grade).strip().lower()
        matches = table.loc[fam_mask & grade_mask]
        if matches.empty:
            known = ", ".join(f"{r.material_family}:{r.material_grade}" for r in table[["material_family", "material_grade"]].itertuples(index=False))
            raise ValueError(f"Unknown Table 5-1 material '{material_family}:{material_grade}'. Available rows: {known}")
        return matches.to_dict(orient="records")

    def lookup(self, material_family: str, material_grade: str) -> dict[str, Any]:
        matches = self.lookup_all(material_family, material_grade)
        if len(matches) > 1:
            raise ValueError(
                f"Table 5-1 lookup for '{material_family}:{material_grade}' is ambiguous. "
                f"Provide direct K_Ic/Syt inputs instead. Matching rows: {matches}"
            )
        return matches[0]


class FigureJsonLibrary:
    """JSON-backed fracture beta-curve library with interpolation helpers."""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else Path(__file__).resolve().parent / "data"
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, figure_id: str) -> dict[str, Any]:
        normalized = str(figure_id).strip().lower().replace("-", "_")
        if not normalized.startswith("figure_"):
            normalized = f"figure_{normalized}"
        path = self.data_dir / f"{normalized}.json"
        if normalized not in self._cache:
            if not path.exists():
                raise FileNotFoundError(f"Figure JSON not found: {path}")
            self._cache[normalized] = json.loads(path.read_text(encoding="utf-8"))
        return self._cache[normalized]

    @staticmethod
    def _interp_curve(points: list[list[float]], x: float) -> float:
        if len(points) < 2:
            raise ValueError("A curve needs at least two points for interpolation.")
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        if x < xs[0] or x > xs[-1]:
            raise ValueError(f"x={x} is outside the curve domain [{xs[0]}, {xs[-1]}].")
        if isclose(x, xs[0], abs_tol=1e-12):
            return ys[0]
        if isclose(x, xs[-1], abs_tol=1e-12):
            return ys[-1]
        i = bisect_left(xs, x)
        if i < len(xs) and isclose(xs[i], x, abs_tol=1e-12):
            return ys[i]
        x0, x1 = xs[i - 1], xs[i]
        y0, y1 = ys[i - 1], ys[i]
        if isclose(x1, x0, abs_tol=1e-12):
            return y0
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    @staticmethod
    def _extract_numeric_suffix(curve_key: str) -> float:
        token = str(curve_key).rsplit("_", 1)[-1]
        return float(token)

    def interpolate_named_curve(self, figure_id: str, x: float, family: str, curve_key: str) -> dict[str, Any]:
        beta = self.interpolate_curve(figure_id=figure_id, curve_key=curve_key, x=x, family=family)
        return {"beta": beta, "curve_key": curve_key, "interpolation": "exact_curve"}

    def interpolate_curve(self, figure_id: str, curve_key: str, x: float, family: str | None = None) -> float:
        figure = self.load(figure_id)
        curves = figure.get("curves", {})
        if family is not None:
            curves = curves[family]
        points = curves[curve_key]
        return self._interp_curve(points, x)

    def interpolate_family_parameter(self, figure_id: str, x: float, parameter_value: float, family: str | None = None, prefix: str | None = None) -> dict[str, Any]:
        figure = self.load(figure_id)
        curves = figure.get("curves", {})
        if family is not None:
            curves = curves[family]
        available: list[tuple[float, str]] = []
        for key in curves.keys():
            if prefix is not None and not str(key).startswith(prefix):
                continue
            try:
                available.append((self._extract_numeric_suffix(key), str(key)))
            except Exception:
                continue
        if not available:
            raise ValueError(f"No parameterized curves found in {figure_id} for family={family} prefix={prefix}.")
        available.sort(key=lambda item: item[0])
        values = [v for v, _ in available]
        keys = [k for _, k in available]
        if parameter_value < values[0] or parameter_value > values[-1]:
            raise ValueError(f"Parameter value {parameter_value} is outside available range [{values[0]}, {values[-1]}] for {figure_id}.")
        for v, k in available:
            if isclose(v, parameter_value, rel_tol=1e-9, abs_tol=1e-12):
                beta = self.interpolate_curve(figure_id, k, x, family=family)
                return {"beta": beta, "curve_key": k, "parameter_value": v, "interpolation": "exact"}
        i = bisect_left(values, parameter_value)
        v0, k0 = values[i - 1], keys[i - 1]
        v1, k1 = values[i], keys[i]
        beta0 = self.interpolate_curve(figure_id, k0, x, family=family)
        beta1 = self.interpolate_curve(figure_id, k1, x, family=family)
        beta = beta0 + (beta1 - beta0) * (parameter_value - v0) / (v1 - v0)
        return {"beta": beta, "curve_key_lower": k0, "curve_key_upper": k1, "parameter_value_lower": v0, "parameter_value_upper": v1, "beta_lower": beta0, "beta_upper": beta1, "interpolation": "linear_between_curves"}


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
        return self.mss_plane_case()

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

    def brittle_coulomb_mohr_factor_of_safety(self, Sut: float, Suc: float) -> tuple[float, str]:
        sA, sB = self._required_plane_principal_pair()
        if sA >= sB >= 0.0:
            denom = sA / Sut
            case = "eq_5_31a_sigmaA>=sigmaB>=0"
        elif sA >= 0.0 >= sB:
            denom = (sA / Sut) - (sB / Suc)
            case = "eq_5_31b_sigmaA>=0>=sigmaB"
        else:
            denom = (-sB) / Suc
            case = "eq_5_31c_0>=sigmaA>=sigmaB"
        if isclose(denom, 0.0, abs_tol=1e-12):
            return inf, case
        return 1.0 / denom, case

    def modified_mohr_factor_of_safety(self, Sut: float, Suc: float) -> tuple[float, str, float | None]:
        sA, sB = self._required_plane_principal_pair()
        ratio = None if isclose(sA, 0.0, abs_tol=1e-12) else abs(sB / sA)
        if sA >= sB >= 0.0:
            denom = sA / Sut
            case = "eq_5_32a_sigmaA>=sigmaB>=0"
        elif sA >= 0.0 >= sB:
            if ratio is not None and ratio <= 1.0:
                denom = sA / Sut
                case = "eq_5_32a_sigmaA>=0>=sigmaB_and_abs_sigmaB_over_sigmaA<=1"
            else:
                denom = ((Suc - Sut) / (Suc * Sut)) * sA - (sB / Suc)
                case = "eq_5_32b_sigmaA>=0>=sigmaB_and_abs_sigmaB_over_sigmaA>1"
        else:
            denom = (-sB) / Suc
            case = "eq_5_32c_0>=sigmaA>=sigmaB"
        if isclose(denom, 0.0, abs_tol=1e-12):
            return inf, case, ratio
        return 1.0 / denom, case, ratio

    def _required_plane_principal_pair(self) -> tuple[float, float]:
        if self.input_mode != "plane_stress":
            raise ValueError("Brittle material plane-stress criteria require a plane-stress state.")
        sigma_a, sigma_b = self.principal_pair_in_plane() or (None, None)
        assert sigma_a is not None and sigma_b is not None
        return sigma_a, sigma_b

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
        summary_df = pd.DataFrame([
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
        ])

        result_case = {
            "label": case_label,
            "description": stress_state_payload.get("description", ""),
            "input_mode": stress_state_payload.get("reported_input_mode", state.input_mode),
            "resolved_stress_representation": state.input_mode,
            "ordered_principal_stresses": {"sigma_1": s1, "sigma_2": s2, "sigma_3": s3},
            "derived": {
                "maximum_shear_stress": max_shear,
                "torsional_shear_yield_strength_Ssy": Ssy,
                "coulomb_mohr_plane_case": state.coulomb_mohr_plane_case() if state.input_mode == "plane_stress" else None,
            },
            "factor_of_safety": {"Coulomb_Mohr": n_cm, "Ssy_over_tau_max": n_shear},
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
            result_case["derived"]["in_plane_principal_stresses"] = {"sigma_A": sigma_a, "sigma_B": sigma_b}
        else:
            result_case["principal_stress_inputs"] = {"sigma_1": s1, "sigma_2": s2, "sigma_3": s3}

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
            "results": {"cases": [result_case], "summary_table": summary_df.to_dict(orient="records")},
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
            }, {"stress_input_mode": mode}
        if mode == "principal_stresses":
            principal = inputs.get("principal_stresses")
            if principal is None or len(principal) != 3:
                raise ValueError("For stress_input_mode='principal_stresses', provide three values in 'principal_stresses'.")
            return {
                "label": inputs.get("label", "principal_stress_case"),
                "description": inputs.get("description", "Principal-stress state for Coulomb-Mohr evaluation."),
                "reported_input_mode": mode,
                "principal_stresses": [float(v) for v in principal],
            }, {"stress_input_mode": mode}
        raise ValueError("Unsupported stress_input_mode. Use one of: 'torsion_shaft', 'plane_stress', 'principal_stresses'.")


class Example53FailureTheoryStrengthSolver:
    solve_path = "failure_theory_strength"

    def __init__(self, material_table: MaterialTable | None = None) -> None:
        self.material_table = material_table or MaterialTable()

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") != self.solve_path:
            raise ValueError(f"Unsupported solve_path '{inputs.get('solve_path')}'. Expected '{self.solve_path}'.")
        material = self._build_material(inputs)
        geometry = self._build_geometry(inputs)
        target = {"design_factor": float(inputs.get("design_factor", 1.0))}
        section = self._compute_section_response(geometry, material.strength_unit, force=1.0)
        normalized_state = StressState({
            "label": inputs.get("label", "failure_theory_strength_case"),
            "description": inputs.get("description", "Critical section under combined bending and torsion, normalized per unit applied force."),
            "sigma_x": section["sigma_x_per_force"],
            "sigma_y": 0.0,
            "tau_xy": section["tau_xy_per_force"],
        })
        sigma_vm_per_force = normalized_state.von_mises_stress()
        tau_max_per_force = normalized_state.max_shear_stress()
        s1_pf, s2_pf, s3_pf = normalized_state.principal_stresses()
        sigma_a_pf, sigma_b_pf = normalized_state.principal_pair_in_plane() or (None, None)
        F_de = inf if isclose(sigma_vm_per_force, 0.0, abs_tol=1e-12) else material.Syt / (target["design_factor"] * sigma_vm_per_force)
        F_mss = inf if isclose(tau_max_per_force, 0.0, abs_tol=1e-12) else (material.Syt / 2.0) / (target["design_factor"] * tau_max_per_force)
        stress_at_de = self._evaluate_state_for_force(section, F_de)
        stress_at_mss = self._evaluate_state_for_force(section, F_mss)
        summary_df = pd.DataFrame([
            {"Theory": "DE", f"Strength {geometry['force_unit']}": F_de, f"svm coeff {material.strength_unit}/{geometry['force_unit']}": sigma_vm_per_force, f"tmax coeff {material.strength_unit}/{geometry['force_unit']}": tau_max_per_force},
            {"Theory": "MSS", f"Strength {geometry['force_unit']}": F_mss, f"svm coeff {material.strength_unit}/{geometry['force_unit']}": sigma_vm_per_force, f"tmax coeff {material.strength_unit}/{geometry['force_unit']}": tau_max_per_force},
        ])
        return {
            "problem": payload.get("problem", "static_failure"),
            "title": payload.get("title", "Failure-theory strength analysis"),
            "inputs": inputs,
            "material": material.to_dict(),
            "meta": {"solve_path": self.solve_path, "applicability": "ductile components where the load causing first yield is sought", "implemented_theories": ["DE", "MSS"], "normalized_solution_strategy": "stresses computed per unit applied force, then inverted for force at yield"},
            "results": {
                "critical_section": {
                    "label": inputs.get("label", "failure_theory_strength_case"),
                    "description": inputs.get("description", "Critical section under combined bending and torsion."),
                    "normalized_stress_state_per_unit_force": {"sigma_x_per_force": section["sigma_x_per_force"], "sigma_y_per_force": 0.0, "tau_xy_per_force": section["tau_xy_per_force"], "stress_per_force_unit": f"{material.strength_unit}/{geometry['force_unit']}"},
                    "normalized_failure_metrics_per_unit_force": {
                        "von_mises_per_force": sigma_vm_per_force,
                        "maximum_shear_per_force": tau_max_per_force,
                        "principal_stresses_per_force": {"sigma_1": s1_pf, "sigma_2": s2_pf, "sigma_3": s3_pf},
                        "in_plane_principal_stresses_per_force": {"sigma_A": sigma_a_pf, "sigma_B": sigma_b_pf},
                    },
                    "normalized_loading_coefficients": {"bending_moment_per_force": geometry["bending_moment_arm_in"], "torque_per_force": geometry["torsion_arm_in"], "moment_unit_per_force": f"{geometry['moment_unit']}/{geometry['force_unit']}"},
                },
                "strength_predictions": {
                    "DE": {"strength_force": F_de, "force_unit": geometry["force_unit"], "design_factor": target["design_factor"], "equation_used": "F = Sy / (nd * sigma_vm_per_unit_force)", "stress_state_at_strength": stress_at_de},
                    "MSS": {"strength_force": F_mss, "force_unit": geometry["force_unit"], "design_factor": target["design_factor"], "equation_used": "F = (Sy/2) / (nd * tau_max_per_unit_force)", "stress_state_at_strength": stress_at_mss},
                },
                "summary_table": summary_df.to_dict(orient="records"),
            },
        }

    def _build_material(self, inputs: dict[str, Any]) -> MaterialProperties:
        if inputs.get("material_lookup"):
            row = self.material_table.lookup(str(inputs["material_lookup"]))
            syt = float(inputs.get("Syt", row["Syt"]))
            syc_raw = row.get("Syc")
            syc = float(inputs.get("Syc", syc_raw if pd.notna(syc_raw) else syt))
            ef = float(inputs["ef"]) if inputs.get("ef") is not None else (float(row["ef"]) if pd.notna(row.get("ef")) else None)
            return MaterialProperties(Syt=syt, Syc=syc, ef=ef, strength_unit=str(inputs.get("strength_unit", row.get("strength_unit", "kpsi"))), name=str(inputs.get("material_name", row.get("material_name", inputs["material_lookup"]))), source=str(row.get("source", "material_table")))
        if "Syt" not in inputs:
            raise ValueError("Provide either 'material_lookup' or 'Syt'.")
        syt = float(inputs["Syt"])
        syc = float(inputs.get("Syc", syt))
        return MaterialProperties(Syt=syt, Syc=syc, ef=float(inputs["ef"]) if inputs.get("ef") is not None else None, strength_unit=str(inputs.get("strength_unit", "kpsi")), name=inputs.get("material_name"), source=inputs.get("material_source"))

    @staticmethod
    def _build_geometry(inputs: dict[str, Any]) -> dict[str, Any]:
        geometry_mode = str(inputs.get("geometry_mode", "round_shaft_bending_torsion_linear_force"))
        if geometry_mode != "round_shaft_bending_torsion_linear_force":
            raise ValueError("Unsupported geometry_mode. Use 'round_shaft_bending_torsion_linear_force'.")
        required = ["diameter_in", "bending_moment_arm_in", "torsion_arm_in"]
        missing = [key for key in required if key not in inputs]
        if missing:
            raise ValueError(f"Missing required geometry inputs: {', '.join(missing)}")
        return {
            "geometry_mode": geometry_mode,
            "diameter_in": float(inputs["diameter_in"]),
            "bending_moment_arm_in": float(inputs["bending_moment_arm_in"]),
            "torsion_arm_in": float(inputs["torsion_arm_in"]),
            "force_unit": str(inputs.get("force_unit", "lbf")),
            "moment_unit": str(inputs.get("moment_unit", "lbf·in")),
            "stress_concentration_considered": bool(inputs.get("stress_concentration_considered", False)),
            "section_note": inputs.get("section_note"),
        }

    @staticmethod
    def _stress_unit_scale_from_psi(strength_unit: str) -> float:
        unit = str(strength_unit).strip().lower()
        scales = {"psi": 1.0, "kpsi": 1.0 / 1000.0, "ksi": 1.0 / 1000.0, "mpa": 0.006894757293168361, "gpa": 6.894757293168361e-06}
        if unit not in scales:
            raise ValueError(f"Unsupported strength_unit for Example 5-3 geometry conversion: {strength_unit}")
        return scales[unit]

    @classmethod
    def _compute_section_response(cls, geometry: dict[str, Any], strength_unit: str, force: float) -> dict[str, float]:
        d = geometry["diameter_in"]
        M = geometry["bending_moment_arm_in"] * force
        T = geometry["torsion_arm_in"] * force
        sigma_x_psi = 32.0 * M / (pi * d**3)
        tau_xy_psi = 16.0 * T / (pi * d**3)
        scale = cls._stress_unit_scale_from_psi(strength_unit)
        sigma_x = sigma_x_psi * scale
        tau_xy = tau_xy_psi * scale
        return {
            "bending_moment": M,
            "torque": T,
            "sigma_x_per_force": sigma_x / force if not isclose(force, 0.0, abs_tol=1e-12) else 32.0 * geometry["bending_moment_arm_in"] / (pi * d**3) * scale,
            "tau_xy_per_force": tau_xy / force if not isclose(force, 0.0, abs_tol=1e-12) else 16.0 * geometry["torsion_arm_in"] / (pi * d**3) * scale,
        }

    @staticmethod
    def _evaluate_state_for_force(section: dict[str, float], force: float) -> dict[str, Any]:
        sigma_x = section["sigma_x_per_force"] * force
        tau_xy = section["tau_xy_per_force"] * force
        state = StressState({"label": "evaluated_strength_state", "sigma_x": sigma_x, "sigma_y": 0.0, "tau_xy": tau_xy})
        s1, s2, s3 = state.principal_stresses()
        sigma_a, sigma_b = state.principal_pair_in_plane() or (None, None)
        return {
            "plane_stress_inputs": {"sigma_x": sigma_x, "sigma_y": 0.0, "tau_xy": tau_xy},
            "ordered_principal_stresses": {"sigma_1": s1, "sigma_2": s2, "sigma_3": s3},
            "derived": {"von_mises_stress": state.von_mises_stress(), "maximum_shear_stress": state.max_shear_stress(), "in_plane_principal_stresses": {"sigma_A": sigma_a, "sigma_B": sigma_b}},
        }


class Example54RealizedFactorOfSafetySolver:
    solve_path = "realized_fos_stock_tube"

    def __init__(self, material_table: MaterialTable | None = None, tube_table: TableA8 | None = None) -> None:
        self.material_table = material_table or MaterialTable()
        self.tube_table = tube_table or TableA8()

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") != self.solve_path:
            raise ValueError(f"Unsupported solve_path '{inputs.get('solve_path')}'. Expected '{self.solve_path}'.")
        material = self._build_material(inputs)
        loading = self._build_loading(inputs)
        selection = {"required_design_factor": float(inputs.get("required_design_factor", inputs.get("design_factor", 1.0))), "size_system": str(inputs.get("size_system", "mm")).lower()}
        candidates = self._evaluate_candidates(loading=loading, material=material, selection=selection)
        selected = next((row for row in candidates if row["meets_required_design_factor"]), None)
        if selected is None:
            raise ValueError(f"No Table A-8 metric tube met the required design factor nd={selection['required_design_factor']}.")
        summary_df = pd.DataFrame([{"Size": row["size"], "OD mm": row["od_mm"], "t mm": row["thickness_mm"], "sigma_x MPa": row["sigma_x"], "tau MPa": row["tau_xy"], "svm MPa": row["von_mises_stress"], "n_DE": row["n_DE"], "Selected": row["selected"]} for row in candidates])
        return {
            "problem": payload.get("problem", "static_failure"),
            "title": payload.get("title", "Realized factor-of-safety stock tube selection"),
            "inputs": inputs,
            "material": material.to_dict(),
            "meta": {"solve_path": self.solve_path, "applicability": "stock round tubes under combined axial, bending, and torsion loading", "implemented_theories": ["DE", "MSS"], "selection_rule": "first Table A-8 metric size meeting the required design factor in table order"},
            "results": {"selected_candidate": selected, "all_candidates": candidates, "summary_table": summary_df.to_dict(orient="records")},
        }

    def _build_material(self, inputs: dict[str, Any]) -> MaterialProperties:
        if inputs.get("material_lookup"):
            row = self.material_table.lookup(str(inputs["material_lookup"]))
            syt = float(inputs.get("Syt", row["Syt"]))
            syc_raw = row.get("Syc")
            syc = float(inputs.get("Syc", syc_raw if pd.notna(syc_raw) else syt))
            ef = float(inputs["ef"]) if inputs.get("ef") is not None else (float(row["ef"]) if pd.notna(row.get("ef")) else None)
            return MaterialProperties(Syt=syt, Syc=syc, ef=ef, strength_unit=str(inputs.get("strength_unit", row.get("strength_unit", "MPa"))), name=str(inputs.get("material_name", row.get("material_name", inputs["material_lookup"]))), source=str(row.get("source", "material_table")))
        if "Syt" not in inputs:
            raise ValueError("Provide either 'material_lookup' or 'Syt'.")
        syt = float(inputs["Syt"])
        syc = float(inputs.get("Syc", syt))
        return MaterialProperties(Syt=syt, Syc=syc, ef=float(inputs["ef"]) if inputs.get("ef") is not None else None, strength_unit=str(inputs.get("strength_unit", "MPa")), name=inputs.get("material_name"), source=inputs.get("material_source"))

    @staticmethod
    def _build_loading(inputs: dict[str, Any]) -> dict[str, Any]:
        loading_mode = str(inputs.get("loading_mode", "tube_axial_bending_torsion"))
        if loading_mode != "tube_axial_bending_torsion":
            raise ValueError("Unsupported loading_mode. Use 'tube_axial_bending_torsion'.")
        if "axial_force_N" not in inputs or "torsion_N_m" not in inputs:
            raise ValueError("Missing required loading inputs.")
        if "bending_moment_N_mm" in inputs:
            bending_moment_n_mm = float(inputs["bending_moment_N_mm"])
        else:
            required = ["bending_load_N", "bending_moment_arm_mm"]
            missing = [key for key in required if key not in inputs]
            if missing:
                raise ValueError("Provide either 'bending_moment_N_mm' or both 'bending_load_N' and 'bending_moment_arm_mm'.")
            bending_moment_n_mm = float(inputs["bending_load_N"]) * float(inputs["bending_moment_arm_mm"])
        return {
            "loading_mode": loading_mode,
            "axial_force_N": float(inputs["axial_force_N"]),
            "bending_moment_N_mm": bending_moment_n_mm,
            "torsion_N_mm": float(inputs["torsion_N_m"]) * 1000.0,
            "input_trace": {
                "axial_force_N": float(inputs["axial_force_N"]),
                "bending_load_N": float(inputs["bending_load_N"]) if inputs.get("bending_load_N") is not None else None,
                "bending_moment_arm_mm": float(inputs["bending_moment_arm_mm"]) if inputs.get("bending_moment_arm_mm") is not None else None,
                "bending_moment_N_mm": bending_moment_n_mm,
                "torsion_N_m": float(inputs["torsion_N_m"]),
            },
        }

    def _evaluate_candidates(self, loading: dict[str, Any], material: MaterialProperties, selection: dict[str, Any]) -> list[dict[str, Any]]:
        if selection["size_system"] != "mm":
            raise ValueError("This solve path currently evaluates the metric portion of Table A-8 only (size_system='mm').")
        candidates = self.tube_table.metric_candidates()
        required_n = selection["required_design_factor"]
        results: list[dict[str, Any]] = []
        found = False
        for row in candidates:
            sigma_x = loading["axial_force_N"] / row["A_mm2"] + loading["bending_moment_N_mm"] * (row["od_mm"] / 2.0) / row["I_mm4"]
            tau_xy = loading["torsion_N_mm"] * (row["od_mm"] / 2.0) / row["J_mm4"]
            state = StressState({"label": row["size"], "description": "Tube outer-surface critical stress state from combined axial, bending, and torsion.", "sigma_x": sigma_x, "sigma_y": 0.0, "tau_xy": tau_xy})
            s1, s2, s3 = state.principal_stresses()
            sigma_a, sigma_b = state.principal_pair_in_plane() or (None, None)
            n_de = state.de_factor_of_safety(material.Syt)
            n_mss = state.mss_factor_of_safety(material.Syt)
            meets = n_de >= required_n
            selected_flag = (not found) and meets
            if selected_flag:
                found = True
            results.append({
                "size": row["size"], "size_system": row["size_system"], "od_mm": row["od_mm"], "thickness_mm": row["thickness_mm"], "area_cm2": row["area_cm2"], "I_cm4": row["I_cm4"], "J_cm4": row["J_cm4"], "mass_kg_per_m": row["mass_kg_per_m"],
                "sigma_x": sigma_x, "tau_xy": tau_xy,
                "ordered_principal_stresses": {"sigma_1": s1, "sigma_2": s2, "sigma_3": s3},
                "derived": {"von_mises_stress": state.von_mises_stress(), "maximum_shear_stress": state.max_shear_stress(), "in_plane_principal_stresses": {"sigma_A": sigma_a, "sigma_B": sigma_b}},
                "factor_of_safety": {"DE": n_de, "MSS": n_mss}, "n_DE": n_de, "n_MSS": n_mss, "von_mises_stress": state.von_mises_stress(), "meets_required_design_factor": meets, "selected": selected_flag,
            })
            if found:
                break
        return results


class Example55BrittleFailureStrengthSolver:
    solve_path = "brittle_failure_strength"

    def __init__(self, cast_iron_table: TableA24GrayCastIron | None = None) -> None:
        self.cast_iron_table = cast_iron_table or TableA24GrayCastIron()

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") != self.solve_path:
            raise ValueError(f"Unsupported solve_path '{inputs.get('solve_path')}'. Expected '{self.solve_path}'.")
        material = self._build_material(inputs)
        model = self._build_model(inputs)
        normalized = self._build_normalized_plane_stress_state(inputs)
        state = StressState(normalized)
        s1_pf, s2_pf, s3_pf = state.principal_stresses()
        sigma_a_pf, sigma_b_pf = state.principal_pair_in_plane() or (None, None)
        if sigma_a_pf is None or sigma_b_pf is None:
            raise ValueError("Example 5-5 solve path requires a plane-stress representation.")
        n_bcm, bcm_case = state.brittle_coulomb_mohr_factor_of_safety(material.Syt, float(material.Syc))
        n_mm, mm_case, mm_ratio = state.modified_mohr_factor_of_safety(material.Syt, float(material.Syc))
        F_bcm = n_bcm / model["design_factor"]
        F_mm = n_mm / model["design_factor"]
        bcm_state = self._evaluate_state_for_force(normalized, F_bcm)
        mm_state = self._evaluate_state_for_force(normalized, F_mm)
        summary_df = pd.DataFrame([
            {"Theory": "Brittle_Coulomb_Mohr", f"Strength {model['force_unit']}": F_bcm, f"sigma_A coeff {material.strength_unit}/{model['force_unit']}": sigma_a_pf, f"sigma_B coeff {material.strength_unit}/{model['force_unit']}": sigma_b_pf, "criterion_case": bcm_case},
            {"Theory": "Modified_Mohr", f"Strength {model['force_unit']}": F_mm, f"sigma_A coeff {material.strength_unit}/{model['force_unit']}": sigma_a_pf, f"sigma_B coeff {material.strength_unit}/{model['force_unit']}": sigma_b_pf, "criterion_case": mm_case},
        ])
        return {
            "problem": payload.get("problem", "static_failure"),
            "title": payload.get("title", "Brittle-material strength analysis"),
            "inputs": inputs,
            "material": {
                **material.to_dict(),
                "Sut": material.Syt,
                "Suc": material.Syc,
                "material_type": "brittle",
                "strength_properties": {
                    "Sut": material.Syt,
                    "Suc": material.Syc,
                    "strength_unit": material.strength_unit,
                    "governing_strength_names": ["Sut", "Suc"],
                    "note": "For brittle-material paths, Sut and Suc are the governing strengths. Syt and Syc are retained as internal compatibility aliases.",
                },
            },
            "meta": {
                "solve_path": self.solve_path,
                "applicability": "brittle materials in plane stress using Coulomb-Mohr and Modified Mohr criteria",
                "implemented_theories": ["Brittle_Coulomb_Mohr", "Modified_Mohr"],
                "normalized_solution_strategy": "principal stresses computed per unit applied force, then inverted for force at fracture",
            },
            "results": {
                "critical_section": {
                    "label": normalized.get("label", "brittle_failure_strength_case"),
                    "description": normalized.get("description", "Critical plane-stress section for brittle failure."),
                    "resolved_stress_representation": "plane_stress",
                    "normalized_stress_state_per_unit_force": {
                        "sigma_x_per_force": normalized["sigma_x"],
                        "sigma_y_per_force": normalized["sigma_y"],
                        "tau_xy_per_force": normalized["tau_xy"],
                        "stress_per_force_unit": f"{material.strength_unit}/{model['force_unit']}",
                    },
                    "normalized_failure_metrics_per_unit_force": {
                        "principal_stresses_per_force": {"sigma_1": s1_pf, "sigma_2": s2_pf, "sigma_3": s3_pf},
                        "in_plane_principal_stresses_per_force": {"sigma_A": sigma_a_pf, "sigma_B": sigma_b_pf},
                        "brittle_coulomb_mohr_case": bcm_case,
                        "modified_mohr_case": mm_case,
                        "modified_mohr_abs_sigmaB_over_sigmaA": mm_ratio,
                    },
                    "normalized_loading_coefficients": normalized.get("normalized_loading_coefficients"),
                },
                "strength_predictions": {
                    "Brittle_Coulomb_Mohr": {
                        "strength_force": F_bcm,
                        "force_unit": model["force_unit"],
                        "design_factor": model["design_factor"],
                        "equation_used": "F = n_BCM_unit_force / nd",
                        "criterion_case": bcm_case,
                        "stress_state_at_strength": bcm_state,
                    },
                    "Modified_Mohr": {
                        "strength_force": F_mm,
                        "force_unit": model["force_unit"],
                        "design_factor": model["design_factor"],
                        "equation_used": "F = n_MM_unit_force / nd",
                        "criterion_case": mm_case,
                        "abs_sigmaB_over_sigmaA": mm_ratio,
                        "stress_state_at_strength": mm_state,
                    },
                },
                "summary_table": summary_df.to_dict(orient="records"),
            },
        }

    def _build_material(self, inputs: dict[str, Any]) -> MaterialProperties:
        grade = inputs.get("gray_cast_iron_astm_grade") or inputs.get("astm_grade")
        if grade is None:
            raise ValueError("Provide 'gray_cast_iron_astm_grade' to fetch Sut and Suc from table_a_24_gray_cast_iron.csv.")
        row = self.cast_iron_table.lookup_grade(grade)
        sut = float(inputs.get("Sut", row["tensile_strength_Sut_kpsi"]))
        suc = float(inputs.get("Suc", row["compressive_strength_Suc_kpsi"]))
        return MaterialProperties(
            Syt=sut,
            Syc=suc,
            ef=None,
            strength_unit=str(inputs.get("strength_unit", "kpsi")),
            name=str(inputs.get("material_name", f"ASTM grade {grade} gray cast iron")),
            source=str(inputs.get("material_source", "Table A-24 gray cast iron")),
        )

    @staticmethod
    def _build_model(inputs: dict[str, Any]) -> dict[str, Any]:
        return {"design_factor": float(inputs.get("design_factor", 1.0)), "force_unit": str(inputs.get("force_unit", "lbf"))}

    @classmethod
    def _build_normalized_plane_stress_state(cls, inputs: dict[str, Any]) -> dict[str, Any]:
        mode = str(inputs.get("stress_input_mode", "linear_plane_stress_per_force"))
        if mode == "linear_plane_stress_per_force":
            required = ["sigma_x_per_force", "tau_xy_per_force"]
            missing = [k for k in required if k not in inputs]
            if missing:
                raise ValueError(f"Missing required inputs for linear_plane_stress_per_force: {', '.join(missing)}")
            sigma_y_pf = float(inputs.get("sigma_y_per_force", 0.0))
            return {
                "label": inputs.get("label", "brittle_failure_strength_case"),
                "description": inputs.get("description", "Plane-stress state normalized per unit applied force."),
                "sigma_x": float(inputs["sigma_x_per_force"]),
                "sigma_y": sigma_y_pf,
                "tau_xy": float(inputs["tau_xy_per_force"]),
                "normalized_loading_coefficients": {
                    "stress_input_mode": mode,
                    "stress_per_force_unit": f"{inputs.get('strength_unit', 'kpsi')}/{inputs.get('force_unit', 'lbf')}",
                },
            }
        if mode == "round_shaft_bending_torsion_linear_force":
            required = ["diameter_in", "bending_moment_arm_in", "torsion_arm_in"]
            missing = [k for k in required if k not in inputs]
            if missing:
                raise ValueError(f"Missing required inputs for round_shaft_bending_torsion_linear_force: {', '.join(missing)}")
            d = float(inputs["diameter_in"])
            Lb = float(inputs["bending_moment_arm_in"])
            Lt = float(inputs["torsion_arm_in"])
            Kf = float(inputs.get("Kf", 1.0))
            Kfs = float(inputs.get("Kfs", 1.0))
            scale = Example53FailureTheoryStrengthSolver._stress_unit_scale_from_psi(str(inputs.get("strength_unit", "kpsi")))
            sigma_x_pf = Kf * 32.0 * Lb / (pi * d**3) * scale
            tau_xy_pf = Kfs * 16.0 * Lt / (pi * d**3) * scale
            return {
                "label": inputs.get("label", "brittle_failure_strength_case"),
                "description": inputs.get("description", "Round-shaft critical plane-stress state normalized per unit applied force."),
                "sigma_x": sigma_x_pf,
                "sigma_y": 0.0,
                "tau_xy": tau_xy_pf,
                "normalized_loading_coefficients": {
                    "stress_input_mode": mode,
                    "diameter_in": d,
                    "bending_moment_arm_in": Lb,
                    "torsion_arm_in": Lt,
                    "Kf": Kf,
                    "Kfs": Kfs,
                    "sigma_x_per_force_equation": "Kf*32*M/(pi*d^3) with M=L_b*F",
                    "tau_xy_per_force_equation": "Kfs*16*T/(pi*d^3) with T=L_t*F",
                },
            }
        raise ValueError("Unsupported stress_input_mode. Use 'linear_plane_stress_per_force' or 'round_shaft_bending_torsion_linear_force'.")

    @staticmethod
    def _evaluate_state_for_force(normalized: dict[str, Any], force: float) -> dict[str, Any]:
        sigma_x = normalized["sigma_x"] * force
        sigma_y = normalized["sigma_y"] * force
        tau_xy = normalized["tau_xy"] * force
        state = StressState({"label": "evaluated_brittle_strength_state", "sigma_x": sigma_x, "sigma_y": sigma_y, "tau_xy": tau_xy})
        s1, s2, s3 = state.principal_stresses()
        sigma_a, sigma_b = state.principal_pair_in_plane() or (None, None)
        return {
            "plane_stress_inputs": {"sigma_x": sigma_x, "sigma_y": sigma_y, "tau_xy": tau_xy},
            "ordered_principal_stresses": {"sigma_1": s1, "sigma_2": s2, "sigma_3": s3},
            "derived": {"maximum_shear_stress": state.max_shear_stress(), "in_plane_principal_stresses": {"sigma_A": sigma_a, "sigma_B": sigma_b}},
        }


class Example56TransverseCrackFractureSolver:
    solve_path = "transverse_crack_fracture"

    def __init__(self, table_5_1: Table51FractureToughness | None = None, figure_library: FigureJsonLibrary | None = None) -> None:
        self.table_5_1 = table_5_1 or Table51FractureToughness()
        self.figure_library = figure_library or FigureJsonLibrary()

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") != self.solve_path:
            raise ValueError(f"Unsupported solve_path '{inputs.get('solve_path')}'. Expected '{self.solve_path}'.")
        material = self._build_material(inputs)
        geometry = self._build_geometry(inputs)
        applied = self._build_applied_loading(inputs, material["strength_unit"])
        beta_info = self._resolve_beta(inputs, geometry)
        K_I_applied = beta_info["beta"] * applied["nominal_stress"] * sqrt(pi * geometry["a_m"])
        n_fracture = inf if isclose(K_I_applied, 0.0, abs_tol=1e-12) else material["K_Ic"] / K_I_applied
        sigma_catastrophic = inf if isclose(beta_info["beta"] * sqrt(pi * geometry["a_m"]), 0.0, abs_tol=1e-12) else material["K_Ic"] / (beta_info["beta"] * sqrt(pi * geometry["a_m"]))
        ratio_to_yield = None if material.get("Syt") in (None, 0) else sigma_catastrophic / material["Syt"]
        yield_limited = material.get("Syt") is not None and sigma_catastrophic >= material["Syt"]
        summary_df = pd.DataFrame([{"beta": beta_info["beta"], f"K_I applied {material['K_Ic_unit']}": K_I_applied, "n_fracture": n_fracture, f"sigma_cat {material['strength_unit']}": sigma_catastrophic, f"Syt {material['strength_unit']}": material.get("Syt"), "sigma_cat_over_Syt": ratio_to_yield}])
        return {"problem": payload.get("problem", "static_failure"), "title": payload.get("title", "Mode-I fracture catastrophic-failure analysis"), "inputs": inputs, "material": material, "meta": {"solve_path": self.solve_path, "applicability": "Mode-I fracture assessments using K_I = beta*sigma*sqrt(pi*a) and n = K_Ic/K_I", "implemented_equations": ["Eq_5_37", "Eq_5_38"], "beta_source_type": beta_info["source_type"]}, "results": {"critical_section": {"geometry_mode": geometry["geometry_mode"], "a_m": geometry["a_m"], "geometry_ratios": geometry["geometry_ratios"], "beta_lookup": beta_info}, "strength_predictions": {"fracture_assessment": {"applied_nominal_stress": applied["nominal_stress"], "applied_stress_unit": material["strength_unit"], "K_I_applied": K_I_applied, "K_Ic": material["K_Ic"], "K_I_unit": material["K_Ic_unit"], "fracture_factor_of_safety_n": n_fracture, "catastrophic_failure_stress": sigma_catastrophic, "yield_strength": material.get("Syt"), "catastrophic_to_yield_ratio": ratio_to_yield, "catastrophic_exceeds_yield_strength": yield_limited}}, "summary_table": summary_df.to_dict(orient="records")}}

    def _build_material(self, inputs: dict[str, Any]) -> dict[str, Any]:
        strength_unit = str(inputs.get("strength_unit", "MPa"))
        K_unit = str(inputs.get("K_Ic_unit", "MPa*sqrt(m)"))
        material_name = inputs.get("material_name")
        source = inputs.get("material_source")
        K_Ic = inputs.get("K_Ic")
        Syt = inputs.get("Syt")
        if inputs.get("table_5_1_lookup"):
            lookup = inputs["table_5_1_lookup"]
            if not isinstance(lookup, dict):
                raise ValueError("'table_5_1_lookup' must be an object with material_family and material_grade.")
            row = self.table_5_1.lookup(lookup.get("material_family"), lookup.get("material_grade"))
            K_Ic = row["K_Ic_MPa_sqrt_m"] if K_Ic is None else K_Ic
            Syt = row["Syt_MPa"] if Syt is None else Syt
            material_name = material_name or f"{lookup.get('material_family')} {lookup.get('material_grade')}"
            source = source or "Table 5-1"
        if K_Ic is None:
            raise ValueError("Provide 'K_Ic' directly or via 'table_5_1_lookup'.")
        return {"name": material_name, "K_Ic": float(K_Ic), "K_Ic_unit": K_unit, "Syt": float(Syt) if Syt is not None else None, "strength_unit": strength_unit, "source": source}

    @staticmethod
    def _build_applied_loading(inputs: dict[str, Any], strength_unit: str) -> dict[str, Any]:
        if "nominal_stress" not in inputs:
            raise ValueError("Missing required input 'nominal_stress'.")
        return {"nominal_stress": float(inputs["nominal_stress"]), "stress_unit": strength_unit}

    @staticmethod
    def _to_meters(value: float, unit: str) -> float:
        u = str(unit).strip().lower()
        scales = {"m": 1.0, "mm": 1e-3, "cm": 1e-2, "in": 0.0254, "ft": 0.3048}
        if u not in scales:
            raise ValueError(f"Unsupported length_unit '{unit}'.")
        return float(value) * scales[u]

    @classmethod
    def _build_geometry(cls, inputs: dict[str, Any]) -> dict[str, Any]:
        length_unit = str(inputs.get("length_unit", "mm"))
        geometry_mode = str(inputs.get("geometry_mode", "figure_5_25_off_center_crack_longitudinal_tension"))
        if geometry_mode == "figure_5_25_off_center_crack_longitudinal_tension":
            if inputs.get("a") is None:
                if inputs.get("two_a") is None:
                    raise ValueError("Provide either 'a' or 'two_a' for the crack length.")
                a = 0.5 * float(inputs["two_a"])
            else:
                a = float(inputs["a"])
            if "d" not in inputs:
                raise ValueError("Provide 'd' for figure_5_25 geometry.")
            d = float(inputs["d"])
            b = float(inputs.get("b", d))
            return {"geometry_mode": geometry_mode, "a_m": cls._to_meters(a, length_unit), "length_unit": length_unit, "geometry_ratios": {"a_over_d": a / d, "d_over_b": d / b}, "raw_dimensions": {"a": a, "d": d, "b": b}}
        raise ValueError("Unsupported geometry_mode. Currently implemented: 'figure_5_25_off_center_crack_longitudinal_tension'.")

    def _resolve_beta(self, inputs: dict[str, Any], geometry: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("beta_override") is not None:
            return {"source_type": "override", "beta": float(inputs["beta_override"])}
        if geometry["geometry_mode"] == "figure_5_25_off_center_crack_longitudinal_tension":
            figure_id = str(inputs.get("beta_figure_id", "figure_5_25"))
            crack_tip = str(inputs.get("crack_tip", "A")).strip().upper()
            family = "tip_A" if crack_tip == "A" else "tip_B"
            d_over_b = float(inputs.get("d_over_b", geometry["geometry_ratios"]["d_over_b"]))
            x_ratio = float(inputs.get("a_over_d", geometry["geometry_ratios"]["a_over_d"]))
            info = self.figure_library.interpolate_family_parameter(figure_id=figure_id, x=x_ratio, parameter_value=d_over_b, family=family, prefix="d_over_b_")
            return {"source_type": "figure_json", "figure_id": figure_id, "family": family, "crack_tip": crack_tip, "x_ratio_name": "a_over_d", "x_ratio": x_ratio, "parameter_name": "d_over_b", **info}
        raise ValueError(f"Unsupported geometry mode for beta lookup: {geometry['geometry_mode']}")


class Example57EdgeCrackAlloySelectionSolver:
    solve_path = "edge_crack_alloy_selection"

    def __init__(self, table_5_1: Table51FractureToughness | None = None, figure_library: FigureJsonLibrary | None = None) -> None:
        self.table_5_1 = table_5_1 or Table51FractureToughness()
        self.figure_library = figure_library or FigureJsonLibrary()

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        inputs = payload.get("inputs", payload)
        if inputs.get("solve_path") != self.solve_path:
            raise ValueError(f"Unsupported solve_path '{inputs.get('solve_path')}'. Expected '{self.solve_path}'.")

        model = self._build_model(inputs)
        candidates = self._build_candidates(inputs)
        beta_info = self._resolve_beta(model=model, inputs=inputs)
        beta = beta_info["beta"]

        evaluated: list[dict[str, Any]] = []
        for idx, candidate in enumerate(candidates, start=1):
            syt = float(candidate["Syt_MPa"])
            kic = float(candidate["K_Ic_MPa_sqrt_m"])
            sigma_allow_yield = syt / model["required_safety_factor"]
            t_yield_m = model["force_N"] / (model["plate_width_m"] * sigma_allow_yield * 1.0e6)

            sigma_fracture_n1 = kic / (beta * sqrt(pi * model["a_m"]))
            sigma_allow_fracture = sigma_fracture_n1 / model["required_safety_factor"]
            t_fracture_m = model["force_N"] / (model["plate_width_m"] * sigma_allow_fracture * 1.0e6)

            governing_mode = "yield" if t_yield_m >= t_fracture_m else "fracture"
            t_required_m = max(t_yield_m, t_fracture_m)

            evaluated.append({
                "candidate_index": idx,
                "candidate_label": candidate.get("candidate_label", f"candidate_{idx}"),
                "material_family": candidate["material_family"],
                "material_grade": candidate["material_grade"],
                "K_Ic_MPa_sqrt_m": kic,
                "Syt_MPa": syt,
                "sigma_allow_yield_MPa": sigma_allow_yield,
                "required_thickness_yield_mm": t_yield_m * 1.0e3,
                "sigma_fracture_n1_MPa": sigma_fracture_n1,
                "sigma_allow_fracture_MPa": sigma_allow_fracture,
                "required_thickness_fracture_mm": t_fracture_m * 1.0e3,
                "governing_mode": governing_mode,
                "required_thickness_mm": t_required_m * 1.0e3,
            })

        selected = min(evaluated, key=lambda row: row["required_thickness_mm"])

        summary_df = pd.DataFrame([
            {
                "Candidate": row["candidate_label"],
                "K_Ic MPa*sqrt(m)": row["K_Ic_MPa_sqrt_m"],
                "Syt MPa": row["Syt_MPa"],
                "t_yield mm": row["required_thickness_yield_mm"],
                "t_fracture mm": row["required_thickness_fracture_mm"],
                "t_required mm": row["required_thickness_mm"],
                "Governing": row["governing_mode"],
                "Selected": row is selected,
            }
            for row in evaluated
        ])

        return {
            "problem": payload.get("problem", "static_failure"),
            "title": payload.get("title", "Edge-crack alloy selection"),
            "inputs": inputs,
            "meta": {
                "solve_path": self.solve_path,
                "applicability": "Plate edge-crack screening where yield and fracture thickness requirements are compared across candidate alloys",
                "implemented_equations": ["Eq_5_37", "Eq_5_38", "sigma_allow = strength/n", "t = P/(w*sigma_allow)"],
                "beta_source_type": beta_info["source_type"],
                "selection_rule": "Choose the candidate with minimum required thickness, assuming weight is proportional to thickness for the compared alloy family.",
            },
            "results": {
                "geometry": {
                    "plate_width_m": model["plate_width_m"],
                    "plate_length_m": model["plate_length_m"],
                    "edge_crack_a_mm": model["edge_crack_a_mm"],
                    "required_safety_factor": model["required_safety_factor"],
                    "h_over_b": model["h_over_b"],
                    "a_over_b": model["a_over_b"],
                    "beta_lookup": beta_info,
                },
                "candidates": evaluated,
                "selected_candidate": selected,
                "summary_table": summary_df.to_dict(orient="records"),
            },
        }

    @staticmethod
    def _build_model(inputs: dict[str, Any]) -> dict[str, Any]:
        required = ["force_N", "plate_width_m", "plate_length_m", "edge_crack_a_mm", "required_safety_factor"]
        missing = [key for key in required if key not in inputs]
        if missing:
            raise ValueError(f"Missing required inputs: {', '.join(missing)}")
        width_m = float(inputs["plate_width_m"])
        length_m = float(inputs["plate_length_m"])
        a_mm = float(inputs["edge_crack_a_mm"])
        a_m = a_mm * 1.0e-3
        h_m = length_m / 2.0
        b_m = width_m
        return {
            "force_N": float(inputs["force_N"]),
            "plate_width_m": width_m,
            "plate_length_m": length_m,
            "edge_crack_a_mm": a_mm,
            "a_m": a_m,
            "required_safety_factor": float(inputs["required_safety_factor"]),
            "h_over_b": h_m / b_m,
            "a_over_b": a_m / b_m,
        }

    def _build_candidates(self, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        if inputs.get("candidate_rows"):
            rows = []
            for idx, row in enumerate(inputs["candidate_rows"], start=1):
                rows.append({
                    "candidate_label": row.get("candidate_label", f"candidate_{idx}"),
                    "material_family": row["material_family"],
                    "material_grade": row["material_grade"],
                    "K_Ic_MPa_sqrt_m": float(row["K_Ic_MPa_sqrt_m"]),
                    "Syt_MPa": float(row["Syt_MPa"]),
                })
            return rows

        table_filter = inputs.get("table_5_1_filter")
        if not table_filter:
            raise ValueError("Provide either 'candidate_rows' or 'table_5_1_filter'.")
        rows = self.table_5_1.lookup_all(table_filter["material_family"], table_filter["material_grade"])
        labeled = []
        for idx, row in enumerate(rows, start=1):
            labeled.append({
                **row,
                "candidate_label": row.get("candidate_label", f"{table_filter['material_family']} {table_filter['material_grade']} option {idx}"),
            })
        return labeled

    def _resolve_beta(self, model: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("beta_override") is not None:
            return {"source_type": "override", "beta": float(inputs["beta_override"])}

        figure_id = str(inputs.get("beta_figure_id", "figure_5_26"))
        family = str(inputs.get("figure_5_26_family", "solid_no_bending_constraints"))
        h_over_b = model["h_over_b"]
        a_over_b = model["a_over_b"]
        if not isclose(h_over_b, 1.0, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(f"Current implementation expects h/b = 1.0 for figure_5_26 exact-curve lookup; got {h_over_b}.")
        curve_key = "h_over_b_1_0"
        info = self.figure_library.interpolate_named_curve(figure_id=figure_id, x=a_over_b, family=family, curve_key=curve_key)
        return {
            "source_type": "figure_json",
            "figure_id": figure_id,
            "family": family,
            "curve_key": info["curve_key"],
            "interpolation": info["interpolation"],
            "beta": info["beta"],
            "h_over_b": h_over_b,
            "a_over_b": a_over_b,
        }
