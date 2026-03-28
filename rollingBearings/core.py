from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import math

try:
    from .in_out import load_csv_dicts
    from .utils import (
        WeibullParams,
        ensure_positive,
        ensure_nonnegative,
        interp_piecewise,
    )
except ImportError:
    from in_out import load_csv_dicts
    from utils import (
        WeibullParams,
        ensure_positive,
        ensure_nonnegative,
        interp_piecewise,
    )


class RollingBearingError(Exception):
    pass


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

_FORCE_TO_NEWTON = {
    "N": 1.0,
    "kN": 1000.0,
    "lbf": 4.4482216152605,
}

def _norm_force_unit(unit: str) -> str:
    u = unit.strip()
    if u not in _FORCE_TO_NEWTON:
        raise ValueError(f"Unsupported force unit: {unit!r}")
    return u

def convert_force(value: float, from_unit: str, to_unit: str) -> float:
    from_u = _norm_force_unit(from_unit)
    to_u = _norm_force_unit(to_unit)
    value_n = value * _FORCE_TO_NEWTON[from_u]
    return value_n / _FORCE_TO_NEWTON[to_u]


class LifeModel:
    @staticmethod
    def rating_life_multiple(hours: float, speed_rpm: float, LR_rev: float) -> float:
        ensure_positive("hours", hours)
        ensure_positive("speed_rpm", speed_rpm)
        ensure_positive("LR_rev", LR_rev)
        return hours * speed_rpm * 60.0 / LR_rev

    @staticmethod
    def life_hours_from_xD(xD: float, speed_rpm: float, LR_rev: float) -> float:
        ensure_positive("xD", xD)
        ensure_positive("speed_rpm", speed_rpm)
        ensure_positive("LR_rev", LR_rev)
        return xD * LR_rev / (speed_rpm * 60.0)

    @staticmethod
    def individual_reliability_from_system(
        system_reliability: float,
        bearing_count: int,
    ) -> float:
        if not (0.0 < system_reliability < 1.0):
            raise ValueError("system_reliability must be between 0 and 1")
        if bearing_count <= 0:
            raise ValueError("bearing_count must be positive")
        return system_reliability ** (1.0 / bearing_count)

    @staticmethod
    def basic_catalog_c10(FD: float, xD: float, a: float) -> float:
        ensure_positive("FD", FD)
        ensure_positive("xD", xD)
        ensure_positive("a", a)
        return FD * (xD ** (1.0 / a))

    @staticmethod
    def c10_required(
        FD: float,
        af: float,
        xD: float,
        weibull: WeibullParams,
        reliability: float,
    ) -> float:
        """
        Reliability-adjusted catalog requirement path (Eq. 11-10 family).

        IMPORTANT:
        FD and returned C10 must be in the SAME force unit system as the catalog.
        """
        ensure_positive("FD", FD)
        ensure_positive("af", af)
        ensure_positive("xD", xD)
        if not (0.0 < reliability < 1.0):
            raise ValueError("reliability must be between 0 and 1")
        base = xD / (
            ((weibull.theta - weibull.x0) * (1.0 - reliability) ** (1.0 / weibull.b))
            + weibull.x0
        )
        return af * FD * (base ** (1.0 / weibull.a))

    @staticmethod
    def reliability_from_c10_approx(
        FD: float,
        af: float,
        xD: float,
        weibull: WeibullParams,
        C10: float,
    ) -> float:
        ensure_positive("af", af)
        ensure_positive("xD", xD)
        ensure_positive("C10", C10)
        if FD <= 0.0:
            return 1.0
        val = ((xD * ((af * FD) / C10) ** weibull.a) - weibull.x0) / (
            weibull.theta - weibull.x0
        )
        return max(0.0, min(1.0, 1.0 - (val ** weibull.b)))

    @staticmethod
    def tapered_reliability_approx(
        FD: float,
        af: float,
        xD: float,
        C10: float,
    ) -> float:
        ensure_positive("af", af)
        ensure_positive("xD", xD)
        ensure_positive("C10", C10)
        if FD <= 0.0:
            return 1.0
        return max(
            0.0,
            min(
                1.0,
                1.0 - (xD / (4.48 * (C10 / (af * FD)) ** (10.0 / 3.0))) ** (3.0 / 2.0),
            ),
        )


