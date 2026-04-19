from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches

try:
    from .core import RotatedPlaneStressResults
except ImportError:
    from core import RotatedPlaneStressResults


def package_directory() -> Path:
    return Path(__file__).resolve().parent


def default_output_directory() -> Path:
    return package_directory() / "out"


def default_json_output_path(stem: str) -> Path:
    return default_output_directory() / f"{stem}.json"


def default_plot_output_path(stem: str) -> Path:
    return default_output_directory() / f"{stem}.png"


def _vec(angle_deg: float) -> np.ndarray:
    ang = math.radians(angle_deg)
    return np.array([math.cos(ang), math.sin(ang)], dtype=float)


def _value_or_integer(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}"
    return f"{value:.3f}"


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


def draw_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], lw: float = 1.7) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(arrowstyle="->", linewidth=lw, shrinkA=0.0, shrinkB=0.0),
    )


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

    _label_box(ax, *(1.03 * face_centers["+x"] + np.array([0.32, 0.12])), f"{sigx_name} = {_stress_value_text(sigma_x)}")
    _label_box(ax, *(1.03 * face_centers["+y"] + np.array([0.08, 0.32])), f"{sigy_name} = {_stress_value_text(sigma_y)}")
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


def render_dashboard(result: dict, outfile: Path, show_plot: bool = False) -> Path:
    if result.get("is_plane_stress"):
        _render_plane_stress_dashboard(result, outfile, show_plot)
    else:
        _render_mohr_3d(result, outfile, show_plot)
    return outfile


