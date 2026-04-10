from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from app import SpurHelicalGearsApp


console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spur and helical gears CLI app based on Shigley/AGMA workflows.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Solve a problem from an input JSON file.")
    run.add_argument("--infile", required=True, help="Input JSON file. Prefer files inside ./in.")
    run.add_argument("--outfile", required=False, help="Output JSON file. Prefer files inside ./out.")
    run.add_argument("--pretty", action="store_true", help="Pretty-print the result JSON to the console.")

    return parser


def _render_key_value_table(title: str, mapping: dict[str, Any]) -> None:
    table = Table(title=title, show_lines=False)
    table.add_column("Field", justify="left", width=32)
    table.add_column("Value", justify="right", width=24)
    for key, value in mapping.items():
        table.add_row(str(key), json.dumps(value) if isinstance(value, (dict, list)) else str(value))
    console.print(table)


def _render_iteration_table(iterations: list[dict[str, Any]]) -> None:
    if not iterations:
        return
    row_labels = [
        "d_P_in", "d_G_in", "V_ft_min", "W_t_lbf", "K_v", "F_trial_in", "F_bend_in", "F_wear_in",
        "F_selected_in", "K_s_P", "K_s_G", "K_m", "I", "S_t_psi", "S_c_psi", "sigma_P_psi",
        "sigma_G_psi", "S_F_P", "S_F_G", "sigma_c_P_psi", "sigma_c_G_psi", "S_H_P", "S_H_G",
        "pinion_threat", "gear_threat", "rim_ht_in", "rim_tR_min_in",
    ]
    table = Table(title="Spur design iteration summary", show_lines=True)
    table.add_column("Metric", width=22, no_wrap=True)
    col_width = 14
    for it in iterations:
        table.add_column(f"P_d={it['P_d']}", width=col_width, justify="center", no_wrap=True)
    for label in row_labels:
        values = [str(it.get(label, "")) for it in iterations]
        table.add_row(label, *values)
    console.print(table)


def main() -> None:
    args = build_parser().parse_args()
    app = SpurHelicalGearsApp()

    if args.command == "run":
        result, saved_path = app.run_from_file(args.infile, args.outfile)
        if result.get("problem") == "spur_design":
            _render_iteration_table(result.get("iterations", []))
        else:
            _render_key_value_table("Derived quantities", result.get("derived", {}))
            _render_key_value_table("Outputs", result.get("outputs", {}))
        if args.pretty:
            console.print_json(data=result)
        elif saved_path:
            console.print(f"Saved output JSON to: {saved_path}")


if __name__ == "__main__":
    main()
