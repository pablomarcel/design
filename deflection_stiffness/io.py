from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import (
    BeamOptions,
    BeamProblem,
    BeamResults,
    DistributedLoad,
    ElementSpec,
    MomentLoad,
    NodeSpec,
    PointLoad,
    SupportSpec,
    Units,
)
from .utils import Issue, read_json, require, write_json

try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover
    go = None


# ------------------------------ parsing ------------------------------

def _parse_nodes(d: Mapping[str, Any]) -> tuple[NodeSpec, ...]:
    return tuple(NodeSpec(id=str(n["id"]), x=float(n["x"]), y=float(n["y"])) for n in d.get("nodes", []))


def _parse_elements(d: Mapping[str, Any]) -> tuple[ElementSpec, ...]:
    els = []
    for e in d.get("elements", []):
        els.append(
            ElementSpec(
                id=str(e["id"]),
                n1=str(e["n1"]),
                n2=str(e["n2"]),
                EA=(None if e.get("EA") is None else float(e["EA"])),
                EI=(None if e.get("EI") is None else float(e["EI"])),
            )
        )
    return tuple(els)


def _parse_supports(d: Mapping[str, Any]) -> tuple[SupportSpec, ...]:
    sups = []
    for s in d.get("supports", []):
        sups.append(
            SupportSpec(
                node=str(s["node"]),
                type=str(s["type"]),
                dof=(None if s.get("dof") is None else str(s["dof"])),
                k=(None if s.get("k") is None else float(s["k"])),
            )
        )
    return tuple(sups)


def _parse_loads(d: Mapping[str, Any]) -> tuple[Any, ...]:
    loads = []
    for ld in d.get("loads", []):
        t = str(ld.get("type", "")).strip().lower()
        if t in ("point", "point_load", "node_force"):
            loads.append(PointLoad(node=str(ld["node"]), Fx=float(ld.get("Fx", 0.0)), Fy=float(ld.get("Fy", 0.0))))
        elif t in ("distributed", "q_load"):
            loads.append(DistributedLoad(element=str(ld["element"]), q=float(ld["q"]), direction=str(ld.get("direction", "y"))))
        elif t in ("moment", "moment_load"):
            loads.append(MomentLoad(node=str(ld["node"]), Ty=float(ld.get("Ty", 0.0))))
        else:
            raise ValueError(f"Unknown load type: {t!r}")
    return tuple(loads)


def load_problem(path: str | Path) -> BeamProblem:
    d = read_json(path)
    schema = str(d.get("schema", "")).strip()
    require(schema != "", "Missing required field: schema")

    units_d = d.get("units", {}) or {}
    units = Units(
        length=str(units_d.get("length", "m")),
        force=str(units_d.get("force", "N")),
        moment=str(units_d.get("moment", "N*m")),
    )

    opt_d = d.get("options", {}) or {}
    defaults = BeamOptions()

    pb = str(opt_d.get("plot_backend", defaults.plot_backend)).strip() or defaults.plot_backend
    if pb not in ("anastruct", "plotly"):
        pb = defaults.plot_backend

    pf_default = "png" if pb == "anastruct" else "html"
    pf = str(opt_d.get("plot_format", pf_default)).strip() or pf_default
    if pf not in ("png", "html", "json"):
        pf = pf_default

    ap_val = opt_d.get("anastruct_plots", None)
    if isinstance(ap_val, str):
        ap = tuple(s.strip() for s in ap_val.split(",") if s.strip())
    elif isinstance(ap_val, (list, tuple)):
        ap = tuple(str(s).strip() for s in ap_val if str(s).strip())
    else:
        ap = defaults.anastruct_plots

    fs_val = opt_d.get("anastruct_figsize", defaults.anastruct_figsize)
    if isinstance(fs_val, (list, tuple)) and len(fs_val) == 2:
        try:
            fs = (float(fs_val[0]), float(fs_val[1]))
        except Exception:
            fs = defaults.anastruct_figsize
    else:
        fs = defaults.anastruct_figsize

    options = BeamOptions(
        solver=str(opt_d.get("solver", defaults.solver)),
        plots=bool(opt_d.get("plots", defaults.plots)),
        plot_backend=pb,
        plot_format=pf,
        deform_scale=float(opt_d.get("deform_scale", defaults.deform_scale)),
        EA_default=(None if opt_d.get("EA_default") is None else float(opt_d.get("EA_default"))),
        EI_default=(None if opt_d.get("EI_default") is None else float(opt_d.get("EI_default"))),
        anastruct_plots=ap,
        anastruct_dpi=int(opt_d.get("anastruct_dpi", defaults.anastruct_dpi)),
        anastruct_figsize=fs,
        anastruct_zip=bool(opt_d.get("anastruct_zip", defaults.anastruct_zip)),
    )

    return BeamProblem(
        schema=schema,
        nodes=_parse_nodes(d),
        elements=_parse_elements(d),
        supports=_parse_supports(d),
        loads=_parse_loads(d),
        units=units,
        options=options,
        meta=dict(d.get("meta", {}) or {}),
    )


