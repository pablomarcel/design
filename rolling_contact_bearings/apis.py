from __future__ import annotations

from typing import Any, Dict

# Import shim:
# - supports package execution
# - supports local module execution from inside rolling_contact_bearings/
try:
    from .app import RollingBearingsApp
except ImportError:
    from app import RollingBearingsApp


def solve(payload: Dict[str, Any]) -> Dict[str, Any]:
    app = RollingBearingsApp()
    return app.solve_payload(payload)
