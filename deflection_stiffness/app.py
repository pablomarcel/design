from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .apis import RunRequest, RunResponse
from .core import (
    BeamProblem,
    BeamResults,
    DistributedLoad,
    ElementResult,
    MomentLoad,
    NodeResult,
    PointLoad,
    ReactionResult,
)
from .io import (
    fig_deformed,
    fig_structure,
    load_problem,
    write_anastruct_plots,
    write_csv_tables,
    write_plot,
    write_results_json,
)
from .utils import timed

logger = logging.getLogger("beams")


def _debug_attrs(obj: Any, *, limit: int = 80) -> list[str]:
    try:
        names = [n for n in dir(obj) if not n.startswith("__")]
        return sorted(names)[:limit]
    except Exception:
        return []


def _debug_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _debug_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_debug_jsonable(v) for v in value]
    try:
        json.dumps(value)
        return value
    except Exception:
        return repr(value)


def _write_debug_snapshot(outpath: Path, payload: dict[str, Any]) -> None:
    try:
        outpath.write_text(json.dumps(_debug_jsonable(payload), indent=2), encoding="utf-8")
        logger.info("Wrote debug snapshot: %s", outpath)
    except Exception as e:
        logger.warning("Failed to write debug snapshot %s: %s", outpath, e)


class SolverError(RuntimeError):
    pass


class BeamSolver:
    def solve(self, prob: BeamProblem) -> BeamResults:  # pragma: no cover
        raise NotImplementedError


# ------------------------------ anastruct compat helpers ------------------------------

def _try_calls(calls: list[Callable[[], Any]], *, what: str) -> Any:
    """Try a list of callables until one succeeds; only swallows TypeError."""
    last: Exception | None = None
    for fn in calls:
        try:
            return fn()
        except TypeError as e:
            last = e
            continue
    raise SolverError(f"Failed to call {what} with any known signature. Last error: {last}")


def _coerce_node_id(nid: Any) -> int:
    """Normalize an anastruct node identifier into a plain int."""
    if isinstance(nid, int):
        return nid

    for attr in ("id", "node_id", "nodeId"):
        if hasattr(nid, attr):
            try:
                return int(getattr(nid, attr))
            except Exception:
                pass

    try:
        return int(nid)
    except Exception as e:
        raise TypeError(f"Expected an int-like node id; got {type(nid).__name__}: {nid!r}") from e


def _find_node_id_int(ss: Any, *, xy: tuple[float, float]) -> int:
    """Find the anastruct node_id for a given vertex and return it as an int."""
    fn = getattr(ss, "find_node_id", None)
    if fn is not None:
        try:
            out = _try_calls(
                [
                    lambda: fn(vertex=[float(xy[0]), float(xy[1])]),
                    lambda: fn(vertex=(float(xy[0]), float(xy[1]))),
                    lambda: fn([float(xy[0]), float(xy[1])]),
                    lambda: fn((float(xy[0]), float(xy[1]))),
                ],
                what="SystemElements.find_node_id",
            )
            if isinstance(out, (list, tuple)) and len(out) == 1:
                out = out[0]
            return _coerce_node_id(out)
        except Exception:
            pass

    tol = 1e-9
    nm = getattr(ss, "node_map", None)
    if isinstance(nm, dict):
        xq, yq = float(xy[0]), float(xy[1])
        for k, nd in nm.items():
            vx = None
            if hasattr(nd, "vertex"):
                vx = getattr(nd, "vertex")
            elif hasattr(nd, "coordinates"):
                vx = getattr(nd, "coordinates")
            elif hasattr(nd, "x") and hasattr(nd, "y"):
                vx = (getattr(nd, "x"), getattr(nd, "y"))
            if vx is None:
                continue
            try:
                xn, yn = float(vx[0]), float(vx[1])
            except Exception:
                continue
            if abs(xn - xq) <= tol and abs(yn - yq) <= tol:
                try:
                    return int(k)
                except Exception:
                    return _coerce_node_id(k)

    raise SolverError(
        "Failed to resolve node_id for vertex "
        f"({xy[0]:.6g}, {xy[1]:.6g}). "
        "If your model uses isolated nodes (not connected by any element), "
        "anastruct will not create them."
    )


