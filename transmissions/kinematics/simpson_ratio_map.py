#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.simpson_ratio_map

Simpson ratio sweep and search utility.

Fixes in this upgrade:
- correct imports for module execution with:
      python -m kinematics.simpson_ratio_map
  from inside the `transmissions` directory
- fallback imports for other layouts
- logging support
- tqdm progress bar support
- CLI entry point
- avoids apparent hangs by using the upgraded analytic Simpson solver
"""

from __future__ import annotations

import argparse
import logging
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:
    from .simpson_solver import SimpsonTransmission, configure_logging
except Exception:
    try:
        from transmissions.kinematics.simpson_solver import SimpsonTransmission, configure_logging
    except Exception:
        from simpson_solver import SimpsonTransmission, configure_logging  # type: ignore

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    tqdm = None


LOGGER = logging.getLogger(__name__)
_ALLOWED_GEARS = {"first", "second", "third", "reverse"}


def _iter_triplets(sun_range: Iterable[int], ring_range: Iterable[int]) -> Iterator[Tuple[int, int, int]]:
    for Ns in sun_range:
        for Nr1 in ring_range:
            for Nr2 in ring_range:
                yield Ns, Nr1, Nr2


def _triplet_count(sun_range: Sequence[int], ring_range: Sequence[int]) -> int:
    return len(sun_range) * len(ring_range) * len(ring_range)


def _wrap_progress(iterable, *, total: Optional[int], desc: str, enable_progress: bool):
    if enable_progress and tqdm is not None:
        return tqdm(iterable, total=total, desc=desc)
    return iterable


def _ratio(result: Dict[str, float], numerator: str, denominator: str) -> float:
    if numerator not in result:
        raise KeyError(f"Missing numerator member: {numerator}")
    if denominator not in result:
        raise KeyError(f"Missing denominator member: {denominator}")

    den = float(result[denominator])
    if abs(den) < 1.0e-12:
        raise ZeroDivisionError(f"Denominator speed for '{denominator}' is zero")
    return float(result[numerator]) / den


def generate_simpson_map(
    sun_range: Iterable[int],
    ring_range: Iterable[int],
    *,
    include_debug: bool = False,
    require_distinct_rings: bool = False,
    enable_progress: bool = True,
    log_every: int = 5000,
) -> List[Dict]:
    """Generate the Simpson ratio map for the provided tooth ranges."""

    sun_values = list(sun_range)
    ring_values = list(ring_range)
    total = _triplet_count(sun_values, ring_values)

    LOGGER.info(
        "Starting Simpson sweep: suns=%s ring1=%s ring2=%s raw_cases=%s",
        len(sun_values),
        len(ring_values),
        len(ring_values),
        total,
    )

    processed = 0
    kept = 0
    skipped = 0
    results: List[Dict] = []

    iterator = _wrap_progress(
        _iter_triplets(sun_values, ring_values),
        total=total,
        desc="Simpson map",
        enable_progress=enable_progress,
    )

    for Ns, Nr1, Nr2 in iterator:
        processed += 1

        if Nr1 <= Ns or Nr2 <= Ns:
            skipped += 1
            continue
        if require_distinct_rings and Nr1 == Nr2:
            skipped += 1
            continue
        if (Nr1 - Ns) % 2 != 0 or (Nr2 - Ns) % 2 != 0:
            skipped += 1
            continue

        try:
            simpson = SimpsonTransmission(Ns=Ns, Nr1=Nr1, Nr2=Nr2, enable_logging=False)

            first_solution = simpson.first_gear()
            second_solution = simpson.second_gear()
            third_solution = simpson.third_gear()
            reverse_solution = simpson.reverse()

            row = {
                "Ns": int(Ns),
                "Nr1": int(Nr1),
                "Nr2": int(Nr2),
                "ratios": {
                    "first": float(_ratio(first_solution, "sun", "carrier")),
                    "second": float(_ratio(second_solution, "sun", "carrier")),
                    "third": 1.0,
                    "reverse": float(-abs(_ratio(reverse_solution, "sun", "carrier"))),
                },
            }

            if include_debug:
                row["solutions"] = {
                    "first": first_solution,
                    "second": second_solution,
                    "third": third_solution,
                    "reverse": reverse_solution,
                }

            results.append(row)
            kept += 1

        except Exception as exc:
            skipped += 1
            LOGGER.debug("Skipping Ns=%s Nr1=%s Nr2=%s because %s", Ns, Nr1, Nr2, exc)

        if log_every > 0 and processed % log_every == 0:
            LOGGER.info("Progress: processed=%s kept=%s skipped=%s", processed, kept, skipped)

    results.sort(
        key=lambda row: (
            row["ratios"]["first"],
            row["ratios"]["second"],
            row["Ns"],
            row["Nr1"],
            row["Nr2"],
        )
    )

    LOGGER.info("Finished Simpson sweep: processed=%s kept=%s skipped=%s", processed, kept, skipped)
    return results


def search_simpson(
    target_ratio: float,
    sun_range: Iterable[int],
    ring_range: Iterable[int],
    *,
    gear: str = "first",
    tol: float = 0.2,
    include_debug: bool = False,
    require_distinct_rings: bool = False,
    enable_progress: bool = True,
    log_every: int = 5000,
) -> List[Dict]:
    if gear not in _ALLOWED_GEARS:
        raise ValueError(f"gear must be one of {_ALLOWED_GEARS}")
    if tol < 0:
        raise ValueError("tol must be non-negative")

    results = generate_simpson_map(
        sun_range=sun_range,
        ring_range=ring_range,
        include_debug=include_debug,
        require_distinct_rings=require_distinct_rings,
        enable_progress=enable_progress,
        log_every=log_every,
    )

    matches = [row for row in results if abs(row["ratios"][gear] - target_ratio) <= tol]
    matches.sort(
        key=lambda row: (
            abs(row["ratios"][gear] - target_ratio),
            row["Ns"],
            row["Nr1"],
            row["Nr2"],
        )
    )
    LOGGER.info("Found %s matches near %.6f for gear=%s tol=%.6f", len(matches), target_ratio, gear, tol)
    return matches


def print_simpson_table(results: List[Dict], limit: Optional[int] = 50) -> None:
    rows = results if limit is None else results[:limit]

    print()
    print("Simpson Transmission Ratio Map")
    print("----------------------------------------------------------------------------")
    print(f"{'Ns':>5} {'Nr1':>5} {'Nr2':>5} {'1st':>10} {'2nd':>10} {'3rd':>10} {'Rev':>10}")
    print("----------------------------------------------------------------------------")
    for row in rows:
        r = row["ratios"]
        print(
            f"{row['Ns']:5d} {row['Nr1']:5d} {row['Nr2']:5d} "
            f"{r['first']:10.3f} {r['second']:10.3f} {r['third']:10.3f} {r['reverse']:10.3f}"
        )
    print()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simpson transmission ratio map explorer")
    parser.add_argument("--sun-min", type=int, default=20)
    parser.add_argument("--sun-max", type=int, default=40)
    parser.add_argument("--ring-min", type=int, default=50)
    parser.add_argument("--ring-max", type=int, default=90)
    parser.add_argument("--limit", type=int, default=25, help="rows to print from sorted map")
    parser.add_argument("--search-target", type=float, default=3.0, help="target ratio for search")
    parser.add_argument("--search-gear", type=str, default="first", choices=sorted(_ALLOWED_GEARS))
    parser.add_argument("--tol", type=float, default=0.1)
    parser.add_argument("--distinct-rings", action="store_true", help="require Nr1 != Nr2")
    parser.add_argument("--include-debug", action="store_true", help="include raw solved states in rows")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--log-every", type=int, default=5000)
    parser.add_argument("--no-progress", action="store_true", help="disable tqdm progress bar")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    level = getattr(logging, args.log_level.upper(), logging.INFO)
    configure_logging(level)

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

    sun_range = range(args.sun_min, args.sun_max)
    ring_range = range(args.ring_min, args.ring_max)

    results = generate_simpson_map(
        sun_range=sun_range,
        ring_range=ring_range,
        include_debug=args.include_debug,
        require_distinct_rings=args.distinct_rings,
        enable_progress=not args.no_progress,
        log_every=args.log_every,
    )

    print_simpson_table(results, limit=args.limit)

    print(f"Search for ~{args.search_target} {args.search_gear} gear")
    matches = search_simpson(
        target_ratio=args.search_target,
        sun_range=sun_range,
        ring_range=ring_range,
        gear=args.search_gear,
        tol=args.tol,
        include_debug=args.include_debug,
        require_distinct_rings=args.distinct_rings,
        enable_progress=not args.no_progress,
        log_every=args.log_every,
    )

    for row in matches[:10]:
        r = row["ratios"]
        print(
            f"Ns={row['Ns']} Nr1={row['Nr1']} Nr2={row['Nr2']} "
            f"1st={r['first']:.3f} 2nd={r['second']:.3f} 3rd={r['third']:.3f} Rev={r['reverse']:.3f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
