#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.seven_speed

Mercedes-Benz W7A-700 / 7G-Tronic-style 7-speed automatic transmission
kinematic model using the shared transmission core classes.

Reference basis
---------------
This module is reconstructed from the user-provided W7A-700 reference figure
and clutch/brake application table:

- an upstream inverse-Ravigneaux-style stage replaces the forward simple set
  used in the earlier Mercedes 5-speed example
- the downstream architecture remains a two-simple-planetary cascade
- shift elements are:
    C1, C2, C3, B1, B2, B3, BR

Important honesty note
----------------------
This script is intentionally a **core-class kinematic abstraction**, not a
pinion-by-pinion OEM production synthesis.

To stay inside the reusable core framework (`PlanetaryGearSet`, `Clutch`,
`Brake`, `TransmissionSolver`), the inverse Ravigneaux front stage is modeled
as an equivalent two-mesh shared-carrier abstraction:

    PG_A : ring is permanently driven by input, sun can be braked by B1
           or locked to input by C1
    PG_B : sun is permanently driven by input, ring can be braked by B3

Both meshes share the same carrier, which then feeds the rear simple planetary
set.  This reproduces the published ratio spread closely while remaining fully
implemented on the reusable core stack.

Modeled rotating members
------------------------
input : turbine / transmission input
fa    : front-stage controllable sun (C1 / B1 branch)
fb    : front-stage controllable ring (B3 branch)
fc    : front-stage carrier = rear-set ring
rs    : rear-set sun
rc    : rear-set carrier = middle-set ring
ms    : middle-set sun
out   : middle-set carrier = output shaft

Gearset abstraction
-------------------
Front stage (effective inverse-Ravigneaux abstraction):
    PG_A : Ns_a * (w_fa   - w_fc) + Nr_a * (w_input - w_fc) = 0
    PG_B : Ns_b * (w_input - w_fc) + Nr_b * (w_fb    - w_fc) = 0

Rear set:
    Ns_r * (w_rs - w_rc) + Nr_r * (w_fc - w_rc) = 0

Middle set:
    Ns_m * (w_ms - w_out) + Nr_m * (w_rc - w_out) = 0

Shift-element interpretation
----------------------------
C1 : input ↔ fa
C2 : input ↔ rc
C3 : rs ↔ ms
B1 : fa → ground
B2 : ms → ground
B3 : fb → ground
BR : rc → ground
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence

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


class SevenSpeedCliError(ValueError):
    """User-facing CLI/configuration error for seven_speed.py."""


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    # Candidate set fitted to the published W7A-700 ratio spread:
    # 1st 4.38, 2nd 2.86, 3rd 1.92, 4th 1.37, 5th 1.00,
    # 6th 0.82, 7th 0.73, R1 -3.42, R2 -2.23 (approximately)
    "Ns_a": 52,
    "Nr_a": 106,
    "Ns_b": 78,
    "Nr_b": 100,
    "Ns_r": 66,
    "Nr_r": 164,
    "Ns_m": 62,
    "Nr_m": 168,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "w7a700_candidate": dict(DEFAULT_TOOTH_COUNTS),
}

