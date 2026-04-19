#!/usr/bin/env python3
"""
sandbox_mohr3d.py

Small CLI sandbox for 3D stress-state calculations and Mohr-circle plotting.

Features
--------
- Accepts a full symmetric 3x3 Cauchy stress tensor via CLI flags
- Computes:
    * principal stresses
    * mean (hydrostatic) stress
    * max shear stress (Tresca)
    * von Mises equivalent stress
    * stress invariants I1, I2, I3
- Plots the 3 Mohr circles for a 3D stress state

Usage examples
--------------
1) General 3D stress state:
    python -m sandbox.sandbox_mohr3d \
        --sxx 12 --syy 20 --szz -8 \
        --txy 6 --tyz -3 --txz 4 \
        --show-plot

2) Example with output only:
    python -m sandbox.sandbox_mohr3d \
        --sxx 80 --syy 20 --szz 0 \
        --txy 30 --tyz 0 --txz 0

Notes
-----
- Sign convention: positive tension for normal stress
- Tensor assumed symmetric
- Notation follows Shigley-style component names:
      [ sxx  txy  txz ]
      [ txy  syy  tyz ]
      [ txz  tyz  szz ]
- Backward-compatible alias: --tzx is still accepted and mapped to --txz
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np


@dataclass
class StressResults:
    tensor: np.ndarray
    principal_stresses: np.ndarray
    mean_stress: float
    max_shear: float
    von_mises: float
    invariants: dict[str, float]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="3D stress tensor sandbox with Mohr-circle plotting."
    )
    parser.add_argument("--sxx", type=float, required=True, help="Normal stress σxx")
    parser.add_argument("--syy", type=float, required=True, help="Normal stress σyy")
    parser.add_argument("--szz", type=float, required=True, help="Normal stress σzz")
    parser.add_argument("--txy", type=float, default=0.0, help="Shear stress τxy")
    parser.add_argument("--tyz", type=float, default=0.0, help="Shear stress τyz")
    parser.add_argument(
        "--txz",
        "--tzx",
        dest="txz",
        type=float,
        default=0.0,
        help="Shear stress τxz (legacy alias --tzx also accepted)",
    )
    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="Display the Mohr-circle plot.",
    )
    parser.add_argument(
        "--save-plot",
        type=str,
        default="",
        help="Optional file path to save the plot, e.g. mohr3d.png",
    )
    parser.add_argument(
        "--digits",
        type=int,
        default=6,
        help="Number of decimal places for text output.",
    )
    return parser


def make_stress_tensor(
    sxx: float,
    syy: float,
    szz: float,
    txy: float,
    tyz: float,
    txz: float,
) -> np.ndarray:
    return np.array(
        [
            [sxx, txy, txz],
            [txy, syy, tyz],
            [txz, tyz, szz],
        ],
        dtype=float,
    )


def compute_invariants(stress: np.ndarray) -> dict[str, float]:
    i1 = float(np.trace(stress))
    i2 = float(
        stress[0, 0] * stress[1, 1]
        + stress[1, 1] * stress[2, 2]
        + stress[2, 2] * stress[0, 0]
        - stress[0, 1] ** 2
        - stress[1, 2] ** 2
        - stress[0, 2] ** 2
    )
    i3 = float(np.linalg.det(stress))
    return {"I1": i1, "I2": i2, "I3": i3}


def compute_von_mises(stress: np.ndarray) -> float:
    sxx, syy, szz = stress[0, 0], stress[1, 1], stress[2, 2]
    txy, tyz, txz = stress[0, 1], stress[1, 2], stress[0, 2]
    vm = math.sqrt(
        0.5
        * (
            (sxx - syy) ** 2
            + (syy - szz) ** 2
            + (szz - sxx) ** 2
            + 6.0 * (txy**2 + tyz**2 + txz**2)
        )
    )
    return float(vm)


def analyze_stress(stress: np.ndarray) -> StressResults:
    eigenvalues, _ = np.linalg.eigh(stress)
    principal = np.sort(eigenvalues)[::-1]  # σ1 >= σ2 >= σ3
    sigma1, _, sigma3 = principal

    mean_stress = float(np.mean(principal))
    max_shear = float((sigma1 - sigma3) / 2.0)
    von_mises = compute_von_mises(stress)
    invariants = compute_invariants(stress)

    return StressResults(
        tensor=stress,
        principal_stresses=principal,
        mean_stress=mean_stress,
        max_shear=max_shear,
        von_mises=von_mises,
        invariants=invariants,
    )


def mohr_circle_data(principal: np.ndarray) -> list[dict[str, float]]:
    sigma1, sigma2, sigma3 = principal
    pairs = [
        ("(σ1, σ2)", sigma1, sigma2),
        ("(σ2, σ3)", sigma2, sigma3),
        ("(σ1, σ3)", sigma1, sigma3),
    ]

    circles = []
    for label, a, b in pairs:
        center = (a + b) / 2.0
        radius = abs(a - b) / 2.0
        circles.append(
            {
                "label": label,
                "sigma_a": a,
                "sigma_b": b,
                "center": center,
                "radius": radius,
            }
        )
    return circles


def plot_mohr_3d(principal: np.ndarray, outfile: str = "") -> None:
    circles = mohr_circle_data(principal)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_aspect("equal", adjustable="box")

    theta = np.linspace(0.0, 2.0 * np.pi, 800)

    for circle in circles:
        c = circle["center"]
        r = circle["radius"]
        x = c + r * np.cos(theta)
        y = r * np.sin(theta)
        ax.plot(x, y, label=f'{circle["label"]}: c={c:.3f}, r={r:.3f}')

    sigma1, sigma2, sigma3 = principal
    ax.scatter(
        [sigma1, sigma2, sigma3],
        [0.0, 0.0, 0.0],
        marker="o",
        label="Principal stresses",
    )

    ax.axhline(0.0, linewidth=1.0)
    ax.axvline(0.0, linewidth=1.0)
    ax.set_xlabel("Normal stress, σ")
    ax.set_ylabel("Shear stress, τ")
    ax.set_title("3D Mohr Circles")
    ax.grid(True)
    ax.legend()

    all_sigmas = [sigma1, sigma2, sigma3]
    max_radius = max(c["radius"] for c in circles)
    pad_x = max(1.0, 0.15 * max(1.0, max(abs(v) for v in all_sigmas)))
    pad_y = max(1.0, 0.15 * max(1.0, max_radius))

    ax.set_xlim(min(all_sigmas) - pad_x, max(all_sigmas) + pad_x)
    ax.set_ylim(-max_radius - pad_y, max_radius + pad_y)

    plt.tight_layout()

    if outfile:
        plt.savefig(outfile, dpi=160, bbox_inches="tight")

    plt.show()


def pretty_print(results: StressResults, digits: int) -> None:
    p = results.principal_stresses
    inv = results.invariants
    fmt = f"{{:.{digits}f}}"

    print("\n3D STRESS TENSOR")
    print(results.tensor)

    print("\nPRINCIPAL STRESSES")
    print(f"σ1 = {fmt.format(p[0])}")
    print(f"σ2 = {fmt.format(p[1])}")
    print(f"σ3 = {fmt.format(p[2])}")

    print("\nDERIVED QUANTITIES")
    print(f"Mean stress          = {fmt.format(results.mean_stress)}")
    print(f"Max shear (Tresca)   = {fmt.format(results.max_shear)}")
    print(f"Von Mises stress     = {fmt.format(results.von_mises)}")

    print("\nSTRESS INVARIANTS")
    print(f"I1 = {fmt.format(inv['I1'])}")
    print(f"I2 = {fmt.format(inv['I2'])}")
    print(f"I3 = {fmt.format(inv['I3'])}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    stress = make_stress_tensor(
        sxx=args.sxx,
        syy=args.syy,
        szz=args.szz,
        txy=args.txy,
        tyz=args.tyz,
        txz=args.txz,
    )

    results = analyze_stress(stress)
    pretty_print(results, digits=args.digits)

    if args.show_plot or args.save_plot:
        plot_mohr_3d(results.principal_stresses, outfile=args.save_plot)


if __name__ == "__main__":
    main()
