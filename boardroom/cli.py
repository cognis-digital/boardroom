"""Command-line interface for BOARDROOM."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import (
    BoardroomError,
    build_report,
    parse_metrics,
    render_markdown,
)


def _load(path: str) -> dict:
    try:
        if path == "-":
            raw = sys.stdin.read()
        else:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
    except OSError as exc:
        raise BoardroomError(f"cannot read input: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BoardroomError(f"invalid JSON: {exc}") from exc


def _print_table(report) -> None:
    cur = report.currency
    print(f"{report.company} - {report.period_label}")
    if report.prior_label:
        print(f"(vs {report.prior_label})")
    print()
    header = f"{'Metric':<16}{'Current':>16}{'Prior':>16}{'%':>10}  Trend"
    print(header)
    print("-" * len(header))
    arrows = {"up": "up", "down": "dn", "flat": "--"}
    for m in report.metrics:
        prev = "-" if m.previous is None else f"{m.previous:,.2f}"
        pct = "-" if m.change_pct is None else f"{m.change_pct}%"
        trend = arrows[m.direction]
        if m.healthy is True:
            trend += "+"
        elif m.healthy is False:
            trend += "!"
        print(
            f"{m.name:<16}{m.current:>16,.2f}{prev:>16}{pct:>10}  {trend}"
        )
    print()
    if report.derived:
        print("Derived:")
        for k, v in report.derived.items():
            print(f"  {k}: {v}")


def cmd_report(args: argparse.Namespace) -> int:
    doc = parse_metrics(_load(args.input))
    report = build_report(doc)
    if args.markdown:
        sys.stdout.write(render_markdown(report))
        return 0
    if args.format == "json":
        json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_table(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Investor-update and KPI one-pager generator from your metrics.",
    )
    parser.add_argument(
        "--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}"
    )
    sub = parser.add_subparsers(dest="command")

    rep = sub.add_parser(
        "report", help="Generate a KPI summary / investor one-pager from metrics JSON."
    )
    rep.add_argument("input", help="Path to metrics JSON file, or '-' for stdin.")
    rep.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table).",
    )
    rep.add_argument(
        "--markdown",
        action="store_true",
        help="Emit the investor-update one-pager as Markdown instead.",
    )
    rep.set_defaults(func=cmd_report)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except BoardroomError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