class Example11_1CatalogC10Solver:
    def solve(
        self,
        *,
        FD: float,
        hours: float,
        speed_rpm: float,
        a: float = 3.0,
        LR_rev: float = 1_000_000.0,
    ) -> Dict[str, Any]:
        xD = LifeModel.rating_life_multiple(
            hours=hours,
            speed_rpm=speed_rpm,
            LR_rev=LR_rev,
        )
        c10 = LifeModel.basic_catalog_c10(FD=FD, xD=xD, a=a)
        return {
            "problem_type": "catalog_c10_basic",
            "equation_path": "Eq. 11-3 / Example 11-1",
            "FD": FD,
            "a": a,
            "LR_rev": LR_rev,
            "xD": xD,
            "C10_required": c10,
        }


class Example11_3CatalogC10Solver:
    def solve(
        self,
        *,
        FD: float,
        af: float,
        hours: float,
        speed_rpm: float,
        reliability: float,
        weibull: WeibullParams,
        LR_rev: float = 1_000_000.0,
    ) -> Dict[str, Any]:
        xD = LifeModel.rating_life_multiple(
            hours=hours,
            speed_rpm=speed_rpm,
            LR_rev=LR_rev,
        )
        c10 = LifeModel.c10_required(
            FD=FD,
            af=af,
            xD=xD,
            weibull=weibull,
            reliability=reliability,
        )
        return {
            "problem_type": "catalog_c10_reliable",
            "equation_path": "Eq. 11-10 / Example 11-3",
            "FD": FD,
            "af": af,
            "reliability": reliability,
            "weibull": weibull.to_dict(),
            "LR_rev": LR_rev,
            "xD": xD,
            "C10_required": c10,
        }


class BallFactorTable:
    def __init__(self) -> None:
        rows = load_csv_dicts("equivalent_radial_load.csv")
        self.rows = []
        for r in rows:
            self.rows.append(
                {
                    "bearing_family": r["bearing_family"].strip(),
                    "Fa_over_C0": float(r["Fa_over_C0"]),
                    "e": float(r["e"]),
                    "X1": float(r["X1"]),
                    "Y1": float(r["Y1"]),
                    "X2": float(r["X2"]),
                    "Y2": float(r["Y2"]),
                }
            )

    def _family_rows(self, bearing_family: str) -> List[Dict[str, float]]:
        hits = [
            r
            for r in self.rows
            if r["bearing_family"].lower() == bearing_family.lower()
        ]
        if not hits:
            raise RollingBearingError(f"Unknown bearing_family={bearing_family!r}")
        return sorted(hits, key=lambda r: r["Fa_over_C0"])

    @staticmethod
    def _clamped_interp(xs: List[float], ys: List[float], x: float) -> float:
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        return interp_piecewise(xs, ys, x)

    def interpolate(self, bearing_family: str, Fa_over_C0: float) -> Dict[str, float]:
        rows = self._family_rows(bearing_family)
        xs = [r["Fa_over_C0"] for r in rows]
        out = {}
        for key in ("e", "X1", "Y1", "X2", "Y2"):
            ys = [r[key] for r in rows]
            out[key] = self._clamped_interp(xs, ys, Fa_over_C0)
        out["Fa_over_C0"] = Fa_over_C0
        out["bearing_family"] = bearing_family
        return out


