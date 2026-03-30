from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import csv
import math

from utils import normalize_oil_grade, safe_float


SAE_OIL_CORRELATIONS: Dict[str, Dict[str, float]] = {
    '10': {'mu0': 0.0158e-6, 'b': 1157.5},
    '20': {'mu0': 0.0136e-6, 'b': 1271.6},
    '30': {'mu0': 0.0141e-6, 'b': 1360.0},
    '40': {'mu0': 0.0121e-6, 'b': 1474.4},
    '50': {'mu0': 0.0170e-6, 'b': 1509.6},
    '60': {'mu0': 0.0187e-6, 'b': 1564.0},
}

SELF_CONTAINED_HCR_PRESETS = {
    'still_air': 2.0,
    'shaft_stirred_air': 2.7,
    'moving_air_500_fpm': 5.9,
}

FIG12_24_COEFFS = {
    1.0: (0.349109, 6.00940, 0.047467),
    0.5: (0.394552, 6.392527, -0.036013),
    0.25: (0.933828, 6.437512, -0.011048),
}


@dataclass
class BearingInputs:
    mu: Optional[float]
    N: float
    W: float
    r: float
    c: float
    l: float
    unit_system: str = 'ips'
    Ps: float = 0.0
    notes: List[str] = field(default_factory=list)

    oil_grade: Optional[str] = None
    inlet_temp_F: Optional[float] = None
    rho: float = 0.0315
    cp: float = 0.48
    J: float = 778.0 * 12.0
    temp_tol_F: float = 2.0
    max_iter: int = 50

    ambient_temp_F: Optional[float] = None
    alpha: Optional[float] = None
    area_in2: Optional[float] = None
    h_cr: Optional[float] = None

    sump_temp_F: Optional[float] = None
    heat_loss_limit_btu_h: Optional[float] = None
    dj: Optional[float] = None
    db: Optional[float] = None
    l_prime: Optional[float] = None
    l_prime_over_d: Optional[float] = None

    @property
    def d(self) -> float:
        return 2.0 * self.r

    @property
    def pressure(self) -> float:
        return self.W / (self.d * self.l)

    def sommerfeld_for_mu(self, mu: float) -> float:
        return (self.r / self.c) ** 2 * (mu * self.N / self.pressure)

    @property
    def sommerfeld(self) -> float:
        if self.mu is None:
            raise ValueError('Sommerfeld requested but mu is not available.')
        return self.sommerfeld_for_mu(self.mu)

    @property
    def l_over_d(self) -> float:
        return self.l / self.d

    @property
    def pressure_fed_l_over_d(self) -> float:
        if self.l_prime_over_d is not None:
            return self.l_prime_over_d
        if self.l_prime is not None:
            return self.l_prime / self.d
        return self.l_over_d

    @property
    def pressure_fed_pressure(self) -> float:
        lprime = self.l_prime if self.l_prime is not None else self.l
        return self.W / (4.0 * self.r * lprime)

    @staticmethod
    def _maybe_float(value: Any) -> Optional[float]:
        if value in (None, ''):
            return None
        return float(value)

    @classmethod
    def from_mapping(cls, data: Dict[str, object]) -> 'BearingInputs':
        oil_grade_raw = data.get('oil_grade')
        oil_grade = None if oil_grade_raw in (None, '') else normalize_oil_grade(str(oil_grade_raw))
        inlet_temp_raw = data.get('inlet_temp_F', data.get('Tin_F', None))
        ambient_temp_raw = data.get('ambient_temp_F', data.get('T_inf_F', data.get('air_temp_F', None)))
        sump_temp_raw = data.get('sump_temp_F', data.get('Ts_F', data.get('supply_temp_F', None)))
        alpha_raw = data.get('alpha', None)
        area_raw = data.get('area_in2', data.get('A_in2', data.get('A', None)))
        hcr_raw = data.get('h_cr', data.get('hCR', data.get('h_cr_btu_h_ft2_F', None)))
        mu_raw = data.get('mu', None)

        dj = cls._maybe_float(data.get('dj'))
        db = cls._maybe_float(data.get('db'))
        l_prime_over_d_raw = data.get('l_prime_over_d', data.get('lprime_over_d', data.get('l_over_d', None)))
        r_raw = data.get('r', None)
        c_raw = data.get('c', None)
        l_raw = data.get('l', data.get('l_prime', data.get('lprime', None)))

        if r_raw not in (None, ''):
            r_val = float(r_raw)
        elif dj is not None:
            r_val = dj / 2.0
        else:
            raise ValueError("Input mapping must provide 'r' or 'dj'.")

        if c_raw not in (None, ''):
            c_val = float(c_raw)
        elif dj is not None and db is not None:
            c_val = (db - dj) / 2.0
        else:
            raise ValueError("Input mapping must provide 'c'.")

        if l_raw in (None, ''):
            raise ValueError("Input mapping must provide 'l' or 'l_prime'.")
        l_val = float(l_raw)

        return cls(
            mu=float(mu_raw) if mu_raw not in (None, '') else None,
            N=safe_float(data.get('N'), 'N'),
            W=safe_float(data.get('W'), 'W'),
            r=r_val,
            c=c_val,
            l=l_val,
            unit_system=str(data.get('unit_system', 'ips')).strip().lower() or 'ips',
            Ps=float(data.get('Ps', data.get('ps', 0.0)) or 0.0),
            notes=list(data.get('notes', [])) if isinstance(data.get('notes', []), list) else [],
            oil_grade=oil_grade,
            inlet_temp_F=float(inlet_temp_raw) if inlet_temp_raw not in (None, '') else None,
            rho=float(data.get('rho', 0.0315) or 0.0315),
            cp=float(data.get('cp', 0.48) or 0.48),
            J=float(data.get('J', 778.0 * 12.0) or (778.0 * 12.0)),
            temp_tol_F=float(data.get('temp_tol_F', data.get('temperature_tolerance_F', 2.0)) or 2.0),
            max_iter=int(data.get('max_iter', 50) or 50),
            ambient_temp_F=float(ambient_temp_raw) if ambient_temp_raw not in (None, '') else None,
            alpha=float(alpha_raw) if alpha_raw not in (None, '') else None,
            area_in2=float(area_raw) if area_raw not in (None, '') else None,
            h_cr=float(hcr_raw) if hcr_raw not in (None, '') else None,
            sump_temp_F=float(sump_temp_raw) if sump_temp_raw not in (None, '') else None,
            heat_loss_limit_btu_h=float(data.get('heat_loss_limit_btu_h')) if data.get('heat_loss_limit_btu_h') not in (None, '') else None,
            dj=dj,
            db=db,
            l_prime=float(l_raw) if data.get('l_prime', data.get('lprime', None)) not in (None, '') else None,
            l_prime_over_d=float(l_prime_over_d_raw) if l_prime_over_d_raw not in (None, '') else None,
        )

    def validate_common(self) -> None:
        for name in ('N', 'W', 'r', 'c', 'l'):
            value = getattr(self, name)
            if value <= 0.0:
                raise ValueError(f"Input '{name}' must be > 0. Received {value}.")
        if self.unit_system not in {'ips', 'custom'}:
            raise ValueError("Supported unit_system values are 'ips' and 'custom'.")
        if self.Ps < 0.0:
            raise ValueError("Input 'Ps' must be >= 0.")
        if self.rho <= 0.0:
            raise ValueError("Input 'rho' must be > 0.")
        if self.cp <= 0.0:
            raise ValueError("Input 'cp' must be > 0.")
        if self.J <= 0.0:
            raise ValueError("Input 'J' must be > 0.")
        if self.temp_tol_F <= 0.0:
            raise ValueError("Input 'temp_tol_F' must be > 0.")
        if self.max_iter <= 0:
            raise ValueError("Input 'max_iter' must be > 0.")
        if self.oil_grade is not None and self.oil_grade not in SAE_OIL_CORRELATIONS:
            supported = ', '.join(sorted(SAE_OIL_CORRELATIONS))
            raise ValueError(f"Unsupported oil_grade '{self.oil_grade}'. Supported SAE grades: {supported}")

    def viscosity_from_temperature(self, temp_F: float) -> float:
        if self.oil_grade is None:
            raise ValueError('Oil viscosity correlation requires oil_grade.')
        params = SAE_OIL_CORRELATIONS[self.oil_grade]
        return params['mu0'] * math.exp(params['b'] / (temp_F + 95.0))


