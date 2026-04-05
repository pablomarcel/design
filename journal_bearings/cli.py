from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from apis import JournalBearingAPI
from in_out import ConsoleRenderer, read_problem_file, write_result_file
from utils import normalize_problem_name


def _add_common_bearing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--mu', type=float, required=True, help='Absolute viscosity.')
    parser.add_argument('--N', type=float, required=True, help='Journal speed in rev/s.')
    parser.add_argument('--W', type=float, required=True, help='Bearing load.')
    parser.add_argument('--r', type=float, required=True, help='Journal radius.')
    parser.add_argument('--c', type=float, required=True, help='Radial clearance.')
    parser.add_argument('--l', type=float, required=True, help='Bearing length.')
    parser.add_argument('--Ps', type=float, default=0.0, help='Supply pressure. Default is 0 for non-pressure-fed bearings.')
    parser.add_argument(
        '--unit-system',
        default='ips',
        choices=['ips', 'custom'],
        help='ips is the current reference system for convenience outputs like hp and Btu/s.',
    )
    parser.add_argument('--outfile', help='Optional JSON output file.')


def _add_temperature_rise_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--oil-grade', required=True, help='SAE oil grade such as 10, 20, 30, 40, 50, 60.')
    parser.add_argument('--inlet-temp-f', type=float, required=True, help='Inlet temperature in degrees F.')
    parser.add_argument('--rho', type=float, default=0.0315, help='Oil density in lbm/in^3 for ips workflows.')
    parser.add_argument('--cp', type=float, default=0.48, help='Specific heat in Btu/(lbm*F) for ips workflows.')
    parser.add_argument('--J', type=float, default=778.0 * 12.0, help='Mechanical equivalent of heat. Default 778*12 in·lbf/Btu.')
    parser.add_argument('--temp-tol-f', type=float, default=2.0, help='Convergence tolerance on successive effective temperatures.')
    parser.add_argument('--max-iter', type=int, default=50, help='Maximum number of temperature-viscosity iterations.')


def _add_self_contained_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--N', type=float, required=True, help='Journal speed in rev/s.')
    parser.add_argument('--W', type=float, required=True, help='Bearing load.')
    parser.add_argument('--r', type=float, required=True, help='Journal radius.')
    parser.add_argument('--c', type=float, required=True, help='Radial clearance.')
    parser.add_argument('--l', type=float, required=True, help='Bearing length.')
    parser.add_argument('--oil-grade', required=True, help='SAE oil grade such as 10, 20, 30, 40, 50, 60.')
    parser.add_argument('--ambient-temp-f', type=float, required=True, help='Ambient air temperature in degrees F.')
    parser.add_argument('--alpha', type=float, required=True, help='Geometry factor alpha from Shigley Eq. (12-19).')
    parser.add_argument('--area-in2', type=float, required=True, help='Lateral bearing area A in in^2.')
    parser.add_argument('--h-cr', type=float, required=True, help='Heat-transfer coefficient h_CR in Btu/(h*ft^2*F).')
    parser.add_argument(
        '--unit-system',
        default='ips',
        choices=['ips', 'custom'],
        help='ips is the current reference system for convenience outputs like hp and Btu/s.',
    )
    parser.add_argument('--temp-tol-f', type=float, default=2.0, help='Convergence tolerance on the final temperature bracket width.')
    parser.add_argument('--max-iter', type=int, default=60, help='Maximum number of heat-balance bisection iterations.')
    parser.add_argument('--outfile', help='Optional JSON output file.')