def _q_load_compat(ss: Any, *, element_id: int, q: float, direction: str | None = None) -> None:
    fn = getattr(ss, "q_load", None)
    if fn is None:
        raise SolverError("anastruct SystemElements has no q_load() method")

    direction_s = None if direction is None else str(direction)
    calls = []
    if direction_s is not None:
        calls.extend(
            [
                lambda: fn(q=q, element_id=element_id, direction=direction_s),
                lambda: fn(element_id=element_id, q=q, direction=direction_s),
                lambda: fn(element_id=element_id, q=q, direction=direction_s.upper()),
            ]
        )
    calls.extend(
        [
            lambda: fn(q=q, element_id=element_id),
            lambda: fn(element_id=element_id, q=q),
            lambda: fn(element_id, q),
        ]
    )
    _try_calls(calls, what="SystemElements.q_load")


def _add_support_roll_compat(ss: Any, *, nid: Any, tr: int) -> None:
    """Add a roller support compatible with anastruct API variants."""
    nid_i = _coerce_node_id(nid)
    axis = "x" if tr == 1 else ("y" if tr == 2 else "rotation")
    fn = getattr(ss, "add_support_roll", None)
    if fn is None:
        raise SolverError("anastruct SystemElements has no add_support_roll() method")

    _try_calls(
        [
            lambda: fn(node_id=nid_i, translation=tr),
            lambda: fn(node_id=nid_i, direction=tr),
            lambda: fn(node_id=nid_i, direction=axis),
            lambda: fn(node_id=nid_i, axis=axis),
            lambda: fn(nid_i, tr),
            lambda: fn(nid_i, axis),
            lambda: fn(nid_i),
        ],
        what="SystemElements.add_support_roll",
    )


def _add_support_fixed_compat(ss: Any, *, nid: Any) -> None:
    fn = getattr(ss, "add_support_fixed", None)
    if fn is None:
        raise SolverError("anastruct SystemElements has no add_support_fixed() method")
    nid_i = _coerce_node_id(nid)
    _try_calls([lambda: fn(node_id=nid_i), lambda: fn(nid_i)], what="SystemElements.add_support_fixed")


def _add_support_hinged_compat(ss: Any, *, nid: Any) -> None:
    fn = getattr(ss, "add_support_hinged", None)
    if fn is None:
        raise SolverError("anastruct SystemElements has no add_support_hinged() method")
    nid_i = _coerce_node_id(nid)
    _try_calls([lambda: fn(node_id=nid_i), lambda: fn(nid_i)], what="SystemElements.add_support_hinged")


def _add_support_spring_compat(ss: Any, *, nid: Any, tr: int, k: float) -> None:
    fn = getattr(ss, "add_support_spring", None)
    if fn is None:
        raise SolverError("anastruct SystemElements has no add_support_spring() method")
    nid_i = _coerce_node_id(nid)
    _try_calls(
        [
            lambda: fn(node_id=nid_i, translation=tr, k=k),
            lambda: fn(node_id=nid_i, direction=tr, k=k),
            lambda: fn(nid_i, tr, k),
            lambda: fn(nid_i, k),
        ],
        what="SystemElements.add_support_spring",
    )


def _moment_load_compat(ss: Any, *, nid: int, Ty: float) -> None:
    fn = getattr(ss, "moment_load", None)
    if fn is None:
        raise SolverError("anastruct SystemElements has no moment_load() method")
    _try_calls(
        [
            lambda: fn(node_id=nid, Ty=Ty),
            lambda: fn(Ty=Ty, node_id=nid),
            lambda: fn(nid, Ty),
        ],
        what="SystemElements.moment_load",
    )


