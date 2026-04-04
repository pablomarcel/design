from __future__ import annotations

import argparse
import sys
from pathlib import Path

from apis import ClutchesBrakesAPI
from in_out import IOManager
from utils import ClutchesBrakesError

BASE_DIR = Path(__file__).resolve().parent
IO = IOManager(BASE_DIR)
API = ClutchesBrakesAPI()


DOORSTOP_TEMPLATE = {
    "schema": "clutchesBrakes.v1",
    "problem_type": "doorstop",
    "meta": {"name": "doorstop_case"},
    "F": 10.0,
    "a": 4.0,
    "b": 2.0,
    "c": 1.6,
    "w1": 1.0,
    "w2": 0.75,
    "mu": 0.4,
    "pressure_model": "uniform",
    "motion": "leftward"
}

RIM_BRAKE_TEMPLATE = {
    "schema": "clutchesBrakes.v1",
    "problem_type": "rim_brake",
    "meta": {"name": "rim_brake_case"},
    "givens": {
        "mu": 0.32,
        "p_a": 1_000_000.0,
        "b": 0.032,
        "r": 0.150,
        "a": 0.1227,
        "c": 0.212,
        "theta1_deg": 0.0,
        "theta2_deg": 126.0,
        "theta_a_deg": 90.0,
        "rotation": "clockwise",
        "actuation_angle_deg": 24.0,
        "actuation_x_sign": 1,
        "actuation_y_sign": 1
    },
    "paired_shoe": {
        "givens": {
            "mu": 0.32,
            "b": 0.032,
            "r": 0.150,
            "a": 0.1227,
            "c": 0.212,
            "theta1_deg": 0.0,
            "theta2_deg": 126.0,
            "theta_a_deg": 90.0,
            "rotation": "counterclockwise",
            "actuation_angle_deg": 24.0,
            "actuation_x_sign": -1,
            "actuation_y_sign": 1
        }
    }
}

