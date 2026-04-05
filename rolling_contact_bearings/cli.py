from __future__ import annotations

import argparse
from pprint import pprint

try:
    from .apis import solve
    from .in_out import load_json, save_json
    from .utils import pretty_data
except ImportError:
    from apis import solve
    from in_out import load_json, save_json
    from utils import pretty_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rolling_contact_bearings")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Solve a problem from an input JSON file")
    run.add_argument("--infile", required=True)
    run.add_argument("--outfile")

    basic = sub.add_parser(
        "catalog_c10", help="Example 11-1 style basic catalog C10 using Eq. 11-3"
    )
    basic.add_argument("--FD", type=float, required=True)
    basic.add_argument("--hours", type=float, required=True)
    basic.add_argument("--speed-rpm", type=float, required=True)
    basic.add_argument("--a", type=float, default=3.0)
    basic.add_argument("--LR-rev", type=float, default=1_000_000.0)
    basic.add_argument("--outfile")

    reliable = sub.add_parser(
        "catalog_c10_reliable", help="Example 11-3 style reliability-adjusted C10"
    )
    reliable.add_argument("--FD", type=float, required=True)
    reliable.add_argument("--af", type=float, required=True)
    reliable.add_argument("--hours", type=float, required=True)
    reliable.add_argument("--speed-rpm", type=float, required=True)
    reliable.add_argument("--reliability", type=float, required=True)
    reliable.add_argument("--a", type=float, required=True)
    reliable.add_argument("--x0", type=float, required=True)
    reliable.add_argument("--theta-minus-x0", type=float, required=True)
    reliable.add_argument("--b", type=float, required=True)
    reliable.add_argument("--LR-rev", type=float, default=1_000_000.0)
    reliable.add_argument("--outfile")

    tl = sub.add_parser(
        "tapered_reliability",
        help="Compute tapered pair reliability from selected bearing",
    )
    tl.add_argument("--xD", type=float, required=True)
    tl.add_argument("--C10", type=float, required=True)
    tl.add_argument("--af", type=float, required=True)
    tl.add_argument("--FeA", type=float, required=True)
    tl.add_argument("--FeB", type=float, required=True)
    tl.add_argument("--outfile")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        payload = load_json(args.infile)
        result = pretty_data(solve(payload))
        if args.outfile:
            save_json(result, args.outfile)
        pprint(result)
        return
    if args.command == "catalog_c10":
        payload = {
            "problem_type": "catalog_c10_basic",
            "FD": args.FD,
            "hours": args.hours,
            "speed_rpm": args.speed_rpm,
            "a": args.a,
            "LR_rev": args.LR_rev,
        }
        result = pretty_data(solve(payload))
        if args.outfile:
            save_json(result, args.outfile)
        pprint(result)
        return
    if args.command == "catalog_c10_reliable":
        payload = {
            "problem_type": "catalog_c10_reliable",
            "FD": args.FD,
            "af": args.af,
            "hours": args.hours,
            "speed_rpm": args.speed_rpm,
            "reliability": args.reliability,
            "LR_rev": args.LR_rev,
            "weibull": {
                "a": args.a,
                "x0": args.x0,
                "theta_minus_x0": args.theta_minus_x0,
                "b": args.b,
            },
        }
        result = pretty_data(solve(payload))
        if args.outfile:
            save_json(result, args.outfile)
        pprint(result)
        return
    if args.command == "tapered_reliability":
        payload = {
            "problem_type": "tapered_pair_reliability",
            "xD": args.xD,
            "C10": args.C10,
            "af": args.af,
            "FeA": args.FeA,
            "FeB": args.FeB,
        }
        result = pretty_data(solve(payload))
        if args.outfile:
            save_json(result, args.outfile)
        pprint(result)
        return


if __name__ == "__main__":
    main()
