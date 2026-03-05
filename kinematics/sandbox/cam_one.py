import sympy as sp
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# ------------------------------------------------
# PARAMETERS
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
follower_offset = 4.5

# ------------------------------------------------
# Cycloidal motion law
# ------------------------------------------------

theta = sp.symbols('theta')
beta = sp.symbols('beta')
h = sp.symbols('h')

rise = h*(theta/beta - (1/(2*sp.pi))*sp.sin(2*sp.pi*theta/beta))
fall = h*(1 - (theta/beta - (1/(2*sp.pi))*sp.sin(2*sp.pi*theta/beta)))

rise_func = sp.lambdify((theta,beta,h),rise,'numpy')
fall_func = sp.lambdify((theta,beta,h),fall,'numpy')

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
# KINEMATICS
# ------------------------------------------------

dtheta = angles[1]-angles[0]

vel = np.gradient(disp,dtheta)
acc = np.gradient(vel,dtheta)

# ------------------------------------------------
# PRESSURE ANGLE
# ------------------------------------------------

pitch_radius = base_radius + disp
pressure_angle = np.degrees(np.arctan(vel/pitch_radius))

# ------------------------------------------------
# FOLLOWER PATH (world frame)
# ------------------------------------------------

x_world = np.ones_like(angles)*follower_offset
y_world = base_radius + roller_radius + disp

# ------------------------------------------------
# PITCH CURVE (cam frame)
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
# CAM PROFILE
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
# CURVATURE
# ------------------------------------------------

ddx=np.gradient(dx)
ddy=np.gradient(dy)

curvature = np.abs(dx*ddy - dy*ddx)/(dx*dx + dy*dy)**1.5
radius_curvature = 1/curvature

min_radius = np.min(radius_curvature)

undercut = min_radius < roller_radius

# ------------------------------------------------
# REPORT
# ------------------------------------------------

print("\n------ CAM DESIGN REPORT ------\n")

print("Max pressure angle:",np.max(np.abs(pressure_angle)))
print("Minimum curvature radius:",min_radius)

if undercut:
    print("WARNING: Undercutting will occur\n")
else:
    print("No undercutting detected\n")

# ------------------------------------------------
# FIGURE
# ------------------------------------------------

fig = plt.figure(figsize=(14,8))

gs = fig.add_gridspec(2,2)

ax_mech = fig.add_subplot(gs[:,0])
ax_pressure = fig.add_subplot(gs[0,1])
ax_motion = fig.add_subplot(gs[1,1])

# ------------------------------------------------
# MECHANISM PLOT
# ------------------------------------------------

ax_mech.set_aspect('equal')
ax_mech.set_xlim(-10,10)
ax_mech.set_ylim(-10,10)
ax_mech.set_title("Cam Mechanism")
ax_mech.grid(True)

cam_fill=ax_mech.fill(cam_x,cam_y,color='red',ec='black')[0]

roller=plt.Circle((follower_offset,0),roller_radius,fc='lightgray',ec='black')
ax_mech.add_patch(roller)

follower_bar,=ax_mech.plot([],[],lw=6,color='gray')

# ------------------------------------------------
# PRESSURE ANGLE
# ------------------------------------------------

ax_pressure.plot(angles_deg,pressure_angle)
ax_pressure.set_title("Pressure Angle")
ax_pressure.set_ylabel("deg")
ax_pressure.set_xlabel("cam angle")
ax_pressure.grid(True)

pressure_marker,=ax_pressure.plot([],[],'ro')

# ------------------------------------------------
# FOLLOWER KINEMATICS
# ------------------------------------------------

ax_motion.plot(angles_deg,disp,label='disp')
ax_motion.plot(angles_deg,vel,label='vel')
ax_motion.plot(angles_deg,acc,label='acc')

ax_motion.legend()
ax_motion.set_title("Follower Kinematics")
ax_motion.set_xlabel("cam angle")
ax_motion.grid(True)

motion_marker,=ax_motion.plot([],[],'ro')

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

    pressure_marker.set_data([angles_deg[frame]],[pressure_angle[frame]])
    motion_marker.set_data([angles_deg[frame]],[disp[frame]])

    return cam_fill,roller,follower_bar,pressure_marker,motion_marker

anim=FuncAnimation(fig,update,frames=len(angles),interval=30)

plt.tight_layout()
plt.show()