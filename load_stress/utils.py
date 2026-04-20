from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches

try:
    from .core import RotatedPlaneStrainResults, RotatedPlaneStressResults
except ImportError:
    from core import RotatedPlaneStrainResults, RotatedPlaneStressResults


# ---------- paths ----------

def package_directory() -> Path:
    return Path(__file__).resolve().parent


def default_output_directory() -> Path:
    return package_directory() / "out"


def default_json_output_path(stem: str) -> Path:
    return default_output_directory() / f"{stem}.json"


def default_plot_output_path(stem: str) -> Path:
    return default_output_directory() / f"{stem}.png"


# ---------- low-level drawing ----------

def _vec(angle_deg: float) -> np.ndarray:
    ang = math.radians(angle_deg)
    return np.array([math.cos(ang), math.sin(ang)], dtype=float)


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


def _component_label(family: str, kind: str, notation_prime: bool) -> str:
    if family == "stress":
        if kind == "x":
            return r"$\sigma_{x'}$" if notation_prime else r"$\sigma_x$"
        if kind == "y":
            return r"$\sigma_{y'}$" if notation_prime else r"$\sigma_y$"
        if kind == "shear":
            return r"$\tau_{x'y'}$" if notation_prime else r"$\tau_{xy}$"
    if family == "strain":
        if kind == "x":
            return r"$\varepsilon_{x'}$" if notation_prime else r"$\varepsilon_x$"
        if kind == "y":
            return r"$\varepsilon_{y'}$" if notation_prime else r"$\varepsilon_y$"
        if kind == "shear":
            return r"$\gamma_{x'y'}$" if notation_prime else r"$\gamma_{xy}$"
    raise ValueError(f"Unsupported family/kind: {family}/{kind}")


def draw_state_element_generic(
    ax: plt.Axes,
    *,
    title: str,
    family: str,
    angle_deg: float,
    x_value: float,
    y_value: float,
    shear_value: float,
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

    sign_x = 1.0 if x_value >= 0.0 else -1.0
    sign_y = 1.0 if y_value >= 0.0 else -1.0

    draw_arrow(ax, tuple(face_centers["+x"]), tuple(face_centers["+x"] + sign_x * normal_len * ex))
    draw_arrow(ax, tuple(face_centers["-x"]), tuple(face_centers["-x"] - sign_x * normal_len * ex))
    draw_arrow(ax, tuple(face_centers["+y"]), tuple(face_centers["+y"] + sign_y * normal_len * ey))
    draw_arrow(ax, tuple(face_centers["-y"]), tuple(face_centers["-y"] - sign_y * normal_len * ey))

    if abs(shear_value) > 1e-14:
        sign_tau = 1.0 if shear_value >= 0.0 else -1.0
        draw_arrow(ax, tuple(face_centers["+x"]), tuple(face_centers["+x"] + sign_tau * shear_len * ey))
        draw_arrow(ax, tuple(face_centers["-x"]), tuple(face_centers["-x"] - sign_tau * shear_len * ey))
        draw_arrow(ax, tuple(face_centers["+y"]), tuple(face_centers["+y"] + sign_tau * shear_len * ex))
        draw_arrow(ax, tuple(face_centers["-y"]), tuple(face_centers["-y"] - sign_tau * shear_len * ex))

    x_name = _component_label(family, "x", notation_prime)
    y_name = _component_label(family, "y", notation_prime)
    shear_name = _component_label(family, "shear", notation_prime)

    precision = 3 if family == "stress" else 6
    fmt = f"{{:.{precision}f}}"
    _label_box(ax, *(1.03 * face_centers["+x"] + np.array([0.32, 0.12])), f"{x_name} = {fmt.format(x_value)}")
    _label_box(ax, *(1.03 * face_centers["+y"] + np.array([0.08, 0.32])), f"{y_name} = {fmt.format(y_value)}")
    shear_text = f"{shear_name} = {fmt.format(shear_value)}" if abs(shear_value) > 1e-14 else f"{shear_name} = 0"
    _label_box(ax, -2.10, 1.40, shear_text)

    if abs(angle_deg) > 1e-12:
        arc = patches.Arc((0.0, 0.0), 0.95, 0.95, theta1=0.0, theta2=angle_deg, linewidth=1.0)
        ax.add_patch(arc)
        ang_mid = math.radians(0.5 * angle_deg)
        ax.text(0.62 * math.cos(ang_mid), 0.62 * math.sin(ang_mid) + 0.04, r"$\theta$", fontsize=10)

    base_y = -2.07
    for i, line in enumerate(subtitle_lines):
        ax.text(0.52, base_y - 0.24 * i, line, fontsize=10)

    ax.set_xlim(-2.35, 2.75)
    ax.set_ylim(-2.35, 2.25)


# ---------- plotting helpers ----------

def _data_scale(values: list[float], radius: float = 0.0) -> float:
    return max([abs(v) for v in values] + [abs(radius), 1e-12])


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


def _plot_plane_circle_base(ax: plt.Axes, center: tuple[float, float], radius: float, *, xlabel: str, ylabel: str) -> None:
    ax.set_aspect("equal", adjustable="box")
    theta = np.linspace(0.0, 2.0 * np.pi, 800)
    x = center[0] + radius * np.cos(theta)
    y = radius * np.sin(theta)
    ax.plot(x, y, linewidth=2.3, color="black")
    ax.axhline(0.0, linewidth=1.0, color="black")
    ax.axvline(0.0, linewidth=1.0, color="black")
    ax.grid(True, alpha=0.28)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)


