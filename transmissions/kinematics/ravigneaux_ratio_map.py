#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
transmissions.kinematics.ravigneaux_ratio_map

Ravignaux transmission ratio-map generator.

This module is aligned with the upgraded simplified Ravignaux solver:

    members: sun_small, sun_large, ring, carrier

Standard reported states:
- 1st:     sun_small input, ring grounded, carrier output
- 2nd:     sun_large input, ring grounded, carrier output
- 3rd:     ring input, sun_large grounded, carrier output
- 4th:     ring locked to carrier, direct drive
- Reverse: sun_small input, carrier grounded, ring output

Important honesty note
----------------------
This is a fast ratio explorer for the current simplified 4-member topology. It
is not a full compound-pinion production synthesis. In particular, the standard
reverse state still does not depend on Ns_large in this abstraction.
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
        from transmissions.kinematics.ravigneaux_solver import RavigneauxTransmission, configure_logging
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
    fourth: float
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
    return (
        Ns_small > 0
        and Ns_large > 0
        and Nr > 0
        and Ns_small < Ns_large < Nr
        and ((Nr - Ns_small) % 2 == 0)
        and ((Nr - Ns_large) % 2 == 0)
    )


def _analytic_ratios(Ns_small: int, Ns_large: int, Nr: int) -> RavignauxRatios:
    if not _basic_geometry_ok(Ns_small, Ns_large, Nr):
        raise ValueError("Invalid simplified Ravignaux tooth-count ordering")
    first = 1.0 + (Nr / Ns_small)
    second = 1.0 + (Nr / Ns_large)
    third = 1.0 + (Ns_large / Nr)
    fourth = 1.0
    reverse = -(Nr / Ns_small)
    return RavignauxRatios(
        first=float(first),
        second=float(second),
        third=float(third),
        fourth=float(fourth),
        reverse=float(reverse),
    )


