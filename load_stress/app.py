from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

try:
    from .apis import SolverAPI, SolverRequest
    from .core import StressTensorInput
    from .in_out import write_json
    from .utils import default_json_output_path, default_plot_output_path, render_dashboard
except ImportError:
    from apis import SolverAPI, SolverRequest
    from core import StressTensorInput
    from in_out import write_json
    from utils import default_json_output_path, default_plot_output_path, render_dashboard


class LoadStressApp:
    def __init__(self) -> None:
        self.api = SolverAPI()

    def solve_flags(
        self,
        *,
        solve_path: str,
        sxx: float,
        syy: float,
        szz: float,
        txy: float = 0.0,
        tyz: float = 0.0,
        txz: float = 0.0,
        phi_deg: Optional[float] = None,
        unit: str = "",
        title: str = "",
        outfile: Optional[str] = None,
        plotfile: Optional[str] = None,
        pretty: bool = True,
        make_plot: bool = True,
        show_plot: bool = False,
    ) -> dict:
        request = SolverRequest(
            solve_path=solve_path,
            inputs=StressTensorInput(
                sxx=sxx,
                syy=syy,
                szz=szz,
                txy=txy,
                tyz=tyz,
                txz=txz,
                phi_deg=phi_deg,
                unit=unit,
                title=title,
            ),
        )
        result = self.api.solve(request)
        payload = asdict(result)

        stem = solve_path
        outfile_path = Path(outfile).expanduser().resolve() if outfile else default_json_output_path(stem)
        plotfile_path = Path(plotfile).expanduser().resolve() if plotfile else default_plot_output_path(stem)

        payload.setdefault("artifacts", {})
        payload["artifacts"]["json_output"] = str(write_json(payload, outfile_path, pretty=pretty))
        if make_plot:
            payload["artifacts"]["plot_output"] = str(render_dashboard(payload, plotfile_path, show_plot=show_plot))
            write_json(payload, outfile_path, pretty=pretty)
        return payload