def _set_plane_circle_limits(ax: plt.Axes, radius: float, x_values: list[float]) -> None:
    scale = _data_scale(x_values, radius)
    x_min = min(x_values + [0.0])
    x_max = max(x_values + [0.0])
    pad_x = max(0.18 * scale, 1e-12)
    pad_y = max(0.18 * max(radius, 0.35 * scale), 1e-12)
    ax.set_xlim(x_min - pad_x, x_max + pad_x)
    ax.set_ylim(-radius - pad_y, radius + pad_y)


def _write_summary_rows(ax: plt.Axes, rows: list[tuple[str, str]]) -> None:
    y = 0.95
    step = 0.075 if len(rows) <= 10 else 0.067
    for label, value in rows:
        ax.text(0.06, y, label, fontsize=10, fontweight="bold", transform=ax.transAxes, va="top")
        ax.text(0.55, y, value, fontsize=10, transform=ax.transAxes, va="top")
        y -= step


def _save_or_show(fig: plt.Figure, outfile: Path, show_plot: bool) -> None:
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=180, bbox_inches="tight")
    if show_plot:
        plt.show()
    else:
        plt.close(fig)


# ---------- dashboard routing ----------

def render_dashboard(result: dict, outfile: Path, show_plot: bool = False) -> Path:
    analysis_type = result.get("analysis_type")
    if analysis_type == "stress":
        if result.get("is_plane_stress"):
            _render_plane_stress_dashboard(result, outfile, show_plot)
        else:
            _render_mohr_3d(result, outfile, show_plot, family="stress")
    elif analysis_type == "strain":
        if result.get("is_plane_strain"):
            _render_plane_strain_dashboard(result, outfile, show_plot)
        else:
            _render_mohr_3d(result, outfile, show_plot, family="strain")
    else:
        raise ValueError("Unsupported analysis_type in result payload.")
    return outfile


# ---------- stress dashboards ----------

