from __future__ import annotations

"""Helpers to build shift schedule JSON payloads from user-friendly CSV input."""

from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .gui_utils_trans import parse_bool, parse_csv_lines, save_json
except Exception:
    from gui_utils_trans import parse_bool, parse_csv_lines, save_json  # type: ignore


_DEFAULT_NEUTRAL_ALIASES = {"n", "neutral"}


def parse_shift_schedule_csv(
    text: str,
    *,
    rich: bool = False,
    allow_header: bool = True,
) -> dict[str, Any]:
    """Parse a CSV-ish shift schedule editor.

    Legacy/simple examples
    ----------------------
    1st, A, B, C
    2nd, A, B, E
    Rev, A, B, D

    Rich examples
    -------------
    state, active_constraints, display_elements, manual_neutral, notes
    N, C3|B1, C3|B1, true, Neutral state
    1st, C3|B1|B2|F1|F2, C3|B1|B2|F1|F2, false,

    Separator rules
    ---------------
    - CSV separates columns
    - Within active/display columns, elements may be split by | ; + or whitespace
    """
    rows = parse_csv_lines(text)
    states: dict[str, Any] = {}

    if not rows:
        return {"states": {}, "display_order": [], "notes": "Built from GUI shift schedule builder."}

    start_idx = 0
    if allow_header and rows:
        header0 = rows[0][0].strip().lower()
        if header0 in {"state", "gear", "range"}:
            start_idx = 1
            rich = True

    display_order: list[str] = []

    for row in rows[start_idx:]:
        if not row:
            continue
        state = row[0].strip()
        if not state:
            continue

        if rich:
            active = _split_elements(row[1] if len(row) > 1 else "")
            display = _split_elements(row[2] if len(row) > 2 else "") or list(active)
            manual_neutral = parse_bool(row[3] if len(row) > 3 else False)
            notes = row[4].strip() if len(row) > 4 else ""
            states[state] = {
                "active_constraints": active,
                "display_elements": display,
                "manual_neutral": manual_neutral,
                "notes": notes,
            }
        else:
            elems = [x for x in row[1:] if str(x).strip()]
            states[state] = elems

        display_order.append(state)

    return {
        "states": states,
        "display_order": display_order,
        "notes": "Built from GUI shift schedule builder.",
    }


def _split_elements(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    for token in ("|", ";", "+"):
        raw = raw.replace(token, ",")
    out: list[str] = []
    for piece in raw.replace("\t", ",").split(","):
        s = piece.strip()
        if not s:
            continue
        if " " in s:
            out.extend([x for x in s.split() if x.strip()])
        else:
            out.append(s)
    return out


def infer_rich_mode_from_payload(payload: Mapping[str, Any]) -> bool:
    states = payload.get("states")
    if not isinstance(states, dict) or not states:
        return False
    first = next(iter(states.values()))
    return isinstance(first, dict)


def schedule_payload_to_csv(payload: Mapping[str, Any], *, rich: bool | None = None) -> str:
    states = payload.get("states")
    if not isinstance(states, dict):
        return ""

    rich_mode = infer_rich_mode_from_payload(payload) if rich is None else bool(rich)
    order = payload.get("display_order") if isinstance(payload.get("display_order"), list) else list(states.keys())

    lines: list[str] = []
    if rich_mode:
        lines.append("state, active_constraints, display_elements, manual_neutral, notes")
        for state in order:
            spec = states.get(state)
            if not isinstance(spec, dict):
                continue
            active = "|".join(str(x) for x in spec.get("active_constraints", []))
            display = "|".join(str(x) for x in spec.get("display_elements", []))
            manual_neutral = "true" if bool(spec.get("manual_neutral", False)) else "false"
            notes = str(spec.get("notes", ""))
            lines.append(f"{state}, {active}, {display}, {manual_neutral}, {notes}")
    else:
        for state in order:
            spec = states.get(state)
            if isinstance(spec, list):
                lines.append(", ".join([state] + [str(x) for x in spec]))
    return "\n".join(lines)


def save_shift_schedule_payload(payload: Mapping[str, Any], path: str | Path) -> Path:
    p = Path(path)
    save_json(p, payload)
    return p
