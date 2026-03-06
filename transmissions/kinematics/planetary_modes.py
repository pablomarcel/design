#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.planetary_modes

Analytical derivation of planetary gear operating modes
from the Willis equation.

Willis equation:

    Ns(ωs − ωc) + Nr(ωr − ωc) = 0

This script derives the speed relationships and gear ratios
for all six operating modes of a simple planetary gearset.

Author: Pablo Montijo Design Project
"""

import sympy as sp


# ------------------------------------------------------------
# symbolic variables
# ------------------------------------------------------------

Ns, Nr = sp.symbols("Ns Nr", positive=True)

ws, wr, wc = sp.symbols("ws wr wc")


# Willis equation
willis = Ns*(ws - wc) + Nr*(wr - wc)


# ------------------------------------------------------------
# helper function
# ------------------------------------------------------------

def derive_mode(input_member, output_member, fixed_member):
    """
    Derive ratio symbolically.
    """

    eqs = [willis]

    if fixed_member == "sun":
        eqs.append(ws)
    elif fixed_member == "ring":
        eqs.append(wr)
    elif fixed_member == "carrier":
        eqs.append(wc)

    if input_member == "sun":
        eqs.append(ws - 1)
    elif input_member == "ring":
        eqs.append(wr - 1)
    elif input_member == "carrier":
        eqs.append(wc - 1)

    sol = sp.solve(eqs, (ws, wr, wc))

    win = sol[{"sun": ws, "ring": wr, "carrier": wc}[input_member]]
    wout = sol[{"sun": ws, "ring": wr, "carrier": wc}[output_member]]

    ratio = sp.simplify(win / wout)

    return ratio


# ------------------------------------------------------------
# planetary modes
# ------------------------------------------------------------

def planetary_modes():

    members = ["sun", "ring", "carrier"]

    modes = []

    for inp in members:

        for out in members:

            if out == inp:
                continue

            fixed = list(set(members) - {inp, out})[0]

            ratio = derive_mode(inp, out, fixed)

            modes.append(
                dict(
                    input=inp,
                    output=out,
                    fixed=fixed,
                    ratio=ratio
                )
            )

    return modes


# ------------------------------------------------------------
# pretty print
# ------------------------------------------------------------

def print_modes():

    modes = planetary_modes()

    print()
    print("Planetary Gear Analytical Modes")
    print("-----------------------------------------------------")
    print(f"{'Input':>8} {'Output':>8} {'Fixed':>8} {'Ratio Formula':>20}")
    print("-----------------------------------------------------")

    for m in modes:

        print(
            f"{m['input']:>8} "
            f"{m['output']:>8} "
            f"{m['fixed']:>8} "
            f"{str(m['ratio']):>20}"
        )

    print()


# ------------------------------------------------------------
# main
# ------------------------------------------------------------

if __name__ == "__main__":

    print_modes()