def _point_load_compat(ss: Any, *, nid: int, Fx: float, Fy: float) -> None:
    fn = getattr(ss, "point_load", None)
    if fn is None:
        raise SolverError("anastruct SystemElements has no point_load() method")
    _try_calls(
        [
            lambda: fn(node_id=nid, Fx=Fx, Fy=Fy),
            lambda: fn(Fx=Fx, Fy=Fy, node_id=nid),
            lambda: fn(nid, Fx, Fy),
        ],
        what="SystemElements.point_load",
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _extract_value(obj: Any, *names: str, default: float = 0.0) -> float:
    for name in names:
        if hasattr(obj, name):
            val = getattr(obj, name)
            try:
                if val is not None:
                    return float(val)
            except Exception:
                pass
    return default


def _node_result_components(obj: Any) -> tuple[float, float, float]:
    """Return (ux, uy, rz) from a public anastruct node result object/dict/tuple."""
    if obj is None:
        return 0.0, 0.0, 0.0

    if isinstance(obj, dict):
        ux = _safe_float(obj.get("ux", 0.0))
        uy = _safe_float(obj.get("uy", obj.get("uz", 0.0)))
        rz = _safe_float(
            obj.get("phi_z", obj.get("phi", obj.get("rz", obj.get("rotation", 0.0))))
        )
        return ux, uy, rz

    if isinstance(obj, (list, tuple)):
        if len(obj) >= 4:
            return _safe_float(obj[-3]), _safe_float(obj[-2]), _safe_float(obj[-1])
        if len(obj) == 3:
            return _safe_float(obj[0]), _safe_float(obj[1]), _safe_float(obj[2])
        return 0.0, 0.0, 0.0

    ux = _extract_value(obj, "ux", default=0.0)
    uy = _extract_value(obj, "uy", "uz", default=0.0)
    rz = _extract_value(obj, "phi_z", "phi", "rz", "rotation", default=0.0)
    return ux, uy, rz


def _reaction_components(obj: Any) -> tuple[float, float, float]:
    """Return (Rx, Ry, Mz) from a public anastruct reaction result object/dict/tuple."""
    if obj is None:
        return 0.0, 0.0, 0.0

    if isinstance(obj, dict):
        return (
            _safe_float(obj.get("Fx", obj.get("Rx", 0.0))),
            _safe_float(obj.get("Fy", obj.get("Ry", 0.0))),
            _safe_float(obj.get("Ty", obj.get("Tz", obj.get("Mz", 0.0)))),
        )

    if isinstance(obj, (list, tuple)):
        if len(obj) >= 4:
            return _safe_float(obj[1]), _safe_float(obj[2]), _safe_float(obj[3])
        if len(obj) == 3:
            return _safe_float(obj[0]), _safe_float(obj[1]), _safe_float(obj[2])
        return 0.0, 0.0, 0.0

    return (
        _extract_value(obj, "Fx", "Rx", default=0.0),
        _extract_value(obj, "Fy", "Ry", default=0.0),
        _extract_value(obj, "Ty", "Tz", "Mz", default=0.0),
    )


def _element_signed_peak(x: Any) -> float:
    """Best-effort signed representative value from scalar/sequence-like element results."""
    try:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, (list, tuple)):
            vals = [float(v) for v in x if v is not None]
            if not vals:
                return 0.0
            return max(vals, key=lambda v: abs(v))
        if hasattr(x, "__iter__") and not isinstance(x, (str, bytes, dict)):
            vals = [float(v) for v in list(x) if v is not None]
            if not vals:
                return 0.0
            return max(vals, key=lambda v: abs(v))
        return float(x)
    except Exception:
        return 0.0


def _get_public_node_result_map(ss: Any) -> dict[int, tuple[float, float, float]]:
    out: dict[int, tuple[float, float, float]] = {}
    logger.debug("node results: probing public APIs")

    fn = getattr(ss, "get_node_displacements", None)
    if fn is not None:
        try:
            rows = fn()
            logger.debug("node results: get_node_displacements() returned type=%s", type(rows).__name__)
            if isinstance(rows, dict):
                for raw_nid, obj in rows.items():
                    out[_coerce_node_id(raw_nid)] = _node_result_components(obj)
                if out:
                    logger.debug("node results: using get_node_displacements() dict path with %d entries", len(out))
                    return out
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        raw_nid = row.get("id", row.get("node_id"))
                        if raw_nid is None:
                            continue
                        out[_coerce_node_id(raw_nid)] = _node_result_components(row)
                    elif isinstance(row, (list, tuple)) and len(row) >= 4:
                        out[_coerce_node_id(row[0])] = _node_result_components(row)
                if out:
                    logger.debug("node results: using get_node_displacements() list path with %d entries", len(out))
                    return out
        except Exception:
            pass

    fn = getattr(ss, "get_node_results_system", None)
    if fn is not None:
        try:
            rows = fn()
            logger.debug("node results: get_node_results_system() returned type=%s", type(rows).__name__)
            if isinstance(rows, dict):
                for raw_nid, obj in rows.items():
                    out[_coerce_node_id(raw_nid)] = _node_result_components(obj)
                if out:
                    logger.debug("node results: using get_node_results_system() dict path with %d entries", len(out))
                    return out
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        raw_nid = row.get("id", row.get("node_id"))
                        if raw_nid is None:
                            continue
                        out[_coerce_node_id(raw_nid)] = _node_result_components(row)
                    elif isinstance(row, (list, tuple)) and len(row) >= 7:
                        out[_coerce_node_id(row[0])] = _node_result_components((row[1], row[2], row[6]))
                if out:
                    logger.debug("node results: using get_node_results_system() list path with %d entries", len(out))
                    return out
        except Exception:
            pass

    nm = getattr(ss, "node_map", None)
    if isinstance(nm, dict):
        logger.debug("node results: falling back to node_map with %d entries", len(nm))
        for raw_nid, nd in nm.items():
            try:
                out[_coerce_node_id(raw_nid)] = _node_result_components(nd)
            except Exception:
                continue

    logger.debug("node results: final map has %d entries", len(out))
    return out