ANNULAR_TEMPLATE = {
    "schema": "clutchesBrakes.v1",
    "problem_type": "annular_pad",
    "meta": {"name": "annular_pad_case"},
    "givens": {
        "model": "uniform_wear",
        "mu": 0.37,
        "ri": 3.875,
        "ro": 5.50,
        "theta1_deg": 36.0,
        "theta2_deg": 144.0,
        "n_pads": 2,
        "torque_total": 13000.0,
        "cylinder_diameter": 1.5,
        "n_cylinders": 2
    }
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI app for selected Shigley clutches and brakes problems.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Solve problem from JSON file in ./in")
    p_run.add_argument("--infile", required=True)
    p_run.add_argument("--outfile", required=True)

    p_tpl = sub.add_parser("template", help="Write a template JSON into ./out")
    p_tpl.add_argument("problem_type", choices=["doorstop", "rim_brake", "annular_pad"])
    p_tpl.add_argument("--outfile", required=True)

    p_d = sub.add_parser("doorstop", help="Solve doorstop problem with CLI flags")
    p_d.add_argument("--F", type=float, required=True)
    p_d.add_argument("--a", type=float, required=True)
    p_d.add_argument("--b", type=float, required=True)
    p_d.add_argument("--c", type=float, required=True)
    p_d.add_argument("--w1", type=float, required=True)
    p_d.add_argument("--w2", type=float, required=True)
    p_d.add_argument("--mu", type=float, required=True)
    p_d.add_argument("--pressure-model", choices=["uniform", "linear"], required=True)
    p_d.add_argument("--motion", choices=["leftward", "rightward"], required=True)
    p_d.add_argument("--outfile")

    p_r = sub.add_parser("rim_brake", help="Solve rim brake with optional paired-shoe backsolve using derived actuator components")
    p_r.add_argument("--mu", type=float, required=True)
    p_r.add_argument("--p-a", type=float, required=True)
    p_r.add_argument("--b", type=float, required=True)
    p_r.add_argument("--r", type=float, required=True)
    p_r.add_argument("--a", type=float, required=True)
    p_r.add_argument("--c", type=float, required=True)
    p_r.add_argument("--theta1-deg", type=float, required=True)
    p_r.add_argument("--theta2-deg", type=float, required=True)
    p_r.add_argument("--theta-a-deg", type=float, default=90.0)
    p_r.add_argument("--rotation", choices=["clockwise", "counterclockwise"], required=True)
    p_r.add_argument("--actuation-angle-deg", type=float, required=True, help="Actuator force angle measured from the positive y-axis.")
    p_r.add_argument("--actuation-x-sign", type=int, choices=[-1, 1], default=1)
    p_r.add_argument("--actuation-y-sign", type=int, choices=[-1, 1], default=1)
    p_r.add_argument("--pair-enable", action="store_true", help="Enable paired-shoe backsolve using the shared actuator force from the main shoe.")
    p_r.add_argument("--pair-mu", type=float)
    p_r.add_argument("--pair-b", type=float)
    p_r.add_argument("--pair-r", type=float)
    p_r.add_argument("--pair-a", type=float)
    p_r.add_argument("--pair-c", type=float)
    p_r.add_argument("--pair-theta1-deg", type=float)
    p_r.add_argument("--pair-theta2-deg", type=float)
    p_r.add_argument("--pair-theta-a-deg", type=float)
    p_r.add_argument("--pair-rotation", choices=["clockwise", "counterclockwise"])
    p_r.add_argument("--pair-actuation-angle-deg", type=float)
    p_r.add_argument("--pair-actuation-x-sign", type=int, choices=[-1, 1])
    p_r.add_argument("--pair-actuation-y-sign", type=int, choices=[-1, 1])
    p_r.add_argument("--outfile")

    p_a = sub.add_parser("annular_pad", help="Solve annular-pad caliper brake")
    p_a.add_argument("--model", choices=["uniform_wear", "uniform_pressure"], required=True)
    p_a.add_argument("--mu", type=float, required=True)
    p_a.add_argument("--ri", type=float, required=True)
    p_a.add_argument("--ro", type=float, required=True)
    p_a.add_argument("--theta1-deg", type=float, default=0.0)
    p_a.add_argument("--theta2-deg", type=float, required=True)
    p_a.add_argument("--n-pads", type=int, default=2)
    p_a.add_argument("--torque-total", type=float)
    p_a.add_argument("--p-a", type=float)
    p_a.add_argument("--F", type=float)
    p_a.add_argument("--cylinder-diameter", type=float)
    p_a.add_argument("--n-cylinders", type=int, default=1)
    p_a.add_argument("--outfile")

    return parser


def maybe_write(result: dict, outfile: str | None) -> None:
    if outfile:
        outpath = IO.write_json(result, outfile)
        print(f"Wrote {outpath}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            payload = IO.read_json(args.infile)
            result = API.solve_from_payload(payload)
            maybe_write(result, args.outfile)
            print(result)
            return 0

        if args.command == "template":
            template_map = {
                "doorstop": DOORSTOP_TEMPLATE,
                "rim_brake": RIM_BRAKE_TEMPLATE,
                "annular_pad": ANNULAR_TEMPLATE,
            }
            outpath = IO.write_json(template_map[args.problem_type], args.outfile)
            print(f"Wrote template {outpath}")
            return 0

        if args.command == "doorstop":
            payload = {
                "F": args.F,
                "a": args.a,
                "b": args.b,
                "c": args.c,
                "w1": args.w1,
                "w2": args.w2,
                "mu": args.mu,
                "pressure_model": args.pressure_model,
                "motion": args.motion,
            }
            result = API.solve("doorstop", payload)
            maybe_write(result, args.outfile)
            print(result)
            return 0

        if args.command == "rim_brake":
            payload = {
                "givens": {
                    "mu": args.mu,
                    "p_a": args.p_a,
                    "b": args.b,
                    "r": args.r,
                    "a": args.a,
                    "c": args.c,
                    "theta1_deg": args.theta1_deg,
                    "theta2_deg": args.theta2_deg,
                    "theta_a_deg": args.theta_a_deg,
                    "rotation": args.rotation,
                    "actuation_angle_deg": args.actuation_angle_deg,
                    "actuation_x_sign": args.actuation_x_sign,
                    "actuation_y_sign": args.actuation_y_sign,
                }
            }
            if args.pair_enable:
                pair_payload = {
                    "givens": {
                        "mu": args.pair_mu if args.pair_mu is not None else args.mu,
                        "b": args.pair_b if args.pair_b is not None else args.b,
                        "r": args.pair_r if args.pair_r is not None else args.r,
                        "a": args.pair_a if args.pair_a is not None else args.a,
                        "c": args.pair_c if args.pair_c is not None else args.c,
                        "theta1_deg": args.pair_theta1_deg if args.pair_theta1_deg is not None else args.theta1_deg,
                        "theta2_deg": args.pair_theta2_deg if args.pair_theta2_deg is not None else args.theta2_deg,
                        "theta_a_deg": args.pair_theta_a_deg if args.pair_theta_a_deg is not None else args.theta_a_deg,
                        "rotation": args.pair_rotation if args.pair_rotation is not None else ("counterclockwise" if args.rotation == "clockwise" else "clockwise"),
                        "actuation_angle_deg": args.pair_actuation_angle_deg if args.pair_actuation_angle_deg is not None else args.actuation_angle_deg,
                        "actuation_x_sign": args.pair_actuation_x_sign if args.pair_actuation_x_sign is not None else -args.actuation_x_sign,
                        "actuation_y_sign": args.pair_actuation_y_sign if args.pair_actuation_y_sign is not None else args.actuation_y_sign,
                    }
                }
                payload["paired_shoe"] = pair_payload
            result = API.solve("rim_brake", payload)
            maybe_write(result, args.outfile)
            print(result)
            return 0

        if args.command == "annular_pad":
            payload = {
                "givens": {
                    "model": args.model,
                    "mu": args.mu,
                    "ri": args.ri,
                    "ro": args.ro,
                    "theta1_deg": args.theta1_deg,
                    "theta2_deg": args.theta2_deg,
                    "n_pads": args.n_pads,
                    "torque_total": args.torque_total,
                    "p_a": args.p_a,
                    "F": args.F,
                    "cylinder_diameter": args.cylinder_diameter,
                    "n_cylinders": args.n_cylinders,
                }
            }
            result = API.solve("annular_pad", payload)
            maybe_write(result, args.outfile)
            print(result)
            return 0

        parser.error("Unknown command")
    except ClutchesBrakesError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