# ------------------------------ results I/O ------------------------------

def results_to_dict(res: BeamResults) -> dict[str, Any]:
    return {
        "nodes": [asdict(n) for n in res.nodes],
        "reactions": [asdict(r) for r in res.reactions],
        "elements": [asdict(e) for e in res.elements],
        "meta": dict(res.meta),
    }


def write_results_json(path: str | Path, res: BeamResults) -> None:
    write_json(path, results_to_dict(res), indent=2)


def write_csv_tables(outdir: str | Path, res: BeamResults) -> list[str]:
    import csv

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []

    def _write(name: str, rows: list[dict[str, Any]]) -> None:
        p = outdir / name
        with p.open("w", newline="", encoding="utf-8") as f:
            if not rows:
                return
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        outputs.append(str(p))

    _write("nodes.csv", [asdict(n) for n in res.nodes])
    _write("reactions.csv", [asdict(r) for r in res.reactions])
    _write("elements.csv", [asdict(e) for e in res.elements])
    return outputs


# ------------------------------ plotly tooling ------------------------------

def fig_structure(prob: BeamProblem):
    """Return a Plotly figure of the undeformed beam geometry."""
    if go is None:
        raise RuntimeError("plotly is not installed. Install plotly to enable interactive plots.")
    node_xy = {n.id: (n.x, n.y) for n in prob.nodes}

    fig = go.Figure()
    for e in prob.elements:
        x1, y1 = node_xy[e.n1]
        x2, y2 = node_xy[e.n2]
        fig.add_trace(go.Scatter(x=[x1, x2], y=[y1, y2], mode="lines", name=e.id, hovertext=f"element {e.id}"))
    fig.add_trace(go.Scatter(
        x=[n.x for n in prob.nodes],
        y=[n.y for n in prob.nodes],
        mode="markers+text",
        text=[n.id for n in prob.nodes],
        textposition="top center",
        name="nodes",
    ))
    fig.update_layout(title="beams: structure", xaxis_title=prob.units.length, yaxis_title=prob.units.length, showlegend=False)
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig


def fig_deformed(prob: BeamProblem, res: BeamResults, *, scale: float = 1.0):
    """Return a Plotly figure of deformed shape (linear scale factor)."""
    if go is None:
        raise RuntimeError("plotly is not installed. Install plotly to enable interactive plots.")
    base_xy = {n.id: (n.x, n.y) for n in prob.nodes}
    disp = {nr.node: (nr.ux, nr.uy) for nr in res.nodes}

    def xy_def(nid: str):
        x0, y0 = base_xy[nid]
        ux, uy = disp.get(nid, (0.0, 0.0))
        return x0 + scale * ux, y0 + scale * uy

    fig = go.Figure()
    for e in prob.elements:
        x1, y1 = xy_def(e.n1)
        x2, y2 = xy_def(e.n2)
        fig.add_trace(go.Scatter(x=[x1, x2], y=[y1, y2], mode="lines", name=e.id))
    fig.add_trace(go.Scatter(
        x=[xy_def(n.id)[0] for n in prob.nodes],
        y=[xy_def(n.id)[1] for n in prob.nodes],
        mode="markers+text",
        text=[n.id for n in prob.nodes],
        textposition="top center",
        name="nodes",
    ))
    fig.update_layout(title=f"beams: deformed (scale={scale:g})", xaxis_title=prob.units.length, yaxis_title=prob.units.length, showlegend=False)
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig


def write_plot(path: str | Path, fig, *, fmt: str = "html") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "html":
        fig.write_html(str(p))
    elif fmt == "json":
        p.write_text(fig.to_json(), encoding="utf-8")
    else:
        raise ValueError(f"Unknown plot format: {fmt!r}")


