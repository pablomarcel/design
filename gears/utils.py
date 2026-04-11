from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

try:
    from rich.console import Console
    from rich.table import Table
except Exception:  # pragma: no cover
    Console = None
    Table = None


def project_root() -> Path:
    return Path(__file__).resolve().parent


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def to_float(value: Any) -> float:
    return float(value)


def vec_add(a: Sequence[float], b: Sequence[float]) -> List[float]:
    return [float(x) + float(y) for x, y in zip(a, b)]


def vec_sub(a: Sequence[float], b: Sequence[float]) -> List[float]:
    return [float(x) - float(y) for x, y in zip(a, b)]


def vec_scale(s: float, v: Sequence[float]) -> List[float]:
    return [float(s) * float(x) for x in v]


def vec_dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def vec_cross(a: Sequence[float], b: Sequence[float]) -> List[float]:
    ax, ay, az = a
    bx, by, bz = b
    return [
        ay * bz - az * by,
        az * bx - ax * bz,
        ax * by - ay * bx,
    ]


def vec_norm(v: Sequence[float]) -> float:
    return math.sqrt(sum(float(x) ** 2 for x in v))


def vec_magnitude(v: Sequence[float]) -> float:
    return vec_norm(v)


def vec_unit(v: Sequence[float]) -> List[float]:
    n = vec_norm(v)
    if n == 0:
        raise ValueError(f"Cannot normalize zero vector: {v}")
    return [float(x) / n for x in v]


def vec_mag_dict(components: Dict[str, float]) -> Dict[str, float]:
    x = abs(float(components.get("x", 0.0)))
    y = abs(float(components.get("y", 0.0)))
    z = abs(float(components.get("z", 0.0)))
    return {
        "x": x,
        "y": y,
        "z": z,
        "resultant": math.sqrt(x * x + y * y + z * z),
    }


def round_floats(obj: Any, digits: int = 6) -> Any:
    if isinstance(obj, float):
        return round(obj, digits)
    if isinstance(obj, dict):
        return {k: round_floats(v, digits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, digits) for v in obj]
    return obj


class ReportBuilder:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or (Console() if Console else None)

    def print_title(self, title: str, subtitle: str | None = None) -> None:
        if not self.console:
            print(title)
            if subtitle:
                print(subtitle)
            return
        self.console.rule(f"[bold cyan]{title}[/bold cyan]")
        if subtitle:
            self.console.print(subtitle)

    def print_kv_table(self, title: str, mapping: Dict[str, Any]) -> None:
        if not mapping:
            return
        if not self.console or not Table:
            print(f"\n{title}")
            for k, v in mapping.items():
                print(f"  {k}: {v}")
            return
        table = Table(title=title, show_header=True, header_style="bold white", expand=False)
        table.add_column("Item", width=40)
        table.add_column("Value", width=30)
        for k, v in mapping.items():
            table.add_row(str(k), self._format_value(v))
        self.console.print(table)

    def print_mapping_sections(self, title: str, mapping: Dict[str, Any]) -> None:
        if not mapping:
            return
        flat_items: Dict[str, Any] = {}
        nested_sections: List[tuple[str, Dict[str, Any]]] = []
        for key, value in mapping.items():
            if isinstance(value, dict):
                nested_sections.append((key, value))
            else:
                flat_items[key] = value
        if flat_items:
            self.print_kv_table(title, flat_items)
        for section_name, section_map in nested_sections:
            self.print_kv_table(f"{title} · {section_name}", section_map)

    def print_rows(self, title: str, rows: Iterable[Dict[str, Any]], columns: Sequence[str]) -> None:
        rows = list(rows)
        if not rows:
            return
        if not self.console or not Table:
            print(f"\n{title}")
            for row in rows:
                print({c: row.get(c) for c in columns})
            return
        table = Table(title=title, show_header=True, header_style="bold white")
        for col in columns:
            table.add_column(col, width=18, overflow="fold")
        for row in rows:
            table.add_row(*(self._format_value(row.get(c, "")) for c in columns))
        self.console.print(table)

    def print_list(self, title: str, items: Sequence[Any]) -> None:
        if not items:
            return
        if not self.console:
            print(f"\n{title}")
            for item in items:
                print(f"  - {item}")
            return
        self.console.print(f"\n[bold]{title}[/bold]")
        for item in items:
            self.console.print(f"  • {item}")

    def _format_value(self, value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.6g}"
        if isinstance(value, (list, tuple)):
            return json.dumps(round_floats(list(value), 6))
        if isinstance(value, dict):
            return json.dumps(round_floats(value, 6))
        return str(value)