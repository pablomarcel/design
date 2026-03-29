from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple
import csv
import math

from utils import safe_float


@dataclass
class BearingInputs:
    mu: float
    N: float
    W: float
    r: float
    c: float
    l: float
    unit_system: str = "ips"
    Ps: float = 0.0
    notes: List[str] = field(default_factory=list)

    @property
    def d(self) -> float:
        return 2.0 * self.r

    @property
    def pressure(self) -> float:
        return self.W / (self.d * self.l)

    @property
    def sommerfeld(self) -> float:
        return (self.r / self.c) ** 2 * (self.mu * self.N / self.pressure)

    @property
    def l_over_d(self) -> float:
        return self.l / self.d

    @classmethod
    def from_mapping(cls, data: Dict[str, object]) -> "BearingInputs":
        return cls(
            mu=safe_float(data.get("mu"), "mu"),
            N=safe_float(data.get("N"), "N"),
            W=safe_float(data.get("W"), "W"),
            r=safe_float(data.get("r"), "r"),
            c=safe_float(data.get("c"), "c"),
            l=safe_float(data.get("l"), "l"),
            unit_system=str(data.get("unit_system", "ips")).strip().lower() or "ips",
            Ps=float(data.get("Ps", 0.0) or 0.0),
            notes=list(data.get("notes", [])) if isinstance(data.get("notes", []), list) else [],
        )

    def validate(self) -> None:
        for name in ("mu", "N", "W", "r", "c", "l"):
            value = getattr(self, name)
            if value <= 0.0:
                raise ValueError(f"Input '{name}' must be > 0. Received {value}.")
        if self.unit_system not in {"ips", "custom"}:
            raise ValueError("Supported unit_system values are 'ips' and 'custom'.")
        if self.Ps < 0.0:
            raise ValueError("Input 'Ps' must be >= 0.")


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
    checks: Dict[str, float | str]
    notes: List[str]


