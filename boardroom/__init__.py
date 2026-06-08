"""BOARDROOM - Investor-update and KPI one-pager generator from your metrics.

Feed it a small JSON file of monthly metrics and BOARDROOM computes deltas,
growth rates, runway, and assembles a clean investor-update one-pager
(Markdown) plus a machine-readable KPI summary (JSON).

Standard library only. Zero install.
"""
from .core import (
    Period,
    Metric,
    Report,
    parse_metrics,
    build_report,
    pct_change,
    cagr,
    runway_months,
    render_markdown,
)

TOOL_NAME = "boardroom"
TOOL_VERSION = "1.0.0"

__all__ = [
    "Period",
    "Metric",
    "Report",
    "parse_metrics",
    "build_report",
    "pct_change",
    "cagr",
    "runway_months",
    "render_markdown",
    "TOOL_NAME",
    "TOOL_VERSION",
]
