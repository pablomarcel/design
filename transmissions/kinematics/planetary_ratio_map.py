#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.planetary_ratio_map

Explores planetary gear ratios by sweeping sun and ring tooth counts.

Uses the analytical formulas derived from the Willis equation.

Author: Pablo Montijo Design Project
"""

from typing import List, Dict


# ------------------------------------------------------------
# Ratio formulas
# ------------------------------------------------------------

def planetary_ratios(Ns: int, Nr: int) -> Dict[str, float]:
    """
    Compute the six planetary ratios.

    Returns dictionary keyed by operating mode.
    """

    ratios = {}

    ratios["sun->carrier | ring fixed"] = (Nr + Ns) / Ns
    ratios["sun->ring | carrier fixed"] = -Nr / Ns

    ratios["ring->carrier | sun fixed"] = (Nr + Ns) / Nr
    ratios["ring->sun | carrier fixed"] = -Ns / Nr

    ratios["carrier->sun | ring fixed"] = Ns / (Nr + Ns)
    ratios["carrier->ring | sun fixed"] = Nr / (Nr + Ns)

    return ratios


# ------------------------------------------------------------
# Ratio sweep
# ------------------------------------------------------------

def generate_ratio_map(
    sun_range,
    ring_range
) -> List[Dict]:
    """
    Sweep tooth counts and compute ratios.
    """

    results = []

    for Ns in sun_range:

        for Nr in ring_range:

            if Nr <= Ns:
                continue

            ratios = planetary_ratios(Ns, Nr)

            row = {
                "Ns": Ns,
                "Nr": Nr,
                "ratios": ratios
            }

            results.append(row)

    return results


# ------------------------------------------------------------
# Pretty print
# ------------------------------------------------------------

def print_ratio_map(results, limit=20):

    print()
    print("Planetary Ratio Map")
    print("------------------------------------------------------------")
    print(f"{'Ns':>6} {'Nr':>6} {'Sun->Carrier':>15} {'Ring->Carrier':>15}")
    print("------------------------------------------------------------")

    count = 0

    for r in results:

        Ns = r["Ns"]
        Nr = r["Nr"]

        sc = r["ratios"]["sun->carrier | ring fixed"]
        rc = r["ratios"]["ring->carrier | sun fixed"]

        print(f"{Ns:6} {Nr:6} {sc:15.3f} {rc:15.3f}")

        count += 1

        if count >= limit:
            break

    print()


# ------------------------------------------------------------
# Target ratio search
# ------------------------------------------------------------

def search_ratio(target_ratio, sun_range, ring_range, tol=0.05):
    """
    Find planetary gearsets that approximate a target ratio.
    """

    matches = []

    for Ns in sun_range:

        for Nr in ring_range:

            if Nr <= Ns:
                continue

            ratio = (Nr + Ns) / Ns

            if abs(ratio - target_ratio) < tol:

                matches.append((Ns, Nr, ratio))

    return matches


# ------------------------------------------------------------
# Example usage
# ------------------------------------------------------------

if __name__ == "__main__":

    sun_range = range(15, 60)
    ring_range = range(30, 120)

    results = generate_ratio_map(sun_range, ring_range)

    print_ratio_map(results)

    print("Example: search for ~3.5 ratio")

    matches = search_ratio(
        target_ratio=3.5,
        sun_range=sun_range,
        ring_range=ring_range
    )

    for m in matches[:10]:

        Ns, Nr, ratio = m

        print(f"Ns={Ns}, Nr={Nr}, ratio={ratio:.3f}")