def _add_pressure_fed_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--N', type=float, required=True, help='Journal speed in rev/s.')
    parser.add_argument('--W', type=float, required=True, help='Radial load in lbf.')
    parser.add_argument('--oil-grade', required=True, help='SAE oil grade such as 20.')
    parser.add_argument('--sump-temp-f', type=float, required=True, help='Externally maintained sump temperature Ts in degrees F.')
    parser.add_argument('--Ps', type=float, required=True, help='Supply pressure ps in psi.')
    parser.add_argument('--r', type=float, help='Journal radius in inches. Optional when --dj is provided.')
    parser.add_argument('--dj', type=float, help='Journal diameter dj in inches. Optional when --r is provided.')
    parser.add_argument('--c', type=float, required=True, help='Minimum radial clearance in inches (direct given input).')
    parser.add_argument('--l-prime', type=float, required=True, help='Half-bearing length l-prime in inches.')
    parser.add_argument('--l-prime-over-d', type=float, required=True, help='Given l-prime/d ratio used for table lookup.')
    parser.add_argument('--rho', type=float, default=0.0311, help='Oil density in lbm/in^3 for ips workflows.')
    parser.add_argument('--cp', type=float, default=0.42, help='Specific heat in Btu/(lbm*F) for ips workflows.')
    parser.add_argument('--J', type=float, default=9336.0, help='Mechanical equivalent of heat in in·lbf/Btu. Default 9336.')
    parser.add_argument('--heat-loss-limit-btu-h', type=float, default=None, help='Optional allowable heat-loss rate for a quick design check.')
    parser.add_argument('--temp-tol-f', type=float, default=0.5, help='Convergence tolerance on T_trial - T_av in degrees F.')
    parser.add_argument('--max-iter', type=int, default=60, help='Maximum number of film-temperature iterations.')
    parser.add_argument(
        '--unit-system',
        default='ips',
        choices=['ips', 'custom'],
        help='ips is the current reference system for convenience outputs.',
    )
    parser.add_argument('--outfile', help='Optional JSON output file.')




def _add_boundary_lubricated_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--bearing-model', required=True, help='Boundary-lubricated bearing model, e.g. oiles_500_sp.')
    parser.add_argument('--length', '--l', dest='length', type=float, required=True, help='Bearing length in inches.')
    parser.add_argument('--bore', '--dj', dest='bore', type=float, required=True, help='Bore diameter in inches.')
    parser.add_argument('--ambient-temp-f', type=float, required=True, help='Ambient temperature in degrees F.')
    parser.add_argument('--foreign-matter', action='store_true', help='Set when foreign matter is present in the environment.')
    parser.add_argument('--allowable-wear-in', type=float, required=True, help='Allowable radial wear in inches.')
    parser.add_argument('--radial-load-lbf', '--W', dest='radial_load_lbf', type=float, required=True, help='Radial load in lbf.')
    parser.add_argument('--velocity-fpm', '--peripheral-velocity-fpm', dest='velocity_fpm', type=float, required=True, help='Peripheral velocity in ft/min.')
    parser.add_argument('--motion-type', default='rotary', choices=['rotary', 'oscillatory', 'reciprocating'], help='Mode of motion for Table 12-10.')
    parser.add_argument('--oscillation-angle-band', choices=['>30', '<30'], help='Required for oscillatory motion.')
    parser.add_argument('--outfile', help='Optional JSON output file.')
    parser.add_argument(
        '--unit-system',
        default='ips',
        choices=['ips', 'custom'],
        help='ips is the current reference system for convenience outputs.',
    )


def _common_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        'mu': args.mu,
        'N': args.N,
        'W': args.W,
        'r': args.r,
        'c': args.c,
        'l': args.l,
        'Ps': args.Ps,
        'unit_system': args.unit_system,
    }
    for key, argname in (
        ('oil_grade', 'oil_grade'),
        ('inlet_temp_F', 'inlet_temp_f'),
        ('rho', 'rho'),
        ('cp', 'cp'),
        ('J', 'J'),
        ('temp_tol_F', 'temp_tol_f'),
        ('max_iter', 'max_iter'),
    ):
        if hasattr(args, argname):
            data[key] = getattr(args, argname)
    return data


def _self_contained_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        'N': args.N,
        'W': args.W,
        'r': args.r,
        'c': args.c,
        'l': args.l,
        'oil_grade': args.oil_grade,
        'ambient_temp_F': args.ambient_temp_f,
        'alpha': args.alpha,
        'area_in2': args.area_in2,
        'h_cr': args.h_cr,
        'unit_system': args.unit_system,
        'temp_tol_F': args.temp_tol_f,
        'max_iter': args.max_iter,
    }