class FiniteJournalBearingTable:
    PROPERTY_COLUMNS = (
        "S",
        "Qbar_L",
        "Qbar_i",
        "RC_over_C_times_f",
        "Pbar_max",
        "theta_max_deg",
        "phi_deg",
        "theta_cav_deg",
    )

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)
        self.rows = self._load_rows(self.csv_path)
        self.l_over_d_values = sorted({row["L_over_D"] for row in self.rows})
        self.epsilon_values = sorted({row["epsilon"] for row in self.rows})
        self._grid: Dict[float, Dict[float, Dict[str, float]]] = {}
        for row in self.rows:
            self._grid.setdefault(row["L_over_D"], {})[row["epsilon"]] = row

    def _load_rows(self, path: Path) -> List[Dict[str, float]]:
        rows: List[Dict[str, float]] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = {k: float(v) if k != "L_over_D_label" else v for k, v in raw.items()}
                rows.append(row)  # type: ignore[arg-type]
        if not rows:
            raise ValueError(f"No rows found in finite journal-bearing table: {path}")
        return rows

    @staticmethod
    def _bracket(value: float, grid: List[float]) -> Tuple[float, float, bool]:
        if value < grid[0] or value > grid[-1]:
            raise ValueError(
                f"Requested value {value} is outside the table range [{grid[0]}, {grid[-1]}]."
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
        s_at_lo = self.interpolate_property(l_over_d, eps_lo, "S")
        s_at_hi = self.interpolate_property(l_over_d, eps_hi, "S")
        s_max = max(s_at_lo, s_at_hi)
        s_min = min(s_at_lo, s_at_hi)
        if not (s_min <= target_s <= s_max):
            raise ValueError(
                f"Sommerfeld number {target_s} is outside the table-supported range [{s_min}, {s_max}] for L/D={l_over_d}."
            )
        lo = eps_lo
        hi = eps_hi
        flo = self.interpolate_property(l_over_d, lo, "S") - target_s
        fhi = self.interpolate_property(l_over_d, hi, "S") - target_s
        if abs(flo) <= tol:
            props = self.interpolate_all(l_over_d, lo)
            e0, e1, e_exact = self._bracket(lo, self.epsilon_values)
            return InterpolationResult(lo, props, (l0, l1), (e0, e1), l_exact, e_exact, flo, 0)
        if abs(fhi) <= tol:
            props = self.interpolate_all(l_over_d, hi)
            e0, e1, e_exact = self._bracket(hi, self.epsilon_values)
            return InterpolationResult(hi, props, (l0, l1), (e0, e1), l_exact, e_exact, fhi, 0)
        if flo * fhi > 0.0:
            raise ValueError(
                "Could not bracket epsilon from the table. Check the requested operating point."
            )
        mid = 0.5 * (lo + hi)
        fmid = self.interpolate_property(l_over_d, mid, "S") - target_s
        iterations = 0
        while iterations < max_iter:
            mid = 0.5 * (lo + hi)
            fmid = self.interpolate_property(l_over_d, mid, "S") - target_s
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
    problem_name: str = "base"
    title: str = "Base Problem"

    def __init__(self, inputs: BearingInputs, table: FiniteJournalBearingTable):
        self.inputs = inputs
        self.inputs.validate()
        self.table = table
        self.state = DerivedState(
            P=self.inputs.pressure,
            S=self.inputs.sommerfeld,
            l_over_d=self.inputs.l_over_d,
            r_over_c=self.inputs.r / self.inputs.c,
        )
        self.lookup = self.table.epsilon_from_sommerfeld(self.state.l_over_d, self.state.S)

    def base_inputs(self) -> Dict[str, object]:
        return {
            "mu": self.inputs.mu,
            "N": self.inputs.N,
            "W": self.inputs.W,
            "r": self.inputs.r,
            "c": self.inputs.c,
            "l": self.inputs.l,
            "d": self.inputs.d,
            "Ps": self.inputs.Ps,
            "unit_system": self.inputs.unit_system,
        }

    def base_derived(self) -> Dict[str, float]:
        return {
            "P": self.state.P,
            "S": self.state.S,
            "l_over_d": self.state.l_over_d,
            "r_over_c": self.state.r_over_c,
        }

    def lookup_metadata(self) -> Dict[str, object]:
        return {
            "table_source": str(self.table.csv_path),
            "l_over_d_lower": self.lookup.l_over_d_bounds[0],
            "l_over_d_upper": self.lookup.l_over_d_bounds[1],
            "epsilon_lower": self.lookup.epsilon_bounds[0],
            "epsilon_upper": self.lookup.epsilon_bounds[1],
            "l_over_d_exact": self.lookup.l_over_d_exact,
            "epsilon_exact": self.lookup.epsilon_exact,
            "solver": "bilinear interpolation in (L/D, epsilon) + bisection on epsilon from Sommerfeld number",
            "iterations": self.lookup.iterations,
        }

    def interpolated_dimensionless(self) -> Dict[str, float]:
        props = dict(self.lookup.properties)
        props["epsilon"] = self.lookup.epsilon
        return props

    def solve(self) -> SolveResult:
        raise NotImplementedError


class MinimumFilmThicknessProblem(BaseProblem):
    problem_name = "minimum_film_thickness"
    title = "Minimum Film Thickness: automated table lookup via finite journal-bearing dataset"

    def solve(self) -> SolveResult:
        eps = self.lookup.epsilon
        h_min = self.inputs.c * (1.0 - eps)
        e = self.inputs.c * eps
        phi_deg = self.lookup.properties["phi_deg"]
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            table_lookup=self.lookup_metadata(),
            interpolated_dimensionless=self.interpolated_dimensionless(),
            outputs={
                "h_min": h_min,
                "e": e,
                "phi_deg": phi_deg,
                "theta_cav_deg": self.lookup.properties["theta_cav_deg"],
            },
            checks={
                "h_min_over_c_minus_1_minus_epsilon": (h_min / self.inputs.c) - (1.0 - eps),
                "sommerfeld_residual": self.lookup.s_residual,
            },
            notes=[
                "This route now uses the finite_journal_bearing.csv dataset instead of manual chart entry.",
                "Minimum film thickness is computed with Khonsari Eq. (8.41): h_min = C(1 - epsilon).",
                "Attitude angle phi is taken directly from the interpolated table values.",
                "theta_cav_deg is included as an extra dataset output, even though Shigley Example 12-1 does not use it.",
            ],
        )


