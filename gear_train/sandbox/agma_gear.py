import numpy as np
import matplotlib.pyplot as plt
from mechanism import SpurGear

def agma_math(torque_nm, module, teeth, face_width=15.0):
    """Core AGMA 2101-D04 Calculation."""
    force_n = (torque_nm * 1000) / ((module * teeth) / 2)
    Ko, Kv, Ks, Km, J = 1.25, 1.2, 1.0, 1.3, 0.33
    return (force_n * Ko * Kv * Ks * Km) / (face_width * module * J)

# --- CONFIG (Bumped values to fix the Undercutting & Stress) ---
torque = 50.0
m = 3.0    # Increased from 2.0
z = 24     # Increased from 20
face_w = 20.0

stress = agma_math(torque, m, z, face_w)
print(f"--- AGMA Analysis ---")
print(f"Bending Stress: {stress:.2f} MPa")
print("STATUS: " + ("DANGER" if stress > 250 else "SAFE"))

# --- VISUALS ---
try:
    # Adding ignore_undercut=True just in case
    my_gear = SpurGear(z, m, agma=True, ignore_undercut=True)
    my_gear.plot()
    plt.title(f"AGMA Spur Gear ({stress:.1f} MPa)")
    plt.axis('equal')
    plt.show()
except Exception as e:
    print(f"Plot failed: {e}")
