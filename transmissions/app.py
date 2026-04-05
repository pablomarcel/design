from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Any, Mapping

try:
    from .apis import build_transmission
    from .io import load_json, save_json
    from .utils import TransmissionAppError
except ImportError:
    from apis import build_transmission
    from utils import TransmissionAppError

    try:
        from module_loader import load_local_module
    except ImportError:
        from .module_loader import load_local_module  # type: ignore

    _io_mod = load_local_module("io_local", "io.py")
    load_json = _io_mod.load_json
    save_json = _io_mod.save_json


@dataclass
class RunRequest:
    spec_path: str | None = None
    schedule_path: str | None = None
    preset: str | None = None
    state: str | None = None
    input_speed: float | None = None
    show_speeds: bool = False
    ratios_only: bool = False
    show_topology: bool = False
    as_json: bool = False
    output_json: str | None = None
    overrides: dict[str, Any] | None = None


class TransmissionApplication:
    def run(self, req: RunRequest) -> dict[str, Any]:
        spec_data = load_json(req.spec_path)
        schedule_data = load_json(req.schedule_path)

        if not spec_data:
            raise TransmissionAppError("Transmission spec JSON is required. Use --spec.")
        if not schedule_data:
            raise TransmissionAppError("Shift schedule JSON is required. Use --schedule.")

        model = build_transmission(
            spec_data=spec_data,
            schedule_data=schedule_data,
            preset=req.preset,
            overrides=req.overrides,
        )

        input_speed = float(req.input_speed if req.input_speed is not None else 1.0)
        state = req.state or "all"

        results_obj = model.solve(state=state, input_speed=input_speed)
        results = {
            name: {
                "state": res.state,
                "engaged": list(res.engaged),
                "ok": res.ok,
                "ratio": res.ratio,
                "speeds": dict(res.speeds),
                "notes": res.notes,
                "solver_path": res.solver_path,
                "status": res.status,
                "message": res.message,
            }
            for name, res in results_obj.items()
        }

        payload: dict[str, Any] = {
            "ok": True,
            "name": model.spec.name,
            "input_member": model.spec.input_member,
            "output_member": model.spec.output_member,
            "input_speed": input_speed,
            "requested_state": state,
            "strict_geometry": model.spec.strict_geometry,
            "available_states": model.available_states(),
            "results": results,
            "member_order": list(model.spec.members) if model.spec.members else [],
            "speed_display_order": list(model.spec.speed_display_order) if model.spec.speed_display_order else [],
            "speed_display_labels": dict(model.spec.speed_display_labels) if model.spec.speed_display_labels else {},
            "gearsets": [
                {
                    "name": g.name,
                    "Ns": g.Ns,
                    "Nr": g.Nr,
                    "sun": g.sun,
                    "ring": g.ring,
                    "carrier": g.carrier,
                }
                for g in model.spec.gearsets
            ],
            "preset": req.preset,
            "schedule_notes": getattr(model.schedule, "notes", ""),
            "spec_notes": model.spec.notes,
        }

        if req.show_topology:
            payload["topology"] = model.topology_summary()

        save_json(payload, req.output_json)
        return payload


def _format_ratio(value: Any, *, ndigits: int = 6) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return str(value)


def _format_speed(value: Any, *, ndigits: int = 3) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{ndigits}f}"
    except (TypeError, ValueError):
        return str(value)


def _format_elems(elems: Any) -> str:
    if not elems:
        return "-"
    return "+".join(str(x) for x in elems)


def _status_label(res: Mapping[str, Any]) -> str:
    status = str(res.get("status", "") or "").strip()
    ok = bool(res.get("ok", False))
    if status:
        return status
    return "ok" if ok else "error"


