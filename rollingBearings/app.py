from __future__ import annotations

from typing import Any, Dict

try:
    from .core import (
        BallBearingCalculator,
        AngularContactBearingSelector,
        CylindricalRollerCatalog,
        Example11_1CatalogC10Solver,
        Example11_3CatalogC10Solver,
        LifeModel,
        TaperedBearingPairSelector,
    )
    from .utils import WeibullParams
except ImportError:
    from core import (
        BallBearingCalculator,
        AngularContactBearingSelector,
        CylindricalRollerCatalog,
        Example11_1CatalogC10Solver,
        Example11_3CatalogC10Solver,
        LifeModel,
        TaperedBearingPairSelector,
    )
    from utils import WeibullParams


class RollingBearingsApp:
    def __init__(self) -> None:
        self.ball = BallBearingCalculator()
        self.angular_selector = AngularContactBearingSelector()
        self.cyl_catalog = CylindricalRollerCatalog()
        self.tapered_selector = TaperedBearingPairSelector()
        self.ex11_1_solver = Example11_1CatalogC10Solver()
        self.ex11_3_solver = Example11_3CatalogC10Solver()

    def solve_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        kind = payload["problem_type"]
        if kind == "catalog_c10_basic":
            return self.ex11_1_solver.solve(
                FD=payload["FD"],
                hours=payload["hours"],
                speed_rpm=payload["speed_rpm"],
                a=payload.get("a", 3.0),
                LR_rev=payload.get("LR_rev", 1_000_000.0),
            )
        if kind in {"catalog_c10_reliable", "catalog_c10_general"}:
            weibull = WeibullParams(**payload["weibull"])
            return self.ex11_3_solver.solve(
                FD=payload["FD"],
                af=payload["af"],
                hours=payload["hours"],
                speed_rpm=payload["speed_rpm"],
                reliability=payload["reliability"],
                weibull=weibull,
                LR_rev=payload.get("LR_rev", 1_000_000.0),
            )
        if kind == "ball_l10_life":
            eq = self.ball.equivalent_dynamic_load(
                bearing_family=payload["bearing_family"],
                Fa=payload["Fa"],
                Fr=payload["Fr"],
                C0=payload["C0"],
                V=payload.get("V", 1.0),
            )
            life_h = self.ball.estimate_l10_life_hours(
                C10=payload["C10"],
                Fe=eq.Fe,
                speed_rpm=payload["speed_rpm"],
                a=payload.get("a", 3.0),
                LR_rev=payload.get("LR_rev", 1_000_000.0),
            )
            return {
                "problem_type": kind,
                "equivalent_load": eq.__dict__,
                "L10_hours": life_h,
            }
        if kind == "select_angular_contact":
            return self.angular_selector.select(
                Fr=payload["Fr"],
                Fa=payload["Fa"],
                V=payload.get("V", 1.0),
                speed_rpm=payload["speed_rpm"],
                hours=payload["hours"],
                target_reliability=payload["target_reliability"],
                af=payload["af"],
                LR_rev=payload.get("LR_rev", 1_000_000.0),
                initial_C0_guess=payload.get("initial_C0_guess", 12000.0),
            )
        if kind == "select_cylindrical_roller":
            weibull = WeibullParams(
                a=10.0 / 3.0, x0=0.02, theta_minus_x0=4.439, b=1.483
            )
            xD = LifeModel.rating_life_multiple(
                hours=payload["hours"],
                speed_rpm=payload["speed_rpm"],
                LR_rev=payload.get("LR_rev", 1_000_000.0),
            )
            c10 = LifeModel.c10_required(
                FD=payload["Fr"],
                af=payload["af"],
                xD=xD,
                weibull=weibull,
                reliability=payload["target_reliability"],
            )
            selected = self.cyl_catalog.select_first_by_c10(c10_required=c10)
            return {
                "problem_type": kind,
                "xD": xD,
                "C10_required": c10,
                "selected": selected,
            }
        if kind == "select_tapered_direct_pair":
            return self.tapered_selector.select_direct_pair(
                FrA=payload["FrA"],
                FrB=payload["FrB"],
                Fae=payload["Fae"],
                speed_rpm=payload["speed_rpm"],
                hours=payload["hours"],
                reliability_goal=payload["reliability_goal"],
                af=payload.get("af", 1.0),
                shaft_bore_mm=payload.get("shaft_bore_mm"),
                K_initial=payload.get("K_initial", 1.5),
                LR_rev=payload.get("LR_rev", 90_000_000.0),
            )
        if kind == "tapered_pair_reliability":
            RA = LifeModel.tapered_reliability_approx(
                FD=payload["FeA"],
                af=payload["af"],
                xD=payload["xD"],
                C10=payload["C10"],
            )
            RB = LifeModel.tapered_reliability_approx(
                FD=payload["FeB"],
                af=payload["af"],
                xD=payload["xD"],
                C10=payload["C10"],
            )
            return {"problem_type": kind, "RA": RA, "RB": RB, "R_total": RA * RB}
        if kind == "select_tapered_thrust_only":
            return self.tapered_selector.solve_external_thrust_only(
                Fae=payload["Fae"],
                speed_rpm=payload["speed_rpm"],
                hours=payload["hours"],
                reliability_goal=payload["reliability_goal"],
                af=payload.get("af", 1.0),
                shaft_bore_mm=payload.get("shaft_bore_mm"),
                LR_rev=payload.get("LR_rev", 90_000_000.0),
            )
        raise ValueError(f"Unknown problem_type={kind!r}")
