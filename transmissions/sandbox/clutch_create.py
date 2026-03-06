from transmissions.core.clutch import RotatingMember, Clutch, Brake

sun = RotatingMember("sun")
carrier = RotatingMember("carrier")
ring = RotatingMember("ring")

c1 = Clutch(sun, carrier)
b1 = Brake(ring)

c1.engage()
b1.engage()

print(c1)
print(b1)