class CatalogTable:
    def __init__(
        self,
        filename: str,
        required_numeric_fields: Optional[List[str]] = None,
    ) -> None:
        self.filename = filename
        self.rows = load_csv_dicts(filename)
        self.required_numeric_fields = required_numeric_fields or []
        self._validate_rows()

    @staticmethod
    def _to_float(value: str) -> float:
        value = value.strip()
        if value == "":
            return float("nan")
        return float(value)

    def _validate_rows(self) -> None:
        for i, row in enumerate(self.rows, start=2):
            for field in self.required_numeric_fields:
                try:
                    self._to_float(row[field])
                except Exception as exc:
                    raise RollingBearingError(
                        f"Malformed catalog row in {self.filename} at CSV line {i}: "
                        f"field {field!r} has value {row.get(field)!r}"
                    ) from exc

    def select_first_by_c10(
        self,
        c10_required: float,
        allowed_families: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        ensure_positive("c10_required", c10_required)
        best = []
        for r in self.rows:
            fam_ok = True
            if allowed_families:
                fam_ok = r.get("bearing_family", "").lower() in {
                    x.lower() for x in allowed_families
                }
            if not fam_ok:
                continue
            c10 = self._to_float(r["C10_N"])
            if c10 >= c10_required:
                best.append((c10, r))
        if not best:
            raise RollingBearingError(
                f"No catalog entry found with C10 >= {c10_required}"
            )
        best.sort(key=lambda item: item[0])
        return best[0][1]


class BallBearingCatalog(CatalogTable):
    def __init__(self) -> None:
        super().__init__(
            "ball_bearings.csv",
            required_numeric_fields=["bore_mm", "OD_mm", "width_mm", "C0_N", "C10_N"],
        )


class CylindricalRollerCatalog(CatalogTable):
    def __init__(self) -> None:
        super().__init__(
            "cylindrical_roller_bearings.csv",
            required_numeric_fields=["bore_mm", "OD_mm", "width_mm", "C10_N", "C0_N"],
        )


class TaperedRollerCatalog(CatalogTable):
    def __init__(self) -> None:
        super().__init__(
            "timken_tapered_roller_bearings.csv",
            required_numeric_fields=[
                "bore_mm",
                "OD_mm",
                "width_mm",
                "C10_N",
                "C0_thrust_N",
                "K",
            ],
        )

    def select_first_by_c10_and_bore(
        self,
        c10_required: float,
        bore_mm: Optional[float] = None,
        bore_tol_mm: float = 1.0,
    ) -> Dict[str, Any]:
        ensure_positive("c10_required", c10_required)
        candidates = []
        for r in self.rows:
            c10 = float(r["C10_N"])
            if c10 < c10_required:
                continue
            if bore_mm is not None:
                d = float(r["bore_mm"])
                if abs(d - bore_mm) > bore_tol_mm:
                    continue
            candidates.append((c10, r))
        if not candidates:
            raise RollingBearingError(
                f"No tapered roller entry found with C10 >= {c10_required} and bore filter {bore_mm}"
            )
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]


@dataclass
class BallEquivalentLoadResult:
    Fe: float
    Fa_over_C0: float
    Fa_over_VFr: float
    e: float
    X_used: float
    Y_used: float
    regime: str


class BallBearingCalculator:
    def __init__(self) -> None:
        self.factors = BallFactorTable()

    def equivalent_dynamic_load(
        self,
        bearing_family: str,
        Fa: float,
        Fr: float,
        C0: float,
        V: float = 1.0,
    ) -> BallEquivalentLoadResult:
        ensure_nonnegative("Fa", Fa)
        ensure_positive("Fr", Fr)
        ensure_positive("C0", C0)
        ensure_positive("V", V)

        fa_over_c0 = Fa / C0
        lookup = self.factors.interpolate(
            bearing_family=bearing_family,
            Fa_over_C0=fa_over_c0,
        )
        fa_over_vfr = Fa / (V * Fr)

        if fa_over_vfr <= lookup["e"]:
            X_used = lookup["X1"]
            Y_used = lookup["Y1"]
            regime = "Fa/(VFr) <= e"
        else:
            X_used = lookup["X2"]
            Y_used = lookup["Y2"]
            regime = "Fa/(VFr) > e"

        Fe = X_used * V * Fr + Y_used * Fa
        return BallEquivalentLoadResult(
            Fe=Fe,
            Fa_over_C0=fa_over_c0,
            Fa_over_VFr=fa_over_vfr,
            e=lookup["e"],
            X_used=X_used,
            Y_used=Y_used,
            regime=regime,
        )

    def estimate_l10_life_hours(
        self,
        *,
        C10: float,
        Fe: float,
        speed_rpm: float,
        a: float = 3.0,
        LR_rev: float = 1_000_000.0,
    ) -> float:
        ensure_positive("C10", C10)
        ensure_positive("Fe", Fe)
        ensure_positive("speed_rpm", speed_rpm)
        ensure_positive("a", a)
        xD = (C10 / Fe) ** a
        return LifeModel.life_hours_from_xD(
            xD=xD,
            speed_rpm=speed_rpm,
            LR_rev=LR_rev,
        )




