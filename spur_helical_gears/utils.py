from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence


PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
IN_DIR = PACKAGE_DIR / "in"
OUT_DIR = PACKAGE_DIR / "out"


class DataRepository:
    """Loads digitized CSV/JSON assets used by the gear solvers."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._cache: dict[str, Any] = {}

    def csv_rows(self, filename: str) -> list[dict[str, str]]:
        key = f"csv::{filename}"
        if key not in self._cache:
            path = self.data_dir / filename
            with path.open("r", encoding="utf-8", newline="") as f:
                self._cache[key] = list(csv.DictReader(f))
        return list(self._cache[key])

    def json_data(self, filename: str) -> dict[str, Any]:
        key = f"json::{filename}"
        if key not in self._cache:
            path = self.data_dir / filename
            with path.open("r", encoding="utf-8") as f:
                self._cache[key] = json.load(f)
        return dict(self._cache[key])


class GearMath:
    @staticmethod
    def interp1(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
        if len(xs) != len(ys):
            raise ValueError("xs and ys must have the same length")
        if len(xs) < 2:
            raise ValueError("Need at least two points for interpolation")
        pairs = sorted(zip(xs, ys), key=lambda p: p[0])
        xs_sorted = [p[0] for p in pairs]
        ys_sorted = [p[1] for p in pairs]
        if x <= xs_sorted[0]:
            return float(ys_sorted[0])
        if x >= xs_sorted[-1]:
            return float(ys_sorted[-1])
        for i in range(len(xs_sorted) - 1):
            x0, x1 = xs_sorted[i], xs_sorted[i + 1]
            if x0 <= x <= x1:
                y0, y1 = ys_sorted[i], ys_sorted[i + 1]
                if x1 == x0:
                    return float(y0)
                return float(y0 + (y1 - y0) * ((x - x0) / (x1 - x0)))
        raise RuntimeError("Interpolation interval not found")

    @staticmethod
    def bilinear_interpolate(
        x: float,
        y: float,
        x_values: Sequence[float],
        y_values: Sequence[float],
        z_grid: dict[tuple[float, float], float],
    ) -> float:
        x0, x1 = GearMath.bracket(x, x_values)
        y0, y1 = GearMath.bracket(y, y_values)
        if x0 == x1 and y0 == y1:
            return float(z_grid[(x0, y0)])
        if x0 == x1:
            return GearMath.interp1(
                y,
                [y0, y1],
                [z_grid[(x0, y0)], z_grid[(x0, y1)]],
            )
        if y0 == y1:
            return GearMath.interp1(
                x,
                [x0, x1],
                [z_grid[(x0, y0)], z_grid[(x1, y0)]],
            )
        z00 = z_grid[(x0, y0)]
        z10 = z_grid[(x1, y0)]
        z01 = z_grid[(x0, y1)]
        z11 = z_grid[(x1, y1)]
        tx = (x - x0) / (x1 - x0)
        ty = (y - y0) / (y1 - y0)
        z0 = z00 + (z10 - z00) * tx
        z1 = z01 + (z11 - z01) * tx
        return float(z0 + (z1 - z0) * ty)

    @staticmethod
    def bracket(value: float, grid: Sequence[float]) -> tuple[float, float]:
        ordered = sorted(float(v) for v in grid)
        if value <= ordered[0]:
            return ordered[0], ordered[0]
        if value >= ordered[-1]:
            return ordered[-1], ordered[-1]
        for i in range(len(ordered) - 1):
            a, b = ordered[i], ordered[i + 1]
            if a <= value <= b:
                return a, b
        raise RuntimeError("Bracket not found")

    @staticmethod
    def round_up_to_increment(value: float, increment: float) -> float:
        return math.ceil(value / increment) * increment

    @staticmethod
    def safe_ln(value: float) -> float:
        if value <= 0:
            raise ValueError(f"Natural log undefined for non-positive value: {value}")
        return math.log(value)


class GearDataLookup:
    def __init__(self, repo: DataRepository | None = None) -> None:
        self.repo = repo or DataRepository()

    def overload_factor(self, power_source: str, driven_machine: str) -> float:
        ps = slugify(power_source)
        dm = slugify(driven_machine)
        for row in self.repo.csv_rows("overload_factors.csv"):
            if row["power_source"] == ps and row["driven_machine"] == dm:
                return float(row["K_o"])
        raise KeyError(f"No overload factor for power_source={power_source!r}, driven_machine={driven_machine!r}")

    def lewis_form_factor(self, number_of_teeth: float) -> float:
        rows = self.repo.csv_rows("table_14_2.csv")
        xs = [float(r["number_of_teeth"]) for r in rows if r["number_of_teeth"].lower() != "rack"]
        ys = [float(r["Y"]) for r in rows if r["number_of_teeth"].lower() != "rack"]
        return GearMath.interp1(float(number_of_teeth), xs, ys)

    def cp_for_material_pair(self, pinion_material: str, gear_material: str) -> float:
        pm = normalize_material_name(pinion_material)
        gm = normalize_material_name(gear_material)
        for row in self.repo.csv_rows("table_14_8.csv"):
            if normalize_material_name(row["pinion_material"]) == pm and normalize_material_name(row["gear_material"]) == gm:
                return float(row["Cp_sqrt_psi"])
        raise KeyError(f"No C_p row for pinion_material={pinion_material!r}, gear_material={gear_material!r}")

    def reliability_factor(self, reliability: float) -> float:
        reliability = float(reliability)
        table_rows: list[dict[str, str]] = []
        table_path = self.repo.data_dir / "table_14_10.csv"
        if table_path.exists():
            table_rows = self.repo.csv_rows("table_14_10.csv")

        # Per Shigley's stated policy: use cardinal table values when available,
        # and only fall back to Eq. 14-38 / Eq. 14-39 for values in between.
        for row in table_rows:
            if abs(float(row["reliability"]) - reliability) < 1e-12:
                return float(row["K_R"])

        if 0.5 < reliability < 0.99:
            return float(0.658 - 0.0759 * math.log(1.0 - reliability))
        if 0.99 < reliability <= 0.9999:
            return float(0.50 - 0.109 * math.log(1.0 - reliability))
        if abs(reliability - 0.99) < 1e-12 and table_rows:
            # Defensive fallback in case a user has a malformed table or deletes the row.
            return 1.0
        raise ValueError("Reliability must be in 0.5 < R <= 0.9999")

    def hardness_scale_hb_from_hrc(self, hrc: float) -> float:
        rows = self.repo.csv_rows("hardness_scale.csv")
        xs = [float(r["HRC"]) for r in rows]
        ys = [float(r["HB"]) for r in rows]
        return GearMath.interp1(float(hrc), xs, ys)

    def hardness_scale_hb_midrange_from_hrc_range(self, low_hrc: float, high_hrc: float) -> float:
        low_hb = self.hardness_scale_hb_from_hrc(low_hrc)
        high_hb = self.hardness_scale_hb_from_hrc(high_hrc)
        return 0.5 * (low_hb + high_hb)

    def nitriding_material_row(self, material_name: str) -> dict[str, str]:
        key = normalize_material_name(material_name)
        for row in self.repo.csv_rows("table_14_5.csv"):
            if normalize_material_name(row["steel"].replace("*", "")) == key:
                return row
        raise KeyError(f"No row for nitriding material {material_name!r}")

    def bending_strength_from_figure(self, figure_file: str, equation_key: str, hb: float) -> float:
        data = self.repo.json_data(figure_file)
        expr = data["equations"][equation_key]["us_customary"]["equation"]
        return evaluate_linear_expression(expr, {"H_B": hb})

    def contact_strength_from_figure(self, figure_file: str, equation_key: str, hb: float) -> float:
        data = self.repo.json_data(figure_file)
        expr = data["equations"][equation_key]["us_customary"]["equation"]
        return evaluate_linear_expression(expr, {"H_B": hb})

    def y_n(self, cycles: float, selection: str = "upper") -> float:
        data = self.repo.json_data("figure_14_14.json")
        curves = data["regions"]["high_cycle_shaded_region"]
        expr = curves[selection]["equation"]
        return evaluate_power_expression(expr, {"N": cycles})

    def z_n(self, cycles: float, selection: str = "upper") -> float:
        data = self.repo.json_data("figure_14_15.json")
        curves = data["regions"]["high_cycle_shaded_region"]
        expr = curves[selection]["equation"]
        return evaluate_power_expression(expr, {"N": cycles})

    def spur_j(self, desired_teeth: float, mating_teeth: float) -> float:
        data = self.repo.json_data("figure_14_6.json")
        curves = data["digitized_curves"]
        grid: dict[tuple[float, float], float] = {}
        x_values: set[float] = set()
        y_values: set[float] = set()
        for name, points in curves.items():
            if name == "load_applied_at_tip_of_tooth":
                continue
            mate = float(name.split("_")[-1])
            y_values.add(mate)
            for pt in points:
                n = float(pt["N"])
                x_values.add(n)
                grid[(n, mate)] = float(pt["J"])
        return GearMath.bilinear_interpolate(desired_teeth, mating_teeth, sorted(x_values), sorted(y_values), grid)

    def helical_j_prime(self, helix_angle_deg: float, number_of_teeth: float) -> float:
        data = self.repo.json_data("figure_14_7.json")
        curves = data["digitized_curves"]
        grid: dict[tuple[float, float], float] = {}
        angle_values: set[float] = set()
        tooth_values: set[float] = set()
        for name, points in curves.items():
            teeth = float(name.split("_")[-1])
            tooth_values.add(teeth)
            for pt in points:
                angle = float(pt["helix_angle_deg"])
                angle_values.add(angle)
                grid[(angle, teeth)] = float(pt["J_prime"])
        return GearMath.bilinear_interpolate(helix_angle_deg, number_of_teeth, sorted(angle_values), sorted(tooth_values), grid)

    def helical_j_multiplier(self, helix_angle_deg: float, mating_teeth: float) -> float:
        data = self.repo.json_data("figure_14_8.json")
        curves = data["digitized_curves"]
        grid: dict[tuple[float, float], float] = {}
        angle_values: set[float] = set()
        tooth_values: set[float] = set()
        for name, points in curves.items():
            teeth = float(name.split("_")[-1])
            tooth_values.add(teeth)
            for pt in points:
                angle = float(pt["helix_angle_deg"])
                angle_values.add(angle)
                grid[(angle, teeth)] = float(pt["modifier"])
        return GearMath.bilinear_interpolate(helix_angle_deg, mating_teeth, sorted(angle_values), sorted(tooth_values), grid)


class ResultBuilder:
    def __init__(self) -> None:
        self.lookups: dict[str, Any] = {}
        self.derived: dict[str, Any] = {}
        self.outputs: dict[str, Any] = {}
        self.iterations: list[dict[str, Any]] = []

    def add_lookup(self, key: str, value: Any) -> None:
        self.lookups[key] = value

    def add_derived(self, key: str, value: Any) -> None:
        self.derived[key] = value

    def add_output(self, key: str, value: Any) -> None:
        self.outputs[key] = value


def normalize_material_name(name: str) -> str:
    return " ".join(
        name.lower()
        .replace("%", " percent ")
        .replace("-", " ")
        .replace("_", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace(",", " ")
        .replace("*", " ")
        .split()
    )


def slugify(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def evaluate_linear_expression(expr: str, variables: dict[str, float]) -> float:
    safe_globals = {"__builtins__": {}}
    safe_locals = dict(variables)
    expr2 = expr.split("=", 1)[1].strip() if "=" in expr else expr
    return float(eval(expr2, safe_globals, safe_locals))


def evaluate_power_expression(expr: str, variables: dict[str, float]) -> float:
    safe_globals = {"__builtins__": {}}
    safe_locals = dict(variables)
    expr2 = expr.split("=", 1)[1].strip() if "=" in expr else expr
    return float(eval(expr2, safe_globals, safe_locals))


def float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def parse_range_text(value: str) -> tuple[float, float]:
    cleaned = value.replace("–", "-").replace("—", "-").replace(" ", "")
    low, high = cleaned.split("-")
    return float(low), float(high)


def pretty_float(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def ensure_out_dir() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR
