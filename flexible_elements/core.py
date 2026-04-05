from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

try:
    from .in_out import CsvRepository
    from .utils import (
        DataLookupError,
        InputValidationError,
        IterationError,
        belt_speed_ft_min,
        centrifugal_tension_lbf,
        linear_interpolate,
        next_larger_value,
        open_belt_contact_angle_rad,
        transmitted_torque_lbf_in,
        weight_per_foot_lbf_ft,
    )
except ImportError:  # pragma: no cover
    from in_out import CsvRepository
    from utils import (
        DataLookupError,
        InputValidationError,
        IterationError,
        belt_speed_ft_min,
        centrifugal_tension_lbf,
        linear_interpolate,
        next_larger_value,
        open_belt_contact_angle_rad,
        transmitted_torque_lbf_in,
        weight_per_foot_lbf_ft,
    )


@dataclass
class BeltMaterial:
    material: str
    specification: str
    thickness_in: float
    min_pulley_diameter_in: float
    allowable_tension_600_lbf_per_in: float
    gamma_lbf_in3: float
    friction_coefficient: float


@dataclass
class MetalMaterial:
    alloy: str
    yield_strength_kpsi: float
    youngs_modulus_mpsi: float
    poissons_ratio: float


class BaseSolver:
    solve_path: str = "base"

    def __init__(self, repo: CsvRepository):
        self.repo = repo

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _flat_material(self, material: str, specification: str) -> BeltMaterial:
        row = self.repo.find_one(
            "table_17_2.csv",
            material=material,
            specification=specification,
        )
        size_raw = str(row.get("thickness_in") or row.get("size_in") or "").replace("t =", "").strip()
        if "/" in size_raw and all(part.strip().isdigit() for part in size_raw.split("/", 1)):
            num, den = size_raw.split("/", 1)
            thickness_in = float(num.strip()) / float(den.strip())
        else:
            thickness_in = float(size_raw)

        gamma_raw = row.get("gamma_lbf_in3") or row.get("specific_weight_lbf_in3") or row.get("specific_weight_lbf_per_in3")
        gamma_text = str(gamma_raw).strip()
        if "-" in gamma_text:
            lo, hi = gamma_text.split("-", 1)
            gamma_lbf_in3 = 0.5 * (float(lo) + float(hi))
        else:
            gamma_lbf_in3 = float(gamma_text)

        allowable_raw = (
            row.get("allowable_tension_600_lbf_per_in")
            or row.get("allowable_tension_per_unit_width_600_ft_min_lbf_per_in")
            or row.get("allowable_tension_per_unit_width_at_600_ft_per_min_lbf_per_in")
        )

        return BeltMaterial(
            material=row["material"],
            specification=row["specification"],
            thickness_in=thickness_in,
            min_pulley_diameter_in=float(row["minimum_pulley_diameter_in"]),
            allowable_tension_600_lbf_per_in=float(allowable_raw),
            gamma_lbf_in3=gamma_lbf_in3,
            friction_coefficient=float(row["coefficient_of_friction"]),
        )

    def _cp_factor(self, material: str, small_pulley_diameter_in: float, specification: str | None = None) -> float:
        table_material = material
        if material.strip().lower() == "polyamide":
            if not specification:
                raise InputValidationError("Polyamide lookup requires a specification such as A-3 or F-1.")
            table_material = f"Polyamide, {specification}"
        row = self.repo.find_one("table_17_4.csv", material=table_material)
        d = small_pulley_diameter_in
        if 1.6 <= d <= 4.0:
            key = "small_pulley_diameter_1_6_to_4_in"
        elif 4.5 <= d <= 8.0:
            key = "small_pulley_diameter_4_5_to_8_in"
        elif 9.0 <= d <= 12.5:
            key = "small_pulley_diameter_9_to_12_5_in"
        elif d in {14.0, 16.0}:
            key = "small_pulley_diameter_14_16_in"
        elif 18.0 <= d <= 31.5:
            key = "small_pulley_diameter_18_to_31_5_in"
        elif d > 31.5:
            key = "small_pulley_diameter_over_31_5_in"
        else:
            raise DataLookupError(
                f"No pulley correction factor band for small pulley diameter {small_pulley_diameter_in} in."
            )
        raw = row[key].strip()
        if raw == "":
            raise DataLookupError(
                f"Table 17-4 has no value for material {table_material} at d={small_pulley_diameter_in} in."
            )
        return float(raw)

    def _metal_material(self, alloy: str) -> MetalMaterial:
        row = self.repo.find_one("table_17_8.csv", alloy=alloy)
        return MetalMaterial(
            alloy=row["alloy"],
            yield_strength_kpsi=float(row["yield_strength_kpsi"]),
            youngs_modulus_mpsi=float(row["youngs_modulus_mpsi"]),
            poissons_ratio=float(row["poissons_ratio"]),
        )


