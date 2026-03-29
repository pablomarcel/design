from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

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
    notes: List[str] = field(default_factory=list)

    @property
    def d(self) -> float:
        return 2.0 * self.r

    @property
    def pressure(self) -> float:
        return self.W / (2.0 * self.r * self.l)

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
            notes=list(data.get("notes", [])) if isinstance(data.get("notes", []), list) else [],
        )

    def validate(self) -> None:
        for name in ("mu", "N", "W", "r", "c", "l"):
            value = getattr(self, name)
            if value <= 0.0:
                raise ValueError(f"Input '{name}' must be > 0. Received {value}.")
        if self.unit_system not in {"ips", "custom"}:
            raise ValueError(
                "Currently supported unit_system values are 'ips' and 'custom'. "
                f"Received '{self.unit_system}'."
            )


@dataclass
class DerivedState:
    P: float
    S: float
    l_over_d: float
    r_over_c: float


@dataclass
class ManualChartInputs:
    h0_over_c: Optional[float] = None
    epsilon: Optional[float] = None
    phi_deg: Optional[float] = None
    rcf: Optional[float] = None
    q_over_rcNl: Optional[float] = None
    qs_over_q: Optional[float] = None
    p_over_pmax: Optional[float] = None
    theta_pmax_deg: Optional[float] = None
    theta_p0_deg: Optional[float] = None

    @classmethod
    def from_mapping(cls, data: Optional[Dict[str, object]]) -> "ManualChartInputs":
        data = data or {}
        kwargs: Dict[str, Optional[float]] = {}
        for key in (
            "h0_over_c",
            "epsilon",
            "phi_deg",
            "rcf",
            "q_over_rcNl",
            "qs_over_q",
            "p_over_pmax",
            "theta_pmax_deg",
            "theta_p0_deg",
        ):
            value = data.get(key)
            kwargs[key] = None if value is None else safe_float(value, key)
        return cls(**kwargs)


class ManualChartProvider:
    def __init__(self, chart_inputs: Optional[ManualChartInputs] = None, interactive: bool = True):
        self.chart_inputs = chart_inputs or ManualChartInputs()
        self.interactive = interactive
        self.prompt_history: List[str] = []

    def _get_or_prompt(
        self,
        attr_name: str,
        prompt_label: str,
        figure_label: str,
        state: DerivedState,
        extra_hint: str = "",
    ) -> float:
        current = getattr(self.chart_inputs, attr_name)
        if current is not None:
            return current
        if not self.interactive:
            raise ValueError(
                f"Missing required manual chart input '{attr_name}'. "
                "This workflow pauses at charts. Provide a value in the JSON/CLI, or enable prompting."
            )
        print("\n" + "=" * 76)
        print("CHART INPUT REQUIRED")
        print("=" * 76)
        print(figure_label)
        print(f"  Sommerfeld number S = {state.S:.6f}")
        print(f"  l/d = {state.l_over_d:.6f}")
        print(f"  r/c = {state.r_over_c:.6f}")
        if extra_hint:
            print(f"  {extra_hint}")
        print("Read the chart, then enter the requested value.")
        while True:
            raw = input(f"Enter {prompt_label}: ").strip()
            try:
                value = float(raw)
                setattr(self.chart_inputs, attr_name, value)
                self.prompt_history.append(f"{attr_name}={value}")
                return value
            except ValueError:
                print(f"Could not parse numeric input for {prompt_label!r}: {raw!r}")

    def get_h0_over_c(self, state: DerivedState) -> float:
        return self._get_or_prompt("h0_over_c", "h0/c", "Figure 12-16: minimum film thickness variable", state)

    def get_epsilon(self, state: DerivedState) -> float:
        return self._get_or_prompt("epsilon", "epsilon = e/c", "Figure 12-16: eccentricity ratio", state)

    def get_phi_deg(self, state: DerivedState) -> float:
        return self._get_or_prompt("phi_deg", "phi in degrees", "Figure 12-17: attitude angle / minimum-film location", state)

    def get_rcf(self, state: DerivedState) -> float:
        return self._get_or_prompt("rcf", "(r/c)f", "Figure 12-18: coefficient-of-friction variable", state)

    def get_q_over_rcNl(self, state: DerivedState) -> float:
        return self._get_or_prompt("q_over_rcNl", "Q/(rcNl)", "Figure 12-19: flow variable", state)

    def get_qs_over_q(self, state: DerivedState) -> float:
        return self._get_or_prompt("qs_over_q", "Qs/Q", "Figure 12-20: side-flow ratio", state)

    def get_p_over_pmax(self, state: DerivedState) -> float:
        return self._get_or_prompt("p_over_pmax", "P/pmax", "Figure 12-21: maximum-film-pressure ratio", state)

    def get_theta_pmax_deg(self, state: DerivedState) -> float:
        return self._get_or_prompt("theta_pmax_deg", "theta_pmax in degrees", "Figure 12-22: position of maximum film pressure", state)

    def get_theta_p0_deg(self, state: DerivedState) -> float:
        return self._get_or_prompt("theta_p0_deg", "theta_p0 in degrees", "Figure 12-22: terminating position of lubricant film", state)


@dataclass
class SolveResult:
    problem: str
    title: str
    inputs: Dict[str, object]
    derived: Dict[str, float]
    chart_inputs_used: Dict[str, float]
    outputs: Dict[str, float]
    checks: Dict[str, float | str]
    notes: List[str]