def _catalog_c0_to_load_units(c0_catalog: float, load_unit: str, catalog_rating_unit: str) -> float:
    return convert_force(c0_catalog, catalog_rating_unit, load_unit)


class CylindricalRollerSelector:
    def __init__(self) -> None:
        self.catalog = CylindricalRollerCatalog()

    def select(
        self,
        *,
        Fr: float,
        af: float,
        speed_rpm: float,
        hours: float,
        target_reliability: Optional[float] = None,
        system_reliability: Optional[float] = None,
        bearing_count: int = 1,
        derived_reliability_digits: Optional[int] = 2,
        weibull: Optional[WeibullParams] = None,
        load_unit: str = "lbf",
        catalog_rating_unit: str = "N",
        LR_rev: float = 1_000_000.0,
    ) -> Dict[str, Any]:
        if system_reliability is not None:
            RD_raw = LifeModel.individual_reliability_from_system(
                system_reliability,
                bearing_count,
            )
            RD = (
                round(RD_raw, derived_reliability_digits)
                if derived_reliability_digits is not None
                else RD_raw
            )
        elif target_reliability is not None:
            RD_raw = target_reliability
            RD = target_reliability
        else:
            raise ValueError(
                "Either target_reliability or system_reliability must be provided"
            )

        weibull = weibull or WeibullParams(
            a=10.0 / 3.0,
            x0=0.02,
            theta_minus_x0=4.439,
            b=1.483,
        )

        xD = LifeModel.rating_life_multiple(
            hours=hours,
            speed_rpm=speed_rpm,
            LR_rev=LR_rev,
        )

        Fr_catalog = convert_force(Fr, load_unit, catalog_rating_unit)
        c10 = LifeModel.c10_required(
            FD=Fr_catalog,
            af=af,
            xD=xD,
            weibull=weibull,
            reliability=RD,
        )
        selected = self.catalog.select_first_by_c10(c10_required=c10)

        return {
            "problem_type": "select_cylindrical_roller",
            "xD": xD,
            "individual_reliability_raw": RD_raw,
            "individual_reliability_used": RD,
            "weibull": weibull.to_dict(),
            "load_unit": load_unit,
            "catalog_rating_unit": catalog_rating_unit,
            "Fr_input": Fr,
            "Fr_catalog_units": Fr_catalog,
            "C10_required": c10,
            "selected": selected,
        }