@dataclass
class DerivedState:
    P: float
    S: float
    l_over_d: float
    r_over_c: float


@dataclass
class InterpolationResult:
    epsilon: float
    properties: Dict[str, float]
    l_over_d_bounds: Tuple[float, float]
    epsilon_bounds: Tuple[float, float]
    l_over_d_exact: bool
    epsilon_exact: bool
    s_residual: float
    iterations: int


@dataclass
class SolveResult:
    problem: str
    title: str
    inputs: Dict[str, object]
    derived: Dict[str, float]
    table_lookup: Dict[str, object]
    interpolated_dimensionless: Dict[str, float]
    outputs: Dict[str, float]
    checks: Dict[str, float | str | bool]
    notes: List[str]
    iteration_history: List[Dict[str, Any]] = field(default_factory=list)


class FiniteJournalBearingTable:
    PROPERTY_COLUMNS = (
        'S',
        'Qbar_L',
        'Qbar_i',
        'RC_over_C_times_f',
        'Pbar_max',
        'theta_max_deg',
        'phi_deg',
        'theta_cav_deg',
    )

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self.rows = self._load_rows(self.csv_path)
        self.l_over_d_values = sorted({row['L_over_D'] for row in self.rows})
        self.epsilon_values = sorted({row['epsilon'] for row in self.rows})
        self._grid: Dict[float, Dict[float, Dict[str, float]]] = {}
        for row in self.rows:
            self._grid.setdefault(row['L_over_D'], {})[row['epsilon']] = row

    def _load_rows(self, path: Path) -> List[Dict[str, float]]:
        rows: List[Dict[str, float]] = []
        with path.open('r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = {k: float(v) if k != 'L_over_D_label' else v for k, v in raw.items()}
                rows.append(row)
        if not rows:
            raise ValueError(f'No rows found in finite journal-bearing table: {path}')
        return rows

    @staticmethod
    def _bracket(value: float, grid: List[float]) -> Tuple[float, float, bool]:
        if value < grid[0] or value > grid[-1]:
            raise ValueError(
                f'Requested value {value} is outside the table range [{grid[0]}, {grid[-1]}].'
            )
        for g in grid:
            if math.isclose(value, g, rel_tol=0.0, abs_tol=1e-12):
                return g, g, True
        lo = grid[0]
        hi = grid[-1]
        for idx in range(len(grid) - 1):
            a = grid[idx]
            b = grid[idx + 1]
            if a <= value <= b:
                lo = a
                hi = b
                break
        return lo, hi, False

    @staticmethod
    def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
        if math.isclose(x0, x1, rel_tol=0.0, abs_tol=1e-15):
            return y0
        return y0 + (x - x0) * (y1 - y0) / (x1 - x0)

    def interpolate_property(self, l_over_d: float, epsilon: float, property_name: str) -> float:
        if property_name not in self.PROPERTY_COLUMNS:
            raise KeyError(f"Unknown table property '{property_name}'.")
        l0, l1, _ = self._bracket(l_over_d, self.l_over_d_values)
        e0, e1, _ = self._bracket(epsilon, self.epsilon_values)
        q11 = self._grid[l0][e0][property_name]
        q21 = self._grid[l1][e0][property_name]
        q12 = self._grid[l0][e1][property_name]
        q22 = self._grid[l1][e1][property_name]
        if math.isclose(l0, l1, abs_tol=1e-15) and math.isclose(e0, e1, abs_tol=1e-15):
            return q11
        if math.isclose(l0, l1, abs_tol=1e-15):
            return self._lerp(epsilon, e0, e1, q11, q12)
        if math.isclose(e0, e1, abs_tol=1e-15):
            return self._lerp(l_over_d, l0, l1, q11, q21)
        r1 = self._lerp(l_over_d, l0, l1, q11, q21)
        r2 = self._lerp(l_over_d, l0, l1, q12, q22)
        return self._lerp(epsilon, e0, e1, r1, r2)

    def interpolate_all(self, l_over_d: float, epsilon: float) -> Dict[str, float]:
        return {name: self.interpolate_property(l_over_d, epsilon, name) for name in self.PROPERTY_COLUMNS}

    def epsilon_from_sommerfeld(self, l_over_d: float, target_s: float, *, tol: float = 1e-10, max_iter: int = 100) -> InterpolationResult:
        l0, l1, l_exact = self._bracket(l_over_d, self.l_over_d_values)
        eps_lo = self.epsilon_values[0]
        eps_hi = self.epsilon_values[-1]
        s_at_lo = self.interpolate_property(l_over_d, eps_lo, 'S')
        s_at_hi = self.interpolate_property(l_over_d, eps_hi, 'S')
        s_max = max(s_at_lo, s_at_hi)
        s_min = min(s_at_lo, s_at_hi)
        if not (s_min <= target_s <= s_max):
            raise ValueError(
                f'Sommerfeld number {target_s} is outside the table-supported range [{s_min}, {s_max}] for L/D={l_over_d}.'
            )
        lo = eps_lo
        hi = eps_hi
        flo = self.interpolate_property(l_over_d, lo, 'S') - target_s
        fhi = self.interpolate_property(l_over_d, hi, 'S') - target_s
        if abs(flo) <= tol:
            props = self.interpolate_all(l_over_d, lo)
            e0, e1, e_exact = self._bracket(lo, self.epsilon_values)
            return InterpolationResult(lo, props, (l0, l1), (e0, e1), l_exact, e_exact, flo, 0)
        if abs(fhi) <= tol:
            props = self.interpolate_all(l_over_d, hi)
            e0, e1, e_exact = self._bracket(hi, self.epsilon_values)
            return InterpolationResult(hi, props, (l0, l1), (e0, e1), l_exact, e_exact, fhi, 0)
        if flo * fhi > 0.0:
            raise ValueError('Could not bracket epsilon from the table. Check the requested operating point.')
        mid = 0.5 * (lo + hi)
        fmid = self.interpolate_property(l_over_d, mid, 'S') - target_s
        iterations = 0
        while iterations < max_iter:
            mid = 0.5 * (lo + hi)
            fmid = self.interpolate_property(l_over_d, mid, 'S') - target_s
            if abs(fmid) <= tol or abs(hi - lo) <= tol:
                break
            if flo * fmid <= 0.0:
                hi = mid
                fhi = fmid
            else:
                lo = mid
                flo = fmid
            iterations += 1
        props = self.interpolate_all(l_over_d, mid)
        e0, e1, e_exact = self._bracket(mid, self.epsilon_values)
        return InterpolationResult(
            epsilon=mid,
            properties=props,
            l_over_d_bounds=(l0, l1),
            epsilon_bounds=(e0, e1),
            l_over_d_exact=l_exact,
            epsilon_exact=e_exact,
            s_residual=fmid,
            iterations=iterations,
        )


class BaseProblem:
    problem_name: str = 'base'
    title: str = 'Base Problem'

    def __init__(self, inputs: BearingInputs, table: FiniteJournalBearingTable):
        self.inputs = inputs
        self.inputs.validate_common()
        self.table = table
        self.state: Optional[DerivedState] = None
        self.lookup: Optional[InterpolationResult] = None
        if self.inputs.mu is not None:
            self.state, self.lookup = self._state_lookup_for_mu(self.inputs.mu)

    def _state_lookup_for_mu(self, mu: float) -> Tuple[DerivedState, InterpolationResult]:
        state = DerivedState(
            P=self.inputs.pressure,
            S=self.inputs.sommerfeld_for_mu(mu),
            l_over_d=self.inputs.l_over_d,
            r_over_c=self.inputs.r / self.inputs.c,
        )
        lookup = self.table.epsilon_from_sommerfeld(state.l_over_d, state.S)
        return state, lookup

    def _require_state_lookup(self) -> Tuple[DerivedState, InterpolationResult]:
        if self.state is None or self.lookup is None:
            raise ValueError('This route requires a known viscosity or a prior lookup state.')
        return self.state, self.lookup

    def _performance_from_lookup(self, mu: float, state: DerivedState, lookup: InterpolationResult) -> Dict[str, float]:
        qbar_l = lookup.properties['Qbar_L']
        qbar_i = lookup.properties['Qbar_i']
        scale = (math.pi / 2.0) * self.inputs.N * self.inputs.d * self.inputs.l * self.inputs.c
        q_leakage = qbar_l * scale
        q_inlet = qbar_i * scale
        rcf = lookup.properties['RC_over_C_times_f']
        f = rcf * self.inputs.c / self.inputs.r
        friction_force_lbf = f * self.inputs.W
        torque_lbf_in = friction_force_lbf * self.inputs.r
        power_in_lbf_s = friction_force_lbf * (2.0 * math.pi * self.inputs.r * self.inputs.N)
        pbar_max = lookup.properties['Pbar_max']
        pmax = mu * self.inputs.N * (self.inputs.r / self.inputs.c) ** 2 * pbar_max + self.inputs.Ps
        h_min = self.inputs.c * (1.0 - lookup.epsilon)
        e = self.inputs.c * lookup.epsilon
        return {
            'h_min': h_min,
            'e': e,
            'phi_deg': lookup.properties['phi_deg'],
            'theta_cav_deg': lookup.properties['theta_cav_deg'],
            'f': f,
            'friction_force_lbf': friction_force_lbf,
            'torque_lbf_in': torque_lbf_in,
            'power_in_lbf_s': power_in_lbf_s,
            'power_loss_hp': power_in_lbf_s / 6600.0 if self.inputs.unit_system == 'ips' else float('nan'),
            'heat_loss_btu_s': power_in_lbf_s / (778.0 * 12.0) if self.inputs.unit_system == 'ips' else float('nan'),
            'Q_leakage': q_leakage,
            'Q_inlet': q_inlet,
            'Q_recirculated': q_inlet - q_leakage,
            'pmax': pmax,
            'theta_max_deg': lookup.properties['theta_max_deg'],
            'Pbar_max': pbar_max,
            'fr_over_c': rcf,
        }

    def base_inputs(self) -> Dict[str, object]:
        data: Dict[str, object] = {
            'mu': self.inputs.mu,
            'N': self.inputs.N,
            'W': self.inputs.W,
            'r': self.inputs.r,
            'c': self.inputs.c,
            'l': self.inputs.l,
            'd': self.inputs.d,
            'Ps': self.inputs.Ps,
            'unit_system': self.inputs.unit_system,
        }
        if self.inputs.dj is not None:
            data['dj'] = self.inputs.dj
        if self.inputs.l_prime is not None:
            data['l_prime'] = self.inputs.l_prime
        if self.inputs.l_prime_over_d is not None:
            data['l_prime_over_d'] = self.inputs.l_prime_over_d
        if self.inputs.oil_grade is not None:
            data['oil_grade'] = self.inputs.oil_grade
        if self.inputs.inlet_temp_F is not None:
            data['inlet_temp_F'] = self.inputs.inlet_temp_F
        if self.inputs.sump_temp_F is not None:
            data['sump_temp_F'] = self.inputs.sump_temp_F
        if self.inputs.ambient_temp_F is not None:
            data['ambient_temp_F'] = self.inputs.ambient_temp_F
        if self.inputs.alpha is not None:
            data['alpha'] = self.inputs.alpha
        if self.inputs.area_in2 is not None:
            data['area_in2'] = self.inputs.area_in2
        if self.inputs.h_cr is not None:
            data['h_cr'] = self.inputs.h_cr
        if self.inputs.heat_loss_limit_btu_h is not None:
            data['heat_loss_limit_btu_h'] = self.inputs.heat_loss_limit_btu_h
        if self.inputs.rho != 0.0315:
            data['rho'] = self.inputs.rho
        if self.inputs.cp != 0.48:
            data['cp'] = self.inputs.cp
        if self.inputs.J != 778.0 * 12.0:
            data['J'] = self.inputs.J
        if self.inputs.temp_tol_F != 2.0:
            data['temp_tol_F'] = self.inputs.temp_tol_F
        if self.inputs.max_iter != 50:
            data['max_iter'] = self.inputs.max_iter
        return data

    def _derived_from_state(self, state: DerivedState) -> Dict[str, float]:
        return {
            'P': state.P,
            'S': state.S,
            'l_over_d': state.l_over_d,
            'r_over_c': state.r_over_c,
        }

    def base_derived(self) -> Dict[str, float]:
        state, _ = self._require_state_lookup()
        return self._derived_from_state(state)

    def _lookup_metadata_from_lookup(self, lookup: InterpolationResult) -> Dict[str, object]:
        return {
            'table_source': str(self.table.csv_path),
            'l_over_d_lower': lookup.l_over_d_bounds[0],
            'l_over_d_upper': lookup.l_over_d_bounds[1],
            'epsilon_lower': lookup.epsilon_bounds[0],
            'epsilon_upper': lookup.epsilon_bounds[1],
            'l_over_d_exact': lookup.l_over_d_exact,
            'epsilon_exact': lookup.epsilon_exact,
            'solver': 'bilinear interpolation in (L/D, epsilon) + bisection on epsilon from Sommerfeld number',
            'iterations': lookup.iterations,
        }

    def lookup_metadata(self) -> Dict[str, object]:
        _, lookup = self._require_state_lookup()
        return self._lookup_metadata_from_lookup(lookup)

    def _interpolated_dimensionless_from_lookup(self, lookup: InterpolationResult) -> Dict[str, float]:
        props = dict(lookup.properties)
        props['epsilon'] = lookup.epsilon
        return props

    def interpolated_dimensionless(self) -> Dict[str, float]:
        _, lookup = self._require_state_lookup()
        return self._interpolated_dimensionless_from_lookup(lookup)

    def solve(self) -> SolveResult:
        raise NotImplementedError


class MinimumFilmThicknessProblem(BaseProblem):
    problem_name = 'minimum_film_thickness'
    title = 'Minimum Film Thickness: automated table lookup via finite journal-bearing dataset'

    def solve(self) -> SolveResult:
        _, lookup = self._require_state_lookup()
        eps = lookup.epsilon
        h_min = self.inputs.c * (1.0 - eps)
        e = self.inputs.c * eps
        phi_deg = lookup.properties['phi_deg']
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            table_lookup=self.lookup_metadata(),
            interpolated_dimensionless=self.interpolated_dimensionless(),
            outputs={
                'h_min': h_min,
                'e': e,
                'phi_deg': phi_deg,
                'theta_cav_deg': lookup.properties['theta_cav_deg'],
            },
            checks={
                'h_min_over_c_minus_1_minus_epsilon': (h_min / self.inputs.c) - (1.0 - eps),
                'sommerfeld_residual': lookup.s_residual,
            },
            notes=[
                'This route uses finite_journal_bearing.csv instead of manual chart entry.',
                'Minimum film thickness is computed with Khonsari Eq. (8.41): h_min = C(1 - epsilon).',
                'Attitude angle phi is taken directly from the interpolated table values.',
                'theta_cav_deg is included as an extra dataset output.',
            ],
        )