def _boundary_lubricated_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        'bearing_model': args.bearing_model,
        'dj': args.bore,
        'l': args.length,
        'ambient_temp_F': args.ambient_temp_f,
        'foreign_matter': args.foreign_matter,
        'allowable_wear_in': args.allowable_wear_in,
        'W': args.radial_load_lbf,
        'peripheral_velocity_fpm': args.velocity_fpm,
        'motion_type': args.motion_type,
        'oscillation_angle_band': args.oscillation_angle_band,
        'unit_system': args.unit_system,
        'r': args.bore / 2.0,
        'c': 1.0,
        'N': 1.0,
        'mu': None,
        'Ps': 0.0,
    }



def _add_boundary_lubricated_temperature_rise_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--bearing-model', required=True, help='Boundary-lubricated bearing model, e.g. oiles_500_sp.')
    parser.add_argument('--ambient-temp-f', type=float, required=True, help='Ambient temperature in degrees F.')
    parser.add_argument('--foreign-matter', action='store_true', help='Set when foreign matter is present in the environment.')
    parser.add_argument('--allowable-wear-in', type=float, required=True, help='Maximum allowable wear in inches.')
    parser.add_argument('--hours-of-use', type=float, required=True, help='Required service life in hours.')
    parser.add_argument('--rpm', type=float, required=True, help='Journal speed in rev/min.')
    parser.add_argument('--radial-load-lbf', '--W', dest='radial_load_lbf', type=float, required=True, help='Radial load in lbf.')
    parser.add_argument('--h-cr', type=float, required=True, help='Heat-transfer coefficient h_CR in Btu/(h*ft^2*F).')
    parser.add_argument('--tmax-f', type=float, required=True, help='Maximum allowable operating temperature in degrees F.')
    parser.add_argument('--friction-coefficient-fs', '--fs', dest='friction_coefficient_fs', type=float, help='Optional friction coefficient fs. If omitted, Table 12-9 is used from the bearing model.')
    parser.add_argument('--design-factor', type=float, required=True, help='Design factor n_d.')
    parser.add_argument('--motion-type', default='rotary', choices=['rotary', 'oscillatory', 'reciprocating'], help='Mode of motion for Table 12-10.')
    parser.add_argument('--oscillation-angle-band', choices=['>30', '<30'], help='Required for oscillatory motion.')
    parser.add_argument('--outfile', help='Optional JSON output file.')
    parser.add_argument(
        '--unit-system',
        default='ips',
        choices=['ips', 'custom'],
        help='ips is the current reference system for convenience outputs.',
    )


def _boundary_lubricated_temperature_rise_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        'bearing_model': args.bearing_model,
        'ambient_temp_F': args.ambient_temp_f,
        'foreign_matter': args.foreign_matter,
        'allowable_wear_in': args.allowable_wear_in,
        'hours_of_use': args.hours_of_use,
        'N': args.rpm,
        'W': args.radial_load_lbf,
        'h_cr': args.h_cr,
        'Tmax_F': args.tmax_f,
        'mu': args.friction_coefficient_fs,
        'design_factor': args.design_factor,
        'motion_type': args.motion_type,
        'oscillation_angle_band': args.oscillation_angle_band,
        'unit_system': args.unit_system,
        'r': 0.5,
        'c': 1.0,
        'l': 1.0,
        'Ps': 0.0,
    }


def _pressure_fed_inputs_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        'N': args.N,
        'W': args.W,
        'oil_grade': args.oil_grade,
        'sump_temp_F': args.sump_temp_f,
        'Ps': args.Ps,
        'c': args.c,
        'l_prime': args.l_prime,
        'l_prime_over_d': args.l_prime_over_d,
        'rho': args.rho,
        'cp': args.cp,
        'J': args.J,
        'temp_tol_F': args.temp_tol_f,
        'max_iter': args.max_iter,
        'unit_system': args.unit_system,
    }
    if args.r is not None:
        data['r'] = args.r
    if args.dj is not None:
        data['dj'] = args.dj
    if args.heat_loss_limit_btu_h is not None:
        data['heat_loss_limit_btu_h'] = args.heat_loss_limit_btu_h
    return data


