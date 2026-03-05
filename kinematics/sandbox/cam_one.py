import sympy as sp
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ------------------------------------------------
# CAM PARAMETERS
# ------------------------------------------------

motion = [
    ('Rise',3,90),
    ('Dwell',15),
    ('Fall',3,90),
    ('Dwell',15),
    ('Rise',2,60),
    ('Dwell',15),
    ('Fall',2,60),
    ('Dwell',15)
]

roller_radius = 1
base_radius = 4
follower_offset = 4.5   # horizontal follower guide

# ------------------------------------------------
# Cycloidal motion law
# ------------------------------------------------

theta=sp.symbols('theta')
beta=sp.symbols('beta')
h=sp.symbols('h')

rise=h*(theta/beta-(1/(2*sp.pi))*sp.sin(2*sp.pi*theta/beta))
fall=h*(1-(theta/beta-(1/(2*sp.pi))*sp.sin(2*sp.pi*theta/beta)))

rise_func=sp.lambdify((theta,beta,h),rise,'numpy')
fall_func=sp.lambdify((theta,beta,h),fall,'numpy')

# ------------------------------------------------
# BUILD MOTION
# ------------------------------------------------

angles_deg=[]
disp=[]

current=0

for seg in motion:

    if seg[0]=='Rise':
        lift,deg=seg[1],seg[2]
        local=np.linspace(0,deg,200)
        s=rise_func(local,deg,lift)

    elif seg[0]=='Fall':
        lift,deg=seg[1],seg[2]
        local=np.linspace(0,deg,200)
        s=fall_func(local,deg,lift)

    elif seg[0]=='Dwell':
        deg=seg[1]
        local=np.linspace(0,deg,120)
        s=np.ones_like(local)*disp[-1] if disp else np.zeros_like(local)

    angles_deg.extend(current+local)
    disp.extend(s)

    current+=deg

angles_deg=np.array(angles_deg)
disp=np.array(disp)

angles=np.radians(angles_deg)

# ------------------------------------------------
# FOLLOWER PATH (world frame)
# ------------------------------------------------

x_world = np.ones_like(angles)*follower_offset
y_world = base_radius + roller_radius + disp

# ------------------------------------------------
# TRANSFORM INTO CAM FRAME
# ------------------------------------------------

x_pitch=[]
y_pitch=[]

for i,th in enumerate(angles):

    R=np.array([
        [np.cos(-th),-np.sin(-th)],
        [np.sin(-th), np.cos(-th)]
    ])

    p=R@np.array([x_world[i],y_world[i]])

    x_pitch.append(p[0])
    y_pitch.append(p[1])

x_pitch=np.array(x_pitch)
y_pitch=np.array(y_pitch)

# ------------------------------------------------
# CAM PROFILE FROM PITCH CURVE
# ------------------------------------------------

dx=np.gradient(x_pitch)
dy=np.gradient(y_pitch)

length=np.sqrt(dx**2+dy**2)

nx=-dy/length
ny=dx/length

cam_x=x_pitch-roller_radius*nx
cam_y=y_pitch-roller_radius*ny

cam_outline=np.vstack((cam_x,cam_y))

# ------------------------------------------------
# FIGURE
# ------------------------------------------------

fig=plt.figure(figsize=(12,6))

ax_mech=fig.add_subplot(121)
ax_mech.set_aspect('equal')
ax_mech.set_xlim(-10,10)
ax_mech.set_ylim(-10,10)
ax_mech.grid(True)
ax_mech.set_title("Cam Mechanism")

cam_fill=ax_mech.fill(cam_x,cam_y,color='red',ec='black')[0]

roller=plt.Circle((follower_offset,0),roller_radius,fc='lightgray',ec='black')
ax_mech.add_patch(roller)

follower_bar,=ax_mech.plot([],[],lw=6,color='gray')

# ------------------------------------------------
# ANIMATION
# ------------------------------------------------

def update(frame):

    th=angles[frame]

    R=np.array([
        [np.cos(th),-np.sin(th)],
        [np.sin(th), np.cos(th)]
    ])

    rotated=R@cam_outline
    cam_fill.set_xy(np.column_stack((rotated[0],rotated[1])))

    rx=follower_offset
    ry=base_radius+roller_radius+disp[frame]

    roller.center=(rx,ry)

    follower_bar.set_data([rx,rx],[ry,ry+3])

    return cam_fill,roller,follower_bar

anim=FuncAnimation(fig,update,frames=len(angles),interval=30)

plt.tight_layout()
plt.show()