class CoefficientOfFrictionProblem(BaseProblem):
    problem_name = 'coefficient_of_friction'
    title = 'Coefficient of Friction: automated table lookup via finite journal-bearing dataset'

    def solve(self) -> SolveResult:
        state, lookup = self._require_state_lookup()
        perf = self._performance_from_lookup(self.inputs.mu or 0.0, state, lookup)
        outputs: Dict[str, float] = {
            'f': perf['f'],
            'friction_force_lbf': perf['friction_force_lbf'],
            'torque_lbf_in': perf['torque_lbf_in'],
            'power_in_lbf_s': perf['power_in_lbf_s'],
        }
        if self.inputs.unit_system == 'ips':
            outputs['power_loss_hp'] = perf['power_loss_hp']
            outputs['heat_loss_btu_s'] = perf['heat_loss_btu_s']
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            table_lookup=self.lookup_metadata(),
            interpolated_dimensionless=self.interpolated_dimensionless(),
            outputs=outputs,
            checks={
                'torque_minus_fWr': perf['torque_lbf_in'] - (perf['f'] * self.inputs.W * self.inputs.r),
                'sommerfeld_residual': lookup.s_residual,
            },
            notes=[
                'The table column RC_over_C_times_f is interpreted as (R/C)f.',
                'Friction coefficient is recovered from f = [(R/C)f] * (C/R).',
                'Power loss is computed from Khonsari Eq. (8.43): E_p = F 2 pi R N_s.',
            ],
        )


