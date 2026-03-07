#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.six_speed

Allison-style 6-speed automatic transmission kinematic model.

Core V2 refactor
----------------
This version is refactored to solve through the upgraded core stack:
- core.planetary.PlanetaryGearSet
- core.clutch.{RotatingMember, Clutch, Brake}
- core.solver.TransmissionSolver

Topology (left to right, engine to output)
------------------------------------------
PG1:
    - PG1.sun permanently connected to engine input
    - PG1.carrier permanently connected to PG2.ring   -> node12
    - PG1.ring can be braked by C3

PG2:
    - PG2.sun can be connected to engine input by C1
    - PG2.carrier can be connected to engine input by C2
    - PG2.sun permanently connected to PG3.sun        -> sun23
    - PG2.carrier permanently connected to PG3.ring   -> node23
    - PG2.ring can be braked by C4

PG3:
    - PG3.carrier is output
    - PG3.ring can be braked by C5

Shift schedule
--------------
    1st : C1 + C5
    2nd : C1 + C4
    3rd : C1 + C3
    4th : C1 + C2
    5th : C2 + C3
    6th : C2 + C4
    Rev : C3 + C5

Design note
-----------
Unlike the Ford C4 refactor, this Allison topology does not need extra
permanent-tie equations in the solver because the shared nodes are modeled
explicitly as shared RotatingMember objects:
    node12 = PG1.carrier = PG2.ring
    sun23  = PG2.sun     = PG3.sun
    node23 = PG2.carrier = PG3.ring

So if this script reports `solver_path: core_v2`, it is solving through the
upgraded core solver for the right reasons, not through local fallback logic.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

try:
    from ..core.clutch import Brake, Clutch, RotatingMember
    from ..core.planetary import PlanetaryGearSet
    from ..core.solver import TransmissionSolver
except Exception:  # pragma: no cover
    try:
        from core.clutch import Brake, Clutch, RotatingMember  # type: ignore
        from core.planetary import PlanetaryGearSet  # type: ignore
        from core.solver import TransmissionSolver  # type: ignore
    except Exception:  # pragma: no cover
        from clutch import Brake, Clutch, RotatingMember  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore
        from solver import TransmissionSolver  # type: ignore

LOG = logging.getLogger(__name__)


class SixSpeedCliError(ValueError):
    """User-facing CLI/configuration error for six_speed.py."""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    "Ns1": 67,
    "Nr1": 109,
    "Ns2": 49,
    "Nr2": 91,
    "Ns3": 39,
    "Nr3": 97,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "allison_3000": {
        "Ns1": 67,
        "Nr1": 109,
        "Ns2": 49,
        "Nr2": 91,
        "Ns3": 39,
        "Nr3": 97,
    },
    "allison_1000_candidate": {
        "Ns1": 61,
        "Nr1": 100,
        "Ns2": 41,
        "Nr2": 79,
        "Ns3": 41,
        "Nr3": 79,
    },
}

PRESET_NOTES: Mapping[str, str] = {
    "allison_3000": "Candidate Allison 3000 family counts that match published ratios very closely.",
    "allison_1000_candidate": "Exploratory Allison 1000/2000 style candidate set; not OEM-confirmed.",
}


@dataclass(frozen=True)
class GearState:
    name: str
    engaged: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class SolveResult:
    state: str
    engaged: tuple[str, ...]
    speeds: Dict[str, float]
    ratio: float
    notes: str = ""
    solver_path: str = "core_v2"


def _validate_counts_basic(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise SixSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise SixSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )


