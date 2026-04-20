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


def _is_microstrain_unit(unit: str) -> bool:
    text = (unit or "").strip().lower()
    return text in {"microstrain", "micro-strain", "µε", "με", "ue", "uε"}


def _strain_display(unit: str) -> dict[str, object]:
    if _is_microstrain_unit(unit):
        return {
            "scale": 1e6,
            "normal_suffix": r" $\mu\varepsilon$",
            "shear_suffix": r" $\mu$rad",
            "gamma_over_2_suffix": r" $\mu$rad",
            "normal_axis": r"Normal strain, $\varepsilon$ ($\mu\varepsilon$)",
            "shear_axis_plane": r"Engineering shear strain, $\gamma/2$ ($\mu$rad)",
            "shear_axis_3d": r"Tensor shear strain, $\varepsilon_{ij}$ ($\mu\varepsilon$)",
            "precision": 0,
        }
    return {
        "scale": 1.0,
        "normal_suffix": "",
        "shear_suffix": "",
        "gamma_over_2_suffix": "",
        "normal_axis": r"Normal strain, $\varepsilon$",
        "shear_axis_plane": r"Engineering shear strain, $\gamma/2$",
        "shear_axis_3d": r"Tensor shear strain, $\varepsilon_{ij}$",
        "precision": 6,
    }


def _format_number(value: float, precision: int) -> str:
    if precision <= 0:
        return f"{value:.0f}"
    return f"{value:.{precision}f}"


def _format_scaled(value: float, *, scale: float, precision: int, suffix: str = "") -> str:
    return f"{_format_number(value * scale, precision)}{suffix}"


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
    value_scale: float = 1.0,
    value_precision: Optional[int] = None,
    x_suffix: str = "",
    y_suffix: str = "",
    shear_suffix: str = "",
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

    precision = value_precision if value_precision is not None else (3 if family == "stress" else 6)
    x_text = f"{x_name} = {_format_scaled(x_value, scale=value_scale, precision=precision, suffix=x_suffix)}"
    y_text = f"{y_name} = {_format_scaled(y_value, scale=value_scale, precision=precision, suffix=y_suffix)}"
    if abs(shear_value) > 1e-14:
        shear_text = f"{shear_name} = {_format_scaled(shear_value, scale=value_scale, precision=precision, suffix=shear_suffix)}"
    else:
        shear_text = f"{shear_name} = 0"

    _label_box(ax, *(1.03 * face_centers["+x"] + np.array([0.32, 0.12])), x_text)
    _label_box(ax, *(1.03 * face_centers["+y"] + np.array([0.08, 0.32])), y_text)
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
    step = 0.075 if len(rows) <= 10 else 0.064
    for label, value in rows:
        ax.text(0.06, y, label, fontsize=10, fontweight="bold", transform=ax.transAxes, va="top")
        ax.text(0.60, y, value, fontsize=10, transform=ax.transAxes, va="top")
        y -= step


