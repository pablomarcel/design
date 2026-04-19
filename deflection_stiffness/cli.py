#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

# ---------- Import shim so `python deflection_stiffness/cli.py ...` works with absolute imports ----------
# If executed as a script (not as a module), __package__ will be None/""
if __package__ in (None, ""):
    # cli.py lives in deflection_stiffness/cli.py → add the directory that CONTAINS deflection_stiffness/ to sys.path
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)

    from deflection_stiffness.apis import RunRequest
    from deflection_stiffness.app import BeamsApp
    from deflection_stiffness.io import load_problem
    from deflection_stiffness.utils import write_json
else:
    from .apis import RunRequest
    from .app import BeamsApp
    from .io import load_problem
    from .utils import write_json


# ------------------------------ CLI helpers ------------------------------

def _configure_logging(level: str) -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )


def _add_log_level_arg(p: argparse.ArgumentParser, *, dest: str) -> None:
    """Allow --log-level either before or after the subcommand.

    argparse only routes options that appear after a subcommand to that subparser,
    so we accept this flag on each subcommand (with a separate dest) and then
    reconcile in main().
    """
    p.add_argument(
        "--log-level",
        dest=dest,
        default=None,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging verbosity (default: INFO)",
    )


def _add_infile_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--infile", "--config", dest="infile", required=True, help="Path to input JSON file")


def _add_strict_group(p: argparse.ArgumentParser, *, default_strict: bool = True) -> None:
    g = p.add_mutually_exclusive_group()
    if default_strict:
        g.add_argument("--strict", action="store_true", help="Strict validation (default)")
        g.add_argument("--non-strict", action="store_true", help="Do not fail on validation errors")
    else:
        g.add_argument("--strict", action="store_true", help="Fail on validation errors")
        g.add_argument("--non-strict", action="store_true", help="Non-strict validation (default)")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="beams",
        description="2D beam/frame analysis (mechanics project)",
    )

    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging verbosity (default: INFO)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # validate
    p_val = sub.add_parser("validate", help="Validate an input JSON problem")
    _add_log_level_arg(p_val, dest="log_level_sub")
    _add_infile_arg(p_val)
    _add_strict_group(p_val, default_strict=True)

    # solve
    p_sol = sub.add_parser("solve", help="Solve a beam problem from JSON")
    _add_log_level_arg(p_sol, dest="log_level_sub")
    _add_infile_arg(p_sol)
    p_sol.add_argument("--outdir", default=None, help="Output directory (default: sibling out_run)")
    _add_strict_group(p_sol, default_strict=True)

    p_sol.add_argument("--no-csv", action="store_true", help="Disable CSV table outputs")
    p_sol.add_argument("--no-results-json", action="store_true", help="Disable results.json output")
    p_sol.add_argument("--no-plots", action="store_true", help="Disable plot outputs")

    # Plot backend selection
    p_sol.add_argument(
        "--plot-backend",
        choices=["anastruct", "plotly"],
        default=None,
        help="Override plot backend. Default is from input JSON options (recommended: anastruct).",
    )

    # Plotly settings (only used when plot_backend=plotly)
    p_sol.add_argument("--plot-format", choices=["html", "json"], default=None, help="Plotly plot format")

    # Anastruct settings (only used when plot_backend=anastruct)
    p_sol.add_argument(
        "--anastruct-plots",
        default=None,
        help=(
            "Comma-separated list of anastruct native plots. "
            "Choices: structure,reaction_force,axial_force,shear_force,bending_moment,displacement"
        ),
    )
    p_sol.add_argument("--plot-dpi", type=int, default=None, help="DPI for anastruct PNG plots")
    p_sol.add_argument(
        "--plot-figsize",
        type=float,
        nargs=2,
        default=None,
        metavar=("W", "H"),
        help="Figure size in inches for anastruct plots (e.g. --plot-figsize 12 8)",
    )
    p_sol.add_argument("--zip-plots", action="store_true", help="Also create plots.zip containing the PNG plots")

    # Deformation scale hint (plotly uses it directly; anastruct uses best-effort)
    p_sol.add_argument("--deform-scale", type=float, default=None, help="Deformation scale factor override")

    # template
    p_tmp = sub.add_parser("template", help="Write a starter template JSON")
    _add_log_level_arg(p_tmp, dest="log_level_sub")
    p_tmp.add_argument("--kind", choices=["beam_simple", "simply_supported_point"], default="beam_simple")
    p_tmp.add_argument("--outfile", required=True, help="Where to write the template JSON")

    return p


