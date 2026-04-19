from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, TypeVar

T = TypeVar("T")

logger = logging.getLogger("beams")


# ------------------------------ decorators ------------------------------

def timed(fn: Callable[..., T]) -> Callable[..., T]:
    """Decorator that measures runtime and logs it at DEBUG level."""
    def wrapper(*args: Any, **kwargs: Any) -> T:
        t0 = time.perf_counter()
        out = fn(*args, **kwargs)
        dt = time.perf_counter() - t0
        logger.debug("timed: %s took %.6fs", fn.__qualname__, dt)
        return out
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    wrapper.__qualname__ = fn.__qualname__
    return wrapper


# ------------------------------ guards ------------------------------

def require(condition: bool, msg: str) -> None:
    """Raise ValueError if condition is False."""
    if not condition:
        raise ValueError(msg)


def ensure_unique(values: Iterable[str], *, what: str) -> None:
    seen: set[str] = set()
    dups: list[str] = []
    for v in values:
        if v in seen:
            dups.append(v)
        seen.add(v)
    require(not dups, f"Duplicate {what}: {sorted(set(dups))}")


# ------------------------------ json helpers ------------------------------

def read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, data: Mapping[str, Any], *, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, sort_keys=False)


# ------------------------------ issues ------------------------------

@dataclass(frozen=True)
class Issue:
    """Validation/reporting issue container."""
    level: str  # "warning" or "error"
    message: str
    path: str | None = None
