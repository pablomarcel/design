from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

try:
    from .apis import SolverAPI, SolverRequest
    from .core import Hooke3DFromStrainInput, RosetteInput, SingleGaugePlaneStressInput, StrainTensorInput, StressTensorInput
    from .in_out import write_json
    from .utils import default_json_output_path, default_plot_output_path, render_dashboard
except ImportError:
    from apis import SolverAPI, SolverRequest
    from core import Hooke3DFromStrainInput, RosetteInput, SingleGaugePlaneStressInput, StrainTensorInput, StressTensorInput
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
        ea: Optional[float] = None,
        eb: Optional[float] = None,
        ec: Optional[float] = None,
        theta_a_deg: Optional[float] = None,
        theta_b_deg: Optional[float] = None,
        theta_c_deg: Optional[float] = None,
        epsilon_theta: Optional[float] = None,
        theta_deg: Optional[float] = None,
        known_sigma_x: Optional[float] = None,
        E: Optional[float] = None,
        nu: Optional[float] = None,
        G: Optional[float] = None,
        phi_deg: Optional[float] = None,
        unit: str = "",
        strain_unit: str = "",
        stress_unit: str = "",
        title: str = "",
        outfile: Optional[str] = None,
        plotfile: Optional[str] = None,
        pretty: bool = True,
        make_plot: bool = True,
        show_plot: bool = False,
    ) -> dict:
        strain_unit = strain_unit or unit
        stress_unit = stress_unit or unit

        if solve_path in {'general_3d_stress', 'plane_stress_rotation'}:
            missing = [name for name, value in {'sxx': sxx, 'syy': syy, 'szz': szz}.items() if value is None]
            if missing:
                raise ValueError(f"Missing required stress flags for {solve_path}: {', '.join(missing)}")
            inputs = StressTensorInput(
                sxx=float(sxx), syy=float(syy), szz=float(szz),
                txy=float(txy), tyz=float(tyz), txz=float(txz),
                phi_deg=phi_deg, unit=stress_unit, title=title,
            )
        elif solve_path in {'general_3d_strain', 'plane_strain_rotation'}:
            missing = [name for name, value in {'exx': exx, 'eyy': eyy, 'ezz': ezz}.items() if value is None]
            if missing:
                raise ValueError(f"Missing required strain flags for {solve_path}: {', '.join(missing)}")
            inputs = StrainTensorInput(
                exx=float(exx), eyy=float(eyy), ezz=float(ezz),
                gxy=float(gxy), gyz=float(gyz), gxz=float(gxz),
                phi_deg=phi_deg, unit=strain_unit, title=title,
            )
        elif solve_path in {'strain_rosette_rectangular', 'strain_rosette_equiangular', 'strain_rosette_general'}:
            missing = [name for name, value in {'ea': ea, 'eb': eb, 'ec': ec}.items() if value is None]
            if missing:
                raise ValueError(f"Missing required rosette strains for {solve_path}: {', '.join(missing)}")
            if solve_path == 'strain_rosette_rectangular':
                theta_a_deg = 0.0 if theta_a_deg is None else theta_a_deg
                theta_b_deg = 45.0 if theta_b_deg is None else theta_b_deg
                theta_c_deg = 90.0 if theta_c_deg is None else theta_c_deg
            elif solve_path == 'strain_rosette_equiangular':
                theta_a_deg = 0.0 if theta_a_deg is None else theta_a_deg
                theta_b_deg = 120.0 if theta_b_deg is None else theta_b_deg
                theta_c_deg = 240.0 if theta_c_deg is None else theta_c_deg
            else:
                angle_missing = [name for name, value in {'theta_a_deg': theta_a_deg, 'theta_b_deg': theta_b_deg, 'theta_c_deg': theta_c_deg}.items() if value is None]
                if angle_missing:
                    raise ValueError(f"Missing required rosette angle flags for {solve_path}: {', '.join(angle_missing)}")
            inputs = RosetteInput(
                ea=float(ea), eb=float(eb), ec=float(ec),
                theta_a_deg=float(theta_a_deg), theta_b_deg=float(theta_b_deg), theta_c_deg=float(theta_c_deg),
                unit=strain_unit, title=title, E=E, nu=nu, G=G, stress_unit=stress_unit, phi_deg=phi_deg,
            )
        elif solve_path == 'hooke_3d_from_strain':
            missing = [name for name, value in {'exx': exx, 'eyy': eyy, 'ezz': ezz, 'E': E}.items() if value is None]
            if missing:
                raise ValueError(f"Missing required flags for {solve_path}: {', '.join(missing)}")
            inputs = Hooke3DFromStrainInput(
                exx=float(exx), eyy=float(eyy), ezz=float(ezz),
                gxy=float(gxy), gyz=float(gyz), gxz=float(gxz),
                E=float(E), nu=nu, G=G, unit=strain_unit, stress_unit=stress_unit, title=title,
            )
        elif solve_path == 'single_gauge_biaxial_plane_stress':
            missing = [name for name, value in {'epsilon_theta': epsilon_theta, 'theta_deg': theta_deg, 'known_sigma_x': known_sigma_x, 'E': E}.items() if value is None]
            if missing:
                raise ValueError(f"Missing required flags for {solve_path}: {', '.join(missing)}")
            inputs = SingleGaugePlaneStressInput(
                epsilon_theta=float(epsilon_theta), theta_deg=float(theta_deg), sigma_x_known=float(known_sigma_x),
                E=float(E), nu=nu, G=G, unit=strain_unit, stress_unit=stress_unit, title=title, phi_deg=phi_deg,
            )
        else:
            raise ValueError(f'Unsupported solve_path: {solve_path}')

        request = SolverRequest(solve_path=solve_path, inputs=inputs)
        result = self.api.solve(request)
        payload = asdict(result)
        stem = solve_path
        outfile_path = Path(outfile).expanduser().resolve() if outfile else default_json_output_path(stem)
        plotfile_path = Path(plotfile).expanduser().resolve() if plotfile else default_plot_output_path(stem)
        payload.setdefault('artifacts', {})
        payload['artifacts']['json_output'] = str(write_json(payload, outfile_path, pretty=pretty))
        if make_plot:
            payload['artifacts']['plot_output'] = str(render_dashboard(payload, plotfile_path, show_plot=show_plot))
            write_json(payload, outfile_path, pretty=pretty)
        return payload
