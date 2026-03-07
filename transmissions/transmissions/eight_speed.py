#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transmissions.transmissions.eight_speed

ZF 8HP45 / 8HP70 family research-backed diagnostic kinematic model.

This version rebuilds the model around the ATSG clutch application chart and
planetary-details page that are substantially more trustworthy than the mixed
public descriptions used earlier.

Truth anchor used here
----------------------
From the ATSG ZF8HP45 technical service manual:
- Input shaft drives the P2 carrier and C clutch housing.
- A brake holds the common P1/P2 sun gears.
- B brake holds the P1 annulus.
- C clutch drives the P3 annulus, the P4 sun gear, and the E clutch housing.
- D clutch connects the P3 carrier with the P4 carrier / output shaft.
- E clutch connects the P2 annulus gear to the P3 sun gear.
- P4 annulus connects to P1 carrier.
- P4 carrier is integral to the output shaft.

That yields the modeled rotating nodes:
- input               : turbine / input shaft (normalized to 1.0)
- sun12               : common sun for P1 and P2
- p1r                 : P1 ring (annulus)
- p1c_p4r             : P1 carrier = P4 ring
- p2r                 : P2 ring (annulus)
- c_out               : C-clutch output node = P3 ring = P4 sun = E housing
- p3s                 : P3 sun
- p3c                 : P3 carrier
- output              : P4 carrier / output shaft

Important honesty note
----------------------
Even with this better-supported fact set, some states remain underdetermined in
public information alone. This script is therefore a diagnostic/research model,
not a final OEM-defensible synthesis engine.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

import sympy as sp

try:
    from ..core.clutch import Brake, Clutch, RotatingMember
    from ..core.planetary import PlanetaryGearSet
except Exception:  # pragma: no cover
    try:
        from core.clutch import Brake, Clutch, RotatingMember  # type: ignore
        from core.planetary import PlanetaryGearSet  # type: ignore
    except Exception:  # pragma: no cover
        from clutch import Brake, Clutch, RotatingMember  # type: ignore
        from planetary import PlanetaryGearSet  # type: ignore


class EightSpeedCliError(ValueError):
    pass


DEFAULT_TOOTH_COUNTS: Mapping[str, int] = {
    "Ns1": 48,
    "Nr1": 96,
    "Ns2": 48,
    "Nr2": 96,
    "Ns3": 38,
    "Nr3": 96,
    "Ns4": 23,
    "Nr4": 85,
}

PRESETS: Mapping[str, Mapping[str, int]] = {
    "zf_8hp45_reference": {
        "Ns1": 48, "Nr1": 96,
        "Ns2": 48, "Nr2": 96,
        "Ns3": 38, "Nr3": 96,
        "Ns4": 23, "Nr4": 85,
    },
    "zf_8hp50_candidate": {
        "Ns1": 48, "Nr1": 96,
        "Ns2": 48, "Nr2": 96,
        "Ns3": 38, "Nr3": 96,
        "Ns4": 24, "Nr4": 89,
    },
    "zf_8hp51_gen3_candidate": {
        "Ns1": 48, "Nr1": 96,
        "Ns2": 48, "Nr2": 96,
        "Ns3": 38, "Nr3": 96,
        "Ns4": 23, "Nr4": 85,
    },
}