def _get_public_reaction_map(ss: Any) -> dict[int, tuple[float, float, float]]:
    out: dict[int, tuple[float, float, float]] = {}
    logger.debug("reactions: probing public APIs")

    fn = getattr(ss, "get_node_results_system", None)
    if fn is not None:
        try:
            rows = fn()
            logger.debug("reactions: get_node_results_system() returned type=%s", type(rows).__name__)
            if isinstance(rows, dict):
                for raw_nid, obj in rows.items():
                    out[_coerce_node_id(raw_nid)] = _reaction_components(obj)
                if out:
                    logger.debug("reactions: using get_node_results_system() dict path with %d entries", len(out))
                    return out
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        raw_nid = row.get("id", row.get("node_id"))
                        if raw_nid is None:
                            continue
                        out[_coerce_node_id(raw_nid)] = _reaction_components(row)
                    elif isinstance(row, (list, tuple)) and len(row) >= 4:
                        out[_coerce_node_id(row[0])] = _reaction_components(row)
                if out:
                    logger.debug("reactions: using get_node_results_system() list path with %d entries", len(out))
                    return out
        except Exception:
            pass

    fn = getattr(ss, "get_reaction_forces", None)
    if fn is not None:
        try:
            rf = fn()
            logger.debug("reactions: get_reaction_forces() returned type=%s", type(rf).__name__)
            if isinstance(rf, dict):
                for raw_nid, obj in rf.items():
                    out[_coerce_node_id(raw_nid)] = _reaction_components(obj)
                if out:
                    logger.debug("reactions: using get_reaction_forces() dict path with %d entries", len(out))
                    return out
            if isinstance(rf, list):
                for row in rf:
                    if isinstance(row, dict):
                        raw_nid = row.get("id", row.get("node_id"))
                        if raw_nid is None:
                            continue
                        out[_coerce_node_id(raw_nid)] = _reaction_components(row)
                    elif isinstance(row, (list, tuple)) and len(row) >= 4:
                        out[_coerce_node_id(row[0])] = _reaction_components(row)
                if out:
                    logger.debug("reactions: using get_reaction_forces() list path with %d entries", len(out))
                    return out
        except Exception:
            pass

    rf = getattr(ss, "reaction_forces", None)
    if isinstance(rf, dict):
        for raw_nid, obj in rf.items():
            try:
                out[_coerce_node_id(raw_nid)] = _reaction_components(obj)
            except Exception:
                continue

    logger.debug("reactions: final map has %d entries", len(out))
    return out


# ------------------------------ anastruct solver ------------------------------