def _default_outfile_for_input(infile: str | Path) -> Path:
    infile = Path(infile)
    return Path('out') / f'{infile.stem}_result.json'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python -m cli',
        description='Automatic journal-bearing app backed by finite_journal_bearing.csv and interpolation.',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    pmenu = sub.add_parser('menu', help='Launch an interactive menu workflow.')
    pmenu.add_argument('--outfile', help='Optional JSON output file.')

    for name, help_text in (
        ('minimum_film_thickness', 'Compute minimum film thickness, eccentricity, and phi automatically.'),
        ('coefficient_of_friction', 'Compute coefficient of friction, torque, and power loss automatically.'),
        ('volumetric_flow_rate', 'Compute flow rates automatically.'),
        ('maximum_film_pressure', 'Compute maximum film pressure automatically.'),
    ):
        p = sub.add_parser(name, help=help_text)
        _add_common_bearing_args(p)

    ptemp = sub.add_parser('temperature_rise', help='Compute temperature rise with iterative viscosity update.')
    _add_common_bearing_args(ptemp)
    _add_temperature_rise_args(ptemp)

    pself = sub.add_parser('self_contained_steady_state', help='Solve Shigley self-contained steady-state bearing problems like Example 12-5.')
    _add_self_contained_args(pself)

    ppf = sub.add_parser('pressure_fed_circumferential', help='Solve Shigley pressure-fed circumferential-groove bearing problems like Example 12-6.')
    _add_pressure_fed_args(ppf)

    pbl = sub.add_parser('boundary_lubricated_bearing', help='Solve Shigley boundary-lubricated bearing problems like Example 12-7.')
    _add_boundary_lubricated_args(pbl)

    pblt = sub.add_parser('boundary_lubricated_temperature_rise', help='Solve Shigley boundary-lubricated bearing sizing problems with temperature rise like Example 12-8.')
    _add_boundary_lubricated_temperature_rise_args(pblt)

    prun = sub.add_parser('run', help='Solve a problem from an input JSON file.')
    prun.add_argument('--infile', required=True, help='Input JSON file in the in/ folder or any path.')
    prun.add_argument('--outfile', help='Output JSON filename or path.')
    return parser


def _menu_problem_choice() -> str:
    options = {
        '1': 'minimum_film_thickness',
        '2': 'coefficient_of_friction',
        '3': 'volumetric_flow_rate',
        '4': 'maximum_film_pressure',
        '5': 'temperature_rise',
        '6': 'self_contained_steady_state',
        '7': 'pressure_fed_circumferential',
        '8': 'boundary_lubricated_bearing',
        '9': 'boundary_lubricated_temperature_rise',
    }
    print('\nJournal Bearings Menu')
    print('  1) minimum film thickness')
    print('  2) coefficient of friction')
    print('  3) volumetric flow rate')
    print('  4) maximum film pressure')
    print('  5) temperature rise')
    print('  6) self-contained steady state')
    print('  7) pressure-fed circumferential groove bearing')
    print('  8) boundary-lubricated bearing')
    print('  9) boundary-lubricated bearing with temperature rise')
    while True:
        choice = input('Choose an option [1-9]: ').strip()
        if choice in options:
            return options[choice]
        print('Invalid option. Try again.')


def _prompt_float(label: str, default: float | None = None) -> float:
    while True:
        suffix = f' [default {default}]' if default is not None else ''
        raw = input(f'{label}{suffix}: ').strip()
        if raw == '' and default is not None:
            return float(default)
        try:
            return float(raw)
        except ValueError:
            print(f'Could not parse a number from {raw!r}. Try again.')


