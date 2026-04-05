import numpy as np
import matplotlib.pyplot as plt
from mechanism import SpurGear


class AGMAPrototyper:
    def __init__(self, teeth, module, b=15.0, phi=20):
        self.z = teeth
        self.m = module
        self.b = b  # Face width (mm)
        self.phi = phi  # Pressure angle (deg)
        self.d = module * teeth  # Pitch Diameter (mm)

    def calculate_stresses(self, torque_nm, rpm):
        """
        Analytical AGMA 2101-D04 Stress Math
        sigma_b: Bending Stress | sigma_c: Pitting (Contact) Stress
        """
        # 1. Tangential Force (F_t)
        Ft = (2000 * torque_nm) / self.d

        # 2. Factors (Analytical defaults for commercial steel gear_train)
        Ko, Kv, Ks, Km = 1.25, 1.2, 1.0, 1.3
        J = 0.33  # Bending Geometry Factor
        Cp = 191  # Elastic Coefficient (Steel on Steel)
        I = 0.10  # Surface Pitting Geometry Factor (Standard 20° Spur)

        # 3. Bending Stress (MPa)
        sigma_b = (Ft * Ko * Kv * Ks * Km) / (self.b * self.m * J)

        # 4. Pitting/Contact Stress (MPa)
        sigma_c = Cp * np.sqrt((Ft * Ko * Kv * Ks * Km) / (self.d * self.b * I))

        return {"bending": sigma_b, "pitting": sigma_c}


# --- RUNNING THE SCIENCE ---
# Define: 24 teeth, Module 3.0 (Makes it strong)
gear_model = AGMAPrototyper(teeth=24, module=3.0, b=20.0)
results = gear_model.calculate_stresses(torque_nm=50, rpm=1500)

print(f"--- AGMA ANALYTICAL RESULTS ---")
print(f"Bending Stress: {results['bending']:.2f} MPa")
print(f"Pitting Stress: {results['pitting']:.2f} MPa")

# STATUS CHECK
if results['bending'] < 250 and results['pitting'] < 1000:
    print("STATUS: DESIGN SAFE (AGMA Grade 1 Steel compliant)")
else:
    print("STATUS: DANGER (Exceeds material limits)")

# --- VISUALS (Using the one library that actually works) ---
try:
    vis = SpurGear(24, 3.0, agma=True, ignore_undercut=True)
    vis.plot()
    plt.title(f"AGMA Design: {results['bending']:.1f} MPa")
    plt.show()
except Exception as e:
    print(f"Vis error (ignore if math is enough): {e}")