def _validate_counts_strict(*, Ns: int, Nr: int, label: str) -> None:
    _validate_counts_basic(Ns=Ns, Nr=Nr, label=label)
    if (Nr - Ns) % 2 != 0:
        raise SixSpeedCliError(
            f"Invalid {label} tooth counts under strict geometry mode: (Nr - Ns) must be even so the implied "
            f"planet tooth count is an integer. Got Ns={Ns}, Nr={Nr}, Nr-Ns={Nr - Ns}."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    validator = _validate_counts_strict if strict_geometry else _validate_counts_basic
    validator(Ns=int(counts["Ns1"]), Nr=int(counts["Nr1"]), label="PG1")
    validator(Ns=int(counts["Ns2"]), Nr=int(counts["Nr2"]), label="PG2")
    validator(Ns=int(counts["Ns3"]), Nr=int(counts["Nr3"]), label="PG3")


def _make_planetary(
    *,
    Ns: int,
    Nr: int,
    name: str,
    sun: RotatingMember,
    ring: RotatingMember,
    carrier: RotatingMember,
    strict_geometry: bool,
):
    geometry_mode = "strict" if strict_geometry else "relaxed"
    try:
        return PlanetaryGearSet(
            Ns=Ns,
            Nr=Nr,
            name=name,
            sun=sun,
            ring=ring,
            carrier=carrier,
            geometry_mode=geometry_mode,
        )
    except TypeError:
        return PlanetaryGearSet(
            Ns=Ns,
            Nr=Nr,
            name=name,
            sun=sun,
            ring=ring,
            carrier=carrier,
        )


class AllisonSixSpeedTransmission:
    """Allison-style 3-planetary, 5-friction-element transmission model."""

    SHIFT_SCHEDULE: Mapping[str, tuple[str, str]] = {
        "1st": ("C1", "C5"),
        "2nd": ("C1", "C4"),
        "3rd": ("C1", "C3"),
        "4th": ("C1", "C2"),
        "5th": ("C2", "C3"),
        "6th": ("C2", "C4"),
        "rev": ("C3", "C5"),
        "reverse": ("C3", "C5"),
    }

    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "6th", "rev")

    def __init__(
        self,
        *,
        Ns1: int,
        Nr1: int,
        Ns2: int,
        Nr2: int,
        Ns3: int,
        Nr3: int,
        strict_geometry: bool = True,
    ) -> None:
        self.strict_geometry = bool(strict_geometry)
        self.tooth_counts: Dict[str, int] = {
            "Ns1": int(Ns1),
            "Nr1": int(Nr1),
            "Ns2": int(Ns2),
            "Nr2": int(Nr2),
            "Ns3": int(Ns3),
            "Nr3": int(Nr3),
        }
        self._build_topology(**self.tooth_counts)

    def _build_topology(self, *, Ns1: int, Nr1: int, Ns2: int, Nr2: int, Ns3: int, Nr3: int) -> None:
        self.input = RotatingMember("input")
        self.ring1 = RotatingMember("ring1")
        self.node12 = RotatingMember("node12")
        self.sun23 = RotatingMember("sun23")
        self.node23 = RotatingMember("node23")
        self.output = RotatingMember("output")

        self.members: Dict[str, RotatingMember] = {
            "input": self.input,
            "ring1": self.ring1,
            "node12": self.node12,
            "sun23": self.sun23,
            "node23": self.node23,
            "output": self.output,
        }

        self.pg1 = _make_planetary(
            Ns=Ns1,
            Nr=Nr1,
            name="PG1",
            sun=self.input,
            ring=self.ring1,
            carrier=self.node12,
            strict_geometry=self.strict_geometry,
        )
        self.pg2 = _make_planetary(
            Ns=Ns2,
            Nr=Nr2,
            name="PG2",
            sun=self.sun23,
            ring=self.node12,
            carrier=self.node23,
            strict_geometry=self.strict_geometry,
        )
        self.pg3 = _make_planetary(
            Ns=Ns3,
            Nr=Nr3,
            name="PG3",
            sun=self.sun23,
            ring=self.node23,
            carrier=self.output,
            strict_geometry=self.strict_geometry,
        )
        self.gearsets: List[PlanetaryGearSet] = [self.pg1, self.pg2, self.pg3]

        self.C1 = Clutch(self.input, self.sun23, name="C1")
        self.C2 = Clutch(self.input, self.node23, name="C2")
        self.C3 = Brake(self.ring1, name="C3")
        self.C4 = Brake(self.node12, name="C4")
        self.C5 = Brake(self.node23, name="C5")

        self.constraints: Dict[str, object] = {
            "C1": self.C1,
            "C2": self.C2,
            "C3": self.C3,
            "C4": self.C4,
            "C5": self.C5,
        }

    def release_all(self) -> None:
        for c in self.constraints.values():
            c.release()  # type: ignore[attr-defined]

    def set_state(self, state: str) -> GearState:
        key = state.strip().lower()
        if key not in self.SHIFT_SCHEDULE:
            raise SixSpeedCliError(f"Unknown state: {state}")
        self.release_all()
        engaged = self.SHIFT_SCHEDULE[key]
        for name in engaged:
            self.constraints[name].engage()  # type: ignore[attr-defined]
        display = "Rev" if key in {"rev", "reverse"} else state.strip()
        notes_map = {
            "1st": "C1 + C5",
            "2nd": "C1 + C4",
            "3rd": "C1 + C3",
            "4th": "C1 + C2 direct drive",
            "5th": "C2 + C3 overdrive",
            "6th": "C2 + C4 double overdrive",
            "rev": "C3 + C5 reverse",
        }
        return GearState(display, engaged, notes_map.get(key, ""))

    def _solve_core_v2(self, *, input_speed: float) -> Dict[str, float]:
        solver = TransmissionSolver()

        if hasattr(solver, "add_members"):
            solver.add_members(self.members.values())  # type: ignore[attr-defined]
        else:
            for member in self.members.values():
                solver.add_member(member)

        solver.add_gearset(self.pg1)
        solver.add_gearset(self.pg2)
        solver.add_gearset(self.pg3)
        solver.add_clutch(self.C1)
        solver.add_clutch(self.C2)
        solver.add_brake(self.C3)
        solver.add_brake(self.C4)
        solver.add_brake(self.C5)

        if not hasattr(solver, "solve_report"):
            raise SixSpeedCliError(
                "Loaded core solver does not support solve_report. This refactored six_speed.py expects the upgraded Core V2 solver."
            )

        report = solver.solve_report(input_member="input", input_speed=float(input_speed))  # type: ignore[attr-defined]
        if not getattr(report, "ok", False):
            message = getattr(getattr(report, "classification", None), "message", "Solver failed")
            raise SixSpeedCliError(str(message))

        result = dict(report.member_speeds)  # type: ignore[attr-defined]
        if "input" not in result:
            result["input"] = float(input_speed)
        return result

    def solve_state(self, state: str, input_speed: float = 1.0) -> Dict[str, object]:
        info = self.set_state(state)
        speeds = self._solve_core_v2(input_speed=float(input_speed))
        if "output" not in speeds:
            raise SixSpeedCliError("Solver result does not contain output speed.")
        if abs(float(speeds["output"])) < 1.0e-12:
            raise SixSpeedCliError(f"Output speed is zero for state {info.name}; ratio is undefined.")

        ordered_speeds = {
            "input": float(speeds["input"]),
            "ring1": float(speeds["ring1"]),
            "node12": float(speeds["node12"]),
            "sun23": float(speeds["sun23"]),
            "node23": float(speeds["node23"]),
            "output": float(speeds["output"]),
        }
        ratio = float(input_speed) / ordered_speeds["output"]
        return {
            "state": info.name,
            "engaged": list(info.engaged),
            "speeds": ordered_speeds,
            "ratio": ratio,
            "notes": info.notes,
            "solver_path": "core_v2",
        }

    def solve_all(self, input_speed: float = 1.0) -> Dict[str, Dict[str, object]]:
        out: Dict[str, Dict[str, object]] = {}
        for state in self.DISPLAY_ORDER:
            label = "Rev" if state == "rev" else state
            out[label] = self.solve_state(state, input_speed=input_speed)
        return out

    def tooth_count_summary(self) -> str:
        c = self.tooth_counts
        mode = "strict" if self.strict_geometry else "relaxed"
        return (
            f"Tooth counts: PG1(Ns1={c['Ns1']}, Nr1={c['Nr1']}), "
            f"PG2(Ns2={c['Ns2']}, Nr2={c['Nr2']}), "
            f"PG3(Ns3={c['Ns3']}, Nr3={c['Nr3']})\n"
            f"Geometry mode: {mode}\n"
            f"Solver path: core_v2"
        )

    def topology_description(self) -> str:
        return (
            "Allison 6-Speed Topology\n"
            "------------------------\n"
            "PG1: sun=input, ring=ring1, carrier=node12\n"
            "PG2: sun=sun23, ring=node12, carrier=node23\n"
            "PG3: sun=sun23, ring=node23, carrier=output\n"
            "Shift elements: C1=input↔sun23, C2=input↔node23, C3=ring1→ground, C4=node12→ground, C5=node23→ground\n"
            "Shared nodes are modeled explicitly as shared rotating members: node12, sun23, node23."
        )

    def summary_table(self, input_speed: float = 1.0) -> str:
        results = self.solve_all(input_speed=input_speed)
        lines: List[str] = []
        lines.append("Allison 6-Speed Kinematic Summary")
        lines.append("-" * 120)
        lines.append(self.tooth_count_summary())
        lines.append("-" * 120)
        lines.append(
            f"{'State':<8s} {'Elems':<16s} {'Ratio':>10s} {'Input':>9s} {'Ring1':>9s} {'Node12':>9s} {'Sun23':>9s} {'Node23':>9s} {'Output':>9s}"
        )
        lines.append("-" * 120)
        for label, result in results.items():
            s = result["speeds"]
            elems = "+".join(result["engaged"])
            lines.append(
                f"{label:<8s} {elems:<16.16s} {float(result['ratio']):>10.3f} "
                f"{float(s['input']):>9.3f} {float(s['ring1']):>9.3f} {float(s['node12']):>9.3f} {float(s['sun23']):>9.3f} {float(s['node23']):>9.3f} {float(s['output']):>9.3f}"
            )
        return "\n".join(lines)

    def ratio_table(self, input_speed: float = 1.0) -> str:
        results = self.solve_all(input_speed=input_speed)
        lines: List[str] = []
        lines.append("Allison 6-Speed Ratios")
        lines.append("-" * 44)
        lines.append(self.tooth_count_summary())
        lines.append("-" * 44)
        lines.append(f"{'State':<8s} {'Elems':<16s} {'Ratio':>10s}")
        lines.append("-" * 44)
        for label, result in results.items():
            elems = "+".join(result["engaged"])
            lines.append(f"{label:<8s} {elems:<16.16s} {float(result['ratio']):>10.3f}")
        return "\n".join(lines)


