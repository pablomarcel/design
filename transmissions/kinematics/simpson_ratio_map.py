#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kinematics.simpson_ratio_map

Fast Simpson transmission ratio explorer for the current project topology.

What this upgrade fixes
-----------------------
1. Supports package/module execution modes that match the project layout:

       python -m kinematics.simpson_ratio_map ...

   and also flat-file execution when the file is copied out of the package.

2. Stops hard-coding 3rd gear in the *map layer*. Third gear is now derived
   from the direct-clutch constraints of the current simplified Simpson model.

3. Keeps reverse sign reporting honest. In the present 4-member topology,
   reverse magnitude comes from the same kinematic equations, but the negative
   sign is still reported by convention because this simplified architecture
   does not intrinsically produce a negative carrier speed.

4. Adds logging and optional tqdm progress bars.

Current modeled topology
------------------------
The active project model contains four rotating members:

    sun, ring1, ring2, carrier

with two planetary sets that share the same sun and the same carrier.

Ratio conventions reported here
-------------------------------
- 1st  = sun / carrier   (carrier input, ring2 grounded)
- 2nd  = sun / carrier   (carrier input, ring1 grounded)
- 3rd  = sun / carrier   (direct clutch => sun locked to carrier)
- Rev  = -abs(sun / carrier) with sun input, ring1 grounded

Important honesty note
----------------------
Reverse is still shown negative by operating-mode convention. That convention
belongs to the current simplified topology, not to a fully general final
transmission synthesis engine.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None

# -----------------------------------------------------------------------------
# Imports: support project package execution and flat-file execution.
# -----------------------------------------------------------------------------

try:
    from .simpson_solver import SimpsonTransmission, configure_logging
except Exception:
    try:
        from kinematics.simpson_solver import SimpsonTransmission, configure_logging
    except Exception:
        _HERE = Path(__file__).resolve().parent
        _PARENT = _HERE.parent
        for _candidate in (str(_HERE), str(_PARENT)):
            if _candidate not in sys.path:
                sys.path.insert(0, _candidate)
        from simpson_solver import SimpsonTransmission, configure_logging  # type: ignore


LOGGER = logging.getLogger(__name__)
_ALLOWED_GEARS = {"first", "second", "third", "reverse"}


@dataclass(frozen=True)
class SimpsonRatios:
    first: float
    second: float
    third: float
    reverse: float


# -----------------------------------------------------------------------------
# Geometry / analytic ratio helpers
# -----------------------------------------------------------------------------


def _is_valid_geometry(Ns: int, Nr1: int, Nr2: int) -> bool:
    return (
        Ns > 0
        and Nr1 > Ns
        and Nr2 > Ns
        and ((Nr1 - Ns) % 2 == 0)
        and ((Nr2 - Ns) % 2 == 0)
    )



def _analytic_ratios(Ns: int, Nr1: int, Nr2: int) -> SimpsonRatios:
    """
    Derive the current simplified-model ratios directly from the same active
    constraints represented in simpson_solver.py.

    For this architecture:
    - first:  carrier input, ring2 grounded  => ws/wc = 1 + Nr2/Ns
    - second: carrier input, ring1 grounded  => ws/wc = 1 + Nr1/Ns
    - third:  direct clutch ws = wc          => ws/wc = 1
    - reverse magnitude with sun input and ring1 grounded:
              wc = Ns/(Ns+Nr1) => ws/wc = 1 + Nr1/Ns
              reported negative by convention
    """

    ns = float(Ns)
    first = 1.0 + (float(Nr2) / ns)
    second = 1.0 + (float(Nr1) / ns)
    third = 1.0
    reverse = -(1.0 + (float(Nr1) / ns))
    return SimpsonRatios(first=first, second=second, third=third, reverse=reverse)



def _iter_cases(
    sun_range: Sequence[int],
    ring_range: Sequence[int],
) -> Iterator[Tuple[int, int, int]]:
    for Ns in sun_range:
        for Nr1 in ring_range:
            for Nr2 in ring_range:
                yield int(Ns), int(Nr1), int(Nr2)


# -----------------------------------------------------------------------------
# Optional solver validation hooks
# -----------------------------------------------------------------------------


def _ratio_from_solution(solution: Dict[str, float], numerator_member: str, denominator_member: str) -> float:
    if numerator_member not in solution:
        raise KeyError(f"Missing numerator member in solution: {numerator_member}")
    if denominator_member not in solution:
        raise KeyError(f"Missing denominator member in solution: {denominator_member}")
    denom = float(solution[denominator_member])
    if abs(denom) < 1.0e-12:
        raise ZeroDivisionError(f"Denominator speed for '{denominator_member}' is zero")
    return float(solution[numerator_member]) / denom



def _solver_debug_bundle(simpson: SimpsonTransmission) -> Dict[str, Dict[str, object]]:
    bundle: Dict[str, Dict[str, object]] = {}
    for state_name in ("first", "second", "third", "reverse"):
        report = simpson.state_report(state_name)
        bundle[state_name] = report
    return bundle



