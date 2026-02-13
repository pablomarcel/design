import numpy as np
import matplotlib.pyplot as plt
from mechanism import SpurGear


def manual_agma_math(torque_nm, module, teeth, face_width=15.0):
    """Core AGMA 2101-D04 Bending Stress calculation."""
    # Tangential Force (F_t)
    force_n = (torque_nm * 1000) / ((module * teeth) / 2)
    # Standard AGMA factors
    Ko, Kv, Ks, Km, J = 1.25, 1.2, 1.0, 1.3, 0.33
    # Stress calculation (MPa)
    return (force_n * Ko * Kv * Ks * Km) / (face_width * module * J)


# --- 1. CONFIG ---
torque, m, z, face_w = 50.0, 2.0, 20, 15.0
stress = manual_agma_math(torque, m, z, face_w)

print(f"--- AGMA Analysis ---")
print(f"Bending Stress: {stress:.2f} MPa")
print("STATUS: " + ("DANGER" if stress > 250 else "SAFE"))

# --- 2. THE VISUAL FIX ---
print(f"\n--- Generating Visualization ---")

# Standard AGMA geometry rules:
# Addendum = 1.0 * module | Dedendum = 1.25 * module
add = 1.0 * m
ded = 1.25 * m

try:
    # Based on your error, the library expects these to be defined.
    # We pass 'agma=True' to trigger the internal AGMA defaults,
    # OR we provide the addendum/dedendum directly.

    # Try the 'agma' flag first as it's the cleanest fix
    my_gear = SpurGear(z, m, agma=True)

except (AssertionError, TypeError):
    # If the flag fails, provide the manual dimensions it's asking for
    # Some versions use (teeth, module, addendum, dedendum)
    my_gear = SpurGear(z, m, add, ded)

# Rendering
try:
    my_gear.plot()
    plt.title(f"AGMA Spur Gear ({stress:.1f} MPa)")
    plt.axis('equal')
    plt.show()
except Exception as e:
    print(f"Plotting failed: {e}")