def _interactive_common_inputs(problem: str) -> Dict[str, Any]:
    if problem == 'self_contained_steady_state':
        print('\nEnter the self-contained steady-state bearing givens.')
        unit_system = input('unit system [default ips]: ').strip().lower() or 'ips'
        return {
            'N': _prompt_float('N'),
            'W': _prompt_float('W'),
            'r': _prompt_float('r'),
            'c': _prompt_float('c'),
            'l': _prompt_float('l'),
            'oil_grade': input('oil grade (SAE) [e.g. 20]: ').strip(),
            'ambient_temp_F': _prompt_float('ambient_temp_F'),
            'alpha': _prompt_float('alpha'),
            'area_in2': _prompt_float('area_in2'),
            'h_cr': _prompt_float('h_cr'),
            'unit_system': unit_system,
            'temp_tol_F': _prompt_float('temp_tol_F', 2.0),
            'max_iter': int(_prompt_float('max_iter', 60)),
        }

    if problem == 'boundary_lubricated_bearing':
        print('\nEnter the boundary-lubricated bearing givens.')
        unit_system = input('unit system [default ips]: ').strip().lower() or 'ips'
        data: Dict[str, Any] = {
            'bearing_model': input('bearing_model [e.g. oiles_500_sp]: ').strip(),
            'dj': _prompt_float('bore'),
            'l': _prompt_float('length'),
            'ambient_temp_F': _prompt_float('ambient_temp_F'),
            'allowable_wear_in': _prompt_float('allowable_wear_in'),
            'W': _prompt_float('radial_load_lbf'),
            'peripheral_velocity_fpm': _prompt_float('velocity_fpm'),
            'motion_type': input('motion_type [rotary/oscillatory/reciprocating] [default rotary]: ').strip().lower() or 'rotary',
            'unit_system': unit_system,
        }
        fm = input('foreign matter present? [y/N]: ').strip().lower()
        data['foreign_matter'] = fm in {'y', 'yes', 'true', '1'}
        if data['motion_type'] == 'oscillatory':
            data['oscillation_angle_band'] = input('oscillation_angle_band [>30 or <30]: ').strip()
        data['r'] = data['dj'] / 2.0
        return data

    if problem == 'boundary_lubricated_temperature_rise':
        print('\nEnter the boundary-lubricated bearing with temperature-rise givens.')
        unit_system = input('unit system [default ips]: ').strip().lower() or 'ips'
        data: Dict[str, Any] = {
            'bearing_model': input('bearing_model [e.g. oiles_500_sp]: ').strip(),
            'ambient_temp_F': _prompt_float('ambient_temp_F'),
            'allowable_wear_in': _prompt_float('allowable_wear_in'),
            'hours_of_use': _prompt_float('hours_of_use'),
            'N': _prompt_float('rpm'),
            'W': _prompt_float('radial_load_lbf'),
            'h_cr': _prompt_float('h_cr'),
            'Tmax_F': _prompt_float('Tmax_F'),
            'design_factor': _prompt_float('design_factor'),
            'motion_type': input('motion_type [rotary/oscillatory/reciprocating] [default rotary]: ').strip().lower() or 'rotary',
            'unit_system': unit_system,
            'r': 0.5,
            'c': 1.0,
            'l': 1.0,
            'Ps': 0.0,
        }
        fs_raw = input('friction_coefficient_fs [optional, blank uses Table 12-9]: ').strip()
        data['mu'] = float(fs_raw) if fs_raw else None
        fm = input('foreign matter present? [y/N]: ').strip().lower()
        data['foreign_matter'] = fm in {'y', 'yes', 'true', '1'}
        if data['motion_type'] == 'oscillatory':
            data['oscillation_angle_band'] = input('oscillation_angle_band [>30 or <30]: ').strip()
        return data

    if problem == 'pressure_fed_circumferential':
        print('\nEnter the pressure-fed circumferential-groove bearing givens.')
        unit_system = input('unit system [default ips]: ').strip().lower() or 'ips'
        use_dj = input('Provide dj instead of r? [y/N]: ').strip().lower() in {'y', 'yes'}
        data: Dict[str, Any] = {
            'N': _prompt_float('N'),
            'W': _prompt_float('W'),
            'oil_grade': input('oil grade (SAE) [e.g. 20]: ').strip(),
            'sump_temp_F': _prompt_float('sump_temp_F'),
            'Ps': _prompt_float('Ps'),
            'c': _prompt_float('c'),
            'l_prime': _prompt_float('l_prime'),
            'l_prime_over_d': _prompt_float('l_prime_over_d'),
            'rho': _prompt_float('rho', 0.0311),
            'cp': _prompt_float('cp', 0.42),
            'J': _prompt_float('J', 9336.0),
            'temp_tol_F': _prompt_float('temp_tol_F', 0.5),
            'max_iter': int(_prompt_float('max_iter', 60)),
            'unit_system': unit_system,
        }
        if use_dj:
            data['dj'] = _prompt_float('dj')
        else:
            data['r'] = _prompt_float('r')
        limit = input('heat_loss_limit_btu_h [optional]: ').strip()
        if limit:
            data['heat_loss_limit_btu_h'] = float(limit)
        return data

    print('\nEnter the bearing givens. The app will compute the dimensionless state, interpolate the table, and finish automatically.')
    unit_system = input('unit system [default ips]: ').strip().lower() or 'ips'
    data: Dict[str, Any] = {
        'mu': _prompt_float('mu'),
        'N': _prompt_float('N'),
        'W': _prompt_float('W'),
        'r': _prompt_float('r'),
        'c': _prompt_float('c'),
        'l': _prompt_float('l'),
        'Ps': _prompt_float('Ps', 0.0),
        'unit_system': unit_system,
    }
    if problem == 'temperature_rise':
        data.update(
            {
                'oil_grade': input('oil grade (SAE) [e.g. 10]: ').strip(),
                'inlet_temp_F': _prompt_float('inlet_temp_F'),
                'rho': _prompt_float('rho', 0.0315),
                'cp': _prompt_float('cp', 0.48),
                'J': _prompt_float('J', 778.0 * 12.0),
                'temp_tol_F': _prompt_float('temp_tol_F', 2.0),
                'max_iter': int(_prompt_float('max_iter', 50)),
            }
        )
    return data


