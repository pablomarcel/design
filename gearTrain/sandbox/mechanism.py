import sympy as sp
import sympy.physics.mechanics as me
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# dynamic variables
q1, q2 = me.dynamicsymbols('q1 q2')
u1, u2 = me.dynamicsymbols('u1 u2')

# constants
l, m, g = sp.symbols('l m g')

# reference frame
N = me.ReferenceFrame('N')

# rotating frames
A = N.orientnew('A', 'Axis', [q1, N.z])
B = A.orientnew('B', 'Axis', [q2, N.z])

# points
O = me.Point('O')
P = O.locatenew('P', l*A.x)
Q = P.locatenew('Q', l*B.x)

# velocities
O.set_vel(N, 0)
P.v2pt_theory(O, N, A)
Q.v2pt_theory(P, N, B)

# particles
Pa = me.Particle('Pa', P, m)
Pb = me.Particle('Pb', Q, m)

# forces
forces = [(P, -m*g*N.y), (Q, -m*g*N.y)]

# kinematic equations
kd = [q1.diff() - u1, q2.diff() - u2]

# Kane's method
KM = me.KanesMethod(N, q_ind=[q1, q2], u_ind=[u1, u2], kd_eqs=kd)

fr, frstar = KM.kanes_equations([Pa, Pb], forces)

rhs = KM.rhs()

# numeric function
params = {l:1.0, m:1.0, g:9.81}
rhs_func = sp.lambdify((me.dynamicsymbols._t, [q1,q2,u1,u2]),
                       rhs.subs(params))

# integrate
dt = 0.02
steps = 500
state = np.array([0.5, 1.0, 0, 0])
states = []

for i in range(steps):
    states.append(state.copy())
    state = state + dt*np.array(rhs_func(0,state)).astype(float).flatten()

states = np.array(states)

# animation
fig, ax = plt.subplots()
ax.set_xlim(-2,2)
ax.set_ylim(-2,2)
ax.set_aspect('equal')

line, = ax.plot([],[],'o-',lw=2)

def update(i):

    q1,q2 = states[i,0], states[i,1]

    x1 = np.cos(q1)
    y1 = np.sin(q1)

    x2 = x1 + np.cos(q1+q2)
    y2 = y1 + np.sin(q1+q2)

    line.set_data([0,x1,x2],[0,y1,y2])

    return line,

ani = FuncAnimation(fig, update, frames=len(states), interval=20)

plt.show()