def _topology_text(payload: Mapping[str, Any]) -> str:
    topo = payload.get("topology")
    if topo is None:
        return ""

    if isinstance(topo, str):
        return topo

    if isinstance(topo, dict):
        lines: list[str] = []
        lines.append(f"name: {topo.get('name', '-')}")
        lines.append(f"input_member: {topo.get('input_member', '-')}")
        lines.append(f"output_member: {topo.get('output_member', '-')}")
        lines.append(f"strict_geometry: {topo.get('strict_geometry', False)}")

        gearsets = topo.get("gearsets", [])
        if gearsets:
            lines.append("gearsets:")
            for g in gearsets:
                lines.append(
                    "  "
                    f"{g.get('name', '?')}: "
                    f"Ns={g.get('Ns')}, Nr={g.get('Nr')}, "
                    f"sun={g.get('sun')}, ring={g.get('ring')}, carrier={g.get('carrier')}"
                )

        clutches = topo.get("clutches_brakes_flywheels", [])
        if clutches:
            lines.append("clutches_brakes_flywheels:")
            for c in clutches:
                lines.append(f"  {c.get('name', '?')}: {c.get('a')} <-> {c.get('b')}")

        brakes = topo.get("brakes", [])
        if brakes:
            lines.append("brakes:")
            for b in brakes:
                lines.append(f"  {b.get('name', '?')}: {b.get('member')} -> ground")

        ties = topo.get("permanent_ties", [])
        if ties:
            lines.append("permanent_ties:")
            for pair in ties:
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    lines.append(f"  {pair[0]} = {pair[1]}")

        return "\n".join(lines)

    return str(topo)


def _tooth_counts_text(payload: Mapping[str, Any]) -> str:
    gearsets = payload.get("gearsets", [])
    if not isinstance(gearsets, list) or not gearsets:
        return ""

    parts: list[str] = []
    for g in gearsets:
        if not isinstance(g, dict):
            continue
        parts.append(f"{g.get('name', '?')}(Ns={g.get('Ns')}, Nr={g.get('Nr')})")
    return ", ".join(parts)


def _speed_column_order(payload: Mapping[str, Any]) -> list[str]:
    explicit = payload.get("speed_display_order", [])
    member_order = payload.get("member_order", [])
    results = payload.get("results", {})

    ordered: list[str] = []
    seen: set[str] = set()

    if isinstance(explicit, list) and explicit:
        for x in explicit:
            key = str(x)
            if key not in seen:
                ordered.append(key)
                seen.add(key)
    elif isinstance(member_order, list) and member_order:
        for x in member_order:
            key = str(x)
            if key not in seen:
                ordered.append(key)
                seen.add(key)

    if isinstance(results, dict):
        for _state, res in results.items():
            speeds = res.get("speeds", {})
            if not isinstance(speeds, dict):
                continue
            for key in speeds.keys():
                skey = str(key)
                if skey not in seen:
                    ordered.append(skey)
                    seen.add(skey)

    return ordered


def _speed_col_label(payload: Mapping[str, Any], key: str) -> str:
    labels = payload.get("speed_display_labels", {})
    if isinstance(labels, dict) and key in labels:
        return str(labels[key])
    return key


def _render_plain_compact(
    payload: Mapping[str, Any],
    *,
    ratios_only: bool = False,
) -> str:
    lines: list[str] = []
    lines.append(f"{payload['name']} — Transmission Summary")
    lines.append("-" * 116)

    tooth_txt = _tooth_counts_text(payload)
    if tooth_txt:
        lines.append(f"Tooth counts : {tooth_txt}")
    lines.append(f"Geometry mode: {'strict' if payload.get('strict_geometry') else 'relaxed'}")
    lines.append(f"Input member : {payload['input_member']}")
    lines.append(f"Output member: {payload['output_member']}")
    lines.append(f"Input speed  : {payload['input_speed']}")

    results = payload.get("results", {})
    lines.append("-" * 116)
    lines.append(f"{'State':<12} {'Ratio':>12} {'Status':<22} {'Elems':<24}")
    lines.append("-" * 116)

    for state_name, res in results.items():
        lines.append(
            f"{state_name:<12} "
            f"{_format_ratio(res.get('ratio')):>12} "
            f"{_status_label(res):<22} "
            f"{_format_elems(res.get('engaged', [])):<24}"
        )

    return "\n".join(lines)


def _render_plain_wide(payload: Mapping[str, Any]) -> str:
    member_cols = _speed_column_order(payload)
    results = payload.get("results", {})

    lines: list[str] = []
    lines.append(f"{payload['name']} — Transmission Kinematic Summary")
    lines.append("-" * 180)

    tooth_txt = _tooth_counts_text(payload)
    if tooth_txt:
        lines.append(f"Tooth counts: {tooth_txt}")
    lines.append(f"Geometry mode: {'strict' if payload.get('strict_geometry') else 'relaxed'}")
    lines.append(f"Input member: {payload['input_member']}")
    lines.append(f"Output member: {payload['output_member']}")
    lines.append(f"Input speed: {payload['input_speed']}")
    lines.append("-" * 180)

    header = (
        f"{'State':<8} "
        f"{'Elems':<18} "
        f"{'Ratio':>10} "
    )
    for col in member_cols:
        header += f" {_speed_col_label(payload, col):>10}"
    lines.append(header)
    lines.append("-" * 180)

    for state_name, res in results.items():
        row = (
            f"{state_name:<8} "
            f"{_format_elems(res.get('engaged', [])):<18} "
            f"{_format_ratio(res.get('ratio'), ndigits=3):>10}"
        )
        speeds = res.get("speeds", {})
        if not isinstance(speeds, dict):
            speeds = {}
        for col in member_cols:
            row += f" {_format_speed(speeds.get(col), ndigits=3):>10}"
        lines.append(row)

    return "\n".join(lines)