class VolumetricFlowRateProblem(BaseProblem):
    problem_name = 'volumetric_flow_rate'
    title = 'Volumetric Flow Rate: automated table lookup via finite journal-bearing dataset'

    def solve(self) -> SolveResult:
        state, lookup = self._require_state_lookup()
        perf = self._performance_from_lookup(self.inputs.mu or 0.0, state, lookup)
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            table_lookup=self.lookup_metadata(),
            interpolated_dimensionless=self.interpolated_dimensionless(),
            outputs={
                'Q_leakage': perf['Q_leakage'],
                'Q_inlet': perf['Q_inlet'],
                'Q_total_shigley_equivalent': perf['Q_inlet'],
                'Q_side_shigley_equivalent': perf['Q_leakage'],
                'Q_recirculated': perf['Q_recirculated'],
            },
            checks={
                'sommerfeld_residual': lookup.s_residual,
            },
            notes=[
                'Leakage flow is computed with Khonsari Eq. (8.39): Q_L = Qbar_L * (pi/2) * N_s D L C.',
                'Inlet flow is computed with Khonsari Eq. (8.40): Q_i = Qbar_i * (pi/2) * N_s D L C.',
                'Shigley side flow aligns with Khonsari leakage flow for the 360-degree bearing formulation.',
            ],
        )