PRESET_NOTES: Mapping[str, str] = {
    "zf_8hp45_reference": "ATSG-style 8HP45 reference tooth counts.",
    "zf_8hp50_candidate": "Exploratory candidate for 8HP50-style spread.",
    "zf_8hp51_gen3_candidate": "Exploratory carry-over candidate. Public Gen 3 data remains noisy.",
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
    ok: bool
    ratio: Optional[float]
    speeds: Dict[str, float]
    notes: str = ""
    solver_path: str = "core_v2:atsg_local_param_guard"
    status: str = "ok"  # ok | underdetermined | inconsistent
    message: str = ""


def _validate_counts_basic(*, Ns: int, Nr: int, label: str) -> None:
    if Ns <= 0 or Nr <= 0:
        raise EightSpeedCliError(f"Invalid {label} tooth counts: Ns and Nr must both be positive integers.")
    if Nr <= Ns:
        raise EightSpeedCliError(
            f"Invalid {label} tooth counts: ring gear teeth Nr ({Nr}) must be greater than sun gear teeth Ns ({Ns})."
        )


def _validate_counts_strict(*, Ns: int, Nr: int, label: str) -> None:
    _validate_counts_basic(Ns=Ns, Nr=Nr, label=label)
    if (Nr - Ns) % 2 != 0:
        raise EightSpeedCliError(
            f"Invalid {label} tooth counts under strict geometry mode: (Nr - Ns) must be even so the implied "
            f"planet tooth count is an integer. Got Ns={Ns}, Nr={Nr}, Nr-Ns={Nr - Ns}."
        )


def validate_tooth_counts(counts: Mapping[str, int], *, strict_geometry: bool) -> None:
    validator = _validate_counts_strict if strict_geometry else _validate_counts_basic
    for i in range(1, 5):
        validator(Ns=int(counts[f"Ns{i}"]), Nr=int(counts[f"Nr{i}"]), label=f"P{i}")


def _make_planetary(*, Ns: int, Nr: int, name: str, sun: RotatingMember, ring: RotatingMember,
                    carrier: RotatingMember, strict_geometry: bool):
    geometry_mode = "strict" if strict_geometry else "relaxed"
    try:
        sig = inspect.signature(PlanetaryGearSet)
        if "geometry_mode" in sig.parameters:
            return PlanetaryGearSet(Ns=Ns, Nr=Nr, name=name, sun=sun, ring=ring, carrier=carrier,
                                    geometry_mode=geometry_mode)
    except Exception:
        pass
    return PlanetaryGearSet(Ns=Ns, Nr=Nr, name=name, sun=sun, ring=ring, carrier=carrier)


class ZF8HPEightSpeedTransmission:
    """
    ATSG Figure 2 / Figure 3 based topology.

    Shift elements
    --------------
    - A brake : sun12 -> ground
    - B brake : p1r -> ground
    - C clutch: input -> c_out   (c_out = P3 ring = P4 sun = E housing)
    - D clutch: p3c -> output
    - E clutch: c_out <-> p2r and c_out <-> p3s

    Shift chart (ATSG)
    ------------------
    R   : A + B + D
    1st : A + B + C
    2nd : A + B + E
    3rd : B + C + E
    4th : B + D + E
    5th : B + C + D
    6th : C + D + E
    7th : A + C + D
    8th : A + D + E
    """

    SHIFT_SCHEDULE: Mapping[str, tuple[str, ...]] = {
        "1st": ("A", "B", "C"),
        "2nd": ("A", "B", "E"),
        "3rd": ("B", "C", "E"),
        "4th": ("B", "D", "E"),
        "5th": ("B", "C", "D"),
        "6th": ("C", "D", "E"),
        "7th": ("A", "C", "D"),
        "8th": ("A", "D", "E"),
        "rev": ("A", "B", "D"),
        "reverse": ("A", "B", "D"),
    }
    DISPLAY_ORDER: Sequence[str] = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "rev")
    DISPLAY_NAMES: Mapping[str, str] = {"rev": "Rev"}

    def __init__(self, *, Ns1: int, Nr1: int, Ns2: int, Nr2: int, Ns3: int, Nr3: int, Ns4: int, Nr4: int,
                 strict_geometry: bool = False) -> None:
        self.strict_geometry = bool(strict_geometry)
        self.tooth_counts: Dict[str, int] = {
            "Ns1": int(Ns1), "Nr1": int(Nr1),
            "Ns2": int(Ns2), "Nr2": int(Nr2),
            "Ns3": int(Ns3), "Nr3": int(Nr3),
            "Ns4": int(Ns4), "Nr4": int(Nr4),
        }
        self._build_topology(**self.tooth_counts)

    def _build_topology(self, *, Ns1: int, Nr1: int, Ns2: int, Nr2: int, Ns3: int, Nr3: int, Ns4: int, Nr4: int) -> None:
        self.input = RotatingMember("input")
        self.sun12 = RotatingMember("sun12")
        self.p1r = RotatingMember("p1r")
        self.p1c_p4r = RotatingMember("p1c_p4r")
        self.p2r = RotatingMember("p2r")
        self.c_out = RotatingMember("c_out")
        self.p3s = RotatingMember("p3s")
        self.p3c = RotatingMember("p3c")
        self.output = RotatingMember("output")

        self.pg1 = _make_planetary(Ns=Ns1, Nr=Nr1, name="P1", sun=self.sun12, ring=self.p1r,
                                   carrier=self.p1c_p4r, strict_geometry=self.strict_geometry)
        self.pg2 = _make_planetary(Ns=Ns2, Nr=Nr2, name="P2", sun=self.sun12, ring=self.p2r,
                                   carrier=self.input, strict_geometry=self.strict_geometry)
        self.pg3 = _make_planetary(Ns=Ns3, Nr=Nr3, name="P3", sun=self.p3s, ring=self.c_out,
                                   carrier=self.p3c, strict_geometry=self.strict_geometry)
        self.pg4 = _make_planetary(Ns=Ns4, Nr=Nr4, name="P4", sun=self.c_out, ring=self.p1c_p4r,
                                   carrier=self.output, strict_geometry=self.strict_geometry)

        self.A = Brake(self.sun12, name="A")
        self.B = Brake(self.p1r, name="B")
        self.C = Clutch(self.input, self.c_out, name="C")
        self.D = Clutch(self.p3c, self.output, name="D")
        # E ties the E housing (c_out) to both P2 ring and P3 sun.
        self.E1 = Clutch(self.c_out, self.p2r, name="E_p2r")
        self.E2 = Clutch(self.c_out, self.p3s, name="E_p3s")

        self.constraints: Dict[str, object] = {
            "A": self.A,
            "B": self.B,
            "C": self.C,
            "D": self.D,
            "E_p2r": self.E1,
            "E_p3s": self.E2,
        }

    def release_all(self) -> None:
        for c in self.constraints.values():
            c.release()  # type: ignore[attr-defined]

    def set_state(self, state: str) -> GearState:
        key = state.strip().lower()
        if key not in self.SHIFT_SCHEDULE:
            raise EightSpeedCliError(f"Unknown state: {state}")
        self.release_all()
        engaged = self.SHIFT_SCHEDULE[key]
        for name in engaged:
            if name == "E":
                self.E1.engage()
                self.E2.engage()
            else:
                self.constraints[name].engage()  # type: ignore[index,attr-defined]
        display = self.DISPLAY_NAMES.get(key, state.strip())
        return GearState(display, tuple(engaged), "ATSG-based shift-element application")

    def _build_equations(self) -> tuple[list[sp.Expr], list[sp.Symbol], dict[str, sp.Symbol]]:
        ws12, wp1r, wp1c, wp2r, wcout, wp3s, wp3c, wout = sp.symbols(
            "ws12 wp1r wp1c wp2r wcout wp3s wp3c wout", real=True
        )
        syms = {
            "sun12": ws12,
            "p1r": wp1r,
            "p1c_p4r": wp1c,
            "p2r": wp2r,
            "c_out": wcout,
            "p3s": wp3s,
            "p3c": wp3c,
            "output": wout,
        }
        eqs: list[sp.Expr] = [
            self.pg1.Ns * (ws12 - wp1c) + self.pg1.Nr * (wp1r - wp1c),
            self.pg2.Ns * (ws12 - 1.0) + self.pg2.Nr * (wp2r - 1.0),
            self.pg3.Ns * (wp3s - wp3c) + self.pg3.Nr * (wcout - wp3c),
            self.pg4.Ns * (wcout - wout) + self.pg4.Nr * (wp1c - wout),
        ]
        if self.A.engaged:
            eqs.append(ws12)
        if self.B.engaged:
            eqs.append(wp1r)
        if self.C.engaged:
            eqs.append(wcout - 1.0)
        if self.D.engaged:
            eqs.append(wp3c - wout)
        if self.E1.engaged:
            eqs.append(wp2r - wcout)
        if self.E2.engaged:
            eqs.append(wp3s - wcout)
        unknowns = [ws12, wp1r, wp1c, wp2r, wcout, wp3s, wp3c, wout]
        return eqs, unknowns, syms

    def solve_state(self, state: str) -> SolveResult:
        gs = self.set_state(state)
        eqs, unknowns, syms = self._build_equations()
        try:
            sols = sp.solve(eqs, unknowns, dict=True)
        except Exception as exc:
            raise EightSpeedCliError(f"SymPy solve failure: {exc}") from exc

        if not sols:
            return SolveResult(
                state=gs.name, engaged=gs.engaged, ok=False, ratio=None, speeds={},
                notes="No solution found for the assembled transmission equations.",
                status="inconsistent", message="No solution found for the assembled transmission equations.",
            )

        sol = sols[0]
        unresolved = [name for name, sym in syms.items() if sym not in sol]
        speeds: Dict[str, float] = {"input": 1.0}
        non_numeric = []
        for name, sym in syms.items():
            if sym in sol:
                expr = sp.simplify(sol[sym])
                if expr.free_symbols:
                    non_numeric.append(name)
                else:
                    speeds[name] = float(sp.N(expr))

        unresolved_all = unresolved + [name for name in non_numeric if name not in unresolved]
        if "output" in speeds and abs(float(speeds["output"])) > 1e-12:
            ratio = 1.0 / float(speeds["output"])
            if unresolved_all:
                msg = "Underdetermined member speeds: " + ", ".join(unresolved_all)
                return SolveResult(gs.name, gs.engaged, True, ratio, speeds, notes=msg,
                                   status="underdetermined", message=msg)
            return SolveResult(gs.name, gs.engaged, True, ratio, speeds,
                               notes="Solved using ATSG-based topology.", status="ok", message="ok")

        msg = "Underdetermined member speeds: " + ", ".join(unresolved_all or ["output"])
        return SolveResult(gs.name, gs.engaged, False, None, speeds, notes=msg,
                           status="underdetermined", message=msg)

    def solve_all(self) -> Dict[str, SolveResult]:
        out: Dict[str, SolveResult] = {}
        for st in self.DISPLAY_ORDER:
            out[self.DISPLAY_NAMES.get(st, st)] = self.solve_state(st)
        return out

    def topology_summary(self) -> dict:
        return {
            "source": "ATSG Figure 2 / Figure 3 style arrangement",
            "permanent_connections": {
                "input": "P2 carrier",
                "sun12": "P1 sun = P2 sun",
                "p1c_p4r": "P1 carrier = P4 ring",
                "c_out": "C clutch output = P3 ring = P4 sun = E housing",
                "output": "P4 carrier / output shaft",
            },
            "shift_elements": {
                "A": "sun12 -> ground",
                "B": "p1r -> ground",
                "C": "input -> c_out",
                "D": "p3c -> output",
                "E": "c_out -> p2r and c_out -> p3s",
            },
        }