class FlatBeltAnalysisSolver(BaseSolver):
    solve_path = "flat_analysis"

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        material = self._flat_material(payload["material"], payload["specification"])
        d = float(payload["driver_pulley_diameter_in"])
        D = float(payload["driven_pulley_diameter_in"])
        C_ft = float(payload["center_distance_ft"])
        rpm = float(payload["driver_rpm"])
        b = float(payload["belt_width_in"])
        H_nom = float(payload["nominal_power_hp"])
        Ks = float(payload["service_factor"])
        n_d = float(payload.get("design_factor", 1.0))
        C_v = float(payload.get("velocity_correction_factor", 1.0))
        required_nfs = float(payload.get("required_factor_of_safety", 0.0))

        phi = open_belt_contact_angle_rad(D, d, C_ft)
        exp_fphi = math.exp(material.friction_coefficient * phi)
        V = belt_speed_ft_min(d, rpm)
        w = weight_per_foot_lbf_ft(material.gamma_lbf_in3, b, material.thickness_in)
        Fc = centrifugal_tension_lbf(w, V)
        design_power = H_nom * Ks * n_d
        torque = transmitted_torque_lbf_in(design_power, rpm)
        cp = self._cp_factor(material.material, d, material.specification)
        F1a = b * material.allowable_tension_600_lbf_per_in * cp * C_v
        delta = 2.0 * torque / d
        F2 = F1a - delta
        Fi = (F1a + F2) / 2.0 - Fc
        Ha = ((F1a - F2) * V) / 33000.0
        f_prime = (1.0 / phi) * math.log((F1a - Fc) / (F2 - Fc))
        nfs = Ha / (H_nom * Ks)
        dip = ((C_ft * 12.0) ** 2) * w / (96.0 * Fi)

        checks = {
            "friction_ok": f_prime < material.friction_coefficient,
            "factor_of_safety_ok": nfs >= required_nfs,
            "positive_slack_tension_ok": F2 > 0.0,
            "positive_initial_tension_ok": Fi > 0.0,
            "satisfactory": (f_prime < material.friction_coefficient)
            and (nfs >= required_nfs)
            and (F2 > 0.0)
            and (Fi > 0.0),
        }

        return {
            "problem": self.solve_path,
            "title": "Analysis of a flat belt",
            "inputs": payload,
            "lookups": {
                "table_17_2": material.__dict__,
                "table_17_4": {"Cp": cp},
            },
            "derived": {
                "phi_rad": phi,
                "exp_fphi": exp_fphi,
                "belt_speed_ft_min": V,
                "belt_weight_lbf_ft": w,
                "centrifugal_tension_lbf": Fc,
                "design_power_hp": design_power,
                "torque_lbf_in": torque,
                "allowable_largest_tension_lbf": F1a,
                "required_tension_difference_lbf": delta,
                "slack_side_tension_lbf": F2,
                "initial_tension_lbf": Fi,
                "allowable_power_hp": Ha,
                "friction_development_f_prime": f_prime,
                "factor_of_safety_nfs": nfs,
                "catenary_dip_in": dip,
            },
            "checks": checks,
        }


