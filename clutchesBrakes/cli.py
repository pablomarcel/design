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

BUTTON_PAD_TEMPLATE = {
    "schema": "clutchesBrakes.v1",
    "problem_type": "button_pad_caliper",
    "meta": {
        "name": "button_pad_caliper_example_16_4",
        "reference": "Shigley Example 16-4",
        "note": "Clean givens-only input. The solver interpolates Table 16-1 internally and then applies Eqs. 16-41, 16-42, and 16-43."
    },
    "givens": {
        "mu": 0.31,
        "pad_radius": 0.5,
        "eccentricity": 2.0,
        "disk_diameter": 3.5,
        "pmax_allowable": 700.0,
        "operating_fraction_of_allowable": 0.5,
        "n_active_sides": 1
    },
    "solve_for": [
        "actuating_force_F",
        "torque_one_side"
    ]
}


FLYWHEEL_TEMPLATE = {
    "schema": "clutchesBrakes.v1",
    "problem_type": "flywheel",
    "meta": {
        "name": "flywheel_example_16_6",
        "reference": "Shigley Example 16-6",
        "note": "Clean givens-only input. The torque-angle table is supplied separately as a CSV file. For textbook part (c), pin the fluctuation interval under analysis.fluctuation_interval_deg."
    },
    "givens": {
        "nominal_angular_speed_rad_per_s": 250.0,
        "coefficient_of_speed_fluctuation": 0.1
    },
    "data_sources": {
        "torque_table_csv": "table_16_6.csv"
    },
    "analysis": {
        "fluctuation_interval_deg": {
            "start": 0.0,
            "end": 180.0
        }
    }
}
TEMPERATURE_RISE_CALIPER_TEMPLATE = {
    "schema": "clutchesBrakes.v1",
    "problem_type": "temperature_rise_caliper",
    "meta": {
        "name": "temperature_rise_caliper_example_16_5",
        "reference": "Shigley Example 16-5",
        "note": "Clean givens-only problem definition. Digitized figures and table are referenced separately under data_sources."
    },
    "givens": {
        "number_of_brake_uses_per_hour": 24.0,
        "initial_speed_rev_per_min": 250.0,
        "final_speed_rev_per_min": 0.0,
        "mean_air_speed_ft_per_s": 25.0,
        "equivalent_rotary_inertia_lbm_in_s2": 289.0,
        "disk_density_lbm_per_in3": 0.282,
        "specific_heat_capacity_Btu_per_lbm_F": 0.108,
        "disk_diameter_in": 6.0,
        "disk_thickness_in": 0.25,
        "pad_material": "dry sintered metal",
        "lateral_area_in2": 50.0,
        "ambient_temperature_F": 70.0
    },
    "iteration": {
        "initial_temperature_rise_guess_F": 200.0,
        "tolerance_temperature_rise_F": 0.5,
        "max_iterations": 50
    },
    "data_sources": {
        "figure_16_24_a": "data/figure_16_24_a.csv",
        "figure_16_24_b": "data/figure_16_24_b.csv",
        "table_16_3": "data/table_16_3.csv"
    }
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI app for selected Shigley clutches and brakes problems.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Solve problem from JSON file in ./in")
    p_run.add_argument("--infile", required=True)
    p_run.add_argument("--outfile", required=True)

    p_tpl = sub.add_parser("template", help="Write a template JSON into ./out")
    p_tpl.add_argument("problem_type", choices=["doorstop", "rim_brake", "annular_pad", "button_pad_caliper", "temperature_rise_caliper", "flywheel"])
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

    p_b = sub.add_parser("button_pad_caliper", help="Solve circular button-pad caliper brake from Table 16-1 and Eqs. 16-41 to 16-43")
    p_b.add_argument("--mu", type=float, required=True)
    p_b.add_argument("--pad-radius", type=float, required=True)
    p_b.add_argument("--eccentricity", type=float, required=True)
    p_b.add_argument("--disk-diameter", type=float)
    p_b.add_argument("--pmax-operating", type=float)
    p_b.add_argument("--pmax-allowable", type=float)
    p_b.add_argument("--operating-fraction-of-allowable", type=float)
    p_b.add_argument("--p-avg", type=float)
    p_b.add_argument("--n-active-sides", type=int, default=1)
    p_b.add_argument("--outfile")

    p_t = sub.add_parser("temperature_rise_caliper", help="Solve Example 16-5 style steady-state temperature rise in a caliper brake")
    p_t.add_argument("--uses-per-hour", type=float, required=True)
    p_t.add_argument("--initial-speed-rpm", type=float, required=True)
    p_t.add_argument("--final-speed-rpm", type=float, default=0.0)
    p_t.add_argument("--mean-air-speed-ft-s", type=float, required=True)
    p_t.add_argument("--inertia-lbm-in-s2", type=float, required=True)
    p_t.add_argument("--density-lbm-in3", type=float, required=True)
    p_t.add_argument("--cp-btu-lbm-f", type=float, required=True)
    p_t.add_argument("--disk-diameter-in", type=float, required=True)
    p_t.add_argument("--disk-thickness-in", type=float, required=True)
    p_t.add_argument("--lateral-area-in2", type=float, required=True)
    p_t.add_argument("--ambient-temp-f", type=float, required=True)
    p_t.add_argument("--pad-material", required=True)
    p_t.add_argument("--guess-rise-f", type=float, default=200.0)
    p_t.add_argument("--tol-rise-f", type=float, default=0.5)
    p_t.add_argument("--max-iterations", type=int, default=50)
    p_t.add_argument("--figure-16-24-a", default="data/figure_16_24_a.csv")
    p_t.add_argument("--figure-16-24-b", default="data/figure_16_24_b.csv")
    p_t.add_argument("--table-16-3", default="data/table_16_3.csv")
    p_t.add_argument("--outfile")


    p_f = sub.add_parser("flywheel", help="Solve flywheel energy-fluctuation problem from torque-angle table")
    p_f.add_argument("--nominal-angular-speed-rad-s", type=float, required=True)
    p_f.add_argument("--coefficient-of-speed-fluctuation", type=float, required=True)
    p_f.add_argument("--torque-table-csv", required=True)
    p_f.add_argument("--fluctuation-start-deg", type=float)
    p_f.add_argument("--fluctuation-end-deg", type=float)
    p_f.add_argument("--outfile")

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
                "button_pad_caliper": BUTTON_PAD_TEMPLATE,
                "temperature_rise_caliper": TEMPERATURE_RISE_CALIPER_TEMPLATE,
                "flywheel": FLYWHEEL_TEMPLATE,
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

        if args.command == "button_pad_caliper":
            payload = {
                "givens": {
                    "mu": args.mu,
                    "pad_radius": args.pad_radius,
                    "eccentricity": args.eccentricity,
                    "disk_diameter": args.disk_diameter,
                    "pmax_operating": args.pmax_operating,
                    "pmax_allowable": args.pmax_allowable,
                    "operating_fraction_of_allowable": args.operating_fraction_of_allowable,
                    "p_avg": args.p_avg,
                    "n_active_sides": args.n_active_sides,
                }
            }
            result = API.solve("button_pad_caliper", payload)
            maybe_write(result, args.outfile)
            print(result)
            return 0

        if args.command == "temperature_rise_caliper":
            payload = {
                "givens": {
                    "number_of_brake_uses_per_hour": args.uses_per_hour,
                    "initial_speed_rev_per_min": args.initial_speed_rpm,
                    "final_speed_rev_per_min": args.final_speed_rpm,
                    "mean_air_speed_ft_per_s": args.mean_air_speed_ft_s,
                    "equivalent_rotary_inertia_lbm_in_s2": args.inertia_lbm_in_s2,
                    "disk_density_lbm_per_in3": args.density_lbm_in3,
                    "specific_heat_capacity_Btu_per_lbm_F": args.cp_btu_lbm_f,
                    "disk_diameter_in": args.disk_diameter_in,
                    "disk_thickness_in": args.disk_thickness_in,
                    "lateral_area_in2": args.lateral_area_in2,
                    "ambient_temperature_F": args.ambient_temp_f,
                    "pad_material": args.pad_material,
                },
                "iteration": {
                    "initial_temperature_rise_guess_F": args.guess_raise_f if hasattr(args, 'guess_raise_f') else args.guess_rise_f,
                    "tolerance_temperature_rise_F": args.tol_rise_f,
                    "max_iterations": args.max_iterations,
                },
                "data_sources": {
                    "figure_16_24_a": args.figure_16_24_a,
                    "figure_16_24_b": args.figure_16_24_b,
                    "table_16_3": args.table_16_3,
                },
            }
            result = API.solve("temperature_rise_caliper", payload)
            maybe_write(result, args.outfile)
            print(result)
            return 0


        if args.command == "flywheel":
            payload = {
                "givens": {
                    "nominal_angular_speed_rad_per_s": args.nominal_angular_speed_rad_s,
                    "coefficient_of_speed_fluctuation": args.coefficient_of_speed_fluctuation,
                },
                "data_sources": {
                    "torque_table_csv": args.torque_table_csv,
                },
            }
            if args.fluctuation_start_deg is not None or args.fluctuation_end_deg is not None:
                if args.fluctuation_start_deg is None or args.fluctuation_end_deg is None:
                    raise ClutchesBrakesError("Provide both --fluctuation-start-deg and --fluctuation-end-deg, or neither.")
                payload["analysis"] = {
                    "fluctuation_interval_deg": {
                        "start": args.fluctuation_start_deg,
                        "end": args.fluctuation_end_deg,
                    }
                }
            result = API.solve("flywheel", payload)
            maybe_write(result, args.outfile)
            print(result)
            return 0

        parser.error("Unknown command")
    except ClutchesBrakesError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