def _solver_ratios(rav: RavigneauxTransmission) -> RavignauxRatios:
    return RavignauxRatios(
        first=rav.ratio_for_state("first"),
        second=rav.ratio_for_state("second"),
        third=rav.ratio_for_state("third"),
        fourth=rav.ratio_for_state("fourth"),
        reverse=rav.ratio_for_state("reverse"),
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
            if not all(isfinite(v) for v in (ratios.first, ratios.second, ratios.third, ratios.fourth, ratios.reverse)):
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
                    "fourth": ratios.fourth,
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
                    "fourth": solver_ratios.fourth,
                    "reverse": solver_ratios.reverse,
                }
                row["validation_error"] = {
                    "first": abs(ratios.first - solver_ratios.first),
                    "second": abs(ratios.second - solver_ratios.second),
                    "third": abs(ratios.third - solver_ratios.third),
                    "fourth": abs(ratios.fourth - solver_ratios.fourth),
                    "reverse": abs(ratios.reverse - solver_ratios.reverse),
                }
                if include_debug:
                    row["state_reports"] = {
                        "first": rav.state_report("first"),
                        "second": rav.state_report("second"),
                        "third": rav.state_report("third"),
                        "fourth": rav.state_report("fourth"),
                        "reverse": rav.state_report("reverse"),
                    }
                    row["audit"] = {
                        name: audit.__dict__ for name, audit in rav.audit_standard_states().items()
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
    key = gear.lower()
    valid_keys = {"first", "second", "third", "fourth", "reverse"}
    if key not in valid_keys:
        raise ValueError(f"Invalid gear '{gear}'. Expected one of {sorted(valid_keys)}")
    matches = [row for row in rows if abs(float(row["ratios"][key]) - float(target)) <= float(tolerance)]
    matches.sort(key=lambda row: abs(float(row["ratios"][key]) - float(target)))
    LOGGER.info(
        "Found %s matches near %.6f for gear=%s tol=%.6f",
        len(matches),
        target,
        key,
        tolerance,
    )
    return matches


def print_ravigneaux_map(rows: Sequence[Dict], *, limit: Optional[int] = 25) -> None:
    print("\nRavigneaux Transmission Ratio Map")
    print("-" * 98)
    print(f"{'Ns_s':>6} {'Ns_l':>6} {'Nr':>6} {'1st':>10} {'2nd':>10} {'3rd':>10} {'4th':>10} {'Rev':>10}")
    print("-" * 98)
    count = 0
    for row in rows:
        ratios = row["ratios"]
        print(
            f"{row['Ns_small']:6d} {row['Ns_large']:6d} {row['Nr']:6d} "
            f"{ratios['first']:10.3f} {ratios['second']:10.3f} "
            f"{ratios['third']:10.3f} {ratios['fourth']:10.3f} {ratios['reverse']:10.3f}"
        )
        count += 1
        if limit is not None and count >= limit:
            break


def _print_audit() -> None:
    audits = RavigneauxTransmission(Ns_small=24, Ns_large=34, Nr=60, enable_logging=False).audit_standard_states()
    print("\nStandard state dependency audit")
    print("-" * 98)
    for name in ("first", "second", "third", "fourth", "reverse"):
        a = audits[name]
        depends = ", ".join(a.depends_on) if a.depends_on else "none"
        print(f"{name:>7}: ratio={a.ratio_expression:<18} depends_on={depends} | {a.notes}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a Ravignaux transmission ratio map")
    parser.add_argument("--sun-min", type=int, default=20, help="Minimum sun tooth count (inclusive)")
    parser.add_argument("--sun-max", type=int, default=40, help="Maximum sun tooth count (exclusive)")
    parser.add_argument("--ring-min", type=int, default=50, help="Minimum ring tooth count (inclusive)")
    parser.add_argument("--ring-max", type=int, default=90, help="Maximum ring tooth count (exclusive)")
    parser.add_argument("--limit", type=int, default=25, help="Rows to print in the map output")
    parser.add_argument("--search-target", type=float, default=3.0, help="Target ratio to search for")
    parser.add_argument(
        "--search-gear",
        type=str,
        default="first",
        choices=["first", "second", "third", "fourth", "reverse"],
        help="Which gear ratio to search against",
    )
    parser.add_argument("--tol", type=float, default=0.1, help="Tolerance for near-ratio search")
    parser.add_argument("--no-progress", action="store_true", help="Disable tqdm progress bar")
    parser.add_argument("--validate-with-solver", action="store_true", help="Cross-check analytic ratios with the solver")
    parser.add_argument("--include-debug", action="store_true", help="Include full state reports in generated rows")
    parser.add_argument("--max-abs-reverse", type=float, default=None, help="Skip rows with |reverse| above this limit")
    parser.add_argument(
        "--log-level",
        type=str,
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    parser.add_argument("--print-audit", action="store_true", help="Print symbolic dependency audit for standard states")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    log_level = getattr(logging, str(args.log_level).upper(), logging.WARNING)
    configure_logging(log_level)
    LOGGER.info(
        "CLI args: small_sun=[%s,%s) large_sun=[%s,%s) ring=[%s,%s) limit=%s search_target=%s search_gear=%s tol=%s",
        args.sun_min,
        args.sun_max,
        args.sun_min,
        args.sun_max,
        args.ring_min,
        args.ring_max,
        args.limit,
        args.search_target,
        args.search_gear,
        args.tol,
    )

    rows = generate_ravigneaux_map(
        range(args.sun_min, args.sun_max),
        range(args.sun_min, args.sun_max),
        range(args.ring_min, args.ring_max),
        include_debug=bool(args.include_debug),
        enable_progress=not bool(args.no_progress),
        validate_with_solver=bool(args.validate_with_solver),
        max_abs_reverse=args.max_abs_reverse,
    )

    print_ravigneaux_map(rows, limit=args.limit)
    if args.print_audit:
        _print_audit()

    print(f"\nSearch for ~{args.search_target} {args.search_gear} gear")
    matches = find_near_ratio(
        rows,
        target=args.search_target,
        gear=args.search_gear,
        tolerance=args.tol,
    )
    for row in matches[:10]:
        ratios = row["ratios"]
        print(
            f"Ns_small={row['Ns_small']} Ns_large={row['Ns_large']} Nr={row['Nr']} "
            f"1st={ratios['first']:.3f} 2nd={ratios['second']:.3f} "
            f"3rd={ratios['third']:.3f} 4th={ratios['fourth']:.3f} Rev={ratios['reverse']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
