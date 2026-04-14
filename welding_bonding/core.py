from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

try:
    from .utils import (
        ValidationError,
        angle_deg_from_x,
        evaluate_expression,
        find_data_file,
        load_csv_rows,
        load_json,
        magnitude_2d,
        parse_decimal_or_fraction,
    )
except ImportError:  # pragma: no cover
    from utils import (
        ValidationError,
        angle_deg_from_x,
        evaluate_expression,
        find_data_file,
        load_csv_rows,
        load_json,
        magnitude_2d,
        parse_decimal_or_fraction,
    )


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
        payload = load_json(find_data_file('table_9_1.json'))
        self.rows: Dict[int, WeldPatternDefinition] = {}
        for row in payload['rows']:
            loc = row.get('location_of_G', {})
            self.rows[int(row['weld_type'])] = WeldPatternDefinition(
                weld_type=int(row['weld_type']),
                description=row.get('description', ''),
                throat_area_formula=row['throat_area_formula'],
                x_bar_formula=loc.get('x_bar_formula'),
                y_bar_formula=loc.get('y_bar_formula'),
                j_u_formula=row['unit_second_polar_moment_formula'],
                centroid_note=loc.get('note'),
            )

    def get(self, weld_type: int) -> WeldPatternDefinition:
        if weld_type not in self.rows:
            raise ValidationError(f'Unsupported weld_type {weld_type}. Available weld types: {sorted(self.rows)}')
        return self.rows[weld_type]


@dataclass
class BendingWeldPatternDefinition:
    weld_type: int
    description: str
    throat_area_formula: str
    x_bar_formula: str | None
    y_bar_formula: str | None
    i_u_formula: str
    centroid_note: str | None = None


class Table92Repository:
    def __init__(self) -> None:
        payload = load_json(find_data_file('table_9_2.json'))
        self.rows: Dict[int, BendingWeldPatternDefinition] = {}
        for row in payload['rows']:
            loc = row.get('location_of_G', {})
            self.rows[int(row['weld_type'])] = BendingWeldPatternDefinition(
                weld_type=int(row['weld_type']),
                description=row.get('description', ''),
                throat_area_formula=row['throat_area_formula'],
                x_bar_formula=loc.get('x_bar_formula'),
                y_bar_formula=loc.get('y_bar_formula'),
                i_u_formula=row['unit_second_moment_formula'],
                centroid_note=loc.get('note'),
            )

    def get(self, weld_type: int) -> BendingWeldPatternDefinition:
        if weld_type not in self.rows:
            raise ValidationError(f'Unsupported weld_type {weld_type}. Available weld types: {sorted(self.rows)}')
        return self.rows[weld_type]


class WeldPropertiesRepository:
    def __init__(self) -> None:
        self.rows = load_csv_rows(find_data_file('table_9_3.csv'))

    def get_by_electrode(self, electrode: str) -> Dict[str, Any]:
        key = electrode.strip().upper()
        for row in self.rows:
            if row['aws_electrode_number'].strip().upper() == key:
                return {
                    'aws_electrode_number': key,
                    'tensile_strength_kpsi': float(row['tensile_strength_kpsi']),
                    'yield_strength_kpsi': float(row['yield_strength_kpsi']),
                    'tensile_strength_MPa': float(row['tensile_strength_MPa']),
                    'yield_strength_MPa': float(row['yield_strength_MPa']),
                }
        raise ValidationError(f'Electrode {electrode!r} not found in table_9_3.csv')


class AISCAllowablesRepository:
    def __init__(self) -> None:
        self.rows = load_csv_rows(find_data_file('table_9_4.csv'))

    def weld_allowable_shear_kpsi(self, weld_ultimate_strength_kpsi: float) -> float:
        return 0.30 * float(weld_ultimate_strength_kpsi)

    def base_allowable_shear_kpsi(self, base_yield_strength_kpsi: float) -> float:
        return 0.40 * float(base_yield_strength_kpsi)

    def base_allowable_tension_kpsi(self, base_yield_strength_kpsi: float) -> float:
        return 0.60 * float(base_yield_strength_kpsi)


class Table96Repository:
    def __init__(self) -> None:
        payload = load_json(find_data_file('table_9_6.json'))
        self.payload = payload
        self.schedule_a = payload['schedule_a']
        self.schedule_b = payload['schedule_b']

    def allowable_unit_force_kip_per_in(self, strength_level_exx_ksi: int, weld_size_in: float) -> float:
        coeffs = self.schedule_a['allowable_unit_force_coefficients_kip_per_linear_in_per_in']
        key = str(int(strength_level_exx_ksi))
        if key not in coeffs:
            raise ValidationError(f'No Schedule A coefficient for EXX={strength_level_exx_ksi}')
        return float(coeffs[key]) * float(weld_size_in)

    def allowable_shear_stress_kpsi(self, strength_level_exx_ksi: int) -> float:
        stresses = self.schedule_a['allowable_shear_stress_on_throat_ksi']
        key = str(int(strength_level_exx_ksi))
        if key not in stresses:
            raise ValidationError(f'No Schedule A throat stress for EXX={strength_level_exx_ksi}')
        return float(stresses[key])


class SteelMaterialRepository:
    def __init__(self) -> None:
        self.rows = load_csv_rows(find_data_file('table_a_20.csv'))

    def get(self, uns_no: str | None = None, sae_aisi_no: str | None = None, processing: str | None = None) -> Dict[str, Any]:
        processing_key = processing.strip().upper() if processing else None
        for row in self.rows:
            if uns_no and row['uns_no'].strip().upper() != uns_no.strip().upper():
                continue
            if sae_aisi_no and row['sae_aisi_no'].strip().upper() != str(sae_aisi_no).strip().upper():
                continue
            if processing_key and row['processing'].strip().upper() != processing_key:
                continue
            return {
                'uns_no': row['uns_no'],
                'sae_aisi_no': row['sae_aisi_no'],
                'processing': row['processing'],
                'tensile_strength_kpsi': float(row['tensile_strength_kpsi']),
                'yield_strength_kpsi': float(row['yield_strength_kpsi']),
                'tensile_strength_MPa': float(row['tensile_strength_MPa']),
                'yield_strength_MPa': float(row['yield_strength_MPa']),
            }
        raise ValidationError('Requested material not found in table_a_20.csv')


