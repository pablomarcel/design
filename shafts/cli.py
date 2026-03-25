from __future__ import annotations

import argparse
import sys
from typing import Any

try:
    from .app import ShaftApp
except ImportError:  # pragma: no cover - local package execution shim
    from app import ShaftApp


class ShaftsCLI:
    def __init__(self) -> None:
        self.app = ShaftApp()

    def build(self) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            prog="shafts",
            description="Shigley Chapter 7 style shaft design CLI",
        )
        sub = p.add_subparsers(dest="command", required=True)

        c = sub.add_parser("endurance", help="Compute real endurance limit Se from Se-prime and Marin factors")
        c.add_argument("--se-prime", type=float, required=True)
        for name in ["ka", "kb", "kc", "kd", "ke", "kf-misc"]:
            c.add_argument(f"--{name}", type=float, default=1.0)
        c.add_argument("--save", action="store_true")
        c.add_argument("--outfile")

        c = sub.add_parser("fatigue", help="Fatigue factor of safety or required diameter")
        c.add_argument("--criterion", required=True, choices=["de_goodman", "de_gerber", "de_asme_elliptic", "de_soderberg"])
        c.add_argument("--Kf", type=float, required=True)
        c.add_argument("--Kfs", type=float, required=True)
        c.add_argument("--Se", type=float, required=True)
        c.add_argument("--Sut", type=float)
        c.add_argument("--Sy", type=float)
        c.add_argument("--Ma", type=float, default=0.0)
        c.add_argument("--Mm", type=float, default=0.0)
        c.add_argument("--Ta", type=float, default=0.0)
        c.add_argument("--Tm", type=float, default=0.0)
        c.add_argument("--d", type=float)
        c.add_argument("--n", type=float)
        c.add_argument("--save", action="store_true")
        c.add_argument("--outfile")

        c = sub.add_parser("yield", help="Yielding check per Eq. 7-15 and 7-16")
        c.add_argument("--Kf", type=float, required=True)
        c.add_argument("--Kfs", type=float, required=True)
        c.add_argument("--Sy", type=float, required=True)
        c.add_argument("--d", type=float, required=True)
        c.add_argument("--Ma", type=float, default=0.0)
        c.add_argument("--Mm", type=float, default=0.0)
        c.add_argument("--Ta", type=float, default=0.0)
        c.add_argument("--Tm", type=float, default=0.0)
        c.add_argument("--save", action="store_true")
        c.add_argument("--outfile")

        c = sub.add_parser("vector-sum", help="Orthogonal vector addition for slope/deflection pairs")
        c.add_argument("--label", action="append", default=[])
        c.add_argument("--xz", action="append", type=float, default=[])
        c.add_argument("--xy", action="append", type=float, default=[])
        c.add_argument("--units", default="")
        c.add_argument("--save", action="store_true")
        c.add_argument("--outfile")

        c = sub.add_parser("diameter-resize", help="New diameter from allowable deflection or slope")
        c.add_argument("--d-old", type=float, required=True)
        c.add_argument("--response-old", type=float, required=True)
        c.add_argument("--response-allow", type=float, required=True)
        c.add_argument("--n-design", type=float, default=1.0)
        c.add_argument("--mode", choices=["deflection", "slope"], default="deflection")
        c.add_argument("--save", action="store_true")
        c.add_argument("--outfile")

        c = sub.add_parser("torsion-angle", help="Angle of twist for stepped shaft")
        c.add_argument("--G", type=float, required=True)
        c.add_argument("--T", type=float)
        c.add_argument("--length", action="append", type=float, default=[])
        c.add_argument("--J", action="append", type=float, default=[])
        c.add_argument("--torque", action="append", type=float, default=[])
        c.add_argument("--save", action="store_true")
        c.add_argument("--outfile")

        c = sub.add_parser("torsional-stiffness", help="Equivalent torsional stiffness from segment stiffnesses or GJ/L")
        c.add_argument("--G", type=float)
        c.add_argument("--length", action="append", type=float, default=[])
        c.add_argument("--J", action="append", type=float, default=[])
        c.add_argument("--k", action="append", type=float, default=[])
        c.add_argument("--save", action="store_true")
        c.add_argument("--outfile")

        c = sub.add_parser("run", help="Solve a problem definition JSON from shafts/in or an explicit path")
        c.add_argument("--infile", required=True)
        c.add_argument("--outfile")
        c.add_argument("--no-save", action="store_true")

        return p

    def _segments_with_optional_torque(self, lengths: list[float], Js: list[float], torques: list[float]) -> list[dict[str, Any]]:
        if len(lengths) != len(Js):
            raise ValueError("--length and --J must have the same number of values")
        if torques and len(torques) != len(lengths):
            raise ValueError("If provided, --torque count must match --length count")
        out = []
        for i, (L, J) in enumerate(zip(lengths, Js)):
            item: dict[str, Any] = {"length": L, "J": J}
            if torques:
                item["torque"] = torques[i]
            out.append(item)
        return out

    def _segments_with_optional_k(self, lengths: list[float], Js: list[float], ks: list[float]) -> list[dict[str, Any]]:
        if ks and len(ks) != len(lengths):
            raise ValueError("If provided, --k count must match --length count")
        if Js and len(Js) != len(lengths):
            raise ValueError("If provided, --J count must match --length count")
        out = []
        for i, L in enumerate(lengths):
            item: dict[str, Any] = {"length": L}
            if Js:
                item["J"] = Js[i]
            if ks:
                item["k"] = ks[i]
            out.append(item)
        return out

    def execute(self, argv: list[str] | None = None) -> int:
        parser = self.build()
        ns = parser.parse_args(argv)
        cmd = ns.command

        try:
            if cmd == "endurance":
                payload = {
                    "se_prime": ns.se_prime,
                    "ka": ns.ka,
                    "kb": ns.kb,
                    "kc": ns.kc,
                    "kd": ns.kd,
                    "ke": ns.ke,
                    "kf_misc": getattr(ns, "kf_misc"),
                }
                result = self.app.run_request("endurance_limit", payload, save=ns.save, outfile=ns.outfile)
            elif cmd == "fatigue":
                payload = {
                    "criterion": ns.criterion,
                    "Kf": ns.Kf,
                    "Kfs": ns.Kfs,
                    "Se": ns.Se,
                    "Sut": ns.Sut,
                    "Sy": ns.Sy,
                    "Ma": ns.Ma,
                    "Mm": ns.Mm,
                    "Ta": ns.Ta,
                    "Tm": ns.Tm,
                    "d": ns.d,
                    "n": ns.n,
                }
                result = self.app.run_request("fatigue", payload, save=ns.save, outfile=ns.outfile)
            elif cmd == "yield":
                payload = {
                    "Kf": ns.Kf,
                    "Kfs": ns.Kfs,
                    "Sy": ns.Sy,
                    "d": ns.d,
                    "Ma": ns.Ma,
                    "Mm": ns.Mm,
                    "Ta": ns.Ta,
                    "Tm": ns.Tm,
                }
                result = self.app.run_request("yield", payload, save=ns.save, outfile=ns.outfile)
            elif cmd == "vector-sum":
                if len(ns.xz) != len(ns.xy):
                    raise ValueError("--xz and --xy must have the same number of values")
                labels = ns.label or []
                pairs = []
                for i, (xz, xy) in enumerate(zip(ns.xz, ns.xy), start=1):
                    label = labels[i - 1] if i - 1 < len(labels) else f"point_{i}"
                    pairs.append({"label": label, "xz": xz, "xy": xy, "units": ns.units})
                result = self.app.run_request("vector_sum", {"pairs": pairs}, save=ns.save, outfile=ns.outfile)
            elif cmd == "diameter-resize":
                payload = {
                    "d_old": ns.d_old,
                    "response_old": ns.response_old,
                    "response_allow": ns.response_allow,
                    "n_design": ns.n_design,
                    "mode": ns.mode,
                }
                result = self.app.run_request("diameter_resize", payload, save=ns.save, outfile=ns.outfile)
            elif cmd == "torsion-angle":
                segs = self._segments_with_optional_torque(ns.length, ns.J, ns.torque)
                payload = {"G": ns.G, "T": ns.T, "segments": segs}
                result = self.app.run_request("torsion_angle", payload, save=ns.save, outfile=ns.outfile)
            elif cmd == "torsional-stiffness":
                segs = self._segments_with_optional_k(ns.length, ns.J, ns.k)
                payload = {"G": ns.G, "segments": segs}
                result = self.app.run_request("torsional_stiffness", payload, save=ns.save, outfile=ns.outfile)
            elif cmd == "run":
                result = self.app.run_json(ns.infile, save=not ns.no_save, outfile=ns.outfile)
            else:  # pragma: no cover
                raise RuntimeError("Unknown command")
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        self.app.io.print_result(result)
        return 0


def main(argv: list[str] | None = None) -> int:
    return ShaftsCLI().execute(argv)


if __name__ == "__main__":
    raise SystemExit(main())