class AngularContactBearingSelector:
    def __init__(self) -> None:
        self.ball_calc = BallBearingCalculator()
        self.catalog = BallBearingCatalog()

    def select(
        self,
        *,
        Fr: float,
        Fa: float,
        V: float,
        speed_rpm: float,
        hours: float,
        target_reliability: Optional[float] = None,
        system_reliability: Optional[float] = None,
        bearing_count: int = 1,
        derived_reliability_digits: Optional[int] = 2,
        af: float,
        LR_rev: float,
        weibull: Optional[WeibullParams] = None,
        initial_family: str = "angular_contact",
        initial_C0_guess: float = 12000.0,
        initial_C0_unit: Optional[str] = None,
        initial_guess_mode: str = "table_midpoint",
        initial_X2_guess: float = 0.56,
        initial_Y2_guess: float = 1.63,
        load_unit: str = "lbf",
        catalog_rating_unit: str = "N",
        max_iter: int = 20,
    ) -> Dict[str, Any]:
        if system_reliability is not None:
            RD_raw = LifeModel.individual_reliability_from_system(
                system_reliability,
                bearing_count,
            )
            RD = (
                round(RD_raw, derived_reliability_digits)
                if derived_reliability_digits is not None
                else RD_raw
            )
        elif target_reliability is not None:
            RD_raw = target_reliability
            RD = target_reliability
        else:
            raise ValueError(
                "Either target_reliability or system_reliability must be provided"
            )

        weibull = weibull or WeibullParams(
            a=3.0,
            x0=0.02,
            theta_minus_x0=4.439,
            b=1.483,
        )

        xD = LifeModel.rating_life_multiple(
            hours=hours,
            speed_rpm=speed_rpm,
            LR_rev=LR_rev,
        )
        previous_part = None
        init_c0_unit = initial_C0_unit or catalog_rating_unit
        C0_load_units = convert_force(initial_C0_guess, init_c0_unit, load_unit)
        history = []

        for it in range(1, max_iter + 1):
            if it == 1 and initial_guess_mode == "table_midpoint" and Fa > 0.0:
                # Trial values live in Table 11-1 dimensionless factors, so only the
                # loads need unit conversion before Eq. 11-10.
                Fe_input = initial_X2_guess * V * Fr + initial_Y2_guess * Fa
                Fe_catalog = convert_force(Fe_input, load_unit, catalog_rating_unit)
                eq = BallEquivalentLoadResult(
                    Fe=Fe_catalog,
                    Fa_over_C0=Fa / C0_load_units,
                    Fa_over_VFr=Fa / (V * Fr),
                    e=float("nan"),
                    X_used=initial_X2_guess,
                    Y_used=initial_Y2_guess,
                    regime="initial_midpoint_guess",
                )
            else:
                # Table decision ratios use consistent force ratios, so unit system
                # cancels out. But Eq. 11-10 below must use catalog units.
                eq_input = self.ball_calc.equivalent_dynamic_load(
                    bearing_family=initial_family,
                    Fa=Fa,
                    Fr=Fr,
                    C0=C0_load_units,
                    V=V,
                )
                eq = BallEquivalentLoadResult(
                    Fe=convert_force(eq_input.Fe, load_unit, catalog_rating_unit),
                    Fa_over_C0=eq_input.Fa_over_C0,
                    Fa_over_VFr=eq_input.Fa_over_VFr,
                    e=eq_input.e,
                    X_used=eq_input.X_used,
                    Y_used=eq_input.Y_used,
                    regime=eq_input.regime,
                )

            c10_req = LifeModel.c10_required(
                FD=eq.Fe,
                af=af,
                xD=xD,
                weibull=weibull,
                reliability=RD,
            )
            selected = self.catalog.select_first_by_c10(
                c10_required=c10_req,
                allowed_families=["angular_contact"],
            )
            selected_c0_catalog = float(selected["C0_N"])
            C0_load_units = _catalog_c0_to_load_units(
                selected_c0_catalog,
                load_unit=load_unit,
                catalog_rating_unit=catalog_rating_unit,
            )

            history.append(
                {
                    "iteration": it,
                    "Fe": eq.Fe,
                    "Fa_over_C0": eq.Fa_over_C0,
                    "e": eq.e,
                    "X_used": eq.X_used,
                    "Y_used": eq.Y_used,
                    "C10_required": c10_req,
                    "selected_part": selected["part_no"],
                    "selected_C10": float(selected["C10_N"]),
                    "selected_C0": selected_c0_catalog,
                }
            )

            if selected["part_no"] == previous_part:
                return {
                    "status": "converged",
                    "iterations": history,
                    "selected": selected,
                    "xD": xD,
                    "individual_reliability_raw": RD_raw,
                    "individual_reliability_used": RD,
                    "weibull": weibull.to_dict(),
                    "load_unit": load_unit,
                    "catalog_rating_unit": catalog_rating_unit,
                }
            previous_part = selected["part_no"]

        return {
            "status": "max_iter_reached",
            "iterations": history,
            "selected": history[-1]["selected_part"] if history else None,
            "xD": xD,
            "individual_reliability_raw": RD_raw,
            "individual_reliability_used": RD,
            "weibull": weibull.to_dict(),
            "load_unit": load_unit,
            "catalog_rating_unit": catalog_rating_unit,
        }


