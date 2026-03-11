from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


_BASE_DIR = Path(__file__).resolve().parent


def load_local_module(module_name: str, filename: str) -> ModuleType:
    """
    Load a sibling .py file as a module under a safe synthetic name.

    This is used for flat-layout execution such as:
        python -m cli

    where relative imports fail, and where some filenames (like io.py)
    would otherwise collide with Python stdlib modules.
    """
    synthetic_name = f"_tx_local_{module_name}"
    if synthetic_name in sys.modules:
        return sys.modules[synthetic_name]

    path = _BASE_DIR / filename
    spec = importlib.util.spec_from_file_location(synthetic_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load local module '{filename}' from '{path}'.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[synthetic_name] = module
    spec.loader.exec_module(module)
    return module