from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from utils import dump_json, fmt, load_json


def read_problem_file(path: str | Path) -> Dict[str, Any]:
    return load_json(path)


def write_result_file(path: str | Path, payload: Dict[str, Any]) -> None:
    dump_json(payload, path)


class ConsoleRenderer:
    def __init__(self) -> None:
        self._rich_console = None
        self._rich_table = None
        self._rich_panel = None
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            self._rich_console = Console()
            self._rich_table = Table
            self._rich_panel = Panel
        except Exception:
            self._rich_console = None

    @property
    def has_rich(self) -> bool:
        return self._rich_console is not None

    def render_result(self, result: Dict[str, Any]) -> None:
        if self.has_rich:
            self._render_rich(result)
        else:
            self._render_plain(result)

    def _render_plain_iteration_history(self, history: List[Dict[str, Any]]) -> None:
        print("\n[iteration_history]")
        if not history:
            print("  -")
            return
        keys = [
            "iteration",
            "mu_used",
            "effective_temp_used_F",
            "effective_temp_updated_F",
            "effective_temp_change_F",
            "delta_T_F",
            "Q_leakage",
            "power_in_lbf_s",
            "updated_mu",
        ]
        header = "  " + " | ".join(f"{k:>24s}" for k in keys)
        print(header)
        print("  " + "-" * (len(header) - 2))
        for row in history:
            print("  " + " | ".join(f"{fmt(row.get(k)):>24s}" for k in keys))

    def _render_plain(self, result: Dict[str, Any]) -> None:
        print("=" * 92)
        print(result.get("title", result.get("problem", "journal bearing result")))
        print("=" * 92)
        for section_name in (
            "inputs",
            "derived",
            "table_lookup",
            "interpolated_dimensionless",
            "outputs",
            "checks",
        ):
            section = result.get(section_name, {})
            print(f"\n[{section_name}]")
            if not section:
                print("  -")
                continue
            for key, value in section.items():
                print(f"  {key:36s} {fmt(value)}")
        history = result.get("iteration_history", [])
        if history:
            self._render_plain_iteration_history(history)
        notes = result.get("notes", [])
        if notes:
            print("\n[notes]")
            for note in notes:
                print(f"  - {note}")

    def _render_rich(self, result: Dict[str, Any]) -> None:
        assert self._rich_console is not None
        Table = self._rich_table
        Panel = self._rich_panel
        self._rich_console.print(
            Panel.fit(result.get("title", result.get("problem", "journal bearing result")), subtitle=result.get("problem", ""))
        )
        for section_name in (
            "inputs",
            "derived",
            "table_lookup",
            "interpolated_dimensionless",
            "outputs",
            "checks",
        ):
            section = result.get(section_name, {})
            table = Table(title=section_name.replace("_", " "), show_header=True)
            table.add_column("Name", style="cyan")
            table.add_column("Value", style="white")
            if not section:
                table.add_row("-", "-")
            else:
                for key, value in section.items():
                    table.add_row(str(key), fmt(value))
            self._rich_console.print(table)

        history = result.get("iteration_history", [])
        if history:
            hist_table = Table(title="iteration history", show_header=True)
            keys = [
                "iteration",
                "mu_used",
                "effective_temp_used_F",
                "effective_temp_updated_F",
                "effective_temp_change_F",
                "delta_T_F",
                "Q_leakage",
                "power_in_lbf_s",
                "updated_mu",
            ]
            for key in keys:
                hist_table.add_column(key, style="white")
            for row in history:
                hist_table.add_row(*[fmt(row.get(key)) for key in keys])
            self._rich_console.print(hist_table)

        notes = result.get("notes", [])
        if notes:
            note_table = Table(title="notes")
            note_table.add_column("#", style="cyan")
            note_table.add_column("Text", style="white")
            for idx, note in enumerate(notes, start=1):
                note_table.add_row(str(idx), str(note))
            self._rich_console.print(note_table)