def _save_or_show(fig: plt.Figure, outfile: Path, show_plot: bool) -> None:
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=180, bbox_inches="tight")
    if show_plot:
        plt.show()
    else:
        plt.close(fig)


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

    disp = _strain_display(result.get("inputs", {}).get("unit", ""))
    sc = float(disp["scale"])
    prec = int(disp["precision"])
    n_suffix = str(disp["normal_suffix"])
    s_suffix = str(disp["shear_suffix"])
    s2_suffix = str(disp["gamma_over_2_suffix"])

    exx = float(strain_tensor[0, 0]); eyy = float(strain_tensor[1, 1]); gxy_over_2 = float(strain_tensor[0, 1]); gxy = 2.0 * gxy_over_2
    epsilon_avg = plane["epsilon_avg"]; radius = plane["radius"]; epsilon1 = plane["epsilon1"]; epsilon2 = plane["epsilon2"]
    theta_p = plane["theta_p_deg_ccw"]; theta_s = plane["theta_s_deg_ccw"]; gamma_max = plane["gamma_max_in_plane"]
    gamma_abs_max_3d = plane.get("gamma_abs_max_3d", result.get("max_engineering_shear_strain_3d", gamma_max))
    theta_e1_ccw = plane.get("theta_epsilon1_deg_ccw", theta_p)
    theta_e2_ccw = plane.get("theta_epsilon2_deg_ccw", theta_p + 90.0)
    theta_e1_cw = plane.get("theta_epsilon1_deg_cw", abs(theta_p))
    theta_e2_cw = plane.get("theta_epsilon2_deg_cw", abs(theta_p + 90.0))
    abs_eq_in_plane = bool(plane.get("abs_max_equals_in_plane", False))

    A = (plane["point_x"][0] * sc, plane["point_x"][1] * sc)
    B = (plane["point_y"][0] * sc, plane["point_y"][1] * sc)
    C = (epsilon_avg * sc, 0.0)
    P1 = (epsilon1 * sc, 0.0)
    P2 = (epsilon2 * sc, 0.0)
    S_top = (epsilon_avg * sc, radius * sc)
    S_bot = (epsilon_avg * sc, -radius * sc)

    plot_scale = _data_scale([P1[0], P2[0], A[0], B[0], C[0]], radius * sc)

    fig = plt.figure(figsize=(16, 9), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, width_ratios=[1.0, 1.45, 1.0], height_ratios=[1.0, 1.0])
    ax_input = fig.add_subplot(gs[0, 0])
    ax_mohr = fig.add_subplot(gs[0, 1])
    ax_right_top = fig.add_subplot(gs[0, 2])
    ax_principal = fig.add_subplot(gs[1, 0])
    ax_shear = fig.add_subplot(gs[1, 1])
    ax_results = fig.add_subplot(gs[1, 2])

    draw_state_element_generic(
        ax_input, title="Input strain element", family="strain", angle_deg=0.0,
        x_value=exx, y_value=eyy, shear_value=gxy, subtitle_lines=[],
        value_scale=sc, value_precision=prec, x_suffix=n_suffix, y_suffix=n_suffix, shear_suffix=s_suffix
    )
    draw_state_element_generic(
        ax_principal, title="Principal strain element", family="strain", angle_deg=theta_p,
        x_value=epsilon1, y_value=epsilon2, shear_value=0.0,
        subtitle_lines=[
            rf"$\theta_{{\varepsilon_1}} = {theta_e1_ccw:.2f}^\circ$ ccw",
            rf"$\theta_{{\varepsilon_2}} = {theta_e2_ccw:.2f}^\circ$ ccw",
            f"ε1 = {_format_scaled(epsilon1, scale=sc, precision=prec, suffix=n_suffix)}",
            f"ε2 = {_format_scaled(epsilon2, scale=sc, precision=prec, suffix=n_suffix)}",
        ],
        value_scale=sc, value_precision=prec, x_suffix=n_suffix, y_suffix=n_suffix, shear_suffix=s_suffix
    )
    draw_state_element_generic(
        ax_shear, title="Maximum in-plane shear element", family="strain", angle_deg=theta_s,
        x_value=epsilon_avg, y_value=epsilon_avg, shear_value=gamma_max,
        subtitle_lines=[
            rf"$\theta_s = {theta_s:.2f}^\circ$ ccw",
            f"εavg = {_format_scaled(epsilon_avg, scale=sc, precision=prec, suffix=n_suffix)}",
            f"γmax,in-plane = {_format_scaled(gamma_max, scale=sc, precision=prec, suffix=s_suffix)}",
            "equal normal strain on all faces",
        ],
        value_scale=sc, value_precision=prec, x_suffix=n_suffix, y_suffix=n_suffix, shear_suffix=s_suffix
    )

    if rotated is not None:
        draw_state_element_generic(
            ax_right_top, title="Arbitrary-angle strain element", family="strain", angle_deg=rotated.phi_deg_ccw,
            x_value=rotated.epsilon_x_prime, y_value=rotated.epsilon_y_prime, shear_value=rotated.gamma_x_prime_y_prime,
            subtitle_lines=[
                rf"$\phi = {rotated.phi_deg_ccw:.2f}^\circ$ ccw",
                f"εx' = {_format_scaled(rotated.epsilon_x_prime, scale=sc, precision=prec, suffix=n_suffix)}",
                f"εy' = {_format_scaled(rotated.epsilon_y_prime, scale=sc, precision=prec, suffix=n_suffix)}",
                f"γx'y' = {_format_scaled(rotated.gamma_x_prime_y_prime, scale=sc, precision=prec, suffix=s_suffix)}",
            ],
            notation_prime=True, value_scale=sc, value_precision=prec, x_suffix=n_suffix, y_suffix=n_suffix, shear_suffix=s_suffix
        )
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
    rows = [
        (r"$\varepsilon_{avg}$", _format_scaled(epsilon_avg, scale=sc, precision=prec, suffix=n_suffix)),
        ("Radius", _format_scaled(radius, scale=sc, precision=prec, suffix=s2_suffix)),
        (r"$\varepsilon_1$", _format_scaled(epsilon1, scale=sc, precision=prec, suffix=n_suffix)),
        (r"$\varepsilon_2$", _format_scaled(epsilon2, scale=sc, precision=prec, suffix=n_suffix)),
        (r"$\gamma_{max,\ in\text{-}plane}$", _format_scaled(gamma_max, scale=sc, precision=prec, suffix=s_suffix)),
        (r"$\gamma_{abs,\ 3D}$", _format_scaled(gamma_abs_max_3d, scale=sc, precision=prec, suffix=s_suffix)),
        (r"$\theta_{\varepsilon_1}$", f"{theta_e1_ccw:.2f}° ccw / {theta_e1_cw:.2f}° cw"),
        (r"$\theta_{\varepsilon_2}$", f"{theta_e2_ccw:.2f}° ccw / {theta_e2_cw:.2f}° cw"),
        (r"$\theta_s$", f"{theta_s:.2f}° ccw"),
        ("3D note", "abs max = in-plane" if abs_eq_in_plane else "abs max differs from in-plane"),
    ]
    if rotated is not None:
        rows.extend([
            (r"$\phi$", f"{rotated.phi_deg_ccw:.2f}° ccw"),
            (r"$\varepsilon_{x'}$", _format_scaled(rotated.epsilon_x_prime, scale=sc, precision=prec, suffix=n_suffix)),
            (r"$\varepsilon_{y'}$", _format_scaled(rotated.epsilon_y_prime, scale=sc, precision=prec, suffix=n_suffix)),
            (r"$\gamma_{x'y'}$", _format_scaled(rotated.gamma_x_prime_y_prime, scale=sc, precision=prec, suffix=s_suffix)),
            (r"$\gamma_{x'y'}/2$", _format_scaled(rotated.gamma_x_prime_y_prime_over_2, scale=sc, precision=prec, suffix=s2_suffix)),
        ])
    _write_summary_rows(ax_results, rows)

    ax_mohr.set_title("Plane-strain Mohr circle", fontsize=12, pad=8, fontweight="bold")
    _plot_plane_circle_base(ax_mohr, C, radius * sc, xlabel=str(disp["normal_axis"]), ylabel=str(disp["shear_axis_plane"]))
    ax_mohr.plot([C[0], A[0]], [C[1], A[1]], linewidth=1.2, color="tab:blue", linestyle="--", alpha=0.85)
    ax_mohr.plot([C[0], B[0]], [C[1], B[1]], linewidth=1.2, color="tab:orange", linestyle="--", alpha=0.85)

    for point in [A, B, C, P1, P2, S_top, S_bot]:
        ax_mohr.plot(point[0], point[1], marker="o", linestyle="None", markersize=5, color="black")

    ax_mohr.annotate("x", xy=A, xytext=(5, 5), textcoords="offset points", fontsize=10)
    ax_mohr.annotate("y", xy=B, xytext=(5, -14), textcoords="offset points", fontsize=10)
    ax_mohr.annotate(r"$P_1$", xy=P1, xytext=(8, -16), textcoords="offset points", fontsize=10, color="tab:blue")
    ax_mohr.annotate(r"$P_2$", xy=P2, xytext=(-16, -16), textcoords="offset points", fontsize=10, color="tab:blue")
    ax_mohr.annotate(r"$S_2$", xy=S_top, xytext=(-12, 8), textcoords="offset points", fontsize=10, color="tab:red")
    ax_mohr.annotate(r"$S_1$", xy=S_bot, xytext=(-12, -18), textcoords="offset points", fontsize=10, color="tab:red")
    _label_box(ax_mohr, C[0], -0.16 * plot_scale, rf"$C = ({_format_number(C[0], prec)}, 0)$", ha="center")
    _label_box(ax_mohr, A[0] + 0.08 * plot_scale, A[1] + 0.08 * plot_scale, rf"$x(\varepsilon_x,\,-\gamma_{{xy}}/2)$", fontsize=9)
    _label_box(ax_mohr, B[0] - 0.10 * plot_scale, B[1] - 0.08 * plot_scale, rf"$y(\varepsilon_y,\,+\gamma_{{xy}}/2)$", fontsize=9, ha="right")
    _label_box(ax_mohr, C[0] + 0.14 * plot_scale, 0.14 * plot_scale, rf"$R = {_format_number(radius * sc, prec)}$", fontsize=9)

    angle_CA = math.degrees(math.atan2(A[1] - C[1], A[0] - C[0]))
    annotate_angle_arc(ax_mohr, center=C, radius=max(radius * sc * 0.18, 0.10 * plot_scale), theta1_deg=0.0, theta2_deg=angle_CA, text=rf"$2\theta_p = {abs(angle_CA):.1f}^\circ$", color="tab:blue")

    if rotated is not None:
        Pphi = (rotated.point_x_prime[0] * sc, rotated.point_x_prime[1] * sc)
        Qphi = (rotated.point_y_prime[0] * sc, rotated.point_y_prime[1] * sc)
        ax_mohr.plot(Pphi[0], Pphi[1], marker="o", linestyle="None", markersize=6, color="tab:red")
        ax_mohr.plot(Qphi[0], Qphi[1], marker="o", linestyle="None", markersize=6, color="tab:purple")
        ax_mohr.annotate(r"$P_\phi$", xy=Pphi, xytext=(5, 7), textcoords="offset points", fontsize=10, color="tab:red")
        ax_mohr.annotate(r"$Q_\phi$", xy=Qphi, xytext=(5, -15), textcoords="offset points", fontsize=10, color="tab:purple")
        ax_mohr.plot([C[0], Pphi[0]], [C[1], Pphi[1]], linestyle="--", linewidth=1.2, color="tab:red", alpha=0.9)
        angle_CP = math.degrees(math.atan2(Pphi[1] - C[1], Pphi[0] - C[0]))
        annotate_angle_arc(ax_mohr, center=C, radius=max(radius * sc * 0.30, 0.14 * plot_scale), theta1_deg=angle_CA, theta2_deg=angle_CP, text=rf"$2\phi = {2.0 * rotated.phi_deg_ccw:.2f}^\circ$", color="tab:red", linestyle="--", text_radius_scale=1.18)

    _set_plane_circle_limits(ax_mohr, radius * sc, [P1[0], P2[0], A[0], B[0], C[0]])
    fig.suptitle(result.get("title") or "Mohr circle dashboard", fontsize=20, fontweight="bold")
    _save_or_show(fig, outfile, show_plot)


