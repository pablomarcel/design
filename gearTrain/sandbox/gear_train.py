#!/usr/bin/env python3
"""
gearbox_sandbox.py

Sandbox runner for the *python-gearbox* library (efirvida/python-gearbox).

What’s going on with your install
---------------------------------
You installed: python-gearbox==0.1.2a0.dev0 (PyPI)

That release has TWO naming issues:
1) The subpackage is misspelled:
      gearbox.transmition   (not gearbox.transmission)

2) The “Transmission” class is also misspelled:
      Transmition           (not Transmission)

So imports like this will fail on that build:
    from gearbox.transmission.gears import Transmission

This script supports BOTH layouts:
- Newer / repo layouts:
    gearbox.transmission.gears  with class Transmission
- PyPI 0.1.2a0.dev0 layout:
    gearbox.transmition.gears   with class Transmition

Run
---
Diagnostics only:
    python gearbox_sandbox.py --probe

Compute ISO + AGMA pitting/bending:
    python gearbox_sandbox.py --z1 24 --z2 48 --module 3 --face 20 --torque 50 --rpm 1500
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from typing import Any, Callable


# Order matters: try “correct” spelling first, then the PyPI misspelling.
_IMPORT_CANDIDATES: list[tuple[str, str]] = [
    ("gearbox.transmission.gears", "transmission"),
    ("gearbox.transmition.gears", "transmition"),  # PyPI misspelling
]


def power_kw_from_torque_rpm(torque_nm: float, rpm: float) -> float:
    """Mechanical power (kW) from torque (N·m) and speed (rpm)."""
    omega = 2.0 * math.pi * rpm / 60.0  # rad/s
    return (torque_nm * omega) / 1000.0


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)


def _get_any(obj: Any, names: list[str]) -> Any:
    """Return the first attribute that exists from `names`, else raise AttributeError."""
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    raise AttributeError(f"None of these attributes exist: {names}")


def probe_gearbox_package() -> dict[str, Any]:
    """Return debug info about which `gearbox` package is being imported and which layouts exist."""
    info: dict[str, Any] = {"ok": False}

    try:
        import gearbox  # type: ignore
    except Exception as e:
        info["error"] = f"import gearbox failed: {e!r}"
        return info

    info["ok"] = True
    info["gearbox_file"] = getattr(gearbox, "__file__", None)
    info["gearbox_version_attr"] = getattr(gearbox, "__version__", None)

    # List immediate submodules (best-effort)
    try:
        import pkgutil

        if hasattr(gearbox, "__path__"):
            info["submodules"] = sorted({m.name for m in pkgutil.iter_modules(gearbox.__path__)})
        else:
            info["submodules"] = []
    except Exception as e:
        info["submodules_error"] = repr(e)

    # Check both spellings for the "gears" module and the Transmission class name variants.
    for mod, label in _IMPORT_CANDIDATES:
        key_mod = f"has_{label}_gears_mod"
        key_cls = f"{key_mod}_has_transmission_class"
        try:
            m = importlib.import_module(mod)
            info[key_mod] = True
            # Transmission class can be Transmission or Transmition (PyPI typo).
            info[key_cls] = any(hasattr(m, n) for n in ("Transmission", "Transmition"))
            if not info[key_cls]:
                info[f"{key_cls}_available"] = sorted([n for n in dir(m) if "ransmi" in n.lower()])
        except Exception as e:
            info[key_mod] = False
            info[f"{key_mod}_error"] = repr(e)

    return info


def import_python_gearbox_primitives():
    """
    Import primitives from python-gearbox, supporting both spelling variants.

    Returns:
        Lubricant, Material, Tool, Gear, TransmissionClass, subpkg_label
    """
    last_err: Exception | None = None

    for mod, label in _IMPORT_CANDIDATES:
        try:
            m = importlib.import_module(mod)

            Lubricant = _get_any(m, ["Lubricant"])
            Material = _get_any(m, ["Material"])
            Tool = _get_any(m, ["Tool"])
            Gear = _get_any(m, ["Gear"])

            # IMPORTANT: class name differs between layouts
            TransmissionClass = _get_any(m, ["Transmission", "Transmition"])

            return Lubricant, Material, Tool, Gear, TransmissionClass, label
        except Exception as e:
            last_err = e

    probe = probe_gearbox_package()
    raise RuntimeError(
        "Could not import python-gearbox primitives from either:\n"
        "  gearbox.transmission.gears  OR  gearbox.transmition.gears\n\n"
        f"Last import error: {last_err!r}\n\n"
        "DIAGNOSTIC (which `gearbox` did Python import?):\n"
        f"{_json(probe)}\n\n"
        "Fix:\n"
        "  - PyPI python-gearbox==0.1.2a0.dev0 uses 'transmition' AND class 'Transmition'.\n"
        "  - GitHub/newer layouts typically use 'transmission' AND class 'Transmission'.\n"
    ) from last_err


def build_transmission(
    *,
    z1: float,
    z2: float,
    module_mm: float,
    face_width_mm: float,
    pressure_angle_deg: float,
    helix_angle_deg: float,
    torque_nm: float,
    rpm_in: float,
    life_hours: float,
    ka: float,
    backlash_total_mm: float,
    x1: float,
    x2: float,
) -> Any:
    """Create a python-gearbox Transmission object with demo-like defaults."""
    Lubricant, Material, Tool, Gear, TransmissionClass, label = import_python_gearbox_primitives()

    lubricant = Lubricant(name="Generic ISO VG", v40=160)

    # Demo-ish material allowables (replace with your real allowables/material)
    material = Material(
        name="Generic steel",
        classification="NV(nitrocar)",
        sh_limit=1500.0,
        sf_limit=460.0,
        e=206000.0,         # MPa
        poisson=0.30,
        density=7.83e-6,    # kg/mm^3 (~7830 kg/m^3)
        brinell=286.6667,
    )

    tool = Tool(
        ha_p=1.0,
        hf_p=1.25,
        rho_fp=0.38,
        x=0.0,
        rho_ao=0.0,
        delta_ao=0.0,
        nc=10.0,
    )

    half_backlash = backlash_total_mm / 2.0
    p_kw = power_kw_from_torque_rpm(torque_nm, rpm_in)

    pinion = Gear(
        profile=tool,
        material=material,
        z=float(z1),
        beta=float(helix_angle_deg),
        alpha=float(pressure_angle_deg),
        m=float(module_mm),
        x=float(x1),
        b=float(face_width_mm),
        bs=float(face_width_mm),
        sr=0.0,
        rz=3.67,
        precision_grade=6.0,
        shaft_diameter=max(10.0, 0.5 * module_mm * z1),
        schema=3.0,
        l=60.0,
        s=15.0,
        backlash=+half_backlash,
        gear_crown=1,
        helix_modification=1,
        favorable_contact=True,
        gear_condition=1,
    )

    gear = Gear(
        profile=tool,
        material=material,
        z=float(z2),
        beta=float(helix_angle_deg),
        alpha=float(pressure_angle_deg),
        m=float(module_mm),
        x=float(x2),
        b=float(face_width_mm),
        bs=float(face_width_mm),
        sr=0.0,
        rz=3.67,
        precision_grade=6.0,
        shaft_diameter=max(10.0, 0.5 * module_mm * z2),
        schema=3.0,
        l=60.0,
        s=35.0,
        backlash=-half_backlash,
        gear_crown=1,
        helix_modification=1,
        favorable_contact=True,
        gear_condition=1,
    )

    # Signature matches the library's demo patterns.
    t = TransmissionClass(
        gears=[pinion, gear],
        lubricant=lubricant,
        rpm_in=float(rpm_in),
        p=float(p_kw),
        l=float(life_hours),
        gear_box_type=2,
        ka=float(ka),
        sh_min=1,
        sf_min=1,
    )

    # Breadcrumb: which layout did we use?
    setattr(t, "_python_gearbox_subpkg", label)
    setattr(t, "_python_gearbox_transmission_class", getattr(TransmissionClass, "__name__", None))
    return t


def calculate_all(transmission: Any) -> dict[str, Any]:
    # These imports are stable in your installed package (your probe listed "standards").
    from gearbox.standards.iso import Pitting as ISOPitting  # type: ignore
    from gearbox.standards.iso import Bending as ISOBending  # type: ignore
    from gearbox.standards.agma import Pitting as AGMAPitting  # type: ignore
    from gearbox.standards.agma import Bending as AGMABending  # type: ignore

    return {
        "iso_pitting": ISOPitting(transmission=transmission).calculate(),
        "iso_bending": ISOBending(transmission=transmission).calculate(),
        "agma_pitting": AGMAPitting(transmission=transmission).calculate(),
        "agma_bending": AGMABending(transmission=transmission).calculate(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Sandbox runner for python-gearbox (ISO/AGMA stresses).")
    ap.add_argument("--probe", action="store_true", help="Only print diagnostics about imported `gearbox` package.")
    ap.add_argument("--z1", type=float, default=22.0, help="Pinion teeth")
    ap.add_argument("--z2", type=float, default=40.0, help="Gear teeth")
    ap.add_argument("--module", type=float, default=2.5, help="Module (mm)")
    ap.add_argument("--face", type=float, default=34.0, help="Face width b (mm)")
    ap.add_argument("--phi", type=float, default=20.0, help="Pressure angle alpha (deg)")
    ap.add_argument("--beta", type=float, default=0.0, help="Helix angle beta (deg)")
    ap.add_argument("--torque", type=float, default=50.0, help="Input torque (N·m)")
    ap.add_argument("--rpm", type=float, default=1450.0, help="Input speed (rpm)")
    ap.add_argument("--life", type=float, default=10000.0, help="Life (hours)")
    ap.add_argument("--ka", type=float, default=1.3, help="Application factor Ka")
    ap.add_argument("--backlash", type=float, default=0.034, help="Total backlash (mm)")
    ap.add_argument("--x1", type=float, default=0.525, help="Profile shift x1 (pinion)")
    ap.add_argument("--x2", type=float, default=-0.275, help="Profile shift x2 (gear)")

    args = ap.parse_args()

    if args.probe:
        print(_json(probe_gearbox_package()))
        sys.exit(0)

    transmission = build_transmission(
        z1=args.z1,
        z2=args.z2,
        module_mm=args.module,
        face_width_mm=args.face,
        pressure_angle_deg=args.phi,
        helix_angle_deg=args.beta,
        torque_nm=args.torque,
        rpm_in=args.rpm,
        life_hours=args.life,
        ka=args.ka,
        backlash_total_mm=args.backlash,
        x1=args.x1,
        x2=args.x2,
    )

    results = calculate_all(transmission)
    meta = {
        "inputs": vars(args),
        "power_kw": power_kw_from_torque_rpm(args.torque, args.rpm),
        "gearbox_subpkg_used": getattr(transmission, "_python_gearbox_subpkg", None),
        "gearbox_transmission_class": getattr(transmission, "_python_gearbox_transmission_class", None),
    }
    print(_json({"meta": meta, "results": results}))


if __name__ == "__main__":
    main()
