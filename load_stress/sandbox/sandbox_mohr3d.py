#!/usr/bin/env python3
"""
sandbox_mohr3d.py

CLI sandbox for 3D stress-state calculations and Mohr-circle plotting.

This sandbox includes:
- automatic plot persistence in the same directory as this script
- a polished plane-stress dashboard with cleaner mathematical notation
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
        help=(
            "Optional arbitrary in-plane rotation angle φ in degrees, positive ccw "
            "from x to x'. Plane-stress mode only."
        ),
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


def _vec(angle_deg: float) -> np.ndarray:
    ang = math.radians(angle_deg)
    return np.array([math.cos(ang), math.sin(ang)], dtype=float)


def draw_rotated_square(ax: plt.Axes, center: tuple[float, float], size: float, angle_deg: float) -> None:
    lower_left = (center[0] - size / 2.0, center[1] - size / 2.0)
    rect = patches.Rectangle(
        lower_left,
        size,
        size,
        angle=angle_deg,
        rotation_point=center,
        fill=False,
        linewidth=2.0,
        edgecolor="black",
    )
    ax.add_patch(rect)


def draw_arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    lw: float = 1.7,
) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(arrowstyle="->", linewidth=lw, shrinkA=0.0, shrinkB=0.0),
    )


def add_axes_marker(ax: plt.Axes) -> None:
    draw_arrow(ax, (0.0, 0.0), (1.75, 0.0), lw=1.8)
    draw_arrow(ax, (0.0, 0.0), (0.0, 1.75), lw=1.8)
    ax.text(1.92, -0.06, r"$x$", fontsize=10)
    ax.text(-0.08, 1.92, r"$y$", fontsize=10)


def _stress_value_text(value: float) -> str:
    return f"{value:.3f}"


def _math_label_for_component(kind: str, notation_prime: bool) -> str:
    if kind == "sigx":
        return r"$\sigma_{x'}$" if notation_prime else r"$\sigma_x$"
    if kind == "sigy":
        return r"$\sigma_{y'}$" if notation_prime else r"$\sigma_y$"
    if kind == "tau":
        return r"$\tau_{x'y'}$" if notation_prime else r"$\tau_{xy}$"
    raise ValueError(f"Unsupported label kind: {kind}")


def _label_box(
    ax: plt.Axes,
    x: float,
    y: float,
    text: str,
    fontsize: int = 10,
    ha: str = "left",
    va: str = "center",
) -> None:
    ax.text(
        x,
        y,
        text,
        fontsize=fontsize,
        ha=ha,
        va=va,
        bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="0.80", alpha=0.96),
    )


def draw_stress_element_generic(
    ax: plt.Axes,
    *,
    title: str,
    angle_deg: float,
    sigma_x: float,
    sigma_y: float,
    tau_xy: float,
    subtitle_lines: list[str],
    notation_prime: bool = False,
) -> None:
    ax.set_title(title, fontsize=12, pad=8, fontweight="bold")
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    draw_rotated_square(ax, center=(0.0, 0.0), size=1.8, angle_deg=angle_deg)
    add_axes_marker(ax)

    ex = _vec(angle_deg)
    ey = _vec(angle_deg + 90.0)
    h = 0.9
    normal_len = 0.48
    shear_len = 0.42

    face_centers = {
        "+x": h * ex,
        "-x": -h * ex,
        "+y": h * ey,
        "-y": -h * ey,
    }

    sign_x = 1.0 if sigma_x >= 0.0 else -1.0
    sign_y = 1.0 if sigma_y >= 0.0 else -1.0

    draw_arrow(ax, tuple(face_centers["+x"]), tuple(face_centers["+x"] + sign_x * normal_len * ex))
    draw_arrow(ax, tuple(face_centers["-x"]), tuple(face_centers["-x"] - sign_x * normal_len * ex))
    draw_arrow(ax, tuple(face_centers["+y"]), tuple(face_centers["+y"] + sign_y * normal_len * ey))
    draw_arrow(ax, tuple(face_centers["-y"]), tuple(face_centers["-y"] - sign_y * normal_len * ey))

    if abs(tau_xy) > 1e-12:
        sign_tau = 1.0 if tau_xy >= 0.0 else -1.0
        draw_arrow(ax, tuple(face_centers["+x"]), tuple(face_centers["+x"] + sign_tau * shear_len * ey))
        draw_arrow(ax, tuple(face_centers["-x"]), tuple(face_centers["-x"] - sign_tau * shear_len * ey))
        draw_arrow(ax, tuple(face_centers["+y"]), tuple(face_centers["+y"] + sign_tau * shear_len * ex))
        draw_arrow(ax, tuple(face_centers["-y"]), tuple(face_centers["-y"] - sign_tau * shear_len * ex))

    sigx_name = _math_label_for_component("sigx", notation_prime)
    sigy_name = _math_label_for_component("sigy", notation_prime)
    tauxy_name = _math_label_for_component("tau", notation_prime)

    # Representative face labels only: cleaner and less busy.
    _label_box(
        ax,
        *(1.03 * face_centers["+x"] + np.array([0.32, 0.12])),
        f"{sigx_name} = {_stress_value_text(sigma_x)}",
    )
    _label_box(
        ax,
        *(1.03 * face_centers["+y"] + np.array([0.08, 0.32])),
        f"{sigy_name} = {_stress_value_text(sigma_y)}",
    )

    shear_text = f"{tauxy_name} = {_stress_value_text(tau_xy)}" if abs(tau_xy) > 1e-12 else f"{tauxy_name} = 0"
    _label_box(ax, -2.10, 1.40, shear_text)

    if abs(angle_deg) > 1e-12:
        arc = patches.Arc((0.0, 0.0), 0.95, 0.95, theta1=0.0, theta2=angle_deg, linewidth=1.0)
        ax.add_patch(arc)
        ang_mid = math.radians(0.5 * angle_deg)
        ax.text(0.62 * math.cos(ang_mid), 0.62 * math.sin(ang_mid) + 0.04, r"$\theta$", fontsize=10)

    base_y = -2.07
    for i, line in enumerate(subtitle_lines):
        ax.text(0.52, base_y - 0.24 * i, line, fontsize=10)

    ax.set_xlim(-2.35, 2.55)
    ax.set_ylim(-2.35, 2.25)


def draw_input_element(ax: plt.Axes, sxx: float, syy: float, txy: float) -> None:
    draw_stress_element_generic(
        ax,
        title="Input stress element",
        angle_deg=0.0,
        sigma_x=sxx,
        sigma_y=syy,
        tau_xy=txy,
        subtitle_lines=[],
    )


def draw_principal_element(ax: plt.Axes, plane: PlaneStressResults) -> None:
    draw_stress_element_generic(
        ax,
        title="Principal stress element",
        angle_deg=plane.theta_p_deg_ccw,
        sigma_x=plane.sigma1,
        sigma_y=plane.sigma2,
        tau_xy=0.0,
        subtitle_lines=[
            rf"$\theta_p = {plane.theta_p_deg_ccw:.2f}^\circ$ ccw",
            rf"$\sigma_1 = {plane.sigma1:.3f}$",
            rf"$\sigma_2 = {plane.sigma2:.3f}$",
            r"$\tau = 0$",
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
        subtitle_lines=[
            rf"$\theta_s = {plane.theta_s_deg_ccw:.2f}^\circ$ ccw",
            rf"$\sigma_{{avg}} = {plane.sigma_avg:.3f}$",
            rf"$\tau_{{max}} = {plane.tau_max_in_plane:.3f}$",
            "equal normal stress on all faces",
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
        subtitle_lines=[
            rf"$\phi = {rotated.phi_deg_ccw:.2f}^\circ$ ccw",
            rf"$\sigma_{{x'}} = {rotated.sigma_x_prime:.3f}$",
            rf"$\sigma_{{y'}} = {rotated.sigma_y_prime:.3f}$",
            rf"$\tau_{{x'y'}} = {rotated.tau_x_prime_y_prime:.3f}$",
        ],
        notation_prime=True,
    )


def annotate_angle_arc(
    ax: plt.Axes,
    center: tuple[float, float],
    radius: float,
    theta1_deg: float,
    theta2_deg: float,
    text: str,
    *,
    linestyle: str = "-",
    color: str = "0.25",
    text_radius_scale: float = 1.10,
    linewidth: float = 1.15,
) -> None:
    arc = patches.Arc(
        center,
        2 * radius,
        2 * radius,
        angle=0,
        theta1=theta1_deg,
        theta2=theta2_deg,
        linewidth=linewidth,
        linestyle=linestyle,
        color=color,
    )
    ax.add_patch(arc)
    theta_mid = math.radians(0.5 * (theta1_deg + theta2_deg))
    tx = center[0] + text_radius_scale * radius * math.cos(theta_mid)
    ty = center[1] + text_radius_scale * radius * math.sin(theta_mid)
    _label_box(ax, tx, ty, text, fontsize=9)


def draw_results_panel(
    ax: plt.Axes,
    plane: PlaneStressResults,
    rotated: Optional[RotatedPlaneStressResults],
) -> None:
    ax.axis("off")
    ax.set_title("Results summary", fontsize=12, pad=8, fontweight="bold")

    def section(y_top: float, title: str, rows: list[tuple[str, str]], *, fc: str) -> float:
        row_h = 0.075
        header_h = 0.085
        total_h = header_h + row_h * len(rows) + 0.03
        rect = patches.FancyBboxPatch(
            (0.02, y_top - total_h),
            0.96,
            total_h,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            facecolor=fc,
            edgecolor="0.80",
            linewidth=1.0,
            transform=ax.transAxes,
        )
        ax.add_patch(rect)
        ax.text(0.05, y_top - 0.035, title, fontsize=10.5, fontweight="bold", transform=ax.transAxes, va="top")
        y = y_top - header_h
        for label, value in rows:
            ax.text(0.07, y, label, fontsize=10, fontweight="bold", transform=ax.transAxes, va="top")
            ax.text(0.56, y, value, fontsize=10, transform=ax.transAxes, va="top")
            y -= row_h
        return y_top - total_h - 0.035

    y = 0.97
    y = section(
        y,
        "Base solution",
        [
            (r"$\sigma_{avg}$", f"{plane.sigma_avg:.3f}"),
            ("Radius", f"{plane.radius:.3f}"),
        ],
        fc="#f6f8fb",
    )
    y = section(
        y,
        "Principal / shear",
        [
            (r"$\sigma_1$", f"{plane.sigma1:.3f}"),
            (r"$\sigma_2$", f"{plane.sigma2:.3f}"),
            (r"$\tau_{max}$", f"{plane.tau_max_in_plane:.3f}"),
            (r"$\theta_p$", f"{plane.theta_p_deg_ccw:.2f}° ccw"),
            (r"$\theta_s$", f"{plane.theta_s_deg_ccw:.2f}° ccw"),
        ],
        fc="#fbfbfb",
    )
    if rotated is not None:
        y = section(
            y,
            "Optional " + r"$\phi$" + " mode",
            [
                (r"$\phi$", f"{rotated.phi_deg_ccw:.2f}° ccw"),
                (r"$\sigma_{x'}$", f"{rotated.sigma_x_prime:.3f}"),
                (r"$\sigma_{y'}$", f"{rotated.sigma_y_prime:.3f}"),
                (r"$\tau_{x'y'}$", f"{rotated.tau_x_prime_y_prime:.3f}"),
            ],
            fc="#f8f7fd",
        )


def _value_or_integer(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}"
    return f"{value:.3f}"


def plot_plane_stress_dashboard(
    stress: np.ndarray,
    plane: PlaneStressResults,
    rotated: Optional[RotatedPlaneStressResults],
    outfile: Path,
    show_plot: bool,
) -> None:
    sxx = float(stress[0, 0])
    syy = float(stress[1, 1])

    fig = plt.figure(figsize=(17, 10))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.0, 1.45, 1.0], height_ratios=[1.0, 1.0])
    ax_input = fig.add_subplot(gs[0, 0])
    ax_mohr = fig.add_subplot(gs[0, 1])
    ax_right_top = fig.add_subplot(gs[0, 2])
    ax_principal = fig.add_subplot(gs[1, 0])
    ax_shear = fig.add_subplot(gs[1, 1])
    ax_results = fig.add_subplot(gs[1, 2])

    draw_input_element(ax_input, sxx=float(stress[0, 0]), syy=float(stress[1, 1]), txy=float(stress[0, 1]))
    draw_principal_element(ax_principal, plane)
    draw_max_shear_element(ax_shear, plane)
    if rotated is not None:
        draw_arbitrary_angle_element(ax_right_top, rotated)
    else:
        ax_right_top.axis("off")
        ax_right_top.set_title("Optional arbitrary-angle mode", fontsize=12, pad=8, fontweight="bold")
        ax_right_top.text(
            0.04,
            0.92,
            "Pass --phi-deg <value> to add:",
            fontsize=11.5,
            va="top",
            fontweight="bold",
        )
        bullet_lines = [
            r"transformed stresses $\sigma_{x'}$ and $\sigma_{y'}$",
            r"transformed shear $\tau_{x'y'}$",
            r"the point pair $P_\phi$ and $Q_\phi$ on Mohr's circle",
            r"the rotated stress-element sketch",
        ]
        for i, line in enumerate(bullet_lines):
            ax_right_top.text(0.08, 0.80 - i * 0.13, u"\u2022 " + line, fontsize=10.8, va="top")

    draw_results_panel(ax_results, plane, rotated)

    ax_mohr.set_title("Plane-stress Mohr circle", fontsize=12, pad=8, fontweight="bold")
    ax_mohr.set_aspect("equal", adjustable="box")
    theta = np.linspace(0.0, 2.0 * np.pi, 800)
    x = plane.sigma_avg + plane.radius * np.cos(theta)
    y = plane.radius * np.sin(theta)
    ax_mohr.plot(x, y, linewidth=2.3, color="black")

    A = plane.point_x
    B = plane.point_y
    C = (plane.sigma_avg, 0.0)
    P1 = (plane.sigma1, 0.0)
    P2 = (plane.sigma2, 0.0)

    ax_mohr.axhline(0.0, linewidth=1.0, color="black")
    ax_mohr.axvline(0.0, linewidth=1.0, color="black")
    ax_mohr.grid(True, alpha=0.28)
    ax_mohr.set_xlabel(r"Normal stress, $\sigma$", fontsize=11)
    ax_mohr.set_ylabel(r"Shear stress, $\tau$", fontsize=11)

    # Helper construction lines with restrained color coding.
    ax_mohr.plot([C[0], A[0]], [C[1], A[1]], linewidth=1.2, color="tab:blue", linestyle="--", alpha=0.85)
    ax_mohr.plot([C[0], B[0]], [C[1], B[1]], linewidth=1.2, color="tab:orange", linestyle="--", alpha=0.85)
    ax_mohr.plot([A[0], A[0]], [0.0, A[1]], linewidth=0.95, color="tab:blue", linestyle=":", alpha=0.85)
    ax_mohr.plot([B[0], B[0]], [0.0, B[1]], linewidth=0.95, color="tab:orange", linestyle=":", alpha=0.85)
    ax_mohr.plot([C[0], C[0]], [-plane.radius, plane.radius], linewidth=0.95, color="0.45", linestyle="--", alpha=0.85)

    point_style = dict(marker="o", linestyle="None", markersize=5, color="black")
    for point in [A, B, C, P1, P2]:
        ax_mohr.plot(point[0], point[1], **point_style)

    ax_mohr.annotate("A", xy=A, xytext=(5, 5), textcoords="offset points", fontsize=10)
    ax_mohr.annotate("B", xy=B, xytext=(5, -14), textcoords="offset points", fontsize=10)
    ax_mohr.annotate("C", xy=C, xytext=(6, 6), textcoords="offset points", fontsize=10)

    ax_mohr.annotate(r"$\sigma_1$", xy=P1, xytext=(8, -16), textcoords="offset points", fontsize=10)
    ax_mohr.annotate(r"$\sigma_2$", xy=P2, xytext=(-16, -16), textcoords="offset points", fontsize=10)

    _label_box(ax_mohr, C[0], -0.16 * max(plane.radius, 1.0), rf"$\sigma_{{avg}} = {plane.sigma_avg:.3f}$", ha="center")
    _label_box(ax_mohr, A[0] + 0.04 * max(plane.radius, 1.0), 0.12 * max(plane.radius, 1.0), rf"$\sigma_x = {_value_or_integer(sxx)}$", fontsize=9)
    _label_box(ax_mohr, B[0] + 0.04 * max(plane.radius, 1.0), 0.20 * plane.radius, rf"$\sigma_y = {_value_or_integer(syy)}$", fontsize=9)

    # Clean point coordinate notes only for the original state.
    _label_box(ax_mohr, A[0] + 0.12 * max(plane.radius, 1.0), A[1] + 0.10 * max(plane.radius, 1.0), rf"$A(\sigma_x,\,-\tau_{{xy}})$", fontsize=9)
    _label_box(ax_mohr, B[0] - 0.15 * max(plane.radius, 1.0), B[1] - 0.12 * max(plane.radius, 1.0), rf"$B(\sigma_y,\,+\tau_{{xy}})$", fontsize=9, ha="right")

    angle_CA = math.degrees(math.atan2(A[1] - C[1], A[0] - C[0]))
    annotate_angle_arc(
        ax_mohr,
        center=C,
        radius=max(plane.radius * 0.18, 5.0),
        theta1_deg=0.0,
        theta2_deg=angle_CA,
        text=rf"$2\theta_p = {angle_CA:.2f}^\circ$",
        color="tab:blue",
    )

    if rotated is not None:
        Pphi = rotated.point_x_prime
        Qphi = rotated.point_y_prime
        ax_mohr.plot(Pphi[0], Pphi[1], marker="o", linestyle="None", markersize=6, color="tab:red")
        ax_mohr.plot(Qphi[0], Qphi[1], marker="o", linestyle="None", markersize=6, color="tab:purple")
        ax_mohr.annotate(r"$P_\phi$", xy=Pphi, xytext=(5, 7), textcoords="offset points", fontsize=10, color="tab:red")
        ax_mohr.annotate(r"$Q_\phi$", xy=Qphi, xytext=(5, -15), textcoords="offset points", fontsize=10, color="tab:purple")
        ax_mohr.plot([C[0], Pphi[0]], [C[1], Pphi[1]], linestyle="--", linewidth=1.2, color="tab:red", alpha=0.9)
        angle_CP = math.degrees(math.atan2(Pphi[1] - C[1], Pphi[0] - C[0]))
        annotate_angle_arc(
            ax_mohr,
            center=C,
            radius=max(plane.radius * 0.30, 8.0),
            theta1_deg=angle_CA,
            theta2_deg=angle_CP,
            text=rf"$2\phi = {2.0 * rotated.phi_deg_ccw:.2f}^\circ$",
            color="tab:red",
            linestyle="--",
            text_radius_scale=1.18,
        )

    pad_x = max(10.0, 0.18 * max(abs(plane.sigma1), abs(plane.sigma2), abs(sxx), abs(syy), 1.0))
    pad_y = max(8.0, 0.18 * plane.radius)
    xmin = min(plane.sigma2, A[0], B[0], 0.0) - pad_x
    xmax = max(plane.sigma1, A[0], B[0], 0.0) + pad_x
    ymin = -plane.radius - pad_y
    ymax = plane.radius + pad_y
    ax_mohr.set_xlim(xmin, xmax)
    ax_mohr.set_ylim(ymin, ymax)

    fig.suptitle("Mohr circle dashboard", fontsize=20, fontweight="bold")
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
        ax.plot(x, y, linewidth=2.0, label=f'{circle["label"]}: c={c:.3f}, r={r:.3f}')

    sigma1, sigma2, sigma3 = principal
    ax.scatter([sigma1, sigma2, sigma3], [0.0, 0.0, 0.0], marker="o", label="Principal stresses")
    ax.axhline(0.0, linewidth=1.0, color="black")
    ax.axvline(0.0, linewidth=1.0, color="black")
    ax.set_xlabel(r"Normal stress, $\sigma$")
    ax.set_ylabel(r"Shear stress, $\tau$")
    ax.set_title("3D Mohr circles", fontweight="bold")
    ax.grid(True, alpha=0.45)
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

    outfile = resolve_plot_path(args.save_plot)
    if plane is not None:
        plot_plane_stress_dashboard(stress, plane, rotated=rotated, outfile=outfile, show_plot=args.show_plot)
    else:
        plot_mohr_3d(results.principal_stresses, outfile=outfile, show_plot=args.show_plot)


if __name__ == "__main__":
    main()
