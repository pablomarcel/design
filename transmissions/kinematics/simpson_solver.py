#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.simpson_solver
"""

from transmissions.core.solver import TransmissionSolver
from transmissions.core.clutch import RotatingMember, Clutch, Brake
from transmissions.core.planetary import PlanetaryGearSet


class SimpsonTransmission:

    def __init__(self, Ns, Nr1, Nr2):

        self.Ns = Ns
        self.Nr1 = Nr1
        self.Nr2 = Nr2

        # rotating members
        self.sun = RotatingMember("sun")
        self.ring1 = RotatingMember("ring1")
        self.ring2 = RotatingMember("ring2")
        self.carrier = RotatingMember("carrier")

        # planetary gearsets
        self.p1 = PlanetaryGearSet(
            Ns=Ns,
            Nr=Nr1,
            sun=self.sun,
            ring=self.ring1,
            carrier=self.carrier
        )

        self.p2 = PlanetaryGearSet(
            Ns=Ns,
            Nr=Nr2,
            sun=self.sun,
            ring=self.ring2,
            carrier=self.carrier
        )

        # solver
        self.solver = TransmissionSolver()

        for m in [
            self.sun,
            self.ring1,
            self.ring2,
            self.carrier
        ]:
            self.solver.add_member(m)

        self.solver.add_gearset(self.p1)
        self.solver.add_gearset(self.p2)

        # shift elements
        self.ring1_brake = Brake(self.ring1)
        self.ring2_brake = Brake(self.ring2)

        self.direct_clutch = Clutch(self.sun, self.carrier)

        self.solver.add_brake(self.ring1_brake)
        self.solver.add_brake(self.ring2_brake)
        self.solver.add_clutch(self.direct_clutch)

    def reset(self):

        self.ring1_brake.release()
        self.ring2_brake.release()
        self.direct_clutch.release()

    def first_gear(self):

        self.reset()

        self.ring2_brake.engage()

        return self.solver.solve(
            input_member="carrier",
            input_speed=1.0
        )

    def second_gear(self):

        self.reset()

        self.ring1_brake.engage()

        return self.solver.solve(
            input_member="carrier",
            input_speed=1.0
        )

    def third_gear(self):

        self.reset()

        self.direct_clutch.engage()

        return self.solver.solve(
            input_member="carrier",
            input_speed=1.0
        )

    def reverse(self):

        self.reset()

        self.ring1_brake.engage()

        return self.solver.solve(
            input_member="sun",
            input_speed=1.0
        )


def gear_ratio(result, input_member, output_member):

    return result[input_member] / result[output_member]