def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    if args.preset is None:
        counts = dict(DEFAULT_TOOTH_COUNTS)
    else:
        if args.preset not in PRESETS:
            valid = ", ".join(sorted(PRESETS))
            raise SixSpeedCliError(f"Unknown preset: {args.preset}. Valid presets: {valid}")
        counts = dict(PRESETS[args.preset])

    for key in ("Ns1", "Nr1", "Ns2", "Nr2", "Ns3", "Nr3"):
        value = getattr(args, key, None)
        if value is not None:
            counts[key] = int(value)
    return counts


def _presets_payload() -> Dict[str, object]:
    return {
        "presets": {name: dict(values) for name, values in PRESETS.items()},
        "preset_notes": dict(PRESET_NOTES),
    }


def _emit_cli_error(*, args: argparse.Namespace, message: str, tooth_counts: Optional[Mapping[str, int]] = None) -> int:
    payload = {
        "ok": False,
        "error": message,
        "preset": getattr(args, "preset", None),
        "strict_geometry": bool(getattr(args, "strict_geometry", True)),
    }
    if tooth_counts is not None:
        payload["tooth_counts"] = dict(tooth_counts)

    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        print("six_speed.py error", file=sys.stderr)
        print("------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                f"Tooth counts: PG1(Ns1={tooth_counts['Ns1']}, Nr1={tooth_counts['Nr1']}), "
                f"PG2(Ns2={tooth_counts['Ns2']}, Nr2={tooth_counts['Nr2']}), "
                f"PG3(Ns3={tooth_counts['Ns3']}, Nr3={tooth_counts['Nr3']})",
                file=sys.stderr,
            )
    return 2


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Allison-style 6-speed automatic transmission kinematic solver")
    p.add_argument("--state", default="all", help="State to solve: all, 1st, 2nd, 3rd, 4th, 5th, 6th, rev")
    p.add_argument("--input-speed", type=float, default=1.0, help="Input angular speed used for normalization")
    p.add_argument("--Ns1", type=int, default=None, help="PG1 sun tooth count")
    p.add_argument("--Nr1", type=int, default=None, help="PG1 ring tooth count")
    p.add_argument("--Ns2", type=int, default=None, help="PG2 sun tooth count")
    p.add_argument("--Nr2", type=int, default=None, help="PG2 ring tooth count")
    p.add_argument("--Ns3", type=int, default=None, help="PG3 sun tooth count")
    p.add_argument("--Nr3", type=int, default=None, help="PG3 ring tooth count")
    p.add_argument("--preset", default="allison_3000", help="Named preset tooth-count configuration")
    p.add_argument("--strict-geometry", action="store_true", default=True, help="Enforce strict integer-planet geometry checks (default: on)")
    p.add_argument("--relaxed-geometry", action="store_true", help="Disable strict integer-planet geometry checks")
    p.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    p.add_argument("--show-topology", action="store_true", help="Print topology summary before results")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Emit only ratios")
    p.add_argument("--log-level", default="WARNING", help="Logging level")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.relaxed_geometry:
        args.strict_geometry = False

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.WARNING),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    tooth_counts: Optional[Dict[str, int]] = None
    try:
        if args.list_presets:
            if args.json:
                print(json.dumps(_presets_payload(), indent=2))
            else:
                print("Available presets")
                print("-" * 18)
                for name, values in PRESETS.items():
                    print(f"{name}: {dict(values)}")
                    note = PRESET_NOTES.get(name, "")
                    if note:
                        print(f"  note: {note}")
            return 0

        tooth_counts = _resolve_tooth_counts(args)
        validate_tooth_counts(tooth_counts, strict_geometry=bool(args.strict_geometry))
        tx = AllisonSixSpeedTransmission(**tooth_counts, strict_geometry=bool(args.strict_geometry))

        if args.show_topology and not args.json:
            print(tx.topology_description())
            print()

        if args.state.lower() == "all":
            result = tx.solve_all(input_speed=args.input_speed)
            if args.json:
                payload: Dict[str, object] = {
                    "ok": True,
                    "preset": args.preset,
                    "strict_geometry": bool(args.strict_geometry),
                    "tooth_counts": tooth_counts,
                    "states": result,
                }
                if args.ratios_only:
                    payload["ratios"] = {name: state["ratio"] for name, state in result.items()}
                print(json.dumps(payload, indent=2))
            else:
                print(tx.ratio_table(input_speed=args.input_speed) if args.ratios_only else tx.summary_table(input_speed=args.input_speed))
            return 0

        result = tx.solve_state(args.state, input_speed=args.input_speed)
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
                "strict_geometry": bool(args.strict_geometry),
                "tooth_counts": tooth_counts,
                **result,
            }
            print(json.dumps(payload, indent=2))
        else:
            print(tx.tooth_count_summary())
            print(f"State: {result['state']}")
            print(f"Engaged: {' + '.join(result['engaged'])}")
            print(f"Ratio (input/output): {result['ratio']:.6f}")
            print(json.dumps(result['speeds'], indent=2))
        return 0
    except SixSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts)
    except ValueError as exc:
        return _emit_cli_error(args=args, message=f"Invalid input: {exc}", tooth_counts=tooth_counts)
    except RuntimeError as exc:
        return _emit_cli_error(args=args, message=f"Solver failure: {exc}", tooth_counts=tooth_counts)
    except KeyboardInterrupt:
        return _emit_cli_error(args=args, message="Interrupted by user.", tooth_counts=tooth_counts)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