class AnastructSolver(BeamSolver):
    """Anastruct-based solver adapter."""

    def __init__(self) -> None:
        try:
            from anastruct import SystemElements  # type: ignore
        except Exception as e:  # pragma: no cover
            import sys

            raise SolverError(
                "anastruct is not importable in the CURRENT interpreter.\n"
                f"python: {sys.executable}\n"
                "Fix: install into THIS environment:\n"
                "  python -m pip install anastruct\n"
            ) from e
        self._SystemElements = SystemElements
        self._last_system: Any | None = None

    @property
    def last_system(self):
        return self._last_system

    @timed
    def solve(self, prob: BeamProblem) -> BeamResults:
        ss = self._SystemElements()

        logger.info(
            "Starting anastruct solve: nodes=%d elements=%d supports=%d loads=%d",
            len(prob.nodes), len(prob.elements), len(prob.supports), len(prob.loads),
        )
        logger.debug("Problem meta: %s", prob.meta)

        node_xy = {n.id: (n.x, n.y) for n in prob.nodes}
        logger.debug("Node coordinates: %s", node_xy)

        for e in prob.elements:
            x1, y1 = node_xy[e.n1]
            x2, y2 = node_xy[e.n2]

            EA = e.EA if e.EA is not None else prob.options.EA_default
            EI = e.EI if e.EI is not None else prob.options.EI_default

            kwargs: dict[str, Any] = {}
            if EA is not None:
                kwargs["EA"] = float(EA)
            if EI is not None:
                kwargs["EI"] = float(EI)

            ss.add_element(location=[[x1, y1], [x2, y2]], **kwargs)
            logger.debug(
                "Added element %s: %s -> %s EA=%s EI=%s",
                e.id, e.n1, e.n2, kwargs.get("EA"), kwargs.get("EI"),
            )

        for s in prob.supports:
            nid = _find_node_id_int(ss, xy=node_xy[s.node])
            st = s.type.lower()
            logger.debug(
                "Applying support %s at node=%s resolved_nid=%s dof=%s k=%s",
                s.type, s.node, nid, s.dof, s.k,
            )
            if st == "fixed":
                _add_support_fixed_compat(ss, nid=nid)
            elif st == "hinged":
                _add_support_hinged_compat(ss, nid=nid)
            elif st == "roller":
                dof = (s.dof or "uy").lower()
                tr = 1 if dof == "ux" else (2 if dof == "uy" else 3)
                _add_support_roll_compat(ss, nid=nid, tr=tr)
            elif st == "spring":
                dof = (s.dof or "ux").lower()
                tr = 1 if dof == "ux" else (2 if dof == "uy" else 3)
                _add_support_spring_compat(ss, nid=nid, tr=tr, k=float(s.k))
            else:  # pragma: no cover
                raise ValueError(f"Unknown support type: {s.type!r}")

        element_ids = [e.id for e in prob.elements]
        for ld in prob.loads:
            if ld.type == "point":
                lf: PointLoad = ld  # type: ignore[assignment]
                nid = _find_node_id_int(ss, xy=node_xy[lf.node])
                _point_load_compat(ss, nid=nid, Fx=float(lf.Fx), Fy=float(lf.Fy))
                logger.debug(
                    "Applied point load at node=%s resolved_nid=%s Fx=%s Fy=%s",
                    lf.node, nid, lf.Fx, lf.Fy,
                )
            elif ld.type == "distributed":
                lq: DistributedLoad = ld  # type: ignore[assignment]
                idx = element_ids.index(lq.element) + 1
                _q_load_compat(ss, element_id=idx, q=float(lq.q), direction=str(lq.direction))
                logger.debug(
                    "Applied distributed load on element=%s idx=%s q=%s dir=%s",
                    lq.element, idx, lq.q, lq.direction,
                )
            elif ld.type == "moment":
                lm: MomentLoad = ld  # type: ignore[assignment]
                nid = _find_node_id_int(ss, xy=node_xy[lm.node])
                _moment_load_compat(ss, nid=nid, Ty=float(lm.Ty))
                logger.debug("Applied moment load at node=%s resolved_nid=%s Ty=%s", lm.node, nid, lm.Ty)
            else:  # pragma: no cover
                raise ValueError(f"Unknown load type: {ld.type!r}")

        ss.solve()
        logger.info("anastruct solve completed")
        self._last_system = ss

        node_id_by_name = {n.id: _find_node_id_int(ss, xy=node_xy[n.id]) for n in prob.nodes}
        logger.debug("Resolved node ids: %s", node_id_by_name)
        logger.debug(
            "System has get_node_displacements=%s get_node_results_system=%s get_reaction_forces=%s",
            hasattr(ss, "get_node_displacements"),
            hasattr(ss, "get_node_results_system"),
            hasattr(ss, "get_reaction_forces"),
        )

        if logger.isEnabledFor(logging.DEBUG):
            nm = getattr(ss, "node_map", None)
            if isinstance(nm, dict):
                sample = {}
                for raw_nid, nd in list(nm.items())[: min(5, len(nm))]:
                    sample[str(raw_nid)] = {
                        "type": type(nd).__name__,
                        "attrs": _debug_attrs(nd),
                        "ux": getattr(nd, "ux", None),
                        "uy": getattr(nd, "uy", None),
                        "uz": getattr(nd, "uz", None),
                        "phi_z": getattr(nd, "phi_z", None),
                        "phi": getattr(nd, "phi", None),
                        "rz": getattr(nd, "rz", None),
                        "rotation": getattr(nd, "rotation", None),
                    }
                logger.debug("node_map sample: %s", sample)

        public_node_map = _get_public_node_result_map(ss)
        public_reaction_map = _get_public_reaction_map(ss)
        logger.debug("public_node_map keys=%s", sorted(public_node_map.keys()))
        logger.debug("public_reaction_map keys=%s", sorted(public_reaction_map.keys()))

        nodes_out: list[NodeResult] = []
        for name, nid in node_id_by_name.items():
            ux, uy, rz = public_node_map.get(nid, (0.0, 0.0, 0.0))
            logger.debug("node %-6s nid=%s -> ux=%+.9g uy=%+.9g rz=%+.9g", name, nid, ux, uy, rz)
            nodes_out.append(NodeResult(node=name, ux=float(ux), uy=float(uy), rz=float(rz)))

        reactions_out: list[ReactionResult] = []
        for name, nid in node_id_by_name.items():
            if nid in public_reaction_map:
                Rx, Ry, Mz = public_reaction_map[nid]
                logger.debug("reaction %-6s nid=%s -> Rx=%+.9g Ry=%+.9g Mz=%+.9g", name, nid, Rx, Ry, Mz)
                reactions_out.append(ReactionResult(node=name, Rx=float(Rx), Ry=float(Ry), Mz=float(Mz)))

        elements_out: list[ElementResult] = []
        em: Any = getattr(ss, "element_map", None)
        if isinstance(em, dict):
            for i, e in enumerate(prob.elements, start=1):
                obj = em.get(i)
                axial = shear = moment = 0.0
                if obj is not None:
                    axial = _element_signed_peak(getattr(obj, "N", getattr(obj, "axial_force", 0.0)))
                    shear = _element_signed_peak(getattr(obj, "V", getattr(obj, "shear_force", getattr(obj, "Q", 0.0))))
                    moment = _element_signed_peak(getattr(obj, "M", getattr(obj, "bending_moment", 0.0)))
                    logger.debug(
                        "element %-6s idx=%s attrs=%s -> axial=%+.9g shear=%+.9g moment=%+.9g",
                        e.id, i, _debug_attrs(obj, limit=30), axial, shear, moment,
                    )
                elements_out.append(ElementResult(element=e.id, axial=axial, shear=shear, moment=moment))
        else:
            for e in prob.elements:
                elements_out.append(ElementResult(element=e.id, axial=0.0, shear=0.0, moment=0.0))

        return BeamResults(
            nodes=tuple(nodes_out),
            reactions=tuple(reactions_out),
            elements=tuple(elements_out),
            meta={
                "solver": "anastruct",
                "n_nodes": len(prob.nodes),
                "n_elements": len(prob.elements),
                "rotation_field_preference": "phi_z",
            },
        )