def _render_and_write(renderer: ConsoleRenderer, result: Dict[str, Any], outfile: str | Path | None) -> None:
    renderer.render_result(result)
    if outfile:
        write_result_file(outfile, result)
        print(f'\nWrote result file: {outfile}')


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    api = JournalBearingAPI()
    renderer = ConsoleRenderer()

    if args.command == 'menu':
        problem = _menu_problem_choice()
        result = api.solve_problem(problem=problem, inputs=_interactive_common_inputs(problem))
        _render_and_write(renderer, result, args.outfile)
        return 0

    if args.command == 'run':
        payload = read_problem_file(args.infile)
        result = api.solve_problem(problem=payload['problem'], inputs=payload['inputs'])
        outpath = Path(args.outfile) if args.outfile else _default_outfile_for_input(args.infile)
        _render_and_write(renderer, result, outpath)
        return 0

    problem = normalize_problem_name(args.command)
    if problem == 'self_contained_steady_state':
        result = api.solve_problem(problem=problem, inputs=_self_contained_inputs_from_args(args))
    elif problem == 'pressure_fed_circumferential':
        result = api.solve_problem(problem=problem, inputs=_pressure_fed_inputs_from_args(args))
    elif problem == 'boundary_lubricated_bearing':
        result = api.solve_problem(problem=problem, inputs=_boundary_lubricated_inputs_from_args(args))
    elif problem == 'boundary_lubricated_temperature_rise':
        result = api.solve_problem(problem=problem, inputs=_boundary_lubricated_temperature_rise_inputs_from_args(args))
    else:
        result = api.solve_problem(problem=problem, inputs=_common_inputs_from_args(args))
    _render_and_write(renderer, result, args.outfile)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
