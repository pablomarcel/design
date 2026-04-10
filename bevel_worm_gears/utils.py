from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


class BevelWormGearError(Exception):
    pass


@dataclass
class ChartPoint:
    x: float
    y: float
    z: float


class GridInterpolator2D:
    """Simple inverse-distance interpolation for sparse digitized chart data."""

    def __init__(self, points: Iterable[ChartPoint]):
        self.points = list(points)
        if not self.points:
            raise BevelWormGearError("Interpolator requires at least one point.")

    def interpolate(self, x: float, y: float, *, power: float = 2.0, k: int = 8) -> float:
        exact = [p.z for p in self.points if abs(p.x - x) < 1e-12 and abs(p.y - y) < 1e-12]
        if exact:
            return exact[0]
        ranked: List[Tuple[float, ChartPoint]] = []
        for p in self.points:
            d2 = (p.x - x) ** 2 + (p.y - y) ** 2
            ranked.append((d2, p))
        ranked.sort(key=lambda item: item[0])
        chosen = ranked[: max(1, min(k, len(ranked)))]
        num = 0.0
        den = 0.0
        for d2, p in chosen:
            d = math.sqrt(max(d2, 1e-18))
            w = 1.0 / (d**power)
            num += w * p.z
            den += w
        return num / den


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def to_float(value: Any, *, field: str = "") -> float:
    if value is None or value == "":
        raise BevelWormGearError(f"Missing numeric value for field '{field}'.")
    return float(value)


def log10(x: float) -> float:
    return math.log10(x)


def rpm_to_pitchline_velocity_ft_min(diameter_in: float, rpm: float) -> float:
    return math.pi * diameter_in * rpm / 12.0


def hp_from_tangential_force(force_lbf: float, velocity_ft_min: float) -> float:
    return force_lbf * velocity_ft_min / 33000.0


def tangential_force_from_hp(hp: float, velocity_ft_min: float) -> float:
    return hp * 33000.0 / velocity_ft_min


def qv_B(qv: float) -> float:
    return 0.25 * (12.0 - qv) ** (2.0 / 3.0)


def qv_A(qv: float) -> float:
    b = qv_B(qv)
    return 50.0 + 56.0 * (1.0 - b)


def dynamic_factor_kv(qv: float, velocity_ft_min: float) -> Dict[str, float]:
    b = qv_B(qv)
    a = qv_A(qv)
    kv = ((a + math.sqrt(velocity_ft_min)) / a) ** b
    vt_max = (a + (qv - 3.0)) ** 2
    return {"B": b, "A": a, "K_v": kv, "v_t_max_ft_per_min": vt_max, "valid": velocity_ft_min < vt_max}


def overload_factor_ko(table_rows: List[Dict[str, str]], prime_mover: str, driven_machine: str, *, speed_increasing_ratio: Optional[float] = None) -> float:
    pm_key = prime_mover.strip().lower()
    dm_key = driven_machine.strip().lower().replace("-", " ")
    mapping = {
        "uniform": "driven_machine_uniform",
        "light shock": "driven_machine_light_shock",
        "medium shock": "driven_machine_medium_shock",
        "heavy shock": "driven_machine_heavy_shock",
    }
    for row in table_rows:
        if row["character_of_prime_mover"].strip().lower() == pm_key:
            raw = row[mapping[dm_key]].replace(" or higher", "")
            value = float(raw)
            if speed_increasing_ratio is not None:
                value += 0.01 * (speed_increasing_ratio**2)
            return value
    raise BevelWormGearError(f"Could not find K_o for prime mover='{prime_mover}', driven machine='{driven_machine}'.")


def size_factor_bending_kx() -> float:
    return 1.0


def size_factor_ks(pd: float) -> float:
    return 0.4867 + 0.2132 / pd


def crowning_factor_cxc(crowned: bool) -> float:
    """Eq. (15-12), crowning factor for pitting.

    Properly crowned teeth use 1.5.
    Uncrowned or larger teeth use 2.0.
    """
    return 1.5 if crowned else 2.0


def size_factor_pitting_cs(face_width_in: float) -> float:
    if face_width_in < 0.5:
        return 0.5
    if face_width_in > 4.5:
        return 1.0
    return 0.125 * face_width_in + 0.4375