# ------------------------------ app orchestrator ------------------------------

@dataclass
class BeamsApp:
    solver: BeamSolver | None = None

    def _get_solver(self, prob: BeamProblem) -> BeamSolver:
        if self.solver is not None:
            return self.solver
        sel = prob.options.solver.lower().strip()
        if sel in ("anastruct", "auto"):
            return AnastructSolver()
        raise SolverError(f"Unknown solver: {prob.options.solver!r}")

    @timed
    def run(self, req: RunRequest) -> RunResponse:
        prob = load_problem(req.infile)

        issues = prob.validate(strict=req.strict)
        issues_dict = [dict(level=i.level, message=i.message, path=i.path) for i in issues]

        outdir = Path(req.outdir) if req.outdir is not None else (Path(req.infile).resolve().parent / "out_run")
        outdir.mkdir(parents=True, exist_ok=True)

        outputs: list[str] = []

        try:
            solver = self._get_solver(prob)
            res = solver.solve(prob)
            if logger.isEnabledFor(logging.DEBUG):
                ss = getattr(solver, "_last_system", None)
                debug_payload = {
                    "meta": {
                        "solver": type(solver).__name__,
                        "n_nodes": len(prob.nodes),
                        "n_elements": len(prob.elements),
                        "n_supports": len(prob.supports),
                        "n_loads": len(prob.loads),
                    },
                    "results_meta": res.meta,
                    "node_results": [nr.__dict__ for nr in res.nodes],
                    "reactions": [rr.__dict__ for rr in res.reactions],
                    "elements": [er.__dict__ for er in res.elements],
                    "system_summary": {
                        "has_node_map": isinstance(getattr(ss, "node_map", None), dict),
                        "has_element_map": isinstance(getattr(ss, "element_map", None), dict),
                        "has_get_node_displacements": hasattr(ss, "get_node_displacements"),
                        "has_get_node_results_system": hasattr(ss, "get_node_results_system"),
                        "has_get_reaction_forces": hasattr(ss, "get_reaction_forces"),
                    },
                }
                _write_debug_snapshot(outdir / "anastruct_debug_snapshot.json", debug_payload)
        except Exception as e:
            issues_dict.append({"level": "error", "message": f"Solve failed: {e}", "path": "solver.solve"})
            return RunResponse(ok=False, outputs=outputs, issues=issues_dict, summary={"outdir": str(outdir)})

        if req.write_results_json:
            p = outdir / "results.json"
            write_results_json(p, res)
            outputs.append(str(p))

        if req.write_csv:
            outputs.extend(write_csv_tables(outdir, res))

        if req.write_plots and prob.options.plots:
            backend = req.plot_backend or getattr(prob.options, "plot_backend", "anastruct")

            if backend == "anastruct":
                try:
                    ss = getattr(solver, "_last_system", None)
                    if ss is None:
                        raise RuntimeError("anastruct plotting requires an AnastructSolver run in the same process")

                    plots = req.anastruct_plots or getattr(prob.options, "anastruct_plots", None)
                    dpi = req.anastruct_dpi if req.anastruct_dpi is not None else getattr(prob.options, "anastruct_dpi", 150)
                    figsize = req.anastruct_figsize if req.anastruct_figsize is not None else getattr(prob.options, "anastruct_figsize", (12.0, 8.0))
                    zip_plots = req.anastruct_zip if req.anastruct_zip is not None else getattr(prob.options, "anastruct_zip", False)
                    deform_scale = prob.options.deform_scale if req.deform_scale is None else float(req.deform_scale)

                    out_paths, warn_issues = write_anastruct_plots(
                        outdir,
                        ss=ss,
                        plots=plots,
                        dpi=int(dpi),
                        figsize=tuple(figsize),
                        deform_scale=float(deform_scale),
                        zip_plots=bool(zip_plots),
                    )
                    outputs.extend(out_paths)
                    issues_dict.extend([dict(level=i.level, message=i.message, path=i.path) for i in warn_issues])
                except Exception as e:
                    issues_dict.append({"level": "warning", "message": f"Anastruct plot generation failed: {e}", "path": "io.plot.anastruct"})
            else:
                fmt = req.plot_format or prob.options.plot_format
                try:
                    fig0 = fig_structure(prob)
                    p0 = outdir / f"structure.{fmt}"
                    write_plot(p0, fig0, fmt=fmt)
                    outputs.append(str(p0))

                    scale = prob.options.deform_scale if req.deform_scale is None else float(req.deform_scale)
                    fig1 = fig_deformed(prob, res, scale=scale)
                    p1 = outdir / f"deformed.{fmt}"
                    write_plot(p1, fig1, fmt=fmt)
                    outputs.append(str(p1))
                except Exception as e:
                    issues_dict.append({"level": "warning", "message": f"Plot generation failed: {e}", "path": "io.plot.plotly"})

        return RunResponse(ok=True, outputs=outputs, issues=issues_dict, summary={"outdir": str(outdir)})
