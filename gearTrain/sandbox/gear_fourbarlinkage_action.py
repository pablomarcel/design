# ------------------------------------------------
# Industrial Gear Four-Bar Visualization
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

pressure_angle = np.deg2rad(20)

# base circle radii
rb_pinion = r_pinion * np.cos(pressure_angle)
rb_gear = r_gear * np.cos(pressure_angle)

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

ani, fig, ax = mech.get_animation()

# ------------------------------------------------
# Plot limits
# ------------------------------------------------

lim = center_distance + r_gear + 2

ax.set_xlim(-lim, lim)
ax.set_ylim(-lim, lim)
ax.set_aspect("equal")

ax.set_title("Four-Bar Representation of Involute Gear Pair")

# ------------------------------------------------
# Draw pitch circles
# ------------------------------------------------

theta = np.linspace(0, 2*np.pi, 400)

ax.plot(
    r_pinion*np.cos(theta),
    r_pinion*np.sin(theta),
    linewidth=3,
    label="Pinion pitch circle"
)

ax.plot(
    center_distance + r_gear*np.cos(theta),
    r_gear*np.sin(theta),
    linewidth=3,
    label="Gear pitch circle"
)

# ------------------------------------------------
# Base circles
# ------------------------------------------------

ax.plot(
    rb_pinion*np.cos(theta),
    rb_pinion*np.sin(theta),
    '--',
    linewidth=2
)

ax.plot(
    center_distance + rb_gear*np.cos(theta),
    rb_gear*np.sin(theta),
    '--',
    linewidth=2
)

# ------------------------------------------------
# Line of centers
# ------------------------------------------------

ax.plot([0, center_distance], [0,0], 'g--', linewidth=2)

# ------------------------------------------------
# Pitch point
# ------------------------------------------------

pitch_x = r_pinion
pitch_y = 0

ax.plot(pitch_x, pitch_y, 'ko', markersize=8)

# ------------------------------------------------
# Line of action
# ------------------------------------------------

loa_length = lim

x1 = pitch_x - loa_length*np.sin(pressure_angle)
y1 = pitch_y + loa_length*np.cos(pressure_angle)

x2 = pitch_x + loa_length*np.sin(pressure_angle)
y2 = pitch_y - loa_length*np.cos(pressure_angle)

ax.plot([x1,x2],[y1,y2],'r--',linewidth=2)

# ------------------------------------------------
# Contact path visualization
# ------------------------------------------------

contact_len = 1.2

xc1 = pitch_x - contact_len*np.sin(pressure_angle)
yc1 = pitch_y + contact_len*np.cos(pressure_angle)

xc2 = pitch_x + contact_len*np.sin(pressure_angle)
yc2 = pitch_y - contact_len*np.cos(pressure_angle)

ax.plot([xc1,xc2],[yc1,yc2],'r',linewidth=4)

# ------------------------------------------------
# Angular velocity arrows
# ------------------------------------------------

arrow = 0.7

ax.arrow(-r_pinion,0,0,arrow,width=0.03)
ax.arrow(center_distance+r_gear,0,0,-arrow,width=0.03)

# ------------------------------------------------
# Labels
# ------------------------------------------------

ax.text(0,-r_pinion-0.5,"Pinion",ha='center')
ax.text(center_distance,-r_gear-0.5,"Gear",ha='center')

ax.text(
    center_distance/2,
    r_gear*0.6,
    f"Gear Ratio = {gear_ratio:.1f}",
    ha="center",
    fontsize=14,
    bbox=dict(facecolor='white', alpha=0.9)
)

ax.text(
    pitch_x+0.1,
    pitch_y+0.2,
    "Pitch Point"
)

ax.text(
    x2,
    y2,
    "Line of Action",
    rotation=np.rad2deg(-pressure_angle)
)

# ------------------------------------------------
# Grid
# ------------------------------------------------

ax.grid(True)

plt.show()