def _render_plane_stress_dashboard(result: dict, outfile: Path, show_plot: bool) -> None:
    stress = np.array(result["tensor"], dtype=float)
    plane = result["plane_stress"]
    rotated_dict = result.get("rotated_plane_stress")
    rotated: Optional[RotatedPlaneStressResults] = None
    if rotated_dict:
        rotated = RotatedPlaneStressResults(
            phi_deg_ccw=rotated_dict["phi_deg_ccw"],
            sigma_x_prime=rotated_dict["sigma_x_prime"],
            sigma_y_prime=rotated_dict["sigma_y_prime"],
            tau_x_prime_y_prime=rotated_dict["tau_x_prime_y_prime"],
            point_x_prime=tuple(rotated_dict["point_x_prime"]),
            point_y_prime=tuple(rotated_dict["point_y_prime"]),
        )

    sxx = float(stress[0, 0])
    syy = float(stress[1, 1])
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
    plot_scale = _data_scale([sigma1, sigma2, sxx, syy, A[0], B[0]], radius)

    fig = plt.figure(figsize=(16, 9), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, width_ratios=[1.0, 1.45, 1.0], height_ratios=[1.0, 1.0])
    ax_input = fig.add_subplot(gs[0, 0])
    ax_mohr = fig.add_subplot(gs[0, 1])
    ax_right_top = fig.add_subplot(gs[0, 2])
    ax_principal = fig.add_subplot(gs[1, 0])
    ax_shear = fig.add_subplot(gs[1, 1])
    ax_results = fig.add_subplot(gs[1, 2])

    draw_state_element_generic(ax_input, title="Input stress element", family="stress", angle_deg=0.0, x_value=sxx, y_value=syy, shear_value=2.0 * abs(A[1]), subtitle_lines=[])
    draw_state_element_generic(ax_principal, title="Principal stress element", family="stress", angle_deg=theta_p, x_value=sigma1, y_value=sigma2, shear_value=0.0, subtitle_lines=[rf"$\theta_p = {theta_p:.2f}^\circ$ ccw", rf"$\sigma_1 = {sigma1:.3f}$", rf"$\sigma_2 = {sigma2:.3f}$", r"$\tau = 0$"])
    draw_state_element_generic(ax_shear, title="Maximum in-plane shear element", family="stress", angle_deg=theta_s, x_value=sigma_avg, y_value=sigma_avg, shear_value=tau_max, subtitle_lines=[rf"$\theta_s = {theta_s:.2f}^\circ$ ccw", rf"$\sigma_{{avg}} = {sigma_avg:.3f}$", rf"$\tau_{{max}} = {tau_max:.3f}$", "equal normal stress on all faces"])

    if rotated is not None:
        draw_state_element_generic(ax_right_top, title="Arbitrary-angle stress element", family="stress", angle_deg=rotated.phi_deg_ccw, x_value=rotated.sigma_x_prime, y_value=rotated.sigma_y_prime, shear_value=rotated.tau_x_prime_y_prime, subtitle_lines=[rf"$\phi = {rotated.phi_deg_ccw:.2f}^\circ$ ccw", rf"$\sigma_{{x'}} = {rotated.sigma_x_prime:.3f}$", rf"$\sigma_{{y'}} = {rotated.sigma_y_prime:.3f}$", rf"$\tau_{{x'y'}} = {rotated.tau_x_prime_y_prime:.3f}$"], notation_prime=True)
    else:
        ax_right_top.axis("off")
        ax_right_top.set_title("Optional arbitrary-angle mode", fontsize=12, pad=8, fontweight="bold")
        ax_right_top.text(0.04, 0.92, "Pass --phi-deg <value> to add:", fontsize=11.5, va="top", fontweight="bold")
        for i, line in enumerate([
            r"transformed stresses $\sigma_{x'}$ and $\sigma_{y'}$",
            r"transformed shear $\tau_{x'y'}$",
            r"the point pair $P_\phi$ and $Q_\phi$ on Mohr's circle",
            r"the rotated stress-element sketch",
        ]):
            ax_right_top.text(0.08, 0.80 - i * 0.13, "• " + line, fontsize=10.8, va="top")

    ax_results.axis("off")
    ax_results.set_title("Results summary", fontsize=12, pad=8, fontweight="bold")
    rows = [(r"$\sigma_{avg}$", f"{sigma_avg:.3f}"), ("Radius", f"{radius:.3f}"), (r"$\sigma_1$", f"{sigma1:.3f}"), (r"$\sigma_2$", f"{sigma2:.3f}"), (r"$\tau_{max}$", f"{tau_max:.3f}"), (r"$\theta_p$", f"{theta_p:.2f}° ccw"), (r"$\theta_s$", f"{theta_s:.2f}° ccw")]
    if rotated is not None:
        rows.extend([(r"$\phi$", f"{rotated.phi_deg_ccw:.2f}° ccw"), (r"$\sigma_{x'}$", f"{rotated.sigma_x_prime:.3f}"), (r"$\sigma_{y'}$", f"{rotated.sigma_y_prime:.3f}"), (r"$\tau_{x'y'}$", f"{rotated.tau_x_prime_y_prime:.3f}")])
    _write_summary_rows(ax_results, rows)

    ax_mohr.set_title("Plane-stress Mohr circle", fontsize=12, pad=8, fontweight="bold")
    _plot_plane_circle_base(ax_mohr, C, radius, xlabel=r"Normal stress, $\sigma$", ylabel=r"Shear stress, $\tau$")
    ax_mohr.plot([C[0], A[0]], [C[1], A[1]], linewidth=1.2, color="tab:blue", linestyle="--", alpha=0.85)
    ax_mohr.plot([C[0], B[0]], [C[1], B[1]], linewidth=1.2, color="tab:orange", linestyle="--", alpha=0.85)
    for point in [A, B, C, P1, P2]:
        ax_mohr.plot(point[0], point[1], marker="o", linestyle="None", markersize=5, color="black")
    ax_mohr.annotate("A", xy=A, xytext=(5, 5), textcoords="offset points", fontsize=10)
    ax_mohr.annotate("B", xy=B, xytext=(5, -14), textcoords="offset points", fontsize=10)
    ax_mohr.annotate(r"$\sigma_1$", xy=P1, xytext=(8, -16), textcoords="offset points", fontsize=10)
    ax_mohr.annotate(r"$\sigma_2$", xy=P2, xytext=(-16, -16), textcoords="offset points", fontsize=10)
    _label_box(ax_mohr, C[0], -0.16 * plot_scale, rf"$\sigma_{{avg}} = {sigma_avg:.3f}$", ha="center")
    _label_box(ax_mohr, A[0] + 0.04 * plot_scale, 0.12 * plot_scale, rf"$\sigma_x = {sxx:.3f}$", fontsize=9)
    _label_box(ax_mohr, B[0] + 0.04 * plot_scale, 0.20 * radius, rf"$\sigma_y = {syy:.3f}$", fontsize=9)
    angle_CA = math.degrees(math.atan2(A[1] - C[1], A[0] - C[0]))
    annotate_angle_arc(ax_mohr, center=C, radius=max(radius * 0.18, 0.10 * plot_scale), theta1_deg=0.0, theta2_deg=angle_CA, text=rf"$2\theta_p = {angle_CA:.2f}^\circ$", color="tab:blue")
    if rotated is not None:
        Pphi = rotated.point_x_prime
        Qphi = rotated.point_y_prime
        ax_mohr.plot(Pphi[0], Pphi[1], marker="o", linestyle="None", markersize=6, color="tab:red")
        ax_mohr.plot(Qphi[0], Qphi[1], marker="o", linestyle="None", markersize=6, color="tab:purple")
        ax_mohr.annotate(r"$P_\phi$", xy=Pphi, xytext=(5, 7), textcoords="offset points", fontsize=10, color="tab:red")
        ax_mohr.annotate(r"$Q_\phi$", xy=Qphi, xytext=(5, -15), textcoords="offset points", fontsize=10, color="tab:purple")
        ax_mohr.plot([C[0], Pphi[0]], [C[1], Pphi[1]], linestyle="--", linewidth=1.2, color="tab:red", alpha=0.9)
        angle_CP = math.degrees(math.atan2(Pphi[1] - C[1], Pphi[0] - C[0]))
        annotate_angle_arc(ax_mohr, center=C, radius=max(radius * 0.30, 0.14 * plot_scale), theta1_deg=angle_CA, theta2_deg=angle_CP, text=rf"$2\phi = {2.0 * rotated.phi_deg_ccw:.2f}^\circ$", color="tab:red", linestyle="--", text_radius_scale=1.18)
    _set_plane_circle_limits(ax_mohr, radius, [sigma1, sigma2, sxx, syy, A[0], B[0]])
    fig.suptitle(result.get("title") or "Mohr circle dashboard", fontsize=20, fontweight="bold")
    _save_or_show(fig, outfile, show_plot)