def _render_plain_report(
    payload: Mapping[str, Any],
    *,
    show_speeds: bool = False,
    ratios_only: bool = False,
) -> str:
    topo_text = _topology_text(payload)

    if show_speeds:
        base = _render_plain_wide(payload)
    else:
        base = _render_plain_compact(payload, ratios_only=ratios_only)

    if topo_text:
        return (
            base
            + "\n"
            + "-" * 116
            + "\nTopology\n"
            + "-" * 116
            + "\n"
            + topo_text
        )

    return base


def _render_rich_compact(console, payload: Mapping[str, Any]) -> None:
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    title = f"{payload['name']}"
    subtitle = (
        f"input={payload['input_member']}   "
        f"output={payload['output_member']}   "
        f"speed={payload['input_speed']}   "
        f"geometry={'strict' if payload.get('strict_geometry') else 'relaxed'}"
    )
    console.print(Panel(Text(subtitle), title=title, expand=False))

    tooth_txt = _tooth_counts_text(payload)
    if tooth_txt:
        console.print(f"Tooth counts: {tooth_txt}")

    table = Table(show_header=True, header_style="bold")
    table.add_column("State", justify="left")
    table.add_column("Ratio", justify="right")
    table.add_column("Status", justify="left")
    table.add_column("Elems", justify="left")

    results = payload.get("results", {})
    for state_name, res in results.items():
        table.add_row(
            str(state_name),
            _format_ratio(res.get("ratio")),
            _status_label(res),
            _format_elems(res.get("engaged", [])),
        )

    console.print(table)


def _render_rich_wide(console, payload: Mapping[str, Any]) -> None:
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    title = f"{payload['name']}"
    subtitle = (
        f"input={payload['input_member']}   "
        f"output={payload['output_member']}   "
        f"speed={payload['input_speed']}   "
        f"geometry={'strict' if payload.get('strict_geometry') else 'relaxed'}"
    )
    console.print(Panel(Text(subtitle), title=title, expand=False))

    tooth_txt = _tooth_counts_text(payload)
    if tooth_txt:
        console.print(f"Tooth counts: {tooth_txt}")

    member_cols = _speed_column_order(payload)

    table = Table(show_header=True, header_style="bold", expand=False)
    table.add_column("State", justify="left", no_wrap=True)
    table.add_column("Elems", justify="left", no_wrap=True)
    table.add_column("Ratio", justify="right", no_wrap=True)

    for col in member_cols:
        table.add_column(_speed_col_label(payload, col), justify="right", no_wrap=True)

    results = payload.get("results", {})
    for state_name, res in results.items():
        row = [
            str(state_name),
            _format_elems(res.get("engaged", [])),
            _format_ratio(res.get("ratio"), ndigits=3),
        ]

        speeds = res.get("speeds", {})
        if not isinstance(speeds, dict):
            speeds = {}

        for col in member_cols:
            row.append(_format_speed(speeds.get(col), ndigits=3))

        table.add_row(*row)

    console.print(table)


def _render_rich_report(
    payload: Mapping[str, Any],
    *,
    show_speeds: bool = False,
    ratios_only: bool = False,
) -> str:
    try:
        from rich.console import Console
        from rich.panel import Panel
    except Exception:
        return _render_plain_report(payload, show_speeds=show_speeds, ratios_only=ratios_only)

    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=True,
        color_system="auto",
        width=220,
    )

    if show_speeds:
        _render_rich_wide(console, payload)
    else:
        _render_rich_compact(console, payload)

    topo_text = _topology_text(payload)
    if topo_text:
        console.print(Panel(topo_text, title="Topology", expand=False))

    return buffer.getvalue().rstrip()


def render_text_report(
    payload: Mapping[str, Any],
    *,
    show_speeds: bool = False,
    ratios_only: bool = False,
) -> str:
    return _render_rich_report(payload, show_speeds=show_speeds, ratios_only=ratios_only)