def _solver_ratios(simpson: SimpsonTransmission) -> SimpsonRatios:
    first_sol = simpson.first_gear()
    second_sol = simpson.second_gear()
    third_sol = simpson.third_gear()
    reverse_sol = simpson.reverse()
    return SimpsonRatios(
        first=_ratio_from_solution(first_sol, "sun", "carrier"),
        second=_ratio_from_solution(second_sol, "sun", "carrier"),
        third=_ratio_from_solution(third_sol, "sun", "carrier"),
        reverse=-abs(_ratio_from_solution(reverse_sol, "sun", "carrier")),
    )


# -----------------------------------------------------------------------------
# Map generation
# -----------------------------------------------------------------------------


def generate_simpson_map(
    sun_range: Iterable[int],
    ring_range: Iterable[int],
    *,
    include_debug: bool = False,
    require_distinct_rings: bool = False,
    show_progress: bool = False,
    validate_with_solver: bool = False,
    validation_tol: float = 1.0e-10,
) -> List[Dict[str, object]]:
    """
    Generate a Simpson ratio map for all valid tooth-count combinations.

    Parameters
    ----------
    sun_range : iterable of int
        Candidate sun tooth counts.
    ring_range : iterable of int
        Candidate ring tooth counts for both ring sets.
    include_debug : bool
        Include solver reports and analytic ratios in each row.
    require_distinct_rings : bool
        If True, skip cases where Nr1 == Nr2.
    show_progress : bool
        If True and tqdm is installed, show a progress bar.
    validate_with_solver : bool
        If True, verify analytic ratios against the upgraded state solver for
        every kept configuration.
    validation_tol : float
        Absolute tolerance for analytic-vs-solver validation.
    """

    suns = [int(x) for x in sun_range]
    rings = [int(x) for x in ring_range]
    raw_cases = len(suns) * len(rings) * len(rings)

    LOGGER.info(
        "Starting Simpson sweep: suns=%s ring1=%s ring2=%s raw_cases=%s",
        len(suns),
        len(rings),
        len(rings),
        raw_cases,
    )

    iterator: Iterator[Tuple[int, int, int]] = _iter_cases(suns, rings)
    if show_progress and tqdm is not None:
        iterator = tqdm(iterator, total=raw_cases, desc="Simpson map")

    results: List[Dict[str, object]] = []
    processed = 0
    skipped = 0
    kept = 0

    for Ns, Nr1, Nr2 in iterator:
        processed += 1

        if require_distinct_rings and Nr1 == Nr2:
            skipped += 1
            continue

        if not _is_valid_geometry(Ns, Nr1, Nr2):
            skipped += 1
            continue

        ratios = _analytic_ratios(Ns, Nr1, Nr2)
        row: Dict[str, object] = {
            "Ns": Ns,
            "Nr1": Nr1,
            "Nr2": Nr2,
            "ratios": {
                "first": float(ratios.first),
                "second": float(ratios.second),
                "third": float(ratios.third),
                "reverse": float(ratios.reverse),
            },
        }

        if include_debug or validate_with_solver:
            simpson = SimpsonTransmission(Ns=Ns, Nr1=Nr1, Nr2=Nr2)
            solver_ratios = _solver_ratios(simpson)
            diffs = {
                "first": abs(ratios.first - solver_ratios.first),
                "second": abs(ratios.second - solver_ratios.second),
                "third": abs(ratios.third - solver_ratios.third),
                "reverse": abs(ratios.reverse - solver_ratios.reverse),
            }
            validation_ok = all(delta <= float(validation_tol) for delta in diffs.values())

            if validate_with_solver and not validation_ok:
                raise RuntimeError(
                    "Analytic-vs-solver mismatch for Ns=%s Nr1=%s Nr2=%s: %s"
                    % (Ns, Nr1, Nr2, diffs)
                )

            if include_debug:
                row["analytic_ratios"] = {
                    "first": float(ratios.first),
                    "second": float(ratios.second),
                    "third": float(ratios.third),
                    "reverse": float(ratios.reverse),
                }
                row["solver_ratios"] = {
                    "first": float(solver_ratios.first),
                    "second": float(solver_ratios.second),
                    "third": float(solver_ratios.third),
                    "reverse": float(solver_ratios.reverse),
                }
                row["ratio_diffs"] = diffs
                row["validation_ok"] = validation_ok
                row["state_reports"] = _solver_debug_bundle(simpson)

        results.append(row)
        kept += 1

    results.sort(
        key=lambda row: (
            abs(float(row["ratios"]["first"])),  # type: ignore[index]
            abs(float(row["ratios"]["second"])),  # type: ignore[index]
            int(row["Ns"]),
            int(row["Nr1"]),
            int(row["Nr2"]),
        )
    )

    LOGGER.info(
        "Finished Simpson sweep: processed=%s kept=%s skipped=%s",
        processed,
        kept,
        skipped,
    )
    return results


# -----------------------------------------------------------------------------
# Search / pretty printing
# -----------------------------------------------------------------------------


