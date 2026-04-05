import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# --- link lengths
L1 = 4.0   # ground
L2 = 2.0   # crank
L3 = 3.5   # coupler
L4 = 3.0   # rocker

# ground points
O2 = np.array([0.0, 0.0])
O4 = np.array([L1, 0.0])


def solve_fourbar(theta2):
    """Solve coupler joint position using circle intersection."""

    # crank end
    A = O2 + L2*np.array([np.cos(theta2), np.sin(theta2)])

    # circle intersection (A radius L3, O4 radius L4)
    dx = O4[0]-A[0]
    dy = O4[1]-A[1]
    d = np.sqrt(dx*dx + dy*dy)

    a = (L3**2 - L4**2 + d**2)/(2*d)
    h = np.sqrt(max(L3**2 - a**2, 0))

    xm = A[0] + a*dx/d
    ym = A[1] + a*dy/d

    rx = -dy*(h/d)
    ry = dx*(h/d)

    B = np.array([xm+rx, ym+ry])

    return A, B


# --- plotting
fig, ax = plt.subplots()
ax.set_aspect('equal')
ax.set_xlim(-5,7)
ax.set_ylim(-5,5)

line, = ax.plot([], [], 'o-', lw=3)

def update(frame):

    theta2 = np.radians(frame)

    A,B = solve_fourbar(theta2)

    x = [O2[0], A[0], B[0], O4[0]]
    y = [O2[1], A[1], B[1], O4[1]]

    line.set_data(x,y)

    return line,

ani = FuncAnimation(fig, update, frames=np.arange(0,360,2), interval=30)

plt.show()