def mounting_factor_kmb(mounting: str) -> float:
    key = mounting.strip().lower()
    table = {
        "both members straddle-mounted": 1.00,
        "one member straddle-mounted": 1.10,
        "neither member straddle-mounted": 1.25,
        "outboard": 1.25,
        "outboard mounting": 1.25,
    }
    if key not in table:
        raise BevelWormGearError(f"Unknown mounting configuration '{mounting}'.")
    return table[key]


def load_distribution_factor_km(face_width_in: float, mounting: str) -> Dict[str, float]:
    kmb = mounting_factor_kmb(mounting)
    km = kmb + 0.0036 * face_width_in**2
    return {"K_mb": kmb, "K_m": km}


def life_factor_cl(cycles: float) -> float:
    if cycles <= 1.0e4:
        return 2.0
    return 3.4822 * cycles ** (-0.0602)


def life_factor_kl(cycles: float, *, branch: str = "general") -> float:
    branch = branch.strip().lower()
    if branch == "general":
        if cycles <= 1.0e3:
            return 2.7
        return 1.683 * cycles ** (-0.0323)
    if branch in {"critical_upper", "upper", "critical-upper"}:
        if cycles <= 1.0e3:
            return 2.7
        if cycles < 1.0e7:
            return 6.1514 * cycles ** (-0.1192)
        return 1.3558 * cycles ** (-0.0178)
    if branch in {"critical_lower", "lower", "critical-lower"}:
        if cycles <= 1.0e3:
            return 2.7
        if cycles < 3.0e6:
            return 6.1514 * cycles ** (-0.1192)
        return 1.683 * cycles ** (-0.0323)
    raise BevelWormGearError(f"Unknown K_L branch '{branch}'.")


def temperature_factor_kt(temperature_f: float) -> float:
    return 1.0 if 32.0 <= temperature_f <= 250.0 else (460.0 + temperature_f) / 710.0


def reliability_factor_kr(reliability: float) -> Dict[str, float]:
    if 0.99 <= reliability <= 0.999:
        kr = 0.50 - 0.25 * log10(1.0 - reliability)
    elif 0.9 <= reliability < 0.99:
        kr = 0.70 - 0.15 * log10(1.0 - reliability)
    else:
        raise BevelWormGearError("Reliability must be within 0.9 <= R <= 0.999 for these Shigley formulas.")
    return {"K_R": kr, "C_R": math.sqrt(kr)}


def hardness_ratio_factor_ch(*, pinion_hb: float, gear_hb: float, ratio_n_over_n: float, case_hardened_pinion: bool = False, pinion_surface_finish_um: Optional[float] = None) -> Dict[str, Any]:
    ratio = pinion_hb / gear_hb
    if ratio < 1.2:
        return {"hardness_ratio": ratio, "C_H": 1.0, "method": "ratio_below_1.2_set_to_1"}
    if case_hardened_pinion:
        if pinion_surface_finish_um is None:
            raise BevelWormGearError("pinion_surface_finish_um is required for Eq. (15-17).")
        b2 = 0.00075 * math.exp(-0.0122 * pinion_surface_finish_um)
        ch = 1.0 + b2 * (450.0 - gear_hb)
        return {"hardness_ratio": ratio, "B2": b2, "C_H": ch, "method": "eq_15_17"}
    if ratio <= 1.7:
        b1 = 0.00898 * ratio - 0.00829
        ch = 1.0 + b1 * (ratio_n_over_n - 1.0)
        return {"hardness_ratio": ratio, "B1": b1, "C_H": ch, "method": "eq_15_16"}
    return {"hardness_ratio": ratio, "C_H": 1.0, "method": "ratio_above_1.7_not_modeled_set_to_1"}


def elastic_coefficient_cp_steel_default() -> float:
    return 2290.0


def round_up(value: float, increment: float) -> float:
    return math.ceil(value / increment) * increment


