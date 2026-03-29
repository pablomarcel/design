from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

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
            from rich.table import Table
            from rich.panel import Panel
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

    def _render_plain(self, result: Dict[str, Any]) -> None:
        print("=" * 88)
        print(result["title"])
        print("=" * 88)
        for section_name in ("inputs", "derived", "chart_inputs_used", "outputs", "checks"):
            print(f"\n[{section_name}]")
            section = result.get(section_name, {})
            if not section:
                print("  -")
                continue
            for k, v in section.items():
                print(f"  {k:32s} {fmt(v)}")
        notes = result.get("notes", [])
        if notes:
            print("\n[notes]")
            for note in notes:
                print(f"  - {note}")

    def _render_rich(self, result: Dict[str, Any]) -> None:
        assert self._rich_console is not None
        Table = self._rich_table
        Panel = self._rich_panel
        self._rich_console.print(Panel.fit(result["title"], subtitle=result.get("problem", "")))
        for section_name in ("inputs", "derived", "chart_inputs_used", "outputs", "checks"):
            section = result.get(section_name, {})
            table = Table(title=section_name.replace("_", " "), show_header=True)
            table.add_column("Name", style="cyan")
            table.add_column("Value", style="white")
            if not section:
                table.add_row("-", "-")
            else:
                for k, v in section.items():
                    table.add_row(str(k), fmt(v))
            self._rich_console.print(table)
        notes = result.get("notes", [])
        if notes:
            note_table = Table(title="notes")
            note_table.add_column("#", style="cyan")
            note_table.add_column("Text", style="white")
            for idx, note in enumerate(notes, start=1):
                note_table.add_row(str(idx), str(note))
            self._rich_console.print(note_table)
