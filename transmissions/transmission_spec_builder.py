from __future__ import annotations

"""Helpers to build transmission spec JSON payloads from GUI fields."""

import json
from pathlib import Path
from typing import Any, Mapping

try:
    from .gui_utils_trans import parse_bool, parse_csv_lines, parse_name_list, save_json
except Exception:
    from gui_utils_trans import parse_bool, parse_csv_lines, parse_name_list, save_json  # type: ignore


def build_spec_payload(
    *,
    name: str,
    input_member: str,
    output_member: str,
    strict_geometry: bool,
    members_text: str = "",
    speed_display_order_text: str = "",
    speed_display_labels_text: str = "",
    gearsets_text: str = "",
    clutches_text: str = "",
    brakes_text: str = "",
    sprags_text: str = "",
    permanent_ties_text: str = "",
    display_order_text: str = "",
    state_aliases_text: str = "",
    presets_text: str = "",
    notes: str = "",
    meta_text: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": str(name).strip() or "Generic Transmission",
        "input_member": str(input_member).strip(),
        "output_member": str(output_member).strip(),
        "strict_geometry": bool(strict_geometry),
        "members": parse_name_list(members_text),
        "speed_display_order": parse_name_list(speed_display_order_text),
        "speed_display_labels": _parse_key_value_rows(speed_display_labels_text, expected_cols=2),
        "gearsets": _parse_gearsets(gearsets_text),
        "clutches_brakes_flywheels": _parse_clutches(clutches_text),
        "brakes": _parse_brakes(brakes_text),
        "sprags": _parse_sprags(sprags_text),
        "permanent_ties": _parse_pairs(permanent_ties_text),
        "display_order": parse_name_list(display_order_text),
        "state_aliases": _parse_key_value_rows(state_aliases_text, expected_cols=2),
        "presets": _parse_json_object(presets_text),
        "notes": str(notes or "").strip(),
        "meta": _parse_json_object(meta_text),
    }
    return payload


def spec_payload_to_editors(payload: Mapping[str, Any]) -> dict[str, str]:
    return {
        "name": str(payload.get("name", "")),
        "input_member": str(payload.get("input_member", "")),
        "output_member": str(payload.get("output_member", "")),
        "strict_geometry": "true" if bool(payload.get("strict_geometry", False)) else "false",
        "members_text": "\n".join(str(x) for x in payload.get("members", []) if str(x).strip()),
        "speed_display_order_text": "\n".join(str(x) for x in payload.get("speed_display_order", []) if str(x).strip()),
        "speed_display_labels_text": _dump_key_value_rows(payload.get("speed_display_labels", {})),
        "gearsets_text": _dump_rows(payload.get("gearsets", []), ["name", "Ns", "Nr", "sun", "ring", "carrier"]),
        "clutches_text": _dump_rows(payload.get("clutches_brakes_flywheels", []), ["name", "a", "b"]),
        "brakes_text": _dump_rows(payload.get("brakes", []), ["name", "member"]),
        "sprags_text": _dump_rows(payload.get("sprags", []), ["name", "member", "hold_direction", "locked_when_engaged"]),
        "permanent_ties_text": _dump_pairs(payload.get("permanent_ties", [])),
        "display_order_text": "\n".join(str(x) for x in payload.get("display_order", []) if str(x).strip()),
        "state_aliases_text": _dump_key_value_rows(payload.get("state_aliases", {})),
        "presets_text": json.dumps(payload.get("presets", {}), indent=2, ensure_ascii=False),
        "notes": str(payload.get("notes", "")),
        "meta_text": json.dumps(payload.get("meta", {}), indent=2, ensure_ascii=False),
    }


def save_spec_payload(payload: Mapping[str, Any], path: str | Path) -> Path:
    p = Path(path)
    save_json(p, payload)
    return p


def _parse_gearsets(text: str) -> list[dict[str, Any]]:
    rows = parse_csv_lines(text)
    out: list[dict[str, Any]] = []
    if rows and rows[0] and rows[0][0].strip().lower() == "name":
        rows = rows[1:]
    for row in rows:
        if len(row) < 6:
            continue
        out.append(
            {
                "name": row[0],
                "Ns": int(row[1]),
                "Nr": int(row[2]),
                "sun": row[3],
                "ring": row[4],
                "carrier": row[5],
            }
        )
    return out


def _parse_clutches(text: str) -> list[dict[str, Any]]:
    rows = parse_csv_lines(text)
    out: list[dict[str, Any]] = []
    if rows and rows[0] and rows[0][0].strip().lower() == "name":
        rows = rows[1:]
    for row in rows:
        if len(row) < 3:
            continue
        out.append({"name": row[0], "a": row[1], "b": row[2]})
    return out


def _parse_brakes(text: str) -> list[dict[str, Any]]:
    rows = parse_csv_lines(text)
    out: list[dict[str, Any]] = []
    if rows and rows[0] and rows[0][0].strip().lower() == "name":
        rows = rows[1:]
    for row in rows:
        if len(row) < 2:
            continue
        out.append({"name": row[0], "member": row[1]})
    return out


def _parse_sprags(text: str) -> list[dict[str, Any]]:
    rows = parse_csv_lines(text)
    out: list[dict[str, Any]] = []
    if rows and rows[0] and rows[0][0].strip().lower() == "name":
        rows = rows[1:]
    for row in rows:
        if len(row) < 2:
            continue
        out.append(
            {
                "name": row[0],
                "member": row[1],
                "hold_direction": row[2] if len(row) > 2 and row[2].strip() else "counter_clockwise",
                "locked_when_engaged": parse_bool(row[3] if len(row) > 3 else True, True),
            }
        )
    return out


def _parse_pairs(text: str) -> list[list[str]]:
    rows = parse_csv_lines(text)
    out: list[list[str]] = []
    for row in rows:
        if len(row) < 2:
            continue
        out.append([row[0], row[1]])
    return out


def _parse_key_value_rows(text: str, *, expected_cols: int = 2) -> dict[str, str]:
    rows = parse_csv_lines(text)
    out: dict[str, str] = {}
    for row in rows:
        if len(row) < expected_cols:
            continue
        out[str(row[0]).strip()] = str(row[1]).strip()
    return out


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object.")
    return data


def _dump_rows(items: Any, keys: list[str]) -> str:
    if not isinstance(items, list):
        return ""
    lines = [", ".join(keys)]
    for item in items:
        if not isinstance(item, dict):
            continue
        vals = [str(item.get(k, "")) for k in keys]
        lines.append(", ".join(vals))
    return "\n".join(lines)


def _dump_pairs(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    lines: list[str] = []
    for item in items:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            lines.append(f"{item[0]}, {item[1]}")
    return "\n".join(lines)


def _dump_key_value_rows(items: Any) -> str:
    if not isinstance(items, dict):
        return ""
    return "\n".join(f"{k}, {v}" for k, v in items.items())
