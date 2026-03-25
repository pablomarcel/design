from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .core import (
        DiameterResizeCalculator,
        DiameterResizeInput,
        DeflectionVectorCalculator,
        EnduranceLimitCalculator,
        EnduranceLimitInput,
        FatigueCalculator,
        FatigueInput,
        TorsionCalculator,
        TorsionInput,
        TorsionSegment,
        VectorPair,
        YieldCalculator,
        YieldInput,
    )
except ImportError:  # pragma: no cover - local package execution shim
    from core import (
        DiameterResizeCalculator,
        DiameterResizeInput,
        DeflectionVectorCalculator,
        EnduranceLimitCalculator,
        EnduranceLimitInput,
        FatigueCalculator,
        FatigueInput,
        TorsionCalculator,
        TorsionInput,
        TorsionSegment,
        VectorPair,
        YieldCalculator,
        YieldInput,
    )


PKG_DIR = Path(__file__).resolve().parent
IN_DIR = PKG_DIR / "in"
OUT_DIR = PKG_DIR / "out"


def _json_dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2)


def _print_json(data: dict[str, Any]) -> None:
    print(_json_dump(data))


def _resolve_infile(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    if p.exists():
        return p.resolve()
    candidate = IN_DIR / path_str
    if candidate.exists():
        return candidate.resolve()
    return candidate.resolve()


def _resolve_outfile(path_str: str | None, default_name: str) -> Path | None:
    if path_str is None:
        return None
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (OUT_DIR / p).resolve() if not p.parent.parts else p.resolve()


def _write_outfile(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(data) + "\n", encoding="utf-8")


def _load_problem(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _run_problem(problem: dict[str, Any]) -> dict[str, Any]:
    calc = str(problem.get("calculation", "")).strip().lower()
    inputs = problem.get("inputs", {})

    if calc == "endurance" or calc == "endurance_limit":
        model = EnduranceLimitInput(
            se_prime=float(inputs["se_prime"]),
            ka=float(inputs["ka"]),
            kb=float(inputs["kb"]),
            kc=float(inputs["kc"]),
            kd=float(inputs["kd"]),
            ke=float(inputs["ke"]),
            kf_misc=float(inputs["kf_misc"]),
        )
        return EnduranceLimitCalculator(model).solve()

    if calc == "fatigue":
        model = FatigueInput(
            criterion=str(inputs["criterion"]),
            Kf=float(inputs["Kf"]),
            Kfs=float(inputs["Kfs"]),
            Se=float(inputs["Se"]),
            Sut=float(inputs["Sut"]) if inputs.get("Sut") is not None else None,
            Sy=float(inputs["Sy"]) if inputs.get("Sy") is not None else None,
            Ma=float(inputs.get("Ma", 0.0)),
            Mm=float(inputs.get("Mm", 0.0)),
            Ta=float(inputs.get("Ta", 0.0)),
            Tm=float(inputs.get("Tm", 0.0)),
            d=float(inputs["d"]) if inputs.get("d") is not None else None,
            n=float(inputs["n"]) if inputs.get("n") is not None else None,
            strength_unit=str(inputs.get("strength_unit", "ksi")),
        )
        return FatigueCalculator(model).solve()

    if calc == "yield":
        model = YieldInput(
            Kf=float(inputs["Kf"]),
            Kfs=float(inputs["Kfs"]),
            Sy=float(inputs["Sy"]),
            d=float(inputs["d"]),
            Ma=float(inputs.get("Ma", 0.0)),
            Mm=float(inputs.get("Mm", 0.0)),
            Ta=float(inputs.get("Ta", 0.0)),
            Tm=float(inputs.get("Tm", 0.0)),
            strength_unit=str(inputs.get("strength_unit", "ksi")),
        )
        return YieldCalculator(model).solve()

    if calc == "vector_sum":
        raw_pairs = inputs.get("pairs", [])
        pairs = [
            VectorPair(
                xz=float(item["xz"]),
                xy=float(item["xy"]),
                units=item.get("units"),
                label=item.get("label"),
            )
            for item in raw_pairs
        ]
        return DeflectionVectorCalculator(pairs).solve()

    if calc == "diameter_resize":
        model = DiameterResizeInput(
            d_old=float(inputs["d_old"]),
            response_old=float(inputs["response_old"]),
            response_allow=float(inputs["response_allow"]),
            n_design=float(inputs.get("n_design", 1.0)),
            mode=str(inputs.get("mode", "deflection")),
        )
        return DiameterResizeCalculator(model).solve()

    if calc == "torsion_angle":
        segs = [
            TorsionSegment(
                length=float(item["length"]),
                torque=float(item["torque"]) if item.get("torque") is not None else None,
                J=float(item["J"]) if item.get("J") is not None else None,
                k=float(item["k"]) if item.get("k") is not None else None,
            )
            for item in inputs.get("segments", [])
        ]
        model = TorsionInput(
            G=float(inputs["G"]) if inputs.get("G") is not None else None,
            T=float(inputs["T"]) if inputs.get("T") is not None else None,
            segments=segs,
        )
        return TorsionCalculator(model).angle_of_twist()

    if calc == "torsional_stiffness":
        segs = [
            TorsionSegment(
                length=float(item["length"]),
                torque=float(item["torque"]) if item.get("torque") is not None else None,
                J=float(item["J"]) if item.get("J") is not None else None,
                k=float(item["k"]) if item.get("k") is not None else None,
            )
            for item in inputs.get("segments", [])
        ]
        model = TorsionInput(
            G=float(inputs["G"]) if inputs.get("G") is not None else None,
            T=float(inputs["T"]) if inputs.get("T") is not None else None,
            segments=segs,
        )
        return TorsionCalculator(model).stiffness()

    raise ValueError(
        "Unsupported calculation in JSON problem file. "
        "Use one of: endurance_limit, fatigue, yield, vector_sum, "
        "diameter_resize, torsion_angle, torsional_stiffness"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shafts-cli",
        description="CLI-based shaft design app for Shigley Chapter 7 style calculations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_end = sub.add_parser("endurance", help="Calculate real endurance limit Se")
    p_end.add_argument("--se-prime", type=float, required=True)
    p_end.add_argument("--ka", type=float, required=True)
    p_end.add_argument("--kb", type=float, required=True)
    p_end.add_argument("--kc", type=float, required=True)
    p_end.add_argument("--kd", type=float, required=True)
    p_end.add_argument("--ke", type=float, required=True)
    p_end.add_argument("--kf-misc", type=float, required=True)
    p_end.add_argument("--outfile", type=str, default=None)

    p_fat = sub.add_parser("fatigue", help="Fatigue factor of safety or diameter")
    p_fat.add_argument(
        "--criterion",
        type=str,
        required=True,
        choices=[
            "de_goodman",
            "de_gerber",
            "de_asme_elliptic",
            "de_soderberg",
        ],
    )
    p_fat.add_argument("--Kf", type=float, required=True)
    p_fat.add_argument("--Kfs", type=float, required=True)
    p_fat.add_argument("--Se", type=float, required=True)
    p_fat.add_argument("--Sut", type=float, default=None)
    p_fat.add_argument("--Sy", type=float, default=None)
    p_fat.add_argument("--strength-unit", type=str, default="ksi")
    p_fat.add_argument("--Ma", type=float, default=0.0)
    p_fat.add_argument("--Mm", type=float, default=0.0)
    p_fat.add_argument("--Ta", type=float, default=0.0)
    p_fat.add_argument("--Tm", type=float, default=0.0)
    p_fat.add_argument("--d", type=float, default=None)
    p_fat.add_argument("--n", type=float, default=None)
    p_fat.add_argument("--outfile", type=str, default=None)

    p_yld = sub.add_parser("yield", help="Yield check using von Mises maximum stress")
    p_yld.add_argument("--Kf", type=float, required=True)
    p_yld.add_argument("--Kfs", type=float, required=True)
    p_yld.add_argument("--Sy", type=float, required=True)
    p_yld.add_argument("--strength-unit", type=str, default="ksi")
    p_yld.add_argument("--Ma", type=float, default=0.0)
    p_yld.add_argument("--Mm", type=float, default=0.0)
    p_yld.add_argument("--Ta", type=float, default=0.0)
    p_yld.add_argument("--Tm", type=float, default=0.0)
    p_yld.add_argument("--d", type=float, required=True)
    p_yld.add_argument("--outfile", type=str, default=None)

    p_vec = sub.add_parser(
        "vector-sum",
        help="Vector summation of xz and xy values at one or more stations",
    )
    p_vec.add_argument(
        "--label",
        action="append",
        default=[],
        help="Optional repeated labels, one per station",
    )
    p_vec.add_argument(
        "--xz",
        action="append",
        type=float,
        required=True,
        help="Repeated xz values, one per station",
    )
    p_vec.add_argument(
        "--xy",
        action="append",
        type=float,
        required=True,
        help="Repeated xy values, one per station",
    )
    p_vec.add_argument("--units", type=str, default=None)
    p_vec.add_argument("--outfile", type=str, default=None)

    p_resize = sub.add_parser(
        "diameter-resize",
        help="Resize diameter from old response and allowable response",
    )
    p_resize.add_argument("--d-old", type=float, required=True)
    p_resize.add_argument("--response-old", type=float, required=True)
    p_resize.add_argument("--response-allow", type=float, required=True)
    p_resize.add_argument("--n-design", type=float, default=1.0)
    p_resize.add_argument(
        "--mode",
        type=str,
        default="deflection",
        choices=["deflection", "slope"],
    )
    p_resize.add_argument("--outfile", type=str, default=None)

    p_ta = sub.add_parser(
        "torsion-angle",
        help="Angle of twist for stepped shaft or shaft segments in series",
    )
    p_ta.add_argument("--G", type=float, required=True)
    p_ta.add_argument("--T", type=float, default=None)
    p_ta.add_argument("--length", action="append", type=float, required=True)
    p_ta.add_argument("--J", action="append", type=float, required=True)
    p_ta.add_argument("--torque", action="append", type=float, default=None)
    p_ta.add_argument("--outfile", type=str, default=None)

    p_ts = sub.add_parser(
        "torsional-stiffness",
        help="Equivalent torsional stiffness for shaft segments in series",
    )
    p_ts.add_argument("--G", type=float, default=None)
    p_ts.add_argument("--length", action="append", type=float, required=True)
    p_ts.add_argument("--J", action="append", type=float, default=None)
    p_ts.add_argument("--k", action="append", type=float, default=None)
    p_ts.add_argument("--outfile", type=str, default=None)

    p_run = sub.add_parser("run", help="Run a JSON problem file from in/")
    p_run.add_argument("--infile", type=str, required=True)
    p_run.add_argument("--outfile", type=str, default=None)

    return parser


def _build_vector_pairs(ns: argparse.Namespace) -> list[VectorPair]:
    xz_vals = ns.xz or []
    xy_vals = ns.xy or []
    labels = ns.label or []

    if len(xz_vals) != len(xy_vals):
        raise ValueError("vector-sum requires the same number of --xz and --xy values")

    pairs: list[VectorPair] = []
    for i, (xz, xy) in enumerate(zip(xz_vals, xy_vals)):
        label = labels[i] if i < len(labels) else None
        pairs.append(
            VectorPair(
                xz=float(xz),
                xy=float(xy),
                units=ns.units,
                label=label,
            )
        )
    return pairs


def _build_torsion_segments_for_angle(ns: argparse.Namespace) -> list[TorsionSegment]:
    lengths = ns.length or []
    Js = ns.J or []
    torques = ns.torque or []

    if len(lengths) != len(Js):
        raise ValueError(
            "torsion-angle requires the same number of --length and --J values"
        )

    segments: list[TorsionSegment] = []
    for i, (L, J) in enumerate(zip(lengths, Js)):
        torque = torques[i] if i < len(torques) else None
        segments.append(
            TorsionSegment(
                length=float(L),
                J=float(J),
                torque=float(torque) if torque is not None else None,
            )
        )
    return segments


def _build_torsion_segments_for_stiffness(ns: argparse.Namespace) -> list[TorsionSegment]:
    lengths = ns.length or []
    Js = ns.J or []
    ks = ns.k or []

    if ks and len(ks) != len(lengths):
        raise ValueError(
            "torsional-stiffness requires the same number of --length and --k values"
        )

    if Js and len(Js) != len(lengths):
        raise ValueError(
            "torsional-stiffness requires the same number of --length and --J values"
        )

    if not ks and not Js:
        raise ValueError(
            "torsional-stiffness requires either repeated --k values or repeated --J values"
        )

    segments: list[TorsionSegment] = []
    for i, L in enumerate(lengths):
        J = Js[i] if i < len(Js) else None
        k_i = ks[i] if i < len(ks) else None
        segments.append(
            TorsionSegment(
                length=float(L),
                J=float(J) if J is not None else None,
                k=float(k_i) if k_i is not None else None,
            )
        )
    return segments


def dispatch(ns: argparse.Namespace) -> dict[str, Any]:
    if ns.command == "endurance":
        model = EnduranceLimitInput(
            se_prime=float(ns.se_prime),
            ka=float(ns.ka),
            kb=float(ns.kb),
            kc=float(ns.kc),
            kd=float(ns.kd),
            ke=float(ns.ke),
            kf_misc=float(ns.kf_misc),
        )
        return EnduranceLimitCalculator(model).solve()

    if ns.command == "fatigue":
        model = FatigueInput(
            criterion=str(ns.criterion),
            Kf=float(ns.Kf),
            Kfs=float(ns.Kfs),
            Se=float(ns.Se),
            Sut=float(ns.Sut) if ns.Sut is not None else None,
            Sy=float(ns.Sy) if ns.Sy is not None else None,
            Ma=float(ns.Ma),
            Mm=float(ns.Mm),
            Ta=float(ns.Ta),
            Tm=float(ns.Tm),
            d=float(ns.d) if ns.d is not None else None,
            n=float(ns.n) if ns.n is not None else None,
            strength_unit=str(ns.strength_unit),
        )
        return FatigueCalculator(model).solve()

    if ns.command == "yield":
        model = YieldInput(
            Kf=float(ns.Kf),
            Kfs=float(ns.Kfs),
            Sy=float(ns.Sy),
            d=float(ns.d),
            Ma=float(ns.Ma),
            Mm=float(ns.Mm),
            Ta=float(ns.Ta),
            Tm=float(ns.Tm),
            strength_unit=str(ns.strength_unit),
        )
        return YieldCalculator(model).solve()

    if ns.command == "vector-sum":
        pairs = _build_vector_pairs(ns)
        return DeflectionVectorCalculator(pairs).solve()

    if ns.command == "diameter-resize":
        model = DiameterResizeInput(
            d_old=float(ns.d_old),
            response_old=float(ns.response_old),
            response_allow=float(ns.response_allow),
            n_design=float(ns.n_design),
            mode=str(ns.mode),
        )
        return DiameterResizeCalculator(model).solve()

    if ns.command == "torsion-angle":
        segments = _build_torsion_segments_for_angle(ns)
        model = TorsionInput(
            G=float(ns.G),
            T=float(ns.T) if ns.T is not None else None,
            segments=segments,
        )
        return TorsionCalculator(model).angle_of_twist()

    if ns.command == "torsional-stiffness":
        segments = _build_torsion_segments_for_stiffness(ns)
        model = TorsionInput(
            G=float(ns.G) if ns.G is not None else None,
            segments=segments,
        )
        return TorsionCalculator(model).stiffness()

    if ns.command == "run":
        infile = _resolve_infile(ns.infile)
        problem = _load_problem(infile)
        result = _run_problem(problem)
        result["_meta"] = {
            "infile": str(infile),
            "pkg_dir": str(PKG_DIR),
            "in_dir": str(IN_DIR),
            "out_dir": str(OUT_DIR),
        }
        return result

    raise ValueError(f"Unsupported command: {ns.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)

    try:
        result = dispatch(ns)
        _print_json(result)

        outfile = _resolve_outfile(
            getattr(ns, "outfile", None),
            default_name=f"{ns.command}.json",
        )
        if outfile is not None:
            _write_outfile(outfile, result)

        return 0

    except Exception as exc:
        err = {
            "ok": False,
            "command": getattr(ns, "command", None),
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
        _print_json(err)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())