class CoefficientOfFrictionProblem(BaseProblem):
    problem_name = "coefficient_of_friction"
    title = "Coefficient of Friction: automated table lookup via finite journal-bearing dataset"

    def solve(self) -> SolveResult:
        rcf = self.lookup.properties["RC_over_C_times_f"]
        f = rcf * self.inputs.c / self.inputs.r
        friction_force_lbf = f * self.inputs.W
        torque_lbf_in = friction_force_lbf * self.inputs.r
        power_in_lbf_s = friction_force_lbf * (2.0 * math.pi * self.inputs.r * self.inputs.N)
        outputs: Dict[str, float] = {
            "f": f,
            "friction_force_lbf": friction_force_lbf,
            "torque_lbf_in": torque_lbf_in,
            "power_in_lbf_s": power_in_lbf_s,
        }
        checks: Dict[str, float | str] = {
            "torque_minus_fWr": torque_lbf_in - (f * self.inputs.W * self.inputs.r),
            "sommerfeld_residual": self.lookup.s_residual,
        }
        notes = [
            "The table column RC_over_C_times_f is interpreted as (R/C)f.",
            "Friction coefficient is recovered from f = [(R/C)f] * (C/R).",
            "Power loss is computed from Khonsari Eq. (8.43): E_p = F 2 pi R N_s.",
        ]
        if self.inputs.unit_system == "ips":
            outputs["power_loss_hp"] = power_in_lbf_s / 6600.0
            outputs["heat_loss_btu_s"] = power_in_lbf_s / (778.0 * 12.0)
            notes.append("ips conversions: 1 hp = 6600 in·lbf/s and 1 Btu = 778 ft·lbf.")
        else:
            checks["power_conversion"] = "Skipped because unit_system != 'ips'."
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            table_lookup=self.lookup_metadata(),
            interpolated_dimensionless=self.interpolated_dimensionless(),
            outputs=outputs,
            checks=checks,
            notes=notes,
        )


class VolumetricFlowRateProblem(BaseProblem):
    problem_name = "volumetric_flow_rate"
    title = "Volumetric Flow Rate: automated table lookup via finite journal-bearing dataset"

    def solve(self) -> SolveResult:
        qbar_l = self.lookup.properties["Qbar_L"]
        qbar_i = self.lookup.properties["Qbar_i"]
        scale = (math.pi / 2.0) * self.inputs.N * self.inputs.d * self.inputs.l * self.inputs.c
        q_leakage = qbar_l * scale
        q_inlet = qbar_i * scale
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            table_lookup=self.lookup_metadata(),
            interpolated_dimensionless=self.interpolated_dimensionless(),
            outputs={
                "Q_leakage": q_leakage,
                "Q_inlet": q_inlet,
                "Q_total_shigley_equivalent": q_inlet,
                "Q_side_shigley_equivalent": q_leakage,
                "Q_recirculated": q_inlet - q_leakage,
            },
            checks={
                "sommerfeld_residual": self.lookup.s_residual,
            },
            notes=[
                "Leakage flow is computed with Khonsari Eq. (8.39): Q_L = Qbar_L * (pi/2) * N_s D L C.",
                "Inlet flow is computed with Khonsari Eq. (8.40): Q_i = Qbar_i * (pi/2) * N_s D L C.",
                "For the Shigley-style Example 12-3 comparison, Q_i matches the total flow and Q_L matches the side flow.",
            ],
        )


class MaximumFilmPressureProblem(BaseProblem):
    problem_name = "maximum_film_pressure"
    title = "Maximum Film Pressure: automated table lookup via finite journal-bearing dataset"

    def solve(self) -> SolveResult:
        pbar_max = self.lookup.properties["Pbar_max"]
        pmax = self.inputs.mu * self.inputs.N * (self.inputs.r / self.inputs.c) ** 2 * pbar_max + self.inputs.Ps
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            table_lookup=self.lookup_metadata(),
            interpolated_dimensionless=self.interpolated_dimensionless(),
            outputs={
                "pmax": pmax,
                "theta_max_deg": self.lookup.properties["theta_max_deg"],
                "phi_deg": self.lookup.properties["phi_deg"],
                "theta_cav_deg": self.lookup.properties["theta_cav_deg"],
            },
            checks={
                "sommerfeld_residual": self.lookup.s_residual,
            },
            notes=[
                "Maximum pressure is computed from the dimensionless pressure definition used with Khonsari Eq. (8.36).",
                "For the current non-pressure-fed scope, supply pressure Ps is normally zero.",
                "theta_p0 is not reported because the finite_journal_bearing.csv dataset does not provide Shigley's terminating-pressure angle directly.",
                "The angle frame of reference follows the Khonsari table, so direct numerical comparison to Shigley's theta values may differ.",
            ],
        )


PROBLEM_REGISTRY = {
    "minimum_film_thickness": MinimumFilmThicknessProblem,
    "coefficient_of_friction": CoefficientOfFrictionProblem,
    "volumetric_flow_rate": VolumetricFlowRateProblem,
    "maximum_film_pressure": MaximumFilmPressureProblem,
}
