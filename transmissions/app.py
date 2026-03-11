from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

try:
    from .apis import build_transmission
    from .io import load_json, save_json
    from .utils import TransmissionAppError, stable_json_dumps
except ImportError:
    from apis import build_transmission
    from utils import TransmissionAppError, stable_json_dumps

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


def render_text_report(payload: Mapping[str, Any], *, show_speeds: bool = False, ratios_only: bool = False) -> str:
    lines: list[str] = []
    lines.append(f"{payload['name']} — Universal Transmission CLI Summary")
    lines.append("-" * 140)
    lines.append(f"Input member : {payload['input_member']}")
    lines.append(f"Output member: {payload['output_member']}")
    lines.append(f"Input speed  : {payload['input_speed']}")
    lines.append(f"Geometry mode: {'strict' if payload.get('strict_geometry') else 'relaxed'}")

    if payload.get("topology") is not None:
        lines.append("Topology:")
        lines.append(stable_json_dumps(payload["topology"]))

    results = payload.get("results", {})
    lines.append("-" * 140)

    if ratios_only:
        lines.append(f"{'State':<14} {'Ratio':>14} {'Status':<24} {'Elems':<30}")
        lines.append("-" * 140)
        for state_name, res in results.items():
            ratio = res.get("ratio")
            ratio_txt = "-" if ratio is None else f"{float(ratio):.6f}"
            elems_txt = "+".join(res.get("engaged", []))
            lines.append(f"{state_name:<14} {ratio_txt:>14} {res.get('status',''):<24} {elems_txt:<30}")
        return "\n".join(lines)

    lines.append(f"{'State':<14} {'Ratio':>14} {'Status':<24} {'Elems':<30} {'Solver':<28}")
    lines.append("-" * 140)
    for state_name, res in results.items():
        ratio = res.get("ratio")
        ratio_txt = "-" if ratio is None else f"{float(ratio):.6f}"
        elems_txt = "+".join(res.get("engaged", []))
        lines.append(
            f"{state_name:<14} {ratio_txt:>14} {res.get('status',''):<24} {elems_txt:<30} {res.get('solver_path',''):<28}"
        )
        if res.get("message"):
            lines.append(f"  msg : {res['message']}")
        if show_speeds and res.get("speeds"):
            spd = ", ".join(f"{k}={float(v):.6f}" for k, v in res["speeds"].items())
            lines.append(f"  w   : {spd}")

    return "\n".join(lines)