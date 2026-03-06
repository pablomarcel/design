#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.simpson_ratio_map

Physically correct Simpson transmission ratio explorer.

Uses the real kinematic solver instead of approximate formulas.

Author: Pablo Montijo Design Project
"""

from typing import List, Dict

from transmissions.kinematics.simpson_solver import (
    SimpsonTransmission,
    gear_ratio
)


# ------------------------------------------------------------
# Generate ratio map
# ------------------------------------------------------------

def generate_simpson_map(
    sun_range,
    ring_range
) -> List[Dict]:

    results = []

    for Ns in sun_range:

        for Nr1 in ring_range:

            for Nr2 in ring_range:

                if Nr1 <= Ns or Nr2 <= Ns:
                    continue

                try:

                    simpson = SimpsonTransmission(
                        Ns=Ns,
                        Nr1=Nr1,
                        Nr2=Nr2
                    )

                    r1 = simpson.first_gear()
                    r2 = simpson.second_gear()
                    r3 = simpson.third_gear()
                    rr = simpson.reverse()

                    ratios = dict(
                        first=gear_ratio(r1, "carrier1", "carrier2"),
                        second=gear_ratio(r2, "carrier1", "carrier2"),
                        third=gear_ratio(r3, "carrier1", "carrier2"),
                        reverse=gear_ratio(rr, "sun", "carrier2")
                    )

                    results.append(
                        dict(
                            Ns=Ns,
                            Nr1=Nr1,
                            Nr2=Nr2,
                            ratios=ratios
                        )
                    )

                except Exception:
                    # some configurations are not solvable
                    continue

    return results


# ------------------------------------------------------------
# Pretty print
# ------------------------------------------------------------

def print_simpson_table(results, limit=50):

    print()
    print("Simpson Transmission Ratio Map")
    print("-----------------------------------------------------------------")
    print(f"{'Ns':>5} {'Nr1':>5} {'Nr2':>5} {'1st':>10} {'2nd':>10} {'3rd':>10} {'Rev':>10}")
    print("-----------------------------------------------------------------")

    for r in results[:limit]:

        ratios = r["ratios"]

        print(
            f"{r['Ns']:5} "
            f"{r['Nr1']:5} "
            f"{r['Nr2']:5} "
            f"{ratios['first']:10.3f} "
            f"{ratios['second']:10.3f} "
            f"{ratios['third']:10.3f} "
            f"{ratios['reverse']:10.3f}"
        )

    print()


# ------------------------------------------------------------
# Search tool
# ------------------------------------------------------------

def search_simpson(
    target_ratio,
    sun_range,
    ring_range,
    gear="first",
    tol=0.2
):

    matches = []

    results = generate_simpson_map(sun_range, ring_range)

    for r in results:

        ratio = r["ratios"][gear]

        if abs(ratio - target_ratio) < tol:

            matches.append(r)

    return matches


# ------------------------------------------------------------
# Example
# ------------------------------------------------------------

if __name__ == "__main__":

    sun_range = range(20, 40)
    ring_range = range(50, 90)

    results = generate_simpson_map(
        sun_range,
        ring_range
    )

    print_simpson_table(results)

    print("Search for ~3.0 first gear")

    matches = search_simpson(
        target_ratio=3.0,
        sun_range=sun_range,
        ring_range=ring_range
    )

    for m in matches[:10]:

        print(
            f"Ns={m['Ns']} "
            f"Nr1={m['Nr1']} "
            f"Nr2={m['Nr2']} "
            f"1st={m['ratios']['first']:.3f}"
        )