def _resolve_strict(args: argparse.Namespace) -> bool:
    if getattr(args, "non_strict", False):
        return False
    return True


def _parse_csv_list(s: str | None) -> list[str] | None:
    if s is None:
        return None
    items = [x.strip() for x in s.split(",") if x.strip()]
    return items or None


def _template(kind: str) -> dict[str, Any]:
    if kind == "beam_simple":
        return {
            "schema": "beams.v1",
            "meta": {"name": "beam_simple", "note": "Matches beam_simple.py intent (cantilever with UDL)"},
            "units": {"length": "m", "force": "N", "moment": "N*m"},
            "nodes": [
                {"id": "A", "x": 0.0, "y": 0.0},
                {"id": "B", "x": 5.0, "y": 0.0},
            ],
            "elements": [
                {"id": "E1", "n1": "A", "n2": "B", "EA": 1.0e7, "EI": 1.0e4},
            ],
            "supports": [
                {"node": "A", "type": "fixed"},
            ],
            "loads": [
                {"type": "distributed", "element": "E1", "q": -10.0, "direction": "y"},
            ],
            "options": {
                "solver": "anastruct",
                "plots": True,
                "plot_backend": "anastruct",
                "plot_format": "png",
                "deform_scale": 10.0,
                "anastruct_plots": ["structure", "reaction_force", "shear_force", "bending_moment", "displacement"],
                "anastruct_dpi": 150,
                "anastruct_figsize": [12.0, 8.0],
                "anastruct_zip": False,
            },
        }

    # simply supported with a point load
    return {
        "schema": "beams.v1",
        "meta": {"name": "simply_supported_point", "note": "Simply supported beam with midspan point load"},
        "units": {"length": "m", "force": "N", "moment": "N*m"},
        "nodes": [
            {"id": "A", "x": 0.0, "y": 0.0},
            {"id": "B", "x": 5.0, "y": 0.0},
            {"id": "C", "x": 2.5, "y": 0.0},
        ],
        "elements": [
            {"id": "E1", "n1": "A", "n2": "C", "EA": 1.0e7, "EI": 1.0e4},
            {"id": "E2", "n1": "C", "n2": "B", "EA": 1.0e7, "EI": 1.0e4},
        ],
        "supports": [
            {"node": "A", "type": "hinged"},
            {"node": "B", "type": "roller", "dof": "uy"},
        ],
        "loads": [
            {"type": "point", "node": "C", "Fx": 0.0, "Fy": -100.0},
        ],
        "options": {
            "solver": "anastruct",
            "plots": True,
            "plot_backend": "anastruct",
            "plot_format": "png",
            "deform_scale": 10.0,
            "anastruct_plots": ["structure", "reaction_force", "shear_force", "bending_moment", "displacement"],
            "anastruct_dpi": 150,
            "anastruct_figsize": [12.0, 8.0],
            "anastruct_zip": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = _parser()
    args = p.parse_args(argv)
    level = getattr(args, "log_level_sub", None) or args.log_level
    _configure_logging(level)

    if args.cmd == "template":
        d = _template(args.kind)
        write_json(args.outfile, d, indent=2)
        print(f"Wrote template: {args.outfile}")
        return 0

    if args.cmd == "validate":
        prob = load_problem(args.infile)
        strict = _resolve_strict(args)
        issues = prob.validate(strict=strict)
        if issues:
            for i in issues:
                print(f"[{i.level}] {i.message} ({i.path})")
        print("OK" if strict else "DONE")
        return 0

    if args.cmd == "solve":
        app = BeamsApp()
        strict = _resolve_strict(args)

        req = RunRequest(
            infile=args.infile,
            outdir=args.outdir,
            strict=strict,
            write_csv=not args.no_csv,
            write_results_json=not args.no_results_json,
            write_plots=not args.no_plots,
            plot_backend=args.plot_backend,
            plot_format=args.plot_format,
            deform_scale=args.deform_scale,
            anastruct_plots=_parse_csv_list(args.anastruct_plots),
            anastruct_dpi=args.plot_dpi,
            anastruct_figsize=tuple(args.plot_figsize) if args.plot_figsize is not None else None,
            anastruct_zip=True if args.zip_plots else None,
        )

        resp = app.run(req)

        for outp in resp.outputs:
            print(outp)

        if resp.issues:
            for it in resp.issues:
                print(f"[{it.get('level')}] {it.get('message')} ({it.get('path')})")

        return 0 if resp.ok else 2

    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
