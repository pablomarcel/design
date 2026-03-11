from __future__ import annotations

import json
from typing import Any, Iterable, Mapping


class TransmissionAppError(RuntimeError):
    pass


def maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stable_json_dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=False, ensure_ascii=False)


def ensure_dict(value: Any, *, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TransmissionAppError(f"{context} must be a JSON object/dict.")
    return dict(value)


def ensure_list(value: Any, *, context: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TransmissionAppError(f"{context} must be a JSON array/list.")
    return list(value)


def ensure_str(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransmissionAppError(f"{context} must be a non-empty string.")
    return value.strip()


def coerce_int(value: Any, *, context: str) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        raise TransmissionAppError(f"{context} must be an integer.") from None
    return out


def parse_key_value_overrides(items: list[str] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise TransmissionAppError(f"Invalid override '{item}'. Expected KEY=VALUE.")
        key, raw = item.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if not key:
            raise TransmissionAppError(f"Invalid override '{item}'. Empty key.")
        out[key] = _parse_scalar(raw)
    return out


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    lower = text.lower()

    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"null", "none"}:
        return None

    try:
        if any(ch in text for ch in (".", "e", "E")):
            val = float(text)
            if val.is_integer():
                return int(val)
            return val
        return int(text)
    except ValueError:
        pass

    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    return text


def normalize_state_name(name: str, aliases: Mapping[str, str] | None = None) -> str:
    raw = ensure_str(name, context="state")
    if raw.lower() == "all":
        return "all"

    alias_map = {str(k).strip().lower(): str(v).strip() for k, v in (aliases or {}).items()}
    mapped = alias_map.get(raw.lower())
    return mapped if mapped else raw


def dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out