class Example11_7CylindricalRollerSolver:
    def __init__(self) -> None:
        self.selector = CylindricalRollerSelector()

    def solve(
        self,
        *,
        Fr: float,
        af: float = 1.2,
        speed_rpm: float,
        hours: float = 10_000.0,
        system_reliability: float = 0.96,
        bearing_count: int = 4,
        derived_reliability_digits: Optional[int] = 2,
        weibull: Optional[WeibullParams] = None,
        load_unit: str = "lbf",
        catalog_rating_unit: str = "N",
        LR_rev: float = 1_000_000.0,
    ) -> Dict[str, Any]:
        return self.selector.select(
            Fr=Fr,
            af=af,
            speed_rpm=speed_rpm,
            hours=hours,
            system_reliability=system_reliability,
            bearing_count=bearing_count,
            derived_reliability_digits=derived_reliability_digits,
            weibull=weibull,
            load_unit=load_unit,
            catalog_rating_unit=catalog_rating_unit,
            LR_rev=LR_rev,
        )


class Example11_7AngularContactSolver:
    def __init__(self) -> None:
        self.selector = AngularContactBearingSelector()

    def solve(
        self,
        *,
        Fr: float,
        Fa: float,
        af: float = 1.2,
        V: float = 1.0,
        speed_rpm: float,
        hours: float = 10_000.0,
        system_reliability: float = 0.96,
        bearing_count: int = 4,
        derived_reliability_digits: Optional[int] = 2,
        weibull: Optional[WeibullParams] = None,
        LR_rev: float = 1_000_000.0,
        initial_C0_guess: float = 35_500.0,
        initial_C0_unit: Optional[str] = None,
        initial_guess_mode: str = "table_midpoint",
        initial_X2_guess: float = 0.56,
        initial_Y2_guess: float = 1.63,
        load_unit: str = "lbf",
        catalog_rating_unit: str = "N",
    ) -> Dict[str, Any]:
        return self.selector.select(
            Fr=Fr,
            Fa=Fa,
            V=V,
            speed_rpm=speed_rpm,
            hours=hours,
            system_reliability=system_reliability,
            bearing_count=bearing_count,
            derived_reliability_digits=derived_reliability_digits,
            af=af,
            LR_rev=LR_rev,
            weibull=weibull,
            initial_C0_guess=initial_C0_guess,
            initial_C0_unit=initial_C0_unit,
            initial_guess_mode=initial_guess_mode,
            initial_X2_guess=initial_X2_guess,
            initial_Y2_guess=initial_Y2_guess,
            load_unit=load_unit,
            catalog_rating_unit=catalog_rating_unit,
        )