def print_simpson_table(results: List[Dict[str, object]], limit: Optional[int] = 50) -> None:
    rows = results if limit is None else results[:limit]

    print()
    print("Simpson Transmission Ratio Map")
    print("----------------------------------------------------------------------------")
    print(f"{'Ns':>5} {'Nr1':>5} {'Nr2':>5} {'1st':>10} {'2nd':>10} {'3rd':>10} {'Rev':>10}")
    print("----------------------------------------------------------------------------")

    for row in rows:
        ratios = row["ratios"]  # type: ignore[assignment]
        print(
            f"{int(row['Ns']):5d} "
            f"{int(row['Nr1']):5d} "
            f"{int(row['Nr2']):5d} "
            f"{float(ratios['first']):10.3f} "
            f"{float(ratios['second']):10.3f} "
            f"{float(ratios['third']):10.3f} "
            f"{float(ratios['reverse']):10.3f}"
        )
    print()



def search_simpson(
    target_ratio: float,
    sun_range: Iterable[int],
    ring_range: Iterable[int],
    *,
    gear: str = "first",
    tol: float = 0.2,
    include_debug: bool = False,
    require_distinct_rings: bool = False,
    show_progress: bool = False,
    validate_with_solver: bool = False,
) -> List[Dict[str, object]]:
    if gear not in _ALLOWED_GEARS:
        raise ValueError(f"gear must be one of {_ALLOWED_GEARS}")
    if tol < 0:
        raise ValueError("tol must be non-negative")

    results = generate_simpson_map(
        sun_range=sun_range,
        ring_range=ring_range,
        include_debug=include_debug,
        require_distinct_rings=require_distinct_rings,
        show_progress=show_progress,
        validate_with_solver=validate_with_solver,
    )

    matches = [
        row
        for row in results
        if abs(float(row["ratios"][gear]) - float(target_ratio)) <= float(tol)  # type: ignore[index]
    ]

    matches.sort(
        key=lambda row: (
            abs(float(row["ratios"][gear]) - float(target_ratio)),  # type: ignore[index]
            int(row["Ns"]),
            int(row["Nr1"]),
            int(row["Nr2"]),
        )
    )
    return matches


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Simpson transmission ratio maps")
    parser.add_argument("--sun-min", type=int, default=20)
    parser.add_argument("--sun-max", type=int, default=40)
    parser.add_argument("--ring-min", type=int, default=50)
    parser.add_argument("--ring-max", type=int, default=90)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--search-target", type=float, default=3.0)
    parser.add_argument("--search-gear", choices=sorted(_ALLOWED_GEARS), default="first")
    parser.add_argument("--tol", type=float, default=0.1)
    parser.add_argument("--distinct-rings", action="store_true")
    parser.add_argument("--include-debug", action="store_true")
    parser.add_argument("--validate-with-solver", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--log-level", default="WARNING", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser



def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.sun_max <= args.sun_min:
        parser.error("--sun-max must be greater than --sun-min")
    if args.ring_max <= args.ring_min:
        parser.error("--ring-max must be greater than --ring-min")
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be non-negative")
    if args.tol < 0:
        parser.error("--tol must be non-negative")

    log_level = getattr(logging, str(args.log_level).upper())
    configure_logging(level=log_level)

    sun_range = range(args.sun_min, args.sun_max)
    ring_range = range(args.ring_min, args.ring_max)
    show_progress = not bool(args.no_progress)

    LOGGER.info(
        "CLI args: sun=[%s,%s) ring=[%s,%s) limit=%s search_target=%s search_gear=%s tol=%s",
        args.sun_min,
        args.sun_max,
        args.ring_min,
        args.ring_max,
        args.limit,
        args.search_target,
        args.search_gear,
        args.tol,
    )

    results = generate_simpson_map(
        sun_range=sun_range,
        ring_range=ring_range,
        include_debug=args.include_debug,
        require_distinct_rings=args.distinct_rings,
        show_progress=show_progress,
        validate_with_solver=args.validate_with_solver,
    )
    print_simpson_table(results, limit=args.limit)

    print(f"Search for ~{args.search_target} {args.search_gear} gear")
    matches = [
        row
        for row in results
        if abs(float(row["ratios"][args.search_gear]) - float(args.search_target)) <= float(args.tol)  # type: ignore[index]
    ]
    LOGGER.info(
        "Found %s matches near %f for gear=%s tol=%f",
        len(matches),
        args.search_target,
        args.search_gear,
        args.tol,
    )

    for row in matches[:10]:
        ratios = row["ratios"]  # type: ignore[assignment]
        print(
            f"Ns={int(row['Ns'])} "
            f"Nr1={int(row['Nr1'])} "
            f"Nr2={int(row['Nr2'])} "
            f"1st={float(ratios['first']):.3f} "
            f"2nd={float(ratios['second']):.3f} "
            f"3rd={float(ratios['third']):.3f} "
            f"Rev={float(ratios['reverse']):.3f}"
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