class MaximumFilmPressureProblem(BaseProblem):
    problem_name = 'maximum_film_pressure'
    title = 'Maximum Film Pressure: automated table lookup via finite journal-bearing dataset'

    def solve(self) -> SolveResult:
        state, lookup = self._require_state_lookup()
        perf = self._performance_from_lookup(self.inputs.mu or 0.0, state, lookup)
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            table_lookup=self.lookup_metadata(),
            interpolated_dimensionless=self.interpolated_dimensionless(),
            outputs={
                'pmax': perf['pmax'],
                'theta_max_deg': perf['theta_max_deg'],
                'phi_deg': lookup.properties['phi_deg'],
                'theta_cav_deg': lookup.properties['theta_cav_deg'],
            },
            checks={
                'sommerfeld_residual': lookup.s_residual,
            },
            notes=[
                'Maximum pressure is computed from the dimensionless pressure definition used with Khonsari Eq. (8.36).',
                'For the current non-pressure-fed scope, supply pressure Ps is normally zero.',
                'theta_p0 is not reported because the dataset does not provide Shigley terminating-pressure angle directly.',
            ],
        )


class TemperatureRiseProblem(BaseProblem):
    problem_name = 'temperature_rise'
    title = 'Temperature Rise: iterative finite journal-bearing solution with SAE oil viscosity correlation'

    def solve(self) -> SolveResult:
        if self.inputs.oil_grade is None or self.inputs.inlet_temp_F is None or self.inputs.mu is None:
            raise ValueError('temperature_rise requires mu, oil_grade and inlet_temp_F so viscosity can be iterated from temperature.')

        initial_mu_from_correlation = self.inputs.viscosity_from_temperature(self.inputs.inlet_temp_F)
        current_mu = self.inputs.mu
        current_effective_temp_F = self.inputs.inlet_temp_F
        iteration_history: List[Dict[str, Any]] = []
        converged = False

        for idx in range(1, self.inputs.max_iter + 1):
            state, lookup = self._state_lookup_for_mu(current_mu)
            perf = self._performance_from_lookup(current_mu, state, lookup)

            delta_T = perf['power_in_lbf_s'] / (self.inputs.J * self.inputs.rho * self.inputs.cp * perf['Q_leakage'])
            updated_effective_temp_F = self.inputs.inlet_temp_F + delta_T
            updated_mu = self.inputs.viscosity_from_temperature(updated_effective_temp_F)
            temp_change_F = updated_effective_temp_F - current_effective_temp_F

            iteration_history.append({
                'iteration': idx,
                'mu_used': current_mu,
                'effective_temp_used_F': current_effective_temp_F,
                'effective_temp_updated_F': updated_effective_temp_F,
                'delta_T_F': delta_T,
                'effective_temp_change_F': temp_change_F,
                'S': state.S,
                'epsilon': lookup.epsilon,
                'phi_deg': lookup.properties['phi_deg'],
                'theta_cav_deg': lookup.properties['theta_cav_deg'],
                'Q_leakage': perf['Q_leakage'],
                'Q_inlet': perf['Q_inlet'],
                'f': perf['f'],
                'friction_force_lbf': perf['friction_force_lbf'],
                'power_in_lbf_s': perf['power_in_lbf_s'],
                'power_loss_hp': perf['power_loss_hp'],
                'heat_loss_btu_s': perf['heat_loss_btu_s'],
                'pmax': perf['pmax'],
                'updated_mu': updated_mu,
                'sommerfeld_residual': lookup.s_residual,
            })

            if abs(temp_change_F) <= self.inputs.temp_tol_F:
                converged = True
                current_effective_temp_F = updated_effective_temp_F
                current_mu = updated_mu
                break

            current_effective_temp_F = updated_effective_temp_F
            current_mu = updated_mu

        final_state, final_lookup = self._state_lookup_for_mu(current_mu)
        final_perf = self._performance_from_lookup(current_mu, final_state, final_lookup)
        final_delta_T = current_effective_temp_F - self.inputs.inlet_temp_F

        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self._derived_from_state(final_state),
            table_lookup=self._lookup_metadata_from_lookup(final_lookup),
            interpolated_dimensionless=self._interpolated_dimensionless_from_lookup(final_lookup),
            outputs={
                'mu_initial': self.inputs.mu,
                'mu_initial_from_correlation': initial_mu_from_correlation,
                'mu_effective': current_mu,
                'T_inlet_F': self.inputs.inlet_temp_F,
                'T_effective_F': current_effective_temp_F,
                'delta_T_F': final_delta_T,
                'h_min': final_perf['h_min'],
                'e': final_perf['e'],
                'phi_deg': final_perf['phi_deg'],
                'theta_cav_deg': final_perf['theta_cav_deg'],
                'Q_leakage': final_perf['Q_leakage'],
                'Q_inlet': final_perf['Q_inlet'],
                'Q_recirculated': final_perf['Q_recirculated'],
                'f': final_perf['f'],
                'friction_force_lbf': final_perf['friction_force_lbf'],
                'torque_lbf_in': final_perf['torque_lbf_in'],
                'power_in_lbf_s': final_perf['power_in_lbf_s'],
                'power_loss_hp': final_perf['power_loss_hp'],
                'heat_loss_btu_s': final_perf['heat_loss_btu_s'],
                'pmax': final_perf['pmax'],
                'theta_max_deg': final_perf['theta_max_deg'],
            },
            checks={
                'converged': converged,
                'temperature_tolerance_F': self.inputs.temp_tol_F,
                'final_effective_temp_change_F': abs(iteration_history[-1]['effective_temp_change_F']) if iteration_history else float('nan'),
                'initial_mu_minus_correlation_mu': self.inputs.mu - initial_mu_from_correlation,
                'sommerfeld_residual': final_lookup.s_residual,
            },
            notes=[
                'Temperature rise is computed with Khonsari Eq. (8.44): delta_T = E_p / (J rho c_p Q_L).',
                'Viscosity is updated each iteration with the SAE oil correlation mu = mu0 exp[b / (T + 95)] using T in degrees F.',
                'The loop converges when the change in effective temperature between successive iterations is within temp_tol_F.',
                'Q_L is the Khonsari leakage flow, which aligns with the side-flow concept used in Shigley energy-balance discussion.',
            ],
            iteration_history=iteration_history,
        )