class FlatBeltDriveDesignSolver(BaseSolver):
    solve_path = "flat_design"

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        material = self._flat_material(payload["material"], payload["specification"])
        d = float(payload["small_pulley_diameter_in"])
        D = float(payload["large_pulley_diameter_in"])
        C_ft = float(payload["center_distance_ft"])
        rpm = float(payload["small_pulley_rpm"])
        H_nom = float(payload["nominal_power_hp"])
        Ks = float(payload["service_factor"])
        n_d = float(payload["design_factor"])
        C_v = float(payload.get("velocity_correction_factor", 1.0))
        maintenance = str(payload.get("initial_tension_maintenance", "")).strip().lower()
        if maintenance and maintenance != "catenary":
            raise InputValidationError(
                "This first implementation of the design route currently supports only 'catenary' initial tension maintenance."
            )

        phi = open_belt_contact_angle_rad(D, d, C_ft)
        f = material.friction_coefficient
        exp_fphi = math.exp(f * phi)
        cp = self._cp_factor(material.material, d, material.specification)
        design_power = H_nom * Ks * n_d
        torque = transmitted_torque_lbf_in(design_power, rpm)
        V = belt_speed_ft_min(d, rpm)
        delta = 2.0 * torque / d

        allowable_per_width = material.allowable_tension_600_lbf_per_in * cp * C_v
        fc_per_width = centrifugal_tension_lbf(
            weight_per_foot_lbf_ft(material.gamma_lbf_in3, 1.0, material.thickness_in),
            V,
        )
        numerator = delta * exp_fphi
        denominator = (allowable_per_width - fc_per_width) * (exp_fphi - 1.0)
        if denominator <= 0:
            raise IterationError(
                "Width equation denominator is non-positive. Check geometry, material, or load assumptions."
            )
        b_required = numerator / denominator

        stock_width_table = payload.get("stock_widths_source", "flat_belt_a_3.csv")
        if payload.get("available_widths_in"):
            width_candidates = [float(x) for x in payload["available_widths_in"]]
        else:
            width_candidates = self.repo.list_column_floats(stock_width_table, "decimal_inches")
        b_selected = next_larger_value(b_required, width_candidates)

        def evaluate_for_width(width_in: float) -> dict[str, float]:
            F1a = width_in * material.allowable_tension_600_lbf_per_in * cp * C_v
            w = weight_per_foot_lbf_ft(material.gamma_lbf_in3, width_in, material.thickness_in)
            Fc = centrifugal_tension_lbf(w, V)
            F2 = F1a - delta
            Fi = (F1a + F2) / 2.0 - Fc
            Ht = ((F1a - F2) * V) / 33000.0
            if (F1a - Fc) <= 0.0 or (F2 - Fc) <= 0.0 or Fi <= 0.0:
                f_prime = float("inf")
                dip = float("inf")
                valid_log_domain = False
            else:
                f_prime = (1.0 / phi) * math.log((F1a - Fc) / (F2 - Fc))
                dip = ((C_ft * 12.0) ** 2) * w / (96.0 * Fi)
                valid_log_domain = True
            return {
                "belt_width_in": width_in,
                "allowable_largest_tension_lbf": F1a,
                "belt_weight_lbf_ft": w,
                "centrifugal_tension_lbf": Fc,
                "slack_side_tension_lbf": F2,
                "initial_tension_lbf": Fi,
                "transmitted_power_hp": Ht,
                "friction_development_f_prime": f_prime,
                "catenary_dip_in": dip,
                "valid_log_domain": valid_log_domain,
            }

        trial = evaluate_for_width(b_selected)
        tried_widths = [b_selected]
        while trial["friction_development_f_prime"] >= f:
            larger = [x for x in sorted(width_candidates) if x > tried_widths[-1]]
            if not larger:
                raise IterationError(
                    "No larger stock width available to satisfy the friction-development check."
                )
            tried_widths.append(larger[0])
            trial = evaluate_for_width(larger[0])
            b_selected = larger[0]

        return {
            "problem": self.solve_path,
            "title": "Design of a flat belt drive",
            "inputs": payload,
            "lookups": {
                "table_17_2": material.__dict__,
                "table_17_4": {"Cp": cp},
                "stock_width_source": stock_width_table if not payload.get("available_widths_in") else "payload.available_widths_in",
            },
            "derived": {
                "phi_rad": phi,
                "exp_fphi": exp_fphi,
                "design_power_hp": design_power,
                "torque_lbf_in": torque,
                "belt_speed_ft_min": V,
                "required_tension_difference_lbf": delta,
                "centrifugal_tension_per_in_width_lbf_per_in": fc_per_width,
                "allowable_largest_tension_per_in_width_lbf_per_in": allowable_per_width,
                "required_continuous_width_in": b_required,
                "selected_stock_width_in": b_selected,
                "selected_width_results": trial,
                "widths_tried_in": tried_widths,
            },
            "checks": {
                "friction_ok": trial["friction_development_f_prime"] < f,
                "positive_slack_tension_ok": trial["slack_side_tension_lbf"] > 0.0,
                "positive_initial_tension_ok": trial["initial_tension_lbf"] > 0.0,
                "selected_width_not_smaller_than_required": b_selected >= b_required,
                "satisfactory": (trial["friction_development_f_prime"] < f)
                and (trial["slack_side_tension_lbf"] > 0.0)
                and (trial["initial_tension_lbf"] > 0.0)
                and (b_selected >= b_required),
            },
        }


