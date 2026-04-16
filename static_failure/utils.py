from __future__ import annotations

from math import isfinite
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from rich.console import Console
from rich.table import Table


class DisplayUtils:
    """Formatting and console-display helpers for the static_failure package."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    @staticmethod
    def package_root() -> Path:
        return Path(__file__).resolve().parent

    @staticmethod
    def normalize_float(value: Any, digits: int = 6) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not isfinite(value):
                return "inf" if value > 0 else "-inf"
            return round(value, digits)
        return value

    def print_banner(self, title: str) -> None:
        self.console.rule(f"[bold cyan]{title}[/bold cyan]")

    def dataframe_to_rich_table(
        self,
        dataframe: pd.DataFrame,
        title: str | None = None,
        equal_width: int | None = None,
    ) -> Table:
        width = equal_width or self._recommended_equal_width(dataframe)
        table = Table(title=title, show_lines=False, expand=False)
        for column in dataframe.columns:
            table.add_column(
                str(column),
                justify="center",
                min_width=width,
                max_width=width,
                overflow="fold",
                no_wrap=False,
            )
        for _, row in dataframe.iterrows():
            rendered = [self._format_cell(v) for v in row.tolist()]
            table.add_row(*rendered)
        return table

    def print_dataframe(
        self,
        dataframe: pd.DataFrame,
        title: str | None = None,
        equal_width: int | None = None,
    ) -> None:
        table = self.dataframe_to_rich_table(dataframe, title=title, equal_width=equal_width)
        self.console.print(table)

    def print_key_value_block(self, title: str, mapping: dict[str, Any], digits: int = 6) -> None:
        if not mapping:
            return
        rows = [(str(key), self._format_cell(self.normalize_float(value, digits=digits))) for key, value in mapping.items()]
        key_width = max(24, min(40, max(len(k) for k, _ in rows) + 2))
        val_width = 24
        table = Table(title=title, expand=False)
        table.add_column("Field", justify="left", min_width=key_width, max_width=key_width)
        table.add_column("Value", justify="right", min_width=val_width, max_width=val_width)
        for key, value in rows:
            table.add_row(key, value)
        self.console.print(table)

    @staticmethod
    def _recommended_equal_width(dataframe: pd.DataFrame, min_width: int = 12, max_width: int = 18) -> int:
        max_len = 0
        for column in dataframe.columns:
            max_len = max(max_len, len(str(column)))
        for _, row in dataframe.iterrows():
            for value in row.tolist():
                max_len = max(max_len, len(DisplayUtils._format_cell(value)))
        return max(min_width, min(max_width, max_len + 2))

    @staticmethod
    def _format_cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if not isfinite(value):
                return "∞" if value > 0 else "-∞"
            return f"{value:.6g}"
        return str(value)

    @staticmethod
    def deep_round(value: Any, digits: int = 6) -> Any:
        if isinstance(value, dict):
            return {k: DisplayUtils.deep_round(v, digits=digits) for k, v in value.items()}
        if isinstance(value, list):
            return [DisplayUtils.deep_round(v, digits=digits) for v in value]
        return DisplayUtils.normalize_float(value, digits=digits)

    @staticmethod
    def ensure_iterable_dict_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]
