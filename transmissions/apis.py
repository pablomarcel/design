from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

try:
    from .model import GenericTransmission, ShiftSchedule, TransmissionSpec
    from .utils import TransmissionAppError, ensure_dict
except ImportError:
    from model import GenericTransmission, ShiftSchedule, TransmissionSpec
    from utils import TransmissionAppError, ensure_dict


def apply_preset_to_spec(spec_data: Mapping[str, Any], preset_name: str | None) -> dict[str, Any]:
    data = deepcopy(dict(spec_data))
    if not preset_name:
        return data

    presets = ensure_dict(data.get("presets"), context="spec.presets")
    if preset_name not in presets:
        valid = ", ".join(sorted(presets)) or "(none)"
        raise TransmissionAppError(f"Unknown preset '{preset_name}'. Valid presets: {valid}")

    preset = ensure_dict(presets[preset_name], context=f"spec.presets.{preset_name}")

    if "strict_geometry" in preset:
        data["strict_geometry"] = bool(preset["strict_geometry"])

    if "gearsets" in preset:
        patch_root = ensure_dict(preset["gearsets"], context=f"spec.presets.{preset_name}.gearsets")
        by_name = {str(g.get("name")): g for g in data.get("gearsets", []) if isinstance(g, dict)}

        for gname, patch_any in patch_root.items():
            patch = ensure_dict(patch_any, context=f"spec.presets.{preset_name}.gearsets.{gname}")
            if gname not in by_name:
                raise TransmissionAppError(f"Preset '{preset_name}' references unknown gearset '{gname}'.")
            if "Ns" in patch:
                by_name[gname]["Ns"] = int(patch["Ns"])
            if "Nr" in patch:
                by_name[gname]["Nr"] = int(patch["Nr"])

    return data


def apply_cli_overrides_to_spec(spec_data: Mapping[str, Any], overrides: Mapping[str, Any] | None) -> dict[str, Any]:
    data = deepcopy(dict(spec_data))
    if not overrides:
        return data

    gearsets = data.get("gearsets", [])
    by_name = {str(g.get("name")): g for g in gearsets if isinstance(g, dict)}

    for raw_key, raw_value in dict(overrides).items():
        key = str(raw_key).strip()
        parts = key.split(".")

        if len(parts) == 2 and parts[1] in {"Ns", "Nr"}:
            gname, field = parts
            if gname not in by_name:
                raise TransmissionAppError(f"Override references unknown gearset '{gname}'.")
            by_name[gname][field] = int(raw_value)
            continue

        if len(parts) == 3 and parts[0] == "gearsets" and parts[2] in {"Ns", "Nr"}:
            _, gname, field = parts
            if gname not in by_name:
                raise TransmissionAppError(f"Override references unknown gearset '{gname}'.")
            by_name[gname][field] = int(raw_value)
            continue

        if key in {"input_member", "output_member", "name"}:
            data[key] = raw_value
            continue

        if key == "strict_geometry":
            data[key] = bool(raw_value)
            continue

        raise TransmissionAppError(
            f"Unsupported override '{key}'. "
            f"Use P1.Ns=..., P1.Nr=..., gearsets.P1.Ns=..., gearsets.P1.Nr=..., "
            f"input_member=..., output_member=..., or strict_geometry=true/false."
        )

    return data


def build_transmission(
    *,
    spec_data: Mapping[str, Any],
    schedule_data: Mapping[str, Any],
    preset: str | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> GenericTransmission:
    patched = apply_preset_to_spec(spec_data, preset)
    patched = apply_cli_overrides_to_spec(patched, overrides)

    spec = TransmissionSpec.from_dict(patched)
    schedule = ShiftSchedule.from_dict(schedule_data, aliases=spec.state_aliases)
    return GenericTransmission(spec=spec, schedule=schedule)


def list_presets(spec_data: Mapping[str, Any]) -> list[str]:
    presets = ensure_dict(dict(spec_data).get("presets"), context="spec.presets")
    return sorted(presets.keys())