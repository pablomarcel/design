#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""transmissions.gui_core_trans

Dear PyGui frontend for the universal transmission analyzer.

Main workflow
-------------
- Left side: pick/build shift schedule JSON + transmission spec JSON
- Left side: run options for the generic analyzer
- Right side: tables/report, JSON payload, topology, logs, history

Run
---
python -m gui_core_trans
"""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from queue import SimpleQueue
from typing import Any, Callable

if __package__ in (None, ""):
    pkg_root = os.path.abspath(os.path.dirname(__file__))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)

try:
    import dearpygui.dearpygui as dpg
except Exception as e:  # pragma: no cover
    raise SystemExit("Dear PyGui is required. Install with: pip install dearpygui") from e

try:
    from .app import RunRequest, TransmissionApplication, render_text_report
    try:
        from .app import _render_plain_report as _app_render_plain_report
    except Exception:
        _app_render_plain_report = None  # type: ignore[assignment]
    from .gui_log_trans import LogPanel, DpgLogHandler
    from .gui_utils_trans import (
        TaskResult,
        ensure_dir,
        extract_dpg_file_dialog_path,
        find_repo_root,
        in_dir,
        out_dir,
        list_schedule_files,
        list_spec_files,
        load_json,
        open_path,
        pretty_json,
        run_task_async,
        save_json,
    )
    from .shift_schedule_builder import parse_shift_schedule_csv, schedule_payload_to_csv
    from .transmission_spec_builder import build_spec_payload, spec_payload_to_editors
except Exception:  # pragma: no cover
    from app import RunRequest, TransmissionApplication, render_text_report  # type: ignore
    try:
        from app import _render_plain_report as _app_render_plain_report  # type: ignore
    except Exception:
        _app_render_plain_report = None  # type: ignore[assignment]
    from gui_log_trans import LogPanel, DpgLogHandler  # type: ignore
    from gui_utils_trans import (  # type: ignore
        TaskResult,
        ensure_dir,
        extract_dpg_file_dialog_path,
        find_repo_root,
        in_dir,
        out_dir,
        list_schedule_files,
        list_spec_files,
        load_json,
        open_path,
        pretty_json,
        run_task_async,
        save_json,
    )
    from shift_schedule_builder import parse_shift_schedule_csv, schedule_payload_to_csv  # type: ignore
    from transmission_spec_builder import build_spec_payload, spec_payload_to_editors  # type: ignore


LEFT_PANEL_WIDTH = 640
DEFAULT_UI_SCALE = 1.08


def t(prefix: str, name: str) -> str:
    return f"##{prefix}_{name}"


@dataclass
class AppState:
    repo_root: Path
    in_root: Path
    out_root: Path
    ui_font_default: int | None = None
    ui_font_macos: int | None = None
    ui_font_labview: int | None = None
    mono_font: int | None = None
    log_handler: logging.Handler | None = None
    last_spec_path: str = ""
    last_schedule_path: str = ""
    last_output_json: str = ""
    history: list[str] | None = None


UiTask = Callable[[], None]


def _file_dialog_extension_tag(dialog_kind: str, ext_kind: str) -> str:
    return t("tr", f"fdext_{dialog_kind}_{ext_kind}")


def _apply_file_dialog_extension_colors(text_rgb: tuple[int, int, int]) -> None:
    color = tuple(text_rgb) + (255,)
    for dialog_kind in ("spec", "schedule"):
        for ext_kind in ("json", "all"):
            tag = _file_dialog_extension_tag(dialog_kind, ext_kind)
            if not dpg.does_item_exist(tag):
                continue
            try:
                dpg.configure_item(tag, color=color)
            except Exception:
                pass


def enqueue_task(q: SimpleQueue[UiTask], fn: UiTask) -> None:
    q.put(fn)


def drain_tasks(q: SimpleQueue[UiTask], *, max_tasks: int = 50) -> None:
    for _ in range(max_tasks):
        try:
            fn = q.get_nowait()
        except Exception:
            return
        try:
            fn()
        except Exception:
            return


# ------------------------------ themes/fonts ------------------------------

def _make_theme_light() -> int:
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (240, 242, 245, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (236, 240, 245, 255))
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (255, 255, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (17, 24, 39, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (107, 114, 128, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (255, 255, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (249, 250, 251, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (243, 244, 246, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (203, 213, 225, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Separator, (226, 232, 240, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (59, 130, 246, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (37, 99, 235, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (29, 78, 216, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Tab, (229, 231, 235, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (191, 219, 254, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, (59, 130, 246, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Header, (219, 234, 254, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (191, 219, 254, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (147, 197, 253, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, (241, 245, 249, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, (148, 163, 184, 255))

            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 10)
            dpg.add_theme_style(dpg.mvStyleVar_PopupRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, 10)
            dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 10)

            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 16, 14)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 7)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 10, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ItemInnerSpacing, 8, 6)

        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
    return theme


def _make_theme_dark() -> int:
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (24, 26, 31, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (31, 34, 39, 255))
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (31, 34, 39, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (233, 236, 239, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (156, 163, 175, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (41, 45, 52, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (55, 60, 69, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (70, 76, 87, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (55, 60, 69, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (99, 102, 241, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (79, 70, 229, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (67, 56, 202, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Tab, (41, 45, 52, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (70, 76, 87, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, (99, 102, 241, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Header, (55, 60, 69, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (70, 76, 87, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (99, 102, 241, 255))

            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 10)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 16, 14)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 7)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 10, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ItemInnerSpacing, 8, 6)
    return theme


def _make_theme_macos() -> int:
    window_bg = (245, 245, 247, 255)
    control_bg = (255, 255, 255, 255)
    subtle_border = (214, 214, 214, 255)
    graphite = (28, 28, 30, 255)
    accent = (0, 122, 255, 255)

    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, window_bg)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, window_bg)
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, control_bg)
            dpg.add_theme_color(dpg.mvThemeCol_Text, graphite)
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (120, 120, 125, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, control_bg)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (248, 248, 250, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (240, 240, 243, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Border, subtle_border)
            dpg.add_theme_color(dpg.mvThemeCol_Separator, subtle_border)

            dpg.add_theme_color(dpg.mvThemeCol_Button, accent)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (22, 118, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (10, 97, 223, 255))

            dpg.add_theme_color(dpg.mvThemeCol_Tab, (230, 230, 233, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (210, 225, 255, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, accent)

            dpg.add_theme_color(dpg.mvThemeCol_Header, (219, 234, 254, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (191, 219, 254, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (147, 197, 253, 255))

            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, (241, 245, 249, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, (148, 163, 184, 255))

            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 10)
            dpg.add_theme_style(dpg.mvStyleVar_PopupRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_ScrollbarRounding, 10)
            dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 10)

            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 16, 14)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 7)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 10, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ItemInnerSpacing, 8, 6)

        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))
    return theme


def _make_theme_labview() -> int:
    window_bg = (223, 225, 229, 255)
    panel_bg = (208, 210, 214, 255)
    control_bg = (242, 243, 245, 255)
    graphite = (30, 31, 34, 255)
    border = (139, 143, 148, 255)
    accent = (242, 194, 0, 255)

    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, window_bg)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, panel_bg)
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, control_bg)
            dpg.add_theme_color(dpg.mvThemeCol_Text, graphite)
            dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, (110, 115, 120, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, control_bg)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (233, 235, 238, 255))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (224, 226, 230, 255))
            dpg.add_theme_color(dpg.mvThemeCol_Border, border)
            dpg.add_theme_color(dpg.mvThemeCol_Separator, border)

            dpg.add_theme_color(dpg.mvThemeCol_Button, (230, 232, 235, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (255, 213, 77, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, accent)

            dpg.add_theme_color(dpg.mvThemeCol_Tab, (215, 217, 221, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (245, 224, 140, 255))
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, accent)

            dpg.add_theme_color(dpg.mvThemeCol_Header, (220, 222, 226, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (245, 224, 140, 255))
            dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (255, 213, 77, 255))

            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarBg, panel_bg)
            dpg.add_theme_color(dpg.mvThemeCol_ScrollbarGrab, (160, 165, 170, 255))

            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_ChildRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 14, 12)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 6)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 10, 7)
            dpg.add_theme_style(dpg.mvStyleVar_ItemInnerSpacing, 8, 5)
    return theme


@dataclass(frozen=True)
class ThemeSpec:
    label: str
    key: str
    theme_id: int
    dialog_theme_id: int | None
    font_id: int | None


def _make_file_dialog_theme(*, text_rgb: tuple[int, int, int], selected_text_rgb: tuple[int, int, int] | None = None) -> int:
    """Create a file-dialog-specific theme.

    Dear PyGui file dialogs can render file-list entries with button/selectable
    text colors that do not inherit well from the main light themes. We bind an
    item theme directly to the file dialog so file names remain readable in
    Light/macOS/LabVIEW modes while leaving Dark mode untouched.
    """
    selected = selected_text_rgb or text_rgb
    with dpg.theme() as theme:
        for component in (getattr(dpg, "mvButton", None), getattr(dpg, "mvSelectable", None)):
            if component is None:
                continue
            with dpg.theme_component(component):
                dpg.add_theme_color(dpg.mvThemeCol_Text, text_rgb + (255,))
                try:
                    dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, text_rgb + (190,))
                except Exception:
                    pass
                try:
                    dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, selected + (255,))
                except Exception:
                    pass
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, text_rgb + (255,))
            try:
                dpg.add_theme_color(dpg.mvThemeCol_TextDisabled, text_rgb + (190,))
            except Exception:
                pass
    return theme


def _norm_theme_key(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "")
    if s in ("lab", "labview", "lv", "ni", "lab-view"):
        return "labview"
    if s in ("mac", "macos", "osx", "macosx"):
        return "macos"
    if s in ("dark", "night"):
        return "dark"
    if s in ("light", "day"):
        return "light"
    return s


def _load_fonts(state: AppState, *, ui_point_size: int = 14, mono_point_size: int = 13) -> None:
    def _try_add_font(path: str, size: int) -> int | None:
        fp = Path(path)
        if not fp.exists():
            return None
        try:
            return dpg.add_font(str(fp), size)
        except Exception:
            return None

    ui_default_candidates: list[str] = []
    ui_macos_candidates: list[str] = []
    ui_labview_candidates: list[str] = []
    mono_candidates: list[str] = []

    if sys.platform.startswith("darwin"):
        ui_default_candidates += [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/SFNSText.ttf",
            "/System/Library/Fonts/SFNSDisplay.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc",
        ]
        ui_macos_candidates += [
            "/System/Library/Fonts/SFNSText.ttf",
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        ui_labview_candidates += [
            "/System/Library/Fonts/Supplemental/Verdana.ttf",
            "/System/Library/Fonts/Supplemental/Tahoma.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        mono_candidates += [
            "/System/Library/Fonts/Monaco.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "/Library/Fonts/Menlo.ttc",
        ]

    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        ui_default_candidates += [
            str(Path(windir) / "Fonts" / "segoeui.ttf"),
            str(Path(windir) / "Fonts" / "arial.ttf"),
        ]
        ui_macos_candidates += [
            str(Path(windir) / "Fonts" / "segoeui.ttf"),
            str(Path(windir) / "Fonts" / "arial.ttf"),
        ]
        ui_labview_candidates += [
            str(Path(windir) / "Fonts" / "verdana.ttf"),
            str(Path(windir) / "Fonts" / "tahoma.ttf"),
            str(Path(windir) / "Fonts" / "arial.ttf"),
        ]
        mono_candidates += [
            str(Path(windir) / "Fonts" / "consola.ttf"),
            str(Path(windir) / "Fonts" / "lucon.ttf"),
            str(Path(windir) / "Fonts" / "cour.ttf"),
        ]

    ui_default_candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    ]
    ui_macos_candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    ui_labview_candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    mono_candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf",
    ]

    try:
        with dpg.font_registry():
            state.ui_font_default = next((fid for fid in (_try_add_font(p, ui_point_size) for p in ui_default_candidates) if fid), None)
            state.ui_font_macos = next((fid for fid in (_try_add_font(p, ui_point_size) for p in ui_macos_candidates) if fid), None)
            state.ui_font_labview = next((fid for fid in (_try_add_font(p, ui_point_size) for p in ui_labview_candidates) if fid), None)
            state.mono_font = next((fid for fid in (_try_add_font(p, mono_point_size) for p in mono_candidates) if fid), None)
    except Exception:
        return

    if state.ui_font_default is None:
        state.ui_font_default = state.ui_font_macos or state.ui_font_labview
    if state.ui_font_macos is None:
        state.ui_font_macos = state.ui_font_default
    if state.ui_font_labview is None:
        state.ui_font_labview = state.ui_font_default


def _apply_theme(mode: str, themes: dict[str, ThemeSpec]) -> None:
    key = _norm_theme_key(mode)
    spec = themes.get(key) or themes.get("light")
    if spec is None:
        return
    try:
        dpg.bind_theme(spec.theme_id)
    except Exception:
        pass
    for tag in (t("tr", "fd_spec"), t("tr", "fd_schedule")):
        if dpg.does_item_exist(tag):
            try:
                if spec.dialog_theme_id is not None:
                    dpg.bind_item_theme(tag, spec.dialog_theme_id)
                else:
                    dpg.bind_item_theme(tag, 0)
            except Exception:
                pass
    ext_text_rgb_by_theme = {
        "light": (17, 24, 39),
        "macos": (28, 28, 30),
        "labview": (30, 31, 34),
        "dark": (233, 236, 239),
    }
    _apply_file_dialog_extension_colors(ext_text_rgb_by_theme.get(spec.key, (17, 24, 39)))
    if spec.font_id is not None:
        try:
            dpg.bind_font(spec.font_id)
        except Exception:
            pass


def _set_ui_scale(scale: float) -> None:
    try:
        dpg.set_global_font_scale(float(scale))
    except Exception:
        pass


# ------------------------------ logging ------------------------------

def _install_gui_logging(state: AppState, panel: LogPanel, *, level_name: str = "INFO") -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        try:
            root.removeHandler(h)
        except Exception:
            pass
    lvl = getattr(logging, str(level_name).upper(), logging.INFO)
    root.setLevel(lvl)
    h = DpgLogHandler(panel, level=lvl)
    h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    root.addHandler(h)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(lvl)
    sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    root.addHandler(sh)
    state.log_handler = h


def _set_log_level(level_name: str) -> None:
    lvl = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.getLogger().setLevel(lvl)
    for h in logging.getLogger().handlers:
        try:
            h.setLevel(lvl)
        except Exception:
            pass


# ------------------------------ text rendering ------------------------------

def _strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(text or ""))


def _gui_render_report(payload: dict[str, Any], *, show_speeds: bool = False, ratios_only: bool = False) -> str:
    """Render a GUI-safe plain-text report.

    The CLI intentionally uses Rich with forced terminal output, which emits
    ANSI color/control sequences and box-drawing glyphs. Dear PyGui input_text
    widgets do not render that reliably, so the GUI must use the plain renderer.
    """
    try:
        if _app_render_plain_report is not None:
            return str(_app_render_plain_report(payload, show_speeds=show_speeds, ratios_only=ratios_only))
    except Exception:
        pass
    try:
        return _strip_ansi(render_text_report(payload, show_speeds=show_speeds, ratios_only=ratios_only))
    except Exception:
        return pretty_json(payload)


def _estimate_scroll_text_width(text: str) -> int:
    """Best-effort width for readonly mono report widgets.

    Dear PyGui only shows a horizontal scrollbar when the child content is
    wider than the child window. A width=-1 input_text always fits the parent,
    so wide transmission tables get clipped. We therefore size the readonly
    input_text wider than the parent based on the longest line.
    """
    lines = str(text or "").splitlines() or [""]
    max_chars = max((len(line) for line in lines), default=0)
    # Empirical mono-char width that works well with the current UI scale/fonts.
    px = 40 + int(max_chars * 8.4)
    return max(900, min(px, 20000))


def _set_scrollable_report_text(tag: str, text: str) -> None:
    value = str(text or "")
    if dpg.does_item_exist(tag):
        dpg.set_value(tag, value)
        try:
            dpg.configure_item(tag, width=_estimate_scroll_text_width(value))
        except Exception:
            pass


# ------------------------------ dialogs ------------------------------

def _pick_spec_cb(sender, app_data, user_data) -> None:
    state, log = user_data["state"], user_data["log"]
    raw = extract_dpg_file_dialog_path(app_data)
    if not raw:
        return
    dpg.set_value(t("tr", "spec_path"), raw)
    state.last_spec_path = raw
    log.info(f"Selected spec: {raw}")
    _refresh_run_state_combo(state, log)


def _pick_schedule_cb(sender, app_data, user_data) -> None:
    state, log = user_data["state"], user_data["log"]
    raw = extract_dpg_file_dialog_path(app_data)
    if not raw:
        return
    dpg.set_value(t("tr", "schedule_path"), raw)
    state.last_schedule_path = raw
    log.info(f"Selected schedule: {raw}")
    _refresh_run_state_combo(state, log)


def _build_file_dialogs(state: AppState, log: LogPanel) -> None:
    with dpg.file_dialog(
        directory_selector=False,
        show=False,
        callback=_pick_spec_cb,
        tag=t("tr", "fd_spec"),
        user_data={"state": state, "log": log},
        width=780,
        height=500,
    ):
        dpg.add_file_extension(".json", color=(17, 24, 39, 255), tag=_file_dialog_extension_tag("spec", "json"))
        dpg.add_file_extension(".*", color=(17, 24, 39, 255), tag=_file_dialog_extension_tag("spec", "all"))
    with dpg.file_dialog(
        directory_selector=False,
        show=False,
        callback=_pick_schedule_cb,
        tag=t("tr", "fd_schedule"),
        user_data={"state": state, "log": log},
        width=780,
        height=500,
    ):
        dpg.add_file_extension(".json", color=(17, 24, 39, 255), tag=_file_dialog_extension_tag("schedule", "json"))
        dpg.add_file_extension(".*", color=(17, 24, 39, 255), tag=_file_dialog_extension_tag("schedule", "all"))


# ------------------------------ builders/helpers ------------------------------

def _selected_spec_path() -> str:
    return str(dpg.get_value(t("tr", "spec_path")) or "").strip()


def _selected_schedule_path() -> str:
    return str(dpg.get_value(t("tr", "schedule_path")) or "").strip()


def _refresh_spec_combo(state: AppState) -> None:
    items = [str(p) for p in list_spec_files(state.in_root)]
    dpg.configure_item(t("tr", "spec_pick"), items=[""] + items)


def _refresh_schedule_combo(state: AppState) -> None:
    items = [str(p) for p in list_schedule_files(state.in_root)]
    dpg.configure_item(t("tr", "schedule_pick"), items=[""] + items)


def _refresh_run_state_combo(state: AppState, log: LogPanel) -> None:
    path = _selected_schedule_path()
    items = ["all"]
    if path and Path(path).exists():
        try:
            data = load_json(path)
            states = data.get("display_order") if isinstance(data.get("display_order"), list) else list(data.get("states", {}).keys())
            items.extend([str(x) for x in states if str(x).strip()])
        except Exception as e:
            log.warn(f"Could not refresh state list from schedule: {e}")
    dpg.configure_item(t("tr", "state"), items=items)
    cur = str(dpg.get_value(t("tr", "state")) or "all")
    if cur not in items:
        dpg.set_value(t("tr", "state"), "all")


def _load_schedule_into_builder(log: LogPanel) -> None:
    path = _selected_schedule_path()
    if not path:
        log.warn("No schedule path selected.")
        return
    data = load_json(path)
    rich = False
    states = data.get("states", {})
    if isinstance(states, dict) and states:
        first = next(iter(states.values()))
        rich = isinstance(first, dict)
    dpg.set_value(t("tr", "schedule_rich_mode"), rich)
    dpg.set_value(t("tr", "schedule_filename"), Path(path).name)
    dpg.set_value(t("tr", "schedule_notes"), str(data.get("notes", "")))
    dpg.set_value(t("tr", "schedule_csv"), schedule_payload_to_csv(data, rich=rich))
    log.info(f"Loaded schedule into builder: {path}")


def _load_spec_into_builder(log: LogPanel) -> None:
    path = _selected_spec_path()
    if not path:
        log.warn("No spec path selected.")
        return
    data = load_json(path)
    ed = spec_payload_to_editors(data)
    dpg.set_value(t("tr", "spec_filename"), Path(path).name)
    dpg.set_value(t("tr", "spec_name"), ed["name"])
    dpg.set_value(t("tr", "input_member"), ed["input_member"])
    dpg.set_value(t("tr", "output_member"), ed["output_member"])
    dpg.set_value(t("tr", "strict_geometry"), ed["strict_geometry"] == "true")
    dpg.set_value(t("tr", "members_text"), ed["members_text"])
    dpg.set_value(t("tr", "speed_display_order_text"), ed["speed_display_order_text"])
    dpg.set_value(t("tr", "speed_display_labels_text"), ed["speed_display_labels_text"])
    dpg.set_value(t("tr", "gearsets_text"), ed["gearsets_text"])
    dpg.set_value(t("tr", "clutches_text"), ed["clutches_text"])
    dpg.set_value(t("tr", "brakes_text"), ed["brakes_text"])
    dpg.set_value(t("tr", "sprags_text"), ed["sprags_text"])
    dpg.set_value(t("tr", "permanent_ties_text"), ed["permanent_ties_text"])
    dpg.set_value(t("tr", "display_order_text"), ed["display_order_text"])
    dpg.set_value(t("tr", "state_aliases_text"), ed["state_aliases_text"])
    dpg.set_value(t("tr", "presets_text"), ed["presets_text"])
    dpg.set_value(t("tr", "spec_notes"), ed["notes"])
    dpg.set_value(t("tr", "meta_text"), ed["meta_text"])
    log.info(f"Loaded spec into builder: {path}")


def _create_schedule_from_builder(state: AppState, log: LogPanel) -> None:
    filename = str(dpg.get_value(t("tr", "schedule_filename")) or "").strip() or "shift_schedule_gui.json"
    if not filename.lower().endswith(".json"):
        filename += ".json"
    rich = bool(dpg.get_value(t("tr", "schedule_rich_mode")))
    csv_text = str(dpg.get_value(t("tr", "schedule_csv")) or "")
    payload = parse_shift_schedule_csv(csv_text, rich=rich)
    notes = str(dpg.get_value(t("tr", "schedule_notes")) or "").strip()
    if notes:
        payload["notes"] = notes
    path = state.in_root / filename
    save_json(path, payload)
    dpg.set_value(t("tr", "schedule_path"), str(path))
    state.last_schedule_path = str(path)
    _refresh_schedule_combo(state)
    _refresh_run_state_combo(state, log)
    dpg.set_value(t("tr", "schedule_json_preview"), pretty_json(payload))
    log.info(f"Created schedule JSON: {path}")


def _create_spec_from_builder(state: AppState, log: LogPanel) -> None:
    filename = str(dpg.get_value(t("tr", "spec_filename")) or "").strip() or "transmission_spec_gui.json"
    if not filename.lower().endswith(".json"):
        filename += ".json"
    payload = build_spec_payload(
        name=str(dpg.get_value(t("tr", "spec_name")) or ""),
        input_member=str(dpg.get_value(t("tr", "input_member")) or ""),
        output_member=str(dpg.get_value(t("tr", "output_member")) or ""),
        strict_geometry=bool(dpg.get_value(t("tr", "strict_geometry"))),
        members_text=str(dpg.get_value(t("tr", "members_text")) or ""),
        speed_display_order_text=str(dpg.get_value(t("tr", "speed_display_order_text")) or ""),
        speed_display_labels_text=str(dpg.get_value(t("tr", "speed_display_labels_text")) or ""),
        gearsets_text=str(dpg.get_value(t("tr", "gearsets_text")) or ""),
        clutches_text=str(dpg.get_value(t("tr", "clutches_text")) or ""),
        brakes_text=str(dpg.get_value(t("tr", "brakes_text")) or ""),
        sprags_text=str(dpg.get_value(t("tr", "sprags_text")) or ""),
        permanent_ties_text=str(dpg.get_value(t("tr", "permanent_ties_text")) or ""),
        display_order_text=str(dpg.get_value(t("tr", "display_order_text")) or ""),
        state_aliases_text=str(dpg.get_value(t("tr", "state_aliases_text")) or ""),
        presets_text=str(dpg.get_value(t("tr", "presets_text")) or ""),
        notes=str(dpg.get_value(t("tr", "spec_notes")) or ""),
        meta_text=str(dpg.get_value(t("tr", "meta_text")) or ""),
    )
    path = state.in_root / filename
    save_json(path, payload)
    dpg.set_value(t("tr", "spec_path"), str(path))
    state.last_spec_path = str(path)
    _refresh_spec_combo(state)
    dpg.set_value(t("tr", "spec_json_preview"), pretty_json(payload))
    log.info(f"Created spec JSON: {path}")


def _run_analysis(state: AppState, log: LogPanel, uiq: SimpleQueue[UiTask]) -> None:
    spec_path = _selected_spec_path()
    schedule_path = _selected_schedule_path()
    if not spec_path or not Path(spec_path).exists():
        log.warn("Pick or build a transmission spec JSON first.")
        return
    if not schedule_path or not Path(schedule_path).exists():
        log.warn("Pick or build a shift schedule JSON first.")
        return

    state_name = str(dpg.get_value(t("tr", "state")) or "all")
    input_speed = float(dpg.get_value(t("tr", "input_speed")) or 1.0)
    preset = str(dpg.get_value(t("tr", "preset")) or "").strip() or None
    show_speeds = bool(dpg.get_value(t("tr", "show_speeds")))
    ratios_only = bool(dpg.get_value(t("tr", "ratios_only")))
    show_topology = bool(dpg.get_value(t("tr", "show_topology")))
    overrides_text = str(dpg.get_value(t("tr", "overrides")) or "").strip()

    overrides: dict[str, Any] = {}
    for raw in overrides_text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            raise ValueError(f"Invalid override line: {s}")
        key, val = s.split("=", 1)
        vv = val.strip()
        low = vv.lower()
        if low in {"true", "false"}:
            parsed: Any = low == "true"
        else:
            try:
                parsed = int(vv)
            except Exception:
                try:
                    parsed = float(vv)
                except Exception:
                    parsed = vv
        overrides[key.strip()] = parsed

    out_name = str(dpg.get_value(t("tr", "output_json_name")) or "").strip()
    out_path = str((state.out_root / out_name).resolve()) if out_name else None

    req = RunRequest(
        spec_path=spec_path,
        schedule_path=schedule_path,
        preset=preset,
        state=state_name,
        input_speed=input_speed,
        show_speeds=show_speeds,
        ratios_only=ratios_only,
        show_topology=show_topology,
        as_json=False,
        output_json=out_path,
        overrides=overrides,
    )

    app = TransmissionApplication()
    log.set_status("Running analyzer…")
    log.info("Running analyzer…")

    def _work() -> dict[str, Any]:
        return app.run(req)

    def _done(res: TaskResult) -> None:
        def _apply() -> None:
            if not res.ok:
                log.error(f"Run failed: {res.error}")
                log.set_status("Run failed")
                return
            payload = res.value
            report_txt = _gui_render_report(payload, show_speeds=show_speeds, ratios_only=ratios_only)
            _set_scrollable_report_text(t("tr", "results_text"), report_txt)
            _set_scrollable_report_text(t("tr", "payload_text"), pretty_json(payload))
            topo = payload.get("topology", {}) if isinstance(payload, dict) else {}
            _set_scrollable_report_text(t("tr", "topology_text"), pretty_json(topo) if topo else "")
            if out_path:
                state.last_output_json = out_path
            state.history = state.history or []
            hist_entry = f"state={state_name} | spec={Path(spec_path).name} | schedule={Path(schedule_path).name}"
            state.history.insert(0, hist_entry)
            state.history = state.history[:50]
            dpg.configure_item(t("tr", "history_list"), items=state.history)
            log.set_status("Analyzer complete ✅")
        enqueue_task(uiq, _apply)

    run_task_async(_work, on_done=_done)


def _clear_spec_selection(state: AppState, log: LogPanel) -> None:
    for tag, val in (
        (t("tr", "spec_pick"), ""),
        (t("tr", "spec_path"), ""),
    ):
        if dpg.does_item_exist(tag):
            try:
                dpg.set_value(tag, val)
            except Exception:
                pass
    state.last_spec_path = ""
    log.info("Cleared selected spec file.")


def _clear_schedule_selection(state: AppState, log: LogPanel) -> None:
    for tag, val in (
        (t("tr", "schedule_pick"), ""),
        (t("tr", "schedule_path"), ""),
    ):
        if dpg.does_item_exist(tag):
            try:
                dpg.set_value(tag, val)
            except Exception:
                pass
    state.last_schedule_path = ""
    _refresh_run_state_combo(state, log)
    log.info("Cleared selected schedule file.")


def _clear_output_views(state: AppState, log: LogPanel) -> None:
    for tag in (t("tr", "results_text"), t("tr", "payload_text"), t("tr", "topology_text")):
        if dpg.does_item_exist(tag):
            try:
                dpg.set_value(tag, "")
                dpg.configure_item(tag, width=1600)
            except Exception:
                pass
    state.last_output_json = ""
    log.info("Cleared analyzer output panes.")


def _clear_left_inputs(state: AppState, log: LogPanel) -> None:
    _clear_spec_selection(state, log)
    _clear_schedule_selection(state, log)

    defaults: dict[str, Any] = {
        t("tr", "schedule_filename"): "shift_schedule_gui.json",
        t("tr", "schedule_rich_mode"): False,
        t("tr", "schedule_csv"): "",
        t("tr", "schedule_notes"): "",
        t("tr", "schedule_json_preview"): "",
        t("tr", "spec_filename"): "transmission_spec_gui.json",
        t("tr", "strict_geometry"): False,
        t("tr", "spec_name"): "",
        t("tr", "input_member"): "",
        t("tr", "output_member"): "",
        t("tr", "members_text"): "",
        t("tr", "speed_display_order_text"): "",
        t("tr", "speed_display_labels_text"): "",
        t("tr", "gearsets_text"): "",
        t("tr", "clutches_text"): "",
        t("tr", "brakes_text"): "",
        t("tr", "sprags_text"): "",
        t("tr", "permanent_ties_text"): "",
        t("tr", "display_order_text"): "",
        t("tr", "state_aliases_text"): "",
        t("tr", "presets_text"): "{}",
        t("tr", "meta_text"): "{}",
        t("tr", "spec_notes"): "",
        t("tr", "spec_json_preview"): "",
        t("tr", "state"): "all",
        t("tr", "preset"): "",
        t("tr", "input_speed"): 1.0,
        t("tr", "show_speeds"): True,
        t("tr", "ratios_only"): False,
        t("tr", "show_topology"): True,
        t("tr", "overrides"): "",
        t("tr", "output_json_name"): "transmission_gui_run.json",
    }

    for tag, val in defaults.items():
        if dpg.does_item_exist(tag):
            try:
                dpg.set_value(tag, val)
            except Exception:
                pass

    _refresh_run_state_combo(state, log)
    log.info("Cleared left-panel inputs for a fresh analysis.")


def _clear_all_for_new_analysis(state: AppState, log: LogPanel) -> None:
    _clear_left_inputs(state, log)
    _clear_output_views(state, log)
    log.set_status("Cleared ✅")


def _on_spec_combo_changed(sender, app_data, user_data) -> None:
    state, log = user_data["state"], user_data["log"]
    val = str(app_data or "").strip()
    dpg.set_value(t("tr", "spec_path"), val)
    state.last_spec_path = val
    if val:
        log.info(f"Selected spec: {val}")


def _on_schedule_combo_changed(sender, app_data, user_data) -> None:
    state, log = user_data["state"], user_data["log"]
    val = str(app_data or "").strip()
    dpg.set_value(t("tr", "schedule_path"), val)
    state.last_schedule_path = val
    _refresh_run_state_combo(state, log)
    if val:
        log.info(f"Selected schedule: {val}")


# ------------------------------ UI panes ------------------------------

def _build_shift_schedule_builder() -> None:
    with dpg.collapsing_header(label="Shift schedule builder", default_open=True):
        with dpg.group(horizontal=True):
            dpg.add_text("File name")
            dpg.add_input_text(tag=t("tr", "schedule_filename"), default_value="shift_schedule_gui.json", width=240)
            dpg.add_checkbox(label="Rich schema", tag=t("tr", "schedule_rich_mode"), default_value=False)
        dpg.add_input_text(
            tag=t("tr", "schedule_csv"),
            multiline=True,
            height=180,
            width=-1,
            hint=(
                "Simple mode example:\n"
                "1st, A, B, C\n2nd, A, B, E\nRev, A, B, D\n\n"
                "Rich mode example:\n"
                "state, active_constraints, display_elements, manual_neutral, notes\n"
                "N, C3|B1, C3|B1, true, Neutral"
            ),
        )
        dpg.add_input_text(tag=t("tr", "schedule_notes"), width=-1, hint="Optional schedule notes")
        dpg.add_input_text(tag=t("tr", "schedule_json_preview"), multiline=True, readonly=True, height=120, width=-1)


def _build_spec_builder() -> None:
    with dpg.collapsing_header(label="Transmission spec builder", default_open=True):
        with dpg.group(horizontal=True):
            dpg.add_text("File name")
            dpg.add_input_text(tag=t("tr", "spec_filename"), default_value="transmission_spec_gui.json", width=260)
            dpg.add_checkbox(label="Strict geometry", tag=t("tr", "strict_geometry"), default_value=False)
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag=t("tr", "spec_name"), width=280, hint="Transmission name")
            dpg.add_input_text(tag=t("tr", "input_member"), width=160, hint="input_member")
            dpg.add_input_text(tag=t("tr", "output_member"), width=160, hint="output_member")

        with dpg.tab_bar():
            with dpg.tab(label="Core"):
                dpg.add_text("Members (one per line or comma-separated)")
                dpg.add_input_text(tag=t("tr", "members_text"), multiline=True, height=110, width=-1)
                dpg.add_text("Speed display order")
                dpg.add_input_text(tag=t("tr", "speed_display_order_text"), multiline=True, height=90, width=-1)
                dpg.add_text("Speed display labels (member,label)")
                dpg.add_input_text(tag=t("tr", "speed_display_labels_text"), multiline=True, height=90, width=-1)
                dpg.add_text("Display order (states, one per line)")
                dpg.add_input_text(tag=t("tr", "display_order_text"), multiline=True, height=90, width=-1)

            with dpg.tab(label="Topology"):
                dpg.add_text("Gearsets CSV: name,Ns,Nr,sun,ring,carrier")
                dpg.add_input_text(tag=t("tr", "gearsets_text"), multiline=True, height=120, width=-1)
                dpg.add_text("Clutches CSV: name,a,b")
                dpg.add_input_text(tag=t("tr", "clutches_text"), multiline=True, height=80, width=-1)
                dpg.add_text("Brakes CSV: name,member")
                dpg.add_input_text(tag=t("tr", "brakes_text"), multiline=True, height=80, width=-1)
                dpg.add_text("Sprags CSV: name,member,hold_direction,locked_when_engaged")
                dpg.add_input_text(tag=t("tr", "sprags_text"), multiline=True, height=80, width=-1)
                dpg.add_text("Permanent ties CSV: member_a,member_b")
                dpg.add_input_text(tag=t("tr", "permanent_ties_text"), multiline=True, height=70, width=-1)

            with dpg.tab(label="States / presets"):
                dpg.add_text("State aliases CSV: alias,canonical_state")
                dpg.add_input_text(tag=t("tr", "state_aliases_text"), multiline=True, height=90, width=-1)
                dpg.add_text("Presets JSON object")
                dpg.add_input_text(tag=t("tr", "presets_text"), multiline=True, height=130, width=-1, default_value="{}")
                dpg.add_text("Meta JSON object")
                dpg.add_input_text(tag=t("tr", "meta_text"), multiline=True, height=90, width=-1, default_value="{}")
                dpg.add_text("Spec notes")
                dpg.add_input_text(tag=t("tr", "spec_notes"), multiline=True, height=80, width=-1)

        dpg.add_input_text(tag=t("tr", "spec_json_preview"), multiline=True, readonly=True, height=140, width=-1)



def _build_inputs_panel(state: AppState, log: LogPanel, uiq: SimpleQueue[UiTask]) -> None:
    dpg.add_text("Existing input files")
    with dpg.group(horizontal=True):
        dpg.add_button(label="📂 Browse spec", callback=lambda: dpg.show_item(t("tr", "fd_spec")))
        dpg.add_button(label="📂 Browse schedule", callback=lambda: dpg.show_item(t("tr", "fd_schedule")))
        dpg.add_button(label="🗂 Open in/", callback=lambda: open_path(state.in_root))
    with dpg.group(horizontal=True):
        dpg.add_text("Spec")
        dpg.add_combo(items=[""], tag=t("tr", "spec_pick"), width=280, callback=_on_spec_combo_changed, user_data={"state": state, "log": log})
        dpg.add_button(label="↺ Refresh", callback=lambda: _clear_spec_selection(state, log))
        dpg.add_button(label="Load → builder", callback=lambda: _load_spec_into_builder(log))
    dpg.add_input_text(tag=t("tr", "spec_path"), width=-1, hint="Path to transmission spec JSON")
    with dpg.group(horizontal=True):
        dpg.add_text("Schedule")
        dpg.add_combo(items=[""], tag=t("tr", "schedule_pick"), width=280, callback=_on_schedule_combo_changed, user_data={"state": state, "log": log})
        dpg.add_button(label="↺ Refresh", callback=lambda: _clear_schedule_selection(state, log))
        dpg.add_button(label="Load → builder", callback=lambda: _load_schedule_into_builder(log))
    dpg.add_input_text(tag=t("tr", "schedule_path"), width=-1, hint="Path to shift schedule JSON")

    _build_shift_schedule_builder()
    with dpg.group(horizontal=True):
        dpg.add_button(label="Create schedule JSON", callback=lambda: _create_schedule_from_builder(state, log))
        dpg.add_button(label="Open selected schedule", callback=lambda: open_path(_selected_schedule_path()))

    _build_spec_builder()
    with dpg.group(horizontal=True):
        dpg.add_button(label="Create spec JSON", callback=lambda: _create_spec_from_builder(state, log))
        dpg.add_button(label="Open selected spec", callback=lambda: open_path(_selected_spec_path()))

    with dpg.group(horizontal=True):
        dpg.add_button(label="🧹 Clear left inputs", callback=lambda: _clear_left_inputs(state, log))
        dpg.add_button(label="🧼 New analysis", callback=lambda: _clear_all_for_new_analysis(state, log))

    with dpg.collapsing_header(label="Analyzer controls", default_open=True):
        with dpg.group(horizontal=True):
            dpg.add_text("State")
            dpg.add_combo(items=["all"], default_value="all", tag=t("tr", "state"), width=140)
            dpg.add_text("Preset")
            dpg.add_input_text(tag=t("tr", "preset"), width=160, hint="optional preset")
            dpg.add_text("Input speed")
            dpg.add_input_float(tag=t("tr", "input_speed"), width=140, default_value=1.0)
        with dpg.group(horizontal=True):
            dpg.add_checkbox(label="Show speeds", tag=t("tr", "show_speeds"), default_value=True)
            dpg.add_checkbox(label="Ratios only", tag=t("tr", "ratios_only"), default_value=False)
            dpg.add_checkbox(label="Show topology", tag=t("tr", "show_topology"), default_value=True)
        dpg.add_text("Overrides (one KEY=VALUE per line, e.g. P1.Ns=48)")
        dpg.add_input_text(tag=t("tr", "overrides"), multiline=True, height=90, width=-1)
        with dpg.group(horizontal=True):
            dpg.add_text("Output JSON file")
            dpg.add_input_text(tag=t("tr", "output_json_name"), width=260, default_value="transmission_gui_run.json")
            dpg.add_button(label="▶ Run analyzer", callback=lambda: _run_analysis(state, log, uiq))
            dpg.add_button(label="🗂 Open out/", callback=lambda: open_path(state.out_root))



def _build_outputs_panel(state: AppState, log: LogPanel) -> None:
    with dpg.tab_bar():
        with dpg.tab(label="Tables"):
            with dpg.group(horizontal=True):
                dpg.add_button(label="🧹 Clear table", callback=lambda: _clear_output_views(state, log))
                dpg.add_text("Clear the current analyzer output before starting a new case.")
            with dpg.child_window(height=-1, width=-1, border=False, horizontal_scrollbar=True):
                dpg.add_input_text(tag=t("tr", "results_text"), multiline=True, readonly=True, height=-1, width=1600)
                if state.mono_font is not None:
                    dpg.bind_item_font(t("tr", "results_text"), state.mono_font)
        with dpg.tab(label="Payload"):
            with dpg.child_window(height=-1, width=-1, border=False, horizontal_scrollbar=True):
                dpg.add_input_text(tag=t("tr", "payload_text"), multiline=True, readonly=True, height=-1, width=1600)
                if state.mono_font is not None:
                    dpg.bind_item_font(t("tr", "payload_text"), state.mono_font)
        with dpg.tab(label="Topology"):
            with dpg.child_window(height=-1, width=-1, border=False, horizontal_scrollbar=True):
                dpg.add_input_text(tag=t("tr", "topology_text"), multiline=True, readonly=True, height=-1, width=1600)
                if state.mono_font is not None:
                    dpg.bind_item_font(t("tr", "topology_text"), state.mono_font)
        with dpg.tab(label="Logs"):
            with dpg.child_window(height=-1, width=-1, border=False):
                log.build(height=-1, mono_font=state.mono_font)
        with dpg.tab(label="History"):
            dpg.add_text("Recent GUI runs")
            dpg.add_listbox(items=[], tag=t("tr", "history_list"), width=-1, num_items=14)


# ------------------------------ main ------------------------------

def main() -> int:
    repo = find_repo_root()
    state = AppState(repo_root=repo, in_root=ensure_dir(in_dir(repo)), out_root=ensure_dir(out_dir(repo)), history=[])

    dpg.create_context()
    _load_fonts(state)
    dpg.create_viewport(title="Transmissions GUI (Dear PyGui)", width=1520, height=980)

    theme_light = _make_theme_light()
    theme_dark = _make_theme_dark()
    theme_macos = _make_theme_macos()
    theme_labview = _make_theme_labview()
    fd_theme_light = _make_file_dialog_theme(text_rgb=(17, 24, 39))
    fd_theme_dark = _make_file_dialog_theme(text_rgb=(233, 236, 239))
    fd_theme_macos = _make_file_dialog_theme(text_rgb=(28, 28, 30))
    fd_theme_labview = _make_file_dialog_theme(text_rgb=(30, 31, 34))
    themes: dict[str, ThemeSpec] = {
        "light": ThemeSpec("Light", "light", theme_light, fd_theme_light, state.ui_font_default),
        "dark": ThemeSpec("Dark", "dark", theme_dark, fd_theme_dark, state.ui_font_default),
        "macos": ThemeSpec("macOS", "macos", theme_macos, fd_theme_macos, state.ui_font_macos),
        "labview": ThemeSpec("LabVIEW", "labview", theme_labview, fd_theme_labview, state.ui_font_labview),
    }
    _apply_theme("Light", themes)
    _set_ui_scale(DEFAULT_UI_SCALE)

    log = LogPanel(tag_level=t("tr", "log_level"), tag_box=t("tr", "log_box"), tag_status=t("tr", "log_status"), tag_clear_btn=t("tr", "log_clear"))
    uiq: SimpleQueue[UiTask] = SimpleQueue()

    _build_file_dialogs(state, log)

    with dpg.window(label="Transmissions GUI", width=-1, height=-1):
        with dpg.group(horizontal=True):
            dpg.add_text("Transmissions • Universal Analyzer GUI ✨")
            dpg.add_spacer(width=18)
            dpg.add_text("Theme:")
            dpg.add_combo(items=["Light", "Dark", "macOS", "LabVIEW"], default_value="Light", width=120, callback=lambda s, a, u: _apply_theme(str(a), themes))
            dpg.add_spacer(width=14)
            dpg.add_text("UI scale:")
            dpg.add_slider_float(default_value=DEFAULT_UI_SCALE, min_value=0.85, max_value=1.60, width=180, callback=lambda s, a, u: _set_ui_scale(a))
            dpg.add_spacer(width=14)
            dpg.add_text("Log level:")
            dpg.add_combo(items=["DEBUG", "INFO", "WARNING", "ERROR"], default_value="INFO", width=110, callback=lambda s, a, u: _set_log_level(a))

        with dpg.collapsing_header(label="Paths (click to expand)", default_open=False):
            dpg.add_text(f"root: {state.repo_root}")
            dpg.add_text(f"in:   {state.in_root}")
            dpg.add_text(f"out:  {state.out_root}")

        dpg.add_separator()
        with dpg.group(horizontal=True):
            with dpg.child_window(width=LEFT_PANEL_WIDTH, height=-1, border=False):
                _build_inputs_panel(state, log, uiq)
            with dpg.child_window(width=-1, height=-1, border=False):
                _build_outputs_panel(state, log)

    dpg.setup_dearpygui()
    dpg.show_viewport()

    _install_gui_logging(state, log, level_name="INFO")
    _refresh_spec_combo(state)
    _refresh_schedule_combo(state)
    _refresh_run_state_combo(state, log)

    def _on_frame() -> None:
        log.drain(max_lines=250)
        drain_tasks(uiq, max_tasks=60)

    while dpg.is_dearpygui_running():
        _on_frame()
        dpg.render_dearpygui_frame()

    dpg.destroy_context()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
