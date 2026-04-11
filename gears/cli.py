from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

try:
    from .app import GearForceApp  # type: ignore
except Exception:  # pragma: no cover
    from app import GearForceApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gear force analysis CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Solve a problem from an input JSON file")
    run_p.add_argument("--infile", required=True, help="Input JSON file name, usually located in ./in")
    run_p.add_argument("--outfile", required=False, help="Output JSON file name, usually located in ./out")
    run_p.add_argument("--no-pretty", action="store_true", help="Disable rich terminal report")

    inline = sub.add_parser("solve", help="Solve directly from an inline JSON string")
    inline.add_argument("--json", required=True, help="Full problem JSON payload")
    inline.add_argument("--outfile", required=False)
    inline.add_argument("--no-pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = GearForceApp(base_dir=Path(__file__).resolve().parent)

    if args.command == "run":
        app.run_from_file(args.infile, outfile=args.outfile, pretty=not args.no_pretty)
        return 0

    if args.command == "solve":
        problem: Dict[str, Any] = json.loads(args.json)
        app.run_from_dict(problem, outfile=args.outfile, pretty=not args.no_pretty)
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
