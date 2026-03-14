from __future__ import annotations

"""transmissions.gui_utils_trans

Utility helpers for the Dear PyGui frontend for the universal transmissions app.

This mirrors the style of the circuits GUI utilities but targets the JSON-based
transmission analyzer workflow:
- repo root discovery
- in/out folder helpers
- file-dialog path normalization
- JSON/text IO helpers
- background task runners
- lightweight CSV-ish parsing helpers for builder panes
"""

import csv
import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Iterable, List, Mapping, Optional, Sequence


# ------------------------------ paths ------------------------------

def find_repo_root(start: Optional[str | Path] = None) -> Path:
    """Best-effort repo root discovery.

    Supports either:
    - flat-layout project with app.py/model.py at root
    - package layout with transmissions/__init__.py
    """
    candidates: list[Path] = []
    if start is not None:
        candidates.append(Path(start).resolve())
    candidates.append(Path.cwd().resolve())
    candidates.append(Path(__file__).resolve().parent)

    markers = [
        lambda d: (d / "transmissions" / "__init__.py").exists(),
        lambda d: (d / "app.py").exists() and (d / "model.py").exists(),
    ]

    for base in candidates:
        d = base
        for _ in range(40):
            if any(fn(d) for fn in markers):
                return d
            if d.parent == d:
                break
            d = d.parent
    return Path.cwd().resolve()


def _has_package_layout(repo_root: Path) -> bool:
    return (repo_root / "transmissions" / "__init__.py").exists()


def in_dir(repo_root: Path) -> Path:
    if _has_package_layout(repo_root):
        return (repo_root / "transmissions" / "in").resolve()
    return (repo_root / "in").resolve()


def out_dir(repo_root: Path) -> Path:
    if _has_package_layout(repo_root):
        return (repo_root / "transmissions" / "out").resolve()
    return (repo_root / "out").resolve()


def ensure_dir(p: str | Path) -> Path:
    pp = Path(p).expanduser().resolve()
    pp.mkdir(parents=True, exist_ok=True)
    return pp


def unique_path(base: Path) -> Path:
    base = Path(base)
    if not base.exists():
        return base
    for k in range(1, 10000):
        cand = base.with_name(f"{base.stem}_{k}{base.suffix}")
        if not cand.exists():
            return cand
    return base.with_name(f"{base.stem}_{os.getpid()}{base.suffix}")


# ------------------------------ file-dialog helpers ------------------------------

def extract_dpg_file_dialog_path(app_data: Any) -> str:
    if not isinstance(app_data, dict):
        return ""
    sels = app_data.get("selections")
    if isinstance(sels, dict) and sels:
        try:
            return str(next(iter(sels.values())))
        except Exception:
            pass
    for key in ("file_path_name", "file_path", "path"):
        val = app_data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


# ------------------------------ OS helpers ------------------------------

def open_path(path: str | os.PathLike[str] | Path) -> bool:
    p = Path(path).expanduser()
    if not p.exists():
        return False
    try:
        if sys.platform.startswith("darwin"):
            subprocess.Popen(["open", str(p)])
            return True
        if os.name == "nt":
            os.startfile(str(p))  # type: ignore[attr-defined]
            return True
        subprocess.Popen(["xdg-open", str(p)])
        return True
    except Exception:
        return False


# ------------------------------ IO helpers ------------------------------

def load_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def save_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object/dict: {path}")
    return data


def save_json(path: str | Path, payload: Mapping[str, Any], *, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(dict(payload), f, indent=indent, sort_keys=False, ensure_ascii=False)
        f.write("\n")


def pretty_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)


# ------------------------------ list helpers ------------------------------

def list_json_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files = [p for p in root.rglob("*.json") if p.is_file()]
    return sorted(files, key=lambda p: str(p).lower())


def list_schedule_files(root: Path) -> list[Path]:
    files = list_json_files(root)
    out: list[Path] = []
    for p in files:
        name = p.name.lower()
        if "schedule" in name:
            out.append(p)
            continue
        try:
            data = load_json(p)
            if isinstance(data.get("states"), dict):
                out.append(p)
        except Exception:
            continue
    return sorted(dict.fromkeys(out), key=lambda p: str(p).lower())


def list_spec_files(root: Path) -> list[Path]:
    files = list_json_files(root)
    out: list[Path] = []
    for p in files:
        name = p.name.lower()
        if "spec" in name:
            out.append(p)
            continue
        try:
            data = load_json(p)
            if isinstance(data.get("gearsets"), list) and data.get("input_member"):
                out.append(p)
        except Exception:
            continue
    return sorted(dict.fromkeys(out), key=lambda p: str(p).lower())


# ------------------------------ CSV-ish parsing ------------------------------

def nonempty_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def parse_csv_lines(text: str) -> list[list[str]]:
    lines = nonempty_lines(text)
    if not lines:
        return []
    buf = StringIO("\n".join(lines))
    rows: list[list[str]] = []
    for row in csv.reader(buf, skipinitialspace=True):
        cleaned = [str(x).strip() for x in row]
        if cleaned and any(x != "" for x in cleaned):
            rows.append(cleaned)
    return rows


def parse_name_list(text: str) -> list[str]:
    out: list[str] = []
    for raw in (text or "").replace(",", "\n").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def parse_bool(text: Any, default: bool = False) -> bool:
    if isinstance(text, bool):
        return text
    s = str(text or "").strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


# ------------------------------ threaded runners ------------------------------

@dataclass
class TaskResult:
    ok: bool
    value: Any
    error: str = ""


def run_task_async(
    fn: Callable[[], Any],
    *,
    on_done: Optional[Callable[[TaskResult], None]] = None,
) -> threading.Thread:
    def _worker() -> None:
        try:
            val = fn()
            res = TaskResult(ok=True, value=val)
        except Exception as e:
            res = TaskResult(ok=False, value=None, error=f"{type(e).__name__}: {e}")
        if on_done:
            on_done(res)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
