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
        }

        if req.show_topology:
            payload["topology"] = model.topology_summary()

        save_json(payload, req.output_json)
        return payload


def _format_ratio(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.6f}"
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

        clutches = topo.get("clutches", [])
        if clutches:
            lines.append("clutches:")
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


def _render_plain_report(
    payload: Mapping[str, Any],
    *,
    show_speeds: bool = False,
    ratios_only: bool = False,
) -> str:
    lines: list[str] = []

    lines.append(f"{payload['name']} — Transmission Summary")
    lines.append("-" * 100)
    lines.append(f"Input member : {payload['input_member']}")
    lines.append(f"Output member: {payload['output_member']}")
    lines.append(f"Input speed  : {payload['input_speed']}")
    lines.append(f"Geometry mode: {'strict' if payload.get('strict_geometry') else 'relaxed'}")

    topo_text = _topology_text(payload)
    if topo_text:
        lines.append("-" * 100)
        lines.append("Topology")
        lines.append("-" * 100)
        lines.append(topo_text)

    results = payload.get("results", {})
    lines.append("-" * 100)
    lines.append(f"{'State':<12} {'Ratio':>12} {'Status':<22} {'Elems':<24}")
    lines.append("-" * 100)

    for state_name, res in results.items():
        ratio_txt = _format_ratio(res.get("ratio"))
        status_txt = _status_label(res)
        elems_txt = _format_elems(res.get("engaged", []))
        lines.append(f"{state_name:<12} {ratio_txt:>12} {status_txt:<22} {elems_txt:<24}")

        if show_speeds:
            speeds = res.get("speeds", {})
            if speeds:
                speed_txt = ", ".join(f"{k}={float(v):.6f}" for k, v in speeds.items())
                lines.append(f"  speeds: {speed_txt}")

    return "\n".join(lines)


def _render_rich_report(
    payload: Mapping[str, Any],
    *,
    show_speeds: bool = False,
    ratios_only: bool = False,
) -> str:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except Exception:
        return _render_plain_report(payload, show_speeds=show_speeds, ratios_only=ratios_only)

    buffer = StringIO()
    console = Console(
        file=buffer,
        force_terminal=True,
        color_system="auto",
        width=100,
    )

    title = f"{payload['name']}"
    subtitle = (
        f"input={payload['input_member']}   "
        f"output={payload['output_member']}   "
        f"speed={payload['input_speed']}   "
        f"geometry={'strict' if payload.get('strict_geometry') else 'relaxed'}"
    )
    console.print(Panel(Text(subtitle), title=title, expand=False))

    topo_text = _topology_text(payload)
    if topo_text:
        console.print(Panel(topo_text, title="Topology", expand=False))

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

    if show_speeds:
        for state_name, res in results.items():
            speeds = res.get("speeds", {})
            if not speeds:
                continue

            speed_table = Table(show_header=True, header_style="bold")
            speed_table.add_column("Member", justify="left")
            speed_table.add_column("Speed", justify="right")

            for member, value in speeds.items():
                speed_table.add_row(str(member), f"{float(value):.6f}")

            console.print(Panel(speed_table, title=f"{state_name} Speeds", expand=False))

    return buffer.getvalue().rstrip()


def render_text_report(
    payload: Mapping[str, Any],
    *,
    show_speeds: bool = False,
    ratios_only: bool = False,
) -> str:
    return _render_rich_report(payload, show_speeds=show_speeds, ratios_only=ratios_only)