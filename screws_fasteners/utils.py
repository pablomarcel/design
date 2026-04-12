from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, is_dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PACKAGE_ROOT = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_ROOT / "data"
IN_DIR = PACKAGE_ROOT / "in"
OUT_DIR = PACKAGE_ROOT / "out"


class ScrewsFastenersError(Exception):
    """Base package exception."""


class DataLookupError(ScrewsFastenersError):
    """Raised when a required table lookup fails."""


class ValidationError(ScrewsFastenersError):
    """Raised when inputs are invalid or incomplete."""


MATERIAL_ALIASES = {
    "steel": "steel",
    "gray cast iron": "gray_cast_iron",
    "grey cast iron": "gray_cast_iron",
    "cast iron, gray": "gray_cast_iron",
    "aluminum": "aluminum",
    "copper": "copper",
    "general": "general_expression",
    "general expression": "general_expression",
}


THREAD_MAJOR_DIAMETER_ALIASES = (
    "nominal_major_diameter_in",
    "major_diameter_in",
    "nominal_size_in",
    "diameter_in",
)

THREAD_SERIES_ALIASES = ("series", "thread_series")
THREAD_TENSILE_AREA_ALIASES = ("tensile_stress_area_in2", "At_in2", "tensile_area_in2")
THREAD_TPI_ALIASES = ("threads_per_inch", "threads_per_inch_N", "tpi")


WASHER_SIZE_ALIASES = ("washer_size_in", "nominal_size_in", "fastener_nominal_size_in")
WASHER_OD_ALIASES = ("diameter_od_in", "od_in", "outside_diameter_in")
WASHER_ID_ALIASES = ("diameter_id_in", "id_in", "inside_diameter_in")
WASHER_THICKNESS_ALIASES = ("thickness_in", "thickness")


MATERIAL_NAME_ALIASES = ("material", "material_used", "name")
MATERIAL_E_PSI_ALIASES = ("E_psi", "elastic_modulus_psi")
MATERIAL_E_MPSI_ALIASES = ("elastic_modulus_Mpsi", "E_Mpsi")
MATERIAL_E_GPA_ALIASES = ("elastic_modulus_GPa", "E_GPa")


PROOF_GRADE_ALIASES = ("sae_grade_no", "grade", "sae_grade")
PROOF_SIZE_RANGE_ALIASES = ("size_range_inclusive_in", "size_range_in")
PROOF_STRENGTH_ALIASES = ("minimum_proof_strength_kpsi", "proof_strength_kpsi", "Sp_kpsi")
TENSILE_STRENGTH_ALIASES = ("minimum_tensile_strength_kpsi", "tensile_strength_kpsi", "Sut_kpsi")
YIELD_STRENGTH_ALIASES = ("minimum_yield_strength_kpsi", "yield_strength_kpsi", "Sy_kpsi")

ENDURANCE_GRADE_ALIASES = ("grade_or_class", "sae_grade", "sae_grade_no", "grade")
ENDURANCE_SIZE_RANGE_ALIASES = ("size_range", "size_range_in", "size_range_inclusive_in")
ENDURANCE_STRENGTH_ALIASES = ("endurance_strength", "endurance_strength_kpsi", "Se_kpsi")


def ensure_dirs() -> None:
    IN_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def normalize_material_name(name: str) -> str:
    key = str(name).strip().lower()
    return MATERIAL_ALIASES.get(key, key.replace(" ", "_"))


def _coerce(value: str) -> Any:
    raw = value.strip()
    if raw == "":
        return ""
    for caster in (int, float):
        try:
            if caster is int and any(ch in raw.lower() for ch in ".e"):
                continue
            return caster(raw)
        except Exception:
            pass
    return raw


def _candidate_paths(filename: str) -> List[Path]:
    return [DATA_DIR / filename, PACKAGE_ROOT / filename]


def _resolve_data_path(filename: str) -> Path:
    for path in _candidate_paths(filename):
        if path.exists():
            return path
    tried = ", ".join(str(p) for p in _candidate_paths(filename))
    raise DataLookupError(f"Required data file not found: {filename}. Looked in: {tried}")


def load_csv_rows(filename: str) -> List[Dict[str, Any]]:
    path = _resolve_data_path(filename)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [{k: _coerce(v) for k, v in row.items()} for row in reader]