class SelfContainedSteadyStateProblem(BaseProblem):
    problem_name = 'self_contained_steady_state'
    title = 'Self-Contained Bearing Steady State: Shigley Example 12-5 style heat-balance solution'

    def __init__(self, inputs: BearingInputs, table: FiniteJournalBearingTable):
        super().__init__(inputs, table)
        if inputs.oil_grade is None:
            raise ValueError('self_contained_steady_state requires oil_grade.')
        if inputs.ambient_temp_F is None:
            raise ValueError('self_contained_steady_state requires ambient_temp_F.')
        if inputs.alpha is None or inputs.alpha <= 0.0:
            raise ValueError('self_contained_steady_state requires alpha > 0.')
        if inputs.area_in2 is None or inputs.area_in2 <= 0.0:
            raise ValueError('self_contained_steady_state requires area_in2 > 0.')
        if inputs.h_cr is None or inputs.h_cr <= 0.0:
            raise ValueError('self_contained_steady_state requires h_cr > 0.')
        if not (0.25 <= inputs.l_over_d <= 1.0):
            raise ValueError('self_contained_steady_state currently supports 0.25 <= l/d <= 1.0 because Fig. 12-24 correlations are only available for 1, 1/2, and 1/4.')

    def _dimless_temp_rise_variable(self, l_over_d: float, S: float) -> Tuple[float, Dict[str, float | bool | str]]:
        keys = sorted(FIG12_24_COEFFS.keys())
        if l_over_d < min(keys) or l_over_d > max(keys):
            raise ValueError(f'l/d={l_over_d} is outside the supported Fig. 12-24 range [{min(keys)}, {max(keys)}].')

        def poly(ld: float) -> float:
            a, b, c = FIG12_24_COEFFS[ld]
            return a + b * S + c * S * S

        if any(math.isclose(l_over_d, k, abs_tol=1e-12) for k in keys):
            k = min(keys, key=lambda x: abs(x - l_over_d))
            return poly(k), {'fig12_24_mode': 'exact', 'l_over_d_lower': k, 'l_over_d_upper': k}

        lower = max(k for k in keys if k < l_over_d)
        upper = min(k for k in keys if k > l_over_d)
        y_lower = poly(lower)
        y_upper = poly(upper)
        y = y_lower + (l_over_d - lower) * (y_upper - y_lower) / (upper - lower)
        return y, {
            'fig12_24_mode': 'linear interpolation in l/d between available polynomial correlations',
            'l_over_d_lower': lower,
            'l_over_d_upper': upper,
        }

    def _evaluate_trial(self, trial_temp_F: float) -> Dict[str, Any]:
        mu_trial = self.inputs.viscosity_from_temperature(trial_temp_F)
        state, lookup = self._state_lookup_for_mu(mu_trial)
        perf = self._performance_from_lookup(mu_trial, state, lookup)
        heat_gen_btu_h = perf['power_loss_hp'] * 2545.0
        area_ft2 = (self.inputs.area_in2 or 0.0) / 144.0
        heat_loss_btu_h = (self.inputs.h_cr or 0.0) * area_ft2 / (1.0 + (self.inputs.alpha or 0.0)) * (trial_temp_F - (self.inputs.ambient_temp_F or 0.0))
        residual_btu_h = heat_gen_btu_h - heat_loss_btu_h
        y_dimless, fig_meta = self._dimless_temp_rise_variable(state.l_over_d, state.S)
        delta_T_F = y_dimless * state.P / 9.70
        T_sump_F = trial_temp_F - delta_T_F / 2.0
        T_max_F = T_sump_F + delta_T_F
        T_b_F = (trial_temp_F + (self.inputs.alpha or 0.0) * (self.inputs.ambient_temp_F or 0.0)) / (1.0 + (self.inputs.alpha or 0.0))
        return {
            'trial_temp_F': trial_temp_F,
            'mu_trial': mu_trial,
            'S': state.S,
            'epsilon': lookup.epsilon,
            'phi_deg': lookup.properties['phi_deg'],
            'theta_cav_deg': lookup.properties['theta_cav_deg'],
            'fr_over_c': perf['fr_over_c'],
            'f': perf['f'],
            'h_min': perf['h_min'],
            'torque_lbf_in': perf['torque_lbf_in'],
            'power_loss_hp': perf['power_loss_hp'],
            'heat_generation_btu_h': heat_gen_btu_h,
            'heat_loss_btu_h': heat_loss_btu_h,
            'residual_btu_h': residual_btu_h,
            'delta_T_F': delta_T_F,
            'T_sump_F': T_sump_F,
            'T_max_F': T_max_F,
            'T_b_F': T_b_F,
            'pmax': perf['pmax'],
            'theta_max_deg': perf['theta_max_deg'],
            'Q_leakage': perf['Q_leakage'],
            'sommerfeld_residual': lookup.s_residual,
            'lookup': lookup,
            'state': state,
            'fig12_24_y': y_dimless,
            **fig_meta,
        }

    def _bracket_root(self) -> Tuple[float, Dict[str, Any], float, Dict[str, Any]]:
        T_inf = self.inputs.ambient_temp_F or 0.0
        valid_points: List[Tuple[float, Dict[str, Any]]] = []
        for temp in [T_inf + 1.0 + 5.0 * i for i in range(0, 121)]:
            try:
                valid_points.append((temp, self._evaluate_trial(temp)))
            except ValueError:
                continue
        if len(valid_points) < 2:
            raise ValueError('Could not find enough valid trial temperatures within the finite-bearing table range for the self-contained solver.')
        for (t0, e0), (t1, e1) in zip(valid_points[:-1], valid_points[1:]):
            if e0['residual_btu_h'] == 0.0:
                return t0, e0, t0, e0
            if e0['residual_btu_h'] * e1['residual_btu_h'] <= 0.0:
                return t0, e0, t1, e1
        raise ValueError('Could not bracket the self-contained steady-state temperature. Try checking inputs or expanding the valid operating range.')

    def solve(self) -> SolveResult:
        lo, eval_lo, hi, eval_hi = self._bracket_root()
        iteration_history: List[Dict[str, Any]] = []
        converged = False
        final_eval = eval_lo

        for idx in range(1, self.inputs.max_iter + 1):
            mid = 0.5 * (lo + hi)
            eval_mid = self._evaluate_trial(mid)
            iteration_history.append({
                'iteration': idx,
                'trial_temp_F': eval_mid['trial_temp_F'],
                'mu_trial': eval_mid['mu_trial'],
                'S': eval_mid['S'],
                'epsilon': eval_mid['epsilon'],
                'fr_over_c': eval_mid['fr_over_c'],
                'heat_generation_btu_h': eval_mid['heat_generation_btu_h'],
                'heat_loss_btu_h': eval_mid['heat_loss_btu_h'],
                'residual_btu_h': eval_mid['residual_btu_h'],
                'delta_T_F': eval_mid['delta_T_F'],
                'T_b_F': eval_mid['T_b_F'],
                'T_sump_F': eval_mid['T_sump_F'],
                'T_max_F': eval_mid['T_max_F'],
            })
            final_eval = eval_mid
            if abs(eval_mid['residual_btu_h']) <= 1e-6 or abs(hi - lo) <= self.inputs.temp_tol_F:
                converged = True
                break
            if eval_lo['residual_btu_h'] * eval_mid['residual_btu_h'] <= 0.0:
                hi = mid
                eval_hi = eval_mid
            else:
                lo = mid
                eval_lo = eval_mid

        final_lookup: InterpolationResult = final_eval['lookup']
        final_state: DerivedState = final_eval['state']
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived={
                **self._derived_from_state(final_state),
                'heat_loss_bracket_lower_temp_F': lo,
                'heat_loss_bracket_upper_temp_F': hi,
            },
            table_lookup={
                **self._lookup_metadata_from_lookup(final_lookup),
                'fig12_24_mode': final_eval['fig12_24_mode'],
                'fig12_24_l_over_d_lower': final_eval['l_over_d_lower'],
                'fig12_24_l_over_d_upper': final_eval['l_over_d_upper'],
            },
            interpolated_dimensionless={
                **self._interpolated_dimensionless_from_lookup(final_lookup),
                'fr_over_c': final_eval['fr_over_c'],
                'fig12_24_y': final_eval['fig12_24_y'],
            },
            outputs={
                'mu_effective': final_eval['mu_trial'],
                'T_f_avg_F': final_eval['trial_temp_F'],
                'delta_T_F': final_eval['delta_T_F'],
                'T_sump_F': final_eval['T_sump_F'],
                'T_max_F': final_eval['T_max_F'],
                'T_b_F': final_eval['T_b_F'],
                'h_min': final_eval['h_min'],
                'phi_deg': final_eval['phi_deg'],
                'theta_cav_deg': final_eval['theta_cav_deg'],
                'f': final_eval['f'],
                'fr_over_c': final_eval['fr_over_c'],
                'torque_lbf_in': final_eval['torque_lbf_in'],
                'power_loss_hp': final_eval['power_loss_hp'],
                'heat_generation_btu_h': final_eval['heat_generation_btu_h'],
                'heat_loss_btu_h': final_eval['heat_loss_btu_h'],
                'pmax': final_eval['pmax'],
                'theta_max_deg': final_eval['theta_max_deg'],
            },
            checks={
                'converged': converged,
                'temperature_tolerance_F': self.inputs.temp_tol_F,
                'final_bracket_width_F': abs(hi - lo),
                'heat_balance_residual_btu_h': final_eval['residual_btu_h'],
                'sommerfeld_residual': final_eval['sommerfeld_residual'],
            },
            notes=[
                'This route implements Shigley Sec. 12-9 style steady-state analysis for self-contained bearings.',
                'Average film temperature is solved from heat balance H_gen = H_loss using bisection, not manual trial-and-error.',
                'H_loss uses Eq. (12-19a): h_CR A /(1+alpha) * (T_f_bar - T_inf).',
                'delta_T_F uses Fig. 12-24 polynomial correlations for l/d = 1, 1/2, 1/4. For intermediate l/d in [0.25, 1], the app linearly interpolates between the available polynomial outputs.',
                'Friction and minimum film thickness are then computed from the finite-bearing dataset at the converged viscosity.',
            ],
            iteration_history=iteration_history,
        )



