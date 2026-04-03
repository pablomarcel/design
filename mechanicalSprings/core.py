from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils import DATA_DIR


@dataclass
class Material104Row:
    material_key: str
    material_label: str
    astm_no: str
    m: float
    diameter_in_min: Optional[float]
    diameter_in_max: Optional[float]
    A_kpsi_in_m: float
    relative_cost_min: Optional[float]
    relative_cost_max: Optional[float]


class SpringData:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.table_10_1 = self._load_json("table_10_1.json")
        self.table_10_2 = self._load_csv("table_10_2.csv")
        self.table_10_4 = self._load_csv("table_10_4.csv")
        self.table_10_5 = self._load_csv("table_10_5.csv")
        self.table_10_6 = self._load_csv("table_10_6.csv")
        self.table_a_28 = self._load_csv("table_a_28.csv")
        self.table_6_6 = self._load_json("table_6_6.json")
        self.table_6_7 = self._load_json("table_6_7.json")
        self.table_6_8 = self._load_json("table_6_8.json")

    def _load_json(self, name: str) -> Dict[str, Any]:
        import json
        with (self.data_dir / name).open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_csv(self, name: str) -> List[Dict[str, str]]:
        with (self.data_dir / name).open("r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    @staticmethod
    def _to_float(value: str | None) -> Optional[float]:
        if value is None:
            return None
        value = str(value).strip()
        if value == "":
            return None
        return float(value)

    @staticmethod
    def _canonicalize_text(text: str) -> str:
        return (
            text.lower()
            .strip()
            .replace("_", " ")
            .replace("-", " ")
            .replace("&", "and")
        )

    def _normalize_material_query(self, material_query: str) -> List[str]:
        """
        Return a list of normalized aliases to try, most specific first.
        This makes the lookup robust to user-friendly names such as
        'hard-drawn', 'hard-drawn wire', 'music wire', etc.
        """
        raw = self._canonicalize_text(material_query)
        compact = " ".join(raw.split())

        aliases = {compact}

        alias_groups = {
            "a228": [
                "a228", "music wire", "music", "astm a228",
            ],
            "a227": [
                "a227", "hard drawn", "hard drawn wire", "hard-drawn", "hard-drawn wire",
                "hd spring", "hd spring a227", "astm a227",
            ],
            "a229": [
                "a229", "oqt", "oq and t", "oq&t", "oqt wire", "oil quenched and tempered",
                "oil quenched and tempered wire", "astm a229",
            ],
            "a230": [
                "a230", "valve spring", "valve spring wire", "astm a230",
            ],
            "a231": [
                "a231", "chrome vanadium", "chrome vanadium wire", "astm a231",
            ],
            "a232": [
                "a232", "chrome vanadium", "chrome vanadium wire", "astm a232",
            ],
            "a401": [
                "a401", "chrome silicon", "chrome silicon wire", "astm a401",
            ],
            "a313": [
                "a313", "302 stainless", "302 stainless wire", "stainless", "stainless wire", "astm a313",
            ],
            "b159": [
                "b159", "phosphor bronze", "phosphor bronze wire", "astm b159",
            ],
            "b197": [
                "b197", "beryllium copper", "beryllium copper wire", "astm b197",
            ],
            "x750": [
                "inconel x 750", "inconel x750", "x750", "inconel alloy x 750",
            ],
            "17-7ph": [
                "17 7ph", "17-7ph", "stainless 17 7ph", "stainless 17-7ph",
            ],
            "414": [
                "414", "stainless 414",
            ],
            "420": [
                "420", "stainless 420",
            ],
            "431": [
                "431", "stainless 431",
            ],
        }

        for canon, group in alias_groups.items():
            group_norm = {self._canonicalize_text(x) for x in group}
            if compact in group_norm:
                aliases.add(canon)
                aliases.update(group_norm)

        ordered = [compact]
        for item in sorted(aliases, key=lambda s: (len(s), s)):
            if item not in ordered:
                ordered.append(item)
        return ordered

    def get_end_equations(self, end_type: str) -> Dict[str, str]:
        return self.table_10_1["end_types"][end_type]["equations"]

    def get_end_condition_alpha(self, end_condition_key: str) -> float:
        for row in self.table_10_2:
            if row["end_condition_key"] == end_condition_key:
                return float(row["alpha"])
        raise KeyError(f"Unknown end condition: {end_condition_key}")

    def _row_text(self, row: Dict[str, str], keys: List[str]) -> str:
        return self._canonicalize_text(" ".join(row.get(k, "") for k in keys))

    def _diameter_matches(self, row: Dict[str, str], d_in: Optional[float]) -> bool:
        if d_in is None:
            return True
        dmin = self._to_float(row.get("diameter_in_min"))
        dmax = self._to_float(row.get("diameter_in_max"))
        return (dmin is None or d_in >= dmin - 1e-12) and (dmax is None or d_in <= dmax + 1e-12)

    def get_material_104(self, material_query: str, d_in: Optional[float] = None) -> Dict[str, Any]:
        aliases = self._normalize_material_query(material_query)
        candidates: List[Dict[str, str]] = []
        for row in self.table_10_4:
            row_text = self._row_text(row, ["material_label", "material_key", "astm_no"])
            astm = self._canonicalize_text(row.get("astm_no", ""))
            if any(alias == astm or alias in row_text for alias in aliases):
                if self._diameter_matches(row, d_in):
                    candidates.append(row)
        if not candidates:
            raise KeyError(f"No Table 10-4 row matched material={material_query!r}, d_in={d_in}")
        row = candidates[0]
        return {
            "material_key": row["material_key"],
            "material_label": row["material_label"],
            "astm_no": row["astm_no"],
            "m": float(row["m"]),
            "A_kpsi_in_m": float(row["A_kpsi_in_m"]),
            "relative_cost": self._average_range(row.get("relative_cost_min"), row.get("relative_cost_max")),
            "diameter_in_min": self._to_float(row.get("diameter_in_min")),
            "diameter_in_max": self._to_float(row.get("diameter_in_max")),
        }

    def get_material_105(self, material_query: str, d_in: Optional[float] = None) -> Dict[str, Any]:
        aliases = self._normalize_material_query(material_query)
        candidates: List[Dict[str, str]] = []
        for row in self.table_10_5:
            row_text = self._row_text(row, ["material_label", "material_key", "astm_no"])
            astm = self._canonicalize_text(row.get("astm_no", ""))
            if not any(alias == astm or alias in row_text for alias in aliases):
                continue
            if self._diameter_matches(row, d_in):
                candidates.append(row)
        if not candidates:
            raise KeyError(f"No Table 10-5 row matched material={material_query!r}, d_in={d_in}")
        row = candidates[0]
        return {
            "material_key": row["material_key"],
            "material_label": row["material_label"],
            "astm_no": row["astm_no"],
            "Sey_tension_pct_min": self._to_float(row.get("Sey_tension_pct_min")),
            "Sey_tension_pct_max": self._to_float(row.get("Sey_tension_pct_max")),
            "Ssy_torsion_pct_min": self._to_float(row.get("Ssy_torsion_pct_min")),
            "Ssy_torsion_pct_max": self._to_float(row.get("Ssy_torsion_pct_max")),
            "E_Mpsi": float(row["E_Mpsi"]),
            "G_Mpsi": float(row["G_Mpsi"]),
        }

    def get_allowable_percent_106(self, material_query: str, set_removed: bool = False, strategy: str = "min") -> float:
        mq = self._canonicalize_text(material_query)
        group_key = self._map_material_to_106_group(mq)
        for row in self.table_10_6:
            if row["material_group_key"] != group_key:
                continue
            if set_removed:
                return self._range_value(
                    row["max_percent_tensile_strength_after_set_removed_min"],
                    row["max_percent_tensile_strength_after_set_removed_max"],
                    strategy,
                )
            return self._range_value(
                row["max_percent_tensile_strength_before_set_removed_min"],
                row["max_percent_tensile_strength_before_set_removed_max"],
                strategy,
            )
        raise KeyError(f"No Table 10-6 mapping for material={material_query!r}")

    def _map_material_to_106_group(self, material_query: str) -> str:
        mq = self._canonicalize_text(material_query)
        if any(x in mq for x in ["music", "a228", "hard drawn", "a227", "cold drawn"]):
            return "music_wire_and_cold_drawn_carbon_steel"
        if any(x in mq for x in ["oil tempered", "a229", "valve", "a230", "chrome vanadium", "a231", "a232", "chrome silicon", "a401", "oqt"]):
            return "hardened_tempered_carbon_and_low_alloy_steel"
        if any(x in mq for x in ["stainless", "a313", "17 7ph", "414", "420", "431"]):
            return "austenitic_stainless_steels"
        return "nonferrous_alloys"

    def _range_value(self, vmin: str, vmax: str, strategy: str) -> float:
        a = float(vmin)
        b = float(vmax)
        if strategy == "min":
            return a / 100.0
        if strategy == "max":
            return b / 100.0
        return (0.5 * (a + b)) / 100.0

    def _average_range(self, vmin: str | None, vmax: str | None) -> Optional[float]:
        a = self._to_float(vmin)
        b = self._to_float(vmax)
        if a is None and b is None:
            return None
        if a is None:
            return b
        if b is None:
            return a
        return 0.5 * (a + b)

    def select_wire_from_a28(self, system_key: str, required_d_in: float, prefer: str = "at_or_above") -> Dict[str, Any]:
        valid_rows = []
        for row in self.table_a_28:
            raw = row.get(system_key, "")
            value = self._to_float(raw)
            if value is None:
                continue
            valid_rows.append({"gauge": row["gauge"], "diameter_in": value})
        valid_rows.sort(key=lambda r: r["diameter_in"])
        if prefer == "at_or_above":
            for row in valid_rows:
                if row["diameter_in"] + 1e-12 >= required_d_in:
                    return row
            return valid_rows[-1]
        for row in reversed(valid_rows):
            if row["diameter_in"] <= required_d_in + 1e-12:
                return row
        return valid_rows[0]


def spring_index(D: float, d: float) -> float:
    return D / d


def ks(C: float) -> float:
    return (2 * C + 1) / (2 * C)


def kw(C: float) -> float:
    return (4 * C - 1) / (4 * C - 4) + 0.615 / C


def kb(C: float) -> float:
    return (4 * C + 2) / (4 * C - 3)


def kc(C: float) -> float:
    return kb(C) / ks(C)


def tau_max(F: float, D: float, d: float, factor: float) -> float:
    return factor * 8.0 * F * D / (math.pi * d ** 3)


def deflection(F: float, D: float, d: float, Na: float, G_psi: float, include_small_term: bool = False) -> float:
    if include_small_term:
        C = D / d
        return (8.0 * F * D ** 3 * Na / (d ** 4 * G_psi)) * (1.0 + 1.0 / (2.0 * C ** 2))
    return 8.0 * F * D ** 3 * Na / (d ** 4 * G_psi)


def spring_rate(D: float, d: float, Na: float, G_psi: float) -> float:
    return d ** 4 * G_psi / (8.0 * D ** 3 * Na)


def sut_from_table_104(A_kpsi_in_m: float, m: float, d_in: float) -> float:
    return A_kpsi_in_m / (d_in ** m)


def ssu_from_sut(sut_kpsi: float) -> float:
    return 0.67 * sut_kpsi


def D_from_OD(OD: float, d: float) -> float:
    return OD - d


def OD_from_D(D: float, d: float) -> float:
    return D + d


def ID_from_D(D: float, d: float) -> float:
    return D - d


def fs_solid(Fmax: float, xi: float) -> float:
    return (1.0 + xi) * Fmax


def equation_10_23(alpha: float, beta: float) -> float:
    term = (2.0 * alpha - beta) / (4.0 * beta)
    return term + math.sqrt(term ** 2 - (3.0 * alpha) / (4.0 * beta))


def equation_10_23_d_from_strength(A_kpsi_in_m: float, m: float, percent: float, ns: float, Fs: float, C: float) -> float:
    numerator = kb(C) * 8.0 * Fs * C * ns
    denominator = math.pi * percent * A_kpsi_in_m * 1000.0
    exponent = 1.0 / (2.0 - m)
    return (numerator / denominator) ** exponent


def buckling_l0_cr_steel(D: float, alpha_end: float) -> float:
    return 2.63 * D / alpha_end


def weight_lbf(d: float, D: float, Na: float, gamma_lb_per_in3: float) -> float:
    return (math.pi ** 2) * d ** 2 * D * Na * gamma_lb_per_in3 / 4.0


def natural_frequency_hz(k_lbf_per_in: float, W_lbf: float, g_in_per_s2: float = 386.0) -> float:
    return 0.5 * math.sqrt(k_lbf_per_in * g_in_per_s2 / W_lbf)


def zimmerli(unpeened: bool = True) -> Dict[str, float]:
    if unpeened:
        return {"Ssa_kpsi": 35.0, "Ssm_kpsi": 55.0}
    return {"Ssa_kpsi": 57.5, "Ssm_kpsi": 77.5}


def fatigue_forces(Fmin: float, Fmax: float) -> Dict[str, float]:
    return {"Fa": 0.5 * (Fmax - Fmin), "Fm": 0.5 * (Fmax + Fmin)}


def load_line_slope(tau_a: float, tau_m: float) -> float:
    if abs(tau_m) < 1e-15:
        return math.inf
    return tau_a / tau_m


def gerber_sse_from_zimmerli(Ssa: float, Ssm: float, Ssu: float) -> float:
    return Ssa / (1.0 - (Ssm / Ssu) ** 2)


def goodman_sse_from_zimmerli(Ssa: float, Ssm: float, Ssu: float) -> float:
    return Ssa / (1.0 - (Ssm / Ssu))


def gerber_allowable_shear_amplitude(r: float, Sse: float, Ssu: float) -> float:
    return (r ** 2 * Ssu ** 2 / (2.0 * Sse)) * (-1.0 + math.sqrt(1.0 + (2.0 * Sse / (r * Ssu)) ** 2))


def goodman_allowable_shear_amplitude(r: float, Sse: float, Ssu: float) -> float:
    return r * Sse * Ssu / (r * Ssu + Sse)


def sines_nf(Ssa: float, tau_a: float) -> float:
    return Ssa / tau_a


def figure_of_merit(relative_cost: float, d: float, D: float, Nt: float, include_gamma: bool = False, gamma: Optional[float] = None) -> float:
    value = -(relative_cost) * math.pi ** 2 * d ** 2 * Nt * D / 4.0
    if include_gamma and gamma is not None:
        value *= gamma
    return value


def safe_eval_expr(expr: str, vars_map: Dict[str, float]) -> float:
    allowed = {"sqrt": math.sqrt, "pi": math.pi}
    allowed.update(vars_map)
    return float(eval(expr, {"__builtins__": {}}, allowed))
