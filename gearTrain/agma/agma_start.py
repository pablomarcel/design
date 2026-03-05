from mechanism import SpurGear
import matplotlib.pyplot as plt


def calculate_agma_bending(torque_nm, module, teeth, face_width_mm=10):
    """
    Simplified AGMA Bending Stress: sigma = (F_t * K_o * K_v * K_s * K_m) / (b * m * J)
    We'll use standard factors for a quick prototype.
    """
    # 1. Convert Torque to Tangential Force (F_t)
    radius_mm = (module * teeth) / 2
    force_n = (torque_nm * 1000) / radius_mm

    # 2. Simplified AGMA Factors (K)
    Ko = 1.25  # Overload factor (moderate shock)
    Kv = 1.2  # Dynamic factor (commercial quality)
    J = 0.3  # Geometry factor (standard for 20 teeth, 20° pressure angle)

    # 3. Calculate Stress (MPa)
    stress_mpa = (force_n * Ko * Kv) / (face_width_mm * module * J)
    return stress_mpa


# --- EXECUTION ---
torque = 50  # Nm
m = 2.0  # Module
z = 20  # Teeth

# Brain: Math
stress = calculate_agma_bending(torque, m, z)
print(f"Estimated AGMA Bending Stress: {stress:.2f} MPa")

# Eyes: Visuals (Mechanism library)
try:
    # Use phi for pressure angle in mechanism
    my_gear = SpurGear(module=m, teeth=z, phi=20)
    my_gear.plot()
    plt.title(f"AGMA Prototype: {stress:.1f} MPa Stress")
    plt.show()
except Exception as e:
    print(f"Visualization failed, but math is solid: {e}")