# ------------------------------ anastruct plotting ------------------------------

_ANASTRUCT_PLOTS = {
    "structure": ("show_structure", "structure.png"),
    "reaction_force": ("show_reaction_force", "reaction_force.png"),
    "axial_force": ("show_axial_force", "axial_force.png"),
    "shear_force": ("show_shear_force", "shear_force.png"),
    "bending_moment": ("show_bending_moment", "bending_moment.png"),
    "displacement": ("show_displacement", "displacement.png"),
}


def write_anastruct_plots(
    outdir: str | Path,
    ss: Any,
    *,
    plots: Sequence[str] = ("structure", "reaction_force", "axial_force", "shear_force", "bending_moment", "displacement"),
    dpi: int = 150,
    figsize: tuple[float, float] = (12.0, 8.0),
    deform_scale: float | None = None,
    zip_plots: bool | None = None,
    make_zip: bool | None = None,
) -> tuple[list[str], list[Issue]]:
    """Write anastruct native plots to PNG files.

    Returns (outputs, issues).

    IMPORTANT: We save the figure created by anastruct (plt.gcf()) to avoid blank images.
    """
    # Back-compat: older versions used make_zip; CLI uses --zip-plots (zip_plots).
    if zip_plots is None and make_zip is None:
        zip_plots = False
    if zip_plots is None:
        zip_plots = bool(make_zip)
    make_zip = bool(zip_plots)

    outputs: list[str] = []
    issues: list[Issue] = []

    outdir_p = Path(outdir)
    outdir_p.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"matplotlib is required for anastruct PNG plots: {e}") from e

    plot_paths: list[Path] = []

    def _call_show(fn, *, scale: float | None = None):
        # Try common signatures across anastruct versions.
        if scale is None:
            for attempt in (lambda: fn(show=False), lambda: fn(False), lambda: fn()):
                try:
                    return attempt()
                except TypeError:
                    continue
            raise TypeError("no compatible signature")

        for attempt in (
            lambda: fn(show=False, factor=scale),
            lambda: fn(show=False, scale=scale),
            lambda: fn(show=False, deformation_factor=scale),
            lambda: fn(factor=scale),
            lambda: fn(scale=scale),
            lambda: fn(),
        ):
            try:
                return attempt()
            except TypeError:
                continue
        raise TypeError("no compatible signature")

    def _figure_from_return(ret):
        if ret is None:
            return None
        if hasattr(ret, "savefig"):
            return ret
        if isinstance(ret, (tuple, list)):
            for obj in ret:
                if hasattr(obj, "savefig"):
                    return obj
        return None

    for name in plots:
        key = str(name).strip().lower()
        if not key:
            continue
        if key not in _ANASTRUCT_PLOTS:
            issues.append(Issue("warning", f"Unknown anastruct plot kind: {name!r}", path="io.anastruct_plots"))
            continue

        method_name, filename = _ANASTRUCT_PLOTS[key]
        fn = getattr(ss, method_name, None)
        if fn is None:
            issues.append(Issue("warning", f"anastruct SystemElements missing method {method_name}()", path="io.anastruct_plots"))
            continue

        try:
            # Ensure we save the figure that anastruct created
            plt.close("all")

            if key == "displacement":
                ret = _call_show(fn, scale=deform_scale)
            else:
                ret = _call_show(fn)

            fig = _figure_from_return(ret) or plt.gcf()

            # Enforce user figsize even if anastruct created a default-sized fig.
            try:
                fig.set_size_inches(float(figsize[0]), float(figsize[1]), forward=True)
            except Exception:
                pass

            # Ensure it is rendered before saving
            try:
                fig.canvas.draw()
            except Exception:
                pass

            p = outdir_p / filename
            fig.savefig(p, format="png", dpi=int(dpi), bbox_inches="tight")
            outputs.append(str(p))
            plot_paths.append(p)

        except Exception as e:
            issues.append(Issue("warning", f"Failed to render plot {key}: {e}", path="io.anastruct_plots"))
        finally:
            try:
                plt.close("all")
            except Exception:
                pass

    if make_zip and plot_paths:
        import zipfile
        zip_path = outdir_p / "plots.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for pth in plot_paths:
                zf.write(pth, arcname=pth.name)
        outputs.append(str(zip_path))

    return outputs, issues