class WeldGeometryEngine:
    def __init__(self, repository: Table91Repository | None = None) -> None:
        self.repository = repository or Table91Repository()

    def evaluate_pattern(self, weld_type: int, geometry: Mapping[str, float], weld_size_mm: float) -> Dict[str, Any]:
        pattern = self.repository.get(weld_type)
        variables = {k: float(v) for k, v in geometry.items()}
        variables['h'] = float(weld_size_mm)
        area_mm2 = evaluate_expression(pattern.throat_area_formula, variables)
        j_u_mm3 = evaluate_expression(pattern.j_u_formula, variables)
        x_bar_mm = evaluate_expression(pattern.x_bar_formula, variables) if pattern.x_bar_formula is not None else 0.0
        y_bar_mm = evaluate_expression(pattern.y_bar_formula, variables) if pattern.y_bar_formula is not None else 0.0
        j_mm4 = 0.707 * weld_size_mm * j_u_mm3
        points = self._canonical_points_mm(weld_type=weld_type, geometry=geometry)
        return {
            'pattern': pattern,
            'geometry': dict(geometry),
            'area_mm2': area_mm2,
            'x_bar_mm': x_bar_mm,
            'y_bar_mm': y_bar_mm,
            'j_u_mm3': j_u_mm3,
            'j_mm4': j_mm4,
            'points_mm': points,
            'coordinate_system_note': self._coordinate_system_note(weld_type),
        }

    def _coordinate_system_note(self, weld_type: int) -> str:
        if weld_type == 4:
            return ('For weld_type 4, point coordinates mirror Shigley Fig. 9-15 / 9-16. '
                    'The local x-coordinate measures downward from the top weld, and the local y-coordinate measures '
                    'to the right from the left weld. With this convention: C = top-left, D = top-right, '
                    'A = bottom-right, and B = bottom-left.')
        return "Point coordinates are reported in the solver's local 2D weld-group coordinate system for the selected weld type."

    def _canonical_points_mm(self, weld_type: int, geometry: Mapping[str, float]) -> Dict[str, Tuple[float, float]]:
        g = {k: float(v) for k, v in geometry.items()}
        if weld_type == 1:
            d = g['d']
            return {'A': (0.0, 0.0), 'B': (0.0, d)}
        if weld_type == 2:
            b, d = g['b'], g['d']
            return {'A': (0.0, 0.0), 'B': (0.0, d), 'C': (b, 0.0), 'D': (b, d)}
        if weld_type == 3:
            b, d = g['b'], g['d']
            return {'A': (0.0, 0.0), 'B': (0.0, d), 'C': (b, 0.0)}
        if weld_type == 4:
            b, d = g['b'], g['d']
            return {'A': (b, d), 'B': (b, 0.0), 'C': (0.0, 0.0), 'D': (0.0, d)}
        if weld_type == 5:
            b, d = g['b'], g['d']
            return {'A': (0.0, 0.0), 'B': (0.0, d), 'C': (b, d), 'D': (b, 0.0)}
        if weld_type == 6:
            r = g['r']
            return {'E': (r, 0.0), 'N': (0.0, r), 'W': (-r, 0.0), 'S': (0.0, -r)}
        raise ValidationError(f'Canonical points are not defined for weld_type {weld_type}')


class WeldBendingGeometryEngine:
    def __init__(self, repository: Table92Repository | None = None) -> None:
        self.repository = repository or Table92Repository()

    def evaluate_pattern(self, weld_type: int, geometry: Mapping[str, float], weld_size_in: float) -> Dict[str, Any]:
        pattern = self.repository.get(weld_type)
        variables = {k: float(v) for k, v in geometry.items()}
        variables['h'] = float(weld_size_in)
        area_in2 = evaluate_expression(pattern.throat_area_formula, variables)
        x_bar_in = evaluate_expression(pattern.x_bar_formula, variables) if pattern.x_bar_formula is not None else 0.0
        y_bar_in = evaluate_expression(pattern.y_bar_formula, variables) if pattern.y_bar_formula is not None else 0.0
        variables['x_bar'] = x_bar_in
        variables['y_bar'] = y_bar_in
        i_u_in3 = evaluate_expression(pattern.i_u_formula, variables)
        i_in4 = 0.707 * weld_size_in * i_u_in3
        return {
            'pattern': pattern,
            'area_in2': area_in2,
            'x_bar_in': x_bar_in,
            'y_bar_in': y_bar_in,
            'i_u_in3': i_u_in3,
            'i_in4': i_in4,
        }


