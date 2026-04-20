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
    parser = argparse.ArgumentParser(description='CLI app for stress, strain, strain-rosette, and isotropic Hooke-law analysis.')
    subparsers = parser.add_subparsers(dest='command', required=True)
    run_parser = subparsers.add_parser('run', help='Run a solve path using CLI flags.')
    run_parser.add_argument('--solve-path', default='general_3d_stress', help='Solver route.')

    run_parser.add_argument('--sxx', type=float, default=None)
    run_parser.add_argument('--syy', type=float, default=None)
    run_parser.add_argument('--szz', type=float, default=None)
    run_parser.add_argument('--txy', type=float, default=0.0)
    run_parser.add_argument('--tyz', type=float, default=0.0)
    run_parser.add_argument('--txz', '--tzx', dest='txz', type=float, default=0.0)

    run_parser.add_argument('--exx', type=float, default=None)
    run_parser.add_argument('--eyy', type=float, default=None)
    run_parser.add_argument('--ezz', type=float, default=None)
    run_parser.add_argument('--gxy', type=float, default=0.0)
    run_parser.add_argument('--gyz', '--gzy', dest='gyz', type=float, default=0.0)
    run_parser.add_argument('--gxz', '--gzx', dest='gxz', type=float, default=0.0)

    run_parser.add_argument('--ea', type=float, default=None, help='Rosette strain a')
    run_parser.add_argument('--eb', type=float, default=None, help='Rosette strain b')
    run_parser.add_argument('--ec', type=float, default=None, help='Rosette strain c')
    run_parser.add_argument('--theta-a-deg', type=float, default=None)
    run_parser.add_argument('--theta-b-deg', type=float, default=None)
    run_parser.add_argument('--theta-c-deg', type=float, default=None)

    run_parser.add_argument('--epsilon-theta', type=float, default=None, help='Single-gage measured normal strain along theta')
    run_parser.add_argument('--theta-deg', type=float, default=None, help='Single-gage measurement angle from +x, ccw')
    run_parser.add_argument('--known-sigma-x', type=float, default=None, help='Known biaxial plane-stress sigma_x for the single-gage solve path')

    run_parser.add_argument('--E', type=float, default=None, help='Young modulus')
    run_parser.add_argument('--nu', type=float, default=None, help='Poisson ratio')
    run_parser.add_argument('--G', type=float, default=None, help='Shear modulus')

    run_parser.add_argument('--phi-deg', type=float, default=None)
    run_parser.add_argument('--unit', '--strain-unit', '--stress-unit', dest='unit', default='')
    run_parser.add_argument('--stress-output-unit', dest='stress_unit', default='')
    run_parser.add_argument('--title', default='')
    run_parser.add_argument('--outfile', default='')
    run_parser.add_argument('--plotfile', default='')
    run_parser.add_argument('--pretty', action='store_true')
    run_parser.add_argument('--show', action='store_true')
    run_parser.add_argument('--show-plot', action='store_true')
    run_parser.add_argument('--no-plot', action='store_true')

    list_parser = subparsers.add_parser('list', help='List available solve paths.')
    list_parser.add_argument('--json', action='store_true')
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == 'list':
        api = SolverAPI()
        available = api.registry.available()
        if args.json:
            print(json.dumps({'solve_paths': available}, indent=2))
        else:
            print('Available solve paths:')
            for item in available:
                print(f'- {item}')
        return

    app = LoadStressApp()
    try:
        payload = app.solve_flags(
            solve_path=args.solve_path,
            sxx=args.sxx, syy=args.syy, szz=args.szz, txy=args.txy, tyz=args.tyz, txz=args.txz,
            exx=args.exx, eyy=args.eyy, ezz=args.ezz, gxy=args.gxy, gyz=args.gyz, gxz=args.gxz,
            ea=args.ea, eb=args.eb, ec=args.ec,
            theta_a_deg=args.theta_a_deg, theta_b_deg=args.theta_b_deg, theta_c_deg=args.theta_c_deg,
            epsilon_theta=args.epsilon_theta, theta_deg=args.theta_deg, known_sigma_x=args.known_sigma_x,
            E=args.E, nu=args.nu, G=args.G,
            phi_deg=args.phi_deg,
            unit=args.unit, stress_unit=args.stress_unit, title=args.title,
            outfile=args.outfile or None, plotfile=args.plotfile or None,
            pretty=args.pretty, make_plot=not args.no_plot, show_plot=args.show_plot,
        )
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1) from exc

    if args.show:
        print(json.dumps(payload, indent=2))
    else:
        json_path = payload.get('artifacts', {}).get('json_output')
        plot_path = payload.get('artifacts', {}).get('plot_output')
        print('Solve completed.')
        if json_path:
            print(f'JSON output : {json_path}')
        if plot_path:
            print(f'Plot output : {plot_path}')


if __name__ == '__main__':
    main()
