
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

try:
    from .utils import ValidationError, angle_deg_from_x, evaluate_expression, find_data_file, load_json, magnitude_2d
except ImportError:  # pragma: no cover
    from utils import ValidationError, angle_deg_from_x, evaluate_expression, find_data_file, load_json, magnitude_2d


@dataclass
class WeldPatternDefinition:
    weld_type: int
    description: str
    throat_area_formula: str
    x_bar_formula: str | None
    y_bar_formula: str | None
    j_u_formula: str
    centroid_note: str | None = None


class Table91Repository:
    def __init__(self) -> None:
        payload = load_json(find_data_file("table_9_1.json"))
        self.rows: Dict[int, WeldPatternDefinition] = {}
        for row in payload["rows"]:
            loc = row.get("location_of_G", {})
            self.rows[int(row["weld_type"])] = WeldPatternDefinition(
                weld_type=int(row["weld_type"]),
                description=row.get("description", ""),
                throat_area_formula=row["throat_area_formula"],
                x_bar_formula=loc.get("x_bar_formula"),
                y_bar_formula=loc.get("y_bar_formula"),
                j_u_formula=row["unit_second_polar_moment_formula"],
                centroid_note=loc.get("note"),
            )

    def get(self, weld_type: int) -> WeldPatternDefinition:
        if weld_type not in self.rows:
            raise ValidationError(f"Unsupported weld_type {weld_type}. Available weld types: {sorted(self.rows)}")
        return self.rows[weld_type]


class WeldGeometryEngine:
    def __init__(self, repository: Table91Repository | None = None) -> None:
        self.repository = repository or Table91Repository()

    def evaluate_pattern(self, weld_type: int, geometry: Mapping[str, float], weld_size_mm: float) -> Dict[str, Any]:
        pattern = self.repository.get(weld_type)
        variables = {k: float(v) for k, v in geometry.items()}
        variables["h"] = float(weld_size_mm)
        area_mm2 = evaluate_expression(pattern.throat_area_formula, variables)
        j_u_mm3 = evaluate_expression(pattern.j_u_formula, variables)
        if pattern.x_bar_formula is not None:
            x_bar_mm = evaluate_expression(pattern.x_bar_formula, variables)
        else:
            x_bar_mm = 0.0
        if pattern.y_bar_formula is not None:
            y_bar_mm = evaluate_expression(pattern.y_bar_formula, variables)
        else:
            y_bar_mm = 0.0
        j_mm4 = 0.707 * weld_size_mm * j_u_mm3
        points = self._canonical_points_mm(weld_type=weld_type, geometry=geometry)
        return {
            "pattern": pattern,
            "geometry": dict(geometry),
            "area_mm2": area_mm2,
            "x_bar_mm": x_bar_mm,
            "y_bar_mm": y_bar_mm,
            "j_u_mm3": j_u_mm3,
            "j_mm4": j_mm4,
            "points_mm": points,
            "coordinate_system_note": self._coordinate_system_note(weld_type),
        }

    def _coordinate_system_note(self, weld_type: int) -> str:
        if weld_type == 4:
            return (
                "For weld_type 4, point coordinates mirror Shigley Fig. 9-15 / 9-16. "
                "The local x-coordinate measures downward from the top weld, and the local y-coordinate measures "
                "to the right from the left weld. With this convention: C = top-left, D = top-right, "
                "A = bottom-right, and B = bottom-left."
            )
        return (
            "Point coordinates are reported in the solver's local 2D weld-group coordinate system for the selected weld type."
        )

    def _canonical_points_mm(self, weld_type: int, geometry: Mapping[str, float]) -> Dict[str, Tuple[float, float]]:
        g = {k: float(v) for k, v in geometry.items()}
        if weld_type == 1:
            d = g["d"]
            return {"A": (0.0, 0.0), "B": (0.0, d)}
        if weld_type == 2:
            b, d = g["b"], g["d"]
            return {"A": (0.0, 0.0), "B": (0.0, d), "C": (b, 0.0), "D": (b, d)}
        if weld_type == 3:
            b, d = g["b"], g["d"]
            return {"A": (0.0, 0.0), "B": (0.0, d), "C": (b, 0.0)}
        if weld_type == 4:
            b, d = g["b"], g["d"]
            return {
                "A": (b, d),
                "B": (b, 0.0),
                "C": (0.0, 0.0),
                "D": (0.0, d),
            }
        if weld_type == 5:
            b, d = g["b"], g["d"]
            return {"A": (0.0, 0.0), "B": (0.0, d), "C": (b, d), "D": (b, 0.0)}
        if weld_type == 6:
            r = g["r"]
            return {"E": (r, 0.0), "N": (0.0, r), "W": (-r, 0.0), "S": (0.0, -r)}
        raise ValidationError(f"Canonical points are not defined for weld_type {weld_type}")