def _resolve_tooth_counts(args: argparse.Namespace) -> Dict[str, int]:
    if args.preset is None:
        counts = dict(DEFAULT_TOOTH_COUNTS)
    else:
        if args.preset not in PRESETS:
            valid = ", ".join(sorted(PRESETS))
            raise EightSpeedCliError(f"Unknown preset: {args.preset}. Valid presets: {valid}")
        counts = dict(PRESETS[args.preset])
    for i in range(1, 5):
        ns_val = getattr(args, f"Ns{i}")
        nr_val = getattr(args, f"Nr{i}")
        if ns_val is not None:
            counts[f"Ns{i}"] = int(ns_val)
        if nr_val is not None:
            counts[f"Nr{i}"] = int(nr_val)
    validate_tooth_counts(counts, strict_geometry=bool(args.strict_geometry))
    return counts


def _normalize_state_name(state: str) -> str:
    key = state.strip().lower()
    aliases = {"reverse": "rev", "r": "rev"}
    return aliases.get(key, key)


def _payload(result: SolveResult) -> Dict[str, object]:
    return {
        "state": result.state,
        "engaged": list(result.engaged),
        "ok": result.ok,
        "status": result.status,
        "ratio": result.ratio,
        "speeds": dict(result.speeds),
        "notes": result.notes,
        "solver_path": result.solver_path,
        "message": result.message,
    }


