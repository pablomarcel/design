import sympy as sp
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ------------------------------------------------
# Cam motion definition
# ------------------------------------------------

motion = [
    ('Rise', 3, 90),
    ('Dwell', 15),
    ('Fall', 3, 90),
    ('Dwell', 15),
    ('Rise', 2, 60),
    ('Dwell', 15),
    ('Fall', 2, 60),
    ('Dwell', 15)
]

roller_radius = 1
base_radius = 4

# ------------------------------------------------
# Cycloidal motion law
# ------------------------------------------------

theta = sp.symbols('theta')
beta = sp.symbols('beta')
h = sp.symbols('h')

cycloidal_rise = h*(theta/beta - (1/(2*sp.pi))*sp.sin(2*sp.pi*theta/beta))
cycloidal_fall = h*(1-(theta/beta - (1/(2*sp.pi))*sp.sin(2*sp.pi*theta/beta)))

rise_func = sp.lambdify((theta,beta,h), cycloidal_rise,'numpy')
fall_func = sp.lambdify((theta,beta,h), cycloidal_fall,'numpy')

# ------------------------------------------------
# Generate displacement curve
# ------------------------------------------------

angles=[]
disp=[]
current_angle=0

for seg in motion:

    if seg[0]=='Rise':
        height,deg=seg[1],seg[2]
        local=np.linspace(0,deg,200)
        s=rise_func(local,deg,height)

    elif seg[0]=='Fall':
        height,deg=seg[1],seg[2]
        local=np.linspace(0,deg,200)
        s=fall_func(local,deg,height)

    elif seg[0]=='Dwell':
        deg=seg[1]
        local=np.linspace(0,deg,100)
        s=np.ones_like(local)*disp[-1] if disp else np.zeros_like(local)

    global_theta=current_angle+local

    angles.extend(global_theta)
    disp.extend(s)

    current_angle+=local[-1]

angles=np.radians(np.array(angles))
disp=np.array(disp)

# ------------------------------------------------
# Kinematics
# ------------------------------------------------

vel=np.gradient(disp,angles)
acc=np.gradient(vel,angles)

pitch_radius=base_radius+disp

pressure_angle=np.degrees(np.arctan(vel/pitch_radius))

# ------------------------------------------------
# Cam geometry
# ------------------------------------------------

x_pitch=pitch_radius*np.cos(angles)
y_pitch=pitch_radius*np.sin(angles)

cam_x=x_pitch-roller_radius*np.cos(angles)
cam_y=y_pitch-roller_radius*np.sin(angles)

cam_outline=np.vstack((cam_x,cam_y))

# ------------------------------------------------
# Figure layout
# ------------------------------------------------

fig=plt.figure(figsize=(12,6))

ax_mech=fig.add_subplot(121)
ax_mech.set_aspect('equal')
ax_mech.set_xlim(-10,10)
ax_mech.set_ylim(-10,10)
ax_mech.grid(True)
ax_mech.set_title("Cam Mechanism")

cam_fill=ax_mech.fill(cam_x,cam_y,color='red',ec='black')[0]

roller=plt.Circle((0,0),roller_radius,color='lightgray',ec='black')
ax_mech.add_patch(roller)

follower_bar,=ax_mech.plot([],[],lw=6,color='gray')

# ------------------------------------------------
# Pressure angle plot
# ------------------------------------------------

ax_pressure=fig.add_subplot(222)
ax_pressure.plot(np.degrees(angles),pressure_angle)
ax_pressure.set_title("Pressure Angle")
ax_pressure.grid(True)

pressure_marker,=ax_pressure.plot([],[],'ro')

# ------------------------------------------------
# Kinematics plot
# ------------------------------------------------

ax_motion=fig.add_subplot(224)

ax_motion.plot(np.degrees(angles),disp,label='disp')
ax_motion.plot(np.degrees(angles),vel,label='vel')
ax_motion.plot(np.degrees(angles),acc,label='acc')

ax_motion.legend()
ax_motion.grid(True)
ax_motion.set_title("Follower Kinematics")

motion_marker,=ax_motion.plot([],[],'ro')

# ------------------------------------------------
# Animation
# ------------------------------------------------

def update(frame):

    rot=angles[frame]

    R=np.array([
        [np.cos(rot),-np.sin(rot)],
        [np.sin(rot), np.cos(rot)]
    ])

    rotated=R@cam_outline

    cam_fill.set_xy(np.column_stack((rotated[0],rotated[1])))

    idx=np.argmax(rotated[1])

    contact_y=rotated[1][idx]

    roller_y=contact_y+roller_radius

    roller.center=(0,roller_y)

    follower_bar.set_data([0,0],[roller_y,roller_y+3])

    pressure_marker.set_data(
        [np.degrees(angles[frame])],
        [pressure_angle[frame]]
    )

    motion_marker.set_data(
        [np.degrees(angles[frame])],
        [disp[frame]]
    )

    return cam_fill,roller,follower_bar,pressure_marker,motion_marker


anim=FuncAnimation(fig,update,frames=len(angles),interval=30)

plt.tight_layout()
plt.show()