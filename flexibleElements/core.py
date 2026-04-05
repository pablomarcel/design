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

        # Width solve per Ex. 17-2 rearrangement.
        allowable_per_width = material.allowable_tension_600_lbf_per_in * cp * C_v
        fc_per_width = centrifugal_tension_lbf(
            weight_per_foot_lbf_ft(material.gamma_lbf_in3, 1.0, material.thickness_in),
            V,
        )
        numerator = delta
        denominator = (allowable_per_width - fc_per_width) * exp_fphi - allowable_per_width
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

        # Minimum pulley diameter check.
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