class WeldGroupTorsionSolver:
    solve_path = 'weld_group_torsion'

    def __init__(self, geometry_engine: WeldGeometryEngine | None = None) -> None:
        self.geometry_engine = geometry_engine or WeldGeometryEngine()

    def solve(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        payload = self._normalize_inputs(inputs)
        geometry_eval = self.geometry_engine.evaluate_pattern(
            weld_type=payload['weld_type'],
            geometry=payload['geometry_mm'],
            weld_size_mm=payload['weld_size_mm'],
        )
        V_N = payload['analyzed_group_force_N']
        A_mm2 = geometry_eval['area_mm2']
        x_bar = geometry_eval['x_bar_mm']
        y_bar = geometry_eval['y_bar_mm']
        J_mm4 = geometry_eval['j_mm4']
        points = geometry_eval['points_mm']
        centroid = (x_bar, y_bar)
        load_line = self._resolve_load_line(payload, centroid)
        e_mm = self._moment_arm_mm(payload, centroid, load_line)
        M_N_mm = V_N * e_mm
        primary_tau_MPa = V_N / A_mm2
        evaluated_points = []
        max_point = None
        for label, point in points.items():
            point_result = self._evaluate_point(
                label=label, point=point, centroid=centroid, J_mm4=J_mm4, M_N_mm=M_N_mm,
                primary_tau_MPa=primary_tau_MPa, primary_direction=payload['primary_shear_direction'],
                torsion_sign=payload['torsion_sign'], combination_model=payload['combination_model'],
            )
            evaluated_points.append(point_result)
            if max_point is None or point_result['resultant_shear_stress_MPa'] > max_point['resultant_shear_stress_MPa']:
                max_point = point_result
        tol = 1e-9
        critical_labels = [p['label'] for p in evaluated_points if abs(p['resultant_shear_stress_MPa'] - max_point['resultant_shear_stress_MPa']) <= tol]
        return {
            'problem': self.solve_path,
            'title': payload.get('title') or 'Weld-group torsion analysis',
            'inputs': payload['reported_inputs'],
            'lookups': {
                'table_9_1': {
                    'weld_type': payload['weld_type'],
                    'description': geometry_eval['pattern'].description,
                    'throat_area_formula': geometry_eval['pattern'].throat_area_formula,
                    'x_bar_formula': geometry_eval['pattern'].x_bar_formula,
                    'y_bar_formula': geometry_eval['pattern'].y_bar_formula,
                    'unit_second_polar_moment_formula': geometry_eval['pattern'].j_u_formula,
                }
            },
            'derived': {
                'throat_area_mm2': A_mm2,
                'primary_shear_stress_MPa': primary_tau_MPa,
                'centroid_mm': {'x': x_bar, 'y': y_bar},
                'unit_second_polar_moment_mm3': geometry_eval['j_u_mm3'],
                'polar_moment_mm4': J_mm4,
                'coordinate_system_note': geometry_eval['coordinate_system_note'],
                'load_line_mm': {'x': load_line[0], 'y': load_line[1]},
                'moment_arm_mm': e_mm,
                'moment_N_mm': M_N_mm,
                'moment_N_m': M_N_mm / 1000.0,
                'points_evaluated': evaluated_points,
                'critical_point': max_point,
                'critical_point_labels': critical_labels,
            },
            'summary': {
                'maximum_shear_stress_MPa': max_point['resultant_shear_stress_MPa'],
                'critical_point_label': max_point['label'],
                'critical_point_labels': critical_labels,
            },
        }

    def _normalize_inputs(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        if inputs.get('solve_path') != self.solve_path:
            raise ValidationError(f"solve_path must be '{self.solve_path}'")
        weld_type = int(inputs['weld_type'])
        weld_size_mm = float(inputs['weld_size_mm'])
        geometry_mm = {k: float(v) for k, v in (inputs.get('geometry') or {}).items()}
        total_force_N = float(inputs.get('total_force_N', 0.0))
        group_share_count = int(inputs.get('group_share_count', 1))
        analyzed_group_force_N = inputs.get('analyzed_group_force_N')
        if analyzed_group_force_N is None:
            if total_force_N == 0.0:
                raise ValidationError('Provide either analyzed_group_force_N or total_force_N')
            analyzed_group_force_N = total_force_N / group_share_count
        return {
            'title': inputs.get('title'),
            'weld_type': weld_type,
            'weld_size_mm': weld_size_mm,
            'geometry_mm': geometry_mm,
            'total_force_N': total_force_N,
            'group_share_count': group_share_count,
            'analyzed_group_force_N': float(analyzed_group_force_N),
            'primary_shear_direction': str(inputs.get('primary_shear_direction', 'negative_x')),
            'torsion_sign': str(inputs.get('torsion_sign', 'ccw')),
            'load_line_x_mm': inputs.get('load_line_x_mm'),
            'load_line_y_mm': inputs.get('load_line_y_mm'),
            'moment_arm_mm': inputs.get('moment_arm_mm'),
            'combination_model': str(inputs.get('combination_model', 'shigley_radial')),
            'reported_inputs': dict(inputs),
        }

    def _resolve_load_line(self, payload: Mapping[str, Any], centroid: Tuple[float, float]) -> Tuple[float, float]:
        x = payload.get('load_line_x_mm')
        y = payload.get('load_line_y_mm')
        if x is None and y is None and payload.get('moment_arm_mm') is None:
            raise ValidationError('Provide load_line_x_mm and/or load_line_y_mm, or provide moment_arm_mm directly')
        if x is None:
            x = centroid[0]
        if y is None:
            y = centroid[1]
        return (float(x), float(y))

    def _moment_arm_mm(self, payload: Mapping[str, Any], centroid: Tuple[float, float], load_line: Tuple[float, float]) -> float:
        explicit = payload.get('moment_arm_mm')
        if explicit is not None:
            return float(explicit)
        dx = load_line[0] - centroid[0]
        dy = load_line[1] - centroid[1]
        direction = payload['primary_shear_direction']
        return abs(dy) if direction in {'positive_x', 'negative_x'} else abs(dx)

    def _evaluate_point(self, label: str, point: Tuple[float, float], centroid: Tuple[float, float], J_mm4: float, M_N_mm: float,
                        primary_tau_MPa: float, primary_direction: str, torsion_sign: str, combination_model: str) -> Dict[str, Any]:
        x_rel = point[0] - centroid[0]
        y_rel = point[1] - centroid[1]
        r_mm = magnitude_2d(x_rel, y_rel)
        tau_secondary_MPa = (M_N_mm * r_mm / J_mm4) if J_mm4 else 0.0
        if combination_model == 'tangential':
            tau2_x, tau2_y = self._tangential_components(tau_secondary_MPa, x_rel, y_rel, r_mm, torsion_sign)
        else:
            tau2_x, tau2_y = self._shigley_radial_components(tau_secondary_MPa, x_rel, y_rel, r_mm, primary_direction)
        tau1_x, tau1_y = self._primary_vector(primary_tau_MPa, primary_direction)
        result_x = tau1_x + tau2_x
        result_y = tau1_y + tau2_y
        return {
            'label': label,
            'point_mm': {'x': point[0], 'y': point[1]},
            'relative_to_centroid_mm': {'x': x_rel, 'y': y_rel},
            'radius_from_centroid_mm': r_mm,
            'radial_angle_deg_from_x': angle_deg_from_x(x_rel, y_rel),
            'primary_shear_vector_MPa': {'x': tau1_x, 'y': tau1_y},
            'secondary_shear_vector_MPa': {'x': tau2_x, 'y': tau2_y},
            'secondary_shear_magnitude_MPa': tau_secondary_MPa,
            'resultant_shear_vector_MPa': {'x': result_x, 'y': result_y},
            'resultant_shear_stress_MPa': magnitude_2d(result_x, result_y),
            'resultant_angle_deg_from_x': angle_deg_from_x(result_x, result_y),
        }

    def _primary_vector(self, magnitude_MPa: float, direction: str) -> Tuple[float, float]:
        return {
            'positive_x': (magnitude_MPa, 0.0),
            'negative_x': (-magnitude_MPa, 0.0),
            'positive_y': (0.0, magnitude_MPa),
            'negative_y': (0.0, -magnitude_MPa),
        }[direction]

    def _shigley_radial_components(self, tau_secondary_MPa: float, x_rel: float, y_rel: float, r_mm: float, primary_direction: str) -> Tuple[float, float]:
        if r_mm == 0:
            return (0.0, 0.0)
        if primary_direction in {'positive_x', 'negative_x'}:
            return tau_secondary_MPa * (x_rel / r_mm), tau_secondary_MPa * (abs(y_rel) / r_mm)
        return tau_secondary_MPa * (abs(x_rel) / r_mm), tau_secondary_MPa * (y_rel / r_mm)

    def _tangential_components(self, tau_secondary_MPa: float, x_rel: float, y_rel: float, r_mm: float, torsion_sign: str) -> Tuple[float, float]:
        if r_mm == 0:
            return (0.0, 0.0)
        if torsion_sign == 'ccw':
            return tau_secondary_MPa * (-y_rel / r_mm), tau_secondary_MPa * (x_rel / r_mm)
        return tau_secondary_MPa * (y_rel / r_mm), tau_secondary_MPa * (-x_rel / r_mm)


class ParallelWeldStaticLoadingSolver:
    solve_path = 'parallel_weld_static_loading'

    def __init__(self) -> None:
        self.schedule = Table96Repository()
        self.allowables = AISCAllowablesRepository()
        self.materials = SteelMaterialRepository()

    def solve(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        if inputs.get('solve_path') != self.solve_path:
            raise ValidationError(f"solve_path must be '{self.solve_path}'")
        geom = inputs['geometry']
        F_kip = float(inputs['load_kip'])
        h_in = float(inputs['weld_size_in'])
        l_each_in = float(geom['weld_length_each_in'])
        sides = int(geom.get('number_of_welds', 2))
        total_length_in = sides * l_each_in
        electrode_strength = int(inputs['electrode_strength_level_exx'])
        force_per_in = self.schedule.allowable_unit_force_kip_per_in(electrode_strength, h_in)
        weld_capacity = force_per_in * total_length_in
        weld_ok = weld_capacity >= F_kip

        material = self.materials.get(uns_no=inputs.get('attachment_material_uns_no'), processing=inputs.get('attachment_material_processing'))
        Sy = material['yield_strength_kpsi']
        tau_allow_base = self.allowables.base_allowable_shear_kpsi(Sy)
        sigma_allow_base = self.allowables.base_allowable_tension_kpsi(Sy)
        t_in = float(geom['attachment_thickness_in'])
        width_in = float(geom['attachment_width_in'])

        shear_area_adjacent_to_weld_in2 = 2.0 * h_in * l_each_in
        tension_area_shank_in2 = t_in * width_in
        tau_actual = F_kip / shear_area_adjacent_to_weld_in2
        sigma_actual = F_kip / tension_area_shank_in2

        shear_ok = tau_actual <= tau_allow_base + 1e-12
        tension_ok = sigma_actual <= sigma_allow_base + 1e-12
        attachment_ok = shear_ok and tension_ok
        at_allowable_limit = abs(tau_actual - tau_allow_base) <= 1e-12 or abs(sigma_actual - sigma_allow_base) <= 1e-12

        return {
            'problem': self.solve_path,
            'title': inputs.get('title', 'Parallel weld under static loading'),
            'inputs': dict(inputs),
            'lookups': {
                'table_9_6': {
                    'electrode_strength_level_exx': electrode_strength,
                    'allowable_unit_force_kip_per_linear_in': force_per_in,
                },
                'table_a_20': material,
                'table_9_4': {
                    'weld_allowable_shear_expression': '0.30*S_ut',
                    'base_metal_shear_limit_expression': '0.40*S_y',
                    'base_metal_tension_limit_expression': '0.60*S_y',
                    'base_metal_shear_limit_note': 'This is the Table 9-4 footnote limit on base metal, not the weld-metal shear row.',
                },
            },
            'derived': {
                'weld_metal': {
                    'total_effective_weld_length_in': total_length_in,
                    'allowable_force_per_unit_length_kip_per_in': force_per_in,
                    'allowable_total_force_kip': weld_capacity,
                    'applied_force_kip': F_kip,
                    'margin_ratio_allowable_over_applied': weld_capacity / F_kip,
                    'is_satisfactory': weld_ok,
                },
                'attachment': {
                    'yield_strength_kpsi': Sy,
                    'shear_area_adjacent_to_weld_in2': shear_area_adjacent_to_weld_in2,
                    'allowable_shear_stress_kpsi': tau_allow_base,
                    'actual_shear_stress_adjacent_to_weld_kpsi': tau_actual,
                    'tension_area_shank_in2': tension_area_shank_in2,
                    'allowable_tension_stress_kpsi': sigma_allow_base,
                    'actual_tension_stress_shank_kpsi': sigma_actual,
                    'shear_check_is_satisfactory': shear_ok,
                    'tension_check_is_satisfactory': tension_ok,
                    'is_satisfactory': attachment_ok,
                    'is_exactly_at_allowable_limit': at_allowable_limit,
                },
            },
            'summary': {
                'weld_metal_is_satisfactory': weld_ok,
                'attachment_is_satisfactory': attachment_ok,
                'attachment_is_borderline_at_allowable_limit': at_allowable_limit,
            },
        }


class DesignWeldStaticLoadingSolver:
    solve_path = 'design_weld_static_loading'

    def __init__(self) -> None:
        self.allowables = AISCAllowablesRepository()
        self.materials = SteelMaterialRepository()
        self.weld_props = WeldPropertiesRepository()

    def solve(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        if inputs.get('solve_path') != self.solve_path:
            raise ValidationError(f"solve_path must be '{self.solve_path}'")
        F = float(inputs['load_kip'])
        h = float(inputs['weld_size_in'])
        top_y = float(inputs['top_weld_y_in'])
        bot_y = float(inputs['bottom_weld_y_in'])
        section_rects = inputs['attachment_section_rectangles']
        y_bar = self._composite_centroid_y(section_rects)
        F1 = F * (y_bar - bot_y) / (top_y - bot_y)
        F2 = F - F1
        ratio = F2 / F1

        electrode = self.weld_props.get_by_electrode(inputs['electrode_class'])
        weld_tau_allow = self.allowables.weld_allowable_shear_kpsi(electrode['tensile_strength_kpsi'])
        l1_weld = F / (0.707 * h * weld_tau_allow * (1.0 + ratio))
        l2_weld = ratio * l1_weld

        material = inputs.get('attachment_material_custom') or self.materials.get(
            sae_aisi_no=inputs.get('attachment_material_sae_aisi_no'),
            processing=inputs.get('attachment_material_processing'),
        )
        base_tau_allow = self.allowables.base_allowable_shear_kpsi(float(material['yield_strength_kpsi']))
        l1_base = F / (h * base_tau_allow * (1.0 + ratio))
        l2_base = ratio * l1_base
        sigma_allow = self.allowables.base_allowable_tension_kpsi(float(material['yield_strength_kpsi']))
        attachment_area = sum(float(r['thickness_in']) * float(r['height_in']) for r in section_rects)
        sigma_actual = F / attachment_area
        shank_ok = sigma_actual <= sigma_allow + 1e-12

        design_mode = str(inputs.get('design_mode', 'textbook_weld_only'))
        rounding_step = parse_decimal_or_fraction(inputs.get('round_to_nearest_fraction_in'))
        if design_mode == 'extended_governing_case':
            controlling = 'base_metal' if (l1_base + l2_base) >= (l1_weld + l2_weld) else 'weld_metal'
            l1_req = l1_base if controlling == 'base_metal' else l1_weld
            l2_req = l2_base if controlling == 'base_metal' else l2_weld
        else:
            controlling = 'weld_metal'
            l1_req = l1_weld
            l2_req = l2_weld

        if rounding_step:
            l1_selected = self._round_up_to_step(l1_req, rounding_step)
            l2_selected = self._round_up_to_step(l2_req, rounding_step)
        else:
            l1_selected = l1_req
            l2_selected = l2_req

        return {
            'problem': self.solve_path,
            'title': inputs.get('title', 'Design of weld under static loading'),
            'inputs': dict(inputs),
            'lookups': {
                'table_9_4': {
                    'weld_allowable_shear_expression': '0.30*S_ut',
                    'base_allowable_shear_expression': '0.40*S_y',
                    'base_allowable_tension_expression': '0.60*S_y',
                },
                'table_a_20': material,
            },
            'derived': {
                'attachment_centroid_y_in': y_bar,
                'force_split_kip': {'F1_top': F1, 'F2_bottom': F2},
                'weld_length_ratio_l2_over_l1': ratio,
                'weld_metal_design': {
                    'allowable_shear_stress_kpsi': weld_tau_allow,
                    'required_l1_in': l1_weld,
                    'required_l2_in': l2_weld,
                },
                'base_metal_check': {
                    'allowable_shear_stress_kpsi': base_tau_allow,
                    'required_l1_in_if_base_shear_governed': l1_base,
                    'required_l2_in_if_base_shear_governed': l2_base,
                    'allowable_tension_stress_kpsi': sigma_allow,
                    'actual_shank_tension_stress_kpsi': sigma_actual,
                    'shank_is_satisfactory': shank_ok,
                    'note': 'Reported as an additional adequacy check. It does not override the textbook weld-sizing result unless design_mode is set to extended_governing_case.',
                },
                'design_mode_used': design_mode,
                'controlling_case': controlling,
                'selected_lengths_in': {'l1': l1_selected, 'l2': l2_selected},
            },
            'summary': {
                'controlling_case': controlling,
                'selected_l1_in': l1_selected,
                'selected_l2_in': l2_selected,
            },
        }

    def _composite_centroid_y(self, rects: list[dict[str, Any]]) -> float:
        num = 0.0
        den = 0.0
        for r in rects:
            area = float(r['thickness_in']) * float(r['height_in'])
            y = float(r['centroid_y_in'])
            num += y * area
            den += area
        if den <= 0:
            raise ValidationError('Composite section area must be positive')
        return num / den

    def _round_up_to_step(self, value: float, step: float) -> float:
        import math
        return math.ceil(value / step - 1e-12) * step


class WeldedJointBendingStaticLoadingSolver:
    solve_path = 'welded_joint_bending_static_loading'

    def __init__(self) -> None:
        self.weld_props = WeldPropertiesRepository()
        self.bending_patterns = WeldBendingGeometryEngine()
        self.schedule = Table96Repository()
        self.materials = SteelMaterialRepository()

    def solve(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        if inputs.get('solve_path') != self.solve_path:
            raise ValidationError(f"solve_path must be '{self.solve_path}'")
        F_lbf = float(inputs['load_lbf'])
        F_kip = F_lbf / 1000.0
        e = float(inputs['moment_arm_in'])
        M_kip_in = F_kip * e
        weld_size_in = float(inputs['weld_size_in'])
        weld_type = int(inputs['weld_type'])
        geometry = {k: float(v) for k, v in inputs['geometry'].items()}
        c = float(inputs['c_in'])
        pattern = self.bending_patterns.evaluate_pattern(weld_type, geometry, weld_size_in)
        A = pattern['area_in2']
        I = pattern['i_in4']
        tau_primary = F_kip / A
        tau_secondary = M_kip_in * c / I
        tau_resultant = (tau_primary**2 + tau_secondary**2) ** 0.5

        electrode = self.weld_props.get_by_electrode(inputs['electrode_class'])
        Sy_weld = electrode['yield_strength_kpsi']
        n_weld_conventional = 0.577 * Sy_weld / tau_resultant

        material = self.materials.get(
            sae_aisi_no=inputs.get('attachment_material_sae_aisi_no'),
            processing=inputs.get('attachment_material_processing'),
        )
        b = float(inputs['attachment_section_b_in'])
        d = float(inputs['attachment_section_d_in'])
        section_modulus = b * d**2 / 6.0
        sigma_attachment = M_kip_in / section_modulus
        n_attachment = material['yield_strength_kpsi'] / sigma_attachment

        exx = int(inputs['electrode_strength_level_exx'])
        tau_allow_code = self.schedule.allowable_shear_stress_kpsi(exx)
        n_weld_code = tau_allow_code / tau_resultant
        design_factor = float(inputs.get('design_factor', 1.0))
        return {
            'problem': self.solve_path,
            'title': inputs.get('title', 'Welded joint in bending under static loading'),
            'inputs': dict(inputs),
            'lookups': {
                'table_9_3': electrode,
                'table_9_2': {
                    'weld_type': weld_type,
                    'description': pattern['pattern'].description,
                    'throat_area_formula': pattern['pattern'].throat_area_formula,
                    'unit_second_moment_formula': pattern['pattern'].i_u_formula,
                },
                'table_a_20': material,
                'table_9_6': {'allowable_shear_stress_kpsi': tau_allow_code},
            },
            'derived': {
                'weld_metal_conventional': {
                    'throat_area_in2': A,
                    'unit_second_moment_in3': pattern['i_u_in3'],
                    'second_moment_in4': I,
                    'primary_shear_kpsi': tau_primary,
                    'secondary_shear_kpsi': tau_secondary,
                    'resultant_shear_kpsi': tau_resultant,
                    'factor_of_safety': n_weld_conventional,
                    'is_satisfactory_for_design_factor': n_weld_conventional >= design_factor,
                },
                'attachment_conventional': {
                    'yield_strength_kpsi': material['yield_strength_kpsi'],
                    'section_modulus_in3': section_modulus,
                    'bending_stress_kpsi': sigma_attachment,
                    'factor_of_safety': n_attachment,
                    'is_satisfactory_for_design_factor': n_attachment >= design_factor,
                },
                'weld_metal_code_method': {
                    'allowable_shear_stress_kpsi': tau_allow_code,
                    'actual_resultant_shear_kpsi': tau_resultant,
                    'factor_of_safety': n_weld_code,
                    'is_satisfactory_for_design_factor': n_weld_code >= design_factor,
                    'is_satisfactory_at_code_allowable': tau_resultant <= tau_allow_code + 1e-12,
                },
            },
            'summary': {
                'weld_metal_conventional_factor_of_safety': n_weld_conventional,
                'attachment_factor_of_safety': n_attachment,
                'weld_metal_code_factor_of_safety': n_weld_code,
            },
        }



class MarinSurfaceFinishRepository:
    _ALIASES = {
        'ground': 'ground',
        'machined': 'machined or cold-drawn',
        'machined or cold drawn': 'machined or cold-drawn',
        'machined or cold-drawn': 'machined or cold-drawn',
        'cold drawn': 'machined or cold-drawn',
        'cold-drawn': 'machined or cold-drawn',
        'hot rolled': 'hot-rolled',
        'hot-rolled': 'hot-rolled',
        'hr': 'hot-rolled',
        'as forged': 'as-forged',
        'as-forged': 'as-forged',
        'forged': 'as-forged',
    }

    def __init__(self) -> None:
        self.rows = load_csv_rows(find_data_file('table_6_2.csv'))

    def _canonical_key(self, surface_finish: str) -> str:
        key = surface_finish.strip().lower().replace('_', ' ').replace('  ', ' ')
        return self._ALIASES.get(key, key)

    def get(self, surface_finish: str) -> Dict[str, Any]:
        key = self._canonical_key(surface_finish)
        for row in self.rows:
            row_key = self._canonical_key(row['surface_finish'])
            if row_key == key:
                return {
                    'surface_finish': row['surface_finish'],
                    'surface_finish_input': surface_finish,
                    'canonical_surface_finish': key,
                    'a_factor_kpsi': float(row['a_factor_kpsi']),
                    'a_factor_MPa': float(row['a_factor_MPa']),
                    'b_exponent': float(row['b_exponent']),
                }
        raise ValidationError(f"Surface finish {surface_finish!r} not found in table_6_2.csv")


class FatigueStressConcentrationRepository:
    def __init__(self) -> None:
        self.rows = load_csv_rows(find_data_file('table_9_5.csv'))

    def get(self, type_of_weld: str) -> Dict[str, Any]:
        key = type_of_weld.strip().lower()
        for row in self.rows:
            if row['type_of_weld'].strip().lower() == key:
                return {
                    'type_of_weld': row['type_of_weld'],
                    'K_fs': float(row['K_fs']),
                }
        raise ValidationError(f"Type of weld {type_of_weld!r} not found in table_9_5.csv")


class FatigueCriteriaRepository:
    def __init__(self) -> None:
        self.payload = load_json(find_data_file('table_6_7.json'))
        self.fos_equation = self.payload['fatigue_factor_of_safety']['equation']

    def gerber_factor_of_safety(self, shear_ultimate_strength_kpsi: float, corrected_endurance_limit_kpsi: float,
                                alternating_shear_kpsi: float, mean_shear_kpsi: float) -> float:
        sigma_a = float(alternating_shear_kpsi)
        sigma_m = float(mean_shear_kpsi)
        if sigma_a < 0:
            raise ValidationError('Alternating stress must be nonnegative')
        if sigma_a == 0.0:
            return float('inf')
        if sigma_m <= 0:
            raise ValidationError('Gerber fatigue-factor equation requires positive mean stress')
        return evaluate_expression(
            self.fos_equation,
            {
                'Sut': float(shear_ultimate_strength_kpsi),
                'Se': float(corrected_endurance_limit_kpsi),
                'sigma_a': sigma_a,
                'sigma_m': sigma_m,
            },
        )


class MarinFactorEngine:
    _PROCESSING_TO_SURFACE = {
        'HR': 'hot-rolled',
        'HOT-ROLLED': 'hot-rolled',
        'CD': 'machined or cold-drawn',
        'COLD-DRAWN': 'machined or cold-drawn',
        'MACHINED': 'machined or cold-drawn',
        'GROUND': 'ground',
        'FORGED': 'as-forged',
        'AS-FORGED': 'as-forged',
    }

    def __init__(self) -> None:
        self.surface_repo = MarinSurfaceFinishRepository()

    def surface_factor_ka(self, surface_finish: str, tensile_strength_kpsi: float, material_processing: str | None = None) -> Dict[str, Any]:
        row = self.surface_repo.get(surface_finish)
        ka = row['a_factor_kpsi'] * (float(tensile_strength_kpsi) ** row['b_exponent'])
        inferred = None
        consistency = None
        note = None
        if material_processing:
            inferred = self._PROCESSING_TO_SURFACE.get(str(material_processing).strip().upper())
            if inferred is None:
                consistency = None
                note = 'Material processing was provided, but no default Marin surface-finish mapping is defined for it.'
            else:
                consistency = inferred == row['canonical_surface_finish']
                if consistency:
                    note = 'Selected Marin surface-finish row is consistent with the material processing label.'
                else:
                    note = ('Selected Marin surface-finish row differs from the material processing label. '
                            'This is allowed and the solver honors the explicit surface_finish input, '
                            'which is useful when matching a textbook example or a known weld-surface condition.')
        return {
            'surface_finish': row['surface_finish'],
            'surface_finish_input': row['surface_finish_input'],
            'canonical_surface_finish': row['canonical_surface_finish'],
            'a_factor_kpsi': row['a_factor_kpsi'],
            'b_exponent': row['b_exponent'],
            'ka': ka,
            'material_processing_input': material_processing,
            'processing_inferred_surface_finish': inferred,
            'processing_surface_finish_consistent': consistency,
            'selection_note': note,
        }

    def size_factor_kb(self, mode: str, **kwargs: Any) -> Dict[str, Any]:
        key = str(mode).strip().lower()
        if key == 'uniform_shear_on_throat':
            return {'mode': mode, 'kb': 1.0, 'note': 'For uniform shear stress on the throat, kb = 1.'}
        if key == 'override':
            kb = float(kwargs['kb_override'])
            return {'mode': mode, 'kb': kb, 'note': 'User override'}
        raise ValidationError(f'Unsupported size_factor_mode: {mode!r}')

    def load_factor_kc(self, mode: str) -> Dict[str, Any]:
        key = str(mode).strip().lower()
        mapping = {
            'bending': 1.0,
            'axial': 0.85,
            'torsion_shear': 0.59,
        }
        if key not in mapping:
            raise ValidationError(f'Unsupported loading_factor_mode: {mode!r}')
        return {'mode': mode, 'kc': mapping[key]}

    def prime_endurance_limit_kpsi(self, tensile_strength_kpsi: float) -> Dict[str, Any]:
        Sut = float(tensile_strength_kpsi)
        if Sut <= 200.0:
            Se_prime = 0.5 * Sut
            rule = "S'e = 0.5*Sut"
        else:
            Se_prime = 100.0
            rule = "S'e = 100 kpsi cap"
        return {'S_e_prime_kpsi': Se_prime, 'rule': rule}


class WeldFatigueFactorOfSafetySolver:
    solve_path = 'weld_fatigue_factor_of_safety'

    def __init__(self) -> None:
        self.materials = SteelMaterialRepository()
        self.weld_props = WeldPropertiesRepository()
        self.kfs_repo = FatigueStressConcentrationRepository()
        self.bending_patterns = WeldBendingGeometryEngine()
        self.marin = MarinFactorEngine()

    def solve(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        if inputs.get('solve_path') != self.solve_path:
            raise ValidationError(f"solve_path must be '{self.solve_path}'")

        material = self.materials.get(
            sae_aisi_no=inputs.get('attachment_material_sae_aisi_no'),
            processing=inputs.get('attachment_material_processing'),
        )
        electrode = self.weld_props.get_by_electrode(inputs['electrode_class'])
        kfs_row = self.kfs_repo.get(inputs['fatigue_stress_concentration_type'])
        geometry_eval = self.bending_patterns.evaluate_pattern(
            int(inputs['weld_type']),
            {k: float(v) for k, v in inputs['geometry'].items()},
            float(inputs['weld_size_in']),
        )

        ka_data = self.marin.surface_factor_ka(
            inputs['surface_finish'],
            material['tensile_strength_kpsi'],
            material_processing=material.get('processing'),
        )
        kb_data = self.marin.size_factor_kb(
            inputs.get('size_factor_mode', 'uniform_shear_on_throat'),
            kb_override=inputs.get('kb_override'),
        )
        kc_data = self.marin.load_factor_kc(inputs.get('loading_factor_mode', 'torsion_shear'))
        kd = float(inputs.get('temperature_factor_kd', 1.0))
        ke = float(inputs.get('reliability_factor_ke', 1.0))
        kf_misc = float(inputs.get('misc_factor_kf', 1.0))
        se_prime_data = self.marin.prime_endurance_limit_kpsi(material['tensile_strength_kpsi'])
        corrected_se = ka_data['ka'] * kb_data['kb'] * kc_data['kc'] * kd * ke * kf_misc * se_prime_data['S_e_prime_kpsi']

        A = geometry_eval['area_in2']
        if A <= 0.0:
            raise ValidationError('Computed weld throat area must be positive')
        Fa_lbf = float(inputs['force_amplitude_lbf'])
        Fm_lbf = float(inputs.get('force_mean_lbf', 0.0))
        Kfs = kfs_row['K_fs']
        tau_a_kpsi = Kfs * Fa_lbf / A / 1000.0
        tau_m_kpsi = Kfs * Fm_lbf / A / 1000.0
        stress_ratio_R = (-Fa_lbf + Fm_lbf) / (Fa_lbf + Fm_lbf) if abs(Fa_lbf + Fm_lbf) > 1e-12 else None

        if abs(tau_m_kpsi) <= 1e-12:
            nf = float('inf') if abs(tau_a_kpsi) <= 1e-12 else corrected_se / tau_a_kpsi
            criterion_used = 'zero_mean_simple_ratio'
            criterion_note = "In the absence of a midrange component, n_f = S_se / tau_a'"
        else:
            raise ValidationError('This solve path is intended for the zero-mean Example 9-5 style case. Use weld_fatigue_strength for repeated loading with nonzero mean stress.')

        return {
            'problem': self.solve_path,
            'title': inputs.get('title', 'Factor of safety of welding under fatigue loading'),
            'inputs': dict(inputs),
            'lookups': {
                'table_a_20': material,
                'table_9_3': electrode,
                'table_9_5': kfs_row,
                'table_6_2': {
                    'surface_finish': ka_data['surface_finish'],
                    'surface_finish_input': ka_data['surface_finish_input'],
                    'canonical_surface_finish': ka_data['canonical_surface_finish'],
                    'a_factor_kpsi': ka_data['a_factor_kpsi'],
                    'b_exponent': ka_data['b_exponent'],
                },
                'table_6_7': {
                    'criterion': 'not needed because mean stress is zero',
                },
                'table_9_2': {
                    'weld_type': int(inputs['weld_type']),
                    'description': geometry_eval['pattern'].description,
                    'throat_area_formula': geometry_eval['pattern'].throat_area_formula,
                },
            },
            'derived': {
                'weld_geometry': {
                    'throat_area_in2': A,
                },
                'strengths': {
                    'base_metal_tensile_strength_kpsi': material['tensile_strength_kpsi'],
                    'base_metal_yield_strength_kpsi': material['yield_strength_kpsi'],
                    'electrode_tensile_strength_kpsi': electrode['tensile_strength_kpsi'],
                    'electrode_yield_strength_kpsi': electrode['yield_strength_kpsi'],
                },
                'surface_finish_selection': {
                    'surface_finish_input': ka_data['surface_finish_input'],
                    'surface_finish_used': ka_data['surface_finish'],
                    'canonical_surface_finish': ka_data['canonical_surface_finish'],
                    'material_processing_input': ka_data['material_processing_input'],
                    'processing_inferred_surface_finish': ka_data['processing_inferred_surface_finish'],
                    'processing_surface_finish_consistent': ka_data['processing_surface_finish_consistent'],
                    'selection_note': ka_data['selection_note'],
                },
                'marin_factors': {
                    'ka': ka_data['ka'],
                    'kb': kb_data['kb'],
                    'kc': kc_data['kc'],
                    'kd': kd,
                    'ke': ke,
                    'kf_misc': kf_misc,
                },
                'endurance_limit': {
                    'prime_endurance_limit_kpsi': se_prime_data['S_e_prime_kpsi'],
                    'prime_endurance_limit_rule': se_prime_data['rule'],
                    'corrected_endurance_limit_kpsi': corrected_se,
                },
                'fatigue_loading': {
                    'K_fs': Kfs,
                    'force_amplitude_lbf': Fa_lbf,
                    'force_mean_lbf': Fm_lbf,
                    'stress_ratio_R': stress_ratio_R,
                    'alternating_shear_stress_kpsi': tau_a_kpsi,
                    'mean_shear_stress_kpsi': tau_m_kpsi,
                },
                'fatigue_factor_of_safety': {
                    'criterion_used': criterion_used,
                    'criterion_note': criterion_note,
                    'n_f': nf,
                    'is_satisfactory_for_infinite_life': nf >= 1.0,
                },
            },
            'summary': {
                'fatigue_factor_of_safety': nf,
                'is_satisfactory_for_infinite_life': nf >= 1.0,
            },
        }


class WeldFatigueStrengthSolver:
    solve_path = 'weld_fatigue_strength'

    def __init__(self) -> None:
        self.materials = SteelMaterialRepository()
        self.kfs_repo = FatigueStressConcentrationRepository()
        self.bending_patterns = WeldBendingGeometryEngine()
        self.marin = MarinFactorEngine()
        self.criteria = FatigueCriteriaRepository()

    def solve(self, inputs: Mapping[str, Any]) -> Dict[str, Any]:
        if inputs.get('solve_path') != self.solve_path:
            raise ValidationError(f"solve_path must be '{self.solve_path}'")

        material = self.materials.get(
            sae_aisi_no=inputs.get('attachment_material_sae_aisi_no'),
            processing=inputs.get('attachment_material_processing'),
        )
        kfs_row = self.kfs_repo.get(inputs['fatigue_stress_concentration_type'])
        geometry_eval = self.bending_patterns.evaluate_pattern(
            int(inputs['weld_type']),
            {k: float(v) for k, v in inputs['geometry'].items()},
            float(inputs['weld_size_in']),
        )

        ka_data = self.marin.surface_factor_ka(
            inputs['surface_finish'],
            material['tensile_strength_kpsi'],
            material_processing=material.get('processing'),
        )
        kb_data = self.marin.size_factor_kb(
            inputs.get('size_factor_mode', 'uniform_shear_on_throat'),
            kb_override=inputs.get('kb_override'),
        )
        kc_data = self.marin.load_factor_kc(inputs.get('loading_factor_mode', 'torsion_shear'))
        kd = float(inputs.get('temperature_factor_kd', 1.0))
        ke = float(inputs.get('reliability_factor_ke', 1.0))
        kf_misc = float(inputs.get('misc_factor_kf', 1.0))
        se_prime_data = self.marin.prime_endurance_limit_kpsi(material['tensile_strength_kpsi'])
        corrected_se = ka_data['ka'] * kb_data['kb'] * kc_data['kc'] * kd * ke * kf_misc * se_prime_data['S_e_prime_kpsi']

        A = geometry_eval['area_in2']
        if A <= 0.0:
            raise ValidationError('Computed weld throat area must be positive')
        Fa_lbf = float(inputs['force_amplitude_lbf'])
        Fm_lbf = float(inputs['force_mean_lbf'])
        Kfs = kfs_row['K_fs']
        tau_a_kpsi = Kfs * Fa_lbf / A / 1000.0
        tau_m_kpsi = Kfs * Fm_lbf / A / 1000.0
        stress_ratio_R = (Fm_lbf - Fa_lbf) / (Fm_lbf + Fa_lbf) if abs(Fm_lbf + Fa_lbf) > 1e-12 else None

        shear_ultimate_strength_kpsi = 0.67 * material['tensile_strength_kpsi']
        if abs(tau_m_kpsi) <= 1e-12:
            nf = float('inf') if abs(tau_a_kpsi) <= 1e-12 else corrected_se / tau_a_kpsi
            criterion_used = 'zero_mean_simple_ratio'
            criterion_note = "Midrange component is zero, so the Gerber relation collapses to n_f = S_se / tau_a'."
        else:
            nf = self.criteria.gerber_factor_of_safety(
                shear_ultimate_strength_kpsi=shear_ultimate_strength_kpsi,
                corrected_endurance_limit_kpsi=corrected_se,
                alternating_shear_kpsi=tau_a_kpsi,
                mean_shear_kpsi=tau_m_kpsi,
            )
            criterion_used = 'gerber_in_shear'
            criterion_note = 'Gerber fatigue factor of safety evaluated in shear using Table 6-7.'

        return {
            'problem': self.solve_path,
            'title': inputs.get('title', 'Fatigue strength of welding under fatigue loading'),
            'inputs': dict(inputs),
            'lookups': {
                'table_a_20': material,
                'table_9_5': kfs_row,
                'table_6_2': {
                    'surface_finish': ka_data['surface_finish'],
                    'surface_finish_input': ka_data['surface_finish_input'],
                    'canonical_surface_finish': ka_data['canonical_surface_finish'],
                    'a_factor_kpsi': ka_data['a_factor_kpsi'],
                    'b_exponent': ka_data['b_exponent'],
                },
                'table_6_7': {
                    'criterion': 'gerber' if criterion_used == 'gerber_in_shear' else 'not needed because mean stress is zero',
                    'fatigue_factor_of_safety_equation': self.criteria.fos_equation,
                },
                'table_9_2': {
                    'weld_type': int(inputs['weld_type']),
                    'description': geometry_eval['pattern'].description,
                    'throat_area_formula': geometry_eval['pattern'].throat_area_formula,
                },
            },
            'derived': {
                'weld_geometry': {
                    'throat_area_in2': A,
                },
                'strengths': {
                    'base_metal_tensile_strength_kpsi': material['tensile_strength_kpsi'],
                    'base_metal_yield_strength_kpsi': material['yield_strength_kpsi'],
                    'shear_ultimate_strength_kpsi': shear_ultimate_strength_kpsi,
                    'shear_ultimate_strength_rule': 'S_su = 0.67*S_ut',
                },
                'surface_finish_selection': {
                    'surface_finish_input': ka_data['surface_finish_input'],
                    'surface_finish_used': ka_data['surface_finish'],
                    'canonical_surface_finish': ka_data['canonical_surface_finish'],
                    'material_processing_input': ka_data['material_processing_input'],
                    'processing_inferred_surface_finish': ka_data['processing_inferred_surface_finish'],
                    'processing_surface_finish_consistent': ka_data['processing_surface_finish_consistent'],
                    'selection_note': ka_data['selection_note'],
                },
                'marin_factors': {
                    'ka': ka_data['ka'],
                    'kb': kb_data['kb'],
                    'kc': kc_data['kc'],
                    'kd': kd,
                    'ke': ke,
                    'kf_misc': kf_misc,
                },
                'endurance_limit': {
                    'prime_endurance_limit_kpsi': se_prime_data['S_e_prime_kpsi'],
                    'prime_endurance_limit_rule': se_prime_data['rule'],
                    'corrected_endurance_limit_kpsi': corrected_se,
                },
                'fatigue_loading': {
                    'K_fs': Kfs,
                    'force_amplitude_lbf': Fa_lbf,
                    'force_mean_lbf': Fm_lbf,
                    'stress_ratio_R': stress_ratio_R,
                    'alternating_shear_stress_kpsi': tau_a_kpsi,
                    'mean_shear_stress_kpsi': tau_m_kpsi,
                },
                'fatigue_factor_of_safety': {
                    'criterion_used': criterion_used,
                    'criterion_note': criterion_note,
                    'n_f': nf,
                    'is_satisfactory_for_infinite_life': nf >= 1.0,
                },
            },
            'summary': {
                'fatigue_factor_of_safety': nf,
                'is_satisfactory_for_infinite_life': nf >= 1.0,
            },
        }
