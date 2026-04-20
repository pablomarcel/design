from __future__ import annotations

import argparse
import json
import sys

try:
    from .app import LoadStressApp
    from .apis import SolverAPI
except ImportError:
    from app import LoadStressApp
    from apis import SolverAPI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI app for general three-dimensional stress and strain analysis with Mohr-circle reporting."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a stress-state or strain-state solve path using CLI flags.")
    run_parser.add_argument(
        "--solve-path",
        default="general_3d_stress",
        help="Solver route. Examples: general_3d_stress, plane_stress_rotation, general_3d_strain, plane_strain_rotation",
    )

    # Stress flags
    run_parser.add_argument("--sxx", type=float, default=None, help="Normal stress sigma_xx")
    run_parser.add_argument("--syy", type=float, default=None, help="Normal stress sigma_yy")
    run_parser.add_argument("--szz", type=float, default=None, help="Normal stress sigma_zz")
    run_parser.add_argument("--txy", type=float, default=0.0, help="Shear stress tau_xy")
    run_parser.add_argument("--tyz", type=float, default=0.0, help="Shear stress tau_yz")
    run_parser.add_argument("--txz", "--tzx", dest="txz", type=float, default=0.0, help="Shear stress tau_xz")

    # Strain flags
    run_parser.add_argument("--exx", type=float, default=None, help="Normal strain epsilon_xx")
    run_parser.add_argument("--eyy", type=float, default=None, help="Normal strain epsilon_yy")
    run_parser.add_argument("--ezz", type=float, default=None, help="Normal strain epsilon_zz")
    run_parser.add_argument("--gxy", type=float, default=0.0, help="Engineering shear strain gamma_xy")
    run_parser.add_argument("--gyz", "--gzy", dest="gyz", type=float, default=0.0, help="Engineering shear strain gamma_yz")
    run_parser.add_argument("--gxz", "--gzx", dest="gxz", type=float, default=0.0, help="Engineering shear strain gamma_xz")

    run_parser.add_argument("--phi-deg", type=float, default=None, help="Optional in-plane rotation angle in degrees. Plane-state only.")
    run_parser.add_argument(
        "--unit",
        "--stress-unit",
        "--strain-unit",
        dest="unit",
        default="",
        help="Optional engineering unit label, e.g. MPa, ksi, strain, microstrain, µε.",
    )
    run_parser.add_argument("--title", default="", help="Optional report title.")
    run_parser.add_argument("--outfile", default="", help="Optional JSON output file path.")
    run_parser.add_argument("--plotfile", default="", help="Optional plot output file path.")
    run_parser.add_argument("--pretty", action="store_true", help="Write formatted JSON output.")
    run_parser.add_argument("--show", action="store_true", help="Print the full JSON payload to stdout.")
    run_parser.add_argument("--show-plot", action="store_true", help="Display the matplotlib plot window.")
    run_parser.add_argument("--no-plot", action="store_true", help="Skip plot generation.")

    list_parser = subparsers.add_parser("list", help="List available solve paths.")
    list_parser.add_argument("--json", action="store_true", help="Emit available solve paths as JSON.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list":
        api = SolverAPI()
        available = api.registry.available()
        if args.json:
            print(json.dumps({"solve_paths": available}, indent=2))
        else:
            print("Available solve paths:")
            for item in available:
                print(f"- {item}")
        return

    app = LoadStressApp()
    try:
        payload = app.solve_flags(
            solve_path=args.solve_path,
            sxx=args.sxx,
            syy=args.syy,
            szz=args.szz,
            txy=args.txy,
            tyz=args.tyz,
            txz=args.txz,
            exx=args.exx,
            eyy=args.eyy,
            ezz=args.ezz,
            gxy=args.gxy,
            gyz=args.gyz,
            gxz=args.gxz,
            phi_deg=args.phi_deg,
            unit=args.unit,
            title=args.title,
            outfile=args.outfile or None,
            plotfile=args.plotfile or None,
            pretty=args.pretty,
            make_plot=not args.no_plot,
            show_plot=args.show_plot,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.show:
        print(json.dumps(payload, indent=2))
    else:
        json_path = payload.get("artifacts", {}).get("json_output")
        plot_path = payload.get("artifacts", {}).get("plot_output")
        print("Solve completed.")
        if json_path:
            print(f"JSON output : {json_path}")
        if plot_path:
            print(f"Plot output : {plot_path}")


if __name__ == "__main__":
    main()