# ---------- strain dashboards ----------

def _render_plane_strain_dashboard(result: dict, outfile: Path, show_plot: bool) -> None:
    strain_tensor = np.array(result["tensor"], dtype=float)
    plane = result["plane_strain"]
    rotated_dict = result.get("rotated_plane_strain")
    rotated: Optional[RotatedPlaneStrainResults] = None
    if rotated_dict:
        rotated = RotatedPlaneStrainResults(
            phi_deg_ccw=rotated_dict["phi_deg_ccw"],
            epsilon_x_prime=rotated_dict["epsilon_x_prime"],
            epsilon_y_prime=rotated_dict["epsilon_y_prime"],
            gamma_x_prime_y_prime=rotated_dict["gamma_x_prime_y_prime"],
            gamma_x_prime_y_prime_over_2=rotated_dict["gamma_x_prime_y_prime_over_2"],
            point_x_prime=tuple(rotated_dict["point_x_prime"]),
            point_y_prime=tuple(rotated_dict["point_y_prime"]),
        )

    exx = float(strain_tensor[0, 0])
    eyy = float(strain_tensor[1, 1])
    gxy_over_2 = float(strain_tensor[0, 1])
    gxy = 2.0 * gxy_over_2
    epsilon_avg = plane["epsilon_avg"]
    radius = plane["radius"]
    epsilon1 = plane["epsilon1"]
    epsilon2 = plane["epsilon2"]
    theta_p = plane["theta_p_deg_ccw"]
    theta_s = plane["theta_s_deg_ccw"]
    gamma_max = plane["gamma_max_in_plane"]
    A = tuple(plane["point_x"])
    B = tuple(plane["point_y"])
    C = (epsilon_avg, 0.0)
    P1 = (epsilon1, 0.0)
    P2 = (epsilon2, 0.0)
    plot_scale = _data_scale([epsilon1, epsilon2, exx, eyy, A[0], B[0], gxy_over_2], radius)

    fig = plt.figure(figsize=(16, 9), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, width_ratios=[1.0, 1.45, 1.0], height_ratios=[1.0, 1.0])
    ax_input = fig.add_subplot(gs[0, 0])
    ax_mohr = fig.add_subplot(gs[0, 1])
    ax_right_top = fig.add_subplot(gs[0, 2])
    ax_principal = fig.add_subplot(gs[1, 0])
    ax_shear = fig.add_subplot(gs[1, 1])
    ax_results = fig.add_subplot(gs[1, 2])

    draw_state_element_generic(ax_input, title="Input strain element", family="strain", angle_deg=0.0, x_value=exx, y_value=eyy, shear_value=gxy, subtitle_lines=[])
    draw_state_element_generic(ax_principal, title="Principal strain element", family="strain", angle_deg=theta_p, x_value=epsilon1, y_value=epsilon2, shear_value=0.0, subtitle_lines=[rf"$\theta_p = {theta_p:.2f}^\circ$ ccw", rf"$\varepsilon_1 = {epsilon1:.6f}$", rf"$\varepsilon_2 = {epsilon2:.6f}$", r"$\gamma = 0$"])
    draw_state_element_generic(ax_shear, title="Maximum in-plane shear element", family="strain", angle_deg=theta_s, x_value=epsilon_avg, y_value=epsilon_avg, shear_value=gamma_max, subtitle_lines=[rf"$\theta_s = {theta_s:.2f}^\circ$ ccw", rf"$\varepsilon_{{avg}} = {epsilon_avg:.6f}$", rf"$\gamma_{{max}} = {gamma_max:.6f}$", "equal normal strain on all faces"])

    if rotated is not None:
        draw_state_element_generic(ax_right_top, title="Arbitrary-angle strain element", family="strain", angle_deg=rotated.phi_deg_ccw, x_value=rotated.epsilon_x_prime, y_value=rotated.epsilon_y_prime, shear_value=rotated.gamma_x_prime_y_prime, subtitle_lines=[rf"$\phi = {rotated.phi_deg_ccw:.2f}^\circ$ ccw", rf"$\varepsilon_{{x'}} = {rotated.epsilon_x_prime:.6f}$", rf"$\varepsilon_{{y'}} = {rotated.epsilon_y_prime:.6f}$", rf"$\gamma_{{x'y'}} = {rotated.gamma_x_prime_y_prime:.6f}$"], notation_prime=True)
    else:
        ax_right_top.axis("off")
        ax_right_top.set_title("Optional arbitrary-angle mode", fontsize=12, pad=8, fontweight="bold")
        ax_right_top.text(0.04, 0.92, "Pass --phi-deg <value> to add:", fontsize=11.5, va="top", fontweight="bold")
        for i, line in enumerate([
            r"transformed strains $\varepsilon_{x'}$ and $\varepsilon_{y'}$",
            r"transformed engineering shear strain $\gamma_{x'y'}$",
            r"the point pair $P_\phi$ and $Q_\phi$ on Mohr's circle",
            r"the rotated strain-element sketch",
        ]):
            ax_right_top.text(0.08, 0.80 - i * 0.13, "• " + line, fontsize=10.8, va="top")

    ax_results.axis("off")
    ax_results.set_title("Results summary", fontsize=12, pad=8, fontweight="bold")
    rows = [(r"$\varepsilon_{avg}$", f"{epsilon_avg:.6f}"), ("Radius", f"{radius:.6f}"), (r"$\varepsilon_1$", f"{epsilon1:.6f}"), (r"$\varepsilon_2$", f"{epsilon2:.6f}"), (r"$\gamma_{max}$", f"{gamma_max:.6f}"), (r"$\gamma_{max}/2$", f"{gamma_max/2.0:.6f}"), (r"$\theta_p$", f"{theta_p:.2f}° ccw"), (r"$\theta_s$", f"{theta_s:.2f}° ccw")]
    if rotated is not None:
        rows.extend([(r"$\phi$", f"{rotated.phi_deg_ccw:.2f}° ccw"), (r"$\varepsilon_{x'}$", f"{rotated.epsilon_x_prime:.6f}"), (r"$\varepsilon_{y'}$", f"{rotated.epsilon_y_prime:.6f}"), (r"$\gamma_{x'y'}$", f"{rotated.gamma_x_prime_y_prime:.6f}"), (r"$\gamma_{x'y'}/2$", f"{rotated.gamma_x_prime_y_prime_over_2:.6f}")])
    _write_summary_rows(ax_results, rows)

    ax_mohr.set_title("Plane-strain Mohr circle", fontsize=12, pad=8, fontweight="bold")
    _plot_plane_circle_base(ax_mohr, C, radius, xlabel=r"Normal strain, $\varepsilon$", ylabel=r"Engineering shear strain, $\gamma/2$")
    ax_mohr.plot([C[0], A[0]], [C[1], A[1]], linewidth=1.2, color="tab:blue", linestyle="--", alpha=0.85)
    ax_mohr.plot([C[0], B[0]], [C[1], B[1]], linewidth=1.2, color="tab:orange", linestyle="--", alpha=0.85)
    for point in [A, B, C, P1, P2]:
        ax_mohr.plot(point[0], point[1], marker="o", linestyle="None", markersize=5, color="black")
    ax_mohr.annotate("x", xy=A, xytext=(5, 5), textcoords="offset points", fontsize=10)
    ax_mohr.annotate("y", xy=B, xytext=(5, -14), textcoords="offset points", fontsize=10)
    ax_mohr.annotate(r"$\varepsilon_1$", xy=P1, xytext=(8, -16), textcoords="offset points", fontsize=10)
    ax_mohr.annotate(r"$\varepsilon_2$", xy=P2, xytext=(-16, -16), textcoords="offset points", fontsize=10)
    _label_box(ax_mohr, C[0], -0.16 * plot_scale, rf"$\varepsilon_{{avg}} = {epsilon_avg:.6f}$", ha="center")
    _label_box(ax_mohr, A[0] + 0.04 * plot_scale, 0.12 * plot_scale, rf"$\varepsilon_x = {exx:.6f}$", fontsize=9)
    _label_box(ax_mohr, B[0] + 0.04 * plot_scale, 0.20 * radius, rf"$\varepsilon_y = {eyy:.6f}$", fontsize=9)
    _label_box(ax_mohr, A[0] + 0.10 * plot_scale, A[1] + 0.10 * plot_scale, rf"$x(\varepsilon_x,\,-\gamma_{{xy}}/2)$", fontsize=9)
    _label_box(ax_mohr, B[0] - 0.15 * plot_scale, B[1] - 0.12 * plot_scale, rf"$y(\varepsilon_y,\,+\gamma_{{xy}}/2)$", fontsize=9, ha="right")
    _label_box(ax_mohr, C[0], -0.34 * plot_scale, rf"$\gamma_{{xy}}/2 = {gxy_over_2:.6f}$", fontsize=9, ha="center")
    angle_CA = math.degrees(math.atan2(A[1] - C[1], A[0] - C[0]))
    annotate_angle_arc(ax_mohr, center=C, radius=max(radius * 0.18, 0.10 * plot_scale), theta1_deg=0.0, theta2_deg=angle_CA, text=rf"$2\theta_p = {angle_CA:.2f}^\circ$", color="tab:blue")
    if rotated is not None:
        Pphi = rotated.point_x_prime
        Qphi = rotated.point_y_prime
        ax_mohr.plot(Pphi[0], Pphi[1], marker="o", linestyle="None", markersize=6, color="tab:red")
        ax_mohr.plot(Qphi[0], Qphi[1], marker="o", linestyle="None", markersize=6, color="tab:purple")
        ax_mohr.annotate(r"$P_\phi$", xy=Pphi, xytext=(5, 7), textcoords="offset points", fontsize=10, color="tab:red")
        ax_mohr.annotate(r"$Q_\phi$", xy=Qphi, xytext=(5, -15), textcoords="offset points", fontsize=10, color="tab:purple")
        ax_mohr.plot([C[0], Pphi[0]], [C[1], Pphi[1]], linestyle="--", linewidth=1.2, color="tab:red", alpha=0.9)
        angle_CP = math.degrees(math.atan2(Pphi[1] - C[1], Pphi[0] - C[0]))
        annotate_angle_arc(ax_mohr, center=C, radius=max(radius * 0.30, 0.14 * plot_scale), theta1_deg=angle_CA, theta2_deg=angle_CP, text=rf"$2\phi = {2.0 * rotated.phi_deg_ccw:.2f}^\circ$", color="tab:red", linestyle="--", text_radius_scale=1.18)
    _set_plane_circle_limits(ax_mohr, radius, [epsilon1, epsilon2, exx, eyy, A[0], B[0]])
    fig.suptitle(result.get("title") or "Mohr circle dashboard", fontsize=20, fontweight="bold")
    _save_or_show(fig, outfile, show_plot)


