#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""transmissions.gui_log_trans

Logging panel + GUI logging handler for the Dear PyGui transmissions GUI.
"""

from dataclasses import dataclass, field
from datetime import datetime
from queue import SimpleQueue
import logging
import re

try:
    import dearpygui.dearpygui as dpg
except Exception:  # pragma: no cover
    dpg = None  # type: ignore


_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"]


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _norm_level(s: str) -> str:
    s = str(s or "").strip().upper()
    if s in ("WARNING", "WARN"):
        return "WARN"
    if s in _LEVELS:
        return s
    return "INFO"


@dataclass
class LogPanel:
    tag_level: str = "##trans_log_level"
    tag_box: str = "##trans_log_box"
    tag_status: str = "##trans_log_status"
    tag_clear_btn: str = "##trans_log_clear"
    default_level: str = "INFO"
    max_chars: int = 250_000

    _queue: SimpleQueue[str] = field(default_factory=SimpleQueue, init=False)
    _level_value: str = field(default="INFO", init=False)
    _text: str = field(default="", init=False)

    def build(self, parent: object | None = None, *, height: int = 240, mono_font: int | None = None) -> None:
        if dpg is None:
            raise RuntimeError("Dear PyGui is not installed.")

        kwargs = {"parent": parent} if parent is not None else {}
        with dpg.group(**kwargs):
            with dpg.group(horizontal=True):
                dpg.add_text("Log:")
                dpg.add_combo(
                    items=_LEVELS,
                    default_value=_norm_level(self.default_level),
                    width=110,
                    tag=self.tag_level,
                    callback=lambda s, a, u: self._on_level_changed(a),
                )
                dpg.add_button(label="🧹 Clear", tag=self.tag_clear_btn, callback=lambda: self.clear())
                dpg.add_spacer(width=12)
                dpg.add_text("", tag=self.tag_status)

            dpg.add_input_text(tag=self.tag_box, multiline=True, readonly=True, width=-1, height=height)

        self._level_value = _norm_level(self.default_level)
        dpg.set_value(self.tag_box, "")
        if mono_font is not None and dpg.does_item_exist(self.tag_box):
            try:
                dpg.bind_item_font(self.tag_box, mono_font)
            except Exception:
                pass

    def clear(self) -> None:
        self._text = ""
        if dpg is not None and dpg.does_item_exist(self.tag_box):
            dpg.set_value(self.tag_box, "")

    def debug(self, msg: str) -> None:
        self._enqueue("DEBUG", msg)

    def info(self, msg: str) -> None:
        self._enqueue("INFO", msg)

    def warn(self, msg: str) -> None:
        self._enqueue("WARN", msg)

    def error(self, msg: str) -> None:
        self._enqueue("ERROR", msg)

    def set_status(self, msg: str) -> None:
        if dpg is not None and dpg.does_item_exist(self.tag_status):
            dpg.set_value(self.tag_status, str(msg))

    def _on_level_changed(self, value: str) -> None:
        self._level_value = _norm_level(value)

    def _enqueue(self, level: str, msg: str) -> None:
        self._queue.put(f"[{_ts()}] {_norm_level(level)}: {msg}")

    def _level_allows(self, level: str) -> bool:
        try:
            idx = _LEVELS.index(_norm_level(level))
            cur = _LEVELS.index(_norm_level(self._level_value))
            return idx >= cur
        except Exception:
            return True

    def drain(self, *, max_lines: int = 200) -> None:
        if dpg is None:
            return
        added = 0
        while added < max_lines:
            try:
                line = self._queue.get_nowait()
            except Exception:
                break
            m = re.match(r"^\[\d\d:\d\d:\d\d\]\s+([A-Z]+):", line)
            lvl = m.group(1) if m else "INFO"
            if self._level_allows(lvl):
                self._text += line + "\n"
            added += 1
        if added == 0:
            return
        if len(self._text) > self.max_chars:
            self._text = self._text[-self.max_chars :]
        if dpg.does_item_exist(self.tag_box):
            dpg.set_value(self.tag_box, self._text)


class DpgLogHandler(logging.Handler):
    def __init__(self, panel: LogPanel, *, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._panel = panel

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        lvl = _norm_level(record.levelname)
        if lvl == "DEBUG":
            self._panel.debug(msg)
        elif lvl == "INFO":
            self._panel.info(msg)
        elif lvl == "WARN":
            self._panel.warn(msg)
        else:
            self._panel.error(msg)
