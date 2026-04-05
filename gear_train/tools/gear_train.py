#!/usr/bin/env python3
"""
gearbox_sandbox.py

Sandbox runner for the *python-gearbox* library (efirvida/python-gearbox).

Why you may be seeing: "ModuleNotFoundError: gearbox.transmission"
-------------------------------------------------------------------
There is ALSO a different, unrelated PyPI project named **gearbox** (TurboGears CLI tool).
If that project is installed in your environment, it can shadow/overwrite the `gearbox`
package name that python-gearbox expects to provide.

Quick sanity check:
    python -c "import gearbox; print(gearbox.__file__)"

If that path looks like a TurboGears install, you’re importing the wrong `gearbox`.

This script helps you diagnose that and (if correct python-gearbox is installed)
runs ISO + AGMA pitting/bending calculations.

References (upstream)
---------------------
The upstream demo uses:
    from gearbox.transmission.gear_train import *
and builds a Transmission then calls ISO/AGMA calculate(). (See demo/demo.py in repo.)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any


def power_kw_from_torque_rpm(torque_nm: float, rpm: float) -> float:
    omega = 2.0 * math.pi * rpm / 60.0  # rad/s
    return (torque_nm * omega) / 1000.0


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)


def probe_gearbox_package() -> dict[str, Any]:
    """Return debug info about which `gearbox` package is being imported."""
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

    # Check the critical import
    try:
        from gearbox.transmission.gears import Transmission  # noqa: F401
        info["has_transmission_gears"] = True
    except Exception as e:
        info["has_transmission_gears"] = False
        info["transmission_gears_error"] = repr(e)

    return info


def import_python_gearbox_primitives():
    """
    Import primitives from python-gearbox.

    We keep this in a function so we can print a helpful diagnostic if it fails.
    """
    try:
        from gearbox.transmission.gears import Lubricant, Material, Tool, Gear, Transmission  # type: ignore
        return Lubricant, Material, Tool, Gear, Transmission
    except Exception as e:
        probe = probe_gearbox_package()
        msg = (
            "Could not import python-gearbox primitives via:\n"
            "  from gearbox.transmission.gear_train import Lubricant, Material, Tool, Gear, Transmission\n\n"
            f"Import error: {e!r}\n\n"
            "DIAGNOSTIC (which `gearbox` did Python import?):\n"
            f"{_json(probe)}\n\n"
            "Most common fix (name collision):\n"
            "  1) pip uninstall -y gearbox\n"
            "  2) pip uninstall -y python-gearbox\n"
            "  3) Create a fresh venv\n"
            "  4) pip install -e git+https://github.com/efirvida/python-gearbox.git#egg=python-gearbox\n\n"
            "If you must stay on the PyPI 0.1.2.* release, run it in an isolated env with NO `gearbox` package installed.\n"
        )
        raise RuntimeError(msg) from e


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
    Lubricant, Material, Tool, Gear, Transmission = import_python_gearbox_primitives()

    lubricant = Lubricant(name="Generic ISO VG", v40=160)

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

    return Transmission(
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


def calculate_all(transmission: Any) -> dict[str, Any]:
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
    meta = {"inputs": vars(args), "power_kw": power_kw_from_torque_rpm(args.torque, args.rpm)}
    print(_json({"meta": meta, "results": results}))


if __name__ == "__main__":
    main()