def _emit_cli_error(*, args: argparse.Namespace, message: str,
                    tooth_counts: Optional[Mapping[str, int]] = None) -> int:
    payload = {
        "ok": False,
        "error": message,
        "preset": getattr(args, "preset", None),
        "strict_geometry": bool(getattr(args, "strict_geometry", False)),
    }
    if tooth_counts is not None:
        payload["tooth_counts"] = dict(tooth_counts)
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    else:
        print("eight_speed.py error", file=sys.stderr)
        print("--------------------", file=sys.stderr)
        print(message, file=sys.stderr)
        if tooth_counts is not None:
            print(
                "Tooth counts: "
                f"P1(Ns1={tooth_counts['Ns1']}, Nr1={tooth_counts['Nr1']}), "
                f"P2(Ns2={tooth_counts['Ns2']}, Nr2={tooth_counts['Nr2']}), "
                f"P3(Ns3={tooth_counts['Ns3']}, Nr3={tooth_counts['Nr3']}), "
                f"P4(Ns4={tooth_counts['Ns4']}, Nr4={tooth_counts['Nr4']})",
                file=sys.stderr,
            )
    return 2


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ZF 8HP ATSG-based 8-speed transmission diagnostic model")
    p.add_argument("--state", default="all", help="State to solve: all, 1st..8th, rev")
    for i in range(1, 5):
        p.add_argument(f"--Ns{i}", type=int, default=None, help=f"P{i} sun tooth count")
        p.add_argument(f"--Nr{i}", type=int, default=None, help=f"P{i} ring tooth count")
    p.add_argument("--preset", default="zf_8hp45_reference", help="Named preset tooth-count configuration")
    p.add_argument("--strict-geometry", action="store_true", help="Enforce strict simple-planetary integer-planet geometry checks")
    p.add_argument("--list-presets", action="store_true", help="List presets and exit")
    p.add_argument("--json", action="store_true", help="Emit JSON output")
    p.add_argument("--ratios-only", action="store_true", help="Emit only ratios")
    p.add_argument("--show-topology", action="store_true", help="Show modeled topology and exit")
    return p