class PressureFedCircumferentialProblem(BaseProblem):
    problem_name = 'pressure_fed_circumferential'
    title = 'Pressure-Fed Circumferential-Groove Bearing: Shigley Example 12-6 style iterative solution'

    def __init__(self, inputs: BearingInputs, table: FiniteJournalBearingTable):
        super().__init__(inputs, table)
        if inputs.oil_grade is None:
            raise ValueError('pressure_fed_circumferential requires oil_grade.')
        if inputs.sump_temp_F is None:
            raise ValueError('pressure_fed_circumferential requires sump_temp_F.')
        if inputs.Ps <= 0.0:
            raise ValueError('pressure_fed_circumferential requires Ps > 0.')
        if inputs.c <= 0.0:
            raise ValueError('pressure_fed_circumferential requires c > 0.')
        if inputs.l_prime is None and inputs.l <= 0.0:
            raise ValueError('pressure_fed_circumferential requires l_prime (or l used as l_prime).')
        if inputs.l_prime_over_d is None:
            raise ValueError('pressure_fed_circumferential requires l_prime_over_d as a given problem input.')
        if inputs.l_prime_over_d <= 0.0:
            raise ValueError('pressure_fed_circumferential requires l_prime_over_d > 0.')

    def _pressure_fed_state_lookup_for_mu(self, mu: float) -> Tuple[DerivedState, InterpolationResult]:
        state = DerivedState(
            P=self.inputs.pressure_fed_pressure,
            S=(self.inputs.r / self.inputs.c) ** 2 * (mu * self.inputs.N / self.inputs.pressure_fed_pressure),
            l_over_d=self.inputs.pressure_fed_l_over_d,
            r_over_c=self.inputs.r / self.inputs.c,
        )
        lookup = self.table.epsilon_from_sommerfeld(state.l_over_d, state.S)
        return state, lookup

    def _evaluate_trial(self, trial_temp_F: float) -> Dict[str, Any]:
        mu_trial = self.inputs.viscosity_from_temperature(trial_temp_F)
        state, lookup = self._pressure_fed_state_lookup_for_mu(mu_trial)
        perf = self._performance_from_lookup(mu_trial, state, lookup)
        epsilon = lookup.epsilon
        fr_over_c = perf['fr_over_c']
        delta_T_F = 0.0123 * fr_over_c * state.S * (self.inputs.W ** 2) / ((1.0 + 1.5 * epsilon ** 2) * self.inputs.Ps * (self.inputs.r ** 4))
        Tav_F = (self.inputs.sump_temp_F or 0.0) + delta_T_F / 2.0
        residual_F = Tav_F - trial_temp_F
        T_max_F = (self.inputs.sump_temp_F or 0.0) + delta_T_F
        lprime = self.inputs.l_prime if self.inputs.l_prime is not None else self.inputs.l
        Qs = math.pi * self.inputs.Ps * self.inputs.r * (self.inputs.c ** 3) / (3.0 * mu_trial * lprime) * (1.0 + 1.5 * epsilon ** 2)
        Hloss_btu_s = self.inputs.rho * self.inputs.cp * Qs * delta_T_F
        Hloss_btu_h = Hloss_btu_s * 3600.0
        torque_lbf_in = fr_over_c * self.inputs.W * self.inputs.c
        f = fr_over_c * self.inputs.c / self.inputs.r
        return {
            'trial_temp_F': trial_temp_F,
            'mu_trial': mu_trial,
            'S': state.S,
            'epsilon': epsilon,
            'fr_over_c': fr_over_c,
            'delta_T_F': delta_T_F,
            'T_av_F': Tav_F,
            'residual_F': residual_F,
            'T_max_F': T_max_F,
            'h_min': self.inputs.c * (1.0 - epsilon),
            'p_st': state.P,
            'phi_deg': lookup.properties['phi_deg'],
            'theta_cav_deg': lookup.properties['theta_cav_deg'],
            'Qs_in3_s': Qs,
            'Hloss_btu_s': Hloss_btu_s,
            'Hloss_btu_h': Hloss_btu_h,
            'torque_lbf_in': torque_lbf_in,
            'f': f,
            'pmax_total_psi': perf['pmax'],
            'theta_max_deg': perf['theta_max_deg'],
            'lookup': lookup,
            'state': state,
        }

    def _bracket_root(self) -> Tuple[float, Dict[str, Any], float, Dict[str, Any]]:
        Ts = self.inputs.sump_temp_F or 0.0
        valid_points: List[Tuple[float, Dict[str, Any]]] = []
        for temp in [Ts + 1.0 + 2.5 * i for i in range(0, 161)]:
            try:
                valid_points.append((temp, self._evaluate_trial(temp)))
            except ValueError:
                continue
        if len(valid_points) < 2:
            raise ValueError('Could not find enough valid trial temperatures within the finite-bearing table range for the pressure-fed solver.')
        for (t0, e0), (t1, e1) in zip(valid_points[:-1], valid_points[1:]):
            if e0['residual_F'] == 0.0:
                return t0, e0, t0, e0
            if e0['residual_F'] * e1['residual_F'] <= 0.0:
                return t0, e0, t1, e1
        raise ValueError('Could not bracket the pressure-fed average film temperature. Check the input geometry, oil grade, or operating conditions.')

    def solve(self) -> SolveResult:
        lo, eval_lo, hi, eval_hi = self._bracket_root()
        iteration_history: List[Dict[str, Any]] = []
        converged = False
        final_eval = eval_lo
        for idx in range(1, self.inputs.max_iter + 1):
            mid = 0.5 * (lo + hi)
            eval_mid = self._evaluate_trial(mid)
            iteration_history.append({
                'iteration': idx,
                'trial_temp_F': eval_mid['trial_temp_F'],
                'mu_trial': eval_mid['mu_trial'],
                'S': eval_mid['S'],
                'epsilon': eval_mid['epsilon'],
                'fr_over_c': eval_mid['fr_over_c'],
                'delta_T_F': eval_mid['delta_T_F'],
                'T_av_F': eval_mid['T_av_F'],
                'residual_F': eval_mid['residual_F'],
                'Qs_in3_s': eval_mid['Qs_in3_s'],
                'Hloss_btu_h': eval_mid['Hloss_btu_h'],
                'torque_lbf_in': eval_mid['torque_lbf_in'],
            })
            final_eval = eval_mid
            if abs(eval_mid['residual_F']) <= self.inputs.temp_tol_F or abs(hi - lo) <= self.inputs.temp_tol_F:
                converged = True
                break
            if eval_lo['residual_F'] * eval_mid['residual_F'] <= 0.0:
                hi = mid
                eval_hi = eval_mid
            else:
                lo = mid
                eval_lo = eval_mid

        final_lookup: InterpolationResult = final_eval['lookup']
        final_state: DerivedState = final_eval['state']
        checks: Dict[str, Any] = {
            'converged': converged,
            'temperature_tolerance_F': self.inputs.temp_tol_F,
            'final_bracket_width_F': abs(hi - lo),
            'final_residual_F': final_eval['residual_F'],
            'sommerfeld_residual': final_lookup.s_residual,
        }
        if self.inputs.heat_loss_limit_btu_h is not None:
            checks['heat_loss_limit_btu_h'] = self.inputs.heat_loss_limit_btu_h
            checks['heat_loss_within_limit'] = final_eval['Hloss_btu_h'] <= self.inputs.heat_loss_limit_btu_h

        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived={
                **self._derived_from_state(final_state),
                'trial_bracket_lower_temp_F': lo,
                'trial_bracket_upper_temp_F': hi,
            },
            table_lookup=self._lookup_metadata_from_lookup(final_lookup),
            interpolated_dimensionless={
                **self._interpolated_dimensionless_from_lookup(final_lookup),
                'fr_over_c': final_eval['fr_over_c'],
            },
            outputs={
                'mu_effective': final_eval['mu_trial'],
                'T_f_avg_F': final_eval['trial_temp_F'],
                'delta_T_F': final_eval['delta_T_F'],
                'T_av_F': final_eval['T_av_F'],
                'T_sump_F': self.inputs.sump_temp_F or 0.0,
                'T_max_F': final_eval['T_max_F'],
                'h_min': final_eval['h_min'],
                'epsilon': final_eval['epsilon'],
                'phi_deg': final_eval['phi_deg'],
                'theta_cav_deg': final_eval['theta_cav_deg'],
                'P_st': final_eval['p_st'],
                'Q_side_in3_s': final_eval['Qs_in3_s'],
                'H_loss_btu_s': final_eval['Hloss_btu_s'],
                'H_loss_btu_h': final_eval['Hloss_btu_h'],
                'torque_lbf_in': final_eval['torque_lbf_in'],
                'f': final_eval['f'],
                'fr_over_c': final_eval['fr_over_c'],
                'pmax_total_psi': final_eval['pmax_total_psi'],
                'theta_max_deg': final_eval['theta_max_deg'],
            },
            checks=checks,
            notes=[
                'This route implements the pressure-fed circumferential-groove bearing workflow from Shigley Sec. 12-11 and Example 12-6.',
                'Clearance c is treated as a direct given input. The bushing diameter db is not required for the route.',
                'The characteristic load pressure uses Shigley Eq. (12-23): P_st = W / (4 r l_prime).',
                'The table lookup uses l_prime_over_d as a direct given ratio, rather than deriving it from geometry.',
                'The iterative closure condition is T_trial = T_av, where T_av = T_s + DeltaT/2.',
                'DeltaT uses Shigley Eq. (12-24) in ips form, and side flow uses Shigley Eq. (12-22).',
            ],
            iteration_history=iteration_history,
        )


PROBLEM_REGISTRY = {
    'minimum_film_thickness': MinimumFilmThicknessProblem,
    'coefficient_of_friction': CoefficientOfFrictionProblem,
    'volumetric_flow_rate': VolumetricFlowRateProblem,
    'maximum_film_pressure': MaximumFilmPressureProblem,
    'temperature_rise': TemperatureRiseProblem,
    'self_contained_steady_state': SelfContainedSteadyStateProblem,
    'pressure_fed_circumferential': PressureFedCircumferentialProblem,
}
