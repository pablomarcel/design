import numpy as np
import matplotlib.pyplot as plt
from mechanism import Cam


# -----------------------------
# CAM DEFINITION
# -----------------------------

cam = Cam(
    motion=[
        ('Rise', 3, 90),
        ('Dwell', 15),
        ('Fall', 3, 90),
        ('Dwell', 15),
        ('Rise', 2, 60),
        ('Dwell', 15),
        ('Fall', 2, 60),
        ('Dwell', 15)
    ],
    degrees=True,
    omega=np.pi,
    rotation='cw'
)


# -----------------------------
# SIZE CAM (ROLLER FOLLOWER)
# -----------------------------

roller_analysis = cam.get_base_circle(
    kind='cycloidal',
    follower='roller',
    roller_radius=1,
    max_pressure_angle=30,
    plot=True
)


# -----------------------------
# CAM PROFILE
# -----------------------------

fig1, ax1 = cam.profile(
    kind='cycloidal',
    base=roller_analysis['Rb'],
    show_base=True,
    show_pitch=True,
    roller_radius=1
)

plt.title("Cam Profile (Cycloidal + Roller)")
plt.show()


# -----------------------------
# ROLLER FOLLOWER ANIMATION
# -----------------------------

ani, fig2, ax2, follower = cam.get_animation(
    kind='cycloidal',
    base=4,
    inc=5,
    roller_radius=1
)

plt.title("Cam Animation — Roller Follower")
plt.show()


# -----------------------------
# FOLLOWER MOTION PLOT
# -----------------------------

fig3, ax3 = follower.plot()

plt.title("Follower Motion (Roller)")
plt.show()


# -----------------------------
# FLAT FACE FOLLOWER ANIMATION
# -----------------------------

ani2, fig4, ax4, follower2 = cam.get_animation(
    kind='harmonic',
    base=4,
    inc=5,
    face_width=4
)

plt.title("Cam Animation — Flat Face Follower")
plt.show()


# -----------------------------
# FOLLOWER MOTION (FLAT)
# -----------------------------

fig5, ax5 = follower2.plot()

plt.title("Follower Motion (Flat Face)")
plt.show()