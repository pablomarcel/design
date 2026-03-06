#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.ravigneaux_ratio_map

Ravignaux transmission ratio-map generator.

This tool is intentionally aligned with the simplified Ravignaux topology used
in `ravigneaux_solver.py`:

    members: sun_small, sun_large, ring, carrier

Standard map states:
- 1st:    sun_small input, ring grounded, carrier output
- 2nd:    sun_large input, ring grounded, carrier output
- 3rd:    ring locked to carrier, direct drive
- Reverse: sun_small input, sun_large grounded, carrier output

Important honesty note
----------------------
This is a fast kinematic ratio explorer for the current simplified topology.
It does not yet perform a full compound-pinion geometric synthesis of a
production Ravignaux mechanism.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
from math import isfinite
from pathlib import Path
import sys
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None

try:
    from .ravigneaux_solver import RavigneauxTransmission, configure_logging
except Exception:
    try:
        from kinematics.ravigneaux_solver import RavigneauxTransmission, configure_logging
    except Exception:
        _HERE = Path(__file__).resolve().parent
        _PARENT = _HERE.parent
        for _candidate in (str(_HERE), str(_PARENT)):
            if _candidate not in sys.path:
                sys.path.insert(0, _candidate)
        from ravigneaux_solver import RavigneauxTransmission, configure_logging  # type: ignore


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RavignauxRatios:
    first: float
    second: float
    third: float
    reverse: float


def _iter_triplets(
    small_suns: Sequence[int],
    large_suns: Sequence[int],
    rings: Sequence[int],
) -> Iterator[Tuple[int, int, int]]:
    for Ns_small in small_suns:
        for Ns_large in large_suns:
            for Nr in rings:
                yield Ns_small, Ns_large, Nr


def _triplet_count(
    small_suns: Sequence[int],
    large_suns: Sequence[int],
    rings: Sequence[int],
) -> int:
    return len(small_suns) * len(large_suns) * len(rings)


def _wrap_progress(iterator: Iterable, *, total: int, desc: str, enable_progress: bool):
    if enable_progress and tqdm is not None:
        return tqdm(iterator, total=total, desc=desc)
    return iterator


def _basic_geometry_ok(Ns_small: int, Ns_large: int, Nr: int) -> bool:
    """
    Conservative topology filter for the simplified Ravignaux map.

    This intentionally does NOT claim to be full compound-pinion packaging
    validation. It only enforces the assumptions used by the simplified solver:

    - positive tooth counts
    - small sun < large sun < ring
    """
    return (
        Ns_small > 0
        and Ns_large > 0
        and Nr > 0
        and Ns_small < Ns_large < Nr
    )


def _analytic_ratios(Ns_small: int, Ns_large: int, Nr: int) -> RavignauxRatios:
    if not _basic_geometry_ok(Ns_small, Ns_large, Nr):
        raise ValueError("Invalid simplified Ravignaux tooth-count ordering")

    first = 1.0 + (Nr / Ns_small)
    second = 1.0 + (Nr / Ns_large)
    third = 1.0

    # Reverse from the actual simplified state used in the solver:
    #   small sun input = 1, large sun = 0, carrier is output.
    # From the linear equations, carrier = Ns_small / (Ns_small - Ns_large).
    wc = Ns_small / (Ns_small - Ns_large)
    if abs(wc) < 1.0e-12:
        raise ZeroDivisionError("Reverse state produced zero carrier speed")
    reverse = 1.0 / wc

    return RavignauxRatios(
        first=float(first),
        second=float(second),
        third=float(third),
        reverse=float(reverse),
    )


def _solver_ratios(rav: RavigneauxTransmission) -> RavignauxRatios:
    first_solution = rav.first_gear()
    second_solution = rav.second_gear()
    third_solution = rav.third_gear()
    reverse_solution = rav.reverse()

    def ratio(sol: Dict[str, float], num: str, den: str) -> float:
        den_val = float(sol[den])
        if abs(den_val) < 1.0e-12:
            raise ZeroDivisionError(f"Denominator '{den}' has zero speed")
        return float(sol[num]) / den_val

    return RavignauxRatios(
        first=ratio(first_solution, "sun_small", "carrier"),
        second=ratio(second_solution, "sun_large", "carrier"),
        third=ratio(third_solution, "ring", "carrier"),
        reverse=ratio(reverse_solution, "sun_small", "carrier"),
    )


