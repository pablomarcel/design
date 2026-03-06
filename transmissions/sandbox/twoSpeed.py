from transmissions.core.planetary import PlanetaryGearSet

pg = PlanetaryGearSet(30, 72, name="Example PGS")

pg.summary(
    input_member="sun",
    output_member="carrier",
    fixed_member="ring"
)