class TaperedBearingPairSelector:
    def __init__(self) -> None:
        self.catalog = TaperedRollerCatalog()

    @staticmethod
    def induced_load(Fr: float, K: float) -> float:
        ensure_nonnegative("Fr", Fr)
        ensure_positive("K", K)
        return 0.47 * Fr / K

    @staticmethod
    def equivalent_loads_direct_mount(
        *,
        FrA: float,
        FrB: float,
        FiA: float,
        FiB: float,
        Fae: float,
        KA: float,
        KB: float,
    ) -> Dict[str, Any]:
        if FiA <= FiB + Fae:
            return {
                "FeA": 0.4 * FrA + KA * (FiB + Fae),
                "FeB": FrB,
                "regime": "11-19",
            }
        return {
            "FeA": FrA,
            "FeB": 0.4 * FrB + KB * (FiA - Fae),
            "regime": "11-20",
        }

    def select_direct_pair(
        self,
        *,
        FrA: float,
        FrB: float,
        Fae: float,
        speed_rpm: float,
        hours: float,
        reliability_goal: float,
        af: float = 1.0,
        shaft_bore_mm: Optional[float] = None,
        K_initial: float = 1.5,
        LR_rev: float = 90_000_000.0,
        max_iter: int = 10,
    ) -> Dict[str, Any]:
        xD = LifeModel.rating_life_multiple(
            hours=hours,
            speed_rpm=speed_rpm,
            LR_rev=LR_rev,
        )
        RD_guess = math.sqrt(reliability_goal)
        KA = K_initial
        KB = K_initial
        chosen = None
        history = []

        for it in range(1, max_iter + 1):
            FiA = self.induced_load(Fr=FrA, K=KA)
            FiB = self.induced_load(Fr=FrB, K=KB)
            eq = self.equivalent_loads_direct_mount(
                FrA=FrA, FrB=FrB, FiA=FiA, FiB=FiB, Fae=Fae, KA=KA, KB=KB
            )
            weibull = WeibullParams(a=10.0 / 3.0, x0=0.0, theta_minus_x0=4.48, b=1.5)
            c10_A_req = LifeModel.c10_required(
                FD=eq["FeA"],
                af=af,
                xD=xD,
                weibull=weibull,
                reliability=RD_guess,
            )
            c10_B_req = LifeModel.c10_required(
                FD=eq["FeB"],
                af=af,
                xD=xD,
                weibull=weibull,
                reliability=RD_guess,
            )
            sel_A = self.catalog.select_first_by_c10_and_bore(
                c10_required=c10_A_req,
                bore_mm=shaft_bore_mm,
            )
            sel_B = self.catalog.select_first_by_c10_and_bore(
                c10_required=c10_B_req,
                bore_mm=shaft_bore_mm,
            )
            pair = sel_A if float(sel_A["C10_N"]) >= float(sel_B["C10_N"]) else sel_B
            KA = float(pair["K"])
            KB = float(pair["K"])
            C10_pair = float(pair["C10_N"])
            RA = LifeModel.tapered_reliability_approx(
                FD=eq["FeA"], af=af, xD=xD, C10=C10_pair
            )
            RB = LifeModel.tapered_reliability_approx(
                FD=eq["FeB"], af=af, xD=xD, C10=C10_pair
            )
            R_total = RA * RB
            history.append(
                {
                    "iteration": it,
                    "FiA": FiA,
                    "FiB": FiB,
                    "FeA": eq["FeA"],
                    "FeB": eq["FeB"],
                    "regime": eq["regime"],
                    "c10_A_required": c10_A_req,
                    "c10_B_required": c10_B_req,
                    "selected_cone": pair["cone"],
                    "selected_cup": pair["cup"],
                    "selected_C10": C10_pair,
                    "selected_K": KA,
                    "RA": RA,
                    "RB": RB,
                    "R_total": R_total,
                    "decision": (
                        "accept" if R_total >= reliability_goal else "iterate_up"
                    ),
                }
            )
            same_as_before = (
                chosen is not None
                and chosen["cone"] == pair["cone"]
                and chosen["cup"] == pair["cup"]
            )
            chosen = pair
            if R_total >= reliability_goal and same_as_before:
                return {
                    "status": "converged",
                    "xD": xD,
                    "iterations": history,
                    "selected_pair": pair,
                }
            if R_total >= reliability_goal and it >= 2:
                return {
                    "status": "accepted_on_reliability",
                    "xD": xD,
                    "iterations": history,
                    "selected_pair": pair,
                }
            RD_guess = math.sqrt(max(reliability_goal, R_total))
        return {
            "status": "max_iter_reached",
            "xD": xD,
            "iterations": history,
            "selected_pair": chosen,
        }

    def solve_external_thrust_only(
        self,
        *,
        Fae: float,
        speed_rpm: float,
        hours: float,
        reliability_goal: float,
        af: float = 1.0,
        shaft_bore_mm: Optional[float] = None,
        LR_rev: float = 90_000_000.0,
    ) -> Dict[str, Any]:
        xD = LifeModel.rating_life_multiple(
            hours=hours,
            speed_rpm=speed_rpm,
            LR_rev=LR_rev,
        )
        weibull = WeibullParams(a=10.0 / 3.0, x0=0.0, theta_minus_x0=4.48, b=1.5)
        req = LifeModel.c10_required(
            FD=Fae,
            af=af,
            xD=xD,
            weibull=weibull,
            reliability=reliability_goal,
        )
        sel = self.catalog.select_first_by_c10_and_bore(
            c10_required=req,
            bore_mm=shaft_bore_mm,
        )
        C10 = float(sel["C10_N"])
        RA = LifeModel.tapered_reliability_approx(FD=Fae, af=af, xD=xD, C10=C10)
        return {
            "xD": xD,
            "required_C10": req,
            "selected_pair": sel,
            "RA": RA,
            "RB": 1.0,
            "R_total": RA,
        }