def _render_plane_stress_dashboard(result: dict, outfile: Path, show_plot: bool) -> None:
    stress = np.array(result["tensor"], dtype=float)
    plane = result["plane_stress"]
    rotated_dict = result.get("rotated_plane_stress")
    rotated = RotatedPlaneStressResults(
        phi_deg_ccw=rotated_dict["phi_deg_ccw"],
        sigma_x_prime=rotated_dict["sigma_x_prime"],
        sigma_y_prime=rotated_dict["sigma_y_prime"],
        tau_x_prime_y_prime=rotated_dict["tau_x_prime_y_prime"],
        point_x_prime=tuple(rotated_dict["point_x_prime"]),
        point_y_prime=tuple(rotated_dict["point_y_prime"]),
    ) if rotated_dict else None

    sxx = float(stress[0, 0])
    syy = float(stress[1, 1])
    txy = float(stress[0, 1])
    sigma_avg = plane["sigma_avg"]
    radius = plane["radius"]
    sigma1 = plane["sigma1"]
    sigma2 = plane["sigma2"]
    theta_p = plane["theta_p_deg_ccw"]
    theta_s = plane["theta_s_deg_ccw"]
    tau_max = plane["tau_max_in_plane"]
    A = tuple(plane["point_x"])
    B = tuple(plane["point_y"])
    C = (sigma_avg, 0.0)
    P1 = (sigma1, 0.0)
    P2 = (sigma2, 0.0)

    fig = plt.figure(figsize=(17, 10))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.0, 1.45, 1.0], height_ratios=[1.0, 1.0])
    ax_input = fig.add_subplot(gs[0, 0])
    ax_mohr = fig.add_subplot(gs[0, 1])
    ax_right_top = fig.add_subplot(gs[0, 2])
    ax_principal = fig.add_subplot(gs[1, 0])
    ax_shear = fig.add_subplot(gs[1, 1])
    ax_results = fig.add_subplot(gs[1, 2])

    draw_stress_element_generic(
        ax_input,
        title="Input stress element",
        angle_deg=0.0,
        sigma_x=sxx,
        sigma_y=syy,
        tau_xy=txy,
        subtitle_lines=[],
    )
    draw_stress_element_generic(
        ax_principal,
        title="Principal stress element",
        angle_deg=theta_p,
        sigma_x=sigma1,
        sigma_y=sigma2,
        tau_xy=0.0,
        subtitle_lines=[rf"$\theta_p = {theta_p:.2f}^\circ$ ccw", rf"$\sigma_1 = {sigma1:.3f}$", rf"$\sigma_2 = {sigma2:.3f}$", r"$\tau = 0$"],
    )
    draw_stress_element_generic(
        ax_shear,
        title="Maximum in-plane shear element",
        angle_deg=theta_s,
        sigma_x=sigma_avg,
        sigma_y=sigma_avg,
        tau_xy=tau_max,
        subtitle_lines=[rf"$\theta_s = {theta_s:.2f}^\circ$ ccw", rf"$\sigma_{{avg}} = {sigma_avg:.3f}$", rf"$\tau_{{max}} = {tau_max:.3f}$", "equal normal stress on all faces"],
    )

    if rotated is not None:
        draw_stress_element_generic(
            ax_right_top,
            title="Arbitrary-angle stress element",
            angle_deg=rotated.phi_deg_ccw,
            sigma_x=rotated.sigma_x_prime,
            sigma_y=rotated.sigma_y_prime,
            tau_xy=rotated.tau_x_prime_y_prime,
            subtitle_lines=[rf"$\phi = {rotated.phi_deg_ccw:.2f}^\circ$ ccw", rf"$\sigma_{{x'}} = {rotated.sigma_x_prime:.3f}$", rf"$\sigma_{{y'}} = {rotated.sigma_y_prime:.3f}$", rf"$\tau_{{x'y'}} = {rotated.tau_x_prime_y_prime:.3f}$"],
            notation_prime=True,
        )
    else:
        ax_right_top.axis("off")
        ax_right_top.set_title("Optional arbitrary-angle mode", fontsize=12, pad=8, fontweight="bold")
        ax_right_top.text(0.04, 0.92, "Pass --phi-deg <value> to add:", fontsize=11.5, va="top", fontweight="bold")
        bullet_lines = [
            r"transformed stresses $\sigma_{x'}$ and $\sigma_{y'}$",
            r"transformed shear $\tau_{x'y'}$",
            r"the point pair $P_\phi$ and $Q_\phi$ on Mohr's circle",
            r"the rotated stress-element sketch",
        ]
        for i, line in enumerate(bullet_lines):
            ax_right_top.text(0.08, 0.80 - i * 0.13, "• " + line, fontsize=10.8, va="top")

    ax_results.axis("off")
    ax_results.set_title("Results summary", fontsize=12, pad=8, fontweight="bold")
    rows = [
        (r"$\sigma_{avg}$", f"{sigma_avg:.3f}"),
        ("Radius", f"{radius:.3f}"),
        (r"$\sigma_1$", f"{sigma1:.3f}"),
        (r"$\sigma_2$", f"{sigma2:.3f}"),
        (r"$\tau_{max}$", f"{tau_max:.3f}"),
        (r"$\theta_p$", f"{theta_p:.2f}° ccw"),
        (r"$\theta_s$", f"{theta_s:.2f}° ccw"),
    ]
    if rotated is not None:
        rows.extend([
            (r"$\phi$", f"{rotated.phi_deg_ccw:.2f}° ccw"),
            (r"$\sigma_{x'}$", f"{rotated.sigma_x_prime:.3f}"),
            (r"$\sigma_{y'}$", f"{rotated.sigma_y_prime:.3f}"),
            (r"$\tau_{x'y'}$", f"{rotated.tau_x_prime_y_prime:.3f}"),
        ])
    y = 0.95
    for label, value in rows:
        ax_results.text(0.06, y, label, fontsize=10, fontweight="bold", transform=ax_results.transAxes, va="top")
        ax_results.text(0.55, y, value, fontsize=10, transform=ax_results.transAxes, va="top")
        y -= 0.08

    ax_mohr.set_title("Plane-stress Mohr circle", fontsize=12, pad=8, fontweight="bold")
    ax_mohr.set_aspect("equal", adjustable="box")
    theta = np.linspace(0.0, 2.0 * np.pi, 800)
    x = sigma_avg + radius * np.cos(theta)
    y = radius * np.sin(theta)
    ax_mohr.plot(x, y, linewidth=2.3, color="black")
    ax_mohr.axhline(0.0, linewidth=1.0, color="black")
    ax_mohr.axvline(0.0, linewidth=1.0, color="black")
    ax_mohr.grid(True, alpha=0.28)
    ax_mohr.set_xlabel(r"Normal stress, $\sigma$", fontsize=11)
    ax_mohr.set_ylabel(r"Shear stress, $\tau$", fontsize=11)
    ax_mohr.plot([C[0], A[0]], [C[1], A[1]], linewidth=1.2, color="tab:blue", linestyle="--", alpha=0.85)
    ax_mohr.plot([C[0], B[0]], [C[1], B[1]], linewidth=1.2, color="tab:orange", linestyle="--", alpha=0.85)
    for point in [A, B, C, P1, P2]:
        ax_mohr.plot(point[0], point[1], marker="o", linestyle="None", markersize=5, color="black")
    ax_mohr.annotate("A", xy=A, xytext=(5, 5), textcoords="offset points", fontsize=10)
    ax_mohr.annotate("B", xy=B, xytext=(5, -14), textcoords="offset points", fontsize=10)
    ax_mohr.annotate(r"$\sigma_1$", xy=P1, xytext=(8, -16), textcoords="offset points", fontsize=10)
    ax_mohr.annotate(r"$\sigma_2$", xy=P2, xytext=(-16, -16), textcoords="offset points", fontsize=10)
    _label_box(ax_mohr, C[0], -0.16 * max(radius, 1.0), rf"$\sigma_{{avg}} = {sigma_avg:.3f}$", ha="center")
    _label_box(ax_mohr, A[0] + 0.04 * max(radius, 1.0), 0.12 * max(radius, 1.0), rf"$\sigma_x = {_value_or_integer(sxx)}$", fontsize=9)
    _label_box(ax_mohr, B[0] + 0.04 * max(radius, 1.0), 0.20 * radius, rf"$\sigma_y = {_value_or_integer(syy)}$", fontsize=9)
    angle_CA = math.degrees(math.atan2(A[1] - C[1], A[0] - C[0]))
    annotate_angle_arc(ax_mohr, center=C, radius=max(radius * 0.18, 5.0), theta1_deg=0.0, theta2_deg=angle_CA, text=rf"$2\theta_p = {angle_CA:.2f}^\circ$", color="tab:blue")

    if rotated is not None:
        Pphi = rotated.point_x_prime
        Qphi = rotated.point_y_prime
        ax_mohr.plot(Pphi[0], Pphi[1], marker="o", linestyle="None", markersize=6, color="tab:red")
        ax_mohr.plot(Qphi[0], Qphi[1], marker="o", linestyle="None", markersize=6, color="tab:purple")
        ax_mohr.annotate(r"$P_\phi$", xy=Pphi, xytext=(5, 7), textcoords="offset points", fontsize=10, color="tab:red")
        ax_mohr.annotate(r"$Q_\phi$", xy=Qphi, xytext=(5, -15), textcoords="offset points", fontsize=10, color="tab:purple")
        ax_mohr.plot([C[0], Pphi[0]], [C[1], Pphi[1]], linestyle="--", linewidth=1.2, color="tab:red", alpha=0.9)
        angle_CP = math.degrees(math.atan2(Pphi[1] - C[1], Pphi[0] - C[0]))
        annotate_angle_arc(ax_mohr, center=C, radius=max(radius * 0.30, 8.0), theta1_deg=angle_CA, theta2_deg=angle_CP, text=rf"$2\phi = {2.0 * rotated.phi_deg_ccw:.2f}^\circ$", color="tab:red", linestyle="--", text_radius_scale=1.18)

    pad_x = max(10.0, 0.18 * max(abs(sigma1), abs(sigma2), abs(sxx), abs(syy), 1.0))
    pad_y = max(8.0, 0.18 * radius)
    ax_mohr.set_xlim(min(sigma2, A[0], B[0], 0.0) - pad_x, max(sigma1, A[0], B[0], 0.0) + pad_x)
    ax_mohr.set_ylim(-radius - pad_y, radius + pad_y)

    fig.suptitle(result.get("title") or "Mohr circle dashboard", fontsize=20, fontweight="bold")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=180, bbox_inches="tight")
    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def _render_mohr_3d(result: dict, outfile: Path, show_plot: bool) -> None:
    principal = np.array(result["principal_stresses"], dtype=float)
    sigma1, sigma2, sigma3 = principal
    circles = [
        {"label": "(σ1, σ2)", "center": 0.5 * (sigma1 + sigma2), "radius": 0.5 * abs(sigma1 - sigma2)},
        {"label": "(σ2, σ3)", "center": 0.5 * (sigma2 + sigma3), "radius": 0.5 * abs(sigma2 - sigma3)},
        {"label": "(σ1, σ3)", "center": 0.5 * (sigma1 + sigma3), "radius": 0.5 * abs(sigma1 - sigma3)},
    ]
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.set_aspect("equal", adjustable="box")
    theta = np.linspace(0.0, 2.0 * np.pi, 800)
    for circle in circles:
        c = circle["center"]
        r = circle["radius"]
        x = c + r * np.cos(theta)
        y = r * np.sin(theta)
        ax.plot(x, y, linewidth=2.0, label=f'{circle["label"]}: c={c:.3f}, r={r:.3f}')
    ax.scatter([sigma1, sigma2, sigma3], [0.0, 0.0, 0.0], marker="o", label="Principal stresses")
    ax.axhline(0.0, linewidth=1.0, color="black")
    ax.axvline(0.0, linewidth=1.0, color="black")
    ax.set_xlabel(r"Normal stress, $\sigma$")
    ax.set_ylabel(r"Shear stress, $\tau$")
    ax.set_title(result.get("title") or "3D Mohr circles", fontweight="bold")
    ax.grid(True, alpha=0.45)
    ax.legend()
    max_radius = max(c["radius"] for c in circles)
    pad_x = max(1.0, 0.15 * max(1.0, max(abs(v) for v in [sigma1, sigma2, sigma3])))
    pad_y = max(1.0, 0.15 * max(1.0, max_radius))
    ax.set_xlim(min(sigma1, sigma2, sigma3) - pad_x, max(sigma1, sigma2, sigma3) + pad_x)
    ax.set_ylim(-max_radius - pad_y, max_radius + pad_y)
    fig.tight_layout()
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=180, bbox_inches="tight")
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
