from __future__ import annotations

import argparse
import json
import sys

try:
    from .apis import list_presets
    from .app import RunRequest, TransmissionApplication, render_text_report
    from .io import load_json
    from .utils import TransmissionAppError, parse_key_value_overrides
except ImportError:
    from apis import list_presets
    from app import RunRequest, TransmissionApplication, render_text_report
    from utils import TransmissionAppError, parse_key_value_overrides

    try:
        from module_loader import load_local_module
    except ImportError:
        from .module_loader import load_local_module  # type: ignore

    _io_mod = load_local_module("io_local", "io.py")
    load_json = _io_mod.load_json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cli",
        description="Universal transmission CLI built from JSON topology + shift schedule.",
    )

    p.add_argument("--spec", dest="spec_path", type=str, required=False, help="Path to transmission spec JSON.")
    p.add_argument("--schedule", dest="schedule_path", type=str, required=False, help="Path to shift schedule JSON.")
    p.add_argument("--preset", type=str, help="Optional preset name defined inside the spec JSON.")
    p.add_argument("--state", type=str, default="all", help="State to solve, e.g. all, 4th, Rev.")
    p.add_argument("--input-speed", type=float, default=1.0, help="Input speed for normalization/reporting.")

    p.add_argument("--show-speeds", action="store_true", help="Show member speeds.")
    p.add_argument("--ratios-only", action="store_true", help="Print condensed ratio table only.")
    p.add_argument("--show-topology", action="store_true", help="Print topology summary.")
    p.add_argument("--as-json", action="store_true", help="Print result payload as JSON.")
    p.add_argument("--out-json", dest="output_json", type=str, help="Optional output JSON path.")

    p.add_argument(
        "--set",
        dest="overrides",
        metavar="KEY=VALUE",
        nargs="*",
        default=[],
        help=(
            "Override spec values. Supported forms: "
            "P1.Ns=48 P1.Nr=96 gearsets.P1.Ns=48 gearsets.P1.Nr=96 "
            "input_member=input output_member=output strict_geometry=true"
        ),
    )

    p.add_argument("--list-presets", action="store_true", help="List spec-defined presets and exit.")
    return p


def _print_presets(spec_path: str | None) -> int:
    if not spec_path:
        print("ERROR: --list-presets requires --spec", file=sys.stderr)
        return 2

    spec = load_json(spec_path)
    names = list_presets(spec)

    print("Available presets")
    print("-" * 80)
    if not names:
        print("(none)")
        return 0

    for name in names:
        print(name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)

    if ns.list_presets:
        return _print_presets(ns.spec_path)

    try:
        req = RunRequest(
            spec_path=ns.spec_path,
            schedule_path=ns.schedule_path,
            preset=ns.preset,
            state=ns.state,
            input_speed=ns.input_speed,
            show_speeds=bool(ns.show_speeds),
            ratios_only=bool(ns.ratios_only),
            show_topology=bool(ns.show_topology),
            as_json=bool(ns.as_json),
            output_json=ns.output_json,
            overrides=parse_key_value_overrides(ns.overrides),
        )

        app = TransmissionApplication()
        payload = app.run(req)

        if ns.as_json:
            print(json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False))
        else:
            print(
                render_text_report(
                    payload,
                    show_speeds=bool(ns.show_speeds),
                    ratios_only=bool(ns.ratios_only),
                )
            )
        return 0

    except TransmissionAppError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"ERROR: file not found: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: unexpected failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())