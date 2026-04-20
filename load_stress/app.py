from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

try:
    from .apis import SolverAPI, SolverRequest
    from .core import StrainTensorInput, StressTensorInput
    from .in_out import write_json
    from .utils import default_json_output_path, default_plot_output_path, render_dashboard
except ImportError:
    from apis import SolverAPI, SolverRequest
    from core import StrainTensorInput, StressTensorInput
    from in_out import write_json
    from utils import default_json_output_path, default_plot_output_path, render_dashboard


class LoadStressApp:
    def __init__(self) -> None:
        self.api = SolverAPI()

    def solve_flags(
        self,
        *,
        solve_path: str,
        sxx: Optional[float] = None,
        syy: Optional[float] = None,
        szz: Optional[float] = None,
        txy: float = 0.0,
        tyz: float = 0.0,
        txz: float = 0.0,
        exx: Optional[float] = None,
        eyy: Optional[float] = None,
        ezz: Optional[float] = None,
        gxy: float = 0.0,
        gyz: float = 0.0,
        gxz: float = 0.0,
        phi_deg: Optional[float] = None,
        unit: str = "",
        title: str = "",
        outfile: Optional[str] = None,
        plotfile: Optional[str] = None,
        pretty: bool = True,
        make_plot: bool = True,
        show_plot: bool = False,
    ) -> dict:
        if "strain" in solve_path:
            missing = [name for name, value in {"exx": exx, "eyy": eyy, "ezz": ezz}.items() if value is None]
            if missing:
                raise ValueError(f"Missing required strain flags for {solve_path}: {', '.join(missing)}")
            inputs = StrainTensorInput(
                exx=float(exx),
                eyy=float(eyy),
                ezz=float(ezz),
                gxy=float(gxy),
                gyz=float(gyz),
                gxz=float(gxz),
                phi_deg=phi_deg,
                unit=unit,
                title=title,
            )
        else:
            missing = [name for name, value in {"sxx": sxx, "syy": syy, "szz": szz}.items() if value is None]
            if missing:
                raise ValueError(f"Missing required stress flags for {solve_path}: {', '.join(missing)}")
            inputs = StressTensorInput(
                sxx=float(sxx),
                syy=float(syy),
                szz=float(szz),
                txy=float(txy),
                tyz=float(tyz),
                txz=float(txz),
                phi_deg=phi_deg,
                unit=unit,
                title=title,
            )

        request = SolverRequest(solve_path=solve_path, inputs=inputs)
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