def _print_presets() -> None:
    print("Available presets")
    print("-----------------")
    for name, counts in PRESETS.items():
        note = PRESET_NOTES.get(name, "")
        print(
            f"{name:22s} "
            f"Ns1={counts['Ns1']} Nr1={counts['Nr1']} "
            f"Ns2={counts['Ns2']} Nr2={counts['Nr2']} "
            f"Ns3={counts['Ns3']} Nr3={counts['Nr3']} "
            f"Ns4={counts['Ns4']} Nr4={counts['Nr4']}"
        )
        if note:
            print(f"  note: {note}")


def _print_summary(*, counts: Mapping[str, int], results: Dict[str, SolveResult], ratios_only: bool, strict_geometry: bool) -> None:
    print("ZF 8HP 8-Speed Kinematic Summary")
    print("-" * 150)
    print(
        f"Tooth counts: P1(Ns1={counts['Ns1']}, Nr1={counts['Nr1']}), "
        f"P2(Ns2={counts['Ns2']}, Nr2={counts['Nr2']}), "
        f"P3(Ns3={counts['Ns3']}, Nr3={counts['Nr3']}), "
        f"P4(Ns4={counts['Ns4']}, Nr4={counts['Nr4']})"
    )
    print(f"Geometry mode: {'strict' if strict_geometry else 'relaxed'}")
    print("Solver path: core_v2:atsg_local_param_guard")
    print("-" * 150)
    if ratios_only:
        print(f"{'State':<8s} {'Elems':<14s} {'Status':<18s} {'Ratio':>10s}")
        print("-" * 150)
        for name, result in results.items():
            elems = "+".join(result.engaged)
            ratio_txt = "-" if result.ratio is None else f"{result.ratio:.3f}"
            print(f"{name:<8s} {elems:<14s} {result.status:<18s} {ratio_txt:>10s}")
            if result.notes:
                print(f"  note: {result.notes}")
        return

    headers = (
        f"{'State':<8s} {'Elems':<14s} {'Status':<18s} {'Ratio':>10s} {'Input':>9s} {'sun12':>9s} {'p1r':>9s} "
        f"{'p2r':>9s} {'c_out':>9s} {'p3s':>9s} {'p1c_p4r':>9s} {'p3c':>9s} {'Output':>9s}"
    )
    print(headers)
    print("-" * 150)
    for name, result in results.items():
        elems = "+".join(result.engaged)
        s = result.speeds
        ratio_txt = "-" if result.ratio is None else f"{result.ratio:.3f}"
        def fmt(key: str) -> str:
            return f"{s[key]:>9.3f}" if key in s else f"{'-':>9s}"
        print(
            f"{name:<8s} {elems:<14.14s} {result.status:<18s} {ratio_txt:>10s} "
            f"{fmt('input')} {fmt('sun12')} {fmt('p1r')} {fmt('p2r')} {fmt('c_out')} {fmt('p3s')} {fmt('p1c_p4r')} {fmt('p3c')} {fmt('output')}"
        )
        if result.notes:
            print(f"  note: {result.notes}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.list_presets:
        _print_presets()
        return 0
    tooth_counts: Optional[Dict[str, int]] = None
    try:
        tooth_counts = _resolve_tooth_counts(args)
        tx = ZF8HPEightSpeedTransmission(**tooth_counts, strict_geometry=bool(args.strict_geometry))
        if args.show_topology:
            payload = tx.topology_summary()
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(json.dumps(payload, indent=2))
            return 0
        if str(args.state).strip().lower() == "all":
            results = tx.solve_all()
            if args.json:
                payload = {
                    "ok": True,
                    "preset": args.preset,
                    "strict_geometry": bool(args.strict_geometry),
                    "tooth_counts": tooth_counts,
                    "solver_path": "core_v2:atsg_local_param_guard",
                    "states": {name: _payload(result) for name, result in results.items()},
                }
                if args.ratios_only:
                    payload["ratios"] = {name: result.ratio for name, result in results.items()}
                print(json.dumps(payload, indent=2))
            else:
                _print_summary(counts=tooth_counts, results=results,
                               ratios_only=bool(args.ratios_only), strict_geometry=bool(args.strict_geometry))
            return 0

        state = _normalize_state_name(args.state)
        result = tx.solve_state(state)
        if args.json:
            payload = {
                "ok": True,
                "preset": args.preset,
                "strict_geometry": bool(args.strict_geometry),
                "tooth_counts": tooth_counts,
                **_payload(result),
            }
            print(json.dumps(payload, indent=2))
        else:
            if args.ratios_only:
                ratio_txt = "-" if result.ratio is None else f"{result.ratio:.6f}"
                print(f"{result.state}: {ratio_txt}")
            else:
                print(f"State: {result.state}")
                print(f"Engaged: {' + '.join(result.engaged)}")
                print(
                    f"Tooth counts: P1(Ns1={tooth_counts['Ns1']}, Nr1={tooth_counts['Nr1']}), "
                    f"P2(Ns2={tooth_counts['Ns2']}, Nr2={tooth_counts['Nr2']}), "
                    f"P3(Ns3={tooth_counts['Ns3']}, Nr3={tooth_counts['Nr3']}), "
                    f"P4(Ns4={tooth_counts['Ns4']}, Nr4={tooth_counts['Nr4']})"
                )
                print(f"Geometry mode: {'strict' if args.strict_geometry else 'relaxed'}")
                print("Solver path: core_v2:atsg_local_param_guard")
                ratio_txt = "-" if result.ratio is None else f"{result.ratio:.6f}"
                print(f"Ratio (input/output): {ratio_txt}")
                print(json.dumps(result.speeds, indent=2))
                if result.notes:
                    print(result.notes)
        return 0
    except (EightSpeedCliError, ValueError) as exc:
        return _emit_cli_error(args=args, message=str(exc), tooth_counts=tooth_counts)
    except Exception as exc:  # pragma: no cover
        return _emit_cli_error(args=args, message=f"Unexpected solver/runtime failure: {exc}", tooth_counts=tooth_counts)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
