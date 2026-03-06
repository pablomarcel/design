#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.gear_state_table

Enumerates all possible operating states for a simple planetary gearset.

Each state specifies:
    input member
    output member
    fixed member

Using the Willis equation solver from planetary.py.

Author: Pablo Montijo Design Project
"""

from typing import List, Dict
from itertools import permutations

from transmissions.core.planetary import PlanetaryGearSet


# ------------------------------------------------------------
# Gear state table generator
# ------------------------------------------------------------

def generate_state_table(gearset: PlanetaryGearSet) -> List[Dict]:
    """
    Generate all possible planetary gear operating states.

    Returns
    -------
    list of dict
    """

    members = ["sun", "ring", "carrier"]

    table = []

    for input_member, output_member, fixed_member in permutations(members, 3):

        speeds = gearset.solve(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member,
            input_speed=1.0
        )

        ratio = gearset.ratio(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member
        )

        mode = gearset.describe_mode(
            input_member=input_member,
            output_member=output_member,
            fixed_member=fixed_member
        )

        row = dict(
            input=input_member,
            output=output_member,
            fixed=fixed_member,
            ratio=ratio,
            mode=mode,
            speeds=speeds
        )

        table.append(row)

    return table


# ------------------------------------------------------------
# Pretty print
# ------------------------------------------------------------

def print_state_table(table: List[Dict]):

    print()
    print("Planetary Gearset State Table")
    print("-------------------------------------------------------------")
    print(f"{'Input':>8}  {'Output':>8}  {'Fixed':>8}  {'Ratio':>10}  {'Mode':>12}")
    print("-------------------------------------------------------------")

    for row in table:

        print(
            f"{row['input']:>8}  "
            f"{row['output']:>8}  "
            f"{row['fixed']:>8}  "
            f"{row['ratio']:>10.3f}  "
            f"{row['mode']:>12}"
        )

    print()


# ------------------------------------------------------------
# Convenience helper
# ------------------------------------------------------------

def analyze_planetary(Ns: int, Nr: int):
    """
    Quick planetary analysis helper.
    """

    gearset = PlanetaryGearSet(Ns, Nr)

    table = generate_state_table(gearset)

    print_state_table(table)

    return table


# ------------------------------------------------------------
# Example usage
# ------------------------------------------------------------

if __name__ == "__main__":

    table = analyze_planetary(
        Ns=30,
        Nr=72
    )