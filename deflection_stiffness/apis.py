from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

PlotBackend = Literal["anastruct", "plotly"]
PlotFormat = Literal["png", "html", "json"]


@dataclass(frozen=True)
class RunRequest:
    """Run request for the deflection_stiffness App."""

    infile: str | Path
    outdir: str | Path | None = None

    # validation + outputs
    strict: bool = True
    write_csv: bool = True
    write_results_json: bool = True
    write_plots: bool = True

    # plotting (None => use JSON options)
    plot_backend: PlotBackend | None = None
    plot_format: PlotFormat | None = None
    deform_scale: float | None = None

    # anastruct plotting controls
    anastruct_plots: Sequence[str] | None = None
    anastruct_dpi: int | None = None
    anastruct_figsize: tuple[float, float] | None = None
    anastruct_zip: bool | None = None

    # optional property overrides (reserved for future growth)
    overrides: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunResponse:
    ok: bool
    outputs: list[str] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