PRESET_NOTES: Mapping[str, str] = {
    "w7a700_candidate": (
        "Candidate tooth-count set fitted to the published W7A-700 ratio spread "
        "using a reusable-core inverse-Ravigneaux equivalent abstraction; not "
        "claimed as OEM-confirmed tooth data."
    ),
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


STATE_ALIASES: Mapping[str, str] = {
    "1": "1st",
    "1st": "1st",
    "first": "1st",
    "2": "2nd",
    "2nd": "2nd",
    "second": "2nd",
    "3": "3rd",
    "3rd": "3rd",
    "third": "3rd",
    "4": "4th",
    "4th": "4th",
    "fourth": "4th",
    "5": "5th",
    "5th": "5th",
    "fifth": "5th",
    "6": "6th",
    "6th": "6th",
    "sixth": "6th",
    "7": "7th",
    "7th": "7th",
    "seventh": "7th",
    "r1": "R1",
    "rev1": "R1",
    "reverse1": "R1",
    "reverse_1": "R1",
    "r2": "R2",
    "rev2": "R2",
    "reverse2": "R2",
    "reverse_2": "R2",
    "n": "N",
    "neutral": "N",
}


def _validate_counts_basic(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise SevenSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise SevenSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )


def _validate_counts_strict(*, Ns: int, Nr: int, label: str) -> None:
    _validate_counts_basic(Ns=Ns, Nr=Nr, label=label)
    if (Nr - Ns) % 2 != 0:
        raise SevenSpeedCliError(
            f"Invalid {label} tooth counts under strict geometry mode: (Nr - Ns) must be even so the implied "
            f"planet tooth count is an integer. Got Ns={Ns}, Nr={Nr}, Nr-Ns={Nr - Ns}."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    validator = _validate_counts_strict if strict_geometry else _validate_counts_basic
    validator(Ns=int(counts["Ns_a"]), Nr=int(counts["Nr_a"]), label="Front mesh A")
    validator(Ns=int(counts["Ns_b"]), Nr=int(counts["Nr_b"]), label="Front mesh B")
    validator(Ns=int(counts["Ns_r"]), Nr=int(counts["Nr_r"]), label="Rear gearset")
    validator(Ns=int(counts["Ns_m"]), Nr=int(counts["Nr_m"]), label="Middle gearset")


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
        sig = inspect.signature(PlanetaryGearSet)
        if "geometry_mode" in sig.parameters:
            return PlanetaryGearSet(
                Ns=Ns,
                Nr=Nr,
                name=name,
                sun=sun,
                ring=ring,
                carrier=carrier,
                geometry_mode=geometry_mode,
            )
    except Exception:
        pass

    return PlanetaryGearSet(
        Ns=Ns,
        Nr=Nr,
        name=name,
        sun=sun,
        ring=ring,
        carrier=carrier,
    )


class MercedesW7A700SevenSpeedTransmission:
    """
    W7A-700 / 7G-Tronic-style 7-speed transmission model on the shared core stack.
    """

    SHIFT_SCHEDULE: Mapping[str, tuple[str, ...]] = {
        "1st": ("C3", "B2", "B3"),
        "2nd": ("C3", "B1", "B2"),
        "3rd": ("C1", "C3", "B2"),
        "4th": ("C1", "C2", "B2"),
        "5th": ("C1", "C2", "C3"),
        "6th": ("C2", "C3", "B1"),
        "7th": ("C2", "C3", "B3"),
        "R1": ("C3", "B3", "BR"),
        "R2": ("C3", "B1", "BR"),
        "N": ("C3", "B3"),
    }

    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "R1", "R2", "N")

    def __init__(
        self,
        *,
        Ns_a: int,
        Nr_a: int,
        Ns_b: int,
        Nr_b: int,
        Ns_r: int,
        Nr_r: int,
        Ns_m: int,
        Nr_m: int,
        strict_geometry: bool = False,
    ) -> None:
        self.strict_geometry = bool(strict_geometry)
        self.tooth_counts: Dict[str, int] = {
            "Ns_a": int(Ns_a),
            "Nr_a": int(Nr_a),
            "Ns_b": int(Ns_b),
            "Nr_b": int(Nr_b),
            "Ns_r": int(Ns_r),
            "Nr_r": int(Nr_r),
            "Ns_m": int(Ns_m),
            "Nr_m": int(Nr_m),
        }
        validate_tooth_counts(self.tooth_counts, strict_geometry=self.strict_geometry)
        self._build_topology(**self.tooth_counts)

    @staticmethod
    def normalize_state_name(state: str) -> str:
        key = state.strip().lower()
        if key == "all":
            return "all"
        if key not in STATE_ALIASES:
            raise SevenSpeedCliError(
                "Unknown state: {}. Valid states are 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, R1, R2, N, or all.".format(state)
            )
        return STATE_ALIASES[key]

    def _build_topology(
        self,
        *,
        Ns_a: int,
        Nr_a: int,
        Ns_b: int,
        Nr_b: int,
        Ns_r: int,
        Nr_r: int,
        Ns_m: int,
        Nr_m: int,
    ) -> None:
        self.input = RotatingMember("input")
        self.fa = RotatingMember("fa")
        self.fb = RotatingMember("fb")
        self.fc = RotatingMember("fc")
        self.rs = RotatingMember("rs")
        self.rc = RotatingMember("rc")
        self.ms = RotatingMember("ms")
        self.out = RotatingMember("out")

        self.members: Dict[str, RotatingMember] = {
            "input": self.input,
            "fa": self.fa,
            "fb": self.fb,
            "fc": self.fc,
            "rs": self.rs,
            "rc": self.rc,
            "ms": self.ms,
            "out": self.out,
        }

        # Upstream equivalent inverse-Ravigneaux abstraction:
        #   mesh A -> ring permanently driven by input, controllable sun fa
        #   mesh B -> sun permanently driven by input, controllable ring fb
        self.pg_a = _make_planetary(
            Ns=Ns_a,
            Nr=Nr_a,
            name="PG_A",
            sun=self.fa,
            ring=self.input,
            carrier=self.fc,
            strict_geometry=self.strict_geometry,
        )
        self.pg_b = _make_planetary(
            Ns=Ns_b,
            Nr=Nr_b,
            name="PG_B",
            sun=self.input,
            ring=self.fb,
            carrier=self.fc,
            strict_geometry=self.strict_geometry,
        )

        # Downstream cascade, same functional idea as the 5-speed family:
        self.pg_r = _make_planetary(
            Ns=Ns_r,
            Nr=Nr_r,
            name="PG_R",
            sun=self.rs,
            ring=self.fc,
            carrier=self.rc,
            strict_geometry=self.strict_geometry,
        )
        self.pg_m = _make_planetary(
            Ns=Ns_m,
            Nr=Nr_m,
            name="PG_M",
            sun=self.ms,
            ring=self.rc,
            carrier=self.out,
            strict_geometry=self.strict_geometry,
        )

        self.C1 = Clutch(self.input, self.fa, name="C1")
        self.C2 = Clutch(self.input, self.rc, name="C2")
        self.C3 = Clutch(self.rs, self.ms, name="C3")

        self.B1 = Brake(self.fa, name="B1")
        self.B2 = Brake(self.ms, name="B2")
        self.B3 = Brake(self.fb, name="B3")
        self.BR = Brake(self.rc, name="BR")

        self.constraints: Dict[str, object] = {
            "C1": self.C1,
            "C2": self.C2,
            "C3": self.C3,
            "B1": self.B1,
            "B2": self.B2,
            "B3": self.B3,
            "BR": self.BR,
        }

    def release_all(self) -> None:
        for c in self.constraints.values():
            c.release()  # type: ignore[attr-defined]

    def set_state(self, state: str) -> GearState:
        key = self.normalize_state_name(state)
        if key == "all":
            raise SevenSpeedCliError("Use solve_all() when state='all'.")
        self.release_all()
        engaged = self.SHIFT_SCHEDULE[key]
        for name in engaged:
            self.constraints[name].engage()  # type: ignore[attr-defined]

        notes_map = {
            "1st": "C3 + B2 + B3",
            "2nd": "C3 + B1 + B2",
            "3rd": "C1 + C3 + B2",
            "4th": "C1 + C2 + B2",
            "5th": "C1 + C2 + C3 direct",
            "6th": "C2 + C3 + B1 overdrive",
            "7th": "C2 + C3 + B3 overdrive",
            "R1": "C3 + B3 + BR reverse",
            "R2": "C3 + B1 + BR reverse",
            "N": "C3 + B3 neutral/reporting convention",
        }
        return GearState(name=key, engaged=engaged, notes=notes_map.get(key, ""))

    def _build_solver(self) -> TransmissionSolver:
        solver = TransmissionSolver()

        if hasattr(solver, "add_members"):
            solver.add_members(self.members.values())  # type: ignore[attr-defined]
        else:
            for member in self.members.values():
                solver.add_member(member)

        solver.add_gearset(self.pg_a)
        solver.add_gearset(self.pg_b)
        solver.add_gearset(self.pg_r)
        solver.add_gearset(self.pg_m)

        solver.add_clutch(self.C1)
        solver.add_clutch(self.C2)
        solver.add_clutch(self.C3)

        solver.add_brake(self.B1)
        solver.add_brake(self.B2)
        solver.add_brake(self.B3)
        solver.add_brake(self.BR)

        return solver

    def _solve_core_v2(self, *, input_speed: float) -> Dict[str, float]:
        solver = self._build_solver()

        if not hasattr(solver, "solve_report"):
            raise SevenSpeedCliError(
                "Loaded core solver does not support solve_report. This refactored seven_speed.py expects the upgraded Core V2 solver."
            )

        report = solver.solve_report(input_member="input", input_speed=float(input_speed))  # type: ignore[attr-defined]
        if not getattr(report, "ok", False):
            classification = getattr(report, "classification", None)
            status = getattr(classification, "status", "unknown")
            message = getattr(classification, "message", "Core solver failed.")
            raise SevenSpeedCliError(f"Core solver failed for current state ({status}): {message}")

        speeds = dict(getattr(report, "member_speeds", {}))
        missing = [name for name in self.members if name not in speeds]
        if missing:
            raise SevenSpeedCliError(f"Core solver did not return speeds for: {', '.join(missing)}")
        return {name: float(speeds[name]) for name in self.members}

    def solve_state(self, state: str, input_speed: float = 1.0) -> Dict[str, object]:
        gear_state = self.set_state(state)

        if gear_state.name == "N":
            speeds = {
                "input": float(input_speed),
                "fa": 0.0,
                "fb": 0.0,
                "fc": 0.0,
                "rs": 0.0,
                "rc": 0.0,
                "ms": 0.0,
                "out": 0.0,
            }
            return SolveResult(
                state="N",
                engaged=gear_state.engaged,
                speeds=speeds,
                ratio=0.0,
                notes=gear_state.notes,
                solver_path="core_v2",
            ).__dict__

        speeds = self._solve_core_v2(input_speed=float(input_speed))
        out_speed = float(speeds["out"])
        if abs(out_speed) < 1.0e-12:
            raise SevenSpeedCliError(f"Output speed is zero in state {gear_state.name}; ratio undefined.")

        ratio_signed = float(input_speed) / out_speed
        if gear_state.name in {"R1", "R2"}:
            ratio_display = ratio_signed
        else:
            ratio_display = abs(ratio_signed)

        return SolveResult(
            state=gear_state.name,
            engaged=gear_state.engaged,
            speeds=speeds,
            ratio=float(ratio_display),
            notes=gear_state.notes,
            solver_path="core_v2",
        ).__dict__

    def solve_all(self, *, input_speed: float = 1.0) -> Dict[str, Dict[str, object]]:
        out: Dict[str, Dict[str, object]] = {}
        for label in self.DISPLAY_ORDER:
            out[label] = self.solve_state(label, input_speed=input_speed)
        return out


def _resolve_tooth_counts(args: argparse.Namespace, *, strict_geometry: bool) -> Dict[str, int]:
    counts = dict(DEFAULT_TOOTH_COUNTS)

    if args.preset:
        if args.preset not in PRESETS:
            raise SevenSpeedCliError(
                f"Unknown preset '{args.preset}'. Available presets: {', '.join(sorted(PRESETS))}"
            )
        counts.update(PRESETS[args.preset])

    overrides = {
        "Ns_a": args.Ns_a,
        "Nr_a": args.Nr_a,
        "Ns_b": args.Ns_b,
        "Nr_b": args.Nr_b,
        "Ns_r": args.Ns_r,
        "Nr_r": args.Nr_r,
        "Ns_m": args.Ns_m,
        "Nr_m": args.Nr_m,
    }
    for key, value in overrides.items():
        if value is not None:
            counts[key] = int(value)

    validate_tooth_counts(counts, strict_geometry=strict_geometry)
    return counts


def _print_tooth_counts(
    counts: Mapping[str, int],
    *,
    preset: Optional[str] = None,
    strict_geometry: bool = False,
) -> None:
    print("Tooth Counts")
    print("------------------------------------------------------------")
    print(f"Front mesh A: Ns_a={counts['Ns_a']}, Nr_a={counts['Nr_a']}")
    print(f"Front mesh B: Ns_b={counts['Ns_b']}, Nr_b={counts['Nr_b']}")
    print(f"Rear set    : Ns_r={counts['Ns_r']}, Nr_r={counts['Nr_r']}")
    print(f"Middle set  : Ns_m={counts['Ns_m']}, Nr_m={counts['Nr_m']}")
    print(f"Geometry mode: {'strict' if strict_geometry else 'relaxed'}")
    if preset and preset in PRESET_NOTES:
        print(f"Preset note: {PRESET_NOTES[preset]}")
    print()


def _print_single(
    result: Mapping[str, object],
    *,
    tooth_counts: Mapping[str, int],
    preset: Optional[str],
    strict_geometry: bool,
) -> None:
    _print_tooth_counts(tooth_counts, preset=preset, strict_geometry=strict_geometry)
    print(f"State: {result['state']}")
    print(f"Engaged: {' + '.join(result['engaged'])}")
    print(f"Ratio (input/output): {float(result['ratio']):.6f}")
    print(f"Solver path: {result.get('solver_path', 'core_v2')}")
    print(f"Notes: {result['notes']}")
    print(json.dumps(result['speeds'], indent=2))


def _print_all(
    results: Mapping[str, Mapping[str, object]],
    *,
    tooth_counts: Mapping[str, int],
    preset: Optional[str],
    strict_geometry: bool,
) -> None:
    _print_tooth_counts(tooth_counts, preset=preset, strict_geometry=strict_geometry)
    print("Mercedes-Benz W7A-700 7-Speed Kinematic Summary")
    print("-" * 160)
    print(f"Geometry mode: {'strict' if strict_geometry else 'relaxed'}")
    print("Solver path: core_v2")
    print("-" * 160)
    print(
        f"{'State':<6} {'Elems':<20} {'Ratio':>8} "
        f"{'Input':>9} {'F.sunA':>9} {'F.ringB':>9} {'F.car':>9} "
        f"{'R.sun':>9} {'R.car':>9} {'M.sun':>9} {'Out':>9}"
    )
    print("-" * 160)
    for key in MercedesW7A700SevenSpeedTransmission.DISPLAY_ORDER:
        r = results[key]
        s = r["speeds"]
        print(
            f"{key:<6} {'+'.join(r['engaged']):<20} "
            f"{float(r['ratio']):>8.3f} "
            f"{float(s['input']):>9.3f} "
            f"{float(s['fa']):>9.3f} "
            f"{float(s['fb']):>9.3f} "
            f"{float(s['fc']):>9.3f} "
            f"{float(s['rs']):>9.3f} "
            f"{float(s['rc']):>9.3f} "
            f"{float(s['ms']):>9.3f} "
            f"{float(s['out']):>9.3f}"
        )


def _print_ratios_only(results: Mapping[str, Mapping[str, object]], *, as_json: bool = False) -> None:
    payload = {key: float(results[key]["ratio"]) for key in MercedesW7A700SevenSpeedTransmission.DISPLAY_ORDER}
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    print("Ratios Only")
    print("------------------------------------------------------------")
    for key in MercedesW7A700SevenSpeedTransmission.DISPLAY_ORDER:
        print(f"{key:>3}: {payload[key]:.6f}")


def _emit_cli_error(
    *,
    args: argparse.Namespace,
    message: str,
    tooth_counts: Optional[Mapping[str, int]] = None,
    strict_geometry: bool = False,
) -> int:
    payload = {
        "ok": False,
        "error": message,
        "preset": getattr(args, "preset", None),
        "geometry_mode": "strict" if strict_geometry else "relaxed",
    }
    if tooth_counts is not None:
        payload["tooth_counts"] = dict(tooth_counts)

    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        print("seven_speed.py error", file=sys.stderr)
        print("--------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                f"Front A: Ns_a={tooth_counts['Ns_a']}, Nr_a={tooth_counts['Nr_a']} | "
                f"Front B: Ns_b={tooth_counts['Ns_b']}, Nr_b={tooth_counts['Nr_b']} | "
                f"Rear: Ns_r={tooth_counts['Ns_r']}, Nr_r={tooth_counts['Nr_r']} | "
                f"Middle: Ns_m={tooth_counts['Ns_m']}, Nr_m={tooth_counts['Nr_m']}",
                file=sys.stderr,
            )
    return 2


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Mercedes-Benz W7A-700 7-speed automatic transmission kinematic solver")
    p.add_argument("--state", default="all", help="State to solve: 1st, 2nd, 3rd, 4th, 5th, 6th, 7th, R1, R2, N, or all")
    p.add_argument("--input-speed", type=float, default=1.0, help="Input speed used for normalization")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Print only the ratios")
    p.add_argument("--preset", choices=sorted(PRESETS.keys()), default="w7a700_candidate", help="Named tooth-count preset")
    p.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    p.add_argument("--strict-geometry", action="store_true", help="Enforce strict simple-planetary integer-planet checks")
    p.add_argument("--relaxed-geometry", action="store_true", help="Force relaxed geometry mode")
    p.add_argument("--Ns-a", dest="Ns_a", type=int, default=None, help="Front mesh A sun tooth count")
    p.add_argument("--Nr-a", dest="Nr_a", type=int, default=None, help="Front mesh A ring tooth count")
    p.add_argument("--Ns-b", dest="Ns_b", type=int, default=None, help="Front mesh B sun tooth count")
    p.add_argument("--Nr-b", dest="Nr_b", type=int, default=None, help="Front mesh B ring tooth count")
    p.add_argument("--Ns-r", dest="Ns_r", type=int, default=None, help="Rear-set sun tooth count")
    p.add_argument("--Nr-r", dest="Nr_r", type=int, default=None, help="Rear-set ring tooth count")
    p.add_argument("--Ns-m", dest="Ns_m", type=int, default=None, help="Middle-set sun tooth count")
    p.add_argument("--Nr-m", dest="Nr_m", type=int, default=None, help="Middle-set ring tooth count")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    strict_geometry = bool(args.strict_geometry)
    if args.strict_geometry and args.relaxed_geometry:
        return _emit_cli_error(args=args, message="Choose only one of --strict-geometry or --relaxed-geometry.")
    if args.relaxed_geometry:
        strict_geometry = False

    if args.list_presets:
        payload = {
            name: {
                "tooth_counts": dict(values),
                "note": PRESET_NOTES.get(name, ""),
            }
            for name, values in PRESETS.items()
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Available presets")
            print("------------------------------------------------------------")
            for name, data in payload.items():
                values = data["tooth_counts"]
                print(
                    f"{name}: Ns_a={values['Ns_a']}, Nr_a={values['Nr_a']}, "
                    f"Ns_b={values['Ns_b']}, Nr_b={values['Nr_b']}, "
                    f"Ns_r={values['Ns_r']}, Nr_r={values['Nr_r']}, "
                    f"Ns_m={values['Ns_m']}, Nr_m={values['Nr_m']}"
                )
                if data["note"]:
                    print(f"  note: {data['note']}")
        return 0

    tooth_counts: Dict[str, int] = {}
    try:
        tooth_counts = _resolve_tooth_counts(args, strict_geometry=strict_geometry)
        tx = MercedesW7A700SevenSpeedTransmission(**tooth_counts, strict_geometry=strict_geometry)
        normalized = tx.normalize_state_name(args.state)

        if normalized == "all":
            results = tx.solve_all(input_speed=float(args.input_speed))
            if args.json:
                payload = {
                    "ok": True,
                    "preset": args.preset,
                    "preset_note": PRESET_NOTES.get(args.preset, ""),
                    "geometry_mode": "strict" if strict_geometry else "relaxed",
                    "solver_path": "core_v2",
                    "tooth_counts": tooth_counts,
                    "results": results,
                }
                if args.ratios_only:
                    payload = {
                        "ok": True,
                        "preset": args.preset,
                        "preset_note": PRESET_NOTES.get(args.preset, ""),
                        "geometry_mode": "strict" if strict_geometry else "relaxed",
                        "solver_path": "core_v2",
                        "tooth_counts": tooth_counts,
                        "ratios": {key: float(results[key]["ratio"]) for key in tx.DISPLAY_ORDER},
                    }
                print(json.dumps(payload, indent=2))
                return 0

            if args.ratios_only:
                _print_tooth_counts(tooth_counts, preset=args.preset, strict_geometry=strict_geometry)
                _print_ratios_only(results, as_json=False)
            else:
                _print_all(results, tooth_counts=tooth_counts, preset=args.preset, strict_geometry=strict_geometry)
            return 0

        result = tx.solve_state(normalized, input_speed=float(args.input_speed))
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
                "preset_note": PRESET_NOTES.get(args.preset, ""),
                "geometry_mode": "strict" if strict_geometry else "relaxed",
                "solver_path": result.get("solver_path", "core_v2"),
                "tooth_counts": tooth_counts,
                "result": result,
            }
            print(json.dumps(payload, indent=2))
            return 0

        _print_single(result, tooth_counts=tooth_counts, preset=args.preset, strict_geometry=strict_geometry)
        return 0

    except SevenSpeedCliError as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts or None, strict_geometry=strict_geometry)
    except Exception as exc:  # pragma: no cover
        return _emit_cli_error(
            args=args,
            message=f"Unexpected failure in seven_speed.py: {exc}",
            tooth_counts=tooth_counts or None,
            strict_geometry=strict_geometry,
        )


if __name__ == "__main__":
    raise SystemExit(main())