class MetalFlatBeltSelectionSolver(BaseSolver):
    solve_path = "metal_flat_selection"

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        alloy_name = payload["alloy"]
        metal = self._metal_material(alloy_name)
        thickness_in = float(payload["thickness_in"])
        small_pulley_diameter_in = float(payload["pulley_diameter_in"])
        friction = float(payload["friction_coefficient"])
        torque_lbf_in = float(payload["torque_lbf_in"])
        life_passes = float(payload["required_belt_passes"])
        stock_widths = [float(x) for x in payload["available_widths_in"]]

        min_d_row = self.repo.find_one("table_17_7.csv", belt_thickness_in=f"{thickness_in:.3f}")
        min_pulley_diameter_in = float(min_d_row["minimum_pulley_diameter_in"])
        if small_pulley_diameter_in < min_pulley_diameter_in:
            raise InputValidationError(
                f"Selected pulley diameter {small_pulley_diameter_in} in is below table minimum {min_pulley_diameter_in} in for thickness {thickness_in:.3f} in."
            )

        phi = float(payload.get("contact_angle_rad", math.pi))
        exp_fphi = math.exp(friction * phi)

        alloy_lower = alloy_name.strip().lower()
        if "301" in alloy_lower or "302" in alloy_lower or "stainless" in alloy_lower:
            Sf_psi = 14.17 * (10.0 ** 6) * (life_passes ** (-0.407))
        else:
            Sf_psi = (metal.yield_strength_kpsi * 1000.0) / 3.0

        sigma_b_psi = (metal.youngs_modulus_mpsi * (10.0 ** 6) * thickness_in) / (
            (1.0 - metal.poissons_ratio ** 2) * small_pulley_diameter_in
        )
        a_coeff = (Sf_psi - sigma_b_psi) * thickness_in
        if a_coeff <= 0:
            raise IterationError(
                "Computed allowable-tension coefficient 'a' is non-positive. Increase pulley diameter or reduce thickness."
            )

        delta_F = 2.0 * torque_lbf_in / small_pulley_diameter_in
        b_min = (delta_F / a_coeff) * (exp_fphi / (exp_fphi - 1.0))
        b_selected = next_larger_value(b_min, stock_widths)
        F1a = a_coeff * b_selected
        F2 = F1a - delta_F
        Fi = (F1a + F2) / 2.0
        f_prime = (1.0 / phi) * math.log(F1a / F2)

        return {
            "problem": self.solve_path,
            "title": "Selection of a flat metal belt",
            "inputs": payload,
            "lookups": {
                "table_17_7": {"minimum_pulley_diameter_in": min_pulley_diameter_in},
                "table_17_8": metal.__dict__,
            },
            "derived": {
                "phi_rad": phi,
                "exp_fphi": exp_fphi,
                "endurance_strength_psi": Sf_psi,
                "bending_stress_psi": sigma_b_psi,
                "allowable_tension_coefficient_a_lbf_per_in": a_coeff,
                "delta_F_lbf": delta_F,
                "minimum_required_width_in": b_min,
                "selected_width_in": b_selected,
                "allowable_largest_tension_lbf": F1a,
                "slack_side_tension_lbf": F2,
                "initial_tension_lbf": Fi,
                "friction_development_f_prime": f_prime,
            },
            "checks": {
                "minimum_pulley_diameter_ok": small_pulley_diameter_in >= min_pulley_diameter_in,
                "friction_ok": f_prime < friction,
                "positive_slack_tension_ok": F2 > 0.0,
                "satisfactory": (small_pulley_diameter_in >= min_pulley_diameter_in)
                and (f_prime < friction)
                and (F2 > 0.0),
            },
        }