# ---------- 3D circles ----------

def _render_mohr_3d(result: dict, outfile: Path, show_plot: bool, *, family: str) -> None:
    if family == "stress":
        principal = np.array(result["principal_stresses"], dtype=float)
        title = result.get("title") or "3D Mohr circles"
        xlabel = r"Normal stress, $\sigma$"
        ylabel = r"Shear stress, $\tau$"
        point_label = "Principal stresses"
        precision = 3
    elif family == "strain":
        principal = np.array(result["principal_strains"], dtype=float)
        title = result.get("title") or "3D Mohr circles"
        xlabel = r"Normal strain, $\varepsilon$"
        ylabel = r"Tensor shear strain, $\varepsilon_{ij}$"
        point_label = "Principal strains"
        precision = 6
    else:
        raise ValueError("Unsupported family.")

    s1, s2, s3 = principal
    circles = [
        {"label": "(1, 2)", "center": 0.5 * (s1 + s2), "radius": 0.5 * abs(s1 - s2)},
        {"label": "(2, 3)", "center": 0.5 * (s2 + s3), "radius": 0.5 * abs(s2 - s3)},
        {"label": "(1, 3)", "center": 0.5 * (s1 + s3), "radius": 0.5 * abs(s1 - s3)},
    ]

    fig, ax = plt.subplots(figsize=(10, 8), constrained_layout=True)
    ax.set_aspect("equal", adjustable="box")
    theta = np.linspace(0.0, 2.0 * np.pi, 800)
    for circle in circles:
        c = circle["center"]
        r = circle["radius"]
        x = c + r * np.cos(theta)
        y = r * np.sin(theta)
        ax.plot(x, y, linewidth=2.0, label=f'{circle["label"]}: c={c:.{precision}f}, r={r:.{precision}f}')
    ax.scatter([s1, s2, s3], [0.0, 0.0, 0.0], marker="o", label=point_label)
    ax.axhline(0.0, linewidth=1.0, color="black")
    ax.axvline(0.0, linewidth=1.0, color="black")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.grid(True, alpha=0.45)
    ax.legend()

    max_radius = max(c["radius"] for c in circles)
    scale = _data_scale([s1, s2, s3], max_radius)
    pad_x = max(0.18 * scale, 1e-12)
    pad_y = max(0.18 * max(max_radius, 0.35 * scale), 1e-12)
    ax.set_xlim(min(s1, s2, s3) - pad_x, max(s1, s2, s3) + pad_x)
    ax.set_ylim(-max_radius - pad_y, max_radius + pad_y)
    _save_or_show(fig, outfile, show_plot)
