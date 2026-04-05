# ------------------------------------------------
# Advanced Four-Bar Gear Representation
# ------------------------------------------------

from mechanism import *
import numpy as np
import matplotlib.pyplot as plt

# ------------------------------------------------
# Gear parameters
# ------------------------------------------------

pd = 8
N_gear = 45
N_pinion = 15

gear_ratio = N_gear / N_pinion

r_pinion = N_pinion / (2 * pd)
r_gear = N_gear / (2 * pd)

center_distance = r_pinion + r_gear

# ------------------------------------------------
# Define joints
# ------------------------------------------------

O, A, B, C = get_joints('O A B C')

A.follow = True
B.follow = True

# ------------------------------------------------
# Define vectors
# ------------------------------------------------

a = Vector((O, A), r=r_pinion)
b = Vector((A, B), style='dotted')
c = Vector((C, B), r=r_gear)
d = Vector((O, C), r=center_distance, theta=0, show=False)

# ------------------------------------------------
# Loop equations
# ------------------------------------------------

def loops(x, inp):

    loop = a(inp) + b(x[0], x[1]) - c(x[2]) - d()

    constraint = a.pos.theta + gear_ratio * c.pos.theta

    return np.concatenate((loop, [constraint]))

# ------------------------------------------------
# Input motion
# ------------------------------------------------

thetas = np.linspace(0, gear_ratio * 2 * np.pi, 400)

pos_guess = np.array([center_distance, 0, 0])

# ------------------------------------------------
# Build mechanism
# ------------------------------------------------

mech = Mechanism(
    vectors=(a, b, c, d),
    origin=O,
    loops=loops,
    pos=thetas,
    guess=(pos_guess,)
)

mech.iterate()

# ------------------------------------------------
# Create animation
# ------------------------------------------------

ani, fig, ax = mech.get_animation()

# ------------------------------------------------
# Plot styling
# ------------------------------------------------

lim = center_distance + r_gear + 2

ax.set_xlim(-lim, lim)
ax.set_ylim(-lim, lim)
ax.set_aspect("equal")

ax.set_title("Four-Bar Linkage Representation of Gear Pair")

# ------------------------------------------------
# Draw pitch circles
# ------------------------------------------------

theta_circle = np.linspace(0, 2*np.pi, 400)

pinion_circle_x = r_pinion * np.cos(theta_circle)
pinion_circle_y = r_pinion * np.sin(theta_circle)

gear_circle_x = center_distance + r_gear * np.cos(theta_circle)
gear_circle_y = r_gear * np.sin(theta_circle)

ax.plot(pinion_circle_x, pinion_circle_y, linewidth=2)
ax.plot(gear_circle_x, gear_circle_y, linewidth=2)

# ------------------------------------------------
# Contact point
# ------------------------------------------------

contact_x = r_pinion
contact_y = 0

ax.plot(contact_x, contact_y, 'ko', markersize=6)

# ------------------------------------------------
# Line of centers
# ------------------------------------------------

ax.plot([0, center_distance], [0, 0], '--', linewidth=1)

# ------------------------------------------------
# Gear ratio label
# ------------------------------------------------

ax.text(
    center_distance/2,
    r_gear * 0.6,
    f"Gear Ratio = {gear_ratio:.1f}",
    ha="center",
    fontsize=14,
    bbox=dict(facecolor='white', alpha=0.8)
)

# ------------------------------------------------
# Angular velocity arrows
# ------------------------------------------------

arrow_scale = 0.6

ax.arrow(
    -r_pinion,
    0,
    0,
    arrow_scale,
    width=0.03,
    length_includes_head=True
)

ax.arrow(
    center_distance + r_gear,
    0,
    0,
    -arrow_scale,
    width=0.03,
    length_includes_head=True
)

# ------------------------------------------------
# Labels
# ------------------------------------------------

ax.text(0, -r_pinion - 0.5, "Pinion")
ax.text(center_distance, -r_gear - 0.5, "Gear")

# ------------------------------------------------
# Grid
# ------------------------------------------------

ax.grid(True)

plt.show()