def _first_present(row: Dict[str, Any], names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return default


def _parse_fractional_size(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        pass
    try:
        parts = text.split()
        total = sum(Fraction(part) for part in parts)
        return float(total)
    except Exception:
        return None


def _parse_fastener_size_and_type(text: Any) -> Tuple[Optional[float], Optional[str]]:
    if text is None:
        return None, None
    raw = str(text).strip()
    if not raw:
        return None, None
    parts = raw.split()
    washer_type = None
    if parts and parts[-1].upper() in {"N", "W"}:
        washer_type = parts[-1].upper()
        parts = parts[:-1]
    size_text = " ".join(parts)
    if size_text.startswith("#"):
        return None, washer_type
    return _parse_fractional_size(size_text), washer_type


def _grade_matches(row_value: Any, requested_grade: Any) -> bool:
    row_text = str(row_value).strip()
    req_text = str(requested_grade).strip()
    if row_text == req_text:
        return True
    try:
        return float(row_text) == float(req_text)
    except Exception:
        return False


def _size_in_range(size_in: float, range_text: Any) -> bool:
    if range_text in (None, ""):
        return False
    raw = str(range_text).strip().replace("–", "-").replace("—", "-")
    if "-" not in raw:
        bound = _parse_fractional_size(raw)
        return bound is not None and abs(float(size_in) - float(bound)) < 1e-12
    left, right = raw.split("-", 1)
    lo = _parse_fractional_size(left)
    hi = _parse_fractional_size(right)
    if lo is None or hi is None:
        return False
    return float(lo) <= float(size_in) <= float(hi)


def find_thread_row(size_in: float, series: str, threads_per_inch: Optional[int] = None) -> Dict[str, Any]:
    series = str(series).strip().upper()
    rows = load_csv_rows("table_8_2.csv")
    prefix_map = {"UNC": "unc", "UNF": "unf"}

    for row in rows:
        row_size = _first_present(row, THREAD_MAJOR_DIAMETER_ALIASES)
        if row_size is None:
            continue
        if abs(float(row_size) - float(size_in)) >= 1e-9:
            continue

        prefix = prefix_map.get(series)
        if prefix and f"{prefix}_tensile_stress_area_At_in2" in row:
            row_tpi = row.get(f"{prefix}_threads_per_inch_N")
            if threads_per_inch is not None and str(row_tpi).strip() not in {"", str(int(threads_per_inch))}:
                continue
            tensile_area = row.get(f"{prefix}_tensile_stress_area_At_in2")
            minor_area = row.get(f"{prefix}_minor_diameter_area_Ar_in2")
            if tensile_area in (None, ""):
                break
            canonical = dict(row)
            canonical["nominal_major_diameter_in"] = float(row_size)
            canonical["series"] = series
            canonical["threads_per_inch"] = row_tpi
            canonical["tensile_stress_area_in2"] = float(tensile_area)
            if minor_area not in (None, ""):
                canonical["minor_diameter_area_in2"] = float(minor_area)
            return canonical

        row_series = _first_present(row, THREAD_SERIES_ALIASES)
        if row_series is None or str(row_series).strip().upper() != series:
            continue
        row_tpi = _first_present(row, THREAD_TPI_ALIASES)
        if threads_per_inch is not None and row_tpi not in (None, "") and str(row_tpi).strip() != str(int(threads_per_inch)):
            continue
        tensile_area = _first_present(row, THREAD_TENSILE_AREA_ALIASES)
        if tensile_area is None:
            raise DataLookupError(
                f"Matched table_8_2.csv row for size {size_in} in and series {series}, but no tensile area column was found. "
                f"Available columns: {', '.join(row.keys())}"
            )
        canonical = dict(row)
        canonical.setdefault("nominal_major_diameter_in", float(row_size))
        canonical.setdefault("series", str(row_series).upper())
        canonical.setdefault("threads_per_inch", row_tpi)
        canonical.setdefault("tensile_stress_area_in2", float(tensile_area))
        return canonical

    detail = f" and {threads_per_inch} TPI" if threads_per_inch is not None else ""
    raise DataLookupError(f"No thread row found in table_8_2.csv for size {size_in} in and series {series}{detail}.")


def find_proof_strength_row(sae_grade: Any, nominal_diameter_in: float) -> Dict[str, Any]:
    rows = load_csv_rows("table_8_9.csv")
    for row in rows:
        row_grade = _first_present(row, PROOF_GRADE_ALIASES)
        row_range = _first_present(row, PROOF_SIZE_RANGE_ALIASES)
        if row_grade is None or row_range is None:
            continue
        if not _grade_matches(row_grade, sae_grade):
            continue
        if not _size_in_range(nominal_diameter_in, row_range):
            continue
        proof = _first_present(row, PROOF_STRENGTH_ALIASES)
        tensile = _first_present(row, TENSILE_STRENGTH_ALIASES)
        yield_strength = _first_present(row, YIELD_STRENGTH_ALIASES)
        canonical = dict(row)
        canonical.setdefault("sae_grade_no", row_grade)
        canonical.setdefault("size_range_inclusive_in", row_range)
        if proof not in (None, ""):
            canonical.setdefault("minimum_proof_strength_kpsi", float(proof))
        if tensile not in (None, ""):
            canonical.setdefault("minimum_tensile_strength_kpsi", float(tensile))
        if yield_strength not in (None, ""):
            canonical.setdefault("minimum_yield_strength_kpsi", float(yield_strength))
        return canonical
    raise DataLookupError(
        f"No proof-strength row found in table_8_9.csv for SAE grade {sae_grade} and nominal diameter {nominal_diameter_in} in."
    )


def find_washer_row(nominal_size_in: float, washer_type: str = "N") -> Dict[str, Any]:
    washer_type = str(washer_type).strip().upper()
    rows = load_csv_rows("table_a_32.csv")
    for row in rows:
        row_size = _first_present(row, WASHER_SIZE_ALIASES)
        row_type = row.get("washer_type")
        parsed_size, parsed_type = _parse_fastener_size_and_type(row.get("fastener_size"))

        if row_size is None:
            row_size = parsed_size
        if row_type in (None, ""):
            row_type = parsed_type

        if row_size is None:
            continue

        row_type_norm = str(row_type).strip().upper() if row_type not in (None, "") else ""
        if abs(float(row_size) - float(nominal_size_in)) < 1e-9 and row_type_norm == washer_type:
            canonical = dict(row)
            canonical.setdefault("nominal_size_in", float(row_size))
            canonical.setdefault("washer_type", row_type_norm)
            od = _first_present(row, WASHER_OD_ALIASES)
            idx = _first_present(row, WASHER_ID_ALIASES)
            thk = _first_present(row, WASHER_THICKNESS_ALIASES)
            if od is not None:
                canonical.setdefault("diameter_od_in", float(od))
            if idx is not None:
                canonical.setdefault("diameter_id_in", float(idx))
            if thk is not None:
                canonical.setdefault("thickness_in", float(thk))
            return canonical

    available = ", ".join(rows[0].keys()) if rows else "<empty table>"
    raise DataLookupError(
        f"No washer row found in table_a_32.csv for nominal size {nominal_size_in} in and washer type {washer_type}. "
        f"Available columns: {available}"
    )


def find_nut_dimensions_row(nominal_size_in: float) -> Dict[str, Any]:
    rows = load_csv_rows("table_a_31.csv")
    for row in rows:
        if str(row.get("system", "")).strip().lower() != "inch":
            continue
        row_size = row.get("nominal_size_in")
        if row_size in (None, ""):
            continue
        if abs(float(row_size) - float(nominal_size_in)) >= 1e-9:
            continue
        canonical = dict(row)
        for key in (
            "nominal_size_in",
            "width_W_value",
            "height_regular_hex_value",
            "height_thick_or_slotted_value",
            "height_jam_value",
        ):
            if canonical.get(key, "") not in (None, ""):
                canonical[key] = float(canonical[key])
        return canonical
    raise DataLookupError(f"No nut-dimensions row found in table_a_31.csv for nominal size {nominal_size_in} in.")


def find_preferred_fraction_size_ge(required_length_in: float) -> Dict[str, Any]:
    candidates = []
    for row in load_csv_rows("table_a_17.csv"):
        if str(row.get("section", "")).strip() != "fraction_of_inches":
            continue
        value = row.get("value")
        if value in (None, ""):
            continue
        value = float(value)
        if value + 1e-12 >= float(required_length_in):
            candidates.append({"label": row.get("label"), "value_in": value, "section": row.get("section")})
    if not candidates:
        raise DataLookupError(f"No preferred fractional length found in table_a_17.csv that is >= {required_length_in} in.")
    return min(candidates, key=lambda item: item["value_in"])


def find_gray_cast_iron_row(astm_number: Any) -> Dict[str, Any]:
    rows = load_csv_rows("table_a_24_gray_cast_iron.csv")
    for row in rows:
        if str(row.get("astm_number", "")).strip() != str(astm_number).strip():
            continue
        canonical = dict(row)
        for key in canonical:
            if canonical[key] not in (None, ""):
                try:
                    canonical[key] = float(canonical[key]) if "." in str(canonical[key]) else int(canonical[key])
                except Exception:
                    pass
        return canonical
    raise DataLookupError(f"No gray cast iron row found in table_a_24_gray_cast_iron.csv for ASTM number {astm_number}.")


def find_material_stiffness_row(material: str) -> Dict[str, Any]:
    target = normalize_material_name(material)
    rows = load_csv_rows("table_8_8.csv")
    for row in rows:
        material_name = _first_present(row, MATERIAL_NAME_ALIASES)
        if material_name is None:
            continue
        if normalize_material_name(str(material_name)) != target:
            continue

        E_psi = _first_present(row, MATERIAL_E_PSI_ALIASES)
        if E_psi in (None, ""):
            e_mpsi = _first_present(row, MATERIAL_E_MPSI_ALIASES)
            if e_mpsi not in (None, ""):
                E_psi = float(e_mpsi) * 1_000_000.0
        if E_psi in (None, ""):
            e_gpa = _first_present(row, MATERIAL_E_GPA_ALIASES)
            if e_gpa not in (None, ""):
                E_psi = float(e_gpa) * 145_037.73773
        if E_psi in (None, ""):
            raise DataLookupError(
                f"Matched material '{material}', but no elastic modulus column convertible to psi was found. "
                f"Available columns: {', '.join(row.keys())}"
            )

        canonical = dict(row)
        canonical.setdefault("material", str(material_name))
        canonical.setdefault("E_psi", float(E_psi))
        return canonical
    raise DataLookupError(f"No material row found in table_8_8.csv for material '{material}'.")



def find_endurance_strength_row(grade_or_class: Any, nominal_diameter_in: float) -> Dict[str, Any]:
    rows = load_csv_rows("table_8_17.csv")
    for row in rows:
        row_grade = _first_present(row, ENDURANCE_GRADE_ALIASES)
        row_range = _first_present(row, ENDURANCE_SIZE_RANGE_ALIASES)
        if row_grade is None or row_range is None:
            continue
        if not _grade_matches(row_grade, grade_or_class):
            continue
        if not _size_in_range(nominal_diameter_in, row_range):
            continue
        endurance = _first_present(row, ENDURANCE_STRENGTH_ALIASES)
        canonical = dict(row)
        canonical.setdefault("grade_or_class", row_grade)
        canonical.setdefault("size_range", row_range)
        if endurance not in (None, ""):
            canonical.setdefault("endurance_strength_kpsi", float(endurance))
        return canonical
    raise DataLookupError(
        f"No endurance-strength row found in table_8_17.csv for grade/class {grade_or_class} and nominal diameter {nominal_diameter_in} in."
    )

def math_exp_safe(x: float) -> float:
    try:
        return math.exp(x)
    except OverflowError as exc:
        raise ValidationError(f"Overflow while evaluating exp({x}).") from exc


def order_desc(values: Iterable[float]) -> List[float]:
    return sorted((float(v) for v in values), reverse=True)


def round_floats(obj: Any, digits: int = 6) -> Any:
    if isinstance(obj, float):
        return round(obj, digits)
    if is_dataclass(obj):
        return round_floats(asdict(obj), digits=digits)
    if isinstance(obj, dict):
        return {k: round_floats(v, digits=digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, digits=digits) for v in obj]
    return obj


def dump_json(data: Dict[str, Any], path: Path, pretty: bool = True) -> None:
    ensure_dirs()
    kwargs = {"ensure_ascii": False}
    if pretty:
        kwargs.update({"indent": 2, "sort_keys": False})
    with path.open("w", encoding="utf-8") as f:
        json.dump(round_floats(data), f, **kwargs)
        f.write("\n")


def format_number(value: Any, digits: int = 6) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
            return text if text not in {"-0", ""} else "0"
        return str(value)
    return str(value)


def format_engineering(value: float, unit: str = "", digits: int = 4) -> str:
    if value == 0:
        return f"0 {unit}".strip()
    exponent = int(math.floor(math.log10(abs(value)) / 3) * 3)
    exponent = max(min(exponent, 12), -12)
    scaled = value / (10 ** exponent)
    prefix_map = {
        -12: "p",
        -9: "n",
        -6: "µ",
        -3: "m",
        0: "",
        3: "k",
        6: "M",
        9: "G",
        12: "T",
    }
    prefix = prefix_map.get(exponent, f"e{exponent}")
    return f"{scaled:.{digits}g} {prefix}{unit}".strip()


def try_render_key_value_table(title: str, rows: List[tuple[str, Any]]) -> None:
    formatted_rows = [(str(key), format_number(value)) for key, value in rows]
    try:
        from rich import box
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(
            title=title,
            box=box.SIMPLE_HEAVY,
            header_style="bold",
            show_edge=True,
            pad_edge=True,
            expand=False,
        )
        table.add_column("Quantity", justify="left", no_wrap=True, min_width=42)
        table.add_column("Value", justify="right", no_wrap=True, min_width=16)
        for key, value in formatted_rows:
            table.add_row(key, value)
        console.print(table)
    except Exception:
        print(f"\n{title}")
        print("=" * len(title))
        width = max(len(key) for key, _ in formatted_rows) if formatted_rows else 10
        for key, value in formatted_rows:
            print(f"{key:<{width}}  {value:>16}")


def validate_positive(name: str, value: float) -> None:
    if float(value) <= 0:
        raise ValidationError(f"{name} must be > 0. Got {value}.")


def validate_nonnegative(name: str, value: float) -> None:
    if float(value) < 0:
        raise ValidationError(f"{name} must be >= 0. Got {value}.")