def worm_mesh_design_comparison_rows(result: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    iterations = result.get("iterations", {})
    if not isinstance(iterations, Mapping):
        return rows

    axial_trials = iterations.get("axial_pitch_trials", [])
    if not isinstance(axial_trials, list):
        return rows

    selected = result.get("selected_design", {})
    selected_px = selected.get("candidate_axial_pitch_p_x_in")
    selected_d = selected.get("candidate_d_in")

    for axial in axial_trials:
        if not isinstance(axial, Mapping):
            continue
        for trial in axial.get("worm_pitch_diameter_trials", []):
            if not isinstance(trial, Mapping):
                continue

            geom = trial.get("geometry", {})
            cap = trial.get("capacity", {})
            thermal = trial.get("thermal", {})
            bending = trial.get("bending", {})
            forces = trial.get("forces_and_powers", {})

            px = trial.get("candidate_axial_pitch_p_x_in")
            d = trial.get("candidate_d_in")
            scenario_label = f"p_x={px}, d={d}"
            is_selected = (
                selected_px is not None
                and selected_d is not None
                and abs(float(px) - float(selected_px)) < 1e-12
                and abs(float(d) - float(selected_d)) < 1e-12
            )

            rows.append(
                {
                    "scenario": scenario_label,
                    "selected": "*" if is_selected else "",
                    "p_x_in": px,
                    "d_in": d,
                    "lambda_deg": geom.get("lead_angle_lambda_deg"),
                    "lambda_max_deg": geom.get("lambda_max_deg"),
                    "lead_ok": geom.get("lead_angle_ok"),
                    "F_e_req_in": cap.get("effective_face_width_required_F_e_req_in"),
                    "F_e_sel_in": cap.get("effective_face_width_selected_in"),
                    "F_e_max_in": cap.get("effective_face_width_max_in"),
                    "W_G_t_lbf": forces.get("gear_tangential_force_W_G_t_lbf"),
                    "W_t_all_lbf": cap.get("allowable_tangential_force_W_t_all_lbf"),
                    "capacity_margin_lbf": cap.get("excess_capacity_margin_lbf"),
                    "t_s_F": thermal.get("sump_temperature_with_actual_area_F"),
                    "sigma_psi": bending.get("sigma_gear_psi"),
                    "pass": trial.get("meets_design"),
                    "failure_reasons": "; ".join(trial.get("failure_reasons", [])),
                }
            )
    return rows


def render_worm_mesh_design_comparison_table(result: Mapping[str, Any]) -> bool:
    rows = worm_mesh_design_comparison_rows(result)
    if not rows:
        return False

    try:
        import pandas as pd
        from rich.console import Console
        from rich.table import Table
    except Exception:
        return False

    df = pd.DataFrame(rows)
    if df.empty:
        return False

    scenario_cols = []
    for _, row in df.iterrows():
        label = row["scenario"]
        if row["selected"] == "*":
            label = f"{label} *"
        scenario_cols.append(label)

    metric_order = [
        ("p_x_in", "p_x [in]"),
        ("d_in", "d [in]"),
        ("lambda_deg", "lambda [deg]"),
        ("lambda_max_deg", "lambda_max [deg]"),
        ("lead_ok", "lead ok"),
        ("F_e_req_in", "F_e_req [in]"),
        ("F_e_sel_in", "F_e_selected [in]"),
        ("F_e_max_in", "F_e_max [in]"),
        ("W_G_t_lbf", "W_G_t [lbf]"),
        ("W_t_all_lbf", "W_t_all [lbf]"),
        ("capacity_margin_lbf", "capacity margin [lbf]"),
        ("t_s_F", "sump temp [F]"),
        ("sigma_psi", "sigma [psi]"),
        ("pass", "meets design"),
        ("failure_reasons", "failure reasons"),
    ]

    def fmt_value(key: str, value: Any) -> str:
        if value is None:
            return ""
        if key in {"lead_ok", "pass"}:
            return "yes" if bool(value) else "no"
        if key == "failure_reasons":
            return str(value)
        try:
            return f"{float(value):.3f}"
        except Exception:
            return str(value)

    table = Table(title=f"Worm Mesh Design Scenario Comparison ({len(rows)} scenarios)")
    table.add_column("Metric", style="bold")
    for col in scenario_cols:
        table.add_column(col)

    for key, label in metric_order:
        row_values = [fmt_value(key, row.get(key)) for row in rows]
        table.add_row(label, *row_values)

    Console().print(table)
    return True
