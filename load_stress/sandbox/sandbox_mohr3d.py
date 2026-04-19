#!/usr/bin/env python3
"""
sandbox_mohr3d.py

CLI sandbox for 3D stress-state calculations and Mohr-circle plotting.

This sandbox includes:
- automatic plot persistence in the same directory as this script
- richer plane-stress visualization inspired by Shigley's Figure 3-11
- principal-stress and maximum-shear stress-element sketches for plane stress
- optional arbitrary-angle stress transformation for plane stress via --phi-deg
- fallback 3D Mohr-circle plot for general 3D stress states

Notes
-----
- Sign convention: positive tension for normal stress.
- Tensor assumed symmetric.
- Notation follows Shigley-style component names:
      [ sxx  txy  txz ]
      [ txy  syy  tyz ]
      [ txz  tyz  szz ]
- Backward-compatible alias: --tzx is still accepted and mapped to --txz.
- For plane stress examples from Shigley, enter clockwise τxy as a negative value
  when using the standard tensor sign convention.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches


@dataclass
class StressResults:
    tensor: np.ndarray
    principal_stresses: np.ndarray
    mean_stress: float
    max_shear: float
    von_mises: float
    invariants: dict[str, float]


@dataclass
class PlaneStressResults:
    sigma_avg: float
    radius: float
    sigma1: float
    sigma2: float
    tau_max_in_plane: float
    theta_p_deg_ccw: float
    theta_s_deg_ccw: float
    point_x: tuple[float, float]
    point_y: tuple[float, float]


@dataclass
class RotatedPlaneStressResults:
    phi_deg_ccw: float
    sigma_x_prime: float
    sigma_y_prime: float
    tau_x_prime_y_prime: float
    point_x_prime: tuple[float, float]
    point_y_prime: tuple[float, float]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="3D stress tensor sandbox with Mohr-circle plotting."
    )
    parser.add_argument("--sxx", type=float, required=True, help="Normal stress σxx")
    parser.add_argument("--syy", type=float, required=True, help="Normal stress σyy")
    parser.add_argument("--szz", type=float, required=True, help="Normal stress σzz")
    parser.add_argument("--txy", type=float, default=0.0, help="Shear stress τxy")
    parser.add_argument("--tyz", type=float, default=0.0, help="Shear stress τyz")
    parser.add_argument(
        "--txz",
        "--tzx",
        dest="txz",
        type=float,
        default=0.0,
        help="Shear stress τxz (legacy alias --tzx also accepted)",
    )
    parser.add_argument(
        "--phi-deg",
        type=float,
        default=None,
        help="Optional arbitrary in-plane rotation angle φ in degrees, positive ccw from x to x'. Plane-stress mode only.",
    )
    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="Display the plot window.",
    )
    parser.add_argument(
        "--save-plot",
        type=str,
        default="",
        help="Optional file path for the generated plot.",
    )
    parser.add_argument(
        "--digits",
        type=int,
        default=6,
        help="Number of decimal places for text output.",
    )
    return parser


def script_directory() -> Path:
    return Path(__file__).resolve().parent


def default_plot_path() -> Path:
    return script_directory() / "sandbox_mohr3d_plot.png"


def resolve_plot_path(user_value: str) -> Path:
    if user_value:
        return Path(user_value).expanduser().resolve()
    return default_plot_path()


def make_stress_tensor(
    sxx: float,
    syy: float,
    szz: float,
    txy: float,
    tyz: float,
    txz: float,
) -> np.ndarray:
    return np.array(
        [
            [sxx, txy, txz],
            [txy, syy, tyz],
            [txz, tyz, szz],
        ],
        dtype=float,
    )


def compute_invariants(stress: np.ndarray) -> dict[str, float]:
    i1 = float(np.trace(stress))
    i2 = float(
        stress[0, 0] * stress[1, 1]
        + stress[1, 1] * stress[2, 2]
        + stress[2, 2] * stress[0, 0]
        - stress[0, 1] ** 2
        - stress[1, 2] ** 2
        - stress[0, 2] ** 2
    )
    i3 = float(np.linalg.det(stress))
    return {"I1": i1, "I2": i2, "I3": i3}


def compute_von_mises(stress: np.ndarray) -> float:
    sxx, syy, szz = stress[0, 0], stress[1, 1], stress[2, 2]
    txy, tyz, txz = stress[0, 1], stress[1, 2], stress[0, 2]
    vm = math.sqrt(
        0.5
        * (
            (sxx - syy) ** 2
            + (syy - szz) ** 2
            + (szz - sxx) ** 2
            + 6.0 * (txy**2 + tyz**2 + txz**2)
        )
    )
    return float(vm)


def analyze_stress(stress: np.ndarray) -> StressResults:
    eigenvalues, _ = np.linalg.eigh(stress)
    principal = np.sort(eigenvalues)[::-1]
    sigma1, _, sigma3 = principal

    return StressResults(
        tensor=stress,
        principal_stresses=principal,
        mean_stress=float(np.mean(principal)),
        max_shear=float((sigma1 - sigma3) / 2.0),
        von_mises=compute_von_mises(stress),
        invariants=compute_invariants(stress),
    )


def is_plane_stress_case(stress: np.ndarray, tol: float = 1e-12) -> bool:
    return (
        abs(stress[2, 2]) <= tol
        and abs(stress[1, 2]) <= tol
        and abs(stress[0, 2]) <= tol
    )


def analyze_plane_stress(stress: np.ndarray) -> PlaneStressResults:
    sxx = float(stress[0, 0])
    syy = float(stress[1, 1])
    txy = float(stress[0, 1])

    sigma_avg = 0.5 * (sxx + syy)
    radius = math.sqrt((0.5 * (sxx - syy)) ** 2 + txy**2)
    sigma1 = sigma_avg + radius
    sigma2 = sigma_avg - radius
    tau_max = radius

    theta_p_rad = 0.5 * math.atan2(2.0 * txy, sxx - syy)
    theta_s_rad = theta_p_rad + math.pi / 4.0

    point_x = (sxx, -txy)
    point_y = (syy, txy)

    return PlaneStressResults(
        sigma_avg=sigma_avg,
        radius=radius,
        sigma1=sigma1,
        sigma2=sigma2,
        tau_max_in_plane=tau_max,
        theta_p_deg_ccw=math.degrees(theta_p_rad),
        theta_s_deg_ccw=math.degrees(theta_s_rad),
        point_x=point_x,
        point_y=point_y,
    )


def analyze_rotated_plane_stress(stress: np.ndarray, phi_deg_ccw: float) -> RotatedPlaneStressResults:
    sxx = float(stress[0, 0])
    syy = float(stress[1, 1])
    txy = float(stress[0, 1])

    phi_rad = math.radians(phi_deg_ccw)
    c2 = math.cos(2.0 * phi_rad)
    s2 = math.sin(2.0 * phi_rad)
    avg = 0.5 * (sxx + syy)
    half_diff = 0.5 * (sxx - syy)

    sigma_x_prime = avg + half_diff * c2 + txy * s2
    sigma_y_prime = avg - half_diff * c2 - txy * s2
    tau_x_prime_y_prime = -half_diff * s2 + txy * c2

    point_x_prime = (sigma_x_prime, -tau_x_prime_y_prime)
    point_y_prime = (sigma_y_prime, tau_x_prime_y_prime)

    return RotatedPlaneStressResults(
        phi_deg_ccw=phi_deg_ccw,
        sigma_x_prime=sigma_x_prime,
        sigma_y_prime=sigma_y_prime,
        tau_x_prime_y_prime=tau_x_prime_y_prime,
        point_x_prime=point_x_prime,
        point_y_prime=point_y_prime,
    )


def mohr_circle_data(principal: np.ndarray) -> list[dict[str, float]]:
    sigma1, sigma2, sigma3 = principal
    pairs = [
        ("(σ1, σ2)", sigma1, sigma2),
        ("(σ2, σ3)", sigma2, sigma3),
        ("(σ1, σ3)", sigma1, sigma3),
    ]
    circles = []
    for label, a, b in pairs:
        circles.append(
            {
                "label": label,
                "center": 0.5 * (a + b),
                "radius": 0.5 * abs(a - b),
                "sigma_a": a,
                "sigma_b": b,
            }
        )
    return circles


def draw_rotated_square(ax: plt.Axes, center: tuple[float, float], size: float, angle_deg: float) -> None:
    lower_left = (center[0] - size / 2.0, center[1] - size / 2.0)
    rect = patches.Rectangle(
        lower_left,
        size,
        size,
        angle=angle_deg,
        rotation_point=center,
        fill=False,
        linewidth=1.8,
    )
    ax.add_patch(rect)


def draw_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], lw: float = 1.5) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(arrowstyle="->", linewidth=lw),
    )


def _vec(angle_deg: float) -> np.ndarray:
    ang = math.radians(angle_deg)
    return np.array([math.cos(ang), math.sin(ang)], dtype=float)


def draw_stress_element_generic(
    ax: plt.Axes,
    *,
    title: str,
    angle_deg: float,
    sigma_x: float,
    sigma_y: float,
    tau_xy: float,
    footer_lines: list[str],
    extra_text: Optional[list[tuple[float, float, str]]] = None,
) -> None:
    ax.set_title(title)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    draw_rotated_square(ax, center=(0.0, 0.0), size=1.8, angle_deg=angle_deg)

    draw_arrow(ax, (0.0, 0.0), (1.8, 0.0))
    draw_arrow(ax, (0.0, 0.0), (0.0, 1.8))
    ax.text(1.95, -0.05, "x", fontsize=10)
    ax.text(-0.08, 1.95, "y", fontsize=10)

    ex = _vec(angle_deg)
    ey = _vec(angle_deg + 90.0)
    h = 0.9
    normal_len = 0.55
    shear_len = 0.55

    face_centers = {
        "+x": h * ex,
        "-x": -h * ex,
        "+y": h * ey,
        "-y": -h * ey,
    }

    # Normal stress arrows.
    sign_x = 1.0 if sigma_x >= 0.0 else -1.0
    sign_y = 1.0 if sigma_y >= 0.0 else -1.0
    draw_arrow(ax, tuple(face_centers["+x"]), tuple(face_centers["+x"] + sign_x * normal_len * ex))
    draw_arrow(ax, tuple(face_centers["-x"]), tuple(face_centers["-x"] - sign_x * normal_len * ex))
    draw_arrow(ax, tuple(face_centers["+y"]), tuple(face_centers["+y"] + sign_y * normal_len * ey))
    draw_arrow(ax, tuple(face_centers["-y"]), tuple(face_centers["-y"] - sign_y * normal_len * ey))

    # Shear stress arrows in standard tensor sign convention.
    sign_tau = 1.0 if tau_xy >= 0.0 else -1.0
    draw_arrow(ax, tuple(face_centers["+x"]), tuple(face_centers["+x"] + sign_tau * shear_len * ey))
    draw_arrow(ax, tuple(face_centers["-x"]), tuple(face_centers["-x"] - sign_tau * shear_len * ey))
    draw_arrow(ax, tuple(face_centers["+y"]), tuple(face_centers["+y"] + sign_tau * shear_len * ex))
    draw_arrow(ax, tuple(face_centers["-y"]), tuple(face_centers["-y"] - sign_tau * shear_len * ex))

    # Labels.
    ax.text(*(1.02 * face_centers["+x"] + np.array([0.35, 0.15])), f"σx={sigma_x:.3f}")
    ax.text(*(-1.12 * face_centers["+x"] + np.array([-0.15, 0.15])), f"σx={sigma_x:.3f}")
    ax.text(*(1.00 * face_centers["+y"] + np.array([0.12, 0.28])), f"σy={sigma_y:.3f}")
    ax.text(*(-1.00 * face_centers["+y"] + np.array([0.12, -0.40])), f"σy={sigma_y:.3f}")
    ax.text(-2.1, 1.45, f"τxy={tau_xy:.3f}")

    if extra_text:
        for x, y, txt in extra_text:
            ax.text(x, y, txt)

    base_y = -2.1
    for i, line in enumerate(footer_lines):
        ax.text(0.65, base_y - 0.28 * i, line)

    ax.set_xlim(-2.4, 2.6)
    ax.set_ylim(-2.45, 2.3)


def draw_input_element(ax: plt.Axes, sxx: float, syy: float, txy: float) -> None:
    draw_stress_element_generic(
        ax,
        title="Input stress element",
        angle_deg=0.0,
        sigma_x=sxx,
        sigma_y=syy,
        tau_xy=txy,
        footer_lines=[],
        extra_text=None,
    )


def draw_principal_element(ax: plt.Axes, plane: PlaneStressResults) -> None:
    draw_stress_element_generic(
        ax,
        title="Principal stress element",
        angle_deg=plane.theta_p_deg_ccw,
        sigma_x=plane.sigma1,
        sigma_y=plane.sigma2,
        tau_xy=0.0,
        footer_lines=[
            f"θp={plane.theta_p_deg_ccw:.2f}° ccw",
            f"σ1={plane.sigma1:.3f}",
            f"σ2={plane.sigma2:.3f}",
        ],
    )


def draw_max_shear_element(ax: plt.Axes, plane: PlaneStressResults) -> None:
    draw_stress_element_generic(
        ax,
        title="Maximum in-plane shear element",
        angle_deg=plane.theta_s_deg_ccw,
        sigma_x=plane.sigma_avg,
        sigma_y=plane.sigma_avg,
        tau_xy=plane.tau_max_in_plane,
        footer_lines=[
            f"θs={plane.theta_s_deg_ccw:.2f}° ccw",
            f"σ={plane.sigma_avg:.3f}",
            f"τmax={plane.tau_max_in_plane:.3f}",
        ],
    )


def draw_arbitrary_angle_element(ax: plt.Axes, rotated: RotatedPlaneStressResults) -> None:
    draw_stress_element_generic(
        ax,
        title="Arbitrary-angle stress element",
        angle_deg=rotated.phi_deg_ccw,
        sigma_x=rotated.sigma_x_prime,
        sigma_y=rotated.sigma_y_prime,
        tau_xy=rotated.tau_x_prime_y_prime,
        footer_lines=[
            f"φ={rotated.phi_deg_ccw:.2f}° ccw",
            f"σx'={rotated.sigma_x_prime:.3f}",
            f"σy'={rotated.sigma_y_prime:.3f}",
            f"τx'y'={rotated.tau_x_prime_y_prime:.3f}",
        ],
    )


def annotate_angle_arc(
    ax: plt.Axes,
    center: tuple[float, float],
    radius: float,
    theta1_deg: float,
    theta2_deg: float,
    text: str,
    text_radius_scale: float = 1.12,
) -> None:
    arc = patches.Arc(center, 2 * radius, 2 * radius, angle=0, theta1=theta1_deg, theta2=theta2_deg, linewidth=1.2)
    ax.add_patch(arc)
    theta_mid = math.radians(0.5 * (theta1_deg + theta2_deg))
    tx = center[0] + text_radius_scale * radius * math.cos(theta_mid)
    ty = center[1] + text_radius_scale * radius * math.sin(theta_mid)
    ax.text(tx, ty, text)


def plot_plane_stress_dashboard(
    stress: np.ndarray,
    plane: PlaneStressResults,
    rotated: Optional[RotatedPlaneStressResults],
    outfile: Path,
    show_plot: bool,
) -> None:
    sxx = float(stress[0, 0])
    syy = float(stress[1, 1])
    txy = float(stress[0, 1])

    if rotated is None:
        fig = plt.figure(figsize=(14, 10))
        gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.45], height_ratios=[1.0, 1.0])
        ax_input = fig.add_subplot(gs[0, 0])
        ax_mohr = fig.add_subplot(gs[0, 1])
        ax_principal = fig.add_subplot(gs[1, 0])
        ax_shear = fig.add_subplot(gs[1, 1])
        ax_rot = None
    else:
        fig = plt.figure(figsize=(17, 10))
        gs = fig.add_gridspec(2, 3, width_ratios=[1.0, 1.45, 1.0], height_ratios=[1.0, 1.0])
        ax_input = fig.add_subplot(gs[0, 0])
        ax_mohr = fig.add_subplot(gs[0, 1])
        ax_rot = fig.add_subplot(gs[0, 2])
        ax_principal = fig.add_subplot(gs[1, 0])
        ax_shear = fig.add_subplot(gs[1, 1])
        ax_blank = fig.add_subplot(gs[1, 2])
        ax_blank.axis("off")
        ax_blank.text(
            0.02,
            0.98,
            "Optional arbitrary-angle mode\n\n"
            "Reported values:\n"
            "• σx'\n"
            "• σy'\n"
            "• τx'y'\n\n"
            "Mohr-circle point pair:\n"
            "• Pφ = (σx', -τx'y')\n"
            "• Qφ = (σy',  τx'y')",
            va="top",
            fontsize=11,
        )

    draw_input_element(ax_input, sxx=sxx, syy=syy, txy=txy)
    draw_principal_element(ax_principal, plane)
    draw_max_shear_element(ax_shear, plane)
    if ax_rot is not None and rotated is not None:
        draw_arbitrary_angle_element(ax_rot, rotated)

    ax_mohr.set_title("Plane-stress Mohr circle")
    ax_mohr.set_aspect("equal", adjustable="box")
    theta = np.linspace(0.0, 2.0 * np.pi, 800)
    x = plane.sigma_avg + plane.radius * np.cos(theta)
    y = plane.radius * np.sin(theta)
    ax_mohr.plot(x, y, linewidth=2.0)

    A = plane.point_x
    B = plane.point_y
    C = (plane.sigma_avg, 0.0)
    D = (sxx, 0.0)
    E = (plane.sigma_avg, plane.radius)
    F = (plane.sigma_avg, -plane.radius)
    P1 = (plane.sigma1, 0.0)
    P2 = (plane.sigma2, 0.0)

    for label, point, dx, dy in [
        ("A", A, 2.0, 2.0),
        ("B", B, 2.0, -3.0),
        ("C", C, 1.5, 2.0),
        ("D", D, 1.5, -5.0),
        ("E", E, 1.5, 2.0),
        ("F", F, 1.5, -5.0),
    ]:
        ax_mohr.plot(point[0], point[1], "o")
        ax_mohr.annotate(label, xy=point, xytext=(dx, dy), textcoords="offset points")

    ax_mohr.plot([P1[0], P2[0]], [0.0, 0.0], "o")
    ax_mohr.annotate(f"σ1={plane.sigma1:.3f}", xy=P1, xytext=(6, -16), textcoords="offset points")
    ax_mohr.annotate(f"σ2={plane.sigma2:.3f}", xy=P2, xytext=(-6, -16), textcoords="offset points")
    ax_mohr.annotate(f"τmax={plane.tau_max_in_plane:.3f}", xy=E, xytext=(8, 12), textcoords="offset points")

    ax_mohr.axhline(0.0, linewidth=1.0)
    ax_mohr.axvline(0.0, linewidth=1.0)
    ax_mohr.plot([C[0], A[0]], [C[1], A[1]], linestyle="--", linewidth=1.1)
    ax_mohr.plot([C[0], B[0]], [C[1], B[1]], linestyle="--", linewidth=1.1)
    ax_mohr.plot([D[0], D[0]], [0.0, A[1]], linestyle="--", linewidth=0.9)
    ax_mohr.plot([C[0], C[0]], [F[1], E[1]], linestyle="--", linewidth=0.9)
    ax_mohr.plot([C[0], A[0]], [C[1], A[1]], linewidth=1.2)

    angle_CA = math.degrees(math.atan2(A[1] - C[1], A[0] - C[0]))
    annotate_angle_arc(
        ax_mohr,
        center=C,
        radius=max(plane.radius * 0.18, 5.0),
        theta1_deg=0.0,
        theta2_deg=angle_CA,
        text=f"2θp={angle_CA:.2f}°",
    )

    if rotated is not None:
        Pphi = rotated.point_x_prime
        Qphi = rotated.point_y_prime
        ax_mohr.plot(Pphi[0], Pphi[1], marker="o")
        ax_mohr.plot(Qphi[0], Qphi[1], marker="o")
        ax_mohr.annotate("Pφ", xy=Pphi, xytext=(6, 6), textcoords="offset points")
        ax_mohr.annotate("Qφ", xy=Qphi, xytext=(6, -14), textcoords="offset points")
        ax_mohr.plot([C[0], Pphi[0]], [C[1], Pphi[1]], linestyle=":", linewidth=1.3)
        angle_CP = math.degrees(math.atan2(Pphi[1] - C[1], Pphi[0] - C[0]))
        annotate_angle_arc(
            ax_mohr,
            center=C,
            radius=max(plane.radius * 0.30, 8.0),
            theta1_deg=angle_CA,
            theta2_deg=angle_CP,
            text=f"2φ={2.0 * rotated.phi_deg_ccw:.2f}°",
            text_radius_scale=1.22,
        )
        ax_mohr.annotate(
            f"σx'={rotated.sigma_x_prime:.3f}\nσy'={rotated.sigma_y_prime:.3f}\nτx'y'={rotated.tau_x_prime_y_prime:.3f}",
            xy=Pphi,
            xytext=(12, -48),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.7", alpha=0.9),
            fontsize=10,
        )

    ax_mohr.annotate(f"({A[0]:.3f}, {A[1]:.3f})", xy=A, xytext=(8, 8), textcoords="offset points")
    ax_mohr.annotate(f"({B[0]:.3f}, {B[1]:.3f})", xy=B, xytext=(-60, -18), textcoords="offset points")
    ax_mohr.text(C[0], -0.10 * plane.radius, f"σavg={plane.sigma_avg:.3f}", ha="center")

    pad_x = max(10.0, 0.18 * max(abs(plane.sigma1), abs(plane.sigma2), abs(sxx), abs(syy), 1.0))
    pad_y = max(8.0, 0.18 * plane.radius)
    xmin = min(plane.sigma2, A[0], B[0], 0.0) - pad_x
    xmax = max(plane.sigma1, A[0], B[0], 0.0) + pad_x
    ymin = -plane.radius - pad_y
    ymax = plane.radius + pad_y
    ax_mohr.set_xlim(xmin, xmax)
    ax_mohr.set_ylim(ymin, ymax)
    ax_mohr.grid(True)
    ax_mohr.set_xlabel("Normal stress, σ")
    ax_mohr.set_ylabel("Shear stress, τ")

    fig.suptitle("Mohr circle dashboard", fontsize=18)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=180, bbox_inches="tight")
    print(f"\nPlot saved to: {outfile}")
    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def plot_mohr_3d(principal: np.ndarray, outfile: Path, show_plot: bool) -> None:
    circles = mohr_circle_data(principal)
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.set_aspect("equal", adjustable="box")

    theta = np.linspace(0.0, 2.0 * np.pi, 800)
    for circle in circles:
        c = circle["center"]
        r = circle["radius"]
        x = c + r * np.cos(theta)
        y = r * np.sin(theta)
        ax.plot(x, y, label=f'{circle["label"]}: c={c:.3f}, r={r:.3f}')

    sigma1, sigma2, sigma3 = principal
    ax.scatter([sigma1, sigma2, sigma3], [0.0, 0.0, 0.0], marker="o", label="Principal stresses")
    ax.axhline(0.0, linewidth=1.0)
    ax.axvline(0.0, linewidth=1.0)
    ax.set_xlabel("Normal stress, σ")
    ax.set_ylabel("Shear stress, τ")
    ax.set_title("3D Mohr circles")
    ax.grid(True)
    ax.legend()

    all_sigmas = [sigma1, sigma2, sigma3]
    max_radius = max(c["radius"] for c in circles)
    pad_x = max(1.0, 0.15 * max(1.0, max(abs(v) for v in all_sigmas)))
    pad_y = max(1.0, 0.15 * max(1.0, max_radius))
    ax.set_xlim(min(all_sigmas) - pad_x, max(all_sigmas) + pad_x)
    ax.set_ylim(-max_radius - pad_y, max_radius + pad_y)

    fig.tight_layout()
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=180, bbox_inches="tight")
    print(f"\nPlot saved to: {outfile}")
    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def pretty_print(
    results: StressResults,
    digits: int,
    plane: Optional[PlaneStressResults],
    rotated: Optional[RotatedPlaneStressResults],
) -> None:
    p = results.principal_stresses
    inv = results.invariants
    fmt = f"{{:.{digits}f}}"

    print("\n3D STRESS TENSOR")
    print(results.tensor)

    print("\nPRINCIPAL STRESSES")
    print(f"σ1 = {fmt.format(p[0])}")
    print(f"σ2 = {fmt.format(p[1])}")
    print(f"σ3 = {fmt.format(p[2])}")

    print("\nDERIVED QUANTITIES")
    print(f"Mean stress          = {fmt.format(results.mean_stress)}")
    print(f"Max shear (Tresca)   = {fmt.format(results.max_shear)}")
    print(f"Von Mises stress     = {fmt.format(results.von_mises)}")

    print("\nSTRESS INVARIANTS")
    print(f"I1 = {fmt.format(inv['I1'])}")
    print(f"I2 = {fmt.format(inv['I2'])}")
    print(f"I3 = {fmt.format(inv['I3'])}")

    if plane is not None:
        print("\nPLANE-STRESS SUMMARY")
        print(f"σavg                = {fmt.format(plane.sigma_avg)}")
        print(f"Radius              = {fmt.format(plane.radius)}")
        print(f"In-plane σ1         = {fmt.format(plane.sigma1)}")
        print(f"In-plane σ2         = {fmt.format(plane.sigma2)}")
        print(f"In-plane τmax       = {fmt.format(plane.tau_max_in_plane)}")
        print(f"θp (ccw)            = {fmt.format(plane.theta_p_deg_ccw)} deg")
        print(f"θs (ccw)            = {fmt.format(plane.theta_s_deg_ccw)} deg")
        print("Note: for Shigley Example 3-4, θp is often discussed by magnitude and orientation on the element sketch.")

    if rotated is not None:
        print("\nARBITRARY-ANGLE SUMMARY")
        print(f"φ (ccw)             = {fmt.format(rotated.phi_deg_ccw)} deg")
        print(f"σ(phi)_x'           = {fmt.format(rotated.sigma_x_prime)}")
        print(f"σ(phi)_y'           = {fmt.format(rotated.sigma_y_prime)}")
        print(f"τ(phi)_x'y'         = {fmt.format(rotated.tau_x_prime_y_prime)}")
        print("Note: these values are computed with the standard plane-stress transformation equations.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    stress = make_stress_tensor(
        sxx=args.sxx,
        syy=args.syy,
        szz=args.szz,
        txy=args.txy,
        tyz=args.tyz,
        txz=args.txz,
    )

    results = analyze_stress(stress)
    plane = analyze_plane_stress(stress) if is_plane_stress_case(stress) else None
    rotated = None
    if args.phi_deg is not None:
        if plane is None:
            raise SystemExit("--phi-deg is only supported for plane-stress cases in this sandbox release.")
        rotated = analyze_rotated_plane_stress(stress, args.phi_deg)

    pretty_print(results, digits=args.digits, plane=plane, rotated=rotated)

    if args.show_plot or args.save_plot == "":
        outfile = resolve_plot_path(args.save_plot)
        if plane is not None:
            plot_plane_stress_dashboard(stress, plane, rotated=rotated, outfile=outfile, show_plot=args.show_plot)
        else:
            plot_mohr_3d(results.principal_stresses, outfile=outfile, show_plot=args.show_plot)


if __name__ == "__main__":
    main()