class BaseProblem:
    problem_name: str = "base"
    title: str = "Base Problem"

    def __init__(self, inputs: BearingInputs, chart_provider: ManualChartProvider):
        self.inputs = inputs
        self.chart_provider = chart_provider
        self.inputs.validate()
        self.state = DerivedState(
            P=self.inputs.pressure,
            S=self.inputs.sommerfeld,
            l_over_d=self.inputs.l_over_d,
            r_over_c=self.inputs.r / self.inputs.c,
        )

    def base_inputs(self) -> Dict[str, object]:
        return {
            "mu": self.inputs.mu,
            "N": self.inputs.N,
            "W": self.inputs.W,
            "r": self.inputs.r,
            "c": self.inputs.c,
            "l": self.inputs.l,
            "d": self.inputs.d,
            "unit_system": self.inputs.unit_system,
        }

    def base_derived(self) -> Dict[str, float]:
        return {
            "P": self.state.P,
            "S": self.state.S,
            "l_over_d": self.state.l_over_d,
            "r_over_c": self.state.r_over_c,
        }

    def solve(self) -> SolveResult:
        raise NotImplementedError


class Example12_1_MinFilm(BaseProblem):
    problem_name = "ex12_1"
    title = "Example 12-1: minimum film thickness, eccentricity, and phi"

    def solve(self) -> SolveResult:
        h0_over_c = self.chart_provider.get_h0_over_c(self.state)
        epsilon = self.chart_provider.get_epsilon(self.state)
        phi_deg = self.chart_provider.get_phi_deg(self.state)
        h0 = h0_over_c * self.inputs.c
        e = epsilon * self.inputs.c
        relation_residual = h0_over_c - (1.0 - epsilon)
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            chart_inputs_used={"h0_over_c": h0_over_c, "epsilon": epsilon, "phi_deg": phi_deg},
            outputs={"h0": h0, "e": e, "phi_deg": phi_deg},
            checks={"h0_over_c_minus_1_minus_epsilon": relation_residual},
            notes=[
                "The app computed P, S, l/d, and r/c first, then paused for manual chart reads.",
                "Figure 12-16 supplies h0/c and epsilon.",
                "Figure 12-17 supplies phi.",
                "For ideal consistency, h0/c = 1 - epsilon.",
            ],
        )


class Example12_2_Friction(BaseProblem):
    problem_name = "ex12_2"
    title = "Example 12-2: coefficient of friction, torque, and power loss"

    def solve(self) -> SolveResult:
        rcf = self.chart_provider.get_rcf(self.state)
        f = rcf * self.inputs.c / self.inputs.r
        torque_lbf_in = f * self.inputs.W * self.inputs.r
        outputs = {"f": f, "torque_lbf_in": torque_lbf_in}
        notes = [
            "The app computed P, S, l/d, and r/c first, then paused for the friction chart read.",
            "Figure 12-18 supplies the friction variable (r/c)f.",
        ]
        checks: Dict[str, float | str] = {}
        if self.inputs.unit_system == "ips":
            hp_loss = torque_lbf_in * self.inputs.N / 1050.0
            heat_btu_s = 2.0 * 3.141592653589793 * torque_lbf_in * self.inputs.N / (778.0 * 12.0)
            outputs["power_loss_hp"] = hp_loss
            outputs["heat_loss_btu_s"] = heat_btu_s
            notes.append("Horsepower and Btu/s conversions use the ips-style textbook form.")
        else:
            checks["power_conversion"] = "Skipped because unit_system != 'ips'."
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            chart_inputs_used={"rcf": rcf},
            outputs=outputs,
            checks=checks,
            notes=notes,
        )


class Example12_3_Flow(BaseProblem):
    problem_name = "ex12_3"
    title = "Example 12-3: total volumetric flow rate and side flow rate"

    def solve(self) -> SolveResult:
        q_over_rcNl = self.chart_provider.get_q_over_rcNl(self.state)
        qs_over_q = self.chart_provider.get_qs_over_q(self.state)
        Q = q_over_rcNl * self.inputs.r * self.inputs.c * self.inputs.N * self.inputs.l
        Qs = qs_over_q * Q
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            chart_inputs_used={"q_over_rcNl": q_over_rcNl, "qs_over_q": qs_over_q},
            outputs={"Q": Q, "Qs": Qs, "Q_minus_Qs": Q - Qs},
            checks={},
            notes=[
                "The app computed P, S, l/d, and r/c first, then paused for the two chart reads.",
                "Figure 12-19 supplies Q/(rcNl).",
                "Figure 12-20 supplies Qs/Q.",
            ],
        )


class Example12_4_FilmPressure(BaseProblem):
    problem_name = "ex12_4"
    title = "Example 12-4: maximum film pressure and angular locations"

    def solve(self) -> SolveResult:
        p_over_pmax = self.chart_provider.get_p_over_pmax(self.state)
        theta_pmax_deg = self.chart_provider.get_theta_pmax_deg(self.state)
        theta_p0_deg = self.chart_provider.get_theta_p0_deg(self.state)
        pmax = self.state.P / p_over_pmax
        return SolveResult(
            problem=self.problem_name,
            title=self.title,
            inputs=self.base_inputs(),
            derived=self.base_derived(),
            chart_inputs_used={
                "p_over_pmax": p_over_pmax,
                "theta_pmax_deg": theta_pmax_deg,
                "theta_p0_deg": theta_p0_deg,
            },
            outputs={"pmax": pmax, "theta_pmax_deg": theta_pmax_deg, "theta_p0_deg": theta_p0_deg},
            checks={},
            notes=[
                "The app computed P, S, l/d, and r/c first, then paused for the pressure charts.",
                "Figure 12-21 supplies P/pmax.",
                "Figure 12-22 supplies theta_pmax and theta_p0.",
            ],
        )


PROBLEM_REGISTRY = {
    "ex12_1": Example12_1_MinFilm,
    "ex12_2": Example12_2_Friction,
    "ex12_3": Example12_3_Flow,
    "ex12_4": Example12_4_FilmPressure,
}