def _render_mohr_3d(result: dict, outfile: Path, show_plot: bool, *, family: str) -> None:
    if family == "stress":
        principal = np.array(result["principal_stresses"], dtype=float)
        title = result.get("title") or "3D Mohr circles"
        xlabel = r"Normal stress, $\sigma$"
        ylabel = r"Shear stress, $\tau$"
        point_label = "Principal stresses"
        precision = 3
        scale = 1.0
        suffix = ""
    elif family == "strain":
        principal = np.array(result["principal_strains"], dtype=float)
        disp = _strain_display(result.get("inputs", {}).get("unit", ""))
        scale = float(disp["scale"])
        title = result.get("title") or "3D Mohr circles"
        xlabel = str(disp["normal_axis"])
        ylabel = str(disp["shear_axis_3d"])
        point_label = "Principal strains"
        precision = int(disp["precision"])
        suffix = str(disp["normal_suffix"])
    else:
        raise ValueError("Unsupported family.")

    principal_scaled = principal * scale
    s1, s2, s3 = principal_scaled
    circles = [
        {"label": "(1, 2)", "center": 0.5 * (s1 + s2), "radius": 0.5 * abs(s1 - s2)},
        {"label": "(2, 3)", "center": 0.5 * (s2 + s3), "radius": 0.5 * abs(s2 - s3)},
        {"label": "(1, 3)", "center": 0.5 * (s1 + s3), "radius": 0.5 * abs(s1 - s3)},
    ]

    fig, ax = plt.subplots(figsize=(10, 8), constrained_layout=True)
    ax.set_aspect("equal", adjustable="box")
    theta = np.linspace(0.0, 2.0 * np.pi, 800)
    for circle in circles:
        c = circle["center"]; r = circle["radius"]
        x = c + r * np.cos(theta)
        y = r * np.sin(theta)
        ax.plot(x, y, linewidth=2.0, label=f'{circle["label"]}: c={_format_number(c, precision)}{suffix}, r={_format_number(r, precision)}{suffix}')
    ax.scatter([s1, s2, s3], [0.0, 0.0, 0.0], marker="o", label=point_label)
    ax.axhline(0.0, linewidth=1.0, color="black")
    ax.axvline(0.0, linewidth=1.0, color="black")
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(title, fontweight="bold")
    ax.grid(True, alpha=0.45); ax.legend()

    max_radius = max(c["radius"] for c in circles)
    scale_plot = _data_scale([s1, s2, s3], max_radius)
    pad_x = max(0.18 * scale_plot, 1e-12)
    pad_y = max(0.18 * max(max_radius, 0.35 * scale_plot), 1e-12)
    ax.set_xlim(min(s1, s2, s3) - pad_x, max(s1, s2, s3) + pad_x)
    ax.set_ylim(-max_radius - pad_y, max_radius + pad_y)
    _save_or_show(fig, outfile, show_plot)
