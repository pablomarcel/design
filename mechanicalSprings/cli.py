from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

try:
    from apis import MechanicalSpringsAPI
    from in_out import IOHandler
    from utils import IN_DIR, OUT_DIR, round_dict
except ImportError:  # pragma: no cover
    from .apis import MechanicalSpringsAPI
    from .in_out import IOHandler
    from .utils import IN_DIR, OUT_DIR, round_dict


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Mechanical springs CLI for Shigley Chapter 10 compression spring solve paths.")
    sub = p.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Solve a problem definition from a JSON file.")
    p_run.add_argument("--infile", required=True, help="Input JSON file path. Relative paths are resolved from ./in first.")
    p_run.add_argument("--outfile", required=False, help="Output JSON file path. Relative paths are resolved to ./out.")

    p_show = sub.add_parser("show-solve-paths", help="Print the available solve path names.")

    p_inline = sub.add_parser("solve", help="Solve from an inline JSON string.")
    p_inline.add_argument("--payload", required=True, help="JSON payload string with solve_path and inputs.")
    p_inline.add_argument("--outfile", required=False)
    return p


def resolve_infile(name: str) -> Path:
    path = Path(name)
    if path.exists():
        return path
    candidate = IN_DIR / name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(name)


def resolve_outfile(name: str | None) -> Path | None:
    if name is None:
        return None
    path = Path(name)
    if path.is_absolute() or path.parent != Path('.'):
        return path
    return OUT_DIR / name


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    api = MechanicalSpringsAPI()
    io = IOHandler()

    if args.command == "show-solve-paths":
        print("compression_analysis")
        print("static_select")
        print("static_iter_c")
        print("fatigue_check")
        print("fatigue_design_iter")
        print("extension_static_service")
        print("extension_dynamic_loading")
        return 0

    if args.command == "run":
        payload = io.read_json(resolve_infile(args.infile))
    else:
        payload = json.loads(args.payload)

    result = round_dict(api.solve(payload))
    outfile = resolve_outfile(getattr(args, "outfile", None))
    if outfile is not None:
        io.write_json(outfile, result)
        print(outfile)
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