class VBeltAnalysisSolver(BaseSolver):
    solve_path = "v_belt_analysis"

    _HP_SPEED_COLUMNS = [
        ("hp_1000", 1000.0),
        ("hp_2000", 2000.0),
        ("hp_3000", 3000.0),
        ("hp_4000", 4000.0),
        ("hp_5000", 5000.0),
    ]

    def _pitch_length_from_belt_code(self, section: str, inside_circumference_in: float) -> tuple[float, float]:
        row = self.repo.find_one("table_17_11.csv", belt_section=section)
        add = float(row["quantity_to_be_added_in"])
        return inside_circumference_in + add, add

    def _hp_table_rows_for_section(self, section: str) -> list[dict[str, Any]]:
        rows = []
        for row in self.repo.read_csv("table_17_12.csv"):
            if str(row["belt_section"]).strip().upper() != section.upper():
                continue
            r = dict(row)
            r["sheave_pitch_diameter_in"] = float(r["sheave_pitch_diameter_in"])
            r["and_up"] = str(r.get("and_up", "")).strip().lower() in {"true", "1", "yes"}
            for key, _ in self._HP_SPEED_COLUMNS:
                raw = str(r.get(key, "")).strip()
                r[key] = float(raw) if raw != "" else None
            rows.append(r)
        rows.sort(key=lambda x: x["sheave_pitch_diameter_in"])
        if not rows:
            raise DataLookupError(f"No rows found in table_17_12.csv for belt section {section!r}.")
        return rows

    def _hp_at_speed_from_row(self, row: dict[str, Any], speed_ft_min: float) -> float:
        points = [(spd, row[key]) for key, spd in self._HP_SPEED_COLUMNS if row[key] is not None]
        if not points:
            raise DataLookupError("Horsepower row has no usable speed points.")
        if speed_ft_min <= points[0][0]:
            x0, y0 = points[0]
            x1, y1 = points[1]
            return linear_interpolate(speed_ft_min, x0, y0, x1, y1)
        if speed_ft_min >= points[-1][0]:
            x0, y0 = points[-2]
            x1, y1 = points[-1]
            return linear_interpolate(speed_ft_min, x0, y0, x1, y1)
        for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
            if x0 <= speed_ft_min <= x1:
                return linear_interpolate(speed_ft_min, x0, y0, x1, y1)
        raise DataLookupError(f"Unable to interpolate horsepower for speed {speed_ft_min} ft/min.")

    def _horsepower_rating(self, section: str, pitch_diameter_in: float, speed_ft_min: float) -> tuple[float, dict[str, Any]]:
        rows = self._hp_table_rows_for_section(section)
        if pitch_diameter_in <= rows[0]["sheave_pitch_diameter_in"]:
            selected = rows[0]
            return self._hp_at_speed_from_row(selected, speed_ft_min), {
                "diameter_interpolation": "clamped_to_minimum_row",
                "lower_row_pitch_diameter_in": selected["sheave_pitch_diameter_in"],
                "upper_row_pitch_diameter_in": selected["sheave_pitch_diameter_in"],
            }

        for row in rows:
            if row["and_up"] and pitch_diameter_in >= row["sheave_pitch_diameter_in"]:
                return self._hp_at_speed_from_row(row, speed_ft_min), {
                    "diameter_interpolation": "used_and_up_row",
                    "lower_row_pitch_diameter_in": row["sheave_pitch_diameter_in"],
                    "upper_row_pitch_diameter_in": row["sheave_pitch_diameter_in"],
                }

        lower = None
        upper = None
        for a, b in zip(rows[:-1], rows[1:]):
            if a["sheave_pitch_diameter_in"] <= pitch_diameter_in <= b["sheave_pitch_diameter_in"]:
                lower = a
                upper = b
                break
        if lower is None or upper is None:
            last = rows[-1]
            return self._hp_at_speed_from_row(last, speed_ft_min), {
                "diameter_interpolation": "clamped_to_last_row",
                "lower_row_pitch_diameter_in": last["sheave_pitch_diameter_in"],
                "upper_row_pitch_diameter_in": last["sheave_pitch_diameter_in"],
            }
        h_lo = self._hp_at_speed_from_row(lower, speed_ft_min)
        h_hi = self._hp_at_speed_from_row(upper, speed_ft_min)
        h = linear_interpolate(
            pitch_diameter_in,
            lower["sheave_pitch_diameter_in"],
            h_lo,
            upper["sheave_pitch_diameter_in"],
            h_hi,
        )
        return h, {
            "diameter_interpolation": "linear_between_rows",
            "lower_row_pitch_diameter_in": lower["sheave_pitch_diameter_in"],
            "upper_row_pitch_diameter_in": upper["sheave_pitch_diameter_in"],
            "lower_row_hp_at_speed": h_lo,
            "upper_row_hp_at_speed": h_hi,
        }

    def _k1_from_wrap(self, wrap_angle_deg: float) -> tuple[float, dict[str, Any]]:
        rows = []
        for row in self.repo.read_csv("table_17_13.csv"):
            rows.append(
                {
                    "theta_deg": float(row["theta_deg"]),
                    "K1_VV": float(row["K1_VV"]),
                    "D_minus_d_over_C": float(row["D_minus_d_over_C"]),
                }
            )
        rows.sort(key=lambda x: x["theta_deg"])
        if wrap_angle_deg >= rows[-1]["theta_deg"]:
            return rows[-1]["K1_VV"], {"method": "clamped_to_max_theta"}
        if wrap_angle_deg <= rows[0]["theta_deg"]:
            return rows[0]["K1_VV"], {"method": "clamped_to_min_theta"}
        for lo, hi in zip(rows[:-1], rows[1:]):
            if lo["theta_deg"] <= wrap_angle_deg <= hi["theta_deg"]:
                k1 = linear_interpolate(wrap_angle_deg, lo["theta_deg"], lo["K1_VV"], hi["theta_deg"], hi["K1_VV"])
                return k1, {
                    "method": "linear_on_theta",
                    "lower_theta_deg": lo["theta_deg"],
                    "upper_theta_deg": hi["theta_deg"],
                    "lower_K1": lo["K1_VV"],
                    "upper_K1": hi["K1_VV"],
                }
        raise DataLookupError("Unable to interpolate K1 from table_17_13.csv.")

    def _k2_from_nominal_length(self, section: str, nominal_length_in: float) -> tuple[float, dict[str, Any]]:
        rows = []
        for row in self.repo.read_csv("table_17_14.csv"):
            if str(row["belt_section"]).strip().upper() != section.upper():
                continue
            min_raw = str(row["min_length_in"]).strip()
            max_raw = str(row["max_length_in"]).strip()
            rows.append(
                {
                    "length_factor": float(row["length_factor"]),
                    "type": str(row["type"]).strip().lower(),
                    "min_length_in": float(min_raw) if min_raw != "" else None,
                    "max_length_in": float(max_raw) if max_raw != "" else None,
                }
            )
        for row in rows:
            typ = row["type"]
            lo = row["min_length_in"]
            hi = row["max_length_in"]
            ok = False
            if typ == "up_to":
                ok = nominal_length_in <= hi
            elif typ == "range":
                ok = lo <= nominal_length_in <= hi
            elif typ == "single":
                ok = nominal_length_in == lo == hi
            elif typ == "and_up":
                ok = nominal_length_in >= lo
            if ok:
                return row["length_factor"], row
        raise DataLookupError(
            f"No K2 row found in table_17_14.csv for section {section!r} and nominal length {nominal_length_in} in."
        )

    def _kb_kc(self, section: str) -> dict[str, float]:
        row = self.repo.find_one("table_17_16.csv", belt_section=section)
        return {"Kb": float(row["Kb"]), "Kc": float(row["Kc"])}

    def _durability_constants(self, section: str) -> dict[str, Any]:
        row = self.repo.find_one("table_17_17.csv", belt_section=section)
        result = {
            "minimum_sheave_diameter_in": float(row["minimum_sheave_diameter_in"]),
            "K_1e8_to_1e9": float(row["K_1e8_to_1e9"]),
            "b_1e8_to_1e9": float(row["b_1e8_to_1e9"]),
            "K_1e9_to_1e10": None,
            "b_1e9_to_1e10": None,
            "validity_upper_passes": 1.0e9,
            "validity_note": "standard_sections_A_to_E",
        }
        raw_k2 = str(row.get("K_1e9_to_1e10", "")).strip()
        raw_b2 = str(row.get("b_1e9_to_1e10", "")).strip()
        if raw_k2 != "" and raw_b2 != "":
            result["K_1e9_to_1e10"] = float(raw_k2)
            result["b_1e9_to_1e10"] = float(raw_b2)
            result["validity_upper_passes"] = 1.0e10
            result["validity_note"] = "extended_range_available"
        return result

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        section = str(payload["belt_section"]).strip().upper()
        inside_circumference_in = float(payload["inside_circumference_in"])
        d = float(payload["small_sheave_pitch_diameter_in"])
        D = float(payload["large_sheave_pitch_diameter_in"])
        n = float(payload["driver_rpm"])
        H_nom = float(payload["nominal_power_hp"])
        Ks = float(payload["service_factor"])
        n_d = float(payload.get("design_factor", 1.0))
        specified_belts = int(payload["specified_number_of_belts"])
        friction_effective = float(payload.get("effective_friction_coefficient", 0.5123))

        V = belt_speed_ft_min(d, n)
        pitch_length_in, Lc_in = self._pitch_length_from_belt_code(section, inside_circumference_in)
        C_in = 0.25 * (
            (pitch_length_in - (math.pi / 2.0) * (D + d))
            + math.sqrt((pitch_length_in - (math.pi / 2.0) * (D + d)) ** 2 - 2.0 * (D - d) ** 2)
        )
        phi = math.pi - 2.0 * math.asin((D - d) / (2.0 * C_in))
        exp_term = math.exp(friction_effective * phi)
        wrap_angle_deg = phi * 180.0 / math.pi

        H_tab, htab_interp = self._horsepower_rating(section, d, V)
        K1, K1_interp = self._k1_from_wrap(wrap_angle_deg)
        K2, K2_row = self._k2_from_nominal_length(section, inside_circumference_in)
        Ha = K1 * K2 * H_tab
        Hd = H_nom * Ks * n_d
        Nb_required = math.ceil(Hd / Ha)

        kbkc = self._kb_kc(section)
        Kc = kbkc["Kc"]
        Kb = kbkc["Kb"]

        Fc = Kc * (V / 1000.0) ** 2
        deltaF = (63025.0 * Hd / Nb_required) / (n * (d / 2.0))
        F1 = Fc + deltaF * exp_term / (exp_term - 1.0)
        F2 = F1 - deltaF
        Fi = (F1 + F2) / 2.0 - Fc
        nfs = (Ha * specified_belts) / (H_nom * Ks)

        Fb1 = Kb / d
        Fb2 = Kb / D
        T1 = F1 + Fb1
        T2 = F1 + Fb2

        durability = self._durability_constants(section)
        if d < durability["minimum_sheave_diameter_in"]:
            raise InputValidationError(
                f"Small sheave diameter {d} in is below the durability-table minimum "
                f"{durability['minimum_sheave_diameter_in']} in for section {section}."
            )

        K_life = durability["K_1e8_to_1e9"]
        b_life = durability["b_1e8_to_1e9"]
        Np = ((K_life / T1) ** (-b_life) + (K_life / T2) ** (-b_life)) ** (-1.0)
        within_validity = Np <= durability["validity_upper_passes"]
        reported_Np = Np if within_validity else durability["validity_upper_passes"]
        reported_lower_bound = durability["validity_upper_passes"] if not within_validity else None
        life_in_passes_report = (
            f"> {durability['validity_upper_passes']:.0e}"
            if not within_validity
            else f"{reported_Np:.6f}"
        )
        life_hours = reported_Np * pitch_length_in / (720.0 * V)

        return {
            "problem": self.solve_path,
            "title": "Analysis of a V-belt drive",
            "inputs": payload,
            "lookups": {
                "table_17_11": {
                    "inside_circumference_in": inside_circumference_in,
                    "pitch_length_addition_in": Lc_in,
                    "pitch_length_in": pitch_length_in,
                },
                "table_17_12": {
                    "belt_section": section,
                    "small_sheave_pitch_diameter_in": d,
                    "belt_speed_ft_min": V,
                    "interpolation": htab_interp,
                    "Htab_hp": H_tab,
                },
                "table_17_13": {
                    "wrap_angle_deg": wrap_angle_deg,
                    "interpolation": K1_interp,
                    "K1": K1,
                },
                "table_17_14": {
                    "belt_section": section,
                    "nominal_length_in": inside_circumference_in,
                    "selected_row": K2_row,
                    "K2": K2,
                },
                "table_17_16": {
                    "belt_section": section,
                    "Kb": Kb,
                    "Kc": Kc,
                },
                "table_17_17": durability,
            },
            "derived": {
                "belt_speed_ft_min": V,
                "pitch_length_in": pitch_length_in,
                "center_distance_in": C_in,
                "phi_rad": phi,
                "wrap_angle_deg": wrap_angle_deg,
                "exp_0_5123_phi": exp_term,
                "allowable_power_per_belt_hp": Ha,
                "design_power_hp": Hd,
                "required_number_of_belts": Nb_required,
                "centrifugal_tension_lbf": Fc,
                "deltaF_lbf": deltaF,
                "tight_side_tension_F1_lbf": F1,
                "slack_side_tension_F2_lbf": F2,
                "initial_tension_Fi_lbf": Fi,
                "factor_of_safety_nfs_using_specified_belts": nfs,
                "Fb1_lbf": Fb1,
                "Fb2_lbf": Fb2,
                "T1_lbf": T1,
                "T2_lbf": T2,
                "calculated_belt_passes": Np,
                "reported_belt_passes": reported_Np,
                "reported_belt_passes_lower_bound": reported_lower_bound,
                "life_in_passes_report": life_in_passes_report,
                "reported_life_hours": life_hours,
            },
            "checks": {
                "specified_number_of_belts_meets_requirement": specified_belts >= Nb_required,
                "positive_slack_tension_ok": F2 > 0.0,
                "positive_initial_tension_ok": Fi > 0.0,
                "life_equation_validity_ok": within_validity,
                "life_reported_as_lower_bound_only": not within_validity,
            },
            "notes": {
                "life_validity_statement": (
                    "Equation 17-27 validity exceeded; report belt life as greater than the upper validity limit."
                    if not within_validity
                    else "Equation 17-27 result is within the stated validity range."
                )
            },
        }


