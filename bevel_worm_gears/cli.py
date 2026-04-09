from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .app import BevelWormGearApp
    from .in_out import in_dir
except ImportError:  # pragma: no cover
    from app import BevelWormGearApp
    from in_out import in_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI app for Shigley bevel and worm gear calculations.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Solve a problem from an input JSON file.")
    run.add_argument("--infile", required=True, help="Input JSON file name or absolute path.")
    run.add_argument("--outfile", required=True, help="Output JSON file name or absolute path.")

    tmpl = sub.add_parser("list-inputs", help="List sample input JSON files in the in directory.")
    tmpl.add_argument("--absolute", action="store_true", help="Show absolute paths.")

    solve_paths = sub.add_parser("list-solve-paths", help="List supported solve_path values.")
    solve_paths.add_argument("--json", action="store_true", help="Print as JSON.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    app = BevelWormGearApp()
    if args.command == "run":
        outpath = app.run_file(args.infile, args.outfile)
        print(str(outpath))
        return
    if args.command == "list-inputs":
        paths = sorted(in_dir().glob("*.json"))
        payload = [str(p.resolve() if args.absolute else p.name) for p in paths]
        print(json.dumps(payload, indent=2))
        return
    if args.command == "list-solve-paths":
        payload = [
            "straight_bevel_analysis",
            "straight_bevel_mesh_design",
            "worm_analysis",
            "worm_mesh_design",
        ]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("\n".join(payload))
        return
    raise SystemExit(2)


if __name__ == "__main__":
    main()
