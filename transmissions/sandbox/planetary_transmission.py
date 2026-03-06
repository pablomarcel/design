from transmissions.core.solver import TransmissionSolver
from transmissions.core.clutch import RotatingMember, Brake
from transmissions.core.planetary import PlanetaryGearSet

solver = TransmissionSolver()

sun = RotatingMember("sun")
ring = RotatingMember("ring")
carrier = RotatingMember("carrier")

solver.add_member(sun)
solver.add_member(ring)
solver.add_member(carrier)

pgs = PlanetaryGearSet(30, 72)

solver.add_gearset(pgs)

brake = Brake(ring)
brake.engage()

solver.add_brake(brake)

result = solver.solve("sun", 1.0)

print(result)