def generate_ravigneaux_map(
    small_sun_range: Iterable[int],
    large_sun_range: Iterable[int],
    ring_range: Iterable[int],
    *,
    include_debug: bool = False,
    enable_progress: bool = True,
    log_every: int = 5000,
    validate_with_solver: bool = False,
    max_abs_reverse: Optional[float] = None,
) -> List[Dict]:
    small_values = list(small_sun_range)
    large_values = list(large_sun_range)
    ring_values = list(ring_range)
    total = _triplet_count(small_values, large_values, ring_values)

    LOGGER.info(
        "Starting Ravignaux sweep: small_suns=%s large_suns=%s rings=%s raw_cases=%s",
        len(small_values),
        len(large_values),
        len(ring_values),
        total,
    )

    processed = 0
    kept = 0
    skipped = 0
    results: List[Dict] = []

    iterator = _wrap_progress(
        _iter_triplets(small_values, large_values, ring_values),
        total=total,
        desc="Ravigneaux map",
        enable_progress=enable_progress,
    )

    for Ns_small, Ns_large, Nr in iterator:
        processed += 1

        if not _basic_geometry_ok(Ns_small, Ns_large, Nr):
            skipped += 1
            continue

        try:
            ratios = _analytic_ratios(Ns_small, Ns_large, Nr)

            if max_abs_reverse is not None and abs(ratios.reverse) > max_abs_reverse:
                skipped += 1
                continue

            if not all(isfinite(v) for v in (ratios.first, ratios.second, ratios.third, ratios.reverse)):
                skipped += 1
                continue

            row = {
                "Ns_small": int(Ns_small),
                "Ns_large": int(Ns_large),
                "Nr": int(Nr),
                "ratios": {
                    "first": ratios.first,
                    "second": ratios.second,
                    "third": ratios.third,
                    "reverse": ratios.reverse,
                },
            }

            if validate_with_solver or include_debug:
                rav = RavigneauxTransmission(
                    Ns_small=Ns_small,
                    Ns_large=Ns_large,
                    Nr=Nr,
                    enable_logging=False,
                )
                solver_ratios = _solver_ratios(rav)
                row["solver_ratios"] = {
                    "first": solver_ratios.first,
                    "second": solver_ratios.second,
                    "third": solver_ratios.third,
                    "reverse": solver_ratios.reverse,
                }
                row["validation_error"] = {
                    "first": abs(ratios.first - solver_ratios.first),
                    "second": abs(ratios.second - solver_ratios.second),
                    "third": abs(ratios.third - solver_ratios.third),
                    "reverse": abs(ratios.reverse - solver_ratios.reverse),
                }
                if include_debug:
                    row["solutions"] = {
                        "first": rav.first_gear(),
                        "second": rav.second_gear(),
                        "third": rav.third_gear(),
                        "reverse": rav.reverse(),
                    }

            results.append(row)
            kept += 1

        except Exception as exc:
            skipped += 1
            LOGGER.debug(
                "Skipping Ns_small=%s Ns_large=%s Nr=%s because %s",
                Ns_small,
                Ns_large,
                Nr,
                exc,
            )

        if log_every > 0 and processed % log_every == 0:
            LOGGER.info("Progress: processed=%s kept=%s skipped=%s", processed, kept, skipped)

    LOGGER.info(
        "Finished Ravignaux sweep: processed=%s kept=%s skipped=%s",
        processed,
        kept,
        skipped,
    )
    return results


def find_near_ratio(
    rows: Sequence[Dict],
    *,
    target: float,
    gear: str = "first",
    tolerance: float = 0.1,
) -> List[Dict]:
    if gear not in {"first", "second", "third", "reverse"}:
        raise ValueError(f"Unsupported gear for search: {gear}")

    matches = [
        row for row in rows
        if abs(float(row["ratios"][gear]) - float(target)) <= float(tolerance)
    ]
    matches.sort(key=lambda row: abs(float(row["ratios"][gear]) - float(target)))
    LOGGER.info(
        "Found %s matches near %.6f for gear=%s tol=%.6f",
        len(matches),
        target,
        gear,
        tolerance,
    )
    return matches