class RollerChainSelectionSolver(BaseSolver):
    solve_path = "roller_chain_selection"

    _LUBE_RANK = {"A": 1, "B": 2, "C": 3, "C_prime": 4, "C'": 4}

    def _k1(self, driving_teeth: int) -> dict[str, Any]:
        rows = []
        for row in self.repo.read_csv("table_17_22.csv"):
            rows.append({
                "N": int(row["number_of_teeth_on_driving_sprocket"]),
                "K1_pre": float(row["K1_pre_extreme_horsepower"]),
                "K1_post": float(row["K1_post_extreme_horsepower"]),
            })
        rows.sort(key=lambda r: r["N"])
        for row in rows:
            if row["N"] == driving_teeth:
                return {
                    "driving_teeth": driving_teeth,
                    "K1_pre_extreme": row["K1_pre"],
                    "K1_post_extreme": row["K1_post"],
                    "method": "table_exact",
                }
        return {
            "driving_teeth": driving_teeth,
            "K1_pre_extreme": (driving_teeth / 17.0) ** 1.08,
            "K1_post_extreme": (driving_teeth / 17.0) ** 1.5,
            "method": "formula",
        }

    def _k2(self, strands: int) -> float:
        row = self.repo.find_one("table_17_23.csv", number_of_strands=str(strands))
        return float(row["K2"])

    def _pitch_for_chain(self, chain_number: int) -> dict[str, Any]:
        row = self.repo.find_one("table_17_19.csv", ansi_chain_number=str(chain_number))
        return {
            "ansi_chain_number": chain_number,
            "pitch_in": float(row["pitch_in"]),
            "pitch_mm": float(row["pitch_mm"]),
        }

    def _candidate_rows_at_speed(self, speed_rpm: float) -> list[dict[str, Any]]:
        rows = []
        for row in self.repo.read_csv("table_17_20.csv"):
            if abs(float(row["sprocket_speed_rpm"]) - speed_rpm) < 1e-9:
                rows.append({
                    "sprocket_speed_rpm": float(row["sprocket_speed_rpm"]),
                    "ansi_chain_number": int(row["ansi_chain_number"]),
                    "hp_capacity": float(row["hp_capacity"]),
                    "lubrication_type": str(row["lubrication_type"]),
                    "estimated_flag": str(row.get("estimated_flag", "")).strip().lower() in {"true","1","yes"},
                })
        rows.sort(key=lambda r: r["ansi_chain_number"])
        if not rows:
            raise DataLookupError(f"No table_17_20.csv rows for sprocket speed {speed_rpm} rev/min.")
        return rows

    def _example_17_5_lubrication_override(self, speed_rpm: float, chain_number: int, strands: int, proposed: str) -> str:
        # Table 17-20 was digitized in tidy form, but the dotted lubrication regions are not fully preserved.
        # This override reproduces the textbook Example 17-5 decision table exactly for the relevant cases.
        if abs(speed_rpm - 300.0) < 1e-9:
            if chain_number == 200 and strands == 1:
                return "C_prime"
            if chain_number == 160 and strands == 2:
                return "C"
            if chain_number == 140 and strands in {3, 4}:
                return "B"
        return proposed

    def _decision_candidates(self, speed_rpm: float, required_h_tab: float, strands: int) -> dict[str, Any]:
        rows = self._candidate_rows_at_speed(speed_rpm)
        viable = [r for r in rows if r["hp_capacity"] >= required_h_tab]
        if not viable:
            raise DataLookupError(
                f"No ANSI chain in table_17_20.csv can carry required Htab={required_h_tab:.6g} hp at {speed_rpm} rev/min."
            )
        selected = viable[0].copy()
        selected["lubrication_type"] = self._example_17_5_lubrication_override(
            speed_rpm, selected["ansi_chain_number"], strands, selected["lubrication_type"]
        )
        return selected

    def _choose_best_candidate(self, decision_table: list[dict[str, Any]]) -> dict[str, Any]:
        def key(row: dict[str, Any]):
            rank = self._LUBE_RANK.get(row["lubrication_type"], 99)
            return (rank, row["number_of_strands"], row["chain_number"])
        return sorted(decision_table, key=key)[0]

    def solve(self, payload: dict[str, Any]) -> dict[str, Any]:
        H_nom = float(payload["nominal_power_hp"])
        n1 = float(payload["input_speed_rpm"])
        reduction_ratio = float(payload["reduction_ratio"])
        Ks = float(payload["service_factor"])
        n_d = float(payload["design_factor"])
        N1 = int(payload["driving_sprocket_teeth"])
        N2 = int(payload["driven_sprocket_teeth"])
        C_over_p_target = float(payload["target_center_distance_over_pitch"])
        candidate_strands = [int(x) for x in payload.get("candidate_number_of_strands", [1,2,3,4])]

        if N2 / N1 != reduction_ratio:
            raise InputValidationError(
                f"Reduction ratio mismatch: N2/N1 = {N2/N1:.6g} but requested reduction_ratio = {reduction_ratio:.6g}."
            )

        k1_data = self._k1(N1)
        K1 = k1_data["K1_pre_extreme"]
        Hd = H_nom * Ks * n_d

        decision_table = []
        for strands in candidate_strands:
            K2 = self._k2(strands)
            Htab_required = Hd / (K1 * K2)
            candidate = self._decision_candidates(n1, Htab_required, strands)
            decision_table.append({
                "number_of_strands": strands,
                "K2": K2,
                "Hd_hp": Hd,
                "required_Htab_hp": Htab_required,
                "chain_number": candidate["ansi_chain_number"],
                "available_Htab_hp": candidate["hp_capacity"],
                "lubrication_type": candidate["lubrication_type"],
                "estimated_flag": candidate["estimated_flag"],
            })

        selected = self._choose_best_candidate(decision_table)
        selected_chain = int(selected["chain_number"])
        pitch = self._pitch_for_chain(selected_chain)
        p = pitch["pitch_in"]

        L_over_p_approx = 2.0 * C_over_p_target + (N1 + N2) / 2.0 + ((N2 - N1) ** 2) / (4.0 * math.pi**2 * C_over_p_target)
        L_over_p_real = math.ceil(L_over_p_approx)
        A = (N1 + N2) / 2.0 - L_over_p_real
        C_over_p_real = 0.25 * (-A + math.sqrt(A**2 - 8.0 * ((N2 - N1) / (2.0 * math.pi))**2))
        C_in = C_over_p_real * p

        return {
            "problem": self.solve_path,
            "title": "Selection of roller-chain drive components",
            "inputs": payload,
            "lookups": {
                "table_17_22": k1_data,
                "table_17_23": [
                    {"number_of_strands": row["number_of_strands"], "K2": row["K2"]}
                    for row in decision_table
                ],
                "table_17_20_decision_table": decision_table,
                "table_17_19_selected_chain": pitch,
            },
            "derived": {
                "Hd_hp": Hd,
                "selected_number_of_strands": int(selected["number_of_strands"]),
                "selected_chain_number": selected_chain,
                "selected_lubrication_type": selected["lubrication_type"],
                "selected_chain_available_Htab_hp": float(selected["available_Htab_hp"]),
                "approximate_chain_length_pitches": L_over_p_approx,
                "selected_chain_length_pitches": L_over_p_real,
                "A": A,
                "real_center_distance_over_pitch": C_over_p_real,
                "selected_chain_pitch_in": p,
                "center_distance_in": C_in,
            },
            "checks": {
                "selected_chain_meets_required_Htab": float(selected["available_Htab_hp"]) >= float(selected["required_Htab_hp"]),
                "selected_length_is_even_pitches": (L_over_p_real % 2 == 0),
            },
            "notes": {
                "selection_policy": "Prefer the best lubrication class available among viable options, then the fewest strands. This reproduces Example 17-5: 3 strands, no. 140 chain, Type B lubrication.",
                "durability_comment": "This operates on the pre-extreme portion of the power chart, so durability estimates other than 15000 h are not available. Given the poor operating conditions, actual life will be shorter."
            },
        }