class WeldGroupTorsionSolver:
    solve_path = "weld_group_torsion"

    def __init__(self, geometry_engine: WeldGeometryEngine | None = None) -> None:
        self.geometry_engine = geometry_engine or WeldGeometryEngine()

    def solve(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        payload = self._normalize_inputs(inputs)
        geometry_eval = self.geometry_engine.evaluate_pattern(
            weld_type=payload["weld_type"],
            geometry=payload["geometry_mm"],
            weld_size_mm=payload["weld_size_mm"],
        )

        V_N = payload["analyzed_group_force_N"]
        A_mm2 = geometry_eval["area_mm2"]
        x_bar = geometry_eval["x_bar_mm"]
        y_bar = geometry_eval["y_bar_mm"]
        J_mm4 = geometry_eval["j_mm4"]
        points = geometry_eval["points_mm"]

        centroid = (x_bar, y_bar)
        load_line = self._resolve_load_line(payload, centroid)
        e_mm = self._moment_arm_mm(payload, centroid, load_line)
        M_N_mm = V_N * e_mm
        primary_tau_MPa = V_N / A_mm2

        evaluated_points = []
        max_point = None
        for label, point in points.items():
            point_result = self._evaluate_point(
                label=label,
                point=point,
                centroid=centroid,
                J_mm4=J_mm4,
                M_N_mm=M_N_mm,
                primary_tau_MPa=primary_tau_MPa,
                primary_direction=payload["primary_shear_direction"],
                torsion_sign=payload["torsion_sign"],
                combination_model=payload["combination_model"],
            )
            evaluated_points.append(point_result)
            if max_point is None or point_result["resultant_shear_stress_MPa"] > max_point["resultant_shear_stress_MPa"]:
                max_point = point_result

        tol = 1e-9
        critical_labels = [
            p["label"] for p in evaluated_points if abs(p["resultant_shear_stress_MPa"] - max_point["resultant_shear_stress_MPa"]) <= tol
        ]

        return {
            "problem": self.solve_path,
            "title": payload.get("title") or "Weld-group torsion analysis",
            "inputs": payload["reported_inputs"],
            "lookups": {
                "table_9_1": {
                    "weld_type": payload["weld_type"],
                    "description": geometry_eval["pattern"].description,
                    "throat_area_formula": geometry_eval["pattern"].throat_area_formula,
                    "x_bar_formula": geometry_eval["pattern"].x_bar_formula,
                    "y_bar_formula": geometry_eval["pattern"].y_bar_formula,
                    "unit_second_polar_moment_formula": geometry_eval["pattern"].j_u_formula,
                }
            },
            "derived": {
                "throat_area_mm2": A_mm2,
                "primary_shear_stress_MPa": primary_tau_MPa,
                "centroid_mm": {"x": x_bar, "y": y_bar},
                "unit_second_polar_moment_mm3": geometry_eval["j_u_mm3"],
                "polar_moment_mm4": J_mm4,
                "coordinate_system_note": geometry_eval["coordinate_system_note"],
                "load_line_mm": {"x": load_line[0], "y": load_line[1]},
                "moment_arm_mm": e_mm,
                "moment_N_mm": M_N_mm,
                "moment_N_m": M_N_mm / 1000.0,
                "points_evaluated": evaluated_points,
                "critical_point": max_point,
                "critical_point_labels": critical_labels,
            },
            "summary": {
                "maximum_shear_stress_MPa": max_point["resultant_shear_stress_MPa"],
                "critical_point_label": max_point["label"],
                "critical_point_labels": critical_labels,
            },
        }

    def _normalize_inputs(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        solve_path = inputs.get("solve_path")
        if solve_path != self.solve_path:
            raise ValidationError(f"solve_path must be '{self.solve_path}', got: {solve_path!r}")

        weld_type = int(inputs["weld_type"])
        weld_size_mm = float(inputs["weld_size_mm"])
        if weld_size_mm <= 0:
            raise ValidationError("weld_size_mm must be positive")

        geometry_in = inputs.get("geometry") or {}
        geometry_mm = {k: float(v) for k, v in geometry_in.items()}
        self._validate_geometry(weld_type, geometry_mm)

        total_force_N = float(inputs.get("total_force_N", 0.0))
        group_share_count = int(inputs.get("group_share_count", 1))
        analyzed_group_force_N = inputs.get("analyzed_group_force_N")
        if analyzed_group_force_N is None:
            if total_force_N == 0.0:
                raise ValidationError("Provide either analyzed_group_force_N or total_force_N")
            if group_share_count <= 0:
                raise ValidationError("group_share_count must be positive")
            analyzed_group_force_N = total_force_N / group_share_count
        analyzed_group_force_N = float(analyzed_group_force_N)

        primary_direction = str(inputs.get("primary_shear_direction", "negative_x"))
        if primary_direction not in {"positive_x", "negative_x", "positive_y", "negative_y"}:
            raise ValidationError("primary_shear_direction must be one of positive_x, negative_x, positive_y, negative_y")

        torsion_sign = str(inputs.get("torsion_sign", "ccw"))
        if torsion_sign not in {"ccw", "cw"}:
            raise ValidationError("torsion_sign must be 'ccw' or 'cw'")

        combination_model = str(inputs.get("combination_model", "shigley_radial"))
        if combination_model not in {"shigley_radial", "tangential"}:
            raise ValidationError("combination_model must be 'shigley_radial' or 'tangential'")

        reported_inputs = dict(inputs)
        return {
            "title": inputs.get("title"),
            "weld_type": weld_type,
            "weld_size_mm": weld_size_mm,
            "geometry_mm": geometry_mm,
            "total_force_N": total_force_N,
            "group_share_count": group_share_count,
            "analyzed_group_force_N": analyzed_group_force_N,
            "primary_shear_direction": primary_direction,
            "torsion_sign": torsion_sign,
            "load_line_x_mm": inputs.get("load_line_x_mm"),
            "load_line_y_mm": inputs.get("load_line_y_mm"),
            "moment_arm_mm": inputs.get("moment_arm_mm"),
            "combination_model": combination_model,
            "reported_inputs": reported_inputs,
        }

    def _validate_geometry(self, weld_type: int, geometry: Mapping[str, float]) -> None:
        required_by_type = {
            1: {"d"},
            2: {"b", "d"},
            3: {"b", "d"},
            4: {"b", "d"},
            5: {"b", "d"},
            6: {"r"},
        }
        required = required_by_type.get(weld_type)
        if required is None:
            raise ValidationError(f"Unsupported weld_type {weld_type}")
        missing = sorted(required - set(geometry))
        if missing:
            raise ValidationError(f"Missing geometry parameters for weld_type {weld_type}: {missing}")
        for k in required:
            if float(geometry[k]) <= 0:
                raise ValidationError(f"geometry parameter {k} must be positive")

    def _resolve_load_line(self, payload: Mapping[str, Any], centroid: Tuple[float, float]) -> Tuple[float, float]:
        x = payload.get("load_line_x_mm")
        y = payload.get("load_line_y_mm")
        if x is None and y is None and payload.get("moment_arm_mm") is None:
            raise ValidationError("Provide load_line_x_mm and/or load_line_y_mm, or provide moment_arm_mm directly")
        if x is None:
            x = centroid[0]
        if y is None:
            y = centroid[1]
        return (float(x), float(y))

    def _moment_arm_mm(self, payload: Mapping[str, Any], centroid: Tuple[float, float], load_line: Tuple[float, float]) -> float:
        explicit = payload.get("moment_arm_mm")
        if explicit is not None:
            e_mm = float(explicit)
        else:
            dx = load_line[0] - centroid[0]
            dy = load_line[1] - centroid[1]
            direction = payload["primary_shear_direction"]
            if direction in {"positive_x", "negative_x"}:
                e_mm = abs(dy)
            else:
                e_mm = abs(dx)
        if e_mm <= 0:
            raise ValidationError("moment arm must be positive")
        return e_mm

    def _evaluate_point(
        self,
        label: str,
        point: Tuple[float, float],
        centroid: Tuple[float, float],
        J_mm4: float,
        M_N_mm: float,
        primary_tau_MPa: float,
        primary_direction: str,
        torsion_sign: str,
        combination_model: str,
    ) -> Dict[str, Any]:
        x_rel = point[0] - centroid[0]
        y_rel = point[1] - centroid[1]
        r_mm = magnitude_2d(x_rel, y_rel)
        tau_secondary_MPa = (M_N_mm * r_mm / J_mm4) if J_mm4 else 0.0

        if combination_model == "tangential":
            tau2_x, tau2_y = self._tangential_components(
                tau_secondary_MPa=tau_secondary_MPa,
                x_rel=x_rel,
                y_rel=y_rel,
                r_mm=r_mm,
                torsion_sign=torsion_sign,
            )
        else:
            tau2_x, tau2_y = self._shigley_radial_components(
                tau_secondary_MPa=tau_secondary_MPa,
                x_rel=x_rel,
                y_rel=y_rel,
                r_mm=r_mm,
                primary_direction=primary_direction,
            )
        tau1_x, tau1_y = self._primary_vector(primary_tau_MPa, primary_direction)
        result_x = tau1_x + tau2_x
        result_y = tau1_y + tau2_y
        angle = angle_deg_from_x(result_x, result_y)
        radial_angle = angle_deg_from_x(x_rel, y_rel)

        return {
            "label": label,
            "point_mm": {"x": point[0], "y": point[1]},
            "relative_to_centroid_mm": {"x": x_rel, "y": y_rel},
            "radius_from_centroid_mm": r_mm,
            "radial_angle_deg_from_x": radial_angle,
            "primary_shear_vector_MPa": {"x": tau1_x, "y": tau1_y},
            "secondary_shear_vector_MPa": {"x": tau2_x, "y": tau2_y},
            "secondary_shear_magnitude_MPa": tau_secondary_MPa,
            "resultant_shear_vector_MPa": {"x": result_x, "y": result_y},
            "resultant_shear_stress_MPa": magnitude_2d(result_x, result_y),
            "resultant_angle_deg_from_x": angle,
        }

    def _primary_vector(self, magnitude_MPa: float, direction: str) -> Tuple[float, float]:
        mapping = {
            "positive_x": (magnitude_MPa, 0.0),
            "negative_x": (-magnitude_MPa, 0.0),
            "positive_y": (0.0, magnitude_MPa),
            "negative_y": (0.0, -magnitude_MPa),
        }
        return mapping[direction]

    def _shigley_radial_components(
        self,
        tau_secondary_MPa: float,
        x_rel: float,
        y_rel: float,
        r_mm: float,
        primary_direction: str,
    ) -> Tuple[float, float]:
        if r_mm == 0:
            return (0.0, 0.0)
        if primary_direction in {"positive_x", "negative_x"}:
            tau2_x = tau_secondary_MPa * (x_rel / r_mm)
            tau2_y = tau_secondary_MPa * (abs(y_rel) / r_mm)
            return tau2_x, tau2_y
        tau2_x = tau_secondary_MPa * (abs(x_rel) / r_mm)
        tau2_y = tau_secondary_MPa * (y_rel / r_mm)
        return tau2_x, tau2_y

    def _tangential_components(
        self,
        tau_secondary_MPa: float,
        x_rel: float,
        y_rel: float,
        r_mm: float,
        torsion_sign: str,
    ) -> Tuple[float, float]:
        if r_mm == 0:
            return (0.0, 0.0)
        tx, ty = self._tangential_unit_vector(x_rel, y_rel, torsion_sign)
        return tau_secondary_MPa * tx, tau_secondary_MPa * ty

    def _tangential_unit_vector(self, x_rel: float, y_rel: float, torsion_sign: str) -> Tuple[float, float]:
        r = magnitude_2d(x_rel, y_rel)
        if r == 0:
            return (0.0, 0.0)
        if torsion_sign == "ccw":
            return (-y_rel / r, x_rel / r)
        return (y_rel / r, -x_rel / r)