def print_ratio_map(rows: Sequence[Dict], *, limit: int = 25) -> None:
    print("\nRavigneaux Transmission Ratio Map")
    print("-" * 84)
    print(f"{'Ns_s':>6} {'Ns_l':>6} {'Nr':>6} {'1st':>10} {'2nd':>10} {'3rd':>10} {'Rev':>10}")
    print("-" * 84)

    for row in rows[:limit]:
        r = row["ratios"]
        print(
            f"{row['Ns_small']:6d} {row['Ns_large']:6d} {row['Nr']:6d} "
            f"{r['first']:10.3f} {r['second']:10.3f} {r['third']:10.3f} {r['reverse']:10.3f}"
        )


def print_matches(rows: Sequence[Dict], *, gear: str, limit: int = 10) -> None:
    print(f"\nSearch for ~3.0 {gear} gear")
    for row in rows[:limit]:
        r = row["ratios"]
        print(
            f"Ns_small={row['Ns_small']} Ns_large={row['Ns_large']} Nr={row['Nr']} "
            f"1st={r['first']:.3f} 2nd={r['second']:.3f} 3rd={r['third']:.3f} Rev={r['reverse']:.3f}"
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Ravignaux ratio map")

    parser.add_argument("--sun-min", type=int, default=20, help="Shared default minimum for both suns")
    parser.add_argument("--sun-max", type=int, default=40, help="Shared default exclusive maximum for both suns")
    parser.add_argument("--small-sun-min", type=int, default=None, help="Override small-sun minimum")
    parser.add_argument("--small-sun-max", type=int, default=None, help="Override small-sun exclusive maximum")
    parser.add_argument("--large-sun-min", type=int, default=None, help="Override large-sun minimum")
    parser.add_argument("--large-sun-max", type=int, default=None, help="Override large-sun exclusive maximum")
    parser.add_argument("--ring-min", type=int, default=50, help="Ring minimum")
    parser.add_argument("--ring-max", type=int, default=90, help="Ring exclusive maximum")
    parser.add_argument("--limit", type=int, default=25, help="Rows to print")
    parser.add_argument("--search-target", type=float, default=3.0, help="Target ratio to search")
    parser.add_argument(
        "--search-gear",
        type=str,
        default="first",
        choices=["first", "second", "third", "reverse"],
        help="Which gear ratio to search near target",
    )
    parser.add_argument("--tol", type=float, default=0.1, help="Search tolerance")
    parser.add_argument("--log-level", type=str, default="WARNING", help="Logging level")
    parser.add_argument("--no-progress", action="store_true", help="Disable tqdm progress bar")
    parser.add_argument("--validate-with-solver", action="store_true", help="Cross-check rows with the solver")
    parser.add_argument(
        "--max-abs-reverse",
        type=float,
        default=None,
        help="Optional filter to discard rows with |reverse| above this value",
    )
    parser.add_argument("--include-debug", action="store_true", help="Attach solutions / validation details")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    level = getattr(logging, str(args.log_level).upper(), logging.WARNING)
    configure_logging(level)

    small_min = args.small_sun_min if args.small_sun_min is not None else args.sun_min
    small_max = args.small_sun_max if args.small_sun_max is not None else args.sun_max
    large_min = args.large_sun_min if args.large_sun_min is not None else args.sun_min
    large_max = args.large_sun_max if args.large_sun_max is not None else args.sun_max

    LOGGER.info(
        "CLI args: small_sun=[%s,%s) large_sun=[%s,%s) ring=[%s,%s) limit=%s search_target=%s search_gear=%s tol=%s",
        small_min,
        small_max,
        large_min,
        large_max,
        args.ring_min,
        args.ring_max,
        args.limit,
        args.search_target,
        args.search_gear,
        args.tol,
    )

    rows = generate_ravigneaux_map(
        range(int(small_min), int(small_max)),
        range(int(large_min), int(large_max)),
        range(int(args.ring_min), int(args.ring_max)),
        include_debug=bool(args.include_debug),
        enable_progress=not bool(args.no_progress),
        validate_with_solver=bool(args.validate_with_solver),
        max_abs_reverse=args.max_abs_reverse,
    )

    # Present rows sorted by closeness to the search gear target.
    rows_sorted = sorted(rows, key=lambda row: abs(float(row["ratios"][args.search_gear]) - float(args.search_target)))
    print_ratio_map(rows_sorted, limit=int(args.limit))

    matches = find_near_ratio(
        rows,
        target=float(args.search_target),
        gear=str(args.search_gear),
        tolerance=float(args.tol),
    )
    print_matches(matches, gear=str(args.search_gear), limit=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
